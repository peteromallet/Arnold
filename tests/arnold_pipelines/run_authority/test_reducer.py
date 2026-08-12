from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from arnold_pipelines.run_authority import (
    CapabilityGrant,
    Claim,
    CoordinatorFence,
    Decision,
    EvidenceEnvelope,
    IdempotencyKey,
    ObservationEnvelope,
    SubjectAttempt,
    reduce_run_authority,
)


def _chain():
    evidence = EvidenceEnvelope("ev-1", "run-1", "rev-2", "result", "worker://one", {"ok": True})
    fence = CoordinatorFence("run-1", "rev-2", "coord-1", 3)
    grant = CapabilityGrant(
        "grant-1", "run-1", "rev-2", "coord-1", 3, ("subject-1",), ("submit",), ("ev-1",)
    )
    attempt = SubjectAttempt("attempt-1", "run-1", "rev-2", "subject-1", "grant-1", "coord-1", 3, 1)
    claim = Claim(
        "claim-1", "run-1", "rev-2", "subject-1", "attempt-1", "grant-1", "coord-1", 3,
        "result", ("ev-1",), "claim-key", {"state": "complete"},
    )
    decision = Decision(
        "decision-1", "run-1", "rev-2", "subject-1", "attempt-1", "grant-1", "coord-1", 3,
        "claim-1", "accepted", ("ev-1",), "decision-key", {"reason": "verified"},
    )
    return (
        evidence,
        fence,
        grant,
        attempt,
        IdempotencyKey("claim-key", claim.payload_hash),
        claim,
        IdempotencyKey("decision-key", decision.payload_hash),
        decision,
    )


def _reasons(view) -> set[str]:
    return {record.reason for record in view.quarantines}


def test_complete_chain_projects_stably_and_repeat_projection_is_idempotent() -> None:
    records = _chain()
    first = reduce_run_authority(records, run_id="run-1", run_revision="rev-2", journal_cursor=8)
    repeated = reduce_run_authority(records + records, run_id="run-1", run_revision="rev-2", journal_cursor=8)

    assert first.to_dict() == repeated.to_dict()
    assert first.to_json() == json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":"))
    assert len(first.evidence_set_digest) == len(first.view_hash) == 64
    assert [item.claim_id for item in first.claims] == ["claim-1"]
    assert [item.decision_id for item in first.decisions] == ["decision-1"]
    assert first.quarantines == ()
    with pytest.raises(FrozenInstanceError):
        first.run_id = "changed"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda records: tuple(replace(item, run_revision="old") if isinstance(item, Claim) else item for item in records), "missing_matching_revision"),
        (lambda records: tuple(item for item in records if not isinstance(item, SubjectAttempt)), "missing_matching_attempt"),
        (lambda records: tuple(item for item in records if not isinstance(item, CapabilityGrant)), "missing_matching_grant"),
        (lambda records: tuple(item for item in records if not isinstance(item, CoordinatorFence)), "missing_matching_fence"),
        (lambda records: tuple(item for item in records if not isinstance(item, EvidenceEnvelope)), "missing_matching_evidence"),
        (lambda records: tuple(item for item in records if not (isinstance(item, IdempotencyKey) and item.value == "claim-key")), "missing_matching_idempotency_identity"),
    ],
)
def test_every_incompletely_linked_claim_is_deterministically_quarantined(mutate, reason: str) -> None:
    view = reduce_run_authority(mutate(_chain()), run_id="run-1", run_revision="rev-2")

    assert view.claims == ()
    assert reason in _reasons(view)
    assert view.decisions == ()
    assert "missing_authoritative_claim" in _reasons(view)
    assert all(record.source.startswith("contract://") for record in view.quarantines)


def test_legacy_observations_are_preserved_but_never_create_authority() -> None:
    legacy = ObservationEnvelope(
        "legacy-1", "run-1", "old-revision", "legacy_terminal_label",
        "legacy://state", (), {"status": "complete"},
    )
    view = reduce_run_authority((legacy,), run_id="run-1", run_revision="rev-2")

    assert view.observations == (legacy,)
    assert view.claims == ()
    assert view.decisions == ()
    assert view.quarantines == ()


def test_conflicting_record_and_idempotency_keys_are_excluded_independent_of_order() -> None:
    records = _chain()
    claim = next(item for item in records if isinstance(item, Claim))
    conflicting_claim = replace(claim, payload={"state": "failed"})
    conflicting_key = IdempotencyKey("claim-key", conflicting_claim.payload_hash)
    mixed = records + (conflicting_claim, conflicting_key)

    forward = reduce_run_authority(mixed, run_id="run-1", run_revision="rev-2", journal_cursor=10)
    reverse = reduce_run_authority(tuple(reversed(mixed)), run_id="run-1", run_revision="rev-2", journal_cursor=10)

    assert forward.to_dict() == reverse.to_dict()
    conflicts = [item for item in forward.diagnostics if item.code == "conflicting_duplicate_key"]
    assert {(item.record_type, item.record_id) for item in conflicts} == {
        ("claim", "claim-1"), ("idempotency_key", "claim-key")
    }
    assert forward.claims == ()
    assert forward.decisions == ()


def test_reducer_leaves_mutable_input_container_and_contract_payloads_unchanged() -> None:
    records = list(_chain())
    before = [item.to_json() for item in records]
    container_ids = [id(item) for item in records]

    first = reduce_run_authority(records, run_id="run-1", run_revision="rev-2")
    second = reduce_run_authority(records, run_id="run-1", run_revision="rev-2")

    assert [item.to_json() for item in records] == before
    assert [id(item) for item in records] == container_ids
    assert first.to_dict() == second.to_dict()
    with pytest.raises(TypeError):
        records[0].payload["mutated"] = True


def test_reducer_source_has_no_external_or_domain_specific_reads() -> None:
    import arnold_pipelines.run_authority.reducer as reducer

    source = reducer.__loader__.get_source(reducer.__name__).lower()
    forbidden = (
        "pathlib", "open(", "requests", "subprocess", "datetime", "time.",
        "import git", "megaplan", "finalize.json", "state.json", "os.environ",
    )
    assert all(term not in source for term in forbidden)


def test_crash_restart_replay_with_prefix_and_reordering_produces_identical_projection() -> None:
    """Simulate a crash-restart: prefix of records seen, then all records replayed
    in a different order, some duplicated.  The reducer must produce the same
    deterministic RunAuthorityView regardless of duplicate streams, replay
    prefixes, or restart-equivalent reordering."""
    evidence = EvidenceEnvelope("ev-1", "run-1", "rev-2", "result", "worker://one", {"ok": True})
    fence = CoordinatorFence("run-1", "rev-2", "coord-1", 3)
    grant = CapabilityGrant(
        "grant-1", "run-1", "rev-2", "coord-1", 3, ("subject-1",), ("submit",), ("ev-1",)
    )
    attempt = SubjectAttempt("attempt-1", "run-1", "rev-2", "subject-1", "grant-1", "coord-1", 3, 1)
    claim = Claim(
        "claim-1", "run-1", "rev-2", "subject-1", "attempt-1", "grant-1", "coord-1", 3,
        "result", ("ev-1",), "claim-key", {"state": "complete"},
    )
    decision = Decision(
        "decision-1", "run-1", "rev-2", "subject-1", "attempt-1", "grant-1", "coord-1", 3,
        "claim-1", "accepted", ("ev-1",), "decision-key", {"reason": "verified"},
    )
    claim_key = IdempotencyKey("claim-key", claim.payload_hash)
    decision_key = IdempotencyKey("decision-key", decision.payload_hash)

    full_stream = (evidence, fence, grant, attempt, claim_key, claim, decision_key, decision)

    # All scenarios use the same journal_cursor so the resulting views
    # (including cursor and view_hash) are identical — the contract is that
    # the caller supplies the journal boundary and the reducer must not
    # depend on input ordering or duplicate count for its projections.
    cursor = 8

    # Baseline: normal ordered stream
    baseline = reduce_run_authority(full_stream, run_id="run-1", run_revision="rev-2", journal_cursor=cursor)

    # Scenario 1: duplicate stream (full replay of every record)
    duplicate = reduce_run_authority(
        full_stream + full_stream, run_id="run-1", run_revision="rev-2", journal_cursor=cursor
    )
    assert duplicate.to_dict() == baseline.to_dict()

    # Scenario 2: crash after prefix, then full replay
    # (events 1-4 seen, crash, then all events 1-8 replayed)
    prefix = full_stream[:4]  # evidence, fence, grant, attempt
    crash_replay = reduce_run_authority(
        prefix + full_stream, run_id="run-1", run_revision="rev-2", journal_cursor=cursor
    )
    assert crash_replay.to_dict() == baseline.to_dict()

    # Scenario 3: restart-equivalent reordering after crash
    # Prefix duplicated, then full stream reversed then forward again
    shuffled = reduce_run_authority(
        prefix + tuple(reversed(full_stream)) + full_stream,
        run_id="run-1", run_revision="rev-2", journal_cursor=cursor,
    )
    assert shuffled.to_dict() == baseline.to_dict()

    # Scenario 4: interleaved duplicates
    interleaved = (evidence, evidence, fence, grant, attempt, claim_key,
                   claim, decision_key, decision, fence, grant, attempt)
    interleaved_view = reduce_run_authority(
        interleaved, run_id="run-1", run_revision="rev-2", journal_cursor=cursor
    )
    assert interleaved_view.to_dict() == baseline.to_dict()

    # All views must have the same hash (strongest determinism check)
    assert len({baseline.view_hash, duplicate.view_hash, crash_replay.view_hash,
                shuffled.view_hash, interleaved_view.view_hash}) == 1


def _coherent_observation(observation_id="obs-coherent"):
    return ObservationEnvelope.capture(
        observation_id=observation_id,
        run_id="run-1",
        run_revision="rev-2",
        observation_type="runtime",
        source="collector://one",
        runtime_observation={
            "recorded_engine_root": "/workspace/arnold",
            "manifest_runtime_root": "/workspace/arnold",
            "manifest_expected_head": "a" * 40,
            "live_import_root": "/workspace/arnold",
            "wrapper_digest": "b" * 64,
            "dependency_generation": "v3-r7",
            "environment_identity": "env-a",
            "session_identity": "env-a",
        },
        source_identity="collector://one",
        source_version="1.2.3",
        source_cursor=7,
        content_hash="c" * 64,
    )


def test_unknown_and_incoherent_observations_never_collapse_to_success() -> None:
    legacy = ObservationEnvelope(
        "legacy-1", "run-1", "old-revision", "legacy_terminal_label",
        "legacy://state", (), {"status": "complete"},
    )
    torn = ObservationEnvelope.capture(
        observation_id="obs-torn",
        run_id="run-1",
        run_revision="rev-2",
        observation_type="runtime",
        source="collector://one",
        runtime_observation={
            "recorded_engine_root": "/workspace/arnold",
            "manifest_runtime_root": "/workspace/arnold",
            "manifest_expected_head": "a" * 40,
            "live_import_root": "/workspace/other",
            "wrapper_digest": "b" * 64,
            "dependency_generation": "v3-r7",
            "environment_identity": "env-a",
            "session_identity": "env-a",
        },
    )

    view = reduce_run_authority((legacy, torn), run_id="run-1", run_revision="rev-2")

    # Both are preserved as observations for auditability...
    assert {item.observation_id for item in view.observations} == {"legacy-1", "obs-torn"}
    # ...but neither is ever projected as coherent or mints authority.
    assert view.coherent_observations == ()
    assert view.claims == ()
    assert view.decisions == ()
    non_coherent = [item for item in view.diagnostics if item.code == "non_coherent_observation"]
    assert {item.record_id for item in non_coherent} == {"legacy-1", "obs-torn"}
    assert all(item.reason.endswith("cannot_authorize_dispatch") for item in non_coherent)


def test_coherent_observation_is_projected_but_mints_no_authority() -> None:
    envelope = _coherent_observation()

    view = reduce_run_authority(
        (envelope,), run_id="run-1", run_revision="rev-2", journal_cursor=8,
    )

    assert view.observations == (envelope,)
    assert view.coherent_observations == (envelope,)
    # A coherent observation is still only an observation: it never creates
    # accepted progress by itself.
    assert view.claims == ()
    assert view.decisions == ()
    assert not any(item.code == "non_coherent_observation" for item in view.diagnostics)


def test_coherent_observation_does_not_rescue_an_unresolved_claim() -> None:
    claim = Claim(
        "claim-1", "run-1", "rev-2", "subject-1", "attempt-1", "grant-1", "coord-1", 3,
        "result", ("ev-1",), "claim-key", {"state": "complete"},
    )
    envelope = _coherent_observation()

    view = reduce_run_authority(
        (claim, envelope), run_id="run-1", run_revision="rev-2", journal_cursor=8,
    )

    assert view.claims == ()
    assert view.decisions == ()
    assert any(q.reason.startswith("missing_matching") for q in view.quarantines)
    assert view.coherent_observations == (envelope,)


def test_older_revision_observation_is_stale_and_never_dispatchable() -> None:
    current = _coherent_observation("obs-current")
    stale = replace(_coherent_observation("obs-stale"), run_revision="rev-1")
    foreign = replace(_coherent_observation("obs-foreign"), run_id="run-other")
    future = replace(_coherent_observation("obs-future"), source_cursor=9)

    view = reduce_run_authority(
        (stale, current, foreign, future),
        run_id="run-1",
        run_revision="rev-2",
        journal_cursor=8,
    )

    # Same run id + matching revision: projected coherent.
    assert view.coherent_observations == (current,)
    # Same run id, older run revision: preserved for auditability but never
    # projected coherent, and surfaced as a stale diagnostic.
    assert stale in view.observations
    assert stale not in view.coherent_observations
    # Differing run id: not projected at all.
    assert foreign not in view.observations
    assert foreign not in view.coherent_observations
    # Source cursor beyond the view's journal boundary is stale too.
    assert future in view.observations
    assert future not in view.coherent_observations

    stale_diagnostics = [
        item for item in view.diagnostics
        if item.code == "non_coherent_observation"
        and item.record_id in {"obs-stale", "obs-future"}
    ]
    assert {item.record_id for item in stale_diagnostics} == {"obs-stale", "obs-future"}
    assert all(
        item.reason == "stale_observation_cannot_authorize_dispatch"
        for item in stale_diagnostics
    )
    assert not any(
        item.code == "non_coherent_observation" and item.record_id == "obs-current"
        for item in view.diagnostics
    )
