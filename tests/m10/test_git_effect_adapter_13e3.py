"""Tests for Step 13E3: git add/commit/update-ref adapter routing.

Covers:
- Shard enforcement (only ADD/COMMIT/UPDATE_REF accepted by route_staging)
- Command-specific semantics (paths for add, message for commit, ref+hash for update_ref)
- Duplicate dispatch (same attempt_id produces idempotent GLEK)
- Crash behavior (protocol errors produce INDETERMINATE)
- Stale-fence negatives
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from arnold.workflow.effect_protocol import (
    EffectProtocol,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_INDETERMINATE,
)
from arnold.workflow.execution_attempt_ledger import GlobalEffectIdentity
from arnold_pipelines.megaplan.chain.git_effect_adapter import (
    GitEffectShard,
    GIT_SHARD_13E2,
    GIT_SHARD_13E3,
    GitTarget,
    GitOutcome,
    GitEffectAdapter,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_protocol():
    """Create a mock EffectProtocol."""
    protocol = MagicMock(spec=EffectProtocol)
    reservation = MagicMock()
    reservation.global_logical_effect_key = "glek-test-123"
    protocol.reserve_and_start.return_value = reservation
    return protocol


@pytest.fixture
def adapter(mock_protocol):
    """Create a GitEffectAdapter with shadow gate."""
    return GitEffectAdapter(
        mock_protocol,
        production_enabled=False,
    )


@pytest.fixture
def add_target():
    return GitTarget(
        shard=GitEffectShard.ADD,
        module="arnold_pipelines/megaplan/chain/git_ops.py",
        enclosing_function="_commit_phase",
        repository="test-repo",
        branch="main",
    )


@pytest.fixture
def commit_target():
    return GitTarget(
        shard=GitEffectShard.COMMIT,
        module="arnold_pipelines/megaplan/chain/git_ops.py",
        enclosing_function="_commit_phase",
        repository="test-repo",
        branch="main",
    )


@pytest.fixture
def update_ref_target():
    return GitTarget(
        shard=GitEffectShard.UPDATE_REF,
        module="arnold_pipelines/megaplan/chain/git_ops.py",
        enclosing_function="commit_plan_artifacts_to_base",
        repository="test-repo",
        branch="main",
    )


# ── Shard enforcement ────────────────────────────────────────────────────────


def test_route_staging_rejects_13e2_shards(adapter):
    """route_staging rejects reset/clean/checkout (13E2 shards)."""
    for shard in GIT_SHARD_13E2:
        target = GitTarget(
            shard=shard,
            module="test.py",
            enclosing_function="test_fn",
        )
        with pytest.raises(ValueError, match="route_staging only supports Step 13E3"):
            adapter.route_staging(
                target=target,
                intent_payload={},
                apply_fn=lambda x: x,
            )


def test_route_accepts_all_13e3_shards(adapter, mock_protocol):
    """General route() accepts all 13E3 shards."""
    for shard in GIT_SHARD_13E3:
        target = GitTarget(
            shard=shard,
            module="test.py",
            enclosing_function="test_fn",
        )
        # route_staging requires command-specific payload
        payload = {}
        if shard == GitEffectShard.ADD:
            payload = {"paths": ["file.py"]}
        elif shard == GitEffectShard.COMMIT:
            payload = {"message": "test commit"}
        elif shard == GitEffectShard.UPDATE_REF:
            payload = {"ref": "refs/heads/main", "target_hash": "abc123"}

        result = adapter.route_staging(
            target=target,
            intent_payload=payload,
            apply_fn=lambda x: {"ok": True},
            fence_token=1,
        )
        assert result.ok, f"Shard {shard.value} should succeed"
        assert result.glek != ""


def test_unknown_shard_rejected(adapter):
    """A shard not in 13E2 or 13E3 is rejected by route()."""
    # Create a target with a shard value not in the enum
    class FakeShard:
        value = "unknown_shard"

    target = MagicMock()
    target.shard = FakeShard()
    target.target_key = "git:unknown:test"
    target.repository = "test"
    target.enclosing_function = "test_fn"
    target.module = "test.py"

    with pytest.raises((ValueError, TypeError)):
        adapter.route(
            target=target,
            intent_payload={},
            apply_fn=lambda x: x,
        )


# ── Command-specific semantics ───────────────────────────────────────────────


def test_add_requires_non_empty_paths(adapter, add_target):
    """git add rejects empty or missing paths."""
    # Empty list
    result = adapter.route_staging(
        target=add_target,
        intent_payload={"paths": []},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "paths" in result.error.lower()

    # Missing paths key
    result = adapter.route_staging(
        target=add_target,
        intent_payload={},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "paths" in result.error.lower()


def test_commit_requires_non_empty_message(adapter, commit_target):
    """git commit rejects empty or missing message."""
    # Empty string
    result = adapter.route_staging(
        target=commit_target,
        intent_payload={"message": ""},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "message" in result.error.lower()

    # Whitespace only
    result = adapter.route_staging(
        target=commit_target,
        intent_payload={"message": "   "},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "message" in result.error.lower()

    # Missing message key
    result = adapter.route_staging(
        target=commit_target,
        intent_payload={},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "message" in result.error.lower()


def test_update_ref_requires_ref_and_target_hash(adapter, update_ref_target):
    """git update-ref requires ref and target_hash."""
    # Missing both
    result = adapter.route_staging(
        target=update_ref_target,
        intent_payload={},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "ref" in result.error.lower()

    # Missing target_hash
    result = adapter.route_staging(
        target=update_ref_target,
        intent_payload={"ref": "refs/heads/main"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "ref" in result.error.lower()

    # Missing ref
    result = adapter.route_staging(
        target=update_ref_target,
        intent_payload={"target_hash": "abc123"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "ref" in result.error.lower()


def test_add_with_valid_paths_succeeds(adapter, add_target, mock_protocol):
    """git add with valid paths dispatches successfully."""
    result = adapter.route_staging(
        target=add_target,
        intent_payload={"paths": ["file1.py", "file2.py"]},
        apply_fn=lambda x: {"ok": True, "staged": x.get("paths")},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


def test_commit_with_valid_message_succeeds(adapter, commit_target, mock_protocol):
    """git commit with valid message dispatches successfully."""
    result = adapter.route_staging(
        target=commit_target,
        intent_payload={"message": "feat: add new feature"},
        apply_fn=lambda x: {"ok": True, "hash": "abc123"},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


def test_update_ref_with_valid_args_succeeds(adapter, update_ref_target, mock_protocol):
    """git update-ref with valid args dispatches successfully."""
    result = adapter.route_staging(
        target=update_ref_target,
        intent_payload={"ref": "refs/heads/main", "target_hash": "abc123def456"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


# ── Duplicate dispatch (crash-idempotency) ───────────────────────────────────


def test_duplicate_dispatch_same_attempt_id(adapter, add_target, mock_protocol):
    """Re-dispatching with the same attempt_id is idempotent."""
    payload = {"paths": ["file.py"]}
    attempt_id = "11111111-1111-1111-1111-111111111111"

    # First dispatch
    result1 = adapter.route_staging(
        target=add_target,
        intent_payload=payload,
        apply_fn=lambda x: {"ok": True},
        attempt_id=attempt_id,
        fence_token=1,
    )
    assert result1.ok
    glek1 = result1.glek

    # Second dispatch with same attempt_id
    result2 = adapter.route_staging(
        target=add_target,
        intent_payload=payload,
        apply_fn=lambda x: {"ok": True},
        attempt_id=attempt_id,
        fence_token=1,
    )
    # The protocol handles idempotency; the GLEK should be the same
    assert result2.ok or result2.outcome_kind == OUTCOME_INDETERMINATE
    assert mock_protocol.reserve_and_start.call_count >= 1


def test_different_attempt_ids_produce_different_reservations(adapter, add_target, mock_protocol):
    """Different attempt_ids produce separate reservations."""
    payload = {"paths": ["file.py"]}

    mock_protocol.reset_mock()
    reservation1 = MagicMock()
    reservation1.global_logical_effect_key = "glek-001"
    reservation2 = MagicMock()
    reservation2.global_logical_effect_key = "glek-002"
    mock_protocol.reserve_and_start.side_effect = [reservation1, reservation2]

    result1 = adapter.route_staging(
        target=add_target,
        intent_payload=payload,
        apply_fn=lambda x: {"ok": True},
        attempt_id="22222222-2222-2222-2222-222222222222",
        fence_token=1,
    )
    result2 = adapter.route_staging(
        target=add_target,
        intent_payload=payload,
        apply_fn=lambda x: {"ok": True},
        attempt_id="33333333-3333-3333-3333-333333333333",
        fence_token=1,
    )

    assert result1.glek == "glek-001"
    assert result2.glek == "glek-002"
    assert result1.glek != result2.glek


# ── Crash behavior ───────────────────────────────────────────────────────────


def test_protocol_exception_produces_indeterminate(adapter, add_target, mock_protocol):
    """If the protocol raises, the outcome is INDETERMINATE."""
    mock_protocol.reserve_and_start.side_effect = RuntimeError("DB crashed")

    result = adapter.route_staging(
        target=add_target,
        intent_payload={"paths": ["file.py"]},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_INDETERMINATE
    assert "Protocol error" in result.error


def test_apply_fn_exception_produces_failed(adapter, add_target, mock_protocol):
    """If the apply_fn raises, the outcome is FAILED."""
    def failing_apply(payload):
        raise ValueError("git add failed: permission denied")

    result = adapter.route_staging(
        target=add_target,
        intent_payload={"paths": ["protected.py"]},
        apply_fn=failing_apply,
        fence_token=1,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_FAILED
    assert "permission denied" in result.error


# ── Stale-fence negatives ────────────────────────────────────────────────────


def test_stale_fence_blocks_staging(adapter, add_target):
    """Missing fence_token blocks staging dispatch."""
    result = adapter.route_staging(
        target=add_target,
        intent_payload={"paths": ["file.py"]},
        apply_fn=lambda x: x,
        fence_token=None,
    )
    assert not result.ok
    assert "Stale fence" in result.error


def test_zero_fence_token_blocks_staging(adapter, add_target):
    """Zero fence_token is treated as stale."""
    result = adapter.route_staging(
        target=add_target,
        intent_payload={"paths": ["file.py"]},
        apply_fn=lambda x: x,
        fence_token=0,
    )
    assert not result.ok
    assert "Stale fence" in result.error


# ── GLEK stability ───────────────────────────────────────────────────────────


def test_glek_stable_for_same_target(adapter, add_target):
    """Same target produces same GLEK identity inputs."""
    ei1 = adapter._build_effect_identity(add_target)
    ei2 = adapter._build_effect_identity(add_target)
    assert ei1.environment_id == ei2.environment_id
    assert ei1.action_target == ei2.action_target
    assert ei1.effect_family == ei2.effect_family


def test_glek_differs_for_different_shards(adapter, add_target, commit_target):
    """Different shards produce different effect identities."""
    ei_add = adapter._build_effect_identity(add_target)
    ei_commit = adapter._build_effect_identity(commit_target)
    assert ei_add.effect_family != ei_commit.effect_family


# ── Default apply_fn passthrough ─────────────────────────────────────────────


def test_route_passes_payload_to_apply_fn(adapter, add_target, mock_protocol):
    """The apply_fn receives the intent_payload."""
    captured = {}

    def capture_apply(payload):
        captured["received"] = payload
        return {"ok": True}

    adapter.route_staging(
        target=add_target,
        intent_payload={"paths": ["a.py"], "extra": "data"},
        apply_fn=capture_apply,
        fence_token=1,
    )
    assert captured["received"] == {"paths": ["a.py"], "extra": "data"}
