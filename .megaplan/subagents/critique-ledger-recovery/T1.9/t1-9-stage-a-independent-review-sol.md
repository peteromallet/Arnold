# Independent Sol review — T1.9 Stage-A implementation delta

Date: 2026-08-02  
Posture: read-only adversarial review  
Verdict: **REVISE / NO-GO as an implementation handoff**

## Conclusion

The delta has the right minimal product shape: one fresh successor, one
owner-installed upload/start/stop transaction, one runner, the finite
`init -> plan -> critique -> gate -> finalize` slice, no execute/publication or
automatic relaunch, and exact stop/fence after the first owner-accepted cursor
past v2. It is substantially closer to the shortest safe implementation than a
generic launch-platform rewrite.

It is not yet safe to hand to an implementer unchanged. The omissions below can
permit launch before the Stage-A GO predicate, allow caller-minted launch
authority, strand cleanup on expiry, or infer success after response loss. The
delta also assigns T1.9 work already owned by T1.5/T1.6, making it broader than
necessary.

## Exact required edits

1. **Split build-time interface freeze from production launch admission.** Keep
   accepted T1.1/T1.5/T1.6/T1.8 as the coding prerequisites, adding T1.7 only
   if a selected owner actually uses its store. Add a separate immutable
   production GO manifest which `execute` must join and revalidate before every
   effect. It must bind:
   - accepted T1.2/T1.3/scoped-T1.4 contract and receipt digests;
   - exactly one installed physical model route, credential-set identity and
     tool mode, with zero fallback;
   - the accepted scoped T1.10 failure/one-message canary receipt and current
     owner head;
   - the scoped deploy decision, capacity receipt, installed-release receipt,
     live-vector attestation and rollback/forward-fix disposition;
   - current T4.1-T4.5 v2 quarantine, revocation, advanced epoch, per-GLEK
     no-redispatch report and selection-away receipts;
   - accepted T5.1-T5.6 raw CL1 decision, fresh v3 spec/identity reservations,
     finite-slice envelope and verifier challenge.
   Missing, stale, expired, revoked or cross-candidate input must make production
   `execute` unavailable. T1.9 consumes these records; it does not implement
   their owners.

2. **Make issuance provenance explicit.** Add issuer, subject, audience, venue,
   owner endpoint identity, store incarnation/anchor, signing-key ID, decision
   ID, nonce/idempotency ID and signatures to the seed, envelope and stop
   capability. A caller may purely canonicalize a seed but cannot issue an
   executable envelope or stop capability. The installed client accepts only an
   opaque handle minted by the owner-installed Launch Authority and authenticates
   the fixed server/trust root. A compiled socket alone is not authority. Bind an
   independently keyed verifier identity/query/challenge; the verifier must
   recompute the owner join and may not trust `StageALaunchReceipt` as its own
   proof.

3. **Remove the false cross-owner atomicity claim.** Replace “one append-only
   owner transaction” with “one append-only Launch Authority record plus a
   fail-closed saga across RA, Custody, WBC, Release and venue owners.” Reserve
   atomically only inside one owner. Replace “atomically deny new effects” with
   a persisted, stepwise stop saga: durable fence/stop intent; deny all new
   effects except the pre-issued stop/reconcile children; publish runner fence;
   revoke RA; advance/fence Custody; dispatch exact stop; observe absence; join
   all current heads. Persist an exact operation ID and canonical receipt at
   every step so a crash cannot skip or repeat it.

4. **Close owner-CAS replay, not only provider replay.** Extend reconciliation to
   reservation CASes, Launch Authority commits, the target Run Authority CAS,
   each fence/revoke CAS and their receipts. After response loss, adopt only the
   exact pre-bound operation tuple and complete canonical receipt. Never infer
   success from the current projection/head, because later valid history may
   have advanced it; distinguish typed conflict from genuinely unknown outcome.
   Add an explicit `TARGET_CURSOR_INDETERMINATE` path.

5. **Eliminate the redispatch contradiction.** Lines describing authoritative
   `NOT_APPLIED` as allowing the same GLEK to “resume” conflict with “never
   upload/start again” and the accepted shortest-route rule. For bounded Stage A,
   once an upload or start child is `STARTED`, T1.9 never calls dispatch again.
   Exact applied evidence may be adopted; definite non-application becomes a
   durable failed/fenced launch; unknown remains sticky indeterminate. Any more
   general same-GLEK continuation belongs to T1.6 follow-up, not this launch.

6. **Separate launch expiry from cleanup authority.** Give the pre-issued stop
   capability a cleanup-only validity/reconciliation horizon longer than the
   launch TTL and make it usable after the launch grant/lease is expired or
   revoked. It must never restore run authority. Bind serialized wall-clock
   expiry to a locally recorded monotonic deadline and boot/clock identity so a
   restart cannot extend TTL. If cleanup authority itself expires while outcome
   is unknown, all run/effect authority remains permanently denied and the state
   remains visible/quarantined. Mere passage of time is not a stop receipt.

7. **Complete the state and acceptance model.** Add ordinary slice-failure,
   target-CAS-indeterminate, fence-in-progress, stop-pending and quarantined
   states. A graph rejection, critic failure, owner conflict, expiry or process
   mismatch must enter the persisted fence/stop saga. Define Stage-A success
   only as: exact target-transition receipt plus a current independent
   RA/Custody/WBC/Release/process join, followed by either confirmed exact stop
   or independently proven expired-and-fenced denial of every further effect.
   A safe failure, clock expiry alone, liveness, logs, marker or launch-owner
   projection is not acceptance.

8. **Narrow implementation ownership.** Treat T1.5 retirement, T1.6 exclusive
   provider dispatch, T1.2/T1.3/T1.4 semantic enforcement and T1.8 generation
   selection as frozen dependencies. T1.9 should add the launch owner/client,
   reservation/stop/reconcile reducer, canonical runner budget guard and only
   residual installed launch bypasses proven reachable by the generated
   inventory. Do not rewrite every provider, recovery or model file merely to
   duplicate an accepted dependency boundary. Conversely, any leaf alias that
   demonstrably bypasses the shared guard must still hard-deny before mutation.
   Mark the proposed paths as illustrative until the frozen package layouts are
   known.

9. **Add the missing acceptance probes.** The finite matrix must include:
   caller-minted/old-incarnation/cross-venue envelopes and stop capabilities;
   missing or stale production-GO joins; partial failure at every cross-owner
   fence step; response loss before/after every reservation and target/fence CAS;
   later valid owner history after an exact committed operation; launch expiry
   during upload/start/run/stop and process restart/boot change; concurrent
   exact stop; denial of every non-stop child after fencing; and 2/200 concurrent
   launch/reconcile calls. Assertions must use exact owner receipts and provider
   call counts, not projections.

With these edits, the delta is the shortest safe T1.9 implementation: it adds
only the missing launch/stop authority and joins already-owned Stage-A controls,
while retaining the finite reviewer stop rule and deferring platform
generalization.

No source, Git, cloud/provider, owner, checklist, process, session or existing
artifact was mutated by this review. This report is the sole write.
