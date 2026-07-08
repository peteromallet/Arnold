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
from pathlib import Path

from arnold_pipelines.megaplan.cloud.redact import REDACTION

REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers"
SYSTEMD_DIR = REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "systemd"


def _wrapper(name: str) -> str:
    return (WRAPPER_DIR / name).read_text(encoding="utf-8")


def _systemd_file(name: str) -> str:
    return (SYSTEMD_DIR / name).read_text(encoding="utf-8")


def _extract_report_assembler() -> str:
    """Extract the final report-assembly Python program from the auditor wrapper."""
    text = _wrapper("arnold-progress-auditor")
    # The report assembler is the last python3 - ... <<'PY' block
    marker = 'python3 - "$GATHER_DIR/findings.json" "$JSON_OUT" "$MD_OUT" "$REPORT_LOG" "$TS" <<\'PY\''
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


def _extract_auditor_function(name: str) -> str:
    text = _wrapper("arnold-progress-auditor")
    start = text.index(f"{name}() {{")
    end = text.index("\n}\n", start) + 3
    return text[start:end]


def _run_gather_program(
    worklist_entries: list[dict],
    tmp_path: Path,
    *,
    arnold_src: Path | None = None,
    extra_env: dict[str, str] | None = None,
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
        env=env,
    )
    assert result.returncode == 0, f"gather program failed: {result.stderr}"
    return json.loads((gather_dir / "findings.json").read_text(encoding="utf-8"))


def _run_report_assembler(
    findings_data: dict, tmp_path: Path, ts: str = "20260702T220000Z"
) -> tuple[dict, str]:
    """Run the report assembler with synthetic findings data and return (json_payload, markdown_text)."""
    program = _extract_report_assembler()
    prog_path = tmp_path / "_report_assembler.py"
    prog_path.write_text(program, encoding="utf-8")

    findings_path = tmp_path / "findings.json"
    json_out = tmp_path / "audit.json"
    md_out = tmp_path / "audit.md"
    log_path = tmp_path / "audit-report.log"

    findings_path.write_text(json.dumps(findings_data), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(prog_path),
            str(findings_path),
            str(json_out),
            str(md_out),
            str(log_path),
            ts,
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
            _extract_auditor_function("dispatch_one"),
            f"WRAPPER_REPO_ROOT={shlex.quote(str(REPO_ROOT))}",
            f"ARNOLD_SRC={shlex.quote(str(REPO_ROOT))}",
            f"GATHER_DIR={shlex.quote(str(gather_dir))}",
            "DEEPSEEK_MODEL=deepseek:deepseek-v4-pro",
            "SUBAGENT_PROFILE=partnered-5",
            "CODEX_TIMEOUT=30",
            'AUDIT_AUTOFIX_ENABLED_FLAG="$(audit_flag_enabled audit_autofix_enabled)"',
            'AUDIT_AUTOFIX_COMMIT_ENABLED_FLAG="$(audit_flag_enabled audit_autofix_commit_enabled)"',
            "dispatch_one " + shlex.quote(str(gather_file)),
        ]
    )
    env = dict(os.environ)
    env["PATH"] = f"{tmp_path}:{env.get('PATH', '')}"
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

            findings_path.write_text(json.dumps(findings_data), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(prog_path),
                    str(findings_path),
                    str(json_out),
                    str(md_out),
                    str(fresh_log),
                    "20260702T220000Z",
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

        assert "Autofix mode: REPORT-ONLY." in brief
        assert "Do not edit files, apply patches, or run `git commit` / `git push`." in brief
        assert "Repair-SYSTEM PATCH-ONLY" not in brief
        assert "commit and push" not in brief.lower()

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

        assert "Autofix mode: REPAIR-SYSTEM PATCH-ONLY." in brief
        assert "Leave changes uncommitted; do not run `git commit` or `git push`." in brief
        assert "`arnold_pipelines/megaplan/cloud/**`" in brief
        assert "`tests/cloud/**`" in brief
        assert "Never modify the audited run workspace" in brief
        assert "git push to `origin/editible-install`" not in brief

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

        assert "Autofix mode: REPAIR-SYSTEM PATCH + COMMIT/PUSH (explicitly gated)." in brief
        assert "git commit` and `git push` to `origin/editible-install`." in brief
        assert "Leave changes uncommitted" not in brief

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
        assert "bearer-secret-token-value" not in updated["deepseek_response"]
        assert REDACTION in brief
        assert REDACTION in resp
        assert REDACTION in err
        assert REDACTION in updated["deepseek_response"]
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
        assert Path(finding["source_refs"]["incident_summary_path"]).exists()

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
        assert any("failed launch/no-output evidence" in reason for reason in finding["reasons"])

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
        assert len(payload["autonomous_fix_attempts"]) == 1
        af = payload["autonomous_fix_attempts"][0]
        assert set(af.keys()) == {"plan", "session", "commit", "summary"}
        assert af["plan"] == "fixed-plan"
        assert af["session"] == "fixed-sess"
        assert af["commit"] == "abc123def"
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
        assert "_No autonomous fixes were attempted" not in md

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
        assert len(payload["autonomous_fix_attempts"]) == 1
        assert len(payload["risky_or_deferred_fixes"]) == 1
        assert "## 🔧 Autonomous fix attempts" in md
        assert "## ⚠️ Risky or deferred fixes" in md
        assert "**fixed-plan**" in md
        assert "**esc-plan**" in md
        assert "ccc333" in md
        assert "ESCALATE" in md
