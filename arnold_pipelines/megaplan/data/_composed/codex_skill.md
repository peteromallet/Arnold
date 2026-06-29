---
name: workflow-codex
description: Workflow-only composed skill for Codex.
---

# workflow-codex

This composed rule is the workflow-only successor to the legacy Megaplan skill bundles.  It references only ``arnold.workflow`` and the shipped pipeline registry.

## Launcher

Use the ``arnold`` console script installed by the wheel:

```bash
arnold workflow --help
arnold workflow check --module <package.module>:build_pipeline
```

## Shipped pipelines

- `evidence_pack.verifier` -> `arnold workflow check --module arnold_pipelines.evidence_pack:build_pipeline`
- `megaplan.core` -> `arnold workflow check --module arnold_pipelines.megaplan:build_pipeline`
- `megaplan.creative` -> `arnold workflow check --module arnold_pipelines.megaplan.pipelines.creative:build_pipeline`
- `megaplan.doc` -> `arnold workflow check --module arnold_pipelines.megaplan.pipelines.doc:build_pipeline`
- `megaplan.jokes` -> `arnold workflow check --module arnold_pipelines.megaplan.pipelines.jokes:build_pipeline`
- `megaplan.live_supervisor` -> `arnold workflow check --module arnold_pipelines.megaplan.pipelines.live_supervisor:build_pipeline`
- `megaplan.planning` -> `arnold workflow check --module arnold_pipelines.megaplan.pipelines.planning:build_pipeline`
- `megaplan.select_tournament` -> `arnold workflow check --module arnold_pipelines.megaplan.pipelines.select_tournament:build_pipeline`
- `megaplan.writing_panel_strict` -> `arnold workflow check --module arnold_pipelines.megaplan.pipelines.writing_panel_strict:build_pipeline`

## Disallowed surfaces

Do not author new packages with ``PipelineBuilder``, ``Stage``, public ``Edge``, hand-built graph fallback builders, native-backed factories, executor objects, or deleted Megaplan-root imports.  New packages must be workflow-first: use explicit-node ``arnold.workflow.Pipeline`` authoring and return a ``Pipeline`` from ``build_pipeline()``.  ``WorkflowManifest`` is compiler output only.
