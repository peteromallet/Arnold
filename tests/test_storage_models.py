from __future__ import annotations

from datetime import datetime, timezone

import pytest

from arnold.pipelines.megaplan.schemas import (
    AutomationActor,
    BotTurn,
    Capsule,
    CapsuleContract,
    CapsuleDefinition,
    CapsuleEvidence,
    CapsuleLineage,
    ChecklistItem,
    CodeArtifact,
    Codebase,
    ControlMessage,
    CloudRun,
    Epic,
    EpicEvent,
    EpicLock,
    ExecutionLease,
    ExternalRequest,
    Feedback,
    Image,
    Message,
    MigrationRun,
    Plan,
    PlanArtifact,
    ProgressEvent,
    ResidentConversation,
    ScheduledJob,
    SecondOpinion,
    Sprint,
    SprintItem,
    SystemLog,
    ToolCall,
    Warrant,
    WarrantAccount,
    WarrantAuthority,
    WarrantRationaleAnchor,
    WarrantSignature,
    WarrantSourceCompleteness,
    WarrantSourceProjection,
)
from arnold.pipelines.megaplan.store.snapshot import canonical_json_dumps
from tests.conftest import load_state


NOW = datetime(2026, 5, 3, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("model_cls", "payload"),
    [
        (Epic, {"id": "epic_1", "title": "Epic", "goal": "Ship it", "body": "Body", "state": "shaping"}),
        (BotTurn, {"id": "turn_1", "status": "in_progress"}),
        (Message, {"id": "msg_1", "direction": "inbound", "content": "hello"}),
        (
            ResidentConversation,
            {
                "id": "conversation_1",
                "conversation_key": "discord:guild:g1:channel:c1",
                "guild_id": "g1",
                "channel_id": "c1",
            },
        ),
        (ToolCall, {"id": "tool_1", "turn_id": "turn_1", "tool_name": "read_file", "operation_kind": "read"}),
        (SystemLog, {"id": "log_1", "level": "info", "category": "system", "event_type": "boot", "message": "ok"}),
        (EpicLock, {"epic_id": "epic_1", "holder_id": "worker", "expires_at": NOW}),
        (
            ExternalRequest,
            {
                "id": "req_1",
                "idempotency_key": "idem_1",
                "provider": "openai",
                "endpoint": "/v1/responses",
                "status": "pending",
            },
        ),
        (
            Image,
            {
                "id": "img_1",
                "source": "agent_generated",
                "storage_url": "https://example.invalid/image.png",
                "reference_key": "hero",
            },
        ),
        (ChecklistItem, {"id": "item_1", "epic_id": "epic_1", "content": "Do work", "position": 1}),
        (EpicEvent, {"id": "event_1", "epic_id": "epic_1", "transaction_id": "tx_1", "summary": "Created"}),
        (
            Feedback,
            {
                "id": "feedback_1",
                "kind": "style",
                "content": "Prefer concise replies",
                "source": "explicit_save_request",
            },
        ),
        (
            Sprint,
            {
                "id": "sprint_1",
                "epic_id": "epic_1",
                "sprint_number": 1,
                "name": "Sprint 1",
                "goal": "Deliver foundation",
                "status": "done",
            },
        ),
        (
            SprintItem,
            {
                "id": "sprint_item_1",
                "sprint_id": "sprint_1",
                "content": "Implement model layer",
                "estimated_complexity": "medium",
                "status": "open",
                "position": 1,
            },
        ),
        (
            SecondOpinion,
            {
                "id": "opinion_1",
                "epic_id": "epic_1",
                "requested_by": "user",
                "raw_response": "Looks good",
                "score": 8,
                "summary": "Strong plan",
                "verdict": "go",
                "model_used": "gpt-5.5",
            },
        ),
        (
            Codebase,
            {
                "id": "codebase_1",
                "owner": "openai",
                "name": "megaplan",
                "repo_url": "https://github.com/openai/megaplan.git",
                "repo_workspace": "/workspace/megaplan",
                "default_branch": "main",
            },
        ),
        (
            CodeArtifact,
            {
                "id": "artifact_1",
                "kind": "summary",
                "source": "codebase",
                "content": "Important details",
            },
        ),
        (
            MigrationRun,
            {
                "id": "migration_1",
                "epic_id": "epic_1",
                "source_backend": "file",
                "target_backend": "db",
                "phase": "planning",
                "holder_id": "worker",
                "expires_at": NOW,
            },
        ),
        (
            ExecutionLease,
            {
                "plan_id": "plan_1",
                "holder_id": "worker",
                "phase": "execute",
                "worker_kind": "local_cli",
                "expires_at": NOW,
            },
        ),
        (
            PlanArtifact,
            {
                "name": "plan_v1.md",
                "kind": "markdown",
                "role": "plan_version",
                "sha256": "deadbeef",
                "created_at": NOW,
                "updated_at": NOW,
            },
        ),
        (
            ControlMessage,
            {
                "id": "control_1",
                "epic_id": "epic_1",
                "actor_id": "actor_1",
                "intent": "run_sprint",
                "target_id": "sprint_1",
                "idempotency_key": "msg_1",
            },
        ),
        (
            ProgressEvent,
            {
                "id": "progress_1",
                "epic_id": "epic_1",
                "kind": "phase_start",
                "summary": "Execution started",
            },
        ),
        (
            ScheduledJob,
            {
                "id": "job_1",
                "job_type": "cloud_check",
                "conversation_id": "conversation_1",
                "cloud_run_id": "cloud_run_1",
                "scheduled_for": NOW,
            },
        ),
        (
            CloudRun,
            {
                "id": "cloud_run_1",
                "operation": "chain",
                "status": "running",
                "conversation_id": "conversation_1",
                "provider": "railway",
            },
        ),
        (
            AutomationActor,
            {
                "id": "actor_1",
                "name": "Local CLI",
                "granted_epic_ids": "*",
                "actor_kind": "cli",
            },
        ),
        (
            Plan,
            {
                "id": "plan_1",
                "name": "plan_1",
                "revision": 0,
                "idea": "test idea",
                "current_state": "planned",
                "iteration": 1,
                "config": {"project_dir": "/tmp/project"},
                "sessions": {},
                "plan_versions": [],
                "history": [],
                "meta": {},
                "last_gate": {},
                "created_at": NOW,
                "updated_at": NOW,
            },
        ),
    ],
)
def test_storage_models_construct_with_minimal_valid_payloads(model_cls, payload) -> None:
    model = model_cls.model_validate(payload)

    assert model.model_dump()


def test_storage_models_normalize_json_defaults_and_extensions() -> None:
    request = ExternalRequest.model_validate(
        {
            "id": "req_1",
            "idempotency_key": "idem_1",
            "provider": "openai",
            "endpoint": "/v1/responses",
            "status": "pending",
            "request_summary": None,
            "request_body": {"model": "gpt-5.5"},
        }
    )
    opinion = SecondOpinion.model_validate(
        {
            "id": "opinion_1",
            "epic_id": "epic_1",
            "requested_by": "auto_state_gate",
            "focus_areas": None,
            "raw_response": "Need more detail",
            "score": 4,
            "summary": "Needs work",
            "verdict": "revise",
            "resulting_checklist_item_ids": None,
            "model_used": "gpt-5.5",
        }
    )
    sprint = Sprint.model_validate(
        {
            "id": "sprint_1",
            "epic_id": "epic_1",
            "sprint_number": 1,
            "name": "Sprint 1",
            "goal": "Deliver foundation",
            "status": "running",
        }
    )

    assert request.request_summary == {}
    assert request.request_body == {"model": "gpt-5.5"}
    assert opinion.focus_areas == []
    assert opinion.resulting_checklist_item_ids == []
    assert sprint.status == "running"


def test_resident_schema_exports_and_message_idempotency_fields() -> None:
    from arnold.pipelines.megaplan import schemas 
    from arnold.pipelines.megaplan.schemas import models
    from arnold.pipelines.megaplan.store import CloudRun as StoreCloudRun
    from arnold.pipelines.megaplan.store import ResidentConversation as StoreResidentConversation
    from arnold.pipelines.megaplan.store import ScheduledJob as StoreScheduledJob

    message = Message.model_validate(
        {
            "id": "msg_resident_1",
            "conversation_id": "conversation_1",
            "idempotency_key": "discord:message:123",
            "direction": "inbound",
            "content": "hello",
        }
    )

    assert message.conversation_id == "conversation_1"
    assert message.idempotency_key == "discord:message:123"
    assert models.ResidentConversation is ResidentConversation
    assert schemas.ResidentConversation is ResidentConversation
    assert StoreResidentConversation is ResidentConversation
    assert models.ScheduledJob is ScheduledJob
    assert schemas.ScheduledJob is ScheduledJob
    assert StoreScheduledJob is ScheduledJob
    assert models.CloudRun is CloudRun
    assert schemas.CloudRun is CloudRun
    assert StoreCloudRun is CloudRun


def test_sprint5_event_snapshot_and_image_blob_fields_are_optional() -> None:
    event = EpicEvent.model_validate(
        {
            "id": "event_1",
            "epic_id": "epic_1",
            "transaction_id": "tx_1",
            "summary": "Body changed",
            "pre_state": {"epic": {"revision": 1}},
            "post_state": {"epic": {"revision": 2}},
            "pre_state_canonical_json": "{\"epic\":{\"revision\":1}}",
            "post_state_canonical_json": "{\"epic\":{\"revision\":2}}",
            "pre_state_sha256": "sha256:before",
            "post_state_sha256": "sha256:after",
        }
    )
    image = Image.model_validate(
        {
            "id": "img_1",
            "source": "user_uploaded",
            "storage_url": "mp://blob/blob_1",
            "reference_key": "diagram",
            "blob_backend": "file",
            "blob_id": "blob_1",
            "blob_sha256": "sha256:image",
            "blob_size_bytes": 123,
            "content_type": "image/png",
        }
    )

    assert event.pre_state_sha256 == "sha256:before"
    assert event.post_state["epic"]["revision"] == 2
    assert image.blob_backend == "file"
    assert image.blob_size_bytes == 123


def test_plan_round_trips_current_plan_state_shape(plan_fixture) -> None:
    state = load_state(plan_fixture.plan_dir)

    plan = Plan.from_plan_state(state, plan_id="plan_1", revision=3)

    assert plan.name == state["name"]
    assert plan.revision == 3
    assert plan.to_plan_state() == state


def test_plan_round_trips_lifecycle_failure_and_resume_cursor(plan_fixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state["current_state"] = "failed"
    state["latest_failure"] = {"kind": "phase_failed", "phase": "execute"}
    state["resume_cursor"] = {"phase": "execute", "batch_index": 1}

    plan = Plan.from_plan_state(state, plan_id="plan_1", revision=3)

    assert plan.latest_failure == {"kind": "phase_failed", "phase": "execute"}
    assert plan.resume_cursor == {"phase": "execute", "batch_index": 1}
    assert plan.to_plan_state()["latest_failure"] == state["latest_failure"]
    assert plan.to_plan_state()["resume_cursor"] == state["resume_cursor"]


def test_plan_legacy_state_without_resume_cursor_defaults_to_none(plan_fixture) -> None:
    state = load_state(plan_fixture.plan_dir)
    state.pop("resume_cursor", None)
    state.pop("latest_failure", None)

    plan = Plan.from_plan_state(state, plan_id="plan_1", revision=3)

    assert plan.resume_cursor is None
    assert plan.latest_failure is None
    assert "resume_cursor" not in plan.to_plan_state()


def test_feedback_and_sprint_constraints_match_design_extensions() -> None:
    with pytest.raises(ValueError):
        Feedback.model_validate(
            {
                "id": "feedback_1",
                "kind": "style",
                "content": "Too vague",
                "source": "agent_observation",
            }
        )

    with pytest.raises(ValueError):
        Sprint.model_validate(
            {
                "id": "sprint_1",
                "epic_id": "epic_1",
                "sprint_number": 1,
                "name": "Sprint 1",
                "goal": "Deliver foundation",
                "status": "queued",
            }
        )


def _capsule_payload() -> dict[str, object]:
    return {
        "capsule_hash": "sha256:capsule",
        "definition": {
            "identity_hash": "sha256:definition",
            "static_behavioral_hash": "sha256:static",
            "runtime_topology_hash": "sha256:runtime",
            "pipeline_name": "select-tournament",
            "ports": [{"name": "input", "content_type": "application/json"}],
            "replay_ready": True,
        },
        "contract": {
            "manifest_abi": "arnold.pipeline.v1",
            "static_behavioral_hash": "sha256:static",
            "runtime_topology_hash": "sha256:runtime",
            "port_expectations": [{"name": "input"}],
            "evidence_refs": [{"evidence_id": "evidence_1"}],
            "repo_commit": "abc123",
            "model_version_requirements": {"execute": "codex:gpt-5.5"},
            "tool_version_requirements": {"python": "3.12"},
            "environment_variable_requirements": {"MEGAPLAN_PROFILE": "solo"},
            "secret_shape_declarations": {
                "OPENAI_API_KEY": {"kind": "api_key", "prefix": "sk-", "min_length": 20}
            },
            "model_requirements": {"execute": "gpt-5.5"},
        },
        "lineage": {"capsule_hash": "sha256:capsule"},
        "evidence": [
            {
                "evidence_id": "evidence_1",
                "evidence_type": "export_manifest",
                "payload_ref": {"blob_id": "blob_1", "sha256": "sha256:blob"},
            }
        ],
    }


def _warrant_payload() -> dict[str, object]:
    authority = {
        "authority_id": "authority_1",
        "policy_envelope": {"spend_ceiling_usd": 10, "autonomy": "bounded"},
        "grantor": "operator",
    }
    account = {
        "account_id": "account_1",
        "verified_work_units": [{"task_id": "T1", "status": "done"}],
        "verified_result_ref": {"receipt_id": "receipt_1"},
    }
    rationale_anchor = {
        "anchor_id": "rationale_1",
        "manifest_hash": "sha256:manifest",
        "rationale_ref": {"event_id": "event_1"},
    }
    return {
        "warrant_id": "warrant_1",
        "authority": authority,
        "account": account,
        "rationale_anchor": rationale_anchor,
        "behavioral_manifest_hash": "sha256:manifest",
        "verified_result_ref": {"receipt_id": "receipt_1"},
        "signature": {
            "signed_payload_sha256": "sha256:payload",
            "signature": "hex-signature",
            "key_id": "test-key",
        },
    }


def test_capsule_warrant_and_source_projection_schema_defaults_and_forward_keys() -> None:
    capsule = Capsule.model_validate({**_capsule_payload(), "future_capsule_key": "ignored"})
    warrant = Warrant.model_validate({**_warrant_payload(), "future_warrant_key": "ignored"})
    source_projection = WarrantSourceProjection.model_validate(
        {
            "projection_id": "projection_1",
            "completeness": {
                "present": ["authority", "account"],
                "missing": ["rationale_anchor"],
                "unsupported": [],
                "required_fields": ["authority", "account", "rationale_anchor"],
                "signable": False,
                "future_completeness_key": "ignored",
            },
            "authority": _warrant_payload()["authority"],
            "source_refs": {"receipts": ["receipt_1"]},
            "future_projection_key": "ignored",
        }
    )

    assert capsule.schema_version == 1
    assert capsule.definition.schema_version == 1
    assert capsule.contract.schema_version == 1
    assert capsule.contract.model_version_requirements == {"execute": "codex:gpt-5.5"}
    assert capsule.contract.tool_version_requirements == {"python": "3.12"}
    assert capsule.contract.environment_variable_requirements == {"MEGAPLAN_PROFILE": "solo"}
    assert capsule.contract.secret_shape_declarations == {
        "OPENAI_API_KEY": {"kind": "api_key", "prefix": "sk-", "min_length": 20}
    }
    assert capsule.lineage.schema_version == 1
    assert capsule.evidence[0].schema_version == 1
    assert warrant.schema_version == 1
    assert warrant.authority.schema_version == 1
    assert warrant.account.schema_version == 1
    assert warrant.rationale_anchor.schema_version == 1
    assert warrant.signature.schema_version == 1
    assert source_projection.schema_version == 1
    assert source_projection.completeness.schema_version == 1
    assert "future_capsule_key" not in capsule.model_dump(mode="json")
    assert "future_warrant_key" not in warrant.model_dump(mode="json")
    assert "future_projection_key" not in source_projection.model_dump(mode="json")
    assert "future_completeness_key" not in source_projection.completeness.model_dump(mode="json")

    minimal_contract = CapsuleContract.model_validate(
        {
            "manifest_abi": "arnold.pipeline.v1",
            "static_behavioral_hash": "sha256:static",
        }
    )
    assert minimal_contract.repo_commit is None
    assert minimal_contract.model_version_requirements == {}
    assert minimal_contract.tool_version_requirements == {}
    assert minimal_contract.environment_variable_requirements == {}
    assert minimal_contract.secret_shape_declarations == {}


@pytest.mark.parametrize(
    ("model_cls", "payload"),
    [
        (CapsuleDefinition, {"static_behavioral_hash": "sha256:static"}),
        (
            CapsuleContract,
            {"static_behavioral_hash": "sha256:static"},
        ),
        (
            CapsuleEvidence,
            {"evidence_id": "evidence_1", "evidence_type": "receipt"},
        ),
        (Capsule, {"capsule_hash": "sha256:capsule"}),
        (WarrantAuthority, {"authority_id": "authority_1"}),
        (WarrantAccount, {"account_id": "account_1"}),
        (
            WarrantRationaleAnchor,
            {"anchor_id": "rationale_1", "rationale_ref": {"event_id": "event_1"}},
        ),
        (WarrantSignature, {"signature": "hex"}),
        (Warrant, {"warrant_id": "warrant_1"}),
        (
            WarrantSourceProjection,
            {"projection_id": "projection_1"},
        ),
    ],
)
def test_capsule_warrant_models_validate_required_fields(model_cls, payload) -> None:
    with pytest.raises(ValueError):
        model_cls.model_validate(payload)


def test_warrant_source_completeness_rejects_signable_missing_required_fields() -> None:
    with pytest.raises(ValueError):
        WarrantSourceCompleteness.model_validate(
            {
                "present": ["authority"],
                "missing": ["account"],
                "unsupported": [],
                "required_fields": ["authority", "account"],
                "signable": True,
            }
        )


def test_capsule_warrant_and_source_projection_canonical_round_trips() -> None:
    capsule = Capsule.model_validate(_capsule_payload())
    warrant = Warrant.model_validate(_warrant_payload())
    source_projection = WarrantSourceProjection.model_validate(
        {
            "projection_id": "projection_1",
            "completeness": {
                "present": [
                    "authority",
                    "account",
                    "rationale_anchor",
                    "behavioral_manifest_hash",
                    "verified_result_ref",
                ],
                "missing": [],
                "unsupported": [],
                "required_fields": [
                    "authority",
                    "account",
                    "rationale_anchor",
                    "behavioral_manifest_hash",
                    "verified_result_ref",
                ],
                "signable": True,
            },
            "authority": _warrant_payload()["authority"],
            "account": _warrant_payload()["account"],
            "rationale_anchor": _warrant_payload()["rationale_anchor"],
            "behavioral_manifest_hash": "sha256:manifest",
            "verified_result_ref": {"receipt_id": "receipt_1"},
            "source_refs": {"receipts": ["receipt_1"], "events": ["event_1"]},
        }
    )

    for model_cls, instance in [
        (Capsule, capsule),
        (Warrant, warrant),
        (WarrantSourceProjection, source_projection),
    ]:
        canonical = canonical_json_dumps(instance.model_dump(mode="json"))
        restored = model_cls.model_validate_json(canonical)

        assert canonical_json_dumps(restored.model_dump(mode="json")) == canonical
