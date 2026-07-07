from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..contracts import read_json, write_json
from ..paths import assets_dir, output_dir, plan_dir


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
SCRIPT_EXTENSIONS = {".txt", ".md"}
MOTION_EXTENSIONS = {".mov", ".webm", ".mp4"}


def ensure_project_dirs(project_dir: Path) -> None:
    for path in [
        plan_dir(project_dir),
        project_dir / "work" / "render",
        project_dir / "work" / "tmp",
        output_dir(project_dir) / "qc",
        output_dir(project_dir) / "edit_package",
        assets_dir(project_dir) / "raw" / "video",
        assets_dir(project_dir) / "selected" / "by_shot",
        assets_dir(project_dir) / "selected" / "by_theme",
        assets_dir(project_dir) / "metadata",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def find_script(project_dir: Path, script_name: str | None = None) -> Path | None:
    candidates = []
    if script_name:
        candidates.append(project_dir / script_name)
    candidates.extend(project_dir.glob("script.*"))
    candidates.extend(project_dir.glob("文案.*"))
    candidates.extend(path for path in project_dir.iterdir() if path.suffix.lower() in SCRIPT_EXTENSIONS)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def find_oral_video(project_dir: Path, oral_name: str | None = None) -> Path | None:
    candidates = []
    if oral_name:
        candidates.append(project_dir / oral_name)
    for name in ("oral.mp4", "avatar.mp4", "avater.mp4", "talking_head.mp4", "source.mp4"):
        candidates.append(project_dir / name)
    candidates.extend(path for path in project_dir.iterdir() if path.suffix.lower() in VIDEO_EXTENSIONS)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def ffprobe_path() -> str | None:
    return os.environ.get("FFPROBE") or shutil.which("ffprobe")


def ffprobe_json(video: Path) -> tuple[dict[str, Any] | None, str]:
    ffprobe = ffprobe_path()
    if not ffprobe:
        return None, "ffprobe_not_found"
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video),
    ]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        return None, result.stderr.strip() or "ffprobe_failed"
    try:
        return json.loads(result.stdout), ""
    except json.JSONDecodeError:
        return None, "ffprobe_invalid_json"


def media_metadata(video: Path) -> tuple[dict[str, Any] | None, str]:
    payload, error = ffprobe_json(video)
    if payload is None:
        return None, error
    video_stream = next((stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"), {})
    audio_stream = next((stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"), {})
    container_duration = safe_float(payload.get("format", {}).get("duration"))
    video_duration = safe_float(video_stream.get("duration"))
    audio_duration = safe_float(audio_stream.get("duration"))
    metadata = {
        "source": str(video),
        "container_duration": container_duration,
        "audio_stream_duration": audio_duration,
        "video_stream_duration": video_duration,
        "audio_duration": audio_duration,
        "resolution": {
            "width": int(video_stream.get("width") or 0),
            "height": int(video_stream.get("height") or 0),
        },
        "fps": parse_fps(str(video_stream.get("r_frame_rate") or video_stream.get("avg_frame_rate") or "")),
        "audio_codec": audio_stream.get("codec_name") or "",
        "video_codec": video_stream.get("codec_name") or "",
        "format": payload.get("format", {}),
    }
    return metadata, ""


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_fps(value: str) -> float:
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            return float(numerator) / max(float(denominator), 1.0)
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def split_script_units(text: str) -> list[dict[str, Any]]:
    chunks = [chunk.strip() for chunk in re.split(r"(?<=[。！？!?；;])|\n+", text) if chunk.strip()]
    if not chunks and text.strip():
        chunks = [text.strip()]
    units = []
    for index, chunk in enumerate(chunks, start=1):
        role = "final_summary" if index == len(chunks) else "explanation"
        units.append({"unit_id": f"u{index:03d}", "text": chunk, "narrative_role": role})
    return units


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle)]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows or []:
            writer.writerow(row)


def real_decodable_video(path: Path) -> bool:
    if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
        return False
    metadata, _ = media_metadata(path)
    return bool(metadata and metadata.get("audio_duration", 0) >= 0 and metadata.get("resolution", {}).get("width", 0) > 0)


def load_stage_report(project_dir: Path, stage: str) -> dict[str, Any]:
    payload = read_json(plan_dir(project_dir) / "stage_reports" / f"{stage}.json", {})
    return payload if isinstance(payload, dict) else {}


def all_previous_pass(project_dir: Path, stages: list[str]) -> bool:
    return all(load_stage_report(project_dir, stage).get("status") == "PASS" for stage in stages)


def has_engine_pass(report: dict[str, Any]) -> bool:
    return report.get("generated_by") == "short_video_engine" and report.get("status") == "PASS"
