from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from arnold_pipelines.megaplan._core.state import make_history_entry, set_active_step
from arnold_pipelines.megaplan.cli.status_view import _build_status_payload
from arnold_pipelines.megaplan.observability.routing_ledger import LEDGER_FILE, record_step_routing
from arnold_pipelines.megaplan.receipts import build_receipt
from arnold_pipelines.megaplan.receipts.report import _phase_rows, render_audit_report_markdown
from arnold_pipelines.megaplan.workers import WorkerResult


def test_record_step_routing_includes_fallback_observability_fields(tmp_path: Path) -> None:
    record_step_routing(
        tmp_path,
        phase="critique",
        step_label="check_1",
        agent="claude",
        selected_spec="claude:claude-sonnet-4-6:high",
        resolved_model="claude-sonnet-4-6",
        actual_model="claude-sonnet-4-6",
        configured_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        attempt_index=1,
        attempted_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        failed_attempt_reasons=("availability",),
        fallback_trigger="availability",
    )

    rows = (tmp_path / LEDGER_FILE).read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["selected_spec"] == "claude:claude-sonnet-4-6:high"
    assert payload["configured_specs"] == [
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    ]
    assert payload["attempted_specs"] == [
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    ]
    assert payload["selected_spec_index"] == 1
    assert payload["selected_spec_total"] == 2
    assert payload["fallback_trigger"] == "availability"
    assert payload["failed_attempt_reasons"] == ["availability"]


def test_record_step_routing_ignores_removed_plan_directory(tmp_path: Path, caplog) -> None:
    removed_plan_dir = tmp_path / "removed-plan"

    record_step_routing(
        removed_plan_dir,
        phase="plan",
        step_label="plan",
        agent="codex",
        selected_spec="codex:gpt-5.5",
        resolved_model="gpt-5.5",
        actual_model="gpt-5.5",
    )

    assert not removed_plan_dir.exists()
    assert "Routing ledger write failed" not in caplog.text


def test_build_receipt_prefers_selected_attempt_and_emits_fallback_fields(tmp_path: Path) -> None:
    state = {
        "name": "demo-plan",
        "iteration": 1,
        "config": {"project_dir": str(tmp_path), "profile": "demo"},
        "meta": {},
    }
    args = argparse.Namespace(
        phase_model=['execute=__fallback_json__:["codex:gpt-5.5:high","claude:claude-sonnet-4-6:high"]'],
        hermes=None,
        agent=None,
        profile="demo",
    )
    worker = SimpleNamespace(
        payload={},
        receipt_metrics={},
        model_actual="claude-sonnet-4-6",
        session_id=None,
        cost_usd=0.0,
        duration_ms=0,
        prompt_tokens=0,
        completion_tokens=0,
        worker_channel=None,
        auth_channel=None,
        auth_metadata=None,
        configured_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        attempt_index=1,
        attempted_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        failed_attempt_reasons=("availability",),
        fallback_trigger="availability",
    )

    receipt = build_receipt(
        phase="execute",
        state=state,
        plan_dir=tmp_path,
        args=args,
        worker=worker,
        agent="claude",
        mode="persistent",
        output_file="execute.json",
        artifact_hash="sha256:test",
        verdict="success",
    )

    assert receipt["model_configured"] == "claude:claude-sonnet-4-6:high"
    assert receipt["configured_specs"] == [
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    ]
    assert receipt["attempted_specs"] == [
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    ]
    assert receipt["selected_spec_index"] == 1
    assert receipt["selected_spec_total"] == 2
    assert receipt["fallback_trigger"] == "availability"
    assert receipt["failed_attempt_reasons"] == ["availability"]


def test_status_payload_exposes_active_step_fallback_fields(tmp_path: Path) -> None:
    state = {
        "name": "demo-plan",
        "current_state": "planning",
        "iteration": 1,
        "config": {"mode": "code"},
        "meta": {},
        "history": [],
        "sessions": {},
        "plan_versions": [],
    }
    set_active_step(
        state,
        step="plan",
        agent="claude",
        mode="persistent",
        model="claude-sonnet-4-6",
        configured_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        attempt_index=1,
        attempted_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        failed_attempt_reasons=("availability",),
        fallback_trigger="availability",
    )

    payload = _build_status_payload(tmp_path, state)

    assert payload["active_step"]["configured_specs"] == [
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    ]
    assert payload["active_step"]["attempted_specs"] == [
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    ]
    assert payload["active_step"]["selected_spec_index"] == 1
    assert payload["active_step"]["selected_spec_total"] == 2
    assert payload["active_step"]["fallback_trigger"] == "availability"
    assert payload["active_step"]["failed_attempt_reasons"] == ["availability"]


def test_history_and_reporting_include_fallback_fields() -> None:
    worker = WorkerResult(
        payload={},
        raw_output="",
        duration_ms=10,
        cost_usd=0.25,
        configured_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        attempt_index=1,
        attempted_specs=("codex:gpt-5.5:high", "claude:claude-sonnet-4-6:high"),
        failed_attempt_reasons=("availability",),
        fallback_trigger="availability",
    )
    history_entry = make_history_entry(
        "critique",
        duration_ms=worker.duration_ms,
        cost_usd=worker.cost_usd,
        result="success",
        worker=worker,
        agent="claude",
        mode="persistent",
        output_file="critique_v1.json",
        artifact_hash="sha256:test",
    )

    assert history_entry["configured_specs"] == [
        "codex:gpt-5.5:high",
        "claude:claude-sonnet-4-6:high",
    ]
    assert history_entry["selected_spec_index"] == 1
    assert history_entry["selected_spec_total"] == 2

    rows = _phase_rows(
        [
            {
                "_file": "step_receipt_critique_v1.json",
                "phase": "critique",
                "iteration": 1,
                "agent": "claude",
                "model_configured": "claude:claude-sonnet-4-6:high",
                "configured_specs": history_entry["configured_specs"],
                "attempted_specs": history_entry["attempted_specs"],
                "selected_spec_index": history_entry["selected_spec_index"],
                "selected_spec_total": history_entry["selected_spec_total"],
                "fallback_trigger": history_entry["fallback_trigger"],
                "failed_attempt_reasons": history_entry["failed_attempt_reasons"],
            }
        ],
        {"history": [history_entry]},
    )

    assert rows[0]["configured_specs"] == history_entry["configured_specs"]
    assert rows[0]["attempted_specs"] == history_entry["attempted_specs"]
    assert rows[0]["selected_spec_index"] == 1
    assert rows[0]["selected_spec_total"] == 2
    assert rows[0]["fallback_trigger"] == "availability"
    assert rows[0]["failed_attempt_reasons"] == ["availability"]

    markdown = render_audit_report_markdown(
        {
            "plan": "demo-plan",
            "plan_dir": "/tmp/demo-plan",
            "state": "planning",
            "iteration": 1,
            "profile": "demo",
            "robustness": "medium",
            "mode": "code",
            "total_cost_usd_upper_bound": 0.25,
            "receipt_totals": {
                "duration_ms": 10.0,
                "cost_usd": 0.25,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
            "active_step": {
                "phase": "critique",
                "agent": "claude",
                "attempt": 2,
                "worker_pid": 123,
                "last_activity_at": "2026-07-04T00:00:00Z",
                "last_activity_kind": "heartbeat",
                "configured_specs": history_entry["configured_specs"],
                "attempted_specs": history_entry["attempted_specs"],
                "selected_spec_index": history_entry["selected_spec_index"],
                "selected_spec_total": history_entry["selected_spec_total"],
                "fallback_trigger": history_entry["fallback_trigger"],
                "failed_attempt_reasons": history_entry["failed_attempt_reasons"],
            },
            "phase_rows": rows,
            "warnings": [],
            "gate": None,
            "execution": None,
            "phase_result": None,
            "artifacts": [],
        }
    )

    assert "Selected fallback attempt" in markdown
    assert "Configured specs" in markdown
