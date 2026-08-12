from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping

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
    ObservationEnvelope,
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

    # Raw mappings are UNKNOWN-typed evidence: they preserve the observable
    # non-green states (stopped/stale/identity mismatch) but can never
    # authorize ``live`` (``running``/``indeterminate`` degrade to pending).
    assert [view.status for view in (stopped, live, stale, mismatch, unknown)] == [
        "stopped", "pending", "stale", "identity_mismatch", "pending",
    ]
    assert stopped.to_dict()["shadow"] is stopped.to_dict()["read_only"] is True
    assert all("accepted_task_ids" not in view.to_dict() for view in (stopped, live, stale, mismatch, unknown))
    assert {item.code for item in stale.diagnostics} == {"stale_heartbeat", "non_coherent_observation"}
    assert {item.source for item in mismatch.diagnostics} == {"cloud/session.json"}
    assert {item.code for item in unknown.diagnostics} == {"runner_unknown", "non_coherent_observation"}


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
    assert {item.code for item in first.diagnostics} == {
        "runner_identity_mismatch", "non_coherent_observation",
    }
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
    assert {item.code for item in blocked.diagnostics} == {
        "no_push_configured", "publication_observation_unknown", "non_coherent_observation",
    }
    assert "chain/command" in blocked.source_paths
    unknown = {item.field for item in incomplete.observations if item.state == "unknown"}
    assert unknown == {"branch_ancestry", "dirty_workspace", "pushed_sha", "pull_request", "auth", "no_push"}
    # A raw mapping can report fields but never authorizes ``ready``; without a
    # coherence claim the incomplete view degrades from ``unknown`` to ``pending``.
    assert incomplete.status == "pending"
    assert {"non_coherent_observation"} <= {item.code for item in incomplete.diagnostics}
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


_RUNTIME_CAPTURE = {
    "recorded_engine_root": "/opt/arnold/engine",
    "manifest_runtime_root": "/opt/arnold/engine",
    "manifest_expected_head": "expected-head-1",
    "live_import_root": "/opt/arnold/engine",
    "wrapper_digest": "wrapper-digest-1",
    "dependency_generation": "generation-1",
    "environment_identity": "env-1",
    "session_identity": "env-1",
}

_PUBLICATION_PAYLOAD = {
    "branch": "feature/authority",
    "branch_ancestry": "valid",
    "dirty_workspace": False,
    "pushed_sha": "a" * 40,
    "pull_request": "https://example.test/pr/7",
    "auth": True,
    "no_push": False,
}


def _envelope(
    observation_id: str,
    *,
    observation_type: str,
    source: str,
    payload: Mapping[str, Any],
    run_id: str = RUN,
    run_revision: str = REVISION,
    source_cursor: int | None = 5,
    runtime_capture: Mapping[str, Any] | None = None,
) -> ObservationEnvelope:
    """A coherent current capture envelope unless overridden (stale/non-coherent)."""

    return ObservationEnvelope.capture(
        observation_id=observation_id,
        run_id=run_id,
        run_revision=run_revision,
        observation_type=observation_type,
        source=source,
        payload=dict(payload),
        runtime_observation=_RUNTIME_CAPTURE if runtime_capture is None else runtime_capture,
        source_identity="test-source",
        source_version="test-version",
        source_cursor=source_cursor,
        content_hash="a" * 64,
    )


def _publication_envelope(
    observation_id: str, *, payload: Mapping[str, Any] | None = None, **overrides: Any,
) -> ObservationEnvelope:
    return _envelope(
        observation_id,
        observation_type="publication",
        source=f"envelope://publication/{observation_id}",
        payload=_PUBLICATION_PAYLOAD if payload is None else payload,
        **overrides,
    )


def _runner_envelope(
    observation_id: str, *, state: str = "running", payload: Mapping[str, Any] | None = None, **overrides: Any,
) -> ObservationEnvelope:
    return _envelope(
        observation_id,
        observation_type="process",
        source=f"envelope://runner/{observation_id}",
        payload=(
            {"state": state, "identity": "runner-1", "expected_identity": "runner-1"}
            if payload is None else payload
        ),
        **overrides,
    )


def test_publication_view_coherent_current_envelope_is_ready() -> None:
    view = derive_publication_view(
        (_publication_envelope("pub-ready"),),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "ready"
    assert all(item.state == "known" for item in view.observations)
    assert view.diagnostics == ()


def test_publication_view_gates_non_coherent_envelopes_never_ready() -> None:
    unknown_capture = dict(_RUNTIME_CAPTURE)
    unknown_capture.pop("wrapper_digest")
    incoherent_capture = dict(_RUNTIME_CAPTURE)
    incoherent_capture["live_import_root"] = "/opt/arnold/other"

    unknown = _publication_envelope("pub-unknown", runtime_capture=unknown_capture)
    incoherent = _publication_envelope("pub-incoherent", runtime_capture=incoherent_capture)
    assert unknown.coherence == "UNKNOWN"
    assert incoherent.coherence == "INCOHERENT"
    assert unknown.is_dispatchable is False
    assert incoherent.is_dispatchable is False

    # The coherence gate applies even without an explicit run context.
    no_context = derive_publication_view((unknown,))
    gated = derive_publication_view((unknown, incoherent), run_id=RUN, run_revision=REVISION, journal_cursor=10)

    for view in (no_context, gated):
        assert view.status != "ready"
        assert view.status == "pending"
        assert all(item.state == "unknown" for item in view.observations)
        assert {"non_coherent_observation"} <= {item.code for item in view.diagnostics}


def test_publication_view_gates_stale_envelopes_never_ready() -> None:
    stale_revision = _publication_envelope("pub-old-revision", run_revision="revision-old")
    stale_cursor = _publication_envelope("pub-beyond-journal", source_cursor=50)
    wrong_run = _publication_envelope("pub-other-run", run_id="plan-other")

    views = tuple(
        derive_publication_view((observation,), run_id=RUN, run_revision=REVISION, journal_cursor=10)
        for observation in (stale_revision, stale_cursor, wrong_run)
    )
    for view in views:
        assert view.status != "ready"
        assert view.status == "pending"
        assert {"stale_observation"} <= {item.code for item in view.diagnostics}


def test_publication_view_never_ready_when_any_envelope_gated() -> None:
    view = derive_publication_view(
        (
            _publication_envelope("pub-ready"),
            _publication_envelope("pub-stale", run_revision="revision-old"),
        ),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "pending"
    assert {item.code for item in view.diagnostics} == {"stale_observation"}


def test_runner_view_coherent_current_envelope_is_live() -> None:
    view = derive_runner_view(
        (_runner_envelope("run-live"),),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "live"
    assert len(view.observations) == 1
    assert view.diagnostics == ()


def test_runner_view_gates_non_coherent_and_stale_envelopes_never_live() -> None:
    unknown_capture = dict(_RUNTIME_CAPTURE)
    unknown_capture.pop("wrapper_digest")
    incoherent_capture = dict(_RUNTIME_CAPTURE)
    incoherent_capture["live_import_root"] = "/opt/arnold/other"

    unknown = _runner_envelope("run-unknown", runtime_capture=unknown_capture)
    incoherent = _runner_envelope("run-incoherent", runtime_capture=incoherent_capture)
    stale_revision = _runner_envelope("run-old-revision", run_revision="revision-old")
    stale_cursor = _runner_envelope("run-beyond-journal", source_cursor=50)

    assert unknown.coherence == "UNKNOWN"
    assert incoherent.coherence == "INCOHERENT"

    # The coherence gate applies even without an explicit run context.
    no_context = derive_runner_view((unknown,))
    for observation in (unknown, incoherent, stale_revision, stale_cursor):
        view = derive_runner_view((observation,), run_id=RUN, run_revision=REVISION, journal_cursor=10)
        assert view.status != "live"
        assert view.status == "pending"
        assert view.observations == ()
    assert no_context.status == "pending"
    assert {item.code for item in no_context.diagnostics} == {"non_coherent_observation", "runner_unknown"}
    assert {item.code for item in derive_runner_view(
        (stale_revision,), run_id=RUN, run_revision=REVISION, journal_cursor=10,
    ).diagnostics} == {"stale_observation", "runner_unknown"}


def test_runner_view_never_live_when_any_envelope_gated() -> None:
    view = derive_runner_view(
        (
            _runner_envelope("run-live"),
            _runner_envelope("run-stale", run_revision="revision-old"),
        ),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "pending"
    assert {item.code for item in view.diagnostics} == {"stale_observation"}


def test_runner_view_never_live_from_stale_payload_envelope() -> None:
    """A coherent envelope whose OWN payload is stale is stale evidence."""
    # A coherent ``process`` observation (state=running) that declares itself
    # stale must never authorize ``live`` — the payload-stale gate applies to
    # every observation type, not just heartbeats.
    stale_payload = _runner_envelope("run-stale-payload", payload={
        "state": "running", "identity": "runner-1", "expected_identity": "runner-1", "stale": True,
    })
    assert stale_payload.coherence == "COHERENT"
    assert stale_payload.is_dispatchable is True

    view = derive_runner_view(
        (stale_payload,),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status != "live"
    assert view.status == "pending"
    # Gated envelopes are excluded from the projection entirely.
    assert view.observations == ()
    assert {item.code for item in view.diagnostics} == {"stale_observation", "runner_unknown"}
    assert any(
        item.code == "stale_observation" and item.reason == "observation_payload_stale"
        for item in view.diagnostics
    )

    # The ``stale_heartbeats`` alias marks the same stale evidence.
    stale_heartbeats = _runner_envelope("run-stale-heartbeats", payload={
        "state": "running", "identity": "runner-1", "expected_identity": "runner-1",
        "stale_heartbeats": True,
    })
    view = derive_runner_view(
        (stale_heartbeats,),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "pending"
    assert any(
        item.code == "stale_observation" and item.reason == "observation_payload_stale"
        for item in view.diagnostics
    )

    # A stale payload beside a live, current envelope denies live too.
    mixed = derive_runner_view(
        (_runner_envelope("run-live"), stale_payload),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert mixed.status == "pending"
    assert {item.code for item in mixed.diagnostics} == {"stale_observation"}


def test_runner_view_never_live_from_stale_raw_mapping() -> None:
    """An admitted stale mapping stays visible but can never authorize live."""
    stale_raw = {
        "type": "process", "source": "cloud/process.json",
        "status": "running", "identity": "runner-1", "expected_identity": "runner-1",
        "stale": True,
    }
    view = derive_runner_view((stale_raw,), expected_identity="runner-1")
    assert view.status != "live"
    assert view.status == "stale"
    # Soft gate: the raw mapping remains observable for diagnostics.  A raw
    # mapping is unconditionally non-coherent evidence, and its self-declared
    # staleness is additionally surfaced as a stale_observation diagnostic.
    assert len(view.observations) == 1
    assert {item.code for item in view.diagnostics} == {"non_coherent_observation", "stale_observation"}
    assert any(
        item.code == "stale_observation" and item.reason == "observation_payload_stale"
        for item in view.diagnostics
    )


def test_publication_view_never_ready_from_stale_payload_envelope() -> None:
    """Publication readiness applies the same payload-stale gate."""
    stale_payload = _publication_envelope(
        "pub-stale-payload", payload={**_PUBLICATION_PAYLOAD, "stale": True},
    )
    assert stale_payload.coherence == "COHERENT"
    assert stale_payload.is_dispatchable is True

    view = derive_publication_view(
        (stale_payload,),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status != "ready"
    assert view.status == "pending"
    assert {"stale_observation"} <= {item.code for item in view.diagnostics}
    assert any(
        item.code == "stale_observation" and item.reason == "observation_payload_stale"
        for item in view.diagnostics
    )

    # The ``stale_heartbeats`` alias marks the same stale evidence.
    stale_heartbeats = _publication_envelope(
        "pub-stale-heartbeats", payload={**_PUBLICATION_PAYLOAD, "stale_heartbeats": True},
    )
    view = derive_publication_view(
        (stale_heartbeats,),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "pending"
    assert {"stale_observation"} <= {item.code for item in view.diagnostics}
    assert any(
        item.code == "stale_observation" and item.reason == "observation_payload_stale"
        for item in view.diagnostics
    )

    # A stale payload beside a ready envelope denies ready too.
    mixed = derive_publication_view(
        (_publication_envelope("pub-ready"), stale_payload),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert mixed.status == "pending"
    assert {item.code for item in mixed.diagnostics} == {"stale_observation"}


def test_publication_view_never_ready_from_raw_mappings() -> None:
    complete = {
        "branch": "feature/authority",
        "branch_ancestry": "valid",
        "dirty_workspace": False,
        "pushed_sha": "a" * 40,
        "pull_request": "https://example.test/pr/7",
        "auth": True,
        "no_push": False,
        "source": "git/combined.json",
    }

    # A complete raw mapping reports every field but has no coherence claim:
    # it can never authorize ``ready``.
    complete_view = derive_publication_view((complete,))
    assert complete_view.status == "pending"
    assert all(item.state == "known" for item in complete_view.observations)
    assert {item.code for item in complete_view.diagnostics} == {"non_coherent_observation"}

    # Even beside a coherent, current envelope, one raw mapping denies ready.
    mixed = derive_publication_view(
        (_publication_envelope("pub-ready"), complete),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert mixed.status == "pending"
    assert {item.code for item in mixed.diagnostics} == {"non_coherent_observation"}


def test_runner_view_never_live_from_raw_mappings() -> None:
    raw_live = {
        "type": "process", "source": "cloud/process.json",
        "status": "running", "identity": "runner-1", "expected_identity": "runner-1",
    }
    view = derive_runner_view((raw_live,), expected_identity="runner-1")
    assert view.status == "pending"
    # The raw mapping stays visible (soft gate) but cannot authorize live.
    assert len(view.observations) == 1
    assert {item.code for item in view.diagnostics} == {"non_coherent_observation"}

    # Even beside a coherent, current envelope, one raw mapping denies live.
    mixed = derive_runner_view(
        (_runner_envelope("run-live"), raw_live),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert mixed.status == "pending"
    assert {item.code for item in mixed.diagnostics} == {"non_coherent_observation"}


def test_raw_mapping_self_asserted_coherence_never_authorizes() -> None:
    # A raw mapping that self-declares ``coherence`` COHERENT plus matching run
    # provenance can never authorize ``live``: only a wrapped, coherent and
    # current ObservationEnvelope may produce a green status.
    raw_coherent = {
        "type": "process", "source": "cloud/process.json",
        "status": "running", "identity": "runner-1", "expected_identity": "runner-1",
        "coherence": "COHERENT",
        "run_id": RUN, "run_revision": REVISION, "source_cursor": 3,
    }
    live = derive_runner_view(
        (raw_coherent,),
        expected_identity="runner-1",
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert live.status == "pending"
    assert len(live.observations) == 1  # soft gate: still visible for observation
    assert {item.code for item in live.diagnostics} == {"non_coherent_observation"}

    # The same holds for the publication view: a complete raw mapping with a
    # self-asserted COHERENT verdict can never produce ``ready``.
    raw_ready = {
        "branch": "feature/authority",
        "branch_ancestry": "valid",
        "dirty_workspace": False,
        "pushed_sha": "a" * 40,
        "pull_request": "https://example.test/pr/7",
        "auth": True,
        "no_push": False,
        "coherence": "COHERENT",
        "run_id": RUN, "run_revision": REVISION, "source_cursor": 3,
        "source": "git/combined.json",
    }
    ready = derive_publication_view(
        (raw_ready,),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert ready.status == "pending"
    assert all(item.state == "known" for item in ready.observations)
    assert {item.code for item in ready.diagnostics} == {"non_coherent_observation"}

    # Matching provenance does not unlock the raw mapping either: the
    # self-asserted coherence field is never trusted.
    mixed = derive_runner_view(
        (_runner_envelope("run-live"), raw_coherent),
        expected_identity="runner-1",
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert mixed.status == "pending"
    assert {item.code for item in mixed.diagnostics} == {"non_coherent_observation"}


def test_raw_mapping_self_asserted_is_dispatchable_never_authorizes() -> None:
    raw_dispatchable = {
        "type": "process", "source": "cloud/process.json",
        "status": "running", "identity": "runner-1", "expected_identity": "runner-1",
        "is_dispatchable": True,
        "run_id": RUN, "run_revision": REVISION, "source_cursor": 3,
    }
    view = derive_runner_view(
        (raw_dispatchable,),
        expected_identity="runner-1",
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "pending"
    assert {item.code for item in view.diagnostics} == {"non_coherent_observation"}

    # A self-asserted ``is_dispatchable`` mapping beside a coherent envelope
    # still denies live.
    mixed = derive_runner_view(
        (_runner_envelope("run-live"), raw_dispatchable),
        expected_identity="runner-1",
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert mixed.status == "pending"
    assert {item.code for item in mixed.diagnostics} == {"non_coherent_observation"}


def test_publication_view_never_ready_from_mixed_environment_envelopes() -> None:
    other_env = dict(_RUNTIME_CAPTURE)
    other_env["environment_identity"] = "env-2"
    other_env["session_identity"] = "env-2"

    view = derive_publication_view(
        (
            _publication_envelope("pub-env-1"),
            _publication_envelope("pub-env-2", runtime_capture=other_env),
        ),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "pending"
    assert {item.code for item in view.diagnostics} == {"cross_environment_observation"}
    assert view.observations


def test_runner_view_never_live_from_mixed_environment_envelopes() -> None:
    other_env = dict(_RUNTIME_CAPTURE)
    other_env["environment_identity"] = "env-2"
    other_env["session_identity"] = "env-2"

    view = derive_runner_view(
        (
            _runner_envelope("run-env-1"),
            _runner_envelope("run-env-2", runtime_capture=other_env),
        ),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "pending"
    assert {item.code for item in view.diagnostics} == {"cross_environment_observation"}
    assert view.observations


def test_publication_view_never_ready_from_mixed_run_envelopes_without_context() -> None:
    # Two individually coherent, same-environment envelopes captured in
    # different runs: without a run anchor the view cannot tell one run's
    # coherent capture from another's, so mixed-run evidence must be pending.
    view = derive_publication_view(
        (
            _publication_envelope("pub-run-1"),
            _publication_envelope("pub-run-2", run_id="plan-other"),
        ),
    )
    assert view.status == "pending"
    assert view.status != "ready"
    assert {item.code for item in view.diagnostics} == {"mixed_run_observation"}
    assert view.observations


def test_publication_view_never_ready_from_mixed_revisions_without_context() -> None:
    view = derive_publication_view(
        (
            _publication_envelope("pub-rev-1"),
            _publication_envelope("pub-rev-2", run_revision="revision-other"),
        ),
    )
    assert view.status == "pending"
    assert {item.code for item in view.diagnostics} == {"mixed_run_observation"}


def test_publication_view_single_run_envelopes_without_context_stay_ready() -> None:
    # The common single-source case is unchanged: one coherent envelope (or
    # several from one run) with no supplied context may still be ready.
    single = derive_publication_view((_publication_envelope("pub-ready"),))
    assert single.status == "ready"
    same_run = derive_publication_view(
        (
            _publication_envelope("pub-ready-a"),
            _publication_envelope("pub-ready-b"),
        ),
    )
    assert same_run.status == "ready"


def test_publication_view_anchored_run_still_disambiguates_mixed_envelopes() -> None:
    # With a run anchor supplied, the per-observation gate disambiguates: the
    # foreign-run envelope is stale evidence and the cross-run gate does not
    # fire — the view is pending for the stale observation, never "ready".
    view = derive_publication_view(
        (
            _publication_envelope("pub-run-1"),
            _publication_envelope("pub-run-2", run_id="plan-other"),
        ),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "pending"
    assert {item.code for item in view.diagnostics} == {"stale_observation"}


def test_runner_view_never_live_from_mixed_run_envelopes_without_context() -> None:
    view = derive_runner_view(
        (
            _runner_envelope("run-live-1"),
            _runner_envelope("run-live-2", run_id="plan-other"),
        ),
    )
    assert view.status == "pending"
    assert view.status != "live"
    assert {item.code for item in view.diagnostics} == {"mixed_run_observation"}
    assert view.observations


def test_runner_view_single_run_envelopes_without_context_stay_live() -> None:
    single = derive_runner_view((_runner_envelope("run-live"),))
    assert single.status == "live"
    same_run = derive_runner_view(
        (
            _runner_envelope("run-live-a"),
            _runner_envelope("run-live-b"),
        ),
    )
    assert same_run.status == "live"


def test_runner_view_anchored_run_still_disambiguates_mixed_envelopes() -> None:
    view = derive_runner_view(
        (
            _runner_envelope("run-live-1"),
            _runner_envelope("run-live-2", run_id="plan-other"),
        ),
        run_id=RUN,
        run_revision=REVISION,
        journal_cursor=10,
    )
    assert view.status == "pending"
    assert {item.code for item in view.diagnostics} == {"stale_observation"}


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
