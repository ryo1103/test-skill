#!/usr/bin/env python3
"""Audit subtitle, topic banner, and ordinary layout plans before final render."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(text: str) -> str:
    return re.sub(r"[\s，。！？!?,.、：:；;（）()【】\[\]\"'“”‘’\-—_]", "", text or "").lower()


def contains_visible_punctuation(text: str) -> bool:
    return bool(re.search(r"[，。；：、,.!?！？;:]", text or ""))


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def read_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def rect_overlap(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"]
        or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"]
        or b["y"] + b["height"] <= a["y"]
    )


def rect_inside_canvas_and_safe(rect: dict, canvas: dict, safe: dict, *, compact: bool = False) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    width = int(canvas.get("width", 1080))
    height = int(canvas.get("height", 1920))
    left = int(safe.get("left", 72))
    right = width - int(safe.get("right", 72))
    top = int(safe.get("top", 120))
    bottom = height - int(safe.get("bottom", 210))

    if rect["x"] < 0 or rect["y"] < 0 or rect["x"] + rect["width"] > width or rect["y"] + rect["height"] > height:
        return False, ["box_outside_canvas"]
    if rect["x"] < left or rect["x"] + rect["width"] > right or rect["y"] + rect["height"] > bottom:
        return False, ["box_outside_safe_area"]
    if rect["y"] < top:
        if compact:
            warnings.append("compact_banner_above_default_top_safe_area; allowed for talking-head face clearance")
        else:
            return False, ["box_above_top_safe_area"]
    return True, warnings


def estimate_subtitle_rect(style: dict, line_count: int | None = None) -> dict:
    canvas = style.get("canvas", {})
    subtitle = style.get("subtitle", {})
    width = int(canvas.get("width", 1080))
    height = int(canvas.get("height", 1920))
    horizontal = int(subtitle.get("horizontal_margin_px", 72))
    font_size = int(subtitle.get("font_size_px", 76))
    max_lines = int(subtitle.get("line_count_max", 2))
    lines = min(line_count or max_lines, max_lines)
    box_height = math.ceil(font_size * 1.28 * max(1, lines))
    bottom_margin = int(subtitle.get("bottom_margin_px", 240))
    return {
        "x": horizontal,
        "y": height - bottom_margin - box_height,
        "width": width - horizontal * 2,
        "height": box_height,
    }


def get_subtitle_cues(path: Path) -> list[dict]:
    payload = read_json(path, {})
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        cues = payload.get("cues", [])
        if isinstance(cues, list):
            return cues
    return []


def get_subtitle_payload(path: Path) -> dict:
    payload = read_json(path, {})
    return payload if isinstance(payload, dict) else {"alignment_method": "", "cues": payload if isinstance(payload, list) else []}


def cue_text(cue: dict) -> str:
    for key in ("text", "subtitle", "caption", "line"):
        value = cue.get(key)
        if isinstance(value, str):
            return value
    return ""


def cue_line_count(cue: dict, soft_chars: int) -> int:
    explicit = cue.get("subtitle_line_count") or cue.get("line_count")
    if explicit:
        return int(to_float(explicit, 0))
    text = cue_text(cue)
    if "\n" in text:
        return len([line for line in text.splitlines() if line.strip()])
    normalized = normalize_text(text)
    if not normalized:
        return 0
    return max(1, math.ceil(len(normalized) / max(1, soft_chars)))


def total_duration_from_manifest(rows: list[dict]) -> float:
    max_end = 0.0
    for row in rows:
        start = to_float(row.get("start"))
        end = to_float(row.get("end"))
        duration = to_float(row.get("duration"))
        if end:
            max_end = max(max_end, end)
        elif duration:
            max_end = max(max_end, start + duration)
    return max_end


def selected_banner_text(topic: dict) -> tuple[str, str]:
    selected = topic.get("selected_banner", {}) if isinstance(topic, dict) else {}
    return str(selected.get("main", "") or ""), str(selected.get("sub", "") or "")


def audit_design_boxes(shot_plan: dict, subtitle_rect: dict) -> list[dict]:
    failures: list[dict] = []
    shots = shot_plan.get("shots", []) if isinstance(shot_plan, dict) else []
    for shot in shots:
        shot_id = shot.get("shot_id") or shot.get("shot") or ""
        containers: list[Any] = []
        overlay_plan = shot.get("overlay_layer_plan")
        design_plan = shot.get("design_plan")
        if isinstance(overlay_plan, dict):
            containers.extend(overlay_plan.get("screen_elements", []) or [])
            containers.extend(overlay_plan.get("boxes", []) or [])
        if isinstance(design_plan, dict):
            containers.extend(design_plan.get("screen_elements", []) or [])
            containers.extend(design_plan.get("boxes", []) or [])
        for index, element in enumerate(containers):
            if not isinstance(element, dict):
                continue
            if not all(key in element for key in ("x", "y", "width", "height")):
                continue
            rect = {key: int(to_float(element.get(key))) for key in ("x", "y", "width", "height")}
            if rect_overlap(rect, subtitle_rect):
                failures.append(
                    {
                        "code": "design_card_overlaps_subtitle_area",
                        "shot_id": shot_id,
                        "element_index": index,
                        "box": rect,
                    }
                )
    return failures


def main():
    parser = argparse.ArgumentParser(description="Audit short-video style/layout plan before final rendering.")
    parser.add_argument("project_dir", help="Short-video project directory")
    args = parser.parse_args()

    root = Path(args.project_dir).expanduser().resolve()
    plan_dir = root / "work" / "plan"

    style_path = plan_dir / "style_contract.json"
    topic_path = plan_dir / "video_topic.json"
    cues_path = plan_dir / "subtitle_cues.json"
    shot_plan_path = plan_dir / "shot_plan.json"
    manifest_path = plan_dir / "edit_manifest.csv"

    style = read_json(style_path, {})
    topic = read_json(topic_path, {})
    subtitle_payload = get_subtitle_payload(cues_path)
    cues = get_subtitle_cues(cues_path)
    shot_plan = read_json(shot_plan_path, {})
    manifest_rows = read_manifest(manifest_path)

    failures: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    if not style:
        failures.append({"code": "missing_style_contract", "path": str(style_path)})
    if not isinstance(style, dict):
        style = {}

    canvas = style.get("canvas", {})
    safe = canvas.get("safe_area", {})
    subtitle = style.get("subtitle", {})
    banner = style.get("persistent_topic_banner", {})
    enabled_banner = bool(banner.get("enabled", False))
    required_banner = bool(banner.get("required_for_final_render", False))

    font_size = int(to_float(subtitle.get("font_size_px"), 0))
    min_font = int(to_float(subtitle.get("font_size_min_px"), 68))
    max_lines = int(to_float(subtitle.get("line_count_max"), 2))
    soft_chars = int(to_float(subtitle.get("chars_per_line_soft_max"), 14))
    cue_target_min = int(to_float(subtitle.get("chars_per_cue_target_min"), 6))
    cue_target_max = int(to_float(subtitle.get("chars_per_cue_target_max"), 14))
    cue_hard_max = int(to_float(subtitle.get("chars_per_cue_hard_max"), 18))
    subtitle_rect = estimate_subtitle_rect(style)

    if font_size < min_font:
        failures.append({"code": "subtitle_font_below_min", "font_size_px": font_size, "font_size_min_px": min_font})
    checks.append({"name": "subtitle_min_size", "status": "passed" if font_size >= min_font else "failed"})

    subtitle_inside, subtitle_safe_warnings = rect_inside_canvas_and_safe(subtitle_rect, canvas, safe)
    if not subtitle_inside:
        failures.append({"code": "subtitle_box_outside_safe_area", "box": subtitle_rect})
    for warning in subtitle_safe_warnings:
        warnings.append({"code": warning, "box": subtitle_rect})
    checks.append({"name": "subtitle_safe_area", "status": "passed" if subtitle_inside else "failed"})

    subtitle_failures: list[dict] = []
    long_cue_failures: list[dict] = []
    alignment_method = str(subtitle_payload.get("alignment_method", "") or "")
    allowed_alignment_methods = {
        "asr_word_timestamps",
        "asr_word",
        "forced_alignment",
        "phrase_timestamps",
        "manual_phrase_timestamps",
        "manual_phrase",
        "manual_timestamp",
    }
    if alignment_method == "script_length_proportional_draft_only":
        item = {
            "code": "final_render_blocked_draft_alignment_only",
            "alignment_method": alignment_method,
            "allowed_output": "output/draft_preview.mp4",
            "blocked_output": "output/final.mp4",
        }
        subtitle_failures.append(item)
        failures.append(item)
    elif alignment_method and alignment_method not in allowed_alignment_methods:
        item = {
            "code": "subtitle_alignment_method_not_audio_derived",
            "alignment_method": alignment_method,
            "allowed_methods": sorted(allowed_alignment_methods),
        }
        subtitle_failures.append(item)
        failures.append(item)
    if not cues:
        item = {
            "code": "missing_subtitle_cues_for_final",
            "path": str(cues_path),
        }
        subtitle_failures.append(item)
        failures.append(item)
    for cue in cues:
        text = cue_text(cue)
        line_count = cue_line_count(cue, soft_chars)
        cue_id = cue.get("cue_id") or cue.get("id") or ""
        cue_norm_len = len(normalize_text(text))
        alignment_source = str(cue.get("alignment_source", "") or "")
        sync_confidence = str(cue.get("sync_confidence", "") or "").lower()
        start_sec = cue.get("start_sec", cue.get("start"))
        end_sec = cue.get("end_sec", cue.get("end"))
        has_audio_timing = to_float(end_sec, -1) > to_float(start_sec, -1) >= 0
        source_is_audio_derived = (
            alignment_source in allowed_alignment_methods
            or alignment_method in allowed_alignment_methods
        )
        if not has_audio_timing or not source_is_audio_derived:
            item = {
                "code": "subtitle_cue_missing_audio_derived_timing",
                "cue_id": cue_id,
                "alignment_method": alignment_method,
                "alignment_source": alignment_source,
                "start": start_sec,
                "end": end_sec,
            }
            subtitle_failures.append(item)
            failures.append(item)
        if sync_confidence in {"low", "very_low", "proportional", "draft"}:
            item = {
                "code": "subtitle_cue_low_sync_confidence",
                "cue_id": cue_id,
                "sync_confidence": sync_confidence,
            }
            subtitle_failures.append(item)
            failures.append(item)
        if contains_visible_punctuation(text) and not cue.get("punctuation_semantic_required", False):
            item = {
                "code": "subtitle_visible_punctuation_not_removed",
                "cue_id": cue_id,
                "text": text,
            }
            subtitle_failures.append(item)
            failures.append(item)
        if cue_norm_len > cue_hard_max and not cue.get("allow_long_named_entity", False):
            item = {
                "code": "subtitle_cue_too_long_for_burned_caption",
                "cue_id": cue_id,
                "chars": cue_norm_len,
                "hard_max": cue_hard_max,
                "target": f"{cue_target_min}-{cue_target_max}",
                "text": text,
            }
            subtitle_failures.append(item)
            failures.append(item)
        if line_count > max_lines:
            item = {
                "code": "subtitle_exceeds_line_count",
                "cue_id": cue_id,
                "line_count": line_count,
                "max_lines": max_lines,
                "text": text,
            }
            subtitle_failures.append(item)
            failures.append(item)
        hard_capacity = min(soft_chars * max_lines + 4, cue_hard_max)
        if subtitle.get("forbid_shrinking_below_min", True) and len(normalize_text(text)) > hard_capacity:
            item = {
                "code": "long_subtitle_requires_semantic_split",
                "cue_id": cue_id,
                "chars": len(normalize_text(text)),
                "hard_capacity": hard_capacity,
                "text": text,
            }
            long_cue_failures.append(item)
            subtitle_failures.append(item)
            failures.append(item)

    main_title, sub_title = selected_banner_text(topic)
    topic_status = "passed"
    topic_failures: list[dict] = []
    topic_warnings: list[dict] = []
    total_duration = total_duration_from_manifest(manifest_rows)

    if not enabled_banner:
        topic_status = "user_disabled"
        checks.append({"name": "topic_banner", "status": "user_disabled"})
    else:
        if required_banner and not (main_title or sub_title):
            item = {"code": "required_topic_banner_missing", "path": str(topic_path)}
            topic_failures.append(item)
            failures.append(item)

        if banner.get("visible_start_sec", 0) > 0:
            item = {"code": "topic_banner_does_not_start_at_zero", "visible_start_sec": banner.get("visible_start_sec")}
            topic_failures.append(item)
            failures.append(item)
        if total_duration > 0 and banner.get("visible_end_policy") != "full_duration":
            visible_end = to_float(banner.get("visible_end_sec"), 0)
            if visible_end < total_duration:
                item = {
                    "code": "topic_banner_does_not_cover_full_duration",
                    "visible_end_sec": visible_end,
                    "total_duration_sec": total_duration,
                }
                topic_failures.append(item)
                failures.append(item)

        position = banner.get("position", {})
        banner_rect = {
            "x": int(to_float(position.get("x"), 0)),
            "y": int(to_float(position.get("y"), 0)),
            "width": int(to_float(position.get("width"), 0)),
            "height": int(to_float(position.get("height"), 0)),
        }
        banner_inside, banner_safe_warnings = rect_inside_canvas_and_safe(banner_rect, canvas, safe)
        if not banner_inside:
            item = {"code": "topic_banner_outside_safe_area", "box": banner_rect}
            topic_failures.append(item)
            failures.append(item)
        for warning in banner_safe_warnings:
            topic_warnings.append({"code": warning, "box": banner_rect})

        compact_position = banner.get("compact_position_for_talking_head", {})
        if compact_position:
            compact_rect = {
                "x": int(to_float(compact_position.get("x"), 0)),
                "y": int(to_float(compact_position.get("y"), 0)),
                "width": int(to_float(compact_position.get("width"), 0)),
                "height": int(to_float(compact_position.get("height"), 0)),
            }
            compact_inside, compact_warnings = rect_inside_canvas_and_safe(compact_rect, canvas, safe, compact=True)
            if not compact_inside:
                item = {"code": "compact_topic_banner_outside_safe_area", "box": compact_rect}
                topic_failures.append(item)
                failures.append(item)
            for warning in compact_warnings:
                topic_warnings.append({"code": warning, "box": compact_rect})

        if rect_overlap(banner_rect, subtitle_rect):
            item = {"code": "topic_banner_overlaps_subtitle", "banner_box": banner_rect, "subtitle_box": subtitle_rect}
            topic_failures.append(item)
            failures.append(item)

        if banner.get("must_not_duplicate_current_subtitle", True):
            banner_norms = [normalize_text(main_title), normalize_text(sub_title)]
            for cue in cues:
                cue_norm = normalize_text(cue_text(cue))
                if not cue_norm:
                    continue
                for banner_norm in banner_norms:
                    if not banner_norm:
                        continue
                    exact = cue_norm == banner_norm
                    near = len(banner_norm) >= 8 and (banner_norm in cue_norm or cue_norm in banner_norm)
                    if exact or near:
                        item = {
                            "code": "topic_banner_duplicates_subtitle",
                            "cue_id": cue.get("cue_id") or cue.get("id") or "",
                            "banner_text": main_title if banner_norm == banner_norms[0] else sub_title,
                            "subtitle_text": cue_text(cue),
                        }
                        topic_failures.append(item)
                        failures.append(item)
        topic_status = "failed" if topic_failures else "passed"
        checks.append({"name": "topic_banner", "status": topic_status})

    design_failures = audit_design_boxes(shot_plan, subtitle_rect)
    failures.extend(design_failures)
    checks.append({"name": "design_cards_subtitle_clearance", "status": "passed" if not design_failures else "failed"})

    subtitle_status = "failed" if subtitle_failures or any(item.get("code", "").startswith("subtitle_") for item in failures) else "passed"
    layout_status = "failed" if failures else "passed"

    layout_report = {
        "status": layout_status,
        "project_dir": str(root),
        "style_contract": str(style_path),
        "video_topic": str(topic_path),
        "total_duration_sec": total_duration,
        "checks": checks,
        "failures": failures,
        "warnings": warnings + topic_warnings,
        "computed_boxes": {
            "subtitle": subtitle_rect,
            "topic_banner": banner.get("position", {}) if isinstance(banner, dict) else {},
            "compact_topic_banner": banner.get("compact_position_for_talking_head", {}) if isinstance(banner, dict) else {},
        },
    }

    topic_audit = {
        "status": topic_status,
        "enabled": enabled_banner,
        "user_disabled": not enabled_banner,
        "required_for_final_render": required_banner,
        "selected_banner": {"main": main_title, "sub": sub_title},
        "coverage": {
            "visible_start_sec": banner.get("visible_start_sec") if isinstance(banner, dict) else None,
            "visible_end_policy": banner.get("visible_end_policy") if isinstance(banner, dict) else None,
            "total_duration_sec": total_duration,
        },
        "failures": topic_failures,
        "warnings": topic_warnings,
    }

    subtitle_audit = {
        "status": subtitle_status,
        "font_size_px": font_size,
        "font_size_min_px": min_font,
        "line_count_max": max_lines,
        "chars_per_line_soft_max": soft_chars,
        "chars_per_cue_target_min": cue_target_min,
        "chars_per_cue_target_max": cue_target_max,
        "chars_per_cue_hard_max": cue_hard_max,
        "alignment_method": alignment_method,
        "final_render_blocked": any(item.get("code") == "final_render_blocked_draft_alignment_only" for item in subtitle_failures),
        "allowed_output_when_blocked": "output/draft_preview.mp4",
        "cue_count": len(cues),
        "subtitle_box": subtitle_rect,
        "failures": subtitle_failures
        + [item for item in failures if item.get("code") in {"subtitle_font_below_min", "subtitle_box_outside_safe_area"}],
        "warnings": [],
    }

    write_json(plan_dir / "layout_qc_report.json", layout_report)
    write_json(plan_dir / "topic_banner_audit.json", topic_audit)
    write_json(plan_dir / "subtitle_style_audit.json", subtitle_audit)

    print(plan_dir / "layout_qc_report.json")
    print(f"status: {layout_status}")
    if failures:
        for failure in failures[:12]:
            print(f"FAIL {failure.get('code')}: {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
