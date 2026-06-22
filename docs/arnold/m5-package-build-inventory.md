<!-- M5 Phase 1 inventory: package build contents. -->

# M5 Package Build Inventory

## Wheel / sdist packages

| Package | Type | Included data | py.typed | Notes |
| --- | --- | --- | --- | --- |
| `arnold` | regular | Python sources, `py.typed`, manifest/runtime modules | yes (`arnold/py.typed`) | Core SDK and workflow runtime. |
| `arnold_pipelines` | namespace | Megaplan plugin subtree, `pipeline_ids.json`, `SKILL.md`, generated data | yes (`arnold_pipelines/megaplan/py.typed`) | Plugin package; root `__init__.py` removed to make it a namespace package. |

## Entrypoints

| Entrypoint | Function | Status |
| --- | --- | --- |
| `arnold` | `arnold.cli:cli_entry` | required (added in M5) |
| `megaplan` | `arnold_pipelines.megaplan.cli:cli_entry` | legacy / transition-only |

## Expected wheel contents

- `arnold/` package tree including `arnold/cli/workflow.py`, `arnold/cli/operators.py`, `arnold/cli/execution.py`.
- `arnold_pipelines/megaplan/` package tree.
- `arnold/py.typed` and `arnold_pipelines/megaplan/py.typed` markers.
- `arnold_pipelines/megaplan/_pipeline/pipeline_ids.json` and any survivor registry files.
- `arnold_pipelines/megaplan/data/_composed/` and `_codex_skills/` generated assets (post-M5 migration).

## Build exclusions

The following remain excluded per `pyproject.toml` `[tool.hatch.build]`:

- `arnold/pipelines/megaplan/cloud/_reference/**`
- `arnold/pipelines/megaplan/agent/pyproject.toml`
- `arnold/pipelines/megaplan/agent/auto_improve/iterations/**`
- Corresponding `arnold_pipelines` paths.

## Verification

- Build wheel and sdist in a clean venv.
- Verify `arnold` console script exists and imports only public surfaces.
- Verify `arnold workflow --help` works from the installed wheel.
- Verify deleted command/module paths are not importable through public surfaces.
