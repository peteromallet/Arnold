from __future__ import annotations

import json
import hashlib
from pathlib import Path

from arnold_pipelines.megaplan._core import execute_batch_artifact_path
from arnold_pipelines.megaplan.authority import (
    DispatchGrant,
    DispatchIdentity,
    ResultEnvelope,
    TASK_COMPLETION_CLAIM,
    TASK_RESULT_CAPABILITY,
    TaskAttempt,
    TaskClaim,
)
from arnold_pipelines.megaplan.authority.batch_scope import (
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
)
from arnold_pipelines.megaplan.chain import _latest_execution_batch_all_tasks_done
from arnold_pipelines.megaplan.chain.spec import ChainState
from arnold_pipelines.run_authority import CoordinatorFence, EvidenceEnvelope, IdempotencyKey


RUN = "plan-shadow"
REVISION = "revision-shadow"


def _records(task_id: str):
    evidence = EvidenceEnvelope(
        f"evidence-{task_id}",
        RUN,
        REVISION,
        "pytest",
        f"reports/{task_id}.json",
        {"passed": True},
    )
    fence = CoordinatorFence(RUN, REVISION, "coordinator-1", 3)
    grant = DispatchGrant(
        f"dispatch-{task_id}",
        RUN,
        REVISION,
        "coordinator-1",
        3,
        (task_id,),
        (TASK_RESULT_CAPABILITY,),
        (evidence.evidence_id,),
    )
    attempt = TaskAttempt(
        f"attempt-{task_id}",
        RUN,
        REVISION,
        task_id,
        grant.grant_id,
        "coordinator-1",
        3,
        1,
    )
    claim = TaskClaim(
        f"claim-{task_id}",
        RUN,
        REVISION,
        task_id,
        attempt.attempt_id,
        grant.grant_id,
        "coordinator-1",
        3,
        TASK_COMPLETION_CLAIM,
        (evidence.evidence_id,),
        f"claim-key-{task_id}",
        {"status": "done"},
    )
    return evidence, fence, grant, attempt, IdempotencyKey(claim.idempotency_key, claim.payload_hash), claim


def _write_accepted_batch_overlay(plan_dir: Path, *, task_id: str) -> str:
    evidence, fence, grant, attempt, _claim_key, claim = _records(task_id)
    dispatch = DispatchIdentity.from_records(
        grant,
        fence,
        prerequisite_digest="prereq-digest",
        worker_id="worker-1",
    )
    envelope = ResultEnvelope(
        dispatch=dispatch,
        attempt=attempt,
        claim=claim,
        evidence=(evidence,),
    )
    path = execute_batch_artifact_path(plan_dir, 1, [task_id])
    source_path = "execute_batches/batch_1/tasks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": task_id,
                        "status": "done",
                        "files_changed": [f"src/{task_id}.py"],
                        "authority": {"envelope_digest": envelope.digest()},
                        "authority_validation": {
                            "outcome": "accepted",
                            "entry_kind": "task_update",
                            "entry_index": 0,
                            "subject_id": task_id,
                            "reason": "task_update_authority_valid",
                            "idempotency_key": claim.idempotency_key,
                            "envelope_digest": envelope.digest(),
                            "source_path": source_path,
                        },
                    }
                ],
                DISPATCH_IDENTITY_KEY: dispatch.to_dict(),
                RESULT_ENVELOPES_KEY: [envelope.to_dict()],
            }
        ),
        encoding="utf-8",
    )
    return envelope.digest()


def test_chain_completion_shadow_names_disagreeing_authority_sources(tmp_path: Path) -> None:
    (tmp_path / "state.json").write_text(
        json.dumps({"current_state": "done", "config": {}, "meta": {}}),
        encoding="utf-8",
    )
    (tmp_path / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {"id": "T1", "status": "pending", "depends_on": []},
                    {"id": "T2", "status": "done", "depends_on": ["T1"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_accepted_batch_overlay(tmp_path, task_id="T1")
    chain_state = ChainState(
        current_milestone_index=0,
        completed=[{"label": "m1", "plan": "plan-shadow", "status": "done"}],
    )

    ok, reason = _latest_execution_batch_all_tasks_done(
        tmp_path,
        chain_state=chain_state,
        completion_record=chain_state.completed[0],
    )

    assert ok is False
    assert "chain_authority_shadow[T2]" in reason
    assert "finalize data source finalize.json status='done'" in reason
    assert "dispatch-grant/accepted-attempt authority" in reason
    assert "execute_batches/batch_1" in reason
    assert "chain_authority_shadow[m1]" in reason
    assert "chain state source chain_state.completed[m1]" in reason
    assert "incomplete sources: T2 from finalize.json" in reason


def test_chain_completion_accepts_evidence_bound_stale_status_reconciliation(
    tmp_path: Path,
) -> None:
    validation_path = tmp_path / "verification" / "validation_VJ8.json"
    validation_path.parent.mkdir(parents=True)
    validation_path.write_text(
        json.dumps({"status": "passed", "exit_code": 0}),
        encoding="utf-8",
    )
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "task_verdicts": [
                    {"task_id": "T1", "reviewer_verdict": "Pass. Work verified."}
                ]
            }
        ),
        encoding="utf-8",
    )
    envelope_digest = _write_accepted_batch_overlay(tmp_path, task_id="T1")
    (tmp_path / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "blocked",
                        "depends_on": [],
                        "files_changed": ["src/T1.py"],
                        "commands_run": ["pytest tests/T1.py"],
                        "authority": {"envelope_digest": envelope_digest},
                        "authority_validation": {
                            "outcome": "accepted",
                            "envelope_digest": envelope_digest,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    receipt = {
        "schema": "arnold.megaplan.chain_task_projection_reconciliation.v1",
        "task_id": "T1",
        "stale_status": "blocked",
        "reconciled_status": "done",
        "authority_envelope_digest": envelope_digest,
        "quality_resolution_blocker_id": "quality:global:stale-t1",
        "validation": {
            "path": "verification/validation_VJ8.json",
            "sha256": hashlib.sha256(validation_path.read_bytes()).hexdigest(),
        },
        "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
    }
    receipt["content_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (tmp_path / "state.json").write_text(
        json.dumps(
            {
                "current_state": "done",
                "config": {},
                "meta": {
                    "quality_gate_resolutions": [
                        {
                            "blocker_id": "quality:global:stale-t1",
                            "resolution": "fixed",
                        }
                    ],
                    "chain_task_projection_reconciliations": [receipt],
                },
            }
        ),
        encoding="utf-8",
    )

    ok, reason = _latest_execution_batch_all_tasks_done(tmp_path)

    assert ok is True
    assert reason == "finalize.json"
