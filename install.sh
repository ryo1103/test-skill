#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/skills/short-video-editor"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
TARGET_ROOT="$CODEX_HOME_DIR/skills"
TARGET_DIR="$TARGET_ROOT/short-video-editor"

if [[ ! -f "$SOURCE_DIR/SKILL.md" ]]; then
  echo "Cannot find skills/short-video-editor/SKILL.md" >&2
  exit 1
fi

mkdir -p "$TARGET_ROOT"

if [[ -e "$TARGET_DIR" ]]; then
  BACKUP_DIR="${TARGET_DIR}.bak.$(date +%Y%m%d-%H%M%S)"
  mv "$TARGET_DIR" "$BACKUP_DIR"
  echo "Backed up existing skill to: $BACKUP_DIR"
fi

cp -R "$SOURCE_DIR" "$TARGET_DIR"
find "$TARGET_DIR" -name ".DS_Store" -delete

echo "Installed short-video-editor to: $TARGET_DIR"
echo "Restart Codex to refresh the skill list."
