"""Local isolation tests for the read-only CL2 replay contract.

``ProjectionBuilder.replay()`` is contractually pure over the persisted
partition plus the pure semantic loop (``semantic_loop.replay_full`` imports
only ``hashlib`` / ``datetime`` / ``enum`` — no I/O, no model calls).  It must
not mutate any local state surface.

Seven local-state spies each wrap a real mutation entry point so a regression
(replay reaching that surface) is *recorded*, not merely assumed.  Four are
local durable-state surfaces; three are external-effect surfaces:

* plan           -> ``arnold_pipelines.megaplan.store.plan_repository.write_plan_state``
* gate           -> ``arnold_pipelines.megaplan.content_types.write_gate_signal_artifact``
* lifecycle      -> the side-effecting ``SqliteAttemptLedgerStore`` mutating methods
* queue          -> ``arnold.workflow._ledger_outbox_m9.FileBackedLedgerOutbox.enqueue``
* git/provider   -> ``arnold.agent.dispatch`` (the model/provider dispatch entry)
* delivery       -> ``arnold.workflow.ledger_outbox.LedgerOutbox.mark_dispatched``
* external-effect -> ``arnold.workflow.effect_protocol.EffectProtocol.dispatch_effect``

A store read-guard asserts replay calls only the read-only store API, and a
filesystem write-spy asserts replay writes no files.  Together these prove the
canonical partition: the sole side-effecting CL2 surface is
``LedgerPersistenceService`` (writes); replay is read-only.

Beyond isolation, this module positively asserts the CL2 authority model over
mixed-attempt projections: legacy ``cl2_kind=legacy_historical`` /
``derived_from_legacy`` context markers, legacy replay exclusion
(``legacy_derived``), per-contribution ``non_authoritative`` scope, the
``mixed_authoritative`` rollup for attempts carrying both authoritative (v1)
and non-authoritative (legacy) contributions, and exact missing-evidence
labelling (``unavailable_reason=legacy_import``) with NO
``required_for_briefing`` / ``reopen_condition`` markers.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import pytest

from arnold.critique_ledger.legacy_import import (
    LEGACY_UNAVAILABLE_REASON,
    OneTimeImporter,
)
from arnold.critique_ledger.persistence_service import (
    LedgerEventContext,
    LedgerPersistenceService,
)
from arnold.critique_ledger.projections import (
    ATTEMPT_AUTHORITY_MIXED,
    AUTHORITY_SCOPE_AUTHORITATIVE,
    AUTHORITY_SCOPE_NON_AUTHORITATIVE,
    CL2_KIND_LEGACY_HISTORICAL,
    EXCLUSION_REASON_LEGACY_DERIVED,
    ProjectionBuilder,
    ProjectionResult,
)
from arnold.critique_ledger.schemas import (
    Authority,
    DispositionFamily,
    EvidenceAvailability,
    ParseStatus,
    Relationship,
    CritiqueOccurrenceEnvelope,
    FindingDispositionEvent,
    FindingReconciliationEvent,
)
from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
from arnold.workflow.execution_attempt_ledger import (
    AdapterKind,
    AttemptEventType,
    AttemptIdentity,
    AttemptOutcome,
    AttemptProvenance,
    GrantRef,
    LedgerEvent,
    RuntimeAdapter,
    VersionSet,
)

WBC_CHAIN = {"wbc-001": {"valid": True}}

#: Store methods that mutate durable state.  Replay must call NONE of these.
_STORE_MUTATING_METHODS = frozenset(
    {
        "append_event",
        "append_started",
        "append_completed",
        "append_failed",
        "append_cancelled",
        "reserve_attempt",
        "reserve_global_effect",
        "initialize_attempt",
        "record_persistence_failure_diagnostic",
        "record_reconciliation_diagnostic",
        "update_source_cursor",
        "_append_tx",
    }
)


# ── local-state spy ──────────────────────────────────────────────────────────


class LocalStateSpy:
    """Records mutation attempts against one local state surface.

    Used both as a monkeypatch target (callable) and to expose
    :attr:`untouched`.  A recorded call is a *mutation* of that surface.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append((args, kwargs))

    @property
    def untouched(self) -> bool:
        return not self.calls

    def reset(self) -> None:
        self.calls.clear()


# ── fixtures / seed helpers ─────────────────────────────────────────────────


def _context(attempt_id: str) -> LedgerEventContext:
    return LedgerEventContext(
        identity=AttemptIdentity(
            workflow_id="wf-cl2",
            run_id="run-cl2",
            graph_revision="rev-cl2",
            attempt_id=attempt_id,
        ),
        provenance=AttemptProvenance(),
        adapter=RuntimeAdapter(AdapterKind.NATIVE, "cl2-iso-test"),
        versions=VersionSet(code_version="c116f38cc83"),
        grant_ref=GrantRef(grant_id="bridge-no-positive-authority"),
        occurred_at="2026-08-06T00:00:00+00:00",
        observed_at="2026-08-06T00:00:01+00:00",
    )


def _lifecycle_event(
    context: LedgerEventContext,
    event_type: AttemptEventType,
    sequence: int,
    idempotency_key: str,
) -> LedgerEvent:
    outcome = None
    if event_type == AttemptEventType.COMPLETED:
        outcome = AttemptOutcome.SUCCEEDED
    elif event_type == AttemptEventType.FAILED:
        outcome = AttemptOutcome.FAILED
    return LedgerEvent(
        idempotency_key=idempotency_key,
        event_type=event_type,
        identity=context.identity,
        provenance=context.provenance,
        adapter=context.adapter,
        versions=context.versions,
        grant_ref=context.grant_ref,
        sequence=sequence,
        causal_predecessor_sequence=sequence - 1,
        append_position=sequence - 1,
        occurred_at=context.occurred_at,
        observed_at=context.observed_at,
        outcome=outcome,
    )


def _valid_occurrence(attempt_id: str) -> CritiqueOccurrenceEnvelope:
    return CritiqueOccurrenceEnvelope(
        occurrence_id="occ-1",
        attempt_id=attempt_id,
        round_label="round-1",
        finding_id="F01",
        producer_id="critic-1",
        model_id="model-1",
        custody_receipt_refs=("wbc-001",),
        parse_status=ParseStatus.SELECTED.value,
        evidence_availability=EvidenceAvailability.RETAINED.value,
    )


def _valid_reconciliation() -> FindingReconciliationEvent:
    return FindingReconciliationEvent(
        reconciliation_id="rec-1",
        canonical_finding_id="F01",
        semantic_finding_id="sf-1",
        occurrence_ids=("occ-1",),
        relationship=Relationship.DUPLICATE.value,
        authority=Authority.EVALUATOR.value,
        reason="evaluator supplied",
    )


def _valid_disposition() -> FindingDispositionEvent:
    return FindingDispositionEvent(
        disposition_id="disp-1",
        semantic_finding_id="sf-1",
        family=DispositionFamily.ACCEPTED_RISK.value,
        authority=Authority.EVALUATOR.value,
    )


@pytest.fixture
def seeded(tmp_path: Path) -> tuple[
    SqliteAttemptLedgerStore,
    ProjectionBuilder,
    LedgerPersistenceService,
    str,
    LedgerEventContext,
]:
    store = SqliteAttemptLedgerStore(tmp_path / "cl2-iso.sqlite")
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)
    service = LedgerPersistenceService(store)
    store.append_started(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    service.persist_occurrence(
        attempt_id, _valid_occurrence(attempt_id), idempotency_key="occ", context=context
    )
    service.persist_reconciliation(
        attempt_id, _valid_reconciliation(), idempotency_key="rec", context=context
    )
    service.persist_disposition(
        attempt_id, _valid_disposition(), idempotency_key="disp", context=context
    )
    return store, ProjectionBuilder(store), service, attempt_id, context


# ── 1. lifecycle spy: store read-guard ──────────────────────────────────────


def test_replay_calls_no_mutating_store_method(seeded: Any) -> None:
    """Replay touches only the read-only store API (lifecycle surface)."""
    store, builder, _, attempt_id, _ = seeded
    lifecycle_spy = LocalStateSpy("lifecycle")
    originals: dict[str, Any] = {}
    for name in _STORE_MUTATING_METHODS:
        if hasattr(store, name):
            originals[name] = getattr(store, name)
            setattr(store, name, lifecycle_spy)

    try:
        # The spy raises on call, so any mutation fails the test immediately.
        result = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)
    finally:
        for name, original in originals.items():
            setattr(store, name, original)

    assert isinstance(result, ProjectionResult)
    assert lifecycle_spy.untouched, (
        f"replay mutated the lifecycle store via: "
        f"{[c[0] for c in lifecycle_spy.calls]}"
    )


def test_replay_calls_only_read_events(seeded: Any) -> None:
    """The only store method replay invokes is read_events."""
    store, builder, _, attempt_id, _ = seeded
    called: list[str] = []

    class _Recording:
        """Wrap read_events so we can observe which methods replay reaches."""

        def __init__(self, target: Any) -> None:
            object.__setattr__(self, "_t", target)

        def __getattr__(self, name: str) -> Any:
            attr = getattr(self._t, name)

            def _record(*args: Any, **kwargs: Any) -> Any:
                called.append(name)
                return attr(*args, **kwargs)

            return _record

    # Swap the builder's store reference for a recording proxy.
    original_store = builder._store  # type: ignore[attr-defined]
    builder._store = _Recording(original_store)  # type: ignore[attr-defined]
    try:
        builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)
    finally:
        builder._store = original_store  # type: ignore[attr-defined]

    assert called == ["read_events"], (
        f"replay reached unexpected store methods: {called}"
    )


# ── 2. plan / gate / queue spies + filesystem write-spy ────────────────────


def _install_category_spies(monkeypatch: pytest.MonkeyPatch) -> dict[str, LocalStateSpy]:
    """Install all seven local-state spies on their canonical mutation entry points.

    Four durable-state surfaces (plan/gate/lifecycle/queue) plus three
    external-effect surfaces (git/provider, delivery, external-effect).  Replay
    must reach NONE of them; a recorded call is a mutation of that surface.
    """
    plan_spy = LocalStateSpy("plan")
    gate_spy = LocalStateSpy("gate")
    queue_spy = LocalStateSpy("queue")
    git_provider_spy = LocalStateSpy("git/provider")
    delivery_spy = LocalStateSpy("delivery")
    external_effect_spy = LocalStateSpy("external-effect")

    # plan
    import arnold_pipelines.megaplan.store.plan_repository as plan_repo

    monkeypatch.setattr(plan_repo, "write_plan_state", plan_spy)
    if hasattr(plan_repo, "write_plan_artifact_json"):
        monkeypatch.setattr(plan_repo, "write_plan_artifact_json", plan_spy)

    # gate
    import arnold_pipelines.megaplan.content_types as content_types

    monkeypatch.setattr(content_types, "write_gate_signal_artifact", gate_spy)

    # queue
    import arnold.workflow._ledger_outbox_m9 as outbox_mod

    monkeypatch.setattr(outbox_mod.FileBackedLedgerOutbox, "enqueue", queue_spy)

    # git/provider — the model/provider dispatch entry (spawns providers/git).
    import arnold.agent as agent_mod

    monkeypatch.setattr(agent_mod, "dispatch", git_provider_spy)

    # delivery — the transactional-outbox delivery mutation entry.
    import arnold.workflow.ledger_outbox as outbox_base

    monkeypatch.setattr(
        outbox_base.LedgerOutbox, "mark_dispatched", delivery_spy
    )

    # external-effect — the WBC external-effect dispatch entry.
    import arnold.workflow.effect_protocol as effect_mod

    monkeypatch.setattr(
        effect_mod.EffectProtocol, "dispatch_effect", external_effect_spy
    )

    return {
        "plan": plan_spy,
        "gate": gate_spy,
        "queue": queue_spy,
        "git/provider": git_provider_spy,
        "delivery": delivery_spy,
        "external-effect": external_effect_spy,
    }


def test_replay_leaves_all_local_state_spies_untouched(
    seeded: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replay does not call any plan/gate/queue/external-effect entry point."""
    _, builder, _, attempt_id, _ = seeded
    spies = _install_category_spies(monkeypatch)

    builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)
    builder.build_cumulative([attempt_id])
    builder.verify_byte_equivalence(
        attempt_id,
        builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN).manifest_hash,
        builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN).briefing_hash,
        wbc_receipt_chain=WBC_CHAIN,
    )

    for name, spy in spies.items():
        assert spy.untouched, (
            f"replay mutated the {name} surface via: "
            f"{[c[0] for c in spy.calls]}"
        )


def test_replay_writes_no_files(seeded: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replay writes no files (plan/gate/lifecycle/queue on-disk surfaces)."""
    _, builder, _, attempt_id, _ = seeded
    write_spy = LocalStateSpy("filesystem-write")

    # Patch the broad filesystem write primitives in the two modules replay
    # actually touches.  Any write attempt is recorded as a mutation.
    import arnold.critique_ledger.projections as proj_mod
    import arnold.critique_ledger.semantic_loop as loop_mod

    for mod in (proj_mod, loop_mod):
        if hasattr(Path, "write_text"):
            monkeypatch.setattr(Path, "write_text", write_spy, raising=False)
        if hasattr(Path, "write_bytes"):
            monkeypatch.setattr(Path, "write_bytes", write_spy, raising=False)
        if hasattr(Path, "unlink"):
            monkeypatch.setattr(Path, "unlink", write_spy, raising=False)
    monkeypatch.setattr(os, "replace", write_spy, raising=False)
    monkeypatch.setattr(os, "rename", write_spy, raising=False)

    result = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)

    assert isinstance(result, ProjectionResult)
    assert write_spy.untouched, (
        f"replay wrote/mutated files via: {[c[0] for c in write_spy.calls]}"
    )


def test_replay_is_deterministic_and_repeatable(seeded: Any) -> None:
    """Repeated replays yield identical hashes (no hidden accumulating state)."""
    _, builder, _, attempt_id, _ = seeded
    first = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)
    for _ in range(3):
        again = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)
        assert again.manifest_hash == first.manifest_hash
        assert again.briefing_hash == first.briefing_hash


# ── 3. mixed-attempt fixture (v1 authoritative + legacy non-authoritative) ──


def _legacy_ndjson(tmp_path: Path) -> Path:
    """Two-record inline legacy r5 NDJSON: one retained, one missing-evidence.

    Mirrors the r5 record shape (no ``evidence_available`` flag); the second
    record carries no evidence keys so the real importer labels it
    ``UNAVAILABLE`` / ``legacy_import``.
    """
    retained = {
        "schema_version": "cl.m6-corpus.v1",
        "finding_id": "FINDING-LEGACY-RETAINED",
        "producer_id": "critic-legacy",
        "model_id": "model-legacy",
        "round_label": "round-legacy",
        "semantic_finding_id": "sf-legacy-retained",
        "evidence_ref": "durable://evidence/legacy/retained",
    }
    missing = {
        "schema_version": "megaplan-critique-custody-v1",
        "finding_id": "FINDING-LEGACY-MISSING",
        "producer_id": "critic-legacy",
        "model_id": "model-legacy",
        "round_label": "round-legacy",
        "semantic_finding_id": "sf-legacy-missing",
    }
    path = tmp_path / "legacy-inline.ndjson"
    path.write_text(
        json.dumps(retained) + "\n" + json.dumps(missing) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def mixed_seeded(tmp_path: Path) -> tuple[
    SqliteAttemptLedgerStore,
    ProjectionBuilder,
    LedgerPersistenceService,
    str,
    LedgerEventContext,
]:
    """One attempt_id carrying BOTH v1 (authoritative) and legacy
    (non-authoritative) contributions.

    A complete v1 replay partition (occurrence + reconciliation + disposition)
    is persisted first, then two legacy r5 records are imported through the real
    :class:`OneTimeImporter` under the SAME ``attempt_id`` — one with retained
    evidence, one missing-evidence.  This is the mixed-authority edge case.
    """
    store = SqliteAttemptLedgerStore(tmp_path / "cl2-mixed.sqlite")
    attempt_id = str(uuid.uuid4())
    context = _context(attempt_id)
    service = LedgerPersistenceService(store)
    store.append_started(
        attempt_id,
        _lifecycle_event(context, AttemptEventType.STARTED, 1, "started"),
    )
    service.record_intent(
        attempt_id, {"briefing_ref": "ref"}, idempotency_key="intent", context=context
    )
    # Authoritative v1 partition.
    service.persist_occurrence(
        attempt_id, _valid_occurrence(attempt_id), idempotency_key="occ", context=context
    )
    service.persist_reconciliation(
        attempt_id, _valid_reconciliation(), idempotency_key="rec", context=context
    )
    service.persist_disposition(
        attempt_id, _valid_disposition(), idempotency_key="disp", context=context
    )
    # Non-authoritative legacy contributions via the real importer.
    OneTimeImporter(store).import_ndjson(
        _legacy_ndjson(tmp_path),
        epoch=1,
        attempt_id=attempt_id,
        context=context,
    )
    return store, ProjectionBuilder(store), service, attempt_id, context


# ── 4. external-effect isolation over legacy handling (SC15) ────────────────


def test_legacy_handling_leaves_external_effect_spies_untouched(
    mixed_seeded: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replay/cumulative/legacy-context over a mixed attempt touch no surface.

    Exercises the three external-effect spies (git/provider, delivery,
    external-effect) alongside the durable-state spies across the full
    legacy-handling path: ``replay``, ``build_cumulative``, and
    ``read_legacy_context``.  None may be reached (SC15).
    """
    _, builder, _, attempt_id, _ = mixed_seeded
    spies = _install_category_spies(monkeypatch)

    builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)
    builder.build_cumulative([attempt_id])
    builder.read_legacy_context(attempt_id)

    for name, spy in spies.items():
        assert spy.untouched, (
            f"legacy handling mutated the {name} surface via: "
            f"{[c[0] for c in spy.calls]}"
        )


# ── 5. legacy context markers (positive) ────────────────────────────────────


def test_read_legacy_context_carries_legacy_markers(mixed_seeded: Any) -> None:
    """``read_legacy_context`` returns legacy_historical + derived_from_legacy."""
    _, builder, _, attempt_id, _ = mixed_seeded
    legacy = builder.read_legacy_context(attempt_id)

    assert len(legacy) == 2
    for event in legacy:
        assert event.event_type == AttemptEventType.EXTERNAL_EFFECT_OUTCOME
        payload = event.payload
        assert isinstance(payload, dict)
        assert payload["cl2_kind"] == CL2_KIND_LEGACY_HISTORICAL
        assert payload["envelope"]["metadata"]["derived_from_legacy"] is True
        # Original (non-v1) schema_version preserved byte-for-byte.
        assert payload["envelope"]["schema_version"] != "cl.schema.v1"


# ── 6. replay exclusion (positive) ──────────────────────────────────────────


def test_replay_excludes_legacy_with_legacy_derived_reason(
    mixed_seeded: Any,
) -> None:
    """Legacy OUTCOMEs are excluded from replay with reason ``legacy_derived``.

    The v1 partition is admitted (1 occurrence / reconciliation / disposition);
    both legacy OUTCOMEs land in ``replay_excluded`` and never reach
    ``replay_full``.
    """
    _, builder, _, attempt_id, _ = mixed_seeded
    result = builder.replay(attempt_id, wbc_receipt_chain=WBC_CHAIN)

    # The v1 partition is admitted and replay succeeds.
    assert len(result.occurrences) == 1
    assert len(result.reconciliations) == 1
    assert len(result.dispositions) == 1
    # Every legacy OUTCOME is excluded with reason legacy_derived.
    assert len(result.replay_excluded) == 2
    for excl in result.replay_excluded:
        assert excl.cl2_kind == CL2_KIND_LEGACY_HISTORICAL
        assert excl.reason == EXCLUSION_REASON_LEGACY_DERIVED


# ── 7. per-contribution non_authoritative scope (positive) ──────────────────


def test_legacy_contributions_carry_non_authoritative_scope(
    mixed_seeded: Any,
) -> None:
    """Each legacy contribution is scoped ``non_authoritative`` (per-contribution)."""
    _, builder, _, attempt_id, _ = mixed_seeded
    cumulative = builder.build_cumulative([attempt_id])

    legacy_contribs = [
        c for c in cumulative.contributions
        if c.cl2_kind == CL2_KIND_LEGACY_HISTORICAL
    ]
    assert len(legacy_contribs) == 2
    for contrib in legacy_contribs:
        assert contrib.authority_scope == AUTHORITY_SCOPE_NON_AUTHORITATIVE


# ── 8. mixed-attempt rollup (positive) ──────────────────────────────────────


def test_mixed_attempt_rolls_up_to_mixed_authoritative(
    mixed_seeded: Any,
) -> None:
    """A mixed attempt (v1 authoritative + legacy non-) rolls up to mixed.

    Authority is per-contribution, not per-attempt: the v1 OUTCOMEs are
    authoritative, the legacy OUTCOMEs are non_authoritative, and the per-attempt
    rollup is ``mixed_authoritative``.
    """
    _, builder, _, attempt_id, _ = mixed_seeded
    cumulative = builder.build_cumulative([attempt_id])

    scopes = {c.authority_scope for c in cumulative.contributions}
    assert AUTHORITY_SCOPE_AUTHORITATIVE in scopes
    assert AUTHORITY_SCOPE_NON_AUTHORITATIVE in scopes
    assert cumulative.attempt_authority_summary[attempt_id] == ATTEMPT_AUTHORITY_MIXED


# ── 9. missing-evidence labels (positive) ───────────────────────────────────


def test_missing_evidence_legacy_labels_without_briefing_or_reopen(
    mixed_seeded: Any,
) -> None:
    """Missing-evidence legacy records are labelled but never drive briefings.

    The imported missing-evidence record carries
    ``evidence_availability=UNAVAILABLE`` / ``unavailable_reason=legacy_import``
    (the labelling convention) and is NOT stamped with
    ``required_for_briefing`` or ``reopen_condition``: legacy evidence is
    historical context only — it must not reopen a finding or force a briefing.
    """
    _, builder, _, attempt_id, _ = mixed_seeded
    legacy = builder.read_legacy_context(attempt_id)

    unavailable = [
        e for e in legacy
        if e.payload["envelope"]["evidence_availability"]
        == EvidenceAvailability.UNAVAILABLE.value
    ]
    assert len(unavailable) == 1
    envelope = unavailable[0].payload["envelope"]

    # Exact labelling convention.
    assert envelope["unavailable_reason"] == LEGACY_UNAVAILABLE_REASON
    # No evidence keys leak onto an unavailable record.
    for key in ("evidence_ref", "raw_completion_hash", "redacted_prompt_hash"):
        assert key not in envelope
    # No briefing driver, no reopen trigger.
    assert "required_for_briefing" not in envelope.get("metadata", {})
    assert envelope["metadata"].get("required_for_briefing") is None
    assert "reopen_condition" not in envelope
    assert envelope.get("reopen_condition") is None
