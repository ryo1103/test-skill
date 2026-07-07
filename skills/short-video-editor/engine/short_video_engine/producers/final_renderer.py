from __future__ import annotations

import csv
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import load_contract, read_json, write_json
from ..paths import output_dir, plan_dir
from ..reporting.provenance import provenance_fields
from ..stage_result import current_command, failure
from ..stages.common import ffprobe_json, media_metadata
from .probe_renderer import escape_filter_path, extract_frame, ffmpeg_path, motion_required, to_float


QC_NAMES = ["start", "mid", "end", "tail"]


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def read_manifest(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle)]


def render_final(project_dir: Path) -> tuple[list[Path], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    final_path = output_dir(project_dir) / "final.mp4"
    base = output_dir(project_dir) / "base_plate.mp4"
    subtitles = output_dir(project_dir) / "subtitles.ass"
    title = output_dir(project_dir) / "title_overlay.ass"
    coverage = read_json(plan_dir(project_dir) / "timeline_coverage_report.json", {})
    if coverage.get("status") != "PASS":
        failures.append(failure("timeline_coverage_not_passed", "timeline_coverage_report.json must PASS before final render."))
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        failures.append(failure("ffmpeg_not_found", "ffmpeg is required for final render."))
    for path, code in [(base, "missing_base_plate"), (subtitles, "missing_subtitles_ass"), (title, "missing_title_overlay")]:
        if not path.exists():
            failures.append(failure(code, f"{path} is missing."))
    if failures:
        write_final_reports(project_dir, [], failures)
        return [], failures
    motion_specs = motion_overlay_specs(project_dir)
    cmd = build_final_ffmpeg_command(ffmpeg, base, title, subtitles, final_path, motion_specs)
    result = run_cmd(cmd)
    if result.returncode != 0:
        failures.append(failure("final_render_failed", result.stderr[-1200:] or "ffmpeg final render failed."))
        write_final_reports(project_dir, [final_path], failures, ffmpeg_command=cmd, motion_specs=motion_specs)
        return [final_path], failures
    write_final_reports(project_dir, [final_path], failures, ffmpeg_command=cmd, motion_specs=motion_specs)
    failures.extend(extract_final_frames(project_dir, final_path))
    failures.extend(build_edit_package(project_dir))
    failures.extend(validate_final_outputs(project_dir))
    write_final_reports(project_dir, [final_path], failures, ffmpeg_command=cmd, motion_specs=motion_specs)
    return [
        final_path,
        plan_dir(project_dir) / "final_render_log.json",
        plan_dir(project_dir) / "final_video_metadata.json",
        plan_dir(project_dir) / "final_stream_probe.json",
    ], failures


def build_final_ffmpeg_command(ffmpeg: str, base: Path, title: Path, subtitles: Path, final_path: Path, motion_specs: list[dict[str, Any]]) -> list[str]:
    if not motion_specs:
        vf = f"ass={escape_filter_path(title)},ass={escape_filter_path(subtitles)}"
        return [ffmpeg, "-y", "-i", str(base), "-vf", vf, "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", str(final_path)]
    cmd = [ffmpeg, "-y", "-i", str(base)]
    for spec in motion_specs:
        cmd.extend(["-framerate", f"{spec['framerate']:.3f}", "-i", str(spec["pattern"])])
    filters = [f"[0:v]ass={escape_filter_path(title)},ass={escape_filter_path(subtitles)}[v0]"]
    previous = "v0"
    for index, spec in enumerate(motion_specs, start=1):
        motion = f"m{index}"
        current = f"v{index}"
        filters.append(f"[{index}:v]format=rgba,scale={spec['width']}:{spec['height']},setpts=PTS-STARTPTS+{spec['start']:.3f}/TB[{motion}]")
        filters.append(f"[{previous}][{motion}]overlay=0:0:eof_action=pass:repeatlast=0[{current}]")
        previous = current
    return [*cmd, "-filter_complex", ";".join(filters), "-map", f"[{previous}]", "-map", "0:a:0?", "-c:v", "mpeg4", "-q:v", "5", "-c:a", "aac", str(final_path)]


def motion_overlay_specs(project_dir: Path) -> list[dict[str, Any]]:
    base_meta, _ = media_metadata(output_dir(project_dir) / "base_plate.mp4")
    resolution = base_meta.get("resolution") if isinstance(base_meta, dict) and isinstance(base_meta.get("resolution"), dict) else {}
    width = int(resolution.get("width") or 1080)
    height = int(resolution.get("height") or 1920)
    layers = read_json(plan_dir(project_dir) / "motion_layers.json", {}).get("layers") or []
    specs: list[dict[str, Any]] = []
    for layer in layers if isinstance(layers, list) else []:
        if layer.get("overlay_compositing_mode") != "transparent_rgba_overlay" or layer.get("alpha_channel_status") != "passed":
            continue
        sequence_dir = Path(str(layer.get("png_sequence_dir") or ""))
        if not sequence_dir.exists() or not sequence_dir.is_dir():
            continue
        frames = sorted(sequence_dir.glob("frame_*.png"))
        if not frames:
            continue
        intervals = layer.get("required_intervals") or []
        if not intervals:
            continue
        start = to_float(intervals[0].get("start"))
        end = to_float(intervals[0].get("end"))
        if end <= start:
            continue
        specs.append(
            {
                "shot_id": str(layer.get("shot_id") or ""),
                "covered_shot_ids": [str(item) for item in (layer.get("covered_shot_ids") or []) if str(item).strip()] or [str(layer.get("shot_id") or "")],
                "pattern": sequence_dir / "frame_%03d.png",
                "start": start,
                "end": end,
                "framerate": max(1.0, len(frames) / max(end - start, 0.1)),
                "width": width,
                "height": height,
                "compositing_mode": "transparent_rgba_overlay",
            }
        )
    return specs


def write_final_reports(project_dir: Path, outputs: list[Path], failures: list[dict[str, str]], ffmpeg_command: list[str] | None = None, motion_specs: list[dict[str, Any]] | None = None) -> None:
    del outputs
    base = output_dir(project_dir) / "base_plate.mp4"
    final = output_dir(project_dir) / "final.mp4"
    intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
    base_meta, _ = media_metadata(base) if base.exists() else (None, "")
    final_meta, _ = media_metadata(final) if final.exists() else (None, "")
    stream_probe = stream_probe_payload(final) if final.exists() else {}
    last_ts = last_video_frame_timestamp(final) if final.exists() else 0
    video_before = to_float(base_meta.get("container_duration")) if isinstance(base_meta, dict) else 0
    audio_before = to_float(intake.get("audio_stream_duration") or intake.get("audio_duration"))
    final_video_duration = stream_probe.get("video_stream_duration", 0)
    final_audio_duration = stream_probe.get("audio_stream_duration", 0)
    final_inputs = [base, output_dir(project_dir) / "subtitles.ass", output_dir(project_dir) / "title_overlay.ass", plan_dir(project_dir) / "motion_layers.json", plan_dir(project_dir) / "edit_manifest.csv", plan_dir(project_dir) / "timeline_coverage_report.json"]
    final_outputs = [final] if final.exists() else []
    common = {**provenance_fields("S8_final_render_and_validation", final_inputs, final_outputs), "validator": "s8_final_render_and_validation"}
    write_json(
        plan_dir(project_dir) / "final_render_log.json",
        {
            **common,
            "ffmpeg_command": " ".join(ffmpeg_command or []),
            "base_clock_source": "base_plate",
            "overlay_duration_policy": "pad_or_trim_to_required_interval",
            "motion_overlay_count": len(motion_specs or []),
            "overlay_inputs": [
                {"shot_id": spec.get("shot_id"), "covered_shot_ids": spec.get("covered_shot_ids") or [], "start": spec.get("start"), "end": spec.get("end"), "pattern": str(spec.get("pattern")), "compositing_mode": spec.get("compositing_mode")}
                for spec in (motion_specs or [])
            ],
            "shortest_used": False,
            "video_duration_before_mux": video_before,
            "audio_duration_before_mux": audio_before,
            "final_video_stream_duration": final_video_duration,
            "final_audio_stream_duration": final_audio_duration,
            "last_video_frame_timestamp": last_ts,
            "failure_codes": [item["code"] for item in failures],
        },
    )
    metadata_payload = {
        **common,
        "probe_source": "ffprobe_show_streams_show_frames",
        "container_duration": to_float(final_meta.get("container_duration")) if isinstance(final_meta, dict) else 0,
        "video_stream_duration": final_video_duration,
        "audio_stream_duration": final_audio_duration,
        "last_video_frame_timestamp": last_ts,
        "resolution": final_meta.get("resolution") if isinstance(final_meta, dict) else {},
        "fps": final_meta.get("fps") if isinstance(final_meta, dict) else 0,
    }
    write_json(plan_dir(project_dir) / "final_video_metadata.json", metadata_payload)
    write_json(plan_dir(project_dir) / "final_stream_probe.json", {**common, **stream_probe})


def stream_probe_payload(video: Path) -> dict[str, Any]:
    payload, _ = ffprobe_json(video)
    if not isinstance(payload, dict):
        return {}
    streams = payload.get("streams") or []
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), {})
    return {
        "video_stream_duration": to_float(video_stream.get("duration") or payload.get("format", {}).get("duration")),
        "audio_stream_duration": to_float(audio_stream.get("duration") or payload.get("format", {}).get("duration")),
        "video_codec": video_stream.get("codec_name") or "",
        "audio_codec": audio_stream.get("codec_name") or "",
    }


def last_video_frame_timestamp(video: Path) -> float:
    ffprobe = os.environ.get("FFPROBE") or shutil.which("ffprobe")
    if not ffprobe or not video.exists():
        return 0
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries", "frame=best_effort_timestamp_time,pkt_pts_time", "-of", "csv=p=0", str(video)]
    result = run_cmd(cmd)
    last = 0.0
    for line in result.stdout.splitlines():
        for part in line.split(","):
            try:
                value = float(part)
            except ValueError:
                continue
            last = max(last, value)
    return last


def extract_final_frames(project_dir: Path, final_path: Path) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    metadata, _ = media_metadata(final_path)
    duration = to_float(metadata.get("container_duration")) if isinstance(metadata, dict) else 0
    frame_sets = {
        "final_qc_frames": [0.1, duration / 2, max(0.1, duration - 0.5), max(0.1, duration - 0.1)],
        "final_title_frames": [0.1, min(duration / 2, 1.0), min(max(duration - 0.1, 0.1), 2.0)],
        "final_text_layout_frames": [0.2, duration / 2, max(0.1, duration - 0.3)],
    }
    for dirname, times in frame_sets.items():
        directory = output_dir(project_dir) / "qc" / dirname
        reset_dir(directory)
        names = QC_NAMES if dirname == "final_qc_frames" else ["start", "mid", "end"]
        for name, timestamp in zip(names, times):
            if not extract_frame(final_path, timestamp, directory / f"{name}.png"):
                failures.append(failure(f"missing_{dirname}_{name}", f"Could not extract {dirname}/{name}."))
    failures.extend(extract_motion_frames(project_dir, final_path))
    failures.extend(extract_talking_head_anchor_frames(project_dir, final_path))
    return failures


def extract_motion_frames(project_dir: Path, final_path: Path) -> list[dict[str, str]]:
    failures = []
    directory = output_dir(project_dir) / "qc" / "final_motion_frames"
    reset_dir(directory)
    layers = read_json(plan_dir(project_dir) / "motion_layers.json", {}).get("layers") or []
    for layer in layers if isinstance(layers, list) else []:
        shot_id = str(layer.get("shot_id") or "motion")
        intervals = layer.get("required_intervals") or []
        if not intervals:
            continue
        interval = intervals[0]
        start = to_float(interval.get("start"))
        end = to_float(interval.get("end"))
        for name, ts in [("start", start), ("mid", (start + end) / 2), ("end", max(start, end - 0.05))]:
            target = directory / f"{shot_id}_{name}.png"
            if not extract_frame(final_path, ts, target):
                failures.append(failure("missing_final_motion_frame", f"Could not extract final motion frame {target.name}."))
    return failures


def extract_talking_head_anchor_frames(project_dir: Path, final_path: Path) -> list[dict[str, str]]:
    failures = []
    directory = output_dir(project_dir) / "qc" / "final_talking_head_anchor_frames"
    reset_dir(directory)
    rows = read_manifest(plan_dir(project_dir) / "edit_manifest.csv")
    final_row = next((row for row in rows if row.get("is_final_conclusion") == "true"), None)
    if not final_row:
        return [failure("missing_final_conclusion_anchor_interval", "No final conclusion anchor row exists.")]
    start = to_float(final_row.get("start"))
    end = to_float(final_row.get("end"))
    for name, ts in [("start", start), ("mid", (start + end) / 2), ("end", max(start, end - 0.05))]:
        target = directory / f"{name}.png"
        if not extract_frame(final_path, ts, target):
            failures.append(failure("missing_final_talking_head_anchor_frame", f"Could not extract talking head anchor {name}."))
    return failures


def build_edit_package(project_dir: Path) -> list[dict[str, str]]:
    failures = []
    package = output_dir(project_dir) / "edit_package"
    reset_dir(package)
    files = [
        output_dir(project_dir) / "base_plate.mp4",
        output_dir(project_dir) / "final.mp4",
        output_dir(project_dir) / "subtitles.srt",
        output_dir(project_dir) / "subtitles.ass",
        plan_dir(project_dir) / "edit_manifest.csv",
        plan_dir(project_dir) / "final_render_log.json",
        plan_dir(project_dir) / "final_video_metadata.json",
        project_dir / "assets" / "metadata" / "asset_manifest.json",
    ]
    for source in files:
        if source.exists():
            shutil.copy2(source, package / source.name)
    layers = read_json(plan_dir(project_dir) / "motion_layers.json", {}).get("layers") or []
    motion_dir = package / "motion_artifacts"
    motion_dir.mkdir(parents=True, exist_ok=True)
    for layer in layers if isinstance(layers, list) else []:
        seq = Path(str(layer.get("png_sequence_dir") or ""))
        if seq.exists() and seq.is_dir():
            dest = motion_dir / seq.name
            shutil.copytree(seq, dest, dirs_exist_ok=True)
    media_files = [path for path in package.rglob("*") if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".webm", ".png"}]
    if not media_files:
        failures.append(failure("edit_package_missing_real_media_layers", "edit package must contain real media layers, not only metadata."))
    return failures


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def validate_final_outputs(project_dir: Path) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    final_path = output_dir(project_dir) / "final.mp4"
    if not final_path.exists() or final_path.stat().st_size <= 0:
        failures.append(failure("missing_final_mp4", "output/final.mp4 is missing or empty."))
    metadata = read_json(plan_dir(project_dir) / "final_video_metadata.json", {})
    render_log = read_json(plan_dir(project_dir) / "final_render_log.json", {})
    if metadata.get("generated_by") != "short_video_engine" or metadata.get("probe_source") != "ffprobe_show_streams_show_frames":
        failures.append(failure("untrusted_final_video_metadata", "final_video_metadata must come from engine ffprobe/show_frames."))
    if to_float(metadata.get("video_stream_duration")) <= 0 or to_float(metadata.get("audio_stream_duration")) <= 0:
        failures.append(failure("final_metadata_container_duration_only", "final_video_metadata must include positive video/audio stream durations."))
    tolerance = to_float(load_contract("final_video_contract.json").get("timing_tolerance_sec") or 0.25)
    video_duration = to_float(render_log.get("final_video_stream_duration") or metadata.get("video_stream_duration"))
    audio_duration = to_float(render_log.get("final_audio_stream_duration") or metadata.get("audio_stream_duration"))
    if video_duration + tolerance < audio_duration:
        failures.append(failure("final_video_stream_shorter_than_audio", "Final video stream is shorter than audio stream."))
    if to_float(render_log.get("last_video_frame_timestamp")) + tolerance < audio_duration:
        failures.append(failure("last_video_frame_before_audio_end", "Last video frame timestamp is before audio end."))
    if render_log.get("shortest_used") is True and to_float(render_log.get("video_duration_before_mux")) + tolerance < to_float(render_log.get("audio_duration_before_mux")):
        failures.append(failure("dangerous_shortest_used", "-shortest is forbidden unless video before mux covers oral audio."))
    required_motion_ids = {
        str(shot.get("shot_id") or "")
        for shot in (read_json(plan_dir(project_dir) / "shot_plan.json", {}).get("shots") or [])
        if isinstance(shot, dict) and shot.get("motion_overlay_required") and shot.get("shot_id")
    }
    covered_motion_ids = set()
    for item in render_log.get("overlay_inputs") or []:
        if isinstance(item, dict):
            covered_motion_ids.update(str(shot_id) for shot_id in (item.get("covered_shot_ids") or []) if str(shot_id).strip())
            if item.get("shot_id"):
                covered_motion_ids.add(str(item.get("shot_id")))
    if required_motion_ids and (required_motion_ids - covered_motion_ids):
        failures.append(failure("missing_final_motion_overlay_inputs", "Final render did not composite every required transparent motion overlay."))
    for item in render_log.get("overlay_inputs") or []:
        if isinstance(item, dict) and item.get("compositing_mode") != "transparent_rgba_overlay":
            failures.append(failure("final_motion_overlay_not_transparent", "Final motion overlay input must use transparent RGBA compositing."))
    failures.extend(validate_final_frame_dirs(project_dir))
    failures.extend(validate_edit_package(project_dir))
    return failures


def validate_final_frame_dirs(project_dir: Path) -> list[dict[str, str]]:
    failures = []
    required = {
        "final_qc_frames": ["start", "mid", "end", "tail"],
        "final_title_frames": ["start", "mid", "end"],
        "final_text_layout_frames": ["start", "mid", "end"],
        "final_talking_head_anchor_frames": ["start", "mid", "end"],
    }
    for dirname, names in required.items():
        directory = output_dir(project_dir) / "qc" / dirname
        for name in names:
            path = directory / f"{name}.png"
            if not path.exists() or path.stat().st_size <= 0:
                failures.append(failure(f"missing_{dirname}_{name}", f"Missing final frame evidence {dirname}/{name}."))
    if motion_required(project_dir):
        motion_dir = output_dir(project_dir) / "qc" / "final_motion_frames"
        if not motion_dir.exists() or len(list(motion_dir.glob("*.png"))) < 3:
            failures.append(failure("missing_final_motion_frames", "Required final motion frames are missing."))
    return failures


def validate_edit_package(project_dir: Path) -> list[dict[str, str]]:
    package = output_dir(project_dir) / "edit_package"
    if not package.exists():
        return [failure("missing_edit_package", "output/edit_package is missing.")]
    media = [path for path in package.rglob("*") if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".webm", ".png"}]
    if not media:
        return [failure("edit_package_missing_real_media_layers", "edit package contains no real media layers.")]
    return []
