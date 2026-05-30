"""Parsing tests for megaplan.orchestration.suite_runner.

Verifies:
- Exit-code mapping: 0→passed, 1→failed, 2→runner_error, 5→not_applicable
- Parametrized nodeid parsing from FAILED/PASSED lines
- ``collections_parse_ok=False`` when collection lines are absent
- Code hash stable across reruns on unchanged tree
- git ls-tree path used (mock git)
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest import mock

import pytest

from megaplan.orchestration.suite_runner import (
    SuiteRunResult,
    _compute_code_hash,
    _parse_pytest_output,
    _run_collect_only,
    run_suite,
)


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

_EXIT_CODE_STATUS_MAP = [
    (0, "passed"),
    (1, "failed"),
    (2, "runner_error"),
    (5, "not_applicable"),
    (3, "runner_error"),    # arbitrary other → runner_error
    (137, "runner_error"),  # SIGKILL
    (-15, "runner_error"),  # SIGTERM
]


class TestExitCodeMapping:
    """Verify every exit code maps to the correct SuiteStatus."""

    @pytest.mark.parametrize("exit_code,expected_status", _EXIT_CODE_STATUS_MAP)
    def test_exit_code_maps_to_correct_status(
        self,
        tmp_path: Path,
        exit_code: int,
        expected_status: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fast path through run_suite by mocking the subprocess bits."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        # Mock spawn to return a fake proc that exits immediately with the
        # desired code.
        fake_proc = mock.MagicMock()
        fake_proc.poll.return_value = None  # not dead yet on first poll
        fake_proc.wait.return_value = exit_code

        monkeypatch.setattr(
            "megaplan.orchestration.suite_runner.spawn",
            lambda *a, **kw: fake_proc,
        )
        # The collect-only fallback would fail in an empty tmp dir, so
        # provide stub IDs to prevent it from overriding the status.
        monkeypatch.setattr(
            "megaplan.orchestration.suite_runner._run_collect_only",
            lambda *a, **kw: ["tests/stub.py::test_stub"],
        )

        config = {
            "test_command": "pytest",
            "plan_dir": str(plan_dir),
        }

        deadline = time.monotonic() + 30.0
        result = run_suite(project_dir, config, phase="exit_test", deadline_seconds=deadline)

        assert result.status == expected_status, (
            f"exit_code={exit_code} → expected {expected_status}, got {result.status}"
        )
        assert result.exit_code == exit_code


# ---------------------------------------------------------------------------
# Parametrized nodeid parsing
# ---------------------------------------------------------------------------

class TestParametrizedNodeidParsing:
    """Verify parametrized suffixes like ``test_foo[a-1]`` are captured."""

    def test_parametrized_failure_nodeid(self) -> None:
        stdout = (
            "collected 4 items\n"
            "FAILED tests/test_params.py::test_foo[a-1] - AssertionError\n"
            "FAILED tests/test_params.py::test_foo[b-2] - ValueError\n"
            "PASSED tests/test_params.py::test_ok_one\n"
            "PASSED tests/test_params.py::test_ok_two\n"
            "2 failed, 2 passed\n"
        )
        parsed = _parse_pytest_output(stdout)
        assert parsed["failures"] == [
            "tests/test_params.py::test_foo[a-1]",
            "tests/test_params.py::test_foo[b-2]",
        ]
        assert len(parsed["passes"]) == 2

    def test_parametrized_pass_nodeid(self) -> None:
        stdout = (
            "collected 3 items\n"
            "PASSED tests/test_params.py::test_bar[x-y]\n"
            "PASSED tests/test_params.py::test_bar[z-w]\n"
            "PASSED tests/test_params.py::test_bar[extra]\n"
            "3 passed\n"
        )
        parsed = _parse_pytest_output(stdout)
        assert len(parsed["passes"]) == 3
        assert "tests/test_params.py::test_bar[x-y]" in parsed["passes"]
        assert "tests/test_params.py::test_bar[z-w]" in parsed["passes"]
        assert parsed["failures"] == []

    def test_mixed_parametrized_and_plain(self) -> None:
        stdout = (
            "collected 5 items\n"
            "FAILED tests/test_mix.py::test_param[0-True]\n"
            "PASSED tests/test_mix.py::test_plain\n"
            "PASSED tests/test_mix.py::test_param[1-False]\n"
            "PASSED tests/test_mix.py::test_param[2-False]\n"
            "PASSED tests/test_mix.py::test_param[3-False]\n"
            "1 failed, 4 passed\n"
        )
        parsed = _parse_pytest_output(stdout)
        assert parsed["failures"] == ["tests/test_mix.py::test_param[0-True]"]
        assert len(parsed["passes"]) == 4
        assert "tests/test_mix.py::test_plain" in parsed["passes"]
        assert "tests/test_mix.py::test_param[1-False]" in parsed["passes"]

    def test_collected_ids_is_union_of_all_parsed_nodeids(self) -> None:
        """collected_ids must be the deduplicated union of failures + passes."""
        stdout = (
            "collected 3 items\n"
            "FAILED tests/test_a.py::test_x\n"
            "PASSED tests/test_a.py::test_y\n"
            "PASSED tests/test_a.py::test_z\n"
            "1 failed, 2 passed\n"
        )
        parsed = _parse_pytest_output(stdout)
        assert len(parsed["collected_ids"]) == 3
        assert "tests/test_a.py::test_x" in parsed["collected_ids"]
        assert "tests/test_a.py::test_y" in parsed["collected_ids"]

    def test_collected_ids_empty_when_no_parsed_lines(self) -> None:
        """collected_ids stays empty when no stable nodeid lines are present."""
        stdout = "collected 5 items\n5 passed in 0.10s\n"
        parsed = _parse_pytest_output(stdout)
        assert parsed["collected_ids"] == []
        assert parsed["passes"] == []
        assert parsed["parse_ok"] is False

    def test_summary_count_mismatch_fails_loud(self) -> None:
        stdout = (
            "collected 2 items\n"
            "PASSED tests/test_a.py::test_one\n"
            "2 passed\n"
        )
        parsed = _parse_pytest_output(stdout)
        assert parsed["parse_ok"] is False
        assert "<test-" not in str(parsed)

    def test_nodeid_parsing_avoids_substring_approach(self) -> None:
        """Ensure the old endswith(' FAILED') substring approach is NOT used.

        The old approach at finalize.py:584-586 would misparse lines where
        ' FAILED' appears as part of a test name.  Our regex approach
        requires ^FAILED at the start of the line, so a test named
        ``test_not_FAILED_check`` would not be captured as a failure.
        """
        stdout = (
            "collected 2 items\n"
            "FAILED tests/test_real.py::test_actual_fail\n"
            "PASSED tests/test_real.py::test_not_FAILED_check\n"
            "1 failed, 1 passed\n"
        )
        parsed = _parse_pytest_output(stdout)
        # Only the real FAILED line should be captured
        assert parsed["failures"] == ["tests/test_real.py::test_actual_fail"]
        assert "tests/test_real.py::test_not_FAILED_check" in parsed["passes"]


# ---------------------------------------------------------------------------
# collections_parse_ok=False when collection lines are absent
# ---------------------------------------------------------------------------

class TestCollectionsParseOkFalse:
    """Verify the fallback path when no collection lines are parsed."""

    def test_collections_parse_ok_false_triggers_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When pytest output has no FAILED/PASSED lines AND exit_code != 5,
        collections_parse_ok becomes False and --collect-only is tried."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        # Simulate pytest exiting 0 with no nodeid lines (e.g. empty test run)
        fake_proc = mock.MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.wait.return_value = 0

        monkeypatch.setattr(
            "megaplan.orchestration.suite_runner.spawn",
            lambda *a, **kw: fake_proc,
        )

        # Mock _run_collect_only to return some ids
        collected = [
            "tests/test_a.py::test_one",
            "tests/test_a.py::test_two",
        ]
        monkeypatch.setattr(
            "megaplan.orchestration.suite_runner._run_collect_only",
            lambda *a, **kw: collected,
        )

        config = {
            "test_command": "pytest",
            "plan_dir": str(plan_dir),
        }
        deadline = time.monotonic() + 30.0
        result = run_suite(project_dir, config, phase="parse_test", deadline_seconds=deadline)

        # The log will be empty (no real output), so parsing yields zero ids
        assert result.collections_parse_ok is True  # fallback succeeded
        assert result.collected_ids == collected

    def test_collections_parse_ok_false_when_fallback_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When both the main parse and --collect-only fail, status is runner_error."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        fake_proc = mock.MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.wait.return_value = 0

        monkeypatch.setattr(
            "megaplan.orchestration.suite_runner.spawn",
            lambda *a, **kw: fake_proc,
        )
        # Fallback returns empty
        monkeypatch.setattr(
            "megaplan.orchestration.suite_runner._run_collect_only",
            lambda *a, **kw: [],
        )

        config = {
            "test_command": "pytest",
            "plan_dir": str(plan_dir),
        }
        deadline = time.monotonic() + 30.0
        result = run_suite(project_dir, config, phase="parse_test", deadline_seconds=deadline)

        assert result.status == "runner_error"
        assert result.collections_parse_ok is False
        assert result.collected_ids == []

    def test_no_fallback_when_exit_code_5(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When exit_code=5 (no tests collected), we skip the fallback entirely."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        fake_proc = mock.MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.wait.return_value = 5  # pytest exit code 5 = no tests

        monkeypatch.setattr(
            "megaplan.orchestration.suite_runner.spawn",
            lambda *a, **kw: fake_proc,
        )

        config = {
            "test_command": "pytest",
            "plan_dir": str(plan_dir),
        }
        deadline = time.monotonic() + 30.0
        result = run_suite(project_dir, config, phase="no_tests", deadline_seconds=deadline)

        # exit_code=5 → status='not_applicable', no fallback attempted
        assert result.status == "not_applicable"
        assert result.exit_code == 5


# ---------------------------------------------------------------------------
# Code hash stability
# ---------------------------------------------------------------------------

class TestCodeHashStability:
    """Verify code_hash is stable across reruns on an unchanged tree."""

    def test_code_hash_stable_across_reruns(self, tmp_path: Path) -> None:
        """Running _compute_code_hash twice on the same tree yields the same hash."""
        project_dir = tmp_path / "repo"
        project_dir.mkdir()

        # Create a git repo
        subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
        (project_dir / "a.py").write_text("print('a')")
        (project_dir / "b.py").write_text("print('b')")
        subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init", "--allow-empty"],
            cwd=project_dir,
            capture_output=True,
        )

        h1 = _compute_code_hash(project_dir)
        h2 = _compute_code_hash(project_dir)

        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_code_hash_changes_when_files_change(self, tmp_path: Path) -> None:
        """Adding a file to the repo should change the code hash."""
        project_dir = tmp_path / "repo"
        project_dir.mkdir()

        subprocess.run(["git", "init"], cwd=project_dir, capture_output=True)
        (project_dir / "a.py").write_text("print('a')")
        subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init", "--allow-empty"],
            cwd=project_dir,
            capture_output=True,
        )

        h1 = _compute_code_hash(project_dir)

        # Add a new file
        (project_dir / "b.py").write_text("print('b')")
        subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "add b"],
            cwd=project_dir,
            capture_output=True,
        )

        h2 = _compute_code_hash(project_dir)

        assert h1 != h2

    def test_non_git_code_hash_is_deterministic_and_content_based(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "plain"
        project_dir.mkdir()
        (project_dir / "pkg").mkdir()
        (project_dir / "pkg" / "a.py").write_text("print('a')\n", encoding="utf-8")
        (project_dir / "pkg" / "b.py").write_text("print('b')\n", encoding="utf-8")

        h1 = _compute_code_hash(project_dir, paths=["pkg"])
        h2 = _compute_code_hash(project_dir, paths=["pkg"])
        assert h1 == h2

        (project_dir / "pkg" / "a.py").write_text("print('changed')\n", encoding="utf-8")
        assert _compute_code_hash(project_dir, paths=["pkg"]) != h1


# ---------------------------------------------------------------------------
# git ls-tree path used (mock git)
# ---------------------------------------------------------------------------

class TestCodeHashPaths:
    """Verify that paths are passed to git ls-tree."""

    def test_ls_tree_receives_paths(self, tmp_path: Path) -> None:
        """When paths are provided, git ls-tree is called with those paths."""
        project_dir = tmp_path / "repo"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()  # fake git dir — no real repo needed

        paths = ["tests", "src"]

        with mock.patch("subprocess.run") as mock_run:
            # First call: git ls-tree succeeds
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout="100644 blob abc\ttests/test_x.py\n",
            )
            _compute_code_hash(project_dir, paths=paths)

            # Verify the git command was called with the paths
            git_calls = [
                c for c in mock_run.call_args_list
                if "ls-tree" in str(c.args[0]) if c.args
            ]
            assert len(git_calls) >= 1
            git_argv = git_calls[0].args[0]
            # Paths should appear after the '--' separator
            assert "tests" in git_argv
            assert "src" in git_argv
            # Verify git -C is used
            assert "-C" in git_argv or git_argv[0] == "git"

    def test_ls_tree_no_paths_defaults_to_dot(self, tmp_path: Path) -> None:
        """When paths is None, git ls-tree defaults to '.'."""
        project_dir = tmp_path / "repo"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                returncode=0,
                stdout="100644 blob abc\ttests/test_x.py\n",
            )
            _compute_code_hash(project_dir, paths=None)

            git_calls = [
                c for c in mock_run.call_args_list
                if "ls-tree" in str(c.args[0]) if c.args
            ]
            assert len(git_calls) >= 1
            git_argv = git_calls[0].args[0]
            # "." should be in the argv after '--'
            assert "." in git_argv


# ---------------------------------------------------------------------------
# _run_collect_only unit tests
# ---------------------------------------------------------------------------

class TestRunCollectOnly:
    """Direct unit tests for the _run_collect_only fallback."""

    def test_returns_ids_on_success(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        # Create a minimal conftest so pytest --collect-only doesn't complain
        (project_dir / "conftest.py").write_text("")
        (project_dir / "test_x.py").write_text(
            "def test_a(): pass\n"
            "def test_b(): pass\n"
        )

        ids = _run_collect_only(project_dir, "pytest")
        assert len(ids) == 2
        assert "test_x.py::test_a" in ids
        assert "test_x.py::test_b" in ids

    def test_returns_empty_when_no_tests(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "empty"
        project_dir.mkdir()
        (project_dir / "conftest.py").write_text("")

        ids = _run_collect_only(project_dir, "pytest")
        assert ids == []

    def test_returns_empty_on_spawn_failure(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("no pytest")),
        )
        ids = _run_collect_only(Path("/nonexistent"), "pytest")
        assert ids == []


def test_run_suite_parses_real_pytest_summary_nodeids(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    plan_dir = tmp_path / "plan"
    project_dir.mkdir()
    plan_dir.mkdir()
    (project_dir / "test_real_output.py").write_text(
        "def test_passes():\n"
        "    assert True\n\n"
        "def test_fails():\n"
        "    assert False\n",
        encoding="utf-8",
    )

    result = run_suite(
        project_dir,
        {"test_command": "pytest", "plan_dir": str(plan_dir)},
        phase="real_output",
        deadline_seconds=time.monotonic() + 60,
    )

    assert result.status == "failed"
    assert "test_real_output.py::test_fails" in result.failures
    assert "test_real_output.py::test_passes" in result.passes
    assert all("::" in nodeid for nodeid in result.failures + result.passes)
    assert "<test-" not in str(result.failures + result.passes + result.collected_ids)
    raw = result.raw_log_path.read_text(encoding="utf-8")
    assert "FAILED test_real_output.py::test_fails" in raw
    assert "PASSED test_real_output.py::test_passes" in raw


# ---------------------------------------------------------------------------
# run_suite exit_code=2 → runner_error integration
# ---------------------------------------------------------------------------

class TestExitCode2RunnerError:
    """Verify exit code 2 is mapped to runner_error end-to-end."""

    def test_exit_code_2_yields_runner_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()

        fake_proc = mock.MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.wait.return_value = 2  # pytest internal error

        monkeypatch.setattr(
            "megaplan.orchestration.suite_runner.spawn",
            lambda *a, **kw: fake_proc,
        )

        config = {
            "test_command": "pytest",
            "plan_dir": str(plan_dir),
        }
        deadline = time.monotonic() + 30.0
        result = run_suite(project_dir, config, phase="exit2", deadline_seconds=deadline)

        assert result.status == "runner_error"
        assert result.exit_code == 2
