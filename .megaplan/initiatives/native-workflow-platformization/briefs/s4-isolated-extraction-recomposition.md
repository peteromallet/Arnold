# S4 — Isolated extraction and recomposition

## Objective

Extract the first reusable patterns through the S2A runtime, S2B authoring
core, and S3 developer tooling,
make Megaplan consume the shared implementations, and prove that reuse survives
different bindings, concurrent instances and supported composition shapes
without changing Megaplan's accepted behavior. Demonstrate the authoring loop
for edited components while preserving production isolation.

## Normative contract and inputs

[`../decisions/PLATFORM_CONTRACT.md`](../decisions/PLATFORM_CONTRACT.md) is normative. Consume the
Native Parity completion and handoff evidence, S1's classification and candidate
contracts, and the S2A/S2B/S3 content-addressed implementation/proof handoffs.
Continue to run the inherited Native Parity golden and DX corpora; extraction
cannot replace them with generic-only tests.

The consumed lineage includes the exact C1/C2 manifests, sole S2R GO-0
enablement receipt, current divergence-ledger hash, and Custody bounded-query
benchmark receipt. S4 migrates Megaplan to the already extracted completion
implementation; it does not copy, wrap, re-enable, or reinterpret it.

## Receipt-bound Megaplan adoption

The shared implementations, candidate bindings, and migration transaction may
land together, but the active Megaplan dependency lock/binding remains on the
previous implementation through merge. The S4 stage gate proves the merged
candidate against generic and Megaplan golden evidence. Only an explicit
binding/lock migration operation that validates and consumes that exact
accepted post-merge S4 receipt may make the shared implementation authoritative
for new Megaplan work. Existing occurrences stay pinned unless an independently
accepted occurrence migration applies. The switch is atomic and rejects a
status, path, copied verdict, stale hash, or receipt from another incarnation.
The operation runs only in the chain's declared S4 transition phase. Its
immutable output receipt and the resulting selected binding/lock are inputs to
the separate post-transition S4 verifier; failure prevents milestone completion
without pretending the pre-transition state was migrated.

## Locked decisions

- First-wave candidates are the evaluator panel, bounded refinement loop, typed
  human gate, and effect-safe action. Product-specific planning, critique, gate,
  finalization and task meaning stay in Megaplan unless S4 proves otherwise.
- Extracted code accepts product types, policies, outcomes, effects, storage,
  models/tools and resources through typed bindings; it has no Megaplan import,
  default or ambient global state.
- Each component instance owns disjoint state, checkpoints, artifacts,
  identity, Custody and effects unless an explicit shared-resource port exists.
- A pattern must work in at least two supported shapes and under applicable
  suspension, cancellation, retry and replay. Shape-specific semantics are not
  reusable semantics.
- The agentic example is a small conformance fixture for the generic boundary,
  not evidence that a nonexistent Megaplan pattern should be generalized.
- Registry status remains experimental. Megaplan parity plus first extraction
  is not the unrelated second-consumer proof required for stability.
- Megaplan retains one completion writer, one authoritative decoder, one
  acceptance transaction, the two distinct registries and their total mapping,
  and the exact Custody incident projection. The migration changes dependency
  direction and binding/lock only.
- C2's aggregation signatures and S2R's concrete primitive instances remain
  intact. Platform workflow-shape composition does not create another
  completion-disposition algebra, child mapping, evidence window, verifier, or
  waiver rule.

## Required work

1. Extract and package the four first-wave patterns against the S1 descriptors,
   S2B public experimental core, and S3 authoring tools. Every extracted
   durable workflow gets its own `.pype`; reusable steps live in `.py`, while
   truly private steps may remain file-local and unimportable. Remove reverse
   imports, hidden dependency lookup, mutable shared state and product-default
   precedence.
2. Make Megaplan import and bind the shared implementations. Preserve its exact
   accepted source/runtime topology, business/control results, terminal truth,
   effects, identities and normalized golden traces.
   Make Megaplan consume the already extracted
   `CompletionSpec -> CompletionBinding -> CompletionVerdict` implementation
   and its acceptance adapter as one receipt-bound dependency/lock change.
   This is not a semantic migration, a new enablement, or rebinding of an
   existing subject. Prove byte/semantic
   compatibility for S2R-era persisted records and absence of a second writer,
   decoder, divergence ledger, outcome registry, boundary mapping, evidence
   store, or projection.
3. Instantiate every pattern twice concurrently with intentionally different
   bindings. Attempt cross-read, cross-resume, cross-cancel and cross-reconcile
   mutations across all owned namespaces.
4. Recompose every pattern in at least two supported shapes. Cover nested,
   sequential, bounded loop, keyed fanout/fanin, suspension/cancellation and
   root hosting where each descriptor declares those capabilities.
5. Use the evaluator panel to prove all/any/quorum satisfaction/impossibility,
   qualifying/non-qualifying results, loser cancellation and late evidence.
   Use the bounded loop to prove every durable ledger edge and named exit. Use
   the human gate to prove all timeout generations and answer/timeout/cancel
   races. Use the effect-safe action to prove retry over accepted/ambiguous non-
   idempotent work and resource-specific settlement.
6. Exercise typed checkpointed reconfiguration and the small agentic fixture
   with closed outer results, declared route influence, per-inner-call WBC,
   Custody/effect identity and charge.
7. Extend the faithful local kit for each pattern: typed fakes, human fast-
   forward, boundary fault injection, lifecycle/namespace inspection, replay
   from recorded accepted outcomes, repeat and fork from fixture/recorded input/
   eligible checkpoint, and side-by-side source/agent/LLM/tool/effect/cost/log
   comparison.
8. Edit one implementation or binding for each first-wave pattern and prove
   immediate fresh preview/sandbox iteration without migration, while silent
   production resume, production effects/keys and namespace reuse fail.
9. Update conformance, traceability and proof-map rows with both Megaplan golden
   evidence and generic component evidence from checkout, wheel and installed
   execution.
10. Run the receipt-consuming Megaplan binding/lock migration with wrong-tree,
    pre-merge, stale, red, cross-incarnation, partial-update and replayed-
    receipt mutations. Before consumption the candidate is non-authoritative;
    after consumption exactly one binding/lock is authoritative.
11. Rerun the cumulative neutral-package/product-adapter import lint and exact
    inventory equality for completion writers, decoders, evaluators,
    disposition registries, primitive aggregation instances and acceptance
    transactions. The old package binding becomes inert for new admissions,
    while evidence required by retained runs remains content-addressed and
    reachable.

## Gates

### Semantic gate

- Megaplan consumes the shared implementation with unchanged normalized golden
  behavior and no compatibility carrier becoming route authority.
- Every first-wave pattern preserves its local contract across its declared
  shapes, including result classes, conditions, lifecycle, effects, resources,
  terminals and parent/child causality.
- Concurrent differently bound instances cannot observe or affect each other's
  durable state or authority/effect domains.

### Proof gate

- Per-pattern suites cover success, replay without repeated external/LLM/human
  work, human suspend/fast-forward including stale/duplicate/wrong capability,
  two concurrent instances, parent retry/new generation, every loop-ledger
  crash edge, join and late-child races, cancellation/deadline/budget at every
  lifecycle edge, unresolved expiry and reconciliation, resource invariants,
  raw trace multiplicity/partial order and route-inert payload mutations.
- Local and installed runs have equivalent normalized lifecycle/admission traces
  given identical recorded boundary outcomes, and inherited/S1 no-network
  latency/repeatability thresholds remain green.
- For every pattern, edited-code repeat/fork remains low-friction and fully
  queryable by exact experiment/component occurrence; silent resume, authority,
  effect and namespace leakage fail before action.

### Adoption gate

- Megaplan is a real consumer of the shared experimental implementations from a
  clean installation; there is no copied implementation or reverse import.
- The active Megaplan binding changed only through the S4 receipt-consuming
  migration after the merged candidate and golden proof were accepted.
- Each candidate has an updated classification and evidence record. A pattern
  unsupported by its tests remains experimental or product-specific rather than
  being generalized to make the gate green.

## Artifacts and S5 handoff

Produce the first-wave shared implementations and descriptors; Megaplan binding
and migration changes; per-pattern isolation/recomposition/local-kit fixtures;
golden and generic conformance receipts; updated DX results; and a content-
addressed S4 handoff listing retained, revised, rejected and still-experimental
abstractions. Include the exact public surfaces and novel shapes S5 must attack.

## Do not close this sprint if

- Megaplan behavior changes without an explicit accepted product decision;
- the candidate becomes authoritative before the exact accepted post-merge S4
  receipt is consumed, or old/new bindings can both admit new work;
- shared packages import/copy Megaplan or contain hidden product defaults;
- any duplicate/concurrent instance can collide across durable namespaces;
- any supported composition shape changes undeclared component semantics;
- local tests implement alternate runtime semantics or fake CAS is promoted to
  production evidence; or
- extraction requires a parser, identity/refactor rule, CLI/editor workaround,
  or generated-file edit outside the S2B/S3 surfaces; or
- first-consumer success is represented as stable/two-consumer proof.

## Non-goals

- Extracting every Megaplan phase or stabilizing compiler internals.
- Building the unrelated S5 consumer or certifying stable registry entries.
- Adding open streams, marketplace functionality, M11 replacements or arbitrary
  durable Python.
