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

    # Disposition failures
    DISPOSITION_ORPHAN_FINDING = "DISPOSITION_ORPHAN_FINDING"
    DISPOSITION_DUPLICATE_EVENT = "DISPOSITION_DUPLICATE_EVENT"
    DISPOSITION_UNKNOWN_FAMILY = "DISPOSITION_UNKNOWN_FAMILY"
    DISPOSITION_MISSING_ID = "DISPOSITION_MISSING_ID"
    DISPOSITION_INCOMPLETE = "DISPOSITION_INCOMPLETE"
    CLOSURE_UNSUPPORTED = "CLOSURE_UNSUPPORTED"

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
    """
    failures: list[dict[str, Any]] = []
    reopen_events: list[dict[str, Any]] = []
    finding_map: dict[str, set[str]] = {}
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

        # Inferred sameness check (non-DUPLICATE relationship without reason)
        if (
            rec.relationship != Relationship.DUPLICATE.value
            and not rec.reason
            and rec.relationship != Relationship.REOPEN.value
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

    # Convert sets to sorted lists for deterministic output
    finding_map_lists: dict[str, list[str]] = {
        sf_id: sorted(oids)
        for sf_id, oids in finding_map.items()
    }

    # Check for unreconciled occurrences (those not in any finding_map)
    all_reconciled: set[str] = set()
    for oids in finding_map.values():
        all_reconciled.update(oids)

    return {
        "accepted": len([f for f in failures if f["mode"] not in (
            FailureMode.RECONCILIATION_INFERRED_SAMENESS.value,
        )]) == 0,
        "finding_map": finding_map_lists,
        "total_semantic_findings": len(finding_map_lists),
        "failures": failures,
        "reopen_events": reopen_events,
    }


# ══════════════════════════════════════════════════════════════════════
# Phase 3: Disposition
# ══════════════════════════════════════════════════════════════════════


def apply_disposition_events(
    finding_map: dict[str, Any],
    dispositions: list[FindingDispositionEvent],
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
    """
    failures: list[dict[str, Any]] = []
    family_counts: dict[str, int] = {}
    disposition_map: dict[str, dict[str, Any]] = {}
    seen_disposition_ids: set[str] = set()

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

    valid_statuses = frozenset({
        ParseStatus.SELECTED.value,
        ParseStatus.COMPLETED.value,
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
        cross_domain_refs=(),
        timestamp_utc=(prior_manifest.timestamp_utc if prior_manifest else ""),
    )

    return manifest


# ══════════════════════════════════════════════════════════════════════
# Phase 5: Briefing
# ══════════════════════════════════════════════════════════════════════


def build_briefing(
    manifest: LedgerRevisionManifest,
    disp_result: dict[str, Any],
    finding_map: dict[str, Any],
    budget_level: str = "standard",
    domain_assignments: dict[str, str] | None = None,
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

    # Classify findings by disposition family
    open_findings: list[str] = []
    blocked_findings: list[str] = []
    accepted_risk_findings: list[str] = []
    unknown_findings: list[str] = []
    all_findings: list[str] = []

    for sf_id in sorted(normalized_fm.keys()):
        all_findings.append(sf_id)
        disp = disposition_map.get(sf_id, {})
        family = disp.get("family", DispositionFamily.UNKNOWN.value)

        if family in _OPEN_FAMILIES:
            open_findings.append(sf_id)
        elif family in _BLOCKED_FAMILIES:
            blocked_findings.append(sf_id)
        elif family == DispositionFamily.ACCEPTED_RISK.value:
            accepted_risk_findings.append(sf_id)
        elif family == DispositionFamily.UNKNOWN.value:
            unknown_findings.append(sf_id)
        elif family == DispositionFamily.DUPLICATE.value:
            # Duplicates are tracked but not classified as open/blocked
            pass
        elif family == DispositionFamily.RESOLVED.value:
            # Resolved findings are closed
            pass

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

    # Budget enforcement: finding spillover
    spillover: list[str] = []
    is_truncated = False
    truncation_warning: Optional[str] = None

    if max_findings is not None and len(all_findings) > max_findings:
        is_truncated = True
        spillover = all_findings[max_findings:]
        all_findings = all_findings[:max_findings]
        # Filter spillover from classifications
        spillover_set = set(spillover)
        open_findings = [f for f in open_findings if f not in spillover_set]
        blocked_findings = [f for f in blocked_findings if f not in spillover_set]
        accepted_risk_findings = [f for f in accepted_risk_findings if f not in spillover_set]
        unknown_findings = [f for f in unknown_findings if f not in spillover_set]
        truncation_warning = (
            f"{len(spillover)} finding(s) exceed {budget_level} budget "
            f"({max_findings} max). Linked via spillover_findings — not "
            f"silently discarded."
        )

    briefing = DomainBriefingEnvelope(
        briefing_id=(
            "briefing-"
            + hashlib.sha256(
                (
                    canonical_hash(manifest)
                    + "|"
                    + budget_level
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
        open_findings=tuple(open_findings),
        blocked_findings=tuple(blocked_findings),
        accepted_risk_findings=tuple(accepted_risk_findings),
        unknown_findings=tuple(unknown_findings),
        cross_domain_refs=(),
        spillover_findings=tuple(spillover),
        no_additional_findings=len(all_findings) == 0,
        no_open_blocking_findings=(len(open_findings) == 0 and len(blocked_findings) == 0),
        no_known_findings=len(all_findings) == 0,
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

    return {
        "manifest_id": manifest.manifest_id,
        "input_set_hash": manifest.input_set_hash,
        "revision_number": manifest.revision_number,
        "finding_summaries": finding_summaries,
        "unavailable_evidence": unavailable_evidence,
        "occurrence_failed_dropped_malformed": failed_dropped_malformed,
        "total_occurrences": len(occurrences),
        "total_findings": len(briefing.findings),
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

    return {
        "manifest_id": manifest.manifest_id,
        "input_set_hash": manifest.input_set_hash,
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
        if occ.parse_status == ParseStatus.FAILED.value:
            raise SemanticLoopError(
                mode=FailureMode.OCCURRENCE_PARSE_FAILED,
                detail=f"Occurrence {occ.occurrence_id} has parse_status=FAILED",
            )
        if occ.parse_status == ParseStatus.DROPPED.value:
            raise SemanticLoopError(
                mode=FailureMode.ATTEMPT_DROPPED,
                detail=f"Occurrence {occ.occurrence_id} was dropped",
            )
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

    mapped_counts: dict[str, int] = {}
    for mapped_ids in rec_result["finding_map"].values():
        for occurrence_id in mapped_ids:
            mapped_counts[occurrence_id] = mapped_counts.get(occurrence_id, 0) + 1
    parseable_ids = {
        occ.occurrence_id
        for occ in occurrences
        if occ.parse_status in {ParseStatus.SELECTED.value, ParseStatus.COMPLETED.value}
    }
    unmapped = sorted(parseable_ids - set(mapped_counts))
    if unmapped:
        raise SemanticLoopError(
            mode=FailureMode.OCCURRENCE_UNMAPPED,
            detail=f"Parseable occurrences lack reconciliation: {unmapped}",
        )
    multiply_mapped = sorted(
        occurrence_id for occurrence_id, count in mapped_counts.items() if count != 1
    )
    if multiply_mapped:
        raise SemanticLoopError(
            mode=FailureMode.OCCURRENCE_MULTIPLY_MAPPED,
            detail=f"Occurrences map to multiple semantic findings: {multiply_mapped}",
        )

    # Phase 3: Disposition
    disp_result = apply_disposition_events(rec_result["finding_map"], dispositions)
    if not disp_result["accepted"]:
        raise SemanticLoopError(
            mode=disp_result["failures"][0]["mode"],
            detail=disp_result["failures"][0].get("detail", "Disposition failed"),
            failures=disp_result["failures"],
        )
    unsupported_closures = [
        disp.disposition_id
        for disp in dispositions
        if (
            disp.family == DispositionFamily.RESOLVED.value
            and (not disp.evidence_refs or not disp.reason_subcode)
        )
    ]
    if unsupported_closures:
        raise SemanticLoopError(
            mode=FailureMode.CLOSURE_UNSUPPORTED,
            detail=f"Resolved dispositions lack reason/evidence: {unsupported_closures}",
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
