from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.cloud.test_watchdog_wrappers import REPO_ROOT, _extract_repair_program


def test_repair_loop_classifies_terminal_plan_plus_initialized_chain_as_stale_state(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir(parents=True)

    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    session_marker_dir = workspace / ".megaplan" / "cloud-sessions"
    session_marker_dir.mkdir(parents=True, exist_ok=True)
    (session_marker_dir / "repair-data").mkdir(parents=True, exist_ok=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones:\n  - label: m1\n", encoding="utf-8")

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "current_state": "",
                "last_state": "initialized",
                "current_milestone_index": 0,
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo-session.log").write_text(
        "[chain] terminal state reached: done\n",
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        json.dumps({"name": "demo-plan", "current_state": "done", "latest_failure": None}),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

    marker_payload = {
        "session": "demo-session",
        "workspace": str(workspace),
        "run_kind": "chain",
        "remote_spec": str(spec_path),
        "plan_name": "",
    }
    (marker_dir / "demo-session.json").write_text(json.dumps(marker_payload), encoding="utf-8")
    (session_marker_dir / "demo-session.json").write_text(
        json.dumps(marker_payload),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    prog_path = tmp_path / "_collect_failure_context.py"
    prog_path.write_text(program, encoding="utf-8")
    env = dict(os.environ)
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(repair_data_dir)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [sys.executable, str(prog_path), str(workspace), "demo-session", "chain", ""],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "stale_state"
    assert payload["stale_state"]["classification"] == "NO LATEST FAILURE"
    stale_evidence = payload["resolver_output"]["stale_evidence"]
    assert any(item["kind"] == "stale_chain_state_after_terminal_plan" for item in stale_evidence)


def test_repair_loop_classifies_dead_execute_active_step_without_latest_failure_as_stale_state(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir(parents=True)

    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    session_marker_dir = workspace / ".megaplan" / "cloud-sessions"
    session_marker_dir.mkdir(parents=True, exist_ok=True)
    (session_marker_dir / "repair-data").mkdir(parents=True, exist_ok=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones:\n  - label: m1\n", encoding="utf-8")

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "current_state": "",
                "last_state": "finalized",
                "current_milestone_index": 0,
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo-session.log").write_text(
        "[chain] milestone m1 starting\n",
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "finalized",
                "latest_failure": None,
                "active_step": {"phase": "execute", "worker_pid": -1},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

    marker_payload = {
        "session": "demo-session",
        "workspace": str(workspace),
        "run_kind": "chain",
        "remote_spec": str(spec_path),
        "plan_name": "",
    }
    (marker_dir / "demo-session.json").write_text(json.dumps(marker_payload), encoding="utf-8")
    (session_marker_dir / "demo-session.json").write_text(
        json.dumps(marker_payload),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    prog_path = tmp_path / "_collect_failure_context.py"
    prog_path.write_text(program, encoding="utf-8")
    env = dict(os.environ)
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(repair_data_dir)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [sys.executable, str(prog_path), str(workspace), "demo-session", "chain", ""],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "stale_state"
    assert payload["stale_state"]["classification"] == "NO LATEST FAILURE"
    stale_evidence = payload["resolver_output"]["stale_evidence"]
    assert any(item["kind"] == "stale_active_step_dead_pid" for item in stale_evidence)


def test_repair_loop_detects_executed_plan_chain_mismatch_without_latest_failure(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    marker_dir = tmp_path / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir(parents=True)

    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    chain_dir.mkdir(parents=True, exist_ok=True)
    plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    session_marker_dir = workspace / ".megaplan" / "cloud-sessions"
    session_marker_dir.mkdir(parents=True, exist_ok=True)
    (session_marker_dir / "repair-data").mkdir(parents=True, exist_ok=True)
    spec_path = workspace / ".megaplan" / "initiatives" / "demo" / "chain.yaml"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("milestones:\n  - label: m1\n", encoding="utf-8")

    digest = hashlib.sha1(str(spec_path.resolve()).encode("utf-8")).hexdigest()[:12]
    (chain_dir / f"{spec_path.stem}-{digest}.json").write_text(
        json.dumps(
            {
                "current_plan_name": "demo-plan",
                "current_state": "",
                "last_state": "blocked",
                "current_milestone_index": 0,
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    (workspace / ".megaplan" / "cloud-chain-demo-session.log").write_text(
        "[chain] milestone m1 starting\n",
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo-plan",
                "current_state": "executed",
                "latest_failure": None,
                "resume_cursor": {"phase": "review", "retry_strategy": "manual_review"},
                "active_step": {"phase": "review", "worker_pid": -1},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

    marker_payload = {
        "session": "demo-session",
        "workspace": str(workspace),
        "run_kind": "chain",
        "remote_spec": str(spec_path),
        "plan_name": "",
    }
    (marker_dir / "demo-session.json").write_text(json.dumps(marker_payload), encoding="utf-8")
    (session_marker_dir / "demo-session.json").write_text(
        json.dumps(marker_payload),
        encoding="utf-8",
    )

    program = _extract_repair_program(
        "collect_failure_context_json",
        "python3 - \"$workspace\" \"$session\" \"$run_kind\" \"$plan_name\" <<'PY'",
    )
    prog_path = tmp_path / "_collect_failure_context.py"
    prog_path.write_text(program, encoding="utf-8")
    env = dict(os.environ)
    env["CLOUD_WATCHDOG_MARKER_DIR"] = str(marker_dir)
    env["CLOUD_WATCHDOG_REPAIR_DATA_DIR"] = str(repair_data_dir)
    env["PYTHONPATH"] = f"{REPO_ROOT}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [sys.executable, str(prog_path), str(workspace), "demo-session", "chain", ""],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["failure_classification"] == "stale_state"
    assert payload["state_mismatch"]["detected"] is True
    assert payload["state_mismatch"]["plan_state"] == "executed"
    assert payload["state_mismatch"]["chain_last_state"] == "blocked"
