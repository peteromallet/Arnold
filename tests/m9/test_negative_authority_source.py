"""Negative source-type tests for M9 authority displays and sibling views."""

from __future__ import annotations

import json
from typing import Any, Mapping

import pytest

from arnold_pipelines.megaplan.authority import (
    derive_megaplan_recovery_view,
    derive_publication_view,
    derive_runner_view,
)
from arnold_pipelines.megaplan.status_projection import plan_status_presentation


FORGED_SOURCE_PAYLOADS: tuple[tuple[str, Mapping[str, Any]], ...] = (
    ("raw_receipt", {"status": "done", "receipt": "accepted"}),
    ("prose", {"summary": "all tasks passed, ship it"}),
    ("token", {"token": "COMPLETE"}),
    ("mutable_json", {"state": "done", "completed": True}),
    ("filename", {"path": "execution_batch_999_done.json"}),
    ("marker", {"marker": "session.complete"}),
    ("process_fact", {"pid": 4242, "status": "running"}),
    ("implicit_latest_schema", {"latest": True, "batch": "latest"}),
)

FORBIDDEN_ACTION_FIELDS = {
    "dispatch",
    "completion",
    "cancellation",
    "publication",
    "delivery",
}


def _authority_strings(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"authority", "display_authority", "status_route_authority"}:
                found.append(str(item))
            found.extend(_authority_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_authority_strings(item))
    return found


@pytest.mark.parametrize(("source_type", "payload"), FORGED_SOURCE_PAYLOADS)
def test_status_projection_wraps_forged_inputs_as_display_only(
    source_type: str,
    payload: Mapping[str, Any],
) -> None:
    projection = plan_status_presentation(
        payload.get("state") or payload.get("status") or "done",
        source_cursor_vector={
            "source_type": source_type,
            "cursor": payload,
            "authority": "granted",
        },
        wbc_query_inputs={
            "source_type": source_type,
            "status": "VERIFIED",
            "authority": "granted",
        },
    )

    assert projection["display_authority"] == "display_only_non_authoritative"
    assert projection["source_cursor_vector"]["authority"] == "evidence_extracted_display_only"
    assert projection["wbc_query_inputs"]["authority"] == "wbc_query_display_only"
    assert not (set(_authority_strings(projection)) & FORBIDDEN_ACTION_FIELDS)


def test_process_facts_can_show_liveness_but_not_task_or_action_authority() -> None:
    runner = derive_runner_view(
        (
            {
                "observation_id": "process-live",
                "observation_type": "process",
                "source": "ps://pid/4242",
                "state": "running",
                "identity": "runner-1",
                "expected_identity": "runner-1",
            },
        ),
        expected_identity="runner-1",
    )
    payload = runner.to_dict()

    assert payload["status"] == "live"
    assert payload["read_only"] is True
    assert payload["shadow"] is True
    assert "accepted_task_ids" not in payload
    assert "authority" not in json.dumps(payload, sort_keys=True)


def test_publication_observations_do_not_smuggle_execution_authority() -> None:
    publication = derive_publication_view(
        (
            {"source": "git://HEAD", "branch": "feature/m9"},
            {"source": "git://ancestry", "branch_ancestry": "valid"},
            {"source": "git://dirty", "dirty_workspace": False},
            {"source": "git://push", "pushed_sha": "abc123"},
            {"source": "github://pr", "pull_request": "123"},
            {"source": "auth://gh", "auth": True},
            {"source": "policy://push", "no_push": False},
        )
    )
    payload = publication.to_dict()

    assert payload["status"] == "ready"
    assert payload["read_only"] is True
    assert payload["shadow"] is True
    assert "accepted_task_ids" not in payload
    assert "task_authority" not in json.dumps(payload, sort_keys=True)


def test_custody_projection_without_durable_active_repair_cannot_dispatch_repair() -> None:
    recovery = derive_megaplan_recovery_view(
        {
            "custody_bucket": "repairing",
            "blocker_id": "B1",
            "current_state": "failed",
            "retry_strategy": "retry",
            "failure_kind": "failed: tests",
            "active_request_ids": ["req-1"],
            "active_claim_request_ids": [],
            "attempts": [],
        },
        custody_source="mutable-json://repair-progress.json",
    )
    payload = recovery.to_dict()

    assert payload["status"] == "healthy"
    assert payload["read_only"] is True
    assert any(
        item["code"] == "unsupported_repairing_custody"
        for item in payload["diagnostics"]
    )
    assert {item["action_type"] for item in payload["permitted_actions"]} == {"no_action"}


def test_repairable_projection_is_diagnostic_not_bearer_token() -> None:
    recovery = derive_megaplan_recovery_view(
        {
            "custody_bucket": "repairable_not_repairing",
            "blocker_id": "B2",
            "current_state": "failed",
            "retry_strategy": "retry",
            "failure_kind": "error: tests",
            "active_request_ids": [],
        },
        custody_source="projection://repair-custody",
    )
    payload = recovery.to_dict()

    assert payload["status"] == "repairable"
    assert payload["read_only"] is True
    assert payload["shadow"] is True
    assert {item["action_type"] for item in payload["permitted_actions"]} == {
        "repair_dispatch",
        "retry",
    }
    assert "grant_id" not in json.dumps(payload, sort_keys=True)
    assert "fence_token" not in json.dumps(payload, sort_keys=True)
