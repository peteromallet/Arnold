# M5b — Decompose session.py + Fix Error Architecture

## Outcome
`vibecomfy/runtime/session.py` is split from a 1379-line god-class into cohesive modules,
and the run hot path raises typed `VibeComfyError`s with `next_action` instead of bare
`RuntimeError`s. Split out from the old combined M5 (the emitter half is now M5a) because
this half depends on **M4**, not M2 alone.

## Dependency note
**Depends on M4** — confirmed real: M4 extracts the `queue_prompt → _wait_for_server_history
→ _outputs_from_server_history` sequence that currently lives *inside* `session.py`
(`ServerSession._run_untracked` and the polling/output helpers). Splitting session before
M4 would mean carving up code M4 then rewrites. Run after M4.

## Problem (audit lenses 5 & 6)
- **`session.py` — 1379 LOC god-class.** Bundles `EmbeddedSession`, `ServerSession`,
  `SessionConfig`, `RunResult`, server spawning (`_spawn_comfy_server`), prompt prep,
  schema validation, history polling, output collection, metadata gen, model
  fingerprinting, watchdog lifecycle, and session discovery (`active_session_metadata`,
  `find_active_session`). `_on_schema_unavailable` is duplicated verbatim across the two
  session classes.
- **Error architecture not followed.** CLAUDE.md states all errors extend
  `VibeComfyError(RuntimeError)` with optional `next_action`, yet `session.py` raises 9+
  **bare `RuntimeError`s** (lines ~230, 240, 257, 264, 399, 456, 592, 607, 611) on the
  execution hot path, reaching users as `"run failed: ..."` with no remediation hint.
  Also: `errors.py:27` formats `next_action` with no separator (run-on sentence); the
  `_prepare_prompt` catch-alls (`session.py:855, 886`) wrap into fresh `RuntimeError`,
  **stripping any `next_action`** a caught `VibeComfyError` carried.

## Scope
1. **Split `session.py`** into cohesive modules — separate session lifecycle, server
   management (`_spawn_comfy_server`), prompt orchestration, and session discovery.
   Extract the duplicated `_on_schema_unavailable` into one place. Delegate
   queue/wait/outputs to M4's shared helper rather than re-implementing.
2. **Fix the run-path error architecture:** replace the bare `RuntimeError`s with
   appropriate `VibeComfyError` subclasses carrying actionable `next_action` strings.
   Make `_prepare_prompt` catch-alls **preserve** a caught `VibeComfyError`'s
   `next_action` instead of discarding it. Fix the `errors.py:27` separator. Make the CLI
   catch (`commands/run.py:163`) also handle `SyntaxError` from a broken scratchpad import
   gracefully.

## Locked decisions
- **Behavior-preserving** for run behavior and exit codes. Error-message *text* may
  change (adding `next_action`), but the CLI catch-tuple contract and exit codes stay
  stable.
- Build on M4's shared queue/wait helper; do not re-introduce a local copy.

## Done criteria
- No single session module exceeds ~600 LOC; `_on_schema_unavailable` defined once.
- No bare `RuntimeError` on the session run path; each carries a typed class +
  `next_action`. A test asserts `next_action` survives `_prepare_prompt`.
- The M1 golden gate passes in full; `run` and `runtime eval-node` CLI smoke pass.
- Full `pytest` green.

## Touchpoints
`vibecomfy/runtime/session.py` (+ new sibling modules under `vibecomfy/runtime/`),
`vibecomfy/errors.py`, `vibecomfy/commands/run.py`, `vibecomfy/runtime/{run,watchdog}.py`,
tests under `tests/`.

## Anti-scope
Do not touch `emitter.py` (M5a). Do not re-open validation (M3) or eval/diagnostics (M4).
No user-facing doc edits (M7) beyond docstrings on the new modules.
