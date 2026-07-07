from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import contracts_dir


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_contract(name: str) -> dict[str, Any]:
    payload = read_json(contracts_dir() / name, {})
    if not isinstance(payload, dict):
        raise ValueError(f"Contract {name} must be a JSON object")
    return payload


def load_pipeline_stages() -> list[str]:
    payload = load_contract("pipeline_stages.json")
    stages = payload.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("contracts/pipeline_stages.json must define a non-empty stages list")
    result: list[str] = []
    for item in stages:
        if not isinstance(item, dict) or not item.get("id"):
            raise ValueError("Each pipeline stage must define id")
        result.append(str(item["id"]))
    return result
