"""Headless Shannon stream worker tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from megaplan.types import CliError
from tests._workers_helpers import _mock_state


def test_shannon_stream_config_is_limited_to_stream_knobs() -> None:
    from megaplan.workers.shannon_stream import ShannonStreamConfig

    assert set(ShannonStreamConfig.__dataclass_fields__) == {
        "execute_timeout_seconds",
        "stream_idle_timeout_seconds",
        "parser_max_unknown_events",
        "conformance_enabled",
        "max_output_tokens",
        "session_roulette_enabled",
        "session_compact_probability",
        "context_op_timeout_seconds",
        "context_op_delay_min_seconds",
        "context_op_delay_max_seconds",
        "handshake_probability",
        "handshake_delay_min_seconds",
        "handshake_delay_max_seconds",
        "readiness_timeout_seconds",
        "readiness_probe_forced",
        "voice",
    }


def test_shannon_stream_config_loads_stream_env_with_shannon_fallbacks() -> None:
    from megaplan.workers.shannon_stream import ShannonStreamConfig

    cfg = ShannonStreamConfig.load(
        {
            "MEGAPLAN_SHANNON_STREAM_EXECUTE_TIMEOUT_SECONDS": "9",
            "MEGAPLAN_SHANNON_STREAM_IDLE_TIMEOUT_SECONDS": "12.5",
            "MEGAPLAN_SHANNON_STREAM_PARSER_MAX_UNKNOWN_EVENTS": "4",
            "MEGAPLAN_SHANNON_STREAM_CONFORMANCE": "yes",
            "MEGAPLAN_SHANNON_STREAM_SESSION_ROULETTE": "off",
            "MEGAPLAN_SHANNON_STREAM_CONTEXT_OP_TIMEOUT_SECONDS": "17",
            "MEGAPLAN_SHANNON_STREAM_CONTEXT_OP_DELAY_MIN_SECONDS": "1.5",
            "MEGAPLAN_SHANNON_STREAM_CONTEXT_OP_DELAY_MAX_SECONDS": "2.5",
            "MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY": "0.75",
            "MEGAPLAN_SHANNON_MAX_OUTPUT_TOKENS": "64000",
        }
    )

    assert cfg.execute_timeout_seconds == 9
    assert cfg.stream_idle_timeout_seconds == 12.5
    assert cfg.parser_max_unknown_events == 4
    assert cfg.conformance_enabled is True
    assert cfg.max_output_tokens == 64000
    assert cfg.session_roulette_enabled is False
    assert cfg.session_compact_probability == 0.75
    assert cfg.context_op_timeout_seconds == 17
    assert cfg.context_op_delay_min_seconds == 1.5
    assert cfg.context_op_delay_max_seconds == 2.5
    assert cfg.handshake_probability == 0.0
    assert cfg.voice == "native_stream"


def test_build_shannon_stream_env_isolates_claude_and_locks_updates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.workers.shannon_stream import build_shannon_stream_env

    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("CLAUDECODE", "outer-thread")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "outer-session")
    monkeypatch.setenv("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "777")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    env, claude_config_dir = build_shannon_stream_env(
        plan_dir=plan_dir,
        state=state,
        step="execute",
    )

    assert env["MEGAPLAN_TURN_ID"] == "plan_worker_test-plan"
    assert "CLAUDECODE" not in env
    assert "CLAUDE_CODE_SESSION_ID" not in env
    assert env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "777"
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["CLAUDE_CONFIG_DIR"] == str(claude_config_dir)
    assert claude_config_dir.is_dir()
    assert claude_config_dir.is_relative_to(plan_dir / ".megaplan" / "runs")
    assert env["DISABLE_AUTOUPDATER"] == "1"
    assert env["CLAUDE_CODE_DISABLE_AUTOUPDATER"] == "1"
    assert env["CLAUDE_DISABLE_AUTOUPDATER"] == "1"

    settings = json.loads(
        (claude_config_dir / "settings.json").read_text(encoding="utf-8")
    )
    assert settings["autoUpdates"] is False


def test_build_shannon_stream_env_sets_default_max_output_when_not_inherited(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.workers.shannon_stream import (
        ShannonStreamConfig,
        build_shannon_stream_env,
    )

    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.delenv("CLAUDE_CODE_MAX_OUTPUT_TOKENS", raising=False)

    env, _ = build_shannon_stream_env(
        plan_dir=plan_dir,
        state=state,
        step="critique",
        config=ShannonStreamConfig.load(
            {"MEGAPLAN_SHANNON_STREAM_MAX_OUTPUT_TOKENS": "96000"}
        ),
        turn_id="custom-turn",
    )

    assert env["MEGAPLAN_TURN_ID"] == "custom-turn"
    assert env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "96000"


def test_shannon_stream_liveness_counts_parsed_stdout_ndjson_as_progress(
    tmp_path: Path,
) -> None:
    from megaplan.workers.shannon_stream import make_shannon_stream_liveness

    plan_dir, state = _mock_state(tmp_path)
    liveness = make_shannon_stream_liveness(
        claude_config_dir=plan_dir / "claude_config",
        work_dir=Path(state["config"]["project_dir"]),
        child_alive=lambda: True,
    )

    liveness.activity_guard("stdout", '{"type":"assistant"')
    assert liveness.probe() == "stalled"

    liveness.activity_guard("stdout", ',"message":{"content":"working"}}\n')
    assert liveness.probe() == "progressing"
    assert liveness.probe() == "stalled"


def test_shannon_stream_liveness_reports_advancing_transcript_mtime(
    tmp_path: Path,
) -> None:
    from megaplan.workers.shannon_stream import (
        _claude_project_slug,
        make_shannon_stream_liveness,
    )

    _plan_dir, state = _mock_state(tmp_path)
    work_dir = Path(state["config"]["project_dir"])
    claude_config_dir = tmp_path / "claude_config"
    transcript_dir = claude_config_dir / "projects" / _claude_project_slug(work_dir)
    transcript_dir.mkdir(parents=True)
    transcript = transcript_dir / "session-1.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    os.utime(transcript, (1000, 1000))
    liveness = make_shannon_stream_liveness(
        claude_config_dir=claude_config_dir,
        work_dir=work_dir,
        session_id="session-1",
        child_alive=lambda: True,
    )

    assert liveness.probe() == "alive_only"
    os.utime(transcript, (1010, 1010))
    assert liveness.probe() == "progressing"
    assert liveness.probe() == "alive_only"


def test_shannon_stream_liveness_classifies_child_and_transcript_stalls(
    tmp_path: Path,
) -> None:
    from megaplan.workers.shannon_stream import (
        _claude_project_slug,
        make_shannon_stream_liveness,
    )

    _plan_dir, state = _mock_state(tmp_path)
    work_dir = Path(state["config"]["project_dir"])
    missing = make_shannon_stream_liveness(
        claude_config_dir=tmp_path / "missing_config",
        work_dir=work_dir,
        child_alive=lambda: True,
    )
    assert missing.probe() == "stalled"

    claude_config_dir = tmp_path / "claude_config"
    transcript_dir = claude_config_dir / "projects" / _claude_project_slug(work_dir)
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "session-1.jsonl").write_text("{}\n", encoding="utf-8")
    exited = make_shannon_stream_liveness(
        claude_config_dir=claude_config_dir,
        work_dir=work_dir,
        child_alive=lambda: False,
    )
    assert exited.probe() == "stalled"


def test_build_shannon_stream_command_write_mode_uses_native_stream_and_bypass(
    tmp_path: Path,
) -> None:
    from megaplan.workers.shannon_stream import build_shannon_stream_command

    _plan_dir, state = _mock_state(tmp_path)

    launch = build_shannon_stream_command(
        state=state,
        prompt="return json",
        model="claude-opus-test",
        session_id="new-session",
    )

    assert launch.command == [
        "claude",
        "--print",
        "--verbose",
        "--input-format=stream-json",
        "--output-format=stream-json",
        "--model",
        "claude-opus-test",
        "--session-id",
        "new-session",
        "--permission-mode",
        "bypassPermissions",
    ]
    assert launch.cwd == Path(state["config"]["project_dir"])
    assert json.loads(launch.stdin_text) == {
        "type": "user",
        "message": {"role": "user", "content": "return json"},
    }


def test_shannon_stream_safety_text_states_os_user_boundary() -> None:
    import megaplan.workers.shannon_stream as shannon_stream

    with pytest.raises(CliError) as exc_info:
        shannon_stream._raise_for_native_stream_failure(
            returncode=1,
            raw_output="Permission denied while opening /root/secret\n",
            session_id=None,
        )

    docs_and_errors = "\n".join(
        [
            shannon_stream.__doc__ or "",
            str(exc_info.value),
        ]
    )
    normalized = docs_and_errors.lower()
    assert "bypasspermissions" in normalized
    assert "os user" in normalized
    assert "process environment" in normalized
    assert "cwd selects" in normalized
    assert "not a filesystem sandbox" in normalized
    for forbidden in (
        "cwd confines",
        "cwd sandbox",
        "worktree confines",
        "worktree sandbox",
        "confined by cwd",
        "confined by the cwd",
        "confined by worktree",
        "filesystem confinement",
    ):
        assert forbidden not in normalized


def test_build_shannon_stream_command_read_only_restricts_tools_without_bypass(
    tmp_path: Path,
) -> None:
    from megaplan.workers.shannon_stream import build_shannon_stream_command

    _plan_dir, state = _mock_state(tmp_path)

    launch = build_shannon_stream_command(
        state=state,
        prompt="inspect only",
        read_only=True,
        resume_session_id="read-session",
    )

    command = launch.command
    assert "--resume" in command
    assert command[command.index("--resume") + 1] == "read-session"
    assert "--allowedTools" in command
    allowed_idx = command.index("--allowedTools")
    assert command[allowed_idx + 1 : allowed_idx + 6] == [
        "Read",
        "Grep",
        "Glob",
        "WebFetch",
        "WebSearch",
    ]
    assert "--disallowedTools" in command
    disallowed_idx = command.index("--disallowedTools")
    assert command[disallowed_idx + 1 : disallowed_idx + 8] == [
        "Bash",
        "Edit",
        "MultiEdit",
        "NotebookEdit",
        "TodoWrite",
        "Task",
        "Write",
    ]
    assert "--permission-mode" not in command
    assert "bypassPermissions" not in command


def test_build_shannon_stream_command_read_only_fails_closed_when_unsupported(
    tmp_path: Path,
) -> None:
    from megaplan.workers.shannon_stream import build_shannon_stream_command

    _plan_dir, state = _mock_state(tmp_path)

    with pytest.raises(CliError) as exc_info:
        build_shannon_stream_command(
            state=state,
            prompt="inspect only",
            read_only=True,
            read_only_tool_policy_supported=False,
        )

    assert exc_info.value.code == "read_only_unsupported"


def test_build_shannon_stream_command_rejects_resume_and_session_id_together(
    tmp_path: Path,
) -> None:
    from megaplan.workers.shannon_stream import build_shannon_stream_command

    _plan_dir, state = _mock_state(tmp_path)

    with pytest.raises(CliError) as exc_info:
        build_shannon_stream_command(
            state=state,
            prompt="hello",
            resume_session_id="old-session",
            session_id="new-session",
        )

    assert exc_info.value.code == "invalid_args"


def _ndjson(*events: dict[str, object]) -> str:
    return "\n".join(json.dumps(event) for event in events) + "\n"


def test_parse_shannon_stream_output_accepts_drifted_native_events() -> None:
    from megaplan.workers.shannon_stream import parse_shannon_stream_output

    raw = _ndjson(
        {"event": "init", "sessionId": "session-from-init", "model": "claude-test"},
        {
            "kind": "assistant",
            "message": {"content": [{"type": "text", "text": "working"}]},
            "usage": {"input_tokens": 4, "output_tokens": 5},
        },
        {"type": "tool_trace", "payload": {"name": "surprise"}},
        {
            "eventType": "result",
            "resultStatus": "success",
            "conversation": {"id": "ignored"},
            "session": {"id": "session-from-result"},
            "payload": {"ok": True, "value": 3},
            "tokenUsage": {"prompt_tokens": 10, "completion_tokens": 11},
            "costUsd": "0.02",
        },
    )

    result = parse_shannon_stream_output(raw, duration_ms=123)

    assert result.payload == {"ok": True, "value": 3}
    assert result.raw_output == raw
    assert result.duration_ms == 123
    assert result.cost_usd == 0.02
    assert result.session_id == "session-from-result"
    assert result.model_actual == "claude-test"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 11
    assert result.total_tokens == 21
    trace = json.loads(result.trace_output or "{}")
    assert trace["assistant_event_count"] == 1
    assert trace["unknown_events"] == [{"type": "tool_trace", "payload": {"name": "surprise"}}]


def test_parse_shannon_stream_output_normalizes_all_rate_limit_windows() -> None:
    from megaplan.workers.shannon_stream import parse_shannon_stream_output

    raw = _ndjson(
        {"type": "init", "session_id": "s1"},
        {
            "type": "rate_limit_event",
            "rateLimits": [
                {"provider": "anthropic", "window": "minute", "remaining": 3},
                {"provider": "anthropic", "window": "day", "remaining": 99},
            ],
        },
        {
            "kind": "rate_limit",
            "rateLimit": {"provider": "anthropic", "window": "hour", "remaining": 7},
        },
        {"type": "result", "status": "completed", "result": {"done": True}},
    )

    result = parse_shannon_stream_output(raw)

    assert result.rate_limit == {
        "values": [
            {"provider": "anthropic", "window": "minute", "remaining": 3},
            {"provider": "anthropic", "window": "day", "remaining": 99},
            {"provider": "anthropic", "window": "hour", "remaining": 7},
        ]
    }


def test_parse_shannon_stream_output_requires_final_result_event() -> None:
    from megaplan.workers.shannon_stream import parse_shannon_stream_output

    raw = _ndjson(
        {"type": "init", "session_id": "s1"},
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "{\"ok\": true}"}]},
        },
    )

    with pytest.raises(CliError) as exc_info:
        parse_shannon_stream_output(raw)

    assert exc_info.value.code == "parse_error"
    assert "final result event" in exc_info.value.message


def test_parse_shannon_stream_output_rejects_uninterpretable_final_result() -> None:
    from megaplan.workers.shannon_stream import parse_shannon_stream_output

    raw = _ndjson(
        {"type": "init", "session_id": "s1"},
        {"type": "result", "status": "success", "result": "plain text"},
    )

    with pytest.raises(CliError) as exc_info:
        parse_shannon_stream_output(raw)

    assert exc_info.value.code == "parse_error"
    assert "interpretable payload" in exc_info.value.message


def test_parse_shannon_stream_output_raises_typed_parse_error_on_bad_ndjson() -> None:
    from megaplan.workers.shannon_stream import parse_shannon_stream_output

    with pytest.raises(CliError) as exc_info:
        parse_shannon_stream_output('{"type":"init"}\nnot-json\n')

    assert exc_info.value.code == "parse_error"
    assert "raw_output" in exc_info.value.extra


def test_parse_shannon_stream_output_raises_native_error_cli_error() -> None:
    from megaplan.workers.shannon_stream import parse_shannon_stream_output

    raw = _ndjson(
        {"type": "init", "session_id": "s1"},
        {
            "type": "result",
            "status": "error",
            "error": {"code": "auth_error", "message": "not logged in; run /login"},
        },
    )

    with pytest.raises(CliError) as exc_info:
        parse_shannon_stream_output(raw)

    assert exc_info.value.code == "auth_error"
    assert "raw_output" in exc_info.value.extra


def test_run_shannon_stream_step_launches_native_claude_and_builds_worker_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import megaplan.workers.shannon_stream as shannon_stream
    from megaplan.workers._impl import CommandResult
    from megaplan.workers._impl import session_key_for

    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][session_key_for("execute", "shannon", model="claude-opus-test")] = {
        "id": "existing-session"
    }
    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_SESSION_ROULETTE", "off")
    calls: list[dict[str, object]] = []
    stdout = _ndjson(
        {"type": "init", "session_id": "existing-session", "model": "claude-test"},
        {
            "type": "rate_limit_event",
            "rateLimits": [{"provider": "anthropic", "window": "minute", "remaining": 5}],
        },
        {
            "type": "result",
            "status": "success",
            "session_id": "landed-session",
            "result": {
                "task_updates": [
                    {
                        "task_id": "T9",
                        "status": "completed",
                        "executor_notes": "Implemented stream runner.",
                        "files_changed": ["megaplan/workers/shannon_stream.py"],
                        "commands_run": ["pytest tests/test_workers_shannon_stream.py"],
                    }
                ],
                "sense_check_acknowledgments": [
                    {"sense_check_id": "SC9", "executor_note": "Stream runner verified."}
                ],
            },
            "usage": {"input_tokens": 7, "output_tokens": 11, "total_tokens": 18},
            "cost_usd": 0.03,
        },
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append({"command": command, **kwargs})
        activity_guard = kwargs["activity_guard"]
        assert callable(activity_guard)
        activity_guard("stdout", stdout)
        assert kwargs["progress_liveness_probe"]() == "progressing"
        return CommandResult(
            command=command,
            cwd=Path(kwargs["cwd"]),
            returncode=0,
            stdout=stdout,
            stderr="debug stderr\n",
            duration_ms=321,
        )

    monkeypatch.setattr(shannon_stream, "run_command", fake_run_command)

    result = shannon_stream.run_shannon_stream_step(
        "execute",
        state,
        plan_dir,
        root=Path.cwd(),
        fresh=False,
        prompt_override="Only produce `task_updates` for these tasks: ['T9']\n"
        "Only produce `sense_check_acknowledgments` for these sense checks: ['SC9']",
        model="claude-opus-test",
    )

    assert calls
    call = calls[0]
    assert call["command"] == [
        "claude",
        "--print",
        "--verbose",
        "--input-format=stream-json",
        "--output-format=stream-json",
        "--model",
        "claude-opus-test",
        "--resume",
        "existing-session",
        "--permission-mode",
        "bypassPermissions",
    ]
    assert call["cwd"] == Path(state["config"]["project_dir"])
    assert call["timeout"] == 7200
    assert call["idle_timeout"] == 300.0
    assert call["progress_liveness_grace_timeout"] == 300.0
    stdin_payload = json.loads(str(call["stdin_text"]))
    prompt = stdin_payload["message"]["content"]
    assert "Output format:" in prompt
    assert "EXECUTE BATCH OUTPUT SCOPE:" in prompt

    assert result.payload["task_updates"][0]["status"] == "done"
    assert result.raw_output == stdout + "debug stderr\n"
    assert result.duration_ms == 321
    assert result.cost_usd == 0.03
    assert result.session_id == "landed-session"
    assert result.model_actual == "claude-test"
    assert result.prompt_tokens == 7
    assert result.completion_tokens == 11
    assert result.total_tokens == 18
    assert result.rate_limit == {
        "provider": "anthropic",
        "window": "minute",
        "remaining": 5,
    }
    assert result.rendered_prompt == prompt
    assert result.shannon_plan == {
        "kind": "resume",
        "session_id": "landed-session",
        "voice": "native_stream",
        "pre_turns": [],
        "main": {"delivery": "stdin", "resume": True, "pre_sleep_s": 0.0},
    }


def test_run_shannon_stream_step_preserves_raw_context_on_parse_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import megaplan.workers.shannon_stream as shannon_stream
    from megaplan.workers._impl import CommandResult

    plan_dir, state = _mock_state(tmp_path)

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        return CommandResult(
            command=command,
            cwd=Path(kwargs["cwd"]),
            returncode=0,
            stdout='{"type":"init","session_id":"s1"}\n',
            stderr="stderr details\n",
            duration_ms=12,
        )

    monkeypatch.setattr(shannon_stream, "run_command", fake_run_command)

    with pytest.raises(CliError) as exc_info:
        shannon_stream.run_shannon_stream_step(
            "execute",
            state,
            plan_dir,
            root=Path.cwd(),
            fresh=True,
            prompt_override="return execute json",
        )

    assert exc_info.value.code == "parse_error"
    assert exc_info.value.extra["raw_output"].endswith("stderr details\n")
    assert exc_info.value.extra["session_id"]


def test_run_shannon_stream_step_uses_clear_plan_and_resumes_landed_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import megaplan.workers.shannon_stream as shannon_stream
    from megaplan.workers._impl import CommandResult
    from megaplan.workers._impl import session_key_for

    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][session_key_for("execute", "shannon", model="claude-opus-test")] = {
        "id": "stale-session"
    }
    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_SESSION_COMPACT_PROBABILITY", "0")
    calls: list[dict[str, object]] = []
    main_stdout = _ndjson(
        {"type": "init", "session_id": "rotated-session"},
        {
            "type": "result",
            "status": "success",
            "session_id": "landed-session",
            "result": {
                "task_updates": [],
                "sense_check_acknowledgments": [],
            },
        },
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append({"command": command, **kwargs})
        stdin_payload = json.loads(str(kwargs["stdin_text"]))
        if stdin_payload["message"]["content"] == "/clear":
            return CommandResult(
                command=command,
                cwd=Path(kwargs["cwd"]),
                returncode=0,
                stdout=_ndjson({"type": "result", "status": "success", "session_id": "rotated-session"}),
                stderr="",
                duration_ms=10,
            )
        return CommandResult(
            command=command,
            cwd=Path(kwargs["cwd"]),
            returncode=0,
            stdout=main_stdout,
            stderr="",
            duration_ms=20,
        )

    monkeypatch.setattr(shannon_stream, "run_command", fake_run_command)

    result = shannon_stream.run_shannon_stream_step(
        "execute",
        state,
        plan_dir,
        root=Path.cwd(),
        fresh=False,
        prompt_override="return execute json",
        model="claude-opus-test",
    )

    assert len(calls) == 2
    assert calls[0]["command"][calls[0]["command"].index("--resume") + 1] == "stale-session"
    assert calls[1]["command"][calls[1]["command"].index("--resume") + 1] == "rotated-session"
    assert result.session_id == "landed-session"
    assert result.shannon_plan is not None
    assert result.shannon_plan["kind"] == "clear"
    assert result.shannon_plan["session_id"] == "landed-session"
    assert result.shannon_plan["main"]["resume"] is True


def test_run_shannon_stream_step_context_op_failure_starts_fresh_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import megaplan.workers.shannon_stream as shannon_stream
    from megaplan.workers._impl import CommandResult
    from megaplan.workers._impl import session_key_for

    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][session_key_for("execute", "shannon", model="claude-opus-test")] = {
        "id": "stale-session"
    }
    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_SESSION_COMPACT_PROBABILITY", "0")
    calls: list[dict[str, object]] = []
    main_stdout = _ndjson(
        {"type": "init", "session_id": "fresh-session"},
        {
            "type": "result",
            "status": "success",
            "session_id": "fresh-session",
            "result": {
                "task_updates": [],
                "sense_check_acknowledgments": [],
            },
        },
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append({"command": command, **kwargs})
        if len(calls) == 1:
            return CommandResult(
                command=command,
                cwd=Path(kwargs["cwd"]),
                returncode=1,
                stdout="",
                stderr="clear failed",
                duration_ms=10,
            )
        return CommandResult(
            command=command,
            cwd=Path(kwargs["cwd"]),
            returncode=0,
            stdout=main_stdout,
            stderr="",
            duration_ms=20,
        )

    monkeypatch.setattr(shannon_stream, "run_command", fake_run_command)

    result = shannon_stream.run_shannon_stream_step(
        "execute",
        state,
        plan_dir,
        root=Path.cwd(),
        fresh=False,
        prompt_override="return execute json",
        model="claude-opus-test",
    )

    assert len(calls) == 2
    assert "--resume" in calls[0]["command"]
    assert calls[0]["command"][calls[0]["command"].index("--resume") + 1] == "stale-session"
    assert "--resume" not in calls[1]["command"]
    assert "--session-id" in calls[1]["command"]
    assert calls[1]["command"][calls[1]["command"].index("--session-id") + 1] != "stale-session"
    assert result.session_id == "fresh-session"
    assert result.shannon_plan is not None
    assert result.shannon_plan["kind"] == "clear"
    assert result.shannon_plan["session_id"] == "fresh-session"
    assert result.shannon_plan["main"]["resume"] is False
