"""Tests for :class:`arnold.agent.adapters.codex.CodexAdapter`.

Deterministic and offline: the real ``run_codex_step`` worker is either
replaced wholesale (projection / arg-synthesis tests) or driven with a mocked
``run_command`` (real-worker-path test) so no codex CLI ever launches.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.agent import ArnoldDispatcher, CodexAdapter, dispatch
from arnold.agent.contracts import AgentRequest


def _request(**overrides) -> AgentRequest:
    base = dict(
        agent="codex",
        mode="oneshot",
        model="gpt-5.5",
        resolved_model="gpt-5.5",
        effort="low",
        read_only=True,
        prompt="What is 2 + 2?",
        system_prompt="You are a calculator.",
    )
    base.update(overrides)
    return AgentRequest(**base)


def _fake_worker_result(**overrides):
    from arnold.pipelines.megaplan.workers import WorkerResult

    base = dict(
        payload={"answer": "4"},
        raw_output='{"answer": "4"}',
        duration_ms=1234,
        cost_usd=0.0021,
        session_id="codex-sess-abc",
        trace_output=None,
        rendered_prompt="rendered",
        model_actual="gpt-5.5",
        prompt_tokens=11,
        completion_tokens=3,
        total_tokens=14,
    )
    base.update(overrides)
    return WorkerResult(**base)


def test_codex_adapter_projects_worker_result_to_agent_result() -> None:
    captured: dict = {}

    def fake_run_codex_step(step, state, plan_dir, **kwargs):
        captured["step"] = step
        captured["state"] = state
        captured["plan_dir"] = plan_dir
        captured["kwargs"] = kwargs
        return _fake_worker_result()

    with patch(
        "arnold.pipelines.megaplan.workers.run_codex_step",
        side_effect=fake_run_codex_step,
    ):
        result = CodexAdapter()(_request())

    # Projection: every telemetry field survives the WorkerResult -> AgentResult bridge.
    assert result.raw_output == '{"answer": "4"}'
    assert result.payload == {"answer": "4"}
    assert result.session_id == "codex-sess-abc"
    assert result.cost.cost_usd == pytest.approx(0.0021)
    assert result.cost_usd == pytest.approx(0.0021)
    assert result.model_actual == "gpt-5.5"
    assert result.tokens.prompt_tokens == 11
    assert result.tokens.completion_tokens == 3
    assert result.tokens.total_tokens == 14
    assert result.duration_ms == 1234
    # Provenance carries the request triple.
    assert result.provenance is not None
    assert result.provenance.agent == "codex"
    assert result.provenance.mode == "oneshot"
    assert result.provenance.model == "gpt-5.5"
    assert result.provenance.session_id == "codex-sess-abc"


def test_codex_adapter_synthesizes_oneshot_context() -> None:
    captured: dict = {}

    def fake_run_codex_step(step, state, plan_dir, **kwargs):
        captured["step"] = step
        captured["state"] = state
        captured["kwargs"] = kwargs
        return _fake_worker_result()

    with patch(
        "arnold.pipelines.megaplan.workers.run_codex_step",
        side_effect=fake_run_codex_step,
    ):
        CodexAdapter()(_request())

    # Fresh, non-persistent, one-shot.
    assert captured["kwargs"]["fresh"] is True
    assert captured["kwargs"]["persistent"] is False
    assert captured["kwargs"]["read_only"] is True
    assert captured["kwargs"]["model"] == "gpt-5.5"
    assert captured["kwargs"]["effort"] == "low"
    # system_prompt is folded into the override prompt.
    assert "You are a calculator." in captured["kwargs"]["prompt_override"]
    assert "What is 2 + 2?" in captured["kwargs"]["prompt_override"]
    # Empty sessions => every call is treated as fresh.
    assert captured["state"]["sessions"] == {}


def test_codex_adapter_read_only_vs_write_work_dir(tmp_path: Path) -> None:
    work_dir = tmp_path / "wd"
    work_dir.mkdir()
    captured: dict = {}

    def fake_run_codex_step(step, state, plan_dir, **kwargs):
        captured["read_only"] = kwargs["read_only"]
        captured["project_dir"] = state["config"]["project_dir"]
        return _fake_worker_result()

    with patch(
        "arnold.pipelines.megaplan.workers.run_codex_step",
        side_effect=fake_run_codex_step,
    ):
        # write mode + explicit work_dir
        CodexAdapter()(
            _request(read_only=False, metadata={"work_dir": str(work_dir)})
        )

    assert captured["read_only"] is False
    assert captured["project_dir"] == str(work_dir.resolve())


def test_codex_adapter_real_worker_path_mock_shortcut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive the *genuine* ``run_codex_step`` (no wholesale stub) via the
    in-process mock-worker shortcut (``MEGAPLAN_MOCK_WORKERS=1``).

    This proves the synthesized one-shot context (ephemeral PlanState +
    plan_dir + ``ensure_runtime_layout`` schema root) actually satisfies the
    real worker's entry path — env/layout/state lookups, schema load, and the
    ``WorkerResult`` -> ``AgentResult`` projection — without launching a codex
    CLI. No ``run_command`` is invoked on this path.
    """
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    result = CodexAdapter()(_request())
    # mock_worker_output returns a schema-valid synthetic payload for the step.
    assert isinstance(result.payload, dict)
    assert result.raw_output  # non-empty synthetic output


def test_default_dispatcher_routes_codex() -> None:
    with patch(
        "arnold.pipelines.megaplan.workers.run_codex_step",
        side_effect=lambda *a, **k: _fake_worker_result(),
    ):
        result = dispatch(_request())
    assert result.session_id == "codex-sess-abc"


def test_explicit_dispatcher_register_and_route() -> None:
    disp = ArnoldDispatcher()
    disp.register("codex", CodexAdapter())
    with patch(
        "arnold.pipelines.megaplan.workers.run_codex_step",
        side_effect=lambda *a, **k: _fake_worker_result(session_id="X"),
    ):
        result = disp.dispatch(_request())
    assert result.session_id == "X"
