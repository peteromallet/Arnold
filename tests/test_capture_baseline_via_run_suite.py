"""Tests for ``_capture_test_baseline`` refactored to call ``run_suite``.

Verifies:
- Baseline capture round-trips through ``run_suite`` (mock).
- Back-compat ``baseline_test_failures`` / ``baseline_test_command`` / ``baseline_test_note`` are populated.
- Timeout, runner_error, not_applicable, passed, and failed paths.
- Mock mode returns the expected stub.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest import mock

import pytest

from megaplan.orchestration.suite_runner import SuiteRunResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(**overrides: object) -> SuiteRunResult:
    """Build a SuiteRunResult with reasonable defaults."""
    defaults: dict[str, object] = {
        "run_id": "abc123def456",
        "phase": "baseline",
        "command": "pytest --tb=no -q --no-header -rN",
        "duration": 1.5,
        "collected": 5,
        "collected_ids": [
            "tests/test_a.py::test_pass",
            "tests/test_a.py::test_fail",
        ],
        "failures": ["tests/test_a.py::test_fail"],
        "passes": ["tests/test_a.py::test_pass"],
        "status": "failed",
        "exit_code": 1,
        "raw_log_path": Path("/tmp/raw_abc123def456.log"),
        "code_hash": "sha256:deadbeef",
        "collections_parse_ok": True,
    }
    defaults.update(overrides)
    return SuiteRunResult(**{k: v for k, v in defaults.items() if k != "overrides"})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Mock-path
# ---------------------------------------------------------------------------


def test_capture_baseline_mock_env_returns_stub(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When MOCK_ENV_VAR is set, return empty failures + command stub."""
    import megaplan.handlers.finalize as _mod

    monkeypatch.setenv(_mod.MOCK_ENV_VAR, "1")
    result = _mod._capture_test_baseline(tmp_path, {})
    assert result["baseline_test_failures"] == []
    assert result["baseline_test_command"] == "pytest --tb=no -q --no-header -rN"


# ---------------------------------------------------------------------------
# Invalid timeout
# ---------------------------------------------------------------------------


def test_capture_baseline_invalid_timeout_returns_note(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Non-positive / non-int timeout returns None failures + note."""
    import megaplan.handlers.finalize as _mod

    monkeypatch.delenv(_mod.MOCK_ENV_VAR, raising=False)
    result = _mod._capture_test_baseline(
        tmp_path,
        {"test_baseline_timeout": "not_a_number", "test_command": "pytest"},
    )
    assert result["baseline_test_failures"] is None
    assert "invalid" in result["baseline_test_note"].lower()
    assert result["baseline_test_command"] == "pytest"


# ---------------------------------------------------------------------------
# run_suite round-trip: timeout path
# ---------------------------------------------------------------------------


def test_capture_baseline_via_run_suite_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When run_suite returns timeout, baseline is None + note."""
    import megaplan.handlers.finalize as _mod

    monkeypatch.delenv(_mod.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(status="timeout", exit_code=None, failures=[])

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = _mod._capture_test_baseline(tmp_path, {"test_baseline_timeout": 60})
        mock_run.assert_called_once()

    assert result["baseline_test_failures"] is None
    assert "timed out" in result["baseline_test_note"].lower()
    assert "60" in result["baseline_test_note"]
    assert result["baseline_test_command"] == fake_result.command


# ---------------------------------------------------------------------------
# run_suite round-trip: runner_error path
# ---------------------------------------------------------------------------


def test_capture_baseline_via_run_suite_runner_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When run_suite returns runner_error, baseline is None + note."""
    import megaplan.handlers.finalize as _mod

    monkeypatch.delenv(_mod.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(status="runner_error", exit_code=2, failures=[])

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = _mod._capture_test_baseline(tmp_path, {})
        mock_run.assert_called_once()

    assert result["baseline_test_failures"] is None
    assert "runner error" in result["baseline_test_note"].lower()
    assert result["baseline_test_command"] is None


# ---------------------------------------------------------------------------
# run_suite round-trip: not_applicable path
# ---------------------------------------------------------------------------


def test_capture_baseline_via_run_suite_not_applicable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When run_suite returns not_applicable, baseline is None + note about no tests."""
    import megaplan.handlers.finalize as _mod

    monkeypatch.delenv(_mod.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(status="not_applicable", exit_code=5, failures=[])

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = _mod._capture_test_baseline(tmp_path, {})
        mock_run.assert_called_once()

    assert result["baseline_test_failures"] is None
    assert "no tests collected" in result["baseline_test_note"].lower()
    assert result["baseline_test_command"] == fake_result.command


# ---------------------------------------------------------------------------
# run_suite round-trip: passed (all green)
# ---------------------------------------------------------------------------


def test_capture_baseline_via_run_suite_passed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When run_suite returns passed, baseline failures = []."""
    import megaplan.handlers.finalize as _mod

    monkeypatch.delenv(_mod.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(
        status="passed",
        exit_code=0,
        failures=[],
        passes=["tests/test_a.py::test_pass"],
    )

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = _mod._capture_test_baseline(tmp_path, {})
        mock_run.assert_called_once()

    assert result["baseline_test_failures"] == []
    assert result["baseline_test_command"] == fake_result.command
    assert "baseline_test_note" not in result  # no note on success


# ---------------------------------------------------------------------------
# run_suite round-trip: failed (pre-existing failures recorded)
# ---------------------------------------------------------------------------


def test_capture_baseline_via_run_suite_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When run_suite returns failed, baseline failures = nodeid list."""
    import megaplan.handlers.finalize as _mod

    monkeypatch.delenv(_mod.MOCK_ENV_VAR, raising=False)

    expected_failures = [
        "tests/test_a.py::test_broken",
        "tests/test_b.py::test_param[0-1]",
    ]
    fake_result = _make_result(
        status="failed",
        exit_code=1,
        failures=expected_failures,
        passes=["tests/test_a.py::test_pass"],
    )

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = _mod._capture_test_baseline(tmp_path, {})
        mock_run.assert_called_once()

    assert result["baseline_test_failures"] == expected_failures
    assert result["baseline_test_command"] == fake_result.command
    assert "baseline_test_note" not in result


# ---------------------------------------------------------------------------
# Back-compat: fields are present and correctly typed
# ---------------------------------------------------------------------------


def test_capture_baseline_backcompat_fields_structure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The returned dict always has baseline_test_failures, baseline_test_command,
    and (when relevant) baseline_test_note."""
    import megaplan.handlers.finalize as _mod

    monkeypatch.delenv(_mod.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(
        status="failed",
        exit_code=1,
        failures=["tests/test_x.py::test_y"],
    )

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ):
        result = _mod._capture_test_baseline(tmp_path, {})

    assert "baseline_test_failures" in result
    assert isinstance(result["baseline_test_failures"], list)
    assert "baseline_test_command" in result
    assert isinstance(result["baseline_test_command"], str)


# ---------------------------------------------------------------------------
# run_suite receives correct deadline and phase
# ---------------------------------------------------------------------------


def test_capture_baseline_passes_correct_arguments_to_run_suite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that deadline_seconds is computed as monotonic + timeout and
    phase='baseline' is passed."""
    import megaplan.handlers.finalize as _mod

    monkeypatch.delenv(_mod.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result()

    with mock.patch(
        "megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        _mod._capture_test_baseline(
            tmp_path, {"test_baseline_timeout": 42}
        )

    call_kwargs = mock_run.call_args.kwargs
    assert call_kwargs["phase"] == "baseline"
    # deadline_seconds should be ~monotonic_now + 42
    deadline = call_kwargs["deadline_seconds"]
    now = time.monotonic()
    assert deadline > now  # deadline is in the future
    assert deadline <= now + 42 + 1  # small epsilon
