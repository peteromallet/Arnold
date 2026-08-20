# T1.9 Stage-A launch/stop implementation delta v2 — Sol

Date: 2026-08-02  
Status: **implementation-ready specification; not implemented, accepted, deployed, or launch authority**

## 1. Bounded outcome

Implement one owner-installed transaction which can upload one immutable v3
input, start at most one exact runner, permit only
`init -> plan -> critique -> gate -> finalize`, accept the first exact Run
Authority transition whose installed-schema cursor is strictly beyond poisoned
v2's frozen `gated/finalize` cursor, and then permanently close the envelope by
expiry/fence and exact stop where observable.

It grants no execute, revise loop, second finalize or milestone, Git/ref/PR
publication, product deploy, source refresh, package install, model fallback,
generic command execution, broad process termination, lease renewal or automatic
relaunch. A failed bounded run is evidence for a new owner decision; it is not
authority to retry.

T1.9 owns only launch reservation, upload/start/stop orchestration, launch-owner
replay, the phase/cursor budget, and independent launch verification. T1.1-T1.8
and T1.10 remain the owners of admission, model semantics, recovery, effect
dispatch, storage where adopted, release generation and notification. T1.9
joins their accepted records rather than recreating them.

## 2. Two manifests, not one circular gate

### 2.1 `BuildInterfaceManifest`

Freeze this before implementing adapters. It identifies one clean integration
descendant of `6787d6363e8fc0603092913ae877db14f3b9fff8` and exactly one accepted
commit/tree/schema/contract/help/production-endpoint tuple for:

- T1.1 Run Authority and raw-CL1 admission;
- T1.5 singleton Recovery owner and topology/retirement inventory;
- T1.6 exclusive WBC dispatcher, child-GLEK rules and structured
  upload/start/observe/stop capabilities;
- T1.8 Release Authority, installed-generation selection and independent live
  observation;
- T1.7 only if any selected production owner uses that implementation.

The manifest also pins the candidate commit/tree, wheel/package vector, fixed
owner configuration digest and capability-registry digest. A port change
invalidates the build; an implementer must not guess or copy dirty diffs.

### 2.2 `StageAProductionGoManifest`

This is issued after integration, installation, installed canaries, v2
retirement and fresh-v3 admission. `execute` resolves it from an owner-minted
opaque handle and revalidates it before every irreversible child operation. It
contains, all bound to the same candidate/generation and current owner heads:

1. Accepted T1.2 attempt-health, T1.3 authenticated raw bundle and scoped T1.4
   graph-admission/one-repair contract and receipt digests.
2. One physical model provider/model/route, one credential-set ID and one tool
   mode; `fallbacks=[]` and every other route is unavailable.
   The exact Stage-A effect-family allowlist and budgets are
   `input-upload=1`, `runner-start=1`, the accepted bounded model-attempt set,
   `fixer<=1`, `notification-initial<=1`, and `runner-stop=1`; every unlisted
   family is unavailable. The manifest pins T1.6's child-derivation contract.
3. The scoped T1.5/T1.10 installed failure canary: one occurrence/claim/fixer
   outcome, one initial notification outcome, 200 unchanged observations with
   no additional send, and sticky provider ambiguity with no redispatch.
4. Capacity/WAL/receipt reserve, scoped deploy decision, installed-release
   receipt, two-observer live-vector attestation and rollback or explicit
   forward-fix disposition.
5. The exact v2 tuple and current T4.1-T4.5 receipts: quarantine, all-grant/effect
   revocation, advanced Custody epoch/tombstone, every inventoried GLEK terminal
   or sticky non-redispatchable, selection CAS away from v2, and unchanged v2
   marker digest.
6. T5.1's four actual owner decisions, T5.2 raw target-bound CL1 decision,
   T5.3 spec/preconditions, T5.4 fresh identity declaration, T5.5 preflight and
   T5.6 signed finite-slice/stop/verifier decision.
7. Expected owner endpoints, store incarnations, anchors, heads, signing keys,
   expiries and independent verifier identity/query/challenge.

Any missing, corrupt, unreadable, stale, expired, revoked, cross-venue,
cross-candidate or disagreeing item produces `GO_JOIN_REJECTED` before a
reservation or provider call. A status projection cannot supply or repair an
item.

## 3. Neutral contracts and authority provenance

Add `arnold/launch/contracts.py` with strict frozen dataclasses and canonical
JSON vectors. Reject duplicate/unknown fields, aliases, non-normalized IDs,
non-finite numbers, malformed digests/signatures, mixed owner heads and
non-canonical serialization.

```text
BuildInterfaceManifest
  schema/contract digest; candidate commit/tree/wheel/package vector
  dependency commit/tree/schema/help/contract/endpoint tuples
  fixed owner-config and capability-registry digests

StageAProductionGoManifest
  schema/contract digest; issue/expiry; candidate/generation/venue
  dependency acceptance receipts; model route and no-fallback proof
  effect-family allowlist/budgets and child-derivation contract digest
  capacity/deploy/install/live-vector/rollback receipts
  v2 tuple/cursor/retirement receipts and current heads
  v3 CL1/spec/fresh-identity/finite-slice receipts and current heads
  failure/fixer/notification/200-silence receipts
  owner endpoint/incarnation/anchor/key/head set; verifier challenge

StageALaunchSeed
  seed ID/digest; issuer/subject/audience/venue; issue/expiry/TTL
  candidate/generation and production-GO digest
  exact input bytes digest/size/destination/readback challenge
  raw+normalized workspace/session/plan/path/branch/worktree/state/marker IDs
  runner slot, disabled publication namespace and all reservation IDs
  frozen v2 cursor/order digest; fresh-v3 start and exact target transition
  phase allowlist [init, plan, critique, gate, finalize] and cursor budget
  parent/child GLEKs; stop-capability digest; no_refresh=true
  exact upload/start/stop children; bounded model/fixer/notification derivation
  owner endpoint/incarnation/anchor/signing-key/decision/nonce/signatures

StageALaunchEnvelope
  seed and GO-manifest digests; issuer/subject/audience/venue
  RA grant/revision/fence/cursor; Custody occurrence/lease/epoch/fence
  WBC parent attempt/GLEK/store generation and exact child manifest
  effect-family allowlist/budgets and child-derivation contract digest
  Release selection/attestation; reservation heads; runner-slot claim
  signed wall expiry + accepted monotonic deadline/boot identity
  verifier identity/query/challenge; decision/nonce/signatures

StageAStopCapability
  cleanup-only issuer/subject/audience/venue and one-use operation identity
  original seed/grant/fence/lease/epoch/generation/slot bindings
  distinct stop parent/child GLEKs and allowed cleanup operations only
  eventually bound exact PID + birth + cgroup/unit observation
  cleanup expiry/reconciliation horizon; owner incarnation/key/signatures

OwnerOperationReceipt
  owner ID/incarnation; operation ID; exact request/result digests
  predecessor and committed sequence/head; issue time; signature

StageALaunchReceipt
  launch-owner event/head; exact operation receipts for every saga step
  reservation/upload/process/phase/target/fence/stop evidence digests
  terminal classification and independent-verifier decision reference
```

`prepare` may canonicalize a seed but returns no authority. Only the
owner-installed Launch Authority issues an executable opaque launch handle and
the longer-lived opaque stop handle. Both resolve to signed server-side records.
The production client authenticates the fixed server/trust root; a Unix socket
path alone is not authority. No production constructor accepts a socket, root,
repository, provider, callback, key or test backend.

## 4. Owner topology and ports

Add `arnold/launch/ports.py` with narrow protocols frozen to the accepted
interfaces:

```python
class RunAuthorityPort(Protocol):
    def revalidate_admission(...): ...
    def read_operation_receipt(operation_id: str): ...
    def accept_target_transition(...): ...
    def fence_grant(...): ...

class CustodyPort(Protocol):
    def read_current_lease(...): ...
    def advance_fence(...): ...
    def read_operation_receipt(operation_id: str): ...

class EffectDispatcherPort(Protocol):
    def reserve_child(...): ...
    def mark_started(...): ...
    def dispatch_registered(...): ...
    def reconcile_child(...): ...
    def deny_except_stop(...): ...

class ReleaseAuthorityPort(Protocol):
    def attest_current_generation(...): ...

class ReservationOwnerPort(Protocol):
    def reserve_exact(...): ...
    def read_operation_receipt(operation_id: str): ...

class IndependentProcessObserverPort(Protocol):
    def observe_exact(...): ...
```

The Launch Authority has its own append-only record, but it does not pretend
that RA, Custody, WBC, Release and venue owners share a transaction. Add
`arnold/launch/repository.py` with an owner-local CAS/event repository contract:
`append(expected_head, event, operation_id)`, `read_head()`, and
`read_operation_receipt(operation_id)`. Production composition uses the
owner-installed backend pinned by `BuildInterfaceManifest`; use T1.7 when that
is the frozen choice, otherwise implement only this owner-local durability
contract. Never instantiate caller-root SQLite or silently initialize a new
store.

Add `arnold/launch/production.py` with the sole production assembly function
`production_launch_client()`. It reads the Release-Authority-pinned owner
configuration at its fixed installed path and verifies its digest. Test fakes
live under `tests/arnold/launch/fakes.py`, not behind a production flag.

## 5. Append-only state and exact replay

Add `arnold/launch/reducer.py` with these durable states:

```text
PREPARED
AUTHORITY_VALIDATED
TARGETS_RESERVING
TARGETS_RESERVED
UPLOAD_INTENT_DURABLE
UPLOAD_STARTED
UPLOAD_VERIFIED
START_INTENT_DURABLE
START_STARTED
RUNNING_VERIFIED
SLICE_ACTIVE
TARGET_CURSOR_INTENT_DURABLE
TARGET_CURSOR_ACCEPTED | TARGET_CURSOR_INDETERMINATE
FENCE_INTENT_DURABLE
FENCING
STOP_INTENT_DURABLE
STOP_STARTED
STOPPED_FENCED | EXPIRED_FENCED | FAILED_FENCED
QUARANTINED
SUCCEEDED_CLOSED
```

Every event contains a stable operation ID, exact request/result digest,
expected predecessor, dependency heads and signer. Invalid transitions,
duplicate operation IDs with different bytes, sequence gaps, corrupt reads and
head rollback fail closed.

`arnold/launch/replay.py::resolve_owner_operation()` is the only owner-CAS
replay rule. After response loss it queries the exact operation ID and adopts
only a complete canonical receipt whose pre-bound tuple/result matches. It does
not infer success from the current head or projection; later legitimate history
does not invalidate the exact earlier receipt. A typed conflict remains a
conflict; absent or incomplete proof is `INDETERMINATE`.

Apply this rule to every reservation CAS, Launch Authority append, target Run
Authority CAS, RA fence, Custody advance, WBC deny and stop receipt. Provider
reconciliation is separate and never substitutes for owner proof.

## 6. Transaction algorithms

Add `arnold/launch/transaction.py` with only:

```python
execute_launch(handle: OpaqueLaunchHandle) -> StageALaunchReceipt
reconcile_launch(transaction_id: str, challenge: VerifierChallenge) -> StageALaunchReceipt
request_stop(stop_handle: OpaqueStopHandle) -> StageALaunchReceipt
```

### 6.1 `execute_launch`

1. Resolve/authenticate the opaque handle and signed server-side seed/envelope.
2. Load `BuildInterfaceManifest`; load and independently recompute the complete
   current `StageAProductionGoManifest` join. Verify wall/monotonic expiry,
   owner incarnations, all heads, v2 retirement, candidate/generation, one model
   route/no fallback, topology and pre-issued cleanup capability.
3. Reserve raw and normalized workspace, session, remote input, deterministic
   plan/path, branch/ref, worktree registration/path, chain state/marker, runner
   slot, occurrence/GLEKs and disabled publication namespace. Reserve atomically
   within an owner and as an ordered fail-closed saga across owners. Each result
   is only `ABSENT_RESERVED`, `COLLISION`, or `UNKNOWN`. Collision/unknown never
   deletes, resets, cleans, overwrites, adopts by name or releases evidence.
4. Persist the exact upload child manifest and WBC intent; reread all required
   heads; CAS the child to `STARTED`; dispatch the exact seeded bytes once via
   the registered T1.6 capability; independently read back durable bytes and
   identity. After `STARTED`, T1.9 never calls upload dispatch again.
5. Persist the exact structured-start child manifest and intent; reread heads;
   CAS-claim the runner slot and child `STARTED`; dispatch once via T1.6. The
   argv/cwd/environment digests bind fixed installed interpreter/entrypoint,
   candidate/generation, seed, GO manifest, fences, GLEK, input and TTL. After
   `STARTED`, T1.9 never calls start dispatch again.
6. The independently observed exact process birth is CAS-bound to the runner
   slot and pre-issued stop record before any initialization token is issued.
   Zero, duplicate, wrong or unreadable process evidence never creates a phase
   token.
7. Start the bounded runner. Any failure, rejection, owner conflict, expiry or
   mismatch persists `FENCE_INTENT_DURABLE` and enters the stop saga.

For upload/start reconciliation, exact applied evidence may be adopted.
Authoritative definite `NOT_APPLIED` produces a durable failed/fenced launch;
unknown stays sticky `INDETERMINATE`. The bounded implementation never resumes
or redispatches a `STARTED` child, even with the same GLEK.

### 6.2 `reconcile_launch`

Recompute current authority and use exact operation receipts for all owner
steps. For upload, adopt only the exact bytes/object identity. For start, adopt
only one process matching slot, PID/birth/cgroup-or-unit, argv, cwd, environment,
seed, generation, fences, GLEK and input digest. Multiple/wrong/incomplete/
unknown evidence enters fence/stop and remains visible. Reconciliation never
refreshes source, rerenders input, chooses a new name, dispatches upload/start,
or launches another runner.

### 6.3 Stop saga

Add `arnold/launch/stop.py::advance_stop_saga()`. This is explicitly not an
atomic cross-owner transaction:

1. Persist `FENCE_INTENT_DURABLE` and the complete pre-issued stop child.
2. Ask WBC to deny every new child except the already-bound stop/reconcile
   children; persist and exact-replay its receipt.
3. Publish the runner fence; fence RA; advance/fence Custody, recording exact
   receipts after each step.
4. CAS the stop child to `STARTED` and dispatch at most once through T1.6.
5. Reconcile stop acknowledgement by exact process identity; never use tmux
   name, PID grep, `pkill`, container destroy, provider down or relaunch.
6. Join current RA/Custody/WBC/Release/process heads; preserve workspace, input,
   plan, branch/worktree, marker, logs and every owner record.

A crash resumes at the first unreceipted step. Stop failure leaves all new
effects denied and state `INDETERMINATE`/`QUARANTINED`; it never restores
authority.

## 7. Expiry and cleanup authority

The signed launch record carries `issued_at`, `expires_at` and positive bounded
TTL. At owner acceptance, persist local `accepted_wall_time`,
`accepted_monotonic_ns` and boot/clock identity. Before every reservation,
effect and phase claim, use the earlier of signed wall expiry and the persisted
monotonic deadline. If monotonic continuity or trusted wall time cannot be
proved after restart/boot change, expire and fence; never extend the TTL.

The stop capability is cleanup-only and has a separately signed reconciliation
horizon longer than launch TTL plus the maximum observation/stop window. It
remains usable after the launch grant/lease expires or is revoked and cannot
mint or renew run authority. If cleanup authority itself expires while process
truth is unknown, the identity remains permanently denied and quarantined.
Clock passage alone is never an exact-stop receipt.

## 8. Finite runner and acceptance

Add `arnold_pipelines/megaplan/stage_a_runner.py`:

```python
run_stage_a_slice(opaque_handle: str) -> StageASliceResult
```

It obtains a process-bound runner context from the fixed Launch Authority,
invokes only `handle_init`, `handle_plan`, `handle_critique`, `handle_gate` and
`handle_finalize` in order, and stops on any other route signal. No `revise`,
`execute`, `review`, override, retry ladder or second milestone is registered.
Handler namespaces are deterministically constructed from the owner-stored seed
and accepted spec; CLI arguments and environment values cannot add or replace a
phase, model, route, path, grant, effect or deadline.

Add `arnold/launch/runner_guard.py`:

```python
claim_phase(handle, phase, predecessor_cursor, process_observation) -> PhaseClaimReceipt
record_phase_outcome(claim, dependency_receipts, outcome_digest) -> PhaseOutcomeReceipt
accept_target(claim, exact_transition) -> OwnerOperationReceipt
```

At the first mutation line of the five Stage-A handlers, call the shared guard
when the installed capability registry says `stage_a_only=true`. The guard
round-trips to the fixed owner; a marker, environment variable, JSON object or
locally instantiated Python token cannot satisfy it. Direct handler imports are
therefore denied before mutation.

Before each phase claim, rejoin current RA/Custody/WBC/Release heads, deadline,
process birth, predecessor cursor, ordinal and remaining budget. After critique,
require the exact T1.2/T1.3 selected-attempt/raw-route receipts. Before finalize,
require scoped T1.4 graph admission or its one consumed stable-fingerprint
repair. Gate iteration/revise, skip, repeat, equal/backward cursor, execute and
any transition after the target enter the stop saga.

If a typed eligible failure occurs, the runner may report it only through the
accepted T1.5 occurrence owner. Any fixer or initial notification then uses the
same envelope's bounded T1.6 derivation and current T1.10 owner; a second
occurrence, fixer claim or send is denied. This failure branch always proceeds
to fencing/stopping and never satisfies Stage A.

Precommit an exact target operation ID, predecessor and expected result before
the Run Authority CAS. On lost response, query that operation receipt; do not
compare only the current head. Acceptance of the exact target consumes the
terminal cursor token and persists `FENCE_INTENT_DURABLE` before returning.

`SUCCEEDED_CLOSED` requires all of:

- the exact canonical target-transition receipt;
- a current independent RA/Custody/WBC/Release/process join;
- one runner and no duplicate launch/effect;
- exact T1.2/T1.3/T1.4 receipts for the bounded slice; and
- either confirmed exact stop, or independently proven expired-and-fenced
  denial of every subsequent effect.

Safe failure, target-CAS ambiguity, clock expiry alone, process liveness, logs,
marker, bot prose or a launch-owner projection is not Stage-A acceptance.

## 9. Exact files and minimal source seams

### Add

- `arnold/launch/__init__.py` — public types only.
- `arnold/launch/contracts.py` — strict records, enums and canonical vectors.
- `arnold/launch/ports.py` — frozen owner/effect/observer protocols.
- `arnold/launch/repository.py` — owner-local append/CAS/operation-receipt port.
- `arnold/launch/reducer.py` — event/state reducer.
- `arnold/launch/replay.py` — exact owner-operation replay.
- `arnold/launch/transaction.py` — execute/reconcile/request-stop orchestration.
- `arnold/launch/stop.py` — crash-resumable cross-owner stop saga.
- `arnold/launch/runner_guard.py` — phase claims, outcomes and target CAS.
- `arnold/launch/verifier.py` — independently keyed GO/terminal owner join.
- `arnold/launch/client.py` — fixed server-authenticated opaque-handle client.
- `arnold/launch/production.py` — sole fixed production composition.
- `arnold/launch/cli.py` — `execute`, `reconcile`, `stop`, `status`, `schema`,
  `contract-digest`; optional `prepare` is pure only.
- `arnold_pipelines/megaplan/stage_a_runner.py` — the sole finite runner.

### Modify narrowly

- `arnold/cli/__init__.py`: add `arnold launch-authority ...` dispatch. Do not
  add a second console script.
- `arnold_pipelines/megaplan/handlers/{init,plan,critique,gate,finalize}.py`:
  invoke the shared point-of-use guard before the earliest mutation.
- `arnold_pipelines/megaplan/runtime/manifest_backend.py`: under the pinned
  Stage-A registry, expose only plan/critique/gate/finalize and reject every
  alternate route before handler dispatch.
- `arnold_pipelines/megaplan/chain/__init__.py`,
  `chain/epic_chain.py` and `supervisor/chain_runner.py`: in the Stage-A
  installed generation, raw start/fresh/resume/child/supervisor entrypoints
  return `AUTHORIZED_LAUNCH_REQUIRED` before state/worktree mutation. Read-only
  status remains.
- `arnold_pipelines/megaplan/cloud/cli.py`: add one
  `authorized-stage-a-launch` thin adapter accepting only the opaque handle and
  calling `production_launch_client()`. It may not instantiate a provider.

Do **not** blanket-edit `cloud/providers/*`, recovery, notification, model or
release implementations in T1.9. Their accepted T1.5/T1.6/T1.8 boundaries and
receipts are prerequisites. Generate an installed reachability inventory over
Python, shell, templates, systemd units, package scripts, wheels and
materialized wrappers. Patch a leaf alias only if that test proves it can still
reach launch/upload/start/stop mutation around the shared guard. Any reachable
residual must hard-deny before its first mutation; absent or already-retired
surfaces need no duplicate rewrite.

## 10. Finite tests

Add:

- `tests/arnold/launch/test_contracts.py`
- `tests/arnold/launch/test_authority_provenance.py`
- `tests/arnold/launch/test_production_go_join.py`
- `tests/arnold/launch/test_repository_and_owner_replay.py`
- `tests/arnold/launch/test_reservation_saga.py`
- `tests/arnold/launch/test_transaction_crashes.py`
- `tests/arnold/launch/test_response_loss.py`
- `tests/arnold/launch/test_stop_and_expiry.py`
- `tests/arnold/launch/test_runner_guard_and_budget.py`
- `tests/arnold/launch/test_target_cas_replay.py`
- `tests/arnold/launch/test_independent_verifier.py`
- `tests/integration/test_stage_a_launch_boundary_closure.py`
- `tests/installed_wheel/test_stage_a_launch_authority.py`

The matrix must prove at least:

1. Caller-minted, unsigned, wrong-key, old-incarnation, cross-venue and
   cross-candidate seeds/envelopes/stop capabilities make zero calls.
2. Every missing/stale/expired GO item—including v2 retirement, installed
   release, one-route/no-fallback and T1.10 canary—makes zero reservations and
   zero provider calls.
3. Alias/case/Unicode/symlink/hard-link/collision/corrupt/read-error targets are
   never cleaned or adopted; partial cross-owner reservation is quarantined.
4. Two and 200 concurrent execute/reconcile calls produce one reservation set,
   one slot, at most one upload and at most one start.
5. Crash, ENOSPC, cancellation and response loss before/after every owner append,
   reservation CAS, WBC boundary, provider application, observation, target CAS,
   fence CAS and stop boundary never redispatch a `STARTED` upload/start/stop.
6. Exact operation receipts are adopted after loss even when later valid owner
   history advances the head; a projection/current head alone never proves the
   operation.
7. Definite `NOT_APPLIED` after `STARTED` fails/fences without a second dispatch;
   applied exact evidence is adopted; mismatched/unknown evidence stays sticky.
8. Wrong PID birth/generation/argv/env/cwd/input/GLEK, PID reuse, zero/multiple
   processes and observer disagreement never issue a phase claim.
9. Launch expiry during reservation/upload/start/each phase/target/stop fences;
   restart or boot/clock discontinuity never extends TTL; cleanup remains valid
   after run expiry and cannot restore run authority.
10. Partial failure at every WBC deny/runner fence/RA revoke/Custody advance/
    terminate/observe step resumes from exact receipts, permits only the bound
    stop/reconcile children and never broadly kills.
11. The ordered budget reaches exactly one owner-accepted target beyond v2,
    denies revise/execute/repeat/second milestone, and a finalizer failure stops
    without success.
12. Source, fresh wheel, installed `python -P`, `arnold` executable, thin cloud
    adapter and materialized wrappers expose identical schema/help/digest/error
    behavior; every discovered raw launch alias denies before mutation.

Use exact owner receipts and call counters as assertions. Status, logs, marker
or bot text are never test or acceptance oracles.

## 11. Coding and acceptance order

1. Freeze `BuildInterfaceManifest`; stop if any required port is unaccepted.
2. Implement strict contracts/golden vectors, repository/reducer and exact owner
   replay with no provider adapter.
3. Implement signed issuance, fixed production client and full GO-join verifier.
4. Implement reservations and the stop saga; pass crash/replay/expiry tests.
5. Register only exact upload/start/observe/stop children through frozen T1.6;
   then implement the happy path.
6. Add the process-bound finite runner and point-of-use handler guards.
7. Add the thin CLIs and generated installed reachability inventory; patch only
   demonstrated residual bypasses.
8. Build one clean candidate and prove source/wheel/installed/materialized
   parity plus the isolated finite-slice canary.
9. Obtain the scoped deploy decision, install/attest, run recovery/notification/
   stop canaries, retire v2, resolve CL1 and issue
   `StageAProductionGoManifest`.
10. Independent review may authorize T6.1 only from the complete current owner
    join. It may accept T6.2 only from `SUCCEEDED_CLOSED` evidence.

## 12. Deferred work

Defer multi-venue/failover, lease renewal, multiple runners, arbitrary chain
shapes, generalized launch retries, execute, publication, product deployment,
hot upgrade, generic SSH/subprocess custody, broad provider migration, all model
routes, universal owner-store migration and historical-state migration. They
remain `UNAVAILABLE_IN_GENERATION`; none falls back to legacy behavior.

## 13. Self-check against the nine independent-review findings

| Review finding | Exact revision |
| --- | --- |
| 1. Build dependencies conflated with launch GO | Section 2 splits `BuildInterfaceManifest` from the full runtime `StageAProductionGoManifest`; Sections 6 and 11 make the latter a zero-effect launch gate. |
| 2. Caller-mintable/unauthenticated authority | Sections 3-4 add issuer/subject/audience/venue, owner incarnation/anchor/key, signatures, opaque owner-issued handles, fixed authenticated production composition and independent verifier identity. |
| 3. False cross-owner atomicity | Sections 4 and 6.3 define one Launch owner plus a persisted fail-closed saga and exact per-owner receipts. |
| 4. Owner-CAS replay omitted | Section 5 adds `resolve_owner_operation()` and applies it to reservations, target CAS and every fence/stop owner step. |
| 5. `NOT_APPLIED` redispatch contradiction | Section 6.1 makes every `STARTED` upload/start non-redispatchable; definite non-application is failed/fenced. |
| 6. Cleanup stranded by launch expiry | Section 7 gives stop a longer cleanup-only horizon, fail-closed clock/boot rules and permanent quarantine if cleanup truth stays unknown. |
| 7. Failure/acceptance states incomplete | Sections 5 and 8 add failure, target-indeterminate, fencing, stop-pending terminal states and exact `SUCCEEDED_CLOSED` criteria. |
| 8. T1.9 duplicated dependency scope | Sections 1 and 9 restrict implementation to Launch ownership/runner/verified residual bypasses and explicitly prohibit blanket provider/recovery/model rewrites. |
| 9. Acceptance probes missing | Section 10 adds authority, GO join, cross-owner CAS, later-history replay, expiry/boot, 2/200 concurrency, stop-only and installed parity probes. |

Self-check result: **all nine findings are closed in the specification; ready
for bounded implementation once the named build-time ports are frozen and
accepted.** This document itself grants no production or launch authority.

No source, Git, cloud/provider, owner, checklist, process, existing session or
existing artifact was mutated. This revised delta is the sole write.
