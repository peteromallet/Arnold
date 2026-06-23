---
name: pipeline-template-reference
description: Reference contract for the canonical Arnold pipeline template scaffold.
---

# Skill: Pipeline Template Reference

The canonical scaffold is `arnold_pipelines/_template/`. It shows the minimum
required contract for a workflow pipeline:

- `build_pipeline()` returns `arnold.workflow.Pipeline`.
- Module-level metadata variables.
- Typed module-level component exports for Python-shaped source, or explicit
  `Step`/`Route` topology with stable ids while using the current DSL directly.

For Python-shaped authoring, organize components as package-local exports such
as `steps.py`, `prompts.py`, `policies.py`, `schemas.py`, and `subflows.py`.
Workflow imports define the authored graph. Generated component catalogs and
manifest files are derived artifacts, not package source.

Do not use the legacy authoring primitives in new packages.
