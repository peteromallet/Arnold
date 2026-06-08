"""Tests for SuiteDelta computation and flake retry in GreenSuiteProvider.

Covers:
  (i)   A deleted test does NOT appear in newly_passing.
  (ii)  Parametrize rename matches by nodeid — no spurious deleted+added.
  (iii) Flake retry stabilizes a one-off flip.
  (iv)  Flake retry skipped for >1000 flips.
  (v)   collections_parse_ok=False yields delta.computable=False.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from unittest import mock

import pytest

from arnold.pipelines.megaplan.orchestration.completion_contract import (
    ArtifactRef,
    CompletionContext,
    CompletionSubject,
    EvidenceRef,
    EvidenceStatus,
    GreenSuiteProvider,
    SuiteDelta,
    TrustClass,
    compute_delta,
)
from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _subject(name: str = "plan-x") -> CompletionSubject:
    return CompletionSubject(kind="plan", name=name, to_state="done", plan_name=name)


def _make_result(**overrides: object) -> SuiteRunResult:
    """Build a SuiteRunResult with sensible defaults, overridable by kwarg."""
    defaults: dict[str, object] = {
        "run_id": "fake-run-id",
        "phase": "verification",
        "command": "pytest --tb=no -q --no-header -rA",
        "duration": 0.1,
        "collected": 3,
        "collected_ids": [
            "tests/test_a.py::test_x",
            "tests/test_b.py::test_y",
            "tests/test_c.py::test_z",
        ],
        "failures": [],
        "passes": [
            "tests/test_a.py::test_x",
            "tests/test_b.py::test_y",
            "tests/test_c.py::test_z",
        ],
        "status": "passed",
        "exit_code": 0,
        "raw_log_path": Path("/dev/null"),
        "code_hash": "abc123",
        "collections_parse_ok": True,
    }
    defaults.update(overrides)
    return SuiteRunResult(**defaults)  # type: ignore[arg-type]


def _ctx(
    tmp_path: Path,
    *,
    plan_dir: Path | None = None,
    project_dir: Path | None = None,
    timeout: int = 30,
) -> CompletionContext:
    pd = plan_dir or (tmp_path / "plan")
    pd.mkdir(parents=True, exist_ok=True)
    proj = project_dir or (tmp_path / "repo")
    proj.mkdir(parents=True, exist_ok=True)
    return CompletionContext(
        plan_dir=pd,
        project_dir=proj,
        state={
            "config": {
                "test_baseline_timeout": timeout,
                "project_dir": str(proj),
            }
        },
        subject=_subject(),
    )


def _seed_baseline(
    plan_dir: Path,
    baseline: SuiteRunResult,
) -> None:
    """Write a baseline record into suite_runs.ndjson."""
    from arnold.pipelines.megaplan.orchestration.suite_runner import append_suite_run as real_append

    real_append(plan_dir, baseline)


def _mock_collect_deps(
    verification: SuiteRunResult,
    *,
    baseline: SuiteRunResult | None = None,
    code_hash: str = "abc123",
) -> list[mock._patch]:
    """Return a list of mock patches for GreenSuiteProvider.collect dependencies.

    Mocks run_suite, append_suite_run, _compute_code_hash, freshness_skip,
    and — when *baseline* is provided — latest_run_for_phase so
    _baseline_from_log returns it.
    """
    patches: list[mock._patch] = []

    # Always mock run_suite to return the verification result.
    patches.append(
        mock.patch(
            "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
            return_value=verification,
        )
    )
    # Suppress real ndjson writes.
    patches.append(
        mock.patch(
            "arnold.pipelines.megaplan.orchestration.suite_runner.append_suite_run",
        )
    )
    # Stable code_hash.
    patches.append(
        mock.patch(
            "arnold.pipelines.megaplan.orchestration.suite_runner._compute_code_hash",
            return_value=code_hash,
        )
    )
    # Never short-circuit freshness.
    patches.append(
        mock.patch(
            "arnold.pipelines.megaplan.orchestration.suite_runner.freshness_skip",
            return_value=None,
        )
    )

    # If a baseline is provided, seed it and mock latest_run_for_phase.
    if baseline is not None:
        patches.append(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.completion_contract.GreenSuiteProvider._baseline_from_log",
                return_value=baseline,
            )
        )

    return patches


# ---------------------------------------------------------------------------
# (i) Deleted test does NOT appear in newly_passing
# ---------------------------------------------------------------------------


def test_deleted_test_not_in_newly_passing(tmp_path: Path) -> None:
    """A test that existed in baseline but was deleted before verification
    must NOT appear in newly_passing."""
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        failures=["tests/test_b.py::test_y"],
        passes=["tests/test_a.py::test_x"],
    )
    # Verification: test_b is deleted (not in collected_ids), test_x still passes.
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["tests/test_a.py::test_x"],
        failures=[],
        passes=["tests/test_a.py::test_x"],
        collected=1,
    )

    delta = compute_delta(baseline, verification)

    # test_b was failing in baseline but is NOT in verification_collected → deleted
    assert "tests/test_b.py::test_y" in delta.deleted_tests
    # test_b must NOT appear in newly_passing (it was deleted, not fixed)
    assert "tests/test_b.py::test_y" not in delta.newly_passing


def test_deleted_and_added_dont_overlap_newly_passing(tmp_path: Path) -> None:
    """A renamed test yields deleted+added; the old name must NOT appear
    in newly_passing (it was deleted, not fixed).  The new name, if it
    fails, correctly appears in newly_failing AND added_tests."""
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["tests/test_a.py::test_old_name"],
        failures=["tests/test_a.py::test_old_name"],
        passes=[],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["tests/test_a.py::test_new_name"],
        failures=["tests/test_a.py::test_new_name"],
        passes=[],
    )

    delta = compute_delta(baseline, verification)

    assert "tests/test_a.py::test_old_name" in delta.deleted_tests
    assert "tests/test_a.py::test_new_name" in delta.added_tests
    # The deleted test must NOT appear in newly_passing.
    assert "tests/test_a.py::test_old_name" not in delta.newly_passing
    # The new test correctly appears in newly_failing (it's an added failure).
    assert "tests/test_a.py::test_new_name" in delta.newly_failing


# ---------------------------------------------------------------------------
# (ii) Parametrize rename matches by nodeid — no spurious deleted+added
# ---------------------------------------------------------------------------


def test_parametrize_rename_no_spurious_deleted_added(tmp_path: Path) -> None:
    """Renaming a parametrize marker (e.g. [a-1] → [a-2]) yields the expected
    deleted + added, not a false newly_passing."""
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["tests/test_foo.py::test_bar[a-1]"],
        failures=[],
        passes=["tests/test_foo.py::test_bar[a-1]"],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["tests/test_foo.py::test_bar[a-2]"],
        failures=[],
        passes=["tests/test_foo.py::test_bar[a-2]"],
    )

    delta = compute_delta(baseline, verification)

    # Old parametrize id is deleted.
    assert "tests/test_foo.py::test_bar[a-1]" in delta.deleted_tests
    # New parametrize id is added.
    assert "tests/test_foo.py::test_bar[a-2]" in delta.added_tests
    # No spurious newly_passing / newly_failing.
    assert delta.newly_passing == ()
    assert delta.newly_failing == ()
    assert delta.still_green == ()  # different nodeids


def test_parametrize_still_red_recognized(tmp_path: Path) -> None:
    """A parametrized test that fails in both baseline and verification
    is still_red."""
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=[
            "tests/test_foo.py::test_bar[a-1]",
            "tests/test_foo.py::test_bar[a-2]",
        ],
        failures=["tests/test_foo.py::test_bar[a-1]"],
        passes=["tests/test_foo.py::test_bar[a-2]"],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=[
            "tests/test_foo.py::test_bar[a-1]",
            "tests/test_foo.py::test_bar[a-2]",
        ],
        failures=["tests/test_foo.py::test_bar[a-1]"],
        passes=["tests/test_foo.py::test_bar[a-2]"],
    )

    delta = compute_delta(baseline, verification)

    assert delta.still_red == ("tests/test_foo.py::test_bar[a-1]",)
    assert delta.still_green == ("tests/test_foo.py::test_bar[a-2]",)
    assert delta.newly_failing == ()
    assert delta.newly_passing == ()


# ---------------------------------------------------------------------------
# (iii) Flake retry stabilizes a one-off flip
# ---------------------------------------------------------------------------


def test_flake_retry_stabilizes_one_off_flip(tmp_path: Path) -> None:
    """A test that flips from pass→fail in verification but passes again
    in the retry is classified as a flake, NOT newly_failing."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        failures=[],
        passes=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
    )
    # Verification: test_x flipped to failure.
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        failures=["tests/test_a.py::test_x"],
        passes=["tests/test_b.py::test_y"],
    )
    # Retry: test_x passes again (flake).
    retry = _make_result(
        run_id="fr-1",
        phase="flake_retry",
        collected_ids=["tests/test_a.py::test_x"],
        failures=[],
        passes=["tests/test_a.py::test_x"],
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        # Override run_suite for the flake retry call.
        stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
                side_effect=[verification, retry],
            )
        )
        ref = provider.collect(ctx)

    delta_dict = ref.details.get("delta")
    assert delta_dict is not None
    assert delta_dict["computable"] is True
    # test_x was unstable → classified as flake
    assert "tests/test_a.py::test_x" in delta_dict["flakes"]
    assert delta_dict["newly_failing"] == []
    assert ref.details["flake_retried"] is True


def test_flake_retry_confirms_stable_newly_failing(tmp_path: Path) -> None:
    """A test that flips from pass→fail in verification AND stays failed
    in the retry is classified as newly_failing."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        failures=[],
        passes=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        failures=["tests/test_a.py::test_x"],
        passes=["tests/test_b.py::test_y"],
    )
    # Retry confirms the failure is stable.
    retry = _make_result(
        run_id="fr-1",
        phase="flake_retry",
        collected_ids=["tests/test_a.py::test_x"],
        failures=["tests/test_a.py::test_x"],
        passes=[],
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
                side_effect=[verification, retry],
            )
        )
        ref = provider.collect(ctx)

    delta_dict = ref.details.get("delta")
    assert delta_dict is not None
    assert delta_dict["newly_failing"] == ["tests/test_a.py::test_x"]
    assert delta_dict["flakes"] == []
    assert ref.details["flake_retried"] is True


def test_flake_retry_confirms_stable_newly_passing(tmp_path: Path) -> None:
    """A test that was failing in baseline, passes in verification, and
    stays passing in the retry is newly_passing."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        failures=["tests/test_a.py::test_x"],
        passes=["tests/test_b.py::test_y"],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        failures=[],
        passes=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
    )
    retry = _make_result(
        run_id="fr-1",
        phase="flake_retry",
        collected_ids=["tests/test_a.py::test_x"],
        failures=[],
        passes=["tests/test_a.py::test_x"],
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
                side_effect=[verification, retry],
            )
        )
        ref = provider.collect(ctx)

    delta_dict = ref.details.get("delta")
    assert delta_dict is not None
    assert delta_dict["newly_passing"] == ["tests/test_a.py::test_x"]
    assert delta_dict["flakes"] == []


def test_flake_retry_skipped_when_no_flips(tmp_path: Path) -> None:
    """When there are no flipped nodeids, flake retry is not invoked."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        failures=["tests/test_a.py::test_x"],
        passes=["tests/test_b.py::test_y"],
    )
    # Same failures — no flips.
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        failures=["tests/test_a.py::test_x"],
        passes=["tests/test_b.py::test_y"],
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        m_run = stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
                return_value=verification,
            )
        )
        ref = provider.collect(ctx)

    # run_suite called exactly once (verification only, no retry).
    assert m_run.call_count == 1
    assert ref.details.get("flake_retried") is False


# ---------------------------------------------------------------------------
# (iv) Flake retry skipped for >1000 flips
# ---------------------------------------------------------------------------


def test_flake_retry_skipped_over_1000_flips(tmp_path: Path) -> None:
    """When >1000 nodeids flip, retry is skipped and all are marked flakes."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    # Generate 1001 nodeids that pass in baseline.
    many_ids = [f"tests/test_x.py::test_{i}" for i in range(1001)]
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=many_ids,
        failures=[],
        passes=many_ids,
        collected=1001,
    )
    # All 1001 now fail in verification.
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=many_ids,
        failures=many_ids,
        passes=[],
        collected=1001,
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        m_run = stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
                return_value=verification,
            )
        )
        ref = provider.collect(ctx)

    # run_suite called once (verification only), no retry.
    assert m_run.call_count == 1

    delta_dict = ref.details.get("delta")
    assert delta_dict is not None
    assert delta_dict["computable"] is True
    # All 1001 are flakes, none are newly_failing.
    assert len(delta_dict["flakes"]) == 1001
    assert delta_dict["newly_failing"] == []
    assert delta_dict["flake_retry_skipped"] is True
    assert ">1000" in delta_dict["flake_retry_reason"]


def test_flake_retry_runs_for_100_or_fewer_flips(tmp_path: Path) -> None:
    """When ≤100 nodeids flip, retry runs with direct nodeid args."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    many_ids = [f"tests/test_x.py::test_{i}" for i in range(50)]
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=many_ids,
        failures=[],
        passes=many_ids,
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=many_ids,
        failures=many_ids,
        passes=[],
    )
    # Retry: all 50 still fail (stable).
    retry = _make_result(
        run_id="fr-1",
        phase="flake_retry",
        collected_ids=many_ids,
        failures=many_ids,
        passes=[],
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        m_run = stack.enter_context(
            mock.patch(
                "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite",
                side_effect=[verification, retry],
            )
        )
        ref = provider.collect(ctx)

        # Two calls: verification + retry.
        assert m_run.call_count == 2
        assert ref.details["flake_retried"] is True
        delta_dict = ref.details["delta"]
        # Nodeids are sorted lexicographically (string sort), not numerically.
        assert set(delta_dict["newly_failing"]) == set(many_ids)
        assert len(delta_dict["newly_failing"]) == 50


# ---------------------------------------------------------------------------
# (v) collections_parse_ok=False yields delta.computable=False
# ---------------------------------------------------------------------------


def test_collections_parse_failure_yields_not_computable(
    tmp_path: Path,
) -> None:
    """When verification has collections_parse_ok=False, delta is
    non-computable and verdict is runner_error-style (unsatisfied, not
    silent-green)."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collections_parse_ok=True,
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collections_parse_ok=False,
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    delta_dict = ref.details.get("delta")
    assert delta_dict is not None
    assert delta_dict["computable"] is False
    # Verdict is unsatisfied (runner_error-style), NOT satisfied/passed.
    assert ref.status == EvidenceStatus.unsatisfied
    assert "not computable" in ref.summary.lower()
    assert ref.details.get("failures") == ["runner_error"]


def test_baseline_parse_failure_yields_not_computable(
    tmp_path: Path,
) -> None:
    """When baseline has collections_parse_ok=False, delta is non-computable."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collections_parse_ok=False,
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collections_parse_ok=True,
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    delta_dict = ref.details.get("delta")
    assert delta_dict is not None
    assert delta_dict["computable"] is False
    assert ref.status == EvidenceStatus.unsatisfied
    assert ref.details.get("failures") == ["runner_error"]


def test_both_parse_failure_yields_not_computable(tmp_path: Path) -> None:
    """When both baseline and verification have collections_parse_ok=False."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collections_parse_ok=False,
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collections_parse_ok=False,
    )

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=baseline):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    delta_dict = ref.details.get("delta")
    assert delta_dict is not None
    assert delta_dict["computable"] is False
    assert ref.status == EvidenceStatus.unsatisfied
    assert ref.details.get("failures") == ["runner_error"]


def test_no_baseline_yields_no_delta(tmp_path: Path) -> None:
    """When no baseline record exists at all, delta is None but
    collect still returns a valid EvidenceRef (fail-open)."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()

    verification = _make_result()

    with contextlib.ExitStack() as stack:
        for p in _mock_collect_deps(verification, baseline=None):
            stack.enter_context(p)
        ref = provider.collect(ctx)

    # No delta because there is no baseline.
    assert ref.details.get("delta") is None
    # Still returns a valid verdict (passed).
    assert ref.status == EvidenceStatus.satisfied


# ---------------------------------------------------------------------------
# compute_delta standalone unit tests
# ---------------------------------------------------------------------------


def test_compute_delta_all_green(tmp_path: Path) -> None:
    """All passing, no failures, no changes."""
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["a", "b", "c"],
        failures=[],
        passes=["a", "b", "c"],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["a", "b", "c"],
        failures=[],
        passes=["a", "b", "c"],
    )
    delta = compute_delta(baseline, verification)
    assert delta.computable is True
    assert delta.newly_failing == ()
    assert delta.newly_passing == ()
    assert delta.still_red == ()
    assert delta.still_green == ("a", "b", "c")
    assert delta.deleted_tests == ()
    assert delta.added_tests == ()
    assert delta.tests_collected == 3


def test_compute_delta_new_failure(tmp_path: Path) -> None:
    """A previously passing test now fails."""
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["a", "b"],
        failures=[],
        passes=["a", "b"],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["a", "b"],
        failures=["a"],
        passes=["b"],
    )
    delta = compute_delta(baseline, verification)
    assert delta.newly_failing == ("a",)
    assert delta.newly_passing == ()
    assert delta.still_green == ("b",)


def test_compute_delta_fixed_failure(tmp_path: Path) -> None:
    """A previously failing test now passes."""
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["a", "b"],
        failures=["a"],
        passes=["b"],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["a", "b"],
        failures=[],
        passes=["a", "b"],
    )
    delta = compute_delta(baseline, verification)
    assert delta.newly_passing == ("a",)
    assert delta.newly_failing == ()
    assert delta.still_green == ("b",)


def test_compute_delta_mixed(tmp_path: Path) -> None:
    """One fixed, one new failure, one still red, one deleted.

    ``d`` was failing in baseline but is absent from verification_collected
    → it is a deleted test, NOT newly_passing.  ``newly_passing`` is
    intersected with ``verification_collected`` so deleted tests can never
    surface as passing.
    """
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["a", "b", "c", "d"],
        failures=["a", "d"],
        passes=["b", "c"],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["a", "b", "c"],
        failures=["a", "b"],
        passes=["c"],
    )
    delta = compute_delta(baseline, verification)
    assert delta.newly_failing == ("b",)
    # d was deleted — NOT in newly_passing (intersected with verification_collected).
    assert delta.newly_passing == ()
    assert delta.still_red == ("a",)
    assert delta.still_green == ("c",)
    assert delta.deleted_tests == ("d",)


def test_compute_delta_duration_comes_from_verification(tmp_path: Path) -> None:
    """duration field is verification.duration."""
    baseline = _make_result(duration=100.0)
    verification = _make_result(duration=5.5)
    delta = compute_delta(baseline, verification)
    assert delta.duration == 5.5


def test_compute_delta_sorted_tuples(tmp_path: Path) -> None:
    """All nodeid tuples are sorted."""
    baseline = _make_result(
        run_id="bl-1",
        phase="baseline",
        collected_ids=["z", "a", "m"],
        failures=[],
        passes=["z", "a", "m"],
    )
    verification = _make_result(
        run_id="vf-1",
        phase="verification",
        collected_ids=["z", "a", "m"],
        failures=["z", "a", "m"],
        passes=[],
    )
    delta = compute_delta(baseline, verification)
    # Should be alphabetically sorted.
    assert delta.newly_failing == ("a", "m", "z")


def test_suite_delta_to_dict_roundtrip(tmp_path: Path) -> None:
    """SuiteDelta.to_dict produces a JSON-serializable dict."""
    delta = SuiteDelta(
        computable=True,
        newly_failing=("a", "b"),
        newly_passing=("c",),
        still_red=(),
        still_green=("d", "e"),
        deleted_tests=(),
        added_tests=(),
        flakes=("f",),
        tests_collected=5,
        duration=1.23,
        flake_retry_skipped=False,
        flake_retry_reason="",
    )
    d = delta.to_dict()
    assert d["computable"] is True
    assert d["newly_failing"] == ["a", "b"]
    assert d["newly_passing"] == ["c"]
    assert d["flakes"] == ["f"]
    assert d["tests_collected"] == 5
    assert d["duration"] == 1.23
    # Should be JSON-serializable.
    json.dumps(d)


def test_completion_contract_reexports_evidence_symbols_for_green_suite_compat() -> None:
    """Compatibility imports used by green-suite tests remain available."""
    ref = EvidenceRef(
        kind="green_suite",
        status=EvidenceStatus.satisfied,
        summary="suite passed",
        details={"delta": {}},
        trust_class=TrustClass.evidence,
        artifact=ArtifactRef(path="suite_runs.ndjson", artifact_type="suite_run_log"),
    )

    assert ref.status is EvidenceStatus.satisfied
    assert ref.trust_class is TrustClass.evidence
    assert ref.artifact is not None
    assert ref.artifact.path == "suite_runs.ndjson"
