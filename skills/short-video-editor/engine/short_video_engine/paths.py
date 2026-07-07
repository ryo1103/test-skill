from __future__ import annotations

from pathlib import Path


def engine_root() -> Path:
    return Path(__file__).resolve().parents[1]


def skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def contracts_dir() -> Path:
    return skill_root() / "contracts"


def project_root(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def plan_dir(project_dir: Path) -> Path:
    return project_dir / "work" / "plan"


def stage_reports_dir(project_dir: Path) -> Path:
    return plan_dir(project_dir) / "stage_reports"


def output_dir(project_dir: Path) -> Path:
    return project_dir / "output"


def assets_dir(project_dir: Path) -> Path:
    return project_dir / "assets"
