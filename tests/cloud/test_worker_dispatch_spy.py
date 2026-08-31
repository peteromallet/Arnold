from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.workers import _impl
from arnold_pipelines.megaplan.workers._impl import AgentMode
from arnold_pipelines.megaplan.cloud.worker_dispatch import (
    WorkerAdmissionReceipt,
    dispatch_with_admission,
    require_production_worker_dispatch_runtime,
)
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome
from tests.cloud.dispatch_test_helpers import native_proof, request


def test_native_public_door_delegates_to_canonical_production_dispatch(tmp_path: Path, monkeypatch) -> None:
    calls: list[object] = []
    expected = (object(), "codex", "fresh", True)
    monkeypatch.setattr(_impl, "_production_worker_dispatch", lambda *args, **kwargs: calls.append(kwargs) or expected)
    result = _impl.run_step_with_worker(
        "plan", {"meta": {}}, tmp_path, argparse.Namespace(), root=tmp_path,
        resolved=AgentMode("codex", "fresh", True, "gpt-5.5", None, "gpt-5.5"),
        worker_options={"production_intent": True},
    )
    assert result == expected
    assert len(calls) == 1


def test_door_source_has_one_shared_dispatch_loop() -> None:
    source = Path(_impl.__file__).read_text(encoding="utf-8")
    assert source.count("def dispatch_with_admission") == 0
    assert source.count("dispatch_with_admission(") == 1


def test_native_selected_construction_seam_admits_exactly_once(tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []
    proof = native_proof(observed_at=datetime.now(timezone.utc).isoformat())

    def construction_seam(provider: str, model: str, route: str) -> dict[str, object]:
        calls.append((provider, model, route))
        return proof

    result = require_production_worker_dispatch_runtime(
        request(
            tmp_path,
            native_construction_seam=construction_seam,
            route_liveness_resolver=lambda *_: proof,
        )
    )
    assert isinstance(result, WorkerAdmissionReceipt)
    assert calls == [("codex", "gpt-5.5", "codex:gpt-5.5")]


def _typed_terminal(receipt: WorkerAdmissionReceipt, kind: str) -> DispatchOutcome:
    common = dict(
        kind=kind,
        launch_state="accepted",
        plan_id=receipt.plan_id,
        phase=receipt.phase,
        dispatch_family_id=receipt.dispatch_family_id,
        logical_dispatch_id=receipt.logical_dispatch_id,
        admission_receipt_id=receipt.admission_receipt_id,
        semantic_dispatch_fingerprint=receipt.semantic_dispatch_fingerprint,
        selected_spec=receipt.normalized_spec,
        worker_identity={"host": "host", "pid": 123, "boot_id": "boot"},
        started_at="2026-08-30T00:00:00+00:00",
        finished_at="2026-08-30T00:00:01+00:00",
    )
    if kind == "success":
        common["success_payload"] = {"ok": True}
    elif kind == "ordinary_terminal_failure":
        common["terminal_failure"] = {"error": "ordinary"}
    elif kind == "provider_exhausted":
        common["provider_evidence"] = {
            "observation_id": "observation",
            "retryability_class": "availability",
            "exhausted_attempt_count": 1,
            "terminal_provider_evidence_id": "provider-evidence",
            "precondition_identity": "precondition",
            "provider_epoch_identity": "epoch",
            "provider_failure_key": "a" * 64,
            "observed_at": "2026-08-30T00:00:00+00:00",
        }
        common["provider_failure_key"] = "a" * 64
    else:
        common["disposition_id"] = "disposition"
    return DispatchOutcome(**common)


@pytest.mark.parametrize("door", ("native", "omp", "managed"))
def test_physical_door_transports_typed_terminal_categories(tmp_path: Path, door: str) -> None:
    for kind in ("success", "ordinary_terminal_failure", "provider_exhausted", "worker_disposition"):
        root = tmp_path / door / kind
        ledger = IncidentLedger(root)
        receipt = require_production_worker_dispatch_runtime(request(root, ledger=ledger))
        assert isinstance(receipt, WorkerAdmissionReceipt)
        if kind == "worker_disposition":
            original = ledger.append_terminal_outcome
            ledger.append_terminal_outcome = lambda **kwargs: {"payload": {"terminal_outcome_id": "terminal"}}  # type: ignore[method-assign]
        result = dispatch_with_admission(
            request(root, ledger=ledger),
            lambda _context, receipt=receipt, kind=kind: _typed_terminal(receipt, kind),
            ledger=ledger,
            gate=lambda _request, receipt=receipt: receipt,
        )
        assert isinstance(result, DispatchOutcome)
        assert result.kind == kind
        if kind == "worker_disposition":
            ledger.append_terminal_outcome = original  # type: ignore[method-assign]


def test_native_physical_door_transports_typed_terminal_categories(tmp_path: Path) -> None:
    test_physical_door_transports_typed_terminal_categories(tmp_path, "native")


def test_omp_physical_door_transports_typed_terminal_categories(tmp_path: Path) -> None:
    test_physical_door_transports_typed_terminal_categories(tmp_path, "omp")


def test_managed_door_transports_typed_terminal_categories(tmp_path: Path) -> None:
    test_physical_door_transports_typed_terminal_categories(tmp_path, "managed")
