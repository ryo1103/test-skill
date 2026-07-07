from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from typing import Any

from .base import BaseAssetProvider


class WikimediaCommonsProvider(BaseAssetProvider):
    name = "wikimedia_commons"

    api_url = "https://commons.wikimedia.org/w/api.php"
    max_download_bytes = 8 * 1024 * 1024
    max_download_seconds = 15

    def search(self, query: str, wanted_visuals: list[str], avoid_visuals: list[str], required_entities: list[str], limit: int) -> list[dict[str, Any]]:
        del wanted_visuals, avoid_visuals
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for term in search_terms(query, required_entities)[:3]:
            for candidate in self.search_commons(term, min(max(limit, 5), 8)):
                key = str(candidate.get("direct_download_url") or candidate.get("source_url") or candidate.get("source_key"))
                if key in seen:
                    continue
                seen.add(key)
                results.append(candidate)
                if len(results) >= limit:
                    return results
        return results

    def search_commons(self, term: str, limit: int) -> list[dict[str, Any]]:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": "6",
            "gsrsearch": term,
            "gsrlimit": str(min(max(limit, 1), 50)),
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
        }
        url = f"{self.api_url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "short-video-engine/0.1 (asset sourcing)"})
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []
        pages = (payload.get("query") or {}).get("pages") or {}
        candidates: list[dict[str, Any]] = []
        for page in pages.values():
            if not isinstance(page, dict):
                continue
            info_items = page.get("imageinfo") or []
            if not info_items or not isinstance(info_items[0], dict):
                continue
            info = info_items[0]
            mime = str(info.get("mime") or "")
            download_url = str(info.get("url") or "")
            size = int(info.get("size") or 0)
            if not mime.startswith("video/") or not download_url or size > self.max_download_bytes:
                continue
            metadata = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
            title = str(page.get("title") or "")
            description = clean_metadata(metadata.get("ImageDescription", {}).get("value") if isinstance(metadata.get("ImageDescription"), dict) else "")
            license_name = clean_metadata(metadata.get("LicenseShortName", {}).get("value") if isinstance(metadata.get("LicenseShortName"), dict) else "")
            categories = clean_metadata(metadata.get("Categories", {}).get("value") if isinstance(metadata.get("Categories"), dict) else "")
            source_url = str(info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}")
            candidates.append(
                {
                    "provider": self.name,
                    "provider_asset_id": str(page.get("pageid") or title),
                    "source_key": title,
                    "source_url": source_url,
                    "direct_download_url": download_url,
                    "license_or_note": f"Wikimedia Commons {license_name or 'license metadata'}",
                    "provenance_type": "open_license_provider",
                    "max_download_bytes": self.max_download_bytes,
                    "max_download_seconds": self.max_download_seconds,
                    "title": title,
                    "description": description,
                    "tags": categories,
                }
            )
        return candidates


def search_terms(query: str, required_entities: list[str]) -> list[str]:
    raw = re.sub(r"\s+", " ", query or "").strip()
    terms: list[str] = []
    english = " ".join(re.findall(r"[A-Za-z][A-Za-z0-9+#.-]+", raw))
    if english and english.lower() not in {"real relevant b-roll footage", "real b-roll base with"}:
        terms.append(f"{english} video")
    entity_text = " ".join(required_entities)
    if "GlassBridge" in entity_text:
        terms.extend(["fiber optic cable video", "optical fiber connector video", "silicon photonics video"])
    if "FAU" in entity_text:
        terms.extend(["fiber optic connector video", "optical fiber cable video"])
    if "AI" in entity_text:
        terms.extend(["data center server video", "computer server room video"])
    terms.extend(
        [
            "fiber optic cable video",
            "optical fiber video",
            "data center video",
            "server room video",
            "semiconductor manufacturing video",
            "glass manufacturing video",
            "telecommunications cable video",
            "computer network video",
        ]
    )
    result: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = term.lower().strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(term)
    return result


def clean_metadata(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()
