"""Characterization tests for ``run_step_with_worker`` dispatch boundaries."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.pipelines.megaplan.types import AgentMode, CliError
from arnold.pipelines.megaplan.workers import WorkerResult, run_claude_step, run_codex_step, run_step_with_worker, session_key_for
from arnold.pipelines.megaplan.workers.turn_cap import HOST_TURN_CAP_SOURCE, acquire_turn_slot
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


def _write_channel_shadow_gate(root: Path, plan_id: str, *, greenlight: bool = True) -> None:
    path = root / ".megaplan" / "bakeoffs" / plan_id / "channel_shadow.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "experiment_id": plan_id,
                "real_parity_success_count": 5 if greenlight else 4,
                "records": [],
                "gate": {
                    "greenlight": greenlight,
                    "threshold": 5,
                    "real_parity_success_count": 5 if greenlight else 4,
                    "real_parity_failure_count": 0,
                    "skipped_count": 0,
                    "fixture_count": 0,
                    "blockers": [] if greenlight else ["insufficient_real_parity_successes"],
                    "channel_pair": {
                        "primary_worker_channel": "shannon_tmux",
                        "primary_auth_channel": "subscription",
                        "shadow_worker_channel": "shannon_stream",
                        "shadow_auth_channel": "subscription",
                    },
                    "provenance": {
                        "source": "channel_shadow_hook",
                        "fixture": False,
                    },
                    "evaluated_at": "2026-06-12T09:00:00Z",
                    "api_channel_greenlight": False,
                    "api_channel_blockers": ["api_proof_not_live"],
                },
            }
        ),
        encoding="utf-8",
    )


def test_dispatches_to_hermes_without_interpreting_shannon_metadata(tmp_path: Path) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="hermes-session")

    with patch("arnold.pipelines.megaplan.workers.hermes.run_hermes_step", return_value=worker) as run_hermes:
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

    with patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step", return_value=worker) as run_shannon:
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


def test_stream_flag_dispatches_claude_to_stream_worker_with_read_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="claude-via-stream")

    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_WORKER", "1")
    with (
        patch("arnold.pipelines.megaplan.workers.shannon_stream.run_shannon_stream_step", return_value=worker) as run_stream,
        patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step") as run_shannon,
    ):
        result, agent, mode, refreshed = run_step_with_worker(
            "critique",
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
            read_only=True,
        )

    assert result is worker
    assert agent == "claude"
    assert mode == "persistent"
    assert refreshed is True
    run_stream.assert_called_once()
    run_shannon.assert_not_called()
    assert run_stream.call_args.kwargs["session_agent"] == "claude"
    assert run_stream.call_args.kwargs["model"] == "claude-sonnet-4"
    assert run_stream.call_args.kwargs["read_only"] is True


def test_dispatches_plain_shannon_without_claude_session_agent(tmp_path: Path) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="plain-shannon")

    with patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step", return_value=worker) as run_shannon:
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


def test_stream_flag_dispatches_plain_shannon_to_stream_worker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="plain-stream-shannon")

    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_WORKER", "yes")
    with (
        patch("arnold.pipelines.megaplan.workers.shannon_stream.run_shannon_stream_step", return_value=worker) as run_stream,
        patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step") as run_shannon,
    ):
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
    run_stream.assert_called_once()
    run_shannon.assert_not_called()
    assert "session_agent" not in run_stream.call_args.kwargs
    assert run_stream.call_args.kwargs["model"] == "claude-opus-4-1"


def test_green_channel_shadow_gate_dispatches_shannon_to_stream_by_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="gated-stream-shannon")
    monkeypatch.delenv("MEGAPLAN_SHANNON_STREAM_WORKER", raising=False)
    _write_channel_shadow_gate(tmp_path, state["name"], greenlight=True)

    with (
        patch("arnold.pipelines.megaplan.workers.shannon_stream.run_shannon_stream_step", return_value=worker) as run_stream,
        patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step") as run_shannon,
    ):
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
    run_stream.assert_called_once()
    run_shannon.assert_not_called()


def test_explicit_false_stream_flag_restores_tmux_despite_green_gate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="tmux-fallback-shannon")
    _write_channel_shadow_gate(tmp_path, state["name"], greenlight=True)
    monkeypatch.setenv("MEGAPLAN_SHANNON_STREAM_WORKER", "off")

    with (
        patch("arnold.pipelines.megaplan.workers.shannon_stream.run_shannon_stream_step") as run_stream,
        patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step", return_value=worker) as run_shannon,
    ):
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
    run_stream.assert_not_called()


def test_dispatches_codex_with_resolved_model_and_worker_metadata(
    tmp_path: Path,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    worker = _worker(session_id="codex-session")

    with patch("arnold.pipelines.megaplan.workers._impl.run_codex_step", return_value=worker) as run_codex:
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


def test_run_step_with_worker_refuses_codex_when_host_turn_cap_full(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    lock_dir = tmp_path / "turn-cap"
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP", "1")
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP_DIR", str(lock_dir))

    with acquire_turn_slot(engine="claude", step="other", plan=plan_dir, cap=1, lock_dir=lock_dir):
        with (
            patch("arnold.pipelines.megaplan.workers._impl._run_codex_step_uncapped") as run_codex,
            pytest.raises(CliError) as exc_info,
        ):
            run_step_with_worker(
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

    assert exc_info.value.code == "rate_limit"
    assert exc_info.value.extra["source"] == HOST_TURN_CAP_SOURCE
    assert exc_info.value.extra["retryable"] is True
    run_codex.assert_not_called()


def test_run_codex_step_refuses_direct_call_when_host_turn_cap_full(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    lock_dir = tmp_path / "turn-cap"
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP", "1")
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP_DIR", str(lock_dir))

    with acquire_turn_slot(engine="claude", step="other", plan=plan_dir, cap=1, lock_dir=lock_dir):
        with (
            patch("arnold.pipelines.megaplan.workers._impl._run_codex_step_uncapped") as run_codex,
            pytest.raises(CliError) as exc_info,
        ):
            run_codex_step(
                "plan",
                state,
                plan_dir,
                root=tmp_path,
                persistent=True,
                fresh=True,
                model="gpt-5.5",
            )

    assert exc_info.value.code == "rate_limit"
    assert exc_info.value.extra["source"] == HOST_TURN_CAP_SOURCE
    assert exc_info.value.extra["retryable"] is True
    run_codex.assert_not_called()


def test_run_step_with_worker_leaves_claude_cap_to_shannon_turn_seam(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    lock_dir = tmp_path / "turn-cap"
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP", "1")
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP_DIR", str(lock_dir))
    worker = _worker(session_id="claude-via-shannon")

    with acquire_turn_slot(engine="codex", step="other", plan=plan_dir, cap=1, lock_dir=lock_dir):
        with patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step", return_value=worker) as run_shannon:
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


def test_run_claude_step_leaves_cap_to_shannon_turn_seam(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    lock_dir = tmp_path / "turn-cap"
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP", "1")
    monkeypatch.setenv("MEGAPLAN_WORKER_TURN_CAP_DIR", str(lock_dir))
    worker = _worker(session_id="direct-claude")

    with acquire_turn_slot(engine="codex", step="other", plan=plan_dir, cap=1, lock_dir=lock_dir):
        with patch("arnold.pipelines.megaplan.workers._impl._run_claude_step_uncapped", return_value=worker) as run_claude:
            result = run_claude_step(
                "plan",
                state,
                plan_dir,
                root=tmp_path,
                fresh=True,
                model="claude-sonnet-4",
            )

    assert result is worker
    run_claude.assert_called_once()


def test_shannon_retry_uses_fresh_session_without_recording_stale_session(
    tmp_path: Path,
) -> None:
    plan_dir, state = _mock_state(tmp_path)
    error = CliError("worker_stall", "stalled", extra={"session_id": "stale-shannon"})
    worker = _worker(session_id="fresh-shannon")

    with patch("arnold.pipelines.megaplan.workers.shannon.run_shannon_step", side_effect=[error, worker]) as run_shannon:
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

    with patch("arnold.pipelines.megaplan.workers._impl.run_codex_step", side_effect=[error, worker]) as run_codex:
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
