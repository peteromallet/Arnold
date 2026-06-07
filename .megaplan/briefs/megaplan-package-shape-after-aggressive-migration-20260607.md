# Megaplan Package Shape After Aggressive Migration

Date: 2026-06-07

Source: architecture subagent review of the generalized pipeline, aggressive migration, and Evidence-First briefs.

## Target Shape

Megaplan should end as a normal Arnold pipeline package, not the place where Arnold's runtime is invented.

The neutral center is `arnold.pipeline`: graph, step, port, contract, routing, executor, artifacts, schema registry, step-IO policy, and discovery primitives. Megaplan becomes one serious app on that substrate.

```text
arnold/
  pipeline/
    __init__.py
    types.py
    builder.py
    contracts.py
    declaration_lowering.py
    routing.py
    executor.py
    executor_hooks.py
    execution_result.py
    state.py
    artifacts.py
    schema_registry.py
    step_invocation.py
    step_io_policy.py
    step_io_contract.py
    discovery/
    steps/

  runtime/
    envelope.py
    operations.py
    driver.py
    batch.py
    settings.py
    settings_resolver.py
    recovery.py
    resume.py
    dry_run.py

  control/
    __init__.py
    outcome.py
    state_delta.py
    interface.py
    registry.py

  supervisor/
    __init__.py
    model.py
    state.py
    ladder.py
    runner.py
    outcomes.py
    policies.py

  pipelines/
    evidence_pack/
      pipelines.py
      steps.py
      verifier.py

    megaplan/
      __init__.py
      __main__.py
      manifest.py
      pipeline.py
      runner.py
      step_contracts.py
      step_invocations.py
      pipeline_contracts.py
      routing.py
      stages/
      prompts/
      schemas/
      profiles/
      workers/
      model_seam.py
      planning/
      execute/
      review/
      chain/
      bakeoff/
      store/
      observability/
      runtime/
      supervisor_binding.py
      control_binding.py
```

## What Remains In Megaplan

Megaplan keeps:

- planning semantics: `prep`, `plan`, `critique`, `gate`, `revise`, `finalize`, `execute`, `review`, `tiebreaker`
- gate vocabulary: `PROCEED`, `ITERATE`, `ESCALATE`, tiebreaker behavior
- plan artifact names and conventions
- prompt assembly and model capture policy
- profile / robustness / depth defaults
- plan state meaning
- Git / PR / merge policy
- chain milestone YAML
- bakeoff product behavior
- Evidence-First authority and provenance policy
- store models that are genuinely Megaplan domain objects

The existing `arnold/pipelines/megaplan/pipeline.py` is close to the desired flagship shape: `build_pipeline()` assembles the planning graph and typed payload ports. It should import `Pipeline`, `Stage`, and `Edge` from `arnold.pipeline`, not from `arnold.pipelines.megaplan._pipeline.types`.

## What Moves Out

Move to `arnold.pipeline`:

- production executor behavior from `arnold/pipelines/megaplan/_pipeline/executor.py`
- typed port binding
- parallel safety hook
- output verification
- suspension handling
- loop conditions
- lifecycle hook protocols
- state patch application
- envelope joins
- generic graph/pattern helpers
- neutral state patching, reconciled with `arnold/pipeline/state.py`

Move to `arnold.control`:

- `RunOutcome`
- `RunResultMetadata`
- `ControlTarget`
- `ControlProjection`
- `RunStateView`
- `ControlBinding`
- transition DTOs

Keep Megaplan-specific bridge functions that read/write `state.json` in `megaplan/control_binding.py`.

Move to `arnold.supervisor`:

- `RunNode`
- `RunRecord`
- dependency assertions
- supervisor state
- generic ladder mechanics

Do not move Megaplan profile strings such as `premium`, `apex`, `thorough`, or Megaplan chain/Git/PR policy.

## Known Generic Leaks To Remove

- `arnold/pipeline/schema_registry.py` must lose `_PLAN_DIR_MARKER = (".megaplan", "plans")` and `MEGAPLAN_CONTRACT_SCHEMA_ROOT`.
- `arnold/pipeline/step_io_policy.py` must lose Megaplan path/env assumptions.
- `arnold/pipeline/artifacts.py` must lose the Megaplan context adapter/import example.
- Boundary tests should ban `arnold.pipelines.megaplan`, `.megaplan`, `MEGAPLAN_`, `GateRecommendation`, and `STATE_*` inside generic packages.

## Megaplan Runner

`arnold/pipelines/megaplan/runner.py` should be thin:

```python
@dataclass(frozen=True)
class StepOutcome:
    plan: str
    step: str
    exit_code: int
    previous_state: str | None
    current_state: str | None
    final_stage: str | None
    output_path: Path | None
    contract_result: ContractResult | None
    stdout: str = ""
    stderr: str = ""

def next_steps(plan: str, *, root: Path | None = None) -> list[str]: ...
def run_step(
    plan: str,
    step: str,
    *,
    root: Path | None = None,
    profile: str | None = None,
    extra_args: Mapping[str, Any] | None = None,
) -> StepOutcome: ...
def run_pipeline(
    plan: str,
    steps: Sequence[str] | None = None,
    *,
    root: Path | None = None,
    policy: MegaplanRunPolicy | None = None,
) -> StepOutcome: ...
```

Responsibilities:

- resolve `root/.megaplan/plans/<plan>`
- load Megaplan plan state
- validate requested step against Megaplan workflow/topology
- build `pipeline = megaplan.pipeline.build_pipeline()`
- build neutral `RuntimeEnvelope` and Arnold `StepContext`
- call `arnold.pipeline.executor.run_pipeline(...)`
- supply Megaplan hooks for state persistence, activation events, governor, suspension cursor, output path policy
- return structured outcome

It must not own retry ladders, unattended driving, chain advancement, PR policy, human gate policy, or independent graph walking.

## StepContract

Create `arnold/pipelines/megaplan/step_contracts.py` as the source of truth for current scatter:

- `workers/_impl.py`: `STEP_SCHEMA_FILENAMES`
- `model_seam.py`: capture schemas, compatibility modes, normalizers
- prompt/routing/default worker metadata

Shape:

```python
@dataclass(frozen=True)
class StepContract:
    name: str
    schema_key: str
    capture_schema_key: str
    output_kind: str
    compatibility_mode: CompatibilityMode
    capture_normalizer: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    prompt_key: str | None = None
    default_worker: str | None = None
    supports_persistent: bool = False
    template_write_step: bool = False
```

Derive old dict views from this registry first. Delete the old dicts only after byte-for-byte parity tests pass.

## Temporary Shims

Keep temporarily:

- `arnold.pipelines.megaplan._pipeline.types` re-exporting/adapting `arnold.pipeline.types`
- `arnold.pipelines.megaplan._pipeline.executor.run_pipeline` delegating to `arnold.pipeline.executor.run_pipeline` with Megaplan hooks
- `arnold.pipelines.megaplan.run_outcome` re-exporting `arnold.control.outcome`
- `arnold.pipelines.megaplan.control_interface` re-exporting neutral DTOs plus Megaplan bridge functions
- `compile_planning_pipeline = build_pipeline`

Delete at the end:

- Megaplan `_pipeline/types.py`, `_pipeline/executor.py`, `_pipeline/contracts.py` once no internal imports remain
- legacy compatibility projection paths in `model_seam.py` after native compatibility is permanently green
- `workers/_impl.py::STEP_SCHEMA_FILENAMES` as an owned table
- Megaplan-owned neutral supervisor/control models
- generic-module `.megaplan` path derivation or `MEGAPLAN_` env support

## Migration Order

1. Add hard boundary tests for `arnold.pipeline`, `arnold.runtime`, `arnold.control`, and `arnold.supervisor`.
2. Remove `.megaplan` assumptions from `arnold.pipeline.schema_registry`, `step_io_policy`, and `artifacts`.
3. Move `RunOutcome` and neutral control DTOs to `arnold.control`; leave re-export shims.
4. Add `megaplan.step_contracts` as a read-only mirror; prove derived views match old dicts.
5. Flip workers/model seam/prompt factories to derive from `StepContract`; delete old metadata tables.
6. Purify executor by moving Megaplan `_pipeline/executor.py` capabilities into `arnold.pipeline.executor` hook points.
7. Convert Megaplan `pipeline.py` and stages to neutral `arnold.pipeline` types.
8. Add `megaplan.runner.py` as a wrapper over the canonical executor.
9. Extract supervisor model/ladder/runner to `arnold.supervisor`; keep chain/Git/PR/YAML policy in Megaplan.
10. Run dual-run/replay oracles; only then delete shims and retire `auto.py` as the blessed path.

Net result: `evidence_pack` proves Arnold is generic; Megaplan proves Arnold can host a serious, stateful, model-driven flagship app without owning the substrate.
