# S5 - One Reusable Delivery Cycle

## Objective

Implement one authored reusable delivery subworkflow:

```text
finalize -> approval -> dependency-ready dynamic batches
         -> review fanout/reducer -> bounded scoped rework -> finalize ...
```

The cycle must preserve exact task/batch/item identity, survive partial failure
and cross-host handoff, and never duplicate an accepted external effect.

Make `NP-GT-004` and `NP-GT-005` in
`../GOLDEN_TRACE_CONTRACT.md` green incrementally.

## Mandatory GO-2 live-effect stop/go

After the new delivery producer/action envelope exists, but before any live
effect cutover or legacy writer delete/disable/fence, execute a
production-shaped non-destructive/idempotent effect through checkout and the
clean installed artifact. Inject a crash after durable external effect outcome
but before product receipt, reconcile on another host exactly once, prove the
old writer is inert, and emit the GO-2 receipt.

Only dual-read comparison is allowed before GO-2; dual-write is forbidden.
GO-2 failure means no live effect cutover and no old-writer fence/deletion.

## Product scope

- deterministic ready-batch calculation over finalized task dependencies,
  oversized-task splitting, complexity-based model routing, fresh sessions,
  worker cap, sequential fallback, and result merge;
- destructive/user approval, no-review terminal, and deferred-human gates;
- non-retryable block, cancellation/await/orphan handling, retry, partial
  resume, recover-blocked, and dependency recomputation;
- review worker/check dynamic fanout, infrastructure retry, reducer, typed
  decision, human verification, blocking/advisory cap outcomes;
- scoped re-finalization, re-execution, and re-review in one bounded cycle.

## Required work

- Use deterministic semantic child coordinates containing task ID, batch
  identity, and item path; list index alone is forbidden.
- Give parent/child WBC execution attempts explicit causal joins and preserve
  them across cancellation, fallback, retry, and resume.
- Acquire/validate Custody per exact authoritative task/effect target, not a
  broad phase/session name. Transfer/reclaim must increment epoch.
- Validate every dispatch/effect/acceptance with the current Run Authority
  fence and Custody epoch through M11's action validator.
- Bind accepted batch/review/final results through Run Authority decisions.
  Verify-only repair/adoption must match revision, task contract, tree/tests,
  semantic path, fence, and epoch.
- Use M11's effect intent/outcome, ambiguity, idempotency, persistence,
  reconciliation, query, and recovery facilities; do not recreate them.
- Delete/fence execute/review/finalize component routes, handler route strings,
  auto scheduling decisions, compatibility projection authority, and index-only
  checkpoints for the corrected cycle.
- Emit same-run `NP-GT-004` effect/crash/reconciliation and `NP-GT-005`
  scoped-rework/refinalization receipts into the final proof map.
- Derive every delivery state, checkpoint, artifact, effect-idempotency, and
  cache namespace from run identity plus delivery generation and exact semantic
  task/batch/item/retry/reentry coordinates.
- Add collision tests for two sequential delivery-cycle generations, two
  same-kind siblings in one fanout, and concurrent runs with identical product
  task IDs. None may cross-read, overwrite, or accidentally deduplicate another
  instance's state, artifacts, checkpoints, effects, or cache entries.
- Express `review_blocked -> replan` as a typed exit addressed to the named
  enclosing `planning_cycle`. Acceptance terminates/closes that target ledger,
  records exactly one `superseded_by_named_exit` control terminal for every
  intervening durable scope in innermost-to-outermost order, and lets the parent
  explicitly create a new planning-cycle instance at generation zero. Only
  declared digest-bound carry fields survive; no sentinel state, exception or
  child-to-root terminal is allowed.
- Freeze each delivery/review fanout's canonical item set, context, policy,
  prompt/tool and artifact bindings at admission. Every child consumes that
  digest; reducers consume a canonical keyed multiset and are invariant to
  completion order.
- Keep GO-2 shadow/dry-run records solely in the comparison namespace. Prove
  the candidate cannot acquire action authority, emit an admitted effect, or
  promote its history, while old and candidate paths remain registered behind
  one shared validator and exactly one admitted writer.
- Default cancellation to reconcile any intent-without-outcome ambiguity before
  parent acceptance. A site may explicitly declare
  `cancelled_pending_reconciliation(obligation_id)` as a child lifecycle
  terminal—not an effect terminal—with a separately fenced reconciliation
  target. Late resolution cannot rewrite the parent terminal; compensation
  needs a fresh decision.
- Remove S4's finalize/delivery seam and generate a closed typed delivery-to-
  legacy-control serializer with registered durable writes, route-inert
  mutations and S6 expiry.

## Semantic gate

- One reusable authored cycle, not manually duplicated passes, determines all
  execute/review/rework routes and cap outcomes.
- Scenarios cover denied/approved destructive action; dynamic batch ordering;
  batch 2-of-4 block and exact resume; cancellation/fallback; no-review done;
  review infrastructure retry; scoped rework and re-review; blocking cap;
  advisory force-proceed; deferred-human verification.
- Runtime child set, topology, and checkpoint coordinates equal the authored
  dynamic set; legacy route mutation cannot change behavior.
- Repeated and concurrent instances preserve isolated durable namespaces even
  when display labels and product task IDs match.
- Completion-order permutations and attempted sibling context mutation preserve
  the reducer decision and frozen child bindings; the named replan exit reaches
  exactly the declared outer loop, closes every required ledger and reenters a
  fresh instance.
- GO-2 is green before any old writer is disabled or any live effect authority
  cutover occurs.

## Custody-adoption gate

- Crash before/after effect intent/outcome, partial persistence, cross-host
  transfer/reclaim, and retry rerun only incomplete children and never duplicate
  an accepted effect.
- Wrong task target, stale fence, stale lease epoch, historical WBC success,
  and forged projection all fail positive action.
- Parent/child subject attempts, WBC attempts, and custody targets remain
  distinct and causally joined to the exact semantic child paths.
- The GO-2 installed cross-host trace contains one effect intent/outcome,
  rebuilds the missing receipt from durable WBC history, and never replays the
  external effect.

## Do not close if

- Checkpoints are index-only, WBC identity is handler/phase-only, or custody is
  leased at an overly broad session target.
- Review rework returns after one duplicate block rather than cycling.
- An evidence receipt is used as execution, resume, adoption, or completion
  authority.
- An external effect is dual-written, or live cutover/deletion precedes a green
  GO-2 receipt.
- Namespace derivation relies on Python object identity, list position, display
  label, or a broad phase/session name.
- Replan is smuggled through payload/sentinel/exception, reducer output depends
  on completion order, or comparison history becomes admitted/resumable.
