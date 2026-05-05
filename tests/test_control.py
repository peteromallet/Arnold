from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan.control import ControlProcessor, ControlTarget, ControlTargetResolver, process_pending_control_messages
from megaplan.progress import ProgressContext
from megaplan.schemas import ControlMessage
from megaplan.store import ControlMessageInput, FileStore, SprintItemInput
from megaplan.types import CliError


def _plan_dir(project_root: Path, name: str, state: dict) -> Path:
    plan_dir = project_root / ".megaplan" / "plans" / name
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return plan_dir


def test_control_resolver_validates_run_sprint_target(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    sprint = store.create_sprint(epic_id=epic.id, sprint_number=2, name="Two", goal="Ship")
    plan_dir = _plan_dir(
        tmp_path,
        "sprint-two",
        {"current_state": "initialized", "meta": {"epic_id": epic.id, "sprint_id": sprint.id}},
    )
    progress_context = {"backend": "file", "file_root": str(tmp_path / "store"), "epic_id": epic.id}

    target = ControlTargetResolver(store).resolve(
        "run_sprint",
        sprint.id,
        {
            "project_root": str(tmp_path),
            "epic_id": epic.id,
            "plan": "sprint-two",
            "progress_context": progress_context,
        },
    )

    assert target.intent == "run_sprint"
    assert target.project_root == tmp_path.resolve()
    assert target.epic_id == epic.id
    assert target.sprint_id == sprint.id
    assert target.sprint_number == 2
    assert target.plan_dir == plan_dir
    assert target.progress_context == ProgressContext(**progress_context)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({}, "missing_project_root"),
        ({"project_root": "/does/not/exist"}, "invalid_project_root"),
    ],
)
def test_control_resolver_fails_fast_for_bad_project_root(tmp_path: Path, payload: dict, code: str) -> None:
    store = FileStore(tmp_path / "store")

    with pytest.raises(CliError) as exc_info:
        ControlTargetResolver(store).resolve("resume_plan", "demo", payload)

    assert exc_info.value.code == code


def test_control_resolver_rejects_store_only_plan_metadata(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    store.create_plan(sprint_id=None, epic_id=epic.id, name="store-only", idea="Idea")

    with pytest.raises(CliError) as exc_info:
        ControlTargetResolver(store).resolve(
            "resume_plan",
            "store-only",
            {"project_root": str(tmp_path), "epic_id": epic.id},
        )

    assert exc_info.value.code == "missing_filesystem_plan"


def test_control_resolver_rejects_unknown_sprint_and_bad_gate_payload(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    _plan_dir(tmp_path, "demo", {"current_state": "critiqued", "meta": {"epic_id": epic.id}})
    resolver = ControlTargetResolver(store)

    with pytest.raises(CliError) as sprint_error:
        resolver.resolve("run_sprint", "missing", {"project_root": str(tmp_path), "epic_id": epic.id})
    assert sprint_error.value.code == "unknown_sprint"

    with pytest.raises(CliError) as gate_error:
        resolver.resolve("approve_gate", "gate-1", {"project_root": str(tmp_path), "plan": ""})
    assert gate_error.value.code == "invalid_plan"


def test_control_resolver_validates_plan_identity_and_progress_context(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    _plan_dir(tmp_path, "demo", {"current_state": "paused", "meta": {"epic_id": epic.id, "sprint_id": "sprint-1"}})
    resolver = ControlTargetResolver(store)

    target = resolver.resolve(
        "approve_gate",
        "gate-1",
        {"project_root": str(tmp_path), "plan": "demo", "epic_id": epic.id, "sprint_id": "sprint-1"},
    )
    assert target.gate_id == "gate-1"
    assert target.plan == "demo"

    with pytest.raises(CliError) as mismatch:
        resolver.resolve("resume_plan", "demo", {"project_root": str(tmp_path), "epic_id": "other"})
    assert mismatch.value.code == "epic_mismatch"

    with pytest.raises(CliError) as bad_context:
        resolver.resolve(
            "resume_plan",
            "demo",
            {"project_root": str(tmp_path), "progress_context": {"backend": "file"}},
        )
    assert bad_context.value.code == "invalid_progress_context"


def _put_control(
    store: FileStore,
    *,
    epic_id: str,
    intent: str,
    target_id: str,
    payload: dict,
    key: str,
) -> ControlMessage:
    return store.put_control_message(
        ControlMessageInput(
            epic_id=epic_id,
            actor_id="discord-user",
            intent=intent,
            target_id=target_id,
            payload=payload,
            idempotency_key=key,
        )
    )


def test_control_processor_marks_success_failure_and_unsupported_once(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    _plan_dir(tmp_path, "demo", {"current_state": "paused", "meta": {"epic_id": epic.id}})
    calls: list[ControlTarget] = []

    def resume_handler(target: ControlTarget, message: ControlMessage) -> dict:
        assert message.intent == "resume_plan"
        calls.append(target)
        return {"resumed": target.plan}

    success = _put_control(
        store,
        epic_id=epic.id,
        intent="resume_plan",
        target_id="demo",
        payload={"project_root": str(tmp_path), "epic_id": epic.id},
        key="success",
    )
    failure = _put_control(
        store,
        epic_id=epic.id,
        intent="resume_plan",
        target_id="missing",
        payload={"project_root": str(tmp_path), "epic_id": epic.id},
        key="failure",
    )
    unsupported = _put_control(
        store,
        epic_id=epic.id,
        intent="pause_plan",
        target_id="demo",
        payload={"project_root": str(tmp_path), "epic_id": epic.id},
        key="unsupported",
    )

    results = process_pending_control_messages(
        store,
        processor_id="proc-1",
        handlers={"resume_plan": resume_handler},
    )

    assert [result["message_id"] for result in results] == [success.id, failure.id, unsupported.id]
    assert [result["status"] for result in results] == ["success", "failure", "unsupported"]
    assert results[0]["details"] == {"resumed": "demo"}
    assert results[1]["error"]["code"] == "unknown_plan"
    assert results[2]["error"]["code"] == "unsupported_control_intent"
    assert [target.plan for target in calls] == ["demo"]

    assert store.claim_pending_control_messages(processor_id="proc-2") == []
    for message_id in (success.id, failure.id, unsupported.id):
        processed = store._load_model(store._control_message_path(message_id), ControlMessage)
        assert processed is not None
        assert processed.processed_at is not None
        assert processed.processor_id == "proc-1"
        assert processed.result is not None


def test_control_processor_records_unimplemented_and_handler_exceptions(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    _plan_dir(tmp_path, "demo", {"current_state": "paused", "meta": {"epic_id": epic.id}})
    unimplemented = _put_control(
        store,
        epic_id=epic.id,
        intent="approve_gate",
        target_id="gate-1",
        payload={"project_root": str(tmp_path), "plan": "demo", "epic_id": epic.id},
        key="unimplemented",
    )
    handler_error = _put_control(
        store,
        epic_id=epic.id,
        intent="reject_gate",
        target_id="gate-2",
        payload={"project_root": str(tmp_path), "plan": "demo", "epic_id": epic.id},
        key="handler-error",
    )

    def reject_handler(target: ControlTarget, message: ControlMessage) -> None:
        raise RuntimeError(f"boom {target.gate_id} {message.id}")

    results = ControlProcessor(
        store,
        processor_id="proc-1",
        handlers={"approve_gate": None, "reject_gate": reject_handler},
    ).process_pending()

    assert [result["message_id"] for result in results] == [unimplemented.id, handler_error.id]
    assert results[0]["status"] == "unsupported"
    assert results[0]["error"]["code"] == "control_handler_unimplemented"
    assert results[1]["status"] == "failure"
    assert results[1]["error"]["code"] == "control_handler_exception"
    assert "boom gate-2" in results[1]["error"]["message"]


def test_approve_gate_uses_override_user_approval_emits_progress_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.auto import DriverOutcome

    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    _plan_dir(tmp_path, "demo", {"current_state": "critiqued", "meta": {"epic_id": epic.id}})
    override_calls: list[object] = []
    drive_calls: list[dict[str, object]] = []

    def fake_override(root: Path, args: object) -> dict:
        assert root == tmp_path.resolve()
        override_calls.append(args)
        return {"success": True, "summary": "approved", "state": "gated"}

    def fake_drive(plan: str, **kwargs: object) -> DriverOutcome:
        drive_calls.append({"plan": plan, **kwargs})
        return DriverOutcome(status="done", plan=plan, final_state="done", iterations=1)

    monkeypatch.setattr("megaplan.control.handle_override", fake_override)
    monkeypatch.setattr("megaplan.control.drive_auto", fake_drive)
    _put_control(
        store,
        epic_id=epic.id,
        intent="approve_gate",
        target_id="gate-1",
        payload={
            "project_root": str(tmp_path),
            "plan": "demo",
            "epic_id": epic.id,
            "auto_continue": True,
            "progress_context": {"backend": "file", "file_root": str(tmp_path / "store"), "epic_id": epic.id},
        },
        key="approve-gate",
    )

    result = process_pending_control_messages(store, processor_id="proc-1")[0]

    assert result["status"] == "success"
    assert len(override_calls) == 1
    override_args = override_calls[0]
    assert getattr(override_args, "override_action") == "force-proceed"
    assert getattr(override_args, "user_approved") is True
    assert drive_calls[0]["plan"] == "demo"
    assert isinstance(drive_calls[0]["progress_env"], dict)
    events = store.list_progress_events(epic_id=epic.id, plan_id="demo")
    assert len(events) == 1
    assert events[0].kind == "gate_resolved"
    assert events[0].details["gate_id"] == "gate-1"
    assert events[0].details["decision"] == "approved"


def test_reject_gate_attaches_user_note_and_does_not_auto_continue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    _plan_dir(tmp_path, "demo", {"current_state": "critiqued", "meta": {"epic_id": epic.id}})
    override_calls: list[object] = []

    def fake_override(root: Path, args: object) -> dict:
        del root
        override_calls.append(args)
        return {"success": True, "summary": "note added", "state": "critiqued"}

    monkeypatch.setattr("megaplan.control.handle_override", fake_override)
    monkeypatch.setattr(
        "megaplan.control.drive_auto",
        lambda *args, **kwargs: pytest.fail("reject_gate should not auto-continue"),
    )
    _put_control(
        store,
        epic_id=epic.id,
        intent="reject_gate",
        target_id="gate-2",
        payload={"project_root": str(tmp_path), "plan": "demo", "epic_id": epic.id, "note": "needs revision"},
        key="reject-gate",
    )

    result = process_pending_control_messages(store, processor_id="proc-1")[0]

    assert result["status"] == "success"
    assert len(override_calls) == 1
    override_args = override_calls[0]
    assert getattr(override_args, "override_action") == "add-note"
    assert getattr(override_args, "source") == "user"
    assert getattr(override_args, "note") == "needs revision"
    events = store.list_progress_events(epic_id=epic.id, plan_id="demo")
    assert len(events) == 1
    assert events[0].details["decision"] == "rejected"


def test_gate_resolution_is_not_emitted_when_override_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    _plan_dir(tmp_path, "demo", {"current_state": "paused", "meta": {"epic_id": epic.id}})

    def fail_override(root: Path, args: object) -> dict:
        del root, args
        raise CliError("strict_notes_blocked", "no")

    monkeypatch.setattr("megaplan.control.handle_override", fail_override)
    _put_control(
        store,
        epic_id=epic.id,
        intent="approve_gate",
        target_id="gate-3",
        payload={"project_root": str(tmp_path), "plan": "demo", "epic_id": epic.id},
        key="approve-fails",
    )

    result = process_pending_control_messages(store, processor_id="proc-1")[0]

    assert result["status"] == "failure"
    assert result["error"]["code"] == "strict_notes_blocked"
    assert store.list_progress_events(epic_id=epic.id, plan_id="demo") == []


def test_resume_plan_uses_workflow_runner_with_progress_env_and_can_continue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.auto import DriverOutcome

    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    _plan_dir(
        tmp_path,
        "demo",
        {
            "current_state": "failed",
            "meta": {"epic_id": epic.id},
            "resume_cursor": {"phase": "execute", "batch_index": 1},
        },
    )
    runner_seen: dict[str, object] = {}
    drive_seen: dict[str, object] = {}

    def fake_resume(root: Path, plan: str, *, store: object, runner: object) -> dict:
        del store
        code, stdout, stderr = runner(["execute", "--plan", plan], cwd=root)
        runner_seen.update({"code": code, "stdout": stdout, "stderr": stderr})
        return {"success": True, "command": ["execute", "--plan", plan]}

    class FakeProc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_subprocess_run(cmd: list[str], **kwargs: object) -> FakeProc:
        runner_seen["cmd"] = cmd
        runner_seen["cwd"] = kwargs.get("cwd")
        runner_seen["env"] = kwargs.get("env")
        return FakeProc()

    def fake_drive(plan: str, **kwargs: object) -> DriverOutcome:
        drive_seen.update({"plan": plan, **kwargs})
        return DriverOutcome(status="paused", plan=plan, final_state="paused", iterations=2, reason="waiting")

    monkeypatch.setattr("megaplan.control.resume_plan", fake_resume)
    monkeypatch.setattr("megaplan.control.subprocess.run", fake_subprocess_run)
    monkeypatch.setattr("megaplan.control.drive_auto", fake_drive)
    _put_control(
        store,
        epic_id=epic.id,
        intent="resume_plan",
        target_id="demo",
        payload={
            "project_root": str(tmp_path),
            "epic_id": epic.id,
            "auto_continue": True,
            "progress_context": {"backend": "file", "file_root": str(tmp_path / "store"), "epic_id": epic.id},
        },
        key="resume-plan",
    )

    result = process_pending_control_messages(store, processor_id="proc-1")[0]

    assert result["status"] == "success"
    assert runner_seen["cmd"][-3:] == ["execute", "--plan", "demo"]
    env = runner_seen["env"]
    assert isinstance(env, dict)
    assert env["MEGAPLAN_PROGRESS_PLAN_ID"] == "demo"
    assert drive_seen["plan"] == "demo"
    assert isinstance(drive_seen["progress_env"], dict)


def test_run_sprint_control_initializes_filesystem_plan_and_drives_auto(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.auto import DriverOutcome

    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    sprint = store.create_sprint(epic_id=epic.id, sprint_number=2, name="Two", goal="Ship the thing")
    store.replace_sprint_items(
        sprint.id,
        [
            SprintItemInput(content="Build first", position=1),
            SprintItemInput(content="Verify second", position=2),
        ],
    )
    progress_context = ProgressContext(
        backend="file",
        file_root=str(tmp_path / "store"),
        epic_id=epic.id,
        run_id="run-1",
    )
    captured: dict[str, object] = {}

    def fake_drive(plan: str, **kwargs: object) -> DriverOutcome:
        captured["plan"] = plan
        captured["cwd"] = kwargs.get("cwd")
        captured["progress_env"] = kwargs.get("progress_env")
        return DriverOutcome(status="done", plan=plan, final_state="done", iterations=3, reason="complete")

    monkeypatch.setattr("megaplan.control.drive_auto", fake_drive)
    message = _put_control(
        store,
        epic_id=epic.id,
        intent="run_sprint",
        target_id=sprint.id,
        payload={
            "project_root": str(tmp_path),
            "epic_id": epic.id,
            "plan": "sprint-two",
            "progress_context": {
                "backend": progress_context.backend,
                "file_root": progress_context.file_root,
                "epic_id": progress_context.epic_id,
                "run_id": progress_context.run_id,
            },
        },
        key="run-sprint",
    )

    results = process_pending_control_messages(store, processor_id="proc-1")

    assert results[0]["message_id"] == message.id
    assert results[0]["status"] == "success"
    details = results[0]["details"]
    assert details["created_plan"] is True
    assert details["plan"] == "sprint-two"
    assert details["auto_outcome"]["status"] == "done"
    plan_dir = tmp_path / ".megaplan" / "plans" / "sprint-two"
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["meta"]["epic_id"] == epic.id
    assert state["meta"]["sprint_id"] == sprint.id
    assert "Build first" in state["idea"]
    assert captured["plan"] == "sprint-two"
    assert captured["cwd"] == tmp_path.resolve()
    progress_env = captured["progress_env"]
    assert isinstance(progress_env, dict)
    assert progress_env["MEGAPLAN_PROGRESS_PLAN_ID"] == "sprint-two"
    assert progress_env["MEGAPLAN_PROGRESS_SPRINT_ID"] == sprint.id


def test_run_sprint_control_reuses_existing_filesystem_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from megaplan.auto import DriverOutcome

    store = FileStore(tmp_path / "store")
    epic = store.create_epic(title="Epic", goal="Goal", body="Body")
    sprint = store.create_sprint(epic_id=epic.id, sprint_number=2, name="Two", goal="Ship")
    _plan_dir(
        tmp_path,
        "existing",
        {"current_state": "initialized", "meta": {"epic_id": epic.id, "sprint_id": sprint.id}},
    )
    init_called = False

    def fail_init(*args: object, **kwargs: object) -> None:
        nonlocal init_called
        init_called = True
        raise AssertionError("handle_init should not be called")

    def fake_drive(plan: str, **kwargs: object) -> DriverOutcome:
        del kwargs
        return DriverOutcome(status="done", plan=plan, final_state="done", iterations=1)

    monkeypatch.setattr("megaplan.control.handle_init", fail_init)
    monkeypatch.setattr("megaplan.control.drive_auto", fake_drive)
    _put_control(
        store,
        epic_id=epic.id,
        intent="run_sprint",
        target_id=sprint.id,
        payload={"project_root": str(tmp_path), "epic_id": epic.id, "plan": "existing"},
        key="reuse",
    )

    results = process_pending_control_messages(store, processor_id="proc-1")

    assert results[0]["status"] == "success"
    assert results[0]["details"]["created_plan"] is False
    assert init_called is False
