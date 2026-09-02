"""Focused real-door checks for the managed babysitter admission boundary.

Only backend/system observations and the final managed command are replaced;
the named managed door and canonical admission/ledger path remain real.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

import pytest

from arnold_pipelines.megaplan.cloud import operator_control, worker_dispatch
from arnold_pipelines.megaplan.fallback_chains import provider_family
from arnold_pipelines.megaplan.incident.schema import ProviderFailureKey
from arnold_pipelines.megaplan.cloud.babysitter.launch import (
    ManagedLaunchUnresolved,
    _validate_automatic_launch_reservation,
    _admit_managed_launch,
)
from arnold_pipelines.megaplan.chain.spec import _state_path_for
from arnold_pipelines.megaplan.incident.ledger import IncidentLedger
from arnold_pipelines.megaplan.incident.chain_control import state_digest_for
from arnold_pipelines.megaplan.incident.schema import (
    CauseKind,
    DispositionMode,
    KillerKind,
    Signal,
    WorkerDisposition,
)
from arnold_pipelines.megaplan.managed_agent import (
    ManagedCommandSpec,
    machine_origin_provenance,
)
from arnold_pipelines.megaplan.orchestration.phase_result import DispatchOutcome


MODEL = "gpt-5.6-luna"
ROUTE = f"codex:{MODEL}"
IDENTITY = {"host": "managed-host", "pid": 321, "boot_id": "managed-boot", "process_start_identity": "managed-start"}


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _native_observation(*, observed_at: str | None = None, model: str = MODEL) -> dict[str, object]:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    registry = {"backend": "codex", "executable": {"path": "/usr/bin/codex"}, "models": [model]}
    proof = {
        "constructable": True,
        "catalog": [model],
        "registry": registry,
        "preparation": {
            "ok": True,
            "backend": "codex",
            "provider": "codex",
            "model": model,
            "route": f"codex:{model}",
        },
        "seam": "test backend preparation",
    }
    content = {
        "backend": "codex",
        "provider": "codex",
        "normalized_model": model,
        "route": f"codex:{model}",
        "capability_registry": registry,
        "registry_generation": "test-generation",
        "proof": proof,
        "proof_generation": "test-proof-generation",
        # The mismatch fixture intentionally uses a non-catalog model; its
        # upstream family remains the canonical codex family even though the
        # full spec is not parseable by the live model grammar.
        "family": provider_family("codex:gpt-5.6"),
    }
    identity = _digest(content)
    return {
        "kind": "native_backend",
        **content,
        "identity": identity,
        "observed_at": observed_at,
        "digest": _digest({**content, "identity": identity, "observed_at": observed_at}),
    }


def _spec(root: Path, *, identity: str = "managed-door") -> ManagedCommandSpec:
    return ManagedCommandSpec(
        run_kind="automatic_watchdog_source_repair",
        identity_key=identity,
        project_dir=root,
        argv=("codex", "exec", "--help"),
        task_kind="autonomous",
        difficulty=8,
        model=ROUTE,
        reasoning_effort="bounded",
        route_class="watchdog_babysitter_codex_override",
        backend="codex",
        command_display="managed physical-door test",
        launch_provenance=machine_origin_provenance(
            origin_kind="watchdog_source_repair",
            origin_id=identity,
            component="tests.cloud.test_managed_physical_door",
            trigger_id=identity,
        ),
        links={"cloud_session": "session"},
        run_root=root,
    )


def _context(root: Path, *, run_id: str = "occurrence") -> dict[str, object]:
    return {
        "session": "session",
        "run_id": run_id,
        "managed_run_id": "managed-run",
        "plan": "plan",
        "run_root": root,
        "goal_path": str(root / "goal.md"),
        "model": ROUTE,
    }


@pytest.fixture
def managed_observations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Replace only backend/system observations beneath the real gate."""
    monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda _agent, model: _native_observation(model=model))
    monkeypatch.setattr(worker_dispatch, "_validate_runtime_binding", lambda _request: None)
    seed = tmp_path / "runtime-seed.json"
    manifest = tmp_path / "runtime-manifest.json"
    seed.write_text("seed", encoding="utf-8")
    manifest.write_text("manifest", encoding="utf-8")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.runtime_attestation.configured_seed_path",
        lambda: seed,
    )
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST", str(manifest))
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.runtime_provenance.runtime_provenance",
        lambda: {"source_revision": "a" * 40, "runtime": "test"},
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.memory_headroom.memory_cooldown_wait_secs",
        lambda *_args, **_kwargs: 0.0,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.memory_headroom.classify_memory_headroom",
        lambda *_args, **_kwargs: {"ok": True, "available_bytes": 1},
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.memory_headroom.read_cgroup_memory_snapshot",
        lambda: {},
    )


def _events(root: Path) -> list[dict[str, object]]:
    return [record["payload"] for record in IncidentLedger(root).read_nbf_events()]


def test_valid_admission_and_integer_command_are_each_once_without_running_receipt(
    managed_observations, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[ManagedCommandSpec] = []

    def run(spec: ManagedCommandSpec) -> int:
        calls.append(spec)
        return 0

    monkeypatch.setattr("arnold_pipelines.megaplan.cloud.babysitter.launch.run_managed_command", run)
    ctx = _context(tmp_path)
    result = _admit_managed_launch(ctx, _spec(tmp_path))

    assert result == 0
    assert calls == [_spec(tmp_path)]
    events = _events(tmp_path)
    assert [item["event_type"] for item in events].count("admission_reserved") == 1
    assert [item["event_type"] for item in events].count("worker_terminal_outcome") == 1
    assert not any(item.get("event_type") == "babysitter_running_receipt" for item in events)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("schema", None),
        lambda value: value.update(workspace="/foreign/workspace"),
        lambda value: value.update(managed_run_id="foreign-run"),
    ],
)
def test_automatic_reservation_validator_rejects_forged_identity(
    tmp_path: Path, mutation
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    ctx = {
        "session": "session",
        "workspace": str(tmp_path),
        "remote_spec": str(spec_path),
        "plan": "plan",
        "occurrence": "occurrence",
        "run_id": "run",
        "managed_run_id": "managed",
        "marker_dir": marker_dir,
    }
    reservation = {
        "schema": "arnold.babysitter.launch-reservation.v1",
        "schema_version": 1,
        "reservation_id": "reservation",
        "session": "session",
        "workspace": str(tmp_path),
        "spec": str(spec_path),
        "plan": "plan",
        "occurrence_digest": "occurrence",
        "run_id": "run",
        "managed_run_id": "managed",
        "logical_dispatch_id": "logical",
        "status": "claimed",
    }
    forged = dict(reservation)
    mutation(forged)
    (marker_dir / "session.json").write_text(
        json.dumps(
            {
                "session": "session",
                "workspace": str(tmp_path),
                "remote_spec": str(spec_path),
                "plan": "plan",
                "should_run": True,
                "babysitter_launch_reservation": forged,
            }
        ),
        encoding="utf-8",
    )
    ctx["babysitter_launch_reservation"] = reservation
    with pytest.raises(RuntimeError, match="reservation"):
        _validate_automatic_launch_reservation(ctx)


def test_automatic_reservation_validator_allows_exact_pause_after_claim(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    reservation = {
        "schema": "arnold.babysitter.launch-reservation.v1",
        "schema_version": 1,
        "reservation_id": "reservation",
        "session": "session",
        "workspace": str(tmp_path),
        "spec": str(spec_path),
        "plan": "plan",
        "occurrence_digest": "occurrence",
        "run_id": "run",
        "managed_run_id": "managed",
        "logical_dispatch_id": "logical",
        "status": "claimed",
    }
    (marker_dir / "session.json").write_text(
        json.dumps(
            {
                "session": "session",
                "workspace": str(tmp_path),
                "remote_spec": str(spec_path),
                "plan": "plan",
                "should_run": False,
                "operator_pause": {
                    "schema_version": "arnold.megaplan.operator-pause.v1",
                    "active": True,
                },
                "babysitter_launch_reservation": reservation,
            }
        ),
        encoding="utf-8",
    )
    # The context predates the canonical chain-state read.  It must not veto
    # the exact claimed reservation whose plan was captured under lock.
    _validate_automatic_launch_reservation(
        {
            "session": "session",
            "workspace": str(tmp_path),
            "remote_spec": str(spec_path),
            "plan": "stale-plan",
            "occurrence": "occurrence",
            "run_id": "run",
            "managed_run_id": "managed",
            "marker_dir": marker_dir,
            "babysitter_launch_reservation": reservation,
        }
    )


def test_automatic_reservation_validator_uses_fresh_chain_plan_not_stale_context(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    state_path = _state_path_for(spec_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    raw_state = {
        "schema_version": 1,
        "current_milestone_index": 0,
        "current_plan_name": "canonical-plan",
        "last_state": "running",
        "completed": [],
        "metadata": {"_nbf08_revision": 3},
    }
    state_path.write_text(json.dumps(raw_state), encoding="utf-8")
    reservation = {
        "schema": "arnold.babysitter.launch-reservation.v1",
        "schema_version": 1,
        "reservation_id": "reservation",
        "session": "session",
        "workspace": str(tmp_path),
        "spec": str(spec_path),
        "plan": "canonical-plan",
        "occurrence_digest": "occurrence",
        "run_id": "run",
        "managed_run_id": "managed",
        "logical_dispatch_id": "logical",
        "status": "claimed",
        "chain_state_revision": 3,
        "chain_state_digest": state_digest_for(raw_state),
    }
    (marker_dir / "session.json").write_text(
        json.dumps(
            {
                "session": "session",
                "workspace": str(tmp_path),
                "remote_spec": str(spec_path),
                "plan": "canonical-plan",
                "should_run": True,
                "babysitter_launch_reservation": reservation,
            }
        ),
        encoding="utf-8",
    )
    # The context predates the canonical chain-state read.  It must not veto
    # the exact claimed reservation whose plan was captured under lock.
    _validate_automatic_launch_reservation(
        {
            "session": "session",
            "workspace": str(tmp_path),
            "remote_spec": str(spec_path),
            "plan": "stale-plan",
            "occurrence": "occurrence",
            "run_id": "run",
            "managed_run_id": "managed",
            "marker_dir": marker_dir,
            "babysitter_launch_reservation": reservation,
        }
    )


def test_automatic_reservation_validator_waits_for_pause_after_claim(
    tmp_path: Path,
) -> None:
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    marker_path = marker_dir / "session.json"
    reservation = {
        "schema": "arnold.babysitter.launch-reservation.v1",
        "schema_version": 1,
        "reservation_id": "reservation",
        "session": "session",
        "workspace": str(tmp_path),
        "spec": str(spec_path),
        "plan": "plan",
        "occurrence_digest": "occurrence",
        "run_id": "run",
        "managed_run_id": "managed",
        "logical_dispatch_id": "logical",
        "status": "claimed",
    }
    marker_path.write_text(
        json.dumps(
            {
                "session": "session",
                "workspace": str(tmp_path),
                "remote_spec": str(spec_path),
                "plan": "plan",
                "should_run": True,
                "babysitter_launch_reservation": reservation,
            }
        ),
        encoding="utf-8",
    )
    ctx = {
        "session": "session",
        "workspace": str(tmp_path),
        "remote_spec": str(spec_path),
        "plan": "stale-plan",
        "occurrence": "occurrence",
        "run_id": "run",
        "managed_run_id": "managed",
        "marker_dir": marker_dir,
        "babysitter_launch_reservation": reservation,
    }
    done = threading.Event()
    failures: list[BaseException] = []

    def validate() -> None:
        try:
            _validate_automatic_launch_reservation(ctx)
        except BaseException as exc:  # pragma: no cover - assertion below
            failures.append(exc)
        finally:
            done.set()

    with operator_control.marker_runtime_cutover_lock(marker_path):
        thread = threading.Thread(target=validate)
        thread.start()
        # The validator has a bounded blocking marker wait and cannot pass
        # while the operator owns the cutover lock.
        time.sleep(0.05)
        assert not done.is_set()
        current, marker_sha = operator_control._load_marker(marker_path)
        current["operator_pause"] = {
            "schema_version": "arnold.megaplan.operator-pause.v1",
            "active": True,
        }
        current["should_run"] = False
        operator_control._write_marker_locked(
            marker_path,
            current,
            expected_sha256=marker_sha,
        )
    thread.join(timeout=2)
    assert done.is_set()
    assert failures == []


@pytest.mark.parametrize(
    ("label", "observation"),
    [
        ("unknown", None),
        ("stale", _native_observation(observed_at="1900-01-01T00:00:00+00:00")),
        ("mismatch", _native_observation(model="other-model")),
        ("missing", {"kind": "native_backend"}),
    ],
)
def test_invalid_backend_observation_has_zero_reservation_or_command(
    managed_observations,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    label: str,
    observation: dict[str, object] | None,
) -> None:
    command_calls: list[object] = []
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.babysitter.launch.run_managed_command",
        lambda _spec: command_calls.append(True) or 0,
    )
    if label == "unknown":
        monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_args: (_ for _ in ()).throw(worker_dispatch.CliError("route_liveness_missing", "unknown")))
    else:
        monkeypatch.setattr(worker_dispatch, "_default_native_liveness", lambda *_args, value=observation: value)

    with pytest.raises(RuntimeError, match="admission refused"):
        _admit_managed_launch(_context(tmp_path, run_id=label), _spec(tmp_path, identity=label))

    assert command_calls == []
    assert not any(item.get("event_type") == "admission_reserved" for item in _events(tmp_path))


def _typed_exception(
    code: str,
    *,
    identity: dict[str, object] = IDENTITY,
    disposition_id: str = "disp",
) -> BaseException:
    exc = RuntimeError(f"{code} from managed worker")
    exc.code = code  # type: ignore[attr-defined]
    if code == "ordinary_terminal_failure":
        exc.extra = {"worker_identity": identity, "terminal_failure": {"error": "ordinary"}}  # type: ignore[attr-defined]
    elif code == "provider_exhausted":
        key = ProviderFailureKey.derive(
            phase="babysitter",
            selected_spec=ROUTE,
            provider_failure_class="availability",
            provider_epoch_identity="epoch",
        ).value
        evidence = {
            "observation_id": "obs",
            "retryability_class": "availability",
            "exhausted_attempt_count": 1,
            "terminal_provider_evidence_id": "provider-evidence",
            "precondition_identity": "precondition",
            "provider_epoch_identity": "epoch",
            "provider_failure_key": key,
            "observed_at": "2026-08-31T00:00:00+00:00",
        }
        exc.extra = {"worker_identity": identity, "provider_evidence": evidence, "provider_failure_key": key}  # type: ignore[attr-defined]
    else:
        exc.extra = {"worker_identity": identity, "disposition_id": disposition_id}  # type: ignore[attr-defined]
    return exc


@pytest.mark.parametrize("code", ["ordinary_terminal_failure", "provider_exhausted"])
def test_typed_managed_terminal_preserves_integer_api_and_context(
    managed_observations,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    code: str,
) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.babysitter.launch.run_managed_command",
        lambda _spec: (_ for _ in ()).throw(_typed_exception(code)),
    )
    ctx = _context(tmp_path, run_id=code)
    if code == "provider_exhausted":
        with pytest.raises(RuntimeError, match="provider_degraded"):
            _admit_managed_launch(ctx, _spec(tmp_path, identity=code))
        terminals = [item for item in _events(tmp_path) if item.get("event_type") == "worker_terminal_outcome"]
        assert terminals
        assert terminals[0]["outcome_kind"] == code
        assert terminals[0]["provider"] == "codex"
        assert terminals[0]["route_liveness_kind"] == "native_backend"
        assert len(str(terminals[0]["route_liveness_identity"])) == 64
        assert terminals[0]["route_liveness_digest"]
        return
    result = _admit_managed_launch(ctx, _spec(tmp_path, identity=code))

    assert isinstance(result, int)
    assert result != 0
    terminals = [item for item in _events(tmp_path) if item.get("event_type") == "worker_terminal_outcome"]
    assert len(terminals) == 1
    assert terminals[0]["outcome_kind"] == code
    assert terminals[0]["provider"] == "codex"
    assert terminals[0]["route_liveness_kind"] == "native_backend"
    assert len(str(terminals[0]["route_liveness_identity"])) == 64
    assert terminals[0]["route_liveness_digest"]


def test_preexisting_worker_disposition_is_linked_once_and_not_coerced(
    managed_observations,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def run(spec: ManagedCommandSpec) -> int:
        events = _events(spec.run_root or tmp_path)
        reservation = next(item for item in events if item.get("event_type") == "admission_reserved")
        disposition = WorkerDisposition(
            disposition_id="disp-1",
            mode=DispositionMode.in_band.value,
            plan_id=str(reservation["plan_id"]),
            phase=str(reservation["phase"]),
            dispatch_family_id=str(reservation["dispatch_family_id"]),
            logical_dispatch_id=str(reservation["logical_dispatch_id"]),
            admission_receipt_id=str(reservation["admission_receipt_id"]),
            semantic_dispatch_fingerprint=str(reservation["semantic_dispatch_fingerprint"]),
            selected_spec=str(reservation["selected_spec"]),
            killer_kind=KillerKind.launcher_timeout.value,
            killer_identity="killer-1",
            cause_kind=CauseKind.timeout.value,
            signal=Signal.SIGTERM.value,
            elapsed_s=1.0,
            worker_identity=IDENTITY,
            observed_at=datetime.now(timezone.utc).isoformat(),
            evidence={"source": "test"},
        )
        IncidentLedger(spec.run_root or tmp_path).append_disposition(disposition)
        raise _typed_exception("worker_disposition", disposition_id="disp-1")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.babysitter.launch.run_managed_command",
        run,
    )
    ctx = _context(tmp_path, run_id="disposition")
    assert _admit_managed_launch(ctx, _spec(tmp_path, identity="disposition")) == 1
    events = _events(tmp_path)
    assert sum(item.get("event_type") == "worker_disposition" for item in events) == 1
    terminals = [item for item in events if item.get("event_type") == "worker_terminal_outcome"]
    assert len(terminals) == 1
    assert terminals[0]["outcome_kind"] == "worker_disposition"
    assert terminals[0]["disposition_id"] == "disp-1"


def test_explicit_typed_terminal_keeps_authoritative_route_context(
    managed_observations,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def run(spec: ManagedCommandSpec) -> int:
        reservation = next(
            item
            for item in _events(spec.run_root or tmp_path)
            if item.get("event_type") == "admission_reserved"
        )
        outcome = DispatchOutcome(
            kind="ordinary_terminal_failure",
            launch_state="accepted",
            plan_id=str(reservation["plan_id"]),
            phase=str(reservation["phase"]),
            dispatch_family_id=str(reservation["dispatch_family_id"]),
            logical_dispatch_id=str(reservation["logical_dispatch_id"]),
            admission_receipt_id=str(reservation["admission_receipt_id"]),
            semantic_dispatch_fingerprint=str(reservation["semantic_dispatch_fingerprint"]),
            selected_spec=str(reservation["selected_spec"]),
            worker_identity=IDENTITY,
            started_at="2026-08-31T00:00:00+00:00",
            finished_at="2026-08-31T00:00:01+00:00",
            terminal_failure={"error": "explicit"},
        )
        exc = RuntimeError("explicit typed outcome")
        exc.dispatch_outcome = outcome  # type: ignore[attr-defined]
        raise exc

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.babysitter.launch.run_managed_command",
        run,
    )
    ctx = _context(tmp_path, run_id="explicit")
    assert _admit_managed_launch(ctx, _spec(tmp_path, identity="explicit")) == 1
    assert ctx["dispatch_outcome"]["kind"] == "ordinary_terminal_failure"
    terminal = next(item for item in _events(tmp_path) if item.get("event_type") == "worker_terminal_outcome")
    assert terminal["route_liveness_kind"] == "native_backend"
    assert terminal["provider"] == "codex"


def test_forged_typed_identity_becomes_unresolved_and_never_relaunches(
    managed_observations,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    forged = DispatchOutcome(
        kind="ordinary_terminal_failure",
        launch_state="accepted",
        plan_id="wrong-plan",
        phase="babysitter",
        dispatch_family_id="family",
        logical_dispatch_id="logical",
        admission_receipt_id="wrong-receipt",
        semantic_dispatch_fingerprint="f" * 64,
        selected_spec=ROUTE,
        worker_identity=IDENTITY,
        started_at="2026-08-31T00:00:00+00:00",
        finished_at="2026-08-31T00:00:01+00:00",
        terminal_failure={"error": "forged"},
    )
    exc = RuntimeError("forged")
    exc.dispatch_outcome = forged  # type: ignore[attr-defined]
    calls: list[object] = []
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.babysitter.launch.run_managed_command",
        lambda _spec: calls.append(True) or (_ for _ in ()).throw(exc),
    )
    with pytest.raises(ManagedLaunchUnresolved) as caught:
        _admit_managed_launch(_context(tmp_path), _spec(tmp_path))
    assert caught.value.outcome.kind == "unresolved_launch"
    assert calls == [True]
    assert not any(item.get("event_type") == "worker_terminal_outcome" for item in _events(tmp_path))


def test_append_failure_holds_reservation_and_second_attempt_does_not_relaunch(
    managed_observations,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cloud.babysitter.launch.run_managed_command",
        lambda _spec: calls.append(True) or 0,
    )
    ledger = IncidentLedger(tmp_path)
    original = ledger.append_terminal_outcome
    monkeypatch.setattr(IncidentLedger, "append_terminal_outcome", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("link unavailable")))
    ctx = _context(tmp_path, run_id="append-failure")
    with pytest.raises(ManagedLaunchUnresolved):
        _admit_managed_launch(ctx, _spec(tmp_path, identity="append-failure"))
    assert calls == [True]
    monkeypatch.setattr(IncidentLedger, "append_terminal_outcome", original)
    with pytest.raises(RuntimeError):
        _admit_managed_launch(ctx, _spec(tmp_path, identity="append-failure"))
    assert calls == [True]
