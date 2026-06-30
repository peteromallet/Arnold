# Milestone 7 — Flip the default and clean up

## Outcome

Native execution becomes the default for new pipeline runs, the graph executor is kept as a read-only fallback for old plans, hand-built graph builders are deprecated and removed where safe, docs/skills are updated, and the derived graph is the only graph path.

## Scope (IN)

- Default flip:
  - Make native execution the default for new runs of all converted pipelines.
  - Keep per-pipeline and per-run escape hatches to the graph executor for debugging or emergency rollback.
  - Add envelope markers so new runs record `runtime: "native"` and old graph-born runs record `runtime: "graph"`.
- In-flight compatibility:
  - Graph-born plans (detected via `state.json.runtime_envelope.runtime == "graph"` or non-native cursor) resume with the legacy graph executor.
  - Native-born plans resume with the native runtime.
  - Provide a migration path or explicit cursor-upgrade command for graph-born plans that want to resume natively once it is proven safe.
- Deprecation and removal:
  - Mark hand-built graph builders as deprecated.
  - Remove graph-builder scaffolding that is no longer used by any converted pipeline.
  - Keep the graph executor itself as a read-only fallback until the deprecation window closes.
- Documentation and skills:
  - Update pipeline authoring docs to describe `@pipeline`, `@phase`, `@decision`, `run_subpipeline(...)`, and `parallel(...)`.
  - Update skills that define pipelines (e.g., `creative`, `doc`, `simplify_writing`) to use native authoring.
  - Update `arnold pipelines check` help and dashboard docs to reflect derived graphs.
- Final acceptance gate:
  - All converted pipelines pass parity tests in native-default mode.
  - Existing tests still pass.
  - A canary period is documented (e.g., one release cycle) before graph-builder removal is finalized.

## Scope (OUT)

- New pipeline features unrelated to the migration.
- Forced migration of graph-born in-flight plans; they may finish on the legacy executor.
- Changes to persistence formats.

## Locked decisions

- Native is the default only after all converted pipelines run natively with parity and in-flight compatibility is proven.
- The graph executor remains available as a read-only fallback for old plans for at least one deprecation window.
- Graph-builder removal is scoped to unused scaffolding; load-bearing graph types needed for the derived view are preserved.

## Open questions

- How long is the deprecation window before graph builders can be fully removed?
- What is the exact command or API for upgrading a graph-born cursor to native?
- Which docs/skills must be updated before the flip, and which can follow?
- What observability alerts are needed to detect native-runtime regressions after the flip?

## Constraints

- Must not lose in-flight plans.
- Must not break existing tests or `arnold pipelines check`.
- Must preserve the ability to roll back a pipeline to graph execution for a limited time.
- Must keep derived graph validation passing.

## Done criteria

- Native execution is the default for new runs of all converted pipelines.
- Graph-born in-flight plans resume on the graph executor; native-born plans resume on the native runtime.
- Hand-built graph builders are deprecated and unused scaffolding is removed.
- Docs and skills are updated to native authoring.
- All parity tests pass in native-default mode.
- All existing tests pass.
- A rollback procedure and deprecation window are documented.

## Touchpoints

- `arnold/pipeline/native/` (default flags)
- `arnold/pipeline/executor.py` (fallback behavior)
- `arnold/pipeline/builder.py` or graph-builder modules (deprecation/removal)
- `arnold/pipelines/*/pipeline.py` (default runtime wiring)
- `docs/arnold/pipelines/` (authoring docs)
- `.agents/skills/*/SKILL.md` (pipeline-native skills)
- `tests/arnold/pipeline/native/test_default_flip.py` (new)

## Anti-scope

- Do not force old graph-born plans onto native resume without a proven cursor-upgrade path.
- Do not remove the graph executor entirely until the deprecation window closes.
- Do not introduce new pipeline features.
