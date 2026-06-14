"""Confirm EvidenceStatus / TrustClass identity across shim boundary.

The extraction task (T3) moved the canonical enum definitions from
``evidence_contract.py`` into ``arnold/pipeline/types.py`` and added a
re-export shim so every existing import site keeps working.

These tests assert that the enum *classes* are the same object (``is``,
not ``==``) and that the LEGACY/CANONICAL helpers are left untouched in
the evidence_contract module.
"""

from __future__ import annotations

from arnold.pipeline.types import EvidenceStatus as CanonicalEvidenceStatus
from arnold.pipeline.types import TrustClass as CanonicalTrustClass

from arnold.pipelines.megaplan.orchestration.evidence_contract import (
    CANONICAL_EVIDENCE_STATUSES,
    LEGACY_EVIDENCE_STATUS_ALIASES,
    EvidenceStatus,
    EvidenceStatusNormalization,
    TrustClass,
)


def test_evidence_status_is_identity() -> None:
    """The shim import and the canonical import are the same class object."""
    assert EvidenceStatus is CanonicalEvidenceStatus


def test_trust_class_is_identity() -> None:
    """The shim import and the canonical import are the same class object."""
    assert TrustClass is CanonicalTrustClass


def test_evidence_status_vocabulary_preserved() -> None:
    """All five canonical status members are present."""
    assert {s.value for s in EvidenceStatus} == {
        "satisfied",
        "unsatisfied",
        "unknown",
        "not_applicable",
        "waived",
    }


def test_trust_class_vocabulary_preserved() -> None:
    """All four canonical trust-class members are present."""
    assert {t.value for t in TrustClass} == {
        "claim",
        "evidence",
        "judgment",
        "routing",
    }


def test_legacy_aliases_still_in_place() -> None:
    """LEGACY_EVIDENCE_STATUS_ALIASES maps old status strings to canonical enums."""
    assert LEGACY_EVIDENCE_STATUS_ALIASES["not_evaluated"] is EvidenceStatus.unknown
    assert LEGACY_EVIDENCE_STATUS_ALIASES["fail-not-success"] is EvidenceStatus.unsatisfied


def test_canonical_statuses_frozenset_still_in_place() -> None:
    """CANONICAL_EVIDENCE_STATUSES is the frozenset of all status string values."""
    assert CANONICAL_EVIDENCE_STATUSES == frozenset(
        {"satisfied", "unsatisfied", "unknown", "not_applicable", "waived"}
    )


def test_evidence_status_normalization_still_importable() -> None:
    """EvidenceStatusNormalization dataclass is still defined in evidence_contract."""
    result = EvidenceStatusNormalization(status=EvidenceStatus.satisfied)
    assert result.status is EvidenceStatus.satisfied
    assert result.diagnostics == {}
