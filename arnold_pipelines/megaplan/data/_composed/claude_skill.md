---
name: workflow-claude
description: Workflow-only composed skill for Claude.
---

# workflow-claude

This composed rule is the workflow-only successor to the legacy Megaplan skill bundles.  It references only ``arnold.workflow`` and the shipped pipeline registry.

## Launcher

Use the ``arnold`` console script installed by the wheel:

```bash
arnold workflow --help
arnold workflow check --module <package.module>:build_pipeline
```

## Shipped pipelines

- `arnold.folder_audit` -> `arnold workflow check --module arnold.pipelines.folder_audit:build_pipeline`
- `megaplan.creative` -> `arnold workflow check --module arnold.pipelines.megaplan.pipelines.creative:build_pipeline`
- `megaplan.doc` -> `arnold workflow check --module arnold.pipelines.megaplan.pipelines.doc:build_pipeline`
- `megaplan.epic_blitz` -> `arnold workflow check --module arnold.pipelines.megaplan.pipelines.epic_blitz:build_pipeline`
- `megaplan.jokes` -> `arnold workflow check --module arnold.pipelines.megaplan.pipelines.jokes:build_pipeline`
- `megaplan.live_supervisor` -> `arnold workflow check --module arnold.pipelines.megaplan.pipelines.live_supervisor:build_pipeline`
- `megaplan.select_tournament` -> `arnold workflow check --module arnold.pipelines.megaplan.pipelines.select_tournament:build_pipeline`
- `megaplan.writing_panel_strict` -> `arnold workflow check --module arnold.pipelines.megaplan.pipelines.writing_panel_strict:build_pipeline`
- `evidence_pack.verifier` -> `arnold workflow check --module arnold_pipelines.evidence_pack:build_pipeline`
- `megaplan.core` -> `arnold workflow check --module arnold_pipelines.megaplan:build_pipeline`
- `megaplan.planning` -> `arnold workflow check --module arnold_pipelines.megaplan.pipelines.planning:build_pipeline`

## Disallowed surfaces

Do not author new packages with ``PipelineBuilder``, ``Stage``, public ``Edge``, native decorators, or ``arnold.pipelines.megaplan`` imports.  Use ``arnold.workflow.Pipeline`` and ``arnold_pipelines.discovery`` instead.
