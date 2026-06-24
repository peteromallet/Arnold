from __future__ import annotations

from arnold.pipeline.contracts import RepairGradient, bind
from arnold.pipelines.megaplan.pipeline import build_pipeline
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


def _edge_map(pipeline) -> dict[str, tuple[str, ...]]:
    stage_names = set(pipeline.stages)
    return {
        stage_name: tuple(
            edge.target for edge in stage.edges if edge.target in stage_names
        )
        for stage_name, stage in pipeline.stages.items()
    }


def test_build_pipeline_declares_non_empty_enriched_stage_ports() -> None:
    pipeline = build_pipeline()
    stages = pipeline.stages

    assert stages["prep"].produces[0].name == "prep_payload"
    assert stages["prep"].produces[0].logical_type == LOGICAL_PREP_PAYLOAD

    assert stages["plan"].consumes[0].port_name == "prep_payload"
    assert stages["plan"].consumes[0].logical_type == LOGICAL_PREP_PAYLOAD
    assert stages["plan"].produces[0].name == "plan_payload"
    assert stages["plan"].produces[0].logical_type == LOGICAL_PLAN_PAYLOAD

    critique_inputs = {port.port_name: port.logical_type for port in stages["critique"].consumes}
    assert critique_inputs == {
        "plan_payload": LOGICAL_PLAN_PAYLOAD,
        "revise_payload": LOGICAL_REVISE_PAYLOAD,
        "tiebreaker_payload": LOGICAL_TIEBREAKER_PAYLOAD,
    }
    assert stages["critique"].produces[0].name == "critique_payload"
    assert stages["critique"].produces[0].logical_type == LOGICAL_CRITIQUE_PAYLOAD

    for stage_name, expected_logical_type in (
        ("gate", LOGICAL_GATE_PAYLOAD),
        ("revise", LOGICAL_REVISE_PAYLOAD),
        ("finalize", LOGICAL_FINALIZE_PAYLOAD),
        ("execute", LOGICAL_EXECUTE_PAYLOAD),
        ("review", LOGICAL_REVIEW_PAYLOAD),
        ("tiebreaker", LOGICAL_TIEBREAKER_PAYLOAD),
    ):
        stage = stages[stage_name]
        assert stage.consumes
        assert stage.produces
        assert stage.produces[0].logical_type == expected_logical_type


def test_build_pipeline_explicitly_represents_branch_and_loop_seam_pairs() -> None:
    pipeline = build_pipeline()
    stages = pipeline.stages

    gate_consumers = {"revise", "finalize", "tiebreaker"}
    for stage_name in gate_consumers:
        consume = stages[stage_name].consumes[0]
        assert consume.port_name == "gate_payload"
        assert consume.logical_type == LOGICAL_GATE_PAYLOAD

    tiebreaker_to_critique = {
        port.port_name: port.logical_type for port in stages["critique"].consumes
    }
    assert tiebreaker_to_critique["tiebreaker_payload"] == LOGICAL_TIEBREAKER_PAYLOAD
    assert tiebreaker_to_critique["revise_payload"] == LOGICAL_REVISE_PAYLOAD


def test_build_pipeline_stage_ports_expose_loop_seams_even_when_static_bind_stops_at_backedge() -> None:
    pipeline = build_pipeline()

    result = bind(pipeline.stages, _edge_map(pipeline), typed_ports=True)

    assert isinstance(result, RepairGradient)
    assert result.error_kind == "no_match"
    assert result.wanted.port_name in {"revise_payload", "tiebreaker_payload"}
