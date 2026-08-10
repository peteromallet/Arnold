"""Tests for worker-launch preflight checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from arnold_pipelines.megaplan.execute.preflight import (
    PreflightCheck,
    PreflightFailureKind,
    PreflightReport,
    check_dirty_checkout,
    check_divergent_checkout,
    check_editable_install_refs,
    check_import_leakage,
    check_install_revision,
    check_revision_consistency,
    check_source_revision,
    run_worker_preflight,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_check(kind: str, passed: bool, detail: str = "", evidence: dict | None = None) -> PreflightCheck:
    return PreflightCheck(kind=kind, passed=passed, detail=detail, evidence=evidence or {})


# ---------------------------------------------------------------------------
# PreflightCheck & PreflightReport
# ---------------------------------------------------------------------------


class TestPreflightCheck:
    def test_check_defaults(self) -> None:
        check = PreflightCheck(kind="test", passed=True)
        assert check.kind == "test"
        assert check.passed is True
        assert check.detail == ""
        assert check.evidence == {}

    def test_check_with_evidence(self) -> None:
        check = PreflightCheck(
            kind="dirty_checkout",
            passed=False,
            detail="3 uncommitted files",
            evidence={"dirty_count": 3},
        )
        assert check.evidence["dirty_count"] == 3

    def test_check_immutable(self) -> None:
        check = PreflightCheck(kind="test", passed=True, evidence={"key": "value"})
        with pytest.raises(Exception):
            check.passed = False  # type: ignore[misc]


class TestPreflightReport:
    def test_passed_report(self) -> None:
        checks = (_make_check("dirty_checkout", True), _make_check("divergent_checkout", True))
        report = PreflightReport(passed=True, checks=checks, summary="All good")
        assert report.passed is True
        assert len(report.checks) == 2
        assert report.summary == "All good"

    def test_failed_report(self) -> None:
        checks = (
            _make_check("dirty_checkout", True),
            _make_check("divergent_checkout", False, "diverged"),
        )
        report = PreflightReport(passed=False, checks=checks, summary="One failure")
        assert report.passed is False

    def test_as_dict(self) -> None:
        checks = (_make_check("dirty_checkout", True),)
        report = PreflightReport(passed=True, checks=checks, summary="ok")
        d = report.as_dict()
        assert d["passed"] is True
        assert len(d["checks"]) == 1
        assert d["checks"][0]["kind"] == "dirty_checkout"
        assert d["summary"] == "ok"

    def test_failed_as_dict(self) -> None:
        checks = (
            _make_check("dirty_checkout", False, "dirty", {"count": 5}),
        )
        report = PreflightReport(passed=False, checks=checks)
        d = report.as_dict()
        assert d["passed"] is False
        assert d["checks"][0]["evidence"]["count"] == 5


# ---------------------------------------------------------------------------
# check_dirty_checkout
# ---------------------------------------------------------------------------


class TestCheckDirtyCheckout:
    def test_clean_tree(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        result = check_dirty_checkout(tmp_path)
        assert result.passed is True
        assert result.kind == PreflightFailureKind.DIRTY_CHECKOUT

    def test_dirty_tree(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "new_file.txt").write_text("uncommitted")
        result = check_dirty_checkout(tmp_path)
        assert result.passed is False
        assert result.kind == PreflightFailureKind.DIRTY_CHECKOUT
        assert result.evidence["dirty_count"] >= 1

    def test_non_git_directory(self, tmp_path: Path) -> None:
        result = check_dirty_checkout(tmp_path)
        assert result.passed is False
        assert result.kind == PreflightFailureKind.GIT_UNAVAILABLE

    def test_dirty_with_staged_changes(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "staged.txt").write_text("staged")
        subprocess.run(["git", "add", "staged.txt"], cwd=tmp_path, check=True)
        result = check_dirty_checkout(tmp_path)
        assert result.passed is False


# ---------------------------------------------------------------------------
# check_divergent_checkout
# ---------------------------------------------------------------------------


class TestCheckDivergentCheckout:
    def test_no_upstream(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        result = check_divergent_checkout(tmp_path)
        # No upstream -> passes (can't diverge from nothing)
        assert result.passed is True
        assert result.kind == PreflightFailureKind.DIVERGENT_CHECKOUT

    def test_non_git_directory(self, tmp_path: Path) -> None:
        result = check_divergent_checkout(tmp_path)
        assert result.passed is True  # Non-git passes (soft check)

    def test_upstream_not_configured_is_ok(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        result = check_divergent_checkout(tmp_path)
        assert result.passed is True


# ---------------------------------------------------------------------------
# check_editable_install_refs
# ---------------------------------------------------------------------------


class TestCheckEditableInstallRefs:
    def test_no_editable_installs(self, tmp_path: Path) -> None:
        # Mock pip list to return empty
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result("[]", "", 0)
            result = check_editable_install_refs(tmp_path)
            assert result.passed is True

    def test_editable_install_outside_project(self, tmp_path: Path) -> None:
        pkg_json = json.dumps([
            {"name": "arnold", "editable_project_location": "/other/path"}
        ])
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result(pkg_json, "", 0)
            result = check_editable_install_refs(tmp_path)
            assert result.passed is False
            assert result.kind == PreflightFailureKind.INVALID_EDITABLE_INSTALL
            assert "arnold" in result.detail

    def test_editable_install_inside_project(self, tmp_path: Path) -> None:
        pkg_json = json.dumps([
            {"name": "arnold", "editable_project_location": str(tmp_path.resolve())}
        ])
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result(pkg_json, "", 0)
            result = check_editable_install_refs(tmp_path)
            assert result.passed is True

    def test_pip_failure_is_non_fatal(self, tmp_path: Path) -> None:
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result("", "pip error", 1)
            result = check_editable_install_refs(tmp_path)
            assert result.passed is True

    def test_subprocess_timeout(self, tmp_path: Path) -> None:
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pip", 30)):
            result = check_editable_install_refs(tmp_path)
            assert result.passed is False
            assert result.kind == PreflightFailureKind.INVALID_EDITABLE_INSTALL

    def test_invalid_json_from_pip(self, tmp_path: Path) -> None:
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result("not json", "", 0)
            result = check_editable_install_refs(tmp_path)
            assert result.passed is True  # Non-fatal


# ---------------------------------------------------------------------------
# check_import_leakage
# ---------------------------------------------------------------------------


class TestCheckImportLeakage:
    def test_no_leakage(self, tmp_path: Path) -> None:
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result('{"leaked": []}', "", 0)
            result = check_import_leakage(tmp_path)
            assert result.passed is True

    def test_leakage_detected(self, tmp_path: Path) -> None:
        leaked = [{"name": "bad_module", "path": "/usr/local/bad.py"}]
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result(
                json.dumps({"leaked": leaked}), "", 0
            )
            result = check_import_leakage(tmp_path)
            assert result.passed is False
            assert result.kind == PreflightFailureKind.IMPORT_LEAKAGE
            assert len(result.evidence["leaked_modules"]) == 1

    def test_subprocess_timeout(self, tmp_path: Path) -> None:
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("python", 30)):
            result = check_import_leakage(tmp_path)
            assert result.passed is False
            assert result.kind == PreflightFailureKind.IMPORT_LEAKAGE

    def test_unparseable_output_is_ok(self, tmp_path: Path) -> None:
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result("garbage", "", 0)
            result = check_import_leakage(tmp_path)
            assert result.passed is True


# ---------------------------------------------------------------------------
# check_source_revision
# ---------------------------------------------------------------------------


class TestCheckSourceRevision:
    def test_valid_repo(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        result = check_source_revision(tmp_path)
        assert result.passed is True
        assert "head" in result.evidence
        assert len(result.evidence["head"]) == 40  # Full SHA

    def test_non_git_directory(self, tmp_path: Path) -> None:
        result = check_source_revision(tmp_path)
        assert result.passed is False
        assert result.kind == PreflightFailureKind.SOURCE_REVISION_MISMATCH


# ---------------------------------------------------------------------------
# check_install_revision
# ---------------------------------------------------------------------------


class TestCheckInstallRevision:
    def test_package_installed(self, tmp_path: Path) -> None:
        output = "Name: arnold\nVersion: 1.0.0\nLocation: /some/path\n"
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result(output, "", 0)
            result = check_install_revision(tmp_path)
            assert result.passed is True
            assert result.evidence["version"] == "1.0.0"
            assert result.evidence["location"] == "/some/path"

    def test_package_not_installed(self, tmp_path: Path) -> None:
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = _mock_pip_result("", "not found", 1)
            result = check_install_revision(tmp_path)
            assert result.passed is False
            assert result.kind == PreflightFailureKind.INSTALL_REVISION_MISMATCH

    def test_subprocess_timeout(self, tmp_path: Path) -> None:
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pip", 30)):
            result = check_install_revision(tmp_path)
            assert result.passed is False


# ---------------------------------------------------------------------------
# check_revision_consistency
# ---------------------------------------------------------------------------


class TestCheckRevisionConsistency:
    def test_both_pass(self) -> None:
        source = _make_check("source", True, evidence={"head": "abc123"})
        install = _make_check("install", True, evidence={"version": "1.0"})
        result = check_revision_consistency(source, install)
        assert result.passed is True

    def test_source_fails(self) -> None:
        source = _make_check("source", False, "no git")
        install = _make_check("install", True)
        result = check_revision_consistency(source, install)
        assert result.passed is False

    def test_install_fails(self) -> None:
        source = _make_check("source", True, evidence={"head": "abc"})
        install = _make_check("install", False, "not installed")
        result = check_revision_consistency(source, install)
        assert result.passed is False

    def test_evidence_passed_through(self) -> None:
        source = _make_check("source", True, evidence={"head": "abc123"})
        install = _make_check("install", True, evidence={"version": "1.0", "location": "/path"})
        result = check_revision_consistency(source, install)
        assert result.evidence["source_head"] == "abc123"
        assert result.evidence["install_version"] == "1.0"


# ---------------------------------------------------------------------------
# run_worker_preflight (integration)
# ---------------------------------------------------------------------------


class TestRunWorkerPreflight:
    def test_all_pass_in_clean_repo(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        with mock.patch(
            "arnold_pipelines.megaplan.execute.preflight.check_editable_install_refs",
            return_value=_make_check(PreflightFailureKind.INVALID_EDITABLE_INSTALL, True),
        ), mock.patch(
            "arnold_pipelines.megaplan.execute.preflight.check_import_leakage",
            return_value=_make_check(PreflightFailureKind.IMPORT_LEAKAGE, True),
        ), mock.patch(
            "arnold_pipelines.megaplan.execute.preflight.check_install_revision",
            return_value=_make_check(PreflightFailureKind.INSTALL_REVISION_MISMATCH, True),
        ):
            report = run_worker_preflight(tmp_path)
            assert report.passed is True
            assert len(report.checks) == 7

    def test_dirty_checkout_fails_strict(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        # Make a dirty file
        (tmp_path / "dirty.txt").write_text("uncommitted")
        report = run_worker_preflight(tmp_path)
        assert report.passed is False
        failures = [c for c in report.checks if not c.passed]
        assert any(c.kind == PreflightFailureKind.DIRTY_CHECKOUT for c in failures)

    def test_non_strict_allows_non_git_failures(self, tmp_path: Path) -> None:
        # Non-git directory - only git checks block in non-strict
        report = run_worker_preflight(tmp_path, strict=False)
        # Non-strict: only dirty/divergent are hard blockers
        # dirty fails (git unavailable), divergent passes
        assert report.passed is False  # dirty still blocks

    def test_preflight_report_as_dict(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        with mock.patch(
            "arnold_pipelines.megaplan.execute.preflight.check_editable_install_refs",
            return_value=_make_check(PreflightFailureKind.INVALID_EDITABLE_INSTALL, True),
        ), mock.patch(
            "arnold_pipelines.megaplan.execute.preflight.check_import_leakage",
            return_value=_make_check(PreflightFailureKind.IMPORT_LEAKAGE, True),
        ), mock.patch(
            "arnold_pipelines.megaplan.execute.preflight.check_install_revision",
            return_value=_make_check(PreflightFailureKind.INSTALL_REVISION_MISMATCH, True),
        ):
            report = run_worker_preflight(tmp_path)
            d = report.as_dict()
            assert isinstance(d, dict)
            assert "passed" in d
            assert "checks" in d
            assert "summary" in d

    def test_all_checks_present(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        with mock.patch(
            "arnold_pipelines.megaplan.execute.preflight.check_editable_install_refs",
            return_value=_make_check(PreflightFailureKind.INVALID_EDITABLE_INSTALL, True),
        ), mock.patch(
            "arnold_pipelines.megaplan.execute.preflight.check_import_leakage",
            return_value=_make_check(PreflightFailureKind.IMPORT_LEAKAGE, True),
        ), mock.patch(
            "arnold_pipelines.megaplan.execute.preflight.check_install_revision",
            return_value=_make_check(PreflightFailureKind.INSTALL_REVISION_MISMATCH, True),
        ):
            report = run_worker_preflight(tmp_path)
            kinds = {check.kind for check in report.checks}
            expected = {
                PreflightFailureKind.DIRTY_CHECKOUT,
                PreflightFailureKind.DIVERGENT_CHECKOUT,
                PreflightFailureKind.INVALID_EDITABLE_INSTALL,
                PreflightFailureKind.IMPORT_LEAKAGE,
                PreflightFailureKind.SOURCE_REVISION_MISMATCH,
                PreflightFailureKind.INSTALL_REVISION_MISMATCH,
                PreflightFailureKind.RUNTIME_REVISION_MISMATCH,
            }
            assert kinds == expected

    def test_failure_summary_includes_detail(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / "dirty.txt").write_text("x")
        report = run_worker_preflight(tmp_path)
        assert not report.passed
        assert "dirty" in report.summary.lower()


# ---------------------------------------------------------------------------
# PreflightFailureKind constants
# ---------------------------------------------------------------------------


class TestPreflightFailureKind:
    def test_constants_defined(self) -> None:
        assert PreflightFailureKind.DIRTY_CHECKOUT == "dirty_checkout"
        assert PreflightFailureKind.DIVERGENT_CHECKOUT == "divergent_checkout"
        assert PreflightFailureKind.INVALID_EDITABLE_INSTALL == "invalid_editable_install"
        assert PreflightFailureKind.IMPORT_LEAKAGE == "import_leakage"
        assert PreflightFailureKind.SOURCE_REVISION_MISMATCH == "source_revision_mismatch"
        assert PreflightFailureKind.INSTALL_REVISION_MISMATCH == "install_revision_mismatch"
        assert PreflightFailureKind.RUNTIME_REVISION_MISMATCH == "runtime_revision_mismatch"
        assert PreflightFailureKind.GIT_UNAVAILABLE == "git_unavailable"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    """Initialize a minimal git repo at *path*."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path, check=True, capture_output=True,
    )
    (path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def _mock_pip_result(stdout: str, stderr: str, returncode: int) -> mock.MagicMock:
    """Build a mock subprocess.CompletedProcess."""
    result = mock.MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result
