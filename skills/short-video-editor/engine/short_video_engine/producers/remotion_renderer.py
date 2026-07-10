from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .. import ENGINE_VERSION
from ..paths import output_dir, plan_dir
from ..stage_result import failure
from .motion_renderer.motion_canvas_adapter import render_internal_motion_canvas_sequence


def remotion_project_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "remotion"


def remotion_runtime_available(project_dir: Path, *, allow_internal_test_renderer: bool = False) -> bool:
    if allow_internal_test_renderer:
        return True
    root = remotion_project_dir()
    if not (root / "package.json").exists():
        return False
    if shutil.which("node") is None or shutil.which("npm") is None:
        return False
    return (root / "node_modules" / ".bin" / "remotion").exists()


def prepare_remotion_runtime(project_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Install once per dependency lock hash, never per motion clip."""
    root = remotion_project_dir()
    if not root.exists() or not (root / "package.json").exists():
        return [], [failure("remotion_project_missing", "skills/short-video-editor/remotion is missing.")]
    lock = root / "package-lock.json"
    lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else "no_lock"
    stamp = plan_dir(project_dir) / "remotion_runtime.json"
    previous = json.loads(stamp.read_text(encoding="utf-8")) if stamp.exists() else {}
    binary = root / "node_modules" / ".bin" / "remotion"
    if binary.exists() and previous.get("package_lock_hash") == lock_hash:
        return [{"step": "npm_install", "skipped": True, "reason": "runtime_lock_hash_unchanged"}], []
    cmd = ["npm", "ci", "--no-audit", "--no-fund"] if lock.exists() else ["npm", "install", "--no-audit", "--no-fund"]
    install = run_cmd(cmd, cwd=root)
    log = command_log("npm_ci" if lock.exists() else "npm_install", install)
    if install.returncode != 0:
        return [log], [failure("remotion_install_failed", install.stderr[-1000:] or "npm dependency installation failed.")]
    stamp.write_text(json.dumps({"generated_by": "short_video_engine", "package_lock_hash": lock_hash, "install_log": log}, ensure_ascii=False, indent=2), encoding="utf-8")
    return [log], []


def render_remotion_artifact(
    project_dir: Path,
    segment: dict[str, Any],
    scene: dict[str, Any],
    decision: dict[str, Any],
    width: int,
    height: int,
    frame_count: int,
    *,
    allow_internal_test_renderer: bool = False,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    motion_id = str(segment.get("motion_id") or scene.get("scene_id") or segment.get("logic_segment_id") or "motion")
    frame_dir = output_dir(project_dir) / "qc" / "remotion_motion_frames" / motion_id
    reset_dir(frame_dir)
    props = {
        "templateId": decision.get("selected_template"),
        "motionId": motion_id,
        "width": width,
        "height": height,
        "fps": int((decision.get("input_props") or {}).get("fps") or 30),
        **(decision.get("input_props") if isinstance(decision.get("input_props"), dict) else {}),
    }
    props_path = plan_dir(project_dir) / "remotion_props" / f"{motion_id}.json"
    props_path.parent.mkdir(parents=True, exist_ok=True)
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    render_log: list[dict[str, Any]] = []
    if allow_internal_test_renderer:
        frames = render_internal_motion_canvas_sequence(frame_dir, scene, width, height, frame_count)
        return remotion_result(frame_dir, frames, decision, props_path, "internal_test_remotion_sequence", render_log), []
    if shutil.which("node") is None or shutil.which("npm") is None:
        return remotion_source_info(decision, props_path, frame_dir, render_log), [failure("remotion_runtime_unavailable", "Node/npm are required for Remotion production rendering.")]
    root = remotion_project_dir()
    if not root.exists():
        return remotion_source_info(decision, props_path, frame_dir, render_log), [failure("remotion_project_missing", "skills/short-video-editor/remotion is missing.")]
    runtime_log, runtime_failures = prepare_remotion_runtime(project_dir)
    render_log.extend(runtime_log)
    if runtime_failures:
        return remotion_source_info(decision, props_path, frame_dir, render_log), runtime_failures
    out_arg = str(frame_dir)
    public_dir = project_dir / "work" / "remotion_public"
    public_dir.mkdir(parents=True, exist_ok=True)
    render = run_cmd(["node", "scripts/render-sequence.mjs", "src/Root.tsx", "MotionLayer", out_arg, str(props_path), str(public_dir)], cwd=root)
    render_log.append(command_log("npm_run_render", render))
    if render.returncode != 0:
        return remotion_source_info(decision, props_path, frame_dir, render_log), [failure("remotion_render_failed", render.stderr[-1200:] or "Remotion render command failed.")]
    frames = normalize_rendered_frames(frame_dir)
    if not frames:
        return remotion_source_info(decision, props_path, frame_dir, render_log), [failure("remotion_render_no_frames", "Remotion render completed but no transparent PNG sequence was found.")]
    return remotion_result(frame_dir, frames, decision, props_path, "npm_remotion_sequence", render_log), []


def remotion_result(frame_dir: Path, frames: list[Path], decision: dict[str, Any], props_path: Path, status: str, render_log: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = evidence_for(frames)
    return {
        "motion_source_engine": "remotion",
        "motion_source_status": "rendered",
        "motion_source_project_dir": str(remotion_project_dir()),
        "motion_source_files": remotion_source_files(),
        "selected_template": decision.get("selected_template"),
        "input_props_path": str(props_path),
        "input_props_hash": hashlib.sha256(props_path.read_bytes()).hexdigest(),
        "remotion_render_status": status,
        "remotion_render_log": render_log,
        "renderer_backend": "remotion_sequence",
        "artifact_renderer_backend": "remotion_sequence",
        "png_sequence_dir": str(frame_dir),
        "layer_type": "png_sequence",
        "sequence_frame_count": len(frames),
        "sequence_fps": int((decision.get("input_props") or {}).get("fps") or 30),
        "expected_duration_sec": len(frames) / max(1, int((decision.get("input_props") or {}).get("fps") or 30)),
        "frame_evidence": evidence,
    }


def remotion_source_info(decision: dict[str, Any], props_path: Path, frame_dir: Path, render_log: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "motion_source_engine": "remotion",
        "motion_source_status": "prepared",
        "motion_source_project_dir": str(remotion_project_dir()),
        "motion_source_files": remotion_source_files(),
        "selected_template": decision.get("selected_template"),
        "input_props_path": str(props_path),
        "input_props_hash": hashlib.sha256(props_path.read_bytes()).hexdigest() if props_path.exists() else "",
        "remotion_render_status": "failed",
        "remotion_render_log": render_log,
        "renderer_backend": "remotion_source",
        "artifact_renderer_backend": "remotion_source",
        "png_sequence_dir": str(frame_dir),
        "layer_type": "source_project",
        "sequence_frame_count": 0,
        "frame_evidence": {},
    }


def remotion_source_files() -> list[str]:
    root = remotion_project_dir()
    if not root.exists():
        return []
    return [str(path) for path in sorted((root / "src").rglob("*")) if path.is_file() and path.suffix in {".tsx", ".ts", ".css"}]


def normalize_rendered_frames(frame_dir: Path) -> list[Path]:
    frames = sorted(path for path in frame_dir.rglob("*.png") if path.is_file())
    normalized = []
    for index, source in enumerate(frames):
        target = frame_dir / f"frame_{index:03d}.png"
        if source != target:
            target.write_bytes(source.read_bytes())
        normalized.append(target)
    for path in frame_dir.rglob("*.png"):
        if path.parent != frame_dir:
            path.unlink(missing_ok=True)
    return sorted(frame_dir.glob("frame_*.png"))


def evidence_for(frames: list[Path]) -> dict[str, str]:
    if not frames:
        return {}
    indexes = {
        "start": 0,
        "build": max(0, int((len(frames) - 1) * 0.25)),
        "mid": max(0, int((len(frames) - 1) * 0.5)),
        "peak": max(0, int((len(frames) - 1) * 0.68)),
        "settle": max(0, int((len(frames) - 1) * 0.84)),
        "end": len(frames) - 1,
    }
    return {key: str(frames[index]) for key, index in indexes.items()}


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("npm_config_cache", str(cwd / ".npm-cache"))
    env.setdefault("NPM_CONFIG_CACHE", str(cwd / ".npm-cache"))
    return subprocess.run(cmd, cwd=str(cwd), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def command_log(name: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {"step": name, "returncode": result.returncode, "stdout_tail": result.stdout[-1000:], "stderr_tail": result.stderr[-1000:], "engine_version": ENGINE_VERSION}
