# Native Pipeline Conversion Runbook

This runbook captures the M7 conversion pattern. Native authoring is the
default for converted Arnold pipelines; graph execution remains available as a
compatibility fallback for graph-only pipelines and graph-born in-flight plans.

## Runtime Selection

- Fresh runs of converted/native-capable pipelines default to the native
  runtime and persist explicit ownership in `state.json`:
  `runtime_envelope.runtime` and `meta.executor`.
- Fresh runs can opt into the compatibility path with `--runtime graph`.
- Graph-only pipelines remain graph-default until they have a real native
  bundle, projection, or runner covered by parity tests.
- Existing graph-born plans resume on the graph executor. They are not upgraded
  automatically.
- Native-born cursors resume on native. Corrupt native cursors fail closed
  instead of falling back to graph.

To inspect or migrate a graph-born cursor explicitly:

```bash
arnold pipelines upgrade-cursor <plan-dir>
arnold pipelines upgrade-cursor <plan-dir> --write
```

The command is dry-run by default. Write mode first preserves the original
`resume_cursor.json` as a graph backup, then writes the native cursor through
`persist_native_cursor(...)`. Ambiguous graph-stage to native-reentry mappings
fail with a diagnostic and do not mutate the plan.

## Accepted Pattern

1. Define the workflow with native declarations: `@pipeline`, `@phase`, and
   `@decision`.
2. Use `parallel(...)` for fixed branch sets and `native_panel(...)` for fixed
   reviewer panels.
3. Use `run_subpipeline(...)` when a phase must call a child pipeline and keep
   the parent/child resume contract explicit.
4. Compile with `compile_pipeline(...)` and derive the validation graph with
   `project_graph(...)`.
5. Keep `build_pipeline()` as the graph projection entrypoint so discovery,
   `arnold pipelines check`, and existing graph fallback can validate the same
   public topology.
6. Keep legacy graph builders only as parity baselines or as the fallback path
   for old plans during the deprecation window.

Native phase wrappers should delegate to existing production logic where that
logic already owns prompts, artifacts, state patches, profile handling, or
resume semantics. Do not fork business logic just to make the native declaration
look small.

## Parity Tests

For each converted pipeline, add or maintain focused parity coverage for:

- public stage sequence and topology hash;
- normalized final state and event fold;
- artifact inventory and content hashes with only named volatile fields masked;
- native checkpoint/resume at a meaningful boundary;
- graph fallback through `--runtime graph` or a graph-born cursor;
- fresh native-default routing and persisted runtime markers.

Run whole test files or modules, not individual test functions. Existing
baseline failures are not part of conversion work; the harness-owned regression
run remains authoritative.

## Dynamic Fanout And Panels

Native `parallel([...])` supports literal branch lists. `native_panel(...)` is a
thin native wrapper around `parallel(...)` that prefixes reviewer outputs by
reviewer id.

Runtime-sized dynamic fanout, profile-driven panel width, or graph helpers that
choose branch count from state should stay inside a delegating `@phase` until a
separate compiler/runtime change covers that behavior. Literal fixed panels can
use `native_panel(...)` directly.

## Checklist

- `build_pipeline()` returns the validated native projection for converted
  pipelines.
- Fresh converted runs default native and persist `runtime_envelope.runtime` plus
  `meta.executor`.
- `--runtime graph` still works as the compatibility fallback.
- Graph-born cursors resume on graph unless `upgrade-cursor --write` validates
  an exact native reentry mapping.
- Graph fallback/parity code is retained intentionally through the deprecation
  window.
- Docs, pipeline skills, and scaffolds present native declarations as the
  primary authoring path.
