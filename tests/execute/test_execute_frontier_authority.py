from __future__ import annotations

import json
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
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    AUTHORITY_DIVERGENCE_LEDGER,
    AuthorityDecision,
    corroborated_completed_task_ids,
    effective_execute_completed_task_ids,
    scheduler_completed_ids,
)
from arnold_pipelines.run_authority import CoordinatorFence, EvidenceEnvelope, IdempotencyKey


RUN = "plan-frontier"
REVISION = "revision-frontier"


def _records(task_id: str):
    evidence = EvidenceEnvelope(
        f"evidence-{task_id}",
        RUN,
        REVISION,
        "pytest",
        f"reports/{task_id}.json",
        {"passed": True},
    )
    fence = CoordinatorFence(RUN, REVISION, "coordinator-1", 7)
    grant = DispatchGrant(
        f"dispatch-{task_id}",
        RUN,
        REVISION,
        "coordinator-1",
        7,
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
        7,
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
        7,
        TASK_COMPLETION_CLAIM,
        (evidence.evidence_id,),
        f"claim-key-{task_id}",
        {"status": "done"},
    )
    return evidence, fence, grant, attempt, IdempotencyKey(claim.idempotency_key, claim.payload_hash), claim


def _write_validated_attempt_artifact(plan_dir: Path, *, task_id: str) -> ResultEnvelope:
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
    entry = {
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
            "source_path": "execute_batches/batch_1/tasks.json",
        },
    }
    path = execute_batch_artifact_path(plan_dir, 1, [task_id])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "task_updates": [entry],
                DISPATCH_IDENTITY_KEY: dispatch.to_dict(),
                RESULT_ENVELOPES_KEY: [envelope.to_dict()],
            }
        ),
        encoding="utf-8",
    )
    return envelope


def test_completed_task_helpers_are_compatibility_shadow_adapters(tmp_path: Path) -> None:
    for helper in (
        corroborated_completed_task_ids,
        scheduler_completed_ids,
        effective_execute_completed_task_ids,
    ):
        assert "Compatibility/shadow adapter" in (helper.__doc__ or "")

    task = {
        "id": "T-raw",
        "status": "done",
        "files_changed": ["src/raw.py"],
        "head_sha": "abc123",
    }

    corroborated_dir = tmp_path / "corroborated"
    corroborated_dir.mkdir()
    corroborated_decisions: dict[str, AuthorityDecision] = {}
    assert corroborated_completed_task_ids(
        [task],
        plan_dir=corroborated_dir,
        current_head="abc123",
        decisions=corroborated_decisions,
    ) == set()
    assert corroborated_decisions["T-raw"].diagnostics["authority_adapter"] == (
        "corroborated_completed_task_ids"
    )
    assert corroborated_decisions["T-raw"].diagnostics["adapter_mode"] == (
        "compatibility_shadow"
    )

    scheduler_dir = tmp_path / "scheduler"
    scheduler_dir.mkdir()
    scheduler_decisions: dict[str, AuthorityDecision] = {}
    assert scheduler_completed_ids(
        [task],
        plan_dir=scheduler_dir,
        current_head="abc123",
        decisions=scheduler_decisions,
    ) == set()
    assert scheduler_decisions["T-raw"].diagnostics["authority_adapter"] == (
        "scheduler_completed_ids"
    )
    assert scheduler_decisions["T-raw"].diagnostics["shadow_delegate"] == (
        "corroborated_completed_task_ids"
    )


def test_effective_execute_projection_emits_drift_for_raw_terminal_disagreement(
    tmp_path: Path,
) -> None:
    _write_validated_attempt_artifact(tmp_path, task_id="T1")
    tasks = [
        {"id": "T1", "status": "pending", "depends_on": []},
        {
            "id": "T2",
            "status": "done",
            "depends_on": ["T1"],
            "files_changed": ["src/T2.py"],
            "head_sha": "abc123",
        },
    ]
    decisions: dict[str, AuthorityDecision] = {}

    completed = effective_execute_completed_task_ids(
        tasks,
        plan_dir=tmp_path,
        current_head="abc123",
        decisions=decisions,
    )

    assert completed == {"T1"}
    assert decisions["T1"].diagnostics["authority_adapter"] == (
        "effective_execute_completed_task_ids"
    )
    assert decisions["T2"].diagnostics["execute_completion"] == (
        "accepted_attempt_projection"
    )
    assert decisions["T2"].diagnostics["reason"] == "no_accepted_attempt"
    assert any(
        item["code"] == "legacy_terminal_without_authority"
        for item in decisions["T2"].diagnostics["projection_diagnostics"]
    )

    ledger_path = tmp_path / AUTHORITY_DIVERGENCE_LEDGER
    records = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["task_id"] for record in records] == ["T2"]
    assert records[0]["raw_terminal_status"] == "done"
    assert records[0]["reason"] == "no_accepted_attempt"
    assert records[0]["diagnostics"]["execute_completion"] == (
        "accepted_attempt_projection"
    )
