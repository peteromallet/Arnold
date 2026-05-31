# Sprint B1 — Executor + schema prerequisites for YAML planning cutover

> **Superseded by [sprint-b-revised.md](sprint-b-revised.md).** The YAML
> runtime is dead. The schema, compiler, and YAML step kinds targeted by
> this brief were deleted in the cleanbreak (megaplan 0.22.0). Do NOT
> execute this brief.

## Goal

Land the executor-level and schema-level capabilities the YAML planning pipeline (Sprint B2) needs but cannot rely on today. Sprint B1's first draft underspecified the work — the three Codex reviews found additional schema gaps and infeasibilities. This revision includes them.

What B1 ships:

1. **Schema fixes** — make the 7 named handler escape-hatches representable; extend `PanelStepSpec.merge` to support `"structural"`; make typed override edges compilable.
2. **Shared `_run_parallel_stage` helper** consumed by both `run_pipeline` and `run_pipeline_with_policy` (without it, B1 duplicates bugs across both runners).
3. **`pre_handler` on ParallelStage** with `StepContext | StepResult | None` return semantics.
4. **`Verdict.override` dispatch in `run_pipeline_with_policy`** (extending the existing logic in `run_pipeline`).
5. **Executor-level parallel retry** on `parallel_fanout_unavailable`, plumbed into the worker call path so the error code can actually arise.
6. **`megaplan override accept-cache-hit` verb** — typed acknowledge-and-proceed for `cache_hit_suspected` errors. Without this, the no-op detector strands real plans.
7. **`megaplan runtime-audit` command** — scans plan roots, validates `pipeline_runtime` field, refuses unsafe-cutover conditions. Sprint B2's PR3 uses this.

No planning-pipeline migration in this sprint. Pure executor + schema + adjacent CLI work with clear interface specs. Sprint B2 consumes B1 as a foundation.

## Why this is a prerequisite

Sprint B's first attempt escalated at iter 33 ($747 spent) because the planner kept proposing solutions that the executor cannot support — and additionally, the schema cannot REPRESENT. Specifically (verified from current main):

- `PipelineSpec` has `extra="forbid"` (`schema.py:38-42`) and **no stage variant accepts a `handler:` field**. The seven named escape-hatches B2 needs literally cannot be expressed in YAML today.
- `PanelStepSpec.merge` is `Literal["none"] | None` (`schema.py:67-75`). B2 needs `"structural"` — schema gap.
- `Edge.kind="override"` exists in `types.py:78,101-105` but `_compile_edges` hardcodes `kind="normal"` for all edges (`compiler.py:235-262`). Typed override compilation is dead path.
- `parallel_fanout_unavailable` error code does not exist; no real worker throws anything matching it. Without plumbing into `panel.py:73-81`'s `_worker(...)` call, retry is dead code.
- `cache_hit_suspected` (from the cache-fix) raises a hard `CliError` with no recovery verb. Auto classifies it as generic `internal_error` (`auto.py:1251`). Real plans stranded.

These are foundation work. Doing them first makes Sprint B2 a clean cutover instead of a contradiction loop.

## Locked decisions

### Schema work (NEW — was missing from the first draft)

1. **Add `HandlerStepSpec`** to `megaplan/_pipeline/schema.py` — a stage variant accepting a `handler: str` field that names a callable from an explicit compile-time allowlist of seven entries: `handle_critique`, `_validate_tiebreaker`, `handle_gate`, `handle_execute`, `handle_review`, `handle_tiebreaker_decide`, `handle_override`. Compiler resolves the string to the callable; raises at compile time if name not in the allowlist. **Hard-coded allowlist, not configurable.** Adding an 8th name requires a code change + tracked ticket — that's the discipline.
2. **Extend `PanelStepSpec.merge`** to `Literal["none", "structural"] | None`. Default unchanged ("none"). When set to "structural": panel output merges follow `parallel_critique.py`'s ordered/disputed-wins semantics. The compiler wires this in `_make_join`.
3. **Update `_compile_edges`** in `megaplan/_pipeline/compiler.py:235-262` to emit `Edge(kind="override", recommendation=<override_value>)` for entries in a stage's `override_edges:` field. Normal edges keep `kind="normal"`. The compiler walk:
   - For each stage, read `override_edges:` from its spec (new field, optional).
   - Emit one `Edge(kind="override", ...)` per override target.
   - Existing normal-edge emission unchanged.
4. **Validation**: `override_edges` field is only valid on stages whose `produces:` is `verdict` (panel/gate steps that emit a verdict). Compiler raises a clear error otherwise.

### Executor work (revised — adds shared helper)

5. **Extract `_run_parallel_stage(node, ctx) -> StepResult`** into a private helper in `megaplan/_pipeline/executor.py`. Both `run_pipeline` (`executor.py:179-190`) and `run_pipeline_with_policy` (`executor.py:298-309`) call this helper instead of duplicating the fanout/join logic. The helper encapsulates `pre_handler` invocation, ThreadPoolExecutor submission, retry, and join. **Without this helper, B1 duplicates bugs across both runners.**
6. **`pre_handler` on `ParallelStage`** — `Optional[Callable[[StepContext], StepContext | StepResult | None]]`. Behavior:
   - `StepContext` returned → replaces `ctx` for the fanout
   - `StepResult` returned → **stage short-circuits**: no fanout, returned result is the stage output, state/output merge proceeds normally as if the stage ran
   - `None` → proceed unchanged with original `ctx`
   - Exception → stage fails fast (no fanout)
7. **Override dispatch in `run_pipeline_with_policy`** — `run_pipeline` (line ~219) already handles `Verdict.override`. B1 extends `run_pipeline_with_policy` (line ~336) to do the same. When the runner sees a `Verdict.override` value from a stage's output, it selects the matching `kind="override"` edge before falling through to normal `recommendation`-based edge selection.
8. **Executor parallel retry on `parallel_fanout_unavailable`** — when a step in `ParallelStage.steps` raises `CliError(code="parallel_fanout_unavailable")` (new code in `megaplan/types.py`), the helper catches it AT THE STAGE LEVEL and re-runs the failed step(s) **in-thread, sequentially** (no new ThreadPoolExecutor submission). **Other exception types are NOT retried.** Distinct failed steps retry independently in one sequential pass. Retry budget: **1 attempt per failed step, hardcoded**.
9. **Plumb `parallel_fanout_unavailable` into the worker call path.** In `megaplan/_pipeline/steps/panel.py` around line 73-81 (`_worker(...)` call), catch the existing worker error patterns (`worker_error`, `worker_timeout`, `worker_parse_error`) AND raise `parallel_fanout_unavailable` from this layer when the worker error matches a known fanout-unavailable signature. Specific signatures TBD during implementation; safer to start narrow (only `worker_timeout` with `concurrent_execution=True` context) and broaden later. **Without this plumbing, retry is dead code.**
10. **Per-step attempt artifacts** — each retry attempt writes a `<stage_id>/<reviewer_id>/v<n>_attempt<k>.json` artifact recording the attempt's input, model spec, session_id, duration, error code, and error message. Without these, operators see "stage failed" with no idea which step or why.

### CLI work (NEW — required for B2 safety)

11. **`megaplan override accept-cache-hit --plan <name>`** — new override verb. Marks the current `cache_hit_suspected` failure as acknowledged-and-accepted, sets state to allow the cached plan to advance (state ← `revised`), records the override in `state["meta"]["overrides"]` with a required `--reason` argument. Mirrors the shape of existing override verbs (`force-proceed`, `add-note`, etc.). Without this, a real `cache_hit_suspected` strands the plan with no clean recovery path.
12. **`megaplan runtime-audit [--plan <name> | --all] [--fail-on-unsafe-cutover]`** — new top-level command. Scans plan roots (or single plan), reports for each:
    - `pipeline_runtime` field value (or `null` if missing)
    - Current `state`/`current_state`
    - Whether `resume_cursor` references a YAML-only stage when `pipeline_runtime=legacy` (or vice versa)
    - Active `human_gate` pauses (paused indefinitely vs draining)
    - Whether the plan can resume safely on its recorded runtime

    With `--fail-on-unsafe-cutover`: exit non-zero if ANY non-terminal plan is unsafe. Sprint B2's PR3 invokes this as a pre-merge check.

### Backwards compatibility

13. Existing `ParallelStage` users that don't set `pre_handler` or whose steps never raise `parallel_fanout_unavailable` get exactly today's behavior. No silent semantics change.
14. Existing pipelines without `override_edges:` produce identical compiled `Pipeline` objects to today. The new edge kind only fires when explicitly used.

## Scope (in)

- `megaplan/_pipeline/schema.py` — add `HandlerStepSpec`, extend `PanelStepSpec.merge`, add `override_edges:` to relevant specs.
- `megaplan/_pipeline/compiler.py` — handle `HandlerStepSpec`, `merge: structural`, `kind="override"` emission.
- `megaplan/_pipeline/executor.py` — `_run_parallel_stage` helper, both runners use it.
- `megaplan/_pipeline/types.py` — `parallel_fanout_unavailable` code (or in `megaplan/types.py` alongside other `CliError` codes).
- `megaplan/_pipeline/steps/panel.py` — plumb new error code into worker error handling.
- `megaplan/_pipeline/pre_handlers.py` — new module with explicit allowlist of callable names.
- `megaplan/handlers/override.py` — add `accept-cache-hit` verb.
- `megaplan/cli.py` — wire `runtime-audit` command.
- `megaplan/audit/runtime.py` — new module implementing the audit logic (or extend existing audit module if a fit exists).
- Tests:
  - `_run_parallel_stage` covers pre_handler short-circuit, normal pass-through, retry-on-fanout-unavailable, retry-budget-exhaustion, terminal failure.
  - Override dispatch works in both runners; identical behavior.
  - `HandlerStepSpec` compile errors when name not in allowlist.
  - `merge: structural` produces ordered + disputed-wins output matching `parallel_critique.py`'s contract.
  - `accept-cache-hit` recovers a stranded plan; subsequent revise produces a new hash and the detector doesn't refire.
  - `runtime-audit` correctly classifies plans with missing/legacy/yaml runtime fields; `--fail-on-unsafe-cutover` exits non-zero appropriately.

## Scope (out — anti-scope)

- No planning pipeline migration; `megaplan/pipelines/planning/pipeline.yaml` stays parked.
- No new step kinds.
- No changes to `parallel_critique.py`.
- No changes to handler internals (`handle_critique`, `handle_gate`, etc.).
- No `--max-cost-usd` defaults.
- No skill auto-registration.
- **The fictional "timeout inheritance" sentence from the first draft is removed** — there is no stage-timeout layer to inherit from. Phase timeouts live at the auto-driver level; pre_handler and retries run within the same phase budget.

## Done criteria

1. Schema additions compile and validate as expected. Negative-test cases (unknown handler name, `merge: structural` on a non-panel step, `override_edges` on a non-verdict-producing stage) produce clear error messages.
2. `_run_parallel_stage` is the single source of truth for parallel-stage execution. `run_pipeline` and `run_pipeline_with_policy` are thin wrappers around it.
3. All 6 capability tests pass (pre_handler, override, retry, accept-cache-hit, runtime-audit, parity-of-runners).
4. Existing test suites (`tests/_pipeline/`, `tests/test_parallel_critique.py`, plus the cache-fix regression tests) all pass — no regressions.
5. `megaplan override accept-cache-hit` end-to-end smoke: manually trigger a `cache_hit_suspected`, run the override, confirm plan advances cleanly.
6. `megaplan runtime-audit --all` produces a clean report on the current repo state.

## Profile recommendation

`all-codex / full / high`. Apex is overkill for executor + schema refactoring with clear interface specs; codex:high is enough to handle the schema gymnastics. `full` robustness is enough for this confined-blast-radius work.

```bash
megaplan init .megaplan/briefs/yaml-pipelines-sprint-b1.md \
  --profile all-codex --depth high --robustness full \
  --auto-start --auto-approve \
  --in-worktree yaml-pipelines-b1 \
  --worktree-from main \
  --name yaml-pipelines-sprint-b1
```

## Sizing

~500-700 LOC of net new + changed production code (Codex's first review estimated 300-500 before the schema work was added). Plus ~400 LOC of tests. Above the original ~300-500 budget, but the schema work is non-negotiable — without it, B2 can't be built.
