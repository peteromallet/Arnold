# PhaseResult transport — explicit auto↔phase boundary

## Goal

Replace the implicit auto-driver ↔ phase-subprocess boundary with an **explicit, schema-validated `PhaseResult` transport**. Each phase handler writes `phase_result.json` atomically at exit; the auto driver reads *only* that file to decide what to do next. Stop inferring phase outcomes from a coincidence of exit codes, captured stdout, `state.json` history entries, and globbed batch artifacts.

## Authoritative spec

The architectural diagnosis at `docs/auto-execute-boundary-diagnosis.md` (already on disk in this repo) is the spec. Sections 4 and 5 of that doc define the required interface and the smallest-credible-refactor sequence. **Read that document first.** This brief intentionally does not re-derive its content.

## Why (the four bugs this prevents)

Four real bugs in one user session — `c0ebd3c6`, `eb4ac447`, `2c5bfb22`, plus an unfixed "truncated phase_progress_summary JSON" issue — all map to a single missing field on the wire. See diagnosis §3 (the four-row table). After this refactor:
- Bug 1 (`cli_provenance` field): persisted CLI args carried explicitly across subprocess rehydration. Existing fix stays.
- Bug 2 (`exit_kind` enum + structured `blocked_tasks`): no more prefix-matching free-text deviations.
- Bug 3 (`invocation_id`): cross-session vs within-session retry becomes an explicit decision based on an ID, not a heuristic.
- Bug 4 (`phase_result.json` as the read channel): stdout truncation stops mattering because the driver stops reading stdout for control flow.

## Decisions already locked (do not re-debate)

1. **Single canonical `phase_result.json`** per plan dir at a fixed relative path (e.g. `<plan_dir>/phase_result.json`). Last-writer-wins. Atomic write.
2. **All 8 phase handlers emit it**: plan, prep, critique, revise, gate, finalize, execute, review.
3. **Auto driver consumes ONLY `phase_result.json`** for its post-phase routing decisions. Delete the existing pathways that read stdout-tails, history entries, batch globs, and deviation prefix tables for retry classification. (Those paths may still exist for user-visible logging — but not for driver decisions.)
4. **Schema validated** via the existing `validate_payload` machinery, not a parallel one.
5. **Required fields**: `phase`, `invocation_id`, `exit_kind`, `blocked_tasks`, `deviations`, `artifacts_written`, `cli_provenance`. Each has a fixed schema (see diagnosis §4 for shape).
6. **`exit_kind` is an enum literal**, not free text: `success`, `blocked_by_quality`, `blocked_by_prereq`, `timeout`, `context_exhausted`, `internal_error`.
7. **Backwards-compatibility is not a goal**. Existing tests will update. Existing CLI surface stays identical.

## Scope

### 1. `megaplan/phase_result.py` (new module)

- `@dataclass(frozen=True) class PhaseResult` with the 7 required fields.
- `ExitKind` enum.
- `BlockedTask` and `Deviation` sub-dataclasses with explicit schemas.
- `atomic_write_phase_result(plan_dir: Path, result: PhaseResult) -> None` — write to `phase_result.json.tmp`, fsync, rename.
- `read_phase_result(plan_dir: Path) -> PhaseResult | None`.
- JSON schema integrated into `validate_payload` so phase emitters and the driver both validate against one source.
- `invocation_id` generation: ULID stamped at `set_active_step` time, persisted in `state["meta"]["current_invocation_id"]`, read by `_emit_phase_result` helper.

### 2. Phase handler exit-point integration

Every phase handler in `megaplan/handlers/` and `megaplan/execute/core.py` already has its `return StepResponse(...)` paths. For each one (success, blocked, CliError):
- Construct the appropriate `PhaseResult` from the `StepResponse` and current state.
- Call `atomic_write_phase_result(plan_dir, result)` before returning the StepResponse.
- Map existing failure modes onto `ExitKind`:
  - Quality-gate batch block → `blocked_by_quality`
  - Task-level `status="blocked"` → `blocked_by_prereq` (with `BlockedTask` entries surfacing executor notes)
  - Subprocess timeout → `timeout`
  - Context-window exhaustion → `context_exhausted`
  - Any other `CliError` → `internal_error`

Eight handlers: plan, prep, critique, revise, gate, finalize, execute, review. Mechanical pass.

### 3. Auto-driver consumption

In `megaplan/auto.py`, replace the post-phase decision logic:

**Delete (or restrict to logging-only)**:
- `_last_history_step_result(plan_dir, phase)`
- `_read_execute_blocked_task_notes(plan_dir)`
- `_read_execute_blocking_deviations(plan_dir)`
- The `blocking_prefixes` string-match table at lines ~393-398
- The `blocked_task_notes = _read_execute_blocked_task_notes(...)` branch and the chained `_read_execute_blocking_deviations` path at lines ~1366-1411

**Replace with**: a single `read_phase_result(plan_dir)` call after each phase subprocess returns, switching on `result.exit_kind`:
- `success` → continue
- `blocked_by_quality` → existing retry-with-cap behavior (use `result.deviations` directly, no string match)
- `blocked_by_prereq` → exit `awaiting_human` (use `result.blocked_tasks` directly, no batch globbing)
- `timeout` / `context_exhausted` → existing recovery paths
- `internal_error` → existing failure path

### 4. Tests

- Unit tests for `PhaseResult` (round-trip, schema validation, missing-fields error).
- Update existing handler tests to assert `phase_result.json` is written with the right `exit_kind`.
- Update auto-driver tests to drive scenarios via a synthesized `phase_result.json` rather than by mocking history/batch artifacts.
- **Regression tests for the four bugs**:
  - Bug 1: `cli_provenance` field round-trips across a simulated subprocess hop.
  - Bug 2: a `blocked_by_prereq` result routes to `awaiting_human` without consulting any free-text deviation string.
  - Bug 3: cross-session retry is identified by `invocation_id`, not by mutable disk state.
  - Bug 4: auto driver decisions are independent of stdout content (test could pass a corrupted stdout payload while a valid `phase_result.json` exists, and assert correct routing).

### 5. Verification

After the refactor lands and the new megaplan code is committed, re-run megaplan auto on the existing brain-of-bndc plan:

```
cd /Users/peteromalley/Documents/banodoco-workspace/brain-of-bndc
megaplan auto --plan live-update-environment-split \
  --outcome-file /tmp/megaplan-out/live-update-environment-split.outcome.v5.json \
  --phase-timeout 5400 --phase-idle-timeout 1200 --max-iterations 200
```

`.env` already has `DEV_LIVE_UPDATE_CHANNEL_ID`. The new auto driver should:
1. Reset T10 → pending via the prior `--retry-blocked-tasks` flag (still works).
2. Invoke execute. Executor runs, writes `phase_result.json` with `exit_kind="success"` (or `blocked_by_prereq` for some other reason, which would be surfaced cleanly).
3. Auto driver reads `phase_result.json`, sees success, proceeds to T1-T9.
4. The four-bug class of regressions is empirically ruled out.

## Out of scope

- Fixing the stdout-mixing problem (Bug 4 root cause). The driver stops reading stdout for control; that's enough.
- The full rehydration-cursor refactor described in diagnosis §5 (Bug 1 mitigation via `cli_provenance` is sufficient).
- Adding new phases, robustness levels, profile entries.
- Changing the subprocess transport itself (still `subprocess.run`).
- Refactoring chain.py's `on_phase_complete` callback. (Note in diagnosis §6 — separate smell, separate work.)
- Backfilling `phase_result.json` for in-flight plans created before this refactor.

## Acceptance criteria

1. `phase_result.json` exists at `<plan_dir>/phase_result.json` after every phase exit (success, blocked, error), validated against a shared schema.
2. **Audit pass — every auto-driver retry-classification decision reads `phase_result.json` and nothing else.** A grep through `auto.py` confirms no decision path reads `state["history"]`, globs `execution_batch_*.json`, tails captured stdout, or prefix-matches deviation strings. *Load-bearing correctness check.*
3. All 8 phase handlers call `atomic_write_phase_result` at every exit point.
4. Regression tests for the four bug classes pass.
5. Full test suite passes (modulo the two pre-existing unrelated failures: `test_validate_critique_checks_rejects_light_mode_stray_checks`, `test_handle_plan_failure_clears_active_step`).
6. **End-to-end verification**: megaplan auto runs on the brain-of-bndc plan and progresses past T10 (executor runs against the now-populated `.env`, a fresh execution batch is written, T10 transitions to `done`, T1 begins).

## Pointers

- Diagnosis doc: `docs/auto-execute-boundary-diagnosis.md` (the spec).
- Existing schema-validation utility: `validate_payload` (grep for the import; reuse don't reinvent).
- Existing atomic-write helper: `atomic_write_json` (already used at `execute/core.py:637`).
- ULID/UUID source: check if megaplan already has one (likely in `utils.py` or similar); add if missing, don't pull a heavy dependency.
- Active step lifecycle: `set_active_step` / `clear_active_step` in `handlers/execute.py:100,130,133` — `invocation_id` stamping fits naturally here.
- Brain-of-bndc plan for verification: `/Users/peteromalley/Documents/banodoco-workspace/brain-of-bndc/.megaplan/plans/live-update-environment-split/`.
