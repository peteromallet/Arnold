from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import threading

import pytest

from arnold_pipelines.megaplan.resident import subagent
from arnold_pipelines.megaplan.resident.provenance import (
    DELEGATION_CONTEXT_ENV,
    encoded_provenance,
    normalize_delegation_provenance,
)


SESSION_ID = "019f5d2e-d5da-75f3-a617-4712a1c57cc4"
TARGET_RUN_ID = "subagent-20260713-203257-59552356"
QUEUED_OWNER_RUN_ID = "subagent-20260713-203300-aaaaaaaa"
SECOND_PREDECESSOR_RUN_ID = "subagent-20260713-203258-bbbbbbbb"


def _provenance(*, source: str, message: str, conversation: str = "rconv_followuptest") -> dict:
    return normalize_delegation_provenance(
        {
            "schema_version": "arnold-resident-delegation-provenance-v1",
            "applicability": "applicable",
            "transport": "discord",
            "resident_conversation_id": conversation,
            "source_record_id": source,
            "conversation_key": "discord:dm:42",
            "discord_message_id": message,
            "reply_to_message_id": message,
            "dm_user_id": "42",
            "source_kind": "discord_inbound_message",
        }
    )


def _write_run(
    root: Path,
    *,
    run_id: str = TARGET_RUN_ID,
    status: str = "completed",
    provenance: dict | None = None,
    session_id: str | None = SESSION_ID,
    pid: int | None = None,
    lineage_root_run_id: str | None = None,
    parent_run_id: str | None = None,
) -> Path:
    run_dir = root / ".megaplan/plans/resident-subagents" / run_id
    run_dir.mkdir(parents=True)
    log_path = run_dir / "run.log"
    log_path.write_text(f"session id: {session_id}\n" if session_id else "starting\n")
    manifest = {
        "schema_version": "arnold-managed-agent-run-v2",
        "run_kind": "resident_delegated_agent",
        "custodian": "arnold.megaplan.managed_agent",
        "run_id": run_id,
        "status": status,
        "pid": pid,
        "project_dir": str(root),
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "task_kind": "architecture",
        "difficulty": 8,
        "route_class": "ambiguous_or_high_risk",
        "log_path": str(log_path),
        "launch_provenance": provenance
        or _provenance(source="msg_originalsource", message="1001"),
        "created_at": "2026-07-13T20:32:57+00:00",
    }
    if lineage_root_run_id:
        manifest["lineage_root_run_id"] = lineage_root_run_id
    if parent_run_id:
        manifest["parent_run_id"] = parent_run_id
    path = run_dir / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def _write_queued_synthesis_owner(root: Path) -> tuple[Path, Path]:
    target_path = _write_run(root, status="running", session_id=None, pid=111)
    second_path = _write_run(
        root,
        run_id=SECOND_PREDECESSOR_RUN_ID,
        status="completed",
        session_id=None,
    )
    aggregation_key = "resident-synthesis-group-test"
    synthesis_group = "queued-owner-test"
    for path in (target_path, second_path):
        manifest = json.loads(path.read_text())
        manifest["aggregation"] = {
            "schema_version": "arnold-resident-agent-aggregation-v1",
            "key": aggregation_key,
            "synthesis_group": synthesis_group,
            "role": "internal_contributor",
            "delivery_owner_run_id": QUEUED_OWNER_RUN_ID,
        }
        manifest["completion_delivery"] = {"status": "suppressed"}
        path.write_text(json.dumps(manifest))

    owner_dir = root / ".megaplan/plans/resident-subagents" / QUEUED_OWNER_RUN_ID
    owner_dir.mkdir(parents=True)
    prompt_path = owner_dir / "prompt.md"
    prompt = "Synthesize both successful recovery runs and deliver once.\n"
    prompt_path.write_text(prompt)
    owner_path = owner_dir / "manifest.json"
    owner = {
        "schema_version": "arnold-managed-agent-run-v2",
        "run_kind": "resident_delegated_agent",
        "custodian": "arnold.megaplan.managed_agent",
        "run_id": QUEUED_OWNER_RUN_ID,
        "status": "queued",
        "project_dir": str(root),
        "prompt_path": str(prompt_path),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "launch_provenance": _provenance(
            source="msg_originalsource", message="1001"
        ),
        "parent_run_id": TARGET_RUN_ID,
        "lineage_root_run_id": TARGET_RUN_ID,
        "aggregation": {
            "schema_version": "arnold-resident-agent-aggregation-v1",
            "key": aggregation_key,
            "synthesis_group": synthesis_group,
            "role": "synthesis_delivery_owner",
            "delivery_owner_run_id": QUEUED_OWNER_RUN_ID,
            "contributors": [
                {"run_id": TARGET_RUN_ID},
                {"run_id": SECOND_PREDECESSOR_RUN_ID},
            ],
        },
        "completion_delivery": {"status": "pending"},
        "queue": {
            "schema_version": "arnold-resident-subagent-queue-v1",
            "state": "waiting_predecessors",
            "predecessor_run_ids": [TARGET_RUN_ID, SECOND_PREDECESSOR_RUN_ID],
            "predecessor_states": [
                {"run_id": TARGET_RUN_ID, "status": "running"},
                {"run_id": SECOND_PREDECESSOR_RUN_ID, "status": "completed"},
            ],
        },
        "created_at": "2026-07-13T20:33:00+00:00",
    }
    owner_path.write_text(json.dumps(owner))
    return target_path, owner_path


class _Supervisor:
    pid = 4321


@pytest.fixture
def caller_provenance(monkeypatch) -> dict:
    caller = _provenance(source="msg_newfollowupsrc", message="2002")
    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, encoded_provenance(caller))
    return caller


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "interrupted"])
def test_terminal_followup_creates_auditable_session_continuation(
    tmp_path: Path, monkeypatch, caller_provenance: dict, terminal_status: str
) -> None:
    target_path = _write_run(tmp_path, status=terminal_status)
    launches: list[list[str]] = []

    def fake_popen(argv, **kwargs):
        launches.append(list(argv))
        return _Supervisor()

    monkeypatch.setattr(subagent.subprocess, "Popen", fake_popen)
    result = subagent.follow_up_managed_subagent(
        run_id=TARGET_RUN_ID,
        message="Add the authoritative request and factual session summaries.",
        project_dir=tmp_path,
        workspace_root=None,
    )

    assert result.ok is True
    assert result.target_run_id == TARGET_RUN_ID
    assert result.parent_run_id == TARGET_RUN_ID
    assert result.lineage_root_run_id == TARGET_RUN_ID
    assert result.model_session_id == SESSION_ID
    assert result.status == "continuation_started"
    assert len(launches) == 1

    record = json.loads(Path(result.evidence_path).read_text())
    child = json.loads(Path(result.continuation_manifest_path).read_text())
    assert Path(record["message_path"]).read_text().strip() == (
        "Add the authoritative request and factual session summaries."
    )
    assert record["state_history"][-1]["evidence"] == (
        "terminal_lineage_continuation_supervisor_started"
    )
    assert child["parent_run_id"] == TARGET_RUN_ID
    assert child["lineage_root_run_id"] == TARGET_RUN_ID
    assert child["continued_session_id"] == SESSION_ID
    assert child["followup_id"] == result.followup_id
    assert Path(child["parent_manifest_path"]) == target_path
    assert child["launch_provenance"] == caller_provenance
    assert child["discord_origin"]["reply_to_message_id"] == "2002"
    assert child["discord_origin"]["reply_target_source_record_id"] == (
        "msg_newfollowupsrc"
    )


def test_contributor_followup_attaches_to_existing_queued_synthesis_owner(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    target_path, owner_path = _write_queued_synthesis_owner(tmp_path)
    monkeypatch.setattr(
        subagent.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("queued owner attachment launched a worker"),
    )
    message = (
        "Use exact epic revision 28d54763 and change only upcoming M6A-M11; "
        "completed M5/M5A and current M6 are immutable."
    )

    result = subagent.follow_up_managed_subagent(
        run_id=TARGET_RUN_ID,
        message=message,
        project_dir=tmp_path,
        workspace_root=None,
        idempotency_key="custody-revision-28d54763",
    )

    assert result.ok is True
    assert result.route == "queued_synthesis_owner"
    assert result.delivery_owner_run_id == QUEUED_OWNER_RUN_ID
    assert result.continuation_run_id is None
    assert result.continuation_manifest_path is None
    assert result.status == "accepted"
    receipt = json.loads(Path(result.evidence_path).read_text())
    owner = json.loads(owner_path.read_text())
    target = json.loads(target_path.read_text())
    prompt = Path(owner["prompt_path"]).read_text()
    assert message in prompt
    assert receipt["state_history"][-1]["evidence"] == (
        "material_bound_to_existing_queued_synthesis_owner_prompt"
    )
    assert owner["prompt_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert owner["queue"]["predecessor_run_ids"] == [
        TARGET_RUN_ID,
        SECOND_PREDECESSOR_RUN_ID,
    ]
    assert owner["queue"]["predecessor_states"] == [
        {"run_id": TARGET_RUN_ID, "status": "running"},
        {"run_id": SECOND_PREDECESSOR_RUN_ID, "status": "completed"},
    ]
    assert owner["queue"]["inbound_material"] == [
        {
            "schema_version": subagent.QUEUED_OWNER_MATERIAL_SCHEMA,
            "followup_id": result.followup_id,
            "target_run_id": TARGET_RUN_ID,
            "message_path": result.message_path,
            "message_sha256": hashlib.sha256(message.encode()).hexdigest(),
            "evidence_path": result.evidence_path,
            "accepted_at": receipt["accepted_at"],
        }
    ]
    assert owner["status"] == "queued"
    assert owner["completion_delivery"]["status"] == "pending"
    assert target["status"] == "running"
    assert target["completion_delivery"]["status"] == "suppressed"


def test_queued_synthesis_owner_attachment_is_idempotent_and_directly_addressable(
    tmp_path: Path, caller_provenance: dict
) -> None:
    _, owner_path = _write_queued_synthesis_owner(tmp_path)
    kwargs = {
        "run_id": QUEUED_OWNER_RUN_ID,
        "message": "Reconcile the active worktree before consuming upcoming milestones.",
        "project_dir": tmp_path,
        "workspace_root": None,
        "idempotency_key": "queued-owner-material-1",
    }

    first = subagent.follow_up_managed_subagent(**kwargs)
    second = subagent.follow_up_managed_subagent(**kwargs)

    assert first.followup_id == second.followup_id
    assert second.idempotent_replay is True
    owner = json.loads(owner_path.read_text())
    prompt = Path(owner["prompt_path"]).read_text()
    assert prompt.count("Reconcile the active worktree") == 1
    assert len(owner["queue"]["inbound_material"]) == 1


def test_running_synthesis_owner_attachment_preserves_material_without_launch(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    target_path, owner_path = _write_queued_synthesis_owner(tmp_path)
    target = json.loads(target_path.read_text())
    target["status"] = "completed"
    target_path.write_text(json.dumps(target))
    owner = json.loads(owner_path.read_text())
    owner["status"] = "running"
    owner["queue"]["state"] = "running"
    owner["queue"]["predecessor_states"][0]["status"] = "completed"
    owner_path.write_text(json.dumps(owner))
    monkeypatch.setattr(
        subagent.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("running owner inbox launched a worker"),
    )

    result = subagent.follow_up_managed_subagent(
        run_id=TARGET_RUN_ID,
        message="Preserve the exact upcoming-milestone revision for synthesis.",
        project_dir=tmp_path,
        workspace_root=None,
        idempotency_key="running-owner-material-1",
    )

    assert result.route == "running_synthesis_owner_inbox"
    assert result.delivery_owner_run_id == QUEUED_OWNER_RUN_ID
    assert result.continuation_run_id is None
    receipt = json.loads(Path(result.evidence_path).read_text())
    owner = json.loads(owner_path.read_text())
    assert receipt["parent_status_at_acceptance"] == "running"
    assert receipt["launch_visibility"] == (
        "durable_owner_inbox_requires_process_observation"
    )
    assert receipt["state_history"][-1]["evidence"] == (
        "material_bound_to_existing_running_synthesis_owner_inbox"
    )
    assert len(owner["queue"]["inbound_material"]) == 1
    assert owner["status"] == "running"
    assert owner["completion_delivery"]["status"] == "pending"


def test_queued_synthesis_owner_attachment_rejects_conflicting_custody(
    tmp_path: Path, caller_provenance: dict
) -> None:
    _, owner_path = _write_queued_synthesis_owner(tmp_path)
    owner = json.loads(owner_path.read_text())
    owner["aggregation"]["key"] = "different-aggregation"
    owner_path.write_text(json.dumps(owner))

    with pytest.raises(subagent.SubagentFollowupError, match="aggregation custody"):
        subagent.follow_up_managed_subagent(
            run_id=TARGET_RUN_ID,
            message="Do not bypass ownership.",
            project_dir=tmp_path,
            workspace_root=None,
        )


def test_continuation_worker_resumes_exact_parent_session_and_records_acceptance(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    _write_run(tmp_path)
    monkeypatch.setattr(subagent.subprocess, "Popen", lambda *a, **k: _Supervisor())
    result = subagent.follow_up_managed_subagent(
        run_id=TARGET_RUN_ID,
        message="Use both summaries.",
        project_dir=tmp_path,
        workspace_root=None,
    )
    captured: dict[str, object] = {}

    class _Codex:
        pid = 9876

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    def fake_codex(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["env"] = kwargs["env"]
        return _Codex()

    monkeypatch.setattr(subagent.subprocess, "Popen", fake_codex)
    child_path = Path(result.continuation_manifest_path)
    assert subagent._run_codex_manifest(child_path) == 0

    child = json.loads(child_path.read_text())
    argv = captured["argv"]
    assert argv[:3] == ["codex", "exec", "resume"]
    assert SESSION_ID in argv
    assert child["session_dispatch"] == {
        "status": "accepted",
        "mode": "resume",
        "session_id": SESSION_ID,
        "accepted_at": child["worker_started_at"],
        "evidence": "codex_resume_process_started",
    }
    assert child["model_session"]["session_id"] == SESSION_ID
    inherited = json.loads(captured["env"][DELEGATION_CONTEXT_ENV])
    assert inherited["source_record_id"] == "msg_newfollowupsrc"


def test_live_followup_queues_exact_parent_interrupt_and_retry_is_idempotent(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    target_path = _write_run(tmp_path, status="running", pid=111)
    monkeypatch.setattr(
        subagent,
        "_pid_matches_manifest",
        lambda pid, path: pid == 111 and path == target_path,
    )
    calls = 0

    def fake_popen(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _Supervisor()

    monkeypatch.setattr(subagent.subprocess, "Popen", fake_popen)
    kwargs = {
        "run_id": TARGET_RUN_ID,
        "message": "Interrupt the current turn and continue in this session.",
        "project_dir": tmp_path,
        "workspace_root": None,
        "idempotency_key": "request-42",
    }
    first = subagent.follow_up_managed_subagent(**kwargs)
    second = subagent.follow_up_managed_subagent(**kwargs)

    assert calls == 1
    assert first.continuation_run_id == second.continuation_run_id
    assert second.idempotent_replay is True
    record = json.loads(Path(first.evidence_path).read_text())
    assert record["parent_status_at_acceptance"] == "running"
    assert record["state_history"][-1]["evidence"] == (
        "continuation_queued_to_interrupt_active_parent"
    )
    child = json.loads(Path(first.continuation_manifest_path).read_text())
    assert child["continuation_wait"]["status"] == "pending_parent_terminal"
    assert child["continuation_wait"]["interrupt_parent_on_session_ready"] is True
    assert child["parent_run_id"] == TARGET_RUN_ID


def test_continuation_interrupts_only_exact_active_supervisor_before_resume(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    target_path = _write_run(tmp_path, status="running", pid=111)
    monkeypatch.setattr(
        subagent,
        "_pid_matches_manifest",
        lambda pid, path: pid == 111 and path == target_path,
    )
    monkeypatch.setattr(subagent.subprocess, "Popen", lambda *a, **k: _Supervisor())
    result = subagent.follow_up_managed_subagent(
        run_id=TARGET_RUN_ID,
        message="Use this message now.",
        project_dir=tmp_path,
        workspace_root=None,
    )
    signals: list[tuple[int, int]] = []

    def fake_kill(pid: int, signum: int) -> None:
        signals.append((pid, signum))
        parent = json.loads(target_path.read_text())
        parent["status"] = "interrupted"
        target_path.write_text(json.dumps(parent))

    monkeypatch.setattr(subagent.os, "kill", fake_kill)
    monkeypatch.setattr(subagent.time, "sleep", lambda _seconds: None)
    child_path = Path(result.continuation_manifest_path)
    child = json.loads(child_path.read_text())

    resolved, session_id = subagent._await_continuation_parent(child_path, child)

    assert signals == [(111, subagent.signal.SIGINT)]
    assert session_id == SESSION_ID
    assert resolved["continuation_wait"]["status"] == "parent_terminal"
    parent = json.loads(target_path.read_text())
    assert parent["followup_interrupt"]["evidence"] == (
        "exact_manifest_supervisor_identity_verified"
    )


def test_followup_rejects_unknown_malformed_or_cross_conversation_targets(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    with pytest.raises(subagent.SubagentFollowupError, match="malformed"):
        subagent.follow_up_managed_subagent(
            run_id="../../manifest.json",
            message="unsafe",
            project_dir=tmp_path,
            workspace_root=None,
        )
    with pytest.raises(subagent.SubagentFollowupError, match="unknown"):
        subagent.follow_up_managed_subagent(
            run_id=TARGET_RUN_ID,
            message="unknown",
            project_dir=tmp_path,
            workspace_root=None,
        )

    _write_run(
        tmp_path,
        provenance=_provenance(
            source="msg_othersource", message="3003", conversation="rconv_otherconversation"
        ),
    )
    with pytest.raises(subagent.SubagentFollowupError, match="conversation"):
        subagent.follow_up_managed_subagent(
            run_id=TARGET_RUN_ID,
            message="wrong owner",
            project_dir=tmp_path,
            workspace_root=None,
        )

    monkeypatch.setenv(DELEGATION_CONTEXT_ENV, "{malformed")
    with pytest.raises(Exception, match="malformed or ambiguous provenance"):
        subagent.follow_up_managed_subagent(
            run_id=TARGET_RUN_ID,
            message="bad provenance",
            project_dir=tmp_path,
            workspace_root=None,
        )


def test_followup_revalidates_exact_source_after_discord_match(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    _write_run(tmp_path)
    monkeypatch.setattr(
        subagent.subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not launch")),
    )

    with pytest.raises(subagent.SubagentFollowupError, match="source custody changed"):
        subagent.follow_up_managed_subagent(
            run_id=TARGET_RUN_ID,
            message="do not attach after a target swap",
            project_dir=tmp_path,
            workspace_root=None,
            expected_target_source_record_id="msg_different_source",
            expected_target_discord_message_id="1001",
        )


def test_followup_rejects_ambiguous_model_session_ownership(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    _write_run(tmp_path)
    _write_run(
        tmp_path,
        run_id="subagent-20260713-203300-aaaaaaaa",
        provenance=caller_provenance,
    )
    monkeypatch.setattr(
        subagent.subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not launch")),
    )

    with pytest.raises(subagent.SubagentFollowupError, match="ambiguous"):
        subagent.follow_up_managed_subagent(
            run_id=TARGET_RUN_ID,
            message="do not branch an ambiguous session",
            project_dir=tmp_path,
            workspace_root=None,
        )


def test_active_followup_without_session_evidence_falls_back_before_interrupt(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    target_path = _write_run(tmp_path, status="running", session_id=None, pid=111)
    monkeypatch.setattr(
        subagent,
        "_pid_matches_manifest",
        lambda pid, path: pid == 111 and path == target_path,
    )
    monkeypatch.setattr(
        subagent.subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not launch")),
    )
    monkeypatch.setattr(
        subagent.os,
        "kill",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not interrupt")),
    )

    with pytest.raises(subagent.SubagentFollowupError, match="active target has no"):
        subagent.follow_up_managed_subagent(
            run_id=TARGET_RUN_ID,
            message="Cannot safely continue yet.",
            project_dir=tmp_path,
            workspace_root=None,
        )


def test_concurrent_duplicate_followups_create_one_continuation(
    tmp_path: Path, monkeypatch, caller_provenance: dict
) -> None:
    _write_run(tmp_path)
    calls = 0
    calls_lock = threading.Lock()

    def fake_popen(*args, **kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        return _Supervisor()

    monkeypatch.setattr(subagent.subprocess, "Popen", fake_popen)
    kwargs = {
        "run_id": TARGET_RUN_ID,
        "message": "Only one continuation may own this Discord reply.",
        "project_dir": tmp_path,
        "workspace_root": None,
        "idempotency_key": "discord:message:2002",
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: subagent.follow_up_managed_subagent(**kwargs), range(2)))

    assert calls == 1
    assert {result.continuation_run_id for result in results} == {
        results[0].continuation_run_id
    }
    assert sum(result.idempotent_replay for result in results) == 1


def test_followup_requires_inherited_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    _write_run(tmp_path)
    monkeypatch.delenv(DELEGATION_CONTEXT_ENV, raising=False)
    with pytest.raises(subagent.SubagentFollowupError, match="requires inherited"):
        subagent.follow_up_managed_subagent(
            run_id=TARGET_RUN_ID,
            message="no caller custody",
            project_dir=tmp_path,
            workspace_root=None,
        )


def test_followup_cli_help_describes_active_and_terminal_semantics() -> None:
    help_text = " ".join(subagent._build_local_seam_parser().format_help().split())
    assert "active parents are safely interrupted" in help_text
    assert "terminal parents resume" in help_text
