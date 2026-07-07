from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...stages.common import media_metadata


PROVIDER_LADDER = ["asset_library", "mixkit", "pexels", "pixabay", "coverr", "videvo", "wikimedia_commons", "openverse"]
ALLOWED_EXTERNAL_PROVENANCE = {"asset_library", "stock_provider", "open_license_provider", "official_media", "public_domain"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


@dataclass
class ProviderAttempt:
    provider: str
    status: str
    query: str
    message: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "status": self.status, "query": self.query, "message": self.message}


class BaseAssetProvider:
    name = "base"
    requires_api_key = False
    api_key_env: str | None = None
    max_download_bytes = 8 * 1024 * 1024
    max_download_seconds = 15

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def configured(self) -> bool:
        return not self.requires_api_key or bool(self.api_key_env and os.environ.get(self.api_key_env))

    def search(self, query: str, wanted_visuals: list[str], avoid_visuals: list[str], required_entities: list[str], limit: int) -> list[dict[str, Any]]:
        del query, wanted_visuals, avoid_visuals, required_entities, limit
        return []

    def download(self, candidate: dict[str, Any], target_dir: Path) -> Path | None:
        target_dir.mkdir(parents=True, exist_ok=True)
        local_path = candidate.get("local_path") or candidate.get("path")
        if local_path:
            source = resolve_path(self.project_dir, local_path)
            if source.exists() and source.is_file():
                target = target_dir / source.name
                if source.resolve() != target.resolve():
                    shutil.copy2(source, target)
                return target
        url = str(candidate.get("download_url") or candidate.get("direct_download_url") or "")
        if url.startswith(("http://", "https://")):
            suffix = Path(url.split("?", 1)[0]).suffix or ".mp4"
            target = target_dir / f"{self.name}_{sha256_text(url)[:12]}{suffix}"
            max_bytes = int(candidate.get("max_download_bytes") or self.max_download_bytes)
            max_seconds = int(candidate.get("max_download_seconds") or self.max_download_seconds)
            curl = shutil.which("curl")
            if curl:
                result = subprocess.run(
                    [
                        curl,
                        "-L",
                        "--fail",
                        "--silent",
                        "--show-error",
                        "--max-time",
                        str(max_seconds),
                        "--max-filesize",
                        str(max_bytes),
                        "-A",
                        "short-video-engine/0.1 (asset sourcing)",
                        "-o",
                        str(target),
                        url,
                    ],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=max_seconds + 5,
                )
                if result.returncode != 0 or not target.exists() or target.stat().st_size <= 0:
                    target.unlink(missing_ok=True)
                    return None
                return target
            request = urllib.request.Request(url, headers={"User-Agent": "short-video-engine/0.1 (asset sourcing)"})
            deadline = time.monotonic() + max_seconds
            with urllib.request.urlopen(request, timeout=20) as response, target.open("wb") as handle:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_bytes:
                    return None
                copied = 0
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    copied += len(chunk)
                    if copied > max_bytes:
                        handle.close()
                        target.unlink(missing_ok=True)
                        return None
                    if time.monotonic() > deadline:
                        handle.close()
                        target.unlink(missing_ok=True)
                        return None
                    handle.write(chunk)
            return target
        return None

    def normalize_metadata(self, candidate: dict[str, Any], local_path: Path) -> dict[str, Any]:
        metadata, error = probe_and_decode(local_path)
        if metadata is None:
            raise ValueError(error)
        source_key = str(candidate.get("source_key") or candidate.get("provider_asset_id") or candidate.get("source_url") or candidate.get("direct_download_url") or sha256_file(local_path))
        return {
            "asset_key": str(candidate.get("asset_key") or f"{self.name}_{sha256_text(source_key)[:16]}"),
            "shot_id": str(candidate.get("shot_id") or ""),
            "provider": self.name,
            "media_class": "video_broll",
            "source_key": source_key,
            "provider_asset_id": str(candidate.get("provider_asset_id") or source_key),
            "source_url": str(candidate.get("source_url") or ""),
            "direct_download_url": str(candidate.get("direct_download_url") or ""),
            "local_path": str(local_path),
            "sha256": sha256_file(local_path),
            "duration_sec": metadata["container_duration"] or metadata["video_stream_duration"] or metadata["audio_stream_duration"],
            "width": metadata["resolution"]["width"],
            "height": metadata["resolution"]["height"],
            "fps": metadata["fps"],
            "license_or_note": str(candidate.get("license_or_note") or candidate.get("license") or "unknown external source"),
            "external_source": True,
            "provenance_type": str(candidate.get("provenance_type") or "stock_provider"),
            "materialized_status": "passed",
            "ffprobe_decode_status": "passed",
            "relevance_status": str(candidate.get("relevance_status") or "pending"),
        }


def resolve_path(project_dir: Path, value: Any) -> Path:
    path = Path(str(value or "")).expanduser()
    return path if path.is_absolute() else project_dir / path


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ffmpeg_decode(path: Path) -> tuple[bool, str]:
    ffmpeg = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "ffmpeg_not_found"
    try:
        result = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-map", "0:v:0", "-frames:v", "1", "-f", "null", "-"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    except subprocess.TimeoutExpired:
        return False, "ffmpeg_decode_timeout"
    if result.returncode != 0:
        return False, result.stderr.strip() or "ffmpeg_decode_failed"
    return True, ""


def probe_and_decode(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
        return None, "missing_or_empty_local_video"
    metadata, error = media_metadata(path)
    if metadata is None:
        return None, error
    if metadata["resolution"]["width"] <= 0 or metadata["resolution"]["height"] <= 0:
        return None, "missing_video_resolution"
    if (metadata["container_duration"] or metadata["video_stream_duration"] or metadata["audio_stream_duration"]) <= 0:
        return None, "missing_video_duration"
    if metadata["fps"] <= 0:
        return None, "missing_fps"
    ok, decode_error = ffmpeg_decode(path)
    if not ok:
        return None, decode_error
    return metadata, ""


def looks_like_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS
