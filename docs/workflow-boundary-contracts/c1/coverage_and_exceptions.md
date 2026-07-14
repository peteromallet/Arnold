# C1 Coverage and Exceptions

> Generated for C1 Contract Reality Reconciliation
> Matrix reference: `contract_to_producer_matrix.json`, `source_to_owner_matrix.json`, `support_manifest.json`
> Fixture reference: `tests/fixtures/workflow_boundary_contracts/`
> Applies to: Coverage classification of all 35 boundary contracts; intentional exceptions and known gaps.

## Overview

This document names every coverage classification, stale declaration, missing emitter, and intentional exception in the C1 scope. It is the authoritative record of what C1 can and cannot claim as machine-verified. No coverage is fabricated — every `unknown`, `declared_only`, or `non_conformant` entry here corresponds to a typed marker in the contract-to-producer matrix and is tested by `test_contract_reality_matrices.py` and `test_boundary_compatibility_replay.py`.

---

## 1. Native Parity Coverage

"Native parity" means the boundary contract has a real producer code path in the current codebase and at least one captured fixture bundle exercises that contract structurally.

### 1.1 Full Native Parity (13 contracts)

These contracts have `producer_category` of `auto_matched` or `manual_emit`, a verified handler function, and a captured fixture bundle with complete structural data.

| Boundary ID | Phase | Producer Category | Handler | Fixture Bundle |
|------------|-------|-------------------|---------|---------------|
| `prep_to_plan` | prep | auto_matched | `handlers/init.py` | `captured_bundle_025_prep_to_plan.json` |
| `plan_to_critique` | plan | auto_matched | `handlers/plan.py` | `captured_bundle_000_20260616T192957.json` |
| `critique_to_gate` | critique | auto_matched | `handlers/critique.py` → `orchestration/critique_runtime.py` | `captured_bundle_001_20260616T192957.json` |
| `gate_to_revise` | gate | auto_matched | `handlers/gate.py` | `captured_bundle_015_gate_to_revise.json` |
| `revise_to_critique` | revise | auto_matched | `handlers/revise.py` | `captured_bundle_029_revise_to_critique.json` |
| `execute_approval` | execute | manual_emit | `execute/batch.py:_emit_batch_boundary_receipt` | `captured_bundle_005_execute_approval.json` |
| `execute_approval_denial` | execute | manual_emit | `execute/batch.py:_emit_batch_boundary_receipt` | `captured_bundle_006_execute_approval_denial.json` |
| `execute_batch_checkpoint` | execute | manual_emit | `execute/batch.py:_emit_batch_boundary_receipt` | `captured_bundle_007_execute_batch_checkpoint.json` |
| `execute_partial_failure` | execute | manual_emit | `execute/batch.py:_emit_batch_boundary_receipt` | `captured_bundle_010_execute_partial_failure.json` |
| `execute_blocked_anchor` | execute | manual_emit | `execute/batch.py:_emit_batch_boundary_receipt` | `captured_bundle_008_execute_blocked_anchor.json` |
| `execute_resume_anchor` | execute | manual_emit | `execute/batch.py:_emit_batch_boundary_receipt` | `captured_bundle_011_execute_resume_anchor.json` |
| `execute_aggregate_promotion` | execute | manual_emit | `execute/batch.py:_emit_batch_boundary_receipt` | `captured_bundle_004_execute_aggregate_promotion.json` |
| `execute_no_review_terminal` | execute | manual_emit | `execute/batch.py:_emit_batch_boundary_receipt` | `captured_bundle_009_execute_no_review_terminal.json` |

**Total**: 13 out of 35 contracts (37%) have full native parity.
**Coverage by phase**: S2 front-half (5/5), S4 execute (8/8), S3 tiebreaker (0/4), S5 review (0/5), S5 finalize (0/3), S6 override (0/8), S3 replan (0/1), S3 parent_rejoin (0/1).

### 1.2 Real Producer Cases (T18)

The `real_producer_cases.bundle.json` provides 16 cases (8 healthy + 8 broken) covering all 8 required phase families:

| Phase Family | Healthy Case | Broken Case (one corruption) |
|-------------|-------------|------------------------------|
| prep | `prep_to_plan` (compatible) | Missing boundary receipt → incompatible |
| plan_revise | `plan_to_critique` (compatible) | Missing phase_result exit_kind → incompatible |
| critique_gate | `critique_to_gate` (compatible) | Missing manifest → incompatible |
| tiebreaker | `tiebreaker_researcher_to_challenger` (unknown, declared_only) | Corrupted boundary_id → incompatible |
| execute | `execute_approval` (compatible) | Missing receipt outcome → incompatible |
| finalize | `finalize_artifacts` (non_conformant, declared_only) | Missing state → unknown |
| review | `review_child_outputs` (non_conformant, declared_only) | Missing boundary_receipts → incompatible |
| override | `override_abort_authority` (unknown) | Missing boundary_receipts → unknown |

---

## 2. Stale Declarations (Declared-Only Contracts)

These contracts are present in `BOUNDARY_CONTRACTS` (the boundary contract registry in `boundary_contracts.py`) but have no matching producer emission path. They are classified as `declared_only` in `contract_to_producer_matrix.json`.

### 2.1 Tiebreaker Sub-Step Contracts (4 contracts)

| Boundary ID | Row ID | Reason Stale |
|------------|--------|-------------|
| `tiebreaker_researcher_to_challenger` | s3.tiebreaker.1 | Tiebreaker run/decide steps emit overall phase_results but no per-sub-step boundary receipts. |
| `tiebreaker_challenger_to_synthesis` | s3.tiebreaker.2 | Same — no per-sub-step receipt emission in `handlers/tiebreaker.py`. |
| `tiebreaker_synthesis_to_decision` | s3.tiebreaker.3 | Same — no per-sub-step receipt emission. |
| `tiebreaker_decision_to_parent` | s3.tiebreaker.4 | Same — no per-sub-step receipt emission. |

**C2 migration target**: Add per-sub-step boundary receipt emission to the tiebreaker handler or promote tiebreaker sub-steps to independent boundaries with their own auto-match entries.

### 2.2 Review Contracts (5 contracts)

| Boundary ID | Row ID | Reason Stale |
|------------|--------|-------------|
| `review_child_outputs` | s5.review.1 | Review handler (`handlers/review.py`) does not emit explicit boundary receipts. Review is excluded from `_finish_step` auto-receipt. |
| `review_reducer_promotion` | s5.review.2 | Same — review is excluded from auto-receipt emission. |
| `review_rework_effects` | s5.review.3 | Same — no receipt emission path. |
| `review_cap_authority` | s5.review.4 | Same — no receipt emission path. |
| `review_human_verification` | s5.review.5 | Same — human verification steps emit no automated boundary receipt. |

**C2 migration target**: Add receipt emission to the review handler or create a review-specific `_finish_step` variant that includes boundary receipt logic.

### 2.3 Finalize Contracts (3 contracts)

| Boundary ID | Row ID | Reason Stale |
|------------|--------|-------------|
| `finalize_artifacts` | s5.finalize.1 | Finalize handler (`handlers/finalize.py`) does not emit explicit boundary receipts. |
| `finalize_fallback` | s5.finalize.2 | Same — no receipt emission path. |
| `final_projection` | s5.finalize.3 | Same — no receipt emission path. |

**C2 migration target**: Add receipt emission to the finalize handler.

### 2.4 Parent Rejoin (1 contract)

| Boundary ID | Row ID | Reason Stale |
|------------|--------|-------------|
| `parent_rejoin_promotion` | s3.rejoin.1 | Parent rejoin logic exists in the tiebreaker orchestration but does not emit a standalone boundary receipt. |

**C2 migration target**: Add explicit rejoin receipt emission in the parent rejoin code path.

---

## 3. Missing Emitters (Unknown Producer Category)

These contracts are present in `BOUNDARY_CONTRACTS` but no producer emission path could be confirmed through code inspection. They are classified as `unknown` in `contract_to_producer_matrix.json`.

### 3.1 Replan Authority (1 contract)

| Boundary ID | Row ID | Reason Missing |
|------------|--------|---------------|
| `replan_authority` | s3.replan.1 | The replan code path exists in the tiebreaker family but does not emit a distinct boundary receipt. The replan step re-enters the plan phase rather than crossing a replan-specific boundary. |

### 3.2 Override Contracts (8 contracts)

| Boundary ID | Row ID | Reason Missing |
|------------|--------|---------------|
| `override_abort_authority` | s6.override.1 | All 8 override contracts have `receipt_required=False` in `BOUNDARY_CONTRACTS`. The override handler applies state transitions directly without emitting per-contract boundary receipts. |
| `override_force_proceed_authority` | s6.override.2 | Same — `receipt_required=False`. |
| `override_replan_authority` | s6.override.3 | Same — `receipt_required=False`. |
| `override_recover_blocked_authority` | s6.override.4 | Same — `receipt_required=False`. |
| `override_resume_clarify_authority` | s6.override.5 | Same — `receipt_required=False`. |
| `override_adopt_execution_authority` | s6.override.6 | Same — `receipt_required=False`. |
| `override_suspension_authority` | s6.override.7 | Same — `receipt_required=False`. |
| `override_human_gate_authority` | s6.override.8 | Same — `receipt_required=False`. |

---

## 4. Intentional Exceptions

These gaps are by design, not omissions. C1 documents them as intentional exceptions with rationale.

### 4.1 Override Contracts — Receipt Not Required

- **Scope**: All 8 `override_*` contracts.
- **Exception**: `receipt_required=False` in `BOUNDARY_CONTRACTS`.
- **Rationale**: Override transitions are authority decisions that mutate state directly (e.g., `set_current_state(STATE_ABORTED)`). The authority decision itself is the durable record; a boundary receipt would be redundant. The override receipt is a state mutation, not a boundary crossing.
- **C2 action**: Either (a) keep `receipt_required=False` and remove these from the boundary contract registry, or (b) add receipt emission and set `receipt_required=True` in C4 when authority attestation is formalized.

### 4.2 Warn-Only Authority Routes

- **Scope**: Authority routes with `WARN_ONLY` disposition in `AUTHORITY_ROUTES`.
- **Exception**: C1R004 flags warn-only routes as non-conformant when they lack durable prerequisite-owned migration metadata.
- **Rationale**: Warn-only is a legitimate transitional state when the route's enforcement is not yet production-ready, but only if accompanied by an owner, reason, and expiry milestone. C1 requires this metadata; routes without it fail C1R004.
- **C2 action**: Add migration metadata to every warn-only route or promote to enforced.

### 4.3 Legacy Fixture Bundles (000–003)

- **Scope**: `captured_bundle_{000..003}_*.json` — raw event store data from early Megaplan runs.
- **Exception**: These bundles contain only raw `events.jsonl` data without structured boundary_receipts, manifests, or phase_results.
- **Rationale**: Legacy fixtures prove historical continuity but cannot be evaluated for boundary compatibility. `CompatibilityEvaluator` correctly classifies them as `UNKNOWN` with `CBC011_LEGACY_FIXTURE_UNKNOWN`.
- **C2 action**: No action needed. Legacy bundles are preserved for provenance, not compatibility evaluation.

### 4.4 Evidence Pack — No Direct Contract Mapping

- **Scope**: `evidence_pack` steps in `support_manifest.json`.
- **Exception**: Evidence pack rows are not directly mapped to individual boundary contracts.
- **Rationale**: The evidence pack pipeline independently verifies persisted artifacts rather than crossing workflow boundaries. Its verification is orthogonal to boundary contract emission.
- **C2 action**: If evidence pack steps gain boundary semantics, add them to `BOUNDARY_CONTRACTS` with corresponding producer entries.

### 4.5 Typed Unknown Markers for Unavailable Categories

- **Scope**: All captured fixture bundles where source data is absent.
- **Exception**: Categories like `routing_ledger`, `events`, `execution`, `completion`, `watchdog`, `verdict`, and `gate_review_artifacts` may be `{"category":"...","reason":"source_missing"}` rather than populated.
- **Rationale**: C1 captures what exists; it does not fabricate missing data. Typed unknown markers are schema-conformant placeholders that prevent silent omission.
- **C2 action**: As C2–C6 add real producers, these markers will be replaced by actual data in new fixture captures.

---

## 5. Coverage Summary

| Classification | Count | Contracts |
|---------------|-------|-----------|
| **Full native parity** (auto_matched or manual_emit with fixtures) | 13 | prep_to_plan, plan_to_critique, critique_to_gate, gate_to_revise, revise_to_critique, execute_approval, execute_approval_denial, execute_batch_checkpoint, execute_partial_failure, execute_blocked_anchor, execute_resume_anchor, execute_aggregate_promotion, execute_no_review_terminal |
| **Declared only** (stale declarations) | 12 | tiebreaker_researcher_to_challenger, tiebreaker_challenger_to_synthesis, tiebreaker_synthesis_to_decision, tiebreaker_decision_to_parent, review_child_outputs, review_reducer_promotion, review_rework_effects, review_cap_authority, review_human_verification, finalize_artifacts, finalize_fallback, final_projection |
| **Unknown producer** (missing emitters) | 9 | replan_authority, parent_rejoin_promotion, override_abort_authority, override_force_proceed_authority, override_replan_authority, override_recover_blocked_authority, override_resume_clarify_authority, override_adopt_execution_authority, override_suspension_authority, override_human_gate_authority |
| **Total** | 35 | — |

Note: `parent_rejoin_promotion` is counted under declared_only in the matrix but could also be classified as unknown. The matrix classifies it as `declared_only` because no emission callsite was found for it.

---

## 6. Non-Conformant Status Propagation

Contracts classified as `declared_only` or `unknown` in the matrix propagate to fixture replay results as follows:

| Producer Category | CompatibilityStatus | Primary Diagnostic |
|------------------|---------------------|-------------------|
| `declared_only` | `NON_CONFORMANT` | `CBC013_DECLARED_ONLY_NO_PRODUCER` |
| `unknown` | `UNKNOWN` | `CBC014_UNKNOWN_PRODUCER_CATEGORY` |
| `auto_matched` + `visible_non_conformant` | `NON_CONFORMANT` | `CBC015_VISIBLE_NON_CONFORMANCE` |
| `manual_emit` + `visible_non_conformant` | `NON_CONFORMANT` | `CBC015_VISIBLE_NON_CONFORMANCE` |

No contract currently has both a real producer (`auto_matched` or `manual_emit`) and a `visible_non_conformant` entry. This path is reserved for C2+ when a real producer exists but exhibits known deviations.

---

## 7. What C1 Does NOT Claim

1. **C1 does not claim full producer coverage.** 22 of 35 contracts (63%) lack real producers. This is documented, not hidden.

2. **C1 does not claim runtime reconciliation.** `atomicity_failure_table.md` prescribes deterministic reconciliation but C1 does not implement it. That is C4+ scope.

3. **C1 does not claim LLM output determinism.** Captured fixtures freeze one representative run. Real producer cases validate structural invariants, not content identity.

4. **C1 does not claim evidence pack boundary semantics.** Evidence pack is classified in the support manifest but not in the contract-to-producer matrix.

5. **C1 does not claim external effect verification.** Git push, commit, and external API calls are documented as non-replayable in the conformance plan.

6. **C1 does not claim that synthetic semantic-health tests replace real producer coverage.** Synthetic tests provide vocabulary and schema coverage; real producer cases provide structural health coverage for phase families with real producers.

---

## 8. C2–C6 Migration Targets

| Gap | Current C1 Status | C2+ Target |
|-----|-------------------|-----------|
| Tiebreaker sub-step receipts | 4 declared_only | Add per-sub-step receipt emission (C2) |
| Review receipts | 5 declared_only | Add receipt emission to review handler (C2) |
| Finalize receipts | 3 declared_only | Add receipt emission to finalize handler (C2) |
| Replan receipt | 1 unknown | Add explicit replan boundary receipt or accept that replan re-enters plan phase (C2) |
| Override receipts | 8 unknown, receipt_required=False | Formalize as authority attestations in C4 or remove from registry (C4) |
| Parent rejoin receipt | 1 declared_only | Add rejoin receipt emission (C2) |
| Evidence pack boundary mapping | Not mapped | Map to boundary contracts if boundary semantics are adopted (C3) |
| Transaction/outbox migration | Schema only (primitive gaps documented) | Implement in C4–C6 |
| Runtime reconciliation (CP1–CP12, LR1–LR4) | Specification only | Implement in C4 |
| NDJSON sequence gap detection | Schema only | Implement in C4 |
| Idempotent retry of external effects | Not implemented | Implement in C4–C5 |
| Full suite compatibility replay with evidence-pack attestation | Not implemented | Implement in C5 |
| Production migration with real producer coverage for all 35 contracts | 13/35 covered | Achieve in C6 |
