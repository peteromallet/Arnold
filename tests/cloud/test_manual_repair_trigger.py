from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud import manual_repair_trigger, repair_requests


SESSION = "custody-control-plane-test"
PLAN = "m5a-test-plan"
ARTIFACT_HASH = "sha256:" + "a" * 64


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    marker_dir = tmp_path / ".megaplan" / "cloud-sessions"
    queue_root = tmp_path / ".megaplan" / "repair-queue"
    workspace = tmp_path / "workspace"
    plan_dir = workspace / ".megaplan" / "plans" / PLAN
    plan_dir.mkdir(parents=True)
    marker_dir.mkdir(parents=True)
    state = {
        "name": PLAN,
        "current_state": "blocked",
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
    trigger_bin = tmp_path / "arnold-repair-trigger"
    trigger_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    trigger_bin.chmod(0o755)
    return marker_dir, queue_root, trigger_bin, target


def _authorized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARNOLD_AUTONOMY", "1")
    monkeypatch.setenv("ARNOLD_REPAIR_TRIGGER_ENABLED", "1")


def test_manual_trigger_enqueues_canonical_request_and_dispatches_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir, queue_root, trigger_bin, target = _fixture(tmp_path)
    _authorized(monkeypatch)
    calls: list[list[str]] = []

    def runner(command, **_kwargs):
        calls.append(command)
        request_id = command[command.index("--request-id") + 1]
        event = {
            "event": "repair_trigger_dispatch",
            "status": "dispatched",
            "request_id": request_id,
            "managed_run_id": "managed-test-1",
            "managed_manifest_path": "/tmp/managed-test-1/manifest.json",
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(event) + "\n", "")

    result = manual_repair_trigger.trigger_once(
        session=SESSION,
        plan=PLAN,
        expected_history_index=15,
        expected_artifact_hash=ARTIFACT_HASH,
        marker_dir=marker_dir,
        queue_root=queue_root,
        trigger_bin=trigger_bin,
        target_resolver=lambda *_args, **_kwargs: target,
        command_runner=runner,
    )

    assert result["status"] == "dispatched"
    assert result["managed_run_id"] == "managed-test-1"
    assert len(calls) == 1
    request = next(
        item
        for item in repair_requests.iter_repair_requests(queue_root)
        if item["request_id"] == result["request_id"]
    )
    assert request["source"] == "manual_terminal_failure_retrigger"
    assert request["problem_signature"]["blocked_task_id"] == "T24"
    receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "dispatched"
    assert receipt["dispatch_event"]["managed_run_id"] == "managed-test-1"

    with pytest.raises(manual_repair_trigger.ManualRepairTriggerError, match="already exists"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=15,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            trigger_bin=trigger_bin,
            target_resolver=lambda *_args, **_kwargs: target,
            command_runner=runner,
        )
    assert len(calls) == 1


def test_manual_trigger_rejects_changed_evidence_before_queue_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir, queue_root, trigger_bin, target = _fixture(tmp_path)
    _authorized(monkeypatch)

    with pytest.raises(manual_repair_trigger.ManualRepairTriggerError, match="cursor"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=14,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            trigger_bin=trigger_bin,
            target_resolver=lambda *_args, **_kwargs: target,
            command_runner=lambda *_args, **_kwargs: pytest.fail("must not dispatch"),
        )

    assert not (queue_root / repair_requests.REQUESTS_DIR_NAME).exists()
    assert not (queue_root / manual_repair_trigger.RECEIPT_DIR_NAME).exists()


def test_manual_trigger_requires_invocation_scoped_l1_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir, queue_root, trigger_bin, target = _fixture(tmp_path)
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
            trigger_bin=trigger_bin,
            target_resolver=lambda *_args, **_kwargs: target,
        )


def test_manual_trigger_quarantines_receipt_when_queue_identity_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir, queue_root, trigger_bin, target = _fixture(tmp_path)
    _authorized(monkeypatch)

    original_enqueue = repair_requests.enqueue_repair_request

    def mismatched_enqueue(**kwargs):
        result = original_enqueue(**kwargs)
        request = dict(result["request"])
        request["repair_identity"] = {
            **request["repair_identity"],
            "attempt_number": 99,
        }
        request["repair_identity_key"] = repair_requests.repair_identity_key(
            request["repair_identity"]
        )
        result["request"] = request
        return result

    with pytest.raises(manual_repair_trigger.ManualRepairTriggerError, match="quarantined"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=15,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            trigger_bin=trigger_bin,
            target_resolver=lambda *_args, **_kwargs: target,
            command_runner=lambda *_args, **_kwargs: pytest.fail("must not dispatch"),
            repair_requests_enqueue=mismatched_enqueue,  # type: ignore[call-arg]
        )

    quarantined = list((queue_root / manual_repair_trigger.RECEIPT_DIR_NAME / "quarantine").glob("*.json"))
    assert len(quarantined) == 1
    payload = json.loads(quarantined[0].read_text(encoding="utf-8"))
    assert payload["status"] == "quarantined"


def test_manual_trigger_quarantines_receipt_when_queue_identity_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker_dir, queue_root, trigger_bin, target = _fixture(tmp_path)
    _authorized(monkeypatch)

    original_enqueue = repair_requests.enqueue_repair_request

    def identity_free_enqueue(**kwargs):
        result = original_enqueue(**kwargs)
        request = dict(result["request"])
        request["repair_identity"] = {}
        request["repair_identity_key"] = ""
        result["request"] = request
        return result

    with pytest.raises(manual_repair_trigger.ManualRepairTriggerError, match="quarantined"):
        manual_repair_trigger.trigger_once(
            session=SESSION,
            plan=PLAN,
            expected_history_index=15,
            expected_artifact_hash=ARTIFACT_HASH,
            marker_dir=marker_dir,
            queue_root=queue_root,
            trigger_bin=trigger_bin,
            target_resolver=lambda *_args, **_kwargs: target,
            command_runner=lambda *_args, **_kwargs: pytest.fail("must not dispatch"),
            repair_requests_enqueue=identity_free_enqueue,  # type: ignore[call-arg]
        )

    quarantined = list((queue_root / manual_repair_trigger.RECEIPT_DIR_NAME / "quarantine").glob("*.json"))
    assert len(quarantined) == 1
    payload = json.loads(quarantined[0].read_text(encoding="utf-8"))
    assert payload["status"] == "quarantined"
    assert payload["observed_repair_identity"] == {}
