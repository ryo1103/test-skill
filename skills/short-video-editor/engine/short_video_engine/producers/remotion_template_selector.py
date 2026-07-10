from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import load_contract, read_json, write_json
from ..paths import plan_dir
from ..stage_result import current_command, failure


STYLE = "tech_hud_glass"


def select_remotion_templates(project_dir: Path) -> tuple[Path, dict[str, Any], list[dict[str, str]]]:
    assertions_payload = read_json(plan_dir(project_dir) / "motion_assertions.json", {})
    graphic_plan = read_json(plan_dir(project_dir) / "graphic_scene_plan.json", {})
    icon_manifest = read_json(plan_dir(project_dir) / "motion_icon_manifest.json", {})
    required_index = read_json(plan_dir(project_dir) / "required_motion_index.json", {})
    intervals_by_motion = {str(item.get("motion_id") or ""): item for item in (required_index.get("required_motions") or []) if isinstance(item, dict)}
    registry = load_contract("remotion_template_registry.json")
    assertions = assertions_payload.get("assertions") if isinstance(assertions_payload, dict) else []
    scenes = graphic_plan.get("scenes") if isinstance(graphic_plan, dict) else []
    scene_by_motion = scene_index_by_motion(scenes if isinstance(scenes, list) else [])
    external_payload = load_external_selector_payload()
    selector = "llm_or_deterministic" if external_payload else "deterministic"
    decisions = []
    for assertion in assertions if isinstance(assertions, list) else []:
        if not isinstance(assertion, dict):
            continue
        llm_decision = decision_from_external(external_payload, assertion) if external_payload else None
        decision = llm_decision or deterministic_decision(assertion, scene_by_motion.get(str(assertion.get("motion_id") or "")), registry)
        interval = intervals_by_motion.get(str(assertion.get("motion_id") or ""), {})
        duration_sec = max(0.8, float(interval.get("end_sec") or 0) - float(interval.get("start_sec") or 0))
        decision.setdefault("input_props", {})["durationInFrames"] = round(duration_sec * 30)
        decision["input_props"]["fps"] = 30
        enrich_decision_with_icons(project_dir, decision, assertion, icon_manifest)
        decisions.append(decision)
    payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "selector": selector,
        "command": " ".join(current_command()),
        "decisions": decisions,
    }
    path = plan_dir(project_dir) / "remotion_template_decisions.json"
    write_json(path, payload)
    failures = validate_remotion_template_decisions(project_dir, payload, registry)
    return path, payload, failures


def scene_index_by_motion(scenes: list[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        motion_id = str(scene.get("motion_id") or "")
        if not motion_id:
            logic_segment_id = str(scene.get("logic_segment_id") or "")
            parts = logic_segment_id.split("_")
            if len(parts) >= 2 and parts[1].isdigit():
                motion_id = f"motion_{int(parts[1]):03d}"
        if motion_id:
            result[motion_id] = scene
    return result


def load_external_selector_payload() -> dict[str, Any] | None:
    raw = os.environ.get("SVIDEO_REMOTION_SELECTOR_JSON")
    if not raw:
        return None
    try:
        path = Path(raw)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def decision_from_external(payload: dict[str, Any] | None, assertion: dict[str, Any]) -> dict[str, Any] | None:
    if not payload:
        return None
    decisions = payload.get("decisions") if isinstance(payload.get("decisions"), list) else []
    motion_id = str(assertion.get("motion_id") or "")
    for item in decisions:
        if isinstance(item, dict) and str(item.get("motion_id") or "") == motion_id:
            return {
                "motion_id": motion_id,
                "motion_assertion_id": assertion.get("motion_assertion_id"),
                "semantic_action": assertion.get("semantic_action"),
                "selected_template": item.get("selected_template"),
                "selection_reason": str(item.get("selection_reason") or "llm_registry_selection"),
                "input_props": item.get("input_props") if isinstance(item.get("input_props"), dict) else {},
            }
    return None


def deterministic_decision(assertion: dict[str, Any], scene: dict[str, Any] | None, registry: dict[str, Any]) -> dict[str, Any]:
    action = str(assertion.get("semantic_action") or "")
    mapping = registry.get("deterministic_mapping") if isinstance(registry.get("deterministic_mapping"), dict) else {}
    template_id = str(mapping.get(action) or "concept_definition")
    slots = assertion.get("slots") if isinstance(assertion.get("slots"), dict) else {}
    input_props = props_for_action(action, slots, assertion, scene or {})
    return {
        "motion_id": assertion.get("motion_id"),
        "motion_assertion_id": assertion.get("motion_assertion_id"),
        "semantic_action": action,
        "selected_template": template_id,
        "selection_reason": "deterministic_registry_mapping",
        "input_props": input_props, "selected_layout_variant": "semantic_svg_overlay", "icon_selection_reason": "manifest_localized_svg_slots",
    }


def props_for_action(action: str, slots: dict[str, Any], assertion: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = {
        "semanticAction": action,
        "claim": assertion.get("claim") or scene.get("primary_title") or "",
        "durationInFrames": 72, "fps": 30,
        "style": STYLE,
        "icons": {},
        "labels": [slot_text(value) for value in slots.values() if slot_text(value)],
    }
    for key, value in slots.items():
        props[camel_case(key)] = slot_text(value)
        if isinstance(value, dict) and value.get("semantic_icon"):
            props["icons"][key] = value.get("semantic_icon")
    if action == "negate_and_redefine":
        props.update(
            {
                "subject": slot_text(slots.get("subject")),
                "rejectedA": slot_text(slots.get("rejected_a")),
                "rejectedB": slot_text(slots.get("rejected_b")),
                "acceptedDefinition": slot_text(slots.get("accepted_definition")),
            }
        )
    elif action == "connector_metaphor":
        props.update({"input": slot_text(slots.get("input")), "connector": slot_text(slots.get("connector")), "output": slot_text(slots.get("output"))})
    elif action == "metric_growth":
        props.update({"metric": slot_text(slots.get("metric")), "baseline": slot_text(slots.get("baseline")), "targetOrDelta": slot_text(slots.get("target_or_delta"))})
    elif action == "process_migration":
        props.update({"oldStep": slot_text(slots.get("old_step")), "newStep": slot_text(slots.get("new_step")), "result": slot_text(slots.get("result"))})
    elif action == "density_comparison":
        props.update({"oldSolution": slot_text(slots.get("old_solution")), "newRequirement": slot_text(slots.get("new_requirement")), "newSolution": slot_text(slots.get("new_solution"))})
    elif action == "before_after_change":
        props.update({"oldStep": slot_text(slots.get("before")), "newStep": slot_text(slots.get("after")), "result": slot_text(slots.get("transition"))})
    elif action == "cause_to_result":
        props.update({"input": slot_text(slots.get("cause")), "connector": slot_text(slots.get("mechanism")), "output": slot_text(slots.get("result"))})
    else:
        props.update({"subject": slot_text(slots.get("subject")), "definition": slot_text(slots.get("definition")), "role": slot_text(slots.get("role"))})
    return props


def enrich_decision_with_icons(project_dir: Path, decision: dict[str, Any], assertion: dict[str, Any], manifest: dict[str, Any]) -> None:
    props = decision.setdefault("input_props", {})
    by_assertion = manifest.get("icons_by_assertion") if isinstance(manifest, dict) else {}
    slots = by_assertion.get(str(assertion.get("motion_assertion_id") or ""), {}) if isinstance(by_assertion, dict) else {}
    props["icons"] = {
        str(slot): {"semanticKey": value.get("semantic_key"), "src": value.get("public_path"), "colorToken": "danger" if str(slot).startswith("rejected") else "accentSecondary"}
        for slot, value in slots.items() if isinstance(value, dict)
    }
    props["scene"] = {"nodes": [{"id": str(slot), "label": slot_text((assertion.get("slots") or {}).get(slot)), "iconSlot": str(slot)} for slot in slots], "metrics": [], "connectors": [], "intensity": "normal"}
    props["styleTokens"] = {"accentPrimary": "#65e7ff", "accentSecondary": "#72ebcb", "danger": "#ff5c7a", "textPrimary": "#ffffff", "textSecondary": "#bde6ff", "panel": "rgba(2,13,22,0.68)", "panelEdge": "#65e7ff", "fontFamily": "PingFang SC, Arial, sans-serif"}
    frames = int(props.get("durationInFrames") or 72)
    props["timing"] = {"enterEnd": round(frames * .18), "buildEnd": round(frames * .52), "emphasisEnd": round(frames * .70), "holdEnd": round(frames * .90)}
    decision["icon_coverage"] = sorted(slots)
    decision["unresolved_icon_slots"] = [str(key) for key in (assertion.get("slots") or {}) if str(key) not in slots]


def validate_remotion_template_decisions(project_dir: Path, payload: dict[str, Any], registry: dict[str, Any] | None = None) -> list[dict[str, str]]:
    registry = registry or load_contract("remotion_template_registry.json")
    semantic_contract = load_contract("semantic_motion_contract.json")
    semantic_actions = semantic_contract.get("semantic_actions") if isinstance(semantic_contract.get("semantic_actions"), dict) else {}
    index_payload = read_json(plan_dir(project_dir) / "required_motion_index.json", {})
    assertions_payload = read_json(plan_dir(project_dir) / "motion_assertions.json", {})
    required = index_payload.get("required_motions") if isinstance(index_payload, dict) else []
    assertions = assertions_payload.get("assertions") if isinstance(assertions_payload, dict) else []
    decisions = payload.get("decisions") if isinstance(payload, dict) else []
    if not isinstance(required, list) or not isinstance(assertions, list) or not isinstance(decisions, list):
        return [failure("invalid_remotion_template_decisions", "Remotion selector inputs and decisions must be arrays.")]
    templates = registry_templates(registry)
    decision_by_motion = {str(item.get("motion_id") or ""): item for item in decisions if isinstance(item, dict)}
    assertion_by_motion = {str(item.get("motion_id") or ""): item for item in assertions if isinstance(item, dict)}
    failures: list[dict[str, str]] = []
    for item in required:
        if not isinstance(item, dict) or item.get("motion_required") is not True:
            continue
        motion_id = str(item.get("motion_id") or "")
        decision = decision_by_motion.get(motion_id)
        assertion = assertion_by_motion.get(motion_id)
        if not decision:
            failures.append(failure("remotion_decision_missing_required_motion", f"{motion_id} has no Remotion template decision."))
            continue
        if not assertion:
            failures.append(failure("remotion_decision_missing_assertion", f"{motion_id} has no motion assertion for Remotion selection."))
            continue
        if decision.get("motion_assertion_id") != assertion.get("motion_assertion_id") or decision.get("semantic_action") != assertion.get("semantic_action"):
            failures.append(failure("remotion_decision_identity_mismatch", f"{motion_id} decision must preserve motion_assertion_id and semantic_action."))
        template_id = str(decision.get("selected_template") or "")
        template = templates.get(template_id)
        if not template:
            failures.append(failure("remotion_template_not_in_registry", f"{template_id} is not in remotion_template_registry.json."))
            continue
        action = str(assertion.get("semantic_action") or "")
        if action not in set(template.get("supports_semantic_actions") or []):
            failures.append(failure("remotion_template_action_unsupported", f"{template_id} does not support {action}."))
        input_props = decision.get("input_props") if isinstance(decision.get("input_props"), dict) else {}
        action_contract = semantic_actions.get(action) if isinstance(semantic_actions.get(action), dict) else {}
        missing = [slot for slot in action_contract.get("required_slots", []) if not prop_for_slot(input_props, slot)]
        if missing:
            failures.append(failure("remotion_input_props_missing_required_slot", f"{motion_id} input_props missing: {', '.join(missing)}."))
        if not str(decision.get("selection_reason") or "").strip():
            failures.append(failure("remotion_selection_reason_missing", f"{motion_id} decision must include selection_reason."))
    return failures


def registry_templates(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    templates = registry.get("templates") if isinstance(registry.get("templates"), list) else []
    return {str(item.get("template_id") or ""): item for item in templates if isinstance(item, dict)}


def prop_for_slot(props: dict[str, Any], slot: str) -> Any:
    return props.get(slot) or props.get(camel_case(slot)) or props.get(slot.replace("_", ""))


def slot_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or "").strip()
    return str(value or "").strip()


def camel_case(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])
