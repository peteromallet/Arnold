"""Focused T3.2 proofs for the observation-only unblocker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.maintenance_unblocker import (
    CheckpointStore,
    ObservationEvidence,
    StableOccurrenceIdentity,
    UnblockerOutcome,
    emit_observation_bound_request,
    evaluate_observations,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def _identity(**changes: str) -> StableOccurrenceIdentity:
    values = {
        "occurrence": "occ-1",
        "plan_cursor": "plan:cursor-7",
        "runtime_manifest": "runtime:manifest-a",
        "target_digest": "target:" + "a" * 64,
        "source_cursor": "source:cursor-9",
    }
    values.update(changes)
    return StableOccurrenceIdentity(**values)


def _observation(
    *,
    read_id: str = "read-a",
    read_digest: str = "read-digest-a",
    at: datetime = NOW,
    identity: StableOccurrenceIdentity | None = None,
    evidence_ref: str | None = "evidence://blocked/1",
    producer: str = "producer-1",
    verifier: str = "verifier-1",
    pid: int | None = 123,
    tmux_session: str | None = "tmux-1",
    heartbeat: str | None = "heartbeat-1",
    path: str | None = "/opaque/observation/path",
    lease_epoch: int | None = 4,
    counters: dict[str, int] | None = None,
) -> ObservationEvidence:
    return ObservationEvidence(
        identity=identity or _identity(),
        observed_at=at,
        source_read_id=read_id,
        source_read_digest=read_digest,
        evidence_ref=evidence_ref,
        failure_fingerprint="deterministic-phase-failure:fp-1",
        producer_principal=producer,
        verifier_principal=verifier,
        pid=pid,
        tmux_session=tmux_session,
        heartbeat=heartbeat,
        path=path,
        lease_epoch=lease_epoch,
        permitted_counters=counters or {"observation_count": 1, "read_count": 1},
    )


def _pair(**second_changes: object) -> tuple[ObservationEvidence, ObservationEvidence]:
    first = _observation()
    values: dict[str, object] = {
        "read_id": "read-b",
        "read_digest": "read-digest-b",
        "at": NOW + timedelta(seconds=5),
        "counters": {"observation_count": 2, "read_count": 2},
    }
    values.update(second_changes)
    return first, _observation(**values)  # type: ignore[arg-type]


def test_single_observation_remains_unknown() -> None:
    result = evaluate_observations([_observation()])
    assert result.outcome is UnblockerOutcome.UNKNOWN
    assert result.request is None




def test_matching_stable_subset_and_distinct_reads_emit_inert_request() -> None:
    result = evaluate_observations(_pair())
    assert result.outcome is UnblockerOutcome.REQUEST_EMITTED
    assert result.request is not None
    assert result.request.occurrence == _identity()
    assert result.request.effect_authorized is False
    assert result.request.approval_required is True
    assert result.request.recovery_contract.authority == (
        "explicit_repair_commit_bound_to_engine_runtime"
    )
    assert result.request.recovery_contract.automatic is False


@pytest.mark.parametrize(
    "change",
    [
        {"identity": _identity(runtime_manifest="runtime:manifest-b")},
        {"identity": _identity(target_digest="target:" + "b" * 64)},
        {"identity": _identity(source_cursor="source:cursor-10")},
        {"pid": 999},
        {"lease_epoch": 5},
    ],
)
def test_stable_or_authority_looking_drift_rejects(change: dict[str, object]) -> None:
    first, second = _pair(**change)
    result = evaluate_observations([first, second])
    assert result.outcome is UnblockerOutcome.DRIFT_REJECTED
    assert result.request is None

def test_fixer_contract_is_inert_and_phase_retry_fenced() -> None:
    result = evaluate_observations(_pair())
    contract = result.request.recovery_contract
    assert contract.failure_kind == "deterministic_phase_failure"
    assert contract.retry_strategy == "repair_phase_contract"
    assert contract.repair_scope == "engine_runtime"
    assert contract.authority == "explicit_repair_commit_bound_to_engine_runtime"
    assert contract.approval_required is True
    assert contract.automatic is False
    assert "runtime_rebind_with_milestone_label_m7" in contract.verbs
    assert "recover_blocked_with_explicit_repair_commit" in contract.verbs
    assert "chain_start_one" in contract.verbs



def test_duplicate_stale_projection_with_new_timestamp_is_not_independent() -> None:
    first = _observation()
    second = _observation(
        read_id=first.source_read_id,
        read_digest=first.source_read_digest,
        at=NOW + timedelta(minutes=1),
        counters={"observation_count": 2, "read_count": 2},
    )
    result = evaluate_observations([first, second])
    assert result.outcome is UnblockerOutcome.DRIFT_REJECTED
    assert "underlying source read" in result.reasons[0]


def test_missing_evidence_remains_unknown() -> None:
    first, second = _pair(evidence_ref=None)
    result = evaluate_observations([first, second])
    assert result.outcome is UnblockerOutcome.UNKNOWN
    assert "missing" in result.reasons[0]


def test_producer_verifier_separation_is_required() -> None:
    first = _observation(producer="same", verifier="same")
    second = _observation(
        read_id="read-b",
        read_digest="read-digest-b",
        at=NOW + timedelta(seconds=5),
        producer="same",
        verifier="same",
        counters={"observation_count": 2, "read_count": 2},
    )
    result = evaluate_observations([first, second])
    assert result.outcome is UnblockerOutcome.DRIFT_REJECTED
    assert "distinct" in result.reasons[0]


def test_pid_and_lease_telemetry_never_proves_authority() -> None:
    first = _observation(
        pid=None, lease_epoch=None, tmux_session=None, heartbeat=None, path=None
    )
    second = _observation(
        read_id="read-b",
        read_digest="read-digest-b",
        at=NOW + timedelta(seconds=5),
        pid=None,
        lease_epoch=None,
        tmux_session=None,
        heartbeat=None,
        path=None,
        counters={"observation_count": 2, "read_count": 2},
    )
    result = evaluate_observations([first, second])
    assert result.outcome is UnblockerOutcome.REQUEST_EMITTED
    assert result.request is not None


def test_replay_and_stale_fence_checkpointing_are_safe(tmp_path: Path) -> None:
    disposable = tmp_path / "disposable-unblocker-root"
    store = CheckpointStore(disposable)
    assert store.root != Path.cwd().resolve()
    assert "candidate" not in str(store.root)
    assert "runtime" not in str(store.root)

    first = emit_observation_bound_request(_pair(), fence=7, checkpoint_store=store)
    replay = emit_observation_bound_request(_pair(), fence=7, checkpoint_store=store)
    stale = emit_observation_bound_request(_pair(), fence=6, checkpoint_store=store)
    assert first.outcome is UnblockerOutcome.REQUEST_EMITTED
    assert replay.outcome is UnblockerOutcome.REPLAYED
    assert stale.outcome is UnblockerOutcome.STALE_FENCE
    assert len(list(store.directory.glob("*.json"))) == 1


def test_checkpoint_root_rejects_project_or_live_runtime_roots() -> None:
    with pytest.raises(ValueError, match="disposable root"):
        CheckpointStore(Path.cwd())
    with pytest.raises(ValueError, match="project, candidate, or live"):
        CheckpointStore(Path("/tmp/live/runtime-candidate"))


def test_no_mutation_api_and_no_effect_authority() -> None:
    result = evaluate_observations(_pair())
    assert result.request is not None
    assert not hasattr(result.request, "approve")
    assert not hasattr(result.request, "execute")
    assert not hasattr(result.request, "recover_blocked")
    assert not hasattr(result.request, "runtime_rebind")
    assert not hasattr(result.request, "chain_start")
