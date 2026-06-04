"""Unit tests for the Arnold recovery-classifier seam."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import FrozenSet

import pytest

from arnold.runtime.recovery import (
    RECOVERY_STATUS_VALUES,
    ArnoldRecoveryPolicy,
    NullRecoveryPolicy,
    RecoveryContext,
    RecoveryDecision,
)


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------


class TestRecoveryStatusValues:
    def test_frozenset_contains_three_prescribed_values(self) -> None:
        assert RECOVERY_STATUS_VALUES == frozenset({"decided", "unsupported", "unset"})


# ---------------------------------------------------------------------------
# RecoveryContext
# ---------------------------------------------------------------------------


class TestRecoveryContext:
    def test_error_can_be_string_or_exception(self) -> None:
        ctx_str = RecoveryContext(error="timeout")
        assert ctx_str.error == "timeout"

        ex = RuntimeError("boom")
        ctx_ex = RecoveryContext(error=ex)
        assert ctx_ex.error is ex

    def test_unit_is_opaque_any(self) -> None:
        ctx = RecoveryContext(error="err", unit={"id": "u1"})
        assert ctx.unit == {"id": "u1"}

    def test_metadata_defaults_to_empty_dict(self) -> None:
        ctx = RecoveryContext(error="err")
        assert ctx.metadata == {}

    def test_metadata_carries_plugin_owned_annotations(self) -> None:
        ctx = RecoveryContext(
            error="err", metadata={"retry_budget": 3, "phase": "execute"}
        )
        assert ctx.metadata["retry_budget"] == 3

    def test_frozen(self) -> None:
        ctx = RecoveryContext(error="err")
        with pytest.raises(Exception):
            ctx.error = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RecoveryDecision
# ---------------------------------------------------------------------------


class TestRecoveryDecision:
    def test_defaults_to_unset(self) -> None:
        d = RecoveryDecision()
        assert d.status == "unset"
        assert d.action == ""
        assert d.reason == ""
        assert d.budget_consumed == {}

    def test_decided_decision(self) -> None:
        d = RecoveryDecision(
            status="decided",
            action="retry",
            reason="transient error",
            budget_consumed={"retries_used": 1},
        )
        assert d.status == "decided"
        assert d.action == "retry"
        assert d.reason == "transient error"
        assert d.budget_consumed == {"retries_used": 1}

    def test_unsupported_decision(self) -> None:
        d = RecoveryDecision(
            status="unsupported",
            reason="heartbeat is not supported in M3d",
        )
        assert d.status == "unsupported"

    def test_frozen(self) -> None:
        d = RecoveryDecision()
        with pytest.raises(Exception):
            d.status = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ArnoldRecoveryPolicy Protocol
# ---------------------------------------------------------------------------


class TestArnoldRecoveryPolicyProtocol:
    def test_protocol_is_defined(self) -> None:
        assert ArnoldRecoveryPolicy is not None

    def test_classify_method_present(self) -> None:
        assert hasattr(ArnoldRecoveryPolicy, "classify")

    def test_null_policy_satisfies_protocol(self) -> None:
        # Structural check: NullRecoveryPolicy has the classify method
        assert hasattr(NullRecoveryPolicy, "classify")
        np = NullRecoveryPolicy()
        assert callable(np.classify)


# ---------------------------------------------------------------------------
# NullRecoveryPolicy
# ---------------------------------------------------------------------------


class TestNullRecoveryPolicy:
    def test_always_returns_unset(self) -> None:
        np = NullRecoveryPolicy()
        ctx = RecoveryContext(error="anything")
        decision = np.classify("anything", ctx)
        assert decision.status == "unset"
        assert decision.action == ""

    def test_reason_indicates_no_policy_registered(self) -> None:
        np = NullRecoveryPolicy()
        ctx = RecoveryContext(error="timeout")
        decision = np.classify("timeout", ctx)
        assert "No recovery policy registered" in decision.reason

    def test_different_errors_all_return_unset(self) -> None:
        np = NullRecoveryPolicy()
        for error in ["timeout", "connection_error", RuntimeError("crash")]:
            ctx = RecoveryContext(error=error)
            decision = np.classify(error, ctx)
            assert decision.status == "unset"


# ---------------------------------------------------------------------------
# Boundary: zero Megaplan imports in recovery.py
# ---------------------------------------------------------------------------


_RECOVERY_FILE = Path(__file__).resolve().parent.parent.parent.parent / "arnold" / "runtime" / "recovery.py"


class TestRecoveryBoundary:
    """Verify recovery.py respects the Arnold runtime boundary."""

    def test_no_megaplan_imports(self) -> None:
        """recovery.py must not contain ``import megaplan`` or ``from megaplan``."""
        tree = ast.parse(_RECOVERY_FILE.read_text(), filename=str(_RECOVERY_FILE))
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == "megaplan":
                        violations.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None and node.module.split(".")[0] == "megaplan":
                    violations.append(f"from {node.module}")
        assert not violations, f"recovery.py has forbidden imports: {violations}"

    def test_no_forbidden_vocabulary_literals(self) -> None:
        """recovery.py must not contain Megaplan policy literal strings."""
        forbidden: FrozenSet[str] = frozenset(
            {"planning", "critique", "finalize", "tiebreaker", "escalate",
             "force_proceed", "abort", "replan", "add_note"}
        )
        tree = ast.parse(_RECOVERY_FILE.read_text(), filename=str(_RECOVERY_FILE))
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in forbidden:
                    violations.append(f"line {node.lineno}: '{node.value}'")
        assert not violations, f"recovery.py has forbidden literals: {violations}"
