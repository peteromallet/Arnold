# Arnold Clean Extraction Port Ledger

This branch starts from `origin/main` and ports quarry work selectively. It must
not merge `arnold-generalized-pipeline` wholesale.

## Branch Transplant Audit

Status: landed in this branch.

Decision record:

- `docs/arnold/branch-transplant-audit.md`

Purpose:

- Fix the loose-branch ambiguity before continuing the Arnold extraction.
- Establish `feat/arnold-clean-extraction` from `origin/main` as the build
  branch.
- Classify every known loose branch/worktree/stash as ported, direct quarry,
  reshape quarry, deferred Megaplan package work, rejected for Arnold, or
  preserve-before-prune.

Outcome:

- No other branch should become the Arnold extraction base.
- `arnold-generalized-pipeline` remains a quarry, not a merge target.
- `arnold/panel-dispatch` remains the next concrete adapter quarry for Codex
  and Shannon, following the Slice 13 DeepSeek adapter shape.
- Dirty `fix/arnold-conformance-gate` and `mp-tbr-merge` worktrees must be
  preserved before pruning, but they do not block Arnold extraction.
- `stash@{3}` was spot-checked and is Megaplan chain/autocommit work, not an
  Arnold-neutral substrate blocker.
- Shannon ops branches and Megaplan engine/test-selection/attribution branches
  are separate package cleanup work, not Arnold base changes.

Still pending:

- Preserve the current Slices 1-13 dirty worktree before branch surgery.
- Preserve dirty non-Arnold worktrees before any later pruning.
- Port panel-dispatch Codex/Shannon adapters and worker `free_text` support.
- Decide the resume/re-verification cursor trust model before porting more
  resume machinery.

## Slice 1: Conformance Gates

Status: landed in this branch.

Ported:

- `arnold/conformance/` lightweight result types and static gate runner.
- Import-coupling gate for all active Megaplan package names:
  `megaplan`, `arnold.pipelines.megaplan`, and `arnold_pipelines.megaplan`.
- Package-name staleness gate so a namespace move cannot make the coupling gate
  silently blind.
- Semantic-coupling gate for Megaplan phase names, `PlanState`, `.megaplan`,
  profile slots, handler names, and gate/tiebreaker vocabulary in generic
  Arnold layers.
- Public workflow layering gate to keep low-level graph/executor structures out
  of the public authoring API.
- Never-port artifact gate for archived plans, Hermes state, database sidecars,
  prompt dumps, runtime state, receipts, and driver logs.
- Focused tests under `tests/arnold/conformance/`.

Adapted rather than copied:

- The quarry conformance package from `fix/arnold-conformance-gate` was used as
  source evidence, but this slice implements a smaller static gate set matched
  to the clean plan.
- Exact baseline count assertions were not copied. The new allowlist is a
  ratchet: stale entries fail, and new entries must be deliberate.

Still pending:

- Broader conformance routing/join checks from the quarry.
- CI wiring for `run_conformance_suite`.
- Layer-aware checks for the future `arnold.kernel`, `arnold.workflow`,
  `arnold.patterns`, and `arnold.execution` package split.
- Follow-up removal of current allowlist entries as namespace decontamination
  progresses.

Verification:

```text
python -m pytest tests/arnold/conformance/test_conformance_gates.py -q
10 passed

python -c 'from arnold.conformance.checks import run_conformance_suite; suite = run_conformance_suite(); assert suite.passed'
passed
```

## Slice 2: Neutral Cost, Media, And Token Accounting

Status: landed in this branch.

Ported:

- `arnold/pipeline/cost_types.py` with neutral `CanonicalUsage`,
  `CostResult`, `CostStatus`, and `CostSource`.
- `arnold/pipeline/media_cost.py` with `MediaUsage`, media pricing rows,
  media usage extraction normalization, hook metadata normalization, and
  per-media-unit cost computation.
- `arnold/pipeline/media_content.py` with reference-metadata validators for
  `video/mp4`, `audio/wav`, and `application/x-astrid-timeline`.
- `arnold/pipeline/token_cost.py` with neutral billing route resolution,
  common provider usage normalization, token cost computation, compact display
  helpers, custom pricing rows, and callback-injected provider metadata lookup.
- Public re-exports from `arnold.pipeline`, matching the package's existing
  public-surface style.
- Focused tests under `tests/arnold/pipeline/`.

Adapted rather than copied:

- Did not port the Megaplan `usage_pricing.py` rewrite wholesale.
- Token and media pricing default to unknown unless a pipeline package supplies
  pricing rows or injects provider metadata callbacks. The neutral substrate
  does not embed live provider price snapshots.
- Fixed the media pricing data model so `MediaPricingEntry.source` defaults to
  `"none"`; `"estimated"` remains the status default.
- Kept executor hook accounting and Megaplan worker/runtime shims out of this
  slice.

Still pending:

- A deliberate adapter/shim, if needed, from existing Megaplan agent pricing
  callers to the neutral `arnold.pipeline.token_cost` API.
- Runtime media-cost aggregation from `StepResult.hook_metadata`; this slice
  only adds the neutral primitives and metadata normalizers.
- Package-owned provider pricing tables or provider metadata adapters, if a
  product package wants first-class estimated costs.

Verification:

```text
python -m pytest tests/arnold/pipeline/test_cost_types.py tests/arnold/pipeline/test_media_cost.py tests/arnold/pipeline/test_media_content.py tests/arnold/pipeline/test_token_cost.py tests/arnold/pipeline/test_cost_exports.py -q
27 passed

python -m pytest tests/arnold/conformance/test_conformance_gates.py -q
10 passed

python -c 'from arnold.conformance.checks import run_conformance_suite; suite = run_conformance_suite(); print(suite); assert suite.passed'
passed

python -m pytest tests/arnold/pipeline/test_exports.py tests/arnold/pipeline/test_cost_exports.py -q
15 passed
```

## Slice 3: Runtime Event Durability

Status: landed in this branch.

Ported:

- `arnold/runtime/event_journal.py` with neutral `EventEnvelope`,
  `EventSink`, `NdjsonEventJournal`, `NdjsonEventSink`, sorted eager reads,
  lazy streaming reads, and bounded event-page reads.
- `arnold/runtime/state_persistence.py` with `runtime_state_lock` and atomic
  byte/text/JSON writes using temp-file, fsync, replace, and parent-directory
  fsync semantics.
- `arnold/runtime/wal_fold.py` with a pure event fold and last-state snapshot
  projector.
- `arnold/runtime/semantic_replay.py` with structural equivalence comparison
  and event-journal replay over the last `payload.state` snapshot.
- Public re-exports from `arnold.runtime`, matching the package's existing
  top-level convenience style.
- Focused tests under `tests/arnold/runtime/`.

Adapted rather than copied:

- Renamed the primary lock helper from the quarry's `plan_state_lock` to
  `runtime_state_lock`, because the neutral Arnold runtime should not make
  plan-shaped vocabulary the canonical API. The temporary compatibility alias
  was later removed in Slice 10.
- Kept `expected_state` as the primary semantic replay argument. The temporary
  `expected_plan` compatibility alias was later removed in Slice 10.
- Fixed the quarry event-page edge case where `limit=0` returned one event.
  The clean API returns an empty page.
- Trimmed the implementation to deterministic file-backed primitives and pure
  fold/replay helpers. No store backend, process orchestration, sandbox runner,
  oracle policy, or pipeline-specific event taxonomy was introduced.

Still pending:

- Add CI wiring so the conformance suite runs alongside the runtime tests.
- Evaluate whether durable event journal integration belongs in the Megaplan
  package adapter, a generic execution layer, or both; this slice only provides
  the neutral substrate.
- Consider a later stress/concurrency test for multi-process journal appends if
  the event journal becomes a hot path.

Verification:

```text
python -m pytest tests/arnold/runtime/test_event_journal.py tests/arnold/runtime/test_state_persistence.py tests/arnold/runtime/test_semantic_replay.py tests/arnold/runtime/test_package_boundary.py -q
23 passed

python -m pytest tests/arnold/conformance/test_conformance_gates.py -q
10 passed

python -c 'from arnold.conformance.checks import run_conformance_suite; suite = run_conformance_suite(); print(suite); assert suite.passed'
passed

python -m pytest tests/arnold/runtime -q
193 passed
```

## Slice 4: Neutral Agent Contracts And Dispatcher

Status: landed in this branch.

Ported:

- `arnold/agent/contracts.py` with `AgentSpec`, `AgentMode`,
  `AgentRequest`, `AgentResult`, telemetry value objects, fanout units, and
  `scatter_agent_units`.
- `arnold/agent/dispatcher.py` with the small `ArnoldDispatcher` adapter
  registry.
- `arnold/agent/adapters/__init__.py` with structural protocols for backend
  adapters, session stores, key sources, event emitters, and liveness hooks.
- `arnold/agent/providers/pool.py` with a thread-safe provider key pool,
  environment-key aliases, 429 cooldown, and failure marking.
- `arnold/agent/providers/env_loader.py` with `.env` loading precedence for
  the existing Hermes-compatible key layout.
- A clean `arnold/agent/__init__.py` public surface that re-exports neutral
  contracts and dispatcher helpers.
- Focused tests under `tests/arnold/agent/`.

Adapted rather than copied:

- Did not copy the quarry `arnold/agent/__init__.py` default DeepSeek
  pre-registration. Importing `arnold.agent` must not instantiate or import a
  concrete runtime backend.
- Did not port `arnold/agent/run_agent.py`, `arnold/agent/tools/**`,
  `arnold/agent/hermes_cli/**`, `arnold/agent/honcho_integration/**`, or
  `arnold/pipelines/megaplan/agent/**`. Those are reshape/defer candidates
  because they mix neutral seams with product runtime, tool registration,
  gateway, environment, or Megaplan compatibility concerns.
- Did not port the quarry `_pricing.py` table. The neutral substrate already
  defaults cost estimates to unknown unless a caller injects pricing. The
  concrete DeepSeek adapter was later reshape-ported in Slice 13 without the
  baked pricing table or `run_agent` dependency.

Still pending:

- Decide whether `arnold.agent.providers` should keep the Hermes-compatible
  env naming as the canonical key layout or move to provider-neutral naming
  with compatibility aliases.
- Port or rewrite additional concrete adapter slices, likely Codex/Shannon,
  using the Slice 13 DeepSeek adapter as the clean pattern.
- Reshape file/web/process tool modules into pure helper functions plus thin
  tool-registry bindings, avoiding import-time self-registration.
- Reshape the large `run_agent.py` loop only after the backend adapter boundary
  is proven with tests.

Verification:

```text
python -m pytest tests/arnold/agent -q
9 passed

python - <<'PY'
import sys
before = {k for k in sys.modules if k.startswith('megaplan') or k.startswith('arnold.pipelines.megaplan')}
import arnold.agent
after = {k for k in sys.modules if k.startswith('megaplan') or k.startswith('arnold.pipelines.megaplan')}
assert not (after - before)
PY
passed

python -m pytest tests/arnold/conformance/test_conformance_gates.py -q
10 passed

python -c 'from arnold.conformance.checks import run_conformance_suite; suite = run_conformance_suite(); print(suite); assert suite.passed'
passed

python -m pytest tests/arnold/pipelines/evidence_pack/test_hooks.py tests/arnold/pipelines/evidence_pack/test_end_to_end.py tests/arnold/conformance/test_conformance_gates.py tests/arnold/conformance/test_routing.py tests/arnold/conformance/test_join.py tests/arnold/conformance/test_behavioral_suite.py tests/arnold/pipeline/test_executor_hooks.py tests/arnold/pipeline/test_runner.py tests/arnold/pipeline/test_executor.py tests/arnold/agent tests/arnold/runtime/test_event_journal.py tests/arnold/runtime/test_state_persistence.py tests/arnold/runtime/test_semantic_replay.py tests/arnold/pipelines/megaplan/test_step_contracts_parity.py tests/arnold/pipelines/megaplan/test_step_contracts_registry.py tests/arnold/pipelines/megaplan/test_step_contracts_guards.py tests/arnold/pipelines/megaplan/test_schema_seeds.py tests/arnold/pipelines/megaplan/test_model_seam.py tests/arnold/pipeline/test_cost_types.py tests/arnold/pipeline/test_media_cost.py tests/arnold/pipeline/test_media_content.py tests/arnold/pipeline/test_token_cost.py tests/arnold/pipeline/test_cost_exports.py tests/test_workers_env_runtime_policy.py tests/test_worker_exports_compatibility.py -q
327 passed
```

## Slice 10: Neutral Runtime Surface Cleanup

Status: landed in this branch.

Source:

- DeepSeek adversarial quarry audit, saved under
  `/private/tmp/arnold-quarry-results-20260612-170942/05-adversarial-elegance-review.txt`.

Changed:

- Removed the `phase` field from `EventEnvelope` and the `phase=` keyword from
  `EventSink`, `NdjsonEventJournal.emit()`, and `NdjsonEventSink.emit()`.
  Pipeline-specific stage/phase labels belong in event payloads, not the neutral
  event envelope.
- Removed quarry compatibility aliases:
  - `plan_state_lock` from `arnold.runtime.state_persistence`.
  - `read_event_journal_paged` from `arnold.runtime.event_journal` and
    `arnold.runtime.wal_fold`.
  - `expected_plan` from `semantic_replay_journal()`.
- Trimmed `arnold.runtime.__init__` so it exports only primitives that actually
  exist in the clean branch. Removed aspirational batch, recovery, driver, and
  settings names from the public package surface.
- Removed tests that preserved the compatibility aliases.

Disposition:

- This is a reject/delete slice rather than a port slice. The old names existed
  only to make quarry code comfortable during migration and would make new
  pipeline authors see Megaplan-shaped concepts as neutral runtime API.

Still pending:

- Typed Step-IO executor wiring is now the recommended next execution slice.
- `to_jsonable()` may deserve a neutral helper once a second hook/runtime path
  needs recursive `to_json()` normalization.

Verification:

```text
python -m py_compile arnold/runtime/event_journal.py arnold/runtime/state_persistence.py arnold/runtime/wal_fold.py arnold/runtime/semantic_replay.py arnold/runtime/__init__.py
passed

python -m pytest tests/arnold/runtime/test_event_journal.py tests/arnold/runtime/test_state_persistence.py tests/arnold/runtime/test_semantic_replay.py tests/arnold/pipelines/evidence_pack/test_hooks.py tests/arnold/pipelines/evidence_pack/test_end_to_end.py tests/arnold/conformance/test_conformance_gates.py -q
36 passed

python -m pytest tests/arnold/pipelines/evidence_pack/test_hooks.py tests/arnold/pipelines/evidence_pack/test_end_to_end.py tests/arnold/conformance/test_conformance_gates.py tests/arnold/conformance/test_routing.py tests/arnold/conformance/test_join.py tests/arnold/conformance/test_behavioral_suite.py tests/arnold/pipeline/test_executor_hooks.py tests/arnold/pipeline/test_runner.py tests/arnold/pipeline/test_executor.py tests/arnold/agent tests/arnold/runtime/test_event_journal.py tests/arnold/runtime/test_state_persistence.py tests/arnold/runtime/test_semantic_replay.py tests/arnold/pipelines/megaplan/test_step_contracts_parity.py tests/arnold/pipelines/megaplan/test_step_contracts_registry.py tests/arnold/pipelines/megaplan/test_step_contracts_guards.py tests/arnold/pipelines/megaplan/test_schema_seeds.py tests/arnold/pipelines/megaplan/test_model_seam.py tests/arnold/pipeline/test_cost_types.py tests/arnold/pipeline/test_media_cost.py tests/arnold/pipeline/test_media_content.py tests/arnold/pipeline/test_token_cost.py tests/arnold/pipeline/test_cost_exports.py tests/test_workers_env_runtime_policy.py tests/test_worker_exports_compatibility.py -q
324 passed
```

## Slice 11: Typed Step-IO Executor Wiring

Status: landed in this branch.

Source:

- DeepSeek runtime/resume/Step-IO audit, saved under
  `/private/tmp/arnold-quarry-results-20260612-170942/01-runtime-resume-step-io.txt`.

Changed:

- `arnold.pipeline.executor` now validates typed Step-IO envelopes in
  `StepResult.outputs` and `StepResult.state_patch` before executor-owned
  state is updated.
- Typed writes use `StepIOContractContext(operation=WRITE,
  registry_root=envelope.artifact_root)`. Legacy values remain writable.
  Invalid typed envelopes and typed envelopes whose schema cannot be resolved
  are blocked with a `ValueError`.
- `StepContext.state` still exposes the raw state snapshot. `StepContext.inputs`
  now exposes the Step-IO read view, so valid typed envelopes are presented to
  consumers as their payload while the raw envelope remains in state.
- `__contract_results__` publication remains outside the typed envelope gate.
  `ContractResult` is the control-plane seam primitive, not a
  `StepIOEnvelope`.
- Added focused executor tests for valid typed-envelope handoff and invalid
  typed-envelope write blocking.

Disposition:

- Directly uses already-landed neutral Step-IO primitives rather than copying a
  Megaplan resume runner. This completes the low-blast-radius typed Step-IO
  executor slice while keeping full resume/re-verification deferred.

Still pending:

- Real resume/re-verification across a persisted cursor and manifest/schema
  change remains unsolved.
- If more callers need custom registry roots or shadow/write policy, add an
  explicit executor option rather than implicit global policy.

Verification:

```text
python -m pytest tests/arnold/pipeline/test_executor.py tests/arnold/pipeline/test_step_io_envelope_boundary.py tests/arnold/pipeline/test_step_io_handoff.py tests/arnold/pipeline/test_step_io_seams.py -q
92 passed

python -m pytest tests/arnold/pipelines/evidence_pack/test_hooks.py tests/arnold/pipelines/evidence_pack/test_end_to_end.py tests/arnold/conformance/test_conformance_gates.py tests/arnold/conformance/test_routing.py tests/arnold/conformance/test_join.py tests/arnold/conformance/test_behavioral_suite.py tests/arnold/pipeline/test_executor_hooks.py tests/arnold/pipeline/test_runner.py tests/arnold/pipeline/test_executor.py tests/arnold/pipeline/test_step_io_envelope_boundary.py tests/arnold/pipeline/test_step_io_handoff.py tests/arnold/pipeline/test_step_io_seams.py tests/arnold/agent tests/arnold/runtime/test_event_journal.py tests/arnold/runtime/test_state_persistence.py tests/arnold/runtime/test_semantic_replay.py tests/arnold/pipelines/megaplan/test_step_contracts_parity.py tests/arnold/pipelines/megaplan/test_step_contracts_registry.py tests/arnold/pipelines/megaplan/test_step_contracts_guards.py tests/arnold/pipelines/megaplan/test_schema_seeds.py tests/arnold/pipelines/megaplan/test_model_seam.py tests/arnold/pipeline/test_cost_types.py tests/arnold/pipeline/test_media_cost.py tests/arnold/pipeline/test_media_content.py tests/arnold/pipeline/test_token_cost.py tests/arnold/pipeline/test_cost_exports.py tests/test_workers_env_runtime_policy.py tests/test_worker_exports_compatibility.py -q
381 passed
```

## Slice 12: Agent Backend Adapter Protocol

Status: landed in this branch.

Source:

- DeepSeek agent-adapter audit from
  `/private/tmp/arnold-quarry-results-20260612-170942/02-agent-adapter-runtime.txt`.
- Codex read-only contract review saved at
  `/tmp/arnold-backend-adapter-protocol-codex.txt`.

Changed:

- Replaced `BackendAdapter = Callable[[AgentRequest], AgentResult]` with a
  `@runtime_checkable` callable Protocol in `arnold.agent.adapters`.
- Kept the shape deliberately minimal: `__call__(request: AgentRequest) ->
  AgentResult` only. No `model_name`, streaming flag, async method, lifecycle
  hook, or provider metadata was added ahead of a concrete adapter need.
- Added tests proving both function adapters and class adapters satisfy the
  protocol and still dispatch through `ArnoldDispatcher`.

Disposition:

- This is a small contract-tightening slice that should precede concrete
  DeepSeek/Codex/Shannon adapter reshapes. It gives adapters a named structural
  seam without letting the first concrete provider define the abstraction by
  accident.

Still pending:

- Concrete DeepSeek adapter reshape using the neutral token-cost helpers and no
  import-time provider/runtime coupling.
- Optional adapter import-isolation gate can become part of conformance once a
  concrete adapter exists.

Verification:

```text
python -m pytest tests/arnold/agent -q
11 passed

python - <<'PY'
import sys
before = set(sys.modules)
import arnold.agent
new = set(sys.modules) - before
for forbidden in ('arnold.agent.adapters.deepseek', 'arnold.pipelines.megaplan', 'megaplan', 'openai', 'deepseek'):
    assert not any(name == forbidden or name.startswith(forbidden + '.') for name in new), forbidden
print('passed')
PY
passed

python -m pytest tests/arnold/agent tests/arnold/pipeline/test_executor.py tests/arnold/pipeline/test_executor_hooks.py tests/arnold/pipeline/test_runner.py tests/arnold/pipelines/evidence_pack/test_hooks.py tests/arnold/pipelines/evidence_pack/test_end_to_end.py tests/arnold/runtime/test_event_journal.py tests/arnold/runtime/test_state_persistence.py tests/arnold/runtime/test_semantic_replay.py tests/arnold/conformance/test_conformance_gates.py tests/arnold/conformance/test_behavioral_suite.py -q
105 passed
```

## Slice 13: DeepSeek Adapter Reshape

Status: landed in this branch.

Source:

- `arnold/panel-dispatch` provided the concrete adapter quarry, especially
  `arnold/agent/adapters/deepseek.py` and its tests.
- The clean branch deliberately reshaped rather than copied that adapter,
  because the quarry version wrapped `run_agent.AIAgent` and used a baked
  provider-pricing table.

Changed:

- Added `arnold.agent.adapters.deepseek.DeepSeekAdapter`, a concrete
  `BackendAdapter` implementation for DeepSeek's OpenAI-compatible
  chat-completions API.
- Uses injected `KeyPool`/`KeyPoolLike` for key acquisition and reports 429s
  and auth failures back to the pool.
- Uses an injected transport for tests and a stdlib `urllib` transport by
  default. No OpenAI/DeepSeek SDK import occurs at module import time.
- Uses injected `PricingEntry` rows through `arnold.pipeline.token_cost` for
  cost estimation. Unknown pricing is reported as zero-cost/unknown metadata
  rather than copied from a stale `_pricing.py` table.
- Keeps `DeepSeekAdapter` in `arnold.agent.adapters.deepseek` rather than the
  neutral `arnold.agent` root surface, so importing `arnold.agent` does not
  import a concrete backend adapter.
- Added focused tests for protocol conformance, request payload shape, response
  projection, cost estimation through neutral pricing rows, key-pool 429/auth
  callbacks, no-key failure, and import isolation.

Disposition:

- Reshape-port. The useful quarry idea was "a concrete DeepSeek adapter exists";
  the implementation path was changed to fit the clean neutral package.

Still pending:

- Decide whether Codex/Shannon adapters from `arnold/panel-dispatch` can follow
  the same direct adapter pattern or need more substrate.
- If multiple adapters need identical OpenAI-compatible request/response
  helpers, extract them after the second adapter proves the duplication.

Verification:

```text
python -m pytest tests/arnold/agent -q
16 passed

python - <<'PY'
import sys
before = set(sys.modules)
import arnold.agent
new = set(sys.modules) - before
for forbidden in ('arnold.agent.adapters.deepseek', 'arnold.pipelines.megaplan', 'megaplan', 'openai', 'deepseek'):
    assert not any(name == forbidden or name.startswith(forbidden + '.') for name in new), forbidden
print('passed')
PY
passed

python -m pytest tests/arnold/agent tests/arnold/pipeline/test_executor.py tests/arnold/pipeline/test_executor_hooks.py tests/arnold/pipeline/test_runner.py tests/arnold/pipelines/evidence_pack/test_hooks.py tests/arnold/pipelines/evidence_pack/test_end_to_end.py tests/arnold/runtime/test_event_journal.py tests/arnold/runtime/test_state_persistence.py tests/arnold/runtime/test_semantic_replay.py tests/arnold/conformance/test_conformance_gates.py tests/arnold/conformance/test_behavioral_suite.py -q
110 passed
```

## Slice 5: Megaplan StepContract Registry

Status: staged in this branch.

Ported:

- `arnold/pipelines/megaplan/step_contracts.py` with a frozen
  `StepContract` registry for the 17 Megaplan phase identities.
- Factory helpers for the legacy schema filename map, default agent routing,
  capture schema keys, compatibility modes, and `StepInvocation` construction.
- Byte-parity and registry-shape tests under
  `tests/arnold/pipelines/megaplan/`.

Adapted rather than copied:

- At initial staging, this slice imported the live `CompatibilityMode` enum
  from `model_seam.py` to make parity tests compare against current behavior
  exactly. Slice 7 later extracted that enum into
  `arnold.pipelines.megaplan._compatibility` as part of the real cutover.
- Did not port the AST guard tests yet, because those require replacing the
  legacy dict literals in `workers/_impl.py`, `profiles/policy.py`, and
  `model_seam.py`. This slice establishes the registry and proves it is
  byte-equivalent before the cutover.

Still pending:

- See Slice 7 for the completed factory cutover, enum extraction, and
  StepInvocation bypass guard.

Verification:

```text
python -m pytest tests/arnold/pipelines/megaplan/test_step_contracts_parity.py tests/arnold/pipelines/megaplan/test_step_contracts_registry.py -q
18 passed
```

## Slice 6: Pipeline Hooks And Runner

Status: landed in this branch.

Ported:

- `arnold/pipeline/hooks.py` with the neutral `ExecutorHooks` protocol,
  `NullExecutorHooks`, and opt-in media-cost accounting helper.
- `arnold/pipeline/runner.py` as the thin stable namespace for the canonical
  executor entry point.
- Hook-aware executor integration for step start/end/error, state merge,
  envelope join, parallel result join, suspension, pre-loop halt, routing
  fallback, edge traversal, stage completion, and runtime parallel-safety
  checks.
- `StepContext.hook_extensions` and `StepContext.contract_results` so runtime
  adapters can pass neutral execution context without importing a pipeline
  package.
- `StepResult.hook_metadata` as the narrow side channel for hook-only metadata,
  including `runtime_envelope` and `media_usage`.
- `MediaCostAccumulator` as an opt-in convenience wrapper over the pure media
  cost helper.
- Public re-exports from `arnold.pipeline` for the hook protocol and helper
  types.
- Focused tests under `tests/arnold/pipeline/`.

Adapted rather than copied:

- Fixed a latent runner issue from the quarry shape: explicit
  `parallel_safe=None` now normalizes to the default predicate instead of
  reaching parallel fan-out as a callable.
- Wired `join_envelope` into the executor even though the quarry copy only
  exposed the callback. The clean convention is deliberately small:
  `StepResult.hook_metadata["runtime_envelope"]` is offered to the hook, and
  the hook decides whether to return a replacement envelope.
- Kept the runner intentionally minimal. `run_step` and `next_steps` are not
  present until a real consumer earns them.
- Did not port `run_pipeline_resume`, resume re-verification, typed Step-IO
  enforcement, or `StepIOEnforcementError`. Those are higher-blast-radius
  slices that should land after the hook surface is stable.

Still pending:

- Full resume/re-verification slice, including trust semantics and invalid
  resume handling.
- Typed Step-IO enforcement in the neutral executor, if the migration still
  needs it after the StepContract cutover.
- Behavioural conformance checks for routing and join semantics.
- Megaplan adapters that use these hooks for state persistence, event
  journaling, media/cost aggregation, and suspension.

Verification:

```text
python -m py_compile arnold/pipeline/executor.py arnold/pipeline/hooks.py arnold/pipeline/runner.py arnold/pipeline/types.py arnold/pipeline/__init__.py
passed

python -m pytest tests/arnold/pipeline/test_executor_hooks.py tests/arnold/pipeline/test_runner.py tests/arnold/pipeline/test_executor.py -q
52 passed
```

## Slice 7: Megaplan StepContract Cutover

Status: landed in this branch.

Ported:

- `arnold/pipelines/megaplan/_compatibility.py` with the `CompatibilityMode`
  enum extracted into a leaf module.
- `workers/_impl.py` now derives `STEP_SCHEMA_FILENAMES` from
  `build_step_schema_filenames()`.
- `profiles/policy.py` now derives `DEFAULT_AGENT_ROUTING` from
  `build_default_agent_routing()`, preserving the exact 14-key routing surface
  and excluding prep sub-steps.
- `model_seam.py` now derives `_CAPTURE_SCHEMA_KEYS_BY_STEP` and
  `_COMPATIBILITY_MODE_BY_STEP` from the StepContract registry factories.
- `audit_step_payload()` now routes registered Megaplan phases through
  `contract_to_invocation()` instead of constructing the minimal
  `StepInvocation` metadata shape inline.
- `schema_seeds.py` now reads schema filenames from the registry factory
  instead of importing the workers package.
- The quarry AST guard test was ported as
  `tests/arnold/pipelines/megaplan/test_step_contracts_guards.py`.

Adapted rather than copied:

- The enum extraction was required in this branch, not just a follow-up,
  because `profiles.policy -> step_contracts -> model_seam -> step_contracts`
  otherwise creates a circular import during CLI/test bootstrap.
- Kept `_compatibility_mode_for_step(None)` and unknown-step lookup behavior
  conservative: unregistered steps still default to `CompatibilityMode.LEGACY`.
  The quarry changed that default to native, but this slice avoids that behavior
  change.
- Removed the unknown-step fallback from `audit_step_payload()`. All production
  callers audit registered Megaplan phases; unknown audit requests now fail
  clearly instead of silently recreating the legacy minimal invocation bypass.
- Did not start typed Step-IO enforcement, resume re-verification, authoring
  API enforcement, or long-tail seam deletion. This slice is only metadata
  authority consolidation.

Still pending:

- Behavioural conformance routing/join checks from the quarry.
- Evidence-pack hooks as the first non-Megaplan proof that Slice 3 durability
  and Slice 6 hooks compose.
- Resume/re-verification and typed Step-IO enforcement as a separate
  high-blast-radius execution slice.
- Concrete agent adapter/tooling reshape, starting with the DeepSeek adapter
  only after baked pricing and import-time runtime coupling are removed.

Verification:

```text
python -m py_compile arnold/pipelines/megaplan/_compatibility.py arnold/pipelines/megaplan/step_contracts.py arnold/pipelines/megaplan/model_seam.py arnold/pipelines/megaplan/profiles/policy.py arnold/pipelines/megaplan/workers/_impl.py arnold/pipelines/megaplan/schema_seeds.py
passed

python -m pytest tests/arnold/pipelines/megaplan/test_model_seam.py -q
65 passed

python -m pytest tests/arnold/pipeline/test_executor_hooks.py tests/arnold/pipeline/test_runner.py tests/arnold/pipeline/test_executor.py tests/arnold/conformance/test_conformance_gates.py tests/arnold/agent tests/arnold/runtime/test_event_journal.py tests/arnold/runtime/test_state_persistence.py tests/arnold/runtime/test_semantic_replay.py tests/arnold/pipelines/megaplan/test_step_contracts_parity.py tests/arnold/pipelines/megaplan/test_step_contracts_registry.py tests/arnold/pipelines/megaplan/test_step_contracts_guards.py tests/arnold/pipelines/megaplan/test_schema_seeds.py tests/arnold/pipelines/megaplan/test_model_seam.py tests/arnold/pipeline/test_cost_types.py tests/arnold/pipeline/test_media_cost.py tests/arnold/pipeline/test_media_content.py tests/arnold/pipeline/test_token_cost.py tests/arnold/pipeline/test_cost_exports.py tests/test_workers_env_runtime_policy.py tests/test_worker_exports_compatibility.py -q
243 passed
```

## Slice 8: Behavioural Routing And Join Conformance

Status: landed in this branch.

Ported:

- `arnold/conformance/routing.py` with deterministic pipeline-stage walking,
  routing-stage detection, vocabulary coverage checks, vocabulary/edge
  consistency checks, and seeded `resolve_edge` behavioural checks for normal,
  decision, override, halt, unmatched-signal, and out-of-vocabulary paths.
- `arnold/conformance/join.py` with join-delegation checks for
  `ExecutorHooks.join_parallel_results`, including sentinel delegation,
  child-result forwarding, context forwarding, and non-delegating hook
  detection.
- Quarry tests under `tests/arnold/conformance/test_routing.py` and
  `tests/arnold/conformance/test_join.py`.
- `tests/arnold/conformance/test_behavioral_suite.py` proving that
  `run_conformance_suite()` can opt into behavioural checks for supplied
  pipelines/hooks and that both evidence-pack pipeline shapes pass the opt-in
  suite.

Adapted rather than copied:

- Static conformance remains the default mode. `run_conformance_suite()` still
  returns only the original five static extraction gates unless callers supply
  `pipelines` or `hooks`.
- Behavioural routing checks are opt-in via `pipelines=[...]`; join checks are
  opt-in via `hooks=[...]`. This preserves the lightweight
  `import arnold.conformance` path and avoids importing Megaplan.
- The evidence-pack integration was kept as a focused regression rather than
  copying the quarry's larger conformance integration test wholesale. Adapter
  protocol checks and sample-contract checks remain separate future candidates.

Still pending:

- Evidence-pack hooks as the first concrete non-Megaplan runtime hook consumer.
- Optional adapter-protocol conformance checks if a neutral adapter registry
  becomes part of the extraction gate.
- CI wiring for the expanded conformance test set.

Verification:

```text
python -m pytest tests/arnold/conformance/test_conformance_gates.py tests/arnold/conformance/test_routing.py tests/arnold/conformance/test_join.py tests/arnold/conformance/test_behavioral_suite.py -q
84 passed

python - <<'PY'
import sys
before = set(sys.modules)
import arnold.conformance
new = set(sys.modules) - before
assert not any(name == 'arnold.pipelines.megaplan' or name.startswith('arnold.pipelines.megaplan.') or name == 'megaplan' or name.startswith('megaplan.') for name in new)
PY
passed

python -m pytest tests/arnold/conformance/test_conformance_gates.py tests/arnold/conformance/test_routing.py tests/arnold/conformance/test_join.py tests/arnold/conformance/test_behavioral_suite.py tests/arnold/pipeline/test_executor_hooks.py tests/arnold/pipeline/test_runner.py tests/arnold/pipeline/test_executor.py tests/arnold/agent tests/arnold/runtime/test_event_journal.py tests/arnold/runtime/test_state_persistence.py tests/arnold/runtime/test_semantic_replay.py tests/arnold/pipelines/megaplan/test_step_contracts_parity.py tests/arnold/pipelines/megaplan/test_step_contracts_registry.py tests/arnold/pipelines/megaplan/test_step_contracts_guards.py tests/arnold/pipelines/megaplan/test_schema_seeds.py tests/arnold/pipelines/megaplan/test_model_seam.py tests/arnold/pipeline/test_cost_types.py tests/arnold/pipeline/test_media_cost.py tests/arnold/pipeline/test_media_content.py tests/arnold/pipeline/test_token_cost.py tests/arnold/pipeline/test_cost_exports.py tests/test_workers_env_runtime_policy.py tests/test_worker_exports_compatibility.py -q
317 passed
```

## Slice 9: Evidence-Pack Runtime Hooks

Status: landed in this branch.

Ported:

- `arnold/pipelines/evidence_pack/hooks.py` with `EvidencePackHooks`, the
  first concrete non-Megaplan consumer of the neutral executor hook surface.
- Hook lifecycle wiring for stage-start events, stage-end events, state
  snapshots, and suspension cursor persistence.
- Package export from `arnold.pipelines.evidence_pack`.
- Focused tests under `tests/arnold/pipelines/evidence_pack/test_hooks.py`
  covering event journal writes, state persistence, suspension cursor
  persistence, and a real initial evidence-pack pipeline suspension run.

Adapted rather than copied:

- The quarry hook used the transitional `plan_state_lock` name and a
  `persist_resume_cursor` helper from `arnold.pipeline`. The clean branch uses
  `runtime_state_lock` and keeps resume-cursor persistence local to the
  evidence-pack package as `resume_cursor.json`.
- Event kinds were named `stage_start` and `stage_end` instead of
  `phase_start` and `phase_end`, because the neutral substrate should not make
  phase vocabulary canonical.
- State snapshots are converted through local JSON-shape normalization before
  writing. The executor publishes `ContractResult` objects into
  `__contract_results__`, and those need `to_json()` conversion before
  `atomic_write_json()`.
- Added a narrow public-workflow-layering allowlist for
  `arnold.pipelines.evidence_pack.hooks`. This module is package-local runtime
  integration, not the public workflow authoring surface, but the static
  layering gate intentionally flags public hook methods with `Stage` and
  `StepResult` annotations.

Still pending:

- Decide whether resume cursor persistence deserves a neutral runtime helper
  after a second non-Megaplan package needs it.
- Consider a package-local runner/bootstrap helper that constructs
  `EvidencePackHooks` automatically for evidence-pack executions.
- Optional adapter-protocol conformance checks from the quarry remain deferred.

Verification:

```text
python -m pytest tests/arnold/pipelines/evidence_pack/test_hooks.py tests/arnold/pipelines/evidence_pack/test_end_to_end.py tests/arnold/conformance/test_conformance_gates.py tests/arnold/conformance/test_behavioral_suite.py -q
24 passed

python -c 'from arnold.conformance.checks import run_conformance_suite; suite = run_conformance_suite(); print(suite); assert suite.passed'
passed
```

## Slice 14: Megaplan Codex/Shannon Adapter Reshape

Status: landed in this branch.

Ported:

- `arnold.pipelines.megaplan.agent_adapters._oneshot` with ephemeral
  one-shot context synthesis for Megaplan worker-backed adapter calls.
- `arnold.pipelines.megaplan.agent_adapters.codex.CodexAdapter`, targeting
  the neutral `AgentRequest`/`AgentResult` contract while lazily calling the
  real Megaplan `run_codex_step` worker.
- `arnold.pipelines.megaplan.agent_adapters.shannon.ShannonAdapter`, targeting
  the same neutral contract while lazily calling the real Megaplan
  `run_shannon_step` worker.
- Additive `free_text=False` support in `run_codex_step()` and
  `run_shannon_step()` so one-shot panel-style calls can request verbatim
  output without schema enforcement.
- Shannon `_extract_free_text_result()` for NDJSON/single-document result
  extraction that preserves auth/error detection.
- Offline adapter and free-text tests under `tests/arnold/agent/`.

Adapted rather than copied:

- Did not place Codex/Shannon adapters in `arnold.agent.adapters`. These
  wrappers depend on Megaplan worker internals, so their honest home is the
  Megaplan package. The neutral `arnold.agent` root remains contract-only and
  does not import Megaplan.
- Did not export or auto-register these adapters from `arnold.agent`. Callers
  that want Megaplan-backed Codex/Shannon dispatch should explicitly import the
  package-local adapters and register them with an `ArnoldDispatcher`.
- Did not port the broad Hermes CLI or Honcho relocation from
  `arnold/panel-dispatch`; that work is unrelated to this adapter slice and
  remains rejected/deferred by the branch transplant audit.
- Projected `WorkerResult` directly into the neutral Arnold `AgentResult`
  instead of calling `WorkerResult.to_agent_result()`, avoiding an unnecessary
  import of the Megaplan agent-runtime compatibility type.

Still pending:

- A product/panel integration point can register
  `CodexAdapter`, `ShannonAdapter(session_agent="claude")`, and
  `ShannonAdapter(session_agent="shannon")` where default routing is actually
  needed.
- The remaining `arnold/panel-dispatch` Hermes/Honcho relocation should stay
  parked until a separate product integration task proves it earns its place.
- Resume/re-verification is still the next execution-runtime concern after
  this adapter slice.

Verification:

```text
python -m py_compile arnold/pipelines/megaplan/agent_adapters/_oneshot.py arnold/pipelines/megaplan/agent_adapters/codex.py arnold/pipelines/megaplan/agent_adapters/shannon.py arnold/pipelines/megaplan/workers/_impl.py arnold/pipelines/megaplan/workers/shannon.py
passed

python -m pytest tests/arnold/agent/test_codex_adapter.py tests/arnold/agent/test_shannon_adapter.py tests/arnold/conformance/test_conformance_gates.py -q
21 passed

python - <<'PY'
import sys
before = set(sys.modules)
import arnold.agent
new = set(sys.modules) - before
bad = sorted(name for name in new if name.startswith('arnold.pipelines.megaplan') or name == 'megaplan' or name.startswith('megaplan.'))
assert not bad
PY
passed
```

## Slice 15: Neutral Resume Cursor Persistence Helper

Status: landed in this branch.

Ported:

- `arnold.pipeline.resume` with atomic `resume_cursor.json` persistence and
  read helpers.
- `persist_composite_resume_cursor()` and `read_composite_resume_cursor()` for
  fan-out/composite suspension cursor documents.
- Public exports from `arnold.pipeline`.
- `EvidencePackHooks` now uses `persist_resume_cursor()` instead of carrying a
  package-local duplicate writer.
- Focused tests under `tests/arnold/pipeline/test_resume.py`.

Adapted rather than copied:

- This slice intentionally ports only the durable cursor helper. It does not
  port the broader quarry `resume_validation.py` re-verification stack yet,
  because that crosses artifact IO, content validation, Step-IO policy, and
  human-suspension schema semantics.
- The helper persists opaque cursor documents only. It does not interpret
  cursor bodies or decide whether a resume is trusted.

Still pending:

- Decide the resume re-verification trust model before porting
  `resume_validation.py`.
- Decide whether composite cursor persistence should be wired into the
  executor or remain a helper until a fan-out suspension consumer needs it.

Verification:

```text
python -m py_compile arnold/pipeline/resume.py arnold/pipelines/evidence_pack/hooks.py arnold/pipeline/__init__.py
passed

python -m pytest tests/arnold/pipeline/test_resume.py tests/arnold/pipelines/evidence_pack/test_hooks.py tests/arnold/conformance/test_conformance_gates.py tests/arnold/pipeline/test_exports.py -q
31 passed
```

## Slice 16: Artifact IO Chokepoint And Large-Artifact Sidecars

Status: landed in this branch.

Ported:

- `arnold.pipeline.artifact_io` with `ArtifactIOResult`,
  `ArtifactIOBlocked`, `validate_artifact_io()`, and
  `validate_large_artifact_by_manifest()`.
- Large-artifact sidecar helpers in `arnold.pipeline.artifacts`:
  `SidecarManifest`, `sidecar_path_for()`, `stream_sha256()`,
  `write_sidecar_manifest()`, `read_sidecar_manifest()`, and
  `verify_sidecar_integrity()`.
- `write_versioned(..., content_type="", schema_hash="")` now emits sidecar
  manifests for artifacts larger than 1 MiB.
- Public exports from `arnold.pipeline`.
- Focused tests under `tests/arnold/pipeline/test_artifact_io.py` and
  `tests/arnold/pipeline/test_artifact_sidecar_manifest.py`.

Adapted rather than copied:

- The clean branch's `step_io_policy` API exposes raw
  `decision_blocks_read/write()` helpers. `validate_artifact_io()` reports
  policy-effective blocking, so shadow/warn downgraded seams record telemetry
  without marking the result blocked or raising.
- Did not port `resume_validation.py` in this slice. The subagent audit found
  it depends on this artifact IO chokepoint and should come next.
- Did not wire artifact IO into the executor. This slice provides the neutral
  store/repository chokepoint and sidecar manifest primitives.

Still pending:

- Port resume re-verification now that `artifact_io.py` exists.
- Decide whether executor/store integrations should call
  `validate_artifact_io()` directly or through a package-specific repository
  layer.

Verification:

```text
python -m py_compile arnold/pipeline/artifacts.py arnold/pipeline/artifact_io.py arnold/pipeline/__init__.py
passed

python -m pytest tests/arnold/pipeline/test_artifact_io.py tests/arnold/pipeline/test_artifact_sidecar_manifest.py tests/arnold/pipeline/test_artifacts.py tests/arnold/pipeline/test_exports.py tests/arnold/conformance/test_conformance_gates.py -q
57 passed
```

## Slice 17: Resume Re-Verification Helpers

Status: landed in this branch.

Ported:

- `arnold.pipeline.resume_validation` with:
  - `ResumeReverifyDeclaration`;
  - `ResumeReverifyResult`;
  - `parse_resume_reverify_declaration()`;
  - `resolve_resume_reverify_artifact()`;
  - `reverify_resume_produces()`.
- Public exports from `arnold.pipeline`.
- Focused tests under `tests/arnold/pipeline/test_resume_validation.py`.

Adapted rather than copied:

- The quarry used a `HumanSuspension` name; this branch already has the same
  neutral envelope as `Suspension(kind="human")`, so the clean port uses the
  existing type instead of adding a duplicate alias.
- Cursor bodies remain opaque. Resolution uses only the explicit
  `x-arnold-resume` declaration and display refs.
- Re-verification composes the Slice 16 `validate_artifact_io()` chokepoint.
  Non-media artifacts must be typed envelopes; media reference metadata is
  validated through the existing media content validators.
- Did not port executor-level resume machinery such as `run_pipeline_resume`.
  Entry override, WAL replay, human-input seeding, and executor resume control
  remain separate high-blast-radius work.

Still pending:

- Decide where executor or package drivers invoke `reverify_resume_produces()`
  during an actual resume.
- Port or author a human-gate helper for constructing the
  `x-arnold-resume` declaration only after a package needs it.

Verification:

```text
python -m py_compile arnold/pipeline/resume_validation.py arnold/pipeline/__init__.py
passed

python -m pytest tests/arnold/pipeline/test_resume_validation.py tests/arnold/pipeline/test_artifact_io.py tests/arnold/pipeline/test_artifact_sidecar_manifest.py tests/arnold/pipeline/test_exports.py tests/arnold/conformance/test_conformance_gates.py -q
46 passed
```
