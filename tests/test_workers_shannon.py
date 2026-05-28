"""Direct Shannon worker tests for megaplan.workers."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from megaplan.types import CliError
from megaplan.workers import WorkerResult, resolve_agent_mode, session_key_for
from tests._workers_helpers import FakeShutil, _mock_state


def test_is_shannon_available_all_deps_present() -> None:
    from megaplan._core.io import is_shannon_available
    fake = FakeShutil("shannon", "tmux", "claude")
    assert is_shannon_available(shutil_ref=fake) is True

def test_is_shannon_available_missing_tmux() -> None:
    from megaplan._core.io import is_shannon_available
    fake = FakeShutil("shannon", "claude")
    assert is_shannon_available(shutil_ref=fake) is False

def test_is_shannon_available_missing_claude() -> None:
    from megaplan._core.io import is_shannon_available
    fake = FakeShutil("shannon", "tmux")
    assert is_shannon_available(shutil_ref=fake) is False

def test_is_shannon_available_missing_shannon() -> None:
    from megaplan._core.io import is_shannon_available
    fake = FakeShutil("tmux", "claude")
    assert is_shannon_available(shutil_ref=fake) is False

def test_shannon_missing_deps_lists_missing() -> None:
    from megaplan._core.io import shannon_missing_deps
    fake = FakeShutil("claude")  # missing shannon and tmux
    assert sorted(shannon_missing_deps(shutil_ref=fake)) == ["shannon", "tmux"]

def test_detect_available_agents_includes_shannon_when_deps_present() -> None:
    from megaplan._core.io import detect_available_agents
    # detect_available_agents uses `import megaplan._core as _core_pkg; _core_pkg.shutil`
    # which resolves to the stdlib shutil re-exported in megaplan/_core/__init__.py.
    with patch("megaplan._core.shutil", FakeShutil("shannon", "tmux", "claude", "codex")):
        agents = detect_available_agents()
    assert "shannon" in agents

def test_detect_available_agents_excludes_shannon_when_deps_missing() -> None:
    from megaplan._core.io import detect_available_agents
    with patch("megaplan._core.shutil", FakeShutil("claude", "codex")):
        agents = detect_available_agents()
    assert "shannon" not in agents

def test_is_agent_available_shannon_agrees_with_is_shannon_available() -> None:
    """_is_agent_available('shannon') delegates to is_shannon_available()."""
    from megaplan.workers import _is_agent_available
    # _is_agent_available('shannon') calls is_shannon_available() which uses
    # the `shutil` imported in io.py, and detect_available_agents uses
    # megaplan._core.shutil (re-exported in __init__.py).  Patch both.
    with (
        patch("megaplan._core.io.shutil", FakeShutil("shannon", "tmux", "claude")),
        patch("megaplan._core.shutil", FakeShutil("shannon", "tmux", "claude")),
    ):
        assert _is_agent_available("shannon") is True
    with (
        patch("megaplan._core.io.shutil", FakeShutil("claude")),
        patch("megaplan._core.shutil", FakeShutil("claude")),
    ):
        assert _is_agent_available("shannon") is False

def test_is_agent_available_claude_routes_through_shannon_deps() -> None:
    """The public 'claude' agent now means Shannon-backed Claude."""
    from megaplan.workers import _is_agent_available

    with patch("megaplan._core.io.shutil", FakeShutil("shannon", "tmux", "claude")):
        assert _is_agent_available("claude") is True
    with patch("megaplan._core.io.shutil", FakeShutil("claude")):
        assert _is_agent_available("claude") is False

def test_resolve_agent_mode_agent_shannon_explicit_fails_on_missing_deps() -> None:
    """--agent shannon when deps missing → CliError('agent_deps_missing')."""
    with patch("megaplan.workers._impl.shutil.which", return_value=None):
        with patch("megaplan.workers._impl.load_config", return_value={}):
            with patch("megaplan.workers._impl.detect_available_agents", return_value=["claude", "codex"]):
                with pytest.raises(CliError, match="Shannon requires"):
                    resolve_agent_mode("plan", Namespace(agent="shannon", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))

def test_resolve_agent_mode_phase_model_shannon_explicit_fails_on_missing_deps() -> None:
    """--phase-model plan=shannon when deps missing → CliError('agent_deps_missing')."""
    with patch("megaplan.workers._impl.shutil.which", return_value=None):
        with patch("megaplan.workers._impl.load_config", return_value={}):
            with patch("megaplan.workers._impl.detect_available_agents", return_value=["claude", "codex"]):
                with pytest.raises(CliError, match="Shannon requires"):
                    resolve_agent_mode("plan", Namespace(agent=None, ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=["plan=shannon"]))

def test_resolve_agent_mode_non_explicit_shannon_can_fallback() -> None:
    """When Shannon is not explicitly requested, it can fall back to another agent."""
    with patch("megaplan.workers._impl.shutil.which", side_effect=lambda name: "/usr/bin/claude" if name == "claude" else None):
        with patch("megaplan.workers._impl.load_config", return_value={"agents": {"plan": "shannon"}}):
            # Shannon isn't available, and the config default isn't explicit via --agent,
            # so fallback to the next available.
            with patch("megaplan.workers._impl.detect_available_agents", return_value=["claude", "codex"]):
                agent, mode, refreshed, model = resolve_agent_mode("plan", Namespace(agent=None, ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))
    # Falls back to claude because shannon is unavailable and not explicit
    assert agent == "claude"

def test_resolve_agent_mode_shannon_mock_mode_bypasses_availability_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MEGAPLAN_MOCK_WORKERS=1 + --agent shannon must skip availability checks."""
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    # shutil.which returns None for everything — Shannon deps are missing
    with patch("megaplan.workers._impl.shutil.which", return_value=None):
        with patch("megaplan.workers._impl.load_config", return_value={}):
            agent, mode, refreshed, model = resolve_agent_mode("plan", Namespace(agent="shannon", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))
    assert agent == "shannon"
    assert mode == "persistent"

def test_run_step_with_worker_shannon_calls_run_shannon_step(tmp_path: Path) -> None:
    from megaplan.workers import run_step_with_worker, CommandResult

    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "output": "shannon-done",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": [],
        "sense_check_acknowledgments": [],
    }
    fake_worker = WorkerResult(
        payload=payload,
        raw_output="{}",
        duration_ms=100,
        cost_usd=0.0,
        session_id="shannon-sess",
        rendered_prompt="prompt",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    with patch("megaplan.workers.shannon.run_shannon_step", return_value=fake_worker) as run_shannon:
        run_step_with_worker(
            "plan",
            state,
            plan_dir,
            Namespace(agent="shannon", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]),
            root=tmp_path,
            resolved=("shannon", "persistent", False, None),
        )
    run_shannon.assert_called_once()
    assert run_shannon.call_args.args[0] == "plan"

def test_run_step_with_worker_shannon_returns_agent_shannon(tmp_path: Path) -> None:
    from megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "output": "shannon",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": [],
        "sense_check_acknowledgments": [],
    }
    fake_worker = WorkerResult(
        payload=payload,
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="sess",
        rendered_prompt="p",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )
    with patch("megaplan.workers.shannon.run_shannon_step", return_value=fake_worker):
        result, agent, mode, refreshed = run_step_with_worker(
            "plan",
            state,
            plan_dir,
            Namespace(agent="shannon", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]),
            root=tmp_path,
            resolved=("shannon", "persistent", False, None),
        )
    assert agent == "shannon"
    assert mode == "persistent"
    assert refreshed is True
    assert result.payload == payload

def test_run_step_with_worker_claude_calls_run_shannon_step(tmp_path: Path) -> None:
    from megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    fake_worker = WorkerResult(
        payload=payload,
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="shannon-backed-claude",
        rendered_prompt="p",
    )
    with patch("megaplan.workers.shannon.run_shannon_step", return_value=fake_worker) as run_shannon:
        result, agent, mode, refreshed = run_step_with_worker(
            "plan",
            state,
            plan_dir,
            Namespace(agent="claude", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]),
            root=tmp_path,
            resolved=("claude", "persistent", False, None),
        )
    run_shannon.assert_called_once()
    assert agent == "claude"
    assert mode == "persistent"
    assert refreshed is True
    assert result.payload == payload

def test_session_key_for_shannon_steps() -> None:
    """Generic {agent}_{step} fallback covers all Shannon steps."""
    assert session_key_for("plan", "shannon") == "shannon_planner"
    assert session_key_for("critique", "shannon") == "shannon_critic"
    assert session_key_for("gate", "shannon") == "shannon_gatekeeper"
    assert session_key_for("execute", "shannon") == "shannon_executor"
    assert session_key_for("review", "shannon") == "shannon_reviewer"
    assert session_key_for("finalize", "shannon") == "shannon_finalizer"

def test_parse_shannon_output_structured_output() -> None:
    from megaplan.workers.shannon import _parse_shannon_output

    envelope, payload = _parse_shannon_output(json.dumps({
        "structured_output": {"plan": "# Plan", "questions": []},
        "session_id": "sess-1",
    }))
    assert payload == {"plan": "# Plan", "questions": []}
    assert envelope["session_id"] == "sess-1"

def test_parse_shannon_output_result_string() -> None:
    from megaplan.workers.shannon import _parse_shannon_output

    envelope, payload = _parse_shannon_output(json.dumps({
        "result": json.dumps({"output": "done"}),
    }))
    assert payload == {"output": "done"}

def test_parse_shannon_output_transcript_array() -> None:
    from megaplan.workers.shannon import _parse_shannon_output

    transcript = [
        {"type": "user", "message": {"content": "Do X"}},
        {"type": "assistant", "message": {
            "structured_output": {"plan": "# Plan"},
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }},
    ]
    envelope, payload = _parse_shannon_output(json.dumps(transcript))
    assert payload == {"plan": "# Plan"}

def test_parse_shannon_output_transcript_with_result_string() -> None:
    from megaplan.workers.shannon import _parse_shannon_output

    transcript = [
        {"type": "user", "message": {"content": "Do X"}},
        {"type": "assistant", "message": {
            "result": json.dumps({"output": "done"}),
        }},
    ]
    envelope, payload = _parse_shannon_output(json.dumps(transcript))
    assert payload == {"output": "done"}

def test_parse_shannon_output_prefers_result_event() -> None:
    from megaplan.workers.shannon import _parse_shannon_output

    transcript = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "ignore"}]}},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps({"output": "done"}),
            "session_id": "shannon-real-session",
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    ]
    envelope, payload = _parse_shannon_output(json.dumps(transcript))
    assert payload == {"output": "done"}
    assert envelope["session_id"] == "shannon-real-session"
    assert envelope["total_cost_usd"] == 0.01

def test_parse_shannon_output_result_event_markdown_fenced_json() -> None:
    """Regression: Claude commonly wraps structured JSON in ```json ... ``` fences.

    Prior to the fix, _parse_shannon_output called json.loads on the result
    field and `continue`d on JSONDecodeError, so fenced responses fell through
    and downstream gates surfaced "parse_error: <step> output missing required
    keys: plan". The parser should now fall back to _extract_json_object.
    """
    from megaplan.workers.shannon import _parse_shannon_output

    plan_payload = {
        "plan": "Step 1: do the thing.",
        "questions": [],
        "success_criteria": ["it works"],
        "assumptions": ["env is sane"],
    }
    fenced = "```json\n" + json.dumps(plan_payload) + "\n```"
    transcript = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "thinking..."}]}},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": fenced,
            "session_id": "shannon-fenced-session",
            "total_cost_usd": 0.02,
            "usage": {"input_tokens": 12, "output_tokens": 8},
        },
    ]
    envelope, payload = _parse_shannon_output(json.dumps(transcript))
    assert isinstance(payload, dict)
    assert payload == plan_payload
    assert set(payload.keys()) == {"plan", "questions", "success_criteria", "assumptions"}
    assert envelope["session_id"] == "shannon-fenced-session"

def test_parse_shannon_output_assistant_message_markdown_fenced_json() -> None:
    """Regression: fenced JSON in an assistant message's `result` field should also parse."""
    from megaplan.workers.shannon import _parse_shannon_output

    plan_payload = {
        "plan": "Do it.",
        "questions": ["q?"],
        "success_criteria": ["ok"],
        "assumptions": [],
    }
    fenced = "```json\n" + json.dumps(plan_payload) + "\n```"
    transcript = [
        {"type": "user", "message": {"content": "Plan this"}},
        {"type": "assistant", "message": {"result": fenced}},
    ]
    envelope, payload = _parse_shannon_output(json.dumps(transcript))
    assert payload == plan_payload

def test_parse_shannon_output_assistant_content_block_fenced_json() -> None:
    """Regression: fenced JSON inside an assistant content-block text should also parse."""
    from megaplan.workers.shannon import _parse_shannon_output

    plan_payload = {
        "plan": "P",
        "questions": [],
        "success_criteria": [],
        "assumptions": [],
    }
    fenced = "Here is the plan:\n\n```json\n" + json.dumps(plan_payload) + "\n```"
    transcript = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": fenced}]}},
    ]
    envelope, payload = _parse_shannon_output(json.dumps(transcript))
    assert payload == plan_payload

def test_parse_shannon_output_invalid_json() -> None:
    from megaplan.workers.shannon import _parse_shannon_output

    with pytest.raises(CliError, match="not valid JSON"):
        _parse_shannon_output("not json")

def test_parse_shannon_output_auth_error() -> None:
    from megaplan.workers.shannon import _parse_shannon_output

    with pytest.raises(CliError, match="Shannon step failed"):
        _parse_shannon_output(json.dumps({
            "is_error": True,
            "result": "Not logged in. Run /login first.",
        }))

def test_parse_shannon_output_empty_transcript_uses_last_dict() -> None:
    from megaplan.workers.shannon import _parse_shannon_output

    # Transcript with no structured_output → falls back to last element
    transcript = [
        {"type": "user", "message": {"content": "hello"}},
        {"type": "assistant", "message": {"content": "hi"}},
    ]
    envelope, payload = _parse_shannon_output(json.dumps(transcript))
    # Last message dict is returned
    assert payload == {"content": "hi"}


# ---------------------------------------------------------------------------
# stream-json (NDJSON) parsing — the liveness output format
#
# Sample events mirror @dexh/shannon's stream-json emission shape (one JSON
# object per line): system/init after session discovery, per-turn
# assistant + result, and a trailing shannon_session metadata row on cleanup.
# The final structured-output payload lives in the type=result event's
# `result` field, identical to the legacy buffered json-array path.
# ---------------------------------------------------------------------------


def _shannon_stream_json(events: list[dict]) -> str:
    """Render *events* as Shannon stream-json stdout (one JSON object per line)."""
    return "\n".join(json.dumps(e) for e in events) + "\n"


def test_parse_shannon_stream_json_prefers_result_event() -> None:
    from megaplan.workers.shannon import _parse_shannon_output

    payload = {
        "output": "done",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": [],
        "sense_check_acknowledgments": [],
    }
    raw = _shannon_stream_json([
        {"type": "system", "subtype": "init", "session_id": "sess-stream", "model": "claude-opus"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "working..."}]}},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps(payload),
            "session_id": "sess-stream",
            "total_cost_usd": 0.05,
            "usage": {"input_tokens": 20, "output_tokens": 10},
        },
        # Trailing cleanup metadata row, last line — must be skipped in favour
        # of the result event above.
        {"type": "shannon_session", "subtype": "metadata", "session_id": "sess-stream"},
    ])
    envelope, parsed = _parse_shannon_output(raw)
    assert parsed == payload
    assert envelope["session_id"] == "sess-stream"
    assert envelope["total_cost_usd"] == 0.05


def test_parse_shannon_stream_json_matches_buffered_array() -> None:
    """The NDJSON path must extract the SAME payload the legacy json array does."""
    from megaplan.workers.shannon import _parse_shannon_output

    payload = {"plan": "# Plan", "questions": [], "success_criteria": ["ok"], "assumptions": []}
    events = [
        {"type": "system", "subtype": "init", "session_id": "s1", "model": "claude-opus"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "thinking"}]}},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": json.dumps(payload),
            "session_id": "s1",
            "total_cost_usd": 0.03,
            "usage": {"input_tokens": 5, "output_tokens": 3},
        },
    ]
    # Buffered (--output-format=json): one JSON array on a single line.
    _, buffered_payload = _parse_shannon_output(json.dumps(events))
    # Streamed (--output-format=stream-json): one object per line (NDJSON).
    _, streamed_payload = _parse_shannon_output(_shannon_stream_json(events))
    assert streamed_payload == buffered_payload == payload


def test_parse_shannon_stream_json_result_markdown_fenced() -> None:
    """Fenced JSON in the streamed result event must still recover via _extract_json_object."""
    from megaplan.workers.shannon import _parse_shannon_output

    payload = {"plan": "P", "questions": [], "success_criteria": [], "assumptions": []}
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    raw = _shannon_stream_json([
        {"type": "system", "subtype": "init", "session_id": "s2"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": fenced,
            "session_id": "s2",
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 4, "output_tokens": 2},
        },
    ])
    _, parsed = _parse_shannon_output(raw)
    assert parsed == payload


def test_parse_shannon_stream_json_falls_back_to_assistant_structured_output() -> None:
    """With no result event, the NDJSON path walks back to an assistant message."""
    from megaplan.workers.shannon import _parse_shannon_output

    raw = _shannon_stream_json([
        {"type": "system", "subtype": "init", "session_id": "s3"},
        {"type": "assistant", "message": {
            "structured_output": {"plan": "# From assistant"},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }},
    ])
    _, parsed = _parse_shannon_output(raw)
    assert parsed == {"plan": "# From assistant"}


def test_parse_shannon_single_line_json_array_unchanged() -> None:
    """A single-line JSON array (legacy buffered shape) must still use the
    single-document path, not be misread as NDJSON."""
    from megaplan.workers.shannon import _parse_shannon_output

    payload = {"output": "ok"}
    transcript = [
        {"type": "result", "subtype": "success", "result": json.dumps(payload), "session_id": "s4"},
    ]
    # Single line, no trailing newline split -> not NDJSON.
    _, parsed = _parse_shannon_output(json.dumps(transcript))
    assert parsed == payload


def test_parse_shannon_single_result_line_parses_as_object() -> None:
    """A degenerate one-event stream (just the result line) parses via the
    single-object dict path — len(lines) < 2 declines the NDJSON branch."""
    from megaplan.workers.shannon import _parse_shannon_output

    payload = {"output": "single"}
    raw = json.dumps({
        "type": "result",
        "subtype": "success",
        "result": json.dumps(payload),
        "session_id": "s5",
        "total_cost_usd": 0.0,
    }) + "\n"
    envelope, parsed = _parse_shannon_output(raw)
    assert parsed == payload
    assert envelope["session_id"] == "s5"


def test_parse_shannon_stream_json_pretty_array_not_misread() -> None:
    """A pretty-printed (multi-line) JSON array is NOT NDJSON: its lines are not
    independently parseable, so the parser must fall back to the single-document
    path and still decode the whole array."""
    from megaplan.workers.shannon import _parse_shannon_output

    payload = {"output": "pretty"}
    transcript = [
        {"type": "result", "subtype": "success", "result": json.dumps(payload), "session_id": "s6"},
    ]
    pretty = json.dumps(transcript, indent=2)  # spans many lines, lines aren't valid JSON alone
    assert "\n" in pretty
    _, parsed = _parse_shannon_output(pretty)
    assert parsed == payload

def test_run_shannon_step_timeout_raises_worker_timeout_with_session_id(
    tmp_path: Path,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers.shannon import run_shannon_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][session_key_for("plan", "shannon")] = {
        "id": "shannon-session-abc",
        "mode": "persistent",
        "created_at": "2026-03-20T00:00:00Z",
        "last_used_at": "2026-03-20T00:00:00Z",
        "refreshed": False,
    }

    timeout_error = CliError("worker_timeout", "Shannon timed out", extra={"raw_output": "partial"})
    with patch("megaplan.workers.shannon.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_shannon_step("plan", state, plan_dir, root=tmp_path, fresh=False)

    assert exc_info.value.extra["session_id"] != "shannon-session-abc"
    assert exc_info.value.extra["session_id"]

def test_run_shannon_step_passes_prompt_with_print_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers.shannon import run_shannon_step
    from megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "output": "done",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": [],
        "sense_check_acknowledgments": [],
    }
    raw = json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps(payload),
            "session_id": "real-shannon-session",
            "total_cost_usd": 0.02,
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }
    ])
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=raw,
        stderr="",
        duration_ms=123,
    )

    with patch("megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
        result = run_shannon_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="return json",
        )

    command = run_command.call_args.args[0]
    assert command[0:2] == ["shannon", "-p"]
    assert "Read the full megaplan phase prompt from this file" in command[2]
    # Shannon is launched with stream-json so it emits incremental NDJSON
    # events that reset the _impl.py idle-output watchdog (real liveness),
    # instead of the fully buffered single-array --output-format=json.
    assert "--output-format=stream-json" in command
    assert "--output-format=json" not in command
    assert "--json-schema" not in command
    assert "--add-dir" not in command
    assert "--permission-mode" in command
    assert "bypassPermissions" in command
    assert "--dangerously-skip-permissions" in command
    assert "--allow-dangerously-skip-permissions" in command
    # Readiness probe may trigger probabilistically; accept either flag.
    assert ("--session-id" in command) or ("--resume" in command)
    assert run_command.call_args.kwargs["stdin_text"] is None
    assert run_command.call_args.kwargs["env"]["SHANNON_TURN_TIMEOUT_MS"] == "7200000"
    # On non-root systems, ANTHROPIC_API_KEY is set to "" to block Bun's dotenv auto-load.
    api_key_val = run_command.call_args.kwargs["env"].get("ANTHROPIC_API_KEY")
    assert api_key_val is None or api_key_val == ""
    prompt_file = plan_dir / "execute_shannon_prompt.txt"
    prompt_text = prompt_file.read_text(encoding="utf-8")
    assert "return json" in prompt_text
    assert "SHANNON STRUCTURED OUTPUT CONTRACT" in prompt_text
    assert result.payload == payload
    assert result.session_id == "real-shannon-session"
    assert result.cost_usd == 0.02

def test_run_shannon_step_preserves_anthropic_api_key_for_root_cloud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers.shannon import run_shannon_step
    from megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("megaplan.workers.shannon.os.geteuid", lambda: 0)
    payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=json.dumps([
            {
                "type": "result",
                "subtype": "success",
                "result": json.dumps(payload),
                "session_id": "real-shannon-session",
                "total_cost_usd": 0.02,
                "usage": {"input_tokens": 11, "output_tokens": 7},
            }
        ]),
        stderr="",
        duration_ms=123,
    )

    with patch("megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
        run_shannon_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="return json",
        )

    assert run_command.call_args.kwargs["env"]["ANTHROPIC_API_KEY"] == "sk-ant-test"

def test_run_shannon_step_drops_root_for_trusted_cloud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers.shannon import run_shannon_step
    from megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CHMOD_WORKSPACE", "0")
    monkeypatch.setattr("megaplan.workers.shannon.os.geteuid", lambda: 0)
    monkeypatch.setattr("megaplan.workers.shannon.shutil.which", lambda name: "/bin/su" if name == "su" else None)
    payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=json.dumps([
            {
                "type": "result",
                "subtype": "success",
                "result": json.dumps(payload),
                "session_id": "real-shannon-session",
                "total_cost_usd": 0.02,
                "usage": {"input_tokens": 11, "output_tokens": 7},
            }
        ]),
        stderr="",
        duration_ms=123,
    )

    with patch("megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
        run_shannon_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="return json",
        )

    command = run_command.call_args.args[0]
    env = run_command.call_args.kwargs["env"]
    assert command[:6] == ["/bin/su", "-m", "-s", "/bin/bash", "nobody", "-c"]
    assert " shannon -p " in command[6]
    assert "claude -p" not in command[6]
    assert "--bare" in command[6]
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert env["HOME"] == str(tmp_path / "project" / ".megaplan" / "shannon-home")
    assert env["MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_COUNT"] == "4"
    assert (tmp_path / "project" / ".megaplan" / "shannon-home" / ".claude.json").exists()

def test_run_shannon_step_readiness_probe_resumes_before_real_prompt(
    tmp_path: Path,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers.shannon import run_shannon_step
    from megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    final_raw = json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps(payload),
            "session_id": "real-shannon-session",
            "total_cost_usd": 0.02,
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }
    ])
    calls: list[list[str]] = []
    sleeps: list[float] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append(command)
        if len(calls) == 1:
            assert kwargs["timeout"] == 120
            return CommandResult(
                command=command,
                cwd=tmp_path,
                returncode=0,
                stdout=json.dumps({"result": "READY"}),
                stderr="",
                duration_ms=10,
            )
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=final_raw,
            stderr="",
            duration_ms=123,
        )

    with (
        patch("megaplan.workers.shannon.random.choice", return_value="Handshake test prompt. Reply READY."),
        patch("megaplan.workers.shannon.random.random", return_value=0.0),
        patch("megaplan.workers.shannon.random.randrange", side_effect=[13, 149]),
        patch("megaplan.workers.shannon.time.sleep", side_effect=sleeps.append),
        patch("megaplan.workers.shannon.run_command", side_effect=fake_run_command),
    ):
        result = run_shannon_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="return json",
            session_agent="claude",
        )

    assert len(calls) == 2
    assert calls[0][2] == "Handshake test prompt. Reply READY."
    assert sleeps == [1.3, 14.9]
    assert "--session-id" in calls[0]
    session_id = calls[0][calls[0].index("--session-id") + 1]
    assert "--resume" in calls[1]
    assert calls[1][calls[1].index("--resume") + 1] == session_id
    assert "Read the full megaplan phase prompt from this file" in calls[1][2]
    assert result.payload == payload

def test_run_shannon_step_can_skip_readiness_probe_for_new_claude_session(
    tmp_path: Path,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers.shannon import run_shannon_step
    from megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    raw = json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps(payload),
            "session_id": "real-shannon-session",
            "total_cost_usd": 0.02,
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }
    ])
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=raw,
        stderr="",
        duration_ms=123,
    )

    with (
        patch("megaplan.workers.shannon.random.random", return_value=0.99),
        patch("megaplan.workers.shannon.time.sleep") as sleep,
        patch("megaplan.workers.shannon.run_command", return_value=fake_result) as run_command,
    ):
        result = run_shannon_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="return json",
            session_agent="claude",
        )

    assert run_command.call_count == 1
    command = run_command.call_args.args[0]
    assert "--session-id" in command
    assert "--resume" not in command
    assert "Read the full megaplan phase prompt from this file" in command[2]
    sleep.assert_not_called()
    assert result.payload == payload

def test_run_shannon_step_repeats_execute_batch_scope_after_schema(
    tmp_path: Path,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers.shannon import run_shannon_step
    from megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "output": "done",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": [],
        "sense_check_acknowledgments": [],
    }
    raw = json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps(payload),
            "session_id": "real-shannon-session",
            "total_cost_usd": 0.02,
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }
    ])
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=raw,
        stderr="",
        duration_ms=123,
    )
    prompt_override = "\n".join(
        [
            "Execute batch 2.",
            "- Only produce `task_updates` for these tasks: [T2]",
            "- Only produce `sense_check_acknowledgments` for these sense checks: [SC2]",
        ]
    )

    with patch("megaplan.workers.shannon.run_command", return_value=fake_result):
        run_shannon_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override=prompt_override,
        )

    prompt_text = (plan_dir / "execute_shannon_prompt.txt").read_text(encoding="utf-8")
    assert "EXECUTE BATCH OUTPUT SCOPE" in prompt_text
    assert "exactly these task IDs and no others: T2" in prompt_text
    assert "exactly these sense check IDs and no others: SC2" in prompt_text

def test_run_shannon_step_uses_bypass_permissions_for_non_execute_phases(
    tmp_path: Path,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers.shannon import run_shannon_step
    from megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    raw = json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps(payload),
            "session_id": "real-shannon-session",
            "total_cost_usd": 0.02,
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }
    ])
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=raw,
        stderr="",
        duration_ms=123,
    )

    with patch("megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
        run_shannon_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="return json",
        )

    command = run_command.call_args.args[0]
    assert "--permission-mode" in command
    assert "bypassPermissions" in command
    assert "--dangerously-skip-permissions" in command
    assert "--allow-dangerously-skip-permissions" in command

def test_shannon_worker_patches_known_timeout_and_tool_use_defects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.workers.shannon import _ensure_shannon_parent_timeout_control

    package_dir = tmp_path / "shannon-package"
    bin_dir = package_dir / "bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / "shannon"
    executable.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    entrypoint = package_dir / "index.ts"
    entrypoint.write_text(
        "\n".join(
            [
                "const TURN_TIMEOUT_MS = 180_000;",
                "export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {",
                "  return [];",
                "}",
                "export async function runShannon(options: CliOptions) {",
                "  const tmuxSession = 's';",
                "  const prompt = 'p';",
                "  await runCommand([",
                '    "tmux",',
                '    "new-session",',
                '    "-d",',
                '    "-s",',
                "    tmuxSession,",
                '    "-c",',
                "    options.cwd,",
                '    "claude",',
                "    ...options.claudeArgs,",
                "    prompt,",
                "  ]);",
                "  let launchedWithPrompt = true;",
                "}",
                "export function assistantReplyFromRows(prompt, rows) {",
                "  for (const row of rows) {",
                '    if (textFromContent(row.message.content)) return row;',
                "  }",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("megaplan.workers.shannon.shutil.which", lambda name: str(executable))

    _ensure_shannon_parent_timeout_control()

    patched = entrypoint.read_text(encoding="utf-8")
    assert "SHANNON_TURN_TIMEOUT_MS" in patched
    assert 'row.message?.stop_reason === "tool_use"' in patched
    assert "function rootSafeClaudeArgs(args: string[]): string[]" in patched
    assert 'arg === "--dangerously-skip-permissions"' in patched
    assert 'filtered.push("--permission-mode", "auto")' in patched
    assert 'arg === "--session-id" || arg === "--resume"' in patched
    assert "async function maybeSendStartupEnterKeys(tmuxSession: string)" in patched
    assert "MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_COUNT" in patched
    assert "void maybeSendStartupEnterKeys(tmuxSession);" in patched
    assert '["claude", "-p", ...rootSafeClaudeArgs(options.claudeArgs), prompt]' in patched
    assert (package_dir / "index.ts.bak.megaplan-shannon").exists()

def test_shannon_worker_heals_partially_patched_entrypoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: a previous megaplan patch left ``rootSafeClaudeArgs``
    in place but never inserted ``maybeSendStartupEnterKeys`` because both
    helpers were bundled behind a single gate.  The next patch pass must
    insert the missing helper so the dangling call site resolves.
    """
    from megaplan.workers.shannon import _ensure_shannon_parent_timeout_control

    package_dir = tmp_path / "shannon-package"
    bin_dir = package_dir / "bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / "shannon"
    executable.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    entrypoint = package_dir / "index.ts"
    # Pre-patched state: an older megaplan only knew about isRootProcess
    # and rootSafeClaudeArgs, and still injected the maybeSendStartupEnterKeys
    # call site below.  The function definition is intentionally absent.
    entrypoint.write_text(
        "\n".join(
            [
                "const TURN_TIMEOUT_MS = Number(Bun.env.SHANNON_TURN_TIMEOUT_MS ?? 900_000);",
                "function isRootProcess() {",
                '  return typeof process.getuid === "function" && process.getuid() === 0;',
                "}",
                "",
                "function rootSafeClaudeArgs(args: string[]): string[] {",
                "  if (!isRootProcess()) return args;",
                "  const filtered: string[] = [];",
                "  return filtered;",
                "}",
                "",
                "export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {",
                "  return [];",
                "}",
                "export async function runShannon(options: CliOptions) {",
                "  const tmuxSession = 's';",
                "  const prompt = 'p';",
                "  const claudeLaunchArgs = isRootProcess()",
                '    ? ["claude", "-p", ...rootSafeClaudeArgs(options.claudeArgs), prompt]',
                '    : ["claude", ...options.claudeArgs, prompt];',
                "  await runCommand([",
                '    "tmux",',
                '    "new-session",',
                '    "-d",',
                '    "-s",',
                "    tmuxSession,",
                '    "-c",',
                "    options.cwd,",
                "    ...claudeLaunchArgs,",
                "  ]);",
                "  void maybeSendStartupEnterKeys(tmuxSession);",
                "",
                "  let launchedWithPrompt = true;",
                "}",
                "export function assistantReplyFromRows(prompt, rows) {",
                "  for (const row of rows) {",
                '    if (row.message?.stop_reason === "tool_use") continue;',
                '    if (textFromContent(row.message.content)) return row;',
                "  }",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("megaplan.workers.shannon.shutil.which", lambda name: str(executable))

    _ensure_shannon_parent_timeout_control()

    patched = entrypoint.read_text(encoding="utf-8")
    # All three helper function definitions must be present after the heal.
    assert "function isRootProcess()" in patched
    assert "function rootSafeClaudeArgs(args: string[]): string[]" in patched
    assert "async function maybeSendStartupEnterKeys(tmuxSession: string)" in patched
    # The pre-existing call site is preserved.
    assert "void maybeSendStartupEnterKeys(tmuxSession);" in patched
    # No duplicates were inserted for helpers that were already present.
    assert patched.count("function isRootProcess()") == 1
    assert patched.count("function rootSafeClaudeArgs(args: string[]): string[]") == 1
    assert patched.count("async function maybeSendStartupEnterKeys(tmuxSession: string)") == 1

def test_run_shannon_step_mock_worker_no_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers.shannon import run_shannon_step

    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    # Even with no shannon/tmux/claude on PATH, mock mode works
    result = run_shannon_step("plan", state, plan_dir, root=tmp_path, fresh=True)
    assert isinstance(result, WorkerResult)
    assert result.payload is not None
    assert "output" in result.payload or "plan" in result.payload

def test_shannon_accepted_in_agent_choice_surfaces() -> None:
    """All --agent choice surfaces accept 'shannon'."""
    from megaplan.types import KNOWN_AGENTS
    assert "shannon" in KNOWN_AGENTS
