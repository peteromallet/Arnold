"""Tests for the M11 prerequisite status vocabulary (Step 1) and joins (Step 2).

Covers:
* The prerequisite status enumeration rejects unknown statuses.
* The prerequisite record shape enforces mandatory fields (owner, artifact).
* BLOCKED/EXPIRED statuses require next_action.
* WAIVED status requires expected_class and next_action justification.
* Deterministic digest computation.
* Step 2 join: missing evidence produces typed BLOCKED records.
* Step 2 join: mixed available/missing produces correct per-family statuses.
* Step 2 join: stale digests produce EXPIRED.
* Step 2 join: schedule mismatches produce PENDING.
* Step 2 join: empty artifact strings are BLOCKED.
* Step 2 join: deterministic output for identical inputs.
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.orchestration.m11_acceptance import (
    KNOWN_STATUSES,
    PREDECESSOR_FAMILIES,
    AcceptanceRow,
    PrerequisiteRecord,
    PrerequisiteStatus,
    join_prerequisite_evidence,
    m11_debt_gate,
    schema_descriptor,
)

from arnold_pipelines.megaplan.cloud.status_retirement import (
    LEGACY_RETIREMENT_ELIGIBILITY_SCHEMA,
    LEGACY_RETIREMENT_REQUIRED_GATES,
    LegacyRetirementEligibility,
    compute_legacy_retirement_eligibility,
)


# ── Shape test ───────────────────────────────────────────────────────────


def test_prerequisite_status_shape():
    """Step 1: the prerequisite status vocabulary rejects unknown statuses
    and enforces the required shape (owner, artifact, digest, expected_class,
    next_action)."""

    # --- Known statuses construct successfully ----------------------------
    for status in PrerequisiteStatus:
        record = PrerequisiteRecord(
            owner="T1",
            artifact="evidence/m11-acceptance.json",
            expected_class="m11_acceptance.PrerequisiteRecord",
            status=status,
            next_action="Step 2" if status in (PrerequisiteStatus.BLOCKED, PrerequisiteStatus.EXPIRED, PrerequisiteStatus.WAIVED) else "",
        )
        assert record.status is status
        assert record.owner == "T1"
        assert record.artifact == "evidence/m11-acceptance.json"
        assert record.digest  # auto-computed
        # Digest is deterministic: same inputs → same digest.
        record2 = PrerequisiteRecord(
            owner="T1",
            artifact="evidence/m11-acceptance.json",
            expected_class="m11_acceptance.PrerequisiteRecord",
            status=status,
            next_action="Step 2" if status in (PrerequisiteStatus.BLOCKED, PrerequisiteStatus.EXPIRED, PrerequisiteStatus.WAIVED) else "",
        )
        assert record.digest == record2.digest

    # --- Unknown status string is rejected via from_dict ------------------
    with pytest.raises(ValueError, match="unknown status"):
        PrerequisiteRecord.from_dict(
            {
                "owner": "T1",
                "artifact": "x",
                "status": "nonexistent_status",
            }
        )

    # --- Unknown status object is rejected at construction -----------------
    with pytest.raises(ValueError, match="unknown status"):
        PrerequisiteRecord(
            owner="T1",
            artifact="x",
            status=None,  # type: ignore[arg-type]
        )

    # --- owner is required -------------------------------------------------
    with pytest.raises(ValueError, match="owner is required"):
        PrerequisiteRecord(owner="", artifact="x")

    # --- artifact is required ----------------------------------------------
    with pytest.raises(ValueError, match="artifact is required"):
        PrerequisiteRecord(owner="T1", artifact="")

    # --- BLOCKED must carry a next_action ---------------------------------
    with pytest.raises(ValueError, match="next_action"):
        PrerequisiteRecord(
            owner="T1",
            artifact="x",
            status=PrerequisiteStatus.BLOCKED,
        )

    # --- EXPIRED must carry a next_action ---------------------------------
    with pytest.raises(ValueError, match="next_action"):
        PrerequisiteRecord(
            owner="T1",
            artifact="x",
            status=PrerequisiteStatus.EXPIRED,
        )

    # --- WAIVED must carry expected_class AND next_action -----------------
    with pytest.raises(ValueError, match="expected_class"):
        PrerequisiteRecord(
            owner="T1",
            artifact="x",
            status=PrerequisiteStatus.WAIVED,
            next_action="override approved by X",
        )
    with pytest.raises(ValueError, match="next_action"):
        PrerequisiteRecord(
            owner="T1",
            artifact="x",
            status=PrerequisiteStatus.WAIVED,
            expected_class="OverrideAuthority",
        )

    # --- WAIVED with both justification fields constructs -----------------
    waived = PrerequisiteRecord(
        owner="T1",
        artifact="x",
        status=PrerequisiteStatus.WAIVED,
        expected_class="OverrideAuthority",
        next_action="override approved by X",
    )
    assert waived.status is PrerequisiteStatus.WAIVED

    # --- PENDING and SATISFIED are fine without next_action ---------------
    pending = PrerequisiteRecord(
        owner="T1",
        artifact="x",
        status=PrerequisiteStatus.PENDING,
    )
    assert pending.status is PrerequisiteStatus.PENDING

    satisfied = PrerequisiteRecord(
        owner="T1",
        artifact="x",
        status=PrerequisiteStatus.SATISFIED,
    )
    assert satisfied.status is PrerequisiteStatus.SATISFIED

    # --- NOT_REQUIRED constructs fine -------------------------------------
    not_req = PrerequisiteRecord(
        owner="T1",
        artifact="x",
        status=PrerequisiteStatus.NOT_REQUIRED,
    )
    assert not_req.status is PrerequisiteStatus.NOT_REQUIRED

    # --- to_dict / from_dict round-trip -----------------------------------
    original = PrerequisiteRecord(
        owner="T2",
        artifact="evidence/m11-joins.json",
        expected_class="Joiner",
        next_action="Step 5",
        status=PrerequisiteStatus.SATISFIED,
        detail="join output verified",
    )
    d = original.to_dict()
    assert d["owner"] == "T2"
    assert d["artifact"] == "evidence/m11-joins.json"
    assert d["status"] == "satisfied"
    assert d["detail"] == "join output verified"

    reconstructed = PrerequisiteRecord.from_dict(d)
    assert reconstructed.owner == original.owner
    assert reconstructed.artifact == original.artifact
    assert reconstructed.digest == original.digest
    assert reconstructed.status == original.status

    # --- Schema descriptor covers all statuses ----------------------------
    desc = schema_descriptor()
    assert set(desc["known_statuses"]) == set(s.value for s in KNOWN_STATUSES)
    assert desc["required_fields"] == [
        "owner",
        "artifact",
        "digest",
        "expected_class",
        "next_action",
        "status",
    ]

    # --- Digest changes when a visible field changes ----------------------
    a = PrerequisiteRecord(owner="T1", artifact="x", status=PrerequisiteStatus.PENDING)
    b = PrerequisiteRecord(owner="T1", artifact="y", status=PrerequisiteStatus.PENDING)
    assert a.digest != b.digest

    c = PrerequisiteRecord(owner="T1", artifact="x", status=PrerequisiteStatus.SATISFIED)
    assert a.digest != c.digest


# ── Step 2: prerequisite join ────────────────────────────────────────────


def test_missing_predecessor_evidence_is_prerequisite_incomplete():
    """Step 2: missing predecessor evidence produces typed BLOCKED records.

    When none of the required predecessor families are available, the join
    function must emit a BLOCKED PrerequisiteRecord for every family —
    never silently treat missing evidence as satisfied.
    """
    records = join_prerequisite_evidence(
        owner="T2",
        available_artifacts={},
    )

    # Every known family must produce a record
    assert len(records) == len(PREDECESSOR_FAMILIES)

    # All records must be BLOCKED when no evidence is available
    for r in records:
        assert r.status is PrerequisiteStatus.BLOCKED, (
            f"{r.expected_class}: expected BLOCKED, got {r.status.value}"
        )
        assert r.owner == "T2"
        assert r.artifact  # each must reference an expected path
        assert r.next_action  # BLOCKED requires next_action

    # Verify specific families produce expected artifacts
    artifacts = {r.expected_class: r.artifact for r in records}
    assert artifacts["m10_handoff"] == "evidence/m10-handoff.json"
    assert artifacts["wbc"] == "evidence/wbc.json"
    assert artifacts["runtime"] == "evidence/runtime.json"


def test_partial_predecessor_evidence_mixed_statuses():
    """Step 2: mixed available/missing evidence produces correct per-family statuses."""
    records = join_prerequisite_evidence(
        owner="T2",
        available_artifacts={
            "m10_handoff": "sha256:abc123def456",
            "wbc": "sha256:wbc111wbc222",
        },
    )

    status_map = {r.expected_class: r.status for r in records}

    # Supplied families are SATISFIED
    assert status_map["m10_handoff"] is PrerequisiteStatus.SATISFIED
    assert status_map["wbc"] is PrerequisiteStatus.SATISFIED

    # Missing families are BLOCKED
    assert status_map["runtime"] is PrerequisiteStatus.BLOCKED
    assert status_map["audit"] is PrerequisiteStatus.BLOCKED


def test_stale_digest_produces_expired():
    """Step 2: mismatched digest produces EXPIRED, not SATISFIED."""
    records = join_prerequisite_evidence(
        owner="T2",
        available_artifacts={
            "m10_handoff": "sha256:stale-digest-12345",
        },
        artifact_digests={
            "m10_handoff": "sha256:expected-digest-67890",
        },
    )

    m10 = next(r for r in records if r.expected_class == "m10_handoff")
    assert m10.status is PrerequisiteStatus.EXPIRED
    assert "digest mismatch" in m10.detail.lower()


def test_schedule_mismatch_produces_pending():
    """Step 2: schedule in non-terminal phase produces PENDING."""
    records = join_prerequisite_evidence(
        owner="T2",
        available_artifacts={
            "m10_handoff": "sha256:abc123def456",
        },
        schedule_state={
            "m10_handoff": "execute",
        },
    )

    m10 = next(r for r in records if r.expected_class == "m10_handoff")
    assert m10.status is PrerequisiteStatus.PENDING
    assert "execute" in m10.detail


def test_empty_artifact_string_is_blocked():
    """Step 2: an empty string artifact is treated as missing (BLOCKED)."""
    records = join_prerequisite_evidence(
        owner="T2",
        available_artifacts={
            "m10_handoff": "",
        },
    )

    m10 = next(r for r in records if r.expected_class == "m10_handoff")
    assert m10.status is PrerequisiteStatus.BLOCKED


def test_join_returns_deterministic_records():
    """Step 2: join is deterministic — same inputs produce identical records."""
    inputs: dict = {
        "owner": "T2",
        "available_artifacts": {
            "m10_handoff": "sha256:abc123",
            "wbc": "sha256:def456",
        },
    }

    records_a = join_prerequisite_evidence(**inputs)
    records_b = join_prerequisite_evidence(**inputs)

    assert len(records_a) == len(records_b)
    for ra, rb in zip(records_a, records_b):
        assert ra.digest == rb.digest
        assert ra.status is rb.status
        assert ra.artifact == rb.artifact


# ── Step 5: M11 no-debt gate ─────────────────────────────────────────────


def test_debt_gate_passes_clean_evidence():
    """Step 5: no-debt gate passes evidence without xfail/xpass/skip/debt."""
    result = m11_debt_gate(evidence_text="All tests passed. No issues found.")
    assert result["passed"] is True
    assert result["findings"] == []
    assert result["gate"] == "m11_no_debt"


def test_debt_gate_rejects_xfail():
    """Step 5: no-debt gate rejects evidence containing xfail markers."""
    result = m11_debt_gate(evidence_text="Test marked as xfail; will fix later.")
    assert result["passed"] is False
    assert any(f["kind"] == "xfail_xpass" for f in result["findings"])


def test_debt_gate_rejects_xpass():
    """Step 5: no-debt gate rejects evidence containing xpass markers."""
    result = m11_debt_gate(evidence_text="xpass: test unexpectedly passed.")
    assert result["passed"] is False
    assert any(f["kind"] == "xfail_xpass" for f in result["findings"])


def test_debt_gate_rejects_unexplained_skip():
    """Step 5: no-debt gate rejects evidence with unexplained skips."""
    result = m11_debt_gate(
        evidence_text="Test skipped without reason: not needed."
    )
    assert result["passed"] is False
    assert any(f["kind"] == "unexplained_skip" for f in result["findings"])


def test_debt_gate_rejects_unresolved_debt():
    """Step 5: no-debt gate rejects evidence with unresolved debt."""
    result = m11_debt_gate(
        evidence_text="unresolved debt: T42 has outstanding debt."
    )
    assert result["passed"] is False
    assert any(f["kind"] == "unresolved_debt" for f in result["findings"])


def test_debt_gate_rejects_prerequisite_debt_by_default():
    """Step 5: prerequisite debt is rejected by default (fail-closed)."""
    result = m11_debt_gate(
        evidence_text="unresolved prerequisite debt: T1 blocker."
    )
    assert result["passed"] is False
    assert any(
        f["kind"] == "unresolved_debt" and f.get("category") == "prerequisite"
        for f in result["findings"]
    )


def test_debt_gate_rejects_semantic_carrier_debt_by_default():
    """Step 5: semantic-carrier debt is rejected by default (fail-closed)."""
    result = m11_debt_gate(
        evidence_text="semantic-carrier debt: M8 evidence stale."
    )
    assert result["passed"] is False
    assert any(
        f["kind"] == "unresolved_debt" and f.get("category") == "semantic_carrier"
        for f in result["findings"]
    )


def test_debt_gate_allows_prerequisite_debt_when_opted_in():
    """Step 5: prerequisite debt can be allowed with explicit opt-in."""
    result = m11_debt_gate(
        evidence_text="unresolved prerequisite debt: T1 blocker.",
        allow_prerequisite_debt=True,
    )
    # prerequisite debt is filtered out
    assert not any(
        f.get("category") == "prerequisite" for f in result["findings"]
    )
    # Other markers still pass if clean
    assert result["passed"] is True


def test_debt_gate_allows_semantic_carrier_debt_when_opted_in():
    """Step 5: semantic-carrier debt can be allowed with explicit opt-in."""
    result = m11_debt_gate(
        evidence_text="semantic-carrier debt: M8 evidence stale.",
        allow_semantic_carrier_debt=True,
    )
    assert not any(
        f.get("category") == "semantic_carrier" for f in result["findings"]
    )
    assert result["passed"] is True


def test_debt_gate_opt_in_does_not_allow_everything():
    """Step 5: opt-in for one debt category does not suppress other findings."""
    result = m11_debt_gate(
        evidence_text=(
            "unresolved prerequisite debt: T1. xfail marker present. "
            "unexplained skip found."
        ),
        allow_prerequisite_debt=True,
    )
    # prerequisite is allowed, but xfail and unexplained skip still caught
    assert result["passed"] is False
    findings_kinds = {f["kind"] for f in result["findings"]}
    assert "xfail_xpass" in findings_kinds
    assert "unexplained_skip" in findings_kinds


def test_debt_gate_multiple_findings():
    """Step 5: no-debt gate reports all findings, not just the first."""
    result = m11_debt_gate(
        evidence_text=(
            "xfail: test_a. xpass: test_b. "
            "unexplained skip in test_c. "
            "unresolved debt in T42."
        )
    )
    assert result["passed"] is False
    assert len(result["findings"]) >= 4


def test_debt_gate_is_deterministic():
    """Step 5: debt gate results are deterministic."""
    text = "xfail: test_a. unresolved debt: T42."
    a = m11_debt_gate(evidence_text=text)
    b = m11_debt_gate(evidence_text=text)
    assert a == b


# ── Step 6: Acceptance rows ──────────────────────────────────────────────


def test_acceptance_row_shape():
    """Step 6: acceptance row validates owner and deterministic digest."""
    row = AcceptanceRow(
        owner="T6",
        input_version_vector={"m10_handoff": "sha256:abc123"},
        expected_decision="accepted",
        evidence_refs=["evidence/m11-acceptance.json"],
        prerequisite_status=PrerequisiteStatus.SATISFIED,
        retirement_disposition="pending",
    )
    assert row.owner == "T6"
    assert row.expected_decision == "accepted"
    assert row.digest  # auto-computed
    assert row.prerequisite_status is PrerequisiteStatus.SATISFIED
    assert row.retirement_disposition == "pending"


def test_acceptance_row_owner_required():
    """Step 6: acceptance row requires owner."""
    with pytest.raises(ValueError, match="owner is required"):
        AcceptanceRow(owner="")


def test_acceptance_row_rejects_unknown_decision():
    """Step 6: acceptance row rejects unknown expected_decision."""
    with pytest.raises(ValueError, match="unknown expected_decision"):
        AcceptanceRow(owner="T6", expected_decision="bogus_decision")


def test_acceptance_row_rejects_unknown_retirement_disposition():
    """Step 6: acceptance row rejects unknown retirement_disposition."""
    with pytest.raises(ValueError, match="unknown retirement_disposition"):
        AcceptanceRow(owner="T6", retirement_disposition="bogus_disposition")


def test_acceptance_row_digest_deterministic():
    """Step 6: same fields produce same digest."""
    a = AcceptanceRow(
        owner="T6",
        input_version_vector={"k": "v"},
        expected_decision="rejected",
        evidence_refs=["ref1"],
        prerequisite_status=PrerequisiteStatus.BLOCKED,
        retirement_disposition="not_eligible",
    )
    b = AcceptanceRow(
        owner="T6",
        input_version_vector={"k": "v"},
        expected_decision="rejected",
        evidence_refs=["ref1"],
        prerequisite_status=PrerequisiteStatus.BLOCKED,
        retirement_disposition="not_eligible",
    )
    assert a.digest == b.digest


def test_acceptance_row_digest_changes_with_fields():
    """Step 6: different fields produce different digests."""
    a = AcceptanceRow(
        owner="T6",
        input_version_vector={"k": "v"},
        expected_decision="accepted",
        prerequisite_status=PrerequisiteStatus.SATISFIED,
    )
    b = AcceptanceRow(
        owner="T6",
        input_version_vector={"k": "v"},
        expected_decision="rejected",
        prerequisite_status=PrerequisiteStatus.SATISFIED,
    )
    assert a.digest != b.digest


def test_acceptance_row_to_from_dict_roundtrip():
    """Step 6: to_dict / from_dict round-trip preserves all fields."""
    original = AcceptanceRow(
        owner="T6",
        input_version_vector={"m10_handoff": "sha256:abc", "wbc": "sha256:def"},
        expected_decision="accepted",
        evidence_refs=["evidence/a.json", "evidence/b.json"],
        prerequisite_status=PrerequisiteStatus.SATISFIED,
        retirement_disposition="eligible",
        detail="All checks passed.",
    )
    d = original.to_dict()
    reconstructed = AcceptanceRow.from_dict(d)
    assert reconstructed.owner == original.owner
    assert reconstructed.input_version_vector == original.input_version_vector
    assert reconstructed.expected_decision == original.expected_decision
    assert reconstructed.evidence_refs == original.evidence_refs
    assert reconstructed.digest == original.digest
    assert reconstructed.prerequisite_status == original.prerequisite_status
    assert reconstructed.retirement_disposition == original.retirement_disposition
    assert reconstructed.detail == original.detail


def test_acceptance_row_from_dict_rejects_unknown_status():
    """Step 6: from_dict rejects unknown prerequisite_status."""
    with pytest.raises(ValueError, match="unknown prerequisite_status"):
        AcceptanceRow.from_dict(
            {"owner": "T6", "prerequisite_status": "bogus_status"}
        )


def test_acceptance_row_empty_retirement_disposition_allowed():
    """Step 6: empty retirement_disposition is allowed (not yet determined)."""
    row = AcceptanceRow(owner="T6")
    assert row.retirement_disposition == ""
    assert row.digest


def test_acceptance_row_empty_expected_decision_allowed():
    """Step 6: empty expected_decision is allowed (not yet determined)."""
    row = AcceptanceRow(owner="T6")
    assert row.expected_decision == ""
    assert row.digest


# ── Step 5 narrow: comprehensive no-debt gate ──────────────────────────────


def test_no_xfail_or_unresolved_debt_gate():
    """Step 5: the no-xfail/no-xpass/unexplained-skip/unresolved-debt gate
    blocks final acceptance and never allows prerequisite or semantic-carrier
    debt to satisfy it by default.

    This is the comprehensive narrow test required by T5.  It proves:

    * Every xfail/xpass marker is caught.
    * Every unexplained-skip marker is caught.
    * Unresolved debt (generic) is caught.
    * Prerequisite debt is rejected by default.
    * Semantic-carrier debt is rejected by default.
    * Explicit opt-in for one category leaves the other blocked.
    * The gate result carries the gate name, passed flag, and a complete
      findings list (fail-closed: default allow flags are False).
    """
    # ── Clean evidence passes ──────────────────────────────────────────
    clean = m11_debt_gate(evidence_text="All 42 tests passed.\nNo issues found.")
    assert clean["passed"] is True
    assert clean["findings"] == []
    assert clean["gate"] == "m11_no_debt"
    assert clean["allow_prerequisite_debt"] is False
    assert clean["allow_semantic_carrier_debt"] is False

    # ── No-xfail / no-xpass ─────────────────────────────────────────────
    xfail_result = m11_debt_gate(
        evidence_text="test_feature is marked as xfail (expected failure)."
    )
    assert xfail_result["passed"] is False
    assert any(f["kind"] == "xfail_xpass" for f in xfail_result["findings"])

    xpass_result = m11_debt_gate(
        evidence_text="xpass: test unexpectedly passed."
    )
    assert xpass_result["passed"] is False
    assert any(f["kind"] == "xfail_xpass" for f in xpass_result["findings"])

    # ── No-unexplained-skip ─────────────────────────────────────────────
    skip_result = m11_debt_gate(
        evidence_text="3 tests skipped without reason."
    )
    assert skip_result["passed"] is False
    assert any(f["kind"] == "unexplained_skip" for f in skip_result["findings"])

    # ── No-unresolved-debt ──────────────────────────────────────────────
    debt_result = m11_debt_gate(
        evidence_text="T42 has outstanding debt (unresolved debt)."
    )
    assert debt_result["passed"] is False
    assert any(
        f["kind"] == "unresolved_debt" and f.get("category") == "generic"
        for f in debt_result["findings"]
    )

    # ── Prerequisite debt blocked by default ────────────────────────────
    prereq_result = m11_debt_gate(
        evidence_text="unresolved prerequisite debt: T1 blocker."
    )
    assert prereq_result["passed"] is False
    assert any(
        f["kind"] == "unresolved_debt" and f.get("category") == "prerequisite"
        for f in prereq_result["findings"]
    )

    # ── Semantic-carrier debt blocked by default ────────────────────────
    sem_result = m11_debt_gate(
        evidence_text="semantic-carrier debt: M8 evidence stale."
    )
    assert sem_result["passed"] is False
    assert any(
        f["kind"] == "unresolved_debt" and f.get("category") == "semantic_carrier"
        for f in sem_result["findings"]
    )

    # ── Opt-in for prerequisite does not suppress semantic-carrier ──────
    mixed_result = m11_debt_gate(
        evidence_text=(
            "unresolved prerequisite debt: T1. "
            "semantic-carrier debt: M8 evidence stale."
        ),
        allow_prerequisite_debt=True,
    )
    # prerequisite debt filtered out, semantic-carrier still caught
    assert not any(
        f.get("category") == "prerequisite" for f in mixed_result["findings"]
    )
    assert any(
        f.get("category") == "semantic_carrier" for f in mixed_result["findings"]
    )
    assert mixed_result["passed"] is False

    # ── Opt-in for semantic-carrier does not suppress prerequisite ──────
    mixed2_result = m11_debt_gate(
        evidence_text=(
            "unresolved prerequisite debt: T1. "
            "semantic-carrier debt: M8 evidence stale."
        ),
        allow_semantic_carrier_debt=True,
    )
    assert not any(
        f.get("category") == "semantic_carrier" for f in mixed2_result["findings"]
    )
    assert any(
        f.get("category") == "prerequisite" for f in mixed2_result["findings"]
    )
    assert mixed2_result["passed"] is False

    # ── Both opted in → gate passes (no other markers) ──────────────────
    both_allowed = m11_debt_gate(
        evidence_text=(
            "unresolved prerequisite debt: T1. "
            "semantic-carrier debt: M8 evidence stale."
        ),
        allow_prerequisite_debt=True,
        allow_semantic_carrier_debt=True,
    )
    assert both_allowed["passed"] is True
    assert both_allowed["findings"] == []

    # ── Opt-in never suppresses xfail/xpass/unexplained-skip ────────────
    xfail_with_optin = m11_debt_gate(
        evidence_text="xfail: test_a. unresolved prerequisite debt: T1.",
        allow_prerequisite_debt=True,
    )
    assert xfail_with_optin["passed"] is False
    assert any(f["kind"] == "xfail_xpass" for f in xfail_with_optin["findings"])


# ── Step 6 narrow: acceptance case model fails closed ─────────────────────


def test_acceptance_case_model_fails_closed():
    """Step 6: the M11 acceptance case model (AcceptanceRow) is aggregation
    data that fails closed — it never writes authority, requires owner,
    validates expected_decision and retirement_disposition against known
    vocabularies, and carries prerequisite_status as a PrerequisiteStatus
    enum member (never a raw string).

    The row is intentionally NOT an authority writer: it has no grant/
    fence/lease fields and never reads WBC receipts, labels, liveness, or
    rebuildable projections.
    """
    # ── Every known decision constructs ─────────────────────────────────
    from arnold_pipelines.megaplan.orchestration.m11_acceptance import (
        _KNOWN_DECISIONS,
        _KNOWN_RETIREMENT_DISPOSITIONS,
    )

    for decision in _KNOWN_DECISIONS:
        row = AcceptanceRow(owner="T6", expected_decision=decision)
        assert row.expected_decision == decision
        assert row.digest

    for disposition in _KNOWN_RETIREMENT_DISPOSITIONS:
        row = AcceptanceRow(owner="T6", retirement_disposition=disposition)
        assert row.retirement_disposition == disposition
        assert row.digest

    # ── Unknown decisions are rejected ──────────────────────────────────
    with pytest.raises(ValueError, match="unknown expected_decision"):
        AcceptanceRow(owner="T6", expected_decision="authoritative")

    with pytest.raises(ValueError, match="unknown expected_decision"):
        AcceptanceRow(owner="T6", expected_decision="granted")

    # ── Unknown retirement dispositions are rejected ────────────────────
    with pytest.raises(ValueError, match="unknown retirement_disposition"):
        AcceptanceRow(owner="T6", retirement_disposition="deleted")

    # ── Owner is required ───────────────────────────────────────────────
    with pytest.raises(ValueError, match="owner is required"):
        AcceptanceRow(owner="")

    # ── prereq status must be a PrerequisiteStatus, not a raw string ────
    row = AcceptanceRow(
        owner="T6",
        prerequisite_status=PrerequisiteStatus.BLOCKED,
    )
    assert row.prerequisite_status is PrerequisiteStatus.BLOCKED

    # from_dict rejects raw unknown strings
    with pytest.raises(ValueError, match="unknown prerequisite_status"):
        AcceptanceRow.from_dict(
            {"owner": "T6", "prerequisite_status": "authorized"}
        )

    # ── Row is aggregation data, NOT an authority writer ────────────────
    # No grant, fence, lease, WBC, label, liveness, or projection fields.
    row_dict = AcceptanceRow(owner="T6", expected_decision="accepted").to_dict()
    forbidden_authority_keys = {
        "grant", "fence", "lease", "wbc_receipt", "label",
        "liveness", "projection", "authority", "capability",
    }
    assert forbidden_authority_keys.isdisjoint(row_dict.keys()), (
        f"AcceptanceRow carries forbidden authority keys: "
        f"{forbidden_authority_keys & row_dict.keys()}"
    )

    # ── Digest covers core fields ───────────────────────────────────────
    a = AcceptanceRow(
        owner="T6",
        input_version_vector={"m10": "sha256:abc"},
        expected_decision="accepted",
        evidence_refs=["ref1"],
        prerequisite_status=PrerequisiteStatus.SATISFIED,
        retirement_disposition="eligible",
    )
    # Changing any core field changes the digest
    b_input = AcceptanceRow(
        owner="T6",
        input_version_vector={"m10": "sha256:xyz"},  # different
        expected_decision="accepted",
        evidence_refs=["ref1"],
        prerequisite_status=PrerequisiteStatus.SATISFIED,
        retirement_disposition="eligible",
    )
    assert a.digest != b_input.digest

    b_decision = AcceptanceRow(
        owner="T6",
        input_version_vector={"m10": "sha256:abc"},
        expected_decision="rejected",  # different
        evidence_refs=["ref1"],
        prerequisite_status=PrerequisiteStatus.SATISFIED,
        retirement_disposition="eligible",
    )
    assert a.digest != b_decision.digest

    b_evidence = AcceptanceRow(
        owner="T6",
        input_version_vector={"m10": "sha256:abc"},
        expected_decision="accepted",
        evidence_refs=["ref2"],  # different
        prerequisite_status=PrerequisiteStatus.SATISFIED,
        retirement_disposition="eligible",
    )
    assert a.digest != b_evidence.digest

    b_prereq = AcceptanceRow(
        owner="T6",
        input_version_vector={"m10": "sha256:abc"},
        expected_decision="accepted",
        evidence_refs=["ref1"],
        prerequisite_status=PrerequisiteStatus.BLOCKED,  # different
        retirement_disposition="eligible",
    )
    assert a.digest != b_prereq.digest

    b_retire = AcceptanceRow(
        owner="T6",
        input_version_vector={"m10": "sha256:abc"},
        expected_decision="accepted",
        evidence_refs=["ref1"],
        prerequisite_status=PrerequisiteStatus.SATISFIED,
        retirement_disposition="not_eligible",  # different
    )
    assert a.digest != b_retire.digest

    # detail does NOT affect digest (opaque metadata)
    a_detail = AcceptanceRow(
        owner="T6",
        input_version_vector={"m10": "sha256:abc"},
        expected_decision="accepted",
        evidence_refs=["ref1"],
        prerequisite_status=PrerequisiteStatus.SATISFIED,
        retirement_disposition="eligible",
        detail="extra context",
    )
    assert a.digest == a_detail.digest


# ── Step 7: Predecessor adapter failures reported before aggregation ──────


def test_predecessor_adapter_failures_are_reported_before_aggregation():
    """Step 7: predecessor adapters for M10 C01-C20, F01-F17, M5, and A7
    evidence each check schema, digest, owner, version vector, source path,
    and effective status.  Failures are reported as typed BLOCKED rows before
    aggregation — stale prerequisite proof is never accepted.
    """
    from arnold_pipelines.megaplan.orchestration.m11_acceptance import (
        PredecessorAdapterResult,
        validate_a7_evidence,
        validate_f01_f17_evidence,
        validate_m10_c01_c20_evidence,
        validate_m5_evidence,
        validate_predecessor_adapters,
    )

    # ── M10 C01-C20: valid evidence passes ───────────────────────────────
    valid_m10 = {
        "schema": "m10.c01-c20-conformance.v1",
        "schema_version": 1,
        "generated_at": "2026-07-28T00:00:00Z",
        "status": "reconciled",
        "owner": "M10",
        "version_vector": {"m10_handoff": "sha256:abc"},
        "source_path": "evidence/m10-c01-c20-conformance.json",
        "effective_status": "reconciled",
    }
    result = validate_m10_c01_c20_evidence(valid_m10)
    assert result.passed is True
    assert result.acceptance_row is not None
    assert result.acceptance_row.prerequisite_status is PrerequisiteStatus.SATISFIED
    assert result.acceptance_row.expected_decision == "accepted"
    assert result.failures == []

    # ── M10 C01-C20: missing schema fails ─────────────────────────────────
    bad_m10 = {"schema_version": 1, "generated_at": "2026-07-28T00:00:00Z", "status": "reconciled"}
    result = validate_m10_c01_c20_evidence(bad_m10)
    assert result.passed is False
    assert result.acceptance_row.prerequisite_status is PrerequisiteStatus.BLOCKED
    assert any(f["kind"] == "schema_mismatch" for f in result.failures)

    # ── M10 C01-C20: stale/incoherent status fails ────────────────────────
    stale_m10 = dict(valid_m10, status="draft")
    result = validate_m10_c01_c20_evidence(stale_m10)
    assert result.passed is False
    assert any(f["kind"] == "ineffective_status" for f in result.failures)

    # ── M10 C01-C20: digest mismatch fails ────────────────────────────────
    result = validate_m10_c01_c20_evidence(valid_m10, expected_digest="sha256:wrong")
    assert result.passed is False
    assert any(f["kind"] == "digest_mismatch" for f in result.failures)

    # ── F01-F17: valid evidence passes ────────────────────────────────────
    valid_f01 = {
        "schema": "m10.f01-f17-fault-matrix.v1",
        "schema_version": 1,
        "generated_at": "2026-07-28T00:00:00Z",
        "status": "reconciled",
        "owner": "M10",
        "version_vector": {"fault_matrix": "sha256:f01"},
        "scenarios": [{"id": f"F{index:02d}"} for index in range(1, 18)],
    }
    result = validate_f01_f17_evidence(valid_f01)
    assert result.passed is True
    assert result.acceptance_row.prerequisite_status is PrerequisiteStatus.SATISFIED

    # ── F01-F17: missing scenarios fails ─────────────────────────────────
    no_scenarios = {
        "schema": "m10.f01-f17-fault-matrix.v1",
        "schema_version": 1,
        "status": "reconciled",
        "owner": "M10",
        "version_vector": {"fault_matrix": "sha256:f01"},
    }
    result = validate_f01_f17_evidence(no_scenarios)
    assert result.passed is False
    assert any(f["kind"] == "missing_scenarios" for f in result.failures)

    # ── M5: absent evidence fails closed ──────────────────────────────────
    result = validate_m5_evidence({})
    assert result.passed is False
    assert result.acceptance_row.prerequisite_status is PrerequisiteStatus.BLOCKED
    assert any(f["kind"] == "evidence_missing" for f in result.failures)

    # ── M5: valid evidence passes ─────────────────────────────────────────
    valid_m5 = {
        "schema": "m5.evidence.v1",
        "schema_version": 1,
        "generated_at": "2026-07-28T00:00:00Z",
        "status": "done",
        "version_vector": {"m5_artifact": "sha256:m5test"},
    }
    result = validate_m5_evidence(valid_m5)
    assert result.passed is True
    assert result.acceptance_row.prerequisite_status is PrerequisiteStatus.SATISFIED

    # ── A7: absent evidence fails closed ──────────────────────────────────
    result = validate_a7_evidence({})
    assert result.passed is False
    assert result.acceptance_row.prerequisite_status is PrerequisiteStatus.BLOCKED
    assert any(f["kind"] == "evidence_missing" for f in result.failures)

    # ── A7: valid evidence passes ─────────────────────────────────────────
    valid_a7 = {
        "schema": "a7.evidence.v1",
        "schema_version": 1,
        "generated_at": "2026-07-28T00:00:00Z",
        "status": "done",
        "version_vector": {"a7_artifact": "sha256:a7test"},
    }
    result = validate_a7_evidence(valid_a7)
    assert result.passed is True
    assert result.acceptance_row.prerequisite_status is PrerequisiteStatus.SATISFIED

    # ── Orchestrator: validate_predecessor_adapters returns 4 results ─────
    results = validate_predecessor_adapters(
        owner="T7",
        m10_c01_c20_data=valid_m10,
        f01_f17_data=valid_f01,
        m5_data=valid_m5,
        a7_data=valid_a7,
    )
    assert len(results) == 4
    assert all(isinstance(r, PredecessorAdapterResult) for r in results)
    # First two are SATISFIED, last two are SATISFIED (with valid data)
    for r in results:
        assert r.acceptance_row is not None

    # ── Missing M5/A7 are BLOCKED in orchestrator ─────────────────────────
    results = validate_predecessor_adapters(
        owner="T7",
        m10_c01_c20_data=valid_m10,
        f01_f17_data=valid_f01,
    )
    m5_result = next(r for r in results if r.family == "m5")
    assert m5_result.passed is False
    a7_result = next(r for r in results if r.family == "a7")
    assert a7_result.passed is False

    # ── Adapter results serialize round-trip ──────────────────────────────
    for r in results:
        d = r.to_dict()
        assert d["family"] == r.family
        assert d["passed"] == r.passed
        assert d["evidence_digest"] == r.evidence_digest
        assert d["source_path"] == r.source_path


# ── Step 8: Audit and recovery adapter gates ──────────────────────────────


def test_audit_and_recovery_adapter_gates():
    """Step 8: audit-cycle artifact trees with digest-checked provenance are
    gated.  Four complete trees are required.  The partial marker
    ``20260727T204730.361503Z`` is retained (never treated as complete).
    Recovery SLO status is checked from the ledger.
    """
    from arnold_pipelines.megaplan.orchestration.m11_acceptance import (
        AuditCycleTree,
        AuditRecoveryAdapterResult,
        validate_audit_recovery_adapters,
    )

    # ── Helper: compute correct provenance digest ────────────────────────
    import json
    import hashlib

    def _make_digest(cycle_id, paths, complete):
        payload = json.dumps(
            {"cycle_id": cycle_id, "artifact_paths": sorted(paths), "is_complete": complete},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    # ── Four complete trees pass ──────────────────────────────────────────
    tree_data = [
        (["evidence/a1.json", "evidence/a2.json"]),
        (["evidence/b1.json", "evidence/b2.json"]),
        (["evidence/c1.json", "evidence/c2.json"]),
        (["evidence/d1.json", "evidence/d2.json"]),
    ]
    four_complete = [
        {
            "cycle_id": f"cycle-{i+1:03d}",
            "artifact_paths": paths,
            "provenance_digest": _make_digest(f"cycle-{i+1:03d}", paths, True),
            "is_complete": True,
        }
        for i, paths in enumerate(tree_data)
    ]
    result = validate_audit_recovery_adapters(
        audit_trees_data=four_complete,
        recovery_ledger_data={"slo_met": True},
    )
    assert result.passed is True
    assert result.acceptance_row.prerequisite_status is PrerequisiteStatus.SATISFIED
    assert result.acceptance_row.expected_decision == "accepted"
    assert len(result.audit_trees) == 4
    assert result.partial_marker_retained is False
    # All trees are complete with validated digests
    for t in result.audit_trees:
        assert t.is_complete is True
        assert t.provenance_digest

    # ── Fewer than 4 complete trees fails ────────────────────────────────
    three_complete = four_complete[:3]
    result = validate_audit_recovery_adapters(
        audit_trees_data=three_complete,
        recovery_ledger_data={"slo_met": True},
    )
    assert result.passed is False
    assert result.acceptance_row.prerequisite_status is PrerequisiteStatus.BLOCKED
    assert any(f["kind"] == "insufficient_complete_trees" for f in result.failures)

    # ── Partial marker is retained, not counted as complete ──────────────
    with_partial = four_complete + [
        {
            "cycle_id": "20260727T204730.361503Z",
            "artifact_paths": ["evidence/m11-genuine-block-candidate/manifest.json"],
            "provenance_digest": "",
            "is_complete": False,
            "is_partial_marker": True,
        },
    ]
    result = validate_audit_recovery_adapters(
        audit_trees_data=with_partial,
        recovery_ledger_data={"slo_met": True},
    )
    # Four complete trees still pass, partial marker is retained
    assert result.passed is True
    assert result.partial_marker_retained is True
    # Verify partial marker tree
    partial_trees = [t for t in result.audit_trees if t.is_partial_marker]
    assert len(partial_trees) == 1
    assert partial_trees[0].cycle_id == "20260727T204730.361503Z"
    assert partial_trees[0].is_complete is False

    # ── Partial marker as only tree fails (not complete) ──────────────────
    partial_only = [
        {
            "cycle_id": "20260727T204730.361503Z",
            "artifact_paths": ["evidence/m11-genuine-block-candidate/manifest.json"],
            "provenance_digest": "",
            "is_complete": False,
            "is_partial_marker": True,
        },
    ]
    result = validate_audit_recovery_adapters(
        audit_trees_data=partial_only,
        recovery_ledger_data={"slo_met": True},
    )
    assert result.passed is False
    assert result.partial_marker_retained is True
    assert any(f["kind"] == "insufficient_complete_trees" for f in result.failures)

    # ── Recovery SLO not met fails ────────────────────────────────────────
    result = validate_audit_recovery_adapters(
        audit_trees_data=four_complete,
        recovery_ledger_data={"slo_met": False},
    )
    assert result.passed is False
    assert any(f["kind"] == "recovery_slo_not_met" for f in result.failures)

    # ── Incomplete (non-partial) tree is flagged ──────────────────────────
    with_incomplete = four_complete + [
        {
            "cycle_id": "cycle-005",
            "artifact_paths": ["evidence/e1.json"],
            "provenance_digest": "",
            "is_complete": False,
        },
    ]
    result = validate_audit_recovery_adapters(
        audit_trees_data=with_incomplete,
        recovery_ledger_data={"slo_met": True},
    )
    # Still passes (4 complete + 1 incomplete)
    assert result.passed is True
    # The incomplete tree has is_complete=False
    incomplete_tree = next((t for t in result.audit_trees if t.cycle_id == "cycle-005"), None)
    assert incomplete_tree is not None
    assert incomplete_tree.is_complete is False

    # ── Result serializes correctly ───────────────────────────────────────
    d = result.to_dict()
    assert d["passed"] == result.passed
    assert d["partial_marker_retained"] == result.partial_marker_retained
    assert "acceptance_row" in d
    assert isinstance(d["audit_trees"], list)


# ── Step 9: Aggregate report determinism and partial-state outcome ───────


def test_aggregate_report_is_deterministic():
    """Step 9: the M11 aggregate report generator is deterministic.

    The generator must produce identical reports — including identical
    content_hash — when given the same inputs.  This proves that the
    aggregate is reproducible, not dependent on transient state.
    """
    import json
    import tempfile
    from pathlib import Path

    from scripts.generate_m11_cross_contract_acceptance import main as generate

    # ── Build canonical inputs ──────────────────────────────────────────
    manifest = {
        "m10_handoff": "sha256:m10abc",
        "c_family": "sha256:cfamabc",
        "m5_family": "sha256:m5abc",
        "a7_family": "sha256:a7abc",
        "audit": "sha256:auditabc",
        "wbc": "sha256:wbcabc",
        "genuine_block": "sha256:genabc",
        "recovery": "sha256:recabc",
        "route": "sha256:routeabc",
        "no_debt": "sha256:nodebtabc",
        "runtime": "sha256:runtimeabc",
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        c01_path = tmp_path / "c01.json"
        c01_path.write_text(json.dumps({
            "schema": "m10.c01-c20-conformance.v1",
            "schema_version": 1,
            "generated_at": "2026-07-28T00:00:00Z",
            "status": "reconciled",
            "owner": "M10",
            "version_vector": {"m10_handoff": "sha256:abc"},
            "source_path": "evidence/m10-c01-c20-conformance.json",
            "effective_status": "reconciled",
        }), encoding="utf-8")

        f01_path = tmp_path / "f01.json"
        f01_path.write_text(json.dumps({
            "schema": "m10.f01-f17-fault-matrix.v1",
            "schema_version": 1,
            "generated_at": "2026-07-28T00:00:00Z",
            "status": "reconciled",
            "owner": "M10",
            "version_vector": {"fault_matrix": "sha256:f01"},
            "scenarios": [{"id": f"F{index:02d}"} for index in range(1, 18)],
        }), encoding="utf-8")

        m5_path = tmp_path / "m5.json"
        m5_path.write_text(json.dumps({
            "schema": "m5.evidence.v1",
            "schema_version": 1,
            "generated_at": "2026-07-28T00:00:00Z",
            "status": "done",
            "version_vector": {"m5_artifact": "sha256:m5test"},
        }), encoding="utf-8")

        a7_path = tmp_path / "a7.json"
        a7_path.write_text(json.dumps({
            "schema": "a7.evidence.v1",
            "schema_version": 1,
            "generated_at": "2026-07-28T00:00:00Z",
            "status": "done",
            "version_vector": {"a7_artifact": "sha256:a7test"},
        }), encoding="utf-8")

        audit_path = tmp_path / "audit.json"
        audit_path.write_text(json.dumps({
            "audit_cycle_trees": [
                {
                    "cycle_id": "cycle-001",
                    "artifact_paths": ["evidence/a1.json"],
                    "provenance_digest": _make_provenance_digest("cycle-001", ["evidence/a1.json"], True),
                    "is_complete": True,
                },
                {
                    "cycle_id": "cycle-002",
                    "artifact_paths": ["evidence/b1.json"],
                    "provenance_digest": _make_provenance_digest("cycle-002", ["evidence/b1.json"], True),
                    "is_complete": True,
                },
                {
                    "cycle_id": "cycle-003",
                    "artifact_paths": ["evidence/c1.json"],
                    "provenance_digest": _make_provenance_digest("cycle-003", ["evidence/c1.json"], True),
                    "is_complete": True,
                },
                {
                    "cycle_id": "cycle-004",
                    "artifact_paths": ["evidence/d1.json"],
                    "provenance_digest": _make_provenance_digest("cycle-004", ["evidence/d1.json"], True),
                    "is_complete": True,
                },
            ],
        }), encoding="utf-8")

        rec_path = tmp_path / "rec.json"
        rec_path.write_text(json.dumps({"slo_met": True}), encoding="utf-8")

        out1 = tmp_path / "out1.json"
        out2 = tmp_path / "out2.json"

        # ── First run ──────────────────────────────────────────────────
        rc1 = generate([
            "--owner", "T9",
            "--artifacts", str(manifest_path),
            "--c01-c20", str(c01_path),
            "--f01-f17", str(f01_path),
            "--m5", str(m5_path),
            "--a7", str(a7_path),
            "--audit-trees", str(audit_path),
            "--recovery-ledger", str(rec_path),
            "--out", str(out1),
        ])

        # ── Second run (same inputs) ────────────────────────────────────
        rc2 = generate([
            "--owner", "T9",
            "--artifacts", str(manifest_path),
            "--c01-c20", str(c01_path),
            "--f01-f17", str(f01_path),
            "--m5", str(m5_path),
            "--a7", str(a7_path),
            "--audit-trees", str(audit_path),
            "--recovery-ledger", str(rec_path),
            "--out", str(out2),
        ])

        report1 = json.loads(out1.read_text(encoding="utf-8"))
        report2 = json.loads(out2.read_text(encoding="utf-8"))

        # ── Exit codes match ────────────────────────────────────────────
        assert rc1 == rc2, f"Exit codes differ: {rc1} vs {rc2}"

        # ── Content hashes match ────────────────────────────────────────
        assert report1["content_hash"] == report2["content_hash"], (
            f"Content hashes differ: {report1['content_hash'][:24]}... "
            f"vs {report2['content_hash'][:24]}..."
        )

        # ── Typed outcomes match ────────────────────────────────────────
        assert report1["typed_outcome"] == report2["typed_outcome"]

        # ── generated_at and schema_descriptor may differ between runs ──
        # (timestamps naturally differ, descriptor can evolve)
        transient_keys = {"generated_at", "schema_descriptor"}
        for key in report1:
            if key in transient_keys:
                continue
            assert report1[key] == report2[key], (
                f"Field '{key}' differs between runs"
            )


def test_partial_predecessor_state_has_one_typed_outcome():
    """Step 9: partial predecessor state produces typed_outcome='m11_prerequisite_incomplete'.

    When any evidence family is missing, blocked, or expired — or when any
    predecessor adapter fails — the aggregate report must emit exactly one
    typed_outcome of 'm11_prerequisite_incomplete', never 'complete'.
    """
    import json
    import tempfile
    from pathlib import Path

    from scripts.generate_m11_cross_contract_acceptance import main as generate

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # ── Only one family satisfied, all others missing → partial ─────
        manifest = {"m10_handoff": "sha256:m10abc"}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        # Empty predecessor evidence → adapters will fail
        c01_path = tmp_path / "c01.json"
        c01_path.write_text("{}", encoding="utf-8")

        f01_path = tmp_path / "f01.json"
        f01_path.write_text("{}", encoding="utf-8")

        m5_path = tmp_path / "m5.json"
        m5_path.write_text("{}", encoding="utf-8")

        a7_path = tmp_path / "a7.json"
        a7_path.write_text("{}", encoding="utf-8")

        audit_path = tmp_path / "audit.json"
        audit_path.write_text(json.dumps({"audit_cycle_trees": []}), encoding="utf-8")

        rec_path = tmp_path / "rec.json"
        rec_path.write_text(json.dumps({"slo_met": False}), encoding="utf-8")

        out = tmp_path / "out.json"

        rc = generate([
            "--owner", "T9",
            "--artifacts", str(manifest_path),
            "--c01-c20", str(c01_path),
            "--f01-f17", str(f01_path),
            "--m5", str(m5_path),
            "--a7", str(a7_path),
            "--audit-trees", str(audit_path),
            "--recovery-ledger", str(rec_path),
            "--out", str(out),
        ])

        report = json.loads(out.read_text(encoding="utf-8"))

        # ── Must be 'm11_prerequisite_incomplete', not 'complete' ───────
        assert report["typed_outcome"] == "m11_prerequisite_incomplete", (
            f"Expected 'm11_prerequisite_incomplete' outcome, got {report['typed_outcome']!r}"
        )
        assert report["typed_outcome"] != "complete"

        # ── Exit code is non-zero for partial ───────────────────────────
        assert rc != 0, f"Expected non-zero exit for partial state, got {rc}"

        # ── Content hash is present ─────────────────────────────────────
        assert report["content_hash"], "Content hash must be present"

        # ── All required top-level keys are present ─────────────────────
        required_keys = {
            "schema", "content_hash", "generated_at", "typed_outcome",
            "runtime_vectors", "prerequisite_records",
            "predecessor_adapter_results", "audit_recovery_result",
            "debt_gate", "refs", "summary",
        }
        missing = required_keys - set(report.keys())
        assert not missing, f"Missing required keys: {missing}"

        # ── At least one blocker is present ─────────────────────────────
        assert len(report["summary"]["blockers"]) > 0, (
            "Partial state must report blockers"
        )


# ── Helper for test_aggregate_report_is_deterministic ──────────────────


def _make_provenance_digest(cycle_id: str, paths: list[str], complete: bool) -> str:
    """Compute a provenance digest matching _digest_check_audit_tree logic."""
    import hashlib
    import json

    payload = json.dumps(
        {"cycle_id": cycle_id, "artifact_paths": sorted(paths), "is_complete": complete},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


# ── Step 97 (T46): non-destructive legacy retirement eligibility ────────────


def test_retirement_eligibility_requires_all_gates() -> None:
    """Step 97 (T46): legacy retirement eligibility is non-destructive and
    requires EVERY M11 acceptance gate to pass.

    Eligibility never deletes, tombstones, or mutates any legacy artifact,
    evidence, or projection. Any single failing (or missing) gate produces a
    typed ``eligible=False`` outcome naming the blockers. No authority is
    created from a label, liveness, a WBC receipt, or a rebuildable projection.
    """
    all_pass = {gate: True for gate in LEGACY_RETIREMENT_REQUIRED_GATES}

    # ── 1. Every gate passing ⇒ eligible, non-destructive ────────────────────
    eligible = compute_legacy_retirement_eligibility(all_pass)
    assert isinstance(eligible, LegacyRetirementEligibility)
    assert eligible.eligible is True
    assert eligible.failing_gates == ()
    assert eligible.blockers == ()
    assert eligible.destructive is False  # eligibility never deletes anything
    assert eligible.schema == LEGACY_RETIREMENT_ELIGIBILITY_SCHEMA
    assert set(eligible.passing_gates) == set(LEGACY_RETIREMENT_REQUIRED_GATES)

    # ── 2. Each single gate failing ⇒ blocked with that gate named ───────────
    for failing_gate in LEGACY_RETIREMENT_REQUIRED_GATES:
        gate_status = dict(all_pass)
        gate_status[failing_gate] = False
        blocked = compute_legacy_retirement_eligibility(gate_status)
        assert blocked.eligible is False, f"retirement claimed with {failing_gate}=False"
        assert failing_gate in blocked.failing_gates
        assert any(failing_gate in b for b in blocked.blockers)
        # A single failing gate never authorizes destructive retirement.
        assert blocked.destructive is False

    # ── 3. Missing gate ⇒ fail closed (no silent default-to-True) ─────────────
    gate_status = dict(all_pass)
    del gate_status["prerequisites_ready"]
    blocked_missing = compute_legacy_retirement_eligibility(gate_status)
    assert blocked_missing.eligible is False
    assert "prerequisites_ready" in blocked_missing.failing_gates

    # ── 4. Empty gate map ⇒ blocked, every required gate listed ───────────────
    empty = compute_legacy_retirement_eligibility({})
    assert empty.eligible is False
    assert tuple(sorted(empty.failing_gates)) == tuple(sorted(LEGACY_RETIREMENT_REQUIRED_GATES))
    assert empty.destructive is False

    # ── 5. Unknown/extra gates never satisfy eligibility ─────────────────────
    gate_status = dict(all_pass)
    gate_status["fake_label_authority"] = True  # a label cannot mint authority
    bogus = compute_legacy_retirement_eligibility(gate_status)
    assert bogus.eligible is True  # all REAL gates still pass…
    assert "fake_label_authority" in bogus.unknown_gates  # …but the bogus gate
    # is reported as unknown and is NOT among required gates, so it cannot be
    # the basis for eligibility:
    assert "fake_label_authority" not in bogus.required_gates

    # ── 6. Eligibility is frozen pure decision data (no authority smuggling) ──
    payload = eligible.to_dict()
    forbidden = {
        "grant", "fence", "lease", "epoch", "wbc_receipt", "label",
        "liveness", "projection", "authority", "capability",
    }
    assert not (forbidden & set(payload)), forbidden & set(payload)
    assert payload["destructive"] is False
    with pytest.raises(Exception):
        eligible.eligible = False  # type: ignore[misc]
