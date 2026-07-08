from __future__ import annotations

import csv
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..contracts import load_contract, read_json, write_json
from ..paths import output_dir, plan_dir
from ..stage_result import failure
from ..stages.common import media_metadata


ALLOWED_VISUAL_MODES = {"talking_head_fullscreen", "broll_fullscreen"}
FORBIDDEN_POLICIES = {"freeze_tail", "hold_last_frame", "loop", "repeat", "slow", "stretch", "padding"}
FORBIDDEN_OVERLAY_TOKENS = {"overlay", "subtitle", "title", "motion", "card", "generated"}


def read_manifest(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle)]


def ffmpeg_path() -> str | None:
    return os.environ.get("FFMPEG") or shutil.which("ffmpeg")


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def render_base_plate(project_dir: Path) -> tuple[Path, Path, Path, list[dict[str, str]]]:
    manifest_path = plan_dir(project_dir) / "edit_manifest.csv"
    rows = read_manifest(manifest_path)
    audit_failures = audit_manifest(project_dir, rows)
    output_path = output_dir(project_dir) / "base_plate.mp4"
    render_log_path = plan_dir(project_dir) / "base_render_log.json"
    audit_path = plan_dir(project_dir) / "base_timeline_audit.json"
    if audit_failures:
        write_audit(project_dir, audit_path, render_log_path, rows, output_path, audit_failures, [])
        return output_path, audit_path, render_log_path, audit_failures
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        failures = [failure("ffmpeg_not_found", "ffmpeg is required to render base_plate.mp4.", "Install ffmpeg or set FFMPEG.")]
        write_audit(project_dir, audit_path, render_log_path, rows, output_path, failures, [])
        return output_path, audit_path, render_log_path, failures
    output_dir(project_dir).mkdir(parents=True, exist_ok=True)
    work_dir = project_dir / "work" / "render" / "base_plate_segments"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    segment_paths: list[Path] = []
    commands: list[list[str]] = []
    for index, row in enumerate(rows, start=1):
        source = Path(row["local_source_clip"])
        duration = float(row["duration"])
        source_in = to_float(row.get("source_in"))
        frame_count = max(1, math.ceil(duration * 30))
        segment = work_dir / f"segment_{index:04d}.mp4"
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{source_in:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-frames:v",
            str(frame_count),
            "-an",
            "-r",
            "30",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            str(segment),
        ]
        result = run_cmd(cmd)
        commands.append(cmd)
        if result.returncode != 0:
            failures = [failure("base_segment_render_failed", result.stderr[-1000:] or "ffmpeg segment render failed.")]
            write_audit(project_dir, audit_path, render_log_path, rows, output_path, failures, commands)
            return output_path, audit_path, render_log_path, failures
        segment_paths.append(segment)
    concat_list = work_dir / "concat.txt"
    concat_list.write_text("".join(f"file '{path.as_posix()}'\n" for path in segment_paths), encoding="utf-8")
    video_only = work_dir / "base_plate_video_only.mp4"
    concat_cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-r", "30", "-c:v", "mpeg4", "-q:v", "5", str(video_only)]
    concat_result = run_cmd(concat_cmd)
    commands.append(concat_cmd)
    if concat_result.returncode != 0:
        failures = [failure("base_concat_failed", concat_result.stderr[-1000:] or "ffmpeg concat failed.")]
        write_audit(project_dir, audit_path, render_log_path, rows, output_path, failures, commands)
        return output_path, audit_path, render_log_path, failures
    intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
    oral_video = str(intake.get("oral_video_path") or "")
    oral_duration = float(intake.get("audio_stream_duration") or intake.get("audio_duration") or 0)
    mux_cmd = [ffmpeg, "-y", "-i", str(video_only), "-i", oral_video, "-t", f"{oral_duration:.3f}", "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "copy", "-c:a", "aac", str(output_path)]
    mux_result = run_cmd(mux_cmd)
    commands.append(mux_cmd)
    if mux_result.returncode != 0:
        failures = [failure("base_mux_failed", mux_result.stderr[-1000:] or "ffmpeg mux failed.")]
        write_audit(project_dir, audit_path, render_log_path, rows, output_path, failures, commands)
        return output_path, audit_path, render_log_path, failures
    final_failures = audit_manifest(project_dir, rows)
    final_failures.extend(audit_output_duration(project_dir, output_path, rows))
    write_audit(project_dir, audit_path, render_log_path, rows, output_path, final_failures, commands)
    return output_path, audit_path, render_log_path, final_failures


def audit_manifest(project_dir: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    failures = []
    if not rows:
        return [failure("missing_edit_manifest", "work/plan/edit_manifest.csv is missing or empty.", "Run edit_manifest compiler.")]
    for row in rows:
        visual_mode = row.get("visual_mode", "")
        if visual_mode not in ALLOWED_VISUAL_MODES:
            failures.append(failure("base_plate_contains_disallowed_visual", f"Disallowed visual_mode: {visual_mode}."))
        if row.get("contains_overlay", "").strip().lower() != "false":
            failures.append(failure("base_plate_contains_overlay", "Base plate row contains overlay/card/title/motion content."))
        row_text = " ".join(str(value).lower() for value in row.values())
        if any(token in row_text for token in FORBIDDEN_OVERLAY_TOKENS) and row.get("contains_overlay", "").strip().lower() != "false":
            failures.append(failure("base_plate_contains_overlay", "Overlay/card/title/motion token detected in base plate row."))
        policy = row.get("playback_policy", "").lower()
        if any(token in policy for token in FORBIDDEN_POLICIES):
            failures.append(failure("forbidden_base_plate_padding", f"Forbidden playback policy: {policy}."))
        duration = to_float(row.get("duration"))
        start = to_float(row.get("start"))
        end = to_float(row.get("end"))
        source_in = to_float(row.get("source_in"))
        source_out = to_float(row.get("source_out"))
        source_duration = to_float(row.get("source_duration_sec"))
        if visual_mode == "broll_fullscreen" and duration > source_duration + 1e-6:
            failures.append(failure("broll_source_overrun", f"B-roll shot {row.get('shot_id')} duration exceeds source duration."))
        if source_out > source_duration + 1e-6:
            failures.append(failure("source_timecode_overrun", f"Shot {row.get('shot_id')} source_out exceeds source duration."))
        if source_out - source_in + 0.001 < duration:
            failures.append(failure("source_trim_shorter_than_shot", f"Shot {row.get('shot_id')} source trim is shorter than target duration."))
        if visual_mode == "talking_head_fullscreen":
            if abs(source_in - start) > 0.02 or abs(source_out - end) > 0.02:
                failures.append(failure("talking_head_timecode_mismatch", "Talking-head rows must use the same source timecode interval as the final audio timeline."))
            if row.get("playback_policy") != "same_timecode_from_oral_video":
                failures.append(failure("talking_head_playback_policy_invalid", "Talking-head rows must declare same_timecode_from_oral_video playback policy."))
        if row.get("is_final_conclusion", "").lower() == "true" and visual_mode != "talking_head_fullscreen":
            failures.append(failure("final_conclusion_not_talking_head", "Final conclusion must use talking_head_fullscreen."))
        source = Path(row.get("local_source_clip") or "")
        if not source.exists():
            failures.append(failure("missing_local_source_clip", f"Missing local source clip: {source}."))
    failures.extend(audit_manifest_duration(project_dir, rows))
    return failures


def audit_manifest_duration(project_dir: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
    oral_duration = float(intake.get("audio_stream_duration") or intake.get("audio_duration") or 0)
    tolerance = float(load_contract("final_video_contract.json").get("timing_tolerance_sec") or 0.25)
    max_end = max((to_float(row.get("end")) for row in rows), default=0)
    if oral_duration > 0 and abs(max_end - oral_duration) > tolerance:
        return [failure("base_plate_duration_mismatch", "Manifest end time does not match oral audio duration tolerance.")]
    return []


def audit_output_duration(project_dir: Path, output_path: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not output_path.exists():
        return [failure("missing_base_plate", "output/base_plate.mp4 is missing.")]
    metadata, error = media_metadata(output_path)
    if metadata is None:
        return [failure("base_plate_probe_failed", f"base_plate probe failed: {error}")]
    intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
    oral_duration = float(intake.get("audio_stream_duration") or intake.get("audio_duration") or 0)
    base_duration = float(metadata.get("container_duration") or 0)
    base_video_duration = float(metadata.get("video_stream_duration") or 0)
    tolerance = float(load_contract("final_video_contract.json").get("timing_tolerance_sec") or 0.25)
    if oral_duration > 0 and abs(base_duration - oral_duration) > tolerance:
        return [failure("base_plate_output_duration_mismatch", "Rendered base_plate duration does not match oral audio duration tolerance.")]
    if oral_duration > 0 and base_video_duration + tolerance < oral_duration:
        return [failure("base_plate_video_stream_shorter_than_audio", "Rendered base_plate video stream does not cover oral audio duration.")]
    return []


def write_audit(project_dir: Path, audit_path: Path, render_log_path: Path, rows: list[dict[str, str]], output_path: Path, failures: list[dict[str, str]], commands: list[list[str]]) -> None:
    intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
    metadata, _ = media_metadata(output_path) if output_path.exists() else (None, "")
    base_duration = float(metadata.get("container_duration") or 0) if isinstance(metadata, dict) else 0
    base_video_duration = float(metadata.get("video_stream_duration") or 0) if isinstance(metadata, dict) else 0
    max_end = max((to_float(row.get("end")) for row in rows), default=0)
    payload = {
        "generated_by": "short_video_engine",
        "validator": "s4_base_timeline",
        "status": "PASS" if not failures else "FINAL_BLOCKED",
        "oral_audio_duration_sec": float(intake.get("audio_stream_duration") or intake.get("audio_duration") or 0),
        "base_plate_duration_sec": base_duration,
        "base_plate_video_stream_duration_sec": base_video_duration,
        "max_manifest_end": max_end,
        "rows_checked": len(rows),
        "forbidden_overlay_check": "passed" if not any(item["code"] == "base_plate_contains_overlay" for item in failures) else "failed",
        "final_conclusion_anchor_check": "passed" if not any(item["code"] == "final_conclusion_not_talking_head" for item in failures) else "failed",
        "broll_source_overrun_check": "passed" if not any(item["code"] == "broll_source_overrun" for item in failures) else "failed",
        "failure_codes": [item["code"] for item in failures],
        "failures": failures,
    }
    write_json(audit_path, payload)
    write_json(
        render_log_path,
        {
            "generated_by": "short_video_engine",
            "renderer": "base_plate_renderer",
            "ffmpeg_commands": [" ".join(cmd) for cmd in commands],
            "input_clips": [row.get("local_source_clip") for row in rows],
            "trim_intervals": [
                {
                    "shot_id": row.get("shot_id"),
                    "visual_mode": row.get("visual_mode"),
                    "source": row.get("local_source_clip"),
                    "source_in": row.get("source_in"),
                    "source_out": row.get("source_out"),
                    "duration": row.get("duration"),
                }
                for row in rows
            ],
            "scale_crop_policy": "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "output_duration": base_duration,
            "audio_source": intake.get("oral_video_path"),
        },
    )


def to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
