from pathlib import Path
import os
import signal
import subprocess
from types import SimpleNamespace
import pytest

from arnold_pipelines.megaplan import managed_agent
from arnold_pipelines.megaplan.cloud import operator_control


def test_known_worker_without_context_is_zero_signal(tmp_path: Path, monkeypatch):
    calls = []
    monkeypatch.delenv("ARNOLD_WORKER_EXECUTION_CONTEXT", raising=False)
    monkeypatch.setattr(managed_agent.os, "kill", lambda *args: calls.append(args))

    assert not managed_agent.signal_managed_process(
        tmp_path / "manifest.json",
        {"run_id": "uncertified"},
        os.getpid(),
        signal.SIGTERM,
        cause_kind="timeout",
        ladder_step="term",
        worker=True,
    )
    assert calls == []


def test_parent_lifecycle_records_before_signal(tmp_path: Path, monkeypatch):
    calls = []
    monkeypatch.setattr(managed_agent.os, "kill", lambda *args: calls.append(args))
    monkeypatch.setattr(managed_agent.os, "getpgid", lambda pid: pid)

    assert managed_agent.signal_managed_process(
        tmp_path / "manifest.json",
        {"run_id": "supervisor"},
        os.getpid(),
        signal.SIGTERM,
        cause_kind="terminate",
        ladder_step="term",
        worker=False,
    )
    assert calls == [(os.getpid(), signal.SIGTERM)]
    events = list((tmp_path / ".megaplan" / "incident-ledger" / "events.jsonl").read_text().splitlines())
    assert any('"event_type":"non_worker_signal_disposition"' in item for item in events)


def test_operator_identity_is_positive_or_fail_closed(monkeypatch):
    monkeypatch.setattr(operator_control.subprocess, "run", lambda *args, **kwargs: type(
        "Result", (), {"returncode": 0, "stdout": "Mon Jan  1 00:00:00 2024\n"}
    )())
    identity = operator_control._pid_start_identity(123)
    assert identity and identity.startswith("ps-lstart:")


def test_native_timeout_uses_controlled_teardown_before_returning(monkeypatch):
    from arnold_pipelines.megaplan import workers as workers_package  # noqa: F401
    from arnold_pipelines.megaplan.workers import _impl
    from arnold_pipelines.megaplan.custody.common_worker_dispatch import SpawnedChildControl

    class Authority:
        def __init__(self):
            self.process = None

        def register(self, registration):
            return registration

        def immediate_timeout(self, process, **_kwargs):
            self.process = process
            process.terminate()
            process.wait(timeout=2)
            return {"state": "already_dead"}

        def signal_ladder(self, process, **_kwargs):
            self.process = process
            return {"state": "confirmation_pending"}

    authority = Authority()
    # Match the production WBC shape: the wrapper exposes signal_ladder while
    # its bound signal implementation carries the controlled authority.
    control = SpawnedChildControl(
        register_impl=authority.register,
        signal_impl=authority.signal_ladder,
        production=False,
    )
    try:
        with pytest.raises(Exception):
            _impl.run_command(
                ["/bin/sleep", "10"], cwd=Path.cwd(), timeout=0.05,
                spawn_registration_callback=control,
            )
    finally:
        if authority.process is not None and authority.process.poll() is None:
            authority.process.kill()
            authority.process.wait(timeout=2)
    assert authority.process is not None
    assert authority.process.returncode is not None


def test_spawn_registration_failure_returns_typed_cleanup_hold_without_signal():
    from arnold_pipelines.megaplan.workers import _impl

    seen = {}

    def legacy_callback(registration):
        seen["pid"] = registration["worker_identity"]["pid"]
        raise RuntimeError("legacy admission failure")

    with pytest.raises(_impl.SpawnRegistrationError) as raised:
        _impl.run_command(
            ["/bin/sleep", "20"],
            cwd=Path.cwd(),
            timeout=1,
            spawn_registration_callback=legacy_callback,
        )
    hold = raised.value.cleanup_hold
    try:
        assert hold.pid == seen["pid"]
        assert hold.process_start_identity
        assert raised.value.extra["spawn_cleanup_hold"]["state"] == "cleanup_hold"
        assert raised.value.extra["admission_error"] == "legacy admission failure"
        assert raised.value.dispatch_outcome["kind"] == "unresolved_launch"
        assert raised.value.dispatch_outcome["launch_state"] == "ambiguous"
        assert raised.value.dispatch_outcome["worker_identity"]["pid"] == hold.pid
        # A legacy callback has no durable cleanup authority.  Its synthetic
        # registration hash must never be advertised as a ledger reference.
        assert raised.value.dispatch_outcome["reconciliation_event_id"] is None
        assert raised.value.extra["dispatch_outcome"] == raised.value.dispatch_outcome
        receipt = SimpleNamespace(
            plan_id="unknown",
            phase="unknown",
            dispatch_family_id="unknown",
            logical_dispatch_id="unknown",
            admission_receipt_id="unknown",
            semantic_dispatch_fingerprint="unknown",
            normalized_spec="unknown",
            provider=None,
            route_liveness_kind=None,
            route_liveness_identity=None,
            route_liveness_digest=None,
        )
        from arnold_pipelines.megaplan.cloud.worker_dispatch import (
            _outcome_from_terminal_exception,
        )
        translated = _outcome_from_terminal_exception(
            raised.value, receipt, "started", "finished"
        )
        assert translated is not None
        assert translated.kind == "unresolved_launch"
        assert translated.launch_state == "ambiguous"
        assert hold.reconcile(timeout_s=0.01)["state"] == "live"
    finally:
        hold.process.kill()
        hold.process.wait(timeout=2)


def test_delegated_admission_failure_handoffs_hold_without_raw_signal():
    from arnold_pipelines.megaplan.workers import _impl
    from arnold_pipelines.megaplan.custody.common_worker_dispatch import SpawnedChildControl

    class FailingAuthority:
        def __init__(self):
            self.hold = None
            self.signal_calls = 0
            self.context = {
                "ledger_root": str(Path.cwd()),
                "plan_id": "plan",
                "phase": "execute",
                "dispatch_family_id": "family",
                "logical_dispatch_id": "logical",
                "admission_receipt_id": "receipt",
                "semantic_dispatch_fingerprint": "f" * 64,
                "selected_spec": "codex:gpt-5.5",
                "physical_door_id": "door",
            }

        def register(self, _registration):
            raise RuntimeError("controlled admission failure")

        def signal_ladder(self, _process, **_kwargs):
            self.signal_calls += 1
            return {"state": "unresolved", "reason": "identity not registered"}

        def handoff_spawn_cleanup(self, hold):
            self.hold = hold
            return {"state": "cleanup_hold", "event_type": "spawn_cleanup_hold"}

    authority = FailingAuthority()
    control = SpawnedChildControl(
        register_impl=lambda _registration: None,
        delegate=authority,
        production=True,
    )
    with pytest.raises(_impl.SpawnRegistrationError) as raised:
        _impl.run_command(
            ["/bin/sleep", "20"],
            cwd=Path.cwd(),
            timeout=1,
            spawn_registration_callback=control,
        )
    hold = raised.value.cleanup_hold
    try:
        assert authority.hold is hold
        assert authority.signal_calls == 0
        assert raised.value.extra["cleanup_result"]["attempted"] is False
        assert raised.value.extra["cleanup_result"]["handoff_required"] is True
        assert raised.value.extra["cleanup_result"]["handoff_supported"] is True
        assert raised.value.dispatch_outcome["kind"] == "unresolved_launch"
        assert raised.value.dispatch_outcome["launch_state"] == "ambiguous"
        assert raised.value.dispatch_outcome["worker_identity"]["pid"] == hold.pid
        assert raised.value.dispatch_outcome["admission_receipt_id"] == "receipt"
        assert raised.value.dispatch_outcome["semantic_dispatch_fingerprint"] == "f" * 64
        # This compatibility fake returns no typed persisted handoff ID.
        assert raised.value.dispatch_outcome["reconciliation_event_id"] is None
        assert hold.reconcile(timeout_s=0.01)["state"] == "live"
        assert raised.value.extra["spawn_cleanup_hold"]["reconciliation_route"].endswith(
            "spawn-registration-reconcile.v1"
        )
    finally:
        hold.process.kill()
        hold.process.wait(timeout=2)


def test_production_handoff_id_replaces_synthetic_and_survives_unwind():
    from arnold_pipelines.megaplan.cloud.worker_dispatch import _outcome_from_terminal_exception
    from arnold_pipelines.megaplan.custody.common_worker_dispatch import SpawnedChildControl
    from arnold_pipelines.megaplan.workers import _impl

    class CanonicalAuthority:
        def __init__(self):
            self.process = None

        def register(self, _registration):
            raise RuntimeError("admission append failed")

        def handoff(self, process):
            self.process = process
            return {
                "state": "cleanup_hold",
                "handoff": {
                    "event_type": "spawn_cleanup_handoff",
                    "event_id": "canonical-handoff-event",
                    "handoff_id": "canonical-handoff-id",
                },
            }

    authority = CanonicalAuthority()
    control = SpawnedChildControl(
        register_impl=authority.register,
        handoff_impl=authority.handoff,
        production=True,
    )
    with pytest.raises(_impl.SpawnRegistrationError) as raised:
        _impl.run_command(
            ["/bin/sleep", "20"],
            cwd=Path.cwd(),
            timeout=1,
            spawn_registration_callback=control,
        )
    hold = raised.value.cleanup_hold
    try:
        canonical = "canonical-handoff-id"
        assert authority.process is hold.process
        assert hold.spawn_event_id != canonical
        assert raised.value.dispatch_outcome["reconciliation_event_id"] == canonical
        assert raised.value.extra["cleanup_result"]["handoff_event_id"] == canonical
        receipt = SimpleNamespace(
            plan_id="unknown",
            phase="unknown",
            dispatch_family_id="unknown",
            logical_dispatch_id="unknown",
            admission_receipt_id="unknown",
            semantic_dispatch_fingerprint="unknown",
            normalized_spec="unknown",
            provider=None,
            route_liveness_kind=None,
            route_liveness_identity=None,
            route_liveness_digest=None,
        )
        translated = _outcome_from_terminal_exception(
            raised.value, receipt, "started", "finished"
        )
        assert translated is not None
        assert translated.kind == "unresolved_launch"
        assert translated.reconciliation_event_id == canonical
        assert authority.process.poll() is None
    finally:
        hold.process.kill()
        hold.process.wait(timeout=2)


def test_spawn_registration_success_path_remains_command_result():
    from arnold_pipelines.megaplan.workers import _impl

    result = _impl.run_command(
        ["/bin/sh", "-c", "exit 0"],
        cwd=Path.cwd(),
        timeout=1,
        spawn_registration_callback=lambda _registration: None,
    )
    assert result.returncode == 0
    assert result.worker_identity is not None
    assert result.worker_identity["pid"] > 0
