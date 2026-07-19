from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan import auto


def _write_state(plan_dir: Path, history: list[dict[str, object]]) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_dir.name,
                "current_state": "critiqued",
                "history": history,
            }
        ),
        encoding="utf-8",
    )


def test_later_same_phase_success_supersedes_historical_failure(tmp_path: Path) -> None:
    plan_dir = tmp_path / "demo"
    _write_state(
        plan_dir,
        [
            {
                "step": "gate",
                "result": "error",
                "timestamp": "2026-07-16T15:30:03Z",
                "message": "worker_structural_audit_failed: enum_mismatch",
            },
            {
                "step": "gate",
                "result": "success",
                "timestamp": "2026-07-16T15:32:13Z",
                "recommendation": "ITERATE",
            },
            {"step": "revise", "result": "success"},
            {"step": "critique", "result": "success"},
        ],
    )

    repeat = auto._repeated_failure_signature(
        plan_dir,
        {"state": "critiqued", "next_step": "revise"},
    )

    assert repeat is None


def test_repeated_polling_does_not_recount_one_history_failure(tmp_path: Path) -> None:
    plan_dir = tmp_path / "demo"
    _write_state(
        plan_dir,
        [
            {
                "step": "gate",
                "result": "error",
                "timestamp": "2026-07-16T15:30:03Z",
                "message": "worker_structural_audit_failed: enum_mismatch",
            }
        ],
    )
    status = {"state": "critiqued", "next_step": "revise"}
    repeat = auto._repeated_failure_signature(plan_dir, status)
    assert repeat is not None

    signature, occurrence, count = auto._update_repeated_failure_counter(
        repeat,
        tracked_signature=None,
        tracked_occurrence=None,
        count=0,
    )
    for _ in range(5):
        same_poll = auto._repeated_failure_signature(plan_dir, status)
        signature, occurrence, count = auto._update_repeated_failure_counter(
            same_poll,
            tracked_signature=signature,
            tracked_occurrence=occurrence,
            count=count,
        )

    assert count == 1

    _write_state(
        plan_dir,
        [
            {
                "step": "gate",
                "result": "error",
                "timestamp": "2026-07-16T15:30:03Z",
                "message": "worker_structural_audit_failed: enum_mismatch",
            },
            {
                "step": "gate",
                "result": "error",
                "timestamp": "2026-07-16T15:31:03Z",
                "message": "worker_structural_audit_failed: enum_mismatch",
            },
        ],
    )
    new_occurrence = auto._repeated_failure_signature(plan_dir, status)
    signature, occurrence, count = auto._update_repeated_failure_counter(
        new_occurrence,
        tracked_signature=signature,
        tracked_occurrence=occurrence,
        count=count,
    )

    assert count == 2
    assert occurrence == new_occurrence["occurrence_id"]
