"""Characterization-gate subprocess test for --known-failures-audit.

Demonstrates that ``--known-failures-audit`` emits a ``STALE FAILURES``
section when a scoped quarantine file contains entries that no longer map to
any collected test ID, and that it does NOT modify quarantine files.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
KF_PATH = REPO_ROOT / "tests" / "known_failures.txt"
QUARANTINE_PATH = REPO_ROOT / "tests" / "quarantine" / "_tmp_audit_stale_entries.txt"

# Stale test IDs that are guaranteed not to exist in this repo.
_STALE_IDS = (
    "tests/test_this_does_not_exist.py::test_nonexistent",
    "tests/test_also_nonexistent.py::test_another_fake",
)


def _run_audit(test_target: str = "tests/characterization/test_compile_api_snapshots.py") -> subprocess.CompletedProcess[str]:
    """Run a focused pytest invocation with --known-failures-audit."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--known-failures-audit",
            test_target,
            "--tb=no",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONHASHSEED": "0"},
        timeout=120,
    )


@pytest.mark.characterization
def test_known_failures_audit_reports_stale_entries() -> None:
    """Verify --known-failures-audit reports stale entries and does NOT modify files.

    Temporarily injects stale entries into a scoped quarantine file,
    runs ``--known-failures-audit``, asserts the STALE FAILURES section
    appears in stdout, then removes the temporary quarantine file.
    """
    original = KF_PATH.read_text(encoding="utf-8") if KF_PATH.exists() else ""
    QUARANTINE_PATH.unlink(missing_ok=True)

    try:
        stale_block = (
            "# owner: characterization-audit\n"
            "# reason: verifies scoped quarantine stale-entry reporting\n\n"
            + "\n".join(_STALE_IDS)
            + "\n"
        )
        QUARANTINE_PATH.write_text(stale_block, encoding="utf-8")

        result = _run_audit()

        assert "STALE FAILURES" in result.stdout, (
            f"Expected 'STALE FAILURES' section in stdout, got:\n"
            f"STDOUT:\n{result.stdout[:2000]}\n"
            f"STDERR:\n{result.stderr[:1000]}"
        )
        for sid in _STALE_IDS:
            assert sid in result.stdout, (
                f"Expected stale entry '{sid}' in audit output, got:\n{result.stdout[:2000]}"
            )
        assert "tests/quarantine/_tmp_audit_stale_entries.txt" in result.stdout
        assert "owner=characterization-audit" in result.stdout

        after_audit = KF_PATH.read_text(encoding="utf-8")
        assert after_audit == original, "--known-failures-audit must NOT modify known_failures.txt"
        assert QUARANTINE_PATH.read_text(encoding="utf-8") == stale_block

    finally:
        QUARANTINE_PATH.unlink(missing_ok=True)

    restored = KF_PATH.read_text(encoding="utf-8")
    assert restored == original, (
        "known_failures.txt should be byte-identical to original after restore"
    )
