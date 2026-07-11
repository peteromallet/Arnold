from __future__ import annotations

from pathlib import Path

import pytest

from arnold_pipelines.megaplan.authority.batch_scope import BatchScope, resolve_batch_scope
from arnold_pipelines.megaplan.authority.binding import (
    DispatchGrant,
    SENSE_CHECK_RESULT_CAPABILITY,
    TASK_RESULT_CAPABILITY,
)
from arnold_pipelines.run_authority import (
    CapabilityGrant,
    ContractError,
    contract_from_dict,
)


RUN_ID = "megaplan-run-1"
RUN_REVISION = "revision-20260710"
COORDINATOR_ATTEMPT_ID = "coordinator-attempt-1"
FENCE_TOKEN = 7


def _dispatch_grant() -> DispatchGrant:
    return DispatchGrant(
        grant_id="dispatch-batch-1",
        run_id=RUN_ID,
        run_revision=RUN_REVISION,
        coordinator_attempt_id=COORDINATOR_ATTEMPT_ID,
        fence_token=FENCE_TOKEN,
        subject_ids=("T2", "SC1", "T1"),
        capabilities=(SENSE_CHECK_RESULT_CAPABILITY, TASK_RESULT_CAPABILITY),
        evidence_ids=("execute-prompt", "batch-manifest", "execute-prompt"),
    )


def test_dispatch_grant_round_trips_through_generic_capability_contract() -> None:
    grant = _dispatch_grant()

    generic = CapabilityGrant.from_json(grant.to_json())
    decoded = contract_from_dict(grant.to_dict())
    rewrapped = DispatchGrant.from_dict(generic.to_dict())

    assert isinstance(grant, CapabilityGrant)
    assert isinstance(generic, CapabilityGrant)
    assert not isinstance(generic, DispatchGrant)
    assert decoded == generic
    assert rewrapped == grant
    assert grant.contract_type == generic.contract_type == "capability_grant"
    assert grant.dispatch_id == grant.grant_id == "dispatch-batch-1"


def test_dispatch_grant_preserves_identity_fields_and_evidence_refs() -> None:
    grant = _dispatch_grant()

    payload = grant.to_dict()

    assert payload["grant_id"] == "dispatch-batch-1"
    assert payload["run_id"] == RUN_ID
    assert payload["run_revision"] == RUN_REVISION
    assert payload["coordinator_attempt_id"] == COORDINATOR_ATTEMPT_ID
    assert payload["fence_token"] == FENCE_TOKEN
    assert payload["evidence_ids"] == ["batch-manifest", "execute-prompt"]
    assert DispatchGrant.from_json(grant.to_json()).evidence_ids == (
        "batch-manifest",
        "execute-prompt",
    )


def test_dispatch_grant_carries_task_and_sense_check_scope_as_subjects() -> None:
    grant = _dispatch_grant()
    payload = grant.to_dict()

    assert grant.subject_ids == ("SC1", "T1", "T2")
    assert grant.capabilities == (
        SENSE_CHECK_RESULT_CAPABILITY,
        TASK_RESULT_CAPABILITY,
    )
    assert payload["subject_ids"] == ["SC1", "T1", "T2"]
    assert payload["capabilities"] == [
        SENSE_CHECK_RESULT_CAPABILITY,
        TASK_RESULT_CAPABILITY,
    ]
    assert "task_ids" not in payload
    assert "sense_check_ids" not in payload


def test_dispatch_grant_rejects_non_megaplan_capabilities() -> None:
    with pytest.raises(ContractError, match="unsupported Megaplan dispatch capabilities"):
        DispatchGrant(
            grant_id="dispatch-shell",
            run_id=RUN_ID,
            run_revision=RUN_REVISION,
            coordinator_attempt_id=COORDINATOR_ATTEMPT_ID,
            fence_token=FENCE_TOKEN,
            subject_ids=("T1",),
            capabilities=("generic.shell",),
        )


def test_batch_scope_is_compatibility_proof_not_dispatch_authority() -> None:
    scope = BatchScope.create(
        batch_number=1,
        task_ids=("T2", "T1"),
        sense_check_ids=("SC1",),
    )
    payload = {"batch_scope": scope.to_dict()}
    artifact_path = Path(f"/plan/execute_batches/batch_1/tasks_{scope.task_set_digest}.json")

    resolution = resolve_batch_scope(
        payload,
        artifact_path,
        known_task_ids=("T1", "T2", "T3"),
        known_sense_check_ids=("SC1", "SC2"),
        expected_batch_number=1,
    )

    assert resolution.scope == scope
    assert resolution.scope is not None
    assert resolution.scope.task_ids == ("T1", "T2")
    assert resolution.scope.sense_check_ids == ("SC1",)
    assert set(scope.to_dict()) == {
        "schema_version",
        "batch_number",
        "task_ids",
        "sense_check_ids",
        "task_set_digest",
    }

    with pytest.raises(ContractError, match="unknown contract_type None"):
        contract_from_dict(scope.to_dict())
    with pytest.raises(ContractError, match="invalid DispatchGrant fields"):
        DispatchGrant.from_dict({"contract_type": "capability_grant", **scope.to_dict()})
