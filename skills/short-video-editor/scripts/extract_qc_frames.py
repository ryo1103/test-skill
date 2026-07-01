#!/usr/bin/env python3
"""Extract QC frames and an optional contact sheet from an MP4 with ffmpeg."""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


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


def probe_duration(ffmpeg: str, video: Path) -> float:
    result = run([ffmpeg, "-hide_banner", "-i", str(video)])
    text = result.stderr + result.stdout
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_timestamps(value: str | None) -> list[float]:
    if not value:
        return []
    timestamps: list[float] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        timestamps.append(max(0.0, float(part)))
    return timestamps


def timestamps_from_every(duration: float, every_sec: float) -> list[float]:
    if duration <= 0:
        return [0.0]
    every_sec = max(0.25, every_sec)
    count = max(1, int(math.floor(duration / every_sec)) + 1)
    timestamps = [round(index * every_sec, 3) for index in range(count)]
    if timestamps[-1] > duration:
        timestamps[-1] = max(0.0, duration - 0.05)
    elif duration - timestamps[-1] > every_sec * 0.75:
        timestamps.append(max(0.0, duration - 0.05))
    return sorted(set(timestamps))


def extract_frame(ffmpeg: str, video: Path, timestamp: float, output: Path) -> None:
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output),
    ]
    result = run(cmd)
    if result.returncode != 0 or not output.exists():
        raise RuntimeError(f"ffmpeg failed extracting {timestamp:.3f}s: {result.stderr.strip()}")


def make_contact_sheet(ffmpeg: str, out_dir: Path, contact_sheet: Path, columns: int, thumb_width: int) -> None:
    frames = sorted(out_dir.glob("frame_*.png"))
    if not frames:
        raise RuntimeError("No extracted frames available for contact sheet.")
    columns = max(1, columns)
    rows = max(1, math.ceil(len(frames) / columns))
    pattern = out_dir / "frame_%03d.png"
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        "1",
        "-i",
        str(pattern),
        "-vf",
        f"scale={thumb_width}:-1,tile={columns}x{rows}",
        "-frames:v",
        "1",
        str(contact_sheet),
    ]
    result = run(cmd)
    if result.returncode != 0 or not contact_sheet.exists():
        raise RuntimeError(f"ffmpeg failed creating contact sheet: {result.stderr.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract representative QC frames from an MP4.")
    parser.add_argument("video", help="Input MP4/video path")
    parser.add_argument("--out-dir", required=True, help="Output frame directory")
    parser.add_argument("--every-sec", type=float, default=5.0, help="Sample every N seconds when --timestamps is not set")
    parser.add_argument("--timestamps", help="Comma-separated timestamps in seconds, e.g. 0,3,8")
    parser.add_argument("--contact-sheet", help="Optional contact sheet PNG path")
    parser.add_argument("--columns", type=int, default=4, help="Contact sheet columns")
    parser.add_argument("--thumb-width", type=int, default=270, help="Contact sheet thumbnail width")
    args = parser.parse_args()

    ffmpeg = find_ffmpeg()
    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        print(f"Input video not found: {video}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("frame_*.png"):
        old.unlink()

    timestamps = parse_timestamps(args.timestamps)
    if not timestamps:
        duration = probe_duration(ffmpeg, video)
        timestamps = timestamps_from_every(duration, args.every_sec)

    for index, timestamp in enumerate(timestamps):
        extract_frame(ffmpeg, video, timestamp, out_dir / f"frame_{index:03d}.png")

    if args.contact_sheet:
        make_contact_sheet(ffmpeg, out_dir, Path(args.contact_sheet).expanduser().resolve(), args.columns, args.thumb_width)

    print(f"Extracted {len(timestamps)} frame(s) to {out_dir}")
    if args.contact_sheet:
        print(Path(args.contact_sheet).expanduser().resolve())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
