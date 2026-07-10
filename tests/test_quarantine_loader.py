from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import textwrap

import pytest

from tests import conftest as test_conftest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
QUARANTINE_DIR = REPO_ROOT / "tests" / "quarantine"
SUBPROCESS_TEST = REPO_ROOT / "tests" / "_tmp_quarantine_signal_test.py"
SUBPROCESS_QUARANTINE = QUARANTINE_DIR / "_tmp_quarantine_signal.txt"


def test_quarantine_loader_requires_owner_and_reason_metadata(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir()
    quarantine_file = quarantine_dir / "missing_reason.txt"
    quarantine_file.write_text(
        "# owner: diagnostics\n"
        "tests/test_example.py::test_known_failure\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(test_conftest, "_QUARANTINE_DIR", quarantine_dir)
    monkeypatch.setattr(test_conftest, "_KNOWN_FAILURES_FILE", tmp_path / "known_failures.txt")

    with pytest.raises(ValueError, match="missing required quarantine metadata: reason"):
        test_conftest._load_quarantine_index()


def test_quarantined_failures_are_attributed_and_new_failures_still_fail() -> None:
    QUARANTINE_DIR.mkdir(exist_ok=True)
    SUBPROCESS_TEST.write_text(
        textwrap.dedent(
            """
            def test_quarantined_failure():
                assert False


            def test_new_failure():
                assert False
            """
        ),
        encoding="utf-8",
    )
    SUBPROCESS_QUARANTINE.write_text(
        "# owner: diagnostics\n"
        "# reason: verifies scoped quarantine summary attribution\n"
        "tests/_tmp_quarantine_signal_test.py::test_quarantined_failure\n",
        encoding="utf-8",
    )

    env = {**os.environ, "PYTHONHASHSEED": "0"}
    try:
        known_only = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/_tmp_quarantine_signal_test.py::test_quarantined_failure",
                "--tb=no",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
        )
        assert known_only.returncode == 0, known_only.stdout + known_only.stderr
        assert "TOLERATED FAIL: tests/_tmp_quarantine_signal_test.py::test_quarantined_failure" in known_only.stdout
        assert "tests/quarantine/_tmp_quarantine_signal.txt" in known_only.stdout

        mixed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/_tmp_quarantine_signal_test.py",
                "--tb=no",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
        )
        assert mixed.returncode == 1, mixed.stdout + mixed.stderr
        assert "TOLERATED FAIL: tests/_tmp_quarantine_signal_test.py::test_quarantined_failure" in mixed.stdout
        assert "NEW FAIL: tests/_tmp_quarantine_signal_test.py::test_new_failure" in mixed.stdout
    finally:
        SUBPROCESS_TEST.unlink(missing_ok=True)
        SUBPROCESS_QUARANTINE.unlink(missing_ok=True)
