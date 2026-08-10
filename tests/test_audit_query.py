from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_megaplan(args: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env["PYTHONPATH"] = str(REPO_ROOT)
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "arnold_pipelines.megaplan", *args],
        cwd=cwd,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _receipt(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "timestamp_utc": "2026-04-24T12:00:00+00:00",
        "plan_id": "plan-a",
        "phase": "execute",
        "profile_name": "standard",
        "model_configured": "glm-5.1",
        "model_actual": None,
        "duration_ms": 1234,
        "cost_usd": 0.25,
        "scope_drift_severity": "high",
        "verdict": "success",
    }
    data.update(overrides)
    return data


def test_audit_query_json_filters_model_and_phase(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    receipts = [
        _receipt(),
        _receipt(plan_id="plan-b", phase="plan", model_configured="kimi-k2", duration_ms=50, cost_usd=0.01),
    ]
    (audit_dir / "receipts.jsonl").write_text(
        "".join(json.dumps(receipt) + "\n" for receipt in receipts),
        encoding="utf-8",
    )

    result = _run_megaplan(
        [
            "audit",
            "query",
            "--model",
            "glm-5.1",
            "--phase",
            "execute",
            "--audit-dir",
            str(audit_dir),
            "--json",
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload) == 1
    assert payload[0]["duration_ms"] == 1234
    assert payload[0]["cost_usd"] == 0.25
    assert payload[0]["scope_drift_severity"] == "high"
    assert payload[0]["verdict"] == "success"


def test_audit_plan_without_query_returns_legacy_payload(tmp_path: Path) -> None:
    root = tmp_path / "root"
    plan_dir = root / ".megaplan" / "plans" / "audit-query-plan"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "audit-query-plan",
        "current_state": "planned",
        "config": {"project_dir": str(tmp_path / "project")},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")

    result = _run_megaplan(["audit", "--plan", "audit-query-plan"], cwd=root)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["step"] == "audit"
    assert payload["plan"] == "audit-query-plan"
    assert payload["state"]["current_state"] == "planned"


def test_audit_report_renders_markdown_from_plan_receipts(tmp_path: Path) -> None:
    root = tmp_path / "root"
    plan_dir = root / ".megaplan" / "plans" / "audit-report-plan"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "audit-report-plan",
        "current_state": "planned",
        "iteration": 2,
        "created_at": "2026-05-21T12:00:00Z",
        "config": {"project_dir": str(root), "profile": "partnered", "robustness": "full", "mode": "code"},
        "meta": {"total_cost_usd": 2.5},
        "active_step": {"step": "critique", "agent": "codex", "worker_pid": 1234},
        "history": [],
        "sessions": {},
    }
    (plan_dir / "state.json").write_text(json.dumps(state) + "\n", encoding="utf-8")
    (plan_dir / "step_receipt_plan_v1.json").write_text(
        json.dumps(
            {
                "phase": "plan",
                "iteration": 1,
                "result": "success",
                "agent": "codex",
                "model_actual": "gpt-5.5",
                "duration_ms": 120000,
                "cost_usd": 0.5,
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "output_file": "plan_v1.md",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "gate.json").write_text(
        json.dumps({"recommendation": "ITERATE", "must_fix": [{"id": "FLAG-1"}], "settled_decisions": []}) + "\n",
        encoding="utf-8",
    )

    result = _run_megaplan(["audit", "report", "--plan", "audit-report-plan"], cwd=root)

    assert result.returncode == 0, result.stderr
    assert "# Megaplan Audit Report: audit-report-plan" in result.stdout
    assert "| plan | 1 | success | codex | gpt-5.5 | 2m 0s | $0.5000 | 1,000 | 200 | `plan_v1.md` |" in result.stdout
    assert "Gate recommendation: `ITERATE`" in result.stdout


def test_audit_report_prefers_dispatch_receipt_runtime_model(tmp_path: Path) -> None:
    root = tmp_path / "root"
    plan_dir = root / ".megaplan" / "plans" / "dispatch-model-report"
    receipt_dir = plan_dir / "dispatch_receipts"
    receipt_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "dispatch-model-report",
                "current_state": "done",
                "config": {"project_dir": str(root)},
                "meta": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (receipt_dir / "repair-001.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "dispatch_id": "repair-001",
                "action": "automatic_repair",
                "configured_model": "stale-configured-model",
                "resolved_runtime_model": "gpt-5.6-sol",
                "subprocess_started": True,
                "outcome": "succeeded",
                "mutation_facts": {"state": False, "source": True, "commit": False, "push": False},
                "updated_at_utc": "2026-07-10T12:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_megaplan(["audit", "report", "--plan", "dispatch-model-report"], cwd=root)

    assert result.returncode == 0, result.stderr
    assert (
        "| automatic_repair | `repair-001` | gpt-5.6-sol | stale-configured-model | true | succeeded |"
        in result.stdout
    )


def test_audit_report_can_write_markdown_and_json_payload(tmp_path: Path) -> None:
    root = tmp_path / "root"
    plan_dir = root / ".megaplan" / "plans" / "audit-report-files"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "audit-report-files",
                "current_state": "done",
                "config": {"project_dir": str(root), "profile": "partnered"},
                "meta": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    md_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"

    result = _run_megaplan(
        [
            "audit",
            "report",
            "--plan",
            "audit-report-files",
            "--output",
            str(md_path),
            "--json-output",
            str(json_path),
        ],
        cwd=root,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["step"] == "audit_report"
    assert md_path.read_text(encoding="utf-8").startswith("# Megaplan Audit Report: audit-report-files")
    assert json.loads(json_path.read_text(encoding="utf-8"))["plan"] == "audit-report-files"


def test_receipts_jsonl_is_jq_friendly(tmp_path: Path) -> None:
    jq = shutil.which("jq")
    if jq is None:
        return
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    receipts_path = audit_dir / "receipts.jsonl"
    receipts_path.write_text(
        json.dumps(_receipt(phase="execute")) + "\n"
        + json.dumps(_receipt(phase="plan", model_configured="kimi-k2")) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [jq, ".phase", str(receipts_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['"execute"', '"plan"']
