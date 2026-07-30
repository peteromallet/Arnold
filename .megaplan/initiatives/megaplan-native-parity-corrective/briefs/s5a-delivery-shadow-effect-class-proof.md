# S5A — Delivery Shadow and Per-Effect-Class GO-2 Proof

## Objective

Build the delivery workflow in comparison/shadow mode and prove every external
effect-protocol class before any live authority switch or old-writer fencing.
This sprint may not cut over a live effect.

The workflow covers the complete standardized-completion vertical slice:

```text
finalize/admit
  -> execute
  -> landed-write and validation evidence
  -> CompletionVerdict and atomic acceptance
  -> review
  -> reopen an existing subject or admit genuinely new work
  -> execute
  -> root workflow aggregation
```

It also covers approval, dependency-ready dynamic batches, review
fanout/reduction, bounded scoped rework, and re-finalization. S5B consumes the
accepted GO-2 receipt to make the exact slice live.

## Required work

0. Reconsume the exact C1/C2 manifests, S2R kernel-enablement receipt, current
   divergence-ledger hash, accepted M11 coordinates, Custody's exact
   `bounded-incident-projection-handoff.json`, and scoped
   topology/obligation hashes. Missing, stale, unresolved-blocking, or
   mismatched evidence blocks GO-2.

1. Author `delivery/cycle.pype`, `execute.pype`, `execute_batch.pype`, and
   `review.pype` with stable semantic child/item/batch identities, frozen fanout
   membership, keyed reducers, bounded retry/rework, total cancellation and
   resource settlement.
2. Run the delivery topology only in comparison/shadow mode. It may observe
   copied or recorded inputs but cannot acquire admitted effect authority,
   write production idempotency keys, publish terminals, or influence routing.
3. Generate an exhaustive external-effect inventory from source, lowered graph,
   locks, adapters, policy bindings, and live legacy writers/readers.
4. Partition that inventory into effect-protocol equivalence classes bound to:
   adapter and external system; operation and destructive profile; idempotency
   key semantics; intent/outcome protocol; reconciliation behavior; fencing
   and custody requirements; consistency/store guarantees; and crash edges.
5. Execute intent/outcome/crash/cross-host reconciliation proof for every
   class. A class may share a receipt only through a reviewed,
   content-addressed equivalence record verified independently against the
   inventory. A non-destructive proxy cannot authorize a destructive,
   non-idempotent, differently fenced, or differently reconciled class.
6. Execute the complete future-live delivery scenario corpus in shadow:
   `NP-GT-004` effect/crash/reconciliation and `NP-GT-005` scoped rework/
   refinalization; dependency-ready batching; approval; every review outcome;
   `review_blocked -> replan` named unwind; cancellation/late-child/unresolved
   handling; retry/fallback/partial resume; bounded rework and cap exits; cross-
   host recovery; and namespace isolation across generations, siblings, and
   concurrent runs. Bind exact source/lowered/runtime route sets, raw
   multiplicity/causality, terminal/result classes, child/item coordinates,
   policies, locks, adapters, and expected admitted dispositions.
7. Prove the legacy writer is reader/use-def unreachable from the shadow path
   and that the shadow producer cannot act. Mutation and reachability must
   cover route, decision, admission, resume, retry, effect-intent, and terminal
   consumers, not only writers.
8. Emit GO-2 through the generic pre-merge/post-merge `conformance_gate`.
9. Compile task objectives, success criteria, intended write sets, tests, sense
   checks and validation jobs into proposed completion specs; deterministically
   augment landed-write, validation, freshness, runtime, authority, custody,
   WBC and contract-hash obligations; reject vague, circular, trivial,
   unscoped or unverifiable proposals before shadow dispatch.
10. Bind every finalized dynamic task/rework occurrence exactly once through
    normal admission. `accepted(...)` remains a candidate only. Review may:
    reopen a prior semantic subject through a fresh attempt/generation and
    immutable binding; admit genuinely new work under a new stable ID; or
    record an independently verified non-action. It may not mutate/reuse the
    prior binding or dispatch `REVIEW`.
11. Run the captured M10/M11 false-done/unroutable-review fixture end to end.
    Legacy `done` without accepted bound evidence remains incomplete,
    `REVIEW` never reaches the executor, valid new review work is admitted,
    and accepted unrelated evidence remains immutable without rebinding.
    Include the M11 `{1,39}` versus `{1..39}` execution-manifest case and its
    missing/unresolved accepted-attempt dependency chain. Shadow review must
    identify one causal manifest/authority repair scope, preserve affected task
    identities, and avoid emitting duplicate per-task rework for downstream
    symptoms.
12. Exercise crash/reentry at finalize/admission, execution, evidence capture,
    verdict/acceptance, review, reopen/new-work admission, rework execution and
    aggregate completion without duplicate effects, duplicate admission or
    cross-window evidence reuse.
13. Run the 57,000-event corpus in shadow through Custody's bounded query API.
    Record latency/peak-memory and cursor behavior as GO-2 input, and fail any
    fallback to full-history recomputation. Custody—not S5A—owns projector
    implementation and its benchmark receipt.
14. Append every completion parity difference to C1's same
    content-addressed stable-occurrence ledger. GO-2 binds the exact current
    hash and rejects stale or unresolved blocking entries.

## GO-2 gate

GO-2 binds:

- the merged source/compiler/lock/manifest;
- the exhaustive effect inventory and class mapping;
- each class receipt or accepted equivalence record;
- the complete shadow `NP-GT-004/005` scenario matrix and exact expected
  admitted route/cancellation/rework/reconciliation behavior;
- the complete shadow finalize/admit/execute/evidence/verdict/accept/review/
  reopen-or-new-work/aggregate matrix, false-done/`REVIEW` fixture, and exact
  binding/evidence/verdict/decision inventory;
- the exact S2R kernel-enablement receipt, current divergence-ledger hash, and
  Custody bounded-projection handoff plus shadow 57k no-fallback result;
- production adapter/store/schema and certified CAS provenance;
- proof-registry incarnation/restore generation and raw-history cursor;
- shadow namespace and comparison non-promotion proof;
- old-writer reachability and mutation results; and
- the exact receipt-consumption contract S5B must enforce.

Missing inventory members, unmatched classes, proxy overgeneralization,
incomplete future-live scenario coverage, first-time route/cancellation/rework
work deferred to S5B, dual-write, live authority, red/stale evidence, or
producer-only verification fails the gate.

## Handoff to S5B

Produce the authored delivery sources, shadow traces, effect inventory,
equivalence records, full `NP-GT-004/005` shadow behavior matrix,
crash/reconciliation evidence, old-writer reachability proof, GO-2 proof map,
and accepted merged-tree receipt. The live switch must require this exact
receipt; milestone completion alone is not authority.

## Do not close if

- any live effect or old-writer fence occurs;
- list position or completion order defines semantic identity;
- an effect class is omitted or represented by a materially weaker proxy;
- any route, cancellation, named-exit, rework, partial-restart, or
  reconciliation behavior that will become live is not already green in the
  bound shadow corpus;
- a review finding bypasses normal admission, reuses/mutates an old binding,
  executable `REVIEW` reaches dispatch, legacy `done` satisfies completion, or
  the 57k query falls back to full-history recomputation;
- comparison output can be promoted into admitted history;
- shadow or legacy readers can still influence action;
- the receipt does not bind the merged tree and proof-registry incarnation; or
- S5B could bypass receipt validation at its cutover API.
