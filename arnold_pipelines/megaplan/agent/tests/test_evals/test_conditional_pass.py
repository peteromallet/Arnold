"""Tests for conditional pass scoring logic.

The conditional pass logic lives in run_all_evals() but is tested here
via a helper that mirrors the exact branching at evals/run_evals.py:725-738.
"""


def _score(build_success: bool, eval_success: bool, passed: int | None, total: int | None) -> tuple[str, bool]:
    """Mirror the conditional pass logic from run_all_evals."""
    final_status = "passed"
    conditional = False
    all_assertions_passed = (
        passed is not None
        and total is not None
        and total > 0
        and passed == total
    )
    if not build_success and all_assertions_passed:
        final_status = "passed"
        conditional = True
    elif not build_success or not eval_success:
        final_status = "failed"
    return final_status, conditional


def test_build_fail_all_assertions_pass():
    status, cond = _score(build_success=False, eval_success=True, passed=5, total=5)
    assert status == "passed"
    assert cond is True


def test_build_fail_some_assertions_fail():
    status, cond = _score(build_success=False, eval_success=False, passed=3, total=5)
    assert status == "failed"
    assert cond is False


def test_build_fail_zero_assertions():
    status, cond = _score(build_success=False, eval_success=False, passed=0, total=0)
    assert status == "failed"
    assert cond is False


def test_build_fail_no_reporter():
    status, cond = _score(build_success=False, eval_success=False, passed=None, total=None)
    assert status == "failed"
    assert cond is False


def test_build_pass_all_assertions_pass():
    status, cond = _score(build_success=True, eval_success=True, passed=5, total=5)
    assert status == "passed"
    assert cond is False


def test_build_pass_some_assertions_fail():
    status, cond = _score(build_success=True, eval_success=False, passed=3, total=5)
    assert status == "failed"
    assert cond is False
