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
    "negation_to_connector_scene",
    "connector_flow_scene",
    "metric_growth_scene",
    "process_migration_scene",
    "density_pressure_scene",
    "concept_definition_scene",
    "cause_to_result_scene",
    "before_after_scene",
    "progressive_relation_graph_scene",
    "narrative_trend_curve_scene",
    "evidence_callout_overlay_scene",
}

OPEN_CANVAS_TEMPLATES = {
    "progressive_relation_graph_scene",
    "narrative_trend_curve_scene",
    "evidence_callout_overlay_scene",
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
    semantic_action = str(segment.get("semantic_action") or "")
    wanted_visuals = " ".join(str(item) for item in (shot.get("wanted_visuals") or shot.get("required_entities") or segment.get("logic_entities") or []))
    template = str(segment.get("recommended_template") or "")
    if not template:
        template = select_scene_template(relation, script_fragment, wanted_visuals)
    labels = semantic_labels(segment) or [str(item) for item in (segment.get("motion_text_items") or segment.get("logic_entities") or []) if str(item).strip()]
    labels = (labels + labels_for_template(template, relation))[:4]
    nodes, metrics, connectors, layout_type, topology = scene_components_for(segment, template, labels)
    cue_anchors = subtitle_cue_anchors(subtitle_layout, segment)
    primary_title = str(segment.get("visual_claim") or (labels[0] if labels else relation) or "逻辑关系")[:18]
    production_rules = preset.get("production_composition_rules") if isinstance(preset.get("production_composition_rules"), dict) else {}
    composition_mode = "open_canvas" if template in OPEN_CANVAS_TEMPLATES else ("split_field" if template in {"comparison_split_glass", "comparison_split_glass_scene", "before_after_scene"} else "bounded_semantic")
    return {
        "scene_id": f"graphic_{index:03d}_{shot_id or 'scene'}",
        "motion_id": segment.get("motion_id"),
        "shot_id": shot_id,
        "covered_shot_ids": segment.get("covered_shot_ids") or ([shot_id] if shot_id else []),
        "logic_segment_id": segment.get("logic_segment_id"),
        "logic_relation": relation,
        "semantic_action": semantic_action,
        "script_fragment": script_fragment,
        "wanted_visuals": wanted_visuals,
        "subtitle_layout_cues": subtitle_summary(subtitle_layout, segment, cue_anchors),
        "cue_anchors": cue_anchors,
        "scene_template": template,
        "layout_type": layout_type,
        "topology": topology,
        "composition_mode": composition_mode,
        "visual_grammar": "editorial_tech_overlay_v2",
        "visual_metaphor": visual_metaphor_for(template, relation),
        "primary_title": primary_title,
        "secondary_labels": labels[:4],
        "nodes": nodes,
        "metrics": metrics,
        "connectors": connectors,
        "background_treatment": background_treatment_for(template, preset),
        "animation_sequence": animation_sequence(preset, template, semantic_action),
        "quality_target": {
            "professional_quality_status": "target",
            "motion_design_preset_applied": True,
            "no_large_empty_panel": True,
            "no_title_subtitle_overlap": True,
            "no_global_outer_frame": production_rules.get("no_global_outer_frame") is True,
            "no_unmotivated_full_width_connector": production_rules.get("no_unmotivated_full_width_connector") is True,
            "no_glyph_arrow": production_rules.get("no_glyph_arrow") is True,
            "localized_template_chrome": production_rules.get("localized_template_chrome") is True,
            "local_readability_backdrop": production_rules.get("local_readability_backdrop") is True,
            "connector_animation_policy": production_rules.get("connector_animation_policy") or "segmented_sequential_node_to_node",
            "no_unmotivated_yellow_connector": production_rules.get("no_unmotivated_yellow_connector") is True,
            "semantic_color_roles_applied": production_rules.get("semantic_color_roles_applied") is True,
            "open_canvas_requires_materialized_topology": production_rules.get("open_canvas_requires_materialized_topology") is True,
            "cue_anchored_reveal_required": production_rules.get("cue_anchored_reveal_required") is True,
            "base_plate_visible": True,
            "required_components": ["materialized_open_canvas_topology"] if composition_mode == "open_canvas" else ["panel", "two_of_icon_node_connector_metric"],
        },
        "component_inventory": component_inventory(template, nodes, metrics, connectors, composition_mode),
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
    if template == "negation_to_connector_scene":
        return ["芯片", "光模块", "连接器", "数据流"]
    if template == "connector_flow_scene":
        return ["输入", "连接器", "输出"]
    if template == "metric_growth_scene":
        return ["基准", "增长", "方向"]
    if template == "process_migration_scene":
        return ["旧路径", "迁移", "新路径", "结果"]
    if template == "density_pressure_scene":
        return ["旧方案", "高密度压力", "新方案"]
    if template in {"concept_definition_scene", "cause_to_result_scene", "before_after_scene"}:
        return ["概念", "机制", "结果"]
    if template == "progressive_relation_graph_scene":
        return ["核心", "依赖条件", "支撑条件"]
    if template == "narrative_trend_curve_scene":
        return ["现在", "拐点", "未来", "趋势"]
    if template == "evidence_callout_overlay_scene":
        return ["关键环节", "核心瓶颈", "量化证据"]
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
    if template in {"negation_to_connector_scene", "connector_flow_scene", "process_migration_scene", "density_pressure_scene", "cause_to_result_scene", "before_after_scene"}:
        return [{"id": f"n{idx + 1}", "label": label, "role": "semantic_node"} for idx, label in enumerate(labels[:4])]
    if template in {"chip_node_network", "process_milestone_rail"}:
        return [{"id": f"n{idx + 1}", "label": label, "role": "node"} for idx, label in enumerate(labels[:4])]
    if template in {"comparison_split_glass", "not_x_but_y_pivot_panel"}:
        return [{"id": "left", "label": labels[0], "role": "source"}, {"id": "right", "label": labels[-1], "role": "target"}]
    return [{"id": "core", "label": labels[0], "role": "focus"}, {"id": "support", "label": labels[min(1, len(labels) - 1)], "role": "support"}]


def metrics_for_template(template: str, segment: dict[str, Any], labels: list[str]) -> list[dict[str, Any]]:
    if template == "metric_growth_scene":
        slots = segment.get("slots") if isinstance(segment.get("slots"), dict) else {}
        return [
            {"id": "baseline", "label": slot_text(slots.get("baseline")) or "基准", "value": "baseline"},
            {"id": "delta", "label": slot_text(slots.get("target_or_delta")) or "增长", "value": "delta"},
        ]
    if template == "density_pressure_scene":
        return [{"id": "pressure", "label": "密度压力", "value": "expansion_required"}]
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


def scene_components_for(segment: dict[str, Any], template: str, labels: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str, str]:
    action = str(segment.get("semantic_action") or "")
    slots = segment.get("slots") if isinstance(segment.get("slots"), dict) else {}
    if action == "relation_network":
        nodes = [
            graph_node("core", slots, "root", 0.50, 0.16, 0),
            graph_node("dependency_a", slots, "dependency", 0.17, 0.64, 1),
            graph_node("dependency_b", slots, "dependency", 0.83, 0.64, 2),
        ]
        connectors = [
            {"from": "core", "to": "dependency_a", "relation": "depends_on", "style": "semantic_path", "reveal_order": 1},
            {"from": "core", "to": "dependency_b", "relation": "depends_on", "style": "semantic_path", "reveal_order": 2},
        ]
        return nodes, [], connectors, "semantic_graph", "hub_spoke"
    if action == "cause_to_result":
        nodes = [
            graph_node("cause", slots, "cause", 0.14, 0.48, 0),
            graph_node("mechanism", slots, "mechanism", 0.50, 0.48, 1),
            graph_node("result", slots, "result", 0.86, 0.48, 2),
        ]
        connectors = [
            {"from": "cause", "to": "mechanism", "relation": "causes", "style": "semantic_path", "reveal_order": 1},
            {"from": "mechanism", "to": "result", "relation": "produces", "style": "semantic_path", "reveal_order": 2},
        ]
        return nodes, [], connectors, "semantic_graph", "directed_chain"
    if action == "trend_timeline":
        periods = ["start_period", "pivot_period", "end_period"]
        nodes = [graph_node(slot, slots, "milestone", x, 0.76, order) for slot, x, order in zip(periods, (0.08, 0.52, 0.92), range(3))]
        metrics = [{"id": "trend", "label": slot_text(slots.get("metric")), "value": slot_text(slots.get("trend_label")), "role": "trend_metric"}]
        connectors = [
            {"from": "start_period", "to": "pivot_period", "relation": "trend", "style": "smooth_curve", "reveal_order": 1},
            {"from": "pivot_period", "to": "end_period", "relation": "projection", "style": "smooth_curve_contrast", "reveal_order": 2},
        ]
        return nodes, metrics, connectors, "narrative_trend", "time_series"
    if action == "metric_growth":
        nodes = [
            graph_node("baseline", slots, "baseline", 0.08, 0.76, 0),
            graph_node("metric", slots, "metric", 0.52, 0.76, 1),
            graph_node("target_or_delta", slots, "target", 0.92, 0.76, 2),
        ]
        metrics = [{"id": "trend", "label": slot_text(slots.get("metric")), "value": slot_text(slots.get("target_or_delta")), "role": "trend_metric"}]
        connectors = [
            {"from": "baseline", "to": "metric", "relation": "baseline", "style": "smooth_curve", "reveal_order": 1},
            {"from": "metric", "to": "target_or_delta", "relation": "growth", "style": "smooth_curve", "reveal_order": 2},
        ]
        return nodes, metrics, connectors, "narrative_trend", "time_series"
    if action == "bottleneck_evidence":
        nodes = [
            graph_node("subject", slots, "anchor", 0.50, 0.42, 0),
            graph_node("bottleneck", slots, "callout", 0.50, 0.20, 1),
        ]
        metrics = [{"id": "evidence", "label": slot_text(slots.get("bottleneck")), "value": slot_text(slots.get("duration_or_metric")), "role": "evidence"}]
        connectors = [{"from": "bottleneck", "to": "subject", "relation": "locates", "style": "leader_line", "reveal_order": 1}]
        return nodes, metrics, connectors, "anchored_evidence", "callout_anchor"
    nodes = nodes_for_template(template, labels)
    return nodes, metrics_for_template(template, segment, labels), connectors_for_template(template, nodes), "template_layout", "ordered"


def graph_node(slot: str, slots: dict[str, Any], role: str, x: float, y: float, reveal_order: int) -> dict[str, Any]:
    return {
        "id": slot,
        "label": slot_text(slots.get(slot)),
        "role": role,
        "icon_slot": slot,
        "position": {"x": x, "y": y},
        "reveal_order": reveal_order,
    }


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
        "negation_to_connector_scene": "two rejected states are crossed out before the accepted connector carries a signal flow",
        "connector_flow_scene": "input signal travels through connector and exits as output",
        "metric_growth_scene": "baseline meter grows into changed metric with directional emphasis",
        "process_migration_scene": "old path transitions into new manufacturing path and result",
        "density_pressure_scene": "old solution is constrained by density pressure while the new solution expands capacity",
        "concept_definition_scene": "subject connects to definition and role through a visible relation edge",
        "cause_to_result_scene": "cause passes through mechanism into result",
        "before_after_scene": "before state transforms across an axis into after state",
        "progressive_relation_graph_scene": "semantic nodes appear only when narration establishes their relationship, then materialized paths connect them",
        "narrative_trend_curve_scene": "a sparse time axis draws toward a narrated pivot and continues as a semantic projection",
        "evidence_callout_overlay_scene": "a local evidence label locks onto the relevant base-plate region and reveals one decisive metric",
    }.get(template, f"{relation or 'logic'} hud graphic")


def animation_sequence(preset: dict[str, Any], template: str, semantic_action: str = "") -> list[dict[str, Any]]:
    timing = preset.get("animation_timing") if isinstance(preset.get("animation_timing"), dict) else {}
    easing = str(timing.get("easing") or "cubic-bezier(0.16,1,0.3,1)")
    stagger = float(timing.get("stagger_sec") or 0.08)
    stages = {
        "progressive_relation_graph_scene": ["show_core", "grow_relation_a", "reveal_dependency_a", "grow_relation_b", "reveal_dependency_b", "settle_network"],
        "narrative_trend_curve_scene": ["reveal_axis", "draw_trend", "reveal_pivot", "extend_projection", "hold_outlook"],
        "evidence_callout_overlay_scene": ["locate_subject", "pin_bottleneck", "reveal_metric", "hold_evidence"],
    }.get(template, ["start", "build", "peak", "settle", "end"])
    if template == "narrative_trend_curve_scene" and semantic_action == "metric_growth":
        stages = ["reveal_baseline", "draw_growth_curve", "reveal_delta", "direction_emphasis"]
    total = max(1.2, float(timing.get("duration_sec") or 1.8))
    duration = round(total / len(stages), 3)
    return [
        {"stage": stage, "duration_sec": duration, "easing": easing, "stagger_sec": stagger, "intent": intent_for_stage(stage, template)}
        for stage in stages
    ]


def intent_for_stage(stage: str, template: str) -> str:
    generic = {
        "start": "transparent pre-roll and scan grid lock",
        "build": f"{template} primary components enter with stagger",
        "peak": "connectors, node glow, or meter value reach readable emphasis",
        "settle": "reduce movement and hold the logic relation",
        "end": "fade nonessential highlights while preserving semantic read",
    }
    semantic = {
        "show_core": "establish the narrated core node without a surrounding card",
        "grow_relation_a": "draw the first edge from the established node",
        "reveal_dependency_a": "reveal the first dependency at the edge endpoint",
        "grow_relation_b": "draw the second relation only when narration introduces it",
        "reveal_dependency_b": "reveal the second dependency at the materialized endpoint",
        "settle_network": "hold the completed topology with restrained halo motion",
        "reveal_axis": "materialize a sparse time axis while preserving the base plate",
        "draw_trend": "draw the primary trend curve from the first narrated period",
        "reveal_pivot": "emphasize the narrated pivot period and semantic tag",
        "extend_projection": "continue the projection with contrast only when direction changes",
        "hold_outlook": "hold the complete trend for reading",
        "reveal_baseline": "establish the metric baseline on a sparse axis",
        "draw_growth_curve": "draw the metric change as a continuous semantic curve",
        "reveal_delta": "reveal the target or delta at the curve endpoint",
        "direction_emphasis": "hold the direction with semantic color emphasis",
        "locate_subject": "establish the relevant base-plate subject region",
        "pin_bottleneck": "grow a leader line to the bottleneck target",
        "reveal_metric": "reveal the compact evidence plaque and decisive value",
        "hold_evidence": "hold the anchored evidence without adding decorative motion",
    }
    return semantic.get(stage) or generic.get(stage) or f"materialize semantic stage {stage}"


def component_inventory(template: str, nodes: list[dict[str, Any]], metrics: list[dict[str, Any]], connectors: list[dict[str, Any]], composition_mode: str = "bounded_semantic") -> dict[str, Any]:
    return {
        "panel": composition_mode != "open_canvas",
        "open_canvas": composition_mode == "open_canvas",
        "icon": template in PROFESSIONAL_TEMPLATES,
        "node": bool(nodes),
        "node_count": len(nodes),
        "connector": bool(connectors),
        "connector_count": len(connectors),
        "metric": bool(metrics),
        "metric_count": len(metrics),
        "callout": template == "evidence_callout_overlay_scene",
    }


def semantic_labels(segment: dict[str, Any]) -> list[str]:
    slots = segment.get("slots") if isinstance(segment.get("slots"), dict) else {}
    action = str(segment.get("semantic_action") or "")
    orders = {
        "negate_and_redefine": ["rejected_a", "rejected_b", "accepted_definition", "subject"],
        "connector_metaphor": ["input", "connector", "output"],
        "metric_growth": ["metric", "baseline", "target_or_delta"],
        "process_migration": ["old_step", "new_step", "result"],
        "density_comparison": ["old_solution", "new_requirement", "new_solution"],
        "concept_definition": ["subject", "definition", "role"],
        "cause_to_result": ["cause", "mechanism", "result"],
        "before_after_change": ["before", "transition", "after"],
    }
    return [slot_text(slots.get(key)) for key in orders.get(action, []) if slot_text(slots.get(key))]


def slot_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or "").strip()
    return str(value or "").strip()


def subtitle_summary(subtitle_layout: dict[str, Any], segment: dict[str, Any], anchors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    anchors = anchors if anchors is not None else subtitle_cue_anchors(subtitle_layout, segment)
    return {
        "cue_count": len(anchors),
        "reserved_region": "bottom_subtitle_band",
        "avoid_overlap": True,
        "cue_anchored": bool(anchors),
    }


def subtitle_cue_anchors(subtitle_layout: dict[str, Any], segment: dict[str, Any]) -> list[dict[str, Any]]:
    cues = subtitle_layout.get("cues") if isinstance(subtitle_layout, dict) else []
    cues = cues if isinstance(cues, list) else []
    wanted = {str(item) for item in (segment.get("subtitle_cue_ids") or [])}
    interval = (segment.get("required_intervals") or [{}])[0] if isinstance(segment.get("required_intervals"), list) else {}
    start_sec = float_or_zero(interval.get("start"))
    end_sec = float_or_zero(interval.get("end"))
    matched = []
    for cue in cues:
        if not isinstance(cue, dict):
            continue
        cue_id = str(cue.get("cue_id") or "")
        parent_id = str(cue.get("parent_cue_id") or cue.get("semantic_parent_cue_id") or "")
        cue_start = float_or_zero(cue.get("start"))
        cue_end = float_or_zero(cue.get("end"))
        belongs = cue_id in wanted or parent_id in wanted
        overlaps = end_sec > start_sec and cue_end > start_sec and cue_start < end_sec
        if belongs or (not wanted and overlaps):
            matched.append(cue)
    matched.sort(key=lambda item: float_or_zero(item.get("start")))
    duration = max(0.001, end_sec - start_sec)
    return [
        {
            "cue_id": str(cue.get("cue_id") or ""),
            "parent_cue_id": str(cue.get("parent_cue_id") or cue.get("semantic_parent_cue_id") or ""),
            "text": str(cue.get("display_text") or cue.get("source_text") or ""),
            "start_offset_sec": round(max(0.0, float_or_zero(cue.get("start")) - start_sec), 3),
            "end_offset_sec": round(max(0.0, float_or_zero(cue.get("end")) - start_sec), 3),
            "progress": round(max(0.0, min(1.0, (float_or_zero(cue.get("start")) - start_sec) / duration)), 4),
            "timing_provenance": cue.get("timing_provenance") or {},
        }
        for cue in matched
    ]


def background_treatment_for(template: str, preset: dict[str, Any]) -> str:
    if template in OPEN_CANVAS_TEMPLATES:
        return "base_plate_navy_wash_with_local_semantic_surfaces"
    return preset.get("background_treatment", {}).get("default") or "localized_translucent_readability_backdrop"


def float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
