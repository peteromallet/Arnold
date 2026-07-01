# Codex subagent brief: BoundaryTurn overlap with native epics

Working directory: `/Users/peteromalley/Documents/Arnold`.

You are a Codex subagent doing an independent architecture/program-shaping
sense-check. Do not edit files. Read the listed files and return a direct
recommendation.

## Question

Can the BoundaryTurn end-to-end epic be done at the same time as these existing
native follow-up epics if we are willing to spend some time merging the plans
together?

- `.megaplan/initiatives/native-python-pipelines-completion/chain.yaml`
- `.megaplan/initiatives/native-composition-followup/chain.yaml`
- `.megaplan/initiatives/native-platform-followup/chain.yaml`

Also read the current BoundaryTurn epic:

- `.megaplan/initiatives/boundary-turn-end-to-end/chain.yaml`
- `.megaplan/initiatives/boundary-turn-end-to-end/NORTHSTAR.md`
- `.megaplan/initiatives/boundary-turn-end-to-end/briefs/m1-boundary-foundation.md`
- `.megaplan/initiatives/boundary-turn-end-to-end/briefs/m2-primary-stage-boundaries.md`
- `.megaplan/initiatives/boundary-turn-end-to-end/briefs/m3-reducer-stage-boundaries.md`
- `.megaplan/initiatives/boundary-turn-end-to-end/briefs/m4-recipe-conformance.md`

And the design inputs:

- `docs/arnold/megaplan-boundary-turn-design.md`
- `docs/arnold/megaplan-boundary-turn-load-bearing-questions.md`

## What to decide

Give an opinionated answer on whether BoundaryTurn should:

1. remain a separate epic with dependency edges to those chains;
2. be merged into `native-python-pipelines-completion`;
3. be merged into `native-composition-followup`;
4. be merged into `native-platform-followup`;
5. be split across them.

Assume the team is willing to spend some time merging plans and resolving brief
overlap, but does not want accidental scope bloat or months of unnecessary
sequencing.

## Evaluation criteria

- Does BoundaryTurn naturally depend on native Python completion?
- Does it naturally depend on composition semantics?
- Does it naturally depend on platform side-effect/idempotency/checkpoint work?
- Which BoundaryTurn milestones can safely run in parallel with which existing
  milestones?
- Which milestones would create merge conflicts or conceptual drift if run in
  parallel?
- What is the shortest robust program shape?
- What should the chain dependency/precondition structure be?

## Output format

Return only Markdown, under 2200 words:

1. `Verdict`: one paragraph.
2. `Recommended Shape`: concrete chain/milestone placement.
3. `Parallelization Map`: what can run together, what must wait.
4. `Merge Risks`: top risks and mitigations.
5. `Proposed Edits`: specific changes to the BoundaryTurn chain or existing
   chains, if any.

Be blunt. If the current 4-milestone BoundaryTurn epic is still too big, say so.
If merging into the native epics is worse than keeping it separate, say so.
