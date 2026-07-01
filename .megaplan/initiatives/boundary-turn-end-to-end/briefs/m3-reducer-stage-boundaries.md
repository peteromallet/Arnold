# M3: Reducer Stage Boundaries

## Outcome

Implement BoundaryTurn child/reducer semantics for the stages that cannot be
represented as single draft files: execute, parallel/extreme review, and
tiebreaker subpipelines.

## Scope

IN:

- Execute child turns for `execution_batch_N.json` plus an aggregate reducer for
  `execution.json`.
- Execute side-effect evidence for target-repo mutations, approval/preflight,
  timeout recovery, quality gates, blocked-task reset, prerequisite blocks,
  audit/trace output, skipped-review stubs, tier routing, active-step session
  keys, stable batch numbering, and `finalize.json` child updates.
- Review single-worker scratch path plus parallel/extreme child reducer.
- Review infra failure detection, empty-approved backfill, verdict merge into
  finalize projection, maker stop, transition-policy denial, rework caps,
  conditional `review.json` re-promotion, receipts, flag provenance, and
  `final.md` rewrites.
- Tiebreaker researcher/challenger child turns, versioned iterations,
  `gate.json` evidence refs, `tiebreaker_decisions.json`, audits, flag-registry
  mutation checkpoints, and human/replan/revise route choices.

OUT:

- Generic Arnold public recipe.
- New execution/review/tiebreaker product behavior.
- Target-repository rollback.

## Locked Decisions

- Execute cannot be atomic; it records side-effect evidence and supports resume.
- Child turns never write parent artifacts or advance parent state directly.
- Parent state advances only during reducer promotion.
- Review outcome policy and transition-policy denial stay outside BoundaryTurn.
- Reducers validate child evidence before canonical promotion or flag mutation.

## Open Questions

- How much execute/review audit output should be `ExternalEffectRef` versus
  observability event?
- Should tiebreaker reducer reprompts reuse one draft path or versioned attempt
  paths?

## Constraints

- Batch numbering must be stable across resume.
- Parallel review must preserve concerned task IDs, deterministic-check
  evidence, flag IDs, and infra-failure signals.
- Tiebreaker must reject direct child writes to canonical parent artifacts.

## Done Criteria

- Execute tests cover partial resume, stable task-slot mapping, side-effect
  evidence, child `finalize.json` updates, reducer validation, tier routing, and
  timeout/blocked paths.
- Review tests cover simple approve, rework cap, infra failure, parallel
  reducer, transition denial, conditional re-promotion, and flag provenance.
- Tiebreaker tests cover missing evidence, direct canonical write rejection,
  versioned iterations, audit recording, checkpointed flag mutation, and route
  selection.

## Touchpoints

- Execute handler and batch artifacts
- Quality gates, audit/trace writers, resume state
- Review handler, parallel review orchestration, transition policy, final
  projection, flag registry
- Tiebreaker orchestration and flag registry

## Anti-Scope

- Do not make BoundaryTurn the route engine.
- Do not hide execute/review/tiebreaker special cases behind generic code.

## Run Notes

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because reducer
stages have real external side effects, fanout evidence, resume semantics, and
state mutation ordering risks.

Use `partnered-5/thorough/high @codex +prep`.
