#!/usr/bin/env python3
"""Backward-compatible wrapper for svideo validate-production."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    engine_dir = Path(__file__).resolve().parents[1] / "engine"
    sys.path.insert(0, str(engine_dir))
    from short_video_engine.cli import main as cli_main

    return cli_main(["validate-production", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
