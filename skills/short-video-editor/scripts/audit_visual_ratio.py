#!/usr/bin/env python3
"""Compute and audit visual mix ratios from the render timeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from workflow_audit_lib import (
    fail,
    is_broll_scene,
    is_hyperframe_scene,
    is_talking_scene,
    load_asset_records,
    meaningful_rows,
    percentage,
    plan_dir,
    read_csv,
    read_json,
    resolve_asset_path,
    row_duration,
    shot_id_from_item,
    to_float,
    write_audit,
)


def classify_item(item: dict[str, Any]) -> str:
    text = " ".join(
        str(item.get(key, "") or "")
        for key in ("visual_mode", "scene_type", "renderer", "digital_human_presence", "shot_id", "shot")
    )
    if is_hyperframe_scene(text):
        return "hyperframe"
    if is_talking_scene(text) or str(item.get("digital_human_presence", "")).lower() == "fullscreen":
        return "digital_human"
    if is_broll_scene(text):
        return "broll"
    return "other"


def rows_from_manifest(project_dir: Path) -> list[dict[str, Any]]:
    rows = meaningful_rows(read_csv(plan_dir(project_dir) / "edit_manifest.csv"))
    return [row for row in rows if row_duration(row) > 0]


def rows_from_shot_plan(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    shots = payload.get("shots", []) if isinstance(payload, dict) else []
    rows: list[dict[str, Any]] = []
    start = 0.0
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        duration = to_float(shot.get("duration_sec") or shot.get("duration"), 0.0)
        if duration <= 0:
            continue
        row = dict(shot)
        row["start"] = start
        row["end"] = start + duration
        row["duration"] = duration
        row["shot_id"] = shot_id_from_item(shot)
        rows.append(row)
        start += duration
    return rows


def source_exists_for_row(project_dir: Path, row: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    for key in ("source_segments", "asset_key", "broll_base_asset"):
        if resolve_asset_path(project_dir, row.get(key), records):
            return True
    return False


def max_continuous(rows: list[dict[str, Any]], target: str) -> float:
    current = 0.0
    maximum = 0.0
    for row in rows:
        duration = row_duration(row)
        if classify_item(row) == target:
            current += duration
            maximum = max(maximum, current)
        else:
            current = 0.0
    return maximum


def audit(project_dir: Path) -> int:
    failures: list[dict] = []
    warnings: list[dict] = []
    records = load_asset_records(project_dir)
    rows = rows_from_manifest(project_dir)
    source = "edit_manifest.csv"
    if not rows:
        rows = rows_from_shot_plan(project_dir)
        source = "shot_plan.json"

    if not rows:
        failures.append(fail("visual_ratio", "missing_timeline_rows", "No timed edit_manifest rows or shot_plan durations were found.", "Create a cue-level edit manifest with real durations before ratio audit."))

    totals = {"digital_human": 0.0, "broll": 0.0, "hyperframe": 0.0, "other": 0.0}
    missing_broll_assets: list[dict[str, Any]] = []
    total = 0.0
    classified_rows: list[dict[str, Any]] = []
    for row in rows:
        duration = row_duration(row)
        if duration <= 0:
            continue
        kind = classify_item(row)
        totals[kind] = totals.get(kind, 0.0) + duration
        total += duration
        classified_rows.append({"shot_id": row.get("shot_id") or row.get("shot") or "", "class": kind, "duration": duration})
        if kind == "broll" and not source_exists_for_row(project_dir, row, records):
            missing_broll_assets.append({"shot_id": row.get("shot_id") or row.get("shot") or "", "asset_key": row.get("asset_key") or "", "source_segments": row.get("source_segments") or ""})

    if total <= 0:
        failures.append(fail("visual_ratio", "zero_total_duration", "Total planned duration is zero.", "Add real start/end/duration values before ratio audit."))

    digital_ratio = percentage(totals["digital_human"], total)
    broll_ratio = percentage(totals["broll"], total)
    hyper_ratio = percentage(totals["hyperframe"], total)
    continuous_digital = max_continuous(rows, "digital_human")
    continuous_hyper = max_continuous(rows, "hyperframe")

    if total > 0 and not 0.15 <= digital_ratio <= 0.28:
        failures.append(fail("visual_ratio", "digital_human_ratio_out_of_range", f"Full-screen digital human ratio is {digital_ratio:.1%}, expected 15%-28%.", "Shorten or add full-screen digital-human pivots to match the style contract.", ratio=digital_ratio))
    if total > 0 and not 0.50 <= broll_ratio <= 0.70:
        failures.append(fail("visual_ratio", "broll_ratio_out_of_range", f"B-roll/screen/image-motion ratio is {broll_ratio:.1%}, expected 50%-70%.", "Source more B-roll, shorten nonessential digital-human/HyperFrame spans, or revise the timeline.", ratio=broll_ratio))
    if total > 0 and not 0.08 <= hyper_ratio <= 0.18:
        failures.append(fail("visual_ratio", "hyperframe_ratio_out_of_range", f"HyperFrame/AE ratio is {hyper_ratio:.1%}, expected 8%-18%.", "Downgrade weak HyperFrames or add only justified key logic/data motion shots.", ratio=hyper_ratio))
    if continuous_digital > 15:
        failures.append(fail("visual_ratio", "continuous_digital_human_too_long", f"Continuous full-screen digital-human duration is {continuous_digital:.2f}s, limit is 15s.", "Cut to B-roll or shorten the host segment.", duration=continuous_digital))
    if continuous_hyper > 15:
        failures.append(fail("visual_ratio", "continuous_hyperframe_too_long", f"Continuous HyperFrame/AE duration is {continuous_hyper:.2f}s, limit is 15s.", "Break the motion section with B-roll or downgrade adjacent shots.", duration=continuous_hyper))
    if missing_broll_assets:
        failures.append(fail("visual_ratio", "broll_ratio_not_backed_by_existing_assets", "Some B-roll duration is not backed by selected local assets.", "Run asset sourcing and update edit_manifest.csv with existing selected assets.", missing=missing_broll_assets[:20]))

    status = "failed" if failures else "passed"
    payload = {
        "total_duration_sec": round(total, 3),
        "digital_human_fullscreen_sec": round(totals["digital_human"], 3),
        "digital_human_ratio": f"{digital_ratio:.2%}",
        "broll_or_screen_recording_sec": round(totals["broll"], 3),
        "broll_ratio": f"{broll_ratio:.2%}",
        "hyperframe_sec": round(totals["hyperframe"], 3),
        "hyperframe_ratio": f"{hyper_ratio:.2%}",
        "continuous_digital_human_max_sec": round(continuous_digital, 3),
        "continuous_hyperframe_max_sec": round(continuous_hyper, 3),
        "computed_from": source,
        "classified_rows": classified_rows,
        "rule_check": [failure["code"] for failure in failures],
    }
    result = write_audit(plan_dir(project_dir) / "visual_ratio_audit.json", status, failures, warnings=warnings, **payload)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute and audit visual ratio from selected assets and timeline durations.")
    parser.add_argument("project_dir")
    args = parser.parse_args()
    return audit(Path(args.project_dir).expanduser().resolve())


if __name__ == "__main__":
    sys.exit(main())
