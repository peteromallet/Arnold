# Codex subagent brief: BoundaryTurn end-to-end epic shaping

Working directory: `/Users/peteromalley/Documents/Arnold`.

You are a Codex subagent asked to shape an end-to-end Megaplan epic. Do not edit
files. Read the relevant docs and return a concrete epic plan that another
agent can write into `.megaplan/initiatives/<slug>/`.

## Required inputs to read

- `docs/arnold/megaplan-boundary-turn-design.md`
- `docs/arnold/megaplan-boundary-turn-load-bearing-questions.md`
- `.megaplan/boundary-turn-lbq/results/_report.json`
- The individual `.megaplan/boundary-turn-lbq/results/*.txt` files as needed.
- `/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/arnold/pipelines/megaplan/data/_codex_skills/megaplan-prep/SKILL.md`
- Existing chain examples under `.megaplan/initiatives/*/chain.yaml`, only enough to match local format.

## Goal

Design the full epic that builds BoundaryTurn end-to-end, not just the first
JSON facade sprint. Use the `megaplan-prep` rubric explicitly:

- Size the work into sprint-sized megaplans, each roughly <= two weeks of human
  work.
- Give each milestone a self-contained brief title, outcome, scope, locked
  decisions, open questions, constraints, done criteria, touchpoints, and
  anti-scope.
- Score overall plan difficulty per milestone and select profile/robustness/
  depth/vendor.
- Explain where prep is needed and provide `prep_direction` text.
- Preserve the principle that BoundaryTurn is a promotion-time abstraction, not
  a worker parser, route engine, or phase-policy replacement.

## Required epic coverage

The epic must carry the design from first foundation to end-state:

1. Conservative JSON facade over existing scratch behavior.
2. Ordered promotion/checkpoint/receipt semantics.
3. Plan/revise structured-payload boundary without metadata loss.
4. Gate reprompt semantics and route-policy preservation.
5. Finalize multi-artifact promotion, baseline side-effect recording, and
   finalize-to-revise route.
6. Execute child batch turns plus aggregate reducer, side-effect evidence, resume
   mapping, tier routing, and `finalize.json` child updates.
7. Review single-worker plus parallel/extreme child reducer, infra failure,
   transition-policy denial, rework caps, flag provenance, and conditional
   `review.json` re-promotion.
8. Tiebreaker/subpipeline child turns plus reducer, `gate.json` evidence refs,
   versioned iterations, audits, and flag-registry mutation checkpoints.
9. General Arnold recipe/protocols so non-Megaplan pipeline authors can adopt
   the draft/capture/validate/promote pattern without importing Megaplan
   registries.
10. Final conformance/docs/acceptance gate proving no stage functionality was
   lost and the recipe is reusable.

## Output format

Return only Markdown, under 4500 words, with:

1. `Epic Recommendation`: slug, one-paragraph north star, whether this should be
   an epic and why.
2. `Milestones`: a table with label, title, profile, robustness, depth, vendor,
   prep yes/no, dependencies, and one-sentence purpose.
3. `Milestone Briefs`: one subsection per milestone with self-contained brief
   content. These should be concrete enough to paste into `.md` brief files.
4. `Chain YAML Sketch`: valid-looking YAML matching local examples.
5. `Risk Notes`: the top risks that should be called out in the epic.

Be opinionated. Avoid hedging. If you split differently from the numbered
coverage above, explain why in the milestone purpose.
