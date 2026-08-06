"""Governed freshness vectors for CL2 ledger evidence.

Freshness is a **staleness / availability** signal only.  It never confers,
implies, or infers authority.  A ``FreshnessVector`` records how stale an
observed piece of evidence is and *why*; it carries no authority field and
no field whose incidental value (a legacy marker, a state-JSON blob, a
producer/model PID, or model prose) could be read as authorization.

Governance rules (enforced here and by the unit tests):

* Unavailable evidence (``EvidenceAvailability.UNAVAILABLE``) is surfaced as
  stale with reason ``"unavailable"``.
* Tombstoned evidence (``ParseStatus.TOMBSTONED``) is surfaced as stale with
  reason ``"tombstoned"`` — a tombstone marks *absence*, never authorization.
* Observed timestamps contribute an age-based staleness reason only when an
  explicit freshness window (``now`` + ``max_age_seconds``) is supplied.
* Briefing-required evidence that is unavailable or tombstoned blocks
  briefing (``required_for_briefing_unavailable``).

The marker set below is documented for defence-in-depth: every one of these
incidental fields is deliberately *ignored* by freshness classification.
They are not read, ranked, or promoted into any authority signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from arnold.critique_ledger.schemas import EvidenceAvailability, ParseStatus
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import AttemptEventType

# Payload discriminators carried on EXTERNAL_EFFECT_OUTCOME events.
_CL2_KIND = "cl2_kind"
_OCCURRENCE_KIND = "occurrence"
_LEGACY_KIND = "legacy_historical"
_ENVELOPE = "envelope"

# Incidental fields that MUST NOT be interpreted as authority by freshness
# classification.  Documented (and asserted by tests); never read for ranking.
_AUTHORITY_NEUTRAL_IGNORED_FIELDS: frozenset[str] = frozenset(
    {
        "derived_from_legacy",
        "producer_id",
        "model_id",
        "grant_ref",
        "authority",
        "accepted_for_cl2",
    }
)

REASON_TOMBSTONED = "tombstoned"
REASON_UNAVAILABLE = "unavailable"
REASON_OBSERVATION_EXCEEDED_MAX_AGE = "observation_exceeded_max_age"


@dataclass(frozen=True)
class FreshnessVector:
    """Staleness/availability signal for one observed occurrence.

    Fields:
        occurrence_id: producer-local identity of the occurrence.
        last_observed_at: the ``observed_at`` timestamp of the ledger event
            that carried this occurrence (observation time, not authority).
        evidence_class: the ``evidence_availability`` value of the occurrence.
        is_stale: whether the evidence is stale/unavailable for use.
        staleness_reason: machine-readable reason when ``is_stale`` is True;
            empty string when fresh.

    There is deliberately no authority field.  A stale vector is never an
    authorization, and a fresh vector is never an authorization either.
    """

    occurrence_id: str
    last_observed_at: str
    evidence_class: str
    is_stale: bool
    staleness_reason: str = ""


def _parse_instant(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp (with offset or trailing ``Z``)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_seconds(observed_at: str, now: str) -> float | None:
    """Return the age in seconds between ``observed_at`` and ``now``.

    Returns ``None`` when either timestamp cannot be parsed or when they
    carry incomparable timezone awareness.  Timestamps alone never establish
    authority; an unparseable timestamp simply disables age-based staleness.
    """
    observed = _parse_instant(observed_at)
    reference = _parse_instant(now)
    if observed is None or reference is None:
        return None
    # Make both offset-aware before subtracting so naive/aware mixing is safe.
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return (reference - observed).total_seconds()


def _classify_staleness(
    evidence_class: str,
    parse_status: str,
    observed_at: str,
    *,
    now: str | None,
    max_age_seconds: int | None,
) -> tuple[bool, str]:
    """Classify staleness from availability, tombstone, and observed age.

    Precedence: tombstone (absence) > unavailable > observation age.
    No incidental marker influences the result.
    """
    if parse_status == ParseStatus.TOMBSTONED.value:
        return True, REASON_TOMBSTONED
    if evidence_class == EvidenceAvailability.UNAVAILABLE.value:
        return True, REASON_UNAVAILABLE
    if now is not None and max_age_seconds is not None:
        age = _age_seconds(observed_at, now)
        if age is not None and age > max_age_seconds:
            return True, REASON_OBSERVATION_EXCEEDED_MAX_AGE
    return False, ""


class FreshnessTracker:
    """Compute governed freshness vectors over persisted occurrence events.

    The tracker reads ``EXTERNAL_EFFECT_OUTCOME`` events carrying an
    occurrence envelope (``cl2_kind`` ``occurrence`` or
    ``legacy_historical``) and emits staleness signals.  It is read-only and
    side-effect-free; it never infers authority from markers, state JSON,
    PIDs, or model prose.
    """

    def __init__(self, store: SqliteAttemptLedgerStore) -> None:
        self._store = store

    def _occurrence_envelopes(
        self, attempt_id: str
    ) -> Iterable[tuple[str, dict[str, Any]]]:
        """Yield ``(observed_at, envelope)`` for each occurrence outcome.

        Legacy-historical envelopes are included so their staleness is also
        governed — but they never acquire authority here (there is no
        authority field to acquire).
        """
        for event in self._store.read_events(attempt_id):
            if event.event_type != AttemptEventType.EXTERNAL_EFFECT_OUTCOME:
                continue
            payload = event.payload
            if not isinstance(payload, dict):
                continue
            kind = payload.get(_CL2_KIND)
            if kind not in (_OCCURRENCE_KIND, _LEGACY_KIND):
                continue
            envelope = payload.get(_ENVELOPE)
            if not isinstance(envelope, dict):
                continue
            yield event.observed_at, envelope

    def compute_freshness(
        self,
        attempt_id: str,
        *,
        now: str | None = None,
        max_age_seconds: int | None = None,
    ) -> list[FreshnessVector]:
        """Return one ``FreshnessVector`` per occurrence outcome.

        ``now``/``max_age_seconds`` are optional; when both are supplied an
        observation older than ``max_age_seconds`` seconds is flagged stale.
        """
        vectors: list[FreshnessVector] = []
        for observed_at, envelope in self._occurrence_envelopes(attempt_id):
            evidence_class = str(
                envelope.get(
                    "evidence_availability", EvidenceAvailability.RETAINED.value
                )
            )
            parse_status = str(
                envelope.get("parse_status", ParseStatus.SELECTED.value)
            )
            is_stale, reason = _classify_staleness(
                evidence_class,
                parse_status,
                observed_at,
                now=now,
                max_age_seconds=max_age_seconds,
            )
            vectors.append(
                FreshnessVector(
                    occurrence_id=str(envelope.get("occurrence_id", "")),
                    last_observed_at=observed_at,
                    evidence_class=evidence_class,
                    is_stale=is_stale,
                    staleness_reason=reason,
                )
            )
        return vectors

    def required_for_briefing_unavailable(
        self,
        attempt_id: str,
        evidence_class: str | None = None,
        *,
        now: str | None = None,
        max_age_seconds: int | None = None,
    ) -> bool:
        """Return True when briefing-required evidence blocks briefing.

        Only occurrences whose ``metadata.required_for_briefing`` is ``True``
        are considered.  If ``evidence_class`` is given, only occurrences
        whose ``evidence_availability`` equals it are considered.  Briefing
        is blocked when such evidence is unavailable or tombstoned (absent).
        Age-based staleness alone does NOT block briefing — the evidence
        still exists, it is merely old.
        """
        for observed_at, envelope in self._occurrence_envelopes(attempt_id):
            metadata = envelope.get("metadata", {})
            if not (
                isinstance(metadata, dict)
                and metadata.get("required_for_briefing") is True
            ):
                continue
            evidence_class_value = str(
                envelope.get(
                    "evidence_availability", EvidenceAvailability.RETAINED.value
                )
            )
            if (
                evidence_class is not None
                and evidence_class_value != evidence_class
            ):
                continue
            parse_status = str(
                envelope.get("parse_status", ParseStatus.SELECTED.value)
            )
            is_stale, reason = _classify_staleness(
                evidence_class_value,
                parse_status,
                observed_at,
                now=now,
                max_age_seconds=max_age_seconds,
            )
            if is_stale and reason in (REASON_UNAVAILABLE, REASON_TOMBSTONED):
                return True
        return False


__all__ = [
    "REASON_OBSERVATION_EXCEEDED_MAX_AGE",
    "REASON_TOMBSTONED",
    "REASON_UNAVAILABLE",
    "FreshnessTracker",
    "FreshnessVector",
]
