"""Direct physical-door checks (the named doors are never replaced)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold.agent.contracts import AgentMode
from arnold_pipelines.megaplan.cloud import runtime_attestation, worker_dispatch
from arnold_pipelines.megaplan.managed_agent import ManagedCommandSpec
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.orchestration.phase_result import (
    DispatchOutcome,
    ExitKind,
    PhaseResult,
    SchedulingCondition,
    phase_result_guard,
)
from arnold_pipelines.megaplan.workers import _impl, omp
from arnold_pipelines.megaplan.runtime import memory_headroom
from tests.cloud.dispatch_test_helpers import native_proof


class _NoWbc:
    def run(self, _dispatch):
        raise AssertionError("WBC must not run after invalid authority")


class _Wbc:
    def __init__(self):
        self.calls = 0

    def run(self, dispatch):
        self.calls += 1
        return SimpleNamespace(worker_result=dispatch(None))


class _SeedPath:
    """Small read-only seed seam; admission still runs its real gate."""

    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def is_file(self):
        return True

    def read_bytes(self):
        return b"physical-door-seed"

    def read_text(self, encoding="utf-8"):
        return json.dumps(self.payload)


@pytest.fixture
def admitted_runtime(monkeypatch, tmp_path):
    provenance = runtime_attestation.runtime_provenance()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("physical-door-manifest", encoding="utf-8")
    seed = _SeedPath(
        {
            "expected_revision": provenance["source_revision"],
            "runtime_provenance": provenance,
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "content_sha256": hashlib.sha256(b"physical-door-seed").hexdigest(),
            "dependency_generation": {"interpreter_path": str(Path(sys.executable).resolve())},
        }
    )
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    monkeypatch.setattr(runtime_attestation, "configured_seed_path", lambda: seed)
    monkeypatch.setattr(
        runtime_attestation,
        "validate_runtime_launch_seed",
        lambda *_args, **_kwargs: {"status": "ready", "runtime_vector_sha256": "test"},
    )
    monkeypatch.setattr(
        memory_headroom,
        "classify_memory_headroom",
        lambda *_args, **_kwargs: {"ok": True, "available_bytes": 10**9},
    )
    monkeypatch.setattr(memory_headroom, "read_cgroup_memory_snapshot", lambda: {})
    return tmp_path


def _native_admission_proof(agent: str, model: str):
    return native_proof(
        backend=agent,
        provider=agent,
        model=model,
        route=f"{agent}:{model}",
        observed_at=datetime.now(timezone.utc).isoformat(),
    )


def _worker(payload=None):
    from arnold_pipelines.megaplan.workers._impl import WorkerResult

    return WorkerResult(
        payload or {}, "", 1, 0.0,
        worker_identity={"host": "physical-door", "pid": 1, "boot_id": "test"},
    )


def managed_spec(root: Path) -> ManagedCommandSpec:
    return ManagedCommandSpec(
        run_kind="automatic_repair",
        identity_key="physical-door-test",
        project_dir=root,
        argv=("codex", "exec", "--help"),
        task_kind="repair",
        difficulty=1,
        model="codex:gpt-5.6-luna",
        reasoning_effort="high",
        route_class="test",
        backend="codex",
        command_display="physical-door-test",
        launch_provenance={},
        links={},
        run_root=root,
    )


def test_native_physical_door_valid_admission_once_and_legacy_tuple(
    monkeypatch, admitted_runtime, tmp_path
):
    proof = _native_admission_proof("codex", "gpt-5.6")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)
    worker = _worker()
    calls = []

    def final(*_args, **_kwargs):
        calls.append(True)
        return worker, "codex", "fresh", False

    monkeypatch.setattr(_impl, "_run_step_with_worker_legacy", final)
    wbc = _Wbc()
    result = _impl._production_worker_dispatch(
        "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
        tmp_path, argparse.Namespace(), root=tmp_path,
        resolved=AgentMode("codex", "fresh", True, "gpt-5.6", None, "gpt-5.6"),
        prompt_override=None, prompt_kwargs=None, read_only=False, output_path=None,
        worker_options={"physical_door_id": "forged", "authorized_route_identity": "forged"},
        wbc_dispatch=wbc,
    )
    assert isinstance(result, tuple) and len(result) == 4
    assert calls == [True]
    assert wbc.calls == 1
    outcome = result[0].auth_metadata["dispatch_outcome"]
    assert outcome["provider"] == "codex"
    assert outcome["route_liveness_kind"] == "native_backend"
    assert outcome["route_liveness_identity"] == proof["identity"]
    assert outcome["route_liveness_digest"] == proof["digest"]


def test_native_effort_is_receipt_context_and_mismatch_is_prelaunch(
    monkeypatch, admitted_runtime, tmp_path
):
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    proof = _native_admission_proof("codex", "gpt-5.6")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)
    worker = _worker()
    calls = []

    def final(*_args, **_kwargs):
        calls.append(True)
        return worker, "codex", "fresh", False

    monkeypatch.setattr(_impl, "_run_step_with_worker_legacy", final)
    result = _impl._production_worker_dispatch(
        "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
        tmp_path, argparse.Namespace(), root=tmp_path,
        resolved=AgentMode("codex", "fresh", True, "gpt-5.6", "high", "gpt-5.6"),
        prompt_override=None, prompt_kwargs=None, read_only=False, output_path=None,
        worker_options={}, wbc_dispatch=_Wbc(),
    )
    assert result[0].auth_metadata["dispatch_outcome"]["selected_spec"] == "codex:gpt-5.6:high"
    assert result[0].auth_metadata["dispatch_outcome"]["route_liveness_identity"] == proof["identity"]
    assert calls == [True]

    for index, (bad_resolved, bad_proof) in enumerate(
        (
        (AgentMode("codex", "fresh", True, "gpt-5.6", "not-an-effort", "gpt-5.6"), proof),
        (AgentMode("codex", "fresh", True, "gpt-5.6", "high", "gpt-5.6"),
         {**proof, "route": "codex:gpt-5.7"}),
        )
    ):
        isolated = tmp_path / ("bad-" + str(index))
        isolated.mkdir()
        monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: bad_proof)
        with pytest.raises(CliError):
            _impl._production_worker_dispatch(
                "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
                isolated, argparse.Namespace(), root=isolated,
                resolved=bad_resolved, prompt_override=None, prompt_kwargs=None,
                read_only=False, output_path=None, worker_options={}, wbc_dispatch=_NoWbc(),
            )
        assert not any(isolated.iterdir()) or not IncidentLedger(isolated).projection()["reservations"]


def test_native_missing_worker_identity_is_unresolved_without_supervisor_fallback(
    monkeypatch, admitted_runtime, tmp_path
):
    proof = _native_admission_proof("codex", "gpt-5.6")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)
    missing = _worker()
    missing.worker_identity = None
    monkeypatch.setattr(
        _impl, "_run_step_with_worker_legacy",
        lambda *_args, **_kwargs: (missing, "codex", "fresh", False),
    )
    with pytest.raises(CliError) as raised:
        _impl._production_worker_dispatch(
            "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
            tmp_path, argparse.Namespace(), root=tmp_path,
            resolved=AgentMode("codex", "fresh", True, "gpt-5.6", None, "gpt-5.6"),
            prompt_override=None, prompt_kwargs=None, read_only=False, output_path=None,
            worker_options={}, wbc_dispatch=_Wbc(),
        )
    assert raised.value.code == "scheduling_condition"
    assert raised.value.extra["dispatch_outcome"]["kind"] == "unresolved_launch"
    assert "native-worker" not in str(raised.value.extra)


@pytest.mark.parametrize(
    ("code", "extra", "expected_kind"),
    [
        (
            "ordinary_terminal_failure",
            {
                "worker_identity": {"host": "native-terminal", "pid": 7, "boot_id": "b"},
                "terminal_failure": {"error": "ordinary"},
            },
            "ordinary_terminal_failure",
        ),
        (
            "provider_exhausted",
            {
                "worker_identity": {"host": "native-provider", "pid": 8, "boot_id": "b"},
                "provider_failure_key": "a" * 64,
                "provider_evidence": {
                    "observation_id": "observation",
                    "retryability_class": "availability",
                    "exhausted_attempt_count": 1,
                    "terminal_provider_evidence_id": "evidence",
                    "precondition_identity": "precondition",
                    "provider_epoch_identity": "epoch",
                    "provider_failure_key": "a" * 64,
                    "observed_at": "2026-08-31T00:00:00Z",
                },
            },
            "provider_exhausted",
        ),
    ],
)
def test_native_physical_door_terminal_outcomes_keep_legacy_tuple_and_context(
    monkeypatch, admitted_runtime, tmp_path, code, extra, expected_kind
):
    proof = _native_admission_proof("codex", "gpt-5.6")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)

    def terminal(*_args, **_kwargs):
        raise CliError(code, "typed terminal", extra=extra)

    monkeypatch.setattr(_impl, "_run_step_with_worker_legacy", terminal)
    result = _impl._production_worker_dispatch(
        "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
        tmp_path, argparse.Namespace(), root=tmp_path,
        resolved=AgentMode("codex", "fresh", True, "gpt-5.6", None, "gpt-5.6"),
        prompt_override=None, prompt_kwargs=None, read_only=False, output_path=None,
        worker_options={}, wbc_dispatch=_Wbc(),
    )

    assert isinstance(result, tuple) and len(result) == 4
    worker, agent, mode, refreshed = result
    assert agent == "codex"
    assert mode == "fresh"
    assert refreshed is True
    outcome = worker.auth_metadata["dispatch_outcome"]
    assert outcome["kind"] == expected_kind
    assert outcome["provider"] == "codex"
    assert outcome["route_liveness_identity"] == proof["identity"]
    assert outcome["route_liveness_digest"] == proof["digest"]
    assert worker.worker_identity == extra["worker_identity"]
    assert outcome["worker_identity"] == extra["worker_identity"]


def test_native_physical_door_forged_identity_is_unresolved_without_terminal(
    monkeypatch, admitted_runtime, tmp_path
):
    proof = _native_admission_proof("codex", "gpt-5.6")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)
    forged = {"host": "forged", "pid": 99, "boot_id": "forged-boot"}
    worker = _worker(
        {
            "dispatch_outcome": {
                "kind": "success",
                "launch_state": "accepted",
                "worker_identity": forged,
                "started_at": "2026-08-31T00:00:00Z",
                "finished_at": "2026-08-31T00:00:01Z",
                "success_payload": {"ok": True},
            }
        }
    )
    monkeypatch.setattr(
        _impl,
        "_run_step_with_worker_legacy",
        lambda *_args, **_kwargs: (worker, "codex", "fresh", False),
    )
    with pytest.raises(CliError) as raised:
        _impl._production_worker_dispatch(
            "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
            tmp_path, argparse.Namespace(), root=tmp_path,
            resolved=AgentMode("codex", "fresh", True, "gpt-5.6", None, "gpt-5.6"),
            prompt_override=None, prompt_kwargs=None, read_only=False, output_path=None,
            worker_options={}, wbc_dispatch=_Wbc(),
        )
    assert raised.value.code == "scheduling_condition"
    assert raised.value.extra["dispatch_outcome"]["kind"] == "unresolved_launch"


def test_native_physical_door_missing_terminal_identity_is_unresolved(
    monkeypatch, admitted_runtime, tmp_path
):
    proof = _native_admission_proof("codex", "gpt-5.6")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)
    monkeypatch.setattr(
        _impl,
        "_run_step_with_worker_legacy",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            CliError("ordinary_terminal_failure", "missing identity")
        ),
    )
    with pytest.raises(CliError) as raised:
        _impl._production_worker_dispatch(
            "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
            tmp_path, argparse.Namespace(), root=tmp_path,
            resolved=AgentMode("codex", "fresh", True, "gpt-5.6", None, "gpt-5.6"),
            prompt_override=None, prompt_kwargs=None, read_only=False, output_path=None,
            worker_options={}, wbc_dispatch=_Wbc(),
        )
    assert raised.value.code == "scheduling_condition"
    assert raised.value.extra["dispatch_outcome"]["kind"] == "unresolved_launch"


def test_native_physical_door_terminal_append_failure_holds_unresolved_without_relaunch(
    monkeypatch, admitted_runtime, tmp_path
):
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger

    proof = _native_admission_proof("codex", "gpt-5.6")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)
    launches = []

    def terminal(*_args, **_kwargs):
        launches.append(1)
        raise CliError(
            "ordinary_terminal_failure",
            "typed terminal",
            extra={
                "worker_identity": {"host": "native-terminal", "pid": 7, "boot_id": "b"},
                "terminal_failure": {"error": "ordinary"},
            },
        )

    monkeypatch.setattr(_impl, "_run_step_with_worker_legacy", terminal)
    append_calls = []

    def fail_append(self, **_kwargs):
        append_calls.append(1)
        raise OSError("terminal append unavailable")

    monkeypatch.setattr(IncidentLedger, "append_terminal_outcome", fail_append)
    with pytest.raises(CliError) as raised:
        _impl._production_worker_dispatch(
            "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
            tmp_path, argparse.Namespace(), root=tmp_path,
            resolved=AgentMode("codex", "fresh", True, "gpt-5.6", None, "gpt-5.6"),
            prompt_override=None, prompt_kwargs=None, read_only=False, output_path=None,
            worker_options={}, wbc_dispatch=_Wbc(),
        )
    assert raised.value.code == "scheduling_condition"
    assert raised.value.extra["dispatch_outcome"]["kind"] == "unresolved_launch"
    assert launches == [1]
    assert append_calls == [1]


def test_real_handler_worker_traversal_emits_condition_and_outcome_without_failure_accounting(
    monkeypatch, tmp_path
):
    from arnold_pipelines.megaplan.handlers import shared

    state = {
        "config": {"project_dir": str(tmp_path)},
        "meta": {"current_invocation_id": "invocation"},
        "iteration": 1,
        "current_state": "initialized",
    }
    (tmp_path / "state.json").write_text(
        json.dumps({"meta": state["meta"], "active_step": {"phase": "plan"}}),
        encoding="utf-8",
    )
    identity = {"host": "native", "pid": 11, "boot_id": "boot"}
    outcome = DispatchOutcome(
        kind="unresolved_launch",
        launch_state="ambiguous",
        plan_id="plan",
        phase="plan",
        dispatch_family_id="family",
        logical_dispatch_id="logical",
        admission_receipt_id="receipt",
        semantic_dispatch_fingerprint="a" * 64,
        selected_spec="codex:gpt-5.6",
        worker_identity=identity,
        started_at="2026-08-31T00:00:00Z",
        finished_at="2026-08-31T00:00:01Z",
    )
    condition = SchedulingCondition(
        condition_id="unresolved:logical",
        reason="unresolved_launch",
        plan_id="plan",
        phase="plan",
        spec="codex:gpt-5.6",
        dispatch_family_id="family",
        logical_dispatch_id="logical",
        admission_attempt=1,
        retry_after_s=0.0,
        observed_at=outcome.finished_at,
        evidence={"dispatch_outcome": outcome.to_dict()},
    )
    monkeypatch.setattr(shared, "apply_profile_expansion", lambda *a, **k: None)
    monkeypatch.setattr(shared, "save_state_merge_meta", lambda *a, **k: None)
    monkeypatch.setattr(shared, "set_active_step", lambda current, **kwargs: "run-id")
    monkeypatch.setattr(shared, "clear_active_step", lambda *a, **k: None)
    failures = []
    monkeypatch.setattr(shared, "record_step_failure", lambda *a, **k: failures.append(1))
    monkeypatch.setattr(
        shared.worker_module,
        "run_step_with_worker",
        lambda *a, **k: (_ for _ in ()).throw(
            CliError(
                "scheduling_condition",
                "unresolved",
                extra={
                    "condition": condition.to_dict(),
                    "dispatch_outcome": outcome.to_dict(),
                },
            )
        ),
    )
    args = argparse.Namespace(production_intent=True)
    with pytest.raises(CliError):
        shared._run_worker(
            "plan",
            state,
            tmp_path,
            args,
                root=tmp_path,
                resolved=AgentMode("codex", "fresh", True, "gpt-5.6", None, "gpt-5.6"),
                wbc_dispatch=SimpleNamespace(),
            )

    result = PhaseResult.from_dict(json.loads((tmp_path / "phase_result.json").read_text()))
    assert result.scheduling_condition == condition
    assert result.dispatch_outcome == outcome
    assert failures == []


@pytest.mark.parametrize(
    "dispatcher_enabled", (False, True), ids=("flag-off", "flag-on")
)
def test_real_handler_constructs_one_wbc_and_reaches_native_door_without_injection(
    monkeypatch, admitted_runtime, tmp_path, dispatcher_enabled
):
    from arnold_pipelines.megaplan.handlers import shared
    from arnold_pipelines.megaplan.custody.phase_wbc import activate_phase_wbc
    from arnold_pipelines.megaplan._core.state import set_active_step
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    from tests._workers_helpers import _mock_state

    plan_dir, state = _mock_state(tmp_path)
    state["meta"]["plan_id"] = "plan"
    state["meta"]["current_invocation_id"] = "invocation"
    proof = _native_admission_proof("codex", "gpt-5.6")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)
    if dispatcher_enabled:
        monkeypatch.setenv("MEGAPLAN_USE_AGENT_DISPATCHER", "1")
    else:
        monkeypatch.delenv("MEGAPLAN_USE_AGENT_DISPATCHER", raising=False)
    set_active_step(state, step="plan", agent="codex", mode="fresh", model="gpt-5.6")
    activate_phase_wbc(state=state, plan_dir=plan_dir, step="plan", agent="codex")
    monkeypatch.setenv("MEGAPLAN_MOCK_WORKERS", "1")
    provider_calls = []
    original_mock = _impl.mock_worker_output

    def fake_final_provider(*args, **kwargs):
        provider_calls.append(1)
        result = original_mock(*args, **kwargs)
        result.worker_identity = {"host": "native-test-worker", "pid": 17, "boot_id": "native-test-boot"}
        return result

    monkeypatch.setattr(_impl, "mock_worker_output", fake_final_provider)
    result = shared._run_worker(
        "plan", state, plan_dir,
        argparse.Namespace(production_intent=True), root=tmp_path,
        resolved=AgentMode("codex", "fresh", True, "gpt-5.6", "high", "gpt-5.6"),
        reuse_active_phase=True,
    )
    assert isinstance(result, tuple) and len(result) == 4
    worker, _agent, _mode, _refreshed = result
    assert worker.worker_identity == {"host": "native-test-worker", "pid": 17, "boot_id": "native-test-boot"}
    assert provider_calls == [1]
    reservations = IncidentLedger(tmp_path).projection()["reservations"]
    assert len(reservations) == 1
    assert next(iter(reservations.values()))["closed"] is True


def test_native_physical_door_constructor_failure_has_zero_reservation_and_wbc(
    monkeypatch, admitted_runtime, tmp_path
):
    def missing(*_args):
        raise CliError("native_constructor_unavailable", "constructor unavailable")

    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", missing)
    wbc = _NoWbc()
    with pytest.raises(CliError, match="constructor unavailable"):
        _impl._production_worker_dispatch(
            "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
            tmp_path, argparse.Namespace(), root=tmp_path,
            resolved=AgentMode("codex", "fresh", True, "gpt-5.6", None, "gpt-5.6"),
            prompt_override=None, prompt_kwargs=None, read_only=False, output_path=None,
            worker_options={}, wbc_dispatch=wbc,
        )
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    assert IncidentLedger(tmp_path).projection()["reservations"] == {}


@pytest.mark.parametrize("failure", ["stale", "mismatch"])
def test_native_physical_door_invalid_backend_proof_has_zero_effects(
    monkeypatch, admitted_runtime, tmp_path, failure
):
    proof = _native_admission_proof("codex", "gpt-5.6")
    if failure == "stale":
        proof = _native_admission_proof("codex", "gpt-5.6").copy()
        proof["observed_at"] = "1900-01-01T00:00:00+00:00"
        # The digest is deliberately not repaired: the real gate must reject
        # this stale backend observation before it can reserve anything.
    else:
        proof = _native_admission_proof("claude", "gpt-5.6")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)
    wbc = _NoWbc()
    with pytest.raises(CliError):
        _impl._production_worker_dispatch(
            "plan", {"meta": {"plan_id": "plan", "current_invocation_id": "invocation"}},
            tmp_path, argparse.Namespace(), root=tmp_path,
            resolved=AgentMode("codex", "fresh", True, "gpt-5.6", None, "gpt-5.6"),
            prompt_override=None, prompt_kwargs=None, read_only=False, output_path=None,
            worker_options={}, wbc_dispatch=wbc,
        )
    from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
    assert IncidentLedger(tmp_path).projection()["reservations"] == {}


def test_omp_physical_door_valid_admission_once_and_context(
    monkeypatch, admitted_runtime, tmp_path
):
    route = "openrouter/stealth/ox-alpha"
    monkeypatch.setattr(
        worker_dispatch, "resolve_omp_live_membership",
        lambda *_args, **_kwargs: {
            "kind": "omp_membership", "identity": route, "digest": "d" * 64,
            "provider": "openrouter", "model": "stealth/ox-alpha",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    worker = _worker()
    class _AdmissionOnlyWbc:
        def __init__(self):
            self.calls = 0

        def run(self, _dispatch):
            self.calls += 1
            # The actual run_omp_step production route is exercised in
            # tests/workers/test_omp_physical_door.py.  This direct adapter
            # test isolates the admission door and fakes only its final
            # provider result; it never replaces a named production door.
            return SimpleNamespace(worker_result=worker)

    wbc = _AdmissionOnlyWbc()
    result = omp._run_omp_with_admission(
        "plan", {"meta": {"current_invocation_id": "invocation"}}, tmp_path,
        root=tmp_path, fresh=True, model=f"omp:{route}", effort=None,
        prompt_override=None, output_path=None, worker_options={}, read_only=False,
        prompt_kwargs=None, wbc_dispatch=wbc,
    )
    assert result is worker
    assert wbc.calls == 1
    outcome = result.auth_metadata["dispatch_outcome"]
    assert outcome["provider"] == "openrouter"
    assert outcome["route_liveness_identity"] == route


def test_managed_physical_door_valid_admission_once_and_command(monkeypatch, admitted_runtime, tmp_path):
    from arnold_pipelines.megaplan.cloud.babysitter import launch

    proof = _native_admission_proof("codex", "gpt-5.6-luna")
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_: proof)
    calls = []
    monkeypatch.setattr(launch, "run_managed_command", lambda spec: calls.append(spec) or 0)
    ctx = {
        "session": "physical-door",
        "run_id": "run",
        "plan": "plan",
        "run_root": tmp_path,
        "goal_path": str(tmp_path / "goal.md"),
    }
    assert launch._admit_managed_launch(ctx, managed_spec(tmp_path)) == 0
    assert len(calls) == 1


def test_native_handler_unresolved_emits_condition_and_outcome_through_guard(tmp_path):
    outcome = DispatchOutcome(
        kind="unresolved_launch",
        launch_state="ambiguous",
        plan_id="plan",
        phase="plan",
        dispatch_family_id="family",
        logical_dispatch_id="logical",
        admission_receipt_id="receipt",
        semantic_dispatch_fingerprint="a" * 64,
        selected_spec="codex:gpt-5.6",
        worker_identity={"host": "host", "pid": 1, "boot_id": "boot"},
        started_at="2026-08-31T00:00:00Z",
        finished_at="2026-08-31T00:00:01Z",
        provider="codex",
        route_liveness_kind="native_backend",
        route_liveness_identity="route",
        route_liveness_digest="b" * 64,
    )
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "meta": {"current_invocation_id": "invocation"},
                "active_step": {"phase": "plan"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CliError):
        with phase_result_guard(tmp_path):
            raise CliError(
                "scheduling_condition",
                "canonical native launch remains unresolved",
                extra={"reason": "unresolved_launch", "dispatch_outcome": outcome.to_dict()},
            )

    result = PhaseResult.from_dict(json.loads((tmp_path / "phase_result.json").read_text()))
    assert result.exit_kind == ExitKind.scheduling_condition.value
    assert result.scheduling_condition is not None
    assert result.scheduling_condition.reason == "unresolved_launch"
    assert result.scheduling_condition.evidence["dispatch_outcome"] == outcome.to_dict()
    assert result.dispatch_outcome == outcome
