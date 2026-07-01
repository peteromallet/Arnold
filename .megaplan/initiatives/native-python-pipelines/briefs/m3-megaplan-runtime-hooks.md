# Milestone 3 — Megaplan-specific native runtime hooks

## Outcome

The native runtime understands Megaplan semantics: state merge, override injection, step-IO policy, envelope joining, subloop promotion/suspension-lift, and loop-condition guards. A Megaplan-shaped toy pipeline exercises all of these and produces byte-compatible persistence shapes.

## Scope (IN)

- `arnold.pipelines.megaplan.native_hooks` module implementing:
  - `merge_state` / executor-key-merge and `_state_meta` CAS semantics.
  - Override injection from `state["meta"]["overrides"]` and the operation catalog (`planning.operations.override_catalog()`), with CLI spelling normalization (`routing.cli_to_internal_override()`).
  - Megaplan step-IO policy adapter (`resolve_megaplan_step_io_policy()`) wired into native handoff validation.
  - Envelope joining and trust-state handling.
  - Subloop promotion and suspension-lift semantics via `run_subpipeline(...)` child frames.
  - Loop-condition guards and `should_halt_loop` policy.
- Native runtime hook points (`NativeRuntimeHooks`) for `on_phase_start`, `on_phase_end`, `on_phase_error`, `merge_state`, `should_suspend`, `should_halt_loop`, `on_handoff`, `on_checkpoint`.
- A Megaplan-shaped toy native pipeline covering:
  - a decision vocabulary with override,
  - a guarded loop,
  - a nested subpipeline that promotes state back to the parent,
  - a suspension/resume cycle.
- Parity tests comparing the toy pipeline's native traces to a reference graph-executor run (or to the known M2 corpus if a direct graph equivalent exists).

## Scope (OUT)

- Conversion of the main `megaplan` pipeline.
- Conversion of any other real production pipeline.
- `parallel(...)` primitive and panel/human-gate support.
- Flipping the default execution mode.
- Graph-builder removal.

## Locked decisions

- Overrides are intercepted before a `@decision` body runs and routed through `verdict.override` so resolver priority matches `resolve_edge`: halt, override, decision, normal.
- State merge uses executor-key-merge with `_state_meta` CAS, exactly as the graph executor does today.
- Subloops create isolated child frames; only promoted results cross back to the parent; suspended children produce a composite parent cursor.
- Loop position is stored in `loop_counters` and checkpoint IDs, not inferred from stage names.

## Open questions

- Which Megaplan state keys are owned by the executor vs. by phase bodies? Need an explicit key-ownership map for native `executor_owned_keys`.
- How does the native runtime emit `override_applied` events exactly as existing observability helpers do today?
- What is the minimal set of `RuntimeEnvelope` fields that must be joined after a subloop completes?
- Should loop-condition guards be declared as decorator metadata, as runtime policy hooks, or both?

## Constraints

- Must not break existing tests or in-flight plans.
- Must run behind the existing feature flag.
- Must produce byte-compatible persistence shapes where exercised.
- Must reuse existing helpers: `write_plan_state`, `fold_journal`, `last_state_snapshot_projector`, `emit_state_written`, `EventKind` enumeration.

## Done criteria

- `arnold.pipelines.megaplan.native_hooks` exists and is importable.
- Toy Megaplan-shaped native pipeline compiles, validates, runs, resumes, and suspends correctly.
- Override injection skips decision bodies for true control overrides and leaves additive overrides (`add-note`, `set-model`) as state/config mutations.
- Subloop promotion writes the expected `subloop:<name>:state`, `subloop:<name>:recommendation`, and optional `subloop:<name>:resume_cursor` keys.
- Suspended subloops produce a composite parent cursor with the correct child frame stack.
- Native event/state/cursor output matches the reference traces.
- All existing tests still pass.
- Milestone 4 handoff documents the exact integration points for the main `megaplan` pipeline.

## Touchpoints

- `arnold/pipeline/native/runtime.py` (hook integration)
- `arnold/pipeline/native/context.py` (frame stack, child frames)
- `arnold/pipeline/native/checkpoint.py` (composite cursor serialization)
- `arnold/pipeline/native/contracts.py` (step-IO policy adapter)
- `arnold/pipelines/megaplan/native_hooks.py` (new)
- `arnold/pipelines/megaplan/pipeline.py` (read-only reference for semantics)
- `arnold/pipelines/megaplan/planning/operations.py` (override catalog)
- `arnold/pipelines/megaplan/routing.py` (CLI override spelling)
- `arnold/runtime/envelope.py` (`RuntimeEnvelope`, join algebra)
- `tests/arnold/pipeline/native/test_megaplan_hooks.py` (new)

## Anti-scope

- Do not rewrite the main `megaplan` pipeline function yet.
- Do not add `parallel(...)` or human-gate suspension here.
- Do not change the default execution mode.
- Do not remove graph builders.
