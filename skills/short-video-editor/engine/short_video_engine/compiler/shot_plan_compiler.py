from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import load_contract, read_json, write_json
from ..paths import plan_dir
from ..stage_result import current_command, failure


TALKING_ROLES = {"opening", "opinion", "judgment", "conclusion", "final_summary"}
FORBIDDEN_BASE_VISUALS = {"generated_card", "placeholder", "title_card", "text_card", "generated_diagram"}
ALLOWED_MOTION_RELATIONS = {"comparison", "process", "cause_effect", "timeline", "structure", "kpi_change", "not_x_but_y", "before_after"}

ROLE_PATTERNS = {
    "opinion": re.compile(r"我的答案|我觉得|我认为|我判断|我更倾向|我的观点|在我看来|靠谱吗|担心|不用急着|值得关注"),
    "judgment": re.compile(r"其实|本质|关键是|结论|必须|应该|不应该|判断|观点|不会|太早|大概率"),
    "conclusion": re.compile(r"总结|最后|归根到底|结论|因此|所以|真正值得关注|真正兑现"),
}

RELATION_PATTERNS = [
    ("not_x_but_y", re.compile(r"不是.+而是|not\s+.+\s+but", re.I)),
    ("comparison", re.compile(r"对比|比较|相比|更高|更低| versus | vs\\.? |compare|comparison", re.I)),
    ("process", re.compile(r"流程|步骤|第一|第二|第三|迁移|人工对准|晶圆制造|一次做好|process|step|workflow", re.I)),
    ("cause_effect", re.compile(r"因为|导致|所以|原因|结果|因果|cause|effect|therefore", re.I)),
    ("timeline", re.compile(r"时间线|阶段|周期|去年|今年|明年|timeline|phase", re.I)),
    ("kpi_change", re.compile(r"指标|数据|增长|增加|下降|成本|效率|风险|规模|%|倍|kpi|metric|cost|efficiency|risk", re.I)),
    ("structure", re.compile(r"结构|系统|架构|组成|链路|器件|连接器|理解成|structure|system|architecture", re.I)),
]
BEFORE_AFTER_PATTERN = re.compile(r"之前|之后|以前|现在|过去|新做法|新方案|before|after", re.I)
BEFORE_MARKER_PATTERN = re.compile(r"之前|以前|过去|before", re.I)
AFTER_MARKER_PATTERN = re.compile(r"之后|现在|以后|新做法|新方案|另一种|GlassBridge|after", re.I)


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def load_units(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "script_units.json", {})
    units = payload.get("units") if isinstance(payload, dict) else []
    return [unit for unit in units if isinstance(unit, dict)]


def first_paragraph_end(project_dir: Path) -> int:
    payload = read_json(plan_dir(project_dir) / "script_units.json", {})
    script_path = Path(str(payload.get("source_script") or "")) if isinstance(payload, dict) else Path()
    if not script_path.exists():
        return -1
    text = script_path.read_text(encoding="utf-8", errors="ignore")
    stripped_start = len(text) - len(text.lstrip())
    newline = text.find("\n", stripped_start)
    if newline >= 0:
        return newline
    sentence_end = re.search(r"[。！？!?；;]", text[stripped_start:])
    return stripped_start + sentence_end.end() if sentence_end else len(text)


def load_cues(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
    cues = payload.get("cues") if isinstance(payload, dict) else []
    return [cue for cue in cues if isinstance(cue, dict)]


def load_layout_cues(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "subtitle_layout_cues.json", {})
    cues = payload.get("cues") if isinstance(payload, dict) else []
    return [cue for cue in cues if isinstance(cue, dict)]


def draft_by_unit(project_dir: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "draft_visual_plan.json", {})
    items = []
    if isinstance(payload, dict):
        items = payload.get("shots") or payload.get("units") or payload.get("items") or []
    elif isinstance(payload, list):
        items = payload
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and item.get("unit_id"):
            result[str(item["unit_id"])] = item
    return result


def cues_for_unit(cues: list[dict[str, Any]], unit_id: str) -> list[dict[str, Any]]:
    return [cue for cue in cues if str(cue.get("unit_id") or "") == unit_id]


def layout_intervals(cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    intervals = []
    for cue in cues:
        intervals.append({"cue_id": cue.get("cue_id"), "start": cue.get("start"), "end": cue.get("end"), "display_lines": cue.get("display_lines") or []})
    return intervals


def classify_relation(text: str, draft: dict[str, Any] | None = None) -> str | None:
    relation, _reason = classify_relation_with_reason(text, draft)
    return relation


def classify_relation_with_reason(text: str, draft: dict[str, Any] | None = None) -> tuple[str | None, dict[str, Any]]:
    for relation, pattern in RELATION_PATTERNS:
        match = pattern.search(text)
        if match:
            return relation, {
                "source": "rule_pattern",
                "matched_pattern": pattern.pattern,
                "matched_text": match.group(0),
            }
    before_after_match = BEFORE_AFTER_PATTERN.search(text)
    if before_after_match and BEFORE_MARKER_PATTERN.search(text) and AFTER_MARKER_PATTERN.search(text):
        return "before_after", {
            "source": "paired_temporal_markers",
            "matched_pattern": BEFORE_AFTER_PATTERN.pattern,
            "matched_text": before_after_match.group(0),
        }
    draft_relation = clean_text((draft or {}).get("logic_relation"))
    if draft_relation in ALLOWED_MOTION_RELATIONS:
        return draft_relation, {"source": "draft_visual_plan", "matched_text": draft_relation}
    return None, {"source": "none", "matched_text": ""}


def classify_role(unit: dict[str, Any], index: int, total: int, first_paragraph_boundary: int = -1, draft: dict[str, Any] | None = None) -> str:
    role = clean_text(unit.get("narrative_role") or unit.get("role")).lower()
    text = clean_text(unit.get("source_text") or unit.get("original_text") or unit.get("text"))
    if index == total:
        return "final_summary"
    span = unit.get("source_span") if isinstance(unit.get("source_span"), dict) else {}
    if first_paragraph_boundary >= 0 and int(span.get("start", 10**9)) < first_paragraph_boundary:
        return "opening"
    if role in TALKING_ROLES:
        return role
    for candidate, pattern in ROLE_PATTERNS.items():
        if pattern.search(text):
            return candidate
    draft_role = clean_text((draft or {}).get("narrative_role") or (draft or {}).get("role")).lower()
    if draft_role in TALKING_ROLES:
        return draft_role
    return "explanation"


def extract_required_entities(text: str) -> list[str]:
    entities = re.findall(r"[A-Za-z][A-Za-z0-9._+/#-]*(?:\s+[A-Za-z0-9][A-Za-z0-9._+/#-]*)*", text)
    entities.extend(re.findall(r"\d+(?:\.\d+)?%?", text))
    seen: set[str] = set()
    result = []
    for entity in entities:
        entity = entity.strip()
        if entity and entity not in seen:
            seen.add(entity)
            result.append(entity)
    return result


def wanted_visuals_for(text: str, visual_mode: str, relation: str | None, draft: dict[str, Any] | None) -> list[str]:
    draft_wanted = (draft or {}).get("wanted_visuals")
    values = [str(item) for item in draft_wanted if str(item).strip()] if isinstance(draft_wanted, list) else []
    if visual_mode == "talking_head_fullscreen":
        values.insert(0, "full-screen talking head anchor")
    elif relation:
        values.insert(0, f"real B-roll base with {relation} motion overlay")
    else:
        values.insert(0, "real relevant B-roll footage")
    return values


def compile_shot_plan(project_dir: Path) -> dict[str, Any]:
    units = load_units(project_dir)
    cues = load_cues(project_dir)
    layout_cues = load_layout_cues(project_dir)
    final_contract = load_contract("final_video_contract.json")
    style_preset = load_contract("style_preset.json")
    drafts = draft_by_unit(project_dir)
    first_paragraph_boundary = first_paragraph_end(project_dir)
    shots = []
    for index, unit in enumerate(units, start=1):
        unit_id = str(unit.get("unit_id") or f"unit_{index:03d}")
        text = clean_text(unit.get("source_text") or unit.get("original_text") or unit.get("text"))
        draft = drafts.get(unit_id, {})
        narrative_role = classify_role(unit, index, len(units), first_paragraph_boundary, draft)
        relation, relation_reason = classify_relation_with_reason(text, draft)
        motion_required = bool(relation) and narrative_role not in TALKING_ROLES
        talking_required = narrative_role in TALKING_ROLES
        if talking_required:
            visual_mode = "talking_head_fullscreen"
            motion_required = False
            relation = None
        elif motion_required:
            visual_mode = "broll_fullscreen"
        else:
            visual_mode = "broll_fullscreen"
        unit_cues = cues_for_unit(cues, unit_id)
        unit_layout_cues = cues_for_unit(layout_cues, unit_id)
        start = unit_cues[0].get("start") if unit_cues else None
        end = unit_cues[-1].get("end") if unit_cues else None
        duration = None
        if start is not None and end is not None:
            try:
                duration = round(float(end) - float(start), 3)
            except (TypeError, ValueError):
                duration = None
        shot_id = f"shot_{index:03d}_{unit_id}"
        shots.append(
            {
                "shot_id": shot_id,
                "unit_id": unit_id,
                "subtitle_cue_ids": [str(cue.get("cue_id")) for cue in unit_cues if cue.get("cue_id")],
                "subtitle_layout_cue_ids": [str(cue.get("cue_id")) for cue in unit_layout_cues if cue.get("cue_id")],
                "subtitle_layout_intervals": layout_intervals(unit_layout_cues),
                "subtitle_layout_beat_count": len(unit_layout_cues),
                "start": start,
                "end": end,
                "duration": duration,
                "visual_role": visual_mode,
                "visual_mode": visual_mode,
                "script_fragment": text,
                "wanted_visuals": wanted_visuals_for(text, visual_mode, relation, draft),
                "avoid_visuals": sorted(FORBIDDEN_BASE_VISUALS),
                "required_entities": extract_required_entities(text),
                "talking_head_required": talking_required,
                "motion_overlay_required": motion_required,
                "logic_relation": relation,
                "logic_relation_reason": relation_reason,
                "motion_template": template_for_relation(relation),
                "narrative_role": narrative_role,
                "compiler_notes": {
                    "draft_visual_plan_used_as_weak_signal": bool(draft),
                    "contract_overrode_draft": clean_text(draft.get("visual_mode")) in FORBIDDEN_BASE_VISUALS or clean_text(draft.get("visual_role")) in FORBIDDEN_BASE_VISUALS,
                },
            }
        )
    return {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "compiler": "shot_plan_compiler",
        "command": " ".join(current_command()),
        "source_artifacts": {
            "script_units": "work/plan/script_units.json",
            "subtitle_cues": "work/plan/subtitle_cues.json",
            "subtitle_layout_cues": "work/plan/subtitle_layout_cues.json",
            "final_video_contract": "contracts/final_video_contract.json",
            "style_preset": "contracts/style_preset.json",
        },
        "contract": final_contract.get("contract"),
        "style_preset": style_preset.get("preset"),
        "allowed_motion_relations": sorted(ALLOWED_MOTION_RELATIONS),
        "forbidden_base_visuals": sorted(FORBIDDEN_BASE_VISUALS),
        "shots": shots,
    }


def template_for_relation(relation: str | None) -> str | None:
    if relation == "comparison":
        return "comparison_split_screen"
    if relation == "process":
        return "process_flow"
    if relation == "cause_effect":
        return "cause_effect_chain"
    if relation == "timeline":
        return "timeline"
    if relation == "structure":
        return "system_structure"
    if relation == "kpi_change":
        return "kpi_delta"
    if relation == "before_after":
        return "before_after"
    if relation == "not_x_but_y":
        return "not_x_but_y_bridge"
    return None


def validate_shot_plan_payload(payload: dict[str, Any], project_dir: Path) -> list[dict[str, str]]:
    failures = []
    if payload.get("generated_by") != "short_video_engine":
        failures.append(failure("untrusted_shot_plan", "shot_plan.json was not generated by short_video_engine.", "Regenerate S2 through the engine compiler."))
    shots = payload.get("shots")
    if not isinstance(shots, list) or not shots:
        return failures + [failure("missing_shots", "shot_plan.json has no shots.", "Run S2 compiler.")]
    units = load_units(project_dir)
    expected_units = {str(unit.get("unit_id")) for unit in units if unit.get("unit_id")}
    covered_units = {str(shot.get("unit_id")) for shot in shots if isinstance(shot, dict) and shot.get("unit_id")}
    missing_units = sorted(expected_units - covered_units)
    if missing_units:
        failures.append(failure("script_unit_missing_shot", f"Script units missing shots: {', '.join(missing_units)}", "Regenerate shot_plan from all script units."))
    final_unit = str(units[-1].get("unit_id")) if units else ""
    for shot in shots:
        if not isinstance(shot, dict):
            failures.append(failure("invalid_shot_record", "A shot is not a JSON object.", "Regenerate shot_plan."))
            continue
        unit_id = str(shot.get("unit_id") or "")
        visual_role = clean_text(shot.get("visual_role") or shot.get("visual_mode"))
        visual_mode = clean_text(shot.get("visual_mode") or shot.get("visual_role"))
        if not visual_role:
            failures.append(failure("missing_visual_role", f"Shot {shot.get('shot_id')} lacks visual_role.", "Regenerate S2 compiler output."))
        if not shot.get("subtitle_layout_cue_ids") or int(shot.get("subtitle_layout_beat_count") or 0) <= 0:
            failures.append(failure("missing_subtitle_layout_beats", f"Shot {shot.get('shot_id')} lacks subtitle layout beat references.", "Run S1.5 before S2 and regenerate shot_plan."))
        if visual_mode in FORBIDDEN_BASE_VISUALS or visual_role in FORBIDDEN_BASE_VISUALS:
            failures.append(failure("forbidden_base_visual", f"Shot {shot.get('shot_id')} uses forbidden base visual {visual_mode or visual_role}.", "Use talking_head_fullscreen or real B-roll as base visual."))
        if unit_id == final_unit and (visual_mode != "talking_head_fullscreen" or shot.get("talking_head_required") is not True):
            failures.append(failure("final_summary_must_be_talking_head", "Final summary shot must be talking_head_fullscreen.", "Regenerate S2; contract overrides draft."))
        role = clean_text(shot.get("narrative_role")).lower()
        if role in TALKING_ROLES and (visual_mode != "talking_head_fullscreen" or shot.get("talking_head_required") is not True):
            failures.append(failure("talking_role_requires_talking_head", f"Shot {shot.get('shot_id')} role {role} must be talking_head_fullscreen.", "Regenerate S2; contract overrides draft."))
        relation = shot.get("logic_relation")
        motion_required = bool(shot.get("motion_overlay_required"))
        if motion_required and relation not in ALLOWED_MOTION_RELATIONS:
            failures.append(failure("invalid_motion_relation", f"Shot {shot.get('shot_id')} has invalid motion relation {relation}.", "Use an allowed deterministic logic_relation."))
        if motion_required and role in TALKING_ROLES:
            failures.append(failure("motion_overlay_not_allowed_for_talking_role", f"Shot {shot.get('shot_id')} cannot require motion overlay for {role}.", "Talking-head opinion/conclusion shots cannot use motion as base requirement."))
    return failures


def write_shot_plan(project_dir: Path) -> tuple[Path, list[dict[str, str]]]:
    payload = compile_shot_plan(project_dir)
    path = plan_dir(project_dir) / "shot_plan.json"
    write_json(path, payload)
    return path, validate_shot_plan_payload(payload, project_dir)
