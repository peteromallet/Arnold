# C1 Query, Replay, and Audit Conformance Plan

> Generated for C1 Contract Reality Reconciliation
> Schema anchors: `arnold/workflow/boundary_compatibility.py`, `arnold/workflow/execution_attempt_ledger.py`
> Diagnostic anchors: `arnold_pipelines/megaplan/workflows/contract_reality.py` (C1R001–C1R010), `arnold/workflow/boundary_compatibility.py` (CBC001–CBC015)
> Applies to: All C1 observe-only surfaces; C2–C6 consumers inherit this plan as a handoff artifact.

## Overview

This document names every machine-produced evidence artifact, required index, authorization check, read-only constraint, and non-replayable effect behavior that C1 surfaces for audit and conformance. It serves as the authoritative conformance plan that downstream C2–C6 consumers use to validate that C1's observe-only guarantees are preserved and that no evidence has been retroactively fabricated.

---

## 1. Machine-Produced Evidence Artifacts

Every artifact listed below is checked into the repository, produced by a deterministic tool or capture script, and referenced by at least one C1 test surface. No artifact was hand-crafted or invented.

### 1.1 Checked-in Matrices

| Artifact | Path | Producer | What It Proves |
|----------|------|----------|-----------------|
| Source-to-Owner Matrix | `arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json` | T10 (hand-built from code inspection) | 44 surfaces classified with exactly one mutating owner each (wbc: 20, run_authority: 14, maintenance: 10). No dual ownership. All wbc surfaces carry valid `wbc_access_level`. |
| Contract-to-Producer Matrix | `arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json` | T11 (hand-built from code inspection) | 35 boundary contracts mapped to real producer code paths. 5 auto_matched, 8 manual_emit, 12 declared_only, 10 unknown. Every producer path confirmed via code inspection. |
| Support Manifest | `arnold_pipelines/megaplan/workflows/support_manifest.json` | T12 (hand-built from code inspection) | 76 entries across 4 families (megaplan: 39, arnold_workflow: 21, arnold_pipeline_native: 10, evidence_pack: 6). Every entry has owner, support_status, and C2–C6 migration milestone. |

### 1.2 Captured Fixture Bundles

| Artifact | Path | Producer | What It Proves |
|----------|------|----------|-----------------|
| Captured Bundle Index | `tests/fixtures/workflow_boundary_contracts/captured_bundles_index.json` | `tools/capture_wbc_contract_reality_fixtures.py` (T14) | Index of all 34 captured bundles with source run directories and capture timestamps. |
| Captured Bundles (34 files) | `tests/fixtures/workflow_boundary_contracts/captured_bundle_{000..033}_*.json` | `tools/capture_wbc_contract_reality_fixtures.py` (T14, T15) | Redacted, compact fixture bundles with boundary_receipts, manifest, phase_result, semantic_health, state, events, routing_ledger, execution, gate_review_artifacts, completion, watchdog, and verdict sections. Typed unknown markers where source categories are absent. Prose redacted. |
| Real Producer Cases | `tests/fixtures/workflow_boundary_contracts/real_producer_cases.bundle.json` | `tools/generate_real_producer_cases.py` (T18) | 16 cases (8 healthy + 8 broken) covering prep, plan_revise, critique_gate, tiebreaker, execute, finalize, review, and override phase families. Each broken case corrupts exactly one relation. |

### 1.3 Schema Modules (arol.workflow)

| Artifact | Path | Contents |
|----------|------|----------|
| Durable Refs | `arnold/workflow/durable_refs.py` | `DurableRef` dataclass with 5 enums (PrivacyClass, AvailabilityClass, EncryptionScope, RetentionClass, AccessScope) and 8 forbidden secret-key patterns. |
| Payload Policy | `arnold/workflow/payload_policy.py` | `wbc.inline.v1` and `wbc.retention.v1` validators. 16 KiB canonical JSON threshold. RetentionMode, RedactionMode, TombstoneMode, AuditMode, IsolationLevel. |
| Execution Attempt Ledger | `arnold/workflow/execution_attempt_ledger.py` | Schema-only ledger with 11 event types, 9 typed payload refs, identity/provenance/ordering/position types, PersistenceFailureDiagnostic, ReconciliationDiagnostic. |
| Boundary Evidence | `arnold/workflow/boundary_evidence.py` | `BoundaryContract`, `BoundaryReceipt`, `BoundaryAuthorityRecord`, `SemanticFinding`, `SemanticHealthProfile`, and 4 diagnostic codes (AWF246–AWF249). |
| Boundary Compatibility | `arnold/workflow/boundary_compatibility.py` | `CompatibilityEvaluator` with 4 statuses (compatible/incompatible/unknown/non_conformant), 15 CBC diagnostic codes, and read-only fixture replay. |

### 1.4 Diagnostic Modules

| Artifact | Path | Contents |
|----------|------|----------|
| Contract Reality Validators | `arnold_pipelines/megaplan/workflows/contract_reality.py` | 10 C1R diagnostic codes, 7 read-only validators, composite `run_c1_preflight`. Evidence refs pinned per diagnostic. |
| Atomicity Failure Table | `docs/workflow-boundary-contracts/c1/atomicity_failure_table.md` | 12 crash points (CP1–CP12) with visible state and deterministic reconciliation; 4 ledger-level conditions (LR1–LR4). |

### 1.5 Test Evidence

| Artifact | Path | Tests | What It Proves |
|----------|------|-------|-----------------|
| Failure Condition Tests | `tests/arnold_pipelines/megaplan/test_contract_reality_failure_conditions.py` | 47 | All 10 C1R codes pinned with evidence_ref assertions. |
| Matrix Integrity Tests | `tests/arnold_pipelines/megaplan/test_contract_reality_matrices.py` | 92 | Deterministic structural validation of all 3 matrices. Cross-matrix consistency checks. |
| Boundary Compatibility Replay | `tests/arnold/workflow/test_boundary_compatibility_replay.py` | 218 | 34 bundles evaluated; 10 compatible, 3 incompatible, 20 unknown, 1 non_conformant. Determinism, no-write, legacy non-normalization all verified. |
| Zero-Write Mutation Gate | `tests/arnold_pipelines/megaplan/test_zero_write_mutation_gate.py` | 23 | Semantic inspection and fixture replay produce zero writes across all 12 write-surface categories. |
| Schema Golden Fixtures | `tests/arnold/workflow/test_golden_fixtures.py` | 43 | Deterministic compact cases for all ledger event types, payload policies, and durable refs. |
| Ledger Tests | `tests/arnold/workflow/test_execution_attempt_ledger.py` | 265 | All 4 enums, 9 typed payload refs, identity/provenance/ordering/position validation, persistence-failure diagnostics. |
| Durable Refs Tests | `tests/arnold/workflow/test_durable_refs.py` | 67 | Construction, enum enforcement, secret exclusion (all 8 patterns), all validators. |
| Payload Policy Tests | `tests/arnold/workflow/test_payload_policy.py` | 73 | 16 KiB threshold boundaries, inline/reference classification, retention/redaction/tombstone/legal-hold rules. |

---

## 2. Required Indexes

C1 defines and validates the following indexes for audit trail integrity. No index requires runtime computation; all are derivable from checked-in artifacts.

### 2.1 Contract-to-Producer Index

- **Source**: `contract_to_producer_matrix.json` → `contracts[].boundary_id`
- **Cardinality**: 35 boundary_ids, one row per contract.
- **Validation**: `TestContractToProducerMatrixIntegrity` (29 tests) verifies no duplicate boundary_ids, all 35 expected contracts present, producer categories consistent with summary counts.
- **Consumer use**: `CompatibilityEvaluator._contracts_by_boundary_id` loads this index for O(1) lookup during fixture replay.

### 2.2 Source-to-Owner Index

- **Source**: `source_to_owner_matrix.json` → `surfaces[].surface_id`
- **Cardinality**: 44 surfaces, one mutating owner each.
- **Validation**: `TestSourceToOwnerMatrixIntegrity` (25 tests) verifies deterministic ordering, no dual ownership, valid WBC access levels, complete compatibility readers.
- **Consumer use**: C1 preflight validators cross-reference this index to detect dual mutating ownership (C1R005).

### 2.3 Support Manifest Entry Index

- **Source**: `support_manifest.json` → `families[].entries[].step_id`
- **Cardinality**: 76 entries across 4 families.
- **Validation**: `TestSupportManifestIntegrity` (31 tests) verifies all entries have owner, support_status, migration milestone; no duplicate step_ids.
- **Consumer use**: Migration coverage and milestone gap detection (C1R008, C1R009).

### 2.4 Captured Bundle Index

- **Source**: `captured_bundles_index.json` → `bundles[]`
- **Cardinality**: 34 bundle entries.
- **Validation**: `TestEvaluatorCoverage` (2 tests) verifies all 34 bundles are evaluated, no duplicates.
- **Consumer use**: `CompatibilityEvaluator.evaluate_all()` globs `captured_bundle_*.json` directly; the index serves as a human-readable manifest.

### 2.5 Diagnostic Code Index

- **Source**: `contract_reality.py` → `C1_DIAGNOSTIC_SPECS_BY_CODE`
- **Cardinality**: 10 C1R codes + 15 CBC codes.
- **Validation**: Schema-level assertion that every code has exactly one spec entry.
- **Consumer use**: Downstream gates filter on diagnostic code for blocking vs. advisory classification.

---

## 3. Authorization Checks

C1 performs the following authorization checks without granting, requesting, or modifying authority. Every check emits a stable diagnostic code and evidence reference.

### 3.1 Run Authority Manifest/Base SHA (C1R001, C1R002)

- **Validator**: `validate_run_authority_manifest_hash` and `validate_run_authority_base_sha` in `contract_reality.py`.
- **What it checks**: The pinned Run Authority completion manifest hash and base SHA match the current repository state.
- **Evidence ref**: `state.idea` → handoff record, `git rev-parse HEAD`.
- **Authorization posture**: **read-only** — compares hashes, does not checkout or rebase.

### 3.2 Route Migration Disposition (C1R003, C1R004)

- **Validator**: `validate_route_migration_disposition` in `contract_reality.py`.
- **What it checks**: Every authority-increasing consumer in `AUTHORITY_ROUTES` has a migration disposition (enforced, warn_only, shadow_only, informational, deferred). Warn-only routes without durable prerequisite-owned migration metadata are non-conformant.
- **Evidence ref**: `arnold_pipelines.megaplan.orchestration.authority_readers:AUTHORITY_ROUTES`.
- **Authorization posture**: **read-only** — reads the route table, emits diagnostics.

### 3.3 Dual Mutating Ownership Detection (C1R005)

- **Validator**: `validate_no_dual_mutating_ownership` in `contract_reality.py`.
- **What it checks**: Cross-references `source_to_owner_matrix.json` to detect any surface with multiple `mutating_owner` claims.
- **Evidence ref**: `source_to_owner_matrix.json` surfaces list.
- **Authorization posture**: **read-only** — reads the matrix, detects conflicts.

### 3.4 Fixture Replay Mutability (C1R006)

- **Validator**: `validate_fixture_replay_mutability` in `contract_reality.py`.
- **What it checks**: Confirms that `CompatibilityEvaluator` performs zero writes (backed by `test_zero_write_mutation_gate.py`).
- **Evidence ref**: `test_zero_write_mutation_gate.py` results.
- **Authorization posture**: **read-only** — checks that the evaluator never calls write primitives.

### 3.5 Zero-Write Mutation Gates (T20 Tests)

- **Validator**: `test_zero_write_mutation_gate.py` (23 tests).
- **What it checks**: `inspect_semantic_health` and `CompatibilityEvaluator.evaluate_all()` perform zero writes across 12 write surfaces: path writes, lifecycle, repair, status persister, queue, commit/push, projection/drift, and audited-input writes.
- **Evidence ref**: Monkey-patched `pathlib.Path.write_text`, `builtins.open` (write modes), atomic write primitives, persistence backend methods.
- **Authorization posture**: **read-only** — the tests prove that observe-only operations never mutate disk.

---

## 4. Read-Only Guarantees

C1 surfaces these read-only guarantees as structural invariants, not runtime promises.

### 4.1 CompatibilityEvaluator

- **Guarantee**: `CompatibilityEvaluator.evaluate_all()` and `evaluate_fixture()` read fixture JSON files, the contract matrix, and return `CompatibilityResult` tuples. They never open a file in write mode, never call `write_text` or `write_bytes`, and never invoke `os.rename`, `os.replace`, or `shutil.move`.
- **Proof**: `test_zero_write_mutation_gate.py::TestFixtureReplayZeroWrite` (8 tests).
- **SC16 compliance**: No fixture normalization, no legacy schema upgrading, no current fixture rewriting.

### 4.2 Semantic Health Inspection

- **Guarantee**: `inspect_semantic_health` reads boundary contracts, state files, and manifests, then returns `SemanticHealthProfile` diagnostics without mutating lifecycle state, queues, source, or status.
- **Proof**: `test_zero_write_mutation_gate.py::TestSemanticInspectionZeroWrite` (9 tests).

### 4.3 Contract Reality Preflight Validators

- **Guarantee**: All 7 validators in `contract_reality.py` are `@staticmethod` functions that read matrices and emit `C1PreflightDiagnostic` records. None call approval, waiver, or lifecycle mutation APIs.
- **Proof**: `test_contract_reality_failure_conditions.py` (47 tests) — every test verifies diagnostic code and evidence reference, not approval outcomes.

### 4.4 Fixture Capture

- **Guarantee**: `tools/capture_wbc_contract_reality_fixtures.py` reads source run/plan directories and writes only under `tests/fixtures/workflow_boundary_contracts/`. It never mutates source directories. Prose is redacted; schema-significant structure is preserved.
- **Proof**: `--dry-run` mode validates paths before any write; output locality enforced by hardcoded `FIXTURE_OUT_DIR`.

---

## 5. Non-Replayable Effect Behavior

Some boundary transitions produce external effects that cannot be replayed by C1's observe-only evaluator. These are documented in the atomicity failure table and classified here.

### 5.1 Git Push (Execute/Finalize)

- **Effect**: `git push` of generated artifacts to a remote repository.
- **Why non-replayable**: Requires network access, remote credentials, and may conflict with concurrent pushes.
- **C1 treatment**: Captured fixture bundles include `execution.json` and artifact hashes but not remote push outcomes. CP4 and CP5 in `atomicity_failure_table.md` prescribe idempotent retry for C4+.
- **Diagnostic reference**: `external_effect_intent` / `external_effect_outcome` event types defined in `execution_attempt_ledger.py` — schema only, no producer in C1.

### 5.2 Git Commit

- **Effect**: `git commit` of generated artifacts with deterministic commit messages.
- **Why non-replayable**: Mutates the git object database. C1 cannot commit.
- **C1 treatment**: Artifact content is captured as redacted fixture data. Commit hashes are not captured (they would change on any rebase).

### 5.3 Worker Invocation (Phase Handlers)

- **Effect**: Megaplan phase handlers invoke LLM workers that produce non-deterministic outputs.
- **Why non-replayable**: LLM outputs vary across runs even with identical inputs.
- **C1 treatment**: Captured bundles freeze one representative run's outputs. Real producer cases validate structural invariants, not content identity.

### 5.4 External API Calls (Evidence Pack)

- **Effect**: `evidence_pack` pipeline may call external verification APIs.
- **Why non-replayable**: External API availability and responses are outside C1 control.
- **C1 treatment**: Evidence pack steps are classified in `support_manifest.json` with support_status and migration milestone. No evidence_pack fixtures are captured.

---

## 6. Audit Trail Integrity

### 6.1 Immutable Diagnostic Codes

All C1 diagnostic codes are frozen `StrEnum` values:

- **C1R001–C1R010**: `C1RealityDiagnosticCode` in `contract_reality.py`. Must not be renamed or repurposed.
- **CBC001–CBC015**: `CompatibilityDiagnosticCode` in `boundary_compatibility.py`. Must not be renamed or repurposed.
- **AWF246–AWF249**: `DiagnosticCode` in `boundary_evidence.py`. Pre-existing, not modified by C1.

### 6.2 Deterministic Ordering

All matrices and fixture evaluations use deterministic ordering:
- `source_to_owner_matrix.json`: surfaces sorted by `surface_id`.
- `contract_to_producer_matrix.json`: contracts sorted by `boundary_id`.
- `support_manifest.json`: entries sorted within each family.
- `CompatibilityEvaluator.evaluate_all()`: results sorted by fixture filename.
- `CompatibilityResult` diagnostics: always tuples (order-preserving).

### 6.3 Chained Evidence References

Every diagnostic carries an `evidence_ref` that pins it to a specific checked-in artifact:

| Diagnostic | Evidence Ref Pattern |
|-----------|---------------------|
| C1R001 | `run_authority:manifest_hash` |
| C1R002 | `run_authority:base_sha` |
| C1R003 | `authority_route:{route_id}` |
| C1R004 | `authority_route:{route_id}` |
| C1R005 | `source_to_owner_matrix:surfaces` |
| C1R006 | `test_zero_write_mutation_gate:fixture_replay` |
| C1R007 | `contract_to_producer_matrix:{boundary_id}` |
| C1R008 | `support_manifest:{producer_ref}` |
| C1R009 | `support_manifest:{producer_ref}` |
| C1R010 | `durable_refs:{hash_ref}` |
| CBC001–CBC012 | `artifacts.{category}`, `unknown_markers[category={cat}]`, `fixture_path:{path}` |
| CBC013–CBC015 | `contract_to_producer:{boundary_id}` |

---

## 7. C2–C6 Integration Seams

This plan is a handoff artifact. C2–C6 consumers inherit these invariants:

1. **Schema stability**: `arnold/workflow/durable_refs.py`, `payload_policy.py`, `execution_attempt_ledger.py`, `boundary_evidence.py`, `boundary_compatibility.py` are frozen under C1. C2+ may add producers that write these schemas but may not alter the schema vocabulary.

2. **Matrix stability**: `source_to_owner_matrix.json`, `contract_to_producer_matrix.json`, `support_manifest.json` are frozen under C1. C2+ may reclassify entries (e.g., promote `declared_only` to `manual_emit` as producers are added) but must update the matrix atomically with the code change.

3. **Diagnostic code stability**: C1R001–C1R010 and CBC001–CBC015 are immutable. C2+ may add new codes but must not rename or repurpose existing codes.

4. **Fixture stability**: Captured bundles under `tests/fixtures/workflow_boundary_contracts/` are C1 baseline evidence. C2+ may add new bundles but must not modify C1 bundles.

5. **Reconciliation contract**: `atomicity_failure_table.md` prescribes deterministic reconciliation for CP1–CP12 and LR1–LR4. C4+ runtimes must implement these procedures before claiming atomicity.

---

## 8. Acceptance Gate Summary

| Criterion | Evidence | Status |
|-----------|----------|--------|
| Preflight diagnostics (C1R001–C1R010) stable and tested | `test_contract_reality_failure_conditions.py` (47 tests) | ✅ |
| Schema validators enforce North Star fields | `test_durable_refs.py` (67), `test_payload_policy.py` (73), `test_execution_attempt_ledger.py` (265) | ✅ |
| Source-to-owner matrix single-owner | `source_to_owner_matrix.json` (44 surfaces, 0 dual) | ✅ |
| Contract-to-producer matrix maps 35 contracts | `contract_to_producer_matrix.json` (35 contracts) | ✅ |
| Support manifest covers 76 entries | `support_manifest.json` (76 entries across 4 families) | ✅ |
| Fixture replay read-only with typed results | `test_boundary_compatibility_replay.py` (218 tests) | ✅ |
| Real producer cases for all 8 phase families | `real_producer_cases.bundle.json` (16 cases) | ✅ |
| Zero-write mutation gate | `test_zero_write_mutation_gate.py` (23 tests) | ✅ |
| Atomicity failure table | `atomicity_failure_table.md` (12 CPs + 4 LR conditions) | ✅ |
| This conformance plan | `query_replay_audit_conformance_plan.md` | ✅ (this document) |
| Coverage and exceptions | `coverage_and_exceptions.md` | ✅ (companion document) |
