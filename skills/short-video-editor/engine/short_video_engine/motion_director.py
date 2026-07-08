from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import ENGINE_VERSION
from .contracts import load_contract, read_json, write_json
from .paths import plan_dir


PROFESSIONAL_TEMPLATES = {
    "chip_node_network",
    "tech_hud_concept_card",
    "kpi_dual_meter_panel",
    "process_milestone_rail",
    "comparison_split_glass",
    "not_x_but_y_pivot_panel",
    "system_error_terminal",
    "callout_lens_overlay",
}

TECH_RE = re.compile(r"GlassBridge|FAU|芯片|光纤|光互连|数据中心|算力|服务器|AI|晶圆|半导体", re.I)
ERROR_RE = re.compile(r"错误|失败|崩|卡住|阻塞|告警|风险|问题|不对|异常|error|fail", re.I)


def build_graphic_scene_plan(project_dir: Path, segments: list[dict[str, Any]]) -> tuple[Path, dict[str, Any]]:
    shot_plan = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    subtitle_layout = read_json(plan_dir(project_dir) / "subtitle_layout_cues.json", {})
    shots = shot_plan.get("shots") if isinstance(shot_plan, dict) else []
    shots_by_id = {str(shot.get("shot_id") or ""): shot for shot in shots if isinstance(shot, dict)}
    preset = load_contract("motion_design_preset.json")
    scenes = [scene_for_segment(segment, shots_by_id, subtitle_layout, preset, index) for index, segment in enumerate(segments, start=1)]
    payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "motion_design_preset": preset.get("preset_id", "tech_hud_graphic_package_v1"),
        "motion_design_preset_applied": True,
        "scenes": scenes,
    }
    path = plan_dir(project_dir) / "graphic_scene_plan.json"
    write_json(path, payload)
    return path, payload


def scene_for_segment(segment: dict[str, Any], shots_by_id: dict[str, dict[str, Any]], subtitle_layout: dict[str, Any], preset: dict[str, Any], index: int) -> dict[str, Any]:
    shot_id = str(segment.get("shot_id") or "")
    shot = shots_by_id.get(shot_id, {})
    script_fragment = "".join(str(shots_by_id.get(item, {}).get("script_fragment") or "") for item in segment.get("covered_shot_ids") or [shot_id])
    if not script_fragment:
        script_fragment = str(shot.get("script_fragment") or segment.get("visual_claim") or "")
    relation = str(segment.get("logic_relation") or shot.get("logic_relation") or "")
    wanted_visuals = " ".join(str(item) for item in (shot.get("wanted_visuals") or shot.get("required_entities") or segment.get("logic_entities") or []))
    template = select_scene_template(relation, script_fragment, wanted_visuals)
    labels = [str(item) for item in (segment.get("motion_text_items") or segment.get("logic_entities") or []) if str(item).strip()]
    labels = (labels + labels_for_template(template, relation))[:4]
    nodes = nodes_for_template(template, labels)
    metrics = metrics_for_template(template, segment, labels)
    connectors = connectors_for_template(template, nodes)
    primary_title = str(segment.get("visual_claim") or (labels[0] if labels else relation) or "逻辑关系")[:18]
    return {
        "scene_id": f"graphic_{index:03d}_{shot_id or 'scene'}",
        "shot_id": shot_id,
        "covered_shot_ids": segment.get("covered_shot_ids") or ([shot_id] if shot_id else []),
        "logic_segment_id": segment.get("logic_segment_id"),
        "logic_relation": relation,
        "script_fragment": script_fragment,
        "wanted_visuals": wanted_visuals,
        "subtitle_layout_cues": subtitle_summary(subtitle_layout, segment),
        "scene_template": template,
        "visual_metaphor": visual_metaphor_for(template, relation),
        "primary_title": primary_title,
        "secondary_labels": labels[:4],
        "nodes": nodes,
        "metrics": metrics,
        "connectors": connectors,
        "background_treatment": preset.get("background_treatment", {}).get("default") or "transparent_overlay_with_scan_grid_and_depth_scrim",
        "animation_sequence": animation_sequence(preset, template),
        "quality_target": {
            "professional_quality_status": "target",
            "motion_design_preset_applied": True,
            "no_large_empty_panel": True,
            "no_title_subtitle_overlap": True,
            "required_components": ["panel", "two_of_icon_node_connector_metric"],
        },
        "component_inventory": component_inventory(template, nodes, metrics, connectors),
        "intensity": "low" if relation == "final_summary" else ("high" if template == "system_error_terminal" else "medium"),
    }


def select_scene_template(relation: str, script_fragment: str, wanted_visuals: str) -> str:
    text = f"{script_fragment} {wanted_visuals}"
    if relation == "kpi_change":
        return "kpi_dual_meter_panel"
    if relation in {"process", "timeline"}:
        return "process_milestone_rail"
    if relation in {"comparison", "before_after"}:
        return "comparison_split_glass"
    if relation == "not_x_but_y":
        return "not_x_but_y_pivot_panel"
    if ERROR_RE.search(text):
        return "system_error_terminal"
    if relation in {"cause_effect", "structure"} or TECH_RE.search(text):
        return "chip_node_network"
    if "镜头" in text or "看" in text:
        return "callout_lens_overlay"
    return "tech_hud_concept_card"


def labels_for_template(template: str, relation: str) -> list[str]:
    if template == "chip_node_network":
        return ["输入", "节点", "连接", "输出"]
    if template == "system_error_terminal":
        return ["异常", "定位", "修正", "恢复"]
    if template == "process_milestone_rail":
        return ["阶段1", "阶段2", "阶段3", "完成"]
    if template == "kpi_dual_meter_panel":
        return ["基准", "变化"]
    if relation == "not_x_but_y":
        return ["旧判断", "转折", "新判断"]
    return ["概念", "机制", "结论"]


def nodes_for_template(template: str, labels: list[str]) -> list[dict[str, Any]]:
    labels = labels or labels_for_template(template, "")
    if template in {"chip_node_network", "process_milestone_rail"}:
        return [{"id": f"n{idx + 1}", "label": label, "role": "node"} for idx, label in enumerate(labels[:4])]
    if template in {"comparison_split_glass", "not_x_but_y_pivot_panel"}:
        return [{"id": "left", "label": labels[0], "role": "source"}, {"id": "right", "label": labels[-1], "role": "target"}]
    return [{"id": "core", "label": labels[0], "role": "focus"}, {"id": "support", "label": labels[min(1, len(labels) - 1)], "role": "support"}]


def metrics_for_template(template: str, segment: dict[str, Any], labels: list[str]) -> list[dict[str, Any]]:
    if template == "kpi_dual_meter_panel":
        return [
            {"id": "m1", "label": str(segment.get("metric") or labels[0] if labels else "指标"), "value": "baseline"},
            {"id": "m2", "label": str(segment.get("delta") or labels[-1] if labels else "变化"), "value": "delta"},
        ]
    if template == "system_error_terminal":
        return [{"id": "severity", "label": "风险", "value": "HIGH"}]
    return [{"id": "signal", "label": "强度", "value": "active"}]


def connectors_for_template(template: str, nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    if len(nodes) < 2:
        return []
    return [{"from": str(nodes[idx]["id"]), "to": str(nodes[idx + 1]["id"]), "style": "glow_data_line"} for idx in range(len(nodes) - 1)]


def visual_metaphor_for(template: str, relation: str) -> str:
    return {
        "chip_node_network": "chip-level node network showing signal routing",
        "tech_hud_concept_card": "editorial HUD concept card with active data edge",
        "kpi_dual_meter_panel": "dual meter panel comparing pressure and change",
        "process_milestone_rail": "milestone rail with staged activation",
        "comparison_split_glass": "split glass comparison board with center axis",
        "not_x_but_y_pivot_panel": "pivot panel rejecting X and activating Y",
        "system_error_terminal": "terminal alert resolving into corrected state",
        "callout_lens_overlay": "magnifying lens callout locking onto key detail",
    }.get(template, f"{relation or 'logic'} hud graphic")


def animation_sequence(preset: dict[str, Any], template: str) -> list[dict[str, Any]]:
    timing = preset.get("animation_timing") if isinstance(preset.get("animation_timing"), dict) else {}
    easing = str(timing.get("easing") or "cubic-bezier(0.16,1,0.3,1)")
    stagger = float(timing.get("stagger_sec") or 0.08)
    stages = ["start", "build", "peak", "settle", "end"]
    return [
        {"stage": stage, "duration_sec": duration, "easing": easing, "stagger_sec": stagger, "intent": intent_for_stage(stage, template)}
        for stage, duration in zip(stages, [0.18, 0.44, 0.46, 0.34, 0.18])
    ]


def intent_for_stage(stage: str, template: str) -> str:
    return {
        "start": "transparent pre-roll and scan grid lock",
        "build": f"{template} primary components enter with stagger",
        "peak": "connectors, node glow, or meter value reach readable emphasis",
        "settle": "reduce movement and hold the logic relation",
        "end": "fade nonessential highlights while preserving semantic read",
    }[stage]


def component_inventory(template: str, nodes: list[dict[str, Any]], metrics: list[dict[str, Any]], connectors: list[dict[str, Any]]) -> dict[str, bool]:
    return {
        "panel": True,
        "icon": template in PROFESSIONAL_TEMPLATES,
        "node": bool(nodes),
        "connector": bool(connectors),
        "metric": bool(metrics),
    }


def subtitle_summary(subtitle_layout: dict[str, Any], segment: dict[str, Any]) -> dict[str, Any]:
    cues = subtitle_layout.get("cues") if isinstance(subtitle_layout, dict) else []
    cues = cues if isinstance(cues, list) else []
    wanted = {str(item) for item in (segment.get("subtitle_cue_ids") or [])}
    matched = [cue for cue in cues if isinstance(cue, dict) and str(cue.get("cue_id") or "") in wanted]
    return {
        "cue_count": len(matched),
        "reserved_region": "bottom_subtitle_band",
        "avoid_overlap": True,
    }
