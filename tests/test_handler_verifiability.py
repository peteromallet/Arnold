from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from megaplan.handlers import verifiability as verifiability_module
from megaplan.handlers.verifiability import get_human_verification_status


def test_get_human_verification_status_latest_verdict_controls_pending(tmp_path: Path) -> None:
    plan_meta = {
        "success_criteria": [
            {"criterion": "browser proof", "priority": "must", "requires": ["drive_browser"]},
            {"criterion": "logs attached", "priority": "should", "requires": ["drive_browser"]},
        ]
    }
    (tmp_path / "human_verifications.json").write_text(
        json.dumps(
            [
                {"criterion_idx": 0, "timestamp": "2026-05-25T10:00:00Z", "verdict": "pass"},
                {"criterion_idx": 0, "timestamp": "2026-05-25T11:00:00Z", "verdict": "fail"},
                {"criterion_idx": 1, "timestamp": "2026-05-25T12:00:00Z", "verdict": "pass"},
            ]
        ),
        encoding="utf-8",
    )

    status = get_human_verification_status(
        tmp_path,
        plan_meta,
        worker_caps={"codex": {"run_tests"}},
    )

    assert status["verified"] == 1
    assert status["pending"] == 1
    assert status["all_deferred_must_verified"] is False
    assert status["rows"][0]["latest_verdict"] == "fail"
    assert status["rows"][0]["verified"] is False
    assert status["rows"][1]["latest_verdict"] == "pass"
    assert status["rows"][1]["verified"] is True


def test_get_human_verification_status_same_timestamp_uses_last_file_entry(tmp_path: Path) -> None:
    plan_meta = {
        "success_criteria": [
            {"criterion": "browser proof", "priority": "must", "requires": ["drive_browser"]},
        ]
    }
    verifications_path = tmp_path / "human_verifications.json"
    verifications_path.write_text(
        json.dumps(
            [
                {"criterion_idx": 0, "timestamp": "2026-05-25T10:00:00Z", "verdict": "fail"},
                {"criterion_idx": 0, "timestamp": "2026-05-25T10:00:00Z", "verdict": "pass"},
            ]
        ),
        encoding="utf-8",
    )

    status = get_human_verification_status(
        tmp_path,
        plan_meta,
        worker_caps={"codex": {"run_tests"}},
    )

    assert status["pending"] == 0
    assert status["verified"] == 1
    assert status["all_deferred_must_verified"] is True
    assert status["rows"][0]["latest_verdict"] == "pass"
    assert status["rows"][0]["latest_timestamp"] == "2026-05-25T10:00:00Z"


def test_verify_human_list_uses_worker_capabilities_for_pending_count(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_meta = {
        "success_criteria": [
            {"criterion": "unit tests pass", "priority": "must", "requires": ["run_tests"]},
            {"criterion": "browser inspected", "priority": "must", "requires": ["drive_browser"]},
        ]
    }
    meta_path = tmp_path / "plan.meta.json"
    meta_path.write_text(json.dumps(plan_meta), encoding="utf-8")
    (tmp_path / "human_verifications.json").write_text(
        json.dumps(
            [
                {
                    "criterion_idx": 1,
                    "timestamp": "2026-05-25T10:00:00Z",
                    "verdict": "pass",
                }
            ]
        ),
        encoding="utf-8",
    )
    state = {
        "name": "demo",
        "current_state": "done",
        "config": {"workers": {"codex": {"verifies": ["run_tests"]}}},
    }

    monkeypatch.setattr(
        verifiability_module,
        "load_plan",
        lambda _root, _plan: (tmp_path, state),
    )
    monkeypatch.setattr(
        verifiability_module,
        "latest_plan_meta_path",
        lambda _plan_dir, _state: meta_path,
    )

    result = verifiability_module.handle_verify_human(
        tmp_path,
        Namespace(plan="demo", list_flag=True, json_flag=True),
    )

    assert result["pending"] == 0
    assert result["all_deferred_must_verified"] is True
    assert result["rows"][0]["deferred_must"] is False
    assert result["rows"][1]["deferred_must"] is True
