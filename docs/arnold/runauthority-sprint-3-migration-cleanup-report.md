# RunAuthority Sprint 3 — Consumer Migration And Compatibility Cleanup Report

**Date:** 2026-07-11
**Sprint:** Sprint 3 — Consumer Migration And Compatibility Cleanup
**Artifact:** Cleanup report per success criterion "Legacy/raw authority-reader paths are either removed, demoted to compatibility projections, or explicitly listed with blockers."

---

## 1. Executive Summary

Sprint 3 migrated five sibling authority views (Execution, Runner, Publication, Human Gate, Recovery) into a composed `MegaplanPlanView` facade and rewired four downstream consumer families — cloud status, human-gate controls, repair/recovery dispatch, and chain/supervisor aggregation — to consume view-backed projections. **One route (CHAIN-01) reached full enforcement** with accepted-attempt projections. **Twenty-two routes operate in warn-only mode** with drift diagnostics and legacy fallback. **One duplicate raw reader (SUP-01) was quarantined.** **Five status/shadow routes were deferred** to a later milestone.

All consumer migrations preserve fail-open semantics: drift diagnostics are observable but never override the legacy decision path. The `status_consumers_unchanged: True` contract is preserved for cloud status consumers.

---

## 2. View Architecture

### 2.1 Sibling Views (Five Separated Read-Only Domains)

All views live in `arnold_pipelines/megaplan/authority/views.py` and are exported from `arnold_pipelines/megaplan/authority/__init__.py`.

| View | Dataclass | Derivation | Key Diagnostics |
|------|-----------|------------|-----------------|
| **Execution** | `PlanExecutionView` | `derive_plan_execution_view(...)` | Accepted-attempt projections, task DAG, dispatch grants, coordinator fences |
| **Runner** | `RunnerView` | (existing, pre-Sprint-3) | Liveness, tmux, watchdog taxonomy |
| **Publication** | `PublicationView` | `derive_publication_view(...)` | Branch ancestry (T6), auth, push, PR, dirty workspace, no_push |
| **Human Gate** | `HumanGateView` | `derive_human_gate_view(...)` (T2) | Stale-token detection, superseded-override evidence, needs-human observations |
| **Recovery** | `MegaplanRecoveryView` | `derive_megaplan_recovery_view(...)` (T4) | Repair custody bucket, permitted actions, runner liveness cross-checks, publication blockers, stale active steps |

### 2.2 Composition Facade

`MegaplanPlanView` (T7) composes all five sibling views into a single deterministic hash without re-deriving them. Each sub-view retains its own independently-computed hash. The facade is marked `shadow=True`, `read_only=True` and adds no new policy.

---

## 3. Enforced Surfaces

### 3.1 CHAIN-01 — Fully Enforced

- **Route:** `arnold_pipelines/megaplan/chain/__init__.py` lines 1742–1968
- **Function:** `_latest_execution_batch_all_tasks_done`
- **Disposition:** **ENFORCED**
- **What changed:** This function now exclusively uses `effective_execute_completed_task_ids`, which is backed by accepted-attempt projections, dispatch grants, coordinator fences, and evidence envelopes (the full `run_authority` reducer pipeline). The previous batch-artifact + `finalize.json` raw-status reads are no longer the primary decision path.
- **Justification:** This is the only route where the authority path fully controls the completion decision. The accepted-attempt pipeline was already proven equivalent by Sprint 1 and Sprint 2 tests.
- **Tests:** Covered by `tests/arnold_pipelines/run_authority/test_reducer.py` (11 tests), `tests/arnold_pipelines/megaplan/test_authority_views.py` (38 tests including 16 recovery-view), `tests/arnold_pipelines/megaplan/test_chain_authority_shadow.py`, and cross-suite chain/supervisor tests.

**This is the only enforced route in Sprint 3.** All other migrated consumers remain warn-only per SD2/SD3.

---

## 4. Compatibility Surfaces (Warn-Only With Drift Diagnostics)

Twenty-two routes operate in **warn-only** mode. In each case:
- An authority adapter or view-backed projection exists and produces drift diagnostics on disagreement.
- The legacy decision path is preserved as the effective outcome (fail-open).
- No raw authority readers were removed without equivalence coverage.

### 4.1 Execute Family (9 routes: EXEC-01 through EXEC-09)

All execute-family routes in `arnold_pipelines/megaplan/execute/batch.py`, `_core/io.py`, `_core/scheduler/topo.py`, `_binding/reducer.py`, `execute/timeout.py`, and `prompts/execute.py` continue to read raw task status. Downstream consumers (chain, supervisor) use `effective_execute_completed_task_ids` which is authority-backed. Batch.py source-level migration is deferred but all consumers are protected.

- **Drift surface:** `_latest_execution_batch_all_tasks_done` (CHAIN-01, enforced) cross-checks raw batch status against accepted-attempt projections.
- **Rollback seam:** Reverting batch.py to raw reads would not break chain/supervisor — they already use the authority-backed path.

### 4.2 Resume / Redrive Family (4 routes: RESUME-01 through RESUME-04)

- **RESUME-01** (`_core/workflow.py`): Control interface rewired (T9) with `source_view_hash`/`source_view_revision` on override receipts. Compatibility path preserved for callers without view hash.
- **RESUME-02** (`_pipeline/resume.py`): Cursor payload preservation available for guard annotation; not yet gated on authority.
- **RESUME-03** (`auto.py`, `_active_phase_already_completed`): Human gate and control interface rewired (T9/T10); active-phase completion still legacy-trusting.
- **RESUME-04** (`auto.py`, terminal success signaling): Human gate rewired with view hash/revision; terminal success gating produces drift diagnostics but legacy outcome preserved.

### 4.3 Chain Family (4 routes: CHAIN-02 through CHAIN-05)

- **CHAIN-02** (`_handle_outcome`): Authority drift diagnostics captured via epic chain aggregation (T11); legacy ADVANCE decision preserved.
- **CHAIN-03** (`_recover_blocked_execute_if_tasks_done`): Delegates to CHAIN-01 (enforced) for completion check; recovery decision itself is fail-open per T12.
- **CHAIN-04** (seed plan terminal skip): Authority drift captured via epic chain aggregation (T11); legacy terminal-state comparison preserved.
- **CHAIN-05** (current_plan_name pointer reads): Informational pointer reads are safe; skip/advance cross-checked with authority drift diagnostics (T11/T12).

### 4.4 Supervisor Family (4 routes: SUP-01 through SUP-04)

- **SUP-01** (`_recover_blocked_execute_if_tasks_done`): **QUARANTINED** as duplicate of CHAIN-03. Equivalence covered by shared `effective_execute_completed_task_ids` and `_latest_execution_batch_all_tasks_done`.
- **SUP-02** (`_assert_dependencies_completed`): Authority shadow derivation wired (T12); cross-checks ladder ADVANCE against authority-backed completion.
- **SUP-03** (milestone advancement loop): Authority shadow derivation wired (T12) for ADVANCE and PR-merge paths.
- **SUP-04** (dependency gates, PR-merge advancement): Same authority semantics as canonical chain (T12); divergence captured as diagnostic.

### 4.5 Timeout Family (1 route: TIMEOUT-01)

Best-effort corroborated completion via `effective_execute_completed_task_ids`; uncorroborated tasks labelled as `asserted_terminal`; fail-open (SD3).

---

## 5. Retired / Quarantined Raw Readers

| Route | File | Disposition | Reason |
|-------|------|-------------|--------|
| **SUP-01** | `arnold_pipelines/megaplan/supervisor/chain_runner.py` (875-930) | **QUARANTINED** (warn-only) | Exact duplicate of CHAIN-03. Both call the same `_latest_execution_batch_all_tasks_done` helper backed by accepted-attempt projections. Equivalence coverage via shared authority helper. Not removed — marked duplicate with cross-reference. |

No raw readers were physically removed. The one duplicate was explicitly quarantined with a cross-reference to its canonical counterpart.

---

## 6. Deferred Routes

Five routes are deferred to a later milestone:

| Route | File | Reason |
|-------|------|--------|
| **STATUS-02** | `auto.py` (1395-1455) | Completion contract enforcement is a later milestone concern; shadow/warn modes are fail-open |
| **STATUS-03** | `chain/__init__.py` (465-500) | Documented as SHADOW-ONLY, fail-open, never blocks advancement |
| **STATUS-04** | `orchestration/completion_contract.py` (1698) | Shadow-only with SHADOW_TODOS; deliberately not enforcement per M2 scope boundary (SD2) |
| **STATUS-05** | `auto.py` (1406-1436) | Shadow verdict path; evidence/shadow infrastructure, not authority enforcement |
| **STATUS-06** | `chain/__init__.py` (485-525) | Shadow verdict path; fail-open, non-blocking in shadow/warn modes |

**STATUS-01** remains **INFORMATIONAL** (read-only operator visibility, does not increase authority).

---

## 7. Rollback Seams

Every consumer migration in Sprint 3 preserves a rollback seam:

### 7.1 Fail-Open Design Pattern

All 22 warn-only routes and all 5 deferred routes preserve the legacy decision path as the effective outcome. Drift diagnostics are emitted but never override.

### 7.2 Shadow/Warn/Enforce Gating

The `status_consumers_unchanged: True` contract (SD2) is preserved. Cloud status output renders all five domains as shadow/read-only with independent hashes, diagnostics, and source paths. No consumer is promoted to enforce without equivalence diagnostics.

### 7.3 Compatibility Helpers Retained

- `build_needs_human_marker`, `write_needs_human_marker_payload`, `supersede_needs_human_marker`, `clear_needs_human_marker`, `compute_escalation_id` — all retained source-addressable and unchanged (T9).
- `classify_repair_dispatch` with `recovery_view=None` falls through to the existing canonical→legacy dispatch path unchanged (T10).
- `apply_transition` with `source_view_hash=None` continues to work unchanged; compatibility path preserved for all callers without view hash (T9).

### 7.4 Legacy Fallbacks

- Epic chain: `_observe_child_epic` preserves `effective_status` from legacy chain state when authority views disagree (T11).
- Supervisor: `_derive_milestone_authority_shadow` is purely diagnostic — it never blocks milestone advancement (T12).
- Repair dispatch: `classify_repair_dispatch` with `recovery_view=None` falls through to legacy path (T10).

---

## 8. Drift Ledgers

Every consumer migration emits structured drift diagnostics when authority views disagree with legacy readings:

| Drift Ledger | Location | Trigger | Task |
|-------------|----------|---------|------|
| **Epic chain authority drift** | `ObservedChildEpic.authority_drift` + `classification.metadata.epic_chain_authority_drift` | Legacy "complete" but `_plan_terminal_completion_is_authoritative` disagrees | T11 |
| **Supervisor milestone drift** | `_derive_milestone_authority_shadow` → `authority_drift` in milestone result | Ladder ADVANCE disagrees with `_latest_execution_batch_all_tasks_done` | T12 |
| **Repair custody drift** | `_emit_recovery_legacy_custody_drift` | `recovery_view.custody_bucket` disagrees with legacy `custody_projection` | T10 |
| **Repair dispatch drift** | `_emit_dispatch_drift_detected` | `recovery_view` and `canonical_run_state` disagree | T10 |
| **Human-gate stale token** | `HumanGateView.diagnostics` (stale_token) | `plan_ref` mismatch against `current_plan_revision` | T2, T9 |
| **Human-gate superseded override** | `HumanGateView.diagnostics` (superseded_override) | Explicit stale/superseded flags on override signals | T2, T9 |
| **Publication branch ancestry** | `PublicationView.diagnostics` (invalid_branch_ancestry) | `branch_ancestry` value is 'invalid' | T6 |

All drift diagnostics are **observable** (logged, included in status snapshots and cloud shadows) but **non-blocking** — they never revert or override the legacy effective decision.

---

## 9. Test Coverage Per Enforcement Boundary

### 9.1 Core Reducer (RunAuthority)
- **File:** `tests/arnold_pipelines/run_authority/test_reducer.py` — 11 tests
- **Covers:** Replay determinism, crash-restart idempotency, conflicting record exclusion, quarantine determinism, reducer source purity (no Megaplan policy leakage)

### 9.2 Execution Authority Views
- **File:** `tests/arnold_pipelines/megaplan/test_authority_views.py` — 38 tests
- **Covers:** `PlanExecutionView` determinism, `RunnerView` liveness, `PublicationView` (branch ancestry, auth, push, PR, dirty workspace), `MegaplanRecoveryView` (16 recovery-specific tests: custody buckets, permitted actions, cross-checks, determinism, JSON roundtrip), `MegaplanPlanView` facade composition

### 9.3 Human Gate View
- **File:** `tests/arnold_pipelines/megaplan/test_human_gate_view.py` — 62 tests
- **Covers:** Deterministic hashing, source hash/revision binding, stale freshness-token diagnostics, superseded override evidence, needs-human sidecar observation semantics, cross-cutting determinism

### 9.4 Human Blockers
- **File:** `tests/cloud/test_human_blockers.py` — 46 tests
- **Covers:** `HumanGateView` dict presence in `HumanBlockerClassification`, None-when-missing, stale diagnostics, preloaded payload, ledger diagnostics

### 9.5 Cloud Status
- **Files:** `tests/cloud/test_status_snapshot.py`, `tests/arnold_pipelines/megaplan/test_cloud_status_authority_shadow.py`
- **Covers:** Five separated shadow domains with independent hashes, `status_consumers_unchanged: True`, facade composition, source path aggregation

### 9.6 Semantic Health / Control Interface
- **File:** `tests/arnold_pipelines/megaplan/test_semantic_health.py` — 85 tests
- **Covers:** Override receipts with/without `source_view_hash`/`source_view_revision`, compatibility path preservation

### 9.7 Repair / Recovery
- **Files:** `tests/cloud/test_repair_contract.py` (116+ tests), `tests/cloud/test_repair_custody.py`
- **Covers:** Recovery-view dispatch classification, `_classify_from_recovery_view`, custody bucket routing, permitted actions integration, legacy fallback, drift emission

### 9.8 Chain & Supervisor
- **Files:** `tests/arnold_pipelines/megaplan/test_epic_chain.py` (10 tests), supervisor tests woven through chain integration
- **Covers:** Epic chain authority drift capture, `_plan_terminal_completion_is_authoritative` cross-check, supervisor milestone authority shadow derivation

### 9.9 Route Inventory
- **File:** `tests/test_state_reader_audit.py` — 17 tests
- **Covers:** Route disposition vocabulary, valid disposition sets, convenience functions (`enforced_routes`, `warn_only_routes`, `shadow_only_routes`, `deferred_routes`, `informational_routes`)

### 9.10 Authority Inventory
- **File:** `tests/arnold_pipelines/megaplan/test_authority_inventory.py` — 4 tests
- **Covers:** Authority inventory CLI, package exports

---

## 10. Files Changed (Complete Inventory)

### 10.1 Core Authority Views
- `arnold_pipelines/megaplan/authority/views.py` — All five sibling views, composition facade, pure derivation helpers
- `arnold_pipelines/megaplan/authority/__init__.py` — Package exports

### 10.2 Consumer Wiring
- `arnold_pipelines/megaplan/cloud/status_snapshot.py` — `_compose_shadow_views` wired through facade
- `arnold_pipelines/megaplan/cloud/status_format.py` — `_append_shadow_views` renders five domains
- `arnold_pipelines/megaplan/cloud/human_blockers.py` — `HumanBlockerClassification.human_gate_view`, `_derive_human_gate_view_dict`
- `arnold_pipelines/megaplan/cloud/repair_contract.py` — `classify_repair_dispatch` with `recovery_view` parameter
- `arnold_pipelines/megaplan/control_interface.py` — `source_view_hash`/`source_view_revision` on override receipts
- `arnold_pipelines/megaplan/chain/epic_chain.py` — `ObservedChildEpic.authority_drift`, `_plan_terminal_completion_is_authoritative` cross-check
- `arnold_pipelines/megaplan/supervisor/chain_runner.py` — `_derive_milestone_authority_shadow`, authority-gated ADVANCE
- `arnold_pipelines/megaplan/orchestration/authority_readers.py` — Disposition vocabulary, route inventory update

### 10.3 Tests
- `tests/arnold_pipelines/megaplan/test_human_gate_view.py` — 62 tests (T3)
- `tests/arnold_pipelines/megaplan/test_authority_views.py` — Extended with 16 recovery tests (T10)
- `tests/arnold_pipelines/megaplan/test_cloud_status_authority_shadow.py` — Updated for five-domain rendering (T8)
- `tests/arnold_pipelines/megaplan/test_semantic_health.py` — Override receipt tests (T9)
- `tests/arnold_pipelines/megaplan/test_epic_chain.py` — Authority drift tests (T11)
- `tests/cloud/test_human_blockers.py` — HumanGateView integration (T9)
- `tests/cloud/test_repair_contract.py` — Recovery-view dispatch (T10)
- `tests/cloud/test_repair_custody.py` — Recovery-view integration (T10)
- `tests/cloud/test_status_snapshot.py` — Updated for five-domain shadow (T8)
- `tests/test_state_reader_audit.py` — Updated disposition vocabulary (T13)

---

## 11. North Star Compliance

- **Generic kernel separability preserved:** Task DAGs, PR lifecycle, tmux semantics, watchdog taxonomy, prompt contracts, and model routing policy remain outside the generic `run_authority` reducer.
- **Mutable legacy artifacts are observations or compatibility projections, not authority.**
- **Accepted authority traces to revision, attempts, grants, fences, and evidence.**
- **All derivation helpers are pure over already-loaded inputs** — no filesystem, Git, process, API, or wall-clock reads inside reducers or view derivation.
- **Execution, runner, publication, human-gate, and recovery remain sibling domains** — no universal lifecycle enum, no cross-domain authority inference.

---

## 12. Known Baseline Failures (Not Introduced By This Sprint)

Thirteen test files had pre-existing failures before Sprint 3 began. These failures are **unchanged** by this sprint's work:

1. `tests/arnold/pipeline/test_profiles.py`
2. `tests/arnold/pipeline/test_profiles_opaque.py`
3. `tests/arnold_pipelines/megaplan/pipelines/test_native_truth.py`
4. `tests/arnold_pipelines/megaplan/test_anchors.py`
5. `tests/arnold_pipelines/megaplan/test_cli_command_parser_parity.py`
6. `tests/arnold_pipelines/megaplan/test_cli_commands.py`
7. `tests/arnold_pipelines/megaplan/test_hermes_plan_recovery.py`
8. `tests/arnold_pipelines/megaplan/test_native_golden_traces.py`
9. `tests/cli/test_arnold_parser_snapshot.py`
10. `tests/cloud/test_phase_command_shim.py`
11. `tests/m8/regression/test_structural_regressions.py`
12. `tests/megaplan/test_authority_divergence_recovery.py`
13. `tests/test_arnold_cli.py`

*Source: `baseline_test_failures` in `finalize.json`*

---

## 13. Second-Consumer Outcome: `evidence_pack` — Precise Blocker

### 13.1 Inspection Scope

Inspected all six files in `arnold_pipelines/evidence_pack/`:

| File | Lines | Role |
|------|-------|------|
| `__init__.py` | 31 | Package metadata; capabilities: `artifact-verification`, `evidence-pack` |
| `pipeline.py` | 199 | Projected-shell pipeline builder; topology: ingest → content_validators(fanout) → reduce → human_review → emit_attestation |
| `native.py` | 347 | Native runtime phases, decisions, and compiled program entrypoint |
| `steps.py` | 441 | Runtime-agnostic step behaviors: IngestStep, ContentValidatorStep, ReduceStep, HumanReviewStep, EmitAttestationStep |
| `verifier.py` | 342 | Artifact schemas (evidence_pack, checkpoint, verdict, attestation), JSON helpers, Verdict value object |
| `resume.py` | 160 | Resume helpers: native cursor loading, human-review suspension/resumption via `resume_evidence_pack` |

### 13.2 Blocker: Missing Run-Authority Mechanics

The `evidence_pack` pipeline is a self-contained artifact-verification pipeline. It has human-review/checkpoint semantics (suspension via native cursors, human-gate decision routing, checkpoint persistence), but it operates entirely outside the run-authority ecosystem. **Zero references to any run-authority concept exist in the entire module** (confirmed by ripgrep across all six files for `run_revision`, `coordinator_fenc`, `dispatch_grant`, `subject_attempt`, `accepted.attempt`, `evidence_envelope`).

The following five mechanics are absent, each of which is required before `evidence_pack` can consume run-authority views:

#### 13.2.1 Run Revision Binding
- **What's missing:** `evidence_pack` has no `run_revision` parameter on `build_pipeline`, `resume_evidence_pack`, or any step. The pipeline verifies an evidence-pack JSON artifact by its `evidence_pack_id` alone — it does not know which run revision produced the artifact.
- **Why it matters:** Without run-revision binding, the pipeline cannot cross-check whether the evidence pack corresponds to the run revision that the authority views assert is complete. Two different runs could produce evidence packs with the same `evidence_pack_id` at different revisions.
- **Precise gap:** `build_pipeline(name, **_)` would need to accept `run_revision: str | None`; `resume_evidence_pack` would need to bind the native cursor to a specific revision; the ingest step would need to validate that the evidence pack's source revision matches the run revision.

#### 13.2.2 Coordinator Fencing
- **What's missing:** No fence token, lease, or distributed-lock mechanism. Multiple concurrent invocations of `resume_evidence_pack` for the same `artifact_root` could race — the native cursor provides some idempotency but no exclusion guarantee.
- **Why it matters:** Run authority requires that only one coordinator holds the fence at a time for a given run. Evidence-pack verification that runs outside the fence could attest to stale or superseded state.
- **Precise gap:** The pipeline would need to accept a fence token, validate it before executing any phase, and refuse to proceed if the fence has been revoked or transferred.

#### 13.2.3 Dispatch Grants
- **What's missing:** No concept of dispatch grants. The pipeline doesn't check whether it has been granted authority to verify this particular evidence pack. Any caller with access to the artifact root can invoke `resume_evidence_pack`.
- **Why it matters:** The run-authority reducer produces dispatch grants that authorize specific actions on specific runs. Without grant validation, evidence-pack verification is ambient rather than authority-gated.
- **Precise gap:** `build_pipeline` or `resume_evidence_pack` would need to accept a `grant` parameter (or grant envelope), and the ingest phase would need to validate that the grant authorizes evidence-pack verification for the given run revision.

#### 13.2.4 Subject Attempts
- **What's missing:** No attempt tracking — no attempt number, no accepted/rejected distinction, no retry semantics beyond the native cursor's resume capability. The pipeline either succeeds, fails, or suspends; it doesn't distinguish "first attempt failed, retry with different human input" from "attempt accepted as final."
- **Why it matters:** Run authority tracks subject attempts via accepted-attempt projections. Evidence-pack verification that doesn't participate in attempt tracking can't contribute to the authority view's determination of whether all tasks are complete.
- **Precise gap:** The pipeline would need to emit attempt metadata (attempt number, outcome, acceptance envelope) that the run-authority reducer can consume. The resume path would need to create a new attempt on each retry.

#### 13.2.5 Evidence References (to Run-Authority Envelopes)
- **What's missing:** The pipeline has `artifact_refs` within checkpoints and attestations, but these are self-referential — they point to other evidence-pack artifacts (checkpoints, verdicts) within the same verification session. They do not reference run-authority evidence envelopes (accepted-attempt projections, grant ledgers, fence tokens, reducer outputs).
- **Why it matters:** For evidence-pack to serve as a run-authority consumer, its attestation would need to reference the authority evidence that authorized its execution, not just its own internal checkpoint artifacts. Without this, the attestation is provenance-isolated and can't be cross-validated against the authority reducer's output.
- **Precise gap:** The attestation payload would need an `authority_evidence_refs` field containing URIs/hashes of the run-authority evidence envelopes that authorized and accompanied the verification.

### 13.3 Why This Does Not Widen the Generic Kernel

None of the five missing mechanics require changing the generic `run_authority` reducer, the `RunAuthorityView`, or any kernel-level concept:
- **Run revision binding** is Megaplan-local — it's the evidence_pack pipeline that needs to learn about revisions, not the kernel.
- **Coordinator fencing** already exists in Megaplan's coordinator layer; evidence_pack just needs to consume it.
- **Dispatch grants** are already produced by the run-authority reducer; evidence_pack needs to validate them, not produce them.
- **Subject attempts** are already tracked by the reducer; evidence_pack needs to participate in the attempt lifecycle, not redefine it.
- **Evidence references** would point *to* kernel-produced envelopes without adding new policy to the kernel.

All five mechanics are consumer-side concerns — they wire evidence_pack into the existing authority ecosystem without expanding the kernel's scope into artifact verification, evidence-pack schemas, or pipeline topology.

### 13.4 Minimum Viable Wiring Path

When these mechanics are available, the minimum wiring path would be:

1. Accept `run_revision`, `fence_token`, and `dispatch_grant` in `build_pipeline` / `resume_evidence_pack`.
2. Validate the grant and fence in the ingest phase before reading the evidence pack.
3. Bind the evidence-pack's `source_ticket` to the run revision for cross-validation.
4. Emit attempt metadata (`attempt_number`, `outcome`, `acceptance_envelope_ref`) in the attestation phase.
5. Include `authority_evidence_refs` (grant envelope hash, reducer output hash, fence token) in the attestation payload.
6. Register the attestation as a subject-attempt outcome that the run-authority reducer can consume.

### 13.5 Verdict: Precise Blocker (No Bounded Proof Possible Today)

The `evidence_pack` pipeline **cannot** serve as a run-authority consumer in its current state. The five missing mechanics are individually well-defined and bounded, but collectively they represent a non-trivial wiring effort that spans pipeline entrypoints, phase behaviors, schema extensions, and resume paths. None of them require expanding the generic kernel.

**This is recorded as a precise blocker, not as suppressed or deferred work.** The blocker does not block any other Sprint 3 consumer migration — all other consumers (cloud status, human-gate, repair/recovery, chain/supervisor) are independent of evidence_pack.

---

## 14. Open Items For Later Milestones

1. **STATUS-02 through STATUS-06 completion contract enforcement** — Shadow verdict infrastructure exists; enforcement deferred.
2. **Batch.py source-level migration (EXEC-01 through EXEC-09)** — All downstream consumers are protected; batch.py raw reads remain as source-of-truth for batch-level operations.
3. **SUP-01 deduplication** — Quarantined with equivalence coverage; could be collapsed into CHAIN-03 in a future cleanup pass.
4. **Recovery-view test coverage** — `MegaplanRecoveryView` derivation is tested via 16 authority-view tests, but no dedicated `test_recovery_view.py` exists. The view operates in shadow mode so this is non-blocking.
5. **`evidence_pack` second-consumer wiring** — Five mechanics blocked (see §13). Minimum wiring path documented. No kernel changes required.

---

*Report generated as part of Sprint 3 execution batch 15.*
*See also: `finalize.json` for baseline data, `plan_v1.meta.json` for success criteria, and `authority_readers.py` for the authoritative route inventory.*
