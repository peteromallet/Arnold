#!/usr/bin/env bash
# Sync megaplan codex skills from this directory into ~/.claude, ~/.codex, and ~/.agents.
#
# For each top-level directory under arnold/pipelines/megaplan/data/_codex_skills
# (except _underscore ones), create a symlink in each target skills directory,
# ONLY IF nothing exists at that path yet. Never deletes or overwrites existing entries.
#
# Anything pre-existing that you want replaced must be removed by hand.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$REPO_ROOT/arnold/pipelines/megaplan/data/_codex_skills"
SKILL_TARGETS=(
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.agents/skills"
)

created=0
skipped=0

for entry in "$SRC_DIR"/*/; do
  [ -d "$entry" ] || continue
  name="$(basename "$entry")"
  case "$name" in
    _*) continue ;;
  esac
  src="$SRC_DIR/$name"

  for target_dir in "${SKILL_TARGETS[@]}"; do
    [ -d "$target_dir" ] || continue
    dest="$target_dir/$name"

    if [ -e "$dest" ] || [ -L "$dest" ]; then
      printf 'skip   %s (exists)\n' "$dest"
      skipped=$((skipped + 1))
      continue
    fi

    ln -s "$src" "$dest"
    printf 'linked %s -> %s\n' "$dest" "$src"
    created=$((created + 1))
  done
done

echo ""
echo "done: $created created, $skipped skipped"
