from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from arnold.control.interface import ControlTransition
from arnold_pipelines.megaplan.handlers.override import _override_set_model
from arnold_pipelines.megaplan.planning.control_binding import (
    planning_control_binding,
    planning_run_state_view,
)
from arnold_pipelines.megaplan.types import CliError


def _state(root: Path) -> dict:
    return {
        "name": "demo",
        "current_state": "planned",
        "iteration": 1,
        "config": {
            "project_dir": str(root),
            "profile": "partnered-5",
            "phase_model": ["critique_evaluator=codex:gpt-5.5"],
            "tier_models": {
                "critique_evaluator": {"5": "codex:gpt-5.5"},
                "critique": {"5": "codex:gpt-5.5"},
            },
        },
        "meta": {},
        "history": [],
        "plan_versions": [],
        "last_gate": {},
    }


def test_legacy_set_model_persists_full_hermes_evaluator_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.handlers.override.save_state_merge_meta",
        lambda *args, **kwargs: None,
    )

    response = _override_set_model(
        tmp_path,
        tmp_path,
        state,
        argparse.Namespace(
            phase="critique_evaluator",
            model="hermes:zhipu:glm-5.2",
            effort=None,
            reason="pin evaluator",
        ),
    )

    assert response["success"] is True
    assert response["new_spec"] == "hermes:zhipu:glm-5.2"
    assert state["config"]["phase_model"] == [
        "critique_evaluator=hermes:zhipu:glm-5.2"
    ]
    assert "critique_evaluator" not in state["config"]["tier_models"]
    assert "critique" in state["config"]["tier_models"]


def test_control_set_model_persists_full_hermes_evaluator_spec(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)

    result = planning_control_binding().apply_transition(
        planning_run_state_view(state),
        ControlTransition(
            op="override",
            target_id="set-model",
            payload={
                "phase": "critique_evaluator",
                "model": "hermes:zhipu:glm-5.2",
                "reason": "pin evaluator",
            },
        ),
    )

    assert result.accepted is True
    config = next(delta.value for delta in result.state_deltas if delta.key == "config")
    assert config["phase_model"] == [
        "critique_evaluator=hermes:zhipu:glm-5.2"
    ]
    assert "critique_evaluator" not in config["tier_models"]
    assert "critique" in config["tier_models"]


@pytest.mark.parametrize("agent", ["hermes", "shannon"])
def test_nonpremium_model_override_rejects_separate_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    agent: str,
) -> None:
    state = _state(tmp_path)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.handlers.override.save_state_merge_meta",
        lambda *args, **kwargs: None,
    )

    with pytest.raises(CliError, match="only supported for claude/codex"):
        _override_set_model(
            tmp_path,
            tmp_path,
            state,
            argparse.Namespace(
                phase="critique_evaluator",
                model=f"{agent}:provider:model",
                effort="high",
                reason="invalid split",
            ),
        )
