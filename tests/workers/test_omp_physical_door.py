"""Physical-door tests for the production OMP worker.

These tests intentionally enter ``_run_omp_with_admission`` and the production
``run_omp_step`` route.  Only backend observations, RPC construction, and the
WBC adapter are faked; the canonical admission and dispatch gate remain live.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from arnold_pipelines.megaplan.cloud import runtime_attestation, runtime_provenance
from arnold_pipelines.megaplan.cloud import worker_dispatch
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.incident.schema import WorkerDisposition
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.workers import omp
from arnold_pipelines.megaplan.workers import _impl
from arnold_pipelines.megaplan.workers._impl import WorkerResult
from arnold.agent.contracts import AgentMode, AgentResult
from tests._workers_helpers import _mock_state
from tests.workers.fake_omp_rpc import FakeRpcClient, make_turn


class _Wbc:
    def __init__(self) -> None:
        self.calls = 0
        self.client_calls = 0

    def run(self, dispatch):
        self.calls += 1
        value = dispatch(None)
        if isinstance(value, WorkerResult) and value.worker_identity is None:
            value.worker_identity = {
                "host": "omp-test-worker",
                "pid": 42,
                "boot_id": "omp-test-boot",
            }
        return SimpleNamespace(worker_result=value)


class _TypedWbc(_Wbc):
    def __init__(self, root: Path, kind: str, *, forged_identity: bool = False) -> None:
        super().__init__()
        self.root = root
        self.kind = kind
        self.forged_identity = forged_identity
        # The higher-level dispatcher wrapper reads these custody fields from
        # a real CommonWorkerDispatchResult.  Keep this fake beneath the OMP
        # door structurally compatible without replacing that wrapper.
        self.artifacts = None
        self.attempt_id = "omp-higher-level"
        self.expected_source_version = "source.v1"
        self.start_source_lookup_key = "start"
        self.success_source_lookup_key = "complete"

    def run(self, dispatch):
        self.calls += 1
        value = dispatch(None)
        if isinstance(value, tuple):
            marker = SimpleNamespace(append_result=None)
            terminal = SimpleNamespace(
                append_result=None,
                promotion_mode=SimpleNamespace(value="action_off"),
                artifacts=None,
            )
            return SimpleNamespace(
                worker_result=value,
                start=SimpleNamespace(attempt_id="omp-higher-level"),
                terminal=terminal,
                diagnostics={"writer_id": "test", "surface_name": "test"},
            )
        admission = next(
            item["payload"]
            for item in reversed(IncidentLedger(self.root).read_nbf_events())
            if item["payload"].get("event_type") == "admission_reserved"
        )
        identity = {"host": "omp", "pid": 42, "boot_id": "omp-boot"}
        if self.forged_identity:
            identity = {"host": "forged", "pid": 99, "boot_id": "forged-boot"}
        common: dict[str, Any] = {
            "kind": self.kind,
            "launch_state": "accepted",
            "plan_id": admission["plan_id"],
            "phase": admission["phase"],
            "dispatch_family_id": admission["dispatch_family_id"],
            "logical_dispatch_id": admission["logical_dispatch_id"],
            "admission_receipt_id": admission["admission_receipt_id"],
            "semantic_dispatch_fingerprint": admission["semantic_dispatch_fingerprint"],
            "selected_spec": admission["selected_spec"],
            "worker_identity": identity,
            "started_at": "2026-08-31T00:00:00+00:00",
            "finished_at": "2026-08-31T00:00:01+00:00",
        }
        if self.kind == "ordinary_terminal_failure":
            common["terminal_failure"] = {"code": "provider_bad_payload"}
        elif self.kind == "provider_exhausted":
            key = "a" * 64
            common["provider_failure_key"] = key
            common["provider_evidence"] = {
                "observation_id": "obs",
                "retryability_class": "availability",
                "exhausted_attempt_count": 1,
                "terminal_provider_evidence_id": "evidence",
                "precondition_identity": "precondition",
                "provider_epoch_identity": "epoch",
                "provider_failure_key": key,
                "observed_at": "2026-08-31T00:00:00+00:00",
            }
        elif self.kind == "worker_disposition":
            common["disposition_id"] = "disposition-1"
            # The terminal writer must link an already durable disposition;
            # This must be a complete canonical disposition, with every
            # admission coordinate copied from the durable reservation.
            IncidentLedger(self.root).append_disposition(
                WorkerDisposition(
                    disposition_id="disposition-1",
                    mode="in_band",
                    plan_id=admission["plan_id"],
                    phase=admission["phase"],
                    dispatch_family_id=admission["dispatch_family_id"],
                    logical_dispatch_id=admission["logical_dispatch_id"],
                    admission_receipt_id=admission["admission_receipt_id"],
                    semantic_dispatch_fingerprint=admission["semantic_dispatch_fingerprint"],
                    selected_spec=admission["selected_spec"],
                    killer_kind="watchdog",
                    killer_identity="omp-supervisor",
                    cause_kind="wedge",
                    signal="SIGTERM",
                    elapsed_s=1.0,
                    worker_identity=identity,
                    observed_at="2026-08-31T00:00:00+00:00",
                    evidence={"positive": True},
                ).to_dict()
            )
        return SimpleNamespace(worker_result=DispatchOutcome(**common))


def _payload() -> dict[str, Any]:
    return {
        "plan": "# Implementation Plan\n\n## Step 1: Do it\n\n- [ ] thing",
        "questions": [],
        "success_criteria": [{"criterion": "c", "priority": "must"}],
        "assumptions": [],
    }


@pytest.fixture
def production(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Install positive system observations while retaining the real gate."""
    provenance = {"ok": True, "source_revision": "revision", "runtime": "fixture"}
    seed_path = tmp_path / "runtime-seed.json"
    seed_path.write_text("seed", encoding="utf-8")
    manifest_path = tmp_path / "runtime-manifest.json"
    manifest_path.write_text("manifest", encoding="utf-8")
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    seed = {
        "expected_revision": provenance["source_revision"],
        "runtime_provenance": provenance,
        "manifest_sha256": manifest_sha,
        "dependency_generation": {"interpreter_path": str(Path(sys.executable).resolve())},
        "interpreter": {"executable": str(Path(sys.executable).resolve())},
    }
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest_path))
    monkeypatch.setenv("MEGAPLAN_RUNTIME_LAUNCH_SEED", str(seed_path))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(runtime_attestation, "configured_seed_path", lambda: seed_path)
    monkeypatch.setattr(runtime_attestation, "_json_file", lambda *_args, **_kwargs: seed)
    monkeypatch.setattr(runtime_attestation, "validate_runtime_launch_seed", lambda *_args, **_kwargs: {"status": "ready"})
    monkeypatch.setattr(runtime_provenance, "runtime_provenance", lambda **_kwargs: provenance)
    from arnold_pipelines.megaplan.runtime import memory_headroom

    monkeypatch.setattr(memory_headroom, "memory_cooldown_wait_secs", lambda *_args, **_kwargs: 0.0)
    monkeypatch.setattr(memory_headroom, "classify_memory_headroom", lambda *_args, **_kwargs: {"ok": True})
    catalog_calls: list[tuple[Any, ...]] = []

    def run_catalog(*args, **kwargs):
        catalog_calls.append(args)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"models": ["deepseek/deepseek-v4-pro"]}),
            stderr="",
        )

    monkeypatch.setattr(worker_dispatch.subprocess, "run", run_catalog)
    return tmp_path, catalog_calls


def _rpc_factory(monkeypatch: pytest.MonkeyPatch):
    client = FakeRpcClient()

    def factory(**kwargs):
        for key, value in kwargs.items():
            setattr(client, key, value)

        def turn():
            result = client.custom_tools[0].execute(
                {"payload": json.dumps(_payload())}, object()
            )
            assert not result["details"].get("isError")
            return make_turn(assistant_text="done")

        client.turn_factory = turn
        return client

    monkeypatch.setattr(omp, "_build_client", factory)
    return client


def test_valid_production_omp_door_admits_once_and_returns_legacy_worker_result(
    production, monkeypatch: pytest.MonkeyPatch
):
    client = _rpc_factory(monkeypatch)
    wbc = _Wbc()
    root, catalog_calls = production
    plan_dir, state = _mock_state(root)
    result = omp.run_omp_step(
        "plan", state, plan_dir, root=root, model="omp:deepseek/deepseek-v4-pro",
        worker_options={"production_intent": True}, wbc_dispatch=wbc,
    )
    assert isinstance(result, WorkerResult)
    assert result.payload["plan"] == _payload()["plan"]
    assert result.payload["success_criteria"][0]["criterion"] == "c"
    assert wbc.calls == 1
    assert client.started == client.stopped == client.prompt_calls == 1
    assert catalog_calls == [( ["omp", "models", "--json"], )]
    projection = IncidentLedger(root).projection()
    assert len(projection["reservations"]) == 1
    reservation = next(iter(projection["reservations"].values()))
    assert reservation["accepted_launch"] is True
    assert reservation["closed"] is True


@pytest.mark.parametrize(
    ("model", "models", "code"),
    [
        ("omp:deepseek/deepseek-v4-pro", [], "route_liveness_missing"),
        ("omp:deepseek/deepseek-v4-pro", ["deepseek/deepseek-v4-flash"], "route_liveness_missing"),
        ("omp:openrouter/stealth/ox-alpha", ["deepseek/deepseek-v4-pro"], "route_liveness_missing"),
    ],
)
def test_invalid_or_stale_omp_membership_has_zero_reservation_wbc_or_rpc(
    production, monkeypatch: pytest.MonkeyPatch, model: str, models: list[str], code: str
):
    root, _catalog_calls = production
    client = _rpc_factory(monkeypatch)
    wbc = _Wbc()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        worker_dispatch.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps({"models": models}), stderr=""
        ),
    )
    plan_dir, state = _mock_state(root)
    with pytest.raises(CliError) as exc_info:
        omp.run_omp_step(
            "plan", state, plan_dir, root=root, model=model,
            worker_options={"production_intent": True}, wbc_dispatch=wbc,
        )
    assert exc_info.value.code == code
    assert wbc.calls == 0
    assert client.started == client.prompt_calls == 0
    assert IncidentLedger(root).projection()["reservations"] == {}


@pytest.mark.parametrize(
    "kind", ("ordinary_terminal_failure", "provider_exhausted", "worker_disposition")
)
def test_omp_door_transports_typed_terminal_and_provider_route_context(
    production, monkeypatch: pytest.MonkeyPatch, kind: str
):
    root, _catalog_calls = production
    client = _rpc_factory(monkeypatch)
    wbc = _TypedWbc(root, kind)
    plan_dir, state = _mock_state(root)
    result = omp.run_omp_step(
        "plan", state, plan_dir, root=root, model="omp:deepseek/deepseek-v4-pro",
        worker_options={"production_intent": True}, wbc_dispatch=wbc,
    )
    assert isinstance(result, DispatchOutcome)
    assert result.kind == kind
    assert result.provider == "deepseek"
    assert result.route_liveness_kind == "omp_membership"
    assert result.route_liveness_identity == "deepseek/deepseek-v4-pro"
    assert result.route_liveness_digest
    assert result.worker_identity == {"host": "omp", "pid": 42, "boot_id": "omp-boot"}
    if kind == "worker_disposition":
        assert result.disposition_id == "disposition-1"
    assert wbc.calls == client.prompt_calls == 1
    terminals = [
        item["payload"] for item in IncidentLedger(root).read_nbf_events()
        if item["payload"].get("event_type") == "worker_terminal_outcome"
    ]
    assert len(terminals) == 1
    if kind == "worker_disposition":
        assert terminals[0]["disposition_id"] == "disposition-1"
        assert terminals[0]["provider"] == result.provider == "deepseek"
        assert terminals[0]["route_liveness_kind"] == result.route_liveness_kind == "omp_membership"
        assert terminals[0]["route_liveness_identity"] == result.route_liveness_identity == "deepseek/deepseek-v4-pro"
        assert terminals[0]["route_liveness_digest"] == result.route_liveness_digest
        assert len(IncidentLedger(root).projection()["dispositions"]) == 1


@pytest.mark.parametrize(
    "dispatcher_enabled", (False, True), ids=("flag-off", "flag-on")
)
@pytest.mark.parametrize(
    "kind", ("ordinary_terminal_failure", "provider_exhausted", "worker_disposition")
)
def test_omp_typed_terminal_survives_higher_level_worker_routes(
    production,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    dispatcher_enabled: bool,
):
    """Both worker-loop routes retain the OMP door's typed terminal envelope."""
    root, _catalog_calls = production
    client = _rpc_factory(monkeypatch)
    wbc = _TypedWbc(root, kind)
    plan_dir, state = _mock_state(root)
    if dispatcher_enabled:
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
    else:
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
    # Both worker-loop modes enter the real OMP production door.  The typed
    # WBC/client fakes are beneath that door; no named production function is
    # replaced to manufacture a terminal result.
    wbc_dispatch = wbc
    worker_options = {"production_intent": True}
    args = argparse.Namespace(production_intent=False)
    result = _impl.run_step_with_worker(
        "plan",
        state,
        plan_dir,
        args,
        root=root,
        resolved=AgentMode(
            "omp", "fresh", True, "deepseek/deepseek-v4-pro", None,
            "omp:deepseek/deepseek-v4-pro",
        ),
        worker_options=worker_options,
        wbc_dispatch=wbc_dispatch,
    )
    assert isinstance(result, tuple) and len(result) == 4
    worker, _agent, _mode, _refreshed = result
    assert isinstance(worker, WorkerResult)
    outcome = worker.auth_metadata["dispatch_outcome"]
    assert outcome["kind"] == kind
    assert outcome["provider"] == "deepseek"
    assert outcome["route_liveness_kind"] == "omp_membership"
    assert outcome["route_liveness_identity"] == "deepseek/deepseek-v4-pro"
    assert outcome["worker_identity"] == {"host": "omp", "pid": 42, "boot_id": "omp-boot"}
    assert worker.worker_identity == outcome["worker_identity"]
    assert wbc.calls == client.prompt_calls == 1


def test_worker_identity_survives_agent_result_roundtrip_and_legacy_metadata_reads():
    identity = {"host": "omp", "pid": 42, "boot_id": "omp-boot"}
    outcome = {
        "kind": "provider_exhausted",
        "provider": "deepseek",
        "worker_identity": identity,
    }
    worker = WorkerResult(
        payload={"success": False},
        raw_output="",
        duration_ms=1,
        cost_usd=0.0,
        worker_identity=identity,
        auth_metadata={"dispatch_outcome": outcome},
    )
    projected = worker.to_agent_result()
    assert projected.metadata["worker_identity"] == identity
    assert projected.metadata["auth_metadata"]["worker_identity"] == identity
    restored = WorkerResult.from_agent_result(projected)
    assert restored.worker_identity == identity
    assert restored.auth_metadata["dispatch_outcome"] == outcome

    legacy = AgentResult(payload={}, raw_output="", duration_ms=0, cost_usd=0.0)
    assert WorkerResult.from_agent_result(legacy).worker_identity is None


def test_worker_identity_roundtrip_rejects_conflicting_embedded_identity():
    identity = {"host": "omp", "pid": 42, "boot_id": "omp-boot"}
    worker = WorkerResult(
        payload={}, raw_output="", duration_ms=0, cost_usd=0.0,
        worker_identity=identity,
    )
    projected = worker.to_agent_result()
    conflicting = dict(projected.metadata)
    conflicting["worker_identity"] = {"host": "forged", "pid": 99, "boot_id": "x"}
    with pytest.raises(ValueError, match="worker identity conflicts"):
        WorkerResult.from_agent_result(replace(projected, metadata=conflicting))


def test_omp_door_preserves_explicit_typed_identity_without_relaunch(
    production, monkeypatch: pytest.MonkeyPatch
):
    root, _catalog_calls = production
    client = _rpc_factory(monkeypatch)
    wbc = _TypedWbc(root, "ordinary_terminal_failure", forged_identity=True)
    plan_dir, state = _mock_state(root)
    result = omp.run_omp_step(
        "plan", state, plan_dir, root=root, model="omp:deepseek/deepseek-v4-pro",
        worker_options={"production_intent": True}, wbc_dispatch=wbc,
    )
    assert isinstance(result, DispatchOutcome)
    assert result.worker_identity == {"host": "forged", "pid": 99, "boot_id": "forged-boot"}
    assert wbc.calls == client.prompt_calls == 1


def test_omp_missing_worker_identity_fails_closed_without_supervisor_fallback(
    production, monkeypatch: pytest.MonkeyPatch
):
    root, _catalog_calls = production
    plan_dir, state = _mock_state(root)

    class _MissingIdentityWbc:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, _dispatch):
            self.calls += 1
            return SimpleNamespace(
                worker_result=WorkerResult(
                    payload={}, raw_output="", duration_ms=1, cost_usd=0.0,
                    worker_identity=None,
                )
            )

    wbc = _MissingIdentityWbc()
    with pytest.raises(CliError) as exc_info:
        omp.run_omp_step(
            "plan", state, plan_dir, root=root,
            model="omp:deepseek/deepseek-v4-pro",
            worker_options={"production_intent": True}, wbc_dispatch=wbc,
        )
    assert exc_info.value.code == "scheduling_condition"
    assert exc_info.value.extra["dispatch_outcome"]["kind"] == "unresolved_launch"
    assert "omp-worker" not in str(exc_info.value.extra)
    assert wbc.calls == 1


def test_omp_door_append_failure_returns_unresolved_and_never_relaunches(
    production, monkeypatch: pytest.MonkeyPatch
):
    root, _catalog_calls = production
    client = _rpc_factory(monkeypatch)
    wbc = _Wbc()
    ledger = IncidentLedger(root)
    original = ledger.append_terminal_outcome
    ledger.append_terminal_outcome = lambda **_kwargs: (_ for _ in ()).throw(OSError("append unavailable"))  # type: ignore[method-assign]
    # The physical door creates its own ledger; patch the constructor's method
    # on the instance only after admission is created via the public seam.
    monkeypatch.setattr(worker_dispatch, "IncidentLedger", lambda _root: ledger)
    plan_dir, state = _mock_state(root)
    with pytest.raises(CliError) as exc_info:
        omp.run_omp_step(
            "plan", state, plan_dir, root=root, model="omp:deepseek/deepseek-v4-pro",
            worker_options={"production_intent": True}, wbc_dispatch=wbc,
        )
    assert exc_info.value.code == "scheduling_condition"
    assert wbc.calls == client.prompt_calls == 1
    assert IncidentLedger(root).projection()["reservations"]
    assert next(iter(IncidentLedger(root).projection()["reservations"].values()))["closed"] is False

    # An unresolved accepted launch is a reconciliation hold, not permission
    # for a second admission.  The next public-door call is refused while the
    # original reservation remains open, and neither WBC nor RPC is relaunched.
    with pytest.raises(CliError) as second_exc_info:
        omp.run_omp_step(
            "plan", state, plan_dir, root=root, model="omp:deepseek/deepseek-v4-pro",
            worker_options={"production_intent": True}, wbc_dispatch=wbc,
        )
    assert second_exc_info.value.code == "admission_rejected"
    assert wbc.calls == client.prompt_calls == 1
    assert [
        item["payload"] for item in ledger.read_nbf_events()
        if item["payload"].get("event_type") == "worker_terminal_outcome"
    ] == []
    ledger.append_terminal_outcome = original  # type: ignore[method-assign]
