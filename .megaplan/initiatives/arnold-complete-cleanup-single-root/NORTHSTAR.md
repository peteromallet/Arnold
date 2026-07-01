# North Star

Arnold has one Megaplan implementation root:

```text
arnold_pipelines/megaplan/
```

The legacy tree:

```text
arnold/pipelines/megaplan/
```

contains no business logic in the final state. Prefer deleting it entirely. If a short-lived compatibility file is needed during the migration, it is a tracked temporary shim, not a product surface.

## What "Clean" Means

- Every remaining piece of loose Arnold work is either landed, archived, or deleted.
- `arnold_pipelines.megaplan` does not import implementation behavior from `arnold.pipelines.megaplan`.
- No public docs, bundled skills, generated assets, CLI examples, discovery rows, or tests instruct agents or humans to use `python -m arnold.pipelines.megaplan`.
- No final `_pipeline` compatibility namespace is recreated under `arnold_pipelines`.
- Existing Megaplan behavior is preserved for current supported workflows: init/status/run, chain start/status/resume, PR helpers, worker launches, import side effects, discovery, and installed-wheel usage.
- Import order cannot change content-type registration, model adapter installation, normalizer registration, or pipeline registry behavior.
- Editable installs and built wheels exercise the same canonical implementation.
- The deletion gate is binary: no business logic under `arnold/pipelines/megaplan`, no untracked shims, no hidden symlink churn, no stale `__pycache__` survivors.

## Why This Matters

The native Python completion epic solved the pipeline-shape direction, but Megaplan still has a duplicate-root hazard. Fixes can land in one root while local CLI, tests, workers, docs, or packages import the other. That is exactly how the previous root cleanup attempt became unsafe: it tried to delete or shim surfaces before the canonical replacement existed.

The purpose of this epic is not cosmetic tidiness. It removes the class of "fixed in one root, running the other root" bugs and gives later composition/platform epics a single authority to build on.
