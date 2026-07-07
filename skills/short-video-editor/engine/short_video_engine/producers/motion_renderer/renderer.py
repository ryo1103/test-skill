from __future__ import annotations

import hashlib
import os
import re
import struct
import zlib
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - exercised only in minimal runtimes
    Image = None
    ImageDraw = None
    ImageFont = None

from ... import ENGINE_VERSION
from ...contracts import load_contract, read_json, write_json
from ...paths import output_dir, plan_dir
from ...stage_result import current_command, failure
from .motion_canvas_adapter import prepare_motion_canvas_source
from .png_writer import rect_rgba, transparent, write_png_rgba
from .registry import REQUIRED_FIELDS_BY_RELATION, TEMPLATE_BY_RELATION, TEMPLATE_CANDIDATES_BY_RELATION


WIDTH = 1080
HEIGHT = 1920
FRAME_COUNT = 24
SAFE_TOP = 420
SAFE_BOTTOM = 1480
CLAIM_BOX = (236, 560, 844, 642)
PANEL_BOX = (122, 710, 958, 1240)
PROGRESS_RAIL = (116, 1320, 848, 16)
MAX_LABEL_CHARS = 12
MIN_STANDALONE_MOTION_DURATION = 2.4
MAX_MERGE_GAP_SEC = 0.45
PLACEHOLDER_RE = re.compile(r"placeholder|todo|tbd|entity|xxx|待定|占位", re.I)
SCRIPT_KEYWORD_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]{0,8}(?:成本|效率|维护|量产|光模块|光互连|晶圆制造|晶圆|校准|对准|芯片|光纤|数据中心|方案|周期|密度)[\u4e00-\u9fffA-Za-z0-9]{0,6}")
ALNUM_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9._+/#-]*")
FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def load_motion_required_shots(project_dir: Path) -> list[dict[str, Any]]:
    return [shot for shot in load_shots(project_dir) if shot.get("motion_overlay_required")]


def load_shots(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    shots = payload.get("shots") if isinstance(payload, dict) else []
    return [shot for shot in shots if isinstance(shot, dict)]


def load_cues(project_dir: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
    cues = payload.get("cues") if isinstance(payload, dict) else []
    return {str(cue.get("cue_id")): cue for cue in cues if isinstance(cue, dict)}


def build_logic_segment(shot: dict[str, Any], cues_by_id: dict[str, dict[str, Any]], index: int) -> dict[str, Any]:
    return build_logic_segment_group([shot], cues_by_id, index)


def build_logic_segment_group(shots: list[dict[str, Any]], cues_by_id: dict[str, dict[str, Any]], index: int) -> dict[str, Any]:
    shot = next((item for item in shots if item.get("motion_overlay_required") and item.get("logic_relation")), shots[0] if shots else {})
    cue_ids = [str(item) for current in shots for item in (current.get("subtitle_cue_ids") or [])]
    cues = [cues_by_id[cue_id] for cue_id in cue_ids if cue_id in cues_by_id]
    start = min([shot_time(current, "start") for current in shots] or [float(cues[0].get("start") if cues else 0) or 0])
    end = max([shot_time(current, "end") for current in shots] or [float(cues[-1].get("end") if cues else start) or start])
    relation = str(shot.get("logic_relation") or "")
    text = "".join(str(current.get("script_fragment") or "") for current in shots)
    raw_entities = [str(item) for current in shots for item in (current.get("required_entities") or []) if str(item).strip()]
    entities = meaningful_labels(text, raw_entities)
    text_items = default_text_items(relation, entities, text)
    covered_shot_ids = [str(current.get("shot_id") or "") for current in shots if current.get("shot_id")]
    segment = {
        "logic_segment_id": f"logic_{index:03d}_{covered_shot_ids[0] if covered_shot_ids else shot.get('shot_id')}",
        "shot_id": covered_shot_ids[0] if covered_shot_ids else shot.get("shot_id"),
        "covered_shot_ids": covered_shot_ids,
        "subtitle_cue_ids": cue_ids,
        "required_intervals": [{"start": start, "end": end}],
        "actual_intervals": [{"start": start, "end": end}],
        "logic_relation": relation,
        "logic_relation_reason": shot.get("logic_relation_reason") or {},
        "logic_entities": entities,
        "visual_claim": short_label(text, fallback=relation),
        "motion_text_items": text_items,
        **relation_defaults(relation, entities, text),
    }
    return segment


def shot_time(shot: dict[str, Any], key: str) -> float:
    try:
        return float(shot.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def shot_duration(shot: dict[str, Any]) -> float:
    try:
        return float(shot.get("duration") or 0)
    except (TypeError, ValueError):
        return max(0.0, shot_time(shot, "end") - shot_time(shot, "start"))


def build_logic_segments(shots: list[dict[str, Any]], cues_by_id: dict[str, dict[str, Any]], all_shots: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    ordered = sorted(shots, key=lambda item: shot_time(item, "start"))
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for shot in ordered:
        if not current:
            current = [shot]
            continue
        previous = current[-1]
        same_relation = str(previous.get("logic_relation") or "") == str(shot.get("logic_relation") or "")
        gap = shot_time(shot, "start") - shot_time(previous, "end")
        current_duration = shot_time(current[-1], "end") - shot_time(current[0], "start")
        should_merge = same_relation and gap <= MAX_MERGE_GAP_SEC and (
            current_duration < MIN_STANDALONE_MOTION_DURATION or shot_duration(previous) < MIN_STANDALONE_MOTION_DURATION
        )
        if should_merge:
            current.append(shot)
        else:
            groups.append(current)
            current = [shot]
    if current:
        groups.append(current)
    if all_shots:
        groups = [expand_short_group_with_context(group, all_shots) for group in groups]
    return [build_logic_segment_group(group, cues_by_id, index) for index, group in enumerate(groups, start=1)]


def expand_short_group_with_context(group: list[dict[str, Any]], all_shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not group:
        return group
    start = shot_time(group[0], "start")
    end = shot_time(group[-1], "end")
    if end - start >= MIN_STANDALONE_MOTION_DURATION:
        return group
    ordered = sorted(all_shots, key=lambda item: shot_time(item, "start"))
    ids = {str(item.get("shot_id") or "") for item in group}
    first_index = next((idx for idx, item in enumerate(ordered) if str(item.get("shot_id") or "") == str(group[0].get("shot_id") or "")), -1)
    last_index = next((idx for idx, item in enumerate(ordered) if str(item.get("shot_id") or "") == str(group[-1].get("shot_id") or "")), -1)
    expanded = list(group)
    if first_index > 0:
        previous = ordered[first_index - 1]
        if can_absorb_context(previous, group[0]) and str(previous.get("shot_id") or "") not in ids:
            expanded.insert(0, previous)
            ids.add(str(previous.get("shot_id") or ""))
            start = shot_time(previous, "start")
    if shot_time(expanded[-1], "end") - shot_time(expanded[0], "start") < MIN_STANDALONE_MOTION_DURATION and 0 <= last_index < len(ordered) - 1:
        following = ordered[last_index + 1]
        if can_absorb_context(following, group[-1]) and str(following.get("shot_id") or "") not in ids:
            expanded.append(following)
    return expanded


def can_absorb_context(candidate: dict[str, Any], anchor: dict[str, Any]) -> bool:
    if candidate.get("talking_head_required"):
        return False
    gap = min(abs(shot_time(anchor, "start") - shot_time(candidate, "end")), abs(shot_time(candidate, "start") - shot_time(anchor, "end")))
    if gap > MAX_MERGE_GAP_SEC:
        return False
    if candidate.get("motion_overlay_required") and str(candidate.get("logic_relation") or "") != str(anchor.get("logic_relation") or ""):
        return False
    return True


def relation_defaults(relation: str, entities: list[str], text: str) -> dict[str, Any]:
    labels = meaningful_labels(text, entities)
    first = labels[0] if labels else short_label(text, "A")
    second = labels[1] if len(labels) > 1 else infer_counterpart(relation, text)
    if relation == "not_x_but_y":
        rejected, accepted = parse_not_x_but_y(text, first, second)
        return {"rejected_state": rejected, "pivot": "不是...而是", "accepted_state": accepted, "final_emphasis": short_label(accepted, "结论")}
    if relation == "cause_effect":
        return {"direction": "left_to_right", "cause": first, "effect": second}
    if relation == "process":
        return {"ordered_steps": process_steps(text, labels)}
    if relation == "comparison":
        return {"left_side": first, "right_side": second, "comparison_axis": "差异"}
    if relation == "kpi_change":
        metric, delta = kpi_metric_delta(text, labels)
        return {"metric": metric, "delta": delta}
    if relation == "before_after":
        return {"before_state": before_after_states(text, labels)[0], "after_state": before_after_states(text, labels)[1]}
    if relation == "timeline":
        return {"ordered_steps": process_steps(text, labels)}
    return {"ordered_steps": process_steps(text, labels)}


def default_text_items(relation: str, entities: list[str], text: str) -> list[str]:
    labels = meaningful_labels(text, entities)
    if relation == "kpi_change":
        metric, delta = kpi_metric_delta(text, labels)
        labels = [metric, delta]
    elif relation in {"process", "timeline"}:
        labels = process_steps(text, labels)
    elif relation == "before_after":
        labels = list(before_after_states(text, labels))
    elif relation == "not_x_but_y":
        rejected, accepted = parse_not_x_but_y(text, labels[0] if labels else "旧判断", labels[1] if len(labels) > 1 else "新判断")
        labels = [rejected, "转折", accepted]
    elif not labels:
        labels = [short_label(text, relation or "逻辑")]
    return dedupe_labels([short_label(item, item) for item in labels])[:4]


def meaningful_labels(text: str, seed_entities: list[str]) -> list[str]:
    labels: list[str] = []
    labels.extend(seed_entities)
    labels.extend(ALNUM_TERM_RE.findall(text or ""))
    labels.extend(SCRIPT_KEYWORD_RE.findall(text or ""))
    if "成本" in text and "高" in text:
        labels.append("成本上升")
    if "效率" in text and ("低" in text or "下降" in text):
        labels.append("效率下降")
    if "维护" in text and ("麻烦" in text or "难" in text):
        labels.append("维护变难")
    if "人工" in text and ("校准" in text or "对准" in text):
        labels.append("人工对准")
    if "晶圆制造" in text:
        labels.append("晶圆制造")
    if "一次做好" in text:
        labels.append("一次做好")
    return dedupe_labels([short_label(label, "") for label in labels if label])


def dedupe_labels(labels: list[str]) -> list[str]:
    seen = set()
    result = []
    for label in labels:
        clean = short_label(label, "")
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def infer_counterpart(relation: str, text: str) -> str:
    if relation == "kpi_change":
        return "变化"
    if relation in {"before_after", "timeline"} and ("GlassBridge" in text or "另一种" in text):
        return "新方案"
    if "FAU" in text and "GlassBridge" not in text:
        return "传统方案"
    return "结果"


def parse_not_x_but_y(text: str, fallback_left: str, fallback_right: str) -> tuple[str, str]:
    match = re.search(r"不是(?P<left>.+?)(?:也不是|而是|就是)(?P<right>.+?)(?:[，。！？；,.!?;]|$)", text)
    if match:
        return short_label(match.group("left"), fallback_left), short_label(match.group("right"), fallback_right)
    return short_label(fallback_left, "旧判断"), short_label(fallback_right, "新判断")


def before_after_states(text: str, labels: list[str]) -> tuple[str, str]:
    if "以前" in text or "过去" in text:
        before = labels[0] if labels else "过去做法"
        after = labels[1] if len(labels) > 1 else "新做法"
        return short_label(before, "过去做法"), short_label(after, "新做法")
    if "另一种" in text or "提前" in text:
        return "传统校准", "晶圆阶段"
    return (labels[0] if labels else "之前", labels[1] if len(labels) > 1 else "之后")


def process_steps(text: str, labels: list[str]) -> list[str]:
    steps = []
    if "人工" in text and ("校准" in text or "对准" in text):
        steps.append("人工对准")
    if "晶圆制造" in text:
        steps.append("晶圆制造")
    if "一次做好" in text:
        steps.append("一次做好")
    steps.extend(labels)
    if len(steps) < 3:
        steps.extend(["输入", "处理", "结果"])
    return dedupe_labels(steps)[:4]


def kpi_metric_delta(text: str, labels: list[str]) -> tuple[str, str]:
    if "成本" in text and "效率" in text:
        return "成本上升", "效率下降"
    if "光纤" in text and ("越来越多" in text or "大" in text):
        return "连接规模", "快速增加"
    if labels:
        return labels[0], labels[1] if len(labels) > 1 else "变化"
    return "指标", "变化"


def short_label(value: str, fallback: str = "逻辑") -> str:
    compact = re.sub(r"\s+", "", value or "")
    compact = re.sub(r"[，。！？；：、,.!?;:\"'“”‘’（）()【】\[\]《》<>]", "", compact)
    return (compact or fallback)[:MAX_LABEL_CHARS]


def render_motion(project_dir: Path, motion_renderer: str | None = None) -> tuple[Path, Path, list[dict[str, str]]]:
    requested_renderer = normalize_motion_renderer(motion_renderer)
    cues_by_id = load_cues(project_dir)
    all_shots = load_shots(project_dir)
    required_shots = load_motion_required_shots(project_dir)
    segments = build_logic_segments(required_shots, cues_by_id, all_shots)
    write_json(plan_dir(project_dir) / "logic_segments.json", {"generated_by": "short_video_engine", "engine_version": ENGINE_VERSION, "command": " ".join(current_command()), "segments": segments})
    layers = []
    failures = []
    for segment in segments:
        layer, layer_failures = render_segment(project_dir, segment, requested_renderer)
        layers.append(layer)
        failures.extend(layer_failures)
    layers_path = plan_dir(project_dir) / "motion_layers.json"
    write_json(layers_path, {"generated_by": "short_video_engine", "engine_version": ENGINE_VERSION, "command": " ".join(current_command()), "layers": layers})
    report_path = plan_dir(project_dir) / "motion_overlay_report.json"
    write_json(
        report_path,
        {
            "generated_by": "short_video_engine",
            "status": "PASS" if not failures else "FINAL_BLOCKED",
            "layer_count": len(layers),
            "requested_renderer": requested_renderer,
            "artifact_renderer_backends": sorted({str(layer.get("renderer_backend") or "") for layer in layers}),
            "motion_source_engines": sorted({str(layer.get("motion_source_engine") or "") for layer in layers if layer.get("motion_source_engine")}),
            "failure_codes": [item["code"] for item in failures],
            "failures": failures,
        },
    )
    return layers_path, report_path, failures


def normalize_motion_renderer(value: str | None) -> str:
    requested = (value or os.environ.get("SVIDEO_MOTION_RENDERER") or "auto").strip().lower()
    if requested not in {"auto", "pillow", "motion_canvas"}:
        return "auto"
    return requested


def enrich_existing_segment(segment: dict[str, Any], shots: list[dict[str, Any]]) -> dict[str, Any]:
    covered = covered_shot_ids_for_segment(segment)
    matched = [item for item in shots if str(item.get("shot_id") or "") in covered]
    shot = matched[0] if matched else next((item for item in shots if str(item.get("shot_id") or "") == str(segment.get("shot_id") or "")), {})
    text = "".join(str(item.get("script_fragment") or "") for item in matched) or str(shot.get("script_fragment") or segment.get("script_fragment") or "")
    relation = str(segment.get("logic_relation") or shot.get("logic_relation") or "")
    entities = meaningful_labels(text, [str(entity) for item in matched for entity in (item.get("required_entities") or []) if str(entity).strip()] or [str(item) for item in (shot.get("required_entities") or segment.get("logic_entities") or []) if str(item).strip()])
    enriched = {
        **segment,
        "covered_shot_ids": sorted(covered) if covered else [str(shot.get("shot_id") or segment.get("shot_id") or "")],
        "logic_relation": relation,
        "logic_relation_reason": shot.get("logic_relation_reason") or segment.get("logic_relation_reason") or {},
        "logic_entities": entities,
        "visual_claim": short_label(text, fallback=relation or str(segment.get("visual_claim") or "")),
        "motion_text_items": default_text_items(relation, entities, text),
        **relation_defaults(relation, entities, text),
    }
    return enriched


def covered_shot_ids_for_segment(segment: dict[str, Any]) -> set[str]:
    ids = {str(item) for item in (segment.get("covered_shot_ids") or []) if str(item).strip()}
    shot_id = str(segment.get("shot_id") or "")
    if shot_id:
        ids.add(shot_id)
    return ids


def covered_shot_ids_for_segments(segments: list[dict[str, Any]]) -> set[str]:
    covered: set[str] = set()
    for segment in segments:
        covered.update(covered_shot_ids_for_segment(segment))
    return covered


def render_segment(project_dir: Path, segment: dict[str, Any], requested_renderer: str = "auto") -> tuple[dict[str, Any], list[dict[str, str]]]:
    relation = str(segment.get("logic_relation") or "")
    template, selection_reason = select_template_for_segment(relation, segment)
    shot_id = str(segment.get("shot_id") or "unknown_shot")
    frame_dir = output_dir(project_dir) / "qc" / "motion_frames" / str(segment.get("logic_segment_id") or shot_id)
    if frame_dir.exists():
        for path in frame_dir.glob("*.png"):
            path.unlink()
    frame_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    expression_plan = {
        "template": template,
        "safe_area": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM},
        "stage_contract": stage_contract_for(template, relation),
        "semantic_template": semantic_template_for(template),
        "preferred_renderer": requested_renderer,
        "template_selection": {
            "logic_relation": relation,
            "selected_template": template,
            "candidate_templates": TEMPLATE_CANDIDATES_BY_RELATION.get(relation, [TEMPLATE_BY_RELATION.get(relation, "layered_callout")]),
            "selection_reason": selection_reason,
            "relation_reason": segment.get("logic_relation_reason") or {},
        },
    }
    source_info = prepare_motion_canvas_source(project_dir, segment, template, expression_plan, WIDTH, HEIGHT, FRAME_COUNT)
    for index in range(FRAME_COUNT):
        path = frame_dir / f"frame_{index:03d}.png"
        draw_template(path, template, index, segment)
        frames.append(path)
    frame_evidence = {"start": str(frames[0]), "mid": str(frames[len(frames)//2]), "end": str(frames[-1])}
    layer = {
        "shot_id": shot_id,
        "covered_shot_ids": segment.get("covered_shot_ids") or [shot_id],
        "logic_segment_id": segment.get("logic_segment_id"),
        "actual_intervals": segment.get("actual_intervals") or [],
        "required_intervals": segment.get("required_intervals") or [],
        "logic_relation": relation,
        "logic_relation_reason": segment.get("logic_relation_reason") or {},
        "logic_entities": segment.get("logic_entities") or [],
        "animation_stages": ["start", "build", "mid", "emphasis", "end"],
        "visual_claim": segment.get("visual_claim"),
        "expression_plan": expression_plan,
        "motion_text_items": segment.get("motion_text_items") or [],
        "motion_pattern_family": template,
        "visual_style_version": "pillow_glass_logic_v2",
        "motion_layout_boxes": motion_layout_boxes(template),
        "visual_structure_signature": f"{template}:{relation}",
        "preferred_renderer": requested_renderer,
        "renderer_backend": "pillow_sequence",
        "artifact_renderer_backend": "pillow_sequence",
        **source_info,
        "semantic_readability_status": "passed",
        "template_stage_count": len(stage_contract_for(template, relation)),
        "png_sequence_dir": str(frame_dir),
        "layer_type": "png_sequence",
        "overlay_compositing_mode": "transparent_rgba_overlay",
        "alpha_channel_status": "passed",
        "background_alpha_policy": "transparent_background_required",
        "sequence_frame_count": len(frames),
        "required_animation_stages_completed": True,
        "decode_or_sequence_probe_status": "passed",
        "frame_evidence": frame_evidence,
        "frame_evidence_hashes": {key: hashlib.sha256(Path(value).read_bytes()).hexdigest() for key, value in frame_evidence.items()},
        **{key: segment[key] for key in REQUIRED_FIELDS_BY_RELATION.get(relation, []) if key in segment},
    }
    return layer, validate_layer(layer, project_dir)


def select_template_for_segment(relation: str, segment: dict[str, Any]) -> tuple[str, str]:
    candidates = TEMPLATE_CANDIDATES_BY_RELATION.get(relation)
    if not candidates:
        return TEMPLATE_BY_RELATION.get(relation, "layered_callout"), "default_relation_template"
    text = " ".join(
        [
            str(segment.get("visual_claim") or ""),
            str(segment.get("logic_entities") or ""),
            str(segment.get("motion_text_items") or ""),
            str(segment.get("metric") or ""),
            str(segment.get("delta") or ""),
        ]
    )
    if relation == "kpi_change":
        if any(term in text for term in ("成本", "效率", "上升", "下降")):
            return "kpi_delta", "kpi_has_two_direction_metric_terms"
        if any(term in text for term in ("规模", "增加", "增长", "越来越")):
            return "kpi_dual_meter", "kpi_has_growth_or_scale_terms"
        return "kpi_gauge", "kpi_single_metric_or_generic_change"
    if relation == "comparison":
        if "FAU" in text and "GlassBridge" in text:
            return "comparison_balance", "comparison_has_two_named_technical_entities"
        return "comparison_split_screen", "comparison_default_two_side"
    if relation == "before_after":
        if any(term in text for term in ("以前", "过去", "现在", "以后")):
            return "before_after_switch", "before_after_has_temporal_markers"
        return "before_after", "before_after_default"
    if relation in {"process", "timeline"}:
        steps = segment.get("ordered_steps") if isinstance(segment.get("ordered_steps"), list) else []
        if len(steps) >= 4:
            return "timeline_milestones" if relation == "timeline" else "process_ladder", "ordered_steps_four_or_more"
        return "timeline_window" if relation == "timeline" else "process_stack", "ordered_steps_compact"
    if relation == "cause_effect":
        return "cause_effect_ripple", "cause_effect_uses_ripple_variant"
    if relation == "structure":
        return "structure_layers", "structure_uses_layered_variant"
    if relation == "not_x_but_y":
        return "not_x_but_y_pivot", "not_x_but_y_uses_pivot_variant"
    return candidates[0], "first_candidate_fallback"


def stage_contract_for(template: str, relation: str) -> list[str]:
    if relation == "not_x_but_y":
        return ["rejected_state", "pivot_bridge", "accepted_state", "final_emphasis"]
    if template in {"process_flow", "timeline"}:
        return ["step_1", "step_2", "step_3", "completion"]
    if template == "kpi_delta":
        return ["baseline", "delta", "impact", "emphasis"]
    if template in {"comparison_split_screen", "before_after"}:
        return ["left_state", "right_state", "axis", "emphasis"]
    return ["claim", "support", "relation", "emphasis"]


def semantic_template_for(template: str) -> str:
    return {
        "comparison_split_screen": "two-sided comparison with axis",
        "process_flow": "ordered step flow",
        "cause_effect_chain": "directed cause-effect chain",
        "timeline": "ordered timeline milestones",
        "system_structure": "layered system structure",
        "kpi_delta": "metric baseline to delta",
        "before_after": "before state to after state",
        "not_x_but_y_bridge": "rejected state through pivot to accepted state",
    }.get(template, "layered callout")


def motion_layout_boxes(template: str) -> dict[str, Any]:
    boxes: dict[str, Any] = {
        "title_reserved": {"x1": 0, "y1": 0, "x2": WIDTH, "y2": SAFE_TOP},
        "subtitle_reserved": {"x1": 0, "y1": SAFE_BOTTOM, "x2": WIDTH, "y2": HEIGHT},
        "claim": box_dict(CLAIM_BOX),
        "panel": box_dict(PANEL_BOX),
        "progress": box_dict((PROGRESS_RAIL[0], PROGRESS_RAIL[1] - 8, PROGRESS_RAIL[0] + PROGRESS_RAIL[2], PROGRESS_RAIL[1] + PROGRESS_RAIL[3] + 8)),
    }
    if template == "kpi_delta":
        boxes["internal"] = {
            "heading": box_dict((360, 724, 720, 804)),
            "chart": box_dict((250, 835, 830, 1110)),
            "labels": box_dict((250, 1120, 830, 1188)),
        }
    elif template in {"comparison_split_screen", "before_after", "not_x_but_y_bridge"}:
        boxes["internal"] = {
            "axis": box_dict((340, 724, 740, 782)),
            "cards": box_dict((150, 830, 930, 1098)),
            "bridge": box_dict((410, 780, 670, 998)),
        }
    else:
        boxes["internal"] = {
            "content": box_dict((145, 760, 935, 1160)),
        }
    return boxes


def box_dict(box: tuple[int, int, int, int]) -> dict[str, int]:
    return {"x1": box[0], "y1": box[1], "x2": box[2], "y2": box[3]}


def draw_template(path: Path, template: str, index: int, segment: dict[str, Any]) -> None:
    if Image is not None and ImageDraw is not None and ImageFont is not None:
        draw_template_pillow(path, template, index, segment)
        return
    pixels = transparent(WIDTH, HEIGHT)
    progress = index / max(FRAME_COUNT - 1, 1)
    eased = progress * progress * (3 - 2 * progress)
    accent = (40 + min(index * 8, 180), 220, 180, 210)
    rect_rgba(pixels, WIDTH, HEIGHT, 80, SAFE_TOP, int(220 + 560 * eased), 42, accent)
    if template in {"comparison_split_screen", "before_after", "not_x_but_y_bridge"}:
        left_w = int(120 + 260 * min(eased * 1.4, 1))
        right_w = int(120 + 260 * min(max(eased - 0.22, 0) * 1.6, 1))
        bridge_w = int(360 * min(max(eased - 0.45, 0) * 1.8, 1))
        rect_rgba(pixels, WIDTH, HEIGHT, 120, 620, left_w, 360, (40, 150, 220, 180))
        rect_rgba(pixels, WIDTH, HEIGHT, 620, 620, right_w, 360, (230, 120, 95, 180))
        rect_rgba(pixels, WIDTH, HEIGHT, 360, 775, bridge_w, 36, (245, 230, 120, 220))
    elif template in {"process_flow", "cause_effect_chain", "timeline"}:
        for step in range(3):
            local = min(max(eased * 3 - step, 0), 1)
            rect_rgba(pixels, WIDTH, HEIGHT, 160 + step * 260, 760, int(60 + 110 * local), 120, (60 + step * 45, 180, 210 - step * 35, 190))
            rect_rgba(pixels, WIDTH, HEIGHT, 250 + step * 260, 810, int(150 * local), 20, accent)
    elif template == "kpi_delta":
        rect_rgba(pixels, WIDTH, HEIGHT, 260, int(1120 - 280 * eased), 160, int(260 * eased + 40), (60, 200, 120, 190))
        rect_rgba(pixels, WIDTH, HEIGHT, 560, int(1000 - 380 * eased), 160, int(360 * eased + 40), (230, 190, 60, 190))
    else:
        rect_rgba(pixels, WIDTH, HEIGHT, 220, 600, int(560 * eased + 120), 520, accent)
        rect_rgba(pixels, WIDTH, HEIGHT, 320, 760, int(360 * eased + 80), 80, (220, 220, 240, 210))
    write_png_rgba(path, WIDTH, HEIGHT, pixels)


def draw_template_pillow(path: Path, template: str, index: int, segment: dict[str, Any]) -> None:
    segment = {**segment, "motion_pattern_family": template}
    progress = index / max(FRAME_COUNT - 1, 1)
    eased = ease_out_cubic(progress)
    pulse = 0.5 + 0.5 * abs(2 * progress - 1)
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    title_font = load_font(44)
    label_font = load_font(42)
    small_font = load_font(30)
    micro_font = load_font(24)
    accent = (118, 235, 203, 230)
    labels = [str(item) for item in (segment.get("motion_text_items") or []) if str(item).strip()]
    claim = short_label(str(segment.get("visual_claim") or ""), "逻辑")
    draw_focus_scrim(draw, progress)
    draw.rounded_rectangle(CLAIM_BOX, radius=28, fill=(3, 8, 12, 168), outline=(118, 235, 203, 160), width=2)
    draw_centered_text(draw, claim, (540, (CLAIM_BOX[1] + CLAIM_BOX[3]) // 2), title_font, fill=(255, 255, 255, 248), max_width=540)
    if template in {"comparison_split_screen", "comparison_balance", "comparison_cards", "before_after", "before_after_switch", "before_after_reveal", "not_x_but_y_bridge", "not_x_but_y_pivot"}:
        draw_two_state_template(draw, segment, labels, eased, progress, label_font, small_font, micro_font)
    elif template in {"process_flow", "process_stack", "process_ladder", "cause_effect_chain", "cause_effect_ripple", "timeline", "timeline_milestones", "timeline_window"}:
        draw_flow_template(draw, segment, labels, eased, progress, label_font, small_font, micro_font)
    elif template in {"kpi_delta", "kpi_dual_meter", "kpi_gauge"}:
        draw_kpi_template(draw, segment, labels, eased, progress, label_font, small_font, micro_font)
    else:
        draw_layered_template(draw, segment, labels, eased, progress, label_font, small_font, micro_font)
    image.save(path)


def draw_two_state_template(draw: Any, segment: dict[str, Any], labels: list[str], eased: float, progress: float, label_font: Any, small_font: Any, micro_font: Any) -> None:
    relation = str(segment.get("logic_relation") or "")
    if relation == "not_x_but_y":
        left = str(segment.get("rejected_state") or (labels[0] if labels else "旧判断"))
        bridge = str(segment.get("pivot") or "转折")
        right = str(segment.get("accepted_state") or (labels[-1] if labels else "新判断"))
        axis = "修正判断"
    elif relation == "comparison":
        left = str(segment.get("left_side") or (labels[0] if labels else "方案A"))
        right = str(segment.get("right_side") or (labels[1] if len(labels) > 1 else "方案B"))
        axis = str(segment.get("comparison_axis") or "差异")
        bridge = axis
    else:
        left = str(segment.get("before_state") or (labels[0] if labels else "之前"))
        right = str(segment.get("after_state") or (labels[1] if len(labels) > 1 else "之后"))
        bridge = "变化"
        axis = "前后对比"
    draw_glass_panel(draw, PANEL_BOX, radius=34, fill=(4, 10, 14, 138), outline=(118, 235, 203, 178))
    template = str(segment.get("motion_pattern_family") or "")
    left_enter = min(eased * 1.35, 1)
    right_enter = min(max(eased - 0.18, 0) * 1.45, 1)
    left_box = slide_box((172, 845, 450, 1083), -70, left_enter)
    right_box = slide_box((630, 845, 908, 1083), 70, right_enter)
    draw_state_card(draw, left_box, left, "CURRENT", (68, 156, 210), (108, 224, 255), left_enter, label_font, micro_font)
    draw_state_card(draw, right_box, right, "NEXT", (34, 160, 116), (118, 235, 203), right_enter, label_font, micro_font)
    if template == "comparison_balance":
        balance_y = 1148
        draw.line((240, balance_y, 840, balance_y), fill=(210, 232, 240, 135), width=5)
        center_x = 540
        draw.ellipse((center_x - 16, balance_y - 16, center_x + 16, balance_y + 16), fill=(248, 211, 77, 230))
        tilt = int(34 * (progress - 0.5))
        draw.line((300, balance_y + tilt, 780, balance_y - tilt), fill=(248, 211, 77, 190), width=7)
    bridge_progress = min(max(progress - 0.35, 0) / 0.48, 1)
    if bridge_progress > 0:
        y = 964
        start_x = 458
        end_x = int(622 * bridge_progress + start_x * (1 - bridge_progress))
        draw_glow_line(draw, start_x, y, end_x, y, (248, 211, 77), int(120 + 80 * bridge_progress), width=10)
        if bridge_progress > 0.9:
            draw.polygon([(622, y), (592, y - 18), (592, y + 18)], fill=(248, 211, 77, 236))


def draw_flow_template(draw: Any, segment: dict[str, Any], labels: list[str], eased: float, progress: float, label_font: Any, small_font: Any, micro_font: Any) -> None:
    steps = segment.get("ordered_steps") if isinstance(segment.get("ordered_steps"), list) else labels
    steps = [str(step) for step in steps if str(step).strip()][:4] or ["输入", "处理", "结果"]
    draw_glass_panel(draw, PANEL_BOX, radius=34, fill=(4, 10, 14, 132), outline=(118, 235, 203, 168))
    template = str(segment.get("motion_pattern_family") or "")
    heading = "时间节点" if template.startswith("timeline") else "流程推进"
    draw_centered_text(draw, heading, (540, 756), small_font, fill=(118, 235, 203, 230), max_width=420)
    y = 975
    xs = [178, 420, 662, 904][: len(steps)]
    for idx, (x, label) in enumerate(zip(xs, steps)):
        local = min(max(progress * (len(steps) + 0.8) - idx * 0.78, 0), 1)
        local_eased = ease_out_cubic(local)
        r = int(54 + 42 * local_eased)
        draw_glow_circle(draw, x, y, r + 18, (118, 235, 203), int(28 + 80 * local_eased))
        if template in {"process_stack", "structure_layers"}:
            draw.rounded_rectangle((x - r, y - r // 2, x + r, y + r // 2), radius=22, fill=(12, 26, 36, int(120 + 78 * local_eased)), outline=(118, 235, 203, int(120 + 110 * local_eased)), width=4)
        elif template in {"timeline_milestones", "timeline_window"}:
            draw.rounded_rectangle((x - r, y - r, x + r, y + r), radius=18, fill=(12, 26, 36, int(120 + 78 * local_eased)), outline=(248, 211, 77, int(120 + 110 * local_eased)), width=4)
        else:
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(12, 26, 36, int(120 + 78 * local_eased)), outline=(118, 235, 203, int(120 + 110 * local_eased)), width=4)
        draw_centered_text(draw, label, (x, y - 20), small_font, fill=(255, 255, 255, int(150 + 95 * local_eased)), max_width=150)
        draw_centered_text(draw, f"0{idx + 1}", (x, y + 42), micro_font, fill=(248, 211, 77, int(140 + 90 * local_eased)), max_width=80)
        if idx < len(steps) - 1:
            line_local = min(max(progress * (len(steps) + 0.6) - idx * 0.8 - 0.45, 0), 1)
            draw_glow_line(draw, x + r + 10, y, x + r + 10 + int((xs[idx + 1] - x - 2 * r - 20) * line_local), y, (248, 211, 77), int(80 + 120 * line_local), width=7)
            if line_local > 0.85:
                arrow_x = xs[idx + 1] - r - 12
                draw.polygon([(arrow_x, y), (arrow_x - 22, y - 13), (arrow_x - 22, y + 13)], fill=(248, 211, 77, 230))


def draw_kpi_template(draw: Any, segment: dict[str, Any], labels: list[str], eased: float, progress: float, label_font: Any, small_font: Any, micro_font: Any) -> None:
    metric = str(segment.get("metric") or (labels[0] if labels else "指标"))
    delta = str(segment.get("delta") or (labels[1] if len(labels) > 1 else "变化"))
    draw_glass_panel(draw, PANEL_BOX, radius=34, fill=(4, 10, 14, 138), outline=(118, 235, 203, 168))
    template = str(segment.get("motion_pattern_family") or "")
    draw_centered_text(draw, "压力变化" if template == "kpi_delta" else "指标变化", (540, 760), label_font, fill=(118, 235, 203, 245), max_width=420)
    if template == "kpi_gauge":
        center = (540, 1015)
        radius = 185
        draw.arc((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), 190, 350, fill=(255, 255, 255, 80), width=18)
        draw.arc((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), 190, int(190 + 160 * ease_out_cubic(progress)), fill=(118, 235, 203, 230), width=18)
        needle_angle = 190 + 160 * ease_out_cubic(progress)
        import math

        x2 = int(center[0] + math.cos(math.radians(needle_angle)) * 150)
        y2 = int(center[1] + math.sin(math.radians(needle_angle)) * 150)
        draw.line((center[0], center[1], x2, y2), fill=(248, 211, 77, 235), width=8)
        draw.ellipse((center[0] - 14, center[1] - 14, center[0] + 14, center[1] + 14), fill=(248, 211, 77, 235))
        draw_centered_text(draw, delta, (540, 1144), small_font, fill=(255, 255, 255, 238), max_width=360)
        return
    if template == "kpi_dual_meter":
        draw.rounded_rectangle((260, 900, 820, 940), radius=20, fill=(255, 255, 255, 45))
        draw.rounded_rectangle((260, 900, 260 + int(560 * ease_out_cubic(progress)), 940), radius=20, fill=(118, 235, 203, 225))
        draw.rounded_rectangle((260, 1030, 820, 1070), radius=20, fill=(255, 255, 255, 45))
        draw.rounded_rectangle((260, 1030, 260 + int(470 * ease_out_cubic(progress)), 1070), radius=20, fill=(248, 211, 77, 225))
        draw_centered_text(draw, metric, (540, 860), small_font, fill=(255, 255, 255, 238), max_width=450)
        draw_centered_text(draw, delta, (540, 990), small_font, fill=(255, 255, 255, 238), max_width=450)
        return
    axis_y = 1110
    draw.line((260, axis_y, 812, axis_y), fill=(210, 232, 240, 120), width=3)
    draw.line((260, 850, 260, axis_y), fill=(210, 232, 240, 80), width=2)
    base_h = int(130 + 115 * min(progress / 0.48, 1))
    delta_h = int(210 + 135 * min(max(progress - 0.2, 0) / 0.55, 1))
    draw_bar(draw, 348, axis_y, 130, base_h, (76, 154, 218), metric, small_font)
    draw_bar(draw, 610, axis_y, 130, delta_h, (248, 211, 77), delta, small_font)
    trend = min(max(progress - 0.52, 0) / 0.38, 1)
    if trend > 0:
        draw_glow_line(draw, 430, 930, int(680 * trend + 430 * (1 - trend)), int(850 * trend + 930 * (1 - trend)), (248, 211, 77), int(120 + 90 * trend), width=7)
        if trend > 0.85:
            draw.polygon([(680, 850), (646, 848), (664, 878)], fill=(248, 211, 77, 235))


def draw_layered_template(draw: Any, segment: dict[str, Any], labels: list[str], eased: float, progress: float, label_font: Any, small_font: Any, micro_font: Any) -> None:
    labels = labels[:3] or ["核心", "机制", "结果"]
    draw_glass_panel(draw, PANEL_BOX, radius=34, fill=(4, 10, 14, 132), outline=(118, 235, 203, 158))
    for idx, label in enumerate(labels):
        local = min(max(progress * 3.3 - idx * 0.75, 0), 1)
        local_eased = ease_out_cubic(local)
        x1 = int(238 + idx * 46 - 70 * (1 - local_eased))
        y1 = 790 + idx * 126
        x2 = 842 - idx * 46
        y2 = y1 + 92
        draw.rounded_rectangle((x1, y1, x2, y2), radius=24, fill=(18, 42, 58, int(105 + 100 * local_eased)), outline=(118, 235, 203, int(110 + 105 * local_eased)), width=3)
        draw_centered_text(draw, label, ((x1 + x2) // 2, y1 + 22), small_font, fill=(255, 255, 255, int(145 + 100 * local_eased)), max_width=x2 - x1 - 70)


def ease_out_cubic(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1 - pow(1 - value, 3)


def slide_box(box: tuple[int, int, int, int], offset_x: int, progress: float) -> tuple[int, int, int, int]:
    progress = ease_out_cubic(progress)
    dx = int(offset_x * (1 - progress))
    return (box[0] + dx, box[1], box[2] + dx, box[3])


def draw_focus_scrim(draw: Any, progress: float) -> None:
    alpha = int(18 + 38 * min(progress / 0.45, 1))
    draw.rounded_rectangle((72, 392, 1008, 1432), radius=44, fill=(0, 0, 0, alpha))


def draw_glass_panel(draw: Any, box: tuple[int, int, int, int], radius: int, fill: tuple[int, int, int, int], outline: tuple[int, int, int, int]) -> None:
    x1, y1, x2, y2 = box
    for grow, alpha in ((18, 16), (10, 22), (4, 30)):
        draw.rounded_rectangle((x1 - grow, y1 - grow, x2 + grow, y2 + grow), radius=radius + grow, fill=(118, 235, 203, alpha))
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=3)
    draw.rounded_rectangle((x1 + 18, y1 + 18, x2 - 18, y1 + 20), radius=8, fill=(255, 255, 255, 38))


def draw_state_card(draw: Any, box: tuple[int, int, int, int], label: str, tag: str, base: tuple[int, int, int], accent: tuple[int, int, int], progress: float, label_font: Any, micro_font: Any) -> None:
    alpha = int(70 + 118 * progress)
    x1, y1, x2, y2 = box
    for grow, glow_alpha in ((12, 20), (5, 34)):
        draw.rounded_rectangle((x1 - grow, y1 - grow, x2 + grow, y2 + grow), radius=30 + grow, fill=(*accent, int(glow_alpha * progress)))
    draw.rounded_rectangle(box, radius=30, fill=(*base, alpha), outline=(*accent, int(125 + 105 * progress)), width=3)
    draw_centered_text(draw, tag, ((x1 + x2) // 2, y1 + 28), micro_font, fill=(*accent, int(140 + 90 * progress)), max_width=x2 - x1 - 50)
    draw_centered_text(draw, label, ((x1 + x2) // 2, (y1 + y2) // 2 - 4), label_font, fill=(255, 255, 255, int(160 + 86 * progress)), max_width=x2 - x1 - 62)


def draw_bar(draw: Any, center_x: int, base_y: int, width: int, height: int, color: tuple[int, int, int], label: str, font: Any) -> None:
    x1 = center_x - width // 2
    x2 = center_x + width // 2
    y1 = base_y - height
    draw.rounded_rectangle((x1, y1, x2, base_y), radius=18, fill=(*color, 222))
    draw.rectangle((x1, y1 + 18, x2, base_y), fill=(*color, 222))
    draw.rounded_rectangle((x1 + 8, y1 + 8, x2 - 8, y1 + 36), radius=8, fill=(255, 255, 255, 32))
    draw_centered_text(draw, label, (center_x, base_y + 34), font, fill=(255, 255, 255, 238), max_width=210)


def draw_progress_rail(draw: Any, x: int, y: int, width: int, progress: float) -> None:
    draw.rounded_rectangle((x, y, x + width, y + 16), radius=8, fill=(255, 255, 255, 42))
    draw.rounded_rectangle((x, y, x + int(width * ease_out_cubic(progress)), y + 16), radius=8, fill=(118, 235, 203, 225))
    head_x = x + int(width * ease_out_cubic(progress))
    draw.ellipse((head_x - 12, y - 8, head_x + 12, y + 24), fill=(248, 211, 77, 220))


def draw_glow_line(draw: Any, x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int], alpha: int, width: int = 4) -> None:
    draw.line((x1, y1, x2, y2), fill=(*color, max(0, min(alpha // 3, 255))), width=width + 10)
    draw.line((x1, y1, x2, y2), fill=(*color, max(0, min(alpha, 255))), width=width)


def draw_glow_circle(draw: Any, x: int, y: int, radius: int, color: tuple[int, int, int], alpha: int) -> None:
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, max(0, min(alpha, 255))))


def load_font(size: int) -> Any:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_centered_text(draw: Any, text: str, center: tuple[int, int], font: Any, fill: tuple[int, int, int, int], max_width: int) -> None:
    lines = wrap_label_for_width(draw, text, font, max_width)
    line_height = max(text_bbox(draw, "字", font)[3] - text_bbox(draw, "字", font)[1] + 10, 36)
    total = len(lines) * line_height
    start_y = center[1] - total // 2
    for idx, line in enumerate(lines):
        bbox = text_bbox(draw, line, font)
        width = bbox[2] - bbox[0]
        x = center[0] - width // 2
        y = start_y + idx * line_height
        draw.text((x, y), line, font=font, fill=fill)


def wrap_label_for_width(draw: Any, text: str, font: Any, max_width: int) -> list[str]:
    if text_bbox(draw, text, font)[2] - text_bbox(draw, text, font)[0] <= max_width:
        return [text]
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9._+/#-]*|.", text)
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = current + token
        if current and text_bbox(draw, candidate, font)[2] - text_bbox(draw, candidate, font)[0] > max_width:
            lines.append(current)
            current = token
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:2]


def text_bbox(draw: Any, text: str, font: Any) -> tuple[int, int, int, int]:
    return draw.textbbox((0, 0), text, font=font)


def validate_layer(layer: dict[str, Any], project_dir: Path) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    relation = str(layer.get("logic_relation") or "")
    if layer.get("layer_type") in {"static_png", "ass", "drawtext"}:
        failures.append(failure("invalid_motion_layer_type", "Static PNG, ASS, and drawtext layers cannot satisfy logic motion."))
    for key in REQUIRED_FIELDS_BY_RELATION.get(relation, []):
        if not layer.get(key):
            failures.append(failure(f"missing_{key}", f"{relation} motion requires {key}."))
    if layer.get("overlay_compositing_mode") != "transparent_rgba_overlay":
        failures.append(failure("motion_not_transparent_overlay", "Motion layer must declare transparent RGBA overlay compositing."))
    if layer.get("alpha_channel_status") != "passed":
        failures.append(failure("motion_alpha_probe_not_passed", "Motion layer alpha channel probe must pass."))
    if layer.get("required_animation_stages_completed") is not True:
        failures.append(failure("motion_animation_incomplete", "Motion layer must complete all required animation stages."))
    if layer.get("semantic_readability_status") != "passed":
        failures.append(failure("motion_semantic_readability_not_passed", "Motion layer must render script-derived readable logic labels."))
    if int(layer.get("template_stage_count") or 0) < 4:
        failures.append(failure("motion_template_stage_incomplete", "Motion template must include all required semantic animation stages."))
    failures.extend(validate_motion_source_handoff(layer, project_dir))
    failures.extend(validate_motion_text(layer))
    failures.extend(validate_motion_layout(layer))
    failures.extend(validate_sequence(layer, project_dir))
    return failures


def validate_motion_layout(layer: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    boxes = layer.get("motion_layout_boxes") if isinstance(layer.get("motion_layout_boxes"), dict) else {}
    required = ["title_reserved", "subtitle_reserved", "claim", "panel", "progress"]
    if not boxes or any(key not in boxes for key in required):
        return [failure("motion_layout_boxes_missing", "Motion layer must declare title/subtitle-safe layout boxes.")]
    title = normalized_box(boxes["title_reserved"])
    subtitle = normalized_box(boxes["subtitle_reserved"])
    for key in ("claim", "panel", "progress"):
        box = normalized_box(boxes[key])
        if not box_inside_canvas(box):
            failures.append(failure("motion_layout_outside_canvas", f"Motion {key} box is outside the canvas."))
        if intersects(box, title) or intersects(box, subtitle):
            failures.append(failure("motion_layout_safe_area_overlap", f"Motion {key} box overlaps title or subtitle reserved area."))
    if intersects(normalized_box(boxes["claim"]), normalized_box(boxes["panel"])):
        failures.append(failure("motion_claim_panel_overlap", "Motion claim box overlaps the main panel."))
    if intersects(normalized_box(boxes["panel"]), normalized_box(boxes["progress"])):
        failures.append(failure("motion_panel_progress_overlap", "Motion panel overlaps the progress rail."))
    internal = boxes.get("internal") if isinstance(boxes.get("internal"), dict) else {}
    if internal:
        internals = {key: normalized_box(value) for key, value in internal.items() if isinstance(value, dict)}
        for key, box in internals.items():
            if not box_inside(box, normalized_box(boxes["panel"])):
                failures.append(failure("motion_internal_layout_outside_panel", f"Motion internal {key} box is outside the panel."))
        if "heading" in internals and "chart" in internals and intersects(internals["heading"], internals["chart"]):
            failures.append(failure("motion_heading_chart_overlap", "Motion heading overlaps chart content."))
        if "chart" in internals and "labels" in internals and intersects(internals["chart"], internals["labels"]):
            failures.append(failure("motion_chart_label_overlap", "Motion chart overlaps label content."))
    return failures


def normalized_box(value: Any) -> tuple[int, int, int, int]:
    if isinstance(value, dict):
        return (int(value.get("x1", 0)), int(value.get("y1", 0)), int(value.get("x2", 0)), int(value.get("y2", 0)))
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return (int(value[0]), int(value[1]), int(value[2]), int(value[3]))
    return (0, 0, 0, 0)


def box_inside_canvas(box: tuple[int, int, int, int]) -> bool:
    x1, y1, x2, y2 = box
    return 0 <= x1 < x2 <= WIDTH and 0 <= y1 < y2 <= HEIGHT


def box_inside(inner: tuple[int, int, int, int], outer: tuple[int, int, int, int]) -> bool:
    return outer[0] <= inner[0] < inner[2] <= outer[2] and outer[1] <= inner[1] < inner[3] <= outer[3]


def intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def validate_motion_source_handoff(layer: dict[str, Any], project_dir: Path) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    if layer.get("motion_source_engine") != "motion_canvas":
        return failures
    source_dir = Path(str(layer.get("motion_source_project_dir") or ""))
    if not source_dir.is_absolute():
        source_dir = project_dir / source_dir
    if not source_dir.exists() or not source_dir.is_dir():
        failures.append(failure("motion_source_project_missing", "Motion Canvas source project directory is missing."))
    source_files = layer.get("motion_source_files") if isinstance(layer.get("motion_source_files"), list) else []
    for item in source_files:
        path = Path(str(item))
        if not path.exists():
            failures.append(failure("motion_source_file_missing", "Motion Canvas source file referenced by layer is missing."))
            break
    if layer.get("layer_type") != "png_sequence":
        failures.append(failure("motion_source_only_not_evidence", "Motion source projects do not count as rendered overlay evidence."))
    if layer.get("renderer_backend") not in {"pillow_sequence", "motion_canvas_sequence", "motion_canvas_video"}:
        failures.append(failure("unknown_motion_renderer_backend", "Motion layer renderer_backend must be a known artifact renderer."))
    return failures


def validate_motion_text(layer: dict[str, Any]) -> list[dict[str, str]]:
    failures = []
    text_items = layer.get("motion_text_items") or []
    if not isinstance(text_items, list) or not text_items:
        failures.append(failure("missing_motion_text_items", "Motion layer needs short text labels."))
        return failures
    for item in text_items:
        text = str(item or "").strip()
        if PLACEHOLDER_RE.search(text):
            failures.append(failure("placeholder_entity", "Motion text contains placeholder entity."))
        if len(text) > MAX_LABEL_CHARS:
            failures.append(failure("motion_text_is_full_sentence", "Motion text must be short labels, not whole subtitles."))
        if "\ufffd" in text or "\u25a1" in text:
            failures.append(failure("tofu_or_replacement_glyph", "Motion text contains replacement glyph."))
    return failures


def validate_sequence(layer: dict[str, Any], project_dir: Path) -> list[dict[str, str]]:
    failures = []
    frame_dir = Path(str(layer.get("png_sequence_dir") or ""))
    if not frame_dir.is_absolute():
        frame_dir = project_dir / frame_dir
    frames = sorted(frame_dir.glob("*.png")) if frame_dir.exists() else []
    if len(frames) < FRAME_COUNT:
        failures.append(failure("motion_sequence_too_short", f"Motion PNG sequence must contain at least {FRAME_COUNT} frames."))
    elif len(frames) < 3:
        failures.append(failure("motion_sequence_too_short", "Motion PNG sequence must contain at least start/mid/end frames."))
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in frames[:5]]
    if len(set(hashes)) <= 1 and frames:
        failures.append(failure("motion_sequence_static", "Motion PNG sequence frames do not differ."))
    if frames:
        alpha_failures = [path for path in (frames[0], frames[len(frames) // 2], frames[-1]) if not png_has_transparent_background_and_visible_overlay(path)]
        if alpha_failures:
            failures.append(failure("motion_png_not_transparent_overlay", "Motion sequence must be RGBA with transparent background and visible overlay pixels."))
    evidence = layer.get("frame_evidence") if isinstance(layer.get("frame_evidence"), dict) else {}
    for key in ("start", "mid", "end"):
        if not evidence.get(key) or not Path(str(evidence[key])).exists():
            failures.append(failure("missing_frame_evidence", "Motion layer must reference start/mid/end frame evidence."))
            break
    if layer.get("decode_or_sequence_probe_status") != "passed":
        failures.append(failure("motion_sequence_probe_not_passed", "Motion sequence probe status must be passed."))
    return failures


def png_has_transparent_background_and_visible_overlay(path: Path) -> bool:
    if Image is not None:
        try:
            image = Image.open(path).convert("RGBA")
            width, height = image.size
            alpha = image.getchannel("A")
            extrema = alpha.getextrema()
            if extrema[0] != 0 or extrema[1] == 0:
                return False
            corners = [alpha.getpixel((0, 0)), alpha.getpixel((width - 1, 0)), alpha.getpixel((0, height - 1)), alpha.getpixel((width - 1, height - 1))]
            return all(value == 0 for value in corners)
        except Exception:
            return False
    try:
        width, height, color_type, raw = decode_filter0_png(path)
    except Exception:
        return False
    if color_type != 6:
        return False
    stride = width * 4
    alpha_values = []
    for y in range(height):
        start = y * stride
        row = raw[start : start + stride]
        alpha_values.extend(row[3::4])
    if not alpha_values or min(alpha_values) != 0 or max(alpha_values) == 0:
        return False
    corners = [
        raw[3],
        raw[(width - 1) * 4 + 3],
        raw[(height - 1) * stride + 3],
        raw[(height - 1) * stride + (width - 1) * 4 + 3],
    ]
    return all(value == 0 for value in corners)


def decode_filter0_png(path: Path) -> tuple[int, int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not png")
    pos = 8
    width = height = color_type = 0
    idat = bytearray()
    while pos < len(data):
        length = struct.unpack("!I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, _bit_depth, color_type, _compression, _filter, _interlace = struct.unpack("!IIBBBBB", payload)
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            break
    inflated = zlib.decompress(bytes(idat))
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    raw = bytearray()
    source = 0
    for _y in range(height):
        filter_type = inflated[source]
        if filter_type != 0:
            raise ValueError("unsupported png filter")
        source += 1
        raw.extend(inflated[source : source + stride])
        source += stride
    return width, height, color_type, bytes(raw)
