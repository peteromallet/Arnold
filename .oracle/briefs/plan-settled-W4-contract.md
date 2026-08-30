# Settled-plan W4 — contract-completeness lens

## Complete immutable North Star

# North Star — Arnold self-healing supervision

**End state:** An agent harness where no worker can be launched onto a spec that
isn't live, a box that won't survive it, or a seed bound to the wrong interpreter —
and where every worker death carries its killer's identity in a typed record that
the recovery loop consumes before it ever retries the same fingerprint.

**Enduring principles**
- One door per invariant: admission, dispatch, and death are each enforced at
  exactly one place; duplicate preflights are deleted, not patched around.
- Deaths speak: SIGKILL, timeout, terminate, restack — every termination emits
  `{killer, signal, elapsed_s}` into the failure ledger. Silent death is a bug.
- Models are admitted, not assumed: a model id must resolve against catalog,
  prefix map, family classifier, and live provider membership at dispatch time,
  typedly rejecting expired or unknown ids.
- Fixes ship on main through the fixer contract; hotfixes that live only as
  deployed-but-uncommitted files do not exist.

**Anti-patterns to avoid**
- Single-scan verdicts treated as sustained truth (wedge kills, restacks).
- Anonymous integer exit codes where a disposition belongs.
- Judgment-based "healthy" claims without positive proof (live pid + advancing seq).
- Redispatch of an identical failure fingerprint without a changed precondition.

**Aligned progress feels like:** fewer incident classes over time, each new stall
arriving with evidence attached and leaving with a root fix on main.

## Complete frozen agent goal

# Agent Goal — make the 24h failure marathon structurally impossible

[North Star](./northstar.md) — this run advances "one door per invariant" and
"deaths speak" by shipping the systemic guard Grok specified in
docs/nbf-grok-verdicts.md (§3), verified by structural tests.

## Objective
Implement, in this repo, the typed worker-disposition control plane that makes the
2026-08-26 NBF failure marathon (11+ failure events, docs/nbf-failure-ledger.md)
impossible to recur:

1. **Unique admission gate.** Extend `require_production_worker_dispatch_runtime`
   (cloud/runtime_attestation.py) into the single production worker-admission door:
   spec translation, catalog row, model-family classification, live omp membership,
   seed/interpreter binding, timeout budget — fail closed before any worker exists.
2. **Wire all three launch doors — exactly once each.** workers/_impl.py non-OMP
   routes, workers/omp.py run_omp_step (backend entry; _impl delegates to it at
   _impl.py:7698-7713 — the nested OMP path must total ONE hit), and
   cloud/babysitter/launch.py pre-managed-launch. No other refresh_/require_
   preflight may execute on these paths.
3. **Typed death dispositions — every real signal branch.** Route ALL terminate
   sites through one typed helper over `IncidentLedger.append_event`
   (incident/ledger.py:338-361), appending
   `{killer, signal, elapsed_s, disposition_id}`:
   - launcher: the child is killed BEFORE TimeoutExpired raises
     (subagent-launcher/launch_omp_agent.py:251-261) — disposition at the kill,
     not the exception
   - resident/subagent.py: two terminate→kill ladders (:4818-4824, :5065-5072)
   - watchdog: SIGTERM + wedged-signaling path (wrappers/arnold-watchdog)
   - ensure-megaplan-watchdog restack pkill
4. **Fingerprint redispatch block — pre-launch.** Admission refuses to launch a
   worker whose dispatch fingerprint matches the last terminal fingerprint
   (incident/projection.py:452-478 currently only diagnoses at the 3rd repeat)
   unless a durable changed-precondition identity is recorded.
5. **Joint model admission — and expired-ID proof.** One admission function
   validates spec↔catalog↔family↔live provider membership simultaneously; a
   test proves the discriminating case: static catalog ACCEPTS an expired id
   (ox-alpha, workers/omp.py:98-105 / model_seam.py:502-506) while the joint
   admission REJECTS it typedly against the live provider.
6. **Structural spy test — three doors, gate-before-spawn.** Driving
   `run_step_with_worker` (workers/_impl.py:7347 — NOT the underscore name)
   and `run_omp_step` under a production manifest hits the gate exactly ONCE
   per dispatch (the nested OMP delegation totals one hit), the babysitter
   pre-launch door is covered, the spy intercepts only final spawn/RPC (no
   mock early-return), and a door-bypass today would make it fail.

## In scope / non-goals
- In scope: engine code above + their focused tests; catalog/family wiring already
  on main stays; hot-env pin file gets a comment pointing at the gate (no behavior).
- Non-goals: the 22-milestone NBF chain itself (it runs independently);
  Discord/resident features; CI rework beyond making new tests run.

## Settled decisions
- Model policy (user-pinned, superseding the earlier staged declaration):
  Planner, Oracle, and any justified `[XHARD]` task = GPT-5.6 Sol
  (`gpt-5.6-sol`, high reasoning); every normal exploration, critique,
  execution, and independent review task = GPT-5.6 Luna (`gpt-5.6-luna`).
  No model switch is authorized without user approval.
- Fix delivery = fixer contract: commit in candidate tree, ship to origin/main,
  never hotfix-by-deploy-only.
- Single-scan supervision verdicts are banned; two-scan confirmation pattern is
  the standard for any kill decision.

## Validation
- pytest tests/cloud/test_runtime_attestation.py (existing 42) PLUS new
  disposition/admission/spy suites, all green locally.
- Structural spy asserts exactly-once gating from both doors.
- bash -n on wrapper changes; grep proves no remaining raw refresh_/require_ pair
  on the three doors.

## Done / stop
Done when criteria 1–6 hold with green suites and the structural spy passes after a
fresh `git fetch && git rebase origin/main`. Stop (blocked) only if box evidence
needed for a disposition consumer is unavailable and user cannot grant it.

## Sync policy
Push branch `megado-nbf-guard-0826` to origin when batches pass oracle gates.
Merging to main requires user approval at completion review.

## Source custody for resumed execution

Build on refreshed `origin/main` at immutable source SHA
`798c50619204010ed3f4297fbb57988fe9381924`; preserve the five branch-only
planning/evolution commits and the protected untracked artifacts named in
`custody.md`. The source update does not widen scope or authorize a main merge.

7. **Cooldown-aware scheduling conditions (T7, added via plan evolution — ledger
   entry 13).** Treat an active same-phase/spec cgroup-OOM cooldown as a typed,
   time-bounded `scheduling_condition`, never a worker/phase failure: shared
   pre-dispatch seam calls `memory_cooldown_wait_secs`, emits `retry_wait`
   evidence, sleeps via injectable clock/sleeper, reruns admission. A
   scheduling condition increments neither deterministic-phase-failure nor
   repeated-signature counters and cannot set the plan to `blocked`; genuine
   repeated internal_errors still open their breakers. Foundation shipped to
   main: a9e1c7d0d6 (death expiry) + af370f5ec6 (defer refusals; recover
   repeated-failure blocks).

8. **Typed `provider_degraded` scheduling condition (T8, plan evolution — ledger
   entry 14).** Consecutive upstream idle-timeouts/availability errors for one
   spec become a typed, time-bounded `scheduling_condition`
   (`reason=provider_degraded`, carrying `phase`/`spec`/`retry_after_s`) —
   never a worker/phase failure. Breaker-exempt like T7. If a configured
   fallback exists (same-family alternate or last-known-good), flip through the
   existing fallback-chain door (`fallback_chains.py`,
   `_advance_configured_spec_fallback`) with the flip target passing joint
   admission (criterion 5); if the pin is scalar, hold with a bounded health
   probe and redispatch once after recovery. Flip AND return-to-primary append
   ledger evidence. Files: fallback_chains.py, workers/_impl.py,
   handlers/shared.py, orchestration/phase_result.py, recovery_policy.py,
   auto.py breakers, incident/ledger.py. DEEP verdict (Grok 4.6, full spec in
   .oracle/findings/evolution-entry14.txt).

## Complete plan v4 candidate

Plan SHA-256: 19d37c43207e116877ba0f3b5391fdfd1cf55f8cffda3d11e9869feb8ba734db

# Plan — Typed NBF worker admission, disposition, and scheduling control plane

## 1. Planning basis and custody

This revision incorporates every accepted W3 Oracle finding and applies the Oracle’s simpler correction for dispatch-family concurrency. It preserves every frozen product criterion, authority boundary, custody rule, delivery rule, model policy, and merge checkpoint.

- Branch: `megado-nbf-guard-0826`
- Planning HEAD recorded by the prior immutable snapshot: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Immutable source base: `origin/main` at `798c50619204010ed3f4297fbb57988fe9381924`
- Superseded immutable plan-v3 SHA-256: `f2fc235e52f00d9fe039951b4d86e8723fc38b289cb8ca9955d6469f90e3c3d3`
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

## 2. Revision delta from immutable plan v3

This revision makes the following material W3 corrections:

1. Assigns T8 implementation and policy ownership exclusively to NBF-06.
   - NBF-01 owns schemas, replay projection, and the ledger CAS/composite-event primitive.
   - NBF-02 owns canonical admission, generic `dispatch_with_admission`, T7 cooldown behavior, typed `DispatchOutcome` intake, scheduling transport, breaker bypass, exception normalization, reconciliation integration, and generic linked-dispatch mechanics.
   - NBF-03 owns only physical-door wiring, WBC ordering, admission-attempt/final-launch cardinality, context propagation, and generic structural traces.
   - NBF-06 alone owns provider observation, probe, degradation, fallback/scalar policy, linked recovery and transition decisions, return-to-primary policy, replay, races, and T8 tests.
2. Defines route-applicable positive liveness:
   - OMP routes require exact current membership from `omp models --json`.
   - Native routes require positive proof from the native backend’s existing runtime/provider/model authority.
   - Absence or failure of the applicable proof is a typed pre-launch refusal.
3. Replaces multi-record route-transition transactions with one composite ledger event containing both the authorized route transition and linked-child reservation. Replay projects both or neither from a single NDJSON append.
4. Freezes the `reservation_reconciled` schema, legal transitions, evidence requirements, idempotency, release rules, permanent-hold behavior, and restart projection.
5. Defines final-launch exception normalization:
   - a proven pre-spawn exception becomes a typed terminal outcome;
   - a post-spawn or ambiguous exception leaves an unresolved reservation;
   - retry is forbidden until positive reconciliation evidence is recorded.
6. Defines a canonical generated repository-wide signal inventory at `docs/nbf-signal-inventory.json`, with deterministic discovery, regeneration, and freshness checking.
7. Removes the plan-created promise that a dispatch family can never contain concurrently active independent launches. No family-wide lease is added.
8. Preserves the required narrower invariant:
   - each logical dispatch performs at most one final launch;
   - a fallback, recovery, or return child cannot reserve or launch until its parent has a terminal outcome and a durable authorization exists;
   - concurrent independent requests remain governed by semantic-fingerprint reservation CAS.
9. Deletes provider-policy scenarios and acceptance obligations from NBF-02 and NBF-03 and consolidates them under NBF-06.
10. Updates dependencies, focused tests, crash matrices, completion criteria, and final evidence collection to match these ownership boundaries.

No new store, rotator, pseudo-transaction, network health service, family lease, or `[XHARD]` task is introduced.

## 3. Current-state inventory

| Criterion | Status | Existing basis | Remaining work |
|---|---|---|---|
| 1. Unique admission gate | **Partially satisfied** | `cloud/runtime_attestation.py::require_production_worker_dispatch_runtime` validates seed, manifest generation, dependency interpreter, and seed interpreter. | It lacks complete production caller coverage and does not jointly own translation, catalog, family, route-applicable liveness, source/runtime, timeout, memory, fingerprint, or reservation. |
| 2. Exactly-once launch doors | **Partially satisfied** | `run_step_with_worker` is the public worker entry; nested OMP delegates to `run_omp_step`; babysitter has a managed-launch seam. | Raw preflights and WBC ordering obscure physical ownership. Admission attempts, logical dispatches, WBC starts, and final launches are not separately proven. |
| 3. Typed death dispositions | **Partially satisfied** | `IncidentLedger.append_event` is the journal write door; cgroup-OOM evidence is partially projected. | No complete schema/helper/CLI/context transport exists. Multiple Python and shell signal paths remain silent or anonymous. |
| 4. Fingerprint redispatch block | **Missing** | Incident projection diagnoses repeated repair attempts after failure. | No stable semantic fingerprint, cross-logical-ID CAS key, changed-precondition consumption, or atomic reservation exists. |
| 5. Joint model admission | **Partially satisfied** | Static catalog validation, model-family classification, translation, OMP membership, and native backend configuration exist independently. | No simultaneous route-applicable spec↔catalog↔family↔positive-liveness decision exists. Static authorities still accept expired `openrouter/stealth/ox-alpha`. |
| 6. Structural spy | **Missing** | Individual worker and babysitter tests exist. | No production-manifest spy proves canonical inclusion, WBC ordering, physical ownership, or gate-before-final-launch. |
| 7. Cooldown scheduling | **Partially satisfied** | `memory_cooldown_wait_secs` and post-failure cooldown recovery exist. | Cooldown is not transported as a typed scheduling result through the whole stack and still relies on post-failure counter repair. |
| 8. Provider degradation | **Missing** | Retryability classification and configured fallback rotation exist. | No typed post-launch outcome projection, sustained observation policy, bounded hold/probe, atomic transition-child event, or restart-safe return path exists. |
| Crash reconciliation | **Missing** | Running receipts and incident replay provide partial evidence. | No frozen reconciliation event distinguishes positive no-launch, recovered post-launch outcome, and ambiguous launch state. |
| Signal closure | **Missing** | Named Python and shell sites are known. | No generated, freshness-checked inventory proves repository-wide classification. |

### Fragmented controls to eliminate or subordinate

- Raw runtime refresh/require and source preflight in `workers/_impl.py`.
- `chain/source_admission.py::worker_launch_preflight` and chain-local launch refusals.
- Standalone memory admission in `handlers/shared.py`.
- OMP static catalog logic separate from current membership proof.
- Native backend selection without a positive applicable model/runtime proof returned to admission.
- Launcher-local spec translation.
- WBC attempt creation before canonical admission.
- Provider fallback decisions outside the shared scheduling seam.
- Cooldown repair and counter reset in `auto.py`.
- Death information split among raw signal sites, state summaries, and plan events.
- Hand-maintained or partial signal-site fixtures that do not compare against live repository discovery.

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
- a linked recovery/fallback/return child cannot reserve or launch until the parent has a terminal outcome and its authorization is durably recorded;
- an unresolved parent reservation cannot produce a child.

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

The admission receipt stores the applicable liveness proof identity. OMP membership digest and native proof generation are evidence, not semantic retry identity.

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

Manifestless development remains explicitly non-production. Production intent, a production manifest, or a configured cloud seed cannot collapse into a development no-op.

Route-liveness, ledger, source, interpreter, or runtime-proof failure rejects before client, process, WBC attempt, or RPC construction.

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

### 4.6 Changed-precondition contract

A terminal worker disposition records the semantic dispatch fingerprint.

Admission refuses a proposed redispatch of the same terminal fingerprint unless a later, single-use, allowlisted `changed_precondition` event proves a durable change.

Schema:

```text
schema_version
event_type = changed_precondition
event_id
plan_id
phase
dispatch_family_id | null
logical_dispatch_id | null
reason
before_content_id
after_content_id
evidence_event_id
source_revision | null
runtime_vector | null
interpreter_identity | null
route_identity | null
timeout_policy_identity | null
repair_commit_sha | null
recorded_at
actor
```

Allowlisted reasons:

```text
source_revision_changed
runtime_generation_changed
seed_or_interpreter_binding_changed
timeout_policy_changed
authorized_route_changed
provider_recovery_verified
verified_repair_committed
```

Rules:

- `before_content_id` and `after_content_id` differ.
- The reason-specific identity field is present.
- `authorized_route_changed` references a jointly admitted composite route transition.
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
- changed-precondition consumption;
- provider observation transitions;
- probe leases and results;
- composite route-transition-and-child reservation;
- reservation reconciliation.

No second journal or metadata store is introduced.

#### Ordinary reservation

Under the existing journal lock:

1. Load the current projection version.
2. Read the latest terminal fingerprint, active reservation, and eligible changed-precondition event.
3. Compare projection key plus semantic fingerprint.
4. Reject an unchanged terminal fingerprint without an unused valid change.
5. Reject an active duplicate reservation even if logical IDs differ.
6. Consume the valid change event when required.
7. Append one `admission_reserved` event.
8. Return receipt data only after the append is durable.

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
child_admission_receipt_id
child_route_liveness_identity
consumed_changed_precondition_event_id | null
recorded_at
actor
```

Under one lock and one append:

1. Validate the child through canonical admission up to its transactional step.
2. Verify projection version, parent terminality, target authorization, applicable route-liveness proof, fingerprint rules, and absence of a duplicate child reservation.
3. Consume the authorizing event logically as part of the composite event.
4. Append exactly one `provider_route_child_reserved` NDJSON record.
5. Replay projects both the route transition and child reservation from that record.
6. Return one receipt whose `reservation_event_id` and `route_transition_event_id` identify the same composite event.

There are no separate `provider_route_flip` plus `admission_reserved` appends, no prepare record, no commit marker, and no multi-record pseudo-transaction. A crash before the append yields neither state; a crash after the append yields both.

Fallback metadata is a derived cache updated after commit.

### 4.8 Reservation reconciliation

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

Acceptable proof includes:

- a persisted final-launch state marker still at `not_started`;
- a final-launch wrapper exception classified before its spawn/RPC/WBC/managed-command acceptance marker;
- equivalent deterministic evidence proving no process, RPC, WBC attempt, or managed command was created.

Effects:

- releases only the named reservation;
- creates no worker terminal fingerprint;
- permits a new reservation subject to current admission checks;
- cannot be inferred from absence of a PID, elapsed time, missing cache, or a restarted supervisor.

#### `terminal_outcome_recovered`

Allowed only when positive evidence proves a final launch occurred and a canonical success, terminal failure, or worker disposition can be linked to the receipt.

Effects:

- closes the reservation;
- projects the recovered terminal outcome;
- applies normal terminal-fingerprint and changed-precondition rules;
- never authorizes an immediate identical retry by itself.

#### `permanent_hold_ambiguous`

Used when evidence cannot distinguish no launch from accepted or running launch.

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

Blind release based on missing processes, stale timestamps, incomplete metadata, or supervisor restart is forbidden.

### 4.9 Crash and replay semantics

Incident-ledger events are authoritative. Derived fallback or running metadata is written only after the relevant ledger append commits.

Crash behavior:

- Before lock: no new state exists.
- After read/before compare: no new state exists.
- After compare/before append: no new state exists.
- During the single composite-event write: recovery accepts only a complete valid NDJSON record; a torn record is rejected and never projected.
- After composite append/before cache update: replay reconstructs both transition and child reservation.
- After cache update/before final launch: the child reservation is unresolved and must reconcile.
- Before the final-launch acceptance marker: a raised exception may reconcile as `released_no_launch`.
- After the acceptance marker/before returned outcome: the reservation is unresolved and cannot be retried blindly.
- After returned outcome/before outcome append: the reservation remains unresolved until `terminal_outcome_recovered` or another canonical outcome is recorded.
- Outcome append failure never silently releases a reservation.
- A losing concurrent writer reloads and does not duplicate a reservation, composite transition, probe lease, provider observation, reconciliation, or launch.

Required crash injection boundaries:

```text
before lock
after read/before compare
after compare/before append
during composite-event write
after composite append/before cache update
after cache update/before final-launch entry
after final-launch entry/before acceptance marker
after acceptance marker/before closure return
after closure return/before outcome append
after outcome append/before derived-cache update
```

Fresh-ledger reopen tests must prove:

- a route transition and linked-child reservation are both visible or both absent;
- no torn event is projected;
- unresolved launch state never triggers blind redispatch;
- reconciliation is idempotent;
- cache loss or mismatch cannot change authoritative state.

### 4.10 Scheduling-condition schema and transport

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

### 4.11 Typed final-launch outcome and exception boundary

Every final-launch closure returns `DispatchOutcome`:

```text
schema_version
kind
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
```

`kind`:

```text
success
ordinary_terminal_failure
provider_exhausted
unresolved_launch
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

The final-launch closure receives a typed launch-state recorder:

```text
mark_final_launch_entered()
mark_final_launch_accepted(worker_identity, process_or_rpc_identity)
```

The shared seam wraps the closure:

- Exception before `mark_final_launch_entered` is normalized to an ordinary typed terminal outcome and the reservation reconciles as `released_no_launch`.
- Exception after entry but before acceptance may reconcile as `released_no_launch` only when the final-launch implementation supplies positive proof that no spawn, RPC, WBC attempt, or managed command was accepted.
- Exception after acceptance becomes `unresolved_launch`.
- An exception with insufficient sequencing evidence becomes `unresolved_launch`.
- `unresolved_launch` returns a scheduling condition and requires reservation reconciliation before any retry.
- Outcome-append failure also leaves the reservation unresolved.
- No exception path silently drops the receipt or starts another logical dispatch.

Provider rules:

- One exhausted logical dispatch produces one provider observation regardless of internal retry count.
- English stderr is never parsed for scheduling policy.
- Auth, quota, rate limit, unsupported model, context-window, malformed output, schema, and internal errors cannot produce `provider_exhausted`.
- Success and ordinary failure reach existing consumers only after canonical outcome recording.
- Raw provider degradation evidence never reaches `RecoveryPolicy`.

NBF-01 defines the schemas. NBF-02 implements this generic intake and exception boundary. NBF-06 alone supplies the T8 provider-policy response to `provider_exhausted`.

### 4.12 One scheduling owner with one provider-policy extension

`dispatch_with_admission` is the only scheduling loop and the only component allowed to:

- call admission;
- wait through a scheduling interval;
- rerun admission;
- invoke a final-launch closure;
- create the next linked logical dispatch;
- return a serialized scheduling condition when the bounded window expires.

For each logical dispatch it:

1. Invokes the canonical gate.
2. On receipt, verifies the committed reservation.
3. Invokes the final-launch closure at most once.
4. Normalizes closure exceptions.
5. Records or reconciles the typed outcome.
6. Returns success or ordinary terminal failure normally.
7. Handles T7 memory cooldown directly through its generic pre-launch scheduling loop.
8. Passes `provider_exhausted` to the single T8 policy implementation added by NBF-06.
9. Executes the pure policy decision without transferring loop ownership.
10. Creates a linked child only after the parent terminal event and durable authorization exist.
11. Never recursively re-enters a physical door.

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

For a route transition, the policy supplies the authorization and target. `dispatch_with_admission` constructs the linked child request, and canonical admission uses the single composite event to validate the target and reserve the child.

### 4.13 T7 memory cooldown

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

### 4.14 T8 provider/precondition projection

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

1. One exhausted logical dispatch creates one observation.
2. Internal retry chatter changes only evidence fields.
3. Matching requires phase, selected spec, projection key, and precondition identity.
4. Success or an allowlisted durable change resets the observation streak.
5. Two consecutive matching observations establish degradation.
6. Excluded error classes never enter the degradation projection.
7. Duplicate observation IDs do not increment twice.
8. All transitions compare the expected projection version.
9. One caller holds a probe lease.
10. Restart replay yields identical state.
11. Fallback metadata mirrors the projection and is never authoritative.
12. `_advance_configured_spec_fallback` remains the only configured fallback-selection door.
13. An unresolved parent reservation blocks observation-driven child creation.
14. The composite event projects route transition and child reservation together.

### 4.15 T8 first observation, degradation, fallback, scalar hold, and return

#### First matching provider observation

- One exhausted availability or idle-timeout outcome appends one `provider_observation`.
- It does not mark the provider degraded or rotate.
- The policy appends `provider_hold` and returns `provider_observation_wait`.
- After `retry_not_before`, one caller acquires a probe lease.
- A failed probe appends typed evidence and launches no worker.
- A passed probe appends a successful `provider_probe_result` and an allowlisted `provider_recovery_verified` changed-precondition event.
- The shared seam may then request one linked same-route child admission.
- Admission consumes the event atomically with the child reservation.
- Time passage alone cannot authorize the child.

#### Second matching observation

- If the authorized linked child also exhausts with the same projection key and precondition identity, its observation establishes `provider_degraded`.
- The old logical dispatch is terminal and is never reused.
- No transition or child can be created from an unresolved parent.

#### Configured fallback

1. `_advance_configured_spec_fallback` proposes the next configured target.
2. The policy returns the proposed target and authorizing observation.
3. The shared seam constructs a linked child request.
4. Canonical admission jointly validates the target, including route-applicable positive liveness.
5. Rejection produces no transition, child reservation, WBC attempt, client, or RPC.
6. Acceptance appends one `provider_route_child_reserved` composite event.
7. The resulting child receipt names its parent and the composite event.
8. Derived fallback metadata updates after commit.
9. The shared seam performs the child’s one final launch.

#### Scalar pin

- Never widen to historical last-known-good.
- Append a bounded hold and return a scheduling condition.
- Acquire one bounded probe lease after `retry_not_before`.
- Run one injected, no-tool provider probe.
- Failed probes append evidence and remain scheduling.
- Passed probes create one `provider_recovery_verified` event.
- Exactly one linked same-route child reservation may consume that event.

#### Return to primary

1. Projection deadline and lease control primary probing.
2. A passing probe precedes child admission.
3. The policy proposes a return and supplies its authorization.
4. Canonical admission jointly validates the primary route.
5. One composite event records the return and reserves the linked child.
6. Cache state changes only after commit.
7. The old fallback logical dispatch is not reused.

#### Execute and loop-execute

- Fallback advancement remains prohibited.
- `ExecuteFallbackUnsafe` semantics remain.
- Bounded hold/probe scheduling is allowed.
- No provider rotation creates a second execute attempt.

### 4.16 Receipt context transport

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
- Running receipts persist the reference and final-launch state before supervision begins.
- Resident worker state retains it across same-session follow-up and termination ladders.
- Watchdog and restack code resolve it from the running receipt and ledger, verifying plan, receipt, PID, and process-start identity.
- Shell wrappers pass the resolved context to the disposition CLI.
- The standalone launcher accepts the reference through its invocation contract.
- Context cannot be reconstructed from model name, PID, current directory, or free-form text.
- Missing or inconsistent context prevents an in-band worker signal.
- Already-observed dead processes use an observed schema and never fabricate missing receipt data.

### 4.17 Canonical signal and disposition contracts

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

### 4.18 Shell disposition CLI

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
```

Wrapper order:

```text
resolve exact subject and process incarnation
resolve worker context or classify explicit non-worker subject
perform two observations where sustained proof is required
invoke disposition CLI
verify exit 0 and acknowledgement identity
invoke stub-able signal primitive
```

Nonzero status leaves a live victim unsignaled.

### 4.19 Generated repository-wide signal inventory

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

- two separated observations;
- same process-start identity;
- same relevant progress identity;
- positive lack-of-progress proof;
- PID replacement or progress resets confirmation.

Immediate explicit timeout or orderly owner-requested termination may use its direct causal event instead of two scans, but still requires record-before-signal.

## 5. Explicitly prohibited patterns

The implementation must not:

- retain chain-local or WBC-local admission authority;
- start a WBC worker attempt before admission;
- record scheduling as a WBC failure or completion;
- gate both `_impl.py` and `run_omp_step` for nested OMP;
- reuse a logical-dispatch ID after a final launch;
- perform two final launches under one logical ID;
- add a family-wide launch lease;
- allow a linked child before its parent has a terminal outcome;
- place scheduling loops in the gate, `auto.py`, `RecoveryPolicy`, handlers, fallback code, or the T8 policy component;
- implement T8 policy in NBF-02 or NBF-03;
- return raw provider-degradation evidence to generic breaker handling;
- parse English stderr for provider policy;
- treat internal retries as multiple provider observations;
- include route-liveness digest or generation in semantic retry identity;
- use different logical IDs to evade reservation uniqueness;
- write route transition and child reservation as separate journal events;
- add a prepare/commit pseudo-transaction or second journal;
- treat fallback metadata as authoritative;
- add a second provider rotator;
- force native models into OMP membership;
- add speculative network health checks to admission;
- release an unresolved reservation merely because a process cannot be found;
- normalize a post-spawn or ambiguous exception as a no-launch failure;
- invent a disposition, fingerprint, worker identity, signal, or killer for missing context;
- signal an in-band worker without resolved admission context;
- claim cgroup OOM without positive evidence;
- signal before the disposition append succeeds;
- treat a one-scan verdict, PID presence, completed marker, or stale timestamp as sustained kill proof;
- permit a free-form note, time passage, sleep, retry count, or liveness-receipt refresh to bypass fingerprint refusal;
- let a membership/runtime proof failure become accepted empty membership;
- accept a hand-maintained signal inventory without live-discovery comparison;
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
- changed-precondition consumption;
- probe-lease primitives;
- the single composite route-transition-and-child-reservation event;
- reservation reconciliation primitives;
- canonical disposition helper/CLI contracts.

It does not own canonical admission calls, scheduling loops, T7 behavior, T8 policy, physical doors, or provider fallback decisions.

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

**Work**

- Add strict `SchedulingCondition` and `DispatchOutcome` schemas.
- Add worker, observed-death, and non-worker disposition schemas.
- Add changed-precondition and semantic-fingerprint schemas.
- Add ordinary `admission_reserved`.
- Add the single composite `provider_route_child_reserved` event.
- Add `reservation_reconciled` with the three frozen resolutions.
- Add provider projection event schemas and deterministic replay without implementing provider policy.
- Add lock/read/compare/single-append CAS operations.
- Add one-use event consumption, probe leases, cache reconciliation, deterministic IDs, and torn-record handling.
- Add the shell disposition CLI.
- Do not implement request-specific admission, scheduling waits, provider policy, or caller wiring.

**Acceptance**

- Scheduling and outcomes round-trip strictly through serialization.
- Incomplete dispositions are rejected.
- Observed unknown death cannot claim OOM or fabricate worker identity.
- Non-worker lifecycle records validate without a worker fingerprint.
- TERM and KILL ladder IDs differ.
- Free-form changed-precondition reasons fail.
- Route-liveness digest is absent from semantic fingerprint.
- Same fingerprint with different logical IDs maps to the same reservation key.
- A change event is single-use.
- Two-process contention yields one ordinary reservation winner.
- Composite transition and child reservation project together from one record.
- A crash or torn write cannot expose a partial transition.
- `reservation_reconciled` rejects blind no-launch claims.
- Positive no-launch releases only the named reservation.
- Ambiguous launch stays held.
- Recovered terminal outcome applies normal fingerprint rules.
- Conflicting reconciliation is rejected; identical replay is idempotent.
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
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

**Synchronization point**

The Sol Oracle freezes schemas, fingerprint components, single-record composite-event behavior, reconciliation transitions, proof requirements, crash semantics, CLI behavior, and replay before caller work begins.

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
- T7 memory cooldown;
- typed `DispatchOutcome` intake;
- final-launch exception normalization;
- unresolved-reservation reconciliation integration;
- lossless `PhaseResult`/handler/`auto.py` scheduling transport;
- early breaker bypass;
- generic linked-child request construction after a supplied durable authorization.

NBF-02 does not own provider observation thresholds, probe policy, degradation, fallback selection, scalar policy, return-to-primary policy, or T8 race/replay decisions.

**Files and symbols**

- `cloud/runtime_attestation.py`
- Shared dispatch module containing `dispatch_with_admission`
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

**Work**

1. Inventory chain, raw runtime, memory, native liveness, OMP membership, and WBC callers.
2. Reduce retained helpers to non-authoritative primitives.
3. Add typed request, receipt, refusal, execution-context reference, and request-specific reservation.
4. Normalize model translation ownership.
5. Add injectable route-liveness resolution:
   - OMP `omp models --json`;
   - native positive backend/runtime/model proof.
6. Prove static acceptance and joint rejection of expired `openrouter/stealth/ox-alpha`.
7. Prove missing native positive proof rejects before client construction.
8. Move source/runtime, timeout, memory, fingerprint, and reservation checks into the gate.
9. Use the NBF-01 CAS primitive for ordinary and authorized child reservations.
10. Implement the generic scheduling loop without provider policy.
11. Implement T7 cooldown wait, evidence, bounded expiry, and complete re-admission.
12. Add typed final-launch state markers and exception normalization.
13. Integrate all three reconciliation outcomes.
14. Preserve scheduling through handler and `auto.py`.
15. Add early scheduling bypass before failure or breaker accounting.
16. Delete cooldown-specific counter repair/reset logic.
17. Define execution-context propagation at Python, subprocess, managed-command, and running-receipt boundaries.
18. Define the single typed T8 policy-extension interface consumed later by NBF-06; it may return decisions but cannot own waiting or launching.

**Acceptance**

- One receipt proves every frozen admission invariant.
- Chain has no independent authorization caller.
- Production cannot pass without source/runtime/seed/interpreter proof.
- OMP admission requires exact current membership.
- Native admission requires positive route-applicable backend/runtime/model proof.
- Missing or unreadable applicable proof fails typedly.
- Invalid timeout values fail typedly.
- Static `ox-alpha` acceptance remains while joint admission rejects it before client construction.
- Same semantic fingerprint with different logical IDs yields one reservation.
- Liveness-digest-only change does not authorize redispatch.
- One valid changed event authorizes one reservation and is named by the receipt.
- Cooldown causes multiple admission attempts and zero launches before expiry.
- Scheduling expiry reaches `PhaseResult` without failure accounting, WBC attempt, or `blocked`.
- Final-launch closure is invoked at most once per logical dispatch.
- Raise-before-spawn becomes a typed terminal outcome with positive no-launch reconciliation.
- Raise-after-spawn or ambiguous raise becomes unresolved.
- Outcome-append failure remains unresolved.
- Restart never blindly relaunches an unresolved reservation.
- Generic child construction requires a terminal parent and durable authorization.
- No provider observation, probe, flip, scalar hold, or return policy is implemented here.
- Execution context is persisted before supervision begins.

**Focused validation**

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_dispatch_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py \
  tests/arnold_pipelines/megaplan/test_plan_circuit.py \
  tests/workers/test_omp_adapter.py
```

### Batch 3 — Physical doors, WBC ordering, and generic structural proof

#### NBF-03 — Wire the three doors and prove generic launch cardinality

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-02.

**Ownership boundary**

NBF-03 owns only:

- the three physical-door bindings;
- nested/direct OMP ownership;
- chain delegation;
- WBC intent/admission/start ordering;
- admission-attempt and final-launch traces;
- generic scheduling no-launch traces;
- receipt-context propagation through the doors.

It does not own or assert first/second provider observations, provider probes, degradation, fallback selection, scalar routing, return-to-primary, or provider-transition policy.

**Files and symbols**

- `workers/_impl.py::run_step_with_worker`
- `_run_step_with_worker_legacy`
- WBC dispatcher construction and callbacks
- `workers/omp.py::run_omp_step`
- `cloud/babysitter/launch.py`
- Chain delegation path
- `docs/nbf-hourly-loop-goal.md`
- `cloud/fixer_model_policy.py`
- New `tests/cloud/test_worker_dispatch_spy.py`
- `tests/cloud/test_chain_admission.py`
- `tests/cloud/test_babysitter_routing.py`
- `tests/cloud/test_babysitter_goal.py`
- `tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py`

**Work**

- Delete `_impl.py` raw refresh/require/source-preflight blocks.
- Native `_impl.py` binds the shared seam once.
- Nested OMP delegates without outer admission.
- `run_omp_step` binds the shared seam for nested and direct OMP.
- Babysitter binds it before running receipt or managed command.
- Emit optional pre-admission WBC intent only.
- Move admission before `wbc_dispatch.run`.
- Start WBC attempt state only inside the admitted final-launch closure.
- Ensure generic scheduling consumes no WBC start/failure/complete.
- Keep normal and agent-dispatcher paths identical in ownership.
- Propagate receipt context and launch-state markers into every final-launch boundary.
- Document that checked-in pins are advisory and canonical admission is authoritative.
- Do not mutate `/workspace/.cloud-hot-env`.

**Structural scenarios**

1. Native non-OMP success.
2. Nested OMP success.
3. Direct OMP success.
4. Babysitter success.
5. Chain-originated success.
6. Admission rejection for each door.
7. Memory cooldown with multiple admission attempts and one eventual final launch.
8. Bounded scheduling expiry with no final launch.
9. Generic authorized child dispatch:
   - parent has a terminal outcome;
   - child has a new logical ID;
   - parent and authorization are linked;
   - each logical ID launches at most once.
10. Rejected or unresolved parent produces no child reservation or launch.
11. WBC ordered trace:
    - optional intent;
    - admission reservation;
    - WBC attempt start;
    - final-launch entry and acceptance;
    - typed outcome.
12. Scheduling WBC trace:
    - intent;
    - scheduling condition;
    - no WBC attempt start/failure/complete.
13. No `MEGAPLAN_MOCK_WORKERS=1`; only final spawn/RPC/WBC/managed-command seams are replaced.

**Acceptance**

- One physical owner per dispatch family.
- One final launch maximum per logical dispatch.
- Generic authorized child has a new logical ID linked to a terminal parent.
- An unresolved parent cannot create a child.
- No recursive physical-door entry occurs.
- Nested OMP has no outer owner.
- Ordered traces prove reservation before WBC attempt and final launch.
- Door removal, duplicate outer gate, chain bypass, pre-admission WBC start, or second final launch under one logical ID fails tests.
- Independent different-fingerprint dispatches are not artificially blocked by a new family lease.
- The three door files contain no raw refresh/require calls.
- No T8 provider-policy behavior is implemented or duplicated in this batch.

**Focused validation**

```bash
pytest -q \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
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

The Sol Oracle reviews caller inventory, route-applicable liveness traces, WBC ordering, physical-owner traces, generic linked-child identity, nested OMP ownership, chain bypass tests, and the raw-preflight scan. Provider-policy judgments are deferred to NBF-06.

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
- Focused launcher, fan, resident, operator, and incarnation tests
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
- OOM requires positive evidence.
- Unknown death remains explicitly unknown.
- Non-worker lifecycle signals never impersonate workers.
- State summaries derive from canonical events.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
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

**Work**

For worker supervision signals:

1. Resolve exact PID/process group and process-start identity.
2. Resolve the admission receipt context.
3. Take two separated observations where sustained proof is required.
4. Require stable incarnation and positive lack-of-progress proof.
5. Invoke the disposition CLI.
6. Verify exit 0 and matching acknowledgement.
7. Invoke the stub-able signal primitive.

For non-worker signals:

- Emit a typed non-worker lifecycle record before signaling.
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

- PID, process-start, or progress changes reset confirmation.
- TERM→KILL produces two records.
- The ensure script resolves the active installed source/runtime.
- Cross-invocation confirmation state includes watchdog/container incarnation.
- CLI or context failure leaves a live victim unsignaled.

**Acceptance**

- Every live-discovered repository real signal or probe has exactly one artifact row.
- Every worker kill is helper-routed.
- A stale or incomplete checked-in inventory fails `--check`.
- First scan never signals where sustained proof is required.
- Progress/incarnation changes reset confirmation.
- CLI precedes signal.
- CLI failure causes zero signal calls.
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
  tests/arnold_pipelines/megaplan/test_python_signal_inventory.py
```

**Synchronization point**

The Sol Oracle receives the generated artifact, artifact digest, discovery rules, freshness result, and ordering evidence. An unclassified live-discovered signal, stale artifact, fabricated worker identity, unresolved worker context followed by a signal, or signal reachable after append failure blocks the batch.

### Batch 6 — Sole T8 provider-resilience implementation

#### NBF-06 — Implement T8 through the shared seam and existing fallback door

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01, NBF-02, and NBF-03.

**Ownership boundary**

NBF-06 is the sole implementation and test owner for:

- structured provider-exhaustion production;
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

It uses the NBF-01 projection/CAS primitives and NBF-02 shared scheduling seam. It creates no scheduler, admission authority, rotator, projection, or journal.

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
- Existing fallback, phase-result, memory, auto, execution-policy, reconciliation, and ledger suites

**Substep A — Structured `DispatchOutcome` producers**

- Export one typed exhausted-dispatch outcome from OMP and non-OMP.
- Include logical ID, phase/spec, retryability class, internal attempt count as evidence, terminal evidence ID, and precondition identity.
- Prove internal retries count once.
- Prove excluded error classes return ordinary failures.
- Prove raw stderr never drives provider policy.

**Substep B — First observation and recovery**

- Append exactly one observation for one exhausted logical dispatch.
- Enter bounded hold without degrading or rotating.
- Acquire one probe lease after `retry_not_before`.
- Append typed passed/failed probe evidence.
- Require a passed probe and single-use `provider_recovery_verified` event before the shared seam requests a same-route child.
- Prove time passage alone creates no child.
- Prove an unresolved parent creates no child.

**Substep C — Degradation and route policy**

- Count the second matching exhausted child as the second observation.
- Establish degradation only after those two matching logical-dispatch outcomes.
- Use `_advance_configured_spec_fallback` only to propose a configured alternate.
- Pass the target through canonical joint admission.
- Use one `provider_route_child_reserved` composite event for the accepted flip.
- Use scalar hold/probe without widening.
- Use the same composite-event process for return to primary.
- Preserve execute and loop-execute fallback prohibition.

**Substep D — Replay, exceptions, and races**

- Reopen fresh ledgers across every T8 transition.
- Inject crashes around composite append, cache update, launch entry, launch acceptance, closure return, and outcome append.
- Prove one probe lease, one observation per exhausted logical dispatch, one route state, and at most one child reservation for each authorization.
- Prove ambiguous launch state becomes scheduling and cannot trigger route advancement or retry.
- Prove success and durable precondition changes reset the observation streak.
- Prove cache mismatch repairs from the ledger.
- Prove genuine internal errors bypass T8 and still open ordinary breakers.

**Acceptance**

- One exhausted dispatch creates one observation.
- Internal retries do not create multiple observations.
- One observation does not degrade or flip.
- Time passage alone cannot launch a second identical attempt.
- Failed probe launches nothing.
- Passed probe authorizes one linked child.
- Two matching observations establish degradation.
- Success or durable changed precondition resets the streak.
- Configured alternate selection uses only `_advance_configured_spec_fallback`.
- Target rejection produces no transition, child reservation, WBC attempt, client, or RPC.
- Accepted flip is one composite event projecting route and child together.
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

The Sol Oracle judges T8 as one batch. A second scheduling owner, duplicated policy in NBF-02/NBF-03, raw provider evidence reaching breakers, stderr policy parsing, unchanged redispatch, unresolved-parent child creation, non-composite route transition, independent provider store, or rotation outside the existing fallback selector is a rejection.

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
6. Run the authoritative broad validation exactly once after rebase.
7. Capture:
   - source and candidate SHAs;
   - exact validation result;
   - dispatch-family, logical-ID, parent-ID, door, admission-attempt, reservation, WBC, final-launch-entry, acceptance, and outcome traces;
   - chain caller inventory;
   - OMP and native route-applicable liveness evidence;
   - fingerprint and cross-logical-ID CAS races;
   - composite-event crash matrix;
   - reservation-reconciliation matrix;
   - pre-spawn, post-spawn, ambiguous, outcome-append-failure, and restart evidence;
   - receipt-context propagation evidence;
   - generated signal inventory path, generator version, artifact digest, and freshness result;
   - CLI and record-before-signal results;
   - T8 replay/interleaving results;
   - breaker snapshots;
   - negative raw-preflight scan;
   - shell syntax results;
   - criterion completion table.
8. Assign one GPT-5.6 Luna independent reviewer to the complete evidence.
9. Submit completion to the GPT-5.6 Sol Oracle.
10. Push `megado-nbf-guard-0826` to origin.
11. If rebase rewrote a published branch, verify its remote tip and use `--force-with-lease`, never unguarded force.
12. Stop before merging and request explicit user approval.

## 7. Task model classification

| Task | Classification | Rationale |
|---|---|---|
| NBF-01 schemas/projection/CAS | Normal / Luna | Contracts and one-record journal behavior have deterministic tests. |
| NBF-02 admission/generic scheduler/T7 | Normal / Luna | One authority composes existing primitives under frozen sequencing and reconciliation rules. |
| NBF-03 door/WBC wiring | Normal / Luna | Ownership, ordering, attempts, and launch cardinality have structural positive and negative oracles. |
| NBF-04 Python dispositions | Normal / Luna | Context propagation and signal classes are fully specified. |
| NBF-05 shell/generated inventory | Normal / Luna | One CLI, one helper, deterministic discovery, and stubbed ordering tests bound the work. |
| NBF-06 sole T8 policy | Normal / Luna | Typed outcome production and provider transitions have fixed ownership, projection, and crash rules. |
| NBF-07 integration | Normal / Luna | Mechanical rebase, regeneration, validation, review, and guarded push. |

No task meets the exceptional `[XHARD]` threshold. No additional architectural exploration is required.

## 8. Open questions and assumptions

### User-authority checkpoint

Merging `megado-nbf-guard-0826` into `main` requires explicit user approval after completion review and branch push. This does not block implementation.

### Implementable assumptions

- Two-scan confirmation applies to sustained supervision judgments, including wedge, hung-child, repair reaping, ensure-restack, and analogous worker-kill paths.
- Explicit owner-requested termination and elapsed timeout have direct causal evidence but still require record-before-signal.
- One exhausted logical dispatch is one provider observation.
- A second same-route dispatch requires a passed probe and consumed `provider_recovery_verified` event.
- Route-liveness digest or generation is receipt evidence, not retry identity.
- Native positive proof comes from the existing native backend/runtime/model seam and does not require OMP membership or speculative network calls.
- Last-known-good never widens a scalar pin.
- Existing static `ox-alpha` rows remain available for the discriminating test.
- A single valid `provider_route_child_reserved` journal event is sufficient to make route transition and child reservation crash-atomic.
- Positive no-launch proof must come from launch sequencing evidence, not merely absence of a process.
- An ambiguous reservation may remain durably held rather than being guessed free.
- Fake clocks, probes, ledgers, processes, RPCs, signals, WBC seams, torn-write fixtures, and two-process fixtures provide sufficient structural proof.
- `/workspace/.cloud-hot-env` remains untouched.
- Repository-wide signal inventory is bounded verification of the frozen “all terminate sites” criterion, not unrelated product expansion.
- No live marathon or box mutation is required.

## 9. Effort and huge-run determination

| Batch | Estimate |
|---|---:|
| Schemas, projection, composite event, and reconciliation CAS | 1.5–2 days |
| Admission, generic scheduler, T7, exceptions, and transport | 2–2.5 days |
| Door wiring and WBC structural proof | 1–1.5 days |
| Python and shell disposition closure plus generated inventory | 2.5–3 days |
| Sole T8 provider scheduling implementation | 2.5–3 days |
| Rebase, validation, review, and delivery | 1 day |
| **Total** | **10.5–13 days** |

**Huge-run determination: NO.** The work remains a bounded, approximately two-week plan with explicit synchronization gates and does not require an epic.

## 10. Validation and completion matrix

| Criterion | Required scenario | Required evidence | Passing condition |
|---|---|---|---|
| 1. Unique admission | Runtime, chain, WBC, caller inventory, OMP liveness, native liveness | Receipt and ordered intent/gate traces | Only the canonical gate authorizes workers; every route supplies applicable positive proof. |
| 2. Exactly-once doors | Native, nested/direct OMP, babysitter, chain, generic linked child | Family/door/logical-ID/final-launch trace | One physical owner; each logical dispatch launches at most once; linked child waits for terminal parent and authorization. |
| 3. Typed deaths | Generated Python/shell inventory | Context resolution, ledger rows, CLI acknowledgement, ordering | Every worker kill records first; missing context or append failure prevents signal. |
| 4. Fingerprint block | Same fingerprint across logical IDs, liveness-digest-only change, valid durable change | CAS winner and consumed event | One reservation across IDs; volatile proof change rejected; one durable change authorizes one reservation. |
| 5. Joint model admission | Static `ox-alpha` acceptance/live OMP rejection; native positive-proof acceptance/refusal | Static, OMP, and native outcomes | Applicable proof is required before WBC/client/RPC; native routes are not forced into OMP. |
| 6. Structural spy | Door removal, duplicate gate, chain bypass, WBC prestart, second launch under one logical ID | Ordered generic traces and negative tests | Every bypass, ownership duplication, or ordering/cardinality violation fails structurally. |
| 7. Cooldown scheduling | Repeated conditions, expiry, serialized return | Condition payload, retry-wait IDs, breaker/WBC snapshots | Shared seam reruns admission; no failure, WBC attempt, block, or premature launch. |
| 8. Provider degradation | First observation, probe, authorized child, second observation, flip, scalar hold, return, execute ban | Typed outcomes, projection events, composite child reservation | NBF-06 alone implements sustained evidence and routing; no breaker leakage or unchanged retry. |
| Composite atomicity | Crash/torn-write around route transition | Fresh replay and child count | Route transition and child reservation are both visible or both absent from one event. |
| Reservation reconciliation | No-launch, recovered terminal, ambiguous, conflicting replay | Reconciliation events and restart projection | No blind release or relaunch; honest evidence selects one legal state. |
| Final-launch exceptions | Raise before entry, before acceptance, after acceptance, append failure, restart | Launch markers, typed outcomes, reconciliation | Proven pre-spawn closes safely; post-spawn/ambiguous remains unresolved until evidence. |
| Signal closure | Live discovery against canonical artifact | Generator output, artifact digest, `--check` | No unclassified real signal, stale artifact, or untested exclusion. |
| Crash safety | Injection around ledger/cache/launch/outcome boundaries | Replay state and launch count | No partial transition, duplicate child, fabricated outcome, or blind retry. |

## 11. Authoritative post-rebase validation

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_dispatch_reconciliation.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/cloud/test_watchdog_dispositions.py \
  tests/cloud/test_watchdog_wrappers.py \
  tests/cloud/test_repository_signal_inventory.py \
  tests/workers/test_omp_adapter.py \
  tests/resident/test_managed_provider_agent_runner.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_python_signal_inventory.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
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

The generated, reviewed, freshness-checked `docs/nbf-signal-inventory.json` owns final signal classification. A raw grep count cannot distinguish real signals, probes, fixtures, and intentional non-worker lifecycle behavior.

## 12. Completion conditions

The work is complete only when:

- criteria 1–8 have PASS evidence;
- all 42 existing runtime-attestation tests remain green;
- one chain-inclusive admission authority remains;
- every OMP route has exact current membership proof;
- every native route has equivalent positive backend/runtime/model proof;
- missing route-applicable proof rejects before launch;
- native models are not forced into OMP and no speculative admission health check exists;
- chain and WBC cannot authorize or start a worker before admission;
- WBC intent, reservation, attempt start, final-launch entry, acceptance, and outcome ordering is proven;
- physical ownership and logical-dispatch cardinality are separately proven;
- no logical dispatch performs more than one final launch;
- no family-wide lease was added;
- every linked child has a terminal parent and durable authorization;
- unresolved parents cannot create children;
- every final-launch closure returns or is normalized into typed `DispatchOutcome`;
- pre-spawn, post-spawn, ambiguous, outcome-append-failure, and restart cases pass;
- raw provider scheduling evidence never reaches generic failure handling;
- semantic CAS uniqueness is independent of logical ID;
- volatile liveness proof changes cannot bypass retry refusal;
- valid changed-precondition events are allowlisted and consumed once;
- route transition and child reservation are represented by one composite journal event;
- replay projects both or neither;
- no second journal, pseudo-transaction, store, or rotator exists;
- `reservation_reconciled` truthfully distinguishes no-launch, recovered terminal, and ambiguous state;
- blind release and blind relaunch are impossible;
- scheduling serializes end to end and bypasses all failure/breaker accounting;
- cooldown and provider conditions cannot set `blocked`;
- genuine repeated internal errors still open breakers;
- receipt context reaches launcher, resident, watchdog, and wrapper boundaries;
- missing in-band worker context prevents signaling;
- observed and non-worker records never fabricate worker identity;
- `docs/nbf-signal-inventory.json` is generated, reviewed, and fresh against live discovery;
- every live-discovered real signal is classified;
- every worker-killing signal is preceded by a successful canonical append;
- append/CLI failure leaves live victims unsignaled;
- sustained supervision kills require two matching scans;
- static `ox-alpha` acceptance and joint live rejection are proven;
- NBF-06 is the sole T8 policy owner;
- configured fallback selection uses only `_advance_configured_spec_fallback`;
- scalar pins hold/probe without widening;
- execute and loop-execute fallback prohibition remains;
- wrapper syntax, inventory freshness, and raw-preflight scans pass;
- fresh fetch/rebase and the authoritative suite succeed;
- custody commits and protected artifacts survive;
- the independent Luna reviewer and Sol Oracle accept completion;
- the candidate branch is pushed to origin;
- no box-only behavior change exists;
- no merge to `main` occurs without explicit user approval.

## 13. Revised settled-plan readiness

**Disposition: READY_FOR_FRESH_LUNA_SETTLED-PLAN WAVE.**

The W3 material findings are resolved at contract, ownership, sequencing, validation, and completion levels:

- NBF-01 owns schemas, replay projection, and the single ledger primitive only;
- NBF-02 owns admission, the generic scheduler, T7, typed outcome intake, exception normalization, reconciliation integration, transport, and breaker bypass;
- NBF-03 owns only physical doors, WBC ordering, generic attempts, launch cardinality, and traces;
- NBF-06 alone owns all T8 provider policy and tests;
- OMP and native routes both require positive route-applicable liveness proof;
- native models are not forced into OMP and admission adds no speculative network checks;
- route transition and child reservation are one composite NDJSON event;
- unresolved reservations have a frozen truthful reconciliation contract;
- final-launch exceptions cannot silently free or duplicate a reservation;
- the plan-created family-wide concurrency promise is removed without weakening per-logical-ID or linked-child invariants;
- the repository-wide signal inventory is generated, freshness-checked, reviewed, and consumed by final integration;
- no new store, journal, pseudo-transaction, rotator, family lease, or `[XHARD]` task is introduced.

One scheduling loop, one admission authority, one ledger authority, one provider projection, one configured fallback-selection door, one signal helper, and one generated signal inventory remain. No material evidence question or user-policy decision remains. A fresh complete GPT-5.6 Luna settled-plan sense-check is mandatory before freezing this snapshot; the later user checkpoint remains merge approval only.

STABILITY: STABLE

## Prior W1 synthesis

# Settled-plan sense-check W1 synthesis

- Immutable plan snapshot: `770c61d4c63e1af0af1c92630fbce3ccdf956d66250c8134cb4db00c5b3dcb69`
- North Star snapshot: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Reviewers: three independent GPT-5.6 Luna normal-task critics, run in parallel
- Result: **material revision required; plan returns to STILL_FORMING**
- Reserved pre-settled critique slot: **skipped: plan had been classified already settled**
- North Star disposition: the accepted corrections strengthen “one door per
  invariant,” “deaths speak,” scheduling-as-scheduling, and the ban on unchanged
  fingerprint redispatch. No accepted finding widens the frozen agent goal.

## Accepted findings

1. **One chain admission authority (CONTRACT-1 / SEQ-1).** Accept. Inventory every
   production caller of `worker_launch_preflight` and chain-local raises. Route
   genuine launches through the canonical admission function; make any retained
   helper a non-authoritative primitive. Add a negative chain-bypass structural
   test. This is load-bearing for criteria 1–2.

2. **One scheduling loop owner; distinguish door ownership from attempts
   (SIMP-1 / CONTRACT-2 / SEQ-2).** Accept. A single shared
   `dispatch_with_admission`/equivalent seam owns typed-condition evidence,
   injected sleep/probe, bounded retry, and full admission rerun. The pure gate
   returns a receipt or typed condition; `RecoveryPolicy` only classifies and
   bypasses breaker accounting; delete the remaining post-failure `auto.py`
   repair/reset path. Exactly-once means one physical door owner and one final
   launch per logical dispatch, not one admission attempt during cooldown.

3. **No synthetic death identity for scheduling (SIMP-3).** Accept.
   `SchedulingCondition` must not require `disposition_id`. It carries a
   typed `cause_event_id`/evidence identity when an actual observation or death
   exists; `disposition_id` is optional and only references a real worker
   disposition. This preserves criterion 7/8 typing without manufacturing deaths.

4. **Freeze the full disposition and CLI contract (CONTRACT-3 / SEQ-4).** Accept.
   Specify enums, required/optional fields for in-band versus observed deaths,
   ledger location/input, serialization, CLI path/exit contract, and record-before-
   signal failure semantics. Shell tests must stub both the disposition CLI and
   signal primitive, assert ordering/arguments for every branch, prove append
   failure leaves victims alive, and emit a machine-readable scoped signal-site
   inventory.

5. **One durable provider/precondition projection, no parallel rotator
   (SIMP-2 / CONTRACT-4 / SEQ-3).** Accept with simplification. Define the typed,
   phase/spec-keyed state and atomic transition/replay rules, but implement it as
   a projection over canonical incident-ledger events plus existing fallback
   metadata—not as a second provider-health store or independent state machine.
   Cover streak identity, current route, retry deadline, probe status, authorized
   target, success/change resets, restart/interleaving, joint-admission-before-
   flip, scalar-pin hold, and return-to-primary evidence.

6. **Changed-precondition allowlist and atomic admission reference (CONTRACT-6).**
   Accept. Freeze event fields and allowlisted reason/content identities; define
   concurrency/atomic check semantics; require the admitted receipt to reference
   the accepted change event. “Explicit recovery action” is not a free-form bypass.

7. **Correct dependencies (CONTRACT-5).** Accept for NBF-04: it explicitly depends
   on NBF-02’s final admission receipt/fingerprint contract. For NBF-06, keep the
   task self-contained only if it owns availability-evidence propagation and tests
   it before route transitions; otherwise split that producer into an earlier
   dependency. Do not implement against an interim incompatible schema.

## Rejected / non-material findings

- **SIMP-4:** no change. Separate Python and shell disposition batches, focused
  tests, the structural spy, negative raw-preflight scan, and one authoritative
  post-rebase matrix are proportionate and test distinct failure modes.
- No critic proposed valid scope expansion or an `[XHARD]` execution kernel.

## Required Sol revision

Revise the entire plan against all accepted findings. Preserve its current
criterion coverage and normal/Luna classifications unless new evidence meets the
exceptional `[XHARD]` threshold. After revision, report the plan delta and whether
any material investigation is newly required. A fresh complete Luna settled-plan
wave must review the revised immutable snapshot before the plan can freeze.

## Prior W2 synthesis

# Settled-plan sense-check W2 synthesis

- Immutable revised plan: `d341a71cf9b15766a35cd2cafd9d6e89f5ef2a2afc5d386fd2ce9c2bda639fdd`
- North Star: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Reviewers: three independent GPT-5.6 Luna normal-task critics in parallel
- Result: **material revision required; plan remains STILL_FORMING**
- North Star disposition: every accepted correction closes a duplicate launch,
  silent-death, volatile-fingerprint, or scheduling-as-failure path. Scope remains
  bounded by the frozen goal.

## Accepted findings

1. **Dispatch cardinality across fallback (SIMP2-1).** Accept. Each provider-route
   attempt is a new `logical_dispatch_id`, linked to the prior terminal attempt
   and authorizing transition event. One logical dispatch has one physical owner
   and at most one final launch. Fallback never launches twice under the old ID.

2. **Typed post-launch outcome owned by the shared seam (SIMP2-2).** Accept.
   The final-launch closure returns a typed `DispatchOutcome` carrying success,
   ordinary terminal failure, or exhausted provider evidence.
   `dispatch_with_admission` alone projects that evidence, emits a scheduling
   condition, performs the authorized hold/probe/fallback, and starts a linked
   child dispatch. Generic failure/breaker code never receives raw provider
   degradation evidence.

3. **Semantic CAS key and stable fingerprint (CONTRACT2-1 / SEQ2-5).** Accept.
   Reservation uniqueness is projection key + semantic dispatch fingerprint,
   independent of logical-dispatch ID. Remove volatile live-membership digest
   from retry identity; membership is admission evidence. Any semantically
   meaningful change requires an allowlisted, single-use changed-precondition
   event. Add concurrent-different-ID and digest-only negative tests.

4. **Crash-atomic route transition (CONTRACT2-2).** Accept. Prefer one atomic
   ledger transaction/CAS operation that consumes the authorizing event, records
   transition, and reserves the linked child dispatch; metadata is derived cache.
   Specify restart reconciliation and crash injection around every boundary.

5. **Receipt context propagation and typed unknowns (CONTRACT2-3 / SEQ2-4).**
   Accept. Freeze how receipt/fingerprint/phase/spec/worker identity reaches
   launcher, resident, watchdog, and wrapper interfaces. In-band signals fail
   closed without it. Already-observed external/kernel deaths use an explicit
   observed/non-worker/unknown schema and never fabricate worker identity.

6. **Repository-wide real-signal inventory (CONTRACT2-4).** Accept with scope
   discipline. Inventory every real signal site repository-wide. Route every
   worker-killing site through the canonical helper; classify and mechanically
   test probes, non-worker lifecycle signals, and intentional exclusions. This
   satisfies “ALL terminate sites” without silently broadening unrelated product
   behavior.

7. **CAS primitive ownership (SEQ2-1).** Accept. NBF-01 freezes schemas and adds
   the ledger transaction/CAS primitive. NBF-02 is the sole owner of request-
   specific reservation. Add two-process race, lock/append failure, and restart
   replay tests.

8. **WBC admission ordering (SEQ2-2).** Accept. Explicitly define WBC start as
   pre-admission intent only or move admission before `wbc_dispatch.run`; no
   worker-attempt start/failure/complete may be consumed by a scheduling
   condition. Add ordered WBC-intent/gate/final-launch traces.

9. **End-to-end scheduling propagation (SEQ2-3).** Accept. NBF-01 owns condition
   serialization and PhaseResult transport. The admission/scheduling batch wires
   handler/auto early bypass before failure recording. Tests prove expiry and
   provider holds cannot increment breakers or set blocked.

## Non-material / rejected

- The suggestion to split `incident/disposition.py` is non-material. Keep one
  canonical ledger authority unless implementation size proves a purely internal
  module split necessary; do not create a second writer or state owner.
- No finding justifies `[XHARD]`; all corrections are precise, bounded normal
  Luna work.

## Required Sol revision

Apply every accepted correction across the full plan. Reconcile task dependencies,
acceptance criteria, completion matrix, and structural tests, not just design prose.
Preserve KISS/YAGNI: one scheduling owner, one ledger transaction authority, one
route projection, one signal helper. Report a revision delta and explicit stability.
A fresh complete Luna wave is mandatory after the new immutable snapshot.

## Prior W3 synthesis

# Settled-plan sense-check W3 synthesis

- Immutable plan: `f2fc235e52f00d9fe039951b4d86e8723fc38b289cb8ca9955d6469f90e3c3d3`
- North Star: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Reviewers: three independent GPT-5.6 Luna normal-task critics
- Result: **material revision required; STILL_FORMING**
- No new exploration or `[XHARD]` execution is justified.

## Accepted findings

1. **Single T8 implementation owner (SIMP3-1 / CONTRACT3-3).** Accept. NBF-01
   owns only schemas/projection/CAS. NBF-02 owns the generic scheduling seam, T7,
   typed DispatchOutcome intake, transport, and breaker bypass. NBF-03 owns only
   physical doors, WBC ordering, admission-attempt/final-launch cardinality, and
   generic traces. NBF-06 alone owns T8 observation, probe, degradation, fallback/
   scalar routing, return, replay, and race policy/tests.

2. **Route-applicable positive liveness proof (CONTRACT3-1).** Accept as a bounded
   clarification. OMP routes require current `omp models --json` membership.
   Native routes require their equivalent positive runtime/provider/model proof
   already available at the native backend seam; missing/unreadable proof fails
   typedly before launch. Do not force native models into the OMP catalog and do
   not add speculative network health checks.

3. **Reservation reconciliation event (CONTRACT3-4).** Accept. Freeze
   `reservation_reconciled` payload, legal transitions, positive no-launch versus
   ambiguous/post-launch evidence, idempotency, release/permanent-hold semantics,
   and restart projection. Blind release is forbidden.

4. **Generated repository-wide signal inventory (CONTRACT3-5).** Accept. Name a
   canonical machine-readable artifact and generator/discovery rule; tests compare
   live discovered real-signal sites to the reviewed classifications; NBF-07
   consumes the artifact. A hand-maintained incomplete fixture cannot pass.

5. **Crash-atomic route transition (SEQ3-1).** Accept the simplest protocol: one
   composite ledger event atomically contains the authorized route transition and
   linked-child reservation. Replay projects both or neither from one NDJSON
   append. Do not create multi-record pseudo-transactions or a second journal.

6. **Final-launch exception normalization (SEQ3-2).** Accept. The shared seam wraps
   the closure. Raise-before-spawn becomes a typed terminal outcome; raise-after-
   spawn or ambiguous launch state becomes unresolved and must reconcile against
   positive process/receipt evidence before retry. Test pre-spawn, post-spawn,
   outcome-append failure, and restart.

## Accepted finding with different correction

- **CONTRACT3-2 family concurrency.** The plan itself introduced a stronger
  “no concurrently active final launches in one family” promise not required by
  the frozen goal. Reject adding a family-wide lease. Remove that promise.
  Preserve the needed invariant: a fallback/return child cannot reserve or launch
  until the parent has a terminal outcome and an atomic authorized transition;
  concurrent independent dispatches remain governed by the semantic-fingerprint
  CAS.

## Rejected / non-material

- Do not split the canonical incident authority merely for file-size aesthetics.
- Do not add live network probes beyond route-applicable positive model/runtime
  membership evidence.
- No scope expansion, new store, new rotator, or `[XHARD]` task.

## Required Sol revision

Apply the accepted corrections everywhere: design, task ownership, dependencies,
spies, acceptance, completion matrix, and revision delta. Prefer deletion and a
single composite event over new protocols. A fresh complete Luna wave is required
on the next immutable plan snapshot.

Freshly review the entire v4 snapshot. Prior accepted findings are now plan
requirements; do not repeat them without new contradictory plan/source evidence.
Do not add semantics beyond the frozen goal. Prefer deleting plan-created promises
over inventing machinery. Model assignment: user-selected GPT-5.6 Luna (normal).
Every finding needs an explicit North Star disposition.

Find only material contradiction, missing authority/identity/state transition,
unverifiable acceptance, or goal mismatch that would let execution pass while a
frozen criterion fails.

Return `PASS_CONTRACT_COMPLETE` or ranked `CONTRACT4-N` findings with
materiality, exact evidence, smallest correction, criterion impact, and North
Star disposition. Under 650 words.
