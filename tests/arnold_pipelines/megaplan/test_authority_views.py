from __future__ import annotations

from copy import deepcopy
import json

import pytest

from arnold_pipelines.megaplan.authority import (
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
    derive_publication_view,
    derive_runner_view,
)
from arnold_pipelines.megaplan._core import execute_batch_artifact_path
from arnold_pipelines.megaplan.authority.batch_scope import (
    DISPATCH_IDENTITY_KEY,
    RESULT_ENVELOPES_KEY,
)
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    accepted_attempt_execution_projection,
    effective_execute_completed_task_ids,
)
from arnold_pipelines.megaplan.orchestration.authority_readers import AuthorityDecision
from arnold_pipelines.megaplan.orchestration.evidence_contract import EvidenceStatus
from arnold_pipelines.run_authority import (
    CASExpectation,
    ContractError,
    CoordinatorFence,
    EvidenceEnvelope,
    IdempotencyKey,
    QuarantineRecord,
    reduce_run_authority,
)


RUN = "plan-1"
REVISION = "revision-7"


def _records(task_id: str = "T1"):
    evidence = EvidenceEnvelope(
        f"evidence-{task_id}", RUN, REVISION, "pytest", f"reports/{task_id}.json", {"passed": True}
    )
    fence = CoordinatorFence(RUN, REVISION, "coordinator-1", 4)
    grant = DispatchGrant(
        f"dispatch-{task_id}", RUN, REVISION, "coordinator-1", 4,
        (task_id,), (TASK_RESULT_CAPABILITY,), (evidence.evidence_id,),
    )
    attempt = TaskAttempt(
        f"attempt-{task_id}", RUN, REVISION, task_id, grant.grant_id,
        "coordinator-1", 4, 1,
    )
    claim = TaskClaim(
        f"claim-{task_id}", RUN, REVISION, task_id, attempt.attempt_id,
        grant.grant_id, "coordinator-1", 4, TASK_COMPLETION_CLAIM,
        (evidence.evidence_id,), f"claim-key-{task_id}", {"status": "done"},
    )
    decision = TaskValidationDecision(
        f"decision-{task_id}", RUN, REVISION, task_id, attempt.attempt_id,
        grant.grant_id, "coordinator-1", 4, claim.claim_id, "accepted",
        (evidence.evidence_id,), f"decision-key-{task_id}", {"reason": "tests_passed"},
    )
    return (
        evidence, fence, grant, attempt,
        IdempotencyKey(claim.idempotency_key, claim.payload_hash), claim,
        IdempotencyKey(decision.idempotency_key, decision.payload_hash), decision,
    )


def _satisfied(task_id: str) -> AuthorityDecision:
    return AuthorityDecision(
        task_id=task_id,
        status=EvidenceStatus.satisfied,
        satisfied=True,
        diagnostics={"source": f"reports/{task_id}.json"},
    )


def _task_states_by_id(view):
    return {item.task_id: item for item in view.tasks}


def _write_validated_attempt_artifact(
    plan_dir,
    *,
    task_id: str,
    outcome: str = "accepted",
    batch_number: int = 1,
    with_cas: bool = False,
) -> ResultEnvelope:
    evidence, fence, grant, attempt, _claim_key, claim, *_ = _records(task_id)
    dispatch = DispatchIdentity.from_records(
        grant,
        fence,
        prerequisite_digest="digest-1",
        worker_id="worker-1",
        cas_expectation=(
            CASExpectation(RUN, REVISION, 3)
            if with_cas
            else None
        ),
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
            "outcome": outcome,
            "entry_kind": "task_update",
            "entry_index": 0,
            "subject_id": task_id,
            "reason": (
                "task_update_authority_valid"
                if outcome == "accepted"
                else "worker_identity_mismatch"
            ),
            "idempotency_key": claim.idempotency_key,
            "envelope_digest": envelope.digest(),
            "source_path": "execute_batches/batch_1/tasks.json",
        },
    }
    path = execute_batch_artifact_path(plan_dir, batch_number, [task_id])
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


def test_megaplan_wrappers_retain_generic_wire_contract_and_reject_other_policy() -> None:
    records = _records()
    grant, attempt, claim, decision = records[2], records[3], records[5], records[7]

    assert grant.contract_type == "capability_grant"
    assert grant.dispatch_id == "dispatch-T1"
    assert attempt.task_id == claim.task_id == decision.task_id == "T1"
    assert TaskClaim.from_json(claim.to_json()) == claim

    with pytest.raises(ContractError, match="unsupported Megaplan dispatch"):
        DispatchGrant("g", RUN, REVISION, "c", 1, ("T1",), ("generic.shell",))


def test_plan_execution_accepts_only_kernel_and_megaplan_evidence_intersection() -> None:
    records = _records("T1") + _records("T3")
    quarantine = QuarantineRecord(
        "q-stale", RUN, REVISION, "claim", "claim-stale", "missing_matching_revision",
        "execute_batches/batch_2/tasks.json", (), {"task_id": "T2"},
    )
    authority = reduce_run_authority((*records, quarantine), run_id=RUN, run_revision=REVISION)
    plan = {"tasks": [
        {"id": "T2", "status": "done", "depends_on": ["T1"]},
        {"id": "T1", "status": "pending", "depends_on": []},
        {"id": "T3", "status": "done", "depends_on": ["T1"]},
    ]}

    view = derive_plan_execution_view(
        authority,
        plan,
        evidence_decisions={"T1": _satisfied("T1")},
        legacy_labels=(
            LegacyTaskLabel("T2", "completed", "state.json", "observation"),
            LegacyTaskLabel("T2", "done", "execute_batches/batch_2/tasks.json"),
        ),
    )

    assert view.accepted_task_ids == ("T1",)
    assert {item.task_id: item.accepted for item in view.tasks} == {
        "T1": True, "T2": False, "T3": False,
    }
    assert "q-stale" in view.quarantine_ids
    assert any(
        item.code == "legacy_terminal_without_authority" and item.source == "state.json"
        for item in view.diagnostics
    )
    assert any(
        item.code == "kernel_policy_disagreement"
        and item.source == "contract://decision/decision-T3"
        for item in view.diagnostics
    )
    assert any(
        item.code == "quarantined_authority_record"
        and item.source == "execute_batches/batch_2/tasks.json"
        for item in view.diagnostics
    )
    assert view.to_dict()["shadow"] is view.to_dict()["read_only"] is True


def test_plan_execution_projection_is_deterministic_idempotent_and_read_only() -> None:
    authority = reduce_run_authority(_records(), run_id=RUN, run_revision=REVISION, journal_cursor=8)
    plan = {"tasks": [
        {"id": "T2", "depends_on": ["T1"], "status": "pending"},
        {"id": "T1", "depends_on": [], "status": "done"},
    ]}
    original = deepcopy(plan)
    labels = (
        LegacyTaskLabel("T1", "done", "state.json", "observation"),
        LegacyTaskLabel("T1", "done", "execute_batches/batch_1/tasks.json"),
    )

    first = derive_plan_execution_view(
        authority, plan, evidence_decisions={"T1": _satisfied("T1")}, legacy_labels=labels
    )
    second = derive_plan_execution_view(
        authority,
        {"tasks": list(reversed(plan["tasks"]))},
        evidence_decisions={"T1": _satisfied("T1")},
        legacy_labels=reversed(labels),
    )

    assert first == second
    assert first.to_json() == second.to_json()
    assert len(first.view_hash) == 64
    assert plan == original
    assert first.accepted_task_ids == ("T1",)


def test_plan_execution_derives_dependency_closure_and_ready_wave_from_accepted_attempts() -> None:
    authority = reduce_run_authority(
        _records("T5") + _records("T2") + _records("T1"),
        run_id=RUN,
        run_revision=REVISION,
    )
    plan = {"tasks": [
        {"id": "T1", "status": "done", "depends_on": []},
        {"id": "T2", "status": "done", "depends_on": ["T1"]},
        {"id": "T3", "status": "done", "depends_on": ["T2"]},
        {"id": "T4", "status": "pending", "depends_on": ["T2"]},
        {"id": "T5", "status": "done", "depends_on": ["T3"]},
    ]}

    view = derive_plan_execution_view(
        authority,
        plan,
        evidence_decisions={
            "T1": _satisfied("T1"),
            "T2": _satisfied("T2"),
            "T5": _satisfied("T5"),
        },
    )
    states = _task_states_by_id(view)

    assert view.accepted_task_ids == ("T1", "T2", "T5")
    assert [
        (item.task_id, item.attempt_id, item.claim_id, item.decision_id, item.grant_id)
        for item in view.accepted_task_attempts
    ] == [
        ("T1", "attempt-T1", "claim-T1", "decision-T1", "dispatch-T1"),
        ("T2", "attempt-T2", "claim-T2", "decision-T2", "dispatch-T2"),
        ("T5", "attempt-T5", "claim-T5", "decision-T5", "dispatch-T5"),
    ]
    assert [item.source_paths for item in view.accepted_task_attempts] == [
        ("reports/T1.json",),
        ("reports/T2.json",),
        ("reports/T5.json",),
    ]
    assert view.dependency_closed_completed_task_ids == ("T1", "T2")
    assert view.next_ready_wave == ("T3", "T4")

    assert states["T1"].dependency_closed is True
    assert states["T2"].dependency_closed is True
    assert states["T5"].accepted is True
    assert states["T5"].dependency_closed is False
    assert states["T5"].accepted_attempt_ids == ("attempt-T5",)
    assert states["T5"].unresolved_dependency_ids == ("T3",)
    assert states["T3"].accepted is False
    assert states["T3"].dependency_closed is False

    diagnostics = {(item.code, item.subject_id) for item in view.diagnostics}
    assert ("accepted_task_dependency_unresolved", "T5") in diagnostics
    assert ("unresolved_dependency", "T5") in diagnostics
    assert ("legacy_terminal_without_authority", "T3") in diagnostics


def test_plan_execution_preserves_existing_fields_claims_quarantine_and_diagnostics() -> None:
    unresolved_records = _records("T1")
    bad_claim_records = _records("T2")
    quarantine = QuarantineRecord(
        "q-stale", RUN, REVISION, "claim", "claim-stale", "missing_matching_revision",
        "execute_batches/batch_2/tasks.json", (), {"task_id": "T-stale"},
    )
    authority = reduce_run_authority(
        unresolved_records[:-1] + bad_claim_records[4:6] + (quarantine,),
        run_id=RUN,
        run_revision=REVISION,
    )

    view = derive_plan_execution_view(
        authority,
        {"tasks": [
            {"id": "T1", "status": "done", "depends_on": []},
            {"id": "T2", "status": "pending", "depends_on": ["T1"]},
        ]},
        evidence_decisions={"T1": _satisfied("T1"), "T2": _satisfied("T2")},
    )
    states = _task_states_by_id(view)
    payload = view.to_dict()

    assert view.accepted_task_ids == ()
    assert view.accepted_task_attempts == ()
    assert view.dependency_closed_completed_task_ids == ()
    assert view.next_ready_wave == ("T1",)
    assert view.unresolved_claim_ids == ("claim-T1",)
    assert states["T1"].unresolved_claim_ids == ("claim-T1",)
    assert states["T2"].unresolved_dependency_ids == ("T1",)
    assert "q-stale" in view.quarantine_ids
    assert payload["accepted_task_ids"] == []
    assert payload["accepted_task_attempts"] == []
    assert payload["dependency_closed_completed_task_ids"] == []
    assert payload["next_ready_wave"] == ["T1"]

    diagnostics = {(item.code, item.subject_id, item.source) for item in view.diagnostics}
    assert ("legacy_terminal_without_authority", "T1", "finalize.json") in diagnostics
    assert (
        "quarantined_authority_record",
        "claim-stale",
        "execute_batches/batch_2/tasks.json",
    ) in diagnostics
    assert ("quarantined_incomplete_link", "claim-T2", "contract://claim/claim-T2") in diagnostics


def test_execute_scheduler_prefers_accepted_attempt_projection(tmp_path) -> None:
    envelope = _write_validated_attempt_artifact(tmp_path, task_id="T1")
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

    projection = accepted_attempt_execution_projection(tasks, plan_dir=tmp_path)
    completed = effective_execute_completed_task_ids(tasks, plan_dir=tmp_path)

    assert projection is not None
    assert projection.view.accepted_task_ids == ("T1",)
    assert projection.view.dependency_closed_completed_task_ids == ("T1",)
    assert projection.view.next_ready_wave == ("T2",)
    assert projection.view.accepted_task_attempts[0].attempt_id == envelope.attempt.attempt_id
    assert completed == {"T1"}


def test_accepted_attempt_projection_treats_cas_as_dispatch_precondition(
    tmp_path,
) -> None:
    envelope = _write_validated_attempt_artifact(
        tmp_path,
        task_id="T1",
        with_cas=True,
    )
    tasks = [
        {"id": "T1", "status": "pending", "depends_on": []},
        {"id": "T2", "status": "pending", "depends_on": ["T1"]},
    ]

    projection = accepted_attempt_execution_projection(tasks, plan_dir=tmp_path)

    assert projection is not None
    assert projection.view.accepted_task_ids == ("T1",)
    assert projection.view.dependency_closed_completed_task_ids == ("T1",)
    assert projection.view.next_ready_wave == ("T2",)
    assert projection.view.accepted_task_attempts[0].attempt_id == envelope.attempt.attempt_id


def test_execute_scheduler_rejected_projection_prevents_raw_done_fallback(tmp_path) -> None:
    _write_validated_attempt_artifact(tmp_path, task_id="T1", outcome="rejected")
    tasks = [
        {
            "id": "T1",
            "status": "done",
            "depends_on": [],
            "files_changed": ["src/T1.py"],
            "head_sha": "abc123",
        },
    ]
    decisions: dict[str, AuthorityDecision] = {}

    completed = effective_execute_completed_task_ids(
        tasks,
        plan_dir=tmp_path,
        decisions=decisions,
    )

    assert completed == set()
    assert decisions["T1"].status is EvidenceStatus.unknown
    assert decisions["T1"].diagnostics["execute_completion"] == "accepted_attempt_projection"


def test_raw_terminal_labels_and_unresolved_claims_never_complete_tasks() -> None:
    records = _records()
    authority = reduce_run_authority(records[:-1], run_id=RUN, run_revision=REVISION)

    view = derive_plan_execution_view(
        authority,
        {"tasks": [{"id": "T1", "status": "done"}, {"id": "T2", "status": "skipped"}]},
        evidence_decisions={"T1": _satisfied("T1"), "T2": _satisfied("T2")},
    )

    assert view.accepted_task_ids == ()
    assert view.unresolved_claim_ids == ("claim-T1",)
    assert all(not item.accepted for item in view.tasks)
    assert {item.source for item in view.diagnostics if item.code == "legacy_terminal_without_authority"} == {
        "finalize.json"
    }


def test_runner_view_preserves_liveness_states_without_execution_authority() -> None:
    stopped = derive_runner_view(({
        "id": "session-1", "type": "session", "source": "cloud/session.json",
        "status": "stopped", "identity": "runner-1",
    },), expected_identity="runner-1")
    live = derive_runner_view((
        {
            "id": "process-1", "type": "process", "source": "cloud/process.json",
            "status": "running", "identity": "runner-1",
        },
        {
            "id": "heartbeat-1", "type": "heartbeat", "source": "cloud/heartbeat.json",
            "age_seconds": 12, "identity": "runner-1",
        },
    ), expected_identity="runner-1")
    stale = derive_runner_view(({
        "id": "heartbeat-2", "type": "heartbeat", "source": "cloud/heartbeat.json",
        "age_seconds": 301, "identity": "runner-1",
    },), expected_identity="runner-1")
    mismatch = derive_runner_view(({
        "id": "session-2", "type": "session", "source": "cloud/session.json",
        "status": "running", "identity": "runner-other",
    },), expected_identity="runner-1")
    unknown = derive_runner_view(({
        "id": "session-3", "type": "session", "source": "cloud/session.json",
        "status": "indeterminate",
    },))

    assert [view.status for view in (stopped, live, stale, mismatch, unknown)] == [
        "stopped", "live", "stale", "identity_mismatch", "unknown",
    ]
    assert stopped.to_dict()["shadow"] is stopped.to_dict()["read_only"] is True
    assert all("accepted_task_ids" not in view.to_dict() for view in (stopped, live, stale, mismatch, unknown))
    assert {item.code for item in stale.diagnostics} == {"stale_heartbeat"}
    assert {item.source for item in mismatch.diagnostics} == {"cloud/session.json"}
    assert {item.code for item in unknown.diagnostics} == {"runner_unknown"}


def test_runner_view_is_deterministic_and_retains_identity_contradictions() -> None:
    observations = (
        {
            "type": "heartbeat", "source": "cloud/heartbeat.json", "age_seconds": 3,
            "identity": "runner-1", "expected_identity": "runner-1",
        },
        {
            "id": "process", "type": "process", "source": "cloud/process.json",
            "status": "alive", "identity": "runner-2", "expected_identity": "runner-2",
        },
    )

    first = derive_runner_view(observations)
    second = derive_runner_view(reversed(observations))

    assert first == second
    assert first.to_json() == second.to_json()
    assert len(first.view_hash) == 64
    assert first.status == "identity_mismatch"
    assert {item.code for item in first.diagnostics} == {"runner_identity_mismatch"}
    assert set(first.source_paths) == {"cloud/heartbeat.json", "cloud/process.json"}


def test_publication_view_keeps_observations_unknowns_and_blockers_separate() -> None:
    blocked = derive_publication_view((
        {"type": "git_branch", "source": "git/HEAD", "value": "feature/authority"},
        {"type": "workspace", "source": "git/status", "value": False},
        {"type": "push", "source": "git/remote", "value": "a" * 40},
        {"type": "pull_request", "source": "github/pr.json", "value": "https://example.test/pr/7"},
        {"type": "auth", "source": "github/auth", "value": True},
        {"type": "no_push", "source": "chain/command", "value": True},
    ))
    incomplete = derive_publication_view((
        {"branch": "feature/authority", "source": "git/HEAD"},
    ))

    assert blocked.status == "blocked"
    assert blocked.to_dict()["shadow"] is blocked.to_dict()["read_only"] is True
    assert {item.field for item in blocked.observations} == {
        "branch", "branch_ancestry", "dirty_workspace", "pushed_sha", "pull_request", "auth", "no_push",
    }
    assert {item.code for item in blocked.diagnostics} == {"no_push_configured", "publication_observation_unknown"}
    assert "chain/command" in blocked.source_paths
    unknown = {item.field for item in incomplete.observations if item.state == "unknown"}
    assert unknown == {"branch_ancestry", "dirty_workspace", "pushed_sha", "pull_request", "auth", "no_push"}
    assert incomplete.status == "unknown"
    assert all("accepted_task_ids" not in view.to_dict() for view in (blocked, incomplete))


def test_publication_view_is_deterministic_and_preserves_source_contradictions() -> None:
    observations = (
        {"branch": "feature/a", "source": "git/HEAD"},
        {"branch": "feature/b", "source": "chain/state.json"},
        {"dirty_workspace": False, "source": "git/status"},
        {"pushed_sha": "a" * 40, "source": "git/remote"},
        {"pr_url": "https://example.test/pr/7", "source": "github/pr.json"},
        {"authenticated": True, "source": "github/auth"},
        {"no_push": False, "source": "chain/command"},
    )

    first = derive_publication_view(observations)
    second = derive_publication_view(reversed(observations))

    assert first == second
    assert first.to_json() == second.to_json()
    assert len(first.view_hash) == 64
    assert first.status == "contradicted"
    branch = next(item for item in first.observations if item.field == "branch")
    assert branch.state == "contradicted"
    assert branch.source == "chain/state.json,git/HEAD"
    diagnostic = next(item for item in first.diagnostics if item.code == "publication_observation_contradiction")
    assert diagnostic.field == "branch"
    assert diagnostic.source == "chain/state.json,git/HEAD"


def test_publication_blocked_is_independent_of_execution_and_runner_views() -> None:
    authority = reduce_run_authority(_records(), run_id=RUN, run_revision=REVISION)
    execution = derive_plan_execution_view(
        authority,
        {"tasks": [{"id": "T1", "status": "done"}]},
        evidence_decisions={"T1": _satisfied("T1")},
    )
    runner = derive_runner_view(({
        "type": "process", "source": "cloud/process.json", "status": "stopped",
    },))
    publication = derive_publication_view((
        {"branch": "feature/authority", "source": "git/HEAD"},
        {"dirty_workspace": True, "source": "git/status"},
        {"pushed_sha": "a" * 40, "source": "git/remote"},
        {"pr_url": "https://example.test/pr/7", "source": "github/pr.json"},
        {"authenticated": True, "source": "github/auth"},
        {"no_push": False, "source": "chain/command"},
    ))

    assert execution.accepted_task_ids == ("T1",)
    assert runner.status == "stopped"
    assert publication.status == "blocked"
    assert publication.view_hash not in {execution.view_hash, runner.view_hash}


# ---------------------------------------------------------------------------
# derive_megaplan_recovery_view — recovery/repair custody projection
# ---------------------------------------------------------------------------


from arnold_pipelines.megaplan.authority import (
    derive_megaplan_recovery_view,
    MegaplanRecoveryView,
    RecoveryCustodyObservation,
    PermittedAction,
    RecoveryDiagnostic,
)


def _r_custody(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "custody_bucket": "repairable_not_repairing",
        "blocker_id": "blocker-99",
        "current_state": "blocked",
        "retry_strategy": "manual_review",
        "failure_kind": "execution_blocked",
        "active_request_ids": ["req-1"],
    }
    result.update(overrides)
    return result


def test_derive_recovery_view_repairable_with_custody() -> None:
    """Recovery view derives correctly from a repairable custody projection."""
    view = derive_megaplan_recovery_view(repair_custody=_r_custody())
    assert isinstance(view, MegaplanRecoveryView)
    assert view.status == "repairable"
    assert view.recovery_needed is True
    assert view.custody_bucket == "repairable_not_repairing"
    assert len(view.observations) == 1
    assert view.observations[0].custody_bucket == "repairable_not_repairing"
    assert view.observations[0].active_request_count == 1


def test_derive_recovery_view_rejects_bucket_only_repairing() -> None:
    """A repairing label with no durable owner/attempt is only advisory."""
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(custody_bucket="repairing", active_request_ids=[])
    )
    assert view.status == "healthy"
    assert view.recovery_needed is False
    assert any(d.code == "unsupported_repairing_custody" for d in view.diagnostics)


def test_derive_recovery_view_repairing_with_durable_attempt() -> None:
    """A linked nonterminal durable attempt yields repairing status."""
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(
            custody_bucket="repairing",
            active_request_ids=["req-1"],
            attempts=[{
                "attempt_id": "attempt-1",
                "request_id": "req-1",
                "source": "repair_queue_dispatch_attempt",
                "path": "/durable/attempt-1.json",
                "terminal": False,
            }],
        )
    )
    assert view.status == "repairing"
    assert view.recovery_needed is True
    assert view.custody_bucket == "repairing"


def test_derive_recovery_view_human_required() -> None:
    """Human-required custody yields human_required status."""
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(custody_bucket="human_required")
    )
    assert view.status == "human_required"
    assert view.recovery_needed is True


def test_derive_recovery_view_broken_superfixer() -> None:
    """Broken superfixer custody yields broken_superfixer status."""
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(custody_bucket="broken_superfixer")
    )
    assert view.status == "broken_superfixer"
    assert view.recovery_needed is True


def test_derive_recovery_view_healthy_when_no_evidence() -> None:
    """Empty custody (no bucket match → no distress) yields healthy."""
    view = derive_megaplan_recovery_view(repair_custody={"custody_bucket": "some_unknown_value"})
    assert view.status == "healthy"
    assert view.recovery_needed is False


def test_derive_recovery_view_unknown_without_custody() -> None:
    """None custody yields unknown status with custody_unavailable diagnostic."""
    view = derive_megaplan_recovery_view(repair_custody=None)
    assert view.status == "unknown"
    assert view.recovery_needed is False
    assert view.custody_bucket is None
    assert any(d.code == "custody_unavailable" for d in view.diagnostics)


def test_derive_recovery_view_permitted_actions_repairable() -> None:
    """Repairable custody yields repair_dispatch + retry permitted actions."""
    view = derive_megaplan_recovery_view(repair_custody=_r_custody())
    action_types = {a.action_type for a in view.permitted_actions}
    assert "repair_dispatch" in action_types
    assert "retry" in action_types


def test_derive_recovery_view_permitted_actions_human_required() -> None:
    """Human-required custody yields human_escalation permitted action."""
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(custody_bucket="human_required")
    )
    action_types = {a.action_type for a in view.permitted_actions}
    assert "human_escalation" in action_types


def test_derive_recovery_view_permitted_actions_broken() -> None:
    """Broken superfixer yields investigate_superfixer + human_escalation."""
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(custody_bucket="broken_superfixer")
    )
    action_types = {a.action_type for a in view.permitted_actions}
    assert "investigate_superfixer" in action_types
    assert "human_escalation" in action_types


def test_derive_recovery_view_deterministic_hashing() -> None:
    """Same inputs produce same view_hash and observations."""
    custody = _r_custody()
    v1 = derive_megaplan_recovery_view(repair_custody=custody)
    v2 = derive_megaplan_recovery_view(repair_custody=dict(custody))
    assert v1.view_hash == v2.view_hash
    assert v1.status == v2.status
    assert len(v1.observations) == len(v2.observations)


def test_derive_recovery_view_observations_order_independent() -> None:
    """Recovery view observations are sorted (insertion order irrelevant)."""
    v1 = derive_megaplan_recovery_view(repair_custody=_r_custody())
    v2 = derive_megaplan_recovery_view(repair_custody=_r_custody())
    assert v1.observations == v2.observations


def test_derive_recovery_view_json_roundtrip() -> None:
    """MegaplanRecoveryView survives JSON serialization round-trip."""
    import json as _json
    view = derive_megaplan_recovery_view(repair_custody=_r_custody())
    dumped = view.to_json()
    loaded = _json.loads(dumped)
    assert loaded["status"] == "repairable"
    assert loaded["recovery_needed"] is True
    assert loaded["custody_bucket"] == "repairable_not_repairing"
    assert loaded["shadow"] is True
    assert loaded["read_only"] is True


def test_derive_recovery_view_custody_unknown_bucket_is_healthy() -> None:
    """Unrecognized custody bucket not in the known set defaults to healthy."""
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(custody_bucket="garbage_bucket")
    )
    assert view.status == "healthy"


def test_derive_recovery_view_stale_active_steps_diagnostic() -> None:
    """Stale active-step observations produce a stale_active_steps diagnostic."""
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(),
        active_step_observations=[
            {"source": "step/1", "stale": True},
            {"source": "step/2", "stale": True},
            {"source": "step/3", "stale": False},
        ],
    )
    assert any(d.code == "stale_active_steps" for d in view.diagnostics)


def test_derive_recovery_view_runner_blocked_diagnostic() -> None:
    """A stopped runner produces a runner_unavailable diagnostic and blocked status."""
    from arnold_pipelines.megaplan.authority.views import RunnerView, RunnerObservation

    obs = RunnerObservation(
        observation_id="obs-1", observation_type="process",
        source="cloud/process.json", state="stopped",
    )
    runner = RunnerView(
        schema_version=1, status="stopped", expected_identity=None,
        observations=(obs,), source_paths=("cloud/process.json",),
        diagnostics=(), view_hash="hash-1",
    )
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(custody_bucket="repairable_not_repairing"),
        runner_view=runner,
    )
    assert view.status == "blocked"
    assert any(d.code == "runner_unavailable" for d in view.diagnostics)


def test_derive_recovery_view_human_gate_blocked_diagnostic() -> None:
    """A blocked human gate produces a human_gate_blocked diagnostic."""
    from arnold_pipelines.megaplan.authority.views import HumanGateView, HumanGateObservation

    hobs = HumanGateObservation(
        observation_id="hobs-1", gate_type="needs_human",
        gate_reason="manual review", source="markers/needs_human.json",
    )
    hgv = HumanGateView(
        schema_version=1, status="blocked", human_required=True,
        typed_gate="needs_human", observations=(hobs,),
        source_paths=("markers/needs_human.json",), diagnostics=(), view_hash="hg-hash",
    )
    view = derive_megaplan_recovery_view(
        repair_custody=_r_custody(custody_bucket="repairable_not_repairing"),
        human_gate_view=hgv,
    )
    assert view.status == "blocked"
    assert any(d.code == "human_gate_blocked" for d in view.diagnostics)
