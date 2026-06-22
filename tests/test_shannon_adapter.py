"""Tests for :class:`arnold.agent.adapters.shannon.ShannonAdapter`.

Deterministic and offline: the real ``run_shannon_step`` worker is replaced
wholesale so no tmux session, claude CLI, or vendored-bun process ever runs.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.agent import ArnoldDispatcher, ShannonAdapter, dispatch
from arnold.agent.contracts import AgentRequest


def _request(agent: str = "claude", **overrides) -> AgentRequest:
    base = dict(
        agent=agent,
        mode="oneshot",
        model="opus-4.8",
        resolved_model="opus-4.8",
        effort="medium",
        read_only=True,
        prompt="Summarise the repo.",
        system_prompt="You are concise.",
    )
    base.update(overrides)
    return AgentRequest(**base)


def _fake_worker_result(**overrides):
    from arnold_pipelines.megaplan.workers import WorkerResult

    base = dict(
        payload={"summary": "ok"},
        raw_output='{"summary": "ok"}',
        duration_ms=5555,
        cost_usd=0.0,
        session_id="shannon-sess-xyz",
        trace_output=None,
        rendered_prompt="rendered",
        model_actual="opus-4.8",
        prompt_tokens=20,
        completion_tokens=5,
        total_tokens=25,
        shannon_plan={"kind": "fresh", "session_id": "shannon-sess-xyz"},
    )
    base.update(overrides)
    return WorkerResult(**base)


def test_shannon_adapter_projects_worker_result() -> None:
    with patch(
        "arnold_pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=lambda *a, **k: _fake_worker_result(),
    ):
        result = ShannonAdapter()(_request())

    assert result.raw_output == '{"summary": "ok"}'
    assert result.payload == {"summary": "ok"}
    assert result.session_id == "shannon-sess-xyz"
    assert result.cost.cost_usd == 0.0
    assert result.model_actual == "opus-4.8"
    assert result.tokens.total_tokens == 25
    assert result.duration_ms == 5555
    # shannon_plan survives the bridge.
    assert result.shannon_plan == {"kind": "fresh", "session_id": "shannon-sess-xyz"}
    assert result.provenance is not None
    assert result.provenance.agent == "claude"
    assert result.provenance.session_id == "shannon-sess-xyz"


def test_shannon_adapter_synthesizes_oneshot_context() -> None:
    captured: dict = {}

    def fake_run_shannon_step(step, state, plan_dir, **kwargs):
        captured["step"] = step
        captured["state"] = state
        captured["kwargs"] = kwargs
        return _fake_worker_result()

    with patch(
        "arnold_pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=fake_run_shannon_step,
    ):
        ShannonAdapter(session_agent="claude")(_request())

    assert captured["kwargs"]["fresh"] is True
    assert captured["kwargs"]["read_only"] is True
    assert captured["kwargs"]["model"] == "opus-4.8"
    assert captured["kwargs"]["effort"] == "medium"
    assert captured["kwargs"]["session_agent"] == "claude"
    assert "You are concise." in captured["kwargs"]["prompt_override"]
    assert "Summarise the repo." in captured["kwargs"]["prompt_override"]
    assert captured["state"]["sessions"] == {}


def test_shannon_adapter_read_only_vs_write_work_dir(tmp_path: Path) -> None:
    work_dir = tmp_path / "wd"
    work_dir.mkdir()
    captured: dict = {}

    def fake_run_shannon_step(step, state, plan_dir, **kwargs):
        captured["read_only"] = kwargs["read_only"]
        captured["project_dir"] = state["config"]["project_dir"]
        return _fake_worker_result()

    with patch(
        "arnold_pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=fake_run_shannon_step,
    ):
        ShannonAdapter()(
            _request(read_only=False, metadata={"work_dir": str(work_dir)})
        )

    assert captured["read_only"] is False
    assert captured["project_dir"] == str(work_dir.resolve())


def test_shannon_adapter_session_agent_default_and_override() -> None:
    captured: dict = {}

    def fake_run_shannon_step(step, state, plan_dir, **kwargs):
        captured.setdefault("agents", []).append(kwargs["session_agent"])
        return _fake_worker_result()

    with patch(
        "arnold_pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=fake_run_shannon_step,
    ):
        ShannonAdapter()(_request())  # default -> "claude"
        ShannonAdapter(session_agent="shannon")(_request(agent="shannon"))

    assert captured["agents"] == ["claude", "shannon"]


def test_shannon_adapter_is_available_delegates() -> None:
    with patch(
        "arnold_pipelines.megaplan._core.is_shannon_available",
        return_value=True,
    ):
        assert ShannonAdapter.is_available() is True
    with patch(
        "arnold_pipelines.megaplan._core.is_shannon_available",
        return_value=False,
    ):
        assert ShannonAdapter.is_available() is False


def test_default_dispatcher_routes_claude_and_shannon() -> None:
    captured: dict = {}

    def fake_run_shannon_step(step, state, plan_dir, **kwargs):
        captured.setdefault("agents", []).append(kwargs["session_agent"])
        return _fake_worker_result()

    with patch(
        "arnold_pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=fake_run_shannon_step,
    ):
        r_claude = dispatch(_request(agent="claude"))
        r_shannon = dispatch(_request(agent="shannon"))

    assert r_claude.session_id == "shannon-sess-xyz"
    assert r_shannon.session_id == "shannon-sess-xyz"
    # claude routes session_agent="claude"; shannon routes session_agent="shannon".
    assert captured["agents"] == ["claude", "shannon"]


def test_shannon_adapter_real_worker_path_mock_shortcut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive the *genuine* ``run_shannon_step`` via the in-process mock-worker
    shortcut (``MEGAPLAN_MOCK_WORKERS=1``) — no tmux/claude/bun process runs —
    proving the synthesized one-shot context satisfies the real worker entry."""
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    result = ShannonAdapter()(_request())
    assert isinstance(result.payload, dict)
    assert result.raw_output


def test_explicit_dispatcher_register_and_route() -> None:
    disp = ArnoldDispatcher()
    disp.register("claude", ShannonAdapter(session_agent="claude"))
    with patch(
        "arnold_pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=lambda *a, **k: _fake_worker_result(session_id="Y"),
    ):
        result = disp.dispatch(_request())
    assert result.session_id == "Y"
