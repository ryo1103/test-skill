#!/usr/bin/env python3
"""Audit B-roll source uniqueness and playback ranges."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from workflow_audit_lib import (
    clean_text,
    fail,
    is_broll_scene,
    load_asset_records,
    meaningful_rows,
    plan_dir,
    read_csv,
    record_asset_key,
    row_duration,
    to_float,
    truthy,
    write_json,
)


UNIQUE_KEYS = [
    "source_url",
    "direct_download_url",
    "provider_asset_id",
    "original_file_page",
    "cached_source_file",
    "local_source_clip",
    "asset_key",
]


def find_record(records: list[dict[str, Any]], asset_key: str) -> dict[str, Any]:
    for record in records:
        if asset_key and asset_key == record_asset_key(record):
            return record
    return {}


def is_broll_row(row: dict[str, Any]) -> bool:
    text = " ".join(str(row.get(key, "") or "") for key in ("visual_mode", "scene_type", "source_segments", "asset_key"))
    return is_broll_scene(text)


def is_still_fallback(row: dict[str, Any], record: dict[str, Any]) -> bool:
    text = " ".join(str(row.get(key, "") or "") for key in ("visual_mode", "playback_policy", "usage", "asset_key")).lower()
    text += " " + " ".join(str(record.get(key, "") or "") for key in ("usage", "usage_type", "media_type", "file_path", "path")).lower()
    return any(token in text for token in ("still", "image", "photo", "screenshot", "fallback_image")) or truthy(row.get("approved_still_fallback"))


def row_source_keys(row: dict[str, Any], record: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in UNIQUE_KEYS:
        value = clean_text(row.get(key)) or clean_text(record.get(key))
        if value:
            values[key] = value
    if clean_text(row.get("asset_key")):
        values["asset_key"] = clean_text(row.get("asset_key"))
    return values


def audit(project_dir: Path) -> int:
    rows = meaningful_rows(read_csv(plan_dir(project_dir) / "edit_manifest.csv"))
    records = load_asset_records(project_dir)
    broll_rows = [row for row in rows if is_broll_row(row)]
    uniqueness_failures: list[dict] = []
    playback_failures: list[dict] = []
    used_source_keys: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    ranges_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    still_fallbacks: list[dict[str, Any]] = []

    if not rows:
        playback_failures.append(fail("source_playback", "missing_edit_manifest", "edit_manifest.csv is missing or has no rows.", "Create a cue-level edit_manifest.csv before source usage audit."))
    if not broll_rows:
        uniqueness_failures.append(fail("source_uniqueness", "no_broll_events", "No B-roll rows were found in edit_manifest.csv.", "Generate B-roll timeline entries before rendering."))

    for index, row in enumerate(broll_rows, start=2):
        shot_id = row.get("shot_id") or row.get("shot") or f"row_{index}"
        asset_key = clean_text(row.get("asset_key"))
        record = find_record(records, asset_key)
        still = is_still_fallback(row, record)
        keys = row_source_keys(row, record)
        used_source_keys.append({"shot_id": shot_id, "asset_key": asset_key, "keys": keys})

        if still:
            reason = clean_text(row.get("reason") or row.get("fallback_reason") or record.get("reason") or record.get("license_or_note"))
            source_url = clean_text(row.get("source_url") or record.get("source_url"))
            duration = row_duration(row)
            if not truthy(row.get("approved_still_fallback")) or not reason or not source_url or duration <= 0:
                playback_failures.append(fail("source_playback", "invalid_still_fallback_record", f"{shot_id} is a still/image fallback but lacks approval, reason, source_url, or duration.", "Document approved_still_fallback=true, reason, source_url, and duration.", shot_id=shot_id))
            still_fallbacks.append({"shot_id": shot_id, "asset_key": asset_key, "source_url": source_url, "reason": reason, "duration": duration, "approved_still_fallback": truthy(row.get("approved_still_fallback"))})
            continue

        if not asset_key:
            playback_failures.append(fail("source_playback", "missing_asset_key", f"{shot_id} is missing asset_key.", "Record the selected asset_key for every B-roll event.", shot_id=shot_id))
        for required in ("source_in", "source_out", "start", "end", "playback_policy"):
            if not clean_text(row.get(required)):
                playback_failures.append(fail("source_playback", "missing_playback_field", f"{shot_id} is missing {required}.", "Record asset_key, source_in/source_out, timeline start/end, and playback_policy for every B-roll event.", shot_id=shot_id, field=required))

        policy = str(row.get("playback_policy", "") or "").lower()
        if any(token in policy for token in ("loop", "stream_loop", "restart", "repeat")):
            playback_failures.append(fail("source_playback", "loop_or_restart_policy", f"{shot_id} playback_policy indicates loop/restart/repeat.", "Replace with one continuous non-looped source trim.", shot_id=shot_id, playback_policy=policy))

        source_in = to_float(row.get("source_in"), -1)
        source_out = to_float(row.get("source_out"), -1)
        start = to_float(row.get("start"), -1)
        end = to_float(row.get("end"), -1)
        duration = row_duration(row)
        if source_in < 0 or source_out <= source_in:
            playback_failures.append(fail("source_playback", "invalid_source_range", f"{shot_id} has invalid source_in/source_out.", "Use a positive continuous trim range for the source clip.", shot_id=shot_id, source_in=source_in, source_out=source_out))
        if start < 0 or end <= start:
            playback_failures.append(fail("source_playback", "invalid_timeline_range", f"{shot_id} has invalid start/end.", "Record a valid timeline range.", shot_id=shot_id, start=start, end=end))
        if source_out > source_in and duration > (source_out - source_in) + 0.05:
            playback_failures.append(fail("source_playback", "output_longer_than_source_trim", f"{shot_id} output duration exceeds its selected source trim.", "Shorten the output event or select a longer non-looped source trim.", shot_id=shot_id, duration=duration, source_trim=source_out - source_in))

        source_id = asset_key or "|".join(f"{key}:{value}" for key, value in sorted(keys.items()))
        ranges_by_asset[source_id].append({"shot_id": shot_id, "source_in": source_in, "source_out": source_out, "start": start, "end": end})

        for key, value in keys.items():
            pair = (key, value)
            if pair in seen:
                duplicate = {"key": key, "value": value, "first": seen[pair].get("shot_id"), "duplicate": shot_id}
                duplicates.append(duplicate)
                uniqueness_failures.append(fail("source_uniqueness", "duplicate_broll_source_key", f"{shot_id} repeats B-roll source key {key}.", "Replace the later source with an unused asset or document explicit user approval.", **duplicate))
            else:
                seen[pair] = {"shot_id": shot_id}

    for asset_key, ranges in ranges_by_asset.items():
        if len(ranges) > 1:
            playback_failures.append(fail("source_playback", "multi_range_source_use", f"{asset_key} is used in multiple B-roll timeline ranges.", "Use one continuous trim once, or replace later occurrences with unique assets.", asset_key=asset_key, ranges=ranges))
        sorted_ranges = sorted(ranges, key=lambda item: item["start"])
        previous_out = None
        previous_range = None
        for item in sorted_ranges:
            if previous_out is not None and item["source_in"] < previous_out - 0.05:
                playback_failures.append(fail("source_playback", "backward_seek_source", f"{asset_key} seeks backward after earlier playback.", "Replace the later event or choose a single forward continuous range.", asset_key=asset_key, previous=previous_range, current=item))
            previous_out = item["source_out"]
            previous_range = item

    uniqueness_status = "failed" if uniqueness_failures else "passed"
    playback_status = "failed" if playback_failures else "passed"

    write_json(
        plan_dir(project_dir) / "source_uniqueness_audit.json",
        {
            "status": uniqueness_status,
            "used_source_keys": used_source_keys,
            "duplicates": duplicates,
            "checks": UNIQUE_KEYS,
            "failures": uniqueness_failures,
            "warnings": [],
            "remediation_required": bool(uniqueness_failures),
        },
    )
    write_json(
        plan_dir(project_dir) / "source_playback_audit.json",
        {
            "status": playback_status,
            "source_playback_ranges": dict(ranges_by_asset),
            "looped_sources": [failure for failure in playback_failures if failure["code"] == "loop_or_restart_policy"],
            "restarted_sources": [failure for failure in playback_failures if failure["code"] == "loop_or_restart_policy"],
            "backward_seek_sources": [failure for failure in playback_failures if failure["code"] == "backward_seek_source"],
            "multi_range_sources": [failure for failure in playback_failures if failure["code"] == "multi_range_source_use"],
            "repeated_ranges": [failure for failure in playback_failures if failure["code"] == "multi_range_source_use"],
            "overlong_output_ranges": [failure for failure in playback_failures if failure["code"] == "output_longer_than_source_trim"],
            "approved_still_fallbacks": still_fallbacks,
            "failures": playback_failures,
            "warnings": [],
            "remediation_required": bool(playback_failures),
        },
    )
    print(plan_dir(project_dir) / "source_uniqueness_audit.json")
    print(plan_dir(project_dir) / "source_playback_audit.json")
    print(f"source_uniqueness: {uniqueness_status}")
    print(f"source_playback: {playback_status}")
    return 0 if uniqueness_status == "passed" and playback_status == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit B-roll source uniqueness and playback ranges.")
    parser.add_argument("project_dir")
    args = parser.parse_args()
    return audit(Path(args.project_dir).expanduser().resolve())


if __name__ == "__main__":
    sys.exit(main())
