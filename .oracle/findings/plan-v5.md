# Plan — Typed NBF worker admission, disposition, and scheduling control plane

## 1. Planning basis and custody

This revision incorporates every accepted W4 Oracle finding as a bounded final contract correction. It preserves every frozen product criterion, authority boundary, custody rule, delivery rule, model policy, and merge checkpoint.

- Branch: `megado-nbf-guard-0826`
- Planning HEAD recorded by the prior immutable snapshot: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Immutable source base: `origin/main` at `798c50619204010ed3f4297fbb57988fe9381924`
- Superseded immutable plan-v4 SHA-256: `19d37c43207e116877ba0f3b5391fdfd1cf55f8cffda3d11e9869feb8ba734db`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Protected untracked artifact: `.oracle/briefs/planner-sol.md`
- Earlier protected planning and evolution artifacts remain governed by `custody.md`.
- `.oracle/tasklist.md` is foreign onboarding-run evidence and remains excluded.
- `tests/cloud/test_runtime_attestation.py` contains 42 existing tests.
- OMP route membership is read from the machine-readable `omp models --json` surface.
- Native routes must provide their equivalent positive model/runtime/provider proof from the existing native backend seam. Missing, unreadable, ambiguous, or stale proof rejects typedly before launch.
- Native models are not forced into the OMP catalog, and no speculative network health check is introduced.
- No files were edited and no mutating commands or tests were run by the read-only revision owner.

The source update, custody requirements, and this revision do not widen the frozen product scope or authorize a merge to `main`.

## 2. Revision delta from immutable plan v4

This revision makes the following material W4 corrections:

1. Removes `child_admission_receipt_id` from the composite route-transition event.
   - The linked child receipt ID is derived deterministically after commit from the composite event ID and canonical child identity.
   - Fresh replay must reproduce the identical receipt ID byte-for-byte.
2. Adds a distinct typed `no_launch` outcome with `launch_state=not_started`.
   - It is not a worker death, worker terminal event, terminal fingerprint, provider observation, phase failure, or breaker input.
   - Positive controlled sequencing evidence is required before a reservation may reconcile as `released_no_launch`.
   - Missing, stale, or contradictory sequencing evidence produces `unresolved_launch`.
3. Freezes a controlled final-launch adapter that durably records `not_started`, `entered`, and `accepted` around every launch-capable operation.
   - Reconciliation occurs before consumer projection.
   - Identical redispatch after a proven no-launch release is allowed only through a fresh admission reservation.
4. Closes the production no-WBC bypass.
   - Every production `run_step_with_worker` call enters `dispatch_with_admission`.
   - The implementation either constructs the WBC adapter internally or typedly rejects `wbc_dispatch=None` before any legacy launch path.
5. Adds one canonical `worker_terminal_outcome` event for every non-scheduling result after launch acceptance.
   - It contains the semantic fingerprint, reservation, receipt, execution-context, and disposition links.
   - Projection and redispatch CAS consume it before reservation closure.
   - Provider exhaustion is recorded once in its typed provider form and is not double-recorded as an ordinary failure.
6. Restricts changed-precondition creation to canonical reason-specific producers.
   - Producers derive before/after content identities from authoritative state and evidence.
   - Ledger CAS validates the evidence-to-identity binding and rejects caller-forged unequal identifiers.
7. Makes NBF-06 depend on NBF-01 through NBF-05.
   - T8 implementation cannot begin until the shared disposition, context, signal, and generated-inventory gates pass.
8. Freezes durable two-scan confirmation in the existing incident ledger.
   - The schema, projection owner, key, versioned TTL policy, atomic replacement, consumption, expiry, restart, PID-reuse, progress-reset, and supervisor-incarnation rules are explicit.
9. Adds a targeted admission-authority bypass checker.
   - It covers forbidden authority calls and launch construction across all three doors and chain origins.
   - NBF-03 and NBF-07 run it; the existing grep remains a readable secondary check.
10. Updates task ownership, dependencies, focused suites, structural scenarios, crash matrices, completion criteria, and final evidence collection to match these corrections.

No prepare/commit protocol, scheduler, store, journal, rotator, family lease, or `[XHARD]` task is introduced.

## 3. Current-state inventory

| Criterion | Status | Existing basis | Remaining work |
|---|---|---|---|
| 1. Unique admission gate | **Partially satisfied** | `cloud/runtime_attestation.py::require_production_worker_dispatch_runtime` validates seed, manifest generation, dependency interpreter, and seed interpreter. | It lacks complete production caller coverage and does not jointly own translation, catalog, family, route-applicable liveness, source/runtime, timeout, memory, fingerprint, or reservation. |
| 2. Exactly-once launch doors | **Partially satisfied** | `run_step_with_worker` is the public worker entry; nested OMP delegates to `run_omp_step`; babysitter has a managed-launch seam. | Raw preflights, the no-WBC legacy path, and WBC ordering obscure physical ownership. Admission attempts, logical dispatches, WBC starts, and final launches are not separately proven. |
| 3. Typed death dispositions | **Partially satisfied** | `IncidentLedger.append_event` is the journal write door; cgroup-OOM evidence is partially projected. | No complete schema/helper/CLI/context transport exists. Multiple Python and shell signal paths remain silent or anonymous. |
| 4. Fingerprint redispatch block | **Missing** | Incident projection diagnoses repeated repair attempts after failure. | No stable semantic fingerprint, cross-logical-ID CAS key, canonical terminal-outcome event, evidence-bound changed-precondition producer, or atomic reservation exists. |
| 5. Joint model admission | **Partially satisfied** | Static catalog validation, model-family classification, translation, OMP membership, and native backend configuration exist independently. | No simultaneous route-applicable spec↔catalog↔family↔positive-liveness decision exists. Static authorities still accept expired `openrouter/stealth/ox-alpha`. |
| 6. Structural spy | **Missing** | Individual worker and babysitter tests exist. | No production-manifest spy proves canonical inclusion, no-WBC closure, WBC ordering, physical ownership, or gate-before-final-launch. |
| 7. Cooldown scheduling | **Partially satisfied** | `memory_cooldown_wait_secs` and post-failure cooldown recovery exist. | Cooldown is not transported as a typed scheduling result through the whole stack and still relies on post-failure counter repair. |
| 8. Provider degradation | **Missing** | Retryability classification and configured fallback rotation exist. | No typed post-launch outcome projection, sustained observation policy, bounded hold/probe, atomic transition-child event, or restart-safe return path exists. |
| Crash reconciliation | **Missing** | Running receipts and incident replay provide partial evidence. | No frozen reconciliation event distinguishes positive no-launch, recovered post-launch outcome, and ambiguous launch state. |
| Launch sequencing | **Missing** | Launch paths have local process/RPC sequencing. | No authoritative controlled adapter proves `not_started`, `entered`, and `accepted` across every launch-capable operation. |
| Two-scan durability | **Missing** | Some supervisors perform repeated observations. | No ledger-owned confirmation key, TTL, atomic replacement, expiry, restart, or reset contract exists. |
| Signal closure | **Missing** | Named Python and shell sites are known. | No generated, freshness-checked inventory proves repository-wide classification. |
| Authority closure | **Missing** | Known raw preflight symbols can be grepped. | No targeted static checker rejects forbidden authority calls and direct launch construction across doors and chain origins. |

### Fragmented controls to eliminate or subordinate

- Raw runtime refresh/require and source preflight in `workers/_impl.py`.
- The production `wbc_dispatch=None` fallback into `_run_step_with_worker_legacy`.
- `chain/source_admission.py::worker_launch_preflight` and chain-local launch refusals.
- Standalone memory admission in `handlers/shared.py`.
- OMP static catalog logic separate from current membership proof.
- Native backend selection without a positive applicable model/runtime proof returned to admission.
- Launcher-local spec translation.
- WBC attempt creation before canonical admission.
- Provider fallback decisions outside the shared scheduling seam.
- Cooldown repair and counter reset in `auto.py`.
- Terminal failures not represented by one canonical fingerprint-bearing outcome event.
- Caller-created changed-precondition IDs without authoritative evidence binding.
- Death information split among raw signal sites, state summaries, and plan events.
- Volatile or process-local two-scan state.
- Hand-maintained or partial signal-site fixtures that do not compare against live repository discovery.
- Grep-only authority checks that cannot detect aliases, imported calls, or direct launch construction.

## 4. Frozen control-plane design

### 4.1 Dispatch identities and cardinality

The implementation distinguishes:

- **Dispatch family:** one call into a physical door and any scheduling-controlled sequence of linked route attempts.
- **Logical dispatch:** one admitted attempt for one selected route/spec.
- **Physical door owner:** the single code location binding a dispatch family to `dispatch_with_admission`.
- **Admission attempt:** one invocation of `require_production_worker_dispatch_runtime` for a logical dispatch. Pre-launch scheduling conditions may cause multiple attempts.
- **Final launch:** one spawn, backend call, WBC invocation, managed command, or RPC.
- **Linked child dispatch:** a new logical dispatch authorized after a terminal parent outcome and a durable recovery or route-transition event.

Required cardinality:

```text
one dispatch family
  -> exactly one physical door owner
  -> one or more linked logical dispatches
  -> each logical dispatch has one or more admission attempts
  -> each logical dispatch has zero or one final launch
```

A fallback, recovery retry, or return-to-primary attempt never reuses the old `logical_dispatch_id`. The child contains:

```text
logical_dispatch_id
parent_logical_dispatch_id
authorizing_event_id
dispatch_family_id
physical_door_id
```

Nested OMP has one physical owner in `run_omp_step`. `_impl.py` delegates without independently invoking admission.

The plan imposes no family-wide serialization lease. Independent logical dispatches with different semantic fingerprints may proceed according to existing caller semantics. The durable invariants are:

- no logical dispatch performs more than one final launch;
- different logical IDs cannot evade duplicate reservation for the same projection key and semantic fingerprint;
- a linked recovery/fallback/return child cannot reserve or launch until the parent has a canonical terminal outcome and its authorization is durably recorded;
- an unresolved parent reservation cannot produce a child;
- a proven no-launch release closes no worker terminal state and does not count as a terminal parent for provider-driven child creation;
- every production physical door enters the shared admission seam regardless of WBC configuration.

### 4.2 One chain-inclusive admission authority

`cloud/runtime_attestation.py::require_production_worker_dispatch_runtime` is the only production worker-admission authority.

Before wiring, inventory every production caller of:

- `chain/source_admission.py::worker_launch_preflight`;
- chain-local source/runtime refusal logic;
- `refresh_runtime_launch_seed_for_worker_dispatch`;
- `require_configured_runtime_launch`;
- standalone memory/headroom refusal helpers;
- direct launch construction in `chain/__init__.py`;
- `CommonWorkerDispatchSpec.run` and its callers;
- `_run_step_with_worker_legacy`;
- `run_step_with_worker(..., wbc_dispatch=None)`;
- native backend model/runtime selection;
- OMP client/model construction.

Rules:

- Chain orchestration may prepare inputs and emit pre-admission intent, but cannot authorize or start a worker.
- Retained helpers become non-authoritative validation primitives callable only from the canonical gate.
- A chain-originated worker delegates to a frozen physical door.
- Any newly discovered direct chain launch is refactored to an existing physical door, not made a fourth authority.
- WBC pre-admission intent is not an attempt start, worker start, failure, or completion.
- Production admission occurs before `wbc_dispatch.run`.
- A scheduling condition consumes no WBC attempt and emits no WBC failure or completion.
- Every production `run_step_with_worker` invocation enters `dispatch_with_admission`.
- Under production intent, `wbc_dispatch=None` must either cause internal construction of the canonical WBC adapter or a typed pre-launch refusal.
- The production no-WBC path may not delegate directly to `_run_step_with_worker_legacy`.
- Any retained legacy implementation is development-only or is callable solely as the admitted final-launch closure.
- Production intent, manifest presence, or cloud seed selection cannot silently choose the legacy bypass.

The physical final-launch owners remain:

1. Native non-OMP routes in `workers/_impl.py`.
2. Direct and nested OMP routes in `workers/omp.py::run_omp_step`.
3. Babysitter managed launches in `cloud/babysitter/launch.py`.

Chain and WBC are origins/delegation mechanisms, not admission authorities.

### 4.3 Route-applicable positive liveness

Every production route supplies a positive, typed liveness receipt appropriate to that route.

#### OMP route

The canonical gate requires:

- successful `omp models --json` execution within a bounded timeout;
- valid JSON schema;
- unambiguous provider/model identity;
- exact current provider/model membership for the normalized route;
- consistency with static catalog and family classification.

Command failure, timeout, malformed JSON, ambiguity, absence, or provider-read failure rejects typedly.

#### Native route

The canonical gate requires a positive proof from the existing native backend seam that will construct the final client/runtime. The proof must identify:

```text
backend identity
provider identity
normalized model identity
native runtime or capability registry identity
proof generation/content identity
observed_at
```

The proof may come from the existing loaded backend registry, native capability map, configured runtime registry, or equivalent authoritative local runtime surface already used by that backend. It must prove that the selected provider/model route is presently constructible by the native launch seam.

Rules:

- A configuration string by itself is not proof.
- Missing, unreadable, ambiguous, or inconsistent native proof rejects before WBC, client, process, or RPC construction.
- Native models are not inserted into the OMP catalog merely to reuse OMP validation.
- No speculative network request or provider health probe is added to admission.
- Provider availability after admission is handled by typed `DispatchOutcome`, not by pre-launch network probing.

The admission receipt stores the applicable liveness-proof identity. OMP membership digest and native proof generation are evidence, not semantic retry identity.

### 4.4 Typed admission request, decision, and receipt

`WorkerAdmissionRequest` contains:

```text
plan_id
phase
dispatch_family_id
logical_dispatch_id
parent_logical_dispatch_id | null
authorizing_event_id | null
physical_door_id
admission_attempt
configured_spec
selected_spec
timeout_budget_s
source_revision
runtime_vector
manifest_identity
seed_identity
dependency_interpreter_identity
prompt_or_phase_input_identity
configured_fallback_chain_identity
authorized_route_identity
projection_key
expected_projection_version
production_intent
```

Injected adapters provide:

```text
route_liveness_resolver
clock
source_runtime_validator
memory_headroom_reader
ledger_projection_reader
ledger_transaction_authority
```

The gate performs:

1. Canonical translation and normalization.
2. Static catalog-row validation where applicable.
3. Model-family classification.
4. Route-applicable positive liveness validation.
5. Manifest, seed, and interpreter refresh and validation.
6. Source/runtime validation through a retained non-authoritative primitive.
7. Finite, positive, policy-valid timeout validation.
8. Memory/headroom and same-phase/spec cooldown evaluation.
9. Stable semantic dispatch-fingerprint derivation.
10. Ordinary atomic reservation, or composite route-transition-and-child reservation, through the ledger transaction authority.
11. Immutable receipt return only after the append commits.

Outcome:

```text
WorkerAdmissionReceipt
| SchedulingCondition
| AdmissionRefusal
```

The gate does not sleep, probe, emit retry-wait evidence, invoke a final launch, implement provider-degradation policy, or recursively call itself.

The receipt contains:

```text
admission_receipt_id
plan_id
phase
dispatch_family_id
logical_dispatch_id
parent_logical_dispatch_id | null
authorizing_event_id | null
physical_door_id
admission_attempt
normalized_spec
provider
model
family
route_liveness_kind
route_liveness_identity
route_liveness_digest
timeout_budget_s
source_revision
runtime_vector
manifest_identity
seed_identity
dependency_interpreter_identity
semantic_dispatch_fingerprint
projection_key
projection_version
reservation_event_id
accepted_changed_precondition_event_id | null
route_transition_event_id | null
admitted_at
```

For ordinary reservations, `admission_receipt_id` is derived from the committed `admission_reserved` event ID and canonical logical-child identity. For composite reservations, it is derived from the committed `provider_route_child_reserved` event ID and canonical child identity. The derivation is versioned, deterministic, and replay-stable:

```text
admission_receipt_id =
  digest(
    receipt_derivation_version,
    reservation_event_id,
    plan_id,
    phase,
    dispatch_family_id,
    logical_dispatch_id,
    physical_door_id,
    semantic_dispatch_fingerprint
  )
```

No receipt ID is accepted as input to the reservation event. Replay applies the same derivation and must reproduce the byte-identical ID.

Manifestless development remains explicitly non-production. Production intent, a production manifest, or a configured cloud seed cannot collapse into a development no-op.

Route-liveness, ledger, source, interpreter, runtime-proof, WBC-configuration, or authority-check failure rejects before client, process, WBC attempt, managed command, or RPC construction.

### 4.5 Stable semantic dispatch fingerprint and CAS key

The semantic fingerprint contains only durable execution preconditions:

```text
phase
normalized selected spec
model family
prompt_or_phase_input_identity
source revision
runtime vector
manifest identity
seed identity
dependency interpreter identity
timeout-policy identity
configured fallback-chain identity
authorized route identity
```

It excludes:

```text
logical_dispatch_id
dispatch_family_id
admission attempt number
OMP live-membership digest
native liveness-proof generation
timestamps
retry counters
PID/process incarnation
temporary provider-probe observations
```

Admission uniqueness is:

```text
projection key + semantic dispatch fingerprint
```

It is independent of logical-dispatch ID. Concurrent requests with different logical IDs but the same key and fingerprint contend for one reservation.

A route-liveness receipt change may affect current admission eligibility but cannot by itself bypass a prior terminal-fingerprint refusal.

Only canonical post-acceptance `worker_terminal_outcome` events create terminal fingerprint state. A proven `no_launch` outcome and `released_no_launch` reconciliation create no terminal fingerprint.

### 4.6 Canonical changed-precondition contract and producers

A terminal worker outcome records the semantic dispatch fingerprint.

Admission refuses a proposed redispatch of the same terminal fingerprint unless a later, single-use, allowlisted `changed_precondition` event proves a durable change.

Schema:

```text
schema_version
event_type = changed_precondition
event_id
producer_kind
producer_version
plan_id
phase
dispatch_family_id | null
logical_dispatch_id | null
reason
authoritative_subject
before_content_id
after_content_id
evidence_event_id
evidence_digest
source_revision | null
runtime_vector | null
interpreter_identity | null
route_identity | null
timeout_policy_identity | null
repair_commit_sha | null
recorded_at
actor
```

Allowlisted reasons and canonical producers:

```text
source_revision_changed
  -> source-revision producer reads the authoritative repository/source receipt

runtime_generation_changed
  -> runtime-generation producer reads the authoritative runtime registry/manifest

seed_or_interpreter_binding_changed
  -> binding producer reads the authoritative seed and interpreter attestations

timeout_policy_changed
  -> timeout-policy producer reads the canonical timeout-policy configuration

authorized_route_changed
  -> route-transition producer binds the jointly admitted composite route event

provider_recovery_verified
  -> provider-probe producer binds a successful canonical bounded probe result

verified_repair_committed
  -> repair producer binds repository commit identity and verified evidence digest
```

Rules:

- Callers request a reason-specific producer; they do not supply arbitrary before/after IDs.
- Each producer reads the authoritative before state, authoritative after state, and cited evidence.
- `before_content_id` and `after_content_id` are derived by the producer from normalized authoritative content and must differ.
- The producer stores its kind and version so replay can validate the derivation contract.
- The ledger transaction authority validates the reason, producer kind, evidence type, evidence digest, subject, and before/after binding before consumption.
- A caller-forged event, forged evidence reference, arbitrary pair of unequal IDs, mismatched subject, or unsupported producer version is rejected.
- `authorized_route_changed` references the committed composite route-transition event.
- `provider_recovery_verified` references a successful bounded provider probe.
- `verified_repair_committed` includes a repository commit SHA and evidence digest.
- Free-form notes, elapsed time, PID replacement, retry count, membership refresh, and sleep are insufficient.
- The event is later than the terminal outcome it supersedes.
- A receipt names the consumed change event.
- Consumption is atomic with reservation.
- One event cannot authorize two concurrent reservations.

A proven `released_no_launch` reconciliation is not a changed precondition because no final launch occurred and no terminal worker fingerprint was created. It releases only the unresolved reservation it names.

### 4.7 One ledger CAS and composite-event authority

NBF-01 adds one lock/read/compare/append authority to the existing incident ledger. It is the sole durable authority for:

- ordinary admission reservation;
- canonical terminal outcome recording and reservation closure;
- changed-precondition production validation and consumption;
- provider observation transitions;
- probe leases and results;
- composite route-transition-and-child reservation;
- reservation reconciliation;
- durable two-scan confirmation state;
- canonical dispositions.

No second journal or metadata store is introduced.

#### Ordinary reservation

Under the existing journal lock:

1. Load the current projection version.
2. Read the latest canonical terminal fingerprint, active reservation, and eligible changed-precondition event.
3. Compare projection key plus semantic fingerprint.
4. Reject an unchanged terminal fingerprint without an unused valid change.
5. Reject an active duplicate reservation even if logical IDs differ.
6. Validate authoritative evidence binding for any required change event.
7. Consume the valid change event when required.
8. Append one `admission_reserved` event.
9. Derive the receipt ID from the committed event ID and canonical child identity.
10. Return receipt data only after the append is durable.

#### Composite route transition and child reservation

Route flip and return use one event:

```text
schema_version
event_type = provider_route_child_reserved
event_id
plan_id
phase
projection_key
expected_projection_version
transition_kind = fallback_flip | return_to_primary
from_spec
to_spec
parent_logical_dispatch_id
parent_terminal_event_id
authorizing_event_id
configured_fallback_chain_identity
precondition_identity
child_dispatch_family_id
child_logical_dispatch_id
child_physical_door_id
child_semantic_dispatch_fingerprint
child_route_liveness_identity
consumed_changed_precondition_event_id | null
receipt_derivation_version
recorded_at
actor
```

`child_admission_receipt_id` is deliberately absent.

Under one lock and one append:

1. Validate the child through canonical admission up to its transactional step.
2. Verify projection version, parent terminality, target authorization, applicable route-liveness proof, fingerprint rules, authoritative changed-precondition binding, and absence of a duplicate child reservation.
3. Consume the authorizing event logically as part of the composite event.
4. Append exactly one `provider_route_child_reserved` NDJSON record.
5. Replay projects both the route transition and child reservation from that record.
6. Derive the child receipt ID from the committed event ID and canonical child identity.
7. Return one receipt whose `reservation_event_id` and `route_transition_event_id` identify the same composite event.

Fresh replay uses the versioned derivation in §4.4 and must produce the same child receipt ID byte-for-byte.

There are no separate `provider_route_flip` plus `admission_reserved` appends, no receipt-ID input, no prepare record, no commit marker, and no multi-record pseudo-transaction. A crash before the append yields neither state; a crash after the append yields both.

Fallback metadata is a derived cache updated after commit.

### 4.8 Canonical post-launch terminal outcome

Every non-scheduling result after final-launch acceptance is recorded through one canonical writer as:

```text
schema_version
event_type = worker_terminal_outcome
event_id
terminal_outcome_id
outcome_kind
plan_id
phase
projection_key
dispatch_family_id
logical_dispatch_id
admission_receipt_id
reservation_event_id
semantic_dispatch_fingerprint
selected_spec
physical_door_id
launch_state = accepted
worker_identity
process_or_rpc_identity
started_at
finished_at
success_payload_digest | null
terminal_failure_class | null
terminal_failure_evidence_id | null
provider_observation_id | null
provider_retryability_class | null
provider_exhausted_attempt_count | null
disposition_id | null
execution_context_identity
recorded_at
actor
```

`outcome_kind`:

```text
success
ordinary_terminal_failure
provider_exhausted
worker_disposition
```

Rules:

- The canonical writer verifies an accepted launch marker linked to the receipt.
- The event contains the semantic fingerprint and is the only ordinary post-launch source of terminal fingerprint state.
- Projection consumes the event before closing the reservation.
- Reservation closure and terminal projection occur atomically from this one append.
- `success` clears applicable provider-observation streaks through canonical projection rules.
- `ordinary_terminal_failure` enters existing failure consumers after the append.
- `provider_exhausted` enters the T8 policy after the append and is not also recorded as `ordinary_terminal_failure`.
- `worker_disposition` links the already-recorded canonical disposition and does not duplicate its signal evidence.
- Duplicate `terminal_outcome_id` is idempotent.
- Conflicting terminal outcomes for the same reservation are rejected.
- No accepted launch may close through `released_no_launch`.
- Failure to append leaves the reservation unresolved and produces `unresolved_launch`.

The following do not create `worker_terminal_outcome`:

- `SchedulingCondition`;
- `no_launch`;
- `unresolved_launch`;
- provider probe results;
- observed deaths without a linked admitted worker receipt;
- non-worker lifecycle signals.

### 4.9 Reservation reconciliation

A committed reservation remains unresolved until one of these is durably established:

- no final launch occurred;
- a final launch occurred and its terminal outcome was recovered;
- launch state remains ambiguous and must stay held.

Canonical schema:

```text
schema_version
event_type = reservation_reconciled
event_id
reconciliation_id
plan_id
phase
projection_key
logical_dispatch_id
admission_receipt_id
reservation_event_id
semantic_dispatch_fingerprint
resolution
evidence_kind
evidence_event_ids
launch_state_identity
worker_identity | null
victim_pid | null
victim_process_start_identity | null
running_receipt_identity | null
terminal_outcome_event_id | null
observed_at
recorded_at
actor
```

`resolution`:

```text
released_no_launch
terminal_outcome_recovered
permanent_hold_ambiguous
```

Legal transitions:

#### `released_no_launch`

Allowed only from an active unresolved reservation when positive evidence proves the final launch was never entered or accepted.

Acceptable proof requires:

- a persisted controlled-adapter state at `not_started`;
- the marker is linked to the exact admission receipt and reservation;
- the marker was persisted before any launch-capable operation became reachable;
- the controlled adapter proves that all spawn, RPC, WBC attempt, and managed-command acceptance operations were reachable only after its `entered` transition;
- no contradictory `entered`, `accepted`, running-receipt, process, RPC, WBC-attempt, managed-command, disposition, or terminal-outcome evidence exists.

An exception before entry may yield `released_no_launch` only when this positive sequencing evidence remains valid.

Effects:

- releases only the named reservation;
- creates no worker terminal outcome or terminal fingerprint;
- creates no provider observation;
- causes no phase-failure or breaker accounting;
- permits a fresh identical reservation subject to current admission checks;
- cannot be inferred from absence of a PID, elapsed time, missing cache, missing marker, or a restarted supervisor.

#### `terminal_outcome_recovered`

Allowed only when positive evidence proves a final launch was accepted and a canonical success, terminal failure, provider exhaustion, or worker disposition can be linked to the receipt.

Effects:

- closes the reservation through the canonical terminal-outcome projection;
- applies normal terminal-fingerprint and changed-precondition rules;
- never authorizes an immediate identical retry by itself;
- does not create a second terminal event when the canonical event already exists.

#### `permanent_hold_ambiguous`

Used when evidence cannot distinguish no launch from entered, accepted, or running launch.

Effects:

- retains a durable non-launchable hold;
- creates no fabricated worker outcome;
- permits no child reservation, fallback, recovery retry, or identical redispatch;
- may transition later only through a new reconciliation event containing positive evidence or explicit operator-supported durable evidence accepted by the frozen schema.

Idempotency:

```text
reconciliation_id =
  digest(reservation_event_id, resolution, normalized evidence identity)
```

Duplicate identical reconciliation is a no-op. Conflicting reconciliation for an already resolved reservation is rejected. Replay produces the same state after restart or cache loss.

Blind release based on missing processes, missing sequencing markers, stale timestamps, incomplete metadata, or supervisor restart is forbidden.

### 4.10 Controlled final-launch sequencing

Every final-launch closure executes through one `ControlledFinalLaunch` adapter. Direct access to the underlying spawn, RPC, WBC-attempt start, or managed-command acceptance primitive is forbidden from production door code.

Persisted launch states:

```text
not_started
entered
accepted
closed
```

State records contain:

```text
schema_version
event_type = final_launch_state
event_id
state_transition_id
plan_id
phase
dispatch_family_id
logical_dispatch_id
admission_receipt_id
reservation_event_id
physical_door_id
from_state | null
to_state
worker_identity | null
process_or_rpc_identity | null
evidence
recorded_at
actor
```

Transition contract:

1. After admission reservation and before invoking caller-controlled launch code, persist `not_started`.
2. Before any launch-capable operation can be called, atomically transition `not_started → entered`.
3. The adapter alone exposes the spawn/RPC/WBC/managed-command operation.
4. Immediately after the underlying operation accepts or creates the worker identity, persist `entered → accepted`.
5. After canonical terminal recording or truthful reconciliation, project `closed`.

Rules:

- The final-launch implementation cannot obtain the raw launch primitive without the adapter.
- A closure exception while a valid `not_started` marker remains and no launch-capable operation was exposed may normalize to `no_launch`.
- An exception after `entered` but before `accepted` may normalize to `no_launch` only when the adapter provides positive operation-specific evidence that no process, RPC, WBC attempt, or managed command was accepted.
- Missing, stale, skipped, contradictory, or out-of-order markers produce `unresolved_launch`.
- Any accepted worker, process, RPC, WBC attempt, or managed command produces `accepted` or an unresolved reservation; it can never produce `released_no_launch`.
- Reconciliation occurs before any return-level `no_launch` projection reaches `PhaseResult`.
- Restart reconstructs state solely from ledger events and running receipts.
- Direct launch construction outside the adapter is rejected by the authority-bypass checker.

### 4.11 Crash and replay semantics

Incident-ledger events are authoritative. Derived fallback or running metadata is written only after the relevant ledger append commits.

Crash behavior:

- Before lock: no new state exists.
- After read/before compare: no new state exists.
- After compare/before append: no new state exists.
- During the single composite-event write: recovery accepts only a complete valid NDJSON record; a torn record is rejected and never projected.
- After composite append/before receipt construction: replay derives the child receipt ID from the committed event.
- After receipt construction/before cache update: replay reconstructs the same receipt, transition, and child reservation.
- After cache update/before `not_started`: the child reservation is unresolved and must reconcile; absence of `not_started` is not proof of no launch.
- After `not_started`/before `entered`: positive adapter evidence may reconcile as no-launch.
- After `entered`/before launch acceptance: release requires positive operation-specific no-acceptance proof; otherwise the reservation is unresolved.
- After launch acceptance/before `accepted`: the reservation is unresolved and cannot be retried blindly.
- After `accepted`/before closure return: the reservation is unresolved until a terminal outcome is recorded.
- After closure return/before terminal-outcome append: the reservation remains unresolved.
- After terminal-outcome append/before derived-cache update: replay closes the reservation and projects the terminal fingerprint.
- Outcome-append failure never silently releases a reservation.
- A losing concurrent writer reloads and does not duplicate a reservation, composite transition, receipt, probe lease, provider observation, reconciliation, terminal outcome, confirmation record, or launch.

Required crash injection boundaries:

```text
before lock
after read/before compare
after compare/before append
during composite-event write
after composite append/before receipt derivation
after receipt derivation/before cache update
after cache update/before not_started persistence
after not_started/before entered
after entered/before underlying launch call
after underlying launch acceptance/before accepted persistence
after accepted/before closure return
after closure return/before terminal-outcome append
after terminal-outcome append/before derived-cache update
```

Fresh-ledger reopen tests must prove:

- a route transition and linked-child reservation are both visible or both absent;
- the derived child receipt ID is byte-identical after replay;
- no torn event is projected;
- no missing marker is treated as positive no-launch proof;
- a truthful no-launch release creates no terminal fingerprint or breaker input;
- identical redispatch after truthful no-launch requires and obtains a fresh reservation;
- unresolved launch state never triggers blind redispatch;
- terminal projection precedes reservation closure;
- reconciliation is idempotent;
- cache loss or mismatch cannot change authoritative state.

### 4.12 Scheduling-condition schema and transport

Add `ExitKind.scheduling_condition` and strict `SchedulingCondition` serialization through `PhaseResult`.

Payload:

```text
schema_version
condition_id
reason
plan_id
phase
spec
dispatch_family_id
logical_dispatch_id
admission_attempt
retry_after_s
observed_at
cause_event_id | null
disposition_id | null
from_spec | null
to_spec | null
evidence
```

Initial reasons:

```text
memory_cooldown
provider_observation_wait
provider_degraded
provider_probe_wait
provider_probe_failed
unresolved_launch
```

Rules:

- `condition_id` is independent of death identity.
- `cause_event_id` references real provider, memory, or reconciliation evidence when present.
- `disposition_id` is optional and references only a real recorded worker disposition.
- Provider holds, probe failures, and ambiguous reservations never invent a disposition.
- Scheduling conditions do not call `record_step_failure`.
- They increment no deterministic-phase, repeated-signature, or recovery-circuit counter.
- They cannot set the plan to `blocked`.
- `PhaseResult` preserves them losslessly through handlers and `auto.py`.
- Handler and `auto.py` routing recognizes scheduling before failure recording.
- `RecoveryPolicy.classify_with_circuit` performs an early scheduling bypass before recording or consulting a breaker.
- Genuine internal errors, malformed output, schema failures, auth failures, test failures, and excluded provider classes retain existing failure behavior.

`no_launch` is distinct from scheduling:

- it may cross `PhaseResult` as a typed return-level outcome;
- it is emitted only after successful `released_no_launch` reconciliation;
- it creates no worker terminal event, fingerprint, provider observation, phase failure, or breaker accounting;
- it does not itself authorize a linked child;
- a caller may request a new logical dispatch only through the normal admission path.

### 4.13 Typed dispatch outcome and exception boundary

Every final-launch closure returns or is normalized into `DispatchOutcome`:

```text
schema_version
kind
launch_state
plan_id
phase
dispatch_family_id
logical_dispatch_id
admission_receipt_id
semantic_dispatch_fingerprint
selected_spec
worker_identity | null
started_at | null
finished_at | null
success_payload | null
terminal_failure | null
provider_evidence | null
reconciliation_event_id | null
terminal_outcome_event_id | null
```

`kind`:

```text
success
no_launch
ordinary_terminal_failure
provider_exhausted
unresolved_launch
```

`launch_state`:

```text
not_started
accepted
ambiguous
```

Valid combinations:

```text
no_launch                -> not_started
success                  -> accepted
ordinary_terminal_failure -> accepted
provider_exhausted       -> accepted
unresolved_launch        -> ambiguous
```

`provider_exhausted` requires structured evidence:

```text
observation_id
retryability_class
exhausted_attempt_count
terminal_provider_evidence_id
precondition_identity
observed_at
```

The shared seam wraps the controlled launch adapter:

- A proven pre-entry exception with valid persisted `not_started` evidence becomes `no_launch`.
- It first appends `reservation_reconciled(resolution=released_no_launch)`.
- Only after reconciliation succeeds may the `no_launch` outcome reach `PhaseResult`.
- `no_launch` is not written as `worker_terminal_outcome`.
- Exception after entry but before acceptance becomes `no_launch` only with positive operation-specific no-acceptance evidence; otherwise it becomes `unresolved_launch`.
- Exception after acceptance becomes `unresolved_launch` until a canonical terminal outcome can be recovered.
- An exception with missing or contradictory sequencing evidence becomes `unresolved_launch`.
- `unresolved_launch` returns a scheduling condition and requires reservation reconciliation before any retry.
- Outcome-append failure also leaves the reservation unresolved.
- No exception path silently drops the receipt or starts another logical dispatch.

For accepted launches:

- `success`, `ordinary_terminal_failure`, and `provider_exhausted` are recorded through the single `worker_terminal_outcome` writer before reaching consumers.
- One exhausted logical dispatch produces one provider outcome and one provider observation regardless of internal retry count.
- Provider exhaustion is not double-recorded as an ordinary terminal failure.
- English stderr is never parsed for scheduling policy.
- Auth, quota, rate limit, unsupported model, context-window, malformed output, schema, and internal errors cannot produce `provider_exhausted`.
- Raw provider-degradation evidence never reaches `RecoveryPolicy`.

NBF-01 defines the schemas and writer primitives. NBF-02 implements generic intake, controlled sequencing, truthful reconciliation, and the exception boundary. NBF-06 alone supplies the T8 provider-policy response to the recorded `provider_exhausted` outcome.

### 4.14 One scheduling owner with one provider-policy extension

`dispatch_with_admission` is the only scheduling loop and the only component allowed to:

- call admission;
- wait through a scheduling interval;
- rerun admission;
- invoke a controlled final-launch closure;
- create the next linked logical dispatch;
- return a serialized scheduling condition when the bounded window expires.

For each logical dispatch it:

1. Invokes the canonical gate.
2. On receipt, verifies the committed reservation and derived receipt identity.
3. Persists controlled launch state `not_started`.
4. Invokes the final-launch closure at most once through the controlled adapter.
5. Normalizes closure exceptions.
6. Reconciles a proven no-launch before projecting `no_launch`.
7. Records accepted terminal outcomes through the canonical writer.
8. Returns success, no-launch, or ordinary terminal failure normally.
9. Handles T7 memory cooldown directly through its generic pre-launch scheduling loop.
10. Passes recorded `provider_exhausted` to the single T8 policy implementation added by NBF-06.
11. Executes the pure policy decision without transferring loop ownership.
12. Creates a linked child only after the parent canonical terminal event and durable authorization exist.
13. Never recursively re-enters a physical door.

The NBF-06 provider-policy component may:

- classify ledger projection state;
- append provider observation, hold, probe, and recovery evidence through the existing ledger authority;
- propose a configured fallback target through `_advance_configured_spec_fallback`;
- return a typed instruction to hold, probe, request child admission, or return a scheduling condition.

It may not:

- sleep;
- invoke admission directly outside the shared request path;
- invoke a final launch;
- recurse into a physical door;
- create a second scheduling loop;
- create a second projection, rotator, or journal.

For a route transition, the policy supplies the authorization and target. `dispatch_with_admission` constructs the linked child request, and canonical admission uses the single composite event to validate the target and reserve the child. The receipt is derived only after that event commits.

### 4.15 T7 memory cooldown

NBF-02 owns T7 completely.

- Active same-phase/spec cgroup-OOM cooldown returns `memory_cooldown`.
- The shared seam emits idempotent `retry_wait` evidence.
- It sleeps through an injected sleeper within the bounded dispatch-family deadline.
- It reruns the complete canonical gate.
- No final launch occurs before a receipt.
- Scheduling-window expiry returns the serialized condition.
- No WBC attempt starts.
- No phase failure, repeated-signature counter, deterministic-failure counter, recovery circuit, or `blocked` state changes.
- Existing cooldown-specific counter repair/reset logic is deleted.
- Genuine later internal errors retain ordinary breaker behavior.

### 4.16 T8 provider/precondition projection

NBF-01 supplies the schemas and replay mechanics. NBF-06 is the sole policy and behavior owner.

Projection key:

```text
plan_id
phase
primary_spec
configured_fallback_chain_identity
precondition_identity
```

Derived fields:

```text
projection_version
primary_spec
current_route
route_status
observation_streak
last_observation_id
last_observed_spec
retry_not_before
probe_status
probe_lease_id | null
authorized_target | null
last_transition_event_id | null
latest_changed_precondition_event_id | null
active_reservation_key | null
unresolved_reservation_state | null
```

Route status:

```text
primary
holding
probing
fallback
return_pending
```

Probe status:

```text
none
leased
passed
failed
```

Canonical events:

```text
worker_terminal_outcome
provider_observation
provider_hold
provider_probe_started
provider_probe_result
provider_success
changed_precondition
admission_reserved
provider_route_child_reserved
reservation_reconciled
```

Rules:

1. One accepted, recorded `provider_exhausted` terminal outcome creates one observation.
2. Internal retry chatter changes only evidence fields.
3. Matching requires phase, selected spec, projection key, and precondition identity.
4. Success or an allowlisted evidence-bound durable change resets the observation streak.
5. Two consecutive matching observations establish degradation.
6. Excluded error classes never enter the degradation projection.
7. Duplicate observation IDs do not increment twice.
8. All transitions compare the expected projection version.
9. One caller holds a probe lease.
10. Restart replay yields identical state.
11. Fallback metadata mirrors the projection and is never authoritative.
12. `_advance_configured_spec_fallback` remains the only configured fallback-selection door.
13. An unresolved parent reservation blocks observation-driven child creation.
14. A no-launch parent creates no provider observation and cannot authorize a provider-driven child.
15. The composite event projects route transition and child reservation together.
16. Provider exhaustion is never double-recorded as ordinary failure.
17. Changed-precondition CAS validates canonical producer/evidence binding before child reservation.

### 4.17 T8 first observation, degradation, fallback, scalar hold, and return

#### First matching provider observation

- One accepted and canonically recorded exhausted availability or idle-timeout outcome appends one `provider_observation`.
- It does not mark the provider degraded or rotate.
- The policy appends `provider_hold` and returns `provider_observation_wait`.
- After `retry_not_before`, one caller acquires a probe lease.
- A failed probe appends typed evidence and launches no worker.
- A passed probe appends a successful `provider_probe_result`.
- The canonical provider-recovery producer derives and appends an evidence-bound `provider_recovery_verified` changed-precondition event.
- The shared seam may then request one linked same-route child admission.
- Admission validates and consumes the event atomically with the child reservation.
- Time passage alone cannot authorize the child.
- A caller-forged changed-precondition event cannot authorize the child.
- A no-launch or unresolved parent cannot authorize the child.

#### Second matching observation

- If the authorized linked child launches, is accepted, and also records `provider_exhausted` with the same projection key and precondition identity, its observation establishes `provider_degraded`.
- The old logical dispatch is terminal and is never reused.
- No transition or child can be created from an unresolved parent.

#### Configured fallback

1. `_advance_configured_spec_fallback` proposes the next configured target.
2. The policy returns the proposed target and authorizing observation.
3. The shared seam constructs a linked child request.
4. Canonical admission jointly validates the target, including route-applicable positive liveness.
5. Rejection produces no transition, child reservation, receipt, WBC attempt, client, or RPC.
6. Acceptance appends one `provider_route_child_reserved` composite event.
7. The child receipt ID is derived after commit from that event and the canonical child identity.
8. The resulting child receipt names its parent and the composite event.
9. Derived fallback metadata updates after commit.
10. The shared seam performs the child’s one controlled final launch.

#### Scalar pin

- Never widen to historical last-known-good.
- Append a bounded hold and return a scheduling condition.
- Acquire one bounded probe lease after `retry_not_before`.
- Run one injected, no-tool provider probe.
- Failed probes append evidence and remain scheduling.
- Passed probes use the canonical recovery producer to create one evidence-bound `provider_recovery_verified` event.
- Exactly one linked same-route child reservation may consume that event.

#### Return to primary

1. Projection deadline and lease control primary probing.
2. A passing probe precedes child admission.
3. The canonical producer binds recovery evidence to the proposed primary route.
4. The policy proposes a return and supplies its authorization.
5. Canonical admission jointly validates the primary route.
6. One composite event records the return and reserves the linked child.
7. The child receipt is derived from the committed event.
8. Cache state changes only after commit.
9. The old fallback logical dispatch is not reused.

#### Execute and loop-execute

- Fallback advancement remains prohibited.
- `ExecuteFallbackUnsafe` semantics remain.
- Bounded hold/probe scheduling is allowed.
- No provider rotation creates a second execute attempt.

### 4.18 Receipt context transport

Every admitted final launch receives an immutable `WorkerExecutionContextRef`:

```text
ledger_root
plan_id
phase
dispatch_family_id
logical_dispatch_id
admission_receipt_id
semantic_dispatch_fingerprint
selected_spec
physical_door_id
```

Transport rules:

- Python APIs receive the typed object explicitly.
- Subprocess and managed-command boundaries receive a canonical serialized reference through the existing command/environment construction seam.
- Running receipts persist the reference and controlled final-launch state before supervision begins.
- Resident worker state retains it across same-session follow-up and termination ladders.
- Watchdog and restack code resolve it from the running receipt and ledger, verifying plan, receipt, PID, and process-start identity.
- Shell wrappers pass the resolved context to the disposition CLI.
- The standalone launcher accepts the reference through its invocation contract.
- Context cannot be reconstructed from model name, PID, current directory, or free-form text.
- Missing or inconsistent context prevents an in-band worker signal.
- Already-observed dead processes use an observed schema and never fabricate missing receipt data.

### 4.19 Canonical signal and disposition contracts

Add one canonical signal/disposition helper authority in `incident/disposition.py`.

Typed records:

```text
WorkerDisposition
ObservedProcessDeath
NonWorkerSignalDisposition
```

Common enums:

```text
DispositionMode:
  in_band
  observed

DispositionSubject:
  worker
  external_process
  non_worker_lifecycle

Signal:
  SIGINT
  SIGTERM
  SIGKILL

KillerKind:
  launcher_timeout
  resident_supervisor
  watchdog
  ensure_watchdog
  kernel_cgroup_oom
  external_unknown
  lifecycle_supervisor

CauseKind:
  timeout
  terminate
  escalation
  wedge
  restack
  cgroup_oom
  observed_dead_unknown
  lifecycle_shutdown
```

`WorkerDisposition` requires:

```text
schema_version
event_type = worker_disposition
disposition_id
mode
plan_id
phase
dispatch_family_id
logical_dispatch_id
admission_receipt_id
semantic_dispatch_fingerprint
selected_spec
killer_kind
killer_identity
cause_kind
signal
elapsed_s
worker_identity
victim_pid | null
victim_process_start_identity | null
process_group_identity | null
timeout_source | null
ladder_step | null
confirmation_event_id | null
observed_at
evidence
```

`ObservedProcessDeath` permits missing worker context only when the process is already dead and contains:

```text
subject = worker | external_process
observation_source
known_context_fields
unknown_context_fields
victim_identity_evidence
cause_kind
killer_kind
signal | null
positive_cgroup_delta | null
observed_at
evidence
```

Rules:

- It cannot authorize an in-band signal.
- `kernel_cgroup_oom` requires positive cgroup evidence.
- Unknown cause uses `external_unknown` and `observed_dead_unknown`.
- It never invents a fingerprint, worker identity, signal, or killer.

`NonWorkerSignalDisposition` contains:

```text
subject = non_worker_lifecycle
lifecycle_identity
killer_identity
cause_kind
signal
victim_pid_or_group
victim_process_start_identity
confirmation_event_id | null
observed_at
evidence
```

Signal rules:

- In-band worker and non-worker lifecycle appends complete before signaling.
- Append failure prevents the signal and returns non-success.
- TERM and KILL ladder steps have distinct deterministic IDs and records.
- Observed-death append completes before orphan cleanup or redispatch authorization.
- State summaries are derived projections, not a second authority.
- `kill -0` and equivalent checks are probes, not dispositions.
- Sustained-proof signals require a consumed durable two-scan confirmation event.
- Immediate explicit timeout or orderly owner-requested termination may use its direct causal event without a two-scan confirmation, but still requires record-before-signal.

### 4.20 Durable two-scan confirmation

The existing incident ledger owns durable sustained-proof confirmation. No wrapper-local file, shell variable, second journal, or new store is authoritative.

Canonical first-observation event:

```text
schema_version
event_type = supervision_confirmation_observed
event_id
confirmation_id
site_id
subject_class
plan_id | null
admission_receipt_id | null
victim_pid
victim_process_start_identity
relevant_progress_identity
supervisor_incarnation_identity
cause_kind
scan_interval_s
confirmation_policy_identity
first_observed_at
expires_at
evidence_digest
recorded_at
actor
```

Canonical consumption/reset event:

```text
schema_version
event_type =
  supervision_confirmation_consumed
  | supervision_confirmation_replaced
  | supervision_confirmation_expired
event_id
confirmation_id
prior_confirmation_event_id
site_id
replacement_reason | null
second_observed_at | null
second_evidence_digest | null
disposition_id | null
recorded_at
actor
```

Confirmation key:

```text
confirmation_id =
  digest(
    confirmation_schema_version,
    site_id,
    subject_class,
    victim_pid,
    victim_process_start_identity,
    relevant_progress_identity,
    supervisor_incarnation_identity,
    cause_kind
  )
```

TTL policy:

- Signal sites supply the existing configured supervision scan interval, not a free-form TTL.
- The canonical helper resolves a versioned `confirmation_policy_identity`.
- The default policy derives:

```text
confirmation_ttl_s =
  min(max(2 * scan_interval_s, 30.0), 300.0)

expires_at =
  first_observed_at + confirmation_ttl_s
```

- `scan_interval_s` must be finite and positive.
- The second observation must be separated from the first by at least one configured `scan_interval_s` and must occur no later than `expires_at`.
- A site requiring a different existing supervision cadence must register a versioned policy in the same helper; callers cannot choose arbitrary expiry values.

Atomic projection rules under the existing ledger lock:

1. Read the current confirmation projection for the site and subject.
2. On first qualifying observation, append `supervision_confirmation_observed`.
3. On a second matching observation within the policy window, atomically validate all key components and append `supervision_confirmation_consumed`.
4. The disposition append then references the consumed confirmation.
5. A consumed confirmation cannot authorize another signal.
6. PID reuse, process-start change, progress advance, cause change, or supervisor/watchdog/container incarnation change atomically replaces the prior confirmation and begins a new first scan.
7. Expiry invalidates the prior confirmation; the next observation is a new first scan.
8. A stale confirmation from an earlier supervisor incarnation cannot be consumed.
9. Restart replays the current confirmation from the ledger and preserves its original expiry.
10. Missing or torn confirmation events authorize no signal.
11. A first scan never emits a disposition or signal.
12. A second scan that fails any equality, separation, TTL, or evidence check performs no signal and records replacement or expiry as applicable.

Tests cover wrapper restart, ledger reopen, PID reuse, process-start reuse defense, progress advance, supervisor incarnation change, container incarnation change, expiry, duplicate second scans, concurrent second scans, and TERM→KILL ladders. TERM and KILL require separate confirmation/disposition identities when both depend on sustained proof.

### 4.21 Shell disposition CLI

Interface:

```bash
python -m arnold_pipelines.megaplan.incident.disposition record \
  --ledger-root "$LEDGER_ROOT" \
  --json-stdin
```

Contract:

- Reads exactly one UTF-8 JSON object.
- Validates one canonical disposition schema.
- Resolves the plan incident ledger beneath explicit `--ledger-root`.
- Validates any required consumed confirmation event.
- Appends synchronously through the canonical helper.
- Emits one JSON acknowledgement with record ID and ledger event ID.
- Writes diagnostics to stderr.
- Does not signal.

Exit statuses:

```text
0  append succeeded
2  malformed JSON or schema violation
3  ledger append/locking failure
4  invalid or unavailable ledger/context location
5  missing, expired, mismatched, or already-consumed confirmation
```

Wrapper order:

```text
resolve exact subject and process incarnation
resolve worker context or classify explicit non-worker subject
perform or resume durable two-scan confirmation where sustained proof is required
consume matching confirmation
invoke disposition CLI with confirmation reference
verify exit 0 and acknowledgement identity
invoke stub-able signal primitive
```

Nonzero status leaves a live victim unsignaled.

### 4.22 Generated repository-wide signal inventory

The canonical artifact is:

```text
docs/nbf-signal-inventory.json
```

It is a deterministic JSON document with:

```text
schema_version
generator_version
repository_revision
discovery_rules
entries
```

Each entry contains:

```text
site_id
source_file
function_or_branch
source_locator
signal_or_probe
subject_class
worker_kill
killer_kind
context_resolver
two_scan_required
two_scan_owner
confirmation_policy_identity | null
disposition_test_id
failure_order_test_id
exclusion_reason | null
```

The deterministic generator/checker is:

```text
scripts/generate_nbf_signal_inventory.py
```

Discovery rules:

- Python AST and narrowly defined textual fallbacks find real `os.kill`, `os.killpg`, process `send_signal`, `terminate`, `kill`, and equivalent project signal-wrapper calls.
- Shell discovery finds real `kill`, `pkill`, and project signal-wrapper invocations while excluding comments, documentation, and test fixture strings.
- Known probe forms such as `kill -0` are discovered and classified as probes.
- Stable `site_id` derives from source path plus enclosing function/branch and normalized signal expression, not line number alone.
- The generator merges reviewed classifications from the existing canonical artifact, fails on every newly discovered unclassified site, fails on vanished or duplicate site IDs until reviewed, and emits deterministic ordering.
- `--check` performs live discovery and fails if the checked-in artifact differs from the generated result.
- Tests exercise the same discovery engine; a hand-maintained incomplete fixture cannot pass.
- NBF-07 regenerates after rebase, reviews the complete artifact, runs `--check`, and includes the artifact digest in final evidence.

The initial inventory includes at least:

- `skills/subagent-launcher/launch_omp_agent.py`
- `skills/subagent-launcher/fan.py`
- `skills/subagent-launcher/fan_process.py`
- `resident/subagent.py`
- `resident/agent_loop.py`
- `cloud/operator_control.py`
- `cloud/wrappers/arnold-watchdog`
- `cloud/wrappers/arnold-heartbeat`
- `cloud/systemd/ensure-megaplan-watchdog`

Classification:

- Worker-killing real signal: route through `WorkerDisposition`.
- Already-dead observation: route through `ObservedProcessDeath`.
- Non-worker lifecycle signal: route through `NonWorkerSignalDisposition`.
- Probe: mechanically prove it cannot signal.
- Intentional exclusion: narrow, documented, mechanically tested, and accepted by the Sol Oracle.

No worker-killing site may be excluded merely because it lies outside the initially named files.

Sustained-proof rules apply to watchdog wedge, hung child, repair reaping, ensure-restack, and analogous supervision kills:

- two separated durable observations;
- same process-start identity;
- same relevant progress identity;
- same watchdog/container incarnation;
- positive lack-of-progress proof;
- PID replacement, progress advance, incarnation change, or TTL expiry resets confirmation.

Immediate explicit timeout or orderly owner-requested termination may use its direct causal event instead of two scans, but still requires record-before-signal.

### 4.23 Targeted admission-authority bypass checker

Add:

```text
scripts/check_worker_admission_authority.py
```

The checker uses Python AST plus narrow shell/text rules where AST is unavailable. It scans the three physical doors and all discovered chain-origin callers.

Required coverage includes:

```text
refresh_runtime_launch_seed_for_worker_dispatch
require_configured_runtime_launch
worker_launch_preflight
standalone source/runtime refusal helpers
standalone memory/headroom admission helpers
direct subprocess/process/client/RPC/WBC/managed-command construction
_run_step_with_worker_legacy production delegation
run_step_with_worker production no-WBC bypass
direct calls to final-launch primitives outside ControlledFinalLaunch
direct production worker launch construction in chain origins
admission calls in both _impl.py and run_omp_step for one nested OMP family
```

Contract:

- Maintain an explicit allowlist of the canonical gate, retained validation primitives called only from that gate, the three physical final-launch owners, and the controlled launch adapter.
- Resolve imported aliases and qualified attribute calls where the AST permits.
- Fail on every unclassified forbidden call or construction.
- Fail when an allowlisted site disappears or moves without reviewed regeneration.
- Emit deterministic JSON diagnostics containing file, enclosing symbol, call/construction category, and reason.
- Provide `--check` for CI/local validation.
- Use fixtures proving it detects:
  - raw refresh/require calls;
  - chain-local `worker_launch_preflight`;
  - direct chain spawn;
  - production no-WBC legacy delegation;
  - WBC start before admission;
  - nested OMP double admission;
  - launch primitive access outside the controlled adapter.
- Run in NBF-03 before its Oracle gate and in NBF-07 after rebase.
- Keep the focused raw-symbol grep as secondary human-readable evidence.

The checker proves authority deletion and launch ownership; it does not become a runtime admission authority.

## 5. Explicitly prohibited patterns

The implementation must not:

- retain chain-local or WBC-local admission authority;
- allow production `run_step_with_worker(..., wbc_dispatch=None)` to bypass `dispatch_with_admission`;
- start a WBC worker attempt before admission;
- record scheduling or no-launch as a WBC failure or completion;
- gate both `_impl.py` and `run_omp_step` for nested OMP;
- reuse a logical-dispatch ID after a final launch;
- perform two final launches under one logical ID;
- expose a raw production launch primitive outside `ControlledFinalLaunch`;
- add a family-wide launch lease;
- allow a linked child before its parent has a canonical terminal outcome;
- treat no-launch as a provider-terminal parent;
- place scheduling loops in the gate, `auto.py`, `RecoveryPolicy`, handlers, fallback code, or the T8 policy component;
- implement T8 policy in NBF-02 or NBF-03;
- begin NBF-06 before NBF-01 through NBF-05 have passed their synchronization gates;
- return raw provider-degradation evidence to generic breaker handling;
- parse English stderr for provider policy;
- treat internal retries as multiple provider observations;
- double-record provider exhaustion as ordinary terminal failure;
- close an accepted reservation without the canonical terminal-outcome event;
- create a worker terminal event, terminal fingerprint, provider observation, or breaker input for `no_launch`;
- include route-liveness digest or generation in semantic retry identity;
- use different logical IDs to evade reservation uniqueness;
- write route transition and child reservation as separate journal events;
- place a child receipt ID inside the composite-event input;
- add a prepare/commit pseudo-transaction or second journal;
- treat fallback metadata as authoritative;
- add a second provider rotator;
- force native models into OMP membership;
- add speculative network health checks to admission;
- release an unresolved reservation merely because a process or sequencing marker cannot be found;
- infer no-launch solely from absence of an `entered` marker;
- normalize a post-spawn or ambiguous exception as a no-launch failure;
- let consumer projection precede no-launch reconciliation or terminal-outcome recording;
- accept caller-supplied arbitrary changed-precondition content IDs;
- consume a changed-precondition event without validating authoritative evidence binding;
- invent a disposition, fingerprint, worker identity, signal, or killer for missing context;
- signal an in-band worker without resolved admission context;
- claim cgroup OOM without positive evidence;
- signal before the disposition append succeeds;
- keep authoritative two-scan state only in process memory, shell variables, or wrapper-local files;
- consume a two-scan confirmation after expiry, PID reuse, process-start change, progress advance, or supervisor/container incarnation change;
- treat a one-scan verdict, PID presence, completed marker, or stale timestamp as sustained kill proof;
- permit a free-form note, time passage, sleep, retry count, or liveness-receipt refresh to bypass fingerprint refusal;
- let a membership/runtime proof failure become accepted empty membership;
- accept a hand-maintained signal inventory without live-discovery comparison;
- rely only on grep to prove admission-authority closure;
- apply a box-only hotfix absent from the candidate branch.

## 6. Execution batches and tasks

All implementation, focused testing, critique, and independent review work uses GPT-5.6 Luna. Planning, revision, Oracle judgments, and any justified `[XHARD]` task use GPT-5.6 Sol with high reasoning. No task below is `[XHARD]`, and no model switch is authorized without user approval.

### Batch 1 — Contracts, replay projection, and ledger CAS

#### NBF-01 — Freeze schemas and add the single ledger primitive

**Classification:** Normal / GPT-5.6 Luna.

**Ownership boundary**

NBF-01 owns only:

- typed schemas and serialization;
- deterministic incident replay projections;
- ordinary reservation CAS;
- canonical terminal-outcome writer and projection;
- canonical changed-precondition producers and evidence-binding validation;
- changed-precondition consumption;
- probe-lease primitives;
- the single composite route-transition-and-child-reservation event;
- deterministic post-commit receipt derivation;
- reservation reconciliation primitives;
- durable two-scan confirmation schemas and ledger projection;
- canonical disposition helper/CLI contracts.

It does not own canonical admission calls, scheduling loops, T7 behavior, T8 policy, physical doors, launch adapters, signal-site wiring, or provider fallback decisions.

**Files and symbols**

- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- New `arnold_pipelines/megaplan/incident/disposition.py`
- Existing fallback metadata schema
- New tests:
  - `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
  - `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
  - `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
  - `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
  - `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`
  - `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
  - `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`
  - `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`

**Work**

- Add strict `SchedulingCondition` and `DispatchOutcome` schemas, including `no_launch`.
- Add worker, observed-death, and non-worker disposition schemas.
- Add changed-precondition and semantic-fingerprint schemas.
- Add canonical reason-specific changed-precondition producers.
- Validate authoritative evidence-to-identity binding.
- Add ordinary `admission_reserved`.
- Add `worker_terminal_outcome` and atomic reservation closure/projection.
- Add the single composite `provider_route_child_reserved` event without a receipt-ID field.
- Add versioned deterministic receipt derivation after commit and during replay.
- Add `reservation_reconciled` with the three frozen resolutions.
- Add provider projection event schemas and deterministic replay without implementing provider policy.
- Add durable two-scan confirmation events, projection, TTL-policy validation, replacement, expiry, and consumption.
- Add lock/read/compare/single-append CAS operations.
- Add one-use event consumption, probe leases, cache reconciliation, deterministic IDs, and torn-record handling.
- Add the shell disposition CLI.
- Do not implement request-specific admission, scheduling waits, launch control, provider policy, caller wiring, or signals.

**Acceptance**

- Scheduling, no-launch, and accepted outcomes round-trip strictly through serialization.
- `no_launch` cannot serialize with `launch_state=accepted`.
- `no_launch` cannot produce a terminal event, terminal fingerprint, provider observation, or breaker input.
- Incomplete dispositions are rejected.
- Observed unknown death cannot claim OOM or fabricate worker identity.
- Non-worker lifecycle records validate without a worker fingerprint.
- TERM and KILL ladder IDs differ.
- Free-form changed-precondition reasons fail.
- Caller-forged unequal content IDs fail.
- Mismatched evidence, subject, producer kind, or producer version fails.
- Route-liveness digest is absent from semantic fingerprint.
- Same fingerprint with different logical IDs maps to the same reservation key.
- A validated change event is single-use.
- Two-process contention yields one ordinary reservation winner.
- Composite transition and child reservation project together from one record.
- Composite input contains no child receipt ID.
- Receipt derivation is byte-identical after fresh replay.
- A crash or torn write cannot expose a partial transition or receipt.
- Accepted terminal outcomes project fingerprint state before reservation closure.
- Provider exhaustion is not double-recorded as ordinary failure.
- `reservation_reconciled` rejects blind no-launch claims.
- Positive no-launch releases only the named reservation and creates no terminal fingerprint.
- Ambiguous launch stays held.
- Recovered terminal outcome applies normal fingerprint rules.
- Conflicting reconciliation is rejected; identical replay is idempotent.
- Two-scan confirmation survives restart.
- PID reuse, progress advance, incarnation change, expiry, or conflicting scans prevent consumption.
- Concurrent second scans yield one consumer.
- Lock, append, schema, and projection-version failures fail closed.
- Restart replay and cache repair reproduce exact state.
- CLI acknowledgements and exit codes match the frozen contract.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

**Synchronization point**

The Sol Oracle freezes schemas, canonical terminal-outcome behavior, canonical changed-precondition producers, fingerprint components, receipt derivation, single-record composite behavior, reconciliation transitions, launch-state proof requirements, durable two-scan confirmation, CLI behavior, crash semantics, and replay before caller work begins.

### Batch 2 — Canonical admission, generic scheduler, T7, and transport

#### NBF-02 — Expand admission and implement generic `dispatch_with_admission`

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01.

**Ownership boundary**

NBF-02 owns:

- the canonical admission request and receipt path;
- request-specific use of NBF-01 reservation primitives;
- route-applicable positive liveness;
- generic `dispatch_with_admission`;
- controlled final-launch sequencing;
- T7 memory cooldown;
- typed `DispatchOutcome` intake;
- truthful `no_launch` handling;
- final-launch exception normalization;
- canonical terminal-outcome writer integration;
- unresolved-reservation reconciliation integration;
- lossless `PhaseResult`/handler/`auto.py` scheduling and no-launch transport;
- early breaker bypass;
- generic linked-child request construction after a supplied durable authorization.

NBF-02 does not own provider observation thresholds, probe policy, degradation, fallback selection, scalar policy, return-to-primary policy, signal-site wiring, two-scan policy calls, or T8 race/replay decisions.

**Files and symbols**

- `cloud/runtime_attestation.py`
- Shared dispatch module containing `dispatch_with_admission`
- Controlled final-launch adapter module
- `chain/source_admission.py`
- `chain/__init__.py`
- `workers/omp.py`
- Native backend selection/runtime seams
- `arnold/pipeline/model_seam.py`
- `skills/subagent-launcher/launch_omp_agent.py`
- `runtime/memory_headroom.py`
- `handlers/shared.py`
- `orchestration/phase_result.py`
- `orchestration/phase_result_classify.py`
- `orchestration/recovery_policy.py`
- `auto.py`
- `incident/disposition.py`
- `observability/work_ledger.py`
- `tests/cloud/test_runtime_attestation.py`
- New:
  - `tests/cloud/test_worker_dispatch_admission.py`
  - `tests/cloud/test_dispatch_with_admission.py`
  - `tests/cloud/test_chain_admission.py`
  - `tests/cloud/test_worker_dispatch_context.py`
  - `tests/cloud/test_dispatch_reconciliation.py`
  - `tests/cloud/test_controlled_final_launch.py`

**Work**

1. Inventory chain, raw runtime, memory, native liveness, OMP membership, legacy no-WBC, and WBC callers.
2. Reduce retained helpers to non-authoritative primitives.
3. Add typed request, receipt, refusal, execution-context reference, and request-specific reservation.
4. Derive receipt IDs only after committed reservation events.
5. Normalize model translation ownership.
6. Add injectable route-liveness resolution:
   - OMP `omp models --json`;
   - native positive backend/runtime/model proof.
7. Prove static acceptance and joint rejection of expired `openrouter/stealth/ox-alpha`.
8. Prove missing native positive proof rejects before client construction.
9. Move source/runtime, timeout, memory, fingerprint, and reservation checks into the gate.
10. Use the NBF-01 CAS primitive for ordinary and authorized child reservations.
11. Implement the generic scheduling loop without provider policy.
12. Implement T7 cooldown wait, evidence, bounded expiry, and complete re-admission.
13. Implement the controlled launch adapter and persisted `not_started`, `entered`, and `accepted` transitions.
14. Make raw production launch primitives reachable only through the adapter.
15. Add typed exception normalization:
    - proven no-entry/no-acceptance becomes `no_launch`;
    - accepted or ambiguous launch becomes unresolved until terminal evidence exists.
16. Reconcile `released_no_launch` before projecting `no_launch`.
17. Integrate the canonical terminal-outcome writer for accepted results.
18. Integrate all three reconciliation outcomes.
19. Preserve scheduling and no-launch through handler and `auto.py` without failure accounting.
20. Add early scheduling/no-launch bypass before failure or breaker accounting.
21. Delete cooldown-specific counter repair/reset logic.
22. Define execution-context propagation at Python, subprocess, managed-command, and running-receipt boundaries.
23. Define the single typed T8 policy-extension interface consumed later by NBF-06; it may return decisions but cannot own waiting or launching.

**Acceptance**

- One receipt proves every frozen admission invariant.
- Receipt ID is derived from the committed reservation event.
- Chain has no independent authorization caller.
- Production cannot pass without source/runtime/seed/interpreter proof.
- OMP admission requires exact current membership.
- Native admission requires positive route-applicable backend/runtime/model proof.
- Missing or unreadable applicable proof fails typedly.
- Invalid timeout values fail typedly.
- Static `ox-alpha` acceptance remains while joint admission rejects it before client construction.
- Same semantic fingerprint with different logical IDs yields one reservation.
- Liveness-digest-only change does not authorize redispatch.
- One canonically produced valid changed event authorizes one reservation and is named by the receipt.
- Caller-forged changed events fail.
- Cooldown causes multiple admission attempts and zero launches before expiry.
- Scheduling expiry reaches `PhaseResult` without failure accounting, WBC attempt, or `blocked`.
- Final-launch closure is invoked at most once per logical dispatch.
- The adapter persists `not_started` before any launch-capable operation.
- Raise with positive `not_started` proof becomes `no_launch` only after reconciliation.
- `no_launch` creates no terminal fingerprint or breaker input.
- Identical redispatch after truthful no-launch obtains a fresh reservation.
- Missing or contradictory sequencing evidence becomes unresolved.
- Raise after acceptance or ambiguous raise becomes unresolved.
- Accepted success/failure/provider exhaustion records one canonical terminal event before consumer projection.
- Provider exhaustion is not double-recorded.
- Outcome-append failure remains unresolved.
- Restart never blindly relaunches an unresolved reservation.
- Generic child construction requires a canonical terminal parent and durable authorization.
- A no-launch parent is insufficient for provider-driven child creation.
- No provider observation, probe, flip, scalar hold, or return policy is implemented here.
- Execution context and launch state are persisted before supervision begins.

**Focused validation**

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_dispatch_reconciliation.py \
  tests/cloud/test_controlled_final_launch.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py \
  tests/arnold_pipelines/megaplan/test_plan_circuit.py \
  tests/workers/test_omp_adapter.py
```

### Batch 3 — Physical doors, WBC ordering, and authority proof

#### NBF-03 — Wire the three doors and prove generic launch cardinality

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-02.

**Ownership boundary**

NBF-03 owns only:

- the three physical-door bindings;
- nested/direct OMP ownership;
- chain delegation;
- production no-WBC closure;
- WBC intent/admission/start ordering;
- controlled-adapter placement;
- admission-attempt and final-launch traces;
- generic scheduling/no-launch traces;
- receipt-context propagation through the doors;
- the targeted authority-bypass checker.

It does not own or assert first/second provider observations, provider probes, degradation, fallback selection, scalar routing, return-to-primary, or provider-transition policy.

**Files and symbols**

- `workers/_impl.py::run_step_with_worker`
- `_run_step_with_worker_legacy`
- WBC dispatcher construction and callbacks
- `workers/omp.py::run_omp_step`
- `cloud/babysitter/launch.py`
- Chain delegation path
- New `scripts/check_worker_admission_authority.py`
- `docs/nbf-hourly-loop-goal.md`
- `cloud/fixer_model_policy.py`
- New `tests/cloud/test_worker_dispatch_spy.py`
- New `tests/cloud/test_worker_admission_authority.py`
- `tests/cloud/test_chain_admission.py`
- `tests/cloud/test_babysitter_routing.py`
- `tests/cloud/test_babysitter_goal.py`
- `tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py`

**Work**

- Delete `_impl.py` raw refresh/require/source-preflight blocks.
- Native `_impl.py` binds the shared seam once.
- Close the production `wbc_dispatch=None` legacy bypass.
- Construct the canonical WBC adapter internally where appropriate, or typedly reject missing WBC configuration before any launch.
- Ensure any retained legacy function is development-only or runs solely inside the admitted controlled final-launch closure.
- Nested OMP delegates without outer admission.
- `run_omp_step` binds the shared seam for nested and direct OMP.
- Babysitter binds it before running receipt or managed command.
- Emit optional pre-admission WBC intent only.
- Move admission before `wbc_dispatch.run`.
- Start WBC attempt state only inside the admitted controlled final-launch closure.
- Ensure generic scheduling and no-launch consume no WBC start/failure/complete.
- Keep normal and agent-dispatcher paths identical in ownership.
- Propagate receipt context and launch-state markers into every final-launch boundary.
- Implement the targeted authority-bypass checker and negative fixtures.
- Document that checked-in pins are advisory and canonical admission is authoritative.
- Do not mutate `/workspace/.cloud-hot-env`.

**Structural scenarios**

1. Native non-OMP success.
2. Nested OMP success.
3. Direct OMP success.
4. Babysitter success.
5. Chain-originated success.
6. Admission rejection for each door.
7. Production `run_step_with_worker(..., wbc_dispatch=None)`:
   - enters canonical admission with an internally constructed adapter; or
   - rejects typedly before legacy launch;
   - never launches through an unadmitted fallback.
8. Memory cooldown with multiple admission attempts and one eventual final launch.
9. Bounded scheduling expiry with no final launch.
10. Proven pre-entry exception:
    - `not_started` persisted;
    - no launch primitive called;
    - reconciliation precedes `no_launch`;
    - no WBC failure/completion or terminal fingerprint.
11. Ambiguous launch sequencing:
    - unresolved condition;
    - no reservation release or retry.
12. Generic authorized child dispatch:
    - parent has a canonical terminal outcome;
    - child has a new logical ID;
    - parent and authorization are linked;
    - each logical ID launches at most once.
13. Rejected, no-launch, or unresolved parent produces no provider-driven child reservation or launch.
14. WBC ordered trace:
    - optional intent;
    - admission reservation;
    - derived receipt;
    - persisted `not_started`;
    - WBC attempt start/final-launch entry;
    - final-launch acceptance;
    - canonical typed outcome.
15. Scheduling/no-launch WBC trace:
    - intent;
    - scheduling condition or reconciled no-launch;
    - no WBC failure/complete;
    - no premature final launch.
16. No `MEGAPLAN_MOCK_WORKERS=1`; only final spawn/RPC/WBC/managed-command seams are replaced.
17. Static-checker fixtures for every forbidden authority/bypass category.

**Acceptance**

- One physical owner per dispatch family.
- Every production `run_step_with_worker` call enters the shared seam.
- Production no-WBC input cannot reach an unadmitted legacy launch.
- One final launch maximum per logical dispatch.
- Generic authorized child has a new logical ID linked to a canonical terminal parent.
- A no-launch or unresolved parent cannot create a provider-driven child.
- No recursive physical-door entry occurs.
- Nested OMP has no outer owner.
- Ordered traces prove reservation and controlled launch state before WBC attempt and final launch.
- Door removal, duplicate outer gate, chain bypass, no-WBC bypass, pre-admission WBC start, raw launch primitive access, or second final launch under one logical ID fails tests.
- Independent different-fingerprint dispatches are not artificially blocked by a new family lease.
- The authority checker reports no forbidden calls or launch constructions.
- The three door files contain no raw refresh/require calls.
- No T8 provider-policy behavior is implemented or duplicated in this batch.

**Focused validation**

```bash
pytest -q \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_worker_admission_authority.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

```bash
python scripts/check_worker_admission_authority.py --check
```

```bash
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

**Synchronization point**

The Sol Oracle reviews caller inventory, route-applicable liveness traces, no-WBC closure, controlled launch traces, WBC ordering, physical-owner traces, generic linked-child identity, nested OMP ownership, chain bypass tests, authority-checker output, and the secondary raw-preflight scan. Provider-policy judgments are deferred to NBF-06.

### Batch 4 — Python worker deaths and context closure

#### NBF-04 — Route all repository Python signal paths through the helper

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01, NBF-02, and NBF-03.

**Files and symbols**

- `skills/subagent-launcher/launch_omp_agent.py`
- `skills/subagent-launcher/fan.py`
- `skills/subagent-launcher/fan_process.py`
- `resident/subagent.py`
- `resident/agent_loop.py`
- `cloud/operator_control.py`
- `auto.py` orphan recovery
- `incident/disposition.py`
- Focused launcher, fan, resident, operator, confirmation, and incarnation tests
- New `tests/arnold_pipelines/megaplan/test_python_signal_inventory.py`

**Work**

- Replace launcher timeout handling with explicit process control.
- Propagate and resolve `WorkerExecutionContextRef`.
- Record timeout disposition at the kill site before killing.
- Record every resident SIGINT, SIGTERM, and SIGKILL before signaling.
- Preserve TERM→wait→KILL behavior and distinct ladder records.
- Inventory and classify fan, agent-loop, operator-control, and all other discovered Python signal sites.
- Route worker kills through `WorkerDisposition`.
- Route non-worker lifecycle signals through `NonWorkerSignalDisposition`.
- Use durable confirmation for every Python sustained-proof signal site.
- Mechanically test probes and narrow exclusions.
- Convert positive OOM orphan evidence into `ObservedProcessDeath`.
- Record unknown dead-process observations without fabricated context.
- Prevent in-band signal when required context cannot resolve.
- Feed Python discovery and reviewed classifications into the canonical inventory pipeline completed in NBF-05.

**Acceptance**

- Every discovered Python real signal has a reviewed classification.
- Every worker signal has a resolvable receipt and fingerprint.
- Missing in-band context leaves the process alive.
- Append failure leaves the process alive.
- Timeout return code and metadata remain compatible.
- TERM-only and TERM→KILL paths are covered.
- Follow-up SIGINT is covered.
- Sustained-proof Python signals require one consumed durable confirmation.
- Confirmation survives restart and rejects PID reuse, progress advance, expiry, and incarnation change.
- OOM requires positive evidence.
- Unknown death remains explicitly unknown.
- Non-worker lifecycle signals never impersonate workers.
- State summaries derive from canonical events.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py \
  tests/arnold_pipelines/megaplan/test_python_signal_inventory.py \
  tests/resident/test_managed_provider_agent_runner.py
```

### Batch 5 — Shell supervision and generated signal closure

#### NBF-05 — Instrument shell signals and generate the complete inventory

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-04.

**Files and symbols**

- `cloud/wrappers/arnold-watchdog`
- `cloud/wrappers/arnold-heartbeat`
- `cloud/systemd/ensure-megaplan-watchdog`
- Any additional shell or Python signal site found by live discovery
- `incident/disposition.py` CLI
- New `scripts/generate_nbf_signal_inventory.py`
- New canonical `docs/nbf-signal-inventory.json`
- `tests/cloud/test_watchdog_wrappers.py`
- `tests/cloud/test_watchdog_dispositions.py`
- New `tests/cloud/test_repository_signal_inventory.py`
- Confirmation restart/incarnation fixtures

**Work**

For worker supervision signals:

1. Resolve exact PID/process group and process-start identity.
2. Resolve the admission receipt context.
3. Resolve watchdog/container incarnation identity.
4. Append or resume the durable first-scan confirmation.
5. Require a separated second observation with identical confirmation key.
6. Consume the confirmation atomically.
7. Invoke the disposition CLI with the consumed confirmation reference.
8. Verify exit 0 and matching acknowledgement.
9. Invoke the stub-able signal primitive.

For non-worker signals:

- Emit a typed non-worker lifecycle record before signaling.
- Use durable confirmation where the decision is a sustained supervision judgment.
- Preserve exact targeting.
- Do not fabricate worker fields.

For probes and exclusions:

- Discover repository-wide.
- Mechanically prove probes cannot signal.
- Give exclusions a narrow reason and direct regression test.

For the inventory:

- Implement deterministic Python and shell discovery.
- Generate `docs/nbf-signal-inventory.json`.
- Fail generation on new unclassified sites, duplicate IDs, stale vanished rows, or classification/schema gaps.
- Add `--check` and use the same discovery engine in tests.
- Record generator version and deterministic artifact digest.
- Ensure direct source changes to signal sites make freshness tests fail until the inventory is regenerated and reviewed.

Additional rules:

- PID, process-start, progress, supervisor incarnation, or container incarnation changes replace confirmation and begin a new first scan.
- TTL expiry begins a new first scan.
- TERM→KILL produces distinct confirmations when sustained proof applies and always produces two disposition records.
- The ensure script resolves the active installed source/runtime.
- CLI, confirmation, or context failure leaves a live victim unsignaled.

**Acceptance**

- Every live-discovered repository real signal or probe has exactly one artifact row.
- Every worker kill is helper-routed.
- A stale or incomplete checked-in inventory fails `--check`.
- First scan never signals where sustained proof is required.
- Confirmation persists across wrapper restart.
- PID reuse, progress advance, expiry, or incarnation change resets confirmation.
- Concurrent second scans authorize at most one signal.
- CLI and consumed confirmation precede signal.
- CLI or confirmation failure causes zero signal calls.
- Missing worker context causes zero worker signal calls.
- TERM→KILL ordering is complete.
- Probes are not mistaken for signals.
- No worker is reaped from a single stale scan, `completed.json`, or PID presence.
- Shell syntax passes.
- No unreviewed worker-kill exclusion remains.

**Focused validation**

```bash
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-heartbeat
bash -n arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog
python scripts/generate_nbf_signal_inventory.py --check
pytest -q \
  tests/cloud/test_watchdog_dispositions.py \
  tests/cloud/test_watchdog_wrappers.py \
  tests/cloud/test_repository_signal_inventory.py \
  tests/arnold_pipelines/megaplan/test_python_signal_inventory.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
```

**Synchronization point**

The Sol Oracle receives the generated artifact, artifact digest, discovery rules, freshness result, durable confirmation replay/reset evidence, and ordering evidence. An unclassified live-discovered signal, stale artifact, fabricated worker identity, unresolved worker context followed by a signal, expired/mismatched confirmation followed by a signal, or signal reachable after append failure blocks the batch.

### Batch 6 — Sole T8 provider-resilience implementation

#### NBF-06 — Implement T8 through the shared seam and existing fallback door

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01, NBF-02, NBF-03, NBF-04, and NBF-05.

**Dependency barrier**

NBF-06 starts only after the synchronization gates for NBF-01 through NBF-05 pass. In particular, the canonical terminal-outcome writer, evidence-bound changed-precondition producers, controlled launch adapter, receipt-context transport, disposition helper/CLI, durable confirmation contract, authority checker, and generated signal inventory must be frozen and green before T8 edits begin.

**Ownership boundary**

NBF-06 is the sole implementation and test owner for:

- structured provider-exhaustion production after launch acceptance;
- provider observations;
- hold and probe policy;
- degradation threshold;
- same-route recovery authorization;
- configured fallback selection;
- scalar-pin behavior;
- linked fallback and return decisions;
- composite transition use;
- provider replay, crash, and race behavior;
- execute/loop-execute fallback prohibition.

It uses the NBF-01 projection/CAS primitives and NBF-02 shared scheduling seam. It creates no scheduler, admission authority, terminal writer, changed-precondition bypass, rotator, projection, or journal.

**Files and symbols**

- `fallback_chains.py`
- `workers/_impl.py`
- `workers/omp.py`
- T8 policy module consumed by `dispatch_with_admission`
- `handlers/shared.py`
- `orchestration/phase_result.py`
- `orchestration/phase_result_classify.py`
- `orchestration/recovery_policy.py`
- `auto.py`
- `incident/ledger.py`
- `incident/disposition.py`
- New `tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py`
- Existing fallback, phase-result, memory, auto, execution-policy, reconciliation, terminal-outcome, changed-precondition, and ledger suites

**Substep A — Structured `DispatchOutcome` producers**

- Export one typed exhausted-dispatch outcome from OMP and non-OMP.
- Require accepted launch state.
- Include logical ID, phase/spec, retryability class, internal attempt count as evidence, terminal evidence ID, and precondition identity.
- Record it once through `worker_terminal_outcome(outcome_kind=provider_exhausted)`.
- Prove internal retries count once.
- Prove excluded error classes return ordinary failures.
- Prove provider exhaustion is not double-recorded.
- Prove raw stderr never drives provider policy.

**Substep B — First observation and recovery**

- Append exactly one observation for one canonical provider-exhausted terminal outcome.
- Enter bounded hold without degrading or rotating.
- Acquire one probe lease after `retry_not_before`.
- Append typed passed/failed probe evidence.
- Use the canonical provider-recovery producer to derive content identities from the probe result.
- Require a passed probe and single-use evidence-bound `provider_recovery_verified` event before the shared seam requests a same-route child.
- Prove time passage alone creates no child.
- Prove forged changed-precondition content IDs create no child.
- Prove a no-launch or unresolved parent creates no child.

**Substep C — Degradation and route policy**

- Count the second matching accepted and canonically recorded exhausted child as the second observation.
- Establish degradation only after those two matching logical-dispatch outcomes.
- Use `_advance_configured_spec_fallback` only to propose a configured alternate.
- Pass the target through canonical joint admission.
- Use one `provider_route_child_reserved` composite event for the accepted flip.
- Derive the child receipt after commit.
- Use scalar hold/probe without widening.
- Use the same composite-event process for return to primary.
- Preserve execute and loop-execute fallback prohibition.

**Substep D — Replay, exceptions, and races**

- Reopen fresh ledgers across every T8 transition.
- Inject crashes around composite append, receipt derivation, cache update, `not_started`, launch entry, launch acceptance, closure return, and terminal-outcome append.
- Prove one probe lease, one observation per exhausted logical dispatch, one route state, and at most one child reservation for each authorization.
- Prove replay derives the same child receipt ID.
- Prove no-launch creates no observation or degradation.
- Prove ambiguous launch state becomes scheduling and cannot trigger route advancement or retry.
- Prove success and evidence-bound durable precondition changes reset the observation streak.
- Prove cache mismatch repairs from the ledger.
- Prove genuine internal errors bypass T8 and still open ordinary breakers.

**Acceptance**

- One accepted and canonically recorded exhausted dispatch creates one observation.
- Internal retries do not create multiple observations.
- Provider exhaustion is never double-recorded as ordinary failure.
- One observation does not degrade or flip.
- Time passage alone cannot launch a second identical attempt.
- Failed probe launches nothing.
- Passed probe authorizes one linked child through a canonical evidence-bound producer.
- Caller-forged change events fail.
- No-launch or unresolved parents authorize no child.
- Two matching observations establish degradation.
- Success or durable changed precondition resets the streak.
- Configured alternate selection uses only `_advance_configured_spec_fallback`.
- Target rejection produces no transition, child reservation, receipt, WBC attempt, client, or RPC.
- Accepted flip is one composite event projecting route and child together.
- Child receipt is derived after commit and replay-stable.
- Scalar pin never widens.
- Probe leases prevent hammering.
- Return-to-primary uses one composite transition-child event.
- Scheduling changes no breaker and cannot block.
- Genuine repeated internal errors still open their breaker.
- Execute fallback remains unsafe and prohibited.
- Restart, two-process races, torn-write handling, and crash injection reproduce one route and at most one authorized child reservation.
- An unresolved parent blocks all provider-driven child creation.
- Ledger-14 cannot create an unbounded retry or invalid-transition cascade.
- No T8 implementation remains in NBF-02 or NBF-03 surfaces beyond their generic extension and trace contracts.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_fallback_chains.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py \
  tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_gpt56_execution_policy.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/cloud/test_dispatch_reconciliation.py
```

**Synchronization point**

The Sol Oracle judges T8 as one batch. A second scheduling owner, duplicated policy in NBF-02/NBF-03, raw provider evidence reaching breakers, stderr policy parsing, double-recorded provider exhaustion, forged changed-precondition acceptance, no-launch/unresolved-parent child creation, unchanged redispatch, non-composite route transition, pre-commit receipt identity, independent provider store, or rotation outside the existing fallback selector is a rejection.

### Batch 7 — Fresh-base integration, independent review, and guarded delivery

#### NBF-07 — Rebase, validate, review, and push

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01 through NBF-06.

**Work**

1. Commit accepted implementation batches in the candidate tree.
2. Verify custody commits and protected artifacts.
3. Run:

```bash
git fetch origin main --prune
git rebase origin/main
```

4. Resolve conflicts by composing with current main.
5. Regenerate and review `docs/nbf-signal-inventory.json`.
6. Run the targeted authority-bypass checker against the rebased tree.
7. Run the authoritative broad validation exactly once after rebase.
8. Capture:
   - source and candidate SHAs;
   - exact validation result;
   - dispatch-family, logical-ID, parent-ID, door, admission-attempt, reservation, derived-receipt, WBC, `not_started`, final-launch-entry, acceptance, reconciliation, and terminal-outcome traces;
   - chain caller inventory;
   - production no-WBC rejection/internal-adapter evidence;
   - OMP and native route-applicable liveness evidence;
   - fingerprint and cross-logical-ID CAS races;
   - canonical changed-precondition producer and forged-event rejection evidence;
   - composite-event and receipt-derivation crash matrix;
   - reservation-reconciliation matrix;
   - no-launch identical-redispatch and restart evidence;
   - pre-entry, pre-acceptance, post-acceptance, ambiguous, outcome-append-failure, and restart evidence;
   - canonical terminal-outcome projection and provider non-duplication evidence;
   - receipt-context propagation evidence;
   - durable two-scan restart, TTL, PID-reuse, progress-reset, incarnation-reset, and concurrent-consumption evidence;
   - generated signal inventory path, generator version, artifact digest, and freshness result;
   - CLI and record-before-signal results;
   - targeted authority-checker result;
   - T8 replay/interleaving results;
   - breaker snapshots;
   - secondary negative raw-preflight scan;
   - shell syntax results;
   - criterion completion table.
9. Assign one GPT-5.6 Luna independent reviewer to the complete evidence.
10. Submit completion to the GPT-5.6 Sol Oracle.
11. Push `megado-nbf-guard-0826` to origin.
12. If rebase rewrote a published branch, verify its remote tip and use `--force-with-lease`, never unguarded force.
13. Stop before merging and request explicit user approval.

## 7. Task model classification

| Task | Classification | Rationale |
|---|---|---|
| NBF-01 schemas/projection/CAS | Normal / Luna | Contracts, terminal projection, evidence binding, receipt derivation, confirmation, and one-record journal behavior have deterministic tests. |
| NBF-02 admission/generic scheduler/T7 | Normal / Luna | One authority composes existing primitives under frozen launch sequencing and reconciliation rules. |
| NBF-03 door/WBC/authority wiring | Normal / Luna | Ownership, no-WBC closure, ordering, attempts, and launch cardinality have structural positive, negative, and static oracles. |
| NBF-04 Python dispositions | Normal / Luna | Context propagation, durable confirmation, and signal classes are fully specified. |
| NBF-05 shell/generated inventory | Normal / Luna | One CLI, one helper, ledger-owned confirmation, deterministic discovery, and stubbed ordering tests bound the work. |
| NBF-06 sole T8 policy | Normal / Luna | Typed terminal production and provider transitions have fixed ownership, projection, evidence binding, and crash rules. |
| NBF-07 integration | Normal / Luna | Mechanical rebase, regeneration, static checks, validation, review, and guarded push. |

No task meets the exceptional `[XHARD]` threshold. No additional architectural exploration is required.

## 8. Open questions and assumptions

### User-authority checkpoint

Merging `megado-nbf-guard-0826` into `main` requires explicit user approval after completion review and branch push. This does not block implementation.

### Implementable assumptions

- Two-scan confirmation applies to sustained supervision judgments, including wedge, hung-child, repair reaping, ensure-restack, and analogous worker-kill paths.
- Explicit owner-requested termination and elapsed timeout have direct causal evidence but still require record-before-signal.
- Durable two-scan state lives in the existing incident ledger and uses the versioned TTL policy in §4.20.
- One exhausted logical dispatch is one accepted canonical provider terminal outcome and one provider observation.
- A second same-route dispatch requires a passed probe and consumed, evidence-bound `provider_recovery_verified` event.
- Route-liveness digest or generation is receipt evidence, not retry identity.
- Native positive proof comes from the existing native backend/runtime/model seam and does not require OMP membership or speculative network calls.
- Last-known-good never widens a scalar pin.
- Existing static `ox-alpha` rows remain available for the discriminating test.
- A single valid `provider_route_child_reserved` journal event is sufficient to make route transition and child reservation crash-atomic.
- Child receipt identity is derived after commit and replayed from the composite event.
- Positive no-launch proof comes from the controlled adapter’s sequencing evidence, not merely absence of a process or marker.
- No-launch creates no worker terminal fingerprint, provider observation, phase failure, or breaker input.
- An ambiguous reservation may remain durably held rather than being guessed free.
- Every production no-WBC invocation either receives an internally constructed canonical adapter or rejects typedly.
- Canonical changed-precondition producers can read the existing authoritative repository, runtime, seed/interpreter, timeout-policy, route-transition, provider-probe, and repair evidence surfaces.
- Fake clocks, probes, ledgers, processes, RPCs, signals, WBC seams, launch adapters, torn-write fixtures, and two-process fixtures provide sufficient structural proof.
- `/workspace/.cloud-hot-env` remains untouched.
- Repository-wide signal inventory and targeted authority checking are bounded verification of the frozen criteria, not unrelated product expansion.
- No live marathon or box mutation is required.

## 9. Effort and huge-run determination

| Batch | Estimate |
|---|---:|
| Schemas, terminal projection, evidence-bound producers, composite event, confirmation, and reconciliation CAS | 2–2.5 days |
| Admission, generic scheduler, controlled launch, T7, exceptions, and transport | 2–2.5 days |
| Door wiring, no-WBC closure, WBC proof, and authority checker | 1–1.5 days |
| Python and shell disposition closure plus durable confirmation and generated inventory | 2.5–3 days |
| Sole T8 provider scheduling implementation | 2.5–3 days |
| Rebase, validation, review, and delivery | 1 day |
| **Total** | **11–13.5 days** |

**Huge-run determination: NO.** The work remains a bounded, approximately two-week plan with explicit synchronization gates and does not require an epic.

## 10. Validation and completion matrix

| Criterion | Required scenario | Required evidence | Passing condition |
|---|---|---|---|
| 1. Unique admission | Runtime, chain, WBC, no-WBC, caller inventory, OMP liveness, native liveness | Receipt, authority-checker output, and ordered intent/gate traces | Only the canonical gate authorizes workers; every production path enters it and supplies applicable positive proof. |
| 2. Exactly-once doors | Native, nested/direct OMP, babysitter, chain, no-WBC, generic linked child | Family/door/logical-ID/controlled-launch trace | One physical owner; each logical dispatch launches at most once; linked child waits for canonical terminal parent and authorization. |
| 3. Typed deaths | Generated Python/shell inventory | Context resolution, confirmation rows, ledger rows, CLI acknowledgement, ordering | Every worker kill records first; sustained kills consume confirmation; missing context or append failure prevents signal. |
| 4. Fingerprint block | Same fingerprint across logical IDs, liveness-digest-only change, valid durable change, forged change | Terminal projection, producer evidence, CAS winner, consumed event | One reservation across IDs; volatile proof and forged changes reject; one authoritative durable change authorizes one reservation. |
| 5. Joint model admission | Static `ox-alpha` acceptance/live OMP rejection; native positive-proof acceptance/refusal | Static, OMP, and native outcomes | Applicable proof is required before WBC/client/RPC; native routes are not forced into OMP. |
| 6. Structural spy | Door removal, duplicate gate, chain bypass, no-WBC bypass, WBC prestart, raw launch access, second launch | Ordered traces, negative tests, authority checker | Every bypass, ownership duplication, or ordering/cardinality violation fails structurally or statically. |
| 7. Cooldown scheduling | Repeated conditions, expiry, serialized return | Condition payload, retry-wait IDs, breaker/WBC snapshots | Shared seam reruns admission; no failure, WBC attempt, block, or premature launch. |
| 8. Provider degradation | Canonical exhausted outcome, first observation, probe, authorized child, second observation, flip, scalar hold, return, execute ban | Terminal events, projection events, producer evidence, composite child reservation | NBF-06 alone implements sustained evidence and routing; no breaker leakage, double recording, or unchanged retry. |
| Receipt derivation | Ordinary and composite reservations, restart, torn append | Committed event IDs and replayed receipts | Receipt is derived post-commit and reproduces byte-for-byte; no circular input exists. |
| Composite atomicity | Crash/torn-write around route transition | Fresh replay and child count | Route transition and child reservation are both visible or both absent from one event. |
| No-launch truth | Proven pre-entry exception, missing marker, contradictory marker, identical retry | Launch-state events, reconciliation, fingerprint/breaker snapshots | Only positive not-started proof releases; no terminal fingerprint is created; ambiguity remains held. |
| Terminal projection | Success, ordinary failure, provider exhaustion, disposition | Canonical terminal event and reservation projection | Every accepted non-scheduling terminal result records once before closure/consumer projection. |
| Reservation reconciliation | No-launch, recovered terminal, ambiguous, conflicting replay | Reconciliation events and restart projection | No blind release or relaunch; honest evidence selects one legal state. |
| Final-launch exceptions | Raise before entry, before acceptance, after acceptance, append failure, restart | Controlled markers, typed outcomes, reconciliation | Proven no-launch closes safely; accepted/ambiguous cases remain unresolved until evidence. |
| Changed preconditions | All allowlisted reasons plus forged inputs | Producer outputs and CAS validation | Identities come from authoritative evidence; caller-forged unequal IDs cannot authorize retry. |
| Two-scan durability | Restart, expiry, PID reuse, progress advance, supervisor/container change, race | Confirmation projection and signal count | First scan never signals; only one matching unexpired second scan authorizes one signal. |
| Signal closure | Live discovery against canonical artifact | Generator output, artifact digest, `--check` | No unclassified real signal, stale artifact, or untested exclusion. |
| Authority closure | Doors and chain origins | AST/static checker plus secondary grep | No forbidden authority call, direct launch construction, no-WBC bypass, or raw launch access remains. |
| Crash safety | Injection around ledger/cache/receipt/launch/outcome boundaries | Replay state and launch count | No partial transition, duplicate child, fabricated outcome, circular receipt, or blind retry. |

## 11. Authoritative post-rebase validation

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_dispatch_reconciliation.py \
  tests/cloud/test_controlled_final_launch.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_worker_admission_authority.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/cloud/test_watchdog_dispositions.py \
  tests/cloud/test_watchdog_wrappers.py \
  tests/cloud/test_repository_signal_inventory.py \
  tests/workers/test_omp_adapter.py \
  tests/resident/test_managed_provider_agent_runner.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_python_signal_inventory.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py \
  tests/arnold_pipelines/megaplan/test_fallback_chains.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py \
  tests/arnold_pipelines/megaplan/test_gpt56_execution_policy.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py \
  tests/arnold_pipelines/megaplan/test_plan_circuit.py
```

```bash
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-heartbeat
bash -n arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog
```

```bash
python scripts/generate_nbf_signal_inventory.py --check
python scripts/check_worker_admission_authority.py --check
```

```bash
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

The targeted authority checker owns final admission-authority closure. The generated, reviewed, freshness-checked `docs/nbf-signal-inventory.json` owns final signal classification. The secondary grep remains readable evidence but cannot replace either structured check.

## 12. Completion conditions

The work is complete only when:

- criteria 1–8 have PASS evidence;
- all 42 existing runtime-attestation tests remain green;
- one chain-inclusive admission authority remains;
- every production `run_step_with_worker` path enters `dispatch_with_admission`;
- production `wbc_dispatch=None` cannot reach an unadmitted legacy launch;
- every OMP route has exact current membership proof;
- every native route has equivalent positive backend/runtime/model proof;
- missing route-applicable proof rejects before launch;
- native models are not forced into OMP and no speculative admission health check exists;
- chain and WBC cannot authorize or start a worker before admission;
- WBC intent, reservation, derived receipt, `not_started`, attempt start, final-launch entry, acceptance, reconciliation, and outcome ordering is proven;
- physical ownership and logical-dispatch cardinality are separately proven;
- no logical dispatch performs more than one final launch;
- raw production launch primitives are accessible only through the controlled adapter;
- no family-wide lease was added;
- every linked provider child has a canonical terminal parent and durable authorization;
- no-launch and unresolved parents cannot create provider-driven children;
- every final-launch closure returns or is normalized into typed `DispatchOutcome`;
- `no_launch` is distinct, requires positive sequencing proof, reconciles first, and creates no worker terminal event, fingerprint, provider observation, phase failure, or breaker input;
- identical redispatch after truthful no-launch uses a fresh admission reservation;
- missing or contradictory no-launch evidence becomes unresolved;
- every accepted non-scheduling terminal result records through one canonical `worker_terminal_outcome` writer before reservation closure and consumer projection;
- provider exhaustion is not double-recorded as ordinary failure;
- pre-entry, pre-acceptance, post-acceptance, ambiguous, outcome-append-failure, and restart cases pass;
- raw provider scheduling evidence never reaches generic failure handling;
- semantic CAS uniqueness is independent of logical ID;
- volatile liveness proof changes cannot bypass retry refusal;
- valid changed-precondition events are minted by canonical reason-specific producers;
- evidence-to-identity binding is validated before consumption;
- forged unequal content IDs cannot authorize redispatch;
- valid changed-precondition events are allowlisted and consumed once;
- route transition and child reservation are represented by one composite journal event;
- the composite event contains no child receipt-ID input;
- child receipt identity is derived after commit and replayed byte-for-byte;
- replay projects transition and child together or neither;
- no second journal, pseudo-transaction, store, or rotator exists;
- `reservation_reconciled` truthfully distinguishes no-launch, recovered terminal, and ambiguous state;
- blind release and blind relaunch are impossible;
- scheduling serializes end to end and bypasses all failure/breaker accounting;
- cooldown and provider conditions cannot set `blocked`;
- genuine repeated internal errors still open breakers;
- receipt context reaches launcher, resident, watchdog, and wrapper boundaries;
- missing in-band worker context prevents signaling;
- observed and non-worker records never fabricate worker identity;
- durable two-scan confirmation is ledger-owned, restart-safe, TTL-bounded, and single-consumption;
- PID reuse, process-start change, progress advance, expiry, or supervisor/container incarnation change resets confirmation;
- `docs/nbf-signal-inventory.json` is generated, reviewed, and fresh against live discovery;
- every live-discovered real signal is classified;
- every worker-killing signal is preceded by a successful canonical append;
- every sustained-proof signal references a consumed matching confirmation;
- append, confirmation, or CLI failure leaves live victims unsignaled;
- static `ox-alpha` acceptance and joint live rejection are proven;
- the targeted authority checker passes across all doors and chain origins;
- NBF-06 starts only after NBF-01 through NBF-05 pass;
- NBF-06 is the sole T8 policy owner;
- configured fallback selection uses only `_advance_configured_spec_fallback`;
- scalar pins hold/probe without widening;
- execute and loop-execute fallback prohibition remains;
- wrapper syntax, signal-inventory freshness, authority checking, and secondary raw-preflight scans pass;
- fresh fetch/rebase and the authoritative suite succeed;
- custody commits and protected artifacts survive;
- the independent Luna reviewer and Sol Oracle accept completion;
- the candidate branch is pushed to origin;
- no box-only behavior change exists;
- no merge to `main` occurs without explicit user approval.

## 13. Revised settled-plan readiness

**Disposition: READY_FOR_FRESH_LUNA_SETTLED-PLAN WAVE.**

The W4 material findings are resolved at contract, ownership, sequencing, validation, and completion levels:

- linked-child receipt identity is derived from the committed composite event and canonical child identity, eliminating circular input while preserving one-record atomicity;
- `no_launch` is a distinct truthful state with `launch_state=not_started`, reconciliation-before-projection, and no worker terminal fingerprint, provider observation, or breaker accounting;
- controlled launch sequencing makes missing or contradictory evidence unresolved rather than guessed free;
- every production `run_step_with_worker` path enters canonical admission, including the no-WBC case;
- one canonical terminal-outcome writer records every accepted non-scheduling result before reservation closure and consumer projection;
- provider exhaustion remains typed and is never double-recorded as ordinary failure;
- canonical reason-specific changed-precondition producers bind content identities to authoritative evidence, and CAS rejects caller-forged changes;
- NBF-06 depends on NBF-01 through NBF-05 and remains the sole T8 policy owner;
- durable two-scan confirmation is owned by the existing ledger with a frozen key, versioned TTL policy, atomic consumption/replacement, restart behavior, and reset semantics;
- a targeted static checker proves authority deletion and launch ownership across all doors and chain origins;
- NBF-01 owns schemas, replay projection, receipt derivation, terminal projection, evidence validation, confirmation, and the single ledger primitive only;
- NBF-02 owns admission, the generic scheduler, controlled launch, T7, typed outcome intake, truthful reconciliation, transport, and breaker bypass;
- NBF-03 owns only physical doors, no-WBC closure, WBC ordering, generic attempts, launch cardinality, traces, and the authority checker;
- OMP and native routes both require positive route-applicable liveness proof;
- native models are not forced into OMP and admission adds no speculative network checks;
- route transition and child reservation remain one composite NDJSON event;
- unresolved reservations retain a frozen truthful reconciliation contract;
- the plan-created family-wide concurrency promise remains removed without weakening per-logical-ID or linked-child invariants;
- the repository-wide signal inventory remains generated, freshness-checked, reviewed, and consumed by final integration;
- no prepare/commit protocol, scheduler, store, journal, rotator, family lease, or `[XHARD]` task is introduced.

One scheduling loop, one admission authority, one ledger authority, one terminal-outcome writer, one provider projection, one configured fallback-selection door, one signal helper, one durable confirmation projection, one authority checker, and one generated signal inventory remain. No material evidence question or user-policy decision remains. A fresh complete GPT-5.6 Luna settled-plan sense-check is mandatory before freezing this snapshot; the later user checkpoint remains merge approval only.

STABILITY: STABLE
