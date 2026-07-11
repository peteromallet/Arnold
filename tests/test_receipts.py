"""Fault-injection coverage for authoritative automatic-dispatch receipts."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from arnold_pipelines.megaplan.receipts import writer


def _prepared(dispatch_id: str = "dispatch-001") -> writer.AutomaticDispatchReceipt:
    return writer.prepare_dispatch_receipt(
        action="automatic-repair",
        configured_model="configured-model",
        dispatch_id=dispatch_id,
        created_at_utc="2026-07-10T00:00:00+00:00",
    )


def _journal(plan_dir: Path) -> list[dict[str, object]]:
    path = plan_dir / "dispatch_receipts" / "lifecycle.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_launch_observes_durable_identity_initialization_and_snapshot(tmp_path: Path) -> None:
    """All initialization custody is readable before automatic launch begins."""
    plan_dir = tmp_path / "plan"
    receipt = _prepared()
    observations: list[dict[str, object]] = []

    def launch() -> object:
        receipt_dir = plan_dir / "dispatch_receipts"
        snapshot = json.loads((receipt_dir / "dispatch-001.json").read_text())
        observations.append(
            {
                "identity": (receipt_dir / "dispatch-001.identity").read_text().strip(),
                "journal": _journal(plan_dir),
                "snapshot": snapshot,
            }
        )
        return object()

    started, process = writer.initialize_and_launch_dispatch(plan_dir, receipt, launch)

    assert process is not None
    assert observations == [
        {
            "identity": "dispatch-001",
            "journal": [mock.ANY],
            "snapshot": mock.ANY,
        }
    ]
    initialized = observations[0]["journal"][0]  # type: ignore[index]
    snapshot = observations[0]["snapshot"]
    assert initialized == snapshot
    assert initialized["sequence"] == 1
    assert initialized["subprocess_started"] is False
    assert initialized["outcome"] == "initialized"
    assert started["sequence"] == 2
    assert started["subprocess_started"] is True


def test_snapshot_initialization_failure_forbids_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A journal append without its initialized snapshot is not launch authority."""
    plan_dir = tmp_path / "plan"
    launch = mock.Mock()

    def fail_snapshot(*_args: object, **_kwargs: object) -> None:
        raise OSError("snapshot unavailable")

    monkeypatch.setattr(writer, "atomic_write_json", fail_snapshot)

    with pytest.raises(writer.DispatchInitializationError) as caught:
        writer.initialize_and_launch_dispatch(plan_dir, _prepared(), launch)

    assert launch.call_count == 0
    assert caught.value.stage == "initialization"
    assert caught.value.receipt["subprocess_started"] is False
    assert caught.value.receipt["outcome"] == "blocked"
    assert _journal(plan_dir)[0]["outcome"] == "initialized"
    assert not writer.dispatch_receipt_path(plan_dir, "dispatch-001").exists()


def test_initialization_append_failure_forbids_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An identity alone cannot authorize launch when lifecycle append fails."""
    plan_dir = tmp_path / "plan"
    launch = mock.Mock()

    def fail_append(*_args: object, **_kwargs: object) -> None:
        raise OSError("append unavailable")

    monkeypatch.setattr(writer, "_append_authoritative_jsonl", fail_append)

    with pytest.raises(writer.DispatchInitializationError) as caught:
        writer.initialize_and_launch_dispatch(plan_dir, _prepared(), launch)

    assert launch.call_count == 0
    assert caught.value.stage == "initialization"
    assert caught.value.receipt["subprocess_started"] is False
    assert (plan_dir / "dispatch_receipts" / "dispatch-001.identity").exists()
    assert not (plan_dir / "dispatch_receipts" / "lifecycle.jsonl").exists()
    assert not writer.dispatch_receipt_path(plan_dir, "dispatch-001").exists()


def test_identity_fsync_failure_forbids_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The subprocess cannot start when identity durability cannot be proven."""
    launch = mock.Mock()
    real_fsync = writer.os.fsync
    calls = 0

    def fail_first_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("identity fsync unavailable")
        real_fsync(fd)

    monkeypatch.setattr(writer.os, "fsync", fail_first_fsync)

    with pytest.raises(writer.DispatchInitializationError) as caught:
        writer.initialize_and_launch_dispatch(tmp_path / "plan", _prepared(), launch)

    assert calls == 1
    assert launch.call_count == 0
    assert caught.value.receipt["failure_stage"] == "initialization"
    assert caught.value.receipt["subprocess_started"] is False


def test_post_launch_append_failure_is_explicit_and_indeterminate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failure to persist the started transition cannot erase the real launch."""
    plan_dir = tmp_path / "plan"
    launch = mock.Mock(return_value=object())
    real_append = writer._append_authoritative_jsonl
    append_count = 0

    def fail_started_append(path: Path, payload: dict[str, object]) -> None:
        nonlocal append_count
        append_count += 1
        if append_count == 2:
            raise OSError("started append unavailable")
        real_append(path, payload)

    monkeypatch.setattr(writer, "_append_authoritative_jsonl", fail_started_append)

    with pytest.raises(writer.DispatchFinalizationError) as caught:
        writer.initialize_and_launch_dispatch(plan_dir, _prepared(), launch)

    assert launch.call_count == 1
    assert caught.value.stage == "subprocess_started"
    assert caught.value.receipt["subprocess_started"] is True
    assert caught.value.receipt["outcome"] == "indeterminate"
    assert caught.value.receipt["mutation_facts"] == {
        "state": None,
        "source": None,
        "commit": None,
        "push": None,
    }
    assert [event["sequence"] for event in _journal(plan_dir)] == [1]


def test_finalization_failure_preserves_started_and_factual_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed final write reports the attempted facts but not a false outcome."""
    plan_dir = tmp_path / "plan"
    initialized = writer.initialize_dispatch_receipt(plan_dir, _prepared())
    started = writer.record_dispatch_started(
        plan_dir,
        initialized,
        resolved_runtime_model="runtime-model",
    )

    def fail_finalization(*_args: object, **_kwargs: object) -> None:
        raise OSError("final append unavailable")

    monkeypatch.setattr(writer, "_persist_dispatch_transition", fail_finalization)

    with pytest.raises(writer.DispatchFinalizationError) as caught:
        writer.finalize_dispatch_receipt(
            plan_dir,
            started,
            outcome="failed",
            mutation_facts={"state": True, "source": False, "commit": False, "push": False},
            detail="child exited 1",
        )

    assert caught.value.stage == "finalization"
    assert caught.value.receipt["subprocess_started"] is True
    assert caught.value.receipt["outcome"] == "indeterminate"
    assert caught.value.receipt["failure_stage"] == "finalization"
    assert caught.value.receipt["resolved_runtime_model"] == "runtime-model"
    assert caught.value.receipt["mutation_facts"] == {
        "state": True,
        "source": False,
        "commit": False,
        "push": False,
    }
    assert [event["outcome"] for event in _journal(plan_dir)] == ["initialized", "running"]


def test_completed_lifecycle_records_runtime_evidence_and_mutation_facts(tmp_path: Path) -> None:
    """Configured intent, runtime evidence, outcomes, and facts remain distinct."""
    plan_dir = tmp_path / "plan"
    initialized = writer.initialize_dispatch_receipt(plan_dir, _prepared())
    started = writer.record_dispatch_started(
        plan_dir,
        initialized,
        resolved_runtime_model="runtime-model",
    )
    final = writer.finalize_dispatch_receipt(
        plan_dir,
        started,
        outcome="succeeded",
        mutation_facts={"state": True, "source": True, "commit": False, "push": False},
        detail="observed child result",
    )

    assert started["configured_model"] == "configured-model"
    assert started["resolved_runtime_model"] == "runtime-model"
    assert started["outcome"] == "running"
    assert all(value is None for value in started["mutation_facts"].values())
    assert final["subprocess_started"] is True
    assert final["outcome"] == "succeeded"
    assert final["mutation_facts"] == {
        "state": True,
        "source": True,
        "commit": False,
        "push": False,
    }
    events = _journal(plan_dir)
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert [event["outcome"] for event in events] == ["initialized", "running", "succeeded"]
    assert json.loads(writer.dispatch_receipt_path(plan_dir, "dispatch-001").read_text()) == final


@pytest.mark.parametrize("telemetry_writer", [writer.write_receipt, writer.write_boundary_receipt])
def test_unrelated_telemetry_remains_best_effort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    telemetry_writer: object,
) -> None:
    """The authoritative dispatch contract does not harden unrelated telemetry."""
    def fail_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("telemetry unavailable")

    monkeypatch.setattr(writer, "atomic_write_json", fail_write)
    if telemetry_writer is writer.write_receipt:
        writer.write_receipt(tmp_path / "plan", {"phase": "execute", "iteration": 1})
    else:
        receipt = mock.Mock()
        receipt.to_dict.return_value = {"boundary_id": "automatic-dispatch"}
        receipt.boundary_id = "automatic-dispatch"
        writer.write_boundary_receipt(tmp_path / "plan", receipt)
