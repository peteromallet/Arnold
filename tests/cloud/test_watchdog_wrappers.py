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


def test_watchdog_kimi_operator_dedupe_does_not_match_its_own_grep() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'pgrep -f "arnold-kimi-goal-operator[[:space:]]+$session[[:space:]]"' in text
    assert 'grep -F "[a]rnold-kimi-goal-operator $session "' not in text


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

    assert "if [[ -f /workspace/.cloud-hot-env ]]; then set -a; . /workspace/.cloud-hot-env; set +a; fi;" in text
    assert "cd %q && PYTHONSAFEPATH=1 PYTHONPATH=%q:${PYTHONPATH:-}" in text
    assert "python3 -P -m arnold_pipelines.megaplan chain start" in text
    assert '"$SRC_DIR" "$remote_spec" "$workspace"' in text
    assert "--project-dir %q >> %q 2>&1" in text
    assert "--project-dir %q --one" not in text
    assert 'tmux kill-session -t "$session"' in text
    assert 'sleep 0.2' in text
    assert "relaunch raced with existing tmux session" in text
    assert "session exists after relaunch race" in text


def test_arnold_chain_wrapper_reloads_hot_env_before_launch() -> None:
    text = _wrapper("arnold-chain")

    assert "if [[ -f /workspace/.cloud-hot-env ]]; then set -a; . /workspace/.cloud-hot-env; set +a; fi;" in text
    assert "python -P -m arnold_pipelines.megaplan chain start" in text


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
    assert 'PRINCIPLES_PATH="${KIMI_GOAL_PRINCIPLES_PATH:-/usr/local/share/arnold-watchdog/principles.md}"' in text
    assert 'MAX_TURNS="${KIMI_GOAL_MAX_TURNS:-120}"' in text
    assert 'CODEX_TIMEOUT="${KIMI_GOAL_CODEX_TIMEOUT_SECS:-1800}"' in text
    assert '--max_turns="$MAX_TURNS"' in text
    assert 'CODEX_PROMPT="$RUN_DIR/codex-repair-prompt.md"' in text
    assert 'CODEX_LOG="$RUN_DIR/codex-repair.log"' in text
    assert 'capture "subagent launcher skill"' in text
    assert 'RUN_CWD="$ARNOLD_SRC"' in text
    assert 'cd "$RUN_CWD"' in text
    assert "Do not let MEGAPLAN_REF or the active workflow workspace branch" in text
    assert "Your Codex brief should contain the core issue, evidence, constraints, and plausible hypotheses only" in text
    assert "do not prescribe the implementation" in text
    assert "First read the \\$subagent-launcher SKILL.md" in text
    assert "then dispatch Codex through that skill" in text
    assert "If \\$subagent-launcher or Codex cannot be launched" in text
    assert "launching Codex repair subagent" in text
    assert 'codex exec --sandbox danger-full-access "$(cat "$CODEX_PROMPT")" </dev/null' in text
    assert 'capture "codex repair subagent result"' in text
    assert "launching Kimi goal operator" in text
    assert text.index("launching Codex repair subagent") < text.index("launching Kimi goal operator")


def test_watchdog_repair_principles_are_general_and_loaded_into_kimi_prompt() -> None:
    wrapper = _wrapper("arnold-kimi-goal-operator")
    principles = _wrapper("principles.md")

    assert "$PRINCIPLES_TEXT" in wrapper
    assert "# Repair Principles" in wrapper
    assert "Codex phases must run through the Codex plan/CLI path" in principles
    assert "DeepSeek phases must run through the direct DeepSeek API credentials" in principles
    assert "read the launcher skill instructions" in principles
    assert "brief Codex through `$subagent-launcher`" in principles
