"""Public surface of the megaplan `_pipeline` package (Sprint 1).

Re-exports the frozen primitive types defined in ``types.py``. The
executor and demo modules live alongside and are imported separately
(``megaplan._pipeline.executor`` / ``megaplan._pipeline.demo_judges``).

M3a compatibility bridge: several of the re-exported types (Edge,
Pipeline, Stage, Step, StepContext, StepResult, PipelineVerdict,
ParallelStage) now have neutral counterparts in ``arnold.pipeline``.
The megaplan versions are kept as forwarders so legacy consumers
continue to compile.  Delete these re-exports in M7 when old paths
are removed.
"""

# M3a compatibility bridge; delete in M7
from arnold_pipelines.megaplan._pipeline.types import (  # noqa: E402
    Edge,
    Overlay,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
    StepContext,
    StepResult,
    PipelineVerdict,
)
from arnold_pipelines.megaplan._pipeline.judge_manifest import (
    EVALUAND_RECORD_CONTENT_TYPE,
    JUDGE_MANIFEST_SCHEMA,
    JudgeManifestPort,
    JudgePieceManifest,
    compute_judge_version,
    compute_piece_version,
    compute_rubric_hash,
    dump_judge_manifest,
    load_judge_manifest,
    make_judge_manifest,
)
from arnold_pipelines.megaplan._pipeline.judge_manifest_discovery import (
    JudgeManifestDiagnostics,
    JudgeManifestMatch,
    discover_judge_manifests,
    find_judge_manifest,
    manifest_to_binder_ports,
    validate_manifest_bindings,
    validate_judge_manifest,
)

__all__ = [
    "Pipeline",
    "Stage",
    "Step",
    "StepContext",
    "StepResult",
    "Edge",
    "Overlay",
    "PipelineVerdict",
    "ParallelStage",
    "EVALUAND_RECORD_CONTENT_TYPE",
    "JUDGE_MANIFEST_SCHEMA",
    "JudgeManifestPort",
    "JudgePieceManifest",
    "compute_judge_version",
    "compute_piece_version",
    "compute_rubric_hash",
    "dump_judge_manifest",
    "load_judge_manifest",
    "make_judge_manifest",
    "JudgeManifestDiagnostics",
    "JudgeManifestMatch",
    "discover_judge_manifests",
    "find_judge_manifest",
    "manifest_to_binder_ports",
    "validate_manifest_bindings",
    "validate_judge_manifest",
]
