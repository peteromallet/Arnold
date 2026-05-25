# Sprint 4 — Toward elegance

Two weeks to retire the shims, collapse to one runtime, and finish the
kind taxonomy. Starting state: Sprint 1-3 shipped primitives, demos,
parity tests, prompt registry, profile binding, the planning Pipeline
derived from a single shared data module, and an in-process / subprocess
shim pair for handlers. The four honest caveats from the elegance audit:

1. HandlerStep is a subprocess shim — not a real port.
2. Edge labels carry encoded data (`gate_iterate:revise` packs two
   fields into a string).
3. Two runtimes co-exist — `auto.py` still polls `WORKFLOW` instead of
   walking the `Pipeline`.
4. `subloop` and `override` kinds are declared on the Step Literal but
   the executor has no branch for them.

This sprint addresses all four.

## Goal

After Sprint 4: zero shims, one runtime, typed edges, full kind
taxonomy. The Pipeline IS the planning state machine — not a derived
view of it.

## Out of scope

- New planning features (handlers stay behaviorally identical).
- New profile slot keys (TOML schema unchanged).
- Cloud orchestrator, Hermes worker, resident scheduler, Discord/Railway
  runner — none touched.

## Operating principles (same as v2 brief)

- No human review or approval gates.
- Mandatory artifact-based checkpoints at the end of each chunk.
- Blockers get overcome via fallback paths; >2 attempts → `BLOCKER-<n>.md`.
- Live `megaplan` (system shebang) must keep working — verified after
  every commit.
- All work in the same worktree (`/Users/peteromalley/Documents/megaplan-decomp`)
  on `decomp/main`. No new branches.

## Week 1 — Typed verdicts + real handler ports

### Chunk A (Days 1–2): Typed verdict + typed edges

**Problem:** `Edge.label="gate_iterate:revise"` is a string that
encodes `(condition, next_step)`. `Verdict.recommendation` doesn't
exist — gate stores its decision in a JSON file and the matching
edge is found by string compare.

**Deliverable:**

- Add `GateRecommendation = Literal["proceed", "iterate", "tiebreaker",
  "escalate"]` and `OverrideAction = Literal["force_proceed", "abort",
  "replan", "add_note"]` to `megaplan/_pipeline/types.py`.
- Extend `Verdict` with `recommendation: GateRecommendation | None`
  and `override: OverrideAction | None`.
- Add `EdgeKind = Literal["normal", "gate", "override"]` and either
  refactor `Edge` to a tagged variant or add `Edge.kind` + `Edge.match`
  to support matching on `Verdict.recommendation` instead of label
  string compare.
- Update `_pipeline/planning.py::_edges_from_transitions` to emit
  typed edges (no more `"gate_iterate:revise"` strings).
- Update the executor's edge-dispatch to match on `Verdict.recommendation`
  when `edge.kind == "gate"`.
- Migrate the existing tests and demos to the typed shape. Tests
  that hand-construct `Edge(label="to_revise", target="revise")`
  keep the `label=` form for `kind="normal"` edges.

**Acceptance:** All Sprint 1-3 tests pass with the typed-edge
shape. New `tests/test_pipeline_typed_edges.py` asserts the
encoded-string form is gone (grep test) and that
`Verdict.recommendation` propagates through the gate.

### Chunk B (Days 3–5): Real handler ports

**Problem:** `HandlerStep` shells out via subprocess.
`InProcessHandlerStep` wraps `handle_<phase>(root, args)` but still
threads through the legacy argparse Namespace and StepResponse dict.

**Deliverable:**

- For each handler in `megaplan/handlers/`, extract the worker
  dispatch + prompt resolution into a `Step.run` body that returns a
  typed `StepResult` directly. No subprocess. No Namespace.
- New per-handler files under `megaplan/_pipeline/stages/`:
  `prep.py`, `plan.py`, `critique.py`, `gate.py`, `revise.py`,
  `finalize.py`, `execute.py`, `review.py`.
- Each ported Step reads its inputs from `ctx.inputs` (typed) and
  writes its outputs by returning a `StepResult` whose `outputs`
  dict carries `{label: Path}` pairs. The Step never touches
  `state.json` directly — that's the executor's job.
- The legacy `handle_<phase>` CLI entrypoints become thin shims that
  build a single-stage Pipeline + run it via the executor — the
  inverse of today's setup.

**Acceptance:** `tests/test_legacy_phase_cli_compat.py` still
passes (the CLI surface is preserved through the inverted shim).
`tests/test_pipeline_planning_e2e.py` still produces the same
artifacts. New `tests/test_handler_ports.py` exercises each new
Step in isolation (mock workers, hermetic).

## Week 2 — One runtime, full taxonomy

### Chunk C (Days 6–8): `auto.py` walks the Pipeline

**Problem:** `auto.py` has ~1700 LOC of phase-polling logic against
`WORKFLOW`. The Pipeline executor doesn't know about stall detection,
cost caps, `--max-iterations`, `--max-context-retries`, escalate
policy, etc.

**Deliverable:**

- Extract the policy machinery from `auto.py` into a
  `megaplan/_pipeline/runtime.py` module with classes/functions for:
  `StallDetector`, `CostTracker`, `EscalatePolicy`, `ContextRetry`,
  `BlockedRetry`. Each has a clean dependency on the Pipeline
  executor's per-stage events.
- `megaplan/_pipeline/executor.py` grows a `run_pipeline_with_policy`
  variant that takes the runtime modules + a Pipeline + a
  StepContext. The bare `run_pipeline` stays for hermetic demos.
- `auto.py`'s phase loop becomes a thin wrapper around
  `run_pipeline_with_policy` — preserve every existing CLI flag's
  semantics.

**Acceptance:** Every existing `tests/test_auto*.py` test passes
unchanged. `tests/test_init_plan.py::test_workflow_mock_end_to_end`
still produces the same artifacts. New
`tests/test_auto_pipeline_runtime.py` exercises the policy modules
in isolation. `megaplan auto --plan <name>` on a real mock plan
produces byte-identical artifacts pre/post migration (parametric
across the 5 robustness levels).

### Chunk D (Days 9–10): `subloop` + `override` primitives

**Problem:** `subloop`/`override` are reserved Step kinds with no
executor branch. Tiebreaker is still two regular stages
(`tiebreaker_pending` → `tiebreaker_ready`). Override is still a CLI
escape hatch outside the state machine.

**Deliverable:**

- Executor branch on `step.kind == "subloop"`: the Step is expected
  to carry a nested `Pipeline` in a new field; `run` builds a child
  StepContext and calls `run_pipeline` recursively. The child's
  final state becomes a Verdict on the parent.
- Refactor `tiebreaker_run` + `tiebreaker_decide` into a single
  `TiebreakerSubloop` Step whose nested Pipeline has the
  researcher → challenger → synthesis edges.
- Executor branch on `step.kind == "override"`: any Stage can carry
  an `override_edges: tuple[Edge, ...]` that the executor evaluates
  before the normal `edges` set whenever a Verdict carries an
  `override` recommendation. This makes "override force-proceed"
  an edge, not a side-effecting CLI subcommand.

**Acceptance:** `tests/test_pipeline_subloop.py` and
`tests/test_pipeline_override.py` exercise both kinds with
hermetic demos. Existing tiebreaker tests
(`tests/test_tiebreaker_*`) still pass. The state-machine no
longer routes through `tiebreaker_pending` /
`tiebreaker_ready` — those states are gone.

### Chunk E (Days 11–12): Delete `WORKFLOW`

**Problem:** Even after `auto.py` walks the Pipeline, the
`WORKFLOW` dict in `_core/workflow_data.py` is consulted by
`_workflow_for_robustness` to compute robustness overlays. The
Pipeline + Overlays should be the only source.

**Deliverable:**

- Rewrite `_workflow_for_robustness` to derive its return shape
  from `compile_pipeline_for(robustness, ...)`. The function name
  stays (back-compat) but the body reads from the Pipeline.
- Mark `WORKFLOW` and `_ROBUSTNESS_OVERRIDES` in
  `_core/workflow_data.py` as `_LEGACY_*` shims that build their
  dicts by reverse-deriving from the Pipeline. Then schedule them
  for deletion in a follow-up sprint once consumers migrate.
- Delete `_core/workflow_data.py` entirely if all consumers
  (legacy workflow.py + the Pipeline compilation) are pure consumers
  of the Pipeline value.

**Acceptance:** `tests/test_pipeline_planning_parity.py` still
passes — but in the inverted direction: the Pipeline is the source,
the legacy dicts are the derived view. `git grep -nw WORKFLOW
megaplan/` shows only re-export sites + the parity tests.

### Chunk F (Days 13–14): Polish + docs + release

**Deliverable:**

- `docs/pipeline-architecture.md` — the elegance writeup. Diagrams
  for: primitive surface, mode dispatch, profile binding,
  three-axis composition, runtime layering.
- Update `docs/pipeline-resume.md` to reflect the typed-edge shape.
- Update `briefs/STATUS.md` — Sprint 4 entries.
- Final full-suite run. Tag commit on `decomp/main` as `v0.21.0`.
- Cut a PR from `decomp/main` → `main` for review.

## Acceptance — Sprint 4 as a whole

After this sprint, the four honest caveats are closed:

1. **No subprocess shims.** Every Step is a real port; `HandlerStep`
   subprocess path is gone (or kept only as a remote-execution
   primitive for future cloud work).
2. **Typed edges.** `Edge.label="gate_iterate:revise"` is gone.
   Matching happens on typed Verdict fields.
3. **One runtime.** `auto.py` walks the Pipeline. The legacy
   `_workflow_for_robustness` reads from the Pipeline, not from a
   parallel dict.
4. **Full kind taxonomy.** `subloop` and `override` have executor
   branches; tiebreaker is a Subloop; override is an escape edge.

## Risk profile

- **auto.py is 1700 LOC and runs production plans.** Migration risk
  is high. Mitigation: keep both runtimes during migration, gated by
  `MEGAPLAN_PIPELINE_AUTO=1` env var. Default flips to Pipeline on
  Day 12 after a week of byte-identical parity in CI.
- **Tiebreaker migration touches state-machine state names** (the
  `tiebreaker_pending` / `tiebreaker_ready` states go away). Plans
  with persisted state in those names need migration. Mitigation:
  state-migration helper in `_pipeline/migrate.py` that runs
  automatically on plan load.
- **Profile slot resolution** might surface mismatches if a Step's
  `slot` doesn't appear in a profile TOML. Mitigation:
  `Profile.model_for` already raises with a clear message; add a
  `compile_pipeline_for` pre-flight that asserts every Step's slot
  is resolvable in the active Profile.

## Robustness recommendation

Sprint 4 is kernel-invariant work — `--robustness robust` minimum;
`superrobust` for Chunk C (auto.py rewrite). Profile `all-claude`,
depth `high`. Two megaplan invocations: one for Week 1 (Chunks A+B),
one for Week 2 (Chunks C+D+E+F).

## Definition of done

- All Sprint 1-3 tests still pass (no regressions).
- 5 new elegance-property tests pass:
  - `test_no_subprocess_shims_in_production_path` — grep-based
  - `test_no_string_packed_edge_labels` — grep-based
  - `test_auto_walks_pipeline` — checks `auto.py` imports + uses
    `run_pipeline_with_policy`
  - `test_subloop_and_override_have_executor_branches` —
    introspects executor source
  - `test_workflow_dict_derived_from_pipeline` — asserts the
    inversion
- Full `pytest tests/` stays green (excluding the known main flake).
- Live `megaplan` (system shebang) still resolves to main checkout.
- `briefs/STATUS.md` reflects Sprint 4 complete with commit ledger.
