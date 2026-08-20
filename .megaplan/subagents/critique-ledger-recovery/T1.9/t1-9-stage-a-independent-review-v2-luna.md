# PASS — T1.9 Stage-A implementation delta v2 independent review

Date: 2026-08-02  
Posture: read-only adversarial specification review  
Verdict: **PASS as the bounded T1.9 implementation handoff**

This PASS applies only to the revised Stage-A specification. It is not an
implementation, accepted dependency freeze, installed-release receipt,
production GO decision, `LAUNCH-TXN`/`STOP-TXN` capability, T6.1 authorization,
or evidence that a successor ran or advanced.

## Inputs and scope

- Active objective: T1.9 in
  `docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md:354-367`:
  implement the missing authorized launch/stop transaction, start at most one
  canonical runner without refresh/watchdog custody, pre-issue exact stop
  authority, reject collisions without cleanup, and finish at installed
  CLI/API, negative tests, digest parity and an isolated non-production canary.
- Original NO-GO:
  `t1-9-stage-a-independent-review-sol.md`, SHA-256
  `4ff916a7fc35be3e516c1dbdba66f9e44e32c16dc4c546aeb5cf5f5532af19fc`.
- Revised delta:
  `t1-9-stage-a-implementation-delta-v2-sol.md`, SHA-256
  `9a604b05637d2f9eba54db6a6f42e488e2d2979105a6b0d1d6dcb5665688ad11`.
- Governing plan SHA-256:
  `edddb198701c7567325aac5827100321addbe9e7c5dd458c1329628e82472e0c`.

The review was confined to the finite fresh
`init -> plan -> critique -> gate -> finalize` transaction and its exact
upload/start/fence/stop/reconcile boundary. No source, Git, cloud/provider,
owner, checklist, process or session state was mutated. This report is the sole
write.

## Nine-finding closure

1. **Build freeze versus production GO — closed.** Sections 2.1 and 2.2 now
   separate `BuildInterfaceManifest` from `StageAProductionGoManifest`.
   `execute` must resolve the owner-minted GO handle and recompute the full
   current join before every irreversible child operation. Missing, stale,
   expired, revoked, cross-candidate, cross-venue or disagreeing evidence is
   `GO_JOIN_REJECTED` before reservations or provider calls. T1.9 consumes the
   T1.2/T1.3/scoped-T1.4, T1.5/T1.10, T1.8/release, T4 and T5 records; it does
   not claim to own them.

2. **Authority provenance and exact port identity — closed.** Section 3 binds
   issuer, subject, audience, venue, endpoint, store incarnation/anchor,
   signing key, decision, nonce/idempotency identity and signatures. A caller
   may only perform pure seed canonicalization; executable launch and cleanup
   handles are opaque records issued by the owner-installed Launch Authority.
   Production composition is fixed and server/trust-root authenticated, with
   no constructor injection or test-backend flag. The verifier has a distinct
   key/query/challenge and must independently recompute the owner join.

   Section 4 correctly does not guess unresolved dependency symbols. It defines
   the required Run Authority, Custody, WBC dispatcher, Release Authority,
   reservation owner and independent process-observer roles, while Sections
   2.1, 4 and coding-order step 1 require their exact accepted
   commit/tree/schema/help/contract/endpoint/incarnation/key tuples to be frozen
   before adapter coding. If an exact accepted port is absent or differs,
   production `execute` is unavailable. The protocol ellipses are therefore
   interface requirements, not permission to invent an adapter.

3. **Cross-owner atomicity — closed.** Sections 4, 5 and 6 replace the false
   distributed-transaction claim with one owner-local append/CAS record plus a
   fail-closed saga across RA, Custody, WBC, Release, reservation and venue
   owners. Each step has a stable operation ID and canonical receipt. The stop
   saga durably records fence intent, denies all non-stop children, publishes
   the runner fence, fences RA, advances/fences Custody, dispatches the exact
   stop once, observes exact absence, and rejoins current heads.

4. **Owner-CAS replay — closed.** Section 5 makes
   `resolve_owner_operation()` the sole replay rule for reservation CASes,
   Launch Authority appends, target acceptance and every fence/stop owner step.
   Adoption requires the exact operation ID, pre-bound tuple and complete
   receipt; later valid head advancement does not erase the exact earlier
   receipt. Projection/head inference is forbidden and absent/incomplete proof
   remains typed `INDETERMINATE`, including
   `TARGET_CURSOR_INDETERMINATE`.

5. **WBC/provider non-redispatch — closed.** Sections 6.1 and 6.2 are
   unambiguous: after an upload or start child reaches `STARTED`, T1.9 never
   dispatches it again. Exact applied evidence may be adopted; definite
   `NOT_APPLIED` fails and fences; mismatched or unknown evidence stays sticky.
   The stop child is also pre-bound, CAS-started and dispatched at most once;
   crashes resume from receipts rather than issuing a second stop. No same-GLEK
   continuation or relaunch remains in this bounded generation.

6. **Time basis, expiry and cleanup — closed.** Section 7 binds signed wall
   issuance/expiry and bounded TTL to owner-acceptance wall time, local monotonic
   acceptance/deadline and boot/clock identity, uses the earlier deadline before
   every reservation/effect/phase claim, and treats unprovable continuity after
   restart as expiry rather than a fresh TTL. The pre-issued stop capability has
   a separately signed, longer, cleanup-only reconciliation horizon, remains
   usable after launch grant/lease expiry or revocation, and cannot restore
   authority. Expiry of cleanup truth leaves permanent denial and visible
   quarantine; time passage alone is never a stop receipt.

7. **Failure, stop and acceptance state — closed.** Section 5 includes ordinary
   failed/fenced, target-indeterminate, fencing, stop-started/pending,
   quarantined, expired-fenced and succeeded-closed states. Sections 6 and 8
   route graph rejection, critic/finalizer failure, owner conflict, expiry,
   process mismatch and target ambiguity into durable fence/stop handling.
   `SUCCEEDED_CLOSED` requires the exact target operation receipt, current
   independent RA/Custody/WBC/Release/process evidence, the exact bounded-slice
   receipts, one runner/no duplicate effects, and either exact stop or
   independently proven expiry plus permanent effect denial. Liveness, logs,
   markers, projections, safe failure and clock expiry alone cannot satisfy it.

8. **Implementation ownership and finite authority — closed.** Sections 1, 9
   and 12 restrict T1.9 to Launch Authority/client/repository/replay,
   reservation/stop orchestration, runner budget/guard, thin CLI adapters and
   only residual installed aliases proven reachable by generated inventory.
   T1.5 retirement, T1.6 effect dispatch, T1.2/T1.3/scoped-T1.4 semantics and
   T1.8 release selection stay frozen dependencies. Blanket provider/recovery/
   notification/model rewrites are explicitly forbidden.

9. **Acceptance probes — closed.** Section 10 now covers forged/old-incarnation/
   cross-venue authority; every stale or missing GO join; alias/collision and
   corrupt/read-error targets; partial reservation and every fence step; crash,
   ENOSPC and response loss before/after every owner/provider boundary; later
   valid history; definite-not-applied and sticky unknown; PID birth/reuse and
   process disagreement; expiry at every phase plus restart/boot discontinuity;
   concurrent exact stop; denial of non-stop children; 2/200 concurrent
   execute/reconcile; target replay; installed/materialized parity; and exact
   receipt/provider-call-count assertions rather than projection or prose.

## Finite-boundary audit

The phase surface is exactly `init`, `plan`, `critique`, `gate`, `finalize` in
order. Phase claims round-trip to the fixed owner at the earliest mutation seam
and rejoin current RA/Custody/WBC/Release heads, deadline, process birth,
predecessor cursor, ordinal and remaining budget. The target operation is
precommitted and accepted by exact RA CAS under the frozen installed cursor
ordering; equal/backward cursors, repeats, skips, revise, execute, a second
finalize/milestone and every post-target transition enter the stop saga. Target
acceptance atomically consumes the terminal cursor token and durably records
fence intent before returning.

The effect budget is likewise finite: one immutable input upload, one runner
start, one exact stop, the accepted bounded model-attempt set, at most one
scoped fixer and at most one initial notification; all unlisted effect families
are unavailable. The exact numeric/model and cursor vectors are owner-signed
manifest data pinned before execution, not caller options.

The delta grants no execute, revise loop, second milestone/finalize, Git/ref/PR
publication, product deployment, source/runtime refresh, package installation,
model fallback, generic command execution, broad process termination, lease
renewal or automatic relaunch. Publication namespaces are reserved only to
prove collision-free denial; they are not publication authority.

## Acceptance conditions carried into implementation

This PASS depends on enforcing the delta's own stop conditions literally:

- coding stops at `BuildInterfaceManifest` if any exact accepted port,
  endpoint, schema/digest, owner incarnation/key or installed generation is
  unavailable or disagrees;
- no hermetic/test owner, caller-supplied transport, callback, repository,
  provider or signing key is reachable from production composition;
- every reducer/event/receipt and phase/effect budget is strict canonical data,
  and no status projection substitutes for an owner receipt;
- `STARTED` upload/start/stop children are reconciled only, never redispatched;
- every failure path records fence intent before exposing another phase claim,
  and cleanup cannot renew launch authority;
- source, wheel, installed `python -P`, CLI, thin adapter and materialized
  wrapper parity plus the isolated canary must pass before T1.9 can be claimed.

Subject to those explicit invariants, the revised delta is the shortest safe
implementation plan for T1.9 and is **PASS / GO for bounded implementation**.
