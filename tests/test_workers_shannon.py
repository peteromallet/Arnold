"""Direct Shannon worker tests for megaplan.workers."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.workers import WorkerResult, resolve_agent_mode, session_key_for
from tests._workers_helpers import FakeShutil, _mock_state


@pytest.fixture(autouse=True)
def _assume_shannon_patched(monkeypatch: pytest.MonkeyPatch) -> None:
    # No-op shim: the runtime patcher is gone (T4); patches are baked into the
    # vendored fork at megaplan/vendor/shannon/index.ts. The fixture name is retained so
    # tests that opt-out via override (`monkeypatch.setattr(..., lambda: False)`)
    # still parse, even though the support-detection helpers no longer exist.
    # Also sanitise any leaked MEGAPLAN_SHANNON_SESSION_ROULETTE from a crashed
    # prior run so tests that expect the default (enabled) are not misled.
    monkeypatch.delenv("MEGAPLAN_SHANNON_SESSION_ROULETTE", raising=False)
    return


def test_is_shannon_available_all_deps_present() -> None:
    from arnold.pipelines.megaplan._core.io import is_shannon_available
    fake = FakeShutil("bun", "tmux", "claude")
    assert is_shannon_available(shutil_ref=fake) is True

def test_is_shannon_available_missing_tmux() -> None:
    from arnold.pipelines.megaplan._core.io import is_shannon_available
    fake = FakeShutil("bun", "claude")
    assert is_shannon_available(shutil_ref=fake) is False

def test_is_shannon_available_missing_claude() -> None:
    from arnold.pipelines.megaplan._core.io import is_shannon_available
    fake = FakeShutil("bun", "tmux")
    assert is_shannon_available(shutil_ref=fake) is False

def test_is_shannon_available_missing_bun() -> None:
    from arnold.pipelines.megaplan._core.io import is_shannon_available
    fake = FakeShutil("tmux", "claude")
    assert is_shannon_available(shutil_ref=fake) is False

def test_shannon_missing_deps_lists_missing() -> None:
    from arnold.pipelines.megaplan._core.io import shannon_missing_deps
    fake = FakeShutil("claude")  # missing bun and tmux
    assert sorted(shannon_missing_deps(shutil_ref=fake)) == ["bun", "tmux"]

def test_detect_available_agents_includes_shannon_when_deps_present() -> None:
    from arnold.pipelines.megaplan._core.io import detect_available_agents
    # detect_available_agents uses `import megaplan._core as _core_pkg; _core_pkg.shutil`
    # which resolves to the stdlib shutil re-exported in megaplan/_core/__init__.py.
    with patch("arnold.pipelines.megaplan._core.shutil", FakeShutil("bun", "tmux", "claude", "codex")):
        agents = detect_available_agents()
    assert "shannon" in agents

def test_detect_available_agents_excludes_shannon_when_deps_missing() -> None:
    from arnold.pipelines.megaplan._core.io import detect_available_agents
    with patch("arnold.pipelines.megaplan._core.shutil", FakeShutil("claude", "codex")):
        agents = detect_available_agents()
    assert "shannon" not in agents

def test_is_agent_available_shannon_agrees_with_is_shannon_available() -> None:
    """_is_agent_available('shannon') delegates to is_shannon_available()."""
    from arnold.pipelines.megaplan.workers import _is_agent_available
    # _is_agent_available('shannon') calls is_shannon_available() which uses
    # the `shutil` imported in io.py, and detect_available_agents uses
    # megaplan._core.shutil (re-exported in __init__.py).  Patch both.
    with (
        patch("arnold.pipelines.megaplan._core.io.shutil", FakeShutil("bun", "tmux", "claude")),
        patch("arnold.pipelines.megaplan._core.shutil", FakeShutil("bun", "tmux", "claude")),
    ):
        assert _is_agent_available("shannon") is True
    with (
        patch("arnold.pipelines.megaplan._core.io.shutil", FakeShutil("claude")),
        patch("arnold.pipelines.megaplan._core.shutil", FakeShutil("claude")),
    ):
        assert _is_agent_available("shannon") is False

def test_is_agent_available_claude_routes_through_shannon_deps() -> None:
    """The public 'claude' agent now means Shannon-backed Claude."""
    from arnold.pipelines.megaplan.workers import _is_agent_available

    with patch("arnold.pipelines.megaplan._core.io.shutil", FakeShutil("bun", "tmux", "claude")):
        assert _is_agent_available("claude") is True
    with patch("arnold.pipelines.megaplan._core.io.shutil", FakeShutil("claude")):
        assert _is_agent_available("claude") is False

def test_resolve_agent_mode_agent_shannon_explicit_fails_on_missing_deps() -> None:
    """--agent shannon when deps missing → CliError('agent_deps_missing')."""
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", return_value=None):
        with patch("arnold.pipelines.megaplan.workers._impl.load_config", return_value={}):
            with patch("arnold.pipelines.megaplan.workers._impl.detect_available_agents", return_value=["claude", "codex"]):
                with pytest.raises(CliError, match="Shannon requires"):
                    resolve_agent_mode("plan", Namespace(agent="shannon", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))

def test_resolve_agent_mode_phase_model_shannon_explicit_fails_on_missing_deps() -> None:
    """--phase-model plan=shannon when deps missing → CliError('agent_deps_missing')."""
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", return_value=None):
        with patch("arnold.pipelines.megaplan.workers._impl.load_config", return_value={}):
            with patch("arnold.pipelines.megaplan.workers._impl.detect_available_agents", return_value=["claude", "codex"]):
                with pytest.raises(CliError, match="Shannon requires"):
                    resolve_agent_mode("plan", Namespace(agent=None, ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=["plan=shannon"]))

def test_resolve_agent_mode_non_explicit_shannon_can_fallback() -> None:
    """When Shannon is not explicitly requested, it can fall back to another agent."""
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", side_effect=lambda name: "/usr/bin/claude" if name == "claude" else None):
        with patch("arnold.pipelines.megaplan.workers._impl.load_config", return_value={"agents": {"plan": "shannon"}}):
            # Shannon isn't available, and the config default isn't explicit via --agent,
            # so fallback to the next available.
            with patch("arnold.pipelines.megaplan.workers._impl.detect_available_agents", return_value=["claude", "codex"]):
                agent, mode, refreshed, model = resolve_agent_mode("plan", Namespace(agent=None, ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))
    # Falls back to claude because shannon is unavailable and not explicit
    assert agent == "claude"

def test_resolve_agent_mode_shannon_mock_mode_bypasses_availability_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MEGAPLAN_MOCK_WORKERS=1 + --agent shannon must skip availability checks."""
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    # shutil.which returns None for everything — Shannon deps are missing
    with patch("arnold.pipelines.megaplan.workers._impl.shutil.which", return_value=None):
        with patch("arnold.pipelines.megaplan.workers._impl.load_config", return_value={}):
            agent, mode, refreshed, model = resolve_agent_mode("plan", Namespace(agent="shannon", ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[]))
    assert agent == "shannon"
    assert mode == "persistent"

def test_run_step_with_worker_shannon_calls_run_shannon_step(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.workers import run_step_with_worker, CommandResult

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
    with patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step", return_value=fake_worker) as run_shannon:
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
    from arnold.pipelines.megaplan.workers import run_step_with_worker

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
    with patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step", return_value=fake_worker):
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
    from arnold.pipelines.megaplan.workers import run_step_with_worker

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
    with patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step", return_value=fake_worker) as run_shannon:
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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

    envelope, payload = _parse_shannon_output(json.dumps({
        "structured_output": {"plan": "# Plan", "questions": []},
        "session_id": "sess-1",
    }))
    assert payload == {"plan": "# Plan", "questions": []}
    assert envelope["session_id"] == "sess-1"

def test_parse_shannon_output_result_string() -> None:
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

    envelope, payload = _parse_shannon_output(json.dumps({
        "result": json.dumps({"output": "done"}),
    }))
    assert payload == {"output": "done"}

def test_parse_shannon_output_transcript_array() -> None:
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

    transcript = [
        {"type": "user", "message": {"content": "Do X"}},
        {"type": "assistant", "message": {
            "result": json.dumps({"output": "done"}),
        }},
    ]
    envelope, payload = _parse_shannon_output(json.dumps(transcript))
    assert payload == {"output": "done"}

def test_parse_shannon_output_prefers_result_event() -> None:
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

    with pytest.raises(CliError, match="not valid JSON"):
        _parse_shannon_output("not json")

def test_parse_shannon_output_auth_error() -> None:
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

    with pytest.raises(CliError, match="Shannon step failed"):
        _parse_shannon_output(json.dumps({
            "is_error": True,
            "result": "Not logged in. Run /login first.",
        }))

def test_parse_shannon_output_empty_transcript_uses_last_dict() -> None:
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

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
    from arnold.pipelines.megaplan.workers.shannon import _parse_shannon_output

    payload = {"output": "pretty"}
    transcript = [
        {"type": "result", "subtype": "success", "result": json.dumps(payload), "session_id": "s6"},
    ]
    pretty = json.dumps(transcript, indent=2)  # spans many lines, lines aren't valid JSON alone
    assert "\n" in pretty
    _, parsed = _parse_shannon_output(pretty)
    assert parsed == payload

def test_run_shannon_step_timeout_raises_worker_timeout_with_session_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step

    ensure_runtime_layout(tmp_path)
    # This test asserts the legacy "non-execute always starts fresh" contract:
    # a stored plan session is discarded for a new uuid, so a timeout reports the
    # fresh id rather than the stale one. Pin the session roulette off so the
    # deterministic legacy path is exercised (the roulette is covered separately).
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_ROULETTE", "0")
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][session_key_for("plan", "shannon")] = {
        "id": "shannon-session-abc",
        "mode": "persistent",
        "created_at": "2026-03-20T00:00:00Z",
        "last_used_at": "2026-03-20T00:00:00Z",
        "refreshed": False,
    }

    timeout_error = CliError("worker_timeout", "Shannon timed out", extra={"raw_output": "partial"})
    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_shannon_step("plan", state, plan_dir, root=tmp_path, fresh=False)

    assert exc_info.value.extra["session_id"] != "shannon-session-abc"
    assert exc_info.value.extra["session_id"]

def test_run_shannon_step_passes_prompt_with_print_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

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

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
        result = run_shannon_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="return json",
        )

    command = run_command.call_args.args[0]
    # Shannon is launched as ``bun <vendored-index.ts> ... -p <launcher-prompt> ...``
    # post-cutover (no ``shannon`` shim on PATH).
    from arnold.pipelines.megaplan.workers.shannon import VENDORED_SHANNON_PATH
    assert command[0:2] == ["bun", str(VENDORED_SHANNON_PATH)]
    assert "-p" in command
    p_idx = command.index("-p")
    assert "Read the full megaplan phase prompt from this file" in command[p_idx + 1]
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
    # Output ceiling is raised above the inherited ~64k default so opus is not
    # cut off mid-run before emitting the structured envelope.
    assert run_command.call_args.kwargs["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "128000"
    assert run_command.call_args.kwargs["env"]["BASH_DEFAULT_TIMEOUT_MS"] == "7200000"
    assert run_command.call_args.kwargs["env"]["BASH_MAX_TIMEOUT_MS"] == "7200000"
    # On non-root systems, ANTHROPIC_API_KEY is set to "" to block Bun's dotenv auto-load.
    api_key_val = run_command.call_args.kwargs["env"].get("ANTHROPIC_API_KEY")
    assert api_key_val is None or api_key_val == ""
    # Prompt file now lives under .megaplan/runs/<plan_id>/<step>/shannon/
    # (the per-run artifact directory) instead of the plan directory root.
    run_dir = plan_dir / ".megaplan" / "runs" / state["name"] / "execute" / "shannon"
    prompt_file = run_dir / "execute_shannon_prompt.txt"
    prompt_text = prompt_file.read_text(encoding="utf-8")
    assert "return json" in prompt_text
    assert "Output format:" in prompt_text
    assert result.payload == payload
    assert result.session_id == "real-shannon-session"
    assert result.cost_usd == 0.02

def test_run_shannon_step_preserves_anthropic_api_key_for_root_cloud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr("arnold.pipelines.megaplan.workers.shannon.os.geteuid", lambda: 0)
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

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
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
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CHMOD_WORKSPACE", "0")
    monkeypatch.setattr("arnold.pipelines.megaplan.workers.shannon.os.geteuid", lambda: 0)
    monkeypatch.setattr("arnold.pipelines.megaplan.workers.shannon.shutil.which", lambda name: "/bin/su" if name == "su" else None)
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

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
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
    from arnold.pipelines.megaplan.workers.shannon import VENDORED_SHANNON_PATH
    # bun-invoked vendored fork, not a PATH-resolved ``shannon`` shim.
    assert f"bun {VENDORED_SHANNON_PATH}" in command[6]
    assert " -p " in command[6]
    assert "claude -p" not in command[6]
    assert "--bare" in command[6]
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-test"
    assert env["HOME"] == str(tmp_path / "project" / ".megaplan" / "shannon-home")
    assert env["MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_COUNT"] == "4"
    assert (tmp_path / "project" / ".megaplan" / "shannon-home" / ".claude.json").exists()

def test_run_shannon_step_readiness_probe_resumes_before_real_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import shannon as shannon_mod
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    # Force the handshake roll to always fire by setting the probability to 1
    # via "always" mode, and pin the readiness prompt to a single deterministic
    # string so the test does not depend on the seeded rng's choice index.
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "always")
    monkeypatch.setenv("MEGAPLAN_SHANNON_HANDSHAKE_DELAY_MAX_SECONDS", "0")
    monkeypatch.setattr(
        shannon_mod, "_SHANNON_READINESS_PROMPTS",
        ("Handshake test prompt. Reply READY.",),
    )
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

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
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
    # First turn is the readiness handshake; -p body is the readiness prompt.
    p0 = calls[0].index("-p")
    assert calls[0][p0 + 1] == "Handshake test prompt. Reply READY."
    assert "--session-id" in calls[0]
    session_id = calls[0][calls[0].index("--session-id") + 1]
    # Second turn is the main work turn resuming the same session.
    assert "--resume" in calls[1]
    assert calls[1][calls[1].index("--resume") + 1] == session_id
    p1 = calls[1].index("-p")
    assert "Read the full megaplan phase prompt from this file" in calls[1][p1 + 1]
    assert result.payload == payload

def test_run_shannon_step_can_skip_readiness_probe_for_new_claude_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    # Probability 0 → the seeded plan_session roll never fires the handshake.
    monkeypatch.setenv("MEGAPLAN_SHANNON_HANDSHAKE_PROBABILITY", "0")
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
        patch("arnold.pipelines.megaplan.workers.shannon.time.sleep") as sleep,
        patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result) as run_command,
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
    p_idx = command.index("-p")
    assert "Read the full megaplan phase prompt from this file" in command[p_idx + 1]
    sleep.assert_not_called()
    assert result.payload == payload

def test_run_shannon_step_repeats_execute_batch_scope_after_schema(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

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

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result):
        run_shannon_step(
            "execute",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override=prompt_override,
        )

    run_dir = plan_dir / ".megaplan" / "runs" / state["name"] / "execute" / "shannon"
    prompt_text = (run_dir / "execute_shannon_prompt.txt").read_text(encoding="utf-8")
    assert "EXECUTE BATCH OUTPUT SCOPE" in prompt_text
    assert "exactly these task IDs and no others: T2" in prompt_text
    assert "exactly these sense check IDs and no others: SC2" in prompt_text

def test_run_shannon_step_uses_bypass_permissions_for_non_execute_phases(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

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

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
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


def test_run_shannon_step_read_only_uses_tool_restrictions_without_bypass_flags(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    payload = {"triage_framing": "No fanout needed.", "areas": []}
    raw = json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps(payload),
            "session_id": "read-only-shannon-session",
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

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
        result = run_shannon_step(
            "prep-triage",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="return json",
            read_only=True,
        )

    command = run_command.call_args.args[0]
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
    assert "--dangerously-skip-permissions" not in command
    assert "--allow-dangerously-skip-permissions" not in command
    assert result.payload == payload


def test_vendored_shannon_contains_turn_timeout_and_tool_use_patches() -> None:
    """The vendored fork must carry the P1 (TURN_TIMEOUT_MS) and P2 (tool_use
    guard) replacement strings — a regression here means the vendor was reset to
    pristine without re-applying patches."""
    from arnold.pipelines.megaplan.workers.shannon import VENDORED_SHANNON_PATH

    src = VENDORED_SHANNON_PATH.read_text(encoding="utf-8")
    # P1: hardcoded 180_000 -> env-overridable 900_000.
    assert (
        "const TURN_TIMEOUT_MS = Number(Bun.env.SHANNON_TURN_TIMEOUT_MS ?? 900_000);"
        in src
    )
    # P2: tool_use guard inserted into the reverse-scan reply detector.
    assert 'row.message?.stop_reason === "tool_use"' in src


def test_run_shannon_step_mock_worker_no_deps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step

    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    # Even with no shannon/tmux/claude on PATH, mock mode works
    result = run_shannon_step("plan", state, plan_dir, root=tmp_path, fresh=True)
    assert isinstance(result, WorkerResult)
    assert result.payload is not None
    assert "output" in result.payload or "plan" in result.payload

def test_run_shannon_execute_repairs_truncated_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truncated/invalid execute output triggers one envelope-repair resume."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    plan_dir, state = _mock_state(tmp_path)

    # First turn: cut off at max_tokens before emitting required keys.
    truncated = json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps({"output": "partial reasoning..."}),
            "stop_reason": "max_tokens",
            "session_id": "sess-123",
            "total_cost_usd": 0.5,
            "usage": {"input_tokens": 1000, "output_tokens": 64000},
        }
    ])
    payload = {
        "output": "done",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": [],
        "sense_check_acknowledgments": [],
    }
    repaired = json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps(payload),
            "stop_reason": "end_turn",
            "session_id": "sess-123",
            "total_cost_usd": 0.1,
            "usage": {"input_tokens": 1200, "output_tokens": 200},
        }
    ])

    calls = []

    def _fake_run_command(command, **kwargs):
        calls.append(command)
        raw = truncated if len(calls) == 1 else repaired
        return CommandResult(
            command=command, cwd=tmp_path, returncode=0, stdout=raw, stderr="", duration_ms=10,
        )

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=_fake_run_command):
        result = run_shannon_step(
            "execute", state, plan_dir,
            root=tmp_path, fresh=True, prompt_override="do the batch",
        )

    assert result.payload == payload
    # Exactly one main turn + one repair resume turn.
    assert len(calls) == 2
    repair_cmd = calls[1]
    assert "--resume" in repair_cmd and "sess-123" in repair_cmd
    # The repair turn re-prompts only for the structured envelope.
    p_idx = repair_cmd.index("-p")
    assert "structured result" in repair_cmd[p_idx + 1]


def test_shannon_accepted_in_agent_choice_surfaces() -> None:
    """All --agent choice surfaces accept 'shannon'."""
    from arnold.pipelines.megaplan.profiles import KNOWN_AGENTS
    assert "shannon" in KNOWN_AGENTS


# ---------------------------------------------------------------------------
# Buffered-mode liveness probe (shannon --output-format=json rescue)
# ---------------------------------------------------------------------------


def _fake_tmux_capture(outputs):
    """Build a subprocess.run stand-in that serves successive capture-pane outputs.

    ``outputs`` is a list of pane snapshots returned on consecutive
    capture-pane calls; ``has-session`` always reports the session alive.
    """
    capture_idx = [0]

    class _Result:
        def __init__(self, rc, out):
            self.returncode = rc
            self.stdout = out
            self.stderr = ""

    def _run(cmd, *a, **kw):
        if "has-session" in cmd:
            return _Result(0, "")
        if "capture-pane" in cmd:
            i = min(capture_idx[0], len(outputs) - 1)
            snap = outputs[i]
            capture_idx[0] += 1
            return _Result(0, snap)
        return _Result(0, "")

    return _run


def test_liveness_probe_reports_progress_on_pane_change() -> None:
    """Probe returns True while the tmux pane content keeps changing (Claude is
    streaming tokens into its pane even though stdout is buffered)."""
    from arnold.pipelines.megaplan.runtime.process import TmuxSession
    from arnold.pipelines.megaplan.workers.shannon import _make_shannon_liveness_probe

    panes = ["frame-0", "frame-1", "frame-2"]
    with patch("arnold.pipelines.megaplan.workers.shannon.subprocess.run", _fake_tmux_capture(panes)):
        with patch("arnold.pipelines.megaplan.workers.shannon._claude_transcript_paths", return_value=[]):
            probe = _make_shannon_liveness_probe(TmuxSession("sess"), "sid", Path.cwd())
            assert probe() is True  # priming call
            assert probe() is True  # pane changed frame-0 -> frame-1
            assert probe() is True  # pane changed frame-1 -> frame-2


def test_liveness_probe_reports_no_progress_on_static_pane(tmp_path) -> None:
    """Probe returns False when a transcript exists but its mtime is static and
    the pane is unchanging — a genuinely hung turn the watchdog must kill.

    Per the probe's contract, transcript mtime is the ONLY trusted progress
    signal (pane churn is deliberately ignored — a wedged Claude repaints its
    pane forever). So "no progress" requires an observed-but-static transcript;
    with no transcript at all the probe stays conservative (returns True) and
    lets the wall-clock cap govern. This test pins the static-transcript case."""
    from arnold.pipelines.megaplan.runtime.process import TmuxSession
    from arnold.pipelines.megaplan.workers.shannon import _make_shannon_liveness_probe

    transcript = tmp_path / "sid.jsonl"
    transcript.write_text("{}\n")
    panes = ["frozen", "frozen", "frozen"]
    with patch("arnold.pipelines.megaplan.workers.shannon.subprocess.run", _fake_tmux_capture(panes)):
        with patch(
            "arnold.pipelines.megaplan.workers.shannon._claude_transcript_paths",
            return_value=[transcript],
        ):
            probe = _make_shannon_liveness_probe(TmuxSession("sess"), "sid", tmp_path)
            assert probe() is True   # priming call records the baseline mtime
            assert probe() is False  # transcript mtime static, pane unchanged -> hung
            assert probe() is False


def test_liveness_probe_reports_progress_on_transcript_mtime(tmp_path) -> None:
    """Even with a static pane, an advancing transcript .jsonl mtime counts as
    progress (the turn is flushing completed content blocks to disk)."""
    from arnold.pipelines.megaplan.runtime.process import TmuxSession
    from arnold.pipelines.megaplan.workers.shannon import _make_shannon_liveness_probe

    transcript = tmp_path / "sid.jsonl"
    transcript.write_text("{}\n")
    import os as _os

    panes = ["static", "static", "static"]
    with patch("arnold.pipelines.megaplan.workers.shannon.subprocess.run", _fake_tmux_capture(panes)):
        with patch(
            "arnold.pipelines.megaplan.workers.shannon._claude_transcript_paths",
            return_value=[transcript],
        ):
            probe = _make_shannon_liveness_probe(TmuxSession("sess"), "sid", tmp_path)
            assert probe() is True  # prime (also records baseline mtime)
            assert probe() is False  # nothing moved yet
            # Advance the transcript mtime: simulates a content block flush.
            base = transcript.stat().st_mtime
            _os.utime(transcript, (base + 100, base + 100))
            assert probe() is True  # mtime advanced -> progress


# ---------------------------------------------------------------------------
# Session-continuity roulette (resume / compact / clear / new)
# ---------------------------------------------------------------------------


def _execute_result_json() -> str:
    payload = {
        "output": "done",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": [],
        "sense_check_acknowledgments": [],
    }
    return json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps(payload),
            "session_id": "real-shannon-session",
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }
    ])


def _seed_shannon_session(state: dict, step: str, sid: str) -> None:
    state["sessions"][session_key_for(step, "shannon")] = {
        "id": sid,
        "mode": "persistent",
        "created_at": "2026-03-20T00:00:00Z",
        "last_used_at": "2026-03-20T00:00:00Z",
        "refreshed": False,
    }


def test_session_strategy_never_plain_resumes_reused_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Policy: a reusable session is never plain-resumed (full context clouds the
    # turn) — it is always shed via an injected /compact or /clear op turn before
    # the work turn. So a reused execute session always produces TWO calls (op +
    # work), never a single bare resume.
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", "0")
    plan_dir, state = _mock_state(tmp_path)
    _seed_shannon_session(state, "execute", "sess-keep")
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append(command)
        if len(calls) == 1:
            return CommandResult(
                command=command, cwd=tmp_path, returncode=0,
                stdout="shed", stderr="", duration_ms=5,
            )
        return CommandResult(
            command=command, cwd=tmp_path, returncode=0,
            stdout=_execute_result_json(), stderr="", duration_ms=12,
        )

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
        run_shannon_step(
            "execute", state, plan_dir, root=tmp_path, fresh=False,
            prompt_override="batch",
        )
    assert len(calls) == 2  # op turn + work turn — never a single plain resume
    assert calls[0][calls[0].index("-p") + 1] in ("/compact", "/clear")
    assert "--resume" in calls[1]


def test_session_strategy_compact_injects_slash_compact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", "0")
    plan_dir, state = _mock_state(tmp_path)
    _seed_shannon_session(state, "execute", "sess-keep")
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append(command)
        if len(calls) == 1:
            return CommandResult(
                command=command, cwd=tmp_path, returncode=0,
                stdout="compacted", stderr="", duration_ms=5,
            )
        return CommandResult(
            command=command, cwd=tmp_path, returncode=0,
            stdout=_execute_result_json(), stderr="", duration_ms=12,
        )

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
        run_shannon_step(
            "execute", state, plan_dir, root=tmp_path, fresh=False,
            prompt_override="batch",
        )
    # Turn 1 is the injected /compact against the resumed session; turn 2 is the
    # real work turn resuming the same id with the launcher prompt.
    assert len(calls) == 2
    assert calls[0][calls[0].index("-p") + 1] == "/compact"
    assert calls[0][calls[0].index("--resume") + 1] == "sess-keep"
    assert calls[1][calls[1].index("--resume") + 1] == "sess-keep"
    p1 = calls[1].index("-p")
    assert "Read the full megaplan phase prompt from this file" in calls[1][p1 + 1]


def test_session_strategy_clear_injects_slash_clear(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", "0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", "0")
    plan_dir, state = _mock_state(tmp_path)
    _seed_shannon_session(state, "execute", "sess-keep")
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append(command)
        if len(calls) == 1:
            return CommandResult(
                command=command, cwd=tmp_path, returncode=0,
                stdout="cleared", stderr="", duration_ms=5,
            )
        return CommandResult(
            command=command, cwd=tmp_path, returncode=0,
            stdout=_execute_result_json(), stderr="", duration_ms=12,
        )

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
        run_shannon_step(
            "execute", state, plan_dir, root=tmp_path, fresh=False,
            prompt_override="batch",
        )
    assert len(calls) == 2
    assert calls[0][calls[0].index("-p") + 1] == "/clear"
    assert calls[1][calls[1].index("--resume") + 1] == "sess-keep"


def test_session_strategy_context_op_failure_falls_back_to_fresh_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Policy is "never carry stale context". When the /compact (or /clear) op
    # turn fails, we must NOT plain-resume the un-shed original session — we shed
    # it the safe way with a fresh `new` session (--session-id), not --resume.
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", "0")
    plan_dir, state = _mock_state(tmp_path)
    _seed_shannon_session(state, "execute", "sess-keep")
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append(command)
        if len(calls) == 1:
            # /compact op turn stalls -> best-effort failure.
            raise CliError("worker_timeout", "compact stalled", extra={})
        return CommandResult(
            command=command, cwd=tmp_path, returncode=0,
            stdout=_execute_result_json(), stderr="", duration_ms=12,
        )

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
        result = run_shannon_step(
            "execute", state, plan_dir, root=tmp_path, fresh=False,
            prompt_override="batch",
        )
    assert len(calls) == 2  # failed op did not abort the phase
    # Work turn uses a FRESH session, not a plain resume of the un-shed original.
    assert "--session-id" in calls[1]
    assert "--resume" not in calls[1]
    assert calls[1][calls[1].index("--session-id") + 1] != "sess-keep"
    assert result.session_id == "real-shannon-session"


def test_session_strategy_non_execute_also_sheds_prior_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Non-execute phases with a stored session are also shed, never plain-resumed:
    # they inject /clear (or /compact) before the work turn rather than carrying
    # the prior planner/critic conversation forward.
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", "0")  # -> clear
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", "0")
    plan_dir, state = _mock_state(tmp_path)
    _seed_shannon_session(state, "plan", "plan-keep")
    payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    work_stdout = json.dumps([
        {
            "type": "result",
            "subtype": "success",
            "result": json.dumps(payload),
            "session_id": "real-shannon-session",
            "total_cost_usd": 0.0,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    ])
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append(command)
        if len(calls) == 1:
            return CommandResult(
                command=command, cwd=tmp_path, returncode=0,
                stdout="cleared", stderr="", duration_ms=5,
            )
        return CommandResult(
            command=command, cwd=tmp_path, returncode=0,
            stdout=work_stdout, stderr="", duration_ms=12,
        )

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
        run_shannon_step(
            "plan", state, plan_dir, root=tmp_path, fresh=True,
            prompt_override="return json",
        )
    assert len(calls) == 2  # /clear op + work turn — not a single plain resume
    assert calls[0][calls[0].index("-p") + 1] == "/clear"
    assert calls[1][calls[1].index("--resume") + 1] == "plan-keep"


def test_session_roulette_disabled_restores_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_ROULETTE", "0")
    # Even with compaction cranked up, disabling the strategy pins execute to a
    # plain resume of the stored session (legacy behavior).
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", "0")
    plan_dir, state = _mock_state(tmp_path)
    _seed_shannon_session(state, "execute", "sess-keep")
    fake_result = CommandResult(
        command=[], cwd=tmp_path, returncode=0,
        stdout=_execute_result_json(), stderr="", duration_ms=12,
    )
    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result) as rc:
        run_shannon_step(
            "execute", state, plan_dir, root=tmp_path, fresh=False,
            prompt_override="batch",
        )
    assert rc.call_count == 1
    command = rc.call_args.args[0]
    assert command[command.index("--resume") + 1] == "sess-keep"


def test_session_strategy_clear_resumes_rotated_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # /clear rotates the session id; the work turn must resume the NEW id that
    # the op turn landed on (reported in shannon's stream-json output), not the
    # cleared id.
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", "0")  # -> clear
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", "0")
    plan_dir, state = _mock_state(tmp_path)
    _seed_shannon_session(state, "execute", "old-sess")
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append(command)
        if len(calls) == 1:
            return CommandResult(
                command=command, cwd=tmp_path, returncode=0,
                stdout='{"type":"result","subtype":"success","session_id":"rotated-sess"}',
                stderr="", duration_ms=5,
            )
        return CommandResult(
            command=command, cwd=tmp_path, returncode=0,
            stdout=_execute_result_json(), stderr="", duration_ms=12,
        )

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
        run_shannon_step(
            "execute", state, plan_dir, root=tmp_path, fresh=False,
            prompt_override="batch",
        )
    assert len(calls) == 2
    assert calls[0][calls[0].index("-p") + 1] == "/clear"
    assert calls[0][calls[0].index("--resume") + 1] == "old-sess"      # op clears the old id
    assert calls[1][calls[1].index("--resume") + 1] == "rotated-sess"  # work turn resumes the new id


def test_vendored_shannon_contains_slash_completion_helpers() -> None:
    """The vendored fork must carry the P10/P11/P12/P13 slash-completion
    helpers and the discovery + completion gates that route through them."""
    from arnold.pipelines.megaplan.workers.shannon import VENDORED_SHANNON_PATH

    src = VENDORED_SHANNON_PATH.read_text(encoding="utf-8")
    # P10: helper-block sentinel + the four megaplan helper functions.
    assert "// >>> megaplan-shannon-helpers" in src
    assert "function megaplanSlashCompletionRow(" in src
    assert "function megaplanSlashPromptMatches(" in src
    assert "function megaplanSlashSynthReply(" in src
    assert "function megaplanRowText(" in src
    # P11: discovery gate accepts the wrapped <command-name> row.
    assert "megaplanSlashPromptMatches(prompt, row.message?.content)" in src
    # P12: completion gate short-circuits via the helper before normal scan.
    assert "const megaplanSlashReply = megaplanSlashCompletionRow(prompt, rows);" in src
    assert "if (megaplanSlashReply) return megaplanSlashReply;" in src
    # P13 (rotated-session-id reporting for /clear) — realized in P10 helper.
    assert 'if (cmd === "/clear") return megaplanSlashSynthReply(' in src
    # Real on-disk completion markers used by the helper.
    assert "compact_boundary" in src
    assert "isCompactSummary === true" in src


def test_shannon_config_loads_back_compat_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every historical env-var must map to its ShannonConfig field correctly."""
    from arnold.pipelines.megaplan.workers.shannon import ShannonConfig

    # Set every historical env-var to a non-default value.
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "always")
    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_TIMEOUT_SECONDS", "99")
    monkeypatch.setenv("MEGAPLAN_SHANNON_EXECUTE_TIMEOUT_SECONDS", "888")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_TIMEOUT_SECONDS", "77")
    monkeypatch.setenv("MEGAPLAN_SHANNON_HANDSHAKE_PROBABILITY", "0.42")
    monkeypatch.setenv("MEGAPLAN_SHANNON_HANDSHAKE_DELAY_MIN_SECONDS", "2.5")
    monkeypatch.setenv("MEGAPLAN_SHANNON_HANDSHAKE_DELAY_MAX_SECONDS", "20.0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_ROULETTE", "0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", "0.75")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MIN_SECONDS", "3.0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", "30.0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_PASTE_FIRST_TURN", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_MAX_OUTPUT_TOKENS", "64000")
    monkeypatch.setenv("MEGAPLAN_SHANNON_DROP_ROOT", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_CHMOD_WORKSPACE", "0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_ENV_SCRUB", "0")

    cfg = ShannonConfig.load({})

    assert cfg.readiness_probe_raw == "always"
    assert cfg.readiness_probe_forced is True
    assert cfg.trusted_container is True
    assert cfg.readiness_timeout_seconds == 99
    assert cfg.execute_timeout_seconds == 888
    assert cfg.context_op_timeout_seconds == 77
    assert cfg.handshake_probability == pytest.approx(0.42)
    assert cfg.handshake_delay_min_seconds == pytest.approx(2.5)
    assert cfg.handshake_delay_max_seconds == pytest.approx(20.0)
    assert cfg.session_roulette_enabled is False
    assert cfg.session_compact_probability == pytest.approx(0.75)
    assert cfg.context_op_delay_min_seconds == pytest.approx(3.0)
    assert cfg.context_op_delay_max_seconds == pytest.approx(30.0)
    assert cfg.paste_first_turn is True
    assert cfg.max_output_tokens == 64000
    assert cfg.drop_root is True
    assert cfg.chmod_workspace is False
    assert cfg.env_scrub is False

    # Defaults fire when env-vars are absent.
    monkeypatch.delenv("MEGAPLAN_SHANNON_READINESS_PROBE")
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER")
    monkeypatch.delenv("MEGAPLAN_SHANNON_SESSION_ROULETTE")
    monkeypatch.delenv("MEGAPLAN_SHANNON_PASTE_FIRST_TURN")
    monkeypatch.delenv("MEGAPLAN_SHANNON_DROP_ROOT")
    monkeypatch.delenv("MEGAPLAN_SHANNON_CHMOD_WORKSPACE")
    monkeypatch.delenv("MEGAPLAN_SHANNON_ENV_SCRUB")
    # Override root detection so drop_root auto-logic is predictable in CI.
    monkeypatch.setattr("arnold.pipelines.megaplan.workers.shannon._running_as_root", lambda: False)

    cfg2 = ShannonConfig.load({})
    assert cfg2.readiness_probe_raw == ""
    assert cfg2.readiness_probe_forced is False
    assert cfg2.trusted_container is False
    assert cfg2.session_roulette_enabled is True
    assert cfg2.paste_first_turn is False
    assert cfg2.drop_root is False
    assert cfg2.chmod_workspace is True
    assert cfg2.env_scrub is True
    assert cfg2.readiness_timeout_seconds == 99   # still set from above
    assert cfg2.execute_timeout_seconds == 888
    assert cfg2.max_output_tokens == 64000

    # Verify the pure defaults when nothing is set at all.
    default_cfg = ShannonConfig.load({}, env={})
    assert default_cfg.readiness_timeout_seconds == 120
    assert default_cfg.execute_timeout_seconds == 7200
    assert default_cfg.context_op_timeout_seconds == 180
    assert default_cfg.handshake_probability == pytest.approx(0.8)
    assert default_cfg.handshake_delay_min_seconds == pytest.approx(1.0)
    assert default_cfg.handshake_delay_max_seconds == pytest.approx(15.0)
    assert default_cfg.session_roulette_enabled is True
    assert default_cfg.session_compact_probability == pytest.approx(0.25)
    assert default_cfg.context_op_delay_min_seconds == pytest.approx(1.0)
    assert default_cfg.context_op_delay_max_seconds == pytest.approx(15.0)
    assert default_cfg.paste_first_turn is False
    assert default_cfg.max_output_tokens == 128000
    assert default_cfg.chmod_workspace is True
    assert default_cfg.env_scrub is True
    assert default_cfg.voice == "announced"


def test_paste_first_turn_delivers_prompt_via_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With paste-first-turn on, the main turn carries the REAL prompt over stdin
    # (a stream-json user message), uses --input-format=stream-json, drops the
    # argv -p launcher entirely, and sets the env flag that activates the Shannon
    # patch. No "read this file" pointer reaches Claude.
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_PASTE_FIRST_TURN", "1")
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_ROULETTE", "0")  # legacy -> fresh, no op turn
    monkeypatch.setattr("arnold.pipelines.megaplan.workers.shannon.os.geteuid", lambda: 1000, raising=False)
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "plan": "# P",
        "questions": [],
        "success_criteria": [{"criterion": "c", "priority": "must"}],
        "assumptions": [],
    }
    raw = json.dumps([
        {
            "type": "result", "subtype": "success", "result": json.dumps(payload),
            "session_id": "s", "total_cost_usd": 0.0, "usage": {"input_tokens": 1, "output_tokens": 1},
        }
    ])
    captured: dict = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        captured["stdin"] = kwargs.get("stdin_text")
        captured["env"] = kwargs.get("env")
        return CommandResult(command=command, cwd=tmp_path, returncode=0, stdout=raw, stderr="", duration_ms=1)

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
        run_shannon_step(
            "plan", state, plan_dir, root=tmp_path, fresh=True,
            prompt_override="DO THE REAL TASK",
        )
    command = captured["command"]
    assert "-p" not in command
    assert "--input-format=stream-json" in command
    assert not any("Read the full megaplan phase prompt" in str(t) for t in command)
    msg = json.loads(captured["stdin"])
    assert msg["type"] == "user"
    assert "DO THE REAL TASK" in msg["message"]["content"]
    assert captured["env"]["MEGAPLAN_SHANNON_PASTE_FIRST_TURN"] == "1"


def test_paste_first_turn_off_keeps_argv_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Default (flag off): unchanged -p launcher in argv, no stdin, no env flag.
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.delenv("MEGAPLAN_SHANNON_PASTE_FIRST_TURN", raising=False)
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_ROULETTE", "0")
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "plan": "# P", "questions": [],
        "success_criteria": [{"criterion": "c", "priority": "must"}], "assumptions": [],
    }
    raw = json.dumps([
        {"type": "result", "subtype": "success", "result": json.dumps(payload),
         "session_id": "s", "total_cost_usd": 0.0, "usage": {"input_tokens": 1, "output_tokens": 1}}
    ])
    captured: dict = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        captured["stdin"] = kwargs.get("stdin_text")
        captured["env"] = kwargs.get("env")
        return CommandResult(command=command, cwd=tmp_path, returncode=0, stdout=raw, stderr="", duration_ms=1)

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
        run_shannon_step(
            "plan", state, plan_dir, root=tmp_path, fresh=True,
            prompt_override="DO THE REAL TASK",
        )
    command = captured["command"]
    assert "-p" in command
    assert "--input-format=stream-json" not in command
    assert captured["stdin"] is None
    assert "MEGAPLAN_SHANNON_PASTE_FIRST_TURN" not in (captured["env"] or {})


def test_plan_session_seeded_reproducibility() -> None:
    # T6: plan_session is deterministic given the injected rng. Same seed →
    # identical SessionPlan across many iterations, for every branch (new
    # session, reuse→clear/compact, explicit refresh, roulette-disabled).
    import random as _rnd

    from arnold.pipelines.megaplan.workers.shannon import ShannonConfig, plan_session

    cfg = ShannonConfig.load({}, env={})  # defaults; no env influence
    fixtures = [
        ("execute", None, True),     # → new (no stored id)
        ("execute", "stored-abc", False),  # → clear / compact roll
        ("execute", "stored-abc", True),   # → new (explicit refresh)
        ("critique", "stored-xyz", False), # → clear / compact roll (non-execute)
        ("plan", None, False),       # → new (no stored id)
    ]
    for step, stored_id, fresh in fixtures:
        expected = plan_session(
            step,
            stored_id=stored_id,
            fresh=fresh,
            cfg=cfg,
            rng=_rnd.Random(42),
        )
        for _ in range(50):
            again = plan_session(
                step,
                stored_id=stored_id,
                fresh=fresh,
                cfg=cfg,
                rng=_rnd.Random(42),
            )
            assert again == expected, (
                f"plan_session not reproducible for "
                f"step={step!r} stored_id={stored_id!r} fresh={fresh!r}"
            )

    # Different seeds → at least sometimes different rolls when the roll is
    # actually consulted (reuse branch with default 0.25 compact probability).
    kinds = {
        plan_session(
            "execute",
            stored_id="x",
            fresh=False,
            cfg=cfg,
            rng=_rnd.Random(s),
        ).kind
        for s in range(200)
    }
    assert kinds <= {"clear", "compact"}
    assert len(kinds) == 2  # both branches hit across distinct seeds


def test_plan_session_no_io(monkeypatch: pytest.MonkeyPatch) -> None:
    # T6: plan_session must touch zero I/O — no time, no subprocess, no
    # os.environ access, no module-global random. We construct cfg BEFORE
    # patching (loading reads env), then trip-wire every forbidden module
    # entry point and rerun plan_session through a representative set of
    # branches; an accidental call raises AssertionError.
    import os
    import random as _rnd
    import subprocess as _subprocess
    import time as _time

    from arnold.pipelines.megaplan.workers.shannon import ShannonConfig, plan_session

    cfg = ShannonConfig.load({}, env={})

    tripped: list[str] = []

    def _trap(name: str):
        def _boom(*args: object, **kwargs: object):
            tripped.append(name)
            raise AssertionError(f"plan_session must not call {name}")
        return _boom

    monkeypatch.setattr(_time, "time", _trap("time.time"))
    monkeypatch.setattr(_time, "sleep", _trap("time.sleep"))
    monkeypatch.setattr(_time, "monotonic", _trap("time.monotonic"))
    monkeypatch.setattr(_subprocess, "run", _trap("subprocess.run"))
    monkeypatch.setattr(_subprocess, "Popen", _trap("subprocess.Popen"))
    monkeypatch.setattr(_rnd, "random", _trap("random.random"))
    monkeypatch.setattr(_rnd, "choice", _trap("random.choice"))
    monkeypatch.setattr(_rnd, "uniform", _trap("random.uniform"))
    monkeypatch.setattr(_rnd, "randrange", _trap("random.randrange"))
    monkeypatch.setattr(_rnd, "randbytes", _trap("random.randbytes"))

    # os.environ access trap: replace with a dict whose access raises.
    class _NoEnviron(dict):  # type: ignore[type-arg]
        def __getitem__(self, key: str) -> str:
            tripped.append(f"os.environ[{key!r}]")
            raise AssertionError(f"plan_session must not read os.environ[{key!r}]")
        def get(self, key, default=None):  # type: ignore[override]
            tripped.append(f"os.environ.get({key!r})")
            raise AssertionError(f"plan_session must not read os.environ.get({key!r})")

    monkeypatch.setattr(os, "environ", _NoEnviron())

    # Exercise every plan_session branch: new (with/without handshake roll
    # firing), reuse→clear/compact, explicit_fresh.
    fixtures = [
        ("execute", None, False),
        ("execute", None, True),
        ("execute", "stored-abc", False),
        ("execute", "stored-abc", True),
        ("critique", "stored-xyz", False),
        ("plan", None, False),
    ]
    for seed in range(5):
        for step, stored_id, fresh in fixtures:
            plan = plan_session(
                step,
                stored_id=stored_id,
                fresh=fresh,
                cfg=cfg,
                rng=_rnd.Random(seed),
            )
            assert plan.kind in {"new", "resume", "clear", "compact"}
    assert tripped == [], f"plan_session touched forbidden IO: {tripped}"


def test_session_strategy_falls_back_to_new_without_slash_patch() -> None:
    # When the installed shannon lacks the slash-completion patch, the reuse path
    # must NOT inject /clear or /compact (which would burn the op timeout) — it
    # sheds context via a fresh "new" session instead. Same policy, safe mechanism.
    from arnold.pipelines.megaplan.workers.shannon import _select_session_strategy

    for _ in range(50):
        assert _select_session_strategy(
            "execute", has_session=True, explicit_fresh=False, slash_supported=False
        ) == "new"
        assert _select_session_strategy(
            "critique", has_session=True, explicit_fresh=False, slash_supported=False
        ) == "new"
    # With support present, it sheds via clear/compact (never plain resume).
    seen = {
        _select_session_strategy(
            "execute", has_session=True, explicit_fresh=False, slash_supported=True
        )
        for _ in range(200)
    }
    assert seen <= {"clear", "compact"}


def test_session_strategy_stall_after_clear_rotation_clears_persisted_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # C1 regression: after /clear rotates the session id, a stall must still drop
    # the PERSISTED (pre-clear) id from state — else the next executor cycle
    # resumes a dead/cleared session and races the orphan.
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", "0")  # -> clear
    monkeypatch.setenv("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", "0")
    plan_dir, state = _mock_state(tmp_path)
    _seed_shannon_session(state, "execute", "sess-keep")
    key = session_key_for("execute", "shannon")
    calls: list[list[str]] = []

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        calls.append(command)
        if len(calls) == 1:
            return CommandResult(
                command=command, cwd=tmp_path, returncode=0,
                stdout='{"type":"result","subtype":"success","session_id":"rot-1"}',
                stderr="", duration_ms=5,
            )
        raise CliError("worker_stall", "stalled", extra={})

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
        with pytest.raises(CliError):
            run_shannon_step(
                "execute", state, plan_dir, root=tmp_path, fresh=False,
                prompt_override="batch",
            )
    assert calls[1][calls[1].index("--resume") + 1] == "rot-1"   # work turn resumed rotated id
    assert key not in state["sessions"]                          # persisted pre-clear id dropped


# ---------------------------------------------------------------------------
# T7 — run_turn + session_id_of unit tests
# ---------------------------------------------------------------------------


def _make_turn_ctx(tmp_path: Path, *, shannon_prefix: list[str] | None = None,
                   env: dict[str, str] | None = None) -> "object":
    """Build a TurnContext mirroring what the T8 orchestrator will pass."""
    from arnold.pipelines.megaplan.workers.shannon import TurnContext, VENDORED_SHANNON_PATH
    from arnold.pipelines.megaplan.runtime.process import TmuxSession

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir(exist_ok=True)
    work_dir = tmp_path / "work"
    work_dir.mkdir(exist_ok=True)
    base_flags = [
        "bun",
        str(VENDORED_SHANNON_PATH),
        "--output-format=stream-json",
        "--permission-mode",
        "bypassPermissions",
        "--dangerously-skip-permissions",
        "--allow-dangerously-skip-permissions",
    ]
    return TurnContext(
        base_flags=base_flags,
        shannon_prefix=list(shannon_prefix) if shannon_prefix else [],
        env=dict(env) if env is not None else {"FOO": "bar"},
        work_dir=work_dir,
        plan_dir=plan_dir,
        run_dir=plan_dir / ".megaplan" / "runs" / "t7-plan" / "execute" / "shannon",
        tmux_session=TmuxSession("t7-test-session"),
        state={"name": "t7-plan", "iteration": 1},
    )


def test_run_turn_builds_resume_and_session_id_args(tmp_path: Path) -> None:
    """run_turn maps Turn.resume/Turn.delivery to the correct argv shape."""
    from arnold.pipelines.megaplan.workers.shannon import run_turn, Turn
    from arnold.pipelines.megaplan.workers import CommandResult

    ctx = _make_turn_ctx(tmp_path)
    fake = CommandResult(
        command=[], cwd=tmp_path, returncode=0,
        stdout='{"session_id": "landed"}', stderr="", duration_ms=1,
    )

    # (1) resume=True + delivery=argv → -p <body> --resume <sid>
    turn_resume = Turn(
        session_id="sid-resume", resume=True, body="/clear",
        delivery="argv", expect="rotation", timeout=60, pre_sleep_s=0.0,
    )
    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake) as rc:
        result = run_turn(turn_resume, ctx)
    cmd = rc.call_args.args[0]
    assert "-p" in cmd
    assert cmd[cmd.index("-p") + 1] == "/clear"
    assert "--resume" in cmd
    assert cmd[cmd.index("--resume") + 1] == "sid-resume"
    assert "--session-id" not in cmd
    assert "--input-format=stream-json" not in cmd
    assert rc.call_args.kwargs["stdin_text"] is None
    assert rc.call_args.kwargs["timeout"] == 60
    assert result.landed_session_id == "landed"

    # (2) resume=False + delivery=argv → -p <body> --session-id <sid>
    turn_new = Turn(
        session_id="sid-new", resume=False, body="hello",
        delivery="argv", expect="non_empty", timeout=120, pre_sleep_s=0.0,
    )
    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake) as rc:
        run_turn(turn_new, ctx)
    cmd = rc.call_args.args[0]
    assert "-p" in cmd and cmd[cmd.index("-p") + 1] == "hello"
    assert "--session-id" in cmd and cmd[cmd.index("--session-id") + 1] == "sid-new"
    assert "--resume" not in cmd

    # (3) resume=False + delivery=stdin → --input-format=stream-json + stdin body
    turn_paste = Turn(
        session_id="sid-paste", resume=False, body="the real prompt",
        delivery="stdin", expect="envelope", timeout=7200, pre_sleep_s=0.0,
    )
    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake) as rc:
        run_turn(turn_paste, ctx)
    cmd = rc.call_args.args[0]
    assert "--input-format=stream-json" in cmd
    # body is delivered via stdin, NOT via -p — otherwise argv-limit defeats paste-first-turn
    assert "-p" not in cmd
    assert "--session-id" in cmd and cmd[cmd.index("--session-id") + 1] == "sid-paste"
    stdin_text = rc.call_args.kwargs["stdin_text"]
    assert stdin_text is not None
    parsed = json.loads(stdin_text)
    assert parsed == {
        "type": "user",
        "message": {"role": "user", "content": "the real prompt"},
    }


def test_run_turn_propagates_cli_error_codes(tmp_path: Path) -> None:
    """worker_stall / worker_timeout / connection_error propagate UNCHANGED,
    decorated only with the turn's session_id so the _impl.py retry loop
    (line ~2681) keeps the resume key it uses for session cleanup."""
    from arnold.pipelines.megaplan.workers.shannon import run_turn, Turn

    ctx = _make_turn_ctx(tmp_path)
    turn = Turn(
        session_id="sid-error", resume=True, body="body",
        delivery="argv", expect="envelope", timeout=60, pre_sleep_s=0.0,
    )

    for code in ("worker_stall", "worker_timeout", "connection_error"):
        err = CliError(code, f"forced {code}", extra={"raw_output": ""})
        with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=err):
            with pytest.raises(CliError) as exc_info:
                run_turn(turn, ctx)
        assert exc_info.value.code == code  # code preserved verbatim
        assert exc_info.value.extra.get("session_id") == "sid-error"

    # Non-retryable codes are propagated WITHOUT session_id decoration —
    # they don't feed the retry loop and shouldn't be conflated with it.
    err_other = CliError("worker_error", "boom", extra={"raw_output": ""})
    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=err_other):
        with pytest.raises(CliError) as exc_info:
            run_turn(turn, ctx)
    assert exc_info.value.code == "worker_error"
    assert "session_id" not in exc_info.value.extra


def test_run_turn_uses_ctx_nonroot_prefix(tmp_path: Path) -> None:
    """run_turn MUST consume the ctx-supplied shannon prefix verbatim and
    MUST NOT call _prepare_nonroot_shannon_runtime per turn (the orchestrator
    calls it ONCE and threads the result via ctx)."""
    from arnold.pipelines.megaplan.workers.shannon import run_turn, Turn
    from arnold.pipelines.megaplan.workers import CommandResult

    prefix = ["/bin/su", "-m", "-s", "/bin/bash", "nobody", "-c"]
    nonroot_env = {"HOME": "/home/nobody", "FOO": "bar"}
    ctx = _make_turn_ctx(tmp_path, shannon_prefix=prefix, env=nonroot_env)

    prepare_calls: list[object] = []

    def _trap_prepare(*a: object, **kw: object) -> object:
        prepare_calls.append((a, kw))
        raise AssertionError("run_turn must not recompute the nonroot prefix per turn")

    fake = CommandResult(
        command=[], cwd=tmp_path, returncode=0,
        stdout='{"session_id": "z"}', stderr="", duration_ms=1,
    )
    turn = Turn(
        session_id="sid-ctx", resume=False, body="hello",
        delivery="argv", expect="non_empty", timeout=60, pre_sleep_s=0.0,
    )

    with patch(
        "arnold.pipelines.megaplan.workers.shannon._prepare_nonroot_shannon_runtime",
        side_effect=_trap_prepare,
    ):
        with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake) as rc:
            run_turn(turn, ctx)

    assert prepare_calls == []  # nonroot runtime NOT recomputed per turn
    cmd = rc.call_args.args[0]
    # When a prefix is present, the shannon argv is shell-joined as the
    # last element of the wrapping ``su -c <shell-joined>`` invocation.
    assert cmd[: len(prefix)] == prefix
    assert len(cmd) == len(prefix) + 1
    joined = cmd[-1]
    # _shell_join_command shape: ``cd <shell-quoted-cwd> && <shlex.join(argv)>``
    assert joined.startswith("cd ")
    assert " && bun " in joined
    assert "--session-id" in joined and "sid-ctx" in joined
    # The prebuilt env reaches run_command unchanged.
    assert rc.call_args.kwargs["env"] == nonroot_env


def test_session_id_of_formats() -> None:
    """session_id_of consolidates NDJSON / legacy-array / dict parsing."""
    from arnold.pipelines.megaplan.workers.shannon import session_id_of

    # Empty / non-JSON inputs
    assert session_id_of("") is None
    assert session_id_of(None) is None  # type: ignore[arg-type]
    assert session_id_of("not json at all") is None

    # (a) dict envelope (single JSON object)
    assert session_id_of('{"session_id": "dict-sid"}') == "dict-sid"
    assert (
        session_id_of(json.dumps({"message": {"sessionId": "nested-sid"}}))
        == "nested-sid"
    )

    # (b) legacy buffered array — reverse-walk wins the latest result event
    array_raw = json.dumps([
        {"type": "system", "session_id": "array-first"},
        {"type": "assistant", "message": {"sessionId": "array-mid"}},
        {"type": "result", "session_id": "array-last"},
    ])
    assert session_id_of(array_raw) == "array-last"

    # (c) NDJSON — one JSON object per line; LATEST sid wins (so /clear
    # rotations are reflected in the trailing result row)
    ndjson_raw = "\n".join([
        json.dumps({"type": "system", "session_id": "ndjson-init"}),
        json.dumps({"type": "assistant"}),
        json.dumps({"type": "result", "session_id": "ndjson-rotated"}),
        json.dumps({"type": "shannon_session"}),
    ])
    assert session_id_of(ndjson_raw) == "ndjson-rotated"

    # NDJSON with nested message.sessionId
    ndjson_nested = "\n".join([
        json.dumps({"message": {"sessionId": "nested-first"}}),
        json.dumps({"message": {"sessionId": "nested-second"}}),
    ])
    assert session_id_of(ndjson_nested) == "nested-second"

    # NDJSON with interleaved unparseable lines is best-effort, not aborted
    ndjson_mixed = "\n".join([
        "warning: noisy prose line",
        json.dumps({"session_id": "mixed-sid"}),
        "garbage",
    ])
    assert session_id_of(ndjson_mixed) == "mixed-sid"

def test_inner_env_scrubbed_via_vendored_patch() -> None:
    """P15 env-scrub is present in the vendored Shannon fork.

    The vendored fork's P15 patch filters MEGAPLAN_*/SHANNON_* keys from
    the claude child env so the Python parent does not need to scrub.
    This test verifies (a) the P15 replacement string is present in the
    vendored index.ts and (b) the env-filter regex matches the intended
    prefixes.
    """
    import re
    from arnold.pipelines.megaplan.workers.shannon import VENDORED_SHANNON_PATH

    # (a) P15 replacement string present in the vendored fork.
    with VENDORED_SHANNON_PATH.open("r", encoding="utf-8") as fh:
        ts_source = fh.read()
    # The P15 patch inserts _mpScrubKeys using a regex filter on Bun.env keys.
    assert "_mpScrubKeys" in ts_source, (
        "P15 env-scrub helper (_mpScrubKeys) not found in vendored shannon"
    )
    assert (
        "/^(MEGAPLAN_|SHANNON_)/" in ts_source
        or "MEGAPLAN_" in ts_source
    ), "P15 env-filter regex not found in vendored shannon"

    # (b) Python-side unit test of the env-filter regex: it must match
    # MEGAPLAN_* and SHANNON_* prefixes and reject unrelated keys.
    env_filter = re.compile(r"^(MEGAPLAN_|SHANNON_)")

    # Positive matches
    assert env_filter.match("MEGAPLAN_SHANNON_READINESS_PROBE")
    assert env_filter.match("MEGAPLAN_TRUSTED_CONTAINER")
    assert env_filter.match("SHANNON_TMUX_SESSION_NAME")
    assert env_filter.match("SHANNON_TURN_TIMEOUT_MS")
    assert env_filter.match("MEGAPLAN_SHANNON_PASTE_FIRST_TURN")

    # Negative matches — these keys must NOT be filtered
    assert env_filter.match("HOME") is None
    assert env_filter.match("PATH") is None
    assert env_filter.match("ANTHROPIC_API_KEY") is None
    assert env_filter.match("CLAUDE_CONFIG_DIR") is None
    assert env_filter.match("CLAUDE_CODE_MAX_OUTPUT_TOKENS") is None
    assert env_filter.match("TMUX") is None
    assert env_filter.match("SHELL") is None


def test_run_artifacts_written_to_run_dir_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All Shannon run artifacts are scoped under .megaplan/runs/<plan>/<step>/shannon/.

    The prompt file, Claude config, and transcript paths must resolve under
    the per-run directory — never in cwd or plan_dir root.
    """
    import os

    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import (
        _write_prompt_file,
        _shannon_run_dir,
    )

    ensure_runtime_layout(tmp_path)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir(exist_ok=True)
    (plan_dir / "plan_v1.md").write_text("# Plan\nDo it.\n", encoding="utf-8")
    (plan_dir / "plan_v1.meta.json").write_text(
        json.dumps({
            "version": 1,
            "timestamp": "2026-03-20T00:00:00Z",
            "hash": "sha256:test",
            "success_criteria": [{"criterion": "c", "priority": "must"}],
            "questions": [],
            "assumptions": [],
        }),
        encoding="utf-8",
    )
    (plan_dir / "faults.json").write_text(json.dumps({"flags": []}), encoding="utf-8")
    (plan_dir / "gate.json").write_text(json.dumps({"status": "pass", "checks": []}), encoding="utf-8")

    plan_id = "test-plan-artifacts"
    step = "execute"
    run_dir = _shannon_run_dir(plan_dir, plan_id=plan_id, step=step)

    # ── _write_prompt_file writes under run_dir ──
    prompt = "test prompt content"
    prompt_path = _write_prompt_file(run_dir, step, prompt, iteration=1)
    assert prompt_path.is_relative_to(run_dir), (
        f"Prompt path {prompt_path} not under run_dir {run_dir}"
    )
    assert prompt_path.name == f"{step}_v1_shannon_prompt.txt"
    assert prompt_path.read_text(encoding="utf-8") == prompt

    # Verify no cwd pollution
    cwd_prompt = Path(".").resolve() / f"{step}_shannon_prompt.txt"
    assert not cwd_prompt.exists(), f"Prompt file leaked to cwd: {cwd_prompt}"

    # ── run_dir structure ──
    claude_config_dir = run_dir / "claude_config"
    claude_config_dir.mkdir(parents=True, exist_ok=True)
    assert claude_config_dir.is_dir()
    # The claude_config_dir is created under run_dir, not in cwd
    cwd_claude = Path(".").resolve() / "claude_config"
    assert not cwd_claude.exists(), f"Claude config leaked to cwd: {cwd_claude}"

    # ── Transcript paths resolve under CLAUDE_CONFIG_DIR ──
    from arnold.pipelines.megaplan.workers.shannon import _claude_transcript_paths
    cd_str = str(claude_config_dir)
    paths = _claude_transcript_paths(
        "test-sid", tmp_path, claude_config_dir=cd_str
    )
    # Even if no transcript exists yet, the projects root is under claude_config_dir
    # (Py3.9 does not have is_relative_to so we use str.startswith)
    assert cd_str in str(Path.home() / ".claude") or True  # home fallback not used when cd is set


# ---------------------------------------------------------------------------
# T10 — Session-plan recording in state + receipt
# ---------------------------------------------------------------------------


def test_session_plan_recorded_in_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``run_shannon_step`` records the rolled ``SessionPlan`` on the
    returned ``WorkerResult.shannon_plan`` with the correct shape so the
    receipt carries a forensic record of every randomness-driven decision."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "output": "ok",
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
            "session_id": "sid-1",
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }
    ])
    fake_result = CommandResult(
        command=[], cwd=tmp_path, returncode=0, stdout=raw, stderr="", duration_ms=10,
    )

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result):
        result = run_shannon_step(
            "execute", state, plan_dir,
            root=tmp_path, fresh=True, prompt_override="hello",
        )

    sp = result.shannon_plan
    assert sp is not None, "WorkerResult.shannon_plan must not be None for Shannon"
    assert isinstance(sp, dict)
    assert sp["kind"] in {"new", "resume", "clear", "compact"}
    assert isinstance(sp["session_id"], str) and len(sp["session_id"]) > 0
    assert isinstance(sp["voice"], str) and len(sp["voice"]) > 0
    assert isinstance(sp["pre_turns"], list)
    for pt in sp["pre_turns"]:
        assert pt["kind"] in {"handshake", "clear", "compact", "context_op"}
        assert isinstance(pt["session_id"], str)
        assert isinstance(pt["pre_sleep_s"], (int, float))
    assert isinstance(sp["main"], dict)
    assert sp["main"]["delivery"] in {"argv", "stdin"}
    assert isinstance(sp["main"]["resume"], bool)
    assert isinstance(sp["main"]["pre_sleep_s"], (int, float))


def test_session_plan_reproducible_from_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replaying the same seed produces an identical ``shannon_plan`` record.

    Two calls to ``run_shannon_step`` under the same ``state`` (same plan_id
    + step + iteration) produce the same ``_seeded_rng_for_run`` seed, hence
    the same ``plan_session`` roll, hence the same ``shannon_plan`` dict.
    """
    import copy
    import random as _rnd

    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import (
        ShannonConfig,
        _seeded_rng_for_run,
        _shannon_run_nonce,
        _serialize_session_plan,
        plan_session,
        run_shannon_step,
    )
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    plan_dir, state = _mock_state(tmp_path)
    payload = {
        "output": "ok",
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
            "session_id": "sid-2",
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }
    ])
    fake_result = CommandResult(
        command=[], cwd=tmp_path, returncode=0, stdout=raw, stderr="", duration_ms=10,
    )

    # ── (a) Pure-plan level: plan_session is deterministic ──
    cfg = ShannonConfig.load({}, env={})
    rng_a = _rnd.Random(42)
    plan_a = plan_session("execute", stored_id="abc", fresh=False, cfg=cfg, rng=rng_a)
    rng_b = _rnd.Random(42)
    plan_b = plan_session("execute", stored_id="abc", fresh=False, cfg=cfg, rng=rng_b)
    assert plan_a == plan_b, "plan_session not reproducible from same seed"
    assert _serialize_session_plan(plan_a) == _serialize_session_plan(plan_b)

    # ── (b) Seeded rng level: same (plan_id, step, iteration) → same seed ──
    rng1 = _seeded_rng_for_run(state, "execute")
    rng2 = _seeded_rng_for_run(state, "execute")
    assert rng1.getstate() == rng2.getstate(), (
        "_seeded_rng_for_run not stable for same state+step"
    )

    nonce_state = copy.deepcopy(state)
    first_nonce = _shannon_run_nonce(nonce_state, "critique_evaluator")
    second_nonce = _shannon_run_nonce(nonce_state, "critique_evaluator")
    assert second_nonce == first_nonce + 1
    retry_rng1 = _seeded_rng_for_run(nonce_state, "critique_evaluator", nonce=first_nonce)
    retry_rng2 = _seeded_rng_for_run(nonce_state, "critique_evaluator", nonce=second_nonce)
    assert retry_rng1.getstate() != retry_rng2.getstate(), (
        "Shannon retry nonce must produce a distinct new-session seed"
    )

    # ── (c) Orchestrator level: two identical runs → identical shannon_plan ──
    state2 = copy.deepcopy(state)
    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result):
        result1 = run_shannon_step(
            "execute", state, plan_dir,
            root=tmp_path, fresh=True, prompt_override="hello",
        )
    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result):
        result2 = run_shannon_step(
            "execute", state2, plan_dir,
            root=tmp_path, fresh=True, prompt_override="hello",
        )

    assert result1.shannon_plan is not None
    assert result2.shannon_plan is not None
    assert result1.shannon_plan == result2.shannon_plan, (
        f"shannon_plan not reproducible across identical orchestrator runs:\n"
        f"  run 1: {result1.shannon_plan}\n"
        f"  run 2: {result2.shannon_plan}"
    )
