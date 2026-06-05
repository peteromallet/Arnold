"""Direct environment and runtime-policy tests for megaplan.workers."""

from __future__ import annotations

import json
import signal
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.pipelines.megaplan._core import PHASE_RUNTIME_POLICY
from arnold.pipelines.megaplan.workers import (
    _codex_child_env,
    _codex_timeout_for_step,
    _external_worker_env,
    _merge_partial_output,
)
from tests._workers_helpers import _mock_state


def test_external_worker_env_strips_progress_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEGAPLAN_PROGRESS_ENABLED", "1")
    monkeypatch.setenv("MEGAPLAN_PROGRESS_EPIC_ID", "epic-1")
    monkeypatch.setenv("CODEX_THREAD_ID", "outer-thread")
    monkeypatch.setenv("CODEX_CI", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")

    claude_env = _external_worker_env()
    codex_env = _codex_child_env()

    assert "MEGAPLAN_PROGRESS_ENABLED" not in claude_env
    assert "MEGAPLAN_PROGRESS_EPIC_ID" not in claude_env
    assert claude_env["OPENAI_API_KEY"] == "secret"
    assert "MEGAPLAN_PROGRESS_ENABLED" not in codex_env
    assert "MEGAPLAN_PROGRESS_EPIC_ID" not in codex_env
    assert "CODEX_THREAD_ID" not in codex_env
    assert "CODEX_CI" not in codex_env
    assert codex_env["OPENAI_API_KEY"] == "secret"

def test_run_command_heartbeats_while_subprocess_is_silent_but_alive() -> None:
    """A subprocess that runs without emitting output must still produce
    activity_callback liveness beats, so a long-but-alive worker (e.g. codex
    exec mid-turn) does not look idle to the outer `megaplan auto` watchdog.
    """
    import sys as _sys
    import threading as _threading

    from arnold.pipelines.megaplan.workers._impl import run_command

    calls: list[tuple[str, str]] = []
    lock = _threading.Lock()

    def _cb(kind: str, detail: str) -> None:
        with lock:
            calls.append((kind, detail))

    # Sleep ~7s emitting nothing on stdout/stderr — longer than the 5s
    # heartbeat interval, so at least one liveness beat must fire.
    run_command(
        [_sys.executable, "-c", "import time; time.sleep(7)"],
        cwd=Path.cwd(),
        timeout=30,
        activity_callback=_cb,
    )

    liveness_beats = [c for c in calls if c[0] == "liveness"]
    assert liveness_beats, f"expected at least one liveness beat, got {calls!r}"

def test_step_schema_filenames_cover_all_steps() -> None:
    from arnold.pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES
    required_steps = {"plan", "prep", "revise", "critique", "gate", "finalize", "execute", "review"}
    assert required_steps.issubset(set(STEP_SCHEMA_FILENAMES.keys()))

def test_step_schema_filenames_reference_existing_schemas() -> None:
    from arnold.pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES
    from arnold.pipelines.megaplan.schemas import SCHEMAS
    for step, filename in STEP_SCHEMA_FILENAMES.items():
        assert filename in SCHEMAS, f"Step '{step}' references non-existent schema '{filename}'"

def test_phase_runtime_policy_covers_all_worker_steps() -> None:
    from arnold.pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES

    assert set(PHASE_RUNTIME_POLICY) == set(STEP_SCHEMA_FILENAMES)

def test_codex_timeout_for_step_caps_non_execute_steps() -> None:
    assert _codex_timeout_for_step("plan") == 900

def test_codex_timeout_for_step_preserves_execute_timeout() -> None:
    assert _codex_timeout_for_step("execute") == 7200

def test_codex_child_env_strips_parent_session_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from arnold.pipelines.megaplan.workers import _codex_child_env

    monkeypatch.setenv("CODEX_THREAD_ID", "parent-thread")
    monkeypatch.setenv("CODEX_CI", "1")
    monkeypatch.setenv("CODEX_MANAGED_BY_NPM", "1")

    env = _codex_child_env()

    assert "CODEX_THREAD_ID" not in env
    assert "CODEX_CI" not in env
    assert env["CODEX_MANAGED_BY_NPM"] == "1"

def test_merge_partial_output_appends_output_file_contents(tmp_path: Path) -> None:
    output_path = tmp_path / "partial.json"
    output_path.write_text('{"partial": true}', encoding="utf-8")

    merged = _merge_partial_output("stderr text", output_path)

    assert "stderr text" in merged
    assert "[partial_output_file]" in merged
    assert '{"partial": true}' in merged

def test_run_claude_step_uses_cwd_for_add_dir_when_worktree_differs(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import (
        CommandResult,
        run_claude_step,
        set_work_dir_override,
    )

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    # Simulate a worktree: project_dir is /tmp/.../project but the current
    # "checkout" is /tmp/.../worktree.
    worktree_dir = tmp_path / "worktree"
    worktree_dir.mkdir()
    set_work_dir_override(worktree_dir)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    captured: dict[str, Any] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=json.dumps({"result": json.dumps(plan_payload), "total_cost_usd": 0.0}),
            stderr="",
            duration_ms=1,
        )

    try:
        with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True)
    finally:
        set_work_dir_override(None)

    command = captured["command"]
    assert "--add-dir" not in command
    assert Path(captured["cwd"]) == worktree_dir

def test_run_claude_step_honors_explicit_work_dir_override(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import (
        CommandResult,
        run_claude_step,
        set_work_dir_override,
    )

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    # project_dir lives at tmp_path/project; --work-dir explicitly forces a
    # different path (simulating the operator passing --work-dir on the CLI).
    forced_dir = tmp_path / "forced"
    forced_dir.mkdir()
    set_work_dir_override(forced_dir)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    captured: dict[str, Any] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout=json.dumps({"result": json.dumps(plan_payload), "total_cost_usd": 0.0}),
            stderr="",
            duration_ms=1,
        )

    try:
        with patch("arnold.pipelines.megaplan.workers.shannon.run_command", side_effect=fake_run_command):
            run_claude_step("plan", state, plan_dir, root=tmp_path, fresh=True)
    finally:
        set_work_dir_override(None)

    command = captured["command"]
    assert "--add-dir" not in command

def test_run_codex_step_uses_work_dir_for_dash_c_not_project_dir(
    tmp_path: Path,
) -> None:
    from arnold.pipelines.megaplan._core import ensure_runtime_layout
    from arnold.pipelines.megaplan.workers import (
        CommandResult,
        run_codex_step,
        set_work_dir_override,
    )

    ensure_runtime_layout(tmp_path)
    plan_dir, state = _mock_state(tmp_path)
    worktree_dir = tmp_path / "worktree"
    worktree_dir.mkdir()
    set_work_dir_override(worktree_dir)

    plan_payload = {
        "plan": "# Plan\nDo it.",
        "questions": [],
        "success_criteria": [{"criterion": "criterion", "priority": "must"}],
        "assumptions": [],
    }

    captured: dict[str, Any] = {}

    def fake_run_command(command: list[str], **kwargs: object) -> CommandResult:
        captured["command"] = command
        output_idx = command.index("-o") + 1
        Path(command[output_idx]).write_text(json.dumps(plan_payload), encoding="utf-8")
        return CommandResult(
            command=command,
            cwd=tmp_path,
            returncode=0,
            stdout="",
            stderr="",
            duration_ms=1,
        )

    try:
        with patch("arnold.pipelines.megaplan.workers._impl.run_command", side_effect=fake_run_command):
            run_codex_step("plan", state, plan_dir, root=tmp_path, persistent=False, fresh=True)
    finally:
        set_work_dir_override(None)

    command = captured["command"]
    cd_idx = command.index("-C") + 1
    add_dir_idx = command.index("--add-dir") + 1
    # -C (source-code cwd) should follow the worktree, NOT project_dir.
    assert Path(command[cd_idx]) == worktree_dir
    assert Path(command[cd_idx]) != Path(state["config"]["project_dir"])
    # --add-dir still grants access to the plan's artifacts directory
    # (unchanged by the worktree fix).
    assert Path(command[add_dir_idx]) == plan_dir

def test_resolve_work_dir_defaults_to_project_dir_when_no_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: without --work-dir and without any override set,
    resolve_work_dir() should return the plan's stored project_dir rather
    than falling back to the shell's CWD. This prevents codex from being
    sandboxed to an arbitrary subdirectory when the operator cd's around
    between ``megaplan init`` and ``megaplan execute``.
    """
    from arnold.pipelines.megaplan.workers import resolve_work_dir, set_work_dir_override

    _plan_dir, state = _mock_state(tmp_path)
    project_dir = Path(state["config"]["project_dir"])

    # Simulate the shell being somewhere else (a child directory of the
    # project) when execute fires. Without fix 1, resolve_work_dir would
    # return this narrower CWD.
    narrower_cwd = project_dir / "child-subdir"
    narrower_cwd.mkdir()
    monkeypatch.chdir(narrower_cwd)

    set_work_dir_override(None)
    try:
        resolved = resolve_work_dir(state)
    finally:
        set_work_dir_override(None)

    assert resolved == project_dir, (
        "resolve_work_dir must default to the plan's project_dir when no "
        f"--work-dir override is set (got {resolved})"
    )

def test_warn_if_work_dir_differs_from_project_dir_prints_on_divergence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fix 2: a divergent work_dir must surface a stderr WARNING, not a
    buried info line. The message must identify both directories and offer
    a concrete remediation.
    """
    from arnold.pipelines.megaplan.workers import (
        set_work_dir_override,
        warn_if_work_dir_differs_from_project_dir,
    )

    _plan_dir, state = _mock_state(tmp_path)
    project_dir = Path(state["config"]["project_dir"])
    narrower = project_dir / "subdir"
    narrower.mkdir()

    set_work_dir_override(narrower)
    try:
        warn_if_work_dir_differs_from_project_dir(state)
    finally:
        set_work_dir_override(None)

    captured = capsys.readouterr()
    assert "WARNING" in captured.err
    assert str(project_dir) in captured.err
    assert str(narrower) in captured.err
    assert "--work-dir" in captured.err

def test_warn_if_work_dir_differs_from_project_dir_silent_when_matching(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from arnold.pipelines.megaplan.workers import (
        set_work_dir_override,
        warn_if_work_dir_differs_from_project_dir,
    )

    _plan_dir, state = _mock_state(tmp_path)
    project_dir = Path(state["config"]["project_dir"])

    set_work_dir_override(project_dir)
    try:
        warn_if_work_dir_differs_from_project_dir(state)
    finally:
        set_work_dir_override(None)

    captured = capsys.readouterr()
    assert captured.err == ""

def test_resolve_work_dir_explicit_override_still_wins(tmp_path: Path) -> None:
    """Fix 1 must remain backward-compatible with --work-dir: an explicit
    override should still beat the project_dir default.
    """
    from arnold.pipelines.megaplan.workers import resolve_work_dir, set_work_dir_override

    _plan_dir, state = _mock_state(tmp_path)
    forced = tmp_path / "forced"
    forced.mkdir()

    set_work_dir_override(forced)
    try:
        resolved = resolve_work_dir(state)
    finally:
        set_work_dir_override(None)

    assert resolved == forced


# ---------------------------------------------------------------------------
# Per-worker filesystem-state isolation (execution.worker_isolated_env_vars)
# ---------------------------------------------------------------------------


def _patch_isolated_vars(names: list[str]):
    """Patch get_effective so worker_isolated_env_vars resolves to *names*."""
    from arnold.pipelines.megaplan.types import DEFAULTS

    def _fake_get_effective(section: str, key: str):
        if (section, key) == ("execution", "worker_isolated_env_vars"):
            return names
        return DEFAULTS[f"{section}.{key}"]

    return patch("arnold.pipelines.megaplan.workers._impl.get_effective", _fake_get_effective)


def test_isolation_unset_leaves_env_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty config list = no isolation; the worker env is built as before."""
    monkeypatch.setenv("ASTRID_HOME", "/real/home")
    with _patch_isolated_vars([]):
        env = _external_worker_env()
        codex_env = _codex_child_env()
    # Existing value preserved verbatim (no temp redirect injected).
    assert env["ASTRID_HOME"] == "/real/home"
    assert codex_env["ASTRID_HOME"] == "/real/home"


def test_isolation_redirects_configured_vars_to_temp_dirs() -> None:
    """Configured vars get fresh, existing, unique temp dirs in the built env."""
    import tempfile

    with _patch_isolated_vars(["ASTRID_HOME", "ASTRID_PROJECTS_ROOT"]):
        env = _external_worker_env()

    tmp_root = str(Path(tempfile.gettempdir()))
    for var in ("ASTRID_HOME", "ASTRID_PROJECTS_ROOT"):
        assert var in env
        p = Path(env[var])
        assert p.is_dir(), f"{var} temp dir was not created"
        assert str(p).startswith(tmp_root), f"{var} not under OS temp dir"
    # The two vars get DISTINCT directories.
    assert env["ASTRID_HOME"] != env["ASTRID_PROJECTS_ROOT"]


def test_isolation_unique_per_worker_invocation() -> None:
    """Each worker spawn (each env build) mints distinct temp dirs."""
    with _patch_isolated_vars(["ASTRID_HOME"]):
        env_a = _external_worker_env()
        env_b = _external_worker_env()
        codex_env = _codex_child_env()

    homes = {env_a["ASTRID_HOME"], env_b["ASTRID_HOME"], codex_env["ASTRID_HOME"]}
    assert len(homes) == 3, "worker isolation dirs collided across invocations"
    for home in homes:
        assert Path(home).is_dir()


def test_isolation_overwrites_only_listed_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only listed vars are redirected; every other env key is preserved."""
    monkeypatch.setenv("ASTRID_HOME", "/real/home")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret")
    with _patch_isolated_vars(["ASTRID_HOME"]):
        env = _external_worker_env(turn_id="t1", actor_id="a1")

    # Listed var redirected away from the real value...
    assert env["ASTRID_HOME"] != "/real/home"
    assert Path(env["ASTRID_HOME"]).is_dir()
    # ...while unrelated keys (API keys, megaplan ids) are untouched.
    assert env["OPENAI_API_KEY"] == "secret-key"
    assert env["ANTHROPIC_API_KEY"] == "anthropic-secret"
    assert env["MEGAPLAN_TURN_ID"] == "t1"
    assert env["MEGAPLAN_ACTOR_ID"] == "a1"
