from __future__ import annotations

from types import SimpleNamespace

from vibecomfy.comfy_nodes.agent.edit import (
    _direct_existing_parameter_tweak_feedback,
)


def _state(*, task: str, graph: dict) -> SimpleNamespace:
    return SimpleNamespace(
        task=task,
        graph=graph,
        request_payload={"query": task},
    )


def test_direct_existing_parameter_tweak_feedback_triggers_for_visible_existing_widgets() -> None:
    state = _state(
        task="Increase frame count and adjust frame rate to keep motion smooth.",
        graph={
            "nodes": {
                "34": {
                    "id": "34",
                    "class_type": "MoonvalleyImg2VideoNode",
                    "inputs": {},
                    "widgets": {"widget_3": 7, "widget_6": 100},
                }
            }
        },
    )

    feedback = _direct_existing_parameter_tweak_feedback(
        state,
        "I could not find a workflow precedent or installed/provisional node schema.",
    )

    assert "Direct existing-node tweak fallback applies here" in feedback
    assert "MoonvalleyImg2VideoNode [34]" in feedback
    assert "widget_N" in feedback


def test_direct_existing_parameter_tweak_feedback_skips_non_parameter_requests() -> None:
    state = _state(
        task="Replace the current workflow with a completely different architecture.",
        graph={
            "nodes": {
                "3": {
                    "id": "3",
                    "class_type": "TripoTextToModelNode",
                    "inputs": {},
                    "widgets": {"widget_9": "detailed"},
                }
            }
        },
    )

    feedback = _direct_existing_parameter_tweak_feedback(
        state,
        "I could not find a workflow precedent or installed/provisional node schema.",
    )

    assert feedback == ""
