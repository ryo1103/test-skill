from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request

from ...contracts import read_json
from ...paths import plan_dir
from .base import BaseAssetProvider, looks_like_video, resolve_path


class AssetLibraryProvider(BaseAssetProvider):
    name = "asset_library"
    max_search_seconds = 25

    def search(self, query: str, wanted_visuals: list[str], avoid_visuals: list[str], required_entities: list[str], limit: int) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        candidates.extend(self.search_remote(query, wanted_visuals, required_entities, limit))
        if len(candidates) < limit:
            candidates.extend(self.search_local(wanted_visuals, avoid_visuals, required_entities, limit - len(candidates)))
        return candidates[:limit]

    def search_remote(self, query: str, wanted_visuals: list[str], required_entities: list[str], limit: int) -> list[dict[str, Any]]:
        base_url = asset_library_base_url(self.project_dir)
        if not base_url:
            return []
        queries = remote_queries(self.project_dir, query, wanted_visuals, required_entities)
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        deadline = time.monotonic() + self.max_search_seconds
        for search_query in queries:
            if time.monotonic() > deadline:
                break
            payload = {"query": search_query[:200], "limit": min(max(limit * 3, 12), 50), "filters": {"max_duration_ms": 120000}}
            request = urllib.request.Request(
                urllib.parse.urljoin(base_url + "/", "search"),
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "short-video-engine/0.1"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=6) as response:
                    data = json.loads(response.read().decode("utf-8"))
            except Exception:
                continue
            search_id = str(data.get("search_id") or "")
            for index, item in enumerate(data.get("results") or [], start=1):
                if not isinstance(item, dict) or item.get("media_type") != "video":
                    continue
                asset_id = str(item.get("asset_id") or "")
                if not asset_id or asset_id in seen:
                    continue
                seen.add(asset_id)
                download_url = str(item.get("download_url") or "")
                if download_url.startswith("/"):
                    download_url = urllib.parse.urljoin(base_url + "/", download_url.lstrip("/"))
                if not download_url:
                    download_url = urllib.parse.urljoin(base_url + "/", f"assets/{asset_id}/download?{urllib.parse.urlencode({'search_id': search_id, 'rank': index})}")
                canonical_download_url = urllib.parse.urljoin(base_url + "/", f"assets/{asset_id}/download")
                results.append(
                    {
                        "provider": self.name,
                        "asset_key": f"asset_library_{asset_id}",
                        "provider_asset_id": asset_id,
                        "source_key": asset_id,
                        "source_url": urllib.parse.urljoin(base_url + "/", f"assets/{asset_id}"),
                        "direct_download_url": canonical_download_url,
                        "download_url": download_url,
                        "license_or_note": "asset_library cloud source",
                        "provenance_type": "asset_library",
                        "title": f"{item.get('theme', '')} {item.get('sub_theme', '')}".strip(),
                        "description": str(item.get("caption") or ""),
                        "tags": " ".join([str(item.get("theme") or ""), str(item.get("sub_theme") or ""), " ".join(str(x) for x in item.get("match_reason") or [])]),
                        "semantic_query": search_query,
                        "match_reason": item.get("match_reason") or [],
                        "search_score": item.get("score"),
                        "max_download_bytes": max(int(item.get("size_bytes") or 0), 1) + 1024,
                        "max_download_seconds": 30,
                    }
                )
                if len(results) >= limit:
                    return results
        return results

    def search_local(self, wanted_visuals: list[str], avoid_visuals: list[str], required_entities: list[str], limit: int) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        index_paths = [
            self.project_dir / "assets" / "library" / "asset_index.json",
            self.project_dir / "assets_library" / "asset_index.json",
            self.project_dir / "assets" / "metadata" / "asset_library_index.json",
        ]
        for index_path in index_paths:
            payload = read_json(index_path, [])
            items = payload.get("assets") if isinstance(payload, dict) else payload
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        candidates.append({**item, "provider": self.name})
        for directory in [self.project_dir / "assets" / "library" / "video", self.project_dir / "assets_library" / "video"]:
            if directory.exists():
                for path in sorted(directory.iterdir()):
                    if path.is_file() and looks_like_video(path):
                        candidates.append(
                            {
                                "provider": self.name,
                                "local_path": str(path),
                                "source_url": f"asset-library://{path.name}",
                                "source_key": f"asset-library://{path.name}",
                                "license_or_note": "local asset library",
                                "provenance_type": "asset_library",
                            }
                        )
        filtered = []
        for candidate in candidates:
            local_path = resolve_path(self.project_dir, candidate.get("local_path") or candidate.get("path"))
            if local_path.exists() and local_path.is_file() and relevance_matches(candidate, wanted_visuals, avoid_visuals, required_entities):
                filtered.append(candidate)
            if len(filtered) >= limit:
                break
        return filtered


def asset_library_base_url(project_dir: Path) -> str:
    value = os.environ.get("ASSET_LIBRARY_BASE_URL", "").strip()
    if value:
        return value.rstrip("/")
    for env_path in [project_dir / ".env", project_dir / ".env.example"]:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("ASSET_LIBRARY_BASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
    return ""


def remote_queries(project_dir: Path, query: str, wanted_visuals: list[str], required_entities: list[str]) -> list[str]:
    terms = []
    entity_text = " ".join(required_entities).strip()
    wanted_text = " ".join(wanted_visuals).replace("real relevant B-roll footage", "").replace("real B-roll base with", "").strip()
    global_text = project_topic_text(project_dir)
    extracted = extracted_project_queries(query, global_text, required_entities)
    terms.extend(extracted)
    if query:
        terms.append(query)
    if entity_text:
        terms.append(entity_text)
        terms.extend(entity_expansions(required_entities))
    if wanted_text:
        terms.append(wanted_text)
    if not extracted:
        terms.extend(["technology close up", "industrial equipment", "data center hardware"])
    result = []
    seen = set()
    for term in terms:
        normalized = " ".join(str(term).split())
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result[:10]


def project_topic_text(project_dir: Path) -> str:
    chunks: list[str] = []
    intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
    script_path_value = str(intake.get("script_path") or "script.txt") if isinstance(intake, dict) else "script.txt"
    script_path = Path(script_path_value)
    if not script_path.is_absolute():
        script_path = project_dir / script_path
    if script_path.exists() and script_path.is_file():
        chunks.append(script_path.read_text(encoding="utf-8", errors="ignore"))
    for path in [plan_dir(project_dir) / "script_units.json", plan_dir(project_dir) / "shot_plan.json"]:
        payload = read_json(path, {})
        if not isinstance(payload, dict):
            continue
        for key in ("units", "shots"):
            items = payload.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        chunks.extend(str(item.get(field) or "") for field in ("original_text", "source_text", "script_fragment"))
                        chunks.extend(str(value) for value in item.get("required_entities") or [] if value)
    return " ".join(chunks)


def extracted_project_queries(query: str, global_text: str, entities: list[str]) -> list[str]:
    text = f"{query} {global_text}"
    terms: list[str] = []
    terms.extend(chinese_domain_terms(text))
    terms.extend(context_phrases(text))
    terms.extend(english_terms(text))
    terms.extend(entity_expansions(entities))
    terms.extend(term_expansions(terms))
    return prioritize_terms_for_query(unique_texts(terms), query)


def prioritize_terms_for_query(terms: list[str], query: str) -> list[str]:
    query_lc = query.lower()
    direct: list[str] = []
    rest: list[str] = []
    for term in terms:
        if term.lower() in query_lc or term in query:
            direct.append(term)
        else:
            rest.append(term)
    return direct + rest


def english_terms(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", text)
    result: list[str] = []
    ignored = {
        "real",
        "relevant",
        "roll",
        "footage",
        "base",
        "with",
        "broll",
        "fullscreen",
        "before",
        "after",
        "kpi",
        "change",
        "timeline",
        "process",
        "comparison",
        "split",
        "screen",
        "cause",
        "effect",
        "chain",
        "motion",
        "overlay",
        "talking",
        "head",
        "required",
    }
    for token in tokens:
        if token.lower() in ignored:
            continue
        result.append(token)
    return result


def chinese_domain_terms(text: str) -> list[str]:
    protected_terms = [
        "光互连",
        "硅光芯片",
        "硅光",
        "光模块",
        "光纤连接器",
        "光纤",
        "玻璃桥",
        "玻璃基板",
        "精密对准",
        "晶圆制造",
        "晶圆",
        "数据中心",
        "AI数据中心",
        "服务器",
        "半导体",
        "芯片",
        "量产",
        "供应链",
        "客户验证",
        "高精度设备",
    ]
    terms = [term for term in protected_terms if term in text]
    terms.extend(chinese_script_phrases(text))
    return unique_texts(terms)


def chinese_script_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    stopwords = {
        "这个",
        "这种",
        "一个",
        "不是",
        "但是",
        "所以",
        "如果",
        "因为",
        "我们",
        "他们",
        "可能",
        "已经",
        "没有",
        "什么",
        "问题",
        "阶段",
        "时候",
        "方式",
        "公司",
    }
    signal_chars = set("光芯片晶圆数据中心服务器半导体玻璃连接器互连模块供应链量产客户验证设备")
    for chunk in re.split(r"[。！？；，、,.!?;\s]+", text):
        chunk = re.sub(r"[^\u4e00-\u9fff]", "", chunk)
        if len(chunk) < 2:
            continue
        for size in range(min(8, len(chunk)), 1, -1):
            for start in range(0, len(chunk) - size + 1):
                phrase = chunk[start : start + size]
                if phrase in stopwords:
                    continue
                if any(char in signal_chars for char in phrase):
                    phrases.append(phrase)
                    break
            if phrases and phrases[-1] in chunk:
                break
    return phrases[:24]


def context_phrases(text: str) -> list[str]:
    compact = re.sub(r"\s+", "", text)
    phrases: list[str] = []
    for match in re.finditer(r"(光纤|芯片|晶圆|数据中心|服务器|半导体|玻璃|光模块)[^。！？；，、,.!?;]{0,10}", compact):
        phrase = match.group(0)
        if 2 <= len(phrase) <= 14:
            phrases.append(phrase)
    return phrases


def entity_expansions(entities: list[str]) -> list[str]:
    text = " ".join(entities).lower()
    terms: list[str] = []
    if "glassbridge" in text:
        terms.extend(["glass bridge optical interconnect", "glass substrate optical interconnect", "fiber to chip optical coupling", "silicon photonics packaging"])
    if "fau" in text:
        terms.extend(["fiber array unit", "fiber optic connector alignment", "optical fiber array", "fiber optic cable connector"])
    if "ai" in text:
        terms.extend(["AI data center server rack", "data center optical network", "GPU server data center"])
    return terms


def term_expansions(terms: list[str]) -> list[str]:
    text = " ".join(terms).lower()
    expansions: list[str] = []
    mapping = {
        "光纤": ["fiber optic cable", "optical fiber"],
        "光纤连接器": ["fiber optic connector"],
        "光互连": ["optical interconnect"],
        "硅光": ["silicon photonics"],
        "光模块": ["optical transceiver"],
        "晶圆": ["semiconductor wafer"],
        "半导体": ["semiconductor manufacturing"],
        "数据中心": ["data center server rack"],
        "服务器": ["server rack cables"],
        "玻璃": ["glass substrate manufacturing"],
        "对准": ["precision alignment equipment"],
        "ai": ["AI data center hardware"],
        "glassbridge": ["glass substrate optical interconnect"],
        "fau": ["fiber array unit"],
    }
    for key, values in mapping.items():
        if key in text:
            expansions.extend(values)
    return expansions


def unique_texts(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(str(value).split())
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def relevance_matches(candidate: dict[str, Any], wanted_visuals: list[str], avoid_visuals: list[str], required_entities: list[str]) -> bool:
    text = " ".join(str(candidate.get(key, "") or "") for key in ("title", "description", "tags", "source_url", "local_path", "path")).lower()
    for avoid in avoid_visuals:
        avoid_text = str(avoid or "").lower()
        if avoid_text and avoid_text in text:
            return False
    for entity in required_entities:
        entity_text = str(entity or "").lower()
        if entity_text and entity_text not in text:
            return False
    if wanted_visuals:
        wanted_joined = " ".join(str(item).lower() for item in wanted_visuals)
        if any(generic in text for generic in ("business meeting", "city skyline", "abstract tech", "stock trading")):
            return any(generic in wanted_joined for generic in ("business meeting", "city skyline", "abstract tech", "stock trading"))
    return True
