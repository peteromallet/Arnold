"""Direct tmux and Shannon session lifecycle tests for megaplan.workers."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import time
from unittest.mock import patch

import pytest

from arnold.pipelines.megaplan.workers import WorkerResult
from tests._workers_helpers import _mock_state


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux not installed")
def test_tmux_session_create_exists_teardown_idempotent() -> None:
    """TmuxSession exists() → teardown() → exists() → second teardown() safe."""
    import uuid
    from arnold.pipelines.megaplan.runtime.process import TmuxSession

    name = f"megaplan-test-tmuxsession-{uuid.uuid4().hex[:8]}"
    session = TmuxSession(name)

    # Ensure clean starting state.
    session.teardown()

    # Create a detached tmux session that sleeps for 300s.
    result = subprocess.run(
        ["tmux", "new-session", "-d", "-s", name, "sleep", "300"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    try:
        # exists() must report True for a live session.
        assert session.exists() is True

        # pane_pids must return non-empty list.
        from arnold.pipelines.megaplan.runtime.process import pane_pids

        pids = pane_pids(name)
        assert len(pids) > 0
        for pid in pids:
            assert pid.isdigit()

        # teardown() must reap the session.
        session.teardown()
        # exists() must be False after teardown.
        assert session.exists() is False

        # Second teardown() must be a safe no-op (no exception).
        session.teardown()
        # Still False.
        assert session.exists() is False
    finally:
        # Best-effort cleanup.
        session.teardown()

@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux not installed")
def test_wedge_regression_teardown_reaps_orphaned_session_pids_dead() -> None:
    """Simulate a shannon-like wrapper: spawn sleep inside a detached tmux
    session, SIGKILL the subprocess that launched it, then assert TmuxSession
    teardown reaps the now-orphaned session by name and captured PIDs are dead."""
    import uuid
    from arnold.pipelines.megaplan.runtime.process import TmuxSession, pane_pids

    name = f"megaplan-wedge-{uuid.uuid4().hex[:8]}"
    session = TmuxSession(name)

    # Clean start.
    session.teardown()

    # Start a subprocess that creates a detached tmux session and then stays
    # alive briefly (the "wrapper").
    wrapper = subprocess.Popen(
        [
            "sh",
            "-c",
            f"tmux new-session -d -s {name} sleep 300; sleep 60",
        ],
    )
    try:
        # Give the tmux session a moment to come up.
        time.sleep(0.3)

        # Capture PIDs inside the session before killing the wrapper.
        pids_before = pane_pids(name)
        assert len(pids_before) > 0, "Expected at least one pane PID"

        # SIGKILL the wrapper — the tmux session should survive because it is
        # owned by the tmux server, not the wrapper process.
        wrapper.kill()
        wrapper.wait(timeout=5)

        # The session must still exist (orphaned).
        assert session.exists() is True

        # Teardown must reap the session by name.
        session.teardown()
        # Session must be gone.
        assert session.exists() is False

        # Assert captured PIDs are dead. On Linux, /proc/<pid>/stat or
        # os.kill(pid, 0) is the portable check.
        import os as _os
        for pid_str in pids_before:
            pid = int(pid_str)
            try:
                _os.kill(pid, 0)
                # Process still exists — but it may be a zombie. Check that it's
                # not running.
                try:
                    stat_path = f"/proc/{pid}/stat"
                    with open(stat_path, "r") as f:
                        stat = f.read()
                    # State character is at position 2 (0-indexed) after the closing
                    # paren of the comm field.
                    state_char = stat.split(") ", 1)[1][0] if ") " in stat else "?"
                    assert state_char in ("Z", "X", "?"), (
                        f"PID {pid} still alive (state={state_char}) after teardown"
                    )
                except FileNotFoundError:
                    # /proc/<pid>/stat missing → process is dead. Good.
                    pass
            except OSError:
                # ESRCH: process does not exist. Good.
                pass

        # detect_orphans with this plan's pattern must return clean.
        from arnold.pipelines.megaplan.runtime.process import detect_orphans
        orphans = detect_orphans("megaplan-wedge-*")
        assert name not in orphans
    finally:
        # Best-effort cleanup: reap the tmux session, kill wrapper if alive.
        session.teardown()
        try:
            wrapper.kill()
            wrapper.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass

def test_reconcile_reaps_residual_same_name_session_and_proceeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Residual same-(plan,step) session → reconcile reaps it and
    run_shannon_step PROCEEDS (no raise)."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult
    from arnold.pipelines.megaplan.runtime.process import TmuxSession

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    plan_dir, state = _mock_state(tmp_path)

    # Construct the deterministic session name that run_shannon_step will use.
    # T9 Step 7: session name is sha256(plan|step|iteration)[:12], not megaplan-slug.
    import hashlib
    session_name = hashlib.sha256(f"{state['name']}|plan|{state.get('iteration', 0)}".encode()).hexdigest()[:12]

    # Track calls.
    teardown_calls: list[str] = []

    # TmuxSession that starts as existing and tracks teardown.
    class FakeTmuxSession:
        def __init__(self, name: str) -> None:
            self.name = name
            self._exists = True

        def teardown(self) -> None:
            teardown_calls.append(self.name)
            self._exists = False

        def exists(self) -> bool:
            return self._exists

    # Pane PIDs stub.
    def fake_pane_pids(session_name: str) -> list[str]:
        return ["12345"]

    # Successful CommandResult — must satisfy plan.json required keys.
    plan_payload = {
        "plan": "Execute the plan.",
        "questions": [],
        "success_criteria": [{"criterion": "It works", "priority": "must", "requires": []}],
        "assumptions": [],
    }
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=json.dumps([{"type": "result", "subtype": "success",
                            "result": json.dumps(plan_payload),
                            "session_id": "s1", "total_cost_usd": 0.01,
                            "usage": {"input_tokens": 1, "output_tokens": 1}}]),
        stderr="",
        duration_ms=100,
    )

    with patch("arnold.pipelines.megaplan.workers.shannon.TmuxSession", FakeTmuxSession), \
         patch("arnold.pipelines.megaplan.workers.shannon.pane_pids", fake_pane_pids), \
         patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result):
        result = run_shannon_step("plan", state, plan_dir, root=tmp_path, fresh=True)

    # reconcile must have called teardown (reaping the residual).
    assert session_name in teardown_calls, (
        f"Expected teardown({session_name!r}) during reconcile, got {teardown_calls}"
    )
    # The step must have proceeded successfully (no OrphanDetectedError / CliError).
    assert isinstance(result, WorkerResult)
    assert result.payload is not None

def test_backstop_unkillable_session_raises_orphan_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatch teardown to no-op while exists() stays True →
    OrphanDetectedError (wrapped in CliError) raised."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.types import CliError

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    plan_dir, state = _mock_state(tmp_path)

    # Unkillable session: teardown does nothing, exists always True.
    class UnkillableTmuxSession:
        def __init__(self, name: str) -> None:
            self.name = name

        def teardown(self) -> None:
            pass  # no-op — session survives

        def exists(self) -> bool:
            return True  # always alive

    def fake_pane_pids(session_name: str) -> list[str]:
        return ["99999"]

    with patch("arnold.pipelines.megaplan.workers.shannon.TmuxSession", UnkillableTmuxSession), \
         patch("arnold.pipelines.megaplan.workers.shannon.pane_pids", fake_pane_pids):
        with pytest.raises(CliError) as exc_info:
            run_shannon_step("plan", state, plan_dir, root=tmp_path, fresh=True)

    assert exc_info.value.code == "worker_error"
    assert "orphan" in exc_info.value.message.lower()
    assert exc_info.value.extra is not None
    assert "sessions" in exc_info.value.extra
    assert "pids" in exc_info.value.extra

def test_different_plan_name_session_not_touched_no_backstop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A session with a different-plan-name is NOT touched by reconcile and
    does NOT trigger OrphanDetectedError (backstop is plan-scoped only)."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "0")
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "0")
    plan_dir, state = _mock_state(tmp_path)

    # Teardown tracker — must NOT be called for the different-plan session name.
    teardown_calls: list[str] = []

    class SpyTmuxSession:
        def __init__(self, name: str) -> None:
            self.name = name
            self._exists = False  # plan's own name is clean

        def teardown(self) -> None:
            teardown_calls.append(self.name)
            self._exists = False

        def exists(self) -> bool:
            return self._exists

    def fake_pane_pids(session_name: str) -> list[str]:
        return []

    plan_payload = {
        "plan": "Execute the plan.",
        "questions": [],
        "success_criteria": [{"criterion": "It works", "priority": "must", "requires": []}],
        "assumptions": [],
    }
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=json.dumps([{"type": "result", "subtype": "success",
                            "result": json.dumps(plan_payload),
                            "session_id": "s1", "total_cost_usd": 0.01,
                            "usage": {"input_tokens": 1, "output_tokens": 1}}]),
        stderr="",
        duration_ms=100,
    )

    with patch("arnold.pipelines.megaplan.workers.shannon.TmuxSession", SpyTmuxSession), \
         patch("arnold.pipelines.megaplan.workers.shannon.pane_pids", fake_pane_pids), \
         patch("arnold.pipelines.megaplan.workers.shannon.run_command", return_value=fake_result):
        result = run_shannon_step("plan", state, plan_dir, root=tmp_path, fresh=True)

    # reconcile always calls teardown on the plan's own session (idempotent,
    # no-op for a non-existent session). The key assertion: it must NOT have
    # touched a session belonging to a different plan. Since the session_name is
    # deterministically scoped to this plan+step, every teardown call must be
    # for this plan's name only.
    assert isinstance(result, WorkerResult)
    assert result.payload is not None
    # T9 Step 7: session name is sha256(plan|step|iteration)[:12].
    import hashlib
    plan_session = hashlib.sha256(f"{state['name']}|plan|{state.get('iteration', 0)}".encode()).hexdigest()[:12]
    for call in teardown_calls:
        assert call == plan_session, f"Touched unrelated session: {call}"

def test_detect_orphans_degrade_on_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """detect_orphans returns [] when tmux binary is missing."""
    from arnold.pipelines.megaplan.runtime.process import detect_orphans

    def fake_run(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("tmux not found")

    with patch("arnold.pipelines.megaplan.runtime.process.subprocess.run", fake_run):
        result = detect_orphans("megaplan-*")
    assert result == []

def test_pane_pids_degrade_on_file_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """pane_pids returns [] when tmux binary is missing."""
    from arnold.pipelines.megaplan.runtime.process import pane_pids

    def fake_run(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("tmux not found")

    with patch("arnold.pipelines.megaplan.runtime.process.subprocess.run", fake_run):
        result = pane_pids("any-session")
    assert result == []

def test_tmux_session_exists_degrade_on_file_not_found() -> None:
    """TmuxSession.exists() returns False when tmux is missing."""
    from arnold.pipelines.megaplan.runtime.process import TmuxSession

    def fake_run(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("tmux not found")

    with patch("arnold.pipelines.megaplan.runtime.process.subprocess.run", fake_run):
        session = TmuxSession("any-session")
        assert session.exists() is False

def test_tmux_session_teardown_degrade_on_file_not_found() -> None:
    """TmuxSession.teardown() does not raise when tmux is missing."""
    from arnold.pipelines.megaplan.runtime.process import TmuxSession

    def fake_run(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("tmux not found")

    with patch("arnold.pipelines.megaplan.runtime.process.subprocess.run", fake_run):
        session = TmuxSession("any-session")
        # Must not raise.
        session.teardown()

def test_both_run_command_sites_receive_tmux_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spy on run_command to assert BOTH the readiness-probe call and the
    main call receive the same tmux_session object."""
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers.shannon import run_shannon_step
    from arnold.pipelines.megaplan.workers import CommandResult

    ensure_runtime_layout(tmp_path)
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "0")
    # Force the readiness probe ON so we get both call sites.
    monkeypatch.setenv("MEGAPLAN_SHANNON_READINESS_PROBE", "always")
    plan_dir, state = _mock_state(tmp_path)

    # Track tmux_session kwarg passed to each run_command call.
    run_command_calls: list[dict[str, object]] = []

    plan_payload = {
        "plan": "Execute the plan.",
        "questions": [],
        "success_criteria": [{"criterion": "It works", "priority": "must", "requires": []}],
        "assumptions": [],
    }
    fake_result = CommandResult(
        command=[],
        cwd=tmp_path,
        returncode=0,
        stdout=json.dumps([{"type": "result", "subtype": "success",
                            "result": json.dumps(plan_payload),
                            "session_id": "s1", "total_cost_usd": 0.01,
                            "usage": {"input_tokens": 1, "output_tokens": 1}}]),
        stderr="",
        duration_ms=100,
    )

    def spy_run_command(*args: object, **kwargs: object) -> CommandResult:
        run_command_calls.append(kwargs)
        return fake_result

    with patch("arnold.pipelines.megaplan.workers.shannon.run_command", spy_run_command):
        result = run_shannon_step("plan", state, plan_dir, root=tmp_path, fresh=True)

    assert isinstance(result, WorkerResult)
    assert result.payload is not None

    # Must have at least 2 calls: readiness probe + main command.
    assert len(run_command_calls) >= 2, (
        f"Expected at least 2 run_command calls (probe + main), got {len(run_command_calls)}"
    )

    # All calls must have tmux_session= set.
    for i, call_kwargs in enumerate(run_command_calls):
        assert "tmux_session" in call_kwargs, (
            f"run_command call {i} missing tmux_session kwarg"
        )
        tmux_session = call_kwargs["tmux_session"]
        assert tmux_session is not None, (
            f"run_command call {i} tmux_session is None"
        )
        # All calls must share the same TmuxSession object.
        first_session = run_command_calls[0].get("tmux_session")
        assert tmux_session is first_session, (
            f"run_command call {i} has different tmux_session than call 0"
        )

    # env must have SHANNON_TMUX_SESSION_NAME set (T9 Step 7: sha256 hash, 12 hex chars).
    for call_kwargs in run_command_calls:
        env = call_kwargs.get("env")
        assert isinstance(env, dict)
        assert "SHANNON_TMUX_SESSION_NAME" in env, (
            "SHANNON_TMUX_SESSION_NAME not in env"
        )
        assert len(env["SHANNON_TMUX_SESSION_NAME"]) == 12
        assert all(c in "0123456789abcdef" for c in env["SHANNON_TMUX_SESSION_NAME"])


def test_shannon_success_result_detector_accepts_jsonl_success() -> None:
    from arnold.pipelines.megaplan.workers.shannon import _raw_contains_success_result

    raw = "\n".join(
        [
            json.dumps({"type": "system", "subtype": "init"}),
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "terminal_reason": "completed",
                    "result": "{}",
                }
            ),
        ]
    )

    assert _raw_contains_success_result(raw) is True


def test_shannon_success_result_detector_rejects_error_jsonl() -> None:
    from arnold.pipelines.megaplan.workers.shannon import _raw_contains_success_result

    raw = json.dumps(
        {
            "type": "result",
            "subtype": "error",
            "is_error": True,
            "terminal_reason": "failed",
            "result": "nope",
        }
    )

    assert _raw_contains_success_result(raw) is False
