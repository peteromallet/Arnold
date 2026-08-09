"""Focused contract tests for exact-version WBC query results."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from arnold.workflow.attempt_ledger_store import (
    GateStatus,
    SourceCursor,
    StartGateResult,
)
from arnold.workflow.execution_attempt_ledger import (
    LEDGER_SCHEMA_VERSION,
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    PersistenceStatus,
    RuntimeAdapter,
    VersionSet,
)
from arnold.workflow.wbc_queries import (
    WBC_QUERY_CONTRACT_VERSION,
    WbcEventRef,
    WbcIncompleteResult,
    WbcIncoherentResult,
    WbcIndeterminateResult,
    WbcQueryDiagnostic,
    WbcQueryStatus,
    WbcVerifiedResult,
)


ATTEMPT_ID = "11111111-1111-4111-8111-111111111111"


def _event(
    event_type: AttemptEventType,
    *,
    sequence: int,
    idempotency_key: str,
) -> LedgerEvent:
    outcome = None
    if event_type is AttemptEventType.COMPLETED:
        outcome = AttemptOutcome.SUCCEEDED
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=AttemptIdentity(
            workflow_id="workflow-1",
            run_id="run-1",
            graph_revision="revision-1",
            attempt_ordinal=1,
            attempt_id=ATTEMPT_ID,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(
            adapter_kind=AdapterKind.NATIVE,
            adapter_version="1",
        ),
        versions=VersionSet(code_version="code-1"),
        grant_ref=GrantRef(grant_id="grant-1"),
        sequence=sequence,
        causal_predecessor_sequence=max(0, sequence - 1),
        append_position=sequence - 1,
        occurred_at="2026-07-22T00:00:00Z",
        observed_at="2026-07-22T00:00:01Z",
        persistence_status=PersistenceStatus.DURABLE,
        outcome=outcome,
    )


def _cursor(*, sequence: int = 2) -> SourceCursor:
    return SourceCursor(
        attempt_id=ATTEMPT_ID,
        cursor_key="attempt_events",
        last_sequence=sequence,
        last_position=f"sqlite:{sequence}",
        updated_at_ns=1,
    )


def _verified() -> WbcVerifiedResult:
    return WbcVerifiedResult.from_events(
        started_event=_event(
            AttemptEventType.STARTED,
            sequence=1,
            idempotency_key="event-started",
        ),
        terminal_event=_event(
            AttemptEventType.COMPLETED,
            sequence=2,
            idempotency_key="event-completed",
        ),
        source_cursor=_cursor(),
        evidence_ids=("event-completed", "event-started"),
    )


def test_verified_result_binds_exact_version_events_cursor_and_digest() -> None:
    result = _verified()

    assert result.status is WbcQueryStatus.VERIFIED
    assert result.contract_version == WBC_QUERY_CONTRACT_VERSION
    assert result.stored_schema_version == LEDGER_SCHEMA_VERSION
    assert result.start_event_ref is not None
    assert result.start_event_ref.event_id == "event-started"
    assert result.terminal_event_ref is not None
    assert result.terminal_event_ref.event_id == "event-completed"
    assert result.source_cursor is not None
    assert result.source_cursor.last_sequence == 2
    assert result.evidence_ids == ("event-completed", "event-started")
    assert result.digest is not None and result.digest.startswith("sha256:")
    assert result.to_dict()["status"] == "verified"


def test_verified_result_is_deterministic_and_immutable() -> None:
    first = _verified()
    second = _verified()

    assert first == second
    assert first.digest == second.digest
    with pytest.raises(FrozenInstanceError):
        first.attempt_id = "changed"  # type: ignore[misc]


def test_four_result_states_are_typed_and_non_verified_states_explain_why() -> None:
    diagnostic = WbcQueryDiagnostic(
        code="terminal_missing",
        message="No terminal event is stored at the observed cursor.",
        evidence_ids=("event-started",),
    )

    incomplete = WbcIncompleteResult(
        attempt_id=ATTEMPT_ID,
        start_event_ref=WbcEventRef.from_event(
            _event(
                AttemptEventType.STARTED,
                sequence=1,
                idempotency_key="event-started",
            )
        ),
        stored_schema_version=LEDGER_SCHEMA_VERSION,
        diagnostics=(diagnostic,),
    )
    indeterminate = WbcIndeterminateResult(
        attempt_id=ATTEMPT_ID,
        diagnostics=(
            WbcQueryDiagnostic(code="store_unreadable", message="Read failed."),
        ),
    )
    incoherent = WbcIncoherentResult(
        attempt_id=ATTEMPT_ID,
        diagnostics=(
            WbcQueryDiagnostic(
                code="multiple_terminal_events",
                message="More than one terminal event was observed.",
            ),
        ),
    )

    assert incomplete.status is WbcQueryStatus.INCOMPLETE
    assert indeterminate.status is WbcQueryStatus.INDETERMINATE
    assert incoherent.status is WbcQueryStatus.INCOHERENT
    assert incomplete.digest is indeterminate.digest is incoherent.digest is None


@pytest.mark.parametrize(
    "raw_value",
    [
        "completed",  # prose/token
        "receipt.json",  # filename
        Path(".complete"),  # marker
        {"status": "completed"},  # mutable JSON / projection
        StartGateResult(
            attempt_id=ATTEMPT_ID,
            status=GateStatus.VERIFIED,
            started_event=None,
            evidence="raw receipt",
        ),
    ],
)
def test_raw_receipts_prose_files_markers_and_mutable_json_cannot_verify(
    raw_value: object,
) -> None:
    with pytest.raises(TypeError):
        WbcVerifiedResult(
            attempt_id=ATTEMPT_ID,
            start_event_ref=raw_value,  # type: ignore[arg-type]
        )


def test_mutable_evidence_id_collection_cannot_verify() -> None:
    with pytest.raises(TypeError, match="immutable tuple"):
        WbcVerifiedResult.from_events(
            started_event=_event(
                AttemptEventType.STARTED,
                sequence=1,
                idempotency_key="event-started",
            ),
            terminal_event=_event(
                AttemptEventType.COMPLETED,
                sequence=2,
                idempotency_key="event-completed",
            ),
            source_cursor=_cursor(),
            evidence_ids=["event-started", "event-completed"],  # type: ignore[arg-type]
        )


def test_implicit_latest_schema_cannot_verify() -> None:
    result = _verified()
    assert result.start_event_ref is not None
    assert result.terminal_event_ref is not None
    assert result.source_cursor is not None

    with pytest.raises(ValueError, match="exact supported stored schema"):
        replace(result, stored_schema_version="latest")


def test_cursor_or_digest_disagreement_cannot_verify() -> None:
    result = _verified()
    assert result.source_cursor is not None

    with pytest.raises(ValueError, match="exact terminal sequence"):
        replace(
            result,
            source_cursor=replace(result.source_cursor, last_sequence=1),
        )
    with pytest.raises(ValueError, match="digest does not match"):
        replace(result, digest="sha256:" + "0" * 64)


def test_non_verified_results_cannot_carry_verified_digest_or_hide_reason() -> None:
    with pytest.raises(ValueError, match="require diagnostics"):
        WbcIndeterminateResult(attempt_id=ATTEMPT_ID)
    with pytest.raises(ValueError, match="cannot carry a verified digest"):
        WbcIncoherentResult(
            attempt_id=ATTEMPT_ID,
            digest="sha256:" + "0" * 64,
            diagnostics=(
                WbcQueryDiagnostic(code="conflict", message="Evidence conflicts."),
            ),
        )


def test_result_contract_exposes_no_bearer_authority_api() -> None:
    forbidden = {
        "authorize",
        "complete",
        "dispatch",
        "grant",
        "publish",
        "repair",
        "retry",
    }

    assert forbidden.isdisjoint(dir(_verified()))
