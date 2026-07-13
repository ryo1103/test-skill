from __future__ import annotations


TEMPLATE_BY_RELATION = {
    "comparison": "comparison_split_screen",
    "process": "process_flow",
    "cause_effect": "cause_effect_chain",
    "timeline": "timeline",
    "structure": "system_structure",
    "kpi_change": "kpi_delta",
    "before_after": "before_after",
    "not_x_but_y": "not_x_but_y_bridge",
}

TEMPLATE_CANDIDATES_BY_RELATION = {
    "comparison": ["comparison_split_screen", "comparison_balance", "comparison_cards"],
    "process": ["process_flow", "process_stack", "process_ladder"],
    "cause_effect": ["cause_effect_chain", "cause_effect_ripple"],
    "timeline": ["timeline", "timeline_milestones", "timeline_window"],
    "structure": ["system_structure", "structure_layers"],
    "kpi_change": ["kpi_delta", "kpi_dual_meter", "kpi_gauge"],
    "before_after": ["before_after", "before_after_switch", "before_after_reveal"],
    "not_x_but_y": ["not_x_but_y_bridge", "not_x_but_y_pivot"],
}

TEMPLATES = {
    "comparison_split_screen",
    "comparison_balance",
    "comparison_cards",
    "process_flow",
    "process_stack",
    "process_ladder",
    "cause_effect_chain",
    "cause_effect_ripple",
    "timeline",
    "timeline_milestones",
    "timeline_window",
    "system_structure",
    "structure_layers",
    "kpi_delta",
    "kpi_dual_meter",
    "kpi_gauge",
    "before_after",
    "before_after_switch",
    "before_after_reveal",
    "not_x_but_y_bridge",
    "not_x_but_y_pivot",
    "layered_callout",
}

REQUIRED_FIELDS_BY_RELATION = {
    "not_x_but_y": ["rejected_state", "pivot", "accepted_state", "final_emphasis"],
    "cause_effect": ["direction"],
    "process": ["ordered_steps"],
    "comparison": ["left_side", "right_side", "comparison_axis"],
    "kpi_change": ["metric", "delta"],
}

SEMANTIC_TEMPLATE_BY_ACTION = {
    "negate_and_redefine": "negation_to_connector_scene",
    "connector_metaphor": "connector_flow_scene",
    "metric_growth": "narrative_trend_curve_scene",
    "process_migration": "process_migration_scene",
    "density_comparison": "density_pressure_scene",
    "concept_definition": "concept_definition_scene",
    "cause_to_result": "progressive_relation_graph_scene",
    "before_after_change": "before_after_scene",
    "relation_network": "progressive_relation_graph_scene",
    "trend_timeline": "narrative_trend_curve_scene",
    "bottleneck_evidence": "evidence_callout_overlay_scene",
}
