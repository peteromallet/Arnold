"""Join delegation conformance tests for ``arnold.conformance.join``.

Covers:
* Green fixtures — default delegation to ``stage.join`` via ``NullExecutorHooks``,
  child-result forwarding, context forwarding, and the full
  ``run_join_conformance_suite`` returning all-pass results.
* Seeded red fixtures — a deliberately non-delegating custom hook that does
  **not** call ``stage.join``, proving the non-delegation check detects
  the override correctly.
"""

from __future__ import annotations

import pytest

from arnold.conformance import ConformanceCheckResult
from arnold.conformance.join import (
    check_join_delegation,
    check_join_delegation_with_child_results,
    check_join_delegation_non_delegating,
    check_join_delegation_context_forwarding,
    run_join_conformance_suite,
)
from arnold.execution.hooks import ExecutorHooks, NullExecutorHooks
from arnold.pipeline.types import (
    ParallelStage,
    StepContext,
    StepResult,
)


# ---------------------------------------------------------------------------
# Green fixtures — default delegation
# ---------------------------------------------------------------------------

class TestJoinDelegationGreen:
    """Green fixtures for ``check_join_delegation`` with default delegation."""

    def test_null_hooks_delegates_to_stage_join(self) -> None:
        result = check_join_delegation()
        assert isinstance(result, ConformanceCheckResult)
        assert result.check_id == "join-delegation"
        assert result.passed is True

    def test_null_hooks_returns_passed_result(self) -> None:
        result = check_join_delegation()
        assert result.message == ""

    def test_explicit_null_hooks_delegates_to_stage_join(self) -> None:
        hooks = NullExecutorHooks()
        result = check_join_delegation(hooks)
        assert result.passed is True

    def test_delegation_is_default_behavior(self) -> None:
        """The default path (no hooks) delegates to stage.join and returns sentinel."""
        hooks = NullExecutorHooks()
        stage = _make_sentinel_stage()
        ctx = StepContext(artifact_root="/tmp/test", state=None)
        child_results = [StepResult(next="child_1")]
        joined = hooks.join_parallel_results(stage, ctx, child_results)
        # Default delegation returns the sentinel's result
        assert isinstance(joined, StepResult)

    def test_multiple_child_results_delegated(self) -> None:
        hooks = NullExecutorHooks()
        stage = _make_sentinel_stage()
        ctx = StepContext(artifact_root="/tmp/test", state=None)
        child_results = [
            StepResult(next="a", outputs={"idx": 0}),
            StepResult(next="b", outputs={"idx": 1}),
            StepResult(next="c", outputs={"idx": 2}),
        ]
        joined = hooks.join_parallel_results(stage, ctx, child_results)
        assert isinstance(joined, StepResult)


class TestJoinDelegationChildResultsGreen:
    """Green fixtures for ``check_join_delegation_with_child_results``."""

    def test_null_hooks_forwards_child_results(self) -> None:
        result = check_join_delegation_with_child_results()
        assert result.check_id == "join-delegation-child-results"
        assert result.passed is True

    def test_explicit_null_hooks_forwards_child_results(self) -> None:
        hooks = NullExecutorHooks()
        result = check_join_delegation_with_child_results(hooks)
        assert result.passed is True

    def test_child_results_forwarded_correctly_direct_proof(self) -> None:
        """Direct proof: child results are forwarded to stage.join."""
        received: list[list[StepResult]] = []

        def recording_join(
            child_results: list[StepResult],
            ctx: StepContext,
        ) -> StepResult:
            received.append(list(child_results))
            return StepResult(next="recorded")

        stage = ParallelStage(
            name="_proof_stage",
            steps=(),
            join=recording_join,
            edges=(),
        )
        hooks = NullExecutorHooks()
        ctx = StepContext(artifact_root="/tmp/test", state=None)
        expected = [
            StepResult(next="x", outputs={"k": "v1"}),
            StepResult(next="y", outputs={"k": "v2"}),
        ]
        hooks.join_parallel_results(stage, ctx, expected)
        assert len(received) == 1
        assert received[0] == expected


class TestJoinDelegationContextForwardingGreen:
    """Green fixtures for ``check_join_delegation_context_forwarding``."""

    def test_null_hooks_forwards_context(self) -> None:
        result = check_join_delegation_context_forwarding()
        assert result.check_id == "join-delegation-context-forwarding"
        assert result.passed is True

    def test_explicit_null_hooks_forwards_context(self) -> None:
        hooks = NullExecutorHooks()
        result = check_join_delegation_context_forwarding(hooks)
        assert result.passed is True

    def test_context_forwarded_correctly_direct_proof(self) -> None:
        """Direct proof: StepContext is forwarded to stage.join correctly."""
        received_ctx: list[StepContext] = []

        def ctx_recording_join(
            child_results: list[StepResult],
            ctx: StepContext,
        ) -> StepResult:
            received_ctx.append(ctx)
            return StepResult(next="ctx_recorded")

        stage = ParallelStage(
            name="_ctx_proof_stage",
            steps=(),
            join=ctx_recording_join,
            edges=(),
        )
        hooks = NullExecutorHooks()
        ctx = StepContext(
            artifact_root="/tmp/ctx_proof",
            state={"key": "value"},
            mode="proof_mode",
        )
        hooks.join_parallel_results(stage, ctx, [])
        assert len(received_ctx) == 1
        assert received_ctx[0].artifact_root == "/tmp/ctx_proof"
        assert received_ctx[0].state == {"key": "value"}
        assert received_ctx[0].mode == "proof_mode"


# ---------------------------------------------------------------------------
# Seeded red fixtures — non-delegating custom hook
# ---------------------------------------------------------------------------

class _NonDelegatingHooks:
    """A custom ``ExecutorHooks`` that does NOT delegate ``join_parallel_results``
    to ``stage.join``.  Used exclusively in tests to verify non-delegation detection.
    """

    def join_parallel_results(
        self,
        stage: ParallelStage,
        ctx: StepContext,
        child_results: list[StepResult],
    ) -> StepResult:
        """Override: return a fixed result without calling stage.join."""
        return StepResult(
            next="non_delegated",
            outputs={"_delegated": False},
        )


class TestJoinDelegationNonDelegatingRed:
    """Seeded red fixtures for ``check_join_delegation_non_delegating``.

    These tests use a deliberately non-delegating custom hook to prove the
    conformance check correctly detects when a hook overrides delegation.
    """

    def test_non_delegating_hook_detected(self) -> None:
        hooks = _NonDelegatingHooks()
        result = check_join_delegation_non_delegating(hooks)
        assert result.check_id == "join-delegation-non-delegating"
        assert result.passed is True  # the check confirms non-delegation is correctly detected

    def test_non_delegating_hook_returns_different_result(self) -> None:
        """Direct proof: non-delegating hook returns a result that differs from sentinel."""
        hooks = _NonDelegatingHooks()
        stage = _make_sentinel_stage()
        ctx = StepContext(artifact_root="/tmp/test", state=None)
        joined = hooks.join_parallel_results(stage, ctx, [])
        assert isinstance(joined, StepResult)
        assert joined.next == "non_delegated"
        assert joined.outputs == {"_delegated": False}

    def test_non_delegating_hook_does_not_call_stage_join(self) -> None:
        """Verify the non-delegating hook never touches stage.join."""
        call_count = [0]

        def counting_join(
            child_results: list[StepResult],
            ctx: StepContext,
        ) -> StepResult:
            call_count[0] += 1
            return StepResult(next="called")

        stage = ParallelStage(
            name="_counting_stage",
            steps=(),
            join=counting_join,
            edges=(),
        )
        hooks = _NonDelegatingHooks()
        ctx = StepContext(artifact_root="/tmp/test", state=None)
        joined = hooks.join_parallel_results(stage, ctx, [])
        # The non-delegating hook should NOT have called stage.join
        assert call_count[0] == 0
        assert joined.next == "non_delegated"

    def test_check_join_delegation_fails_with_non_delegating_hook(self) -> None:
        """When hooks override join_parallel_results, check_join_delegation fails
        because the result is not the sentinel (delegation didn't happen)."""
        hooks = _NonDelegatingHooks()
        result = check_join_delegation(hooks)
        assert result.passed is False
        assert "did not delegate" in result.message

    def test_check_child_results_fails_with_non_delegating_hook(self) -> None:
        """Non-delegating hook does not call stage.join → no child results forwarded."""
        hooks = _NonDelegatingHooks()
        result = check_join_delegation_with_child_results(hooks)
        assert result.passed is False
        assert "never called" in result.message

    def test_check_context_forwarding_fails_with_non_delegating_hook(self) -> None:
        """Non-delegating hook does not call stage.join → context not forwarded."""
        hooks = _NonDelegatingHooks()
        result = check_join_delegation_context_forwarding(hooks)
        assert result.passed is False
        assert "never called" in result.message


# ---------------------------------------------------------------------------
# run_join_conformance_suite — green
# ---------------------------------------------------------------------------

class TestRunJoinConformanceSuite:
    """Green fixtures for ``run_join_conformance_suite``."""

    def test_default_hooks_suite_all_pass(self) -> None:
        results = run_join_conformance_suite()
        assert len(results) == 3  # delegation, child-results, context-forwarding
        for r in results:
            assert r.passed, f"{r.check_id}: {r.message}"

    def test_explicit_null_hooks_suite_all_pass(self) -> None:
        hooks = NullExecutorHooks()
        results = run_join_conformance_suite(hooks)
        assert len(results) == 3
        for r in results:
            assert r.passed, f"{r.check_id}: {r.message}"

    def test_returns_list_of_conformance_check_results(self) -> None:
        results = run_join_conformance_suite()
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, ConformanceCheckResult)

    def test_suite_includes_delegation_check(self) -> None:
        results = run_join_conformance_suite()
        check_ids = {r.check_id for r in results}
        assert "join-delegation" in check_ids

    def test_suite_includes_child_results_check(self) -> None:
        results = run_join_conformance_suite()
        check_ids = {r.check_id for r in results}
        assert "join-delegation-child-results" in check_ids

    def test_suite_includes_context_forwarding_check(self) -> None:
        results = run_join_conformance_suite()
        check_ids = {r.check_id for r in results}
        assert "join-delegation-context-forwarding" in check_ids

    def test_non_delegating_hook_not_in_default_suite(self) -> None:
        """The default suite does NOT include the non-delegating check
        (that requires a caller-supplied hooks)."""
        results = run_join_conformance_suite()
        check_ids = {r.check_id for r in results}
        assert "join-delegation-non-delegating" not in check_ids


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestJoinDelegationEdgeCases:
    """Edge cases for join delegation."""

    def test_empty_child_results_delegated(self) -> None:
        hooks = NullExecutorHooks()
        stage = _make_sentinel_stage()
        ctx = StepContext(artifact_root="/tmp/test", state=None)
        joined = hooks.join_parallel_results(stage, ctx, [])
        assert isinstance(joined, StepResult)

    def test_single_child_result_delegated(self) -> None:
        hooks = NullExecutorHooks()
        stage = _make_sentinel_stage()
        ctx = StepContext(artifact_root="/tmp/test", state=None)
        joined = hooks.join_parallel_results(
            stage, ctx, [StepResult(next="only_child")]
        )
        assert isinstance(joined, StepResult)

    def test_join_preserves_stepresult_type(self) -> None:
        """The join result is always a StepResult."""
        hooks = NullExecutorHooks()
        stage = _make_sentinel_stage()
        ctx = StepContext(artifact_root="/tmp/test", state=None)
        joined = hooks.join_parallel_results(
            stage, ctx, [StepResult(next="x"), StepResult(next="y")]
        )
        assert isinstance(joined, StepResult)

    def test_join_returned_by_sentinel_has_sentinel_outputs(self) -> None:
        """The sentinel join returns a StepResult with distinctive outputs."""
        hooks = NullExecutorHooks()
        stage = _make_sentinel_stage()
        ctx = StepContext(artifact_root="/tmp/test", state=None)
        joined = hooks.join_parallel_results(stage, ctx, [])
        # The sentinel join returns {"_sentinel": True}
        assert joined.outputs == {"_sentinel": True}
        assert joined.next == "_sentinel_next"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sentinel_stage() -> ParallelStage:
    """Build a minimal ParallelStage with a sentinel join function."""
    def sentinel_join(
        child_results: list[StepResult],
        ctx: StepContext,
    ) -> StepResult:
        return StepResult(
            outputs={"_sentinel": True},
            next="_sentinel_next",
        )

    return ParallelStage(
        name="_test_sentinel_stage",
        steps=(),
        join=sentinel_join,
        edges=(),
    )
