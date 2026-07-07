from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import read_json, write_json
from ..paths import plan_dir
from ..producers.asr_timing import enabled_by_env, produce_asr_timing
from ..stage_result import DRAFT_ONLY, FAIL, FINAL_BLOCKED, PASS, StageResult, current_command, failure, hash_existing


FINAL_TIMING_METHODS = {"asr", "forced_alignment", "asr_word_timestamps", "manual_phrase_timestamps", "user_provided_manual_timestamps"}
DRAFT_TIMING_METHODS = {"script_length_proportional_draft_only", "model_guessed", "proportional"}
VISIBLE_PUNCT_RE = re.compile(r"[，。！？；：、,.!?;:\"'“”‘’（）()【】\[\]《》<>]")
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+/#-]*")
SYNC_TOLERANCE_SEC = 0.5


def unit_id(index: int, start: int, text: str) -> str:
    digest = hashlib.sha1(f"{start}:{text}".encode("utf-8")).hexdigest()[:8]
    return f"u{index:03d}_{digest}"


def non_ws(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def display_text_for(source_text: str) -> str:
    return re.sub(r"\s+", "", VISIBLE_PUNCT_RE.sub("", source_text or ""))


def segment_script(script_text: str) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    pattern = re.compile(r"[^\s。！？!?；;\n][^。！？!?；;\n]*(?:[。！？!?；;]+|(?=\n|$))", re.S)
    for match in pattern.finditer(script_text):
        raw = match.group(0)
        start = match.start()
        end = match.end()
        leading = len(raw) - len(raw.lstrip())
        trailing = len(raw.rstrip())
        text = raw.strip()
        if not text:
            continue
        source_start = start + leading
        source_end = start + trailing
        index = len(units) + 1
        units.append(
            {
                "unit_id": unit_id(index, source_start, text),
                "index": index,
                "original_text": text,
                "source_text": text,
                "source_span": {"start": source_start, "end": source_end},
            }
        )
    if not units and script_text.strip():
        text = script_text.strip()
        source_start = script_text.index(text)
        units.append({"unit_id": unit_id(1, source_start, text), "index": 1, "original_text": text, "source_text": text, "source_span": {"start": source_start, "end": source_start + len(text)}})
    return units


def has_provenance(payload: Any) -> bool:
    if isinstance(payload, dict):
        provenance = payload.get("provenance")
        if isinstance(provenance, dict) and any(str(value).strip() for value in provenance.values()):
            return True
        cues = payload.get("cues")
        if isinstance(cues, list) and cues:
            return all(isinstance(cue, dict) and isinstance(cue.get("provenance"), dict) and cue.get("provenance") for cue in cues)
    if isinstance(payload, list) and payload:
        return all(isinstance(cue, dict) and isinstance(cue.get("provenance"), dict) and cue.get("provenance") for cue in payload)
    return False


def load_timing_input(project_dir: Path) -> tuple[str, Any, Path | None, bool]:
    plan = plan_dir(project_dir)
    manual_path = plan / "manual_phrase_timestamps.json"
    if manual_path.exists():
        payload = read_json(manual_path, None)
        return "manual_phrase_timestamps", payload, manual_path, has_provenance(payload)
    for name, default_method in (
        ("asr_word_timestamps.json", "asr_word_timestamps"),
        ("forced_alignment.json", "forced_alignment"),
        ("subtitle_timing_input.json", ""),
    ):
        path = plan / name
        if path.exists():
            payload = read_json(path, None)
            method = str(payload.get("alignment_method") or default_method) if isinstance(payload, dict) else default_method
            return method, payload, path, has_provenance(payload)
    return "script_length_proportional_draft_only", None, None, False


def cues_from_units_proportional(units: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    step = duration / max(len(units), 1) if duration > 0 else 0
    cues = []
    for index, unit in enumerate(units, start=1):
        source_text = unit["source_text"]
        cues.append(
            {
                "cue_id": f"c{index:03d}",
                "unit_id": unit["unit_id"],
                "source_text": source_text,
                "text": source_text,
                "display_text": display_text_for(source_text),
                "source_span": unit["source_span"],
                "start": round((index - 1) * step, 3),
                "end": round(index * step, 3),
                "timing_provenance": {"method": "script_length_proportional_draft_only", "draft_only": True},
            }
        )
    return cues


def normalize_timed_cues(timing_payload: Any, units: list[dict[str, Any]], method: str) -> list[dict[str, Any]]:
    if isinstance(timing_payload, dict):
        raw_cues = timing_payload.get("cues") or timing_payload.get("timestamps") or []
        top_provenance = timing_payload.get("provenance") or {}
    elif isinstance(timing_payload, list):
        raw_cues = timing_payload
        top_provenance = {}
    else:
        raw_cues = []
        top_provenance = {}
    cues = []
    by_id = {unit["unit_id"]: unit for unit in units}
    for index, unit in enumerate(units, start=1):
        raw = raw_cues[index - 1] if index - 1 < len(raw_cues) and isinstance(raw_cues[index - 1], dict) else {}
        if raw.get("unit_id") in by_id:
            unit = by_id[raw["unit_id"]]
        source_text = str(raw.get("source_text") or raw.get("text") or unit["source_text"])
        cues.append(
            {
                "cue_id": str(raw.get("cue_id") or f"c{index:03d}"),
                "unit_id": unit["unit_id"],
                "source_text": source_text,
                "text": source_text,
                "display_text": str(raw.get("display_text") or display_text_for(source_text)),
                "source_span": unit["source_span"],
                "start": raw.get("start"),
                "end": raw.get("end"),
                "timing_provenance": raw.get("provenance") or top_provenance or {"method": method},
            }
        )
    return cues


def validate_units(script_text: str, units: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures = []
    if non_ws("".join(unit["source_text"] for unit in units)) != non_ws(script_text):
        failures.append(failure("script_units_do_not_cover_source_script", "script_units.json does not exactly cover the original script text.", "Regenerate S1 from the original script without deleting text."))
    for unit in units:
        span = unit.get("source_span") if isinstance(unit.get("source_span"), dict) else {}
        start = int(span["start"]) if "start" in span else -1
        end = int(span["end"]) if "end" in span else -1
        if start < 0 or end <= start or script_text[start:end] != unit.get("source_text"):
            failures.append(failure("invalid_script_unit_source_span", f"Unit {unit.get('unit_id')} source_span does not match original script.", "Regenerate script units from source spans."))
            break
    return failures


def validate_cues(script_text: str, units: list[dict[str, Any]], cues: list[dict[str, Any]], method: str, strict: bool, duration: float, timing_has_provenance: bool) -> list[dict[str, str]]:
    failures = []
    unit_text_by_id = {unit["unit_id"]: unit["source_text"] for unit in units}
    cue_source = "".join(str(cue.get("source_text") or cue.get("text") or "") for cue in cues)
    if non_ws(cue_source) != non_ws(script_text):
        failures.append(failure("subtitle_cues_do_not_cover_source_script", "subtitle_cues.json does not cover the exact original script.", "Do not delete source script sentences from cues."))
    for cue in cues:
        source_text = str(cue.get("source_text") or "")
        unit_id_value = str(cue.get("unit_id") or "")
        if unit_id_value not in unit_text_by_id or source_text != unit_text_by_id[unit_id_value]:
            failures.append(failure("cue_text_not_exact_source_unit", f"Cue {cue.get('cue_id')} source_text does not match its script unit.", "Regenerate cues from script_units without rewriting."))
        if source_text and source_text not in script_text:
            failures.append(failure("cue_contains_non_source_text", f"Cue {cue.get('cue_id')} contains text that is not in the original script.", "Remove non-source content from subtitle cues."))
        if str(cue.get("display_text") or "") != display_text_for(source_text):
            failures.append(failure("display_text_rewrites_source", f"Cue {cue.get('cue_id')} display_text is not a punctuation-only transform.", "Only remove visible punctuation from display_text."))
        try:
            start = float(cue.get("start"))
            end = float(cue.get("end"))
        except (TypeError, ValueError):
            failures.append(failure("cue_missing_timing", f"Cue {cue.get('cue_id')} has invalid start/end.", "Provide numeric subtitle timing."))
            continue
        if start < 0 or end <= start:
            failures.append(failure("cue_invalid_timing_order", f"Cue {cue.get('cue_id')} has non-positive duration.", "Provide increasing cue start/end values."))
    failures.extend(validate_no_token_split(cues))
    if strict and method in DRAFT_TIMING_METHODS:
        failures.append(failure("subtitle_timing_draft_only", "Proportional/model-guessed timing cannot strict PASS.", "Provide ASR/forced-alignment/manual phrase timestamps."))
    if strict and method in FINAL_TIMING_METHODS and not timing_has_provenance:
        failures.append(failure("timing_provenance_missing", "Strict subtitle timing requires provenance.", "Add provenance for manual, ASR, or forced-alignment timestamps."))
    if cues and duration > 0:
        last_end = float(cues[-1].get("end") or 0)
        if strict and abs(last_end - duration) > SYNC_TOLERANCE_SEC:
            failures.append(failure("last_subtitle_end_audio_duration_mismatch", "Last subtitle end does not match oral audio duration tolerance.", "Fix timestamps; do not delete ending subtitles."))
    return failures


def validate_no_token_split(cues: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures = []
    for left, right in zip(cues, cues[1:]):
        left_text = str(left.get("source_text") or "")
        right_text = str(right.get("source_text") or "")
        if not left_text or not right_text:
            continue
        left_boundary = VISIBLE_PUNCT_RE.sub("", left_text.rstrip()).rstrip()
        right_boundary = VISIBLE_PUNCT_RE.sub("", right_text.lstrip()).lstrip()
        left_tail = re.search(r"([A-Za-z0-9][A-Za-z0-9._+/#-]*)$", left_boundary)
        right_head = TOKEN_RE.match(right_boundary)
        if left_tail and right_head:
            tail = left_tail.group(1)
            head = right_head.group(0)
            if tail and head and tail[-1].isalnum() and head[0].isalnum():
                failures.append(failure("english_brand_or_model_token_split", f"Token appears split across cues near '{tail}|{head}'.", "Do not split English brands, models, or abbreviations across cues."))
                break
    return failures


def write_timing_reports(project_dir: Path, method: str, cues: list[dict[str, Any]], duration: float, status: str, failures: list[dict[str, str]]) -> tuple[Path, Path]:
    first_start = float(cues[0].get("start") or 0) if cues else 0
    last_end = float(cues[-1].get("end") or 0) if cues else 0
    max_drift = abs(last_end - duration) if duration > 0 else 0
    audit_path = plan_dir(project_dir) / "subtitle_timing_audit.json"
    sync_path = plan_dir(project_dir) / "subtitle_timing_sync_report.json"
    common = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "validator": "s1_script_and_subtitles",
        "stage": "S1_script_and_subtitles",
        "command": " ".join(current_command()),
        "alignment_method": method,
        "cue_count_checked": len(cues),
        "max_drift_sec": round(max_drift, 3),
        "first_cue_start_sec": first_start,
        "last_cue_end_sec": last_end,
        "oral_audio_duration_sec": duration,
        "status": status,
        "failure_codes": [item["code"] for item in failures],
    }
    write_json(audit_path, common)
    write_json(sync_path, {**common, "sync_tolerance_sec": SYNC_TOLERANCE_SEC, "failures": failures})
    return audit_path, sync_path


def run(project_dir: Path, strict: bool = True, enable_asr: bool = False, **_: object) -> StageResult:
    intake_path = plan_dir(project_dir) / "project_intake_report.json"
    intake = read_json(intake_path, {})
    if not isinstance(intake, dict) or intake.get("generated_by") != "short_video_engine" or not intake.get("script_path"):
        return StageResult("S1_script_and_subtitles", FAIL, "s1_script_and_subtitles", current_command(), failures=[failure("missing_trusted_intake_report", "Trusted S0 intake report is missing.", "Run S0_intake first.")])

    script_path = Path(str(intake["script_path"]))
    script_text = script_path.read_text(encoding="utf-8", errors="ignore")
    duration = float(intake.get("audio_stream_duration") or intake.get("audio_duration") or 0)
    units = segment_script(script_text)
    units_path = plan_dir(project_dir) / "script_units.json"
    units_payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "source_script": str(script_path),
        "script_sha256": hash_existing([script_path]).get(str(script_path)),
        "units": units,
    }
    write_json(units_path, units_payload)

    asr_failures: list[dict[str, str]] = []
    existing_method, _existing_payload, _existing_path, _existing_has_provenance = load_timing_input(project_dir)
    if existing_method in DRAFT_TIMING_METHODS and (enable_asr or enabled_by_env()):
        oral_video = Path(str(intake.get("oral_video_path") or ""))
        _asr_path, asr_failures = produce_asr_timing(project_dir, units, oral_video, duration)

    method, timing_payload, timing_path, timing_has_provenance = load_timing_input(project_dir)
    if method in FINAL_TIMING_METHODS and timing_payload is not None:
        cues = normalize_timed_cues(timing_payload, units, method)
    else:
        method = "script_length_proportional_draft_only"
        cues = cues_from_units_proportional(units, duration)

    cues_path = plan_dir(project_dir) / "subtitle_cues.json"
    cues_payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "source_script": str(script_path),
        "alignment_method": method,
        "timing_input_path": str(timing_path) if timing_path else None,
        "cues": cues,
    }
    write_json(cues_path, cues_payload)

    failures = validate_units(script_text, units)
    failures.extend(validate_cues(script_text, units, cues, method, strict, duration, timing_has_provenance))
    failures.extend(asr_failures)
    if method in DRAFT_TIMING_METHODS:
        if not any(item["code"] == "subtitle_timing_draft_only" for item in failures):
            failures.append(failure("subtitle_timing_draft_only", "Proportional/model-guessed timing is draft preview only.", "Provide ASR/forced-alignment/manual phrase timestamps before final PASS."))
        status = DRAFT_ONLY
    else:
        status = PASS if not failures else FINAL_BLOCKED
    audit_path, sync_path = write_timing_reports(project_dir, method, cues, duration, status, failures)
    inputs = [script_path, intake_path]
    if timing_path:
        inputs.append(timing_path)
    return StageResult("S1_script_and_subtitles", status, "s1_script_and_subtitles", current_command(), failures=failures, inputs=inputs, outputs=[units_path, cues_path, audit_path, sync_path])
