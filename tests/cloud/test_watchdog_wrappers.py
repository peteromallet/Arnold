"""Regression tests for cloud watchdog wrapper invariants."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import shlex
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


def _repair_wrapper() -> str:
    return _wrapper("arnold-repair-loop")


def _extract_repair_function(name: str) -> str:
    text = _repair_wrapper()
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


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
    marker = None
    for candidate in (
        "python3 - \"$MARKER_DIR\" \"$REPAIR_OPERATOR_ROOT\" "
        "\"$REAP_STALL_GRACE_SECS\" \"$REAP_STALL_IDLE_SECS\" "
        "\"$REAP_AGE_SECS\" <<'PY'",
        "python3 - \"$MARKER_DIR\" \"$KIMI_OPERATOR_ROOT\" "
        "\"$REAP_STALL_GRACE_SECS\" \"$REAP_STALL_IDLE_SECS\" "
        "\"$REAP_AGE_SECS\" <<'PY'",
    ):
        if candidate in text[start:]:
            marker = candidate
            break
    assert marker is not None
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _extract_repair_program(function_name: str, marker: str) -> str:
    text = _repair_wrapper()
    start = text.index(f"{function_name}() {{")
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


def _run_embedded_python(program: str, *args: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        prog_path = Path(tmpdir) / "_embedded.py"
        prog_path.write_text(program, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(prog_path), *args],
            capture_output=True,
            text=True,
            check=False,
        )


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
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    env.setdefault("MEGAPLAN_DISCOVER_WORKSPACE_ROOT", str(tmp_path / "workspace-root"))
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


def test_watchdog_flags_setup_deviations_instead_of_skipping() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'report_item "$report_items" "$session" "flag" "workspace_missing" "workspace missing"' in text
    assert 'report_item "$report_items" "$session" "flag" "spec_missing" "chain spec missing"' in text
    assert 'report_item "$report_items" "" "flag" "setup_invalid" "missing session: $marker"' in text
    assert 'report_item "$report_items" "$session" "flag" "setup_invalid" "missing remote_spec: $marker"' in text
    assert '"spec_missing" "chain spec missing"' in text
    assert '"skip" "spec_missing"' not in text
    assert '"skip" "workspace_missing"' not in text


def test_repair_loop_prompts_start_from_inline_incident_snapshot() -> None:
    text = _repair_wrapper()

    assert "## Incident Snapshot" in text
    assert "## RECURRENCE EVIDENCE" in text
    assert "Recurrence means the prior attempts may have treated symptoms, not the cause." in text
    assert "Start from the inline incident snapshot above." in text
    assert "ATTEMPT to resolve those user actions before treating this as a human stop" in text
    assert "Classification guide:" in text
    assert "LAST EXECUTE ATTEMPT" in text
    assert "The root cause might be in the Arnold SOURCE" in text
    assert "OR in the PLAN STATE" in text
    assert "deferred or blocked rather than failed" in text
    assert "LIVE FAILURE: The latest_failure is recent" in text
    assert "STALE STATE: The latest_failure predates a successful run" in text
    assert "## STATE MISMATCH DETECTED + CLEARED" in text
    assert "state mismatch detected + cleared" in text
    assert "repair_clear_stale_state_if_needed()" in text
    assert 'if [[ "$INITIAL_HEALTH" == "alive" ]]' in text
    assert "repair target already running; no dev-fix needed" in text
    assert "MEGAPLAN_ACTOR_ID=repair-loop-dev-fix" in text
    assert "Use the raw failure signal, run narrative, and prior-attempt history" in text
    assert "Do not hardcode a workflow-specific workaround when a general engine fix is appropriate." in text
    assert "This is a recurring problem. Do NOT pick the likely fix." in text
    assert "Trace the actual mechanism end-to-end" in text


def test_repair_loop_collects_failure_signal_narrative_and_event_tail(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "iteration": 21,
                "latest_failure": {
                    "kind": "phase_failed",
                    "message": "phase 'execute' internal_error",
                    "phase": "execute",
                    "recorded_at": "2026-06-28T19:30:34Z",
                    "metadata": {
                        "exit_code": 2,
                        "stderr": "__main__.py: error: unrecognized arguments: --confirm-destructive",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text(
        "\n".join(
            [
                json.dumps({"kind": "phase_started", "phase": "execute", "payload": {"msg": "launch execute"}}),
                json.dumps({"kind": "phase_failed", "phase": "execute", "payload": {"reason": "cli rejected flags"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "user_actions": [
                    {
                        "id": "ua-01-decide-cleanup",
                        "phase": "before_execute",
                        "blocks_task_ids": ["T1"],
                        "rationale": "Maintainer decision affects cleanup.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "user_actions.md").write_text(
        "# User Actions\n\n- **ua-01-decide-cleanup**: Decide cleanup scope.\n",
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "last_state": "awaiting_human",
                "events": [{"msg": "milestone demo starting"}, {"msg": "resuming existing plan demo-plan"}],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo.log").write_text(
        "\n".join(
            [
                "[chain] milestone demo starting",
                "[chain] resuming existing plan demo-plan",
                "[auto demo-plan] phase 'execute' exited with internal_error",
                "__main__.py: error: unrecognized arguments: --confirm-destructive",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "cli_or_argument_error"
    assert any("unrecognized arguments" in item for item in payload["raw_failure_signals"])
    assert "phase 'execute' exited with internal_error" in payload["chain_log_tail"]
    assert "execute:phase_failed | reason=cli rejected flags" in payload["plan_events_tail"]
    assert payload["plan_latest_failure"]["state_path"].endswith("/demo-plan/state.json")
    user_action_context = payload["user_action_context"]
    assert user_action_context["user_actions_path"].endswith("/demo-plan/user_actions.md")
    assert user_action_context["unresolved_user_actions"][0]["id"] == "ua-01-decide-cleanup"
    assert user_action_context["unresolved_user_actions"][0]["blocks_task_ids"] == ["T1"]


def test_repair_loop_collects_execute_attempt_artifacts_and_renders_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    history = [
        {
            "step": "execute",
            "result": "blocked",
            "timestamp": f"2026-06-29T02:0{i}:00Z",
            "output_file": "execution_batch_2.json",
        }
        for i in range(8)
    ]
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "iteration": 21,
                "latest_failure": {
                    "kind": "phase_failed",
                    "message": "phase 'execute' internal_error",
                    "phase": "execute",
                    "recorded_at": "2026-06-29T01:00:00Z",
                    "metadata": {"stderr": "old internal_error"},
                },
                "history": history,
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text(
        json.dumps({"kind": "phase_end", "phase": "execute", "payload": {"status": "blocked"}}) + "\n",
        encoding="utf-8",
    )
    (plan_dir / "execute_batch_2_output.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {"task_id": "m7-01", "status": "completed", "executor_notes": "done"},
                    {"task_id": "m7-13-full-suite-final-gate", "status": "pending", "executor_notes": ""},
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "execution_batch_2.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {"task_id": "m7-01", "status": "completed", "executor_notes": "done"},
                    {
                        "task_id": "m7-13-full-suite-final-gate",
                        "status": "blocked",
                        "executor_notes": "Deferred by harness until baseline is available.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "baseline_test_failures": None,
                "baseline_test_note": "runner error exit code 2",
                "baseline_test_collection_errors": ["tests/test_import_bad.py"],
                "tasks": [
                    {"id": "m7-01", "status": "completed", "executor_notes": "done"},
                    {
                        "id": "m7-13-full-suite-final-gate",
                        "status": "skipped",
                        "reviewer_verdict": "deferred_baseline_unavailable",
                        "executor_notes": (
                            "Collection failed with 43 errors - stale test imports "
                            "of deleted arnold.pipeline.*"
                        ),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "full_suite_backstop.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "baseline_failing_count": 0,
                "current_failing_count": 43,
                "failing_tests": ["tests/test_import_bad.py"],
                "collection_errors": ["tests/test_import_bad.py"],
            }
        ),
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "blocked"}),
        encoding="utf-8",
    )

    collect_program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(collect_program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    execute_context = payload["execute_attempt_context"]
    assert execute_context["execute_batch_output"]["path"].endswith("execute_batch_2_output.json")
    assert execute_context["execution_batch"]["status_counts"]["blocked"] == 1
    assert execute_context["finalize"]["baseline_test_failures"] is None
    assert execute_context["plan_history"]["consecutive_execute_blocked"] == 8

    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps({"initial_facts": {}, "iterations": [payload]}),
        encoding="utf-8",
    )
    summary_program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    summary_result = _run_embedded_python(summary_program, str(data_path))

    assert summary_result.returncode == 0, summary_result.stderr
    summary = summary_result.stdout
    assert summary.startswith("## LAST EXECUTE ATTEMPT")
    assert "Blocked/deferred task: m7-13-full-suite-final-gate" in summary
    assert "deferred_baseline_unavailable" in summary
    assert "baseline_test_failures is null" in summary
    assert "runner error exit code 2" in summary
    assert "pytest collection: 1 errors" in summary
    assert "8 consecutive execute=blocked" in summary
    assert "NOTE: this may be STALE" in summary


def test_repair_loop_collects_stale_state_classification(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "latest_failure": {
                    "kind": "phase_failed",
                    "message": "phase 'execute' internal_error",
                    "phase": "execute",
                    "recorded_at": "2026-06-29T01:00:00Z",
                    "metadata": {"stderr": "unrecognized arguments: --retry-blocked-tasks"},
                },
                "history": [
                    {
                        "step": "execute",
                        "result": "blocked",
                        "timestamp": "2026-06-29T02:00:00Z",
                        "duration_ms": 0,
                        "artifact_hash": "sha256:repeat",
                        "output_file": "execution.json",
                    },
                    {
                        "step": "execute",
                        "result": "blocked",
                        "timestamp": "2026-06-29T02:01:00Z",
                        "duration_ms": 0,
                        "artifact_hash": "sha256:repeat",
                        "output_file": "execution.json",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text(
        json.dumps(
            {
                "seq": 10,
                "kind": "gate",
                "phase": "gate",
                "ts_utc": "2026-06-29T01:30:00Z",
                "payload": {"recommendation": "PROCEED"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "awaiting_human"}),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "stale_state"
    assert payload["state_mismatch"]["detected"] is False
    stale = payload["stale_state"]
    assert stale["classification"] == "STALE STATE"
    assert stale["latest_failure_stale"] is True
    assert stale["latest_success_after_failure"]["timestamp"] == "2026-06-29T01:30:00Z"
    assert stale["stale_block_replay"]["detected"] is True
    assert stale["stale_block_replay"]["artifact_hash"] == "sha256:repeat"


def test_repair_loop_collects_named_single_plan_in_mixed_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    target = workspace / ".megaplan" / "plans" / "target-plan"
    unrelated = workspace / ".megaplan" / "plans" / "newer-unrelated"
    _write_plan(
        target,
        {
            "name": "target-plan",
            "current_state": "planning",
            "latest_failure": None,
            "history": [],
        },
        plan_v_bodies={"plan_v1.md": "target"},
        events_body=json.dumps({"kind": "plan_started", "phase": "plan"}) + "\n",
    )
    _write_plan(
        unrelated,
        {
            "name": "newer-unrelated",
            "current_state": "blocked",
            "latest_failure": {
                "kind": "phase_failed",
                "phase": "execute",
                "message": "newer unrelated failure",
            },
            "history": [{"step": "execute", "result": "error"}],
        },
        plan_v_bodies={"plan_v1.md": "unrelated"},
        events_body=json.dumps({"kind": "phase_end", "phase": "execute", "payload": {"status": "failed"}}) + "\n",
    )
    log_dir = workspace / ".megaplan" / "cloud-logs"
    log_dir.mkdir(parents=True)
    (log_dir / "target-plan-cloud.log").write_text("target plan log line\n", encoding="utf-8")
    old_ts = time.time() - 600
    new_ts = time.time()
    os.utime(target / "state.json", (old_ts, old_ts))
    os.utime(unrelated / "state.json", (new_ts, new_ts))

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "single-session", "plan", "target-plan")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["run_kind"] == "plan"
    assert payload["requested_plan_name"] == "target-plan"
    assert payload["plan_latest_failure"]["plan_name"] == "target-plan"
    assert payload["plan_latest_failure"]["state_path"].endswith("/target-plan/state.json")
    assert payload["failure_classification"] == "unknown_failure_mode"
    assert "target plan log line" in payload["run_log_tail"]
    assert payload["chain_log_tail"] == ""
    assert payload["chain_state_summary"] == {}


def test_repair_loop_clear_stale_state_trims_replay_tail_and_backs_up_phase_result(tmp_path: Path) -> None:
    plan_dir = tmp_path / "workflow" / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "latest_failure": {"kind": "phase_failed", "recorded_at": "2026-06-29T01:00:00Z"},
                "history": [
                    {"step": "gate", "result": "success", "timestamp": "2026-06-29T01:30:00Z"},
                    {
                        "step": "execute",
                        "result": "blocked",
                        "duration_ms": 0,
                        "artifact_hash": "sha256:repeat",
                        "timestamp": "2026-06-29T02:00:00Z",
                    },
                    {
                        "step": "execute",
                        "result": "blocked",
                        "duration_ms": 0,
                        "artifact_hash": "sha256:repeat",
                        "timestamp": "2026-06-29T02:01:00Z",
                    },
                ],
                "meta": {},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "phase_result.json").write_text(
        json.dumps({"phase": "execute", "exit_kind": "blocked_by_prereq"}),
        encoding="utf-8",
    )
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(json.dumps({"initial_facts": {}, "iterations": []}), encoding="utf-8")
    failure_context = {
        "plan_latest_failure": {"state_path": str(state_path)},
        "stale_state": {
            "classification": "STALE STATE",
            "latest_failure_stale": True,
            "latest_success_after_failure": {"timestamp": "2026-06-29T01:30:00Z"},
            "stale_block_replay": {
                "detected": True,
                "artifact_hash": "sha256:repeat",
                "duration_ms": 0,
            },
        },
    }

    program = _extract_repair_program(
        "repair_clear_stale_state_if_needed",
        "python3 - \"$DATA_FILE\" \"$failure_context\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path), json.dumps(failure_context))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("cleared:")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["latest_failure"] is None
    assert [item["step"] for item in state["history"]] == ["gate"]
    assert not (plan_dir / "phase_result.json").exists()
    assert list(plan_dir.glob("phase_result.stale-*.json"))
    repair_data = json.loads(data_path.read_text(encoding="utf-8"))
    assert repair_data["stale_state_actions"][0]["actions"]


def test_repair_loop_clear_stale_state_syncs_plan_chain_mismatch(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo-plan"
    chain_dir = tmp_path / ".megaplan" / "initiatives" / "demo" / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    chain_path = chain_dir / "chain-demo.json"
    state_path.write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "latest_failure": None,
                "meta": {},
            }
        ),
        encoding="utf-8",
    )
    chain_path.write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "last_state": "awaiting_human",
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(json.dumps({"initial_facts": {}, "iterations": []}), encoding="utf-8")
    failure_context = {
        "plan_latest_failure": {
            "plan_name": "demo-plan",
            "state_path": str(state_path),
            "current_state": "finalized",
        },
        "stale_state": {
            "classification": "NO LATEST FAILURE",
            "summary": "no latest_failure is set",
        },
        "state_mismatch": {
            "detected": True,
            "plan_state": "finalized",
            "chain_last_state": "awaiting_human",
            "plan_name": "demo-plan",
            "chain_plan_name": "demo-plan",
            "plan_state_path": str(state_path),
            "chain_state_path": str(chain_path),
        },
    }

    program = _extract_repair_program(
        "repair_clear_stale_state_if_needed",
        "python3 - \"$DATA_FILE\" \"$failure_context\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path), json.dumps(failure_context))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("cleared:")
    assert "state mismatch detected + cleared" in result.stdout
    chain_state = json.loads(chain_path.read_text(encoding="utf-8"))
    assert chain_state["last_state"] == "finalized"
    records = chain_state["metadata"]["watchdog_repair_state_mismatch_clears"]
    assert records[0]["chain_last_state_was"] == "awaiting_human"
    repair_data = json.loads(data_path.read_text(encoding="utf-8"))
    action = repair_data["stale_state_actions"][0]
    assert action["state_mismatch"]["cleared"] is True
    assert repair_data["initial_facts"]["state_mismatch"]["cleared"] is True


def test_repair_loop_collects_state_meta_user_action_resolutions(tmp_path: Path) -> None:
    workspace = tmp_path / "workflow"
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)

    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "latest_failure": {"kind": "phase_failed", "message": "phase 'execute' internal_error"},
                "meta": {
                    "user_action_resolutions": {
                        "ua-01-decide-cleanup": {"state": "satisfied", "reason": "covered by evidence"}
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "user_actions": [
                    {
                        "id": "ua-01-decide-cleanup",
                        "phase": "before_execute",
                        "blocks_task_ids": ["T1"],
                        "rationale": "Maintainer decision affects cleanup.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "user_actions.md").write_text(
        "# User Actions\n\n- **ua-01-decide-cleanup**: Decide cleanup scope.\n",
        encoding="utf-8",
    )
    (chain_dir / "chain-demo.json").write_text(
        json.dumps({"current_plan_name": "demo-plan", "last_state": "awaiting_human"}),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["user_action_context"]["unresolved_user_actions"] == []


def test_repair_loop_summary_inlines_error_narrative_and_attempt_history(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "initial_facts": {},
                "iterations": [
                    {
                        "i": 1,
                        "dev_model": "gpt-5.4",
                        "dev_summary": "cleared stale markers only",
                        "mechanical_launch": "failed:retrying_failure",
                        "kimi_launch": "failed:retrying_failure",
                        "why": "status label changed but same execute failure remained",
                    },
                    {
                        "i": 2,
                        "dev_model": "gpt-5.5",
                        "failure_classification": "cli_or_argument_error",
                        "raw_failure_signals": [
                            "__main__.py: error: unrecognized arguments: --confirm-destructive --user-approved"
                        ],
                        "chain_log_tail": "[chain] resuming existing plan demo-plan\n[auto demo-plan] phase 'execute' exited with internal_error",
                        "plan_events_tail": "execute:phase_failed | reason=cli rejected flags",
                        "plan_latest_failure": {
                            "current_state": "finalized",
                            "phase": "execute",
                            "iteration": 21,
                            "kind": "phase_failed",
                            "message": "phase 'execute' internal_error",
                            "recorded_at": "2026-06-28T19:30:34Z",
                            "state_path": "/tmp/demo/state.json",
                            "events_path": "/tmp/demo/events.ndjson",
                            "metadata": {"exit_code": 2},
                        },
                        "chain_state_summary": {
                            "path": "/tmp/demo/chain.json",
                            "last_state": "awaiting_human",
                            "current_plan_name": "demo-plan",
                        },
                        "user_action_context": {
                            "plan_dir": "/tmp/demo",
                            "user_actions_path": "/tmp/demo/user_actions.md",
                            "resolutions_path": "/tmp/demo/user_action_resolutions.json",
                            "finalize_path": "/tmp/demo/finalize.json",
                            "user_actions_md": "# User Actions\n\n- **ua-01-decide-cleanup**: Decide cleanup scope.",
                            "unresolved_user_actions": [
                                {
                                    "id": "ua-01-decide-cleanup",
                                    "phase": "before_execute",
                                    "blocks_task_ids": ["T1"],
                                    "resolution_state": "unresolved",
                                    "summary": "Decide cleanup scope.",
                                }
                            ],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    summary = result.stdout
    assert "## Incident Snapshot" in summary
    assert "unrecognized arguments: --confirm-destructive --user-approved" in summary
    assert "[auto demo-plan] phase 'execute' exited with internal_error" in summary
    assert "## Prior repair attempts" in summary
    assert "i1 model=gpt-5.4 attempted=cleared stale markers only" in summary
    assert "plan events: /tmp/demo/events.ndjson" in summary
    assert "## User Action Gate" in summary
    assert "ua-01-decide-cleanup" in summary
    assert "user action resolutions: /tmp/demo/user_action_resolutions.json" in summary


def test_repair_loop_summary_falls_back_to_latest_failure_metadata(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "initial_facts": {},
                "iterations": [
                    {
                        "i": 1,
                        "dev_model": "gpt-5.4",
                        "mechanical_launch": "failed:retrying_failure",
                        "chain_log_tail": "[chain] resuming existing plan demo-plan",
                        "plan_latest_failure": {
                            "current_state": "finalized",
                            "phase": "execute",
                            "iteration": 21,
                            "kind": "phase_failed",
                            "message": "phase 'execute' internal_error",
                            "metadata": {
                                "exit_code": 2,
                                "stderr": (
                                    "usage: __main__.py [-h]\n"
                                    "__main__.py: error: unrecognized arguments: --confirm-destructive --user-approved"
                                ),
                            },
                        },
                        "chain_state_summary": {
                            "last_state": "awaiting_human",
                            "current_plan_name": "demo-plan",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    summary = result.stdout
    assert "failure classification: cli_or_argument_error" in summary
    assert "latest_failure.metadata.stderr:" in summary
    assert "unrecognized arguments: --confirm-destructive --user-approved" in summary
    assert "latest_failure.metadata.exit_code: 2" in summary


def test_repair_loop_renders_recurrence_block_from_controlled_signature_history(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "attempts": [
                    {
                        "attempt_id": 1,
                        "dev_model": "gpt-5.4",
                        "dev_summary": "patched prompt-path normalization only",
                        "dev_fix_sha": "abc1234",
                        "dev_hypothesis": "worker read stale prompt target",
                    },
                    {
                        "attempt_id": 2,
                        "dev_model": "gpt-5.5",
                        "dev_summary": "cleared stale state only",
                        "dev_fix_sha": "def5678",
                        "dev_hypothesis": "plan state was stale",
                    },
                ],
                "current_recurrence": {
                    "detected": True,
                    "attempt_number": 3,
                    "problem_signature": {
                        "failure_kind": "authority_divergence",
                        "current_state": "blocked",
                        "phase_or_step": "execute",
                        "milestone_or_plan": "m7-final-gate",
                        "gate_recommendation": "ITERATE",
                        "blocked_task_id": "m7-13-full-suite-final-gate",
                    },
                    "layer1": {"detected": True, "matching_attempt_ids": [1, 2], "repeat_count": 2},
                    "layer2": {
                        "detected": True,
                        "no_advance_dispatch_count": 3,
                        "min_dispatches": 3,
                        "window_seconds": 21600,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "render_recurrence_block",
        "python3 - \"$DATA_FILE\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    block = result.stdout
    assert "## RECURRENCE EVIDENCE" in block
    assert "This is attempt 3 for the same controlled-field symptom (recurrence detected)." in block
    assert "The symptom came back despite these prior fixes:" in block
    assert "Recurrence means the prior attempts may have treated symptoms, not the cause." in block
    assert "Layer 1 fired" in block
    assert "Layer 2 fired" in block
    assert "authority_divergence" in block
    assert "attempt 1: model=gpt-5.4" in block
    assert "attempt 2: model=gpt-5.5" in block


def test_repair_loop_classifies_completed_chain_as_chain_completed(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "",
                "current_state": "",
                "last_state": "done",
                "events": [{"msg": "all milestones complete"}],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo-chain.log").write_text(
        "[chain] all milestones complete\n",
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo-chain", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "chain_completed"


def test_repair_loop_classifies_completed_chain_with_null_current_fields(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": None,
                "current_state": None,
                "last_state": "done",
                "events": [{"msg": "all milestones complete"}],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    result = _run_embedded_python(program, str(workspace), "demo-chain", "chain", "")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "chain_completed"


def test_repair_loop_reclassifies_completed_chain_history_unknown_sentinels(tmp_path: Path) -> None:
    data_path = tmp_path / "repair-data.json"
    data_path.write_text(
        json.dumps(
            {
                "iterations": [
                    {
                        "failure_classification": "timeout_or_hang",
                        "plan_latest_failure": {"kind": "phase_failed", "message": "phase failed"},
                        "raw_failure_signals": ["latest_failure.kind: phase_failed"],
                        "chain_state_summary": {
                            "last_state": "done",
                            "current_plan_name": "unknown",
                            "current_state": "unknown",
                            "events": [{"msg": "all milestones complete"}],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "render_failure_summary",
        "python3 - \"$data_path\" <<'PY'",
    )
    result = _run_embedded_python(program, str(data_path))

    assert result.returncode == 0, result.stderr
    assert "failure classification: chain_completed" in result.stdout


def test_repair_loop_exits_immediately_for_completed_chain(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "ws"
    bin_dir = tmp_path / "bin"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()
    bin_dir.mkdir()

    calls_log = tmp_path / "calls.log"
    for name in ("tmux", "codex"):
        path = bin_dir / name
        path.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' {name!r} >> {str(calls_log)!r}\n"
            "exit 97\n",
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    timeout_path = bin_dir / "timeout"
    timeout_path.write_text(
        "#!/usr/bin/env bash\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    timeout_path.chmod(timeout_path.stat().st_mode | stat.S_IXUSR)

    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text(json.dumps({"run_kind": "chain"}), encoding="utf-8")
    _write_chain_state(
        workspace / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_plan_name": "demo-plan",
            "current_milestone_index": 3,
            "last_state": "done",
            "completed": [{"label": "m1"}, {"label": "m2"}, {"label": "m3"}],
            "milestones": [{"label": "m1"}, {"label": "m2"}, {"label": "m3"}],
        },
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "blocked",
            "iteration": 3,
            "latest_failure": {"kind": "authority_divergence", "message": "stale", "recorded_at": "2026-06-29T00:00:00Z"},
        },
    )

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    result = subprocess.run(
        ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), str(spec_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    combined = f"{result.stdout}\n{result.stderr}"
    assert "chain already complete; no repair needed" in combined
    assert not calls_log.exists() or not calls_log.read_text(encoding="utf-8").strip()
    assert not (marker_dir / "demo-session.repair-loop.pid").exists()


def test_watchdog_liveness_is_scoped_to_marked_chain_spec() -> None:
    text = _wrapper("arnold-watchdog")

    assert 'local remote_spec="$3"' in text
    assert "ps -eww -o args=" in text
    assert 'grep -Fq -- "$remote_spec"' in text
    assert 'health="$(session_health_status "$session" "$workspace" "$remote_spec" "$run_kind" "$plan_name")"' in text


def test_watchdog_checks_plan_phase_health_even_when_session_alive() -> None:
    text = _wrapper("arnold-watchdog")

    assert "plan_phase_health_status()" in text
    assert 'phase_health="$(plan_phase_health_status "$workspace" "$run_kind" "$plan_name")"' in text
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
                "'You are the watchdog repair-loop dev-fix agent for a stopped Arnold cloud session. "
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
    assert 'pgrep -f "/$PRIMARY_REPAIR_BASENAME[[:space:]]+$session([[:space:]]|$)"' in text
    assert 'printf \'%s/%s.kimi-pgid\' "$MARKER_DIR" "$1"' in text
    assert 'kill -0 -- "-$pgid"' in text
    assert 'grep -F "[a]rnold-kimi-goal-operator $session "' not in text


def test_watchdog_kimi_repair_is_backgrounded_so_it_cannot_block_the_tick() -> None:
    text = _wrapper("arnold-watchdog")

    # The bounded repair loop is launched in the background (setsid ... &) so a
    # repair on one session cannot block the tick from scanning/reporting the
    # other sessions.
    assert "dispatch_kimi_repair()" in text
    assert 'setsid bash -c \'echo "$$" > "$1"; exec "$2" "$3" "$4" "$5"\'' in text
    assert 'PRIMARY_REPAIR_BIN="${CLOUD_WATCHDOG_PRIMARY_REPAIR_BIN:-/usr/local/bin/arnold-repair-loop}"' in text
    assert "kimi_dispatch_marker_set" in text
    assert "mechanical_relaunch_attempted_previously" in text
    assert "kimi_dispatch_failed_previously" in text
    # The direct-relaunch fallback consumes the marker (repair loop tried and exited w/o recovery).
    assert "session stopped; repair loop tried and exited without recovery -> direct relaunch" in text
    assert "session stopped; mechanical relaunch first" in text
    assert "session stopped after mechanical relaunch: background-dispatched repair loop" in text
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


def test_watchdog_repair_dispatch_is_scoped_per_session() -> None:
    text = _wrapper("arnold-watchdog")

    assert "repair_pidfile_path()" in text
    assert "repair_loop_pid_matches_session()" in text
    assert "repair_loop_busy_state()" in text
    assert 'repair_busy="$(repair_loop_busy_state "$session")"' in text
    assert 'pidfile="$(repair_pidfile_path "$session")"' in text
    assert 'if repair_loop_pid_matches_session "$existing_pid" "$session"; then' in text
    assert "another repair loop already running; waiting turn" in text


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


def test_watchdog_skips_same_session_dispatch_when_repair_loop_is_already_running(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / "demo-spec.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("repair_pidfile_path"),
            _extract_wrapper_function("repair_loop_pid_matches_session"),
            _extract_wrapper_function("repair_loop_busy_state"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_attention_status_env() { return 0; }
kimi_operator_running() { [[ "$1" == "demo-session" ]]; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_running\trepair already running\t" in report
    assert "DISPATCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_allows_concurrent_repairs_for_different_sessions(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    log_path = tmp_path / "watchdog.log"
    launch_log = tmp_path / "repair-launches.log"
    repair_bin = tmp_path / "fake-repair-loop"
    repair_bin.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$1\" >> {str(launch_log)!r}\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    repair_bin.chmod(repair_bin.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("repair_pidfile_path"),
            _extract_wrapper_function("repair_loop_pid_matches_session"),
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_set"),
            _extract_wrapper_function("kimi_operator_running"),
            _extract_wrapper_function("repair_loop_busy_state"),
            _extract_wrapper_function("dispatch_kimi_repair"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"PRIMARY_REPAIR_BIN={str(repair_bin)!r}",
            f"PRIMARY_REPAIR_BASENAME={repair_bin.name!r}",
            f"LOG={str(log_path)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
dispatch_kimi_repair demo-a /tmp/ws /tmp/spec
echo "first:${REPAIR_DISPATCH_RESULT:-unset}"
dispatch_kimi_repair demo-b /tmp/ws /tmp/spec
echo "second:${REPAIR_DISPATCH_RESULT:-unset}"
for _ in {1..20}; do
  [[ -f __LAUNCH_LOG__ ]] && [[ "$(wc -l < __LAUNCH_LOG__)" -ge 2 ]] && break
  sleep 0.1
done
if [[ -f "$(kimi_pgid_path demo-a)" ]]; then
  demo_pgid="$(cat "$(kimi_pgid_path demo-a)")"
  kill -- "-$demo_pgid" 2>/dev/null || kill "$demo_pgid" 2>/dev/null || true
fi
if [[ -f "$(kimi_pgid_path demo-b)" ]]; then
  demo_pgid="$(cat "$(kimi_pgid_path demo-b)")"
  kill -- "-$demo_pgid" 2>/dev/null || kill "$demo_pgid" 2>/dev/null || true
fi
sleep 0.1
""".replace("__LAUNCH_LOG__", shlex.quote(str(launch_log))).strip(),
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["first:dispatched", "second:dispatched"]
    assert sorted(launch_log.read_text(encoding="utf-8").strip().splitlines()) == ["demo-a", "demo-b"]


def test_watchdog_dispatch_skips_duplicate_same_session_repair(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    log_path = tmp_path / "watchdog.log"
    launch_log = tmp_path / "repair-launches.log"
    repair_bin = tmp_path / "fake-repair-loop"
    repair_bin.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$1\" >> {str(launch_log)!r}\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    repair_bin.chmod(repair_bin.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("safe_name"),
            _extract_wrapper_function("repair_pidfile_path"),
            _extract_wrapper_function("repair_loop_pid_matches_session"),
            _extract_wrapper_function("kimi_dispatch_marker_path"),
            _extract_wrapper_function("kimi_pgid_path"),
            _extract_wrapper_function("kimi_dispatch_marker_set"),
            _extract_wrapper_function("kimi_operator_running"),
            _extract_wrapper_function("repair_loop_busy_state"),
            _extract_wrapper_function("dispatch_kimi_repair"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"PRIMARY_REPAIR_BIN={str(repair_bin)!r}",
            f"PRIMARY_REPAIR_BASENAME={repair_bin.name!r}",
            f"LOG={str(log_path)!r}",
            """
log() { printf '%s\n' "$*" >> "$LOG"; }
dispatch_kimi_repair demo-a /tmp/ws /tmp/spec
echo "first:${REPAIR_DISPATCH_RESULT:-unset}"
for _ in {1..20}; do
  [[ -f __LAUNCH_LOG__ ]] && break
  sleep 0.1
done
dispatch_kimi_repair demo-a /tmp/ws /tmp/spec
echo "second:${REPAIR_DISPATCH_RESULT:-unset}"
if [[ -f "$(kimi_pgid_path demo-a)" ]]; then
  demo_pgid="$(cat "$(kimi_pgid_path demo-a)")"
  kill -- "-$demo_pgid" 2>/dev/null || kill "$demo_pgid" 2>/dev/null || true
fi
sleep 0.1
""".replace("__LAUNCH_LOG__", shlex.quote(str(launch_log))).strip(),
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["first:dispatched", "second:busy"]
    assert launch_log.read_text(encoding="utf-8").strip().splitlines() == ["demo-a"]
    assert "repair loop already active; skipping dispatch session=demo-a" in log_path.read_text(
        encoding="utf-8"
    )


def test_repair_loop_serializes_same_session_invocations_and_cleans_pidfile_on_term(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "ws"
    bin_dir = tmp_path / "bin"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()
    bin_dir.mkdir()

    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text(
        json.dumps({"run_kind": "plan", "plan_name": "demo-plan", "relaunch_command": "true"}),
        encoding="utf-8",
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "blocked",
            "iteration": 1,
            "latest_failure": {
                "kind": "phase_failed",
                "message": "boom",
                "recorded_at": "2026-06-29T00:00:00Z",
                "metadata": {"exit_code": 1},
            },
        },
    )

    timeout_path = bin_dir / "timeout"
    timeout_path.write_text(
        "#!/usr/bin/env bash\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    timeout_path.chmod(timeout_path.stat().st_mode | stat.S_IXUSR)
    codex_path = bin_dir / "codex"
    codex_path.write_text(
        "#!/usr/bin/env bash\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR)
    launcher_path = tmp_path / "launcher.py"
    launcher_path.write_text("import time\n\ntime.sleep(5)\n", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    env["CLOUD_WATCHDOG_HERMES_LAUNCHER"] = str(launcher_path)

    args = ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), "/tmp/spec.json"]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    pidfile = marker_dir / "demo-session.repair-loop.pid"
    try:
        for _ in range(100):
            if pidfile.exists():
                break
            time.sleep(0.05)
        assert pidfile.exists(), "repair loop never claimed pidfile"

        second = subprocess.run(args, capture_output=True, text=True, env=env, check=False)
        assert second.returncode == 75
        assert "another repair loop is already active" in f"{second.stdout}\n{second.stderr}"
    finally:
        proc.terminate()
        proc.wait(timeout=15)

    assert not pidfile.exists()


def test_repair_loop_reclaims_stale_pidfile_on_start(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "ws"
    bin_dir = tmp_path / "bin"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()
    bin_dir.mkdir()

    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text(
        json.dumps({"run_kind": "plan", "plan_name": "demo-plan", "relaunch_command": "true"}),
        encoding="utf-8",
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "blocked",
            "iteration": 1,
            "latest_failure": {
                "kind": "phase_failed",
                "message": "boom",
                "recorded_at": "2026-06-29T00:00:00Z",
                "metadata": {"exit_code": 1},
            },
        },
    )
    stale_pidfile = marker_dir / "demo-session.repair-loop.pid"
    stale_pidfile.write_text("999999\n", encoding="utf-8")

    timeout_path = bin_dir / "timeout"
    timeout_path.write_text(
        "#!/usr/bin/env bash\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    timeout_path.chmod(timeout_path.stat().st_mode | stat.S_IXUSR)
    codex_path = bin_dir / "codex"
    codex_path.write_text(
        "#!/usr/bin/env bash\n"
        "sleep 5\n",
        encoding="utf-8",
    )
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR)
    launcher_path = tmp_path / "launcher.py"
    launcher_path.write_text("import time\n\ntime.sleep(5)\n", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    env["CLOUD_WATCHDOG_HERMES_LAUNCHER"] = str(launcher_path)

    proc = subprocess.Popen(
        ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), "/tmp/spec.json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        for _ in range(100):
            if stale_pidfile.exists() and stale_pidfile.read_text(encoding="utf-8").strip() == str(proc.pid):
                break
            time.sleep(0.05)
        assert stale_pidfile.read_text(encoding="utf-8").strip() == str(proc.pid)
    finally:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=15)

    combined = f"{stdout}\n{stderr}"
    assert "stale repair pidfile detected; reclaiming" in combined
    assert not stale_pidfile.exists()


def test_repair_loop_reclaims_pidfile_after_kill9_with_child_alive(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_root = tmp_path / "repair-root"
    workspace = tmp_path / "ws"
    bin_dir = tmp_path / "bin"
    codex_pids = tmp_path / "codex-pids.txt"
    marker_dir.mkdir()
    repair_root.mkdir()
    workspace.mkdir()
    bin_dir.mkdir()

    (marker_dir / "demo-session.json").write_text(
        json.dumps({"run_kind": "plan", "plan_name": "demo-plan", "relaunch_command": "true"}),
        encoding="utf-8",
    )
    _write_plan(
        workspace / ".megaplan" / "plans" / "demo-plan",
        {
            "name": "demo-plan",
            "current_state": "blocked",
            "iteration": 1,
            "latest_failure": {
                "kind": "phase_failed",
                "message": "boom",
                "recorded_at": "2026-06-29T00:00:00Z",
                "metadata": {"exit_code": 1},
            },
        },
    )

    timeout_path = bin_dir / "timeout"
    timeout_path.write_text(
        "#!/usr/bin/env bash\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    timeout_path.chmod(timeout_path.stat().st_mode | stat.S_IXUSR)
    codex_path = bin_dir / "codex"
    codex_path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$$\" >> {shlex.quote(str(codex_pids))}\n"
        "sleep 30\n",
        encoding="utf-8",
    )
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR)
    launcher_path = tmp_path / "launcher.py"
    launcher_path.write_text("import time\n\ntime.sleep(30)\n", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_ROOT"] = str(repair_root)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(marker_dir / "repair-data")
    env["CLOUD_WATCHDOG_HERMES_LAUNCHER"] = str(launcher_path)

    args = ["bash", str(WRAPPER_DIR / "arnold-repair-loop"), "demo-session", str(workspace), "/tmp/spec.json"]
    pidfile = marker_dir / "demo-session.repair-loop.pid"
    first = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    second: subprocess.Popen[str] | None = None
    try:
        for _ in range(100):
            if pidfile.exists() and pidfile.read_text(encoding="utf-8").strip() == str(first.pid):
                break
            time.sleep(0.05)
        assert pidfile.read_text(encoding="utf-8").strip() == str(first.pid)

        first.kill()
        first.wait(timeout=15)
        assert pidfile.exists(), "kill -9 should leave a stale pidfile for recovery"

        second = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        for _ in range(100):
            if pidfile.exists() and pidfile.read_text(encoding="utf-8").strip() == str(second.pid):
                break
            time.sleep(0.05)
        assert pidfile.read_text(encoding="utf-8").strip() == str(second.pid)
    finally:
        if second is not None and second.poll() is None:
            second.terminate()
            second.communicate(timeout=15)
        if first.poll() is None:
            first.terminate()
            first.wait(timeout=15)
        if codex_pids.exists():
            for raw_pid in codex_pids.read_text(encoding="utf-8").splitlines():
                if raw_pid.strip().isdigit():
                    subprocess.run(["kill", "-9", raw_pid.strip()], check=False)


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
    assert 'wait_status="$(chain_wait_status "$workspace" "$remote_spec")"' in text
    assert 'if [[ "$health" == "awaiting_pr_merge" ]]; then' in text
    assert 'report_item "$report_items" "$session" "observe" "awaiting_pr_merge" "session waiting on PR merge"' in text
    assert '["gh", "pr", "view", str(pr_number), "--json", "state"]' in text
    assert '["gh", "pr", "merge", str(pr_number), *flags]' in text


def test_watchdog_stopped_tmux_reports_awaiting_pr_merge_from_chain_state(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: review\n", encoding="utf-8")
    (chain_dir / "demo-chain.json").write_text(
        json.dumps({"last_state": "awaiting_pr_merge"}),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("chain_wait_status"),
            _extract_wrapper_function("session_health_status"),
            """
tmux() {
  if [[ "$1" == "has-session" ]]; then
    return 1
  fi
  return 0
}
""".strip(),
            f"session_health_status demo-session {str(workspace)!r} {str(spec_path)!r} chain ''",
        ]
    )
    result = _run_watchdog_shell(script)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "awaiting_pr_merge"


def test_watchdog_auto_merge_policy_attempts_pr_merge_before_waiting(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("merge_policy: auto\n", encoding="utf-8")
    (chain_dir / "demo-chain.json").write_text(
        json.dumps({"last_state": "awaiting_pr_merge", "pr_number": 42}),
        encoding="utf-8",
    )

    gh_log = tmp_path / "gh.log"
    merged_flag = tmp_path / "merged"
    gh_path = tmp_path / "gh"
    gh_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                f"printf '%s\\n' \"$*\" >> {str(gh_log)!r}",
                "if [[ \"$1 $2 $3\" == \"pr view 42\" ]]; then",
                f"  if [[ -f {str(merged_flag)!r} ]]; then",
                "    printf '%s\\n' '{\"state\":\"MERGED\"}'",
                "  else",
                "    printf '%s\\n' '{\"state\":\"OPEN\"}'",
                "  fi",
                "  exit 0",
                "fi",
                "if [[ \"$1 $2 $3\" == \"pr ready 42\" ]]; then",
                "  exit 0",
                "fi",
                "if [[ \"$1 $2 $3\" == \"pr merge 42\" ]]; then",
                f"  touch {str(merged_flag)!r}",
                "  exit 0",
                "fi",
                "exit 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_wrapper_function("chain_wait_status"),
            f"chain_wait_status {str(workspace)!r} {str(spec_path)!r}",
        ]
    )
    result = _run_watchdog_shell(script, path_prefix=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "none"
    gh_calls = gh_log.read_text(encoding="utf-8").splitlines()
    assert "pr ready 42" in gh_calls
    assert "pr merge 42 --auto --squash --delete-branch" in gh_calls


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
    workspace_root = tmp_path / "workspace-root"
    workspace = workspace_root / "test-watchdog-vibecomfy-per-workflow-window-chat-20260628"
    (workspace / ".megaplan" / "plans" / "per-workflow-window-chat-cloud-20260628").mkdir(parents=True, exist_ok=True)

    tmux_path = tmp_path / "tmux"
    tmux_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"vibecomfy-per-workflow-window-chat\t4000\t{workspace}\t"
        "cd "
        f"{workspace}"
        " && MEGAPLAN_TRUSTED_CONTAINER=1 python3 -m arnold_pipelines.megaplan init "
        "--project-dir . --idea-file .megaplan/initiatives/per-workflow-window-chat/briefs/per-workflow-window-chat.md "
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
        "--project-dir . --idea-file .megaplan/initiatives/per-workflow-window-chat/briefs/per-workflow-window-chat.md "
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
            f"export MEGAPLAN_DISCOVER_WORKSPACE_ROOT={str(workspace_root)!r}",
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
    assert payload["remote_spec"] == ".megaplan/initiatives/per-workflow-window-chat/briefs/per-workflow-window-chat.md"
    assert "python3 -P -m arnold_pipelines.megaplan auto --plan per-workflow-window-chat-cloud-20260628" in payload["relaunch_command"]


def test_watchdog_does_not_adopt_non_arnold_tmux_sessions(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    workspace_root = tmp_path / "workspace-root"
    workspace = workspace_root / "test-watchdog-random-workspace"
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
            f"export MEGAPLAN_DISCOVER_WORKSPACE_ROOT={str(workspace_root)!r}",
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
    workspace_root = tmp_path / "workspace-root"
    workspace = workspace_root / "test-shared-discover-vibecomfy"
    (workspace / ".megaplan" / "plans" / "shared-discover-plan").mkdir(parents=True, exist_ok=True)

    tmux_path = tmp_path / "tmux"
    tmux_path.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"vibecomfy-shared-discover\t4000\t{workspace}\t"
        "cd "
        f"{workspace}"
        " && python3 -m arnold_pipelines.megaplan init --project-dir . "
        "--idea-file .megaplan/initiatives/shared/briefs/shared.md --name shared-discover-plan --auto-start\n"
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
        "--idea-file .megaplan/initiatives/shared/briefs/shared.md --name shared-discover-plan --auto-start\n"
        "5000 1 bash -lc /usr/local/bin/arnold-watchdog --once\n"
        "6000 1 bash -lc /usr/local/bin/arnold-kimi-goal-operator demo\n"
        "EOF\n",
        encoding="utf-8",
    )
    ps_path.chmod(ps_path.stat().st_mode | stat.S_IXUSR)

    result = _run_discover(tmp_path, marker_dir=marker_dir)
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.strip().splitlines() if line]
    assert len(lines) == 1
    fields = lines[0].split("\t")
    assert fields[0] == "vibecomfy-shared-discover"
    assert fields[1] == str(workspace)
    assert fields[2] == ".megaplan/initiatives/shared/briefs/shared.md"
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
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} chain {plan_name!r} ''",
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
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan '' ''",
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
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
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


def test_watchdog_auto_stall_manual_review_dispatches_repair_before_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 6,
            "current_state": "critiqued",
            "resume_cursor": {"retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "stalled",
                "message": "stalled at 'critiqued' for 5 iterations",
                "metadata": {"manual_review_origin": "auto_stall"},
            },
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("repair_needs_human_path"),
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
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tauto_stall manual_review repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


def test_watchdog_legacy_stalled_manual_review_dispatches_repair_before_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 9,
            "current_state": "critiqued",
            "resume_cursor": {"phase": "override add-note", "retry_strategy": "manual_review"},
            "latest_failure": {
                "kind": "stalled",
                "message": "stalled at 'critiqued' for 5 iterations",
                "phase": "override add-note",
                "metadata": {"stall_count": 5, "iteration": 9},
            },
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("repair_needs_human_path"),
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
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tauto_stall manual_review repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_awaiting_human_plan_state_dispatches_repair_before_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    _write_plan(
        workspace / ".megaplan" / "plans" / plan_name,
        {
            "iteration": 3,
            "current_state": "awaiting_human",
            "latest_failure": {
                "kind": "blocked_by_prereq",
                "message": "execute reported blocked tasks awaiting user action: T1",
            },
        },
        events_body="{}\n",
    )
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function_until("notify_needs_human", "adopt_unmarked_tmux_sessions"),
            _extract_wrapper_function("repair_needs_human_path"),
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
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tawaiting_human repair loop dispatched before needs_human\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "\tobserve\tcomplete\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


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
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} plan {plan_name!r} ''",
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
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
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
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
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
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} chain {plan_name!r} ''",
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
            f"launch_chain_tick demo-session {str(workspace)!r} .megaplan/initiatives/demo/briefs/demo.md {str(report_path)!r} chain {plan_name!r} ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\trepair loop dispatched after mechanical relaunch\t" in report
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
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
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
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
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
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
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


def test_watchdog_awaiting_human_chain_state_dispatches_repair_before_needs_human(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    plan_name = "demo-plan"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "iteration": 9,
            "current_state": "finalized",
        },
        events_body="{}\n",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "m7-06-runtime-deletion-target-purge",
                        "description": "Delete runtime targets.",
                        "status": "blocked",
                    }
                ],
                "user_actions": [
                    {
                        "id": "ua-01-reclassify-deletion-targets",
                        "phase": "before_execute",
                        "blocks_task_ids": ["m7-06-runtime-deletion-target-purge"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": plan_name,
                "last_state": "awaiting_human",
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
            _extract_wrapper_function("repair_needs_human_path"),
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
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\tstate mismatch repair loop dispatched\t" in report
    assert "\tobserve\tneeds_human\t" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr
    assert "needs-human webhook unset" not in log_path.read_text(encoding="utf-8")


def test_watchdog_completed_chain_state_reports_complete_without_repair(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "",
                "current_state": "",
                "last_state": "done",
                "events": [{"msg": "all milestones complete"}],
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
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH >&2; return 1; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tcomplete\tchain complete\t" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "RELAUNCH" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_missing_base_ref_chain_state_reports_needs_human_without_plan_state(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": None,
                "last_state": "missing_base_ref",
                "metadata": {
                    "missing_base_ref": {
                        "base_branch": "stack/base",
                        "last_known_sha": "abc123def456",
                        "message": "Base branch 'stack/base' is missing on origin and no local ref is available to restore it.",
                        "recorded_at": "2026-06-28T00:00:00Z",
                        "retry_strategy": "manual_review",
                    }
                },
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
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\tmanual_review halt;" in report
    assert "state=missing_base_ref" in report
    assert "failure=missing_base_ref" in report
    assert "missing_base_ref" in report
    assert "stack/base" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


def test_watchdog_normal_chain_state_does_not_force_missing_base_ref_manual_review(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": None,
                "last_state": "blocked",
                "metadata": {"note": "not missing base ref"},
            }
        ),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("plan_attention_status_env"),
            f"eval \"$(plan_attention_status_env {str(workspace)!r} {str(spec_path)!r} chain '')\"",
            "printf '%s\\t%s\\t%s\\n' \"$PLAN_STATUS_MANUAL_REVIEW\" \"$PLAN_STATUS_FAILURE_KIND\" \"$PLAN_STATUS_CURRENT_STATE\"",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0"


def test_watchdog_scan_once_completes_when_chain_state_is_unreadable(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    workspace = tmp_path / "ws"
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / "demo-session.json"
    marker_path.write_text(
        json.dumps(
            {
                "session": "demo-session",
                "workspace": str(workspace),
                "remote_spec": ".megaplan/initiatives/demo-chain/chain.yaml",
                "run_kind": "chain",
            }
        ),
        encoding="utf-8",
    )
    import hashlib

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text("{not-json\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"
    log_path = tmp_path / "watchdog.log"

    script = "\n\n".join(
        [
            _extract_wrapper_function("json_field"),
            _extract_wrapper_function("plan_attention_status_env"),
            _extract_wrapper_function("launch_chain_tick"),
            _extract_wrapper_function("scan_once"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"LOG={str(log_path)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { printf '%s\n' "$*" >> "$LOG"; }
maybe_reexec_updated_watchdog() { :; }
sync_editable_source_branch() { return 0; }
adopt_unmarked_tmux_sessions() { return 0; }
reap_stale_repairs() { return 0; }
emit_report() { cp "$1" REPORT_PATH_PLACEHOLDER; }
session_health_status() { echo stopped; }
plan_phase_health_status() { echo ok; }
plan_progress_stall_status() { echo ok; }
kimi_operator_running() { return 1; }
mechanical_relaunch_attempted_previously() { return 0; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
kimi_dispatch_failed_previously() { return 1; }
kimi_dispatch_marker_set() { :; }
kimi_dispatch_marker_clear() { :; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".replace("REPORT_PATH_PLACEHOLDER", str(report_path)).strip(),
            "scan_once",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    assert "scan complete markers=1" in log_path.read_text(encoding="utf-8")
    report = report_path.read_text(encoding="utf-8")
    assert "\trepair\trepair_dispatched\trepair loop dispatched after mechanical relaunch\t" in report
    assert "needs_human" not in report
    assert "DISPATCH" in result.stderr
    assert "REPAIR" not in result.stderr
    assert "TMUX" not in result.stderr


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
        ".megaplan/initiatives/demo/briefs/demo.md chain stopped 'manual_review halt'"
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
            f"notify_needs_human {str(report_path)!r} demo-session /tmp/ws .megaplan/initiatives/demo/briefs/demo.md chain stopped 'manual_review halt'",
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
            f"notify_needs_human {str(report_path)!r} demo-session /tmp/ws .megaplan/initiatives/demo/briefs/demo.md chain stopped 'manual_review halt'",
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
    spec_path = workspace / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
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
            f"launch_chain_tick demo-chain {str(workspace)!r} .megaplan/initiatives/demo-chain/chain.yaml {str(report_path)!r} chain '' ''",
        ]
    )
    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "alive" in report
    assert "spec_missing" not in report


def test_watchdog_scan_ignores_progress_snapshot_markers() -> None:
    text = _wrapper("arnold-watchdog")

    assert "*.progress.json|*.reap-progress.json|*.chain-health.progress.json" in text


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


def test_repair_loop_wrapper_records_accumulated_data_and_escalates_models() -> None:
    text = _wrapper("arnold-repair-loop")

    assert 'DATA_FILE="$DATA_DIR/${SAFE_SESSION}.repair-data.json"' in text
    assert 'PROGRESS_FILE="$MARKER_DIR/${SAFE_SESSION}.repair-progress.json"' in text
    assert 'NEEDS_HUMAN_FILE="$DATA_DIR/${SAFE_SESSION}.needs-human.json"' in text
    assert 'FINDINGS_DIR="${CLOUD_WATCHDOG_REPAIR_FINDINGS_DIR:-/workspace/repair-findings}"' in text
    assert 'FINDINGS_DOC="${CLOUD_WATCHDOG_REPAIR_FINDINGS_DOC:-$FINDINGS_DIR/persistent-problems.md}"' in text
    assert 'REPAIR_PID_FILE="${CLOUD_WATCHDOG_REPAIR_PID_FILE:-$MARKER_DIR/${SAFE_SESSION}.repair-loop.pid}"' in text
    assert 'REPAIR_PID_GUARD_FILE="${REPAIR_PID_FILE}.guard"' in text
    assert "acquire_repair_lock()" in text
    assert "repair_loop_pid_matches_session()" in text
    assert "find_live_repair_loop_for_session()" in text
    assert 'flock "$guard_fd"' in text
    assert 'log "repair pid claimed session=$SESSION pid=$$ pidfile=$REPAIR_PID_FILE"' in text
    assert 'log "stale repair pidfile detected; reclaiming session=$SESSION stale_pid=$existing_pid pidfile=$REPAIR_PID_FILE"' in text
    assert "guard_against_recursive_repair_loop()" in text
    assert 'export CLOUD_WATCHDOG_REPAIR_LOOP_ACTIVE=1' in text
    assert 'log "repair loop recursion blocked; parent repair loop already active' in text
    assert "acquire_repair_lock || exit 75" in text
    assert 'exit_if_repair_target_complete "start"' in text
    assert 'exit_if_repair_target_complete "iteration-$iteration-start"' in text
    assert "repair_data_init()" in text
    assert "repair_data_record_dev()" in text
    assert "append_repair_finding_if_reported()" in text
    assert 'append_repair_finding_if_reported "$iteration" "$report_path" "$dispatch_model"' in text
    assert "repair_data_record_mechanical()" in text
    assert "repair_data_record_kimi()" in text
    assert "repair_recurrence_prepare_attempt()" in text
    assert "render_recurrence_block()" in text
    assert "repair_exhausted_should_retry_without_human()" in text
    assert "collect_failure_context_json()" in text
    assert "PLAN_STATUS_STATE_MISMATCH" in _wrapper("arnold-watchdog")
    assert "render_failure_summary()" in text
    assert '"failure_context"' in text
    assert '"raw_failure_signals"' in text
    assert '"failure_classification"' in text
    assert '"chain_log_tail"' in text
    assert '"plan_events_tail"' in text
    assert '"mechanical_log_tail"' in text
    assert '"plan_latest_failure"' in text
    assert '"chain_state_summary"' in text
    assert '"pr_number": chain_state.get("pr_number")' in text
    assert '"target_base_ref": chain_state.get("target_base_ref")' in text
    assert '"workspace": str(workspace)' in text
    assert "workspace=str(payload.get(\"workspace\") or failure_context.get(\"workspace\") or \"\")" in text
    assert 'logger=lambda message: print(f"repair_recurrence: {message}", file=sys.stderr)' in text
    assert "repair_recurrence.atomic_write_json(data_path, payload)" in text
    assert "repair_recurrence.atomic_write_json(progress_path, session_snapshot)" in text
    assert "os.replace(tmp_name, target_path)" in text
    assert '"plan_runtime_state"' in text
    assert '"last_gate"' in text
    assert "for iteration in 1 2 3; do" in text
    assert 'DEV_REQUESTED_MODEL="glm-5.2"' in text
    assert 'DEV_REQUESTED_MODEL="codex:gpt-5.4"' in text
    assert 'DEV_REQUESTED_MODEL="codex:gpt-5.5"' in text
    assert 'GLM_FALLBACK="zhipu:glm-5.2 unresolved on this box; falling back to gpt-5.4 for iteration 1"' in text
    assert 'repair_data_set_outcome "running"' in text
    assert 'repair_data_set_outcome "recurring_retry_pending"' in text
    assert 'repair_data_set_outcome "discord_escalated"' in text
    assert "write_needs_human_marker" in text
    assert "send_discord_escalation" in text
    assert "## Incident Snapshot" in text
    assert "## RECURRENCE EVIDENCE" in text
    assert "This is attempt " in text
    assert "for the same controlled-field symptom (recurrence detected)." in text
    assert "The symptom came back despite these prior fixes:" in text
    assert "primary failure signal(s)" in text
    assert "current run narrative (plan log tail when present)" in text
    assert "## Prior repair attempts" in text
    assert "Repair data file: $DATA_FILE" in text
    assert "Persistent findings doc: $FINDINGS_DOC" in text
    assert "Go to the deepest structural level" in text
    assert "Do not just fix the one symptom that caused this stop" in text
    assert "Do NOT pick the likely fix" in text
    assert "Trace the actual mechanism end-to-end" in text
    assert "Use the extra time in this root-cause attempt" in text
    assert "append it to the findings doc at $FINDINGS_DOC" in text
    assert "structural_pattern, other_instantiations, human_review_recommendation" in text
    assert "findings_doc_path, findings_doc_appended" in text
    assert 'entry["structural_pattern"] = report.get("structural_pattern") or ""' in text
    assert "do not relaunch the run yourself" in text.lower()


def test_repair_loop_wrapper_bounds_mechanical_and_kimi_launch_steps() -> None:
    text = _wrapper("arnold-repair-loop")

    assert 'DEV_TIMEOUT="${CLOUD_WATCHDOG_DEV_FIX_TIMEOUT_SECS:-600}"' in text
    assert 'DEV_ROOT_CAUSE_TIMEOUT="${CLOUD_WATCHDOG_DEV_FIX_ROOT_CAUSE_TIMEOUT_SECS:-1800}"' in text
    assert 'KIMI_TIMEOUT="${CLOUD_WATCHDOG_KIMI_TIMEOUT_SECS:-600}"' in text
    assert 'KIMI_MAX_TURNS="${CLOUD_WATCHDOG_KIMI_MAX_TURNS:-40}"' in text
    assert "verify_started_and_holding()" in text
    assert "mechanical_launch_step()" in text
    assert "run_kimi_launch_turn()" in text
    assert 'timeout "$dev_timeout"' in text
    assert 'timeout "$KIMI_TIMEOUT" python3 -P -m arnold.agent.run_agent \\' in text
    assert 'tmux new-session -d -s "$session"' in text
    assert 'repair_data_record_kimi "$iteration" "$CURRENT_ATTEMPT_ID" "running"' in text


def test_watchdog_repair_loop_needs_human_sidecar_short_circuits_relaunch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"
    (repair_data_dir / "demo-session.needs-human.json").write_text(
        json.dumps(
            {
                "summary": "i1 dev=zhipu:glm-5.2 sha=abc mechanical=failed:stopped kimi=failed:bad-creds",
                "repair_data_path": str(repair_data_dir / "demo-session.repair-data.json"),
                "discord_status": "delivered",
            }
        ),
        encoding="utf-8",
    )

    script = "\n\n".join(
        [
            _extract_wrapper_function("repair_needs_human_path"),
            _extract_wrapper_function("repair_needs_human_summary"),
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_data_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo stopped; }
plan_attention_status_env() { return 0; }
kimi_operator_running() { return 1; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tneeds_human\t" in report
    assert "repair_data=" in report
    assert "discord=delivered" in report
    assert "DISPATCH" not in result.stderr
    assert "TMUX" not in result.stderr


# ---------------------------------------------------------------------------
# Progress-stall detection + progress auditor (new components)
# ---------------------------------------------------------------------------


def _extract_phase_program() -> str:
    """Pull the python body of plan_phase_health_status() out of the wrapper."""
    text = _wrapper("arnold-watchdog")
    start = text.index("plan_phase_health_status() {")
    marker = "python3 - \"$workspace\" \"$run_kind\" \"$plan_name\" <<'PY'"
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _run_phase(workspace: Path, run_kind: str = "chain", plan_name: str = "") -> str:
    program = _extract_phase_program()
    prog_path = workspace.parent / "_phase_prog.py"
    prog_path.write_text(program, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(prog_path), str(workspace), run_kind, plan_name],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"phase program failed: {result.stderr}"
    return result.stdout.strip()


def _extract_stall_program() -> str:
    """Pull the python body of plan_progress_stall_status() out of the wrapper."""
    text = _wrapper("arnold-watchdog")
    start = text.index("plan_progress_stall_status() {")
    marker = "python3 - \"$workspace\" \"$MARKER_DIR\" \"$run_kind\" \"$plan_name\" <<'PY'"
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _run_stall(
    workspace: Path,
    marker: Path,
    env_overrides: dict[str, str] | None = None,
    run_kind: str = "chain",
    plan_name: str = "",
) -> str:
    program = _extract_stall_program()
    prog_path = workspace.parent / "_stall_prog.py"
    prog_path.write_text(program, encoding="utf-8")
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(prog_path), str(workspace), str(marker), run_kind, plan_name],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"stall program failed: {result.stderr}"
    return result.stdout.strip()


def _extract_chain_health_program() -> str:
    """Pull the python body of chain_health_status() out of the wrapper."""
    text = _wrapper("arnold-watchdog")
    start = text.index("chain_health_status() {")
    marker = 'eval "$(python3 - "$session" "$workspace" "$remote_spec_path" "$health" "$MARKER_DIR" "$REPAIR_DATA_DIR" <<\'PY\''
    py_start = text.index(marker, start)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _parse_shell_assignments(stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in stdout.strip().splitlines():
        name, sep, raw_value = line.partition("=")
        if not sep:
            continue
        values = shlex.split(raw_value)
        parsed[name] = values[0] if values else ""
    return parsed


def _run_chain_health(
    workspace: Path,
    marker: Path,
    repair_data_dir: Path,
    *,
    session: str = "demo",
    remote_spec_path: str = "",
    health: str = "stopped",
    env_overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    program = _extract_chain_health_program()
    prog_path = workspace.parent / "_chain_health_prog.py"
    prog_path.write_text(program, encoding="utf-8")
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            session,
            str(workspace),
            remote_spec_path,
            health,
            str(marker),
            str(repair_data_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, f"chain health program failed: {result.stderr}"
    return _parse_shell_assignments(result.stdout)


def _write_plan(plan_dir: Path, state: dict, plan_v_bodies: dict[str, str] | None = None,
                events_body: str = "") -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    for name, body in (plan_v_bodies or {}).items():
        (plan_dir / name).write_text(body, encoding="utf-8")
    if events_body:
        (plan_dir / "events.ndjson").write_text(events_body, encoding="utf-8")


def _write_chain_state(state_path: Path, state: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state), encoding="utf-8")


def _init_git_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Watchdog Tests"], cwd=path, check=True)
    (path / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=path, check=True, capture_output=True, text=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def test_chain_health_status_is_wired_into_launch_chain_tick() -> None:
    text = _wrapper("arnold-watchdog")

    assert "chain_health_status()" in text
    assert 'chain_health_status "$session" "$workspace" "$remote_spec_path" "$health"' in text
    assert 'report_item "$report_items" "$session" "observe" "${CHAIN_HEALTH_STATUS:-chain_issue}"' in text


def test_watchdog_chain_health_short_circuits_plan_repair_dispatch(tmp_path: Path) -> None:
    marker_dir = tmp_path / "markers"
    repair_dir = tmp_path / "repair-data"
    marker_dir.mkdir()
    repair_dir.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    spec_path = workspace / "demo-spec.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    report_path = tmp_path / "report.tsv"

    script = "\n\n".join(
        [
            _extract_wrapper_function("launch_chain_tick"),
            f"MARKER_DIR={str(marker_dir)!r}",
            f"REPAIR_DATA_DIR={str(repair_dir)!r}",
            """
report_item() {
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7" >> "$1"
}
log() { :; }
session_health_status() { echo alive; }
chain_health_status() {
  CHAIN_HEALTH_STATUS=chain_cycle
  CHAIN_HEALTH_SUMMARY='chain cycle detected'
  CHAIN_HEALTH_ARTIFACT_PATH=/tmp/chain-health.json
}
plan_phase_health_status() { echo phase_failure:should-not-run; }
plan_progress_stall_status() { echo progress_stall:should-not-run; }
plan_attention_status_env() { echo SHOULD_NOT_RUN >&2; }
repair_loop_busy_state() { echo none; }
dispatch_kimi_repair() { echo DISPATCH >&2; return 0; }
repair_unhealthy_session() { echo REPAIR >&2; return 0; }
mechanical_relaunch_attempted_previously() { return 1; }
kimi_dispatch_failed_previously() { return 1; }
ensure_install_or_repair() { return 0; }
resolve_relaunch_command() { echo RELAUNCH; }
safe_name() { printf '%s\n' "$1"; }
tmux() { echo TMUX >&2; return 1; }
""".strip(),
            f"launch_chain_tick demo-session {str(workspace)!r} {str(spec_path)!r} {str(report_path)!r} chain '' ''",
        ]
    )

    result = _run_watchdog_shell(script)
    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "\tobserve\tchain_cycle\tchain cycle detected; artifact=/tmp/chain-health.json\t" in report
    assert "DISPATCH" not in result.stderr
    assert "REPAIR" not in result.stderr
    assert "SHOULD_NOT_RUN" not in result.stderr
    assert "TMUX" not in result.stderr


def test_chain_health_status_detects_repeating_merged_pr_completion_guard_cycle() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    spec_path = ws / ".megaplan" / "initiatives" / "demo-chain" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    plan_name = "m8-generated-assets-and-merge-20260629-1937"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {"current_state": "blocked", "iteration": 1},
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / f"chain-{digest}.json",
        {
            "current_milestone_index": 7,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_number": 128,
            "pr_state": "merged",
            "completed": [{"label": "m1"}, {"label": "m2"}],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    repeated = "\n".join(
        [
            "[chain] PR #128 merged; advancing past m8-generated-assets-merge-result-conformance",
            "[chain] completion guard blocked m8-generated-assets-merge-result-conformance: plan m8-generated-assets-and-merge-20260629-1937 current_state='blocked' is not terminal-success 'done'",
            '[chain] synced last_state for m8-generated-assets-and-merge-20260629-1937: authority_divergence -> blocked',
        ]
        * 3
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(repeated + "\n", encoding="utf-8")

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        remote_spec_path=str(spec_path),
        env_overrides={"CLOUD_WATCHDOG_CHAIN_CYCLE_REPEATS": "3"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "chain_cycle"
    artifact_path = Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"])
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_cycle"
    assert artifact["completion_guard"]["milestone"] == "m8-generated-assets-merge-result-conformance"
    assert artifact["completion_guard"]["repeat_count"] == 3
    assert "## CHAIN HEALTH EVIDENCE" in artifact["evidence_markdown"]
    assert "Route to arnold_pipelines/megaplan/chain/" in artifact["why_chain_layer_issue"]


def test_chain_health_status_leaves_one_off_completion_guard_repair_eligible() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    plan_name = "sprint-1-safe-compiler-20260630-0033"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {"current_state": "blocked", "iteration": 1},
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_state": "",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        "[chain] completion guard blocked sprint-01-safe-compiler-foundation: "
        "no semantic diff from milestone_base_sha 9d2d53e to local HEAD; "
        "no typed no-op completion waiver found\n",
        encoding="utf-8",
    )

    payload = _run_chain_health(ws, marker, repair_dir, health="stopped")

    assert payload["CHAIN_HEALTH_STATUS"] == "ok"
    assert payload["CHAIN_HEALTH_ARTIFACT_PATH"] == ""


def test_chain_health_status_escalates_recurring_completion_guard_with_zero_git_advancement() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    base_sha = _init_git_repo(ws)
    plan_name = "sprint-1-safe-compiler-20260630-0033"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "blocked",
            "iteration": 3,
            "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
        },
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_state": "",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        (
            "[chain] completion guard blocked sprint-01-safe-compiler-foundation: "
            f"no semantic diff from milestone_base_sha {base_sha} to local HEAD; "
            "no typed no-op completion waiver found\n"
        )
        * 3,
        encoding="utf-8",
    )

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="stopped",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_COMPLETION_GUARD_REPEATS": "3"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "needs_human"
    assert "produces NO code changes" in payload["CHAIN_HEALTH_SUMMARY"]
    assert "Not auto-repairable" in payload["CHAIN_HEALTH_SUMMARY"]
    artifact = json.loads(Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "plan_noop_completion_guard"
    assert artifact["completion_guard"]["repeat_count"] == 3
    assert artifact["details"]["completion_guard_advancement"]["available"] is True
    assert artifact["details"]["completion_guard_advancement"]["ahead_count"] == 0
    assert artifact["details"]["completion_guard_worktree"]["dirty"] is False


def test_chain_health_status_classifies_zero_git_advancement_with_dirty_worktree_as_commit_bug() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    base_sha = _init_git_repo(ws)
    (ws / "compiler.py").write_text("print('uncommitted execute output')\n", encoding="utf-8")
    plan_name = "sprint-1-safe-compiler-20260630-0033"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "blocked",
            "iteration": 3,
            "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
        },
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_state": "",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        (
            "[chain] completion guard blocked sprint-01-safe-compiler-foundation: "
            f"no semantic diff from milestone_base_sha {base_sha} to local HEAD; "
            "no typed no-op completion waiver found\n"
        )
        * 3,
        encoding="utf-8",
    )

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="stopped",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_COMPLETION_GUARD_REPEATS": "3"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "chain_uncommitted_execute_output"
    assert "execute output was not committed" in payload["CHAIN_HEALTH_SUMMARY"]
    assert "no-op waiver" in payload["CHAIN_HEALTH_SUMMARY"]
    assert "CHAIN HEALTH EVIDENCE: working tree has 1 uncommitted files" in payload["CHAIN_HEALTH_LOG_MESSAGE"]
    artifact = json.loads(Path(payload["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_uncommitted_execute_output"
    worktree = artifact["details"]["completion_guard_worktree"]
    assert worktree["dirty"] is True
    assert worktree["uncommitted_file_count"] == 1
    assert "compiler.py" in "\n".join(worktree["sample"])
    assert "Working tree evidence: 1 uncommitted files" in artifact["evidence_markdown"]
    assert "commit-and-push gating" in artifact["evidence_markdown"]


def test_chain_health_status_keeps_recurring_completion_guard_repair_eligible_when_git_advanced() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    base_sha = _init_git_repo(ws)
    (ws / "compiler.py").write_text("print('work landed')\n", encoding="utf-8")
    subprocess.run(["git", "add", "compiler.py"], cwd=ws, check=True)
    subprocess.run(["git", "commit", "-m", "land work"], cwd=ws, check=True, capture_output=True, text=True)
    plan_name = "sprint-1-safe-compiler-20260630-0033"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {
            "current_state": "blocked",
            "iteration": 3,
            "meta": {"chain_policy": {"milestone_base_sha": base_sha}},
        },
        events_body=json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 0,
            "current_plan_name": plan_name,
            "last_state": "authority_divergence",
            "pr_state": "",
            "completed": [],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        (
            "[chain] completion guard blocked sprint-01-safe-compiler-foundation: "
            f"no semantic diff from milestone_base_sha {base_sha} to local HEAD; "
            "no typed no-op completion waiver found\n"
        )
        * 3,
        encoding="utf-8",
    )

    payload = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="stopped",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_COMPLETION_GUARD_REPEATS": "3"},
    )

    assert payload["CHAIN_HEALTH_STATUS"] == "ok"
    assert payload["CHAIN_HEALTH_ARTIFACT_PATH"] == ""


def test_chain_health_status_detects_stuck_nonterminal_across_ticks() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 4,
            "current_plan_name": "demo-plan",
            "last_state": "authority_divergence",
            "pr_state": "merged",
            "completed": [{"label": "m1"}],
        },
    )
    (ws / ".megaplan" / "cloud-chain-demo.log").parent.mkdir(parents=True, exist_ok=True)
    (ws / ".megaplan" / "cloud-chain-demo.log").write_text(
        "[chain] completion guard blocked demo: still blocked\n",
        encoding="utf-8",
    )

    first = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )
    second = _run_chain_health(
        ws,
        marker,
        repair_dir,
        health="alive",
        env_overrides={"CLOUD_WATCHDOG_CHAIN_STUCK_TICKS": "2"},
    )

    assert first["CHAIN_HEALTH_STATUS"] == "ok"
    assert second["CHAIN_HEALTH_STATUS"] == "chain_stuck"
    artifact = json.loads(Path(second["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_stuck_nonterminal"
    assert artifact["details"]["stuck_ticks"] == 2
    assert artifact["chain_state_summary"]["last_state"] == "authority_divergence"


def test_chain_health_status_detects_busy_no_advance_across_ticks() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    repair_dir = tmp / "repair-data"
    plan_name = "demo-plan"
    _write_plan(
        ws / ".megaplan" / "plans" / plan_name,
        {"current_state": "planning", "iteration": 1},
        events_body=json.dumps({"kind": "phase_started", "phase": "execute"}) + "\n",
    )
    _write_chain_state(
        ws / ".megaplan" / "plans" / ".chains" / "chain-demo.json",
        {
            "current_milestone_index": 2,
            "current_plan_name": plan_name,
            "last_state": "planning",
            "pr_state": "open",
            "completed": [{"label": "m1"}],
        },
    )

    assert _run_chain_health(ws, marker, repair_dir, env_overrides={"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"})["CHAIN_HEALTH_STATUS"] == "ok"
    events_path = ws / ".megaplan" / "plans" / plan_name / "events.ndjson"
    events_path.write_text(
        events_path.read_text(encoding="utf-8") + json.dumps({"kind": "phase_end", "phase": "execute"}) + "\n",
        encoding="utf-8",
    )
    assert _run_chain_health(ws, marker, repair_dir, env_overrides={"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"})["CHAIN_HEALTH_STATUS"] == "ok"
    events_path.write_text(
        events_path.read_text(encoding="utf-8") + json.dumps({"kind": "phase_started", "phase": "review"}) + "\n",
        encoding="utf-8",
    )
    third = _run_chain_health(
        ws,
        marker,
        repair_dir,
        env_overrides={"CLOUD_WATCHDOG_CHAIN_NO_ADVANCE_TICKS": "2"},
    )

    assert third["CHAIN_HEALTH_STATUS"] == "chain_no_advance"
    artifact = json.loads(Path(third["CHAIN_HEALTH_ARTIFACT_PATH"]).read_text(encoding="utf-8"))
    assert artifact["issue_kind"] == "chain_no_advance"
    assert artifact["details"]["no_advance_ticks"] == 2
    assert artifact["chain_state_summary"]["current_milestone_index"] == 2


def test_plan_progress_stall_status_is_wired_into_launch_chain_tick() -> None:
    text = _wrapper("arnold-watchdog")

    assert "plan_progress_stall_status()" in text
    assert 'stall_health="$(plan_progress_stall_status "$workspace" "$run_kind" "$plan_name")"' in text
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


def test_watchdog_plan_helpers_use_named_single_plan_in_mixed_workspace() -> None:
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"
    marker = tmp / "markers"
    target = ws / ".megaplan" / "plans" / "target-plan"
    unrelated = ws / ".megaplan" / "plans" / "newer-unrelated"
    _write_plan(
        target,
        {
            "iteration": 1,
            "current_state": "planning",
            "active_step": {"phase": "plan", "attempt": 0},
            "history": [],
        },
        plan_v_bodies={"plan_v1.md": "target"},
        events_body="{}\n",
    )
    _write_plan(
        unrelated,
        {
            "iteration": 25,
            "current_state": "blocked",
            "active_step": {"phase": "execute", "attempt": 12},
            "latest_failure": {
                "kind": "phase_failed",
                "phase": "execute",
                "message": "unrelated failure should not be inspected",
            },
            "history": [{"step": "execute", "result": "error"}],
        },
        plan_v_bodies={"plan_v1.md": "unrelated"},
        events_body="{}\n",
    )
    old_ts = time.time() - 600
    new_ts = time.time()
    os.utime(target / "state.json", (old_ts, old_ts))
    os.utime(unrelated / "state.json", (new_ts, new_ts))

    assert _run_phase(ws, "plan", "target-plan") == "ok"
    assert _run_stall(ws, marker, run_kind="plan", plan_name="target-plan") == "ok"
    assert _run_phase(ws).startswith("phase_failure:newer-unrelated")
    assert _run_stall(ws, marker).startswith("progress_stall:newer-unrelated")


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
    assert 'REPAIR_DATA_DIR="${MEGAPLAN_AUDIT_REPAIR_DATA_DIR:-$MARKER_DIR/repair-data}"' in text
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
    assert "You are auditing a cloud megaplan SESSION, not just one plan." in text
    assert "chain log line numbers" in text
    assert "Live failure vs stale state" in text
    assert "Gate resolvability" in text
    assert "stale_state_evidence" in text
    assert "latest_failure_is_stale" in text
    assert "stale_block_replay" in text
    assert "between_milestone_cycling" in text
    assert "STALE" in text
    assert "INEFFICIENT" in text


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


def _extract_auditor_gather_program() -> str:
    text = _wrapper("arnold-progress-auditor")
    marker = "python3 - \"$WORKLIST\" \"$GATHER_DIR\" \"$AUDIT_WINDOW_HOURS\" \"$ARNOLD_SRC\" \"$stall_summary\" <<'PY'"
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
    gather_prog = _extract_auditor_gather_program()
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
    plan_marker_ws = workspace_root / "single-plan-marker-workspace"
    for ws in (chain_ws, bootstrap_ws, done_ws, plan_marker_ws):
        (ws / ".megaplan" / "plans").mkdir(parents=True)

    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    (marker_dir / "chain-session.json").write_text(
        json.dumps({"session": "chain-session", "workspace": str(chain_ws), "updated_at": _iso_hours_ago(0.2)}),
        encoding="utf-8",
    )
    (marker_dir / "single-plan-session.json").write_text(
        json.dumps(
            {
                "session": "single-plan-session",
                "workspace": str(plan_marker_ws),
                "run_kind": "plan",
                "plan_name": "target-plan",
                "updated_at": _iso_hours_ago(0.2),
            }
        ),
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
    write_recent_plan(plan_marker_ws, "target-plan", state_recent=False, events_recent=False)
    write_recent_plan(plan_marker_ws, "stale-unrelated", state_recent=False, events_recent=False)
    write_recent_plan(arnold_src, "should-not-scan", state_recent=True)

    discover_bin = tmp_path / "discover_stub.sh"
    discover_bin.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        f"bootstrap-session\t{bootstrap_ws}\t.megaplan/initiatives/bootstrap/briefs/bootstrap.md\tplan\tm1-bootstrap\tignored\n"
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
    assert (str(plan_marker_ws), "target-plan") in observed
    assert observed[(str(plan_marker_ws), "target-plan")] == {"marker"}
    assert (str(plan_marker_ws), "stale-unrelated") not in observed
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

    gather_prog = _extract_auditor_gather_program()
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


def test_auditor_gather_includes_chain_repair_stderr_and_user_action_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "m7-demo"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    state = {
        "name": plan_name,
        "iteration": 21,
        "current_state": "finalized",
        "active_step": {"phase": "execute", "attempt": 2},
        "latest_failure": {
            "kind": "phase_failed",
            "message": "phase 'execute' internal_error",
            "phase": "execute",
            "recorded_at": _iso_hours_ago(2.0),
            "metadata": {
                "exit_code": 2,
                "stderr": "__main__.py: error: unrecognized arguments: --confirm-destructive --user-approved",
            },
        },
        "last_gate": {"recommendation": "PASS"},
        "meta": {
            "weighted_scores": [8.0],
            "plan_deltas": [1.0],
            "significant_counts": [1],
            "user_action_resolutions": {
                "ua-02-cleanup-policy": {"state": "satisfied", "decision": "proceed"}
            },
        },
        "history": [
            {
                "step": "execute",
                "result": "blocked",
                "timestamp": _iso_hours_ago(1.0),
                "duration_ms": 0,
                "artifact_hash": "sha256:stale-block",
                "output_file": "execution.json",
            },
            {
                "step": "execute",
                "result": "blocked",
                "timestamp": _iso_hours_ago(0.5),
                "duration_ms": 0,
                "artifact_hash": "sha256:stale-block",
                "output_file": "execution.json",
            },
        ],
    }
    _write_plan(
        plan_dir,
        state,
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "kind": "phase_end",
                        "phase": "execute",
                        "ts_utc": _iso_hours_ago(1.5),
                        "payload": {"phase": "execute", "exit_kind": "success"},
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "kind": "gate",
                        "phase": "gate",
                        "ts_utc": _iso_hours_ago(1.0),
                        "payload": {"recommendation": "PROCEED"},
                    }
                ),
            ]
        )
        + "\n",
    )
    (plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "user_actions": [
                    {
                        "id": "ua-01-reclassify-deletion-targets",
                        "phase": "before_execute",
                        "blocks_task_ids": ["m7-06-runtime-deletion-target-purge"],
                        "rationale": "Maintainer must confirm authoritative deletion targets.",
                    },
                    {
                        "id": "ua-02-cleanup-policy",
                        "phase": "before_execute",
                        "blocks_task_ids": ["m7-07-pipeline-deletion-target-purge"],
                        "rationale": "Cleanup policy choice.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "user_actions.md").write_text(
        "# User Actions\n\n"
        "- **ua-01-reclassify-deletion-targets**: Confirm deletion targets.\n"
        "- **ua-02-cleanup-policy**: Cleanup policy.\n",
        encoding="utf-8",
    )

    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    (chain_dir / "chain-demo.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 6,
                "current_plan_name": plan_name,
                "last_state": "awaiting_human",
                "pr_number": 122,
                "pr_state": "open",
                "completed": [
                    {
                        "label": "m6-installed-artifacts",
                        "plan": "m6-demo",
                        "status": "done",
                        "pr_number": 121,
                        "pr_state": "merged",
                        "full_suite_backstop": {
                            "status": "failed",
                            "blocks": False,
                            "failed": 3,
                            "delta_computed": True,
                        },
                    }
                ],
                "events": [{"msg": "milestone m7 starting"}, {"msg": "awaiting_human"}],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo-session.log").write_text(
        "\n".join(
            [
                "[chain] milestone m7 starting",
                "[chain] terminal state reached: done",
                "[chain] status: stopped reason=milestone m7 ended awaiting_human",
                "[chain] milestone m7 starting",
                "[chain] terminal state reached: done",
                "[chain] status: stopped reason=milestone m7 ended awaiting_human",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    repair_data_dir = tmp_path / "repair-data"
    repair_data_dir.mkdir()
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "outcome": "repairing",
                "iterations": [
                    {
                        "i": 1,
                        "mechanical_launch": "failed:awaiting_human",
                        "chain_state_summary": {"current_plan_name": plan_name, "last_state": "awaiting_human"},
                        "plan_latest_failure": {
                            "kind": "phase_failed",
                            "message": "phase 'execute' internal_error",
                            "metadata": {"stderr": "__main__.py: error: unrecognized arguments: --confirm-destructive"},
                        },
                    },
                    {
                        "i": 2,
                        "mechanical_launch": "failed:awaiting_human",
                        "chain_state_summary": {"current_plan_name": plan_name, "last_state": "awaiting_human"},
                        "plan_latest_failure": {
                            "kind": "phase_failed",
                            "message": "phase 'execute' internal_error",
                            "metadata": {"stderr": "__main__.py: error: unrecognized arguments: --confirm-destructive"},
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "demo-session",
                "kind": "chain",
                "remote_spec": str(workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"),
                "launch_command": "python3 -P -m arnold_pipelines.megaplan chain start --spec demo",
                "log": str(workspace / ".megaplan" / "cloud-chain-demo-session.log"),
                "sources": ["marker"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    env = dict(os.environ)
    env["MEGAPLAN_AUDIT_REPAIR_DATA_DIR"] = str(repair_data_dir)
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected chain-level signals to produce a suspicious finding"
    finding = findings[0]
    assert finding["session_header"]["kind"] == "chain"
    assert finding["chain_log"]["path"].endswith("cloud-chain-demo-session.log")
    assert "L6: [chain] status: stopped" in finding["chain_log"]["tail"]
    assert any(item["signature"] == "awaiting_human" and item["count"] == 2 for item in finding["chain_log"]["repetition_summary"])
    assert finding["chain_state_summary"]["current"]["last_state"] == "awaiting_human"
    assert finding["chain_state_summary"]["current"]["completed_count"] == 1
    assert finding["repair_data_summary"]["iteration_count"] == 2
    assert finding["repair_data_summary"]["repeated_failure_signatures"][0]["count"] == 2
    assert "unrecognized arguments" in finding["plan_latest_failure"]["metadata"]["stderr"]
    stale = finding["stale_state_evidence"]
    assert stale["latest_failure_is_stale"] is True
    assert stale["last_success_after_failure"]
    assert stale["last_success_after_failure_event"]["kind"] == "gate"
    assert stale["stale_block_replay"] is True
    assert stale["stale_block_replay_hash"] == "sha256:stale-block"
    assert finding["latest_failure_is_stale"] is True
    assert finding["stale_block_replay"] is True
    user_action_context = finding["user_action_context"]
    assert "ua-01-reclassify-deletion-targets" in user_action_context["user_actions_md"]
    assert [item["id"] for item in user_action_context["unresolved_user_actions"]] == ["ua-01-reclassify-deletion-targets"]
    reasons = " ".join(finding["reasons"])
    assert "chain last_state=awaiting_human" in reasons
    assert "chain log repeats" in reasons
    assert "repair data has 2 repair iterations" in reasons
    assert "unresolved user actions" in reasons
    assert "latest_failure is stale" in reasons
    assert "stale block replay" in reasons


def test_auditor_gather_flags_plan_stale_block_without_chain_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "single-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "name": plan_name,
            "iteration": 4,
            "current_state": "blocked",
            "active_step": None,
            "latest_failure": {
                "kind": "execution_blocked",
                "message": "blocked replay",
                "phase": "execute",
            },
            "last_gate": {"recommendation": "PASS"},
            "meta": {"weighted_scores": [8.0], "plan_deltas": [1.0], "significant_counts": [1]},
            "history": [
                {
                    "step": "execute",
                    "result": "blocked",
                    "timestamp": _iso_hours_ago(1.0),
                    "duration_ms": 0,
                    "artifact_hash": "sha256:plan-stale",
                    "output_file": "execution.json",
                },
                {
                    "step": "execute",
                    "result": "blocked",
                    "timestamp": _iso_hours_ago(0.5),
                    "duration_ms": 0,
                    "artifact_hash": "sha256:plan-stale",
                    "output_file": "execution.json",
                },
            ],
        },
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "single-plan-session",
                "kind": "plan",
                "plan_name": plan_name,
                "sources": ["marker"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected plan-level stale block replay to produce a finding"
    finding = findings[0]
    assert finding["session_header"]["kind"] == "plan"
    assert finding["chain_log"]["path"] == ""
    assert finding["chain_state_summary"]["current"] == {}
    stale = finding["stale_state_evidence"]
    assert stale["stale_block_replay"] is True
    assert stale["stale_block_replay_hash"] == "sha256:plan-stale"
    assert stale["between_milestone_cycling"] is False
    assert "stale block replay" in " ".join(finding["reasons"])


def test_auditor_gather_flags_between_milestone_cycling(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    plan_name = "m3-demo"
    plan_dir = workspace / ".megaplan" / "plans" / plan_name
    _write_plan(
        plan_dir,
        {
            "name": plan_name,
            "iteration": 3,
            "current_state": "finalized",
            "active_step": None,
            "last_gate": {"recommendation": "PASS"},
            "meta": {"weighted_scores": [8.0], "plan_deltas": [1.0], "significant_counts": [1]},
            "history": [],
        },
        plan_v_bodies={"plan_v1.md": "v1"},
        events_body="{}\n",
    )

    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True)
    (chain_dir / "chain-demo.json").write_text(
        json.dumps(
            {
                "current_milestone_index": 2,
                "current_plan_name": plan_name,
                "last_state": "stopped",
                "completed": [
                    {"label": "m1", "plan": "m1-demo", "status": "done"},
                    {"label": "m2", "plan": "m2-demo", "status": "done"},
                ],
                "milestones": [{"label": "m1"}, {"label": "m2"}, {"label": "m3"}],
                "events": [{"msg": "m1 done"}, {"msg": "m2 done"}],
            }
        ),
        encoding="utf-8",
    )
    log_path = workspace / ".megaplan" / "cloud-chain-demo-session.log"
    log_path.write_text(
        "\n".join(
            [
                "[chain] milestone m1 starting",
                "[chain] terminal state reached: done",
                "[chain] status: stopped reason=completed one milestone: m1",
                "[chain] milestone m2 starting",
                "[chain] terminal state reached: done",
                "[chain] status: stopped reason=completed one milestone: m2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    gather_dir = tmp_path / "gather"
    gather_dir.mkdir()
    worklist = tmp_path / "worklist.jsonl"
    worklist.write_text(
        json.dumps(
            {
                "workspace": str(workspace),
                "plan": plan_name,
                "session": "demo-session",
                "kind": "chain",
                "log": str(log_path),
                "sources": ["marker"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gather_path = gather_dir / "gather.py"
    gather_path.write_text(_extract_auditor_gather_program(), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(gather_path), str(worklist), str(gather_dir), "6", str(tmp_path), "none"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    findings = json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))["findings"]
    assert findings, "expected between-milestone cycling to produce a finding"
    finding = findings[0]
    stale = finding["stale_state_evidence"]
    assert stale["between_milestone_cycling"] is True
    assert stale["one_milestone_stop_cycle_count"] == 2
    assert finding["between_milestone_cycling"] is True
    assert "between-milestone cycling" in " ".join(finding["reasons"])


def test_arnold_progress_auditor_produces_evidence_cited_report_via_mocked_deepseek(tmp_path) -> None:
    report = _run_auditor_with_mocked_deepseek(tmp_path)
    finding = report["findings"][0]
    # The finding cites specific plan_v + gate evidence.
    combined = " ".join(finding["reasons"]) + " " + finding.get("hypothesis", "")
    assert "plan_v refreshed" in combined
    assert "gate=ITERATE/blocked" in combined
    assert "hypothesis:" in finding["hypothesis"]
