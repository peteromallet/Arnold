from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.managed_agent import (
    MANAGED_AGENT_CUSTODIAN,
    MANAGED_AGENT_SCHEMA,
)
from arnold_pipelines.megaplan.resident import profile as profile_module
from arnold_pipelines.megaplan.resident import cli as resident_cli
from arnold_pipelines.megaplan.resident import subagent
from arnold_pipelines.megaplan.resident.config import ResidentConfig
from arnold_pipelines.megaplan.resident.context_tree import read_context_node
from arnold_pipelines.megaplan.resident.provenance import DELEGATION_CONTEXT_ENV


PREDECESSOR_RUN_ID = "subagent-20260715-120000-aaaaaaaa"
SECOND_PREDECESSOR_RUN_ID = "subagent-20260715-120100-cccccccc"
CALLER_RUN_ID = "subagent-20260715-130000-bbbbbbbb"


def _non_discord_provenance() -> dict[str, object]:
    return {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "not_applicable",
        "transport": "non_discord",
        "source_kind": "explicit_non_discord",
    }


def _discord_provenance() -> dict[str, object]:
    return {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "correlation_id": "discord-corr-queue-test",
        "custody_id": "discord-custody-queue-test",
        "resident_conversation_id": "rconv_queue_test",
        "source_record_id": "msg_queue_test1",
        "conversation_key": "discord:dm:42",
        "discord_message_id": "1527043418327486586",
        "reply_to_message_id": "1527043418327486586",
        "guild_id": None,
        "channel_id": "42",
        "thread_id": None,
        "dm_user_id": "42",
        "resident_turn_id": "turn_queue_test",
        "source_kind": "discord_inbound_message",
        "timezone_name": "UTC",
    }


def _cross_provenance(
    *,
    source_record_id: str,
    message_id: str,
    conversation_id: str = "rconv_queuetest",
    user_id: str = "42",
    root_run_id: str | None = None,
) -> dict[str, object]:
    value = {
        "schema_version": "arnold-resident-delegation-provenance-v1",
        "applicability": "applicable",
        "transport": "discord",
        "correlation_id": f"discord-corr-{source_record_id}",
        "custody_id": f"discord-custody-{source_record_id}",
        "resident_conversation_id": conversation_id,
        "source_record_id": source_record_id,
        "conversation_key": f"discord:dm:{user_id}",
        "discord_message_id": message_id,
        "reply_to_message_id": message_id,
        "guild_id": None,
        "channel_id": "777",
        "thread_id": None,
        "dm_user_id": user_id,
        "resident_turn_id": f"turn_{source_record_id}",
        "source_kind": "discord_inbound_message",
        "timezone_name": "UTC",
    }
    if root_run_id:
        value["root_run_id"] = root_run_id
    return value


def _write_authoritative_request(
    root: Path,
    provenance: dict[str, object],
    *,
    author_id: str,
    ancestor_content: str | None = None,
) -> None:
    store = root / ".megaplan/resident"
    messages = store / "messages"
    conversations = store / "resident_conversations"
    messages.mkdir(parents=True, exist_ok=True)
    conversations.mkdir(parents=True, exist_ok=True)
    source = str(provenance["source_record_id"])
    conversation_id = str(provenance["resident_conversation_id"])
    message_id = str(provenance["discord_message_id"])
    messages.joinpath(f"{source}.json").write_text(
        json.dumps(
            {
                "id": source,
                "conversation_id": conversation_id,
                "direction": "inbound",
                "content": "authorized request",
                "discord_message_id": message_id,
                "discord_reply_provenance": {
                    "transport": "discord",
                    "source_message_id": message_id,
                    "source_author_id": author_id,
                    "conversation_key": provenance["conversation_key"],
                    "scope": {
                        "channel_id": provenance["channel_id"],
                        "dm_user_id": provenance["dm_user_id"],
                    },
                    **(
                        {
                            "ancestors": [
                                {
                                    "status": "available",
                                    "content": ancestor_content,
                                }
                            ]
                        }
                        if ancestor_content is not None
                        else {}
                    ),
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    conversations.joinpath(f"{conversation_id}.json").write_text(
        json.dumps(
            {
                "id": conversation_id,
                "transport": "discord",
                "conversation_key": provenance["conversation_key"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_cross_request_caller(
    root: Path,
    provenance: dict[str, object],
    *,
    names_predecessor: bool = True,
) -> Path:
    run_dir = root / ".megaplan/plans/resident-subagents" / CALLER_RUN_ID
    run_dir.mkdir(parents=True)
    prompt = (
        f"Queue exactly after {PREDECESSOR_RUN_ID}."
        if names_predecessor
        else "Queue the requested successor."
    )
    prompt_path = run_dir / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    source = str(provenance["source_record_id"])
    relationship = {
        "schema_version": "arnold-resident-query-relationship-v1",
        "conversation_id": provenance["resident_conversation_id"],
        "current_request": {"source_record_id": source},
        "delivery_owner": {"source_record_id": source},
        "aggregation_owner": {"source_record_id": source},
    }
    manifest = {
        "schema_version": MANAGED_AGENT_SCHEMA,
        "run_kind": "resident_delegated_agent",
        "custodian": MANAGED_AGENT_CUSTODIAN,
        "run_id": CALLER_RUN_ID,
        "status": "running",
        "project_dir": str(root),
        "work_intent": "review",
        "prompt_path": str(prompt_path),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "task_sha256": hashlib.sha256(b"queue task").hexdigest(),
        "launch_provenance": provenance,
        "query_relationship": relationship,
        "aggregation": {
            "schema_version": subagent.AGGREGATION_SCHEMA,
            "key": "aggregation-current-request",
            "synthesis_group": "current-request-synthesis",
            "role": "internal_contributor",
            "delivery_owner_run_id": None,
            "delivery_target_source_record_id": source,
            "contributors": [],
        },
        "completion_delivery": {
            "transport": "discord",
            "status": "suppressed",
            "reply_target": {
                "source_record_id": source,
                "message_id": provenance["discord_message_id"],
                "conversation_key": provenance["conversation_key"],
            },
        },
    }
    path = run_dir / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _cross_request_fixture(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    current_author: str = "42",
    predecessor_author: str = "42",
    current_conversation: str = "rconv_queuetest",
    names_predecessor: bool = True,
) -> tuple[dict[str, object], Path]:
    monkeypatch.setenv(
        "MEGAPLAN_RESIDENT_STORE_ROOT", str(root / ".megaplan/resident")
    )
    predecessor_provenance = _cross_provenance(
        source_record_id="msg_predecessor1",
        message_id="1527043418327486586",
    )
    current_provenance = _cross_provenance(
        source_record_id="msg_currentreq1",
        message_id="1527043418327486587",
        conversation_id=current_conversation,
        user_id="42",
        root_run_id=CALLER_RUN_ID,
    )
    _write_authoritative_request(
        root, predecessor_provenance, author_id=predecessor_author
    )
    _write_authoritative_request(root, current_provenance, author_id=current_author)
    predecessor_path = _write_predecessor(root, provenance=predecessor_provenance)
    _write_cross_request_caller(
        root, current_provenance, names_predecessor=names_predecessor
    )
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(current_provenance))
    return current_provenance, predecessor_path


def _queue_cross_request(root: Path):
    return subagent.launch_codex_subagent_detached(
        task="Verify predecessor success and own delivery to the current request.",
        description="Verify predecessor for current request",
        project_dir=str(root),
        depends_on_run_id=PREDECESSOR_RUN_ID,
    )


def _cross_request_root_turn_fixture(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, object], Path, Path]:
    monkeypatch.setenv(
        "MEGAPLAN_RESIDENT_STORE_ROOT", str(root / ".megaplan/resident")
    )
    predecessor_provenance = _cross_provenance(
        source_record_id="msg_predecessor1",
        message_id="1527043418327486586",
    )
    current_provenance = _cross_provenance(
        source_record_id="msg_currentreq1",
        message_id="1527043418327486587",
    )
    current_provenance["resident_turn_id"] = "turn_123456789abc"
    _write_authoritative_request(
        root, predecessor_provenance, author_id="42"
    )
    _write_authoritative_request(
        root,
        current_provenance,
        author_id="42",
        ancestor_content=f"Launched `{PREDECESSOR_RUN_ID}`.",
    )
    predecessor_path = _write_predecessor(
        root, provenance=predecessor_provenance
    )
    source = str(current_provenance["source_record_id"])
    relationship = {
        "schema_version": "arnold-resident-query-relationship-v1",
        "conversation_id": current_provenance["resident_conversation_id"],
        "current_request": {"source_record_id": source},
        "delivery_owner": {"source_record_id": source},
        "aggregation_owner": {"source_record_id": source},
    }
    relationship_dir = root / ".megaplan/resident/query_relationships"
    relationship_dir.mkdir(parents=True, exist_ok=True)
    relationship_dir.joinpath(f"{source}.json").write_text(
        json.dumps(relationship), encoding="utf-8"
    )
    turn_dir = root / ".megaplan/resident/turns"
    turn_dir.mkdir(parents=True, exist_ok=True)
    turn_path = turn_dir / f"{current_provenance['resident_turn_id']}.json"
    turn_path.write_text(
        json.dumps(
            {
                "id": current_provenance["resident_turn_id"],
                "status": "in_progress",
                "triggered_by_message_ids": [source],
                "prompt_snapshot": {"message_count": 1},
                "started_at": "2026-07-15T13:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, json.dumps(current_provenance))
    return current_provenance, predecessor_path, turn_path


def _write_predecessor(
    root: Path,
    *,
    run_id: str = PREDECESSOR_RUN_ID,
    status: str = "running",
    provenance: dict[str, object] | None = None,
    result: str = "",
) -> Path:
    run_dir = root / ".megaplan/plans/resident-subagents" / run_id
    run_dir.mkdir(parents=True)
    result_path = run_dir / "result.md"
    result_path.write_text(result, encoding="utf-8")
    (run_dir / "run.log").write_text("bounded log", encoding="utf-8")
    (run_dir / "prompt.md").write_text("predecessor prompt", encoding="utf-8")
    provenance = provenance or _non_discord_provenance()
    is_discord = provenance["applicability"] == "applicable"
    manifest = {
        "schema_version": MANAGED_AGENT_SCHEMA,
        "run_kind": "resident_delegated_agent",
        "custodian": MANAGED_AGENT_CUSTODIAN,
        "run_id": run_id,
        "status": status,
        "terminal_outcome": (
            status
            if status in {"completed", "failed", "cancelled", "superseded"}
            else None
        ),
        "returncode": 0 if status == "completed" else None,
        "project_dir": str(root),
        "model": "gpt-test",
        "reasoning_effort": "medium",
        "task_kind": "review",
        "work_intent": "review",
        "difficulty": 5,
        "route_class": "test",
        "description": "Produce predecessor evidence.",
        "manifest_path": str(run_dir / "manifest.json"),
        "prompt_path": str(run_dir / "prompt.md"),
        "result_path": str(result_path),
        "log_path": str(run_dir / "run.log"),
        "full_log_path": str(run_dir / "run.log"),
        "created_at": "2026-07-15T12:00:00+00:00",
        "launch_provenance": provenance,
        "request_id": provenance.get("source_record_id") or "request-test",
        "source_record_id": provenance.get("source_record_id"),
        "correlation_id": provenance.get("correlation_id") or "non-discord",
        "custody_id": provenance.get("custody_id") or "non-discord",
        "query_relationship": None,
        "aggregation": {
            "schema_version": subagent.AGGREGATION_SCHEMA,
            "key": "aggregation-queue-test",
            "synthesis_group": "queue-test",
            "role": "synthesis_delivery_owner",
            "delivery_owner_run_id": run_id,
            "delivery_target_source_record_id": provenance.get("source_record_id"),
            "contributors": [],
        },
        "completion_delivery": {
            "transport": "discord" if is_discord else "non_discord",
            "status": "pending" if is_discord else "not_applicable",
            "attempt_count": 0,
            "custody_id": provenance.get("custody_id") or "non-discord",
            "state_history": [],
        },
        "status_history": [],
    }
    if is_discord:
        manifest["discord_origin"] = {
            "transport": "discord",
            "conversation_id": provenance["resident_conversation_id"],
            "conversation_key": provenance["conversation_key"],
            "message_id": provenance["discord_message_id"],
            "reply_to_message_id": provenance["reply_to_message_id"],
            "channel_id": provenance["channel_id"],
            "dm_user_id": provenance["dm_user_id"],
            "reply_target_source_record_id": provenance["source_record_id"],
        }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _queue_successor(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    provenance: dict[str, object] | None = None,
    prompt: str = "Check the output of this agent and use it to write the final decision.",
    max_attempts: int = 3,
):
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    return subagent.launch_codex_subagent_detached(
        task=prompt,
        description="Synthesize the predecessor result",
        project_dir=str(root),
        launch_origin=provenance or _non_discord_provenance(),
        depends_on_run_id=PREDECESSOR_RUN_ID,
        queue_max_launch_attempts=max_attempts,
    )


def _queue_fanin_successor(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    provenance: dict[str, object] | None = None,
):
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    return subagent.launch_codex_subagent_detached(
        task="Synthesize every predecessor result into one final decision.",
        description="Synthesize the predecessor fan-in",
        project_dir=str(root),
        launch_origin=provenance or _non_discord_provenance(),
        depends_on_run_ids=[PREDECESSOR_RUN_ID, SECOND_PREDECESSOR_RUN_ID],
    )


class _Supervisor:
    pid = 4242


def _complete_predecessor(path: Path, *, result: str = "usable result") -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "status": "completed",
            "terminal_outcome": "completed",
            "returncode": 0,
            "finished_at": "2026-07-15T12:01:00+00:00",
        }
    )
    Path(manifest["result_path"]).write_text(result, encoding="utf-8")
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_queue_happy_path_is_durable_and_duplicate_terminal_observation_launches_once(
    tmp_path, monkeypatch
) -> None:
    predecessor_path = _write_predecessor(tmp_path)
    queued = _queue_successor(tmp_path, monkeypatch)
    replayed = _queue_successor(tmp_path, monkeypatch)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text(encoding="utf-8"))

    assert queued.status == "queued"
    assert replayed.run_id == queued.run_id
    assert successor["queue"]["predecessor_run_id"] == PREDECESSOR_RUN_ID
    assert successor["queue"]["successor_run_id"] == queued.run_id
    assert all(
        ref["content_inlined"] is False
        for ref in successor["queue"]["predecessor_references"]
    )
    predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))
    assert predecessor["aggregation"]["role"] == "internal_contributor"
    assert successor["aggregation"]["role"] == "synthesis_delivery_owner"

    _complete_predecessor(predecessor_path)
    launches = []

    def launch(path, manifest):
        launches.append(path)
        running = json.loads(path.read_text(encoding="utf-8"))
        running.update({"status": "running", "pid": _Supervisor.pid})
        running["queue"].update({"state": "running", "attention": "none"})
        path.write_text(json.dumps(running), encoding="utf-8")
        return _Supervisor(), running

    monkeypatch.setattr(subagent, "_spawn_managed_supervisor", launch)
    monkeypatch.setattr(
        subagent, "_pid_matches_manifest", lambda pid, path: pid == _Supervisor.pid
    )
    first = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    second = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )

    assert first.launched == 1
    assert second.launched == 0
    assert launches == [successor_path]
    assert json.loads(successor_path.read_text())["status"] == "running"


def _launch_four_deep_non_mutating_chain(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[Path], list[Path]]:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    provenance = _discord_provenance()
    group = "four-word-regression"
    launched: list[Path] = []

    def launch(path, manifest):
        launched.append(path)
        running = dict(manifest)
        running.update({"status": "running", "pid": _Supervisor.pid})
        path.write_text(json.dumps(running), encoding="utf-8")
        return _Supervisor(), running

    monkeypatch.setattr(subagent, "_spawn_managed_supervisor", launch)
    first = subagent.launch_codex_subagent_detached(
        task="Choose WORD_1 without modifying the repository.",
        description="Choose word one",
        project_dir=str(root),
        launch_origin=provenance,
        task_kind="mechanical",
        work_intent="execution",
        aggregation_role="internal_contributor",
        synthesis_group=group,
    )
    second = subagent.launch_codex_subagent_detached(
        task="Read WORD_1 and choose WORD_2 without modifying the repository.",
        description="Choose word two",
        project_dir=str(root),
        launch_origin=provenance,
        aggregation_role="internal_contributor",
        synthesis_group=group,
        depends_on_run_id=first.run_id,
    )
    third = subagent.launch_codex_subagent_detached(
        task="Read two words and choose WORD_3 without modifying the repository.",
        description="Choose word three",
        project_dir=str(root),
        launch_origin=provenance,
        aggregation_role="internal_contributor",
        synthesis_group=group,
        depends_on_run_id=second.run_id,
    )
    fourth = subagent.launch_codex_subagent_detached(
        task="Read three words, choose WORD_4, and synthesize all four.",
        description="Synthesize all four words",
        project_dir=str(root),
        launch_origin=provenance,
        aggregation_role="synthesis_delivery_owner",
        synthesis_group=group,
        depends_on_run_id=third.run_id,
    )
    return [
        Path(item.manifest_path) for item in (first, second, third, fourth)
    ], launched


def _complete_non_mutating_run(path: Path, result: str) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "status": "completed",
            "terminal_outcome": "completed",
            "returncode": 0,
            "finished_at": "2026-07-16T19:00:00+00:00",
            "completion_verification": {
                "schema_version": subagent.COMPLETION_VERIFICATION_SCHEMA,
                "status": "success",
                "classification": "applicable_non_mutating_success",
                "git_custody": "not_applicable",
                "basis": {
                    "task_kind": "mechanical",
                    "work_intent": "execution",
                    "mutation_claim": "none",
                },
            },
        }
    )
    Path(manifest["result_path"]).write_text(result, encoding="utf-8")
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_non_mutating_mechanical_predecessor_launches_successor_and_four_deep_chain_reaches_owner(
    tmp_path, monkeypatch
) -> None:
    paths, launched = _launch_four_deep_non_mutating_chain(tmp_path, monkeypatch)
    assert launched == [paths[0]]

    words = ["lantern", "meadow", "cobalt"]
    for index, word in enumerate(words):
        _complete_non_mutating_run(paths[index], f"WORD_{index + 1}: {word}")
        sweep = subagent.reconcile_managed_subagent_queues(
            project_root=tmp_path, workspace_root=None
        )
        assert sweep.launched == 1
        assert launched[-1] == paths[index + 1]

    manifests = [json.loads(path.read_text()) for path in paths]
    assert [item["mutation_claim"] for item in manifests] == ["none"] * 4
    assert [item["aggregation"]["role"] for item in manifests] == [
        "internal_contributor",
        "internal_contributor",
        "internal_contributor",
        "synthesis_delivery_owner",
    ]
    assert [item["completion_delivery"]["status"] for item in manifests] == [
        "suppressed",
        "suppressed",
        "suppressed",
        "pending",
    ]
    assert manifests[3]["status"] == "running"


def test_four_deep_dependency_failure_propagates_without_executing_successors(
    tmp_path, monkeypatch
) -> None:
    paths, launched = _launch_four_deep_non_mutating_chain(tmp_path, monkeypatch)
    first = json.loads(paths[0].read_text())
    first.update(
        {
            "status": "failed",
            "terminal_outcome": "failed",
            "returncode": 1,
            "finished_at": "2026-07-16T19:00:00+00:00",
        }
    )
    paths[0].write_text(json.dumps(first))

    for _ in range(4):
        subagent.reconcile_managed_subagent_queues(
            project_root=tmp_path, workspace_root=None
        )

    assert launched == [paths[0]]
    successors = [json.loads(path.read_text()) for path in paths[1:]]
    assert [item["status"] for item in successors] == ["failed"] * 3
    assert all(item.get("started_at") is None for item in successors)
    assert all(
        item["queue"]["attention"] == "predecessor_terminal_failure"
        for item in successors
    )


def test_queue_fanin_waits_for_all_then_launches_exactly_once_after_restart(
    tmp_path, monkeypatch
) -> None:
    first_path = _write_predecessor(tmp_path)
    second_path = _write_predecessor(
        tmp_path, run_id=SECOND_PREDECESSOR_RUN_ID
    )
    queued = _queue_fanin_successor(tmp_path, monkeypatch)
    successor_path = Path(queued.manifest_path)
    committed = json.loads(successor_path.read_text())

    assert committed["queue"]["predecessor_run_ids"] == [
        PREDECESSOR_RUN_ID,
        SECOND_PREDECESSOR_RUN_ID,
    ]
    assert "predecessor_run_id" not in committed["queue"]
    assert len(committed["queue"]["predecessor_references"]) == 6
    assert len(committed["queue"]["predecessor_states"]) == 2

    _complete_predecessor(first_path)
    monkeypatch.setattr(
        subagent,
        "_spawn_managed_supervisor",
        lambda *args, **kwargs: pytest.fail("partial fan-in must not launch"),
    )
    partial = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    waiting = json.loads(successor_path.read_text())

    assert partial.waiting == 1
    assert partial.launched == 0
    assert waiting["queue"]["state"] == "waiting_predecessors"
    assert waiting["queue"]["predecessor_states"] == [
        {
            "run_id": PREDECESSOR_RUN_ID,
            "status": "completed",
            "result_state": "valid",
            "attention": "ready",
        },
        {
            "run_id": SECOND_PREDECESSOR_RUN_ID,
            "status": "running",
            "result_state": "pending",
            "attention": "waiting_for_predecessor",
        },
    ]

    _complete_predecessor(second_path)
    launches = []

    def launch(path, manifest):
        launches.append(path)
        running = json.loads(path.read_text())
        running.update({"status": "running", "pid": _Supervisor.pid})
        running["queue"].update({"state": "running", "attention": "none"})
        path.write_text(json.dumps(running))
        return _Supervisor(), running

    monkeypatch.setattr(subagent, "_spawn_managed_supervisor", launch)
    monkeypatch.setattr(
        subagent, "_pid_matches_manifest", lambda pid, path: pid == _Supervisor.pid
    )
    recovered = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    replay = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )

    assert recovered.launched == 1
    assert replay.launched == 0
    assert launches == [successor_path]
    assert json.loads(successor_path.read_text())["queue"]["attempt_count"] == 1


@pytest.mark.parametrize(
    ("second_status", "result", "expected_status", "expected_attention"),
    [
        ("failed", "", "failed", "predecessor_terminal_failure"),
        ("cancelled", "", "cancelled", "predecessor_cancelled"),
        ("superseded", "", "superseded", "predecessor_superseded"),
        ("completed", "", "failed", "predecessor_result_empty_or_invalid"),
    ],
)
def test_queue_fanin_propagates_any_terminal_dependency_violation(
    tmp_path,
    monkeypatch,
    second_status,
    result,
    expected_status,
    expected_attention,
) -> None:
    first_path = _write_predecessor(tmp_path)
    _complete_predecessor(first_path)
    _write_predecessor(
        tmp_path,
        run_id=SECOND_PREDECESSOR_RUN_ID,
        status=second_status,
        result=result,
    )
    queued = _queue_fanin_successor(tmp_path, monkeypatch)

    sweep = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    terminal = json.loads(Path(queued.manifest_path).read_text())

    assert sweep.failed_closed == 1
    assert terminal["status"] == expected_status
    assert terminal["queue"]["attention"] == expected_attention
    assert terminal["queue"]["failed_predecessor_run_id"] == (
        SECOND_PREDECESSOR_RUN_ID
    )
    assert len(terminal["queue"]["predecessor_states"]) == 2


def test_queue_dependency_input_contract_rejects_duplicates_mixed_and_malformed(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    _write_predecessor(tmp_path)
    provenance = _non_discord_provenance()
    common = {
        "task": "Synthesize dependency evidence.",
        "description": "Synthesize dependency evidence",
        "project_dir": str(tmp_path),
        "launch_origin": provenance,
    }

    with pytest.raises(subagent.SubagentQueueError, match="duplicate predecessor"):
        subagent.launch_codex_subagent_detached(
            **common,
            depends_on_run_ids=[PREDECESSOR_RUN_ID, PREDECESSOR_RUN_ID],
        )
    with pytest.raises(subagent.SubagentQueueError, match="mutually exclusive"):
        subagent.launch_codex_subagent_detached(
            **common,
            depends_on_run_id=PREDECESSOR_RUN_ID,
            depends_on_run_ids=[PREDECESSOR_RUN_ID],
        )
    with pytest.raises(subagent.SubagentQueueError, match="must not be empty"):
        subagent.launch_codex_subagent_detached(**common, depends_on_run_ids=[])
    with pytest.raises(subagent.SubagentQueueError, match="malformed"):
        subagent.launch_codex_subagent_detached(
            **common, depends_on_run_ids=[PREDECESSOR_RUN_ID, "bad-id"]
        )
    with pytest.raises(subagent.SubagentQueueError, match="unknown predecessor"):
        subagent.launch_codex_subagent_detached(
            **common,
            depends_on_run_ids=[
                PREDECESSOR_RUN_ID,
                "subagent-20260715-120200-dddddddd",
            ],
        )


def test_queue_fanin_cycle_and_committed_self_dependency_fail_closed(
    tmp_path, monkeypatch
) -> None:
    first_path = _write_predecessor(tmp_path)
    second_path = _write_predecessor(
        tmp_path, run_id=SECOND_PREDECESSOR_RUN_ID
    )
    first = json.loads(first_path.read_text())
    second = json.loads(second_path.read_text())
    first["queue"] = {
        "schema_version": subagent.QUEUE_SCHEMA,
        "predecessor_run_ids": [SECOND_PREDECESSOR_RUN_ID],
    }
    second["queue"] = {
        "schema_version": subagent.QUEUE_SCHEMA,
        "predecessor_run_ids": [PREDECESSOR_RUN_ID],
    }
    first_path.write_text(json.dumps(first))
    second_path.write_text(json.dumps(second))
    with pytest.raises(subagent.SubagentQueueError, match="cycle"):
        _queue_fanin_successor(tmp_path, monkeypatch)

    first.pop("queue")
    second.pop("queue")
    first_path.write_text(json.dumps(first))
    second_path.write_text(json.dumps(second))
    queued = _queue_fanin_successor(tmp_path, monkeypatch)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    successor["queue"].pop("predecessor_run_id", None)
    successor["queue"]["predecessor_run_ids"] = [queued.run_id]
    successor_path.write_text(json.dumps(successor))

    sweep = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    terminal = json.loads(successor_path.read_text())
    assert sweep.failed_closed == 1
    assert terminal["status"] == "failed"
    assert terminal["queue"]["attention"] == "invalid_dependency_contract"
    assert "depend on itself" in terminal["queue"]["last_validation_error"]["message"]


def test_queue_restart_recovery_replays_a_precommitted_launch_claim(
    tmp_path, monkeypatch
) -> None:
    predecessor_path = _write_predecessor(tmp_path)
    queued = _queue_successor(tmp_path, monkeypatch)
    _complete_predecessor(predecessor_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    successor["status"] = "launching"
    successor["queue"]["state"] = "launching"
    successor_path.write_text(json.dumps(successor))
    monkeypatch.setattr(subagent, "_pid_matches_manifest", lambda pid, path: False)
    launches = []
    monkeypatch.setattr(
        subagent,
        "_spawn_managed_supervisor",
        lambda path, manifest: (launches.append(path) or _Supervisor(), manifest),
    )

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )

    assert result.launched == 1
    assert launches == [successor_path]


def test_queue_pid_or_session_acceptance_is_not_completion_evidence(
    tmp_path, monkeypatch
) -> None:
    predecessor_path = _write_predecessor(tmp_path)
    queued = _queue_successor(tmp_path, monkeypatch)
    _complete_predecessor(predecessor_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    successor.update(
        {
            "status": "running",
            "pid": 999999,
            "session_dispatch": {
                "status": "accepted",
                "evidence": "provider_process_started_not_terminal",
            },
        }
    )
    successor_path.write_text(json.dumps(successor))
    monkeypatch.setattr(subagent, "_pid_matches_manifest", lambda pid, path: False)
    monkeypatch.setattr(
        subagent,
        "_spawn_managed_supervisor",
        lambda *args, **kwargs: pytest.fail("ambiguous accepted execution must not relaunch"),
    )

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    terminal = json.loads(successor_path.read_text())

    assert result.failed_closed == 1
    assert terminal["status"] == "failed"
    assert terminal["queue"]["attention"] == (
        "successor_execution_lost_supervisor_without_terminal_evidence"
    )


@pytest.mark.parametrize("predecessor_status", ["failed", "interrupted"])
def test_queue_predecessor_failure_fails_closed(
    tmp_path, monkeypatch, predecessor_status
) -> None:
    _write_predecessor(tmp_path, status=predecessor_status)
    queued = _queue_successor(tmp_path, monkeypatch)

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    successor = json.loads(Path(queued.manifest_path).read_text())

    assert result.failed_closed == 1
    assert successor["status"] == "failed"
    assert successor["queue"]["attention"] == "predecessor_terminal_failure"


def test_queue_unknown_predecessor_status_fails_closed_instead_of_waiting(
    tmp_path, monkeypatch
) -> None:
    _write_predecessor(tmp_path, status="UNKNOWN_FROM_STALE_READER")
    queued = _queue_successor(tmp_path, monkeypatch)

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    successor = json.loads(Path(queued.manifest_path).read_text())

    assert result.failed_closed == 1
    assert result.waiting == 0
    assert successor["status"] == "failed"
    assert successor["queue"]["predecessor_status"] == "unknown"
    assert successor["queue"]["attention"] == "predecessor_status_unknown"


@pytest.mark.parametrize("predecessor_status", ["cancelled", "superseded"])
def test_queue_cancellation_and_supersession_propagate(
    tmp_path, monkeypatch, predecessor_status
) -> None:
    _write_predecessor(tmp_path, status=predecessor_status)
    queued = _queue_successor(tmp_path, monkeypatch)

    subagent.reconcile_managed_subagent_queues(project_root=tmp_path, workspace_root=None)
    successor = json.loads(Path(queued.manifest_path).read_text())

    assert successor["status"] == predecessor_status
    assert successor["queue"]["attention"] == f"predecessor_{predecessor_status}"


@pytest.mark.parametrize("result", ["", None])
def test_queue_missing_or_invalid_result_fails_closed(tmp_path, monkeypatch, result) -> None:
    predecessor_path = _write_predecessor(tmp_path)
    queued = _queue_successor(tmp_path, monkeypatch)
    _complete_predecessor(predecessor_path, result=result or "temporary")
    if result is None:
        Path(json.loads(predecessor_path.read_text())["result_path"]).unlink()
    else:
        Path(json.loads(predecessor_path.read_text())["result_path"]).write_text("")

    subagent.reconcile_managed_subagent_queues(project_root=tmp_path, workspace_root=None)
    successor = json.loads(Path(queued.manifest_path).read_text())

    assert successor["status"] == "failed"
    assert successor["queue"]["attention"] in {
        "predecessor_result_missing",
        "predecessor_result_empty_or_invalid",
    }


def test_queue_prompt_and_references_are_bounded_without_inlining_output(
    tmp_path, monkeypatch
) -> None:
    secret_output = "OUTPUT-MUST-NOT-BE-INLINED"
    _write_predecessor(tmp_path, status="completed", result=secret_output)
    queued = _queue_successor(tmp_path, monkeypatch)
    manifest = json.loads(Path(queued.manifest_path).read_text())
    prompt = Path(manifest["prompt_path"]).read_text()

    assert secret_output not in prompt
    assert "[Queued predecessor references" in prompt
    assert len(manifest["queue"]["predecessor_references"]) == 3
    with pytest.raises(ValueError, match="queued successor prompt exceeds"):
        _queue_successor(
            tmp_path,
            monkeypatch,
            prompt="x" * (subagent.MAX_QUEUE_PROMPT_CHARS + 1),
        )


def test_queue_inherits_discord_provenance_and_cannot_broaden_authorization(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    provenance = _discord_provenance()
    _write_predecessor(tmp_path, provenance=provenance)
    with pytest.raises(
        subagent.SubagentQueueError, match="must inherit predecessor work_intent"
    ):
        subagent.launch_codex_subagent_detached(
            task="Check the output of this agent and use it to finish the request.",
            description="Finish the same Discord request",
            project_dir=str(tmp_path),
            launch_origin=provenance,
            task_kind="coding",
            work_intent="execution",
            depends_on_run_id=PREDECESSOR_RUN_ID,
        )
    queued = subagent.launch_codex_subagent_detached(
        task="Check the output of this agent and use it to finish the request.",
        description="Finish the same Discord request",
        project_dir=str(tmp_path),
        launch_origin=provenance,
        task_kind="coding",
        work_intent="auto",
        depends_on_run_id=PREDECESSOR_RUN_ID,
    )
    manifest = json.loads(Path(queued.manifest_path).read_text())

    assert manifest["launch_provenance"] == provenance
    assert manifest["project_dir"] == str(tmp_path)
    assert manifest["work_intent"] == "review"
    assert manifest["delegation_delivery_instruction"]["resolved_work_intent"] == "review"
    assert manifest["source_record_id"] == provenance["source_record_id"]
    predecessor_path = (
        tmp_path
        / ".megaplan/plans/resident-subagents"
        / PREDECESSOR_RUN_ID
        / "manifest.json"
    )
    predecessor = json.loads(predecessor_path.read_text())
    assert predecessor["completion_delivery"]["status"] == "superseded"
    assert manifest["completion_delivery"]["status"] == "pending"


def test_queue_fanin_preserves_provenance_and_exactly_one_delivery_owner(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    provenance = _discord_provenance()
    first_path = _write_predecessor(tmp_path, provenance=provenance)
    second_path = _write_predecessor(
        tmp_path,
        run_id=SECOND_PREDECESSOR_RUN_ID,
        provenance=provenance,
    )
    queued = _queue_fanin_successor(
        tmp_path, monkeypatch, provenance=provenance
    )
    successor = json.loads(Path(queued.manifest_path).read_text())
    predecessors = [
        json.loads(first_path.read_text()),
        json.loads(second_path.read_text()),
    ]

    assert successor["launch_provenance"] == provenance
    assert successor["aggregation"]["role"] == "synthesis_delivery_owner"
    assert successor["aggregation"]["delivery_owner_run_id"] == queued.run_id
    assert successor["completion_delivery"]["status"] == "pending"
    assert successor["completion_delivery"]["reply_target"]["source_record_id"] == (
        provenance["source_record_id"]
    )
    assert all(
        item["aggregation"]["role"] == "internal_contributor"
        and item["completion_delivery"]["status"] == "superseded"
        for item in predecessors
    )


def test_cross_request_queue_uses_authoritative_same_subject_and_current_delivery(
    tmp_path, monkeypatch
) -> None:
    current, predecessor_path = _cross_request_fixture(tmp_path, monkeypatch)

    queued = _queue_cross_request(tmp_path)
    replayed = _queue_cross_request(tmp_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())

    assert queued.status == "queued"
    assert replayed.run_id == queued.run_id
    assert successor["route_class"] == "queued_cross_request_successor"
    assert successor["launch_provenance"] == current
    assert successor["source_record_id"] == current["source_record_id"]
    assert successor["aggregation"]["key"] == "aggregation-current-request"
    assert successor["aggregation"]["role"] == "synthesis_delivery_owner"
    assert successor["completion_delivery"]["reply_target"]["source_record_id"] == current[
        "source_record_id"
    ]
    authorization = successor["queue"]["cross_request_authorization"]
    assert authorization["schema_version"] == (
        subagent.QUEUE_CROSS_REQUEST_AUTHORIZATION_SCHEMA
    )
    assert authorization["predecessor_run_id"] == PREDECESSOR_RUN_ID
    assert "42" not in json.dumps(authorization)
    inspected = resident_cli._resident_inspect_subagent_queue(
        tmp_path,
        argparse.Namespace(
            project_dir=str(tmp_path), run_id=queued.run_id, limit=8
        ),
    )
    assert inspected["items"][0]["authorization_mode"] == (
        "same_subject_same_conversation_explicit_predecessor"
    )
    predecessor = json.loads(predecessor_path.read_text())
    assert predecessor["aggregation"]["role"] == "synthesis_delivery_owner"
    assert predecessor["completion_delivery"]["status"] == "pending"


def test_cross_request_queue_accepts_immutable_resident_root_turn_authority(
    tmp_path, monkeypatch
) -> None:
    current, predecessor_path, turn_path = _cross_request_root_turn_fixture(
        tmp_path, monkeypatch
    )

    queued = _queue_cross_request(tmp_path)
    successor = json.loads(Path(queued.manifest_path).read_text())
    authorization = successor["queue"]["cross_request_authorization"]

    assert queued.status == "queued"
    assert successor["launch_provenance"] == current
    assert authorization["authorization_source"] == "resident_root_turn"
    assert authorization["caller_turn_id"] == current["resident_turn_id"]
    assert "caller_run_id" not in authorization
    assert authorization["current_source_record_id"] == current["source_record_id"]

    turn = json.loads(turn_path.read_text())
    turn["status"] = "completed"
    turn["completed_at"] = "2026-07-15T13:01:00+00:00"
    turn_path.write_text(json.dumps(turn))
    _complete_predecessor(predecessor_path)
    launched: list[Path] = []
    monkeypatch.setattr(
        subagent,
        "_spawn_managed_supervisor",
        lambda path, manifest: (launched.append(path) or _Supervisor(), manifest),
    )

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )

    assert result.launched == 1
    assert launched == [Path(queued.manifest_path)]


@pytest.mark.parametrize(
    ("fixture_kwargs", "error"),
    [
        ({"current_author": "43"}, "changed Discord subject"),
        (
            {"current_conversation": "rconv_otherconv"},
            "changed resident conversation",
        ),
        (
            {"names_predecessor": False},
            "does not explicitly name predecessor",
        ),
    ],
)
def test_cross_request_queue_denies_wrong_subject_conversation_or_missing_explicit_name(
    tmp_path, monkeypatch, fixture_kwargs, error
) -> None:
    _cross_request_fixture(tmp_path, monkeypatch, **fixture_kwargs)

    with pytest.raises(subagent.SubagentQueueError, match=error):
        _queue_cross_request(tmp_path)


def test_cross_request_queue_denies_missing_authoritative_provenance(
    tmp_path, monkeypatch
) -> None:
    _cross_request_fixture(tmp_path, monkeypatch)
    (tmp_path / ".megaplan/resident/messages/msg_currentreq1.json").unlink()

    with pytest.raises(ValueError, match="source_record_id does not match"):
        _queue_cross_request(tmp_path)


def test_cross_request_queue_reconciliation_revalidates_authorization_after_restart(
    tmp_path, monkeypatch
) -> None:
    _, predecessor_path = _cross_request_fixture(tmp_path, monkeypatch)
    queued = _queue_cross_request(tmp_path)
    _complete_predecessor(predecessor_path)
    caller_path = (
        tmp_path
        / ".megaplan/plans/resident-subagents"
        / CALLER_RUN_ID
        / "manifest.json"
    )
    caller = json.loads(caller_path.read_text())
    caller["status"] = "completed"
    caller_path.write_text(json.dumps(caller))
    launched = []
    monkeypatch.setattr(
        subagent,
        "_spawn_managed_supervisor",
        lambda path, manifest: (launched.append(path) or _Supervisor(), manifest),
    )

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )

    assert result.launched == 1
    assert launched == [Path(queued.manifest_path)]


def test_cross_request_queue_recovers_exact_stale_runtime_unknown_predecessor_rejection(
    tmp_path, monkeypatch
) -> None:
    """A pre-feature predecessor worker must not permanently kill a newer queue."""

    _, predecessor_path = _cross_request_fixture(tmp_path, monkeypatch)
    queued = _queue_cross_request(tmp_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    rejected_at = "2026-07-15T21:20:43.605255+00:00"
    successor.update(
        {
            "status": "failed",
            "terminal_outcome": "failed",
            "finished_at": rejected_at,
            "updated_at": rejected_at,
            "error": "queued successor dependency failed closed",
            "error_class": "ResidentSubagentDependencyFailure",
        }
    )
    successor["queue"].update(
        {
            "state": "dependency_failed",
            "attention": "invalid_dependency_contract",
            "predecessor_status": "unknown",
            "failed_at": rejected_at,
            "updated_at": rejected_at,
        }
    )
    successor["status_history"].append(
        {
            "status": "failed",
            "at": rejected_at,
            "evidence": "invalid_dependency_contract",
            "predecessor_status": "unknown",
        }
    )
    successor_path.write_text(json.dumps(successor))

    waiting = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    recovered = json.loads(successor_path.read_text())

    assert waiting.waiting == 1
    assert waiting.failed_closed == 0
    assert recovered["status"] == "queued"
    assert recovered["queue"]["state"] == "waiting_predecessor"
    assert recovered["queue"]["predecessor_status"] == "running"
    assert recovered["queue"]["attention"] == "waiting_for_predecessor"
    assert "revalidated_at" in recovered["queue"]
    assert "terminal_outcome" not in recovered
    assert recovered["status_history"][-1]["evidence"] == (
        "valid_contract_recovered_after_stale_runtime_rejection"
    )

    _complete_predecessor(predecessor_path)
    launches = []

    def launch(path, manifest):
        launches.append(path)
        running = json.loads(path.read_text())
        running.update({"status": "running", "pid": _Supervisor.pid})
        path.write_text(json.dumps(running))
        return _Supervisor(), manifest

    monkeypatch.setattr(
        subagent,
        "_spawn_managed_supervisor",
        launch,
    )
    monkeypatch.setattr(
        subagent, "_pid_matches_manifest", lambda pid, path: pid == _Supervisor.pid
    )

    first = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    second = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )

    assert first.launched == 1
    assert second.launched == 0
    assert launches == [successor_path]


def test_cross_request_queue_incident_contract_survives_restart_and_keeps_delivery_owner(
    tmp_path, monkeypatch
) -> None:
    """The live incident shape remains success-gated, durable, and exactly once."""

    _, predecessor_path = _cross_request_fixture(tmp_path, monkeypatch)
    queued = _queue_cross_request(tmp_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    expected_aggregation = successor["aggregation"]
    expected_delivery = successor["completion_delivery"]
    rejected_at = "2026-07-15T21:20:43.605255+00:00"
    successor.update(
        {
            "status": "failed",
            "terminal_outcome": "failed",
            "finished_at": rejected_at,
            "updated_at": rejected_at,
            "error": "queued successor dependency failed closed",
            "error_class": "ResidentSubagentDependencyFailure",
        }
    )
    successor["queue"].update(
        {
            "state": "dependency_failed",
            "attention": "invalid_dependency_contract",
            "predecessor_status": "unknown",
            "failed_at": rejected_at,
            "updated_at": rejected_at,
        }
    )
    successor["status_history"].append(
        {
            "status": "failed",
            "at": rejected_at,
            "evidence": "invalid_dependency_contract",
            "predecessor_status": "unknown",
        }
    )
    successor_path.write_text(json.dumps(successor))

    # A later scheduler sweep models the post-restart resident. Recovery reads
    # only these durable manifests; the queue has no process-local launch state.
    waiting = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    recovered = json.loads(successor_path.read_text())

    assert waiting.waiting == 1
    assert waiting.launched == 0
    assert recovered["status"] == "queued"
    assert recovered["queue"]["predecessor_status"] == "running"
    assert recovered["aggregation"] == expected_aggregation
    assert recovered["aggregation"]["role"] == "synthesis_delivery_owner"
    assert recovered["completion_delivery"] == expected_delivery
    assert recovered["completion_delivery"]["status"] == "pending"

    _complete_predecessor(predecessor_path)
    launches = []

    def launch(path, manifest):
        launches.append(path)
        running = json.loads(path.read_text())
        running.update({"status": "running", "pid": _Supervisor.pid})
        path.write_text(json.dumps(running))
        return _Supervisor(), manifest

    monkeypatch.setattr(subagent, "_spawn_managed_supervisor", launch)
    monkeypatch.setattr(
        subagent, "_pid_matches_manifest", lambda pid, path: pid == _Supervisor.pid
    )

    first = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    second = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    running = json.loads(successor_path.read_text())

    assert first.launched == 1
    assert second.launched == 0
    assert launches == [successor_path]
    assert running["queue"]["attempt_count"] == 1
    assert running["aggregation"] == expected_aggregation
    assert running["completion_delivery"] == expected_delivery


def test_cross_request_queue_stale_rejection_recovery_remains_fail_closed_on_tamper(
    tmp_path, monkeypatch
) -> None:
    _cross_request_fixture(tmp_path, monkeypatch)
    queued = _queue_cross_request(tmp_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    rejected_at = "2026-07-15T21:20:43.605255+00:00"
    successor.update(
        {
            "status": "failed",
            "terminal_outcome": "failed",
            "finished_at": rejected_at,
            "error": "queued successor dependency failed closed",
            "error_class": "ResidentSubagentDependencyFailure",
        }
    )
    successor["queue"].update(
        {
            "state": "dependency_failed",
            "attention": "invalid_dependency_contract",
            "predecessor_status": "unknown",
            "failed_at": rejected_at,
        }
    )
    successor["queue"]["cross_request_authorization"][
        "predecessor_run_id"
    ] = "subagent-20260715-120000-ffffffff"
    successor["status_history"].append(
        {
            "status": "failed",
            "at": rejected_at,
            "evidence": "invalid_dependency_contract",
            "predecessor_status": "unknown",
        }
    )
    successor_path.write_text(json.dumps(successor))

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    terminal = json.loads(successor_path.read_text())

    assert result.failed_closed == 1
    assert terminal["status"] == "failed"
    assert terminal["queue"]["attention"] == "invalid_dependency_contract"
    assert "revalidated_at" not in terminal["queue"]


def test_cross_request_queue_stale_rejection_does_not_recover_after_delivery(
    tmp_path, monkeypatch
) -> None:
    _cross_request_fixture(tmp_path, monkeypatch)
    queued = _queue_cross_request(tmp_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    rejected_at = "2026-07-15T21:20:43.605255+00:00"
    successor.update(
        {
            "status": "failed",
            "terminal_outcome": "failed",
            "finished_at": rejected_at,
            "error": "queued successor dependency failed closed",
            "error_class": "ResidentSubagentDependencyFailure",
        }
    )
    successor["queue"].update(
        {
            "state": "dependency_failed",
            "attention": "invalid_dependency_contract",
            "predecessor_status": "unknown",
            "failed_at": rejected_at,
        }
    )
    successor["completion_delivery"].update(
        {"status": "delivered", "attempt_count": 1, "delivered_at": rejected_at}
    )
    successor["status_history"].append(
        {
            "status": "failed",
            "at": rejected_at,
            "evidence": "invalid_dependency_contract",
            "predecessor_status": "unknown",
        }
    )
    successor_path.write_text(json.dumps(successor))

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    terminal = json.loads(successor_path.read_text())

    assert result.skipped == 1
    assert result.waiting == 0
    assert terminal["status"] == "failed"
    assert terminal["completion_delivery"]["status"] == "delivered"
    assert terminal["queue"]["attention"] == "invalid_dependency_contract"
    assert "revalidated_at" not in terminal["queue"]


def test_cross_request_queue_preserves_failure_propagation(
    tmp_path, monkeypatch
) -> None:
    _, predecessor_path = _cross_request_fixture(tmp_path, monkeypatch)
    queued = _queue_cross_request(tmp_path)
    predecessor = json.loads(predecessor_path.read_text())
    predecessor.update(
        {"status": "failed", "terminal_outcome": "failed", "returncode": 1}
    )
    predecessor_path.write_text(json.dumps(predecessor))

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    successor = json.loads(Path(queued.manifest_path).read_text())

    assert result.failed_closed == 1
    assert successor["status"] == "failed"
    assert successor["queue"]["attention"] == "predecessor_terminal_failure"


def test_cross_request_queue_fails_closed_if_authorization_or_source_record_changes(
    tmp_path, monkeypatch
) -> None:
    _cross_request_fixture(tmp_path, monkeypatch)
    queued = _queue_cross_request(tmp_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    del successor["queue"]["cross_request_authorization"]
    successor_path.write_text(json.dumps(successor))

    result = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )
    terminal = json.loads(successor_path.read_text())

    assert result.failed_closed == 1
    assert terminal["status"] == "failed"
    assert terminal["queue"]["attention"] == "invalid_dependency_contract"
    assert terminal["queue"]["last_validation_error"]["error_class"] == (
        "SubagentQueueError"
    )
    assert terminal["queue"]["predecessor_status"] == "running"


def test_idempotent_replay_recovers_zero_attempt_cross_request_false_terminal(
    tmp_path, monkeypatch
) -> None:
    _cross_request_fixture(tmp_path, monkeypatch)
    queued = _queue_cross_request(tmp_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    subagent._queue_terminalize(
        successor_path,
        successor,
        status="failed",
        reason="invalid_dependency_contract",
        predecessor_status="unknown",
        now=datetime(2026, 7, 15, 12, 3, tzinfo=timezone.utc),
    )

    replayed = _queue_cross_request(tmp_path)
    recovered = json.loads(successor_path.read_text())
    sweep = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None
    )

    assert replayed.run_id == queued.run_id
    assert replayed.status == "queued"
    assert recovered["status"] == "queued"
    assert recovered["queue"]["state"] == "waiting_predecessor"
    assert recovered["queue"]["attempt_count"] == 0
    assert recovered["queue"]["recovery_reason"] == (
        "idempotent_replay_revalidated_dependency_contract"
    )
    assert sweep.waiting == 1


def test_idempotent_replay_does_not_recover_already_delivered_false_terminal(
    tmp_path, monkeypatch
) -> None:
    _cross_request_fixture(tmp_path, monkeypatch)
    queued = _queue_cross_request(tmp_path)
    successor_path = Path(queued.manifest_path)
    successor = json.loads(successor_path.read_text())
    subagent._queue_terminalize(
        successor_path,
        successor,
        status="failed",
        reason="invalid_dependency_contract",
        predecessor_status="unknown",
        now=datetime(2026, 7, 15, 12, 3, tzinfo=timezone.utc),
    )
    terminal = json.loads(successor_path.read_text())
    terminal["completion_delivery"]["status"] = "delivered"
    successor_path.write_text(json.dumps(terminal))

    replayed = _queue_cross_request(tmp_path)

    assert replayed.run_id == queued.run_id
    assert replayed.status == "failed"


def test_cross_request_queue_denies_delivered_aggregation_owner(
    tmp_path, monkeypatch
) -> None:
    _cross_request_fixture(tmp_path, monkeypatch)
    conflict_dir = (
        tmp_path
        / ".megaplan/plans/resident-subagents"
        / "subagent-20260715-140000-cccccccc"
    )
    conflict_dir.mkdir(parents=True)
    conflict_dir.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "schema_version": MANAGED_AGENT_SCHEMA,
                "run_kind": "resident_delegated_agent",
                "custodian": MANAGED_AGENT_CUSTODIAN,
                "run_id": "subagent-20260715-140000-cccccccc",
                "aggregation": {
                    "key": "aggregation-current-request",
                    "role": "synthesis_delivery_owner",
                },
                "completion_delivery": {"status": "delivered"},
            }
        )
    )

    with pytest.raises(ValueError, match="already has a delivered owner"):
        _queue_cross_request(tmp_path)


def test_queue_cycle_is_rejected_before_successor_commit(tmp_path, monkeypatch) -> None:
    predecessor_path = _write_predecessor(tmp_path)
    predecessor = json.loads(predecessor_path.read_text())
    predecessor["queue"] = {
        "schema_version": subagent.QUEUE_SCHEMA,
        "predecessor_run_id": PREDECESSOR_RUN_ID,
    }
    predecessor_path.write_text(json.dumps(predecessor))

    with pytest.raises(subagent.SubagentQueueError, match="cycle"):
        _queue_successor(tmp_path, monkeypatch)


def test_queue_launch_retries_are_bounded_and_recover(tmp_path, monkeypatch) -> None:
    predecessor_path = _write_predecessor(tmp_path)
    queued = _queue_successor(tmp_path, monkeypatch, max_attempts=2)
    _complete_predecessor(predecessor_path)
    calls = 0

    def launch(path, manifest):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("transient launch failure")
        return _Supervisor(), manifest

    monkeypatch.setattr(subagent, "_spawn_managed_supervisor", launch)
    now = datetime(2026, 7, 15, 12, 2, tzinfo=timezone.utc)
    first = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path, workspace_root=None, now=now
    )
    pending = json.loads(Path(queued.manifest_path).read_text())
    second = subagent.reconcile_managed_subagent_queues(
        project_root=tmp_path,
        workspace_root=None,
        now=now + timedelta(seconds=6),
    )

    assert first.retry_pending == 1
    assert pending["queue"]["state"] == "retry_pending"
    assert second.launched == 1
    assert calls == 2


def test_queue_hot_context_is_bounded_and_truncated(tmp_path) -> None:
    run_root = tmp_path / ".megaplan/plans/resident-subagents"
    for index in range(12):
        run_id = f"subagent-20260715-12{index:04d}-abcd{index:04d}"
        run_dir = run_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": MANAGED_AGENT_SCHEMA,
                    "run_kind": "resident_delegated_agent",
                    "custodian": MANAGED_AGENT_CUSTODIAN,
                    "run_id": run_id,
                    "status": "queued",
                    "created_at": f"2026-07-15T12:{index:02d}:00+00:00",
                    "description": "d" * 180,
                    "launch_provenance": _non_discord_provenance(),
                    "queue": {
                        "schema_version": subagent.QUEUE_SCHEMA,
                        "state": "waiting_predecessor",
                        "attention": "waiting_for_predecessor",
                        "predecessor_run_id": PREDECESSOR_RUN_ID,
                        "successor_run_id": run_id,
                        "authored_prompt": {
                            "description": "p" * 500,
                            "size_chars": 999999,
                        },
                    },
                }
            )
        )

    inventory = subagent.list_managed_resident_agents(
        project_root=tmp_path, workspace_root=None
    )
    hot = profile_module._compact_resident_agents(inventory)

    assert inventory["queued_count"] == 12
    assert len(inventory["queued"]) == subagent.MAX_QUEUE_HOT_CONTEXT_ROWS
    assert len(hot["queued"]) == 8
    assert hot["queued_omitted_count"] == 4
    assert len(hot["queued"][0]["queue"]["authored_prompt"]["description"]) == 180
    assert "predecessor_references" not in hot["queued"][0]["queue"]
    assert len(json.dumps(hot)) < 20_000
    routed = read_context_node(
        {"agents": hot}, node_id="agents/queued", cursor=0, limit=8
    )
    assert routed["success"] is True
    assert len(routed["node"]["items"]) == 8


def test_resident_cli_can_create_and_inspect_bounded_queue_dependency(
    tmp_path, monkeypatch
) -> None:
    _write_predecessor(tmp_path)
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    created = resident_cli._resident_queue_subagent_successor(
        tmp_path,
        ResidentConfig(),
        argparse.Namespace(
            prompt="Check the output of this agent and use it to finalize the note.",
            prompt_file=None,
            description="Finalize the queued note",
            project_dir=str(tmp_path),
            after_run_id=PREDECESSOR_RUN_ID,
            max_launch_attempts=3,
        ),
    )
    inspected = resident_cli._resident_inspect_subagent_queue(
        tmp_path,
        argparse.Namespace(
            project_dir=str(tmp_path),
            run_id=created["run_id"],
            limit=8,
        ),
    )

    assert created["status"] == "queued"
    assert created["authorization_mode"] == "same_request_custody"
    assert inspected["count"] == 1
    assert inspected["items"][0]["predecessor_run_id"] == PREDECESSOR_RUN_ID
    assert inspected["items"][0]["authorization_mode"] == "same_request_custody"
    assert len(inspected["items"][0]["predecessor_references"]) == 3


def test_resident_cli_plural_contract_exposes_complete_dependency_states(
    tmp_path, monkeypatch
) -> None:
    _write_predecessor(tmp_path)
    _write_predecessor(tmp_path, run_id=SECOND_PREDECESSOR_RUN_ID)
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    created = resident_cli._resident_queue_subagent_successor(
        tmp_path,
        ResidentConfig(),
        argparse.Namespace(
            prompt="Synthesize every predecessor into one final note.",
            prompt_file=None,
            description="Finalize the fan-in note",
            project_dir=str(tmp_path),
            after_run_id=None,
            after_run_ids=[PREDECESSOR_RUN_ID, SECOND_PREDECESSOR_RUN_ID],
            max_launch_attempts=3,
        ),
    )
    inspected = resident_cli._resident_inspect_subagent_queue(
        tmp_path,
        argparse.Namespace(
            project_dir=str(tmp_path), run_id=created["run_id"], limit=8
        ),
    )

    assert created["predecessor_run_id"] is None
    assert created["predecessor_run_ids"] == [
        PREDECESSOR_RUN_ID,
        SECOND_PREDECESSOR_RUN_ID,
    ]
    item = inspected["items"][0]
    assert item["predecessor_run_ids"] == created["predecessor_run_ids"]
    assert [state["run_id"] for state in item["predecessor_states"]] == (
        created["predecessor_run_ids"]
    )
    assert len(item["predecessor_references"]) == 6
