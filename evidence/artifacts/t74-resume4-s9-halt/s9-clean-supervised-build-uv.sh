#!/usr/bin/env bash
# T74RESUME4 — S9 clean supervised canary build, strategy=uv + uv.toml remedy.
# Authority: orchestrator amendment 9d06fdfe21 — pre-place uv.toml
# (link-mode = "copy") at container /tmp so uv ancestor-config discovery
# covers the disposable sandbox roots; build config only, zero candidate-code
# or snapshot-contract change. On-box discovery/schema proven by nlink probe
# (baseline nlink=2 -> ancestor-uv.toml nlink=1) before this attempt.
# Invocation identical to T74RESUME3 frozen S9; ALL output files are NEW
# paths (clause-7 no-overwrite): resume3 evidence stays byte-for-byte.
set -uo pipefail
umask 077
RUN_DIR="$(cat /tmp/arnold-t74-latest-run)"
# shellcheck disable=SC1090
source "$RUN_DIR/env.sh"

docker() {
  if [ "$1" = "exec" ]; then
    shift
    command docker exec -i -w /tmp "$@"
  else
    command docker "$@"
  fi
}

OUT="$RUN/clean-build.stdout.uv.r4.json"
ERR="/tmp/t74-resume4.s9.stderr"
EX="/tmp/t74-resume4.s9.exit"
: > "$ERR"

UVPATH="/tmp/arnold-t74-resume3-uv/bin:$CPATH"

 docker exec "$CTR" \
   env -i \
    PATH="$UVPATH" \
    LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    "$BUILD" \
      --source-repo "$CAND" \
      --root "$CLEAN_ROOT" \
      --slug t74-clean \
      --base-ref "$HEAD_SHA" \
      --generation-build-strategy uv \
      --supervise \
      --supervisor-timeout 900 \
  > "$OUT" 2> "$ERR"
code=$?
printf '%s\n' "$code" > "$EX"
if [ "$code" -ne 0 ]; then
  echo "S9-BUILD-FAILED exit=$code" >&2
  exit "$code"
fi

docker exec "$CTR" "$PY" "$ASSERT" clean "$CLEAN_ROOT" \
  > "$RUN/clean-build-verdict.uv.r4.json"
arc=$?
cat "$RUN/clean-build-verdict.uv.r4.json"
printf '%s\n' "$arc" > /tmp/t74-resume4.s9.assert-exit

docker exec "$CTR" cat "$CLEAN_ROOT/report.json" \
  > "$RUN/clean-build-report.uv.r4.json"
docker exec "$CTR" cat "$CLEAN_ROOT.supervisor/snapshot-anchor.json" \
  > "$RUN/clean-snapshot-anchor.uv.r4.json"
exit "$arc"
