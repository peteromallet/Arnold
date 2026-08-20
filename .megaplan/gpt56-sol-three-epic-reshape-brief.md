# Task: reshape three initiative epics to implement the reviewed sequencing

Work in `/Users/peteromalley/Documents/Arnold`.

Use the planning/oracle document:

- `docs/arnold/completion-spec-sequencing-and-ownership.md`

Reshape these three initiative epics:

- `.megaplan/initiatives/megaplan-native-parity-corrective/`
- `.megaplan/initiatives/standardized-completion-specifications/`
- `.megaplan/initiatives/native-workflow-platformization/`

Goal: make the actual epic manifests, north stars, README sequencing, sprint briefs,
gates, ownership boundaries, and supersession/dependency records match the complete
sequencing logic and oracle amendments in the planning document.

This is an editing task, not just a review. Carefully inspect every file in all three
initiatives before changing anything. Preserve all still-valid planned work and proof
requirements; relocate or reframe work rather than silently dropping it. Do not launch
any epic or plan. Do not modify the currently running M11 cloud plan. Do not commit,
push, or create a PR.

Required architecture:

1. Native Parity executes S1 then S2F.
2. The Completion initiative is inserted in the same program frontier:
   - M1 owns neutral spec/identity semantics and shadow generation.
   - M2 owns binding/evaluator schema and only the *aggregation signatures/algebra*.
   - M2 remains shadow-only; it must not activate live enforcement.
3. Native Parity S2R owns concrete aggregation instances for durable primitives and
   is the first live enforcement point.
4. Native Parity S3A..S4 consume kernel receipts; S5A/S5B perform shadow slice/live
   cutover; S6/S7 prove inventory equality and eliminate competing writers.
5. Platformization follows Native Parity and consumes the landed kernel; it does not
   reinvent completion semantics.

Oracle amendments that must become explicit, executable gates:

- mechanically checkable durable-subject predicate plus static lint;
- candidate outcome evaluated before its applicable obligations, with typed proof
  requirements for blocked/waived outcomes and quarantine nonterminal unless an
  admitted terminal policy explicitly allows otherwise;
- `(spec_hash, obligation_id)` executable identity and stable semantic obligation IDs;
- total child-disposition mapping, waiver-taint propagation, multiplicity and
  no-double-counting rules;
- presence versus absence verifiers and complete-capture requirements;
- normative evidence window tuple;
- verifier independence by producer identity and trust class;
- one canonical disposition registry; all product/platform registries are strict
  tested projections;
- neutral kernel types import neither Megaplan nor Arnold product policy; adapters
  live product-side, enforced by import lint;
- human-gate and rework subject identities must exist by S2F or use an explicitly
  gated deferred-template mechanism;
- Q49/cursor-bounded high-volume replay has an owner and an enforceable load gate
  before S5B;
- restore drill for store-incarnation invalidation;
- parity divergences reuse the stable finding/occurrence system;
- generated Markdown reports are disposable projections, with a deletion fixture;
- persisted binding schema is internally versioned from M1 even though public API
  stability waits until Platform S6;
- M11/live evidence dependencies cannot be superseded in a way that orphans evidence;
- at least one reproduced false-pass golden exemplar gates entry past shadow work;
- reopen is a new admission referencing the prior subject, not mutation/rebinding.

Also answer the deeper design constraint: creating a new durable step/workflow should
be elegant and low-boilerplate. The author declares intent/obligations using the
canonical authoring surface; deterministic tooling generates/pins bindings and
human-readable completion worksheets/reports as non-authoritative projections;
admission/lints reject omissions. Pure helpers must require no completion contract.

Before editing, make a concise inventory mapping every existing milestone and proof
artifact to retain/move/merge/supersede. Then edit all affected files consistently.
After editing:

- run every initiative validation/check command documented by these initiatives;
- search for stale milestone names and contradictory ordering;
- produce a concise final report listing files changed, preservation decisions,
  validation results, and any unresolved empirical dependency that cannot be settled
  from the repo.

Take a position and finish the edits. Do not merely recommend changes.
