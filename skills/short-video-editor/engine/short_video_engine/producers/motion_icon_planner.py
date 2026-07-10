from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import read_json, write_json
from ..paths import plan_dir

FORBIDDEN_ROLES = {"comparison_left_media", "comparison_right_media", "subject_media", "product_media", "background_media", "screenshot", "poster_frame", "cutout", "video", "image"}


def plan_motion_icon_requests(project_dir: Path, assertions_payload: dict[str, Any] | None = None) -> tuple[Path, dict[str, Any]]:
    assertions_payload = assertions_payload or read_json(plan_dir(project_dir) / "motion_assertions.json", {})
    requests: list[dict[str, Any]] = []
    for assertion in assertions_payload.get("assertions", []) if isinstance(assertions_payload, dict) else []:
        if not isinstance(assertion, dict):
            continue
        for slot, value in (assertion.get("slots") or {}).items():
            if str(slot) in FORBIDDEN_ROLES:
                continue
            detail = value if isinstance(value, dict) else {"text": str(value or "")}
            requests.append({
                "request_id": f"icon_request_{len(requests)+1:03d}", "motion_id": assertion.get("motion_id"), "motion_assertion_id": assertion.get("motion_assertion_id"),
                "slot": str(slot), "text": str(detail.get("text") or ""), "semantic_key": str(detail.get("semantic_icon") or "generic_concept"), "required": True,
                "source_order": ["project_local_svg", "bundled_svg", "generated_svg", "approved_remote_svg"], "fallback_semantic_key": "node", "style_family": "monoline_hud",
            })
    payload = {"generated_by": "short_video_engine", "engine_version": ENGINE_VERSION, "stage": "S2_visual_plan", "requests": requests}
    path = plan_dir(project_dir) / "motion_icon_requests.json"
    write_json(path, payload)
    return path, payload
