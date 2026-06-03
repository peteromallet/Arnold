"""Direct Claude worker tests for megaplan.workers."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from megaplan.types import AgentMode, CliError
from megaplan.workers import WorkerResult, session_key_for
from tests._workers_helpers import _mock_state


def test_run_claude_step_parses_structured_output(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    claude_output = json.dumps({
        "structured_output": plan_payload,
        "total_cost_usd": 0.05,
        "session_id": "sess-abc",
        "usage": {
            "input_tokens": 1000,
            "cache_read_input_tokens": 4000,
            "cache_creation_input_tokens": 500,
            "output_tokens": 250,
        },
    })
    fake_result = CommandResult(
        command=["claude"],
        cwd=tmp_path,
        returncode=0,
        stdout=claude_output,
        stderr="",
        duration_ms=500,
    )
    with patch("megaplan.workers.shannon.run_command", return_value=fake_result):
        result = run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True)
    assert result.payload == plan_payload
    assert result.cost_usd == 0.05
    assert result.session_id == "sess-abc"
    assert result.duration_ms == 500
    assert result.prompt_tokens == 5500
    assert result.completion_tokens == 250
    assert result.total_tokens == 5750

def test_run_claude_step_passes_effort_flag(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    claude_output = json.dumps({
        "structured_output": plan_payload,
        "total_cost_usd": 0.0,
        "session_id": "sess-effort",
    })
    fake_result = CommandResult(
        command=["claude"],
        cwd=tmp_path,
        returncode=0,
        stdout=claude_output,
        stderr="",
        duration_ms=10,
    )
    with patch("megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
        run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True, effort="low")
    invoked_cmd = run_command.call_args.args[0]
    assert "--effort" in invoked_cmd
    assert invoked_cmd[invoked_cmd.index("--effort") + 1] == "low"

def test_run_claude_step_rejects_invalid_effort(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    with pytest.raises(CliError, match="Unsupported claude effort level"):
        run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True, effort="bogus")

def test_run_claude_step_uses_prompt_override_without_builder(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    fake_result = CommandResult(
        command=["claude"],
        cwd=tmp_path,
        returncode=0,
        stdout=json.dumps({"structured_output": {"plan": "x", "questions": [], "success_criteria": [{"criterion": "test", "priority": "must"}], "assumptions": []}}),
        stderr="",
        duration_ms=10,
    )
    with patch("megaplan.workers.shannon.create_claude_prompt", side_effect=AssertionError("builder should not run")):
        with patch("megaplan.workers.shannon.run_command", return_value=fake_result) as run_command:
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True, prompt_override="custom prompt")
    command = run_command.call_args.args[0]
    assert command[0] == "bun"
    assert str(command[1]).endswith("vendor/shannon/index.ts")
    assert "-p" not in command
    assert "custom prompt" in run_command.call_args.kwargs["stdin_text"]
    assert "Your final answer must be exactly one valid JSON object" in run_command.call_args.kwargs["stdin_text"]
    prompt_file = plan_dir / ".megaplan" / "runs" / state["name"] / "plan" / "shannon" / "plan_v1_shannon_prompt.txt"
    prompt_text = prompt_file.read_text(encoding="utf-8")
    assert "custom prompt" in prompt_text
    assert "Output format:" in prompt_text
    assert "Your final answer must be exactly one valid JSON object" in prompt_text

def test_run_claude_step_raises_on_invalid_payload(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    # Missing required string key `plan` for "plan" step (array keys would
    # be auto-defaulted by `_normalize_worker_payload`).
    claude_output = json.dumps({
        "structured_output": {
            "questions": ["?"],
            "success_criteria": ["ok"],
            "assumptions": ["x"],
        },
        "total_cost_usd": 0.0,
    })
    fake_result = CommandResult(
        command=["claude"],
        cwd=tmp_path,
        returncode=0,
        stdout=claude_output,
        stderr="",
        duration_ms=100,
    )
    with patch("megaplan.workers.shannon.run_command", return_value=fake_result):
        with pytest.raises(CliError, match="missing required keys"):
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True)

def test_run_claude_step_attaches_session_id_on_timeout(tmp_path: Path) -> None:
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    state["sessions"][session_key_for("plan", "claude")] = {
        "id": "claude-session",
        "mode": "persistent",
        "created_at": "2026-03-20T00:00:00Z",
        "last_used_at": "2026-03-20T00:00:00Z",
        "refreshed": False,
    }

    timeout_error = CliError("worker_timeout", "Claude timed out", extra={"raw_output": "partial"})
    with patch("megaplan.workers.shannon.run_command", side_effect=timeout_error):
        with pytest.raises(CliError) as exc_info:
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=False)

    assert exc_info.value.extra["session_id"] != "claude-session"
    assert exc_info.value.extra["session_id"]

def test_run_step_with_worker_falls_back_from_claude_auth_error_to_codex(tmp_path: Path) -> None:
    from megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    args = Namespace(agent=None, ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[])
    auth_error = CliError(
        "auth_error",
        "Claude step failed: Not logged in · Please run /login",
        extra={"raw_output": "Not logged in · Please run /login"},
    )
    worker = WorkerResult(
        payload={
            "plan": "# Plan\nDo it.",
            "questions": [],
            "success_criteria": [{"criterion": "criterion", "priority": "must"}],
            "assumptions": [],
        },
        raw_output="",
        duration_ms=1,
        cost_usd=0.0,
        session_id="codex-fallback-session",
    )

    with patch("megaplan.workers._impl.resolve_agent_mode", return_value=("claude", "persistent", False, None)):
        with patch("megaplan.workers._impl.detect_available_agents", return_value=["claude", "codex"]):
            with patch("megaplan.workers.shannon.run_shannon_step", side_effect=auth_error) as mocked_shannon:
                with patch("megaplan.workers._impl.run_codex_step", return_value=worker) as mocked_codex:
                    result, agent, mode, refreshed = run_step_with_worker(
                        "plan",
                        state,
                        plan_dir,
                        args,
                        root=tmp_path,
                    )

    assert mocked_shannon.call_count == 1
    assert mocked_codex.call_count == 1
    assert result == worker
    assert agent == "codex"
    assert mode == "persistent"
    assert refreshed is True
    assert args._agent_fallback == {
        "requested": "claude",
        "resolved": "codex",
        "reason": "claude runtime unhealthy: auth_error",
    }


def test_run_step_with_worker_forwards_output_path_to_claude_shannon(tmp_path: Path) -> None:
    from megaplan.workers import run_step_with_worker

    plan_dir, state = _mock_state(tmp_path)
    args = Namespace(agent=None, ephemeral=False, fresh=False, persist=False, confirm_self_review=False, hermes=None, phase_model=[])
    output_path = plan_dir / "critique_check_issue_hints.json"
    worker = WorkerResult(
        payload={"checks": [{"id": "issue-hints", "findings": []}]},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
        session_id="claude-session",
    )

    with patch("megaplan.workers.shannon.run_shannon_step", return_value=worker) as mocked_shannon:
        result, agent, _mode, _refreshed = run_step_with_worker(
            "critique",
            state,
            plan_dir,
            args,
            root=tmp_path,
            resolved=AgentMode(
                agent="claude",
                mode="persistent",
                refreshed=False,
                model=None,
                resolved_model="claude-sonnet-4",
            ),
            output_path=output_path,
            read_only=True,
        )

    assert result == worker
    assert agent == "claude"
    assert mocked_shannon.call_args.kwargs["output_path"] == output_path
    assert mocked_shannon.call_args.kwargs["read_only"] is True


def test_run_claude_step_checks_final_prompt_before_run_command(
    tmp_path: Path,
) -> None:
    """Oversized prompt_override triggers guard before run_command is reached."""
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)

    def fake_check_prompt_size(prompt_text: str, *, phase: str) -> None:
        assert phase == "plan"
        assert prompt_text.startswith("custom claude prompt")
        raise CliError("prompt_oversized", "too large")

    with (
        patch("megaplan.workers.shannon.check_prompt_size", side_effect=fake_check_prompt_size),
        patch(
            "megaplan.workers.shannon.run_command",
            side_effect=AssertionError("run_command should not be reached"),
        ),
    ):
        with pytest.raises(CliError, match="too large"):
            run_claude_step(
                "plan",
                state,
                plan_dir,
                root=tmp_path,
                fresh=True,
                prompt_override="custom claude prompt",
            )


def test_run_claude_step_normal_prompt_dispatches_after_guard_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normal-sized prompt reaches run_command after the guard passes."""
    from megaplan._core import ensure_runtime_layout
    from megaplan.workers import CommandResult, run_claude_step

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }
    fake_result = CommandResult(
        command=["claude"],
        cwd=tmp_path,
        returncode=0,
        stdout=json.dumps({
            "structured_output": plan_payload,
            "session_id": "sess-normal",
            "total_cost_usd": 0.01,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }),
        stderr="",
        duration_ms=10,
    )

    guard_checked: list[str] = []

    def fake_check_prompt_size(prompt_text: str, *, phase: str) -> None:
        guard_checked.append(prompt_text)
        # Normal — no raise

    with (
        patch("megaplan.workers.shannon.check_prompt_size", side_effect=fake_check_prompt_size),
        patch("megaplan.workers.shannon.run_command", return_value=fake_result) as run_command,
    ):
        result = run_claude_step(
            "plan",
            state,
            plan_dir,
            root=tmp_path,
            fresh=True,
            prompt_override="normal claude prompt",
        )

    assert run_command.call_count == 1
    assert result.payload == plan_payload
    assert result.session_id == "sess-normal"
    # Guard was consulted with the full prompt after schema augmentation
    assert len(guard_checked) == 1
    assert "normal claude prompt" in guard_checked[0]
    # Projection-specific heading is present in the prompt text
    prompt_file = plan_dir / ".megaplan" / "runs" / state["name"] / "plan" / "shannon" / "plan_v1_shannon_prompt.txt"
    prompt_text = prompt_file.read_text(encoding="utf-8")
    assert "normal claude prompt" in prompt_text
    assert "Output format:" in prompt_text


def test_shannon_file_fallback_prefers_supplied_output_path(tmp_path: Path) -> None:
    from megaplan.workers.shannon import _apply_file_fallback

    plan_dir = tmp_path
    aggregate = {
        "checks": [
            {"id": "aggregate-a", "findings": [{"severity": "high", "description": "wrong"}]},
            {"id": "aggregate-b", "findings": []},
        ]
    }
    per_check = {
        "checks": [
            {"id": "issue-hints", "findings": [{"severity": "medium", "description": "right"}]}
        ]
    }
    (plan_dir / "critique_output.json").write_text(json.dumps(aggregate), encoding="utf-8")
    output_path = plan_dir / "critique_check_issue_hints.json"
    output_path.write_text(json.dumps(per_check), encoding="utf-8")

    result = _apply_file_fallback("critique", {"checks": []}, plan_dir, output_path=output_path)

    assert result == per_check
