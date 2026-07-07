from __future__ import annotations

from pathlib import Path

from ..contracts import read_json, write_json
from ..paths import plan_dir
from ..producers.motion_renderer.renderer import render_motion
from ..stage_result import FINAL_BLOCKED, PASS, StageResult, current_command


def run(project_dir: Path, **options: object) -> StageResult:
    shot_plan = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    shots = shot_plan.get("shots", []) if isinstance(shot_plan, dict) else []
    required = [shot for shot in shots if isinstance(shot, dict) and shot.get("motion_overlay_required")]
    if not required:
        report_path = plan_dir(project_dir) / "motion_overlay_report.json"
        write_json(report_path, {"generated_by": "short_video_engine", "status": PASS, "motion_required": False})
        return StageResult("S5_motion_overlay", PASS, "s5_motion_overlay", current_command(), outputs=[report_path])
    layers_path, report_path, failures = render_motion(project_dir, motion_renderer=str(options.get("motion_renderer") or "auto"))
    status = PASS if not failures else FINAL_BLOCKED
    return StageResult("S5_motion_overlay", status, "s5_motion_overlay", current_command(), failures=failures, outputs=[layers_path, report_path])
