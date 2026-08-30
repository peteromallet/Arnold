# Settled-plan W3 — sequencing and verification lens

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

## Complete plan v3 candidate

Plan SHA-256: f2fc235e52f00d9fe039951b4d86e8723fc38b289cb8ca9955d6469f90e3c3d3

# Plan — Typed NBF worker admission, disposition, and scheduling control plane

## 1. Planning basis and custody

This revision incorporates every material finding accepted by the W2 Oracle synthesis and none of the rejected or non-material suggestions.

- Branch: `megado-nbf-guard-0826`
- Planning HEAD recorded by the prior immutable snapshot: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Immutable source base: `origin/main` at `798c50619204010ed3f4297fbb57988fe9381924`
- Superseded immutable plan-v2 SHA-256: `d341a71cf9b15766a35cd2cafd9d6e89f5ef2a2afc5d386fd2ce9c2bda639fdd`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Protected untracked artifact: `.oracle/briefs/planner-sol.md`
- Earlier protected planning and evolution artifacts remain under the custody rules in `custody.md`.
- `.oracle/tasklist.md` is foreign onboarding-run evidence and remains excluded.
- `tests/cloud/test_runtime_attestation.py` contains 42 existing tests.
- The machine-readable live-membership surface remains `omp models --json`. Read, timeout, command, or schema failures become typed admission refusals, never empty-catalog acceptance.
- No files were edited and no mutating commands or tests were run by the read-only revision owner.

The source update, custody requirements, and this revision do not widen the frozen product scope or authorize a merge to `main`.

## 2. Revision delta from immutable plan v2

This revision makes the following material corrections required by W2:

1. Defines each provider-route attempt as a distinct `logical_dispatch_id`. A fallback or return-to-primary attempt is a linked child dispatch authorized by a durable transition event; no logical dispatch performs more than one final launch.
2. Adds a typed `DispatchOutcome` returned by every final-launch closure. `dispatch_with_admission` alone consumes exhausted provider evidence, projects scheduling state, performs holds/probes/transitions, and creates linked child dispatches.
3. Defines admission uniqueness as the provider/precondition projection key plus a stable semantic dispatch fingerprint, independent of logical-dispatch ID.
4. Removes volatile live-membership digest from retry identity. Membership digest remains receipt evidence and cannot by itself authorize redispatch.
5. Adds one ledger transaction/CAS authority supporting ordinary reservation and atomic route-transition-plus-child-reservation. NBF-01 owns the primitive; NBF-02 owns request-specific use.
6. Defines restart and crash reconciliation before, during, and after route transitions, reservation commits, metadata-cache updates, and final launch.
7. Freezes receipt-context transport from admission through launcher, resident, watchdog, and wrapper interfaces. In-band worker signals fail closed without resolvable context.
8. Adds explicit observed-worker, observed-external/unknown, and non-worker signal records so missing worker identity is never fabricated.
9. Expands the signal inventory repository-wide. Every worker-killing signal uses the canonical helper; probes, non-worker lifecycle signals, and intentional exclusions are classified and mechanically tested.
10. Defines WBC ordering: pre-admission intent is not a worker attempt; admission occurs before `wbc_dispatch.run`; scheduling conditions consume no WBC attempt or worker outcome.
11. Completes end-to-end scheduling transport through `PhaseResult`, handlers, `auto.py`, and recovery policy with an early breaker bypass.
12. Adds a first-provider-observation hold/probe path. A successful bounded probe supplies the allowlisted durable change required for a second same-route dispatch; time passage alone never authorizes an identical retry.
13. Reconciles all task dependencies, focused tests, synchronization gates, validation commands, and completion criteria with these contracts.

No frozen criterion, model policy, authority boundary, custody rule, delivery rule, or merge checkpoint changes.

## 3. Current-state inventory

| Criterion | Status | Existing basis | Remaining work |
|---|---|---|---|
| 1. Unique admission gate | **Partially satisfied** | `cloud/runtime_attestation.py::require_production_worker_dispatch_runtime` validates seed, manifest generation, dependency interpreter, and seed interpreter. | It has no complete production caller coverage and does not jointly own translation, catalog, family, live membership, source/runtime, timeout, memory, fingerprint, or atomic reservation. Chain admission remains fragmented. |
| 2. Exactly-once launch doors | **Partially satisfied** | `run_step_with_worker` is the public worker entry; nested OMP delegates to `run_omp_step`; babysitter has a managed-launch seam. | Raw preflights and WBC ordering obscure ownership. Door ownership, admission attempts, logical child dispatches, and final launches are not separately proven. |
| 3. Typed death dispositions | **Partially satisfied** | `IncidentLedger.append_event` is the journal write door; cgroup-OOM evidence is partially projected. | No complete disposition schema/helper/CLI/context transport exists. Multiple Python and shell signal paths remain silent or anonymous. |
| 4. Fingerprint redispatch block | **Missing** | Incident projection diagnoses repeated repair attempts after failure. | No stable semantic fingerprint, cross-logical-ID CAS key, single-use changed-precondition consumption, or atomic reservation exists. |
| 5. Joint model admission | **Partially satisfied** | Static catalog validation, model-family classification, and translation exist independently. | No simultaneous spec↔catalog↔family↔live-membership decision exists. Static authorities still accept expired `openrouter/stealth/ox-alpha`. |
| 6. Structural spy | **Missing** | Individual worker and babysitter tests exist. | No production-manifest spy proves chain inclusion, WBC ordering, physical ownership, linked dispatches, or gate-before-launch. |
| 7. Cooldown scheduling | **Partially satisfied** | `memory_cooldown_wait_secs` and post-failure cooldown recovery exist. | Cooldown is not transported as a typed scheduling result through the whole stack and still has post-failure counter-repair behavior. |
| 8. Provider degradation | **Missing** | Retryability classification and configured fallback rotation exist. | No typed post-launch outcome, sustained observation projection, bounded hold/probe, atomic flip-plus-child-reservation, or restart-safe return path exists. |

### Fragmented controls to eliminate or subordinate

- Raw runtime refresh/require and source preflight in `workers/_impl.py`.
- `chain/source_admission.py::worker_launch_preflight` and chain-local launch refusals.
- Standalone memory admission in `handlers/shared.py`.
- OMP static catalog logic separate from live membership.
- Launcher-local spec translation.
- WBC attempt creation before canonical admission.
- Provider fallback handling outside the shared scheduling seam.
- Cooldown repair and counter reset in `auto.py`.
- Death information split among raw signal sites, state summaries, and plan events.
- Repository signal sites not classified as worker kills, probes, non-worker lifecycle signals, or exclusions.

## 4. Frozen control-plane design

### 4.1 Dispatch identities and cardinality

The implementation distinguishes:

- **Dispatch family:** one call into a physical door and its scheduling-controlled sequence of linked route attempts.
- **Logical dispatch:** exactly one admitted attempt for one selected route/spec.
- **Physical door owner:** the single code location binding a dispatch family to `dispatch_with_admission`.
- **Admission attempt:** one invocation of `require_production_worker_dispatch_runtime` for a logical dispatch. Conditions may cause multiple admission attempts before launch.
- **Final launch:** one spawn, backend call, WBC invocation, managed command, or RPC.
- **Linked child dispatch:** a new logical dispatch created after a durable provider recovery or authorized route transition.

Required cardinality:

```text
one dispatch family
  -> exactly one physical door owner
  -> one or more linked logical dispatches
  -> each logical dispatch has one or more admission attempts
  -> each logical dispatch has zero or one final launch
  -> the family has no concurrently active final launches
```

A fallback, recovery retry, or return-to-primary never reuses the old `logical_dispatch_id`. The child contains:

```text
logical_dispatch_id
parent_logical_dispatch_id
authorizing_event_id
dispatch_family_id
physical_door_id
```

Nested OMP has one physical owner in `run_omp_step`. `_impl.py` delegates without independently invoking admission.

“Exactly once” means one physical owner per dispatch family and no more than one final launch per logical dispatch. It does not mean one admission attempt or one route attempt for the whole family.

### 4.2 One chain-inclusive admission authority

`cloud/runtime_attestation.py::require_production_worker_dispatch_runtime` is the only production worker-admission authority.

Before wiring, inventory every production caller of:

- `chain/source_admission.py::worker_launch_preflight`;
- chain-local source/runtime refusal logic;
- `refresh_runtime_launch_seed_for_worker_dispatch`;
- `require_configured_runtime_launch`;
- standalone memory/headroom refusal helpers;
- direct launch construction in `chain/__init__.py`;
- `CommonWorkerDispatchSpec.run` and its callers.

Rules:

- Chain orchestration may prepare inputs and emit pre-admission intent, but cannot authorize or start a worker.
- Retained helpers become non-authoritative validation primitives callable only from the canonical gate.
- A chain-originated worker delegates to a frozen physical door.
- Any newly discovered direct chain launch is refactored to an existing physical door, not made a fourth authority.
- WBC pre-admission intent is explicitly not an attempt start, worker start, failure, or completion.
- Production admission occurs before `wbc_dispatch.run`.
- A scheduling condition consumes no WBC attempt and emits no WBC failure or completion.

The physical final-launch owners remain:

1. Native non-OMP routes in `workers/_impl.py`.
2. Direct and nested OMP routes in `workers/omp.py::run_omp_step`.
3. Babysitter managed launches in `cloud/babysitter/launch.py`.

Chain and WBC are origins/delegation mechanisms, not additional admission authorities.

### 4.3 Typed admission request, decision, and receipt

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
live_membership_resolver
clock
source_runtime_validator
memory_headroom_reader
ledger_projection_reader
ledger_transaction_authority
```

The gate performs:

1. Canonical translation and normalization.
2. Static catalog-row validation.
3. Model-family classification.
4. Exact live provider/model membership validation for OMP routes.
5. Manifest, seed, and interpreter refresh and validation.
6. Source/runtime validation through the retained non-authoritative primitive.
7. Finite, positive, policy-valid timeout validation.
8. Memory/headroom and same-phase/spec cooldown evaluation.
9. Stable semantic dispatch-fingerprint derivation.
10. Atomic reservation, or atomic route-transition-plus-child-reservation, through the ledger transaction authority.
11. Immutable receipt return only after the transaction commits.

Outcome:

```text
WorkerAdmissionReceipt
| SchedulingCondition
| AdmissionRefusal
```

The gate does not sleep, probe, emit retry-wait evidence, invoke a final launch, or recursively call itself.

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
live_membership_digest
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

Live-membership digest is admission evidence, not part of semantic retry identity.

Manifestless development remains explicitly non-production. Production intent, a production manifest, or a configured cloud seed cannot collapse into a development no-op.

Membership command failure, timeout, malformed JSON, ambiguity, provider-read failure, or ledger failure rejects typedly before client, process, WBC attempt, or RPC construction.

### 4.4 Stable semantic dispatch fingerprint and CAS key

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
live-membership digest
timestamps
retry counters
PID/process incarnation
temporary probe observations
```

Admission uniqueness is:

```text
projection key + semantic dispatch fingerprint
```

It is independent of logical-dispatch ID. Concurrent requests with different logical IDs but the same key and fingerprint contend for one reservation.

A membership-digest-only change never bypasses a terminal fingerprint refusal. Membership changes may affect current admission success, but redispatch still requires an allowlisted durable changed-precondition or route-transition authorization.

### 4.5 Changed-precondition contract

A terminal worker disposition records the semantic dispatch fingerprint.

Admission refuses the first proposed redispatch of the same terminal fingerprint unless a later, single-use, allowlisted `changed_precondition` event proves a durable change.

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
- `authorized_route_changed` references a jointly admitted route transition.
- `provider_recovery_verified` references a successful bounded provider probe.
- `verified_repair_committed` includes a repository commit SHA and evidence digest.
- Free-form notes, elapsed time, PID replacement, retry count, and sleep are insufficient.
- The event is later than the terminal outcome it supersedes.
- A receipt names the consumed change event.
- Consumption is atomic with reservation.
- One event cannot authorize two concurrent reservations.

### 4.6 One ledger transaction/CAS authority

NBF-01 adds one transaction/CAS primitive to the incident ledger. It is the sole durable read/compare/append authority for:

- ordinary admission reservation;
- changed-precondition consumption;
- provider observation transitions;
- probe leases and results;
- route-transition-plus-child-reservation;
- return-to-primary-plus-child-reservation.

NBF-02 alone owns request-specific admission calls to that primitive.

Ordinary reservation transaction:

1. Lock/load the current projection version.
2. Read the latest terminal fingerprint, active reservation, and eligible changed-precondition event.
3. Compare using projection key plus semantic fingerprint.
4. Reject an unchanged terminal fingerprint without an unused valid change.
5. Reject an active duplicate reservation even if logical IDs differ.
6. Consume the valid change event when required.
7. Append `admission_reserved`.
8. Return the receipt data after commit.

Route transition transaction:

1. Validate the proposed child through the canonical gate up to its transactional step.
2. Lock/load the route projection.
3. Verify the authorizing observation/probe/transition preconditions.
4. Consume the authorizing event.
5. Append `provider_route_flip` or `provider_route_return`.
6. Append/reserve the linked child dispatch in the same transaction.
7. Return one receipt containing both event identities after commit.

No provisional receipt escapes before commit.

Failure to lock, append, compare, consume, or commit is fail-closed and produces no launch.

### 4.7 Crash and replay semantics

Incident-ledger events are authoritative. Fallback metadata is a derived cache written only after transaction commit.

Crash behavior:

- Before transaction: no reservation or transition exists; retry reloads state.
- During transaction: no partial event set is visible.
- After commit but before cache write: replay reconstructs the committed route and reservation.
- After cache write: cache version must match the ledger projection.
- Cache mismatch or missing cache triggers deterministic replay.
- A committed reservation without a final-launch outcome is unresolved. Restart reconciliation checks the running receipt/process incarnation; it never blindly launches again.
- If positive evidence proves no worker was launched, reconciliation appends a typed reservation-release/change event before a new reservation.
- If launch state is ambiguous, admission fails closed pending typed observed-death or operator-supported durable evidence.
- A losing concurrent writer reloads and does not duplicate a reservation, flip, return, probe, or launch.

Required crash injection boundaries:

```text
before lock
after read/before compare
after compare/before append
after transition append/before reservation append
after atomic commit/before cache update
after cache update/before final launch
after final launch/before outcome append
```

The transition and child reservation are one atomic unit; the apparent boundary between their appends is tested to prove it cannot become externally visible.

### 4.8 Scheduling-condition schema and transport

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
```

Rules:

- `condition_id` is independent of death identity.
- `cause_event_id` references real provider or memory evidence when present.
- `disposition_id` is optional and only references a real recorded worker disposition.
- Provider holds and probe timeouts never invent a disposition.
- Scheduling conditions do not call `record_step_failure`.
- They increment no deterministic-phase, repeated-signature, or recovery-circuit counter.
- They cannot set the plan to `blocked`.
- `PhaseResult` preserves them losslessly through handlers and `auto.py`.
- Handler and `auto.py` routing recognizes scheduling before any failure recording.
- `RecoveryPolicy.classify_with_circuit` performs an early scheduling bypass before recording or consulting a breaker.
- Genuine internal errors, malformed output, schema failures, auth failures, test failures, and other excluded provider classes retain existing failure behavior.

### 4.9 Typed final-launch outcome

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

Rules:

- One exhausted logical dispatch produces one provider observation regardless of internal retry count.
- English stderr is never parsed for scheduling policy.
- Availability and idle-timeout evidence reaches `dispatch_with_admission`, not generic breaker handling.
- Auth, quota, rate limit, unsupported model, context-window, malformed output, schema, and internal errors cannot produce `provider_exhausted`.
- Success and ordinary failure are returned to existing consumers after the shared seam records their canonical outcome.
- Raw provider degradation evidence never reaches `RecoveryPolicy`.

### 4.10 One scheduling owner

`dispatch_with_admission` is the only owner of pre-launch and post-launch scheduling.

For each logical dispatch it:

1. Invokes the canonical gate.
2. On an admission receipt, verifies the committed reservation.
3. Invokes the final-launch closure at most once for that logical dispatch.
4. Consumes the typed `DispatchOutcome`.
5. Returns success or ordinary terminal failure normally.
6. For `provider_exhausted`, appends exactly one provider observation and derives the route projection.
7. Emits idempotent scheduling-condition and `retry_wait` evidence where scheduling applies.
8. Uses injected clock, sleeper, and bounded probe.
9. Reruns the complete gate after a pre-launch condition resolves.
10. Creates a linked child logical dispatch only after a single-use recovery or route authorization exists.
11. Never recursively re-enters a physical door and never creates a second scheduler.

Memory cooldown:

- Active same-phase/spec cgroup-OOM cooldown returns `memory_cooldown`.
- The seam waits within the bounded family deadline and reruns the entire gate.
- No final launch occurs before a receipt.

First provider observation:

- One exhausted availability/idle-timeout outcome appends one observation.
- It does not yet mark the provider degraded or rotate.
- The seam emits `provider_observation_wait`, holds until the bounded probe window, and acquires the single probe lease.
- A failed probe remains a scheduling condition and launches no worker.
- A successful probe appends `provider_recovery_verified`, supplying the single-use durable change needed for a linked child dispatch.
- Time passage alone cannot authorize the child.

Second matching observation:

- A second exhausted linked dispatch with the same projection key and precondition identity establishes `provider_degraded`.
- The seam either performs an atomic configured-route transition plus child reservation or enters scalar hold/probe.
- The failed logical dispatch is never relaunched under its old ID.

Scheduling-window expiry:

- Returns the current serialized scheduling condition.
- Does not synthesize a worker failure, WBC completion, or blocked plan.
- Resume re-enters the same shared seam from ledger state.

`auto.py`, `RecoveryPolicy`, fallback code, handlers, and physical doors do not sleep, probe, reset counters, or independently rotate.

### 4.11 Provider/precondition projection

One incident-ledger projection owns provider health, route state, fingerprint changes, change consumption, reservations, and retry authorization.

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
provider_route_flip
provider_route_return
provider_success
changed_precondition
admission_reserved
reservation_reconciled
```

Rules:

1. One exhausted logical dispatch creates one observation.
2. Internal retry chatter changes only evidence fields.
3. Matching requires phase, selected spec, projection key, and precondition identity.
4. Success or an allowlisted durable change resets the streak.
5. Two consecutive matching observations establish degradation.
6. Excluded error classes never enter the degradation projection.
7. Duplicate observation IDs do not increment twice.
8. All transitions use expected projection version.
9. One caller holds a probe lease.
10. Restart replay yields identical state.
11. Fallback metadata mirrors the projection and is never authoritative.
12. `_advance_configured_spec_fallback` remains the only configured fallback-selection door.

### 4.12 Fallback, scalar hold, and return-to-primary

Configured non-execute fallback:

1. Two matching observations establish `provider_degraded`.
2. `_advance_configured_spec_fallback` proposes the next configured target.
3. The canonical gate jointly validates the target.
4. Rejection produces no route transition, reservation, WBC attempt, client, or RPC.
5. Acceptance atomically records the route flip and reserves a linked child logical dispatch.
6. The child receipt names the parent dispatch and transition event.
7. Cache metadata updates only after commit.
8. The shared seam performs the child’s one final launch.

Scalar pin:

1. Never widen to historical last-known-good.
2. Append a bounded hold and return a scheduling condition.
3. Acquire one probe lease after `retry_not_before`.
4. Run one injected, bounded, no-tool probe.
5. Failed probes append evidence and remain scheduling.
6. Passed probes append `provider_recovery_verified`.
7. Exactly one linked child reservation may consume that event.

Return to primary:

1. Do not probe on every loop.
2. Projection deadline and lease control probing.
3. A passing probe precedes joint admission.
4. Admission atomically records `provider_route_return` and reserves a linked child.
5. Route cache changes only after commit.
6. The old fallback logical dispatch is not reused.

Execute and loop-execute:

- Fallback advancement remains prohibited.
- `ExecuteFallbackUnsafe` semantics remain.
- Bounded hold/probe scheduling is allowed.
- No provider rotation creates a second execution attempt.

### 4.13 Receipt context transport

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
- Subprocess and managed-command boundaries receive a canonical serialized context reference through the existing command/environment construction seam.
- Running receipts persist the reference before supervision begins.
- Resident worker state retains it across same-session follow-up and termination ladders.
- Watchdog and restack code resolve it from the running receipt and ledger, verifying plan, receipt, PID, and process-start identity.
- Shell wrappers pass the resolved context to the disposition CLI.
- The standalone launcher accepts the context reference through its invocation contract.
- Context cannot be reconstructed from model name, PID, current directory, or free-form text.
- Missing or inconsistent context prevents an in-band worker signal.
- Already-observed dead processes use an observed schema and never fabricate missing receipt data.

### 4.14 Canonical signal and disposition contracts

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

It is recorded through the same helper when a repository signal intentionally targets infrastructure rather than a worker.

Signal rules:

- In-band worker and non-worker lifecycle appends complete before signaling.
- Append failure prevents the signal and returns non-success.
- TERM and KILL ladder steps have distinct deterministic IDs and records.
- Observed-death append completes before orphan cleanup or redispatch authorization.
- State summaries are derived projections, not a second authority.
- `kill -0` and equivalent checks are probes, not dispositions.

### 4.15 Shell disposition CLI

Interface:

```bash
python -m arnold_pipelines.megaplan.incident.disposition record \
  --ledger-root "$LEDGER_ROOT" \
  --json-stdin
```

Contract:

- Reads exactly one UTF-8 JSON object.
- Validates one of the canonical disposition schemas.
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

### 4.16 Repository-wide signal inventory

Generate a machine-readable inventory for every real signal site in the repository, including at least:

- `skills/subagent-launcher/launch_omp_agent.py`
- `skills/subagent-launcher/fan.py`
- `skills/subagent-launcher/fan_process.py`
- `resident/subagent.py`
- `resident/agent_loop.py`
- `cloud/operator_control.py`
- `cloud/wrappers/arnold-watchdog`
- `cloud/wrappers/arnold-heartbeat`
- `cloud/systemd/ensure-megaplan-watchdog`

Each row contains:

```text
source_file
function_or_branch
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

Classification:

- Worker-killing real signal: route through `WorkerDisposition`.
- Already-dead observation: route through `ObservedProcessDeath`.
- Non-worker lifecycle signal: route through `NonWorkerSignalDisposition`.
- Probe: mechanically prove it cannot signal.
- Intentional exclusion: narrow, documented, mechanically tested, and accepted by the Sol Oracle.

No worker-killing site may be excluded merely because it lies outside the initially named files.

Sustained-proof rules apply to watchdog wedge, hung child, repair reaping, ensure-restack, and any analogous supervision kill:

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
- place scheduling loops in the gate, `auto.py`, `RecoveryPolicy`, handlers, or fallback code;
- return raw provider degradation evidence to generic breaker handling;
- parse English stderr for provider policy;
- treat internal retries as multiple provider observations;
- include live-membership digest or other volatile observations in semantic retry identity;
- use different logical IDs to evade reservation uniqueness;
- transition a route separately from child reservation;
- treat fallback metadata as an authoritative provider store;
- add a second provider rotator;
- invent a disposition, fingerprint, worker identity, or killer for missing context;
- signal an in-band worker without a resolved admission context;
- claim cgroup OOM without positive evidence;
- signal before the disposition append succeeds;
- treat a one-scan verdict, PID presence, completed marker, or stale timestamp as sustained kill proof;
- permit a free-form note, time passage, sleep, or retry count to bypass fingerprint refusal;
- let a membership read failure become accepted empty membership;
- apply a box-only hotfix absent from the candidate branch.

## 6. Execution batches and tasks

All implementation, focused testing, critique, and independent review work uses GPT-5.6 Luna. Planning, revision, Oracle judgments, and any justified `[XHARD]` task use GPT-5.6 Sol with high reasoning. No task below is `[XHARD]`, and no model switch is authorized without user approval.

### Batch 1 — Contracts, serialization, projections, and ledger CAS

#### NBF-01 — Freeze typed contracts and add the transaction authority

**Classification:** Normal / GPT-5.6 Luna.

**Files and symbols**

- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`
- `arnold_pipelines/megaplan/orchestration/recovery_policy.py`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- New `arnold_pipelines/megaplan/incident/disposition.py`
- Existing fallback metadata schema
- New tests:
  - `test_worker_disposition.py`
  - `test_scheduling_conditions.py`
  - `test_provider_route_projection.py`
  - `test_incident_ledger_transactions.py`

**Work**

- Add `SchedulingCondition` and lossless `PhaseResult` transport.
- Add `DispatchOutcome`.
- Add worker, observed-death, and non-worker disposition schemas.
- Add changed-precondition and stable semantic-fingerprint schemas.
- Add provider/precondition projection events and replay.
- Add one ledger transaction/CAS primitive for ordinary reservation and atomic transition-plus-child-reservation.
- Add strict version checks, one-use event consumption, probe leases, cache reconciliation, and deterministic IDs.
- Add the shell CLI.
- Add early scheduling bypass to recovery classification before breaker accounting.
- Do not implement request-specific admission wiring; that belongs only to NBF-02.

**Acceptance**

- Scheduling round-trips through `PhaseResult`.
- Scheduling reaches recovery classification without recording a failure.
- Three genuine identical internal errors still open the breaker.
- Incomplete dispositions are rejected.
- Observed unknown death cannot claim OOM or fabricate worker identity.
- Non-worker lifecycle signals validate without a worker fingerprint.
- TERM and KILL ladder IDs differ.
- Free-form changed-precondition reasons fail.
- Membership digest is absent from semantic fingerprint.
- Same fingerprint with different logical IDs maps to the same reservation key.
- A change event is single-use.
- Two-process contention yields one reservation winner.
- Atomic route transition and child reservation are never partially visible.
- Lock/append failures fail closed.
- Restart replay and cache repair reproduce exact state.
- CLI acknowledgements and exit codes match the frozen contract.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py \
  tests/arnold_pipelines/megaplan/test_plan_circuit.py
```

**Synchronization point**

The Sol Oracle freezes schemas, fingerprint components, transaction operations, crash semantics, CLI behavior, and serialization before caller work begins.

### Batch 2 — Canonical admission and the sole scheduling seam

#### NBF-02 — Expand admission and implement `dispatch_with_admission`

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01.

**Files and symbols**

- `cloud/runtime_attestation.py`
- Shared dispatch module containing `dispatch_with_admission`
- `chain/source_admission.py`
- `chain/__init__.py`
- `workers/omp.py`
- `arnold/pipeline/model_seam.py`
- `skills/subagent-launcher/launch_omp_agent.py`
- `runtime/memory_headroom.py`
- `handlers/shared.py`
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

**Work**

1. Inventory chain, raw runtime, memory, and WBC callers.
2. Reduce retained helpers to non-authoritative primitives.
3. Add typed request, receipt, refusal, condition, execution-context reference, and request-specific reservation.
4. Normalize model translation ownership.
5. Add injectable `omp models --json` membership resolution.
6. Prove static acceptance and joint rejection of expired `openrouter/stealth/ox-alpha`.
7. Move source/runtime, timeout, memory, fingerprint, and reservation checks into the gate.
8. Use the NBF-01 CAS primitive for ordinary reservations.
9. Implement `dispatch_with_admission` for both admission conditions and typed post-launch outcomes.
10. Create linked logical dispatch IDs for recovery, fallback, and return attempts.
11. Implement first-observation hold/probe and single-use recovery authorization.
12. Use atomic transition-plus-child-reservation for route changes.
13. Emit idempotent scheduling and retry-wait evidence.
14. Wire handler and `auto.py` early scheduling return paths.
15. Delete cooldown-specific counter repair/reset logic.
16. Define execution-context propagation at Python, subprocess, managed-command, and running-receipt boundaries.

**Acceptance**

- One receipt proves all frozen admission invariants.
- Chain has no independent authorization caller.
- Production cannot pass without source/runtime/seed/interpreter proof.
- Invalid timeout values fail typedly.
- Static `ox-alpha` acceptance remains while joint admission rejects it before client construction.
- Membership failure rejects typedly.
- Same semantic fingerprint with different logical IDs yields one reservation.
- Digest-only change does not authorize redispatch.
- One valid changed event authorizes one reservation and is named by the receipt.
- Cooldown causes multiple admission attempts and zero launches before expiry.
- Scheduling expiry reaches `PhaseResult` without failure accounting or `blocked`.
- First provider observation cannot relaunch merely because time elapsed.
- Passed probe creates one consumable recovery event.
- Fallback creates a linked child ID.
- Atomic route transition and child reservation share one commit.
- No raw scheduling evidence reaches generic recovery policy.
- Execution context is persisted before supervision begins.

**Focused validation**

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/workers/test_omp_adapter.py
```

### Batch 3 — Physical-door wiring, WBC ordering, and structural proof

#### NBF-03 — Wire the three doors and prove linked-dispatch cardinality

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-02.

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
- `test_common_worker_dispatch_wbc.py`

**Work**

- Delete `_impl.py` raw refresh/require/source-preflight blocks.
- Native `_impl.py` binds the shared seam once.
- Nested OMP delegates without outer admission.
- `run_omp_step` binds the shared seam for nested and direct OMP.
- Babysitter binds it before running receipt or managed command.
- Emit optional pre-admission WBC intent only.
- Move admission before `wbc_dispatch.run`.
- Start WBC attempt state only inside the admitted final-launch closure.
- Ensure scheduling consumes no WBC start/failure/complete.
- Keep normal and agent-dispatcher paths identical in ownership.
- Propagate the receipt context into every final-launch boundary.
- Document that checked-in pins are advisory and the canonical gate is authoritative.
- Do not mutate `/workspace/.cloud-hot-env`.

**Structural scenarios**

1. Native non-OMP success.
2. Nested OMP success.
3. Direct OMP success.
4. Babysitter success.
5. Chain-originated success.
6. Admission rejection for each door.
7. Memory cooldown with multiple attempts and one eventual launch.
8. First provider observation, probe wait, and no unauthorized relaunch.
9. Configured fallback with parent and child IDs, one launch each.
10. Atomic transition rejection with no child launch.
11. WBC ordered trace:
    - optional intent;
    - admission reservation;
    - WBC attempt start;
    - final launch;
    - typed outcome.
12. Scheduling WBC trace:
    - intent;
    - scheduling condition;
    - no WBC attempt start/failure/complete.
13. No `MEGAPLAN_MOCK_WORKERS=1`; only final spawn/RPC/WBC/managed-command seams are replaced.

**Acceptance**

- One physical owner per dispatch family.
- One final launch maximum per logical dispatch.
- Fallback child has a new logical ID linked to the transition.
- No recursive physical-door entry occurs.
- Nested OMP has no outer owner.
- Ordered traces prove reservation before WBC attempt and final launch.
- Door removal, duplicate outer gate, chain bypass, or pre-admission WBC start fails tests.
- The three door files contain no raw refresh/require calls.

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

The Sol Oracle reviews caller inventory, WBC ordering, physical-owner traces, linked child identities, transition atomicity, nested OMP ownership, chain bypass tests, and the raw-preflight scan.

### Batch 4 — Python worker deaths and execution-context closure

#### NBF-04 — Route all repository Python signal paths through the helper

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01, NBF-02, and NBF-03’s final context propagation contract.

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
- Inventory and classify fan, agent-loop, operator-control, and all other Python signal sites.
- Route worker kills through `WorkerDisposition`.
- Route non-worker lifecycle signals through `NonWorkerSignalDisposition`.
- Mechanically test probes and narrow exclusions.
- Convert positive OOM orphan evidence into `ObservedProcessDeath`.
- Record unknown dead-process observations without fabricated context.
- Prevent in-band signal when required context cannot resolve.

**Acceptance**

- Every Python real signal has an inventory row.
- Every worker signal has a resolvable receipt/fingerprint.
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

### Batch 5 — Shell supervision and repository-wide signal closure

#### NBF-05 — Instrument shell signals and prove sustained supervision

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-04.

**Files and symbols**

- `cloud/wrappers/arnold-watchdog`
- `cloud/wrappers/arnold-heartbeat`
- `cloud/systemd/ensure-megaplan-watchdog`
- Any additional shell signal site found by the repository-wide inventory
- `incident/disposition.py` CLI
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

For probes/exclusions:

- Classify repository-wide.
- Mechanically prove probes cannot signal.
- Give exclusions a narrow reason and direct regression test.

Additional rules:

- PID, process-start, or progress changes reset confirmation.
- TERM→KILL produces two records.
- The ensure script resolves the active installed source/runtime.
- Cross-invocation confirmation state includes watchdog/container incarnation.
- CLI or context failure leaves a live victim unsignaled.

**Machine-readable artifact**

```text
source_file
function_or_branch
signal_or_probe
subject_class
worker_kill
killer_kind
context_resolver
two_scan_required
two_scan_owner
disposition_test_id
failure_order_test_id
exclusion_reason
```

**Acceptance**

- Every repository real signal is classified.
- Every worker kill is helper-routed.
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
pytest -q \
  tests/cloud/test_watchdog_dispositions.py \
  tests/cloud/test_watchdog_wrappers.py \
  tests/cloud/test_repository_signal_inventory.py
```

**Synchronization point**

The Sol Oracle receives the complete repository-wide inventory and ordering evidence. An unclassified real signal, fabricated worker identity, unresolved worker context followed by a signal, or signal reachable after append failure blocks the batch.

### Batch 6 — Complete cooldown and provider resilience

#### NBF-06 — Complete T7/T8 through the shared seam and existing fallback door

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01 through NBF-03.

NBF-06 first completes structured availability evidence production. Route work cannot infer provider state from stderr.

**Files and symbols**

- `fallback_chains.py`
- `workers/_impl.py`
- `workers/omp.py`
- `handlers/shared.py`
- `orchestration/phase_result.py`
- `orchestration/phase_result_classify.py`
- `orchestration/recovery_policy.py`
- `auto.py`
- `incident/ledger.py`
- `incident/disposition.py`
- New `test_provider_scheduling_conditions.py`
- Existing fallback, phase-result, memory, auto, and execution-policy suites

**Substep A — Structured `DispatchOutcome` producers**

- Export one typed exhausted-dispatch observation from OMP and non-OMP.
- Include logical ID, phase/spec, retryability class, internal attempt count as evidence, terminal evidence ID, and precondition identity.
- Prove internal retries count once.
- Prove excluded error classes return ordinary failures.

**Substep B — End-to-end scheduling propagation**

- Preserve scheduling serialization through handler and `auto.py`.
- Bypass failure recording and all breakers before classification.
- Remove remaining scheduling-specific counter repair.
- Prove scheduling-window expiry cannot set `blocked`.

**Substep C — Provider observations and recovery**

- Append first observation and enter bounded hold/probe.
- Require passed probe plus single-use recovery event before a same-route child dispatch.
- Append the second matching observation when that child exhausts.
- Establish `provider_degraded` only after two observations.
- Use `_advance_configured_spec_fallback` only to select a configured target.
- Jointly admit the target.
- Atomically append route transition and reserve the linked child.
- Use scalar hold/probe without widening.
- Use the same atomic process for return to primary.
- Preserve execute/loop-execute fallback prohibition.

**Acceptance**

- One exhausted dispatch creates one observation.
- One observation does not degrade or flip.
- Time passage alone cannot launch a second identical attempt.
- Failed probe launches nothing.
- Passed probe authorizes one linked child.
- Two matching observations establish degradation.
- Success or durable changed precondition resets streak.
- Configured alternate selection uses only the existing fallback door.
- Target rejection produces no transition, child reservation, or RPC.
- Flip and child reservation are crash-atomic.
- Scalar pin never widens.
- Probe leases prevent hammering.
- Return-to-primary transition and child reservation are atomic.
- Scheduling changes no breaker and cannot block.
- Genuine repeated internal errors still open their breaker.
- Execute fallback remains unsafe and prohibited.
- Restart, two-process races, and crash injection reproduce one route and at most one child reservation.
- Ledger-14 cannot create an unbounded retry or invalid-transition cascade.

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
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py
```

**Synchronization point**

The Sol Oracle judges T7/T8 jointly. A second scheduling owner, raw provider evidence reaching breakers, stderr policy parsing, unchanged redispatch, non-atomic route transition, independent provider store, or rotation outside the existing fallback selector is a rejection.

### Batch 7 — Fresh-base integration, review, and guarded delivery

#### NBF-07 — Rebase, validate, independently review, and push

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
5. Run the authoritative broad validation exactly once after rebase.
6. Capture:
   - source and candidate SHAs;
   - exact validation result;
   - dispatch-family, logical-ID, parent-ID, door, admission-attempt, reservation, WBC, and final-launch traces;
   - chain caller inventory;
   - fingerprint and cross-logical-ID CAS races;
   - route-transition crash matrix;
   - receipt-context propagation evidence;
   - repository-wide signal inventory;
   - CLI and record-before-signal results;
   - provider replay/interleaving results;
   - breaker snapshots;
   - negative raw-preflight scan;
   - shell syntax results;
   - criterion completion table.
7. Assign one GPT-5.6 Luna independent reviewer to the complete evidence.
8. Submit completion to the GPT-5.6 Sol Oracle.
9. Push `megado-nbf-guard-0826` to origin.
10. If rebase rewrote a published branch, verify its remote tip and use `--force-with-lease`, never unguarded force.
11. Stop before merging and request explicit user approval.

## 7. Task model classification

| Task | Classification | Rationale |
|---|---|---|
| NBF-01 contracts/CAS | Normal / Luna | Schemas and transaction behavior are frozen with deterministic tests. |
| NBF-02 admission/scheduler | Normal / Luna | One authority composes existing primitives under explicit contracts. |
| NBF-03 door/WBC wiring | Normal / Luna | Ordering and cardinality have structural positive and negative oracles. |
| NBF-04 Python dispositions | Normal / Luna | Context propagation and signal classes are fully specified. |
| NBF-05 shell/inventory | Normal / Luna | One CLI, one helper, explicit classifications, and stubbed ordering tests bound the work. |
| NBF-06 T7/T8 | Normal / Luna | Typed outcome production and route transitions have fixed ownership and state rules. |
| NBF-07 integration | Normal / Luna | Mechanical rebase, validation, review, and guarded push. |

No task meets the exceptional `[XHARD]` threshold. No additional architectural research is required.

## 8. Open questions and assumptions

### User-authority checkpoint

Merging `megado-nbf-guard-0826` into `main` requires explicit user approval after completion review and branch push. This does not block implementation.

### Implementable assumptions

- Two-scan confirmation applies to sustained supervision judgments, including wedge, hung-child, repair reaping, ensure-restack, and analogous repository worker-kill paths.
- Explicit owner-requested termination and elapsed timeout have direct causal evidence but still require record-before-signal.
- One exhausted logical dispatch is one provider observation.
- A second same-route dispatch requires a passed probe and consumed `provider_recovery_verified` event.
- Live-membership digest is evidence, not retry identity.
- Last-known-good never widens a scalar pin.
- Existing static `ox-alpha` rows remain available for the discriminating test.
- Fake clocks, probes, ledgers, processes, RPCs, signals, WBC seams, and two-process fixtures provide sufficient structural proof.
- `/workspace/.cloud-hot-env` remains untouched.
- Repository-wide signal inventory is bounded verification of the frozen “all terminate sites” criterion, not unrelated product expansion.
- No live marathon or box mutation is required.

## 9. Effort and huge-run determination

| Batch | Estimate |
|---|---:|
| Contracts, projection, and CAS | 1.5–2 days |
| Admission and shared scheduling seam | 2–2.5 days |
| Door wiring and WBC structural proof | 1–1.5 days |
| Python and shell disposition closure | 2.5–3 days |
| T7/T8 provider scheduling | 2.5–3 days |
| Rebase, validation, review, delivery | 1 day |
| **Total** | **10.5–13 days** |

**Huge-run determination: NO.** The work remains a bounded, approximately two-week plan with explicit synchronization gates and does not require an epic.

## 10. Validation and completion matrix

| Criterion | Required scenario | Required evidence | Passing condition |
|---|---|---|---|
| 1. Unique admission | Runtime, chain, WBC, and caller-inventory suites | Receipt and ordered intent/gate traces | Only the canonical gate authorizes workers; chain/WBC helpers cannot. |
| 2. Exactly-once doors | Native, nested/direct OMP, babysitter, chain, fallback | Family/door/logical-ID/final-launch trace | One physical owner; each linked logical dispatch launches at most once. |
| 3. Typed deaths | Repository-wide Python/shell inventory | Context resolution, ledger rows, CLI acknowledgement, ordering | Every worker kill records first; missing context or append failure prevents signal. |
| 4. Fingerprint block | Same fingerprint across different logical IDs, digest-only change, valid durable change | CAS winner and consumed event | One reservation across IDs; digest-only retry rejected; one durable change authorizes one reservation. |
| 5. Joint model admission | Static `ox-alpha` acceptance and live rejection | Static and joint outcomes | Joint live admission rejects before WBC/client/RPC. |
| 6. Structural spy | Door removal, duplicate gate, chain bypass, WBC prestart | Ordered traces and negative tests | Every bypass or ordering violation fails structurally. |
| 7. Cooldown scheduling | Repeated conditions, expiry, serialized return | Condition payload, retry-wait IDs, breaker/WBC snapshots | Shared seam reruns admission; no failure, WBC attempt, block, or premature launch. |
| 8. Provider degradation | First observation, probe, second observation, flip, scalar hold, restart, race, return, execute ban | Typed outcomes, projection events, atomic child reservation | Sustained evidence only; linked IDs; atomic transitions; no breaker leakage or unchanged retry. |
| Crash safety | Injection around every transaction/cache/launch boundary | Replay state and launch count | No partial transition, duplicate child reservation, or blind relaunch. |
| Signal closure | Repository-wide inventory | One row per real signal/probe | No unclassified worker kill or untested exclusion. |

## 11. Authoritative post-rebase validation

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
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
  tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py \
  tests/arnold_pipelines/megaplan/test_fallback_chains.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py \
  tests/arnold_pipelines/megaplan/test_gpt56_execution_policy.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

```bash
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-heartbeat
bash -n arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog
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

The reviewed machine-readable signal inventory, not a raw grep count, owns final signal classification because liveness probes and intentional non-worker lifecycle signals are legitimate.

## 12. Completion conditions

The work is complete only when:

- criteria 1–8 have PASS evidence;
- all 42 existing runtime-attestation tests remain green;
- one chain-inclusive admission authority remains;
- chain and WBC cannot authorize or start a worker before admission;
- WBC intent, admission, attempt start, launch, and outcome ordering is proven;
- physical ownership and logical-dispatch cardinality are separately proven;
- every fallback/recovery attempt uses a linked child logical ID;
- no logical dispatch performs more than one final launch;
- every final-launch closure returns typed `DispatchOutcome`;
- raw provider scheduling evidence never reaches generic failure handling;
- semantic CAS uniqueness is independent of logical ID;
- volatile membership digest cannot bypass retry refusal;
- valid changed-precondition events are allowlisted and consumed once;
- route transition and child reservation are crash-atomic;
- restart reconciliation cannot blindly relaunch an unresolved reservation;
- scheduling serializes end to end and bypasses all failure/breaker accounting;
- cooldown and provider conditions cannot set `blocked`;
- genuine repeated internal errors still open breakers;
- receipt context reaches launcher, resident, watchdog, and wrapper boundaries;
- missing in-band worker context prevents signaling;
- observed and non-worker records never fabricate worker identity;
- every repository real signal is classified;
- every worker-killing signal is preceded by a successful canonical append;
- append/CLI failure leaves live victims unsignaled;
- sustained supervision kills require two matching scans;
- static `ox-alpha` acceptance and joint live rejection are proven;
- configured fallback selection uses only `_advance_configured_spec_fallback`;
- scalar pins hold/probe without widening;
- execute and loop-execute fallback prohibition remains;
- wrapper syntax and raw-preflight scans pass;
- fresh fetch/rebase and the authoritative suite succeed;
- custody commits and protected artifacts survive;
- the independent Luna reviewer and Sol Oracle accept completion;
- the candidate branch is pushed to origin;
- no box-only behavior change exists;
- no merge to `main` occurs without explicit user approval.

## 13. Revised settled-plan readiness

**Disposition: READY_FOR_FRESH_LUNA_SETTLED-PLAN WAVE.**

The W2 material findings are resolved at contract and task level:

- fallback attempts are linked child dispatches with one launch each;
- the shared seam owns typed post-launch provider outcomes;
- reservation uniqueness uses stable semantic identity across logical IDs;
- route transitions and child reservations are one atomic ledger operation;
- crash and restart boundaries are explicit;
- worker context is closed over every launch and signal boundary;
- observed and non-worker cases remain truthful without fabricated identity;
- the signal inventory is repository-wide;
- NBF-01 owns the CAS primitive while NBF-02 alone owns request-specific reservation;
- WBC cannot record an attempt before admission;
- scheduling propagates losslessly and bypasses breakers end to end.

The design retains one scheduling owner, one ledger transaction authority, one provider/precondition projection, one fallback-selection door, and one signal helper. No material evidence question or user-policy decision remains. A fresh complete GPT-5.6 Luna settled-plan sense-check is mandatory before freezing this snapshot; the later user checkpoint remains merge approval only.

STABILITY: STABLE

## Prior accepted/rejected W1 dispositions

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

## Prior accepted/rejected W2 dispositions

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

This is a fresh whole-plan review after the second material revision. Evaluate
every section and criterion. Do not repeat a prior objection without new evidence.
Do not widen scope. Model assignment is user-selected GPT-5.6 Luna (normal).
Every finding must include a North Star disposition.

Find only material execution-order, synchronization, concurrency/restart,
propagation, physical-door, or test-evidence gaps. Validation must stay
proportionate.

Return `PASS_SEQUENCE_AND_VERIFICATION` or ranked `SEQ3-N` findings with
materiality, exact plan/source/test evidence, smallest correction, criterion
impact, and North Star disposition. Under 700 words.
