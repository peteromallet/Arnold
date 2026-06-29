from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.agent import AgentRequest, ArnoldDispatcher
from arnold_pipelines.megaplan.agent_adapters.codex import CodexAdapter


def _request(**overrides) -> AgentRequest:
    data = {
        "agent": "codex",
        "mode": "oneshot",
        "model": "gpt-5.5",
        "resolved_model": "gpt-5.5",
        "effort": "low",
        "read_only": True,
        "prompt": "What is 2 + 2?",
        "system_prompt": "You are a calculator.",
    }
    data.update(overrides)
    return AgentRequest(**data)


def _fake_worker_result(**overrides):
    from arnold_pipelines.megaplan.workers import WorkerResult

    data = {
        "payload": {"answer": "4"},
        "raw_output": '{"answer": "4"}',
        "duration_ms": 1234,
        "cost_usd": 0.0021,
        "session_id": "codex-sess-abc",
        "trace_output": None,
        "rendered_prompt": "rendered",
        "model_actual": "gpt-5.5",
        "prompt_tokens": 11,
        "completion_tokens": 3,
        "total_tokens": 14,
    }
    data.update(overrides)
    return WorkerResult(**data)


def test_codex_adapter_projects_worker_result() -> None:
    with patch(
        "arnold_pipelines.megaplan.workers.run_codex_step",
        side_effect=lambda *args, **kwargs: _fake_worker_result(),
    ):
        result = CodexAdapter()(_request())

    assert result.raw_output == '{"answer": "4"}'
    assert result.payload == {"answer": "4"}
    assert result.session_id == "codex-sess-abc"
    assert result.cost.cost_usd == pytest.approx(0.0021)
    assert result.tokens.total_tokens == 14
    assert result.provenance is not None
    assert result.provenance.agent == "codex"
    assert result.provenance.mode == "oneshot"


def test_codex_adapter_synthesizes_oneshot_context(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    captured: dict = {}

    def fake_run_codex_step(step, state, plan_dir, **kwargs):
        captured["step"] = step
        captured["state"] = state
        captured["plan_dir"] = plan_dir
        captured["kwargs"] = kwargs
        return _fake_worker_result()

    with patch(
        "arnold_pipelines.megaplan.workers.run_codex_step",
        side_effect=fake_run_codex_step,
    ):
        CodexAdapter()(_request(read_only=False, metadata={"work_dir": str(work_dir)}))

    assert captured["step"] == "critique"
    assert captured["kwargs"]["persistent"] is False
    assert captured["kwargs"]["fresh"] is True
    assert captured["kwargs"]["read_only"] is False
    assert captured["kwargs"]["model"] == "gpt-5.5"
    assert captured["kwargs"]["effort"] == "low"
    assert captured["state"]["sessions"] == {}
    assert captured["state"]["config"]["project_dir"] == str(work_dir.resolve())
    assert "You are a calculator." in captured["kwargs"]["prompt_override"]
    assert "What is 2 + 2?" in captured["kwargs"]["prompt_override"]


def test_codex_adapter_passes_free_text_only_without_output_schema() -> None:
    captured: list[bool] = []

    def fake_run_codex_step(step, state, plan_dir, **kwargs):
        captured.append(kwargs["free_text"])
        return _fake_worker_result(raw_output="batch([done()])", payload={})

    with patch(
        "arnold_pipelines.megaplan.workers.run_codex_step",
        side_effect=fake_run_codex_step,
    ):
        raw_result = CodexAdapter()(_request(metadata={"toolsets": []}))
        CodexAdapter()(_request(metadata={"output_schema": {"type": "object"}}))

    assert raw_result.raw_output == "batch([done()])"
    assert captured == [True, False]


def test_explicit_dispatcher_routes_codex_adapter() -> None:
    dispatcher = ArnoldDispatcher()
    dispatcher.register("codex", CodexAdapter())

    with patch(
        "arnold_pipelines.megaplan.workers.run_codex_step",
        side_effect=lambda *args, **kwargs: _fake_worker_result(session_id="X"),
    ):
        result = dispatcher.dispatch(_request())

    assert result.session_id == "X"


def test_run_codex_step_free_text_omits_output_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan._core import ensure_runtime_layout
    from arnold_pipelines.megaplan.workers import _impl

    root = tmp_path / "root"
    root.mkdir()
    ensure_runtime_layout(root)
    plan_dir = root / ".megaplan" / "plans" / "oneshot"
    plan_dir.mkdir(parents=True, exist_ok=True)
    output_path = plan_dir / "out.txt"
    state = {
        "name": "free-text",
        "idea": "x",
        "current_state": "critiqued",
        "iteration": 0,
        "created_at": "1970-01-01T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
    }
    captured: dict = {}

    def fake_run_command(command, **kwargs):
        captured["command"] = list(command)
        output_path.write_text("batch([done()])", encoding="utf-8")
        return _impl.CommandResult(
            command=list(command),
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=5,
        )

    monkeypatch.setattr(_impl, "run_command", fake_run_command)
    monkeypatch.setattr(
        _impl, "_codex_step_cost", lambda *args, **kwargs: (0.0, 0, 0, "gpt-5.5", None)
    )

    result = _impl.run_codex_step(
        "critique",
        state,
        plan_dir,
        root=root,
        persistent=False,
        fresh=True,
        read_only=True,
        output_path=output_path,
        prompt_override="Return a fenced call.",
        free_text=True,
    )

    assert "--output-schema" not in captured["command"]
    assert result.payload == {}
    assert result.raw_output == "batch([done()])"


def test_run_command_reads_prompt_file_path_as_file_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.workers import _impl

    prompt_path = tmp_path / "gate-prompt.txt"
    prompt_path.write_text("Stage: gate\nEvaluate the actual prompt.\n", encoding="utf-8")
    captured: dict[str, str] = {}

    def fake_subprocess_run(command, stdin, **kwargs):
        assert stdin is not None
        captured["stdin"] = stdin.read().decode("utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(_impl.subprocess, "run", fake_subprocess_run)

    result = _impl.run_command(
        ["codex", "exec", "-"],
        cwd=tmp_path,
        stdin_text=str(prompt_path),
    )

    assert result.returncode == 0
    assert captured["stdin"] == prompt_path.read_text(encoding="utf-8")
    assert captured["stdin"] != str(prompt_path)


def test_run_codex_step_read_only_trusted_container_bypasses_inner_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan._core import ensure_runtime_layout
    from arnold_pipelines.megaplan.workers import _impl

    root = tmp_path / "root"
    root.mkdir()
    ensure_runtime_layout(root)
    plan_dir = root / ".megaplan" / "plans" / "oneshot"
    plan_dir.mkdir(parents=True, exist_ok=True)
    output_path = plan_dir / "out.json"
    state = {
        "name": "trusted-read-only",
        "idea": "x",
        "current_state": "critiqued",
        "iteration": 0,
        "created_at": "1970-01-01T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
    }
    captured: dict = {}

    def fake_run_command(command, **kwargs):
        captured["command"] = list(command)
        output_path.write_text('{"checks":[],"flags":[]}', encoding="utf-8")
        return _impl.CommandResult(
            command=list(command),
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=5,
        )

    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    monkeypatch.setattr(_impl, "run_command", fake_run_command)
    monkeypatch.setattr(
        _impl, "_codex_step_cost", lambda *args, **kwargs: (0.0, 0, 0, "gpt-5.5", None)
    )

    _impl.run_codex_step(
        "critique",
        state,
        plan_dir,
        root=root,
        persistent=False,
        fresh=True,
        read_only=True,
        output_path=output_path,
        prompt_override="Return an empty critique payload.",
    )

    assert "--dangerously-bypass-approvals-and-sandbox" in captured["command"]
    assert "sandbox_mode='read-only'" not in captured["command"]
