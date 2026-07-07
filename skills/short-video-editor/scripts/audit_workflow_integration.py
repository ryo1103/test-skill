#!/usr/bin/env python3
"""Final pre-render workflow integration gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from workflow_audit_lib import (
    clean_text,
    decode_video,
    fail,
    meaningful_rows,
    plan_dir,
    read_csv,
    read_json,
    status_is_not_run,
    status_is_passed,
    status_value,
    truthy,
    write_audit,
)


REQUIRED_JSON_FILES = [
    "style_contract.json",
    "video_topic.json",
    "style_intake_report.json",
    "subtitle_cues.json",
    "subtitle_timing_audit.json",
    "shot_plan.json",
    "asset_search_plan.json",
    "news_source_plan.json",
    "asset_gate_audit.json",
    "visual_strategy_audit.json",
    "visual_ratio_audit.json",
    "source_uniqueness_audit.json",
    "source_playback_audit.json",
    "hyperframe_polish_guard.json",
    "hyperframe_plan_audit.json",
    "layout_qc_report.json",
    "topic_banner_audit.json",
    "subtitle_style_audit.json",
    "probe_render_report.json",
]

REQUIRED_CSV_FILES = [
    "visual_strategy.csv",
]


def json_nonempty(payload: Any) -> bool:
    if isinstance(payload, dict):
        return bool(payload)
    if isinstance(payload, list):
        return bool(payload)
    return False


def json_file(project_dir: Path, name: str) -> Path:
    return plan_dir(project_dir) / name


def require_json_file(project_dir: Path, name: str, failures: list[dict[str, Any]]) -> Any:
    path = json_file(project_dir, name)
    payload = read_json(path, None)
    if payload is None:
        failures.append(fail("workflow_integration", "missing_or_invalid_json", f"{name} is missing, empty, or invalid JSON.", "Create a valid non-empty JSON artifact before final render.", path=str(path)))
        return None
    if not json_nonempty(payload):
        failures.append(fail("workflow_integration", "empty_json_template", f"{name} is an empty template.", "Fill the artifact with real workflow data before final render.", path=str(path)))
    return payload


def require_status(project_dir: Path, name: str, allowed: set[str], failures: list[dict[str, Any]], stage: str) -> Any:
    payload = require_json_file(project_dir, name, failures)
    status = status_value(payload)
    if payload is None:
        return payload
    if status in {"", "not_run"}:
        failures.append(fail(stage, "audit_not_run", f"{name}.status is {status or 'missing'}.", "Run the corresponding audit script; file existence is not enough.", path=str(json_file(project_dir, name))))
    elif status not in allowed:
        failures.append(fail(stage, "audit_status_not_passed", f"{name}.status is {status}, expected {sorted(allowed)}.", "Run remediation, rerun the failed audit, and continue only after it passes.", path=str(json_file(project_dir, name))))
    return payload


def subtitle_cues_valid(payload: Any, failures: list[dict[str, Any]]) -> None:
    if not isinstance(payload, dict):
        return
    method = str(payload.get("alignment_method", "") or "")
    cues = payload.get("cues") if isinstance(payload.get("cues"), list) else []
    if method == "script_length_proportional_draft_only":
        failures.append(fail("subtitle_alignment", "draft_alignment_blocks_final", "subtitle_cues.json uses script_length_proportional_draft_only.", "Run ASR/forced alignment/manual phrase timestamp remediation before final render."))
    if not cues:
        failures.append(fail("subtitle_alignment", "empty_subtitle_cues", "subtitle_cues.json has no cue rows.", "Generate audio-aligned semantic subtitle cues."))
    for cue in cues:
        if not isinstance(cue, dict):
            continue
        start = cue.get("start_sec", cue.get("start"))
        end = cue.get("end_sec", cue.get("end"))
        source = str(cue.get("alignment_source") or method or "")
        if start in ("", None) or end in ("", None) or source in {"", "script_length_proportional_draft_only"}:
            failures.append(fail("subtitle_alignment", "cue_missing_audio_timing", f"Cue {cue.get('cue_id') or cue.get('id') or ''} lacks audio-derived timing.", "Rebuild cues with ASR/forced/manual phrase timestamps."))
            break


def visual_strategy_valid(project_dir: Path, failures: list[dict[str, Any]]) -> None:
    rows = meaningful_rows(read_csv(plan_dir(project_dir) / "visual_strategy.csv"))
    if not rows:
        failures.append(fail("visual_strategy", "empty_visual_strategy_csv", "visual_strategy.csv has no actual rows.", "Generate semantic script-to-visual planning rows."))
        return
    for row in rows:
        shot = row.get("shot") or row.get("shot_id") or ""
        if not clean_text(row.get("ae_overlay_candidate")):
            failures.append(fail("visual_strategy", "missing_ae_decision", f"{shot} lacks AE/PPT/HyperFrame decision.", "Run audit_visual_strategy.py and fill ae_overlay_candidate=yes/no."))
            break


def shot_plan_valid(payload: Any, failures: list[dict[str, Any]]) -> None:
    shots = payload.get("shots") if isinstance(payload, dict) else []
    if not isinstance(shots, list) or not shots:
        failures.append(fail("shot_plan", "empty_shot_plan", "shot_plan.json has no shots.", "Generate shot_plan.json with real shot entries."))
        return
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        broll_needed = truthy(shot.get("broll_needed")) or str(shot.get("scene_type", "")).lower() in {"broll_fullscreen", "broll_with_overlay", "screen_recording"}
        if broll_needed and not shot.get("broll_keywords"):
            failures.append(fail("shot_plan", "broll_shot_missing_keywords", f"Shot {shot.get('shot_id') or shot.get('shot') or ''} needs B-roll but lacks broll_keywords.", "Fill shot-level B-roll keywords before asset sourcing."))
            break


def asset_gate_final_valid(payload: Any, failures: list[dict[str, Any]]) -> None:
    if not isinstance(payload, dict):
        return
    if payload.get("documented_shortages"):
        failures.append(fail("asset_gate", "documented_shortage_blocks_final", "asset_gate_audit.json still contains documented_shortages.", "Stop at sourcing or acquire/approve replacement assets before final render.", shortages=payload.get("documented_shortages")))
    if not payload.get("selected_assets"):
        failures.append(fail("asset_gate", "no_selected_assets", "asset_gate_audit.json has no selected_assets.", "Select real local B-roll/screen/image assets or stop with a shortage report."))


def video_source_audit_valid(project_dir: Path, asset_gate: Any, failures: list[dict[str, Any]]) -> None:
    rows = meaningful_rows(read_csv(plan_dir(project_dir) / "video_source_audit.csv"))
    sourcing_needed = isinstance(asset_gate, dict) and bool(asset_gate.get("sourcing_needed"))
    if not sourcing_needed:
        return
    if not rows:
        failures.append(fail("asset_sourcing", "empty_video_source_audit", "Sourcing was needed but video_source_audit.csv has no records.", "Record provider/query/download/blocked attempts."))
        return
    for row in rows:
        if clean_text(row.get("provider")) and clean_text(row.get("query")) and (clean_text(row.get("source_url")) or clean_text(row.get("blocked_reason"))):
            return
    failures.append(fail("asset_sourcing", "video_source_audit_rows_incomplete", "video_source_audit.csv has rows but no real provider/query/source_url-or-blocked_reason record.", "Fill actual sourcing attempts before final render."))


def source_manifest_valid(project_dir: Path, failures: list[dict[str, Any]]) -> None:
    asset_manifest = read_json(project_dir / "assets" / "metadata" / "asset_manifest.json", {})
    assets = asset_manifest.get("assets") if isinstance(asset_manifest, dict) else []
    if not isinstance(assets, list) or not assets:
        failures.append(fail("asset_sourcing", "empty_asset_manifest", "assets/metadata/asset_manifest.json has no assets.", "Record selected/downloaded assets with source metadata."))
    sources = meaningful_rows(read_csv(project_dir / "assets" / "sources.csv"))
    if not sources:
        failures.append(fail("asset_sourcing", "empty_sources_csv", "assets/sources.csv has no rows.", "Record source URLs/licenses/notes for selected assets."))


def probe_valid(project_dir: Path, payload: Any, failures: list[dict[str, Any]]) -> None:
    video = project_dir / "output" / "qc" / "probe_render.mp4"
    frames = project_dir / "output" / "qc" / "probe_frames"
    if not video.exists():
        failures.append(fail("probe_render", "missing_probe_render", "output/qc/probe_render.mp4 is missing.", "Run render_probe.py after layout preflight."))
    else:
        ok, error = decode_video(video)
        if not ok:
            failures.append(fail("probe_render", "probe_decode_failed", "probe_render.mp4 failed decode.", "Fix probe render and rerun.", error=error))
    if not frames.exists() or not list(frames.glob("frame_*.png")):
        failures.append(fail("probe_render", "missing_probe_frames", "output/qc/probe_frames has no extracted frames.", "Extract probe frames before final render."))
    if isinstance(payload, dict):
        if payload.get("missing_required_coverage"):
            failures.append(fail("probe_render", "probe_missing_required_coverage", "Probe render does not cover all required manifest scene types.", "Revise probe selection or manifest rows and rerun render_probe.py.", missing=payload.get("missing_required_coverage")))
        if payload.get("decode_status") and payload.get("decode_status") != "passed":
            failures.append(fail("probe_render", "probe_report_decode_failed", "probe_render_report.json decode_status is not passed.", "Fix probe decode and rerun."))


def visual_inspection_valid(project_dir: Path, failures: list[dict[str, Any]]) -> None:
    path = plan_dir(project_dir) / "visual_inspection_report.json"
    payload = read_json(path, {})
    if not isinstance(payload, dict) or not payload:
        failures.append(fail("visual_qc", "missing_visual_inspection_report", "visual_inspection_report.json is missing.", "Run extract_qc_frames.py --report and inspect frames before final delivery."))
        return
    if payload.get("inspection_required", True) and status_value(payload) != "passed":
        failures.append(fail("visual_qc", "visual_inspection_not_passed", f"visual_inspection_report.json.status is {status_value(payload)}.", "Inspect extracted frames and update the report to passed only after checking required visual issues."))


def audit(project_dir: Path) -> int:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    payloads: dict[str, Any] = {}
    for name in REQUIRED_JSON_FILES:
        payloads[name] = require_json_file(project_dir, name, failures)

    for name in REQUIRED_CSV_FILES:
        path = plan_dir(project_dir) / name
        rows = meaningful_rows(read_csv(path))
        if not path.exists():
            failures.append(fail("workflow_integration", "missing_csv", f"{name} is missing.", "Create the required CSV artifact.", path=str(path)))
        elif not rows:
            failures.append(fail("workflow_integration", "empty_csv_template", f"{name} has no meaningful rows.", "Fill the CSV with real workflow records; header-only files do not pass.", path=str(path)))

    require_status(project_dir, "asset_gate_audit.json", {"passed"}, failures, "asset_gate")
    require_status(project_dir, "visual_strategy_audit.json", {"passed"}, failures, "visual_strategy")
    require_status(project_dir, "visual_ratio_audit.json", {"passed"}, failures, "visual_ratio")
    require_status(project_dir, "source_uniqueness_audit.json", {"passed"}, failures, "source_uniqueness")
    require_status(project_dir, "source_playback_audit.json", {"passed"}, failures, "source_playback")
    require_status(project_dir, "hyperframe_plan_audit.json", {"passed"}, failures, "hyperframe_plan")
    require_status(project_dir, "layout_qc_report.json", {"passed"}, failures, "layout_qc")
    require_status(project_dir, "topic_banner_audit.json", {"passed", "user_disabled"}, failures, "topic_banner")
    require_status(project_dir, "subtitle_style_audit.json", {"passed"}, failures, "subtitle_style")
    require_status(project_dir, "probe_render_report.json", {"passed"}, failures, "probe_render")

    subtitle_cues_valid(payloads.get("subtitle_cues.json"), failures)
    visual_strategy_valid(project_dir, failures)
    shot_plan_valid(payloads.get("shot_plan.json"), failures)
    asset_gate_final_valid(payloads.get("asset_gate_audit.json"), failures)
    video_source_audit_valid(project_dir, payloads.get("asset_gate_audit.json"), failures)
    source_manifest_valid(project_dir, failures)
    probe_valid(project_dir, payloads.get("probe_render_report.json"), failures)
    visual_inspection_valid(project_dir, failures)

    status = "failed" if failures else "passed"
    return write_audit(
        plan_dir(project_dir) / "workflow_integration_audit.json",
        status,
        failures,
        warnings=warnings,
        checked_files=REQUIRED_JSON_FILES + REQUIRED_CSV_FILES + [
            "assets/sources.csv",
            "assets/metadata/asset_manifest.json",
            "output/qc/probe_render.mp4",
            "output/qc/probe_frames/",
            "work/plan/visual_inspection_report.json",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit complete short-video workflow integration before final render.")
    parser.add_argument("project_dir")
    args = parser.parse_args()
    return audit(Path(args.project_dir).expanduser().resolve())


if __name__ == "__main__":
    sys.exit(main())
