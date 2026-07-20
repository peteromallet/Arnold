from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

import pytest

from arnold_pipelines.megaplan.execute.batch import (
    _ExecuteWorkspaceFingerprint,
    _capture_execute_workspace_fingerprint,
    _execute_configured_specs,
    _run_execute_worker_with_configured_fallback,
)
from arnold_pipelines.megaplan.types import CliError, parse_agent_spec
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan.workers.hermes import (
    _raise_for_terminal_provider_failure,
)


GLM_CHAIN = (
    "hermes:zhipu:glm-5.2",
    "hermes:fireworks:accounts/fireworks/models/glm-5p2",
    "codex:gpt-5.4",
)


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        phase_model=["execute=codex:gpt-5.4"],
        tier_models={"execute": {7: list(GLM_CHAIN)}},
    )


def _success(kwargs: dict) -> WorkerResult:
    worker = WorkerResult(
        payload={"success": True},
        raw_output="{}",
        duration_ms=1,
        cost_usd=0.0,
    )
    worker.configured_specs = tuple(kwargs["ledger_configured_specs"])
    worker.attempt_index = kwargs["ledger_attempt_index"]
    worker.attempted_specs = tuple(kwargs["ledger_attempted_specs"])
    worker.failed_attempt_reasons = tuple(kwargs["ledger_failed_attempt_reasons"])
    worker.fallback_trigger = kwargs["ledger_fallback_trigger"]
    return worker


def _install_harness_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fingerprints: list[_ExecuteWorkspaceFingerprint] | None = None,
) -> None:
    stable = _ExecuteWorkspaceFingerprint("head", (("tracked.py", "digest"),))
    values = iter(fingerprints or [stable] * 8)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._capture_execute_workspace_fingerprint",
        lambda _root: next(values),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._render_execute_prompt_for_dispatch",
        lambda **kwargs: kwargs.get("prompt_override") or "execute",
    )

    def resolve(_args: argparse.Namespace, spec: str):
        parsed = parse_agent_spec(spec)
        return parsed.agent, "persistent", parsed.model

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.execute.batch._resolve_tier_spec",
        resolve,
    )


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    return _run_execute_worker_with_configured_fallback(
        root=tmp_path,
        plan_dir=tmp_path / ".megaplan" / "plans" / "p",
        state={"active_step": {"run_id": "run-1"}},
        args=_args(),
        agent="hermes",
        mode="persistent",
        refreshed=False,
        model="zhipu:glm-5.2",
        effort=None,
        resolved_model="zhipu:glm-5.2",
        prompt_override="execute",
        configured_specs=GLM_CHAIN,
        batch_number=7,
    )


def test_tier_selection_preserves_glm_fireworks_codex_chain() -> None:
    assert _execute_configured_specs(
        _args(),
        selected_tier_spec=GLM_CHAIN[0],
        default_spec=GLM_CHAIN[0],
    ) == GLM_CHAIN


def test_execute_fingerprint_detects_worktree_and_index_changes(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.py"
    tracked.write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)

    before = _capture_execute_workspace_fingerprint(tmp_path)
    tracked.write_text("after\n", encoding="utf-8")
    after_worktree = _capture_execute_workspace_fingerprint(tmp_path)
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    after_index = _capture_execute_workspace_fingerprint(tmp_path)

    assert before.error is None
    assert before != after_worktree
    assert after_worktree != after_index


@pytest.mark.parametrize("failure_code", ["worker_timeout", "stream_content_stall"])
def test_glm_retryable_failure_advances_to_fireworks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_code: str,
) -> None:
    _install_harness_stubs(monkeypatch)
    calls: list[str] = []

    def dispatch(*_args, **kwargs):
        resolved = kwargs["resolved"]
        calls.append(f"{resolved.agent}:{resolved.model}")
        if len(calls) == 1:
            raise CliError(failure_code, "provider stalled")
        return _success(kwargs), resolved.agent, resolved.mode, True

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        dispatch,
    )
    worker, agent, _mode, _refreshed = _run(monkeypatch, tmp_path)

    assert calls == ["hermes:zhipu:glm-5.2", "hermes:fireworks:accounts/fireworks/models/glm-5p2"]
    assert agent == "hermes"
    assert worker.attempt_index == 1
    assert worker.failed_attempt_reasons == ("availability",)


def test_retryable_failures_advance_through_fireworks_to_codex(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_harness_stubs(monkeypatch)
    calls: list[str] = []

    def dispatch(*_args, **kwargs):
        resolved = kwargs["resolved"]
        calls.append(f"{resolved.agent}:{resolved.model}")
        if len(calls) < 3:
            raise CliError("worker_timeout", "provider timed out")
        return _success(kwargs), resolved.agent, resolved.mode, True

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        dispatch,
    )
    worker, agent, _mode, _refreshed = _run(monkeypatch, tmp_path)

    assert calls == [
        "hermes:zhipu:glm-5.2",
        "hermes:fireworks:accounts/fireworks/models/glm-5p2",
        "codex:gpt-5.4",
    ]
    assert agent == "codex"
    assert worker.attempt_index == 2
    assert worker.failed_attempt_reasons == ("availability", "availability")


def test_non_retryable_failure_does_not_advance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_harness_stubs(monkeypatch)
    calls = 0

    def dispatch(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise CliError("auth_error", "invalid API key")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        dispatch,
    )
    with pytest.raises(CliError, match="invalid API key") as raised:
        _run(monkeypatch, tmp_path)

    assert raised.value.code == "auth_error"
    assert calls == 1


def test_retryable_failure_with_workspace_change_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_harness_stubs(
        monkeypatch,
        fingerprints=[
            _ExecuteWorkspaceFingerprint("head", (("tracked.py", "before"),)),
            _ExecuteWorkspaceFingerprint("head", (("tracked.py", "after"),)),
        ],
    )
    calls = 0

    def dispatch(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise CliError("worker_timeout", "provider timed out")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.workers.run_step_with_worker",
        dispatch,
    )
    with pytest.raises(CliError) as raised:
        _run(monkeypatch, tmp_path)

    assert raised.value.code == "execute_fallback_unsafe"
    assert calls == 1


def test_terminal_glm_streaming_timeout_is_routing_failure() -> None:
    with pytest.raises(CliError) as raised:
        _raise_for_terminal_provider_failure(
            {
                "failed": True,
                "non_retryable": True,
                "error": "Streaming deadline retry ceiling reached; no retries remain",
            },
            step="execute",
        )

    assert raised.value.code == "streaming_timeout"
