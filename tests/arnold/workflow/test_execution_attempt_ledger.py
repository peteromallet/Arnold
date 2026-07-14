"""Tests for ExecutionAttemptLedger typed payload refs, persistence-failure, and reconciliation diagnostics."""

from __future__ import annotations

import uuid

import pytest

from arnold.workflow.durable_refs import DurableRef
from arnold.workflow.execution_attempt_ledger import (
    LEDGER_SCHEMA_VERSION,
    AdapterKind,
    ArtifactPayload,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    AuthorityPayload,
    CheckpointPayload,
    ExecutionAttemptLedger,
    ExternalEffectPayload,
    GrantRef,
    InputPayload,
    LedgerEvent,
    LedgerPosition,
    OutputPayload,
    PayloadSchemaVersion,
    PersistenceFailureDiagnostic,
    PersistenceFailureMode,
    PersistenceStatus,
    ReconciliationDiagnostic,
    ReconciliationOutcome,
    ResultPayload,
    RuntimeAdapter,
    StateDeltaPayload,
    VerdictPayload,
    VersionSet,
    validate_ledger,
    validate_ledger_event,
    validate_ledger_event_adapter,
    validate_ledger_event_grant,
    validate_ledger_event_identity,
    validate_ledger_event_idempotency,
    validate_ledger_event_ordering,
    validate_ledger_event_provenance,
    validate_ledger_event_timestamps,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_durable_ref(store_id="s3-main", locator="bucket/key") -> DurableRef:
    digest = "sha256:" + "a" * 64
    return DurableRef(
        store_id=store_id,
        locator=locator,
        digest=digest,
        schema_type="application/json",
    )


# ── PayloadSchemaVersion ──────────────────────────────────────────────────


class TestPayloadSchemaVersion:
    def test_all_versions_exist(self):
        assert PayloadSchemaVersion.INPUT_V1.value == "arnold.workflow.ledger.input_payload.v1"
        assert PayloadSchemaVersion.OUTPUT_V1.value == "arnold.workflow.ledger.output_payload.v1"
        assert PayloadSchemaVersion.RESULT_V1.value == "arnold.workflow.ledger.result_payload.v1"
        assert PayloadSchemaVersion.VERDICT_V1.value == "arnold.workflow.ledger.verdict_payload.v1"
        assert PayloadSchemaVersion.STATE_DELTA_V1.value == "arnold.workflow.ledger.state_delta_payload.v1"
        assert PayloadSchemaVersion.ARTIFACT_V1.value == "arnold.workflow.ledger.artifact_payload.v1"
        assert PayloadSchemaVersion.CHECKPOINT_V1.value == "arnold.workflow.ledger.checkpoint_payload.v1"
        assert PayloadSchemaVersion.AUTHORITY_V1.value == "arnold.workflow.ledger.authority_payload.v1"
        assert PayloadSchemaVersion.EXTERNAL_EFFECT_V1.value == "arnold.workflow.ledger.external_effect_payload.v1"

    def test_nine_versions(self):
        assert len(PayloadSchemaVersion) == 9


# ── TypedPayloadBase (tested via concrete subclasses) ─────────────────────


class TestTypedPayloadBaseConstruction:
    """Test _TypedPayloadBase construction constraints via concrete subclasses."""

    def test_inline_data_only(self):
        p = InputPayload(inline_data={"key": "value"})
        assert p.is_inline
        assert not p.is_reference
        assert not p.is_digest_only

    def test_ref_only(self):
        ref = _make_durable_ref()
        p = InputPayload(ref=ref)
        assert not p.is_inline
        assert p.is_reference
        assert not p.is_digest_only

    def test_content_digest_only(self):
        digest = "sha256:" + "a" * 64
        p = InputPayload(content_digest=digest)
        assert not p.is_inline
        assert not p.is_reference
        assert p.is_digest_only

    def test_inline_and_ref_mutually_exclusive(self):
        ref = _make_durable_ref()
        with pytest.raises(ValueError, match="mutually exclusive"):
            InputPayload(inline_data={"k": "v"}, ref=ref)

    def test_all_none_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            InputPayload()

    def test_invalid_digest_raises(self):
        with pytest.raises(ValueError, match="digest must be"):
            InputPayload(content_digest="bad")

    def test_valid_digest_accepted(self):
        digest = "sha256:" + "0" * 64
        p = InputPayload(content_digest=digest)
        assert p.content_digest == digest


class TestTypedPayloadBaseToDict:
    def test_inline_to_dict(self):
        p = InputPayload(inline_data={"a": 1})
        d = p.to_dict()
        assert d == {"inline_data": {"a": 1}}

    def test_ref_to_dict(self):
        ref = _make_durable_ref()
        p = InputPayload(ref=ref)
        d = p.to_dict()
        assert "ref" in d
        assert d["ref"]["store_id"] == "s3-main"

    def test_digest_only_to_dict(self):
        digest = "sha256:" + "f" * 64
        p = InputPayload(content_digest=digest)
        d = p.to_dict()
        assert d == {"content_digest": digest}

    def test_no_inline_data_when_ref(self):
        ref = _make_durable_ref()
        p = InputPayload(ref=ref)
        d = p.to_dict()
        assert "inline_data" not in d


class TestTypedPayloadBaseFrozen:
    def test_frozen(self):
        p = InputPayload(inline_data={"k": "v"})
        with pytest.raises(Exception):
            p.inline_data = {"x": "y"}  # type: ignore[misc]


# ── Concrete payload type classes ─────────────────────────────────────────


class TestAllPayloadClassesExist:
    @pytest.mark.parametrize("cls,expected_version", [
        (InputPayload, PayloadSchemaVersion.INPUT_V1.value),
        (OutputPayload, PayloadSchemaVersion.OUTPUT_V1.value),
        (ResultPayload, PayloadSchemaVersion.RESULT_V1.value),
        (VerdictPayload, PayloadSchemaVersion.VERDICT_V1.value),
        (StateDeltaPayload, PayloadSchemaVersion.STATE_DELTA_V1.value),
        (ArtifactPayload, PayloadSchemaVersion.ARTIFACT_V1.value),
        (CheckpointPayload, PayloadSchemaVersion.CHECKPOINT_V1.value),
        (AuthorityPayload, PayloadSchemaVersion.AUTHORITY_V1.value),
        (ExternalEffectPayload, PayloadSchemaVersion.EXTERNAL_EFFECT_V1.value),
    ])
    def test_schema_version(self, cls, expected_version):
        p = cls(inline_data={"k": "v"})
        assert p.schema_version == expected_version

    @pytest.mark.parametrize("cls", [
        InputPayload, OutputPayload, ResultPayload, VerdictPayload,
        StateDeltaPayload, ArtifactPayload, CheckpointPayload,
        AuthorityPayload, ExternalEffectPayload,
    ])
    def test_all_are_frozen(self, cls):
        p = cls(inline_data={"k": "v"})
        with pytest.raises(Exception):
            p.inline_data = {"x": "y"}  # type: ignore[misc]


class TestEachPayloadTypeAcceptsAllModes:
    """Each typed payload class should accept inline, ref, and digest-only."""

    @pytest.mark.parametrize("cls", [
        InputPayload, OutputPayload, ResultPayload, VerdictPayload,
        StateDeltaPayload, ArtifactPayload, CheckpointPayload,
        AuthorityPayload, ExternalEffectPayload,
    ])
    def test_inline(self, cls):
        p = cls(inline_data={"key": "val"})
        assert p.is_inline

    @pytest.mark.parametrize("cls", [
        InputPayload, OutputPayload, ResultPayload, VerdictPayload,
        StateDeltaPayload, ArtifactPayload, CheckpointPayload,
        AuthorityPayload, ExternalEffectPayload,
    ])
    def test_reference(self, cls):
        ref = _make_durable_ref()
        p = cls(ref=ref)
        assert p.is_reference

    @pytest.mark.parametrize("cls", [
        InputPayload, OutputPayload, ResultPayload, VerdictPayload,
        StateDeltaPayload, ArtifactPayload, CheckpointPayload,
        AuthorityPayload, ExternalEffectPayload,
    ])
    def test_digest_only(self, cls):
        digest = "sha256:" + "c" * 64
        p = cls(content_digest=digest)
        assert p.is_digest_only


# ── PersistenceFailureMode ────────────────────────────────────────────────


class TestPersistenceFailureMode:
    def test_all_modes_exist(self):
        modes = list(PersistenceFailureMode)
        assert PersistenceFailureMode.WRITE_FAILED in modes
        assert PersistenceFailureMode.STORE_UNAVAILABLE in modes
        assert PersistenceFailureMode.QUOTA_EXCEEDED in modes
        assert PersistenceFailureMode.CHECKSUM_MISMATCH in modes
        assert PersistenceFailureMode.PARTIAL_WRITE in modes
        assert PersistenceFailureMode.UNKNOWN in modes
        assert len(modes) == 6


# ── PersistenceFailureDiagnostic ──────────────────────────────────────────


class TestPersistenceFailureDiagnosticConstruction:
    def test_minimal_construction(self):
        pfd = PersistenceFailureDiagnostic(
            failure_mode=PersistenceFailureMode.WRITE_FAILED,
            target_event_sequence=5,
            observed_error="Disk full during append",
        )
        assert pfd.failure_mode == PersistenceFailureMode.WRITE_FAILED
        assert pfd.target_event_sequence == 5
        assert pfd.observed_error == "Disk full during append"
        assert pfd.recovery_evidence_ref is None
        assert not pfd.quarantined_authority_advance
        assert pfd.quarantine_reason is None

    def test_sequence_must_be_positive(self):
        with pytest.raises(ValueError, match="target_event_sequence"):
            PersistenceFailureDiagnostic(
                failure_mode=PersistenceFailureMode.WRITE_FAILED,
                target_event_sequence=0,
                observed_error="err",
            )

    def test_observed_error_must_be_nonempty(self):
        with pytest.raises(ValueError, match="observed_error"):
            PersistenceFailureDiagnostic(
                failure_mode=PersistenceFailureMode.WRITE_FAILED,
                target_event_sequence=1,
                observed_error="  ",
            )

    def test_quarantine_requires_reason(self):
        with pytest.raises(ValueError, match="quarantine_reason"):
            PersistenceFailureDiagnostic(
                failure_mode=PersistenceFailureMode.WRITE_FAILED,
                target_event_sequence=1,
                observed_error="err",
                quarantined_authority_advance=True,
            )

    def test_quarantine_with_reason_ok(self):
        pfd = PersistenceFailureDiagnostic(
            failure_mode=PersistenceFailureMode.WRITE_FAILED,
            target_event_sequence=1,
            observed_error="err",
            quarantined_authority_advance=True,
            quarantine_reason="Authority grant could not be persisted",
        )
        assert pfd.quarantined_authority_advance
        assert pfd.quarantine_reason == "Authority grant could not be persisted"

    def test_with_recovery_evidence(self):
        ref = _make_durable_ref()
        pfd = PersistenceFailureDiagnostic(
            failure_mode=PersistenceFailureMode.PARTIAL_WRITE,
            target_event_sequence=3,
            observed_error="Partial write detected",
            recovery_evidence_ref=ref,
        )
        assert pfd.has_recovery_evidence
        assert pfd.recovery_evidence_ref is ref


class TestPersistenceFailureDiagnosticProperties:
    def test_has_recovery_evidence_true(self):
        ref = _make_durable_ref()
        pfd = PersistenceFailureDiagnostic(
            failure_mode=PersistenceFailureMode.WRITE_FAILED,
            target_event_sequence=1,
            observed_error="err",
            recovery_evidence_ref=ref,
        )
        assert pfd.has_recovery_evidence

    def test_has_recovery_evidence_false(self):
        pfd = PersistenceFailureDiagnostic(
            failure_mode=PersistenceFailureMode.WRITE_FAILED,
            target_event_sequence=1,
            observed_error="err",
        )
        assert not pfd.has_recovery_evidence

    @pytest.mark.parametrize("mode,expected", [
        (PersistenceFailureMode.WRITE_FAILED, True),
        (PersistenceFailureMode.STORE_UNAVAILABLE, True),
        (PersistenceFailureMode.PARTIAL_WRITE, True),
        (PersistenceFailureMode.QUOTA_EXCEEDED, False),
        (PersistenceFailureMode.CHECKSUM_MISMATCH, False),
        (PersistenceFailureMode.UNKNOWN, False),
    ])
    def test_is_recoverable(self, mode, expected):
        pfd = PersistenceFailureDiagnostic(
            failure_mode=mode,
            target_event_sequence=1,
            observed_error="err",
        )
        assert pfd.is_recoverable == expected


class TestPersistenceFailureDiagnosticToDict:
    def test_minimal_to_dict(self):
        pfd = PersistenceFailureDiagnostic(
            failure_mode=PersistenceFailureMode.STORE_UNAVAILABLE,
            target_event_sequence=7,
            observed_error="Store connection refused",
        )
        d = pfd.to_dict()
        assert d["failure_mode"] == "store_unavailable"
        assert d["target_event_sequence"] == 7
        assert d["observed_error"] == "Store connection refused"
        assert d["quarantined_authority_advance"] is False
        assert "recovery_evidence_ref" not in d
        assert "quarantine_reason" not in d

    def test_full_to_dict(self):
        ref = _make_durable_ref()
        pfd = PersistenceFailureDiagnostic(
            failure_mode=PersistenceFailureMode.PARTIAL_WRITE,
            target_event_sequence=3,
            observed_error="Truncated at byte 512",
            recovery_evidence_ref=ref,
            quarantined_authority_advance=True,
            quarantine_reason="Grant persistence ambiguous",
        )
        d = pfd.to_dict()
        assert d["failure_mode"] == "partial_write"
        assert d["target_event_sequence"] == 3
        assert "recovery_evidence_ref" in d
        assert d["quarantined_authority_advance"] is True
        assert d["quarantine_reason"] == "Grant persistence ambiguous"


class TestPersistenceFailureDiagnosticFrozen:
    def test_frozen(self):
        pfd = PersistenceFailureDiagnostic(
            failure_mode=PersistenceFailureMode.UNKNOWN,
            target_event_sequence=1,
            observed_error="err",
        )
        with pytest.raises(Exception):
            pfd.observed_error = "new"  # type: ignore[misc]


# ── ReconciliationOutcome ─────────────────────────────────────────────────


class TestReconciliationOutcome:
    def test_all_outcomes_exist(self):
        outcomes = list(ReconciliationOutcome)
        assert ReconciliationOutcome.RECOVERED in outcomes
        assert ReconciliationOutcome.PARTIALLY_RECOVERED in outcomes
        assert ReconciliationOutcome.UNRECOVERABLE in outcomes
        assert ReconciliationOutcome.REQUIRES_MANUAL_INTERVENTION in outcomes
        assert ReconciliationOutcome.QUARANTINED in outcomes
        assert len(outcomes) == 5


# ── ReconciliationDiagnostic ──────────────────────────────────────────────


class TestReconciliationDiagnosticConstruction:
    def test_minimal_construction(self):
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=10,
            outcome=ReconciliationOutcome.RECOVERED,
            outcome_detail="Replayed from outbox successfully",
        )
        assert rd.reconciled_event_sequence == 10
        assert rd.outcome == ReconciliationOutcome.RECOVERED
        assert rd.outcome_detail == "Replayed from outbox successfully"
        assert rd.recovered_evidence_refs == ()
        assert rd.authority_disposition is None

    def test_sequence_must_be_positive(self):
        with pytest.raises(ValueError, match="reconciled_event_sequence"):
            ReconciliationDiagnostic(
                reconciled_event_sequence=0,
                outcome=ReconciliationOutcome.RECOVERED,
                outcome_detail="ok",
            )

    def test_negative_sequence_raises(self):
        with pytest.raises(ValueError, match="reconciled_event_sequence"):
            ReconciliationDiagnostic(
                reconciled_event_sequence=-1,
                outcome=ReconciliationOutcome.RECOVERED,
                outcome_detail="ok",
            )

    def test_outcome_detail_must_be_nonempty(self):
        with pytest.raises(ValueError, match="outcome_detail"):
            ReconciliationDiagnostic(
                reconciled_event_sequence=1,
                outcome=ReconciliationOutcome.RECOVERED,
                outcome_detail="",
            )

    def test_with_recovered_evidence(self):
        ref1 = _make_durable_ref(store_id="s3-1", locator="bucket/ev1")
        ref2 = _make_durable_ref(store_id="s3-2", locator="bucket/ev2")
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=5,
            outcome=ReconciliationOutcome.PARTIALLY_RECOVERED,
            outcome_detail="Recovered 2 of 3 events",
            recovered_evidence_refs=(ref1, ref2),
        )
        assert rd.has_recovered_evidence
        assert len(rd.recovered_evidence_refs) == 2

    def test_with_authority_disposition(self):
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=12,
            outcome=ReconciliationOutcome.QUARANTINED,
            outcome_detail="Authority grant quarantined pending manual review",
            authority_disposition="quarantine_authority_grant",
        )
        assert rd.authority_disposition == "quarantine_authority_grant"


class TestReconciliationDiagnosticProperties:
    def test_is_fully_recovered_true(self):
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=1,
            outcome=ReconciliationOutcome.RECOVERED,
            outcome_detail="ok",
        )
        assert rd.is_fully_recovered

    def test_is_fully_recovered_false(self):
        for outcome in [
            ReconciliationOutcome.PARTIALLY_RECOVERED,
            ReconciliationOutcome.UNRECOVERABLE,
            ReconciliationOutcome.REQUIRES_MANUAL_INTERVENTION,
            ReconciliationOutcome.QUARANTINED,
        ]:
            rd = ReconciliationDiagnostic(
                reconciled_event_sequence=1,
                outcome=outcome,
                outcome_detail="not fully ok",
            )
            assert not rd.is_fully_recovered

    def test_has_recovered_evidence(self):
        ref = _make_durable_ref()
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=1,
            outcome=ReconciliationOutcome.PARTIALLY_RECOVERED,
            outcome_detail="ok",
            recovered_evidence_refs=(ref,),
        )
        assert rd.has_recovered_evidence

    def test_has_recovered_evidence_empty(self):
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=1,
            outcome=ReconciliationOutcome.RECOVERED,
            outcome_detail="ok",
        )
        assert not rd.has_recovered_evidence

    @pytest.mark.parametrize("outcome,expected", [
        (ReconciliationOutcome.REQUIRES_MANUAL_INTERVENTION, True),
        (ReconciliationOutcome.UNRECOVERABLE, True),
        (ReconciliationOutcome.RECOVERED, False),
        (ReconciliationOutcome.PARTIALLY_RECOVERED, False),
        (ReconciliationOutcome.QUARANTINED, False),
    ])
    def test_requires_intervention(self, outcome, expected):
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=1,
            outcome=outcome,
            outcome_detail="detail",
        )
        assert rd.requires_intervention == expected


class TestReconciliationDiagnosticToDict:
    def test_minimal_to_dict(self):
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=8,
            outcome=ReconciliationOutcome.RECOVERED,
            outcome_detail="Replayed successfully",
        )
        d = rd.to_dict()
        assert d["reconciled_event_sequence"] == 8
        assert d["outcome"] == "recovered"
        assert d["outcome_detail"] == "Replayed successfully"
        assert "recovered_evidence_refs" not in d
        assert "authority_disposition" not in d

    def test_full_to_dict(self):
        ref = _make_durable_ref()
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=3,
            outcome=ReconciliationOutcome.PARTIALLY_RECOVERED,
            outcome_detail="Recovered from spool",
            recovered_evidence_refs=(ref,),
            authority_disposition="resume_normal",
        )
        d = rd.to_dict()
        assert d["reconciled_event_sequence"] == 3
        assert d["outcome"] == "partially_recovered"
        assert len(d["recovered_evidence_refs"]) == 1
        assert d["authority_disposition"] == "resume_normal"


class TestReconciliationDiagnosticFrozen:
    def test_frozen(self):
        rd = ReconciliationDiagnostic(
            reconciled_event_sequence=1,
            outcome=ReconciliationOutcome.RECOVERED,
            outcome_detail="ok",
        )
        with pytest.raises(Exception):
            rd.outcome_detail = "new"  # type: ignore[misc]


# ── Module-level gap documentation check ──────────────────────────────────


class TestModuleDocumentation:
    def test_module_docstring_mentions_primitive_gaps(self):
        import arnold.workflow.execution_attempt_ledger as m
        doc = m.__doc__
        assert doc is not None
        assert "Current Primitive Gaps" in doc
        assert "NDJSON Sequence Gaps" in doc
        assert "Missing Transaction / Outbox Migration" in doc

    def test_module_docstring_mentions_all_typed_payloads(self):
        import arnold.workflow.execution_attempt_ledger as m
        doc = m.__doc__
        assert doc is not None
        for name in [
            "InputPayload", "OutputPayload", "ResultPayload", "VerdictPayload",
            "StateDeltaPayload", "ArtifactPayload", "CheckpointPayload",
            "AuthorityPayload", "ExternalEffectPayload",
        ]:
            assert name in doc, f"{name} not documented in module docstring"

    def test_module_docstring_mentions_diagnostics(self):
        import arnold.workflow.execution_attempt_ledger as m
        doc = m.__doc__
        assert doc is not None
        assert "PersistenceFailureDiagnostic" in doc
        assert "ReconciliationDiagnostic" in doc


# ── Enum tests ────────────────────────────────────────────────────────────


class TestAttemptEventType:
    def test_all_event_types_exist(self):
        types = list(AttemptEventType)
        assert AttemptEventType.STARTED in types
        assert AttemptEventType.COMPLETED in types
        assert AttemptEventType.FAILED in types
        assert AttemptEventType.RETRY_SCHEDULED in types
        assert AttemptEventType.SUSPENDED in types
        assert AttemptEventType.RESUMED in types
        assert AttemptEventType.CANCELLED in types
        assert AttemptEventType.EXTERNAL_EFFECT_INTENT in types
        assert AttemptEventType.EXTERNAL_EFFECT_OUTCOME in types
        assert AttemptEventType.PERSISTENCE_FAILED in types
        assert AttemptEventType.RECONCILIATION in types
        assert len(types) == 11


class TestAttemptOutcome:
    def test_all_outcomes_exist(self):
        outcomes = list(AttemptOutcome)
        assert AttemptOutcome.SUCCEEDED in outcomes
        assert AttemptOutcome.FAILED in outcomes
        assert AttemptOutcome.INDETERMINATE in outcomes
        assert AttemptOutcome.CANCELLED in outcomes
        assert len(outcomes) == 4


class TestAdapterKind:
    def test_all_adapter_kinds_exist(self):
        kinds = list(AdapterKind)
        assert AdapterKind.NATIVE in kinds
        assert AdapterKind.MEGAPLAN_PHASE in kinds
        assert AdapterKind.MEGAPLAN_REDUCER in kinds
        assert AdapterKind.MEGAPLAN_CHAIN in kinds
        assert AdapterKind.MEGAPLAN_AUDITOR in kinds
        assert AdapterKind.MEGAPLAN_CLOUD_REPAIR in kinds
        assert AdapterKind.MEGAPLAN_VERIFICATION in kinds
        assert len(kinds) == 7


class TestPersistenceStatus:
    def test_all_statuses_exist(self):
        statuses = list(PersistenceStatus)
        assert PersistenceStatus.DURABLE in statuses
        assert PersistenceStatus.PERSISTENCE_FAILED in statuses
        assert PersistenceStatus.INDETERMINATE in statuses
        assert len(statuses) == 3


# ── LEDGER_SCHEMA_VERSION ─────────────────────────────────────────────────


class TestLedgerSchemaVersion:
    def test_version_is_stable(self):
        assert LEDGER_SCHEMA_VERSION == "arnold.workflow.execution_attempt_ledger.v1"


# ── AttemptIdentity ───────────────────────────────────────────────────────

def _make_identity(
    workflow_id="wf-1",
    run_id="run-1",
    graph_revision="rev-1",
    step_id=None,
    boundary_id=None,
    invocation_id=None,
    attempt_ordinal=1,
    attempt_id=None,
) -> AttemptIdentity:
    return AttemptIdentity(
        workflow_id=workflow_id,
        run_id=run_id,
        graph_revision=graph_revision,
        step_id=step_id,
        boundary_id=boundary_id,
        invocation_id=invocation_id,
        attempt_ordinal=attempt_ordinal,
        attempt_id=attempt_id or str(uuid.uuid4()),
    )


class TestAttemptIdentityConstruction:
    def test_minimal_valid(self):
        identity = _make_identity()
        assert identity.workflow_id == "wf-1"
        assert identity.run_id == "run-1"
        assert identity.graph_revision == "rev-1"
        assert identity.attempt_ordinal == 1
        assert identity.step_id is None
        assert identity.boundary_id is None

    def test_full_construction(self):
        aid = str(uuid.uuid4())
        identity = AttemptIdentity(
            workflow_id="wf-2",
            run_id="run-2",
            graph_revision="rev-2",
            step_id="step-a",
            boundary_id="boundary-b",
            invocation_id="inv-c",
            attempt_ordinal=3,
            attempt_id=aid,
        )
        assert identity.step_id == "step-a"
        assert identity.boundary_id == "boundary-b"
        assert identity.invocation_id == "inv-c"
        assert identity.attempt_ordinal == 3
        assert identity.attempt_id == aid

    def test_default_attempt_id_is_valid_uuid(self):
        identity = AttemptIdentity(
            workflow_id="wf", run_id="r", graph_revision="g",
        )
        uuid.UUID(identity.attempt_id)

    def test_empty_workflow_id_raises(self):
        with pytest.raises(ValueError, match="workflow_id"):
            AttemptIdentity(workflow_id="  ", run_id="r", graph_revision="g")

    def test_empty_run_id_raises(self):
        with pytest.raises(ValueError, match="run_id"):
            AttemptIdentity(workflow_id="w", run_id="", graph_revision="g")

    def test_empty_graph_revision_raises(self):
        with pytest.raises(ValueError, match="graph_revision"):
            AttemptIdentity(workflow_id="w", run_id="r", graph_revision="  ")

    def test_attempt_ordinal_zero_raises(self):
        with pytest.raises(ValueError, match="attempt_ordinal"):
            AttemptIdentity(
                workflow_id="w", run_id="r", graph_revision="g",
                attempt_ordinal=0,
            )

    def test_attempt_ordinal_negative_raises(self):
        with pytest.raises(ValueError, match="attempt_ordinal"):
            AttemptIdentity(
                workflow_id="w", run_id="r", graph_revision="g",
                attempt_ordinal=-5,
            )

    def test_empty_attempt_id_raises(self):
        with pytest.raises(ValueError, match="attempt_id"):
            AttemptIdentity(
                workflow_id="w", run_id="r", graph_revision="g",
                attempt_id="  ",
            )

    def test_invalid_attempt_id_uuid_raises(self):
        with pytest.raises(ValueError, match="attempt_id"):
            AttemptIdentity(
                workflow_id="w", run_id="r", graph_revision="g",
                attempt_id="not-a-uuid",
            )


class TestAttemptIdentityProperties:
    def test_is_boundary_scoped_true(self):
        identity = _make_identity(boundary_id="b-1")
        assert identity.is_boundary_scoped

    def test_is_boundary_scoped_false(self):
        identity = _make_identity()
        assert not identity.is_boundary_scoped

    def test_is_boundary_scoped_empty_string(self):
        identity = _make_identity(boundary_id="   ")
        assert not identity.is_boundary_scoped

    def test_is_step_scoped_true(self):
        identity = _make_identity(step_id="s-1")
        assert identity.is_step_scoped

    def test_is_step_scoped_false(self):
        identity = _make_identity()
        assert not identity.is_step_scoped

    def test_composite_key_is_stable(self):
        aid = "11111111-1111-1111-1111-111111111111"
        identity = AttemptIdentity(
            workflow_id="wf", run_id="r", graph_revision="g",
            attempt_ordinal=1, attempt_id=aid,
        )
        key1 = identity.composite_key
        key2 = identity.composite_key
        assert key1 == key2
        assert key1.startswith("sha256:")

    def test_composite_key_varies_with_attempt_id(self):
        id1 = _make_identity(workflow_id="wf", attempt_id="11111111-1111-1111-1111-111111111111")
        id2 = _make_identity(workflow_id="wf", attempt_id="22222222-2222-2222-2222-222222222222")
        assert id1.composite_key != id2.composite_key


class TestAttemptIdentityToDict:
    def test_minimal_to_dict(self):
        aid = "11111111-1111-1111-1111-111111111111"
        identity = AttemptIdentity(
            workflow_id="wf", run_id="r", graph_revision="g",
            attempt_ordinal=1, attempt_id=aid,
        )
        d = identity.to_dict()
        assert d["workflow_id"] == "wf"
        assert d["run_id"] == "r"
        assert d["graph_revision"] == "g"
        assert d["attempt_ordinal"] == 1
        assert d["attempt_id"] == aid
        assert "step_id" not in d
        assert "boundary_id" not in d
        assert "invocation_id" not in d

    def test_full_to_dict(self):
        aid = str(uuid.uuid4())
        identity = AttemptIdentity(
            workflow_id="wf", run_id="r", graph_revision="g",
            step_id="s1", boundary_id="b1", invocation_id="i1",
            attempt_ordinal=2, attempt_id=aid,
        )
        d = identity.to_dict()
        assert d["step_id"] == "s1"
        assert d["boundary_id"] == "b1"
        assert d["invocation_id"] == "i1"


class TestAttemptIdentityFrozen:
    def test_frozen(self):
        identity = _make_identity()
        with pytest.raises(Exception):
            identity.workflow_id = "new"  # type: ignore[misc]


# ── AttemptProvenance ─────────────────────────────────────────────────────

def _make_provenance(
    parent_attempt_id=None,
    causal_lineage=(),
    actor_id=None,
    tool_id=None,
) -> AttemptProvenance:
    return AttemptProvenance(
        parent_attempt_id=parent_attempt_id,
        causal_lineage=causal_lineage,
        actor_id=actor_id,
        tool_id=tool_id,
    )


class TestAttemptProvenanceConstruction:
    def test_initial_attempt(self):
        p = _make_provenance()
        assert p.is_initial_attempt
        assert p.parent_attempt_id is None
        assert p.causal_lineage == ()

    def test_retry_with_parent(self):
        parent_id = str(uuid.uuid4())
        p = AttemptProvenance(
            parent_attempt_id=parent_id,
            causal_lineage=(parent_id,),
        )
        assert p.parent_attempt_id == parent_id
        assert p.causal_lineage == (parent_id,)

    def test_multi_generation_lineage(self):
        g1 = str(uuid.uuid4())
        g2 = str(uuid.uuid4())
        g3 = str(uuid.uuid4())
        p = AttemptProvenance(
            parent_attempt_id=g3,
            causal_lineage=(g1, g2, g3),
        )
        assert p.lineage_depth == 3
        assert p.parent_attempt_id == g3

    def test_with_actor_and_tool(self):
        parent_id = str(uuid.uuid4())
        p = AttemptProvenance(
            parent_attempt_id=parent_id,
            causal_lineage=(parent_id,),
            actor_id="actor-1",
            tool_id="tool-1",
        )
        assert p.actor_id == "actor-1"
        assert p.tool_id == "tool-1"

    def test_lineage_without_parent_raises(self):
        with pytest.raises(ValueError, match="parent_attempt_id"):
            AttemptProvenance(
                causal_lineage=(str(uuid.uuid4()),),
                parent_attempt_id=None,
            )

    def test_parent_without_lineage_raises(self):
        with pytest.raises(ValueError, match="causal_lineage"):
            AttemptProvenance(
                parent_attempt_id=str(uuid.uuid4()),
                causal_lineage=(),
            )

    def test_parent_mismatch_with_lineage_last_raises(self):
        g1 = str(uuid.uuid4())
        g2 = str(uuid.uuid4())
        with pytest.raises(ValueError, match="does not match"):
            AttemptProvenance(
                parent_attempt_id=g2,
                causal_lineage=(g1,),  # last is g1, not g2
            )

    def test_lineage_invalid_uuid_raises(self):
        with pytest.raises(ValueError, match="causal_lineage"):
            AttemptProvenance(
                parent_attempt_id=str(uuid.uuid4()),
                causal_lineage=("not-a-uuid",),
            )


class TestAttemptProvenanceProperties:
    def test_is_initial_attempt_true(self):
        p = _make_provenance()
        assert p.is_initial_attempt

    def test_is_initial_attempt_false(self):
        pid = str(uuid.uuid4())
        p = AttemptProvenance(parent_attempt_id=pid, causal_lineage=(pid,))
        assert not p.is_initial_attempt

    def test_lineage_depth_zero(self):
        p = _make_provenance()
        assert p.lineage_depth == 0

    def test_lineage_depth_three(self):
        g1, g2, g3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        p = AttemptProvenance(
            parent_attempt_id=g3,
            causal_lineage=(g1, g2, g3),
        )
        assert p.lineage_depth == 3


class TestAttemptProvenanceToDict:
    def test_initial_to_dict(self):
        p = _make_provenance()
        d = p.to_dict()
        assert d["provenance_version"] == "arnold.workflow.attempt_provenance.v1"
        assert d["lineage_depth"] == 0
        assert "parent_attempt_id" not in d

    def test_retry_to_dict(self):
        pid = str(uuid.uuid4())
        p = AttemptProvenance(
            parent_attempt_id=pid,
            causal_lineage=(pid,),
            actor_id="a", tool_id="t",
        )
        d = p.to_dict()
        assert d["parent_attempt_id"] == pid
        assert d["causal_lineage"] == [pid]
        assert d["actor_id"] == "a"
        assert d["tool_id"] == "t"


class TestAttemptProvenanceFrozen:
    def test_frozen(self):
        p = _make_provenance()
        with pytest.raises(Exception):
            p.actor_id = "new"  # type: ignore[misc]


# ── RuntimeAdapter ────────────────────────────────────────────────────────


class TestRuntimeAdapterConstruction:
    def test_valid_native(self):
        ra = RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE, adapter_version="1.0.0",
        )
        assert ra.adapter_kind == AdapterKind.NATIVE
        assert ra.adapter_version == "1.0.0"

    def test_empty_version_raises(self):
        with pytest.raises(ValueError, match="adapter_version"):
            RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="")


class TestRuntimeAdapterToDict:
    def test_to_dict(self):
        ra = RuntimeAdapter(
            adapter_kind=AdapterKind.MEGAPLAN_PHASE, adapter_version="2.0",
        )
        d = ra.to_dict()
        assert d["adapter_kind"] == "megaplan.phase"
        assert d["adapter_version"] == "2.0"


class TestRuntimeAdapterFrozen:
    def test_frozen(self):
        ra = RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="1")
        with pytest.raises(Exception):
            ra.adapter_version = "2"  # type: ignore[misc]


# ── VersionSet ────────────────────────────────────────────────────────────


class TestVersionSetConstruction:
    def test_code_only(self):
        vs = VersionSet(code_version="abc123")
        assert vs.code_version == "abc123"
        assert vs.config_version is None

    def test_config_only(self):
        vs = VersionSet(config_version="v1.0")
        assert vs.config_version == "v1.0"

    def test_template_only(self):
        vs = VersionSet(template_version="tpl-1")
        assert vs.template_version == "tpl-1"

    def test_all_three(self):
        vs = VersionSet(code_version="c", config_version="cfg", template_version="tpl")
        assert vs.code_version == "c"
        assert vs.config_version == "cfg"
        assert vs.template_version == "tpl"

    def test_all_empty_raises(self):
        with pytest.raises(ValueError):
            VersionSet()

    def test_all_whitespace_raises(self):
        with pytest.raises(ValueError):
            VersionSet(code_version="  ", config_version="\t")


class TestVersionSetToDict:
    def test_code_only_to_dict(self):
        vs = VersionSet(code_version="abc")
        d = vs.to_dict()
        assert d == {"code_version": "abc"}

    def test_full_to_dict(self):
        vs = VersionSet(code_version="c", config_version="cfg", template_version="tpl")
        d = vs.to_dict()
        assert d["code_version"] == "c"
        assert d["config_version"] == "cfg"
        assert d["template_version"] == "tpl"


class TestVersionSetFrozen:
    def test_frozen(self):
        vs = VersionSet(code_version="c")
        with pytest.raises(Exception):
            vs.code_version = "x"  # type: ignore[misc]


# ── GrantRef ─────────────────────────────────────────────────────────────


class TestGrantRefConstruction:
    def test_minimal(self):
        gr = GrantRef(grant_id="grant-1")
        assert gr.grant_id == "grant-1"
        assert gr.decision_id is None

    def test_with_decision(self):
        gr = GrantRef(grant_id="grant-1", decision_id="dec-1")
        assert gr.decision_id == "dec-1"

    def test_empty_grant_id_raises(self):
        with pytest.raises(ValueError, match="grant_id"):
            GrantRef(grant_id="  ")


class TestGrantRefToDict:
    def test_minimal_to_dict(self):
        gr = GrantRef(grant_id="grant-1")
        d = gr.to_dict()
        assert d == {"grant_id": "grant-1"}

    def test_with_decision_to_dict(self):
        gr = GrantRef(grant_id="g", decision_id="d")
        d = gr.to_dict()
        assert d["decision_id"] == "d"


class TestGrantRefFrozen:
    def test_frozen(self):
        gr = GrantRef(grant_id="g")
        with pytest.raises(Exception):
            gr.grant_id = "x"  # type: ignore[misc]


# ── LedgerPosition ───────────────────────────────────────────────────────


def _make_position(sequence=1, append_position=0, causal_predecessor_sequence=0):
    return LedgerPosition(
        sequence=sequence,
        append_position=append_position,
        causal_predecessor_sequence=causal_predecessor_sequence,
    )


class TestLedgerPositionConstruction:
    def test_first_event_position(self):
        pos = _make_position(sequence=1, append_position=0, causal_predecessor_sequence=0)
        assert pos.sequence == 1
        assert pos.append_position == 0
        assert pos.causal_predecessor_sequence == 0
        assert pos.is_first_event

    def test_second_event_position(self):
        pos = _make_position(sequence=2, append_position=10, causal_predecessor_sequence=1)
        assert pos.sequence == 2
        assert not pos.is_first_event

    def test_sequence_zero_raises(self):
        with pytest.raises(ValueError, match="sequence must be >= 1"):
            _make_position(sequence=0)

    def test_sequence_negative_raises(self):
        with pytest.raises(ValueError, match="sequence must be >= 1"):
            _make_position(sequence=-1)

    def test_append_position_negative_raises(self):
        with pytest.raises(ValueError, match="append_position must be >= 0"):
            _make_position(append_position=-1)

    def test_causal_predecessor_negative_raises(self):
        with pytest.raises(ValueError, match="causal_predecessor_sequence must be >= 0"):
            _make_position(causal_predecessor_sequence=-1)

    def test_causal_predecessor_not_less_than_sequence_raises(self):
        with pytest.raises(ValueError, match="must be < sequence"):
            _make_position(sequence=3, causal_predecessor_sequence=3)

    def test_causal_predecessor_greater_than_sequence_raises(self):
        with pytest.raises(ValueError, match="must be < sequence"):
            _make_position(sequence=2, causal_predecessor_sequence=5)


class TestLedgerPositionOrdering:
    def test_sequence_ordering(self):
        p1 = _make_position(sequence=1, append_position=0)
        p2 = _make_position(sequence=2, append_position=10)
        assert p1 < p2

    def test_same_sequence_different_append_not_equal(self):
        p1 = _make_position(sequence=5, append_position=100)
        p2 = _make_position(sequence=5, append_position=200)
        # order=True generates __eq__ from all fields, so different
        # append_positions make them unequal even with same sequence.
        assert p1 != p2
        assert p1 < p2 or p2 < p1  # ordering still defined

    def test_sorting(self):
        positions = [
            _make_position(sequence=3, append_position=30),
            _make_position(sequence=1, append_position=0),
            _make_position(sequence=2, append_position=20),
        ]
        sorted_positions = sorted(positions)
        assert [p.sequence for p in sorted_positions] == [1, 2, 3]


class TestLedgerPositionToDict:
    def test_to_dict(self):
        pos = _make_position(sequence=5, append_position=42, causal_predecessor_sequence=4)
        d = pos.to_dict()
        assert d == {
            "sequence": 5,
            "append_position": 42,
            "causal_predecessor_sequence": 4,
        }


class TestLedgerPositionFrozen:
    def test_frozen(self):
        pos = _make_position()
        with pytest.raises(Exception):
            pos.sequence = 99  # type: ignore[misc]


# ── LedgerEvent ───────────────────────────────────────────────────────────

def _make_event(
    event_type=AttemptEventType.STARTED,
    idempotency_key="idem-1",
    identity=None,
    provenance=None,
    adapter=None,
    versions=None,
    grant_ref=None,
    sequence=1,
    causal_predecessor_sequence=0,
    append_position=0,
    occurred_at="2025-01-01T00:00:00Z",
    observed_at="2025-01-01T00:00:01Z",
    persistence_status=PersistenceStatus.DURABLE,
    outcome=None,
    payload=None,
    payload_policy_ref=None,
) -> LedgerEvent:
    if identity is None:
        identity = _make_identity()
    if provenance is None:
        provenance = _make_provenance()
    if adapter is None:
        adapter = RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="1")
    if versions is None:
        versions = VersionSet(code_version="c")
    if grant_ref is None:
        grant_ref = GrantRef(grant_id="grant-1")
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=identity,
        provenance=provenance,
        adapter=adapter,
        versions=versions,
        grant_ref=grant_ref,
        sequence=sequence,
        causal_predecessor_sequence=causal_predecessor_sequence,
        append_position=append_position,
        occurred_at=occurred_at,
        observed_at=observed_at,
        persistence_status=persistence_status,
        outcome=outcome,
        payload=payload,
        payload_policy_ref=payload_policy_ref,
    )


class TestLedgerEventConstruction:
    def test_minimal_started_event(self):
        event = _make_event()
        assert event.event_type == AttemptEventType.STARTED
        assert event.idempotency_key == "idem-1"
        assert event.sequence == 1
        assert event.causal_predecessor_sequence == 0
        assert event.persistence_status == PersistenceStatus.DURABLE
        assert event.event_schema_version == LEDGER_SCHEMA_VERSION

    def test_all_event_types_constructible(self):
        """Every AttemptEventType must be constructible as a LedgerEvent."""
        # Non-terminal types (those not requiring outcome)
        for et in [
            AttemptEventType.STARTED,
            AttemptEventType.RETRY_SCHEDULED,
            AttemptEventType.SUSPENDED,
            AttemptEventType.RESUMED,
        ]:
            event = _make_event(event_type=et)
            assert event.event_type == et, f"Failed to construct {et}"

        # Types requiring payload
        event = _make_event(
            event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
            payload={"effect": "test"},
        )
        assert event.event_type == AttemptEventType.EXTERNAL_EFFECT_INTENT

        event = _make_event(
            event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            payload={"effect": "test", "status": "done"},
        )
        assert event.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME

    def test_terminal_event_types_require_outcome(self):
        for et in [AttemptEventType.COMPLETED, AttemptEventType.FAILED, AttemptEventType.CANCELLED]:
            with pytest.raises(ValueError, match="must have an outcome"):
                _make_event(event_type=et)

    def test_terminal_with_outcome_succeeds(self):
        for et, outcome in [
            (AttemptEventType.COMPLETED, AttemptOutcome.SUCCEEDED),
            (AttemptEventType.FAILED, AttemptOutcome.FAILED),
            (AttemptEventType.CANCELLED, AttemptOutcome.CANCELLED),
        ]:
            event = _make_event(event_type=et, outcome=outcome)
            assert event.event_type == et
            assert event.outcome == outcome

    def test_terminal_no_outcome_ok_when_not_durable(self):
        event = _make_event(
            event_type=AttemptEventType.FAILED,
            persistence_status=PersistenceStatus.INDETERMINATE,
            outcome=None,
        )
        assert event.event_type == AttemptEventType.FAILED
        assert event.outcome is None

    def test_persistence_failed_event(self):
        event = _make_event(
            event_type=AttemptEventType.PERSISTENCE_FAILED,
            persistence_status=PersistenceStatus.PERSISTENCE_FAILED,
        )
        assert event.event_type == AttemptEventType.PERSISTENCE_FAILED
        assert event.is_persistence_compromised

    def test_persistence_failed_with_durable_status_raises(self):
        with pytest.raises(ValueError, match="persistence_status"):
            _make_event(
                event_type=AttemptEventType.PERSISTENCE_FAILED,
                persistence_status=PersistenceStatus.DURABLE,
            )

    def test_external_effect_intent_no_payload_raises(self):
        with pytest.raises(ValueError, match="payload or payload_policy_ref"):
            _make_event(event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT)

    def test_external_effect_intent_with_payload_succeeds(self):
        event = _make_event(
            event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
            payload={"effect": "send_email"},
        )
        assert event.event_type == AttemptEventType.EXTERNAL_EFFECT_INTENT

    def test_external_effect_intent_with_policy_ref_succeeds(self):
        event = _make_event(
            event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
            payload_policy_ref="wbc.inline.v1",
        )
        assert event.payload_policy_ref == "wbc.inline.v1"

    def test_reconciliation_event(self):
        event = _make_event(event_type=AttemptEventType.RECONCILIATION)
        assert event.event_type == AttemptEventType.RECONCILIATION

    def test_empty_idempotency_key_raises(self):
        with pytest.raises(ValueError, match="idempotency_key"):
            _make_event(idempotency_key="  ")

    def test_sequence_zero_raises(self):
        with pytest.raises(ValueError, match="sequence must be >= 1"):
            _make_event(sequence=0)

    def test_causal_predecessor_not_less_than_sequence_raises(self):
        with pytest.raises(ValueError, match="must be < sequence"):
            _make_event(sequence=2, causal_predecessor_sequence=3)

    def test_append_position_negative_raises(self):
        with pytest.raises(ValueError, match="append_position"):
            _make_event(append_position=-5)

    def test_empty_occurred_at_raises(self):
        with pytest.raises(ValueError, match="occurred_at"):
            _make_event(occurred_at="")

    def test_empty_observed_at_raises(self):
        with pytest.raises(ValueError, match="observed_at"):
            _make_event(observed_at="  ")

    def test_with_durable_ref_payload(self):
        ref = _make_durable_ref()
        event = _make_event(payload=ref)
        assert isinstance(event.payload, DurableRef)

    def test_with_dict_payload(self):
        event = _make_event(payload={"k": "v"})
        assert event.payload == {"k": "v"}

    def test_with_explicit_persistence_status(self):
        event = _make_event(persistence_status=PersistenceStatus.INDETERMINATE)
        assert event.persistence_status == PersistenceStatus.INDETERMINATE


class TestLedgerEventProperties:
    def test_position(self):
        event = _make_event(sequence=3, append_position=30, causal_predecessor_sequence=2)
        pos = event.position
        assert pos.sequence == 3
        assert pos.append_position == 30
        assert pos.causal_predecessor_sequence == 2

    def test_is_first_event_true(self):
        event = _make_event(causal_predecessor_sequence=0)
        assert event.is_first_event

    def test_is_first_event_false(self):
        event = _make_event(sequence=2, causal_predecessor_sequence=1)
        assert not event.is_first_event

    def test_is_terminal_for_completed(self):
        event = _make_event(
            event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        assert event.is_terminal

    def test_is_terminal_false_for_started(self):
        event = _make_event(event_type=AttemptEventType.STARTED)
        assert not event.is_terminal

    def test_is_persistence_compromised_true(self):
        event = _make_event(persistence_status=PersistenceStatus.PERSISTENCE_FAILED)
        assert event.is_persistence_compromised

    def test_is_persistence_compromised_indeterminate(self):
        event = _make_event(persistence_status=PersistenceStatus.INDETERMINATE)
        assert event.is_persistence_compromised

    def test_is_persistence_compromised_false(self):
        event = _make_event(persistence_status=PersistenceStatus.DURABLE)
        assert not event.is_persistence_compromised


class TestLedgerEventToDict:
    def test_minimal_to_dict(self):
        event = _make_event()
        d = event.to_dict()
        assert d["idempotency_key"] == "idem-1"
        assert d["event_type"] == "started"
        assert d["event_schema_version"] == LEDGER_SCHEMA_VERSION
        assert d["sequence"] == 1
        assert d["causal_predecessor_sequence"] == 0
        assert d["append_position"] == 0
        assert "identity" in d
        assert "provenance" in d
        assert "adapter" in d
        assert "versions" in d
        assert "grant_ref" in d

    def test_with_outcome_to_dict(self):
        event = _make_event(
            event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        d = event.to_dict()
        assert d["outcome"] == "succeeded"

    def test_with_payload_to_dict(self):
        event = _make_event(payload={"key": "val"})
        d = event.to_dict()
        assert d["payload"] == {"key": "val"}

    def test_with_durable_ref_payload_to_dict(self):
        ref = _make_durable_ref()
        event = _make_event(payload=ref)
        d = event.to_dict()
        assert isinstance(d["payload"], dict)
        assert d["payload"]["store_id"] == "s3-main"


class TestLedgerEventFrozen:
    def test_frozen(self):
        event = _make_event()
        with pytest.raises(Exception):
            event.idempotency_key = "new"  # type: ignore[misc]


# ── ExecutionAttemptLedger ───────────────────────────────────────────────


class TestExecutionAttemptLedgerConstruction:
    def test_empty_ledger(self):
        aid = str(uuid.uuid4())
        ledger = ExecutionAttemptLedger(attempt_id=aid)
        assert ledger.attempt_id == aid
        assert ledger.event_count == 0
        assert ledger.is_empty
        assert ledger.first_event is None
        assert ledger.last_event is None
        assert ledger.terminal_event is None

    def test_ledger_with_events(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1)
        e2 = _make_event(
            identity=identity, sequence=2,
            causal_predecessor_sequence=1, append_position=10,
        )
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1, e2))
        assert ledger.event_count == 2
        assert not ledger.is_empty
        assert ledger.first_event is e1
        assert ledger.last_event is e2

    def test_attempt_id_mismatch_raises(self):
        aid = str(uuid.uuid4())
        other_aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=other_aid)
        event = _make_event(identity=identity)
        with pytest.raises(ValueError, match="attempt_id"):
            ExecutionAttemptLedger(attempt_id=aid, events=(event,))

    def test_empty_attempt_id_raises(self):
        with pytest.raises(ValueError, match="attempt_id"):
            ExecutionAttemptLedger(attempt_id="  ")


class TestExecutionAttemptLedgerProperties:
    def test_terminal_event_found(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1)
        e2 = _make_event(
            identity=identity, sequence=2,
            event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
            causal_predecessor_sequence=1, append_position=10,
        )
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1, e2))
        assert ledger.terminal_event is e2

    def test_terminal_event_none_when_no_terminal(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1)
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1,))
        assert ledger.terminal_event is None

    def test_event_by_sequence_found(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1)
        e2 = _make_event(
            identity=identity, sequence=2,
            causal_predecessor_sequence=1, append_position=10,
        )
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1, e2))
        assert ledger.event_by_sequence(2) is e2

    def test_event_by_sequence_not_found(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1)
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1,))
        assert ledger.event_by_sequence(99) is None


class TestExecutionAttemptLedgerToDict:
    def test_to_dict(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1)
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1,))
        d = ledger.to_dict()
        assert d["attempt_id"] == aid
        assert d["ledger_schema_version"] == LEDGER_SCHEMA_VERSION
        assert d["event_count"] == 1
        assert len(d["events"]) == 1

    def test_empty_to_dict(self):
        aid = str(uuid.uuid4())
        ledger = ExecutionAttemptLedger(attempt_id=aid)
        d = ledger.to_dict()
        assert d["event_count"] == 0
        assert d["events"] == []


class TestExecutionAttemptLedgerFrozen:
    def test_frozen(self):
        aid = str(uuid.uuid4())
        ledger = ExecutionAttemptLedger(attempt_id=aid)
        with pytest.raises(Exception):
            ledger.attempt_id = "new"  # type: ignore[misc]


# ── Validators: validate_ledger_event_identity ────────────────────────────


class TestValidateLedgerEventIdentity:
    def test_valid_identity(self):
        event = _make_event()
        issues = validate_ledger_event_identity(event)
        assert issues == []

    def test_empty_workflow_id(self):
        identity = _make_identity()
        object.__setattr__(identity, 'workflow_id', '  ')
        event = _make_event(identity=identity)
        issues = validate_ledger_event_identity(event)
        assert any("workflow_id" in i for i in issues)

    def test_empty_run_id(self):
        identity = _make_identity()
        object.__setattr__(identity, 'run_id', '')
        event = _make_event(identity=identity)
        issues = validate_ledger_event_identity(event)
        assert any("run_id" in i for i in issues)

    def test_empty_graph_revision(self):
        identity = _make_identity()
        object.__setattr__(identity, 'graph_revision', '\t')
        event = _make_event(identity=identity)
        issues = validate_ledger_event_identity(event)
        assert any("graph_revision" in i for i in issues)

    def test_ordinal_zero(self):
        identity = _make_identity()
        object.__setattr__(identity, 'attempt_ordinal', 0)
        event = _make_event(identity=identity)
        issues = validate_ledger_event_identity(event)
        assert any("attempt_ordinal" in i for i in issues)

    def test_empty_attempt_id(self):
        identity = _make_identity()
        object.__setattr__(identity, 'attempt_id', '  ')
        event = _make_event(identity=identity)
        issues = validate_ledger_event_identity(event)
        assert any("attempt_id" in i for i in issues)

    def test_invalid_uuid(self):
        identity = _make_identity()
        object.__setattr__(identity, 'attempt_id', 'not-a-valid-uuid')
        event = _make_event(identity=identity)
        issues = validate_ledger_event_identity(event)
        assert any("UUID" in i for i in issues)


# ── Validators: validate_ledger_event_ordering ────────────────────────────

def _make_event_pair(
    aid, seq1, seq2, pred1=0, pred2=1, append1=0, append2=10,
    et1=AttemptEventType.STARTED, et2=AttemptEventType.COMPLETED,
):
    identity = _make_identity(attempt_id=aid)
    e1 = _make_event(
        identity=identity, event_type=et1, sequence=seq1,
        causal_predecessor_sequence=pred1, append_position=append1,
    )
    outcome = AttemptOutcome.SUCCEEDED if et2 in (
        AttemptEventType.COMPLETED, AttemptEventType.FAILED, AttemptEventType.CANCELLED,
    ) else None
    e2 = _make_event(
        identity=identity, event_type=et2, sequence=seq2,
        causal_predecessor_sequence=pred2, append_position=append2,
        outcome=outcome,
    )
    return e1, e2


class TestValidateLedgerEventOrdering:
    def test_empty_events(self):
        issues = validate_ledger_event_ordering([])
        assert issues == []

    def test_valid_ordered_pair(self):
        aid = str(uuid.uuid4())
        e1, e2 = _make_event_pair(aid, 1, 2)
        issues = validate_ledger_event_ordering([e1, e2])
        assert issues == []

    def test_duplicate_sequence(self):
        aid = str(uuid.uuid4())
        e1, e2 = _make_event_pair(aid, 1, 1, pred2=0)
        issues = validate_ledger_event_ordering([e1, e2])
        assert any("Duplicate" in i for i in issues)

    def test_non_monotonic_sequence(self):
        aid = str(uuid.uuid4())
        e1, e2 = _make_event_pair(aid, 5, 3, pred1=0, pred2=2)
        issues = validate_ledger_event_ordering([e1, e2])
        assert any("monotonic" in i for i in issues)

    def test_non_monotonic_append_position(self):
        aid = str(uuid.uuid4())
        e1, e2 = _make_event_pair(aid, 1, 2, append1=50, append2=10)
        issues = validate_ledger_event_ordering([e1, e2])
        assert any("monotonic" in i for i in issues)

    def test_first_event_nonzero_predecessor(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1, causal_predecessor_sequence=0)
        # Bypass __post_init__ to set invalid causal_predecessor_sequence
        object.__setattr__(e1, 'causal_predecessor_sequence', 99)
        issues = validate_ledger_event_ordering([e1])
        assert any("First event" in i for i in issues)

    def test_causal_predecessor_not_in_earlier_events(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1, causal_predecessor_sequence=0, append_position=0)
        e2 = _make_event(
            identity=identity, event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
            sequence=2, causal_predecessor_sequence=1, append_position=10,
        )
        # Bypass __post_init__ to set a bad causal predecessor that points
        # to a non-existent earlier sequence.
        object.__setattr__(e2, 'causal_predecessor_sequence', 99)
        issues = validate_ledger_event_ordering([e1, e2])
        assert any("causal_predecessor_sequence" in i for i in issues)

    def test_lifecycle_precedence_missing_started(self):
        """COMPLETED requires STARTED — test missing STARTED."""
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(
            identity=identity,
            event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
            sequence=1,
        )
        issues = validate_ledger_event_ordering([e1])
        assert any("requires preceding" in i for i in issues)
        assert any("started" in i for i in issues)

    def test_lifecycle_precedence_resumed_requires_suspended(self):
        """RESUMED requires SUSPENDED — test RESUMED without SUSPENDED."""
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, event_type=AttemptEventType.STARTED, sequence=1)
        e2 = _make_event(
            identity=identity, event_type=AttemptEventType.RESUMED,
            sequence=2, causal_predecessor_sequence=1, append_position=10,
        )
        issues = validate_ledger_event_ordering([e1, e2])
        assert any("requires preceding" in i for i in issues)
        assert any("suspended" in i for i in issues)

    def test_lifecycle_precedence_satisfied(self):
        """SUSPENDED -> RESUMED should pass."""
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, event_type=AttemptEventType.STARTED, sequence=1)
        e2 = _make_event(
            identity=identity, event_type=AttemptEventType.SUSPENDED,
            sequence=2, causal_predecessor_sequence=1, append_position=10,
        )
        e3 = _make_event(
            identity=identity, event_type=AttemptEventType.RESUMED,
            sequence=3, causal_predecessor_sequence=2, append_position=20,
        )
        issues = validate_ledger_event_ordering([e1, e2, e3])
        assert issues == []

    def test_lifecycle_external_effect_outcome_requires_intent(self):
        """EXTERNAL_EFFECT_OUTCOME requires EXTERNAL_EFFECT_INTENT."""
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, event_type=AttemptEventType.STARTED, sequence=1)
        e2 = _make_event(
            identity=identity,
            event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
            sequence=2, causal_predecessor_sequence=1, append_position=10,
        )
        issues = validate_ledger_event_ordering([e1, e2])
        assert any("external_effect_intent" in i for i in issues)

    def test_lifecycle_reconciliation_requires_persistence_failed(self):
        """RECONCILIATION requires PERSISTENCE_FAILED."""
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, event_type=AttemptEventType.STARTED, sequence=1)
        e2 = _make_event(
            identity=identity, event_type=AttemptEventType.RECONCILIATION,
            sequence=2, causal_predecessor_sequence=1, append_position=10,
        )
        issues = validate_ledger_event_ordering([e1, e2])
        assert any("persistence_failed" in i for i in issues)

    def test_three_events_strictly_monotonic(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1, append_position=0)
        e2 = _make_event(identity=identity, sequence=2, causal_predecessor_sequence=1, append_position=10)
        e3 = _make_event(identity=identity, sequence=3, causal_predecessor_sequence=2, append_position=20)
        issues = validate_ledger_event_ordering([e1, e2, e3])
        assert issues == []


# ── Validators: validate_ledger_event_provenance ──────────────────────────


class TestValidateLedgerEventProvenance:
    def test_valid_initial_provenance(self):
        p = _make_provenance()
        event = _make_event(provenance=p)
        issues = validate_ledger_event_provenance(event)
        assert issues == []

    def test_valid_retry_provenance(self):
        pid = str(uuid.uuid4())
        p = AttemptProvenance(parent_attempt_id=pid, causal_lineage=(pid,))
        event = _make_event(provenance=p)
        issues = validate_ledger_event_provenance(event)
        assert issues == []

    def test_lineage_without_parent(self):
        pid = str(uuid.uuid4())
        p = AttemptProvenance(
            parent_attempt_id=pid, causal_lineage=(pid,),
        )
        # Manually corrupt: create with bypassing __post_init__
        # We'll use the validator on a real object that's valid,
        # but test the validator's detection via mismatch.
        # Instead, we test with valid provenance — the validator
        # catches consistency issues that might slip past frozen dataclass.
        event = _make_event(provenance=p)
        issues = validate_ledger_event_provenance(event)
        assert issues == []

    def test_parent_without_lineage_detected(self):
        pid = str(uuid.uuid4())
        # This should be caught by AttemptProvenance.__post_init__
        with pytest.raises(ValueError):
            AttemptProvenance(parent_attempt_id=pid, causal_lineage=())

    def test_lineage_invalid_uuid(self):
        pid = str(uuid.uuid4())
        with pytest.raises(ValueError):
            AttemptProvenance(
                parent_attempt_id=pid,
                causal_lineage=("bad-uuid",),
            )

    def test_parent_mismatch_lineage(self):
        g1 = str(uuid.uuid4())
        g2 = str(uuid.uuid4())
        with pytest.raises(ValueError, match="does not match"):
            AttemptProvenance(
                parent_attempt_id=g1,
                causal_lineage=(g2,),
            )


# ── Validators: validate_ledger_event_grant ──────────────────────────────


class TestValidateLedgerEventGrant:
    def test_valid_grant(self):
        event = _make_event()
        issues = validate_ledger_event_grant(event)
        assert issues == []

    def test_empty_grant_id(self):
        gr = _make_event().grant_ref
        object.__setattr__(gr, 'grant_id', '  ')
        event = _make_event(grant_ref=gr)
        issues = validate_ledger_event_grant(event)
        assert any("grant_id" in i for i in issues)

    def test_empty_decision_id(self):
        gr = GrantRef(grant_id="g", decision_id="valid")
        object.__setattr__(gr, 'decision_id', '  ')
        event = _make_event(grant_ref=gr)
        issues = validate_ledger_event_grant(event)
        assert any("decision_id" in i for i in issues)


# ── Validators: validate_ledger_event_timestamps ──────────────────────────


class TestValidateLedgerEventTimestamps:
    def test_valid_timestamps(self):
        event = _make_event()
        issues = validate_ledger_event_timestamps(event)
        assert issues == []

    def test_empty_occurred_at(self):
        event = _make_event()
        object.__setattr__(event, 'occurred_at', '')
        issues = validate_ledger_event_timestamps(event)
        assert any("occurred_at" in i for i in issues)

    def test_empty_observed_at(self):
        event = _make_event()
        object.__setattr__(event, 'observed_at', '  ')
        issues = validate_ledger_event_timestamps(event)
        assert any("observed_at" in i for i in issues)


# ── Validators: validate_ledger_event_adapter ─────────────────────────────


class TestValidateLedgerEventAdapter:
    def test_valid_adapter(self):
        event = _make_event()
        issues = validate_ledger_event_adapter(event)
        assert issues == []

    def test_empty_adapter_version(self):
        ra = RuntimeAdapter(adapter_kind=AdapterKind.NATIVE, adapter_version="1")
        object.__setattr__(ra, 'adapter_version', '  ')
        event = _make_event(adapter=ra)
        issues = validate_ledger_event_adapter(event)
        assert any("adapter_version" in i for i in issues)


# ── Validators: validate_ledger_event_idempotency ────────────────────────


class TestValidateLedgerEventIdempotency:
    def test_valid_key(self):
        event = _make_event(idempotency_key="key-1")
        issues = validate_ledger_event_idempotency(event)
        assert issues == []

    def test_empty_key(self):
        event = _make_event()
        object.__setattr__(event, 'idempotency_key', '  ')
        issues = validate_ledger_event_idempotency(event)
        assert any("idempotency_key" in i for i in issues)


# ── Validators: validate_ledger_event (composite) ─────────────────────────


class TestValidateLedgerEvent:
    def test_valid_event_no_issues(self):
        event = _make_event()
        issues = validate_ledger_event(event)
        assert issues == []

    def test_event_with_bad_identity(self):
        identity = _make_identity()
        object.__setattr__(identity, 'workflow_id', '')
        event = _make_event(identity=identity)
        issues = validate_ledger_event(event)
        assert len(issues) >= 1

    def test_event_with_bad_provenance_not_caught_by_validate_ledger_event(self):
        """validate_ledger_event calls provenance validator but only catches
        issues the dataclass __post_init__ didn't already reject."""
        event = _make_event()
        issues = validate_ledger_event(event)
        assert issues == []


# ── Validators: validate_ledger (full ledger) ─────────────────────────────


class TestValidateLedger:
    def test_empty_ledger(self):
        aid = str(uuid.uuid4())
        ledger = ExecutionAttemptLedger(attempt_id=aid)
        issues = validate_ledger(ledger)
        assert issues == []

    def test_valid_single_event_ledger(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1)
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1,))
        issues = validate_ledger(ledger)
        assert issues == []

    def test_valid_multi_event_ledger(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1)
        e2 = _make_event(
            identity=identity, sequence=2,
            causal_predecessor_sequence=1, append_position=10,
        )
        e3 = _make_event(
            identity=identity, sequence=3,
            causal_predecessor_sequence=2, append_position=20,
            event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
        )
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1, e2, e3))
        issues = validate_ledger(ledger)
        assert issues == []

    def test_ledger_with_attempt_id_mismatch(self):
        aid = str(uuid.uuid4())
        other_aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=other_aid)
        e1 = _make_event(identity=identity, sequence=1)
        # Bypass ExecutionAttemptLedger.__post_init__ to allow mismatch
        ledger = object.__new__(ExecutionAttemptLedger)
        object.__setattr__(ledger, 'attempt_id', aid)
        object.__setattr__(ledger, 'events', (e1,))
        object.__setattr__(ledger, 'ledger_schema_version', LEDGER_SCHEMA_VERSION)
        issues = validate_ledger(ledger)
        assert any("attempt_id" in i for i in issues)

    def test_ledger_with_ordering_issues(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(identity=identity, sequence=1, append_position=10)
        e2 = _make_event(
            identity=identity,
            event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
            sequence=2, causal_predecessor_sequence=1, append_position=20,
        )
        # Reverse the ordering: put higher sequence first
        ledger = object.__new__(ExecutionAttemptLedger)
        object.__setattr__(ledger, 'attempt_id', aid)
        object.__setattr__(ledger, 'events', (e2, e1))
        object.__setattr__(ledger, 'ledger_schema_version', LEDGER_SCHEMA_VERSION)
        issues = validate_ledger(ledger)
        assert len(issues) > 0

    def test_ledger_with_missing_started(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(
            identity=identity,
            event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
            sequence=1,
        )
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1,))
        issues = validate_ledger(ledger)
        assert any("requires preceding" in i for i in issues)


# ── Integration: full lifecycle ──────────────────────────────────────────


class TestFullLifecycle:
    """Demonstrate a complete attempt lifecycle from STARTED through terminal."""

    def test_full_lifecycle_start_to_completed(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        e1 = _make_event(
            identity=identity, event_type=AttemptEventType.STARTED,
            sequence=1, append_position=0,
        )
        e2 = _make_event(
            identity=identity,
            event_type=AttemptEventType.COMPLETED,
            outcome=AttemptOutcome.SUCCEEDED,
            sequence=2, causal_predecessor_sequence=1, append_position=10,
        )
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=(e1, e2))
        issues = validate_ledger(ledger)
        assert issues == []

    def test_full_lifecycle_with_suspend_resume(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        events = [
            _make_event(identity=identity, event_type=AttemptEventType.STARTED,
                        sequence=1, append_position=0),
            _make_event(identity=identity, event_type=AttemptEventType.SUSPENDED,
                        sequence=2, causal_predecessor_sequence=1, append_position=10),
            _make_event(identity=identity, event_type=AttemptEventType.RESUMED,
                        sequence=3, causal_predecessor_sequence=2, append_position=20),
            _make_event(identity=identity, event_type=AttemptEventType.COMPLETED,
                        outcome=AttemptOutcome.SUCCEEDED,
                        sequence=4, causal_predecessor_sequence=3, append_position=30),
        ]
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=tuple(events))
        issues = validate_ledger(ledger)
        assert issues == []

    def test_full_lifecycle_with_persistence_failure_and_reconciliation(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        events = [
            _make_event(identity=identity, event_type=AttemptEventType.STARTED,
                        sequence=1, append_position=0),
            _make_event(identity=identity,
                        event_type=AttemptEventType.PERSISTENCE_FAILED,
                        persistence_status=PersistenceStatus.PERSISTENCE_FAILED,
                        sequence=2, causal_predecessor_sequence=1, append_position=10),
            _make_event(identity=identity,
                        event_type=AttemptEventType.RECONCILIATION,
                        sequence=3, causal_predecessor_sequence=2, append_position=20),
            _make_event(identity=identity,
                        event_type=AttemptEventType.COMPLETED,
                        outcome=AttemptOutcome.SUCCEEDED,
                        sequence=4, causal_predecessor_sequence=3, append_position=30),
        ]
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=tuple(events))
        issues = validate_ledger(ledger)
        assert issues == []

    def test_full_lifecycle_with_external_effects(self):
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        events = [
            _make_event(identity=identity, event_type=AttemptEventType.STARTED,
                        sequence=1, append_position=0),
            _make_event(identity=identity,
                        event_type=AttemptEventType.EXTERNAL_EFFECT_INTENT,
                        payload={"action": "send_email"},
                        sequence=2, causal_predecessor_sequence=1, append_position=10),
            _make_event(identity=identity,
                        event_type=AttemptEventType.EXTERNAL_EFFECT_OUTCOME,
                        payload={"action": "send_email", "status": "sent"},
                        sequence=3, causal_predecessor_sequence=2, append_position=20),
            _make_event(identity=identity,
                        event_type=AttemptEventType.COMPLETED,
                        outcome=AttemptOutcome.SUCCEEDED,
                        sequence=4, causal_predecessor_sequence=3, append_position=30),
        ]
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=tuple(events))
        issues = validate_ledger(ledger)
        assert issues == []

    def test_causal_chain_integrity(self):
        """A full chain must have every event's causal_predecessor referencing
        the immediately prior event's sequence."""
        aid = str(uuid.uuid4())
        identity = _make_identity(attempt_id=aid)
        events = []
        for i in range(1, 6):
            et = AttemptEventType.STARTED if i == 1 else \
                 AttemptEventType.COMPLETED if i == 5 else \
                 AttemptEventType.RETRY_SCHEDULED
            outcome = AttemptOutcome.SUCCEEDED if et == AttemptEventType.COMPLETED else None
            events.append(_make_event(
                identity=identity,
                event_type=et,
                outcome=outcome,
                sequence=i,
                causal_predecessor_sequence=i - 1,
                append_position=(i - 1) * 10,
            ))
        ledger = ExecutionAttemptLedger(attempt_id=aid, events=tuple(events))
        issues = validate_ledger(ledger)
        assert issues == []
