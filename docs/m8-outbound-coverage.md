# M8 Outbound Validation Coverage

Catalog of production and test call sites for outbound validation primitives:
`validate_payload_against_schema`, `audit_step_payload`, `capture_step_output`,
and `validate_payload`.

Generated from ripgrep + AST inspection against the M8 acceptance gate codebase.
Each entry records file:line, containing function, payload type, coverage claim,
existing ratchet cross-references, and closure argument when applicable.

---

## validate_payload_against_schema

**Definition:** `arnold/pipeline/contract_validation.py:300`

### Production Call Sites

| # | File:Line | Containing Function | Payload Type | Coverage Claim | Existing Ratchet | Closure Arg |
|---|-----------|---------------------|-------------|----------------|-----------------|-------------|
| 1 | `arnold/pipeline/step_io_contract.py:187` | `classify_step_io_contract` | `StepIOEnvelope.payload` (Mapping) | Unit-tested via `tests/arnold/pipeline/test_step_io_*.py` | Step-IO contract classification gate | `registry.get_schema(schema_version)` |
| 2 | `arnold/pipeline/contract_validation.py:322` | `validate_contract_result` | `ContractResult.payload` (Mapping) | Unit-tested via `tests/test_contract_validation.py` | Internal wrapper — delegates to same function | `schema` (caller-provided) |
| 3 | `arnold/pipelines/megaplan/model_seam.py:1571` | `_audit_capture_payload` | Step payload (Mapping) | Tested via `tests/arnold/pipelines/megaplan/test_model_seam.py` capture_step_output tests | Structural audit gate inside capture_step_output | `schema` resolved from invocation metadata |
| 4 | `arnold/pipelines/megaplan/pipeline_contracts.py:471` | `consume_payload_result` | `StepIOEnvelope.payload` (Mapping) | Tested via `tests/arnold/pipelines/megaplan/test_pipeline_contracts.py` | Typed-port consumer validation | `registry.get_schema(envelope.schema_version)` |
| 5 | `arnold/pipelines/evidence_pack/steps.py:135` | `run` (IngestStep) | Evidence pack payload (Mapping) | Tested via `tests/arnold/pipelines/evidence_pack/test_steps.py` | Ingest schema validation | `EVIDENCE_PACK_SCHEMA` |
| 6 | `arnold/pipelines/evidence_pack/steps.py:221` | `run` (ContentValidatorStep) | Checkpoint payload (Mapping) | Tested via `tests/arnold/pipelines/evidence_pack/test_steps.py` | Checkpoint schema validation | `CHECKPOINT_SCHEMA` |
| 7 | `arnold/pipelines/evidence_pack/steps.py:446` | `run` (ReduceStep) | Verdict payload (Mapping) | Tested via `tests/arnold/pipelines/evidence_pack/test_steps.py` | Verdict schema validation | `VERDICT_SCHEMA` |
| 8 | `arnold/pipelines/evidence_pack/steps.py:714` | `run` (EmitAttestationStep) | Attestation payload (Mapping) | Tested via `tests/arnold/pipelines/evidence_pack/test_steps.py` | Attestation schema validation | `ATTESTATION_SCHEMA` |

### Test Call Sites

| # | File:Line | Test Function | Notes |
|---|-----------|--------------|-------|
| 1 | `tests/test_contract_validation.py:24` | `test_conformant_payload_passes` | Direct validation of conforming payload |
| 2 | `tests/test_contract_validation.py:43` | `test_additional_properties_rejected` | Additional-properties rejection |
| 3 | `tests/test_contract_validation.py:74` | test with escaped JSON pointers | Pointer-escaping coverage |
| 4 | `tests/test_contract_validation.py:94` | null-optional field test | Null in optional fields |
| 5 | `tests/test_contract_validation.py:99` | array-item type validation | Array sub-schema enforcement |
| 6 | `tests/test_contract_validation.py:120` | nullable field passthrough | None passes for non-required fields |
| 7 | `tests/test_contract_validation.py:121-122` | missing/wrong-type fields | Required field validation |
| 8 | `tests/arnold/pipelines/megaplan/test_model_seam.py:12` | (import only) | Imported for schema validation in capture tests |
| 9 | `tests/m8/regression/test_structural_regressions.py` (T2) | structural audit regressions | M8-distinct additionalProperties rejection |

---

## audit_step_payload

**Definition:** `arnold/pipelines/megaplan/model_seam.py:1540`

Delegates to `_audit_capture_payload` → `validate_payload_against_schema`.

### Production Call Sites

| # | File:Line | Containing Function | Payload Type | Coverage Claim | Existing Ratchet | Closure Arg |
|---|-----------|---------------------|-------------|----------------|-----------------|-------------|
| 1 | `arnold/pipelines/megaplan/model_seam.py:1123` | `_recover_payload_with_provenance` | Preferred recovered payload (Mapping) | Tested via `tests/arnold/pipelines/megaplan/test_model_seam.py` | Output-file preferred recovery path | `step` (string), `preferred_payload` (dict) |
| 2 | `arnold/pipelines/megaplan/model_seam.py:1154` | `_recover_payload_with_provenance` | Candidate recovered payload (Mapping) | Same as above | General recovery loop | `step` (string), `payload` (dict) |
| 3 | `arnold/pipelines/megaplan/handlers/critique.py:538` | `handle_critique` | Worker critique payload | Tested via `tests/pipelines/megaplan/execute/test_*.py` handler tests | Critique output structural audit | `"critique"`, `worker.payload` |
| 4 | `arnold/pipelines/megaplan/handlers/critique.py:703` | `_recover_valid_critique_output` | Recovered critique payload | Same as above | Critique recovery audit | `"critique"`, `payload` |
| 5 | `arnold/pipelines/megaplan/handlers/critique.py:763` | `handle_revise` | Revise payload | Tested via handler tests | Revise output structural audit | `"revise"`, `payload` |
| 6 | `arnold/pipelines/megaplan/handlers/gate.py:717` | `handle_gate` | Gate payload | Tested via `tests/pipelines/megaplan/execute/test_*.py` | Gate output structural audit | `"gate"`, `gate_payload` |
| 7 | `arnold/pipelines/megaplan/handlers/gate.py:778` | `handle_gate` | Gate payload (fallback) | Same as above | Gate fallback audit | `"gate"`, `gate_payload` |
| 8 | `arnold/pipelines/megaplan/handlers/review.py:283` | `_audit_review_payload_or_raise` | Review payload | Tested via `tests/pipelines/megaplan/review/test_review_*.py` | Review output structural audit | `"review"`, `payload` |
| 9 | `arnold/pipelines/megaplan/handlers/execute.py:293` | `handle_execute` | Stub review payload | Tested via execute handler tests | Execute stub-review audit | `"review"`, `stub_review` |
| 10 | `arnold/pipelines/megaplan/workers/_impl.py:1589` | `_recover_payload_from_candidates` | Step payload | Tested via worker tests | Worker-level payload recovery audit | `step` (string), `payload` (dict) |

### Test Call Sites

| # | File:Line | Test Function | Notes |
|---|-----------|--------------|-------|
| 1 | `tests/arnold/pipelines/megaplan/test_model_seam.py` (multiple) | Various capture_step_output tests | Structural audit tested via capture path |
| 2 | `tests/m8/regression/test_structural_regressions.py` (T2) | M8 structural audit regressions | Malformed named-output capture via capture_step_output |

---

## capture_step_output

**Definition:** `arnold/pipelines/megaplan/model_seam.py:851`

### Production Call Sites

| # | File:Line | Containing Function | Payload Type | Coverage Claim | Existing Ratchet | Closure Arg |
|---|-----------|---------------------|-------------|----------------|-----------------|-------------|
| 1 | `arnold/pipelines/megaplan/model_seam.py:891` | `capture_step_output` | Repaired output (Mapping or str) | Self-recursion for repair retry | Retry loop with repair_attempt guard | `repaired_invocation`, `repaired_output` |
| 2 | `arnold/pipelines/megaplan/workers/shannon.py:2417` | `_parse_and_validate` | Model output (str \| Mapping) | Tested via shannon worker integration tests | Shannon worker capture chokepoint | `invocation`, `model_output` |
| 3 | `arnold/pipelines/megaplan/workers/hermes.py:1477` | `_run_attempt` | Model output (str \| Mapping) | Tested via hermes worker integration tests | Hermes worker capture chokepoint | `invocation`, `model_output` |
| 4 | `arnold/pipelines/megaplan/workers/hermes.py:1499` | `_run_attempt` | Model output (str \| Mapping) | Same as above | Codex path capture | `invocation`, `model_output` |
| 5 | `arnold/pipelines/megaplan/execute/timeout.py:149` | `_capture_execute_checkpoint_payload` | Model output (str \| Mapping) | Tested via timeout handler tests | Timeout-recovery capture | `invocation`, `model_output` |
| 6 | `arnold/pipelines/megaplan/execute/batch.py:484` | `_capture_execute_payload` | Model output (str \| Mapping) | Tested via batch executor tests | Batch-step capture chokepoint | `invocation`, `model_output` |
| 7 | `arnold/pipelines/megaplan/workers/_impl.py:2234` | `run_codex_step` | Model output (str \| Mapping) | Tested via worker integration tests | Generic worker capture | `invocation`, `model_output` |
| 8 | `arnold/pipelines/megaplan/workers/_impl.py:2396` | `run_codex_step` | Model output (str \| Mapping) | Same as above | Codex fallback capture | `invocation`, `model_output` |
| 9 | `arnold/pipelines/megaplan/workers/_impl.py:2590` | `run_codex_prep_step` | Model output (str \| Mapping) | Same as above | Codex resume capture | `invocation`, `model_output` |
| 10 | `arnold/pipelines/megaplan/_pipeline/steps/agent.py:112` | `run` (AgentStep) | Model output (str \| Mapping) | Tested via pipeline integration tests | Agent step capture chokepoint | `worker_invocation`, `worker_output` |

### Test Call Sites

| # | File:Line | Test Function | Notes |
|---|-----------|--------------|-------|
| 1 | `tests/arnold/pipelines/megaplan/test_model_seam.py:204` | `test_capture_step_output_preserves_legacy_payload_and_typed_contract` | Core capture test |
| 2 | `tests/arnold/pipelines/megaplan/test_model_seam.py:227` | `test_capture_step_output_skips_compatibility_projection_for_native_execute` | Native-path test |
| 3 | `tests/arnold/pipelines/megaplan/test_model_seam.py:253` | `test_capture_step_output_normalizes_prep_distill_loose_lists` | Normalization test |
| 4 | `tests/arnold/pipelines/megaplan/test_model_seam.py:418-654` | Various step-specific tests (finalize, execute_batch, review, critique) | Per-step schema validation |
| 5 | `tests/arnold/pipelines/megaplan/test_model_seam.py:787-808` | Structural audit rejection tests | Wrong-typed/hallucinated-key rejection |
| 6 | `tests/arnold/pipelines/megaplan/test_model_seam.py:847-907` | Recovery provenance tests | Codex recovery path |
| 7 | `tests/m8/regression/test_structural_regressions.py` (T2) | M8 structural audit regressions | Malformed named-output capture |

---

## validate_payload

**Definition:** `arnold/pipelines/megaplan/workers/_impl.py:1661`
**Status:** **FAIL** — Live orphan. Retired for specific steps; raises `CliError` for those.
For other steps, performs legacy required-keys validation only.

### Production Call Sites

| # | File:Line | Containing Function | Payload Type | Coverage Claim | Existing Ratchet | Closure Arg |
|---|-----------|---------------------|-------------|----------------|-----------------|-------------|
| 1 | `arnold/pipelines/megaplan/workers/_impl.py:1661` | `validate_payload` | `dict[str, Any]` | **LIVE ORPHAN** — marked retired but still callable for non-retired steps | Legacy required-keys validation | `step` (string), `payload` (dict) |
| 2 | `arnold/pipelines/megaplan/workers/__init__.py:55` | (module-level) | N/A | `del validate_payload` — removed from public API surface | Intentional removal from public exports | N/A |

---

## Summary

| Function | Production Sites | Test Sites | Orphans | Status |
|----------|-----------------|------------|---------|--------|
| `validate_payload_against_schema` | 8 | 9 | 0 | Covered |
| `audit_step_payload` | 10 | 2 | 0 | Covered |
| `capture_step_output` | 10 | 7 | 0 | Covered |
| `validate_payload` | 1 | 0 | 1 | **FAIL** — live orphan |

### Orphan Analysis: `validate_payload`

`validate_payload` in `arnold/pipelines/megaplan/workers/_impl.py:1661` is a live orphan:
- It is deliberately removed from the public `workers/__init__.py` API surface via `del validate_payload`.
- For retired steps (`_RETIRED_VALIDATE_PAYLOAD_STEPS`), it raises `CliError("parse_error", ...)` directing callers to use schema-backed capture/audit.
- For non-retired steps, it performs legacy required-keys validation using `_STEP_REQUIRED_KEYS`.
- There are **no test call sites** for `validate_payload` — the coverage gap is intentional since the function is in the process of being retired.
- The remaining non-retired callers should be migrated to `capture_step_output` / `audit_step_payload`.
