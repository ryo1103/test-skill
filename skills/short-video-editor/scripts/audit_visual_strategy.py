#!/usr/bin/env python3
"""Audit script-to-visual planning before asset sourcing or rendering."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from workflow_audit_lib import clean_text, fail, meaningful_rows, plan_dir, read_csv, to_float, write_audit


REQUIRED_COLUMNS = [
    "shot",
    "script_fragment",
    "narrative_role",
    "logic_type",
    "scene_type",
    "renderer",
    "broll_keywords",
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
    "user_review_needed",
]

REQUIRED_TRIGGER_RE = re.compile(
    r"process|流程|step|comparison|对比|before|after|前后|timeline|时间线|cause|effect|因果|caus|"
    r"kpi|data|数据|指标|system|structure|系统|结构|decision|决策|not\s+.+\s+but|不是.+而是|"
    r"cost|成本|efficiency|效率|risk|风险|pressure|压力|migration|迁移|2\+|two.+kpi",
    re.IGNORECASE,
)


def is_yes_no(value: str) -> bool:
    return str(value or "").strip().lower() in {"yes", "no", "true", "false", "y", "n", "是", "否"}


def trigger_required(row: dict[str, str]) -> bool:
    text = " ".join(
        str(row.get(key, "") or "")
        for key in ("logic_type", "script_fragment", "visual_pattern", "data_visual_type", "narrative_role")
    )
    return bool(REQUIRED_TRIGGER_RE.search(text))


def nonempty_jsonish(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text in {"{}", "[]", "none", "None", "null"}:
        return False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return True
    if parsed in ({}, [], None, ""):
        return False
    return True


def has_user_visible_warning(row: dict[str, str]) -> bool:
    for key in ("user_visible_warning", "downgrade_warning", "warning"):
        if clean_text(row.get(key)):
            return True
    return str(row.get("user_review_needed", "") or "").strip().lower() in {"yes", "true", "是", "required"}


def audit(project_dir: Path) -> int:
    path = plan_dir(project_dir) / "visual_strategy.csv"
    raw_rows = read_csv(path)
    rows = meaningful_rows(raw_rows)
    failures: list[dict] = []
    warnings: list[dict] = []
    checked_required_triggers: list[str] = []

    if not path.exists():
        failures.append(fail("visual_strategy", "missing_visual_strategy_csv", "work/plan/visual_strategy.csv is missing.", "Create the script-to-visual plan before continuing."))
    elif not rows:
        failures.append(fail("visual_strategy", "empty_visual_strategy_csv", "visual_strategy.csv has no actual planning rows.", "Fill one row per semantic unit; a header-only CSV is not enough."))

    if raw_rows:
        columns = set(raw_rows[0].keys())
    elif path.exists():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            columns = set(next(csv.reader(handle), []))
    else:
        columns = set()
    for column in REQUIRED_COLUMNS:
        if column not in columns:
            failures.append(fail("visual_strategy", "missing_visual_strategy_column", f"visual_strategy.csv is missing required column {column}.", "Regenerate or extend visual_strategy.csv with the full required schema.", column=column))

    for index, row in enumerate(rows, start=2):
        shot = row.get("shot") or row.get("shot_id") or f"row_{index}"
        for column in ("shot", "script_fragment", "narrative_role", "logic_type", "scene_type", "renderer"):
            if not clean_text(row.get(column)):
                failures.append(fail("visual_strategy", "missing_required_row_value", f"{shot} is missing {column}.", "Complete every semantic planning row before audit.", row=index, column=column))

        candidate = str(row.get("ae_overlay_candidate", "") or "").strip()
        if not is_yes_no(candidate):
            failures.append(fail("visual_strategy", "missing_ae_hyperframe_decision", f"{shot} does not explicitly set ae_overlay_candidate to yes/no.", "Evaluate every semantic unit for AE/PPT/HyperFrame usefulness.", row=index))

        required_trigger = trigger_required(row)
        if required_trigger:
            checked_required_triggers.append(str(shot))
            if not is_yes_no(candidate):
                failures.append(fail("visual_strategy", "required_trigger_without_candidate_decision", f"{shot} contains process/comparison/timeline/cause/data/system/decision logic but lacks an AE/HyperFrame decision.", "Fill ae_overlay_candidate, ae_overlay_type, visual_pattern, hyperframe_score, and downgrade fields if needed.", row=index))
            if not clean_text(row.get("visual_pattern")):
                failures.append(fail("visual_strategy", "required_trigger_missing_visual_pattern", f"{shot} needs a concrete visual_pattern.", "Choose process_flow, comparison, timeline, cause_effect_chain, kpi_card, system_diagram, decision_tree, or a defensible downgrade.", row=index))

        score = to_float(row.get("hyperframe_score"), -999)
        renderer = str(row.get("renderer", "") or "").lower()
        hyperframe_allowed = str(row.get("hyperframe_allowed", "") or "").strip().lower() in {"true", "yes", "1", "是"}
        candidate_yes = candidate.lower() in {"yes", "true", "y", "是"}

        if score >= 3 or renderer == "hyperframe" or hyperframe_allowed:
            if not clean_text(row.get("hyperframe_reason")):
                failures.append(fail("visual_strategy", "missing_hyperframe_reason", f"{shot} is accepted/scored as HyperFrame but lacks hyperframe_reason.", "Explain why HyperFrame is needed over B-roll or a light overlay.", row=index))
            if not clean_text(row.get("why_simple_broll_is_not_enough")):
                failures.append(fail("visual_strategy", "missing_why_broll_not_enough", f"{shot} is accepted/scored as HyperFrame but lacks why_simple_broll_is_not_enough.", "Document why simple B-roll cannot communicate this logic clearly.", row=index))
            if not nonempty_jsonish(row.get("design_plan", "")):
                failures.append(fail("visual_strategy", "missing_design_plan", f"{shot} lacks a non-empty design_plan.", "Write a compact pre-build design plan before coding any HyperFrame.", row=index))
            if not nonempty_jsonish(row.get("animation_plan", "")):
                failures.append(fail("visual_strategy", "missing_animation_plan", f"{shot} lacks a non-empty animation_plan.", "Define setup, enter, build, hold, and exit/settle stages.", row=index))

        downgraded_required_trigger = required_trigger and not (renderer == "hyperframe" or candidate_yes or score >= 3)
        if downgraded_required_trigger:
            if not clean_text(row.get("downgrade_reason")):
                failures.append(fail("visual_strategy", "required_trigger_missing_downgrade_reason", f"{shot} appears to downgrade a required-trigger logic unit without downgrade_reason.", "Explain the downgrade before continuing.", row=index))
            if not clean_text(row.get("why_simple_broll_is_enough")):
                failures.append(fail("visual_strategy", "required_trigger_missing_broll_enough_reason", f"{shot} lacks why_simple_broll_is_enough.", "Document why B-roll/light overlay is enough for the required-trigger unit.", row=index))
            if not has_user_visible_warning(row):
                failures.append(fail("visual_strategy", "required_trigger_missing_user_warning", f"{shot} downgrade lacks a user-visible warning/review marker.", "Add user_visible_warning/downgrade_warning or set user_review_needed=yes.", row=index))

        overlay_requires_broll = candidate_yes or "broll" in str(row.get("overlay_layer_plan", "") or "").lower()
        if overlay_requires_broll and not clean_text(row.get("broll_base_asset")):
            row_text = " ".join(str(value or "").lower() for value in row.values())
            if "needs_sourcing" not in row_text:
                failures.append(fail("visual_strategy", "overlay_missing_broll_base_asset", f"{shot} needs an AE/HyperFrame overlay over B-roll but lacks broll_base_asset or needs_sourcing.", "Select the B-roll base asset or mark needs_sourcing before rendering.", row=index))

    status = "failed" if failures else "passed"
    return write_audit(
        plan_dir(project_dir) / "visual_strategy_audit.json",
        status,
        failures,
        warnings=warnings,
        checked_rows=len(rows),
        required_trigger_shots=checked_required_triggers,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit visual strategy planning completeness.")
    parser.add_argument("project_dir")
    args = parser.parse_args()
    return audit(Path(args.project_dir).expanduser().resolve())


if __name__ == "__main__":
    sys.exit(main())
