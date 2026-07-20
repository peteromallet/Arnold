"""Tests for arnold-progress-auditor gather/report logic.

Covers:
- green_checks tracking for inspected-but-healthy plans
- JSON report shape with green_checks (including empty findings)
- Markdown report output with green_checks
"""

from __future__ import annotations

import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import feature_flags
from arnold_pipelines.megaplan.cloud.redact import REDACTION

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
SYSTEMD_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "systemd"


def _wrapper(name: str) -> str:
    return (WRAPPER_DIR / name).read_text(encoding="utf-8")


def test_installed_auditor_trampoline_honors_deployed_source_root() -> None:
    text = _wrapper("arnold-progress-auditor")
    hot_env_at = text.index(". /workspace/.cloud-hot-env")
    source_root_at = text.index('AUDITOR_SOURCE_ROOT="${MEGAPLAN_AUDIT_ARNOLD_SRC:-')
    reexec_at = text.index('exec "$SOURCE_AUDITOR" "$@"')
    assert hot_env_at < source_root_at < reexec_at
    assert 'CLOUD_WATCHDOG_ARNOLD_SRC:-/workspace/arnold' in text


def test_auditor_gather_prefers_deployed_source_over_caller_cwd() -> None:
    program = _extract_gather_program()
    cwd_at = program.index("sys.path.insert(0, str(pathlib.Path.cwd()))")
    deployed_source_at = program.index("sys.path.insert(0, arnold_src)")

    assert cwd_at < deployed_source_at


def _systemd_file(name: str) -> str:
    return (SYSTEMD_DIR / name).read_text(encoding="utf-8")


def _extract_report_assembler() -> str:
    """Extract the final report-assembly Python program from the auditor wrapper."""
    text = _wrapper("arnold-progress-auditor")
    # The report assembler is the last python3 - ... <<'PY' block
    marker = (
        'python3 - "$GATHER_DIR/findings.json" "$JSON_OUT" "$MD_OUT" '
        '"$REPORT_LOG" "$TS" "$AUDIT_MUTATION_AUTHORIZED_FLAG" '
        '"$AUDIT_LAUNCH_ATTEMPTED" "$RECOVERY_EVIDENCE" '
        '"$AUDIT_CODEX_MODEL" <<\'PY\''
    )
    py_start = text.index(marker)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _extract_gather_program() -> str:
    """Extract the evidence-gathering Python program (the one that produces findings.json)."""
    text = _wrapper("arnold-progress-auditor")
    # The gather program is the second big python3 block (after the worklist builder).
    # It takes "$WORKLIST" "$GATHER_DIR" "$AUDIT_WINDOW_HOURS" "$ARNOLD_SRC" "$stall_summary"
    marker = 'python3 - "$WORKLIST" "$GATHER_DIR" "$AUDIT_WINDOW_HOURS" "$ARNOLD_SRC" "$stall_summary" <<\'PY\''
    py_start = text.index(marker)
    py_start = text.index("\n", py_start) + 1
    py_end = text.index("\nPY\n", py_start)
    return text[py_start:py_end]


def _load_superfixer_cycle_functions() -> dict[str, object]:
    text = _wrapper("arnold-progress-auditor")
    start = text.index("def _superfixer_cycle_evidence(ev):")
    end = text.index("\ndef _meta_repair_gap_is_primary", start)
    namespace: dict[str, object] = {
        "_chain_state_looks_nonterminal": lambda chain: bool(chain),
    }
    exec(text[start:end], namespace)
    return namespace


def _wbc_superfixer_cycle_evidence() -> dict[str, object]:
    return {
        "resolver_state": {"canonical_state": "MACHINE_ACTION_REQUIRED"},
        "repair_custody_summary": {
            "accepted_unclaimed_request_ids": ["7473fa42"],
            "request_status_counts": {"accepted": 1},
            "claim_count": 0,
            "attempt_count": 0,
            "claim_retry_counts": {"7473fa42": 2},
            "claim_alert_request_ids": [],
            "retry_budget": {"claim_retries_remaining": 1},
        },
        "repair_data_summary": {
            "exists": True,
            "outcome": "repair_exhausted",
            "mtime_age_min": 180,
        },
        "meta_repair_summary": {
            "meta_record_count": 0,
            "meta_run_log_count": 0,
            "failed_meta_run_count": 0,
            "failed_meta_record_count": 0,
        },
        "current_target": {"tmux_process": {"live_status": "stopped"}},
        "active_step_liveness": {
            "present": True,
            "worker_pid_alive": False,
        },
        "chain_state_summary": {
            "current": {
                "last_state": "blocked",
                "completed_count": 0,
                "total_milestones": 4,
            }
        },
        "meta_repair_refs": [],
        "prior_watchdog_report_refs": [],
    }


def test_superfixer_cycle_detects_wbc_accepted_unclaimed_exhaustion() -> None:
    namespace = _load_superfixer_cycle_functions()
    evidence = _wbc_superfixer_cycle_evidence()

    reason = namespace["_stale_l1_l2_cycle_reason"](evidence)

    assert reason.startswith("stale_l1_l2_cycle:")
    projected = evidence["deterministic_superfixer_evidence"]
    assert projected["actionable"] is True
    assert projected["accepted_unclaimed_count"] == 1
    assert projected["claim_count"] == 0
    assert projected["attempt_count"] == 0
    assert projected["runner_dead"] is True
    assert projected["absent_or_stale_l2"] is True


def test_superfixer_cycle_excludes_typed_human_gate() -> None:
    namespace = _load_superfixer_cycle_functions()
    evidence = _wbc_superfixer_cycle_evidence()
    evidence["resolver_state"] = {"canonical_state": "HUMAN_ACTION_REQUIRED"}

    reason = namespace["_stale_l1_l2_cycle_reason"](evidence)

    assert reason == ""
    projected = evidence["deterministic_superfixer_evidence"]
    assert projected["actionable"] is False
    assert projected["excluded_typed_human_gate"] is True


def test_superfixer_cycle_fails_closed_on_unknown_custody_evidence() -> None:
    namespace = _load_superfixer_cycle_functions()
    evidence = _wbc_superfixer_cycle_evidence()
    evidence["repair_custody_summary"]["projection_error"] = "runtime skew"

    reason = namespace["_stale_l1_l2_cycle_reason"](evidence)

    assert reason.startswith("broken_superfixer_unknown_evidence:")
    projected = evidence["deterministic_superfixer_evidence"]
    assert projected["actionable"] is False
    assert projected["unknown_evidence"] is True


def _extract_gather_function(name: str, next_name: str) -> str:
    text = _extract_gather_program()
    start = text.index(f"def {name}(")
    end = text.index(f"\ndef {next_name}(", start)
    return text[start:end]


def test_deterministic_phase_history_surfaces_structural_retry_loop() -> None:
    program = _extract_gather_program()
    start = program.index("def _deterministic_phase_history_evidence(")
    end = program.index("\ndef _event_seq(", start)
    namespace = {
        "re": __import__("re"),
        "cutoff": datetime(2026, 7, 13, 16, 0, tzinfo=timezone.utc),
        "_parse_iso": lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
    }
    exec(program[start:end], namespace)
    history = [
        {
            "step": "gate",
            "result": "error",
            "message": "missing_required at /north_star_actions",
            "timestamp": f"2026-07-13T16:0{index}:00Z",
        }
        for index in range(3)
    ]

    evidence = namespace["_deterministic_phase_history_evidence"](history)

    assert evidence["count"] == 3
    assert evidence["phase"] == "gate"
    assert evidence["source"] == "state.history"


def _extract_auditor_function(name: str) -> str:
    text = _wrapper("arnold-progress-auditor")
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _extract_recovery_assembler() -> str:
    text = _wrapper("arnold-progress-auditor")
    marker = '"$watchdog_rc" "$enabled" "$AUDIT_CODEX_MODEL" <<\'PY\''
    start = text.index(marker)
    start = text.index("\n", start) + 1
    end = text.index("\nPY\n", start)
    return text[start:end]


def test_scheduled_recovery_uses_shared_advancement_policy(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    report = tmp_path / "watchdog.json"
    output = tmp_path / "recovery.json"
    before.write_text(json.dumps({"generated_at": "before"}), encoding="utf-8")
    after.write_text(
        json.dumps(
            {
                "generated_at": "after",
                "sessions": [
                    {
                        "session": "manual",
                        "status": "attention",
                        "should_run": True,
                        "workspace": str(tmp_path / "manual"),
                        "advancement": {
                            "action": "await_human",
                            "automatic": False,
                            "gate": "security_approval",
                        },
                    },
                    {
                        "session": "terminal",
                        "status": "attention",
                        "should_run": True,
                        "workspace": str(tmp_path / "terminal"),
                        "advancement": {
                            "action": "reconcile_terminal",
                            "automatic": True,
                            "gate": None,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    report.write_text(
        json.dumps(
            {
                "timestamp_utc": "now",
                "items": [
                    {"session": "manual", "status": "needs_human"},
                    {"session": "terminal", "status": "needs_human"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _extract_recovery_assembler(),
            str(before),
            str(after),
            str(report),
            str(output),
            "0",
            "1",
            "gpt-5.6-sol",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    decisions = {
        item["session"]: item
        for item in json.loads(output.read_text(encoding="utf-8"))["decisions"]
    }
    assert decisions["manual"]["disposition"] == "human_gated"
    assert decisions["manual"]["decision"] == "await_human"
    assert decisions["terminal"]["decision"] == "reconcile_terminal"
    assert decisions["terminal"]["disposition"] == "eligible_missing_runner"


def _run_gather_program(
    worklist_entries: list[dict],
    tmp_path: Path,
    *,
    arnold_src: Path | None = None,
    extra_env: dict[str, str] | None = None,
    cwd: Path | None = None,
    window_hours: str = "6",
    stall_summary: str = "none",
) -> dict:
    """Run the gather program with synthetic worklist data and return findings.json."""
    program = _extract_gather_program()
    prog_path = tmp_path / "_gather_program.py"
    prog_path.write_text(program, encoding="utf-8")

    worklist_path = tmp_path / "worklist.jsonl"
    gather_dir = tmp_path / "gather"
    gather_dir.mkdir(parents=True, exist_ok=True)
    worklist_path.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in worklist_entries),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["ARNOLD_REPAIR_QUEUE_ROOT"] = str(tmp_path / ".megaplan" / "repair-queue")
    # Synthetic sessions may intentionally reuse a production incident name;
    # never let live marker or meta-run evidence alter the deterministic fixture.
    env["MEGAPLAN_AUDIT_MARKER_DIR"] = str(tmp_path / ".megaplan" / "cloud-sessions")
    env["MEGAPLAN_AUDIT_META_RUN_DIR"] = str(tmp_path / ".megaplan" / "meta-runs")
    env["MEGAPLAN_AUDIT_INSTALLED_WRAPPER"] = str(
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor"
    )
    if extra_env:
        env.update(extra_env)

    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            str(worklist_path),
            str(gather_dir),
            window_hours,
            str(arnold_src or REPO_ROOT),
            stall_summary,
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(cwd or REPO_ROOT),
        env=env,
    )
    assert result.returncode == 0, f"gather program failed: {result.stderr}"
    return json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))


def test_gather_detects_deterministic_llm_retry_when_latest_failure_is_empty(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    plan_dir = workspace / ".megaplan" / "plans" / "gate-loop"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "gate-loop",
                "current_state": "critiqued",
                "iteration": 1,
                "latest_failure": None,
                "history": [],
            }
        ),
        encoding="utf-8",
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    message = (
        "worker_structural_audit_failed: model output structural audit failed: "
        "missing_required at /north_star_actions"
    )
    events = [
        {
            "kind": "llm_call_error",
            "phase": "gate",
            "payload": {"message": message},
            "ts_utc": timestamp,
            "seq": seq,
        }
        for seq in range(1, 5)
    ]
    (plan_dir / "events.ndjson").write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    payload = _run_gather_program(
        [
            {
                "workspace": str(workspace),
                "plan": "gate-loop",
                "session": "gate-loop-session",
                "kind": "plan",
                "sources": ["fixture"],
            }
        ],
        tmp_path,
    )

    assert len(payload["findings"]) == 1
    finding = payload["findings"][0]
    assert finding["latest_failure_kind"] is None
    assert finding["deterministic_retry_evidence"]["count"] == 4
    assert finding["deterministic_retry_evidence"]["phase"] == "gate"
    assert any(
        reason.startswith("deterministic_retry_exhaustion:")
        for reason in finding["reasons"]
    )
    assert payload["green_checks"] == []
    patterns = payload["root_cause_patterns"]["repeated_failure_signatures"]
    assert patterns[0]["total_occurrences"] == 4
    assert patterns[0]["affected_plans"] == ["gate-loop"]


def test_gather_report_only_does_not_write_audited_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    plan = "read-only-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan, "current_state": "executing"}),
        encoding="utf-8",
    )
    (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
    (chain_dir / "chain-read-only.json").write_text(
        json.dumps(
            {
                "current_plan_name": plan,
                "last_state": "executing",
                "chain_complete": False,
                "milestones": [{"label": "m1"}],
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    before = {
        path.relative_to(workspace): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }

    _run_gather_program(
        [
            {
                "workspace": str(workspace),
                "plan": plan,
                "session": "read-only-session",
                "kind": "chain",
            }
        ],
        tmp_path,
    )

    after = {
        path.relative_to(workspace): path.read_bytes()
        for path in workspace.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_gather_flags_liveness_and_repair_churn_without_acceptance(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    session = "green-churn"
    plan = "active-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    marker_dir = tmp_path / ".megaplan" / "cloud-sessions"
    repair_dir = marker_dir / "repair-data"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    repair_dir.mkdir(parents=True)
    now = datetime.now(timezone.utc).isoformat()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan, "current_state": "blocked", "iteration": 7}),
        encoding="utf-8",
    )
    events = [
        {"kind": kind, "phase": "execute", "ts_utc": now, "seq": index}
        for index, kind in enumerate(
            ["llm_token_heartbeat", "state_written", "cost_recorded", "llm_token_heartbeat"],
            start=101,
        )
    ]
    (plan_dir / "events.ndjson").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    (chain_dir / "chain-green.json").write_text(
        json.dumps(
            {
                "current_plan_name": plan,
                "last_state": "blocked",
                "chain_complete": False,
                "milestones": [{"label": "m1"}, {"label": "m2"}],
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    (marker_dir / f"{session}.chain-health.progress.json").write_text(
        json.dumps({"no_advance_ticks": 4, "stuck_ticks": 3, "updated_at": now}),
        encoding="utf-8",
    )
    (repair_dir / f"{session}.repair-data.json").write_text(
        json.dumps({"session": session, "outcome": "running", "iterations": [{"i": 1}]}),
        encoding="utf-8",
    )

    payload = _run_gather_program(
        [{"workspace": str(workspace), "plan": plan, "session": session, "kind": "chain"}],
        tmp_path,
        extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_dir)},
    )

    assert payload["green_checks"] == []
    reasons = payload["findings"][0]["reasons"]
    assert any(reason.startswith("green_with_recent_repair_churn:") for reason in reasons)
    assert any(reason.startswith("liveness_without_acceptance_progress:") for reason in reasons)


def test_gather_flags_deterministic_repair_failure_exhaustion(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    session = "deterministic-repair-loop"
    plan = "active-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    repair_dir = tmp_path / "repair-data"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    repair_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps({"name": plan, "current_state": "executing"}), encoding="utf-8"
    )
    (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
    (chain_dir / "chain-loop.json").write_text(
        json.dumps(
            {
                "current_plan_name": plan,
                "last_state": "blocked",
                "chain_complete": False,
                "milestones": [{"label": "m1"}],
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    repeated = {
        "chain_state_summary": {"current_plan_name": plan, "last_state": "blocked"},
        "plan_latest_failure": {"kind": "phase_failed", "message": "same parse failure"},
    }
    (repair_dir / f"{session}.repair-data.json").write_text(
        json.dumps({"session": session, "outcome": "running", "iterations": [repeated] * 3}),
        encoding="utf-8",
    )

    payload = _run_gather_program(
        [{"workspace": str(workspace), "plan": plan, "session": session, "kind": "chain"}],
        tmp_path,
        extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_dir)},
    )

    assert payload["green_checks"] == []
    assert any(
        reason.startswith("deterministic_failure_exhaustion:")
        for reason in payload["findings"][0]["reasons"]
    )


def test_gather_suppresses_clean_completed_shadow_but_not_session_custody(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    session = "completed-shadow"
    shadow = "m1-done"
    current = "m2-current"
    plan_dir = workspace / ".megaplan" / "plans" / shadow
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps({"name": shadow, "current_state": "done"}), encoding="utf-8"
    )
    (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
    chain_path = chain_dir / "chain-shadow.json"
    chain_path.write_text(
        json.dumps(
            {
                "current_plan_name": current,
                "last_state": "executing",
                "chain_complete": False,
                "milestones": [{"label": "m1"}, {"label": "m2"}],
                "completed": [{"label": "m1", "plan": shadow, "status": "done"}],
            }
        ),
        encoding="utf-8",
    )
    worklist = [{"workspace": str(workspace), "plan": shadow, "session": session, "kind": "chain"}]

    clean = _run_gather_program(worklist, tmp_path)

    assert clean["findings"] == []
    assert clean["green_checks"][0]["suppression"]["reason"] == (
        "completed_plan_shadow_plan_local_evidence_suppressed"
    )
    repair_dir = tmp_path / "repair-data"
    repair_dir.mkdir()
    (repair_dir / f"{session}.repair-data.json").write_text(
        json.dumps(
            {
                "session": session,
                "outcome": "running",
                "current_attempt_id": "",
                "attempt_ids": [],
                "iterations": [],
            }
        ),
        encoding="utf-8",
    )

    suspicious = _run_gather_program(
        worklist,
        tmp_path,
        extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_dir)},
    )

    assert suspicious["green_checks"] == []
    assert any(
        reason.startswith("repair_data_ghost_running:")
        for reason in suspicious["findings"][0]["reasons"]
    )


def test_gather_promotes_installed_wrapper_drift_and_ignores_terminal_history(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    plan = "current-plan"
    plan_dir = workspace / ".megaplan" / "plans" / plan
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    plan_dir.mkdir(parents=True)
    chain_dir.mkdir(parents=True)
    state_path = plan_dir / "state.json"
    state_path.write_text(json.dumps({"name": plan, "current_state": "executing"}), encoding="utf-8")
    (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
    chain_path = chain_dir / "chain-wrapper.json"
    chain_path.write_text(
        json.dumps(
            {
                "current_plan_name": plan,
                "last_state": "executing",
                "chain_complete": False,
                "milestones": [{"label": "m1"}],
                "completed": [],
            }
        ),
        encoding="utf-8",
    )
    installed = tmp_path / "installed-auditor"
    installed.write_text("older wrapper\n", encoding="utf-8")
    worklist = [{"workspace": str(workspace), "plan": plan, "session": "wrapper-drift", "kind": "chain"}]

    active = _run_gather_program(
        worklist,
        tmp_path,
        extra_env={"MEGAPLAN_AUDIT_INSTALLED_WRAPPER": str(installed)},
    )

    assert active["green_checks"] == []
    assert any(
        reason.startswith("installed_wrapper_drift:")
        for reason in active["findings"][0]["reasons"]
    )
    assert active["findings"][0]["auditor_wrapper_runtime"]["installed_matches_source"] is False
    report, _markdown = _run_report_assembler(active, tmp_path)
    assert report["auditor_runtime_receipt"]["installed_matches_source"] is False
    assert report["dispatch_summary"]["mode"] == "report_only"
    assert report["dispatch_summary"]["repair_dispatched"] is False
    assert report["dispatch_summary"]["file_edit_performed"] is False

    state_path.write_text(json.dumps({"name": plan, "current_state": "done"}), encoding="utf-8")
    chain_path.write_text(
        json.dumps(
            {
                "current_plan_name": plan,
                "last_state": "done",
                "chain_complete": True,
                "pr_state": "merged",
                "milestones": [{"label": "m1"}],
                "completed": [{"label": "m1", "status": "done"}],
            }
        ),
        encoding="utf-8",
    )
    historical = _run_gather_program(
        worklist,
        tmp_path,
        extra_env={"MEGAPLAN_AUDIT_INSTALLED_WRAPPER": str(installed)},
    )

    assert historical["findings"] == []
    assert len(historical["green_checks"]) == 1


def _run_report_assembler(
    findings_data: dict,
    tmp_path: Path,
    ts: str = "20260702T220000Z",
    *,
    autofix_authorized: bool = False,
    launch_attempted: bool = False,
) -> tuple[dict, str]:
    """Run the report assembler with synthetic findings data and return (json_payload, markdown_text)."""
    program = _extract_report_assembler()
    prog_path = tmp_path / "_report_assembler.py"
    prog_path.write_text(program, encoding="utf-8")

    findings_path = tmp_path / "findings.json"
    json_out = tmp_path / "audit.json"
    md_out = tmp_path / "audit.md"
    log_path = tmp_path / "audit-report.log"
    recovery_path = tmp_path / "recovery.json"

    findings_path.write_text(json.dumps(findings_data), encoding="utf-8")
    recovery_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "watchdog_exit_code": 0,
                "sessions_discovered": 0,
                "should_run_count": 0,
                "decisions": [],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            str(findings_path),
            str(json_out),
            str(md_out),
            str(log_path),
            ts,
            "1" if autofix_authorized else "0",
            "1" if launch_attempted else "0",
            str(recovery_path),
            "gpt-5.6-sol",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"report assembler failed: {result.stderr}"

    json_payload = json.loads(json_out.read_text(encoding="utf-8"))
    md_text = md_out.read_text(encoding="utf-8")
    return json_payload, md_text


def _run_dispatch_one(
    tmp_path: Path,
    *,
    gather_payload: dict,
    extra_env: dict[str, str] | None = None,
    codex_stdout: str = "PASSIVE\nno-op\n",
    codex_stderr: str = "",
) -> tuple[str, str, str, dict]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    gather_dir = tmp_path / "gather"
    gather_dir.mkdir(parents=True, exist_ok=True)
    gather_file = gather_dir / "finding.json"
    payload = {"workspace": str(workspace), **gather_payload}
    gather_file.write_text(json.dumps(payload), encoding="utf-8")

    codex = tmp_path / "codex"
    codex.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$@\" > {shlex.quote(str(tmp_path / 'codex.argv'))}\n"
        f"printf '%s' {shlex.quote(codex_stdout)}\n"
        + (
            f"printf '%s' {shlex.quote(codex_stderr)} >&2\n"
            if codex_stderr
            else ""
        ),
        encoding="utf-8",
    )
    codex.chmod(codex.stat().st_mode | stat.S_IXUSR)

    script = "\n\n".join(
        [
            _extract_auditor_function("redact_inline_text"),
            _extract_auditor_function("redact_file_in_place"),
            _extract_auditor_function("log"),
            _extract_auditor_function("audit_flag_enabled"),
            _extract_auditor_function("autofix_allowed_targets_markdown"),
            _extract_auditor_function("autofix_policy_markdown"),
            _extract_auditor_function("audit_dispatch_receipt_root"),
            _extract_auditor_function("initialize_audit_dispatch_receipt"),
            _extract_auditor_function("record_audit_dispatch_started"),
            _extract_auditor_function("finalize_audit_dispatch_receipt"),
            _extract_auditor_function("dispatch_one"),
            f"WRAPPER_REPO_ROOT={shlex.quote(str(REPO_ROOT))}",
            f"ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            f"GATHER_DIR={shlex.quote(str(gather_dir))}",
            f"REPORT_DIR={shlex.quote(str(tmp_path / 'reports'))}",
            "TS=20260713T210000Z",
            "DEEPSEEK_MODEL=deepseek:deepseek-v4-pro",
            "AUDIT_CODEX_MODEL=gpt-5.6-sol",
            "SUBAGENT_PROFILE=partnered-5",
            "CODEX_TIMEOUT=30",
            'AUDIT_AUTOFIX_ENABLED_FLAG="$(audit_flag_enabled audit_autofix_enabled)"',
            'AUDIT_MUTATION_AUTHORIZED_FLAG="$(audit_flag_enabled audit_autofix_mutation_authorized)"',
            'AUDIT_AUTOFIX_COMMIT_ENABLED_FLAG="$(audit_flag_enabled audit_autofix_commit_enabled)"',
            "dispatch_one " + shlex.quote(str(gather_file)),
        ]
    )
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
    env.setdefault("ARNOLD_AUTONOMY", "1")
    env.setdefault("ARNOLD_AUDIT_AUTOFIX_ENABLED", "1")
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, env=env, check=False)
    assert result.returncode == 0, result.stderr

    plan = payload["plan"]
    brief = (gather_dir / f"brief-{plan}.md").read_text(encoding="utf-8")
    resp = (gather_dir / f"resp-{plan}.txt").read_text(encoding="utf-8")
    err_path = gather_dir / f"resp-{plan}.err"
    err = err_path.read_text(encoding="utf-8") if err_path.exists() else ""
    updated = json.loads(gather_file.read_text(encoding="utf-8"))
    argv_path = tmp_path / "codex.argv"
    updated["_codex_argv"] = argv_path.read_text(encoding="utf-8").splitlines() if argv_path.exists() else []
    return brief, resp, err, updated


def _run_record_incident_audits(tmp_path: Path, findings_data: dict) -> list[dict]:
    gather_dir = tmp_path / "gather"
    gather_dir.mkdir(parents=True, exist_ok=True)
    findings_path = gather_dir / "findings.json"
    findings_path.write_text(json.dumps(findings_data), encoding="utf-8")

    script = "\n\n".join(
        [
            _extract_auditor_function("record_incident_audits"),
            f"WRAPPER_REPO_ROOT={shlex.quote(str(REPO_ROOT))}",
            f"ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            f"GATHER_DIR={shlex.quote(str(gather_dir))}",
            "AUDIT_GITHUB_REPO=''",
            "AUDIT_GITHUB_REPO_PATH=''",
            "AUDIT_GITHUB_LABELS='incident-control-plane,persistent-problem'",
            f"REPAIR_QUEUE_ROOT={shlex.quote(str(tmp_path / '.megaplan' / 'repair-queue'))}",
            "record_incident_audits " + shlex.quote(str(findings_path)),
        ]
    )
    result = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr

    events_path = tmp_path / "workspace" / ".megaplan" / "incident-ledger" / "events.jsonl"
    return [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_stub_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_wrapper_boundary_stub_overlay(
    tmp_path: Path,
    *,
    audit_result: dict | None = None,
    current_target_payload: dict | None = None,
) -> tuple[Path, Path, Path]:
    stub_root = tmp_path / "stub-arnold-src"
    call_log = tmp_path / "wrapper-boundary-calls.jsonl"
    audit_capture = tmp_path / "wrapper-boundary-audit.json"
    audit_result_literal = repr(
        audit_result
        or {
            "incident_id": "inc-demo",
            "problem_id": "problem-demo",
            "findings": [
                {
                    "layer": "reconciler",
                    "status": "error",
                    "severity": "error",
                    "code": "DRIFT_DETECTED",
                    "source_pair": "resolver_vs_ledger",
                    "contradiction": "resolver_canonical_state_conflicts_with_ledger_outcome",
                    "drift_reason": "resolver_vs_ledger:resolver_canonical_state_conflicts_with_ledger_outcome",
                    "observed": {"canonical_state": "RUNNING"},
                    "expected": {
                        "brief_outcome": "blocked",
                        "next_expected_event": "immediate_repair.repair_attempt",
                    },
                    "message": "Cross-source reconciler drift detected for resolver_vs_ledger.",
                }
            ],
            "diagnosis": {
                "summary": "Resolver disagrees with the incident ledger.",
                "finding_count": 1,
                "highest_severity": "error",
            },
            "audit_complete": {
                "outcome": "escalated",
                "summary": "Resolver disagrees with the incident ledger.",
                "next_expected_event": "immediate_repair.repair_attempt",
            },
            "next_expected_event": "immediate_repair.repair_attempt",
        },
    )
    current_target_literal = repr(
        current_target_payload
        or {
            "schema_version": 1,
            "session": "demo-session",
            "target_id": "demo-session:demo-target",
            "authoritative_source": "stub_current_target",
            "current_refs": {"plan": "demo-plan"},
            "ci_health": {"status": "unavailable", "reason": "stub_current_target_slot"},
        },
    )

    package_files = {
        "arnold_pipelines/__init__.py": "",
        "arnold_pipelines/megaplan/__init__.py": "",
        "arnold_pipelines/megaplan/cloud/__init__.py": "",
        "arnold_pipelines/megaplan/run_state/__init__.py": "",
        "arnold_pipelines/megaplan/incident/__init__.py": "",
        "arnold_pipelines/megaplan/cloud/_stub_capture.py": """
import json
import os
from pathlib import Path


def append_call(record):
    path = Path(os.environ["ARNOLD_PROGRESS_AUDITOR_CALL_LOG"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_jsonable(record), sort_keys=True) + "\\n")


def _jsonable(value):
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "__fspath__"):
        return str(value)
    return value


def write_capture(record):
    path = Path(os.environ["ARNOLD_PROGRESS_AUDITOR_AUDIT_CAPTURE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(record), sort_keys=True), encoding="utf-8")
""",
        "arnold_pipelines/megaplan/cloud/redact.py": """
REDACTION = object()


def redact_text(value):
    return value
""",
        "arnold_pipelines/megaplan/cloud/meta_repair.py": """
from arnold_pipelines.megaplan.cloud._stub_capture import append_call


class _Classification:
    should_dispatch = False
    trigger_label = ""
    rationale = []


def evaluate_meta_repair_triggers(*args, **kwargs):
    append_call({"fn": "evaluate_meta_repair_triggers", "kwargs": kwargs})
    return _Classification(), {}
""",
        "arnold_pipelines/megaplan/cloud/repair_contract.py": """
def read_jsonl_records(*args, **kwargs):
    return []
""",
        "arnold_pipelines/megaplan/cloud/current_target.py": (
            "from arnold_pipelines.megaplan.cloud._stub_capture import append_call\n\n\n"
            "def resolve_current_target(session, **kwargs):\n"
            '    append_call({"fn": "resolve_current_target", "session": session, "kwargs": kwargs})\n'
            f"    payload = dict({current_target_literal})\n"
            '    payload["session"] = session\n'
            "    return payload\n"
        ),
        "arnold_pipelines/megaplan/cloud/auditor_external_evidence.py": """
from arnold_pipelines.megaplan.cloud._stub_capture import append_call


def collect_ci_health(repo_root, **kwargs):
    append_call({"fn": "collect_ci_health", "repo_root": str(repo_root), "kwargs": kwargs})
    return {
        "status": "red",
        "available": True,
        "base_branch": kwargs.get("base_branch", "main"),
        "failing_run_count": 2,
        "failed_checks": [{"name": "build", "state": "fail", "details": "stub"}],
    }


def collect_engine_tree_evidence(repo_root, **kwargs):
    append_call({"fn": "collect_engine_tree_evidence", "repo_root": str(repo_root), "kwargs": kwargs})
    return {
        "status": "red",
        "available": True,
        "repo_root": str(repo_root),
        "workspace_root": str(kwargs.get("workspace_root", "")),
        "dirty_paths": ["arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor"],
        "sibling_drift": [{"root": "/workspace/sibling", "changed_paths": ["tests/cloud/test_progress_auditor.py"]}],
        "import_consumers": ["cloud_wrappers"],
    }
""",
        "arnold_pipelines/megaplan/run_state/resolver.py": """
from arnold_pipelines.megaplan.cloud._stub_capture import append_call


class _ResolvedState:
    def __init__(self, payload):
        self._payload = payload

    def to_dict(self):
        return dict(self._payload)


def resolve_run_state(evidence=None, blocker_verdict=None):
    append_call(
        {
            "fn": "resolve_run_state",
            "evidence": evidence if isinstance(evidence, dict) else {},
            "blocker_verdict": blocker_verdict,
        }
    )
    return _ResolvedState(
        {
            "canonical_state": "REAL_IMPLEMENTATION_BLOCK",
            "confidence": "high",
            "next_action": "immediate_repair.repair_attempt",
            "stale_sources": [],
            "root_cause_fingerprint": {"kind": "real_impl", "value": "stub-root-cause"},
        }
    )
""",
        "arnold_pipelines/megaplan/cloud/six_hour_auditor.py": f"""
from arnold_pipelines.megaplan.cloud._stub_capture import write_capture

AUDIT_RESULT = {audit_result_literal}


def build_audit_input(session, *, root, now, persist=True):
    assert persist is False
    return {{
        "brief": {{
            "found": True,
            "incident_id": "inc-demo",
            "summary": "stub incident",
            "next_expected_event": "immediate_repair.repair_attempt",
            "claims": [],
        }},
        "incident": {{
            "incident_id": "inc-demo",
            "problem_id": "problem-demo",
            "state": "open",
            "outcome": "repair_in_progress",
            "session_ids": [session],
            "next_expected_event": "immediate_repair.repair_attempt",
        }},
        "problem": {{
            "problem_id": "problem-demo",
        }},
        "projections": {{}},
        "projection_input": {{
            "seed": "from_stub",
            "audit_history": [{{"audit_complete": {{"next_expected_event": "immediate_repair.repair_attempt"}}}}],
        }},
    }}


def audit_projection_input(audit_input, *, live_process_snapshot, now):
    write_capture(
        {{
            "audit_input": audit_input,
            "live_process_snapshot": live_process_snapshot,
            "now": now,
        }}
    )
    return AUDIT_RESULT


def enqueue_audit_repair_request(item, *, queue_root):
    return None
""",
        "arnold_pipelines/megaplan/incident/summaries.py": """
def write_projection_summaries(*, projections, root):
    return None
""",
    }
    for relative_path, content in package_files.items():
        _write_stub_file(stub_root, relative_path, content.lstrip("\n"))
    return stub_root, call_log, audit_capture


def _read_stub_calls(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestGreenChecksNoFindings:
    """Report shape when all plans are healthy (no suspicious signals)."""

    def test_six_hour_auditor_repairs_superfixer_via_subagent_introspection(self) -> None:
        text = _wrapper("arnold-progress-auditor")
        timer = _systemd_file("megaplan-progress-audit.timer")
        service = _systemd_file("megaplan-progress-audit.service")

        assert "OnUnitActiveSec=6h" in timer
        assert "Description=Megaplan 6-hour DeepSeek plan progress audit" in service
        assert "Codex then reads the subagent-launcher skill" in text
        assert "DeepSeek research subagents" in text
        assert "First audit the repair system itself" in text
        assert "there is no active or recent repair attempt" in text
        assert "Arnold superfixer bug" in text
        assert "Fix the watchdog/repair-trigger/auditor source" in text
        assert "do not hand-unblock only this run" in text

    def test_publication_attempt_ts_detects_github_issue_evidence(self) -> None:
        namespace: dict[str, object] = {}
        exec(
            _extract_gather_function("_publication_attempt_ts", "_dedupe_refs"),
            namespace,
        )
        publication_attempt_ts = namespace["_publication_attempt_ts"]

        incident = {
            "latest_actor": "watchdog",
            "last_timestamp": "2026-07-08T20:33:41+00:00",
            "evidence_refs": [
                {
                    "kind": "github.issue",
                    "number": 176,
                    "created_at": "2026-07-08T20:33:42+00:00",
                }
            ],
        }

        assert publication_attempt_ts(incident, {}) == "2026-07-08T20:33:42+00:00"

    def test_publication_attempt_ts_detects_github_sync_events(self) -> None:
        namespace: dict[str, object] = {}
        exec(
            _extract_gather_function("_publication_attempt_ts", "_dedupe_refs"),
            namespace,
        )
        publication_attempt_ts = namespace["_publication_attempt_ts"]

        incident = {
            "latest_actor": "watchdog",
            "events": [
                {
                    "kind": "incident.github_sync.issue_published",
                    "actor": "github_sync",
                    "timestamp": "2026-07-09T03:47:07+00:00",
                }
            ],
        }

        assert publication_attempt_ts(incident, {}) == "2026-07-09T03:47:07+00:00"

    def test_json_payload_includes_green_checks_when_findings_empty(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [
                {
                    "plan": "m5-meta-repair",
                    "workspace": "/workspace/tiered-repair-hardening/Arnold",
                    "session": "demo-session",
                    "sources": ["marker"],
                    "current_state": "executing",
                    "iteration": 12,
                    "active_step_phase": "execute",
                    "plan_v_count": 1,
                    "last_gate_recommendation": "proceed",
                    "last_gate_score": 8.5,
                }
            ],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        assert payload["schema_version"] == 1
        assert payload["finding_count"] == 0
        assert payload["green_checks_count"] == 1
        assert len(payload["green_checks"]) == 1
        gc = payload["green_checks"][0]
        assert gc["plan"] == "m5-meta-repair"
        assert gc["session"] == "demo-session"
        assert gc["current_state"] == "executing"

    def test_markdown_shows_green_checks_when_findings_empty(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [
                {
                    "plan": "healthy-plan",
                    "workspace": "/workspace/test",
                    "session": "healthy-session",
                    "sources": ["tmux"],
                    "current_state": "running",
                    "iteration": 5,
                    "active_step_phase": None,
                    "plan_v_count": 2,
                    "last_gate_recommendation": "proceed",
                    "last_gate_score": 9.0,
                }
            ],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "No suspicious plans detected" in md
        assert "## ✅ Healthy plans (inspected, no suspicious signals)" in md
        assert "**healthy-plan**" in md
        assert "healthy-session" in md

    def test_markdown_shows_multiple_green_checks(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [
                {
                    "plan": "plan-a",
                    "workspace": "/workspace/a",
                    "session": "session-a",
                    "sources": ["marker"],
                    "current_state": "executing",
                    "iteration": 3,
                    "active_step_phase": "execute",
                    "plan_v_count": 1,
                    "last_gate_recommendation": "proceed",
                    "last_gate_score": 8.0,
                },
                {
                    "plan": "plan-b",
                    "workspace": "/workspace/b",
                    "session": "session-b",
                    "sources": ["tmux"],
                    "current_state": "running",
                    "iteration": 7,
                    "active_step_phase": None,
                    "plan_v_count": 2,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                },
            ],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "## ✅ Healthy plans (inspected, no suspicious signals)" in md
        assert "**plan-a**" in md
        assert "**plan-b**" in md
        assert "session-a" in md
        assert "session-b" in md

    def test_markdown_empty_when_no_plans_at_all(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "No plans detected" in md
        assert "✅ Healthy plans" not in md

    def test_log_line_includes_green_count(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [
                {
                    "plan": "healthy-plan",
                    "workspace": "/workspace/test",
                    "session": "healthy-session",
                    "sources": [],
                    "current_state": "running",
                    "iteration": 1,
                    "active_step_phase": None,
                    "plan_v_count": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                }
            ],
        }
        log_path = tmp_path / "audit-report.log"
        # We already run the assembler; reuse a fresh tmp_path
        fresh = Path(tempfile.mkdtemp())
        try:
            program = _extract_report_assembler()
            prog_path = fresh / "_report_assembler.py"
            prog_path.write_text(program, encoding="utf-8")

            findings_path = fresh / "findings.json"
            json_out = fresh / "audit.json"
            md_out = fresh / "audit.md"
            fresh_log = fresh / "audit-report.log"
            recovery_path = fresh / "recovery.json"

            findings_path.write_text(json.dumps(findings_data), encoding="utf-8")
            recovery_path.write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "watchdog_exit_code": 0,
                        "sessions_discovered": 0,
                        "should_run_count": 0,
                        "decisions": [],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(prog_path),
                    str(findings_path),
                    str(json_out),
                    str(md_out),
                    str(fresh_log),
                    "20260702T220000Z",
                    "0",
                    "0",
                    str(recovery_path),
                    "gpt-5.6-sol",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, f"report assembler failed: {result.stderr}"

            log_text = fresh_log.read_text(encoding="utf-8")
            assert "green=1" in log_text
            assert "findings=0" in log_text
        finally:
            import shutil

            shutil.rmtree(fresh, ignore_errors=True)


class TestGreenChecksWithFindings:
    """Report shape with mixed findings and green_checks."""

    def test_json_payload_includes_both_findings_and_green_checks(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "stall:m-tune",
            "findings": [
                {
                    "plan": "suspicious-plan",
                    "workspace": "/workspace/bad",
                    "session": "bad-session",
                    "reasons": ["gate=ITERATE/blocked 3/4 recent times"],
                    "current_state": "executing",
                    "iteration": 10,
                    "last_gate_recommendation": "iterate",
                    "last_gate_score": 4.0,
                    "plan_v_count": 5,
                    "recent_gate_iterate": 3,
                    "recent_gate_total": 4,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [8, 6, 4],
                    "active_step_attempt": None,
                    "latest_failure_kind": None,
                    "latest_failure_message": "",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": ["marker"],
                    "session_header": {"kind": "chain", "session": "bad-session", "workspace": "/workspace/bad",
                                       "sources": ["marker"]},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                }
            ],
            "green_checks": [
                {
                    "plan": "healthy-plan",
                    "workspace": "/workspace/good",
                    "session": "good-session",
                    "sources": ["marker"],
                    "current_state": "executing",
                    "iteration": 5,
                    "active_step_phase": "execute",
                    "plan_v_count": 1,
                    "last_gate_recommendation": "proceed",
                    "last_gate_score": 8.5,
                }
            ],
        }
        payload, md = _run_report_assembler(findings_data, tmp_path)

        assert payload["finding_count"] == 1
        assert payload["green_checks_count"] == 1
        assert len(payload["findings"]) == 1
        assert len(payload["green_checks"]) == 1
        assert payload["findings"][0]["plan"] == "suspicious-plan"
        assert payload["green_checks"][0]["plan"] == "healthy-plan"

    def test_markdown_shows_both_sections(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "suspicious-plan",
                    "workspace": "/workspace/bad",
                    "session": "bad-session",
                    "reasons": ["score regression 8->4"],
                    "current_state": "executing",
                    "iteration": 10,
                    "last_gate_recommendation": "iterate",
                    "last_gate_score": 4.0,
                    "plan_v_count": 5,
                    "recent_gate_iterate": 2,
                    "recent_gate_total": 5,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [8, 6, 4],
                    "active_step_attempt": None,
                    "latest_failure_kind": None,
                    "latest_failure_message": "",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": ["marker"],
                    "session_header": {"kind": "chain", "session": "bad-session", "workspace": "/workspace/bad",
                                       "sources": ["marker"]},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "STALE: clear latest_failure and re-drive.",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "STALE: clear latest_failure and re-drive.",
                }
            ],
            "green_checks": [
                {
                    "plan": "healthy-plan",
                    "workspace": "/workspace/good",
                    "session": "good-session",
                    "sources": ["marker"],
                    "current_state": "executing",
                    "iteration": 5,
                    "active_step_phase": "execute",
                    "plan_v_count": 1,
                    "last_gate_recommendation": "proceed",
                    "last_gate_score": 8.5,
                }
            ],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        # Findings section present
        assert "## suspicious-plan" in md
        assert "bad-session" in md
        assert "STALE" in md

        # Green checks section present
        assert "## ✅ Healthy plans (inspected, no suspicious signals)" in md
        assert "**healthy-plan**" in md
        assert "good-session" in md

    def test_markdown_window_line_shows_both_counts(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 4,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "p1",
                    "workspace": "/w/p1",
                    "session": "s1",
                    "reasons": ["r1"],
                    "current_state": "e",
                    "iteration": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 0,
                    "recent_gate_total": 0,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [],
                    "active_step_attempt": None,
                    "latest_failure_kind": None,
                    "latest_failure_message": "",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": [],
                    "session_header": {"kind": "chain", "session": "s1", "workspace": "/w/p1", "sources": []},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                }
            ],
            "green_checks": [
                {
                    "plan": "p2",
                    "workspace": "/w/p2",
                    "session": "s2",
                    "sources": [],
                    "current_state": "running",
                    "iteration": 3,
                    "active_step_phase": None,
                    "plan_v_count": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                },
                {
                    "plan": "p3",
                    "workspace": "/w/p3",
                    "session": "s3",
                    "sources": [],
                    "current_state": "executing",
                    "iteration": 7,
                    "active_step_phase": "execute",
                    "plan_v_count": 2,
                    "last_gate_recommendation": "proceed",
                    "last_gate_score": 9.0,
                },
            ],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "findings: 1" in md
        assert "green: 2" in md
        assert "## ✅ Healthy plans (inspected, no suspicious signals)" in md
        assert "**p2**" in md
        assert "**p3**" in md


class TestGreenChecksJsonSchema:
    """Verify the JSON payload shape invariants."""

    def test_green_checks_field_present_even_when_empty(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        assert "green_checks" in payload
        assert payload["green_checks_count"] == 0
        assert payload["green_checks"] == []

    def test_green_checks_field_present_with_data(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [
                {
                    "plan": "p1",
                    "workspace": "/w/p1",
                    "session": "s1",
                    "sources": ["marker"],
                    "current_state": "executing",
                    "iteration": 5,
                    "active_step_phase": "execute",
                    "plan_v_count": 1,
                    "last_gate_recommendation": "proceed",
                    "last_gate_score": 8.5,
                }
            ],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        assert payload["green_checks_count"] == 1
        gc = payload["green_checks"][0]
        assert set(gc.keys()) == {
            "plan", "workspace", "session", "sources", "current_state",
            "iteration", "active_step_phase", "plan_v_count",
            "last_gate_recommendation", "last_gate_score",
        }

    def test_timestamp_always_present(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        assert "timestamp_utc" in payload
        assert payload["timestamp_utc"].endswith("+00:00") or "Z" in payload["timestamp_utc"] or "T" in payload["timestamp_utc"]


class TestGreenChecksMarkdownOutput:
    """Focused Markdown output verification."""

    def test_markdown_header_includes_green_count(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "progress_stall:m-tune",
            "findings": [],
            "green_checks": [
                {
                    "plan": "plan-x",
                    "workspace": "/w/x",
                    "session": "sx",
                    "sources": [],
                    "current_state": "running",
                    "iteration": 2,
                    "active_step_phase": None,
                    "plan_v_count": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                }
            ],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "green: 1" in md
        assert "findings: 0" in md
        assert "progress_stall:m-tune" in md

    def test_green_check_entry_formatted_with_state_and_iteration(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [
                {
                    "plan": "formatted-plan",
                    "workspace": "/w/f",
                    "session": "sf",
                    "sources": [],
                    "current_state": "executing",
                    "iteration": 42,
                    "active_step_phase": None,
                    "plan_v_count": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                }
            ],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "**formatted-plan**" in md
        assert "state `executing`" in md
        assert "iteration `42`" in md

    def test_green_check_entry_includes_gate_when_present(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [
                {
                    "plan": "gated-plan",
                    "workspace": "/w/g",
                    "session": "sg",
                    "sources": [],
                    "current_state": "executing",
                    "iteration": 3,
                    "active_step_phase": None,
                    "plan_v_count": 1,
                    "last_gate_recommendation": "proceed",
                    "last_gate_score": 9.5,
                }
            ],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "gate `proceed`" in md
        assert "score 9.5" in md

    def test_green_check_entry_omits_gate_when_absent(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [
                {
                    "plan": "no-gate-plan",
                    "workspace": "/w/ng",
                    "session": "sng",
                    "sources": [],
                    "current_state": "running",
                    "iteration": 1,
                    "active_step_phase": None,
                    "plan_v_count": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                }
            ],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "gate `" not in md.split("## ✅ Healthy plans")[-1] if "## ✅ Healthy plans" in md else True


class TestAuditorWrapperSyntax:
    """Basic wrapper integrity checks."""

    def test_wrapper_passes_bash_syntax(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(WRAPPER_DIR / "arnold-progress-auditor")],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"bash -n failed: {result.stderr}"

    def test_green_checks_present_in_gather_program(self) -> None:
        program = _extract_gather_program()
        assert "green_checks" in program
        assert "green_checks.append" in program

    def test_green_checks_present_in_report_assembler(self) -> None:
        program = _extract_report_assembler()
        assert "green_checks" in program
        assert "green_checks_count" in program


class TestAuditorAutofixPromptGates:
    def test_dispatch_pins_exact_codex_model_and_persists_read_only_receipt(
        self, tmp_path: Path
    ) -> None:
        _brief, _resp, _err, updated = _run_dispatch_one(
            tmp_path,
            gather_payload={
                "plan": "audit-model-pin",
                "reasons": ["watchdog_report_stale"],
                "session_header": {"kind": "chain"},
            },
        )

        assert updated["_codex_argv"] == [
            "exec", "--sandbox", "read-only", "-c", "model=gpt-5.6-sol",
            "-c", "model_reasoning_effort=high", "-"
        ]
        receipt_path = (
            Path(updated["dispatch_receipt_root"])
            / "dispatch_receipts"
            / f"{updated['dispatch_id']}.json"
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["configured_model"] == "gpt-5.6-sol"
        assert receipt["resolved_runtime_model"] == "gpt-5.6-sol"
        assert receipt["subprocess_started"] is True
        assert receipt["mutation_facts"] == {
            "state": False, "source": False, "commit": False, "push": False
        }
        manifest = json.loads(
            Path(updated["managed_agent_manifest_path"]).read_text(encoding="utf-8")
        )
        assert manifest["run_id"] == updated["managed_agent_run_id"]
        assert manifest["run_kind"] == "automatic_progress_audit_agent"
        assert manifest["launch_provenance"]["origin_kind"] == "periodic_progress_auditor"
        assert manifest["stdin"]["sealed"] is True
        assert manifest["links"]["dispatch_id"] == updated["dispatch_id"]

    def test_disabled_mode_is_report_only(self, tmp_path: Path) -> None:
        brief, _resp, _err, _updated = _run_dispatch_one(
            tmp_path,
            gather_payload={
                "plan": "audit-disabled",
                "reasons": ["phase_failed: stale watchdog output"],
                "session_header": {"kind": "chain"},
            },
            extra_env={
                "ARNOLD_AUDIT_AUTOFIX_ENABLED": "0",
                "ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED": "0",
            },
        )

        assert "Auditor authority: READ-ONLY EVALUATOR." in brief
        assert "Do not apply patches, create claims, launch repair agents, commit, or push." in brief

    def test_enabled_without_commit_gate_is_patch_only_and_bounded(self, tmp_path: Path) -> None:
        brief, _resp, _err, _updated = _run_dispatch_one(
            tmp_path,
            gather_payload={
                "plan": "audit-patch-only",
                "reasons": ["phase_failed: reproducible repair bug"],
                "session_header": {"kind": "chain"},
            },
            extra_env={
                "ARNOLD_AUDIT_AUTOFIX_ENABLED": "1",
                "ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED": "0",
            },
        )

        assert "Auditor authority: READ-ONLY EVALUATOR." in brief
        assert "No mutation targets." in brief
        assert "validated central repair-request authority" in brief

    def test_commit_push_language_requires_explicit_commit_gate(self, tmp_path: Path) -> None:
        brief, _resp, _err, _updated = _run_dispatch_one(
            tmp_path,
            gather_payload={
                "plan": "audit-commit-enabled",
                "reasons": ["phase_failed: bounded repair-system fix available"],
                "session_header": {"kind": "chain"},
            },
            extra_env={
                "ARNOLD_AUDIT_AUTOFIX_ENABLED": "1",
                "ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED": "1",
            },
        )

        assert "Auditor authority: READ-ONLY EVALUATOR." in brief
        assert "Do not edit source, run state, plan state, repair data, or project files." in brief
        assert "REPAIR-SYSTEM PATCH + COMMIT/PUSH" not in brief

    def test_prompt_and_response_artifacts_are_redacted(self, tmp_path: Path) -> None:
        secret = "Authorization: Bearer bearer-secret-token-value"
        brief, resp, err, updated = _run_dispatch_one(
            tmp_path,
            gather_payload={
                "plan": "audit-redaction",
                "reasons": [secret],
                "session_header": {"kind": "chain"},
                "plan_latest_failure": {"kind": "phase_failed", "metadata": {"stderr": secret}},
            },
            extra_env={
                "ARNOLD_AUDIT_AUTOFIX_ENABLED": "1",
                "ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED": "0",
            },
            codex_stdout=f"PASSIVE\n{secret}\n",
            codex_stderr=secret,
        )

        assert "bearer-secret-token-value" not in brief
        assert "bearer-secret-token-value" not in resp
        assert "bearer-secret-token-value" not in err
        assert "bearer-secret-token-value" not in updated["agent_response"]
        assert REDACTION in brief
        assert REDACTION in resp
        assert not err or REDACTION in err
        assert REDACTION in updated["agent_response"]
        assert "No-secrets rule:" in brief

    def test_prompt_uses_reconciler_language_and_brief_first_evidence(self, tmp_path: Path) -> None:
        brief, _resp, _err, _updated = _run_dispatch_one(
            tmp_path,
            gather_payload={
                "plan": "audit-reconciler",
                "reasons": ["reconciler watchdog=watchdog_report_stale: stale watchdog evidence"],
                "session_header": {"kind": "chain"},
            },
        )

        assert "Reconciler findings:" in brief
        assert "Treat bounded incident brief and projection records as the source of truth." in brief
        assert "Use live-process discovery, repair-data sidecars, tmux state, and watchdog archives only as corroboration." in brief
        assert "You are reconciling a cloud megaplan SESSION" in brief
        assert "ledger reconciliation is required" in brief


class TestAuditorCrossReferences:
    def test_gather_prefers_incident_brief_and_projection_records(self, tmp_path: Path) -> None:
        from arnold_pipelines.megaplan.cloud.incident_bridge import append_watchdog_detection

        workspace = tmp_path / "workspace" / "demo"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "created_at": "2026-07-02T20:00:00+00:00",
                    "current_state": "executing",
                    "iteration": 2,
                    "last_gate": {"recommendation": "iterate"},
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

        append_watchdog_detection(
            incident_id="inc-demo",
            session_id="demo-session",
            summary="repair stalled waiting on watchdog follow-up",
            outcome="progress_stall",
            next_expected_event="immediate_repair.repair_attempt",
            deadline_ts="2026-07-02T19:00:00+00:00",
            root=workspace,
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "plan",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
        )

        assert len(findings["findings"]) == 1
        finding = findings["findings"][0]
        assert finding["incident_brief"]["incident_id"] == "inc-demo"
        assert finding["incident_audit"]["incident_id"] == "inc-demo"
        assert finding["reasons"][0].startswith("reconciler ")
        summary_path = Path(finding["source_refs"]["incident_summary_path"])
        assert summary_path == (
            workspace
            / ".megaplan"
            / "incident-ledger"
            / "summaries"
            / "incidents"
            / "inc-demo.json"
        )
        assert not summary_path.exists()


class TestAuditorWrapperBoundary:
    def test_gather_passes_resolver_and_external_evidence_through_projection_input(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace" / "demo"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "executing",
                    "iteration": 2,
                    "last_gate": {"recommendation": "iterate"},
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

        stub_root, call_log, audit_capture = _build_wrapper_boundary_stub_overlay(tmp_path)
        repair_root = tmp_path / "repair-data"
        repair_root.mkdir(parents=True, exist_ok=True)

        _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "plan",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            arnold_src=stub_root,
            cwd=tmp_path,
            extra_env={
                "ARNOLD_PROGRESS_AUDITOR_CALL_LOG": str(call_log),
                "ARNOLD_PROGRESS_AUDITOR_AUDIT_CAPTURE": str(audit_capture),
                "MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root),
            },
        )

        calls = _read_stub_calls(call_log)
        capture = json.loads(audit_capture.read_text(encoding="utf-8"))
        projection_input = capture["audit_input"]["projection_input"]

        current_target_call = next(
            call for call in calls if call["fn"] == "resolve_current_target"
        )
        assert current_target_call["kwargs"] == {
            "marker_dir": str(tmp_path / ".megaplan" / "cloud-sessions"),
            "repair_data_dir": str(repair_root),
            "workspace_hint": str(workspace),
        }

        assert {call["fn"] for call in calls} >= {
            "resolve_current_target",
            "resolve_run_state",
            "collect_ci_health",
            "collect_engine_tree_evidence",
        }
        assert projection_input["current_target"]["authoritative_source"] == "stub_current_target"
        assert projection_input["current_target"]["ci_health"]["reason"] == "stub_current_target_slot"
        assert projection_input["resolver_state"]["canonical_state"] == "REAL_IMPLEMENTATION_BLOCK"
        assert projection_input["resolver_state"]["next_action"] == "immediate_repair.repair_attempt"
        assert projection_input["ci_health"]["status"] == "red"
        assert projection_input["ci_health"]["failing_run_count"] == 2
        assert projection_input["engine_tree"]["status"] == "red"
        assert projection_input["engine_tree"]["import_consumers"] == ["cloud_wrappers"]

    def test_gather_filters_dead_liveness_and_uses_drift_metadata_for_reasons(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace" / "demo"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "executing",
                    "iteration": 4,
                    "last_gate": {"recommendation": "iterate"},
                    "active_step": {"phase": "execute", "attempt": 4, "worker_pid": 999999},
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

        repair_root = tmp_path / "repair-data"
        attempt_dir = repair_root / "attempts"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        (repair_root / "demo-session.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "incident_id": "inc-demo",
                    "attempt_ids": ["attempt-1"],
                    "current_attempt_id": "attempt-1",
                }
            ),
            encoding="utf-8",
        )
        (attempt_dir / "attempt-1.json").write_text(
            json.dumps({"attempt_id": "attempt-1", "incident_id": "inc-demo"}),
            encoding="utf-8",
        )

        stub_root, call_log, audit_capture = _build_wrapper_boundary_stub_overlay(tmp_path)
        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "plan",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            arnold_src=stub_root,
            cwd=tmp_path,
            extra_env={
                "ARNOLD_PROGRESS_AUDITOR_CALL_LOG": str(call_log),
                "ARNOLD_PROGRESS_AUDITOR_AUDIT_CAPTURE": str(audit_capture),
                "MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root),
            },
        )

        capture = json.loads(audit_capture.read_text(encoding="utf-8"))
        finding = findings["findings"][0]
        snapshot = capture["live_process_snapshot"]
        actors = {
            process.get("actor")
            for process in snapshot.get("processes", [])
            if isinstance(process, dict)
        }

        assert "immediate_repair" not in actors
        assert snapshot["immediate_repair"]["active_step_liveness"]["worker_pid_alive"] is False
        assert snapshot["immediate_repair"]["evidence_refs"][0]["attempt_id"] == "attempt-1"
        assert snapshot["corroboration"]["attempt_ref_count"] == 1
        assert finding["reasons"][0] == "resolver_vs_ledger:resolver_canonical_state_conflicts_with_ledger_outcome"
        assert "DRIFT_DETECTED" not in finding["reasons"][0]
        assert not finding["reasons"][0].startswith("reconciler ")

    def test_gather_uses_live_session_evidence_for_process_snapshot(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace" / "demo"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "executing",
                    "iteration": 4,
                    "last_gate": {"recommendation": "iterate"},
                    "history": [],
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

        repair_root = tmp_path / "repair-data"
        attempt_dir = repair_root / "attempts"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        (repair_root / "demo-session.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "incident_id": "inc-demo",
                    "attempt_ids": ["attempt-1"],
                    "current_attempt_id": "attempt-1",
                }
            ),
            encoding="utf-8",
        )
        (attempt_dir / "attempt-1.json").write_text(
            json.dumps({"attempt_id": "attempt-1", "incident_id": "inc-demo"}),
            encoding="utf-8",
        )

        stub_root, call_log, audit_capture = _build_wrapper_boundary_stub_overlay(
            tmp_path,
            current_target_payload={
                "schema_version": 1,
                "session": "demo-session",
                "target_id": "demo-session:demo-target",
                "authoritative_source": "stub_current_target",
                "current_refs": {"plan": "demo-plan"},
                "ci_health": {"status": "unavailable", "reason": "stub_current_target_slot"},
                "tmux_process": {
                    "session": "demo-session",
                    "pid": 4242,
                    "pid_live": True,
                    "session_live": True,
                    "live_status": "alive",
                },
            },
        )
        _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "plan",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            arnold_src=stub_root,
            cwd=tmp_path,
            extra_env={
                "ARNOLD_PROGRESS_AUDITOR_CALL_LOG": str(call_log),
                "ARNOLD_PROGRESS_AUDITOR_AUDIT_CAPTURE": str(audit_capture),
                "MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root),
            },
        )

        capture = json.loads(audit_capture.read_text(encoding="utf-8"))
        processes = capture["live_process_snapshot"]["processes"]

        assert processes[0]["actor"] == "immediate_repair"
        assert processes[0]["worker_pid"] == 4242
        assert "tmux_session" in processes[0]["live_evidence_sources"]
        assert capture["live_process_snapshot"]["immediate_repair"]["evidence_refs"][0]["attempt_id"] == "attempt-1"

    def test_gather_populates_bounded_redacted_cross_references(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace" / "demo"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        now = "2026-07-02T21:00:00+00:00"
        state = {
            "name": "demo-plan",
            "current_state": "executing",
            "iteration": 9,
            "last_gate": {"recommendation": "iterate"},
            "meta": {"weighted_scores": [8, 5, 4]},
            "history": [
                {"step": "gate", "result": "iterate", "timestamp": "2026-07-02T20:10:00+00:00"},
                {"step": "gate", "result": "blocked", "timestamp": "2026-07-02T20:20:00+00:00"},
                {"step": "gate", "result": "iterate", "timestamp": "2026-07-02T20:30:00+00:00"},
            ],
            "latest_failure": {
                "kind": "phase_failed",
                "message": "Authorization: Bearer sk-proj-secretsecretsecretsecret failed",
                "recorded_at": now,
            },
        }
        (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

        repair_root = tmp_path / "repair-data"
        (repair_root / "incidents").mkdir(parents=True, exist_ok=True)
        (repair_root / "attempts").mkdir(parents=True, exist_ok=True)
        (repair_root / "meta").mkdir(parents=True, exist_ok=True)
        (repair_root / "demo-session.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "incident_id": "incident-current",
                    "attempt_ids": ["attempt-current"],
                    "current_attempt_id": "attempt-current",
                    "known_prior_issue_refs": [{"incident_id": "incident-prior"}],
                }
            ),
            encoding="utf-8",
        )
        (repair_root / "incidents" / "incident-current.json").write_text(
            json.dumps({"incident_id": "incident-current", "session": "demo-session", "state": "open"}),
            encoding="utf-8",
        )
        (repair_root / "incidents" / "incident-prior.json").write_text(
            json.dumps(
                {
                    "incident_id": "incident-prior",
                    "session": "demo-session",
                    "state": "resolved",
                    "problem_signature": {"root_cause_hint_hash": "sk-proj-secretsecretsecretsecret"},
                }
            ),
            encoding="utf-8",
        )
        (repair_root / "attempts" / "attempt-current.json").write_text(
            json.dumps({"attempt_id": "attempt-current", "incident_id": "incident-current", "session": "demo-session"}),
            encoding="utf-8",
        )
        (repair_root / "meta" / "meta-incident-prior-20260702210000.json").write_text(
            json.dumps(
                {
                    "meta_repair_id": "meta-incident-prior-20260702210000",
                    "incident_id": "incident-prior",
                    "session": "demo-session",
                }
            ),
            encoding="utf-8",
        )

        sidecar_root = tmp_path / "repair-data.d"
        esc_dir = sidecar_root / "escalations"
        esc_dir.mkdir(parents=True, exist_ok=True)
        (esc_dir / "escalations.jsonl").write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "incident_id": "incident-prior",
                    "escalation_id": "esc-incident-prior-1",
                    "_sequence": 1,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        audit_dir = tmp_path / "audit-reports"
        audit_dir.mkdir()
        (audit_dir / "20260701T010101Z-audit.json").write_text(
            json.dumps(
                {
                    "timestamp_utc": "2026-07-01T01:01:01+00:00",
                    "findings": [{"plan": "demo-plan", "session": "demo-session"}],
                }
            ),
            encoding="utf-8",
        )
        watchdog_archive_dir = tmp_path / "watchdog-reports"
        watchdog_archive_dir.mkdir()
        (tmp_path / "watchdog-report.json").write_text(
            json.dumps({"timestamp_utc": now, "items": [{"session": "demo-session", "plan": "demo-plan"}]}),
            encoding="utf-8",
        )
        findings_doc = tmp_path / "findings" / "persistent-problems.md"
        findings_doc.parent.mkdir(parents=True, exist_ok=True)
        findings_doc.write_text(
            "## 2026-07-02T21:00:00Z -- demo-session -- dev-fix iteration 1\n"
            "Token sk-proj-secretsecretsecretsecret kept recurring in demo-plan\n",
            encoding="utf-8",
        )
        ticket_dir = workspace / ".megaplan" / "tickets"
        ticket_dir.mkdir(parents=True, exist_ok=True)
        (ticket_dir / "TICKET-incident-prior.md").write_text(
            "demo-session demo-plan incident-prior\n",
            encoding="utf-8",
        )

        commit_repo = tmp_path / "commit-src"
        tracked = commit_repo / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
        tracked.mkdir(parents=True, exist_ok=True)
        (commit_repo / "arnold_pipelines" / "megaplan" / "cloud" / "meta_repair.py").parent.mkdir(
            parents=True, exist_ok=True
        )
        (tracked / "arnold-watchdog").write_text("echo watchdog\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=commit_repo, capture_output=True, text=True, check=False)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=commit_repo, capture_output=True, text=True, check=False)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=commit_repo, capture_output=True, text=True, check=False)
        subprocess.run(["git", "add", "."], cwd=commit_repo, capture_output=True, text=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "repair: redact sk-proj-secretsecretsecretsecret"],
            cwd=commit_repo,
            capture_output=True,
            text=True,
            check=False,
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "plan",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={
                "MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root),
                "MEGAPLAN_AUDIT_REPORT_DIR": str(audit_dir),
                "MEGAPLAN_AUDIT_WATCHDOG_REPORT": str(tmp_path / "watchdog-report.json"),
                "MEGAPLAN_AUDIT_WATCHDOG_REPORT_ARCHIVE_DIR": str(watchdog_archive_dir),
                "CLOUD_WATCHDOG_REPAIR_FINDINGS_DOC": str(findings_doc),
                "MEGAPLAN_AUDIT_COMMIT_SOURCE_DIR": str(commit_repo),
            },
        )

        assert len(findings["findings"]) == 1
        finding = findings["findings"][0]
        assert finding["related_prior_incidents"] == [
            {
                "incident_id": "incident-prior",
                "path": str(repair_root / "incidents" / "incident-prior.json"),
                "session": "demo-session",
                "state": "resolved",
                "source": "incident_record",
            }
        ]
        assert finding["prior_audit_refs"][0]["path"] == str(audit_dir / "20260701T010101Z-audit.json")
        assert finding["prior_watchdog_report_refs"][0]["path"] == str(tmp_path / "watchdog-report.json")
        assert finding["persistent_finding_refs"][0]["path"] == str(findings_doc)
        assert finding["ticket_refs"][0]["path"] == str(ticket_dir / "TICKET-incident-prior.md")
        assert finding["meta_repair_refs"][0]["path"] == str(repair_root / "meta" / "meta-incident-prior-20260702210000.json")
        assert finding["attempt_refs"][0]["path"] == str(repair_root / "attempts" / "attempt-current.json")
        assert finding["escalation_refs"][0]["path"] == str(esc_dir / "escalations.jsonl")
        assert finding["commit_refs"][0]["commit"]
        assert "sk-proj-secretsecretsecretsecret" not in finding["commit_refs"][0]["subject"]
        assert "sk-proj-secretsecretsecretsecret" not in finding["persistent_finding_refs"][0]["excerpt"]
        serialized_refs = json.dumps(
            {
                "related_prior_incidents": finding["related_prior_incidents"],
                "persistent_finding_refs": finding["persistent_finding_refs"],
                "commit_refs": finding["commit_refs"],
                "source_refs": finding["source_refs"],
            },
            sort_keys=True,
        )
        assert "sk-proj-secretsecretsecretsecret" not in serialized_refs

    def test_report_assembler_rolls_up_related_prior_incidents(self, tmp_path: Path) -> None:
        payload, _md = _run_report_assembler(
            {
                "window_hours": 6,
                "stall_summary": "none",
                "findings": [
                    {
                        "plan": "demo-plan",
                        "workspace": "/workspace/demo",
                        "session": "demo-session",
                        "reasons": ["gate=ITERATE/blocked 3/3 recent times"],
                        "current_state": "executing",
                        "iteration": 9,
                        "last_gate_recommendation": "iterate",
                        "last_gate_score": 4.0,
                        "plan_v_count": 1,
                        "recent_gate_iterate": 3,
                        "recent_gate_total": 3,
                        "plan_v_sizes": {},
                        "events_size": 0,
                        "score_trajectory": [8, 4],
                        "active_step_attempt": None,
                        "latest_failure_kind": "phase_failed",
                        "latest_failure_message": "boom",
                        "latest_failure_is_stale": None,
                        "last_success_after_failure": None,
                        "stale_block_replay": None,
                        "between_milestone_cycling": None,
                        "sources": ["marker"],
                        "session_header": {"kind": "plan", "session": "demo-session", "workspace": "/workspace/demo", "sources": ["marker"]},
                        "chain_log": {},
                        "chain_state_summary": {"current": {}},
                        "repair_data_summary": {},
                        "plan_latest_failure": {},
                        "stale_state_evidence": {},
                        "user_action_context": {},
                        "active_step_phase": None,
                        "events_mtime_age_min": None,
                        "plan_deltas": [],
                        "significant_counts": [],
                        "latest_failure_metadata": {},
                        "related_prior_incidents": [
                            {"incident_id": "incident-prior", "path": "/tmp/incident-prior.json", "session": "demo-session", "state": "resolved", "source": "incident_record"}
                        ],
                        "source_refs": {"audit_report_paths": ["/tmp/audit.json"]},
                    }
                ],
                "green_checks": [],
            },
            tmp_path,
        )
        assert payload["related_prior_incidents"] == [
            {"incident_id": "incident-prior", "path": "/tmp/incident-prior.json", "session": "demo-session", "state": "resolved", "source": "incident_record"}
        ]

    def test_record_incident_audits_appends_diagnosis_and_audit_complete(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        findings_data = {
            "findings": [
                {
                    "plan": "demo-plan",
                    "workspace": str(workspace),
                    "session": "demo-session",
                    "incident_brief": {
                        "incident_id": "inc-123",
                        "summary": "watchdog reconciliation pending",
                        "deadline_ts": "2026-07-04T00:00:00+00:00",
                        "last_timestamp": "2026-07-03T20:00:00+00:00",
                    },
                    "incident_projection": {"incident_id": "inc-123"},
                    "problem_projection": {"problem_id": "problem-123"},
                    "incident_audit": {
                        "incident_id": "inc-123",
                        "problem_id": "problem-123",
                        "findings": [
                            {
                                "layer": "watchdog",
                                "status": "error",
                                "severity": "error",
                                "code": "watchdog_report_stale",
                                "message": "The watchdog report is older than the configured audit cadence.",
                            }
                        ],
                        "diagnosis": {"summary": "Audit found stale watchdog evidence.", "finding_count": 1, "highest_severity": "error"},
                        "audit_complete": {
                            "outcome": "escalated",
                            "summary": "Audit found stale watchdog evidence.",
                            "next_expected_event": "watchdog.dispatch",
                        },
                    },
                    "source_refs": {
                        "incident_summary_path": str(workspace / ".megaplan" / "incident-ledger" / "summaries" / "incidents" / "inc-123.json"),
                        "problem_summary_path": str(workspace / ".megaplan" / "incident-ledger" / "summaries" / "problems" / "problem-123.json"),
                    },
                }
            ],
            "green_checks": [],
        }

        events = _run_record_incident_audits(tmp_path, findings_data)

        assert [event["payload"]["type"] for event in events] == [
            "six_hour_auditor.diagnosis",
            "six_hour_auditor.audit_complete",
        ]
        assert events[0]["payload"]["next_expected_event"] == "six_hour_auditor.audit_complete"
        assert events[1]["payload"]["next_expected_event"] == "six_hour_auditor.diagnosis"

    def test_record_incident_audits_keeps_auditor_human_escalation_out_of_meta_repair_dispatch(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        findings_data = {
            "findings": [
                {
                    "plan": "demo-plan",
                    "workspace": str(workspace),
                    "session": "demo-session",
                    "incident_brief": {
                        "incident_id": "inc-124",
                        "summary": "auditor escalated to a human operator",
                        "deadline_ts": "2026-07-04T00:00:00+00:00",
                        "last_timestamp": "2026-07-03T20:00:00+00:00",
                    },
                    "incident_projection": {"incident_id": "inc-124"},
                    "problem_projection": {"problem_id": "problem-124"},
                    "incident_audit": {
                        "incident_id": "inc-124",
                        "problem_id": "problem-124",
                        "findings": [
                            {
                                "layer": "recurrence",
                                "status": "error",
                                "severity": "error",
                                "code": "auditor_recursion_guard",
                                "recommendation": "auditor_escalate_to_human",
                                "message": "The auditor found a repeated loop and must hand off to a human.",
                            }
                        ],
                        "diagnosis": {
                            "summary": "Audit found a repeated loop and requires human escalation.",
                            "finding_count": 1,
                            "highest_severity": "error",
                        },
                        "audit_complete": {
                            "outcome": "auditor_human_escalation",
                            "summary": "Audit found a repeated loop and requires human escalation.",
                            "next_expected_event": "auditor_escalate_to_human",
                        },
                    },
                    "source_refs": {
                        "incident_summary_path": str(
                            workspace / ".megaplan" / "incident-ledger" / "summaries" / "incidents" / "inc-124.json"
                        ),
                        "problem_summary_path": str(
                            workspace / ".megaplan" / "incident-ledger" / "summaries" / "problems" / "problem-124.json"
                        ),
                    },
                }
            ],
            "green_checks": [],
        }

        events = _run_record_incident_audits(tmp_path, findings_data)

        assert [event["payload"]["type"] for event in events] == [
            "six_hour_auditor.diagnosis",
            "six_hour_auditor.audit_complete",
        ]
        assert events[1]["payload"]["outcome"] == "auditor_human_escalation"
        assert events[1]["payload"]["next_expected_event"] is None
        assert events[1]["payload"]["decision"]["reconciler_next_expected_event"] == "auditor_escalate_to_human"
        assert all(event["payload"].get("next_expected_event") != "meta_repair.repair_attempt" for event in events)
        queue_root = tmp_path / ".megaplan" / "repair-queue"
        requests = [json.loads(path.read_text(encoding="utf-8")) for path in (queue_root / "requests").glob("*.json")]
        assert requests == []
        repair_data_dir = tmp_path / ".megaplan" / "cloud-sessions" / "repair-data"
        assert not (repair_data_dir / "demo-session.needs-human.json").exists()


class TestLiveSignalFiltering:
    def test_chain_log_awaiting_human_ignores_pytest_command_substring(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "blocked",
                    "iteration": 2,
                    "latest_failure": {
                        "kind": "phase_failed",
                        "message": "boom",
                        "recorded_at": "2026-07-03T16:00:00+00:00",
                    },
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        chain_dir.mkdir(parents=True, exist_ok=True)
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "completed": [],
                    "completed_count": 0,
                    "current_milestone_index": 0,
                    "current_plan_name": "demo-plan",
                    "current_state": "",
                    "events": [],
                    "last_state": "between_milestones",
                    "reason": "",
                }
            ),
            encoding="utf-8",
        )
        (workspace / ".megaplan" / "cloud-chain-demo-session.log").write_text(
            "\n".join(
                [
                    "[chain] milestone demo starting",
                    "[chain] plan demo-plan ended blocked: resume-clarify requires state 'awaiting_human_verify', got 'blocked'",
                    '          "command": "python -m pytest tests/arnold_pipelines/megaplan/test_chain_awaiting_human_retry.py -q"',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
        )

        finding = findings["findings"][0]
        assert finding["chain_log"]["repetition_summary"] == []
        assert not any(
            "chain log repeats awaiting_human" in reason for reason in finding["reasons"]
        )

    def test_meta_repair_summary_ignores_legacy_attempts_without_active_context(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "executing",
                    "iteration": 1,
                    "latest_failure": {
                        "kind": "phase_failed",
                        "message": "boom",
                        "recorded_at": "2026-07-03T16:00:00+00:00",
                    },
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

        repair_root = tmp_path / "repair-data"
        repair_root.mkdir(parents=True, exist_ok=True)
        (repair_root / "demo-session.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "attempts": [
                        {"attempt_id": idx, "iteration": idx, "failure_classification": "timeout_or_hang"}
                        for idx in range(1, 6)
                    ],
                    "iterations": [],
                    "current_attempt_id": None,
                    "current_signature": {},
                    "current_recurrence": {},
                    "outcome": "running",
                }
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "plan",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        finding = findings["findings"][0]
        meta = finding["meta_repair_summary"]
        assert meta["should_dispatch"] is False
        assert meta["trigger"] == ""
        assert meta["missing_meta_run_evidence"] is False
        assert not any("meta-repair trigger" in reason for reason in finding["reasons"])

    def test_meta_repair_summary_ignores_running_history_without_active_iteration_context(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "executing",
                    "iteration": 1,
                    "latest_failure": {
                        "kind": "phase_failed",
                        "message": "boom",
                        "recorded_at": "2026-07-03T16:00:00+00:00",
                    },
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

        repair_root = tmp_path / "repair-data"
        repair_root.mkdir(parents=True, exist_ok=True)
        (repair_root / "demo-session.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "attempts": [
                        {
                            "attempt_id": idx,
                            "iteration": idx,
                            "failure_classification": "timeout_or_hang",
                            "dispatched_at": f"2026-07-03T16:0{idx}:00+00:00",
                            "outcome": "running",
                        }
                        for idx in range(1, 6)
                    ],
                    "iterations": [],
                    "current_attempt_id": None,
                    "current_signature": {},
                    "current_recurrence": {},
                    "outcome": "running",
                }
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "plan",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        finding = findings["findings"][0]
        meta = finding["meta_repair_summary"]
        assert meta["should_dispatch"] is False
        assert meta["trigger"] == ""
        assert meta["missing_meta_run_evidence"] is False
        assert "no active attempt/iteration context" in meta["rationale"][0]
        assert not any("meta-repair trigger" in reason for reason in finding["reasons"])

    def test_meta_repair_summary_flags_no_output_launch_failure_artifacts(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "executing",
                    "iteration": 3,
                    "latest_failure": {
                        "kind": "phase_failed",
                        "message": "repair timed out",
                        "recorded_at": "2026-07-03T16:00:00+00:00",
                    },
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

        repair_root = tmp_path / "repair-data"
        meta_dir = repair_root / "meta"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (repair_root / "demo-session.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "outcome": "repair_timeout",
                    "attempts": [
                        {
                            "attempt_id": "attempt-1",
                            "outcome": "repair_timeout",
                            "failure_classification": "timeout_or_hang",
                            "dispatched_at": "2026-07-03T16:00:00+00:00",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (meta_dir / "meta-launch-failed.json").write_text(
            json.dumps(
                {
                    "meta_repair_id": "meta-launch-failed",
                    "session": "demo-session",
                    "trigger": "repair_timeout",
                    "diagnosis": "Codex meta-repair orchestrator returned no output",
                    "subagent_results": {
                        "codex_response": "Not inside a trusted directory and --skip-git-repo-check was not specified."
                    },
                    "outcome": "UNKNOWN",
                }
            ),
            encoding="utf-8",
        )
        meta_runs = tmp_path / "meta-runs"
        meta_runs.mkdir()
        (meta_runs / "20260703T211454Z-demo-session-resp.err").write_text(
            "Not inside a trusted directory and --skip-git-repo-check was not specified.\n",
            encoding="utf-8",
        )
        (meta_runs / "20260703T211454Z-demo-session-resp.txt").write_text(
            "Codex meta-repair orchestrator returned no output (timed out or failed to launch DeepSeek/Hermes subagents).\n",
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "plan",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={
                "MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root),
                "MEGAPLAN_AUDIT_META_RUN_DIR": str(meta_runs),
            },
        )

        finding = findings["findings"][0]
        meta = finding["meta_repair_summary"]
        assert meta["should_dispatch"] is True
        assert meta["trigger"] == "repair_timeout"
        assert meta["failed_meta_run_evidence"] is True
        assert meta["failed_meta_record_count"] == 1
        assert meta["failed_meta_run_count"] >= 1
        assert any(reason.startswith("meta_record_no_verdict:") for reason in finding["reasons"])
        assert any(reason.startswith("meta_repair_launch_failure:") for reason in finding["reasons"])
        assert findings["green_checks"] == []

    @pytest.mark.parametrize(
        "record",
        [
            {"outcome": "commit_custody_failed"},
            {"outcome": "model_tool_launch_failure"},
            {"outcome": "NO_FIX", "diagnosis": "Mutation is not authorized for this launch"},
            {"outcome": "UNKNOWN", "diagnosis": "", "changes": [], "tests": []},
        ],
        ids=["commit-custody", "model-tool-launch", "unauthorized", "empty-unknown"],
    )
    def test_meta_record_empty_or_pre_verdict_shapes_are_negative_evidence(
        self, tmp_path: Path, record: dict
    ) -> None:
        namespace = {
            "_load_json": lambda path: json.loads(path.read_text(encoding="utf-8")),
        }
        source = "\n\n".join(
            [
                _extract_gather_function(
                    "_text_has_meta_launch_failure", "_meta_record_is_launch_failure"
                ),
                _extract_gather_function(
                    "_meta_record_is_launch_failure", "_repair_attempt_signals"
                ),
            ]
        )
        exec(source, namespace)
        path = tmp_path / "meta.json"
        path.write_text(json.dumps(record), encoding="utf-8")

        assert namespace["_meta_record_is_launch_failure"](path) is True

    def test_meta_record_with_accepted_retrigger_is_not_empty_failure(
        self, tmp_path: Path
    ) -> None:
        namespace = {
            "_load_json": lambda path: json.loads(path.read_text(encoding="utf-8")),
        }
        source = "\n\n".join(
            [
                _extract_gather_function(
                    "_text_has_meta_launch_failure", "_meta_record_is_launch_failure"
                ),
                _extract_gather_function(
                    "_meta_record_is_launch_failure", "_repair_attempt_signals"
                ),
            ]
        )
        exec(source, namespace)
        path = tmp_path / "meta.json"
        path.write_text(
            json.dumps(
                {
                    "outcome": "NO_FIX",
                    "post_retrigger_verification": {"accepted": True},
                    "retrigger_command": "arnold-repair-trigger",
                }
            ),
            encoding="utf-8",
        )

        assert namespace["_meta_record_is_launch_failure"](path) is False

    def test_meta_repair_summary_ignores_partial_liveness_for_complete_chain_without_repair_context(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "done",
                    "iteration": 1,
                    "latest_failure": None,
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 1,
                    "current_plan_name": "",
                    "last_state": "done",
                    "completed": [{"label": "m1-demo", "plan": "demo-plan", "status": "done"}],
                }
            ),
            encoding="utf-8",
        )

        repair_root = tmp_path / "repair-data"
        sidecar_events = tmp_path / "repair-data.d" / "events"
        repair_root.mkdir(parents=True, exist_ok=True)
        sidecar_events.mkdir(parents=True, exist_ok=True)
        (repair_root / "index.json").write_text(json.dumps({}), encoding="utf-8")
        (sidecar_events / "events.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "session": "demo-session",
                        "run_kind": "chain",
                        "plan_name": "",
                        "health": "alive",
                        "outcome": "partial_liveness",
                        "recorded_at": f"2026-07-03T22:0{idx}:00+00:00",
                    }
                )
                + "\n"
                for idx in range(4)
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        assert findings["findings"] == []
        assert len(findings["green_checks"]) == 1
        assert findings["green_checks"][0]["plan"] == "demo-plan"

    def test_meta_repair_summary_ignores_partial_liveness_for_live_active_step_after_finalize(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "finalized",
                    "iteration": 1,
                    "latest_failure": None,
                    "active_step": {"phase": "execute", "attempt": 1},
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 0,
                    "current_plan_name": "demo-plan",
                    "last_state": "between_milestones",
                    "completed": [],
                }
            ),
            encoding="utf-8",
        )

        repair_root = tmp_path / "repair-data"
        sidecar_events = tmp_path / "repair-data.d" / "events"
        repair_root.mkdir(parents=True, exist_ok=True)
        sidecar_events.mkdir(parents=True, exist_ok=True)
        (repair_root / "index.json").write_text(json.dumps({}), encoding="utf-8")
        (sidecar_events / "events.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "session": "demo-session",
                        "run_kind": "chain",
                        "plan_name": "demo-plan",
                        "health": "alive",
                        "outcome": "partial_liveness",
                        "recorded_at": f"2026-07-03T22:0{idx}:00+00:00",
                    }
                )
                + "\n"
                for idx in range(4)
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        assert findings["findings"] == []
        assert len(findings["green_checks"]) == 1
        assert findings["green_checks"][0]["plan"] == "demo-plan"

    def test_meta_repair_summary_reconciles_partial_liveness_with_new_chain_target(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "old-plan"
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"name": "old-plan", "current_state": "done", "latest_failure": None}),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 0,
                    "current_plan_name": "new-plan",
                    "last_state": "finalized",
                    "completed": [],
                }
            ),
            encoding="utf-8",
        )

        repair_root = tmp_path / "repair-data"
        sidecar_events = tmp_path / "repair-data.d" / "events"
        repair_root.mkdir(parents=True)
        sidecar_events.mkdir(parents=True)
        (repair_root / "old-session.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "old-session",
                    "outcome": "partial_liveness",
                    "current_attempt_id": 1,
                    "current_advancement_snapshot": {
                        "milestone_or_plan": "superseded-plan",
                        "current_state": "authority_divergence",
                    },
                }
            ),
            encoding="utf-8",
        )
        (sidecar_events / "events.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "session": "old-session",
                        "run_kind": "chain",
                        "plan_name": "superseded-plan",
                        "health": "alive",
                        "outcome": "partial_liveness",
                        "recorded_at": f"2026-07-03T22:0{idx}:00+00:00",
                    }
                )
                + "\n"
                for idx in range(2)
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "old-plan",
                    "session": "old-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        assert findings["findings"] == []
        assert len(findings["green_checks"]) == 1

    def test_gather_flags_watchdog_complete_chain_health_disagreement(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"name": "demo-plan", "current_state": "executing", "iteration": 1}),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 1,
                    "current_plan_name": "demo-plan",
                    "last_state": "between_milestones",
                    "chain_complete": False,
                    "pr_state": "open",
                    "milestones": [{"label": "m1"}, {"label": "m2"}],
                    "completed": [{"label": "m1", "status": "done"}],
                }
            ),
            encoding="utf-8",
        )
        watchdog_report = tmp_path / "watchdog-report.json"
        watchdog_report.write_text(
            json.dumps(
                {
                    "timestamp_utc": "2026-07-04T10:14:01+00:00",
                    "items": [{"session": "demo-session", "plan": "demo-plan", "status": "complete"}],
                }
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_WATCHDOG_REPORT": str(watchdog_report)},
        )

        assert len(findings["findings"]) == 1
        finding = findings["findings"][0]
        assert any("watchdog_chain_health_disagreement" in reason for reason in finding["reasons"])
        assert finding["prior_watchdog_report_refs"][0]["matched_status"] == "complete"
        assert findings["green_checks"] == []

    def test_gather_flags_watchdog_awaiting_merge_after_terminal_chain(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"name": "demo-plan", "current_state": "done", "iteration": 8}),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 2,
                    "current_plan_name": "",
                    "last_state": "done",
                    "chain_complete": True,
                    "pr_state": "merged",
                    "milestones": [{"label": "m1"}, {"label": "m2"}],
                    "completed": [{"label": "m1", "status": "done"}, {"label": "m2", "status": "done"}],
                }
            ),
            encoding="utf-8",
        )
        watchdog_report = tmp_path / "watchdog-report.json"
        watchdog_report.write_text(
            json.dumps(
                {
                    "timestamp_utc": "2026-07-04T10:14:01+00:00",
                    "issues": [{"session": "demo-session", "plan": "demo-plan", "status": "awaiting_pr_merge"}],
                }
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_WATCHDOG_REPORT": str(watchdog_report)},
        )

        assert len(findings["findings"]) == 1
        assert any("watchdog_chain_health_disagreement" in reason for reason in findings["findings"][0]["reasons"])
        assert findings["findings"][0]["prior_watchdog_report_refs"][0]["matched_status"] == "awaiting_pr_merge"

    def test_gather_flags_repair_data_ghost_running(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"name": "demo-plan", "current_state": "done", "iteration": 1}),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 1,
                    "current_plan_name": "",
                    "last_state": "done",
                    "chain_complete": True,
                    "pr_state": "merged",
                    "milestones": [{"label": "m1"}],
                    "completed": [{"label": "m1", "status": "done"}],
                }
            ),
            encoding="utf-8",
        )
        repair_root = tmp_path / "repair-data"
        repair_root.mkdir(parents=True, exist_ok=True)
        (repair_root / "demo-session.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "outcome": "running",
                    "current_attempt_id": "",
                    "attempt_ids": [],
                    "iterations": [],
                }
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        assert len(findings["findings"]) == 1
        assert any("repair_data_ghost_running" in reason for reason in findings["findings"][0]["reasons"])
        assert findings["findings"][0]["repair_data_summary"]["current_attempt_id"] == ""

    def test_gather_flags_complete_repair_with_incomplete_chain(self, tmp_path: Path) -> None:
        """The exact false-success artifact must be visible to the L3 prompt."""
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"name": "demo-plan", "current_state": "finalized", "active_step": {"phase": "execute", "worker_pid": 999999}}),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 1,
                    "current_plan_name": "demo-plan",
                    "last_state": "finalized",
                    "chain_complete": False,
                    "milestones": [{"label": "m1"}, {"label": "m2"}],
                    "completed": [{"label": "m1", "status": "done"}],
                }
            ),
            encoding="utf-8",
        )
        repair_root = tmp_path / "repair-data"
        repair_root.mkdir()
        (repair_root / "demo-session.repair-data.json").write_text(
            json.dumps({"session": "demo-session", "outcome": "complete"}), encoding="utf-8"
        )

        findings = _run_gather_program(
            [{"workspace": str(workspace), "plan": "demo-plan", "session": "demo-session", "kind": "chain", "sources": ["marker"]}],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        assert len(findings["findings"]) == 1
        reasons = findings["findings"][0]["reasons"]
        assert any("repair_complete_incomplete_chain" in reason for reason in reasons)
        assert any("plan_active_step_ghost_worker" in reason for reason in reasons)

    def test_gather_flags_wbc_accepted_unclaimed_exhausted_cycle_for_l3(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.cloud import repair_requests

        session = "workflow-boundary-contracts-corrective-20260710"
        plan = "c1-contract-reality-20260711-1433"
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / plan
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True)
        chain_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": plan,
                    "current_state": "executed",
                    "iteration": 9,
                    "active_step": {"phase": "execute", "worker_pid": 99999999},
                    "latest_failure": {
                        "kind": "blocked_recovery_not_resolved",
                        "message": "machine repair exhausted without advancement",
                    },
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-wbc.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 1,
                    "current_plan_name": plan,
                    "last_state": "blocked",
                    "chain_complete": False,
                    "milestones": [{"label": "c1"}, {"label": "c2"}],
                    "completed": [],
                }
            ),
            encoding="utf-8",
        )
        repair_root = tmp_path / "repair-data"
        repair_root.mkdir()
        (repair_root / f"{session}.repair-data.json").write_text(
            json.dumps(
                {
                    "session": session,
                    "workspace": str(workspace),
                    "outcome": "repair_exhausted",
                    "attempt_ids": [],
                    "iterations": [{"iteration": value} for value in range(1, 10)],
                }
            ),
            encoding="utf-8",
        )
        queue_root = tmp_path / ".megaplan" / "repair-queue"
        queued = repair_requests.enqueue_repair_request(
            queue_root=queue_root,
            session=session,
            workspace=workspace,
            source="legacy_watchdog",
            problem_signature={},
            target={"plan_name": plan},
        )
        assert queued["status"] == "queued"
        coalesced = repair_requests.enqueue_repair_request(
            queue_root=queue_root,
            session=session,
            workspace=workspace,
            source="six_hour_auditor",
            problem_signature={},
            target={"plan_name": plan},
            root_cause_hint="same blocker observed again",
            created_at="2026-07-14T00:00:00Z",
        )
        assert coalesced["status"] == "coalesced"
        repair_requests.write_decision(
            queue_root,
            request_id=queued["request"]["request_id"],
            decision="claim_alert",
            reason="claim retries exhausted without an owner",
            created_at="2026-07-14T00:01:00Z",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": plan,
                    "session": session,
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        finding = findings["findings"][0]
        assert any("stale_l1_l2_cycle" in reason for reason in finding["reasons"])
        assert any(reason.startswith("stale_unclaimed_repair_custody:") for reason in finding["reasons"])
        assert any(reason.startswith("queue_coalesced_without_live_owner:") for reason in finding["reasons"])
        assert findings["green_checks"] == []
        evidence = finding["deterministic_superfixer_evidence"]
        assert evidence["actionable"] is True
        assert evidence["accepted_unclaimed_count"] == 1
        assert evidence["claim_count"] == 0
        assert evidence["attempt_count"] == 0
        assert evidence["repair_outcome"] == "repair_exhausted"
        assert evidence["runner_dead"] is True
        assert evidence["chain_incomplete"] is True
        assert evidence["absent_or_stale_l2"] is True
        assert evidence["retry_budget"]["remaining_attempts"] == 3

    def test_superfixer_cycle_excludes_typed_human_gate_and_fails_closed_on_malformed_evidence(
        self,
    ) -> None:
        namespace: dict[str, object] = {}
        source = "\n\n".join(
            [
                _extract_gather_function(
                    "_chain_state_looks_terminal", "_chain_state_looks_nonterminal"
                ),
                _extract_gather_function(
                    "_chain_state_looks_nonterminal",
                    "_watchdog_chain_health_disagreement_reason",
                ),
                _extract_gather_function(
                    "_superfixer_cycle_evidence", "_stale_l1_l2_cycle_reason"
                ),
            ]
        )
        exec(source, namespace)
        classify = namespace["_superfixer_cycle_evidence"]

        human = classify({"resolver_state": {"canonical_state": "HUMAN_ACTION_REQUIRED"}})
        assert human == {
            "actionable": False,
            "excluded_typed_human_gate": True,
            "canonical_state": "HUMAN_ACTION_REQUIRED",
        }

        malformed = classify(
            {
                "resolver_state": {"canonical_state": "UNKNOWN"},
                "repair_custody_summary": {"malformed_request_count": 1},
                "repair_data_summary": {},
                "active_step_liveness": {
                    "present": True,
                    "worker_pid_alive": False,
                },
                "current_target": {"tmux_process": {"live_status": "dead"}},
                "chain_state_summary": {
                    "current": {
                        "last_state": "blocked",
                        "chain_complete": False,
                        "total_milestones": 2,
                        "completed_count": 0,
                    }
                },
            }
        )
        assert malformed["actionable"] is False
        assert malformed["unknown_evidence"] is True
        assert malformed["canonical_state"] == "UNKNOWN"
        assert malformed["malformed_request_count"] == 1
        assert malformed["excluded_typed_human_gate"] is False

    def test_gather_preserves_repair_wrapper_contract_failure_as_infrastructure(
        self, tmp_path: Path
    ) -> None:
        session = "wrapper-contract-drift"
        plan = "active-plan"
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / plan
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True)
        chain_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": plan,
                    "current_state": "executing",
                    "active_step": {"phase": "execute", "worker_pid": 99999999},
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-wrapper.json").write_text(
            json.dumps(
                {
                    "current_plan_name": plan,
                    "last_state": "blocked",
                    "chain_complete": False,
                    "milestones": [{"label": "m1"}, {"label": "m2"}],
                    "completed": [],
                }
            ),
            encoding="utf-8",
        )
        repair_root = tmp_path / "repair-data"
        repair_root.mkdir()
        (repair_root / f"{session}.repair-data.json").write_text(
            json.dumps(
                {
                    "session": session,
                    "outcome": "fixer_infrastructure_failure",
                    "attempts": [
                        {
                            "attempt_id": 1,
                            "dev_turn_rc": 2,
                            "dev_launch_evidence": {
                                "kind": "managed_launch_contract_failure",
                                "returncode": 2,
                                "managed_run_id": "",
                                "stderr_tail": "required arguments: --trigger-type",
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        payload = _run_gather_program(
            [{"workspace": str(workspace), "plan": plan, "session": session, "kind": "chain"}],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        assert payload["green_checks"] == []
        finding = payload["findings"][0]
        failure = finding["repair_data_summary"]["latest_fixer_infrastructure_failure"]
        assert failure["kind"] == "managed_launch_contract_failure"
        assert failure["returncode"] == 2
        assert finding["deterministic_superfixer_evidence"]["failure_domain"] == "fixer_infrastructure"
        assert any(
            reason.startswith("stale_l1_l2_cycle: fixer infrastructure failed")
            for reason in finding["reasons"]
        )

    def test_meta_repair_summary_ignores_stale_recurring_retry_after_complete_chain(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        chain_dir = workspace / ".megaplan" / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "done",
                    "iteration": 1,
                    "latest_failure": None,
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 1,
                    "current_plan_name": "",
                    "last_state": "done",
                    "completed": [{"label": "m1-demo", "plan": "demo-plan", "status": "done"}],
                }
            ),
            encoding="utf-8",
        )

        repair_root = tmp_path / "repair-data"
        repair_root.mkdir(parents=True, exist_ok=True)
        (repair_root / "demo-session.repair-data.json").write_text(
            json.dumps(
                {
                    "session": "demo-session",
                    "outcome": "discord_escalated",
                    "attempts": [
                        {
                            "attempt_id": idx,
                            "failure_classification": "timeout_or_hang",
                            "outcome": "discord_escalated",
                        }
                        for idx in range(1, 4)
                    ],
                }
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        assert findings["findings"] == []
        assert len(findings["green_checks"]) == 1
        assert findings["green_checks"][0]["plan"] == "demo-plan"

    def test_meta_repair_summary_ignores_partial_liveness_for_live_chain_without_repair_context(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        megaplan_dir = workspace / ".megaplan"
        plan_dir = megaplan_dir / "plans" / "demo-plan"
        chain_dir = megaplan_dir / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "initialized",
                    "iteration": 0,
                    "latest_failure": None,
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text(
            json.dumps({"kind": "llm_token_heartbeat", "ts_utc": "2026-07-04T13:32:23+00:00"}) + "\n",
            encoding="utf-8",
        )
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 0,
                    "current_plan_name": "demo-plan",
                    "last_state": "",
                    "completed": [],
                }
            ),
            encoding="utf-8",
        )
        (megaplan_dir / "cloud-chain-demo-session.log").write_text(
            "L1: [tool] running 2 tools concurrently\nL2: [done] 2/2 tools completed\n",
            encoding="utf-8",
        )

        repair_root = tmp_path / "repair-data"
        sidecar_events = tmp_path / "repair-data.d" / "events"
        repair_root.mkdir(parents=True, exist_ok=True)
        sidecar_events.mkdir(parents=True, exist_ok=True)
        (repair_root / "index.json").write_text(json.dumps({}), encoding="utf-8")
        (sidecar_events / "events.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "session": "demo-session",
                        "run_kind": "chain",
                        "plan_name": "",
                        "health": "alive",
                        "outcome": "partial_liveness",
                        "recorded_at": f"2026-07-04T12:1{idx}:00+00:00",
                    }
                )
                + "\n"
                for idx in range(2)
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root)},
        )

        assert findings["findings"] == []
        assert len(findings["green_checks"]) == 1
        assert findings["green_checks"][0]["plan"] == "demo-plan"

    def test_meta_repair_summary_ignores_partial_liveness_when_watchdog_reports_session_alive(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "arnold"
        megaplan_dir = workspace / ".megaplan"
        plan_dir = megaplan_dir / "plans" / "demo-plan"
        chain_dir = megaplan_dir / "plans" / ".chains"
        plan_dir.mkdir(parents=True, exist_ok=True)
        chain_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "done",
                    "iteration": 1,
                    "latest_failure": None,
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")
        (chain_dir / "chain-demo.json").write_text(
            json.dumps(
                {
                    "current_milestone_index": 1,
                    "current_plan_name": "next-plan",
                    "last_state": "between_milestones",
                    "completed": [{"label": "m1-demo", "plan": "demo-plan", "status": "done"}],
                }
            ),
            encoding="utf-8",
        )

        repair_root = tmp_path / "repair-data"
        sidecar_events = tmp_path / "repair-data.d" / "events"
        repair_root.mkdir(parents=True, exist_ok=True)
        sidecar_events.mkdir(parents=True, exist_ok=True)
        (repair_root / "index.json").write_text(json.dumps({}), encoding="utf-8")
        (sidecar_events / "events.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "session": "demo-session",
                        "run_kind": "chain",
                        "plan_name": "demo-plan",
                        "health": "alive",
                        "outcome": "partial_liveness",
                        "recorded_at": f"2026-07-04T12:1{idx}:00+00:00",
                    }
                )
                + "\n"
                for idx in range(6)
            ),
            encoding="utf-8",
        )

        watchdog_report = tmp_path / "watchdog-report.json"
        watchdog_archive = tmp_path / "watchdog-reports"
        watchdog_archive.mkdir(parents=True, exist_ok=True)
        watchdog_payload = {
            "timestamp_utc": "2026-07-04T13:40:00+00:00",
            "items": [
                {
                    "session": "demo-session",
                    "action": "observe",
                    "status": "alive",
                    "message": "session already alive",
                    "workspace": str(workspace),
                }
            ],
            "issues": [
                {
                    "session": "other-session",
                    "action": "observe",
                    "status": "needs_human",
                    "message": "unrelated issue",
                    "workspace": "/workspace/other/arnold",
                }
            ],
        }
        watchdog_report.write_text(json.dumps(watchdog_payload), encoding="utf-8")
        (watchdog_archive / "20260704T134100Z.json").write_text(json.dumps(watchdog_payload), encoding="utf-8")

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "chain",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={
                "MEGAPLAN_AUDIT_REPAIR_DATA_DIR": str(repair_root),
                "MEGAPLAN_AUDIT_WATCHDOG_REPORT": str(watchdog_report),
                "MEGAPLAN_AUDIT_WATCHDOG_REPORT_ARCHIVE_DIR": str(watchdog_archive),
            },
        )

        assert findings["findings"] == []
        assert len(findings["green_checks"]) == 1
        assert findings["green_checks"][0]["plan"] == "demo-plan"

    def test_collect_watchdog_report_refs_prefer_exact_session_match_over_workspace_basename(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "arnold"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "state.json").write_text(
            json.dumps(
                {
                    "name": "demo-plan",
                    "current_state": "blocked",
                    "iteration": 1,
                    "latest_failure": {
                        "kind": "phase_failed",
                        "message": "boom",
                        "recorded_at": "2026-07-03T16:00:00+00:00",
                    },
                }
            ),
            encoding="utf-8",
        )
        (plan_dir / "events.ndjson").write_text("", encoding="utf-8")

        watchdog_report = tmp_path / "watchdog-report.json"
        watchdog_report.write_text(
            json.dumps(
                {
                    "timestamp_utc": "2026-07-04T13:40:00+00:00",
                    "items": [
                        {
                            "session": "demo-session",
                            "action": "observe",
                            "status": "alive",
                            "message": "session already alive",
                            "workspace": str(workspace),
                        }
                    ],
                    "issues": [
                        {
                            "session": "other-session",
                            "action": "observe",
                            "status": "needs_human",
                            "message": "wrongly matched before exact-session filtering",
                            "workspace": "/workspace/other/arnold",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        findings = _run_gather_program(
            [
                {
                    "workspace": str(workspace),
                    "plan": "demo-plan",
                    "session": "demo-session",
                    "kind": "plan",
                    "sources": ["marker"],
                }
            ],
            tmp_path,
            extra_env={"MEGAPLAN_AUDIT_WATCHDOG_REPORT": str(watchdog_report)},
        )

        assert len(findings["findings"]) == 1
        assert findings["findings"][0]["prior_watchdog_report_refs"][0]["matched_status"] == "alive"


class TestRootCausePatternsJsonSchema:
    """Verify root_cause_patterns JSON payload shape invariants and stable keys."""

    def test_root_cause_patterns_present_when_empty(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [],
                "chain_log_repetitions": [],
                "stale_state_patterns": [],
            },
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        assert "root_cause_patterns" in payload
        rcp = payload["root_cause_patterns"]
        assert set(rcp.keys()) == {
            "repeated_failure_signatures",
            "chain_log_repetitions",
            "stale_state_patterns",
        }
        assert rcp["repeated_failure_signatures"] == []
        assert rcp["chain_log_repetitions"] == []
        assert rcp["stale_state_patterns"] == []

    def test_root_cause_patterns_stable_keys_repeated_failure(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [
                    {
                        "signature": "plan-a|stopped|timeout|msg",
                        "total_occurrences": 4,
                        "affected_plans": ["plan-a", "plan-b"],
                        "affected_sessions": ["sess-a", "sess-b"],
                    }
                ],
                "chain_log_repetitions": [],
                "stale_state_patterns": [],
            },
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        sig = payload["root_cause_patterns"]["repeated_failure_signatures"][0]
        assert set(sig.keys()) == {
            "signature", "total_occurrences", "affected_plans", "affected_sessions",
        }
        assert sig["signature"] == "plan-a|stopped|timeout|msg"
        assert sig["total_occurrences"] == 4
        assert sig["affected_plans"] == ["plan-a", "plan-b"]
        assert sig["affected_sessions"] == ["sess-a", "sess-b"]

    def test_root_cause_patterns_stable_keys_chain_log(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [],
                "chain_log_repetitions": [
                    {
                        "signature": "status_stopped",
                        "total_occurrences": 6,
                        "affected_plans": ["plan-x"],
                        "affected_sessions": ["sess-x"],
                    }
                ],
                "stale_state_patterns": [],
            },
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        item = payload["root_cause_patterns"]["chain_log_repetitions"][0]
        assert set(item.keys()) == {
            "signature", "total_occurrences", "affected_plans", "affected_sessions",
        }
        assert item["signature"] == "status_stopped"
        assert item["total_occurrences"] == 6
        assert item["affected_plans"] == ["plan-x"]

    def test_root_cause_patterns_stable_keys_stale_state(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [],
                "chain_log_repetitions": [],
                "stale_state_patterns": [
                    {
                        "pattern": "latest_failure_is_stale",
                        "plan_count": 3,
                        "affected_plans": ["plan-1", "plan-2", "plan-3"],
                        "affected_sessions": ["sess-1", "sess-2", "sess-3"],
                    }
                ],
            },
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        item = payload["root_cause_patterns"]["stale_state_patterns"][0]
        assert set(item.keys()) == {
            "pattern", "plan_count", "affected_plans", "affected_sessions",
        }
        assert item["pattern"] == "latest_failure_is_stale"
        assert item["plan_count"] == 3
        assert len(item["affected_plans"]) == 3

    def test_root_cause_patterns_default_when_missing_in_data(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        assert "root_cause_patterns" in payload
        rcp = payload["root_cause_patterns"]
        assert rcp["repeated_failure_signatures"] == []
        assert rcp["chain_log_repetitions"] == []
        assert rcp["stale_state_patterns"] == []


class TestRootCausePatternsAggregation:
    """Verify cross-plan aggregation counts, affected plans, and affected sessions."""

    def test_repeated_failure_aggregation_counts(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [
                    {
                        "signature": "sig-a|stopped|timeout",
                        "total_occurrences": 8,
                        "affected_plans": ["alpha", "beta", "gamma"],
                        "affected_sessions": ["s1", "s2", "s3"],
                    },
                    {
                        "signature": "sig-b|executing|stall",
                        "total_occurrences": 3,
                        "affected_plans": ["delta"],
                        "affected_sessions": ["s4"],
                    },
                ],
                "chain_log_repetitions": [],
                "stale_state_patterns": [],
            },
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        sigs = payload["root_cause_patterns"]["repeated_failure_signatures"]
        assert len(sigs) == 2
        assert sigs[0]["total_occurrences"] == 8
        assert sigs[1]["total_occurrences"] == 3
        assert len(sigs[0]["affected_plans"]) == 3

    def test_chain_log_repetition_aggregation(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [],
                "chain_log_repetitions": [
                    {
                        "signature": "awaiting_human",
                        "total_occurrences": 5,
                        "affected_plans": ["plan-aa", "plan-bb"],
                        "affected_sessions": ["aa-sess", "bb-sess"],
                    },
                    {
                        "signature": "repair_loop_exhausted",
                        "total_occurrences": 2,
                        "affected_plans": ["plan-cc"],
                        "affected_sessions": ["cc-sess"],
                    },
                ],
                "stale_state_patterns": [],
            },
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        reps = payload["root_cause_patterns"]["chain_log_repetitions"]
        assert len(reps) == 2
        assert reps[0]["signature"] == "awaiting_human"
        assert reps[0]["total_occurrences"] == 5
        assert reps[1]["signature"] == "repair_loop_exhausted"
        assert reps[1]["total_occurrences"] == 2

    def test_stale_state_pattern_aggregation(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [],
                "chain_log_repetitions": [],
                "stale_state_patterns": [
                    {
                        "pattern": "latest_failure_is_stale",
                        "plan_count": 4,
                        "affected_plans": ["p1", "p2", "p3", "p4"],
                        "affected_sessions": ["s1", "s2", "s3", "s4"],
                    },
                    {
                        "pattern": "stale_block_replay",
                        "plan_count": 2,
                        "affected_plans": ["p5", "p6"],
                        "affected_sessions": ["s5", "s6"],
                    },
                ],
            },
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        stale = payload["root_cause_patterns"]["stale_state_patterns"]
        assert len(stale) == 2
        assert stale[0]["pattern"] == "latest_failure_is_stale"
        assert stale[0]["plan_count"] == 4
        assert stale[1]["pattern"] == "stale_block_replay"
        assert stale[1]["plan_count"] == 2


class TestRootCausePatternsMarkdown:
    """Verify Markdown output for root_cause_patterns."""

    def test_markdown_includes_root_cause_section_with_failure_signatures(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [
                    {
                        "signature": "alpha|stopped|timeout|boom",
                        "total_occurrences": 7,
                        "affected_plans": ["alpha"],
                        "affected_sessions": ["alpha-sess"],
                    }
                ],
                "chain_log_repetitions": [],
                "stale_state_patterns": [],
            },
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "## 🔁 Root-cause patterns (cross-plan)" in md
        assert "### Repeated failure signatures across plans" in md
        assert "alpha|stopped|timeout|boom" in md
        assert "7" in md  # total_occurrences
        assert "alpha" in md

    def test_markdown_includes_chain_log_repetition_section(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [],
                "chain_log_repetitions": [
                    {
                        "signature": "status_stopped",
                        "total_occurrences": 10,
                        "affected_plans": ["plan-stop"],
                        "affected_sessions": ["stop-sess"],
                    }
                ],
                "stale_state_patterns": [],
            },
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "### Chain-log repetition patterns across plans" in md
        assert "status_stopped" in md
        assert "10" in md
        assert "plan-stop" in md

    def test_markdown_includes_stale_state_section(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [],
                "chain_log_repetitions": [],
                "stale_state_patterns": [
                    {
                        "pattern": "between_milestone_cycling",
                        "plan_count": 3,
                        "affected_plans": ["slow-plan-1", "slow-plan-2", "slow-plan-3"],
                        "affected_sessions": ["s1", "s2", "s3"],
                    }
                ],
            },
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "### Stale-state patterns across plans" in md
        assert "between_milestone_cycling" in md
        assert "3 plans" in md

    def test_markdown_omits_root_cause_section_when_all_empty(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [],
                "chain_log_repetitions": [],
                "stale_state_patterns": [],
            },
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "## 🔁 Root-cause patterns" not in md

    def test_markdown_includes_multiple_pattern_types(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "progress_stall:m-tune",
            "findings": [],
            "green_checks": [],
            "root_cause_patterns": {
                "repeated_failure_signatures": [
                    {
                        "signature": "sig-x|stopped",
                        "total_occurrences": 3,
                        "affected_plans": ["plan-x"],
                        "affected_sessions": ["sx"],
                    }
                ],
                "chain_log_repetitions": [
                    {
                        "signature": "pr_closed",
                        "total_occurrences": 4,
                        "affected_plans": ["plan-y"],
                        "affected_sessions": ["sy"],
                    }
                ],
                "stale_state_patterns": [
                    {
                        "pattern": "latest_failure_is_stale",
                        "plan_count": 2,
                        "affected_plans": ["plan-z"],
                        "affected_sessions": ["sz"],
                    }
                ],
            },
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "### Repeated failure signatures across plans" in md
        assert "### Chain-log repetition patterns across plans" in md
        assert "### Stale-state patterns across plans" in md
        assert "sig-x" in md
        assert "pr_closed" in md
        assert "latest_failure_is_stale" in md


class TestAutonomousFixAttemptsJsonSchema:
    """Verify autonomous_fix_attempts shape in JSON payload."""

    def test_field_present_when_empty(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        assert "autonomous_fix_attempts" in payload
        assert payload["autonomous_fix_attempts"] == []

    def test_field_present_with_fixed_attempts(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "fixed-plan",
                    "workspace": "/w/fixed",
                    "session": "fixed-sess",
                    "reasons": ["phase_failed: bug"],
                    "current_state": "executing",
                    "iteration": 5,
                    "last_gate_recommendation": "iterate",
                    "last_gate_score": 3.0,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 2,
                    "recent_gate_total": 3,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [8, 3],
                    "active_step_attempt": None,
                    "latest_failure_kind": "phase_failed",
                    "latest_failure_message": "bug",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": ["marker"],
                    "session_header": {"kind": "chain", "session": "fixed-sess", "workspace": "/w/fixed", "sources": ["marker"]},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "FIXED abc123def\nFixed the null-pointer issue in repair_contract.py",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "FIXED abc123def\nFixed the null-pointer issue in repair_contract.py",
                }
            ],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        assert payload["autonomous_fix_attempts"] == []
        af = payload["risky_or_deferred_fixes"][0]
        assert set(af.keys()) == {"plan", "session", "verdict", "summary"}
        assert af["plan"] == "fixed-plan"
        assert af["session"] == "fixed-sess"
        assert af["verdict"] == "INVALID_MUTATION_CLAIM"
        assert "null-pointer" in af["summary"]

    def test_field_ignores_non_fixed_hypotheses(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "stale-plan",
                    "workspace": "/w/stale",
                    "session": "stale-sess",
                    "reasons": ["stale failure"],
                    "current_state": "executing",
                    "iteration": 3,
                    "last_gate_recommendation": "proceed",
                    "last_gate_score": 7.0,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 0,
                    "recent_gate_total": 2,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [7],
                    "active_step_attempt": None,
                    "latest_failure_kind": None,
                    "latest_failure_message": "",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": ["marker"],
                    "session_header": {"kind": "chain", "session": "stale-sess", "workspace": "/w/stale", "sources": ["marker"]},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "STALE: clear latest_failure and re-drive.",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "STALE: clear latest_failure and re-drive.",
                }
            ],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        assert payload["autonomous_fix_attempts"] == []
        assert payload["risky_or_deferred_fixes"] == []


class TestRiskyOrDeferredFixesJsonSchema:
    """Verify risky_or_deferred_fixes shape in JSON payload."""

    def test_field_present_when_empty(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        assert "risky_or_deferred_fixes" in payload
        assert payload["risky_or_deferred_fixes"] == []

    def test_field_present_with_escalated_findings(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "escalated-plan",
                    "workspace": "/w/esc",
                    "session": "esc-sess",
                    "reasons": ["gate blocked"],
                    "current_state": "executing",
                    "iteration": 8,
                    "last_gate_recommendation": "blocked",
                    "last_gate_score": 2.0,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 3,
                    "recent_gate_total": 3,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [8, 5, 2],
                    "active_step_attempt": None,
                    "latest_failure_kind": "execution_blocked",
                    "latest_failure_message": "gate blocked",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": ["marker"],
                    "session_header": {"kind": "chain", "session": "esc-sess", "workspace": "/w/esc", "sources": ["marker"]},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "ESCALATE\nHuman needs to reconcile gate verdict — fix identified in repair_contract but requires operator approval.",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "ESCALATE\nHuman needs to reconcile gate verdict — fix identified in repair_contract but requires operator approval.",
                }
            ],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        assert len(payload["risky_or_deferred_fixes"]) == 1
        rf = payload["risky_or_deferred_fixes"][0]
        assert set(rf.keys()) == {"plan", "session", "verdict", "summary"}
        assert rf["plan"] == "escalated-plan"
        assert rf["session"] == "esc-sess"
        assert rf["verdict"] == "ESCALATE"
        assert "gate verdict" in rf["summary"]

    def test_empty_when_findings_have_no_hypothesis(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "no-hyp-plan",
                    "workspace": "/w/nh",
                    "session": "nh-sess",
                    "reasons": ["some reason"],
                    "current_state": "executing",
                    "iteration": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 0,
                    "recent_gate_total": 0,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [],
                    "active_step_attempt": None,
                    "latest_failure_kind": None,
                    "latest_failure_message": "",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": [],
                    "session_header": {"kind": "chain", "session": "nh-sess", "workspace": "/w/nh", "sources": []},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                }
            ],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)
        assert payload["autonomous_fix_attempts"] == []
        assert payload["risky_or_deferred_fixes"] == []


class TestAutonomousFixAttemptsMarkdown:
    """Verify Markdown output for autonomous_fix_attempts."""

    def test_empty_state_text_when_no_attempts(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "## 🔧 Autonomous fix attempts" in md
        assert "_No autonomous fixes were attempted during this audit._" in md

    def test_shows_fixed_attempt_with_commit(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "fixed-plan",
                    "workspace": "/w/fixed",
                    "session": "fixed-sess",
                    "reasons": ["bug"],
                    "current_state": "executing",
                    "iteration": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 0,
                    "recent_gate_total": 0,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [],
                    "active_step_attempt": None,
                    "latest_failure_kind": None,
                    "latest_failure_message": "",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": [],
                    "session_header": {"kind": "chain", "session": "fixed-sess", "workspace": "/w/fixed", "sources": []},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "FIXED deadbeef\nPatched the repair loop timeout logic.",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "FIXED deadbeef\nPatched the repair loop timeout logic.",
                }
            ],
            "green_checks": [],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "## 🔧 Autonomous fix attempts" in md
        assert "**fixed-plan**" in md
        assert "deadbeef" in md
        assert "_No autonomous fixes were attempted" in md
        assert "INVALID_MUTATION_CLAIM" in md

    def test_shows_multiple_fixed_attempts(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "fix-a",
                    "workspace": "/w/a",
                    "session": "sess-a",
                    "reasons": ["bug-a"],
                    "current_state": "executing",
                    "iteration": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 0,
                    "recent_gate_total": 0,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [],
                    "active_step_attempt": None,
                    "latest_failure_kind": None,
                    "latest_failure_message": "",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": [],
                    "session_header": {"kind": "chain", "session": "sess-a", "workspace": "/w/a", "sources": []},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "FIXED aaa111\nFixed issue A.",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "FIXED aaa111\nFixed issue A.",
                },
                {
                    "plan": "fix-b",
                    "workspace": "/w/b",
                    "session": "sess-b",
                    "reasons": ["bug-b"],
                    "current_state": "executing",
                    "iteration": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 0,
                    "recent_gate_total": 0,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [],
                    "active_step_attempt": None,
                    "latest_failure_kind": None,
                    "latest_failure_message": "",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": [],
                    "session_header": {"kind": "chain", "session": "sess-b", "workspace": "/w/b", "sources": []},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "FIXED bbb222\nFixed issue B.",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "FIXED bbb222\nFixed issue B.",
                },
            ],
            "green_checks": [],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "**fix-a**" in md
        assert "**fix-b**" in md
        assert "aaa111" in md
        assert "bbb222" in md


class TestRiskyOrDeferredFixesMarkdown:
    """Verify Markdown output for risky_or_deferred_fixes."""

    def test_empty_state_text_when_no_deferred(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "## ⚠️ Risky or deferred fixes" in md
        assert "_No risky or deferred fixes were identified during this audit._" in md

    def test_shows_escalated_finding(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "esc-plan",
                    "workspace": "/w/esc",
                    "session": "esc-sess",
                    "reasons": ["gate blocked"],
                    "current_state": "executing",
                    "iteration": 5,
                    "last_gate_recommendation": "blocked",
                    "last_gate_score": 1.0,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 3,
                    "recent_gate_total": 3,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [5, 1],
                    "active_step_attempt": None,
                    "latest_failure_kind": "execution_blocked",
                    "latest_failure_message": "blocked",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": [],
                    "session_header": {"kind": "chain", "session": "esc-sess", "workspace": "/w/esc", "sources": []},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "ESCALATE\nRequires operator to approve the fix.",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "ESCALATE\nRequires operator to approve the fix.",
                }
            ],
            "green_checks": [],
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "## ⚠️ Risky or deferred fixes" in md
        assert "**esc-plan**" in md
        assert "ESCALATE" in md
        assert "_No risky or deferred fixes" not in md

    def test_mixed_fixed_and_escalated(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [
                {
                    "plan": "fixed-plan",
                    "workspace": "/w/f",
                    "session": "f-sess",
                    "reasons": ["bug"],
                    "current_state": "executing",
                    "iteration": 1,
                    "last_gate_recommendation": None,
                    "last_gate_score": None,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 0,
                    "recent_gate_total": 0,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [],
                    "active_step_attempt": None,
                    "latest_failure_kind": None,
                    "latest_failure_message": "",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": [],
                    "session_header": {"kind": "chain", "session": "f-sess", "workspace": "/w/f", "sources": []},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "FIXED ccc333\nApplied fix.",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "FIXED ccc333\nApplied fix.",
                },
                {
                    "plan": "esc-plan",
                    "workspace": "/w/e",
                    "session": "e-sess",
                    "reasons": ["blocked"],
                    "current_state": "executing",
                    "iteration": 5,
                    "last_gate_recommendation": "blocked",
                    "last_gate_score": 1.0,
                    "plan_v_count": 1,
                    "recent_gate_iterate": 3,
                    "recent_gate_total": 3,
                    "plan_v_sizes": {},
                    "events_size": 0,
                    "score_trajectory": [5, 1],
                    "active_step_attempt": None,
                    "latest_failure_kind": "execution_blocked",
                    "latest_failure_message": "blocked",
                    "latest_failure_is_stale": None,
                    "last_success_after_failure": None,
                    "stale_block_replay": None,
                    "between_milestone_cycling": None,
                    "sources": [],
                    "session_header": {"kind": "chain", "session": "e-sess", "workspace": "/w/e", "sources": []},
                    "chain_log": {},
                    "chain_state_summary": {"current": {}},
                    "repair_data_summary": {},
                    "plan_latest_failure": {},
                    "stale_state_evidence": {},
                    "user_action_context": {},
                    "active_step_phase": None,
                    "events_mtime_age_min": None,
                    "plan_deltas": [],
                    "significant_counts": [],
                    "latest_failure_metadata": {},
                    "hypothesis": "ESCALATE\nNeeds manual review.",
                    "deepseek_model": "deepseek:deepseek-v4-pro",
                    "deepseek_response": "ESCALATE\nNeeds manual review.",
                },
            ],
            "green_checks": [],
        }
        payload, md = _run_report_assembler(findings_data, tmp_path)
        assert payload["autonomous_fix_attempts"] == []
        assert len(payload["risky_or_deferred_fixes"]) == 2
        assert "## 🔧 Autonomous fix attempts" in md
        assert "## ⚠️ Risky or deferred fixes" in md
        assert "**fixed-plan**" in md
        assert "**esc-plan**" in md
        assert "ccc333" in md
        assert "ESCALATE" in md


class TestStageMetrics:
    """Focused `TestStageMetrics` coverage for stage_metrics JSON and Markdown."""

    STAGE_NAMES = [
        "prep", "plan", "critique", "gate", "revise", "finalize",
        "execute", "review", "feedback", "chain", "repair",
        "meta_repair", "human_pr_ci", "deployment_runtime",
    ]

    COUNTER_NAMES = [
        "stalls", "retries", "repair_attempts", "meta_repair_attempts",
        "human_waits", "ci_waits", "handoff_gaps", "no_op_loops",
        "dead_workers", "duration_seconds", "unknowns", "missing_evidence",
    ]

    def _bucket(self, **counters):
        """Build a stage metric bucket with zero counters and optional overrides."""
        bucket = {}
        for c in self.COUNTER_NAMES:
            bucket[c] = counters.get(c, 0)
            bucket[f"{c}_evidence"] = counters.get(f"{c}_evidence", [])
        return bucket

    def _ref(self, ref_type, value, **extra):
        ref = {"type": ref_type, "value": value}
        ref.update(extra)
        return ref

    # ── JSON payload shape for all 14 stages ──────────────────────────

    def test_stage_metrics_json_has_all_14_stages(self, tmp_path: Path) -> None:
        stage_metrics = {stage: self._bucket() for stage in self.STAGE_NAMES}
        stage_metrics["unknown_phase_count"] = 0
        stage_metrics["unknown_phase_evidence"] = []

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": stage_metrics,
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        sm = payload["stage_metrics"]
        for stage in self.STAGE_NAMES:
            assert stage in sm, f"stage_metrics missing key: {stage}"
        assert sm["unknown_phase_count"] == 0
        assert sm["unknown_phase_evidence"] == []

    # ── All 12 counters per stage ─────────────────────────────────────

    def test_stage_metrics_each_stage_has_all_12_counters(self, tmp_path: Path) -> None:
        stage_metrics = {stage: self._bucket() for stage in self.STAGE_NAMES}
        stage_metrics["unknown_phase_count"] = 0
        stage_metrics["unknown_phase_evidence"] = []

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": stage_metrics,
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        for stage in self.STAGE_NAMES:
            bucket = payload["stage_metrics"][stage]
            for c in self.COUNTER_NAMES:
                assert c in bucket, f"{stage} missing counter: {c}"
                assert isinstance(bucket[c], int), f"{stage}.{c} should be int, got {type(bucket[c])}"

    # ── Empty evidence for zero counters ──────────────────────────────

    def test_stage_metrics_zero_counters_have_empty_evidence(self, tmp_path: Path) -> None:
        stage_metrics = {stage: self._bucket() for stage in self.STAGE_NAMES}
        stage_metrics["unknown_phase_count"] = 0
        stage_metrics["unknown_phase_evidence"] = []

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": stage_metrics,
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        for stage in self.STAGE_NAMES:
            bucket = payload["stage_metrics"][stage]
            for c in self.COUNTER_NAMES:
                if bucket[c] == 0:
                    ev = bucket.get(f"{c}_evidence", None)
                    assert ev == [], f"{stage}.{c}_evidence should be [] when counter=0, got {ev}"

    # ── Evidence pointer fields for nonzero counters ──────────────────

    def test_stage_metrics_nonzero_counters_have_evidence_refs(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        # Put nonzero data in the chain stage
        ref = self._ref("watchdog_stall", "stall:test-plan", source="watchdog-report.json")
        sm["chain"]["stalls"] = 2
        sm["chain"]["stalls_evidence"] = [ref]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        chain = payload["stage_metrics"]["chain"]
        assert chain["stalls"] == 2
        assert chain["stalls_evidence"] == [ref]
        assert ref["type"] == "watchdog_stall"
        assert ref["value"] == "stall:test-plan"

    # ── Markdown rendering ────────────────────────────────────────────

    def test_stage_metrics_markdown_section_header_present(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "## Stage metrics" in md

    def test_stage_metrics_markdown_renders_nonzero_stage(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        sm["chain"]["stalls"] = 3
        sm["chain"]["stalls_evidence"] = [
            self._ref("watchdog_stall", "stall:plan-a", source="watchdog-report.json"),
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "**chain**" in md
        assert "stalls=3" in md

    def test_stage_metrics_markdown_empty_state(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)
        assert "_No stage metric data available._" in md

    # ── Synthetic phase durations ─────────────────────────────────────

    def test_stage_metrics_duration_seconds_counter(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        sm["execute"]["duration_seconds"] = 420
        sm["execute"]["duration_seconds_evidence"] = [
            self._ref("phase_duration", "execute", duration_seconds=420, source="events.ndjson"),
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, md = _run_report_assembler(findings_data, tmp_path)

        assert payload["stage_metrics"]["execute"]["duration_seconds"] == 420
        assert "duration=420s" in md
        assert "**execute**" in md

    # ── Repair attempts / retries ─────────────────────────────────────

    def test_stage_metrics_repair_attempts_and_retries(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        sm["repair"]["repair_attempts"] = 4
        sm["repair"]["repair_attempts_evidence"] = [
            self._ref("repair_data", "/tmp/repair-data.json", source="repair-data"),
        ]
        sm["gate"]["retries"] = 3
        sm["gate"]["retries_evidence"] = [
            self._ref("recent_gate_history", "test-plan", source="state.json"),
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, md = _run_report_assembler(findings_data, tmp_path)

        assert payload["stage_metrics"]["repair"]["repair_attempts"] == 4
        assert payload["stage_metrics"]["gate"]["retries"] == 3
        assert "**repair**" in md
        assert "repair_attempts=4" in md
        assert "**gate**" in md
        assert "retries=3" in md

    # ── Watchdog stalls ───────────────────────────────────────────────

    def test_stage_metrics_watchdog_stalls_counter(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        sm["chain"]["stalls"] = 2
        sm["chain"]["stalls_evidence"] = [
            self._ref("watchdog_stall", "progress_stall:m-tune", source="watchdog-report.json"),
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "progress_stall:m-tune",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, md = _run_report_assembler(findings_data, tmp_path)

        assert payload["stage_metrics"]["chain"]["stalls"] == 2
        assert "stalls=2" in md
        assert "**chain**" in md

    # ── Unmapped phases ───────────────────────────────────────────────

    def test_stage_metrics_unmapped_phases_unknown_count(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 5
        sm["unknown_phase_evidence"] = [
            {"phase": "weird_phase", "refs": [self._ref("plan", "test-plan")]},
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, md = _run_report_assembler(findings_data, tmp_path)

        assert payload["stage_metrics"]["unknown_phase_count"] == 5
        assert len(payload["stage_metrics"]["unknown_phase_evidence"]) == 1
        # Markdown renders unknown phases as a separate bullet
        assert "unknown phases" in md

    # ── Missing evidence ──────────────────────────────────────────────

    def test_stage_metrics_missing_evidence_counter(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        sm["execute"]["missing_evidence"] = 3
        sm["execute"]["missing_evidence_evidence"] = [
            self._ref("unpaired_phase_start", "execute", source="events.ndjson"),
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, md = _run_report_assembler(findings_data, tmp_path)

        assert payload["stage_metrics"]["execute"]["missing_evidence"] == 3
        assert "missing_evidence=3" in md
        assert "**execute**" in md

    # ── coverage block ────────────────────────────────────────────────

    def test_coverage_block_shape(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        # Mark one stage as having data
        sm["execute"]["duration_seconds"] = 100

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        cov = payload["coverage"]
        assert cov["total_stages"] == 14
        assert "stages_with_data" in cov
        assert "stages_without_data" in cov
        assert "stages_not_checked" in cov
        assert "execute" in cov["stages_with_data"]
        assert "prep" in cov["stages_without_data"]  # all-zero
        # No stages should be not_checked since all 14 buckets are present
        assert cov["stages_not_checked"] == []

    def test_coverage_block_with_missing_stages(self, tmp_path: Path) -> None:
        # Stage_metrics with only a few stages (simulating partial input)
        sm: dict = {"unknown_phase_count": 0, "unknown_phase_evidence": []}
        sm["chain"] = self._bucket(stalls=1)

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        cov = payload["coverage"]
        # Stages not present in the dict go to stages_not_checked
        assert "prep" in cov["stages_not_checked"]
        assert "chain" in cov["stages_with_data"]
        assert len(cov["stages_not_checked"]) > 0

    # ── data_quality block ────────────────────────────────────────────

    def test_data_quality_block_shape(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 2
        sm["unknown_phase_evidence"] = [{"phase": "unknown_x", "refs": []}]
        sm["execute"]["missing_evidence"] = 1
        sm["execute"]["missing_evidence_evidence"] = [
            self._ref("unpaired_phase_start", "execute", source="events.ndjson"),
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        dq = payload["data_quality"]
        assert dq["unknown_phases"] == 2
        assert len(dq["unknown_phase_evidence"]) == 1
        assert "execute" in dq["stages_with_missing_evidence"]
        assert dq["missing_inputs"] == []
        assert dq["data_sources"]["stage_metrics_available"] is True
        assert dq["data_sources"]["findings_available"] is False
        assert dq["data_sources"]["green_checks_available"] is False

    def test_data_quality_missing_inputs(self, tmp_path: Path) -> None:
        # Only a subset of stages present
        sm: dict = {"unknown_phase_count": 0, "unknown_phase_evidence": []}
        sm["plan"] = self._bucket(duration_seconds=60)

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        dq = payload["data_quality"]
        missing = {m["stage"] for m in dq["missing_inputs"]}
        assert "prep" in missing
        assert "plan" not in missing  # plan IS present
        for m in dq["missing_inputs"]:
            assert m["status"] == "not_checked"

    # ── dispatch_summary block ────────────────────────────────────────

    def test_dispatch_summary_block_present(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        ds = payload["dispatch_summary"]
        assert ds["mode"] == "report_only"
        expected_keys = {
            "mode", "autofix_enabled", "repair_dispatched", "model_dispatched",
            "deepseek_dispatched", "meta_repair_dispatched", "codex_dispatched",
            "git_commit_performed", "file_edit_performed", "rationale",
            "resolved_runtime_model", "dispatch_receipt_count",
            "managed_agent_run_count", "managed_agent_runs", "repair_agent_runs",
        }
        assert set(ds.keys()) == expected_keys

    def test_dispatch_summary_report_only_guard(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        ds = payload["dispatch_summary"]
        assert ds["autofix_enabled"] is False
        assert ds["repair_dispatched"] is False
        assert ds["model_dispatched"] is False
        assert ds["deepseek_dispatched"] is False
        assert ds["meta_repair_dispatched"] is False
        assert ds["codex_dispatched"] is False
        assert ds["git_commit_performed"] is False
        assert ds["file_edit_performed"] is False
        assert "report-only" in ds["rationale"].lower()
        assert "no repair" in ds["rationale"].lower()

    def test_dispatch_summary_launch_attempt_permanently_falsifies_report_only(
        self, tmp_path: Path
    ) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "one finding",
            "findings": [{"plan": "p", "codex_launch_attempted": True}],
            "green_checks": [],
        }

        payload, _md = _run_report_assembler(
            findings_data,
            tmp_path,
            autofix_authorized=True,
        )

        ds = payload["dispatch_summary"]
        assert ds["mode"] == "report_only"
        assert ds["autofix_enabled"] is True
        assert ds["model_dispatched"] is False
        assert ds["codex_dispatched"] is False
        assert payload["data_quality"]["canonical_launch_disagreements"]

    def test_dispatch_summary_rejects_receipt_without_managed_manifest_as_model_authority(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.receipts.writer import (
            finalize_dispatch_receipt,
            initialize_dispatch_receipt,
            prepare_dispatch_receipt,
            record_dispatch_started,
        )

        receipt_root = tmp_path / "receipt-root"
        receipt = initialize_dispatch_receipt(
            receipt_root,
            prepare_dispatch_receipt(action="six_hour_audit", configured_model="stale-config"),
        )
        receipt = record_dispatch_started(
            receipt_root, receipt, resolved_runtime_model="gpt-5.6-sol"
        )
        final = finalize_dispatch_receipt(
            receipt_root,
            receipt,
            outcome="failed",
            resolved_runtime_model="gpt-5.6-sol",
            mutation_facts={"state": False, "source": False, "commit": False, "push": False},
        )
        payload, _md = _run_report_assembler(
            {
                "findings": [{
                    "plan": "p",
                    "dispatch_receipt_root": str(receipt_root),
                    "dispatch_id": final["dispatch_id"],
                    "configured_model": "wrong-report-value",
                }],
                "green_checks": [],
            },
            tmp_path,
        )

        assert payload["dispatch_summary"]["resolved_runtime_model"] is None
        assert payload["dispatch_summary"]["mode"] == "report_only"
        assert payload["dispatch_receipts"][0]["outcome"] == "failed"
        assert payload["data_quality"]["canonical_launch_disagreements"]

    @pytest.mark.parametrize(
        ("master", "path", "authorized"),
        [("0", "0", False), ("0", "1", False), ("1", "0", False), ("1", "1", True)],
    )
    def test_auditor_wrapper_dispatch_matrix_requires_master_and_l3_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        master: str,
        path: str,
        authorized: bool,
    ) -> None:
        monkeypatch.setenv("ARNOLD_AUTONOMY", master)
        monkeypatch.setenv("ARNOLD_AUDIT_AUTOFIX_ENABLED", path)

        assert feature_flags.audit_autofix_mutation_authorized() is authorized
        wrapper = _wrapper("arnold-progress-auditor")
        assert 'if [[ "$AUDIT_MUTATION_AUTHORIZED_FLAG" == "1" ]]' in wrapper
        assert 'AUDIT_LAUNCH_ATTEMPTED=1' in wrapper
        managed_at = wrapper.index("arnold_pipelines.megaplan.managed_agent run")
        worker_at = wrapper.index('timeout "$CODEX_TIMEOUT" codex exec')
        evidence_at = wrapper.index("AUDIT_LAUNCH_ATTEMPTED=1")
        assert managed_at < worker_at < evidence_at

    # ── Multiple nonzero stages in markdown ───────────────────────────

    def test_stage_metrics_markdown_multiple_nonzero_stages(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        sm["plan"]["retries"] = 1
        sm["plan"]["retries_evidence"] = [
            self._ref("chain_log_repetition", "status_stopped", source="chain_log"),
        ]
        sm["chain"]["stalls"] = 2
        sm["chain"]["stalls_evidence"] = [
            self._ref("watchdog_stall", "stall:plan-a", source="watchdog-report.json"),
        ]
        sm["repair"]["repair_attempts"] = 3
        sm["repair"]["repair_attempts_evidence"] = [
            self._ref("repair_data", "/tmp/rd", source="repair-data"),
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "stall:plan-a",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        assert "**plan**" in md
        assert "retries=1" in md
        assert "**chain**" in md
        assert "stalls=2" in md
        assert "**repair**" in md
        assert "repair_attempts=3" in md

    # ── Multiple counter types within a single stage ───────────────────

    def test_stage_metrics_multiple_counters_same_stage(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        sm["human_pr_ci"]["human_waits"] = 4
        sm["human_pr_ci"]["human_waits_evidence"] = [
            self._ref("unresolved_user_actions", "test-plan", source="finalize.json"),
        ]
        sm["human_pr_ci"]["ci_waits"] = 2
        sm["human_pr_ci"]["ci_waits_evidence"] = [
            self._ref("chain_log_repetition", "pr_closed", source="chain_log"),
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, md = _run_report_assembler(findings_data, tmp_path)

        hb = payload["stage_metrics"]["human_pr_ci"]
        assert hb["human_waits"] == 4
        assert hb["ci_waits"] == 2
        assert "**human_pr_ci**" in md
        assert "human_waits=4" in md
        assert "ci_waits=2" in md

    # ── Stage metrics absent from findings_data ────────────────────────

    def test_stage_metrics_absent_from_input(self, tmp_path: Path) -> None:
        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
        }
        payload, md = _run_report_assembler(findings_data, tmp_path)

        # stage_metrics defaults to empty dict
        assert payload["stage_metrics"] == {}
        # coverage marks all stages as not_checked
        assert len(payload["coverage"]["stages_not_checked"]) == 14
        # data_quality marks all stages as missing_inputs
        assert len(payload["data_quality"]["missing_inputs"]) == 14
        assert payload["data_quality"]["data_sources"]["stage_metrics_available"] is False
        # MD shows empty state
        assert "_No stage metric data available._" in md

    # ── Evidence pointers have stable shape ───────────────────────────

    def test_stage_metrics_evidence_pointer_fields_stable(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        ref = self._ref("watchdog_stall", "progress_stall:m-tune",
                        source="watchdog-report.json",
                        plan="test-plan",
                        workspace="/ws/test")
        sm["chain"]["stalls"] = 1
        sm["chain"]["stalls_evidence"] = [ref]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "progress_stall:m-tune",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        payload, _md = _run_report_assembler(findings_data, tmp_path)

        ev = payload["stage_metrics"]["chain"]["stalls_evidence"][0]
        # Stable required fields
        assert ev["type"] == "watchdog_stall"
        assert ev["value"] == "progress_stall:m-tune"
        assert ev["source"] == "watchdog-report.json"
        assert ev["plan"] == "test-plan"
        assert ev["workspace"] == "/ws/test"

    # ── Markdown evidence truncation ──────────────────────────────────

    def test_stage_metrics_markdown_includes_compact_evidence_refs(self, tmp_path: Path) -> None:
        sm = {stage: self._bucket() for stage in self.STAGE_NAMES}
        sm["unknown_phase_count"] = 0
        sm["unknown_phase_evidence"] = []

        sm["chain"]["stalls"] = 1
        sm["chain"]["stalls_evidence"] = [
            self._ref("watchdog_stall", "stall:plan-x", source="watchdog-report.json"),
        ]

        findings_data = {
            "window_hours": 6,
            "stall_summary": "none",
            "findings": [],
            "green_checks": [],
            "stage_metrics": sm,
        }
        _payload, md = _run_report_assembler(findings_data, tmp_path)

        # Evidence refs should appear in brackets
        assert "watchdog_stall:stall:plan-x" in md
