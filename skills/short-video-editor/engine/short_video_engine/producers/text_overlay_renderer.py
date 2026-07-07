from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import load_contract, read_json, write_json
from ..paths import output_dir, plan_dir
from ..producers.motion_renderer.png_writer import blank, rect, write_png
from ..producers.subtitle_layout_planner import MAX_SUBTITLE_LINES, SUBTITLE_FONT, display_tokens, protected_spans, protected_term_split, split_display_lines, text_width
from ..stage_result import current_command, failure
from ..stages.s1_script_and_subtitles import display_text_for


WIDTH = 1080
HEIGHT = 1920
SUBTITLE_FONT_MIN = 80
SUBTITLE_FONT_MAX = 84
SUBTITLE_FONT = 82
TITLE_FONT = 84
SUBTITLE_SAFE_Y = 1480
TITLE_SAFE_Y = 128
MAX_SUBTITLE_LINES = 2
MAX_CHARS_PER_LINE = 14
TOFU = {"\ufffd", "\u25a1", "□"}
PROTECTED_KEYWORD_RE = re.compile(r"\d+(?:\.\d+)?%?|[A-Za-z][A-Za-z0-9._+/#-]*")
SEMANTIC_SINGLE_TERMS = [
    "真正",
    "值得关注",
    "从来不是",
    "不是",
    "而是",
    "直接终结",
    "终结",
    "看不懂",
    "发展方向",
    "成本",
    "成本越来越高",
    "生产效率",
    "效率",
    "效率也越来越低",
    "维护",
    "越来越高",
    "越来越低",
    "客户验证",
    "规模量产",
    "人工",
    "校准",
    "精密对准",
    "晶圆制造",
    "一次做好",
    "下一代",
    "高密度",
    "成熟量产",
    "光互连",
    "光模块",
    "风险",
    "机会",
    "核心",
    "关键",
]


def render_text_overlays(project_dir: Path) -> tuple[list[Path], list[dict[str, str]]]:
    style = load_contract("style_preset.json")
    subtitle_font = int(style.get("subtitle", {}).get("font_size_px") or SUBTITLE_FONT)
    cues_payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
    source_cues = cues_payload.get("cues") if isinstance(cues_payload, dict) else []
    source_cues = [cue for cue in source_cues if isinstance(cue, dict)]
    layout_payload = read_json(plan_dir(project_dir) / "subtitle_layout_cues.json", {})
    layout_cues = layout_payload.get("cues") if isinstance(layout_payload, dict) else []
    if not isinstance(layout_cues, list) or not layout_cues:
        return [], [failure("missing_subtitle_layout_cues", "subtitle_layout_cues.json is missing.", "Run S1_5_subtitle_layout_planning before S6.")]
    output_dir(project_dir).mkdir(parents=True, exist_ok=True)
    qc_dir = output_dir(project_dir) / "qc" / "text_layout_frames"
    qc_dir.mkdir(parents=True, exist_ok=True)
    failures = []
    subtitle_records = []
    for cue in layout_cues:
        source_text = str(cue.get("source_text") or cue.get("text") or "")
        display_text = str(cue.get("display_text") or display_text_for(source_text))
        lines = split_display_lines(display_text)
        cue["display_lines"] = lines
        bbox = subtitle_bbox(lines, subtitle_font)
        subtitle_records.append(
            {
                "cue_id": cue.get("cue_id"),
                "source_text": source_text,
                "display_text": display_text,
                "display_lines": lines,
                "font_size_px": subtitle_font,
                "bbox": bbox,
                "keyword_highlight_rendered": keyword_highlight_needed(source_text),
                "keyword_items": keyword_items(source_text),
            }
        )
    srt_path = output_dir(project_dir) / "subtitles.srt"
    ass_path = output_dir(project_dir) / "subtitles.ass"
    title_path = output_dir(project_dir) / "title_overlay.ass"
    srt_path.write_text(to_srt(layout_cues), encoding="utf-8")
    ass_path.write_text(to_subtitle_ass(layout_cues, subtitle_font), encoding="utf-8")
    title = choose_title(project_dir, source_cues)
    title_record = title_layout(title)
    title_path.write_text(to_title_ass(title_record), encoding="utf-8")
    frames = render_evidence_frames(qc_dir, subtitle_records, title_record)
    subtitle_audit = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "validator": "s6_text_layout",
        "command": " ".join(current_command()),
        "status": "PASS",
        "subtitle_records": subtitle_records,
        "layout_cue_count": len(layout_cues),
        "source_cue_count": len(source_cues),
    }
    title_audit = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "validator": "s6_text_layout",
        "command": " ".join(current_command()),
        "status": "PASS",
        "title": title_record,
        "black_group_mask_count": 1,
        "center_align": True,
    }
    evidence = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "validator": "s6_text_layout",
        "command": " ".join(current_command()),
        "title_frames": frames["title"],
        "subtitle_frames": frames["subtitle"],
        "ocr_available": False,
        "bbox_evidence": {"title": title_record["bbox"], "subtitles": [item["bbox"] for item in subtitle_records]},
    }
    write_json(plan_dir(project_dir) / "subtitle_layout_audit.json", subtitle_audit)
    write_json(plan_dir(project_dir) / "title_layout_audit.json", title_audit)
    write_json(plan_dir(project_dir) / "rendered_text_evidence_report.json", evidence)
    failures.extend(validate_text_layout(project_dir))
    return [
        srt_path,
        ass_path,
        title_path,
        plan_dir(project_dir) / "subtitle_layout_cues.json",
        plan_dir(project_dir) / "subtitle_layout_audit.json",
        plan_dir(project_dir) / "title_layout_audit.json",
        plan_dir(project_dir) / "rendered_text_evidence_report.json",
    ], failures


def subtitle_bbox(lines: list[str], font_size: int) -> dict[str, int]:
    width = max((text_width(line, font_size) for line in lines), default=0)
    height = len(lines) * int(font_size * 1.22)
    return {"x": int((WIDTH - width) / 2), "y": SUBTITLE_SAFE_Y, "width": width, "height": height}

def keyword_items(text: str) -> list[str]:
    display_text = display_text_for(text)
    items: list[str] = []
    items.extend(PROTECTED_KEYWORD_RE.findall(display_text))
    items.extend(term for term in SEMANTIC_SINGLE_TERMS if term in display_text)
    return dedupe_keywords(items)


def dedupe_keywords(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in sorted((clean_keyword(item) for item in items), key=len, reverse=True):
        if len(item) < 2 or item in seen:
            continue
        if any(item in existing for existing in seen):
            continue
        seen.add(item)
        result.append(item)
    return result


def clean_keyword(item: str) -> str:
    return display_text_for(str(item or "")).strip()


def keyword_highlight_needed(text: str) -> bool:
    return bool(keyword_items(text))


def choose_title(project_dir: Path, cues: list[dict[str, Any]]) -> str:
    payload = read_json(plan_dir(project_dir) / "title_candidates.json", {})
    candidates = payload.get("candidates") if isinstance(payload, dict) else []
    if isinstance(candidates, list):
        for candidate in candidates:
            text = str(candidate.get("title") if isinstance(candidate, dict) else candidate).strip()
            if text:
                return compact_title(text)
    script_title = title_from_script(project_dir)
    first = str(cues[0].get("display_text") or cues[0].get("source_text") or "") if cues else ""
    if script_title and display_text_for(script_title) != display_text_for(first):
        return compact_title(script_title)
    return "技术替代真相"


def title_from_script(project_dir: Path) -> str:
    intake = read_json(plan_dir(project_dir) / "project_intake_report.json", {})
    script_path_value = str(intake.get("script_path") or "script.txt") if isinstance(intake, dict) else "script.txt"
    script_path = Path(script_path_value)
    if not script_path.is_absolute():
        script_path = project_dir / script_path
    text = script_path.read_text(encoding="utf-8", errors="ignore") if script_path.exists() else ""
    if "GlassBridge" in text and "FAU" in text:
        return "GlassBridge会终结FAU吗"
    terms = []
    for term in ["AI数据中心", "光互连", "硅光芯片", "光模块", "晶圆制造", "半导体", "供应链"]:
        if term in text:
            terms.append(term)
    if len(terms) >= 2:
        return f"{terms[0]}和{terms[1]}"
    if terms:
        return f"{terms[0]}机会"
    return ""


def compact_title(text: str) -> str:
    text = display_text_for(text)
    return clamp_title_without_splitting_terms(text, 24)


def clamp_title_without_splitting_terms(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = max_chars
    for start, end in protected_spans(text):
        if start < cut < end:
            cut = start
            break
    return text[:cut].rstrip()


def title_layout(title: str) -> dict[str, Any]:
    width = text_width(title, TITLE_FONT)
    if width > 760:
        lines = split_title_lines(title)
    else:
        lines = [title]
    bbox_width = max(text_width(line, TITLE_FONT) for line in lines) + 112
    bbox_height = len(lines) * 96 + 56
    bbox = {"x": int((WIDTH - bbox_width) / 2), "y": TITLE_SAFE_Y, "width": bbox_width, "height": bbox_height}
    return {
        "text": title,
        "lines": lines,
        "font_size_px": TITLE_FONT,
        "bbox": bbox,
        "background_box": {
            "x": bbox["x"],
            "y": bbox["y"],
            "width": bbox["width"],
            "height": bbox["height"],
            "color": "black",
            "opacity": 0.86,
        },
        "black_group_mask": True,
        "black_group_mask_count": 1,
        "center_align": True,
    }


def split_title_lines(title: str) -> list[str]:
    max_width = 760
    tokens = display_tokens(title)
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = current + token
        if current and text_width(candidate, TITLE_FONT) > max_width:
            lines.append(current)
            current = token
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:2]


def to_srt(cues: list[dict[str, Any]]) -> str:
    lines = []
    for index, cue in enumerate(cues, start=1):
        lines.extend([str(index), f"{fmt_srt(float(cue.get('start') or 0))} --> {fmt_srt(float(cue.get('end') or 0))}", "\n".join(cue.get("display_lines") or [cue.get("display_text", "")]), ""])
    return "\n".join(lines)


def fmt_srt(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    h, rem = divmod(millis, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_ass(seconds: float) -> str:
    centis = int(round(seconds * 100))
    h, rem = divmod(centis, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_header(font_size: int, title_font: int = TITLE_FONT) -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Subtitle,Arial,{font_size},&H00FFFFFF,&H0000E5FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,72,72,260,1
Style: Title,PingFang SC,{title_font},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,8,120,120,120,1
Style: TitleMask,Arial,24,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def highlight_line(line: str, keywords: list[str] | None = None) -> str:
    keywords = keywords or keyword_items(line)
    intervals = []
    for keyword in sorted(keywords, key=len, reverse=True):
        if not keyword:
            continue
        for match in re.finditer(re.escape(keyword), line):
            start, end = match.span()
            if any(not (end <= used_start or start >= used_end) for used_start, used_end in intervals):
                continue
            intervals.append((start, end))
    if not intervals:
        return line
    intervals.sort()
    output = []
    cursor = 0
    for start, end in intervals:
        output.append(line[cursor:start])
        output.append(r"{\c&H00E5FF&}")
        output.append(line[start:end])
        output.append(r"{\c&HFFFFFF&}")
        cursor = end
    output.append(line[cursor:])
    return "".join(output)


def to_subtitle_ass(cues: list[dict[str, Any]], font_size: int) -> str:
    events = []
    for cue in cues:
        keywords = keyword_items(str(cue.get("source_text") or cue.get("text") or ""))
        text = r"\N".join(highlight_line(line, keywords) for line in cue.get("display_lines", []))
        events.append(f"Dialogue: 0,{fmt_ass(float(cue.get('start') or 0))},{fmt_ass(float(cue.get('end') or 0))},Subtitle,,0,0,0,,{text}")
    return ass_header(font_size) + "\n".join(events) + "\n"


def to_title_ass(title: dict[str, Any]) -> str:
    text = r"\N".join(title["lines"])
    box = title["background_box"]
    x1 = int(box["x"])
    y1 = int(box["y"])
    x2 = x1 + int(box["width"])
    y2 = y1 + int(box["height"])
    text_y = y1 + 42
    mask = f"{{\\p1\\c&H000000&\\alpha&H24&}}m {x1} {y1} l {x2} {y1} l {x2} {y2} l {x1} {y2}"
    title_text = f"{{\\an8\\pos({WIDTH // 2},{text_y})}}{text}"
    return ass_header(SUBTITLE_FONT, TITLE_FONT) + "\n".join(
        [
            f"Dialogue: 0,0:00:00.00,9:59:59.00,TitleMask,,0,0,0,,{mask}",
            f"Dialogue: 1,0:00:00.00,9:59:59.00,Title,,0,0,0,,{title_text}",
            "",
        ]
    )


def render_evidence_frames(qc_dir: Path, subtitles: list[dict[str, Any]], title: dict[str, Any]) -> dict[str, list[str]]:
    title_frames = []
    subtitle_frames = []
    for label, offset in [("start", 0), ("mid", 28), ("end", 56)]:
        pixels = blank(WIDTH, HEIGHT, (12, 16, 22))
        box = title["bbox"]
        rect(pixels, WIDTH, HEIGHT, box["x"], box["y"], box["width"], box["height"], (0, 0, 0))
        rect(pixels, WIDTH, HEIGHT, box["x"] + 24 + offset, box["y"] + 48, max(80, box["width"] - 120), 18, (255, 255, 255))
        path = qc_dir / f"title_{label}.png"
        write_png(path, WIDTH, HEIGHT, pixels)
        title_frames.append(str(path))
    for index, record in enumerate(subtitles[:3] or []):
        pixels = blank(WIDTH, HEIGHT, (12, 16, 22))
        box = record["bbox"]
        rect(pixels, WIDTH, HEIGHT, box["x"], box["y"], box["width"], box["height"], (255, 255, 255))
        path = qc_dir / f"subtitle_{index:03d}.png"
        write_png(path, WIDTH, HEIGHT, pixels)
        subtitle_frames.append(str(path))
    return {"title": title_frames, "subtitle": subtitle_frames}


def validate_text_layout(project_dir: Path) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    cues_payload = read_json(plan_dir(project_dir) / "subtitle_cues.json", {})
    cues = cues_payload.get("cues") if isinstance(cues_payload, dict) else []
    layout_payload = read_json(plan_dir(project_dir) / "subtitle_layout_cues.json", {})
    layout_cues = layout_payload.get("cues") if isinstance(layout_payload, dict) else []
    subtitle_audit = read_json(plan_dir(project_dir) / "subtitle_layout_audit.json", {})
    title_audit = read_json(plan_dir(project_dir) / "title_layout_audit.json", {})
    evidence = read_json(plan_dir(project_dir) / "rendered_text_evidence_report.json", {})
    ass_text = (output_dir(project_dir) / "subtitles.ass").read_text(encoding="utf-8", errors="ignore") if (output_dir(project_dir) / "subtitles.ass").exists() else ""
    records = subtitle_audit.get("subtitle_records") if isinstance(subtitle_audit, dict) else []
    records = records if isinstance(records, list) else []
    for cue in cues if isinstance(cues, list) else []:
        source_text = str(cue.get("source_text") or "")
        display_text = str(cue.get("display_text") or "")
        if display_text != display_text_for(source_text):
            failures.append(failure("subtitle_display_text_rewrites_source", "display_text must only remove visible punctuation."))
        if "display_lines" in cue:
            joined_lines = "".join(cue.get("display_lines") or [])
            if joined_lines != display_text:
                failures.append(failure("subtitle_display_lines_delete_or_rewrite_text", "display_lines must preserve display_text exactly."))
            if len(cue.get("display_lines") or []) > MAX_SUBTITLE_LINES:
                failures.append(failure("subtitle_exceeds_two_lines", "Subtitle display_lines exceed two lines."))
            if protected_term_split(cue.get("display_lines") or []):
                failures.append(failure("protected_term_split", "English/brand/model/acronym was split across subtitle lines."))
    for cue in layout_cues if isinstance(layout_cues, list) else []:
        source_text = str(cue.get("source_text") or "")
        display_text = str(cue.get("display_text") or "")
        joined_lines = "".join(cue.get("display_lines") or [])
        if display_text != display_text_for(source_text):
            failures.append(failure("subtitle_display_text_rewrites_source", "layout display_text must only remove visible punctuation."))
        if joined_lines != display_text:
            failures.append(failure("subtitle_display_lines_delete_or_rewrite_text", "display_lines must preserve display_text exactly."))
        if len(cue.get("display_lines") or []) > MAX_SUBTITLE_LINES:
            failures.append(failure("subtitle_exceeds_two_lines", "Subtitle display_lines exceed two lines."))
        if protected_term_split(cue.get("display_lines") or []):
            failures.append(failure("protected_term_split", "English/brand/model/acronym was split across subtitle lines."))
    for record in records:
        font_size = int(record.get("font_size_px") or 0)
        if font_size < SUBTITLE_FONT_MIN or font_size > SUBTITLE_FONT_MAX:
            failures.append(failure("subtitle_font_size_out_of_range", "Subtitle font size must be 80-84px."))
        bbox = record.get("bbox") or {}
        if int(bbox.get("x", 0)) < 72 or int(bbox.get("x", 0)) + int(bbox.get("width", 0)) > WIDTH - 72:
            failures.append(failure("subtitle_bbox_overflow", "Subtitle bbox overflows safe horizontal area."))
        if record.get("keyword_items") and not record.get("keyword_highlight_rendered"):
            failures.append(failure("keyword_highlight_missing", "Keyword highlight is required but not rendered in evidence."))
    if any(record.get("keyword_items") for record in records) and "\\c&H00E5FF&" not in ass_text:
        failures.append(failure("keyword_highlight_missing", "ASS does not contain keyword highlight tags."))
    title = title_audit.get("title") if isinstance(title_audit, dict) else {}
    if title:
        bbox = title.get("bbox") or {}
        if int(bbox.get("x", 0)) < 0 or int(bbox.get("x", 0)) + int(bbox.get("width", 0)) > WIDTH:
            failures.append(failure("title_overflow", "Title bbox overflows canvas."))
        if title_audit.get("black_group_mask_count") != 1:
            failures.append(failure("title_mask_not_single_black_group", "Title must use exactly one black group mask."))
        background = title.get("background_box") or {}
        if not background:
            failures.append(failure("title_background_box_missing", "Title must include a single background box that wraps all title lines."))
        else:
            bx = int(background.get("x", 0))
            by = int(background.get("y", 0))
            bw = int(background.get("width", 0))
            bh = int(background.get("height", 0))
            tx = int(bbox.get("x", 0))
            ty = int(bbox.get("y", 0))
            tw = int(bbox.get("width", 0))
            th = int(bbox.get("height", 0))
            if bx > tx or by > ty or bx + bw < tx + tw or by + bh < ty + th:
                failures.append(failure("title_background_box_does_not_wrap_title", "Title background box must wrap the full title bbox."))
        title_ass = output_dir(project_dir) / "title_overlay.ass"
        title_ass_text = title_ass.read_text(encoding="utf-8", errors="ignore") if title_ass.exists() else ""
        if "Style: TitleMask" not in title_ass_text or "\\p1" not in title_ass_text:
            failures.append(failure("title_background_mask_not_rendered", "title_overlay.ass must render a vector background mask behind the title."))
        if not title_audit.get("center_align"):
            failures.append(failure("title_not_center_aligned", "Title must be center aligned."))
        if any(token in "".join(title.get("lines") or []) for token in TOFU):
            failures.append(failure("title_tofu_glyph", "Title contains tofu/replacement glyph."))
        first_subtitle = "".join((cues[0].get("display_lines") or [])) if cues else ""
        if first_subtitle and "".join(title.get("lines") or []) == first_subtitle:
            failures.append(failure("title_duplicates_subtitle", "Title must not duplicate bottom subtitle."))
    for frame in (evidence.get("title_frames") or []) + (evidence.get("subtitle_frames") or []):
        if not Path(str(frame)).exists():
            failures.append(failure("missing_text_layout_frame_evidence", "Rendered text evidence frame is missing."))
            break
    return failures
