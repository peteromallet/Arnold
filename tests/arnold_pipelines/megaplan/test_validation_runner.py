"""Tests for the deterministic validation job runner.

Covers subprocess execution, evidence capture, error handling, and the
extraction helper — all without requiring a live plan directory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from arnold_pipelines.megaplan.execute.validation_runner import (
    ValidationJobResult,
    ValidationRunReport,
    _classify_job,
    _compute_code_hash,
    _compute_result_hash,
    extract_compiled_validation_jobs,
    run_single_validation_job,
    run_validation_jobs,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_job(**overrides) -> dict:
    """Create a minimal valid compiled validation job."""
    job = {
        "id": "vj-01",
        "command": ["echo", "hello"],
        "environment": {},
        "cwd": "${project_dir}",
        "timeout_seconds": 30,
        "expected_output_paths": [],
        "content_addressed_evidence": True,
    }
    job.update(overrides)
    return job


# ============================================================================
# Test compute helpers
# ============================================================================


class TestCodeHash:
    """_compute_code_hash produces deterministic hashes."""

    def test_identical_jobs_produce_same_hash(self) -> None:
        h1 = _compute_code_hash(_make_job())
        h2 = _compute_code_hash(_make_job())
        assert h1 == h2
        assert len(h1) == 64

    def test_different_commands_produce_different_hash(self) -> None:
        h1 = _compute_code_hash(_make_job(command=["echo", "a"]))
        h2 = _compute_code_hash(_make_job(command=["echo", "b"]))
        assert h1 != h2

    def test_different_env_produces_different_hash(self) -> None:
        h1 = _compute_code_hash(_make_job(environment={"X": "1"}))
        h2 = _compute_code_hash(_make_job(environment={"X": "2"}))
        assert h1 != h2


class TestResultHash:
    """_compute_result_hash produces deterministic hashes."""

    def test_identical_results_produce_same_hash(self) -> None:
        h1 = _compute_result_hash(0, "out", "err")
        h2 = _compute_result_hash(0, "out", "err")
        assert h1 == h2
        assert len(h1) == 64

    def test_different_exit_code_different_hash(self) -> None:
        h1 = _compute_result_hash(0, "out", "")
        h2 = _compute_result_hash(1, "out", "")
        assert h1 != h2


# ============================================================================
# Test _classify_job
# ============================================================================


class TestClassifyJob:
    """_classify_job detects mutating or unexecutable jobs."""

    def test_valid_job_returns_none(self) -> None:
        assert _classify_job(_make_job()) is None

    def test_non_empty_expected_output_paths_is_mutating(self) -> None:
        assert _classify_job(_make_job(expected_output_paths=["out.txt"])) == "validation_mutating"

    def test_write_set_with_paths_is_mutating(self) -> None:
        assert (
            _classify_job(_make_job(write_set={"paths": ["f.py"]})) == "validation_mutating"
        )

    def test_empty_write_set_paths_not_mutating(self) -> None:
        assert _classify_job(_make_job(write_set={"paths": []})) is None

    def test_missing_command_is_missing_command(self) -> None:
        assert _classify_job(_make_job(command=[])) == "validation_missing_command"

    def test_command_with_empty_strings(self) -> None:
        assert _classify_job(_make_job(command=["echo", ""])) == "validation_missing_command"

    def test_command_not_a_list(self) -> None:
        assert _classify_job(_make_job(command="echo hello")) == "validation_missing_command"


# ============================================================================
# Test run_single_validation_job
# ============================================================================


class TestRunSingleValidationJob:
    """run_single_validation_job executes a job and captures evidence."""

    def test_successful_execution(self) -> None:
        result = run_single_validation_job(
            _make_job(command=["echo", "hello"]),
            project_dir=Path("/tmp"),
        )
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.duration_seconds > 0
        assert len(result.code_hash) == 64
        assert len(result.result_hash) == 64
        assert result.error is None
        assert result.timed_out is False

    def test_failing_command(self) -> None:
        result = run_single_validation_job(
            _make_job(command=["sh", "-c", "exit 3"]),
            project_dir=Path("/tmp"),
        )
        assert result.exit_code == 3
        assert result.error is None  # subprocess succeeded, just non-zero exit

    def test_timeout(self) -> None:
        result = run_single_validation_job(
            _make_job(command=["sleep", "5"], timeout_seconds=1),
            project_dir=Path("/tmp"),
        )
        assert result.timed_out is True
        assert result.error is not None
        assert "timed out" in result.error

    def test_missing_executable(self) -> None:
        result = run_single_validation_job(
            _make_job(command=["nonexistent_cmd_xyzzy"]),
            project_dir=Path("/tmp"),
        )
        assert result.exit_code != 0 or result.error is not None

    def test_evidence_fields_present(self) -> None:
        result = run_single_validation_job(
            _make_job(command=["echo", "test"]),
            project_dir=Path("/tmp"),
        )
        d = result.as_dict()
        for key in (
            "job_id", "command", "environment", "cwd", "exit_code",
            "stdout", "stderr", "duration_seconds", "code_hash",
            "result_hash", "timed_out", "error",
        ):
            assert key in d

    def test_resolves_project_dir_token(self) -> None:
        result = run_single_validation_job(
            _make_job(command=["pwd"], cwd="/tmp"),
            project_dir=Path("/does/not/exist"),
        )
        # Should use the explicit cwd, not the project_dir token
        assert result.exit_code == 0


# ============================================================================
# Test run_validation_jobs (batch)
# ============================================================================


class TestRunValidationJobs:
    """run_validation_jobs executes batches of jobs."""

    def test_empty_list_returns_empty_report(self) -> None:
        report = run_validation_jobs([], project_dir=Path("/tmp"))
        assert report.results == []
        assert report.diagnostics == []
        assert report.admitted is True

    def test_single_valid_job(self) -> None:
        report = run_validation_jobs(
            [_make_job(command=["echo", "ok"])],
            project_dir=Path("/tmp"),
        )
        assert len(report.results) == 1
        assert report.results[0].exit_code == 0
        assert report.admitted is True

    def test_mutating_job_rejected(self) -> None:
        report = run_validation_jobs(
            [_make_job(expected_output_paths=["out.txt"])],
            project_dir=Path("/tmp"),
        )
        assert len(report.results) == 0
        assert len(report.diagnostics) == 1
        assert report.diagnostics[0]["code"] == "validation_mutating"
        assert report.admitted is False

    def test_missing_command_job_rejected(self) -> None:
        report = run_validation_jobs(
            [_make_job(command=[])],
            project_dir=Path("/tmp"),
        )
        assert len(report.diagnostics) == 1
        assert report.diagnostics[0]["code"] == "validation_missing_command"
        assert report.admitted is False

    def test_non_dict_entry_produces_diagnostic(self) -> None:
        report = run_validation_jobs(["not a dict"], project_dir=Path("/tmp"))
        assert len(report.diagnostics) >= 1
        assert any(d["code"] == "validation_ambiguous" for d in report.diagnostics)
        assert report.admitted is False

    def test_non_list_compiled_jobs(self) -> None:
        report = run_validation_jobs("not a list", project_dir=Path("/tmp"))  # type: ignore[arg-type]
        assert len(report.diagnostics) == 1
        assert report.diagnostics[0]["code"] == "validation_unavailable"
        assert report.admitted is False

    def test_mixed_valid_and_invalid(self) -> None:
        report = run_validation_jobs(
            [
                _make_job(id="vj-ok", command=["echo", "ok"]),
                _make_job(id="vj-bad", expected_output_paths=["out.txt"]),
            ],
            project_dir=Path("/tmp"),
        )
        assert len(report.results) == 1
        assert report.results[0].job_id == "vj-ok"
        assert len(report.diagnostics) == 1
        assert report.admitted is False


# ============================================================================
# Test ValidationRunReport
# ============================================================================


class TestValidationRunReport:
    """ValidationRunReport serialization."""

    def test_as_dict_empty(self) -> None:
        report = ValidationRunReport()
        d = report.as_dict()
        assert d == {"results": [], "diagnostics": [], "admitted": True}

    def test_as_dict_with_result(self) -> None:
        result = ValidationJobResult(
            job_id="vj-1",
            command=["echo"],
            environment={},
            cwd="/tmp",
            exit_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.1,
            code_hash="abc123",
            result_hash="def456",
        )
        report = ValidationRunReport(results=[result])
        d = report.as_dict()
        assert len(d["results"]) == 1
        assert d["results"][0]["job_id"] == "vj-1"


# ============================================================================
# Test extract_compiled_validation_jobs
# ============================================================================


class TestExtractCompiledValidationJobs:
    """extract_compiled_validation_jobs reads from finalize_data."""

    def test_extracts_from_graph_report(self) -> None:
        data = {
            "graph_report": {
                "validation_compilation": {
                    "validation_jobs": [
                        {"id": "vj-1", "command": ["echo"]},
                    ]
                }
            }
        }
        jobs = extract_compiled_validation_jobs(data)
        assert len(jobs) == 1
        assert jobs[0]["id"] == "vj-1"

    def test_no_graph_report_returns_empty(self) -> None:
        assert extract_compiled_validation_jobs({}) == []

    def test_graph_report_not_dict(self) -> None:
        assert extract_compiled_validation_jobs({"graph_report": "not dict"}) == []

    def test_no_validation_compilation(self) -> None:
        assert extract_compiled_validation_jobs({"graph_report": {}}) == []

    def test_validation_jobs_not_list(self) -> None:
        data = {
            "graph_report": {
                "validation_compilation": {
                    "validation_jobs": "not a list"
                }
            }
        }
        assert extract_compiled_validation_jobs(data) == []

    def test_filters_non_dict_entries(self) -> None:
        data = {
            "graph_report": {
                "validation_compilation": {
                    "validation_jobs": [
                        {"id": "vj-1", "command": ["echo"]},
                        "not a dict",
                        {"id": "vj-2", "command": ["ls"]},
                    ]
                }
            }
        }
        jobs = extract_compiled_validation_jobs(data)
        assert len(jobs) == 2
        assert jobs[0]["id"] == "vj-1"
        assert jobs[1]["id"] == "vj-2"
