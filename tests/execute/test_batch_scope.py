from __future__ import annotations

from arnold_pipelines.megaplan.authority.batch_scope import (
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
)
from arnold_pipelines.megaplan.authority.binding import (
    DispatchIdentity,
    ResultEnvelope,
    TASK_COMPLETION_CLAIM,
    TASK_RESULT_CAPABILITY,
    TaskAttempt,
    TaskClaim,
)
from arnold_pipelines.megaplan.execute.merge import _merge_batch_results
from arnold_pipelines.megaplan.execute.wbc import EXECUTE_DISPATCH_WBC_KEY
from arnold_pipelines.run_authority import EvidenceEnvelope


def _shared_dispatch(subject_ids: tuple[str, ...]) -> DispatchIdentity:
    return DispatchIdentity.create(
        dispatch_id="dispatch-1",
        run_id="run-1",
        run_revision="revision-1",
        coordinator_attempt_id="coordinator-1",
        fence_token=2,
        subject_ids=subject_ids,
        capabilities=(TASK_RESULT_CAPABILITY,),
        prerequisite_digest="prereq-1",
        worker_id="worker-1",
    )


def _envelope_for(
    entry: dict[str, object],
    *,
    dispatch: DispatchIdentity,
    subject_id: str,
    ordinal: int,
) -> ResultEnvelope:
    base_id = f"{dispatch.dispatch_id}:task:{subject_id}:{ordinal}"
    evidence = EvidenceEnvelope(
        evidence_id=f"{base_id}:evidence",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        evidence_type="megaplan.task_update",
        source="test",
        payload={"entry": entry},
    )
    attempt = TaskAttempt(
        attempt_id=f"{base_id}:attempt",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        subject_id=subject_id,
        grant_id=dispatch.dispatch_id,
        coordinator_attempt_id=dispatch.coordinator_attempt_id,
        fence_token=dispatch.fence_token,
        ordinal=ordinal,
    )
    claim = TaskClaim(
        claim_id=f"{base_id}:claim",
        run_id=dispatch.run_id,
        run_revision=dispatch.run_revision,
        subject_id=subject_id,
        attempt_id=attempt.attempt_id,
        grant_id=dispatch.dispatch_id,
        coordinator_attempt_id=dispatch.coordinator_attempt_id,
        fence_token=dispatch.fence_token,
        claim_type=TASK_COMPLETION_CLAIM,
        evidence_ids=(evidence.evidence_id,),
        idempotency_key=f"{dispatch.dispatch_id}:task:{subject_id}:claim",
        payload={"entry": entry},
    )
    return ResultEnvelope(dispatch=dispatch, attempt=attempt, claim=claim, evidence=(evidence,))


def _payload_with_envelopes(
    entries: list[dict[str, object]],
    envelopes: list[ResultEnvelope],
    dispatch: DispatchIdentity,
) -> dict[str, object]:
    for entry, envelope in zip(entries, envelopes, strict=True):
        entry["authority"] = {
            "envelope_digest": envelope.digest(),
            "dispatch_id": envelope.dispatch_id,
            "run_revision": envelope.run_revision,
            "plan_revision": envelope.plan_revision,
            "fence": envelope.dispatch.fence.to_dict(),
            "scope": {
                "subject_ids": list(envelope.dispatch.subject_ids),
                "capabilities": list(envelope.dispatch.capabilities),
            },
            "prerequisite_digest": envelope.prerequisite_digest,
            "worker_id": envelope.worker_id,
            "attempt": envelope.attempt.to_dict(),
        }
    return {
        DISPATCH_IDENTITY_KEY: dispatch.to_dict(),
        RESULT_ENVELOPES_KEY: [envelope.to_dict() for envelope in envelopes],
        EXECUTE_DISPATCH_WBC_KEY: {
            "schema_version": 1,
            "attempt_id": "execute-dispatch-attempt",
            "writer_id": "megaplan.execute.dispatch_wbc",
            "surface_name": "megaplan.execute.dispatch_wbc",
            "dispatch_id": dispatch.dispatch_id,
            "plan_revision": dispatch.plan_revision,
            "fence_token": dispatch.fence_token,
            "prerequisite_digest": dispatch.prerequisite_digest,
            "worker_id": dispatch.worker_id,
            "expected_source_version": "source.v1",
            "start_source_lookup_key": "execute-batch:1:start",
            "terminal_source_lookup_key": "execute-batch:1:complete",
            "verified_start_sequence": 1,
            "verified_terminal_sequence": 2,
            "verified_reread": True,
        },
        "task_updates": entries,
        "sense_check_acknowledgments": [],
    }


def test_full_batch_ownership_preserves_unclaimed_files() -> None:
    """Step 14: full batch ownership is required before claimed-file mutation.

    T1 admits ``src/a.py`` in its ``write_set``; T2 declares no ``write_set``
    at all.  T1 claims only the file it owns (related) and is accepted.  T2
    claims ``docs/unrelated.md`` — a file no batch task owns — so the batch
    ownership gate blocks T2 and preserves the unrelated file rather than
    letting an undeclared mutation land.
    """

    finalize_data = {
        "tasks": [
            {
                "id": "T1",
                "depends_on": [],
                "status": "pending",
                "write_set": {"paths": ["src/a.py"]},
            },
            {
                "id": "T2",
                "depends_on": ["T1"],
                "status": "pending",
            },
        ],
        "sense_checks": [],
        "user_actions": [],
    }
    entries = [
        {
            "task_id": "T1",
            "status": "done",
            "executor_notes": "owns a.py",
            "files_changed": ["src/a.py"],
            "commands_run": [],
        },
        {
            "task_id": "T2",
            "status": "done",
            "executor_notes": "claims an unrelated file",
            "files_changed": ["docs/unrelated.md"],
            "commands_run": [],
        },
    ]
    dispatch = _shared_dispatch(("T1", "T2"))
    envelopes = [
        _envelope_for(entries[0], dispatch=dispatch, subject_id="T1", ordinal=1),
        _envelope_for(entries[1], dispatch=dispatch, subject_id="T2", ordinal=2),
    ]
    payload = _payload_with_envelopes(entries, envelopes, dispatch)

    issues: list[str] = []
    _merge_batch_results(
        finalize_data=finalize_data,
        payload=payload,
        batch_task_ids=["T1", "T2"],
        batch_sense_check_ids=[],
        issues=issues,
        state={"config": {"mode": "code"}},
        source_path="test-batch-scope",
    )

    tasks = {task["id"]: task for task in finalize_data["tasks"]}
    # T1 owns src/a.py and claims only that file -> accepted.
    assert tasks["T1"]["status"] == "done"
    # T2 has no write_set and claims a file no batch task owns -> blocked,
    # which preserves the unrelated docs/unrelated.md file.
    assert tasks["T2"]["status"] == "blocked"
    assert any("batch ownership" in issue for issue in issues)
    assert any("docs/unrelated.md" in issue for issue in issues)
