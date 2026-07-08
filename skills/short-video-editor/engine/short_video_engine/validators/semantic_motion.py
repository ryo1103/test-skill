from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import load_contract, read_json
from ..paths import plan_dir
from ..stage_result import failure


def validate_semantic_motion(project_dir: Path) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    index_payload = read_json(plan_dir(project_dir) / "required_motion_index.json", {})
    assertions_payload = read_json(plan_dir(project_dir) / "motion_assertions.json", {})
    layers_payload = read_json(plan_dir(project_dir) / "motion_layers.json", {})
    contract = load_contract("semantic_motion_contract.json")
    actions = contract.get("semantic_actions") if isinstance(contract.get("semantic_actions"), dict) else {}
    required = index_payload.get("required_motions") if isinstance(index_payload, dict) else None
    if required is None:
        return [failure("required_motion_index_missing", "S5 strict validation requires work/plan/required_motion_index.json.")]
    if not isinstance(required, list):
        return [failure("required_motion_index_missing", "required_motion_index.json must contain required_motions array.")]
    layers = layers_payload.get("layers") if isinstance(layers_payload, dict) else []
    if not isinstance(layers, list):
        layers = []
    assertions = assertions_payload.get("assertions") if isinstance(assertions_payload, dict) else []
    if not isinstance(assertions, list):
        assertions = []
    assertion_by_id = {str(item.get("motion_assertion_id") or ""): item for item in assertions if isinstance(item, dict)}
    assertion_by_motion = {str(item.get("motion_id") or ""): item for item in assertions if isinstance(item, dict)}
    layer_by_motion: dict[str, list[dict[str, Any]]] = {}
    for layer in layers:
        if isinstance(layer, dict):
            layer_by_motion.setdefault(str(layer.get("motion_id") or ""), []).append(layer)
    for item in required:
        if not isinstance(item, dict) or item.get("motion_required") is not True:
            continue
        motion_id = str(item.get("motion_id") or "")
        if motion_id not in assertion_by_motion:
            failures.append(failure("fallback_assertion_missing", f"{motion_id} has no semantic fallback assertion."))
        motion_layers = layer_by_motion.get(motion_id, [])
        if not motion_layers:
            failures.append(failure("required_motion_missing", f"{motion_id} from required_motion_index has no motion layer."))
            failures.append(failure("required_motion_deleted_or_downgraded", f"{motion_id} appears to have been deleted or downgraded after the S2 required motion lock."))
            continue
        for layer in motion_layers:
            failures.extend(validate_semantic_layer(layer, assertion_by_id, actions))
    required_ids = {str(item.get("motion_id") or "") for item in required if isinstance(item, dict) and item.get("motion_required") is True}
    for motion_id in required_ids:
        if not motion_id:
            continue
        if motion_id not in layer_by_motion:
            failures.append(failure("required_motion_not_referenced_by_layer", f"{motion_id} is not referenced by any rendered layer."))
    if failures and not any(item.get("code") == "motion_rerender_required" for item in failures):
        failures.append(failure("motion_rerender_required", "Semantic motion validation failed; regenerate assertion/template/render artifacts instead of deleting required motion."))
    return failures


def validate_semantic_layer(layer: dict[str, Any], assertion_by_id: dict[str, dict[str, Any]], actions: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    assertion_id = str(layer.get("motion_assertion_id") or "")
    if not assertion_id:
        return [failure("motion_assertion_missing", "Every required motion layer must reference motion_assertion_id.")]
    assertion = assertion_by_id.get(assertion_id)
    if not assertion:
        return [failure("motion_assertion_missing", f"motion_assertion_id {assertion_id} was not found in motion_assertions.json.")]
    semantic_action = str(layer.get("semantic_action") or assertion.get("semantic_action") or "")
    action_contract = actions.get(semantic_action)
    if not isinstance(action_contract, dict):
        failures.append(failure("motion_semantic_invalid", f"Unsupported semantic_action {semantic_action}."))
        return failures
    slots = layer.get("slots") if isinstance(layer.get("slots"), dict) else assertion.get("slots") if isinstance(assertion.get("slots"), dict) else {}
    missing_slots = [slot for slot in action_contract.get("required_slots", []) if not str(slots.get(slot) or "").strip()]
    if missing_slots:
        failures.append(failure("motion_slots_missing", f"{assertion_id} missing slots: {', '.join(missing_slots)}."))
    required_actions = [str(item) for item in action_contract.get("required_visual_actions", []) if str(item).strip()]
    assertion_actions = [str(item) for item in assertion.get("required_visual_actions", []) if str(item).strip()]
    layer_actions = [str(item) for item in layer.get("required_visual_actions", []) if str(item).strip()]
    animation_stages = [str(item) for item in layer.get("animation_stages", []) if str(item).strip()]
    for action in required_actions:
        if action not in assertion_actions or action not in layer_actions or action not in animation_stages:
            failures.append(failure("motion_visual_action_missing", f"{assertion_id} does not execute required visual action {action}."))
    if not is_rendered(layer):
        failures.append(failure("required_motion_not_rendered", f"{assertion_id} does not reference a rendered motion artifact."))
    proof = layer.get("semantic_visual_proof") if isinstance(layer.get("semantic_visual_proof"), dict) else {}
    if proof.get("non_decorative_scene") is not True:
        failures.append(failure("decorative_hud_no_semantic_action", f"{assertion_id} lacks non-decorative semantic visual proof."))
    if proof.get("has_relationship_flow") is not True:
        failures.append(failure("labels_float_without_relationship", f"{assertion_id} lacks relationship flow; labels cannot float without structure."))
    failures.extend(action_specific_failures(assertion_id, semantic_action, proof))
    return failures


def action_specific_failures(assertion_id: str, semantic_action: str, proof: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    if semantic_action == "negate_and_redefine" and (proof.get("has_rejection") is not True or proof.get("has_connection_flow") is not True):
        failures.append(failure("negation_scene_missing_rejection", f"{assertion_id} must visually reject both rejected states and reveal the accepted connector."))
    if semantic_action == "connector_metaphor" and proof.get("has_connection_flow") is not True:
        failures.append(failure("connector_scene_missing_flow", f"{assertion_id} connector metaphor must show input -> connector -> output flow."))
    if semantic_action == "metric_growth" and proof.get("has_metric_delta") is not True:
        failures.append(failure("metric_scene_missing_delta", f"{assertion_id} metric motion must show growth/delta."))
    if semantic_action == "process_migration" and proof.get("has_transition") is not True:
        failures.append(failure("process_scene_missing_transition", f"{assertion_id} process motion must show transition."))
    if semantic_action == "density_comparison" and (proof.get("has_pressure") is not True or proof.get("has_expansion") is not True):
        failures.append(failure("density_scene_missing_pressure_or_expansion", f"{assertion_id} density comparison must show pressure and expansion."))
    if semantic_action in {"before_after_change", "density_comparison"} and proof.get("has_comparison_axis") is not True:
        failures.append(failure("comparison_scene_missing_axis", f"{assertion_id} comparison motion must show an axis or before/after separation."))
    return failures


def is_rendered(layer: dict[str, Any]) -> bool:
    backend = str(layer.get("renderer_backend") or "")
    evidence = layer.get("frame_evidence") if isinstance(layer.get("frame_evidence"), dict) else {}
    return backend in {"motion_canvas_sequence", "motion_canvas_video", "pillow_sequence"} and bool(evidence)
