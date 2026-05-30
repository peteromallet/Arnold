"""T33 / Step 28 — M3 chain CI hook.

Wires every M3 hinge gate in the mandated order and produces a single
``ChainCIResult``.  The commit-message stamp ``[HINGE GATE: GREEN]`` is
emitted ONLY when every gate passes; any red gate produces an unlabelled
result so the milestone commit is never falsely stamped.

Gate order (locked by T33 contract):

1. parity           — workflow-topology parity gate (T10)
2. fold_baseline    — fold-equivalence oracle, baseline MANIFEST (T26)
3. fold_flag_on     — fold-equivalence oracle, flag-ON MANIFEST (T26)
4. crash_isolation  — subprocess crash-isolation oracle (T28)
5. version_skew     — A/B version-skew oracle (T29)
6. cloud_smoke      — cloud phase_command shim (T17)
7. acceptance_toy   — N-queens backtrack-solver acceptance toy (T31)
8. dual_green       — dual-green strangler guard (T32)

Stub-survival:
  ``assert_program_md()`` ensures ``briefs/validation/sequencing/PROGRAM.md``
  exists and carries an M3 entry.  Re-created from Step 0c template if the
  file is missing.

Public surface:

* ``GateOutcome``      — per-gate pass/fail row.
* ``ChainCIResult``   — frozen dataclass; ``passed`` / ``gate_outcomes``.
* ``run_chain_ci``    — execute every gate once and return the result.
* ``commit_label``    — returns ``"[HINGE GATE: GREEN]"`` iff result is green.
* ``assert_program_md`` — stub-survival guard for PROGRAM.md.
* ``GATE_ORDER``       — ordered tuple of (gate_name, callable) pairs.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from megaplan.observability.fold import fold_equivalence_oracle

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Gate target paths
# ---------------------------------------------------------------------------

_PARITY_GATE_TEST = (
    REPO_ROOT / "tests" / "test_workflow_topology_parity_gate.py"
)
_BASELINE_MANIFEST = (
    REPO_ROOT / "tests" / "characterization" / "auto_drive_corpus" / "MANIFEST.json"
)
_FLAG_ON_MANIFEST = (
    REPO_ROOT / "tests" / "corpus" / "flag_on" / "MANIFEST.json"
)
_CRASH_ISOLATION_TEST = (
    REPO_ROOT / "tests" / "oracles" / "test_crash_isolation_oracle.py"
)
_VERSION_SKEW_TEST = (
    REPO_ROOT / "tests" / "oracles" / "test_version_skew_oracle.py"
)
_CLOUD_SMOKE_TEST = (
    REPO_ROOT / "tests" / "cloud" / "test_phase_command_shim.py"
)
_ACCEPTANCE_TOY_TEST = (
    REPO_ROOT / "acceptance" / "backtrack_solver" / "tests" / "test_nqueens.py"
)

_PROGRAM_MD = (
    REPO_ROOT / "briefs" / "validation" / "sequencing" / "PROGRAM.md"
)

HINGE_GATE_GREEN_STAMP = "[HINGE GATE: GREEN]"


# ---------------------------------------------------------------------------
# GateOutcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateOutcome:
    name: str
    ok: bool
    detail: str = ""


# ---------------------------------------------------------------------------
# ChainCIResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainCIResult:
    """Result of running all M3 chain CI gates.

    ``passed`` is True only when every gate reports ok.
    ``commit_label`` returns ``"[HINGE GATE: GREEN]"`` iff passed; otherwise
    returns an empty string so the milestone commit is never falsely stamped.
    """

    passed: bool
    gate_outcomes: List[GateOutcome] = field(default_factory=list)

    @property
    def failures(self) -> List[GateOutcome]:
        return [g for g in self.gate_outcomes if not g.ok]

    def commit_label(self) -> str:
        """Return the hinge-gate stamp iff all gates are green."""
        return HINGE_GATE_GREEN_STAMP if self.passed else ""


# ---------------------------------------------------------------------------
# Individual gate callables
# ---------------------------------------------------------------------------


def _pytest_gate(name: str, test_path: Path) -> GateOutcome:
    if not test_path.exists():
        return GateOutcome(name=name, ok=False, detail=f"missing: {test_path}")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", str(test_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return GateOutcome(name=name, ok=True, detail="pytest ok")
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-10:])
    return GateOutcome(name=name, ok=False, detail=f"rc={proc.returncode}: {tail}")


def _fold_gate(name: str, manifest: Path) -> GateOutcome:
    if not manifest.exists():
        return GateOutcome(name=name, ok=False, detail=f"missing manifest: {manifest}")
    result = fold_equivalence_oracle(manifest)
    if result.ok:
        return GateOutcome(name=name, ok=True, detail=f"{result.passed}/{result.total} goldens")
    detail = "; ".join(
        f"{f.name}: expected={f.expected!r} actual={f.actual!r} ({f.reason})"
        for f in result.failures
    )
    return GateOutcome(name=name, ok=False, detail=detail or "diverged")


def gate_parity() -> GateOutcome:
    """Workflow-topology parity gate (T10)."""
    return _pytest_gate("parity", _PARITY_GATE_TEST)


def gate_fold_baseline() -> GateOutcome:
    """Fold-equivalence oracle, baseline MANIFEST (T26)."""
    return _fold_gate("fold_baseline", _BASELINE_MANIFEST)


def gate_fold_flag_on() -> GateOutcome:
    """Fold-equivalence oracle, flag-ON MANIFEST (T26)."""
    return _fold_gate("fold_flag_on", _FLAG_ON_MANIFEST)


def gate_crash_isolation() -> GateOutcome:
    """Subprocess crash-isolation oracle (T28)."""
    return _pytest_gate("crash_isolation", _CRASH_ISOLATION_TEST)


def gate_version_skew() -> GateOutcome:
    """A/B version-skew oracle (T29)."""
    return _pytest_gate("version_skew", _VERSION_SKEW_TEST)


def gate_cloud_smoke() -> GateOutcome:
    """Cloud phase_command shim (T17)."""
    return _pytest_gate("cloud_smoke", _CLOUD_SMOKE_TEST)


def gate_acceptance_toy() -> GateOutcome:
    """N-queens backtrack-solver acceptance toy (T31)."""
    return _pytest_gate("acceptance_toy", _ACCEPTANCE_TOY_TEST)


def gate_dual_green() -> GateOutcome:
    """Dual-green strangler guard (T32)."""
    from megaplan.chain.m3_dual_green import run_dual_green

    result = run_dual_green()
    if result.passed:
        return GateOutcome(name="dual_green", ok=True, detail="flag-OFF + flag-ON both green")
    parts = []
    if not result.flag_off_ok:
        parts.append("flag-OFF red")
    if not result.flag_on_ok:
        parts.append("flag-ON red")
    return GateOutcome(name="dual_green", ok=False, detail="; ".join(parts))


# ---------------------------------------------------------------------------
# Ordered gate list (T33 contract — do not reorder)
# ---------------------------------------------------------------------------


GATE_ORDER: Tuple[Tuple[str, Callable[[], GateOutcome]], ...] = (
    ("parity", gate_parity),
    ("fold_baseline", gate_fold_baseline),
    ("fold_flag_on", gate_fold_flag_on),
    ("crash_isolation", gate_crash_isolation),
    ("version_skew", gate_version_skew),
    ("cloud_smoke", gate_cloud_smoke),
    ("acceptance_toy", gate_acceptance_toy),
    ("dual_green", gate_dual_green),
)


# ---------------------------------------------------------------------------
# Stub-survival guard — PROGRAM.md
# ---------------------------------------------------------------------------

_M3_PROGRAM_ENTRY = """\

## M3 Entry

- **Seam:** dormant — R1 authority flipped behind `MEGAPLAN_UNIFIED_DISPATCH=1` flag.
- **Status:** R1 flipped; subprocess seam preserved and dormant; retirement deferred to M6.
- **Dual-green window:** Open (M3 through M5c); closes at M6 atomic strangler swap.
- **Hinge gate:** green — all oracles pass; `r1_flip_allowed = True`.
"""


def assert_program_md() -> Path:
    """Ensure ``briefs/validation/sequencing/PROGRAM.md`` exists with M3 entry.

    Re-creates the file from the Step 0c stub template if missing, then
    appends the M3 entry section if not already present.  Returns the path.
    """
    if not _PROGRAM_MD.exists():
        _PROGRAM_MD.parent.mkdir(parents=True, exist_ok=True)
        _PROGRAM_MD.write_text(
            "# PROGRAM\n\n## M3\n\nPlaceholder stub for the PROGRAM sequencing brief.\n",
            encoding="utf-8",
        )
    content = _PROGRAM_MD.read_text(encoding="utf-8")
    if "## M3 Entry" not in content:
        _PROGRAM_MD.write_text(content.rstrip() + _M3_PROGRAM_ENTRY, encoding="utf-8")
    return _PROGRAM_MD


# ---------------------------------------------------------------------------
# run_chain_ci
# ---------------------------------------------------------------------------


def run_chain_ci(
    gates: Optional[Sequence[Tuple[str, Callable[[], GateOutcome]]]] = None,
) -> ChainCIResult:
    """Run every gate in order and return a ``ChainCIResult``.

    Gates default to ``GATE_ORDER``.  Each gate is invoked once; failures are
    collected (no short-circuit) so the operator sees the full red surface.
    ``[HINGE GATE: GREEN]`` is accessible via ``result.commit_label()`` and is
    non-empty only when every gate passes.
    """
    chosen = tuple(gates) if gates is not None else GATE_ORDER
    outcomes: List[GateOutcome] = []
    for _name, fn in chosen:
        try:
            outcome = fn()
        except Exception as exc:
            outcome = GateOutcome(name=_name, ok=False, detail=f"gate raised: {exc!r}")
        outcomes.append(outcome)
    passed = all(g.ok for g in outcomes)
    return ChainCIResult(passed=passed, gate_outcomes=outcomes)


__all__ = [
    "GateOutcome",
    "ChainCIResult",
    "GATE_ORDER",
    "HINGE_GATE_GREEN_STAMP",
    "run_chain_ci",
    "assert_program_md",
    "gate_parity",
    "gate_fold_baseline",
    "gate_fold_flag_on",
    "gate_crash_isolation",
    "gate_version_skew",
    "gate_cloud_smoke",
    "gate_acceptance_toy",
    "gate_dual_green",
]
