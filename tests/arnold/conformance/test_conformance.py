"""Conformance result and import-isolation tests for ``arnold.conformance``.

Covers:
* ``ConformanceCheckResult`` frozen dataclass behaviour.
* ``ConformanceSuiteResult`` frozen dataclass behaviour and computed properties.
* ``assert_conformance`` and ``assert_suite_compliant`` thin assertion helpers.
* Import isolation: no ``megaplan`` in ``sys.modules`` after importing
  ``arnold.conformance`` (verified via subprocess with meta_path blocker).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import FrozenInstanceError

import pytest

from arnold.conformance import (
    ConformanceCheckResult,
    ConformanceSuiteResult,
    assert_conformance,
    assert_suite_compliant,
)


# ---------------------------------------------------------------------------
# Subprocess script — import-isolation gate
# ---------------------------------------------------------------------------

_IMPORT_ISOLATION_SCRIPT = textwrap.dedent("""\
import sys

# Block any megaplan import
class _BlockMegaplanFinder:
    def find_spec(self, fullname, path, target=None):
        if fullname == "megaplan" or fullname.startswith("arnold.pipelines.megaplan."):
            raise ModuleNotFoundError(
                f"megaplan import blocked by leak gate: {fullname}"
            )
        if fullname == "arnold.pipelines.megaplan" or fullname.startswith(
            "arnold.pipelines.megaplan."
        ):
            raise ModuleNotFoundError(
                f"arnold.pipelines.megaplan import blocked by leak gate: {fullname}"
            )
        return None

sys.meta_path.insert(0, _BlockMegaplanFinder())

# Import arnold.conformance — must succeed with zero megaplan side-effects
import arnold.conformance  # noqa: E402

# Prove megaplan never leaked into sys.modules
assert "megaplan" not in sys.modules, (
    f"megaplan leaked into sys.modules: {sorted(k for k in sys.modules if 'megaplan' in k)}"
)
""")


# ---------------------------------------------------------------------------
# ConformanceCheckResult
# ---------------------------------------------------------------------------

class TestConformanceCheckResult:
    """Behaviour of the :class:`ConformanceCheckResult` frozen dataclass."""

    def test_construct_with_all_fields(self) -> None:
        result = ConformanceCheckResult(
            check_id="adapter-protocol",
            passed=True,
            message="all good",
            details={"count": 3},
        )
        assert result.check_id == "adapter-protocol"
        assert result.passed is True
        assert result.message == "all good"
        assert result.details == {"count": 3}

    def test_construct_with_defaults(self) -> None:
        result = ConformanceCheckResult(check_id="some-check", passed=False)
        assert result.check_id == "some-check"
        assert result.passed is False
        assert result.message == ""
        assert result.details is None

    def test_passed_true_message_empty(self) -> None:
        result = ConformanceCheckResult(check_id="ok", passed=True)
        assert result.passed is True
        assert result.message == ""

    def test_passed_false_with_message(self) -> None:
        result = ConformanceCheckResult(
            check_id="fail", passed=False, message="missing field X"
        )
        assert result.passed is False
        assert result.message == "missing field X"

    def test_frozen(self) -> None:
        result = ConformanceCheckResult(check_id="chk", passed=True)
        with pytest.raises(FrozenInstanceError):
            result.check_id = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = ConformanceCheckResult(check_id="x", passed=True, message="ok")
        b = ConformanceCheckResult(check_id="x", passed=True, message="ok")
        c = ConformanceCheckResult(check_id="x", passed=False, message="ok")
        assert a == b
        assert a != c

    def test_hashable(self) -> None:
        result = ConformanceCheckResult(check_id="h", passed=True)
        assert hash(result) == hash(result)
        # Can be used in a set
        s = {result}
        assert len(s) == 1

    def test_details_none_by_default(self) -> None:
        result = ConformanceCheckResult(check_id="no-details", passed=True)
        assert result.details is None

    def test_details_can_be_list(self) -> None:
        result = ConformanceCheckResult(
            check_id="list-details", passed=False, details=[1, 2, 3]
        )
        assert result.details == [1, 2, 3]

    def test_details_can_be_dict(self) -> None:
        result = ConformanceCheckResult(
            check_id="dict-details", passed=False, details={"a": 1}
        )
        assert result.details == {"a": 1}

    def test_details_can_be_string(self) -> None:
        result = ConformanceCheckResult(
            check_id="str-details", passed=False, details="some detail string"
        )
        assert result.details == "some detail string"


# ---------------------------------------------------------------------------
# ConformanceSuiteResult
# ---------------------------------------------------------------------------

class TestConformanceSuiteResult:
    """Behaviour of the :class:`ConformanceSuiteResult` frozen dataclass."""

    @staticmethod
    def _pass(check_id: str) -> ConformanceCheckResult:
        return ConformanceCheckResult(check_id=check_id, passed=True)

    @staticmethod
    def _fail(check_id: str, message: str = "failed") -> ConformanceCheckResult:
        return ConformanceCheckResult(check_id=check_id, passed=False, message=message)

    def test_construct_empty(self) -> None:
        suite = ConformanceSuiteResult(suite_id="empty")
        assert suite.suite_id == "empty"
        assert suite.checks == ()
        assert suite.check_count == 0
        assert suite.failure_count == 0
        assert suite.failures == ()
        assert suite.passed is True

    def test_construct_with_checks(self) -> None:
        checks = (self._pass("a"), self._pass("b"))
        suite = ConformanceSuiteResult(suite_id="s1", checks=checks)
        assert suite.checks == checks
        assert suite.check_count == 2

    def test_passed_all_pass(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="all-ok",
            checks=(self._pass("a"), self._pass("b"), self._pass("c")),
        )
        assert suite.passed is True

    def test_passed_one_fails(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="one-fail",
            checks=(self._pass("a"), self._fail("b"), self._pass("c")),
        )
        assert suite.passed is False

    def test_passed_all_fail(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="all-fail",
            checks=(self._fail("a"), self._fail("b")),
        )
        assert suite.passed is False

    def test_failures_empty_when_all_pass(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="no-fail",
            checks=(self._pass("a"), self._pass("b")),
        )
        assert suite.failures == ()

    def test_failures_subset(self) -> None:
        f1 = self._fail("a", "msg-a")
        f2 = self._fail("c", "msg-c")
        suite = ConformanceSuiteResult(
            suite_id="mixed",
            checks=(f1, self._pass("b"), f2),
        )
        assert suite.failures == (f1, f2)
        assert suite.failure_count == 2

    def test_check_count_on_nonempty(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="counted",
            checks=(self._pass("a"), self._pass("b"), self._pass("c")),
        )
        assert suite.check_count == 3

    def test_frozen(self) -> None:
        suite = ConformanceSuiteResult(suite_id="frozen")
        with pytest.raises(FrozenInstanceError):
            suite.suite_id = "thawed"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = ConformanceSuiteResult(suite_id="eq", checks=(self._pass("x"),))
        b = ConformanceSuiteResult(suite_id="eq", checks=(self._pass("x"),))
        c = ConformanceSuiteResult(suite_id="neq", checks=(self._pass("x"),))
        assert a == b
        assert a != c

    def test_hashable(self) -> None:
        suite = ConformanceSuiteResult(suite_id="hashable")
        assert hash(suite) == hash(suite)
        s = {suite}
        assert len(s) == 1

    def test_checks_are_tuple(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="tuple-check",
            checks=(self._pass("a"), self._pass("b")),
        )
        assert isinstance(suite.checks, tuple)


# ---------------------------------------------------------------------------
# assert_conformance
# ---------------------------------------------------------------------------

class TestAssertConformance:
    """Behaviour of the ``assert_conformance`` thin assertion helper."""

    def test_passed_result_does_not_raise(self) -> None:
        result = ConformanceCheckResult(check_id="ok", passed=True)
        # Should not raise
        assert_conformance(result)

    def test_passed_result_returns_none(self) -> None:
        result = ConformanceCheckResult(check_id="ok", passed=True)
        ret = assert_conformance(result)
        assert ret is None

    def test_failed_result_raises_assertion_error(self) -> None:
        result = ConformanceCheckResult(
            check_id="fail", passed=False, message="something went wrong"
        )
        with pytest.raises(AssertionError) as exc_info:
            assert_conformance(result)
        error_text = str(exc_info.value)
        assert "[fail]" in error_text
        assert "something went wrong" in error_text

    def test_failed_result_no_message_fallback(self) -> None:
        result = ConformanceCheckResult(check_id="no-msg", passed=False)
        with pytest.raises(AssertionError) as exc_info:
            assert_conformance(result)
        error_text = str(exc_info.value)
        assert "[no-msg]" in error_text
        assert "check failed" in error_text


# ---------------------------------------------------------------------------
# assert_suite_compliant
# ---------------------------------------------------------------------------

class TestAssertSuiteCompliant:
    """Behaviour of the ``assert_suite_compliant`` thin assertion helper."""

    @staticmethod
    def _pass(cid: str) -> ConformanceCheckResult:
        return ConformanceCheckResult(check_id=cid, passed=True)

    @staticmethod
    def _fail(cid: str, msg: str = "failed") -> ConformanceCheckResult:
        return ConformanceCheckResult(check_id=cid, passed=False, message=msg)

    def test_empty_suite_does_not_raise(self) -> None:
        suite = ConformanceSuiteResult(suite_id="empty")
        assert_suite_compliant(suite)

    def test_all_pass_does_not_raise(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="ok",
            checks=(self._pass("a"), self._pass("b"), self._pass("c")),
        )
        assert_suite_compliant(suite)

    def test_returns_none_on_pass(self) -> None:
        suite = ConformanceSuiteResult(suite_id="ret", checks=(self._pass("x"),))
        ret = assert_suite_compliant(suite)
        assert ret is None

    def test_single_failure_raises(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="s1",
            checks=(self._pass("a"), self._fail("b", "bad thing"), self._pass("c")),
        )
        with pytest.raises(AssertionError) as exc_info:
            assert_suite_compliant(suite)
        error_text = str(exc_info.value)
        assert "s1" in error_text
        assert "1 failure" in error_text
        assert "[b]" in error_text
        assert "bad thing" in error_text

    def test_multiple_failures_raises_with_all_listed(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="multi",
            checks=(
                self._fail("a", "err-a"),
                self._pass("b"),
                self._fail("c", "err-c"),
            ),
        )
        with pytest.raises(AssertionError) as exc_info:
            assert_suite_compliant(suite)
        error_text = str(exc_info.value)
        assert "multi" in error_text
        assert "2 failure" in error_text
        assert "[a]" in error_text
        assert "err-a" in error_text
        assert "[c]" in error_text
        assert "err-c" in error_text

    def test_failure_with_empty_message_uses_fallback(self) -> None:
        suite = ConformanceSuiteResult(
            suite_id="no-msg",
            checks=(self._fail("x", ""),),
        )
        with pytest.raises(AssertionError) as exc_info:
            assert_suite_compliant(suite)
        error_text = str(exc_info.value)
        assert "check failed" in error_text


# ---------------------------------------------------------------------------
# Import isolation
# ---------------------------------------------------------------------------

class TestConformanceImportIsolation:
    """``arnold.conformance`` must not pull ``megaplan`` into ``sys.modules``."""

    def test_no_megaplan_in_sys_modules_after_import(self) -> None:
        """In-process check: ``megaplan`` absent from ``sys.modules`` after import."""
        # Force a clean state by removing megaplan if already present
        # (it won't be, but this makes the test idempotent)
        for name in list(sys.modules):
            if name == "megaplan" or name.startswith("arnold.pipelines.megaplan."):
                sys.modules.pop(name, None)
        assert "megaplan" not in sys.modules, (
            f"megaplan already in sys.modules before conformance import: "
            f"{sorted(k for k in sys.modules if 'megaplan' in k)}"
        )

    def test_subprocess_with_megaplan_blocker_imports_conformance(self) -> None:
        """Subprocess blocks megaplan imports, then imports arnold.conformance.

        If arnold.conformance transitively imports megaplan the subprocess
        fails, proving the import-isolation boundary is hermetic.
        """
        result = subprocess.run(
            [sys.executable, "-c", _IMPORT_ISOLATION_SCRIPT],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Subprocess exited {result.returncode}.\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
        assert result.stderr == "", (
            f"Subprocess stderr expected empty but got:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

class TestConformancePublicExports:
    """The four public symbols must be importable from ``arnold.conformance``."""

    def test_conformance_check_result_importable(self) -> None:
        from arnold.conformance import ConformanceCheckResult as C
        assert C is not None

    def test_conformance_suite_result_importable(self) -> None:
        from arnold.conformance import ConformanceSuiteResult as C
        assert C is not None

    def test_assert_conformance_importable(self) -> None:
        from arnold.conformance import assert_conformance as fn
        assert fn is not None

    def test_assert_suite_compliant_importable(self) -> None:
        from arnold.conformance import assert_suite_compliant as fn
        assert fn is not None

    def test_run_conformance_suite_importable(self) -> None:
        from arnold.conformance import run_conformance_suite as fn
        assert fn is not None

    def test_all_exports_match_expected_count(self) -> None:
        import arnold.conformance
        assert len(arnold.conformance.__all__) == 5
        expected = {
            "ConformanceCheckResult",
            "ConformanceSuiteResult",
            "assert_conformance",
            "assert_suite_compliant",
            "run_conformance_suite",
        }
        assert set(arnold.conformance.__all__) == expected


# ---------------------------------------------------------------------------
# Suite-level aggregation — all-green
# ---------------------------------------------------------------------------


class TestRunConformanceSuiteAllGreen:
    """All-green ``run_conformance_suite`` results across all four domains."""

    def test_default_suite_all_pass(self) -> None:
        from arnold.conformance import run_conformance_suite
        result = run_conformance_suite()
        assert result.passed is True
        assert result.failure_count == 0
        assert result.failures == ()

    def test_default_suite_returns_conformance_suite_result(self) -> None:
        from arnold.conformance import run_conformance_suite, ConformanceSuiteResult
        result = run_conformance_suite()
        assert isinstance(result, ConformanceSuiteResult)

    def test_default_suite_has_expected_suite_id(self) -> None:
        from arnold.conformance import run_conformance_suite
        result = run_conformance_suite()
        assert result.suite_id == "ar1-conformance"

    def test_default_suite_has_nonzero_check_count(self) -> None:
        from arnold.conformance import run_conformance_suite
        result = run_conformance_suite()
        # Default: adapter-protocol + unknown-kind-fail-closed +
        #   schema-version-skew + empty-schema-version + schema-round-trip = 5
        assert result.check_count >= 5

    def test_all_checks_passed_in_default_suite(self) -> None:
        from arnold.conformance import run_conformance_suite
        result = run_conformance_suite()
        for check in result.checks:
            assert check.passed, f"{check.check_id}: {check.message}"

    def test_per_check_diagnostics_preserved(self) -> None:
        from arnold.conformance import run_conformance_suite
        result = run_conformance_suite()
        for check in result.checks:
            assert isinstance(check.check_id, str)
            assert check.check_id != ""
            assert isinstance(check.passed, bool)
            assert isinstance(check.message, str)

    def test_each_check_is_conformance_check_result(self) -> None:
        from arnold.conformance import run_conformance_suite, ConformanceCheckResult
        result = run_conformance_suite()
        for check in result.checks:
            assert isinstance(check, ConformanceCheckResult)

    def test_passed_property_consistent_with_failure_count(self) -> None:
        from arnold.conformance import run_conformance_suite
        result = run_conformance_suite()
        assert result.passed == (result.failure_count == 0)

    def test_with_custom_suite_id(self) -> None:
        from arnold.conformance import run_conformance_suite
        result = run_conformance_suite(suite_id="my-custom-id")
        assert result.suite_id == "my-custom-id"

    def test_with_pipelines_all_green(self) -> None:
        """Passing a green pipeline adds routing checks without failures."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import Stage, Pipeline, Edge

        class _MinimalStep:
            def __init__(self, name: str = "min") -> None:
                self.name = name
                self.kind = "compute"

            def run(self, ctx):
                from arnold.pipeline.types import StepResult
                return StepResult(next="halt")

        router = Stage(
            name="router",
            step=_MinimalStep("router"),
            decision_vocabulary=frozenset({"proceed", "iterate"}),
            override_vocabulary=frozenset({"force_halt"}),
            edges=(
                Edge(label="continue", target="next_stage", kind="normal"),
                Edge(label="proceed", target="after_proceed", kind="decision"),
                Edge(label="iterate", target="after_iterate", kind="decision"),
                Edge(label="override force_halt", target="halt", kind="override"),
            ),
        )
        pipeline = Pipeline(
            entry="router",
            stages={
                "router": router,
                "next_stage": Stage(name="next_stage", step=_MinimalStep("next")),
                "after_proceed": Stage(name="after_proceed", step=_MinimalStep("ap")),
                "after_iterate": Stage(name="after_iterate", step=_MinimalStep("ai")),
            },
        )
        result = run_conformance_suite(pipelines=[pipeline])
        assert result.passed is True
        # Should have routing checks present
        routing_ids = {"routing-vocabulary-coverage", "routing-vocabulary-edge-consistency"}
        found = {c.check_id for c in result.checks} & routing_ids
        assert len(found) >= 2

    def test_with_contracts_all_green(self) -> None:
        """Passing sample contracts adds round-trip checks without failures."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import ContractResult, ContractStatus

        cr = ContractResult(status=ContractStatus.COMPLETED)
        result = run_conformance_suite(sample_contracts=[cr])
        assert result.passed is True
        # Should have a contract-schema-round-trip check
        round_trip_checks = [c for c in result.checks
                             if c.check_id == "contract-result-round-trip-fidelity"]
        assert len(round_trip_checks) >= 1

    def test_all_four_domains_populated_all_green(self) -> None:
        """Full suite with all four domains populated returns all-pass."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import (
            ContractResult, ContractStatus, Stage, Pipeline, Edge,
        )
        from arnold.pipeline.hooks import NullExecutorHooks

        class _MinimalStep:
            def __init__(self, name: str = "min") -> None:
                self.name = name
                self.kind = "compute"

            def run(self, ctx):
                from arnold.pipeline.types import StepResult
                return StepResult(next="halt")

        router = Stage(
            name="router",
            step=_MinimalStep("router"),
            decision_vocabulary=frozenset({"proceed"}),
            edges=(
                Edge(label="continue", target="next_stage", kind="normal"),
                Edge(label="proceed", target="after_proceed", kind="decision"),
            ),
        )
        pipeline = Pipeline(
            entry="router",
            stages={
                "router": router,
                "next_stage": Stage(name="next_stage", step=_MinimalStep("next")),
                "after_proceed": Stage(name="after_proceed", step=_MinimalStep("ap")),
            },
        )
        cr = ContractResult(status=ContractStatus.COMPLETED)
        hooks = NullExecutorHooks()

        result = run_conformance_suite(
            pipelines=[pipeline],
            sample_contracts=[cr],
            hooks=hooks,
        )
        assert result.passed is True
        assert result.failure_count == 0
        # Should have checks from all four domains
        check_ids = {c.check_id for c in result.checks}
        assert "adapter-protocol" in check_ids
        assert "adapter-unknown-kind-fail-closed" in check_ids
        assert "contract-result-round-trip-fidelity" in check_ids
        assert "contract-result-schema-version-skew" in check_ids
        assert "contract-result-empty-schema-version-accepted" in check_ids
        assert "routing-vocabulary-coverage" in check_ids
        assert "join-delegation" in check_ids


# ---------------------------------------------------------------------------
# Suite-level aggregation — seeded violations
# ---------------------------------------------------------------------------


class TestRunConformanceSuiteSeededViolations:
    """Seeded violations with diagnostics retained at the suite level."""

    def test_non_delegating_hook_failure_detected(self) -> None:
        """A non-delegating hook causes join delegation checks to fail."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import StepResult, ParallelStage, StepContext

        class _NonDelegatingHooks:
            def join_parallel_results(
                self, stage, ctx, child_results,
            ) -> StepResult:
                return StepResult(next="non_delegated", outputs={"_delegated": False})

        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(hooks=hooks)  # type: ignore[arg-type]
        assert result.passed is False
        assert result.failure_count >= 1

    def test_failure_messages_retained_at_suite_level(self) -> None:
        """Failure messages from individual checks are available in suite.failures."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import StepResult, ParallelStage, StepContext

        class _NonDelegatingHooks:
            def join_parallel_results(
                self, stage, ctx, child_results,
            ) -> StepResult:
                return StepResult(next="non_delegated", outputs={"_delegated": False})

        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(hooks=hooks)  # type: ignore[arg-type]
        for failure in result.failures:
            assert failure.passed is False
            assert isinstance(failure.message, str)
            # Each failure should have a meaningful non-empty message
            assert len(failure.message) > 0

    def test_failure_check_ids_retained(self) -> None:
        """Each failing check preserves its check_id at the suite level."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import StepResult

        class _NonDelegatingHooks:
            def join_parallel_results(self, stage, ctx, child_results):
                return StepResult(next="non_delegated", outputs={"_delegated": False})

        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(hooks=hooks)  # type: ignore[arg-type]
        for failure in result.failures:
            assert isinstance(failure.check_id, str)
            assert failure.check_id != ""

    def test_failure_count_matches_failures_length(self) -> None:
        """failure_count property matches len(failures)."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import StepResult

        class _NonDelegatingHooks:
            def join_parallel_results(self, stage, ctx, child_results):
                return StepResult(next="non_delegated", outputs={"_delegated": False})

        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(hooks=hooks)  # type: ignore[arg-type]
        assert result.failure_count == len(result.failures)

    def test_mixed_pass_fail_suite(self) -> None:
        """Suite with both passing and failing checks reports correctly."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import StepResult

        class _NonDelegatingHooks:
            def join_parallel_results(self, stage, ctx, child_results):
                return StepResult(next="non_delegated", outputs={"_delegated": False})

        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(hooks=hooks)  # type: ignore[arg-type]
        # Some checks should pass (adapter, contract), some fail (join)
        passing = [c for c in result.checks if c.passed]
        failing = [c for c in result.checks if not c.passed]
        assert len(passing) > 0
        assert len(failing) > 0
        assert len(passing) + len(failing) == result.check_count

    def test_routing_uncovered_label_failure_detected(self) -> None:
        """Pipeline with uncovered vocabulary label causes routing failure."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import Stage, Pipeline, Edge

        class _MinimalStep:
            def __init__(self, name: str = "min") -> None:
                self.name = name
                self.kind = "compute"

            def run(self, ctx):
                from arnold.pipeline.types import StepResult
                return StepResult(next="halt")

        # Vocabulary declares {"proceed"} but edge uses "iterate" — uncovered
        router = Stage(
            name="router",
            step=_MinimalStep("router"),
            decision_vocabulary=frozenset({"proceed"}),
            edges=(
                Edge(label="continue", target="next_stage", kind="normal"),
                Edge(label="iterate", target="after_iterate", kind="decision"),
            ),
        )
        pipeline = Pipeline(
            entry="router",
            stages={
                "router": router,
                "next_stage": Stage(name="next_stage", step=_MinimalStep("next")),
                "after_iterate": Stage(name="after_iterate", step=_MinimalStep("ai")),
            },
        )
        result = run_conformance_suite(pipelines=[pipeline])
        assert result.passed is False
        # The routing-vocabulary-coverage check should fail
        cov_failures = [c for c in result.failures
                        if c.check_id == "routing-vocabulary-coverage"]
        assert len(cov_failures) >= 1

    def test_routing_failure_diagnostics_retained(self) -> None:
        """Routing failure preserves message and details at suite level."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import Stage, Pipeline, Edge

        class _MinimalStep:
            def __init__(self, name: str = "min") -> None:
                self.name = name
                self.kind = "compute"

            def run(self, ctx):
                from arnold.pipeline.types import StepResult
                return StepResult(next="halt")

        router = Stage(
            name="router",
            step=_MinimalStep("router"),
            decision_vocabulary=frozenset({"proceed"}),
            edges=(
                Edge(label="continue", target="next_stage", kind="normal"),
                Edge(label="iterate", target="after_iterate", kind="decision"),
            ),
        )
        pipeline = Pipeline(
            entry="router",
            stages={
                "router": router,
                "next_stage": Stage(name="next_stage", step=_MinimalStep("next")),
                "after_iterate": Stage(name="after_iterate", step=_MinimalStep("ai")),
            },
        )
        result = run_conformance_suite(pipelines=[pipeline])
        cov_failures = [c for c in result.failures
                        if c.check_id == "routing-vocabulary-coverage"]
        assert len(cov_failures) >= 1
        failure = cov_failures[0]
        assert "router" in failure.message
        assert "iterate" in failure.message
        # Details should contain the uncovered edge information
        assert failure.details is not None

    def test_checks_are_tuple_on_green_and_red(self) -> None:
        """checks is always a tuple, regardless of pass/fail."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import StepResult

        class _NonDelegatingHooks:
            def join_parallel_results(self, stage, ctx, child_results):
                return StepResult(next="non_delegated", outputs={"_delegated": False})

        green_result = run_conformance_suite()
        assert isinstance(green_result.checks, tuple)

        hooks = _NonDelegatingHooks()
        red_result = run_conformance_suite(hooks=hooks)  # type: ignore[arg-type]
        assert isinstance(red_result.checks, tuple)

    def test_failures_is_tuple(self) -> None:
        """failures property returns a tuple."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import StepResult

        class _NonDelegatingHooks:
            def join_parallel_results(self, stage, ctx, child_results):
                return StepResult(next="non_delegated", outputs={"_delegated": False})

        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(hooks=hooks)  # type: ignore[arg-type]
        assert isinstance(result.failures, tuple)

    def test_suite_result_is_frozen(self) -> None:
        """Suite result is immutable even when containing failures."""
        from arnold.conformance import run_conformance_suite
        import pytest
        from dataclasses import FrozenInstanceError

        result = run_conformance_suite()
        with pytest.raises(FrozenInstanceError):
            result.suite_id = "mutated"  # type: ignore[misc]

    def test_suite_id_preserved_on_failure(self) -> None:
        """suite_id is preserved even when suite has failures."""
        from arnold.conformance import run_conformance_suite
        from arnold.pipeline.types import StepResult

        class _NonDelegatingHooks:
            def join_parallel_results(self, stage, ctx, child_results):
                return StepResult(next="non_delegated", outputs={"_delegated": False})

        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(
            hooks=hooks,  # type: ignore[arg-type]
            suite_id="failing-suite",
        )
        assert result.suite_id == "failing-suite"

    def test_assert_suite_compliant_raises_on_red(self) -> None:
        """assert_suite_compliant raises AssertionError on a failing suite."""
        from arnold.conformance import run_conformance_suite, assert_suite_compliant
        from arnold.pipeline.types import StepResult
        import pytest

        class _NonDelegatingHooks:
            def join_parallel_results(self, stage, ctx, child_results):
                return StepResult(next="non_delegated", outputs={"_delegated": False})

        hooks = _NonDelegatingHooks()
        result = run_conformance_suite(hooks=hooks)  # type: ignore[arg-type]
        assert result.passed is False
        with pytest.raises(AssertionError) as exc_info:
            assert_suite_compliant(result)
        error_text = str(exc_info.value)
        assert result.suite_id in error_text
        assert str(result.failure_count) in error_text

    def test_assert_suite_compliant_does_not_raise_on_green(self) -> None:
        """assert_suite_compliant does not raise on a passing suite."""
        from arnold.conformance import run_conformance_suite, assert_suite_compliant

        result = run_conformance_suite()
        assert result.passed is True
        # Should not raise
        assert_suite_compliant(result)
