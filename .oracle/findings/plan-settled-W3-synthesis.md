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
