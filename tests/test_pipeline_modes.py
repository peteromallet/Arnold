"""Mode-specific work now lives in first-class pipelines."""

from __future__ import annotations

from arnold.pipelines.megaplan._pipeline.registry import get_pipeline, registered_pipelines


EXPECTED_PLANNING_STAGES = {
    "prep", "plan", "critique", "gate", "revise",
    "finalize", "execute", "review", "tiebreaker",
}


def test_planning_pipeline_is_mode_neutral() -> None:
    pipeline = get_pipeline("planning")
    assert set(pipeline.stages.keys()) == EXPECTED_PLANNING_STAGES
    assert pipeline.entry == "prep"
    assert pipeline.overlays == ()


def test_doc_and_creative_are_registered_as_first_class_pipelines() -> None:
    names = set(registered_pipelines())
    assert {"doc", "creative"}.issubset(names)

    assert tuple(get_pipeline("doc").stages) == (
        "outline",
        "section_drafts",
        "critique",
        "revise",
        "assembly",
    )
    assert tuple(get_pipeline("creative").stages) == (
        "prep",
        "execute_creative",
        "critique_creative",
        "revise_creative",
        "finalize",
    )
