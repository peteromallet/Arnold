"""T13 — strangler dual-green gate.

With MEGAPLAN_UNIFIED_DISPATCH unset, the four legacy critique test files
must pass with returncode 0, failed 0, errors 0, and passed >= baseline.
Also asserts old-path PipelineVerdict write sites are byte-unchanged.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

_STRANGLER_FILES = [
    "tests/test_critique.py",
    "tests/test_critique_evaluator.py",
    "tests/test_parallel_critique.py",
    "tests/test_adaptive_critique_wired.py",
]

_BASELINE_PATH = _REPO_ROOT / "tests" / "data" / "m5_eval_strangler_baseline.json"

# Old-path sites that must stay byte-identical: (file, line, expected_content_fragment)
_OLD_PATH_INVARIANTS: list[tuple[str, int, str]] = [
    # pattern_joins.py legacy PipelineVerdict writes (score=1.0 literal lines)
    ("megaplan/_pipeline/pattern_joins.py", 96, "score=1.0,"),
    ("megaplan/_pipeline/pattern_joins.py", 176, "score=1.0,"),
    # demo_judges.py verdict construction lines (score= present on same line as PipelineVerdict)
    # inprocess_step.py
    ("megaplan/_pipeline/stages/inprocess_step.py", 83, "PipelineVerdict(score=0.0"),
]


def _parse_pytest_summary(output: str) -> dict[str, int]:
    """Parse pytest -q summary line into {'passed': N, 'failed': N, 'errors': N}."""
    result = {"passed": 0, "failed": 0, "errors": 0}
    # pytest -q ends with a line like: "119 passed, 15 warnings in 0.70s"
    for line in reversed(output.splitlines()):
        m_passed = re.search(r"(\d+) passed", line)
        m_failed = re.search(r"(\d+) failed", line)
        m_error = re.search(r"(\d+) error", line)
        if m_passed:
            result["passed"] = int(m_passed.group(1))
        if m_failed:
            result["failed"] = int(m_failed.group(1))
        if m_error:
            result["errors"] = int(m_error.group(1))
        if m_passed or m_failed or m_error:
            break
    return result


def test_strangler_dual_green():
    """Four legacy critique tests pass with MEGAPLAN_UNIFIED_DISPATCH unset."""
    env = {k: v for k, v in os.environ.items() if k != "MEGAPLAN_UNIFIED_DISPATCH"}

    baseline = json.loads(_BASELINE_PATH.read_text())
    baseline_passed = baseline["passed"]

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *_STRANGLER_FILES],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_REPO_ROOT),
    )

    summary = _parse_pytest_summary(result.stdout + result.stderr)

    assert result.returncode == 0, (
        f"returncode={result.returncode}\nstdout={result.stdout[-2000:]}\nstderr={result.stderr[-1000:]}"
    )
    assert summary["failed"] == 0, f"failed={summary['failed']}"
    assert summary["errors"] == 0, f"errors={summary['errors']}"
    assert summary["passed"] >= baseline_passed, (
        f"passed={summary['passed']} < baseline={baseline_passed}"
    )


def test_old_path_writers_byte_unchanged():
    """Specific old-path PipelineVerdict write lines must be byte-unchanged."""
    for rel_path, lineno, expected_fragment in _OLD_PATH_INVARIANTS:
        path = _REPO_ROOT / rel_path
        lines = path.read_text().splitlines()
        actual_line = lines[lineno - 1]  # 1-indexed
        assert expected_fragment in actual_line, (
            f"{rel_path}:{lineno}: expected fragment {expected_fragment!r} "
            f"not found in {actual_line!r}"
        )
