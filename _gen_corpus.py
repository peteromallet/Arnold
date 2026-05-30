"""[DEPRECATED — M2.5] This script generates the old-style prototype fixtures
under ``tests/fixtures/corpus/``.  It is superseded by the M2.5 characterization
corpus in ``tests/characterization/auto_drive_corpus/``, regenerated via::

    pytest tests/characterization/test_auto_drive.py --write-fixture -q

The four prototype JSON files are retained for backwards reference only and are
NOT the oracle.  This script's behavior is preserved verbatim — no logic
changes.

One-shot corpus generator — run once to populate tests/fixtures/corpus/.

All traces are built by direct DriverOutcome construction (no driver
state-machine replay, no Date.now/random) so the output is deterministic.

SD1 corpus-shape note:
  The brief's recover shape (blocked-retry-then-resume) is intentionally
  covered by the W5 substrate-swap self-test rather than a dedicated
  corpus trace.  Real-run capture is deferred to M1 (accepted debt).
"""

from megaplan.auto import DriverOutcome

CORPUS_DIR = "tests/fixtures/corpus"


def _write(name: str, outcome: DriverOutcome) -> None:
    path = f"{CORPUS_DIR}/{name}"
    with open(path, "w") as fh:
        fh.write(outcome.to_json())
    print(f"  wrote {path}")


def main() -> None:
    print("Generating corpus traces …")

    # (a) happy.json — clean completion
    _write(
        "happy.json",
        DriverOutcome(
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
        ),
    )

    # (b) execute_stall.json — stalled with stall metadata
    _write(
        "execute_stall.json",
        DriverOutcome(
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
        ),
    )

    # (c) blocked_retry.json — blocked with blocked_retries_used > 0
    _write(
        "blocked_retry.json",
        DriverOutcome(
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
        ),
    )

    # (d) escalate.json — escalated with tier_escalations_used > 0
    _write(
        "escalate.json",
        DriverOutcome(
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
        ),
    )

    print("Done.")


if __name__ == "__main__":
    main()
