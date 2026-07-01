"""Producer-hook tests: lifecycle-failure and human-gate repair-request enqueuing.

Covers:
- Lifecycle marker content
- Duplicate coalescing
- Lifecycle enqueue failure non-fatal behavior
- HumanGateStep halt/pause enqueuing
- HumanGateStep non-halt no-op behavior
- Missing hook_extensions no-op behavior
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from arnold.pipeline.types import StepContext as NeutralStepContext
from arnold.pipeline.steps.human_gate import HumanGateStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hook_extensions(
    *,
    plan_dir: str = "/tmp/test-plan",
    workspace_path: str = "/tmp/test-workspace",
    session: str = "test-session-001",
    **extra: str,
) -> dict[str, str]:
    base = {
        "plan_dir": plan_dir,
        "workspace_path": workspace_path,
        "session": session,
        "chain_session": session,
        "run_kind": "plan",
        "plan_name": "test-plan",
    }
    base.update(extra)
    return base


def _make_ctx(
    artifact_root: str = "/tmp/artifact-root",
    hook_extensions: dict[str, str] | None = None,
) -> NeutralStepContext:
    return NeutralStepContext(
        artifact_root=artifact_root,
        state={},
        hook_extensions=hook_extensions or {},
    )


def _read_requests(marker_dir: Path) -> list[dict]:
    """Read all queued repair requests from the marker-dir-adjacent queue."""
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        iter_repair_requests,
        repair_queue_dir,
    )

    queue_dir = repair_queue_dir(marker_dir)
    if not queue_dir.exists():
        return []
    return iter_repair_requests(marker_dir)


def _read_decisions(marker_dir: Path) -> list[dict]:
    """Read all decision records from the queue."""
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        decisions_dir,
        repair_queue_dir,
    )

    dec_dir = decisions_dir(repair_queue_dir(marker_dir))
    if not dec_dir.exists():
        return []
    records: list[dict] = []
    for path in sorted(dec_dir.glob("*.json"), key=lambda p: p.name):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass
    return records


# ---------------------------------------------------------------------------
# Lifecycle failure producer-hook tests
# ---------------------------------------------------------------------------


class TestLifecycleFailureEnqueue:
    """Tests for the _enqueue_lifecycle_failure_request hook in auto.py."""

    def test_lifecycle_marker_content(self, tmp_path: Path) -> None:
        """Enqueued request carries correct source, signature fields, and
        redacted hint hash — no raw failure text stored."""
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        # Create a state.json so _workspace_path_for_plan_dir resolution works
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            kind="stall_detected",
            message="Driver stalled after 5 iterations",
            current_state="blocked",
            phase="execute",
            suggested_action="manual_review",
            metadata={"blocked_task_id": "T1"},
        )

        requests = list(iter_repair_requests(plan_dir))
        assert len(requests) == 1
        req = requests[0]

        # Source is lifecycle_failure
        assert req["source"] == "lifecycle_failure"

        # Signature contains the right kind/state/phase info
        sig = req["problem_signature"]
        assert sig["failure_kind"] == "stall_detected"
        assert sig["current_state"] == "blocked"
        assert sig["phase_or_step"] == "execute"
        assert sig["gate_recommendation"] == "manual_review"
        assert sig["blocked_task_id"] == "T1"

        # No raw failure text
        assert "Driver stalled" not in json.dumps(req)
        assert "root_cause_hint_hash" in req
        assert "root_cause_hint_hash_algorithm" in req

        # Target carries plan identity
        target = req["target"]
        assert target["plan_dir"] == str(plan_dir)
        assert "workspace_path" in target

    def test_duplicate_lifecycle_failure_coalesces(self, tmp_path: Path) -> None:
        """Same failure kind+state+plan_dir submitted twice coalesces into
        a single request with a coalesced decision for the second."""
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            kind="stall_detected",
            message="First stall",
            current_state="blocked",
            phase="execute",
            suggested_action="manual_review",
            metadata={"blocked_task_id": "T1"},
        )

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            kind="stall_detected",
            message="Second stall — same signature",
            current_state="blocked",
            phase="execute",
            suggested_action="manual_review",
            metadata={"blocked_task_id": "T1"},
        )

        requests = list(iter_repair_requests(plan_dir))
        assert len(requests) == 1

        # The decision for the second should be "coalesced"
        decisions = _read_decisions(plan_dir)
        coalesced_decisions = [d for d in decisions if d.get("decision") == "coalesced"]
        assert len(coalesced_decisions) >= 1

    def test_different_lifecycle_failure_kinds_produce_separate_requests(
        self, tmp_path: Path
    ) -> None:
        """Different failure kinds produce separate requests (no coalescing)."""
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            kind="stall_detected",
            message="Driver stalled",
            current_state="blocked",
            phase="execute",
            suggested_action="",
            metadata={"blocked_task_id": "T1"},
        )

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            kind="iteration_cap",
            message="Hit iteration limit",
            current_state="blocked",
            phase="execute",
            suggested_action="",
            metadata={"blocked_task_id": "T2"},
        )

        requests = list(iter_repair_requests(plan_dir))
        assert len(requests) == 2

    def test_enqueue_failure_is_non_fatal(self, tmp_path: Path) -> None:
        """When enqueue_repair_request itself raises, the lifecycle failure
        recording path still completes — the exception is caught and warned."""
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        # Simulate enqueue blowing up
        with patch(
            "arnold_pipelines.megaplan.cloud.repair_requests.enqueue_repair_request",
            side_effect=RuntimeError("disk full"),
        ):
            # Should not raise — exception is caught inside the function
            _enqueue_lifecycle_failure_request(
                plan_dir=plan_dir,
                kind="stall_detected",
                message="Driver stalled",
                current_state="blocked",
                phase="execute",
                suggested_action="",
                metadata={},
            )

        # The function completed without propagating the exception
        # No request was written (enqueue failed), and that's OK
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        requests = list(iter_repair_requests(plan_dir))
        assert len(requests) == 0

    def test_feature_flag_off_suppresses_enqueue(self, tmp_path: Path) -> None:
        """When repair_request_queue_enabled() returns False, no request is written."""
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        with patch(
            "arnold_pipelines.megaplan.cloud.feature_flags.repair_request_queue_enabled",
            return_value=False,
        ):
            _enqueue_lifecycle_failure_request(
                plan_dir=plan_dir,
                kind="stall_detected",
                message="Driver stalled",
                current_state="blocked",
                phase="execute",
                suggested_action="",
                metadata={},
            )

        requests = list(iter_repair_requests(plan_dir))
        assert len(requests) == 0


# ---------------------------------------------------------------------------
# HumanGateStep producer-hook tests
# ---------------------------------------------------------------------------


class TestHumanGateEnqueue:
    """Tests for the _enqueue_human_gate_repair_request hook in human_gate.py."""

    def test_halt_path_enqueues_repair_request(self, tmp_path: Path) -> None:
        """On halt (no resume choice), HumanGateStep enqueues a human_gate
        repair request with proper marker content."""
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        markers = tmp_path / "plan-markers"
        markers.mkdir()

        hook_ext = _make_hook_extensions(plan_dir=str(markers))

        step = HumanGateStep(
            name="human_gate",
            kind="decide",
            _artifact_stage="review",
            _choices=["approve", "reject"],
            _pipeline_name="demo_judges",
            _pipeline_version=1,
            _prompt="Please review the artifact",
            _resume_choice=None,
        )

        ctx = _make_ctx(
            artifact_root=str(tmp_path / "artifacts"),
            hook_extensions=hook_ext,
        )
        # Ensure artifact root exists
        Path(ctx.artifact_root).mkdir(parents=True, exist_ok=True)

        result = step.run(ctx)

        # The step should halt
        assert result.next == "halt"

        # A repair request should have been enqueued
        requests = list(iter_repair_requests(markers))
        assert len(requests) == 1
        req = requests[0]

        assert req["source"] == "human_gate"
        sig = req["problem_signature"]
        assert sig["failure_kind"] == "human_gate"
        assert sig["current_state"] == "demo_judges"
        assert sig["phase_or_step"] == "review"
        assert sig["milestone_or_plan"] == "human_gate"

        target = req["target"]
        assert target["plan_dir"] == str(markers)
        assert target["workspace_path"] == "/tmp/test-workspace"
        assert target["pipeline_name"] == "demo_judges"

    def test_resume_path_does_not_enqueue(self, tmp_path: Path) -> None:
        """On resume (valid _resume_choice), no repair request is enqueued."""
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        markers = tmp_path / "plan-markers"
        markers.mkdir()
        hook_ext = _make_hook_extensions(plan_dir=str(markers))

        step = HumanGateStep(
            name="human_gate",
            kind="decide",
            _artifact_stage="review",
            _choices=["approve", "reject"],
            _pipeline_name="demo_judges",
            _pipeline_version=1,
            _resume_choice="approve",
        )

        ctx = _make_ctx(
            artifact_root=str(tmp_path / "artifacts"),
            hook_extensions=hook_ext,
        )
        Path(ctx.artifact_root).mkdir(parents=True, exist_ok=True)

        result = step.run(ctx)

        # The step should proceed (not halt)
        assert result.next == "approve"

        # No repair request should have been enqueued
        requests = list(iter_repair_requests(markers))
        assert len(requests) == 0

    def test_missing_hook_extensions_no_op(self, tmp_path: Path) -> None:
        """When hook_extensions is missing plan_dir/workspace_path/session,
        no enqueue occurs and the step still halts normally."""
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
            repair_queue_dir,
        )

        markers = tmp_path / "plan-markers"
        markers.mkdir()

        # hook_extensions with no plan_dir, workspace_path, or session
        step = HumanGateStep(
            name="human_gate",
            kind="decide",
            _artifact_stage="review",
            _choices=["approve", "reject"],
            _pipeline_name="demo_judges",
            _pipeline_version=1,
            _resume_choice=None,
        )

        ctx = _make_ctx(
            artifact_root=str(tmp_path / "artifacts"),
            hook_extensions={},  # empty — no plan_dir/workspace/session
        )
        Path(ctx.artifact_root).mkdir(parents=True, exist_ok=True)

        result = step.run(ctx)

        # The step should still halt normally
        assert result.next == "halt"

        # No queue was created because hook_extensions were missing required keys
        queue_dir = repair_queue_dir(markers)
        req_dir = queue_dir / "requests"
        assert not req_dir.exists() or len(list(req_dir.glob("*.json"))) == 0

    def test_missing_workspace_path_no_op(self, tmp_path: Path) -> None:
        """When hook_extensions has plan_dir and session but no workspace_path,
        enqueue is skipped."""
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
            repair_queue_dir,
        )

        markers = tmp_path / "plan-markers"
        markers.mkdir()

        # Missing workspace_path
        hook_ext = {
            "plan_dir": str(markers),
            "session": "test-session",
            "chain_session": "test-session",
        }

        step = HumanGateStep(
            name="human_gate",
            kind="decide",
            _artifact_stage="review",
            _choices=["approve"],
            _pipeline_name="demo_judges",
            _pipeline_version=1,
            _resume_choice=None,
        )

        ctx = _make_ctx(
            artifact_root=str(tmp_path / "artifacts"),
            hook_extensions=hook_ext,
        )
        Path(ctx.artifact_root).mkdir(parents=True, exist_ok=True)

        result = step.run(ctx)
        assert result.next == "halt"

        queue_dir = repair_queue_dir(markers)
        req_dir = queue_dir / "requests"
        assert not req_dir.exists() or len(list(req_dir.glob("*.json"))) == 0

    def test_missing_session_no_op(self, tmp_path: Path) -> None:
        """When hook_extensions has plan_dir and workspace but no session,
        enqueue is skipped."""
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
            repair_queue_dir,
        )

        markers = tmp_path / "plan-markers"
        markers.mkdir()

        # Missing session
        hook_ext = {
            "plan_dir": str(markers),
            "workspace_path": "/tmp/ws",
        }

        step = HumanGateStep(
            name="human_gate",
            kind="decide",
            _artifact_stage="review",
            _choices=["approve"],
            _pipeline_name="demo_judges",
            _pipeline_version=1,
            _resume_choice=None,
        )

        ctx = _make_ctx(
            artifact_root=str(tmp_path / "artifacts"),
            hook_extensions=hook_ext,
        )
        Path(ctx.artifact_root).mkdir(parents=True, exist_ok=True)

        result = step.run(ctx)
        assert result.next == "halt"

        queue_dir = repair_queue_dir(markers)
        req_dir = queue_dir / "requests"
        assert not req_dir.exists() or len(list(req_dir.glob("*.json"))) == 0

    def test_human_gate_feature_flag_off_suppresses_enqueue(self, tmp_path: Path) -> None:
        """When repair_request_queue_enabled() returns False, HumanGateStep
        still halts but does not enqueue."""
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        markers = tmp_path / "plan-markers"
        markers.mkdir()
        hook_ext = _make_hook_extensions(plan_dir=str(markers))

        step = HumanGateStep(
            name="human_gate",
            kind="decide",
            _artifact_stage="review",
            _choices=["approve", "reject"],
            _pipeline_name="demo_judges",
            _pipeline_version=1,
            _resume_choice=None,
        )

        ctx = _make_ctx(
            artifact_root=str(tmp_path / "artifacts"),
            hook_extensions=hook_ext,
        )
        Path(ctx.artifact_root).mkdir(parents=True, exist_ok=True)

        with patch(
            "arnold_pipelines.megaplan.cloud.feature_flags.repair_request_queue_enabled",
            return_value=False,
        ):
            result = step.run(ctx)

        # The step still halts normally
        assert result.next == "halt"

        # No repair request enqueued
        requests = list(iter_repair_requests(markers))
        assert len(requests) == 0

    def test_human_gate_enqueue_failure_non_fatal(self, tmp_path: Path) -> None:
        """If enqueue raises inside HumanGateStep, the step still halts
        normally — enqueue failure is a logged warning only."""
        markers = tmp_path / "plan-markers"
        markers.mkdir()
        hook_ext = _make_hook_extensions(plan_dir=str(markers))

        step = HumanGateStep(
            name="human_gate",
            kind="decide",
            _artifact_stage="review",
            _choices=["approve", "reject"],
            _pipeline_name="demo_judges",
            _pipeline_version=1,
            _resume_choice=None,
        )

        ctx = _make_ctx(
            artifact_root=str(tmp_path / "artifacts"),
            hook_extensions=hook_ext,
        )
        Path(ctx.artifact_root).mkdir(parents=True, exist_ok=True)

        with patch(
            "arnold_pipelines.megaplan.cloud.repair_requests.enqueue_repair_request",
            side_effect=RuntimeError("disk full"),
        ):
            result = step.run(ctx)

        # The step still halts — enqueue failure is non-fatal
        assert result.next == "halt"
        assert result.state_patch.get("_pipeline_paused") is True

    def test_duplicate_human_gate_enqueue_coalesces(self, tmp_path: Path) -> None:
        """Two sequential human-gate halts with the same pipeline/step/session
        coalesce into a single request."""
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        markers = tmp_path / "plan-markers"
        markers.mkdir()
        hook_ext = _make_hook_extensions(plan_dir=str(markers))

        # First halt
        step1 = HumanGateStep(
            name="human_gate",
            kind="decide",
            _artifact_stage="review",
            _choices=["approve", "reject"],
            _pipeline_name="demo_judges",
            _pipeline_version=1,
            _resume_choice=None,
        )
        ctx1 = _make_ctx(
            artifact_root=str(tmp_path / "artifacts1"),
            hook_extensions=hook_ext,
        )
        Path(ctx1.artifact_root).mkdir(parents=True, exist_ok=True)
        result1 = step1.run(ctx1)
        assert result1.next == "halt"

        # Second halt (same session, same signature — but different step instance)
        step2 = HumanGateStep(
            name="human_gate",
            kind="decide",
            _artifact_stage="review",
            _choices=["approve", "reject"],
            _pipeline_name="demo_judges",
            _pipeline_version=1,
            _resume_choice=None,
        )
        ctx2 = _make_ctx(
            artifact_root=str(tmp_path / "artifacts2"),
            hook_extensions=hook_ext,
        )
        Path(ctx2.artifact_root).mkdir(parents=True, exist_ok=True)
        result2 = step2.run(ctx2)
        assert result2.next == "halt"

        # Only one unique request should exist
        requests = list(iter_repair_requests(markers))
        assert len(requests) == 1

        # A coalesced decision should exist
        decisions = _read_decisions(markers)
        coalesced = [d for d in decisions if d.get("decision") == "coalesced"]
        assert len(coalesced) >= 1
