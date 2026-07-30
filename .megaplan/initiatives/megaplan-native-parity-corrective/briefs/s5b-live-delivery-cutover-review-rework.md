# S5B - Live Delivery Cutover, Review, and Rework

## Objective

Consume S5A's accepted per-effect-class GO-2 receipt, then cut over one authored
reusable delivery workflow:

```text
finalize -> approval -> dependency-ready dynamic batches
         -> review fanout/reducer -> bounded scoped rework -> finalize ...
```

The cycle must preserve exact task/batch/item identity, survive partial failure
and cross-host handoff, and never duplicate an accepted external effect.
It is also the sole live cutover for the complete standardized-completion
vertical slice proven by S5A. Reopened and genuinely new review work always
returns through normal finalization/admission; executable `REVIEW` is
forbidden.

Re-execute the S5A-green `NP-GT-004` and `NP-GT-005` scenarios from
`../GOLDEN_TRACE_CONTRACT.md` on the admitted path. S5B may bind authority and
prove admitted equivalence; it may not first implement or first prove a
delivery route, cancellation disposition, named exit, rework edge, or
reconciliation behavior after the switch.

## Mandatory GO-2 consumption at the cutover boundary

The live-effect authority switch and every old-writer disable/fence/delete
operation must validate and consume the exact accepted S5A GO-2 receipt. The
receipt must bind the merged S5A tree, effect-protocol inventory and equivalence
records, production adapter/store/schema, proof-registry incarnation and raw
history cursor. A milestone status, filename, copied verdict, or later S7
replay is not sufficient.

Only dual-read comparison is allowed before the receipt is accepted;
dual-write is forbidden. Failure means no live-effect cutover and no old-writer
fence/deletion.

The switch additionally validates the exact C1/C2 manifests, S2R
kernel-enablement receipt, current divergence-ledger hash, and Custody
`bounded-incident-projection-handoff.json`. The Custody receipt must bind
full-rebuild parity and the 57,000-event latency/peak-memory benchmark. Missing
or mismatched completion/projection evidence leaves the old live path intact.

GO-2 must contain the complete shadow `NP-GT-004/005` scenario matrix, not only
the effect-class inventory. The switch rejects if the exact source/lock/
topology/policy/effect bindings differ from that matrix.
It runs only as the chain's declared S5B transition, consuming both the current
merge-HEAD readiness receipt and S5A's accepted GO-2 milestone receipt. The
chain records the live-switch receipt and requires a separate post-transition
S5B verifier over writer fences and admitted behavior before completion.

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

- Add exactly one workflow to each of
  `workflows/delivery/cycle.pype`, `execute.pype`,
  `execute_batch.pype`, and `review.pype`. `cycle.pype` visibly owns
  finalize → approval → execute → review/rework routing; the other three are
  canonical workflows invoked as children. Reusable delivery leaves and
  support definitions live in `delivery/*.py`; private local steps remain
  unimportable and digest-bound to their containing workflow.
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
- Bind task objectives, criteria, write sets, tests, sense checks and validation
  jobs to immutable completion specs and admission bindings. Deterministically
  require landed writes, validation, freshness, runtime, authority, custody,
  WBC and contract hashes. `accepted(...)` proposes a candidate and cannot
  bypass the evaluator or existing atomic acceptance transaction.
- Route every review finding by identity. Reopen an existing semantic subject
  only through a fresh admission/attempt/generation/binding referencing the
  prior subject; admit genuinely new work under a new stable identity; or
  accept a separately evidenced non-action. Never mutate or reuse the prior
  binding, and never dispatch the pseudo-task `REVIEW`.
- Preserve accepted evidence and bindings for unaffected tasks. Aggregate the
  workflow only after every admitted child binding has an accepted or
  explicitly permitted candidate outcome under S2R's total primitive
  instances.
- Use M11's effect intent/outcome, ambiguity, idempotency, persistence,
  reconciliation, query, and recovery facilities; do not recreate them.
- Delete/fence execute/review/finalize component routes, handler route strings,
  auto scheduling decisions, compatibility projection authority, and index-only
  checkpoints for the corrected cycle.
- Emit same-run `NP-GT-004` effect/crash/reconciliation and `NP-GT-005`
  scoped-rework/refinalization receipts into the final proof map.
- Re-execute the captured false-done/`REVIEW` fixture on the admitted live path:
  legacy `done` without an accepted bound verdict is incomplete, new review
  work is normally admitted and executable, and unrelated accepted evidence
  remains unchanged.
- Re-execute the captured discontinuous execution-manifest fixture on the
  admitted live path: `{1,39}` cannot masquerade as `{1..39}`, unresolved
  accepted-attempt dependencies cannot inherit completion, and reconciliation
  emits one bounded causal repair scope rather than duplicating every
  downstream task symptom.
- Execute at least the captured 57,000-event history through Custody's exact
  bounded/cursor-incremental projection API. Pin latency and peak-memory
  budgets, prove cursor/snapshot-plus-tail consumption and full-rebuild parity,
  and fail any runtime/query fallback that rereads or hashes the full journal.
  S5B consumes and rechecks the Custody receipt; it does not implement the
  projector, checkpoint, snapshot or invalidation scheme.
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
- Consume S5A's GO-2 shadow records only as quarantined proof input. Never
  promote them into admitted history. The authority switch validates the exact
  post-merge receipt and atomically leaves one admitted writer behind the
  shared validator.
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
- The exact S5A GO-2 receipt is accepted and consumed by the switch before any
  old writer is disabled or any live effect authority cutover occurs.
- The full admitted completion slice has exact equality among durable subjects,
  bindings, required evidence, verdicts, accepted decisions/effects and
  terminal candidate outcomes; the exact current divergence-ledger hash has no
  unresolved blocking entry.

## Custody-adoption gate

- Crash before/after effect intent/outcome, partial persistence, cross-host
  transfer/reclaim, and retry rerun only incomplete children and never duplicate
  an accepted effect.
- Wrong task target, stale fence, stale lease epoch, historical WBC success,
  and forged projection all fail positive action.
- Parent/child subject attempts, WBC attempts, and custody targets remain
  distinct and causally joined to the exact semantic child paths.
- Each admitted effect-protocol class retains one effect intent/outcome,
  rebuilds a missing product receipt from durable WBC history, and never
  replays an accepted external effect.

## Do not close if

- Checkpoints are index-only, WBC identity is handler/phase-only, or custody is
  leased at an overly broad session target.
- Review rework returns after one duplicate block rather than cycling.
- Review bypasses admission, reuses an old binding, admits `REVIEW` as an
  executable identity, loses unrelated accepted evidence, or accepts legacy
  `done` without a bound verdict.
- An evidence receipt is used as execution, resume, adoption, or completion
  authority.
- An external effect is dual-written, or live cutover/deletion precedes a green
  GO-2 receipt.
- Namespace derivation relies on Python object identity, list position, display
  label, or a broad phase/session name.
- Replan is smuggled through payload/sentinel/exception, reducer output depends
  on completion order, or comparison history becomes admitted/resumable.
- The 57k path uses a Native/Completion-owned projector or falls back to
  full-history recomputation instead of consuming Custody's exact handoff.
