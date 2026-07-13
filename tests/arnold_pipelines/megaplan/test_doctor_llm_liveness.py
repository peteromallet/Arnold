"""Regression coverage for provider-neutral doctor LLM correlation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from arnold_pipelines.megaplan.observability.doctor import _check_llm_liveness


def test_doctor_accepts_recent_active_step_liveness_for_requestless_call(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    events = [
        {
            "kind": "llm_call_start",
            "phase": "execute",
            "ts_utc": (now - timedelta(minutes=5)).isoformat(),
            "payload": {"model": "gpt-5.6-sol", "request_id": None},
        },
        {
            "kind": "llm_call_end",
            "phase": "execute",
            "ts_utc": (now - timedelta(minutes=3)).isoformat(),
            "payload": {"model": "gpt-5.4", "request_id": "late-provider-id"},
        },
        {
            "kind": "llm_call_start",
            "phase": "execute",
            "ts_utc": (now - timedelta(minutes=2)).isoformat(),
            "payload": {"model": "gpt-5.6-sol", "request_id": None},
        },
    ]
    (plan_dir / "events.ndjson").write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "active_step": {
                    "phase": "execute",
                    "model": "gpt-5.6-sol",
                    "last_activity_at": (now - timedelta(seconds=10)).isoformat(),
                }
            }
        ),
        encoding="utf-8",
    )

    severity, label, _ = _check_llm_liveness(plan_dir)

    assert severity == "OK"
    assert label == "LLM liveness"


def test_doctor_warns_when_current_requestless_call_and_worker_liveness_are_stale(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "events.ndjson").write_text(
        json.dumps(
            {
                "kind": "llm_call_start",
                "phase": "execute",
                "ts_utc": (now - timedelta(minutes=5)).isoformat(),
                "payload": {"model": "gpt-5.6-sol", "request_id": None},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "active_step": {
                    "phase": "execute",
                    "model": "gpt-5.6-sol",
                    "last_activity_at": (now - timedelta(minutes=2)).isoformat(),
                }
            }
        ),
        encoding="utf-8",
    )

    severity, label, message = _check_llm_liveness(plan_dir)

    assert severity == "WARN"
    assert "no heartbeat" in label
    assert "may be wedged" in message
