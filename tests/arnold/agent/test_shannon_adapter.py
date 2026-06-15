from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.agent import AgentRequest, ArnoldDispatcher
from arnold.pipelines.megaplan.agent_adapters.shannon import ShannonAdapter


def _request(agent: str = "claude", **overrides) -> AgentRequest:
    data = {
        "agent": agent,
        "mode": "oneshot",
        "model": "opus-4.8",
        "resolved_model": "opus-4.8",
        "effort": "medium",
        "read_only": True,
        "prompt": "Summarise the repo.",
        "system_prompt": "You are concise.",
    }
    data.update(overrides)
    return AgentRequest(**data)


def _fake_worker_result(**overrides):
    from arnold.pipelines.megaplan.workers import WorkerResult

    data = {
        "payload": {"summary": "ok"},
        "raw_output": '{"summary": "ok"}',
        "duration_ms": 5555,
        "cost_usd": 0.0,
        "session_id": "shannon-sess-xyz",
        "trace_output": None,
        "rendered_prompt": "rendered",
        "model_actual": "opus-4.8",
        "prompt_tokens": 20,
        "completion_tokens": 5,
        "total_tokens": 25,
        "shannon_plan": {"kind": "fresh", "session_id": "shannon-sess-xyz"},
    }
    data.update(overrides)
    return WorkerResult(**data)


def test_shannon_adapter_projects_worker_result() -> None:
    with patch(
        "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=lambda *args, **kwargs: _fake_worker_result(),
    ):
        result = ShannonAdapter()(_request())

    assert result.raw_output == '{"summary": "ok"}'
    assert result.payload == {"summary": "ok"}
    assert result.session_id == "shannon-sess-xyz"
    assert result.tokens.total_tokens == 25
    assert result.shannon_plan == {"kind": "fresh", "session_id": "shannon-sess-xyz"}
    assert result.provenance is not None
    assert result.provenance.agent == "claude"


def test_shannon_adapter_synthesizes_oneshot_context(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    captured: dict = {}

    def fake_run_shannon_step(step, state, plan_dir, **kwargs):
        captured["step"] = step
        captured["state"] = state
        captured["kwargs"] = kwargs
        return _fake_worker_result()

    with patch(
        "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=fake_run_shannon_step,
    ):
        ShannonAdapter(session_agent="shannon")(
            _request(agent="shannon", read_only=False, metadata={"work_dir": str(work_dir)})
        )

    assert captured["step"] == "critique"
    assert captured["kwargs"]["fresh"] is True
    assert captured["kwargs"]["read_only"] is False
    assert captured["kwargs"]["model"] == "opus-4.8"
    assert captured["kwargs"]["effort"] == "medium"
    assert captured["kwargs"]["session_agent"] == "shannon"
    assert captured["state"]["sessions"] == {}
    assert captured["state"]["config"]["project_dir"] == str(work_dir.resolve())
    assert "You are concise." in captured["kwargs"]["prompt_override"]
    assert "Summarise the repo." in captured["kwargs"]["prompt_override"]


def test_shannon_adapter_passes_free_text_only_without_output_schema() -> None:
    captured: list[bool] = []

    def fake_run_shannon_step(step, state, plan_dir, **kwargs):
        captured.append(kwargs["free_text"])
        return _fake_worker_result(raw_output="batch([done()])", payload={})

    with patch(
        "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=fake_run_shannon_step,
    ):
        raw_result = ShannonAdapter()(_request(metadata={"toolsets": []}))
        ShannonAdapter()(_request(metadata={"output_schema": {"type": "object"}}))

    assert raw_result.raw_output == "batch([done()])"
    assert captured == [True, False]


def test_shannon_adapter_is_available_delegates() -> None:
    with patch("arnold.pipelines.megaplan._core.is_shannon_available", return_value=True):
        assert ShannonAdapter.is_available() is True
    with patch("arnold.pipelines.megaplan._core.is_shannon_available", return_value=False):
        assert ShannonAdapter.is_available() is False


def test_explicit_dispatcher_routes_claude_and_shannon() -> None:
    dispatcher = ArnoldDispatcher()
    dispatcher.register("claude", ShannonAdapter(session_agent="claude"))
    dispatcher.register("shannon", ShannonAdapter(session_agent="shannon"))
    captured: list[str] = []

    def fake_run_shannon_step(step, state, plan_dir, **kwargs):
        captured.append(kwargs["session_agent"])
        return _fake_worker_result()

    with patch(
        "arnold.pipelines.megaplan.workers.shannon.run_shannon_step",
        side_effect=fake_run_shannon_step,
    ):
        dispatcher.dispatch(_request(agent="claude"))
        dispatcher.dispatch(_request(agent="shannon"))

    assert captured == ["claude", "shannon"]


def test_extract_free_text_result_returns_verbatim_text_and_errors() -> None:
    from arnold.pipelines.megaplan.workers._impl import CliError
    from arnold.pipelines.megaplan.workers.shannon import _extract_free_text_result

    ndjson = "\n".join(
        [
            json.dumps({"type": "system", "subtype": "init", "session_id": "s1"}),
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "result": "batch([done()])",
                    "session_id": "s1",
                    "total_cost_usd": 0.0012,
                }
            ),
        ]
    )

    envelope, text = _extract_free_text_result(ndjson)
    assert text == "batch([done()])"
    assert envelope["session_id"] == "s1"
    assert envelope["total_cost_usd"] == 0.0012

    err_ndjson = "\n".join(
        [
            json.dumps({"type": "system", "subtype": "init"}),
            json.dumps({"type": "result", "is_error": True, "result": "Not logged in / /login"}),
        ]
    )
    with pytest.raises(CliError, match="Shannon step failed"):
        _extract_free_text_result(err_ndjson)
