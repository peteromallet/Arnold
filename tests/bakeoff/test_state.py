import json
from pathlib import Path

from megaplan.bakeoff.state import (
    BAKEOFF_SCHEMA_VERSION,
    CHANNEL_SHADOW_SCHEMA_VERSION,
    load_channel_shadow_state,
    load_bakeoff_state,
    save_channel_shadow_state,
    save_bakeoff_state,
    worktree_root,
)


def test_bakeoff_state_round_trip_atomic_and_schema_pinned(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    state = {
        "schema_version": BAKEOFF_SCHEMA_VERSION,
        "experiment_id": "exp-1",
        "base_sha": "abc123",
        "idea_hash": "hash",
        "idea_path": str(root / "idea.md"),
        "mode": "code",
        "profiles": [
            {
                "name": "apex",
                "worktree": str(worktree_root(root, "exp-1") / "apex"),
                "plan_id": "exp-1",
                "pid": None,
                "launched_at": None,
                "terminated_at": None,
                "outcome": None,
                "log_path": str(root / ".megaplan" / "bakeoffs" / "exp-1" / "apex" / "auto.log"),
                "outcome_path": str(root / ".megaplan" / "bakeoffs" / "exp-1" / "apex" / "outcome.json"),
            }
        ],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }

    save_bakeoff_state(root, state)

    path = root / ".megaplan" / "bakeoffs" / "exp-1" / "bakeoff.json"
    assert path.exists()
    assert load_bakeoff_state(root, "exp-1") == state
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert not list(path.parent.glob("*.tmp"))


def test_channel_shadow_state_round_trips_required_artifact_fields(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    state = {
        "schema_version": CHANNEL_SHADOW_SCHEMA_VERSION,
        "experiment_id": "exp-shadow",
        "real_parity_success_count": 1,
        "records": [
            {
                "recorded_at": "2026-06-12T09:00:00Z",
                "real_parity_success_count": 1,
                "channel_pair": {
                    "primary_worker_channel": "shannon_tmux",
                    "primary_auth_channel": "subscription",
                    "shadow_worker_channel": "shannon_stream",
                    "shadow_auth_channel": "api_key",
                },
                "decision": {
                    "sampled": True,
                    "skipped": False,
                    "skip_reason": None,
                    "sample_rate": 0.1,
                    "sample_key": "plan-1:execute:0",
                },
                "primary_receipt": {
                    "receipt_path": ".megaplan/plans/plan-1/receipts/primary.json",
                    "worker_channel": "shannon_tmux",
                    "auth_channel": "subscription",
                    "phase": "execute",
                    "plan_id": "plan-1",
                    "exit_kind": "success",
                    "payload_schema_valid": True,
                    "landed_diff": "satisfied",
                    "worker_did_work": "satisfied",
                    "latency_ms": 1200,
                    "cost_usd": 0.03,
                    "metadata": {"request_id": "primary-1"},
                },
                "shadow_receipt": {
                    "receipt_path": ".megaplan/plans/plan-1/receipts/shadow.json",
                    "worker_channel": "shannon_stream",
                    "auth_channel": "api_key",
                    "phase": "execute",
                    "plan_id": "plan-1",
                    "exit_kind": "success",
                    "payload_schema_valid": True,
                    "landed_diff": "satisfied",
                    "worker_did_work": "satisfied",
                    "latency_ms": 1500,
                    "cost_usd": 0.04,
                    "metadata": {"request_id": "shadow-1"},
                },
                "drift": {
                    "primary_latency_ms": 1200,
                    "shadow_latency_ms": 1500,
                    "latency_drift_ms": 300,
                    "latency_drift_ratio": 0.25,
                    "primary_cost_usd": 0.03,
                    "shadow_cost_usd": 0.04,
                    "cost_drift_usd": 0.01,
                    "cost_drift_ratio": 0.3333333333,
                },
                "parity_result": {
                    "passed": True,
                    "exit_kind_match": True,
                    "payload_schema_valid_match": True,
                    "landed_diff_match": True,
                    "worker_did_work_match": True,
                    "compared_at": "2026-06-12T09:01:00Z",
                    "details": {"comparator": "deterministic-v1"},
                },
            },
            {
                "recorded_at": "2026-06-12T09:05:00Z",
                "real_parity_success_count": 1,
                "channel_pair": {
                    "primary_worker_channel": "shannon_tmux",
                    "primary_auth_channel": "subscription",
                    "shadow_worker_channel": "shannon_stream",
                    "shadow_auth_channel": "api_key",
                },
                "decision": {
                    "sampled": False,
                    "skipped": True,
                    "skip_reason": "not_sampled",
                    "sample_rate": 0.1,
                    "sample_key": "plan-1:review:0",
                },
                "primary_receipt": {
                    "receipt_path": ".megaplan/plans/plan-1/receipts/primary-review.json",
                    "worker_channel": "shannon_tmux",
                    "auth_channel": "subscription",
                    "phase": "review",
                    "plan_id": "plan-1",
                    "exit_kind": "success",
                    "payload_schema_valid": True,
                    "landed_diff": None,
                    "worker_did_work": "satisfied",
                    "latency_ms": 900,
                    "cost_usd": 0.02,
                    "metadata": {},
                },
                "shadow_receipt": None,
                "drift": None,
                "parity_result": None,
            },
        ],
    }

    save_channel_shadow_state(root, state)

    path = root / ".megaplan" / "bakeoffs" / "exp-shadow" / "channel_shadow.json"
    loaded_json = json.loads(path.read_text(encoding="utf-8"))
    assert loaded_json["schema_version"] == 1
    assert loaded_json["records"][0]["primary_receipt"]["exit_kind"] == "success"
    assert loaded_json["records"][0]["shadow_receipt"]["auth_channel"] == "api_key"
    assert loaded_json["records"][1]["decision"]["skip_reason"] == "not_sampled"
    assert load_channel_shadow_state(root, "exp-shadow") == state


def test_legacy_bakeoff_state_fixture_does_not_gain_channel_shadow_fields(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    legacy_state = {
        "schema_version": BAKEOFF_SCHEMA_VERSION,
        "experiment_id": "legacy-exp",
        "base_sha": "abc123",
        "idea_hash": "hash",
        "idea_path": str(root / "idea.md"),
        "mode": "code",
        "profiles": [],
        "phase": "running",
        "chosen_profile": None,
        "merged_at": None,
        "judge_model": None,
    }

    save_bakeoff_state(root, legacy_state)

    path = root / ".megaplan" / "bakeoffs" / "legacy-exp" / "bakeoff.json"
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted == legacy_state
    assert "channel_shadow" not in persisted
    assert not (path.parent / "channel_shadow.json").exists()
    assert load_bakeoff_state(root, "legacy-exp") == legacy_state
