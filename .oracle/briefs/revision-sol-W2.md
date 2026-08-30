# Sol full-plan revision brief — settled-plan W2

You are the read-only Planner/Revision owner. Return only the complete revised
Markdown body for .oracle/plan.md. Do not edit files or run mutating commands.

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

## Immutable plan v2

SHA-256: d341a71cf9b15766a35cd2cafd9d6e89f5ef2a2afc5d386fd2ce9c2bda639fdd

# Plan — Typed NBF worker admission, disposition, and scheduling control plane

## 1. Planning basis and custody

This revision incorporates every material finding accepted by the W1 Oracle synthesis and none of the rejected findings.

- Branch: `megado-nbf-guard-0826`
- Planning HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Immutable source base: `origin/main` at `798c50619204010ed3f4297fbb57988fe9381924`
- Immutable plan-v1 SHA-256: `770c61d4c63e1af0af1c92630fbce3ccdf956d66250c8134cb4db00c5b3dcb69`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Branch state at planning: six commits ahead of the source base, including the resumed-custody commit.
- Protected untracked artifact: `.oracle/briefs/planner-sol.md`
- Earlier protected evolution artifacts are preserved in branch history.
- `.oracle/tasklist.md` is foreign onboarding-run evidence and remains excluded.
- `tests/cloud/test_runtime_attestation.py` contains 42 existing tests.
- No files were edited and no mutating commands or tests were run by the read-only revision owner.
- The known machine-readable live membership surface remains `omp models --json`. Read or schema failures must become typed admission refusals, never empty-catalog acceptance.

The source update, custody requirements, and this revision do not widen scope or authorize a merge to `main`.

## 2. Revision delta from immutable plan v1

This revision makes the following material corrections:

1. Makes chain admission explicitly subordinate to the same canonical admission authority. Every production caller of `worker_launch_preflight` and every chain-local launch refusal must be inventoried; retained helpers become non-authoritative primitives callable only by the canonical gate.
2. Separates three counts:
   - one physical door owner per logical dispatch;
   - one or more admission attempts while scheduling conditions resolve;
   - zero or one final launch.
3. Introduces one shared `dispatch_with_admission` seam as the sole owner of scheduling-condition evidence, bounded waiting/probing, injected sleep, and complete admission reruns.
4. Keeps `require_production_worker_dispatch_runtime` free of scheduling-loop behavior. It returns an admitted receipt or typed scheduling condition, or raises a terminal typed refusal.
5. Removes synthetic death identity from scheduling. Scheduling conditions have their own condition identity and may reference a real cause or disposition, but never fabricate a worker death.
6. Freezes the complete in-band and observed-death disposition contracts, including typed enums, required fields, ledger semantics, CLI invocation, exit codes, and record-before-signal behavior.
7. Defines a single ledger-backed projection for terminal fingerprints, changed preconditions, provider observations, route transitions, holds, probes, and return-to-primary. Existing fallback metadata is its cache; there is no second provider store or rotator.
8. Freezes the changed-precondition allowlist and requires every admitted retry to reference the accepted change event.
9. Defines atomic replay/concurrency rules and provider route transitions, including restart recovery and interleaving behavior.
10. Corrects task dependencies: NBF-04 depends on the final NBF-02 receipt/fingerprint contract; NBF-06 owns and tests structured availability-evidence propagation before implementing route transitions.
11. Strengthens shell verification with stubbed disposition and signal primitives, failure-order tests, and a machine-readable signal-site inventory.

No frozen criterion, user authority boundary, model pin, custody rule, or delivery constraint changes.

## 3. Verified current-state inventory

| Criterion | Status | Current evidence | Remaining gap |
|---|---|---|---|
| 1. Unique admission gate | **Partially satisfied** | `cloud/runtime_attestation.py::require_production_worker_dispatch_runtime` validates seed, manifest generation, dependency interpreter, and seed interpreter. `chain/source_admission.py::worker_launch_preflight` separately validates source/runtime state. | The canonical gate has no production callers and does not yet jointly own translation, catalog, family, live membership, timeout, memory, fingerprint, or changed-precondition validation. Chain callers and chain-local raises remain an independent authority until inventoried and subordinated. |
| 2. Exactly-once wiring | **Partially satisfied** | `workers/_impl.py::run_step_with_worker` is the public orchestration entry. Nested OMP delegates to `workers/omp.py::run_omp_step`. Babysitter launches through `cloud/babysitter/launch.py`. | Raw `_impl.py` preflights, chain-local admission, and the standalone memory gate must be removed or reduced to primitives. Door ownership, admission-attempt counts, and final-launch counts are not yet distinguished. |
| 3. Typed death dispositions | **Partially satisfied** | `IncidentLedger.append_event` is the canonical journal write door. `auto.py::_build_worker_death_record` records partial cgroup-OOM evidence. | No complete `worker_disposition` schema/helper/CLI exists. Launcher, resident, watchdog, restack, and orphan paths remain unjoined or anonymous. |
| 4. Fingerprint redispatch block | **Missing** | Projection code diagnoses repeated repair attempts after multiple failures. | No canonical dispatch fingerprint, atomic terminal-fingerprint check, allowlisted changed-precondition event, admission reservation, or receipt reference exists. |
| 5. Joint model admission | **Partially satisfied** | OMP parsing/static catalog validation, model-family classification, and launcher translation exist separately. Static authorities accept expired `openrouter/stealth/ox-alpha`. | Translation is duplicated and no joint live-membership decision exists. |
| 6. Structural spy | **Missing** | Individual runtime, OMP, WBC, and babysitter tests exist. | No production-manifest spy proves chain inclusion, physical door ownership, attempt counts, gate-before-launch ordering, or nested OMP exactly-once ownership. |
| 7. Cooldown scheduling | **Partially satisfied** | `memory_cooldown_wait_secs` and `auto.py`’s cooldown refusal handling exist. | Cooldown remains a post-failure exception/reset path. There is no typed shared scheduling loop, injected clock/sleeper, or complete gate rerun owned by one seam. |
| 8. Provider degradation | **Missing** | Retryability classification, configured fallback advancement, and fallback observability exist. | There is no two-observation provider projection, typed scheduling condition, scalar hold/probe, restart-safe route state, joint-admitted flip, or return-to-primary transition. |

### Existing duplicate or fragmented control paths

- Raw runtime refresh/require and source admission in `_impl.py`.
- `chain/source_admission.py::worker_launch_preflight` plus chain-local raises and callers in `chain/__init__.py`.
- Memory selection/refusal in `handlers/shared.py`.
- OMP grammar/static catalog in `workers/omp.py`.
- Launcher-local prefix translation in `skills/subagent-launcher/launch_omp_agent.py`.
- Repeated-failure diagnosis in incident projection without pre-launch prevention.
- Worker death information split among state projections, plan events, and raw signal branches.
- Cooldown repair in `auto.py` after failure accounting.
- Provider fallback metadata without a canonical ledger-derived health/route projection.

## 4. Frozen control-plane design

### 4.1 Dispatch terminology and cardinality

The implementation and its tests use three distinct units:

- **Logical dispatch:** one orchestration request to run a phase/spec.
- **Physical door ownership:** the one code location responsible for invoking `dispatch_with_admission` for that logical dispatch.
- **Admission attempt:** one invocation of `require_production_worker_dispatch_runtime`. A logical dispatch may require multiple attempts while a typed scheduling condition remains active.
- **Final launch:** the final spawn, backend call, or RPC. A logical dispatch produces at most one final launch.

Required cardinality:

```text
one logical dispatch
  -> exactly one physical door owner
  -> one or more admission attempts
  -> zero final launches while conditions remain active
  -> at most one final launch after an admission receipt
```

“Exactly once” in criteria 2 and 6 means exactly one physical door owner and at most one final launch. It does not require exactly one admission attempt during cooldown or provider recovery.

Nested OMP has one physical owner in `run_omp_step`; `_impl.py` delegates without independently invoking admission.

### 4.2 One chain-inclusive admission authority

`cloud/runtime_attestation.py::require_production_worker_dispatch_runtime` is the only production admission authority.

Every production caller of these symbols must be inventoried before wiring:

- `chain/source_admission.py::worker_launch_preflight`;
- chain-local source/runtime refusal logic;
- `refresh_runtime_launch_seed_for_worker_dispatch`;
- `require_configured_runtime_launch`;
- standalone memory/headroom refusal helpers;
- any direct worker-launch construction in `chain/__init__.py`.

The resulting rule is:

- A genuine worker launch reaches one of the frozen physical worker doors and therefore the canonical admission function.
- Chain orchestration may prepare source/runtime inputs, but it may not independently authorize a worker.
- `worker_launch_preflight`, if retained, becomes a non-authoritative validation primitive invoked only from the canonical admission function. It cannot issue an admission receipt and has no production launch caller.
- If inventory reveals a chain path that directly creates a worker rather than delegating to the known doors, it must be refactored to one of those doors. It must not become a fourth admission implementation.
- Structural tests must prove a chain-originated dispatch cannot bypass the canonical gate.

The three final-launch doors remain:

1. Non-OMP routes in `workers/_impl.py`.
2. OMP backend entry in `workers/omp.py::run_omp_step`, including nested `_impl.py` delegation.
3. Babysitter pre-managed-launch in `cloud/babysitter/launch.py`.

Chain orchestration is covered as an origin/delegation path, not accepted as a separate admission authority.

### 4.3 Typed admission request, outcome, and receipt

The canonical function receives a typed `WorkerAdmissionRequest` containing:

```text
plan_id
phase
logical_dispatch_id
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
latest_projection_version
production_intent
```

Injected adapters provide:

```text
live_membership_resolver
clock
source_runtime_validator
memory_headroom_reader
ledger_projection_reader
atomic_admission_reserver
```

The function composes existing primitives in this order:

1. Canonically translate and normalize the selected spec.
2. Parse and statically validate its catalog row.
3. Classify its model family.
4. For OMP routes, resolve `omp models --json` and require exact provider/model membership.
5. Refresh and validate manifest, seed, and interpreter binding.
6. Validate the source/runtime vector through the retained non-authoritative primitive.
7. Validate a finite, positive, policy-valid timeout budget.
8. Evaluate memory/headroom and active same-phase/spec cooldown.
9. Derive the dispatch fingerprint.
10. Atomically compare the fingerprint with the ledger-backed terminal/precondition projection and reserve an admitted dispatch.
11. Return an immutable `WorkerAdmissionReceipt`.

The outcome contract is:

```text
WorkerAdmissionReceipt
| SchedulingCondition
| typed terminal AdmissionRefusal
```

`require_production_worker_dispatch_runtime` does not sleep, probe, emit `retry_wait`, or recursively call itself. “Pure gate” means it owns validation and the required atomic admission reservation but no scheduling loop or final launch.

The receipt contains:

```text
admission_receipt_id
logical_dispatch_id
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
dispatch_fingerprint
projection_version
admission_reservation_event_id
accepted_changed_precondition_event_id | null
admitted_at
```

Manifestless development remains explicitly non-production. Production intent, a production manifest, or a configured cloud seed may not collapse to a development no-op.

Any live-membership command failure, timeout, malformed JSON, ambiguous row, unavailable database, or provider-read error fails typedly. It never becomes an empty accepted catalog.

### 4.4 One scheduling-condition loop owner

A shared `dispatch_with_admission` seam is the only owner of scheduling-condition control flow.

Its contract is:

1. Invoke the canonical gate.
2. If admitted, verify the receipt’s reservation and call the final-launch closure once.
3. If given a `SchedulingCondition`:
   - append one idempotent scheduling evidence event for the condition identity;
   - emit one corresponding `retry_wait` work-ledger event;
   - calculate the bounded next attempt from `retry_after_s`, the logical dispatch deadline, and policy caps;
   - sleep through the injected sleeper when the bound permits;
   - for probe-required conditions, acquire the projection’s single probe lease and run the injected bounded probe;
   - rerun the entire admission gate with an incremented admission-attempt count;
   - never call the final-launch closure before a receipt.
4. If the logical dispatch’s bounded scheduling window expires, return the current typed scheduling condition to phase-result handling. It is not converted into a worker failure.
5. If given a terminal admission refusal, return or raise that refusal without launching.

`RecoveryPolicy` only classifies the returned scheduling condition as defer/retry-wait before breaker accounting. It does not sleep, probe, rerun admission, reset counters, or rotate providers.

`auto.py` must delete the post-failure cooldown parser/reset path. There is no second scheduler in `auto.py`, `RecoveryPolicy`, or provider fallback code.

Idempotence keys prevent duplicate `retry_wait` evidence for the same condition and admission-attempt identity.

### 4.5 Scheduling-condition schema

Add `ExitKind.scheduling_condition` and a strict `SchedulingCondition` payload:

```text
schema_version
condition_id
reason
phase
spec
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

Typed `reason` values initially in scope:

```text
memory_cooldown
provider_degraded
provider_probe_wait
provider_probe_failed
```

Rules:

- `condition_id` is always required and is independent of death identity.
- `cause_event_id` references the provider/memory observation when one exists.
- `disposition_id` is optional and valid only when the condition was caused by a real recorded worker disposition, such as a positively identified cgroup-OOM death.
- A probe timeout or provider availability hold does not invent a worker disposition.
- Scheduling conditions do not call `record_step_failure`.
- They increment none of the deterministic-phase, repeated-signature, or recovery-circuit counters.
- They cannot transition a plan to `blocked`.
- Genuine internal errors, malformed output, schema failures, auth failures, and test failures retain their existing failure behavior.

### 4.6 Canonical dispatch fingerprint and changed-precondition contract

The canonical dispatch fingerprint includes stable execution preconditions:

```text
phase
normalized selected spec
model family
prompt_or_phase_input_identity
source revision
runtime vector
manifest and seed identity
dependency interpreter identity
timeout budget
live membership digest
configured fallback-chain identity
current authorized route identity
```

A terminal `worker_disposition` records this fingerprint.

Admission refuses the same terminal fingerprint on its first proposed redispatch unless a later allowlisted `changed_precondition` event proves a durable content change. Time passage, sleep, PID replacement, retry count, or an unstructured operator note is never sufficient.

The strict event schema is:

```text
schema_version
event_type = changed_precondition
event_id
plan_id
phase
logical_dispatch_id | null
reason
before_content_id
after_content_id
evidence_event_id
source_revision | null
runtime_vector | null
interpreter_identity | null
route_identity | null
membership_digest | null
timeout_policy_identity | null
repair_commit_sha | null
recorded_at
actor
```

Allowlisted reasons are:

```text
source_revision_changed
runtime_generation_changed
seed_or_interpreter_binding_changed
timeout_policy_changed
authorized_route_changed
provider_recovery_verified
verified_repair_committed
```

Validation rules:

- `before_content_id` and `after_content_id` must differ.
- The reason-specific identity field must be present.
- `authorized_route_changed` must reference a jointly admitted route-transition event.
- `provider_recovery_verified` must reference a successful bounded probe observation.
- `verified_repair_committed` requires a repository commit SHA and evidence digest; free-form “explicit recovery action” is forbidden.
- The event must be later than the terminal disposition it supersedes.
- The admitted receipt must name `accepted_changed_precondition_event_id`.
- A change event may not be reused to authorize multiple concurrent identical reservations.

### 4.7 Atomic admission and replay semantics

`IncidentLedger` is the durable serialization point.

At the final admission step, the gate performs an atomic projection transaction under the ledger’s existing lock/transaction boundary:

1. Read the latest terminal fingerprint, changed-precondition event, route transition, and outstanding admission reservation for the projection key.
2. Reject an unchanged terminal fingerprint without an unused valid change event.
3. Reject a duplicate active reservation for the same logical dispatch/fingerprint.
4. Append an `admission_reserved` event containing the receipt identity, projection version, fingerprint, and accepted change-event reference.
5. Return the receipt only after the append succeeds.

If ledger append or lock acquisition fails, admission fails closed and no final launch occurs.

Projection replay is deterministic from canonical incident-ledger events. Existing fallback metadata may cache the projection, but:

- ledger events are authoritative;
- cache writes occur only after successful ledger append;
- cache/version mismatch triggers replay;
- restart reconstructs the same state;
- concurrent writers use expected projection version/event identity;
- a losing compare-and-swap reloads rather than duplicating a launch, flip, or probe.

### 4.8 Complete worker-disposition contract

Add `incident/disposition.py` with:

- `WorkerDisposition`;
- typed enums;
- fingerprint and disposition-ID builders;
- `record_worker_disposition`;
- `record_changed_precondition`;
- scheduling/provider transition helpers;
- the narrow shell CLI.

Enums:

```text
DispositionMode:
  in_band
  observed

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

CauseKind:
  timeout
  terminate
  escalation
  wedge
  restack
  cgroup_oom
  observed_dead_unknown
```

Every disposition contains:

```text
schema_version
event_type = worker_disposition
disposition_id
mode
plan_id
phase
logical_dispatch_id
dispatch_fingerprint
killer_kind
killer_identity
cause_kind
signal
elapsed_s
selected_spec
worker_identity
victim_pid | null
victim_process_start_identity | null
process_group_identity | null
timeout_source | null
ladder_step | null
observed_at
evidence
```

Mode-specific requirements:

- **In-band:** victim PID or process-group identity, process-start identity where obtainable, exact killer identity, signal, elapsed time, and ladder step for escalation are required.
- **Observed:** observation source and evidence are required. A positive cgroup counter delta is required before claiming `kernel_cgroup_oom`. If the cause is not positively known, use `external_unknown` and `observed_dead_unknown`.
- Timeout dispositions require `timeout_source`.
- TERM and later KILL are separate events with distinct deterministic IDs.
- IDs derive from plan/dispatch fingerprint, victim incarnation, killer, signal, and ladder/observation identity.
- In-band append must complete before the signal primitive is called.
- Append failure prevents the signal and returns non-success.
- Observed-death append must complete before orphan cleanup or redispatch authorization.
- State-level worker-death records are derived cache/projection data, not a second authority.

### 4.9 Shell disposition CLI contract

The executable interface is:

```bash
python -m arnold_pipelines.megaplan.incident.disposition record \
  --ledger-root "$LEDGER_ROOT" \
  --json-stdin
```

Contract:

- Reads exactly one UTF-8 JSON object from stdin.
- Validates it through the same `WorkerDisposition` schema as Python callers.
- Resolves the canonical plan incident ledger beneath the explicit `--ledger-root`.
- Appends synchronously through `IncidentLedger.append_event`.
- Writes one JSON acknowledgement containing `disposition_id` and ledger event identity to stdout.
- Writes diagnostics to stderr.
- Does not perform the signal itself.

Exit statuses:

```text
0  append succeeded
2  malformed JSON or schema violation
3  ledger append/locking failure
4  invalid or unavailable ledger location/context
```

Shell wrappers follow:

```text
resolve exact victim
perform first/second sustained observation where required
invoke disposition CLI
require exit 0 and matching acknowledgement
invoke stub-able signal primitive
```

A nonzero CLI status leaves the victim alive, records the inability to kill where possible, and makes the wrapper return non-success.

Tests replace both the CLI command and the signal primitive. They assert exact arguments and record-before-signal ordering for every scoped branch.

### 4.10 One ledger-backed provider/precondition projection

Provider health, route selection, fingerprint changes, and admission retry authorization use one projection over canonical incident-ledger events. No independent provider-health database or second rotator is introduced.

Projection key:

```text
plan_id
phase
primary_spec
configured_fallback_chain_identity
```

Derived `ProviderRouteProjection` fields:

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
```

`route_status` values:

```text
primary
holding
probing
fallback
return_pending
```

`probe_status` values:

```text
none
leased
passed
failed
```

Canonical events include:

```text
provider_observation
provider_hold
provider_probe_started
provider_probe_result
provider_route_flip
provider_route_return
provider_success
changed_precondition
```

Existing fallback metadata mirrors current route, streak, deadline, and last transition as a cache. `_advance_configured_spec_fallback` remains the only configured fallback-rotation door.

Transition rules:

1. One exhausted logical dispatch classified as availability/idle-timeout appends one `provider_observation`.
2. Internal retry chatter does not create multiple observations.
3. Observations count only when phase, selected spec, and precondition identity match.
4. An intervening provider success or valid changed-precondition event resets the streak.
5. Two consecutive matching observations establish `provider_degraded`.
6. Auth, quota, rate limit, unsupported model, context-window, malformed output, schema, and internal errors never enter this projection as degradation evidence.
7. Projection transitions append under the ledger lock with an expected prior event/version.
8. Restart replays the ledger. Duplicate or interleaved observation IDs do not increment twice.
9. Only one caller may hold a probe lease for a projection key.
10. A loser of a concurrent flip/probe transition reloads the new state and does not repeat the action.

### 4.11 Provider fallback, scalar pin, and return rules

For a configured non-execute fallback chain:

1. Two matching observations produce `provider_degraded`.
2. `dispatch_with_admission` requests the next target through `_advance_configured_spec_fallback`.
3. The proposed target is passed through joint admission before route mutation.
4. If joint admission rejects it, no route event and no RPC occur.
5. If admitted, append `provider_route_flip` with `from_spec`, `to_spec`, reason, observation identity, admission receipt, and projection version.
6. Update existing fallback metadata only after append.
7. Redispatch through the same physical door and shared admission seam.

For a scalar pin:

1. Never widen the pin to historical last-known-good.
2. Append a bounded `provider_hold` and return a scheduling condition.
3. After `retry_not_before`, acquire one probe lease.
4. Run one injected, bounded, no-tool provider probe.
5. Failed probe appends evidence and yields another scheduling condition without blocking.
6. Passed probe appends `provider_probe_result` and an allowlisted `provider_recovery_verified` changed-precondition event.
7. Exactly one post-recovery dispatch reservation may consume that event.

For return to primary:

1. A fallback route does not probe primary on every outer-loop iteration.
2. The projection’s retry deadline and single probe lease control probing.
3. A passing primary probe is followed by joint admission of the primary candidate.
4. Append `provider_route_return` before route metadata changes.
5. The event includes `from_spec`, `to_spec`, reason, probe event, admission receipt, and transition identity.
6. Only then may a new logical dispatch use primary.

For execute and loop-execute:

- fallback advancement remains prohibited;
- `ExecuteFallbackUnsafe` semantics are preserved;
- only bounded hold/probe scheduling is allowed;
- no second execution attempt is created by provider rotation.

## 5. Explicitly rejected implementation patterns

The implementation must not:

- retain a chain-local admission authority;
- add another preflight beside the canonical gate;
- gate `_impl.py` and `run_omp_step` for the same nested OMP dispatch;
- equate physical door count with admission-attempt count;
- place sleep/probe/retry loops in the pure gate;
- place another scheduling loop in `auto.py` or `RecoveryPolicy`;
- scrape English stderr in `auto.py` to infer scheduling policy;
- require or invent a disposition ID for a provider scheduling condition;
- create a provider-health store separate from incident-ledger projection and fallback metadata;
- create an independent provider rotator;
- permit a free-form recovery note to bypass fingerprint refusal;
- redispatch a terminal fingerprint merely because time passed;
- count individual internal retries as separate degradation observations;
- treat one idle-timeout, stale heartbeat, socket dip, or scan as sustained failure;
- accept PID presence as health without process-start identity and advancing progress;
- treat an anonymous integer exit code as a disposition;
- claim cgroup OOM without positive evidence;
- signal before a disposition append succeeds;
- let a live-membership read error become an accepted empty catalog;
- apply a box-only hotfix absent from the candidate branch.

## 6. Execution batches and tasks

All implementation, focused-test, critique, and independent-review work is assigned to GPT-5.6 Luna. Planning/revision and Oracle judgments remain GPT-5.6 Sol with high reasoning. No model switch is authorized without user approval.

### Batch 1 — Freeze typed contracts and projections

#### NBF-01 — Add scheduling, disposition, precondition, and projection contracts

**Classification:** Normal / GPT-5.6 Luna.

**Files and symbols**

- `arnold_pipelines/megaplan/orchestration/phase_result.py`
  - `ExitKind`
  - `SchedulingCondition`
  - serialization/deserialization
- `arnold_pipelines/megaplan/orchestration/recovery_policy.py`
  - `RecoveryPolicy.classify`
  - `classify_with_circuit`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
  - `IncidentLedger.append_event`
  - `RuntimeTransitionWriter`
- New `arnold_pipelines/megaplan/incident/disposition.py`
  - `WorkerDisposition`
  - typed enums
  - fingerprint/disposition builders
  - changed-precondition validation
  - atomic admission reservation
  - provider/precondition projection
  - transition/evidence helpers
  - shell CLI
- Existing fallback metadata schema
- New tests:
  - `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
  - `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
  - `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`

**Work**

- Implement the complete schemas in §§4.5–4.10.
- Add strict mode-specific disposition validation.
- Add allowlisted changed-precondition validation.
- Add ledger-derived projection replay and versioned atomic transitions.
- Reuse fallback metadata as a cache.
- Add admission reservation and one-use change-event consumption.
- Make `RecoveryPolicy` recognize scheduling before all failure/circuit accounting.
- Add the module CLI and frozen exit contract.
- Keep genuine failures on existing failure paths.

**Acceptance**

- Incomplete in-band or observed disposition events are rejected before append.
- An observed unknown death cannot claim cgroup OOM.
- TERM and KILL in one ladder have distinct IDs.
- A scheduling condition is valid without `disposition_id`.
- A scheduling condition never increments any breaker.
- Three genuine identical `internal_error` outcomes still open the existing breaker.
- Free-form changed-precondition reasons are rejected.
- A valid change event cannot authorize two concurrent identical reservations.
- Replay after restart reproduces route, streak, deadline, probe, and precondition state.
- Duplicate/interleaved provider observations do not increment the streak twice.
- Cache disagreement is repaired from the ledger.
- Ledger/lock failure is visible and fail-closed.
- CLI exit codes and stdout acknowledgements match §4.9.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py \
  tests/arnold_pipelines/megaplan/test_plan_circuit.py
```

**Synchronization point**

The Sol Oracle reviews and freezes all schemas, enums, event fields, CLI behavior, and projection transitions before Batch 2 callers adopt them. Later incompatible schema changes require plan revision.

### Batch 2 — The one admission door and shared scheduling seam

#### NBF-02 — Expand canonical admission and implement `dispatch_with_admission`

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01.

**Files and symbols**

- `cloud/runtime_attestation.py`
  - `require_production_worker_dispatch_runtime`
  - typed request/outcome/receipt
  - `refresh_runtime_launch_seed_for_worker_dispatch`
  - `require_configured_runtime_launch`
- New or existing shared dispatch module for:
  - `dispatch_with_admission`
- `chain/source_admission.py::worker_launch_preflight`
- `chain/__init__.py` production callers and chain-local refusals
- `workers/omp.py`
  - `parse_omp_spec`
  - `validate_omp_catalog_model`
  - canonical translation/live-membership adapter
- `arnold/pipeline/model_seam.py::classify_model_family`
- `skills/subagent-launcher/launch_omp_agent.py`
  - remove local translation authority
- `runtime/memory_headroom.py`
  - `memory_cooldown_wait_secs`
  - `select_memory_safe_spec`
- `handlers/shared.py`
  - remove standalone memory admission authority
- `incident/disposition.py`
- `observability/work_ledger.py`
- `orchestration/recovery_policy.py`
- `auto.py`
  - delete post-failure cooldown repair/reset logic
- `tests/cloud/test_runtime_attestation.py`
- New:
  - `tests/cloud/test_worker_dispatch_admission.py`
  - `tests/cloud/test_dispatch_with_admission.py`
  - `tests/cloud/test_chain_admission.py`

**Work**

1. Inventory every production caller of:
   - `worker_launch_preflight`;
   - chain-local source/runtime raises;
   - raw refresh/require helpers;
   - memory admission.
2. Classify each caller as:
   - non-launch preparation;
   - delegate to a frozen physical door;
   - genuine direct launch requiring refactor to a frozen door.
3. Make retained source/runtime helpers non-authoritative primitives callable only by the canonical gate.
4. Add the typed request, terminal refusal, scheduling result, and receipt.
5. Normalize model translation ownership and delete the launcher-local authority.
6. Add injectable `omp models --json` membership resolution.
7. Prove static acceptance but joint rejection of expired `openrouter/stealth/ox-alpha`.
8. Move source/runtime and memory checks into the canonical gate.
9. Implement atomic terminal-fingerprint comparison and admission reservation.
10. Implement `dispatch_with_admission` as the only scheduling-condition loop.
11. Emit idempotent scheduling and retry-wait evidence.
12. Use injected clock, sleeper, and probe seams.
13. Rerun the entire gate after each resolved condition.
14. Delete `auto.py`’s cooldown counter repair/reset path.

**Acceptance**

- One receipt proves all frozen admission invariants.
- Production intent cannot pass without seed, manifest, source, runtime, and interpreter proof.
- Unknown, expired, or live-absent model IDs fail before client/spawn construction.
- Membership command/read failure fails typedly.
- Timeout `None`, zero, negative, non-finite, or policy-invalid values fail typedly.
- The first proposed redispatch of a terminal fingerprint is refused.
- A valid later changed-precondition event permits one admission, and the receipt references it.
- Concurrent identical requests produce at most one active reservation.
- A chain-originated worker dispatch cannot bypass the canonical gate.
- `worker_launch_preflight` has no production authorization caller outside the gate.
- Three active cooldown admission attempts produce retry evidence and zero final launches; expiry produces one receipt and one final launch.
- Attempt counts may exceed one while physical door and final-launch counts remain one.
- Scheduling-window exhaustion returns a scheduling condition without failure accounting.
- No raw memory-admission authority remains in `handlers/shared.py`.
- No cooldown-specific breaker reset remains in `auto.py`.

**Focused validation**

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_chain_admission.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/workers/test_omp_adapter.py
```

#### NBF-03 — Wire all physical doors and prove ownership structurally

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-02.

**Files and symbols**

- `workers/_impl.py`
  - `run_step_with_worker`
  - `_run_step_with_worker_legacy`
  - dispatcher closures
  - nested OMP delegation
- `workers/omp.py::run_omp_step`
- `cloud/babysitter/launch.py::launch_babysitter`
- `cloud/babysitter/launch.py::_managed_spec`
- Chain delegation path identified by NBF-02
- `docs/nbf-hourly-loop-goal.md`
- `cloud/fixer_model_policy.py`
- New `tests/cloud/test_worker_dispatch_spy.py`
- `tests/cloud/test_chain_admission.py`
- Babysitter tests:
  - `tests/cloud/test_babysitter_routing.py`
  - `tests/cloud/test_babysitter_goal.py`

**Work**

- Delete `_impl.py`’s raw refresh/require/source-preflight block.
- Native non-OMP `_impl.py` uses `dispatch_with_admission` once immediately before the final backend call.
- `_impl.py` OMP delegation does not own admission.
- `run_omp_step` owns `dispatch_with_admission` for nested and direct OMP dispatches.
- Admission precedes output seeding, client construction, RPC, and mock-worker early return under production intent.
- Babysitter uses the shared seam immediately before writing its running receipt and invoking `run_managed_command`.
- Normal and `MEGAPLAN_USE_AGENT_DISPATCHER=1` paths obey the same ownership.
- Chain-originated dispatches delegate to these same physical owners.
- Checked-in pin/policy documentation states pins are advisory and the canonical gate is authoritative.
- Do not mutate `/workspace/.cloud-hot-env`.

**Structural spy scenarios**

1. Public `run_step_with_worker`, native non-OMP:
   - one physical door entry;
   - one admission attempt without scheduling;
   - one final worker call.
2. Public `run_step_with_worker`, nested OMP:
   - no outer `_impl.py` admission owner;
   - one physical owner inside `run_omp_step`;
   - one admission attempt without scheduling;
   - one final fake RPC.
3. Direct `run_omp_step`:
   - one physical owner;
   - one admission attempt;
   - one final fake RPC.
4. Babysitter:
   - one physical owner;
   - one admission attempt;
   - one `run_managed_command`.
5. Chain-originated dispatch:
   - no chain-local authorization;
   - delegation reaches one frozen physical owner;
   - one final call.
6. Gate rejection:
   - zero final calls in every scenario.
7. Cooldown:
   - one physical owner;
   - multiple admission attempts;
   - zero final calls before expiry;
   - exactly one final call after the first receipt.
8. No scenario uses `MEGAPLAN_MOCK_WORKERS=1`; only the final spawn/RPC seam is replaced.

**Acceptance**

- Physical door count is exactly one per logical dispatch.
- Final-launch count is zero or one.
- Admission-attempt count is independently observable.
- Reintroducing an outer OMP gate fails with two physical owners or duplicate scheduling traces.
- Removing a door call fails its positive and rejection tests.
- Bypassing the gate from chain fails the chain negative test.
- Ordered traces prove receipt/reservation before final launch.
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

The Sol Oracle reviews:

- caller inventory;
- chain classification;
- structural door/attempt/launch traces;
- nested OMP count;
- chain-bypass negative test;
- raw-preflight negative scan.

### Batch 3 — Every worker death speaks

#### NBF-04 — Route Python signal and observed-death paths through the disposition helper

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01 and NBF-02’s final admission receipt/fingerprint contract.

**Files and symbols**

- `skills/subagent-launcher/launch_omp_agent.py::main`
- `resident/subagent.py`
  - same-session follow-up SIGINT
  - timeout TERM→KILL ladder
  - exception TERM→KILL ladder
- `auto.py`
  - orphan recovery
  - `_build_worker_death_record`
  - `_emit_worker_killed_event`
- `incident/disposition.py`
- `tests/resident/test_managed_provider_agent_runner.py`
- Focused launcher tests under `tests/skills/`
- `tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py`

**Work**

- Replace launcher `subprocess.run(timeout=...)` with explicit process control.
- At timeout, append the SIGKILL disposition at the kill site, then kill/wait, then preserve timeout metadata/return 124.
- Before every resident SIGINT, SIGTERM, and SIGKILL, synchronously append a complete disposition.
- Preserve both TERM→wait→KILL ladders and current return behavior.
- Record distinct ladder events and IDs.
- Convert positive cgroup-OOM orphan evidence into a canonical observed disposition before cleanup or redispatch.
- Record unknown dead-PID observations explicitly without inventing OOM.
- Keep state-level death summaries as projections of canonical events.

**Acceptance**

- Call-order tests show append succeeds before every signal primitive.
- Ledger failure prevents in-band signaling.
- Timeout metadata and return codes remain compatible.
- One OOM observation produces one canonical disposition per active worker incarnation.
- Unknown cause remains typed as unknown.
- Both resident ladders cover TERM-only and TERM→KILL.
- Follow-up SIGINT is covered.
- Every event references the admission dispatch fingerprint.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py \
  tests/resident/test_managed_provider_agent_runner.py
```

#### NBF-05 — Instrument watchdog/restack signals and require sustained proof

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-04.

**Files and symbols**

- `cloud/wrappers/arnold-watchdog`
  - `signal_hung_fixer_children`
  - `babysitter_wedged`
  - stale babysitter signaling
  - `kill_process_group`
  - `kill_pid_and_descendants`
  - repair-tree reaping
- `cloud/systemd/ensure-megaplan-watchdog`
- `incident/disposition.py` CLI
- `tests/cloud/test_watchdog_wrappers.py`
- New `tests/cloud/test_watchdog_dispositions.py`

**Work**

Every real signal in the two scoped shell files must follow:

1. Resolve the exact victim PID/process group and process-start identity.
2. Take the required first observation.
3. Take a separated second observation using the same victim incarnation.
4. Require positive lack-of-progress proof using the same sequence/progress identity.
5. Invoke the disposition CLI with the complete schema.
6. Verify exit 0 and acknowledgement identity.
7. Invoke the signal primitive.

Additional rules:

- PID replacement or advancing progress clears first-scan state.
- Hung-child, wedge, repair reaping, and ensure-restack use the same two-scan contract.
- `kill -0` remains a classified liveness probe, not a real signal.
- TERM→KILL escalation writes one event before each signal.
- The ensure script resolves the active source/runtime for the helper and does not hardcode a candidate checkout.
- CLI/ledger failure leaves the process alive and returns non-success.

**Required shell tests**

Stub both:

- `python -m arnold_pipelines.megaplan.incident.disposition`;
- the real signal primitive.

For every scoped branch, assert:

- first scan does not invoke the CLI or signal;
- changing PID/process-start/progress resets confirmation;
- second matching scan invokes CLI first;
- CLI receives complete killer, victim, signal, elapsed, fingerprint, and evidence fields;
- signal is invoked only after CLI exit 0;
- CLI failure causes zero signal calls;
- TERM and KILL escalation produces two ordered records and two ordered signals;
- process-group and descendant targeting remains exact.

The tests emit a machine-readable execution artifact containing:

```text
source_file
function_or_branch
signal_or_probe
killer_kind
two_scan_owner
disposition_test_id
failure_order_test_id
```

Every scoped real signal must have a row. Liveness probes are marked `probe`.

**Acceptance**

- A first scan never signals.
- Two matching separated observations are required.
- Progress or process incarnation change resets the confirmation.
- Every real signal has a preceding disposition.
- Append failure leaves victims alive.
- No process is reaped solely from `completed.json`, PID presence, or one stale timestamp.
- Shell syntax passes.
- The signal-site inventory has no unclassified real signal.

**Focused validation**

```bash
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
bash -n arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog
pytest -q \
  tests/cloud/test_watchdog_dispositions.py \
  tests/cloud/test_watchdog_wrappers.py
```

**Synchronization point**

The Sol Oracle receives the machine-readable signal-site inventory and shell ordering evidence. Any unclassified real signal or signal reachable after CLI failure blocks the batch.

### Batch 4 — Finish cooldown scheduling and provider resilience

#### NBF-06 — Complete T7 and implement T8 through the existing fallback door

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01 through NBF-03.

NBF-06 owns structured provider-availability evidence propagation. It must complete and test that producer substep before route-transition work begins; no implementation may infer provider degradation from unstructured stderr.

**Files and symbols**

- `fallback_chains.py`
  - `classify_retryability`
  - same-family operational classification
- `workers/_impl.py`
  - `_initial_fallback_metadata`
  - `_advance_configured_spec_fallback`
  - worker-result and `CliError` evidence propagation
- `workers/omp.py`
  - exhausted-dispatch availability evidence
  - bounded injectable provider probe
- `handlers/shared.py`
- `orchestration/phase_result.py`
- `orchestration/phase_result_classify.py`
- `orchestration/recovery_policy.py`
- `auto.py`
  - remove remaining scheduling repair/reset behavior
  - preserve genuine breaker behavior
- `incident/ledger.py`
- `incident/disposition.py`
- New:
  - `tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py`
- Existing fallback, phase-result, memory, auto, and execution-policy suites

**Substep A — Availability-evidence producer**

- Define one structured exhausted-dispatch observation containing:
  - logical dispatch ID;
  - phase/spec;
  - retryability class;
  - exhausted attempt count as evidence only;
  - terminal provider evidence identity;
  - precondition identity.
- Export it from OMP and non-OMP results without English parsing.
- Prove one exhausted dispatch creates one observation regardless of internal retry count.
- Prove excluded classes do not create degradation observations.

**Substep B — Route and hold transitions**

- Feed structured observations into the ledger-backed provider projection.
- Require two consecutive matching observations.
- Emit typed `provider_degraded` before generic failure blocking.
- Use the shared scheduling seam for waits and probes.
- Advance configured non-execute fallbacks only through `_advance_configured_spec_fallback`.
- Jointly admit targets before flip events or RPC.
- Use scalar hold/probe rules without widening pins.
- Use projection deadlines and probe leases to prevent primary hammering.
- Append flip and return events before updating fallback metadata.
- Preserve execute/loop-execute fallback prohibition.
- Delete any remaining `auto.py` scheduling-specific counter repair.

**Acceptance**

- One timeout does not flip or mark degraded.
- Two matching exhausted observations produce `provider_degraded`.
- One dispatch with many internal retries counts once.
- Success or allowlisted changed precondition resets the streak.
- Restart and concurrent observation tests reproduce the same projection.
- Scheduling changes none of the breaker families and never blocks the plan.
- A configured alternate changes only through the existing fallback door.
- Joint admission rejection prevents flip and RPC.
- Scalar pin performs bounded hold, a single leased probe, and at most one admitted post-recovery redispatch.
- Failed scalar probes remain scheduling conditions.
- Return to primary records complete transition evidence before route change.
- Repeated genuine `internal_error` still opens its breaker.
- Execute and loop-execute preserve `ExecuteFallbackUnsafe`.
- The ledger-14 scenario cannot create an unbounded retry or invalid-transition cascade.

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
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

**Synchronization point**

The Sol Oracle judges T7 and T8 jointly. Retaining post-failure counter resets, adding a second scheduling loop, parsing stderr for provider policy, adding another route store, or rotating outside `_advance_configured_spec_fallback` is a rejection.

### Batch 5 — Fresh-base integration, review, and delivery

#### NBF-07 — Rebase, validate once broadly, review, and push the candidate branch

**Classification:** Normal / GPT-5.6 Luna.

**Dependencies:** NBF-01 through NBF-06.

**Work**

1. Commit every accepted implementation batch in the candidate tree.
2. Verify the custody commits and protected artifact still exist.
3. Run:

```bash
git fetch origin main --prune
git rebase origin/main
```

4. Resolve conflicts by composing with current main. Do not reset, discard, or silently overwrite unrelated work.
5. Run the authoritative broad validation exactly once after the fresh rebase.
6. Capture:
   - rebased source and candidate SHAs;
   - exact test command/result;
   - logical-dispatch, physical-door, admission-attempt, and final-launch traces;
   - chain caller inventory and bypass evidence;
   - disposition CLI contract results;
   - machine-readable signal-site inventory;
   - provider projection replay/interleaving results;
   - negative raw-preflight scan;
   - shell syntax results;
   - criterion completion table.
7. Assign one GPT-5.6 Luna independent reviewer to the complete evidence.
8. Submit the result to the GPT-5.6 Sol completion Oracle.
9. Push `megado-nbf-guard-0826` to origin. If rebase rewrote a published branch, verify the remote tip and use `--force-with-lease`, never unguarded force.
10. Stop before merging to `main` and request explicit user approval.

## 7. Task model classification

| Task | Classification | Rationale |
|---|---|---|
| NBF-01 contracts/projection | Normal / Luna | Schemas, transitions, replay, and concurrency behavior are fully specified and testable. |
| NBF-02 admission/scheduling seam | Normal / Luna | Existing validators are being composed under one precise authority with deterministic adapters. |
| NBF-03 wiring/structural spy | Normal / Luna | Ownership and cardinality have explicit positive and negative oracles. |
| NBF-04 Python dispositions | Normal / Luna | Signal sites, schemas, fingerprints, and ordering requirements are enumerated. |
| NBF-05 shell dispositions | Normal / Luna | Two files, a frozen CLI, stubbed ordering tests, and a complete inventory bound the work. |
| NBF-06 T7/T8 | Normal / Luna | Evidence production precedes explicit projection transitions; no design choice remains. |
| NBF-07 integration/delivery | Normal / Luna | Mechanical custody, rebase, validation, independent review, and guarded push. |

No task is `[XHARD]`. The revision resolves the former non-local ambiguity by freezing owners, schemas, transitions, and negative cases. No evidence satisfies the exceptional threshold for a Sol execution worker.

## 8. Open questions and assumptions

### User-authority checkpoint

- Merging `megado-nbf-guard-0826` into `main` requires explicit user approval after completion review and branch push. This does not block implementation.

### Implementable assumptions

- The two-observation rule applies to provider degradation, watchdog wedge, hung child, repair reaping, and ensure-restack.
- One exhausted provider dispatch is one observation; internal retry attempts are evidence, not additional supervision observations.
- Last-known-good does not widen a scalar pin.
- Actual `/workspace/.cloud-hot-env` is outside the repository and remains untouched. Checked-in policy documentation points at the canonical gate.
- Existing static `ox-alpha` rows remain for the discriminating regression test.
- Fake clock, membership, RPC, process, ledger, CLI, and signal seams provide sufficient structural proof.
- Inventorying chain callers and the exact `omp models --json` shape is bounded implementation inspection under already settled contracts, not a new product decision or material investigation.
- No live marathon or box mutation is required for completion.

## 9. Effort and huge-run determination

| Batch | Estimate |
|---|---:|
| Contracts and projections | 1.5–2 engineer-days |
| Admission, scheduling seam, and door wiring | 2–2.5 engineer-days |
| Python and shell dispositions | 2–2.5 engineer-days |
| T7/T8 provider scheduling | 2.5–3 engineer-days |
| Rebase, validation, review, delivery | 1 engineer-day |
| **Total** | **9–11 engineer-days** |

**Huge-run determination: NO.** The scope remains approximately two focused working weeks and does not require a megaplan epic. Synchronization points are review boundaries, not cumulative epic gates.

## 10. Validation and completion matrix

| Criterion | Command/scenario | Required evidence | Passing condition |
|---|---|---|---|
| 1. Unique admission | Runtime/admission/chain suites; caller inventory | Complete receipt, typed refusals, chain classification | Only `require_production_worker_dispatch_runtime` authorizes production workers; retained helpers are non-authoritative. |
| 2. Exactly-once doors | Native, nested OMP, direct OMP, babysitter, chain-origin spies | Separate door, attempt, and launch traces | One physical owner, one or more attempts, zero or one final launch. |
| 3. Typed deaths | Launcher, resident, OOM, watchdog, restack | Complete ledger rows, CLI acknowledgement, signal inventory | Every scoped signal is preceded by a successful append; observed deaths precede cleanup/retry. |
| 4. Fingerprint block | Same terminal fingerprint, concurrent retry, valid changed precondition | Refusal, reservation winner, receipt change reference | First identical retry is rejected; only one valid changed event authorizes one reservation. |
| 5. Joint model admission | Static `ox-alpha` acceptance and live rejection | Static and joint outcomes | Static acceptance remains; joint live admission rejects before RPC. |
| 6. Structural spy | No mock early return; final seams only | Ordered trace and bypass negatives | Removing a door, adding an outer OMP owner, or bypassing from chain fails. |
| 7. Cooldown scheduling | Fake clock with repeated conditions and expiry | Retry-wait IDs, attempts, breaker snapshots, final call | Shared seam owns waits/reruns; no failure accounting; one launch after receipt. |
| 8. Provider degradation | One/two observations, flip, scalar hold/probe, restart, interleaving, return, execute ban | Projection events/cache versions/breaker snapshots | Sustained evidence only; existing rotator only; no block or unchanged retry; genuine failures still break. |

### Authoritative post-rebase command

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/cloud/test_watchdog_dispositions.py \
  tests/cloud/test_watchdog_wrappers.py \
  tests/workers/test_omp_adapter.py \
  tests/resident/test_managed_provider_agent_runner.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py \
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

The machine-readable structural inventory, not an unreviewed grep count, owns final signal classification because `kill -0` and equivalent probes are legitimate.

## 11. Completion conditions

The work is complete only when:

- criteria 1–8 have PASS evidence;
- all 42 existing runtime-attestation tests remain green;
- new admission, scheduling-loop, chain-bypass, disposition, provider-projection, and structural-spy suites are green;
- one canonical chain-inclusive admission authority remains;
- every chain-originated launch delegates to a frozen physical door;
- physical door ownership, admission attempts, and final launches are separately proven;
- scheduling conditions never require synthetic worker-death identities;
- the complete disposition and CLI contracts are enforced;
- every scoped Python and shell signal is preceded by a successful disposition append;
- CLI failure tests prove victims remain alive;
- the signal-site inventory has no unclassified real signal;
- identical terminal fingerprints are refused atomically before launch;
- accepted retries reference an allowlisted changed-precondition event;
- provider state replays correctly after restart and concurrent transitions;
- configured flips use only the existing fallback door after joint admission;
- scalar pins hold/probe without widening;
- return-to-primary evidence precedes route mutation;
- cooldown and provider conditions affect no breaker;
- genuine repeated internal errors still open their breakers;
- wrapper syntax checks pass;
- raw refresh/require calls are absent from the three physical door files;
- fresh fetch/rebase and the authoritative suite complete successfully;
- custody commits and protected artifacts survive;
- the candidate branch is pushed to origin;
- no box-only behavior change exists;
- the independent Luna reviewer and Sol Oracle accept completion;
- no merge to `main` occurs without explicit user approval.

## 12. Revised settled-plan readiness

**Disposition: READY_FOR_FRESH_LUNA_SETTLED-PLAN WAVE.**

The accepted W1 findings are now resolved at plan-contract level:

- admission authority is chain-inclusive and singular;
- scheduling has one loop owner;
- physical door ownership, attempts, and launches have distinct semantics;
- scheduling evidence is not synthetic death evidence;
- disposition schemas and shell interfaces are complete;
- provider and precondition state share one ledger-backed projection;
- changed-precondition bypasses are allowlisted and atomically consumed;
- dependencies and focused tests follow the frozen contracts.

No material architecture decision, user-policy choice, box investigation, or execution-model escalation remains. The exact chain caller inventory and live-membership JSON normalization are bounded implementation inspections with predetermined outcomes.

This revised snapshot must receive a fresh complete GPT-5.6 Luna settled-plan sense-check before it can be declared frozen. The later user-authority checkpoint remains merge approval only.

STABILITY: STABLE

## Oracle synthesis of W2

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

## Raw W2 simplicity findings

[launch_hermes_agent] model=codex:gpt-5.6-luna → resolved=openai-codex/gpt-5.6-luna toolsets=['file'] max_tokens=65536 context_budget_tokens=(auto)
[launch_hermes_agent] NOTE: omp gives the full toolset (Bash, Read, Edit, web, …); the file/web/terminal subset is a superset here.
[launch_hermes_agent] cwd=/Users/peteromalley/Documents/Arnold-oracle-nbf
Working...
**Result: material revision required.** The revised plan is not yet stable.

### SIMP2-1 — Provider fallback violates its own dispatch cardinality

**Material:** Yes.

**Evidence:** §4.1 defines one logical dispatch as producing “at most one final launch.” §4.11 then requires a provider route flip followed by “redispatch through the same physical door.” NBF-06 repeats this requirement. The current implementation already loops from a failed worker result or `CliError` into `_advance_configured_spec_fallback` and continues (`workers/_impl.py:7850-7885`, `7910-7941`), so literal implementation can launch a second worker for the same logical dispatch.

**Smallest safe correction:** Make each provider-route attempt a new `logical_dispatch_id`, linked to the prior attempt by a parent dispatch/transition identity. Preserve “at most one final launch” per logical dispatch. The route-transition event and changed-precondition event authorize the child dispatch; they must not silently permit a second launch under the original identity.

**Criterion impact:** Required for criteria 2, 4, and 8. Without it, launch cardinality and fingerprint replay semantics are contradictory.

**North Star:** Aligns with “one door per invariant” and the ban on retrying an unchanged failure fingerprint. It prevents route fallback from becoming an untracked duplicate launch.

### SIMP2-2 — The shared seam has no post-launch provider-evidence contract

**Material:** Yes.

**Evidence:** §4.4 defines `dispatch_with_admission` around gate outcomes: receipt, scheduling condition, or terminal refusal. T8 degradation, however, originates from an exhausted worker dispatch after the final-launch closure runs. NBF-06 requires that evidence to become `provider_degraded`, but no normative contract returns structured availability evidence from the closure to the seam before generic failure/breaker handling. The existing fallback loop in `_impl.py` is the obvious implementation path, but retaining it would create the second scheduling owner explicitly prohibited by §§4.4–4.5 and §5.

**Smallest safe correction:** Define the final-launch closure’s result as a typed `DispatchOutcome` that can carry terminal provider evidence. `dispatch_with_admission` must own the complete post-launch transition: project the observation, produce `SchedulingCondition`, perform the authorized fallback/hold/probe, rerun admission, and return only the final outcome. `RecoveryPolicy` must receive the scheduling condition, never raw provider evidence.

**Criterion impact:** Required for criteria 7 and 8; otherwise T8 can still bypass the sole scheduling loop.

**North Star:** Directly protects “one door per invariant” and prevents provider degradation from reintroducing fragmented retry logic.

### Non-material simplification

`incident/disposition.py` is assigned death schemas, fingerprints, changed-precondition validation, admission reservations, provider projection, transition helpers, and CLI behavior (§4.8, NBF-01). Splitting those concerns would improve maintainability, but it is not a plan-blocking duplicate authority if all writes remain ledger-backed.

**Material investigation newly required:** No. The corrections are contract-level and supported by the plan plus existing source paths.
[launch_hermes_agent] done in 188.4s (exit=0)
0

## Raw W2 contract findings

[launch_hermes_agent] model=codex:gpt-5.6-luna → resolved=openai-codex/gpt-5.6-luna toolsets=['file'] max_tokens=65536 context_budget_tokens=(auto)
[launch_hermes_agent] NOTE: omp gives the full toolset (Bash, Read, Edit, web, …); the file/web/terminal subset is a superset here.
[launch_hermes_agent] cwd=/Users/peteromalley/Documents/Arnold-oracle-nbf
Working...
**CONTRACT2-1 — Atomic reservation scope is contradictory**  
**Material: yes.** §4.7 rejects only a duplicate reservation for the same `logical_dispatch_id/fingerprint`, but §4.6 deliberately excludes `logical_dispatch_id` from the fingerprint. NBF-02 and the completion matrix require concurrent identical requests to produce at most one reservation, including requests with different logical IDs. Two concurrent dispatches can therefore reserve and launch the same terminal fingerprint. Additionally, a changed `live_membership_digest` changes the fingerprint without requiring an allowlisted `changed_precondition` event.

**Correction:** define the uniqueness/CAS key explicitly as projection key plus semantic dispatch fingerprint, independent of logical dispatch ID, and make the accepted change event single-use across that key. Require every fingerprint component—including membership digest—to be backed by a durable changed-precondition event when it differs from the terminal record, or remove volatile membership state from the fingerprint and use provider transition evidence instead.  
**Impact:** criterion 4; also criterion 5.  
**North Star:** directly violates the ban on unchanged-fingerprint redispatch and weakens “one door per invariant.”

**CONTRACT2-2 — Provider route transitions are not crash-atomic with admission**  
**Material: yes.** §4.11 requires joint admission, then appends `provider_route_flip`/`provider_route_return`, then updates fallback metadata. §4.7 atomically persists only `admission_reserved`; no transaction or recovery rule links that reservation to the subsequent route transition. A crash after reservation but before route-event append can leave a valid receipt consumed, route unchanged, metadata stale, and future dispatches blocked or incorrectly retried. The same window exists for return-to-primary.

**Correction:** define a transition intent/commit protocol in the ledger, or make reservation and route transition one atomic ledger operation. Specify restart reconciliation for every boundary and test crash injection before/after reservation, transition append, and metadata update.  
**Impact:** criteria 4 and 8.  
**North Star:** violates the single durable projection and risks duplicate/stranded route changes.

**CONTRACT2-3 — Death identity is not closed over launch boundaries**  
**Material: yes.** NBF-04 requires every disposition to reference the admission dispatch fingerprint, but its work does not define how the receipt/fingerprint reaches the standalone launcher or resident/shell paths. Current `launch_omp_agent.run()` accepts model/query/timeout but no plan, phase, logical-dispatch, receipt, or fingerprint fields (`skills/subagent-launcher/launch_omp_agent.py:167-183`); timeout handling is currently isolated at `:251-261`. The plan must specify required CLI/environment/metadata transport and failure behavior when context is absent.

**Correction:** freeze receipt-context propagation into launcher, resident, watchdog, and wrapper interfaces; reject signal attempts lacking it unless the event is explicitly typed observed/external-unknown.  
**Impact:** criterion 3 and the launcher acceptance tests.  
**North Star:** “deaths speak” cannot hold if killer identity exists but dispatch identity is missing.

**CONTRACT2-4 — Signal-site scope is incomplete or undefined**  
**Material: yes.** NBF-05 says “every scoped” signal, limited to two shell files, while the goal says “ALL terminate sites.” Current source has additional real signals in `resident/agent_loop.py:547-557,1268-1280`, `skills/subagent-launcher/fan.py:89-103`, `fan_process.py:163-225`, `cloud/operator_control.py:70-72`, and `cloud/wrappers/arnold-heartbeat:33-35`. No inventory marks these as covered, probes, non-worker, or intentionally excluded.

**Correction:** make the machine-readable inventory repository-wide; route worker-killing sites through the helper or explicitly document and test each exclusion.  
**Impact:** criterion 3.  
**North Star:** leaves silent death paths and single-scan termination anti-patterns unresolved.
[launch_hermes_agent] done in 156.7s (exit=0)
0

## Raw W2 sequence findings

[launch_hermes_agent] model=codex:gpt-5.6-luna → resolved=openai-codex/gpt-5.6-luna toolsets=['file'] max_tokens=65536 context_budget_tokens=(auto)
[launch_hermes_agent] NOTE: omp gives the full toolset (Bash, Read, Edit, web, …); the file/web/terminal subset is a superset here.
[launch_hermes_agent] cwd=/Users/peteromalley/Documents/Arnold-oracle-nbf
Working...
**SEQ2-1 — Atomic reservation ownership is duplicated and underspecified**  
**Material: yes.** §6 assigns “atomic admission reservation” to NBF-01, then NBF-02 independently assigns “atomic terminal-fingerprint comparison and admission reservation.” Current `IncidentLedger.append_event` (`incident/ledger.py:354-361`) atomically appends only; its read/compare/append lock exists only for maintenance events (`:298-319`). The plan assumes an existing transaction boundary that does not exist.  
**Correction:** NBF-01 freeze schemas plus a ledger transaction/CAS primitive; NBF-02 alone owns the request-specific reservation call. Add a two-process race test, append/lock-failure test, and restart replay test.  
**Impact:** Criteria 4, 7, 8. **North Star:** required for one admission door and no replay races.

**SEQ2-2 — Physical-door proof does not define WBC ordering**  
**Material: yes.** NBF-03 requires admission before final launch, but the current WBC path calls `wbc_dispatch.run` (`workers/_impl.py:7443`); `CommonWorkerDispatchSpec.run` reserves and starts its attempt before invoking the callback (`custody/common_worker_dispatch.py:86-107`). Placing admission inside `_run_step_with_worker_legacy` therefore records a dispatch start before admission. Conversely, placing it outside requires adapting WBC result and failure semantics. Scheduling retries could also be marked completed by WBC rather than deferred.  
**Correction:** Explicitly define whether WBC start is pre-admission evidence or move admission before `wbc_dispatch.run`; typed conditions must neither consume a worker attempt nor emit worker failure/complete events. Add ordered WBC-start/gate/final-launch traces.  
**Impact:** Criteria 1, 2, 6, 7. **North Star:** prevents a second hidden admission door.

**SEQ2-3 — Scheduling-condition propagation remains incomplete**  
**Material: yes.** Current `ExitKind` has no scheduling value (`orchestration/phase_result.py:23-38`), `PhaseResult` has no condition payload (`:330-386`), and `RecoveryPolicy.classify_with_circuit` records a failure before classification (`recovery_policy.py:834-855`). §4.4–4.5 state that scheduling bypasses breakers, but NBF-01, NBF-02, and NBF-06 split the required changes without assigning the end-to-end handler/auto path.  
**Correction:** Freeze condition serialization and phase-result transport in NBF-01; require NBF-02 to wire handler/auto return paths and an early circuit bypass. Add expiry tests proving no breaker increment and no `blocked` transition.  
**Impact:** Criteria 7–8. **North Star:** scheduling must remain scheduling, never synthetic failure.

**SEQ2-4 — Shell dispositions may lack mandatory worker identity**  
**Material: yes.** §4.8 requires every disposition to carry `dispatch_fingerprint`, phase, spec, and worker identity. Current watchdog receipts expose session/run/occurrence data (`cloud/wrappers/arnold-watchdog:2502-2520`), while `ensure-megaplan-watchdog` has only container/pgrep/heartbeat state and directly runs `xargs kill` (`:47-58`). NBF-05 requires complete fields and two scans but does not specify resolution or durable confirmation state for this path.  
**Correction:** Require an explicit receipt/ledger resolver; absent identity must fail closed or use a separately typed non-worker disposition, never fabricate a fingerprint. Add container/watchdog-incarnation confirmation markers and cross-invocation tests.  
**Impact:** Criterion 3. **North Star:** deaths speak and single scans cannot kill.

**SEQ2-5 — Membership digest can silently bypass fingerprint refusal**  
**Material: yes.** §4.6 includes `live_membership_digest` in the terminal fingerprint, so an ordinary catalog refresh can change the fingerprint without an allowlisted `changed_precondition`. That permits semantically identical redispatch.  
**Correction:** Exclude volatile membership observations from the retry identity, or require `provider_recovery_verified` for any digest-only change; add a digest-only negative test.  
**Impact:** Criteria 4–5. **North Star:** blocks unchanged redispatch.

**Material investigation newly required: no.** These are missing ownership and verification contracts. The snapshot is **not yet frozen**.
[launch_hermes_agent] done in 285.8s (exit=0)
0

## Revision contract

Apply every accepted W2 correction and no rejected/non-material suggestion across
the complete plan. Preserve all frozen criteria and authority boundaries.

Specifically reconcile:
- linked child logical dispatches for provider fallback, one final launch each;
- typed post-launch DispatchOutcome owned by dispatch_with_admission;
- semantic CAS key independent of logical ID and volatile live-membership digest;
- atomic route-transition + child-reservation ledger transaction and crash replay;
- receipt context transport to every in-band signal site, with explicit observed/
  non-worker/unknown schemas rather than fabricated identity;
- repository-wide real-signal inventory, worker-kill routing, and tested exclusions;
- CAS primitive versus request-specific reservation ownership;
- WBC intent/admission/final-launch ordering;
- serialized scheduling propagation and early breaker bypass end to end.

Use the simplest design with one scheduling owner, one ledger transaction
authority, one provider/precondition projection, and one signal helper. Keep all
tasks normal/Luna unless new evidence satisfies the full exceptional [XHARD]
threshold. No new research is expected.

Include a concise revision delta, precise batches/dependencies/tests/completion
matrix, and an explicit readiness disposition. End with exactly:
`STABILITY: STABLE`
or, only if blocked by a material evidence question:
`STABILITY: STILL_FORMING — <question>`
