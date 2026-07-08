from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from . import ENGINE_VERSION
from .contracts import read_json, write_json
from .paths import output_dir, plan_dir, project_root, stage_reports_dir
from .reporting.provenance import provenance_failures, provenance_fields
from .stage_registry import ordered_stage_ids, run_stage
from .stage_result import FINAL_BLOCKED, PASS, StageResult, current_command, failure
from .stages.common import ensure_project_dirs, has_engine_pass


VISUAL_COLUMNS = [
    "shot",
    "script_fragment",
    "narrative_role",
    "logic_type",
    "scene_type",
    "renderer",
    "digital_human_presence",
    "digital_human_reason",
    "broll_keywords",
    "overlay_text",
    "data_visual_type",
    "hyperframe_score",
    "hyperframe_allowed",
    "hyperframe_reason",
    "why_simple_broll_is_not_enough",
    "downgrade_reason",
    "why_simple_broll_is_enough",
    "visual_pattern",
    "ae_overlay_candidate",
    "ae_overlay_type",
    "broll_base_asset",
    "overlay_layer_plan",
    "design_plan",
    "animation_plan",
    "hyperframe_polish_guard",
    "hyperframe_completeness_check",
    "editing_rhythm",
    "screen_text",
    "user_review_needed",
]

MANIFEST_COLUMNS = [
    "shot_id",
    "source_segments",
    "start",
    "end",
    "duration",
    "visual_mode",
    "asset_key",
    "source_in",
    "source_out",
    "playback_policy",
    "overlay_png",
    "script",
    "subtitle_cue_ids",
    "persistent_overlay_id",
    "topic_banner_mode",
    "layout_qc_status",
]


def write_csv_header(path: Path, columns: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=columns).writeheader()


def init_project(project_dir_value: str | Path, script_name: str = "script.txt", oral_name: str = "oral.mp4") -> Path:
    project_dir = project_root(project_dir_value)
    ensure_project_dirs(project_dir)
    write_csv_header(plan_dir(project_dir) / "visual_strategy.csv", VISUAL_COLUMNS)
    write_csv_header(plan_dir(project_dir) / "edit_manifest.csv", MANIFEST_COLUMNS)
    write_csv_header(project_dir / "assets" / "sources.csv", ["asset_key", "path", "source_url", "license_or_note", "usage", "provider", "shot_id"])
    write_json(plan_dir(project_dir) / "pipeline_state.json", {"generated_by": "short_video_engine", "status": "initialized", "script_name": script_name, "oral_name": oral_name})
    for name, payload in {
        "asset_search_plan.json": {"shots": []},
        "news_source_plan.json": {"queries": [], "sources": []},
        "hyperframe_polish_guard.json": {"shots": []},
        "remediation_log.json": {"status": "not_run", "attempts": [], "unresolved_blockers": []},
    }.items():
        path = plan_dir(project_dir) / name
        if not path.exists():
            write_json(path, payload)
    return project_dir


def stage_slice(from_stage: str | None, to_stage: str | None) -> list[str]:
    stages = ordered_stage_ids()
    start = stages.index(from_stage) if from_stage else 0
    end = stages.index(to_stage) if to_stage else len(stages) - 1
    if start > end:
        raise ValueError("--from-stage must not come after --to-stage")
    return stages[start : end + 1]


def run_pipeline(project_dir: Path, from_stage: str | None = None, to_stage: str | None = None, strict: bool = True, draft_ok: bool = False, max_remediation_rounds: int = 0, no_network: bool = False, no_render: bool = False, allow_fixtures: bool = False, enable_asr: bool = False, motion_renderer: str = "auto") -> list[dict[str, Any]]:
    del max_remediation_rounds, no_render
    reports: list[dict[str, Any]] = []
    for stage_id in stage_slice(from_stage, to_stage):
        result = run_stage(stage_id, project_dir, strict=strict, draft_ok=draft_ok, allow_fixtures=allow_fixtures, no_network=no_network, enable_asr=enable_asr, motion_renderer=motion_renderer)
        report = result.write(project_dir)
        reports.append(report)
        if result.status != PASS and not (draft_ok and result.status == "DRAFT_ONLY"):
            break
    write_json(plan_dir(project_dir) / "pipeline_state.json", {"generated_by": "short_video_engine", "status": reports[-1]["status"] if reports else "not_run", "last_stage": reports[-1]["stage"] if reports else None, "reports": reports})
    return reports


def validate_stage(project_dir: Path, stage: str, draft_ok: bool = False) -> StageResult:
    report_path = stage_reports_dir(project_dir) / f"{stage}.json"
    report = read_json(report_path, {})
    failures = []
    status = str(report.get("status") or "")
    if not report:
        failures.append(failure("missing_stage_report", f"{stage} report is missing.", "Run the stage through the engine CLI."))
    elif status == PASS and not has_engine_pass(report):
        failures.append(failure("untrusted_pass_report", f"{stage} PASS report was not generated by short_video_engine.", "Regenerate the report with the engine validator."))
    elif status == "DRAFT_ONLY" and not draft_ok:
        failures.append(failure("draft_only_not_allowed", f"{stage} is DRAFT_ONLY.", "Rerun with real evidence or pass --draft-ok for preview workflows."))
        failures.extend(report_failure_items(report))
    elif status not in {PASS, "DRAFT_ONLY"}:
        failures.append(failure("stage_not_passed", f"{stage} status is {status or 'missing'}.", "Run remediation and rerun the stage."))
        failures.extend(report_failure_items(report))
    if stage == "S0_intake" and status == PASS and not failures:
        intake_path = plan_dir(project_dir) / "project_intake_report.json"
        intake = read_json(intake_path, {})
        if intake.get("generated_by") != "short_video_engine":
            failures.append(failure("untrusted_intake_report", "project_intake_report.json was not generated by short_video_engine.", "Regenerate S0 through the engine."))
        for key in ("container_duration", "audio_stream_duration", "video_stream_duration", "fps"):
            try:
                value = float(intake.get(key) or 0)
            except (TypeError, ValueError):
                value = 0
            if value <= 0:
                failures.append(failure("invalid_intake_metadata", f"project_intake_report.json has non-positive {key}.", "Regenerate S0 with a real decodable oral video."))
        resolution = intake.get("resolution") if isinstance(intake.get("resolution"), dict) else {}
        if int(resolution.get("width") or 0) <= 0 or int(resolution.get("height") or 0) <= 0:
            failures.append(failure("invalid_intake_metadata", "project_intake_report.json has invalid resolution.", "Regenerate S0 with a real decodable oral video."))
        if not intake.get("input_artifact_hashes"):
            failures.append(failure("missing_intake_input_hashes", "project_intake_report.json lacks input_artifact_hashes.", "Regenerate S0 through the engine."))
    if stage == "S1_script_and_subtitles" and status == PASS and not failures:
        from .stages.s1_script_and_subtitles import FINAL_TIMING_METHODS, validate_cues, validate_units

        intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
        units_payload = read_json(plan_dir(project_dir) / "script_units.json", {})
        cues_payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
        audit_payload = read_json(plan_dir(project_dir) / "subtitle_timing_audit.json", {})
        if units_payload.get("generated_by") != "short_video_engine" or cues_payload.get("generated_by") != "short_video_engine":
            failures.append(failure("untrusted_subtitle_artifacts", "S1 artifacts were not generated by short_video_engine.", "Regenerate S1 through the engine."))
        script_path = Path(str(intake.get("script_path") or ""))
        if not script_path.exists():
            failures.append(failure("missing_source_script_for_s1_validation", "Cannot validate S1 because the source script is missing.", "Restore the source script and rerun S1."))
        else:
            script_text = script_path.read_text(encoding="utf-8", errors="ignore")
            units = units_payload.get("units") if isinstance(units_payload.get("units"), list) else []
            cues = cues_payload.get("cues") if isinstance(cues_payload.get("cues"), list) else []
            method = str(cues_payload.get("alignment_method") or "")
            duration = float(intake.get("audio_stream_duration") or intake.get("audio_duration") or 0)
            timing_has_provenance = method in FINAL_TIMING_METHODS and bool(audit_payload.get("alignment_method") == method) and all(isinstance(cue, dict) and cue.get("timing_provenance") for cue in cues)
            failures.extend(validate_units(script_text, units))
            failures.extend(validate_cues(script_text, units, cues, method, True, duration, timing_has_provenance))
    if stage == "S1_5_subtitle_layout_planning" and status == PASS and not failures:
        from .producers.subtitle_layout_planner import validate_layout_cues

        source_payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
        layout_payload = read_json(plan_dir(project_dir) / "subtitle_layout_cues.json", {})
        audit_payload = read_json(plan_dir(project_dir) / "subtitle_readability_audit.json", {})
        source_cues = source_payload.get("cues") if isinstance(source_payload, dict) else []
        layout_cues = layout_payload.get("cues") if isinstance(layout_payload, dict) else []
        if layout_payload.get("generated_by") != "short_video_engine" or audit_payload.get("generated_by") != "short_video_engine":
            failures.append(failure("untrusted_subtitle_layout_plan", "Subtitle layout planning artifacts were not generated by short_video_engine.", "Regenerate S1.5 through the engine."))
        failures.extend(validate_layout_cues([cue for cue in source_cues if isinstance(cue, dict)] if isinstance(source_cues, list) else [], [cue for cue in layout_cues if isinstance(cue, dict)] if isinstance(layout_cues, list) else []))
    if stage == "S2_visual_plan" and status == PASS and not failures:
        from .compiler.shot_plan_compiler import validate_shot_plan_payload

        shot_plan = read_json(plan_dir(project_dir) / "shot_plan.json", {})
        if not isinstance(shot_plan, dict):
            failures.append(failure("invalid_shot_plan_json", "shot_plan.json is not a JSON object.", "Regenerate S2 through the engine compiler."))
        else:
            failures.extend(validate_shot_plan_payload(shot_plan, project_dir))
    if stage == "S3_asset_sourcing" and status == PASS and not failures:
        from .producers.asset_materializer import STRICT_MIN_ASSETS, distinct_passed_records, load_manifest

        passed, record_failures, duplicates = distinct_passed_records(project_dir, load_manifest(project_dir))
        if len(passed) < STRICT_MIN_ASSETS:
            failures.append(failure("insufficient_distinct_materialized_video_broll", f"S3 strict PASS requires {STRICT_MIN_ASSETS} assets; found {len(passed)}.", "Materialize more real external local video_broll assets."))
        if record_failures:
            failures.append(failure("asset_manifest_contains_invalid_records", "Some asset_manifest records are invalid and cannot count.", "Fix or remove invalid manifest records."))
        if duplicates:
            failures.append(failure("asset_manifest_contains_duplicate_sources", "Duplicate source/direct/provider/source_key/sha256 records cannot count as distinct.", "Use distinct source footage."))
    if stage == "S4_base_timeline" and status == PASS and not failures:
        from .producers.base_plate_renderer import audit_manifest, audit_output_duration, read_manifest

        rows = read_manifest(plan_dir(project_dir) / "edit_manifest.csv")
        failures.extend(audit_manifest(project_dir, rows))
        failures.extend(audit_output_duration(project_dir, output_dir(project_dir) / "base_plate.mp4", rows))
    if stage == "S5_motion_overlay" and status == PASS and not failures:
        from .producers.motion_renderer.renderer import validate_layer
        from .validators.motion_design_quality import validate_motion_design_quality
        from .validators.semantic_motion import validate_semantic_motion

        payload = read_json(plan_dir(project_dir) / "motion_layers.json", {})
        layers = payload.get("layers") if isinstance(payload, dict) else []
        if not isinstance(layers, list):
            layers = []
        for layer in layers:
            if isinstance(layer, dict):
                failures.extend(validate_layer(layer, project_dir))
        failures.extend(validate_motion_design_quality(project_dir, strict=not draft_ok, allow_pillow_professional=False))
        failures.extend(validate_semantic_motion(project_dir))
    if stage == "S6_text_layout" and status == PASS and not failures:
        from .producers.text_overlay_renderer import validate_text_layout

        failures.extend(validate_text_layout(project_dir))
    if stage == "S7_process_validation" and status == PASS and not failures:
        from .producers.probe_renderer import build_coverage_report, coverage_failures, previous_stage_status, validate_representative_frames

        frames_payload = read_json(plan_dir(project_dir) / "process_validation_report.json", {})
        frames = frames_payload.get("representative_frames") if isinstance(frames_payload, dict) else {}
        frames = frames if isinstance(frames, dict) else {}
        failures.extend(validate_representative_frames(project_dir, frames))
        coverage = build_coverage_report(project_dir, output_dir(project_dir) / "qc" / "probe_render.mp4", frames)
        failures.extend(coverage_failures(coverage))
        if any(item["status"] != "PASS" for item in previous_stage_status(project_dir)):
            failures.append(failure("previous_production_slice_not_passed", "S0-S6 are not all PASS.", "Fix earlier stages first."))
    if stage == "S8_final_render_and_validation" and status == PASS and not failures:
        from .producers.final_renderer import validate_final_outputs

        acceptance = read_json(plan_dir(project_dir) / "production_acceptance_report.json", {})
        if acceptance.get("generated_by") != "short_video_engine" or acceptance.get("status") != PASS or acceptance.get("can_claim_complete") is not True:
            failures.append(failure("production_acceptance_not_trusted_pass", "production_acceptance_report.json is not a trusted engine PASS.", "Rerun S8 through the engine."))
        failures.extend(validate_final_outputs(project_dir))
    return StageResult(stage, FINAL_BLOCKED if failures else PASS, "validate_stage", current_command(), failures=failures, inputs=[report_path])


def report_failure_items(report: dict[str, Any]) -> list[dict[str, str]]:
    items = report.get("failures")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict) and item.get("code")]
    codes = report.get("failure_codes")
    if isinstance(codes, list):
        return [failure(str(code), f"Stage report failure: {code}") for code in codes if code]
    return []


def allow_fixtures_enabled(allow_fixtures: bool) -> bool:
    return allow_fixtures or os.environ.get("SVIDEO_ALLOW_FIXTURES") == "1"


def validate_final(project_dir: Path, allow_fixtures: bool = False) -> StageResult:
    failures = []
    from .producers.final_renderer import validate_final_outputs

    metadata_path = plan_dir(project_dir) / "final_video_metadata.json"
    metadata = read_json(metadata_path, {})
    if isinstance(metadata, dict) and metadata.get("probe_source") == "dummy_ffprobe_metadata" and not allow_fixtures_enabled(allow_fixtures):
        failures.append(failure("fixture_probe_not_allowed_in_production", "dummy_ffprobe_metadata cannot be accepted in production mode.", "Use real ffprobe evidence or pass --allow-fixtures only for tests."))
    failures.extend(validate_final_outputs(project_dir))
    report_path = plan_dir(project_dir) / "final_validation_report.json"
    status = FINAL_BLOCKED if failures else PASS
    payload = {
        **provenance_fields("final_validation", [plan_dir(project_dir) / "final_render_log.json", plan_dir(project_dir) / "final_video_metadata.json", output_dir(project_dir) / "final.mp4"], [output_dir(project_dir) / "final.mp4"]),
        "validator": "validate_final",
        "status": status,
        "failure_codes": [item["code"] for item in failures],
        "failures": failures,
    }
    write_json(report_path, payload)
    return StageResult("final_validation", status, "validate_final", current_command(), failures=failures, outputs=[report_path])


def validate_production(project_dir: Path) -> StageResult:
    final = read_json(plan_dir(project_dir) / "final_validation_report.json", {})
    failures = []
    final_path = output_dir(project_dir) / "final.mp4"
    final_reports = [
        (plan_dir(project_dir) / "final_video_metadata.json", "S8_final_render_and_validation"),
        (plan_dir(project_dir) / "final_render_log.json", "S8_final_render_and_validation"),
        (plan_dir(project_dir) / "final_stream_probe.json", "S8_final_render_and_validation"),
        (plan_dir(project_dir) / "final_validation_report.json", "final_validation"),
    ]
    stage_report_paths = []
    for stage in ordered_stage_ids():
        path = stage_reports_dir(project_dir) / f"{stage}.json"
        stage_report_paths.append(path)
        payload = read_json(path, {})
        if payload.get("status") != PASS:
            failures.append(failure("stage_not_passed", f"{stage} is not PASS.", "Run the engine pipeline before production acceptance."))
        failures.extend(provenance_failures(payload, expected_stage=stage, check_recorded_hashes=False))
    for path, expected_stage in final_reports:
        payload = read_json(path, {})
        failures.extend(provenance_failures(payload, output_paths=[final_path], expected_stage=expected_stage))
    if final.get("status") != PASS or final.get("generated_by") != "short_video_engine":
        failures.append(failure("final_validation_not_trusted_pass", "final_validation_report.json is not a trusted engine PASS.", "Run svideo validate-final."))
    if final.get("can_claim_complete") is False:
        failures.append(failure("final_validation_cannot_claim_complete", "final_validation_report.json cannot claim complete.", "Rerun S8 and validate final outputs."))
    acceptance_path = plan_dir(project_dir) / "production_acceptance_report.json"
    existing_acceptance = read_json(acceptance_path, {})
    if isinstance(existing_acceptance, dict) and existing_acceptance.get("status") == PASS:
        failures.extend(provenance_failures(existing_acceptance, output_paths=[final_path], expected_stage="production_acceptance"))
    status = FINAL_BLOCKED if failures else PASS
    acceptance_payload = {
        **provenance_fields("production_acceptance", [*stage_report_paths, *[path for path, _ in final_reports]], [final_path]),
        "validator": "validate_production",
        "status": status,
        "can_claim_complete": not failures,
        "failure_codes": [item["code"] for item in failures],
        "failures": failures,
    }
    write_json(
        acceptance_path,
        acceptance_payload,
    )
    return StageResult("production_acceptance", status, "validate_production", current_command(), failures=failures, outputs=[acceptance_path], can_claim_complete=not failures)


def status(project_dir: Path) -> dict[str, Any]:
    stages = []
    for stage in ordered_stage_ids():
        report = read_json(stage_reports_dir(project_dir) / f"{stage}.json", {})
        stages.append({"stage": stage, "status": report.get("status", "not_run"), "generated_by": report.get("generated_by")})
    acceptance = read_json(plan_dir(project_dir) / "production_acceptance_report.json", {})
    return {"generated_by": "short_video_engine", "project_dir": str(project_dir), "stages": stages, "production_acceptance": acceptance}
