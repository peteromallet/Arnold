"""Regression tests for cloud watchdog wrapper invariants."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"


def _wrapper(name: str) -> str:
    return (WRAPPER_DIR / name).read_text(encoding="utf-8")


def test_watchdog_defaults_editable_install_to_dedicated_branch() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'SRC_DIR="${CLOUD_WATCHDOG_ARNOLD_SRC:-/workspace/arnold}"' in text
    assert 'SYNC_BRANCH="${CLOUD_WATCHDOG_SYNC_BRANCH:-editible-install}"' in text
    assert 'SYNC_BRANCH="${CLOUD_WATCHDOG_SYNC_BRANCH:-${MEGAPLAN_REF' not in text
    assert "workflow-manifest-runtime" not in text


def test_watchdog_liveness_is_scoped_to_marked_chain_spec() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'local remote_spec="$3"' in text
    assert "ps -eww -o args=" in text
    assert 'grep -Fq -- "$remote_spec"' in text
    assert 'health="$(session_health_status "$session" "$workspace" "$remote_spec")"' in text


def test_watchdog_checks_plan_phase_health_even_when_session_alive() -> None:
    text = _wrapper("arnold-watchdog")

    assert "plan_phase_health_status()" in text
    assert 'phase_health="$(plan_phase_health_status "$workspace")"' in text
    assert 'latest_failure.get("kind") != "phase_failed"' in text
    assert "success_after_failure" in text
    assert 'f"recorded={recorded_at or' in text
    assert 'session alive but plan unhealthy' in text
    assert 'report_item "$report_items" "$session" "repair" "repair_running"' in text
    assert 'report_item "$report_items" "$session" "repair" "repair_completed"' in text


def test_watchdog_treats_supervisor_retry_before_process_liveness_as_unhealthy() -> None:
    text = _wrapper("arnold-watchdog")

    pane_check = "tmux capture-pane"
    retry_check = "retrying_failure"
    process_check = 'grep -E "[p]ython[0-9.]*([[:space:]]+-P)?[[:space:]]+-m arnold_pipelines.megaplan chain start"'

    assert text.index(pane_check) < text.index(process_check)
    assert text.index(retry_check) < text.index(process_check)
    assert '"error": "invalid_spec"' in text


def test_watchdog_relaunch_runs_editable_install_code_against_active_workspace() -> None:
    text = _wrapper("arnold-watchdog")

    assert "cd %q && PYTHONSAFEPATH=1 PYTHONPATH=%q:${PYTHONPATH:-}" in text
    assert "python3 -P -m arnold_pipelines.megaplan chain start" in text
    assert '"$SRC_DIR" "$remote_spec" "$workspace"' in text
    assert "--project-dir %q >> %q 2>&1" in text
    assert "--project-dir %q --one" not in text
    assert 'tmux kill-session -t "$session"' in text


def test_watchdog_syncs_extra_skills_to_agent_skill_dirs() -> None:
    text = _wrapper("arnold-watchdog")

    assert '"$HOME/.claude/skills"' in text
    assert '"$HOME/.codex/skills"' in text
    assert '"$HOME/.agents/skills"' in text
    assert '"$HOME/.hermes/skills"' in text


def test_kimi_goal_operator_runs_from_editable_install_checkout() -> None:
    text = _wrapper("arnold-kimi-goal-operator")

    assert 'ARNOLD_SRC="${KIMI_GOAL_ARNOLD_SRC:-/workspace/arnold}"' in text
    assert 'SYNC_BRANCH="${KIMI_GOAL_SYNC_BRANCH:-${CLOUD_WATCHDOG_SYNC_BRANCH:-editible-install}}"' in text
    assert 'RUN_CWD="$ARNOLD_SRC"' in text
    assert 'cd "$RUN_CWD"' in text
    assert "Do not let MEGAPLAN_REF or the active workflow workspace branch" in text
