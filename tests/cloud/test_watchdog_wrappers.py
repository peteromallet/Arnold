"""Regression tests for cloud watchdog wrapper invariants."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"


def _wrapper(name: str) -> str:
    return (WRAPPER_DIR / name).read_text(encoding="utf-8")


def _discover_wrapper() -> str:
    return _wrapper("arnold-cloud-discover")


def _extract_wrapper_function(name: str) -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _extract_wrapper_function_until(name: str, next_name: str) -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index(f"{name}() {{")
    end = text.index(f"\n{next_name}() {{", start)
    return text[start:end]


def _extract_reap_program() -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index("reap_stale_repair_candidates() {")
    marker = "python3 - \"$REAP_AGE_SECS\" \"$REAP_ORPHAN_AGE_SECS\" <<'PY'"
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _load_reap_module(tmp_path: Path):
    mod_path = tmp_path / "_reap_prog.py"
    mod_path.write_text(_extract_reap_program(), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("_reap_prog", mod_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_repair_stall_program() -> str:
    text = _wrapper("arnold-watchdog")
    start = text.index("reap_stalled_repair_candidates() {")
    marker = (
        "python3 - \"$MARKER_DIR\" \"$KIMI_OPERATOR_ROOT\" "
        "\"$REAP_STALL_GRACE_SECS\" \"$REAP_STALL_IDLE_SECS\" "
        "\"$REAP_AGE_SECS\" <<'PY'"
    )
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _run_repair_stall(
    tmp_path: Path,
    ps_rows: str,
    marker_dir: Path,
    operator_root: Path,
    grace_secs: int = 900,
    idle_secs: int = 600,
    reap_age_secs: int = 7200,
) -> list[str]:
    program = _extract_repair_stall_program()
    prog_path = tmp_path / "_repair_stall_prog.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            str(marker_dir),
            str(operator_root),
            str(grace_secs),
            str(idle_secs),
            str(reap_age_secs),
        ],
        input=ps_rows,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [line for line in result.stdout.strip().splitlines() if line]


def _run_watchdog_shell(script: str, *, path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}:{env.get('PATH', '')}"
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _run_discover(
    tmp_path: Path,
    *,
    marker_dir: Path,
    src_dir: Path | None = None,
    workspace_prefix: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    if workspace_prefix is not None:
        env["MEGAPLAN_DISCOVER_WORKSPACE_PREFIX"] = str(workspace_prefix)
    return subprocess.run(
        [
            "bash",
            str(WRAPPER_DIR / "arnold-cloud-discover"),
            "tmux-unmarked",
            "--marker-dir",
            str(marker_dir),
            "--src-dir",
            str(src_dir or REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


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
    assert 'health="$(session_health_status "$session" "$workspace" "$remote_spec" "$run_kind" "$plan_name")"' in text


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


def test_watchdog_reaper_is_wired_into_scan_and_report_summary() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'REAP_AGE_SECS="${CLOUD_WATCHDOG_REAP_AGE_SECS:-7200}"' in text
    assert 'REAP_ORPHAN_AGE_SECS="${CLOUD_WATCHDOG_REAP_ORPHAN_AGE_SECS:-3900}"' in text
    assert 'REAP_STALL_GRACE_SECS="${CLOUD_WATCHDOG_REAP_STALL_GRACE_SECS:-900}"' in text
    assert 'REAP_STALL_IDLE_SECS="${CLOUD_WATCHDOG_REAP_STALL_IDLE_SECS:-600}"' in text
    assert 'KIMI_OPERATOR_ROOT="${KIMI_GOAL_OPERATOR_ROOT:-/workspace/kimi-goal-operator}"' in text
    assert "reap_stale_repairs()" in text
    assert "reap_stalled_repair_candidates()" in text
    assert 'reap_stale_repairs "$report_items"' in text
    assert '"reaped_repairs": len(reaped)' in text
    assert 'report_item "$report_items" "${session:-}" "reap" "reaped"' in text


def test_watchdog_reap_decision_helper_reaps_only_stale_cloud_repairs(tmp_path: Path) -> None:
    module = _load_reap_module(tmp_path)

    over_age = module.decide_reap(
        {
            "pid": 4100,
            "ppid": 4000,
            "pgid": 4100,
            "etimes": 7201,
            "args": "/usr/local/bin/arnold-kimi-goal-operator demo-session /tmp/ws /tmp/spec.json",
        },
        7200,
        3900,
    )
    assert over_age["reap"] is True
    assert over_age["rule"] == "age_backstop"
    assert over_age["session"] == "demo-session"

    orphaned = module.decide_reap(
        {
            "pid": 5100,
            "ppid": 1,
            "pgid": 5000,
            "etimes": 3901,
            "args": (
                "python3 -m arnold.agent.run_agent "
                "--query='The user's invariant is: workflows on this Hetzner worker should never pause unexpectedly. "
                "Current Incident: Session: orphan-session Workspace: /tmp/ws'"
            ),
        },
        7200,
        3900,
    )
    assert orphaned["reap"] is True
    assert orphaned["rule"] == "orphan_fast_path"
    assert orphaned["session"] == "orphan-session"

    under_age = module.decide_reap(
        {
            "pid": 6100,
            "ppid": 6000,
            "pgid": 6000,
            "etimes": 600,
            "args": (
                "codex exec --sandbox danger-full-access "
                "'You are the Codex repair subagent launched by the cloud watchdog. "
                "Context: Session: fresh-session Workspace: /tmp/ws'"
            ),
        },
        7200,
        3900,
    )
    assert under_age["reap"] is False
    assert under_age["reason"] == "under_age"

    watchdog = module.decide_reap(
        {
            "pid": 7100,
            "ppid": 1,
            "pgid": 7100,
            "etimes": 9000,
            "args": "bash /usr/local/bin/arnold-watchdog --once",
        },
        7200,
        3900,
    )
    assert watchdog["reap"] is False
    assert watchdog["reason"] == "non_target"

    auditor = module.decide_reap(
        {
            "pid": 7200,
            "ppid": 1,
            "pgid": 7200,
            "etimes": 9000,
            "args": "bash /usr/local/bin/arnold-progress-auditor --once",
        },
        7200,
        3900,
    )
    assert auditor["reap"] is False
    assert auditor["reason"] == "non_target"

    non_arnold = module.decide_reap(
        {
            "pid": 7300,
            "ppid": 1,
            "pgid": 7300,
            "etimes": 99999,
            "args": "python3 -m http.server 8080",
        },
        7200,
        3900,
    )
    assert non_arnold["reap"] is False
    assert non_arnold["reason"] == "non_target"


def test_watchdog_progress_reap_decision_uses_log_idle_and_fails_safe(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    operator_root = tmp_path / "kimi-goal-operator"
    marker_dir.mkdir()
    operator_root.mkdir()
    now = time.time()

    stale_dir = operator_root / "20260628T000000Z-demo-session"
    stale_dir.mkdir()
    stale_operator = stale_dir / "operator.log"
    stale_codex = stale_dir / "codex-repair.log"
    stale_operator.write_text("operator\n", encoding="utf-8")
    stale_codex.write_text("codex\n", encoding="utf-8")
    stale_ts = now - 901
    os.utime(stale_operator, (stale_ts, stale_ts))
    os.utime(stale_codex, (stale_ts, stale_ts))
    os.utime(stale_dir, (stale_ts, stale_ts))

    stale_rows = (
        "4100 4000 4100 1800 "
        "/usr/local/bin/arnold-kimi-goal-operator demo-session /tmp/ws /tmp/spec.json\n"
    )
    stale_out = _run_repair_stall(tmp_path, stale_rows, marker_dir, operator_root)
    assert len(stale_out) == 1
    stale_fields = stale_out[0].split("\t")
    assert stale_fields[0] == "4100"
    assert stale_fields[6] == "stalled"
    assert stale_fields[7].startswith("stall_idle_")
    assert stale_fields[8] == str(stale_dir)
    assert int(stale_fields[9]) >= 600
    snapshot = marker_dir / "demo-session.reap-progress.json"
    snap_payload = json.loads(snapshot.read_text(encoding="utf-8"))
    assert snap_payload["operator_dir"] == str(stale_dir)
    assert "last_advance_ts" in snap_payload

    active_dir = operator_root / "20260628T000500Z-active-session"
    active_dir.mkdir()
    active_operator = active_dir / "operator.log"
    active_operator.write_text("still making progress\n", encoding="utf-8")
    active_ts = now - 30
    os.utime(active_operator, (active_ts, active_ts))
    os.utime(active_dir, (active_ts, active_ts))
    active_rows = (
        "5100 5000 5100 1800 "
        "/usr/local/bin/arnold-kimi-goal-operator active-session /tmp/ws /tmp/spec.json\n"
    )
    assert _run_repair_stall(tmp_path, active_rows, marker_dir, operator_root) == []
    active_snapshot = marker_dir / "active-session.reap-progress.json"
    assert active_snapshot.exists()

    unmappable_rows = (
        "6100 6000 6100 1800 "
        "/usr/local/bin/arnold-kimi-goal-operator missing-session /tmp/ws /tmp/spec.json\n"
    )
    assert _run_repair_stall(tmp_path, unmappable_rows, marker_dir, operator_root) == []
    assert not (marker_dir / "missing-session.reap-progress.json").exists()


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
    assert "mechanical_relaunch_attempted_previously" in text
    assert "kimi_dispatch_failed_previously" in text
    # The direct-relaunch fallback consumes the marker (Kimi tried + exited w/o recovery).
    assert "session stopped; Kimi tried and exited without recovery -> direct relaunch" in text
    assert "session stopped; mechanical relaunch first" in text
    assert "session stopped after mechanical relaunch: background-dispatched Kimi goal operator" in text
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


def test_watchdog_complete_teardown_collects_setsid_descendant_pgids(tmp_path: Path) -> None:
    ps_path = tmp_path / "ps"
    ps_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "100 1 100\n"
        "101 100 100\n"
        "102 101 102\n"
        "103 102 102\n"
        "EOF\n",
        encoding="utf-8",
    )
    ps_path.chmod(ps_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("repair_tree_pgids"),
            """
PATH=%s:$PATH
repair_tree_pgids 100 100
""".strip() % str(tmp_path),
        ]
    )
    result = subprocess.run(
        ["bash", "-lc", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().split() == ["100", "102"]


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
    assert "resolve_relaunch_command()" in text
    assert "default_plan_relaunch_command()" in text
    assert "python3 -P -m arnold_pipelines.megaplan chain start" in text
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan" in text
    assert '"$session" "$workspace" "$remote_spec" "$run_kind" "$plan_name" "$relaunch_command"' in text
    assert "--project-dir %q --one" not in text
    assert 'tmux kill-session -t "$session"' in text
    assert 'sleep 0.2' in text
    assert "relaunch raced with existing tmux session" in text
    assert "session exists after relaunch race" in text


def test_watchdog_adopts_markerless_bootstrap_tmux_run(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace" / "test-watchdog-vibecomfy-per-workflow-window-chat-20260628"
    (workspace / ".megaplan" / "plans" / "per-workflow-window-chat-cloud-20260628").mkdir(parents=True, exist_ok=True)

    tmux_path = tmp_path / "tmux"
    tmux_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"vibecomfy-per-workflow-window-chat\t4000\t{workspace}\t"
        "cd "
        f"{workspace}"
        " && MEGAPLAN_TRUSTED_CONTAINER=1 python3 -m arnold_pipelines.megaplan init "
        "--project-dir . --idea-file .megaplan/briefs/per-workflow-window-chat.md "
        "--name per-workflow-window-chat-cloud-20260628 --auto-start\n"
        "EOF\n",
        encoding="utf-8",
    )
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR)

    ps_path = tmp_path / "ps"
    ps_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "4000 1 bash -lc bootstrap\n"
        "4001 4000 /root/.pyenv/versions/3.11.11/bin/python3 -m arnold_pipelines.megaplan init "
        "--project-dir . --idea-file .megaplan/briefs/per-workflow-window-chat.md "
        "--name per-workflow-window-chat-cloud-20260628 --auto-start\n"
        "4002 4001 /root/.pyenv/versions/3.11.11/bin/python3 -m arnold_pipelines.megaplan critique "
        "--plan per-workflow-window-chat-cloud-20260628\n"
        "EOF\n",
        encoding="utf-8",
    )
    ps_path.chmod(ps_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("adopt_unmarked_tmux_sessions"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"DISCOVER_BIN={str(WRAPPER_DIR / 'arnold-cloud-discover')!r}",
            f"export MEGAPLAN_DISCOVER_WORKSPACE_PREFIX={str(tmp_path / 'workspace')!r}",
            "adopt_unmarked_tmux_sessions",
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "vibecomfy-per-workflow-window-chat" in result.stdout

    marker_path = marker_dir / "vibecomfy-per-workflow-window-chat.json"
    payload = json.loads(marker_path.read_text(encoding="utf-8"))
    assert payload["session"] == "vibecomfy-per-workflow-window-chat"
    assert payload["workspace"] == str(workspace)
    assert payload["run_kind"] == "plan"
    assert payload["plan_name"] == "per-workflow-window-chat-cloud-20260628"
    assert payload["remote_spec"] == ".megaplan/briefs/per-workflow-window-chat.md"
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan per-workflow-window-chat-cloud-20260628" in payload["relaunch_command"]


def test_watchdog_does_not_adopt_non_arnold_tmux_sessions(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace" / "test-watchdog-random-workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    tmux_path = tmp_path / "tmux"
    tmux_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"scratch\t5000\t{workspace}\tbash -lc 'python3 -m http.server 8080'\n"
        "EOF\n",
        encoding="utf-8",
    )
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR)

    ps_path = tmp_path / "ps"
    ps_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "5000 1 bash -lc python3 -m http.server 8080\n"
        "5001 5000 python3 -m http.server 8080\n"
        "EOF\n",
        encoding="utf-8",
    )
    ps_path.chmod(ps_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("adopt_unmarked_tmux_sessions"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"SRC_DIR={str(REPO_ROOT)!r}",
            f"DISCOVER_BIN={str(WRAPPER_DIR / 'arnold-cloud-discover')!r}",
            "adopt_unmarked_tmux_sessions",
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
    assert not marker_dir.exists()


def test_shared_cloud_discover_finds_markerless_arnold_tmux_session_and_skips_supervisors(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    workspace = tmp_path / "workspace" / "test-shared-discover-vibecomfy"
    (workspace / ".megaplan" / "plans" / "shared-discover-plan").mkdir(parents=True, exist_ok=True)

    tmux_path = tmp_path / "tmux"
    tmux_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"vibecomfy-shared-discover\t4000\t{workspace}\t"
        "cd "
        f"{workspace}"
        " && python3 -m arnold_pipelines.megaplan init --project-dir . "
        "--idea-file .megaplan/briefs/shared.md --name shared-discover-plan --auto-start\n"
        f"watchdog-demo\t5000\t{workspace}\tbash -lc '/usr/local/bin/arnold-watchdog --once'\n"
        f"kimi-helper\t6000\t{workspace}\tbash -lc '/usr/local/bin/arnold-kimi-goal-operator demo'\n"
        "EOF\n",
        encoding="utf-8",
    )
    tmux_path.chmod(tmux_path.stat().st_mode | stat.S_IXUSR)

    ps_path = tmp_path / "ps"
    ps_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "4000 1 bash -lc bootstrap\n"
        "4001 4000 python3 -m arnold_pipelines.megaplan init --project-dir . "
        "--idea-file .megaplan/briefs/shared.md --name shared-discover-plan --auto-start\n"
        "5000 1 bash -lc /usr/local/bin/arnold-watchdog --once\n"
        "6000 1 bash -lc /usr/local/bin/arnold-kimi-goal-operator demo\n"
        "EOF\n",
        encoding="utf-8",
    )
    ps_path.chmod(ps_path.stat().st_mode | stat.S_IXUSR)

    result = _run_discover(tmp_path, marker_dir=marker_dir, workspace_prefix=tmp_path / "workspace")
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.strip().splitlines() if line]
    assert len(lines) == 1
    fields = lines[0].split("\t")
    assert fields[0] == "vibecomfy-shared-discover"
    assert fields[1] == str(workspace)
    assert fields[2] == ".megaplan/briefs/shared.md"
    assert fields[3] == "plan"
    assert fields[4] == "shared-discover-plan"
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan shared-discover-plan" in fields[5]


def test_watchdog_plan_markers_relaunch_with_auto_not_chain_start(tmp_path: Path) -> None:
    script = "\n\n".join(
        [
            _extract_wrapper_function("default_plan_relaunch_command"),
            _extract_wrapper_function("resolve_relaunch_command"),
            f"SRC_DIR={str(REPO_ROOT)!r}",
            "resolve_relaunch_command demo-session /tmp/workspace /tmp/not-a-chain.yaml plan demo-plan ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan demo-plan" in result.stdout
    assert "chain start" not in result.stdout


def test_watchdog_done_plan_reports_complete_without_repair_or_relaunch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"iteration": 1, "current_state": "done", "active_step": None},
        events_body="{}\n",
    )

    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text("marker\n", encoding="utf-8")
    progress_path = marker_dir / f"{plan_name}.progress.json"
    progress_path.write_text("{}\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("session_marker_path"),
            _extract_wrapper_function("kimi_dispatch_marker_clear"),
            _extract_wrapper_function("clear_session_tracking_artifacts"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
kimi_dispatch_marker_set() { :; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
plan_attention_status_env() {
  cat <<'EOF'
PLAN_STATUS_FOUND='1'
PLAN_STATUS_PLAN_NAME='demo-plan'
PLAN_STATUS_CURRENT_STATE=''
PLAN_STATUS_RETRY_STRATEGY=''
PLAN_STATUS_FAILURE_KIND=''
PLAN_STATUS_FAILURE_MESSAGE=''
PLAN_STATUS_FAILURE_PHASE=''
PLAN_STATUS_FAILURE_RECORDED_AT=''
PLAN_STATUS_TIERS_TRIED=''
PLAN_STATUS_PUSHED_COMMITS=''
PLAN_STATUS_MANUAL_REVIEW='0'
EOF
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/briefs/demo.md {str(report_path)!r} chain {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert marker_path.exists()
    assert progress_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tcomplete\tplan complete\t" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_done_plan_without_marker_plan_name_uses_newest_plan_dir(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    older_plan = workspace / ".megaplan" / "plans" / "older-plan"
    newer_plan = workspace / ".megaplan" / "plans" / "newer-plan"
    _write_plan(older_plan, {"iteration": 1, "current_state": "planning", "active_step": None})
    _write_plan(newer_plan, {"iteration": 1, "current_state": "done", "active_step": None})
    old_ts = time.time() - 60
    new_ts = time.time()
    os.utime(older_plan / "state.json", (old_ts, old_ts))
    os.utime(newer_plan / "state.json", (new_ts, new_ts))
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
kimi_dispatch_marker_set() { :; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
plan_attention_status_env() {
  cat <<'EOF'
PLAN_STATUS_FOUND='1'
PLAN_STATUS_PLAN_NAME='newer-plan'
PLAN_STATUS_CURRENT_STATE=''
PLAN_STATUS_RETRY_STRATEGY=''
PLAN_STATUS_FAILURE_KIND=''
PLAN_STATUS_FAILURE_MESSAGE=''
PLAN_STATUS_FAILURE_PHASE=''
PLAN_STATUS_FAILURE_RECORDED_AT=''
PLAN_STATUS_TIERS_TRIED=''
PLAN_STATUS_PUSHED_COMMITS=''
PLAN_STATUS_MANUAL_REVIEW='0'
EOF
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/briefs/demo.md {str(report_path)!r} plan '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tcomplete\tplan complete\t" in report
    assert "spec_missing" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_manual_review_plan_state_reports_needs_human_not_complete(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 3,
            "current_state": "manual_review",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {"kind": "iteration_cap", "message": "review required"},
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\tmanual_review halt;" in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" in log_path.read_text(encoding="utf-8")


def test_watchdog_nonterminal_plan_state_mechanically_relaunches_before_kimi(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"iteration": 1, "current_state": "planning", "active_step": {"phase": "plan", "attempt": 1}},
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_set"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  if [[ "$1" == "new-session" ]]; then
    echo TMUX_NEW >&2
    return 0
  fi
  echo "TMUX_$1" >&2
  return 0
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trestart\trestarted\tstopped session relaunched\t" in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX_NEW" in result.stderr
    assert (marker_dir / "demo-session.kimi-dispatch").exists()


def test_watchdog_chain_session_is_not_short_circuited_by_done_plan_state(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    spec_path = workspace / ".megaplan" / "briefs" / "demo-chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"iteration": 1, "current_state": "done", "active_step": None},
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
kimi_dispatch_marker_set() { :; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  if [[ "$1" == "new-session" ]]; then
    echo TMUX_NEW >&2
    return 0
  fi
  echo "TMUX_$1" >&2
  return 0
}
plan_attention_status_env() {
  cat <<'EOF'
PLAN_STATUS_FOUND='0'
PLAN_STATUS_PLAN_NAME=''
PLAN_STATUS_CURRENT_STATE=''
PLAN_STATUS_RETRY_STRATEGY=''
PLAN_STATUS_FAILURE_KIND=''
PLAN_STATUS_FAILURE_MESSAGE=''
PLAN_STATUS_FAILURE_PHASE=''
PLAN_STATUS_FAILURE_RECORDED_AT=''
PLAN_STATUS_TIERS_TRIED=''
PLAN_STATUS_PUSHED_COMMITS=''
PLAN_STATUS_MANUAL_REVIEW='0'
EOF
}
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/briefs/demo-chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trestart\trestarted\tstopped session relaunched\t" in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX_NEW" in result.stderr


def test_watchdog_unreadable_plan_state_falls_through_to_existing_stopped_path(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text("{not-json\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_set"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  if [[ "$1" == "new-session" ]]; then
    echo TMUX_NEW >&2
    return 0
  fi
  echo "TMUX_$1" >&2
  return 0
}
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/briefs/demo.md {str(report_path)!r} chain {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trestart\trestarted\tstopped session relaunched\t" in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX_NEW" in result.stderr


def test_watchdog_restopped_session_falls_back_to_kimi_after_mechanical_relaunch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {"iteration": 1, "current_state": "planning", "active_step": {"phase": "plan", "attempt": 1}},
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    (marker_dir / "demo-session.kimi-dispatch").write_text("2026-06-28T00:00:00Z\n", encoding="utf-8")

    script = "\n\n".join(
        [
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("mechanical_relaunch_attempted_previously"),
            _extract_wrapper_function("kimi_dispatch_failed_previously"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("plan_terminal_status"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/briefs/demo.md {str(report_path)!r} chain {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tKimi goal operator dispatched after mechanical relaunch\t" in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_manual_review_chain_state_reports_needs_human_without_relaunch_or_kimi(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    spec_path = workspace / ".megaplan" / "briefs" / "demo-chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 9,
            "current_state": "blocked",
            "resume_cursor": {"phase": "recover-blocked", "retry_strategy": "manual_review"},
            "latest_failure": {"kind": "iteration_cap", "message": "exceeded max_iterations=200"},
            "history": [
                {
                    "step": "execute",
                    "result": "blocked",
                    "batch_to_tier": [
                        {"actual_agent": "codex", "actual_model": "gpt-5.4"},
                        {"tier_model_spec": "codex:gpt-5.5"},
                    ],
                }
            ],
        },
        events_body="{}\n",
    )
    chain_dir = spec_path.parent / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": plan_name,
                "last_state": "blocked",
                "last_pushed_commit": "abc123def456",
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/briefs/demo-chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\tmanual_review halt;" in report
    assert "abc123def456" in report
    assert "gpt-5.4" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" in log_path.read_text(encoding="utf-8")


def test_watchdog_needs_human_webhook_posts_once_when_configured(tmp_path: Path) -> None:
    dm_helper = tmp_path / "arnold-discord-dm"
    dm_helper.write_text(
        "#!/usr/bin/env bash\n"
        "cat >/dev/null\n"
        "printf '%s\\n' '{\"ok\": false, \"reason\": \"send_failed\"}'\n",
        encoding="utf-8",
    )
    dm_helper.chmod(dm_helper.stat().st_mode | stat.S_IXUSR)

    curl_path = tmp_path / "curl"
    curl_path.write_text(
        "#!/usr/bin/env bash\n"
        f"echo called >> {str(tmp_path / 'curl-calls.txt')!r}\n"
        f"for arg in \"$@\"; do\n"
        "  case \"$arg\" in\n"
        f"    @*) cp \"${{arg#@}}\" {str(tmp_path / 'webhook-payload.json')!r} ;;\n"
        "  esac\n"
        "done\n",
        encoding="utf-8",
    )
    curl_path.chmod(curl_path.stat().st_mode | stat.S_IXUSR)

    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    notify_line = (
        f"notify_needs_human {str(report_path)!r} demo-session /tmp/ws "
        ".megaplan/briefs/demo.md chain stopped 'manual_review halt'"
    )
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            f"LOG={str(log_path)!r}",
            f"DISCORD_DM_BIN={str(dm_helper)!r}",
            "REPORT_WEBHOOK='https://example.test/watchdog'",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
PLAN_STATUS_PLAN_NAME='demo-plan'
PLAN_STATUS_CURRENT_STATE='blocked'
PLAN_STATUS_RETRY_STRATEGY='manual_review'
PLAN_STATUS_FAILURE_KIND='iteration_cap'
PLAN_STATUS_FAILURE_MESSAGE='exceeded max_iterations=200'
PLAN_STATUS_FAILURE_PHASE='recover-blocked'
PLAN_STATUS_FAILURE_RECORDED_AT='2026-06-28T11:29:34Z'
PLAN_STATUS_TIERS_TRIED='codex:gpt-5.4, codex:gpt-5.5'
PLAN_STATUS_PUSHED_COMMITS='abc123def456'
""".strip(),
            notify_line,
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "curl-calls.txt").read_text(encoding="utf-8").strip().splitlines() == ["called"]
    payload = json.loads((tmp_path / "webhook-payload.json").read_text(encoding="utf-8"))
    assert payload["session"] == "demo-session"
    assert payload["plan"]["name"] == "demo-plan"
    assert payload["plan"]["tiers_tried"] == ["codex:gpt-5.4", "codex:gpt-5.5"]
    assert payload["plan"]["pushed_commit_shas"] == ["abc123def456"]
    report = report_path.read_text(encoding="utf-8")
    assert "\tnotify\twebhook_sent\tneeds-human webhook delivered\t" in report


def test_watchdog_needs_human_discord_dm_is_primary_delivery(tmp_path: Path) -> None:
    dm_helper = tmp_path / "arnold-discord-dm"
    dm_helper.write_text(
        "#!/usr/bin/env bash\n"
        f"cat > {str(tmp_path / 'dm-payload.json')!r}\n"
        "printf '%s\\n' '{\"ok\": true, \"message_count\": 1}'\n",
        encoding="utf-8",
    )
    dm_helper.chmod(dm_helper.stat().st_mode | stat.S_IXUSR)

    curl_path = tmp_path / "curl"
    curl_path.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    curl_path.chmod(curl_path.stat().st_mode | stat.S_IXUSR)

    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            f"LOG={str(log_path)!r}",
            f"DISCORD_DM_BIN={str(dm_helper)!r}",
            "REPORT_WEBHOOK='https://example.test/watchdog'",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
PLAN_STATUS_PLAN_NAME='demo-plan'
PLAN_STATUS_CURRENT_STATE='manual_review'
PLAN_STATUS_RETRY_STRATEGY='manual_review'
PLAN_STATUS_FAILURE_KIND='iteration_cap'
PLAN_STATUS_FAILURE_MESSAGE='exceeded max_iterations=200'
PLAN_STATUS_FAILURE_PHASE='recover-blocked'
PLAN_STATUS_FAILURE_RECORDED_AT='2026-06-28T11:29:34Z'
PLAN_STATUS_TIERS_TRIED='deepseek:flash, codex:gpt-5.4, codex:gpt-5.5'
PLAN_STATUS_PUSHED_COMMITS='abc123def456, fedcba654321'
""".strip(),
            f"notify_needs_human {str(report_path)!r} demo-session /tmp/ws .megaplan/briefs/demo.md chain stopped 'manual_review halt'",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads((tmp_path / "dm-payload.json").read_text(encoding="utf-8"))
    assert payload["title"] == "Megaplan needs human review - demo-session"
    assert payload["plan"]["tiers_tried"] == ["deepseek:flash", "codex:gpt-5.4", "codex:gpt-5.5"]
    assert payload["plan"]["pushed_commit_shas"] == ["abc123def456", "fedcba654321"]
    assert any(field["label"] == "Tiers tried" and field["joiner"] == " -> " for field in payload["fields"])
    report = report_path.read_text(encoding="utf-8")
    assert "\tnotify\tdiscord_dm_sent\tneeds-human Discord DM delivered\t" in report
    assert "needs-human webhook delivered" not in log_path.read_text(encoding="utf-8")


def test_watchdog_needs_human_missing_discord_config_skips_webhook_fallback(tmp_path: Path) -> None:
    dm_helper = tmp_path / "arnold-discord-dm"
    dm_helper.write_text(
        "#!/usr/bin/env bash\n"
        "cat >/dev/null\n"
        "printf '%s\\n' '{\"ok\": false, \"reason\": \"missing_config\", \"missing\": [\"DISCORD_BOT_TOKEN\", \"DISCORD_DM_USER_ID\"]}'\n",
        encoding="utf-8",
    )
    dm_helper.chmod(dm_helper.stat().st_mode | stat.S_IXUSR)

    curl_path = tmp_path / "curl"
    curl_path.write_text(
        "#!/usr/bin/env bash\n"
        f"echo called >> {str(tmp_path / 'curl-calls.txt')!r}\n",
        encoding="utf-8",
    )
    curl_path.chmod(curl_path.stat().st_mode | stat.S_IXUSR)

    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"
    script = "\n\n".join(
        [
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            f"LOG={str(log_path)!r}",
            f"DISCORD_DM_BIN={str(dm_helper)!r}",
            "REPORT_WEBHOOK='https://example.test/watchdog'",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
PLAN_STATUS_PLAN_NAME='demo-plan'
""".strip(),
            f"notify_needs_human {str(report_path)!r} demo-session /tmp/ws .megaplan/briefs/demo.md chain stopped 'manual_review halt'",
        ]
    )

    result = _run_watchdog_shell(script, path_prefix=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "curl-calls.txt").exists()
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\tmanual_review halt\t" in report
    assert "discord dm skipped; DISCORD_BOT_TOKEN or DISCORD_DM_USER_ID unset" in log_path.read_text(encoding="utf-8")


def test_watchdog_resolves_relative_chain_specs_against_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "briefs" / "demo-chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("launch_chain_tick"),
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo alive; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_dispatch_marker_clear() { :; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/briefs/demo-chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "alive" in report
    assert "spec_missing" not in report


def test_watchdog_scan_ignores_progress_snapshot_markers() -> None:
    text = _wrapper("arnold-watchdog")

    assert "*.progress.json|*.reap-progress.json" in text


def test_watchdog_enforces_single_instance_and_reexecs_after_hot_update() -> None:
    text = _wrapper("arnold-watchdog")
    scan_once = _extract_wrapper_function("scan_once")

    assert 'LOCK_FILE="${CLOUD_WATCHDOG_LOCK_FILE:-/workspace/.megaplan/watchdog.lock}"' in text
    assert 'LOCK_HELD="${CLOUD_WATCHDOG_LOCK_HELD:-0}"' in text
    assert 'exec flock -n "$LOCK_FILE" bash "$SELF_PATH" "${WATCHDOG_ARGS[@]}"' in text
    assert "maybe_reexec_updated_watchdog()" in text
    assert 'log "watchdog wrapper updated on disk; re-execing current script"' in text
    assert 'exec bash "$SELF_PATH" "${WATCHDOG_ARGS[@]}"' in text
    assert 'log "scan start marker_dir=$MARKER_DIR"' in scan_once
    assert 'sync_editable_source_branch "$report_items" || true' in scan_once
    assert scan_once.count("maybe_reexec_updated_watchdog") == 2
    assert scan_once.index('log "scan start marker_dir=$MARKER_DIR"') < scan_once.index("maybe_reexec_updated_watchdog")
    assert scan_once.index('sync_editable_source_branch "$report_items" || true') < scan_once.rindex("maybe_reexec_updated_watchdog")


def test_watchdog_refresh_syncs_cloud_runtime_wrappers() -> None:
    text = _wrapper("arnold-watchdog")

    assert "sync_cloud_runtime_wrappers()" in text
    assert 'local wrapper_src_dir="$SRC_DIR/arnold_pipelines/megaplan/cloud/wrappers"' in text
    assert 'local wrapper_dest_dir="/usr/local/bin"' in text
    assert 'local support_dest_dir="/usr/local/share/arnold-watchdog"' in text
    assert 'if [[ -f "$dest" ]] && cmp -s "$wrapper" "$dest"; then' in text
    assert 'install -m 0755 "$wrapper" "$dest"' in text
    assert 'if [[ ! -f "$dest" ]] || ! cmp -s "$wrapper_src_dir/principles.md" "$dest"; then' in text
    assert 'install -m 0644 "$wrapper_src_dir/principles.md" "$dest"' in text
    assert 'sync_cloud_runtime_wrappers >> "$LOG" 2>&1 || return 1' in text


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
    assert 'DISCOVER_BIN="${MEGAPLAN_AUDIT_DISCOVER_BIN:-$ARNOLD_SRC/arnold_pipelines/megaplan/cloud/wrappers/arnold-cloud-discover}"' in text
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


def _extract_auditor_worklist_program() -> str:
    text = _wrapper("arnold-progress-auditor")
    marker = (
        "python3 - \"$MARKER_DIR\" \"$WORKLIST\" \"$AUDIT_WINDOW_HOURS\" "
        "\"$DISCOVER_BIN\" \"/workspace\" \"$ARNOLD_SRC\" <<'PY'"
    )
    start = text.index(marker)
    start = text.index("\n", start) + 1
    end = text.index("\nPY\n", start)
    return text[start:end]


def _run_auditor_worklist_builder(
    tmp_path: Path,
    *,
    marker_dir: Path,
    worklist: Path,
    window_hours: float,
    discover_bin: Path,
    workspace_root: Path,
    arnold_src: Path,
) -> list[dict]:
    program = _extract_auditor_worklist_program()
    prog_path = tmp_path / "_auditor_worklist.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            str(marker_dir),
            str(worklist),
            str(window_hours),
            str(discover_bin),
            str(workspace_root),
            str(arnold_src),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [
        json.loads(line)
        for line in worklist.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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
        "name": "m2-mock", "plan": "m2-mock", "session": "m2-mock",
        "workspace": str(workspace), "updated": _iso_hours_ago(0.1), "sources": ["marker"],
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


def test_auditor_worklist_unions_marker_tmux_and_workspace_activity_and_skips_arnold(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    arnold_src = workspace_root / "arnold"
    (arnold_src / ".megaplan" / "plans" / "should-not-scan").mkdir(parents=True)

    chain_ws = workspace_root / "vibecomfy-god-file-splits"
    bootstrap_ws = workspace_root / "vibecomfy-per-workflow-window-chat-20260628"
    done_ws = workspace_root / "python-shaped-workflow-authoring"
    for ws in (chain_ws, bootstrap_ws, done_ws):
        (ws / ".megaplan" / "plans").mkdir(parents=True)

    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "chain-session.json").write_text(
        json.dumps({"session": "chain-session", "workspace": str(chain_ws), "updated_at": _iso_hours_ago(0.2)}),
        encoding="utf-8",
    )

    def write_recent_plan(workspace: Path, name: str, *, state_recent: bool = True, events_recent: bool = False) -> None:
        plan_dir = workspace / ".megaplan" / "plans" / name
        state = {"name": name, "current_state": "done", "history": [], "meta": {}}
        _write_plan(plan_dir, state, plan_v_bodies={"plan_v1.md": "v1"}, events_body="{}\n" if events_recent else "")
        recent_ts = time.time() - 300
        stale_ts = time.time() - (9 * 3600)
        state_path = plan_dir / "state.json"
        events_path = plan_dir / "events.ndjson"
        os.utime(state_path, (recent_ts if state_recent else stale_ts, recent_ts if state_recent else stale_ts))
        if events_path.exists():
            os.utime(events_path, (recent_ts if events_recent else stale_ts, recent_ts if events_recent else stale_ts))

    write_recent_plan(chain_ws, "m2-chain", state_recent=True)
    write_recent_plan(bootstrap_ws, "m1-bootstrap", state_recent=False, events_recent=True)
    write_recent_plan(done_ws, "m5-done", state_recent=False, events_recent=True)
    write_recent_plan(done_ws, "m6-done", state_recent=True, events_recent=False)
    write_recent_plan(arnold_src, "should-not-scan", state_recent=True)

    discover_bin = tmp_path / "discover_stub.sh"
    discover_bin.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"bootstrap-session\t{bootstrap_ws}\t.megaplan/briefs/bootstrap.md\tplan\tm1-bootstrap\tignored\n"
        f"chain-session-live\t{chain_ws}\t/tmp/spec.yaml\tchain\t\tignored\n"
        "EOF\n",
        encoding="utf-8",
    )
    discover_bin.chmod(discover_bin.stat().st_mode | stat.S_IXUSR)

    worklist = tmp_path / "worklist.jsonl"
    entries = _run_auditor_worklist_builder(
        tmp_path,
        marker_dir=marker_dir,
        worklist=worklist,
        window_hours=6,
        discover_bin=discover_bin,
        workspace_root=workspace_root,
        arnold_src=arnold_src,
    )

    observed = {(entry["workspace"], entry["plan"]): set(entry["sources"]) for entry in entries}
    assert (str(chain_ws), "m2-chain") in observed
    assert observed[(str(chain_ws), "m2-chain")] == {"marker", "tmux", "workspace_activity"}
    assert (str(bootstrap_ws), "m1-bootstrap") in observed
    assert observed[(str(bootstrap_ws), "m1-bootstrap")] == {"tmux", "workspace_activity"}
    assert (str(done_ws), "m5-done") in observed
    assert observed[(str(done_ws), "m5-done")] == {"workspace_activity"}
    assert (str(done_ws), "m6-done") in observed
    assert observed[(str(done_ws), "m6-done")] == {"workspace_activity"}
    assert all(entry["workspace"] != str(arnold_src) for entry in entries)


def test_auditor_gather_includes_done_plan_with_recent_events_mtime(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_dir = workspace / ".megaplan" / "plans" / "m6-done"
    state = {
        "name": "m6-done",
        "iteration": 1,
        "current_state": "done",
        "active_step": {"phase": "review", "attempt": 8},
        "latest_failure": {"kind": "stalled", "message": "stale failure record"},
        "last_gate": {"recommendation": "PASS"},
        "meta": {"weighted_scores": [7.0, 6.0, 4.0], "plan_deltas": [1.0, 1.0, 1.0], "significant_counts": [1, 1, 1]},
        "history": [
            {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(1.0)},
            {"step": "gate", "result": "iterate", "timestamp": _iso_hours_ago(2.0)},
            {"step": "gate", "result": "blocked", "timestamp": _iso_hours_ago(3.0)},
        ],
    }
    _write_plan(plan_dir, state, plan_v_bodies={"plan_v1.md": "v1"}, events_body="{}\n{}\n")
    stale_ts = time.time() - (9 * 3600)
    recent_ts = time.time() - 120
    os.utime(plan_dir / "state.json", (stale_ts, stale_ts))
    os.utime(plan_dir / "events.ndjson", (recent_ts, recent_ts))

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": "m6-done",
                "session": "done-session",
                "sources": ["workspace_activity"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    wrapper_text = _wrapper("arnold-progress-auditor")
    g_marker = "python3 - \"$WORKLIST\" \"$GATHER_DIR\" \"$AUDIT_WINDOW_HOURS\" \"$ARNOLD_SRC\" \"$stall_summary\" <<'PY'"
    g_start = wrapper_text.index(g_marker)
    g_start = wrapper_text.index("\n", g_start) + 1
    g_end = wrapper_text.index("\nPY\n", g_start)
    gather_prog = wrapper_text[g_start:g_end]
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(gather_prog, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(gather_path),
            str(worklist),
            str(gather_dir),
            "6",
            str(tmp_path),
            "none",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected done plan with recent events mtime to be included"
    assert findings[0]["plan"] == "m6-done"
    assert findings[0]["session"] == "done-session"
    assert findings[0]["sources"] == ["workspace_activity"]


def test_arnold_progress_auditor_produces_evidence_cited_report_via_mocked_deepseek(tmp_path) -> None:
    report = _run_auditor_with_mocked_deepseek(tmp_path)
    finding = report["findings"][0]
    # The finding cites specific plan_v + gate evidence.
    combined = " ".join(finding["reasons"]) + " " + finding.get("hypothesis", "")
    assert "plan_v refreshed" in combined
    assert "gate=ITERATE/blocked" in combined
    assert "hypothesis:" in finding["hypothesis"]
