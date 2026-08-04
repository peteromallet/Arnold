# F1 — Complete deferred owner, storage and recovery hardening

## Outcome

Close the owner/storage/recovery obligations intentionally scoped out of the
bounded Stage-A finalize canary before v3 receives ordinary execution or
publication authority.

## Scope

Complete deferred T0.3 residue; platform adoption of T1.7 owner-local
transactional storage; the non-exercised but shipped T1.5 legacy recovery
retirement and honest disposition of all formerly hidden assertions; full T1.10
key rotation, reminder buckets and child GLEKs; remaining T1.8/T1.9 owner/store
generalization; and preparation of T4.6 without rewriting evidence.

## Locked decisions

- The accepted Stage-A route is preserved and regression-tested; this milestone
  generalizes rather than replaces it.
- Every canonical owner fails closed on corrupt/missing state, has a current
  revision/fence/incarnation and preserves sticky indeterminacy.
- Every still-shipped ordinary recovery mutation path is either owner-routed or
  hard-denied at point of use. No blanket skips, xfails or collection hiding.
- Notification key rotation and reminders cannot mint a second occurrence or
  re-send an unchanged decision.
- Caller-writable projections can never be the sole proof that an occurrence
  has not already consumed its one mutation attempt. The production
  effect-owner/WBC service holds a monotonic, occurrence-scoped consumed-grant
  or idempotency record outside those projections.
- Missing or rolled-back local attempt/claim/effect rows are not interpreted as
  fresh work. Reconciliation consults the external monotonic authority and
  returns typed UNKNOWN/indeterminate without redispatch when proof is absent.
- The production fixed-socket owner—not a caller or wrapper—issues the exact
  occurrence target/ref, accepted state version, quiet transition and due
  selection. Immediate/reconcile wrappers receive the exact occurrence ID.

## P2 control-plane acceptance (required, not advisory)

The initiative-local mapping in
[`../evidence/p2-control-plane-mapping-20260804.md`](../evidence/p2-control-plane-mapping-20260804.md)
is a durable planning input. F1 must prove these additional root invariants;
they are not satisfied by a passing unit test or by preserving a dirty
worktree:

- VJ9/VJ8 exact-idempotency contracts are separated: a same-key identical
  retry deduplicates, a divergent same-key retry returns a typed conflict,
  and store/outbox serialization comes from one canonical serializer.
- Every failure, receipt, phase result, and recovery mutation carries the
  attempt, occurrence, fingerprint, and generation that produced it. A stale
  artifact cannot clear or supersede a newer failure.
- Repair receipts bind runtime, source commit/tree, worktree, interpreter, and
  test identity. Changed imports or test hashes fail closed before mutation.
- Occurrence IDs, consumed grants, exact wrapper handoff, notification dedupe,
  and no-redispatch decisions are authoritative outside caller-writable
  projections. Snapshot/projection corruption, storage failure, and replay
  are explicit typed failures with deny-before-mutation behavior.

Each item needs source, installed-generation, crash/restart, hostile-replay,
and exact receipt evidence in the F1 completion manifest. The mapping source
digest is recorded in the initiative-local copy; do not silently replace it
with a later unreviewed mapping.

## Open questions

- Which owners can adopt the neutral store directly and which require an
  adapter/migration with a reconciled saga?

## Constraints

No expansion of v3 execution/publication authority, cloud relaunch, marker edit,
or replacement of accepted owner evidence with projections.

## Done criteria

- Storage reserve/capacity and crash/ENOSPC behavior are proven platform-wide.
- Required owners use accepted transactional storage or an independently proven
  equivalent.
- Full recovery topology inventory has zero live unowned mutation path and the
  historical 741 assertions have explicit passing retirement/no-side-effect
  dispositions.
- Full notification rotation/reminder/child-key semantics pass source, wheel and
  installed-generation tests.
- Coordinated erasure and rollback after both ambiguity and completed success
  cannot mint a new attempt or effect, including after process and host restart.
- The deployed production owner passes peer authentication, monotonic
  consumed-grant, exact-occurrence wrapper, quiet-transition, due-selection and
  accepted-state-version hostile tests; the test-only SQLite owner is not used
  as deployment evidence.
- Restart and 200 unchanged polls emit at most one occurrence/version-keyed
  notification effect; missing provenance emits zero.
- Independent completion manifest binds exact commits, migrations and receipts.

## Touchpoints

`arnold.storage`, recovery/simple-fixer topology, notification custody, release
and launch owners, capacity controls, installed wrappers and evidence for
T0.3/T1.5/T1.7-T1.10/T4.6.

## Anti-scope

Do not run CL2 feature execution, publish a PR, deploy the product, or mark the
incident resolved.
