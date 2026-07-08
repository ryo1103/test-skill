from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import load_contract, write_json
from ..paths import plan_dir, skill_root
from ..stage_result import current_command


def resolve_motion_icons(project_dir: Path, assertions_payload: dict[str, Any]) -> tuple[Path, dict[str, Any], list[dict[str, str]]]:
    icon_map = load_contract("motion_icon_map.json")
    semantic_map = icon_map.get("semantic_icon_map") if isinstance(icon_map.get("semantic_icon_map"), dict) else {}
    assertions = assertions_payload.get("assertions") if isinstance(assertions_payload, dict) else []
    assertions = assertions if isinstance(assertions, list) else []
    records_by_key: dict[str, dict[str, Any]] = {}
    icons_by_assertion: dict[str, dict[str, Any]] = {}
    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        assertion_id = str(assertion.get("motion_assertion_id") or "")
        slots = assertion.get("slots") if isinstance(assertion.get("slots"), dict) else {}
        slot_icons: dict[str, Any] = {}
        for slot_name, slot_value in slots.items():
            slot = slot_value if isinstance(slot_value, dict) else {"text": str(slot_value or ""), "semantic_icon": infer_semantic_key(str(slot_value or ""), semantic_map)}
            semantic_key = str(slot.get("semantic_icon") or infer_semantic_key(str(slot.get("text") or ""), semantic_map) or "node")
            record = records_by_key.get(semantic_key)
            if record is None:
                record = materialize_icon(project_dir, semantic_key, semantic_map.get(semantic_key, {}))
                records_by_key[semantic_key] = record
            slot_icons[str(slot_name)] = {
                "asset_id": record["asset_id"],
                "semantic_key": semantic_key,
                "local_path": record["local_path"],
                "source": record["source"],
                "fallback_symbol": record["fallback_symbol"],
            }
        if assertion_id:
            icons_by_assertion[assertion_id] = slot_icons
    payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "contract": icon_map.get("contract_id", "motion_icon_map_v1"),
        "command": " ".join(current_command()),
        "usage_policy": "motion_overlay_icons_only_not_s3_broll",
        "assets": sorted(records_by_key.values(), key=lambda item: item["asset_id"]),
        "icons_by_assertion": icons_by_assertion,
    }
    path = plan_dir(project_dir) / "motion_asset_manifest.json"
    write_json(path, payload)
    return path, payload, []


def materialize_icon(project_dir: Path, semantic_key: str, config: dict[str, Any]) -> dict[str, Any]:
    fallback_symbol = str(config.get("fallback_symbol") or semantic_key)
    local_candidate = skill_root() / "assets" / "motion" / "icons" / f"{semantic_key}.svg"
    if local_candidate.exists():
        path = local_candidate
        source = "local_icon"
    else:
        path = plan_dir(project_dir) / "motion_icons" / f"{semantic_key}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fallback_svg(fallback_symbol), encoding="utf-8")
        source = "bundled_fallback"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "asset_id": f"motion_icon_{sanitize_key(semantic_key)}",
        "semantic_key": semantic_key,
        "local_path": str(path),
        "source": source,
        "sha256": digest,
        "usage": "motion_overlay_icon",
        "fallback_symbol": fallback_symbol,
    }


def infer_semantic_key(text: str, semantic_map: dict[str, Any]) -> str:
    for key, config in semantic_map.items():
        keywords = config.get("keywords") if isinstance(config, dict) else []
        for keyword in keywords if isinstance(keywords, list) else []:
            if str(keyword).lower() in text.lower():
                return str(key)
    if re.search(r"输入|input", text, re.I):
        return "input"
    if re.search(r"输出|output", text, re.I):
        return "output"
    if re.search(r"错误|瓶颈|无法", text):
        return "warning"
    return "node"


def fallback_svg(symbol: str) -> str:
    shape = sanitize_key(symbol)
    if shape == "chip":
        body = "<rect x='22' y='22' width='60' height='60' rx='8'/><path d='M10 32h12M10 52h12M10 72h12M82 32h12M82 52h12M82 72h12M32 10v12M52 10v12M72 10v12M32 82v12M52 82v12M72 82v12'/>"
    elif shape == "module":
        body = "<rect x='18' y='30' width='68' height='44' rx='7'/><path d='M28 42h32M28 56h46M18 48H8M86 48h10'/>"
    elif shape == "connector":
        body = "<path d='M14 52h28'/><rect x='42' y='32' width='20' height='40' rx='5'/><path d='M62 52h28M30 42v20M74 42v20'/>"
    elif shape == "input_port":
        body = "<path d='M12 52h60'/><path d='M58 34l20 18-20 18'/><circle cx='22' cy='52' r='9'/>"
    elif shape == "output_port":
        body = "<path d='M28 52h60'/><path d='M74 34l20 18-20 18'/><circle cx='80' cy='52' r='9'/>"
    elif shape == "memory":
        body = "<rect x='20' y='24' width='64' height='56' rx='6'/><path d='M32 38h40M32 52h40M32 66h30'/>"
    elif shape == "warning":
        body = "<path d='M52 14L92 84H12z'/><path d='M52 36v24M52 72v4'/>"
    else:
        body = "<circle cx='52' cy='52' r='32'/><path d='M32 52h40M52 32v40'/>"
    return f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 104 104' fill='none' stroke='currentColor' stroke-width='6' stroke-linecap='round' stroke-linejoin='round'>{body}</svg>\n"


def sanitize_key(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").lower()).strip("_")
    return clean or "node"
