<!-- M5 Phase 5 inventory: consolidated M6 deletion targets. -->

# M6 Deletion List

> **Phase A status (branch `workflow-manifest-runtime-m6-purge`):** All
> `delete` targets below have been removed from the source tree; `archive`
> targets have been moved to `docs/archive/m5/` and removed from their original
> locations. The public `arnold.pipeline` package no longer re-exports the
> obsolete legacy native symbols (`PipelineBuilder`, `Stage`, `Edge`, `ParallelStage`, or
> `run_pipeline`), and `arnold.cli` no longer delegates to legacy Megaplan CLI
> surfaces.
>
> **Phase B status:** Latent references to deleted surfaces were purged from
> `arnold/agent/tools/*`, `arnold/agent/hermes_cli/config.py`,
> `arnold_pipelines/megaplan/workers/hermes.py`,
> `arnold_pipelines/megaplan/workers/_impl.py`,
> `arnold_pipelines/megaplan/cloud/cli.py`, `arnold_pipelines/megaplan/auto.py`,
> and `arnold_pipelines/megaplan/__main__.py`. Legacy conformance tests for the
> migrated `evidence_pack` workflow pipeline and agent tool compatibility imports
> were removed. Conformance allowlists were burned down, expanded to concrete
> files, and annotated with owner/expiry/non-legacy rationale. Generated docs,
> pipeline ID registries, package disposition, composed rules, and skills were
> regenerated. The conformance suite and the M6 final gate are green.

Every row traces back to a disposition in the M5 inventories and a concrete M5
outcome.

| Path / surface | Source inventory | M5 outcome | M6 action |
| --- | --- | --- | --- |
| `arnold/pipelines/megaplan/` | `m5-pipeline-disposition.md` | delete | Remove package tree. |
| `arnold/pipelines/jokes/` | `m5-pipeline-disposition.md` | delete | Remove package tree. |
| `arnold/pipelines/creative/` | `m5-pipeline-disposition.md` | delete | Remove package tree. |
| `arnold/pipelines/doc/` | `m5-pipeline-disposition.md` | delete | Remove package tree. |
| `arnold/pipelines/live_supervisor/` | `m5-pipeline-disposition.md` | delete | Remove package tree. |
| `arnold/pipelines/select_tournament/` | `m5-pipeline-disposition.md` | delete | Remove package tree. |
| `arnold/pipelines/simplify_writing/` | `m5-pipeline-disposition.md` | archive | Move to `docs/archive/m5/`, then delete source tree. |
| `arnold/pipelines/vibecomfy_executor/` | `m5-pipeline-disposition.md` | archive | Move to `docs/archive/m5/`, then delete source tree. |
| `arnold/pipelines/writing_panel_strict.py` | `m5-pipeline-disposition.md` | delete | Remove file. |
| `arnold/pipelines/epic_blitz/` | `m5-pipeline-disposition.md` | archive | Move to `docs/archive/m5/`, then delete source tree. |
| `arnold/pipelines/folder_audit/` | `m5-pipeline-disposition.md` | archive | Move to `docs/archive/m5/`, then delete source tree. |
| `arnold/pipelines/deliberation/` | `m5-pipeline-disposition.md` | archive | Move to `docs/archive/m5/`, then delete source tree. |
| `arnold/pipelines/_deliberation_example/` | `m5-pipeline-disposition.md` | archive | Move to `docs/archive/m5/`, then delete source tree. |
| `arnold/pipelines/briefs/` | `m5-pipeline-disposition.md` | archive | Move to `docs/archive/m5/`, then delete source tree. |
| `arnold_pipelines/megaplan/pipelines/epic_blitz.py` | `m5-pipeline-disposition.md` | archive | Move to `docs/archive/m5/`, then delete source file. |
| `arnold_pipelines/megaplan/cli/arnold.py` | `m5-cli-dispatch-chain.md` | delete | Remove legacy top-level dispatch. |
| `arnold_pipelines/megaplan/cli/parser.py` | `m5-cli-dispatch-chain.md` | delete | Remove legacy parser. |
| `arnold pipelines *` subcommands | `m5-cli-command-mapping.md` | delete | Remove command handlers. |
| `arnold <module> *` subcommands | `m5-cli-command-mapping.md` | delete | Remove module verb handlers. |
| `arnold init/plan/prep/...` step commands | `m5-cli-command-mapping.md` | delete | Remove Megaplan step commands. |
| `scripts/backfill_step_receipts.py` | `m5-script-tool-inventory.md` | archive | Moved to `docs/archive/m5/scripts/`, then delete. |
| `scripts/m4_oracle_bisect.py` | `m5-script-tool-inventory.md` | archive | Moved to `docs/archive/m5/scripts/`, then delete. |
| `scripts/record_oracle_traces.py` | `m5-script-tool-inventory.md` | archive | Moved to `docs/archive/m5/scripts/`, then delete. |
| `scripts/silent_failure_census.py` | `m5-script-tool-inventory.md` | archive | Moved to `docs/archive/m5/scripts/`, then delete. |
| `tools/m4_oracle_bisect.py` | `m5-script-tool-inventory.md` | archive | Moved to `docs/archive/m5/tools/`, then delete. |
| `_gen_corpus.py` | `m5-script-tool-inventory.md` | archive | Moved to `docs/archive/m5/`, then delete. |
| `tests/_pipeline/` | `m5-legacy-test-inventory.md` | archive | Moved to `tests/archive/m5/`, then delete. |
| `tests/pipelines/` | `m5-legacy-test-inventory.md` | archive | Moved to `tests/archive/m5/`, then delete. |
| `tests/docs/test_arnold_external_builder.py` | `m5-legacy-test-inventory.md` | archive | Moved to `tests/archive/m5/docs/`, then delete. |
| `arnold/pipelines/megaplan/data/` | `m5-generated-artifact-manifest.md` | delete | Removed in Phase 4; old generated skills/composed no longer packaged. |

## Keep list (survivors)

- `arnold.workflow` authoring surface and tests.
- `arnold.execution.run` runtime and tests.
- `arnold/cli/workflow.py` and `arnold/cli/operators.py`.
- Migrated `arnold_pipelines/*` shipped pipelines with `manifest_hash` in registries.
- `arnold_pipelines/megaplan/data/_codex_skills/` and `_composed/` workflow-only generated assets.
- `scripts/check_workflow_pipeline_inventory.py`, `scripts/check_pipeline_id_registry.py`, `scripts/validate_package_disposition.py`, `scripts/render_package_disposition_md.py`, `scripts/generate_arnold_docs.py`.

## Branch / worktree retirement

- Branch: `workflow-manifest-runtime-m6-purge`
- Worktree: `/Users/peteromalley/Documents/.megaplan-worktrees/workflow-manifest-runtime-m6-purge`
- Retirement criteria: Phase B conformance suite green, final gate green, installed-wheel conformance green, generated artifacts up to date, and no legacy `arnold.pipelines.megaplan` imports in production code.
- After merge: this worktree can be removed; the branch should be deleted after
  PR merge. Any future resurrection of deleted surfaces must be treated as a
  new feature, not a revert.
