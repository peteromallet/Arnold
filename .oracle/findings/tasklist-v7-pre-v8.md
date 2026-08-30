# PROPOSED — Typed NBF worker admission, disposition, and scheduling control plane

> **Freeze only after fresh pre-execution review.**

## Frozen references

- Settled plan v7 SHA-256: `3e76fc3c9eeb8fbd6580d1217db341c1c3e9f16a4be3552eadddbef2ccd9276f`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Candidate branch: `megado-nbf-guard-0826`
- Protected artifacts and branch-only planning/evolution commits: preserve exactly as specified by `custody.md`.
- The superseded foreign onboarding tasklist is preserved verbatim at `.oracle/findings/foreign-onboarding-tasklist.md` and is excluded from this run.
- Full schemas, transition rules, crash semantics, prohibited patterns, exact-SHA evidence contract, and completion conditions remain authoritative in settled-plan v7, especially §§4–5 and §§10–12. This tasklist does not supersede them.

## Execution and model policy

- Seven ordered tasks: `NBF-01` through `NBF-07`.
- Five natural execution batches:
  1. `NBF-01`
  2. `NBF-02` → `NBF-03`
  3. `NBF-04` → `NBF-05`
  4. `NBF-06`
  5. `NBF-07`
- Every task is **Normal** and must use **GPT-5.6 Luna**.
- User-selection rationale: the contracts and ownership are frozen, and every task has deterministic structural, serialization, replay, ordering, discovery, or static validation. No task meets the exceptional `[XHARD]` threshold.
- **GPT-5.6 Sol is Oracle only:** synchronization judgments, fresh pre-execution review, pre-push acceptance, and final completion judgment. Sol does not execute implementation tasks.
- No model switch is authorized without user approval.
- Huge-run determination: **NO**. This is a bounded 11–13.5-day plan; do not introduce an epic or cumulative big-batch boundaries.
- Commit after each batch passes its Oracle gate. Do not start the next batch before that gate passes.
- Push only `origin/megado-nbf-guard-0826`, and only after the Sol pre-push acceptance gate authorizes the exact reviewed candidate SHA.
- The post-push Sol completion gate verifies the push receipt and exact remote tip.
- Never merge to `main` without explicit user approval.

## Frozen dispatch and terminal semantics

All tasks must preserve these identities and cardinalities:

```text
one dispatch family
  -> exactly one physical door owner
  -> one or more linked logical dispatches
  -> each logical dispatch has one or more admission attempts
  -> each logical dispatch has zero or one final launch
```

- A scheduling condition may cause multiple admission attempts, but no final launch occurs before admission succeeds.
- A fallback, recovery retry, or return-to-primary creates a new logical dispatch linked by parent and authorizing event; it never reuses the parent logical ID.
- Different logical IDs cannot evade reservation uniqueness for the same projection key and semantic fingerprint.
- Nested OMP is physically owned only by `workers/omp.py::run_omp_step`; `_impl.py` delegates without an outer admission hit.
- Every production `run_step_with_worker` call enters `dispatch_with_admission`.
- Production `wbc_dispatch=None` constructs the canonical WBC adapter internally or rejects typedly before any legacy launch.
- Each logical dispatch has at most one controlled final launch.
- No provider-driven child may be created from a no-launch, unresolved, or non-terminal parent.
- No family-wide launch lease may be added.
- Every accepted non-scheduling result reaches the one canonical terminal writer.
- `DispatchOutcome.kind=worker_disposition` is explicit and requires accepted launch state plus canonical disposition, receipt, fingerprint, phase, spec, worker, and timing context.
- It maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)`.
- The canonical disposition is appended before the signal and is never appended again during outcome construction, reconciliation, replay, or terminal projection.
- Worker dispositions are never coerced into ordinary failure or provider exhaustion and never enter provider-degradation policy.

# Batch 1 — Contracts, replay projection, and ledger CAS

## NBF-01 — Freeze schemas and add the single ledger primitive

- **Classification:** Normal
- **Executor:** GPT-5.6 Luna
- **User-selection rationale:** Settled-plan v7 supplies exact schemas, legal transitions, deterministic identities, disposition-to-terminal mapping, and crash/replay tests.
- **Dependencies:** None

### Scope and ownership

Own only:

- typed schemas and strict serialization;
- explicit `DispatchOutcome.kind=worker_disposition`;
- deterministic disposition-to-terminal-outcome mapping and replay validation;
- deterministic incident-ledger replay projections;
- ordinary reservation CAS;
- canonical terminal-outcome writer and projection;
- canonical changed-precondition producers and evidence-binding validation;
- single-use changed-precondition consumption;
- provider-failure-key representation and deterministic keyed-streak replay mechanics;
- probe leases;
- one composite route-transition-and-child-reservation event;
- deterministic post-commit receipt derivation;
- reservation reconciliation;
- durable two-scan confirmation schemas and projection;
- canonical disposition helper and shell CLI contracts.

Do not implement admission callers, scheduling loops, T7 behavior, T8 thresholds or policy, physical-door wiring, controlled launch execution, signal-site wiring, or provider fallback decisions.

### Files and symbols

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

Implement only the NBF-01-owned primitive portions of settled-plan §§4.4–4.13, §4.16, and §§4.19–4.21. Admission, scheduling, controlled-launch execution, T7/T8 policy, and caller wiring remain excluded.

### Acceptance criteria

- Scheduling, no-launch, success, ordinary failure, provider exhaustion, worker disposition, and unresolved launch round-trip strictly through serialization.
- Invalid kind/state combinations reject.
- `no_launch` cannot serialize with `launch_state=accepted`.
- `worker_disposition` cannot serialize without:
  - `launch_state=accepted`;
  - canonical `disposition_id`;
  - admission receipt;
  - semantic fingerprint;
  - phase and selected spec;
  - logical dispatch and worker identity;
  - start and finish timing.
- Worker disposition cannot carry incompatible provider-exhaustion or no-launch state.
- A worker-disposition outcome maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)`.
- Mapping validates exactly one already-committed matching disposition and never re-appends it.
- A worker disposition is never coerced into ordinary failure.
- Duplicate disposition-terminal linkage is idempotent; conflicting linkage or terminal kinds reject.
- Reservation closure and terminal-fingerprint projection occur exactly once for worker disposition.
- Worker disposition breaks provider-exhaustion consecutiveness without entering provider degradation.
- `no_launch` produces no worker terminal event, fingerprint, provider observation, provider-streak mutation, phase failure, or breaker input.
- Worker, observed-death, and non-worker disposition schemas reject incomplete or fabricated identities.
- OOM requires positive cgroup evidence; unknown death remains explicitly unknown.
- TERM and KILL ladder identities are distinct.
- Semantic fingerprint excludes volatile liveness digests and logical/family IDs.
- Route-liveness digest is absent from both semantic-fingerprint and provider-failure-key identity.
- Different logical IDs with the same projection key and semantic fingerprint contend for one reservation.
- Only allowlisted, reason-specific changed-precondition producers may mint changes.
- Producer, evidence, subject, version, before/after, and provider-failure-key binding are validated.
- Forged unequal content IDs or provider-failure-key transitions reject.
- A valid changed-precondition event is consumed at most once.
- `provider_recovery_verified` may authorize one linked same-route child but does not reset or rekey the existing provider-observation streak.
- Another allowlisted changed precondition resets or rekeys provider observations only when its canonical authoritative before/after binding changes the provider-failure key.
- Ordinary two-process reservation contention yields one winner.
- `provider_route_child_reserved` represents route transition and child reservation in one record and contains no child receipt-ID input.
- Receipt identity derives after append and reproduces byte-for-byte after fresh replay.
- Torn or failed writes cannot expose partial transitions, receipts, or projections.
- Every accepted terminal outcome projects fingerprint state before reservation closure.
- Matching accepted `provider_exhausted` outcomes increment the keyed streak.
- A nonmatching accepted `provider_exhausted` outcome rekeys the streak at one.
- Accepted worker success resets the applicable streak and active provider-failure key.
- An intervening accepted ordinary failure or worker disposition breaks exhausted-outcome consecutiveness without becoming provider degradation.
- Probe results and creation or consumption of `provider_recovery_verified` preserve the matching streak.
- Scheduling, no-launch, unresolved launch, time passage, and liveness refresh do not increment, reset, or rekey the provider streak.
- Reconciliation permits only positive `released_no_launch`, recovered terminal outcome, or durable ambiguous hold.
- A recovered worker disposition links one existing canonical disposition and never duplicates disposition or signal evidence.
- Blind release, conflicting reconciliation, and accepted-launch release as no-launch reject.
- Durable two-scan state survives restart and enforces TTL, scan separation, PID/process-start/progress/incarnation equality, single consumption, and replacement/expiry.
- Ledger lock, append, schema, projection-version, and cache failures fail closed.
- Disposition CLI schema validation, acknowledgements, and exit codes match settled-plan §4.21.

### Focused validation

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

### Frozen alignment

- **Goal criteria:** 3, 4, 7, and 8 foundations; lossless disposition mapping, receipt derivation, terminal projection, keyed provider replay, reconciliation, changed-precondition, and two-scan contracts.
- **North Star principle:** “Deaths speak” and “one door per invariant.”
- **Anti-pattern prevented:** anonymous exits, silent death, disposition coercion, duplicate signal evidence, identical-fingerprint redispatch, probe-driven provider-state erasure, and volatile sustained-truth state.

## Batch 1 checkpoint — Sol contract freeze

**PASS only if all are true:**

- Every NBF-01 focused test passes.
- Schema fields and legal transitions match only the NBF-01-owned primitive portions of settled-plan §§4.4–4.13, §4.16, and §§4.19–4.21.
- `DispatchOutcome.kind=worker_disposition` is lossless and maps exactly once to the matching canonical terminal outcome.
- One incident-ledger authority owns reservation, terminal projection, disposition linkage, keyed provider replay, reconciliation, changed-precondition validation/consumption, confirmation, and dispositions.
- Accepted exhausted worker outcomes—not probes, waits, or recovery-authorization events—are the only inputs that create or increment provider observations.
- `provider_recovery_verified` remains single-use retry authorization while preserving the matching streak.
- Success resets the applicable streak; a different-key exhausted outcome rekeys at one; an ordinary failure or worker disposition breaks consecutiveness; only an authoritative provider-failure-key change may otherwise reset or rekey.
- Composite transition and child reservation remain one append with post-commit replay-stable receipt derivation.
- No-launch, unresolved launch, ordinary failure, provider exhaustion, and worker disposition are mechanically distinct.
- No second journal, store, prepare/commit protocol, scheduler, rotator, or policy owner is introduced.
- Crash, contention, replay, torn-write, disposition-linkage, keyed-streak, TTL, incarnation, and single-consumption tests pass.

**Oracle evidence paths:**

- Files and test suites listed under NBF-01.
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- `arnold_pipelines/megaplan/incident/disposition.py`
- Fresh-ledger replay and crash fixtures in transaction, provider-route, reconciliation, terminal-outcome, producer, disposition, and confirmation test modules.
- Focused pytest output.

On PASS: commit Batch 1 before beginning Batch 2.

# Batch 2 — Canonical admission, generic scheduling, physical doors, and authority proof

## NBF-02 — Expand admission and implement generic `dispatch_with_admission`

- **Classification:** Normal
- **Executor:** GPT-5.6 Luna
- **User-selection rationale:** Admission, controlled launch, typed outcome transport, reconciliation, and T7 behavior have frozen contracts and injectable fixtures.
- **Dependencies:** NBF-01

### Scope and ownership

Own:

- canonical admission request, receipt, refusal, and execution-context path;
- request-specific use of NBF-01 reservation primitives;
- OMP and native route-applicable positive liveness;
- generic `dispatch_with_admission`;
- controlled final-launch sequencing;
- T7 memory-cooldown scheduling;
- typed `DispatchOutcome` intake, including `worker_disposition`;
- truthful `no_launch` handling;
- final-launch exception normalization;
- canonical terminal-outcome writer integration;
- disposition-to-terminal linkage without duplicate disposition append;
- unresolved-reservation reconciliation integration;
- lossless scheduling, no-launch, and worker-disposition transport through handlers and `auto.py`;
- early breaker bypass for scheduling/no-launch only;
- generic authorized linked-child request construction.

Do not implement provider thresholds, provider probing policy, degradation, fallback selection, scalar policy, return-to-primary, signal-site wiring, two-scan policy calls, or T8 route races.

### Files and symbols

- `cloud/runtime_attestation.py::require_production_worker_dispatch_runtime`
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

### Acceptance criteria

- `require_production_worker_dispatch_runtime` is the only admission authority and returns one receipt proving every settled invariant.
- Receipt IDs derive only from committed reservation events.
- Chain helpers are non-authoritative primitives.
- Production rejects before WBC/client/process/RPC construction when source, runtime, manifest, seed, interpreter, timeout, memory, route liveness, or ledger proof is absent or invalid.
- OMP requires bounded, valid, exact `omp models --json` membership.
- Native routes require positive proof from the actual native backend/runtime/model seam without being forced into OMP or adding speculative network checks.
- Static catalog acceptance of `openrouter/stealth/ox-alpha` remains, while joint live admission typedly rejects it before client construction.
- Same fingerprint across logical IDs yields one reservation; liveness-only changes do not bypass refusal.
- Only a canonical, evidence-bound, single-use change may authorize redispatch.
- `dispatch_with_admission` is the sole scheduling loop.
- T7 cooldown may cause multiple admission attempts, idempotent retry-wait evidence, and injected sleep, but zero launches, WBC attempts, or failures before admission.
- Scheduling expiry reaches `PhaseResult` without failure accounting, breaker mutation, or `blocked`.
- `ControlledFinalLaunch` persists `not_started`, `entered`, and `accepted` in order and exposes the only launch primitive.
- Each logical dispatch invokes its final-launch closure at most once.
- Positive no-entry/no-acceptance evidence reconciles before returning `no_launch`.
- Missing, contradictory, post-entry, or post-acceptance evidence stays unresolved until canonical evidence exists.
- Accepted success, ordinary failure, provider exhaustion, and worker disposition each record one canonical terminal event before consumer projection.
- Typed worker disposition retains its `disposition_id`, receipt, fingerprint, phase/spec, worker, timing, and accepted-launch context end to end.
- The terminal writer validates the already-recorded disposition and never appends it twice.
- Worker disposition is never serialized or consumed as ordinary failure and never enters provider degradation.
- Worker dispositions retain their existing typed disposition and breaker semantics after terminal projection; they do not use the scheduling/no-launch breaker bypass.
- Outcome-append or disposition-link failure retains an unresolved reservation.
- A linked child requires a canonical terminal parent plus durable authorization; no-launch and unresolved parents are insufficient.
- Execution context and launch state persist before supervision begins.
- No T8 provider policy is implemented.

### Focused validation

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_dispatch_with_admission.py \
  tests/cloud/test_chain_admission.py \
  tests/cloud/test_worker_dispatch_context.py \
  tests/cloud/test_dispatch_reconciliation.py \
  tests/cloud/test_controlled_final_launch.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
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

### Frozen alignment

- **Goal criteria:** 1, 3, 4, 5, and 7; generic foundation for 2 and 8.
- **North Star principle:** models are admitted, not assumed; deaths remain typed through terminal closure.
- **Anti-pattern prevented:** stale model assumptions, duplicate preflights, blind relaunch, lossy disposition coercion, duplicate disposition append, and cooldown treated as worker failure.

## NBF-03 — Wire the three doors and prove generic launch cardinality

- **Classification:** Normal
- **Executor:** GPT-5.6 Luna
- **User-selection rationale:** Door ownership, WBC ordering, no-WBC closure, and bypass prevention are verifiable with structural spies, typed traces, and a targeted static checker.
- **Dependencies:** NBF-02

### Scope and ownership

Own only:

- the three physical-door bindings;
- nested/direct OMP ownership;
- chain delegation;
- production no-WBC closure;
- WBC intent/admission/start ordering;
- controlled-adapter placement;
- admission-attempt and final-launch traces;
- generic scheduling/no-launch/worker-disposition traces;
- receipt-context propagation through doors;
- the admission-authority bypass checker.

Do not implement T8 observation, probe, degradation, fallback, scalar, or return policy.

### Files and symbols

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

### Acceptance criteria

- Native non-OMP, direct OMP, nested OMP, babysitter, and chain-originated production launches each have exactly one physical admission owner.
- Nested OMP totals one admission hit in `run_omp_step`; `_impl.py` contributes none.
- Every production `run_step_with_worker` call enters `dispatch_with_admission`.
- `wbc_dispatch=None` constructs the canonical adapter or rejects before legacy launch.
- `_run_step_with_worker_legacy` is development-only or only the admitted final-launch closure.
- Optional WBC intent precedes admission, but WBC attempt start occurs only after reservation, derived receipt, and `not_started`.
- Scheduling and truthful no-launch create no WBC start, failure, or completion.
- Accepted worker-disposition traces preserve the disposition ID and show one terminal projection after record-before-signal.
- Each logical ID has at most one final launch; authorized children use a new linked logical ID.
- Door removal, duplicate outer admission, chain bypass, no-WBC bypass, WBC prestart, direct raw launch access, or a second launch fails.
- Structural tests replace only final spawn/RPC/WBC/managed-command seams and do not use `MEGAPLAN_MOCK_WORKERS=1`.
- Different-fingerprint dispatches remain concurrent under existing semantics; no family lease is added.
- `scripts/check_worker_admission_authority.py --check` detects raw authority calls, resolvable aliases, chain-local preflight, direct chain spawn, no-WBC legacy delegation, WBC-before-admission, nested double admission, and raw launch access.
- The checker passes across all three doors and chain origins.
- The three door files contain no raw refresh/require calls.
- `/workspace/.cloud-hot-env` is not mutated.
- No T8 policy appears in NBF-02/NBF-03 surfaces beyond the frozen extension interface and generic traces.

### Focused validation

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

### Frozen alignment

- **Goal criteria:** 1, 2, 5, and 6.
- **North Star principle:** one door per invariant.
- **Anti-pattern prevented:** duplicate preflights, nested double gating, mock early-return evidence, WBC-before-admission, production legacy bypass, and lossy door-level terminal traces.

## Batch 2 checkpoint — Sol admission and door-ownership gate

**PASS only if all are true:**

- All NBF-02 and NBF-03 focused tests pass, including the 42 existing runtime-attestation tests.
- Canonical admission jointly validates translation, catalog where applicable, family, positive route liveness, source/runtime, seed/interpreter, timeout, memory, fingerprint, and reservation.
- Static `ox-alpha` acceptance plus live joint rejection is demonstrated.
- Native positive proof and typed missing-proof refusal are demonstrated.
- T7 schedules without WBC, failure, breaker, or block effects.
- Controlled launch sequencing and reconciliation cover pre-entry, pre-acceptance, accepted, ambiguous, append-failure, restart, and identical retry after truthful no-launch.
- Accepted worker disposition remains typed and links one prior canonical disposition to one terminal outcome.
- Every accepted non-scheduling terminal result records once before consumer projection.
- Native, direct/nested OMP, babysitter, chain, no-WBC, and authorized-child structural traces satisfy frozen cardinality.
- The authority checker and secondary raw-symbol scan pass.
- No second scheduler or admission authority, family lease, raw production launch path, duplicate disposition append, or T8 policy owner exists.

**Oracle evidence paths:**

- NBF-02 and NBF-03 files and test suites.
- `tests/cloud/test_worker_dispatch_spy.py`
- `tests/cloud/test_worker_admission_authority.py`
- `scripts/check_worker_admission_authority.py`
- Ordered WBC, launch, and typed disposition traces.
- Chain caller inventory and `ox-alpha`/native-liveness fixtures.
- Checker JSON diagnostics and focused pytest output.

On PASS: commit Batch 2 before beginning Batch 3.

# Batch 3 — Python and shell death closure with generated inventory

## NBF-04 — Route all repository Python signal paths through the helper

- **Classification:** Normal
- **Executor:** GPT-5.6 Luna
- **User-selection rationale:** Python signal sites, context transport, disposition-to-terminal linkage, ladder behavior, and durable confirmation are mechanically discoverable and testable.
- **Dependencies:** NBF-01, NBF-02, NBF-03

### Files and symbols

- `skills/subagent-launcher/launch_omp_agent.py`
- `skills/subagent-launcher/fan.py`
- `skills/subagent-launcher/fan_process.py`
- `resident/subagent.py`
- `resident/agent_loop.py`
- `cloud/operator_control.py`
- `auto.py` orphan recovery
- `incident/disposition.py`
- `orchestration/phase_result.py`
- Focused launcher, fan, resident, operator, confirmation, terminal-outcome, reconciliation, and incarnation tests
- New `tests/arnold_pipelines/megaplan/test_python_signal_inventory.py`

### Acceptance criteria

- Launcher timeout uses explicit process control and records at the kill site before signaling, not only after `TimeoutExpired`.
- Every resident SIGINT, SIGTERM, and SIGKILL records first; TERM→wait→KILL remains intact with distinct records.
- Every discovered Python signal is classified as worker kill, observed death, non-worker lifecycle signal, probe, or narrow tested exclusion.
- Worker signals resolve `WorkerExecutionContextRef`, receipt, fingerprint, PID, and process-start identity.
- Missing or inconsistent in-band context or append failure leaves a live process unsignaled.
- After a recorded signal produces or confirms an admitted accepted worker death, the path produces or recovers `DispatchOutcome(kind=worker_disposition)`.
- That outcome carries the canonical disposition ID and exact receipt, fingerprint, phase, selected spec, worker, timing, and accepted-launch context.
- The canonical terminal writer appends one `worker_terminal_outcome(outcome_kind=worker_disposition)` and closes the reservation once.
- The pre-signal disposition is never duplicated during outcome creation, reconciliation, replay, or terminal projection.
- Worker disposition is never coerced into ordinary failure or provider exhaustion.
- Worker disposition breaks provider-exhaustion consecutiveness without entering degradation.
- Crash after disposition append, after signal, and before terminal-outcome append is replay and reconciliation safe.
- Timeout return code and metadata remain compatible.
- TERM-only, TERM→KILL, and follow-up SIGINT paths are covered.
- Sustained-proof Python kills consume one valid durable two-scan confirmation.
- Confirmation survives restart and rejects PID reuse, progress advance, expiry, and supervisor/container incarnation change.
- Positive cgroup evidence is required for OOM observations.
- Unknown already-dead processes remain unknown without fabricated worker fields.
- Non-worker lifecycle signals never impersonate workers.
- State summaries derive from canonical ledger events.
- Python classifications feed the canonical repository-wide inventory completed by NBF-05.

### Focused validation

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py \
  tests/arnold_pipelines/megaplan/test_python_signal_inventory.py \
  tests/resident/test_managed_provider_agent_runner.py
```

### Frozen alignment

- **Goal criterion:** 3.
- **North Star principle:** every admitted worker death carries its killer’s identity through a typed record and typed terminal outcome.
- **Anti-pattern prevented:** anonymous exit codes, signal-before-record, disposition coercion, duplicate signal evidence, fabricated OOM/context, and single-scan kill decisions.

## NBF-05 — Instrument shell signals and generate the complete inventory

- **Classification:** Normal
- **Executor:** GPT-5.6 Luna
- **User-selection rationale:** Shell ordering, exact targeting, disposition linkage, two-scan persistence, and non-circular inventory freshness have deterministic oracles.
- **Dependencies:** NBF-04

### Files and symbols

- `cloud/wrappers/arnold-watchdog`
- `cloud/wrappers/arnold-heartbeat`
- `cloud/systemd/ensure-megaplan-watchdog`
- Every additional Python or shell signal site found by live discovery
- `incident/disposition.py` CLI
- New `scripts/generate_nbf_signal_inventory.py`
- New canonical `docs/nbf-signal-inventory.json`
- `tests/cloud/test_watchdog_wrappers.py`
- `tests/cloud/test_watchdog_dispositions.py`
- New `tests/cloud/test_repository_signal_inventory.py`
- Confirmation restart/incarnation fixtures

### Worker-signal sequence

1. Resolve exact PID/process group and process-start identity.
2. Resolve admission-receipt context.
3. Resolve watchdog/container incarnation identity.
4. Append or resume durable first-scan confirmation.
5. Require a separated second observation with the identical confirmation key.
6. Consume confirmation atomically.
7. Invoke the disposition CLI with the consumed confirmation reference.
8. Verify exit 0 and matching acknowledgement.
9. Invoke the stub-able signal primitive.
10. When the admitted accepted worker’s death is consumed, produce or recover typed `DispatchOutcome(kind=worker_disposition)`.
11. Route that outcome through the canonical terminal writer without duplicating the disposition.

### Inventory contract

`docs/nbf-signal-inventory.json` contains:

```text
schema_version
generator_version
discovery_rules_version
discovery_rules
source_inputs_sha256
entries
```

`source_inputs_sha256` is deterministic over:

- digest version;
- generator version;
- discovery-rule version;
- normalized discovery rules;
- normalized, bytewise-sorted repository-relative paths of discovered signal-bearing source inputs;
- normalized content SHA-256 for each input.

It excludes:

- `docs/nbf-signal-inventory.json` itself;
- git commit or repository-revision identity;
- any embedded artifact self-digest;
- validation/evidence files unless they are themselves discovered production signal-bearing inputs.

The artifact’s own SHA-256 is recorded only as external evidence after the exact final candidate SHA is frozen.

### Acceptance criteria

- Every live-discovered repository real signal or probe has exactly one reviewed inventory row.
- Every worker kill is helper-routed.
- Each admitted accepted worker death has a lossless typed worker-disposition outcome and one canonical disposition-linked terminal outcome.
- Worker disposition is never coerced into ordinary failure and its canonical disposition is never appended twice.
- Worker signals resolve exact process identity and receipt context, obtain and consume required durable confirmation, receive successful disposition-CLI acknowledgement, and only then invoke the signal primitive.
- Non-worker lifecycle signals record typed lifecycle context before signaling.
- First scans never signal when sustained proof is required.
- PID, process-start, relevant progress, supervisor/container incarnation, or TTL change resets or replaces confirmation.
- Concurrent second scans authorize at most one signal.
- TERM and KILL use distinct confirmation/disposition identities when sustained proof applies.
- CLI, ledger, confirmation, acknowledgement, or context failure produces zero signal calls.
- Terminal-link validation failure leaves an accepted reservation unresolved and never fabricates or duplicates disposition evidence.
- Probes are mechanically distinguished from signals.
- Exclusions are narrow, documented, tested, and Oracle-reviewed.
- `scripts/generate_nbf_signal_inventory.py` performs live Python AST and narrow shell discovery, deterministic IDs/order, classification merge, vanished/duplicate/unclassified detection, digest computation, and `--check`.
- `source_inputs_sha256` is deterministic and non-circular.
- A discovered signal-bearing source change, generator-version change, or discovery-rule-version change makes `--check` fail until regeneration and review.
- The inventory contains no repository commit, embedded git revision, or self-digest.
- Committing the generated inventory alone does not invalidate its source-input digest.
- No worker is killed from a single stale scan, timestamp, PID presence, or `completed.json`.
- Ensure-watchdog resolves the active installed source/runtime.
- All wrapper syntax checks pass.
- No unreviewed worker-kill exclusion remains.

### Focused validation

```bash
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-heartbeat
bash -n arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog
python scripts/generate_nbf_signal_inventory.py --check
pytest -q \
  tests/cloud/test_watchdog_dispositions.py \
  tests/cloud/test_watchdog_wrappers.py \
  tests/cloud/test_repository_signal_inventory.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_python_signal_inventory.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
```

### Frozen alignment

- **Goal criterion:** 3 and repository-wide signal closure.
- **North Star principle:** deaths speak; SIGKILL, timeout, terminate, and restack all identify their killer.
- **Anti-pattern prevented:** silent shell death, duplicate disposition evidence, wrapper-local confirmation truth, one-scan wedge/restack decisions, incomplete inventories, and circular commit-bound inventory metadata.

## Batch 3 checkpoint — Sol death and inventory gate

**PASS only if all are true:**

- All NBF-04 and NBF-05 focused tests and shell syntax checks pass.
- Live repository discovery and `docs/nbf-signal-inventory.json` agree exactly.
- `source_inputs_sha256` is deterministic, non-circular, and fresh.
- The inventory contains no git revision or self-digest.
- Every real signal is classified; every worker kill records before signaling.
- Every admitted accepted worker death preserves `worker_disposition` through one canonical terminal outcome.
- No outcome construction or terminal projection appends the disposition twice.
- Sustained-proof signals require a matching, unexpired, consumed ledger confirmation.
- Restart, TTL, PID reuse, process-start change, progress advance, incarnation change, duplicate scan, concurrent scan, TERM→KILL, and disposition-to-terminal recovery scenarios pass.
- Missing context, append failure, confirmation failure, or CLI failure leaves live victims unsignaled.
- Disposition-link failure leaves an accepted reservation unresolved without fabricating evidence.
- Observed-death and non-worker records do not fabricate worker identity or OOM.
- No stale artifact, circular revision field, unreviewed exclusion, silent signal path, or wrapper-local authoritative confirmation remains.

**Oracle evidence paths:**

- `docs/nbf-signal-inventory.json`
- `scripts/generate_nbf_signal_inventory.py`
- `arnold_pipelines/megaplan/incident/disposition.py`
- Python and shell files listed in NBF-04/NBF-05
- `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
- `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
- `tests/arnold_pipelines/megaplan/test_python_signal_inventory.py`
- `tests/cloud/test_repository_signal_inventory.py`
- `tests/cloud/test_watchdog_dispositions.py`
- Confirmation, restart, reconciliation, and incarnation fixtures
- `source_inputs_sha256`, generator/discovery-rule versions, external inventory SHA-256 evidence, `--check`, syntax, and focused pytest output

On PASS: commit Batch 3. NBF-06 remains blocked until this checkpoint and every earlier checkpoint pass.

# Batch 4 — Sole T8 provider-resilience implementation

## NBF-06 — Implement T8 through the shared seam and existing fallback door

- **Classification:** Normal
- **Executor:** GPT-5.6 Luna
- **User-selection rationale:** Provider observation, keyed worker-outcome streaks, probe authorization, fallback, scalar hold, return, crash, and race behavior have frozen schemas and deterministic fixtures.
- **Dependencies:** NBF-01, NBF-02, NBF-03, NBF-04, NBF-05
- **Hard synchronization barrier:** Do not begin until Batches 1–3 have passed their Sol gates and been committed.

### Scope and ownership

Solely own:

- typed provider-exhaustion production after accepted launch;
- provider observations;
- provider-failure-key derivation use and consecutive accepted-worker-outcome policy;
- bounded hold/probe policy;
- two-matching-worker-observation degradation threshold;
- evidence-bound same-route recovery without probe-driven streak reset;
- configured fallback selection;
- scalar-pin behavior;
- linked fallback and return decisions;
- composite transition use;
- provider replay, crash, race, and execute prohibitions.

Use NBF-01 ledger/projection/CAS and NBF-02 scheduling/launch seams. Do not create a scheduler, admission authority, terminal writer, changed-precondition bypass, rotator, projection, or journal.

### Files and symbols

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

### Acceptance criteria

- One accepted exhausted logical dispatch records one `worker_terminal_outcome(outcome_kind=provider_exhausted)` and one provider observation.
- Accepted exhausted worker outcomes—not probes, waits, probe-success evidence, recovery-authorization events, ordinary failures, or worker dispositions—form the consecutive provider-observation streak.
- Internal retry chatter remains evidence and never increments observations multiple times.
- Provider exhaustion is never also recorded as ordinary failure.
- Auth, quota, rate limit, unsupported model, context-window, malformed output, schema, and internal errors remain ordinary failures.
- Worker disposition retains its distinct typed path and never enters provider degradation.
- Raw English stderr never drives provider policy.
- The first matching accepted exhausted worker outcome establishes streak one, holds, and probes; it does not degrade or rotate.
- Time passage, sleep, membership refresh, liveness-digest change, and probe success alone cannot authorize an identical retry or reset/rekey the streak.
- One valid probe lease exists; failed probes launch nothing and leave the streak unchanged.
- A passed probe feeds the canonical provider-recovery producer without changing the provider-failure key or streak.
- Exactly one evidence-bound, single-use `provider_recovery_verified` event may authorize a linked same-route child.
- Creation and consumption of `provider_recovery_verified` preserve the matching streak.
- Forged changed-precondition content identities or provider-failure-key transitions reject.
- No-launch or unresolved parents create no observation-driven child.
- If the authorized linked child is accepted and records a matching `provider_exhausted` outcome, it is observation two and may establish `provider_degraded`.
- Accepted worker success resets the applicable streak and active provider-failure key.
- A different-key accepted exhausted outcome rekeys the streak at one.
- An intervening accepted ordinary failure or worker disposition breaks exhausted-outcome consecutiveness without becoming provider degradation.
- Another allowlisted durable changed precondition resets or rekeys the streak only when its canonical authoritative before/after identity changes the provider-failure key.
- A key-preserving changed precondition may authorize semantic redispatch but cannot erase provider observations.
- The canonical provider-failure key remains phase, normalized selected spec, typed provider failure class, and authoritative provider epoch identity.
- `_advance_configured_spec_fallback` is the only configured alternate-selection door.
- Fallback and return targets pass canonical joint admission.
- Rejected targets create no transition, child reservation, receipt, WBC attempt, client, RPC, or launch.
- Accepted flip and return each use one `provider_route_child_reserved` composite event.
- Child receipt derives after commit and is byte-identical after replay.
- Route transition supplies the canonical target provider epoch/key binding and cannot inherit a mismatched source-route streak.
- Scalar pins hold/probe without widening to historical last-known-good.
- Scheduling never reaches failure/breaker accounting or `blocked`.
- Genuine repeated internal errors retain existing breaker behavior.
- Execute and loop-execute fallback advancement remain prohibited.
- Crash injection and two-process races yield one route, one observation per exhausted logical dispatch, one keyed streak, one probe lease, and at most one authorized child.
- Replay preserves streak one across passed probe and creation or consumption of `provider_recovery_verified`.
- Replay allows only the authorized child’s accepted worker outcome to increment, rekey, break, or reset that streak.
- Unresolved reservations block route advancement.
- Cache loss or mismatch repairs from the ledger.
- No T8 implementation remains in NBF-02/NBF-03 beyond generic extension and tracing contracts.

### Focused validation

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

### Frozen alignment

- **Goal criterion:** 8, while preserving criteria 3, 4, 5, and 7.
- **North Star principle:** recovery consumes typed killer/failure evidence before retrying the same fingerprint.
- **Anti-pattern prevented:** redispatch after unchanged provider failure, probe-driven streak reset, stderr-driven policy, duplicated rotators, double-recorded exhaustion, disposition misclassification, and scheduling conditions treated as failures.

## Batch 4 checkpoint — Sol T8 gate

**PASS only if all are true:**

- Every NBF-06 focused test passes.
- NBF-06 began only after NBF-01 through NBF-05 passed.
- Accepted and canonically recorded exhausted worker outcomes are the sole source of provider observations and the only events that create or increment an exhausted-outcome streak.
- The first matching exhausted outcome establishes streak one.
- Passed probe and `provider_recovery_verified` creation/consumption preserve it.
- A matching accepted exhaustion from the authorized child is observation two and may establish degradation.
- Worker success resets the applicable streak.
- A different-key exhausted outcome rekeys at one.
- An ordinary failure or worker disposition breaks consecutiveness without becoming degradation.
- Another changed precondition resets or rekeys observations only when canonical authoritative before/after evidence changes the provider-failure key.
- Probe success, time passage, sleep, membership refresh, and liveness changes cannot reset or rekey observations.
- First observation, probe recovery, second matching worker observation, degradation, configured fallback, scalar hold, and return-to-primary follow settled-plan §§4.14 and 4.16–4.17.
- Recovery authorization is evidence-bound and single-use.
- Route transition and child reservation remain one composite append with replay-stable post-commit receipt identity.
- Provider scheduling never reaches generic breakers or blocks the plan.
- Internal errors still reach ordinary breakers.
- Execute/loop-execute fallback remains prohibited.
- Crash, replay, cache-loss, torn-write, probe-lease, keyed-streak, observation, disposition-interleaving, and child-reservation races pass.
- No second scheduler, provider projection, rotator, journal, terminal writer, or policy copy exists.

**Oracle evidence paths:**

- `tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py`
- `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
- Transaction, terminal, producer, reconciliation, fallback, disposition, breaker, and execution-policy test modules
- T8 policy module and listed file edits
- Provider event/replay fixtures, keyed-streak transition evidence, disposition-interleaving evidence, composite-event crash matrix, and focused pytest output

On PASS: commit Batch 4 before beginning final integration.

# Batch 5 — Fresh-base integration, exact-SHA validation, independent review, and guarded delivery

## NBF-07 — Rebase, freeze candidate, validate, review, and push

- **Classification:** Normal
- **Executor:** GPT-5.6 Luna
- **User-selection rationale:** Final work is bounded integration: custody verification, rebase, deterministic regeneration, exact-clean-SHA validation, evidence collation, independent review, Oracle gates, and guarded push.
- **Dependencies:** NBF-01 through NBF-06
- **Authoritative validation owner:** NBF-07 alone owns the authoritative broad post-rebase validation.

### Work

1. Commit accepted implementation batches in the candidate tree.
2. Verify custody commits and protected artifacts.
3. Refresh and rebase:

```bash
git fetch origin main --prune
git rebase origin/main
```

4. Resolve conflicts by composing with current `main`; do not discard protected or unrelated user work.
5. Complete every post-rebase source, test, checker, wrapper, and integration change.
6. Regenerate and manually review `docs/nbf-signal-inventory.json`:
   - no embedded git or repository revision;
   - no self-digest;
   - deterministic `source_inputs_sha256`;
   - generated inventory excluded from its own source-input digest.
7. Complete any resulting generated-artifact, checker, or integration correction.
8. Commit every final candidate-content change.
9. Require a clean worktree while preserving protected custody artifacts exactly as specified by `custody.md`.
10. Record:
    - exact candidate commit SHA;
    - immutable source-base SHA;
    - candidate branch;
    - clean-tree proof.
11. Create a durable run-named evidence root outside candidate content, named by the run and candidate SHA.
12. Against that exact clean candidate SHA, with no candidate mutation, run:
    - signal-inventory `--check`;
    - admission-authority checker;
    - wrapper syntax checks;
    - secondary raw-preflight scan;
    - authoritative broad pytest suite exactly once.
13. Store command lines, outputs, statuses, timings, and result digests only in the external evidence root.
14. Capture:
    - source and exact candidate SHAs;
    - clean-tree proof before validation and before review;
    - exact validation result;
    - dispatch-family, logical-ID, parent-ID, door, admission-attempt, reservation, derived-receipt, WBC, `not_started`, final-launch-entry, acceptance, reconciliation, and terminal-outcome traces;
    - explicit worker-disposition trace from disposition append → signal → `DispatchOutcome(kind=worker_disposition)` → one linked terminal outcome → reservation closure;
    - proof that worker disposition is never coerced to ordinary failure or provider exhaustion and its disposition is never appended twice;
    - chain caller inventory;
    - production no-WBC rejection/internal-adapter evidence;
    - OMP and native route-applicable liveness evidence;
    - expired-ID discrimination evidence;
    - fingerprint and cross-logical-ID CAS races;
    - canonical changed-precondition producer and forged-event rejection evidence;
    - provider-failure-key derivation and authoritative before/after binding evidence;
    - first exhausted outcome → passed probe → preserved streak → single-use recovery authorization → matching exhausted child → second observation/degradation trace;
    - success-reset, different-key rekey, key-changing precondition reset/rekey, key-preserving precondition no-reset, ordinary-failure non-degradation, and worker-disposition non-degradation traces;
    - composite-event and receipt-derivation crash matrix;
    - reservation-reconciliation matrix, including recovered disposition;
    - no-launch identical-redispatch and restart evidence;
    - pre-entry, pre-acceptance, post-acceptance, disposition-link failure, ambiguous, outcome-append-failure, and restart evidence;
    - receipt-context propagation evidence;
    - durable two-scan restart, TTL, PID-reuse, progress-reset, incarnation-reset, and concurrent-consumption evidence;
    - generated signal inventory path;
    - `source_inputs_sha256`;
    - generator/discovery-rule versions;
    - external inventory SHA-256;
    - freshness result;
    - proof that the inventory contains no git revision or self-digest;
    - CLI and record-before-signal results;
    - targeted authority-checker result;
    - T8 replay/interleaving results;
    - breaker snapshots;
    - secondary negative raw-preflight scan;
    - shell syntax results;
    - criterion-completion table.
15. Reconfirm that candidate SHA and worktree remain unchanged after validation.
16. If any candidate mutation occurred, invalidate the evidence and restart from regeneration as applicable, commit, clean-tree verification, SHA recording, validation, independent review, and Sol pre-push judgment.
17. Assign one independent GPT-5.6 Luna reviewer to the complete external evidence for the exact candidate SHA.
18. Reconfirm no candidate mutation after independent review.
19. Submit the exact candidate SHA, evidence root, and Luna verdict to GPT-5.6 Sol for a pre-push acceptance gate.
20. If Sol rejects, make the required changes and restart the full commit → validation → review cycle.
21. If Sol accepts, push exactly the reviewed candidate SHA to `refs/heads/megado-nbf-guard-0826`; do not commit, regenerate, format, or otherwise mutate candidate content.
22. If rebase rewrote a published branch, verify the expected old remote tip and use `--force-with-lease`, never unguarded force.
23. Record the explicit refspec, push command result, push receipt, and verified remote tip in the external evidence root.
24. Verify mechanically that the remote branch tip equals the exact reviewed candidate SHA.
25. Do not rerun broad or paid validation after push when the remote tip is byte-identical to the accepted SHA.
26. Submit push receipt and remote-tip evidence to Sol for final completion judgment.
27. Stop before merging and request explicit user approval.

### Acceptance criteria

- Fresh fetch/rebase succeeds with custody intact.
- Every post-rebase source, test, integration, checker, wrapper, and generated-artifact change is complete before the final candidate commit.
- Generated signal inventory is current and manually reviewed before commit.
- Inventory contains deterministic `source_inputs_sha256` and no git revision or self-digest.
- Committing the inventory does not invalidate its source-input identity.
- All implementation and generated artifacts are committed before candidate SHA recording.
- Worktree is exactly clean when candidate SHA is frozen and remains unchanged through validation, review, acceptance, and push.
- Inventory `--check`, authority checker, secondary raw-preflight scan, wrapper syntax, and authoritative broad suite run against that exact candidate SHA.
- Validation and review artifacts live only in a durable run-named evidence root outside candidate content.
- Criteria 1–8 and every cross-cutting completion row in settled-plan §10 have binary PASS evidence.
- All 42 existing runtime-attestation tests remain green.
- Accepted worker deaths preserve `worker_disposition` from record-before-signal evidence through one terminal outcome and one reservation closure.
- No worker disposition is coerced or double-appended.
- T8 evidence proves accepted exhausted worker outcomes alone form the streak; probe/recovery authorization preserves it; the matching authorized child’s exhaustion may be observation two; success resets; and only an authoritative provider-failure-key change otherwise resets or rekeys.
- No box-only or deployed-but-uncommitted behavior exists.
- Independent Luna review explicitly accepts the exact candidate SHA and evidence root.
- Sol pre-push gate explicitly accepts and authorizes that exact candidate SHA.
- Any mutation restarts commit, validation, independent review, and Sol acceptance.
- Push sends exactly the reviewed SHA to `origin/megado-nbf-guard-0826`.
- Guarded `--force-with-lease` is used when published history was rewritten.
- Verified remote tip equals the reviewed candidate SHA.
- Sol final completion gate accepts push receipt and remote-tip evidence.
- No merge to `main` occurs.

### Authoritative exact-SHA validation

These commands run only after all candidate content is committed, the worktree is clean, the exact candidate SHA is recorded, and the external evidence root exists:

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

No candidate-content mutation is permitted after these checks begin. Their logs and result digests belong only in the external evidence root.

### Frozen alignment

- **Goal criteria:** authoritative completion of 1–8 and guarded delivery.
- **North Star principle:** fixes ship through the fixer contract; deployed-only or uncommitted fixes do not exist.
- **Anti-pattern prevented:** stale-SHA validation, self-invalidating generated metadata, evidence that mutates its subject, lossy disposition closure, judgment-only health claims, unguarded force-push, and unauthorized merge.

## Batch 5 checkpoint — Final Sol completion gate

**PASS only if all are true:**

- NBF-07 acceptance criteria and complete settled-plan §12 completion conditions are satisfied.
- All final candidate content was committed before validation.
- The worktree was clean when the exact candidate SHA was frozen and remained unchanged.
- Inventory freshness, authority checker, shell syntax, secondary grep, and authoritative pytest suite passed against that exact SHA.
- Validation and review evidence resides outside candidate content.
- `source_inputs_sha256` is deterministic, non-circular, and verified after commit.
- Evidence proves one admission authority, one scheduler, one ledger/CAS/terminal authority, one lossless disposition-to-terminal mapping, one keyed provider projection, one fallback-selection door, one disposition helper, one confirmation projection, one authority checker, one generated signal inventory, and one final candidate SHA.
- Worker-disposition evidence proves:
  - the canonical disposition is committed before signal;
  - accepted worker death produces or recovers `DispatchOutcome(kind=worker_disposition)`;
  - receipt, fingerprint, phase, spec, worker, timing, and disposition identity remain intact;
  - terminal projection maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)`;
  - disposition evidence is never appended twice;
  - reservation closure occurs once;
  - replay and reconciliation are idempotent;
  - disposition is never coerced into ordinary failure or provider exhaustion;
  - disposition breaks exhausted-outcome consecutiveness without entering degradation.
- Provider-streak evidence proves:
  - accepted exhausted worker outcomes alone create or increment the streak;
  - the first matching outcome establishes streak one;
  - probe success and `provider_recovery_verified` creation/consumption preserve it;
  - the authorized matching child’s accepted exhaustion may be observation two and establish degradation;
  - worker success resets it;
  - a different-key exhausted outcome rekeys at one;
  - ordinary failures and dispositions break consecutiveness without becoming degradation;
  - only a canonical authoritative provider-failure-key change otherwise resets or rekeys it;
  - time passage, sleep, membership refresh, liveness changes, probe success, and recovery authorization cannot erase it.
- CAS and single-use recovery authorization, fallback/return transitions, composite atomicity, replay/race safety, and breaker isolation pass.
- No production no-WBC, chain, WBC-ordering, nested-OMP, raw-launch, signal, fingerprint, reconciliation, terminal-mapping, or provider-policy bypass remains.
- Independent Luna review and Sol pre-push gate name and accept the exact candidate SHA before delivery.
- Any post-freeze mutation restarted the complete local cycle.
- Candidate-branch push succeeds using the exact reviewed SHA.
- Remote tip is mechanically verified equal to that SHA.
- Final Sol completion judgment accepts push receipt and remote-tip evidence.
- `main` remains unmerged pending explicit user approval.

**Oracle evidence paths:**

- Rebased branch diff and immutable source/candidate SHAs
- Clean-tree proofs before validation, review, and push
- External run-named evidence root
- All validation paths and outputs listed under NBF-07
- `docs/nbf-signal-inventory.json`
- `source_inputs_sha256`
- Generator and discovery-rule versions
- External inventory artifact SHA-256
- Authority-checker diagnostics
- Complete criterion table and structural, disposition-linkage, replay, and crash evidence
- Provider-failure-key, keyed-streak, probe-preservation, authorized-child, success-reset, rekey, disposition-break, and breaker-isolation evidence
- Independent Luna review naming the candidate SHA
- Sol pre-push acceptance naming the candidate SHA
- Explicit push refspec and guarded lease evidence if applicable
- Push receipt and exact remote-tip verification
- Final Sol completion judgment

On local pre-push PASS: push exactly the already-committed, validated, reviewed, and authorized candidate SHA to `origin/megado-nbf-guard-0826`; no post-gate candidate mutation is allowed. After mechanical remote-tip verification, obtain final Sol completion PASS, then stop before merge.

# Pre-execution review checklist

Freeze this tasklist only when fresh GPT-5.6 Sol pre-execution review answers **YES** to every item:

- [ ] Does the tasklist preserve the complete North Star and avoid every named anti-pattern?
- [ ] Does it preserve frozen goal criteria 1–8 without redesign, widening, omission, or weakened evidence?
- [ ] Does it reference settled plan v7 digest `3e76fc3c9eeb8fbd6580d1217db341c1c3e9f16a4be3552eadddbef2ccd9276f` and North Star digest `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`?
- [ ] Are all seven tasks present, ordered, and grouped into the five natural batches without combining away task ownership?
- [ ] Are dependencies exact, including the hard NBF-06 barrier through NBF-05?
- [ ] Is NBF-01 limited to schemas, replay, CAS, disposition-terminal mapping, terminal/reconciliation/change/confirmation primitives, and deterministic provider-failure-key/keyed-streak replay mechanics without T8 policy?
- [ ] Does NBF-01 explicitly define `DispatchOutcome.kind=worker_disposition`, its accepted-state context, one-way terminal mapping, idempotency, and replay?
- [ ] Is NBF-02 the owner of canonical admission, the only scheduling loop, controlled launch, T7, generic outcome intake, disposition-terminal integration, reconciliation, transport, and scheduling/no-launch breaker bypass?
- [ ] Does NBF-02 preserve worker-disposition breaker semantics instead of bypassing or coercing them?
- [ ] Is NBF-03 limited to physical doors, no-WBC closure, WBC ordering, cardinality and typed traces, chain delegation, and the authority checker?
- [ ] Does NBF-04 produce or recover typed worker-disposition outcomes from every admitted accepted Python worker-death path after record-before-signal?
- [ ] Does NBF-04 prove disposition append → signal → typed outcome → one terminal outcome → reservation closure across crashes and replay?
- [ ] Does NBF-05 preserve the same lossless path for shell-supervised admitted worker deaths?
- [ ] Does NBF-05 define deterministic `source_inputs_sha256` from sorted signal-bearing source inputs plus generator/discovery-rule version?
- [ ] Does NBF-05 exclude the generated inventory, git revision, and self-digest from that digest?
- [ ] Is the inventory artifact SHA-256 external evidence rather than candidate content?
- [ ] Is NBF-06 the sole T8 policy owner, using the existing scheduler, ledger projection, terminal writer, changed-precondition producers, and fallback-selection door?
- [ ] Does NBF-06 preserve the v6/v7 rule that accepted exhausted worker outcomes—not probes or dispositions—form the consecutive provider streak?
- [ ] Does `provider_recovery_verified` authorize exactly one linked same-route retry while preserving the matching streak?
- [ ] Can the authorized matching child’s accepted exhausted outcome become observation two and establish degradation?
- [ ] Does accepted worker success reset the applicable streak, while another changed precondition resets/rekeys only when authoritative before/after evidence changes the provider-failure key?
- [ ] Are time passage, sleep, membership refresh, liveness changes, probe success, and recovery-event creation/consumption prohibited from resetting or rekeying provider observations?
- [ ] Do different-key exhaustion and intervening ordinary-failure/worker-disposition behavior match settled plan v7 exactly?
- [ ] Is NBF-07 the sole authoritative post-rebase validation owner?
- [ ] Does NBF-07 complete regeneration and every candidate-content change before the final candidate commit?
- [ ] Does NBF-07 require a clean worktree and exact candidate SHA before any final check?
- [ ] Do inventory `--check`, authority checker, shell syntax, secondary grep, and authoritative pytest bind to that exact clean SHA?
- [ ] Are validation, review, Oracle, push, and remote-tip artifacts stored outside candidate content in a durable run-named evidence root?
- [ ] Does every candidate mutation restart regeneration as applicable, commit, clean-tree verification, SHA recording, validation, independent review, and Sol pre-push acceptance?
- [ ] Do Luna review and Sol pre-push acceptance explicitly name the exact candidate SHA?
- [ ] Does push send exactly that SHA through an explicit branch refspec?
- [ ] Is rewritten published history guarded by `--force-with-lease` against the observed old remote tip?
- [ ] Does remote verification prove the branch tip equals the reviewed SHA before final Sol completion?
- [ ] Are dispatch-family, logical-dispatch, admission-attempt, linked-child, and final-launch semantics explicit and unchanged?
- [ ] Are production no-WBC closure, nested OMP exactly-once admission, chain authority deletion, and controlled raw-launch access structurally enforced?
- [ ] Are truthful no-launch, unresolved launch, canonical terminal outcome, reservation reconciliation, and post-commit receipt derivation preserved?
- [ ] Are evidence-bound changed-precondition producers and cross-logical-ID fingerprint CAS preserved?
- [ ] Are durable ledger-owned two-scan confirmation and repository-wide signal discovery preserved?
- [ ] Are OMP and native positive route-liveness requirements preserved without forcing native models into OMP or adding speculative network checks?
- [ ] Does every batch have a binary Oracle gate, reviewable evidence paths, and a commit boundary?
- [ ] Do focused and authoritative validations cover every settled criterion and synchronization gate?
- [ ] Are all tasks Normal with GPT-5.6 Luna executors, no `[XHARD]` task, and GPT-5.6 Sol reserved for Oracle judgments?
- [ ] Is huge-run determination explicitly NO, with no epic or cumulative big-batch boundaries?
- [ ] Are custody, candidate-branch-only push, exact-SHA delivery, guarded force-with-lease, and explicit user approval before merging `main` preserved?
- [ ] Does the final gate prohibit box-only behavior and require the fixer contract, independent Luna review, Sol pre-push acceptance, exact-SHA push, remote verification, and final Sol completion judgment?
- [ ] Does the tasklist introduce no new store, service, journal, scheduler, provider projection, rotator, research task, family lease, or `[XHARD]` work?
