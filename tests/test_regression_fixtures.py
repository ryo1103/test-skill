from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_short_video_engine import (
    CLI,
    init_project_with_media,
    mutate_json,
    mutate_manifest,
    prepare_s2_project,
    prepare_s4_project,
    prepare_s6_project,
    prepare_s8_project,
    run_cmd,
    write_manual_timestamps,
)


FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "projects"


def fixture_specs() -> list[dict]:
    specs = []
    for path in sorted(FIXTURES_ROOT.glob("*/fixture.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["fixture_dir"] = path.parent
        specs.append(payload)
    return specs


@pytest.mark.parametrize("spec", fixture_specs(), ids=lambda spec: spec["scenario"])
def test_regression_fixture_failure_codes(tmp_path: Path, spec: dict) -> None:
    project = tmp_path / spec["scenario"]
    SCENARIOS[spec["scenario"]](project)
    final_report = project / "output" / "FINAL_REPORT.md"
    if final_report.exists():
        final_report.unlink()

    result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", spec["stage"]])

    assert result.returncode != 0, result.stdout
    payload = json.loads(result.stdout)
    actual_codes = set(payload.get("failure_codes") or [])
    expected_codes = set(spec["expected_failure_codes"])
    assert expected_codes <= actual_codes
    assert not final_report.exists()


def missing_media_project(project: Path) -> None:
    run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"])


def subtitle_rewrite_project(project: Path) -> None:
    init_project_with_media(project)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"], check=True)
    write_manual_timestamps(project, ["第一句话。", "第二句话。"])
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S1_script_and_subtitles", "--to-stage", "S1_script_and_subtitles", "--strict"], check=True)
    mutate_json(project / "work" / "plan" / "subtitle_cues.json", lambda payload: payload["cues"][0].update({"display_text": "改写字幕"}))


def proportional_timing_project(project: Path) -> None:
    init_project_with_media(project)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"], check=True)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S1_script_and_subtitles", "--to-stage", "S1_script_and_subtitles", "--strict"])


def request_only_assets_project(project: Path) -> None:
    run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
    request = project / "work" / "plan" / "asset_search_remediation_request.json"
    request.write_text(json.dumps({"provider": "pexels", "queued": [{"query": "ai server"}]}), encoding="utf-8")
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S3_asset_sourcing", "--to-stage", "S3_asset_sourcing"])


def fake_motion_static_png_project(project: Path) -> None:
    prepare_s2_project(project, script="开场介绍一句。不是成本问题而是效率问题。最后总结观点。", duration=3.0)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S2_visual_plan", "--to-stage", "S2_visual_plan"], check=True)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S4_5_motion_icon_preparation", "--to-stage", "S4_5_motion_icon_preparation"], check=True)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
    mutate_json(project / "work" / "plan" / "motion_layers.json", lambda payload: payload["layers"][0].update({"layer_type": "static_png"}))


def final_short_video_stream_project(project: Path) -> None:
    prepare_s8_project(project)
    mutate_json(
        project / "work" / "plan" / "final_render_log.json",
        lambda payload: payload.update({"final_video_stream_duration": 1.0, "final_audio_stream_duration": 3.0}),
    )


def title_overflow_project(project: Path) -> None:
    prepare_s6_project(project)
    mutate_json(project / "work" / "plan" / "title_layout_audit.json", lambda payload: payload["title"]["bbox"].update({"x": -10}))


def final_conclusion_broll_project(project: Path) -> None:
    prepare_s4_project(project)

    def final_broll(rows: list[dict[str, str]]) -> None:
        rows[-1]["visual_mode"] = "broll_fullscreen"

    mutate_manifest(project, final_broll)


SCENARIOS = {
    "missing_media_project": missing_media_project,
    "subtitle_rewrite_project": subtitle_rewrite_project,
    "proportional_timing_project": proportional_timing_project,
    "request_only_assets_project": request_only_assets_project,
    "fake_motion_static_png_project": fake_motion_static_png_project,
    "final_short_video_stream_project": final_short_video_stream_project,
    "title_overflow_project": title_overflow_project,
    "final_conclusion_broll_project": final_conclusion_broll_project,
}
