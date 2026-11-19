#!/usr/bin/env bash
# Install the skill pack: copy (default) or symlink every skills/<name> into a skills directory.
# Usage:
#   scripts/install.sh [--target DIR] [--link]
# Targets:
#   Claude Code, global:   ~/.claude/skills            (default)
#   Claude Code, project:  <your project>/.claude/skills
#   Codex:                 pass the skills directory your Codex version reads (check the Codex docs)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${HOME}/.claude/skills"
MODE="copy"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      [ "$#" -ge 2 ] || { echo "--target needs a directory" >&2; exit 2; }
      TARGET="$2"
      shift 2
      ;;
    --link)
      MODE="link"
      shift
      ;;
    -h|--help)
      sed -n '2,9p' "$0"
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$TARGET"
for dir in "$ROOT"/skills/*/; do
  name="$(basename "$dir")"
  dest="$TARGET/$name"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    echo "skip $name: $dest already exists (remove it first to reinstall)"
    continue
  fi
  if [ "$MODE" = "link" ]; then
    ln -s "${dir%/}" "$dest"
  else
    cp -R "${dir%/}" "$dest"
  fi
  echo "installed $name -> $dest ($MODE)"
done
echo "done: restart your agent session so that it picks the skills up"
