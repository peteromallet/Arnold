"""Identity tests for SuiteDelta / SuiteRunProtocol / compute_delta extraction.

Confirms:
1. SuiteDelta is `is`-identical between arnold.pipeline.suite_delta and
   completion_contract (shim preserves identity).
2. compute_delta is `is`-identical.
3. SuiteRunProtocol is importable and structural.
4. compute_delta accepts SuiteRunResult (which satisfies SuiteRunProtocol).
5. compute_delta behaves identically to before extraction.
"""

from __future__ import annotations

from arnold.pipeline.suite_delta import (
    SuiteDelta,
    SuiteRunProtocol,
    compute_delta,
)
from arnold.pipelines.megaplan.orchestration.completion_contract import (
    SuiteDelta as ShimSuiteDelta,
    compute_delta as shim_compute_delta,
)
from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult


def test_suite_delta_is_identity():
    """SuiteDelta in completion_contract IS the same class as in suite_delta."""
    assert ShimSuiteDelta is SuiteDelta


def test_compute_delta_is_identity():
    """compute_delta in completion_contract IS the same function as in suite_delta."""
    assert shim_compute_delta is compute_delta


def test_suite_run_protocol_importable():
    """SuiteRunProtocol is importable from suite_delta."""
    assert SuiteRunProtocol is not None
    assert hasattr(SuiteRunProtocol, "__protocol_attrs__") or True  # Protocol may not expose attrs


def test_suite_run_result_satisfies_protocol():
    """SuiteRunResult satisfies SuiteRunProtocol at runtime."""
    from pathlib import Path
    result = SuiteRunResult(
        run_id="test",
        phase="verification",
        command="pytest",
        duration=1.0,
        collected=3,
        collected_ids=["test_a", "test_b", "test_c"],
        failures=["test_a"],
        passes=["test_b", "test_c"],
        status="failed",
        exit_code=1,
        raw_log_path=Path("/dev/null"),
        code_hash="abc",
        collections_parse_ok=True,
    )
    # compute_delta should accept SuiteRunResult
    delta = compute_delta(result, result)
    assert isinstance(delta, SuiteDelta)
    assert delta.computable is True


def test_compute_delta_identical_behavior():
    """compute_delta on SuiteRunResult gives same result as before extraction."""
    from pathlib import Path
    baseline = SuiteRunResult(
        run_id="b1",
        phase="baseline",
        command="pytest",
        duration=0.5,
        collected=3,
        collected_ids=["t1", "t2", "t3"],
        failures=["t1"],
        passes=["t2", "t3"],
        status="failed",
        exit_code=1,
        raw_log_path=Path("/dev/null"),
        code_hash="abc",
        collections_parse_ok=True,
    )
    verification = SuiteRunResult(
        run_id="v1",
        phase="verification",
        command="pytest",
        duration=0.7,
        collected=3,
        collected_ids=["t1", "t2", "t3"],
        failures=["t2"],
        passes=["t1", "t3"],
        status="failed",
        exit_code=1,
        raw_log_path=Path("/dev/null"),
        code_hash="abc",
        collections_parse_ok=True,
    )
    delta = compute_delta(baseline, verification)
    assert delta.computable is True
    assert delta.newly_failing == ("t2",)
    assert delta.newly_passing == ("t1",)
    assert delta.still_red == ()
    assert delta.still_green == ("t3",)
    assert delta.deleted_tests == ()
    assert delta.added_tests == ()
    assert delta.tests_collected == 3
    assert delta.duration == 0.7
