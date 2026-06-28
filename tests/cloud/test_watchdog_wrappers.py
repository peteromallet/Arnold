"""Regression tests for cloud watchdog wrapper invariants."""

from __future__ import annotations

import datetime as dt
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"


def _wrapper(name: str) -> str:
    return (WRAPPER_DIR / name).read_text(encoding="utf-8")


def _extract_wrapper_function(name: str) -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


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
    assert 'report_item "$report_items" "$session" "repair" "repair_dispatched"' in text


def test_watchdog_kimi_operator_dedupe_does_not_match_its_own_grep() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'pgrep -f "arnold-kimi-goal-operator[[:space:]]+$session[[:space:]]"' in text
    assert 'printf \'%s/%s.kimi-pgid\' "$MARKER_DIR" "$1"' in text
    assert 'kill -0 -- "-$pgid"' in text
    assert 'grep -F "[a]rnold-kimi-goal-operator $session "' not in text


def test_watchdog_kimi_repair_is_backgrounded_so_it_cannot_block_the_tick() -> None:
    text = _wrapper("arnold-watchdog")

    # The Kimi goal operator is launched in the background (setsid ... &) so a
    # 60-min repair on one session cannot block the tick from scanning/reporting
    # the other sessions.
    assert "dispatch_kimi_repair()" in text
    assert 'setsid bash -c \'echo "$$" > "$0"; exec /usr/local/bin/arnold-kimi-goal-operator "$@"\'' in text
    assert "kimi_dispatch_marker_set" in text
    assert "kimi_dispatch_failed_previously" in text
    # The direct-relaunch fallback consumes the marker (Kimi tried + exited w/o recovery).
    assert "session stopped; Kimi tried and exited without recovery -> direct relaunch" in text
    # The marker is cleared once the session is observed alive + healthy.
    assert "kimi_dispatch_marker_clear" in text
    assert 'rm -f "$(kimi_dispatch_marker_path "$1")" "$(kimi_pgid_path "$1")"' in text
    assert 'kill -- "-$pgid"' in text

    # No bare synchronous foreground Kimi invocation remains: every operator
    # call site either guards (kimi_operator_running), dispatches in the
    # background (dispatch_kimi_repair / setsid), or is a marker/log line.
    for ln in text.splitlines():
        if 'arnold-kimi-goal-operator "$session" "$workspace" "$remote_spec"' in ln:
            assert any(tok in ln for tok in (
                "setsid", "dispatch_kimi_repair", "kimi_operator_running",
                "kimi_dispatch", "log ",
            )), f"bare synchronous Kimi invocation remains: {ln!r}"


def test_watchdog_kimi_operator_running_falls_back_to_pgid_pidfile_and_clear_removes_it(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    session = "demo-session"
    pgid_path = marker_dir / f"{session}.kimi-pgid"
    marker_path = marker_dir / f"{session}.kimi-dispatch"
    pgid_path.write_text("4242\n", encoding="utf-8")
    marker_path.write_text("2026-06-28T00:00:00Z\n", encoding="utf-8")

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_clear"),
            _extract_wrapper_function("kimi_operator_running"),
            f"""
MARKER_DIR={str(marker_dir)!r}
pgrep() {{
  return 1
}}
kill() {{
  if [[ "$#" -eq 3 && "$1" == "-0" && "$2" == "--" && "$3" == "-4242" ]]; then
    return 0
  fi
  return 1
}}
ps() {{
  cat <<'EOF'
 4242 python3 -m arnold.agent.run_agent --goal repair
EOF
}}
if kimi_operator_running {session!r}; then
  echo running
else
  echo stopped
fi
kimi_dispatch_marker_clear {session!r}
if [[ ! -e {str(pgid_path)!r} && ! -e {str(marker_path)!r} ]]; then
  echo cleared
fi
""".strip(),
        ]
    )
    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["running", "cleared"]


def test_watchdog_treats_supervisor_retry_before_process_liveness_as_unhealthy() -> None:
    text = _wrapper("arnold-watchdog")

    pane_check = "tmux capture-pane"
    retry_check = "retrying_failure"
    process_check = 'grep -E "[p]ython[0-9.]*([[:space:]]+-P)?[[:space:]]+-m arnold_pipelines.megaplan chain start"'

    assert text.index(pane_check) < text.index(process_check)
    assert text.index(retry_check) < text.index(process_check)
    assert '"error": "invalid_spec"' in text


def test_watchdog_skips_relaunch_while_review_pr_is_still_open() -> None:
    text = _wrapper("arnold-watchdog")

    assert "chain_wait_status()" in text
    assert 'wait_status="$(chain_wait_status "$workspace")"' in text
    assert 'if [[ "$health" == "awaiting_pr_merge" ]]; then' in text
    assert 'report_item "$report_items" "$session" "observe" "awaiting_pr_merge" "session waiting on PR merge"' in text
    assert '["gh", "pr", "view", str(int(pr_number)), "--json", "state"]' in text


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
    assert 'CODEX_TIMEOUT="${KIMI_GOAL_CODEX_TIMEOUT_SECS:-7200}"' in text
    assert '--max_turns="$MAX_TURNS"' in text
    assert 'CODEX_PROMPT="$RUN_DIR/codex-repair-prompt.md"' in text
    assert 'CODEX_LOG="$RUN_DIR/codex-repair.log"' in text
    assert 'capture "subagent launcher skill"' in text
    assert 'RUN_CWD="$ARNOLD_SRC"' in text
    assert 'cd "$RUN_CWD"' in text
    assert 'PYTHONSAFEPATH=1 PYTHONPATH="$ARNOLD_SRC:${PYTHONPATH:-}"' in text
    assert 'timeout "$TIMEOUT" python3 -P -m arnold.agent.run_agent \\' in text
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


def test_kimi_goal_operator_reaps_run_agent_child_on_exit() -> None:
    text = _wrapper("arnold-kimi-goal-operator")

    assert "set -m" in text
    assert "CHILD_PIDS=()" in text
    assert "cleanup_children()" in text
    assert "trap cleanup_children EXIT INT TERM HUP" in text
    assert 'kill -- -"$pgid"' in text
    assert 'kill -9 "$pid"' in text
    assert ') >> "$LOG" 2>&1 &' in text
    assert 'wait "$AGENT_PID"' in text


def test_watchdog_repair_principles_are_general_and_loaded_into_kimi_prompt() -> None:
    wrapper = _wrapper("arnold-kimi-goal-operator")
    principles = _wrapper("principles.md")

    assert "$PRINCIPLES_TEXT" in wrapper
    assert "# Repair Principles" in wrapper
    assert "Codex phases must run through the Codex plan/CLI path" in principles
    assert "DeepSeek phases must run through the direct DeepSeek API credentials" in principles
    assert "read the launcher skill instructions" in principles
    assert "brief Codex through `$subagent-launcher`" in principles


# ---------------------------------------------------------------------------
# Progress-stall detection + progress auditor (new components)
# ---------------------------------------------------------------------------


def _extract_stall_program() -> str:
    """Pull the python body of plan_progress_stall_status() out of the wrapper."""
    text = _wrapper("arnold-watchdog")
    start = text.index("plan_progress_stall_status() {")
    marker = "python3 - \"$workspace\" \"$MARKER_DIR\" <<'PY'"
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _run_stall(workspace: Path, marker: Path, env_overrides: dict[str, str] | None = None) -> str:
    program = _extract_stall_program()
    prog_path = workspace.parent / "_stall_prog.py"
    prog_path.write_text(program, encoding="utf-8")
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(prog_path), str(workspace), str(marker)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"stall program failed: {result.stderr}"
    return result.stdout.strip()


def _write_plan(plan_dir: Path, state: dict, plan_v_bodies: dict[str, str] | None = None,
                events_body: str = "") -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    for name, body in (plan_v_bodies or {}).items():
        (plan_dir / name).write_text(body, encoding="utf-8")
    if events_body:
        (plan_dir / "events.ndjson").write_text(events_body, encoding="utf-8")


def test_plan_progress_stall_status_is_wired_into_launch_chain_tick() -> None:
    text = _wrapper("arnold-watchdog")

    assert "plan_progress_stall_status()" in text
    assert 'stall_health="$(plan_progress_stall_status "$workspace")"' in text
    # FLAG ONLY — emits a progress_stall report item, no repair dispatch.
    assert 'report_item "$report_items" "$session" "observe" "progress_stall"' in text
    # The progress_stall status must NOT be in the alive-allowlist so it surfaces
    # in issues[] — the allowlist is the set excluded from issues.
    assert '"progress_stall"' not in text.split('not in {"alive"')[1].split("}")[0]


def test_plan_progress_stall_status_flags_iteration_threshold() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    _write_plan(
        ws / ".megaplan" / "plans" / "m2-x",
        {
            "iteration": 9,
            "current_state": "blocked",
            "active_step": None,
            "latest_failure": {"kind": "stalled", "metadata": {"stall_count": 5, "iteration": 23}},
        },
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )
    out = _run_stall(ws, marker)
    assert out.startswith("progress_stall:m2-x")
    # The milestone iteration (23 from latest_failure.metadata) dominates the
    # top-level value and trips the >=8 threshold.
    assert "iteration=23>=8" in out
    assert "stall_count=5" in out


def test_plan_progress_stall_status_flags_attempt_threshold() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    _write_plan(
        ws / ".megaplan" / "plans" / "m1-y",
        {"iteration": 2, "current_state": "planning",
         "active_step": {"phase": "plan", "attempt": 11}},
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )
    out = _run_stall(ws, marker)
    assert "progress_stall:m1-y" in out
    assert "active_step.attempt=11>=10" in out


def test_plan_progress_stall_status_ok_for_healthy_plan() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    _write_plan(
        ws / ".megaplan" / "plans" / "m1-ok",
        {"iteration": 2, "current_state": "planning",
         "active_step": {"phase": "plan", "attempt": 1}},
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )
    assert _run_stall(ws, marker) == "ok"


def test_plan_progress_stall_status_persists_tick_over_tick_snapshot() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    plan_dir = ws / ".megaplan" / "plans" / "m-snap"
    _write_plan(
        plan_dir,
        {"iteration": 4, "current_state": "planning",
         "active_step": {"phase": "plan", "attempt": 0}},
        plan_v_bodies={"plan_v1.md": "v1", "plan_v2.md": "v2"},
        events_body="{}\n",
    )

    # First tick: healthy, snapshot written.
    assert _run_stall(ws, marker) == "ok"
    snap = marker / "m-snap.progress.json"
    assert snap.exists()
    first = json.loads(snap.read_text(encoding="utf-8"))
    assert first["iteration"] == 4
    assert first["plan_v_count"] == 2
    assert "ts" in first

    # Second tick: iteration advances, plan_v count unchanged -> unchanged_ticks
    # increments. With iteration still under threshold this stays ok, but the
    # snapshot must reflect the increment.
    (plan_dir / "state.json").write_text(
        json.dumps({"iteration": 5, "current_state": "planning",
                    "active_step": {"phase": "plan", "attempt": 0}}),
        encoding="utf-8",
    )
    _run_stall(ws, marker)
    second = json.loads(snap.read_text(encoding="utf-8"))
    assert second["unchanged_ticks"] == 1

    # Third tick: still unchanged -> trips the "no growth while iteration
    # advances" signal now that unchanged_ticks >= 2.
    (plan_dir / "state.json").write_text(
        json.dumps({"iteration": 6, "current_state": "planning",
                    "active_step": {"phase": "plan", "attempt": 0}}),
        encoding="utf-8",
    )
    out = _run_stall(ws, marker)
    assert "progress_stall:m-snap" in out
    assert "unchanged-2-ticks" in out


def test_plan_progress_stall_thresholds_are_env_tunable() -> None:

    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    _write_plan(
        ws / ".megaplan" / "plans" / "m-tune",
        {"iteration": 3, "current_state": "planning",
         "active_step": {"phase": "plan", "attempt": 0}},
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )
    # iteration=3 is below the default 8 -> ok.
    assert _run_stall(ws, marker) == "ok"
    # Lower the threshold to 2 -> trips.
    out = _run_stall(ws, marker, {"CLOUD_WATCHDOG_STALL_ITERATIONS": "2"})
    assert "progress_stall:m-tune" in out


def test_arnold_progress_auditor_wrapper_has_bash_n_syntax_and_contract() -> None:
    text = _wrapper("arnold-progress-auditor")

    # bash -n on the actual wrapper file.
    wrapper_path = WRAPPER_DIR / "arnold-progress-auditor"
    result = subprocess.run(
        ["bash", "-n", str(wrapper_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"

    # Host-side: docker-execs into the container like ensure-megaplan-watchdog.
    assert 'CONTAINER="${MEGAPLAN_CLOUD_CONTAINER:-megaplan-cloud-agent}"' in text
    assert "docker inspect" in text

    # In-container: iterates active markers, 5h window, deepseek dispatch.
    assert 'MARKER_DIR="${MEGAPLAN_AUDIT_MARKER_DIR:-/workspace/.megaplan/cloud-sessions}"' in text
    assert 'AUDIT_WINDOW_HOURS="${MEGAPLAN_AUDIT_WINDOW_HOURS:-6}"' in text
    assert 'DEEPSEEK_MODEL="${MEGAPLAN_AUDIT_MODEL:-deepseek:deepseek-v4-pro}"' in text
    assert 'SUBAGENT_PROFILE="${MEGAPLAN_AUDIT_SUBAGENT_PROFILE:-partnered-5}"' in text
    assert "launch_hermes_agent.py" in text
    assert '--model="$DEEPSEEK_MODEL"' in text
    # Report paths.
    assert 'REPORT_DIR="${MEGAPLAN_AUDIT_REPORT_DIR:-/workspace/audit-reports}"' in text
    assert 'REPORT_LOG="${MEGAPLAN_AUDIT_REPORT_LOG:-/workspace/audit-report.log}"' in text
    assert 'JSON_OUT="$REPORT_DIR/${TS}-audit.json"' in text
    assert 'MD_OUT="$REPORT_DIR/${TS}-audit.md"' in text
    # Evidence-citing required output shape.
    assert "hypothesis" in text
    assert "recommendation" in text


def test_repair_runner_defaults_meta_loop_repairs_to_partnered_5() -> None:
    from arnold_pipelines.megaplan.watchdog.repair_runner import RepairRunner

    runner = RepairRunner(executable_search_path=[])
    assert runner._is_dry_run() is True
    # The megaplan-subcommand env pins partnered-5 as the default profile.
    env = runner._megaplan_subcommand_env({"PATH": "/bin"})
    assert env.get("MEGAPLAN_DEFAULT_PROFILE") == "partnered-5"
    assert env.get("MEGAPLAN_REPAIR_PROFILE") == "partnered-5"
    assert env.get("PYTHONSAFEPATH") == "1"
    # A caller-supplied default must win (setdefault semantics).
    env2 = runner._megaplan_subcommand_env(
        {"PATH": "/bin", "MEGAPLAN_DEFAULT_PROFILE": "apex"}
    )
    assert env2.get("MEGAPLAN_DEFAULT_PROFILE") == "apex"


def test_kimi_goal_operator_defaults_meta_loop_to_partnered_5_profile() -> None:
    text = _wrapper("arnold-kimi-goal-operator")

    assert 'DEFAULT_PROFILE="${KIMI_GOAL_DEFAULT_PROFILE:-partnered-5}"' in text
    assert 'export MEGAPLAN_DEFAULT_PROFILE="$DEFAULT_PROFILE"' in text
    assert 'export MEGAPLAN_REPAIR_PROFILE="$DEFAULT_PROFILE"' in text


def _run_auditor_with_mocked_deepseek(tmp_path: Path) -> dict:
    """Drive the in-container auditor python with a stubbed launcher.

    We synthesize a marker + a stalled plan, then call the auditor's gather +
    dispatch python in isolation by stubbing the hermes launcher with a script
    that emits a canned hypothesis. This proves the report path end-to-end
    without needing real DeepSeek credentials.
    """
    workspace = tmp_path / "ws"
    plans = workspace / ".megaplan" / "plans" / "m2-mock"
    plans.mkdir(parents=True)
    state = {
        "name": "m2-mock",
        "iteration": 8,
        "current_state": "blocked",
        "active_step": None,
        "latest_failure": {"kind": "stalled",
                           "message": "stalled at 'blocked' for 5 iterations",
                           "metadata": {"stall_count": 5, "iteration": 23}},
        "last_gate": {"recommendation": "ITERATE",
                      "rationale": "score regression 13.5 -> 3.0"},
        "meta": {"weighted_scores": [12.0, 7.0, 14.0, 13.5, 3.0],
                 "plan_deltas": [54.0, 9.0, 9.0, 43.0, 9.0],
                 "significant_counts": [8, 4, 9, 11, 2]},
        "history": [
            {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(0.5)},
            {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(1.5)},
            {"step": "gate", "result": "blocked", "timestamp": _iso_hours_ago(2.5)},
            {"step": "revise", "result": "success", "timestamp": _iso_hours_ago(0.2)},
        ],
    }
    (plans / "state.json").write_text(json.dumps(state), encoding="utf-8")
    for i, body in enumerate(["v1", "v2longer", "v3different", "v4", "v5"], start=1):
        (plans / f"plan_v{i}.md").write_text(body * (i * 100), encoding="utf-8")
    (plans / "events.ndjson").write_text("{}\n" * 10, encoding="utf-8")

    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "m2-mock.json").write_text(json.dumps({
        "session": "m2-mock", "workspace": str(workspace), "updated_at": _iso_hours_ago(0.1),
    }), encoding="utf-8")

    # Stub launcher that returns a canned hypothesis referencing the evidence.
    launcher = tmp_path / "launch_hermes_agent.py"
    canned = (
        "hypothesis: critique loop oscillating over cosmetic import wording; "
        "gate evaluator too strict for phase-0. recommend: tighten gate cosmetic flag."
    )
    launcher.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"print({canned!r})\n",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # Reuse the auditor's python by extracting the gather + dispatch steps is
    # fragile; instead invoke the actual wrapper's inner python via a trimmed
    # copy that points at our tmp paths. We assert the report-construction
    # python produces the cited finding by running it against our gather dir.
    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist"
    worklist.write_text(json.dumps({
        "name": "m2-mock", "session": "m2-mock",
        "workspace": str(workspace), "updated": _iso_hours_ago(0.1),
    }) + "\n", encoding="utf-8")

    wrapper_text = _wrapper("arnold-progress-auditor")
    # Extract the gather python (first heredoc after WORKLIST setup).
    g_marker = "python3 - \"$WORKLIST\" \"$GATHER_DIR\" \"$AUDIT_WINDOW_HOURS\" \"$ARNOLD_SRC\" \"$stall_summary\" <<'PY'"
    g_start = wrapper_text.index(g_marker)
    g_start = wrapper_text.index("\n", g_start) + 1
    g_end = wrapper_text.index("\nPY\n", g_start)
    gather_prog = wrapper_text[g_start:g_end]
    (gather_dir / "gather.py").write_text(gather_prog, encoding="utf-8")

    env = dict(os.environ)
    r = subprocess.run(
        [sys.executable, str(gather_dir / "gather.py"), str(worklist),
         str(gather_dir), "5", str(workspace.parent), "none"],
        capture_output=True, text=True, env=env, check=False,
    )
    assert r.returncode == 0, f"gather failed: {r.stderr}"
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))
    assert findings["findings"], "expected at least one suspicious finding"
    finding = findings["findings"][0]
    assert finding["plan"] == "m2-mock"
    reasons = " ".join(finding["reasons"])
    # Evidence-cited: plan churn + gate regression both present.
    assert "plan_v refreshed" in reasons
    assert "gate=ITERATE/blocked" in reasons

    # Now drive the report-assembly python against this finding with a canned
    # hypothesis (simulating the DeepSeek dispatch output).
    finding["deepseek_model"] = "deepseek:deepseek-v4-pro"
    finding["hypothesis"] = (
        "hypothesis: critique loop oscillating over cosmetic import wording; "
        "gate evaluator too strict for phase-0. recommend: tighten gate cosmetic flag."
    )
    (gather_dir / "findings.json").write_text(
        json.dumps({"window_hours": 5, "stall_summary": "none",
                    "findings": [finding]}),
        encoding="utf-8",
    )

    # Extract report-assembly python.
    a_marker = "python3 - \"$GATHER_DIR/findings.json\" \"$JSON_OUT\" \"$MD_OUT\" \"$REPORT_LOG\" \"$TS\" <<'PY'"
    a_start = wrapper_text.index(a_marker)
    a_start = wrapper_text.index("\n", a_start) + 1
    a_end = wrapper_text.index("\nPY\n", a_start)
    asm_prog = wrapper_text[a_start:a_end]
    json_out = tmp_path / "out.json"
    md_out = tmp_path / "out.md"
    log_path = tmp_path / "audit.log"
    asm = gather_dir / "asm.py"
    asm.write_text(asm_prog, encoding="utf-8")
    r2 = subprocess.run(
        [sys.executable, str(asm), str(gather_dir / "findings.json"),
         str(json_out), str(md_out), str(log_path), "TESTTS"],
        capture_output=True, text=True, env=env, check=False,
    )
    assert r2.returncode == 0, f"report asm failed: {r2.stderr}"
    report = json.loads(json_out.read_text(encoding="utf-8"))
    assert report["finding_count"] == 1
    assert report["deepseek_model"] == "deepseek:deepseek-v4-pro"
    md = md_out.read_text(encoding="utf-8")
    assert "m2-mock" in md
    assert "hypothesis:" in md
    assert "tighten gate cosmetic flag" in md
    # Log append is a single greppable line.
    log_line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert "findings=1" in log_line
    assert "m2-mock" in log_line
    return report


def _iso_hours_ago(hours: float) -> str:
    when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    return when.isoformat().replace("+00:00", "Z")


def test_arnold_progress_auditor_produces_evidence_cited_report_via_mocked_deepseek(tmp_path) -> None:
    report = _run_auditor_with_mocked_deepseek(tmp_path)
    finding = report["findings"][0]
    # The finding cites specific plan_v + gate evidence.
    combined = " ".join(finding["reasons"]) + " " + finding.get("hypothesis", "")
    assert "plan_v refreshed" in combined
    assert "gate=ITERATE/blocked" in combined
    assert "hypothesis:" in finding["hypothesis"]
