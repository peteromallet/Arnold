"""Characterization tests for ``run_step_with_worker`` dispatch boundaries."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from megaplan.types import AgentMode, CliError
from megaplan.workers import WorkerResult, run_step_with_worker, session_key_for
from tests._workers_helpers import _mock_state


def _args(agent: str | None = None) -> Namespace:
    return Namespace(
        agent=agent,
        ephemeral=False,
        fresh=False,
        persist=False,
        confirm_self_review=False,
        hermes=None,
        phase_model=[],
    )


def _worker(payload: dict | None = None, *, session_id: str = "session") -> WorkerResult:
    return WorkerResult(
        payload=payload or {"output": "done"},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id=session_id,
        rendered_prompt="prompt",
        shannon_plan={"kind": "opaque", "engine": "not-routing"},
    )


def test_dispatches_to_hermes_without_interpreting_shannon_metadata(tmp_path: Path) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="hermes-session")

    with patch("megaplan.workers.hermes.run_hermes_step", return_value=worker) as run_hermes:
        result, agent, mode, refreshed = run_step_with_worker(
            "review",
            state,
            plan_dir,
            _args(),
            root=tmp_path,
            resolved=AgentMode(agent="hermes", mode="persistent", refreshed=False),
            read_only=True,
        )

    assert result is worker
    assert result.shannon_plan == {"kind": "opaque", "engine": "not-routing"}
    assert agent == "hermes"
    assert mode == "persistent"
    assert refreshed is True
    run_hermes.assert_called_once()
    assert run_hermes.call_args.kwargs["fresh"] is True


def test_dispatches_claude_through_shannon_with_claude_session_agent(
    tmp_path: Path,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="claude-via-shannon")

    with patch("megaplan.workers.shannon.run_shannon_step", return_value=worker) as run_shannon:
        result, agent, mode, refreshed = run_step_with_worker(
            "plan",
            state,
            plan_dir,
            _args(),
            root=tmp_path,
            resolved=AgentMode(
                agent="claude",
                mode="persistent",
                refreshed=False,
                model=None,
                resolved_model="claude-sonnet-4",
            ),
        )

    assert result is worker
    assert agent == "claude"
    assert mode == "persistent"
    assert refreshed is True
    run_shannon.assert_called_once()
    assert run_shannon.call_args.kwargs["session_agent"] == "claude"
    assert run_shannon.call_args.kwargs["model"] == "claude-sonnet-4"


def test_dispatches_plain_shannon_without_claude_session_agent(tmp_path: Path) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="plain-shannon")

    with patch("megaplan.workers.shannon.run_shannon_step", return_value=worker) as run_shannon:
        result, agent, mode, refreshed = run_step_with_worker(
            "plan",
            state,
            plan_dir,
            _args(),
            root=tmp_path,
            resolved=AgentMode(
                agent="shannon",
                mode="persistent",
                refreshed=False,
                model="claude-opus-4-1",
                resolved_model="claude-opus-4-1",
            ),
        )

    assert result is worker
    assert agent == "shannon"
    assert mode == "persistent"
    assert refreshed is True
    run_shannon.assert_called_once()
    assert "session_agent" not in run_shannon.call_args.kwargs
    assert run_shannon.call_args.kwargs["model"] == "claude-opus-4-1"


def test_dispatches_codex_with_resolved_model_and_worker_metadata(
    tmp_path: Path,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="codex-session")

    with patch("megaplan.workers._impl.run_codex_step", return_value=worker) as run_codex:
        result, agent, mode, refreshed = run_step_with_worker(
            "plan",
            state,
            plan_dir,
            _args(),
            root=tmp_path,
            resolved=AgentMode(
                agent="codex",
                mode="persistent",
                refreshed=False,
                model=None,
                effort="medium",
                resolved_model="gpt-5.5",
            ),
        )

    assert result is worker
    assert result.shannon_plan == {"kind": "opaque", "engine": "not-routing"}
    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is True
    run_codex.assert_called_once()
    assert run_codex.call_args.kwargs["model"] == "gpt-5.5"
    assert run_codex.call_args.kwargs["effort"] == "medium"


def test_shannon_retry_uses_fresh_session_without_recording_stale_session(
    tmp_path: Path,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    error = CliError("worker_stall", "stalled", extra={"session_id": "stale-shannon"})
    worker = _worker(session_id="fresh-shannon")

    with patch("megaplan.workers.shannon.run_shannon_step", side_effect=[error, worker]) as run_shannon:
        result, agent, mode, refreshed = run_step_with_worker(
            "review",
            state,
            plan_dir,
            _args(),
            root=tmp_path,
            resolved=AgentMode(
                agent="shannon",
                mode="persistent",
                refreshed=False,
                model="claude-opus-4-1",
                resolved_model="claude-opus-4-1",
            ),
        )

    assert result is worker
    assert agent == "shannon"
    assert mode == "persistent"
    assert refreshed is True
    assert run_shannon.call_count == 2
    assert [call.kwargs["fresh"] for call in run_shannon.call_args_list] == [True, True]
    assert session_key_for("review", "shannon") not in state["sessions"]


def test_codex_retry_records_stale_session_before_retry(tmp_path: Path) -> None:
    plan_dir, state = _mock_state(tmp_path)
    error = CliError("worker_timeout", "timed out", extra={"session_id": "stale-codex"})
    worker = _worker(session_id="fresh-codex")

    with patch("megaplan.workers._impl.run_codex_step", side_effect=[error, worker]) as run_codex:
        result, agent, mode, refreshed = run_step_with_worker(
            "review",
            state,
            plan_dir,
            _args(),
            root=tmp_path,
            resolved=AgentMode(
                agent="codex",
                mode="persistent",
                refreshed=False,
                model=None,
                effort="medium",
                resolved_model="gpt-5.5",
            ),
        )

    assert result is worker
    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is True
    assert run_codex.call_count == 2
    assert [call.kwargs["fresh"] for call in run_codex.call_args_list] == [True, True]
    key = session_key_for("review", "codex", model="gpt-5.5")
    assert state["sessions"][key]["id"] == "stale-codex"
    assert state["sessions"][key]["refreshed"] is True
