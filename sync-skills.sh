#!/usr/bin/env bash
# Sync megaplan codex skills from this directory into ~/.claude and ~/.codex.
#
# For each top-level bundled skill directory, create a symlink in each target skills directory,
# ONLY IF nothing exists at that path yet. Never deletes or overwrites existing entries.
#
# Anything pre-existing that you want replaced must be removed by hand.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIRS=(
  "$REPO_ROOT/arnold_pipelines/megaplan/data/_codex_skills"
  "$REPO_ROOT/arnold_pipelines/megaplan/skills"
)
SKILL_TARGETS=(
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.agents/skills"
  "$HOME/.hermes/skills"
)

created=0
skipped=0

for src_dir in "${SRC_DIRS[@]}"; do
  [ -d "$src_dir" ] || continue
  for entry in "$src_dir"/*/; do
    [ -d "$entry" ] || continue
    name="$(basename "$entry")"
    case "$name" in
      _*) continue ;;
    esac
    src="$src_dir/$name"

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
done

echo ""
echo "done: $created created, $skipped skipped"
