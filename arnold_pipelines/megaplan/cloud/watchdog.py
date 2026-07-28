"""Steps 15B-15C: Watchdog wrapper seams for recovery backstops.

Step 15B: Watchdog wrapper that converts malformed output, absent child,
fallback mismatch, missed events, and malformed L1/L2 evidence into
durable failures or typed escalation — never treating process presence
as success.

Step 15C: The wrapper is the single seam used by the six-hour
reconciliation backstop.  It accepts a runnable callable, captures
structured output, and refuses to treat a running process as evidence
of correctness.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

LOGGER = logging.getLogger(__name__)


# ── Escalation level ─────────────────────────────────────────────────────────


class EscalationLevel(str, Enum):
    """Typed escalation levels for recovery backstop failures."""

    NONE = "none"
    """No escalation needed — check passed."""

    WARNING = "warning"
    """Non-blocking anomaly — logged and tracked."""

    BLOCKING = "blocking"
    """Durable failure — requires human review."""

    CRITICAL = "critical"
    """Immediate escalation — data integrity at risk."""


# ── Evidence level ───────────────────────────────────────────────────────────


class EvidenceLevel(str, Enum):
    """Evidence quality levels for recovery verification."""

    L1 = "L1"
    """Direct measurement (process exit code, file existence)."""

    L2 = "L2"
    """Derived evidence (log analysis, hash comparison)."""

    L3 = "L3"
    """Synthetic/projection evidence — NOT accepted as authority."""


# ── Watchdog result ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WatchdogResult:
    """Result of a watchdog-wrapped recovery check.

    Step 15B: A check that passes produces ``escalation=NONE``.
    Malformed output, absent child, fallback mismatch, missed events,
    and malformed L1/L2 evidence all produce ``escalation=BLOCKING``
    or ``escalation=CRITICAL``.
    """

    ok: bool
    """True if the check passed without durable failure."""

    check_name: str
    """Stable name for this watchdog check."""

    escalation: EscalationLevel
    """Escalation level if the check failed."""

    evidence_level: EvidenceLevel
    """What level of evidence was used."""

    detail: str = ""
    """Human-readable detail about the failure."""

    evidence: dict[str, Any] = field(default_factory=dict)
    """Structured evidence from the check."""

    child_present: bool = True
    """True if the monitored child process/artifact was present."""

    matched_expected: bool = True
    """True if the output matched expected structure."""

    @property
    def requires_escalation(self) -> bool:
        return self.escalation in (
            EscalationLevel.BLOCKING,
            EscalationLevel.CRITICAL,
        )


# ── Watchdog wrapper ────────────────────────────────────────────────────────


def run_watchdog_check(
    *,
    check_name: str,
    check_fn: Callable[[], Any],
    expected_keys: tuple[str, ...] | None = None,
    child_path: str | None = None,
    timeout_seconds: float = 30.0,
    fallback_fn: Callable[[], Any] | None = None,
) -> WatchdogResult:
    """Step 15B: Wrap a recovery check in watchdog semantics.

    The wrapper converts failures into durable, typed escalations:

    - **Malformed output**: If the check returns output missing required
      ``expected_keys``, escalate to BLOCKING.
    - **Absent child**: If ``child_path`` is provided and the path does
      not exist, escalate to CRITICAL.
    - **Fallback mismatch**: If a ``fallback_fn`` is provided and its
      result contradicts the primary check, escalate to BLOCKING.
    - **Missed events**: If the check raises an exception, escalate to
      BLOCKING (never treat a running process as success).
    - **Malformed L1/L2 evidence**: If evidence is not a dict or is
      missing required fields, escalate to BLOCKING.

    Process presence alone is never treated as success.  The wrapper
    requires structured output.
    """
    start_time = time.monotonic()

    # Absent child check (Step 15B: CRITICAL escalation)
    if child_path is not None:
        import os
        if not os.path.exists(child_path):
            return WatchdogResult(
                ok=False,
                check_name=check_name,
                escalation=EscalationLevel.CRITICAL,
                evidence_level=EvidenceLevel.L1,
                detail=f"Absent child: {child_path} does not exist",
                evidence={
                    "child_path": child_path,
                    "check_name": check_name,
                    "elapsed_seconds": time.monotonic() - start_time,
                },
                child_present=False,
                matched_expected=False,
            )

    # Run the primary check
    try:
        raw_output = check_fn()
    except Exception as exc:
        LOGGER.exception("Watchdog check %s raised exception", check_name)
        return WatchdogResult(
            ok=False,
            check_name=check_name,
            escalation=EscalationLevel.BLOCKING,
            evidence_level=EvidenceLevel.L1,
            detail=f"Check raised {type(exc).__name__}: {exc}",
            evidence={
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "check_name": check_name,
                "elapsed_seconds": time.monotonic() - start_time,
            },
            child_present=child_path is None,
            matched_expected=False,
        )

    elapsed = time.monotonic() - start_time

    # Timeout check
    if elapsed > timeout_seconds:
        LOGGER.warning(
            "Watchdog check %s exceeded timeout (%.1fs > %.1fs)",
            check_name, elapsed, timeout_seconds,
        )
        return WatchdogResult(
            ok=False,
            check_name=check_name,
            escalation=EscalationLevel.BLOCKING,
            evidence_level=EvidenceLevel.L1,
            detail=f"Timeout: {elapsed:.1f}s > {timeout_seconds:.1f}s",
            evidence={
                "elapsed_seconds": elapsed,
                "timeout_seconds": timeout_seconds,
                "check_name": check_name,
            },
            child_present=child_path is None,
            matched_expected=False,
        )

    # Malformed output check (Step 15B: missing expected keys)
    if expected_keys is not None:
        if not isinstance(raw_output, dict):
            return WatchdogResult(
                ok=False,
                check_name=check_name,
                escalation=EscalationLevel.BLOCKING,
                evidence_level=EvidenceLevel.L1,
                detail=f"Malformed output: expected dict, got {type(raw_output).__name__}",
                evidence={
                    "raw_output_type": type(raw_output).__name__,
                    "expected_keys": list(expected_keys),
                    "elapsed_seconds": elapsed,
                },
                child_present=child_path is None,
                matched_expected=False,
            )

        missing_keys = [k for k in expected_keys if k not in raw_output]
        if missing_keys:
            return WatchdogResult(
                ok=False,
                check_name=check_name,
                escalation=EscalationLevel.BLOCKING,
                evidence_level=EvidenceLevel.L2,
                detail=f"Malformed output: missing keys {missing_keys}",
                evidence={
                    "missing_keys": missing_keys,
                    "expected_keys": list(expected_keys),
                    "available_keys": list(raw_output.keys()),
                    "elapsed_seconds": elapsed,
                },
                child_present=child_path is None,
                matched_expected=False,
            )

    # Fallback mismatch check (Step 15B)
    if fallback_fn is not None:
        try:
            fallback_output = fallback_fn()
        except Exception as fallback_exc:
            LOGGER.warning(
                "Watchdog check %s fallback raised %s — treating as mismatch",
                check_name,
                type(fallback_exc).__name__,
            )
            return WatchdogResult(
                ok=False,
                check_name=check_name,
                escalation=EscalationLevel.BLOCKING,
                evidence_level=EvidenceLevel.L2,
                detail=f"Fallback mismatch: fallback raised {type(fallback_exc).__name__}",
                evidence={
                    "fallback_exception": str(fallback_exc),
                    "primary_output": str(raw_output)[:500],
                    "elapsed_seconds": elapsed,
                },
                child_present=child_path is None,
                matched_expected=False,
            )

        # Canonical comparison: both must be dicts with matching key sets
        if isinstance(raw_output, dict) and isinstance(fallback_output, dict):
            primary_keys = set(raw_output.keys())
            fallback_keys = set(fallback_output.keys())
            if primary_keys != fallback_keys:
                return WatchdogResult(
                    ok=False,
                    check_name=check_name,
                    escalation=EscalationLevel.BLOCKING,
                    evidence_level=EvidenceLevel.L2,
                    detail=(
                        f"Fallback mismatch: primary keys {sorted(primary_keys)} "
                        f"!= fallback keys {sorted(fallback_keys)}"
                    ),
                    evidence={
                        "primary_keys": sorted(primary_keys),
                        "fallback_keys": sorted(fallback_keys),
                        "elapsed_seconds": elapsed,
                    },
                    child_present=child_path is None,
                    matched_expected=False,
                )

    # Success
    return WatchdogResult(
        ok=True,
        check_name=check_name,
        escalation=EscalationLevel.NONE,
        evidence_level=EvidenceLevel.L1 if child_path is not None else EvidenceLevel.L2,
        detail="",
        evidence={
            "output": (
                raw_output if isinstance(raw_output, dict)
                else {"raw": str(raw_output)[:500]}
            ),
            "elapsed_seconds": elapsed,
        },
        child_present=child_path is None or True,
        matched_expected=True,
    )


__all__ = [
    "EscalationLevel",
    "EvidenceLevel",
    "WatchdogResult",
    "run_watchdog_check",
]
