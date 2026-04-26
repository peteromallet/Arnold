"""Tests for the family-aware ``--prompt``/``--steps`` enforcement in ``vibecomfy run``.

When a user passes ``--prompt`` or ``--steps`` against a workflow whose nodes
have not been registered as eligible targets (typically WanVideoWrapper, ACE
Step audio, or any other custom-node family whose textual fields mean
something other than "free-form image prompt"), the CLI must error loudly
rather than silently no-op or mutate the wrong field.
"""

from __future__ import annotations

import argparse
import types

import pytest

from vibecomfy.commands.run import _cmd_run
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _make_args(**overrides) -> argparse.Namespace:
    base = dict(
        path="some/workflow",
        ready=False,
        runtime="embedded",
        server_url=None,
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _no_inputs_workflow(workflow_id: str = "wan-wrapper") -> VibeWorkflow:
    """A workflow whose only nodes are NOT in the prompt/steps allowlist.

    This mirrors WanVideoWrapper or ACE Step audio graphs after
    ``finalize_metadata`` runs: the registration step refuses to map
    ``--prompt``/``--steps`` to any of the custom-node text/sampler fields,
    so the universal CLI overrides have no eligible target.
    """
    workflow = VibeWorkflow(workflow_id, WorkflowSource(workflow_id))
    workflow.nodes["1"] = VibeNode(
        "1",
        "WanVideoTextEncode",
        inputs={"text": "source-authored prompt"},
    )
    workflow.nodes["2"] = VibeNode(
        "2",
        "WanVideoSampler",
        inputs={"steps": 20, "seed": 7},
    )
    workflow.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "out"})
    # Note: workflow.inputs is intentionally empty — convert_to_vibe_format
    # would produce the same shape via _register_common_inputs.
    return workflow


def _image_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("img", WorkflowSource("img"))
    workflow.nodes["1"] = VibeNode("1", "CLIPTextEncode", inputs={"text": "old"})
    workflow.nodes["2"] = VibeNode(
        "2",
        "KSampler",
        inputs={"seed": 1, "steps": 4},
    )
    workflow.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "out"})
    workflow.finalize_metadata()
    return workflow


def _stub_run(monkeypatch: pytest.MonkeyPatch, workflow: VibeWorkflow) -> list[VibeWorkflow]:
    runs: list[VibeWorkflow] = []

    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.get_schema_provider",
        lambda prefer, *, server_url=None: object(),
    )
    monkeypatch.setattr(
        "vibecomfy.commands.run.load_workflow_reference",
        lambda *args, **kwargs: workflow,
    )

    def fake_run_embedded_sync(wf: VibeWorkflow, *, backend: str):
        runs.append(wf)
        return types.SimpleNamespace(
            run_id="r",
            prompt_id="p",
            outputs=[],
            metadata_path="m.json",
            log_path="l.log",
        )

    monkeypatch.setattr("vibecomfy.commands.run.run_embedded_sync", fake_run_embedded_sync)
    return runs


def test_cmd_run_errors_when_prompt_supplied_without_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _no_inputs_workflow("wan-wrapper")
    runs = _stub_run(monkeypatch, workflow)

    rc = _cmd_run(_make_args(prompt="anything"))

    assert rc == 2
    assert runs == []
    err = capsys.readouterr().err
    assert "wan-wrapper" in err
    assert "--prompt" in err
    assert "PROMPT_NODE_CLASSES" in err


def test_cmd_run_errors_when_steps_supplied_without_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _no_inputs_workflow("ace-audio")
    runs = _stub_run(monkeypatch, workflow)

    rc = _cmd_run(_make_args(steps=4))

    assert rc == 2
    assert runs == []
    err = capsys.readouterr().err
    assert "ace-audio" in err
    assert "--steps" in err
    assert "STEPS_NODE_CLASSES" in err


def test_cmd_run_seed_remains_universal_for_unwired_overrides(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _no_inputs_workflow("wan-wrapper")
    runs = _stub_run(monkeypatch, workflow)

    # --seed alone (no --prompt/--steps) must succeed even when prompt/steps
    # would have been refused.
    rc = _cmd_run(_make_args(seed=123))

    assert rc == 0
    assert runs == [workflow]
    assert capsys.readouterr().err == ""


def test_cmd_run_applies_prompt_and_steps_for_image_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = _image_workflow()
    runs = _stub_run(monkeypatch, workflow)

    rc = _cmd_run(_make_args(prompt="a red cube", steps=8, seed=42))

    assert rc == 0
    assert runs == [workflow]
    assert workflow.nodes["1"].inputs["text"] == "a red cube"
    assert workflow.nodes["2"].inputs["steps"] == 8
    assert workflow.nodes["2"].inputs["seed"] == 42
