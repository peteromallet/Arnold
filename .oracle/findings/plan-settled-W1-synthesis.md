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
