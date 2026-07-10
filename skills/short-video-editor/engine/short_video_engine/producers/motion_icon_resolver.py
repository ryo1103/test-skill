from __future__ import annotations

import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import load_contract, read_json, write_json
from ..paths import plan_dir, skill_root
from ..stage_result import current_command, failure

GENERATOR_VERSION = "motion_icon_generator_v2"
VIEW_BOX = "0 0 24 24"
FORBIDDEN_SVG_RE = re.compile(r"<(?:script|foreignObject|iframe|image|video|audio)\b|\bon\w+\s*=|javascript:|(?:xlink:)?href\s*=\s*['\"](?:https?:|//|data:)", re.I)
ALLOWED_SVG_RE = re.compile(r"</?(?:svg|g|path|rect|circle|ellipse|line|polyline|polygon)\b[^>]*>", re.I)


def resolve_motion_icons(project_dir: Path, assertions_payload: dict[str, Any] | None = None, *, no_network: bool = False) -> tuple[Path, dict[str, Any], list[dict[str, str]]]:
    """Materialize only local SVG icon assets for S4.5. Never inspect S4 assets."""
    assertions_payload = assertions_payload or read_json(plan_dir(project_dir) / "motion_assertions.json", {})
    requests_payload = read_json(plan_dir(project_dir) / "motion_icon_requests.json", {})
    icon_map = load_contract("motion_icon_map.json")
    semantic_map = icon_map.get("semantic_icon_map") if isinstance(icon_map.get("semantic_icon_map"), dict) else {}
    requests = requests_payload.get("requests") if isinstance(requests_payload, dict) else []
    if not isinstance(requests, list):
        requests = requests_from_assertions(assertions_payload, semantic_map)
    generated_root = project_dir / "assets" / "motion" / "icons" / "generated"
    downloaded_root = project_dir / "assets" / "motion" / "icons" / "downloaded"
    public_root = project_dir / "work" / "remotion_public" / "icons"
    for directory in (generated_root, downloaded_root, public_root):
        directory.mkdir(parents=True, exist_ok=True)
    records_by_key: dict[str, dict[str, Any]] = {}
    icons_by_assertion: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    for request in requests:
        if not isinstance(request, dict) or not str(request.get("slot") or ""):
            continue
        semantic_key = str(request.get("semantic_key") or request.get("fallback_semantic_key") or "generic_concept")
        config = semantic_map.get(semantic_key) if isinstance(semantic_map.get(semantic_key), dict) else semantic_map.get("generic_concept", {})
        if semantic_key not in semantic_map:
            semantic_key = "generic_concept" if "generic_concept" in semantic_map else "node"
            config = semantic_map.get(semantic_key, {})
        record = records_by_key.get(semantic_key)
        if record is None:
            record, record_failures = materialize_icon(project_dir, semantic_key, config if isinstance(config, dict) else {}, no_network=no_network)
            records_by_key[semantic_key] = record
            failures.extend(record_failures)
        assertion_id = str(request.get("motion_assertion_id") or "")
        if assertion_id:
            icons_by_assertion.setdefault(assertion_id, {})[str(request["slot"])] = {
                "icon_id": record["icon_id"], "semantic_key": record["semantic_key"], "public_path": record["public_path"],
            }
    payload = {
        "generated_by": "short_video_engine", "engine_version": ENGINE_VERSION, "generator_version": GENERATOR_VERSION,
        "command": " ".join(current_command()), "network_disabled": no_network,
        "usage_policy": "motion_overlay_icons_only_not_s3_broll", "icons": sorted(records_by_key.values(), key=lambda item: item["icon_id"]),
        "icons_by_assertion": icons_by_assertion,
    }
    path = plan_dir(project_dir) / "motion_icon_manifest.json"
    write_json(path, payload)
    write_json(plan_dir(project_dir) / "motion_icon_preparation_report.json", {
        "generated_by": "short_video_engine", "status": "PASS" if not failures else "FINAL_BLOCKED", "icon_count": len(records_by_key),
        "source_types": sorted({item["source_type"] for item in records_by_key.values()}), "failure_codes": [item["code"] for item in failures],
    })
    return path, payload, failures


def requests_from_assertions(assertions_payload: dict[str, Any], semantic_map: dict[str, Any]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for assertion in assertions_payload.get("assertions", []) if isinstance(assertions_payload, dict) else []:
        if not isinstance(assertion, dict):
            continue
        for slot, value in (assertion.get("slots") or {}).items():
            text = str(value.get("text") if isinstance(value, dict) else value or "")
            key = str(value.get("semantic_icon") if isinstance(value, dict) else "") or infer_semantic_key(text, semantic_map)
            requests.append({"request_id": f"icon_request_{len(requests)+1:03d}", "motion_id": assertion.get("motion_id"), "motion_assertion_id": assertion.get("motion_assertion_id"), "slot": slot, "text": text, "semantic_key": key, "required": True, "fallback_semantic_key": "node", "style_family": "monoline_hud"})
    return requests


def materialize_icon(project_dir: Path, semantic_key: str, config: dict[str, Any], *, no_network: bool) -> tuple[dict[str, Any], list[dict[str, str]]]:
    del no_network  # Generated SVG is the production default; remote SVG is intentionally optional.
    local_candidate = skill_root() / "assets" / "motion" / "icons" / f"{semantic_key}.svg"
    source_type = "bundled_svg" if local_candidate.exists() else "generated_svg"
    content = local_candidate.read_text(encoding="utf-8") if local_candidate.exists() else generated_svg(semantic_key)
    if not sanitize_svg(content):
        content, source_type = generated_svg("generic_concept"), "generated_svg"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    filename = f"{sanitize_key(semantic_key)}_{digest[:8]}.svg"
    local_path = project_dir / "assets" / "motion" / "icons" / ("generated" if source_type == "generated_svg" else "bundled") / filename
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(content, encoding="utf-8")
    public_path = project_dir / "work" / "remotion_public" / "icons" / filename
    if not public_path.exists() or hashlib.sha256(public_path.read_bytes()).hexdigest() != digest:
        shutil.copy2(local_path, public_path)
    return ({
        "icon_id": f"motion_icon_{sanitize_key(semantic_key)}_{digest[:8]}", "semantic_key": semantic_key, "source_type": source_type,
        "provider": "short_video_engine" if source_type == "generated_svg" else "bundled_short_video_editor", "icon_collection": "monoline_hud",
        "icon_name": semantic_key, "source_url": "", "license_or_note": "generated_by_short_video_engine" if source_type == "generated_svg" else "bundled_project_icon",
        "attribution": "", "downloaded_at": datetime.now(timezone.utc).isoformat(), "local_path": str(local_path), "public_path": f"icons/{filename}",
        "sha256": digest, "view_box": VIEW_BOX, "style_family": "monoline_hud", "generator_version": GENERATOR_VERSION if source_type == "generated_svg" else "", "sanitization_status": "passed",
    }, [])


def infer_semantic_key(text: str, semantic_map: dict[str, Any]) -> str:
    lowered = text.lower()
    for key, config in semantic_map.items():
        for keyword in config.get("keywords", []) if isinstance(config, dict) else []:
            if str(keyword).lower() in lowered:
                return str(key)
    return "generic_concept" if "generic_concept" in semantic_map else "node"


def sanitize_svg(content: str) -> bool:
    return bool(content and "<svg" in content.lower() and not FORBIDDEN_SVG_RE.search(content) and all(ALLOWED_SVG_RE.fullmatch(tag) for tag in re.findall(r"<[^>]+>", content) if not tag.startswith("<?")))


def generated_svg(semantic_key: str) -> str:
    # Distinct, deterministic monoline silhouettes. No text, media, filters, or remote references.
    shapes = {
        "chip": "<rect x='6' y='6' width='12' height='12' rx='2'/><rect x='9' y='9' width='6' height='6' rx='1'/><path d='M3 8h3M3 12h3M3 16h3M18 8h3M18 12h3M18 16h3M8 3v3M12 3v3M16 3v3M8 18v3M12 18v3M16 18v3'/>",
        "optical_module": "<rect x='3' y='8' width='15' height='8' rx='2'/><path d='M18 10h3v4h-3M6 10h5v4H6M3 11H1m2 2H1'/>",
        "connector": "<path d='M3 12h5m8 0h5'/><rect x='8' y='7' width='8' height='10' rx='2'/><circle cx='12' cy='12' r='2'/><path d='M10 9v6m4-6v6'/>",
        "server": "<rect x='4' y='4' width='16' height='6' rx='1'/><rect x='4' y='14' width='16' height='6' rx='1'/><path d='M7 7h.01M7 17h.01M11 7h6M11 17h6'/>",
        "database": "<ellipse cx='12' cy='5' rx='7' ry='3'/><path d='M5 5v7c0 2 14 2 14 0V5m-14 7v7c0 2 14 2 14 0v-7'/>",
        "input": "<circle cx='5' cy='12' r='3'/><path d='M8 12h12m-4-4 4 4-4 4'/>", "output": "<path d='M4 12h12m-4-4 4 4-4 4'/><circle cx='19' cy='12' r='3'/>",
        "warning": "<path d='M12 3 22 20H2z'/><path d='M12 9v5m0 3h.01'/>", "factory": "<path d='M3 20V9l6 4V9l6 4V5h6v15zM7 20v-4m5 4v-4m5 4v-4'/>",
        "wafer": "<circle cx='12' cy='12' r='8'/><circle cx='12' cy='12' r='3'/><path d='M12 4v3m0 10v3M4 12h3m10 0h3M6.5 6.5l2 2m7 7 2 2m0-11-2 2m-7 7-2 2'/>",
        "fiber": "<path d='M4 17c5-9 9-9 16-10M4 20c5-7 9-7 16-8'/><circle cx='4' cy='18.5' r='2'/><circle cx='20' cy='6.5' r='2'/>",
        "cost": "<circle cx='12' cy='12' r='8'/><path d='M15 9c-1-2-5-2-5 0 0 3 5 1 5 4 0 2-4 2-5 0m2-8v14'/>",
        "efficiency": "<path d='M4 16 9 11l3 3 8-8'/><path d='M15 6h5v5'/><circle cx='6' cy='18' r='2'/>", "risk": "<path d='M3 3h18v18H3z'/><path d='M12 7v6m0 3h.01'/>",
        "trend_up": "<path d='M3 17 9 11l4 3 8-8'/><path d='M16 6h5v5'/>", "trend_down": "<path d='m3 7 6 6 4-3 8 8'/><path d='M16 18h5v-5'/>",
        "network": "<circle cx='5' cy='12' r='2'/><circle cx='19' cy='6' r='2'/><circle cx='19' cy='18' r='2'/><path d='m7 12 10-6M7 12l10 6'/>", "memory": "<rect x='5' y='6' width='14' height='12' rx='2'/><path d='M8 9h8m-8 3h8m-8 3h5'/>",
        "old_solution": "<path d='M5 4h14v16H5z'/><path d='m8 8 8 8m0-8-8 8'/>", "new_solution": "<path d='M5 12l4 4 10-10'/><circle cx='12' cy='12' r='9'/>",
        "cause": "<circle cx='7' cy='12' r='3'/><path d='M10 12h10m-4-4 4 4-4 4'/>", "mechanism": "<circle cx='12' cy='12' r='3'/><path d='M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1'/>", "result": "<path d='M4 12h10m-4-4 4 4-4 4'/><path d='M17 6h3v12h-3'/>",
    }
    body = shapes.get(semantic_key, "<circle cx='12' cy='12' r='7'/><circle cx='12' cy='12' r='2'/><path d='M12 3v3m0 12v3M3 12h3m12 0h3'/>")
    return f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='{VIEW_BOX}' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>{body}</svg>\n"


def sanitize_key(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").lower()).strip("_") or "generic_concept"
