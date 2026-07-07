#!/usr/bin/env python3
"""Run short-video workflow gates in the required order."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from workflow_audit_lib import plan_dir, read_json, write_json


SCRIPT_DIR = Path(__file__).resolve().parent


def run_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def append_remediation(project_dir: Path, gate: str, result: subprocess.CompletedProcess[str], command: list[str]) -> None:
    path = plan_dir(project_dir) / "remediation_log.json"
    payload = read_json(path, {})
    if not isinstance(payload, dict) or not payload:
        payload = {"status": "in_progress", "attempts": [], "unresolved_blockers": [], "final_block_allowed": False}
    payload.setdefault("attempts", [])
    payload.setdefault("unresolved_blockers", [])
    payload["status"] = "in_progress"
    payload["attempts"].append(
        {
            "gate": gate,
            "failure_code": "script_exit_nonzero",
            "action": " ".join(command),
            "result": "still_failing",
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
            "files_changed": [],
            "next_action": "Read the failed audit JSON, fix the required artifact, then rerun this gate.",
        }
    )
    write_json(path, payload)


def ensure_style_intake(project_dir: Path) -> subprocess.CompletedProcess[str] | None:
    required = ["style_contract.json", "video_topic.json", "style_intake_report.json"]
    if all((plan_dir(project_dir) / name).exists() for name in required):
        return None
    script = SCRIPT_DIR / "create_style_contract.py"
    if not script.exists():
        return subprocess.CompletedProcess([sys.executable, str(script), str(project_dir)], 1, "", "create_style_contract.py is missing")
    return run_command([sys.executable, str(script), str(project_dir)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run short-video workflow gates in order.")
    parser.add_argument("project_dir")
    parser.add_argument("--mode", default="final", choices=["final", "audit-only"], help="final stops before rendering unless all gates pass")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    if not (project_dir / "work" / "plan").exists():
        print("Project is not initialized. Run scripts/init_short_video_project.py <project_dir> first.", file=sys.stderr)
        return 1

    style_result = ensure_style_intake(project_dir)
    if style_result is not None and style_result.returncode != 0:
        append_remediation(project_dir, "style_intake", style_result, style_result.args if isinstance(style_result.args, list) else [str(style_result.args)])
        print(style_result.stdout, end="")
        print(style_result.stderr, end="", file=sys.stderr)
        return 1

    gate_commands: list[tuple[str, list[str]]] = [
        ("visual_strategy", [sys.executable, str(SCRIPT_DIR / "audit_visual_strategy.py"), str(project_dir)]),
        ("asset_gate", [sys.executable, str(SCRIPT_DIR / "audit_asset_gate.py"), str(project_dir)]),
        ("visual_ratio", [sys.executable, str(SCRIPT_DIR / "audit_visual_ratio.py"), str(project_dir)]),
        ("source_usage", [sys.executable, str(SCRIPT_DIR / "audit_source_usage.py"), str(project_dir)]),
        ("hyperframe_plan", [sys.executable, str(SCRIPT_DIR / "audit_hyperframe_plan.py"), str(project_dir)]),
        ("layout_qc", [sys.executable, str(SCRIPT_DIR / "audit_layout_plan.py"), str(project_dir)]),
        ("probe_render", [sys.executable, str(SCRIPT_DIR / "render_probe.py"), str(project_dir)]),
        ("workflow_integration", [sys.executable, str(SCRIPT_DIR / "audit_workflow_integration.py"), str(project_dir)]),
    ]

    for gate, command in gate_commands:
        missing = [part for part in command[1:2] if not Path(part).exists()]
        if missing:
            result = subprocess.CompletedProcess(command, 1, "", f"Missing gate script: {missing[0]}")
        else:
            result = run_command(command)
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            append_remediation(project_dir, gate, result, command)
            print(f"Gate failed: {gate}. Fix the reported artifact and rerun.", file=sys.stderr)
            return 1

    print("All workflow gates passed. Final render may proceed." if args.mode == "final" else "All workflow audits passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
