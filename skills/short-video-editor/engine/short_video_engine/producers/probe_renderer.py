from __future__ import annotations

import csv
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..contracts import load_contract, read_json, write_json
from ..paths import output_dir, plan_dir, stage_reports_dir
from ..stage_result import failure
from ..stages.common import media_metadata


PREVIOUS_STAGES = ["S0_intake", "S1_script_and_subtitles", "S1_5_subtitle_layout_planning", "S2_visual_plan", "S3_asset_sourcing", "S4_base_timeline", "S5_motion_overlay", "S6_text_layout"]
REPRESENTATIVE_BASE = ["talking_head", "broll", "title", "subtitle", "final_conclusion"]


def ffmpeg_path() -> str | None:
    return os.environ.get("FFMPEG") or shutil.which("ffmpeg")


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def read_manifest(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle)]


def render_probe(project_dir: Path) -> tuple[Path, Path, Path, list[dict[str, str]]]:
    probe_path = output_dir(project_dir) / "qc" / "probe_render.mp4"
    frames_dir = output_dir(project_dir) / "qc" / "probe_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for path in frames_dir.iterdir():
        if path.is_file():
            path.unlink()
    failures = []
    stage_status = previous_stage_status(project_dir)
    if any(item["status"] != "PASS" for item in stage_status):
        failures.append(failure("previous_production_slice_not_passed", "S0-S6 are not all PASS, so S7 cannot PASS.", "Fix earlier stages first."))
    failures.extend(render_probe_video(project_dir, probe_path))
    frames = extract_representative_frames(project_dir, probe_path, frames_dir)
    failures.extend(validate_representative_frames(project_dir, frames))
    coverage_report = build_coverage_report(project_dir, probe_path, frames)
    failures.extend(coverage_failures(coverage_report))
    process_path = plan_dir(project_dir) / "process_validation_report.json"
    coverage_path = plan_dir(project_dir) / "timeline_coverage_report.json"
    status = "PASS" if not failures else "FINAL_BLOCKED"
    write_json(
        process_path,
        {
            "generated_by": "short_video_engine",
            "validator": "s7_process_validation",
            "status": status,
            "production_slices": stage_status,
            "representative_frames": frames,
            "failure_codes": [item["code"] for item in failures],
            "failures": failures,
        },
    )
    write_json(coverage_path, {**coverage_report, "generated_by": "short_video_engine", "status": status})
    return probe_path, process_path, coverage_path, failures


def previous_stage_status(project_dir: Path) -> list[dict[str, str]]:
    result = []
    for stage in PREVIOUS_STAGES:
        payload = read_json(stage_reports_dir(project_dir) / f"{stage}.json", {})
        result.append({"stage": stage, "status": str(payload.get("status") or "not_run"), "generated_by": str(payload.get("generated_by") or "")})
    return result


def render_probe_video(project_dir: Path, probe_path: Path) -> list[dict[str, str]]:
    failures = []
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        return [failure("ffmpeg_not_found", "ffmpeg is required for probe render.")]
    base = output_dir(project_dir) / "base_plate.mp4"
    subtitles = output_dir(project_dir) / "subtitles.ass"
    title = output_dir(project_dir) / "title_overlay.ass"
    if not base.exists():
        return [failure("missing_base_plate", "output/base_plate.mp4 is missing.")]
    if not subtitles.exists():
        return [failure("missing_subtitles_ass", "output/subtitles.ass is missing.")]
    if not title.exists():
        return [failure("missing_title_overlay", "output/title_overlay.ass is missing.")]
    from .final_renderer import build_final_ffmpeg_command, motion_overlay_specs

    cmd = build_final_ffmpeg_command(ffmpeg, base, title, subtitles, probe_path, motion_overlay_specs(project_dir))
    result = run_cmd(cmd)
    if result.returncode != 0:
        failures.append(failure("probe_render_failed", result.stderr[-1200:] or "ffmpeg probe render failed."))
    return failures


def escape_filter_path(path: Path) -> str:
    text = str(path)
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def extract_frame(video: Path, timestamp: float, output: Path) -> bool:
    ffmpeg = ffmpeg_path()
    if not ffmpeg or not video.exists():
        return False
    cmd = [ffmpeg, "-y", "-ss", f"{max(0.0, timestamp):.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(output)]
    return run_cmd(cmd).returncode == 0 and output.exists() and output.stat().st_size > 0


def extract_representative_frames(project_dir: Path, probe_path: Path, frames_dir: Path) -> dict[str, str]:
    rows = read_manifest(plan_dir(project_dir) / "edit_manifest.csv")
    frames: dict[str, str] = {}
    pick_and_extract(rows, probe_path, frames_dir, "talking_head", lambda row: row.get("visual_mode") == "talking_head_fullscreen", frames)
    pick_and_extract(rows, probe_path, frames_dir, "broll", lambda row: row.get("visual_mode") == "broll_fullscreen", frames)
    pick_and_extract(rows, probe_path, frames_dir, "final_conclusion", lambda row: row.get("is_final_conclusion") == "true", frames)
    extract_frame(probe_path, 0.2, frames_dir / "title.png")
    frames["title"] = str(frames_dir / "title.png")
    subtitle_time = first_subtitle_time(project_dir)
    extract_frame(probe_path, subtitle_time, frames_dir / "subtitle.png")
    frames["subtitle"] = str(frames_dir / "subtitle.png")
    motion = motion_frame(project_dir)
    if motion:
        target = frames_dir / "motion.png"
        shutil.copy2(motion, target)
        frames["motion"] = str(target)
    return frames


def pick_and_extract(rows: list[dict[str, str]], probe_path: Path, frames_dir: Path, name: str, predicate, frames: dict[str, str]) -> None:
    row = next((item for item in rows if predicate(item)), None)
    if not row:
        return
    timestamp = (to_float(row.get("start")) + to_float(row.get("end"))) / 2
    out = frames_dir / f"{name}.png"
    extract_frame(probe_path, timestamp, out)
    frames[name] = str(out)


def first_subtitle_time(project_dir: Path) -> float:
    payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
    cues = payload.get("cues") if isinstance(payload, dict) else []
    if isinstance(cues, list) and cues:
        return max(0.0, to_float(cues[0].get("start")) + 0.1)
    return 0.2


def motion_frame(project_dir: Path) -> Path | None:
    payload = read_json(plan_dir(project_dir) / "motion_layers.json", {})
    layers = payload.get("layers") if isinstance(payload, dict) else []
    if not isinstance(layers, list):
        return None
    for layer in layers:
        evidence = layer.get("frame_evidence") if isinstance(layer, dict) else {}
        if isinstance(evidence, dict) and evidence.get("mid"):
            path = Path(str(evidence["mid"]))
            if path.exists() and path.stat().st_size > 0:
                return path
    return None


def validate_representative_frames(project_dir: Path, frames: dict[str, str]) -> list[dict[str, str]]:
    failures = []
    required = list(REPRESENTATIVE_BASE)
    if motion_required(project_dir):
        required.append("motion")
    for name in required:
        path = Path(str(frames.get(name) or ""))
        if not path.exists() or path.stat().st_size <= 0:
            failures.append(failure(f"missing_representative_{name}_frame", f"Representative {name} frame is missing or empty."))
    return failures


def motion_required(project_dir: Path) -> bool:
    payload = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    shots = payload.get("shots") if isinstance(payload, dict) else []
    return any(isinstance(shot, dict) and shot.get("motion_overlay_required") for shot in shots or [])


def build_coverage_report(project_dir: Path, probe_path: Path, frames: dict[str, str]) -> dict[str, Any]:
    intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
    oral_duration = to_float(intake.get("audio_stream_duration") or intake.get("audio_duration"))
    base_meta, _ = media_metadata(output_dir(project_dir) / "base_plate.mp4") if (output_dir(project_dir) / "base_plate.mp4").exists() else (None, "")
    base_duration = to_float(base_meta.get("container_duration")) if isinstance(base_meta, dict) else 0
    tolerance = to_float(load_contract("final_video_contract.json").get("timing_tolerance_sec") or 0.25)
    rows = read_manifest(plan_dir(project_dir) / "edit_manifest.csv")
    cues_payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
    cues = cues_payload.get("cues") if isinstance(cues_payload, dict) else []
    layers_payload = read_json(plan_dir(project_dir) / "motion_layers.json", {})
    layers = layers_payload.get("layers") if isinstance(layers_payload, dict) and isinstance(layers_payload.get("layers"), list) else []
    return {
        "oral_audio_duration_sec": oral_duration,
        "base_plate_duration_sec": base_duration,
        "base_plate_covers_oral_audio": abs(base_duration - oral_duration) <= tolerance if oral_duration else False,
        "title_covers_required_interval": (output_dir(project_dir) / "title_overlay.ass").exists() and bool(frames.get("title")),
        "subtitle_cue_count": len(cues) if isinstance(cues, list) else 0,
        "subtitle_cues_cover_required_intervals": subtitle_coverage_ok(cues, oral_duration, tolerance),
        "motion_required": motion_required(project_dir),
        "motion_layers_cover_required_intervals": motion_coverage_ok(layers) if motion_required(project_dir) else True,
        "final_conclusion_anchor_interval_exists": any(row.get("is_final_conclusion") == "true" and row.get("visual_mode") == "talking_head_fullscreen" for row in rows),
        "probe_render_exists": probe_path.exists() and probe_path.stat().st_size > 0,
    }


def subtitle_coverage_ok(cues: Any, duration: float, tolerance: float) -> bool:
    if not isinstance(cues, list) or not cues:
        return False
    first = to_float(cues[0].get("start"))
    last = to_float(cues[-1].get("end"))
    return first <= tolerance and (not duration or abs(last - duration) <= tolerance)


def motion_coverage_ok(layers: list[dict[str, Any]]) -> bool:
    if not layers:
        return False
    for layer in layers:
        required = layer.get("required_intervals") or []
        actual = layer.get("actual_intervals") or []
        if not required or not actual:
            return False
        for req in required:
            covered = any(to_float(act.get("start")) <= to_float(req.get("start")) and to_float(act.get("end")) >= to_float(req.get("end")) for act in actual)
            if not covered:
                return False
    return True


def coverage_failures(report: dict[str, Any]) -> list[dict[str, str]]:
    checks = {
        "base_plate_covers_oral_audio": "base_plate_coverage_gap",
        "title_covers_required_interval": "title_coverage_gap",
        "subtitle_cues_cover_required_intervals": "subtitle_coverage_gap",
        "motion_layers_cover_required_intervals": "motion_coverage_gap",
        "final_conclusion_anchor_interval_exists": "missing_final_conclusion_anchor_interval",
        "probe_render_exists": "missing_probe_render",
    }
    return [failure(code, f"Timeline coverage check failed: {name}.") for name, code in checks.items() if not report.get(name)]


def to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
