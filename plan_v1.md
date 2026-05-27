# Implementation Plan: M4 Naming & Vocabulary Unification

## Overview
M4 should land a canonical vocabulary map first, then apply the chosen names mechanically while preserving persisted state compatibility. The brief is mostly accurate, but targeted greps show two wider areas than stated: `active_step["step"]` is used across runtime, auto, observability, CLI, and tests, and `_pipeline.types.Verdict` appears throughout pipeline docs/demos/tests. This plan treats those as scoped, explicit blast radius rather than incidental cleanup.

The canonical map will keep `gate` for the AI quality checkpoint, rename the pause-for-human pipeline primitive to `HumanDecisionStep`, keep `_pipeline.types.Step` as the pipeline-node protocol, rename active execution metadata typing from `ActiveStep` to `ActivePhase`, keep the persisted top-level `active_step` object, write its inner phase name as `phase`, and read legacy `step` during transition. The pipeline dataclass `Verdict` becomes `PipelineVerdict` (the original target name `JudgeVerdict` is already taken by `megaplan/bakeoff/judge.py:21`). The bakeoff `JudgeVerdict` (TypedDict) and audits `EvaluatorVerdict` (TypedDict) are documented as separate domain concepts. Review/verifiability JSON fields that intentionally use `verdict` remain unchanged and documented.

No file moves happen in this milestone. `_pipeline/steps/` and `_pipeline/stages/` directory vocabulary is documented only; physical relocation is deferred to M5b.

## Phase 1: Prep And Vocabulary Map

### Step 1: Write the canonical vocabulary map (`docs/canonical-vocabulary.md`)
**Complexity: 2**
1. Add the prep deliverable before any renames.
2. Include term, meaning, canonical identifier, legacy/stale identifiers, persistence behavior, and grep verification pattern for each item.
3. Record deliberate non-renames: `_pipeline.types.Step`, top-level `state["active_step"]`, history entries using `"step"`, `review_verdict`, `reviewer_verdict`, `sense_checks[].verdict`, and verifiability UI text.
4. Include the canonical state-string handoff list for M2 from `megaplan/types.py`: `initialized`, `prepped`, `planned`, `critiqued`, `gated`, `finalized`, `executed`, `reviewed`, `done`, `aborted`, `failed`, `blocked`, `paused`, `cancelled`, `awaiting_pr_merge`, `awaiting_human_verify`, `tiebreaker_pending`, `tiebreaker_ready`.
5. **Define grep exclusion zones** for stale-identifier verification (Step 10.3):
   - `docs/archive/**` — historical docs preserved as-is
   - `briefs/**` — locked engineering briefs
   - `CHANGELOG.md` — historical changelog
   - `megaplan/agent/tests/**` — vendored agent test material
   - `**/__pycache__/**` — bytecode caches
   - `docs/yaml-pipelines-migration.md` — self-identified "Archived historical record"
   - `docs/foundation-audit/**` — historical audit artifacts
   - Generated skill material under `megaplan/agent/**` except active source files
   - `*.pyc`, `*.pyo` — compiled bytecode
6. **Define the Verdict prose update rule**: in `_pipeline/` source files, update docstrings, comments, and prose that refer to the dataclass by its class name (e.g., "typed `Verdict`", "Verdict-first edge dispatch", "a `Verdict` on the parent") to use `PipelineVerdict`. Leave generic conceptual prose about "verdicts" as a domain noun (e.g., "the judge returns a verdict", "gate verdict") unchanged in non-pipeline files and in pipeline files where the word is clearly a domain noun rather than a class reference.
7. **Document the three Verdict-class-bearing concepts**: (a) `megaplan/_pipeline/types.py`: `PipelineVerdict` — frozen dataclass, structured output of a pipeline judge-kind step; (b) `megaplan/bakeoff/judge.py`: `JudgeVerdict` — TypedDict for LLM bake-off comparison ranking; (c) `megaplan/audits/critique_evaluator.py`: `EvaluatorVerdict` — TypedDict for critique evaluation. These are distinct domain concepts and must not be conflated.
8. Note that the vocabulary map is a living document amendable during implementation if edge cases are discovered; amendments must be reviewer-visible.

## Phase 2: Low-Risk Identifier Cleanup

### Step 2: Remove both dead execute dispatch aliases (`megaplan/handlers/execute.py`)
**Complexity: 2** (increased from 1 due to doubled scope)
Note: The brief originally identified only `dispatch_execute_auto_loop`, but `handlers/execute.py:10` also creates `dispatch_execute_one_batch` from `handle_execute_one_batch`. Both follow the identical pattern (import-time alias, internal call site, test monkeypatching, docs references) and must be removed together.

1. Remove both alias lines from the import block:
   - `handle_execute_auto_loop as dispatch_execute_auto_loop` → `handle_execute_auto_loop`
   - `handle_execute_one_batch as dispatch_execute_one_batch` → `handle_execute_one_batch`
2. Import `handle_execute_auto_loop` and `handle_execute_one_batch` directly from `megaplan.execute.core`.
3. Update internal call sites in `handle_execute` (lines ~162 and ~178) to use the direct names.
4. Update test monkeypatch references in `tests/test_execute.py`:
   - Lines ~858 (docstring), ~1604, ~1656, ~1700: change `"dispatch_execute_auto_loop"` → `"handle_execute_auto_loop"`
   - Lines ~3571, ~3639: change `"dispatch_execute_one_batch"` → `"handle_execute_one_batch"`
5. Update `docs/execute-token-aggregation.md`: change `dispatch_execute_auto_loop` → `handle_execute_auto_loop` (line ~25) and `dispatch_execute_one_batch` → `handle_execute_one_batch` (line ~52).
6. Grep `dispatch_execute_auto_loop` and `dispatch_execute_one_batch` across `.py/.md/.json/.yaml` to confirm zero active references remain (excluding archive/historical per vocabulary map exclusion zones).

### Step 3: Canonicalize `Backend` / `HomeBackend` (`megaplan/schemas/base.py`, `megaplan/store/base.py`)
**Complexity: 2**
1. Define canonical `Backend = Literal["file", "db"]` in `megaplan/schemas/base.py` (alongside existing `HomeBackend` at line 30). `schemas/base.py` is the canonical owner because it already owns `HomeBackend` and is imported by `store/base.py`.
2. Set `HomeBackend = Backend` as a compatibility alias for Pydantic schema users who import the old name.
3. In `megaplan/store/base.py`, replace the independent `Backend = Literal["file", "db"]` definition at line 54 with `from megaplan.schemas.base import Backend` (added to the existing import block at lines 15-52). Keep all existing imports from `megaplan.schemas.base` intact.
4. Do not change persisted field names like `home_backend` in Pydantic models.

## Phase 3: Gate And Gate-Carry Migration

### Step 4: Rename human pause gate to `HumanDecisionStep` in place
**Complexity: 3**
1. Rename class `HumanGateStep` to `HumanDecisionStep` in `megaplan/_pipeline/steps/human_gate.py`; keep the file path unchanged for M5b.
2. Update imports, docs, and tests in:
   - `megaplan/_pipeline/builder.py`
   - `megaplan/_pipeline/steps/__init__.py`
   - `megaplan/_pipeline/step_helpers.py`
   - `megaplan/cli.py`
   - `megaplan/pipelines/writing_panel_strict.py`
   - `tests/_pipeline/test_human_gate.py`
   - `tests/_pipeline/test_builder.py`
   - `tests/_pipeline/test_writing_panel_e2e.py`
   - `tests/_pipeline/test_epic_blitz_e2e.py`
3. Do not rename `handlers/gate.py` or gate edge kinds; those remain the AI quality checkpoint vocabulary.
4. Grep `\bHumanGateStep\b` in active source/docs/tests and eliminate stale references except excluded historical docs per vocabulary map exclusion zones.

### Step 5: Migrate `gate_carry` from duplicate `verdict`/`recommendation` to `recommendation`
**Complexity: 3**
1. Drop `"verdict"` from `_build_gate_carry()` in `megaplan/handlers/gate.py`; keep `"recommendation"`.
2. Keep read compatibility where legacy artifacts can still appear: normalize with `recommendation = carry.get("recommendation") or carry.get("verdict")` before use.
3. Drop synthesized `"verdict"` from `megaplan/prompts/_shared.py`'s `gate.json` fallback so prompt rendering does not recreate the duplicate.
4. Verify `megaplan/prompts/execute.py` prompt rendering works from a carry object that only has `recommendation`.
5. Update `tests/test_gate.py` to assert exactly one of `verdict`/`recommendation` exists post-write, and add/update a prompt smoke test in `tests/test_prompts.py` (which houses the `test_execute_batch_prompt_*` functions) for the no-`verdict` shape.

## Phase 4: State And Active Phase Vocabulary

### Step 6: Rename `STATE_AWAITING_HUMAN` to `STATE_AWAITING_HUMAN_VERIFY`
**Complexity: 2**
1. Rename the constant only in `megaplan/types.py`; keep the string value `"awaiting_human_verify"` unchanged.
2. Update imports and references in:
   - `megaplan/auto.py`
   - `megaplan/handlers/execute.py`
   - `megaplan/handlers/review.py`
   - `megaplan/handlers/tiebreaker.py`
   - `megaplan/handlers/verifiability.py`
   - `megaplan/_core/workflow.py`
   - `megaplan/_core/workflow_data.py`
   - `tests/test_tiebreaker_trigger.py`
3. Update `AUTOMATION_TERMINAL_STATES` and `CANONICAL_PLAN_STATES` in `megaplan/types.py` to use `STATE_AWAITING_HUMAN_VERIFY`.
4. Keep `PlanCurrentState` literal value `"awaiting_human_verify"` unchanged; document that M2 owns stricter `schemas/sprint1.Plan.current_state` enforcement.

### Step 7: Rename active execution metadata from step to phase without changing function signatures
**Complexity: 4**
1. Rename `ActiveStep` TypedDict to `ActivePhase` in `megaplan/types.py`; keep `PlanState.active_step` as the top-level persisted key for this milestone.
2. Change the inner field written by `set_active_step(...)` from `"step"` to `"phase"`, while preserving the `set_active_step(step=...)` function signature per constraint.
3. Update `PlanState.active_step` annotation from `NotRequired[ActiveStep]` to `NotRequired[ActivePhase]`.
4. Update active metadata readers to accept `phase` first and legacy `step` second in:
   - `megaplan/_core/state.py` — `active_step_is_stale` (line ~120), `_build_plan_locked_details` (line ~183): use `phase = active.get("phase") or active.get("step")` pattern
   - `megaplan/cli.py` (line ~966): same `phase or step` fallback pattern
   - `megaplan/auto.py` (lines ~1341, ~1365): same pattern
   - `megaplan/observability/introspect.py` (line ~463): `active_phase["phase"] = active.get("phase") or active.get("step")`
   - `megaplan/bakeoff/handlers.py` (`_phase` at line ~230): same pattern
   - `megaplan/bakeoff/live_status.py` (line ~40): same pattern
   - `megaplan/orchestration/phase_result.py` (line ~710): restructure chained `.get()` pattern from `raw.get('active_step', {}).get('step', 'unknown')` to `raw.get('active_step', {}).get('phase') or raw.get('active_step', {}).get('step', 'unknown')`
   - **NOTE**: `megaplan/observability/doctor.py:269` and `megaplan/observability/introspect.py:233` are intentionally NOT in the above list — both read only `started_at` from the `active_step` dict and never access the inner `step`/`phase` key, so no fallback pattern is needed there.
5. Update status/auto output tests to expect `phase` in `active_step` responses where the metadata object is surfaced, while adding at least one legacy-read test proving old `active_step: {"step": ...}` still works.
6. Document that workflow/history `entry["step"]` is intentionally not renamed because it is a separate persisted history vocabulary.

## Phase 5: Pipeline Judge Verdict Vocabulary

### Step 8: Rename `_pipeline.types.Verdict` to `PipelineVerdict`
**Complexity: 4**

**CRITICAL**: The initial plan proposed `JudgeVerdict` as the replacement name, but `megaplan/bakeoff/judge.py:21` already defines `class JudgeVerdict(TypedDict)` (imported by `megaplan/bakeoff/comparison.py:10`). The pipeline dataclass is renamed to `PipelineVerdict` instead. The bakeoff `JudgeVerdict` (TypedDict for LLM comparison ranking) retains its name. The audits `EvaluatorVerdict` (`megaplan/audits/critique_evaluator.py:181`) is a separate concept and unchanged. All three Verdict-class-bearing concepts are documented in the vocabulary map (Step 1.7).

1. Rename the dataclass in `megaplan/_pipeline/types.py` from `Verdict` to `PipelineVerdict` and update `StepResult.verdict` annotation to `PipelineVerdict | None`; do not rename the `StepResult.verdict` field unless a separate migration is approved.
2. Update exports in `megaplan/_pipeline/__init__.py` (lines ~17, ~28) and imports/usages in:
   - `megaplan/_pipeline/executor.py` — imports, prose/docstrings referencing the dataclass by name
   - `megaplan/_pipeline/stages/gate.py` — imports, prose
   - `megaplan/_pipeline/stages/inprocess_step.py` — imports (line ~22), construction (lines ~80-83), prose
   - `megaplan/_pipeline/stages/tiebreaker.py` — prose/docstrings (lines ~8, ~56)
   - `megaplan/_pipeline/patterns.py` — imports, prose/docstrings
   - `megaplan/_pipeline/subloop.py` — imports, prose/docstrings
   - `megaplan/_pipeline/planning.py` — prose/docstring (line ~108)
   - `megaplan/_pipeline/demo_judges.py` — imports, usages
   - `megaplan/_pipeline/demos/doc_critique.py` — imports, usages
   - `tests/test_pipeline_receipt.py` — imports
   - `tests/test_pipeline_tiebreaker_subloop.py` — imports/usages
   - `tests/test_pipeline_override.py` — imports/usages
   - `tests/test_pipeline_subloop.py` — imports/usages
   - `tests/_pipeline/test_patterns.py` — imports/usages
   - `tests/_pipeline/test_dynamic_primitives.py` — imports/usages
   - `tests/test_pipeline_composability.py` — imports/usages
   - `tests/test_pipeline_mode_e2e.py` — imports/usages
   - `tests/test_pipeline_typed_edges.py` — imports/usages
   - `tests/test_auto_pipeline_runtime.py` — imports/usages
   - `tests/test_finalize.py` — imports/usages
   - `tests/test_init_plan.py` — imports/usages
3. Apply the Verdict prose rule from the vocabulary map: in `_pipeline/` source files, update docstrings, comments, and prose that reference the dataclass by its class name (e.g., "typed `Verdict`", "Verdict-first edge dispatch", "a `Verdict` on the parent") to use `PipelineVerdict`. Leave generic conceptual prose about "verdicts" as a domain noun (e.g., "the judge returns a verdict", "gate verdict") unchanged.
4. Update active docs `docs/pipelines.md` and `docs/pipeline-architecture.md` to refer to `PipelineVerdict` for the dataclass; leave conceptual verdict prose.
5. Leave `review_verdict`, `reviewer_verdict`, `sense_checks[].verdict`, verifiability pass/fail text, and schema-required `verdict` keys unchanged; these are called out in `docs/canonical-vocabulary.md` as separate domain meanings. The `megaplan/bakeoff/judge.py:21` `JudgeVerdict` TypedDict and `megaplan/audits/critique_evaluator.py:181` `EvaluatorVerdict` TypedDict are also separate domain concepts and are NOT renamed.
6. Grep `\bVerdict\b` after the rename and classify every remaining active hit as either intentionally non-pipeline vocabulary or stale pipeline dataclass text. Exclude archive/historical per vocabulary map exclusion zones.

## Phase 6: Document-Only Invariants

### Step 9: Document critique/review pre/post invariant (`megaplan/handlers/critique.py`, `megaplan/handlers/review.py`)
**Complexity: 1**
1. Add a short module or handler-local doc block stating that critique is the pre-execute plan-quality pass and review is the post-execute implementation-evidence pass.
2. Avoid renaming handlers, commands, prompt fields, or artifacts.

## Phase 7: Verification And Baselines

### Step 10: Run focused tests first, then M0 baselines
**Complexity: 3**
1. Run focused tests for each touched area:
   - Step 2 (aliases): `tests/test_execute.py` (affected functions)
   - Step 3 (Backend): `tests/test_*store*`, `tests/test_*schema*`
   - Step 4 (HumanGateStep): `tests/_pipeline/test_human_gate.py`, `tests/_pipeline/test_builder.py`, `tests/_pipeline/test_writing_panel_e2e.py`, `tests/_pipeline/test_epic_blitz_e2e.py`
   - Step 5 (gate_carry): `tests/test_gate.py`, `tests/test_prompts.py` (functions `test_execute_batch_prompt_*`)
   - Step 6 (STATE): `tests/test_tiebreaker_trigger.py`, plus affected handler/subsystem tests
   - Step 7 (active_step→active_phase): `tests/test_auto.py`, observability tests, status/output tests
   - Step 8 (Verdict→PipelineVerdict): `tests/_pipeline/test_*`, `tests/test_pipeline_*.py`, `tests/test_init_plan.py`, `tests/test_finalize.py`
2. Run characterization baselines: `tests/characterization/test_cli_parser_snapshot.py` and `tests/characterization/test_pipeline_golden.py`. Update snapshots/goldens only where rename-only output changes are intended. The golden fixtures (`tests/fixtures/golden/*.json`) currently don't encode class names as strings, so snapshot regeneration should be minimal; the CLI parser snapshot may need regeneration if it captures handler names.
3. Run cross-format grep checks over `.py`, `.json`, `.md`, `.yaml`, `.yml` for stale identifiers, excluding the zones defined in the vocabulary map (Step 1.5): `dispatch_execute_auto_loop`, `dispatch_execute_one_batch`, `HumanGateStep`, `STATE_AWAITING_HUMAN` (constant only, not string value), `ActiveStep` (TypedDict only), `active_step` objects writing `"step"` (the TypedDict field, not history entries), and pipeline-dataclass `Verdict` references (class construction/annotation, not domain prose in non-pipeline files, and not the bakeoff `JudgeVerdict` TypedDict or audits `EvaluatorVerdict` TypedDict). Exclusion zones from vocabulary map apply: `docs/archive/**`, `briefs/**`, `CHANGELOG.md`, `**/__pycache__/**`, `docs/yaml-pipelines-migration.md`, `docs/foundation-audit/**`, generated/vendored agent material under `megaplan/agent/**` except active source.
4. Run the broader relevant suite if focused tests pass.

## Execution Order
1. Land `docs/canonical-vocabulary.md` first (includes exclusion zones, Verdict prose rule, and the three Verdict-class-bearing concepts: PipelineVerdict, JudgeVerdict, EvaluatorVerdict).
2. Apply both dead aliases (Step 2) and `Backend` canonicalization (Step 3) before riskier renames.
3. Rename `HumanGateStep` (Step 4), then perform the `gate_carry` migration and prompt tests (Step 5).
4. Rename the state constant (Step 6), then active metadata vocabulary (Step 7).
5. Rename `Verdict` to `PipelineVerdict` (Step 8) after the smaller vocabulary changes are stable.
6. Add critique/review invariant docs last (Step 9).
7. Finish with grep verification and M0 baselines (Step 10).

## Ambiguities To Resolve During Implementation
- Whether external users require a temporary `Verdict = PipelineVerdict` alias. Default: no alias, because the done criteria require stale identifier greps to go clean for active code.
- Whether top-level `active_step` should be renamed to `active_phase`. Default: no; the milestone identifies the inner `"step"` key as the real homonym, and renaming the top-level persisted key would materially expand migration scope.
- Whether any file outside the explicit file lists in Steps 7 and 8 reads the inner `"step"` key from `active_step` or imports `Verdict` from `_pipeline.types`. The grep-based verification in Step 10.3 catches these; a pre-execution grep for `active.get("step")` and `from megaplan._pipeline.types import Verdict` across active code is recommended before starting Steps 7 and 8.

## Ticket Link Proposal
No open ticket should be marked `resolves_on_complete=true` from this plan. The execute metadata ticket is adjacent to active metadata naming, but M4 does not backfill or repair per-task execute metadata.
