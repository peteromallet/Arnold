"""Focused resident boundary tests for T3.2 observation-only handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from arnold_pipelines.megaplan.cloud.maintenance_unblocker import UnblockerOutcome
from arnold_pipelines.megaplan.resident.cli import handle_maintenance_unblocker_wakeup


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def _observation(read_id: str, read_digest: str, at: datetime) -> dict[str, object]:
    return {
        "identity": {
            "occurrence": "occ-handler-1",
            "plan_cursor": "plan:cursor-1",
            "runtime_manifest": "runtime:manifest-1",
            "target_digest": "target:digest-1",
            "source_cursor": "source:cursor-1",
        },
        "observed_at": at.isoformat(),
        "source_read_id": read_id,
        "source_read_digest": read_digest,
        "evidence_ref": "evidence://handler/1",
        "failure_fingerprint": "deterministic-phase-failure:handler",
        "producer_principal": "producer-handler",
        "verifier_principal": "verifier-handler",
        "pid": 111,
        "tmux_session": "tmux-handler",
        "heartbeat": "heartbeat-handler",
        "path": "/opaque/handler-path",
        "lease_epoch": 3,
        "permitted_counters": {"observation_count": 1, "read_count": 1},
    }


def test_bounded_handler_emits_request_without_claim_or_effect(tmp_path: Path) -> None:
    payload = {
        "observations": [
            _observation("handler-read-a", "handler-digest-a", NOW),
            _observation(
                "handler-read-b", "handler-digest-b", NOW + timedelta(seconds=1)
            ),
        ]
    }
    result = handle_maintenance_unblocker_wakeup(
        payload,
        checkpoint_root=tmp_path / "disposable-handler-root",
        fence=2,
    )
    assert result["outcome"] == UnblockerOutcome.REQUEST_EMITTED.value
    request = result["request"]
    assert request["effect_authorized"] is False
    assert request["approval_required"] is True
    assert not (tmp_path / "disposable-handler-root" / "plan").exists()
    assert not (tmp_path / "disposable-handler-root" / "chain").exists()


def test_bounded_handler_keeps_one_observation_unknown() -> None:
    result = handle_maintenance_unblocker_wakeup(
        {"observation": _observation("only-read", "only-digest", NOW)}
    )
    assert result["outcome"] == UnblockerOutcome.UNKNOWN.value
    assert result["request"] is None


def test_bounded_handler_replay_is_idempotent(tmp_path: Path) -> None:
    payload = {
        "observations": [
            _observation("replay-a", "replay-digest-a", NOW),
            _observation("replay-b", "replay-digest-b", NOW + timedelta(seconds=1)),
        ]
    }
    root = tmp_path / "disposable-handler-replay"
    first = handle_maintenance_unblocker_wakeup(payload, checkpoint_root=root, fence=4)
    replay = handle_maintenance_unblocker_wakeup(payload, checkpoint_root=root, fence=4)
    assert first["outcome"] == UnblockerOutcome.REQUEST_EMITTED.value
    assert replay["outcome"] == UnblockerOutcome.REPLAYED.value
    assert len(list((root / "maintenance-unblocker-checkpoints").glob("*.json"))) == 1
