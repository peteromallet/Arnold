# M2: Primary Stage Boundaries

## Outcome

Migrate the primary non-reducer stages onto BoundaryTurn while preserving their
stage-specific policy: plan/revise structured payloads, gate attempts, and
finalize multi-artifact promotion.

## Scope

IN:

- Plan/revise as structured-payload boundaries preserving `plan_vN.md` and
  `plan_vN.meta.json`.
- Plan/revise metadata parity: questions, assumptions, success criteria,
  imported decision criteria, changed surfaces, test blast radius, note
  receipts, cache-hit guards, carried blast radius, and flag updates.
- Gate BoundaryTurns for attempts/reprompts, with canonical gate artifacts
  promoted once after final gate policy resolution.
- Finalize multi-artifact promotion: `finalize.json`, `final.md`,
  `contract.json`, `user_actions.md`, `finalize_snapshot.json`, capability
  claims, baseline cache, validation injection, and finalize-to-revise route.

OUT:

- Markdown-only plan/revise drafts.
- Execute child batches.
- Review parallel reducers.
- Tiebreaker child turns.

## Locked Decisions

- Plan/revise do not become Markdown-only drafts in this milestone.
- `_apply_gate_outcome`, transition policy, and auto-driver route derivation
  stay outside BoundaryTurn.
- Intermediate gate attempts validate but do not promote canonical gate
  artifacts.
- Finalize model drafts do not own harness-computed `validation`.
- Baseline capture is recorded as a side effect, not treated as rollback-safe.

## Open Questions

- Should plan/revise start as `inline_only` structured boundaries or stable
  draft paths?
- What side-effect schema should baseline capture use?

## Constraints

- Preserve gate blocked/gated distinctions, debt writes, flag events, invalid
  recommendation fallback, no-progress termination, and tiebreaker validation.
- Preserve finalize baseline-selection failure routing to revise via
  gate/feedback artifacts.

## Done Criteria

- Golden tests prove plan/revise Markdown plus metadata parity.
- Gate tests prove validate-without-promote reprompts and one final canonical
  promotion.
- Finalize tests prove all canonical artifacts, baseline cache behavior,
  harness-computed validation, and finalize-to-revise artifacts.
- No stage loses existing route or state behavior.

## Touchpoints

- Plan/revise handlers and prompt builders
- Gate handler, route policy, flag/debt registries
- Finalize handler, baseline/cache code, contract/user-action writers
- BoundaryTurn foundation from M1

## Anti-Scope

- Do not implement reducer-style execute/review/tiebreaker.
- Do not flatten stage policies into BoundaryTurn.

## Run Notes

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because this
milestone touches the main planning loop, loop-control gate, and user-facing
finalization contract.

Use `partnered-5/thorough/high @codex +prep`.
