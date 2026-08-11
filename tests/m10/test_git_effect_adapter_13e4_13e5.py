"""Tests for Steps 13E4-13E5: git rebase/stash/worktree/push/force-with-lease.

Covers:
- Shard enforcement (route_worktree only accepts 13E4, route_remote only 13E5)
- Command-specific semantics for all 5 new shards
- Stale-fence negatives for both worktree and remote paths
- Lost-ACK reconciliation (APPLIED, NOT_APPLIED, UNKNOWN, query failure)
- Provider-idempotency key stability
- Crash behavior (protocol errors produce INDETERMINATE)
- Overflow action-off for non-routed shards
- GLEK stability
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
from arnold.workflow.effect_reconciliation import (
    ReconciliationResult,
    ReconciliationVerdict,
    QueryFailureError,
)
from arnold.workflow.execution_attempt_ledger import GlobalEffectIdentity
from arnold_pipelines.megaplan.chain.git_effect_adapter import (
    GitEffectShard,
    GIT_SHARD_13E2,
    GIT_SHARD_13E3,
    GIT_SHARD_13E4,
    GIT_SHARD_13E5,
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
    reservation.global_logical_effect_key = "glek-13e4-13e5-test-123"
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
def rebase_target():
    return GitTarget(
        shard=GitEffectShard.REBASE,
        module="arnold_pipelines/megaplan/chain/git_ops.py",
        enclosing_function="_checkout_milestone_branch",
        repository="test-repo",
        branch="main",
    )


@pytest.fixture
def stash_target():
    return GitTarget(
        shard=GitEffectShard.STASH,
        module="arnold_pipelines/megaplan/chain/__init__.py",
        enclosing_function="_assert_clean_base",
        repository="test-repo",
        branch="main",
    )


@pytest.fixture
def worktree_target():
    return GitTarget(
        shard=GitEffectShard.WORKTREE,
        module="arnold_pipelines/megaplan/bakeoff/worktree.py",
        enclosing_function="create_named_worktree",
        repository="test-repo",
        branch="main",
    )


@pytest.fixture
def push_target():
    return GitTarget(
        shard=GitEffectShard.PUSH,
        module="arnold_pipelines/megaplan/chain/git_ops.py",
        enclosing_function="_commit_and_push_phase",
        repository="test-repo",
        branch="main",
    )


@pytest.fixture
def force_with_lease_target():
    return GitTarget(
        shard=GitEffectShard.FORCE_WITH_LEASE,
        module="arnold_pipelines/megaplan/chain/git_ops.py",
        enclosing_function="_checkout_milestone_branch",
        repository="test-repo",
        branch="main",
    )


# ── Shard enforcement: route_worktree ────────────────────────────────────────


def test_route_worktree_rejects_non_13e4_shards(adapter):
    """route_worktree rejects shards outside 13E4."""
    non_13e4 = [
        s for s in GitEffectShard
        if s not in GIT_SHARD_13E4
    ]
    assert len(non_13e4) > 0, "Should have non-13E4 shards to test rejection"

    for shard in non_13e4:
        target = GitTarget(
            shard=shard,
            module="test.py",
            enclosing_function="test_fn",
        )
        with pytest.raises(ValueError, match="route_worktree only supports Step 13E4"):
            adapter.route_worktree(
                target=target,
                intent_payload={},
                apply_fn=lambda x: x,
            )


def test_route_worktree_accepts_all_13e4_shards(adapter, mock_protocol):
    """route_worktree accepts all 13E4 shards with valid payloads."""
    payloads = {
        GitEffectShard.REBASE: {"branch": "main"},
        GitEffectShard.STASH: {"paths": ["file.py"], "message": "wip"},
        GitEffectShard.WORKTREE: {"path": "/tmp/wt", "action": "add"},
    }

    for shard in GIT_SHARD_13E4:
        target = GitTarget(
            shard=shard,
            module="test.py",
            enclosing_function="test_fn",
        )
        payload = payloads[shard]
        result = adapter.route_worktree(
            target=target,
            intent_payload=payload,
            apply_fn=lambda x: {"ok": True},
            fence_token=1,
        )
        assert result.ok, f"Shard {shard.value} should succeed"
        assert result.glek != ""


# ── Shard enforcement: route_remote ───────────────────────────────────────────


def test_route_remote_rejects_non_13e5_shards(adapter):
    """route_remote rejects shards outside 13E5."""
    non_13e5 = [
        s for s in GitEffectShard
        if s not in GIT_SHARD_13E5
    ]
    assert len(non_13e5) > 0, "Should have non-13E5 shards to test rejection"

    for shard in non_13e5:
        target = GitTarget(
            shard=shard,
            module="test.py",
            enclosing_function="test_fn",
        )
        with pytest.raises(ValueError, match="route_remote only supports Step 13E5"):
            adapter.route_remote(
                target=target,
                intent_payload={"branch": "main", "remote": "origin"},
                apply_fn=lambda x: x,
            )


# ── Command-specific semantics: 13E4 ─────────────────────────────────────────


def test_rebase_requires_branch(adapter, rebase_target):
    """git rebase rejects empty or missing branch."""
    # Missing branch
    result = adapter.route_worktree(
        target=rebase_target,
        intent_payload={},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "branch" in result.error.lower()

    # Empty branch
    result = adapter.route_worktree(
        target=rebase_target,
        intent_payload={"branch": ""},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "branch" in result.error.lower()

    # Whitespace-only branch
    result = adapter.route_worktree(
        target=rebase_target,
        intent_payload={"branch": "   "},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "branch" in result.error.lower()


def test_rebase_with_valid_branch_succeeds(adapter, rebase_target, mock_protocol):
    """git rebase with valid branch dispatches successfully."""
    result = adapter.route_worktree(
        target=rebase_target,
        intent_payload={"branch": "main"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


def test_stash_empty_paths_is_noop(adapter, stash_target):
    """git stash with explicitly empty paths returns ok without dispatch."""
    result = adapter.route_worktree(
        target=stash_target,
        intent_payload={"paths": []},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert result.ok
    assert result.glek == ""  # No dispatch
    assert result.evidence.get("action") == "noop"


def test_stash_no_paths_key_dispatches(adapter, stash_target, mock_protocol):
    """git stash without paths key (None) dispatches normally."""
    result = adapter.route_worktree(
        target=stash_target,
        intent_payload={"message": "wip: save work"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""


def test_stash_with_valid_paths_succeeds(adapter, stash_target, mock_protocol):
    """git stash with specific paths dispatches successfully."""
    result = adapter.route_worktree(
        target=stash_target,
        intent_payload={"paths": ["file.py", "other.py"], "message": "wip"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


def test_worktree_requires_path_and_action(adapter, worktree_target):
    """git worktree rejects missing path or action."""
    # Missing both
    result = adapter.route_worktree(
        target=worktree_target,
        intent_payload={},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "path" in result.error.lower()

    # Missing action
    result = adapter.route_worktree(
        target=worktree_target,
        intent_payload={"path": "/tmp/wt"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "action" in result.error.lower()

    # Missing path
    result = adapter.route_worktree(
        target=worktree_target,
        intent_payload={"action": "add"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "path" in result.error.lower()


def test_worktree_list_is_rejected(adapter, worktree_target):
    """git worktree list is read-only and rejected as a mutation."""
    result = adapter.route_worktree(
        target=worktree_target,
        intent_payload={"path": "/tmp/wt", "action": "list"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "read-only" in result.error.lower()


def test_worktree_unknown_action_rejected(adapter, worktree_target):
    """Unknown worktree action is rejected."""
    result = adapter.route_worktree(
        target=worktree_target,
        intent_payload={"path": "/tmp/wt", "action": "prune"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "unknown worktree action" in result.error.lower()


def test_worktree_add_succeeds(adapter, worktree_target, mock_protocol):
    """git worktree add dispatches successfully."""
    result = adapter.route_worktree(
        target=worktree_target,
        intent_payload={"path": "/tmp/new-worktree", "action": "add", "base": "main"},
        apply_fn=lambda x: {"ok": True, "path": x["path"]},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


def test_worktree_remove_succeeds(adapter, worktree_target, mock_protocol):
    """git worktree remove dispatches successfully."""
    result = adapter.route_worktree(
        target=worktree_target,
        intent_payload={"path": "/tmp/old-worktree", "action": "remove", "force": True},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


# ── Command-specific semantics: 13E5 ─────────────────────────────────────────


def test_push_requires_branch_and_remote(adapter, push_target):
    """git push rejects missing branch or remote."""
    # Missing both
    result = adapter.route_remote(
        target=push_target,
        intent_payload={},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "branch" in result.error.lower()

    # Missing remote
    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "remote" in result.error.lower()

    # Missing branch
    result = adapter.route_remote(
        target=push_target,
        intent_payload={"remote": "origin"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "branch" in result.error.lower()


def test_force_with_lease_requires_branch_remote_expected_sha(
    adapter, force_with_lease_target
):
    """git force-with-lease requires branch, remote, and expected_sha."""
    # Missing all
    result = adapter.route_remote(
        target=force_with_lease_target,
        intent_payload={},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "expected_sha" in result.error.lower()

    # Missing expected_sha
    result = adapter.route_remote(
        target=force_with_lease_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "expected_sha" in result.error.lower()

    # Missing remote
    result = adapter.route_remote(
        target=force_with_lease_target,
        intent_payload={"branch": "main", "expected_sha": "abc123"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert "remote" in result.error.lower()


def test_push_with_valid_args_succeeds(adapter, push_target, mock_protocol):
    """git push with valid branch+remote dispatches successfully."""
    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True, "ref": "refs/heads/main"},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


def test_force_with_lease_with_valid_args_succeeds(
    adapter, force_with_lease_target, mock_protocol
):
    """git force-with-lease with valid args dispatches successfully."""
    result = adapter.route_remote(
        target=force_with_lease_target,
        intent_payload={
            "branch": "main",
            "remote": "origin",
            "expected_sha": "abc123def456",
        },
        apply_fn=lambda x: {"ok": True, "forced": True},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED


# ── Stale-fence negatives: 13E4 ──────────────────────────────────────────────


def test_route_worktree_stale_fence_rejected(adapter, rebase_target):
    """Missing fence_token blocks worktree dispatch."""
    result = adapter.route_worktree(
        target=rebase_target,
        intent_payload={"branch": "main"},
        apply_fn=lambda x: x,
        fence_token=None,
    )
    assert not result.ok
    assert "Stale fence" in result.error


def test_route_worktree_zero_fence_rejected(adapter, rebase_target):
    """Zero fence_token is treated as stale."""
    result = adapter.route_worktree(
        target=rebase_target,
        intent_payload={"branch": "main"},
        apply_fn=lambda x: x,
        fence_token=0,
    )
    assert not result.ok
    assert "Stale fence" in result.error


# ── Stale-fence negatives: 13E5 ──────────────────────────────────────────────


def test_route_remote_stale_fence_rejected(adapter, push_target):
    """Missing fence_token blocks remote dispatch."""
    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: x,
        fence_token=None,
    )
    assert not result.ok
    assert "Stale fence" in result.error


def test_route_remote_zero_fence_rejected(adapter, push_target):
    """Zero fence_token is treated as stale for remote dispatch."""
    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: x,
        fence_token=0,
    )
    assert not result.ok
    assert "Stale fence" in result.error


# ── Lost-ACK reconciliation: APPLIED ─────────────────────────────────────────


def test_reconciliation_applied_adopts_without_dispatch(adapter, push_target):
    """When reconciliation returns APPLIED, adopt without re-dispatch."""

    def reconciliation_query(provider_key):
        return ReconciliationResult(
            verdict=ReconciliationVerdict.APPLIED,
            provider_idempotency_key=provider_key,
            is_authoritative=True,
            evidence_payload={"ref": "refs/heads/main", "sha": "abc123"},
        )

    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        reconciliation_query=reconciliation_query,
    )
    assert result.ok
    assert result.outcome_kind == OUTCOME_COMPLETED
    assert result.evidence.get("reconciliation") == "applied"


def test_reconciliation_applied_no_protocol_call(adapter, push_target, mock_protocol):
    """APPLIED reconciliation bypasses the protocol entirely."""

    def reconciliation_query(provider_key):
        return ReconciliationResult(
            verdict=ReconciliationVerdict.APPLIED,
            provider_idempotency_key=provider_key,
            is_authoritative=True,
        )

    mock_protocol.reset_mock()
    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        reconciliation_query=reconciliation_query,
    )
    assert result.ok
    # Protocol should NOT have been called for reservation
    mock_protocol.reserve_and_start.assert_not_called()


# ── Lost-ACK reconciliation: NOT_APPLIED ─────────────────────────────────────


def test_reconciliation_not_applied_dispatches(adapter, push_target, mock_protocol):
    """NOT_APPLIED reconciliation authorizes fenced dispatch."""

    def reconciliation_query(provider_key):
        return ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key=provider_key,
            is_authoritative=True,
        )

    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        reconciliation_query=reconciliation_query,
    )
    assert result.ok
    assert result.outcome_kind == OUTCOME_COMPLETED
    assert result.glek != ""
    mock_protocol.reserve_and_start.assert_called_once()


def test_reconciliation_not_applied_non_authoritative_indeterminate(
    adapter, push_target, mock_protocol
):
    """Non-authoritative NOT_APPLIED is treated as indeterminate."""

    def reconciliation_query(provider_key):
        return ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key=provider_key,
            is_authoritative=False,
        )

    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        reconciliation_query=reconciliation_query,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_INDETERMINATE
    assert "Non-authoritative" in result.error


# ── Lost-ACK reconciliation: UNKNOWN ─────────────────────────────────────────


def test_reconciliation_unknown_is_indeterminate(adapter, push_target):
    """UNKNOWN reconciliation keeps the effect indeterminate."""

    def reconciliation_query(provider_key):
        return ReconciliationResult(
            verdict=ReconciliationVerdict.UNKNOWN,
            provider_idempotency_key=provider_key,
        )

    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        reconciliation_query=reconciliation_query,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_INDETERMINATE
    assert "UNKNOWN" in result.error


# ── Lost-ACK reconciliation: query failure ───────────────────────────────────


def test_reconciliation_query_failure_is_indeterminate(adapter, push_target):
    """Query failure in reconciliation result causes indeterminate."""

    def reconciliation_query(provider_key):
        return ReconciliationResult(
            verdict=ReconciliationVerdict.UNKNOWN,
            query_failure=True,
        )

    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        reconciliation_query=reconciliation_query,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_INDETERMINATE
    assert "query failure" in result.error.lower()


def test_reconciliation_query_raises_is_indeterminate(adapter, push_target):
    """If the reconciliation query callable raises, result is indeterminate."""

    def reconciliation_query(provider_key):
        raise QueryFailureError("network timeout")

    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        reconciliation_query=reconciliation_query,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_INDETERMINATE
    assert "Reconciliation query error" in result.error


def test_reconciliation_query_generic_exception_is_indeterminate(
    adapter, push_target
):
    """Any exception from reconciliation query is caught and causes indeterminate."""

    def reconciliation_query(provider_key):
        raise RuntimeError("unexpected failure")

    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        reconciliation_query=reconciliation_query,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_INDETERMINATE
    assert "Reconciliation query error" in result.error


# ── No reconciliation query (direct dispatch) ────────────────────────────────


def test_route_remote_without_reconciliation_dispatches_directly(
    adapter, push_target, mock_protocol
):
    """Without reconciliation_query, dispatch goes through the protocol directly."""
    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
    )
    assert result.ok
    assert result.glek != ""
    assert result.outcome_kind == OUTCOME_COMPLETED
    mock_protocol.reserve_and_start.assert_called_once()


# ── Crash behavior ───────────────────────────────────────────────────────────


def test_protocol_exception_produces_indeterminate_worktree(
    adapter, rebase_target, mock_protocol
):
    """If the protocol raises during worktree dispatch, outcome is INDETERMINATE."""
    mock_protocol.reserve_and_start.side_effect = RuntimeError("DB crashed")

    result = adapter.route_worktree(
        target=rebase_target,
        intent_payload={"branch": "main"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_INDETERMINATE
    assert "Protocol error" in result.error


def test_protocol_exception_produces_indeterminate_remote(
    adapter, push_target, mock_protocol
):
    """If the protocol raises during remote dispatch, outcome is INDETERMINATE."""
    mock_protocol.reserve_and_start.side_effect = RuntimeError("DB crashed")

    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: x,
        fence_token=1,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_INDETERMINATE
    assert "Protocol error" in result.error


def test_apply_fn_exception_produces_failed_worktree(
    adapter, rebase_target, mock_protocol
):
    """If apply_fn raises during worktree dispatch, outcome is FAILED."""

    def failing_apply(payload):
        raise ValueError("rebase conflict")

    result = adapter.route_worktree(
        target=rebase_target,
        intent_payload={"branch": "main"},
        apply_fn=failing_apply,
        fence_token=1,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_FAILED
    assert "rebase conflict" in result.error


def test_apply_fn_exception_produces_failed_remote(
    adapter, push_target, mock_protocol
):
    """If apply_fn raises during remote dispatch, outcome is FAILED."""

    def failing_apply(payload):
        raise ValueError("push rejected: non-fast-forward")

    result = adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=failing_apply,
        fence_token=1,
    )
    assert not result.ok
    assert result.outcome_kind == OUTCOME_FAILED
    assert "non-fast-forward" in result.error


# ── Overflow action-off ──────────────────────────────────────────────────────


def test_route_rejects_shard_not_in_any_tuple(adapter):
    """A completely unknown shard value is rejected by route()."""
    # Use a mock with a non-existent shard
    class FakeShard:
        value = "bisect"

    target = MagicMock()
    target.shard = FakeShard()
    target.target_key = "git:bisect:test"
    target.repository = "test"
    target.enclosing_function = "test_fn"
    target.module = "test.py"

    with pytest.raises((ValueError, TypeError)):
        adapter.route(
            target=target,
            intent_payload={},
            apply_fn=lambda x: x,
        )


# ── GLEK stability ───────────────────────────────────────────────────────────


def test_glek_stable_for_same_worktree_target(adapter, rebase_target):
    """Same worktree target produces same GLEK identity inputs."""
    ei1 = adapter._build_effect_identity(rebase_target)
    ei2 = adapter._build_effect_identity(rebase_target)
    assert ei1.environment_id == ei2.environment_id
    assert ei1.action_target == ei2.action_target
    assert ei1.effect_family == ei2.effect_family


def test_glek_differs_for_different_shards_13e4_13e5(
    adapter, rebase_target, push_target
):
    """Different 13E4/13E5 shards produce different effect identities."""
    ei_rebase = adapter._build_effect_identity(rebase_target)
    ei_push = adapter._build_effect_identity(push_target)
    assert ei_rebase.effect_family != ei_push.effect_family


# ── Provider idempotency key stability ───────────────────────────────────────


def test_provider_key_stable_for_same_inputs(adapter, push_target):
    """The provider idempotency key is stable for the same inputs."""
    # We test this indirectly via the reconciliation query path
    captured_keys = []

    def reconciliation_query(provider_key):
        captured_keys.append(provider_key)
        return ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key=provider_key,
            is_authoritative=True,
        )

    attempt_id = "11111111-1111-1111-1111-111111111111"

    adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        attempt_id=attempt_id,
        reconciliation_query=reconciliation_query,
    )

    adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        attempt_id=attempt_id,
        reconciliation_query=reconciliation_query,
    )

    assert len(captured_keys) == 2
    assert captured_keys[0] == captured_keys[1], (
        "Provider key should be stable for same inputs"
    )


def test_provider_key_differs_for_different_branches(adapter, push_target):
    """Provider key changes when the branch changes."""
    captured_keys = []

    def reconciliation_query(provider_key):
        captured_keys.append(provider_key)
        return ReconciliationResult(
            verdict=ReconciliationVerdict.NOT_APPLIED,
            provider_idempotency_key=provider_key,
            is_authoritative=True,
        )

    attempt_id = "22222222-2222-2222-2222-222222222222"

    adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        attempt_id=attempt_id,
        reconciliation_query=reconciliation_query,
    )

    adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "feature/x", "remote": "origin"},
        apply_fn=lambda x: {"ok": True},
        fence_token=1,
        attempt_id=attempt_id,
        reconciliation_query=reconciliation_query,
    )

    assert len(captured_keys) == 2
    assert captured_keys[0] != captured_keys[1], (
        "Provider key should differ for different branches"
    )


# ── Payload passthrough ──────────────────────────────────────────────────────


def test_route_remote_passes_payload_to_apply_fn(adapter, push_target, mock_protocol):
    """The apply_fn receives the intent_payload augmented with provider key."""
    captured = {}

    def capture_apply(payload):
        captured["received"] = payload
        return {"ok": True}

    adapter.route_remote(
        target=push_target,
        intent_payload={"branch": "main", "remote": "origin", "tags": True},
        apply_fn=capture_apply,
        fence_token=1,
    )
    assert captured["received"]["branch"] == "main"
    assert captured["received"]["remote"] == "origin"
    assert captured["received"]["tags"] is True
    assert "_provider_idempotency_key" in captured["received"]


def test_route_worktree_passes_payload_to_apply_fn(
    adapter, rebase_target, mock_protocol
):
    """The apply_fn receives the intent_payload."""
    captured = {}

    def capture_apply(payload):
        captured["received"] = payload
        return {"ok": True}

    adapter.route_worktree(
        target=rebase_target,
        intent_payload={"branch": "main", "onto": "develop"},
        apply_fn=capture_apply,
        fence_token=1,
    )
    assert captured["received"]["branch"] == "main"
    assert captured["received"]["onto"] == "develop"
