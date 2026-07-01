# M1: Boundary Foundation

## Outcome

Build the reusable BoundaryTurn foundation without changing Megaplan behavior:
a JSON scratch facade over existing structured output plus ordered promotion
checkpoints for canonical artifacts, state, history, receipts, and diagnostics.

## Scope

IN:

- `BoundaryTurn`, `BoundarySpec`, capture diagnostics, fallback policies, and
  `PromotionResult`.
- A thin facade over `handlers/structured_output.py`.
- `legacy_recovery` as the default policy for existing JSON phases.
- Ordered promotion checkpoints with idempotent resume.
- Parity tests for wrong path, direct canonical path, missing draft, unmodified
  draft, modified-invalid draft, inline fallback, unknown keys, and receipt
  deduplication.
- Migrate one low-risk JSON phase and one higher-value JSON phase through the
  facade.

OUT:

- Plan/revise migration.
- Execute/review/tiebreaker reducers.
- Generic Arnold public protocols.
- Any attempt to make target-repository mutations transactional.

## Locked Decisions

- BoundaryTurn is a promotion-time abstraction, not a worker parser.
- Worker/model-seam recovery runs before boundary classification in
  `legacy_recovery`.
- Current artifact names do not change.
- `workflow_transition` is a proposal or record, not an authoritative route.
- Missing and unmodified drafts remain distinct diagnostics.

## Open Questions

- Should direct canonical writes hard-fail or be diagnostics in legacy mode?
- Should checkpoint state live in `PlanRepository`, a new boundary module, or
  plan-dir checkpoint artifacts?

## Constraints

- Preserve DeepSeek/Kimi recovery, tool-markup extraction, malformed-inline /
  valid-file recovery, phase normalizers, and current `promote_scratch`
  behavior.
- Make the facade incremental; handlers must be migratable one at a time.

## Done Criteria

- Existing structured-output tests pass.
- New BoundaryTurn tests prove parity and fail-closed promotion behavior.
- State cannot advance without required canonical artifacts.
- Interrupted promotion resumes or fails closed without duplicate receipts.
- The milestone leaves clear instructions for migrating additional phases.

## Touchpoints

- `arnold_pipelines/megaplan/handlers/structured_output.py`
- `arnold_pipelines/megaplan/template_registry.py`
- JSON phase handlers/tests
- Plan repository/artifact writers
- State/history/receipt code
- `arnold_pipelines/megaplan/workers/hermes.py`
- `arnold_pipelines/megaplan/model_seam.py`

## Anti-Scope

- Do not move gate/review routing policy into BoundaryTurn.
- Do not rewrite provider parsing or model-seam recovery.
- Do not change canonical artifact names.

## Run Notes

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because this is
the core boundary placement and a bad foundation can silently weaken recovery,
resume, or artifact invariants.

Use `partnered-5/thorough/high @codex +prep`.
