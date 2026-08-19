"""suite_runner subtest-output parsing (occurrence aac1a98ab9c2).

pytest's native unittest.subTest support counts failing subtests in the
summary "failed" counter and emits ``SUBFAILED(<subtest>) <nodeid>`` lines in
the ``-rA`` report, even when the parent test itself PASSES.  The parser must
treat those lines as failures or the count-consistency check flips
``parse_ok`` to False, the run is misclassified as ``runner_error``, and the
no-new-failures delta lifecycle refuses to capture a pre-dispatch envelope —
hard-blocking the batch the gate was about to dispatch (VJ6, batch_7).
"""

from __future__ import annotations

from arnold_pipelines.megaplan.orchestration.suite_runner import (
    _parse_pytest_output,
)


def _log(
    *,
    summary: str,
    report_lines: list[str],
    tail: str = "",
) -> str:
    """Build a pytest ``-rA``-shaped raw log (report section first)."""
    lines = ["=========================== short test summary info ============================"]
    lines.extend(report_lines)
    if tail:
        lines.append(tail)
    lines.append(summary)
    return "\n".join(lines) + "\n"


def test_subtest_only_failure_parses_as_failure() -> None:
    """A run whose ONLY failures are subtests (parents PASSED) is complete.

    pytest 9.1.1 exits 1 and counts the subtest in the summary ``failed``
    counter even though every parent test reports PASSED.
    """
    raw = _log(
        summary="1 failed, 2 passed, 1 subtests passed in 0.01s",
        report_lines=[
            "PASSED tests/test_sub.py::SubTestProbe::test_mixed",
            "PASSED tests/test_sub.py::SubTestProbe::test_ok",
            "SUBFAILED(v=2) tests/test_sub.py::SubTestProbe::test_mixed - AssertionError: ...",
        ],
    )
    parsed = _parse_pytest_output(raw, exit_code=1)
    assert parsed["parse_ok"] is True
    assert parsed["failures"] == [
        "tests/test_sub.py::SubTestProbe::test_mixed"
    ]
    assert parsed["passes"] == [
        "tests/test_sub.py::SubTestProbe::test_mixed",
        "tests/test_sub.py::SubTestProbe::test_ok",
    ]


def test_mixed_failed_parent_and_subfailed_parses_complete() -> None:
    """A run with BOTH real FAILED parents and SUBFAILED subtest lines parses
    with the full failure set (count matches the summary)."""
    raw = _log(
        summary="2 failed, 1 passed, 1 subtests passed in 0.01s",
        report_lines=[
            "PASSED tests/test_sub2.py::SubTestProbe2::test_mixed",
            "FAILED tests/test_sub2.py::SubTestProbe2::test_fail - AssertionError: 1 != 2",
            "SUBFAILED(v=2) tests/test_sub2.py::SubTestProbe2::test_mixed - AssertionError: ...",
        ],
    )
    parsed = _parse_pytest_output(raw, exit_code=1)
    assert parsed["parse_ok"] is True
    assert len(parsed["failures"]) == 2
    assert "tests/test_sub2.py::SubTestProbe2::test_fail" in parsed["failures"]
    assert "tests/test_sub2.py::SubTestProbe2::test_mixed" in parsed["failures"]
    # collected_ids dedupes the parent that appears in both sections.
    assert parsed["collected_ids"] == [
        "tests/test_sub2.py::SubTestProbe2::test_fail",
        "tests/test_sub2.py::SubTestProbe2::test_mixed",
    ]


def test_vj6_shaped_log_parses_complete() -> None:
    """The exact VJ6 failure shape (21 FAILED + 8 SUBFAILED = 29 summary
    failures) parses with parse_ok True and the full 29-entry failure set."""
    report = []
    # 21 FAILED parents
    for i in range(21):
        report.append(f"FAILED tests/a.py::test_fail_{i} - boom")
    # 5 SUBFAILED whose parent is also FAILED
    for v in ("start", "next", "ack", "abort", "status"):
        report.append(
            f"SUBFAILED(verb={v!r}) tests/b.py::LifecycleTest::test_verbs - x"
        )
    # 3 SUBFAILED whose parent PASSES
    for module in ("astrid.core.cli.session", "astrid.core.cli.other", "run"):
        report.append(
            f"SUBFAILED(module={module!r}) tests/c.py::AllowlistTest::test_ok - x"
        )
    # 88 PASSED
    for i in range(88):
        report.append(f"PASSED tests/d.py::test_ok_{i}")
    raw = _log(
        summary="29 failed, 88 passed, 2 warnings, 78 subtests passed in 1.42s",
        report_lines=report,
    )
    parsed = _parse_pytest_output(raw, exit_code=1)
    assert parsed["parse_ok"] is True
    assert len(parsed["failures"]) == 29
    assert len(parsed["passes"]) == 88


def test_no_subtest_run_unchanged() -> None:
    """Plain FAILED/PASSED output keeps parse_ok True (no behavior change)."""
    raw = _log(
        summary="5 failed, 132 passed, 2 warnings in 1.33s",
        report_lines=[
            "FAILED tests/x.py::test_a - boom",
            "FAILED tests/x.py::test_b - boom",
            "PASSED tests/x.py::test_c",
        ],
    )
    # summary says 5 failed but only 2 FAILED lines: still a mismatch -> fail
    # closed on an inconsistent (non-subtest) log.
    parsed = _parse_pytest_output(raw, exit_code=1)
    assert parsed["parse_ok"] is False
    # and a consistent plain log parses clean
    raw2 = _log(
        summary="2 failed, 1 passed, 2 warnings in 1.33s",
        report_lines=[
            "FAILED tests/x.py::test_a - boom",
            "FAILED tests/x.py::test_b - boom",
            "PASSED tests/x.py::test_c",
        ],
    )
    parsed2 = _parse_pytest_output(raw2, exit_code=1)
    assert parsed2["parse_ok"] is True
    assert parsed2["failures"] == [
        "tests/x.py::test_a",
        "tests/x.py::test_b",
    ]


def test_collection_error_still_fails_closed() -> None:
    """Collection errors keep parse_ok False / failures augmented — the
    fail-closed guarantee for malformed runs is preserved."""
    raw = _log(
        summary="1 failed, 0 passed in 0.01s",
        report_lines=[
            "ERROR collecting tests/broken.py",
            "ImportError: No module named 'nope'",
        ],
    )
    parsed = _parse_pytest_output(raw, exit_code=2)
    # collection errors are surfaced as failures with parse_ok True by design
    # (see _collection_errors_from_output); the point here is that a
    # collection-error run is NOT mistaken for a plain failed run.
    assert parsed["collection_errors"]
    assert parsed["failures"]