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
    write_text(src_dir / "project.ts", project_ts())
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
            str(src_dir / "project.ts"),
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
    panel_x, panel_y, panel_w, panel_h = 120, 710, 840, 520
    glow = int(80 + 80 * progress)
    rect_rgba(pixels, width, height, 86, 392, 908, 1010, (4, 12, 20, 34))
    rect_rgba(pixels, width, height, panel_x, panel_y, panel_w, panel_h, (7, 18, 28, 150))
    rect_rgba(pixels, width, height, panel_x, panel_y, int(panel_w * progress), 4, (110, 235, 255, 210))
    rect_rgba(pixels, width, height, panel_x, panel_y + panel_h - 4, int(panel_w * min(progress + 0.1, 1)), 4, (114, 235, 203, 190))
    rect_rgba(pixels, width, height, 210, safe_top + 90, int(660 * min(progress * 1.3, 1)), 82, (2, 7, 12, 178))
    rect_rgba(pixels, width, height, 238, safe_top + 116, int(410 * min(progress * 1.5, 1)), 18, (255, 255, 255, 235))
    if template == "chip_node_network":
        draw_network(pixels, width, height, progress, glow)
    elif template == "system_error_terminal":
        draw_terminal(pixels, width, height, progress, index)
    elif template == "kpi_dual_meter_panel":
        draw_meters(pixels, width, height, progress)
    elif template == "process_milestone_rail":
        draw_rail(pixels, width, height, progress)
    else:
        draw_network(pixels, width, height, progress, glow)


def draw_network(pixels: bytearray, width: int, height: int, progress: float, glow: int) -> None:
    nodes = [(260, 900), (460, 820), (650, 980), (820, 870)]
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
    rows = int(6 * progress)
    for row in range(rows):
        y = 810 + row * 56
        color = (255, 92, 122, 210) if row < 2 and index % 6 < 3 else (114, 235, 203, 190)
        rect_rgba(pixels, width, height, 210, y, 600 - row * 34, 22, color)
    rect_rgba(pixels, width, height, 210, 1130, int(600 * progress), 18, (248, 211, 77, 230))


def draw_meters(pixels: bytearray, width: int, height: int, progress: float) -> None:
    rect_rgba(pixels, width, height, 250, 850, 580, 36, (255, 255, 255, 42))
    rect_rgba(pixels, width, height, 250, 850, int(520 * progress), 36, (114, 235, 203, 224))
    rect_rgba(pixels, width, height, 250, 1010, 580, 36, (255, 255, 255, 42))
    rect_rgba(pixels, width, height, 250, 1010, int(440 * progress), 36, (248, 211, 77, 224))


def draw_rail(pixels: bytearray, width: int, height: int, progress: float) -> None:
    rect_rgba(pixels, width, height, 210, 980, 660, 10, (255, 255, 255, 60))
    rect_rgba(pixels, width, height, 210, 980, int(660 * progress), 10, (248, 211, 77, 220))
    for idx, x in enumerate([230, 430, 630, 830]):
        local = max(0.0, min(1.0, progress * 4 - idx * 0.5))
        rect_rgba(pixels, width, height, x - 32, 930, 64, 100, (12, 36, 54, int(80 + 120 * local)))


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
    "dev": "motion-canvas",
    "render": "motion-canvas render --project src/project.ts --transparent"
  },
  "dependencies": {
    "@motion-canvas/2d": "^3.17.0",
    "@motion-canvas/core": "^3.17.0",
    "@motion-canvas/vite-plugin": "^3.17.0",
    "vite": "^5.0.0",
    "typescript": "^5.0.0"
  },
  "devDependencies": {}
}
"""


def tsconfig_json() -> str:
    return """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "jsxImportSource": "@motion-canvas/2d",
    "resolveJsonModule": true,
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "motion-props.json"]
}
"""


def project_ts() -> str:
    return """import {makeProject} from '@motion-canvas/core';
import logic from './scenes/logic';

export default makeProject({
  scenes: [logic],
});
"""


def logic_scene_tsx() -> str:
    return """import {makeScene2D, Rect, Txt, Line} from '@motion-canvas/2d';
import {all, createRef, waitFor} from '@motion-canvas/core';
import props from '../../motion-props.json';

function label(index: number, fallback: string): string {
  return String((props.motion_text_items as string[])[index] ?? fallback);
}

export default makeScene2D(function* (view) {
  view.fill(null);
  const claim = createRef<Txt>();
  const left = createRef<Rect>();
  const right = createRef<Rect>();
  const arrow = createRef<Line>();
  const progress = createRef<Rect>();

  view.add(
    <Rect layout={false} x={0} y={0} width={1080} height={1920}>
      <Rect x={0} y={-470} width={910} height={104} radius={22} fill={'rgba(0,0,0,0.70)'} stroke={'#72ebbf'} lineWidth={3}>
        <Txt ref={claim} text={String(props.visual_claim ?? '逻辑变化')} fill={'#ffffff'} fontSize={58} fontFamily={'PingFang SC'} />
      </Rect>
      <Rect ref={left} x={-255} y={-20} width={380} height={372} radius={28} fill={'rgba(45,116,150,0.82)'} stroke={'#6ee1ff'} lineWidth={4}>
        <Txt text={label(0, '旧状态')} fill={'#ffffff'} fontSize={46} fontFamily={'PingFang SC'} />
      </Rect>
      <Rect ref={right} x={255} y={-20} width={380} height={372} radius={28} fill={'rgba(38,145,93,0.82)'} stroke={'#72ebbf'} lineWidth={4}>
        <Txt text={label(1, '新状态')} fill={'#ffffff'} fontSize={46} fontFamily={'PingFang SC'} />
      </Rect>
      <Line ref={arrow} points={[[-150, -20], [150, -20]]} stroke={'#fade5a'} lineWidth={12} endArrow opacity={0} />
      <Rect ref={progress} x={-320} y={560} width={1} height={32} fill={'#72ebbf'} />
    </Rect>,
  );

  left().scale(0.86);
  right().scale(0.86);
  claim().opacity(0);
  yield* all(claim().opacity(1, 0.25), left().scale(1, 0.35));
  yield* all(arrow().opacity(1, 0.2), arrow().end(1, 0.45), right().scale(1, 0.35));
  yield* progress().width(860, 0.5);
  yield* waitFor(0.2);
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
