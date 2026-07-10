from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .contracts import load_pipeline_stages
from .stage_result import StageResult
from .stages import (
    s0_intake,
    s1_5_subtitle_layout_planning,
    s1_script_and_subtitles,
    s2_visual_plan,
    s3_asset_sourcing,
    s4_base_timeline,
    s4_5_motion_icon_preparation,
    s5_motion_overlay,
    s6_text_layout,
    s7_process_validation,
    s8_final_render_and_validation,
)

StageFn = Callable[..., StageResult]

_STAGE_HANDLERS: dict[str, StageFn] = {
    "S0_intake": s0_intake.run,
    "S1_script_and_subtitles": s1_script_and_subtitles.run,
    "S1_5_subtitle_layout_planning": s1_5_subtitle_layout_planning.run,
    "S2_visual_plan": s2_visual_plan.run,
    "S3_asset_sourcing": s3_asset_sourcing.run,
    "S4_base_timeline": s4_base_timeline.run,
    "S4_5_motion_icon_preparation": s4_5_motion_icon_preparation.run,
    "S5_motion_overlay": s5_motion_overlay.run,
    "S6_text_layout": s6_text_layout.run,
    "S7_process_validation": s7_process_validation.run,
    "S8_final_render_and_validation": s8_final_render_and_validation.run,
}


def ordered_stage_ids() -> list[str]:
    stages = load_pipeline_stages()
    missing = [stage for stage in stages if stage not in _STAGE_HANDLERS]
    if missing:
        raise ValueError(f"Missing engine stage handlers: {', '.join(missing)}")
    return stages


def get_stage(stage_id: str) -> StageFn:
    if stage_id not in _STAGE_HANDLERS:
        raise KeyError(f"Unknown stage: {stage_id}")
    return _STAGE_HANDLERS[stage_id]


def run_stage(stage_id: str, project_dir: Path, **kwargs) -> StageResult:
    return get_stage(stage_id)(project_dir=project_dir, **kwargs)
