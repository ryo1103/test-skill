from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION


VALIDATOR_VERSION = "1"
REQUIRED_PROVENANCE_FIELDS = {
    "generated_by",
    "engine_version",
    "validator_version",
    "command",
    "stage",
    "created_at",
    "input_artifact_hashes",
    "output_artifact_hashes",
}


def report_failure(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def created_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_existing(paths: list[Path]) -> dict[str, str]:
    return {str(path): file_hash(path) for path in paths if path.exists() and path.is_file()}


def provenance_fields(stage: str, inputs: list[Path] | None = None, outputs: list[Path] | None = None, validator_version: str = VALIDATOR_VERSION) -> dict[str, Any]:
    return {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "validator_version": validator_version,
        "command": " ".join([sys.executable, *sys.argv]),
        "stage": stage,
        "created_at": created_at(),
        "input_artifact_hashes": hash_existing(inputs or []),
        "output_artifact_hashes": hash_existing(outputs or []),
    }


def attach_provenance(payload: dict[str, Any], stage: str, inputs: list[Path] | None = None, outputs: list[Path] | None = None, validator_version: str = VALIDATOR_VERSION) -> dict[str, Any]:
    return {**provenance_fields(stage, inputs, outputs, validator_version), **payload}


def provenance_failures(payload: dict[str, Any], input_paths: list[Path] | None = None, output_paths: list[Path] | None = None, expected_stage: str | None = None, check_recorded_hashes: bool = True) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return [report_failure("report_provenance_missing", "Report is missing or is not a JSON object.")]
    if payload.get("generated_by") != "short_video_engine":
        failures.append(report_failure("report_not_engine_generated", "Report generated_by is not short_video_engine."))
    missing = [field for field in REQUIRED_PROVENANCE_FIELDS if field not in payload or payload.get(field) in (None, "")]
    if missing:
        failures.append(report_failure("report_provenance_missing", f"Report lacks provenance fields: {', '.join(sorted(missing))}."))
    if expected_stage and payload.get("stage") != expected_stage:
        failures.append(report_failure("report_provenance_missing", f"Report stage is {payload.get('stage')!r}, expected {expected_stage!r}."))
    if payload.get("generated_by") == "short_video_engine":
        failures.extend(hash_mismatch_failures(payload, input_paths or [], "input_artifact_hashes"))
        failures.extend(hash_mismatch_failures(payload, output_paths or [], "output_artifact_hashes"))
        if not check_recorded_hashes:
            return failures
        failures.extend(recorded_hash_mismatch_failures(payload, "input_artifact_hashes"))
        failures.extend(recorded_hash_mismatch_failures(payload, "output_artifact_hashes"))
    return failures


def hash_mismatch_failures(payload: dict[str, Any], paths: list[Path], key: str) -> list[dict[str, str]]:
    recorded = payload.get(key)
    if not isinstance(recorded, dict):
        return [report_failure("report_provenance_missing", f"Report {key} must be an object.")]
    expected = hash_existing(paths)
    for path, digest in expected.items():
        if recorded.get(path) != digest:
            return [report_failure("report_artifact_hash_mismatch", f"Report {key} hash mismatch for {path}.")]
    return []


def recorded_hash_mismatch_failures(payload: dict[str, Any], key: str) -> list[dict[str, str]]:
    recorded = payload.get(key)
    if not isinstance(recorded, dict):
        return []
    for path, digest in recorded.items():
        candidate = Path(str(path))
        if candidate.exists() and candidate.is_file() and file_hash(candidate) != digest:
            return [report_failure("report_artifact_hash_mismatch", f"Report {key} hash mismatch for {path}.")]
    return []
