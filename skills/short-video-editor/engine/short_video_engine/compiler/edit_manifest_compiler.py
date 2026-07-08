from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..contracts import read_json
from ..paths import plan_dir
from ..producers.asset_materializer import distinct_passed_records, load_manifest
from ..stage_result import failure


MANIFEST_COLUMNS = [
    "shot_id",
    "unit_id",
    "subtitle_cue_ids",
    "start",
    "end",
    "duration",
    "visual_mode",
    "asset_key",
    "source_key",
    "source_url",
    "local_source_clip",
    "source_in",
    "source_out",
    "source_duration_sec",
    "playback_policy",
    "talking_head_required",
    "is_final_conclusion",
    "contains_overlay",
]


TALKING_ROLES = {"opinion", "judgment", "conclusion", "final_summary"}


def load_shots(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    shots = payload.get("shots") if isinstance(payload, dict) else []
    return [shot for shot in shots if isinstance(shot, dict)] if isinstance(shots, list) else []


def write_manifest_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in MANIFEST_COLUMNS})


def compile_edit_manifest(project_dir: Path) -> tuple[Path, list[dict[str, str]]]:
    intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
    oral_video = str(intake.get("oral_video_path") or "")
    oral_duration = float(intake.get("audio_stream_duration") or intake.get("audio_duration") or 0)
    shots = load_shots(project_dir)
    assets, asset_failures, _duplicates = distinct_passed_records(project_dir, load_manifest(project_dir))
    failures: list[dict[str, str]] = []
    if asset_failures:
        failures.append(failure("asset_manifest_has_invalid_records", "Invalid asset records cannot be used for base timeline.", "Fix S3 asset manifest first."))
    broll_assets = [asset for asset in assets if asset.get("media_class") == "video_broll"]
    broll_index = 0
    rows = []
    final_unit_id = str(shots[-1].get("unit_id")) if shots else ""
    intervals = continuous_visual_intervals(shots, oral_duration)
    for shot, interval in zip(shots, intervals):
        shot_id = str(shot.get("shot_id") or "")
        unit_id = str(shot.get("unit_id") or "")
        role = str(shot.get("narrative_role") or "").lower()
        is_final = unit_id == final_unit_id or role == "final_summary"
        start, end, duration = interval
        if duration <= 0:
            failures.append(failure("shot_missing_timing", f"Shot {shot_id} lacks positive timing.", "Regenerate S2 with subtitle timing."))
        talking_required = bool(shot.get("talking_head_required")) or role in TALKING_ROLES or is_final
        if talking_required:
            visual_mode = "talking_head_fullscreen"
            row = base_row(shot, start, end, duration, visual_mode, "", "", "", oral_video, start, end, float(intake.get("video_stream_duration") or intake.get("container_duration") or 0), "same_timecode_from_oral_video", True, is_final)
        else:
            asset = select_broll_asset(broll_assets, broll_index, duration)
            if asset is None:
                failures.append(failure("no_broll_asset_long_enough", f"No distinct B-roll asset is long enough for shot {shot_id}.", "Use a longer materialized B-roll asset or split the shot."))
                row = base_row(shot, start, end, duration, "broll_fullscreen", "", "", "", "", 0, "missing_source", False, is_final)
            else:
                broll_index += 1
                row = base_row(
                    shot,
                    start,
                    end,
                    duration,
                    "broll_fullscreen",
                    str(asset.get("asset_key") or ""),
                    str(asset.get("source_key") or ""),
                    str(asset.get("source_url") or ""),
                    str(asset.get("local_path") or ""),
                    0.0,
                    duration,
                    float(asset.get("duration_sec") or 0),
                    "normal",
                    False,
                    is_final,
                )
        rows.append(row)
    path = plan_dir(project_dir) / "edit_manifest.csv"
    write_manifest_csv(path, rows)
    return path, failures


def continuous_visual_intervals(shots: list[dict[str, Any]], oral_duration: float) -> list[tuple[float, float, float]]:
    raw = [timing_for_shot(shot) for shot in shots]
    intervals: list[tuple[float, float, float]] = []
    cursor = 0.0
    for index, timing in enumerate(raw):
        raw_start, raw_end, raw_duration = timing
        if index == 0:
            start = 0.0
        else:
            start = cursor
        if index + 1 < len(raw):
            next_start = raw[index + 1][0]
            end = next_start if next_start > start else max(raw_end, start + raw_duration)
        else:
            end = oral_duration if oral_duration > start else raw_end
        duration = max(0.0, end - start)
        intervals.append((start, end, duration))
        cursor = end
    return intervals


def timing_for_shot(shot: dict[str, Any]) -> tuple[float, float, float]:
    try:
        start = float(shot.get("start") or 0)
        end = float(shot.get("end") or 0)
        duration = float(shot.get("duration") or (end - start))
    except (TypeError, ValueError):
        return 0, 0, 0
    return start, end, duration


def select_broll_asset(assets: list[dict[str, Any]], start_index: int, duration: float) -> dict[str, Any] | None:
    for asset in assets[start_index:]:
        if float(asset.get("duration_sec") or 0) + 1e-6 >= duration:
            return asset
    return None


def base_row(shot: dict[str, Any], start: float, end: float, duration: float, visual_mode: str, asset_key: str, source_key: str, source_url: str, local_source_clip: str, source_in: float, source_out: float, source_duration: float, playback_policy: str, talking_required: bool, is_final: bool) -> dict[str, Any]:
    return {
        "shot_id": shot.get("shot_id"),
        "unit_id": shot.get("unit_id"),
        "subtitle_cue_ids": ",".join(str(item) for item in (shot.get("subtitle_cue_ids") or [])),
        "start": f"{start:.3f}",
        "end": f"{end:.3f}",
        "duration": f"{duration:.3f}",
        "visual_mode": visual_mode,
        "asset_key": asset_key,
        "source_key": source_key,
        "source_url": source_url,
        "local_source_clip": local_source_clip,
        "source_in": f"{source_in:.3f}",
        "source_out": f"{source_out:.3f}",
        "source_duration_sec": f"{source_duration:.3f}",
        "playback_policy": playback_policy,
        "talking_head_required": str(bool(talking_required)).lower(),
        "is_final_conclusion": str(bool(is_final)).lower(),
        "contains_overlay": "false",
    }
