from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import load_contract, read_json, write_json
from ..paths import plan_dir
from ..stage_result import current_command, failure
from ..producers.motion_renderer.registry import SEMANTIC_TEMPLATE_BY_ACTION


EN_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9._+/#-]*")


def build_required_motion_index(project_dir: Path, *, overwrite: bool = False) -> tuple[Path, dict[str, Any], list[dict[str, str]]]:
    path = plan_dir(project_dir) / "required_motion_index.json"
    if path.exists() and not overwrite:
        payload = read_json(path, {})
        return path, payload if isinstance(payload, dict) else {}, []
    shot_plan = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    shots = shot_plan.get("shots") if isinstance(shot_plan, dict) else []
    if not isinstance(shots, list):
        return path, {}, [failure("invalid_shot_plan_json", "shot_plan.json must contain a shots array before required motion can be locked.")]
    required = []
    for index, shot in enumerate([item for item in shots if isinstance(item, dict) and item.get("motion_overlay_required")], start=1):
        required.append(
            {
                "motion_id": f"motion_{index:03d}",
                "shot_id": str(shot.get("shot_id") or ""),
                "unit_id": str(shot.get("unit_id") or ""),
                "cue_ids": [str(item) for item in (shot.get("subtitle_cue_ids") or []) if str(item).strip()],
                "start_sec": float_or_zero(shot.get("start")),
                "end_sec": float_or_zero(shot.get("end")),
                "source_text": str(shot.get("script_fragment") or ""),
                "motion_required": True,
                "requirement_reason": requirement_reason(shot),
            }
        )
    payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "stage": "S2_visual_plan",
        "compiler": "motion_assertion_compiler.build_required_motion_index",
        "command": " ".join(current_command()),
        "source_artifact": "work/plan/shot_plan.json",
        "required_motions": required,
    }
    write_json(path, payload)
    return path, payload, []


def compile_motion_assertions(project_dir: Path) -> tuple[Path, dict[str, Any], list[dict[str, str]]]:
    index_payload = read_json(plan_dir(project_dir) / "required_motion_index.json", {})
    contract = load_contract("semantic_motion_contract.json")
    icon_contract = load_contract("motion_icon_map.json")
    actions = contract.get("semantic_actions") if isinstance(contract.get("semantic_actions"), dict) else {}
    semantic_icon_map = icon_contract.get("semantic_icon_map") if isinstance(icon_contract.get("semantic_icon_map"), dict) else {}
    required = index_payload.get("required_motions") if isinstance(index_payload, dict) else []
    if not isinstance(required, list):
        required = []
    shot_plan = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    shots = shot_plan.get("shots") if isinstance(shot_plan, dict) else []
    shots_by_id = {str(shot.get("shot_id") or ""): shot for shot in shots if isinstance(shot, dict)}
    assertions = []
    failures: list[dict[str, str]] = []
    for index, item in enumerate([entry for entry in required if isinstance(entry, dict)], start=1):
        shot = shots_by_id.get(str(item.get("shot_id") or ""), {})
        assertion = compile_assertion(item, shot, actions, semantic_icon_map, index)
        assertions.append(assertion)
        missing_slots = [slot for slot in actions.get(assertion["semantic_action"], {}).get("required_slots", []) if not slot_text(assertion["slots"].get(slot))]
        if missing_slots:
            failures.append(failure("motion_slots_missing", f"{assertion['motion_assertion_id']} missing slots: {', '.join(missing_slots)}."))
        missing_actions = [action for action in actions.get(assertion["semantic_action"], {}).get("required_visual_actions", []) if action not in assertion["required_visual_actions"]]
        if missing_actions:
            failures.append(failure("motion_visual_action_missing", f"{assertion['motion_assertion_id']} missing visual actions: {', '.join(missing_actions)}."))
    payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "contract": contract.get("contract_id", "semantic_motion_contract_v1"),
        "command": " ".join(current_command()),
        "assertions": assertions,
        "failure_codes": [item["code"] for item in failures],
        "failures": failures,
    }
    path = plan_dir(project_dir) / "motion_assertions.json"
    write_json(path, payload)
    return path, payload, failures


def compile_assertion(required_motion: dict[str, Any], shot: dict[str, Any], actions: dict[str, Any], semantic_icon_map: dict[str, Any], index: int) -> dict[str, Any]:
    text = str(required_motion.get("source_text") or shot.get("script_fragment") or "")
    entities = [str(item) for item in (shot.get("required_entities") or []) if str(item).strip()]
    semantic_action, source = infer_semantic_action(text)
    action_contract = actions.get(semantic_action, {})
    raw_slots = fill_slots(semantic_action, text, entities)
    slots = enrich_slots_with_icons(raw_slots, semantic_action, semantic_icon_map)
    required_visual_actions = [str(item) for item in (action_contract.get("required_visual_actions") or []) if str(item).strip()]
    return {
        "motion_assertion_id": f"ma_{index:03d}",
        "motion_id": str(required_motion.get("motion_id") or f"motion_{index:03d}"),
        "shot_id": str(required_motion.get("shot_id") or shot.get("shot_id") or ""),
        "cue_ids": [str(item) for item in (required_motion.get("cue_ids") or []) if str(item).strip()],
        "source_text": text,
        "semantic_action": semantic_action,
        "claim": claim_for(semantic_action, slots),
        "slots": slots,
        "required_visual_actions": required_visual_actions,
        "recommended_template": SEMANTIC_TEMPLATE_BY_ACTION.get(semantic_action) or action_contract.get("recommended_template") or "concept_definition_scene",
        "assertion_source": source,
    }


def infer_semantic_action(text: str) -> tuple[str, str]:
    if re.search(r"不是|也不是|而是", text):
        return "negate_and_redefine", "fallback_ladder:not_but"
    if re.search(r"理解成|连接器|输入|输出|节点|链路|光纤", text):
        return "connector_metaphor", "fallback_ladder:connector"
    if re.search(r"规模|增加|下降|成本|效率|指标|%|倍|增长|变大", text):
        return "metric_growth", "fallback_ladder:metric"
    if re.search(r"流程|步骤|人工对准|晶圆制造|一次做好|第一|第二|第三|迁移", text):
        return "process_migration", "fallback_ladder:process"
    if re.search(r"下一代|高密度|瓶颈|面向|更高|扩展", text):
        return "density_comparison", "fallback_ladder:density"
    if re.search(r"因为|导致|所以|结果|原因", text):
        return "cause_to_result", "fallback_ladder:cause"
    if re.search(r"之前|之后|过去|现在|新方案|旧方案|以前", text):
        return "before_after_change", "fallback_ladder:before_after"
    return "concept_definition", "fallback_ladder:concept"


def fill_slots(action: str, text: str, entities: list[str]) -> dict[str, str]:
    subject = infer_subject(text, entities)
    if action == "negate_and_redefine":
        rejected_a, rejected_b, accepted = parse_negation_slots(text)
        return {
            "subject": subject,
            "rejected_a": rejected_a or "芯片",
            "rejected_b": rejected_b or "光模块",
            "accepted_definition": accepted or "光纤连接器",
        }
    if action == "connector_metaphor":
        return {"input": infer_keyword(text, ["输入", "光纤", "上游"], "输入"), "connector": infer_keyword(text, ["光纤连接器", "连接器", "GlassBridge", "FAU"], subject or "连接器"), "output": infer_keyword(text, ["输出", "芯片", "下游"], "输出")}
    if action == "metric_growth":
        return {"metric": infer_keyword(text, ["连接规模", "规模", "成本", "效率", "指标"], "连接规模"), "baseline": infer_keyword(text, ["当前", "基准", "baseline"], "基准"), "target_or_delta": infer_keyword(text, ["快速增加", "增加", "增长", "下降", "更高", "倍"], "快速增加")}
    if action == "process_migration":
        return {"old_step": infer_keyword(text, ["人工对准", "旧流程", "传统流程", "之前"], "人工对准"), "new_step": infer_keyword(text, ["晶圆制造", "GlassBridge", "新流程", "现在"], "晶圆制造"), "result": infer_keyword(text, ["一次做好", "结果", "完成"], "一次做好")}
    if action == "density_comparison":
        return {"old_solution": infer_keyword(text, ["FAU", "旧方案", "传统方案"], "FAU"), "new_requirement": infer_keyword(text, ["下一代", "高密度", "更高密度", "更高"], "下一代高密度"), "new_solution": infer_keyword(text, ["GlassBridge", "新方案", "扩展"], subject or "GlassBridge")}
    if action == "cause_to_result":
        return {"cause": first_clause(text, "因为") or "原因", "mechanism": infer_keyword(text, ["导致", "所以", "机制"], "机制"), "result": last_clause(text) or "结果"}
    if action == "before_after_change":
        return {"before": infer_keyword(text, ["之前", "以前", "过去", "旧方案"], "之前"), "transition": infer_keyword(text, ["之后", "现在", "变化", "迁移"], "变化"), "after": infer_keyword(text, ["新方案", "现在", "之后", "GlassBridge"], "之后")}
    return {"subject": subject or "核心概念", "definition": infer_keyword(text, ["理解成", "定义", "就是"], "定义"), "role": infer_keyword(text, ["作用", "角色", "连接", "机制"], "连接作用")}


def parse_negation_slots(text: str) -> tuple[str, str, str]:
    rejected_a = ""
    rejected_b = ""
    accepted = ""
    match = re.search(r"不是(?P<a>.+?)(?:也不是|不是)(?P<b>.+?)(?:而是|你可以把它理解成|把它理解成)(?P<c>.+?)(?:[，。！？；,.!?;]|$)", text)
    if match:
        rejected_a = short_slot(match.group("a"))
        rejected_b = short_slot(match.group("b"))
        accepted = short_slot(match.group("c"))
    else:
        a_match = re.search(r"不是(?P<a>.+?)(?:[，,]|也不是|而是)", text)
        b_match = re.search(r"也不是(?P<b>.+?)(?:[，,]|而是)", text)
        c_match = re.search(r"(?:而是|理解成)(?P<c>.+?)(?:[，。！？；,.!?;]|$)", text)
        rejected_a = short_slot(a_match.group("a")) if a_match else ""
        rejected_b = short_slot(b_match.group("b")) if b_match else ""
        accepted = short_slot(c_match.group("c")) if c_match else ""
    if "芯片" in text and not rejected_a:
        rejected_a = "芯片"
    if "光模块" in text and not rejected_b:
        rejected_b = "光模块"
    if "光纤连接器" in text and not accepted:
        accepted = "光纤连接器"
    return rejected_a, rejected_b, accepted


def infer_subject(text: str, entities: list[str]) -> str:
    for entity in entities:
        if entity:
            return short_slot(entity)
    for preferred in ("GlassBridge", "FAU"):
        if preferred in text:
            return preferred
    match = EN_TERM_RE.search(text)
    if match:
        return short_slot(match.group(0))
    return "GlassBridge" if "光" in text else "核心概念"


def infer_keyword(text: str, candidates: list[str], fallback: str) -> str:
    for item in candidates:
        if item and item in text:
            return short_slot(item)
    return short_slot(fallback)


def requirement_reason(shot: dict[str, Any]) -> str:
    reason = shot.get("logic_relation_reason")
    if isinstance(reason, dict):
        return str(reason.get("matched_text") or reason.get("source") or "logic_relation_requires_visual_explanation")
    return "logic_relation_requires_visual_explanation"


def enrich_slots_with_icons(slots: dict[str, str], action: str, semantic_icon_map: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        key: {
            "text": value,
            "semantic_icon": semantic_icon_for(key, value, action, semantic_icon_map),
        }
        for key, value in slots.items()
    }


def semantic_icon_for(slot_name: str, text: str, action: str, semantic_icon_map: dict[str, Any]) -> str:
    lowered = str(text or "").lower()
    # Structural endpoint slots describe the role in the animation and take
    # precedence over nouns in their display labels (for example 光纤 as input).
    if slot_name == "input":
        return "input"
    if slot_name == "output":
        return "output"
    for key, config in semantic_icon_map.items():
        keywords = config.get("keywords") if isinstance(config, dict) else []
        for keyword in keywords if isinstance(keywords, list) else []:
            if str(keyword).lower() in lowered:
                return str(key)
    if slot_name in {"rejected_a"}:
        return "chip"
    if slot_name in {"rejected_b"}:
        return "optical_module"
    if slot_name in {"accepted_definition", "subject", "connector", "new_solution"} and action in {"negate_and_redefine", "connector_metaphor", "density_comparison"}:
        return "connector"
    if slot_name in {"old_solution", "before", "old_step"}:
        return "warning" if action in {"density_comparison", "process_migration"} else "node"
    if slot_name in {"new_requirement"}:
        return "warning"
    if any(term in lowered for term in ("hbm", "dram", "ssd", "内存", "存储")):
        return "memory"
    return "node"


def slot_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or "").strip()
    return str(value or "").strip()


def claim_for(action: str, slots: dict[str, Any]) -> str:
    if action == "negate_and_redefine":
        return f"{slot_text(slots.get('subject'))} 不是 {slot_text(slots.get('rejected_a'))} 或 {slot_text(slots.get('rejected_b'))}，而是 {slot_text(slots.get('accepted_definition'))}"
    if action == "connector_metaphor":
        return f"{slot_text(slots.get('input'))} 通过 {slot_text(slots.get('connector'))} 连接到 {slot_text(slots.get('output'))}"
    if action == "metric_growth":
        return f"{slot_text(slots.get('metric'))} 从 {slot_text(slots.get('baseline'))} 到 {slot_text(slots.get('target_or_delta'))}"
    if action == "process_migration":
        return f"{slot_text(slots.get('old_step'))} 迁移到 {slot_text(slots.get('new_step'))}，形成 {slot_text(slots.get('result'))}"
    if action == "density_comparison":
        return f"{slot_text(slots.get('old_solution'))} 面对 {slot_text(slots.get('new_requirement'))}，需要 {slot_text(slots.get('new_solution'))}"
    return "脚本逻辑需要可视化解释"


def first_clause(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return short_slot(text.split(marker, 1)[-1].split("，", 1)[0])


def last_clause(text: str) -> str:
    parts = [part for part in re.split(r"[，。！？；,.!?;]", text) if part.strip()]
    return short_slot(parts[-1]) if parts else ""


def short_slot(value: str) -> str:
    compact = re.sub(r"\s+", "", str(value or ""))
    compact = re.sub(r"^(一颗|一个|一种|新的|这个|那个|它|是|的|叫)", "", compact)
    compact = re.sub(r"[，。！？；：、,.!?;:\"'“”‘’（）()【】\[\]《》<>]", "", compact)
    return compact[:16] or "未命名"


def float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
