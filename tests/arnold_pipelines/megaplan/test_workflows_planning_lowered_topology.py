from __future__ import annotations

from arnold.workflow.compiler import compile_pipeline
from arnold_pipelines.megaplan.workflows import planning


def _route_targets(routes):
    return {(route.source, route.label): route.target for route in routes}


def _binding_targets(bindings_by_step):
    return {
        (source, binding["label"]): binding["target_ref"]
        for source, bindings in bindings_by_step.items()
        for binding in bindings
    }


def test_build_pipeline_preserves_source_visible_tiebreaker_children_and_rejoins() -> None:
    pipeline = planning.build_pipeline()

    step_ids = [step.id for step in pipeline.steps]
    assert step_ids == [
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "tiebreaker_researcher",
        "tiebreaker_challenger",
        "tiebreaker_synthesis",
        "tiebreaker_decision",
        "finalize",
        "execute",
        "review",
        "halt",
        "override",
    ]

    route_targets = _route_targets(pipeline.routes)
    assert route_targets[("gate", "tiebreaker")] == "tiebreaker_researcher"
    assert route_targets[("tiebreaker_researcher", "default")] == "tiebreaker_challenger"
    assert route_targets[("tiebreaker_challenger", "default")] == "tiebreaker_synthesis"
    assert route_targets[("tiebreaker_synthesis", "default")] == "tiebreaker_decision"
    assert route_targets[("tiebreaker_decision", "iterate")] == "revise"
    assert route_targets[("tiebreaker_decision", "proceed")] == "finalize"
    assert route_targets[("tiebreaker_decision", "escalate")] == "override"

    compile_pipeline(pipeline)


def test_lowered_topology_helpers_report_canonicalized_tiebreaker_routes() -> None:
    topology = planning.lowered_workflow_topology()
    assert "tiebreaker_run" not in topology["steps"]
    assert "tiebreaker_decide" not in topology["steps"]
    assert {
        "tiebreaker_researcher",
        "tiebreaker_challenger",
        "tiebreaker_synthesis",
        "tiebreaker_decision",
    } <= set(topology["steps"])

    bindings = planning.lowered_route_bindings_by_step(
        step_ids={"gate", "tiebreaker_decision"}
    )
    assert _binding_targets(bindings) == {
        ("gate", "proceed"): "finalize",
        ("gate", "iterate"): "revise",
        ("gate", "retry_gate"): "revise",
        ("gate", "reprompt_downgrade"): "revise",
        ("gate", "tiebreaker"): "tiebreaker_researcher",
        ("gate", "escalate"): "override",
        ("gate", "abort"): "halt",
        ("gate", "suspend"): "halt",
        ("gate", "blocked_preflight"): "override",
        ("gate", "force_proceed"): "finalize",
        ("gate", "else"): "finalize",
        ("tiebreaker_decision", "proceed"): "finalize",
        ("tiebreaker_decision", "iterate"): "revise",
        ("tiebreaker_decision", "escalate"): "override",
        ("tiebreaker_decision", "replan"): "revise",
        ("tiebreaker_decision", "else"): "override",
    }

    assert planning.resolve_lowered_route_target_for_signal("gate", "tiebreaker") == "tiebreaker_researcher"
    assert planning.resolve_lowered_route_target_for_signal("tiebreaker_decision", "iterate") == "revise"
