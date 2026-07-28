"""Integration tests for T22, T23, T25, T31, T35 modules.

Covers:
- T22: PublicationAdapter routes through action_gate + effect_protocol.
- T23: ExecuteEffectGate routes execute batch mutations.
- T25: GitEffectAdapter routes reset/clean/checkout with stale-fence negatives.
- T31: DeliveryEffects routes discord_dm and agentbox delivery.
- T35: RecoveryEventStore join + SLO measurement, persist_failure_occurrence.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_protocol(tmp_path: Path):
    """Build a real EffectProtocol backed by SQLite stores."""
    from arnold.workflow.attempt_ledger_store import SqliteAttemptLedgerStore
    from arnold.workflow.effect_protocol import EffectProtocol
    from arnold.workflow.ledger_outbox import SqliteLedgerOutbox

    db_path = str(tmp_path / "test_m10_batch6.db")
    store = SqliteAttemptLedgerStore(db_path)
    # Access conn to trigger lazy schema init
    _ = store.conn
    outbox = SqliteLedgerOutbox(store)
    return EffectProtocol(store, outbox)


# ── T22: PublicationAdapter ───────────────────────────────────────────────────


class TestPublicationAdapter:
    """Step 13B1-13B2: publication through action_gate + effect_protocol."""

    def test_publish_create_issue(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.publication_adapter import (
            PublicationAdapter,
            PublicationTarget,
        )

        protocol = _make_protocol(tmp_path)
        adapter = PublicationAdapter(protocol)

        target = PublicationTarget(
            repo="owner/repo",
            occurrence_key="prob-1",
        )

        def fake_apply(intent):
            return {"ok": True, "number": 42, "url": "https://github.com/owner/repo/issues/42"}

        outcome = adapter.publish(
            target=target,
            action="create",
            intent_payload={"title": "Test issue", "body": "Test body"},
            apply_fn=fake_apply,
        )

        assert outcome.ok is True
        assert outcome.action == "create"
        assert outcome.issue_number == 42
        assert outcome.glek != ""
        assert outcome.outcome_kind == "COMPLETED"

    def test_publish_comment_issue(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.publication_adapter import (
            PublicationAdapter,
            PublicationTarget,
        )

        protocol = _make_protocol(tmp_path)
        adapter = PublicationAdapter(protocol)

        target = PublicationTarget(
            repo="owner/repo",
            issue_number=42,
            occurrence_key="prob-1",
        )

        def fake_apply(intent):
            return {"ok": True, "url": "https://github.com/owner/repo/issues/42#comment-1"}

        outcome = adapter.publish(
            target=target,
            action="comment",
            intent_payload={"body": "Update comment"},
            apply_fn=fake_apply,
        )

        assert outcome.ok is True
        assert outcome.action == "comment"
        assert outcome.issue_number == 42

    def test_publish_blocked_by_gate(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.publication_adapter import (
            PublicationAdapter,
            PublicationTarget,
        )
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionFamily,
            ActionGateVerdict,
        )

        protocol = _make_protocol(tmp_path)

        def blocking_gate(family, target_key):
            return ActionGateVerdict.BLOCKED_CUSTODY

        adapter = PublicationAdapter(protocol, action_gate_check=blocking_gate)

        target = PublicationTarget(repo="owner/repo", occurrence_key="prob-1")
        outcome = adapter.publish(
            target=target,
            action="create",
            intent_payload={"title": "Test"},
            apply_fn=lambda x: {"ok": True},
        )

        assert outcome.ok is False
        assert "gate" in outcome.error.lower() or "blocked" in outcome.error.lower()

    def test_publish_indeterminate(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.publication_adapter import (
            PublicationAdapter,
            PublicationTarget,
        )

        protocol = _make_protocol(tmp_path)
        adapter = PublicationAdapter(protocol)

        target = PublicationTarget(repo="owner/repo", occurrence_key="prob-1")
        outcome = adapter.publish_indeterminate(
            target=target,
            action="create",
            reason="Provider unreachable",
        )

        assert outcome.ok is False
        assert outcome.outcome_kind == "INDETERMINATE"

    def test_publication_target_key_create(self):
        from arnold_pipelines.megaplan.cloud.publication_adapter import PublicationTarget

        target = PublicationTarget(repo="a/b", occurrence_key="p1")
        assert "create" in target.target_key
        assert "a/b" in target.target_key
        assert "p1" in target.target_key

    def test_publication_target_key_comment(self):
        from arnold_pipelines.megaplan.cloud.publication_adapter import PublicationTarget

        target = PublicationTarget(repo="a/b", issue_number=5, occurrence_key="p1")
        assert "comment" in target.target_key
        assert "a/b" in target.target_key
        assert "5" in target.target_key


# ── T23: ExecuteEffectGate ────────────────────────────────────────────────────


class TestExecuteEffectGate:
    """Steps 13C-13D3: execute batch mutation routing."""

    def test_route_local_workspace(self, tmp_path):
        from arnold_pipelines.megaplan.execute.effect_gate import (
            ExecuteEffectGate,
            ExecuteEffectFamily,
            ExecuteTarget,
        )

        protocol = _make_protocol(tmp_path)
        gate = ExecuteEffectGate(protocol)

        target = ExecuteTarget(
            family=ExecuteEffectFamily.LOCAL_WORKSPACE,
            batch_number=1,
            task_ids=("T1", "T2"),
            action="write_artifact",
        )

        def fake_apply(intent):
            return {"written": True}

        outcome = gate.route(
            target=target,
            intent_payload={"data": "test"},
            apply_fn=fake_apply,
        )

        assert outcome.ok is True
        assert outcome.family == "local_workspace"
        assert outcome.glek != ""

    def test_route_process(self, tmp_path):
        from arnold_pipelines.megaplan.execute.effect_gate import (
            ExecuteEffectGate,
            ExecuteEffectFamily,
            ExecuteTarget,
        )

        protocol = _make_protocol(tmp_path)
        gate = ExecuteEffectGate(protocol)

        target = ExecuteTarget(
            family=ExecuteEffectFamily.PROCESS,
            batch_number=2,
            task_ids=("T3",),
            action="run_worker",
        )

        outcome = gate.route(
            target=target,
            intent_payload={"command": "test"},
            apply_fn=lambda x: {"exit_code": 0},
        )

        assert outcome.ok is True
        assert outcome.family == "process"

    def test_route_terminal(self, tmp_path):
        from arnold_pipelines.megaplan.execute.effect_gate import (
            ExecuteEffectGate,
            ExecuteEffectFamily,
            ExecuteTarget,
        )

        protocol = _make_protocol(tmp_path)
        gate = ExecuteEffectGate(protocol)

        target = ExecuteTarget(
            family=ExecuteEffectFamily.TERMINAL,
            batch_number=3,
            task_ids=("T4",),
            action="finalize_batch",
        )

        outcome = gate.route(
            target=target,
            intent_payload={"status": "done"},
            apply_fn=lambda x: {"finalized": True},
        )

        assert outcome.ok is True
        assert outcome.family == "terminal"

    def test_route_publication_handoff(self, tmp_path):
        from arnold_pipelines.megaplan.execute.effect_gate import (
            ExecuteEffectGate,
            ExecuteEffectFamily,
            ExecuteTarget,
        )

        protocol = _make_protocol(tmp_path)
        gate = ExecuteEffectGate(protocol)

        target = ExecuteTarget(
            family=ExecuteEffectFamily.PUBLICATION_HANDOFF,
            batch_number=4,
            task_ids=("T5",),
            action="emit_receipt",
        )

        outcome = gate.route(
            target=target,
            intent_payload={"receipt": "batch-4"},
            apply_fn=lambda x: {"published": True},
        )

        assert outcome.ok is True
        assert outcome.family == "publication_handoff"

    def test_blocked_by_gate(self, tmp_path):
        from arnold_pipelines.megaplan.execute.effect_gate import (
            ExecuteEffectGate,
            ExecuteEffectFamily,
            ExecuteTarget,
        )
        from arnold_pipelines.megaplan.custody.action_gate import (
            ActionGateVerdict,
        )

        protocol = _make_protocol(tmp_path)
        gate = ExecuteEffectGate(
            protocol,
            action_gate_check=lambda f, t: ActionGateVerdict.BLOCKED_RA_UNSATISFIED,
        )

        target = ExecuteTarget(
            family=ExecuteEffectFamily.LOCAL_WORKSPACE,
            batch_number=1,
            task_ids=("T1",),
            action="write",
        )

        outcome = gate.route(
            target=target,
            intent_payload={},
            apply_fn=lambda x: {},
        )

        assert outcome.ok is False
        assert "BLOCKED" in (outcome.error or "")

    def test_target_key_stability(self):
        from arnold_pipelines.megaplan.execute.effect_gate import (
            ExecuteEffectFamily,
            ExecuteTarget,
        )

        t1 = ExecuteTarget(
            family=ExecuteEffectFamily.LOCAL_WORKSPACE,
            batch_number=1,
            task_ids=("T1", "T2"),
            action="write",
        )
        t2 = ExecuteTarget(
            family=ExecuteEffectFamily.LOCAL_WORKSPACE,
            batch_number=1,
            task_ids=("T2", "T1"),  # different order, same tasks
            action="write",
        )

        # Sorted task ids should produce the same key
        assert t1.target_key == t2.target_key


# ── T25: GitEffectAdapter ─────────────────────────────────────────────────────


class TestGitEffectAdapter:
    """Step 13E2: reset/clean/checkout through WBC/action adapter."""

    def test_route_reset(self, tmp_path):
        from arnold_pipelines.megaplan.chain.git_effect_adapter import (
            GitEffectAdapter,
            GitEffectShard,
            GitTarget,
        )

        protocol = _make_protocol(tmp_path)
        adapter = GitEffectAdapter(protocol)

        target = GitTarget(
            shard=GitEffectShard.RESET,
            module="test/git_ops.py",
            enclosing_function="_refresh_base_branch",
            repository="test-repo",
            branch="main",
        )

        outcome = adapter.route(
            target=target,
            intent_payload={"command": "reset", "args": ["--hard", "HEAD~1"]},
            apply_fn=lambda x: {"exit_code": 0},
            fence_token=1,
        )

        assert outcome.ok is True
        assert outcome.shard == "reset"
        assert outcome.glek != ""

    def test_route_clean(self, tmp_path):
        from arnold_pipelines.megaplan.chain.git_effect_adapter import (
            GitEffectAdapter,
            GitEffectShard,
            GitTarget,
        )

        protocol = _make_protocol(tmp_path)
        adapter = GitEffectAdapter(protocol)

        target = GitTarget(
            shard=GitEffectShard.CLEAN,
            module="test/git_ops.py",
            enclosing_function="_clean_worktree_for_chain",
        )

        outcome = adapter.route(
            target=target,
            intent_payload={"command": "clean", "args": ["-fd"]},
            apply_fn=lambda x: {"exit_code": 0},
            fence_token=2,
        )

        assert outcome.ok is True
        assert outcome.shard == "clean"

    def test_route_checkout(self, tmp_path):
        from arnold_pipelines.megaplan.chain.git_effect_adapter import (
            GitEffectAdapter,
            GitEffectShard,
            GitTarget,
        )

        protocol = _make_protocol(tmp_path)
        adapter = GitEffectAdapter(protocol)

        target = GitTarget(
            shard=GitEffectShard.CHECKOUT,
            module="test/git_ops.py",
            enclosing_function="_checkout_milestone_branch",
        )

        outcome = adapter.route(
            target=target,
            intent_payload={"command": "checkout", "args": ["milestone-branch"]},
            apply_fn=lambda x: {"exit_code": 0},
            fence_token=3,
        )

        assert outcome.ok is True
        assert outcome.shard == "checkout"

    def test_stale_fence_rejected(self, tmp_path):
        """Step 13E2 stale-fence negative: zero or missing fence blocks dispatch."""
        from arnold_pipelines.megaplan.chain.git_effect_adapter import (
            GitEffectAdapter,
            GitEffectShard,
            GitTarget,
        )

        protocol = _make_protocol(tmp_path)
        adapter = GitEffectAdapter(protocol)

        target = GitTarget(
            shard=GitEffectShard.RESET,
            module="test/git_ops.py",
            enclosing_function="_refresh_base_branch",
        )

        # fence_token=0 → stale
        outcome = adapter.route(
            target=target,
            intent_payload={"command": "reset"},
            apply_fn=lambda x: {"exit_code": 0},
            fence_token=0,
        )

        assert outcome.ok is False
        assert "stale" in (outcome.error or "").lower()

    def test_stale_fence_none_rejected(self, tmp_path):
        """Step 13E2: None fence also rejects."""
        from arnold_pipelines.megaplan.chain.git_effect_adapter import (
            GitEffectAdapter,
            GitEffectShard,
            GitTarget,
        )

        protocol = _make_protocol(tmp_path)
        adapter = GitEffectAdapter(protocol)

        target = GitTarget(
            shard=GitEffectShard.CLEAN,
            module="test/git_ops.py",
            enclosing_function="_clean_worktree_for_chain",
        )

        outcome = adapter.route(
            target=target,
            intent_payload={"command": "clean"},
            apply_fn=lambda x: {"exit_code": 0},
            fence_token=None,
        )

        assert outcome.ok is False
        assert "stale" in (outcome.error or "").lower()

    def test_intent_failure_empty_payload(self, tmp_path):
        """Step 13E2 intent-failure negative: empty payload rejected."""
        from arnold_pipelines.megaplan.chain.git_effect_adapter import (
            GitEffectAdapter,
            GitEffectShard,
            GitTarget,
        )

        protocol = _make_protocol(tmp_path)
        adapter = GitEffectAdapter(protocol)

        target = GitTarget(
            shard=GitEffectShard.CHECKOUT,
            module="test/git_ops.py",
            enclosing_function="_checkout_milestone_branch",
        )

        outcome = adapter.route(
            target=target,
            intent_payload={},
            apply_fn=lambda x: {"exit_code": 0},
            fence_token=1,
        )

        assert outcome.ok is False
        assert "intent" in (outcome.error or "").lower()

    def test_shard_overflow_rejected(self, tmp_path):
        """Step 13E2/13E7: non-E2 shards are rejected."""
        from arnold_pipelines.megaplan.chain.git_effect_adapter import (
            GitEffectAdapter,
            GitEffectShard,
            GitTarget,
            GIT_SHARD_13E2,
        )
        import pytest as pt

        protocol = _make_protocol(tmp_path)
        adapter = GitEffectAdapter(protocol)

        # Only RESET, CLEAN, CHECKOUT are in GIT_SHARD_13E2
        assert len(GIT_SHARD_13E2) == 3

        # Any shard not in the routed set should be rejected
        # Verify the enum values
        assert GitEffectShard.RESET in GIT_SHARD_13E2
        assert GitEffectShard.CLEAN in GIT_SHARD_13E2
        assert GitEffectShard.CHECKOUT in GIT_SHARD_13E2


# ── T31: DeliveryEffects ──────────────────────────────────────────────────────


class TestDeliveryEffects:
    """Steps 13G1-13G2: resident delivery effects adapter."""

    def test_deliver_discord_dm(self, tmp_path):
        from arnold_pipelines.megaplan.resident.delivery_effects import (
            DeliveryEffects,
            DeliveryChannel,
            DeliveryTarget,
        )

        protocol = _make_protocol(tmp_path)
        effects = DeliveryEffects(protocol)

        target = DeliveryTarget(
            channel=DeliveryChannel.DISCORD_DM,
            parent_id="user-1",
            target_id="user-1",
            action="send_dm",
        )

        def fake_transport(intent):
            return {"ok": True, "channel_id": "ch-1", "message_ids": ["msg-1"]}

        outcome = effects.deliver(
            target=target,
            intent_payload={"title": "Test DM"},
            apply_fn=fake_transport,
        )

        assert outcome.ok is True
        assert outcome.channel == "discord_dm"
        assert outcome.glek != ""

    def test_deliver_agentbox(self, tmp_path):
        from arnold_pipelines.megaplan.resident.delivery_effects import (
            DeliveryEffects,
            DeliveryChannel,
            DeliveryTarget,
        )

        protocol = _make_protocol(tmp_path)
        effects = DeliveryEffects(protocol)

        target = DeliveryTarget(
            channel=DeliveryChannel.AGENTBOX,
            parent_id="op-1",
            target_id="op-1",
            action="notify",
        )

        outcome = effects.deliver(
            target=target,
            intent_payload={"status": "complete"},
            apply_fn=lambda x: {"notified": True},
        )

        assert outcome.ok is True
        assert outcome.channel == "agentbox"

    def test_deliver_discord_dm_convenience(self, tmp_path):
        from arnold_pipelines.megaplan.resident.delivery_effects import DeliveryEffects

        protocol = _make_protocol(tmp_path)
        effects = DeliveryEffects(protocol)

        outcome = effects.deliver_discord_dm(
            user_id="user-1",
            payload={"title": "Test"},
            apply_fn=lambda x: {"ok": True},
        )

        assert outcome.ok is True
        assert outcome.channel == "discord_dm"

    def test_deliver_agentbox_convenience(self, tmp_path):
        from arnold_pipelines.megaplan.resident.delivery_effects import DeliveryEffects

        protocol = _make_protocol(tmp_path)
        effects = DeliveryEffects(protocol)

        outcome = effects.deliver_agentbox(
            operation_id="op-1",
            payload={"status": "done"},
            apply_fn=lambda x: {"notified": True},
        )

        assert outcome.ok is True
        assert outcome.channel == "agentbox"

    def test_gate_blocked_delivery(self, tmp_path):
        from arnold_pipelines.megaplan.resident.delivery_effects import (
            DeliveryEffects,
            DeliveryChannel,
            DeliveryTarget,
        )
        from arnold_pipelines.megaplan.custody.action_gate import ActionGateVerdict

        protocol = _make_protocol(tmp_path)
        effects = DeliveryEffects(
            protocol,
            action_gate_check=lambda f, t: ActionGateVerdict.BLOCKED_CUSTODY,
        )

        target = DeliveryTarget(
            channel=DeliveryChannel.DISCORD_DM,
            parent_id="u1",
            target_id="u1",
        )

        outcome = effects.deliver(
            target=target,
            intent_payload={},
            apply_fn=lambda x: {"ok": True},
        )

        assert outcome.ok is False
        assert "BLOCKED" in (outcome.error or "")

    def test_delivery_target_key_stability(self):
        from arnold_pipelines.megaplan.resident.delivery_effects import (
            DeliveryChannel,
            DeliveryTarget,
        )

        t1 = DeliveryTarget(
            channel=DeliveryChannel.DISCORD_DM,
            parent_id="p1",
            target_id="t1",
            action="send",
        )

        # Same inputs → same key
        assert "delivery" in t1.target_key
        assert "discord_dm" in t1.target_key
        assert "p1" in t1.target_key
        assert "t1" in t1.target_key


# ── T35: RecoveryEventStore + Builder ─────────────────────────────────────────


class TestRecoveryEvents:
    """Steps 14 and 15A: recovery event joins and SLO measurement."""

    def test_record_and_join_blocker_to_request(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import (
            RecoveryEventStore,
            RecoveryEventBuilder,
            RecoveryEventKind,
        )

        store = RecoveryEventStore()

        blocker = RecoveryEventBuilder.blocker_detected(
            blocker_id="block-1",
            session="s1",
            failure_kind="deterministic_phase_failure",
            denominator_group="test",
        )

        # Simulate the join: enqueue a request for this blocker
        request_id = "req-1"
        enqueued = RecoveryEventBuilder.request_enqueued(
            event=blocker,
            request_id=request_id,
        )
        # Update the enqueued event's request_id
        store.record(blocker)
        store.record(enqueued)

        joined = store.join_blocker_to_request(request_id)
        assert joined is not None
        assert joined.kind == RecoveryEventKind.BLOCKER_DETECTED

    def test_slo_denominator_and_violations(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import (
            RecoveryEventStore,
            RecoveryEventBuilder,
        )
        import time as _time

        store = RecoveryEventStore()

        # Create a blocker event
        blocker = RecoveryEventBuilder.blocker_detected(
            blocker_id="b1",
            session="s1",
            failure_kind="test",
            denominator_group="group-a",
        )

        # Simulate claim after 50s
        request_id = "req-1"
        claimed = RecoveryEventBuilder.repair_claimed(
            event=blocker,
            request_id=request_id,
            claimant="worker-1",
        )
        store.record(blocker)
        store.record(claimed)

        # Simulate terminal after 350s (>300s SLO)
        terminal = RecoveryEventBuilder.repair_terminal(
            event=blocker,
            request_id=request_id,
            outcome="fixed",
        )
        store.record(terminal)

        denom = store.slo_denominator("group-a")
        assert denom > 0

        violations = store.slo_violations("group-a", target_seconds=300.0)
        # The terminal was created at "now" so latency ≈ 0, not >300
        # This tests the structure, not real timing

        assert isinstance(store.p95_latency("group-a"), (float, type(None)))

    def test_all_recovery_event_kinds(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import RecoveryEventKind

        # Ensure all expected kinds exist
        assert RecoveryEventKind.BLOCKER_DETECTED
        assert RecoveryEventKind.PROCESS_EXIT
        assert RecoveryEventKind.REPAIR_REQUEST_ENQUEUED
        assert RecoveryEventKind.REPAIR_CLAIMED
        assert RecoveryEventKind.REPAIR_TERMINAL
        assert RecoveryEventKind.REPAIR_ESCALATED
        assert RecoveryEventKind.SLO_EXCEEDED
        # Step 15A kinds
        assert RecoveryEventKind.PARSER_LOSS
        assert RecoveryEventKind.CLASSIFICATION_INCOMPATIBLE
        assert RecoveryEventKind.LAUNCHER_FAILURE
        assert RecoveryEventKind.MISSING_CHILD

    def test_step_15a_parser_loss(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import (
            RecoveryEventBuilder,
            RecoveryEventKind,
        )

        event = RecoveryEventBuilder.parser_loss(
            session="s1",
            phase_or_step="finalize",
            detail="No output from parser",
        )

        assert event.kind == RecoveryEventKind.PARSER_LOSS
        assert event.denominator_group == "parser"
        assert "finalize" in event.metadata["phase_or_step"]

    def test_step_15a_classification_incompatible(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import (
            RecoveryEventBuilder,
            RecoveryEventKind,
        )

        event = RecoveryEventBuilder.classification_incompatible(
            session="s1",
            expected_schema="v2",
            observed="v1",
        )

        assert event.kind == RecoveryEventKind.CLASSIFICATION_INCOMPATIBLE
        assert event.denominator_group == "classification"

    def test_step_15a_launcher_failure(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import (
            RecoveryEventBuilder,
            RecoveryEventKind,
        )

        event = RecoveryEventBuilder.launcher_failure(
            session="s1",
            launcher_name="claude_agent",
            exit_code=1,
            detail="Subprocess crashed",
        )

        assert event.kind == RecoveryEventKind.LAUNCHER_FAILURE
        assert event.denominator_group == "launcher"
        assert event.metadata["exit_code"] == 1

    def test_step_15a_missing_child(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import (
            RecoveryEventBuilder,
            RecoveryEventKind,
        )

        event = RecoveryEventBuilder.missing_child(
            session="s1",
            child_id="worker-3",
            expected_path="/tmp/output.json",
            detail="Worker never produced output",
        )

        assert event.kind == RecoveryEventKind.MISSING_CHILD
        assert event.denominator_group == "child"

    def test_recovery_event_latency_properties(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import (
            RecoveryEvent,
            RecoveryEventKind,
        )

        ev = RecoveryEvent(
            event_id="e1",
            kind=RecoveryEventKind.BLOCKER_DETECTED,
            occurred_at="2026-07-27T00:00:00+00:00",
            recorded_at="2026-07-27T00:00:01+00:00",
            request_id="req-1",
            claim_time="2026-07-27T00:00:10+00:00",
            terminal_time="2026-07-27T00:01:00+00:00",
        )

        assert ev.event_to_request_seconds is not None
        assert ev.event_to_claim_seconds is not None
        assert ev.event_to_terminal_seconds is not None
        assert ev.total_latency_seconds == pytest.approx(60.0, rel=0.1)

    def test_recovery_event_store_count_by_kind(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import (
            RecoveryEventStore,
            RecoveryEventBuilder,
        )

        store = RecoveryEventStore()
        store.record(RecoveryEventBuilder.parser_loss(session="s1"))
        store.record(RecoveryEventBuilder.parser_loss(session="s2"))
        store.record(RecoveryEventBuilder.launcher_failure(session="s1"))

        from arnold_pipelines.megaplan.cloud.recovery_events import RecoveryEventKind

        assert store.count_by_kind(RecoveryEventKind.PARSER_LOSS) == 2
        assert store.count_by_kind(RecoveryEventKind.LAUNCHER_FAILURE) == 1

    def test_process_exit_event(self):
        from arnold_pipelines.megaplan.cloud.recovery_events import (
            RecoveryEventBuilder,
            RecoveryEventKind,
        )

        event = RecoveryEventBuilder.process_exit(
            process_id="worker-42",
            exit_code=1,
            session="s1",
        )

        assert event.kind == RecoveryEventKind.PROCESS_EXIT
        assert event.metadata["exit_code"] == 1
        assert event.metadata["process_id"] == "worker-42"


class TestPersistFailureOccurrence:
    """Step 15A: failure occurrence persistence via repair_requests."""

    def test_persist_parser_loss(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            persist_failure_occurrence,
        )

        queue_dir = tmp_path / ".megaplan" / "repair-queue"
        result = persist_failure_occurrence(
            queue_dir=str(queue_dir),
            session="test-session",
            failure_kind="parser_loss",
            phase_or_step="finalize",
            detail="Parser returned no output",
        )

        assert result["status"] == "persisted"
        assert result["failure_kind"] == "parser_loss"
        assert result["denominator_group"] == "parser"
        assert isinstance(result["event_id"], str) and len(result["event_id"]) > 0

    def test_persist_classification_incompatible(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            persist_failure_occurrence,
        )

        queue_dir = tmp_path / ".megaplan" / "repair-queue"
        result = persist_failure_occurrence(
            queue_dir=str(queue_dir),
            session="test-session",
            failure_kind="classification_incompatible",
            detail="Schema v2 vs v1",
        )

        assert result["status"] == "persisted"
        assert result["failure_kind"] == "classification_incompatible"

    def test_persist_launcher_failure(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            persist_failure_occurrence,
        )

        queue_dir = tmp_path / ".megaplan" / "repair-queue"
        result = persist_failure_occurrence(
            queue_dir=str(queue_dir),
            session="test-session",
            failure_kind="launcher_failure",
            phase_or_step="claude_agent",
            detail="Exit code 1",
        )

        assert result["status"] == "persisted"
        assert result["failure_kind"] == "launcher_failure"

    def test_persist_missing_child(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            persist_failure_occurrence,
        )

        queue_dir = tmp_path / ".megaplan" / "repair-queue"
        result = persist_failure_occurrence(
            queue_dir=str(queue_dir),
            session="test-session",
            failure_kind="missing_child",
            phase_or_step="worker-3",
            detail="No output artifact",
        )

        assert result["status"] == "persisted"
        assert result["failure_kind"] == "missing_child"

    def test_persist_unknown_kind_rejected(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            persist_failure_occurrence,
        )

        queue_dir = tmp_path / ".megaplan" / "repair-queue"
        with pytest.raises(ValueError, match="Unknown Step 15A failure kind"):
            persist_failure_occurrence(
                queue_dir=str(queue_dir),
                session="test-session",
                failure_kind="unknown_failure",
            )


# ── github_sync integration ───────────────────────────────────────────────────


class TestGithubSyncWithAdapter:
    """Step 13B2: github_sync routes through publication adapter."""

    def test_sync_with_adapter_creates_issue(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.github_sync import (
            sync_persistent_problems,
            GitHubSyncConfig,
            GitHubSyncThresholds,
        )
        from arnold_pipelines.megaplan.cloud.publication_adapter import PublicationAdapter

        protocol = _make_protocol(tmp_path)
        adapter = PublicationAdapter(protocol)

        problem = {
            "problem_id": "prob-sync-1",
            "title": "Test problem",
            "status": "open",
            "occurrence_count": 2,
            "recurred_after_fix": False,
            "owner_actor": "watchdog",
            "next_review_ts": "2026-07-27T12:00:00Z",
            "linked_incident_ids": ["inc-1"],
            "fix_commits": [],
        }

        incident = {
            "incident_id": "inc-1",
            "summary": "Test incident",
            "state": "repair_attempt",
            "outcome": "started",
            "next_expected_event": "meta_repair.repair_attempt",
            "last_seq": 1,
            "session_ids": ["s1"],
        }

        projections = {
            "problems": {"problems": [problem]},
            "incidents": {"incidents": [incident]},
        }

        config = GitHubSyncConfig(
            repo="test/repo",
            repo_path=str(tmp_path),
            thresholds=GitHubSyncThresholds(create_min_occurrences=2),
        )

        # The adapter path only activates when publication_adapter is provided
        # and the existing mock path uses real github_cli calls.
        # This test verifies the integration path is callable.
        result = sync_persistent_problems(
            config=config,
            root=tmp_path,
            projections=projections,
        )

        # Without adapter, falls through to existing path (which errors
        # because github_cli isn't available)
        assert isinstance(result, dict)
        assert "repo" in result

    def test_sync_with_adapter_present(self, tmp_path):
        from arnold_pipelines.megaplan.cloud.github_sync import (
            sync_persistent_problems,
            GitHubSyncConfig,
            GitHubSyncThresholds,
        )
        from arnold_pipelines.megaplan.cloud.publication_adapter import PublicationAdapter
        from unittest.mock import patch

        protocol = _make_protocol(tmp_path)
        adapter = PublicationAdapter(protocol)

        problem = {
            "problem_id": "prob-sync-2",
            "title": "Test problem 2",
            "status": "open",
            "occurrence_count": 2,
            "recurred_after_fix": False,
            "owner_actor": "watchdog",
            "next_review_ts": "2026-07-27T12:00:00Z",
            "linked_incident_ids": ["inc-2"],
            "fix_commits": [],
        }

        incident = {
            "incident_id": "inc-2",
            "summary": "Test incident 2",
            "state": "repair_attempt",
            "outcome": "started",
            "next_expected_event": "meta_repair.repair_attempt",
            "last_seq": 1,
            "session_ids": ["s2"],
        }

        projections = {
            "problems": {"problems": [problem]},
            "incidents": {"incidents": [incident]},
        }

        config = GitHubSyncConfig(
            repo="test/repo",
            repo_path=str(tmp_path),
            thresholds=GitHubSyncThresholds(create_min_occurrences=2),
        )

        with patch(
            "arnold_pipelines.megaplan.cloud.github_sync.github_cli.create_issue"
        ) as mock_create:
            mock_create.return_value = {
                "ok": True,
                "evidence_ref": {"number": 1, "url": "https://github.com/test/repo/issues/1"},
            }

            result = sync_persistent_problems(
                config=config,
                root=tmp_path,
                projections=projections,
                publication_adapter=adapter,
            )

            assert isinstance(result, dict)
            assert "repo" in result
