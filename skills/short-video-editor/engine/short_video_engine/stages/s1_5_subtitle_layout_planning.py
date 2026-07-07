from __future__ import annotations

from pathlib import Path

from ..contracts import read_json
from ..paths import plan_dir
from ..producers.subtitle_layout_planner import plan_subtitle_layout
from ..stage_result import FAIL, FINAL_BLOCKED, PASS, StageResult, current_command, failure


def run(project_dir: Path, **_: object) -> StageResult:
    cues_payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
    cues = cues_payload.get("cues") if isinstance(cues_payload, dict) else []
    if not isinstance(cues, list) or not cues:
        return StageResult(
            "S1_5_subtitle_layout_planning",
            FAIL,
            "s1_5_subtitle_layout_planning",
            current_command(),
            failures=[failure("missing_subtitle_cues", "subtitle_cues.json has no cues.", "Run S1_script_and_subtitles first.")],
        )
    outputs, failures = plan_subtitle_layout(project_dir)
    status = PASS if not failures else FINAL_BLOCKED
    return StageResult("S1_5_subtitle_layout_planning", status, "s1_5_subtitle_layout_planning", current_command(), failures=failures, inputs=[plan_dir(project_dir) / "subtitle_cues.json"], outputs=outputs)
