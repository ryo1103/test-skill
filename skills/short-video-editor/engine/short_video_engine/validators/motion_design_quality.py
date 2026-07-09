from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import read_json
from ..motion_director import PROFESSIONAL_TEMPLATES
from ..paths import plan_dir
from ..stage_result import failure


EVIDENCE_STAGES = ("start", "build", "peak", "settle", "end")


def validate_motion_design_quality(project_dir: Path, *, strict: bool = True, allow_pillow_professional: bool = False) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    plan_payload = read_json(plan_dir(project_dir) / "graphic_scene_plan.json", {})
    layers_payload = read_json(plan_dir(project_dir) / "motion_layers.json", {})
    scenes = plan_payload.get("scenes") if isinstance(plan_payload, dict) else []
    layers = layers_payload.get("layers") if isinstance(layers_payload, dict) else []
    if not isinstance(scenes, list) or not scenes:
        failures.append(failure("missing_graphic_scene_plan", "S5 strict PASS requires work/plan/graphic_scene_plan.json with at least one graphic scene."))
        return failures
    if plan_payload.get("motion_design_preset_applied") is not True:
        failures.append(failure("motion_design_preset_not_applied", "graphic_scene_plan must declare motion_design_preset_applied=true."))
    scene_by_id = {str(scene.get("scene_id") or ""): scene for scene in scenes if isinstance(scene, dict)}
    for scene in scenes:
        if isinstance(scene, dict):
            failures.extend(validate_scene(scene))
    if not isinstance(layers, list):
        failures.append(failure("invalid_motion_layers_json", "motion_layers.json must contain a layers array."))
        return failures
    for layer in layers:
        if isinstance(layer, dict):
            scene = scene_by_id.get(str(layer.get("graphic_scene_id") or ""))
            failures.extend(validate_layer_quality(layer, scene, strict=strict, allow_pillow_professional=allow_pillow_professional))
    return failures


def validate_scene(scene: dict[str, Any]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    template = str(scene.get("scene_template") or "")
    if not template:
        failures.append(failure("missing_scene_template", "Every required logic motion scene must declare scene_template."))
    elif template not in PROFESSIONAL_TEMPLATES:
        failures.append(failure("unsupported_professional_scene_template", f"{template} is not in the allowed professional template list."))
    if not str(scene.get("background_treatment") or "").strip():
        failures.append(failure("missing_background_treatment", "Graphic scene must declare a non-empty background_treatment."))
    sequence = scene.get("animation_sequence") if isinstance(scene.get("animation_sequence"), list) else []
    if len(sequence) < 4:
        failures.append(failure("motion_animation_sequence_too_short", "Graphic scene animation_sequence must contain at least four stages."))
    if not any(float_or_zero(stage.get("stagger_sec")) > 0 for stage in sequence if isinstance(stage, dict)):
        failures.append(failure("missing_motion_stagger", "Graphic scene animation_sequence must use stagger_sec > 0."))
    target = scene.get("quality_target") if isinstance(scene.get("quality_target"), dict) else {}
    if target.get("no_large_empty_panel") is not True:
        failures.append(failure("large_empty_panel_detected", "Graphic scene must prove no_large_empty_panel=true."))
    if target.get("no_title_subtitle_overlap") is not True:
        failures.append(failure("title_subtitle_overlap_risk", "Graphic scene must prove no_title_subtitle_overlap=true."))
    if str(scene.get("logic_relation") or "") == "final_summary" and str(scene.get("intensity") or "") == "high":
        failures.append(failure("final_summary_high_intensity_motion", "Final summary scenes cannot use high intensity motion."))
    inventory = scene.get("component_inventory") if isinstance(scene.get("component_inventory"), dict) else {}
    if not component_requirement_met(inventory, scene):
        failures.append(failure("insufficient_professional_components", "Each professional scene needs a panel plus two of icon/node/connector/metric."))
    return failures


def validate_layer_quality(layer: dict[str, Any], scene: dict[str, Any] | None, *, strict: bool, allow_pillow_professional: bool) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    backend = str(layer.get("renderer_backend") or "")
    if strict and backend == "pillow_sequence" and not allow_pillow_professional:
        failures.append(failure("motion_professional_renderer_required", "Strict professional PASS cannot use pillow_sequence as the renderer backend."))
    if backend in {"motion_canvas_source", "remotion_source"}:
        failures.append(failure("motion_source_only_not_evidence", "Motion source files are handoff only and cannot satisfy professional PASS."))
    if layer.get("motion_design_preset_applied") is not True:
        failures.append(failure("motion_design_preset_not_applied", "Motion layer must declare motion_design_preset_applied=true."))
    if strict and layer.get("professional_quality_status") != "passed":
        failures.append(failure("motion_professional_quality_not_passed", "Motion layer must declare professional_quality_status=passed in strict mode."))
    evidence = layer.get("frame_evidence") if isinstance(layer.get("frame_evidence"), dict) else {}
    for key in EVIDENCE_STAGES:
        value = evidence.get(key)
        if not value or not Path(str(value)).exists():
            failures.append(failure("missing_professional_frame_evidence", "Professional motion evidence must include start/build/peak/settle/end rendered frames."))
            break
    if scene is None:
        failures.append(failure("motion_layer_missing_graphic_scene", "Motion layer must reference a graphic_scene_id from graphic_scene_plan.json."))
    return failures


def component_requirement_met(inventory: dict[str, Any], scene: dict[str, Any]) -> bool:
    if inventory:
        has_panel = inventory.get("panel") is True
        secondary_count = sum(1 for key in ("icon", "node", "connector", "metric") if inventory.get(key) is True)
        return has_panel and secondary_count >= 2
    has_panel = True
    secondary_count = 0
    if scene.get("nodes"):
        secondary_count += 1
    if scene.get("metrics"):
        secondary_count += 1
    if scene.get("connectors"):
        secondary_count += 1
    return has_panel and secondary_count >= 2


def float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
