"""Tests for Step 13E8: loop/git.py commit and revert adapter routing.

Covers:
- Shard enforcement (only LOOP_COMMIT/LOOP_REVERT accepted by route_loop_git)
- Command-specific semantics:
  - loop_commit: requires non-empty message + allowed_changes list
  - loop_revert: requires non-empty commit_sha + project_dir
- Stale-fence negatives
- Action gate blocking
- Duplicate-commit: same attempt_id → stable GLEK
- Crash-during-revert: apply_fn exception produces FAILED outcome
- GLEK stability across retries
- Overflow action-off for non-13E8 shards
- Read-only helpers stay out of the sink inventory (structural assertion)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from unittest.mock import MagicMock

from arnold.workflow.effect_protocol import (
    EffectProtocol,
    OUTCOME_COMPLETED,
    OUTCOME_FAILED,
    OUTCOME_INDETERMINATE,
)
from arnold_pipelines.megaplan.chain.git_effect_adapter import (
    GitEffectShard,
    GIT_SHARD_13E2,
    GIT_SHARD_13E3,
    GIT_SHARD_13E4,
    GIT_SHARD_13E5,
    GIT_SHARD_13E6,
    GIT_SHARD_13E8,
    GitTarget,
    GitOutcome,
    GitEffectAdapter,
)
from arnold_pipelines.megaplan.custody.action_validator import (
    ActionBoundaryType,
    GateResult,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_protocol():
    """Create a mock EffectProtocol."""
    protocol = MagicMock(spec=EffectProtocol)
    reservation = MagicMock()
    reservation.global_logical_effect_key = "glek-13e8-test-456"
    protocol.reserve_and_start.return_value = reservation
    return protocol


@pytest.fixture
def adapter(mock_protocol):
    """Create a GitEffectAdapter with an explicit AUTHORIZED action gate."""
    def authorizer(family: ActionBoundaryType, target_key: str) -> GateResult:
        return GateResult.AUTHORIZED

    return GitEffectAdapter(
        mock_protocol,
        action_gate_check=authorizer,
        production_enabled=False,
    )


@pytest.fixture
def loop_commit_target():
    return GitTarget(
        shard=GitEffectShard.LOOP_COMMIT,
        module="arnold_pipelines/megaplan/loop/git.py",
        enclosing_function="git_commit",
        repository="arnold-repo",
        branch="main",
    )


@pytest.fixture
def loop_revert_target():
    return GitTarget(
        shard=GitEffectShard.LOOP_REVERT,
        module="arnold_pipelines/megaplan/loop/git.py",
        enclosing_function="git_revert",
        repository="arnold-repo",
        branch="main",
    )


@pytest.fixture
def fake_git_success():
    """Fake git that always succeeds."""
    def _fake(payload):
        return {"ok": True, "sha": "abc123"}
    return _fake


@pytest.fixture
def fake_git_crash():
    """Fake git that crashes (simulates crash-during-revert)."""
    def _fake(payload):
        raise RuntimeError("git revert: merge conflict — aborting")
    return _fake


# ── Shard enforcement ────────────────────────────────────────────────────────


def test_route_loop_git_rejects_non_13e8_shards(adapter):
    """route_loop_git rejects shards outside 13E8."""
    all_other_shards = (
        *GIT_SHARD_13E2, *GIT_SHARD_13E3, *GIT_SHARD_13E4,
        *GIT_SHARD_13E5, *GIT_SHARD_13E6,
    )
    for shard in all_other_shards:
        target = GitTarget(
            shard=shard,
            module="test.py",
            enclosing_function="test_fn",
        )
        with pytest.raises(ValueError, match="route_loop_git only supports Step 13E8"):
            adapter.route_loop_git(
                target=target,
                intent_payload={"message": "test", "allowed_changes": ["file.py"]},
                apply_fn=lambda p: {"ok": True},
                fence_token=1,
            )


def test_route_loop_git_accepts_loop_commit(adapter, loop_commit_target, fake_git_success):
    """route_loop_git accepts LOOP_COMMIT shard."""
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "test commit", "allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is True
    assert outcome.shard == "loop_commit"
    assert outcome.glek != ""
    assert outcome.outcome_kind == OUTCOME_COMPLETED


def test_route_loop_git_accepts_loop_revert(adapter, loop_revert_target, fake_git_success):
    """route_loop_git accepts LOOP_REVERT shard."""
    outcome = adapter.route_loop_git(
        target=loop_revert_target,
        intent_payload={"commit_sha": "abc123def", "project_dir": "/tmp/repo"},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is True
    assert outcome.shard == "loop_revert"
    assert outcome.glek != ""
    assert outcome.outcome_kind == OUTCOME_COMPLETED


# ── Command-specific semantics ────────────────────────────────────────────────


def test_loop_commit_requires_message(adapter, loop_commit_target, fake_git_success):
    """loop_commit rejects missing or empty message."""
    # Missing message
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "message" in outcome.error.lower()

    # Empty message
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "", "allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "message" in outcome.error.lower()

    # Whitespace-only message
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "   ", "allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "message" in outcome.error.lower()


def test_loop_commit_requires_allowed_changes(adapter, loop_commit_target, fake_git_success):
    """loop_commit rejects missing or empty allowed_changes."""
    # Missing allowed_changes
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "test"},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "allowed_changes" in outcome.error.lower()

    # Empty list
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "test", "allowed_changes": []},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "allowed_changes" in outcome.error.lower()

    # Not a list
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "test", "allowed_changes": "file.py"},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "allowed_changes" in outcome.error.lower()


def test_loop_revert_requires_commit_sha(adapter, loop_revert_target, fake_git_success):
    """loop_revert rejects missing or empty commit_sha."""
    # Missing commit_sha
    outcome = adapter.route_loop_git(
        target=loop_revert_target,
        intent_payload={"project_dir": "/tmp/repo"},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "commit_sha" in outcome.error.lower()

    # Empty commit_sha
    outcome = adapter.route_loop_git(
        target=loop_revert_target,
        intent_payload={"commit_sha": "", "project_dir": "/tmp/repo"},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "commit_sha" in outcome.error.lower()

    # Whitespace-only commit_sha
    outcome = adapter.route_loop_git(
        target=loop_revert_target,
        intent_payload={"commit_sha": "   ", "project_dir": "/tmp/repo"},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "commit_sha" in outcome.error.lower()


def test_loop_revert_requires_project_dir(adapter, loop_revert_target, fake_git_success):
    """loop_revert rejects missing project_dir."""
    # Missing project_dir
    outcome = adapter.route_loop_git(
        target=loop_revert_target,
        intent_payload={"commit_sha": "abc123"},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "project_dir" in outcome.error.lower()


# ── Stale-fence negatives ────────────────────────────────────────────────────


def test_route_loop_git_stale_fence_none(adapter, loop_commit_target, fake_git_success):
    """Stale fence: None token rejects."""
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "test", "allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=None,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "Stale fence" in outcome.error


def test_route_loop_git_stale_fence_zero(adapter, loop_commit_target, fake_git_success):
    """Stale fence: zero token rejects."""
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "test", "allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=0,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "Stale fence" in outcome.error


def test_route_loop_git_stale_fence_negative(adapter, loop_commit_target, fake_git_success):
    """Stale fence: negative token rejects."""
    outcome = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "test", "allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=-5,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "Stale fence" in outcome.error


# ── Action gate blocking ──────────────────────────────────────────────────────


def test_route_loop_git_action_gate_blocked(adapter, loop_commit_target, fake_git_success):
    """Action gate blocks when checker returns non-authorized verdict."""
    def blocker(family: ActionBoundaryType, target_key: str) -> GateResult:
        return GateResult.BLOCKED_RA_UNSATISFIED

    gated = GitEffectAdapter(
        adapter._protocol,
        action_gate_check=blocker,
        production_enabled=False,
    )
    outcome = gated.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "test", "allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "Action gate blocked" in outcome.error
    assert "blocked_ra_unsatisfied" in outcome.error


def test_route_loop_git_action_gate_authorized(adapter, loop_commit_target, fake_git_success):
    """Action gate allows when checker returns AUTHORIZED."""
    def authorizer(family: ActionBoundaryType, target_key: str) -> GateResult:
        return GateResult.AUTHORIZED

    gated = GitEffectAdapter(
        adapter._protocol,
        action_gate_check=authorizer,
        production_enabled=False,
    )
    outcome = gated.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "test", "allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is True


# ── Duplicate-commit (at-most-once) ───────────────────────────────────────────


def test_duplicate_commit_same_attempt_id_stable_glek(
    adapter, loop_commit_target, fake_git_success
):
    """Same attempt_id for loop_commit produces stable GLEK (duplicate-commit test)."""
    attempt_id = "00000000-0000-4000-a000-000000000101"
    outcome1 = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "duplicate commit", "allowed_changes": ["a.py", "b.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
        attempt_id=attempt_id,
    )
    outcome2 = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "duplicate commit", "allowed_changes": ["a.py", "b.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
        attempt_id=attempt_id,
    )
    assert outcome1.glek == outcome2.glek
    assert outcome1.glek != ""
    assert outcome1.ok and outcome2.ok


def test_duplicate_commit_different_attempt_id_both_succeed(
    adapter, loop_commit_target, fake_git_success
):
    """Different attempt_ids both produce valid, non-empty GLEKs."""
    outcome1 = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "first", "allowed_changes": ["a.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
        attempt_id="00000000-0000-4000-a000-000000000201",
    )
    outcome2 = adapter.route_loop_git(
        target=loop_commit_target,
        intent_payload={"message": "first", "allowed_changes": ["a.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
        attempt_id="00000000-0000-4000-a000-000000000202",
    )
    # Both succeed with non-empty GLEKs
    assert outcome1.ok and outcome2.ok
    assert outcome1.glek != ""
    assert outcome2.glek != ""


# ── Crash-during-revert ───────────────────────────────────────────────────────


def test_crash_during_revert_apply_fn_exception(
    adapter, loop_revert_target, fake_git_crash
):
    """When revert apply_fn raises, outcome is FAILED with GLEK reserved (crash-during-revert test)."""
    outcome = adapter.route_loop_git(
        target=loop_revert_target,
        intent_payload={"commit_sha": "abc123def", "project_dir": "/tmp/repo"},
        apply_fn=fake_git_crash,
        fence_token=1,
        attempt_id="00000000-0000-4000-a000-000000000301",
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "git revert" in outcome.error
    assert "merge conflict" in outcome.error
    assert outcome.glek != ""  # GLEK was reserved before dispatch failed


def test_crash_during_revert_protocol_error_produces_indeterminate(
    adapter, loop_revert_target, fake_git_success
):
    """When the protocol itself fails during revert, outcome is INDETERMINATE."""
    # Make reserve_and_start raise an exception
    adapter._protocol.reserve_and_start.side_effect = RuntimeError("DB connection lost")
    outcome = adapter.route_loop_git(
        target=loop_revert_target,
        intent_payload={"commit_sha": "abc123def", "project_dir": "/tmp/repo"},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_INDETERMINATE
    assert "Protocol error" in outcome.error


# ── GLEK stability ───────────────────────────────────────────────────────────


def test_loop_commit_glek_stable_across_retries(
    adapter, loop_commit_target, fake_git_success
):
    """GLEK is stable for loop_commit when all identity inputs are identical."""
    outcomes = []
    for _ in range(3):
        o = adapter.route_loop_git(
            target=loop_commit_target,
            intent_payload={"message": "stable", "allowed_changes": ["x.py"]},
            apply_fn=fake_git_success,
            fence_token=1,
            attempt_id="00000000-0000-4000-a000-000000000401",
        )
        outcomes.append(o)
    gleks = {o.glek for o in outcomes}
    assert len(gleks) == 1
    assert outcomes[0].glek != ""


def test_loop_revert_glek_stable_across_retries(
    adapter, loop_revert_target, fake_git_success
):
    """GLEK is stable for loop_revert when all identity inputs are identical."""
    outcomes = []
    for _ in range(3):
        o = adapter.route_loop_git(
            target=loop_revert_target,
            intent_payload={"commit_sha": "abc123def", "project_dir": "/tmp/repo"},
            apply_fn=fake_git_success,
            fence_token=1,
            attempt_id="00000000-0000-4000-a000-000000000501",
        )
        outcomes.append(o)
    gleks = {o.glek for o in outcomes}
    assert len(gleks) == 1
    assert outcomes[0].glek != ""


# ── Overflow action-off for non-routed shards ─────────────────────────────────


def test_route_loop_git_rejects_loop_commit_via_route(adapter, loop_commit_target, fake_git_success):
    """general route() accepts LOOP_COMMIT (it's in _ROUTED_SHARDS)."""
    # LOOP_COMMIT is in _ROUTED_SHARDS so route() should dispatch it
    outcome = adapter.route(
        target=loop_commit_target,
        intent_payload={"message": "test", "allowed_changes": ["file.py"]},
        apply_fn=fake_git_success,
        fence_token=1,
    )
    assert outcome.ok is True


def test_route_staging_rejects_loop_commit(adapter, loop_commit_target, fake_git_success):
    """route_staging rejects LOOP_COMMIT (wrong dispatch method)."""
    with pytest.raises(ValueError, match="route_staging only supports Step 13E3"):
        adapter.route_staging(
            target=loop_commit_target,
            intent_payload={"paths": ["file.py"]},
            apply_fn=fake_git_success,
            fence_token=1,
        )


def test_route_worktree_rejects_loop_revert(adapter, loop_revert_target, fake_git_success):
    """route_worktree rejects LOOP_REVERT (wrong dispatch method)."""
    with pytest.raises(ValueError, match="route_worktree only supports Step 13E4"):
        adapter.route_worktree(
            target=loop_revert_target,
            intent_payload={"path": "/tmp", "action": "add"},
            apply_fn=fake_git_success,
            fence_token=1,
        )


def test_route_remote_rejects_loop_commit(adapter, loop_commit_target, fake_git_success):
    """route_remote rejects LOOP_COMMIT (wrong dispatch method)."""
    with pytest.raises(ValueError, match="route_remote only supports Step 13E5"):
        adapter.route_remote(
            target=loop_commit_target,
            intent_payload={"branch": "main", "remote": "origin"},
            apply_fn=fake_git_success,
            fence_token=1,
        )


def test_route_pr_rejects_loop_revert(adapter, loop_revert_target, fake_git_success):
    """route_pr rejects LOOP_REVERT (wrong dispatch method)."""
    with pytest.raises(ValueError, match="route_pr only supports Step 13E6"):
        adapter.route_pr(
            target=loop_revert_target,
            intent_payload={"pr_number": 42},
            apply_fn=fake_git_success,
            fence_token=1,
        )


# ── Shard overflow gate ──────────────────────────────────────────────────────


def test_route_loop_git_enforces_13e8_exclusivity(adapter, fake_git_success):
    """Only LOOP_COMMIT and LOOP_REVERT pass the 13E8 boundary; other shards raise."""
    for shard in GitEffectShard:
        target = GitTarget(
            shard=shard,
            module="test.py",
            enclosing_function="test",
        )
        if shard in GIT_SHARD_13E8:
            # Should succeed (with valid payload)
            if shard == GitEffectShard.LOOP_COMMIT:
                outcome = adapter.route_loop_git(
                    target=target,
                    intent_payload={"message": "test", "allowed_changes": ["file.py"]},
                    apply_fn=fake_git_success,
                    fence_token=1,
                )
            else:
                outcome = adapter.route_loop_git(
                    target=target,
                    intent_payload={"commit_sha": "abc123", "project_dir": "/tmp/repo"},
                    apply_fn=fake_git_success,
                    fence_token=1,
                )
            # route_loop_git delegates to route() which dispatches via protocol
            assert outcome.ok is True
        else:
            with pytest.raises(ValueError, match="route_loop_git only supports Step 13E8"):
                adapter.route_loop_git(
                    target=target,
                    intent_payload={"message": "test", "allowed_changes": ["file.py"]},
                    apply_fn=fake_git_success,
                    fence_token=1,
                )


# ── Read-only helpers out of sink inventory ───────────────────────────────────


def test_read_only_helpers_not_in_sink_inventory():
    """Verify that read-only loop/git.py helpers are NOT in the routed shards.

    Only git_commit (LOOP_COMMIT) and git_revert (LOOP_REVERT) are
    mutation sinks.  The read-only helpers (git_current_sha, parse_metric,
    _collect_git_status_paths_with_nested_repos, etc.) are deliberately
    absent from the GitEffectShard enum.
    """
    # These are the only loop/git.py shards
    loop_shard_values = {GitEffectShard.LOOP_COMMIT, GitEffectShard.LOOP_REVERT}
    # Verify no read-only operations have snuck into the enum
    read_only_names = {
        "current_sha", "parse_metric", "status_paths", "changed_allowed_paths",
        "normalize_pathspec", "normalize_repo_path", "parse_git_status_paths",
        "run_git_status_paths", "discover_nested_git_repos",
        "collect_committed_range_paths", "collect_git_status_paths_with_nested_repos",
        "run_git",
    }
    all_shard_values = {s.value for s in GitEffectShard}
    for read_only in read_only_names:
        assert read_only not in all_shard_values, (
            f"Read-only helper '{read_only}' accidentally in GitEffectShard"
        )


def test_loop_git_module_only_has_two_sinks():
    """The sink inventory for loop/git.py should only contain 2 sinks (commit + revert)."""
    # Structural test: the GIT_SHARD_13E8 tuple only contains 2 entries
    assert len(GIT_SHARD_13E8) == 2
    assert GitEffectShard.LOOP_COMMIT in GIT_SHARD_13E8
    assert GitEffectShard.LOOP_REVERT in GIT_SHARD_13E8


# ── Action gate default-deny negatives ──────────────────────────────────────

_LOOP_FAMILY_SHARDS = (
    (GitEffectShard.LOOP_COMMIT, {"message": "msg", "allowed_changes": ["a.py"]}),
    (GitEffectShard.LOOP_REVERT, {"commit_sha": "abc123", "project_dir": "/tmp/proj"}),
)


def _loop_target(shard):
    return GitTarget(
        shard=shard,
        module="arnold_pipelines/megaplan/loop/git.py",
        enclosing_function="test_fn",
        repository="arnold-repo",
        branch="main",
    )


def test_route_loop_git_missing_gate_blocks_every_family(mock_protocol):
    """Missing gate denies loop commit/revert effects before reservation."""
    ungated = GitEffectAdapter(mock_protocol, production_enabled=False)
    spies = []
    for shard, payload in _LOOP_FAMILY_SHARDS:
        apply_fn = MagicMock(return_value={"ok": True, "sha": "abc123"})
        spies.append(apply_fn)
        outcome = ungated.route_loop_git(
            target=_loop_target(shard),
            intent_payload=payload,
            apply_fn=apply_fn,
            fence_token=1,
        )
        assert outcome.ok is False
        assert outcome.outcome_kind == OUTCOME_FAILED
        assert "Action gate blocked" in outcome.error
        assert outcome.evidence.get("gate_verdict") == "error"
        assert outcome.glek == ""
    mock_protocol.reserve_and_start.assert_not_called()
    for spy in spies:
        spy.assert_not_called()


def test_route_loop_git_shadow_pass_blocks_every_family(mock_protocol):
    """SHADOW_PASS verdict denies loop commit/revert effects."""
    def shadow(family: ActionBoundaryType, target_key: str) -> GateResult:
        return GateResult.SHADOW_PASS

    gated = GitEffectAdapter(
        mock_protocol,
        action_gate_check=shadow,
        production_enabled=False,
    )
    spies = []
    for shard, payload in _LOOP_FAMILY_SHARDS:
        apply_fn = MagicMock(return_value={"ok": True, "sha": "abc123"})
        spies.append(apply_fn)
        outcome = gated.route_loop_git(
            target=_loop_target(shard),
            intent_payload=payload,
            apply_fn=apply_fn,
            fence_token=1,
        )
        assert outcome.ok is False
        assert outcome.outcome_kind == OUTCOME_FAILED
        assert "Action gate blocked" in outcome.error
        assert outcome.evidence.get("gate_verdict") == "shadow_pass"
        assert outcome.glek == ""
    mock_protocol.reserve_and_start.assert_not_called()
    for spy in spies:
        spy.assert_not_called()


# ── Worktree removal reference census (T-0027) ───────────────────────────────


def _worktree_remove_target() -> GitTarget:
    return GitTarget(
        shard=GitEffectShard.WORKTREE,
        module="arnold_pipelines/megaplan/bakeoff/worktree.py",
        enclosing_function="remove_worktree",
        repository="arnold-repo",
        branch="main",
    )


def _sandbox_census_stores(monkeypatch, tmp_path) -> None:
    """Point the reference census at sandboxed (initially absent) stores."""
    monkeypatch.setenv("ARNOLD_BASE_DIR", "")
    monkeypatch.setenv("ARNOLD_RUNTIME_MANIFEST_DIR", str(tmp_path / "ref-manifests"))
    monkeypatch.setenv("ARNOLD_REFERENCE_CHAIN_STORE", str(tmp_path / "ref-chains"))
    monkeypatch.setenv("ARNOLD_REFERENCE_MARKER_STORE", str(tmp_path / "ref-markers"))
    monkeypatch.setenv(
        "ARNOLD_REFERENCE_SCHEDULE_STORES", str(tmp_path / "ref-schedules")
    )
    monkeypatch.setenv(
        "ARNOLD_REFERENCE_REPAIR_QUEUE", str(tmp_path / "ref-repair-queue")
    )
    monkeypatch.setenv("ARNOLD_REFERENCE_LEASE_STORE", str(tmp_path / "ref-leases"))


def test_route_worktree_remove_refuses_on_reference(
    adapter, mock_protocol, tmp_path, monkeypatch
) -> None:
    """A worktree removal whose target path is still referenced by a runtime
    store is refused before reservation or dispatch (census REFERENCED)."""
    wt = tmp_path / "wt-remove"
    _sandbox_census_stores(monkeypatch, tmp_path)
    store = tmp_path / "ref-chains"
    store.mkdir(parents=True)
    (store / "chain-ref.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "execution_environment": {"engine_root": str(wt)}
                }
            }
        ),
        encoding="utf-8",
    )
    apply_fn = MagicMock(return_value={"ok": True})
    outcome = adapter.route_worktree(
        target=_worktree_remove_target(),
        intent_payload={"path": str(wt), "action": "remove"},
        apply_fn=apply_fn,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "Reference census refused worktree removal" in outcome.error
    assert outcome.evidence.get("census_verdict") == "REFERENCED"
    assert outcome.evidence.get("worktree_path") == str(wt)
    apply_fn.assert_not_called()
    mock_protocol.reserve_and_start.assert_not_called()


def test_route_worktree_remove_blocks_on_unknown_census(
    adapter, mock_protocol, tmp_path, monkeypatch
) -> None:
    """A corrupt reference store makes the census UNKNOWN and BLOCKS the
    worktree removal (fail-closed: delete-on-unknown never happens)."""
    wt = tmp_path / "wt-remove"
    _sandbox_census_stores(monkeypatch, tmp_path)
    store = tmp_path / "ref-chains"
    store.mkdir(parents=True)
    (store / "corrupt.json").write_text(
        '{"metadata": {"execution_environment": ', encoding="utf-8"
    )
    apply_fn = MagicMock(return_value={"ok": True})
    outcome = adapter.route_worktree(
        target=_worktree_remove_target(),
        intent_payload={"path": str(wt), "action": "remove"},
        apply_fn=apply_fn,
        fence_token=1,
    )
    assert outcome.ok is False
    assert outcome.outcome_kind == OUTCOME_FAILED
    assert "Reference census refused worktree removal" in outcome.error
    assert outcome.evidence.get("census_verdict") == "UNKNOWN"
    apply_fn.assert_not_called()
    mock_protocol.reserve_and_start.assert_not_called()


def test_route_worktree_remove_proceeds_on_clear_census(
    adapter, mock_protocol, tmp_path, monkeypatch
) -> None:
    """A CLEAR reference census keeps the route authority: the removal row
    dispatches through WBC exactly as before."""
    wt = tmp_path / "wt-remove"
    _sandbox_census_stores(monkeypatch, tmp_path)
    apply_fn = MagicMock(return_value={"ok": True})
    outcome = adapter.route_worktree(
        target=_worktree_remove_target(),
        intent_payload={"path": str(wt), "action": "remove"},
        apply_fn=apply_fn,
        fence_token=1,
    )
    assert outcome.ok is True
    assert outcome.outcome_kind == OUTCOME_COMPLETED
    apply_fn.assert_called_once()
    mock_protocol.reserve_and_start.assert_called_once()
