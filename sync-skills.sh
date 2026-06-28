#!/usr/bin/env bash
# Sync megaplan codex skills from this directory into ~/.claude and ~/.codex.
#
# For each top-level bundled skill directory, create a symlink in each target skills directory.
# Existing non-repo entries are left alone; repo-owned skill links can be refreshed when a
# bundled skill moves from generated data into the source skills directory.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SKILLS_DIR="$REPO_ROOT/arnold_pipelines/megaplan/skills"
SRC_DIRS=(
  "$REPO_ROOT/arnold_pipelines/megaplan/data/_codex_skills"
  "$SOURCE_SKILLS_DIR"
)
SKILL_TARGETS=(
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.agents/skills"
  "$HOME/.hermes/skills"
)

created=0
updated=0
skipped=0

for src_dir in "${SRC_DIRS[@]}"; do
  [ -d "$src_dir" ] || continue
  for entry in "$src_dir"/*/; do
    [ -d "$entry" ] || continue
    name="$(basename "$entry")"
    case "$name" in
      _*) continue ;;
    esac
    if [ "$src_dir" != "$SOURCE_SKILLS_DIR" ] && [ -d "$SOURCE_SKILLS_DIR/$name" ]; then
      continue
    fi
    src="$src_dir/$name"

    for target_dir in "${SKILL_TARGETS[@]}"; do
      [ -d "$target_dir" ] || continue
      dest="$target_dir/$name"

      if [ -L "$dest" ]; then
        current="$(readlink "$dest")"
        if [ "$current" != "$src" ]; then
          case "$current:$name" in
            "$REPO_ROOT"/*:*|*:cleanup-loose-branches) ;;
            *)
              printf 'skip   %s (exists)\n' "$dest"
              skipped=$((skipped + 1))
              continue
              ;;
          esac
          rm "$dest"
          ln -s "$src" "$dest"
          printf 'updated %s -> %s\n' "$dest" "$src"
          updated=$((updated + 1))
        else
          printf 'skip   %s (exists)\n' "$dest"
          skipped=$((skipped + 1))
        fi
        continue
      fi

      if [ -e "$dest" ]; then
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
echo "done: $created created, $updated updated, $skipped skipped"
