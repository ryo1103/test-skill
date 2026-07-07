from __future__ import annotations

import difflib
import os
import re
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import write_json
from ..paths import plan_dir
from ..stage_result import current_command, failure


MIN_ALIGNMENT_COVERAGE = 0.45
MAX_TAIL_PAD_SEC = 2.5
VISIBLE_PUNCT_RE = re.compile(r"[，。！？；：、,.!?;:\"'“”‘’（）()【】\[\]《》<>]")


def enabled_by_env() -> bool:
    return os.environ.get("SVIDEO_ENABLE_ASR", "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_text(text: str) -> str:
    return display_text_for(text).lower()


def display_text_for(source_text: str) -> str:
    return re.sub(r"\s+", "", VISIBLE_PUNCT_RE.sub("", source_text or ""))


def produce_asr_timing(project_dir: Path, units: list[dict[str, Any]], oral_video: Path, audio_duration: float) -> tuple[Path | None, list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    output_path = plan_dir(project_dir) / "asr_word_timestamps.json"
    try:
        segments, metadata = transcribe_with_faster_whisper(oral_video)
    except Exception as exc:
        return None, [failure("asr_transcription_failed", f"ASR transcription failed: {exc}", "Install/configure faster-whisper or provide manual timestamps.")]
    payload, align_failures = build_asr_timing_payload(units, segments, audio_duration, metadata)
    failures.extend(align_failures)
    if failures:
        return None, failures
    write_json(output_path, payload)
    return output_path, []


def transcribe_with_faster_whisper(oral_video: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster_whisper is not installed") from exc
    model_name = os.environ.get("SVIDEO_ASR_MODEL", "tiny")
    device = os.environ.get("SVIDEO_ASR_DEVICE", "auto")
    compute_type = os.environ.get("SVIDEO_ASR_COMPUTE_TYPE", "int8")
    download_root = os.environ.get("SVIDEO_ASR_DOWNLOAD_ROOT") or None
    local_files_only = os.environ.get("SVIDEO_ASR_LOCAL_FILES_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}
    model = WhisperModel(model_name, device=device, compute_type=compute_type, download_root=download_root, local_files_only=local_files_only)
    segment_iter, info = model.transcribe(str(oral_video), language="zh", word_timestamps=True, vad_filter=False)
    segments: list[dict[str, Any]] = []
    for segment in segment_iter:
        words = []
        for word in getattr(segment, "words", None) or []:
            words.append({"word": getattr(word, "word", ""), "start": float(getattr(word, "start", 0) or 0), "end": float(getattr(word, "end", 0) or 0)})
        segments.append({"text": getattr(segment, "text", ""), "start": float(getattr(segment, "start", 0) or 0), "end": float(getattr(segment, "end", 0) or 0), "words": words})
    metadata = {
        "provider": "faster_whisper",
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
        "language": getattr(info, "language", "zh"),
        "language_probability": float(getattr(info, "language_probability", 0) or 0),
    }
    return segments, metadata


def build_asr_timing_payload(units: list[dict[str, Any]], segments: list[dict[str, Any]], audio_duration: float, metadata: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    script_text = "".join(str(unit.get("source_text") or "") for unit in units)
    script_norm = normalize_text(script_text)
    asr_chars = asr_character_timeline(segments)
    asr_norm = "".join(item["char"] for item in asr_chars)
    if not script_norm or not asr_norm:
        return {}, [failure("asr_empty_transcript", "ASR transcript or script text is empty.")]
    char_mapping = map_script_chars_to_asr(script_norm, asr_norm)
    coverage = len(char_mapping) / max(len(script_norm), 1)
    if coverage < MIN_ALIGNMENT_COVERAGE:
        return {}, [failure("asr_script_alignment_low_confidence", f"ASR/script alignment coverage {coverage:.2f} is below threshold {MIN_ALIGNMENT_COVERAGE:.2f}.")]
    unit_spans = normalized_unit_spans(units)
    cues: list[dict[str, Any]] = []
    for index, unit in enumerate(units, start=1):
        span = unit_spans[index - 1]
        mapped_indices = [char_mapping[i] for i in range(span[0], span[1]) if i in char_mapping and char_mapping[i] < len(asr_chars)]
        if not mapped_indices:
            return {}, [failure("asr_unit_alignment_missing", f"ASR could not align unit {unit.get('unit_id')}.")]
        start = min(float(asr_chars[i]["start"]) for i in mapped_indices)
        end = max(float(asr_chars[i]["end"]) for i in mapped_indices)
        cues.append(
            {
                "cue_id": f"c{index:03d}",
                "unit_id": unit["unit_id"],
                "source_text": unit["source_text"],
                "text": unit["source_text"],
                "display_text": display_text_for(unit["source_text"]),
                "source_span": unit["source_span"],
                "start": round(start, 3),
                "end": round(max(end, start + 0.05), 3),
                "provenance": {
                    "method": "asr_word_timestamps",
                    "provider": metadata.get("provider", "asr"),
                    "model": metadata.get("model", ""),
                    "alignment_coverage": round(coverage, 3),
                },
            }
        )
    if audio_duration > 0 and cues:
        tail_gap = audio_duration - float(cues[-1]["end"])
        if 0 <= tail_gap <= MAX_TAIL_PAD_SEC:
            cues[-1]["end"] = round(audio_duration, 3)
            cues[-1]["provenance"]["tail_padding_sec"] = round(tail_gap, 3)
        elif abs(tail_gap) > MAX_TAIL_PAD_SEC:
            return {}, [failure("asr_last_subtitle_end_audio_duration_mismatch", "ASR-derived last subtitle end is too far from oral audio duration.")]
    payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "alignment_method": "asr_word_timestamps",
        "command": " ".join(current_command()),
        "provenance": {
            "source": "local_asr",
            "method": "asr_word_timestamps",
            "provider": metadata.get("provider", "asr"),
            "model": metadata.get("model", ""),
            "alignment_coverage": round(coverage, 3),
        },
        "asr_metadata": metadata,
        "asr_segments": segments,
        "cues": cues,
    }
    return payload, []


def asr_character_timeline(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chars: list[dict[str, Any]] = []
    for segment in segments:
        words = segment.get("words") if isinstance(segment.get("words"), list) else []
        if words:
            for word in words:
                add_timed_text(chars, str(word.get("word") or ""), float(word.get("start") or 0), float(word.get("end") or 0))
        else:
            add_timed_text(chars, str(segment.get("text") or ""), float(segment.get("start") or 0), float(segment.get("end") or 0))
    return chars


def add_timed_text(chars: list[dict[str, Any]], text: str, start: float, end: float) -> None:
    normalized = normalize_text(text)
    if not normalized:
        return
    duration = max(end - start, 0.05)
    for index, char in enumerate(normalized):
        char_start = start + duration * index / len(normalized)
        char_end = start + duration * (index + 1) / len(normalized)
        chars.append({"char": char, "start": char_start, "end": char_end})


def map_script_chars_to_asr(script_norm: str, asr_norm: str) -> dict[int, int]:
    matcher = difflib.SequenceMatcher(a=script_norm, b=asr_norm, autojunk=False)
    mapping: dict[int, int] = {}
    for tag, i1, i2, j1, _j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                mapping[i1 + offset] = j1 + offset
    return mapping


def normalized_unit_spans(units: list[dict[str, Any]]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for unit in units:
        normalized = normalize_text(str(unit.get("source_text") or ""))
        start = cursor
        end = start + len(normalized)
        spans.append((start, end))
        cursor = end
    return spans
