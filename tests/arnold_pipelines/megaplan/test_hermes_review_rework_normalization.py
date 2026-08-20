"""Worker-side normalization of review rework_items (occurrence 1f1f5d10145b).

The hermes worker's structural audit runs BEFORE the review handler's
canonical backfill (handlers/review.py _normalize_review_payload).  A review
produced by a fallback provider may carry a top-level ``task_id`` without
``target.task_id`` / ``target.task_ids`` and omit ``deterministic_check`` —
shapes the handler explicitly tolerates.  Without worker-side normalization
such a semantically complete review is rejected by the worker audit and the
phase loops on ``worker_structural_audit_failed``.

These tests pin the normalization: the audit-visible shape after
``clean_parsed_payload`` equals the canonical shape the handler backfill
produces.
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.workers.hermes import clean_parsed_payload


def _review_payload_with_rework_item(**overrides) -> dict:
    payload = {
        "review_verdict": "needs_rework",
        "criteria": [],
        "issues": ["stale frozen schema digests"],
        "rework_items": [
            {
                "task_id": "T5A",
                "issue": "frozen digests stale",
                "expected": "digests refreshed from live source",
                "actual": "digests stale",
                "evidence_file": "arnold_pipelines/megaplan/maintenance/handoffs.py",
                "target": {
                    "kind": "bulk",
                    "id": "bulk-frozen-schema-digest-refresh",
                    "task_ids": ["T5A", "T6"],
                },
            }
        ],
        "summary": "needs rework",
        "task_verdicts": [],
        "sense_check_verdicts": [],
        "review_completion_status": "complete",
    }
    payload.update(overrides)
    return payload


def test_review_rework_item_target_task_id_backfilled_from_top_level() -> None:
    payload = _review_payload_with_rework_item()
    clean_parsed_payload(payload, {}, "review")
    item = payload["rework_items"][0]
    assert item["target"]["task_id"] == "T5A"
    assert item["target"]["task_ids"] == ["T5A", "T6"]
    assert item["target"]["kind"] == "bulk"
    assert item["target"]["id"] == "bulk-frozen-schema-digest-refresh"


def test_review_rework_item_deterministic_check_defaulted() -> None:
    payload = _review_payload_with_rework_item()
    clean_parsed_payload(payload, {}, "review")
    item = payload["rework_items"][0]
    assert "deterministic_check" in item
    assert item["deterministic_check"] is None


def test_review_rework_item_deterministic_check_evidence_file_defaulted() -> None:
    payload = _review_payload_with_rework_item(
        rework_items=[
            {
                "task_id": "T29",
                "issue": "x",
                "expected": "y",
                "actual": "z",
                "evidence_file": "tests/foo.py",
                "target": {"kind": "task", "task_id": "T29"},
                "deterministic_check": {
                    "command": "pytest tests/foo.py -q",
                    "baseline_status": "passed",
                    "post_status": "failed",
                },
            }
        ]
    )
    clean_parsed_payload(payload, {}, "review")
    item = payload["rework_items"][0]
    assert item["deterministic_check"]["evidence_file"] is None
    assert item["deterministic_check"]["command"] == "pytest tests/foo.py -q"


def test_review_without_rework_items_is_unchanged() -> None:
    payload = _review_payload_with_rework_item(rework_items=[])
    clean_parsed_payload(payload, {}, "review")
    assert payload["rework_items"] == []


def test_review_normalization_only_applies_to_review_step() -> None:
    # The same shape must NOT be mutated for a non-review step.
    payload = _review_payload_with_rework_item()
    clean_parsed_payload(payload, {}, "critique")
    item = payload["rework_items"][0]
    assert "task_id" not in item["target"]
    assert "deterministic_check" not in item


@pytest.mark.parametrize(
    "malformed",
    [
        {"rework_items": None},
        {"rework_items": "not-a-list"},
        {"rework_items": [42]},
    ],
)
def test_review_rework_items_malformed_does_not_raise(malformed: dict) -> None:
    payload = _review_payload_with_rework_item(**malformed)
    clean_parsed_payload(payload, {}, "review")  # must not raise
