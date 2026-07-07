#!/usr/bin/env python3
"""Shared helpers for short-video workflow gate audits."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


NOT_RUN_STATUSES = {"", "not_run", "pending", "todo", "draft", "template"}
PASS_STATUSES = {"passed", "pass", "complete", "completed"}


def plan_dir(project_dir: Path) -> Path:
    return project_dir / "work" / "plan"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [row for row in csv.DictReader(handle)]
    except csv.Error:
        return []


def meaningful_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if any(str(value or "").strip() for value in row.values())]


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def truthy(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "是", "需要", "required", "enabled"}


def negative(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"0", "false", "no", "n", "否", "不需要", "none", "disabled"}


def status_value(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("status", "") or "").strip().lower()
    return ""


def status_is_passed(payload: Any) -> bool:
    return status_value(payload) in PASS_STATUSES


def status_is_not_run(payload: Any) -> bool:
    return status_value(payload) in NOT_RUN_STATUSES


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def percentage(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return value / total


def fail(stage: str, code: str, message: str, required_action: str, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "stage": stage,
        "code": code,
        "message": message,
        "required_action": required_action,
    }
    item.update(extra)
    return item


def project_path(project_dir: Path, value: Any) -> Path | None:
    text = str(value or "").strip().strip('"').strip("'")
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = project_dir / path
    return path.resolve()


def path_exists(project_dir: Path, value: Any) -> bool:
    path = project_path(project_dir, value)
    return bool(path and path.exists())


def split_path_values(value: Any) -> list[str]:
    text = str(value or "")
    parts = re.split(r"[;,|]", text)
    return [part.strip().strip('"').strip("'") for part in parts if part.strip()]


def load_asset_records(project_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    manifest = read_json(project_dir / "assets" / "metadata" / "asset_manifest.json", {})
    for item in as_list(manifest.get("assets") if isinstance(manifest, dict) else manifest):
        if isinstance(item, dict):
            records.append(item)
    index = read_json(project_dir / "assets_library" / "asset_index.json", {})
    for item in as_list(index.get("assets") if isinstance(index, dict) else index):
        if isinstance(item, dict):
            records.append(item)
    for row in meaningful_rows(read_csv(project_dir / "assets" / "sources.csv")):
        records.append(row)
    return records


def record_asset_key(record: dict[str, Any]) -> str:
    for key in ("asset_key", "id", "key", "selected_asset_key"):
        value = str(record.get(key, "") or "").strip()
        if value:
            return value
    path = str(record.get("file_path") or record.get("path") or record.get("local_path") or "")
    return Path(path).name if path else ""


def asset_record_paths(record: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in ("file_path", "path", "local_path", "cached_source_file", "local_source_clip"):
        value = str(record.get(key, "") or "").strip()
        if value:
            paths.append(value)
    return paths


def asset_record_matches(record: dict[str, Any], shot_id: str, asset_key: str = "") -> bool:
    if asset_key and asset_key == record_asset_key(record):
        return True
    record_shot = str(record.get("shot_id") or record.get("shot") or record.get("matched_shot") or "").strip()
    if shot_id and record_shot and shot_id == record_shot:
        return True
    return False


def resolve_asset_path(project_dir: Path, value: Any, records: list[dict[str, Any]] | None = None) -> Path | None:
    for part in split_path_values(value):
        direct = project_path(project_dir, part)
        if direct and direct.exists():
            return direct
        if records:
            for record in records:
                if part and part == record_asset_key(record):
                    for path_value in asset_record_paths(record):
                        path = project_path(project_dir, path_value)
                        if path and path.exists():
                            return path
    return None


def row_duration(row: dict[str, Any]) -> float:
    duration = to_float(row.get("duration"))
    if duration > 0:
        return duration
    start = to_float(row.get("start"))
    end = to_float(row.get("end"))
    if end > start:
        return end - start
    source_in = to_float(row.get("source_in"))
    source_out = to_float(row.get("source_out"))
    if source_out > source_in:
        return source_out - source_in
    return 0.0


def shot_id_from_item(item: dict[str, Any]) -> str:
    for key in ("shot_id", "shot", "id"):
        value = str(item.get(key, "") or "").strip()
        if value:
            return value
    return ""


def is_broll_scene(value: Any) -> bool:
    text = str(value or "").lower()
    return any(token in text for token in ("broll", "b-roll", "screen_recording", "screen recording", "素材", "footage", "image_motion"))


def is_talking_scene(value: Any) -> bool:
    text = str(value or "").lower()
    return any(token in text for token in ("talking", "head", "oral", "digital_human", "digital human", "口播", "数字人"))


def is_hyperframe_scene(value: Any) -> bool:
    text = str(value or "").lower()
    return any(token in text for token in ("hyperframe", "ae_", "motion_card", "motion card", "animation", "动效"))


def find_ffmpeg() -> str:
    candidates = [
        os.environ.get("FFMPEG", ""),
        shutil.which("ffmpeg") or "",
        "/Users/admin/.local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return ""


def decode_video(path: Path) -> tuple[bool, str]:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False, "ffmpeg unavailable"
    result = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()
    return True, ""


def write_audit(path: Path, status: str, failures: list[dict[str, Any]], **extra: Any) -> int:
    payload: dict[str, Any] = {
        "status": status,
        "checks": extra.pop("checks", []),
        "failures": failures,
        "warnings": extra.pop("warnings", []),
        "remediation_required": bool(failures),
    }
    payload.update(extra)
    write_json(path, payload)
    print(path)
    print(f"status: {status}")
    for item in failures[:12]:
        print(f"FAIL {item.get('code')}: {item.get('message')}")
    return 0 if status == "passed" else 1
