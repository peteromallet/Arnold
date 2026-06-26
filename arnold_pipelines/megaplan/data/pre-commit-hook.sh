#!/usr/bin/env bash
set -euo pipefail
# Regenerate composed bundles; fail if any changed.
#
# Launcher resolution mirrors the megaplan SKILL.md order so the hook works
# regardless of how python is exposed on this machine (pyenv, venv,
# uv, etc.). The first launcher whose `setup --regen-composed` returns
# 0 or 1 wins; an error like `command not found` falls through to the next.
LAUNCHERS=(
  "python"
  "./.venv/bin/python"
  "uv run python"
  "PYENV_VERSION=3.11.11 python"
)

run_regen() {
  local cmd="$1"
  # shellcheck disable=SC2086
  eval "$cmd -m arnold_pipelines.megaplan setup --regen-composed"
}

rc=127
for launcher in "${LAUNCHERS[@]}"; do
  if run_regen "$launcher"; then
    rc=0
    break
  else
    rc=$?
    # rc=1 means megaplan ran and regenerated files (expected failure mode).
    # Anything else (127 = command not found, 2 = module import error, etc.)
    # means the launcher itself failed — try the next one.
    if [ "$rc" = "1" ]; then
      break
    fi
  fi
done

if [ "$rc" = "1" ]; then
  git add arnold_pipelines/megaplan/data/_composed/
  echo 'megaplan: regenerated composed bundles — re-run git commit' >&2
  exit 1
fi

if [ "$rc" != "0" ]; then
  echo "megaplan: pre-commit hook could not find a working python launcher (rc=$rc)" >&2
  echo "megaplan: tried: ${LAUNCHERS[*]}" >&2
  exit "$rc"
fi

exit 0
