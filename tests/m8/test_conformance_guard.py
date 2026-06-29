"""Guard test proving ``arnold.conformance`` is importable and callable from M8.

Inventory of ``tests/m8/`` and ``tests/arnold/`` found no true duplicates of
the four AR1 conformance checks (adapter protocol, ContractResult round-trip,
decision vocabulary, join delegation) that should be replaced with
``arnold.conformance`` assertion wrappers.

Existing tests target:
- Validator-level integration (test_route_bypass.py) — not direct adapter protocol
- Implementation-specific error messages (test_step_invocation.py) — not
  generic behavioral conformance
- Detailed field-by-field assertions (test_contract_result.py) — not
  high-level round-trip checks
- Executor integration (test_executor_hooks.py) — not hook delegation isolation
- Local adapter registry (test_evidence_pack_expressibility.py) — not
  production adapter surface

This guard test proves the conformance suite is functional and importable
from outside the conformance test directory.
"""

from __future__ import annotations

from arnold.conformance import (
    ConformanceCheckResult,
    ConformanceSuiteResult,
    assert_conformance,
    assert_suite_compliant,
    run_conformance_suite,
)
from arnold.conformance.checks import (
    check_adapter_protocol_conformance,
    check_adapter_unknown_kind_fail_closed,
    check_adapter_smoke_invocation,
    check_adapter_registry_round_trip,
    check_contract_result_schema_round_trip,
    check_contract_result_schema_version_skew,
    check_contract_result_empty_schema_version_accepted,
)
from arnold.execution.step_invocation import StepInvocation, StepInvocationAdapterRegistry


class TestM8ConformanceGuard:
    """Guard: ``arnold.conformance`` is importable and callable from M8 tests."""

    def test_all_five_public_symbols_importable(self) -> None:
        """ConformanceCheckResult, ConformanceSuiteResult, assert_conformance,
        assert_suite_compliant, run_conformance_suite are all importable."""
        assert ConformanceCheckResult is not None
        assert ConformanceSuiteResult is not None
        assert assert_conformance is not None
        assert assert_suite_compliant is not None
        assert run_conformance_suite is not None

    def test_all_seven_check_functions_importable(self) -> None:
        """All seven check functions from arnold.conformance.checks are importable."""
        assert check_adapter_protocol_conformance is not None
        assert check_adapter_unknown_kind_fail_closed is not None
        assert check_adapter_smoke_invocation is not None
        assert check_adapter_registry_round_trip is not None
        assert check_contract_result_schema_round_trip is not None
        assert check_contract_result_schema_version_skew is not None
        assert check_contract_result_empty_schema_version_accepted is not None

    def test_run_conformance_suite_returns_conformance_suite_result(self) -> None:
        """Default run_conformance_suite() returns ConformanceSuiteResult."""
        result = run_conformance_suite(suite_id="m8-guard")
        assert isinstance(result, ConformanceSuiteResult)
        assert result.suite_id == "m8-guard"

    def test_run_conformance_suite_all_passes_on_default(self) -> None:
        """Default run_conformance_suite() reports all-pass."""
        result = run_conformance_suite(suite_id="m8-guard")
        assert result.passed is True
        assert result.failure_count == 0

    def test_assert_conformance_passes_green(self) -> None:
        """assert_conformance does not raise on a green result."""
        good = ConformanceCheckResult(check_id="m8-test", passed=True)
        assert_conformance(good)  # should not raise

    def test_assert_conformance_raises_on_red(self) -> None:
        """assert_conformance raises AssertionError on a red result."""
        import pytest

        bad = ConformanceCheckResult(
            check_id="m8-fail", passed=False, message="M8 guard failure"
        )
        with pytest.raises(AssertionError, match="m8-fail"):
            assert_conformance(bad)

    def test_assert_suite_compliant_on_green_suite(self) -> None:
        """assert_suite_compliant does not raise on all-pass suite."""
        suite = run_conformance_suite(suite_id="m8-guard")
        assert_suite_compliant(suite)  # should not raise

    def test_adapter_unknown_kind_fail_closed_from_m8(self) -> None:
        """check_adapter_unknown_kind_fail_closed is callable from M8."""
        result = check_adapter_unknown_kind_fail_closed()
        assert result.passed is True
        assert result.check_id == "adapter-unknown-kind-fail-closed"

    def test_contract_schema_round_trip_from_m8(self) -> None:
        """check_contract_result_schema_round_trip is callable from M8."""
        result = check_contract_result_schema_round_trip()
        assert result.passed is True
