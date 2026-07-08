from __future__ import annotations

from pathlib import Path

from ..contracts import read_json, write_json
from ..paths import plan_dir
from ..producers.motion_renderer.renderer import render_motion
from ..stage_result import DRAFT_ONLY, FINAL_BLOCKED, PASS, StageResult, current_command


def run(project_dir: Path, **options: object) -> StageResult:
    index_payload = read_json(plan_dir(project_dir) / "required_motion_index.json", {})
    indexed_required = index_payload.get("required_motions") if isinstance(index_payload, dict) else None
    shot_plan = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    shots = shot_plan.get("shots", []) if isinstance(shot_plan, dict) else []
    required = [shot for shot in shots if isinstance(shot, dict) and shot.get("motion_overlay_required")]
    index_has_required = isinstance(indexed_required, list) and any(isinstance(item, dict) and item.get("motion_required") is True for item in indexed_required)
    if not required and not index_has_required:
        report_path = plan_dir(project_dir) / "motion_overlay_report.json"
        write_json(report_path, {"generated_by": "short_video_engine", "status": PASS, "motion_required": False})
        return StageResult("S5_motion_overlay", PASS, "s5_motion_overlay", current_command(), outputs=[report_path])
    draft_ok = bool(options.get("draft_ok"))
    layers_path, report_path, failures = render_motion(project_dir, motion_renderer=str(options.get("motion_renderer") or "auto"), draft_ok=draft_ok)
    status = PASS if not failures else (DRAFT_ONLY if draft_ok else FINAL_BLOCKED)
    return StageResult("S5_motion_overlay", status, "s5_motion_overlay", current_command(), failures=failures, outputs=[layers_path, report_path])
