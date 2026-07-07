from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Any

from .base import BaseAssetProvider


class MixkitProvider(BaseAssetProvider):
    name = "mixkit"
    max_download_bytes = 18 * 1024 * 1024
    max_download_seconds = 20

    def search(self, query: str, wanted_visuals: list[str], avoid_visuals: list[str], required_entities: list[str], limit: int) -> list[dict[str, Any]]:
        del avoid_visuals
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url, label in mixkit_pages(query, wanted_visuals, required_entities):
            for candidate in self.scrape_page(page_url, label):
                key = str(candidate.get("provider_asset_id") or candidate.get("direct_download_url"))
                if key in seen:
                    continue
                seen.add(key)
                results.append(candidate)
                if len(results) >= limit:
                    return results
        return results

    def scrape_page(self, url: str, label: str) -> list[dict[str, Any]]:
        request = urllib.request.Request(url, headers={"User-Agent": "short-video-engine/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read(1_500_000).decode("utf-8", errors="ignore")
        except Exception:
            return []
        urls = re.findall(r"https://assets\.mixkit\.co/videos/(\d+)/\1-(?:360|720|1080)\.mp4", body)
        candidates: list[dict[str, Any]] = []
        for video_id in unique(urls):
            direct = f"https://assets.mixkit.co/videos/{video_id}/{video_id}-360.mp4"
            candidates.append(
                {
                    "provider": self.name,
                    "provider_asset_id": video_id,
                    "source_key": f"mixkit:{video_id}",
                    "source_url": f"https://mixkit.co/free-stock-video/{video_id}/",
                    "direct_download_url": direct,
                    "license_or_note": "Mixkit free video license",
                    "provenance_type": "stock_provider",
                    "title": f"Mixkit {label}",
                    "description": f"Mixkit free stock video result for {label}",
                    "tags": label,
                    "max_download_bytes": self.max_download_bytes,
                    "max_download_seconds": self.max_download_seconds,
                }
            )
        return candidates


def mixkit_pages(query: str, wanted_visuals: list[str], required_entities: list[str]) -> list[tuple[str, str]]:
    text = " ".join([query, " ".join(wanted_visuals), " ".join(required_entities)]).lower()
    pages: list[tuple[str, str]] = []
    if any(term in text for term in ("fiber", "optic", "glassbridge", "fau", "communication", "network")):
        pages.extend(
            [
                ("https://mixkit.co/free-stock-video/technology/", "technology fiber optic network"),
                ("https://mixkit.co/free-stock-video/data-center/", "data center server network"),
            ]
        )
    if any(term in text for term in ("ai", "server", "data center", "chip", "semiconductor")):
        pages.extend(
            [
                ("https://mixkit.co/free-stock-video/data-center/", "data center server ai"),
                ("https://mixkit.co/free-stock-video/technology/", "technology server ai"),
            ]
        )
    pages.extend(
        [
            ("https://mixkit.co/free-stock-video/technology/", "technology"),
            (f"https://mixkit.co/free-stock-video/?q={urllib.parse.quote_plus(query[:80])}", query[:80]),
        ]
    )
    return unique_pairs(pages)


def unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def unique_pairs(values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for url, label in values:
        if url not in seen:
            seen.add(url)
            result.append((url, label))
    return result
