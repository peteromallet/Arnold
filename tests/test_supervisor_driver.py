"""Deterministic tests for megaplan.supervisor.driver using fake seams.

All tests stay fake-driven — they use fake RunDriver/PackRunner implementations
and mock the real auto_drive to avoid invoking real subprocess execution or M6
discovered-pack infrastructure.  The goal is protocol-shape verification and
adapter-contract correctness.
"""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from megaplan.auto import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PHASE_TIMEOUT_SECONDS,
    DEFAULT_POLL_SLEEP_SECONDS,
    DEFAULT_STALL_THRESHOLD,
    DEFAULT_STATUS_TIMEOUT_SECONDS,
    ESCALATE_ACTIONS,
    DriverOutcome,
)
from megaplan.supervisor.driver import (
    DEFAULT_ESCALATE_ACTION,
    DefaultRunDriver,
    PackRunner,
    PhaseCompleteHook,
    RunDriver,
    RunRequest,
    RunWriter,
)
from megaplan.supervisor.model import RunNode

# ──────────────────────────────────────────────────────────────────────────────
# Reference helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_fake_outcome(**overrides: object) -> DriverOutcome:
    """Build a deterministic DriverOutcome without touching real auto-drive."""
    kwargs: dict[str, object] = {
        "status": "done",
        "plan": "fake-plan",
        "final_state": "complete",
        "iterations": 1,
        "reason": "",
        "last_phase": None,
        "events": [],
        "total_cost_usd": None,
        "cost_cap_usd": None,
        "context_retries_used": 0,
        "max_context_retries": None,
        "external_retries_used": 0,
        "max_external_retries": None,
        "blocked_retries_used": 0,
        "max_blocked_retries": None,
        "blocking_reasons": [],
        "tier_escalations_used": 0,
        "escalation_tier_pin": None,
    }
    kwargs.update(overrides)
    return DriverOutcome(**kwargs)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────────────
# RunRequest
# ──────────────────────────────────────────────────────────────────────────────


class TestRunRequest:
    """RunRequest is the stable supervisor request payload."""

    def test_dataclass_is_frozen(self) -> None:
        req = RunRequest(root=Path("."), plan="t")
        with pytest.raises(FrozenInstanceError):
            req.plan = "other"  # type: ignore[misc]

    def test_all_fields_have_defaults_except_root_and_plan(self) -> None:
        req = RunRequest(root=Path("."), plan="demo")
        assert req.stall_threshold == DEFAULT_STALL_THRESHOLD
        assert req.max_iterations == DEFAULT_MAX_ITERATIONS
        assert req.poll_sleep == DEFAULT_POLL_SLEEP_SECONDS
        assert req.phase_timeout == DEFAULT_PHASE_TIMEOUT_SECONDS
        assert req.status_timeout == DEFAULT_STATUS_TIMEOUT_SECONDS
        assert req.escalate_action == DEFAULT_ESCALATE_ACTION
        assert req.on_phase_complete is None
        # pytest may wrap sys.stdout, so compare the underlying name/identity
        assert req.writer.__name__ == sys.stdout.write.__name__

    def test_default_escalate_action_matches_auto_first(self) -> None:
        assert DEFAULT_ESCALATE_ACTION == ESCALATE_ACTIONS[0]

    def test_custom_fields_preserved(self) -> None:
        called: list[object] = []

        def fake_hook(
            plan: str, iteration: int, active_step: str, state: str
        ) -> None:
            called.append((plan, iteration, active_step, state))

        req = RunRequest(
            root=Path("/tmp"),
            plan="custom-plan",
            stall_threshold=7,
            max_iterations=42,
            poll_sleep=0.3,
            phase_timeout=999.0,
            status_timeout=123.0,
            escalate_action="fail",
            on_phase_complete=fake_hook,
            writer=lambda s: None,
        )
        assert req.root == Path("/tmp")
        assert req.plan == "custom-plan"
        assert req.stall_threshold == 7
        assert req.max_iterations == 42
        assert req.poll_sleep == 0.3
        assert req.phase_timeout == 999.0
        assert req.status_timeout == 123.0
        assert req.escalate_action == "fail"
        assert req.on_phase_complete is fake_hook
        assert req.writer is not sys.stdout.write

    def test_two_requests_with_same_params_are_distinct_objects(self) -> None:
        a = RunRequest(root=Path("."), plan="p")
        b = RunRequest(root=Path("."), plan="p")
        assert a == b
        assert a is not b


# ──────────────────────────────────────────────────────────────────────────────
# RunDriver protocol
# ──────────────────────────────────────────────────────────────────────────────


class TestRunDriverProtocol:
    """RunDriver is a @runtime_checkable Protocol fake-friendly seam."""

    def test_runtime_checkable_accepts_fake_with_drive_method(self) -> None:
        class Fake:
            def drive(self, request: RunRequest) -> DriverOutcome:
                return _make_fake_outcome(plan=request.plan)

        assert isinstance(Fake(), RunDriver)

    def test_runtime_checkable_rejects_missing_drive(self) -> None:
        class Bad:
            pass

        assert not isinstance(Bad(), RunDriver)

    def test_runtime_checkable_rejects_wrong_signature(self) -> None:
        class Wrong:
            def drive(self, x: int) -> None:  # type: ignore[empty-body]
                ...

        # Protocol just checks existence of 'drive' attribute, not arity
        # at runtime.  So wrong-signature still passes isinstance (this is
        # normal Protocol behaviour).
        assert isinstance(Wrong(), RunDriver)

    def test_fake_driver_drive_returns_correct_shape(self) -> None:
        class Fake:
            def drive(self, request: RunRequest) -> DriverOutcome:
                return _make_fake_outcome(
                    plan=request.plan,
                    status="stalled",
                    iterations=7,
                )

        fake = Fake()
        assert isinstance(fake, RunDriver)
        outcome = fake.drive(
            RunRequest(root=Path("."), plan="test-plan")
        )
        assert isinstance(outcome, DriverOutcome)
        assert outcome.plan == "test-plan"
        assert outcome.status == "stalled"
        assert outcome.iterations == 7

    def test_fake_driver_requires_no_real_subprocess(self) -> None:
        """Prove a pure-RAM fake passes the protocol without any IO."""
        class Fake:
            def drive(self, request: RunRequest) -> DriverOutcome:
                return _make_fake_outcome(
                    plan=request.plan,
                    reason="purely-deterministic",
                )

        outcome = Fake().drive(RunRequest(root=Path("."), plan="no-io"))
        assert outcome.reason == "purely-deterministic"


# ──────────────────────────────────────────────────────────────────────────────
# DefaultRunDriver
# ──────────────────────────────────────────────────────────────────────────────


class TestDefaultRunDriver:
    """DefaultRunDriver adapts the real auto.drive but we mock it here."""

    def test_exists_and_has_drive_method(self) -> None:
        driver = DefaultRunDriver()
        assert callable(driver.drive)

    def test_drive_forwards_to_auto_drive_correctly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[dict[str, object]] = []

        def fake_auto_drive(
            plan: str,
            cwd: Path | None = None,
            stall_threshold: int = DEFAULT_STALL_THRESHOLD,
            max_iterations: int = DEFAULT_MAX_ITERATIONS,
            on_escalate: str = DEFAULT_ESCALATE_ACTION,
            poll_sleep: float = DEFAULT_POLL_SLEEP_SECONDS,
            phase_timeout: float = DEFAULT_PHASE_TIMEOUT_SECONDS,
            status_timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS,
            on_phase_complete: PhaseCompleteHook | None = None,
            writer: RunWriter = sys.stdout.write,
        ) -> DriverOutcome:
            captured.append(
                {
                    "plan": plan,
                    "cwd": cwd,
                    "stall_threshold": stall_threshold,
                    "max_iterations": max_iterations,
                    "on_escalate": on_escalate,
                    "poll_sleep": poll_sleep,
                    "phase_timeout": phase_timeout,
                    "status_timeout": status_timeout,
                    "on_phase_complete": on_phase_complete,
                    "writer": writer,
                }
            )
            return _make_fake_outcome(plan=plan)

        monkeypatch.setattr(
            "megaplan.supervisor.driver.auto_drive", fake_auto_drive
        )

        called: list[tuple[str, int, str, str]] = []

        def my_hook(
            plan: str, iteration: int, active_step: str, state: str
        ) -> None:
            called.append((plan, iteration, active_step, state))

        req = RunRequest(
            root=Path("/my/root"),
            plan="forwarded-plan",
            stall_threshold=11,
            max_iterations=99,
            poll_sleep=0.1,
            phase_timeout=444.0,
            status_timeout=77.0,
            escalate_action="abort",
            on_phase_complete=my_hook,
            writer=sys.stderr.write,
        )

        outcome = DefaultRunDriver().drive(req)

        assert len(captured) == 1
        c = captured[0]
        assert c["plan"] == "forwarded-plan"
        assert c["cwd"] == Path("/my/root")
        assert c["stall_threshold"] == 11
        assert c["max_iterations"] == 99
        assert c["on_escalate"] == "abort"
        assert c["poll_sleep"] == 0.1
        assert c["phase_timeout"] == 444.0
        assert c["status_timeout"] == 77.0
        assert c["on_phase_complete"] is my_hook
        # pytest may wrap sys.stderr; compare name not identity
        assert c["writer"].__name__ == sys.stderr.write.__name__

        assert outcome.plan == "forwarded-plan"

    def test_drive_with_minimal_request_uses_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[dict[str, object]] = []

        def fake_auto_drive(
            plan: str,
            **kwargs: object,
        ) -> DriverOutcome:
            captured.append({"plan": plan, **kwargs})
            return _make_fake_outcome(plan=plan)

        monkeypatch.setattr(
            "megaplan.supervisor.driver.auto_drive", fake_auto_drive
        )

        req = RunRequest(root=Path("."), plan="minimal")
        outcome = DefaultRunDriver().drive(req)

        assert len(captured) == 1
        c = captured[0]
        assert c["stall_threshold"] == DEFAULT_STALL_THRESHOLD
        assert c["max_iterations"] == DEFAULT_MAX_ITERATIONS
        assert c["poll_sleep"] == DEFAULT_POLL_SLEEP_SECONDS
        assert c["phase_timeout"] == DEFAULT_PHASE_TIMEOUT_SECONDS
        assert c["status_timeout"] == DEFAULT_STATUS_TIMEOUT_SECONDS
        assert c["on_escalate"] == DEFAULT_ESCALATE_ACTION
        assert outcome.plan == "minimal"


# ──────────────────────────────────────────────────────────────────────────────
# PackRunner protocol
# ──────────────────────────────────────────────────────────────────────────────


class TestPackRunnerProtocol:
    """PackRunner is a @runtime_checkable protocol for M6 pack seam."""

    def test_runtime_checkable_accepts_fake_with_prepare_plan(self) -> None:
        class FakePack:
            def prepare_plan(self, *, root: Path, node: RunNode) -> str:
                return node.spec_ref

        assert isinstance(FakePack(), PackRunner)

    def test_runtime_checkable_rejects_missing_prepare_plan(self) -> None:
        class Bad:
            pass

        assert not isinstance(Bad(), PackRunner)

    def test_fake_pack_runner_returns_plan_name_from_node(self) -> None:
        class FakePack:
            def prepare_plan(self, *, root: Path, node: RunNode) -> str:
                return f"packed::{node.spec_ref}"

        pack = FakePack()
        assert isinstance(pack, PackRunner)

        node = RunNode(node_id="n1", spec_ref="profile:alpha")
        plan = pack.prepare_plan(root=Path("/tmp"), node=node)
        assert plan == "packed::profile:alpha"

    def test_fake_pack_runner_requires_no_real_m6_execution(self) -> None:
        """PackRunner tests stay purely in-RAM — no pack discovery or exec."""

        class FakePack:
            def prepare_plan(self, *, root: Path, node: RunNode) -> str:
                return "always-the-same-plan"

        outcome = FakePack().prepare_plan(
            root=Path("/nonexistent"),
            node=RunNode(node_id="ghost", spec_ref="spec:ghost"),
        )
        assert outcome == "always-the-same-plan"
        # The Path("/nonexistent") is never accessed — fake stays pure.


# ──────────────────────────────────────────────────────────────────────────────
# Composed fake flow
# ──────────────────────────────────────────────────────────────────────────────


class TestComposedFakeFlow:
    """End-to-end fake RunDriver + PackRunner without real IO."""

    def test_fake_pack_then_fake_drive_produces_outcome(self) -> None:
        class FakePack:
            def prepare_plan(self, *, root: Path, node: RunNode) -> str:
                return f"plan::{node.node_id}"

        class FakeDriver:
            def drive(self, request: RunRequest) -> DriverOutcome:
                return _make_fake_outcome(
                    plan=request.plan,
                    status="done",
                    iterations=3,
                )

        pack: PackRunner = FakePack()
        driver: RunDriver = FakeDriver()

        node = RunNode(node_id="step-1", spec_ref="chain:step-1")
        plan_name = pack.prepare_plan(root=Path("."), node=node)
        assert plan_name == "plan::step-1"

        outcome = driver.drive(
            RunRequest(root=Path("."), plan=plan_name)
        )
        assert outcome.plan == "plan::step-1"
        assert outcome.status == "done"
        assert outcome.iterations == 3


# ──────────────────────────────────────────────────────────────────────────────
# Export surface
# ──────────────────────────────────────────────────────────────────────────────


class TestExportSurface:
    """Verify the public surface exported from driver and supervisor __init__."""

    DRIVER_ALL = {
        "DEFAULT_ESCALATE_ACTION",
        "DefaultRunDriver",
        "PackRunner",
        "PhaseCompleteHook",
        "RunDriver",
        "RunRequest",
        "RunWriter",
    }

    def test_driver_module_all_matches(self) -> None:
        from megaplan.supervisor import driver as dmod

        assert set(dmod.__all__) == self.DRIVER_ALL

    def test_supervisor_init_exports_driver_items(self) -> None:
        from megaplan.supervisor import __all__ as supervisor_all

        supervisor_set = set(supervisor_all)
        for name in self.DRIVER_ALL:
            assert name in supervisor_set, f"{name} missing from supervisor __all__"

    def test_every_exported_symbol_is_importable(self) -> None:
        from megaplan.supervisor import (
            DEFAULT_ESCALATE_ACTION,
            DefaultRunDriver,
            PackRunner,
            PhaseCompleteHook,
            RunDriver,
            RunRequest,
            RunWriter,
        )

        # If we got here without ImportError, it works.
        assert DEFAULT_ESCALATE_ACTION
        assert DefaultRunDriver
        assert PackRunner
        assert PhaseCompleteHook
        assert RunDriver
        assert RunRequest
        assert RunWriter

    def test_run_writer_is_callable_str_object(self) -> None:
        writer: RunWriter = lambda s: None
        assert callable(writer)
        writer("test")  # smoke


# ──────────────────────────────────────────────────────────────────────────────
# Protocol dispatch pattern
# ──────────────────────────────────────────────────────────────────────────────


class TestProtocolDispatchPattern:
    """Demonstrate the intended usage pattern for chain/bakeoff runners."""

    def test_dispatch_through_protocol_without_knowing_impl(self) -> None:
        """A supervisor runner only knows the protocol, not the concrete type."""

        class FakeDriver:
            def drive(self, request: RunRequest) -> DriverOutcome:
                return _make_fake_outcome(plan=request.plan, status="done")

        def orchestrate(driver: RunDriver, plan: str) -> DriverOutcome:
            # This is what the chain runner will do — call through the
            # protocol without caring whether it's a fake or DefaultRunDriver.
            return driver.drive(
                RunRequest(root=Path("."), plan=plan)
            )

        result = orchestrate(FakeDriver(), "orchestrated-plan")
        assert result.plan == "orchestrated-plan"
        assert result.status == "done"

    def test_default_driver_satisfies_protocol(self) -> None:
        """DefaultRunDriver passes isinstance(RunDriver) check."""
        assert isinstance(DefaultRunDriver(), RunDriver)

    def test_default_run_driver_is_not_a_pack_runner(self) -> None:
        """Cross-protocol check: RunDriver impl is not accidentally a PackRunner."""
        assert not isinstance(DefaultRunDriver(), PackRunner)
