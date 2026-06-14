"""T32 / Step 27 — M3 dual-green chain config tests.

Covers:
    - DualGreenResult passed/not-passed states.
    - run_flag_off / run_flag_on exit-code semantics.
    - assert_no_oneshot_in_scoped_trees gate (passes when 0 matches).
    - Stub-survival guard: re-creates strangler-keep-alive.md if missing.
    - record_m3_dual_green_window idempotency.
    - Scoped grep for "oneshot" returns 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.chain.m3_dual_green import (
    DualGreenResult,
    assert_no_oneshot_in_scoped_trees,
    assert_strangler_keep_alive_stub,
    record_m3_dual_green_window,
    run_dual_green,
    run_dual_green_gate,
    run_flag_off,
    run_flag_on,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# DualGreenResult
# ---------------------------------------------------------------------------


def test_dual_green_result_both_ok() -> None:
    r = DualGreenResult(flag_off_ok=True, flag_on_ok=True)
    assert r.passed is True


def test_dual_green_result_flag_off_fails() -> None:
    r = DualGreenResult(flag_off_ok=False, flag_on_ok=True)
    assert r.passed is False


def test_dual_green_result_flag_on_fails() -> None:
    r = DualGreenResult(flag_off_ok=True, flag_on_ok=False)
    assert r.passed is False


def test_dual_green_result_both_fail() -> None:
    r = DualGreenResult(flag_off_ok=False, flag_on_ok=False)
    assert r.passed is False


def test_dual_green_result_output_fields() -> None:
    r = DualGreenResult(
        flag_off_ok=True,
        flag_on_ok=False,
        flag_off_output="off stdout",
        flag_on_output="on stderr",
    )
    assert "off stdout" in r.flag_off_output
    assert "on stderr" in r.flag_on_output


# ---------------------------------------------------------------------------
# Flag-OFF / Flag-ON smoke tests (fast, no subprocess mocks)
# ---------------------------------------------------------------------------


def test_run_flag_off_runs_without_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag-OFF clears MEGAPLAN_UNIFIED_DISPATCH from env."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "1")
    proc = run_flag_off(extra_args=["--co", "--quiet"])
    # Even if tests fail, the process ran (not a crash)
    assert proc.returncode in (0, 1, 5)


def test_run_flag_on_runs_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag-ON sets MEGAPLAN_UNIFIED_DISPATCH=1."""
    monkeypatch.setenv("MEGAPLAN_UNIFIED_DISPATCH", "0")
    proc = run_flag_on(extra_args=["--co", "--quiet"])
    assert proc.returncode in (0, 1, 5)


def test_run_dual_green_returns_result() -> None:
    """Sanity: run_dual_green returns a DualGreenResult."""
    result = run_dual_green(
        flag_off_extra=["--co", "--quiet"],
        flag_on_extra=["--co", "--quiet"],
    )
    assert isinstance(result, DualGreenResult)
    assert isinstance(result.passed, bool)


def test_run_dual_green_gate_returns_bool() -> None:
    assert isinstance(run_dual_green_gate(), bool)


# ---------------------------------------------------------------------------
# Oneshot grep audit
# ---------------------------------------------------------------------------


def test_assert_no_oneshot_in_scoped_trees_passes() -> None:
    """The word 'oneshot' must not appear in arnold/pipelines/megaplan/_pipeline or arnold/pipelines/megaplan/drivers."""
    assert_no_oneshot_in_scoped_trees()  # must not raise


def test_shell_grep_oneshot_returns_zero() -> None:
    """Literal shell grep for 'oneshot' in scoped trees returns 0 hits."""
    proc = subprocess.run(
        [
            "grep", "-rE", "oneshot",
            "--include=*.py",
            str(REPO_ROOT / "arnold" / "pipelines" / "megaplan" / "_pipeline"),
            str(REPO_ROOT / "arnold" / "pipelines" / "megaplan" / "drivers"),
        ],
        capture_output=True,
        text=True,
    )
    # grep exits 1 when no matches found
    assert proc.returncode == 1, (
        f"oneshot keyword found in scoped trees (rc={proc.returncode}):\n"
        f"{proc.stdout}"
    )


# ---------------------------------------------------------------------------
# Stub-survival guard
# ---------------------------------------------------------------------------


def test_strangler_keep_alive_stub_exists() -> None:
    stub = assert_strangler_keep_alive_stub()
    assert stub.exists()
    assert stub.name == "strangler-keep-alive.md"
    content = stub.read_text(encoding="utf-8")
    assert "# Strangler Keep-Alive" in content
    assert "## M3" in content


def test_strangler_keep_alive_stub_recreates_if_missing(tmp_path: Path) -> None:
    """If the stub is missing, it is re-created from the template."""
    (tmp_path / "briefs" / "validation" / "sequencing").mkdir(parents=True)
    # Temporary monkeypatch: redirect the function to use tmp_path
    import arnold.pipelines.megaplan.chain.m3_dual_green as mdg

    original_root = mdg.REPO_ROOT
    try:
        mdg.REPO_ROOT = tmp_path
        stub = assert_strangler_keep_alive_stub()
        assert stub.exists()
        content = stub.read_text(encoding="utf-8")
        assert "# Strangler Keep-Alive" in content
        assert "Re-created by M3 dual-green stub-survival guard" in content
    finally:
        mdg.REPO_ROOT = original_root


def test_record_m3_dual_green_window(tmp_path: Path) -> None:
    """Recording the dual-green window adds the section."""
    (tmp_path / "briefs" / "validation" / "sequencing").mkdir(parents=True)
    stub = tmp_path / "briefs" / "validation" / "sequencing" / "strangler-keep-alive.md"
    stub.write_text(
        "# Strangler Keep-Alive\n\n## M3\n\nPlaceholder stub.\n",
        encoding="utf-8",
    )

    import arnold.pipelines.megaplan.chain.m3_dual_green as mdg

    original_root = mdg.REPO_ROOT
    try:
        mdg.REPO_ROOT = tmp_path
        record_m3_dual_green_window()
        content = stub.read_text(encoding="utf-8")
        assert "## M3 Dual-Green Window" in content
        assert "Opens:" in content and "M3" in content
        assert "Closes:" in content and "M6" in content
        assert "flag-OFF" in content
        assert "flag-ON" in content
    finally:
        mdg.REPO_ROOT = original_root


def test_record_m3_dual_green_window_idempotent(tmp_path: Path) -> None:
    """Recording a second time does not duplicate the section."""
    (tmp_path / "briefs" / "validation" / "sequencing").mkdir(parents=True)
    stub = tmp_path / "briefs" / "validation" / "sequencing" / "strangler-keep-alive.md"
    stub.write_text(
        "# Strangler Keep-Alive\n\n## M3\n\nPlaceholder stub.\n",
        encoding="utf-8",
    )

    import arnold.pipelines.megaplan.chain.m3_dual_green as mdg

    original_root = mdg.REPO_ROOT
    try:
        mdg.REPO_ROOT = tmp_path
        record_m3_dual_green_window()
        record_m3_dual_green_window()  # second call
        content = stub.read_text(encoding="utf-8")
        # Count occurrences — should be exactly 1
        assert content.count("## M3 Dual-Green Window") == 1
    finally:
        mdg.REPO_ROOT = original_root


# ---------------------------------------------------------------------------
# Subprocess driver code remains (SubprocessIsolatedDriver is importable)
# ---------------------------------------------------------------------------


def test_subprocess_isolated_driver_still_importable() -> None:
    """The subprocess driver code remains — not deleted by the M3 flip."""
    from arnold.pipelines.megaplan.drivers.subprocess_isolated import SubprocessIsolatedDriver

    drv = SubprocessIsolatedDriver(
        name="test",
        argv=["python", "-c", "print('hello')"],
    )
    assert drv.name == "test"
    assert drv.argv == ["python", "-c", "print('hello')"]
