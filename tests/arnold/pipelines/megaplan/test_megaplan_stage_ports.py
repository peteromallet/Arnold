from __future__ import annotations

import inspect

from arnold.pipelines.megaplan._pipeline.pattern_topology import (
    critique_revise_gate_loop,
    phase_zero_gate,
)
from arnold.pipelines.megaplan._pipeline.types import Edge, ParallelStage, Stage, StepResult
from arnold.pipeline.step_invocation import StepInvocation
from arnold.pipeline.types import Port, PortRef, ReadRef, WriteRef
from arnold.pipeline.native.graph_projection import _NativePhaseStep
from arnold.pipelines.megaplan.pipeline import (
    _planning_loop_should_halt,
    build_pipeline,
)
from arnold.pipelines.megaplan.pipeline_contracts import (
    LOGICAL_CRITIQUE_PAYLOAD,
    LOGICAL_EXECUTE_PAYLOAD,
    LOGICAL_FINALIZE_PAYLOAD,
    LOGICAL_GATE_PAYLOAD,
    LOGICAL_PLAN_PAYLOAD,
    LOGICAL_PREP_PAYLOAD,
    LOGICAL_REVISE_PAYLOAD,
    LOGICAL_REVIEW_PAYLOAD,
    LOGICAL_TIEBREAKER_PAYLOAD,
)
from arnold.pipelines.megaplan.routing import (
    PLANNING_DECISIONS,
    PLAN_ESCALATE,
    PLAN_ITERATE,
    PLAN_PROCEED,
    tiebreaker_edges,
)
from arnold.pipelines.megaplan.stages.critique import CritiqueStep
from arnold.pipelines.megaplan.stages.execute import ExecuteStep
from arnold.pipelines.megaplan.stages.finalize import FinalizeStep
from arnold.pipelines.megaplan.stages.gate import GateStep
from arnold.pipelines.megaplan.stages.plan import PlanStep
from arnold.pipelines.megaplan.stages.prep import PrepStep
from arnold.pipelines.megaplan.stages.review import ReviewStep
from arnold.pipelines.megaplan.stages.revise import ReviseStep
from arnold.pipelines.megaplan.stages.tiebreaker import TiebreakerStep


EXPECTED_STAGE_ORDER = (
    "prep",
    "plan",
    "critique",
    "gate",
    "revise",
    "finalize",
    "execute",
    "review",
    "tiebreaker",
)


def test_megaplan_stage_shapes_accept_authoring_fields_and_legacy_refs() -> None:
    invocation = StepInvocation(kind="tool", metadata={"action": "write"})
    read_ref = ReadRef(name="brief.md")
    write_ref = WriteRef(name="draft.md")
    produced_port = Port(name="draft", content_type="text/markdown")
    consumed_port = PortRef(port_name="brief", content_type="text/markdown")

    stage = Stage(
        name="draft",
        step=PrepStep(),
        reads=(read_ref,),
        writes=(write_ref,),
        produces=(produced_port,),
        consumes=(consumed_port,),
        invocation=invocation,
        required_capabilities=("fs.read", "fs.write"),
    )
    parallel_stage = ParallelStage(
        name="panel",
        steps=(CritiqueStep(), ReviewStep()),
        join=lambda results, ctx: StepResult(next="halt"),
        reads=(read_ref,),
        writes=(write_ref,),
        produces=(produced_port,),
        consumes=(consumed_port,),
        invocation=invocation,
        required_capabilities=("fs.read", "fs.write"),
    )

    assert stage.reads == (read_ref,)
    assert stage.writes == (write_ref,)
    assert stage.invocation is invocation
    assert stage.required_capabilities == ("fs.read", "fs.write")
    assert parallel_stage.reads == (read_ref,)
    assert parallel_stage.writes == (write_ref,)
    assert parallel_stage.invocation is invocation
    assert parallel_stage.required_capabilities == ("fs.read", "fs.write")


def _canonical_stage_signatures() -> dict[str, inspect.Signature]:
    return {
        "phase_zero_gate": inspect.signature(phase_zero_gate),
        "critique_revise_gate_loop": inspect.signature(critique_revise_gate_loop),
    }


def _expected_pattern_stages() -> dict[str, Stage]:
    prep_stage = phase_zero_gate(
        PrepStep(),
        name="prep",
        on_pass="plan",
        on_fail="halt",
    )
    cycle = critique_revise_gate_loop(
        CritiqueStep(),
        GateStep(),
        ReviseStep(),
        on_proceed="finalize",
        on_iterate="revise",
        on_tiebreaker="tiebreaker",
        on_escalate="finalize",
        critique_fallback_edges=(
            Edge(label="gate_unset:gate", target="gate"),
            Edge(label="gate", target="gate"),
        ),
        gate_extra_edges=(
            Edge(label="revise", target="revise"),
            Edge(label="gate", target="finalize"),
            Edge(label="override force-proceed", target="finalize"),
            Edge(label="override abort", target="halt"),
        ),
        revise_target="critique",
    )
    return {"prep": prep_stage, **cycle}


def _declared_port_pairs(stage: Stage) -> set[tuple[str, str]]:
    return {(port.name, port.logical_type) for port in stage.produces}


def _consumed_port_pairs(stage: Stage) -> set[tuple[str, str]]:
    return {(port.port_name, port.logical_type) for port in stage.consumes}


def test_all_nine_canonical_stages_have_enriched_port_declarations() -> None:
    stages = build_pipeline().stages

    assert tuple(stages) == EXPECTED_STAGE_ORDER
    assert {name: bool(stage.produces) for name, stage in stages.items()} == {
        name: True for name in EXPECTED_STAGE_ORDER
    }
    assert {name: bool(stage.consumes) for name, stage in stages.items()} == {
        "prep": False,
        "plan": True,
        "critique": True,
        "gate": True,
        "revise": True,
        "finalize": True,
        "execute": True,
        "review": True,
        "tiebreaker": True,
    }
    assert _declared_port_pairs(stages["prep"]) == {("prep_payload", LOGICAL_PREP_PAYLOAD)}
    assert _declared_port_pairs(stages["plan"]) == {("plan_payload", LOGICAL_PLAN_PAYLOAD)}
    assert _declared_port_pairs(stages["critique"]) == {
        ("critique_payload", LOGICAL_CRITIQUE_PAYLOAD)
    }
    assert _declared_port_pairs(stages["gate"]) == {("gate_payload", LOGICAL_GATE_PAYLOAD)}
    assert _declared_port_pairs(stages["revise"]) == {
        ("revise_payload", LOGICAL_REVISE_PAYLOAD)
    }
    assert _declared_port_pairs(stages["finalize"]) == {
        ("finalize_payload", LOGICAL_FINALIZE_PAYLOAD)
    }
    assert _declared_port_pairs(stages["execute"]) == {
        ("execute_payload", LOGICAL_EXECUTE_PAYLOAD)
    }
    assert _declared_port_pairs(stages["review"]) == {
        ("review_payload", LOGICAL_REVIEW_PAYLOAD)
    }
    assert _declared_port_pairs(stages["tiebreaker"]) == {
        ("tiebreaker_payload", LOGICAL_TIEBREAKER_PAYLOAD)
    }


def test_required_branch_and_loop_seam_pairs_are_declared() -> None:
    stages = build_pipeline().stages

    assert ("prep_payload", LOGICAL_PREP_PAYLOAD) in _consumed_port_pairs(stages["plan"])
    assert ("plan_payload", LOGICAL_PLAN_PAYLOAD) in _consumed_port_pairs(stages["critique"])
    assert ("critique_payload", LOGICAL_CRITIQUE_PAYLOAD) in _consumed_port_pairs(stages["gate"])
    assert ("gate_payload", LOGICAL_GATE_PAYLOAD) in _consumed_port_pairs(stages["revise"])
    assert ("gate_payload", LOGICAL_GATE_PAYLOAD) in _consumed_port_pairs(stages["finalize"])
    assert ("gate_payload", LOGICAL_GATE_PAYLOAD) in _consumed_port_pairs(stages["tiebreaker"])
    assert ("revise_payload", LOGICAL_REVISE_PAYLOAD) in _consumed_port_pairs(stages["critique"])
    assert ("tiebreaker_payload", LOGICAL_TIEBREAKER_PAYLOAD) in _consumed_port_pairs(stages["critique"])
    assert ("finalize_payload", LOGICAL_FINALIZE_PAYLOAD) in _consumed_port_pairs(stages["execute"])
    assert ("execute_payload", LOGICAL_EXECUTE_PAYLOAD) in _consumed_port_pairs(stages["review"])


def _edge_tuples(edges: tuple[Edge, ...]) -> set[tuple[str, str, str]]:
    """Normalize edges for cross-type comparison (generic vs Megaplan Edge)."""
    return {(e.label, e.target, e.kind) for e in edges}


def test_pattern_built_stages_gain_ports_without_topology_or_step_drift() -> None:
    pipeline = build_pipeline()
    stages = pipeline.stages
    expected_pattern_stages = _expected_pattern_stages()

    for stage_name in ("prep", "critique", "gate", "revise"):
        actual = stages[stage_name]
        expected = expected_pattern_stages[stage_name]
        assert isinstance(actual.step, _NativePhaseStep)
        assert actual.step.name == stage_name
        assert _edge_tuples(actual.edges) == _edge_tuples(expected.edges)

    assert stages["gate"].decision_vocabulary == frozenset(PLANNING_DECISIONS)
    assert stages["gate"].loop_condition is _planning_loop_should_halt
    assert stages["tiebreaker"].decision_vocabulary == frozenset(
        {PLAN_ITERATE, PLAN_PROCEED, PLAN_ESCALATE}
    )
    assert _edge_tuples(stages["tiebreaker"].edges) == _edge_tuples(
        tiebreaker_edges(
            on_iterate="critique",
            on_proceed="finalize",
            on_escalate="finalize",
        )
    )


def test_pattern_builder_function_signatures_are_unchanged() -> None:
    signatures = _canonical_stage_signatures()

    assert tuple(signatures["phase_zero_gate"].parameters) == (
        "step",
        "name",
        "on_pass",
        "on_fail",
        "criteria",
    )
    assert tuple(signatures["critique_revise_gate_loop"].parameters) == (
        "critique_step",
        "gate_step",
        "revise_step",
        "on_proceed",
        "on_iterate",
        "on_tiebreaker",
        "on_escalate",
        "critique_fallback_edges",
        "gate_extra_edges",
        "revise_target",
    )


def test_non_pattern_stages_keep_expected_step_types_and_routing() -> None:
    stages = build_pipeline().stages

    for stage_name in ("plan", "finalize", "execute", "review", "tiebreaker"):
        assert isinstance(stages[stage_name].step, _NativePhaseStep)
        assert stages[stage_name].step.name == stage_name

    assert _edge_tuples(stages["plan"].edges) == _edge_tuples(
        (Edge(label="critique", target="critique"),)
    )
    assert _edge_tuples(stages["finalize"].edges) == _edge_tuples(
        (Edge(label="execute", target="execute"),)
    )
    assert _edge_tuples(stages["execute"].edges) == _edge_tuples(
        (Edge(label="review", target="review"),)
    )
    assert _edge_tuples(stages["review"].edges) == _edge_tuples(
        (Edge(label="review", target="halt"), Edge(label="halt", target="halt"))
    )
