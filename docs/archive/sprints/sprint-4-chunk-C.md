# Sprint 4 Chunk C — `auto.py` walks the Pipeline

Full Sprint-4 plan at `.megaplan/briefs/sprint-4-elegance.md`. Chunk C follows
Chunks A (typed edges) and B (real handler ports).

## Problem

Today `megaplan/auto.py` is ~1700 LOC of phase-polling logic against
the legacy `WORKFLOW` dict. The Pipeline executor doesn't know about
stall detection, cost caps, `--max-iterations`, `--max-context-retries`,
escalate policy, etc. There are two runtimes.

## What ships in Chunk C

1. **Extract policy modules** from `auto.py` into
   `megaplan/_pipeline/runtime.py`:
   - `StallDetector` — tracks state changes + review.json writes.
   - `CostTracker` — sums `meta.total_cost_usd`, raises at cap.
   - `EscalatePolicy` — implements `--on-escalate force-proceed|abort|fail`.
   - `ContextRetry` — fresh-execute retries on context exhaustion.
   - `BlockedRetry` — re-runs execute on result=blocked, capped.

2. **Pipeline-aware runtime entry point** in
   `megaplan/_pipeline/executor.py`:
   `run_pipeline_with_policy(pipeline, ctx, *, artifact_root, policy)`
   takes a `RuntimePolicy` bundling the modules above + per-stage
   event hooks. The bare `run_pipeline` stays for hermetic demos.

3. **`auto.py`'s phase loop** becomes a thin wrapper around
   `run_pipeline_with_policy`. Every existing CLI flag's semantics
   are preserved bit-for-bit:
   - `--stall-threshold`
   - `--max-iterations`
   - `--max-review-rework-cycles`
   - `--max-cost-usd`
   - `--max-context-retries`
   - `--max-blocked-retries`
   - `--max-add-note-attempts`
   - `--on-escalate`
   - `--poll-sleep`
   - `--phase-timeout`
   - `--phase-idle-timeout`
   - `--work-dir`
   - `--status-timeout`
   - `--outcome-file`

4. **Migration gate** via `MEGAPLAN_PIPELINE_AUTO` env var. When set
   to `"1"`, `auto.py` uses the new Pipeline runtime; otherwise the
   legacy loop. Default is legacy through this chunk; default flips
   to Pipeline in Chunk E (after parity has held for two chunks).

## Out of scope

- Subloop / override executor branches (Chunk D).
- Deleting WORKFLOW (Chunk E).
- Polish + docs (Chunk F).

## Constraints

- Every existing `tests/test_auto*.py` test must pass unchanged.
- `tests/test_init_plan.py::test_workflow_mock_end_to_end` must
  produce the same artifacts.
- Live `megaplan` must keep working.
- All commits on `decomp/main`.

## Acceptance

- New `tests/test_auto_pipeline_runtime.py` exercises each of the 5
  policy modules in isolation (mock workers).
- New `tests/test_auto_pipeline_parity.py` runs `megaplan auto` on
  a fixture plan with `MEGAPLAN_PIPELINE_AUTO=1` and asserts
  byte-identical artifacts against an unset run. Parametrized over
  the 5 robustness levels.
- All existing auto tests pass with the env var unset (legacy path
  preserved).
- All existing auto tests pass with `MEGAPLAN_PIPELINE_AUTO=1` (new
  path matches behaviour).
- Full `pytest tests/` stays green.

## Operating principles

Same as Chunks A + B. **No env-var-based regressions** — when the
env var is unset the legacy code path must be byte-identical to
pre-Chunk-C behaviour. When the env var is set the new path must
produce the same artifacts as the legacy path.
