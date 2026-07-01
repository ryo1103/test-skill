#!/usr/bin/env python3
"""Create style_contract.json, video_topic.json, and style_intake_report.json."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path


DEFAULT_STYLE_CONTRACT = {
    "canvas": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "safe_area": {"top": 120, "bottom": 210, "left": 72, "right": 72},
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
        "position": {"x": 96, "y": 128, "width": 888, "height": 220},
        "compact_position_for_talking_head": {"x": 96, "y": 88, "width": 888, "height": 170},
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

UNCERTAIN_MARKERS = [
    "随便",
    "不知道",
    "多个主题",
    "几个主题",
    "任选",
    "还没定",
    "不确定",
    "混合",
    "杂谈",
]

FINANCE_TECH_KEYWORDS = [
    "财报",
    "股票",
    "市场",
    "周期",
    "AI",
    "芯片",
    "算力",
    "存储",
    "HBM",
    "GPU",
    "科技",
    "商业",
    "公司",
    "供应链",
]

EXPLAINER_KEYWORDS = ["为什么", "怎么", "如何", "原理", "逻辑", "机制", "原因", "解释"]


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_text(path: Path | None) -> str:
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except FileNotFoundError:
        return ""


def resolve_project_path(project_dir: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_dir / path
    return path.resolve()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def visible_chars(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text)


def truncate_chinese(text: str, min_len: int, max_len: int, suffix: str = "") -> str:
    clean = compact_text(text)
    if not clean:
        return ""
    if len(clean) <= max_len:
        return clean
    base = clean[: max(min_len, max_len - len(suffix))]
    return base + suffix


def infer_main_subject(text: str) -> str:
    clean = compact_text(text)
    if not clean:
        return ""

    patterns = [
        r"([\u4e00-\u9fffA-Za-z0-9]{2,12})(财报|业绩|股价|周期|增长|成本|风险|真相|逻辑)",
        r"(AI|HBM|GPU|OpenAI|英伟达|美光|存储|芯片|算力|大模型|市场|供应链|财报)",
        r"([\u4e00-\u9fffA-Za-z0-9]{2,10})(为什么|怎么|如何|到底)",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            return "".join(part for part in match.groups() if part)

    tokens = visible_chars(clean)
    if not tokens:
        return clean[:12]
    first = tokens[0]
    if len(first) >= 4:
        return first[:12]
    joined = "".join(tokens[:3])
    return joined[:12]


def infer_conflict(text: str) -> str:
    clean = compact_text(text)
    conflict_patterns = [
        r"(不是[\u4e00-\u9fffA-Za-z0-9，,]{2,18}而是[\u4e00-\u9fffA-Za-z0-9]{2,18})",
        r"(真正[\u4e00-\u9fffA-Za-z0-9]{2,20})",
        r"(问题[\u4e00-\u9fffA-Za-z0-9]{2,20})",
        r"(关键[\u4e00-\u9fffA-Za-z0-9]{2,20})",
        r"(风险[\u4e00-\u9fffA-Za-z0-9]{2,20})",
    ]
    for pattern in conflict_patterns:
        match = re.search(pattern, clean)
        if match:
            return truncate_chinese(match.group(1), 6, 22)
    if "但" in clean:
        return truncate_chinese(clean.split("但", 1)[1], 6, 22)
    if "?" in clean or "？" in clean:
        return "答案藏在后面的逻辑"
    return "真正关键不在表面"


def infer_viewer_hook(text: str, main_subject: str, conflict: str) -> str:
    if any(keyword in text for keyword in FINANCE_TECH_KEYWORDS):
        return truncate_chinese(conflict or f"{main_subject}背后的逻辑", 10, 22)
    if any(keyword in text for keyword in EXPLAINER_KEYWORDS):
        return truncate_chinese(f"真正卡住的是{main_subject or '核心变量'}", 10, 22)
    return truncate_chinese(conflict or "看懂这轮变化的关键", 10, 22)


def detect_uncertainty(text: str, main_subject: str) -> tuple[bool, str]:
    clean = compact_text(text)
    if len(clean) < 20:
        return True, "script_too_short_to_identify_topic"
    for marker in UNCERTAIN_MARKERS:
        if marker in clean:
            return True, f"uncertain_marker:{marker}"
    topic_signals = sum(1 for keyword in FINANCE_TECH_KEYWORDS + EXPLAINER_KEYWORDS if keyword in clean)
    if not main_subject or (len(clean) > 160 and topic_signals == 0):
        return True, "no_clear_subject_or_conflict_signal"
    return False, ""


def build_candidate_banners(text: str, main_subject: str, conflict: str, hook: str) -> list[dict]:
    clean = compact_text(text)
    candidates: list[dict] = []
    if not clean:
        return [
            {
                "main": "主题待确认",
                "sub": "文案不足以自动判断主线",
                "reason": "No script text was available.",
                "risk": "needs_user_confirmation",
                "score": 10,
            }
        ]

    subject = truncate_chinese(main_subject or clean, 4, 12)
    conflict_sub = truncate_chinese(hook or conflict, 10, 22)

    if any(keyword in clean for keyword in FINANCE_TECH_KEYWORDS):
        candidates.append(
            {
                "main": truncate_chinese(f"{subject}真相", 8, 16),
                "sub": conflict_sub or "市场正在重定价逻辑",
                "reason": "Finance/technology/business script detected; use issue title plus logic hook.",
                "risk": "",
                "score": 92,
            }
        )
        candidates.append(
            {
                "main": truncate_chinese(f"{subject}逻辑变了", 8, 16),
                "sub": "真正关键不在表面",
                "reason": "Conflict-driven title suitable for market or business commentary.",
                "risk": "",
                "score": 86,
            }
        )
    elif any(keyword in clean for keyword in EXPLAINER_KEYWORDS):
        candidates.append(
            {
                "main": truncate_chinese(f"{subject}为什么", 8, 16),
                "sub": conflict_sub or "答案藏在核心变量里",
                "reason": "Explainer script detected; use core question plus answer preview.",
                "risk": "",
                "score": 90,
            }
        )
    else:
        candidates.append(
            {
                "main": truncate_chinese(f"{subject}关键变化", 8, 16),
                "sub": conflict_sub or "看懂这轮变化的关键",
                "reason": "General commentary script; use thesis plus viewer hook.",
                "risk": "",
                "score": 82,
            }
        )

    candidates.append(
        {
            "main": truncate_chinese(subject, 8, 16, "核心"),
            "sub": truncate_chinese(conflict or "真正关键不在表面", 10, 22),
            "reason": "Fallback candidate preserving the detected subject.",
            "risk": "",
            "score": 74,
        }
    )
    return sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)


def build_video_topic(
    script_text: str,
    source_files: list[str],
    topic_main: str | None,
    topic_sub: str | None,
) -> dict:
    main_subject = infer_main_subject(script_text)
    conflict = infer_conflict(script_text)
    hook = infer_viewer_hook(script_text, main_subject, conflict)
    requires_confirmation, uncertainty_reason = detect_uncertainty(script_text, main_subject)
    candidates = build_candidate_banners(script_text, main_subject, conflict, hook)
    selected = candidates[0]

    generation_mode = "auto_from_script"
    if topic_main or topic_sub:
        generation_mode = "user_provided"
        selected = {
            "main": topic_main or selected.get("main", ""),
            "sub": topic_sub or selected.get("sub", ""),
            "reason": "User-provided topic override.",
            "risk": "",
            "score": 100,
        }
        requires_confirmation = False
        uncertainty_reason = ""

    summary = re.sub(r"\s+", " ", script_text).strip()
    if len(summary) > 160:
        summary = summary[:157] + "..."

    return {
        "generation_mode": generation_mode,
        "source_files": source_files,
        "script_summary": summary,
        "main_subject": main_subject,
        "central_conflict": conflict,
        "viewer_hook": hook,
        "one_sentence_promise": f"用一条主线看懂{main_subject or '这个议题'}：{hook or conflict}",
        "candidate_banners": candidates,
        "selected_banner": {
            "main": selected.get("main", ""),
            "sub": selected.get("sub", ""),
            "reason": selected.get("reason", ""),
        },
        "section_banners": [],
        "must_appear_full_video": True,
        "requires_user_confirmation": requires_confirmation,
        "uncertainty_reason": uncertainty_reason,
    }


def detect_user_style_prompt(prompt: str) -> bool:
    if not prompt:
        return False
    markers = ["字幕太小", "轻松好看", "参考", "大字幕", "醒目", "任何帧", "风格", "抖音", "视频号", "Shorts"]
    return any(marker.lower() in prompt.lower() for marker in markers)


def build_style_intake_report(
    reference_images: list[str],
    topic_main: str | None,
    topic_sub: str | None,
    style_prompt: str,
) -> dict:
    user_style_prompt_detected = detect_user_style_prompt(style_prompt)
    if reference_images:
        style_decision = "reference_guided"
        reason = "Reference image paths were supplied. Codex must visually inspect them and write extracted style notes."
    elif user_style_prompt_detected:
        style_decision = "user_specified"
        reason = "User prompt contains style intent; large short-video captions remain the default unless overridden."
    else:
        style_decision = "default_large_short_video_caption"
        reason = "No explicit style prompt; default to large Chinese short-video captions without asking."

    return {
        "user_style_prompt_detected": user_style_prompt_detected,
        "reference_images_detected": reference_images,
        "style_decision": style_decision,
        "topic_decision": "user_provided" if (topic_main or topic_sub) else "auto_from_script",
        "asked_user": False,
        "ask_reason": "",
        "final_decision_reason": reason,
        "reference_style_notes": {
            "codex_visual_inspection_required": bool(reference_images),
            "subtitle_size": "",
            "title_position": "",
            "dominant_colors": [],
            "outline_shadow": "",
            "style_tendency": "",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Create default short-video style and topic files.")
    parser.add_argument("project_dir", help="Short-video project directory")
    parser.add_argument("--script", help="Script path. Relative paths are resolved from project_dir.")
    parser.add_argument("--reference-image", action="append", default=[], help="Reference image path. Can be repeated.")
    parser.add_argument("--style", default="auto", help="Style mode. Use auto unless user supplied a concrete style.")
    parser.add_argument("--topic", default="auto", help="Topic mode. Use auto unless user supplied topic text.")
    parser.add_argument("--topic-main", help="Override persistent topic banner main title.")
    parser.add_argument("--topic-sub", help="Override persistent topic banner subtitle.")
    parser.add_argument("--style-prompt", default="", help="Optional user style prompt text for intake reporting.")
    parser.add_argument("--disable-topic-banner", action="store_true", help="Record explicit user choice to disable the banner.")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).expanduser().resolve()
    plan_dir = project_dir / "work" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)

    script_path = resolve_project_path(project_dir, args.script)
    script_text = read_text(script_path)
    source_files = [str(script_path)] if script_path else []
    references = [str(resolve_project_path(project_dir, value)) for value in args.reference_image]

    style_contract = deepcopy(DEFAULT_STYLE_CONTRACT)
    if args.disable_topic_banner:
        style_contract["persistent_topic_banner"]["enabled"] = False
        style_contract["persistent_topic_banner"]["required_for_final_render"] = False

    if references:
        style_contract["reference_guided_style"] = {
            "reference_images": references,
            "codex_visual_inspection_required": True,
            "notes": "Codex should inspect reference images and update subtitle/title/color fields before rendering.",
        }

    video_topic = build_video_topic(script_text, source_files, args.topic_main, args.topic_sub)
    if references and video_topic["generation_mode"] == "auto_from_script":
        video_topic["generation_mode"] = "reference_guided"
    if args.disable_topic_banner:
        video_topic["must_appear_full_video"] = False

    style_report = build_style_intake_report(references, args.topic_main, args.topic_sub, args.style_prompt)
    if args.style != "auto":
        style_report["style_decision"] = "user_specified"
        style_report["final_decision_reason"] = f"Style mode was set to {args.style}."
    if args.topic != "auto" and not (args.topic_main or args.topic_sub):
        style_report["topic_decision"] = args.topic

    write_json(plan_dir / "style_contract.json", style_contract)
    write_json(plan_dir / "video_topic.json", video_topic)
    write_json(plan_dir / "style_intake_report.json", style_report)

    print(plan_dir / "style_contract.json")
    print(plan_dir / "video_topic.json")
    print(plan_dir / "style_intake_report.json")
    if video_topic.get("requires_user_confirmation"):
        print(f"requires_user_confirmation: {video_topic.get('uncertainty_reason')}")


if __name__ == "__main__":
    main()
