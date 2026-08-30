from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.cloud.worker_dispatch import (
    AdmissionRefusal,
    WorkerAdmissionReceipt,
    dispatch_with_admission,
    LaunchResult,
    _normalize_outcome,
)
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome, SchedulingCondition

from tests.cloud.dispatch_test_helpers import request


WORKER = {"host": "host", "pid": 123, "boot_id": "boot"}


def test_cooldown_retries_without_launch_and_then_admits(tmp_path: Path) -> None:
    waits: list[float] = []
    launches: list[int] = []
    now = [0.0]
    cooldowns = iter((2.0, 0.0))

    def clock() -> float:
        return now[0]

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        now[0] += seconds

    def gate(req):
        from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
        return require_production_worker_dispatch_runtime(
            req,
            # consume the injected cooldown deterministically per attempt
        )

    original = request(tmp_path, cooldown_reader=lambda *_: next(cooldowns))
    result = dispatch_with_admission(
        original,
        lambda _context: (launches.append(1), WORKER)[1],
        gate=gate,
        clock=clock,
        sleeper=sleep,
        deadline_s=10,
    )
    assert isinstance(result, DispatchOutcome)
    assert result.kind == "success"
    assert waits == [2.0]
    assert len(launches) == 1


def test_scheduling_expiry_returns_condition_without_launch(tmp_path: Path) -> None:
    launches: list[int] = []
    result = dispatch_with_admission(
        request(tmp_path, cooldown_reader=lambda *_: 5.0),
        lambda _context: launches.append(1),
        clock=lambda: 0.0,
        sleeper=lambda _seconds: None,
        deadline_s=1.0,
    )
    assert isinstance(result, SchedulingCondition)
    assert result.reason == "memory_cooldown"
    assert launches == []


def test_gate_refusal_prevents_final_launch(tmp_path: Path) -> None:
    launches: list[int] = []
    result = dispatch_with_admission(
        request(tmp_path, seed_identity=""),
        lambda _context: launches.append(1),
    )
    assert isinstance(result, AdmissionRefusal)
    assert launches == []


def test_wrapped_integer_is_not_a_typed_success(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.cloud.worker_dispatch import require_production_worker_dispatch_runtime
    from pytest import raises

    receipt = require_production_worker_dispatch_runtime(request(tmp_path))
    assert isinstance(receipt, WorkerAdmissionReceipt)
    with raises(ValueError, match="primitive launch results"):
        _normalize_outcome(LaunchResult(accepted=True, value=7, worker_identity=WORKER), receipt, "s", "f")
