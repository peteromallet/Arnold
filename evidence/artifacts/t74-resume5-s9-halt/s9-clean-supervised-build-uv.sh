#!/usr/bin/env bash
# T74RESUME5 — S9 clean supervised canary build, strategy=uv + remedy D.
# Authority: JUDG-S9 blended decision (log section JUDG-S9): remedy D —
# PATH-staged uv wrapper forcing UV_LINK_MODE=copy at spawn. PATH is in
# the candidate _ENV_PASSTHROUGH allowlist (canary_sandbox.py:165);
# install_sync spawns ["uv","sync",...] via PATH with dict(os.environ)
# inherited (install_sync.py:579-585). Wrapper bytes identical at box
# /root/t74-resume5/uv-bin/uv and container /tmp/arnold-t74-resume5-uvwrap/uv,
# sha256 641843ee8ed7a4e6253143ec17b2f8a933eeb7317a65a258fd88ac38eeecdea0.
# Pre-attempt Grok probe PASSED: [tool.uv]-bearing frozen cffi project,
# baseline sync nlink>1 files=41 -> wrapped sync nlink>1 files=0.
# Invocation identical to T74RESUME4 frozen S9 except UVPATH wrapper-dir
# prepend; ALL output files NEW paths (clause-7 no-overwrite): resume2c/
# resume3/resume4 evidence stays byte-for-byte. Zero candidate-code or
# snapshot-contract change.
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

OUT="$RUN/clean-build.stdout.uv.r5.json"
ERR="/tmp/t74-resume5.s9.stderr"
EX="/tmp/t74-resume5.s9.exit"
: > "$ERR"

UVPATH="/tmp/arnold-t74-resume5-uvwrap:/tmp/arnold-t74-resume3-uv/bin:$CPATH"

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
  > "$RUN/clean-build-verdict.uv.r5.json"
arc=$?
cat "$RUN/clean-build-verdict.uv.r5.json"
printf '%s\n' "$arc" > /tmp/t74-resume5.s9.assert-exit

docker exec "$CTR" cat "$CLEAN_ROOT/report.json" \
  > "$RUN/clean-build-report.uv.r5.json"
docker exec "$CTR" cat "$CLEAN_ROOT.supervisor/snapshot-anchor.json" \
  > "$RUN/clean-snapshot-anchor.uv.r5.json"
exit "$arc"
