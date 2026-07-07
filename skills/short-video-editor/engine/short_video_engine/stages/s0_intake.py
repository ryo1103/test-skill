from __future__ import annotations

from pathlib import Path

from .. import ENGINE_VERSION
from ..contracts import read_json, write_json
from ..paths import plan_dir
from ..stage_result import FAIL, PASS, StageResult, current_command, failure, hash_existing
from .common import ensure_project_dirs, media_metadata


def resolve_project_path(project_dir: Path, value: object, default_name: str) -> Path:
    raw = str(value or default_name).strip() or default_name
    path = Path(raw).expanduser()
    return path if path.is_absolute() else project_dir / path


def has_text_content(path: Path) -> bool:
    if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
        return False
    return bool(path.read_text(encoding="utf-8", errors="ignore").strip())


def metadata_failures(metadata: dict[str, object] | None, error: str) -> list[dict[str, str]]:
    failures = []
    if metadata is None:
        return [failure("ffprobe_failed", f"ffprobe failed or returned invalid JSON: {error}", "Use a decodable oral video and ensure ffprobe is installed.")]
    if float(metadata.get("container_duration") or 0) <= 0:
        failures.append(failure("missing_container_duration", "ffprobe did not report a positive container duration.", "Use a valid media container."))
    if float(metadata.get("audio_stream_duration") or 0) <= 0:
        failures.append(failure("missing_audio_stream_duration", "ffprobe did not report a positive audio stream duration.", "Use an oral video with a readable audio stream."))
    resolution = metadata.get("resolution") if isinstance(metadata.get("resolution"), dict) else {}
    if int(resolution.get("width") or 0) <= 0 or int(resolution.get("height") or 0) <= 0:
        failures.append(failure("missing_video_resolution", "ffprobe did not report a positive video resolution.", "Use an oral video with a readable video stream."))
    if float(metadata.get("fps") or 0) <= 0:
        failures.append(failure("missing_fps", "ffprobe did not report a positive frame rate.", "Use an oral video with readable frame-rate metadata."))
    if float(metadata.get("video_stream_duration") or 0) <= 0:
        failures.append(failure("missing_video_stream_duration", "ffprobe did not report a positive video stream duration.", "Use an oral video with readable video duration metadata."))
    return failures


def run(project_dir: Path, script_name: str | None = None, oral_name: str | None = None, **_: object) -> StageResult:
    ensure_project_dirs(project_dir)
    report_path = plan_dir(project_dir) / "project_intake_report.json"
    existing_report = read_json(report_path, {})
    existing_report = existing_report if isinstance(existing_report, dict) else {}
    script_path = resolve_project_path(project_dir, script_name or existing_report.get("script_path"), "script.txt")
    oral_path = resolve_project_path(project_dir, oral_name or existing_report.get("oral_video_path"), "oral.mp4")
    failures = []
    inputs = []
    if not script_path.exists() or not script_path.is_file():
        failures.append(failure("missing_script", f"Script file does not exist: {script_path}", "Create script.txt or set script_path in project_intake_report.json."))
    elif not has_text_content(script_path):
        failures.append(failure("empty_script", f"Script file is empty: {script_path}", "Provide a non-empty source script."))
    else:
        inputs.append(script_path)
    if not oral_path.exists() or not oral_path.is_file():
        failures.append(failure("missing_oral_video", f"Oral video file does not exist: {oral_path}", "Create oral.mp4 or set oral_video_path in project_intake_report.json."))
    elif oral_path.stat().st_size <= 0:
        failures.append(failure("empty_oral_video", f"Oral video file is empty: {oral_path}", "Provide a non-empty oral video."))
    else:
        inputs.append(oral_path)

    metadata = None
    if oral_path.exists() and oral_path.is_file() and oral_path.stat().st_size > 0:
        metadata, error = media_metadata(oral_path)
        failures.extend(metadata_failures(metadata, error))

    if failures:
        return StageResult("S0_intake", FAIL, "s0_intake", current_command(), failures=failures, inputs=inputs)

    payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "validator": "s0_intake",
        "stage": "S0_intake",
        "command": " ".join(current_command()),
        "script_path": str(script_path),
        "oral_video_path": str(oral_path),
        "container_duration": metadata["container_duration"],
        "audio_stream_duration": metadata["audio_stream_duration"],
        "video_stream_duration": metadata["video_stream_duration"],
        "audio_duration": metadata["audio_duration"],
        "resolution": metadata["resolution"],
        "fps": metadata["fps"],
        "audio_codec": metadata["audio_codec"],
        "video_codec": metadata["video_codec"],
        "input_artifact_hashes": hash_existing(inputs),
        "output_artifact_hashes": {},
    }
    write_json(report_path, payload)
    return StageResult("S0_intake", PASS, "s0_intake", current_command(), inputs=inputs, outputs=[report_path])
