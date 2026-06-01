"""T30 / Step 25 — chain-level hinge-gate tests.

Locks the public contract of ``megaplan.chain.hinge_gate``:

* ``run_hinge_gate`` aggregates every oracle into a ``HingeGateResult`` and
  reports ``r1_flip_allowed`` only on green.
* The synthetic red-gate dry-run exercises the full bounded escalation ladder
  (retry x2 -> bump_tier -> stop_chain + auto-ticket) without any human wait.
* Green gate never calls ``bump_tier`` or ``stop_chain``.
* The fold-equivalence oracle outcome is a thin wrapper over the
  ``fold_equivalence_oracle`` callable already used by T26 / T27.
* The pytest-driven oracles delegate to the existing T28/T29 test modules
  rather than reimplementing crash-isolation / version-skew assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan.chain import hinge_gate as hg
from megaplan.observability.fold import OracleFailure, OracleResult


pytestmark = pytest.mark.hinge_gate


# ---------------------------------------------------------------------------
# HingeGateResult shape
# ---------------------------------------------------------------------------


def test_hinge_gate_result_green_allows_r1_flip() -> None:
    result = hg.HingeGateResult(passed=True, failures=[], outcomes=[])
    assert result.r1_flip_allowed is True


def test_hinge_gate_result_red_blocks_r1_flip() -> None:
    failure = hg.OracleOutcome(name="x", ok=False, detail="boom")
    result = hg.HingeGateResult(passed=False, failures=[failure], outcomes=[failure])
    assert result.r1_flip_allowed is False


# ---------------------------------------------------------------------------
# run_hinge_gate aggregation
# ---------------------------------------------------------------------------


def test_run_hinge_gate_green_with_all_passing_oracles() -> None:
    calls = []

    def ok_a() -> hg.OracleOutcome:
        calls.append("a")
        return hg.OracleOutcome(name="a", ok=True)

    def ok_b() -> hg.OracleOutcome:
        calls.append("b")
        return hg.OracleOutcome(name="b", ok=True)

    result = hg.run_hinge_gate(oracles=[("a", ok_a), ("b", ok_b)])
    assert result.passed is True
    assert result.failures == []
    assert [o.name for o in result.outcomes] == ["a", "b"]
    assert calls == ["a", "b"]


def test_run_hinge_gate_collects_every_failure_without_short_circuit() -> None:
    def red_a() -> hg.OracleOutcome:
        return hg.OracleOutcome(name="a", ok=False, detail="diverged")

    def red_b() -> hg.OracleOutcome:
        return hg.OracleOutcome(name="b", ok=False, detail="crashed")

    def green_c() -> hg.OracleOutcome:
        return hg.OracleOutcome(name="c", ok=True)

    result = hg.run_hinge_gate(
        oracles=[("a", red_a), ("b", red_b), ("c", green_c)]
    )
    assert result.passed is False
    assert [f.name for f in result.failures] == ["a", "b"]
    assert [o.name for o in result.outcomes] == ["a", "b", "c"]


def test_run_hinge_gate_catches_raising_oracle() -> None:
    def boom() -> hg.OracleOutcome:
        raise RuntimeError("kaboom")

    result = hg.run_hinge_gate(oracles=[("boom", boom)])
    assert result.passed is False
    assert len(result.failures) == 1
    assert "kaboom" in result.failures[0].detail


def test_default_oracles_cover_all_four_axes() -> None:
    names = [name for name, _fn in hg.DEFAULT_ORACLES]
    assert names == [
        "fold_equivalence_baseline",
        "fold_equivalence_flag_on",
        "crash_isolation",
        "version_skew",
    ]


# ---------------------------------------------------------------------------
# Fold-equivalence oracle wrappers
# ---------------------------------------------------------------------------


def test_fold_equivalence_baseline_wrapper_green(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        hg, "fold_equivalence_oracle",
        lambda _path: OracleResult(passed=35, failed=0, total=35),
    )
    outcome = hg.fold_equivalence_baseline()
    assert outcome.ok is True
    assert outcome.name == "fold_equivalence_baseline"
    assert "35/35" in outcome.detail


def test_fold_equivalence_baseline_wrapper_red(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        hg, "fold_equivalence_oracle",
        lambda _path: OracleResult(
            passed=1,
            failed=1,
            total=2,
            failures=[OracleFailure(name="g1", reason="diverged", expected={"x": 1}, actual={"x": 2})],
        ),
    )
    outcome = hg.fold_equivalence_baseline()
    assert outcome.ok is False
    assert "g1" in outcome.detail and "diverged" in outcome.detail


def test_fold_equivalence_red_when_manifest_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(hg, "BASELINE_MANIFEST", tmp_path / "does-not-exist.json")
    outcome = hg.fold_equivalence_baseline()
    assert outcome.ok is False
    assert "missing manifest" in outcome.detail


# ---------------------------------------------------------------------------
# Bounded escalation ladder
# ---------------------------------------------------------------------------


def _green() -> hg.HingeGateResult:
    return hg.HingeGateResult(passed=True, failures=[], outcomes=[])


def _red() -> hg.HingeGateResult:
    f = hg.OracleOutcome(name="synthetic", ok=False, detail="forced red")
    return hg.HingeGateResult(passed=False, failures=[f], outcomes=[f])


def test_escalation_green_first_try_skips_ladder(tmp_path: Path) -> None:
    bump_calls = []
    stop_calls = []

    outcome = hg.run_with_escalation(
        run_gate=_green,
        bump_tier=lambda: bump_calls.append(1),
        stop_chain=lambda r: stop_calls.append(r),
        ticket_dir=tmp_path,
    )

    assert outcome.passed is True
    assert outcome.ticket_path is None
    assert bump_calls == [] and stop_calls == []
    assert len(outcome.steps) == 1
    assert outcome.steps[0].kind == "retry"
    assert outcome.steps[0].attempt == 0


def test_escalation_green_after_one_retry(tmp_path: Path) -> None:
    sequence = iter([_red(), _green()])
    bump_calls = []
    stop_calls = []

    outcome = hg.run_with_escalation(
        run_gate=lambda: next(sequence),
        bump_tier=lambda: bump_calls.append(1),
        stop_chain=lambda r: stop_calls.append(r),
        ticket_dir=tmp_path,
    )

    assert outcome.passed is True
    assert outcome.ticket_path is None
    assert bump_calls == [] and stop_calls == []
    assert [s.kind for s in outcome.steps] == ["retry", "retry"]


def test_synthetic_red_gate_exercises_full_ladder_without_human_wait(tmp_path: Path) -> None:
    """SC30 — synthetic red-gate dry-run hits retry x2 -> bump_tier -> stop_chain + auto-ticket."""
    gate_calls = []
    bump_calls = []
    stop_calls = []

    def always_red() -> hg.HingeGateResult:
        gate_calls.append(len(gate_calls))
        return _red()

    outcome = hg.run_with_escalation(
        run_gate=always_red,
        bump_tier=lambda: bump_calls.append(1),
        stop_chain=lambda r: stop_calls.append(r),
        ticket_dir=tmp_path,
    )

    # Ladder: initial + 2 retries + 1 post-bump retry = 4 gate runs.
    assert len(gate_calls) == 4
    # bump_tier fired exactly once, between retry-2 and stop_chain.
    assert bump_calls == [1]
    # stop_chain fired exactly once with the final red result.
    assert len(stop_calls) == 1
    assert stop_calls[0].passed is False

    assert outcome.passed is False
    assert outcome.final_result.passed is False
    # Step kinds in order.
    assert [s.kind for s in outcome.steps] == [
        "retry", "retry", "retry", "bump_tier", "stop_chain",
    ]

    # Auto-ticket landed under ticket_dir as JSON and is loadable.
    assert outcome.ticket_path is not None
    assert outcome.ticket_path.exists()
    payload = json.loads(outcome.ticket_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "hinge_gate_red"
    assert payload["ladder_exhausted"] is True
    assert any(f["name"] == "synthetic" for f in payload["failures"])


def test_escalation_does_not_auto_flip_r1() -> None:
    """Gate is sole-retirement-authority but never auto-flips the R1 bit."""
    # Green result merely ALLOWS the flip; nothing in the module mutates flag
    # state. We assert this by importing the module and checking that no flag
    # mutation symbol is exposed.
    forbidden = {"flip_r1", "enable_unified_dispatch", "set_flag"}
    assert forbidden.isdisjoint(set(dir(hg)))


def test_escalation_writes_ticket_only_after_ladder_exhausted(tmp_path: Path) -> None:
    """Green-after-bump must NOT write a ticket (ladder did not exhaust)."""
    sequence = iter([_red(), _red(), _red(), _green()])

    outcome = hg.run_with_escalation(
        run_gate=lambda: next(sequence),
        bump_tier=lambda: None,
        stop_chain=lambda r: pytest.fail("stop_chain must not fire on green-after-bump"),
        ticket_dir=tmp_path,
    )

    assert outcome.passed is True
    assert outcome.ticket_path is None
    assert list(tmp_path.glob("hinge_gate_red_*.json")) == []
