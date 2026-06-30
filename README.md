# test-skill

Codex skills for short-video production workflows.

## Included Skills

- `short-video-editor`: Create reproducible workflows and editable assets for 1-2 minute vertical Chinese knowledge, explainer, or news commentary videos from an oral/talking-head video plus script.

## Install

Clone this repository, then run:

```bash
./install.sh
```

The script installs the skill to:

```text
${CODEX_HOME:-$HOME/.codex}/skills/short-video-editor
```

If an older local copy exists, it is moved to a timestamped backup path first.

## Install With Codex Skill Installer

If using Codex's skill installer, install from:

```text
repo: ryo1103/test-skill
path: skills/short-video-editor
```

## Usage

After installation, restart Codex and ask:

```text
用 Short Video Editor 处理这个项目：口播视频是 avater.mp4，文案是 script.txt，帮我生成分镜、成片和可重剪素材包。
```

## Notes

This repository contains only the reusable skill. It does not include project videos, downloaded B-roll, rendered outputs, caches, local API keys, or temporary project render scripts.
