from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import manual_repair_trigger, repair_requests
from arnold_pipelines.megaplan.custody.contracts import CustodyTargetKey


SESSION = "custody-control-plane-test"
PLAN = "m5a-test-plan"
ARTIFACT_HASH = "sha256:" + "a" * 64


def _identity(workspace: Path) -> dict[str, object]:
    target = CustodyTargetKey(
        environment=str(workspace),
        session=SESSION,
        chain=str(workspace / "chain.yaml"),
        plan_revision="sha256:manual-plan-revision",
        phase="review",
        task="T24",
        attempt="1",
        normalized_failure_kind="quality_gate_blocked",
        blocker_or_phase_result_hash=ARTIFACT_HASH,
        fence="runner-fence:1",
    )
    identity = repair_requests.build_normalized_repair_identity(
        target=target,
        run_id="manual-run-1",
        run_revision="sha256:manual-plan-revision",
        run_incarnation_id="manual-run-incarnation-1",
        coordinator_attempt_id="manual-coordinator-1",
        fence_token=1,
        wbc_attempt_reference="manual-wbc-1",
        run_authority_grant_id="manual-grant-1",
        lease_id="manual-lease-1",
        custody_epoch=1,
    )
    assert identity is not None
    return identity


def _fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    marker_dir = tmp_path / ".megaplan" / "cloud-sessions"
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    workspace = tmp_path / "workspace"
    plan_dir = workspace / ".megaplan" / "plans" / PLAN
    plan_dir.mkdir(parents=True)
    marker_dir.mkdir(parents=True)
    repair_identity = _identity(workspace)
    state = {
        "name": PLAN,
        "current_state": "blocked",
        "config": {"profile": "partnered-5"},
        "repair_identity": repair_identity,
        "resume_cursor": {
            "phase": "review",
            "evidence_cursor": {
                "history_index": 15,
                "review_artifact_hash": ARTIFACT_HASH,
            },
        },
        "latest_failure": {
            "kind": "quality_gate_blocked",
            "message": "review rework budget exhausted",
            "phase": "review",
            "suggested_action": "Dispatch one bounded automatic repair.",
            "metadata": {
                "repair_identity": repair_identity,
                "blocked_task_ids": ["T24"],
                "evidence_cursor": {
                    "history_index": 15,
                    "review_artifact_hash": ARTIFACT_HASH,
                },
            },
        },
    }
    state_path = plan_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    fingerprint = hashlib.sha256(state_path.read_bytes()).hexdigest()
    target = {
        "target_session": SESSION,
        "authoritative_source": "chain_state",
        "current_refs": {
            "current_plan_name": PLAN,
            "workspace": str(workspace),
            "remote_spec": str(workspace / "chain.yaml"),
            "run_kind": "chain",
        },
        "plan_state": {
            "path": str(state_path),
            "present": True,
            "name": PLAN,
            "current_state": "blocked",
            "fingerprint": fingerprint,
        },
        "stale_evidence": [],
        "evidence_state": {"mutation_eligible": True},
    }
    return marker_dir, queue_root, target


def _authorized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_AUTONOMY", "1")
    monkeypatch.setenv("ARNOLD_REPAIR_TRIGGER_ENABLED", "1")


def test_manual_trigger_uses_simple_fixer_delegation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T27: trigger_once delegates to simple_fixer instead of executing a subprocess.

    The delegation goes through RepairDelegation with caller_kind="operator_trigger".
    The result includes delegation_outcome and simple_fixer_outcome fields instead
    of managed_run_id/managed_manifest_path/trigger_returncode.
    """
    marker_dir, queue_root, target = _fixture(tmp_path)
    _authorized(monkeypatch)

    result = manual_repair_trigger.trigger_once(
        session=SESSION,
        plan=PLAN,
        expected_history_index=15,
        expected_artifact_hash=ARTIFACT_HASH,
        marker_dir=marker_dir,
        queue_root=queue_root,
        target_resolver=lambda *_args, **_kwargs: target,
    )

    assert result["status"] == "dispatched"
    assert result["session"] == SESSION
    assert result["plan"] == PLAN
    assert "request_id" in result
    assert "receipt_path" in result
    # Delegation fields replace the old managed_run_id/managed_manifest_path.
    assert "delegation_outcome" in result
    assert "simple_fixer_outcome" in result
    assert "occurrence_fingerprint" in result
    # Verify delegation outcome vocabulary is closed.
    assert result["delegation_outcome"] in ("delegated",)
    assert result["simple_fixer_outcome"] in (
        "attempted", "unchanged", "exhausted",
    )

    # The enqueued request still exists (append-only queue evidence preserved).
    request = next(
        item
        for item in repair_requests.iter_repair_requests(queue_root)
        if item["request_id"] == result["request_id"]
    )
    assert request["source"] == "manual_terminal_failure_retrigger"
    assert request["problem_signature"]["blocked_task_id"] == "T24"
    assert request["target"]["configured_profile"] == "partnered-5"
    assert request["target"]["recovery_contract"] == {
        "preserve_configured_profile": True,
        "required_cursor_advance": True,
        "forbid_standalone_completion": True,
        "success_requires": "the canonical plan must advance beyond the frozen evidence cursor",
    }

    # Append-only queue evidence: receipt was written.
    receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "dispatched"
    assert "delegation_outcome" in receipt
    assert "simple_fixer_outcome" in receipt
    assert receipt.get("delegation_target") == "simple_fixer"
    # The old dispatch_event/managed_run_id fields are gone.
    assert "dispatch_event" not in receipt
    assert "trigger_returncode" not in receipt
    assert "trigger_bin" not in receipt

    # Singleton claim prevents duplicate dispatch (receipt exclusive-create).
    with pytest.raises(manual_repair_trigger.ManualRepairTriggerError, match="already exists"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=15,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            target_resolver=lambda *_args, **_kwargs: target,
        )


def test_manual_trigger_rejects_legacy_trigger_bin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T27: trigger_once no longer accepts trigger_bin or command_runner parameters.

    Passing trigger_bin or command_runner as keyword arguments raises TypeError
    because those parameters have been removed in favour of simple_fixer delegation.
    The ARNOLD_MANUAL_REPAIR_TRIGGER_BIN environment variable is also ignored.
    """
    marker_dir, queue_root, target = _fixture(tmp_path)
    _authorized(monkeypatch)

    # trigger_bin is no longer a valid parameter.
    with pytest.raises(TypeError, match="trigger_bin"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=15,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            trigger_bin=Path("/usr/local/bin/arnold-repair-trigger"),
            target_resolver=lambda *_args, **_kwargs: target,
        )

    # command_runner is no longer accepted.
    with pytest.raises(TypeError, match="command_runner"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=15,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            target_resolver=lambda *_args, **_kwargs: target,
            command_runner=lambda *a, **kw: None,
        )

    # ARNOLD_MANUAL_REPAIR_TRIGGER_BIN is ignored — setting it has no effect
    # on a successful delegation dispatch.  Use a separate workspace so the
    # exclusive receipt does not collide with the one created by
    # test_manual_trigger_uses_simple_fixer_delegation.
    fresh = tmp_path / "fresh-workspace"
    fresh.mkdir()
    fresh_queue = fresh / ".megaplan" / "repair-queue"
    monkeypatch.setenv(
        "ARNOLD_MANUAL_REPAIR_TRIGGER_BIN",
        "/usr/local/bin/arnold-repair-trigger",
    )
    # Build a new target pointing into the fresh workspace.
    fresh_workspace = fresh / "workspace"
    fresh_plan_dir = fresh_workspace / ".megaplan" / "plans" / PLAN
    fresh_plan_dir.mkdir(parents=True)
    state_path = fresh_plan_dir / "state.json"
    fresh_identity = _identity(fresh_workspace)
    state_path.write_text(
        json.dumps({
            "name": PLAN,
            "current_state": "blocked",
            "config": {"profile": "partnered-5"},
            "repair_identity": fresh_identity,
            "resume_cursor": {
                "phase": "review",
                "evidence_cursor": {
                    "history_index": 15,
                    "review_artifact_hash": ARTIFACT_HASH,
                },
            },
            "latest_failure": {
                "kind": "quality_gate_blocked",
                "message": "review rework budget exhausted",
                "phase": "review",
                "suggested_action": "Dispatch one bounded automatic repair.",
                "metadata": {
                    "repair_identity": fresh_identity,
                    "blocked_task_ids": ["T24"],
                    "evidence_cursor": {
                        "history_index": 15,
                        "review_artifact_hash": ARTIFACT_HASH,
                    },
                },
            },
        }),
        encoding="utf-8",
    )
    fp = hashlib.sha256(state_path.read_bytes()).hexdigest()
    fresh_target = {
        "target_session": SESSION,
        "authoritative_source": "chain_state",
        "current_refs": {
            "current_plan_name": PLAN,
            "workspace": str(fresh_workspace),
            "remote_spec": str(fresh_workspace / "chain.yaml"),
            "run_kind": "chain",
        },
        "plan_state": {
            "path": str(state_path),
            "present": True,
            "name": PLAN,
            "current_state": "blocked",
            "fingerprint": fp,
        },
        "stale_evidence": [],
        "evidence_state": {"mutation_eligible": True},
    }
    result = manual_repair_trigger.trigger_once(
        session=SESSION,
        plan=PLAN,
        expected_history_index=15,
        expected_artifact_hash=ARTIFACT_HASH,
        marker_dir=marker_dir,
        queue_root=fresh_queue,
        target_resolver=lambda *_args, **_kwargs: fresh_target,
    )
    assert result["status"] == "dispatched"
    # The env var has no effect — the result uses delegation, not subprocess.
    assert "delegation_outcome" in result


def test_manual_trigger_rejects_changed_evidence_before_queue_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir, queue_root, target = _fixture(tmp_path)
    _authorized(monkeypatch)

    with pytest.raises(manual_repair_trigger.ManualRepairTriggerError, match="cursor"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=14,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            target_resolver=lambda *_args, **_kwargs: target,
        )

    assert not (queue_root / repair_requests.REQUESTS_DIR_NAME).exists()
    assert not (queue_root / manual_repair_trigger.RECEIPT_DIR_NAME).exists()


def test_manual_trigger_derives_frozen_cursor_from_matching_terminal_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir, queue_root, target = _fixture(tmp_path)
    _authorized(monkeypatch)
    state_path = Path(target["plan_state"]["path"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "fresh_session"}
    state["latest_failure"] = {
        "kind": "execution_blocked",
        "message": "execute blocked by quality gates",
        "phase": "execute",
        "suggested_action": "Resume execute with a fresh session.",
        "metadata": {},
    }
    state["history"] = [
        {
            "step": "execute",
            "result": "blocked",
            "artifact_hash": ARTIFACT_HASH,
        }
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    target["plan_state"]["fingerprint"] = hashlib.sha256(state_path.read_bytes()).hexdigest()

    result = manual_repair_trigger.trigger_once(
        session=SESSION,
        plan=PLAN,
        expected_history_index=0,
        expected_artifact_hash=ARTIFACT_HASH,
        marker_dir=marker_dir,
        queue_root=queue_root,
        target_resolver=lambda *_args, **_kwargs: target,
    )

    request = next(
        item
        for item in repair_requests.iter_repair_requests(queue_root)
        if item["request_id"] == result["request_id"]
    )
    assert request["target"]["evidence_cursor"] == {
        "history_index": 0,
        "review_artifact_hash": ARTIFACT_HASH,
    }
    assert request["target"]["configured_profile"] == "partnered-5"


def test_manual_trigger_rejects_terminal_history_from_a_different_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir, queue_root, target = _fixture(tmp_path)
    _authorized(monkeypatch)
    state_path = Path(target["plan_state"]["path"])
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "fresh_session"}
    state["latest_failure"] = {
        "kind": "execution_blocked",
        "message": "execute blocked by quality gates",
        "phase": "execute",
        "metadata": {},
    }
    state["history"] = [
        {
            "step": "review",
            "result": "blocked",
            "artifact_hash": ARTIFACT_HASH,
        }
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    target["plan_state"]["fingerprint"] = hashlib.sha256(state_path.read_bytes()).hexdigest()

    with pytest.raises(manual_repair_trigger.ManualRepairTriggerError, match="cursor"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=0,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            target_resolver=lambda *_args, **_kwargs: target,
        )

    assert not (queue_root / repair_requests.REQUESTS_DIR_NAME).exists()
    assert not (queue_root / manual_repair_trigger.RECEIPT_DIR_NAME).exists()


def test_manual_trigger_requires_invocation_scoped_l1_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir, queue_root, target = _fixture(tmp_path)
    monkeypatch.setenv("ARNOLD_AUTONOMY", "0")
    monkeypatch.setenv("ARNOLD_REPAIR_TRIGGER_ENABLED", "1")

    with pytest.raises(manual_repair_trigger.ManualRepairTriggerError, match="not authorized"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=15,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            target_resolver=lambda *_args, **_kwargs: target,
        )
