"""Pure event-sourced replay engine for the Critique Ledger domain.

Provides custody validation, ordered append-only reconciliation,
disposition application, manifest construction, domain briefing,
and read-only reviser/gate projections.

All functions are pure: they accept frozen dataclass instances and
return plain dicts or frozen dataclasses. No side effects, no I/O,
no mutation of lifecycle state.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from arnold.critique_ledger.schemas import (
    BRIEFING_BUDGETS,
    Authority,
    ContextMode,
    CritiqueOccurrenceEnvelope,
    DispositionFamily,
    DomainBriefingEnvelope,
    EvidenceAvailability,
    FindingDispositionEvent,
    FindingReconciliationEvent,
    LedgerRevisionManifest,
    ParseStatus,
    Relationship,
    SCHEMA_VERSION,
    canonical_hash,
)
from arnold.critique_ledger.freshness import compute_input_hash


# ══════════════════════════════════════════════════════════════════════
# Failure modes (14+ typed failure modes)
# ══════════════════════════════════════════════════════════════════════


class FailureMode(str, Enum):
    """Typed failure modes for semantic loop operations.

    Each failure mode maps to a specific validation failure that
    occurs *before* reviser or gate projection. Downstream consumers
    must not receive partial or invalid projections.
    """

    # Custody failures
    CUSTODY_NO_RECEIPT = "CUSTODY_NO_RECEIPT"
    CUSTODY_RECEIPT_CHAIN_BROKEN = "CUSTODY_RECEIPT_CHAIN_BROKEN"
    CUSTODY_PRODUCER_UNKNOWN = "CUSTODY_PRODUCER_UNKNOWN"
    CUSTODY_UNAVAILABLE_EVIDENCE = "CUSTODY_UNAVAILABLE_EVIDENCE"

    # Occurrence failures
    OCCURRENCE_PARSE_FAILED = "OCCURRENCE_PARSE_FAILED"
    OCCURRENCE_DUPLICATE_ID = "OCCURRENCE_DUPLICATE_ID"
    OCCURRENCE_MISSING_ID = "OCCURRENCE_MISSING_ID"
    OCCURRENCE_UNMAPPED = "OCCURRENCE_UNMAPPED"
    OCCURRENCE_MULTIPLY_MAPPED = "OCCURRENCE_MULTIPLY_MAPPED"
    SCHEMA_INCOMPATIBLE = "SCHEMA_INCOMPATIBLE"
    OWNERSHIP_MISSING = "OWNERSHIP_MISSING"
    START_PERSISTENCE_FAILED = "START_PERSISTENCE_FAILED"
    ATTEMPT_DROPPED = "ATTEMPT_DROPPED"
    TERMINAL_OUTCOME_INVALID = "TERMINAL_OUTCOME_INVALID"
    TERMINAL_PERSISTENCE_FAILED = "TERMINAL_PERSISTENCE_FAILED"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    TOMBSTONE_INVALID = "TOMBSTONE_INVALID"

    # Reconciliation failures
    RECONCILIATION_ORPHAN_OCCURRENCE = "RECONCILIATION_ORPHAN_OCCURRENCE"
    RECONCILIATION_DUPLICATE_EVENT = "RECONCILIATION_DUPLICATE_EVENT"
    RECONCILIATION_MISSING_ID = "RECONCILIATION_MISSING_ID"
    RECONCILIATION_INFERRED_SAMENESS = "RECONCILIATION_INFERRED_SAMENESS"
    RECONCILIATION_OUT_OF_ORDER = "RECONCILIATION_OUT_OF_ORDER"
    RECONCILIATION_UNKNOWN_RELATIONSHIP = "RECONCILIATION_UNKNOWN_RELATIONSHIP"

    # Disposition failures
    DISPOSITION_ORPHAN_FINDING = "DISPOSITION_ORPHAN_FINDING"
    DISPOSITION_DUPLICATE_EVENT = "DISPOSITION_DUPLICATE_EVENT"
    DISPOSITION_UNKNOWN_FAMILY = "DISPOSITION_UNKNOWN_FAMILY"
    DISPOSITION_MISSING_ID = "DISPOSITION_MISSING_ID"
    DISPOSITION_INCOMPLETE = "DISPOSITION_INCOMPLETE"
    CLOSURE_UNSUPPORTED = "CLOSURE_UNSUPPORTED"

    # CL4 (Plan Step 5): per-family field-presence failures. Each of the
    # seven non-closure disposition families carries a specific required
    # field so a finding cannot disappear behind a malformed disposition.
    # UNKNOWN is a valid terminal judgment and carries no extra requirement,
    # so it has no dedicated member here. The two closure families
    # (RESOLVED_VERIFIED / legacy RESOLVED) are gated by the closure rules
    # in Step 6, not by these field-presence checks.
    ACTED_ON_MISSING_ACTION = "ACTED_ON_MISSING_ACTION"
    IGNORED_MISSING_REOPEN_PREDICATE = "IGNORED_MISSING_REOPEN_PREDICATE"
    DEFERRED_MISSING_REOPEN_PREDICATE = "DEFERRED_MISSING_REOPEN_PREDICATE"
    ACCEPTED_RISK_MISSING_RATIONALE = "ACCEPTED_RISK_MISSING_RATIONALE"
    REJECTED_MISSING_REASON_SUBCODE = "REJECTED_MISSING_REASON_SUBCODE"
    DUPLICATE_MISSING_CANONICAL_REF = "DUPLICATE_MISSING_CANONICAL_REF"

    # Manifest failures
    MANIFEST_EMPTY_INPUT_SET = "MANIFEST_EMPTY_INPUT_SET"
    MANIFEST_DOMAIN_INCOMPLETE = "MANIFEST_DOMAIN_INCOMPLETE"
    PRIOR_REVISION_CHAIN_BROKEN = "PRIOR_REVISION_CHAIN_BROKEN"

    # Briefing failures
    BRIEFING_BUDGET_EXCEEDED = "BRIEFING_BUDGET_EXCEEDED"
    BRIEFING_DOMAIN_FLOOR_UNMET = "BRIEFING_DOMAIN_FLOOR_UNMET"
    BRIEFING_INPUT_UNAVAILABLE = "BRIEFING_INPUT_UNAVAILABLE"
    REPLAY_PROJECTION_MISMATCH = "REPLAY_PROJECTION_MISMATCH"


# ══════════════════════════════════════════════════════════════════════
# Exception
# ══════════════════════════════════════════════════════════════════════


class SemanticLoopError(Exception):
    """Raised when the semantic loop encounters a typed failure.

    Carries a FailureMode and optional detail so callers can
    distinguish between different failure classes without
    string-matching.
    """

    def __init__(
        self,
        mode: FailureMode | str,
        detail: str = "",
        failures: list[dict[str, Any]] | None = None,
    ) -> None:
        if isinstance(mode, str):
            mode = FailureMode(mode)
        self.mode = mode
        self.detail = detail
        self.failures = failures or []
        super().__init__(f"[{mode.value}] {detail}")


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

_VALID_DISPOSITION_FAMILIES = frozenset(e.value for e in DispositionFamily)

# CL4 (Plan Step 5): per-family field-presence rules. Each of the seven
# non-closure disposition families requires at least one specific field so a
# finding cannot be silently dropped behind a malformed disposition. UNKNOWN
# is a valid terminal judgment with no extra requirement and is deliberately
# absent here. The closure families (RESOLVED_VERIFIED and the legacy
# RESOLVED) are gated by the closure-evidence rules (Step 6), not by this
# table. Each rule maps the family value to a (FailureMode, predicate)
# pair; the predicate inspects the disposition event for the required field.
_DUPLICATE_CANONICAL_REF_KEYS = (
    "canonical_finding_id",
    "canonical_finding_ref",
    "canonical_ref",
)


def _has_duplicate_canonical_ref(disp: FindingDispositionEvent) -> bool:
    """Return True if the disposition metadata carries a canonical-finding
    reference, used to satisfy the DUPLICATE family's field-presence rule."""
    meta = disp.metadata or {}
    return any(meta.get(key) for key in _DUPLICATE_CANONICAL_REF_KEYS)


def _disposition_field_presence_failure(
    disp: FindingDispositionEvent,
) -> tuple[FailureMode, str] | None:
    """Return the (FailureMode, detail) for a missing required field on the
    disposition, or ``None`` when the disposition satisfies its family's
    field-presence rule.

    Only the seven non-closure families are checked here. The two closure
    families and the legacy ``RESOLVED`` value are gated by the closure
    rules and intentionally produce no field-presence failure.
    """
    family = disp.family
    if family == DispositionFamily.ACTED_ON.value:
        if not disp.action_taken or not disp.action_description:
            return (
                FailureMode.ACTED_ON_MISSING_ACTION,
                "ACTED_ON disposition requires action_taken and "
                "action_description",
            )
    elif family == DispositionFamily.IGNORED.value:
        if not disp.reopen_predicate:
            return (
                FailureMode.IGNORED_MISSING_REOPEN_PREDICATE,
                "IGNORED disposition requires a reopen_predicate",
            )
    elif family == DispositionFamily.DEFERRED.value:
        if not disp.reopen_predicate:
            return (
                FailureMode.DEFERRED_MISSING_REOPEN_PREDICATE,
                "DEFERRED disposition requires a reopen_predicate",
            )
    elif family == DispositionFamily.ACCEPTED_RISK.value:
        if not disp.reopen_predicate:
            return (
                FailureMode.ACCEPTED_RISK_MISSING_RATIONALE,
                "ACCEPTED_RISK disposition requires a reopen_predicate "
                "(risk-acceptance rationale)",
            )
    elif family == DispositionFamily.REJECTED.value:
        if not disp.reason_subcode:
            return (
                FailureMode.REJECTED_MISSING_REASON_SUBCODE,
                "REJECTED disposition requires a reason_subcode",
            )
    elif family == DispositionFamily.DUPLICATE.value:
        if not _has_duplicate_canonical_ref(disp):
            return (
                FailureMode.DUPLICATE_MISSING_CANONICAL_REF,
                "DUPLICATE disposition requires a canonical-finding ref "
                "in metadata",
            )
    return None

# Families that count as "open" (not resolved, not blocked)
_OPEN_FAMILIES = frozenset({
    DispositionFamily.ACTED_ON.value,
    DispositionFamily.IGNORED.value,
    DispositionFamily.DEFERRED.value,
})

# Families that count as "blocked"
_BLOCKED_FAMILIES = frozenset({
    DispositionFamily.REJECTED.value,
})

# CL4 (Plan Steps 7-8): family sets shared by the reviser and gate
# projections so the two projections classify dispositions identically.
# ACTIONABLE families require reviser action/follow-up (ACTED_ON carries a
# completed action; ADDRESSED_PENDING_VERIFICATION is an open acted-on
# finding awaiting verification). UNCHANGED families are settled
# (resolved-verified or accepted-risk) and remain visible without further
# action. Legacy "resolved" is normalized to "resolved-verified" upstream
# via _normalize_disposition_family before these sets are consulted.
_PROJECTION_ACTIONABLE_FAMILIES = frozenset({
    DispositionFamily.ACTED_ON.value,
    DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value,
})
_PROJECTION_UNCHANGED_FAMILIES = frozenset({
    DispositionFamily.RESOLVED_VERIFIED.value,
    DispositionFamily.ACCEPTED_RISK.value,
})

# Whitelist of all valid serialized Relationship values (12 after CL4).
# Reconciliation events with a relationship not in this set are rejected
# with a typed failure rather than silently accepted.
_VALID_RELATIONSHIPS = frozenset(e.value for e in Relationship)

# Relationships that are treated as a terminal reconciliation judgment and
# must NOT, on their own, force `accepted=False` or block completion.
# UNCERTAIN is included here: the evaluator explicitly declined to assert
# sameness, but that is a valid terminal judgment, not a hard failure.
_NON_BLOCKING_RELATIONSHIPS = frozenset({
    Relationship.UNRELATED.value,
    Relationship.UNCERTAIN.value,
    Relationship.NEW.value,
    Relationship.MERGE.value,
})

# CL4 (Plan Step 4): relationships that assert an occurrence IS a member of
# the target semantic finding (sameness/identity family). An occurrence
# mapped to two or more DISTINCT findings exclusively via these relationships
# is a contradictory multiply-mapping and a hard failure. When at least one
# mapping uses a non-sameness relationship (UNRELATED/UNCERTAIN/NEW/SPLIT/
# BLOCKS/BLOCKED_BY/REOPEN), the multiple memberships represent a legitimate
# evaluator dispute (e.g. a disputed MERGE) and are retained rather than
# rejected — preserving the done-criteria disputed-MERGE fixture.
_SAMENESS_RELATIONSHIPS = frozenset({
    Relationship.DUPLICATE.value,
    Relationship.MERGE.value,
    Relationship.SUPERSEDED.value,
    Relationship.REFINEMENT.value,
    Relationship.REGRESSION.value,
})

# CL4 (Plan Step 3): parse statuses whose occurrences are eligible to
# contribute to the finding_map. The four terminal-failure/discard statuses
# are accounted as ``excluded-from-finding-map`` and never become findings,
# while NO_ADDITIONAL_FINDINGS is an explicit positive no-content assertion.
# This is the source of truth for per-occurrence reconciliation accounting:
# every input occurrence produces exactly one accounting row derived from its
# parse_status, so FAILED/DROPPED are surfaced with a reason rather than
# silently ignored or confused with NO_ADDITIONAL_FINDINGS.
_FINDING_ELIGIBLE_STATUSES = frozenset({
    ParseStatus.SELECTED.value,
    ParseStatus.COMPLETED.value,
})

# Human-readable reasons for excluded-from-finding-map occurrences, keyed by
# parse_status. These surface WHY a FAILED/DROPPED/MALFORMED/TOMBSTONED
# occurrence did not produce a finding, so the gate can distinguish a parse
# failure from a genuine NO_ADDITIONAL_FINDINGS assertion.
_EXCLUDED_OCCURRENCE_REASONS = {
    ParseStatus.FAILED.value: "parse failure; producer output could not be parsed",
    ParseStatus.DROPPED.value: "attempt dropped before producing a finding",
    ParseStatus.MALFORMED.value: "malformed producer output; unparseable record",
    ParseStatus.TOMBSTONED.value: "tombstoned; occurrence revoked by tombstone",
}


def _normalize_disposition_family(family_value: str) -> str:
    """Normalize a deprecated disposition family value for classification and
    validation without mutating the stored value.

    The deprecated `DispositionFamily.RESOLVED.value` ("resolved") is
    preserved verbatim on stored dispositions and existing handoffs. This
    helper is the single place that interprets it: legacy "resolved" maps
    to "resolved-verified" for the purpose of build_briefing bucketing and
    the closure check. All other values (including the new distinct
    "resolved-verified" and "addressed-pending-verification" serialized
    members) pass through unchanged.

    Args:
        family_value: A serialized disposition family string.

    Returns:
        The normalized family value, leaving the original input untouched.
    """
    if family_value == DispositionFamily.RESOLVED.value:
        return DispositionFamily.RESOLVED_VERIFIED.value
    return family_value

_UNKNOWN_PRODUCER_PREFIXES = frozenset({"UNKNOWN_", "unknown_", "MALFORMED_", "DROPPED_"})


def _is_unknown_producer(producer_id: str) -> bool:
    """Check if a producer_id indicates an unknown/malformed producer."""
    for prefix in _UNKNOWN_PRODUCER_PREFIXES:
        if producer_id.startswith(prefix):
            return True
    return False


def _now_utc() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════
# Phase 1: Custody validation
# ══════════════════════════════════════════════════════════════════════


def validate_occurrence_custody(
    occurrences: list[CritiqueOccurrenceEnvelope],
    wbc_receipt_chain: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate occurrence custody (prove WBC receipt chain).

    Args:
        occurrences: List of critique occurrence envelopes.
        wbc_receipt_chain: Dict mapping receipt refs to their validation
            status. Keys are receipt ref strings; values are dicts with
            at minimum a ``valid`` boolean.

    Returns:
        Dict with keys:
          - valid: bool — whether all occurrences pass custody
          - failures: list of per-occurrence failure dicts
          - receipt_coverage: dict with unique_receipts_referenced count
    """
    if wbc_receipt_chain is None:
        wbc_receipt_chain = {}

    failures: list[dict[str, Any]] = []
    receipt_refs_seen: set[str] = set()

    for occ in occurrences:
        refs = occ.custody_receipt_refs

        # Check for unknown producer
        if _is_unknown_producer(occ.producer_id):
            failures.append({
                "mode": FailureMode.CUSTODY_PRODUCER_UNKNOWN.value,
                "occurrence_id": occ.occurrence_id,
                "producer_id": occ.producer_id,
                "detail": f"Producer '{occ.producer_id}' is unknown/malformed",
            })
            continue

        if (
            occ.evidence_availability == EvidenceAvailability.UNAVAILABLE.value
            and (not occ.unavailable_reason or not occ.reopen_condition)
        ):
            failures.append({
                "mode": FailureMode.CUSTODY_UNAVAILABLE_EVIDENCE.value,
                "occurrence_id": occ.occurrence_id,
                "detail": (
                    "Unavailable evidence requires unavailable_reason and "
                    "reopen_condition"
                ),
            })
            continue

        # Track receipt refs for coverage
        for ref in refs:
            receipt_refs_seen.add(ref)

        # No receipt refs
        if not refs:
            failures.append({
                "mode": FailureMode.CUSTODY_NO_RECEIPT.value,
                "occurrence_id": occ.occurrence_id,
                "detail": "No custody receipt refs provided",
            })
            continue

        # Validate receipt chain
        missing_or_invalid: list[str] = []
        for ref in refs:
            receipt = wbc_receipt_chain.get(ref)
            if receipt is None or not receipt.get("valid"):
                missing_or_invalid.append(ref)

        if missing_or_invalid:
            failures.append({
                "mode": FailureMode.CUSTODY_RECEIPT_CHAIN_BROKEN.value,
                "occurrence_id": occ.occurrence_id,
                "missing_refs": missing_or_invalid,
                "detail": (
                    f"Receipt chain broken: {missing_or_invalid} not found "
                    f"or invalid in WBC receipt chain"
                ),
            })

    return {
        "valid": len(failures) == 0,
        "failures": failures,
        "receipt_coverage": {
            "unique_receipts_referenced": len(receipt_refs_seen),
        },
    }


# ══════════════════════════════════════════════════════════════════════
# Phase 2: Reconciliation
# ══════════════════════════════════════════════════════════════════════


def apply_reconciliation_events(
    occurrences: list[CritiqueOccurrenceEnvelope],
    reconciliations: list[FindingReconciliationEvent],
    allow_reopen: bool = True,
) -> dict[str, Any]:
    """Apply ordered append-only reconciliation events.

    Maps occurrence IDs to semantic finding IDs via evaluator-authored
    reconciliation events. Never infers sameness — relationships are
    exclusively supplied by the evaluator.

    Args:
        occurrences: All occurrence envelopes in the input set.
        reconciliations: Ordered reconciliation events.
        allow_reopen: If False, REOPEN relationship events are rejected
            as out-of-order.

    Returns:
        Dict with keys:
          - accepted: bool
          - finding_map: {semantic_finding_id: [occurrence_ids]}
          - total_semantic_findings: int
          - failures: list of failure dicts
          - reopen_events: list of reopen event dicts
          - occurrence_accounting: list of per-occurrence accounting dicts,
            exactly one row per input occurrence. Each row carries
            ``occurrence_id``, ``parse_status``, ``disposition``
            ("mapped-to-finding" / "excluded-from-finding-map" /
            "no-additional-findings"), ``reason``, and
            ``semantic_finding_id_or_null``. FAILED/DROPPED/MALFORMED/
            TOMBSTONED are surfaced as excluded-from-finding-map with a
            reason and never confused with NO_ADDITIONAL_FINDINGS.

            Plan Step 4 enforces exactly-once accounting completeness here:
            every input occurrence must be covered by exactly one accounting
            row (OCCURRENCE_UNMAPPED / OCCURRENCE_MULTIPLY_MAPPED failures
            otherwise), and every finding-eligible occurrence must map to
            exactly one semantic finding. A contradictory double-sameness
            mapping (e.g. two DUPLICATE assertions to distinct findings) is an
            OCCURRENCE_MULTIPLY_MAPPED hard failure; a disputed MERGE that
            mixes a sameness relationship with a non-sameness judgment
            (UNRELATED/UNCERTAIN/...) is a legitimate evaluator dispute and is
            retained, so ``accepted`` stays True.
    """
    failures: list[dict[str, Any]] = []
    reopen_events: list[dict[str, Any]] = []
    finding_map: dict[str, set[str]] = {}
    # CL4 (Plan Step 4): track the relationship each occurrence was mapped
    # with, so multiply-mapped occurrences can be distinguished from
    # legitimate evaluator disputes (disputed MERGE).
    occ_to_relationships: dict[str, set[str]] = {}
    seen_reconciliation_ids: set[str] = set()
    occurrence_id_set = {occ.occurrence_id for occ in occurrences}

    for rec in reconciliations:
        # Missing ID
        if not rec.reconciliation_id:
            failures.append({
                "mode": FailureMode.RECONCILIATION_MISSING_ID.value,
                "detail": "Reconciliation event has empty reconciliation_id",
            })
            continue

        # Duplicate event
        if rec.reconciliation_id in seen_reconciliation_ids:
            failures.append({
                "mode": FailureMode.RECONCILIATION_DUPLICATE_EVENT.value,
                "reconciliation_id": rec.reconciliation_id,
                "detail": f"Duplicate reconciliation_id: {rec.reconciliation_id}",
            })
            continue
        seen_reconciliation_ids.add(rec.reconciliation_id)

        # Unknown relationship — reject unrecognized serialized values with
        # a typed failure rather than silently accepting them. The whitelist
        # auto-derives from the Relationship enum, so it tracks future
        # additions automatically.
        if rec.relationship not in _VALID_RELATIONSHIPS:
            failures.append({
                "mode": FailureMode.RECONCILIATION_UNKNOWN_RELATIONSHIP.value,
                "reconciliation_id": rec.reconciliation_id,
                "relationship": rec.relationship,
                "detail": (
                    f"Unknown relationship value: {rec.relationship!r}. "
                    f"Valid relationships: {sorted(_VALID_RELATIONSHIPS)}"
                ),
            })
            continue

        # Check for orphan occurrences
        orphans = [
            oid for oid in rec.occurrence_ids
            if oid not in occurrence_id_set
        ]
        if orphans:
            failures.append({
                "mode": FailureMode.RECONCILIATION_ORPHAN_OCCURRENCE.value,
                "reconciliation_id": rec.reconciliation_id,
                "orphan_ids": orphans,
                "detail": f"Orphan occurrence(s) in reconciliation: {orphans}",
            })
            continue

        # Reopen events
        if rec.relationship == Relationship.REOPEN.value or rec.is_reopen:
            if not allow_reopen:
                failures.append({
                    "mode": FailureMode.RECONCILIATION_OUT_OF_ORDER.value,
                    "reconciliation_id": rec.reconciliation_id,
                    "detail": "REOPEN event not allowed (allow_reopen=False)",
                })
                continue
            reopen_events.append({
                "reconciliation_id": rec.reconciliation_id,
                "semantic_finding_id": rec.semantic_finding_id,
                "reopen_condition": rec.reopen_condition,
                "reason": rec.reason,
            })

        # Inferred sameness check (non-DUPLICATE relationship asserting or
        # implying sameness without an explicit reason). UNRELATED and
        # UNCERTAIN are explicit *non-sameness* judgments and do not trip
        # this check; REOPEN is handled above. MERGE/SUPERSEDED/REFINEMENT/
        # REGRESSION/SPLIT/BLOCKS/BLOCKED_BY without a reason still warn.
        _NON_SAMENESS_RELATIONSHIPS = frozenset({
            Relationship.DUPLICATE.value,
            Relationship.REOPEN.value,
            Relationship.UNRELATED.value,
            Relationship.UNCERTAIN.value,
        })
        if (
            rec.relationship not in _NON_SAMENESS_RELATIONSHIPS
            and not rec.reason
        ):
            failures.append({
                "mode": FailureMode.RECONCILIATION_INFERRED_SAMENESS.value,
                "reconciliation_id": rec.reconciliation_id,
                "relationship": rec.relationship,
                "detail": (
                    f"Non-DUPLICATE relationship '{rec.relationship}' "
                    f"without explicit reason — sameness must not be inferred"
                ),
            })
            # Continue processing — this is a warning, not a hard failure
            # for the finding_map

        # Map occurrences to semantic finding
        sf_id = rec.semantic_finding_id
        if sf_id not in finding_map:
            finding_map[sf_id] = set()
        finding_map[sf_id].update(rec.occurrence_ids)
        # CL4 (Plan Step 4): record the relationship used for each mapped
        # occurrence so multiply-mapping can be distinguished from a
        # legitimate evaluator dispute downstream.
        for oid in rec.occurrence_ids:
            occ_to_relationships.setdefault(oid, set()).add(rec.relationship)

    # CL4 (Plan Step 3): exclude non-eligible parse statuses from the
    # finding_map. FAILED/DROPPED/MALFORMED/TOMBSTONED never become findings;
    # they receive explicit "excluded-from-finding-map" accounting entries so
    # no occurrence is silently ignored. This keeps the accounting truthful:
    # an occurrence accounted as excluded-from-finding-map is never present in
    # finding_map. A finding left with zero eligible occurrences is dropped.
    occ_status_by_id = {
        occ.occurrence_id: occ.parse_status for occ in occurrences
    }
    for sf_id in list(finding_map.keys()):
        eligible = {
            oid for oid in finding_map[sf_id]
            if occ_status_by_id.get(oid) in _FINDING_ELIGIBLE_STATUSES
        }
        if eligible:
            finding_map[sf_id] = eligible
        else:
            del finding_map[sf_id]

    # Convert sets to sorted lists for deterministic output
    finding_map_lists: dict[str, list[str]] = {
        sf_id: sorted(oids)
        for sf_id, oids in finding_map.items()
    }

    # Reverse map: occurrence_id -> [semantic_finding_id, ...]
    occ_to_findings: dict[str, list[str]] = {}
    for sf_id, oids in finding_map.items():
        for oid in oids:
            occ_to_findings.setdefault(oid, []).append(sf_id)

    # CL4 (Plan Step 3): produce exactly one accounting entry per input
    # occurrence, derived from parse_status. SELECTED/COMPLETED are
    # mapped-to-finding; FAILED/DROPPED/MALFORMED/TOMBSTONED are
    # excluded-from-finding-map with an explicit reason; NO_ADDITIONAL_
    # FINDINGS is an explicit no-additional-findings event. FAILED and
    # DROPPED are surfaced by reason and never confused with
    # NO_ADDITIONAL_FINDINGS.
    #
    # CL4 (Plan Step 4): while building the rows, also detect finding-
    # eligible occurrences that are unmapped (zero reconciliations) or
    # multiply-mapped (more than one). Both are recorded and surfaced as
    # hard failures after the loop so `accepted` is False and the gate can
    # never observe a truthful-looking but ambiguous or incomplete proof.
    occurrence_accounting: list[dict[str, Any]] = []
    unmapped_eligible: list[str] = []
    multiply_mapped_eligible: list[str] = []
    for occ in sorted(occurrences, key=lambda o: o.occurrence_id):
        status = occ.parse_status
        if status in _FINDING_ELIGIBLE_STATUSES:
            mapped = sorted(occ_to_findings.get(occ.occurrence_id, []))
            if len(mapped) == 0:
                unmapped_eligible.append(occ.occurrence_id)
                semantic_finding_id = None
                reason = (
                    f"parse_status={status}; finding-eligible occurrence "
                    f"lacks a reconciliation mapping"
                )
            elif len(mapped) == 1:
                semantic_finding_id = mapped[0]
                reason = (
                    f"parse_status={status}; reconciled to semantic "
                    f"finding {semantic_finding_id}"
                )
            else:
                # CL4 (Plan Step 4): the occurrence is a member of two or
                # more distinct findings. Only an exclusive-sameness mapping
                # (e.g. two DUPLICATE/MERGE assertions to different findings)
                # is a contradictory multiply-mapping. When at least one
                # relationship is a non-sameness judgment (UNRELATED/
                # UNCERTAIN/...), the multiple memberships are a legitimate
                # evaluator dispute and are retained rather than rejected.
                rels = occ_to_relationships.get(occ.occurrence_id, set())
                if rels and all(r in _SAMENESS_RELATIONSHIPS for r in rels):
                    multiply_mapped_eligible.append(occ.occurrence_id)
                    reason = (
                        f"parse_status={status}; occurrence reconciled to "
                        f"multiple semantic findings via sameness: {mapped}"
                    )
                else:
                    reason = (
                        f"parse_status={status}; occurrence retained across "
                        f"disputed findings {mapped} (non-sameness "
                        f"relationship present: {sorted(rels)})"
                    )
                semantic_finding_id = None
            occurrence_accounting.append({
                "occurrence_id": occ.occurrence_id,
                "parse_status": status,
                "disposition": "mapped-to-finding",
                "reason": reason,
                "semantic_finding_id_or_null": semantic_finding_id,
            })
        elif status == ParseStatus.NO_ADDITIONAL_FINDINGS.value:
            occurrence_accounting.append({
                "occurrence_id": occ.occurrence_id,
                "parse_status": status,
                "disposition": "no-additional-findings",
                "reason": (
                    "parse_status=NO_ADDITIONAL_FINDINGS: producer "
                    "asserted no additional findings"
                ),
                "semantic_finding_id_or_null": None,
            })
        else:
            # FAILED/DROPPED/MALFORMED/TOMBSTONED (and any defensive
            # unknown status) are excluded-from-finding-map with a reason.
            reason_detail = _EXCLUDED_OCCURRENCE_REASONS.get(
                status, f"unhandled parse status {status!r}"
            )
            occurrence_accounting.append({
                "occurrence_id": occ.occurrence_id,
                "parse_status": status,
                "disposition": "excluded-from-finding-map",
                "reason": f"parse_status={status}: {reason_detail}",
                "semantic_finding_id_or_null": None,
            })

    # CL4 (Plan Step 4): exact accounting completeness proof. Every input
    # occurrence — including excluded statuses — must be covered by exactly
    # one accounting row, and every finding-eligible occurrence must map to
    # exactly one semantic finding. Missing or duplicate accounting rows and
    # unmapped/multiply-mapped eligible occurrences are hard acceptance
    # failures so the gate can never observe an incomplete proof. These
    # failures are in addition to any reconciliation-event failures above.
    input_occurrence_ids = [occ.occurrence_id for occ in occurrences]
    accounting_id_counts: dict[str, int] = {}
    for row in occurrence_accounting:
        oid = row["occurrence_id"]
        accounting_id_counts[oid] = accounting_id_counts.get(oid, 0) + 1

    missing_accounting = sorted(
        set(input_occurrence_ids) - set(accounting_id_counts)
    )
    duplicate_accounting = sorted(
        oid for oid, count in accounting_id_counts.items() if count > 1
    )
    if missing_accounting:
        failures.append({
            "mode": FailureMode.OCCURRENCE_UNMAPPED.value,
            "occurrence_ids": missing_accounting,
            "detail": (
                "Occurrence accounting completeness violated: input "
                f"occurrences lack an accounting row: {missing_accounting}"
            ),
        })
    if duplicate_accounting:
        failures.append({
            "mode": FailureMode.OCCURRENCE_MULTIPLY_MAPPED.value,
            "occurrence_ids": duplicate_accounting,
            "detail": (
                "Occurrence accounting uniqueness violated: occurrences "
                f"have multiple accounting rows: {duplicate_accounting}"
            ),
        })
    if unmapped_eligible:
        failures.append({
            "mode": FailureMode.OCCURRENCE_UNMAPPED.value,
            "occurrence_ids": sorted(unmapped_eligible),
            "detail": (
                "Finding-eligible occurrences lack a reconciliation "
                f"mapping: {sorted(unmapped_eligible)}"
            ),
        })
    if multiply_mapped_eligible:
        failures.append({
            "mode": FailureMode.OCCURRENCE_MULTIPLY_MAPPED.value,
            "occurrence_ids": sorted(multiply_mapped_eligible),
            "detail": (
                "Finding-eligible occurrences map to multiple semantic "
                f"findings: {sorted(multiply_mapped_eligible)}"
            ),
        })

    return {
        "accepted": len([f for f in failures if f["mode"] not in (
            FailureMode.RECONCILIATION_INFERRED_SAMENESS.value,
        )]) == 0,
        "finding_map": finding_map_lists,
        "total_semantic_findings": len(finding_map_lists),
        "failures": failures,
        "reopen_events": reopen_events,
        "occurrence_accounting": occurrence_accounting,
    }


# ══════════════════════════════════════════════════════════════════════
# Phase 3: Disposition
# ══════════════════════════════════════════════════════════════════════

# Metadata key under which a disposition records the canonical briefing-input
# hash (``compute_input_hash``) captured when it was authored.  When present,
# it is the stored baseline the live input hash is compared against.
_STORED_INPUT_HASH_KEY = "input_hash"


def _disposition_staleness_deferred(
    disp: FindingDispositionEvent,
    input_hash: str | None,
) -> bool:
    """Classify the advisory staleness flag for a stored disposition.

    Resolution of the CL4 ``cl5_staleness_deferral`` reopen predicate: when the
    production caller supplies the canonical briefing-input hash (``input_hash``
    computed over the live occurrence/reconciliation/disposition sources), a
    disposition that recorded a stored baseline hash in its ``metadata`` is
    compared against it mechanically.  A divergence marks the disposition
    stale (``staleness_check_deferred = True``); a match confirms freshness
    (``False``), overriding the structural ``reopen_predicate`` heuristic.

    The flag is advisory-only and carries no authority: it never opens, admits,
    or authorises anything (the freshness verdict has no authority field).  When
    no live input hash is supplied, or when the disposition recorded no stored
    baseline, the function falls back to the CL4 deferral sentinel
    ``bool(disp.reopen_predicate)`` so direct callers, replay, and restoration
    paths keep their existing advisory behaviour.
    """
    if input_hash is None:
        return bool(disp.reopen_predicate)
    stored = (disp.metadata or {}).get(_STORED_INPUT_HASH_KEY, "")
    if not stored:
        # Live context is available but this disposition recorded no stored
        # baseline to compare against — preserve the advisory fallback.
        return bool(disp.reopen_predicate)
    return bool(stored and stored != input_hash)


def apply_disposition_events(
    finding_map: dict[str, Any],
    dispositions: list[FindingDispositionEvent],
    input_hash: str | None = None,
) -> dict[str, Any]:
    """Apply ordered append-only disposition events to semantic findings.

    Args:
        finding_map: Mapping from semantic_finding_id to set/list of
            occurrence IDs (output of apply_reconciliation_events).
        dispositions: Ordered disposition events.

    Returns:
        Dict with keys:
          - accepted: bool
          - family_counts: {family: count}
          - failures: list of failure dicts
          - disposition_map: {semantic_finding_id: disposition dict}

    CL4 (Plan Step 5): per-family field-presence rules. Each of the seven
    non-closure families requires a specific field — ACTED_ON requires
    ``action_taken`` + ``action_description``; IGNORED, DEFERRED, and
    ACCEPTED_RISK require ``reopen_predicate``; REJECTED requires
    ``reason_subcode``; DUPLICATE requires a canonical-finding ref in
    ``metadata``. A missing required field yields the typed FailureMode
    (ACTED_ON_MISSING_ACTION, IGNORED_MISSING_REOPEN_PREDICATE, ...,
    DUPLICATE_MISSING_CANONICAL_REF) and the disposition is neither counted
    nor stored. UNKNOWN is a valid terminal judgment with no extra
    requirement; the closure families (RESOLVED_VERIFIED / legacy RESOLVED)
    are gated by the closure rules, not by these checks.

    CL4 (Plan Step 6): closure-evidence enforcement and transition gating.
    A RESOLVED_VERIFIED disposition requires a verification artifact in
    ``evidence_refs`` (CLOSURE_UNSUPPORTED when absent); a
    pending->verified transition (ADDRESSED_PENDING_VERIFICATION followed
    by RESOLVED_VERIFIED) carries the same evidence requirement with a
    transition-named detail. The legacy RESOLVED value is intentionally
    not normalized here and keeps its existing apply-level behaviour;
    replay_full's inline closure check is the redundant backstop covering
    both closure values via _normalize_disposition_family. Each stored
    disposition is also annotated with ``staleness_check_deferred``. CL5
    resolves the ``cl5_staleness_deferral`` reopen predicate: when the
    optional ``input_hash`` (the canonical briefing-input hash computed by
    the production orchestrator) is supplied, a disposition that recorded a
    stored baseline hash in its ``metadata`` is compared against it and the
    divergence is flagged mechanically; otherwise the flag falls back to the
    CL4 deferral sentinel ``bool(disp.reopen_predicate)``. The flag is
    advisory-only and never grants authority.
    """
    failures: list[dict[str, Any]] = []
    family_counts: dict[str, int] = {}
    disposition_map: dict[str, dict[str, Any]] = {}
    seen_disposition_ids: set[str] = set()
    # CL4 (Plan Step 6.2): findings currently/ever disposed as
    # ADDRESSED_PENDING_VERIFICATION within this event sequence. A later
    # RESOLVED_VERIFIED for one of these findings is a pending->verified
    # transition that must carry verification evidence (enforced below).
    pending_verification_findings: set[str] = set()

    # Normalize finding_map: convert sets to sorted lists for consistent keys
    normalized_finding_map: dict[str, Any] = {}
    for sf_id, oids in finding_map.items():
        if isinstance(oids, set):
            normalized_finding_map[sf_id] = sorted(oids)
        else:
            normalized_finding_map[sf_id] = oids

    finding_ids = set(normalized_finding_map.keys())

    for disp in dispositions:
        # Missing ID
        if not disp.disposition_id:
            failures.append({
                "mode": FailureMode.DISPOSITION_MISSING_ID.value,
                "detail": "Disposition event has empty disposition_id",
            })
            continue

        # Duplicate event
        if disp.disposition_id in seen_disposition_ids:
            failures.append({
                "mode": FailureMode.DISPOSITION_DUPLICATE_EVENT.value,
                "disposition_id": disp.disposition_id,
                "detail": f"Duplicate disposition_id: {disp.disposition_id}",
            })
            continue
        seen_disposition_ids.add(disp.disposition_id)

        # Unknown family
        if disp.family not in _VALID_DISPOSITION_FAMILIES:
            failures.append({
                "mode": FailureMode.DISPOSITION_UNKNOWN_FAMILY.value,
                "disposition_id": disp.disposition_id,
                "family": disp.family,
                "detail": f"Unknown disposition family: {disp.family}",
            })
            continue

        # Orphan finding
        if disp.semantic_finding_id not in finding_ids:
            failures.append({
                "mode": FailureMode.DISPOSITION_ORPHAN_FINDING.value,
                "disposition_id": disp.disposition_id,
                "semantic_finding_id": disp.semantic_finding_id,
                "detail": (
                    f"Semantic finding '{disp.semantic_finding_id}' "
                    f"not found in finding_map"
                ),
            })
            continue

        # CL4 (Plan Step 5): per-family field-presence rules. Each of the
        # seven non-closure families requires a specific field so a finding
        # cannot disappear behind a malformed disposition. A missing required
        # field produces the typed failure and skips this disposition (it is
        # neither counted nor stored), mirroring the unknown-family / orphan
        # handling. UNKNOWN is a valid terminal judgment with no extra
        # requirement; the closure families are gated separately.
        presence = _disposition_field_presence_failure(disp)
        if presence is not None:
            presence_mode, presence_detail = presence
            failures.append({
                "mode": presence_mode.value,
                "disposition_id": disp.disposition_id,
                "family": disp.family,
                "semantic_finding_id": disp.semantic_finding_id,
                "detail": presence_detail,
            })
            continue

        # CL4 (Plan Step 6.1 / 6.2): closure-evidence enforcement and
        # pending->verified transition gating. A RESOLVED_VERIFIED
        # disposition requires a verification artifact in evidence_refs.
        # This is the PRIMARY closure-evidence enforcement; replay_full's
        # inline closure check is a redundant backstop that additionally
        # requires a reason_subcode and covers both legacy RESOLVED and
        # RESOLVED_VERIFIED via _normalize_disposition_family. The legacy
        # RESOLVED value is intentionally NOT normalized here so existing
        # stored/handoff dispositions keep their apply-level behaviour
        # (legacy RESOLVED closure is enforced only by the replay backstop);
        # only the new RESOLVED_VERIFIED value carries the apply-level
        # evidence requirement. When the verifying disposition follows an
        # ADDRESSED_PENDING_VERIFICATION for the same finding, the failure
        # detail names the transition explicitly (Step 6.2).
        is_verified_closure = (
            disp.family == DispositionFamily.RESOLVED_VERIFIED.value
        )
        is_pending_transition = (
            is_verified_closure
            and disp.semantic_finding_id in pending_verification_findings
        )
        if is_verified_closure and not disp.evidence_refs:
            failures.append({
                "mode": FailureMode.CLOSURE_UNSUPPORTED.value,
                "disposition_id": disp.disposition_id,
                "family": disp.family,
                "semantic_finding_id": disp.semantic_finding_id,
                "detail": (
                    "ADDRESSED_PENDING_VERIFICATION -> RESOLVED_VERIFIED "
                    "transition requires verification evidence in "
                    "evidence_refs"
                    if is_pending_transition
                    else "RESOLVED_VERIFIED closure requires verification "
                    "evidence in evidence_refs"
                ),
            })
            continue
        if disp.family == DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value:
            pending_verification_findings.add(disp.semantic_finding_id)

        # Count families
        family_counts[disp.family] = family_counts.get(disp.family, 0) + 1

        # Store disposition
        disposition_map[disp.semantic_finding_id] = {
            "disposition_id": disp.disposition_id,
            "family": disp.family,
            "reason_subcode": disp.reason_subcode,
            "severity": disp.severity,
            "action_taken": disp.action_taken,
            "action_description": disp.action_description,
            "accountable_scope": disp.accountable_scope,
            "is_reopen": disp.is_reopen,
            "reopen_predicate": disp.reopen_predicate,
            "staleness_check_deferred": _disposition_staleness_deferred(disp, input_hash),
            "evidence_refs": list(disp.evidence_refs),
            "authority": disp.authority,
            "timestamp_utc": disp.timestamp_utc,
        }

    missing_dispositions = sorted(finding_ids - set(disposition_map))
    if missing_dispositions:
        failures.append({
            "mode": FailureMode.DISPOSITION_INCOMPLETE.value,
            "semantic_finding_ids": missing_dispositions,
            "detail": (
                "Every semantic finding requires an explicit disposition; "
                f"missing {missing_dispositions}"
            ),
        })

    return {
        "accepted": len(failures) == 0,
        "family_counts": family_counts,
        "failures": failures,
        "disposition_map": disposition_map,
    }


# ══════════════════════════════════════════════════════════════════════
# Phase 4: Manifest construction
# ══════════════════════════════════════════════════════════════════════


def construct_manifest(
    occurrences: list[CritiqueOccurrenceEnvelope],
    rec_result: dict[str, Any],
    disp_result: dict[str, Any],
    domain_completeness: dict[str, bool] | None = None,
    prior_manifest: LedgerRevisionManifest | None = None,
    expected_prior_revision_hash: str | None = None,
) -> LedgerRevisionManifest:
    """Construct a LedgerRevisionManifest from reconciled/disposed state.

    Args:
        occurrences: All occurrence envelopes.
        rec_result: Output of apply_reconciliation_events.
        disp_result: Output of apply_disposition_events.
        domain_completeness: Optional map of domain → is_complete.

    Returns:
        LedgerRevisionManifest with freshness vectors and completeness maps.

    Raises:
        SemanticLoopError: If input set is empty or domain completeness
            check fails.
    """
    if not occurrences:
        raise SemanticLoopError(
            mode=FailureMode.MANIFEST_EMPTY_INPUT_SET,
            detail="Cannot construct manifest from empty occurrence set",
        )

    # Check domain completeness
    if domain_completeness:
        incomplete = [
            domain for domain, complete in domain_completeness.items()
            if not complete
        ]
        if incomplete:
            raise SemanticLoopError(
                mode=FailureMode.MANIFEST_DOMAIN_INCOMPLETE,
                detail=f"Domains incomplete: {incomplete}",
            )

    # Collect event IDs and reasons
    event_ids: list[str] = []
    included_reasons: dict[str, str] = {}
    excluded_reasons: dict[str, str] = {}

    # T4: admit NO_ADDITIONAL_FINDINGS occurrences into the manifest. They
    # are a positive producer assertion ("nothing more to add") rather than
    # a parse/attempt failure. FAILED/DROPPED/MALFORMED remain excluded so
    # the manifest exclusion contract is preserved.
    valid_statuses = frozenset({
        ParseStatus.SELECTED.value,
        ParseStatus.COMPLETED.value,
        ParseStatus.NO_ADDITIONAL_FINDINGS.value,
    })

    for occ in occurrences:
        event_ids.append(occ.occurrence_id)
        if occ.parse_status in valid_statuses:
            included_reasons[occ.occurrence_id] = (
                f"parse_status={occ.parse_status}, "
                f"producer={occ.producer_id}"
            )
        else:
            excluded_reasons[occ.occurrence_id] = (
                f"parse_status={occ.parse_status}, "
                f"producer={occ.producer_id}"
            )

    # Collect all reconciliation and disposition event IDs
    finding_map = rec_result.get("finding_map", {})
    disposition_map = disp_result.get("disposition_map", {})

    # Compute input set hash from all occurrences
    hash_input = "|".join(
        f"{occ.occurrence_id}:{occ.producer_id}:{occ.parse_status}"
        for occ in sorted(occurrences, key=lambda o: o.occurrence_id)
    )
    input_set_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
    prior_hash = canonical_hash(prior_manifest) if prior_manifest is not None else None
    if expected_prior_revision_hash is not None and prior_hash != expected_prior_revision_hash:
        raise SemanticLoopError(
            mode=FailureMode.PRIOR_REVISION_CHAIN_BROKEN,
            detail=(
                f"Expected prior revision {expected_prior_revision_hash}, "
                f"observed {prior_hash}"
            ),
        )

    # Collect WBC receipt refs
    receipt_refs: set[str] = set()
    for occ in occurrences:
        receipt_refs.update(occ.custody_receipt_refs)

    manifest = LedgerRevisionManifest(
        manifest_id=f"ledger-revision-{input_set_hash[:24]}",
        revision_number=(prior_manifest.revision_number + 1 if prior_manifest else 1),
        prior_revision_hash=prior_hash,
        input_set_hash=input_set_hash,
        source_revisions=tuple(sorted(set(
            occ.round_label for occ in occurrences
        ))),
        domain_completeness=domain_completeness or {},
        wbc_receipt_refs=tuple(sorted(receipt_refs)),
        event_ids=tuple(event_ids),
        included_reasons=included_reasons,
        excluded_reasons=excluded_reasons,
        cross_domain_refs=tuple(sorted(set(
            rec_result.get("cross_domain_refs", []) or []
        ))),
        timestamp_utc=(prior_manifest.timestamp_utc if prior_manifest else ""),
    )

    return manifest


# ══════════════════════════════════════════════════════════════════════
# Phase 5: Briefing
# ══════════════════════════════════════════════════════════════════════


_VALID_BRIEFING_MODES = frozenset({
    ContextMode.BLIND.value,
    ContextMode.HISTORY_AWARE.value,
})


def build_briefing(
    manifest: LedgerRevisionManifest,
    disp_result: dict[str, Any],
    finding_map: dict[str, Any],
    budget_level: str = "standard",
    domain_assignments: dict[str, str] | None = None,
    rec_result: dict[str, Any] | None = None,
    occurrences: list[CritiqueOccurrenceEnvelope] | None = None,
    freshness_vectors: list[Any] | None = None,
    mode: str = ContextMode.HISTORY_AWARE.value,
) -> DomainBriefingEnvelope:
    """Build a domain briefing from the accepted manifest.

    Enforces provisional CL1 budgets:
      - standard: 2 domains / 10 findings
      - high: 4 domains / 25 findings
      - exhaustive: all / unbounded

    Args:
        manifest: The accepted LedgerRevisionManifest.
        disp_result: Output of apply_disposition_events.
        finding_map: Output mapping from apply_reconciliation_events.
        budget_level: One of 'standard', 'high', 'exhaustive'.
        domain_assignments: Optional mapping from semantic_finding_id
            to domain name.

    Returns:
        DomainBriefingEnvelope.

    Raises:
        SemanticLoopError: If budget is unknown or domain floor is unmet.
    """
    if budget_level not in BRIEFING_BUDGETS:
        raise SemanticLoopError(
            mode=FailureMode.BRIEFING_BUDGET_EXCEEDED,
            detail=f"Unknown budget_level: {budget_level!r}",
        )

    budget = BRIEFING_BUDGETS[budget_level]
    max_domains = budget["max_domains"]
    max_findings = budget["max_findings"]

    # T11: validate the briefing mode. HISTORY_AWARE is the complete default
    # (every projection field populated); BLIND retains identity/accounting
    # hashes while excluding dispositions, cross-domain references, prior
    # content, and history-derived flags. Mode participates in the briefing
    # hash so blind/history-aware briefings are canonical-distinct.
    if mode not in _VALID_BRIEFING_MODES:
        raise SemanticLoopError(
            mode=FailureMode.BRIEFING_BUDGET_EXCEEDED,
            detail=f"Unknown briefing mode: {mode!r}",
        )
    is_blind = mode == ContextMode.BLIND.value

    if domain_assignments is None:
        domain_assignments = {}

    disposition_map = disp_result.get("disposition_map", {})

    # Normalize finding_map
    normalized_fm: dict[str, Any] = {}
    for sf_id, oids in finding_map.items():
        if isinstance(oids, set):
            normalized_fm[sf_id] = sorted(oids)
        else:
            normalized_fm[sf_id] = oids

    # Classify findings into ALL EIGHT family buckets. open_findings is
    # derived EXACTLY from the three open sub-buckets (acted-on / ignored /
    # deferred), never independently.
    acted_on_findings: list[str] = []
    ignored_findings: list[str] = []
    deferred_findings: list[str] = []
    open_findings: list[str] = []
    blocked_findings: list[str] = []
    accepted_risk_findings: list[str] = []
    unknown_findings: list[str] = []
    resolved_findings: list[str] = []
    duplicate_findings: list[str] = []
    all_findings: list[str] = []

    for sf_id in sorted(normalized_fm.keys()):
        all_findings.append(sf_id)
        disp = disposition_map.get(sf_id, {})
        family = disp.get("family", DispositionFamily.UNKNOWN.value)
        # Normalize legacy "resolved" → "resolved-verified" at the single
        # classification chokepoint, leaving the stored value untouched.
        normalized_family = _normalize_disposition_family(family)

        if normalized_family == DispositionFamily.ACTED_ON.value:
            acted_on_findings.append(sf_id)
        elif normalized_family == DispositionFamily.IGNORED.value:
            ignored_findings.append(sf_id)
        elif normalized_family == DispositionFamily.DEFERRED.value:
            deferred_findings.append(sf_id)
        elif normalized_family in _BLOCKED_FAMILIES:
            blocked_findings.append(sf_id)
        elif normalized_family == DispositionFamily.ACCEPTED_RISK.value:
            accepted_risk_findings.append(sf_id)
        elif normalized_family == DispositionFamily.RESOLVED_VERIFIED.value:
            resolved_findings.append(sf_id)
        elif (
            normalized_family
            == DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value
        ):
            # CL4: action was taken but verification is still pending, so the
            # finding remains an open acted-on finding requiring follow-up.
            acted_on_findings.append(sf_id)
        elif normalized_family == DispositionFamily.DUPLICATE.value:
            duplicate_findings.append(sf_id)
        else:
            unknown_findings.append(sf_id)

    # open_findings is derived EXACTLY from the three open sub-buckets.
    open_findings = sorted(
        acted_on_findings + ignored_findings + deferred_findings
    )

    # Assert the full pre-truncation partition: the eight named family
    # buckets equal all findings, and open_findings equals the union of the
    # three open sub-buckets.
    _partition = sorted(
        acted_on_findings + ignored_findings + deferred_findings
        + blocked_findings + accepted_risk_findings + unknown_findings
        + resolved_findings + duplicate_findings
    )
    assert _partition == sorted(all_findings), (
        "family-bucket partition invariant violated before truncation"
    )
    assert sorted(open_findings) == sorted(
        acted_on_findings + ignored_findings + deferred_findings
    ), "open_findings must equal exactly the three open sub-buckets"
    # Determine domains from assignments
    # Determine domains from assignments
    domains_set: set[str] = set()
    for sf_id in all_findings:
        domain = domain_assignments.get(sf_id, "critique_ledger")
        domains_set.add(domain)

    domains = tuple(sorted(domains_set)) if domains_set else ("critique_ledger",)

    # Budget enforcement: domain floor
    if max_domains is not None and len(domains) > max_domains:
        raise SemanticLoopError(
            mode=FailureMode.BRIEFING_DOMAIN_FLOOR_UNMET,
            detail=(
                f"Domain count {len(domains)} exceeds {budget_level} "
                f"budget max {max_domains}. Use spillover, not silent truncation."
            ),
        )

    # Budget enforcement: finding spillover. Overflow findings are encoded
    # as relationship-bearing split-parent refs (parent_finding_id,
    # relationship) rather than flat-omitted. Retained buckets stay
    # budget-bounded; every overflow finding remains reachable.
    spillover: list[str] = []
    split_parent_refs: tuple[tuple[str, str], ...] = ()
    is_truncated = False
    truncation_warning: Optional[str] = None

    if max_findings is not None and len(all_findings) > max_findings:
        is_truncated = True
        spillover = all_findings[max_findings:]
        all_findings = all_findings[:max_findings]
        # Encode each overflow finding as a relationship-bearing split ref.
        split_parent_refs = tuple((fid, "SPLIT") for fid in spillover)
        # Filter every family bucket of spillover findings so retained
        # buckets stay budget-bounded.
        spill_set = set(spillover)
        acted_on_findings = [f for f in acted_on_findings if f not in spill_set]
        ignored_findings = [f for f in ignored_findings if f not in spill_set]
        deferred_findings = [f for f in deferred_findings if f not in spill_set]
        open_findings = [f for f in open_findings if f not in spill_set]
        blocked_findings = [f for f in blocked_findings if f not in spill_set]
        accepted_risk_findings = [f for f in accepted_risk_findings if f not in spill_set]
        unknown_findings = [f for f in unknown_findings if f not in spill_set]
        resolved_findings = [f for f in resolved_findings if f not in spill_set]
        duplicate_findings = [f for f in duplicate_findings if f not in spill_set]
        truncation_warning = (
            f"{len(spillover)} finding(s) exceed {budget_level} budget "
            f"({max_findings} max). Linked via spillover_findings and "
            f"split_parent_refs — not silently discarded."
        )
        # Post-truncation reachability invariant: retained bucket IDs plus
        # split-parent IDs equal the full pre-truncation finding set, and
        # each overflow finding is reachable through a relationship-bearing
        # split ref.
        _retained = set(all_findings)
        _split_parents = {p for p, _r in split_parent_refs}
        _pre_trunc = set(_retained | set(spillover))
        assert (_retained | _split_parents) == _pre_trunc, (
            "post-truncation finding reachability invariant violated: "
            "retained bucket IDs + split-parent IDs != full finding set"
        )
        assert _split_parents == set(spillover), (
            "each overflow finding must appear as a split-parent ref"
        )
        assert all(r for _p, r in split_parent_refs), (
            "every split ref must be relationship-bearing (non-empty)"
        )

    # Aggregate occurrence/disposition content + freshness (T3/T5).
    evidence_unavailable: list[str] = []
    prior_instructions: list[str] = []
    revision_actions: list[str] = []
    conclusions: list[str] = []
    questions: list[str] = []
    reopen_conditions: list[str] = []
    evidence_refs: list[str] = []
    cross_domain_ref_list: list[str] = []

    if occurrences:
        for _occ in occurrences:
            if _occ.evidence_availability == EvidenceAvailability.UNAVAILABLE.value:
                _reason = getattr(_occ, "unavailable_reason", "") or _occ.occurrence_id
                evidence_unavailable.append(_reason)
            _meta = getattr(_occ, "metadata", {}) or {}
            for _key, _bucket in (
                ("prior_instructions", prior_instructions),
                ("instructions", prior_instructions),
                ("revision_actions", revision_actions),
                ("conclusions", conclusions),
                ("questions", questions),
            ):
                _val = _meta.get(_key)
                if isinstance(_val, str) and _val.strip():
                    _bucket.append(_val.strip())
                elif isinstance(_val, (list, tuple)):
                    _bucket.extend(str(_x).strip() for _x in _val if str(_x).strip())
            _rc = getattr(_occ, "reopen_condition", None)
            if isinstance(_rc, str) and _rc.strip():
                reopen_conditions.append(_rc.strip())

    if rec_result:
        cross_domain_ref_list = list(rec_result.get("cross_domain_refs", []) or [])
        for _ev in rec_result.get("reopen_events", []) or []:
            _rc = _ev.get("reopen_condition")
            if isinstance(_rc, str) and _rc.strip():
                reopen_conditions.append(_rc.strip())

    for _sf_id in normalized_fm:
        _disp = disposition_map.get(_sf_id, {})
        _rp = _disp.get("reopen_predicate")
        if isinstance(_rp, str) and _rp.strip():
            reopen_conditions.append(_rp.strip())
        _erefs = _disp.get("evidence_refs") or []
        if isinstance(_erefs, (list, tuple)):
            evidence_refs.extend(str(_r) for _r in _erefs)

    # Freshness -> staleness/availability outputs (T5). Derived ONLY from
    # availability / tombstone / configured-age signals carried on the
    # freshness vectors; never from authority-like metadata.
    stale_flag = False
    rebuild_trigger: Optional[str] = None
    if freshness_vectors:
        _stale = [v for v in freshness_vectors if getattr(v, "is_stale", False)]
        if _stale:
            stale_flag = True
            _reasons = [
                getattr(v, "staleness_reason", "")
                for v in _stale
                if getattr(v, "staleness_reason", "")
            ]
            rebuild_trigger = _reasons[0] if _reasons else "stale"

    # T4: no_additional_findings is derived from ADMITTED occurrence statuses
    # (a producer explicitly asserted "no additional findings"); it is True
    # whenever an admitted NO_ADDITIONAL_FINDINGS occurrence is present, even
    # when the ledger already holds prior findings. no_known_findings is
    # derived ONLY from the ledger finding set, independent of occurrence
    # statuses. See SC4.
    no_additional_flag = any(
        occ.parse_status == ParseStatus.NO_ADDITIONAL_FINDINGS.value
        for occ in (occurrences or [])
    )
    no_known_findings_flag = len(normalized_fm) == 0

    # T11: BLIND projection. Identity/accounting hashes (manifest hash,
    # input-set hash, domain set, finding IDs, budget partition) are always
    # retained so two modes over the same accepted input share identical
    # input identity. History/disposition/cross-domain/prior-content fields
    # are blanked for the blind critic. Reconciliation requirements are NOT
    # erased: the manifest reference (revision_manifest_hash) is retained,
    # and reconciliation already ran on the manifest before this projection.
    briefing = DomainBriefingEnvelope(
        briefing_id=(
            "briefing-"
            + hashlib.sha256(
                (
                    canonical_hash(manifest)
                    + "|"
                    + budget_level
                    + "|"
                    + mode
                    + "|"
                    + "|".join(all_findings)
                    + "|"
                    + "|".join(spillover)
                ).encode("utf-8")
            ).hexdigest()[:24]
        ),
        revision_manifest_hash=canonical_hash(manifest),
        budget_level=budget_level,
        domains=domains,
        findings=tuple(all_findings),
        open_findings=() if is_blind else tuple(open_findings),
        blocked_findings=() if is_blind else tuple(blocked_findings),
        accepted_risk_findings=() if is_blind else tuple(accepted_risk_findings),
        unknown_findings=() if is_blind else tuple(unknown_findings),
        resolved_findings=() if is_blind else tuple(resolved_findings),
        duplicate_findings=() if is_blind else tuple(duplicate_findings),
        acted_on_findings=() if is_blind else tuple(acted_on_findings),
        ignored_findings=() if is_blind else tuple(ignored_findings),
        deferred_findings=() if is_blind else tuple(deferred_findings),
        cross_domain_refs=() if is_blind else tuple(sorted(set(cross_domain_ref_list))),
        prior_instructions=() if is_blind else tuple(prior_instructions),
        revision_actions=() if is_blind else tuple(revision_actions),
        conclusions=() if is_blind else tuple(conclusions),
        questions=() if is_blind else tuple(questions),
        reopen_conditions=() if is_blind else tuple(sorted(set(reopen_conditions))),
        evidence_refs=() if is_blind else tuple(sorted(set(evidence_refs))),
        evidence_unavailable=() if is_blind else tuple(evidence_unavailable),
        split_parent_refs=split_parent_refs,
        stale_flag=False if is_blind else stale_flag,
        rebuild_trigger=None if is_blind else rebuild_trigger,
        input_set_hash=manifest.input_set_hash,
        included_reasons=dict(manifest.included_reasons),
        excluded_reasons=dict(manifest.excluded_reasons),
        spillover_findings=tuple(spillover),
        no_additional_findings=no_additional_flag,
        no_open_blocking_findings=(
            False if is_blind
            else (len(open_findings) == 0 and len(blocked_findings) == 0)
        ),
        no_known_findings=no_known_findings_flag,
        no_adjacent_text_match=False,
        is_truncated=is_truncated,
        truncation_warning=truncation_warning,
        timestamp_utc=manifest.timestamp_utc,
    )

    return briefing


# ══════════════════════════════════════════════════════════════════════
# Phase 6a: Reviser projection
# ══════════════════════════════════════════════════════════════════════


def project_reviser_input(
    manifest: LedgerRevisionManifest,
    briefing: DomainBriefingEnvelope,
    occurrences: list[CritiqueOccurrenceEnvelope],
    disp_result: dict[str, Any],
) -> dict[str, Any]:
    """Produce a read-only reviser input projection.

    Exposes complete cumulative truth without issuing any verdict.
    Includes four distinct no-X fields:
      - no_open_blocking_findings
      - no_additional_findings
      - no_known_findings
      - no_adjacent_text_match

    CL4 (Plan Step 7): the projection additionally carries actionable and
    disposed history so the reviser sees every known finding and which ones
    still require action. ``actionable_findings`` lists findings whose
    normalized family requires reviser action/follow-up (ACTED_ON,
    ADDRESSED_PENDING_VERIFICATION); ``disposed_history`` carries the full
    prior-disposition record for every known finding (family, evidence,
    reopen predicate, action state) so no known finding disappears;
    ``unchanged_findings`` lists settled findings (resolved-verified or
    accepted-risk) that remain visible without further action; and
    ``revision_actions_required`` is True when an actionable finding lacks
    action coverage (``action_taken`` False) — i.e. the reviser must act.
    Evidence refs and reopen predicates are retained verbatim on every
    history entry.

    Args:
        manifest: The accepted manifest.
        briefing: The domain briefing.
        occurrences: All occurrence envelopes.
        disp_result: Output of apply_disposition_events.

    Returns:
        Dict with projection fields. Never contains 'verdict', 'proceed',
        or 'block' keys.
    """
    disposition_map = disp_result.get("disposition_map", {})

    # Build finding summaries
    finding_summaries: list[dict[str, Any]] = []
    for sf_id in briefing.findings:
        disp = disposition_map.get(sf_id, {})
        finding_summaries.append({
            "semantic_finding_id": sf_id,
            "family": disp.get("family", "unknown"),
            "severity": disp.get("severity", ""),
            "action_taken": disp.get("action_taken", False),
            "is_reopen": disp.get("is_reopen", False),
        })

    # Track unavailable evidence
    unavailable_evidence: dict[str, dict[str, Any]] = {}
    for occ in occurrences:
        if occ.evidence_availability == EvidenceAvailability.UNAVAILABLE.value:
            unavailable_evidence[occ.occurrence_id] = {
                "reason": occ.unavailable_reason,
                "reopen_condition": occ.reopen_condition,
            }

    # Count occurrences by parse status
    failed_dropped_malformed = sum(
        1 for occ in occurrences
        if occ.parse_status in (
            ParseStatus.FAILED.value,
            ParseStatus.DROPPED.value,
            ParseStatus.MALFORMED.value,
        )
    )

    # CL4 (Plan Step 7): actionable / disposed / unchanged history. Iterate
    # over the union of briefing findings and the disposition_map so no known
    # finding disappears even when action coverage is missing (a finding with
    # missing action coverage is still surfaced in disposed_history and, if
    # its family is actionable, flagged via revision_actions_required).
    all_known_findings = sorted(
        set(briefing.findings) | set(disposition_map.keys())
    )
    actionable_findings: list[dict[str, Any]] = []
    disposed_history: list[dict[str, Any]] = []
    unchanged_findings: list[str] = []
    revision_actions_required = False
    for sf_id in all_known_findings:
        disp = disposition_map.get(sf_id, {})
        family = disp.get("family", DispositionFamily.UNKNOWN.value)
        normalized_family = _normalize_disposition_family(family)
        evidence_refs = list(disp.get("evidence_refs", []))
        reopen_predicate = disp.get("reopen_predicate")
        # Complete prior-disposition record: family/evidence/reopen retained.
        disposed_history.append({
            "semantic_finding_id": sf_id,
            "family": family,
            "normalized_family": normalized_family,
            "reason_subcode": disp.get("reason_subcode", ""),
            "severity": disp.get("severity", ""),
            "action_taken": disp.get("action_taken", False),
            "action_description": disp.get("action_description"),
            "is_reopen": disp.get("is_reopen", False),
            "reopen_predicate": reopen_predicate,
            "staleness_check_deferred": disp.get("staleness_check_deferred", False),
            "evidence_refs": evidence_refs,
        })
        if normalized_family in _PROJECTION_ACTIONABLE_FAMILIES:
            actionable_findings.append({
                "semantic_finding_id": sf_id,
                "family": family,
                "normalized_family": normalized_family,
                "action_taken": disp.get("action_taken", False),
                "action_description": disp.get("action_description"),
            })
            # Missing action coverage: an actionable finding whose action has
            # not been taken. ACTED_ON carries a validated action; an
            # ADDRESSED_PENDING_VERIFICATION finding may legitimately have
            # action_taken False, signalling the reviser must act.
            if not disp.get("action_taken", False):
                revision_actions_required = True
        if normalized_family in _PROJECTION_UNCHANGED_FAMILIES:
            unchanged_findings.append(sf_id)

    return {
        "manifest_id": manifest.manifest_id,
        "input_set_hash": manifest.input_set_hash,
        "revision_number": manifest.revision_number,
        "finding_summaries": finding_summaries,
        "unavailable_evidence": unavailable_evidence,
        "occurrence_failed_dropped_malformed": failed_dropped_malformed,
        "total_occurrences": len(occurrences),
        "total_findings": len(briefing.findings),
        # CL4 (Plan Step 7): actionable history, disposed history, unchanged
        # findings, and the revision-actions-required flag.
        "actionable_findings": actionable_findings,
        "disposed_history": disposed_history,
        "unchanged_findings": unchanged_findings,
        "revision_actions_required": revision_actions_required,
        # Four no-X fields
        "no_open_blocking_findings": briefing.no_open_blocking_findings,
        "no_additional_findings": briefing.no_additional_findings,
        "no_known_findings": briefing.no_known_findings,
        "no_adjacent_text_match": briefing.no_adjacent_text_match,
        # No verdict fields — this is a read-only projection
    }


# ══════════════════════════════════════════════════════════════════════
# Phase 6b: Gate projection
# ══════════════════════════════════════════════════════════════════════


def project_gate_input(
    manifest: LedgerRevisionManifest,
    briefing: DomainBriefingEnvelope,
    occurrences: list[CritiqueOccurrenceEnvelope],
    rec_result: dict[str, Any],
    disp_result: dict[str, Any],
    custody_result: dict[str, Any],
) -> dict[str, Any]:
    """Produce a read-only gate input projection.

    Exposes cumulative truth from custody, reconciliation, disposition,
    manifest, and briefing phases without issuing any verdict. Includes
    four distinct no-X fields.

    Failed/dropped/malformed producers map correctly:
      - no findings → no additional findings flag
      - custody failure → custody_valid = False
      - unavailable evidence → tracked in unavailable_evidence

    CL4 (Plan Step 8): the projection additionally carries the truthful
    ledger/accounting/disposition/revision/verification state the gate
    must ground any acceptance claim on:
      - accepted_ledger_revision: the accepted manifest identity (manifest
        id, revision number, input-set hash, prior-revision hash).
      - occurrence_coverage_proof: the exact per-occurrence reconciliation
        accounting row count vs. input occurrence count and a completeness
        flag derived from occurrence_accounting.
      - disposition_state: per-finding normalized family, reopen predicate,
        staleness flag, evidence refs, action state, plus family counts and
        the disposition accepted flag.
      - revision_actions: actionable findings, the revision-actions-required
        flag, and declared revision actions from the briefing.
      - independent_verification: verified (resolved-verified) and
        pending-verification findings plus a has-verification-evidence flag.

    Args:
        manifest: The accepted manifest.
        briefing: The domain briefing.
        occurrences: All occurrence envelopes.
        rec_result: Output of apply_reconciliation_events.
        disp_result: Output of apply_disposition_events.
        custody_result: Output of validate_occurrence_custody.

    Returns:
        Dict with projection fields. Never contains 'verdict', 'proceed',
        or 'block' keys.
    """
    disposition_map = disp_result.get("disposition_map", {})

    # Count occurrences by parse status
    failed_count = sum(
        1 for occ in occurrences
        if occ.parse_status in (
            ParseStatus.FAILED.value,
            ParseStatus.DROPPED.value,
            ParseStatus.MALFORMED.value,
        )
    )

    # Count blocking and open findings
    blocking_count = len(briefing.blocked_findings)
    open_count = len(briefing.open_findings)

    # Count reopen events from reconciliation
    reopen_count = len(rec_result.get("reopen_events", []))

    # Track unavailable evidence
    unavailable_evidence: dict[str, dict[str, Any]] = {}
    for occ in occurrences:
        if occ.evidence_availability == EvidenceAvailability.UNAVAILABLE.value:
            unavailable_evidence[occ.occurrence_id] = {
                "reason": occ.unavailable_reason,
                "reopen_condition": occ.reopen_condition,
            }

    # CL4 (Plan Step 8): accepted ledger revision identity.
    accepted_ledger_revision = {
        "manifest_id": manifest.manifest_id,
        "revision_number": manifest.revision_number,
        "input_set_hash": manifest.input_set_hash,
        "prior_revision_hash": manifest.prior_revision_hash,
    }

    # CL4 (Plan Step 8): exact occurrence coverage proof grounded in the
    # per-occurrence accounting emitted by apply_reconciliation_events.
    occurrence_accounting = list(rec_result.get("occurrence_accounting", []))
    occurrence_coverage_proof = {
        "total_input_occurrences": len(occurrences),
        "accounting_row_count": len(occurrence_accounting),
        "complete": len(occurrence_accounting) == len(occurrences),
        "reconciliation_accepted": rec_result.get("accepted", False),
        "occurrence_accounting": occurrence_accounting,
    }

    # CL4 (Plan Step 8): per-finding disposition state and family counts.
    # Iterate over the union of briefing findings and the disposition_map so
    # no known finding disappears from the gate's view.
    all_known_findings = sorted(
        set(briefing.findings) | set(disposition_map.keys())
    )
    disposition_state_findings: dict[str, dict[str, Any]] = {}
    actionable_findings: list[str] = []
    verified_findings: list[str] = []
    pending_verification_findings: list[str] = []
    revision_actions_required = False
    has_verification_evidence = False
    for sf_id in all_known_findings:
        disp = disposition_map.get(sf_id, {})
        family = disp.get("family", DispositionFamily.UNKNOWN.value)
        normalized_family = _normalize_disposition_family(family)
        evidence_refs = list(disp.get("evidence_refs", []))
        disposition_state_findings[sf_id] = {
            "family": family,
            "normalized_family": normalized_family,
            "is_reopen": disp.get("is_reopen", False),
            "reopen_predicate": disp.get("reopen_predicate"),
            "staleness_check_deferred": disp.get("staleness_check_deferred", False),
            "evidence_refs": evidence_refs,
            "action_taken": disp.get("action_taken", False),
        }
        if normalized_family in _PROJECTION_ACTIONABLE_FAMILIES:
            actionable_findings.append(sf_id)
            if not disp.get("action_taken", False):
                revision_actions_required = True
        if normalized_family == DispositionFamily.RESOLVED_VERIFIED.value:
            verified_findings.append(sf_id)
            if evidence_refs:
                has_verification_evidence = True
        elif (
            normalized_family
            == DispositionFamily.ADDRESSED_PENDING_VERIFICATION.value
        ):
            pending_verification_findings.append(sf_id)
    disposition_state = {
        "disposition_accepted": disp_result.get("accepted", False),
        "family_counts": dict(disp_result.get("family_counts", {})),
        "findings": disposition_state_findings,
    }

    # CL4 (Plan Step 8): revision-action coverage for the gate.
    revision_actions = {
        "actionable_findings": actionable_findings,
        "revision_actions_required": revision_actions_required,
        "declared_revision_actions": list(briefing.revision_actions),
    }

    # CL4 (Plan Step 8): independent verification state — which findings are
    # verified vs. pending and whether verification evidence is present.
    independent_verification = {
        "verified_findings": verified_findings,
        "pending_verification_findings": pending_verification_findings,
        "has_verification_evidence": has_verification_evidence,
    }

    return {
        "manifest_id": manifest.manifest_id,
        "input_set_hash": manifest.input_set_hash,
        # CL4 (Plan Step 8): enriched truthful-claim state.
        "accepted_ledger_revision": accepted_ledger_revision,
        "occurrence_coverage_proof": occurrence_coverage_proof,
        "disposition_state": disposition_state,
        "revision_actions": revision_actions,
        "independent_verification": independent_verification,
        # Custody signals
        "custody_valid": custody_result.get("valid", False),
        "custody_failure_count": len(custody_result.get("failures", [])),
        # Reconciliation signals
        "reconciliation_accepted": rec_result.get("accepted", False),
        "reconciliation_failure_count": len(rec_result.get("failures", [])),
        # Disposition signals
        "disposition_accepted": disp_result.get("accepted", False),
        "disposition_failure_count": len(disp_result.get("failures", [])),
        # Finding counts
        "total_semantic_findings": rec_result.get("total_semantic_findings", 0),
        "blocking_finding_count": blocking_count,
        "open_finding_count": open_count,
        "accepted_risk_count": len(briefing.accepted_risk_findings),
        "unknown_count": len(briefing.unknown_findings),
        # Occurrence stats
        "total_occurrences": len(occurrences),
        "occurrence_failed_dropped_malformed": failed_count,
        # Reopen
        "reopen_event_count": reopen_count,
        # Unavailable evidence
        "unavailable_evidence": unavailable_evidence,
        # Budget
        "budget_level": briefing.budget_level,
        "is_truncated": briefing.is_truncated,
        # Four no-X fields
        "no_open_blocking_findings": briefing.no_open_blocking_findings,
        "no_additional_findings": briefing.no_additional_findings,
        "no_known_findings": briefing.no_known_findings,
        "no_adjacent_text_match": briefing.no_adjacent_text_match,
        # No verdict fields
    }


# ══════════════════════════════════════════════════════════════════════
# Phase 7: Complete replay
# ══════════════════════════════════════════════════════════════════════


def replay_full(
    occurrences: list[CritiqueOccurrenceEnvelope],
    reconciliations: list[FindingReconciliationEvent],
    dispositions: list[FindingDispositionEvent],
    wbc_receipt_chain: dict[str, Any] | None = None,
    budget_level: str = "standard",
    domain_assignments: dict[str, str] | None = None,
    domain_completeness: dict[str, bool] | None = None,
    allow_reopen: bool = True,
    prior_manifest: LedgerRevisionManifest | None = None,
    expected_prior_revision_hash: str | None = None,
    freshness_vectors: list | None = None,
) -> dict[str, Any]:
    """Execute a complete semantic loop replay.

    Runs all phases in order: custody → reconciliation → disposition →
    manifest → briefing → projections. Fails before projections if any
    phase produces a typed validation failure.

    Args:
        occurrences: All critique occurrence envelopes.
        reconciliations: Ordered reconciliation events.
        dispositions: Ordered disposition events.
        wbc_receipt_chain: WBC receipt chain for custody validation.
        budget_level: Briefing budget level.
        domain_assignments: Semantic finding → domain assignments.
        domain_completeness: Domain → is_complete map.
        allow_reopen: Whether REOPEN events are permitted.

    Returns:
        Dict with keys: custody, reconciliation, disposition, manifest,
        briefing, reviser_projection, gate_projection.

    Raises:
        SemanticLoopError: If any phase fails validation, before any
            projection is produced.
    """
    if wbc_receipt_chain is None:
        wbc_receipt_chain = {}

    # Phase 0: Pre-validate occurrences and attempt lifecycle.  Metadata
    # fields are optional for imported legacy rows; when present they are
    # enforced rather than guessed.
    occurrence_ids: set[str] = set()
    for occ in occurrences:
        if occ.schema_version != SCHEMA_VERSION:
            raise SemanticLoopError(
                mode=FailureMode.SCHEMA_INCOMPATIBLE,
                detail=f"Occurrence {occ.occurrence_id} uses {occ.schema_version}",
            )
        # CL4 (Plan Step 3): FAILED and DROPPED no longer hard-stop replay
        # before reconciliation. They now flow into apply_reconciliation_events
        # and receive an explicit "excluded-from-finding-map" accounting row
        # with a reason, so they are surfaced at the gate rather than silently
        # ignored or raised before reconciliation runs. The typed failure modes
        # OCCURRENCE_PARSE_FAILED / ATTEMPT_DROPPED are retained on FailureMode
        # for legacy compatibility but are no longer raised here.
        if not occ.occurrence_id:
            raise SemanticLoopError(
                mode=FailureMode.OCCURRENCE_MISSING_ID,
                detail="Occurrence has empty occurrence_id",
            )
        if occ.occurrence_id in occurrence_ids:
            raise SemanticLoopError(
                mode=FailureMode.OCCURRENCE_DUPLICATE_ID,
                detail=f"Duplicate occurrence_id {occ.occurrence_id}",
            )
        occurrence_ids.add(occ.occurrence_id)
        if occ.metadata.get("start_persisted") is False:
            raise SemanticLoopError(
                mode=FailureMode.START_PERSISTENCE_FAILED,
                detail=f"Attempt {occ.attempt_id} lacks durable start evidence",
            )
        if occ.metadata.get("terminal_persisted") is False:
            raise SemanticLoopError(
                mode=FailureMode.TERMINAL_PERSISTENCE_FAILED,
                detail=f"Attempt {occ.attempt_id} lacks durable terminal evidence",
            )
        terminal_count = occ.metadata.get("terminal_outcome_count", 1)
        if terminal_count != 1:
            raise SemanticLoopError(
                mode=FailureMode.TERMINAL_OUTCOME_INVALID,
                detail=(
                    f"Attempt {occ.attempt_id} has {terminal_count} terminal "
                    "outcomes; exactly one is required"
                ),
            )
        if "owner" in occ.metadata and not occ.metadata.get("owner"):
            raise SemanticLoopError(
                mode=FailureMode.OWNERSHIP_MISSING,
                detail=f"Occurrence {occ.occurrence_id} has no owner",
            )
        if occ.metadata.get("evidence_fresh") is False:
            raise SemanticLoopError(
                mode=FailureMode.EVIDENCE_STALE,
                detail=f"Occurrence {occ.occurrence_id} evidence is stale",
            )
        if (
            occ.metadata.get("required_for_briefing") is True
            and occ.evidence_availability == EvidenceAvailability.UNAVAILABLE.value
        ):
            raise SemanticLoopError(
                mode=FailureMode.BRIEFING_INPUT_UNAVAILABLE,
                detail=f"Required briefing input {occ.occurrence_id} is unavailable",
            )
        if (
            occ.parse_status == ParseStatus.TOMBSTONED.value
            and not occ.metadata.get("tombstone_reason")
        ):
            raise SemanticLoopError(
                mode=FailureMode.TOMBSTONE_INVALID,
                detail=f"Tombstone {occ.occurrence_id} lacks tombstone_reason",
            )

    valid_authorities = {item.value for item in Authority}
    for event in [*reconciliations, *dispositions]:
        if event.schema_version != SCHEMA_VERSION:
            raise SemanticLoopError(
                mode=FailureMode.SCHEMA_INCOMPATIBLE,
                detail=f"Event uses incompatible schema {event.schema_version}",
            )
        if event.authority not in valid_authorities:
            raise SemanticLoopError(
                mode=FailureMode.OWNERSHIP_MISSING,
                detail="Semantic event lacks accepted evaluator/curator authority",
            )

    # Phase 1: Custody
    custody_result = validate_occurrence_custody(occurrences, wbc_receipt_chain)
    if not custody_result["valid"]:
        raise SemanticLoopError(
            mode=custody_result["failures"][0]["mode"],
            detail=custody_result["failures"][0].get("detail", "Custody validation failed"),
            failures=custody_result["failures"],
        )

    # Phase 2: Reconciliation
    rec_result = apply_reconciliation_events(occurrences, reconciliations, allow_reopen=allow_reopen)
    hard_failures = [
        f for f in rec_result["failures"]
        if f["mode"] != FailureMode.RECONCILIATION_INFERRED_SAMENESS.value
    ]
    if hard_failures:
        raise SemanticLoopError(
            mode=hard_failures[0]["mode"],
            detail=hard_failures[0].get("detail", "Reconciliation failed"),
            failures=rec_result["failures"],
        )

    # CL4 (Plan Step 4): exact accounting completeness proof. The prior
    # parseable-ID coverage heuristic is replaced by a proof grounded in the
    # per-occurrence accounting emitted by apply_reconciliation_events. Every
    # input occurrence must be covered by exactly one accounting row.
    # Finding-membership completeness (unmapped and multiply-mapped eligible
    # occurrences, relationship-aware so disputed MERGEs are retained) is
    # already enforced inside apply_reconciliation_events and surfaced through
    # the hard-failure filter above; this block independently re-verifies the
    # accounting-row invariant so a future regression that emits incomplete or
    # duplicate accounting can never reach the gate.
    occurrence_accounting = rec_result.get("occurrence_accounting", [])
    accounted_ids = [row["occurrence_id"] for row in occurrence_accounting]
    input_id_set = {occ.occurrence_id for occ in occurrences}
    missing_rows = sorted(input_id_set - set(accounted_ids))
    duplicate_rows = sorted(
        {oid for oid in accounted_ids if accounted_ids.count(oid) > 1}
    )
    if missing_rows:
        raise SemanticLoopError(
            mode=FailureMode.OCCURRENCE_UNMAPPED,
            detail=(
                "Accounting completeness proof failed: input occurrences "
                f"missing an accounting row: {missing_rows}"
            ),
        )
    if duplicate_rows:
        raise SemanticLoopError(
            mode=FailureMode.OCCURRENCE_MULTIPLY_MAPPED,
            detail=(
                "Accounting uniqueness proof failed: occurrences have "
                f"multiple accounting rows: {duplicate_rows}"
            ),
        )

    # Phase 3: Disposition
    # CL5: compute the canonical briefing-input hash from the same live sources
    # the disposition layer consumes (occurrence envelopes, reconciliation
    # events, and the disposition events themselves) and pass it so that a
    # disposition recording a stored baseline hash is compared against it
    # mechanically. This resolves the cl5_staleness_deferral reopen predicate
    # for the live production path; the detection remains advisory-only and
    # never grants authority.
    live_input_hash = compute_input_hash(occurrences, reconciliations, dispositions)
    disp_result = apply_disposition_events(
        rec_result["finding_map"], dispositions, input_hash=live_input_hash
    )
    if not disp_result["accepted"]:
        raise SemanticLoopError(
            mode=disp_result["failures"][0]["mode"],
            detail=disp_result["failures"][0].get("detail", "Disposition failed"),
            failures=disp_result["failures"],
        )
    # CL4 (Plan Step 6.3): redundant closure backstop. apply_disposition_events
    # is the PRIMARY closure-evidence enforcement for the new RESOLVED_VERIFIED
    # value (Step 6.1). This inline check is the redundant backstop: it
    # inspects BOTH the legacy RESOLVED value and the new RESOLVED_VERIFIED
    # value via _normalize_disposition_family so a closure disposition of
    # either family that lacks a reason or verification evidence can never
    # reach projection. It additionally requires reason_subcode, matching the
    # historical closure contract for legacy RESOLVED and extending it
    # equivalently to the new verified value.
    unsupported_closures = [
        disp.disposition_id
        for disp in dispositions
        if (
            _normalize_disposition_family(disp.family)
            == DispositionFamily.RESOLVED_VERIFIED.value
            and (not disp.evidence_refs or not disp.reason_subcode)
        )
    ]
    if unsupported_closures:
        raise SemanticLoopError(
            mode=FailureMode.CLOSURE_UNSUPPORTED,
            detail=(
                "Closure dispositions lack reason/evidence: "
                f"{unsupported_closures}"
            ),
        )

    # Phase 4: Manifest
    manifest = construct_manifest(
        occurrences, rec_result, disp_result,
        domain_completeness=domain_completeness,
        prior_manifest=prior_manifest,
        expected_prior_revision_hash=expected_prior_revision_hash,
    )

    # Phase 5: Briefing
    briefing = build_briefing(
        manifest, disp_result, rec_result["finding_map"],
        budget_level=budget_level,
        domain_assignments=domain_assignments,
        rec_result=rec_result,
        occurrences=occurrences,
        freshness_vectors=freshness_vectors,
    )

    # Phase 6: Projections
    reviser = project_reviser_input(manifest, briefing, occurrences, disp_result)
    gate = project_gate_input(
        manifest, briefing, occurrences,
        rec_result, disp_result, custody_result,
    )

    projection_fields = (
        "no_open_blocking_findings",
        "no_additional_findings",
        "no_known_findings",
        "no_adjacent_text_match",
    )
    if any(
        reviser[field] != gate[field] or reviser[field] != getattr(briefing, field)
        for field in projection_fields
    ):
        raise SemanticLoopError(
            mode=FailureMode.REPLAY_PROJECTION_MISMATCH,
            detail="Reviser, gate, and briefing projections disagree",
        )

    return {
        "custody": custody_result,
        "reconciliation": rec_result,
        "disposition": disp_result,
        "manifest": manifest,
        "briefing": briefing,
        "reviser_projection": reviser,
        "gate_projection": gate,
    }
