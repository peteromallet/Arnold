---
type: brief
slug: m5a-atomic-fail-closed-milestone-completion
title: Atomic fail-closed milestone completion boundary
epic: custody-control-plane
created_at: '2026-07-14T20:51:40+00:00'
---

# M5A — Atomic fail-closed milestone completion

## Outcome

Implement one atomic, fail-closed milestone completion transaction for
Megaplan chains. A milestone must not become `executed`, complete, merge-ready,
or advanceable until its entire declared acceptance boundary succeeds against
one exact tested commit and runtime identity. A failed or unknown predicate
must leave the milestone unaccepted, emit a typed repair target, and prevent
every successor from starting. After any repair, the transaction must rerun
the complete end-to-end acceptance boundary before it can commit success.

M5A starts only after M5 has real manually reviewed acceptance evidence. It
uses M5's six-review failure sequence as the required regression case, then
gates M6 and every later Custody Control Plane milestone on the landed M5A
completion contract.

## Authoritative incident and starting evidence

- M5 is the active predecessor:
  `m5-run-authority-receipt-reconciliation-and-retirement`, plan
  `m5-run-authority-receipt-20260714-1428`, with PR #250 and manual review/merge
  custody. M5 is not accepted merely because execution or a review worker ran.
- The repeated-review pattern began when execution reported success despite
  three rejected Run Authority receipts, chain verification divergence,
  collection/import failures, and stale or premature manifest, retirement,
  and attestation evidence. Partial repairs then fixed one layer at a time and
  triggered another review rather than revalidating the whole boundary.
- Current M5 acceptance ordering is receipts, verification, lifecycle-generated
  proof/manifest, canonical metadata-only retirement, then final attestation.
  M5A must preserve and enforce that order in its regression fixture.
- Existing worker, watchdog, repair, review, PR, CI, authorization, and manual
  merge gates remain independent requirements. Activity, repair attempts,
  status projections, or infrastructure liveness never constitute acceptance.

## In scope

- Define a versioned milestone-completion transaction with an immutable
  acceptance snapshot and one commit point. The transaction must bind the
  chain/spec identity, milestone label and index, predecessor receipt, plan and
  finalized task graph, exact tested Git commit/tree, source/import/editable
  runtime revisions, test commands and results, PR/merge evidence when
  required, and every declared acceptance artifact by content address.
- Make the completion state transition compare-and-set and fail closed. Do not
  persist `executed`, completion, merge-ready, successor-ready, a completion
  receipt, or the next milestone cursor unless the same transaction validates
  the full acceptance snapshot. Crash, partial write, stale evidence, unknown
  status, timeout, or identity drift must preserve the prior unaccepted state.
- Require full acceptance-suite success. Collection, import, selector,
  execution, timeout, skipped-required-test, and missing-log failures are
  failures. A scoped repair check may diagnose a target, but it cannot close
  the transaction or replace the complete declared suite.
- Require accepted, lifecycle-generated, content-addressed completion receipts;
  canonical verification with zero divergences; valid prerequisite and
  retirement ordering; and a final attestation whose subject is the exact
  tested commit/runtime/evidence snapshot. Hand-authored, stale, rejected,
  shadow, warning-only, or hash-mismatched evidence is inadmissible.
- Model retirement as an ordered acceptance predicate. For the M5 regression,
  prove accepted Run Authority receipts and zero-divergence verification before
  proof/manifest regeneration, create the canonical metadata-only retirement
  marker only afterward, and create the final attestation only after the marker
  exists. A premature marker or attestation blocks completion.
- Emit a durable typed repair target for every failed or unknown predicate. At
  minimum bind chain/milestone/plan identity, acceptance-transaction identity,
  exact failed predicate and phase, expected and observed content addresses,
  tested commit/runtime identity, evidence references, safe recovery action,
  retry eligibility, retry budget, custody owner, and causal predecessor. Keep
  fixer-launch/infrastructure failures distinct from the underlying milestone
  failure signature.
- On any repair result, invalidate the prior candidate acceptance snapshot and
  run complete end-to-end revalidation from source/runtime identity through the
  full suite, receipts, zero-divergence verification, ordered retirement proof,
  final commit-matched attestation, review/CI/publication gates, and successor
  admission. Rechecking only the failed selector is never sufficient.
- Gate successor initialization at every entry path: normal chain continuation,
  resume, repair/relaunch, watchdog action, manual retry, state reconciliation,
  cloud/resident wrapper, and crash recovery. M6 must be impossible to
  initialize unless M5A has one accepted completion transaction for the exact
  landed/runtime identity.
- Add structured progress evidence that distinguishes accepted milestone
  transitions from worker/review/repair activity. Watchdog escalation must be
  based on absence of accepted progress while separately reporting fixer
  infrastructure failures and current automatic continuation custody.

## Out of scope

Weakening or bypassing manual review, CI, merge, authorization, safety,
execution-binding, or runtime-promotion gates; accepting M5 without its real
evidence; editing receipts/manifests/attestations to force acceptance; deleting
immutable evidence; relaunching Run Authority; launching a parallel Custody
chain; or treating infrastructure availability as guaranteed.

## Locked decisions

- Completion is a single fail-closed transaction, not a sequence of optimistic
  status writes later corrected by review.
- Acceptance is content-addressed and bound to the exact tested commit and
  actual imported runtime. Branch names, latest refs, PR heads observed at a
  different time, working-tree bytes, or nominal green labels are not identity.
- Any false, unknown, missing, stale, rejected, divergent, out-of-order, or
  unbound predicate aborts without advancing the chain.
- Repair does not inherit acceptance. Every repair produces a new candidate
  snapshot and reruns the complete boundary.
- M5 remains behind its existing manual review/merge gate. M5A also requires
  normal planning, execution, independent review, full CI, merge authorization,
  and exact landed/runtime verification. Neither milestone is pre-completed by
  this brief.
- M6 and all former successors retain their relative order and cannot start
  until M5A passes.

## Done criteria

- A versioned completion transaction validates and atomically commits all
  declared milestone acceptance predicates, or durably records no completion
  and one typed blocker/repair target. Failure injection proves no torn state
  can expose `executed`, completed, merge-ready, or successor-ready early.
- The required full acceptance suite succeeds from a clean checkout at the
  exact tested commit and actual imported runtime. Raw logs, commands, exit
  codes, timestamps, suite identity, commit/tree, and content digests are
  durably linked to the accepted transaction.
- All required completion receipts are lifecycle-generated, content-addressed,
  current, and `accepted: true`; canonical verification reports exactly zero
  divergences; retirement predicates are in valid order; and the final
  attestation binds the identical tested commit/runtime/evidence snapshot.
- Every failure class emits a stable typed repair target, including rejected
  receipt, divergence, suite collection/import/selector failure, premature
  retirement, stale manifest, commit/runtime mismatch, attestation mismatch,
  review/CI/publication failure, fixer-launch failure, and unknown evidence.
- A repair of any one predicate forces a complete new end-to-end validation.
  Tests prove that cached success from the prior candidate cannot satisfy the
  new transaction and that a passing focused selector alone cannot advance.
- Regression coverage recreates the six-review M5 pattern: initial optimistic
  execution with rejected/divergent/stale evidence, successive partial repairs,
  missing lifecycle selectors, and repeated review. The new boundary stops at
  the first invalid predicate, emits the correct typed target, revalidates all
  layers after repair, and commits exactly once only when all evidence agrees.
- Concurrency, crash/restart, duplicate driver, stale worker, retry, and
  out-of-order event tests prove idempotent exactly-once completion and no
  successor initialization before the accepted commit point.
- Chain start/resume/reconcile/repair/watchdog/cloud/resident entry-point tests
  prove M6 remains pending when M5A is absent, rejected, stale, unknown, or
  bound to a different commit/runtime. The supported normal continuation path
  selects M5A immediately after M5 and M6 immediately after accepted M5A.
- Independent review and CI pass at the final PR head; the accepted transaction
  is regenerated or verified for the landed commit; publication and runtime
  promotion evidence are exact; no safety or authorization gate is bypassed.

## Touchpoints

Megaplan chain state and cursor advancement, execution/finalize/review and
completion-receipt lifecycle, chain verification and manifests, suite ledger
and full-suite backstop, repair target/queue and recurrence classification,
watchdog/progress projections, execution binding and runtime promotion
attestation, cloud/resident chain wrappers, Git/PR/CI evidence, M5 handoff
artifacts, and focused plus end-to-end chain regression tests.

## Anti-scope

Do not rename optimistic execution as acceptance, whitelist the current M5
evidence, carry green sub-results across a repair, infer the tested commit from
the current branch, create retirement evidence early, mark M5/M5A complete in
planning state, mutate the immutable launch identity implicitly, hand-edit
persisted chain state, or start a second chain driver.

## Stop and rollback conditions

Stop without successor admission on any untyped failure, non-atomic state
write, acceptance evidence that cannot be reproduced by content address,
incomplete full-suite run, non-zero divergence, invalid retirement order,
commit/runtime mismatch, ambiguous repair custody, or entry path that can
initialize M6 early. Rollback may disable the new completion writer but must
preserve immutable evidence, typed failures, and the fail-closed successor gate.

## Handoff and dependencies

Dependency: M5's actually accepted and manually merged reconciliation and
retirement handoff, including three accepted Run Authority receipts,
zero-divergence verification, valid retirement ordering, and attestation bound
to its exact tested and landed/runtime identity. If that evidence is absent or
stale, M5A stops rather than normalizing it.

Handoff to M6: the landed completion-transaction schema and implementation,
accepted M5A transaction/receipt, full-suite and zero-divergence evidence,
typed-repair and end-to-end-revalidation proof, six-review regression results,
exact landed/runtime attestation, independent review/CI/publication evidence,
and proof that every successor entry path fails closed without that bundle.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex +prep`. This changes the
authoritative milestone transition boundary across execution, evidence, repair,
review, state persistence, and every continuation path. A locally green but
non-atomic implementation could falsely advance the entire epic.
