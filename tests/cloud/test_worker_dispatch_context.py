from __future__ import annotations

from arnold_pipelines.megaplan.cloud.worker_dispatch import WorkerExecutionContextRef


def test_execution_context_round_trips_through_environment() -> None:
    context = WorkerExecutionContextRef("/ledger", "plan", "phase", "family", "logical", "receipt", "f" * 64, "codex:gpt-5.5", "door")
    restored = WorkerExecutionContextRef.from_environment(context.to_environment())
    assert restored == context


def test_execution_context_rejects_unknown_or_missing_fields() -> None:
    import pytest

    with pytest.raises(ValueError):
        WorkerExecutionContextRef.from_dict({"ledger_root": "/ledger"})
