#!/usr/bin/env python3
"""Render a low-cost probe clip from edit_manifest.csv before full render."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def find_ffmpeg() -> str:
    candidates = [
        os.environ.get("FFMPEG", ""),
        shutil.which("ffmpeg") or "",
        "/Users/admin/.local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("ffmpeg not found. Install ffmpeg or set FFMPEG=/path/to/ffmpeg.")


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def read_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clean_text(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", "", text or "")
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)] + "…"


def ffmpeg_text_escape(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace(",", "\\,")
    text = text.replace("'", "\\'")
    text = text.replace("%", "\\%")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def find_font() -> str:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return ""


def resolve_source(project_dir: Path, row: dict) -> Path | None:
    candidates: list[str] = []
    source_segments = row.get("source_segments") or ""
    for part in re.split(r"[;,]", source_segments):
        part = part.strip().strip('"').strip("'")
        if part:
            candidates.append(part)
    asset_key = row.get("asset_key") or ""
    if asset_key:
        candidates.extend(
            [
                asset_key,
                f"assets/selected/by_shot/{asset_key}",
                f"assets/raw/video/{asset_key}",
                f"assets/processed/{asset_key}",
            ]
        )

    for candidate in candidates:
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            path = project_dir / path
        if path.exists() and path.is_file():
            return path.resolve()
    return None


def row_duration(row: dict) -> float:
    duration = to_float(row.get("duration"))
    if duration > 0:
        return duration
    start = to_float(row.get("start"))
    end = to_float(row.get("end"))
    if end > start:
        return end - start
    source_in = to_float(row.get("source_in"))
    source_out = to_float(row.get("source_out"))
    if source_out > source_in:
        return source_out - source_in
    return 3.0


def classify_row(row: dict) -> set[str]:
    text = " ".join(str(row.get(key, "")) for key in ("visual_mode", "topic_banner_mode", "persistent_overlay_id", "script")).lower()
    labels: set[str] = set()
    if any(token in text for token in ("talking", "head", "oral", "digital", "human", "口播", "数字人")):
        labels.add("talking_head")
    if any(token in text for token in ("broll", "b-roll", "素材", "footage", "video")):
        labels.add("broll")
    if row.get("topic_banner_mode") or row.get("persistent_overlay_id"):
        labels.add("topic_banner")
    if len(re.sub(r"\s+", "", row.get("script", ""))) > 28 or "," in (row.get("subtitle_cue_ids") or ""):
        labels.add("long_subtitle")
    return labels


def select_probe_rows(rows: list[dict], project_dir: Path) -> list[tuple[dict, Path, set[str]]]:
    resolved: list[tuple[dict, Path, set[str]]] = []
    for row in rows:
        source = resolve_source(project_dir, row)
        if source:
            resolved.append((row, source, classify_row(row)))
    if not resolved:
        return []

    wanted = ["talking_head", "broll", "topic_banner", "long_subtitle"]
    selected: list[tuple[dict, Path, set[str]]] = []
    used_ids: set[int] = set()
    for label in wanted:
        for index, item in enumerate(resolved):
            if index not in used_ids and label in item[2]:
                selected.append(item)
                used_ids.add(index)
                break
    for index, item in enumerate(resolved):
        if index in used_ids:
            continue
        selected.append(item)
        used_ids.add(index)
        if sum(min(row_duration(row), 4.0) for row, _, _ in selected) >= 10:
            break

    if not selected:
        selected = resolved[:4]

    total = 0.0
    trimmed: list[tuple[dict, Path, set[str]]] = []
    for item in selected:
        duration = min(row_duration(item[0]), 4.0)
        if total >= 15:
            break
        if total + duration > 15:
            item[0]["duration"] = max(1.0, 15 - total)
        trimmed.append(item)
        total += duration
    return trimmed


def selected_banner(topic: dict) -> tuple[str, str]:
    selected = topic.get("selected_banner", {}) if isinstance(topic, dict) else {}
    return str(selected.get("main", "") or ""), str(selected.get("sub", "") or "")


def build_filter(style: dict, topic: dict, row: dict) -> str:
    canvas = style.get("canvas", {})
    subtitle = style.get("subtitle", {})
    banner = style.get("persistent_topic_banner", {})
    width = int(canvas.get("width", 1080))
    height = int(canvas.get("height", 1920))
    fps = int(canvas.get("fps", 30))
    filters = [f"scale={width}:{height}:force_original_aspect_ratio=increase", f"crop={width}:{height}", f"fps={fps}"]

    font = find_font()
    font_arg = f":fontfile='{ffmpeg_text_escape(font)}'" if font else ""

    if banner.get("enabled", False):
        main, sub = selected_banner(topic)
        position_key = "compact_position_for_talking_head" if (row.get("topic_banner_mode") == "compact") else "position"
        position = banner.get(position_key) or banner.get("position", {})
        x = int(position.get("x", 96))
        y = int(position.get("y", 128))
        w = int(position.get("width", 888))
        h = int(position.get("height", 220))
        padding = int(banner.get("padding_px", 28))
        main_size = int(banner.get("main_font_size_px", 76))
        sub_size = int(banner.get("sub_font_size_px", 60))
        filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=black@0.72:t=fill")
        if main:
            filters.append(
                "drawtext="
                f"text='{ffmpeg_text_escape(clean_text(main, 18))}'{font_arg}:"
                f"x={x + padding}:y={y + padding}:fontsize={main_size}:fontcolor=0x8CFFD9:"
                "borderw=2:bordercolor=black@0.45"
            )
        if sub:
            filters.append(
                "drawtext="
                f"text='{ffmpeg_text_escape(clean_text(sub, 24))}'{font_arg}:"
                f"x={x + padding}:y={y + padding + main_size + 12}:fontsize={sub_size}:fontcolor=white:"
                "borderw=2:bordercolor=black@0.45"
            )

    script = clean_text(row.get("script", ""), 30)
    if script:
        font_size = int(subtitle.get("font_size_px", 76))
        bottom_margin = int(subtitle.get("bottom_margin_px", 240))
        outline = int(subtitle.get("outline_px", 6))
        y_expr = f"h-{bottom_margin}-{font_size}"
        filters.append(
            "drawtext="
            f"text='{ffmpeg_text_escape(script)}'{font_arg}:"
            f"x=(w-text_w)/2:y={y_expr}:fontsize={font_size}:fontcolor=white:"
            f"borderw={outline}:bordercolor=black@0.85"
        )

    return ",".join(filters)


def render_segment(ffmpeg: str, style: dict, topic: dict, row: dict, source: Path, output: Path) -> None:
    duration = max(1.0, min(row_duration(row), 4.0))
    source_in = max(0.0, to_float(row.get("source_in"), 0.0))
    vf = build_filter(style, topic, row)
    base_cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{source_in:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source),
        "-vf",
        vf,
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = run(base_cmd)
    if result.returncode == 0 and output.exists():
        return

    fallback_vf = ",".join(build_filter(style, {}, {"script": ""}).split(",")[:3])
    fallback_cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{source_in:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source),
        "-vf",
        fallback_vf,
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    fallback = run(fallback_cmd)
    if fallback.returncode != 0 or not output.exists():
        raise RuntimeError(f"ffmpeg failed rendering probe segment from {source}: {result.stderr.strip()}")


def concat_segments(ffmpeg: str, segments: list[Path], output: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as list_file:
        for segment in segments:
            escaped_segment = str(segment).replace("'", "'\\''")
            list_file.write(f"file '{escaped_segment}'\n")
        list_path = Path(list_file.name)
    try:
        cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(output)]
        result = run(cmd)
        if result.returncode != 0 or not output.exists():
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr.strip()}")
    finally:
        list_path.unlink(missing_ok=True)


def decode_check(ffmpeg: str, video: Path) -> None:
    result = run([ffmpeg, "-v", "error", "-i", str(video), "-f", "null", "-"])
    if result.returncode != 0:
        raise RuntimeError(f"Probe decode failed: {result.stderr.strip()}")


def extract_probe_frames(project_dir: Path, video: Path) -> None:
    script_path = Path(__file__).resolve().parent / "extract_qc_frames.py"
    out_dir = project_dir / "output" / "qc" / "probe_frames"
    contact = project_dir / "output" / "qc" / "probe_contact_sheet.png"
    cmd = [
        sys.executable,
        str(script_path),
        str(video),
        "--out-dir",
        str(out_dir),
        "--every-sec",
        "2",
        "--contact-sheet",
        str(contact),
    ]
    result = run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Probe frame extraction failed: {result.stderr.strip()}")


def write_probe_report(project_dir: Path, selected: list[tuple[dict, Path, set[str]]], output: Path) -> None:
    report = {
        "status": "passed",
        "probe_render": str(output),
        "selected_segments": [
            {
                "shot_id": row.get("shot_id", ""),
                "source": str(source),
                "labels": sorted(labels),
                "duration": min(row_duration(row), 4.0),
            }
            for row, source, labels in selected
        ],
        "coverage": {
            "talking_head": any("talking_head" in labels for _, _, labels in selected),
            "broll": any("broll" in labels for _, _, labels in selected),
            "topic_banner": any("topic_banner" in labels for _, _, labels in selected),
            "long_subtitle": any("long_subtitle" in labels for _, _, labels in selected),
        },
    }
    (project_dir / "work" / "plan").mkdir(parents=True, exist_ok=True)
    (project_dir / "work" / "plan" / "probe_render_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a low-cost layout probe before final MP4.")
    parser.add_argument("project_dir", help="Short-video project directory")
    parser.add_argument("--min-sec", type=float, default=8.0, help="Target minimum probe duration")
    parser.add_argument("--max-sec", type=float, default=15.0, help="Target maximum probe duration")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    plan_dir = project_dir / "work" / "plan"
    output_dir = project_dir / "output" / "qc"
    output_dir.mkdir(parents=True, exist_ok=True)

    style = read_json(plan_dir / "style_contract.json", {})
    topic = read_json(plan_dir / "video_topic.json", {})
    manifest = read_manifest(plan_dir / "edit_manifest.csv")
    selected = select_probe_rows(manifest, project_dir)
    if not selected:
        print("No usable source media found in edit_manifest.csv for probe render.", file=sys.stderr)
        return 1

    ffmpeg = find_ffmpeg()
    temp_dir = output_dir / "_probe_segments"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        segments: list[Path] = []
        for index, (row, source, _) in enumerate(selected):
            segment_path = temp_dir / f"segment_{index:03d}.mp4"
            render_segment(ffmpeg, style, topic, row, source, segment_path)
            segments.append(segment_path)

        output = output_dir / "probe_render.mp4"
        concat_segments(ffmpeg, segments, output)
        decode_check(ffmpeg, output)
        extract_probe_frames(project_dir, output)
        write_probe_report(project_dir, selected, output)
        print(output)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
