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
        [sys.executable, "-m", "megaplan", *args],
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
