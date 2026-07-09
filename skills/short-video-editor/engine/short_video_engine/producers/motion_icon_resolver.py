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
        body = "<rect x='22' y='22' width='60' height='60' rx='10'/><rect x='36' y='36' width='32' height='32' rx='5'/><path d='M10 32h12M10 52h12M10 72h12M82 32h12M82 52h12M82 72h12M32 10v12M52 10v12M72 10v12M32 82v12M52 82v12M72 82v12'/><path d='M42 52h20M52 42v20' opacity='.55'/>"
    elif shape == "module":
        body = "<rect x='16' y='28' width='72' height='48' rx='9'/><rect x='28' y='40' width='28' height='24' rx='4'/><path d='M62 42h14M62 52h14M62 62h10M16 48H8M88 48h8M16 58H8M88 58h8'/>"
    elif shape == "connector":
        body = "<path d='M10 52h28'/><rect x='38' y='30' width='28' height='44' rx='8'/><path d='M66 52h28M28 40v24M76 40v24M46 42h12M46 62h12'/><circle cx='52' cy='52' r='6'/>"
    elif shape == "input_port":
        body = "<circle cx='22' cy='52' r='11'/><path d='M36 52h42'/><path d='M62 34l20 18-20 18'/><path d='M22 42v20' opacity='.5'/>"
    elif shape == "output_port":
        body = "<path d='M18 52h50'/><path d='M54 34l20 18-20 18'/><circle cx='82' cy='52' r='11'/><path d='M82 42v20' opacity='.5'/>"
    elif shape == "memory":
        body = "<rect x='20' y='24' width='64' height='56' rx='8'/><path d='M32 38h40M32 52h40M32 66h30M28 14v10M44 14v10M60 14v10M76 14v10M28 80v10M44 80v10M60 80v10M76 80v10'/>"
    elif shape == "warning":
        body = "<path d='M52 12L94 86H10z'/><path d='M52 34v26M52 74v4'/><path d='M30 84h44' opacity='.45'/>"
    else:
        body = "<circle cx='52' cy='52' r='32'/><circle cx='52' cy='52' r='10'/><path d='M52 20v14M52 70v14M20 52h14M70 52h14M31 31l10 10M63 63l10 10M73 31L63 41M41 63L31 73'/>"
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 104 104' fill='none' "
        "stroke='currentColor' stroke-width='5.5' stroke-linecap='round' stroke-linejoin='round'>"
        "<rect x='6' y='6' width='92' height='92' rx='18' opacity='.18'/>"
        f"{body}</svg>\n"
    )


def sanitize_key(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").lower()).strip("_")
    return clean or "node"
