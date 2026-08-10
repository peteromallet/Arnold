# F1 — Close binding, repair-custody, observation and notification gaps

## Outcome

Close the binding, repair-custody, observation and notification obligations
exposed by VJ24 before v3 receives ordinary execution or publication authority.

## Scope

Implement the category root on every retained Critique recovery/notification
surface: immutable execution binding and migrated-child receipts;
occurrence-bound repair through Run Authority + Custody + WBC; a host-side
coherent owner read; and notification intent/effect custody. Unproven surfaces
remain hard-denied. The broader T0.3/T1.7-T1.10 platform inventory remains
preserved, nonblocking work in `../UNFINISHED_WORK.md` and the Custody Control
Plane rather than being reimplemented here.

## Locked decisions

- The accepted Stage-A route is preserved and regression-tested; this milestone
  generalizes rather than replaces it.
- Every retained Critique recovery mutation path is owner-routed or hard-denied
  at point of use. No blanket skips, xfails or collection hiding.
- Caller-writable projections can never prove that an occurrence has not
  consumed its one mutation attempt. Run Authority owns the one-shot
  grant/CAS/idempotency decision; Custody owns the exact occurrence and epoch;
  WBC records the attempt/effect intent and outcome.
- Missing or rolled-back local rows are not fresh work. Reconciliation rereads
  the owners conjunctively and returns typed UNKNOWN/indeterminate without
  redispatch when proof is absent.
- A fixed-socket process, wrapper or sidecar is only an authenticated adapter:
  it consumes the Run Authority decision/CAS and Custody occurrence/epoch,
  records WBC evidence, and receives lifecycle-owned accepted-state/due data.
  It cannot mint any of those authorities.
- Any plan/chain/source/runtime binding change is an append-only migration that
  creates a causally linked child revision/new attempt with a fresh Run
  Authority fence, Custody epoch and WBC attempt. The parent stays immutable.

### Architecture-fit gate

F1 begins with an owner matrix covering every state field and mutation. It
adopts the existing WBC, Run Authority, Custody and lifecycle/TransitionWriter
contracts rather than adding a ledger, recovery queue, snapshot authority or
persistence service. The completion manifest names the exact accepted owner API
revisions/handoffs. If a required upstream owner contract is pending, the slice
stays action-off or is delivered under that owner; Critique does not fork it.
Before expanding the retained entry-point inventory, F1 proves one complete
crash/response-loss/restart slice through the canonical action envelope.

## Root acceptance (required, not advisory)

The initiative-local
[`../evidence/p2-control-plane-mapping-20260804.md`](../evidence/p2-control-plane-mapping-20260804.md)
and occurrence-specific
[`../evidence/immediate-fix-and-category-hardening-20260805.md`](../evidence/immediate-fix-and-category-hardening-20260805.md)
are required planning inputs. F1 binds the exact
`selector_task_output_contract.v1` and accepted-result-envelope digests into
its occurrence/migration/repair lineage; F2 owns cross-consumer enforcement of
that one version/hash. F1 must not resume r5 in place or treat either handoff as
launch authorization.

- Identical same-key retries deduplicate; divergent same-key retries return a
  typed conflict; store/outbox serialization uses one canonical serializer.
- Every failure, receipt, phase result and recovery mutation carries the
  attempt, occurrence, fingerprint, accepted state version and generation that
  produced it. A stale artifact cannot clear or supersede a newer failure.
- The append-only joined lineage names the parent r5 occurrence, accepted
  migration decision and child revision, Run Authority decision/fence, Custody
  occurrence/lease/epoch, WBC contract/attempt/effect/result, execution binding,
  idempotency key, causal parents and lifecycle source cursor/CAS. This is a
  content-addressed join across canonical records, not a new ledger.
- Repair receipts bind runtime, source commit/tree, worktree, interpreter/import
  roots, wrapper/config/schema and test identity. Any mismatch fails closed
  before mutation.
- The host/provider reader gathers a coherent vector of canonical owner records
  without workload-side SSH. Its snapshot is evidence only; staleness,
  corruption or disagreement returns UNKNOWN and cannot grant action/effect.
- Notification intents are keyed by occurrence, accepted state version, target
  and effect class. Provider rejection or ambiguity persists terminal evidence
  or `INDETERMINATE`; neither permits blind resend.

Each load-bearing category contract needs source, installed-generation,
crash/restart, hostile-replay and exact-receipt evidence. Retired or disabled
paths need denial/no-capability proof, not live canaries.

## Bound inputs

The T6.2 handoff and r5 migration acceptance receipt bind the parent and child
identities. F1 may choose adapters only within the canonical owner contracts;
it may not create a neutral authority store.

## Constraints

No expansion of v3 execution/publication authority, cloud relaunch, marker edit,
same-occurrence resume, or replacement of owner evidence with projections.

## Done criteria

- The r5 parent remains `QUARANTINED_IMMUTABLE`; an independently accepted
  migration receipt links it to a child/new attempt with fresh Run Authority,
  Custody and WBC identities. Same-occurrence resume is impossible.
- At crash points after request, decision, claim, effect and receipt,
  restart/reconciliation produces one terminal or `INDETERMINATE` result and no
  second attempt or effect.
- Every retained Critique recovery/notification mutation path is owner-routed;
  every other discovered path is denied with no-capability evidence.
- The host/provider observer proves coherent before/after reads, projection
  disagreement visibility and UNKNOWN/no-action behavior without workload SSH.
- The deployed adapter passes peer-authentication and exact-occurrence hostile
  tests while proving it cannot mint grants, CAS decisions, occurrences,
  epochs, accepted-state versions or WBC outcomes.
- Restart and 200 unchanged polls emit exactly one occurrence/version-keyed
  notification intent and at most one provider effect; missing provenance or
  ambiguous delivery persists `INDETERMINATE` and emits no redispatch.
- The independent completion manifest binds exact owner API revisions, commits,
  migration receipts and the architecture-fit receipt.

## Touchpoints

Run Authority, Custody, WBC, chain execution binding/migration, canonical
run-state resolver, host status, recovery adapters, notification custody and
the category-relevant portions of T1.5/T1.8-T1.10/T4.6 evidence.

## Anti-scope

Do not implement generic Custody M6A-M11 substrate inside Critique; complete the
broad platform storage/retirement/key-policy inventory; run CL2 feature work;
publish a PR; deploy the product; or mark the incident resolved.
