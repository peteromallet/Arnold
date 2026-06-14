"""Join delegation conformance checks.

Verifies that ``PipelineHooks.join_parallel_results`` delegates to ``stage.join``
using sentinel join functions and child results, without depending on executor
internals.

The check exercises the public hook behaviour and parallel stage join delegation
while distinguishing default delegation from deliberately non-delegating hooks.

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

from typing import Any, Sequence

from arnold.conformance import ConformanceCheckResult
from arnold.pipeline.hooks import ExecutorHooks, NullExecutorHooks
from arnold.pipeline.types import (
    ParallelStage,
    StepContext,
    StepResult,
)


# ---------------------------------------------------------------------------
# Sentinel values for join delegation detection
# ---------------------------------------------------------------------------

_SENTINEL_RESULT = StepResult(
    outputs={"_sentinel": True},
    next="_sentinel_next",
)


def _sentinel_join(
    child_results: list[StepResult],
    ctx: StepContext,
) -> StepResult:
    """A sentinel join function that returns a distinctive result.

    If ``join_parallel_results`` delegates to ``stage.join``, the returned
    ``StepResult`` will be this sentinel.  If the hook overrides delegation,
    a different result is returned.
    """
    return _SENTINEL_RESULT


def _make_sentinel_parallel_stage() -> ParallelStage:
    """Build a minimal ``ParallelStage`` with a sentinel join function."""
    return ParallelStage(
        name="_conformance_join_stage",
        steps=(),
        join=_sentinel_join,
        edges=(),
    )


# ---------------------------------------------------------------------------
# Join delegation checks
# ---------------------------------------------------------------------------


def check_join_delegation(
    hooks: ExecutorHooks | None = None,
) -> ConformanceCheckResult:
    """Verify that ``join_parallel_results`` delegates to ``stage.join``.

    Constructs a ``ParallelStage`` with a sentinel join function, passes
    empty child results through ``hooks.join_parallel_results``, and checks
    that the returned ``StepResult`` matches the sentinel — proving delegation
    occurred.

    When *hooks* is ``None`` (or a ``NullExecutorHooks``), the default
    behaviour is delegation to ``stage.join``, which returns the sentinel.

    Parameters
    ----------
    hooks:
        The hook implementation to test.  When *None*, ``NullExecutorHooks``
        is used (which delegates by default).

    Returns
    -------
    ConformanceCheckResult
        ``passed=True`` when the hook delegates to ``stage.join``.
    """
    if hooks is None:
        hooks = NullExecutorHooks()

    stage = _make_sentinel_parallel_stage()
    ctx = StepContext(artifact_root="/tmp/conformance", state=None)
    child_results: list[StepResult] = [
        StepResult(next="child_1"),
        StepResult(next="child_2"),
    ]

    try:
        joined = hooks.join_parallel_results(stage, ctx, child_results)
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="join-delegation",
            passed=False,
            message=(
                f"join_parallel_results raised {type(exc).__name__}: {exc}"
            ),
            details={"error": str(exc)},
        )

    if not isinstance(joined, StepResult):
        return ConformanceCheckResult(
            check_id="join-delegation",
            passed=False,
            message=(
                f"join_parallel_results returned {type(joined).__name__}, "
                f"expected StepResult"
            ),
        )

    # The sentinel join returns _SENTINEL_RESULT. If the hook delegates,
    # we get the sentinel back.
    if joined == _SENTINEL_RESULT:
        return ConformanceCheckResult(check_id="join-delegation", passed=True)

    return ConformanceCheckResult(
        check_id="join-delegation",
        passed=False,
        message=(
            "join_parallel_results did not delegate to stage.join: "
            f"got {joined!r}, expected sentinel {_SENTINEL_RESULT!r}"
        ),
        details={
            "returned": repr(joined),
            "expected_sentinel": repr(_SENTINEL_RESULT),
        },
    )


def check_join_delegation_with_child_results(
    hooks: ExecutorHooks | None = None,
) -> ConformanceCheckResult:
    """Verify that ``join_parallel_results`` passes child results to ``stage.join``.

    Uses a custom sentinel join function that records whether it received the
    expected child results.  This check is stronger than
    :func:`check_join_delegation` because it proves the child results are
    forwarded correctly.
    """
    if hooks is None:
        hooks = NullExecutorHooks()

    expected_child_results: list[StepResult] = [
        StepResult(next="child_a", outputs={"idx": 0}),
        StepResult(next="child_b", outputs={"idx": 1}),
    ]

    received: list[list[StepResult]] = []

    def recording_join(
        child_results: list[StepResult],
        ctx: StepContext,
    ) -> StepResult:
        received.append(list(child_results))
        return StepResult(next="recorded")

    stage = ParallelStage(
        name="_conformance_recording_join_stage",
        steps=(),
        join=recording_join,
        edges=(),
    )
    ctx = StepContext(artifact_root="/tmp/conformance", state=None)

    try:
        joined = hooks.join_parallel_results(stage, ctx, expected_child_results)
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="join-delegation-child-results",
            passed=False,
            message=(
                f"join_parallel_results raised {type(exc).__name__}: {exc}"
            ),
        )

    if not received:
        return ConformanceCheckResult(
            check_id="join-delegation-child-results",
            passed=False,
            message="stage.join was never called by join_parallel_results",
        )

    forwarded = received[0]
    if forwarded != expected_child_results:
        return ConformanceCheckResult(
            check_id="join-delegation-child-results",
            passed=False,
            message=(
                f"stage.join received different child results: "
                f"got {forwarded!r}, expected {expected_child_results!r}"
            ),
            details={
                "received": forwarded,
                "expected": expected_child_results,
            },
        )

    return ConformanceCheckResult(
        check_id="join-delegation-child-results", passed=True
    )


def check_join_delegation_non_delegating(
    hooks: ExecutorHooks,
) -> ConformanceCheckResult:
    """Verify that a deliberately non-delegating hook does NOT delegate to
    ``stage.join``.

    This check confirms the distinction between default delegation and
    intentionally non-delegating behaviour.  A hook that returns a result
    different from the sentinel is correctly identified as non-delegating.

    Parameters
    ----------
    hooks:
        A hook implementation that is expected NOT to delegate to
        ``stage.join``.
    """
    stage = _make_sentinel_parallel_stage()
    ctx = StepContext(artifact_root="/tmp/conformance", state=None)
    child_results: list[StepResult] = []

    try:
        joined = hooks.join_parallel_results(stage, ctx, child_results)
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="join-delegation-non-delegating",
            passed=False,
            message=(
                f"join_parallel_results raised {type(exc).__name__}: {exc}"
            ),
        )

    if joined == _SENTINEL_RESULT:
        return ConformanceCheckResult(
            check_id="join-delegation-non-delegating",
            passed=False,
            message=(
                "Non-delegating hook returned sentinel — appears to "
                "have delegated to stage.join instead of overriding"
            ),
        )

    return ConformanceCheckResult(
        check_id="join-delegation-non-delegating", passed=True
    )


def check_join_delegation_context_forwarding(
    hooks: ExecutorHooks | None = None,
) -> ConformanceCheckResult:
    """Verify that ``join_parallel_results`` forwards the ``StepContext`` to
    ``stage.join``.

    Uses a sentinel join function that records the ``StepContext`` it
    receives and checks it matches what was passed to the hook.
    """
    if hooks is None:
        hooks = NullExecutorHooks()

    received_ctx: list[StepContext] = []

    def context_recording_join(
        child_results: list[StepResult],
        ctx: StepContext,
    ) -> StepResult:
        received_ctx.append(ctx)
        return StepResult(next="ctx_recorded")

    stage = ParallelStage(
        name="_conformance_ctx_forward_stage",
        steps=(),
        join=context_recording_join,
        edges=(),
    )
    ctx = StepContext(
        artifact_root="/tmp/conformance/ctx_test",
        state={"key": "value"},
        mode="test_mode",
    )

    try:
        hooks.join_parallel_results(stage, ctx, [])
    except Exception as exc:
        return ConformanceCheckResult(
            check_id="join-delegation-context-forwarding",
            passed=False,
            message=(
                f"join_parallel_results raised {type(exc).__name__}: {exc}"
            ),
        )

    if not received_ctx:
        return ConformanceCheckResult(
            check_id="join-delegation-context-forwarding",
            passed=False,
            message="stage.join was never called",
        )

    forwarded_ctx = received_ctx[0]
    if forwarded_ctx != ctx:
        return ConformanceCheckResult(
            check_id="join-delegation-context-forwarding",
            passed=False,
            message=(
                f"stage.join received different context: "
                f"got {forwarded_ctx!r}, expected {ctx!r}"
            ),
            details={
                "received": forwarded_ctx,
                "expected": ctx,
            },
        )

    return ConformanceCheckResult(
        check_id="join-delegation-context-forwarding", passed=True
    )


def run_join_conformance_suite(
    hooks: ExecutorHooks | None = None,
) -> list[ConformanceCheckResult]:
    """Run all join delegation conformance checks against *hooks*.

    When *hooks* is ``None``, ``NullExecutorHooks`` is used.

    Returns an ordered list of ``ConformanceCheckResult`` values.
    """
    if hooks is None:
        hooks = NullExecutorHooks()

    return [
        check_join_delegation(hooks),
        check_join_delegation_with_child_results(hooks),
        check_join_delegation_context_forwarding(hooks),
    ]


__all__ = [
    "check_join_delegation",
    "check_join_delegation_with_child_results",
    "check_join_delegation_non_delegating",
    "check_join_delegation_context_forwarding",
    "run_join_conformance_suite",
]
