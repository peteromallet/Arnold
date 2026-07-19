from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.resident.context_tree import build_context_root
from arnold_pipelines.megaplan.resident.subagent import (
    MANAGED_RUN_CUSTODIAN,
    MANAGED_RUN_KIND,
    MANAGED_RUN_SCHEMA,
    _finish_delivery,
    launch_codex_subagent_detached,
    list_managed_resident_agents,
)


NOW = datetime(2026, 7, 17, 15, 0, tzinfo=timezone.utc)


def _write_manifest(
    root: Path,
    *,
    run_id: str,
    status: str,
    description: str,
    outcome_contract: str,
    outcome_key: str,
    delivery_status: str,
    role: str = "internal_contributor",
    queue: dict | None = None,
    result: str = "",
) -> Path:
    run_dir = root / ".megaplan/plans/resident-subagents" / run_id
    run_dir.mkdir(parents=True)
    result_path = run_dir / "result.md"
    result_path.write_text(result, encoding="utf-8")
    manifest = {
        "schema_version": MANAGED_RUN_SCHEMA,
        "run_kind": MANAGED_RUN_KIND,
        "custodian": MANAGED_RUN_CUSTODIAN,
        "run_id": run_id,
        "status": status,
        "description": description,
        "task_kind": "coding" if outcome_contract != "analytical_fragment" else "review",
        "task_sha256": outcome_key,
        "created_at": "2026-07-17T12:00:00+00:00",
        "finished_at": "2026-07-17T12:30:00+00:00" if status == "completed" else None,
        "result_path": str(result_path),
        "completion_delivery": {
            "transport": "discord",
            "status": delivery_status,
            "attempt_count": 0,
        },
        "aggregation": {
            "schema_version": "arnold-resident-agent-aggregation-v1",
            "key": "delivery-fanin",
            "synthesis_group": "delivery-fanin",
            "role": role,
            "delivery_owner_run_id": "owner",
        },
        "execution_contract": {
            "schema_version": "arnold-resident-delivery-status-v2",
            "outcome_contract": outcome_contract,
            "outcome_contract_authority": "explicit_launch_contract",
            "outcome_key": outcome_key,
            "delivery_policy": (
                "deliver_synthesis_result"
                if role == "synthesis_delivery_owner"
                else "legacy_suppressed_independent_result"
                if outcome_contract == "independently_meaningful_execution"
                else "suppress_analytical_fragment"
            ),
        },
    }
    if queue is not None:
        manifest["queue"] = queue
    path = run_dir / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_hidden_repair_refreshes_stale_fanin_and_keeps_request_open(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        run_id="repair",
        status="completed",
        description="Repair and prove the resident runtime outcome",
        outcome_contract="independently_meaningful_execution",
        outcome_key="repair-runtime",
        delivery_status="suppressed",
        result="Repair completed and focused checks passed.",
    )
    _write_manifest(
        tmp_path,
        run_id="unrelated",
        status="running",
        description="Integrate a separate runtime change",
        outcome_contract="independently_meaningful_execution",
        outcome_key="other-runtime-change",
        delivery_status="pending",
    )
    _write_manifest(
        tmp_path,
        run_id="owner",
        status="queued",
        description="Synthesize both outcomes",
        outcome_contract="synthesis_result",
        outcome_key="delivery-fanin",
        delivery_status="pending",
        role="synthesis_delivery_owner",
        queue={
            "policy": "all_success",
            "predecessor_run_ids": ["repair", "unrelated"],
            # Observed failure fixture: both snapshots are stale and reversed.
            "predecessor_states": [
                {"run_id": "repair", "status": "running"},
                {"run_id": "unrelated", "status": "completed"},
            ],
        },
    )

    agents = list_managed_resident_agents(
        project_root=tmp_path, workspace_root=None, now=NOW
    )
    rows = {
        row["run_id"]: row
        for row in agents["running"] + agents["queued"] + agents["recent"]
    }
    repair = rows["repair"]["status_projection"]
    owner = rows["owner"]["status_projection"]

    assert repair["work"]["status"] == "worker_completed"
    assert repair["work"]["worker_completed"] is True
    assert repair["delivery"]["status"] == "suppressed"
    assert repair["request"]["request_delivered"] is False
    assert owner["dependencies"]["source"] == "current_durable_manifests"
    assert owner["dependencies"]["stale_embedded_snapshot_detected"] is True
    current_states = [
        (item["run_id"], item["status"])
        for item in owner["dependencies"]["predecessor_states"]
    ]
    assert current_states == [
        ("repair", "completed"),
        ("unrelated", "running"),
    ]
    assert owner["request"]["status"] == "awaiting_predecessors"
    assert owner["request"]["request_delivered"] is False

    codes = {item["code"] for item in agents["attention"]}
    assert codes >= {
        "completed_independent_result_suppressed",
        "completed_result_hidden_by_predecessor",
        "unrelated_execution_predecessors_all_success",
        "delivery_owner_abnormally_waiting",
    }
    root = build_context_root(
        status=None,
        agents=agents,
        initiatives=[],
        todos=None,
        runtime=None,
        conversation=None,
    )
    assert {item["code"] for item in root["attention"]["agent_delivery"]} >= {
        "completed_independent_result_suppressed",
        "completed_result_hidden_by_predecessor",
    }


def test_failed_predecessor_does_not_make_success_or_request_invisible(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        run_id="repair",
        status="completed",
        description="Repair the runtime",
        outcome_contract="independently_meaningful_execution",
        outcome_key="repair-runtime",
        delivery_status="suppressed",
        result="Repair succeeded.",
    )
    _write_manifest(
        tmp_path,
        run_id="failed",
        status="failed",
        description="Deploy an unrelated outcome",
        outcome_contract="independently_meaningful_execution",
        outcome_key="failed-deploy",
        delivery_status="failed",
    )
    _write_manifest(
        tmp_path,
        run_id="owner",
        status="queued",
        description="Synthesize the fan-in",
        outcome_contract="synthesis_result",
        outcome_key="delivery-fanin",
        delivery_status="pending",
        role="synthesis_delivery_owner",
        queue={
            "join_policy": "all_success",
            "predecessor_run_ids": ["repair", "failed"],
            "predecessor_states": [],
        },
    )

    agents = list_managed_resident_agents(
        project_root=tmp_path, workspace_root=None, now=NOW
    )
    rows = {
        row["run_id"]: row
        for row in agents["running"] + agents["queued"] + agents["recent"]
    }
    assert rows["owner"]["status_projection"]["request"] == {
        "status": "aggregation_blocked",
        "request_delivered": False,
        "aggregation_role": "synthesis_delivery_owner",
        "aggregation_key": "delivery-fanin",
    }
    assert "failed_predecessor_hides_success" in {
        item["code"] for item in agents["attention"]
    }


def test_analytical_contributor_can_suppress_and_synthesize_normally(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        run_id="analysis",
        status="completed",
        description="Review the delivery design",
        outcome_contract="analytical_fragment",
        outcome_key="delivery-review",
        delivery_status="suppressed",
        result="Review finding for synthesis.",
    )
    _write_manifest(
        tmp_path,
        run_id="owner",
        status="completed",
        description="Deliver the combined conclusion",
        outcome_contract="synthesis_result",
        outcome_key="delivery-fanin",
        delivery_status="delivered",
        role="synthesis_delivery_owner",
        result="Combined conclusion delivered.",
    )

    agents = list_managed_resident_agents(
        project_root=tmp_path, workspace_root=None, now=NOW
    )
    rows = {row["run_id"]: row for row in agents["recent"]}
    assert rows["analysis"]["status_projection"]["request"]["status"] == "awaiting_aggregation"
    assert rows["owner"]["status_projection"]["request"]["status"] == "request_delivered"
    assert rows["owner"]["status_projection"]["request"]["request_delivered"] is True
    assert not any(
        item["code"] == "completed_independent_result_suppressed"
        for item in agents["attention"]
    )


def test_worker_completion_does_not_validate_request_delivery(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        run_id="owner",
        status="completed",
        description="Deliver the combined conclusion",
        outcome_contract="synthesis_result",
        outcome_key="delivery-fanin",
        delivery_status="pending",
        role="synthesis_delivery_owner",
        result="Combined conclusion ready for delivery.",
    )
    before = list_managed_resident_agents(
        project_root=tmp_path, workspace_root=None, now=NOW
    )["recent"][0]["status_projection"]
    assert before["work"]["worker_completed"] is True
    assert before["request"]["status"] == "awaiting_delivery"
    assert before["request"]["request_delivered"] is False

    _finish_delivery(
        manifest_path,
        now=NOW,
        message_ids=["discord-reply-1"],
        result_kind="final_result",
    )
    persisted = json.loads(manifest_path.read_text())
    assert persisted["lifecycle"]["request"] == {
        "status": "request_delivered",
        "request_delivered": True,
    }


def test_launch_keeps_execution_contributor_deliverable_unless_override_is_recorded(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("ARNOLD_RESIDENT_DELEGATION_CONTEXT", raising=False)

    class Process:
        pid = 3210

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.resident.subagent.subprocess.Popen",
        lambda *args, **kwargs: Process(),
    )
    provenance = {
        "transport": "discord",
        "applicability": "applicable",
        "correlation_id": "corr-delivery",
        "custody_id": "custody-delivery",
        "resident_conversation_id": "rconv_delivery",
        "resident_turn_id": "turn_delivery",
        "source_record_id": "msg_delivery",
        "conversation_key": "discord:dm:42",
        "discord_message_id": "100",
        "reply_to_message_id": "100",
        "dm_user_id": "42",
        "source_kind": "discord_inbound_message",
    }
    first = launch_codex_subagent_detached(
        task="Repair the resident runtime and prove the user-visible outcome.",
        description="Repair resident delivery",
        task_kind="coding",
        aggregation_role="internal_contributor",
        synthesis_group="repairs",
        project_dir=str(tmp_path),
        launch_origin=provenance,
    )
    first_manifest = json.loads(Path(first.manifest_path).read_text())
    assert first_manifest["aggregation"]["role"] == "internal_contributor"
    assert first_manifest["execution_contract"]["delivery_policy"] == "deliver_independently"
    assert first_manifest["completion_delivery"]["status"] == "pending"

    second = launch_codex_subagent_detached(
        task="Deploy the separately approved runtime package.",
        description="Deploy approved runtime package",
        task_kind="coding",
        aggregation_role="internal_contributor",
        synthesis_group="repairs",
        delivery_suppression_override_reason=(
            "Staging-only dry run; the explicitly named synthesis owner will report the result."
        ),
        project_dir=str(tmp_path),
        launch_origin=provenance,
    )
    second_manifest = json.loads(Path(second.manifest_path).read_text())
    assert second_manifest["execution_contract"]["delivery_policy"] == (
        "suppress_with_recorded_override"
    )
    assert second_manifest["execution_contract"]["delivery_suppression_override_reason"]
    assert second_manifest["completion_delivery"]["status"] == "suppressed"

    owner = launch_codex_subagent_detached(
        task="Synthesize the repair and deployment outcomes.",
        description="Synthesize repair outcomes",
        aggregation_role="synthesis_delivery_owner",
        synthesis_group="repairs",
        project_dir=str(tmp_path),
        launch_origin=provenance,
    )
    assert json.loads(Path(first.manifest_path).read_text())["completion_delivery"][
        "status"
    ] == "pending"
    assert json.loads(Path(second.manifest_path).read_text())["completion_delivery"][
        "status"
    ] == "suppressed"
    assert json.loads(Path(owner.manifest_path).read_text())["completion_delivery"][
        "status"
    ] == "pending"

    with pytest.raises(ValueError, match="cannot be classified as an analytical_fragment"):
        launch_codex_subagent_detached(
            task="Repair and activate the user-visible runtime.",
            description="Repair and activate runtime",
            task_kind="coding",
            aggregation_role="internal_contributor",
            synthesis_group="repairs",
            outcome_contract="analytical_fragment",
            project_dir=str(tmp_path),
            launch_origin=provenance,
        )
