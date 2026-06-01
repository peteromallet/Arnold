"""T30 / Step 25 — chain-level hinge gate.

Runs every M3 hinge oracle and produces a single ``HingeGateResult``.  Owns the
bounded escalation ladder used by the chain runner when the gate fires red:

    retry x2  ->  bump profile/robustness one tier  ->  stop_chain + auto-ticket

The R1 authority flip is GATED on this result: green means the flip is
*allowed* (a separate operator action), red auto-halts the chain.  The gate
NEVER auto-flips R1 on its own (sole-retirement-authority contract).

Public surface:

* ``HingeGateResult`` — frozen dataclass with ``passed`` / ``failures``.
* ``OracleOutcome`` — per-oracle pass/fail row.
* ``run_hinge_gate`` — execute every default oracle once and return the result.
* ``run_with_escalation`` — wrap an oracle callable in the bounded ladder.
* ``DEFAULT_ORACLES`` — list of (name, callable) entries the runner uses.

The fold-equivalence oracles (baseline + flag-ON) call
``fold_equivalence_oracle`` from ``megaplan.observability.fold`` per MANIFEST.
Crash-isolation and version-skew oracles are surfaced via ``pytest -m
hinge_gate`` invocations against the dedicated ``tests/oracles/`` modules so
the gate runs the EXACT assertions T28/T29 already wrote (no reimplementation).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from megaplan.observability.fold import (
    OracleResult,
    fold_equivalence_oracle,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


BASELINE_MANIFEST = (
    REPO_ROOT / "tests" / "characterization" / "auto_drive_corpus" / "MANIFEST.json"
)
FLAG_ON_MANIFEST = REPO_ROOT / "tests" / "corpus" / "flag_on" / "MANIFEST.json"

CRASH_ISOLATION_TEST = REPO_ROOT / "tests" / "oracles" / "test_crash_isolation_oracle.py"
VERSION_SKEW_TEST = REPO_ROOT / "tests" / "oracles" / "test_version_skew_oracle.py"


@dataclass(frozen=True)
class OracleOutcome:
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class HingeGateResult:
    passed: bool
    failures: List[OracleOutcome] = field(default_factory=list)
    outcomes: List[OracleOutcome] = field(default_factory=list)

    @property
    def r1_flip_allowed(self) -> bool:
        """Green gate ALLOWS but does NOT auto-flip R1 authority."""
        return self.passed


# ---------------------------------------------------------------------------
# Built-in oracle callables
# ---------------------------------------------------------------------------


def _fold_equivalence_oracle(name: str, manifest: Path) -> OracleOutcome:
    if not manifest.exists():
        return OracleOutcome(name=name, ok=False, detail=f"missing manifest: {manifest}")
    result: OracleResult = fold_equivalence_oracle(manifest)
    if result.ok:
        return OracleOutcome(name=name, ok=True, detail=f"{result.passed}/{result.total} goldens")
    detail = "; ".join(
        f"{f.name}: expected={f.expected!r} actual={f.actual!r} ({f.reason})"
        for f in result.failures
    )
    return OracleOutcome(name=name, ok=False, detail=detail or "fold-equivalence diverged")


def fold_equivalence_baseline() -> OracleOutcome:
    return _fold_equivalence_oracle("fold_equivalence_baseline", BASELINE_MANIFEST)


def fold_equivalence_flag_on() -> OracleOutcome:
    return _fold_equivalence_oracle("fold_equivalence_flag_on", FLAG_ON_MANIFEST)


def _pytest_oracle(name: str, test_path: Path) -> OracleOutcome:
    if not test_path.exists():
        return OracleOutcome(name=name, ok=False, detail=f"missing test module: {test_path}")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", str(test_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return OracleOutcome(name=name, ok=True, detail="pytest ok")
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-10:])
    return OracleOutcome(name=name, ok=False, detail=f"pytest rc={proc.returncode}: {tail}")


def crash_isolation_oracle() -> OracleOutcome:
    return _pytest_oracle("crash_isolation", CRASH_ISOLATION_TEST)


def version_skew_oracle() -> OracleOutcome:
    return _pytest_oracle("version_skew", VERSION_SKEW_TEST)


# Ordered list — fold-equivalence baseline runs first (cheapest, most likely
# to surface a regression early) so a red there short-circuits expensive
# subprocess oracles in the escalation ladder.
DEFAULT_ORACLES: Tuple[Tuple[str, Callable[[], OracleOutcome]], ...] = (
    ("fold_equivalence_baseline", fold_equivalence_baseline),
    ("fold_equivalence_flag_on", fold_equivalence_flag_on),
    ("crash_isolation", crash_isolation_oracle),
    ("version_skew", version_skew_oracle),
)


def run_hinge_gate(
    oracles: Optional[Sequence[Tuple[str, Callable[[], OracleOutcome]]]] = None,
) -> HingeGateResult:
    """Run every oracle once and return a ``HingeGateResult``.

    ``oracles`` defaults to ``DEFAULT_ORACLES``. Each entry is invoked once;
    failures are collected (no short-circuit so the operator sees the full
    surface in one pass).
    """
    chosen = tuple(oracles) if oracles is not None else DEFAULT_ORACLES
    outcomes: List[OracleOutcome] = []
    failures: List[OracleOutcome] = []
    for _name, fn in chosen:
        try:
            outcome = fn()
        except Exception as exc:  # pragma: no cover - defensive: oracle should never raise
            outcome = OracleOutcome(name=_name, ok=False, detail=f"oracle raised: {exc!r}")
        outcomes.append(outcome)
        if not outcome.ok:
            failures.append(outcome)
    return HingeGateResult(
        passed=not failures,
        failures=failures,
        outcomes=outcomes,
    )


# ---------------------------------------------------------------------------
# Bounded escalation ladder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EscalationStep:
    kind: str  # "retry" | "bump_tier" | "stop_chain"
    attempt: int
    result: HingeGateResult


@dataclass(frozen=True)
class EscalationOutcome:
    passed: bool
    final_result: HingeGateResult
    steps: List[EscalationStep] = field(default_factory=list)
    ticket_path: Optional[Path] = None


def _write_auto_ticket(ticket_dir: Path, result: HingeGateResult, steps: Sequence[EscalationStep]) -> Path:
    ticket_dir.mkdir(parents=True, exist_ok=True)
    ticket_path = ticket_dir / f"hinge_gate_red_{int(time.time() * 1000)}.json"
    payload = {
        "kind": "hinge_gate_red",
        "ladder_exhausted": True,
        "failures": [
            {"name": f.name, "detail": f.detail} for f in result.failures
        ],
        "steps": [
            {"kind": s.kind, "attempt": s.attempt, "failures": [f.name for f in s.result.failures]}
            for s in steps
        ],
    }
    ticket_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return ticket_path


def run_with_escalation(
    run_gate: Callable[[], HingeGateResult] = run_hinge_gate,
    *,
    bump_tier: Optional[Callable[[], None]] = None,
    stop_chain: Optional[Callable[[HingeGateResult], None]] = None,
    ticket_dir: Optional[Path] = None,
    max_retries: int = 2,
) -> EscalationOutcome:
    """Run the gate under the bounded ladder.

    Ladder shape (locked by T30 contract):

    1. Run gate. Green -> return immediately.
    2. On red, retry up to ``max_retries`` times (default 2).
    3. Still red -> invoke ``bump_tier`` (one tier bump only) and retry once.
    4. Still red -> invoke ``stop_chain`` and write an auto-ticket JSON under
       ``ticket_dir`` (defaults to ``<repo>/.megaplan/tickets``).

    All four steps are no-human-wait so a synthetic red-gate dry-run can
    exercise the full ladder in a single test invocation.
    """
    if ticket_dir is None:
        ticket_dir = REPO_ROOT / ".megaplan" / "tickets"

    steps: List[EscalationStep] = []

    result = run_gate()
    steps.append(EscalationStep(kind="retry", attempt=0, result=result))
    if result.passed:
        return EscalationOutcome(passed=True, final_result=result, steps=steps)

    for attempt in range(1, max_retries + 1):
        result = run_gate()
        steps.append(EscalationStep(kind="retry", attempt=attempt, result=result))
        if result.passed:
            return EscalationOutcome(passed=True, final_result=result, steps=steps)

    if bump_tier is not None:
        bump_tier()
    result = run_gate()
    steps.append(EscalationStep(kind="bump_tier", attempt=max_retries + 1, result=result))
    if result.passed:
        return EscalationOutcome(passed=True, final_result=result, steps=steps)

    if stop_chain is not None:
        stop_chain(result)
    ticket = _write_auto_ticket(ticket_dir, result, steps)
    steps.append(EscalationStep(kind="stop_chain", attempt=max_retries + 2, result=result))
    return EscalationOutcome(
        passed=False, final_result=result, steps=steps, ticket_path=ticket
    )


__all__ = [
    "HingeGateResult",
    "OracleOutcome",
    "EscalationOutcome",
    "EscalationStep",
    "DEFAULT_ORACLES",
    "run_hinge_gate",
    "run_with_escalation",
    "fold_equivalence_baseline",
    "fold_equivalence_flag_on",
    "crash_isolation_oracle",
    "version_skew_oracle",
    "BASELINE_MANIFEST",
    "FLAG_ON_MANIFEST",
]
