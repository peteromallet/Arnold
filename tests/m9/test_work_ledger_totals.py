"""M9 proof tests for work-ledger accounting totals."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.observability.work_ledger import (
    LEDGER_FILE,
    WorkClass,
    emit_productive,
    emit_queue_idle,
    emit_replay,
    emit_review_proof,
    emit_strategy_m4_baseline_events,
    emit_validation,
)


MEASURE_FIELDS = (
    "elapsed_ms",
    "model_calls",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "accepted_output_delta",
)


def _records(plan_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (plan_dir / LEDGER_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, dict[str, int | float]] = defaultdict(
        lambda: {field: 0 for field in MEASURE_FIELDS}
    )
    unknown_denominators: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for index, record in enumerate(records):
        work_class = record["work_class"]
        row_id = record.get("task_id") or record.get("attempt_id") or f"row-{index}"
        for field in MEASURE_FIELDS:
            value = record.get(field)
            if value is None:
                unknown_denominators[work_class][field].append(
                    f"{row_id}:{record.get('unavailable_reason')}"
                )
            else:
                totals[work_class][field] += value
    return {
        "totals": {work_class: dict(values) for work_class, values in totals.items()},
        "unknown_denominators": {
            work_class: {field: tuple(values) for field, values in fields.items()}
            for work_class, fields in unknown_denominators.items()
        },
    }


def test_totals_preserve_productive_and_review_proof_as_first_class_work(
    tmp_path: Path,
) -> None:
    emit_productive(
        tmp_path,
        task_id="T-impl",
        elapsed_ms=2000,
        model_calls=1,
        prompt_tokens=100,
        completion_tokens=40,
        total_tokens=140,
        cost_usd=0.014,
        accepted_output_delta=25,
    )
    emit_review_proof(
        tmp_path,
        task_id="T-proof",
        elapsed_ms=800,
        model_calls=1,
        prompt_tokens=70,
        completion_tokens=20,
        total_tokens=90,
        cost_usd=0.009,
        accepted_output_delta=3,
    )
    emit_validation(tmp_path, task_id="T-check", elapsed_ms=150)
    emit_queue_idle(tmp_path, batch_id="batch-35", elapsed_ms=30)

    summary = _summarize(_records(tmp_path))

    assert summary["totals"]["productive"] == {
        "elapsed_ms": 2000,
        "model_calls": 1,
        "prompt_tokens": 100,
        "completion_tokens": 40,
        "total_tokens": 140,
        "cost_usd": 0.014,
        "accepted_output_delta": 25,
    }
    assert summary["totals"]["review_proof"] == {
        "elapsed_ms": 800,
        "model_calls": 1,
        "prompt_tokens": 70,
        "completion_tokens": 20,
        "total_tokens": 90,
        "cost_usd": 0.009,
        "accepted_output_delta": 3,
    }
    assert "waste" not in {record["work_class"] for record in _records(tmp_path)}


def test_unknown_denominators_are_exposed_not_coerced_to_zero(tmp_path: Path) -> None:
    emit_productive(
        tmp_path,
        task_id="T-unknown-usage",
        elapsed_ms=1000,
        unavailable_reason="provider_usage_missing",
    )
    emit_review_proof(
        tmp_path,
        task_id="T-unknown-review",
        unavailable_reason="review_worker_usage_missing",
    )
    emit_replay(
        tmp_path,
        task_id="T-replay",
        elapsed_ms=250,
        unavailable_reason="replay_uses_existing_batch_artifact",
    )

    summary = _summarize(_records(tmp_path))

    assert summary["totals"]["productive"]["elapsed_ms"] == 1000
    assert summary["totals"]["productive"]["total_tokens"] == 0
    assert summary["unknown_denominators"]["productive"]["total_tokens"] == (
        "T-unknown-usage:provider_usage_missing",
    )
    assert summary["unknown_denominators"]["review_proof"]["elapsed_ms"] == (
        "T-unknown-review:review_worker_usage_missing",
    )
    assert summary["unknown_denominators"]["replay"]["total_tokens"] == (
        "T-replay:replay_uses_existing_batch_artifact",
    )


def test_strategy_m4_baseline_remains_productive_and_review_proof(tmp_path: Path) -> None:
    emit_strategy_m4_baseline_events(tmp_path)

    records = _records(tmp_path)
    summary = _summarize(records)

    assert [record["work_class"] for record in records] == [
        WorkClass.PRODUCTIVE.value,
        WorkClass.REVIEW_PROOF.value,
    ]
    assert summary["totals"]["productive"]["elapsed_ms"] == 7_397_000
    assert summary["unknown_denominators"]["productive"]["total_tokens"] == (
        "row-0:strategy_m4_historical_usage_unavailable",
    )
    assert summary["unknown_denominators"]["review_proof"]["elapsed_ms"] == (
        "row-1:strategy_m4_historical_review_usage_unavailable",
    )
    assert records[0]["metadata"]["classification_guard"] == (
        "productive_implementation_not_waste"
    )
    assert records[1]["metadata"]["classification_guard"] == (
        "required_review_not_waste"
    )
