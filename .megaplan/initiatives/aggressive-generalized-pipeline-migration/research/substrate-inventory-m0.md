# Substrate Inventory — M0 Boundary Lock

> Written after Phase 1–3 execution (T1–T12). Reflects the post-boundary-lock
> state where generic Arnold modules are free of Megaplan ownership leakage and
> all Megaplan-specific behavior is quarantined behind named adapter modules under
> `arnold/pipelines/megaplan/_pipeline/`.

---

## 1. Blessed Generic Primitives (`arnold.pipeline`)

These types and functions own no Megaplan semantics. They operate on
explicit inputs with no hidden environment or `.megaplan` layout discovery.

### 1.1 Graph / Stage / Step / Context / Result

| Primitive | Module | Notes |
|---|---|---|
| `Pipeline` | `arnold.pipeline.types` | Named DAG of stages and edges |
| `Stage` | `arnold.pipeline.types` | Single-step stage with labelled edges |
| `ParallelStage` | `arnold.pipeline.types` | Fan-out stage whose steps run concurrently |
| `Edge` | `arnold.pipeline.types` | Materialised dependency between two stages |
| `Step` (Protocol) | `arnold.pipeline.types` | Protocol for executable units |
| `StepContext` | `arnold.pipeline.types` | Runtime context passed to every step |
| `StepResult` | `arnold.pipeline.types` | Result of executing a single step |
| `PipelineVerdict` | `arnold.pipeline.types` | Recommendation / override for pipeline control flow |
| `PipelineBuilder` | `arnold.pipeline.builder` | Builder for constructing pipelines |
| `PipelineRegistry` | `arnold.pipeline.registry` | Registry of named pipelines |

### 1.2 State

| Primitive | Module | Notes |
|---|---|---|
| `StateDelta` | `arnold.pipeline.state` | Ordered multi-patch container |
| `apply_delta` | `arnold.pipeline.state` | Apply StateDelta patches to a state value |

### 1.3 Ports / Routing

| Primitive | Module | Notes |
|---|---|---|
| `Port` | `arnold.pipeline.types` | Typed content port |
| `PortCardinality` | `arnold.pipeline.types` | Singleton / collection / reserved stream vocabulary |
| `PortRef` | `arnold.pipeline.types` | Reference to a named port |
| `RoutingKey` | `arnold.pipeline.types` | Content-type–qualified routing key |
| `ContentTypeRegistry` | `arnold.pipeline.types` | Map content-type names → schema digests |

### 1.4 Contracts / Schema Registry

| Primitive | Module | Notes |
|---|---|---|
| `ContractResult` | `arnold.pipeline.types` | Single shared seam primitive (Step-IO + Evidence-First) |
| `ContractStatus` | `arnold.pipeline.types` | 3-status discriminant (`PASSED` / `FAILED` / `SUSPENDED`) |
| `ContractLedger` | `arnold.pipeline.contracts` | Contract ledger and legal-coercion table |
| `CONTRACT_RESULT_SCHEMA_VERSION` | `arnold.pipeline.types` | SHA-256 hex digest of the contract shape |
| `ContractSchemaRegistry` | `arnold.pipeline.schema_registry` | Neutral retained schema storage with hash-first lookup; explicit-path only post-M0 |
| `AcceptedVersionRange` | `arnold.pipeline.schema_registry` | Inclusive logical-type history bounds for a consumer |
| `ContentValidatorRegistry` | `arnold.pipeline.content_validation` | Instance-local validator registry keyed by content_type |
| `ValidationResult` | `arnold.pipeline.contract_validation` | Aggregate structural validation outcome |
| `ValidationDiagnostic` | `arnold.pipeline.contract_validation` | Single deterministic validation failure |

### 1.5 Step IO Envelope / Policy Mechanics

| Primitive | Module | Notes |
|---|---|---|
| `StepIOEnvelope` | `arnold.pipeline.step_io_contract` | Typed Step IO envelope (read/write/classify) |
| `StepIOOperation` | `arnold.pipeline.step_io_contract` | Operation discriminant |
| `StepIOClassification` | `arnold.pipeline.step_io_contract` | Post-classification result |
| `StepIOContractContext` | `arnold.pipeline.step_io_contract` | Explicit registry + operation context; no hidden plan-dir resolution |
| `StepIOContractDecision` | `arnold.pipeline.step_io_contract` | Decision output |
| `StepIODiagnostic` | `arnold.pipeline.step_io_contract` | Diagnostic entry |
| `StepIOPolicy` | `arnold.pipeline.step_io_policy` | Generic policy: mode (`off`/`shadow`/`warn`/`enforce`) + typed-side flags |
| `resolve_step_io_policy` | `arnold.pipeline.step_io_policy` | Explicit-input policy resolution (no env, no plan-dir) |
| `load_step_io_policy` | `arnold.pipeline.step_io_policy` | Load policy from explicit path or data dict |
| `write_step_io_policy` | `arnold.pipeline.step_io_policy` | Write policy to explicit path |
| `policy_for_envelope` | `arnold.pipeline.step_io_policy` | Compute effective policy for an envelope |
| `has_step_io_self_validation_marker` | `arnold.pipeline.step_io_policy` | Check marker at explicit path |
| `record_step_io_self_validation_marker` | `arnold.pipeline.step_io_policy` | Write marker at explicit path |
| `evaluate_step_io_handoff` | `arnold.pipeline.step_io_handoff` | Evaluate handoff with explicit policy/path/data inputs |
| `StepIOHandoffResult` | `arnold.pipeline.step_io_handoff` | Handoff evaluation result |
| `StepIOViolationRecord` | `arnold.pipeline.step_io_telemetry` | Telemetry violation record |
| `STEP_IO_POLICY_FILENAME` | `arnold.pipeline.step_io_policy` | Constant `step_io_policy.json` |

### 1.6 Generic Artifacts

| Primitive | Module | Notes |
|---|---|---|
| `EvidenceArtifactRef` | `arnold.pipeline.types` | Evidence-by-reference primitive (naming rationale uses generic "downstream storage-row types" language) |
| `Provenance` | `arnold.pipeline.types` | Lineage sub-record of `ContractResult` |
| `Freshness` | `arnold.pipeline.types` | TTL sub-record of `ContractResult` |
| `ReduceResult` | `arnold.pipeline.types` | Structured output of reduce-kind step |
| `SelectionResult` | `arnold.pipeline.types` | Structured output of selection/tournament reduce |
| `Suspension` | `arnold.pipeline.types` | Typed interaction envelope |

Artifact-root mechanics (`arnold/pipeline/artifacts.py`) describe only
`artifact_root` mechanics with no Megaplan bridge vocabulary or
plan-dir inference.

### 1.7 Runtime Carriers (`arnold.runtime`)

| Primitive | Module | Notes |
|---|---|---|
| `RuntimeEnvelope` | `arnold.runtime.envelope` | Runtime-owned run envelope |
| `ResumeCursor` | `arnold.runtime.resume` | Resume cursor and legacy-resume migration contract |
| `OperationRequest` / `OperationResult` | `arnold.runtime.operations` | Capability operation carriers |
| `StepwiseDriver` (Protocol) | `arnold.runtime.driver` | Driver protocol with `IsolationMode` |
| `EffectiveSetting` | `arnold.runtime.settings` | Runtime settings shape |
| `ResolvedSettings` | `arnold.runtime.settings_resolver` | Precedence-chain resolver |
| `BatchUnit` / `BatchRunResult` | `arnold.runtime.batch` | Neutral batch carriers |
| `NullRecoveryPolicy` | `arnold.runtime.recovery` | Neutral recovery-classifier seam |

### 1.8 Audit / Resource / Pipeline Registries

| Primitive | Module | Notes |
|---|---|---|
| `AuditMode` / `AuditPolicyHook` | `arnold.pipeline.audit_policy` | Deterministic audit-mode selection |
| `PipelineIdRegistry` | `arnold.pipeline.pipeline_id_registry` | Pipeline identity registry |
| `MODEL_RESOURCE_CAPABILITIES` | `arnold.pipeline.model_resource_capabilities` | Model resource capability proofs |
| `ContentValidator` | `arnold.pipeline.content_validation` | Content-type keyed validation hooks |
| `StepInvocation` / `StepInvocationAdapter` | `arnold.pipeline.step_invocation` | Step invocation adapters |

### 1.9 Other Generic Sub-modules

| Module | Purpose |
|---|---|
| `arnold.pipeline.pattern_select` | Tournament selection primitives |
| `arnold.pipeline.pattern_stops` | Loop-stop predicates |
| `arnold.pipeline.pattern_joins` | Voting / join patterns |
| `arnold.pipeline.pattern_types` | PromoteFn / JoinFn type aliases |
| `arnold.pipeline.pattern_topology` | Topology pattern helpers |
| `arnold.pipeline.pattern_dynamic` | Dynamic pattern helpers |
| `arnold.pipeline.discovery` | Manifest reading, trust classification |
| `arnold.pipeline.profiles` | Profile loading / merging |
| `arnold.pipeline.step_io_seams` | Seam resolution from binding maps |
| `arnold.pipeline.contract_reduce` | Reduce contract results |
| `arnold.pipeline.declaration_lowering` | Declaration lowering |
| `arnold.pipeline.subpipeline` | Sub-pipeline support |
| `arnold.pipeline.validator` | Pipeline validation |
| `arnold.pipeline.runtime_contract_diagnostics` | Runtime contract diagnostics |

---

## 2. Megaplan-Owned Semantics

These concepts are *not* owned by the generic Arnold substrate. They live
exclusively under `arnold/pipelines/megaplan/` or in Megaplan-owned adapters.

### 2.1 Repository Layout

- `.megaplan/` directory tree — plan directories, chains, plans, briefs, policies
- `.megaplan/plans/<plan>/` — per-plan workspace layout
- `.megaplan/policies/step_io_contract_modes.json` — Megaplan Step IO policy persistence

### 2.2 Plan / Chain Lifecycle

- Plan creation, finalization, execution, review
- Chain lifecycle management
- Plan repository (`arnold/pipelines/megaplan/store/plan_repository.py`)

### 2.3 Git / PR Lifecycle

- Git-based plan tracking
- PR-bound workflows

### 2.4 Profile / Robustness Policy

- Profile-driven agent behavior
- Robustness level configuration (`thorough`, etc.)

### 2.5 Gate Recommendations

- `GateRecommendation` type and vocabulary
- Planning-phase gate semantics

### 2.6 `STATE_*` Tokens

- `STATE_*` enum values and planning-phase state vocabulary
- All planning-phase state machines

### 2.7 Planning Phase Vocabulary

- Task decomposition, execution batches, sense checks
- Inter-task guidance, executor notes
- Plan versioning (`plan_v1` through `plan_v6`)

---

## 3. Quarantine Adapter Locations

All Megaplan compatibility bridge behavior is quarantined in three named
adapter modules under `arnold/pipelines/megaplan/_pipeline/`. Generic
modules import *none* of these.

### 3.1 `schema_registry_adapter.py`

**Path:** `arnold/pipelines/megaplan/_pipeline/schema_registry_adapter.py`

**Owns:**
- `MEGAPLAN_CONTRACT_SCHEMA_ROOT` — environment variable constant
- `_PLAN_DIR_MARKER` — `.megaplan/plans` layout sentinel
- `derive_project_root_from_plan_dir(path)` — derive project root from a `.megaplan/plans/<plan>` path
- `resolve_contract_schema_project_root(explicit_root)` — Megaplan env/precedence resolution
- `create_contract_schema_registry(explicit_root)` — create registry from Megaplan-resolved root
- `create_step_io_contract_context(*, operation, explicit_root, fail_closed_on_write)` — create Step IO context with Megaplan schema-root resolution

**Tests:** `tests/arnold/pipelines/megaplan/test_schema_registry_adapter.py`

### 3.2 `step_io_policy_adapter.py`

**Path:** `arnold/pipelines/megaplan/_pipeline/step_io_policy_adapter.py`

**Owns:**
- `STEP_IO_POLICY_ENV` (`MEGAPLAN_STEP_IO_CONTRACT_MODE`) — environment variable constant
- `STEP_IO_READ_LENIENT_ENV` (`MEGAPLAN_STEP_IO_CONTRACTS_OFF`) — environment variable constant
- `megaplan_step_io_policy_path(plan_dir)` — derive `.megaplan/policies/step_io_contract_modes.json` path
- `megaplan_step_io_read_lenient_escape_on()` — check lenient-read escape (reads env directly, no parameter)
- `resolve_megaplan_step_io_policy(*, configured_mode, plan_dir, state_config, policy_data, policy_path, binding, producer_typed, consumer_typed, read_lenient_escape)` — Megaplan env/policy resolution (keyword-only, reads env internally)
- `load_megaplan_step_io_policy(plan_dir)` — load persisted Megaplan policy
- `write_megaplan_step_io_policy(plan_dir, policy)` — write Megaplan policy
- `megaplan_policy_for_envelope(envelope, plan_dir, ...)` — compute effective policy for an envelope
- `has_megaplan_step_io_self_validation_marker(plan_dir)` — check marker
- `record_megaplan_step_io_self_validation_marker(plan_dir, typed_artifacts)` — write marker

**Tests:** `tests/arnold/pipelines/megaplan/test_step_io_policy_adapter.py`

### 3.3 `artifact_adapter.py`

**Path:** `arnold/pipelines/megaplan/_pipeline/artifact_adapter.py`

**Owns:**
- `artifact_root_as_plan_dir(ctx: StepContext) -> str` — bridge `artifact_root` to legacy `plan_dir` string

**Tests:** `tests/arnold/pipelines/megaplan/test_artifact_adapter.py`

---

## 4. M0 Out-of-Scope Items

The following are explicitly **not** addressed by this M0 boundary lock.
They remain unchanged and are deferred to future milestones.

| Out-of-Scope Item | Rationale |
|---|---|
| Moving `RunOutcome` | Owned by executor convergence work (future milestone) |
| Creating `StepContract` | Owned by contract registry work (future milestone) |
| Executor convergence | Owned by m3-executor-convergence |
| Deleting Megaplan compatibility shims beyond what boundary gates prove safe | Boundary gates only enforce no new leakage; existing Megaplan-owned adapters are the compatibility surface |
| Changing `arnold/control` or `arnold/supervisor` | `arnold/control/` now exists (post-M0); `arnold/supervisor/` does not. Included in boundary scan. |

---

## 5. Evidence-Pack Runtime Validation Requirement

The `arnold/pipelines/evidence_pack` pipeline is a non-Megaplan pipeline
that must remain independent. M0 boundary tests prove zero Megaplan imports
in evidence-pack production code.

**Runtime validation note:** Prep research did not confirm evidence-pack
runtime behavior because that worker failed structurally. This
implementation must run the evidence-pack test suite directly:

```
pytest tests/arnold/pipelines/evidence_pack/
```

The evidence-pack test suite includes:
- `tests/arnold/pipelines/evidence_pack/test_steps.py`
- `tests/arnold/pipelines/evidence_pack/test_pipelines.py`
- `tests/arnold/pipelines/evidence_pack/test_end_to_end.py`

Static import proof must also pass:
```
rg "arnold\.pipelines\.megaplan|from megaplan|import megaplan" arnold/pipelines/evidence_pack
```
→ Zero matches in production code.

---

## 6. Boundary Enforcement Summary

| Gate | Scope | Status (post-M0) |
|---|---|---|
| AST import gate | `arnold/pipeline`, `arnold/runtime`, `arnold/control` (if present), `arnold/supervisor` (if present) | Must not import from `arnold.pipelines.megaplan` |
| Raw-source token gate | Same packages, scans comments + docstrings + executable code | Must not contain `.megaplan`, `MEGAPLAN_`, `GateRecommendation`, `STATE_*`, `megaplan.pipeline-manifest.v1` |
| Evidence-pack isolation | `arnold/pipelines/evidence_pack/**` | Zero imports from `arnold.pipelines.megaplan` |
| Schema caller guard | `arnold/pipelines/megaplan/**` | No `registry_root.*plan_dir` or `plan_dir.*registry_root` in production code |
| Step IO migration guard | `arnold/pipeline/**` | No `M0_REMOVE_STEP_IO_COMPAT`, `plan_dir=`, `STEP_IO_POLICY_ENV`, `STEP_IO_READ_LENIENT_ENV`, `step_io_read_lenient_escape_on` |

---

## 7. Ownership Summary

```
arnold/pipeline/          → Generic Arnold substrate (no Megaplan ownership)
arnold/runtime/           → Generic runtime carriers (no Megaplan ownership)
arnold/pipelines/megaplan/_pipeline/
  ├── schema_registry_adapter.py   → Megaplan schema-root bridge
  ├── step_io_policy_adapter.py    → Megaplan Step IO env/policy bridge
  └── artifact_adapter.py          → Megaplan artifact-root bridge
arnold/pipelines/evidence_pack/    → Independent non-Megaplan pipeline
```
