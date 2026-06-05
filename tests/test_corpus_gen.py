"""Regenerator test for the deterministic trace corpus.

Rebuilds all four fixtures by direct DriverOutcome construction (same
parameters as the generator script ``_gen_corpus.py``) and asserts
**byte-equality** with the committed files under
``tests/fixtures/corpus/``.

SD1 corpus-shape note:
  The brief's recover shape (blocked-retry-then-resume) is intentionally
  covered by the W5 substrate-swap self-test rather than a dedicated
  corpus trace.  Real-run capture is deferred to M1 (accepted debt).
  See also ``tests/fixtures/corpus/CORPUS_NOTES.md``.
"""

from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan.auto import DriverOutcome

# ---------------------------------------------------------------------------
# Canonical constructors — must match _gen_corpus.py exactly
# ---------------------------------------------------------------------------

CORPUS_DIR = Path(__file__).resolve().parent / "fixtures" / "corpus"


def _build_happy() -> DriverOutcome:
    return DriverOutcome(
        status="done",
        plan="corpus-happy",
        final_state="complete",
        iterations=3,
        reason="all milestones completed successfully",
        last_phase="execute",
        events=[
            {"kind": "phase", "phase": "plan"},
            {"kind": "phase", "phase": "execute"},
            {"kind": "phase", "phase": "review"},
        ],
        total_cost_usd=5.42,
        cost_cap_usd=50.0,
        context_retries_used=0,
        max_context_retries=3,
        external_retries_used=0,
        max_external_retries=3,
        blocked_retries_used=0,
        max_blocked_retries=3,
        blocking_reasons=[],
        tier_escalations_used=0,
        escalation_tier_pin=None,
    )


def _build_stall() -> DriverOutcome:
    return DriverOutcome(
        status="stalled",
        plan="corpus-stall",
        final_state="executing",
        iterations=7,
        reason="execute loop stalled: no progress after 5 consecutive iterations",
        last_phase="execute",
        events=[
            {"kind": "phase", "phase": "plan"},
            {"kind": "phase", "phase": "prep"},
            {"kind": "phase", "phase": "execute"},
            {"kind": "phase", "phase": "execute"},
            {"kind": "phase", "phase": "execute"},
            {"kind": "stall", "reason": "no progress", "consecutive": 5},
        ],
        total_cost_usd=12.87,
        cost_cap_usd=50.0,
        context_retries_used=0,
        max_context_retries=3,
        external_retries_used=0,
        max_external_retries=3,
        blocked_retries_used=0,
        max_blocked_retries=3,
        blocking_reasons=[],
        tier_escalations_used=0,
        escalation_tier_pin=None,
    )


def _build_blocked() -> DriverOutcome:
    return DriverOutcome(
        status="blocked",
        plan="corpus-blocked",
        final_state="waiting",
        iterations=4,
        reason="external dependency unavailable after retries",
        last_phase="execute",
        events=[
            {"kind": "phase", "phase": "plan"},
            {"kind": "phase", "phase": "execute"},
            {"kind": "blocked", "reason": "dependency timeout", "attempt": 1},
            {"kind": "blocked", "reason": "dependency timeout", "attempt": 2},
            {"kind": "blocked", "reason": "dependency timeout", "attempt": 3},
        ],
        total_cost_usd=8.15,
        cost_cap_usd=50.0,
        context_retries_used=0,
        max_context_retries=3,
        external_retries_used=0,
        max_external_retries=3,
        blocked_retries_used=3,
        max_blocked_retries=3,
        blocking_reasons=["dependency timeout"],
        tier_escalations_used=0,
        escalation_tier_pin=None,
    )


def _build_escalate() -> DriverOutcome:
    return DriverOutcome(
        status="escalated",
        plan="corpus-escalate",
        final_state="escalated",
        iterations=9,
        reason="escalation triggered after exhausting context and external retries",
        last_phase="execute",
        events=[
            {"kind": "phase", "phase": "plan"},
            {"kind": "phase", "phase": "execute"},
            {"kind": "retry", "type": "context", "attempt": 1},
            {"kind": "retry", "type": "context", "attempt": 2},
            {"kind": "retry", "type": "context", "attempt": 3},
            {"kind": "retry", "type": "external", "attempt": 1},
            {"kind": "escalate", "tier": 2, "reason": "retries exhausted"},
        ],
        total_cost_usd=23.41,
        cost_cap_usd=50.0,
        context_retries_used=3,
        max_context_retries=3,
        external_retries_used=1,
        max_external_retries=3,
        blocked_retries_used=0,
        max_blocked_retries=3,
        blocking_reasons=[],
        tier_escalations_used=2,
        escalation_tier_pin=2,
    )


# ---------------------------------------------------------------------------
# Byte-equality assertions
# ---------------------------------------------------------------------------


def _assert_byte_equal(filename: str, outcome: DriverOutcome) -> None:
    """Rebuild *outcome*, serialize, and compare byte-for-byte."""
    path = CORPUS_DIR / filename
    assert path.is_file(), f"corpus file missing: {path}"

    committed = path.read_bytes()
    regenerated = outcome.to_json().encode("utf-8")

    assert (
        regenerated == committed
    ), f"{filename}: regenerated output differs from committed file"


def test_happy_byte_equal() -> None:
    _assert_byte_equal("happy.json", _build_happy())


def test_execute_stall_byte_equal() -> None:
    _assert_byte_equal("execute_stall.json", _build_stall())


def test_blocked_retry_byte_equal() -> None:
    _assert_byte_equal("blocked_retry.json", _build_blocked())


def test_escalate_byte_equal() -> None:
    _assert_byte_equal("escalate.json", _build_escalate())
