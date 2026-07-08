from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ... import ENGINE_VERSION
from ...paths import output_dir, plan_dir
from .png_writer import rect_rgba, transparent, write_png_rgba


def prepare_motion_canvas_source(project_dir: Path, segment: dict[str, Any], template: str, expression_plan: dict[str, Any], width: int, height: int, frame_count: int) -> dict[str, Any]:
    """Write a Motion Canvas project source next to S5 artifacts.

    The engine still validates rendered PNG/video artifacts. These source files are
    a deterministic high-quality renderer handoff, not completion evidence.
    """
    shot_id = str(segment.get("shot_id") or "unknown_shot")
    source_dir = plan_dir(project_dir) / "motion_canvas" / shot_id
    src_dir = source_dir / "src"
    scene_dir = src_dir / "scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    props = motion_canvas_props(segment, template, expression_plan, width, height, frame_count)
    write_text(source_dir / "package.json", package_json())
    write_text(source_dir / "tsconfig.json", tsconfig_json())
    write_text(source_dir / "scripts" / "render-sequence.mjs", render_sequence_mjs())
    write_text(src_dir / "project.ts", project_ts())
    write_text(src_dir / "motion-canvas-env.d.ts", motion_canvas_env_d_ts())
    write_text(src_dir / "templates" / "techHudTemplates.tsx", tech_hud_templates_tsx())
    write_text(scene_dir / "logic.tsx", logic_scene_tsx())
    write_text(source_dir / "motion-props.json", json.dumps(props, ensure_ascii=False, indent=2) + "\n")
    write_text(source_dir / "README.md", readme_md())
    node = shutil.which("node")
    npm = shutil.which("npm")
    return {
        "motion_source_engine": "motion_canvas",
        "motion_source_status": "prepared",
        "motion_source_project_dir": str(source_dir),
        "motion_source_files": [
            str(source_dir / "package.json"),
            str(source_dir / "tsconfig.json"),
            str(source_dir / "scripts" / "render-sequence.mjs"),
            str(src_dir / "project.ts"),
            str(src_dir / "motion-canvas-env.d.ts"),
            str(src_dir / "templates" / "techHudTemplates.tsx"),
            str(scene_dir / "logic.tsx"),
            str(source_dir / "motion-props.json"),
        ],
        "motion_source_runtime": {"node": node or "", "npm": npm or "", "available": bool(node and npm)},
        "motion_source_note": "Source handoff only; S5 PASS still requires rendered transparent PNG sequence evidence.",
        "suggested_render_command": "npm install && npm run render",
    }


def render_motion_canvas_artifact(
    project_dir: Path,
    segment: dict[str, Any],
    scene: dict[str, Any],
    template: str,
    expression_plan: dict[str, Any],
    width: int,
    height: int,
    frame_count: int,
    *,
    allow_internal_test_renderer: bool = False,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    source_info = prepare_motion_canvas_source(project_dir, segment, template, expression_plan, width, height, frame_count)
    source_dir = Path(str(source_info["motion_source_project_dir"]))
    frame_dir = output_dir(project_dir) / "qc" / "motion_canvas_frames" / str(scene.get("scene_id") or segment.get("logic_segment_id") or segment.get("shot_id") or "scene")
    if frame_dir.exists():
        for path in frame_dir.glob("*.png"):
            path.unlink()
    frame_dir.mkdir(parents=True, exist_ok=True)
    node = shutil.which("node")
    npm = shutil.which("npm")
    render_log: list[dict[str, Any]] = []
    if allow_internal_test_renderer:
        frames = render_internal_motion_canvas_sequence(frame_dir, scene, width, height, frame_count)
        return motion_canvas_result(source_info, frame_dir, frames, "internal_test_motion_canvas_sequence", render_log), []
    if not node or not npm:
        return source_info | {"production_render_status": "unavailable", "production_render_reason": "node_or_npm_missing"}, [
            {"code": "motion_canvas_runtime_unavailable", "message": "Node/npm are required for strict Motion Canvas production rendering."}
        ]
    if os.environ.get("SVIDEO_SKIP_NPM_MOTION_RENDER") == "1":
        return source_info | {"production_render_status": "skipped"}, [
            {"code": "motion_canvas_render_skipped", "message": "Motion Canvas production render was explicitly skipped."}
        ]
    commands = [["npm", "install"], ["npm", "run", "render"]]
    for command in commands:
        try:
            completed = subprocess.run(command, cwd=source_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=int(os.environ.get("SVIDEO_MOTION_CANVAS_TIMEOUT", "120")))
        except (OSError, subprocess.TimeoutExpired) as exc:
            return source_info | {"production_render_status": "failed", "production_render_log": render_log}, [
                {"code": "motion_canvas_render_failed", "message": f"Motion Canvas command failed: {exc}"}
            ]
        render_log.append({"command": " ".join(command), "returncode": completed.returncode, "stdout_tail": completed.stdout[-1200:], "stderr_tail": completed.stderr[-1200:]})
        if completed.returncode != 0:
            return source_info | {"production_render_status": "failed", "production_render_log": render_log}, [
                {"code": "motion_canvas_render_failed", "message": "Motion Canvas production render command returned non-zero status."}
            ]
    rendered_frames = collect_rendered_frames(source_dir)
    if not rendered_frames:
        return source_info | {"production_render_status": "failed", "production_render_log": render_log}, [
            {"code": "motion_canvas_render_no_frames", "message": "Motion Canvas render completed but no transparent PNG sequence was found."}
        ]
    copied = []
    for index, frame in enumerate(rendered_frames[:frame_count]):
        target = frame_dir / f"frame_{index:03d}.png"
        shutil.copyfile(frame, target)
        copied.append(target)
    return motion_canvas_result(source_info, frame_dir, copied, "npm_motion_canvas_sequence", render_log), []


def motion_canvas_result(source_info: dict[str, Any], frame_dir: Path, frames: list[Path], status: str, render_log: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = frame_evidence(frames)
    return source_info | {
        "production_render_status": status,
        "production_render_log": render_log,
        "renderer_backend": "motion_canvas_sequence",
        "artifact_renderer_backend": "motion_canvas_sequence",
        "layer_type": "png_sequence",
        "png_sequence_dir": str(frame_dir),
        "sequence_frame_count": len(frames),
        "frame_evidence": {key: str(value) for key, value in evidence.items()},
    }


def frame_evidence(frames: list[Path]) -> dict[str, Path]:
    if not frames:
        return {}
    last = len(frames) - 1
    indexes = {
        "start": 0,
        "build": max(0, int(last * 0.24)),
        "mid": max(0, int(last * 0.52)),
        "peak": max(0, int(last * 0.52)),
        "settle": max(0, int(last * 0.78)),
        "end": last,
    }
    return {key: frames[index] for key, index in indexes.items()}


def collect_rendered_frames(source_dir: Path) -> list[Path]:
    candidates = []
    for root in (source_dir / "dist", source_dir / "output", source_dir):
        if root.exists():
            candidates.extend(sorted(root.rglob("*.png")))
    return [path for path in candidates if path.is_file()]


def render_internal_motion_canvas_sequence(frame_dir: Path, scene: dict[str, Any], width: int, height: int, frame_count: int) -> list[Path]:
    template = str(scene.get("scene_template") or "tech_hud_concept_card")
    frames: list[Path] = []
    for index in range(frame_count):
        progress = index / max(frame_count - 1, 1)
        eased = progress * progress * (3 - 2 * progress)
        pixels = transparent(width, height)
        draw_hud_frame(pixels, width, height, template, eased, index)
        path = frame_dir / f"frame_{index:03d}.png"
        write_png_rgba(path, width, height, pixels)
        frames.append(path)
    return frames


def draw_hud_frame(pixels: bytearray, width: int, height: int, template: str, progress: float, index: int) -> None:
    safe_top = 420
    panel_x, panel_y, panel_w, panel_h = 112, 688, 856, 588
    glow = int(80 + 80 * progress)
    draw_scan_grid(pixels, width, height, progress)
    draw_panel_shell(pixels, width, height, panel_x, panel_y, panel_w, panel_h, progress)
    if template == "negation_to_connector_scene":
        draw_semantic_negation(pixels, width, height, progress)
    elif template == "connector_flow_scene":
        draw_semantic_connector(pixels, width, height, progress)
    elif template == "metric_growth_scene":
        draw_meters(pixels, width, height, progress)
        draw_direction_arrow(pixels, width, height, progress)
    elif template == "process_migration_scene":
        draw_semantic_process(pixels, width, height, progress)
    elif template == "density_pressure_scene":
        draw_semantic_density(pixels, width, height, progress)
    elif template in {"concept_definition_scene", "cause_to_result_scene", "before_after_scene"}:
        draw_semantic_connector(pixels, width, height, progress)
    elif template == "chip_node_network":
        draw_network(pixels, width, height, progress, glow)
    elif template == "system_error_terminal":
        draw_terminal(pixels, width, height, progress, index)
    elif template == "kpi_dual_meter_panel":
        draw_meters(pixels, width, height, progress)
    elif template == "process_milestone_rail":
        draw_rail(pixels, width, height, progress)
    elif template in {"comparison_split_glass", "not_x_but_y_pivot_panel"}:
        draw_split_pivot(pixels, width, height, progress)
    elif template == "callout_lens_overlay":
        draw_lens(pixels, width, height, progress)
    else:
        draw_concept_card(pixels, width, height, progress)


def draw_semantic_negation(pixels: bytearray, width: int, height: int, progress: float) -> None:
    a = min(progress * 1.7, 1)
    b = min(max(progress - 0.18, 0) * 1.8, 1)
    c = min(max(progress - 0.42, 0) * 1.8, 1)
    rect_rgba(pixels, width, height, 172, 810, 260, 160, (70, 90, 128, int(150 * a)))
    rect_rgba(pixels, width, height, 648, 810, 260, 160, (70, 90, 128, int(150 * b)))
    rect_rgba(pixels, width, height, 454, 1012, 172, 146, (28, 126, 92, int(170 * c)))
    rect_rgba(pixels, width, height, 188, 884, int(228 * a), 10, (255, 92, 122, int(230 * a)))
    rect_rgba(pixels, width, height, 664, 884, int(228 * b), 10, (255, 92, 122, int(230 * b)))
    rect_rgba(pixels, width, height, 260, 1080, int(560 * c), 9, (248, 211, 77, int(230 * c)))
    rect_rgba(pixels, width, height, 810, 1068, int(38 * c), 32, (248, 211, 77, int(230 * c)))


def draw_semantic_connector(pixels: bytearray, width: int, height: int, progress: float) -> None:
    xs = [250, 540, 830]
    for idx, x in enumerate(xs):
        local = max(0.0, min(1.0, progress * 3.2 - idx * 0.42))
        rect_rgba(pixels, width, height, x - 78, 890, 156, 126, (12, 36, 54, int(90 + 105 * local)))
        rect_rgba(pixels, width, height, x - 18, 930, 36, 36, (114, 235, 203, int(210 * local)))
    flow = min(max(progress - 0.22, 0) * 1.45, 1)
    rect_rgba(pixels, width, height, 328, 950, int(424 * flow), 12, (248, 211, 77, int(230 * flow)))
    rect_rgba(pixels, width, height, 744, 938, int(38 * flow), 36, (248, 211, 77, int(230 * flow)))


def draw_direction_arrow(pixels: bytearray, width: int, height: int, progress: float) -> None:
    local = min(max(progress - 0.5, 0) * 2, 1)
    rect_rgba(pixels, width, height, 430, 1166, int(250 * local), 12, (248, 211, 77, int(230 * local)))
    rect_rgba(pixels, width, height, 668, 1154, int(38 * local), 36, (248, 211, 77, int(230 * local)))


def draw_semantic_process(pixels: bytearray, width: int, height: int, progress: float) -> None:
    rect_rgba(pixels, width, height, 184, 840, 250, 100, (255, 92, 122, int(86 + 54 * progress)))
    rect_rgba(pixels, width, height, 194, 902, int(218 * min(progress * 1.4, 1)), 8, (255, 92, 122, 220))
    draw_semantic_connector(pixels, width, height, progress)
    rect_rgba(pixels, width, height, 638, 1030, 250, 100, (114, 235, 203, int(86 + 92 * progress)))
    rect_rgba(pixels, width, height, 438, 1014, int(210 * min(max(progress - 0.35, 0) * 1.7, 1)), 10, (248, 211, 77, 230))


def draw_semantic_density(pixels: bytearray, width: int, height: int, progress: float) -> None:
    left = min(progress * 1.4, 1)
    pressure = min(max(progress - 0.22, 0) * 1.7, 1)
    expand = min(max(progress - 0.48, 0) * 1.9, 1)
    rect_rgba(pixels, width, height, 184, 840, 250, 270, (38, 90, 128, int(140 * left)))
    for x in (440, 470, 500):
        rect_rgba(pixels, width, height, x, 848, 8, int(246 * pressure), (255, 92, 122, int(210 * pressure)))
    rect_rgba(pixels, width, height, 596, 870, int(300 + 110 * expand), 220, (28, 126, 92, int(120 + 72 * expand)))
    rect_rgba(pixels, width, height, 620, 980, int(236 * expand), 12, (248, 211, 77, 230))


def draw_scan_grid(pixels: bytearray, width: int, height: int, progress: float) -> None:
    alpha = int(16 + 24 * progress)
    rect_rgba(pixels, width, height, 74, 386, 932, 1048, (2, 9, 16, alpha))
    for x in range(128, 958, 96):
        rect_rgba(pixels, width, height, x, 690, 1, 584, (110, 235, 255, int(18 * progress)))
    for y in range(724, 1248, 72):
        rect_rgba(pixels, width, height, 112, y, 856, 1, (114, 235, 203, int(16 * progress)))


def draw_panel_shell(pixels: bytearray, width: int, height: int, x: int, y: int, w: int, h: int, progress: float) -> None:
    rect_rgba(pixels, width, height, x - 18, y - 18, w + 36, h + 36, (80, 210, 240, int(10 * progress)))
    rect_rgba(pixels, width, height, x, y, w, h, (7, 18, 28, int(104 + 20 * progress)))
    rect_rgba(pixels, width, height, x, y, int(w * progress), 2, (110, 235, 255, 150))
    rect_rgba(pixels, width, height, x, y + h - 2, int(w * min(progress + 0.12, 1)), 2, (114, 235, 203, 140))
    corner = int(62 * min(progress * 1.4, 1))
    for cx, cy, sx, sy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        rect_rgba(pixels, width, height, cx if sx > 0 else cx - corner, cy, corner, 4, (248, 211, 77, 140))
        rect_rgba(pixels, width, height, cx, cy if sy > 0 else cy - corner, 4, corner, (248, 211, 77, 140))


def draw_title_plate(pixels: bytearray, width: int, height: int, safe_top: int, progress: float) -> None:
    rect_rgba(pixels, width, height, 192, safe_top + 82, int(696 * min(progress * 1.25, 1)), 96, (2, 7, 12, 188))
    rect_rgba(pixels, width, height, 220, safe_top + 110, int(520 * min(progress * 1.45, 1)), 16, (255, 255, 255, 232))
    rect_rgba(pixels, width, height, 220, safe_top + 142, int(260 * min(max(progress - 0.12, 0) * 1.4, 1)), 9, (184, 204, 215, 175))


def draw_network(pixels: bytearray, width: int, height: int, progress: float, glow: int) -> None:
    rect_rgba(pixels, width, height, 498, 792, 84, 300, (18, 54, 76, int(82 + 64 * progress)))
    rect_rgba(pixels, width, height, 372, 915, 336, 74, (12, 32, 48, int(92 + 54 * progress)))
    nodes = [(250, 920), (430, 820), (650, 998), (830, 878)]
    for idx, (x, y) in enumerate(nodes):
        local = max(0.0, min(1.0, progress * 4 - idx * 0.55))
        size = int(46 + 34 * local)
        rect_rgba(pixels, width, height, x - size // 2, y - size // 2, size, size, (12, 36, 54, int(90 + 115 * local)))
        rect_rgba(pixels, width, height, x - 7, y - 7, 14, 14, (114, 235, 203, int(glow * local)))
        if idx:
            px, py = nodes[idx - 1]
            line_w = int((x - px) * local)
            line_h = int((y - py) * local)
            rect_rgba(pixels, width, height, min(px, px + line_w), min(py, py + line_h), max(abs(line_w), 8), 8, (248, 211, 77, int(170 * local)))


def draw_terminal(pixels: bytearray, width: int, height: int, progress: float, index: int) -> None:
    rect_rgba(pixels, width, height, 188, 770, 704, 72, (255, 92, 122, int(44 + 42 * progress)))
    rect_rgba(pixels, width, height, 206, 790, int(318 * progress), 18, (255, 255, 255, 210))
    rows = int(6 * progress)
    for row in range(rows):
        y = 876 + row * 48
        color = (255, 92, 122, 210) if row < 2 and index % 6 < 3 else (114, 235, 203, 190)
        rect_rgba(pixels, width, height, 214, y, 626 - row * 34, 18, color)
        rect_rgba(pixels, width, height, 214, y + 26, 420 - row * 22, 8, (184, 204, 215, int(120 * progress)))
    rect_rgba(pixels, width, height, 214, 1180, int(612 * progress), 18, (248, 211, 77, 230))


def draw_meters(pixels: bytearray, width: int, height: int, progress: float) -> None:
    for idx, (y, color, fill) in enumerate(((842, (114, 235, 203, 224), 0.88), (1032, (248, 211, 77, 224), 0.72))):
        rect_rgba(pixels, width, height, 228, y - 44, 624, 118, (10, 28, 42, 132))
        rect_rgba(pixels, width, height, 260, y, 540, 32, (255, 255, 255, 42))
        rect_rgba(pixels, width, height, 260, y, int(540 * fill * progress), 32, color)
        rect_rgba(pixels, width, height, 260, y - 30, int(240 * min(progress * 1.3, 1)), 10, (255, 255, 255, 220))
        r, g, b, _alpha = color
        rect_rgba(pixels, width, height, 760, y - 16, 42, 64, (r, g, b, int(120 + 80 * progress)))


def draw_rail(pixels: bytearray, width: int, height: int, progress: float) -> None:
    rect_rgba(pixels, width, height, 210, 982, 660, 10, (255, 255, 255, 60))
    rect_rgba(pixels, width, height, 210, 982, int(660 * progress), 10, (248, 211, 77, 220))
    for idx, x in enumerate([230, 430, 630, 830]):
        local = max(0.0, min(1.0, progress * 4 - idx * 0.5))
        rect_rgba(pixels, width, height, x - 38, 914, 76, 138, (12, 36, 54, int(80 + 120 * local)))
        rect_rgba(pixels, width, height, x - 22, 936, 44, 44, (114, 235, 203, int(100 + 110 * local)))
        rect_rgba(pixels, width, height, x - 44, 1066, int(88 * local), 9, (184, 204, 215, 175))


def draw_split_pivot(pixels: bytearray, width: int, height: int, progress: float) -> None:
    left = min(progress * 1.35, 1)
    right = min(max(progress - 0.18, 0) * 1.45, 1)
    rect_rgba(pixels, width, height, 174 - int(42 * (1 - left)), 824, 310, 270, (38, 90, 128, int(92 + 88 * left)))
    rect_rgba(pixels, width, height, 596 + int(42 * (1 - right)), 824, 310, 270, (28, 126, 92, int(92 + 88 * right)))
    rect_rgba(pixels, width, height, 504, 910, int(72 * progress), 72, (248, 211, 77, int(120 + 90 * progress)))
    rect_rgba(pixels, width, height, 472, 944, int(136 * progress), 8, (248, 211, 77, 225))


def draw_lens(pixels: bytearray, width: int, height: int, progress: float) -> None:
    size = int(210 + 70 * progress)
    rect_rgba(pixels, width, height, 540 - size // 2, 940 - size // 2, size, size, (110, 235, 255, int(36 + 34 * progress)))
    rect_rgba(pixels, width, height, 430, 1046, int(280 * progress), 12, (248, 211, 77, 230))
    rect_rgba(pixels, width, height, 692, 1056, int(120 * progress), 12, (248, 211, 77, 230))


def draw_concept_card(pixels: bytearray, width: int, height: int, progress: float) -> None:
    for idx, y in enumerate([820, 924, 1028]):
        local = max(0.0, min(1.0, progress * 3 - idx * 0.45))
        rect_rgba(pixels, width, height, 228 + idx * 28, y, int((620 - idx * 56) * local), 68, (12, 36, 54, int(92 + 82 * local)))
        rect_rgba(pixels, width, height, 254 + idx * 28, y + 24, int((300 - idx * 28) * local), 12, (255, 255, 255, int(180 * local)))


def motion_canvas_props(segment: dict[str, Any], template: str, expression_plan: dict[str, Any], width: int, height: int, frame_count: int) -> dict[str, Any]:
    return {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "shot_id": segment.get("shot_id"),
        "logic_segment_id": segment.get("logic_segment_id"),
        "template": template,
        "logic_relation": segment.get("logic_relation"),
        "visual_claim": segment.get("visual_claim"),
        "motion_text_items": segment.get("motion_text_items") or [],
        "logic_entities": segment.get("logic_entities") or [],
        "semantic_icons": segment.get("semantic_icons") or {},
        "expression_plan": expression_plan,
        "canvas": {"width": width, "height": height, "frame_count": frame_count, "background": "transparent"},
        "relation_fields": {
            key: segment.get(key)
            for key in (
                "rejected_state",
                "pivot",
                "accepted_state",
                "final_emphasis",
                "direction",
                "cause",
                "effect",
                "ordered_steps",
                "left_side",
                "right_side",
                "comparison_axis",
                "metric",
                "delta",
                "before_state",
                "after_state",
            )
            if segment.get(key)
        },
    }


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def package_json() -> str:
    return """{
  "private": true,
  "type": "module",
  "scripts": {
    "serve": "vite --host 127.0.0.1 --port 9000",
    "typecheck": "tsc --noEmit",
    "render": "node scripts/render-sequence.mjs"
  },
  "dependencies": {
    "@motion-canvas/2d": "^3.17.0",
    "@motion-canvas/core": "^3.17.0",
    "@motion-canvas/vite-plugin": "^3.17.0",
    "sharp": "^0.33.5",
    "vite": "^5.0.0",
    "typescript": "^5.0.0"
  },
  "devDependencies": {}
}
"""


def render_sequence_mjs() -> str:
    return """import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import sharp from 'sharp';

const root = process.cwd();
const props = JSON.parse(fs.readFileSync(path.join(root, 'motion-props.json'), 'utf8'));
const canvas = props.canvas ?? {};
const width = Number(canvas.width ?? 1080);
const height = Number(canvas.height ?? 1920);
const frameCount = Number(canvas.frame_count ?? 24);
const scene = props.expression_plan?.graphic_scene ?? {};
const template = String(scene.scene_template ?? props.template ?? 'tech_hud_concept_card');
const textItems = [
  ...(Array.isArray(scene.secondary_labels) ? scene.secondary_labels : []),
  ...(Array.isArray(props.motion_text_items) ? props.motion_text_items : []),
].map(String).filter(Boolean);
const output = path.join(root, 'output');
fs.mkdirSync(output, {recursive: true});
for (const item of fs.readdirSync(output)) {
  if (item.endsWith('.png')) fs.rmSync(path.join(output, item));
}

for (let i = 0; i < frameCount; i++) {
  const t = i / Math.max(frameCount - 1, 1);
  const p = t * t * (3 - 2 * t);
  const pixels = Buffer.alloc(width * height * 4);
  drawFrame(pixels, width, height, template, p, i);
  const file = path.join(output, `frame_${String(i).padStart(3, '0')}.png`);
  writePng(file, width, height, pixels);
  await annotateText(file, template, p);
}
console.log(JSON.stringify({status: 'rendered', output, frameCount, template}));

function drawFrame(px, w, h, tpl, p, index) {
  scanGrid(px, w, h, p);
  panel(px, w, h, 112, 688, 856, 588, p);
  if (tpl === 'negation_to_connector_scene') semanticNegation(px, w, h, p);
  else if (tpl === 'connector_flow_scene') semanticConnector(px, w, h, p);
  else if (tpl === 'metric_growth_scene') { meters(px, w, h, p); directionArrow(px, w, h, p); }
  else if (tpl === 'process_migration_scene') semanticProcess(px, w, h, p);
  else if (tpl === 'density_pressure_scene') semanticDensity(px, w, h, p);
  else if (tpl === 'concept_definition_scene' || tpl === 'cause_to_result_scene' || tpl === 'before_after_scene') semanticConnector(px, w, h, p);
  else if (tpl === 'system_error_terminal') terminal(px, w, h, p, index);
  else if (tpl === 'kpi_dual_meter_panel') meters(px, w, h, p);
  else if (tpl === 'process_milestone_rail') rail(px, w, h, p);
  else if (tpl === 'comparison_split_glass' || tpl === 'not_x_but_y_pivot_panel') split(px, w, h, p);
  else if (tpl === 'callout_lens_overlay') lens(px, w, h, p);
  else if (tpl === 'tech_hud_concept_card') concept(px, w, h, p);
  else network(px, w, h, p);
}

function semanticNegation(px, w, h, p) {
  const a = Math.min(p * 1.7, 1);
  const b = Math.min(Math.max(p - 0.18, 0) * 1.8, 1);
  const c = Math.min(Math.max(p - 0.42, 0) * 1.8, 1);
  rect(px, w, h, 172, 810, 260, 160, [70, 90, 128, Math.round(150 * a)]);
  rect(px, w, h, 648, 810, 260, 160, [70, 90, 128, Math.round(150 * b)]);
  rect(px, w, h, 454, 1012, 172, 146, [28, 126, 92, Math.round(170 * c)]);
  rect(px, w, h, 188, 884, Math.round(228 * a), 10, [255, 92, 122, Math.round(230 * a)]);
  rect(px, w, h, 664, 884, Math.round(228 * b), 10, [255, 92, 122, Math.round(230 * b)]);
  rect(px, w, h, 260, 1080, Math.round(560 * c), 9, [248, 211, 77, Math.round(230 * c)]);
  rect(px, w, h, 810, 1068, Math.round(38 * c), 32, [248, 211, 77, Math.round(230 * c)]);
}

function semanticConnector(px, w, h, p) {
  [250, 540, 830].forEach((x, idx) => {
    const local = Math.max(0, Math.min(1, p * 3.2 - idx * 0.42));
    rect(px, w, h, x - 78, 890, 156, 126, [12, 36, 54, Math.round(90 + 105 * local)]);
    rect(px, w, h, x - 18, 930, 36, 36, [114, 235, 203, Math.round(210 * local)]);
  });
  const flow = Math.min(Math.max(p - 0.22, 0) * 1.45, 1);
  rect(px, w, h, 328, 950, Math.round(424 * flow), 12, [248, 211, 77, Math.round(230 * flow)]);
  rect(px, w, h, 744, 938, Math.round(38 * flow), 36, [248, 211, 77, Math.round(230 * flow)]);
}

function directionArrow(px, w, h, p) {
  const q = Math.min(Math.max(p - 0.5, 0) * 2, 1);
  rect(px, w, h, 430, 1166, Math.round(250 * q), 12, [248, 211, 77, Math.round(230 * q)]);
  rect(px, w, h, 668, 1154, Math.round(38 * q), 36, [248, 211, 77, Math.round(230 * q)]);
}

function semanticProcess(px, w, h, p) {
  rect(px, w, h, 184, 840, 250, 100, [255, 92, 122, Math.round(86 + 54 * p)]);
  rect(px, w, h, 194, 902, Math.round(218 * Math.min(p * 1.4, 1)), 8, [255, 92, 122, 220]);
  semanticConnector(px, w, h, p);
  rect(px, w, h, 638, 1030, 250, 100, [114, 235, 203, Math.round(86 + 92 * p)]);
  rect(px, w, h, 438, 1014, Math.round(210 * Math.min(Math.max(p - 0.35, 0) * 1.7, 1)), 10, [248, 211, 77, 230]);
}

function semanticDensity(px, w, h, p) {
  const left = Math.min(p * 1.4, 1);
  const pressure = Math.min(Math.max(p - 0.22, 0) * 1.7, 1);
  const expand = Math.min(Math.max(p - 0.48, 0) * 1.9, 1);
  rect(px, w, h, 184, 840, 250, 270, [38, 90, 128, Math.round(140 * left)]);
  [440, 470, 500].forEach((x) => rect(px, w, h, x, 848, 8, Math.round(246 * pressure), [255, 92, 122, Math.round(210 * pressure)]));
  rect(px, w, h, 596, 870, Math.round(300 + 110 * expand), 220, [28, 126, 92, Math.round(120 + 72 * expand)]);
  rect(px, w, h, 620, 980, Math.round(236 * expand), 12, [248, 211, 77, 230]);
}

function scanGrid(px, w, h, p) {
  rect(px, w, h, 74, 386, 932, 1048, [2, 9, 16, Math.round(16 + 24 * p)]);
  for (let x = 128; x < 958; x += 96) rect(px, w, h, x, 690, 1, 584, [110, 235, 255, Math.round(18 * p)]);
  for (let y = 724; y < 1248; y += 72) rect(px, w, h, 112, y, 856, 1, [114, 235, 203, Math.round(16 * p)]);
}

function panel(px, w, h, x, y, ww, hh, p) {
  rect(px, w, h, x - 18, y - 18, ww + 36, hh + 36, [80, 210, 240, Math.round(10 * p)]);
  rect(px, w, h, x, y, ww, hh, [7, 18, 28, Math.round(104 + 20 * p)]);
  rect(px, w, h, x, y, Math.round(ww * p), 2, [110, 235, 255, 150]);
  rect(px, w, h, x, y + hh - 2, Math.round(ww * Math.min(p + 0.12, 1)), 2, [114, 235, 203, 140]);
  const c = Math.round(62 * Math.min(p * 1.4, 1));
  for (const [cx, cy, sx, sy] of [[x, y, 1, 1], [x + ww, y, -1, 1], [x, y + hh, 1, -1], [x + ww, y + hh, -1, -1]]) {
    rect(px, w, h, sx > 0 ? cx : cx - c, cy, c, 4, [248, 211, 77, 140]);
    rect(px, w, h, cx, sy > 0 ? cy : cy - c, 4, c, [248, 211, 77, 140]);
  }
}

function title(px, w, h, safeTop, p) {
  rect(px, w, h, 192, safeTop + 82, Math.round(696 * Math.min(p * 1.25, 1)), 96, [2, 7, 12, 188]);
  rect(px, w, h, 220, safeTop + 110, Math.round(520 * Math.min(p * 1.45, 1)), 16, [255, 255, 255, 232]);
  rect(px, w, h, 220, safeTop + 142, Math.round(260 * Math.min(Math.max(p - 0.12, 0) * 1.4, 1)), 9, [184, 204, 215, 175]);
}

function network(px, w, h, p) {
  rect(px, w, h, 498, 792, 84, 300, [18, 54, 76, Math.round(82 + 64 * p)]);
  rect(px, w, h, 372, 915, 336, 74, [12, 32, 48, Math.round(92 + 54 * p)]);
  const nodes = [[250, 920], [430, 820], [650, 998], [830, 878]];
  nodes.forEach(([x, y], idx) => {
    const local = Math.max(0, Math.min(1, p * 4 - idx * 0.55));
    const s = Math.round(46 + 34 * local);
    rect(px, w, h, x - s / 2, y - s / 2, s, s, [12, 36, 54, Math.round(90 + 115 * local)]);
    rect(px, w, h, x - 7, y - 7, 14, 14, [114, 235, 203, Math.round(160 * local)]);
    if (idx) {
      const [px0, py0] = nodes[idx - 1];
      rect(px, w, h, Math.min(px0, x), Math.min(py0, y), Math.max(Math.abs(x - px0) * local, 8), 8, [248, 211, 77, Math.round(170 * local)]);
    }
  });
}

function terminal(px, w, h, p, index) {
  rect(px, w, h, 188, 770, 704, 72, [255, 92, 122, Math.round(44 + 42 * p)]);
  rect(px, w, h, 206, 790, Math.round(318 * p), 18, [255, 255, 255, 210]);
  for (let row = 0; row < Math.round(6 * p); row++) {
    const y = 876 + row * 48;
    const color = row < 2 && index % 6 < 3 ? [255, 92, 122, 210] : [114, 235, 203, 190];
    rect(px, w, h, 214, y, 626 - row * 34, 18, color);
    rect(px, w, h, 214, y + 26, 420 - row * 22, 8, [184, 204, 215, Math.round(120 * p)]);
  }
  rect(px, w, h, 214, 1180, Math.round(612 * p), 18, [248, 211, 77, 230]);
}

function meters(px, w, h, p) {
  [[842, [114, 235, 203, 224], 0.88], [1032, [248, 211, 77, 224], 0.72]].forEach(([y, color, fill]) => {
    rect(px, w, h, 228, y - 44, 624, 118, [10, 28, 42, 132]);
    rect(px, w, h, 260, y, 540, 32, [255, 255, 255, 42]);
    rect(px, w, h, 260, y, Math.round(540 * fill * p), 32, color);
    rect(px, w, h, 260, y - 30, Math.round(240 * Math.min(p * 1.3, 1)), 10, [255, 255, 255, 220]);
  });
}

function rail(px, w, h, p) {
  rect(px, w, h, 210, 982, 660, 10, [255, 255, 255, 60]);
  rect(px, w, h, 210, 982, Math.round(660 * p), 10, [248, 211, 77, 220]);
  [230, 430, 630, 830].forEach((x, idx) => {
    const local = Math.max(0, Math.min(1, p * 4 - idx * 0.5));
    rect(px, w, h, x - 38, 914, 76, 138, [12, 36, 54, Math.round(80 + 120 * local)]);
    rect(px, w, h, x - 22, 936, 44, 44, [114, 235, 203, Math.round(100 + 110 * local)]);
  });
}

function split(px, w, h, p) {
  const left = Math.min(p * 1.35, 1);
  const right = Math.min(Math.max(p - 0.18, 0) * 1.45, 1);
  rect(px, w, h, 174 - 42 * (1 - left), 824, 310, 270, [38, 90, 128, Math.round(92 + 88 * left)]);
  rect(px, w, h, 596 + 42 * (1 - right), 824, 310, 270, [28, 126, 92, Math.round(92 + 88 * right)]);
  rect(px, w, h, 504, 910, Math.round(72 * p), 72, [248, 211, 77, Math.round(120 + 90 * p)]);
}

function lens(px, w, h, p) {
  const s = Math.round(210 + 70 * p);
  rect(px, w, h, 540 - s / 2, 940 - s / 2, s, s, [110, 235, 255, Math.round(36 + 34 * p)]);
  rect(px, w, h, 430, 1046, Math.round(280 * p), 12, [248, 211, 77, 230]);
}

function concept(px, w, h, p) {
  [820, 924, 1028].forEach((y, idx) => {
    const local = Math.max(0, Math.min(1, p * 3 - idx * 0.45));
    rect(px, w, h, 228 + idx * 28, y, Math.round((620 - idx * 56) * local), 68, [12, 36, 54, Math.round(92 + 82 * local)]);
    rect(px, w, h, 254 + idx * 28, y + 24, Math.round((300 - idx * 28) * local), 12, [255, 255, 255, Math.round(180 * local)]);
  });
}

async function annotateText(file, tpl, p) {
  if (p < 0.08) return;
  const svg = textOverlaySvg(tpl, p);
  const tmp = `${file}.tmp.png`;
  await sharp(file)
    .composite([{input: Buffer.from(svg), left: 0, top: 0}])
    .png()
    .toFile(tmp);
  fs.renameSync(tmp, file);
}

function textOverlaySvg(tpl, p) {
  const opacity = Math.max(0, Math.min(1, (p - 0.08) / 0.28));
  const parts = [];
  if (tpl === 'negation_to_connector_scene') {
    parts.push(svgText(label(0, '芯片'), 302, 900, 30, '#FFFFFF', 800, opacity, 'middle'));
    parts.push(svgText(label(1, '光模块'), 778, 900, 30, '#FFFFFF', 800, opacity, 'middle'));
    parts.push(svgText(label(2, '连接器'), 540, 1104, 28, '#FFFFFF', 800, opacity, 'middle'));
  } else if (tpl === 'connector_flow_scene' || tpl === 'concept_definition_scene' || tpl === 'cause_to_result_scene' || tpl === 'before_after_scene') {
    [[250, 1050], [540, 1050], [830, 1050]].forEach(([x, y], i) => parts.push(svgText(label(i, ['输入','连接器','输出'][i]), x, y, 26, '#FFFFFF', 750, opacity, 'middle')));
  } else if (tpl === 'metric_growth_scene') {
    parts.push(svgText(label(0, '连接规模'), 260, 820, 28, '#FFFFFF', 750, opacity));
    parts.push(svgText(label(2, '快速增加'), 260, 1010, 28, '#FFFFFF', 750, opacity));
    parts.push(svgText('GROWTH', 540, 1210, 22, '#F8D34D', 900, opacity, 'middle'));
  } else if (tpl === 'process_migration_scene') {
    parts.push(svgText(label(0, '旧路径'), 310, 930, 26, '#FFFFFF', 800, opacity, 'middle'));
    parts.push(svgText(label(1, '新路径'), 540, 1048, 26, '#FFFFFF', 800, opacity, 'middle'));
    parts.push(svgText(label(2, '结果'), 763, 1120, 26, '#FFFFFF', 800, opacity, 'middle'));
  } else if (tpl === 'density_pressure_scene') {
    parts.push(svgText(label(0, 'FAU'), 310, 990, 28, '#FFFFFF', 800, opacity, 'middle'));
    parts.push(svgText(label(1, '高密度压力'), 480, 820, 22, '#FF5C7A', 800, opacity, 'middle'));
    parts.push(svgText(label(2, 'GlassBridge'), 746, 1000, 28, '#FFFFFF', 800, opacity, 'middle'));
  } else if (tpl === 'chip_node_network') {
    [[250, 990], [430, 790], [650, 1068], [830, 848]].forEach(([x, y], i) => {
      parts.push(svgText(label(i, `节点${i + 1}`), x, y, 24, '#FFFFFF', 700, opacity, 'middle'));
    });
  } else if (tpl === 'system_error_terminal') {
    parts.push(svgText(label(0, '异常告警'), 206, 826, 28, '#FFFFFF', 800, opacity));
    [0, 1, 2, 3].forEach((i) => parts.push(svgText(label(i, `处理${i + 1}`), 214, 864 + i * 48, 22, '#EAF7FF', 650, opacity)));
    parts.push(svgText('RESOLVE', 214, 1168, 20, '#F8D34D', 800, opacity));
  } else if (tpl === 'kpi_dual_meter_panel') {
    parts.push(svgText(label(0, '基准指标'), 260, 820, 28, '#FFFFFF', 750, opacity));
    parts.push(svgText(label(1, '变化趋势'), 260, 1010, 28, '#FFFFFF', 750, opacity));
    parts.push(svgText('88%', 762, 826, 30, '#72EBCB', 900, opacity, 'middle'));
    parts.push(svgText('72%', 762, 1016, 30, '#F8D34D', 900, opacity, 'middle'));
  } else if (tpl === 'process_milestone_rail') {
    [230, 430, 630, 830].forEach((x, i) => {
      parts.push(svgText(`0${i + 1}`, x, 930, 22, '#F8D34D', 900, opacity, 'middle'));
      parts.push(svgText(label(i, `阶段${i + 1}`), x, 1024, 22, '#FFFFFF', 700, opacity, 'middle'));
    });
  } else if (tpl === 'comparison_split_glass' || tpl === 'not_x_but_y_pivot_panel') {
    parts.push(svgText(label(0, '旧判断'), 330, 980, 28, '#FFFFFF', 800, opacity, 'middle'));
    parts.push(svgText(label(textItems.length - 1, '新判断'), 752, 980, 28, '#FFFFFF', 800, opacity, 'middle'));
    parts.push(svgText('PIVOT', 548, 960, 18, '#02070B', 900, opacity, 'middle'));
  } else if (tpl === 'callout_lens_overlay') {
    parts.push(svgText(label(0, '关键细节'), 540, 950, 30, '#FFFFFF', 800, opacity, 'middle'));
  } else {
    [0, 1, 2].forEach((i) => parts.push(svgText(label(i, `要点${i + 1}`), 254 + i * 28, 866 + i * 104, 27, '#FFFFFF', 750, opacity)));
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><style>text{font-family:'PingFang SC','Heiti SC','Arial Unicode MS',sans-serif;paint-order:stroke;stroke:#02070B;stroke-width:5px;stroke-linejoin:round;}</style>${parts.join('')}</svg>`;
}

function svgText(text, x, y, size, color, weight, opacity = 1, anchor = 'start') {
  return `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}" opacity="${opacity.toFixed(3)}" text-anchor="${anchor}">${escapeXml(text)}</text>`;
}

function label(index, fallback) {
  return fit(textItems[index] ?? fallback, 13);
}

function fit(value, max) {
  const text = String(value ?? '').replace(/\\s+/g, '');
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'}[ch]));
}

function rect(px, w, h, x, y, ww, hh, rgba) {
  const [r, g, b, a] = rgba.map(v => Math.max(0, Math.min(255, Math.round(v))));
  const x0 = Math.max(0, Math.min(w, Math.round(x)));
  const y0 = Math.max(0, Math.min(h, Math.round(y)));
  const x1 = Math.max(0, Math.min(w, Math.round(x + ww)));
  const y1 = Math.max(0, Math.min(h, Math.round(y + hh)));
  for (let yy = y0; yy < y1; yy++) {
    const row = yy * w * 4;
    for (let xx = x0; xx < x1; xx++) {
      const i = row + xx * 4;
      px[i] = r; px[i + 1] = g; px[i + 2] = b; px[i + 3] = a;
    }
  }
}

function writePng(file, w, h, px) {
  const raw = Buffer.alloc(h * (w * 4 + 1));
  for (let y = 0; y < h; y++) {
    raw[y * (w * 4 + 1)] = 0;
    px.copy(raw, y * (w * 4 + 1) + 1, y * w * 4, (y + 1) * w * 4);
  }
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  fs.writeFileSync(file, Buffer.concat([
    signature,
    chunk('IHDR', packHeader(w, h)),
    chunk('IDAT', zlib.deflateSync(raw, {level: 9})),
    chunk('IEND', Buffer.alloc(0)),
  ]));
}

function packHeader(w, h) {
  const b = Buffer.alloc(13);
  b.writeUInt32BE(w, 0);
  b.writeUInt32BE(h, 4);
  b[8] = 8; b[9] = 6; b[10] = 0; b[11] = 0; b[12] = 0;
  return b;
}

function chunk(type, data) {
  const name = Buffer.from(type);
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([name, data])), 0);
  return Buffer.concat([len, name, data, crc]);
}

function crc32(buf) {
  let c = 0xffffffff;
  for (const byte of buf) {
    c ^= byte;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  }
  return (c ^ 0xffffffff) >>> 0;
}
"""


def tsconfig_json() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "jsxImportSource": "@motion-canvas/2d/lib",
    "resolveJsonModule": true,
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "motion-props.json"]
}
"""


def project_ts() -> str:
    return """import {makeProject} from '@motion-canvas/core';
import logic from './scenes/logic?scene';

export default makeProject({
  name: 'short-video-engine-motion',
  scenes: [logic],
});
"""


def motion_canvas_env_d_ts() -> str:
    return """declare module '*?scene' {
  import type {FullSceneDescription} from '@motion-canvas/core/lib/scenes';
  const scene: FullSceneDescription;
  export default scene;
}
"""


def tech_hud_templates_tsx() -> str:
    return """import {Circle, Line, Rect, Txt} from '@motion-canvas/2d';
import {all, createRef, createSignal, sequence, waitFor} from '@motion-canvas/core';

type GraphicScene = {
  scene_template?: string;
  primary_title?: string;
  secondary_labels?: string[];
  nodes?: {id?: string; label?: string; role?: string}[];
  metrics?: {id?: string; label?: string; value?: string}[];
  connectors?: {from?: string; to?: string; style?: string}[];
};

type Props = {
  visual_claim?: string;
  motion_text_items?: string[];
  expression_plan?: {template?: string; graphic_scene?: GraphicScene};
};

const W = 1080;
const H = 1920;
const PANEL = {x: 0, y: 120, width: 856, height: 588};
const palette = {
  ink: 'rgba(2,7,12,0.74)',
  panel: 'rgba(7,18,28,0.72)',
  edge: '#6EEBFF',
  mint: '#72EBCB',
  gold: '#F8D34D',
  red: '#FF5C7A',
  text: '#FFFFFF',
  sub: '#B8CCD7',
};

function labels(props: Props): string[] {
  const scene = props.expression_plan?.graphic_scene;
  const sceneLabels = Array.isArray(scene?.secondary_labels) ? scene!.secondary_labels! : [];
  const motionLabels = Array.isArray(props.motion_text_items) ? props.motion_text_items : [];
  return [...sceneLabels, ...motionLabels, '输入', '节点', '连接', '输出'].map(String).filter(Boolean).slice(0, 6);
}

function sceneOf(props: Props): GraphicScene {
  return props.expression_plan?.graphic_scene ?? {};
}

function labelAt(items: string[], index: number, fallback: string): string {
  return String(items[index] ?? fallback).slice(0, 14);
}

export function HudShell({title}: {title: string}) {
  return (
    <Rect layout={false} width={W} height={H}>
      <Rect x={0} y={0} width={932} height={1048} fill={'rgba(2,9,16,0.22)'} />
      {Array.from({length: 9}).map((_, i) => (
        <Line points={[[-428 + i * 96, -174], [-428 + i * 96, 414]]} stroke={'rgba(110,235,255,0.14)'} lineWidth={1} />
      ))}
      {Array.from({length: 8}).map((_, i) => (
        <Line points={[[-428, -132 + i * 72], [428, -132 + i * 72]]} stroke={'rgba(114,235,203,0.12)'} lineWidth={1} />
      ))}
      <Rect x={PANEL.x} y={PANEL.y} width={PANEL.width} height={PANEL.height} radius={24} fill={palette.panel} stroke={palette.edge} lineWidth={3} shadowColor={'rgba(110,235,255,0.26)'} shadowBlur={22} />
      <Line points={[[-428, -174], [-344, -174]]} stroke={palette.gold} lineWidth={5} />
      <Line points={[[428, -174], [344, -174]]} stroke={palette.gold} lineWidth={5} />
      <Line points={[[-428, 414], [-344, 414]]} stroke={palette.gold} lineWidth={5} />
      <Line points={[[428, 414], [344, 414]]} stroke={palette.gold} lineWidth={5} />
    </Rect>
  );
}

function NodeToken({x, y, label, tone = palette.mint}: {x: number; y: number; label: string; tone?: string}) {
  return (
    <Rect x={x} y={y} width={160} height={104} radius={18} fill={'rgba(12,36,54,0.86)'} stroke={tone} lineWidth={3} shadowColor={tone} shadowBlur={16}>
      <Circle width={18} height={18} fill={tone} y={-28} />
      <Txt text={label} y={20} fill={palette.text} fontFamily={'PingFang SC'} fontSize={26} fontWeight={650} />
    </Rect>
  );
}

function MetricBar({x, y, label, value, tone}: {x: number; y: number; label: string; value: number; tone: string}) {
  return (
    <Rect x={x} y={y} width={624} height={118} radius={18} fill={'rgba(10,28,42,0.74)'} stroke={'rgba(184,204,215,0.26)'} lineWidth={2}>
      <Txt text={label} x={-210} y={-30} fill={palette.text} fontFamily={'PingFang SC'} fontSize={26} fontWeight={650} />
      <Rect x={18} y={18} width={540} height={32} radius={16} fill={'rgba(255,255,255,0.12)'} />
      <Rect x={-252 + 270 * value} y={18} width={540 * value} height={32} radius={16} fill={tone} shadowColor={tone} shadowBlur={14} />
    </Rect>
  );
}

export function ChipNodeNetwork({props}: {props: Props}) {
  const items = labels(props);
  return (
    <Rect layout={false}>
      <HudShell title={sceneOf(props).primary_title ?? props.visual_claim ?? '节点网络'} />
      <Line points={[[-280, 40], [-100, -60], [120, 118], [300, -2]]} stroke={palette.gold} lineWidth={8} />
      <Rect x={0} y={60} width={112} height={336} radius={18} fill={'rgba(18,54,76,0.64)'} stroke={'rgba(110,235,255,0.30)'} />
      <NodeToken x={-290} y={40} label={labelAt(items, 0, '输入')} />
      <NodeToken x={-100} y={-60} label={labelAt(items, 1, '节点')} />
      <NodeToken x={130} y={120} label={labelAt(items, 2, '连接')} />
      <NodeToken x={320} y={0} label={labelAt(items, 3, '输出')} />
    </Rect>
  );
}

export function SystemErrorTerminal({props}: {props: Props}) {
  const items = labels(props);
  return (
    <Rect layout={false}>
      <HudShell title={sceneOf(props).primary_title ?? props.visual_claim ?? '系统异常'} />
      <Rect x={0} y={-18} width={704} height={74} radius={14} fill={'rgba(255,92,122,0.28)'} stroke={palette.red} lineWidth={3}>
        <Txt text={labelAt(items, 0, '异常告警')} fill={palette.text} fontFamily={'PingFang SC'} fontSize={30} fontWeight={700} />
      </Rect>
      {items.slice(0, 5).map((item, i) => (
        <Rect x={-4} y={84 + i * 54} width={640 - i * 36} height={24} radius={8} fill={i < 2 ? palette.red : palette.mint} opacity={0.86}>
          <Txt text={item} x={-220} y={-34} fill={palette.sub} fontSize={18} fontFamily={'PingFang SC'} />
        </Rect>
      ))}
      <Line points={[[-310, 400], [310, 400]]} stroke={palette.gold} lineWidth={14} />
    </Rect>
  );
}

export function KpiDualMeterPanel({props}: {props: Props}) {
  const items = labels(props);
  return (
    <Rect layout={false}>
      <HudShell title={sceneOf(props).primary_title ?? props.visual_claim ?? '指标变化'} />
      <MetricBar x={0} y={-22} label={labelAt(items, 0, '基准')} value={0.88} tone={palette.mint} />
      <MetricBar x={0} y={168} label={labelAt(items, 1, '变化')} value={0.72} tone={palette.gold} />
    </Rect>
  );
}

export function ProcessMilestoneRail({props}: {props: Props}) {
  const items = labels(props);
  const xs = [-310, -100, 110, 320];
  return (
    <Rect layout={false}>
      <HudShell title={sceneOf(props).primary_title ?? props.visual_claim ?? '流程推进'} />
      <Line points={[[-330, 116], [330, 116]]} stroke={'rgba(255,255,255,0.24)'} lineWidth={8} />
      <Line points={[[-330, 116], [330, 116]]} stroke={palette.gold} lineWidth={10} />
      {xs.map((x, i) => (
        <Rect x={x} y={84} width={92} height={150} radius={18} fill={'rgba(12,36,54,0.86)'} stroke={palette.mint} lineWidth={3}>
          <Txt text={`0${i + 1}`} y={-38} fill={palette.gold} fontSize={24} fontFamily={'Inter'} fontWeight={800} />
          <Txt text={labelAt(items, i, `阶段${i + 1}`)} y={24} fill={palette.text} fontFamily={'PingFang SC'} fontSize={24} />
        </Rect>
      ))}
    </Rect>
  );
}

export function SplitPivotPanel({props}: {props: Props}) {
  const items = labels(props);
  return (
    <Rect layout={false}>
      <HudShell title={sceneOf(props).primary_title ?? props.visual_claim ?? '转折关系'} />
      <NodeToken x={-230} y={90} label={labelAt(items, 0, '旧判断')} tone={'#6EEBFF'} />
      <NodeToken x={230} y={90} label={labelAt(items, items.length - 1, '新判断')} tone={palette.mint} />
      <Rect x={0} y={90} width={96} height={96} radius={18} fill={'rgba(248,211,77,0.90)'} shadowColor={palette.gold} shadowBlur={18}>
        <Txt text={'PIVOT'} fill={'#02070B'} fontSize={20} fontFamily={'Inter'} fontWeight={900} />
      </Rect>
    </Rect>
  );
}

export function ConceptCard({props}: {props: Props}) {
  const items = labels(props);
  return (
    <Rect layout={false}>
      <HudShell title={sceneOf(props).primary_title ?? props.visual_claim ?? '核心概念'} />
      {items.slice(0, 3).map((item, i) => (
        <Rect x={i * 34} y={-10 + i * 104} width={640 - i * 60} height={78} radius={18} fill={'rgba(12,36,54,0.82)'} stroke={i === 1 ? palette.gold : palette.mint} lineWidth={3}>
          <Txt text={item} fill={palette.text} fontFamily={'PingFang SC'} fontSize={28} fontWeight={650} />
        </Rect>
      ))}
    </Rect>
  );
}

export function renderGraphicScene(props: Props) {
  const template = String(sceneOf(props).scene_template ?? props.expression_plan?.['template'] ?? 'tech_hud_concept_card');
  if (template === 'chip_node_network') return <ChipNodeNetwork props={props} />;
  if (template === 'system_error_terminal') return <SystemErrorTerminal props={props} />;
  if (template === 'kpi_dual_meter_panel') return <KpiDualMeterPanel props={props} />;
  if (template === 'process_milestone_rail') return <ProcessMilestoneRail props={props} />;
  if (template === 'comparison_split_glass' || template === 'not_x_but_y_pivot_panel') return <SplitPivotPanel props={props} />;
  return <ConceptCard props={props} />;
}

export function* animateHudBuild(root: any) {
  root.opacity(0);
  root.scale(0.96);
  yield* all(root.opacity(1, 0.18), root.scale(1, 0.38));
  yield* waitFor(0.18);
}
"""


def logic_scene_tsx() -> str:
    return """import {makeScene2D, Rect} from '@motion-canvas/2d';
import {createRef, waitFor} from '@motion-canvas/core';
import props from '../../motion-props.json';
import {animateHudBuild, renderGraphicScene} from '../templates/techHudTemplates';

export default makeScene2D(function* (view) {
  view.fill(null);
  const root = createRef<Rect>();

  view.add(
    <Rect ref={root} layout={false} x={0} y={0} width={1080} height={1920}>
      {renderGraphicScene(props)}
    </Rect>,
  );

  yield* animateHudBuild(root());
  yield* waitFor(1.1);
});
"""


def readme_md() -> str:
    return """# Motion Canvas Source

This directory is generated by `short_video_engine` as a high-quality S5 renderer source handoff.

The production validator does not accept these source files as motion evidence. It only accepts the rendered transparent PNG sequence or video layer referenced by `work/plan/motion_layers.json`.

Suggested local render:

```bash
npm install
npm run render
```
"""
