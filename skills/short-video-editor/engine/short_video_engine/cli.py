#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

if __package__ in {None, ""}:
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from short_video_engine.paths import project_root
from short_video_engine.pipeline import init_project, run_pipeline, status as project_status, validate_final, validate_production, validate_stage


def print_payload(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="svideo", description="short-video-editor engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize project structure")
    init.add_argument("--project-dir", required=True)
    init.add_argument("--script-name", default="script.txt")
    init.add_argument("--oral-name", default="oral.mp4")

    run = sub.add_parser("run", help="Run engine pipeline")
    run.add_argument("--project-dir", required=True)
    run.add_argument("--from-stage")
    run.add_argument("--to-stage")
    strict_group = run.add_mutually_exclusive_group()
    strict_group.add_argument("--strict", dest="strict", action="store_true", default=True)
    strict_group.add_argument("--no-strict", dest="strict", action="store_false")
    run.add_argument("--draft-ok", action="store_true")
    run.add_argument("--max-remediation-rounds", type=int, default=0)
    run.add_argument("--no-network", action="store_true")
    run.add_argument("--no-render", action="store_true")
    run.add_argument("--allow-fixtures", action="store_true")
    run.add_argument("--enable-asr", action="store_true", help="Allow S1 to run a local ASR producer when no trusted timing input exists")
    run.add_argument("--motion-renderer", choices=["auto", "pillow", "motion_canvas"], default="auto", help="Preferred S5 motion renderer source. PASS still requires rendered transparent overlay artifacts.")

    validate_stage_parser = sub.add_parser("validate-stage", help="Validate one stage report")
    validate_stage_parser.add_argument("--project-dir", required=True)
    validate_stage_parser.add_argument("--stage", required=True)
    validate_stage_parser.add_argument("--draft-ok", action="store_true")

    validate_final_parser = sub.add_parser("validate-final", help="Validate final video artifacts")
    validate_final_parser.add_argument("--project-dir", required=True)
    validate_final_parser.add_argument("--allow-fixtures", action="store_true")

    validate_prod = sub.add_parser("validate-production", help="Validate production acceptance")
    validate_prod.add_argument("--project-dir", required=True)

    stat = sub.add_parser("status", help="Show pipeline status")
    stat.add_argument("--project-dir", required=True)

    args = parser.parse_args(argv)
    if args.command == "init":
        project_dir = init_project(args.project_dir, args.script_name, args.oral_name)
        print_payload({"status": "initialized", "project_dir": str(project_dir)})
        return 0
    if args.command == "run":
        reports = run_pipeline(
            project_root(args.project_dir),
            from_stage=args.from_stage,
            to_stage=args.to_stage,
            strict=args.strict,
            draft_ok=args.draft_ok,
            max_remediation_rounds=args.max_remediation_rounds,
            no_network=args.no_network,
            no_render=args.no_render,
            allow_fixtures=args.allow_fixtures,
            enable_asr=args.enable_asr,
            motion_renderer=args.motion_renderer,
        )
        print_payload({"reports": reports})
        return 0 if reports and reports[-1]["status"] == "PASS" else 2
    if args.command == "validate-stage":
        result = validate_stage(project_root(args.project_dir), args.stage, args.draft_ok)
        payload = result.write(project_root(args.project_dir))
        print_payload(payload)
        return 0 if payload["status"] == "PASS" else 2
    if args.command == "validate-final":
        result = validate_final(project_root(args.project_dir), args.allow_fixtures)
        payload = result.write(project_root(args.project_dir))
        print_payload(payload)
        return 0 if payload["status"] == "PASS" else 2
    if args.command == "validate-production":
        result = validate_production(project_root(args.project_dir))
        payload = result.write(project_root(args.project_dir))
        print_payload(payload)
        return 0 if payload["status"] == "PASS" else 2
    if args.command == "status":
        print_payload(project_status(project_root(args.project_dir)))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
