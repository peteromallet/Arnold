from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
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


def test_run_codex_step_plan_prefers_json_payload_over_transcript_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from arnold_pipelines.megaplan._core import ensure_runtime_layout
    from arnold_pipelines.megaplan.workers import _impl

    root = tmp_path / "root"
    root.mkdir()
    ensure_runtime_layout(root)
    plan_dir = root / ".megaplan" / "plans" / "oneshot"
    plan_dir.mkdir(parents=True, exist_ok=True)
    output_path = plan_dir / "plan.json"
    state = {
        "name": "json-plan-transcript",
        "idea": "x",
        "current_state": "prepped",
        "iteration": 0,
        "created_at": "1970-01-01T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
    }
    plan_payload = {
        "plan": (
            "# Implementation Plan: Demo\n\n"
            "## Overview\n\n"
            "Ship the native-first contract.\n\n"
            "## Phase 1: Patch Worker Parsing\n\n"
            "### Step 1: Parse the structured plan payload (`arnold_pipelines/megaplan/workers/_impl.py`)\n"
            "1. Recover the JSON `plan` object before treating the transcript as markdown.\n\n"
            "## Validation Order\n\n"
            "1. Run `pytest tests/arnold/agent/test_codex_adapter.py -q`.\n"
        ),
        "questions": [],
        "success_criteria": [{"criterion": "Plan capture succeeds", "priority": "must"}],
        "assumptions": [],
    }

    def fake_run_command(command, **kwargs):
        del command, kwargs
        output_path.write_text(
            json.dumps(plan_payload)
            + "\nOpenAI Codex v0.142.2\n--------\ntrailing transcript noise\n",
            encoding="utf-8",
        )
        return _impl.CommandResult(
            command=["codex"],
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
        "plan",
        state,
        plan_dir,
        root=root,
        persistent=False,
        fresh=True,
        read_only=False,
        output_path=output_path,
        prompt_override="Return a structured plan payload.",
    )

    assert result.payload["plan"] == plan_payload["plan"]
    assert result.payload["success_criteria"][0]["criterion"] == "Plan capture succeeds"


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


def test_run_codex_step_normalizes_prompt_file_path_before_dispatch(
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
    prompt_path = tmp_path / "gate-prompt.txt"
    prompt_path.write_text("Stage: gate\nUse the actual prompt text.\n", encoding="utf-8")
    state = {
        "name": "normalize-prompt-path",
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
    captured: dict[str, str] = {}

    def fake_run_command(command, **kwargs):
        captured["stdin_text"] = kwargs["stdin_text"]
        output_path.write_text('{"checks":[],"flags":[]}', encoding="utf-8")
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
        prompt_override=str(prompt_path),
    )

    expected = prompt_path.read_text(encoding="utf-8")
    assert captured["stdin_text"] == expected
    assert result.rendered_prompt == expected


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


def test_codex_progress_liveness_uses_rollout_and_cpu_signals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan.workers import _impl

    output_path = tmp_path / "execute.json"
    output_path.write_text("", encoding="utf-8")
    rollout_path = tmp_path / "rollout.jsonl"
    rollout_path.write_text('{"type":"thread.started"}\n', encoding="utf-8")

    liveness = _impl.CodexProgressLiveness(output_path=output_path)
    liveness.activity_guard(
        "stdout",
        '{"type":"thread.started","thread_id":"thread-123"}\n',
    )
    probe = liveness.bind_process(SimpleNamespace(pid=321, poll=lambda: None))

    monkeypatch.setattr(
        _impl,
        "_codex_session_jsonl_path",
        lambda session_id: rollout_path if session_id == "thread-123" else None,
    )

    cpu_samples = iter([10.0, 10.0, 15.0])
    monkeypatch.setattr(_impl, "_subtree_cputime_sample", lambda _roots: next(cpu_samples))

    assert probe() == "alive_only"

    rollout_path.write_text(
        '{"type":"thread.started"}\n{"type":"item.started"}\n',
        encoding="utf-8",
    )
    assert probe() == "progressing"
    assert probe() == "progressing"


def test_review_liveness_does_not_treat_cpu_only_as_model_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A busy Codex/node process alone cannot keep a silent review alive."""
    from arnold_pipelines.megaplan.workers import _impl

    output_path = tmp_path / "review.json"
    output_path.write_text("", encoding="utf-8")
    liveness = _impl.CodexProgressLiveness(
        output_path=output_path,
        include_cpu_signal=False,
    )
    probe = liveness.bind_process(SimpleNamespace(pid=321, poll=lambda: None))

    # A CPU sample would advance for a spinning node process. Strict review
    # liveness intentionally ignores it until Codex emits a token/event or
    # writes an artifact.
    monkeypatch.setattr(_impl, "_subtree_cputime_sample", lambda _roots: 99.0)
    assert probe() == "alive_only"
    assert probe() == "alive_only"

    output_path.write_text('{"review_verdict":"approved"}', encoding="utf-8")
    assert probe() == "progressing"


def test_run_command_kills_alive_silent_worker_without_liveness_grace(tmp_path: Path) -> None:
    """The review policy can terminate a process that is alive but evidentially silent."""
    from arnold_pipelines.megaplan.types import CliError
    from arnold_pipelines.megaplan.workers import _impl

    with pytest.raises(CliError, match="stalled stream") as captured:
        _impl.run_command(
            ["/bin/sh", "-c", "sleep 5"],
            cwd=tmp_path,
            timeout=10,
            idle_timeout=0.05,
            progress_liveness_probe=lambda: "alive_only",
            progress_liveness_grace_timeout=0.0,
            activity_callback=lambda *_args: None,
        )

    assert captured.value.code == "worker_stall"


def test_run_codex_step_execute_wires_progress_probe(
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
    output_path.write_text(
        '{"output":"","files_changed":[],"commands_run":[],"deviations":[],"task_updates":[],"sense_check_acknowledgments":[]}',
        encoding="utf-8",
    )
    state = {
        "name": "execute-liveness",
        "idea": "x",
        "current_state": "finalized",
        "iteration": 0,
        "created_at": "1970-01-01T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
    }
    captured: dict[str, object] = {}

    def fake_run_command(command, **kwargs):
        captured["command"] = list(command)
        captured["activity_guard"] = kwargs.get("activity_guard")
        captured["progress_liveness_factory"] = kwargs.get("progress_liveness_factory")
        captured["progress_liveness_grace_timeout"] = kwargs.get(
            "progress_liveness_grace_timeout"
        )
        return _impl.CommandResult(
            command=list(command),
            cwd=tmp_path,
            returncode=0,
            stdout='{"type":"thread.started","thread_id":"thread-123"}\n',
            stderr="",
            duration_ms=5,
        )

    monkeypatch.setattr(_impl, "run_command", fake_run_command)
    monkeypatch.setattr(
        _impl, "_codex_step_cost", lambda *args, **kwargs: (0.0, 0, 0, "gpt-5.5", None)
    )

    _impl.run_codex_step(
        "execute",
        state,
        plan_dir,
        root=root,
        persistent=False,
        fresh=True,
        read_only=False,
        output_path=output_path,
        prompt_override="Return a valid execute payload.",
    )

    assert callable(captured["activity_guard"])
    assert callable(captured["progress_liveness_factory"])
    assert captured["progress_liveness_grace_timeout"] == pytest.approx(600.0)


def test_run_codex_step_review_uses_strict_stream_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arnold_pipelines.megaplan._core import ensure_runtime_layout
    from arnold_pipelines.megaplan.workers import _impl

    root = tmp_path / "root"
    root.mkdir()
    ensure_runtime_layout(root)
    plan_dir = root / ".megaplan" / "plans" / "review-liveness"
    plan_dir.mkdir(parents=True, exist_ok=True)
    output_path = plan_dir / "out.json"
    state = {
        "name": "review-liveness",
        "idea": "x",
        "current_state": "executed",
        "iteration": 0,
        "created_at": "1970-01-01T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {},
    }
    captured: dict[str, object] = {}

    def fake_run_command(command, **kwargs):
        captured["command"] = list(command)
        captured["progress_liveness_grace_timeout"] = kwargs.get(
            "progress_liveness_grace_timeout"
        )
        factory = kwargs["progress_liveness_factory"]
        probe = factory(SimpleNamespace(pid=321, poll=lambda: None))
        liveness = probe.__self__
        captured["include_cpu_signal"] = liveness.include_cpu_signal
        output_path.write_text(
            '{"review_verdict":"approved","criteria":[],"issues":[],'
            '"rework_items":[],"summary":"ok","task_verdicts":[],'
            '"sense_check_verdicts":[]}',
            encoding="utf-8",
        )
        return _impl.CommandResult(
            command=list(command), cwd=tmp_path, returncode=0, stdout="", stderr="", duration_ms=5
        )

    monkeypatch.setattr(_impl, "run_command", fake_run_command)
    monkeypatch.setattr(
        _impl, "_codex_step_cost", lambda *args, **kwargs: (0.0, 0, 0, "gpt-5.5", None)
    )

    _impl.run_codex_step(
        "review",
        state,
        plan_dir,
        root=root,
        persistent=False,
        fresh=True,
        read_only=True,
        output_path=output_path,
        prompt_override="Return a valid review payload.",
    )

    assert "--json" in captured["command"], " ".join(captured["command"])
    assert captured["include_cpu_signal"] is False
    assert captured["progress_liveness_grace_timeout"] == 0.0
