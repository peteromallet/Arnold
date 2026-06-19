# Milestone 6 — Remaining pipeline migrations

## Outcome

All remaining smaller Megaplan/A Arnold pipelines run natively behind the feature flag with per-pipeline parity tests, and the native runtime is ready for the default-flip milestone.

## Scope (IN)

- Inventory all remaining smaller pipelines that use the graph executor today (e.g., `creative`, `doc`, `simplify_writing`, `live_supervisor`, `jokes`, and any others discovered during the epic).
- Convert each to a native `@pipeline` function:
  - Preserve handlers and contracts.
  - Use `@phase` / `@decision` decorators with explicit ports.
  - Use `run_subpipeline(...)` and `parallel(...)` where the original graph uses subloops or parallel stages.
  - Use human-gate primitives where needed.
- For each pipeline:
  - Capture a graph-executor golden trace.
  - Assert native parity for stage sequence, `state.json`, `events.ndjson` fold, `resume_cursor.json`, artifacts, and topology hash.
  - Prove native checkpoint resume.
- Update derived `build_pipeline()` exports so `arnold pipelines check` sees native-derived graphs.
- Consolidate common conversion patterns into a short runbook or template so future pipelines can be authored natively from scratch.

## Scope (OUT)

- Flipping the default execution mode to native.
- Removing the graph executor or graph builders.
- Large new runtime features not already provided by Milestones 3–5.

## Locked decisions

- Every converted pipeline must pass parity tests before the milestone is considered done.
- Pipelines are converted one by one; no bulk migration without per-pipeline acceptance.
- The graph executor remains the default for production runs during this milestone.

## Open questions

- What is the exact inventory of remaining pipelines, and which ones are actively used vs. dormant?
- Are there any pipelines that rely on graph-executor-specific hooks that have no native equivalent yet?
- Which pipelines can share a common native skeleton or helper module?
- Should dormant pipelines be migrated or deprecated instead?

## Constraints

- Must not break existing tests or in-flight plans.
- Must run behind the existing feature flag.
- Must produce byte-compatible persistence shapes per converted pipeline.
- Must not change the default execution mode.

## Done criteria

- Every actively used remaining pipeline has a native implementation.
- Each converted pipeline has passing parity tests and a resume test.
- Derived graphs for all converted pipelines pass validation.
- All existing tests still pass.
- A conversion runbook or template is committed.
- Milestone 7 handoff confirms no remaining blockers for flipping the default and lists in-flight compatibility criteria.

## Touchpoints

- `arnold/pipelines/creative/`
- `arnold/pipelines/doc/`
- `arnold/pipelines/simplify_writing/`
- `arnold/pipelines/live_supervisor/`
- `arnold/pipelines/jokes/`
- Any other smaller pipeline directories discovered during inventory.
- `tests/arnold/pipeline/native/parity_corpus/` (extend with new golden traces)
- `docs/arnold/pipelines/native-conversion-runbook.md` (new)

## Anti-scope

- Do not flip the default execution mode.
- Do not remove the graph executor.
- Do not start new feature work unrelated to migration.
