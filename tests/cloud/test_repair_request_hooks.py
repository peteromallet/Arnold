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
from typing import Any
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
    **extra: Any,
) -> dict[str, Any]:
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        enqueue_human_gate_repair_request,
    )

    base = {
        "plan_dir": plan_dir,
        "workspace_path": workspace_path,
        "repair_queue_root": str(Path(workspace_path) / ".megaplan" / "repair-queue"),
        "session": session,
        "chain_session": session,
        "run_kind": "plan",
        "plan_name": "test-plan",
        "human_gate_repair_request_hook": enqueue_human_gate_repair_request,
    }
    base.update(extra)
    return base


def _make_ctx(
    artifact_root: str = "/tmp/artifact-root",
    hook_extensions: dict[str, Any] | None = None,
) -> NeutralStepContext:
    return NeutralStepContext(
        artifact_root=artifact_root,
        state={},
        hook_extensions=hook_extensions or {},
    )


def _queue_root(workspace: Path) -> Path:
    return workspace / ".megaplan" / "repair-queue"


def _read_requests(queue_root: Path) -> list[dict]:
    """Read all requests from an explicit central queue root."""
    from arnold_pipelines.megaplan.cloud.repair_requests import iter_repair_requests

    if not queue_root.exists():
        return []
    return iter_repair_requests(queue_root)


def _read_decisions(queue_root: Path) -> list[dict]:
    """Read all decision records from the queue."""
    from arnold_pipelines.megaplan.cloud.repair_requests import (
        decisions_dir,
    )

    dec_dir = decisions_dir(queue_root)
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

    def test_managed_lifecycle_route_uses_dispatcher_queue_and_chain_identity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.auto import (
            _enqueue_lifecycle_failure_request,
            _lifecycle_repair_request_route,
        )

        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        plan_dir.mkdir(parents=True)
        queue_root = tmp_path / "managed" / ".megaplan" / "repair-queue"
        marker_dir = tmp_path / "managed" / ".megaplan" / "cloud-sessions"
        monkeypatch.setenv("ARNOLD_REPAIR_QUEUE_ROOT", str(queue_root))
        monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(marker_dir))
        monkeypatch.setenv("ARNOLD_REPAIR_SESSION", "canonical-chain-session")
        monkeypatch.setenv("ARNOLD_REPAIR_RUN_KIND", "chain")

        route = _lifecycle_repair_request_route(plan_dir)

        assert route == (
            queue_root,
            marker_dir,
            "canonical-chain-session",
            "chain",
        )

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            queue_root=route[0],
            marker_dir=route[1],
            session=route[2],
            run_kind=route[3],
            kind="phase_failed",
            message="review finalization failed",
            current_state="executed",
            phase="review",
            suggested_action="retry review",
            metadata={"blocked_task_id": "T19"},
        )
        request = _read_requests(queue_root)[0]
        assert request["session"] == "canonical-chain-session"
        assert request["run_kind"] == "chain"
        assert request["marker_dir"] == str(marker_dir)
        assert request["problem_signature"]["failure_kind"] == "phase_failed"
        assert request["problem_signature"]["blocked_task_id"] == "T19"

    def test_terminal_handler_failure_is_enqueued_without_rewriting_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.auto import _enqueue_terminal_failure_request

        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "blocked-plan"
        plan_dir.mkdir(parents=True)
        state = {
            "current_state": "blocked",
            "latest_failure": {
                "kind": "quality_gate_blocked",
                "message": "deterministic review check failed",
                "phase": "review",
                "suggested_action": "dispatch bounded automatic repair",
                "metadata": {"blocked_task_id": "T24"},
            },
        }
        state_path = plan_dir / "state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        queue_root = tmp_path / "central" / ".megaplan" / "repair-queue"
        marker_dir = tmp_path / "central" / ".megaplan" / "cloud-sessions"
        monkeypatch.setenv("ARNOLD_REPAIR_QUEUE_ROOT", str(queue_root))
        monkeypatch.setenv("ARNOLD_REPAIR_MARKER_DIR", str(marker_dir))
        monkeypatch.setenv("ARNOLD_REPAIR_SESSION", "blocked-chain")
        monkeypatch.setenv("ARNOLD_REPAIR_RUN_KIND", "chain")

        _enqueue_terminal_failure_request(plan_dir)

        request = _read_requests(queue_root)[0]
        assert request["session"] == "blocked-chain"
        assert request["run_kind"] == "chain"
        assert request["problem_signature"]["failure_kind"] == "quality_gate_blocked"
        assert request["problem_signature"]["blocked_task_id"] == "T24"
        assert json.loads(state_path.read_text(encoding="utf-8")) == state

    def test_lifecycle_marker_content(self, tmp_path: Path) -> None:
        """Enqueued request carries correct source, signature fields, and
        redacted hint hash — no raw failure text stored."""
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        # Create a state.json so _workspace_path_for_plan_dir resolution works
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            queue_root=_queue_root(tmp_path),
            kind="stall_detected",
            message="Driver stalled after 5 iterations",
            current_state="blocked",
            phase="execute",
            suggested_action="manual_review",
            metadata={"blocked_task_id": "T1"},
        )

        requests = _read_requests(_queue_root(tmp_path))
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

    def test_phase_contract_lifecycle_request_allocates_identity_before_acceptance(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        from arnold_pipelines.megaplan.cloud.repair_contract import blocker_id_for_fingerprint

        plan_dir = (
            tmp_path
            / ".megaplan"
            / "plans"
            / "m6-exact-contract-and-20260716-1303"
        )
        plan_dir.mkdir(parents=True)
        (plan_dir / "state.json").write_text(
            json.dumps({"current_state": "blocked"}), encoding="utf-8"
        )

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            queue_root=_queue_root(tmp_path),
            session="custody-control-plane-20260714",
            run_kind="chain",
            kind="deterministic_phase_failure",
            message="duplicate worker-local flag IDs and blank evidence",
            current_state="blocked",
            phase="critique",
            suggested_action="repair the deterministic phase contract",
            metadata={"count": 3, "max_attempts": 3},
            retry_strategy="repair_phase_contract",
        )

        request = _read_requests(_queue_root(tmp_path))[0]
        assert request["problem_signature"]["blocked_task_id"] == "phase:critique"
        assert request["target"]["retry_strategy"] == "repair_phase_contract"
        assert request["blocker_id"] == blocker_id_for_fingerprint(
            request["blocker_fingerprint"]
        )
        accepted = [
            decision
            for decision in _read_decisions(_queue_root(tmp_path))
            if decision["decision"] == "accepted"
        ]
        assert [decision["request_id"] for decision in accepted] == [
            request["request_id"]
        ]
    def test_duplicate_lifecycle_failure_coalesces(self, tmp_path: Path) -> None:
        """Same failure kind+state+plan_dir submitted twice coalesces into
        a single request with a coalesced decision for the second."""
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            queue_root=_queue_root(tmp_path),
            kind="stall_detected",
            message="First stall",
            current_state="blocked",
            phase="execute",
            suggested_action="manual_review",
            metadata={"blocked_task_id": "T1"},
        )

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            queue_root=_queue_root(tmp_path),
            kind="stall_detected",
            message="Second stall — same signature",
            current_state="blocked",
            phase="execute",
            suggested_action="manual_review",
            metadata={"blocked_task_id": "T1"},
        )

        requests = _read_requests(_queue_root(tmp_path))
        assert len(requests) == 1

        # The decision for the second should be "coalesced"
        decisions = _read_decisions(_queue_root(tmp_path))
        coalesced_decisions = [d for d in decisions if d.get("decision") == "coalesced"]
        assert len(coalesced_decisions) >= 1

    def test_different_lifecycle_failure_kinds_produce_separate_requests(
        self, tmp_path: Path
    ) -> None:
        """Different failure kinds produce separate requests (no coalescing)."""
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            queue_root=_queue_root(tmp_path),
            kind="stall_detected",
            message="Driver stalled",
            current_state="blocked",
            phase="execute",
            suggested_action="",
            metadata={"blocked_task_id": "T1"},
        )

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            queue_root=_queue_root(tmp_path),
            kind="iteration_cap",
            message="Hit iteration limit",
            current_state="blocked",
            phase="execute",
            suggested_action="",
            metadata={"blocked_task_id": "T2"},
        )

        requests = _read_requests(_queue_root(tmp_path))
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
                queue_root=_queue_root(tmp_path),
                kind="stall_detected",
                message="Driver stalled",
                current_state="blocked",
                phase="execute",
                suggested_action="",
                metadata={},
            )

        # The function completed without propagating the exception
        # No request was written (enqueue failed), and that's OK
        requests = _read_requests(_queue_root(tmp_path))
        assert len(requests) == 0

    def test_feature_flag_off_suppresses_enqueue(self, tmp_path: Path) -> None:
        """When repair_request_queue_enabled() returns False, no request is written."""
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        plan_dir = tmp_path / "markers"
        plan_dir.mkdir()
        (plan_dir / "state.json").write_text('{"current_state":"blocked"}')

        with patch(
            "arnold_pipelines.megaplan.cloud.feature_flags.repair_request_queue_enabled",
            return_value=False,
        ):
            _enqueue_lifecycle_failure_request(
                plan_dir=plan_dir,
                queue_root=_queue_root(tmp_path),
                kind="stall_detected",
                message="Driver stalled",
                current_state="blocked",
                phase="execute",
                suggested_action="",
                metadata={},
            )

        requests = _read_requests(_queue_root(tmp_path))
        assert len(requests) == 0

    def test_lifecycle_and_supervisor_producers_converge_on_central_queue(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.auto import _enqueue_lifecycle_failure_request
        from arnold_pipelines.megaplan.cloud.supervise import (
            enqueue_supervisor_repair_request,
        )

        workspace = tmp_path / "workspace"
        plan_dir = workspace / ".megaplan" / "plans" / "demo-plan"
        marker_dir = workspace / ".megaplan" / "cloud-sessions"
        plan_dir.mkdir(parents=True)
        marker_dir.mkdir()
        queue_root = _queue_root(workspace)

        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            queue_root=queue_root,
            kind="stall_detected",
            message="driver stalled",
            current_state="blocked",
            phase="execute",
            suggested_action="manual_review",
            metadata={"blocked_task_id": "T1"},
        )
        first_supervisor = enqueue_supervisor_repair_request(
            queue_root=queue_root,
            marker_dir=marker_dir,
            session="demo-session",
            workspace=workspace,
            remote_spec=".megaplan/initiatives/demo/chain.yaml",
            run_kind="chain",
            reason="retry budget exhausted",
            log_path="/tmp/supervise.log",
        )
        second_supervisor = enqueue_supervisor_repair_request(
            queue_root=queue_root,
            marker_dir=marker_dir,
            session="demo-session",
            workspace=workspace,
            remote_spec=".megaplan/initiatives/demo/chain.yaml",
            run_kind="chain",
            reason="retry budget exhausted",
            log_path="/tmp/supervise.log",
        )

        requests = _read_requests(queue_root)
        assert {request["source"] for request in requests} == {
            "lifecycle_failure",
            "arnold_supervise_exit",
        }
        assert all(request["queue_dir"] == str(queue_root) for request in requests)
        assert first_supervisor["status"] == "queued"
        assert second_supervisor["status"] == "coalesced"
        assert any(
            decision["decision"] == "coalesced"
            for decision in _read_decisions(queue_root)
        )

    def test_supervisor_preserves_execution_binding_drift_identity(
        self, tmp_path: Path
    ) -> None:
        from arnold_pipelines.megaplan.cloud.supervise import (
            enqueue_supervisor_repair_request,
        )

        workspace = tmp_path / "workspace"
        marker_dir = workspace / ".megaplan" / "cloud-sessions"
        marker_dir.mkdir(parents=True)
        queue_root = _queue_root(workspace)

        with patch(
            "arnold_pipelines.megaplan.cloud.current_target.resolve_current_target",
            return_value={"current_refs": {"current_plan_name": "m6-plan"}},
        ):
            result = enqueue_supervisor_repair_request(
                queue_root=queue_root,
                marker_dir=marker_dir,
                session="custody-chain",
                workspace=workspace,
                remote_spec=".megaplan/initiatives/custody/chain.yaml",
                run_kind="chain",
                reason=(
                    "deterministic supervised failure: "
                    "chain_execution_binding_drift;"
                    "active_errors=editable_runtime_import_root_mismatch"
                ),
                log_path="/tmp/supervise.log",
            )

        request = result["request"]
        signature = request["problem_signature"]
        assert result["status"] == "queued"
        assert signature["failure_kind"] == "chain_execution_binding_drift"
        assert signature["phase_or_step"] == "chain_execution_binding"
        assert signature["blocked_task_id"] == (
            "chain_execution_binding:editable_runtime_import_root_mismatch"
        )
        assert signature["event_signature"] == (
            "chain_execution_binding_drift;"
            "active_errors=editable_runtime_import_root_mismatch"
        )
        assert "content-addressed rebind" in signature["gate_recommendation"]
        assert request["blocker_id"].startswith("blocker:v2:")


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

        hook_ext = _make_hook_extensions(
            plan_dir=str(markers), workspace_path=str(tmp_path)
        )

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
        requests = _read_requests(_queue_root(tmp_path))
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
        assert target["workspace_path"] == str(tmp_path)
        assert target["pipeline_name"] == "demo_judges"

    def test_resume_path_does_not_enqueue(self, tmp_path: Path) -> None:
        """On resume (valid _resume_choice), no repair request is enqueued."""
        from arnold_pipelines.megaplan.cloud.repair_requests import (
            iter_repair_requests,
        )

        markers = tmp_path / "plan-markers"
        markers.mkdir()
        hook_ext = _make_hook_extensions(
            plan_dir=str(markers), workspace_path=str(tmp_path)
        )

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
        requests = _read_requests(_queue_root(tmp_path))
        assert len(requests) == 0

    def test_missing_hook_extensions_no_op(self, tmp_path: Path) -> None:
        """When hook_extensions is missing plan_dir/workspace_path/session,
        no enqueue occurs and the step still halts normally."""
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
        queue_dir = _queue_root(tmp_path)
        req_dir = queue_dir / "requests"
        assert not req_dir.exists() or len(list(req_dir.glob("*.json"))) == 0

    def test_missing_workspace_path_no_op(self, tmp_path: Path) -> None:
        """When hook_extensions has plan_dir and session but no workspace_path,
        enqueue is skipped."""
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

        queue_dir = _queue_root(tmp_path)
        req_dir = queue_dir / "requests"
        assert not req_dir.exists() or len(list(req_dir.glob("*.json"))) == 0

    def test_missing_session_no_op(self, tmp_path: Path) -> None:
        """When hook_extensions has plan_dir and workspace but no session,
        enqueue is skipped."""
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

        queue_dir = _queue_root(tmp_path)
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
        hook_ext = _make_hook_extensions(
            plan_dir=str(markers), workspace_path=str(tmp_path)
        )

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
        requests = _read_requests(_queue_root(tmp_path))
        assert len(requests) == 0

    def test_human_gate_enqueue_failure_non_fatal(self, tmp_path: Path) -> None:
        """If enqueue raises inside HumanGateStep, the step still halts
        normally — enqueue failure is a logged warning only."""
        markers = tmp_path / "plan-markers"
        markers.mkdir()
        hook_ext = _make_hook_extensions(
            plan_dir=str(markers), workspace_path=str(tmp_path)
        )

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
        hook_ext = _make_hook_extensions(
            plan_dir=str(markers), workspace_path=str(tmp_path)
        )

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
        requests = _read_requests(_queue_root(tmp_path))
        assert len(requests) == 1

        # A coalesced decision should exist
        decisions = _read_decisions(_queue_root(tmp_path))
        coalesced = [d for d in decisions if d.get("decision") == "coalesced"]
        assert len(coalesced) >= 1
