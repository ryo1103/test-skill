#!/usr/bin/env python3
"""Backward-compatible wrapper for svideo init."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    engine_dir = Path(__file__).resolve().parents[1] / "engine"
    sys.path.insert(0, str(engine_dir))
    from short_video_engine.cli import main as cli_main

    args = sys.argv[1:]
    if args and not args[0].startswith("-"):
        project_dir = args[0]
        rest = args[1:]
    else:
        project_dir = None
        rest = args
    cli_args = ["init"]
    if project_dir is not None:
        cli_args.extend(["--project-dir", project_dir])
    cli_args.extend(rest)
    return cli_main(cli_args)


if __name__ == "__main__":
    raise SystemExit(main())
