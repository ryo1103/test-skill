from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import ENGINE_VERSION
from .contracts import write_json
from .paths import stage_reports_dir
from .reporting.provenance import VALIDATOR_VERSION, created_at, file_hash, hash_existing


PASS = "PASS"
DRAFT_ONLY = "DRAFT_ONLY"
FINAL_BLOCKED = "FINAL_BLOCKED"
NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
FAIL = "FAIL"


@dataclass
class StageResult:
    stage: str
    status: str
    validator: str
    command: list[str]
    failures: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[Path] = field(default_factory=list)
    inputs: list[Path] = field(default_factory=list)
    can_claim_complete: bool = False

    def to_report(self) -> dict[str, Any]:
        return {
            "generated_by": "short_video_engine",
            "engine_version": ENGINE_VERSION,
            "validator_version": VALIDATOR_VERSION,
            "validator": self.validator,
            "stage": self.stage,
            "created_at": created_at(),
            "command": " ".join(self.command),
            "status": self.status,
            "can_claim_complete": self.can_claim_complete,
            "failure_codes": [item.get("code") for item in self.failures if item.get("code")],
            "failures": self.failures,
            "warnings": self.warnings,
            "input_artifact_hashes": hash_existing(self.inputs),
            "output_artifact_hashes": hash_existing(self.outputs),
        }

    def write(self, project_dir: Path) -> dict[str, Any]:
        payload = self.to_report()
        write_json(stage_reports_dir(project_dir) / f"{self.stage}.json", payload)
        return payload


def failure(code: str, message: str, remediation: str = "") -> dict[str, str]:
    payload = {"code": code, "message": message}
    if remediation:
        payload["remediation"] = remediation
    return payload


def current_command() -> list[str]:
    return [sys.executable, *sys.argv]
