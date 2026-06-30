#!/usr/bin/env python3
"""Initialize a reusable short-video editing project structure."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


VISUAL_COLUMNS = [
    "shot",
    "script_fragment",
    "narrative_role",
    "logic_type",
    "scene_type",
    "renderer",
    "digital_human_presence",
    "digital_human_reason",
    "broll_keywords",
    "overlay_text",
    "data_visual_type",
    "hyperframe_score",
    "hyperframe_allowed",
    "visual_pattern",
    "design_plan",
    "animation_plan",
    "hyperframe_polish_guard",
    "hyperframe_completeness_check",
    "editing_rhythm",
    "screen_text",
]

MANIFEST_COLUMNS = [
    "shot_id",
    "source_segments",
    "start",
    "end",
    "duration",
    "visual_mode",
    "asset_key",
    "overlay_png",
    "script",
]

SOURCE_COLUMNS = [
    "asset_key",
    "path",
    "source_url",
    "license_or_note",
    "usage",
    "provider",
    "shot_id",
    "relevance_score",
    "visual_clarity_score",
    "editability_score",
    "copyright_risk",
    "aspect_fit",
    "reuse_tags",
]

VIDEO_SOURCE_AUDIT_COLUMNS = [
    "provider",
    "query",
    "video_found",
    "downloadable",
    "api_or_method",
    "selected_asset_key",
    "source_url",
    "license_or_terms_note",
    "blocked_reason",
]

NEWS_SOURCE_PLAN_TEMPLATE = {
    "script_event_summary": "",
    "queries": [],
    "sources": [],
}

ASSET_SEARCH_PLAN_TEMPLATE = {
    "shots": []
}

HYPERFRAME_POLISH_GUARD_TEMPLATE = {
    "shots": []
}

SHOT_PLAN_TEMPLATE = {
    "project_type": "knowledge_short_video",
    "style_positioning": "broll_main_visual_with_short_fullscreen_digital_human_and_selective_hyperframe",
    "global_rules": {
        "digital_human_role": "short fullscreen brand anchor",
        "broll_role": "main visual carrier",
        "hyperframe_role": "only key logic, data, comparison, flow, timeline, causality, system structure, and professional emphasis",
        "digital_human_ratio_target": "15%-28%",
        "broll_ratio_target": "50%-70%",
        "hyperframe_total_ratio_target": "8%-18%",
    },
    "shots": [],
    "hyperframe_summary": {},
    "digital_human_summary": {},
    "broll_summary": {},
}

VISUAL_RATIO_AUDIT_TEMPLATE = {
    "total_duration_sec": 0,
    "digital_human_fullscreen_sec": 0,
    "digital_human_ratio": "0%",
    "broll_or_screen_recording_sec": 0,
    "broll_ratio": "0%",
    "hyperframe_sec": 0,
    "hyperframe_ratio": "0%",
    "continuous_digital_human_max_sec": 0,
    "continuous_hyperframe_max_sec": 0,
    "rule_check": [],
}

ASSET_MANIFEST_TEMPLATE = {
    "assets": []
}

ASSET_INDEX_TEMPLATE = {
    "assets": []
}

ASSET_LIBRARY_DIRS = [
    "AI/chips",
    "AI/data_centers",
    "AI/robots",
    "AI/dashboards",
    "Finance/stock_market",
    "Finance/charts",
    "Finance/trading_screens",
    "Business/meetings",
    "Business/office",
    "Business/factories",
    "Business/logistics",
    "Technology/cloud",
    "Technology/software_ui",
    "Technology/cybersecurity",
    "Brands/nvidia",
    "Brands/openai",
    "Brands/google",
    "Brands/microsoft",
    "Generic/abstract_background",
    "Generic/city",
    "Generic/people",
    "Generic/warning",
    "Generic/success",
    "ScreenRecordings/websites",
    "ScreenRecordings/tools",
    "ScreenRecordings/dashboards",
    "DataVisuals/kpi_cards",
    "DataVisuals/timelines",
    "DataVisuals/comparison",
    "DataVisuals/flowcharts",
]


def write_csv(path: Path, columns: list[str]):
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()


def write_text_if_missing(path: Path, text: str):
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def write_json_if_missing(path: Path, payload: dict):
    if not path.exists():
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Create a short-video editing project scaffold.")
    parser.add_argument("project_dir", help="Project folder to initialize")
    parser.add_argument("--script-name", default="文案.txt", help="Expected script filename")
    parser.add_argument("--oral-name", default="oral.mp4", help="Expected oral/talking-head video filename")
    args = parser.parse_args()

    root = Path(args.project_dir).expanduser().resolve()
    for folder in [
        root / "assets" / "raw" / "video",
        root / "assets" / "raw" / "image",
        root / "assets" / "raw" / "screenshot",
        root / "assets" / "raw" / "screen_recording",
        root / "assets" / "raw" / "logo",
        root / "assets" / "processed",
        root / "assets" / "selected" / "by_shot",
        root / "assets" / "selected" / "by_theme",
        root / "assets" / "metadata",
        root / "bgm",
        root / "work" / "plan",
        root / "output",
        root / "output" / "edit_package",
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    for folder in ASSET_LIBRARY_DIRS:
        (root / "assets_library" / folder).mkdir(parents=True, exist_ok=True)

    write_csv(root / "work" / "plan" / "visual_strategy.csv", VISUAL_COLUMNS)
    write_csv(root / "work" / "plan" / "edit_manifest.csv", MANIFEST_COLUMNS)
    write_csv(root / "work" / "plan" / "video_source_audit.csv", VIDEO_SOURCE_AUDIT_COLUMNS)
    write_csv(root / "assets" / "sources.csv", SOURCE_COLUMNS)
    write_json_if_missing(root / "work" / "plan" / "news_source_plan.json", NEWS_SOURCE_PLAN_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "asset_search_plan.json", ASSET_SEARCH_PLAN_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "hyperframe_polish_guard.json", HYPERFRAME_POLISH_GUARD_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "shot_plan.json", SHOT_PLAN_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "visual_ratio_audit.json", VISUAL_RATIO_AUDIT_TEMPLATE)
    write_json_if_missing(root / "assets" / "metadata" / "asset_manifest.json", ASSET_MANIFEST_TEMPLATE)
    write_json_if_missing(root / "assets_library" / "asset_index.json", ASSET_INDEX_TEMPLATE)
    write_text_if_missing(root / "assets" / "素材来源.md", "# 素材来源\n\n")
    write_text_if_missing(root / ".env.example", "PEXELS_API_KEY=\nPIXABAY_API_KEY=\n")
    write_text_if_missing(
        root / "work" / "plan" / "manual_recut_tracks.md",
        """# 手动重剪轨道建议

V4 字幕：SRT/ASS 或剪辑软件字幕层
V3 卡片：透明 PNG / PNG 序列
V2 替换 B-roll：新增素材覆盖局部段落
V1 底片：base_with_oral_no_cards_no_subtitles.mp4
A1 口播音频：底片自带或原口播视频音频
""",
    )
    write_text_if_missing(root / args.script_name, "")

    print(root)
    print(f"Expected oral video filename: {args.oral_name}")
    print("Created plan templates under work/plan and asset source templates under assets.")


if __name__ == "__main__":
    main()
