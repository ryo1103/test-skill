#!/usr/bin/env python3
"""Audit B-roll/source acquisition before ratio planning or rendering."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from workflow_audit_lib import (
    asset_record_matches,
    clean_text,
    fail,
    is_broll_scene,
    load_asset_records,
    meaningful_rows,
    negative,
    plan_dir,
    read_csv,
    read_json,
    record_asset_key,
    resolve_asset_path,
    shot_id_from_item,
    truthy,
    write_audit,
)


BAD_BROLL_SUBSTITUTE_TOKENS = {
    "hyperframe",
    "generated",
    "generated_diagram",
    "generated_bitmap",
    "text_card",
    "placeholder",
    "placeholder_motion",
    "looped",
    "repeated",
}


def search_shots(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        shots = payload.get("shots") or payload.get("items") or []
        return [item for item in shots if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def flatten_terms(entry: dict[str, Any]) -> dict[str, list[Any]]:
    search_terms = entry.get("search_terms") if isinstance(entry.get("search_terms"), dict) else {}
    return {
        "primary_terms": entry.get("primary_terms") or search_terms.get("primary_terms") or [],
        "fallback_terms": entry.get("fallback_terms") or search_terms.get("fallback_terms") or [],
        "video_terms": entry.get("video_terms") or search_terms.get("video_terms") or [],
        "news_terms": entry.get("news_terms") or search_terms.get("news_terms") or [],
        "screen_recording_targets": entry.get("screen_recording_targets") or search_terms.get("screen_recording_targets") or [],
    }


def has_any_terms(entry: dict[str, Any]) -> bool:
    terms = flatten_terms(entry)
    return any(bool(value) for value in terms.values())


def has_shortage(entry: dict[str, Any]) -> bool:
    text = " ".join(str(entry.get(key, "") or "") for key in ("blocked_reason", "shortage_reason", "shortage_report", "reason", "notes"))
    if clean_text(text):
        return True
    if entry.get("needs_sourcing") is True and (entry.get("download_candidates") or entry.get("video_source_audit")):
        for item in entry.get("download_candidates") or []:
            if isinstance(item, dict) and clean_text(item.get("blocked_reason") or item.get("download_status") or item.get("reason")):
                return True
        for item in entry.get("video_source_audit") or []:
            if isinstance(item, dict) and clean_text(item.get("blocked_reason") or item.get("download_status") or item.get("reason")):
                return True
    return False


def selected_assets(entry: dict[str, Any]) -> list[Any]:
    values: list[Any] = []
    for key in ("selected_assets", "assets", "selected_asset", "asset_key"):
        value = entry.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value:
            values.append(value)
    return values


def selected_asset_exists(project_dir: Path, value: Any, asset_records: list[dict[str, Any]]) -> bool:
    if isinstance(value, dict):
        for key in ("path", "file_path", "local_path", "asset_key"):
            if resolve_asset_path(project_dir, value.get(key), asset_records):
                return True
        asset_key = record_asset_key(value)
        if asset_key and resolve_asset_path(project_dir, asset_key, asset_records):
            return True
        return False
    return bool(resolve_asset_path(project_dir, value, asset_records))


def item_needs_broll(item: dict[str, Any]) -> bool:
    scene = item.get("scene_type") or item.get("visual_mode") or ""
    if truthy(item.get("broll_needed")):
        return True
    if negative(item.get("broll_needed")):
        return False
    if is_broll_scene(scene):
        return True
    if truthy(item.get("ae_overlay_candidate")) and clean_text(item.get("broll_base_asset")):
        return True
    overlay = str(item.get("overlay_layer_plan") or "").lower()
    if truthy(item.get("ae_overlay_candidate")) and "standalone" not in overlay:
        return True
    return False


def collect_required_shots(project_dir: Path) -> list[dict[str, Any]]:
    shot_plan = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    required: dict[str, dict[str, Any]] = {}
    for item in search_shots(shot_plan):
        if not item_needs_broll(item):
            continue
        shot_id = shot_id_from_item(item) or f"shot_plan_{len(required) + 1}"
        required.setdefault(shot_id, {}).update(item)
        required[shot_id]["shot_id"] = shot_id

    for row in meaningful_rows(read_csv(plan_dir(project_dir) / "visual_strategy.csv")):
        if not item_needs_broll(row):
            continue
        shot_id = str(row.get("shot") or row.get("shot_id") or f"visual_{len(required) + 1}")
        existing = required.setdefault(shot_id, {"shot_id": shot_id})
        existing.update({key: value for key, value in row.items() if value})
    return list(required.values())


def local_selected_assets(project_dir: Path, shot: dict[str, Any], asset_records: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    shot_id = str(shot.get("shot_id") or shot.get("shot") or "")
    for value in (shot.get("broll_base_asset"), shot.get("asset_key")):
        path = resolve_asset_path(project_dir, value, asset_records)
        if path:
            found.append(str(path))
    for item in shot.get("assets") if isinstance(shot.get("assets"), list) else []:
        if selected_asset_exists(project_dir, item, asset_records):
            found.append(str(item if isinstance(item, str) else item.get("asset_key") or item.get("path") or item))
    for record in asset_records:
        if asset_record_matches(record, shot_id, str(shot.get("asset_key") or "")):
            for key in ("path", "file_path", "local_path"):
                path = resolve_asset_path(project_dir, record.get(key), asset_records)
                if path:
                    found.append(str(path))
    return sorted(set(found))


def find_search_entry(shot_id: str, search_entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in search_entries:
        entry_id = str(entry.get("shot_id") or entry.get("shot") or entry.get("id") or "")
        if entry_id == shot_id:
            return entry
    return None


def video_audit_has_records(project_dir: Path) -> bool:
    rows = meaningful_rows(read_csv(plan_dir(project_dir) / "video_source_audit.csv"))
    required_any = ("provider", "query", "source_url", "blocked_reason")
    return any(any(clean_text(row.get(key)) for key in required_any) for row in rows)


def audit(project_dir: Path) -> int:
    failures: list[dict] = []
    warnings: list[dict] = []
    checked: list[dict[str, Any]] = []
    selected: list[str] = []
    shortages: list[dict[str, Any]] = []

    required_shots = collect_required_shots(project_dir)
    if not required_shots:
        failures.append(fail("asset_gate", "no_broll_shots_detected", "No B-roll or B-roll-base shots were found in shot_plan.json or visual_strategy.csv.", "Create script analysis and mark B-roll needs before rendering."))

    asset_records = load_asset_records(project_dir)
    search_payload = read_json(plan_dir(project_dir) / "asset_search_plan.json", {})
    search_entries = search_shots(search_payload)
    sourcing_needed = False

    for shot in required_shots:
        shot_id = str(shot.get("shot_id") or shot.get("shot") or "")
        keywords = shot.get("broll_keywords") or shot.get("asset_keywords") or []
        if not keywords:
            failures.append(fail("asset_gate", "broll_shot_missing_keywords", f"{shot_id} needs B-roll but has no broll_keywords.", "Extract shot-level visible keywords before sourcing.", shot_id=shot_id))

        substitute_text = " ".join(
            str(shot.get(key, "") or "").lower()
            for key in ("broll_base_asset", "asset_key", "assets", "source_segments", "selected_asset", "selected_assets")
        )
        if any(token in substitute_text for token in BAD_BROLL_SUBSTITUTE_TOKENS):
            failures.append(fail("asset_gate", "invalid_broll_substitute", f"{shot_id} appears to use generated/HyperFrame/text/placeholder/repeated media as B-roll coverage.", "Replace the substitute with lawful selected B-roll, image fallback, or documented shortage.", shot_id=shot_id))

        local_assets = local_selected_assets(project_dir, shot, asset_records)
        if local_assets:
            selected.extend(local_assets)
            checked.append({"shot_id": shot_id, "result": "selected_local_asset", "assets": local_assets})
            continue

        sourcing_needed = True
        entry = find_search_entry(shot_id, search_entries)
        if not entry:
            failures.append(fail("asset_gate", "missing_asset_search_entry", f"{shot_id} lacks an asset_search_plan.json entry.", "Create shot-level primary/fallback/video/news/screen-recording search terms.", shot_id=shot_id))
            checked.append({"shot_id": shot_id, "result": "missing_search_entry"})
            continue

        if not has_any_terms(entry):
            failures.append(fail("asset_gate", "empty_asset_search_terms", f"{shot_id} has an empty asset search plan.", "Fill primary_terms, fallback_terms, video_terms, news_terms, or screen_recording_targets.", shot_id=shot_id))

        entry_selected = [value for value in selected_assets(entry) if selected_asset_exists(project_dir, value, asset_records)]
        if entry_selected:
            selected.extend(str(value) for value in entry_selected)
            checked.append({"shot_id": shot_id, "result": "selected_search_asset", "assets": entry_selected})
            continue

        if has_shortage(entry):
            shortage = {"shot_id": shot_id, "reason": entry.get("shortage_reason") or entry.get("blocked_reason") or entry.get("notes") or "documented shortage"}
            shortages.append(shortage)
            checked.append({"shot_id": shot_id, "result": "documented_shortage", "shortage": shortage})
            continue

        failures.append(fail("asset_gate", "no_selected_asset_or_shortage", f"{shot_id} has no selected local asset and no documented shortage.", "Select a lawful asset or record a real shortage/block reason after source attempts.", shot_id=shot_id))
        checked.append({"shot_id": shot_id, "result": "missing_selected_asset_or_shortage"})

    if sourcing_needed and not video_audit_has_records(project_dir):
        failures.append(fail("asset_gate", "missing_video_source_audit_records", "Sourcing was needed but video_source_audit.csv has no real provider/query/source/blocked records.", "Record each provider/query attempt before claiming sourcing was completed."))

    status = "failed" if failures else "passed"
    return write_audit(
        plan_dir(project_dir) / "asset_gate_audit.json",
        status,
        failures,
        warnings=warnings,
        checked_broll_shots=checked,
        selected_assets=sorted(set(selected)),
        documented_shortages=shortages,
        sourcing_needed=sourcing_needed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit B-roll/source acquisition gate.")
    parser.add_argument("project_dir")
    args = parser.parse_args()
    return audit(Path(args.project_dir).expanduser().resolve())


if __name__ == "__main__":
    sys.exit(main())
