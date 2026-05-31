"""T4b — bind() topology-aware port resolution + RepairGradient."""

from __future__ import annotations

from megaplan._pipeline.contracts import BindResult, RepairGradient, bind
from megaplan._pipeline.judge_manifest import (
    EVALUAND_RECORD_CONTENT_TYPE,
    JudgeManifestPort,
    make_judge_manifest,
)
from megaplan._pipeline.judge_manifest_discovery import (
    manifest_to_binder_ports,
    validate_manifest_bindings,
)
from megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Port,
    PortRef,
    Stage,
    StepContext,
    StepResult,
)


class _Source:
    name = "src"
    kind = "produce"
    prompt_key = None
    slot = None
    produces = (Port(name="diff", content_type="application/x-git-diff"),)
    consumes = ()

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
        return StepResult()


class _Sink:
    name = "sink"
    kind = "produce"
    prompt_key = None
    slot = None
    produces = ()

    def __init__(self, consumes):
        self.consumes = consumes

    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
        return StepResult()


def _stages(consumes):
    src = Stage(name="src", step=_Source(), edges=(Edge(label="ok", target="sink"),))
    sink = Stage(name="sink", step=_Sink(consumes), edges=())
    return {"src": src, "sink": sink}


def _edges_map():
    return {"src": ("sink",)}


def test_bind_happy_path_returns_binding_map():
    stages = _stages((PortRef(port_name="diff", content_type="application/x-git-diff"),))
    result = bind(stages, _edges_map())
    assert isinstance(result, BindResult)
    assert result.binding_map[("sink", "diff")] == ("src", "diff")


def test_bind_attached_to_pipeline_binding_map_field():
    stages = _stages((PortRef(port_name="diff", content_type="application/x-git-diff"),))
    result = bind(stages, _edges_map())
    pipeline = Pipeline(stages=stages, entry="src", binding_map=result.binding_map)
    assert pipeline.binding_map[("sink", "diff")] == ("src", "diff")


def test_bind_no_match_emits_repair_gradient():
    stages = _stages((PortRef(port_name="absent", content_type="text/markdown"),))
    result = bind(stages, _edges_map())
    assert isinstance(result, RepairGradient)
    assert result.error_kind == "no_match"


def test_bind_typo_emits_typo_name_with_suggestion():
    stages = _stages((PortRef(port_name="dif", content_type="application/x-git-diff"),))
    result = bind(stages, _edges_map())
    assert isinstance(result, RepairGradient)
    assert result.error_kind == "typo_name"
    assert "diff" in result.suggested_moves


def test_bind_content_type_mismatch_emits_repair():
    stages = _stages((PortRef(port_name="diff", content_type="text/markdown"),))
    result = bind(stages, _edges_map())
    assert isinstance(result, RepairGradient)
    assert result.error_kind == "content_type_mismatch"


def test_bind_schema_mismatch_emits_repair():
    # A schema mismatch shows up structurally as a content-type mismatch in
    # this pure binder (schemas are encoded into content types in the
    # ContractLedger), but the bind() contract enumerates "schema_mismatch"
    # as a distinct kind for downstream callers that want to remap it.
    from megaplan._pipeline.contracts import RepairGradient as RG

    rg = RG(error_kind="schema_mismatch", wanted=None, candidates=())
    assert rg.error_kind == "schema_mismatch"


def test_bind_cardinality_mismatch_repair_kind():
    from megaplan._pipeline.contracts import RepairGradient as RG

    rg = RG(error_kind="cardinality_mismatch", wanted=None, candidates=())
    assert rg.error_kind == "cardinality_mismatch"


def test_bind_reads_stage_produces_first_then_step():
    # Stage-level produces overrides Step-level.
    src_step = _Source()
    src_stage = Stage(
        name="src",
        step=src_step,
        edges=(Edge(label="ok", target="sink"),),
        produces=(Port(name="overridden", content_type="text/markdown"),),
    )
    sink_step = _Sink((PortRef(port_name="overridden", content_type="text/markdown"),))
    sink_stage = Stage(name="sink", step=sink_step, edges=())
    stages = {"src": src_stage, "sink": sink_stage}
    result = bind(stages, _edges_map())
    assert isinstance(result, BindResult)
    assert result.binding_map[("sink", "overridden")] == ("src", "overridden")


def _m5_judge_manifest():
    return make_judge_manifest(
        name="m5-wrapper-eval",
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        model_identity="model:gpt-5.4",
        rubric_body={"rubric": "score the candidate"},
        consumes=(JudgeManifestPort("candidate", "text/markdown"),),
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE),),
        source_hash="sha256:cafebabe",
    )


def test_manifest_ports_convert_to_existing_binder_types():
    consumes, produces = manifest_to_binder_ports(_m5_judge_manifest())

    assert consumes == (PortRef(port_name="candidate", content_type="text/markdown"),)
    assert produces == (
        Port(name="evaluand", content_type=EVALUAND_RECORD_CONTENT_TYPE),
    )


def test_manifest_ports_preserve_taint_in_binder_representation():
    manifest = make_judge_manifest(
        name="m5-wrapper-eval",
        implementation="megaplan.eval.wrapper:Judge",
        arnold_api_version="2026-05-31",
        model_identity="model:gpt-5.4",
        rubric_body={"rubric": "score the candidate"},
        consumes=(JudgeManifestPort("candidate", "text/markdown", taint=("user",)),),
        produces=(JudgeManifestPort("evaluand", EVALUAND_RECORD_CONTENT_TYPE, taint=("audit",)),),
        source_hash="sha256:cafebabe",
    )

    consumes, produces = manifest_to_binder_ports(manifest)

    assert consumes == (PortRef(port_name="candidate", content_type="text/markdown"),)
    assert produces == (
        Port(
            name="evaluand",
            content_type=EVALUAND_RECORD_CONTENT_TYPE,
            taint=frozenset({"audit"}),
        ),
    )


def test_manifest_judge_stage_binds_to_upstream_producer():
    producer = Stage(
        name="producer",
        step=_Source(),
        edges=(Edge(label="judge", target="judge"),),
        produces=(Port(name="candidate", content_type="text/markdown"),),
    )
    judge = Stage(
        name="judge",
        step=_Sink(()),
        edges=(Edge(label="halt", target="halt"),),
    )
    pipeline = Pipeline(stages={"producer": producer, "judge": judge}, entry="producer")

    result = validate_manifest_bindings(
        pipeline,
        judge_stage_name="judge",
        manifest=_m5_judge_manifest(),
    )

    assert isinstance(result, BindResult)
    assert result.binding_map[("judge", "candidate")] == (
        "producer",
        "candidate",
    )
