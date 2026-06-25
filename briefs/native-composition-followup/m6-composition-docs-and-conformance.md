# M6 - Composition Docs And Conformance

## Objective

Turn the implemented composition model into the documented and tested Arnold
authoring contract. Docs, scaffolds, and conformance suites should teach the
actual end state for this epic: stable invocable steps/workflows, declared
inputs/outputs, workflow-in-workflow composition, loops over recorded state,
static graph queries, tree traces, per-attempt audit skeletons, and path resume.

## Files To Change And Instructions

- `docs/arnold/authoring-guide.md`
  Document compositional workflows, stable IDs, declared interfaces, nested
  invocation, loops, and the routing boundary.
- `docs/arnold/package-authoring-contract.md`
  Update package-level expectations for compositional workflows and stable
  workflow identity.
- `docs/arnold/workflow-authoring.md`
  Add examples for a single workflow, a nested workflow, a loop over recorded
  state, repeated child workflow use, and a path-resume scenario.
- `docs/arnold/native-composition-contract.md`
  Ensure the final implemented contract matches the M0 contract, or update the
  contract with deliberate decisions made during implementation.
- `arnold/pipelines/_authoring.py`
  Ensure generated scaffolds use the compositional format and no shim/fallback
  package pattern. The scaffold should generate a small compositional example,
  not only a flat step chain.
- `arnold/pipelines/_template/`
  Update template code and skill instructions to the compositional contract.
- `tests/arnold/pipeline/native/`
  Add a conformance suite for composition: nested invocation, tree trace,
  static graph queries, per-attempt audit skeleton, composite resume, routing
  validator, loop iteration paths, depth-3 nesting, and repeated child workflow
  use.
- `tests/docs/`
  Keep examples and generated docs synchronized with the implemented API.

## Verifiable Completion Criterion

- A new author following docs/scaffolds writes the compositional format by
  default.
- Documentation includes Megaplan as the real-world compositional reference.
- Conformance tests lock stable unit IDs, declared interfaces, nested
  invocation, loops, static graph queries, tree traces, path addressing,
  per-attempt audit skeletons, and composite resume as public behavior.
- Conformance includes a replay-consistency gate: run an equivalent nested
  workflow uninterrupted and with interruption/resume, then assert the final
  state and committed side-effect record are equivalent.
- No doc or scaffold teaches shims, graph fallback builders, or compatibility
  wrapper modules as an authoring pattern.
- Docs are explicit that this epic delivers composition on the existing native
  substrate. Worktree reconcile, credential brokerage, DBOS/Postgres fleet
  durability, full pack/versioning product, and production supervision are
  covered by the platform follow-up epic, not by this composition epic.

## Risks And Blockers

- Docs can outrun implementation. Every example must be backed by a test or a
  generated artifact check.
- The Megaplan example should be explanatory without exposing unnecessary
  internal hook machinery as part of the normal authoring surface.
- If docs hide the deferred platform boundaries, users will mistake the local
  composition system for the full production operating model described in the
  design doc.

## Dependencies

- Depends on M5.
