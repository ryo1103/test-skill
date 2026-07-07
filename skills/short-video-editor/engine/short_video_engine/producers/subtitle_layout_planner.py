from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..contracts import read_json, write_json
from ..paths import plan_dir
from ..stage_result import current_command, failure
from ..stages.s1_script_and_subtitles import display_text_for


WIDTH = 1080
SUBTITLE_FONT = 82
MAX_SUBTITLE_LINES = 2
MAX_CHARS_PER_LINE = 14
VISIBLE_WIDTH = WIDTH - 144
PROTECTED_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+/#-]*(?:\s+[A-Za-z0-9][A-Za-z0-9._+/#-]*)*")
DOMAIN_PROTECTED_TERMS = [
    "GlassBridge",
    "FAU",
    "FAU时代",
    "AI",
    "AI数据中心",
    "光互连",
    "光互连方案",
    "硅光芯片",
    "光模块",
    "光纤连接器",
    "晶圆制造",
    "半导体",
    "供应链",
    "稳定精准",
    "头部客户",
    "客户验证",
    "规模量产",
]
CLAUSE_PUNCT_RE = re.compile(r"[，。！？；：,.!?;:]")
SOFT_BOUNDARY_TERMS = [
    "甚至",
    "如果",
    "但如果",
    "很可能",
    "你可以",
    "一头",
    "另一头",
    "负责",
    "以前",
    "过去",
    "不仅",
    "生产效率",
    "后期维护",
    "而GlassBridge",
    "GlassBridge主要",
    "而不是",
    "谁先",
    "只有",
]
PHRASE_TERMS = sorted(
    set(
        DOMAIN_PROTECTED_TERMS
        + [
            "一块玻璃",
            "康宁股价",
            "很多人",
            "直接终结",
            "讨论GlassBridge",
            "短期不会",
            "下一代",
            "发展方向",
            "一颗芯片",
            "新的光模块",
            "一座玻璃桥",
            "把它理解成",
            "一根根光纤",
            "连接的光纤",
            "精准对准",
            "精度极高",
            "高精度设备",
            "越来越大",
            "越来越多",
            "成本越来越高",
            "效率越来越低",
            "非常麻烦",
            "GlassBridge提供了",
            "另一种思路",
            "人工完成",
            "精密对准",
            "一次做好",
            "更简单",
            "更稳定",
            "更容易",
            "已经成熟",
            "更高密度",
            "两种技术",
            "大概率",
            "不用急着",
            "真正值得关注",
            "真正进入",
            "技术价值",
            "真正兑现",
        ]
    ),
    key=len,
    reverse=True,
)
SEMANTIC_SPLIT_PREFIX_PATTERNS = [
    re.compile(r"^(未来很长一段时间)(.+)$"),
    re.compile(r"^(如果还是靠一根一根去校准)(.+)$"),
    re.compile(r"^(如果还是靠人工校准)(.+)$"),
]
SEMANTIC_BOUNDARY_TERMS = [
    "而不是",
    "但",
    "但是",
    "不仅",
    "所以",
    "因此",
    "而谁",
    "谁先",
]
SEMANTIC_LINE_BOUNDARY_TERMS = [
    "明天",
    "而不是",
    "不仅",
    "生产效率",
    "后期维护",
    "谁先",
]


def text_width(text: str, font_size: int = SUBTITLE_FONT) -> int:
    width = 0
    for char in text:
        width += int(font_size * (0.54 if ord(char) < 128 else 1.0))
    return width


def protected_spans(text: str) -> list[tuple[int, int]]:
    spans = [(m.start(), m.end()) for m in PROTECTED_RE.finditer(text)]
    for term in DOMAIN_PROTECTED_TERMS:
        start = 0
        while term and (index := text.find(term, start)) >= 0:
            spans.append((index, index + len(term)))
            start = index + len(term)
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def display_tokens(text: str) -> list[str]:
    segmented = segment_display_text(text)
    if len(segmented) > 1:
        return segmented
    spans = protected_spans(text)
    tokens: list[str] = []
    i = 0
    while i < len(text):
        protected = next((span for span in spans if span[0] == i), None)
        if protected:
            tokens.append(text[protected[0] : protected[1]])
            i = protected[1]
        else:
            tokens.append(text[i])
            i += 1
    return tokens


def segment_display_text(text: str) -> list[str]:
    """Return display-safe phrase tokens for Chinese subtitle layout.

    Prefer optional mature Chinese segmentation when present, but keep a
    deterministic lexicon fallback so the engine has no hard runtime dependency.
    """
    text = str(text or "")
    if not text:
        return []
    try:  # optional dependency, deliberately not required by the engine
        import jieba  # type: ignore

        raw_tokens = [str(token) for token in jieba.lcut(text, HMM=False) if str(token)]
        return merge_protected_token_fragments(text, raw_tokens)
    except Exception:
        pass
    tokens: list[str] = []
    i = 0
    while i < len(text):
        protected = next((span for span in protected_spans(text) if span[0] == i), None)
        if protected:
            tokens.append(text[protected[0] : protected[1]])
            i = protected[1]
            continue
        matched = next((term for term in PHRASE_TERMS if text.startswith(term, i)), None)
        if matched:
            tokens.append(matched)
            i += len(matched)
            continue
        tokens.append(text[i])
        i += 1
    return tokens


def merge_protected_token_fragments(text: str, tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    protected = protected_spans(text)
    result: list[str] = []
    cursor = 0
    buffer = ""
    buffer_end = 0
    for token in tokens:
        start = text.find(token, cursor)
        if start < 0:
            result.append(token)
            continue
        end = start + len(token)
        crossing = next((span for span in protected if span[0] <= start < span[1]), None)
        if crossing:
            buffer += token
            buffer_end = end
            if buffer_end >= crossing[1]:
                result.append(buffer)
                buffer = ""
        else:
            if buffer:
                result.append(buffer)
                buffer = ""
            result.append(token)
        cursor = end
    if buffer:
        result.append(buffer)
    return result


def split_display_lines(text: str, font_size: int = SUBTITLE_FONT) -> list[str]:
    if len(text) <= MAX_CHARS_PER_LINE and text_width(text, font_size) <= VISIBLE_WIDTH:
        return [text]
    balanced = balanced_two_line_split(text, font_size)
    if balanced:
        return balanced
    lines: list[str] = []
    current = ""
    for chunk in display_tokens(text):
        candidate = current + chunk
        if current and (len(candidate) > MAX_CHARS_PER_LINE or text_width(candidate, font_size) > VISIBLE_WIDTH):
            lines.append(current)
            current = chunk
        else:
            current = candidate
    if current:
        lines.append(current)
    return improve_semantic_line_breaks(text, lines, font_size)


def balanced_two_line_split(text: str, font_size: int = SUBTITLE_FONT) -> list[str] | None:
    candidates = natural_boundary_indexes(text)
    best: tuple[float, list[str]] | None = None
    for index in candidates:
        if index <= 0 or index >= len(text) or inside_protected_span(text, index):
            continue
        left, right = text[:index], text[index:]
        if len(left) < 2 or len(right) < 2:
            continue
        if not safe_subtitle_width([left, right], font_size):
            continue
        score = line_break_score(left, right, font_size)
        if best is None or score < best[0]:
            best = (score, [left, right])
    return best[1] if best else None


def natural_boundary_indexes(text: str) -> list[int]:
    indexes = set()
    cursor = 0
    for token in display_tokens(text):
        cursor += len(token)
        indexes.add(cursor)
    for term in SOFT_BOUNDARY_TERMS + SEMANTIC_LINE_BOUNDARY_TERMS:
        start = 1
        while term and (index := text.find(term, start)) >= 0:
            indexes.add(index)
            if index + len(term) < len(text):
                indexes.add(index + len(term))
            start = index + len(term)
    return sorted(indexes)


def line_break_score(left: str, right: str, font_size: int) -> float:
    left_width = text_width(left, font_size)
    right_width = text_width(right, font_size)
    score = abs(left_width - right_width)
    score += abs(len(left) - len(right)) * font_size * 0.8
    if left[-1:] in {"的", "把", "和", "也", "更", "越", "一", "出", "稳", "精", "时", "连", "提", "已", "急", "理"}:
        score += font_size * 4
    if right[:1] in {"的", "了", "吗", "代", "定", "率", "来", "准", "出", "接", "供", "经", "着", "解"}:
        score += font_size * 5
    if any(right.startswith(term) for term in ("明天", "而不是", "不仅", "生产效率", "后期维护", "谁先")):
        score -= font_size * 3
    if re.search(r"[A-Za-z0-9]$", left) and re.match(r"^[A-Za-z0-9]", right):
        score += font_size * 8
    return score


def improve_semantic_line_breaks(text: str, lines: list[str], font_size: int = SUBTITLE_FONT) -> list[str]:
    if len(lines) != 2:
        return lines
    if min(len(lines[0]), len(lines[1])) > 1:
        return lines
    for term in SEMANTIC_LINE_BOUNDARY_TERMS:
        index = text.find(term, 1)
        if index <= 0 or inside_protected_span(text, index):
            continue
        candidate = [text[:index], text[index:]]
        if all(candidate) and safe_subtitle_width(candidate, font_size):
            return candidate
    return lines


def safe_subtitle_width(lines: list[str], font_size: int = SUBTITLE_FONT) -> bool:
    return all(text_width(line, font_size) <= VISIBLE_WIDTH for line in lines)


def split_display_text_into_cue_chunks(text: str, source_text: str | None = None) -> list[str]:
    semantic_chunks = split_display_text_by_semantics(text, source_text)
    if len(semantic_chunks) > 1:
        chunks: list[str] = []
        for chunk in semantic_chunks:
            chunks.extend(split_display_text_into_width_chunks(chunk))
        return chunks
    return split_display_text_into_width_chunks(text)


def split_display_text_into_width_chunks(text: str) -> list[str]:
    lines = split_display_lines(text)
    if len(lines) <= MAX_SUBTITLE_LINES and safe_subtitle_width(lines):
        return [text]
    chunks: list[str] = []
    current = ""
    for token in display_tokens(text):
        candidate = current + token
        candidate_lines = split_display_lines(candidate)
        if current and (len(candidate_lines) > MAX_SUBTITLE_LINES or not safe_subtitle_width(candidate_lines)):
            chunks.append(current)
            current = token
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def split_display_text_by_semantics(text: str, source_text: str | None = None) -> list[str]:
    text = str(text or "")
    if not text:
        return []
    parts = punctuation_display_chunks(source_text, text) if source_text else [text]
    for pattern in SEMANTIC_SPLIT_PREFIX_PATTERNS:
        next_parts: list[str] = []
        for part in parts:
            match = pattern.match(part)
            if match and match.group(1) and match.group(2):
                next_parts.extend([match.group(1), match.group(2)])
            else:
                next_parts.append(part)
        parts = next_parts
    parts = split_before_terms(parts, SEMANTIC_BOUNDARY_TERMS)
    parts = split_before_terms(parts, SOFT_BOUNDARY_TERMS)
    return merge_tiny_semantic_parts([part for part in parts if part])


def punctuation_display_chunks(source_text: str | None, display_text: str) -> list[str]:
    if not source_text:
        return [display_text]
    raw_parts = [part for part in CLAUSE_PUNCT_RE.split(str(source_text)) if part.strip()]
    display_parts = [display_text_for(part) for part in raw_parts]
    display_parts = [part for part in display_parts if part]
    if not display_parts or "".join(display_parts) != display_text:
        return [display_text]
    return display_parts


def split_before_terms(parts: list[str], terms: list[str]) -> list[str]:
    result = parts
    for term in terms:
        next_parts: list[str] = []
        for part in result:
            indexes = term_indexes(part, term)
            if not indexes:
                next_parts.append(part)
                continue
            cursor = 0
            for index in indexes:
                if index <= cursor:
                    continue
                next_parts.append(part[cursor:index])
                cursor = index
            next_parts.append(part[cursor:])
        result = [part for part in next_parts if part]
    return result


def term_indexes(text: str, term: str) -> list[int]:
    indexes = []
    start = 1
    while term and (index := text.find(term, start)) >= 0:
        if not inside_protected_span(text, index):
            indexes.append(index)
        start = index + len(term)
    return indexes


def inside_protected_span(text: str, index: int) -> bool:
    return any(start < index < end for start, end in protected_spans(text))


def merge_tiny_semantic_parts(parts: list[str]) -> list[str]:
    parts = [part for part in parts if part]
    result: list[str] = []
    index = 0
    tiny_width = text_width("五个字")
    while index < len(parts):
        part = parts[index]
        next_part = parts[index + 1] if index + 1 < len(parts) else ""
        if text_width(part) < tiny_width and next_part and can_merge_as_single_cue(part + next_part):
            result.append(part + next_part)
            index += 2
            continue
        elif result and text_width(part) < tiny_width and can_merge_as_single_cue(result[-1] + part):
            result[-1] += part
        else:
            result.append(part)
        index += 1
    return result


def can_merge_as_single_cue(text: str) -> bool:
    lines = split_display_lines(text)
    return len(lines) <= MAX_SUBTITLE_LINES and safe_subtitle_width(lines)


def split_long_cues_for_layout(cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    layout_cues: list[dict[str, Any]] = []
    for cue in cues:
        source_text = str(cue.get("source_text") or cue.get("text") or "")
        display_text = str(cue.get("display_text") or display_text_for(source_text))
        semantic_chunks = split_display_text_by_semantics(display_text, source_text)
        chunks = split_display_text_into_cue_chunks(display_text, source_text)
        split_origin = "semantic_split_from_source_cue" if len(semantic_chunks) > 1 else "split_from_source_cue"
        if len(chunks) <= 1:
            child = {**cue}
            child["display_text"] = display_text
            child["display_lines"] = split_display_lines(display_text)
            child["layout_origin"] = "source_cue"
            layout_cues.append(child)
            continue
        start = float(cue.get("start") or 0)
        end = float(cue.get("end") or start)
        duration = max(0.0, end - start)
        weights = [max(text_width(chunk), 1) for chunk in chunks]
        total_weight = sum(weights)
        cursor = start
        parent_id = str(cue.get("cue_id") or f"cue_{len(layout_cues) + 1:03d}")
        for index, chunk in enumerate(chunks, start=1):
            next_cursor = end if index == len(chunks) else start + duration * (sum(weights[:index]) / total_weight)
            child = {**cue}
            child["cue_id"] = f"{parent_id}_l{index:02d}"
            child["parent_cue_id"] = parent_id
            child["parent_source_text"] = source_text
            child["source_text"] = chunk
            child["display_text"] = chunk
            child["display_lines"] = split_display_lines(chunk)
            child["start"] = round(cursor, 3)
            child["end"] = round(next_cursor, 3)
            child["layout_origin"] = split_origin
            child["semantic_parent_cue_id"] = parent_id if split_origin == "semantic_split_from_source_cue" else None
            layout_cues.append(child)
            cursor = next_cursor
    return layout_cues


def protected_term_split(lines: list[str]) -> bool:
    for left, right in zip(lines, lines[1:]):
        joined = left + right
        boundary = len(left)
        for start, end in protected_spans(joined):
            if start < boundary < end:
                return True
        if re.search(r"[A-Za-z0-9]$", left) and re.match(r"^[A-Za-z0-9]", right):
            return True
    return False


def validate_layout_cues(source_cues: list[dict[str, Any]], layout_cues: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    source_display = "".join(str(cue.get("display_text") or display_text_for(str(cue.get("source_text") or ""))) for cue in source_cues)
    layout_display = "".join(str(cue.get("display_text") or "") for cue in layout_cues)
    if source_display != layout_display:
        failures.append(failure("subtitle_layout_cues_do_not_cover_source_cues", "Layout cues must preserve all source subtitle text in order."))
    for cue in layout_cues:
        display_text = str(cue.get("display_text") or "")
        joined = "".join(cue.get("display_lines") or [])
        if joined != display_text:
            failures.append(failure("subtitle_display_lines_delete_or_rewrite_text", "display_lines must preserve display_text exactly."))
        if len(cue.get("display_lines") or []) > MAX_SUBTITLE_LINES:
            failures.append(failure("subtitle_exceeds_two_lines", "Subtitle display_lines exceed two lines."))
        if not safe_subtitle_width([str(line) for line in cue.get("display_lines") or []]):
            failures.append(failure("subtitle_bbox_overflow", "Subtitle display line exceeds safe horizontal width."))
        if protected_term_split([str(line) for line in cue.get("display_lines") or []]):
            failures.append(failure("protected_term_split", "Protected term was split across subtitle lines."))
    return failures


def plan_subtitle_layout(project_dir: Path) -> tuple[list[Path], list[dict[str, str]]]:
    source_path = plan_dir(project_dir) / "subtitle_cues.json"
    payload = read_json(source_path, {})
    source_cues = payload.get("cues") if isinstance(payload, dict) else []
    source_cues = [cue for cue in source_cues if isinstance(cue, dict)]
    layout_cues = split_long_cues_for_layout(source_cues)
    failures = validate_layout_cues(source_cues, layout_cues)
    split_count = sum(1 for cue in layout_cues if cue.get("layout_origin") in {"split_from_source_cue", "semantic_split_from_source_cue"})
    semantic_split_count = sum(1 for cue in layout_cues if cue.get("layout_origin") == "semantic_split_from_source_cue")
    layout_path = plan_dir(project_dir) / "subtitle_layout_cues.json"
    plan_path = plan_dir(project_dir) / "subtitle_layout_plan.json"
    audit_path = plan_dir(project_dir) / "subtitle_readability_audit.json"
    common = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "stage": "S1_5_subtitle_layout_planning",
        "command": " ".join(current_command()),
    }
    write_json(layout_path, {**common, "source": "work/plan/subtitle_cues.json", "cues": layout_cues})
    write_json(
        plan_path,
        {
            **common,
            "source_cue_count": len(source_cues),
            "layout_cue_count": len(layout_cues),
            "split_layout_cue_count": split_count,
            "semantic_split_layout_cue_count": semantic_split_count,
            "max_lines": MAX_SUBTITLE_LINES,
            "font_size_px": SUBTITLE_FONT,
            "protected_terms": DOMAIN_PROTECTED_TERMS,
        },
    )
    write_json(
        audit_path,
        {
            **common,
            "status": "PASS" if not failures else "FINAL_BLOCKED",
            "source_cue_count": len(source_cues),
            "layout_cue_count": len(layout_cues),
            "split_layout_cue_count": split_count,
            "semantic_split_layout_cue_count": semantic_split_count,
            "failure_codes": [item["code"] for item in failures],
            "failures": failures,
        },
    )
    return [layout_path, plan_path, audit_path], failures
