from __future__ import annotations

import asyncio
import json
from pathlib import Path

from arnold_pipelines.megaplan.cloud import human_review_diagnostic as diagnostic
from arnold_pipelines.megaplan.resident import subagent as subagent_module
from arnold_pipelines.megaplan.resident.provenance import (
    DELEGATION_CONTEXT_ENV,
    normalize_delegation_provenance,
)
from arnold_pipelines.megaplan.resident.subagent import sweep_managed_agent_deliveries


def _provenance() -> dict[str, object]:
    return {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "correlation_id": "corr-human-review",
        "custody_id": "custody-human-review",
        "resident_conversation_id": "rconv_humanreview1",
        "resident_turn_id": "turn_humanreview1",
        "source_record_id": "msg_humanreview1",
        "conversation_key": "discord:guild:12:channel:34:thread:56",
        "discord_message_id": "987654321",
        "reply_to_message_id": "987654321",
        "guild_id": "12",
        "channel_id": "34",
        "thread_id": "56",
        "source_kind": "discord_inbound_message",
        "timezone_name": "UTC",
    }


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    project = tmp_path / "workspace"
    project.mkdir()
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    repair_data_dir = marker_dir / "repair-data"
    repair_data_dir.mkdir()
    (marker_dir / "demo-session.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "workspace": str(project),
                "remote_spec": ".megaplan/initiatives/demo/chain.yaml",
                "resident_delegation": _provenance(),
            }
        ),
        encoding="utf-8",
    )
    (repair_data_dir / "demo-session.repair-data.json").write_text(
        json.dumps(
            {
                "session": "demo-session",
                "plan_name": "demo-plan",
                "outcome": "needs_human",
                "attempts": [
                    {
                        "failure_classification": "deterministic_failure",
                        "outcome": "failed",
                        "why": "state remained manual_review after bounded repair",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "event": "cloud_watchdog_needs_human",
                "escalation_id": "esc-0123456789abcdef",
                "session": "demo-session",
                "workspace": str(project),
                "remote_spec": ".megaplan/initiatives/demo/chain.yaml",
                "summary": "manual_review halt",
                "plan": {
                    "name": "demo-plan",
                    "current_state": "manual_review",
                    "retry_strategy": "manual_review",
                    "latest_failure": {
                        "kind": "iteration_cap",
                        "message": "bounded repair exhausted",
                        "phase": "recover-blocked",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return project, marker_dir, repair_data_dir, payload_path


def test_success_launch_inherits_discord_custody_and_is_idempotent(
    tmp_path: Path, monkeypatch
) -> None:
    project, marker_dir, repair_data_dir, payload_path = _inputs(tmp_path)
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    launches: list[list[str]] = []

    class _Process:
        pid = 43210

    def fake_popen(argv, **kwargs):
        launches.append(list(argv))
        return _Process()

    monkeypatch.setattr(subagent_module.subprocess, "Popen", fake_popen)

    first = diagnostic.launch_human_review_diagnostic(
        payload_path=payload_path,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        project_dir=project,
    )
    second = diagnostic.launch_human_review_diagnostic(
        payload_path=payload_path,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        project_dir=project,
    )

    assert first.ok is True
    assert second.ok is True
    assert second.idempotent_replay is True
    assert second.run_id == first.run_id
    assert len(launches) == 1

    manifest = json.loads(Path(first.manifest_path or "").read_text(encoding="utf-8"))
    assert manifest["launch_provenance"] == normalize_delegation_provenance(_provenance())
    assert manifest["discord_origin"]["reply_to_message_id"] == "987654321"
    delivery = manifest["completion_delivery"]
    assert delivery["status"] == "pending"
    assert delivery["reply_target"] == {
        "conversation_key": "discord:guild:12:channel:34:thread:56",
        "message_id": "987654321",
        "source_record_id": "msg_humanreview1",
    }
    assert delivery["idempotency_key"] == f"resident-subagent-completion:{first.run_id}"

    state = json.loads(Path(first.state_path).read_text(encoding="utf-8"))
    task = Path(state["task_path"]).read_text(encoding="utf-8")
    assert "Clearly separate known facts, evidence-backed inferences, and unknowns" in task
    assert "first layer that failed" in task
    assert "prioritized recommendation" in task
    assert "explicit verification steps" in task
    assert "bounded repair exhausted" in task

    Path(manifest["result_path"]).write_text(
        "The chain stopped because the current plan remained in manual review after bounded repair.",
        encoding="utf-8",
    )
    manifest["status"] = "completed"
    manifest["returncode"] = 0
    manifest_path = Path(first.manifest_path or "")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    class _Outbound:
        def __init__(self) -> None:
            self.sent = []

        async def send(self, message) -> None:
            self.sent.append(message)
            message.metadata["discord_message_ids"] = ["reply-111"]

    outbound = _Outbound()
    delivered = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=project,
            workspace_root=None,
        )
    )
    replay_delivery = asyncio.run(
        sweep_managed_agent_deliveries(
            outbound=outbound,
            project_root=project,
            workspace_root=None,
        )
    )
    assert delivered.delivered == 1
    assert replay_delivery.delivered == 0
    assert len(outbound.sent) == 1
    assert outbound.sent[0].metadata["discord_reply_to_message_id"] == "987654321"
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert persisted["completion_delivery"]["status"] == "delivered"
    assert persisted["completion_delivery"]["discord_message_ids"] == ["reply-111"]


def test_launch_failure_is_persisted_and_fallback_delivery_is_deduplicated(
    tmp_path: Path, monkeypatch
) -> None:
    project, marker_dir, repair_data_dir, payload_path = _inputs(tmp_path)
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    calls = 0

    async def fail_launch(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise OSError("resident supervisor unavailable")

    monkeypatch.setattr(diagnostic, "launch_subagent_task", fail_launch)
    first = diagnostic.launch_human_review_diagnostic(
        payload_path=payload_path,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        project_dir=project,
    )
    replay = diagnostic.launch_human_review_diagnostic(
        payload_path=payload_path,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        project_dir=project,
    )

    assert first.ok is False
    assert first.status == "launch_failed"
    assert "resident supervisor unavailable" in (first.error or "")
    assert first.run_id is None
    assert first.fallback_delivery_required is True
    assert replay.idempotent_replay is True
    assert calls == 1

    result_path = tmp_path / "fallback-result.json"
    result_path.write_text(
        json.dumps(
            {
                "ok": True,
                "channel_id": "34",
                "message_ids": ["111222333"],
                "message_count": 1,
            }
        ),
        encoding="utf-8",
    )
    diagnostic.record_fallback_delivery(
        state_path=first.state_path, result_path=result_path
    )
    after_delivery = diagnostic.launch_human_review_diagnostic(
        payload_path=payload_path,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        project_dir=project,
    )
    assert after_delivery.ok is False
    assert after_delivery.fallback_delivery_required is False
    assert after_delivery.idempotent_replay is False
    assert calls == 2
    retried_state = json.loads(Path(first.state_path).read_text(encoding="utf-8"))
    assert retried_state["launch_attempt_count"] == 2
    assert retried_state["fallback_delivery"]["status"] == "delivered"
