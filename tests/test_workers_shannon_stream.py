"""Headless Shannon stream worker tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from megaplan.types import CliError
from megaplan.workers._impl import session_key_for
from megaplan.workers.turn_cap import HOST_TURN_CAP_SOURCE, acquire_turn_slot
from tests._workers_helpers import _mock_state


def _stream_session_metadata(
    *, auth_channel: str = "subscription", dry_run: bool = False
) -> dict[str, object]:
    return {
        "worker_channel": "shannon_stream",
        "auth_channel": auth_channel,
        "api_key_present": auth_channel == "api_key" and not dry_run,
        "api_key_source": "MEGAPLAN_SHANNON_STREAM_API_KEY" if auth_channel == "api_key" and not dry_run else None,
        "dry_run": dry_run,
    }


def _stream_session_key(step: str = "execute", *, model: str | None = "claude-opus-test") -> str:
    metadata = _stream_session_metadata()
    return session_key_for(
        step,
        "shannon",
        model=model,
        worker_channel=str(metadata["worker_channel"]),
        auth_channel=str(metadata["auth_channel"]),
        auth_metadata=metadata,
    )


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
        "auth_channel",
        "api_key_dry_run",
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
    assert cfg.auth_channel == "subscription"
    assert cfg.api_key_dry_run is False


def test_build_shannon_stream_env_preserves_subscription_auth_and_locks_updates(
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
    assert env["MEGAPLAN_WORKER_CHANNEL"] == "shannon_stream"
    assert env["MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL"] == "subscription"
    assert env["MEGAPLAN_SHANNON_STREAM_API_DRY_RUN_ACTIVE"] == "0"
    assert "CLAUDE_CONFIG_DIR" not in env
    assert claude_config_dir == Path.home() / ".claude"
    assert env["DISABLE_AUTOUPDATER"] == "1"
    assert env["CLAUDE_CODE_DISABLE_AUTOUPDATER"] == "1"
    assert env["CLAUDE_DISABLE_AUTOUPDATER"] == "1"


def test_build_shannon_stream_env_api_key_preserves_or_injects_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.workers.shannon_stream import (
        ShannonStreamConfig,
        build_shannon_stream_env,
    )

    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-inherited")

    env, _ = build_shannon_stream_env(
        plan_dir=plan_dir,
        state=state,
        step="execute",
        config=ShannonStreamConfig.load(
            {"MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL": "api_key"}
        ),
    )

    assert env["ANTHROPIC_API_KEY"] == "sk-ant-inherited"
    assert env["MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL"] == "api_key"

    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_API_KEY", "sk-ant-narrow")
    env, _ = build_shannon_stream_env(
        plan_dir=plan_dir,
        state=state,
        step="execute",
        config=ShannonStreamConfig.load(
            {"MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL": "api_key"}
        ),
    )

    assert env["ANTHROPIC_API_KEY"] == "sk-ant-narrow"


def test_build_shannon_stream_env_api_key_requires_key_unless_dry_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.workers.shannon_stream import (
        ShannonStreamConfig,
        build_shannon_stream_env,
    )

    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MEGAPLAN_SHANNON_STREAM_API_KEY", raising=False)

    with pytest.raises(CliError) as exc_info:
        build_shannon_stream_env(
            plan_dir=plan_dir,
            state=state,
            step="execute",
            config=ShannonStreamConfig.load(
                {"MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL": "api_key"}
            ),
        )

    assert exc_info.value.code == "auth_error"
    assert exc_info.value.extra["auth_channel"] == "api_key"

    env, _ = build_shannon_stream_env(
        plan_dir=plan_dir,
        state=state,
        step="execute",
        config=ShannonStreamConfig.load(
            {
                "MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL": "api_key",
                "MEGAPLAN_SHANNON_STREAM_API_DRY_RUN": "1",
            }
        ),
    )

    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["MEGAPLAN_SHANNON_STREAM_API_DRY_RUN_ACTIVE"] == "1"


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

    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][_stream_session_key()] = {
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
        "worker_channel": "shannon_stream",
        "auth_channel": "subscription",
        "auth_metadata": {
            "worker_channel": "shannon_stream",
            "auth_channel": "subscription",
            "api_key_present": False,
            "api_key_source": None,
            "dry_run": False,
        },
    }
    assert result.worker_channel == "shannon_stream"
    assert result.auth_channel == "subscription"
    assert result.auth_metadata == result.shannon_plan["auth_metadata"]
    trace = json.loads(result.trace_output or "{}")
    assert trace["metadata"] == result.auth_metadata


def test_run_shannon_stream_step_does_not_resume_legacy_tmux_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import megaplan.workers.shannon_stream as shannon_stream
    from megaplan.workers._impl import CommandResult

    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][session_key_for("execute", "shannon", model="claude-opus-test")] = {
        "id": "legacy-tmux-session"
    }
    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_SESSION_ROULETTE", "off")
    calls: list[list[str]] = []
    stdout = _ndjson(
        {"type": "init", "session_id": "stream-session"},
        {
            "type": "result",
            "status": "success",
            "session_id": "stream-session",
            "result": {"task_updates": [], "sense_check_acknowledgments": []},
        },
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append(command)
        return CommandResult(
            command=command,
            cwd=Path(kwargs["cwd"]),
            returncode=0,
            stdout=stdout,
            stderr="",
            duration_ms=1,
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

    assert len(calls) == 1
    assert "--resume" not in calls[0]
    assert calls[0][calls[0].index("--session-id") + 1] != "legacy-tmux-session"
    assert result.session_id == "stream-session"


def test_run_shannon_stream_step_records_api_auth_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import megaplan.workers.shannon_stream as shannon_stream
    from megaplan.workers._impl import CommandResult

    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL", "api_key")
    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_API_KEY", "sk-ant-test")
    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_SESSION_ROULETTE", "off")
    stdout = _ndjson(
        {"type": "init", "session_id": "api-session", "model": "claude-test"},
        {
            "type": "result",
            "status": "success",
            "session_id": "api-session",
            "result": {
                "task_updates": [
                    {
                        "task_id": "T9",
                        "status": "done",
                        "executor_notes": "Recorded API auth metadata.",
                        "files_changed": [],
                        "commands_run": [],
                    }
                ],
                "sense_check_acknowledgments": [],
            },
        },
    )

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        env = kwargs["env"]
        assert isinstance(env, dict)
        assert env["ANTHROPIC_API_KEY"] == "sk-ant-test"
        assert env["MEGAPLAN_SHANNON_STREAM_AUTH_CHANNEL"] == "api_key"
        return CommandResult(
            command=command,
            cwd=Path(kwargs["cwd"]),
            returncode=0,
            stdout=stdout,
            stderr="",
            duration_ms=9,
        )

    monkeypatch.setattr(shannon_stream, "run_command", fake_run_command)

    result = shannon_stream.run_shannon_stream_step(
        "execute",
        state,
        plan_dir,
        root=Path.cwd(),
        fresh=True,
        prompt_override="Only produce `task_updates` for these tasks: ['T9']",
        model="claude-opus-test",
    )

    assert result.worker_channel == "shannon_stream"
    assert result.auth_channel == "api_key"
    assert result.auth_metadata == {
        "worker_channel": "shannon_stream",
        "auth_channel": "api_key",
        "api_key_present": True,
        "api_key_source": "MEGAPLAN_SHANNON_STREAM_API_KEY",
        "dry_run": False,
    }
    assert result.shannon_plan is not None
    assert result.shannon_plan["auth_metadata"] == result.auth_metadata
    trace = json.loads(result.trace_output or "{}")
    assert trace["metadata"] == result.auth_metadata


def test_shannon_stream_receipt_includes_auth_and_worker_channel_metadata(
    tmp_path: Path,
) -> None:
    from megaplan.receipts import build_receipt
    from megaplan.workers._impl import WorkerResult

    plan_dir, state = _mock_state(tmp_path)
    worker = WorkerResult(
        payload={},
        raw_output="",
        duration_ms=12,
        cost_usd=0.01,
        session_id="sid",
        shannon_plan={
            "worker_channel": "shannon_stream",
            "auth_channel": "api_key",
        },
        worker_channel="shannon_stream",
        auth_channel="api_key",
        auth_metadata={
            "worker_channel": "shannon_stream",
            "auth_channel": "api_key",
            "api_key_present": True,
            "api_key_source": "ANTHROPIC_API_KEY",
            "dry_run": False,
        },
    )

    receipt = build_receipt(
        phase="execute",
        state=state,
        plan_dir=plan_dir,
        args=SimpleNamespace(phase_model=[], profile=None, agent=None),
        worker=worker,
        agent="shannon",
        mode="persistent",
        output_file="execution.json",
        artifact_hash="sha256:test",
        verdict="success",
    )

    assert receipt["worker_channel"] == "shannon_stream"
    assert receipt["auth_channel"] == "api_key"
    assert receipt["auth_metadata"] == worker.auth_metadata


def test_m3_api_adapter_proof_record_distinguishes_dry_run_from_live_proof() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    record_path = repo_root / "docs" / "shannon-stream-api-proof-record.json"
    docs_path = repo_root / "docs" / "shannon-stream-channel-plan.md"

    record = json.loads(record_path.read_text(encoding="utf-8"))
    docs_text = docs_path.read_text(encoding="utf-8")

    assert record["proof_kind"] in {"dry_run", "live"}
    assert record["worker_channel"] == "shannon_stream"
    assert record["auth_channel"] == "api_key"
    assert record["phase"]
    assert "cost_usd" in record
    assert set(record["token_usage"]) == {
        "input_tokens",
        "output_tokens",
        "total_tokens",
    }
    assert "quota_rate_limit_evidence" in record
    assert record["permission_mode"] == "bypassPermissions"
    assert "payload_schema_validity" in record
    assert record["migration_triggers"]

    if record["proof_kind"] == "dry_run":
        assert record["live_api_phase_completed"] is False
        assert record["dry_run"]["validates"]
        blocked_claims = set(record["dry_run"]["does_not_validate"])
        assert "API-channel shadow parity" in blocked_claims
        assert "stream-json default cutover" in blocked_claims
        assert record["parity_evidence"]["status"] == "deferred"

    assert "dry-run only" in docs_text
    assert "validates adapter plumbing only" in docs_text
    assert "does **not** validate live API billing" in docs_text
    assert "downstream shadow/cutover work may only claim subscription" in docs_text


def test_native_stream_turn_pre_sleep_does_not_hold_host_turn_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import megaplan.workers.shannon_stream as shannon_stream
    from megaplan.workers._impl import CommandResult
    from megaplan.workers.shannon_session import Turn

    lock_dir = tmp_path / "turn-cap"
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP", "1")
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP_DIR", str(lock_dir))
    plan_dir, state = _mock_state(tmp_path)
    env, claude_config_dir = shannon_stream.build_shannon_stream_env(
        plan_dir=plan_dir,
        state=state,
        step="execute",
        config=shannon_stream.ShannonStreamConfig.load({}),
        turn_id="plan_worker_test",
    )
    sleep_checked = False
    subprocess_checked = False

    def fake_sleep(seconds: float) -> None:
        nonlocal sleep_checked
        assert seconds == 1.5
        with acquire_turn_slot(
            engine="claude",
            channel="probe",
            step="sleep",
            plan=plan_dir,
            cap=1,
            lock_dir=lock_dir,
        ):
            sleep_checked = True

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        nonlocal subprocess_checked
        with pytest.raises(CliError) as exc_info:
            with acquire_turn_slot(
                engine="claude",
                channel="probe",
                step="subprocess",
                plan=plan_dir,
                cap=1,
                lock_dir=lock_dir,
            ):
                pass
        assert exc_info.value.code == "rate_limit"
        assert exc_info.value.extra["source"] == HOST_TURN_CAP_SOURCE
        subprocess_checked = True
        return CommandResult(
            command=command,
            cwd=Path(kwargs["cwd"]),
            returncode=0,
            stdout='{"type":"result","status":"success","session_id":"sid"}\n',
            stderr="",
            duration_ms=8,
        )

    monkeypatch.setattr(shannon_stream.time, "sleep", fake_sleep)
    monkeypatch.setattr(shannon_stream, "run_command", fake_run_command)

    result = shannon_stream._run_native_stream_turn(
        Turn(
            session_id="sid",
            resume=False,
            body="hello",
            delivery="stdin",
            expect="envelope",
            timeout=30,
            pre_sleep_s=1.5,
        ),
        step="execute",
        state=state,
        plan_dir=plan_dir,
        config=shannon_stream.ShannonStreamConfig.load({}),
        env=env,
        claude_config_dir=claude_config_dir,
        model="claude-test",
        read_only=False,
        prompt="hello",
    )

    assert sleep_checked is True
    assert subprocess_checked is True
    assert result.returncode == 0


def test_native_stream_turn_refuses_when_host_turn_cap_full(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import megaplan.workers.shannon_stream as shannon_stream
    from megaplan.workers.shannon_session import Turn

    lock_dir = tmp_path / "turn-cap"
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP", "1")
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP_DIR", str(lock_dir))
    plan_dir, state = _mock_state(tmp_path)
    config = shannon_stream.ShannonStreamConfig.load({})
    env, claude_config_dir = shannon_stream.build_shannon_stream_env(
        plan_dir=plan_dir,
        state=state,
        step="execute",
        config=config,
        turn_id="plan_worker_test",
    )
    monkeypatch.setattr(
        shannon_stream,
        "run_command",
        lambda *args, **kwargs: pytest.fail("run_command must not launch when cap is full"),
    )

    with acquire_turn_slot(engine="codex", step="other", plan=plan_dir, cap=1, lock_dir=lock_dir):
        with pytest.raises(CliError) as exc_info:
            shannon_stream._run_native_stream_turn(
                Turn(
                    session_id="sid",
                    resume=False,
                    body="hello",
                    delivery="stdin",
                    expect="envelope",
                    timeout=30,
                    pre_sleep_s=0.0,
                ),
                step="execute",
                state=state,
                plan_dir=plan_dir,
                config=config,
                env=env,
                claude_config_dir=claude_config_dir,
                model="claude-test",
                read_only=False,
                prompt="hello",
            )

    assert exc_info.value.code == "rate_limit"
    assert exc_info.value.extra["source"] == HOST_TURN_CAP_SOURCE


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

    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][_stream_session_key()] = {
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

    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][_stream_session_key()] = {
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
