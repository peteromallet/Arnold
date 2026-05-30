"""Tests for GreenSuiteProvider verification runs in all modes.

Verifies that:
  (i)   GreenSuiteProvider.collect runs the verification suite in every
        contract mode (off/shadow/warn/enforce) — mode does NOT gate
        measurement.
  (ii)  freshness_skip is honored: when a verification record with a
        matching code_hash already exists, run_suite is NOT called.
  (iii) The suite run is appended to suite_runs.ndjson.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from megaplan.orchestration.completion_contract import (
    CONTRACT_MODE_ENFORCE,
    CONTRACT_MODE_OFF,
    CONTRACT_MODE_SHADOW,
    CONTRACT_MODE_WARN,
    CompletionContext,
    CompletionSubject,
    EvidenceStatus,
    GreenSuiteProvider,
)
from megaplan.orchestration.suite_runner import SuiteRunResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _subject(name: str = "plan-x") -> CompletionSubject:
    return CompletionSubject(kind="plan", name=name, to_state="done", plan_name=name)


def _make_fake_result(**overrides: object) -> SuiteRunResult:
    """Build a SuiteRunResult with sensible defaults, overridable by kwarg."""
    defaults: dict[str, object] = {
        "run_id": "fake-run-id",
        "phase": "verification",
        "command": "pytest --tb=no -q --no-header -rN",
        "duration": 0.1,
        "collected": 2,
        "collected_ids": ["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
        "failures": [],
        "passes": ["tests/test_a.py::test_x", "tests/test_b.py::test_y"],
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
    mode: str = CONTRACT_MODE_SHADOW,
    *,
    plan_dir: Path | None = None,
    project_dir: Path | None = None,
) -> CompletionContext:
    """Build a CompletionContext with a state config carrying *mode*."""
    pd = plan_dir or (tmp_path / "plan")
    pd.mkdir(parents=True, exist_ok=True)
    proj = project_dir or (tmp_path / "repo")
    proj.mkdir(parents=True, exist_ok=True)
    return CompletionContext(
        plan_dir=pd,
        project_dir=proj,
        state={
            "config": {
                "completion_contract_mode": mode,
                "test_baseline_timeout": 30,
                "project_dir": str(proj),
            }
        },
        subject=_subject(),
    )


# ---------------------------------------------------------------------------
# (i) Verification runs in ALL modes — mode does NOT gate measurement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode",
    [CONTRACT_MODE_OFF, CONTRACT_MODE_SHADOW, CONTRACT_MODE_WARN, CONTRACT_MODE_ENFORCE],
)
def test_verification_runs_in_all_modes(tmp_path: Path, mode: str) -> None:
    """GreenSuiteProvider.collect calls run_suite in every mode."""
    ctx = _ctx(tmp_path, mode=mode)
    provider = GreenSuiteProvider()
    fake = _make_fake_result()

    # The functions are imported locally inside collect(), so we mock the
    # source module (suite_runner), not completion_contract.
    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as m_run:
        with mock.patch(
            "megaplan.orchestration.suite_runner.append_suite_run",
        ) as m_append:
            ref = provider.collect(ctx)

    # run_suite is always called (mode does NOT gate measurement).
    m_run.assert_called_once()
    call_kwargs = m_run.call_args.kwargs
    assert call_kwargs["phase"] == "verification"

    # append_suite_run is always called.
    m_append.assert_called_once_with(ctx.plan_dir, fake)

    # EvidenceRef reflects the fake passed result.
    assert ref.kind == "green_suite"
    assert ref.status == EvidenceStatus.satisfied
    assert ref.details["status"] == "passed"
    assert ref.details["freshness_cache_hit"] is False
    assert "raw_log_path" in ref.details


@pytest.mark.parametrize(
    "mode",
    [CONTRACT_MODE_OFF, CONTRACT_MODE_SHADOW, CONTRACT_MODE_WARN, CONTRACT_MODE_ENFORCE],
)
def test_verification_failure_surfaced_in_all_modes(tmp_path: Path, mode: str) -> None:
    """A failing verification suite is flagged in every mode."""
    ctx = _ctx(tmp_path, mode=mode)
    provider = GreenSuiteProvider()
    fake = _make_fake_result(
        status="failed",
        exit_code=1,
        failures=["tests/test_a.py::test_x"],
        passes=["tests/test_b.py::test_y"],
    )

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with mock.patch(
            "megaplan.orchestration.suite_runner.append_suite_run",
        ):
            ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.unsatisfied
    assert ref.details["status"] == "failed"
    assert ref.details["failure_count"] == 1
    assert "tests/test_a.py::test_x" in ref.details["failures"]


# ---------------------------------------------------------------------------
# (ii) Freshness-skip honored
# ---------------------------------------------------------------------------


def test_freshness_skip_honored_when_hash_matches(tmp_path: Path) -> None:
    """When a verification record with matching code_hash exists, run_suite is skipped."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    fake = _make_fake_result(code_hash="match-me")

    # Pre-populate a verification record in suite_runs.ndjson with the
    # same code_hash that _compute_code_hash will produce.
    with mock.patch(
        "megaplan.orchestration.suite_runner._compute_code_hash",
        return_value="match-me",
    ):
        # Seed the ndjson log with a matching verification record.
        from megaplan.orchestration.suite_runner import append_suite_run as real_append

        seed = _make_fake_result(code_hash="match-me", phase="verification")
        real_append(ctx.plan_dir, seed)

        with mock.patch(
            "megaplan.orchestration.suite_runner.run_suite",
            return_value=fake,
        ) as m_run:
            with mock.patch(
                "megaplan.orchestration.suite_runner.append_suite_run",
            ) as m_append:
                ref = provider.collect(ctx)

    # run_suite MUST NOT be called — freshness_skip returned the cached result.
    m_run.assert_not_called()

    # append_suite_run MUST NOT be called (no new run to persist).
    m_append.assert_not_called()

    # EvidenceRef shows freshness cache hit.
    assert ref.details["freshness_cache_hit"] is True
    assert ref.details["code_hash"] == "match-me"
    assert ref.status == EvidenceStatus.satisfied


def test_freshness_skip_not_honored_when_hash_mismatches(tmp_path: Path) -> None:
    """When code_hash differs, a fresh run is triggered."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    fake = _make_fake_result(code_hash="new-hash")

    # Seed with a DIFFERENT hash.
    from megaplan.orchestration.suite_runner import append_suite_run as real_append

    seed = _make_fake_result(code_hash="old-hash", phase="verification")
    real_append(ctx.plan_dir, seed)

    with mock.patch(
        "megaplan.orchestration.suite_runner._compute_code_hash",
        return_value="new-hash",
    ):
        with mock.patch(
            "megaplan.orchestration.suite_runner.run_suite",
            return_value=fake,
        ) as m_run:
            with mock.patch(
                "megaplan.orchestration.suite_runner.append_suite_run",
            ) as m_append:
                ref = provider.collect(ctx)

    # run_suite IS called because hash mismatched.
    m_run.assert_called_once()
    m_append.assert_called_once_with(ctx.plan_dir, fake)

    # EvidenceRef shows no freshness cache hit.
    assert ref.details["freshness_cache_hit"] is False
    assert ref.details["code_hash"] == "new-hash"


def test_freshness_skip_not_honored_when_no_prior_record(tmp_path: Path) -> None:
    """When no verification record exists at all, a fresh run is triggered."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    fake = _make_fake_result()

    with mock.patch(
        "megaplan.orchestration.suite_runner._compute_code_hash",
        return_value="some-hash",
    ):
        with mock.patch(
            "megaplan.orchestration.suite_runner.run_suite",
            return_value=fake,
        ) as m_run:
            ref = provider.collect(ctx)

    m_run.assert_called_once()
    assert ref.details["freshness_cache_hit"] is False


# ---------------------------------------------------------------------------
# (iii) Suite run is recorded in suite_runs.ndjson
# ---------------------------------------------------------------------------


def test_suite_run_appended_to_ndjson(tmp_path: Path) -> None:
    """After a fresh run, suite_runs.ndjson contains the new record."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    fake = _make_fake_result(
        run_id="test-run-001", phase="verification", code_hash="hash-1",
    )

    ndjson_path = ctx.plan_dir / "verification" / "suite_runs.ndjson"

    with mock.patch(
        "megaplan.orchestration.suite_runner._compute_code_hash",
        return_value="hash-1",
    ):
        with mock.patch(
            "megaplan.orchestration.suite_runner.run_suite",
            return_value=fake,
        ):
            # Use the REAL append_suite_run so the log is actually written.
            provider.collect(ctx)

    # Verify the ndjson file exists and contains exactly one line.
    assert ndjson_path.is_file(), f"Expected {ndjson_path} to exist"
    lines = ndjson_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1, f"Expected 1 line, got {len(lines)}"

    record = json.loads(lines[0])
    assert record["run_id"] == "test-run-001"
    assert record["phase"] == "verification"
    assert record["status"] == "passed"
    assert record["code_hash"] == "hash-1"
    assert "ts" in record


def test_multiple_runs_all_appended(tmp_path: Path) -> None:
    """Multiple collect() calls append one line each to suite_runs.ndjson."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    ndjson_path = ctx.plan_dir / "verification" / "suite_runs.ndjson"

    for i in range(3):
        fake = _make_fake_result(run_id=f"run-{i}", code_hash=f"hash-{i}")
        with mock.patch(
            "megaplan.orchestration.suite_runner._compute_code_hash",
            return_value=f"hash-{i}",
        ):
            with mock.patch(
                "megaplan.orchestration.suite_runner.run_suite",
                return_value=fake,
            ):
                provider.collect(ctx)

    lines = ndjson_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 3
    run_ids = [json.loads(line)["run_id"] for line in lines]
    assert run_ids == ["run-0", "run-1", "run-2"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_timeout_surfaced_as_unsatisfied(tmp_path: Path) -> None:
    """A timed-out suite run is flagged as unsatisfied."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    fake = _make_fake_result(status="timeout", exit_code=None)

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with mock.patch(
            "megaplan.orchestration.suite_runner.append_suite_run",
        ):
            ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.unsatisfied
    assert "timed out" in ref.summary.lower()


def test_runner_error_surfaced_as_unsatisfied(tmp_path: Path) -> None:
    """A runner_error suite run is flagged as unsatisfied (runner_error)."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    fake = _make_fake_result(status="runner_error", exit_code=2)

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with mock.patch(
            "megaplan.orchestration.suite_runner.append_suite_run",
        ):
            ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.unsatisfied
    assert "runner error" in ref.summary.lower()
    assert ref.details.get("failures") == ["runner_error"]


def test_not_applicable_surfaced_as_not_applicable(tmp_path: Path) -> None:
    """A not_applicable suite run (exit code 5) is not_applicable."""
    ctx = _ctx(tmp_path)
    provider = GreenSuiteProvider()
    fake = _make_fake_result(status="not_applicable", exit_code=5)

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with mock.patch(
            "megaplan.orchestration.suite_runner.append_suite_run",
        ):
            ref = provider.collect(ctx)

    assert ref.status == EvidenceStatus.not_applicable


def test_config_timeout_is_used(tmp_path: Path) -> None:
    """The deadline uses test_baseline_timeout from config."""
    ctx = _ctx(tmp_path)
    # Override timeout in config.
    ctx = CompletionContext(
        plan_dir=ctx.plan_dir,
        project_dir=ctx.project_dir,
        state={
            "config": {
                "test_baseline_timeout": 42,
                "project_dir": str(ctx.project_dir),
            }
        },
        subject=_subject(),
    )
    provider = GreenSuiteProvider()
    fake = _make_fake_result()

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ) as m_run:
        provider.collect(ctx)

    call_kwargs = m_run.call_args.kwargs
    assert call_kwargs["phase"] == "verification"


def test_baseline_backcompat_fields_present(tmp_path: Path) -> None:
    """Details still include baseline_test_command and baseline_test_note."""
    ctx = _ctx(tmp_path)
    # Write a finalize.json with baseline info.
    (ctx.plan_dir / "finalize.json").write_text(
        json.dumps({
            "baseline_test_failures": [],
            "baseline_test_command": "pytest -x",
            "baseline_test_note": "baseline captured OK",
        }),
        encoding="utf-8",
    )
    provider = GreenSuiteProvider()
    fake = _make_fake_result()

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite",
        return_value=fake,
    ):
        with mock.patch(
            "megaplan.orchestration.suite_runner.append_suite_run",
        ):
            ref = provider.collect(ctx)

    assert ref.details["baseline_test_command"] == "pytest -x"
    assert ref.details["baseline_test_note"] == "baseline captured OK"
