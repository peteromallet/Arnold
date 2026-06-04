# M5b Plugin Relocation Map

> **Status:** Settled (derived from M-1 `docs/arnold/package-disposition.yaml`)
> **Canonical plugin root:** `arnold/pipelines/megaplan/`
> **Last updated:** 2026-06-05 (T20 audit test relocation)

## Overview

This map records the settled source-to-target mappings for the four policy domains moving into the Megaplan plugin under `arnold/pipelines/megaplan/` during M5b: **execute**, **review**, **orchestration**, and **audits**.

Each mapping is grounded in a `megaplan-plugin` disposition row in `docs/arnold/package-disposition.yaml` (the authoritative source of truth). The rendered `package-disposition.md` targets may reference `megaplan/pipelines/megaplan/` — those paths are **stale**. The canonical plugin location for all four domains is **`arnold/pipelines/megaplan/`**.

## Settled Source-to-Target Mappings

### 1. Execute
| Field | Value |
|---|---|
| **Source** | `megaplan/execute/` |
| **Canonical Target** | `arnold/pipelines/megaplan/execute/` |
| **Disposition** | `megaplan-plugin` |
| **Granularity** | `directory` |
| **YAML Row** | `source: megaplan/execute` → `target: megaplan/pipelines/megaplan/execute` (stale target path in rendered MD) |
| **Reason** | Megaplan-specific batch dispatch, tier routing, timeout, merge, and quality helpers. Deep imports from `megaplan._core`, `megaplan.types`, `megaplan.store`, `megaplan.profiles`, `megaplan.workers`. No reusable Arnold substrate. |
| **Key Vocabulary** | `handle_execute_one_batch`, `handle_execute_auto_loop`, `BatchResult`, `_run_and_merge_batch`, `build_monitor_hint` |
| **Cross-domain Dependencies** | Depends on `orchestration.evaluation`, `orchestration.execution_evidence`, and `audits.quality_gates` |

### 2. Orchestration
| Field | Value |
|---|---|
| **Source** | `megaplan/orchestration/` |
| **Canonical Target** | `arnold/pipelines/megaplan/orchestration/` |
| **Disposition** | `megaplan-plugin` |
| **Granularity** | `directory` |
| **YAML Row** | `source: megaplan/orchestration` → `target: megaplan/pipelines/megaplan/orchestration` (stale target path in rendered MD) |
| **Reason** | Megaplan-specific phase-result transport, progress emission, evaluation, gate signals, completion contracts, iteration pressure, and recovery policy. Deep imports from `megaplan.schemas`, `megaplan.store`, `megaplan.types`. No reusable Arnold substrate. |
| **Key Vocabulary** | `PhaseResult`, `ExitKind`, `ProgressContext`, `ProgressEvent`, `gate_signals`, `recovery_policy`, `iteration_pressure` |
| **Cross-domain Dependencies** | Exports `verifiability` (consumed by audits). Must move first (SD1). |

### 3. Review
| Field | Value |
|---|---|
| **Source** | `megaplan/review/` |
| **Canonical Target** | `arnold/pipelines/megaplan/review/` |
| **Disposition** | `megaplan-plugin` |
| **Granularity** | `directory` |
| **YAML Row** | `source: megaplan/review` → `target: megaplan/pipelines/megaplan/review` (stale target path in rendered MD) |
| **Reason** | Megaplan review infrastructure (parallel review, pre-checks, mechanical checks). Imports from `megaplan._core`, `megaplan.prompts.review`, `megaplan.types`, `megaplan.audits.robustness`. No reusable Arnold substrate. |
| **Key Vocabulary** | `run_parallel_review`, `run_pre_checks`, `mechanical_checks`, `ReviewResult` |
| **Cross-domain Dependencies** | Depends on audits (specifically `audits.robustness`) |

### 4. Audits
| Field | Value |
|---|---|
| **Source** | `megaplan/audits/` |
| **Canonical Target** | `arnold/pipelines/megaplan/audits/` |
| **Disposition** | `megaplan-plugin` |
| **Granularity** | `directory` |
| **YAML Row** | `source: megaplan/audits` → `target: megaplan/pipelines/megaplan/audits` (stale target path in rendered MD) |
| **Reason** | Megaplan audit infrastructure (audit engine, capabilities, critique evaluator, hermes vendoring, iteration, robustness, verifiability). Imports from `megaplan._core`, `megaplan.orchestration.verifiability`, `megaplan.types`, `megaplan.store`. |
| **Key Vocabulary** | `audit_engine`, `record_tiebreaker_audit`, `CRITIQUE_CHECKS`, `validate_robustness`, `capabilities` |
| **Cross-domain Dependencies** | Depends on `orchestration.verifiability` |
| **Note** | `quality_gates.py` has zero megaplan imports — a reusable Arnold substrate candidate — but remains under this directory until the package can be split. |

## Canonical Plugin Root

The canonical plugin root for all four domains is:

```
arnold/pipelines/megaplan/
```

This directory already contains `__init__.py`, `pipeline.py`, `operations.py`, `routing.py`, `stages/`, and `handlers/`. The four domains will be added as sibling subdirectories:

```
arnold/pipelines/megaplan/
├── __init__.py
├── pipeline.py
├── operations.py
├── routing.py
├── stages/
├── handlers/
├── orchestration/   ← moved from megaplan/orchestration/
├── audits/          ← moved from megaplan/audits/
├── review/          ← moved from megaplan/review/
└── execute/         ← moved from megaplan/execute/
```

## Stale Rendered Target Text

The rendered `docs/arnold/package-disposition.md` lists targets as `megaplan/pipelines/megaplan/<domain>` (under the `megaplan/` package). These paths are **stale** — they reflect an earlier naming convention where the plugin lived under `megaplan/pipelines/megaplan/`. The authoritative canonical location is `arnold/pipelines/megaplan/`, as confirmed by:

1. **Done criteria** in the M5b brief: "Execute/review/orchestration policy lives under `arnold/pipelines/megaplan/` or is explicitly classified as neutral service interface."
2. **Existing plugin structure**: `arnold/pipelines/megaplan/` already hosts `__init__.py`, `pipeline.py`, `stages/`, and `handlers/`.
3. **Execution context SD2**: "Moved modules use direct `arnold.pipelines.megaplan.<domain>.*` imports."

The YAML source of truth (`docs/arnold/package-disposition.yaml`) should be updated to reflect the canonical `arnold/pipelines/megaplan/` targets; the rendered markdown will follow.

## Relocation Order

Per SD1 (settled decision), orchestration moves first to satisfy cross-domain import dependencies:

1. **Orchestration** — exports `verifiability`, `evaluation`, `execution_evidence` consumed by audits, review, and execute
2. **Audits** — depends on `orchestration.verifiability`
3. **Review** — depends on `audits.robustness`
4. **Execute** — depends on `orchestration.evaluation`, `orchestration.execution_evidence`, `audits.quality_gates`

## Import Policy (SD2)

Moved modules must use direct plugin-local imports:

```python
# Correct (inside moved code)
from arnold.pipelines.megaplan.orchestration.verifiability import verify_warrant
from arnold.pipelines.megaplan.audits.quality_gates import check_quality_gates

# Incorrect (old shim paths — not for intra-plugin use)
from megaplan.orchestration.verifiability import verify_warrant
```

Old `megaplan.<domain>.*` paths remain as thin public-compatibility facades until M7 (SD2).

## Handler Note (SD3)

Handlers stay physically under `megaplan/handlers/` for M5b. Their imports will be rewritten to plugin-local paths in a single pass after all four domains have moved. The canonical handler location is `arnold/pipelines/megaplan/handlers/`.

## Service-Interface Candidates

Per the brief, the following modules were evaluated for `arnold-service-interface` classification:

- `megaplan/audits/quality_gates.py` — zero megaplan imports; pure quality-gate primitives. Candidate for `arnold-service-interface` split (deferred to post-M5b package split).

No other orchestration/execute/review/audit modules qualify as service interfaces. All four domains are fully `megaplan-plugin` per M-1.

## Module Inventory & Classification

> **Last updated:** 2026-06-04 (T17 test relocation, T2 inventory pass)
> **Legend:** `[I]` = Implementation, `[F]` = Public Facade, `[S]` = Deprecated Shim, `[P]` = Package Init

### Execute (`megaplan/execute/`) — 12 files

| File | Class | Rationale |
|------|-------|-----------|
| `__init__.py` | **[F] Public Facade** | Re-exports names from submodules to preserve `from megaplan.execute import X` compatibility. |
| `core.py` | **[S] Deprecated Shim** | Docstring: "Compatibility facade for legacy `megaplan.execute.core` imports." Delegates to `batch`, `aggregation`, `merge`, `quality`. |
| `batch.py` | **[I] Implementation** | Core batch dispatch: `handle_execute_one_batch`, `handle_execute_auto_loop`, `BatchResult`, `_run_and_merge_batch`, `build_monitor_hint`, `build_blocking_reasons`. 1657 lines. Imports from `megaplan._core`, `megaplan._pipeline.flags`, `megaplan.audits.quality_gates`, `megaplan.orchestration.execution_evidence`, `megaplan.workers`. |
| `quality.py` | **[I] Implementation** | Quality checks: `_check_done_task_evidence`, `_capture_git_status_snapshot`, `run_quality_checks`. 538 lines. Imports from `megaplan.audits.quality_gates`, `megaplan.loop.git`. |
| `merge.py` | **[I] Implementation** | Batch merge/validation: `_validate_and_merge_batch`, `_merge_batch_results`, `_FIELD_ALIASES`, `TERMINAL_TASK_STATUSES`. 540 lines. Imports from `megaplan._core`, `megaplan.forms.stance`, `megaplan.types`. |
| `timeout.py` | **[I] Implementation** | Timeout handling: `_resolve_execute_approval_mode`, `_merge_timeout_checkpoint`, `_recover_execute_timeout`. 341 lines. Imports from `megaplan.orchestration.evaluation`, `megaplan.execute.quality`, `megaplan.execute.merge`, `megaplan.types`, `megaplan.planning.state`, `megaplan.workers`. |
| `aggregation.py` | **[I] Implementation** | Aggregation helpers: `_build_aggregate_execution_payload`, `_compute_execute_scope_drift`, `_stable_unique_strings`. 263 lines. Imports from `megaplan._core`, `megaplan.execute.quality`, `megaplan.forms.directors_notes`, `megaplan.forms.provocations`, `megaplan.receipts.drift`, `megaplan.types`. |
| `step_edit.py` | **[I] Implementation** | Step editing: `handle_step`, `next_plan_artifact_name`. 279 lines. Imports from `megaplan._core`, `megaplan.orchestration.evaluation`, `megaplan.types`, `megaplan.planning.state`. |
| `_envelope.py` | **[I] Implementation** | Feature flag: `unified_execute_enabled()`. 24 lines. Zero megaplan imports (pure stdlib). |
| `_binding/__init__.py` | **[P] Package Init** | Package docstring for `_binding/`. No imports. |
| `_binding/reducer.py` | **[I] Implementation** | Planning reducer: `BatchOutcome`, `BatchReduceResult`, `reduce_batch`, `apply_outcome_to_state`. 160 lines. Imports from `megaplan._core.scheduler.types`, `megaplan.execute`, `megaplan.execute.merge`, `megaplan.planning.state`. |
| `_binding/tier.py` | **[I] Implementation** | Tier binding: `COMPLEXITY_SCALE`, `COMPLEXITY_RUBRIC_REFERENCE`, `validate_task_complexity`, `select_batch_tier`. 78 lines. Imports from `megaplan._core.io`. |

### Review (`megaplan/review/`) — 4 files

| File | Class | Rationale |
|------|-------|-----------|
| `__init__.py` | **[F] Public Facade** | Re-exports names from `parallel`, `checks`, `mechanical` for backward compatibility. |
| `parallel.py` | **[I] Implementation** | Parallel review runner: `run_parallel_review`. 262 lines. Imports from `megaplan._core`, `megaplan.prompts.review`, `megaplan.types`, `megaplan.workers`, `megaplan.runtime.key_pool`. |
| `mechanical.py` | **[I] Implementation** | Pre-checks: `run_pre_checks`. 396 lines. Imports from `megaplan._core`, `megaplan.types`. |
| `checks.py` | **[I] Implementation** | Review check registry: `REVIEW_CHECKS`, `ReviewCheckSpec`, `checks_for_robustness`, `get_check_by_id`. 211 lines. Zero megaplan imports (pure data/helpers). Mirrors `megaplan.audits.robustness`. |

### Orchestration (`megaplan/orchestration/`) — 26 files

| File | Class | Rationale |
|------|-------|-----------|
| `__init__.py` | **[P] Package Init** | Lazy — no eager imports to avoid circular-import drift with `megaplan._core` and `megaplan.store`. |
| `evaluation.py` | **[S] Deprecated Shim** | Docstring: "Compatibility facade for orchestration evaluation helpers." Re-exports from `execution_evidence`, `gate_checks`, `gate_signals`, `plan_structure`, `rubber_stamp`. Also imports `megaplan.loop.git`. |
| `execution_evidence.py` | **[I] Implementation** | Evidence validation: `validate_execution_evidence`. 240 lines. Imports from `megaplan.types`, `megaplan._core`, `megaplan.loop.git`, `megaplan.receipts.drift`, `.rubber_stamp`. |
| `verifiability.py` | **[I] Implementation** | Pure-Python capability matching: `CriterionAudit`, `audit_criteria`, `classify_criteria`, `validate_requires`. 125 lines. Imports from `megaplan.runtime.capabilities`. **Key cross-domain export** (consumed by audits). |
| `progress.py` | **[I] Implementation** | Progress event emission: `ProgressContext`, `ProgressEmitter`. 207 lines. Imports from `megaplan.schemas`, `megaplan.store`. |
| `gate_checks.py` | **[I] Implementation** | Gate preflight: `AGENT_AVAILABILITY_PREFLIGHT_CHECKS`, `run_gate_checks`, `build_gate_artifact`, `build_orchestrator_guidance`. 155 lines. Imports from `megaplan.schemas.planning`, `megaplan.types`, `megaplan._core`. |
| `gate_signals.py` | **[I] Implementation** | Gate-signal scoring: `build_gate_signals`, `compute_plan_delta_percent`, `compute_recurring_critiques`, `flag_weight`. 248 lines. Imports from `megaplan.orchestration.critique_status`, `megaplan.schemas.planning`, `megaplan.types`, `megaplan._core`. |
| `completion_contract.py` | **[I] Implementation** | Completion verification (shadow mode): `CompletionVerdict`, `compute_verdict`. 1399 lines. Imports from `megaplan.orchestration.suite_runner`, `megaplan.schemas`, `megaplan.types`. |
| `completion_io.py` | **[I] Implementation** | Atomic read/write: `write_completion_verdict`, `read_completion_verdict`. 43 lines. Imports from `megaplan.orchestration.completion_contract`, `megaplan._core.io`. |
| `phase_result.py` | **[I] Implementation** | Phase-result transport: `PhaseResult`, `ExitKind`, `BlockedTask`, `Deviation`, `_emit_phase_result`, `phase_result_guard`, `read_phase_result`. 620 lines. Pure stdlib + `megaplan.schemas` (type ref only). |
| `phase_result_classify.py` | **[I] Implementation** | Classification helpers: `_extract_status_code`, `_extract_retry_after`, `_extract_request_id`. 140 lines. Zero megaplan imports (pure stdlib). |
| `iteration_pressure.py` | **[I] Implementation** | Iteration-pressure analysis: `IterationPressureEntry`, `compute_flag_history`, `compute_fuzzy_groups`, `compute_iteration_pressure`. 166 lines. Imports from `megaplan._core.registries`, `megaplan._core.io`, `megaplan.types`. |
| `rubber_stamp.py` | **[I] Implementation** | Rubber-stamp detection: `is_rubber_stamp`, `_is_perfunctory_ack`. 43 lines. Imports from `megaplan._core`. |
| `oracle.py` | **[I] Implementation** | Typed subprocess oracle: `OracleResult`, `run`. 73 lines. Zero megaplan imports (pure stdlib). |
| `prep_research.py` | **[I] Implementation** | Prep research: `triage_task`, `research_task`, `distill_research`. 1130 lines. Imports from `megaplan._core`, `megaplan._core.process_fanout`, `megaplan.profiles`, `megaplan.prompts`, `megaplan.schemas`, `megaplan.types`, `megaplan.workers`. |
| `parallel_critique.py` | **[I] Implementation** | Parallel critique runner: `run_parallel_critique`. 507 lines. Imports from `megaplan._core`, `megaplan.orchestration.critique_status`, `megaplan.prompts.critique`, `megaplan.pipelines.creative.prompts.critique_joke`, `megaplan.types`, `megaplan.workers`. |
| `plan_structure.py` | **[I] Implementation** | Plan parsing: `PLAN_STRUCTURE_REQUIRED_STEP_ISSUE`, `PlanSection`, `parse_plan_sections`, `validate_plan_structure`, `renumber_steps`, `reassemble_plan`. 169 lines. Zero megaplan imports (pure stdlib). |
| `plan_contracts.py` | **[I] Implementation** | Contract helpers: `normalize_contract_payload`. 299 lines. Zero megaplan imports (pure stdlib). |
| `critique_status.py` | **[I] Implementation** | Status helpers: `UNVERIFIABLE_STATUS`, `is_unverifiable_check`, `annotate_unverifiable_checks`, `unverifiable_detail`, `build_unverifiable_warnings`. 145 lines. Zero megaplan imports (pure stdlib). |
| `suite_runs_log.py` | **[I] Implementation** | Append-only log: `append_suite_run`. 129 lines. Imports from `megaplan.orchestration.suite_runner`, `megaplan._core.io`. |
| `feedback.py` | **[I] Implementation** | Feedback template: `load_feedback`, `scaffold_feedback`. 312 lines. Zero megaplan imports (pure stdlib). |
| `plan_audit.py` | **[I] Implementation** | Tiebreaker audit: `record_tiebreaker_audit`, `aggregate_tiebreaker_audit`. 130 lines. Imports from `megaplan._core`. |
| `suite_failure_details.py` | **[I] Implementation** | Failure-detail extraction: `extract_failure_details`. 69 lines. Zero megaplan imports (pure stdlib). |
| `suite_runner.py` | **[I] Implementation** | Test-suite runner: `SuiteRunResult`, `run_suite`. 369 lines. Imports from `megaplan._core.io`, `megaplan.runtime.process`. |
| `tiebreaker.py` | **[I] Implementation** | Tiebreaker subcommand: structured decision support. 293 lines. Imports from `megaplan.profiles`, `megaplan._core`, `megaplan.prompts.tiebreaker_*`, `megaplan.types`, `megaplan.workers`. |
| `recovery_policy.py` | **[I] Implementation** | RecoveryPolicy classifier: `RecoveryPolicy`, `RecoveryDecision`. 355 lines. Zero megaplan imports (pure stdlib dataclasses). |

### Audits (`megaplan/audits/`) — 9 files

| File | Class | Rationale |
|------|-------|-----------|
| `__init__.py` | **[F] Public Facade** | Re-exports names from all submodules for backward compatibility. |
| `verifiability.py` | **[S] Deprecated Shim** | Docstring: "Deprecated compatibility shim — canonical implementation in `megaplan.orchestration.verifiability`." Emits `DeprecationWarning` on import, then `from megaplan.orchestration.verifiability import *`. |
| `capabilities.py` | **[S] Deprecated Shim** | Docstring: "Re-export shim — canonical implementation lives in `megaplan.runtime.capabilities`." Thin `from megaplan.runtime.capabilities import *`. |
| `audit_engine.py` | **[I] Implementation** | Tiebreaker audit engine: `record_tiebreaker_audit`, `aggregate_tiebreaker_audit`, `load_tiebreaker_audit`, `render_audit_report`. 130 lines. Imports from `megaplan._core`. |
| `robustness.py` | **[I] Implementation** | Critique check registry: `CRITIQUE_CHECKS`, `CritiqueCheckSpec`, `checks_for_robustness`, `validate_critique_checks`, `get_check_by_id`. 354 lines. Imports from `megaplan.profiles`. |
| `quality_gates.py` | **[I] Implementation** | Quality gate checks: `run_quality_checks`, `capture_before_line_counts`. 404 lines. **Zero megaplan imports** (pure stdlib + `ast`). Candidate for `arnold-service-interface` split (deferred). |
| `critique_evaluator.py` | **[I] Implementation** | Model roster/ranking: `CRITIC_MODEL_ROSTER`, `validate_evaluator_verdict`, `roster_dispatch_spec`, `assert_adaptive_critique_wired`. 666 lines. Imports from `megaplan.audits.robustness` (lazy). |
| `hermes_vendoring.py` | **[I] Implementation** | Vendored runtime audit: `audit_vendored_agent_history`, `audit_vendored_agent_tree`, `VendoredAgentHistoryAudit`, `VendoredAgentTreeAudit`. 168 lines. Zero megaplan imports (pure stdlib). |
| `iteration.py` | **[I] Implementation** | Iteration-pressure analysis: `IterationPressureEntry`, `compute_flag_history`, `compute_iteration_pressure`, `has_mechanical_recurrence`. 166 lines. Imports from `megaplan._core.registries`, `megaplan._core.io`, `megaplan.types`. |

### Summary

| Domain | Total | [I] Impl | [F] Facade | [S] Shim | [P] Init |
|--------|-------|----------|------------|----------|----------|
| execute | 12 | 9 | 1 | 1 | 1 |
| review | 4 | 3 | 1 | 0 | 0 |
| orchestration | 26 | 24 | 0 | 1 | 1 |
| audits | 9 | 6 | 1 | 2 | 0 |
| **Total** | **51** | **42** | **3** | **4** | **2** |

---

## Consumer Manifest

Discovered via `rg "megaplan\.(execute|review|orchestration|audits)" megaplan arnold tests scripts`.

### 1. Handlers (`megaplan/handlers/`) — 12 files

These stay physically under `megaplan/handlers/` for M5b (SD3). Imports will be rewritten to plugin-local paths in a single pass after all four domains move.

| Handler File | Domains Imported | Key Symbols |
|---|---|---|
| `handlers/execute.py` | execute, orchestration, audits | `handle_execute_one_batch`, `BatchResult`, `_emit_phase_result`, `get_worker_capabilities`, `classify_criteria` |
| `handlers/review.py` | execute, review, orchestration | `build_monitor_hint`, `_check_done_task_evidence`, `_validate_and_merge_batch`, `review_checks`, `is_rubber_stamp`, `_emit_phase_result` |
| `handlers/critique.py` | audits, orchestration, execute | `validate_critique_checks`, `build_gate_artifact`, `build_gate_signals`, `run_parallel_critique`, `_resolve_tier_spec`, `compute_iteration_pressure`, `roster_dispatch_spec` |
| `handlers/gate.py` | orchestration | `build_gate_artifact`, `build_gate_signals`, `build_orchestrator_guidance`, `compute_plan_delta_percent`, `compute_recurring_critiques` |
| `handlers/finalize.py` | orchestration | `normalize_contract_payload`, `run_suite`, `append_suite_run` |
| `handlers/plan.py` | orchestration, audits | `prep_research`, `ALL_CAPABILITIES`, `audit_criteria`, `validate_requires` |
| `handlers/tiebreaker.py` | audits | `record_tiebreaker_audit` |
| `handlers/init.py` | audits | `assert_adaptive_critique_wired` |
| `handlers/override.py` | orchestration | `PLAN_STRUCTURE_REQUIRED_STEP_ISSUE`, `PlanSection`, `parse_plan_sections`, `read_phase_result` |
| `handlers/verifiability.py` | orchestration, audits | `classify_criteria`, `audit_criteria`, `validate_requires`, `get_worker_capabilities` |
| `handlers/shared.py` | execute, orchestration | `build_monitor_hint`, `next_plan_artifact_name`, `phase_result` symbols, `validate_plan_structure` |
| `handlers/__init__.py` | audits, review | `validate_critique_checks`, `run_pre_checks`, `run_parallel_review` |

### 2. Internal Megaplan Consumers (non-handler)

| File | Domains Imported |
|---|---|
| `megaplan/auto.py` | orchestration (`phase_result`, `recovery_policy`), execute (`reconcile_latest_execution_batch` lazy) |
| `megaplan/control.py` | orchestration (`progress`) |
| `megaplan/flags.py` | orchestration (`critique_status`), audits (`robustness` lazy), review (`checks` lazy) |
| `megaplan/run_outcome.py` | execute (`_binding/reducer`) |
| `megaplan/planning/control_binding.py` | orchestration (`evaluation`, `phase_result`) |
| `megaplan/store/plan_repository.py` | orchestration (`feedback`) |
| `megaplan/_core/state.py` | orchestration (`phase_result` lazy) |
| `megaplan/_core/io.py` | orchestration (indirect via state) |
| `megaplan/forms/provocations.py` | audits (`robustness`) |
| `megaplan/cli/__init__.py` | execute (`batch`, `step_edit`) |
| `megaplan/cli/feedback.py` | orchestration (`feedback`) |
| `megaplan/cli/status_view.py` | orchestration (indirect) |
| `megaplan/cli/resolutions.py` | orchestration (indirect) |
| `megaplan/chain/__init__.py` | orchestration (indirect) |
| `megaplan/chain/spec.py` | orchestration (indirect) |
| `megaplan/prompts/tiebreaker_orchestrator.py` | orchestration (by name) |
| `megaplan/prompts/critique.py` | audits (by name) |
| `megaplan/prompts/gate.py` | orchestration (indirect) |
| `megaplan/prompts/feedback.py` | orchestration (by name) |
| `megaplan/prompts/critique_evaluator.py` | audits (by name) |
| `megaplan/workers/hermes.py` | execute (`merge` lazy) |
| `megaplan/workers/_impl.py` | orchestration (indirect) |
| `megaplan/workers/_mock_payloads.py` | orchestration (indirect) |
| `megaplan/observability/doctor.py` | orchestration (indirect) |
| `megaplan/blocker_recovery.py` | execute, orchestration (indirect) |
| `megaplan/auto_escalation.py` | orchestration (indirect) |

### 3. Tests — 50+ files

#### T17 test relocation (M5b batch 17)

Focused execute tests were relocated to `tests/pipelines/megaplan/execute/` during T17.
Monkeypatch targets and direct imports of moved modules were updated to canonical
`arnold.pipelines.megaplan.execute.*` paths. Imports of modules that have NOT been
moved (e.g. `megaplan.execute._binding.*`) were left unchanged.

| Old Location | New Location | Monkeypatch/Import Changes |
|---|---|---|
| `tests/execute/test_envelope_flag.py` | `tests/pipelines/megaplan/execute/test_envelope_flag.py` | `megaplan.execute._envelope` → `arnold.pipelines.megaplan.execute._envelope` (5 reload imports updated) |
| `tests/execute/test_reducer_binding.py` | `tests/pipelines/megaplan/execute/test_reducer_binding.py` | `megaplan.execute.batch` → `arnold.pipelines.megaplan.execute.batch` |
| `tests/execute/test_tier_binding.py` | `tests/pipelines/megaplan/execute/test_tier_binding.py` | No changes (imports `megaplan.execute._binding.tier` — not yet moved) |
| `tests/test_execute_merge.py` | `tests/pipelines/megaplan/execute/test_merge.py` | `megaplan.execute.merge` → `arnold.pipelines.megaplan.execute.merge` |
| `tests/test_execute_merge_creative.py` | `tests/pipelines/megaplan/execute/test_merge_creative.py` | `megaplan.execute.core` → `arnold.pipelines.megaplan.execute.core` |
| `tests/test_execute_batch_prompt.py` | `tests/pipelines/megaplan/execute/test_batch_prompt.py` | No changes (no execute-package imports) |

#### T18 test relocation (M5b batch 18)

Focused review tests were relocated to `tests/pipelines/megaplan/review/` during T18.
Monkeypatch targets and direct imports of moved modules were updated to canonical
`arnold.pipelines.megaplan.review.*` paths. The `megaplan.workers.run_step_with_worker`
monkeypatch target was left unchanged (not a review module).

| Old Location | New Location | Monkeypatch/Import Changes |
|---|---|---|
| `tests/test_review_checks.py` | `tests/pipelines/megaplan/review/test_review_checks.py` | `megaplan.review.checks` → `arnold.pipelines.megaplan.review.checks` |
| `tests/test_review_mechanical.py` | `tests/pipelines/megaplan/review/test_review_mechanical.py` | `megaplan.review.mechanical` → `arnold.pipelines.megaplan.review.mechanical` |
| `tests/test_review_parallel.py` | `tests/pipelines/megaplan/review/test_review_parallel.py` | `megaplan.review.{checks,parallel}` → `arnold.pipelines.megaplan.review.{checks,parallel}`; monkeypatch: `megaplan.review.parallel.{single_check_review_prompt,_resolve_model,scatter_worker_units}` → `arnold.pipelines.megaplan.review.parallel.*` |
|| `tests/test_parallel_review.py` | `tests/pipelines/megaplan/review/test_parallel_review.py` | `megaplan.review.{parallel,checks}` → `arnold.pipelines.megaplan.review.{parallel,checks}`; monkeypatch: `megaplan.review.parallel.{_resolve_model,single_check_review_prompt,scatter_worker_units}` → `arnold.pipelines.megaplan.review.parallel.*`; REPO_ROOT updated parents[1]→parents[4] |

#### T19 test relocation (M5b batch 19)

Focused orchestration tests were relocated to `tests/pipelines/megaplan/orchestration/` during T19.
Monkeypatch targets and direct imports of moved modules were updated to canonical
`arnold.pipelines.megaplan.orchestration.*` paths.

| Old Location | New Location | Monkeypatch/Import Changes |
|---|---|---|
| `tests/test_phase_result.py` | `tests/pipelines/megaplan/orchestration/test_phase_result.py` | `megaplan.orchestration.phase_result` → `arnold.pipelines.megaplan.orchestration.phase_result` |
| `tests/test_recovery_policy.py` | `tests/pipelines/megaplan/orchestration/test_recovery_policy.py` | `megaplan.orchestration.{phase_result,recovery_policy}` → `arnold.pipelines.megaplan.orchestration.{phase_result,recovery_policy}`; importlib path updated |
| `tests/test_progress.py` | `tests/pipelines/megaplan/orchestration/test_progress.py` | `megaplan.orchestration.progress` → `arnold.pipelines.megaplan.orchestration.progress` |
| `tests/test_feedback.py` | `tests/pipelines/megaplan/orchestration/test_feedback.py` | `megaplan.orchestration.feedback` → `arnold.pipelines.megaplan.orchestration.feedback` |

**Concrete exceptions (NOT moved):**

| Test File | Reason |
|---|---|
| `tests/test_execute.py` | Mixed-domain (4629 lines): imports from `megaplan.execute.*`, `megaplan.handlers.*`, `megaplan.workers.*`, `megaplan._core`, `megaplan.cli`, `megaplan.types`. Monkeypatches handler dispatch, worker resolution, git snapshots, CLI config, and execute internals. Too broad for domain-specific relocation. |
| `tests/test_review.py` | Mixed-domain: execute (merge), orchestration (phase_result), review (checks). Documented in mixed-domain table below. |
| `tests/test_doc_mode.py` | Mixed-domain: execute (`timeout`), orchestration (`evaluation`). |
| `tests/test_run_outcome.py` | Mixed-domain: execute (reducer binding) + broader run-outcome surface. |
| `tests/test_receipts_drift_blocking.py` | Cross-cuts execute merge + receipt lifecycle. |
| `tests/characterization/test_import_surface.py` | Characterization test covering import surface across domains — not execute-specific. |
| `tests/characterization/test_pipeline_golden.py` | Golden pipeline tests spanning multiple domains. |
| **Review exceptions (T18):** | |
| `tests/test_handlers_review.py` | Handler test: imports `megaplan.handlers.review` (`_finalize_review_outcome`, `_format_review_success_summary`, `_synthesize_review_rework_items`). Tests handler behavior, not review policy modules directly. |
| `tests/test_handle_review_robustness.py` | Handler/integration test: imports `megaplan.handlers`, bootstraps full plan fixtures, monkeypatches `megaplan._core` internals. Mixed handler+review with heavy test infrastructure. |
| `tests/test_review_stop_affordance.py` | Handler test: imports `megaplan.handlers.review` (`_resolve_review_outcome`). Tests creative stop-signal short-circuit behavior. |
| `tests/test_receipts_review.py` | End-to-end integration: imports `megaplan.handlers`, reuses `test_handle_review_robustness` fixtures. Tests review receipt creation through handler paths. |
| `tests/test_prompts_review.py` | Prompt test: imports `megaplan.prompts.review` (`_review_template_payload`, `_settled_decisions_block`). Tests prompt rendering, not review policy modules. |
| **Orchestration exceptions (T19):** | |
| `tests/test_evaluation.py` | Facade-dependent: imports from `megaplan.orchestration.evaluation` which is a shim re-exporting from 5 canonical modules (`gate_checks`, `gate_signals`, `plan_structure`, `rubber_stamp`, `execution_evidence`). No single canonical `arnold.pipelines.megaplan.orchestration.evaluation` module exists. Monkeypatch targets reference `megaplan.orchestration.evaluation.subprocess.run` which only exists on the facade module object. Splitting imports across 5 canonical sources would require substantial test restructuring. |
| `tests/test_blocker_recovery.py` | Tests `megaplan.blocker_recovery` (not a moved orchestration module). Imports `orchestration.phase_result` but primary module under test is not in the orchestration package. |
| `tests/test_auto_escalation.py` | Tests `megaplan.auto_escalation` (not a moved orchestration module). Uses `orchestration.phase_result` types as input values but primary module is external to orchestration. |
| `tests/test_parallel_critique.py` | Mixed-domain (1052 lines): imports from `megaplan.orchestration.parallel_critique`, `megaplan.audits.robustness`, `megaplan.workers.hermes`, `megaplan.prompts.critique`, `megaplan._core`. Tests span 4 domains. |
| `tests/test_gate.py` | Broad handler/e2e (1832 lines): imports `megaplan.orchestration.evaluation`, `megaplan.handlers`, `megaplan.workers`. Tests gate evaluation through handler dispatch paths. |
| `tests/test_iteration_pressure.py` | Tests `megaplan.audits.iteration` (not a moved orchestration module). The `iteration_pressure` module was moved to orchestration but this test exercises the audits iteration pressure surface. |
| `tests/test_verifiability.py` | Mixed-domain: tests both `megaplan.audits.capabilities` and `megaplan.orchestration.verifiability`, plus `megaplan.handlers.verifiability`. Spans audits + orchestration + handlers. |
| `tests/test_tiebreaker.py` | Tests `megaplan.prompts.tiebreaker_orchestrator` (not a moved orchestration module). The `tiebreaker` module was moved to orchestration but this test exercises the prompts tiebreaker surface. |
| `tests/test_prep.py` | Mixed handler/CLI/receipts (811 lines): imports `megaplan.orchestration.prep_research`, `megaplan.handlers`, `megaplan.cli`, `megaplan.prompts`, `megaplan.receipts`. Spans 4 domains. |
| `tests/test_prep_research.py` | Mixed (1405 lines): imports `megaplan.orchestration.prep_research`, `megaplan._core`, `megaplan.workers`, `megaplan.types`. Broad mock-based test with significant test infrastructure. |
| `tests/test_handler_verifiability.py` | Handler test: imports `megaplan.handlers.verifiability`. Tests handler behavior, not orchestration policy modules. |
| `tests/test_feedback_phase.py` | Handler/mixed test: tests feedback phase through handler dispatch paths. |
| `tests/test_with_feedback.py` | Handler/integration test: tests feedback through handler dispatch paths. |
| `tests/test_tiebreaker_trigger.py` | Handler test: tests tiebreaker trigger through handler dispatch paths. |
| `tests/test_mechanical_gate_e2e.py` | End-to-end gate test spanning handlers + evaluation. |
| `tests/test_m5_eval_gates.py` | Broad evaluation gates test spanning multiple domains. |
| `tests/test_gate_grep_ratchet.py` | Broad ratchet test for gate evaluation patterns. |
| `tests/test_completion_enforce.py` | Broad completion enforcement test spanning orchestration + execution. |
| `tests/test_pipeline_tiebreaker_subloop.py` | Broad pipeline subloop test spanning orchestration + pipeline infrastructure. |
| `tests/test_override_strict_notes.py` | Mixed: imports `orchestration.phase_result` but primary focus is planning state + user actions override enforcement. |
| `tests/test_progress_stall_watchdog.py` | API stall watchdog test (not an orchestration module test). Tests stream progress watchdog, not orchestration progress module. |

#### T20 audit test relocation (M5b batch 20)

Focused audit tests were relocated to `tests/pipelines/megaplan/audits/` during T20.
Direct imports of moved audit modules were updated to canonical
`arnold.pipelines.megaplan.audits.*` paths where the canonical module imported cleanly.

| Old Location | New Location | Import Changes |
|---|---|---|---|
| `tests/test_hermes_vendoring_audit.py` | `tests/pipelines/megaplan/audits/test_hermes_vendoring_audit.py` | `megaplan.audits.hermes_vendoring` → `arnold.pipelines.megaplan.audits.hermes_vendoring` |
| `tests/test_checks.py` | `tests/pipelines/megaplan/audits/test_checks.py` | `megaplan.audits.robustness` → `megaplan.audits.robustness` (facade path preserved; canonical `arnold.pipelines.megaplan.audits.robustness` blocked by engine-sn staleness — see deviation note) |
| `tests/test_iteration_pressure.py` | `tests/pipelines/megaplan/audits/test_iteration_pressure.py` | `megaplan.audits.iteration` → `arnold.pipelines.megaplan.audits.iteration`; docstring updated |
| `tests/test_quality.py` | `tests/pipelines/megaplan/audits/test_quality.py` | `megaplan.audits.quality_gates` → `arnold.pipelines.megaplan.audits.quality_gates`; monkeypatch targets (`quality.subprocess`) unchanged — resolves through same subprocess module object |

**Concrete exceptions (NOT moved):**

| Test File | Reason |
|---|---|
| `tests/test_critique_evaluator.py` | Mixed-domain (1099 lines): imports from `megaplan.audits.critique_evaluator`, `megaplan.handlers`, `megaplan.handlers.critique`, `megaplan.workers`, `megaplan.profiles`, `megaplan.audits.robustness`. Tests evaluator through handler dispatch paths — more handler test than pure audit implementation test. |
| `tests/test_verifiability.py` | Mixed-domain (289 lines): imports from `megaplan.audits.capabilities`, `megaplan.orchestration.verifiability`, `megaplan.handlers.verifiability`. Tests audit verifiability facades alongside canonical orchestration verifiability. Spans audits + orchestration + handlers. Also listed under orchestration exceptions (T19). |
| `tests/test_audit_query.py` | CLI/subprocess test (214 lines): runs `megaplan` CLI with receipt audit query. Not a focused audit implementation test — exercises CLI audit query interface. |
| `tests/test_inspector_run_outcome_audit.py` | State/view test (80 lines): tests `planning_run_state_view`, `RunOutcome`, and `_projected_valid_next`. Exercises state projection and run outcome view — not audit implementation. |
| `tests/test_parallel_critique.py` | Mixed-domain (1052 lines): imports `megaplan.audits.robustness` among orchestration/worker/prompt imports. Also listed under orchestration exceptions (T19). |
| `tests/test_prompts_creative.py` | Prompt test: imports `megaplan.audits.robustness` (joke_checks_for_robustness) for prompt construction. Not primarily an audit implementation test. |
| `tests/test_adaptive_critique_wired.py` | Mixed handler/evaluator test: imports `megaplan.audits.critique_evaluator` but primarily tests adaptive critique wiring through handler and prompt layers. |
| `tests/test_hermes_worker_fireworks_streaming.py` | Worker test: imports `megaplan.audits.robustness` (checks_for_robustness) for worker test setup. Not an audit implementation test. |
| `tests/test_joke_mode_smoke.py` | Smoke test: imports `megaplan.audits.robustness` (joke_checks_for_robustness). Not primarily an audit implementation test. |
| `tests/test_evaluation.py` | Facade-dependent: imports `megaplan.audits.robustness` (validate_critique_checks). Also listed under orchestration exceptions (T19). |
| `tests/test_schemas.py` | Schema test: imports `megaplan.audits.critique_evaluator` (validate_evaluator_verdict) inline. Not an audit implementation test. |
| `tests/test_prompts.py` | Prompt test: imports `megaplan.audits.robustness` (checks_for_robustness) inline. Not primarily an audit implementation test. |
| `tests/test_config.py` | Config test: imports `megaplan.audits.robustness` (checks_for_robustness) inside a nested function. Not an audit implementation test. |
| `tests/test_critique.py` | Critique test: imports `megaplan.audits.robustness` (CRITIQUE_CHECKS) in many test functions. Tests critique behavior broadly, not audit robustness module specifically. |

#### Domain-specific tests (single domain focus)
| Domain | Test Files |
|---|---|
| **execute** | `tests/pipelines/megaplan/execute/test_envelope_flag.py`, `tests/pipelines/megaplan/execute/test_reducer_binding.py`, `tests/pipelines/megaplan/execute/test_tier_binding.py`, `tests/pipelines/megaplan/execute/test_merge.py`, `tests/pipelines/megaplan/execute/test_merge_creative.py`, `tests/pipelines/megaplan/execute/test_batch_prompt.py` |
| **review** | `tests/pipelines/megaplan/review/test_parallel_review.py`, `tests/pipelines/megaplan/review/test_review_checks.py`, `tests/pipelines/megaplan/review/test_review_mechanical.py`, `tests/pipelines/megaplan/review/test_review_parallel.py`, `tests/test_handle_review_robustness.py` (handler exception), `tests/test_review.py` (mixed-domain exception) |
| **orchestration** | `tests/pipelines/megaplan/orchestration/test_phase_result.py`, `tests/pipelines/megaplan/orchestration/test_recovery_policy.py`, `tests/pipelines/megaplan/orchestration/test_progress.py`, `tests/pipelines/megaplan/orchestration/test_feedback.py`, `tests/test_evaluation.py` (facade exception), `tests/test_parallel_critique.py` (mixed-domain exception), `tests/test_prep_research.py` (mixed-domain exception), `tests/test_iteration_pressure.py` (audits exception), `tests/test_blocker_recovery.py` (blocker exception), `tests/test_auto_escalation.py` (auto exception), `tests/test_gate.py` (handler/e2e exception), `tests/test_verifiability.py` (mixed-domain exception), `tests/test_tiebreaker.py` (prompts exception), `tests/test_prep.py` (handler/CLI exception), `tests/test_feedback_phase.py` (handler exception), `tests/test_with_feedback.py` (handler exception), `tests/test_tiebreaker_trigger.py` (handler exception), `tests/test_handler_verifiability.py` (handler exception), `tests/test_mechanical_gate_e2e.py` (e2e exception), `tests/test_m5_eval_gates.py` (broad exception), `tests/test_gate_grep_ratchet.py` (broad exception), `tests/test_completion_enforce.py` (broad exception), `tests/test_pipeline_tiebreaker_subloop.py` (broad exception), `tests/test_override_strict_notes.py` (mixed exception), `tests/test_progress_stall_watchdog.py` (watchdog exception) |
| **audits** | `tests/pipelines/megaplan/audits/test_hermes_vendoring_audit.py`, `tests/pipelines/megaplan/audits/test_checks.py`, `tests/pipelines/megaplan/audits/test_iteration_pressure.py`, `tests/pipelines/megaplan/audits/test_quality.py`, `tests/test_critique_evaluator.py` (handler exception), `tests/test_verifiability.py` (mixed exception), `tests/test_audit_query.py` (CLI exception), `tests/test_inspector_run_outcome_audit.py` (state/view exception), `tests/test_adaptive_critique_wired.py` (handler/evaluator exception), `tests/test_prompts.py` (prompt exception), `tests/test_prompts_creative.py` (prompt exception), `tests/test_parallel_critique.py` (mixed exception), `tests/test_schemas.py` (schema exception), `tests/test_config.py` (config exception), `tests/test_critique.py` (critique exception), `tests/test_evaluation.py` (facade exception), `tests/test_hermes_worker_fireworks_streaming.py` (worker exception), `tests/test_joke_mode_smoke.py` (smoke exception) |

#### Mixed-domain tests
| Test File | Domains |
|---|---|
| `tests/test_execute.py` | execute (batch, core, aggregation, quality, merge), handlers (execute, critique), workers, CLI, _core — broad integration surface; stays at top level as a T17 exception |
| `tests/test_review.py` | execute, orchestration, review (merge, phase_result, review checks) |
| `tests/test_creative_mode_smoke.py` | execute (`core`), audits (`robustness`) |
| `tests/test_joke_mode_smoke.py` | audits (`robustness`) |
| `tests/test_doc_mode.py` | execute (`timeout`), orchestration (`evaluation`) |
| `tests/test_control.py` | orchestration (`progress`) |
| `tests/test_override_strict_notes.py` | orchestration (`phase_result`) |
| `tests/conftest.py` | orchestration (`phase_result`) |
| `tests/oracles/test_replay_oracle.py` | orchestration (`phase_result`) |
| `tests/characterization/test_auto_drive.py` | orchestration (`phase_result`) |
| `tests/characterization/test_blocked_retry_byte_stability.py` | orchestration (`phase_result`) |

#### Golden recorders (reference execution snapshots)
| File | Domains |
|---|---|
| `tests/characterization/_golden_recorders/blocked_retry_golden.py` | orchestration (`ExitKind`, `RecoveryPolicy`) |
| `tests/characterization/_golden_recorders/context_retry_golden.py` | orchestration (`RecoveryPolicy`) |
| `tests/characterization/_golden_recorders/external_retry_golden.py` | orchestration (`ExitKind`, `RecoveryPolicy`) |

### 4. Scripts
| File | Domain | Import |
|---|---|---|
| `scripts/m4_oracle_bisect.py` | orchestration | `from megaplan.orchestration.oracle import OracleResult, run` |

### 5. Arnold Plugin (`arnold/pipelines/megaplan/`)
**Zero current imports** from `megaplan.execute|review|orchestration|audits`. Stages under `stages/` reference megaplan indirectly through the handler dispatch mechanism. Will be wired with plugin-local imports after domain moves.

### 6. Lazy Export Patterns
- `megaplan/audits/__init__.py`: `from megaplan.orchestration.verifiability import ...` (cross-domain re-export)
- `megaplan/execute/core.py`: `from megaplan.execute.{batch,aggregation,merge,quality} import ...` (shim re-export)
- `megaplan/orchestration/evaluation.py`: `from megaplan.orchestration.{execution_evidence,gate_checks,gate_signals,plan_structure,rubber_stamp} import ...` (shim re-export)
- `megaplan/audits/verifiability.py`: `from megaplan.orchestration.verifiability import *` (deprecated re-export with warning)
- `megaplan/audits/capabilities.py`: `from megaplan.runtime.capabilities import *` (thin re-export)
- Lazy imports inside functions: `handlers/critique.py` (execute.batch, audits.critique_evaluator, audits.iteration), `handlers/plan.py` (orchestration.prep_research), `handlers/verifiability.py` (orchestration.verifiability, audits.capabilities), `handlers/execute.py` (audits.capabilities, orchestration.verifiability), `handlers/review.py` (orchestration.phase_result), `handlers/gate.py` (inline), `handlers/finalize.py` (orchestration.suite_runner), `handlers/init.py` (audits.critique_evaluator), `auto.py` (execute.merge), `_core/state.py` (orchestration.phase_result), `workers/hermes.py` (execute.merge), `flags.py` (audits.robustness, review.checks)

---

## Reference

- Authoritative YAML: `docs/arnold/package-disposition.yaml`
- Validator: `scripts/validate_package_disposition.py`
- Renderer: `scripts/render_package_disposition_md.py`
- M5b Brief: `.megaplan/briefs/arnold-megaplan-cleanup/m5b-execute-review-orchestration-policy.md`
