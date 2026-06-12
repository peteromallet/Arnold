# Structure Cleanup

This directory records the repo-structure cleanup process. The first pass used
ten DeepSeek/Hermes audit briefs over the repository root, with separate lenses
for root ownership, abstraction boundaries, generated state, one-off scripts,
docs, agent surfaces, navigation, git hygiene, and deletion risk.

Subsequent passes used layer-specific audit swarms for each major surface:
docs, docs root, docs references, agentic, artifacts, scripts/tools, megaplan,
config/ops, tests, package internals, package root modules,
template/corpus/recipe, and dead-module verification.

## Root-Layer Consensus

Keep these at the root because current code, tooling, or repository convention
expects them there:

- project metadata and config: `README.md`, `LICENSE`, `pyproject.toml`,
  `uv.lock`, `.github/`, `.gitignore`, `.gitmodules`, `.pre-commit-config.yaml`,
  `.importlinter`, `cloud.yaml`
- agent/tool entry instructions: `AGENTS.md`, `CLAUDE.md`
- first-class source/data/test surfaces: `vibecomfy/`, `ready_templates/`,
  `recipes/`, `workflow_corpus/`, `agentic/`, `tests/`, `docs/`, `scripts/`,
  `tools/`, `vendor/`, `agents/`
- repo-owned generated contracts currently referenced from code/docs:
  `template_index.json`, `workflow_index.json`, `external_workflow_index.json`,
  `version_matrix.json`, `custom_nodes.lock`

Move or archive root-level historical/support material:

- `CUSTOM_NODES_AUDIT.md` -> `docs/audits/CUSTOM_NODES_AUDIT.md`
- `SECURITY_AUDIT_NOTES.md` -> `docs/audits/SECURITY_AUDIT_NOTES.md`
- `plan_v2.md`, `revised_plan.md`, `finalize.json` -> `docs/plans/`
- `_fix_t6.py`, `_regen_templates.py` -> `scripts/maintenance/`

Delete ignored local state from this checkout:

- `.DS_Store`
- `_debug_*.py`
- `install.log`
- empty local `input/`

Deferred root questions for the next pass:

- whether checked-in milestone `artifacts/` should become `docs/evidence/` or
  remain a first-class evidence surface
- whether `agentic/`, `agents/`, `.agents/`, `.claude/`, and `.megaplan/`
  need clearer documentation/naming after the root pass
- whether repo-owned generated indexes should eventually move behind a
  dedicated manifest/data abstraction; they stay at root until code and tests
  are migrated deliberately

## Directory Layout

Each audit layer has a corresponding pair of subdirectories:

| Layer | Briefs | Results |
|---|---|---|
| Root (first pass) | `briefs/` | `results/` |
| Docs | `docs_briefs/` | `docs_results/` |
| Docs root | `docsroot_briefs/` | `docsroot_results/` |
| Docs reference | `docs_reference_briefs/` | `docs_reference_results/` |
| Agentic / Agent config | `agentic_briefs/` | `agentic_results/` |
| Artifacts | `artifacts_briefs/` | `artifacts_results/` |
| Scripts / Tools | `scripts_briefs/` | `scripts_results/` |
| Megaplan | `megaplan_briefs/` | `megaplan_results/` |
| Config / Ops | `config_ops_briefs/` | `config_ops_results/` |
| Tests | `tests_briefs/` | `tests_results/` |
| Package internals | `package_briefs/` | `package_results/` |
| Template / Corpus / Recipe surface | `template_surface_briefs/` | `template_surface_results/` |
| Dead-module verification | `dead_module_briefs/` | `dead_module_results/` |
| Historical docs boundary | `historical_docs_briefs/` | `historical_docs_results/` |
| Deletion-first current tree audit | `deletion_first_briefs/` | `deletion_first_results/` |
| Porting deep cleanup | `porting_deep_briefs/` | `porting_deep_results/` |
| Package root modules | `vibe_root_briefs/` | `vibe_root_results/` |
| Runtime | `runtime_briefs/` | `runtime_results/` |
| Nodes | `nodes_briefs/` | `nodes_results/` |
| Compatibility / small shims | `compat_briefs/` | `compat_results/` |
| Vendor compatibility shims | `compat_briefs/09-delete-first-risk.md` | `compat_results/09-delete-first-risk.txt` |
| Comfy nodes | `comfy_nodes_briefs/` | `comfy_nodes_results/` |

Each results directory contains:
- `NN-<topic>.txt` — agent response output
- `NN-<topic>.meta.json` — agent metadata (brief path, model, timing, cost)
- `_report.json` — aggregated fan-runner report

> **Note:** The transient `_fan.pid` file previously checked into
> `docs_reference_results/` has been removed. It was a runtime PID file
> from the subagent fan runner with no audit value.

## Status

See [`status.md`](status.md) for the per-layer completion log, verification
results, and deferred items.

## Cleanup Plan

The entire `structure_cleanup/` directory is a one-time audit artifact.
After all layers are complete and the applied cleanup is verified, move the
entire directory to `docs/historical/structure-cleanup/` per the docs-layer
recommendation.
