from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.cloud.worker_dispatch import (
    AdmissionRefusal,
    WorkerAdmissionRequest,
    WorkerAdmissionReceipt,
    _default_native_liveness,
    require_production_worker_dispatch_runtime,
)
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.types import CliError


def request(tmp_path: Path, **changes: object) -> WorkerAdmissionRequest:
    values: dict[str, object] = {
        "plan_id": "plan",
        "phase": "execute",
        "dispatch_family_id": "family",
        "logical_dispatch_id": "logical",
        "physical_door_id": "door",
        "configured_spec": "codex:gpt-5.5",
        "selected_spec": "codex:gpt-5.5",
        "source_revision": "a" * 40,
        "runtime_vector": {"runtime": "native"},
        "manifest_identity": "manifest",
        "seed_identity": "seed",
        "dependency_interpreter_identity": "/python",
        "prompt_or_phase_input_identity": "prompt",
        "configured_fallback_chain_identity": "",
        "authorized_route_identity": "codex:gpt-5.5",
        "projection_key": "projection",
        "production_intent": False,
        "ledger_root": tmp_path,
        "route_liveness_resolver": lambda *_: {"kind": "native_backend", "identity": "backend", "digest": "b" * 64},
        "memory_headroom_reader": lambda _spec: {"ok": True, "available_bytes": 10},
        "source_runtime_validator": lambda _request: True,
    }
    values.update(changes)
    return WorkerAdmissionRequest(**values)


def test_invalid_request_is_typed_and_happens_before_reservation(tmp_path: Path) -> None:
    result = require_production_worker_dispatch_runtime({"phase": "execute"})
    assert isinstance(result, AdmissionRefusal)
    assert result.code == "invalid_request"
    assert IncidentLedger(tmp_path).projection()["reservations"] == {}


def test_native_requires_positive_liveness_proof(tmp_path: Path) -> None:
    result = require_production_worker_dispatch_runtime(
        request(tmp_path, route_liveness_resolver=lambda *_: {})
    )
    assert isinstance(result, AdmissionRefusal)
    assert result.code == "route_liveness_invalid"


def test_native_catalog_is_exact_and_rejects_unknown_model(monkeypatch) -> None:
    class Result:
        returncode = 0
        stderr = ""
        stdout = '{"models":[{"slug":"gpt-5.6-sol"}]}'

    monkeypatch.setattr("shutil.which", lambda _binary: "/usr/bin/codex")
    monkeypatch.setattr("pathlib.Path.stat", lambda _path: type("S", (), {"st_dev": 1, "st_ino": 2, "st_mtime_ns": 3, "st_size": 4})())
    runner = lambda *args, **kwargs: Result()
    assert _default_native_liveness("codex", "gpt-5.6-sol", runner=runner)["kind"] == "native_backend"
    import pytest
    with pytest.raises(CliError) as error:
        _default_native_liveness("codex", "not-installed", runner=runner)
    assert error.value.code == "route_liveness_missing"


def test_production_runtime_claims_are_machine_bound(tmp_path: Path) -> None:
    result = require_production_worker_dispatch_runtime(request(tmp_path, production_intent=True))
    assert isinstance(result, AdmissionRefusal)
    assert result.code in {"source_runtime_invalid", "runtime_binding_missing", "runtime_binding_invalid"}


def test_omp_static_catalog_can_accept_expired_id_but_live_gate_rejects(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan.workers.omp import validate_omp_catalog_model

    assert validate_omp_catalog_model("openrouter", "stealth/ox-alpha") == "openrouter/stealth/ox-alpha"
    result = require_production_worker_dispatch_runtime(
        request(
            tmp_path,
            configured_spec="omp:openrouter/stealth/ox-alpha",
            selected_spec="omp:openrouter/stealth/ox-alpha",
            authorized_route_identity="omp:openrouter/stealth/ox-alpha",
            route_liveness_resolver=lambda *_: (_ for _ in ()).throw(CliError("route_liveness_missing", "expired")),
        )
    )
    assert isinstance(result, AdmissionRefusal)
    assert result.code == "route_liveness_missing"


def test_same_fingerprint_cannot_be_evaded_by_new_logical_id(tmp_path: Path) -> None:
    ledger = IncidentLedger(tmp_path)
    first = require_production_worker_dispatch_runtime(request(tmp_path, ledger=ledger))
    assert isinstance(first, WorkerAdmissionReceipt)
    second = require_production_worker_dispatch_runtime(
        request(tmp_path, logical_dispatch_id="another", ledger=ledger)
    )
    assert isinstance(second, AdmissionRefusal)
    assert second.code == "admission_rejected"
