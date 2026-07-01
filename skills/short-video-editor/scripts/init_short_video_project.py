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
    "hyperframe_reason",
    "why_simple_broll_is_not_enough",
    "downgrade_reason",
    "why_simple_broll_is_enough",
    "visual_pattern",
    "ae_overlay_candidate",
    "ae_overlay_type",
    "broll_base_asset",
    "overlay_layer_plan",
    "design_plan",
    "animation_plan",
    "hyperframe_polish_guard",
    "hyperframe_completeness_check",
    "editing_rhythm",
    "screen_text",
    "user_review_needed",
]

MANIFEST_COLUMNS = [
    "shot_id",
    "source_segments",
    "start",
    "end",
    "duration",
    "visual_mode",
    "asset_key",
    "source_in",
    "source_out",
    "playback_policy",
    "overlay_png",
    "script",
    "subtitle_cue_ids",
    "persistent_overlay_id",
    "topic_banner_mode",
    "layout_qc_status",
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

SOURCE_UNIQUENESS_AUDIT_TEMPLATE = {
    "status": "not_run",
    "used_source_keys": [],
    "duplicates": [],
    "checks": [
        "source_url",
        "direct_download_url",
        "provider_asset_id",
        "original_file_page",
        "cached_source_file",
        "local_source_clip",
    ],
    "notes": "Repeated B-roll sources must be revised or explicitly approved before final render.",
}

SOURCE_PLAYBACK_AUDIT_TEMPLATE = {
    "status": "not_run",
    "source_ranges": [],
    "looped_sources": [],
    "restarted_sources": [],
    "backward_seeks": [],
    "repeated_ranges": [],
    "overlong_output_ranges": [],
    "approved_still_fallbacks": [],
    "notes": "Video sources may be trimmed shorter once, but must not loop, restart, replay, or exceed the selected trim.",
}

SUBTITLE_CUES_TEMPLATE = {
    "alignment_method": "",
    "rules": {
        "final_render_requires_audio_alignment": True,
        "semantic_complete_cue_required": True,
        "character_count_is_soft_limit": True,
        "target_readability": "short spoken fragment, target 6-14 Chinese characters, hard max 18 except named entities",
        "max_same_subtitle_reuse": 1,
        "sync_tolerance_sec": 0.25,
        "remove_visible_punctuation_unless_semantic": True,
        "draft_alignment_output_policy": "draft_preview_only",
    },
    "cues": [],
}

SUBTITLE_TIMING_AUDIT_TEMPLATE = {
    "status": "not_run",
    "alignment_method": "",
    "sync_tolerance_sec": 0.25,
    "sync_failures": [],
    "semantic_completeness_failures": [],
    "repeated_cue_text_count": 0,
    "readability_length_warnings": [],
}

STYLE_CONTRACT_TEMPLATE = {
    "canvas": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "safe_area": {
            "top": 120,
            "bottom": 210,
            "left": 72,
            "right": 72,
        },
    },
    "subtitle": {
        "mode": "large_short_video_caption",
        "font_family_preferred": [
            "Noto Sans CJK SC",
            "Source Han Sans SC",
            "PingFang SC",
            "Microsoft YaHei",
            "system-ui",
        ],
        "font_size_px": 76,
        "font_size_min_px": 68,
        "font_size_emphasis_px": 88,
        "font_weight": 800,
        "line_count_max": 2,
        "chars_per_cue_target_min": 6,
        "chars_per_cue_target_max": 14,
        "chars_per_cue_hard_max": 18,
        "chars_per_line_soft_max": 14,
        "visible_punctuation_policy": "remove_unless_semantic_required",
        "bottom_margin_px": 240,
        "horizontal_margin_px": 72,
        "outline_px": 6,
        "shadow_px": 3,
        "primary_color": "#FFFFFF",
        "keyword_color": "#00E5FF",
        "secondary_keyword_color": "#7CFFB2",
        "forbid_three_line_subtitles": True,
        "forbid_shrinking_below_min": True,
        "require_audio_derived_timing_for_final": True,
        "fail_low_confidence_timing_for_final": True,
        "draft_alignment_output_policy": "draft_preview_only",
    },
    "persistent_topic_banner": {
        "enabled": True,
        "required_for_final_render": True,
        "visible_start_sec": 0,
        "visible_end_policy": "full_duration",
        "content_source": "work/plan/video_topic.json",
        "max_lines": 2,
        "main_font_size_px": 76,
        "sub_font_size_px": 60,
        "font_weight": 850,
        "position": {
            "x": 96,
            "y": 128,
            "width": 888,
            "height": 220,
        },
        "compact_position_for_talking_head": {
            "x": 96,
            "y": 88,
            "width": 888,
            "height": 170,
        },
        "background": "rgba(0,0,0,0.72)",
        "border_radius_px": 22,
        "padding_px": 28,
        "text_primary": "#8CFFD9",
        "text_secondary": "#FFFFFF",
        "outline_or_glow": True,
        "must_not_duplicate_current_subtitle": True,
    },
    "style_prompt_policy": {
        "if_user_provides_style_reference": "extract_style_from_reference_and_apply",
        "if_user_specifies_style_in_prompt": "follow_user_style",
        "if_user_says_subtitles_too_small": "use_large_short_video_caption",
        "if_no_style_prompt": "use_default_large_short_video_caption",
        "ask_user_when": [
            "用户明确要求先选择风格",
            "参考图风格互相冲突",
            "项目用途和默认短视频风格明显不一致",
            "用户上传了多个强风格参考但没有说明想模仿哪一个",
            "文案主题高度不确定或多个主线冲突",
        ],
        "do_not_ask_when": [
            "只是普通中文口播短视频",
            "用户要求直接生成成片",
            "用户没有给样式要求但目标平台是抖音/视频号/Shorts",
            "用户已经说过要轻松好看的短视频风格",
        ],
    },
    "layout_qc": {
        "require_preflight_contact_sheet": True,
        "require_probe_render_before_final": True,
        "sample_every_sec": 5,
        "check_subtitle_safe_area": True,
        "check_banner_safe_area": True,
        "check_subtitle_banner_overlap": True,
        "check_text_min_size": True,
        "check_hyperframe_snapshots": True,
    },
}

VIDEO_TOPIC_TEMPLATE = {
    "generation_mode": "auto_from_script",
    "source_files": [],
    "script_summary": "",
    "main_subject": "",
    "central_conflict": "",
    "viewer_hook": "",
    "one_sentence_promise": "",
    "candidate_banners": [],
    "selected_banner": {
        "main": "",
        "sub": "",
        "reason": "",
    },
    "section_banners": [],
    "must_appear_full_video": True,
    "requires_user_confirmation": False,
    "uncertainty_reason": "",
}

STYLE_INTAKE_REPORT_TEMPLATE = {
    "user_style_prompt_detected": False,
    "reference_images_detected": [],
    "style_decision": "default_large_short_video_caption",
    "topic_decision": "auto_from_script",
    "asked_user": False,
    "ask_reason": "",
    "final_decision_reason": "Initialized with default large Chinese short-video captions.",
}

LAYOUT_QC_REPORT_TEMPLATE = {
    "status": "not_run",
    "checks": [],
    "failures": [],
    "warnings": [],
}

TOPIC_BANNER_AUDIT_TEMPLATE = {
    "status": "not_run",
    "enabled": True,
    "user_disabled": False,
    "required_for_final_render": True,
    "selected_banner": {
        "main": "",
        "sub": "",
    },
    "coverage": {},
    "failures": [],
    "warnings": [],
}

SUBTITLE_STYLE_AUDIT_TEMPLATE = {
    "status": "not_run",
    "font_size_px": 76,
    "font_size_min_px": 68,
    "line_count_max": 2,
    "failures": [],
    "warnings": [],
}

REMEDIATION_LOG_TEMPLATE = {
    "status": "not_run",
    "attempts": [],
    "unresolved_blockers": [],
    "final_block_allowed": False,
    "notes": "When a gate fails, attempt built-in remediation before writing output/FINAL_BLOCKED.md.",
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
        root / "output" / "qc",
        root / "output" / "qc" / "probe_frames",
        root / "output" / "qc" / "final_qc_frames",
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
    write_json_if_missing(root / "work" / "plan" / "source_uniqueness_audit.json", SOURCE_UNIQUENESS_AUDIT_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "source_playback_audit.json", SOURCE_PLAYBACK_AUDIT_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "subtitle_cues.json", SUBTITLE_CUES_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "subtitle_timing_audit.json", SUBTITLE_TIMING_AUDIT_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "style_contract.json", STYLE_CONTRACT_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "video_topic.json", VIDEO_TOPIC_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "style_intake_report.json", STYLE_INTAKE_REPORT_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "layout_qc_report.json", LAYOUT_QC_REPORT_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "topic_banner_audit.json", TOPIC_BANNER_AUDIT_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "subtitle_style_audit.json", SUBTITLE_STYLE_AUDIT_TEMPLATE)
    write_json_if_missing(root / "work" / "plan" / "remediation_log.json", REMEDIATION_LOG_TEMPLATE)
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
