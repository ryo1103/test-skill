from pathlib import Path

from ..contracts import read_json, write_json
from ..paths import plan_dir
from ..compiler.shot_plan_compiler import write_shot_plan
from ..stage_result import FAIL, FINAL_BLOCKED, PASS, StageResult, current_command, failure


def run(project_dir: Path, **_: object) -> StageResult:
    units_payload = read_json(plan_dir(project_dir) / "script_units.json", {})
    units = units_payload.get("units") if isinstance(units_payload, dict) else []
    if not isinstance(units, list) or not units:
        return StageResult("S2_visual_plan", FAIL, "s2_visual_plan", current_command(), failures=[failure("missing_script_units", "script_units.json has no units.", "Run S1 first.")])
    cues_payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
    cues = cues_payload.get("cues") if isinstance(cues_payload, dict) else []
    if not isinstance(cues, list) or not cues:
        return StageResult("S2_visual_plan", FAIL, "s2_visual_plan", current_command(), failures=[failure("missing_subtitle_cues", "subtitle_cues.json has no cues.", "Run S1 first.")])
    layout_payload = read_json(plan_dir(project_dir) / "subtitle_layout_cues.json", {})
    layout_cues = layout_payload.get("cues") if isinstance(layout_payload, dict) else []
    if not isinstance(layout_cues, list) or not layout_cues:
        return StageResult("S2_visual_plan", FAIL, "s2_visual_plan", current_command(), failures=[failure("missing_subtitle_layout_cues", "subtitle_layout_cues.json has no cues.", "Run S1_5_subtitle_layout_planning first.")])
    path, failures = write_shot_plan(project_dir)
    status = PASS if not failures else FINAL_BLOCKED
    return StageResult("S2_visual_plan", status, "s2_visual_plan", current_command(), failures=failures, inputs=[plan_dir(project_dir) / "script_units.json", plan_dir(project_dir) / "subtitle_cues.json", plan_dir(project_dir) / "subtitle_layout_cues.json"], outputs=[path])
