from __future__ import annotations

import json

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
