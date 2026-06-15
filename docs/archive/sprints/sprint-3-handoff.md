# Sprint 3 — handoff brief

Sprint 1 + Sprint 2 of the megaplan decomposition refactor shipped on
branch `decomp/main`. This doc captures the scope deliberately deferred
from those two sprints so a future Sprint 3 can pick it up without
re-deriving context.

## Background

Sprints 1 + 2 landed:

- The frozen primitive surface (`megaplan/_pipeline/types.py`) — Step,
  Stage, Pipeline, Edge, Overlay, ParallelStage, StepContext,
  StepResult, Verdict. All `@dataclass(frozen=True)` plus a
  `@runtime_checkable Protocol` for Step.
- A standalone Sprint-1 executor (`megaplan/_pipeline/executor.py`)
  that walks a Pipeline, dispatches Steps, applies state patches,
  verifies declared outputs, and follows labelled edges.
- Three working demos: fan-out judges (parallel + barrier-join),
  4-stage compose, doc-critique 3x loop.
- A compiled planning Pipeline (`megaplan/_pipeline/planning.py`)
  derived from `megaplan/_core/workflow.py::WORKFLOW` plus three
  composing Overlays: robustness, with_prep, with_feedback.
- 33 new pipeline tests, all green. Full `pytest tests/` suite (1740
  tests) stays green; live `megaplan` binary keeps resolving to the
  main checkout.

What Sprint 3 picks up: turn the compiled-view-of-WORKFLOW into the
single source of truth, port real handlers into Steps, rewrite
`auto.py` to walk the Pipeline, and ship the two remaining acceptance
tests (#1 byte-identical parity and #5 kill-mid-run resume).

## Scope

### 1. Handler → Step port

Replace `_RuntimeStep` placeholders in
`megaplan/_pipeline/planning.py` with real Step implementations. One
Step per file under a new `megaplan/_pipeline/stages/` package:

- `stages/prep.py` (Produce) — wraps `megaplan/handlers/prep` logic.
- `stages/plan.py` (Produce).
- `stages/critique.py` (Judge).
- `stages/gate.py` (Decide).
- `stages/revise.py` (Produce).
- `stages/finalize.py` (Produce).
- `stages/execute.py` (Produce).
- `stages/review.py` (Judge).
- `stages/tiebreaker.py` (Subloop — Sprint-3 introduces the real
  subloop branch in the executor).
- `stages/override.py` (Override — Sprint-3 adds the escape-edge
  branch in the executor).

Each Step.run wraps the matching `handle_*` function with the
phase_result_guard, slot resolution, prompt-mode dispatch, and
session-management logic that lives inside the handler today. Pass a
real `BudgetRef` and `Profile` through `StepContext` instead of the
Sprint-1 `Any` placeholders.

### 2. Executor → auto.py integration

Move the pipeline runtime into `megaplan/auto.py` so the auto driver
walks the Pipeline instead of polling `WORKFLOW`. Preserve every
existing flag:
`--stall-threshold`, `--max-iterations`, `--max-review-rework-cycles`,
`--max-cost-usd`, `--max-context-retries`, `--max-blocked-retries`,
`--max-add-note-attempts`, `--on-escalate`, `--poll-sleep`,
`--phase-timeout`, `--phase-idle-timeout`, `--work-dir`,
`--status-timeout`, `--outcome-file`.

Stall detection, cost cap, context-retry, escalate-policy: bit-for-bit
preserved. The Pipeline executor lives **inside** auto.py — it
replaces the phase-polling loop, not the policy machinery.

### 3. Delete WORKFLOW

Once every reader consumes the Pipeline instead of `WORKFLOW`:

- Delete `WORKFLOW` and `_ROBUSTNESS_OVERRIDES` from
  `megaplan/_core/workflow.py`.
- Rewire `_RESUME_ACTIVE_STATES` (line 361 today) to be derived from
  the Pipeline via the `derive_resume_active_states(pipeline)` snippet
  in `docs/pipeline-resume.md`.
- Keep `is_valid_transition` and the state-name constants as Pipeline
  helpers.

### 4. Acceptance tests #1 + #5

- `tests/test_pipeline_parity.py` — byte-identical artifacts on a
  fixture idea pre/post refactor. Requires the handler port +
  auto.py integration; structural parity already shipped.
- `tests/test_pipeline_resume.py` — kill `megaplan auto` mid-run,
  resume, assert final artifacts identical to uninterrupted run.
  Requires the executor inside auto.py with the resume_cursor
  contract.

### 5. ParallelStage for parallel_critique

Today `parallel_critique` is hard-coded inside `handle_critique`.
Sprint 3 expresses it as a `ParallelStage` in the planning Pipeline
when the profile/robustness combination enables it. Demonstrates the
fan-out primitive on a real planning flow, not just the demo.

## Operating principles (carry over from v2 brief)

- No human review or approval gates. Self-validating tests are the
  only gate.
- Mandatory artifact-based checkpoints at the end of each handler-port
  commit: full test suite + parity fixture + live-megaplan smoke +
  commit.
- Blockers get overcome via fallback paths; >2 attempts →
  `BLOCKER-<n>.md` + keep going.
- Live megaplan must keep working: system shebang must keep resolving
  to the main checkout. Verify after every commit.
- Worktree-isolated. Dedicated venv `.venv-decomp`.

## Known footguns (carry over from Sprint 1 experience)

- **Persistent-session response caching:** robust-mode megaplan
  invocations re-use the same Claude session across iterations and
  cached responses repeat. Sprint 1's gate→revise loop spent $11 in
  iteration churn before the force-proceed override broke out. For
  Sprint 3 megaplans, consider `--ephemeral` or per-phase
  `--phase-model` overrides that vary the session key.
- **Prose-prefixed JSON:** Claude occasionally prefaces structured JSON
  output with a sentence. The two parser fixes from Sprint 1
  (`megaplan/workers.py` and `megaplan/shannon_worker.py`) handle this.
  Any new payload-parsing path in Sprint 3 should call those same
  extraction helpers, not bare `json.loads`.

## Robustness recommendation

Sprint 3's surface area is much larger than Sprint 1/2 (handler port +
auto.py rewrite). Either:

- `--robustness superrobust` for the planning megaplan, or
- Two smaller megaplans: one for the handler port, one for auto.py.
  Each at `--robustness robust`. The second consumes the first's
  final.md as its `--from-doc` settled decisions.

Profile stays `all-claude` and depth stays `high`.

## Out of scope (still)

- Cloud orchestrator changes (`megaplan/cloud/`).
- Hermes worker / chain runtime changes.
- Resident scheduler.
- Profile TOML schema changes (slot names locked).
- `--vendor` / `--critic` / `--depth` flag semantics changes.
