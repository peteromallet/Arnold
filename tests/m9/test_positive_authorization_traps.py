"""M9 positive-authorization traps.

Forged compatibility projections may look internally consistent at the JSON
level.  These tests pin that they still cannot become accepted task authority
unless the current Run Authority records, result envelope, claim, and validation
decision join through the approved adapter.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core import execute_batch_artifact_path
from arnold_pipelines.megaplan.authority import (
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
    DispatchGrant,
    DispatchIdentity,
    LegacyTaskLabel,
    ResultEnvelope,
    TASK_COMPLETION_CLAIM,
    TASK_RESULT_CAPABILITY,
    TaskAttempt,
    TaskClaim,
    TaskValidationDecision,
    derive_plan_execution_view,
)
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    ENFORCED,
    WARN_ONLY,
    AUTHORITY_ROUTES,
    accepted_attempt_execution_projection,
    corroborated_completed_task_ids,
    effective_execute_completed_task_ids,
    scheduler_completed_ids,
)
from arnold_pipelines.run_authority import (
    CoordinatorFence,
    EvidenceEnvelope,
    IdempotencyKey,
    reduce_run_authority,
)


RUN_ID = "m9-negative-route-fixture"
RUN_REVISION = "rev-current"
_FORBIDDEN_AUTHORITY_WORDS = {
    "complete",
    "completed",
    "dispatch",
    "publication",
    "delivery",
    "repair",
    "retry",
}


def _task(task_id: str = "T33") -> dict[str, Any]:
    return {"id": task_id, "status": "done", "depends_on": []}


def _result_envelope(task_id: str = "T33") -> ResultEnvelope:
    evidence = EvidenceEnvelope(
        f"evidence-{task_id}",
        RUN_ID,
        RUN_REVISION,
        "pytest",
        f"evidence/{task_id}.json",
        {"passed": True},
    )
    fence = CoordinatorFence(RUN_ID, RUN_REVISION, "coordinator-1", 9)
    grant = DispatchGrant(
        f"dispatch-{task_id}",
        RUN_ID,
        RUN_REVISION,
        "coordinator-1",
        9,
        (task_id,),
        (TASK_RESULT_CAPABILITY,),
        (evidence.evidence_id,),
    )
    dispatch = DispatchIdentity.from_records(
        grant,
        fence,
        prerequisite_digest="digest-prereq-current",
        worker_id="worker-current",
    )
    attempt = TaskAttempt(
        f"attempt-{task_id}",
        RUN_ID,
        RUN_REVISION,
        task_id,
        grant.grant_id,
        "coordinator-1",
        9,
        1,
    )
    claim = TaskClaim(
        f"claim-{task_id}",
        RUN_ID,
        RUN_REVISION,
        task_id,
        attempt.attempt_id,
        grant.grant_id,
        "coordinator-1",
        9,
        TASK_COMPLETION_CLAIM,
        (evidence.evidence_id,),
        f"claim-key-{task_id}",
        {"status": "done"},
    )
    decision = TaskValidationDecision(
        f"decision-{task_id}",
        RUN_ID,
        RUN_REVISION,
        task_id,
        attempt.attempt_id,
        grant.grant_id,
        "coordinator-1",
        9,
        claim.claim_id,
        "accepted",
        (evidence.evidence_id,),
        f"decision-key-{task_id}",
        {"reason": "current_source_records_joined"},
    )
    return ResultEnvelope(dispatch, attempt, claim, (evidence,), decision)


def _write_batch_artifact(
    plan_dir: Path,
    *,
    task_id: str = "T33",
    envelope: ResultEnvelope | None = None,
    validation: Mapping[str, Any] | None = None,
    batch_number: int = 1,
) -> Path:
    envelope = envelope if envelope is not None else _result_envelope(task_id)
    validation_payload = {
        "outcome": "accepted",
        "entry_kind": "task_update",
        "entry_index": 0,
        "subject_id": task_id,
        "reason": "task_update_authority_valid",
        "idempotency_key": envelope.claim.idempotency_key,
        "envelope_digest": envelope.digest(),
        "source_path": "execute_batches/batch_1/tasks.json",
    }
    if validation is not None:
        validation_payload.update(dict(validation))
    path = execute_batch_artifact_path(plan_dir, batch_number, [task_id])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": task_id,
                        "status": "done",
                        "files_changed": [f"src/{task_id}.py"],
                        "authority": {"envelope_digest": validation_payload["envelope_digest"]},
                        "authority_validation": validation_payload,
                    }
                ],
                DISPATCH_IDENTITY_KEY: envelope.dispatch.to_dict(),
                RESULT_ENVELOPES_KEY: [envelope.to_dict()],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _assert_no_positive_actions(payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(payload, sort_keys=True)
    for word in _FORBIDDEN_AUTHORITY_WORDS:
        assert f'"authority": "{word}"' not in encoded
        assert f'"action": "{word}"' not in encoded


def test_all_authority_route_families_are_exercised_by_negative_adapter_traps() -> None:
    authority_routes = [
        route for route in AUTHORITY_ROUTES if route.disposition in {ENFORCED, WARN_ONLY}
    ]
    families = {route.route_family for route in authority_routes}

    assert families == {"execute", "resume", "chain", "supervisor", "timeout"}
    assert any(route.id == "CHAIN-01" and route.disposition == ENFORCED for route in authority_routes)
    assert all(route.id and route.file and route.line_range for route in authority_routes)


def test_legacy_terminal_labels_from_every_forged_source_type_never_accept_tasks() -> None:
    source_types = {
        "raw_receipt": "receipts/final-result.json",
        "prose": "review-notes.md",
        "token": "operator-token.txt",
        "mutable_json": "state.json",
        "filename": "execution_batch_999.json",
        "marker": "cloud-sessions/session.done",
        "process_fact": "ps://pid/4242",
        "implicit_latest_schema": "execute_batches/latest/tasks.json",
    }
    legacy_labels = tuple(
        LegacyTaskLabel("T33", "done", source, "observation")
        for source in source_types.values()
    )

    view = derive_plan_execution_view(
        reduce_run_authority((), run_id=RUN_ID, run_revision=RUN_REVISION),
        {"tasks": [_task()]},
        evidence_decisions={},
        legacy_labels=legacy_labels,
    )

    assert view.accepted_task_ids == ()
    assert view.dependency_closed_completed_task_ids == ()
    assert {item.accepted for item in view.tasks} == {False}
    assert {
        diagnostic.source for diagnostic in view.diagnostics
        if diagnostic.code == "legacy_terminal_without_authority"
    } == {*source_types.values(), "finalize.json"}
    assert view.to_dict()["shadow"] is True
    assert view.to_dict()["read_only"] is True
    _assert_no_positive_actions(view.to_dict())


def test_raw_done_task_without_authority_records_does_not_complete_adapter_routes(
    tmp_path: Path,
) -> None:
    tasks = [_task()]

    assert corroborated_completed_task_ids(tasks, plan_dir=tmp_path) == set()
    assert scheduler_completed_ids(tasks, plan_dir=tmp_path) == set()
    assert effective_execute_completed_task_ids(tasks, plan_dir=tmp_path) == set()
    assert accepted_attempt_execution_projection(tasks, plan_dir=tmp_path) is None


def test_forged_accepted_validation_without_matching_envelope_is_rejected(
    tmp_path: Path,
) -> None:
    other_envelope = _result_envelope("T-other")
    _write_batch_artifact(
        tmp_path,
        task_id="T33",
        envelope=other_envelope,
        validation={
            "subject_id": "T33",
            "idempotency_key": "claim-key-T33",
            "envelope_digest": "sha256:forged-missing-envelope",
        },
    )

    decisions: dict[str, Any] = {}
    completed = effective_execute_completed_task_ids(
        [_task()],
        plan_dir=tmp_path,
        decisions=decisions,
    )
    projection = accepted_attempt_execution_projection([_task()], plan_dir=tmp_path)

    assert completed == set()
    assert projection is not None
    assert projection.view.accepted_task_ids == ()
    assert projection.view.dependency_closed_completed_task_ids == ()
    assert decisions["T33"].satisfied is False
    assert {
        diagnostic.source for diagnostic in projection.view.diagnostics
        if diagnostic.code == "legacy_terminal_without_authority"
    } == {"execute_batches/batch_1/tasks_d36c7be46cc2.json", "finalize.json"}


def test_out_of_scope_validated_row_selects_strict_projection_without_shadowing(
    tmp_path: Path,
) -> None:
    # A wave whose grant scope EXCLUDES T99 (scope is [T-other]) carries a
    # validated REJECTED row for T99 (subject_outside_dispatched_batch, no
    # envelope).  The validated row must STILL select the strict projection
    # (fail closed) — the scope gate must run after saw_validation_projection
    # detection — but it must never shadow or mint authority for T99.
    _write_batch_artifact(
        tmp_path,
        task_id="T-other",
        validation={
            "outcome": "rejected",
            "subject_id": "T-other",
            "reason": "worker_identity_mismatch",
            "envelope_digest": None,
        },
    )
    path = execute_batch_artifact_path(tmp_path, 1, ["T-other"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["task_updates"].append(
        {
            "task_id": "T99",
            "status": "done",
            "files_changed": ["src/T99.py"],
            "authority_generation_error": "attempt subject is outside dispatch scope",
            "authority_validation": {
                "outcome": "rejected",
                "entry_kind": "task_update",
                "entry_index": 1,
                "subject_id": "T99",
                "reason": "subject_outside_dispatched_batch",
                "idempotency_key": None,
                "envelope_digest": None,
                "source_path": str(path),
            },
        }
    )
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    decisions: dict[str, Any] = {}
    completed = effective_execute_completed_task_ids(
        [_task()],
        plan_dir=tmp_path,
        decisions=decisions,
    )
    projection = accepted_attempt_execution_projection(
        [_task()], plan_dir=tmp_path
    )

    # Strict projection is SELECTED (validated row seen)...
    assert projection is not None
    # ...but no authority is minted: T99 was out of scope and T33 has no
    # accepted envelope anywhere.
    assert projection.view.accepted_task_ids == ()
    assert projection.view.dependency_closed_completed_task_ids == ()
    assert completed == set()
    assert decisions["T33"].satisfied is False


def test_current_joined_source_records_are_required_for_positive_control(
    tmp_path: Path,
) -> None:
    envelope = _result_envelope("T33")
    _write_batch_artifact(tmp_path, task_id="T33", envelope=envelope)

    projection = accepted_attempt_execution_projection([_task()], plan_dir=tmp_path)
    completed = effective_execute_completed_task_ids([_task()], plan_dir=tmp_path)

    assert projection is not None
    assert projection.view.accepted_task_ids == ("T33",)
    assert projection.view.dependency_closed_completed_task_ids == ("T33",)
    assert completed == {"T33"}
    assert projection.view.to_dict()["read_only"] is True
