# M2: ShannonStreamWorker + drift defense — the headless stream-json channel

**Milestone id:** `M2-stream-worker` · **Profile:** `partnered` · **Robustness:** `full` · **Depth:** `high` · **Vendor:** `codex` · **Prep:** ON · **Repo:** megaplan

Read `00-OVERVIEW.md` for the epic invariants. **Additive + flag-OFF** is mandatory here: this is NEW
code beside `shannon.py`; the engine keeps running the old tmux path. DEPENDS ON M1 (the seam + the
`rate_limit` field).

## Outcome
A `ShannonStreamWorker` that drives Claude headlessly via `claude --print --input-format=stream-json
--output-format=stream-json` behind the M1 seam — structured turn-end, no tmux, no scraping, no
transcript-tailing — gated OFF by a flag, plus the drift-defense that makes depending on Anthropic's
`--print` surface safe.

## Scope (six parts)
**(a) Launch:** env-scrub (`CLAUDECODE`/`CLAUDE_CODE_*`, keep `CLAUDE_CODE_MAX_OUTPUT_TOKENS`) +
`--permission-mode bypassPermissions` + cwd=worktree, API key forced empty to hold subscription OAuth.
**(b) Parser:** consume `init / assistant / result / rate_limit_event` → `WorkerResult` (populating
`rate_limit`); the `result` event is the unambiguous turn-end/death signal.
**(c) Multi-turn:** `--input-format=stream-json` as primary; `--resume <session_id>` as the
restart-survival fallback. Port the existing `session_roulette` (`/clear` 75% / `/compact` 25%, never
plain-resume) lifecycle into the new worker.
**(d) Permission fail-fast watchdog:** detect any headless "awaiting-permission / unexpected-denial"
state → immediate **retryable** fail (a denial must never wedge the channel — the fail-slow→fail-fast
property failure #8 demands).
**(e) Liveness re-home:** the three-channel probe's CPU/socket channels currently read tmux pane-pids;
under stream-json the Claude process is a direct child — re-wire them to `process.pid` so long silent
tool calls aren't false-killed.
**(f) Drift defense:** defensive parsing (tolerate unknown event types AND renamed fields — never fall
through to a garbage payload); a CI conformance smoke-test invoking `claude --print` against the pinned
binary that validates the event schema AND that `bypassPermissions` still executes a tool headlessly; an
autoupdater lock (`autoUpdates:false` / `DISABLE_AUTOUPDATER`, absent today).
**OUT:** the concurrency cap (M3); shadow/cutover (M4); deleting the tmux path (never).

## Locked decisions
- Channel = headless `--print` stream-json (NOT a non-`-p` mode — it doesn't exist; NOT the relay+subagent
  — proven worse). `bypassPermissions` is the minimum mode that executes tools headlessly.
- The new worker is **flag-gated OFF**; default execution stays on the tmux path until M4.
- Today's "stream-json" is the vendored wrapper's *synthesized* events; this moves to Anthropic's
  **native** `--print` schema — hence mandatory defensive parsing + conformance test.

## Open questions (prep + planner resolve)
- The exact native `--print` stream-json event schema across the pinned `claude` version — field names,
  all `rate_limit_event` window types (5-hour vs 7-day), `result` subtypes. **(prep target.)**
- **Safety boundary:** install `megaplan.runtime.sandbox` on the new path, OR document the OS-user
  boundary plainly? (Today the sandbox is only on the Hermes path; tmux Shannon is cwd-only.) Decide here.
- Whether `--input-format=stream-json` multi-turn-in-one-process or cross-process `--resume` is the better
  default for how megaplan phases drive turns.

## Constraints
- **Additive + flag-OFF**; the running engine never executes the new path during this milestone.
- Defensive parsing must never silently degrade to an empty/garbage `WorkerResult`.
- Epic invariants (vendor codex, execute pinned off Shannon, keep tmux, OS-user boundary).

## Done criteria
- A real phase runs end-to-end through `ShannonStreamWorker` *behind the flag* (off by default), producing
  a valid `WorkerResult` with `rate_limit` populated and a clean structured turn-end.
- The permission fail-fast watchdog converts a forced denial into a retryable fail in seconds (test).
- Liveness re-home: a long silent tool call is NOT false-killed (test).
- CI conformance smoke-test passes against the pinned binary and would fail loudly on a schema/permission
  break; autoupdater lock in place.

## Touchpoints
new `megaplan/workers/shannon_stream.py` (or similar); `megaplan/workers/_impl.py` (run_command liveness,
idle/hard-cap), `megaplan/workers/shannon.py` (session_roulette to port, env-scrub set,
`_make_shannon_liveness_probe`), `megaplan/runtime/process.py`, CI config for the conformance test.

## Rubric
Must: worker drives a real phase behind the flag; structured turn-end; permission fail-fast; liveness
re-homed; defensive parsing + conformance test + autoupdater lock; tmux untouched. Should: the
safety-boundary decision documented; multi-turn default chosen with rationale.
