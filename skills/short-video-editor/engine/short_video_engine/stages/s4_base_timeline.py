from __future__ import annotations

from pathlib import Path

from ..compiler.edit_manifest_compiler import compile_edit_manifest
from ..producers.base_plate_renderer import render_base_plate
from ..stage_result import FINAL_BLOCKED, PASS, StageResult, current_command


def run(project_dir: Path, **_: object) -> StageResult:
    manifest_path, manifest_failures = compile_edit_manifest(project_dir)
    output_path, audit_path, render_log_path, render_failures = render_base_plate(project_dir)
    failures = manifest_failures + render_failures
    status = PASS if not failures else FINAL_BLOCKED
    return StageResult(
        "S4_base_timeline",
        status,
        "s4_base_timeline",
        current_command(),
        failures=failures,
        inputs=[manifest_path],
        outputs=[manifest_path, output_path, audit_path, render_log_path],
    )
