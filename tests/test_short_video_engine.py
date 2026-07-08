from __future__ import annotations

import json
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import struct
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "short-video-editor"
CLI = SKILL_ROOT / "engine" / "short_video_engine" / "cli.py"
sys.path.insert(0, str(SKILL_ROOT / "engine"))


def run_cmd(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("SVIDEO_ALLOW_INTERNAL_MOTION_CANVAS_TEST_RENDERER", "1")
    result = subprocess.run([sys.executable, *args], cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if check and result.returncode != 0:
        raise AssertionError(f"command failed: {result.args}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise unittest.SkipTest("ffmpeg is required for real media fixture tests")
    return ffmpeg


def create_video(path: Path, duration: float = 2.0, color: str = "black", frequency: int = 1000) -> None:
    ffmpeg = require_ffmpeg()
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x240:r=25:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration={duration}",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise AssertionError(f"ffmpeg fixture failed\nstdout={result.stdout}\nstderr={result.stderr}")


def init_project_with_media(project: Path, script: str = "第一句话。第二句话。", duration: float = 2.0) -> None:
    run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
    (project / "script.txt").write_text(script, encoding="utf-8")
    create_video(project / "oral.mp4", duration=duration)


def write_manual_timestamps(project: Path, texts: list[str], duration: float = 2.0, provenance: bool = True) -> None:
    step = duration / len(texts)
    payload = {
        "alignment_method": "manual_phrase_timestamps",
        "cues": [
            {"text": text, "start": round(index * step, 3), "end": round((index + 1) * step, 3)}
            for index, text in enumerate(texts)
        ],
    }
    if provenance:
        payload["provenance"] = {"source": "unit_test_manual_timestamps", "provided_by": "test"}
    (project / "work" / "plan" / "manual_phrase_timestamps.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def prepare_s2_project(project: Path, script: str = "普通解释第一句。最后总结观点。", duration: float = 2.0) -> None:
    init_project_with_media(project, script=script, duration=duration)
    texts = [part for part in script.replace("！", "。").replace("？", "。").split("。") if part]
    texts = [f"{part}。" for part in texts]
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"], check=True)
    write_manual_timestamps(project, texts, duration=duration)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S1_script_and_subtitles", "--to-stage", "S1_script_and_subtitles", "--strict"], check=True)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S1_5_subtitle_layout_planning", "--to-stage", "S1_5_subtitle_layout_planning"], check=True)


def write_asset_manifest(project: Path, records: list[dict]) -> None:
    manifest = project / "assets" / "metadata" / "asset_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"generated_by": "short_video_engine", "assets": records}, ensure_ascii=False), encoding="utf-8")


def valid_asset_record(project: Path, index: int, source_url: str | None = None, local_path: Path | None = None, duration: float = 0.6, **overrides) -> dict:
    if local_path is None:
        local_path = project / "assets" / "raw" / "video" / f"fixture_{index:02d}.mp4"
        create_video(local_path, duration=duration, color="black" if index % 2 else "blue", frequency=800 + index * 10)
    record = {
        "asset_key": f"asset_{index:02d}",
        "shot_id": f"shot_{index:03d}",
        "provider": "asset_library",
        "media_class": "video_broll",
        "source_key": f"source_{index:02d}",
        "provider_asset_id": f"provider_asset_{index:02d}",
        "source_url": source_url or f"https://example.com/video/{index}",
        "direct_download_url": f"https://example.com/download/{index}.mp4",
        "local_path": str(local_path),
        "license_or_note": "test fixture license",
        "external_source": True,
        "provenance_type": "asset_library",
        "materialized_status": "passed",
        "ffprobe_decode_status": "passed",
        "relevance_status": "passed",
    }
    record.update(overrides)
    return record


def prepare_s4_project(project: Path) -> None:
    script = "普通解释第一句。普通解释第二句。最后总结观点。"
    prepare_s2_project(project, script=script, duration=3.0)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S2_visual_plan", "--to-stage", "S2_visual_plan"], check=True)
    records = [valid_asset_record(project, index, duration=1.2) for index in range(1, 4)]
    write_asset_manifest(project, records)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S4_base_timeline", "--to-stage", "S4_base_timeline"], check=True)


def mutate_manifest(project: Path, mutator) -> None:
    path = project / "work" / "plan" / "edit_manifest.csv"
    rows = path.read_text(encoding="utf-8").splitlines()
    import csv
    from io import StringIO

    reader = csv.DictReader(StringIO("\n".join(rows)))
    data = list(reader)
    mutator(data)
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(data)
    path.write_text(output.getvalue(), encoding="utf-8")


def prepare_s5_project(project: Path, script: str = "开场介绍一句。不是成本问题而是效率问题。最后总结观点。") -> None:
    prepare_s2_project(project, script=script, duration=2.0)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S2_visual_plan", "--to-stage", "S2_visual_plan"], check=True)


def mutate_motion_layers(project: Path, mutator) -> None:
    path = project / "work" / "plan" / "motion_layers.json"
    payload = read_json(path)
    mutator(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def mutate_graphic_scene_plan(project: Path, mutator) -> None:
    path = project / "work" / "plan" / "graphic_scene_plan.json"
    payload = read_json(path)
    mutator(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def prepare_s6_project(project: Path, script: str = "iPhone 15 Pro表现提升20%。最后总结观点。") -> None:
    prepare_s2_project(project, script=script, duration=2.0)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S6_text_layout", "--to-stage", "S6_text_layout"], check=True)


def mutate_json(path: Path, mutator) -> None:
    payload = read_json(path)
    mutator(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def png_color_type(path: Path) -> int:
    data = path.read_bytes()
    pos = 8
    while pos < len(data):
        length = struct.unpack("!I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            return payload[9]
    return -1


def prepare_s7_project(project: Path) -> None:
    script = "开场介绍一句。不是成本问题而是效率问题。普通解释第二句。最后总结观点。"
    prepare_s2_project(project, script=script, duration=3.0)
    (project / "work" / "plan" / "title_candidates.json").write_text(json.dumps({"candidates": ["效率问题复盘"]}, ensure_ascii=False), encoding="utf-8")
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S2_visual_plan", "--to-stage", "S2_visual_plan"], check=True)
    records = [valid_asset_record(project, index, duration=1.2) for index in range(1, 21)]
    write_asset_manifest(project, records)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S3_asset_sourcing", "--to-stage", "S3_asset_sourcing"], check=True)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S4_base_timeline", "--to-stage", "S4_base_timeline"], check=True)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S6_text_layout", "--to-stage", "S6_text_layout"], check=True)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S7_process_validation", "--to-stage", "S7_process_validation"], check=True)


def prepare_s8_project(project: Path) -> None:
    prepare_s7_project(project)
    run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S8_final_render_and_validation", "--to-stage", "S8_final_render_and_validation"], check=True)


class ShortVideoEngineSmokeTests(unittest.TestCase):
    def test_engine_cli_help(self) -> None:
        result = run_cmd([str(CLI), "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("short-video-editor engine CLI", result.stdout)

    def test_init_creates_project_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            result = run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            self.assertIn("initialized", result.stdout)
            self.assertTrue((project / "work" / "plan").is_dir())
            self.assertTrue((project / "output" / "qc").is_dir())
            self.assertTrue((project / "assets" / "metadata").is_dir())

    def test_missing_media_blocks_s0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "stage_reports" / "S0_intake.json")
            self.assertNotEqual(report["status"], "PASS")
            self.assertIn("missing_script", report["failure_codes"])
            self.assertIn("missing_oral_video", report["failure_codes"])

    def test_empty_script_cannot_pass_s0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            (project / "script.txt").write_text("", encoding="utf-8")
            create_video(project / "oral.mp4")
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "stage_reports" / "S0_intake.json")
            self.assertIn("empty_script", report["failure_codes"])

    def test_ffprobe_failure_cannot_pass_s0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            (project / "script.txt").write_text("第一句话。", encoding="utf-8")
            (project / "oral.mp4").write_text("not a real video", encoding="utf-8")
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "stage_reports" / "S0_intake.json")
            self.assertIn("ffprobe_failed", report["failure_codes"])

    def test_s0_reads_real_video_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            init_project_with_media(project, script="第一句话。", duration=2.0)
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"], check=True)
            self.assertIn('"status": "PASS"', result.stdout)
            intake = read_json(project / "work" / "plan" / "project_intake_report.json")
            self.assertEqual(intake["generated_by"], "short_video_engine")
            self.assertGreater(intake["container_duration"], 0)
            self.assertGreater(intake["audio_stream_duration"], 0)
            self.assertEqual(intake["resolution"]["width"], 320)
            self.assertEqual(intake["resolution"]["height"], 240)
            self.assertGreater(intake["fps"], 0)

    def test_s1_5_splits_subtitles_by_semantic_beats_before_width(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            script = "未来很长一段时间，两种技术大概率会并存，而不是今天出来、明天就替代。最后总结观点。"
            prepare_s2_project(project, script=script, duration=3.0)
            layout = read_json(project / "work" / "plan" / "subtitle_layout_cues.json")
            audit = read_json(project / "work" / "plan" / "subtitle_readability_audit.json")
            chunks = [cue["display_text"] for cue in layout["cues"] if cue.get("parent_cue_id") == "c001"]
            lines_by_chunk = {cue["display_text"]: cue["display_lines"] for cue in layout["cues"] if cue.get("parent_cue_id") == "c001"}
            self.assertGreaterEqual(audit["semantic_split_layout_cue_count"], 3)
            self.assertEqual(chunks[:3], ["未来很长一段时间", "两种技术大概率会并存", "而不是今天出来明天就替代"])
            self.assertEqual(lines_by_chunk["而不是今天出来明天就替代"], ["而不是今天出来", "明天就替代"])
            self.assertFalse(any(chunk.endswith("而不是今") for chunk in chunks))

    def test_s1_5_uses_source_punctuation_and_protects_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            script = "最近很多人都在讨论GlassBridge，甚至有人说，它会直接终结FAU时代。最后总结观点。"
            prepare_s2_project(project, script=script, duration=3.0)
            layout = read_json(project / "work" / "plan" / "subtitle_layout_cues.json")
            chunks = [cue["display_text"] for cue in layout["cues"] if cue.get("parent_cue_id") == "c001"]
            lines = [line for cue in layout["cues"] for line in cue.get("display_lines", [])]
            self.assertEqual(chunks[:3], ["最近很多人都在讨论GlassBridge", "甚至有人说", "它会直接终结FAU时代"])
            self.assertTrue(any("FAU时代" in line for line in lines))
            self.assertFalse(any(line.endswith("FAU时") for line in lines))
            self.assertFalse(any(line == "代" for line in lines))

    def test_dummy_probe_rejected_in_production(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            metadata = project / "work" / "plan" / "final_video_metadata.json"
            metadata.write_text(json.dumps({"probe_source": "dummy_ffprobe_metadata"}), encoding="utf-8")
            result = run_cmd([str(CLI), "validate-final", "--project-dir", str(project)])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "final_validation_report.json")
            self.assertIn("fixture_probe_not_allowed_in_production", report["failure_codes"])

    def test_request_only_asset_not_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            request = project / "work" / "plan" / "asset_search_remediation_request.json"
            request.write_text(json.dumps({"provider": "pexels", "queued": [{"query": "ai server"}]}), encoding="utf-8")
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S3_asset_sourcing", "--to-stage", "S3_asset_sourcing"])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "stage_reports" / "S3_asset_sourcing.json")
            self.assertEqual(report["status"], "FINAL_BLOCKED")
            materialized = read_json(project / "work" / "plan" / "materialized_assets_report.json")
            self.assertEqual(materialized["usable_video_broll_count"], 0)

    def test_s3_queued_provider_rows_do_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            (project / "work" / "plan" / "provider_queue.json").write_text(json.dumps({"queued": [{"provider": "pexels"}]}), encoding="utf-8")
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S3_asset_sourcing", "--to-stage", "S3_asset_sourcing"])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "materialized_assets_report.json")
            self.assertEqual(report["usable_video_broll_count"], 0)

    def test_s3_disallowed_media_classes_do_not_count(self) -> None:
        cases = [
            ("html_recording", {"media_class": "video_broll", "source_url": "file:///tmp/local.html", "provenance_type": "html_recording"}),
            ("screen_recording", {"media_class": "video_broll", "provenance_type": "screen_recording"}),
            ("static_image", {"media_class": "static_image", "local_path": "still.jpg"}),
        ]
        for _name, overrides in cases:
            with self.subTest(_name):
                with tempfile.TemporaryDirectory() as tmp:
                    project = Path(tmp) / "project"
                    run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
                    record = valid_asset_record(project, 1)
                    record.update(overrides)
                    write_asset_manifest(project, [record])
                    result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S3_asset_sourcing", "--to-stage", "S3_asset_sourcing"])
                    self.assertNotEqual(result.returncode, 0)
                    report = read_json(project / "work" / "plan" / "materialized_assets_report.json")
                    self.assertEqual(report["usable_video_broll_count"], 0)

    def test_s3_duplicate_source_url_multiple_trims_count_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            shared_source = "https://example.com/same-source"
            records = [valid_asset_record(project, index, source_url=shared_source) for index in range(1, 4)]
            write_asset_manifest(project, records)
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S3_asset_sourcing", "--to-stage", "S3_asset_sourcing"])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "materialized_assets_report.json")
            self.assertEqual(report["usable_video_broll_count"], 1)
            self.assertGreaterEqual(len(report["duplicate_records"]), 2)

    def test_s3_less_than_20_materialized_video_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            records = [valid_asset_record(project, index) for index in range(1, 5)]
            write_asset_manifest(project, records)
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S3_asset_sourcing", "--to-stage", "S3_asset_sourcing"])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "materialized_assets_report.json")
            self.assertEqual(report["usable_video_broll_count"], 4)
            self.assertIn("insufficient_distinct_materialized_video_broll", report["failure_codes"])

    def test_s3_20_real_fixture_videos_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            run_cmd([str(CLI), "init", "--project-dir", str(project)], check=True)
            records = [valid_asset_record(project, index) for index in range(1, 21)]
            write_asset_manifest(project, records)
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S3_asset_sourcing", "--to-stage", "S3_asset_sourcing"], check=True)
            self.assertIn('"status": "PASS"', result.stdout)
            report = read_json(project / "work" / "plan" / "materialized_assets_report.json")
            self.assertEqual(report["usable_video_broll_count"], 20)

    def test_s4_base_plate_missing_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s4_project(project)
            (project / "output" / "base_plate.mp4").unlink()
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S4_base_timeline"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_base_plate", result.stdout)

    def test_s4_base_plate_shorter_than_audio_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s4_project(project)
            create_video(project / "output" / "base_plate.mp4", duration=1.0)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S4_base_timeline"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("base_plate_output_duration_mismatch", result.stdout)

    def test_s4_broll_segment_over_source_duration_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s4_project(project)

            def overrun(rows):
                for row in rows:
                    if row["visual_mode"] == "broll_fullscreen":
                        row["duration"] = "5.000"
                        break

            mutate_manifest(project, overrun)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S4_base_timeline"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("broll_source_overrun", result.stdout)

    def test_s4_talking_head_uses_same_oral_timecode_as_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s4_project(project)
            manifest = project / "work" / "plan" / "edit_manifest.csv"
            rows = list(csv.DictReader(manifest.read_text(encoding="utf-8").splitlines()))
            talking_rows = [row for row in rows if row["visual_mode"] == "talking_head_fullscreen"]
            self.assertTrue(talking_rows)
            for row in talking_rows:
                self.assertAlmostEqual(float(row["source_in"]), float(row["start"]), places=2)
                self.assertAlmostEqual(float(row["source_out"]), float(row["end"]), places=2)
                self.assertEqual(row["playback_policy"], "same_timecode_from_oral_video")
            render_log = read_json(project / "work" / "plan" / "base_render_log.json")
            talking_trims = [item for item in render_log["trim_intervals"] if item["visual_mode"] == "talking_head_fullscreen"]
            self.assertTrue(talking_trims)
            self.assertTrue(any(float(item["source_in"]) > 0 for item in talking_trims))

    def test_s4_talking_head_timecode_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s4_project(project)

            def desync_talking_head(rows):
                for row in rows:
                    if row["visual_mode"] == "talking_head_fullscreen" and float(row["start"]) > 0:
                        row["source_in"] = "0.000"
                        row["source_out"] = row["duration"]
                        break

            mutate_manifest(project, desync_talking_head)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S4_base_timeline"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("talking_head_timecode_mismatch", result.stdout)

    def test_s4_loop_repeat_freeze_policy_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s4_project(project)

            def bad_policy(rows):
                rows[0]["playback_policy"] = "loop"

            mutate_manifest(project, bad_policy)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S4_base_timeline"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("forbidden_base_plate_padding", result.stdout)

    def test_s4_final_conclusion_broll_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s4_project(project)

            def final_broll(rows):
                rows[-1]["visual_mode"] = "broll_fullscreen"

            mutate_manifest(project, final_broll)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S4_base_timeline"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("final_conclusion_not_talking_head", result.stdout)

    def test_s4_base_plate_contains_overlay_card_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s4_project(project)

            def overlay(rows):
                rows[0]["contains_overlay"] = "true"
                rows[0]["asset_key"] = "card_overlay"

            mutate_manifest(project, overlay)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S4_base_timeline"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("base_plate_contains_overlay", result.stdout)

    def test_s5_motion_generation_request_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            (project / "work" / "plan" / "motion_generation_request.json").write_text(json.dumps({"request": "make motion"}), encoding="utf-8")
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_stage_report", result.stdout)

    def test_s5_static_png_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_motion_layers(project, lambda payload: payload["layers"][0].update({"layer_type": "static_png"}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid_motion_layer_type", result.stdout)

    def test_s5_generated_motion_is_transparent_overlay_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            payload = read_json(project / "work" / "plan" / "motion_layers.json")
            layer = payload["layers"][0]
            self.assertEqual(layer["overlay_compositing_mode"], "transparent_rgba_overlay")
            self.assertEqual(layer["alpha_channel_status"], "passed")
            self.assertGreaterEqual(layer["sequence_frame_count"], 24)
            self.assertTrue(layer["required_animation_stages_completed"])
            self.assertEqual(layer["semantic_readability_status"], "passed")
            self.assertGreaterEqual(layer["template_stage_count"], 4)
            self.assertIn("semantic_template", layer["expression_plan"])
            self.assertIn("效率问题", layer["motion_text_items"])
            self.assertEqual(layer["motion_source_engine"], "motion_canvas")
            self.assertEqual(layer["motion_source_status"], "prepared")
            self.assertEqual(layer["renderer_backend"], "motion_canvas_sequence")
            self.assertEqual(layer["professional_quality_status"], "passed")
            self.assertTrue(layer["motion_design_preset_applied"])
            self.assertIn("graphic_scene_id", layer)
            self.assertIn("motion_layout_boxes", layer)
            self.assertIn("title_reserved", layer["motion_layout_boxes"])
            self.assertIn("subtitle_reserved", layer["motion_layout_boxes"])
            self.assertGreaterEqual(layer["motion_layout_boxes"]["claim"]["y1"], 420)
            self.assertLessEqual(layer["motion_layout_boxes"]["progress"]["y2"], 1480)
            self.assertIn("template_selection", layer["expression_plan"])
            self.assertEqual(layer["expression_plan"]["template_selection"]["selected_template"], layer["motion_pattern_family"])
            self.assertIn("relation_reason", layer["expression_plan"]["template_selection"])
            self.assertTrue(Path(layer["motion_source_project_dir"]).is_dir())
            self.assertTrue((Path(layer["motion_source_project_dir"]) / "motion-props.json").exists())
            self.assertEqual(png_color_type(Path(layer["frame_evidence"]["mid"])), 6)
            self.assertTrue((project / "work" / "plan" / "graphic_scene_plan.json").exists())
            frame_hashes = {Path(layer["frame_evidence"][key]).read_bytes() for key in ("start", "build", "peak", "settle", "end")}
            self.assertGreaterEqual(len(frame_hashes), 4)

    def test_s5_no_pillow_does_not_generate_placeholder_motion(self) -> None:
        from short_video_engine.producers.motion_renderer import renderer

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            original = (renderer.Image, renderer.ImageDraw, renderer.ImageFont)
            renderer.Image = None
            renderer.ImageDraw = None
            renderer.ImageFont = None
            try:
                _layers_path, _report_path, failures = renderer.render_motion(project, motion_renderer="pillow")
            finally:
                renderer.Image, renderer.ImageDraw, renderer.ImageFont = original
            codes = {item["code"] for item in failures}
            self.assertIn("motion_text_renderer_unavailable", codes)
            self.assertIn("motion_placeholder_renderer_forbidden", codes)

    def test_s5_motion_canvas_source_only_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_motion_layers(project, lambda payload: payload["layers"][0].update({"renderer_backend": "motion_canvas_source", "artifact_renderer_backend": "motion_canvas_source", "layer_type": "source_project", "frame_evidence": {}}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("motion_source_only_not_evidence", result.stdout)

    def test_s5_pillow_fallback_cannot_pass_strict_professional_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_motion_layers(project, lambda payload: payload["layers"][0].update({"renderer_backend": "pillow_sequence", "artifact_renderer_backend": "pillow_sequence", "professional_quality_status": "passed"}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("motion_professional_renderer_required", result.stdout)

    def test_s5_graphic_scene_plan_missing_scene_template_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_graphic_scene_plan(project, lambda payload: payload["scenes"][0].pop("scene_template", None))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_scene_template", result.stdout)

    def test_s5_large_empty_panel_fails_motion_design_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_graphic_scene_plan(project, lambda payload: payload["scenes"][0]["quality_target"].update({"no_large_empty_panel": False}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("large_empty_panel_detected", result.stdout)

    def test_s5_missing_stagger_fails_motion_design_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)

            def remove_stagger(payload):
                for stage in payload["scenes"][0]["animation_sequence"]:
                    stage["stagger_sec"] = 0

            mutate_graphic_scene_plan(project, remove_stagger)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_motion_stagger", result.stdout)

    def test_s5_semantic_templates_generate_professional_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            error_project = Path(tmp) / "error_project"
            chip_project = Path(tmp) / "chip_project"
            prepare_s5_project(error_project, script="开场介绍一句。这个错误会导致系统失败需要马上修正。最后总结观点。")
            prepare_s5_project(chip_project, script="开场介绍一句。GlassBridge把芯片和光纤连接器连接成节点网络。最后总结观点。")
            for project, expected in ((error_project, "cause_to_result_scene"), (chip_project, "connector_flow_scene")):
                run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
                scene = read_json(project / "work" / "plan" / "graphic_scene_plan.json")["scenes"][0]
                layer = read_json(project / "work" / "plan" / "motion_layers.json")["layers"][0]
                self.assertEqual(scene["scene_template"], expected)
                self.assertEqual(layer["renderer_backend"], "motion_canvas_sequence")
                for key in ("start", "build", "peak", "settle", "end"):
                    self.assertTrue(Path(layer["frame_evidence"][key]).exists())

    def test_s5_negation_assertion_requires_rejection_and_connector_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project, script="开场介绍一句。GlassBridge它不是一颗芯片，也不是新的光模块，而是一个光纤连接器。最后总结观点。")
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            assertion = read_json(project / "work" / "plan" / "motion_assertions.json")["assertions"][0]
            layer = read_json(project / "work" / "plan" / "motion_layers.json")["layers"][0]
            self.assertEqual(assertion["semantic_action"], "negate_and_redefine")
            self.assertEqual(assertion["slots"]["subject"]["text"], "GlassBridge")
            self.assertEqual(assertion["slots"]["rejected_a"]["text"], "芯片")
            self.assertEqual(assertion["slots"]["rejected_b"]["text"], "光模块")
            self.assertEqual(assertion["slots"]["accepted_definition"]["text"], "光纤连接器")
            self.assertEqual(assertion["slots"]["rejected_a"]["semantic_icon"], "chip")
            self.assertEqual(assertion["slots"]["rejected_b"]["semantic_icon"], "optical_module")
            self.assertEqual(assertion["slots"]["accepted_definition"]["semantic_icon"], "connector")
            self.assertEqual(layer["semantic_icons"]["rejected_a"]["semantic_key"], "chip")
            self.assertEqual(layer["semantic_icons"]["rejected_b"]["semantic_key"], "optical_module")
            self.assertEqual(layer["semantic_icons"]["accepted_definition"]["semantic_key"], "connector")
            for stage in ("reject_a", "reject_b", "reveal_definition", "show_connection_flow"):
                self.assertIn(stage, layer["animation_stages"])

    def test_s5_connector_metaphor_requires_flow_not_floating_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project, script="开场介绍一句。把它理解成一个光纤连接器。最后总结观点。")
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            layer = read_json(project / "work" / "plan" / "motion_layers.json")["layers"][0]
            self.assertEqual(layer["semantic_action"], "connector_metaphor")
            self.assertEqual(layer["semantic_icons"]["input"]["semantic_key"], "input")
            self.assertEqual(layer["semantic_icons"]["connector"]["semantic_key"], "connector")
            self.assertEqual(layer["semantic_icons"]["output"]["semantic_key"], "output")
            for action in ("input_flow", "through_connector", "output_flow"):
                self.assertIn(action, layer["required_visual_actions"])
            mutate_motion_layers(project, lambda payload: payload["layers"][0].update({"semantic_visual_proof": {"non_decorative_scene": True}}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("labels_float_without_relationship", result.stdout)
            self.assertIn("connector_scene_missing_flow", result.stdout)

    def test_s5_metric_growth_requires_delta_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project, script="开场介绍一句。连接规模快速增加。最后总结观点。")
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            layer = read_json(project / "work" / "plan" / "motion_layers.json")["layers"][0]
            self.assertEqual(layer["semantic_action"], "metric_growth")
            for action in ("bar_grow", "number_change", "direction_emphasis"):
                self.assertIn(action, layer["animation_stages"])
            mutate_motion_layers(project, lambda payload: payload["layers"][0]["semantic_visual_proof"].pop("has_metric_delta", None))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("metric_scene_missing_delta", result.stdout)

    def test_s5_process_migration_requires_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project, script="开场介绍一句。人工对准、晶圆制造、一次做好、GlassBridge。最后总结观点。")
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            layer = read_json(project / "work" / "plan" / "motion_layers.json")["layers"][0]
            self.assertEqual(layer["semantic_action"], "process_migration")
            for action in ("old_path", "transition", "new_path"):
                self.assertIn(action, layer["animation_stages"])
            mutate_motion_layers(project, lambda payload: payload["layers"][0]["semantic_visual_proof"].pop("has_transition", None))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("process_scene_missing_transition", result.stdout)

    def test_s5_density_comparison_requires_pressure_and_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project, script="开场介绍一句。FAU 要面向下一代更高密度的光。最后总结观点。")
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            layer = read_json(project / "work" / "plan" / "motion_layers.json")["layers"][0]
            self.assertEqual(layer["semantic_action"], "density_comparison")
            for action in ("old_limit", "requirement_pressure", "new_solution_expansion"):
                self.assertIn(action, layer["animation_stages"])
            mutate_motion_layers(project, lambda payload: payload["layers"][0]["semantic_visual_proof"].update({"has_pressure": False, "has_expansion": False}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("density_scene_missing_pressure_or_expansion", result.stdout)

    def test_s5_required_motion_index_missing_layer_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_motion_layers(project, lambda payload: payload.update({"layers": []}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("required_motion_missing", result.stdout)
            self.assertIn("required_motion_deleted_or_downgraded", result.stdout)

    def test_s5_motion_layer_missing_assertion_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_motion_layers(project, lambda payload: payload["layers"][0].pop("motion_assertion_id", None))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("motion_assertion_missing", result.stdout)

    def test_s5_missing_icon_file_uses_fallback_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project, script="开场介绍一句。GlassBridge它不是一颗芯片，也不是新的光模块，而是一个光纤连接器。最后总结观点。")
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            manifest = read_json(project / "work" / "plan" / "motion_asset_manifest.json")
            sources = {asset["semantic_key"]: asset["source"] for asset in manifest["assets"]}
            self.assertEqual(sources["chip"], "bundled_fallback")
            self.assertEqual(sources["optical_module"], "bundled_fallback")
            self.assertEqual(sources["connector"], "bundled_fallback")
            for asset in manifest["assets"]:
                self.assertEqual(asset["usage"], "motion_overlay_icon")
                self.assertTrue(Path(asset["local_path"]).exists())
            layer = read_json(project / "work" / "plan" / "motion_layers.json")["layers"][0]
            self.assertEqual(layer["renderer_backend"], "motion_canvas_sequence")

    def test_s5_motion_icon_written_to_broll_manifest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            write_asset_manifest(project, [{"asset_key": "motion_icon_chip", "usage": "motion_overlay_icon", "path": "fake.svg"}])
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("motion_icon_in_broll_asset_manifest", result.stdout)

    def test_s5_merges_short_adjacent_motion_beats_into_one_logic_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            script = "开场介绍一句。那以前怎么做。以前主要靠一种叫FAU的器件。最后总结观点。"
            prepare_s5_project(project, script=script)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            shots = read_json(project / "work" / "plan" / "shot_plan.json")["shots"]
            required_ids = [shot["shot_id"] for shot in shots if shot.get("motion_overlay_required")]
            payload = read_json(project / "work" / "plan" / "motion_layers.json")
            self.assertEqual(len(required_ids), 1)
            self.assertEqual(len(payload["layers"]), 1)
            layer = payload["layers"][0]
            self.assertIn(required_ids[0], layer["covered_shot_ids"])
            self.assertIn(shots[1]["shot_id"], layer["covered_shot_ids"])
            self.assertEqual(layer["semantic_action"], "before_after_change")
            self.assertLessEqual(layer["required_intervals"][0]["start"], shots[1]["start"])
            self.assertGreaterEqual(layer["required_intervals"][0]["end"], shots[2]["end"])

    def test_s5_missing_motion_canvas_source_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            payload = read_json(project / "work" / "plan" / "motion_layers.json")
            Path(payload["layers"][0]["motion_source_files"][0]).unlink()
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("motion_source_file_missing", result.stdout)

    def test_s5_ass_drawtext_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_motion_layers(project, lambda payload: payload["layers"][0].update({"layer_type": "drawtext"}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid_motion_layer_type", result.stdout)

    def test_s5_placeholder_entity_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_motion_layers(project, lambda payload: payload["layers"][0].update({"motion_text_items": ["placeholder_entity"]}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("placeholder_entity", result.stdout)

    def test_s5_motion_text_full_subtitle_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_motion_layers(project, lambda payload: payload["layers"][0].update({"motion_text_items": ["这是一整句很长很长的字幕内容"]}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("motion_text_is_full_sentence", result.stdout)

    def test_s5_not_x_but_y_missing_pivot_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)

            def remove_pivot(payload):
                payload["layers"][0].pop("pivot", None)

            mutate_motion_layers(project, remove_pivot)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_pivot", result.stdout)

    def test_s5_missing_start_mid_end_evidence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s5_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S5_motion_overlay", "--to-stage", "S5_motion_overlay"], check=True)
            mutate_motion_layers(project, lambda payload: payload["layers"][0].update({"frame_evidence": {}}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S5_motion_overlay"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_frame_evidence", result.stdout)

    def test_s6_subtitle_over_two_lines_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s6_project(project)
            mutate_json(project / "work" / "plan" / "subtitle_cues.json", lambda payload: payload["cues"][0].update({"display_lines": ["a", "b", "c"]}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S6_text_layout"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("subtitle_exceeds_two_lines", result.stdout)

    def test_s6_subtitle_deleted_word_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s6_project(project)
            mutate_json(project / "work" / "plan" / "subtitle_cues.json", lambda payload: payload["cues"][0].update({"display_lines": ["iPhone表现提升20%"]}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S6_text_layout"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("subtitle_display_lines_delete_or_rewrite_text", result.stdout)

    def test_s6_subtitle_rewrite_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s6_project(project)
            mutate_json(project / "work" / "plan" / "subtitle_cues.json", lambda payload: payload["cues"][0].update({"display_text": "完全改写"}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S6_text_layout"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("subtitle_display_text_rewrites_source", result.stdout)

    def test_s6_english_brand_split_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s6_project(project)
            mutate_json(project / "work" / "plan" / "subtitle_cues.json", lambda payload: payload["cues"][0].update({"display_lines": ["iPhone15", "Pro表现提升20%"]}))
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S6_text_layout"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("protected_term_split", result.stdout)

    def test_s6_font_size_out_of_range_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s6_project(project)

            def bad_font(payload):
                payload["subtitle_records"][0]["font_size_px"] = 72

            mutate_json(project / "work" / "plan" / "subtitle_layout_audit.json", bad_font)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S6_text_layout"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("subtitle_font_size_out_of_range", result.stdout)

    def test_s6_title_overflow_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s6_project(project)

            def overflow(payload):
                payload["title"]["bbox"]["x"] = -10

            mutate_json(project / "work" / "plan" / "title_layout_audit.json", overflow)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S6_text_layout"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("title_overflow", result.stdout)

    def test_s6_title_overlay_has_single_background_mask(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s6_project(project)
            audit = read_json(project / "work" / "plan" / "title_layout_audit.json")
            ass_text = (project / "output" / "title_overlay.ass").read_text(encoding="utf-8")
            self.assertEqual(audit["black_group_mask_count"], 1)
            self.assertIn("background_box", audit["title"])
            self.assertIn("Style: TitleMask", ass_text)
            self.assertIn("\\p1", ass_text)

    def test_s6_keyword_highlight_missing_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s6_project(project)

            def missing_highlight(payload):
                payload["subtitle_records"][0]["keyword_highlight_rendered"] = False

            mutate_json(project / "work" / "plan" / "subtitle_layout_audit.json", missing_highlight)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S6_text_layout"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("keyword_highlight_missing", result.stdout)

    def test_s6_semantic_keywords_are_highlighted_without_proper_nouns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s6_project(project, script="如果还是靠人工校准，不仅成本越来越高，生产效率也越来越低。最后总结观点。")
            audit = read_json(project / "work" / "plan" / "subtitle_layout_audit.json")
            ass_text = (project / "output" / "subtitles.ass").read_text(encoding="utf-8")
            keyword_items = [item for record in audit["subtitle_records"] for item in record["keyword_items"]]
            self.assertTrue(any("成本" in item for item in keyword_items))
            self.assertTrue(any("效率" in item for item in keyword_items))
            self.assertIn("\\c&H00E5FF&", ass_text)

    def test_s7_missing_probe_render_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s7_project(project)
            (project / "output" / "qc" / "probe_render.mp4").unlink()
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S7_process_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_probe_render", result.stdout)

    def test_s7_missing_representative_broll_frame_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s7_project(project)
            process = project / "work" / "plan" / "process_validation_report.json"

            def remove_broll(payload):
                Path(payload["representative_frames"]["broll"]).unlink()

            mutate_json(process, remove_broll)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S7_process_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_representative_broll_frame", result.stdout)

    def test_s7_missing_motion_frame_when_required_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s7_project(project)
            process = project / "work" / "plan" / "process_validation_report.json"

            def remove_motion(payload):
                Path(payload["representative_frames"]["motion"]).unlink()

            mutate_json(process, remove_motion)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S7_process_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_representative_motion_frame", result.stdout)

    def test_s7_previous_stage_non_pass_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s7_project(project)
            mutate_json(project / "work" / "plan" / "stage_reports" / "S6_text_layout.json", lambda payload: payload.update({"status": "FINAL_BLOCKED"}))
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S7_process_validation", "--to-stage", "S7_process_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("previous_production_slice_not_passed", result.stdout)

    def test_s7_timeline_coverage_gap_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s7_project(project)

            def gap(payload):
                payload["cues"][-1]["end"] = 1.0

            mutate_json(project / "work" / "plan" / "subtitle_cues.json", gap)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S7_process_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("subtitle_coverage_gap", result.stdout)

    def test_s8_final_missing_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)
            (project / "output" / "final.mp4").unlink()
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S8_final_render_and_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_final_mp4", result.stdout)

    def test_s8_container_duration_only_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)

            def container_only(payload):
                payload.pop("video_stream_duration", None)
                payload.pop("audio_stream_duration", None)
                payload["container_duration"] = 3.0

            mutate_json(project / "work" / "plan" / "final_video_metadata.json", container_only)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S8_final_render_and_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("final_metadata_container_duration_only", result.stdout)

    def test_s8_video_stream_shorter_than_audio_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)

            def shorten_video(payload):
                payload["final_video_stream_duration"] = 1.0
                payload["final_audio_stream_duration"] = 3.0

            mutate_json(project / "work" / "plan" / "final_render_log.json", shorten_video)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S8_final_render_and_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("final_video_stream_shorter_than_audio", result.stdout)

    def test_s8_last_frame_before_audio_end_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)

            def early_last_frame(payload):
                payload["final_audio_stream_duration"] = 3.0
                payload["last_video_frame_timestamp"] = 1.0

            mutate_json(project / "work" / "plan" / "final_render_log.json", early_last_frame)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S8_final_render_and_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("last_video_frame_before_audio_end", result.stdout)

    def test_s8_dangerous_shortest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)

            def dangerous_shortest(payload):
                payload["shortest_used"] = True
                payload["video_duration_before_mux"] = 1.0
                payload["audio_duration_before_mux"] = 3.0

            mutate_json(project / "work" / "plan" / "final_render_log.json", dangerous_shortest)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S8_final_render_and_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("dangerous_shortest_used", result.stdout)

    def test_s8_missing_required_motion_overlay_input_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)

            def remove_motion_inputs(payload):
                payload["motion_overlay_count"] = 0
                payload["overlay_inputs"] = []

            mutate_json(project / "work" / "plan" / "final_render_log.json", remove_motion_inputs)
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S8_final_render_and_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_final_motion_overlay_inputs", result.stdout)

    def test_s8_missing_final_title_frames_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)
            (project / "output" / "qc" / "final_title_frames" / "mid.png").unlink()
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S8_final_render_and_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing_final_title_frames_mid", result.stdout)

    def test_s8_edit_package_metadata_only_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)
            package = project / "output" / "edit_package"
            for path in list(package.rglob("*")):
                if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".webm", ".png"}:
                    path.unlink()
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S8_final_render_and_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("edit_package_missing_real_media_layers", result.stdout)

    def test_s8_non_pass_does_not_write_final_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s7_project(project)
            mutate_json(project / "work" / "plan" / "stage_reports" / "S7_process_validation.json", lambda payload: payload.update({"status": "FINAL_BLOCKED"}))
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S8_final_render_and_validation", "--to-stage", "S8_final_render_and_validation"])
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((project / "output" / "FINAL_REPORT.md").exists())
            acceptance = read_json(project / "work" / "plan" / "production_acceptance_report.json")
            self.assertNotEqual(acceptance["status"], "PASS")

    def test_production_rejects_handwritten_acceptance_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)
            acceptance = project / "work" / "plan" / "production_acceptance_report.json"
            acceptance.write_text(json.dumps({"status": "PASS", "generated_by": "codex", "can_claim_complete": True}), encoding="utf-8")
            result = run_cmd([str(CLI), "validate-production", "--project-dir", str(project)])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("report_not_engine_generated", result.stdout)

    def test_production_acceptance_passes_with_engine_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)
            result = run_cmd([str(CLI), "validate-production", "--project-dir", str(project)])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            acceptance = read_json(project / "work" / "plan" / "production_acceptance_report.json")
            self.assertEqual(acceptance["status"], "PASS")
            self.assertEqual(acceptance["generated_by"], "short_video_engine")
            self.assertIn("validator_version", acceptance)

    def test_production_rejects_handwritten_stage_report_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)
            report = project / "work" / "plan" / "stage_reports" / "S3_asset_sourcing.json"
            report.write_text(json.dumps({"status": "PASS", "generated_by": "codex", "stage": "S3_asset_sourcing"}), encoding="utf-8")
            result = run_cmd([str(CLI), "validate-production", "--project-dir", str(project)])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("report_not_engine_generated", result.stdout)

    def test_production_detects_final_mp4_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)
            with (project / "output" / "final.mp4").open("ab") as handle:
                handle.write(b"changed-after-probe")
            result = run_cmd([str(CLI), "validate-production", "--project-dir", str(project)])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("report_artifact_hash_mismatch", result.stdout)

    def test_production_report_missing_generated_by_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s8_project(project)

            def remove_generated_by(payload):
                payload.pop("generated_by", None)

            mutate_json(project / "work" / "plan" / "final_render_log.json", remove_generated_by)
            result = run_cmd([str(CLI), "validate-production", "--project-dir", str(project)])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("report_provenance_missing", result.stdout)

    def test_s1_proportional_timing_fails_strict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            init_project_with_media(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"], check=True)
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S1_script_and_subtitles", "--to-stage", "S1_script_and_subtitles", "--strict"])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "stage_reports" / "S1_script_and_subtitles.json")
            self.assertEqual(report["status"], "DRAFT_ONLY")
            self.assertIn("subtitle_timing_draft_only", report["failure_codes"])

    def test_asr_payload_aligns_segments_to_script_units(self) -> None:
        from short_video_engine.producers.asr_timing import build_asr_timing_payload
        from short_video_engine.stages.s1_script_and_subtitles import segment_script

        units = segment_script("第一句话。第二句话。")
        segments = [{"text": "第一句话第二句话", "start": 0.1, "end": 1.9, "words": []}]
        payload, failures = build_asr_timing_payload(units, segments, 2.0, {"provider": "fixture_asr", "model": "fixture"})
        self.assertEqual(failures, [])
        self.assertEqual(payload["alignment_method"], "asr_word_timestamps")
        self.assertEqual(payload["provenance"]["provider"], "fixture_asr")
        self.assertEqual(len(payload["cues"]), 2)
        self.assertEqual(payload["cues"][0]["source_text"], "第一句话。")
        self.assertGreater(payload["cues"][1]["start"], payload["cues"][0]["start"])
        self.assertAlmostEqual(payload["cues"][-1]["end"], 2.0, places=3)

    def test_s1_manual_timestamps_need_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            init_project_with_media(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"], check=True)
            write_manual_timestamps(project, ["第一句话。", "第二句话。"], provenance=False)
            result = run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S1_script_and_subtitles", "--to-stage", "S1_script_and_subtitles", "--strict"])
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "work" / "plan" / "stage_reports" / "S1_script_and_subtitles.json")
            self.assertIn("timing_provenance_missing", report["failure_codes"])

    def test_s1_detects_deleted_script_sentence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            init_project_with_media(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"], check=True)
            write_manual_timestamps(project, ["第一句话。", "第二句话。"])
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S1_script_and_subtitles", "--to-stage", "S1_script_and_subtitles", "--strict"], check=True)
            cues_path = project / "work" / "plan" / "subtitle_cues.json"
            payload = read_json(cues_path)
            payload["cues"] = payload["cues"][:1]
            cues_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S1_script_and_subtitles"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("subtitle_cues_do_not_cover_source_script", result.stdout)

    def test_s1_detects_rewritten_subtitle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            init_project_with_media(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"], check=True)
            write_manual_timestamps(project, ["第一句话。", "第二句话。"])
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S1_script_and_subtitles", "--to-stage", "S1_script_and_subtitles", "--strict"], check=True)
            cues_path = project / "work" / "plan" / "subtitle_cues.json"
            payload = read_json(cues_path)
            payload["cues"][0]["display_text"] = "改写字幕"
            cues_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S1_script_and_subtitles"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("display_text_rewrites_source", result.stdout)

    def test_s1_detects_english_brand_model_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            init_project_with_media(project, script="iPhone 15 Pro Max很好。", duration=2.0)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"], check=True)
            write_manual_timestamps(project, ["iPhone 15 Pro Max很好。"], duration=2.0)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S1_script_and_subtitles", "--to-stage", "S1_script_and_subtitles", "--strict"], check=True)
            cues_path = project / "work" / "plan" / "subtitle_cues.json"
            payload = read_json(cues_path)
            cue = payload["cues"][0]
            payload["cues"] = [
                {**cue, "cue_id": "c001", "source_text": "iPhone 15 Pro", "text": "iPhone 15 Pro", "display_text": "iPhone15Pro", "end": 1.0},
                {**cue, "cue_id": "c002", "source_text": "Max很好。", "text": "Max很好。", "display_text": "Max很好", "start": 1.0, "end": 2.0},
            ]
            cues_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S1_script_and_subtitles"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("english_brand_or_model_token_split", result.stdout)

    def test_s2_final_summary_is_corrected_to_talking_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s2_project(project)
            units = read_json(project / "work" / "plan" / "script_units.json")["units"]
            draft = {
                "shots": [
                    {"unit_id": units[-1]["unit_id"], "visual_mode": "broll_fullscreen", "talking_head_required": False}
                ]
            }
            (project / "work" / "plan" / "draft_visual_plan.json").write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S2_visual_plan", "--to-stage", "S2_visual_plan"], check=True)
            shot_plan = read_json(project / "work" / "plan" / "shot_plan.json")
            final_shot = [shot for shot in shot_plan["shots"] if shot["unit_id"] == units[-1]["unit_id"]][0]
            self.assertEqual(final_shot["visual_mode"], "talking_head_fullscreen")
            self.assertTrue(final_shot["talking_head_required"])

    def test_s2_generated_card_base_visual_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s2_project(project)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S2_visual_plan", "--to-stage", "S2_visual_plan"], check=True)
            shot_plan_path = project / "work" / "plan" / "shot_plan.json"
            payload = read_json(shot_plan_path)
            payload["shots"][0]["visual_mode"] = "generated_card"
            payload["shots"][0]["visual_role"] = "generated_card"
            shot_plan_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S2_visual_plan"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("forbidden_base_visual", result.stdout)

    def test_s2_every_script_unit_has_visual_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s2_project(project, script="第一句普通解释。第二句讲流程步骤。最后总结观点。", duration=3.0)
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S2_visual_plan", "--to-stage", "S2_visual_plan"], check=True)
            shot_plan = read_json(project / "work" / "plan" / "shot_plan.json")
            units = read_json(project / "work" / "plan" / "script_units.json")["units"]
            covered = {shot["unit_id"] for shot in shot_plan["shots"] if shot.get("visual_role")}
            self.assertEqual(covered, {unit["unit_id"] for unit in units})

    def test_s2_invalid_motion_relation_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            prepare_s2_project(project, script="这里有流程步骤需要解释。最后总结观点。")
            run_cmd([str(CLI), "run", "--project-dir", str(project), "--from-stage", "S2_visual_plan", "--to-stage", "S2_visual_plan"], check=True)
            shot_plan_path = project / "work" / "plan" / "shot_plan.json"
            payload = read_json(shot_plan_path)
            payload["shots"][0]["motion_overlay_required"] = True
            payload["shots"][0]["logic_relation"] = "random_relation"
            shot_plan_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run_cmd([str(CLI), "validate-stage", "--project-dir", str(project), "--stage", "S2_visual_plan"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid_motion_relation", result.stdout)

    def test_old_wrappers_still_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            init_wrapper = SKILL_ROOT / "scripts" / "init_short_video_project.py"
            run_wrapper = SKILL_ROOT / "scripts" / "run_pipeline.py"
            validate_wrapper = SKILL_ROOT / "scripts" / "validate_stage.py"
            run_cmd([str(init_wrapper), str(project)], check=True)
            self.assertTrue((project / "work" / "plan").is_dir())
            result = run_cmd([str(run_wrapper), "--project-dir", str(project), "--from-stage", "S0_intake", "--to-stage", "S0_intake"])
            self.assertNotEqual(result.returncode, 0)
            result = run_cmd([str(validate_wrapper), "--project-dir", str(project), "--stage", "S0_intake"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("generated_by", result.stdout)


if __name__ == "__main__":
    unittest.main()
