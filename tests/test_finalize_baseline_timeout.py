from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

import arnold.pipelines.megaplan.handlers as megaplan_handlers
from arnold.pipelines.megaplan.orchestration.suite_runner import SuiteRunResult


def _make_result(**overrides: object) -> SuiteRunResult:
    """Build a SuiteRunResult with reasonable defaults."""
    defaults: dict[str, object] = {
        "run_id": "abc123def456",
        "phase": "baseline",
        "command": "pytest --tb=no -q --no-header -rA",
        "duration": 1.5,
        "collected": 5,
        "collected_ids": [],
        "failures": [],
        "passes": [],
        "status": "timeout",
        "exit_code": None,
        "raw_log_path": Path("/tmp/raw_abc123def456.log"),
        "code_hash": "sha256:deadbeef",
        "collections_parse_ok": False,
    }
    defaults.update(overrides)
    return SuiteRunResult(**{k: v for k, v in defaults.items()})  # type: ignore[arg-type]


# ── default absolute ceiling (3600s) ────────────────────────────────────


def test_capture_test_baseline_default_timeout_is_3600(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When no test_baseline_timeout key is present, the run_suite call
    should use deadline=monotonic+900 and the timeout note should reference 900."""
    monkeypatch.delenv(megaplan_handlers.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(status="timeout")  # timeout_reason defaults to None

    with mock.patch(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = megaplan_handlers._capture_test_baseline(tmp_path, {})

    assert result["baseline_test_failures"] is None
    assert "ceiling" in result["baseline_test_note"].lower()
    assert "3600" in result["baseline_test_note"]
    mock_run.assert_called_once()


def test_capture_test_baseline_idle_stall_note(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A timeout attributed to idle (a wedged suite) yields a 'stalled'/'wedged'
    note referencing the idle cap, not the absolute ceiling."""
    monkeypatch.delenv(megaplan.handlers.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(status="timeout", timeout_reason="idle")

    with mock.patch(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = megaplan.handlers._capture_test_baseline(
            tmp_path, {"test_baseline_idle_timeout": 180}
        )

    assert result["baseline_test_failures"] is None
    note = result["baseline_test_note"].lower()
    assert "stalled" in note and "wedged" in note
    assert "180" in result["baseline_test_note"]
    mock_run.assert_called_once()


# ── absolute-ceiling override honoured ──────────────────────────────────


def test_capture_test_baseline_override_timeout_300(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When test_baseline_timeout is set to 300, timeout note should reference 300."""
    monkeypatch.delenv(megaplan_handlers.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(status="timeout")

    with mock.patch(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = megaplan_handlers._capture_test_baseline(
            tmp_path, {"test_baseline_timeout": 300}
        )

    assert result["baseline_test_failures"] is None
    assert "ceiling" in result["baseline_test_note"].lower()
    assert "300" in result["baseline_test_note"]
    mock_run.assert_called_once()


def test_capture_test_baseline_override_timeout_1500(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When test_baseline_timeout is set to 1500, timeout note should reference 1500."""
    monkeypatch.delenv(megaplan_handlers.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(status="timeout")

    with mock.patch(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = megaplan_handlers._capture_test_baseline(
            tmp_path, {"test_baseline_timeout": 1500}
        )

    assert result["baseline_test_failures"] is None
    assert "ceiling" in result["baseline_test_note"].lower()
    assert "1500" in result["baseline_test_note"]
    mock_run.assert_called_once()


# ── string override (int-like) ──────────────────────────────────────────


def test_capture_test_baseline_override_timeout_string(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """test_baseline_timeout as a string '600' should be coerced to int and used."""
    monkeypatch.delenv(megaplan_handlers.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(status="timeout")

    with mock.patch(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = megaplan_handlers._capture_test_baseline(
            tmp_path, {"test_baseline_timeout": "600"}
        )

    assert result["baseline_test_failures"] is None
    assert "600" in result["baseline_test_note"]
    mock_run.assert_called_once()


# ── invalid config values ───────────────────────────────────────────────


def test_capture_test_baseline_invalid_timeout_negative(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A negative timeout should produce an invalidity note early, before run_suite is invoked."""
    monkeypatch.delenv(megaplan_handlers.MOCK_ENV_VAR, raising=False)

    with mock.patch(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run:
        result = megaplan_handlers._capture_test_baseline(
            tmp_path, {"test_baseline_timeout": -1}
        )

    assert result["baseline_test_failures"] is None
    assert "invalid" in result["baseline_test_note"].lower()
    assert "must be a positive integer" in result["baseline_test_note"]
    mock_run.assert_not_called()


def test_capture_test_baseline_invalid_timeout_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Zero timeout should produce an invalidity note early."""
    monkeypatch.delenv(megaplan_handlers.MOCK_ENV_VAR, raising=False)

    with mock.patch(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run:
        result = megaplan_handlers._capture_test_baseline(
            tmp_path, {"test_baseline_timeout": 0}
        )

    assert result["baseline_test_failures"] is None
    assert "invalid" in result["baseline_test_note"].lower()
    assert "must be a positive integer" in result["baseline_test_note"]
    mock_run.assert_not_called()


def test_capture_test_baseline_invalid_timeout_non_numeric(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A non-numeric timeout should produce an invalidity note early."""
    monkeypatch.delenv(megaplan_handlers.MOCK_ENV_VAR, raising=False)

    with mock.patch(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite"
    ) as mock_run:
        result = megaplan_handlers._capture_test_baseline(
            tmp_path, {"test_baseline_timeout": "fast"}
        )

    assert result["baseline_test_failures"] is None
    assert "invalid" in result["baseline_test_note"].lower()
    assert "must be a positive integer" in result["baseline_test_note"]
    mock_run.assert_not_called()


# ── override honoured on success path (no timeout) ──────────────────────


def test_capture_test_baseline_override_passed_through_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When the command succeeds, the configured timeout is used and baseline is empty."""
    monkeypatch.delenv(megaplan_handlers.MOCK_ENV_VAR, raising=False)

    fake_result = _make_result(
        status="passed",
        exit_code=0,
        failures=[],
        passes=["tests/test_x.py::test_pass"],
    )

    with mock.patch(
        "arnold.pipelines.megaplan.orchestration.suite_runner.run_suite", return_value=fake_result
    ) as mock_run:
        result = megaplan_handlers._capture_test_baseline(
            tmp_path, {"test_baseline_timeout": 1800}
        )

    assert result["baseline_test_failures"] == []
    assert result["baseline_test_command"] == fake_result.command
    mock_run.assert_called_once()
