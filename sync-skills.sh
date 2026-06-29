#!/usr/bin/env bash
# Sync Arnold/Megaplan skills from this repo into agent skill directories.
#
# For each top-level canonical skill directory, create or update a symlink in
# each target skills directory. Stale links created by older Arnold syncs are
# replaced; unrelated user skills are left alone.
#
# Canonical source: arnold_pipelines/megaplan/skills
# Retired source:   arnold_pipelines/megaplan/data/_codex_skills

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SKILLS_DIR="$REPO_ROOT/arnold_pipelines/megaplan/skills"
STALE_SKILLS_DIR="$REPO_ROOT/arnold_pipelines/megaplan/data/_codex_skills"
SKILL_TARGETS=(
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.agents/skills"
  "$HOME/.hermes/skills"
)

created=0
updated=0
skipped=0
removed=0

for target_dir in "${SKILL_TARGETS[@]}"; do
  mkdir -p "$target_dir"
  for dest in "$target_dir"/*; do
    [ -L "$dest" ] || continue
    current="$(readlink "$dest")"
    case "$current" in
      "$STALE_SKILLS_DIR"/*)
        rm "$dest"
        printf 'removed stale %s -> %s\n' "$dest" "$current"
        removed=$((removed + 1))
        ;;
    esac
  done
done

[ -d "$SOURCE_SKILLS_DIR" ] || {
  printf 'missing source skills dir: %s\n' "$SOURCE_SKILLS_DIR" >&2
  exit 1
}

for entry in "$SOURCE_SKILLS_DIR"/*/; do
  [ -d "$entry" ] || continue
  name="$(basename "$entry")"
  case "$name" in
    _*) continue ;;
  esac
  src="$SOURCE_SKILLS_DIR/$name"

  for target_dir in "${SKILL_TARGETS[@]}"; do
    dest="$target_dir/$name"

    if [ -L "$dest" ]; then
      current="$(readlink "$dest")"
      if [ "$current" = "$src" ]; then
        printf 'skip   %s (exists)\n' "$dest"
        skipped=$((skipped + 1))
        continue
      fi

      case "$current" in
        "$REPO_ROOT"/*)
          rm "$dest"
          ln -s "$src" "$dest"
          printf 'updated %s -> %s\n' "$dest" "$src"
          updated=$((updated + 1))
          ;;
        *)
          printf 'skip   %s (exists)\n' "$dest"
          skipped=$((skipped + 1))
          ;;
      esac
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

echo ""
echo "done: $created created, $updated updated, $removed stale removed, $skipped skipped"
