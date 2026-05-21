"""
test_agentic_checks.py — pytest tests for megaplan friction-signal extractors.

Each test creates a synthetic evidence pack (temp dir with stderr.log,
command_log.jsonl, git_diff.patch, project_specific/gate.json) and asserts
that the corresponding signal returns correct count/passed/detail values.

Discoverable via ``python -m pytest`` because this file lives under the
top-level ``tests/`` directory (``pyproject.toml`` line 70:
``testpaths = ["tests"]``).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure ``megaplan`` is importable (the repo root is on the path when
# running from the repo root, but we are defensive).
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from megaplan.tests.agentic.megaplan_checks import project_universal_checks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_evidence_dir() -> Path:
    """Return a path to a fresh temporary directory."""
    td = tempfile.mkdtemp(prefix="megaplan_evidence_")
    return Path(td)


# ---------------------------------------------------------------------------
# Signal 1 — invalid_transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    """Case-sensitive ``invalid_transition`` hits in stderr + command_log."""

    def test_no_hits_empty_evidence(self):
        d = _make_evidence_dir()
        result = project_universal_checks(d)["invalid_transitions"]
        assert result["count"] == 0
        assert result["passed"] is True
        assert "none" in result["detail"]

    def test_hit_in_stderr(self):
        d = _make_evidence_dir()
        _write(d / "stderr.log", "ERROR: invalid_transition from blocked to done\n")
        result = project_universal_checks(d)["invalid_transitions"]
        assert result["count"] == 1
        assert result["passed"] is False
        assert "stderr.log (1)" in result["detail"]

    def test_hit_in_command_log_jsonl(self):
        d = _make_evidence_dir()
        _write(
            d / "command_log.jsonl",
            json.dumps({"command": "megaplan advance", "stderr": "invalid_transition"})
            + "\n",
        )
        result = project_universal_checks(d)["invalid_transitions"]
        assert result["count"] == 1
        assert result["passed"] is False
        assert "command_log.jsonl:1 (1)" in result["detail"]

    def test_multiple_hits_across_files(self):
        d = _make_evidence_dir()
        _write(d / "stderr.log", "invalid_transition\ninvalid_transition\n")
        _write(
            d / "command_log.jsonl",
            json.dumps({"command": "x", "output": "invalid_transition blah invalid_transition"})
            + "\n",
        )
        result = project_universal_checks(d)["invalid_transitions"]
        assert result["count"] == 4  # 2 in stderr + 2 in command_log
        assert result["passed"] is False

    def test_case_insensitive_not_matched(self):
        d = _make_evidence_dir()
        _write(d / "stderr.log", "INVALID_TRANSITION\nInvalid_Transition\n")
        result = project_universal_checks(d)["invalid_transitions"]
        assert result["count"] == 0
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Signal 2 — overrides
# ---------------------------------------------------------------------------


class TestOverrides:
    """Regex ``megaplan override <verb>`` in stdout + stderr."""

    def test_no_overrides(self):
        d = _make_evidence_dir()
        result = project_universal_checks(d)["overrides"]
        assert result["count"] == 0
        assert result["passed"] is True
        assert "none" in result["detail"]

    def test_single_override_with_verb(self):
        d = _make_evidence_dir()
        _write(d / "stdout.log", "ran: megaplan override advance\n")
        result = project_universal_checks(d)["overrides"]
        assert result["count"] == 1
        assert result["passed"] is False
        assert "advance" in result["detail"]

    def test_multiple_overrides_stderr(self):
        d = _make_evidence_dir()
        _write(
            d / "stderr.log",
            "megaplan override block\nsome text\nmegaplan override reject\n",
        )
        result = project_universal_checks(d)["overrides"]
        assert result["count"] == 2
        # Verbs should be collected.
        assert "block" in result["detail"]
        assert "reject" in result["detail"]

    def test_override_without_verb(self):
        d = _make_evidence_dir()
        _write(d / "stdout.log", "megaplan override\n")
        result = project_universal_checks(d)["overrides"]
        assert result["count"] == 1
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# Signal 3 — auto_downgraded
# ---------------------------------------------------------------------------


class TestAutoDowngraded:
    """``Auto-downgraded`` hits in captured gate.json files."""

    def test_no_hits(self):
        d = _make_evidence_dir()
        result = project_universal_checks(d)["auto_downgraded"]
        assert result["count"] == 0
        assert result["passed"] is True

    def test_hit_in_project_specific_gate_json(self):
        d = _make_evidence_dir()
        _write(
            d / "project_specific" / "gate.json",
            '{"status": "Auto-downgraded -- quality threshold not met"}',
        )
        result = project_universal_checks(d)["auto_downgraded"]
        assert result["count"] == 1
        assert result["passed"] is False
        assert "gate.json" in result["detail"]

    def test_multiple_gate_files(self):
        d = _make_evidence_dir()
        _write(
            d / "project_specific" / "gate.json",
            '{"status": "Auto-downgraded"}',
        )
        _write(
            d / "project_specific" / "nested" / "gate.json",
            'Auto-downgraded x2\nAnd Auto-downgraded again',
        )
        result = project_universal_checks(d)["auto_downgraded"]
        # count across all gate.json files
        assert result["count"] >= 1
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# Signal 4 — status_loops
# ---------------------------------------------------------------------------


class TestStatusLoops:
    """Runs of ≥3 consecutive ``megaplan status`` with no mutating command."""

    def test_no_command_log(self):
        d = _make_evidence_dir()
        result = project_universal_checks(d)["status_loops"]
        assert result["count"] == 0
        assert result["passed"] is True

    def test_no_repeated_status(self):
        d = _make_evidence_dir()
        entries = [
            {"command": "megaplan status"},
            {"command": "megaplan run"},
            {"command": "megaplan status"},
        ]
        _write(d / "command_log.jsonl", "\n".join(json.dumps(e) for e in entries) + "\n")
        result = project_universal_checks(d)["status_loops"]
        assert result["count"] == 0
        assert result["passed"] is True

    def test_exactly_three_consecutive_status(self):
        d = _make_evidence_dir()
        entries = [
            {"command": "megaplan status"},
            {"command": "megaplan status"},
            {"command": "megaplan status"},
        ]
        _write(d / "command_log.jsonl", "\n".join(json.dumps(e) for e in entries) + "\n")
        result = project_universal_checks(d)["status_loops"]
        assert result["count"] == 1
        assert result["passed"] is False

    def test_five_consecutive_status_still_one_run(self):
        d = _make_evidence_dir()
        entries = [
            {"command": "megaplan status"}
            for _ in range(5)
        ]
        _write(d / "command_log.jsonl", "\n".join(json.dumps(e) for e in entries) + "\n")
        result = project_universal_checks(d)["status_loops"]
        assert result["count"] == 1
        assert result["passed"] is False

    def test_two_runs_of_three(self):
        d = _make_evidence_dir()
        entries = [
            {"command": "megaplan status"},
            {"command": "megaplan status"},
            {"command": "megaplan status"},
            {"command": "megaplan init"},        # reset
            {"command": "megaplan status"},
            {"command": "megaplan status"},
            {"command": "megaplan status"},
        ]
        _write(d / "command_log.jsonl", "\n".join(json.dumps(e) for e in entries) + "\n")
        result = project_universal_checks(d)["status_loops"]
        assert result["count"] == 2
        assert result["passed"] is False

    def test_two_status_not_enough(self):
        d = _make_evidence_dir()
        entries = [
            {"command": "megaplan status"},
            {"command": "megaplan status"},
            {"command": "megaplan advance"},     # mutating — resets
        ]
        _write(d / "command_log.jsonl", "\n".join(json.dumps(e) for e in entries) + "\n")
        result = project_universal_checks(d)["status_loops"]
        assert result["count"] == 0
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Signal 5 — direct_edits
# ---------------------------------------------------------------------------


class TestDirectEdits:
    """Non-test .py files in git_diff.patch without preceding ``megaplan init``."""

    def test_no_diff_file(self):
        d = _make_evidence_dir()
        result = project_universal_checks(d)["direct_edits"]
        assert result["count"] == 0
        assert result["passed"] is True

    def test_diff_with_no_py_files(self):
        d = _make_evidence_dir()
        _write(
            d / "git_diff.patch",
            "diff --git a/README.md b/README.md\n"
            "--- a/README.md\n"
            "+++ b/README.md\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n",
        )
        result = project_universal_checks(d)["direct_edits"]
        assert result["count"] == 0
        assert result["passed"] is True

    def test_non_test_py_file_no_init(self):
        d = _make_evidence_dir()
        _write(
            d / "git_diff.patch",
            "diff --git a/megaplan/cli.py b/megaplan/cli.py\n"
            "--- a/megaplan/cli.py\n"
            "+++ b/megaplan/cli.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n",
        )
        # No command_log → no megaplan init seen → count = 1
        result = project_universal_checks(d)["direct_edits"]
        assert result["count"] == 1
        assert result["passed"] is False
        assert "megaplan/cli.py" in result["detail"]
        assert "init seen: False" in result["detail"]

    def test_non_test_py_file_with_init(self):
        d = _make_evidence_dir()
        _write(
            d / "git_diff.patch",
            "diff --git a/megaplan/cli.py b/megaplan/cli.py\n"
            "--- a/megaplan/cli.py\n"
            "+++ b/megaplan/cli.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n",
        )
        _write(
            d / "command_log.jsonl",
            json.dumps({"command": "megaplan init my-plan"}) + "\n",
        )
        result = project_universal_checks(d)["direct_edits"]
        assert result["count"] == 0
        assert result["passed"] is True
        assert "init seen: True" in result["detail"]

    def test_test_files_excluded(self):
        d = _make_evidence_dir()
        _write(
            d / "git_diff.patch",
            "diff --git a/tests/test_something.py b/tests/test_something.py\n"
            "--- a/tests/test_something.py\n"
            "+++ b/tests/test_something.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n",
        )
        result = project_universal_checks(d)["direct_edits"]
        assert result["count"] == 0
        assert result["passed"] is True

    def test_multiple_py_files_some_test_some_not(self):
        d = _make_evidence_dir()
        _write(
            d / "git_diff.patch",
            "diff --git a/src/foo.py b/src/foo.py\n"
            "--- a/src/foo.py\n"
            "+++ b/src/foo.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
            "diff --git a/tests/test_foo.py b/tests/test_foo.py\n"
            "--- a/tests/test_foo.py\n"
            "+++ b/tests/test_foo.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n",
        )
        result = project_universal_checks(d)["direct_edits"]
        assert result["count"] == 1  # only src/foo.py counted
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# Integration — all five signals returned
# ---------------------------------------------------------------------------


def test_all_five_signals_present():
    """project_universal_checks returns all five signal keys."""
    d = _make_evidence_dir()
    result = project_universal_checks(d)
    expected_keys = {
        "invalid_transitions",
        "overrides",
        "auto_downgraded",
        "status_loops",
        "direct_edits",
    }
    assert set(result.keys()) == expected_keys
    for key in expected_keys:
        assert "count" in result[key]
        assert "passed" in result[key]
        assert "detail" in result[key]


def test_full_evidence_pack_integration():
    """End-to-end: all evidence files present with realistic data."""
    d = _make_evidence_dir()

    # stderr with an invalid_transition
    _write(d / "stderr.log", "invalid_transition detected\n")

    # stdout with an override
    _write(d / "stdout.log", "megaplan override advance executed\n")

    # command_log with status loop (3 consecutive) and an init for direct_edits
    entries = [
        {"command": "megaplan init my-plan"},
        {"command": "megaplan status"},
        {"command": "megaplan status"},
        {"command": "megaplan status"},
        {"command": "megaplan advance"},
    ]
    _write(d / "command_log.jsonl", "\n".join(json.dumps(e) for e in entries) + "\n")

    # git_diff with a non-test .py change (but init exists, so direct_edits=0)
    _write(
        d / "git_diff.patch",
        "diff --git a/megaplan/cli.py b/megaplan/cli.py\n"
        "--- a/megaplan/cli.py\n"
        "+++ b/megaplan/cli.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n",
    )

    # gate.json with auto-downgraded
    _write(
        d / "project_specific" / "gate.json",
        '{"status": "Auto-downgraded by quality gate"}',
    )

    result = project_universal_checks(d)

    # invalid_transitions: 1 in stderr
    assert result["invalid_transitions"]["count"] == 1
    assert result["invalid_transitions"]["passed"] is False

    # overrides: 1 in stdout
    assert result["overrides"]["count"] == 1
    assert result["overrides"]["passed"] is False
    assert "advance" in result["overrides"]["detail"]

    # auto_downgraded: 1 in gate.json
    assert result["auto_downgraded"]["count"] == 1
    assert result["auto_downgraded"]["passed"] is False

    # status_loops: 1 run of 3 consecutive status
    assert result["status_loops"]["count"] == 1
    assert result["status_loops"]["passed"] is False

    # direct_edits: init exists, so 0
    assert result["direct_edits"]["count"] == 0
    assert result["direct_edits"]["passed"] is True
    assert "init seen: True" in result["direct_edits"]["detail"]
