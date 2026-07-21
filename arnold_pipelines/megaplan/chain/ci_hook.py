"""T33 / Step 28 — M3 chain CI hook.

Wires every M3 hinge gate in the mandated order and produces a single
``ChainCIResult``.  The commit-message stamp ``[HINGE GATE: GREEN]`` is
emitted ONLY when every gate passes; any red gate produces an unlabelled
result so the milestone commit is never falsely stamped.

Gate order (locked by T33 contract — extended T43 for M5d, T6 for M5):

 1. parity              — workflow-topology parity gate (T10)
 2. fold_baseline       — fold-equivalence oracle, baseline MANIFEST (T26)
 3. fold_flag_on        — fold-equivalence oracle, flag-ON MANIFEST (T26)
 4. crash_isolation     — subprocess crash-isolation oracle (T28)
 5. cloud_smoke         — cloud phase_command shim (T17)
 7. acceptance_toy      — N-queens backtrack-solver acceptance toy (T31)
 8. dual_green          — dual-green strangler guard (T32)
 9. supervisor_purity   — M5d supervisor AST purity gate (T43)
10. oracle_acceptance   — oracle acceptance gate (M5, file-path aggregation)

Old-path retention (T43 doc)::
  The legacy chain orchestrator (megaplan/chain/__init__.py) and bakeoff
  orchestrator (megaplan/bakeoff/) are **not deleted** in M5d.  Both remain
  the default execution path behind ``MEGAPLAN_SUPERVISOR_TIER=0`` (or unset).

Retirement gate (T43 doc)::
  Old chain/bakeoff code retirement requires a later dual-green window plus
  a passing oracle pass.  No retirement may happen without:
  * dual-green (flag-off legacy path AND flag-on supervisor path both green)
  * replay oracle pass (boundary-trace corpus matches between old and new substrates)

Stub-survival:
  ``assert_program_md()`` ensures ``briefs/validation/sequencing/PROGRAM.md``
  exists and carries an M3 entry.  Re-created from Step 0c template if the
  file is missing.

Public surface:

* ``GateOutcome``           — per-gate pass/fail row.
* ``ChainCIResult``        — frozen dataclass; ``passed`` / ``gate_outcomes``.
* ``run_chain_ci``         — execute every gate once and return the result.
* ``commit_label``         — returns ``"[HINGE GATE: GREEN]"`` iff result is green.
* ``assert_program_md``     — stub-survival guard for PROGRAM.md.
* ``GATE_ORDER``            — ordered tuple of (gate_name, callable) pairs.
* ``gate_supervisor_purity`` — M5d supervisor AST purity gate (T43).
* ``gate_oracle_acceptance`` — M5 oracle acceptance gate (file-path aggregation).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from arnold_pipelines.megaplan.observability.fold import fold_equivalence_oracle
from arnold_pipelines.megaplan.chain.wbc import (
    CHAIN_CI_SURFACE,
    CHAIN_CI_WRITER_ID,
    ChainWbcRule,
    validate_chain_wbc_transition,
)

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
_CLOUD_SMOKE_TEST = (
    REPO_ROOT / "tests" / "cloud" / "test_phase_command_shim.py"
)
_ACCEPTANCE_TOY_TEST = (
    REPO_ROOT / "acceptance" / "backtrack_solver" / "tests" / "test_nqueens.py"
)

_PROGRAM_MD = (
    REPO_ROOT / "briefs" / "validation" / "sequencing" / "PROGRAM.md"
)

# ---------------------------------------------------------------------------
# Oracle acceptance gate targets (file-path aggregation — SD1)
# ---------------------------------------------------------------------------

_ORACLE_ACCEPTANCE_TARGETS: Tuple[Path, ...] = (
    # Parity-class oracles (tests/oracles/ + tests/oracle/)
    REPO_ROOT / "tests" / "oracles" / "test_replay_oracle.py",
    REPO_ROOT / "tests" / "oracles" / "test_crash_isolation_oracle.py",
    REPO_ROOT / "tests" / "oracles" / "test_budget_authority_oracle.py",
    REPO_ROOT / "tests" / "oracles" / "test_capacity_lease_two_tenant_oracle.py",
    REPO_ROOT / "tests" / "oracles" / "test_effect_ledger_replay_oracle.py",
    REPO_ROOT / "tests" / "oracles" / "test_evaluand_transaction_boundary_oracle.py",
    REPO_ROOT / "tests" / "oracles" / "test_journal_join_key_oracle.py",
    REPO_ROOT / "tests" / "oracles" / "test_calibration_loop_oracle.py",
    REPO_ROOT / "tests" / "oracles" / "test_evaluand_replay_oracle.py",
    REPO_ROOT / "tests" / "oracle" / "test_dual_run_oracle.py",
    REPO_ROOT / "tests" / "oracle" / "test_m5d_substrate_swap.py",
    # Phase-2 extraction-adjacent caller suites (SD2)
    REPO_ROOT / "tests" / "test_oracle_backend.py",
    REPO_ROOT / "tests" / "test_evidence_contract.py",
    REPO_ROOT / "tests" / "test_green_suite_delta.py",
    REPO_ROOT / "tests" / "test_completion_contract.py",
    REPO_ROOT / "tests" / "test_authority_readers.py",
    REPO_ROOT / "tests" / "arnold" / "pipeline" / "test_types_enums_identity.py",
    REPO_ROOT / "tests" / "characterization" / "test_pipeline_golden.py",
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
    validation_evidence: dict[str, object] | None = None

    @property
    def failures(self) -> List[GateOutcome]:
        return [g for g in self.gate_outcomes if not g.ok]

    def commit_label(self) -> str:
        """Return the hinge-gate stamp iff all gates are green."""
        validated = (
            bool(self.validation_evidence.get("rules"))
            if isinstance(self.validation_evidence, dict)
            else self.passed
        )
        return HINGE_GATE_GREEN_STAMP if self.passed and validated else ""


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



def gate_cloud_smoke() -> GateOutcome:
    """Cloud phase_command shim (T17)."""
    return _pytest_gate("cloud_smoke", _CLOUD_SMOKE_TEST)


def gate_acceptance_toy() -> GateOutcome:
    """N-queens backtrack-solver acceptance toy (T31)."""
    return _pytest_gate("acceptance_toy", _ACCEPTANCE_TOY_TEST)


def gate_dual_green() -> GateOutcome:
    """Dual-green strangler guard (T32)."""
    from arnold_pipelines.megaplan.chain.m3_dual_green import run_dual_green

    result = run_dual_green()
    if result.passed:
        return GateOutcome(name="dual_green", ok=True, detail="flag-OFF + flag-ON both green")
    parts = []
    if not result.flag_off_ok:
        parts.append("flag-OFF red")
    if not result.flag_on_ok:
        parts.append("flag-ON red")
    return GateOutcome(name="dual_green", ok=False, detail="; ".join(parts))


def gate_supervisor_purity() -> GateOutcome:
    """M5d supervisor AST purity gate (T43).

    Runs ``run_m5_eval_gates()`` which includes:
    * ``check_supervisor_source_purity()`` — no STATE_* imports/usages or
      force-proceed references in supervisor source files.
    * Plus the existing M5 eval gates (bare-float judgments, second journals,
      calibration purity, SDK state mechanism purity, better-join purity).

    This gate does NOT delete old chain/bakeoff code; retirement requires
    a later dual-green window plus a passing replay oracle pass.
    """
    from arnold_pipelines.megaplan.chain.m5_eval_gates import run_m5_eval_gates, format_findings

    result = run_m5_eval_gates()
    if result.passed:
        return GateOutcome(name="supervisor_purity", ok=True, detail="no findings")
    detail = format_findings(result.findings)
    return GateOutcome(name="supervisor_purity", ok=False, detail=detail)


def gate_oracle_acceptance() -> GateOutcome:
    """Oracle acceptance gate (M5) — file-path aggregation per SD1.

    Runs all oracle tests AND Phase-2 extraction-adjacent caller suites
    in a single pytest invocation.  Marker expressions are intentionally
    NOT used because ``crash_isolation``/``version_skew`` markers are
    registered but unapplied — a marker expression would silently skip
    three of five parity classes.
    """
    missing = [p for p in _ORACLE_ACCEPTANCE_TARGETS if not p.exists()]
    if missing:
        return GateOutcome(
            name="oracle_acceptance", ok=False,
            detail=f"missing targets: {', '.join(str(m) for m in missing)}",
        )
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"]
        + [str(p) for p in _ORACLE_ACCEPTANCE_TARGETS],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return GateOutcome(name="oracle_acceptance", ok=True, detail="pytest ok")
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-10:])
    return GateOutcome(name="oracle_acceptance", ok=False, detail=f"rc={proc.returncode}: {tail}")


# ---------------------------------------------------------------------------
# Ordered gate list (T33 contract extended by T43 — do not reorder)
# ---------------------------------------------------------------------------


GATE_ORDER: Tuple[Tuple[str, Callable[[], GateOutcome]], ...] = (
    ("parity", gate_parity),
    ("fold_baseline", gate_fold_baseline),
    ("fold_flag_on", gate_fold_flag_on),
    ("crash_isolation", gate_crash_isolation),
    ("cloud_smoke", gate_cloud_smoke),
    ("acceptance_toy", gate_acceptance_toy),
    ("dual_green", gate_dual_green),
    ("supervisor_purity", gate_supervisor_purity),
    ("oracle_acceptance", gate_oracle_acceptance),
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
    validation_evidence = validate_chain_wbc_transition(
        writer_id=CHAIN_CI_WRITER_ID,
        surface_name=CHAIN_CI_SURFACE,
        transition_name="chain_ci_result",
        subject="green" if passed else "red",
        source_path=Path(__file__),
        project_dir=REPO_ROOT,
        rules=(
            ChainWbcRule(
                "gate_count",
                len(chosen),
                len(outcomes),
                len(outcomes) == len(chosen),
            ),
            ChainWbcRule(
                "gate_names_unique",
                True,
                len({outcome.name for outcome in outcomes}) == len(outcomes),
                len({outcome.name for outcome in outcomes}) == len(outcomes),
            ),
            ChainWbcRule(
                "green_label_requires_all_green",
                passed,
                all(outcome.ok for outcome in outcomes),
                all(outcome.ok for outcome in outcomes) == passed,
            ),
        ),
        extra={
            "gate_names": [outcome.name for outcome in outcomes],
            "failed_gates": [outcome.name for outcome in outcomes if not outcome.ok],
        },
    )
    return ChainCIResult(
        passed=passed,
        gate_outcomes=outcomes,
        validation_evidence=validation_evidence,
    )


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
    "gate_cloud_smoke",
    "gate_acceptance_toy",
    "gate_dual_green",
    "gate_supervisor_purity",
    "gate_oracle_acceptance",
]
