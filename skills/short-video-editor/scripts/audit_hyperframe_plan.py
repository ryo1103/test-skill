#!/usr/bin/env python3
"""Audit accepted and downgraded HyperFrame/AE overlay plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from workflow_audit_lib import clean_text, decode_video, fail, meaningful_rows, plan_dir, read_csv, read_json, shot_id_from_item, truthy, write_audit


SNAPSHOT_KEYS = ["0%", "25%", "50%", "75%", "100%"]


def jsonish_present(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    text = str(value or "").strip()
    if not text or text in {"{}", "[]", "null", "none", "None"}:
        return False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return True
    return parsed not in ({}, [], None, "")


def collect_shots(project_dir: Path) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    shot_plan = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    for shot in shot_plan.get("shots", []) if isinstance(shot_plan, dict) else []:
        if not isinstance(shot, dict):
            continue
        shot_id = shot_id_from_item(shot) or f"shot_plan_{len(result) + 1}"
        result.setdefault(shot_id, {}).update(shot)
        result[shot_id]["shot_id"] = shot_id
    for row in meaningful_rows(read_csv(plan_dir(project_dir) / "visual_strategy.csv")):
        shot_id = str(row.get("shot") or row.get("shot_id") or f"visual_{len(result) + 1}")
        result.setdefault(shot_id, {"shot_id": shot_id}).update({key: value for key, value in row.items() if value})
    return list(result.values())


def requires_hyperframe_audit(shot: dict[str, Any]) -> bool:
    text = " ".join(str(shot.get(key, "") or "").lower() for key in ("renderer", "scene_type", "visual_pattern", "ae_overlay_type"))
    if "hyperframe" in text:
        return True
    if truthy(shot.get("ae_overlay_candidate")):
        return True
    return False


def accepted_hyperframe(shot: dict[str, Any]) -> bool:
    text = " ".join(str(shot.get(key, "") or "").lower() for key in ("renderer", "scene_type"))
    return "hyperframe" in text or truthy(shot.get("hyperframe_allowed"))


def lookup_guard_records(project_dir: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "hyperframe_polish_guard.json", {})
    records: dict[str, dict[str, Any]] = {}
    items = payload.get("shots") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return records
    for item in items:
        if not isinstance(item, dict):
            continue
        shot_id = str(item.get("shot_id") or item.get("shot") or item.get("id") or "")
        if shot_id:
            records[shot_id] = item
    return records


def merged_guard(shot: dict[str, Any], external: dict[str, dict[str, Any]]) -> dict[str, Any]:
    shot_id = str(shot.get("shot_id") or shot.get("shot") or "")
    guard = external.get(shot_id, {}).copy()
    embedded = shot.get("hyperframe_polish_guard")
    if isinstance(embedded, dict):
        guard.update(embedded)
    elif isinstance(embedded, str) and embedded.strip().startswith("{"):
        try:
            parsed = json.loads(embedded)
            if isinstance(parsed, dict):
                guard.update(parsed)
        except json.JSONDecodeError:
            pass
    return guard


def merged_completeness(shot: dict[str, Any]) -> dict[str, Any]:
    value = shot.get("hyperframe_completeness_check")
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def path_from_value(project_dir: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = project_dir / path
    return path.resolve()


def snapshot_paths(guard: dict[str, Any], completeness: dict[str, Any]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for container in (guard.get("snapshot_paths"), completeness.get("snapshot_paths"), completeness.get("frame_checks")):
        if isinstance(container, dict):
            for key, value in container.items():
                paths[str(key)] = str(value)
        elif isinstance(container, list):
            for item in container:
                if isinstance(item, dict):
                    key = str(item.get("progress") or item.get("time") or item.get("label") or "")
                    value = str(item.get("path") or item.get("file") or "")
                    if key and value:
                        paths[key] = value
                elif isinstance(item, str):
                    for key in SNAPSHOT_KEYS:
                        if key.replace("%", "") in item or key in item:
                            paths[key] = item
    return paths


def warning_present(shot: dict[str, Any]) -> bool:
    for key in ("user_visible_warning", "downgrade_warning", "warning"):
        if clean_text(shot.get(key)):
            return True
    return str(shot.get("user_review_needed", "") or "").strip().lower() in {"yes", "true", "是", "required"}


def audit(project_dir: Path) -> int:
    failures: list[dict] = []
    warnings: list[dict] = []
    checked: list[dict[str, Any]] = []
    external_guards = lookup_guard_records(project_dir)

    candidates = [shot for shot in collect_shots(project_dir) if requires_hyperframe_audit(shot)]
    for shot in candidates:
        shot_id = str(shot.get("shot_id") or shot.get("shot") or "")
        accepted = accepted_hyperframe(shot)
        guard = merged_guard(shot, external_guards)
        completeness = merged_completeness(shot)
        checked.append({"shot_id": shot_id, "accepted": accepted})

        overlay_plan = str(shot.get("overlay_layer_plan") or "").lower()
        needs_broll_base = truthy(shot.get("ae_overlay_candidate")) and "standalone" not in overlay_plan
        if needs_broll_base and not clean_text(shot.get("broll_base_asset")) and "needs_sourcing" not in overlay_plan:
            failures.append(fail("hyperframe_plan", "missing_broll_base_asset", f"{shot_id} needs an AE/HyperFrame overlay base but lacks broll_base_asset.", "Select/source the B-roll base before coding or inserting the overlay.", shot_id=shot_id))

        if not accepted:
            if not clean_text(shot.get("downgrade_reason")):
                failures.append(fail("hyperframe_plan", "downgrade_missing_reason", f"{shot_id} is downgraded but lacks downgrade_reason.", "Document why HyperFrame/AE was downgraded.", shot_id=shot_id))
            if not clean_text(shot.get("why_simple_broll_is_enough")):
                failures.append(fail("hyperframe_plan", "downgrade_missing_broll_reason", f"{shot_id} is downgraded but lacks why_simple_broll_is_enough.", "Explain why B-roll/light overlay is enough.", shot_id=shot_id))
            if not warning_present(shot):
                failures.append(fail("hyperframe_plan", "downgrade_missing_user_warning", f"{shot_id} downgrade lacks a user-visible warning/review marker.", "Add a user-visible downgrade warning or set user_review_needed=yes.", shot_id=shot_id))
            continue

        if not jsonish_present(shot.get("design_plan")):
            failures.append(fail("hyperframe_plan", "accepted_hyperframe_missing_design_plan", f"{shot_id} lacks design_plan.", "Write a compact design_plan before generating HTML.", shot_id=shot_id))
        if not jsonish_present(shot.get("animation_plan")):
            failures.append(fail("hyperframe_plan", "accepted_hyperframe_missing_animation_plan", f"{shot_id} lacks animation_plan.", "Define setup, enter, build, emphasis, hold, and exit/settle.", shot_id=shot_id))

        final_status = str(guard.get("final_status") or guard.get("status") or "").strip().lower()
        visual_status = str(guard.get("visual_qa_status") or "").strip().lower()
        if final_status not in {"complete", "passed"}:
            failures.append(fail("hyperframe_plan", "hyperframe_polish_guard_not_complete", f"{shot_id} polish guard final_status is not complete/passed.", "Run lint/render/snapshot visual QA and mark final_status complete only after passing.", shot_id=shot_id, final_status=final_status))
        if visual_status and visual_status not in {"passed", "complete"}:
            failures.append(fail("hyperframe_plan", "hyperframe_visual_qa_not_passed", f"{shot_id} visual QA did not pass.", "Fix snapshots and rerender before insertion.", shot_id=shot_id, visual_qa_status=visual_status))

        clip_path = path_from_value(project_dir, completeness.get("standalone_clip_path") or guard.get("standalone_clip_path") or guard.get("clip_path"))
        if not clip_path or not clip_path.exists():
            failures.append(fail("hyperframe_plan", "missing_standalone_clip", f"{shot_id} lacks a standalone rendered clip path.", "Render a standalone HyperFrame/AE clip before inserting into the main timeline.", shot_id=shot_id))
        else:
            decoded, error = decode_video(clip_path)
            if not decoded:
                failures.append(fail("hyperframe_plan", "standalone_clip_decode_failed", f"{shot_id} standalone clip failed ffmpeg decode.", "Fix or rerender the clip.", shot_id=shot_id, clip_path=str(clip_path), error=error))

        snapshots = snapshot_paths(guard, completeness)
        missing_snapshots = []
        for key in SNAPSHOT_KEYS:
            candidate = snapshots.get(key) or snapshots.get(key.replace("%", ""))
            path = path_from_value(project_dir, candidate) if candidate else None
            if not path or not path.exists():
                missing_snapshots.append(key)
        if missing_snapshots:
            failures.append(fail("hyperframe_plan", "missing_required_snapshots", f"{shot_id} lacks required 0/25/50/75/100 snapshots.", "Capture and inspect every required progress snapshot.", shot_id=shot_id, missing_snapshots=missing_snapshots))

        all_elements = completeness.get("all_elements_animated")
        no_partial = completeness.get("no_partial_or_placeholder_animation")
        if all_elements is not True:
            failures.append(fail("hyperframe_plan", "elements_not_confirmed_animated", f"{shot_id} does not confirm all elements animated.", "Update hyperframe_completeness_check after visual QA confirms all planned elements animate.", shot_id=shot_id))
        if no_partial is not True:
            failures.append(fail("hyperframe_plan", "partial_placeholder_not_cleared", f"{shot_id} does not confirm no partial/placeholder animation.", "Remove placeholders or downgrade the shot.", shot_id=shot_id))

    status = "failed" if failures else "passed"
    return write_audit(
        plan_dir(project_dir) / "hyperframe_plan_audit.json",
        status,
        failures,
        warnings=warnings,
        checked_hyperframe_or_ae_shots=checked,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit HyperFrame/AE overlay plan completeness.")
    parser.add_argument("project_dir")
    args = parser.parse_args()
    return audit(Path(args.project_dir).expanduser().resolve())


if __name__ == "__main__":
    sys.exit(main())
