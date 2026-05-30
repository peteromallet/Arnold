"""T32 / Step 27 — M3 dual-green chain configuration.

Runs BOTH flag-OFF (subprocess engine, pinned, schema-report-only) AND
flag-ON (in-process driver, throwaway plans only) on every M3 commit.
Both axes must pass for the M3 hinge gate to report green.

Public surface:

* ``DualGreenResult`` — frozen dataclass with ``flag_off_ok`` / ``flag_on_ok``.
* ``run_flag_off()`` — run the schema-report validation under flag-OFF.
* ``run_flag_on()`` — run the in-process driver tests under flag-ON.
* ``run_dual_green()`` — run both and return a ``DualGreenResult``.
* ``run_dual_green_gate()`` — convenience: returns True iff both pass.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Flag-OFF: subprocess engine, pinned, schema-report-only
# ---------------------------------------------------------------------------

_FLAG_OFF_TARGETS = (
    REPO_ROOT / "tests" / "test_driver_subprocess_isolated.py",
    REPO_ROOT / "tests" / "test_driver_selection.py",
    REPO_ROOT / "tests" / "test_supervise_subprocess_regression.py",
    REPO_ROOT / "tests" / "test_legacy_subprocess_snapshot.py",
    REPO_ROOT / "tests" / "test_unified_dispatch_flag.py",
)


def run_flag_off(
    extra_args: Optional[List[str]] = None,
) -> subprocess.CompletedProcess[str]:
    """Run the flag-OFF schema-report suite.

    Environment: MEGAPLAN_UNIFIED_DISPATCH is explicitly **unset** so the
    master flag reads OFF (the ``== "1"`` convention makes absent → False).
    The subprocess engine is the pinned runtime; only schema-report targets
    are exercised (no in-process driver paths).
    """
    env = os.environ.copy()
    env.pop("MEGAPLAN_UNIFIED_DISPATCH", None)
    cmd = [
        sys.executable, "-m", "pytest", "-q", "--tb=short",
        *(str(p) for p in _FLAG_OFF_TARGETS),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Flag-ON: in-process driver, throwaway plans only
# ---------------------------------------------------------------------------

_FLAG_ON_TARGETS = (
    REPO_ROOT / "tests" / "test_driver_in_process.py",
    REPO_ROOT / "tests" / "test_driver_selection.py",
    REPO_ROOT / "tests" / "test_unified_dispatch_flag.py",
    REPO_ROOT / "tests" / "test_activation_in_pipeline.py",
    REPO_ROOT / "tests" / "test_governor_under_activation.py",
    REPO_ROOT / "tests" / "test_loop_node.py",
    REPO_ROOT / "tests" / "test_run_envelope.py",
    REPO_ROOT / "tests" / "test_state_reversible.py",
    REPO_ROOT / "tests" / "test_corpus_completeness.py",
    REPO_ROOT / "tests" / "test_flag_on_corpus_fixtures.py",
    REPO_ROOT / "tests" / "test_hinge_gate_chain.py",
    REPO_ROOT / "tests" / "oracles" / "test_crash_isolation_oracle.py",
    REPO_ROOT / "tests" / "oracles" / "test_version_skew_oracle.py",
    REPO_ROOT / "tests" / "test_hinge_fold_equivalence.py",
    REPO_ROOT / "tests" / "test_workflow_topology_parity_gate.py",
    REPO_ROOT / "tests" / "test_r1_authority_flip.py",
    REPO_ROOT / "tests" / "test_state_reader_audit.py",
)


def run_flag_on(
    extra_args: Optional[List[str]] = None,
) -> subprocess.CompletedProcess[str]:
    """Run the flag-ON in-process driver suite.

    Environment: MEGAPLAN_UNIFIED_DISPATCH=1 so every flag-gated code path
    exercises the new in-process driver with throwaway plans.  The subprocess
    engine is **not** exercised on this axis.
    """
    env = os.environ.copy()
    env["MEGAPLAN_UNIFIED_DISPATCH"] = "1"
    cmd = [
        sys.executable, "-m", "pytest", "-q", "--tb=short",
        *(str(p) for p in _FLAG_ON_TARGETS),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Combined dual-green result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DualGreenResult:
    """Result of a dual-green run.

    Both axes must pass for the M3 hinge gate to report green.
    """

    flag_off_ok: bool
    flag_on_ok: bool
    flag_off_output: str = ""
    flag_on_output: str = ""

    @property
    def passed(self) -> bool:
        """True iff both flag-OFF and flag-ON axes pass."""
        return self.flag_off_ok and self.flag_on_ok


def run_dual_green(
    flag_off_extra: Optional[List[str]] = None,
    flag_on_extra: Optional[List[str]] = None,
) -> DualGreenResult:
    """Run both flag-OFF and flag-ON suites and return a ``DualGreenResult``.

    This is the entry point wired into the M3 chain runner.  Each axis runs
    independently; a failure on one does not short-circuit the other so the
    operator sees the full red surface in a single pass.
    """
    off = run_flag_off(extra_args=flag_off_extra)
    on = run_flag_on(extra_args=flag_on_extra)
    return DualGreenResult(
        flag_off_ok=off.returncode == 0,
        flag_on_ok=on.returncode == 0,
        flag_off_output=off.stdout + off.stderr,
        flag_on_output=on.stdout + on.stderr,
    )


def run_dual_green_gate() -> bool:
    """Convenience: return True iff the dual-green gate passes."""
    return run_dual_green().passed


# ---------------------------------------------------------------------------
# Oneshot grep audit (T32 scoped-grep contract)
# ---------------------------------------------------------------------------


def assert_no_oneshot_in_scoped_trees() -> None:
    """Assert ``grep -rE \"oneshot\" megaplan/_pipeline megaplan/drivers`` returns 0.

    The word *oneshot* is a phantom driver concept that has been deleted from
    the codebase (M3-hinge brief § Scope).  No file in the pipeline or driver
    trees may contain that literal string.  This gate is run by the dual-green
    chain on every M3 commit.
    """
    import subprocess as _sp

    root = REPO_ROOT
    proc = _sp.run(
        ["grep", "-rE", "oneshot", "--include=*.py",
         str(root / "megaplan" / "_pipeline"),
         str(root / "megaplan" / "drivers")],
        capture_output=True, text=True,
    )
    # grep exits 0 on match, 1 on no match, 2+ on error
    if proc.returncode == 0:
        raise AssertionError(
            f"oneshot keyword found in scoped trees:\n{proc.stdout}"
        )
    if proc.returncode > 1:
        raise RuntimeError(
            f"grep failed (rc={proc.returncode}): {proc.stderr}"
        )
    # rc=1 → no matches → gate passes


# ---------------------------------------------------------------------------
# Stub-survival guard
# ---------------------------------------------------------------------------


def assert_strangler_keep_alive_stub() -> Path:
    """Assert ``briefs/validation/sequencing/strangler-keep-alive.md`` exists.

    If the file is missing, re-create it from the Step 0c template.
    Returns the resolved path.
    """
    stub = REPO_ROOT / "briefs" / "validation" / "sequencing" / "strangler-keep-alive.md"
    if not stub.exists():
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text(
            "# Strangler Keep-Alive\n\n"
            "## M3\n\n"
            "Placeholder stub for the strangler keep-alive sequencing brief.\n"
            "Re-created by M3 dual-green stub-survival guard (T32).\n",
            encoding="utf-8",
        )
    return stub


def record_m3_dual_green_window() -> None:
    """Record the M3 dual-green window in the strangler-keep-alive stub.

    The dual-green window starts at M3 (≥1 milestone) and is retired at M6
    when the atomic strangler swap completes.
    """
    stub = assert_strangler_keep_alive_stub()
    content = stub.read_text(encoding="utf-8")
    marker = "## M3 Dual-Green Window"
    if marker in content:
        return  # already recorded
    entry = (
        "\n"
        "## M3 Dual-Green Window\n"
        "\n"
        "- **Opens:** M3 (THE HINGE — Activation + realized-graph + 2-axis drivers + Conveyance + R1 authority-flip + Governor)\n"
        "- **Closes:** M6 (atomic strangler swap — last load-bearing subprocess node retired)\n"
        "- **Coverage:** ≥1 milestone (M3 through M5c inclusive).\n"
        "- **Contract:** Every M3 commit runs BOTH flag-OFF (subprocess engine, pinned, schema-report-only)\n"
        "  AND flag-ON (in-process driver, throwaway plans only).  Both axes must pass for the\n"
        "  hinge gate to report green.\n"
        "- **Retirement:** At M6 the subprocess path is deleted; the dual-green window closes and\n"
        "  flag-ON becomes the sole runtime.\n"
    )
    stub.write_text(content.rstrip() + entry, encoding="utf-8")


__all__ = [
    "DualGreenResult",
    "run_flag_off",
    "run_flag_on",
    "run_dual_green",
    "run_dual_green_gate",
    "assert_no_oneshot_in_scoped_trees",
    "assert_strangler_keep_alive_stub",
    "record_m3_dual_green_window",
]
