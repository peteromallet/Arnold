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
