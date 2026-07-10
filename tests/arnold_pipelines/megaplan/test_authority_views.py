from __future__ import annotations

from copy import deepcopy

import pytest

from arnold_pipelines.megaplan.authority import (
    DispatchGrant,
    LegacyTaskLabel,
    TASK_COMPLETION_CLAIM,
    TASK_RESULT_CAPABILITY,
    TaskAttempt,
    TaskClaim,
    TaskValidationDecision,
    derive_plan_execution_view,
    derive_publication_view,
    derive_runner_view,
)
from arnold_pipelines.megaplan.orchestration.authority_readers import AuthorityDecision
from arnold_pipelines.megaplan.orchestration.evidence_contract import EvidenceStatus
from arnold_pipelines.run_authority import (
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
        "branch", "dirty_workspace", "pushed_sha", "pull_request", "auth", "no_push",
    }
    assert {item.code for item in blocked.diagnostics} == {"no_push_configured"}
    assert "chain/command" in blocked.source_paths
    unknown = {item.field for item in incomplete.observations if item.state == "unknown"}
    assert unknown == {"dirty_workspace", "pushed_sha", "pull_request", "auth", "no_push"}
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
