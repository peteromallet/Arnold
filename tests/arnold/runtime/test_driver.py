"""Tests for ``arnold.runtime.driver`` (T5 / SC5)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from arnold.runtime.driver import (
    ADVANCE_OUTCOME_KINDS,
    CHECKPOINT_OUTCOME_KINDS,
    ISOLATION_MODES,
    AdvanceOutcome,
    CheckpointOutcome,
    StepwiseDriver,
)
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.resume import ResumeCursorRef


# ---------------------------------------------------------------------------
# Fake driver — minimal StepwiseDriver implementation used in protocol tests
# ---------------------------------------------------------------------------


class _FakeDriver:
    """Minimal concrete StepwiseDriver for test composition."""

    def __init__(self, mode: str = "in_process") -> None:
        self.isolation_mode = mode
        self._advances: list[RuntimeEnvelope] = []
        self._checkpoints: list[RuntimeEnvelope] = []

    def advance(self, envelope: RuntimeEnvelope) -> AdvanceOutcome:
        self._advances.append(envelope)
        return AdvanceOutcome(kind="advanced", payload={"run_id": envelope.run_id})

    def checkpoint(self, envelope: RuntimeEnvelope) -> CheckpointOutcome:
        self._checkpoints.append(envelope)
        return CheckpointOutcome(kind="advanced", payload={"checkpointed": True})

    def resume(
        self,
        envelope: RuntimeEnvelope,
        cursor: ResumeCursorRef,
    ) -> RuntimeEnvelope:
        return envelope


# ---------------------------------------------------------------------------
# IsolationMode constant
# ---------------------------------------------------------------------------


class TestIsolationMode:
    def test_isolation_modes_is_frozenset(self) -> None:
        assert isinstance(ISOLATION_MODES, frozenset)

    def test_isolation_modes_has_exactly_two_members(self) -> None:
        assert len(ISOLATION_MODES) == 2

    def test_isolation_modes_contains_in_process(self) -> None:
        assert "in_process" in ISOLATION_MODES

    def test_isolation_modes_contains_subprocess_isolated(self) -> None:
        assert "subprocess_isolated" in ISOLATION_MODES

    def test_isolation_modes_exact_membership(self) -> None:
        assert ISOLATION_MODES == frozenset({"in_process", "subprocess_isolated"})


# ---------------------------------------------------------------------------
# AdvanceOutcome
# ---------------------------------------------------------------------------


class TestAdvanceOutcome:
    def test_advance_outcome_is_frozen(self) -> None:
        outcome = AdvanceOutcome(kind="advanced")
        with pytest.raises(FrozenInstanceError):
            outcome.kind = "halted"  # type: ignore[misc]

    def test_advance_outcome_kinds_exact_set(self) -> None:
        assert ADVANCE_OUTCOME_KINDS == frozenset({"advanced", "halted", "awaiting", "failed"})

    def test_all_prescribed_advance_kinds_are_constructible(self) -> None:
        for kind in ADVANCE_OUTCOME_KINDS:
            outcome = AdvanceOutcome(kind=kind)
            assert outcome.kind == kind

    def test_advance_outcome_payload_defaults_empty(self) -> None:
        assert AdvanceOutcome(kind="advanced").payload == {}

    def test_advance_outcome_errors_defaults_empty_tuple(self) -> None:
        assert AdvanceOutcome(kind="failed").errors == ()

    def test_advance_outcome_accepts_opaque_payload(self) -> None:
        outcome = AdvanceOutcome(kind="advanced", payload={"arbitrary": 42})
        assert outcome.payload["arbitrary"] == 42


# ---------------------------------------------------------------------------
# CheckpointOutcome
# ---------------------------------------------------------------------------


class TestCheckpointOutcome:
    def test_checkpoint_outcome_is_frozen(self) -> None:
        outcome = CheckpointOutcome(kind="advanced")
        with pytest.raises(FrozenInstanceError):
            outcome.kind = "halted"  # type: ignore[misc]

    def test_checkpoint_outcome_kinds_exact_set(self) -> None:
        assert CHECKPOINT_OUTCOME_KINDS == frozenset({"advanced", "halted", "awaiting", "failed"})

    def test_all_prescribed_checkpoint_kinds_are_constructible(self) -> None:
        for kind in CHECKPOINT_OUTCOME_KINDS:
            outcome = CheckpointOutcome(kind=kind)
            assert outcome.kind == kind

    def test_checkpoint_outcome_payload_defaults_empty(self) -> None:
        assert CheckpointOutcome(kind="advanced").payload == {}

    def test_checkpoint_outcome_errors_defaults_empty_tuple(self) -> None:
        assert CheckpointOutcome(kind="failed").errors == ()


# ---------------------------------------------------------------------------
# StepwiseDriver Protocol
# ---------------------------------------------------------------------------


class TestStepwiseDriverProtocol:
    def test_fake_driver_satisfies_protocol(self) -> None:
        assert isinstance(_FakeDriver(), StepwiseDriver)

    def test_fake_driver_isolation_mode_is_in_isolation_modes(self) -> None:
        for mode in ISOLATION_MODES:
            driver = _FakeDriver(mode)
            assert driver.isolation_mode in ISOLATION_MODES

    def test_advance_returns_advance_outcome(self) -> None:
        driver = _FakeDriver()
        env = RuntimeEnvelope(plugin_id="p", run_id="r-1")
        outcome = driver.advance(env)
        assert isinstance(outcome, AdvanceOutcome)
        assert outcome.kind in ADVANCE_OUTCOME_KINDS

    def test_checkpoint_returns_checkpoint_outcome(self) -> None:
        driver = _FakeDriver()
        env = RuntimeEnvelope(plugin_id="p", run_id="r-1")
        outcome = driver.checkpoint(env)
        assert isinstance(outcome, CheckpointOutcome)
        assert outcome.kind in CHECKPOINT_OUTCOME_KINDS

    def test_resume_returns_runtime_envelope(self) -> None:
        driver = _FakeDriver()
        env = RuntimeEnvelope(plugin_id="p", run_id="r-1")
        cursor = ResumeCursorRef(plugin_id="p", run_id="r-1", cursor={})
        result = driver.resume(env, cursor)
        assert isinstance(result, RuntimeEnvelope)

    def test_compose_fake_driver_with_runtime_envelope_from_t2(self) -> None:
        """Verify fake driver composes correctly with a fully-populated RuntimeEnvelope."""
        env = RuntimeEnvelope(
            plugin_id="test-plugin",
            manifest_hash="abc123",
            run_id="run-42",
            artifact_root="/tmp/artifacts",
        )
        driver = _FakeDriver("subprocess_isolated")

        adv = driver.advance(env)
        assert isinstance(adv, AdvanceOutcome)
        assert adv.kind in ADVANCE_OUTCOME_KINDS
        assert adv.payload.get("run_id") == "run-42"

        chk = driver.checkpoint(env)
        assert isinstance(chk, CheckpointOutcome)
        assert chk.kind in CHECKPOINT_OUTCOME_KINDS

        cursor = ResumeCursorRef(plugin_id="test-plugin", run_id="run-42", cursor={"step": 3})
        resumed = driver.resume(env, cursor)
        assert isinstance(resumed, RuntimeEnvelope)
        assert resumed is env

        assert driver._advances[0] is env
        assert driver._checkpoints[0] is env

    def test_driver_protocol_is_runtime_checkable(self) -> None:
        assert hasattr(StepwiseDriver, "__protocol_attrs__") or isinstance(
            _FakeDriver(), StepwiseDriver
        )
