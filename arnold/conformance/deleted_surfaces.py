"""Machine-readable M6 deletion inventory.

The rows below are sourced from:

* ``docs/arnold/m6-deletion-list.md``
* ``docs/arnold/runtime-salvage-deletion-map.md``

Wildcard rows from the docs are kept as patterns and expanded only for gates
that need concrete representative modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SourceDoc = Literal[
    "docs/arnold/m6-deletion-list.md",
    "docs/arnold/runtime-salvage-deletion-map.md",
]

SurfaceKind = Literal["path", "module", "command", "symbol"]


@dataclass(frozen=True)
class DeletedSurface:
    surface: str
    kind: SurfaceKind
    source_doc: SourceDoc
    source_inventory: str
    m5_outcome: str
    m6_action: str
    note: str = ""


M6_DELETION_LIST: tuple[DeletedSurface, ...] = (
    DeletedSurface("arnold/pipelines/megaplan/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "delete", "Remove package tree."),
    DeletedSurface("arnold/pipelines/jokes/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "delete", "Remove package tree."),
    DeletedSurface("arnold/pipelines/creative/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "delete", "Remove package tree."),
    DeletedSurface("arnold/pipelines/doc/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "delete", "Remove package tree."),
    DeletedSurface("arnold/pipelines/live_supervisor/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "delete", "Remove package tree."),
    DeletedSurface("arnold/pipelines/select_tournament/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "delete", "Remove package tree."),
    DeletedSurface("arnold/pipelines/simplify_writing/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "archive", "Move to docs/archive/m5/, then delete source tree."),
    DeletedSurface("arnold/pipelines/vibecomfy_executor/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "archive", "Move to docs/archive/m5/, then delete source tree."),
    DeletedSurface("arnold/pipelines/writing_panel_strict.py", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "delete", "Remove file."),
    DeletedSurface("arnold/pipelines/epic_blitz/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "archive", "Move to docs/archive/m5/, then delete source tree."),
    DeletedSurface("arnold/pipelines/folder_audit/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "archive", "Move to docs/archive/m5/, then delete source tree."),
    DeletedSurface("arnold/pipelines/deliberation/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "archive", "Move to docs/archive/m5/, then delete source tree."),
    DeletedSurface("arnold/pipelines/_deliberation_example/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "archive", "Move to docs/archive/m5/, then delete source tree."),
    DeletedSurface("arnold/pipelines/briefs/", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "archive", "Move to docs/archive/m5/, then delete source tree."),
    DeletedSurface("arnold_pipelines/megaplan/pipelines/epic_blitz.py", "path", "docs/arnold/m6-deletion-list.md", "m5-pipeline-disposition.md", "archive", "Move to docs/archive/m5/, then delete source file."),
    DeletedSurface("arnold_pipelines/megaplan/cli/arnold.py", "path", "docs/arnold/m6-deletion-list.md", "m5-cli-dispatch-chain.md", "delete", "Remove legacy top-level dispatch."),
    DeletedSurface("arnold_pipelines/megaplan/cli/parser.py", "path", "docs/arnold/m6-deletion-list.md", "m5-cli-dispatch-chain.md", "delete", "Remove legacy parser."),
    DeletedSurface("arnold pipelines *", "command", "docs/arnold/m6-deletion-list.md", "m5-cli-command-mapping.md", "delete", "Remove command handlers.", note="Wildcard command row; concrete installed CLI help gates scan arnold pipelines fragments."),
    DeletedSurface("arnold <module> *", "command", "docs/arnold/m6-deletion-list.md", "m5-cli-command-mapping.md", "delete", "Remove module verb handlers.", note="Wildcard command row; concrete installed CLI help gates scan removed step-command fragments."),
    DeletedSurface("arnold init/plan/prep/... step commands", "command", "docs/arnold/m6-deletion-list.md", "m5-cli-command-mapping.md", "delete", "Remove Megaplan step commands."),
    DeletedSurface("scripts/backfill_step_receipts.py", "path", "docs/arnold/m6-deletion-list.md", "m5-script-tool-inventory.md", "archive", "Moved to docs/archive/m5/scripts/, then delete."),
    DeletedSurface("scripts/m4_oracle_bisect.py", "path", "docs/arnold/m6-deletion-list.md", "m5-script-tool-inventory.md", "archive", "Moved to docs/archive/m5/scripts/, then delete."),
    DeletedSurface("scripts/record_oracle_traces.py", "path", "docs/arnold/m6-deletion-list.md", "m5-script-tool-inventory.md", "archive", "Moved to docs/archive/m5/scripts/, then delete."),
    DeletedSurface("scripts/silent_failure_census.py", "path", "docs/arnold/m6-deletion-list.md", "m5-script-tool-inventory.md", "archive", "Moved to docs/archive/m5/scripts/, then delete."),
    DeletedSurface("tools/m4_oracle_bisect.py", "path", "docs/arnold/m6-deletion-list.md", "m5-script-tool-inventory.md", "archive", "Moved to docs/archive/m5/tools/, then delete."),
    DeletedSurface("_gen_corpus.py", "path", "docs/arnold/m6-deletion-list.md", "m5-script-tool-inventory.md", "archive", "Moved to docs/archive/m5/, then delete."),
    DeletedSurface("tests/_pipeline/", "path", "docs/arnold/m6-deletion-list.md", "m5-legacy-test-inventory.md", "archive", "Moved to tests/archive/m5/, then delete."),
    DeletedSurface("tests/docs/test_arnold_external_builder.py", "path", "docs/arnold/m6-deletion-list.md", "m5-legacy-test-inventory.md", "archive", "Moved to tests/archive/m5/docs/, then delete."),
    DeletedSurface("arnold/pipelines/megaplan/data/", "path", "docs/arnold/m6-deletion-list.md", "m5-generated-artifact-manifest.md", "delete", "Removed in Phase 4; old generated skills/composed no longer packaged."),
)

RUNTIME_SALVAGE_DELETION_TARGETS: tuple[DeletedSurface, ...] = (
    DeletedSurface("arnold.runtime.batch*", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.runtime", "M6 deletion target", "Product-specific batch scheduling.", note="Wildcard row; concrete gates expand to arnold.runtime.batch."),
    DeletedSurface("arnold.runtime.driver", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.runtime", "M6 deletion target", "Superseded by arnold.execution.runner.run."),
    DeletedSurface("arnold.runtime.process", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.runtime", "M6 deletion target", "Process model no longer used."),
    DeletedSurface("arnold.runtime.recovery", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.runtime", "M6 deletion target", "Recovery logic is now journal replay."),
    DeletedSurface("arnold.runtime.sandbox", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.runtime", "M6 deletion target", "Replaced by artifact-root isolation."),
    DeletedSurface("arnold.runtime.settings*", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.runtime", "M6 deletion target", "Settings resolution moved to product harness.", note="Wildcard row; concrete gates expand to arnold.runtime.settings."),
    DeletedSurface("arnold.runtime.wal_fold", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.runtime", "M6 deletion target", "WAL folding replaced by journal fold."),
    DeletedSurface("arnold.runtime.oracle", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.runtime", "M6 deletion target", "Oracle coordination is out of scope for the neutral runtime."),
    DeletedSurface("arnold.runtime.operations", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.runtime", "M6 deletion target", "Operational helpers are product-side."),
    DeletedSurface("arnold.pipeline.hooks", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.pipeline", "M6 deletion target", "Hook dispatch is registry-driven."),
    DeletedSurface("arnold.pipeline.step_invocation", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.pipeline", "M6 deletion target", "Native step invocation replaced by backend hooks."),
    DeletedSurface("arnold.pipeline.token_cost / model_resource_capabilities / media_cost", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.pipeline", "M6 deletion target", "Cost/resource modeling belongs in product harness.", note="Grouped row; concrete gates expand to all three modules."),
    DeletedSurface("arnold.pipeline.profiles", "module", "docs/arnold/runtime-salvage-deletion-map.md", "arnold.pipeline", "M6 deletion target", "Profile selection is product-side."),
    DeletedSurface("arnold.pipelines.megaplan._pipeline.discovery", "module", "docs/arnold/runtime-salvage-deletion-map.md", "Discovery", "M6 deletion target", "Product-specific discovery."),
    DeletedSurface("arnold.pipelines.megaplan.runtime", "module", "docs/arnold/runtime-salvage-deletion-map.md", "Oracle", "M6 deletion target", "Product runtime adapter; replaced by registry shims."),
    DeletedSurface("arnold.pipelines.megaplan.agent_runtime", "module", "docs/arnold/runtime-salvage-deletion-map.md", "Agent adapter shims", "M6 deletion target", "Older agent runtime shims replaced by execution registry bridge.", note="Docs phrase this as older agent runtime shims in the package."),
)

DELETED_SURFACES: tuple[DeletedSurface, ...] = (
    *M6_DELETION_LIST,
    *RUNTIME_SALVAGE_DELETION_TARGETS,
)

DELETED_SOURCE_PATHS: tuple[str, ...] = tuple(
    surface.surface
    for surface in M6_DELETION_LIST
    if surface.kind == "path" and not surface.surface.startswith("tests/")
)

DELETED_IMPORT_MODULES: tuple[str, ...] = (
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan._pipeline",
    "arnold_pipelines.megaplan._pipeline.builder",
    "arnold_pipelines.megaplan._pipeline.runtime",
    "arnold_pipelines.megaplan._pipeline.dispatch",
    "arnold_pipelines.megaplan._pipeline.types",
    "arnold_pipelines.megaplan.stages",
    "arnold_pipelines.megaplan.stages.inprocess_step",
    "arnold.runtime.batch",
    "arnold.runtime.driver",
    "arnold.runtime.process",
    "arnold.runtime.recovery",
    "arnold.runtime.sandbox",
    "arnold.runtime.settings",
    "arnold.runtime.wal_fold",
    "arnold.runtime.oracle",
    "arnold.runtime.operations",
    "arnold.pipeline.hooks",
    "arnold.pipeline.step_invocation",
    "arnold.pipeline.token_cost",
    "arnold.pipeline.model_resource_capabilities",
    "arnold.pipeline.media_cost",
    "arnold.pipeline.profiles",
    "arnold.pipelines.megaplan._pipeline.discovery",
    "arnold.pipelines.megaplan.runtime",
    "arnold.pipelines.megaplan.agent_runtime",
)

DELETED_IMPORT_PREFIXES: tuple[str, ...] = (
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan._pipeline",
    "arnold_pipelines.megaplan.stages",
)

DELETED_ARTIFACT_PATH_PREFIXES: tuple[str, ...] = (
    "arnold/pipelines/megaplan/",
    "arnold_pipelines/megaplan/_pipeline/",
    "arnold_pipelines/megaplan/stages/",
)

DELETED_MEGAPLAN_LEGACY_SYMBOLS: tuple[str, ...] = (
    "build_legacy_pipeline",
    "compile_planning_pipeline",
    "WorkflowManifest",
    "run_pipeline",
    "InProcessHandlerStep",
    "HandlerStep",
    "Stage",
)

DELETED_PIPELINE_TOP_LEVEL_SYMBOLS: tuple[str, ...] = (
    "Stage",
    "Edge",
    "ParallelStage",
    "PipelineBuilder",
    "run_pipeline",
)

DELETED_CLI_HELP_FRAGMENTS: tuple[str, ...] = (
    "arnold pipelines",
    "arnold.pipelines.megaplan",
    "arnold_pipelines.megaplan._pipeline",
    "arnold_pipelines.megaplan.stages",
    "megaplan init",
    "megaplan prep",
    "megaplan plan",
    "megaplan critique",
    "megaplan gate",
    "megaplan revise",
    "megaplan finalize",
    "megaplan execute",
    "megaplan review",
    "megaplan run",
)
