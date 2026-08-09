"""Tests for validation_compiler — deterministic no-file validation job compilation."""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.orchestration.validation_compiler import (
    VALIDATION_AMBIGUOUS,
    VALIDATION_MISSING_COMMAND,
    VALIDATION_MUTATING,
    ValidationDiagnostic,
    compile_validation_jobs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Sentinel so callers can explicitly pass an empty list for command or paths.
_EMPTY: list = []


def _vj(
    job_id: str = "VJ1",
    *,
    command: list[str] | None = None,
    environment: dict[str, str] | None = None,
    cwd: str = "${project_dir}",
    timeout_seconds: int = 120,
    expected_output_paths: list[str] | None = None,
    content_addressed_evidence: bool = True,
    extra: dict | None = None,
) -> dict:
    """Build a minimal well-formed validation job dict.

    Pass ``command=_EMPTY`` or ``expected_output_paths=_EMPTY`` to
    explicitly set an empty list (``None`` triggers the default).
    """
    _cmd: list[str]
    if command is None:
        _cmd = ["pytest", "tests/test_x.py", "-q"]
    else:
        _cmd = list(command)

    _paths: list[str]
    if expected_output_paths is None:
        _paths = []
    else:
        _paths = list(expected_output_paths)

    job: dict = {
        "id": job_id,
        "command": _cmd,
        "environment": environment if environment is not None else {},
        "cwd": cwd,
        "timeout_seconds": timeout_seconds,
        "expected_output_paths": _paths,
        "content_addressed_evidence": content_addressed_evidence,
    }
    if extra:
        job.update(extra)
    return job


def _payload(jobs: list[dict] | None = None) -> dict:
    return {"validation_jobs": jobs if jobs is not None else []}


def _compile(jobs: list[dict] | None = None) -> dict:
    return compile_validation_jobs(_payload(jobs))


def _codes(report: dict) -> set[str]:
    return {d["code"] for d in report["diagnostics"]}


# ---------------------------------------------------------------------------
# Successful compilation
# ---------------------------------------------------------------------------


class TestSuccessfulCompilation:
    """Well-formed no-file deterministic jobs are compiled."""

    def test_single_valid_job_is_compiled(self) -> None:
        report = _compile([_vj("VJ1")])
        assert report["admitted"] is True
        assert len(report["validation_jobs"]) == 1
        assert report["validation_jobs"][0]["id"] == "VJ1"

    def test_multiple_valid_jobs_are_compiled(self) -> None:
        report = _compile([
            _vj("VJ1", command=["pytest", "tests/a.py"]),
            _vj("VJ2", command=["pytest", "tests/b.py"]),
        ])
        assert report["admitted"] is True
        assert len(report["validation_jobs"]) == 2

    def test_normalizes_fields_in_output(self) -> None:
        job = _vj("VJ1", command=["pytest", "tests/x.py"], timeout_seconds=60,
                expected_output_paths=[], content_addressed_evidence=False)
        report = _compile([job])
        compiled = report["validation_jobs"][0]
        assert compiled["id"] == "VJ1"
        assert compiled["command"] == ["pytest", "tests/x.py"]
        assert compiled["environment"] == {}
        assert compiled["cwd"] == "${project_dir}"
        assert compiled["timeout_seconds"] == 60
        assert compiled["expected_output_paths"] == []
        assert compiled["content_addressed_evidence"] is False

    def test_empty_validation_jobs_list_is_admitted(self) -> None:
        report = _compile([])
        assert report["admitted"] is True
        assert report["validation_jobs"] == []
        assert report["diagnostics"] == []

    def test_environment_is_normalized_to_strings(self) -> None:
        job = _vj("VJ1", environment={"KEY": 42})  # type: ignore[dict-item]
        report = _compile([job])
        assert report["admitted"] is True
        assert report["validation_jobs"][0]["environment"] == {"KEY": "42"}

    def test_default_cwd_when_empty(self) -> None:
        job = _vj("VJ1", cwd="   ")
        report = _compile([job])
        assert report["admitted"] is True
        assert report["validation_jobs"][0]["cwd"] == "${project_dir}"

    def test_deterministic_output(self) -> None:
        jobs = [
            _vj("VJ1", command=["pytest", "tests/a.py"]),
            _vj("VJ2", command=["pytest", "tests/b.py"]),
        ]
        report_a = compile_validation_jobs(_payload(jobs))
        report_b = compile_validation_jobs(_payload(jobs))
        assert report_a == report_b

    def test_command_with_flags_is_accepted(self) -> None:
        job = _vj("VJ1", command=["pytest", "-q", "--tb=short", "tests/x.py"])
        report = _compile([job])
        assert report["admitted"] is True

    def test_command_with_interpreter_is_accepted(self) -> None:
        job = _vj("VJ1", command=["python", "-m", "pytest", "tests/x.py"])
        report = _compile([job])
        assert report["admitted"] is True


# ---------------------------------------------------------------------------
# Missing / ambiguous command rejection
# ---------------------------------------------------------------------------


class TestCommandRejection:
    """Jobs with missing, empty, or ambiguous commands are rejected."""

    def test_missing_command_field_rejected(self) -> None:
        job = _vj("VJ1")
        del job["command"]
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)
        assert report["admitted"] is False

    def test_null_command_rejected(self) -> None:
        job = _vj("VJ1")
        job["command"] = None  # type: ignore[assignment]
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_empty_command_list_rejected(self) -> None:
        job = _vj("VJ1", command=_EMPTY)
        report = _compile([job])
        assert VALIDATION_MISSING_COMMAND in _codes(report)

    def test_command_with_empty_string_rejected(self) -> None:
        job = _vj("VJ1", command=["pytest", "  "])
        report = _compile([job])
        assert VALIDATION_MISSING_COMMAND in _codes(report)

    def test_command_is_string_not_list_rejected(self) -> None:
        job = _vj("VJ1")
        job["command"] = "pytest tests/x.py"  # type: ignore[assignment]
        report = _compile([job])
        assert VALIDATION_MISSING_COMMAND in _codes(report)

    def test_ellipsis_placeholder_rejected(self) -> None:
        job = _vj("VJ1", command=["...pytest", "tests/x.py"])
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_dollar_placeholder_rejected(self) -> None:
        job = _vj("VJ1", command=["${CMD}", "tests/x.py"])
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_template_placeholder_rejected(self) -> None:
        job = _vj("VJ1", command=["{{ run_test }}", "tests/x.py"])
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_angle_bracket_placeholder_rejected(self) -> None:
        job = _vj("VJ1", command=["<test_runner>", "tests/x.py"])
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_question_mark_placeholder_rejected(self) -> None:
        job = _vj("VJ1", command=["???", "tests/x.py"])
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_prose_instruction_rejected(self) -> None:
        job = _vj("VJ1", command=["Run the test suite and report results"])
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)


# ---------------------------------------------------------------------------
# Missing required fields rejection
# ---------------------------------------------------------------------------


class TestMissingFields:
    """Jobs missing required fields are rejected as ambiguous."""

    @pytest.mark.parametrize("field", [
        "id", "command", "environment", "cwd",
        "timeout_seconds", "expected_output_paths", "content_addressed_evidence",
    ])
    def test_missing_required_field_is_ambiguous(self, field: str) -> None:
        job = _vj("VJ1")
        del job[field]
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    @pytest.mark.parametrize("field", [
        "environment", "cwd", "expected_output_paths", "content_addressed_evidence",
    ])
    def test_null_required_field_is_ambiguous(self, field: str) -> None:
        job = _vj("VJ1")
        job[field] = None  # type: ignore[assignment]
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_missing_multiple_fields_reports_all(self) -> None:
        job: dict = {"id": "VJ1"}  # only id present
        report = compile_validation_jobs({"validation_jobs": [job]})
        assert VALIDATION_AMBIGUOUS in _codes(report)
        assert len(report["diagnostics"]) == 1
        diag = report["diagnostics"][0]
        assert "command" in diag["message"]
        assert "environment" in diag["message"]


# ---------------------------------------------------------------------------
# Mutating validation rejection
# ---------------------------------------------------------------------------


class TestMutatingRejection:
    """Jobs that produce file outputs are rejected as mutating."""

    def test_non_empty_expected_output_paths_rejected(self) -> None:
        job = _vj("VJ1", expected_output_paths=["out/results.json"])
        report = _compile([job])
        assert VALIDATION_MUTATING in _codes(report)

    def test_write_set_with_paths_rejected(self) -> None:
        job = _vj("VJ1", extra={"write_set": {"paths": ["out/report.txt"], "complete": True}})
        report = _compile([job])
        assert VALIDATION_MUTATING in _codes(report)

    def test_empty_write_set_paths_not_mutating(self) -> None:
        job = _vj("VJ1", extra={"write_set": {"paths": [], "complete": True}})
        report = _compile([job])
        assert report["admitted"] is True
        assert VALIDATION_MUTATING not in _codes(report)

    def test_no_write_set_not_mutating(self) -> None:
        job = _vj("VJ1")
        report = _compile([job])
        assert report["admitted"] is True
        assert VALIDATION_MUTATING not in _codes(report)


# ---------------------------------------------------------------------------
# Timeout validation
# ---------------------------------------------------------------------------


class TestTimeoutValidation:
    """Jobs must have a positive integer timeout_seconds."""

    def test_zero_timeout_rejected(self) -> None:
        job = _vj("VJ1", timeout_seconds=0)
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_negative_timeout_rejected(self) -> None:
        job = _vj("VJ1", timeout_seconds=-1)
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_float_timeout_coerced(self) -> None:
        job = _vj("VJ1")
        job["timeout_seconds"] = 90.0  # type: ignore[assignment]
        report = _compile([job])
        # 90.0 is not an int, but should be coercible
        assert report["admitted"] is True
        assert report["validation_jobs"][0]["timeout_seconds"] == 90

    def test_boolean_timeout_rejected(self) -> None:
        job = _vj("VJ1")
        job["timeout_seconds"] = True  # type: ignore[assignment]
        report = _compile([job])
        assert VALIDATION_AMBIGUOUS in _codes(report)


# ---------------------------------------------------------------------------
# Non-list / non-dict validation_jobs
# ---------------------------------------------------------------------------


class TestPayloadShape:
    """Malformed validation_jobs payloads are rejected cleanly."""

    def test_missing_validation_jobs_payload(self) -> None:
        report = compile_validation_jobs({})
        assert VALIDATION_AMBIGUOUS in _codes(report)
        assert report["admitted"] is False

    def test_null_validation_jobs_payload(self) -> None:
        report = compile_validation_jobs({"validation_jobs": None})
        assert VALIDATION_AMBIGUOUS in _codes(report)
        assert report["admitted"] is False

    def test_string_validation_jobs_payload(self) -> None:
        report = compile_validation_jobs({"validation_jobs": "not-a-list"})
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_non_dict_job_entry_rejected(self) -> None:
        report = compile_validation_jobs({"validation_jobs": ["not-a-dict"]})
        assert VALIDATION_AMBIGUOUS in _codes(report)
        assert "index 0" in report["diagnostics"][0]["message"]

    def test_mixed_valid_and_invalid_jobs(self) -> None:
        jobs: list = [
            _vj("VJ1", command=["pytest", "tests/a.py"]),
            "not-a-dict",
            _vj("VJ2", command=["pytest", "tests/b.py"], expected_output_paths=["out.json"]),
        ]
        report = compile_validation_jobs({"validation_jobs": jobs})
        assert report["admitted"] is False
        assert len(report["validation_jobs"]) == 1  # only VJ1 compiled
        assert report["validation_jobs"][0]["id"] == "VJ1"
        assert len(report["diagnostics"]) == 2  # string entry + mutating


# ---------------------------------------------------------------------------
# Diagnostic structure
# ---------------------------------------------------------------------------


class TestDiagnosticStructure:
    """ValidationDiagnostic has the correct shape."""

    def test_diagnostic_as_dict_includes_code_and_message(self) -> None:
        diag = ValidationDiagnostic(VALIDATION_AMBIGUOUS, "test message", "VJ1")
        d = diag.as_dict()
        assert d["code"] == VALIDATION_AMBIGUOUS
        assert d["message"] == "test message"
        assert d["job_id"] == "VJ1"

    def test_diagnostic_as_dict_omits_none_job_id(self) -> None:
        diag = ValidationDiagnostic(VALIDATION_AMBIGUOUS, "test message")
        d = diag.as_dict()
        assert "job_id" not in d


# ---------------------------------------------------------------------------
# Content-addressed evidence flag
# ---------------------------------------------------------------------------


class TestContentAddressedEvidence:
    """The content_addressed_evidence flag is preserved."""

    def test_true_preserved(self) -> None:
        job = _vj("VJ1", content_addressed_evidence=True)
        report = _compile([job])
        assert report["validation_jobs"][0]["content_addressed_evidence"] is True

    def test_false_preserved(self) -> None:
        job = _vj("VJ1", content_addressed_evidence=False)
        report = _compile([job])
        assert report["validation_jobs"][0]["content_addressed_evidence"] is False


# ---------------------------------------------------------------------------
# Id handling
# ---------------------------------------------------------------------------


class TestIdHandling:
    """Job ids are normalized correctly."""

    def test_missing_id_gets_synthetic(self) -> None:
        job = _vj("VJ1")
        del job["id"]
        report = _compile([job])
        # Falls back to synthetic id, but missing required field rejects
        assert VALIDATION_AMBIGUOUS in _codes(report)

    def test_non_string_id_is_accepted_and_stringified(self) -> None:
        job = _vj("VJ1")
        job["id"] = 42  # type: ignore[assignment]
        report = _compile([job])
        assert report["admitted"] is True
        assert report["validation_jobs"][0]["id"] == "42"
