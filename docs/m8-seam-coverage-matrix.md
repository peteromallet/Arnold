# M8 Seam-Coverage Matrix

Every architectural-spine seam, classified as **implemented**, **delegated** (to
Evidence-First), or **out-of-scope**, with concrete implementation and test
evidence for implemented rows.

## Required Columns

| # | Spine Seam | Status | Implementation Location | Test Evidence |
|---|-----------|--------|------------------------|---------------|
| 1 | Step⇄Step (inter-step data flow) | **implemented** | See row detail | See row detail |
| 2 | Step⇄Model (incl. Engine⇄Worker) | **implemented** | See row detail | See row detail |
| 3 | Step⇄State | **implemented** | See row detail | See row detail |
| 4 | Author⇄Runtime | **implemented** | See row detail | See row detail |
| 5 | Engine⇄World | **implemented** | See row detail | See row detail |
| 6 | Control-flow forks | **implemented** | See row detail | See row detail |

---

## 1. Step⇄Step (inter-step data flow)

**Status:** implemented

Data flows between steps through typed ports, edges, and the pipeline graph.

### Implementation

| Component | File:Line | Role |
|-----------|-----------|------|
| `Port` / `PortRef` | `arnold/pipeline/types.py:158-220` | Declared typed ports and references with content-type and cardinality |
| `Edge` | `arnold/pipeline/types.py:65-79` | Labelled, typed transition between stages |
| `Stage` / `ParallelStage` | `arnold/pipeline/types.py:280-480` | Single-step and fan-out stage wrappers with typed `consumes`/`produces` |
| `Pipeline` | `arnold/pipeline/types.py:500-560` | Named DAG of stages, edges, and binding map |
| `StepIOEnvelope` | `arnold/pipeline/step_io_contract.py:50-85` | Envelope with schema_version, logical_type, content_type, payload |
| `classify_step_io_contract` | `arnold/pipeline/step_io_contract.py:85-190` | Classifies a payload as TYPED_VALID/INVALID/LEGACY_UNKNOWN |
| `evaluate_step_io_handoff` | `arnold/pipeline/step_io_handoff.py:60-151` | Full read/write handoff: classify → resolve policy → validate version range |
| `SeamId` / `SeamResolution` | `arnold/pipeline/step_io_seams.py:14-174` | Stable seam identifiers resolved from pipeline binding maps |
| `PipelineBuilder` | `arnold/pipeline/builder.py:19-171` | Policy-free builder with auto-linking edges and binding-map derivation |
| `derive_binding_map` | `arnold/pipeline/declaration_lowering.py` | Derives (consumer_step, consumer_port) → (producer_step, producer_port) bindings from typed port declarations |
| `run_pipeline` | `arnold/pipeline/executor.py:70-260` | Neutral executor that walks stages by following Edge labels |

### Test Evidence

| Test File | What It Proves |
|-----------|---------------|
| `tests/arnold/pipeline/test_evidence_pack_expressibility.py` | StepInvocation + Port/PortRef shape expressibility for multi-content-type fan-out-reduce |
| `tests/arnold/pipeline/test_pattern_topology.py` | Pipeline graph connectivity, edge dispatch |
| `tests/arnold/pipeline/test_select.py` | Port selection and routing |
| `tests/arnold/pipeline/test_contract_result.py` | ContractResult shape correctness |
| `tests/arnold/pipeline/test_contracts.py` | ContractLedger coercion table |
| `tests/arnold/pipeline/test_port_metadata.py` | Port metadata round-trip |
| `tests/arnold/pipeline/test_step_io_seams.py` | SeamId parsing and resolution |
| `tests/arnold/pipelines/evidence_pack/test_pipelines.py` (24 tests) | validator.validate passed for both initial and continuation pipeline shapes; typed Port/PortRef bindings across all 5+2 stages |
| `tests/arnold/pipelines/evidence_pack/test_steps.py` (50 tests) | All 5 Step classes produce correct StepResult with contract payloads |
| `tests/arnold/pipelines/evidence_pack/test_end_to_end.py` (7 tests) | Full initial + continuation pipeline execution through named persisted JSON artifacts |

### Named Artifact Suspend/Continuation

The evidence-pack verifier proves Step⇄Step data flow across a suspend/resume
boundary using **only named persisted JSON artifacts** (see §7 below). The
initial pipeline writes `verifier.checkpoint` (with `status: "suspended"`) and
`verifier.verdict` to `ctx.artifact_root`; the continuation pipeline reads them
back as external `ReadRef`s and resumes at `human_review`. No StepResult,
executor-local state, or in-memory carry-over is used. This is proven by
`tests/arnold/pipelines/evidence_pack/test_end_to_end.py` (T10/T11).

---

## 2. Step⇄Model (incl. Engine⇄Worker)

**Status:** implemented

Every model-output path is captured through a single chokepoint, structurally
audited against a schema, and budget-checked with a real tokenizer assembly.

### Implementation

| Component | File:Line | Role |
|-----------|-----------|------|
| `capture_step_output` | `arnold_pipelines/megaplan/model_seam.py:210-275` | Single chokepoint: parses model output, runs structural audit, returns ContractResult |
| `audit_step_payload` | `arnold_pipelines/megaplan/model_seam.py:308-370` | Structural audit entry point (delegates to `_audit_capture_payload` → `validate_payload_against_schema`) |
| `budget_model_input` | `arnold_pipelines/megaplan/model_seam.py:1-210` | Real-tokenizer assembly-time budget check (catches char→token overflow) |
| `render_step_message` | `arnold_pipelines/megaplan/model_seam.py:1-210` | Renders step message with budget metadata attached |
| `StepInvocation` | `arnold/pipeline/step_invocation.py` | Worker invocation shape with adapter-kind resolution |
| `StepInvocationAdapterRegistry` | `arnold/pipeline/step_invocation.py` | Adapter registry (model accepted; tool/human/state/arbitrary customs fail-closed) |
| Worker capture chokepoints | `arnold_pipelines/megaplan/workers/shannon.py:2931`, `arnold_pipelines/megaplan/workers/_impl.py:3507-4005`, `arnold_pipelines/megaplan/execute/timeout.py:155`, `arnold_pipelines/megaplan/execute/batch.py:1488`, `arnold_pipelines/megaplan/steps/agent.py:91` | Production call sites route through `capture_step_output` |
| Handler capture chokepoints | `arnold_pipelines/megaplan/handlers/review.py:682`, `arnold_pipelines/megaplan/handlers/execute.py:1100` | Handler output paths structurally audited |

### Test Evidence

| Test File | What It Proves |
|-----------|---------------|
| `tests/arnold/pipelines/megaplan/test_model_seam.py` | 50+ tests covering capture_step_output (legacy payload, typed contract, normalization, per-step schema validation, structural audit rejection, recovery provenance) |
| `tests/m8/regression/test_structural_regressions.py` (T2, 9 tests) | Additional-properties rejection and malformed named-output capture through capture_step_output |
| `tests/m8/regression/test_budget_suspension_regressions.py` (T3, 14 tests) | Budget overflow via budget_model_input raising ModelBudgetError; render_step_message budget attachment |
| `tests/m8/regression/test_route_bypass.py` (T12, 11 tests) | Route-bypass prevention: tool/human/state/arbitrary customs rejected; model accepted; no-invocation passes |
| `tests/arnold/pipelines/megaplan/test_pipeline_contracts.py` | Typed-port consumer validation |
| `tests/test_contract_validation.py` | Direct payload validation |
| `docs/m8-outbound-coverage.md` (T19) | Catalogs all 8 validate_payload_against_schema, 10 audit_step_payload, 10 capture_step_output production call sites |

---

## 3. Step⇄State

**Status:** implemented

Pipeline state is carried as an opaque `Mapping[str, Any]` and mutated through
ordered `StateDelta` patches. Steps interact with state exclusively through
`StepContext.state`.

### Implementation

| Component | File:Line | Role |
|-----------|-----------|------|
| `StateDelta` | `arnold/pipeline/state.py:10-50` | Ordered multi-patch container |
| `apply_delta` | `arnold/pipeline/state.py:60-120` | Applies StateDelta patches to a state value |
| `StepContext.state` | `arnold/pipeline/types.py:430-460` | Opaque state Mapping passed to every step |
| `StepResult.state_patch` | `arnold/pipeline/types.py:490-520` | Optional StateDelta returned by a step |
| Executor state application | `arnold/pipeline/executor.py:120-150` | After each step, `apply_delta(state, result.state_patch)` merges the patch into working state |

### Test Evidence

| Test File | What It Proves |
|-----------|---------------|
| `tests/arnold/pipeline/test_executor.py` (35 tests) | StateDelta application during pipeline execution |
| `tests/arnold/pipeline/test_executor_parallel.py` | Parallel-stage state isolation |
| `tests/arnold/runtime/test_envelope.py` | RuntimeEnvelope state round-trip |
| `tests/arnold/pipelines/evidence_pack/test_end_to_end.py` (7 tests) | End-to-end proves that suspension and completion are observable ONLY through named persisted JSON artifacts — never through StepResult.state_patch inspection |

---

## 4. Author⇄Runtime

**Status:** implemented

Pipeline authors declare stages, edges, typed ports, and profile bindings through
the public `PipelineBuilder` API (m7). Runtime behavior (profiles, Step-IO
policy, budget authority, parallel safety) is configured via neutral contracts.

### Implementation

| Component | File:Line | Role |
|-----------|-----------|------|
| `PipelineBuilder` | `arnold/pipeline/builder.py:19-171` | Public authoring API: `add_stage`, `add_parallel_stage`, `add_caller_supplied_edges`, `attach_resource_bundles` |
| Typed declaration lowering | `arnold/pipeline/declaration_lowering.py:1` | Shared lowered view for public `Stage.reads=(PortRef(...),)` and `Stage.writes=(Port(...),)` author declarations |
| Runtime typed handoff enforcement | `arnold/pipeline/executor.py:797` | `_enforce_typed_step_io_handoff` blocks invalid typed payloads before state merge and before consumers run |
| Step-IO handoff evaluator | `arnold/pipeline/step_io_handoff.py:60` | Classifies producer payloads and resolves Author⇄Runtime policy outcomes for typed crossings |
| Static C4 contract checks | `arnold/pipeline/c4_static_checks.py:1` | Pre-run declaration, schema-version, structural, invocation, and capability checks over lowered author declarations |
| Contract-aware CLI | `arnold/pipeline/_cli_check.py:1` | `arnold pipeline check --module dotted.path:factory` loads real authored pipelines and renders hard findings |
| Capability alias normalization | `arnold/agent/costing/model_resource_capabilities.py:1` | Maps author-facing `requires-vision-model` and `requires-image-decoder` aliases into the closed runtime capability vocabulary |
| `PipelineRegistry` | `arnold/pipeline/registry.py` | Named pipeline registration and discovery |
| Profile loading | `arnold/pipeline/profiles.py` | TOML profile parsing, agent-spec shape validation, layer merging |
| `StepIOPolicy` | `arnold/pipeline/step_io_policy.py` | Author-supplied per-operation policies: block/allow/warn/shadow |
| `ContentTypeRegistry` | `arnold/pipeline/types.py:140-156` | Map content-type names → schema digests |
| `ContractSchemaRegistry` | `arnold/pipeline/schema_registry.py` | Neutral file-backed schema registry with hash-first lookup |
| `PipelineIdRegistry` / aggregate loading | `arnold/pipeline/pipeline_id_registry.py:24-157` | Source-controlled identity with duplicate detection across single and aggregate registries |
| `scripts/check_pipeline_id_registry.py` | T14 | Git-aware discovery + per-file rename drift + aggregate uniqueness |
| `arnold/pipelines/evidence_pack/pipeline_ids.json` | T16 | Source-controlled registry entry for evidence_pack.verifier |

### Test Evidence

| Test File | What It Proves |
|-----------|---------------|
| `tests/arnold/pipeline/test_pipeline_id_registry.py` (26 tests, T13/T15) | Aggregate duplicate detection (cross-file active stable IDs, previous IDs, seam IDs, active-vs-previous collisions), default discovery, per-file drift, three-file aggregate |
| `tests/arnold/pipeline/test_declaration_lowering.py` | Public typed `reads`/`writes` lower into effective consumes/produces with deterministic drift diagnostics |
| `tests/arnold/pipeline/test_builder.py` | `PipelineBuilder.build(derive_bindings=True)` derives neutral binding-map entries from the lowered declaration view |
| `tests/arnold/pipeline/test_executor.py` | Runtime handoff enforcement rejects wrong typed payloads before state merge and before consumers run |
| `tests/arnold/pipeline/test_c4_static_checks.py` | Static C4 checks resolve lowered binding-map edges, schema availability, structural subsets, invocation shape, and capability aliases |
| `tests/arnold/pipeline/test_cli_pipeline_check.py` | `arnold pipeline check --module dotted.path:factory` validates real pipeline factories with clean and failing reports |
| `tests/arnold/pipeline/test_model_resource_capabilities.py` | Author-facing capability aliases normalize to the closed canonical vocabulary while unknown names fail closed |
| `tests/arnold/pipeline/test_profiles.py` | Profile loading and validation |
| `tests/arnold/pipeline/test_schema_registry.py` | Schema registry read/write/version-acceptance |
| `tests/arnold/pipeline/test_registry.py` | PipelineRegistry discovery |
| `tests/arnold/pipelines/evidence_pack/test_pipelines.py` (24 tests) | PipelineBuilder construction + validator.validate for initial and continuation shapes |

---

## 5. Engine⇄World

**Status:** implemented

The engine interacts with the filesystem via `artifact_root`, runtime envelopes,
and operation registries. External side effects (network calls, subprocess
spawning) are scoped to worker/handler boundaries.

### Implementation

| Component | File:Line | Role |
|-----------|-----------|------|
| `run_pipeline` artifact_root | `arnold/pipeline/executor.py:70-90` | All artifact I/O rooted under a caller-supplied directory |
| `RuntimeEnvelope` | `arnold/runtime/envelope.py` | Run-level identity and cross-cutting state (no `ContractResult` composition) |
| `OperationRegistry` | `arnold/runtime/operations.py` | Pluggable I/O hooks (null implementation in neutral executor) |
| Content validation (blob by-ref) | `arnold/pipeline/content_validation.py` | Content-type keyed validation hooks for blob metadata |
| `select_audit_mode` | `arnold/pipeline/audit_policy.py` | Deterministic full/manifest audit-mode selection for size thresholds |
| Evidence-pack artifact I/O | `arnold/pipelines/evidence_pack/steps.py:53-72` | Deterministic `_artifact_path`, `_write_json`, `_read_json` helpers |

### Test Evidence

| Test File | What It Proves |
|-----------|---------------|
| `tests/arnold/pipeline/test_executor.py` (35 tests) | artifact_root propagation, RuntimeEnvelope preservation |
| `tests/arnold/runtime/test_envelope.py` | RuntimeEnvelope shape and round-trip |
| `tests/arnold/pipeline/test_content_validation.py` | Blob metadata validation |
| `tests/arnold/pipeline/test_audit_policy.py` | Full vs manifest audit-mode selection |
| `tests/m8/benchmark/test_helpers.py` (T4) | 100MiB validation consumes sidecar manifest without rehashing blob |
| `tests/m8/benchmark/test_benchmark_gate.py` + `tests/m8/benchmark/test_gate.py` (T5, 25 tests) | Benchmark tier generation through 100MiB, hash-on-write manifests, locked by-ref validation |
| `tests/arnold/pipelines/evidence_pack/test_end_to_end.py` (7 tests) | Artifact I/O: checkpoint.json, evidence_pack.json, verdict.json, attestation.json written and read through artifact_root |

---

## 6. Control-flow forks

**Status:** implemented

Pipeline execution branches at gate decisions, parallel fan-out, override edges,
and edge dispatch. All forks are expressed through typed `Edge` objects and
resolved by the neutral `resolve_edge` function.

### Implementation

| Component | File:Line | Role |
|-----------|-----------|------|
| `Edge` (kind: normal/gate/override) | `arnold/pipeline/types.py:65-79` | Three-edge-kind vocabulary for all control-flow forks |
| `PipelineVerdict` (recommendation/override) | `arnold/pipeline/types.py:87-100` | Structured verdict for gate/override dispatch |
| `resolve_edge` | `arnold/pipeline/routing.py:30-143` | Policy-neutral edge resolution with vocabulary validation |
| `RoutingError` | `arnold/pipeline/routing.py:21-27` | Raised when no edge matches the current routing signal |
| Parallel fan-out | `arnold/pipeline/executor.py:150-220` | `ThreadPoolExecutor`-backed concurrent step execution with caller-supplied `join` |
| `ParallelSafePredicate` | `arnold/pipeline/executor.py:47-60` | Contract for runtime-supplied parallel-safety guard |
| `DEFAULT_PARALLEL_SAFE` | `arnold/pipeline/executor.py:57-65` | Accepts everything — runtimes supply their own predicate |
| `reduce_contract_results` (MAX_WINS lattice) | `arnold/pipeline/contract_reduce.py:31-266` | Deterministic status-lattice reduction: COMPLETED < SUSPENDED < FAILED |
| Suspension-aware fan-out join in evidence-pack | `arnold_pipelines/evidence_pack/pipeline.py:50-70` | Barrier `_join_validators` returns the deterministic reduce routing result regardless of individual outcomes |

### Test Evidence

| Test File | What It Proves |
|-----------|---------------|
| `tests/arnold/pipeline/test_executor.py` (35 tests) | Edge dispatch, gate routing, parallel fan-out |
| `tests/arnold/pipeline/test_executor_parallel.py` | Parallel stage concurrency and join |
| `tests/arnold/pipeline/test_contract_reduce.py` | MAX_WINS lattice: FAILED > SUSPENDED > COMPLETED |
| `tests/m8/regression/test_budget_suspension_regressions.py` (T3, 14 tests) | Suspended child propagates SUSPENDED to parent through reduce_contract_results; FAILED > SUSPENDED lattice behavior; ordering invariance |
| `tests/m8/regression/test_route_bypass.py` (T12, 11 tests) | Fail-closed for unknown adapter kinds in StepInvocation routing |
| `tests/arnold/pipeline/test_pattern_joins.py` | Join patterns (majority_vote, weighted_vote) |
| `tests/arnold/pipeline/test_pattern_stops.py` | Loop-stop predicates |

---

## 7. Named Artifact Suspend/Continuation (Evidence-Pack)

**Status:** implemented

The evidence-pack verifier proves suspend/resume across a fresh pipeline boundary
using only named persisted JSON artifacts — no executor-local state or
StepResult carry-over.

### Implementation

| Component | File:Line | Role |
|-----------|-----------|------|
| `HumanReviewStep` (suspend path) | `arnold/pipelines/evidence_pack/steps.py:450-620` | First run: writes `verifier.checkpoint` (with `status: "suspended"`) + Suspension envelope + returns ContractResult(status=SUSPENDED) |
| `HumanReviewStep` (resume path) | `arnold/pipelines/evidence_pack/steps.py:450-620` | Second run (continuation): reads `human_input` from `ctx.inputs`, resolves gate, writes attestation on approval |
| `VERIFIER_ARTIFACT_CHECKPOINT` | `arnold/pipelines/evidence_pack/verifier.py:50-53` | Named constant: `"verifier.checkpoint"` |
| `VERIFIER_ARTIFACT_ATTESTATION` | `arnold/pipelines/evidence_pack/verifier.py:47-49` | Named constant: `"verifier.attestation"` |
| `VERIFIER_ARTIFACT_VERDICT` | `arnold/pipelines/evidence_pack/verifier.py:53-55` | Named constant: `"verifier.verdict"` |
| `build_initial_pipeline` | `arnold_pipelines/evidence_pack/pipeline.py:70-170` | `ingest → validators(∥) → reduce → human_review → emit_attestation` |
| `build_continuation_pipeline` | `arnold_pipelines/evidence_pack/native.py:250-340` | Fresh continuation pipeline reads persisted verdict/evidence-pack inputs through named references |

### Suspend/Continuation Proof

The suspension boundary is proven exclusively through named persisted JSON
artifacts:

1. **Initial run suspends** → `verifier.checkpoint` JSON exists with
   `status: "suspended"`; `verifier.attestation` is absent;
   `verifier.evidence_pack` and `verifier.verdict` are preserved.

2. **Continuation run** is a **fresh** pipeline invocation (not executor-local
   state resume) with `entry='human_review'`. The continuation reads the
   checkpoint, verdict, and evidence-pack artifacts from `ctx.artifact_root` via
   external `ReadRef`s.

3. **Approval path**: `human_input` with `decision: "approved"` → `emit_attestation`
   writes `verifier.attestation` with the verdict and evidence pack ID.

4. **Rejection path**: `human_input` with `decision: "rejected"` → no
   attestation written; checkpoint preserved.

5. **Graceful missing-suspension**: If checkpoint/verdict artifacts are missing
   at continuation start, the pipeline handles it gracefully without crashing.

All assertions inspect **only** named JSON files on disk — never
`StepResult`, `run_pipeline` return values, or executor-internal state.

### Test Evidence

| Test File | What It Proves |
|-----------|---------------|
| `tests/arnold/pipelines/evidence_pack/test_end_to_end.py` (7 tests, T10/T11) | 3 initial-suspension tests (checkpoint exists with `status: "suspended"`, attestation absent, evidence_pack + verdict preserved); 4 continuation tests (approval writes attestation, rejection leaves no attestation, existing artifacts preserved, graceful missing-suspension handling). ALL assertions observe only named persisted JSON artifacts. |

---

## 8. Aggregate Registry

**Status:** implemented

Multiple source-controlled `pipeline_ids.json` files are discovered, loaded,
and validated as an aggregate set with cross-file duplicate detection.

### Implementation

| Component | File:Line | Role |
|-----------|-----------|------|
| `load_pipeline_id_registry` | `arnold/pipeline/pipeline_id_registry.py:24-27` | Load and validate a single registry file |
| `load_pipeline_id_registries` | `arnold/pipeline/pipeline_id_registry.py:30-33` | Load and validate multiple registry files as one aggregate set |
| Aggregate duplicate detection | `arnold/pipeline/pipeline_id_registry.py:36-157` | Cross-file duplicate active stable IDs, duplicate previous stable IDs, duplicate seam IDs, and active-vs-previous stable ID collisions |
| `PipelineIdRegistryError` | `arnold/pipeline/pipeline_id_registry.py:20-21` | Raised when the registry violates the M1 metadata contract |
| `scripts/check_pipeline_id_registry.py` | T14 | Discovers all source-controlled `pipeline_ids.json` via `git ls-files` (fallback glob), supports explicit `--registry` paths, runs aggregate uniqueness, compares rename drift per file via `git merge-base` |
| Evidence-pack registry entry | `arnold/pipelines/evidence_pack/pipeline_ids.json` (T16) | `stable_id: "evidence_pack.verifier"`, `typed_contract_capable: true` |
| Megaplan registry entry | `arnold/pipelines/megaplan/_pipeline/pipeline_ids.json` | Existing megaplan entry |

### Aggregate Wording

The aggregate registry validates that no two pipelines share a stable identity
across **any** registry files in the source tree. Specifically:

- **Duplicate active stable IDs** across any two registry files → `PipelineIdRegistryError`.
- **Duplicate previous stable IDs** (rename history) across any two files → error.
- **Duplicate seam IDs** across any two files → error.
- **Active-vs-previous collision**: a pipeline in file A has `stable_id` X while
  a pipeline in file B lists X in its `previous_stable_ids` → error (regardless
  of encounter order).

The `check_pipeline_id_registry.py` script enforces these invariants at CI time
by discovering all `pipeline_ids.json` files under source control and running
the aggregate validator. It also compares per-file rename drift (current
`stable_id` vs base-branch `stable_id` for each named pipeline).

### Test Evidence

| Test File | What It Proves |
|-----------|---------------|
| `tests/arnold/pipeline/test_pipeline_id_registry.py` (26 tests, T13/T15) | Default discovery finds registries and returns absolute paths; main() no-args passes; per-file drift comparison across two file pairs; `--no-drift` flag skips drift; multiple `--registry` paths validate both; aggregate duplicate detection via main() exits 1; three-file aggregate (all valid loads 3 pipelines, non-adjacent duplicate seam detected, cross-file active/previous collision across 3 files); edge cases (empty pipelines loads, missing file raises FileNotFoundError, non-object pipeline entry raises PipelineIdRegistryError) |
| `scripts/check_pipeline_id_registry.py` dry-run | Passes with 2 discovered registry files (megaplan + evidence-pack) and no duplicate stable IDs, seam IDs, or active/previous collisions |

---

## Production Human-Review UX — Out of Scope

**Status:** out-of-scope

The production human-review **UX** is explicitly out of scope for M8. The
evidence-pack verifier proves the **structural suspend/continuation seam**:
it suspends at `human_review`, writes a checkpoint artifact, and resumes via a
fresh pipeline invocation with a programmatic `human_input` fixture (a dict
matching the `resume_input_schema`). The gate is driven to completion by a
test-supplied decision — never by waiting on a real human.

What is **NOT** implemented (and is intentionally out of scope for M8):

- An interactive CLI or web UI for human operators to approve/reject.
- A notification, queue, or worklist system for pending reviews.
- Persisted audit trails or human-operator identity tracking.
- Timeout, escalation, or delegation of human review tasks.
- Any runtime that blocks waiting for human input.

These are feature work on top of m4 suspension composition, not part of the
acceptance gate. M8 only confirms that the **seam** (suspend → persist checkpoint
→ resume from checkpoint) works structurally. The UX layer is delegated to the
Evidence-First control plane or a future milestone.

---

## Summary

| Spine Seam | Status | Implementation Loc | Evidence |
|-----------|--------|-------------------|----------|
| Step⇄Step | implemented | `arnold/pipeline/types.py`, `step_io_contract.py`, `step_io_seams.py`, `step_io_handoff.py`, `builder.py`, `executor.py` | 50+ tests across test_step_io_seams, test_pipelines, test_end_to_end, test_evidence_pack_expressibility |
| Step⇄Model | implemented | `model_seam.py:851-1722`, `step_invocation.py`, 10 worker capture sites, 7 handler audit sites | test_model_seam.py (50+), T2 (9), T3 (14), T12 (11), outbound coverage catalog |
| Step⇄State | implemented | `state.py`, `types.py` (StepContext/StepResult), `executor.py` (apply_delta) | test_executor.py (35), test_executor_parallel.py, test_end_to_end.py (7) |
| Author⇄Runtime | implemented | `builder.py`, `declaration_lowering.py:1`, `executor.py:797`, `step_io_handoff.py:60`, `c4_static_checks.py:1`, `_cli_check.py:1`, `model_resource_capabilities.py:1`, `profiles.py`, `step_io_policy.py`, `pipeline_id_registry.py`, `check_pipeline_id_registry.py` | test_pipeline_id_registry.py (26), test_declaration_lowering.py, test_builder.py, test_executor.py, test_c4_static_checks.py, test_cli_pipeline_check.py, test_model_resource_capabilities.py, test_pipelines.py (24), test_profiles.py, test_schema_registry.py |
| Engine⇄World | implemented | `executor.py`, `runtime/envelope.py`, `audit_policy.py`, `content_validation.py`, evidence_pack `steps.py` | test_executor.py (35), T4, T5 (25), test_end_to_end.py (7) |
| Control-flow forks | implemented | `routing.py`, `contract_reduce.py`, `executor.py` (parallel fan-out) | test_executor.py (35), test_contract_reduce.py, T3 (14), T12 (11) |
| Named Artifact Suspend/Continuation | implemented | evidence_pack `steps.py`, `verifier.py`, `pipelines.py` | test_end_to_end.py (7) — all assertions via named persisted JSON artifacts only |
| Aggregate Registry | implemented | `pipeline_id_registry.py`, `check_pipeline_id_registry.py`, `pipeline_ids.json` (×2) | test_pipeline_id_registry.py (26) |
| Human-Review UX | **out-of-scope** | — | Delegated to Evidence-First or future milestone |

**No spine seam is unaccounted.** Every seam in the architectural spine
(Step⇄Step, Step⇄Model incl. Engine⇄Worker, Step⇄State, Author⇄Runtime,
Engine⇄World, and control-flow forks) is marked **implemented**, with concrete
file:line references and test evidence. The human-review UX layer is explicitly
**out-of-scope** and delegated.

---

## SHAPE-not-MEANING Limit

This matrix documents that the M8 contract guarantees **structural** validity,
NOT semantic correctness. The contract ensures:

- Payloads conform to their declared JSON Schema (`additionalProperties: false`,
  required fields present, correct types).
- Model budgets are checked with a real tokenizer (not character counts).
- Suspended children propagate SUSPENDED to parents (not silently treated as
  completed).
- Unknown adapter kinds are fail-closed (not silently accepted).

The contract does NOT catch:

- A semantically wrong but structurally valid payload (a well-typed lie still passes).
- Performance regressions that don't exceed benchmark thresholds.
- Human judgment errors in the review gate (the gate only validates the structure
  of the decision, not its correctness).
- Any failure class not expressible as a structural invariant.

"Validated" is never oversold as "correct."
