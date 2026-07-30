# C1 — Completion Contract, Identity, and Shadow Kernel

## Objective

Insert the first half of the completion kernel directly into Native Parity
after S2F and before S2R. Consume S2F's accepted `.pype` authored,
component, graph, source-map, and durable-boundary call-site identity
templates; define the neutral completion contract and its stable identities;
and run it only in shadow.

C1 cannot accept a terminal result, alter admission, enable a completion gate,
or supply Run Authority, Custody, WBC, effect, storage, routing, or acceptance
authority. S2R GO-0 is the sole future live-enablement receipt.

Normative retained design and exhaustive redistribution map:

- `../../standardized-completion-specifications/decisions/standardized-completion-spec-proposal.md`
- `../../standardized-completion-specifications/SUPERSESSION_CROSSWALK.yaml`
- `../../standardized-completion-specifications/briefs/m1.md`

## Required inputs

- the exact accepted S2F GO-FORMAT receipt and `.pype` identity/compiler
  handoff;
- the accepted Custody M11 manifest and exact
  `bounded-incident-projection-handoff.json`;
- the captured M10/M11 false-done and unroutable-`REVIEW` corpus; and
- the existing `CompletionVerdict`, evidence, WBC, Run Authority, Custody,
  admission, and acceptance carriers that must be extended rather than
  duplicated.

## Required work

1. Create the experimental neutral package/import boundary at
   `arnold/workflow/completion/`. It may import product-neutral Arnold
   contracts but must not import Megaplan or product orchestration. Put
   deterministic Megaplan adapters under `arnold_pipelines/megaplan/`.
2. Add cumulative import lint and negative fixtures. The same lint must be
   reconsumed by S7 and Platform S4/S5; copied adapters or an Arnold-to-
   Megaplan reverse dependency fail.
3. Define versioned schemas and canonical serialization/hash versions for
   `CompletionSpec`, `CompletionBinding`, the evolved `CompletionVerdict`, and
   acceptance references. C1 owns the schema identities and canonical
   serialization foundation; C2 completes binding/evaluation fields.
4. Define stable `obligation_id`, canonical `spec_hash`, tombstoning, and exact
   reuse identity. A human-readable ID or mutable semantic-version counter
   cannot authorize reuse.
5. Implement the mechanical durable-subject versus pure-helper predicate.
   Workflows, durable steps, dynamic tasks, human boundaries, registered
   effects, checkpoints/retries, authority/custody subjects, and artifacts
   crossing durable boundaries require templates. Pure helpers receive no
   independent contract and their transitive behavior stays in the containing
   executable digest.
6. Consume S2F's authored/component/graph identities and source-stable
   durable-boundary call-site templates. Generate only the templates knowable
   at S2F. Do not manufacture runtime human, fanout-child, invocation, or
   rework occurrences: finalization/admission and S2R instantiate those
   beneath the templates, while S5 admits product-created reopened/new work.
7. Define one versioned completion candidate-outcome registry, including
   non-success and nonterminal candidates. It is distinct from the platform
   enforcement-disposition registry
   `docs/arnold/workflow-execution-mode-dispositions.yaml`. Define the schema
   for their total generated boundary mapping; never merge them into one enum
   or allow an unversioned local mapping.
8. Add `superseded_by_named_exit` as a typed lifecycle/control terminal. It is
   not success, waiver, cancellation, arbitrary not-applicable, or a completion
   candidate shortcut. Bind it to an accepted named exit, target loop, source
   declaration, every intervening binding, and the ordered unwind set.
9. Generate shadow specs for representative workflows, durable steps, dynamic
   task templates, human boundaries, effects, and rework declarations without
   contracting pure helpers.
10. Execute the captured M10/M11 fixture. Legacy `done` without an accepted
    attempt must remain incomplete; `REVIEW` must never be executable; a new
    review finding must be classified as proposed new admitted work; accepted
    evidence for unrelated subjects must remain intact.
11. Record every parity difference as one stable occurrence in a
    content-addressed append-only divergence ledger. Each entry names old-
    system defect, kernel/generator defect, or reviewed intentional difference,
    its blocking status, evidence, disposition, supersession lineage, and the
    ledger version/hash. Narrowing evidence updates the same occurrence.
12. Emit `completion-kernel-c1-manifest.json`,
    `completion-divergence-ledger.json`, schema/import-lint receipts, fixture
    receipts, and the C1 proof map. C2 and every later Native gate must consume
    the exact current ledger hash and reject unresolved, stale, omitted, or
    silently replaced blocking entries.

## C1 gate

- neutral package import direction is mechanically clean;
- schema and serialization round-trips are deterministic across checkout,
  wheel/sdist, and cloud-compatible installed execution;
- durable/helper lint has positive and hidden-effect negatives;
- authored templates use S2F identities and do not preallocate runtime
  occurrences;
- candidate outcomes and platform enforcement dispositions remain distinct,
  with one total generated boundary-mapping schema;
- named-exit supersession cannot be laundered into success or erase an
  intervening binding;
- false-done and executable-`REVIEW` claims fail under shadow evaluation;
- every shadow divergence has one stable ledger occurrence and explicit
  disposition; and
- existing authoritative behavior is unchanged.

## Do not close if

- the neutral package imports Megaplan, a second verdict/evidence/receipt/
  waiver/store/acceptance system appears, or an adapter becomes semantic
  authority;
- S2F is claimed to own runtime human, dynamic-child, or rework occurrence
  identities;
- the two disposition domains are collapsed or mapped through an incomplete
  hand-maintained table;
- a parity count replaces individually dispositioned ledger entries;
- a status, Markdown view, projection, shadow verdict, or C1 receipt affects
  admission or acceptance; or
- the C1 handoff omits the exact current divergence-ledger hash.
