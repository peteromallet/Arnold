# PREPARED, NOT AUTHORIZED — Batch 1 / NBF-01 executor brief (v8)

This brief prepares one implementation assignment for **NBF-01 only**. It is not
an execution authorization. Read the complete brief before touching a file.

## Hard start gate

**Do not begin implementation, create tests, stage files, commit, push, or mutate
any NBF-owned path unless every condition below is true at the moment work begins:**

1. `.oracle/tasklist.md` visibly declares itself **FROZEN**, not `PROPOSED v8`.
2. A persisted fresh GPT-5.6 Luna receipt records PASS after reading the complete
   v7/v8 contract and explicitly names these final review inputs:
   - plan v8 SHA-256
     `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`;
   - PROPOSED tasklist v8 SHA-256
     `88adb2e2e849285c7f83c924ef32c4fab12f1d05d3d4820dab0813f40c445e43`;
   - North Star SHA-256
     `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.
3. **After** that persisted Luna PASS, a separate independent GPT-5.6 Sol Oracle
   receipt records the explicit verdict `PASS_FREEZE` against the same plan-v8
   and proposed-tasklist-v8 digests, cites the Luna PASS receipt and its digest,
   records the current frozen tasklist digest if the freeze marker changes the
   file bytes, and explicitly authorizes execution.
4. The frozen tasklist still assigns Batch 1 solely to NBF-01 with no dependency
   and still identifies its executor as GPT-5.6 Luna.
5. The worktree is still branch `megado-nbf-guard-0826`; no one has authorized a
   merge to `main`.

At v8 brief preparation time, the gate is **closed**:

- `.oracle/tasklist.md` says `PROPOSED v8`; its SHA-256 is
  `88adb2e2e849285c7f83c924ef32c4fab12f1d05d3d4820dab0813f40c445e43`.
- `.oracle/receipts/contract-fix-sol-v8.md` says `Frozen: false` and
  `Execution authorized: false`.
- The required Luna stage has persisted `PASS_LUNA_V8` in
  `.oracle/receipts/plan-settled-W8-luna.md`, bound to the exact v8 digests.
- The later, independent Sol `PASS_FREEZE` and tasklist freeze have not yet been
  established by those facts. Luna PASS is necessary but not sufficient.

If the tasklist or plan changes after freeze, stop and obtain a replacement brief.
Do not reconcile contract drift by judgment.

## Model and independence boundary

The historical temporary override in `.oracle/agent_goal.md` and
`.oracle/status.md` states:

> For the next 30 minutes, the user authorizes GPT-5.6 Sol subagents for obvious
> fixes and normal implementation/validation work. Independent Sol oracle
> ownership, the prohibition on direct main-agent implementation, no main merge,
> and all existing delivery boundaries remain unchanged.

Plan/tasklist v8 explicitly settles that this 30-minute note is **historical
authorization bookkeeping**. It does not silently change the frozen executors or
the Luna-then-Sol freeze order. NBF-01 is Normal and its executor is GPT-5.6 Luna;
GPT-5.6 Sol is reserved for the independent freeze and later Oracle judgments.

The filename `execution-nbf01-sol.md` is an orchestrator-selected artifact name,
not model authority. A Sol agent reading this brief must not implement NBF-01
unless the user supplies a new explicit post-v8 model override and the frozen
tasklist/receipt records that authorized deviation. The executor never self-reviews,
self-freezes, self-passes the Batch 1 Oracle gate, or merges to `main`.

## Complete immutable North Star

The following is the complete immutable content of `.oracle/northstar.md`; it is
part of the assignment, not a summary:

> # North Star — Arnold self-healing supervision
>
> **End state:** An agent harness where no worker can be launched onto a spec that
> isn't live, a box that won't survive it, or a seed bound to the wrong interpreter —
> and where every worker death carries its killer's identity in a typed record that
> the recovery loop consumes before it ever retries the same fingerprint.
>
> **Enduring principles**
> - One door per invariant: admission, dispatch, and death are each enforced at
>   exactly one place; duplicate preflights are deleted, not patched around.
> - Deaths speak: SIGKILL, timeout, terminate, restack — every termination emits
>   `{killer, signal, elapsed_s}` into the failure ledger. Silent death is a bug.
> - Models are admitted, not assumed: a model id must resolve against catalog,
>   prefix map, family classifier, and live provider membership at dispatch time,
>   typedly rejecting expired or unknown ids.
> - Fixes ship on main through the fixer contract; hotfixes that live only as
>   deployed-but-uncommitted files do not exist.
>
> **Anti-patterns to avoid**
> - Single-scan verdicts treated as sustained truth (wedge kills, restacks).
> - Anonymous integer exit codes where a disposition belongs.
> - Judgment-based "healthy" claims without positive proof (live pid + advancing seq).
> - Redispatch of an identical failure fingerprint without a changed precondition.
>
> **Aligned progress feels like:** fewer incident classes over time, each new stall
> arriving with evidence attached and leaving with a root fix on main.

For this batch, “fixes ship on main” means follow the fixer delivery contract on
the candidate branch. **It does not authorize this executor to push or merge
`main`.** The branch may be pushed only after the later exact-SHA Sol pre-push
gate; merging to `main` always requires explicit user approval.

## Sources and precedence

Read these complete artifacts before implementing:

1. `.oracle/northstar.md` — immutable North Star above.
2. `.oracle/agent_goal.md` — complete criteria 1–8, temporary override, validation,
   sync policy, and source custody.
3. `.oracle/plan.md` — complete settled plan v8, 3,191 lines, SHA-256
   `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`.
4. `.oracle/findings/plan-v7-pre-v8.md` — archived complete v7 contract, SHA-256
   `3e76fc3c9eeb8fbd6580d1217db341c1c3e9f16a4be3552eadddbef2ccd9276f`.
5. The frozen version of `.oracle/tasklist.md`, the persisted Luna PASS receipt,
   and the later independent Sol `PASS_FREEZE` receipt.
6. `.oracle/custody.md`.
7. `.oracle/findings/preexecution-review-sol-v7.md` and
   `.oracle/receipts/contract-fix-sol-v8.md` for the v7 blockers and their v8
   corrections.
8. `.oracle/findings/plan-settled-W8-luna.md` for the prerequisite Luna review;
   remember that it does not itself authorize execution.

Precedence is: immutable North Star and user policy; settled plan v8; frozen
tasklist; this execution brief. If any lower source contradicts a higher source,
stop and report the exact contradiction.

## Goal slice advanced by NBF-01

NBF-01 builds only the contracts and single durable primitive needed by later
batches. It advances the foundations of goal criteria 3, 4, 7, and 8:

- typed worker dispositions and their lossless terminal linkage;
- pre-launch semantic-fingerprint reservation/CAS and evidence-bound retry
  authorization;
- scheduling-condition and no-launch transport schemas;
- provider-failure-key/keyed-streak replay mechanics without provider policy;
- deterministic reconciliation, receipt derivation, and durable two-scan state.

It does **not** implement the admission gate, launch doors, scheduling loops, T7
waiting behavior, T8 thresholds/routing behavior, real signal-site wiring, or
provider fallback decisions.

## Exact file ownership

The executor may modify only these production files:

- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- new `arnold_pipelines/megaplan/incident/disposition.py`

The executor may create or modify only these test files:

- new `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
- new `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
- new `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
- new `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
- new `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`
- new `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
- new `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`
- new `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
- existing `tests/arnold_pipelines/megaplan/test_incident_ledger.py`

The plan's phrase “existing fallback metadata schema” is a compatibility
boundary, not blanket permission to edit fallback policy. Read existing fallback
metadata as necessary, but do not edit `fallback_chains.py`, `_core/state.py`,
workers, handlers, `auto.py`, recovery policy, or any other file in NBF-01. If a
minimal schema edit outside the exact list above is truly unavoidable, stop and
return the exact file, symbol, and reason for an ownership decision. Do not widen
scope yourself.

Do not edit `.oracle/tasklist.md`, any plan, any receipt, custody files, the
North Star, the agent goal, implementation files owned by later tasks, box files,
or `/workspace/.cloud-hot-env`.

## Frozen NBF-01 ownership contract

Own only:

- typed schemas and strict serialization;
- explicit `DispatchOutcome.kind=worker_disposition`;
- deterministic disposition-to-terminal-outcome mapping and replay validation;
- deterministic incident-ledger replay projections;
- ordinary reservation CAS;
- canonical terminal-outcome writer and projection;
- canonical changed-precondition producers and evidence-binding validation;
- single-use changed-precondition consumption;
- provider-failure-key representation and deterministic keyed-streak replay;
- probe leases;
- one composite route-transition-and-child-reservation event;
- deterministic post-commit receipt derivation;
- reservation reconciliation;
- durable two-scan confirmation schemas and projection;
- canonical disposition helper and shell CLI contracts.

Explicitly excluded:

- request-specific admission and admission callers;
- sleeping, retry/wait scheduling loops, T7 behavior, and T8 policy;
- T8 observation thresholds, degradation, scalar hold/probe policy, route choice,
  fallback selection, or return-to-primary decisions;
- controlled final-launch implementation and physical-door wiring;
- Python or shell signal-site wiring;
- worker/client/RPC/WBC construction;
- caller integration, generic handler/`auto.py` routing, or breaker behavior;
- a second journal, store, service, scheduler, rotator, projection, family lease,
  prepare/commit protocol, or multi-record pseudo-transaction.

## Contract A — typed boundary schemas

Add strict, versioned, unknown-field-rejecting round-trip contracts for
`SchedulingCondition` and `DispatchOutcome`, surfaced through `PhaseResult`.
Add `ExitKind.scheduling_condition` without treating it as a failure.

`SchedulingCondition` fields:

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

Initial reasons are exactly:

```text
memory_cooldown
provider_observation_wait
provider_degraded
provider_probe_wait
provider_probe_failed
unresolved_launch
```

The schema must preserve the condition losslessly. A condition is neither a
worker failure nor a disposition. `disposition_id`, when present, references a
real disposition only. Holds, probe failures, or ambiguous reservations never
invent one. This batch defines transport primitives only; later tasks own routing.

`DispatchOutcome` fields:

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
disposition_id | null
reconciliation_event_id | null
terminal_outcome_event_id | null
```

Kinds and only their legal launch states:

```text
no_launch                 -> not_started
success                   -> accepted
ordinary_terminal_failure -> accepted
provider_exhausted        -> accepted
worker_disposition        -> accepted
unresolved_launch         -> ambiguous
```

Reject every incompatible kind/state/payload combination. In particular:

- `no_launch` cannot have accepted state or worker-terminal/provider/disposition
  evidence;
- `worker_disposition` requires `disposition_id`, worker identity, start/finish
  timing, receipt, semantic fingerprint, phase, selected spec, logical dispatch,
  and accepted launch state;
- worker disposition cannot carry provider-exhaustion evidence and cannot
  serialize as ordinary failure;
- provider exhaustion requires structured observation ID, retryability class,
  exhausted-attempt count, terminal provider evidence ID, precondition identity,
  provider epoch identity, provider-failure key, and observation time.

## Contract B — semantic fingerprint and changed preconditions

The semantic dispatch fingerprint contains only durable execution preconditions:

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

It excludes logical/family IDs, attempt number, route-liveness digest or
generation, timestamps, retry counters, PID/incarnation, and provider-probe
observations. Reservation uniqueness is `projection key + semantic fingerprint`,
so two logical IDs with the same pair contend for one reservation.

Only these changed-precondition reasons and reason-specific canonical producers
are allowed:

```text
source_revision_changed
runtime_generation_changed
seed_or_interpreter_binding_changed
timeout_policy_changed
authorized_route_changed
provider_recovery_verified
verified_repair_committed
```

The canonical event binds schema/event identity, producer kind/version, plan,
phase, optional family/logical IDs, reason, authoritative subject,
producer-derived before/after content IDs, evidence event/digest, the relevant
source/runtime/interpreter/route/timeout/repair fields, optional provider-failure
keys before/after, time, and actor.

Callers do not mint arbitrary IDs. The producer reads and normalizes authoritative
before/after state and evidence; before and after content IDs must differ. The CAS
validates reason, producer, producer version, evidence type/digest, subject,
before/after derivation, and provider-key binding. Forged unequal IDs, a mismatched
subject/evidence/version, or caller-supplied key transitions fail closed.

Consumption is single-use and atomic with reservation. `provider_recovery_verified`
may authorize exactly one linked same-route child but preserves the matching
provider-observation streak because its provider-failure key is unchanged. Other
allowlisted changes reset/rekey provider observations only when canonical
authoritative before/after evidence changes that key. Time, sleep, retry count,
PID replacement, membership refresh, liveness refresh, notes, or probe success
alone never bypass the fingerprint.

## Contract C — the single ledger transaction authority

Extend the existing `IncidentLedger`; do not create another journal. Reuse its
existing `NdjsonEventJournal` sequence-sidecar `fcntl.flock`, durable `fsync`, and
append order. NBF-01 adds one lock/read/compare/single-append authority owning:

- ordinary reservation;
- terminal outcome and reservation closure;
- changed-precondition validation/consumption;
- provider-keyed replay transitions;
- probe leases/results;
- composite route transition plus child reservation;
- reconciliation;
- durable confirmation;
- dispositions.

Ordinary reservation under one lock must read projection, compare expected
version/key/fingerprint, reject unchanged terminal fingerprints without one
eligible unused change, reject an active duplicate even across logical IDs,
validate and consume any change, append exactly one `admission_reserved`, then
derive and return the receipt only after commit.

Composite fallback/return reservation is exactly one
`provider_route_child_reserved` NDJSON record containing:

```text
schema_version, event_type, event_id, plan_id, phase, projection_key,
expected_projection_version, transition_kind, from_spec, to_spec,
parent_logical_dispatch_id, parent_terminal_event_id, authorizing_event_id,
configured_fallback_chain_identity, precondition_identity,
child_dispatch_family_id, child_logical_dispatch_id, child_physical_door_id,
child_semantic_dispatch_fingerprint, child_route_liveness_identity,
consumed_changed_precondition_event_id | null, receipt_derivation_version,
recorded_at, actor
```

It must not contain a child receipt ID. One append projects both transition and
reservation. The child receipt is derived afterward from derivation version,
committed event ID, plan, phase, family, logical child, physical door, and semantic
fingerprint. Fresh replay must reproduce it byte-for-byte. There are no separate
flip/reserve records, prepare/commit markers, or second metadata authority.
Fallback metadata is a post-commit derived cache only.

Torn/invalid lines project nothing. Any lock, read, schema, projection-version,
append, fsync, or cache mismatch fails closed; cache loss repairs from replay.

## Contract D — canonical terminal outcomes and no-double-append disposition flow

Every accepted, non-scheduling result maps through one canonical
`worker_terminal_outcome` writer. Its event binds outcome and terminal IDs, plan,
phase, projection key, family/logical IDs, admission receipt, reservation event,
semantic fingerprint, selected spec, physical door, accepted launch state, worker
and process/RPC identity, start/finish times, kind-specific success/failure/provider
evidence, optional `disposition_id`, execution-context identity, time, and actor.

Kinds are exactly:

```text
success
ordinary_terminal_failure
provider_exhausted
worker_disposition
```

The writer validates accepted launch context, projects the terminal fingerprint,
and closes the reservation atomically from this one append. Duplicate terminal ID
or duplicate matching disposition linkage is idempotent. Conflicting terminal
kinds, conflicting linkage, or a second terminal kind for the reservation reject.

### Mandatory worker-death flow

```text
accepted launch
  -> append exactly one canonical worker_disposition record
  -> only after that append succeeds, signal the worker
  -> preserve DispatchOutcome(kind=worker_disposition, launch_state=accepted)
  -> canonical terminal writer validates the already-committed disposition
  -> append exactly one worker_terminal_outcome(outcome_kind=worker_disposition)
  -> project terminal fingerprint and close reservation exactly once
```

The terminal writer **references** the existing disposition by `disposition_id`.
It must never append, rewrite, or duplicate killer, signal, elapsed-time,
confirmation, victim, or signal evidence. The outcome is never coerced into
`ordinary_terminal_failure` or `provider_exhausted`, and never enters provider
degradation. It retains its ordinary typed disposition/breaker semantics and
breaks an active consecutive provider-exhaustion streak.

Crash/replay disposition cases are mandatory:

- after disposition append/before signal: replay sees the disposition but must not
  fabricate a signal or terminal outcome;
- after signal/before terminal append: the accepted reservation stays unresolved
  until the existing disposition is linked by the terminal writer or truthful
  reconciliation;
- after terminal append/before cache update: replay closes once without duplicating
  disposition or terminal evidence;
- a terminal-link append failure leaves the reservation unresolved;
- recovered worker disposition requires matching receipt, fingerprint, phase,
  selected spec, worker incarnation, accepted launch, and canonical disposition;
  it links one terminal outcome and never sends another signal.

`no_launch`, scheduling, unresolved launch, probes, observed deaths without an
admitted receipt, and non-worker lifecycle signals do not create
`worker_terminal_outcome`. Provider exhaustion is not also ordinary failure.

## Contract E — reservation reconciliation and crash truth

`reservation_reconciled` supports only:

```text
released_no_launch
terminal_outcome_recovered
permanent_hold_ambiguous
```

It binds reconciliation/plan/phase/projection/logical/receipt/reservation/
fingerprint identity, resolution, positive evidence type and IDs, launch-state
identity, optional worker/PID/process-start/running-receipt/terminal IDs, observed
and recorded times, and actor.

`released_no_launch` requires positive persisted controlled-adapter evidence that
the exact launch was `not_started`, all launch-capable primitives were unreachable
before `entered`, and no contradictory entered/accepted/process/RPC/WBC/managed
command/disposition/terminal evidence exists. Absence of PID, cache, marker, or
elapsed time is never proof. It releases only the named reservation and creates no
worker terminal event/fingerprint, provider observation/streak change, phase
failure, or breaker input.

`terminal_outcome_recovered` requires positive accepted-launch evidence and a
canonical terminal result. For worker disposition, it must validate and link the
already-existing canonical disposition without a second disposition or signal.

`permanent_hold_ambiguous` retains a non-launchable reservation and creates no
fabricated outcome or child. Conflicting reconciliation rejects; identical replay
is idempotent. Reconciliation ID derives deterministically from reservation,
resolution, and normalized evidence identity.

Test crash boundaries include before lock, after read, after compare, torn
composite write, post-composite/pre-receipt, pre/post-cache, controlled launch
marker boundaries represented by fixtures, disposition append/signal/terminal
link boundaries, terminal append/cache, probe/recovery creation and consumption,
and child reservation/outcome. NBF-01 owns primitive and replay tests, not the
later controlled launch implementation.

## Contract F — provider-failure-key replay mechanics, not T8 policy

The canonical provider-failure key is:

```text
digest(version, phase, normalized selected spec,
       typed provider failure class, authoritative provider epoch identity)
```

It excludes probe results, timestamps, liveness/membership digests, retry counts,
and ephemeral health observations. Projection is keyed by plan, primary spec,
configured fallback-chain identity, and provider-failure key. It deterministically
replays current route/status, active key, observation streak/last observation,
provider epoch, retry/probe/lease state, authorized target, last transition/change,
and active/unresolved reservation state.

State effects owned as replay mechanics:

- first accepted `provider_exhausted` outcome sets its key and streak 1;
- matching accepted exhaustion increments;
- different-key accepted exhaustion rekeys at 1;
- accepted success clears the applicable streak and active key;
- accepted ordinary failure or worker disposition breaks consecutiveness but
  remains its own typed path;
- probe pass/fail and `provider_recovery_verified` creation/consumption preserve
  the streak;
- an authoritative changed precondition resets/rekeys only if its canonical
  before/after provider keys differ;
- scheduling, no-launch, unresolved launch, time passage, and liveness refresh do
  not change the streak;
- duplicate event IDs are idempotent; invalid/torn events reject;
- projection version is compared on transitions; probe lease has one winner;
- unresolved/no-launch parents cannot create provider-driven children;
- fallback metadata is non-authoritative.

Do not implement the two-observation degradation threshold response, holds,
probing policy, fallback/return selection, sleeping, or route rotation here.

## Contract G — disposition records, durable confirmation, and CLI

Add strict `WorkerDisposition`, `ObservedProcessDeath`, and
`NonWorkerSignalDisposition` records with frozen enums for in-band/observed mode,
worker/external/non-worker subjects, SIGINT/SIGTERM/SIGKILL, killer kinds
(`launcher_timeout`, `resident_supervisor`, `watchdog`, `ensure_watchdog`,
`kernel_cgroup_oom`, `external_unknown`, `lifecycle_supervisor`), and causes
(`timeout`, `terminate`, `escalation`, `wedge`, `restack`, `cgroup_oom`,
`observed_dead_unknown`, `lifecycle_shutdown`).

Worker disposition requires plan, phase, family/logical IDs, receipt, semantic
fingerprint, selected spec, killer kind/identity, cause, signal, elapsed seconds,
worker identity, optional PID/process-start/process-group/timeout/ladder/confirmation
fields, observed time, and evidence. Incomplete or fabricated identity rejects.
TERM and KILL ladder steps use distinct deterministic disposition IDs.

Observed death may omit worker context only when already dead; it lists known and
unknown fields and never invents fingerprint, worker, killer, or signal. Cgroup OOM
requires positive cgroup delta/evidence. Unknown death remains explicitly
`external_unknown`/`observed_dead_unknown`. Non-worker lifecycle signals never
impersonate workers.

Durable two-scan confirmation lives only in this incident ledger. Its identity
binds schema version, site, subject, PID, process-start identity, relevant progress,
supervisor incarnation, and cause. TTL derives from the versioned policy:

```text
confirmation_ttl_s = min(max(2 * scan_interval_s, 30.0), 300.0)
expires_at = first_observed_at + confirmation_ttl_s
```

The scan interval is finite/positive; a second scan is at least one interval later
and no later than expiry. Under the ledger lock, first observation records only;
one matching second scan consumes once. PID/process-start/progress/cause/
supervisor-or-container incarnation change replaces; expiry expires; restart
replays original expiry. Missing/torn/mismatched/already-consumed confirmation
authorizes no signal. TERM and KILL have separate identities when both use
sustained proof.

Shell CLI contract:

```bash
python -m arnold_pipelines.megaplan.incident.disposition record \
  --ledger-root "$LEDGER_ROOT" \
  --json-stdin
```

It reads exactly one UTF-8 JSON object, validates one canonical disposition,
resolves the ledger only under explicit `--ledger-root`, validates consumed
confirmation where required, appends synchronously through the same helper, emits
one JSON acknowledgement with disposition/ledger IDs, writes diagnostics only to
stderr, and never signals.

Exit statuses are exact:

```text
0 append succeeded
2 malformed JSON or schema violation
3 ledger append/locking failure
4 invalid or unavailable ledger/context location
5 missing, expired, mismatched, or already-consumed confirmation
```

NBF-01 builds and tests the helper/CLI contracts; later batches own calling real
signal sites.

## Acceptance checklist

All of the following must be true before returning the implementation for Oracle
review:

- Every strict schema round-trips and rejects unknown, missing, or incompatible
  state as required.
- Worker disposition is lossless from `DispatchOutcome` to exactly one matching
  terminal outcome; no coercion or double append is possible.
- Duplicate disposition-terminal linkage is idempotent; conflict rejects.
- Reservation closure/fingerprint projection occurs exactly once for disposition.
- No-launch creates no worker/provider/failure/breaker state.
- Semantic fingerprint and provider key exclude volatile liveness/family/logical
  identity as specified.
- Same fingerprint across logical IDs contends for one reservation.
- Changed-precondition production and consumption are evidence-bound and single-use.
- `provider_recovery_verified` authorizes one linked child without altering streak.
- Ordinary two-process reservation contention has one winner.
- Composite route transition/child reservation is one append; receipt derives
  post-commit and is byte-identical on fresh replay.
- Torn/failed writes expose no partial transition, receipt, or projection.
- Terminal projection precedes closure and distinguishes success, ordinary failure,
  provider exhaustion, worker disposition, no-launch, and unresolved launch.
- Provider keyed streak transitions follow Contract F exactly.
- Reconciliation rejects blind/conflicting release and preserves ambiguity.
- Durable confirmation survives restart and enforces TTL, separation, process/
  progress/incarnation identity, replacement/expiry, and single consumption.
- Ledger lock/append/schema/projection/cache failures fail closed.
- CLI validation, acknowledgement, and exit statuses match Contract G.
- No second journal/store/transaction protocol/scheduler/rotator/policy owner exists.
- No excluded file or later-task behavior changed.

## Required focused validation

Run exactly this focused suite from the repository root:

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

Also run narrowly relevant existing phase-result serialization/classification tests
if an owned production edit affects their established contract. Do not run the
authoritative broad post-rebase suite; NBF-07 alone owns that run.

Capture the exact commands, exit statuses, and concise results for the Batch 1 Sol
Oracle. A failing test is not waived; fix in scope or return a precise blocker.

## Dirty-tree and source custody

Build on the existing dirty candidate tree; never stash, reset, clean, rebase,
checkout over, delete, or overwrite concurrent/user artifacts.

Prepared source identity:

- worktree: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- branch: `megado-nbf-guard-0826`
- prepared HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- immutable source base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- six branch commits currently sit above that base, including the resume-custody
  commit; preserve the entire existing branch history.
- the primary `/Users/peteromalley/Documents/Arnold` and prior
  `/Users/peteromalley/Documents/Arnold-oracle` worktrees are out of scope and
  must not be touched.
- the live `megaplan-cloud-agent-resident-only` agentbox workload is read-only;
  no box mutation is authorized.

Before editing, capture `git status --porcelain=v1` and the hashes of every owned
file that already exists. At preparation time, all owned production/test paths are
clean; the dirty tree consists of orchestrator-owned `.oracle` changes and
untracked planning/review/receipt artifacts. Treat every pre-existing non-owned
change and every untracked artifact as protected.

During work:

- use `apply_patch` for edits;
- never stage or commit non-owned files;
- do not amend, rebase, cherry-pick, reset, clean, or switch branches;
- do not delete untracked files;
- do not edit tasklist/plan/receipt/status/custody artifacts;
- do not push any branch;
- never merge to `main`;
- if an owned file becomes concurrently modified after your snapshot, stop and
  report the overlap rather than overwriting it.

Before handoff, compare the final status to the initial snapshot and prove that
all new changes are confined to the exact owned paths. Do not commit Batch 1. The
orchestrator commits only after the independent Sol Oracle returns PASS.

## Reconnaissance already established

- `phase_result.py` currently has schema/contract version 1 and no
  `scheduling_condition` exit kind or NBF dispatch-outcome dataclass.
- `incident/schema.py` currently validates the legacy permissive M1 incident
  envelope plus strict Maintenance codecs; NBF records must be added without
  breaking those existing compatibility paths.
- `IncidentLedger.append_event` is the existing canonical append door.
- `_IncidentEventJournal.append_maintenance` demonstrates the required
  lock/read/decide/single-append pattern using the existing sequence-sidecar
  `fcntl.flock`, monotonic sequence, append, flush, and `fsync` semantics.
- There is no existing `incident/disposition.py`.
- The eight focused NBF test modules listed as new above do not yet exist;
  `test_incident_ledger.py` does exist.
- No owned implementation or test path was dirty when this brief was prepared.

Prefer extending the existing codec and journal abstractions coherently over
building a parallel subsystem. Preserve legacy event reading and existing incident
tests while making new NBF contracts strict and closed.

## Handoff and Batch 1 stop point

Return only after focused validation is green or a concrete in-scope blocker is
proved. The handoff must include:

- changed-files list, all within ownership;
- concise mapping from each acceptance group to implementation symbols/tests;
- focused pytest command and complete pass/fail count;
- explicit no-double-append disposition trace and its tests;
- contention, fresh-replay, torn-write, reconciliation, keyed-streak,
  confirmation-TTL/incarnation, and CLI evidence;
- initial/final dirty-tree comparison proving custody preservation;
- any assumptions or residual risk.

Then stop. Do not begin NBF-02. Do not self-issue the Batch 1 checkpoint. The
independent Sol Oracle must verify the schemas, terminal/disposition mapping,
provider-key replay, changed-precondition producers, fingerprint components,
post-commit receipts, single-record composite behavior, reconciliation, durable
confirmation, CLI, crashes, and replay. Only Oracle PASS permits the orchestrator
to commit Batch 1 and move to Batch 2.

No push is authorized. No merge to `main` is authorized.
