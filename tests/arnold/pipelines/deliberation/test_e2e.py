from __future__ import annotations

from arnold.pipeline.types import ParallelStage, Stage

from arnold.pipelines.deliberation.pipelines import (
    _build_graph_pipeline,
    _build_initial_pipeline,
)


def _fake_worker(**_: object) -> str:
    return "{}"


def test_build_initial_pipeline_uses_descriptive_stage_names_and_routes() -> None:
    profile = {
        "question_gen": "worker",
        "draft_plan": "worker",
        "layer_high_panel": "high",
        "layer_high_synth": "worker",
        "layer_mid_panel": "mid",
        "layer_mid_synth": "worker",
        "layer_low_panel": "low",
        "layer_low_synth": "worker",
        "final_report": "worker",
    }
    pipeline = _build_initial_pipeline(profile=profile, workers={"worker": _fake_worker})

    assert pipeline.entry == "question_gen"
    assert list(pipeline.stages) == [
        "question_gen",
        "human_gate",
        "draft_plan",
        "layer_high_panel",
        "layer_high_synth",
        "layer_mid_panel",
        "layer_mid_synth",
        "layer_low_panel",
        "layer_low_synth",
        "final_report",
    ]

    human_gate = pipeline.stages["human_gate"]
    assert isinstance(human_gate, Stage)
    assert human_gate.edges[0].label == "answers_collected"
    assert human_gate.edges[0].target == "draft_plan"

    high_panel = pipeline.stages["layer_high_panel"]
    assert isinstance(high_panel, ParallelStage)
    assert high_panel.edges[0].target == "layer_high_synth"
    assert all(step.name.startswith("layer_high_panel.") for step in high_panel.steps)

    final_report = pipeline.stages["final_report"]
    assert isinstance(final_report, Stage)
    assert final_report.edges[0].target == "halt"


def test_private_graph_pipeline_requires_profile_and_workers() -> None:
    try:
        _build_graph_pipeline()
    except ValueError as exc:
        assert "Provide 'profile' and 'workers'" in str(exc)
    else:
        raise AssertionError("expected missing profile/workers to fail")
