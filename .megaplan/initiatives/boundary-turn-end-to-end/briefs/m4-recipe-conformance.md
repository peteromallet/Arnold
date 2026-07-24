# M4: Recipe And Conformance

## Outcome

Turn BoundaryTurn from a Megaplan implementation detail into a reusable Arnold
recipe, then prove no Megaplan stage functionality was lost.

## Scope

IN:

- Generic Arnold-level `BoundarySpec`/validator/promoter protocols or equivalent
  mechanical surface.
- Draft-kind adapters and canonical target declarations that do not depend on
  Megaplan artifact names.
- Runtime event/journal mapping for artifact deltas, state deltas,
  observability events, receipts, and route proposals.
- A small non-Megaplan example using Markdown draft -> validate -> promote.
- Stage preservation matrix covering every Megaplan stage.
- Conformance tests for wrong-path, invalid, unmodified, direct canonical,
  resume, side-effect evidence, reducers, and non-Megaplan clean import.
- Documentation for future pipeline authors.

OUT:

- New phase migrations.
- Reopening architecture settled in M1-M3.
- Migrating unrelated pipelines beyond the proof example.

## Locked Decisions

- The reusable recipe standardizes mechanics, not stage meaning.
- Non-Megaplan adoption must not import Megaplan registries, state classes, or
  artifact names.
- This milestone is an acceptance gate; blockers are regressions against prior
  milestones, not invitations to redesign.

## Open Questions

- Final public module path/name for the neutral protocols.
- How much of the recipe should be public API versus internal Arnold runtime
  helper in this epic.

## Constraints

- The conformance gate must run on the integrated branch.
- Docs must identify stages intentionally left policy-owned.
- The example must prove the recipe is not Megaplan-shaped.

## Done Criteria

- Full test suite plus BoundaryTurn conformance suite passes.
- Stage preservation matrix shows prep, plan, revise, critique,
  critique_evaluator, gate, finalize, execute, review, feedback, and tiebreaker
  behavior preserved or explicitly out of scope.
- A non-Megaplan pipeline uses the draft/capture/validate/promote pattern
  without importing Megaplan.
- Docs provide a standardized recipe others can follow.
- The original design docs are updated to match the implemented end state.

## Touchpoints

- Neutral Arnold runtime/protocol modules
- Megaplan BoundaryTurn adapters
- Example pipeline
- Tests and conformance scripts
- `docs/arnold/megaplan-boundary-turn-design.md`
- `docs/arnold/megaplan-boundary-turn-load-bearing-questions.md`

## Anti-Scope

- Do not add unrelated public API.
- Do not convert additional pipelines beyond the proof example.

## Run Notes

Overall plan difficulty: 4/5; selected profile: `partnered-4`; because the
architecture should be settled by this point, but generic public shape and
conformance still need strong planning.

Use `partnered-4/thorough/medium @codex +prep`.
