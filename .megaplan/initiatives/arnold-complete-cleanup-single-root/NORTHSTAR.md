# North Star

Arnold has one Megaplan implementation root:

```text
arnold_pipelines/megaplan/
```

The single-root migration is complete on `main` in commit `1052ef091a`, which
deleted the legacy tree:

```text
arnold/pipelines/megaplan/
```

It is absent, not a remaining implementation or compatibility surface. This
epic now verifies and closes the remaining conformance and cleanup gates.

## What "Clean" Means

- Every remaining piece of loose Arnold work is either landed, archived, or deleted.
- `arnold_pipelines.megaplan` does not import implementation behavior from `arnold.pipelines.megaplan`.
- No public docs, bundled skills, generated assets, CLI examples, discovery rows, or tests instruct agents or humans to use `python -m arnold.pipelines.megaplan`.
- No final `_pipeline` compatibility namespace is recreated under `arnold_pipelines`.
- Existing Megaplan behavior is preserved for current supported workflows: init/status/execute, chain start/status/resume, PR helpers, worker launches, import side effects, discovery, and installed-wheel usage.
- Import order cannot change content-type registration, model adapter installation, normalizer registration, or pipeline registry behavior.
- Editable installs and built wheels exercise the same canonical implementation.
- The conformance gate lives in `arnold/conformance/checks.py` and `arnold/conformance/legacy_reference_allowlist.json`. It is shrink-only, has 134 live entries, and enforces `stale=[]`.
- The deletion gate is binary for the Megaplan root: no business logic under `arnold/pipelines/megaplan`, no untracked shims, no hidden symlink churn, and no stale `__pycache__` survivors under that root. The parent `arnold/pipelines/` legitimately retains `_authoring.py` and `evidence_pack/`, whose `__pycache__` is gitignored.
- In this epic, "legacy registry" means the deleted `arnold_pipelines.megaplan._pipeline.registry` namespace. It does not mean the canonical, non-empty `arnold_pipelines/megaplan/pipeline_ids.json`, which retains five keep rows.

## Why This Matters

The native Python completion epic solved the pipeline-shape direction, and the single-root migration has now landed on `main`. The remaining closeout verifies that local CLI, tests, workers, docs, and packages continue to use the canonical root rather than reintroducing the old duplicate-root hazard.

The purpose of this epic is not cosmetic tidiness. It closes the class of "fixed in one root, running the other root" bugs and gives later composition/platform epics a single authority to build on.
