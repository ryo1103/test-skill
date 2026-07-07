from __future__ import annotations

from pathlib import Path

from ..producers.text_overlay_renderer import render_text_overlays
from ..stage_result import FINAL_BLOCKED, PASS, StageResult, current_command


def run(project_dir: Path, **_: object) -> StageResult:
    outputs, failures = render_text_overlays(project_dir)
    status = PASS if not failures else FINAL_BLOCKED
    return StageResult("S6_text_layout", status, "s6_text_layout", current_command(), failures=failures, outputs=outputs)
