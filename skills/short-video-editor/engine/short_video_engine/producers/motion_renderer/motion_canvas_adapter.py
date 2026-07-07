from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from ... import ENGINE_VERSION
from ...paths import plan_dir


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
