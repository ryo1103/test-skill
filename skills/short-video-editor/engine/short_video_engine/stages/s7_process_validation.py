from __future__ import annotations

from pathlib import Path

from ..producers.probe_renderer import render_probe
from ..stage_result import FINAL_BLOCKED, PASS, StageResult, current_command


def run(project_dir: Path, **_: object) -> StageResult:
    probe_path, process_path, coverage_path, failures = render_probe(project_dir)
    status = PASS if not failures else FINAL_BLOCKED
    return StageResult("S7_process_validation", status, "s7_process_validation", current_command(), failures=failures, outputs=[probe_path, process_path, coverage_path])
