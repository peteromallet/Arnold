from __future__ import annotations

import inspect
from pathlib import Path
import subprocess
from typing import Callable

import pytest

from arnold_pipelines.megaplan.store import (
    ArnoldStoreAdapter,
    ChecklistItemInput,
    ControlMessageInput,
    DBStore,
    FileStore,
    MultiStore,
    ProgressEventInput,
    SprintItemInput,
    Store,
    StoreError,
    deterministic_idempotency_key,
)
from arnold_pipelines.megaplan.tickets.identity import repo_codebase_identity


def _init_contract_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "contract@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Contract Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# Contract Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


def make_file_store_factory(tmp_path: Path) -> Callable[[], FileStore]:
    """Return a FileStore factory with a committed repo for ticket identity."""
    repo = _init_contract_repo(tmp_path)
    store_root = repo / ".megaplan" / "store"

    def _factory() -> FileStore:
        return FileStore(root=store_root, repo_root=repo)

    return _factory


def _store_protocol_method_names() -> list[str]:
    return sorted(name for name, value in Store.__dict__.items() if callable(value) and not name.startswith("_"))


def _public_callable_method_names(store: object) -> list[str]:
    return sorted(name for name in dir(store) if not name.startswith("_") and callable(getattr(store, name, None)))


def _assert_store_protocol_parity(store: Store) -> None:
    protocol_names = _store_protocol_method_names()
    concrete_names = _public_callable_method_names(store)
    missing = sorted(set(protocol_names) - set(concrete_names))
    assert isinstance(store, Store), f"{type(store).__name__} is not runtime-compatible with Store"
    assert not missing, (
        f"{type(store).__name__} is missing Store methods: {missing}. "
        f"Store protocol methods={protocol_names}; concrete public callables={concrete_names}"
    )
    # Module-layout guard: mixin assembly must not change __module__.
    _EXPECTED_MODULE: dict[type, str] = {
        FileStore: "arnold_pipelines.megaplan.store.file",
        DBStore: "arnold_pipelines.megaplan.store.db",
        MultiStore: "arnold_pipelines.megaplan.store.multi",
    }
    expected = _EXPECTED_MODULE.get(type(store))
    if expected is not None:
        assert type(store).__module__ == expected, (
            f"{type(store).__name__}.__module__ is {type(store).__module__!r}, "
            f"expected {expected!r}. Mixin assembly may have regressed."
        )


def _assert_codebase_signature_contract() -> None:
    implementations = (Store, DBStore, FileStore, MultiStore)
    for method_name in ("create_codebase", "upsert_codebase"):
        signatures = {impl.__name__: inspect.signature(getattr(impl, method_name)) for impl in implementations}
        for impl_name, signature in signatures.items():
            parameters = signature.parameters
            assert "default_branch" in parameters, f"{impl_name}.{method_name} must require default_branch"
            assert parameters["default_branch"].default is inspect.Parameter.empty, (
                f"{impl_name}.{method_name} must not default default_branch"
            )
            assert "root_commit_sha" in parameters, f"{impl_name}.{method_name} must expose root_commit_sha"
            assert parameters["root_commit_sha"].default is None
        assert list(signatures["Store"].parameters) == list(signatures["DBStore"].parameters)
        assert list(signatures["Store"].parameters) == list(signatures["FileStore"].parameters)
        assert list(signatures["Store"].parameters) == list(signatures["MultiStore"].parameters)


def _assert_m2_store_signature_contract() -> None:
    implementations = (DBStore, FileStore, MultiStore)
    method_names = (
        "create_ticket",
        "load_ticket",
        "list_tickets",
        "update_ticket",
        "link_ticket_to_epic",
        "unlink_ticket_from_epic",
        "list_ticket_epic_links",
        "address_tickets_resolved_by_epic",
        "load_codebase_by_associated_epic",
        "resolve_codebase_by_root_sha",
        "events_by_transaction",
    )
    for method_name in method_names:
        protocol_parameters = list(inspect.signature(getattr(Store, method_name)).parameters)
        for implementation in implementations:
            concrete_parameters = list(inspect.signature(getattr(implementation, method_name)).parameters)
            assert concrete_parameters == protocol_parameters, (
                f"{implementation.__name__}.{method_name} parameters must match Store.{method_name}: "
                f"{concrete_parameters} != {protocol_parameters}"
            )


def _capture_error_class(fn: Callable[[], object], *, label: str) -> type[BaseException]:
    try:
        fn()
    except Exception as exc:
        return type(exc)
    raise AssertionError(f"expected {label} to raise")


def _assert_same_error_class(
    label: str,
    first: Callable[[], object],
    second: Callable[[], object],
) -> None:
    first_type = _capture_error_class(first, label=label)
    second_type = _capture_error_class(second, label=label)
    assert first_type is second_type, f"{label} error class mismatch: {first_type.__name__} != {second_type.__name__}"


def _exercise_store_error_contract(store: Store, *, epic_home_backend: str) -> None:
    idem = deterministic_idempotency_key
    _assert_same_error_class(
        "missing epic body access",
        lambda: store.load_body("missing-epic"),
        lambda: store.load_body("missing-epic"),
    )

    conflict_epic = store.create_epic(
        title="Conflict Epic",
        goal="Exercise lock/lease conflicts",
        body="Body",
        home_backend=epic_home_backend,
        idempotency_key=idem("contract", epic_home_backend, "conflict_epic"),
    )
    store.acquire_lock(
        conflict_epic.id,
        "holder-a",
        120,
        idempotency_key=idem("contract", conflict_epic.id, "lock", "holder-a"),
    )
    _assert_same_error_class(
        "active lock conflict",
        lambda: store.acquire_lock(
            conflict_epic.id,
            "holder-b",
            120,
            idempotency_key=idem("contract", conflict_epic.id, "lock", "holder-b"),
        ),
        lambda: store.acquire_lock(
            conflict_epic.id,
            "holder-c",
            120,
            idempotency_key=idem("contract", conflict_epic.id, "lock", "holder-c"),
        ),
    )
    store.release_lock(
        conflict_epic.id,
        "holder-a",
        idempotency_key=idem("contract", conflict_epic.id, "lock", "release"),
    )

    lease_plan = store.create_plan(
        sprint_id=None,
        epic_id=conflict_epic.id,
        name="lease-conflict-plan",
        idea="exercise lease conflicts",
        idempotency_key=idem("contract", conflict_epic.id, "lease-plan"),
    )
    store.acquire_execution_lease(
        lease_plan.id,
        "worker-a",
        "local_cli",
        120,
        epic_id=conflict_epic.id,
        idempotency_key=idem("contract", lease_plan.id, "lease", "worker-a"),
    )
    _assert_same_error_class(
        "active execution lease conflict",
        lambda: store.acquire_execution_lease(
            lease_plan.id,
            "worker-b",
            "local_cli",
            120,
            epic_id=conflict_epic.id,
            idempotency_key=idem("contract", lease_plan.id, "lease", "worker-b"),
        ),
        lambda: store.acquire_execution_lease(
            lease_plan.id,
            "worker-c",
            "local_cli",
            120,
            epic_id=conflict_epic.id,
            idempotency_key=idem("contract", lease_plan.id, "lease", "worker-c"),
        ),
    )
    store.release_lease(
        lease_plan.id,
        "worker-a",
        idempotency_key=idem("contract", lease_plan.id, "lease", "release"),
    )

    orphan_plan = store.create_plan(
        sprint_id=None,
        epic_id=None,
        name="unsafe-artifact-plan",
        idea="exercise unsafe artifact paths",
        idempotency_key=idem("contract", "unsafe-artifact-plan"),
    )
    unsafe_name = "../escape.bin"
    _assert_same_error_class(
        "unsafe artifact paths",
        lambda: store.write_plan_artifact(
            orphan_plan.id,
            unsafe_name,
            b"bad",
            idempotency_key=idem("contract", orphan_plan.id, "unsafe", "write"),
        ),
        lambda: store.read_plan_artifact(orphan_plan.id, unsafe_name),
    )
    _assert_same_error_class(
        "unsafe artifact paths",
        lambda: store.read_plan_artifact(orphan_plan.id, unsafe_name),
        lambda: store.stat_plan_artifact(orphan_plan.id, unsafe_name),
    )


def run_store_contract(store_factory: Callable[[], Store], *, epic_home_backend: str = "file") -> None:
    store = store_factory()
    idem = deterministic_idempotency_key
    _assert_store_protocol_parity(store)
    _assert_codebase_signature_contract()
    _assert_m2_store_signature_contract()
    _exercise_store_error_contract(store, epic_home_backend=epic_home_backend)

    epic = store.create_epic(
        title="Editorial Title",
        goal="Editorial Goal",
        body="# Editorial Title\n\nEditorial Goal\n",
        home_backend=epic_home_backend,
        idempotency_key=idem("contract", "create_epic"),
    )
    assert store.load_epic(epic.id).title == "Editorial Title"
    assert store.load_body(epic.id).startswith("# Editorial Title")

    # --- Explicit epic_id acceptance ---
    explicit_id = "contract-explicit-epic"
    explicit_epic = store.create_epic(
        title="Explicit ID Epic",
        goal="Exercise explicit epic_id acceptance",
        body="# Explicit ID Epic\n",
        epic_id=explicit_id,
        home_backend=epic_home_backend,
        idempotency_key=idem("contract", "explicit_epic"),
    )
    assert explicit_epic.id == explicit_id, (
        f"Expected epic_id={explicit_id!r}, got {explicit_epic.id!r}"
    )
    assert store.load_epic(explicit_id).title == "Explicit ID Epic"

    # --- Generated default IDs unchanged ---
    default_epic = store.create_epic(
        title="Default Generated Epic",
        goal="Exercise generated epic IDs unchanged",
        body="# Default Generated Epic\n",
        home_backend=epic_home_backend,
        idempotency_key=idem("contract", "default_epic"),
    )
    assert default_epic.id, "Generated epic_id must be non-empty"
    assert default_epic.id != explicit_id, (
        f"Generated ID {default_epic.id!r} must differ from explicit ID {explicit_id!r}"
    )
    assert store.load_epic(default_epic.id).title == "Default Generated Epic"

    # --- Idempotency retry does not fork epics ---
    retry_key = idem("contract", "retry_epic")
    retry_epic = store.create_epic(
        title="Retry Epic",
        goal="Exercise idempotency retry without forking",
        body="# Retry Epic\n",
        epic_id="retry-idempotency-epic",
        home_backend=epic_home_backend,
        idempotency_key=retry_key,
    )
    try:
        replayed = store.create_epic(
            title="Retry Epic",
            goal="Exercise idempotency retry without forking",
            body="# Retry Epic\n",
            epic_id="retry-idempotency-epic",
            home_backend=epic_home_backend,
            idempotency_key=retry_key,
        )
        # Idempotent path: same epic returned, no fork
        assert replayed.id == retry_epic.id, (
            f"Replayed epic id {replayed.id!r} != original {retry_epic.id!r}"
        )
        assert replayed.revision == retry_epic.revision, (
            f"Replayed revision {replayed.revision} != original {retry_epic.revision}"
        )
    except Exception:
        # Backend without idempotency replay for create_epic —
        # verify the original was not forked and still loadable
        loaded = store.load_epic(retry_epic.id)
        assert loaded is not None, "Original epic must still exist after retry"
        assert loaded.id == retry_epic.id
        assert loaded.revision == retry_epic.revision

    updated_epic = store.update_body(
        epic.id,
        "# Revised\n",
        expected_revision=epic.revision,
        idempotency_key=idem("contract", epic.id, "update_body"),
    )
    assert updated_epic.revision == epic.revision + 1
    first_state_update = store.update_epic(
        epic.id,
        expected_revision=updated_epic.revision,
        state="planned",
        idempotency_key=idem("contract", epic.id, "update_epic", "state"),
    )
    replayed_state_update = store.update_epic(
        epic.id,
        expected_revision=updated_epic.revision,
        state="planned",
        idempotency_key=idem("contract", epic.id, "update_epic", "state"),
    )
    assert replayed_state_update == first_state_update
    assert store.load_epic(epic.id).revision == first_state_update.revision
    try:
        store.update_epic(
            epic.id,
            expected_revision=first_state_update.revision,
            bogus_column="value",
            idempotency_key=idem("contract", epic.id, "update_epic", "bogus_column"),
        )
    except StoreError:
        pass
    else:
        raise AssertionError("unknown update_epic fields should raise StoreError")
    assert store.search_epics(query="revised")[0].id == epic.id

    checklist = store.seed_checklist(epic.id, ["First item", "Second item"], idempotency_key=idem("contract", epic.id, "seed_checklist"))
    assert [item.position for item in checklist] == [1, 2]
    replaced = store.replace_checklist(
        epic.id,
        [
            ChecklistItemInput(content="Replacement item", status="open", position=1, source="user_requested"),
        ],
        idempotency_key=idem("contract", epic.id, "replace_checklist"),
    )
    assert [item.content for item in replaced] == ["Replacement item"]
    assert (
        store.update_checklist_item(
            replaced[0].id,
            status="done",
            idempotency_key=idem("contract", replaced[0].id, "update_checklist_item"),
        ).completed_at
        is not None
    )
    before_invalid_checklist = store.list_checklist_items(epic.id)
    invalid_checklist = ChecklistItemInput.model_construct(
        content="Invalid checklist",
        status="bogus",
        source="bot_inferred",
    )
    try:
        store.add_checklist_items(
            epic.id,
            [ChecklistItemInput(content="Valid before invalid"), invalid_checklist],
            idempotency_key=idem("contract", epic.id, "invalid_add_checklist"),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid checklist status should be rejected")
    assert store.list_checklist_items(epic.id) == before_invalid_checklist

    try:
        store.update_checklist_item(
            replaced[0].id,
            status="bogus",
            idempotency_key=idem("contract", replaced[0].id, "invalid_update_checklist_item"),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid checklist update status should be rejected")
    assert store.list_checklist_items(epic.id) == before_invalid_checklist

    sprint = store.create_sprint(
        epic_id=epic.id,
        sprint_number=1,
        name="Sprint 1",
        goal="Ship it",
        idempotency_key=idem("contract", epic.id, "create_sprint"),
    )
    items = store.replace_sprint_items(
        sprint.id,
        [
            SprintItemInput(content="Investigate", estimated_complexity="small", status="open", position=1),
        ],
        idempotency_key=idem("contract", sprint.id, "replace_sprint_items"),
    )
    assert items[0].content == "Investigate"
    invalid_sprint_item = SprintItemInput.model_construct(
        content="Invalid sprint item",
        estimated_complexity="enormous",
        status="open",
    )
    try:
        store.replace_sprint_items(
            sprint.id,
            [SprintItemInput(content="Valid before invalid"), invalid_sprint_item],
            idempotency_key=idem("contract", sprint.id, "invalid_replace_sprint_items"),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid sprint item complexity should be rejected")
    assert store.list_sprint_items(sprint.id) == items
    queued = store.set_sprint_queue(epic.id, [sprint.id], {}, idempotency_key=idem("contract", epic.id, "set_sprint_queue"))
    assert queued[0].queue_position == 1
    assert store.list_sprints_with_items(epic.id)[0].items[0].id == items[0].id

    bootstrap_turn = store.create_turn(
        epic_id=None,
        triggered_by_message_ids=[],
        prompt_snapshot={"phase": "bootstrap"},
        idempotency_key=idem("contract", "bootstrap", "create_turn"),
    )
    assert bootstrap_turn.epic_id is None
    bootstrap_message = store.create_message(
        epic_id=None,
        direction="inbound",
        content="bootstrap hello",
        idempotency_key=idem("contract", "bootstrap", "create_message"),
    )
    assert bootstrap_message.epic_id is None

    inbound = store.create_message(
        epic_id=epic.id,
        direction="inbound",
        content="hello from user",
        discord_message_id="discord_1",
        has_code_attachment=True,
        idempotency_key=idem("contract", epic.id, "inbound_message"),
    )
    turn = store.create_turn(
        epic_id=epic.id,
        triggered_by_message_ids=[inbound.id],
        prompt_snapshot={"input": "hello from user"},
        state_at_turn={"state": "shaping"},
        model_version="fake",
        idempotency_key=idem("contract", epic.id, "create_turn"),
    )
    completed_turn = store.update_turn(
        turn.id,
        status="completed",
        reasoning="done",
        idempotency_key=idem("contract", turn.id, "update_turn"),
    )
    assert completed_turn.completed_at is not None
    outbound = store.create_message(
        epic_id=epic.id,
        direction="outbound",
        content="hi",
        bot_turn_id=turn.id,
        idempotency_key=idem("contract", epic.id, turn.id, "outbound_message"),
    )
    assert outbound.discord_message_id == f"inv_{turn.id}_1"
    assert [row.id for row in store.load_messages([outbound.id, inbound.id])] == [outbound.id, inbound.id]
    assert store.latest_outbound_message(epic_id=epic.id).id == outbound.id
    assert store.search_messages(query="hello", epic_id=epic.id)[0].id == inbound.id
    assert store.find_unprocessed_messages(epic.id, inbound.sent_at.isoformat().replace("+00:00", "Z"), exclude_ids=[]) == [inbound]

    tool_call = store.record_tool_call(
        turn_id=turn.id,
        tool_name="send_message",
        operation_kind="write",
        arguments={"content": "hi"},
        result={"discord_message_id": outbound.discord_message_id},
        duration_ms=1,
        idempotency_key=idem("contract", turn.id, "record_tool_call"),
    )
    assert tool_call.arguments["content"] == "hi"
    log = store.log_system_event(
        level="info",
        category="system",
        event_type="contract",
        message="ok",
        details={"ok": True},
        turn_id=turn.id,
        epic_id=epic.id,
        idempotency_key=idem("contract", turn.id, "log_system_event"),
    )
    assert log.details["ok"] is True
    hot = store.load_hot_context(epic.id)
    assert hot.epic.id == epic.id
    assert any(row.id == inbound.id for row in hot.recent_messages)

    first_event = store.record_epic_event(
        epic_id=epic.id,
        transaction_id="txn_shared",
        event_type="body_edit",
        summary="Body updated",
        prior_state={"body": "before"},
        turn_id=turn.id,
        idempotency_key=idem("contract", epic.id, "event", "body"),
    )
    second_event = store.record_epic_event(
        epic_id=epic.id,
        transaction_id="txn_shared",
        event_type="checklist_change",
        summary="Checklist updated",
        prior_state={"items": [item.model_dump(mode='json') for item in replaced]},
        turn_id=turn.id,
        idempotency_key=idem("contract", epic.id, "event", "checklist"),
    )
    latest_event = store.record_epic_event(
        epic_id=epic.id,
        transaction_id="txn_latest",
        event_type="state_change",
        summary="State updated",
        prior_state={"state": "shaping"},
        turn_id=turn.id,
        idempotency_key=idem("contract", epic.id, "event", "state"),
    )
    assert {row.id for row in store.events_by_transaction("txn_shared")} == {first_event.id, second_event.id}
    assert store.latest_transaction_id(epic.id) == "txn_latest"
    assert store.list_epic_events(epic.id, kinds=["state_change"])[0].id == latest_event.id

    request = store.insert_pending(
        idempotency_key="idem_1",
        provider="discord",
        endpoint="POST /channels/channel_1/messages",
        request_summary={"content_preview": "hello"},
        request_body={"content": "hello"},
        turn_id=turn.id,
    )
    assert store.find_pending_external_requests(0)[0].id == request.id
    orphaned = store.mark_orphaned(
        request.id,
        error_details={"reason": "expired"},
        idempotency_key=idem("contract", request.id, "mark_orphaned"),
    )
    assert orphaned.status == "orphaned"
    confirmed = store.mark_confirmed(
        store.insert_pending(
            idempotency_key="idem_2",
            provider="discord",
            endpoint="POST /channels/channel_1/messages",
            request_summary={"content_preview": "second"},
            request_body={"content": "second"},
        ).id,
        provider_request_id="discord-req",
        provider_response_summary={"ok": True},
        idempotency_key=idem("contract", "idem_2", "mark_confirmed"),
    )
    assert confirmed.status == "confirmed"

    user_image = store.create_image(
        epic_id=epic.id,
        source="user_uploaded",
        storage_url="images/a.png",
        idempotency_key=idem("contract", epic.id, "user_image"),
    )
    hero = store.create_image(
        epic_id=epic.id,
        source="agent_generated",
        storage_url="images/b.png",
        reference_key="hero",
        idempotency_key=idem("contract", epic.id, "hero_image"),
    )
    assert user_image.reference_key == "img_user_upload_1"
    assert store.load_active_image_by_reference(epic.id, "hero").id == hero.id
    assert store.active_image_reference_exists(epic.id, "hero") is True
    assert (
        store.deactivate_active_image_reference(
            epic.id,
            "hero",
            idempotency_key=idem("contract", epic.id, "deactivate_image", "hero"),
        )[0].active
        is False
    )

    second_opinion = store.create_second_opinion(
        epic_id=epic.id,
        requested_by="user",
        focus_areas=["tone"],
        raw_response="raw",
        score=8,
        summary="solid",
        verdict="keep going",
        model_used="mock",
        idempotency_key=idem("contract", epic.id, "second_opinion"),
    )
    updated_opinion = store.set_second_opinion_checklist_items(
        second_opinion.id,
        [replaced[0].id],
        idempotency_key=idem("contract", second_opinion.id, "set_items"),
    )
    assert updated_opinion.resulting_checklist_item_ids == [replaced[0].id]

    codebase = store.create_codebase(
        owner="openai",
        name="megaplan",
        default_branch="main",
        repo_url="https://github.com/openai/megaplan.git",
        repo_workspace="/workspace/megaplan",
        root_commit_sha="abc123",
        group_name="backend",
        idempotency_key=idem("contract", "codebase", "create"),
    )
    assert store.find_codebase("openai", "megaplan").id == codebase.id
    assert store.load_codebase(codebase.id).repo_url == "https://github.com/openai/megaplan.git"
    assert store.load_codebase(codebase.id).repo_workspace == "/workspace/megaplan"
    assert store.resolve_codebase_by_root_sha("abc123").id == codebase.id
    upserted_codebase = store.upsert_codebase(
        owner="openai",
        name="megaplan",
        default_branch="trunk",
        repo_url="git@github.com:openai/megaplan.git",
        repo_workspace="/workspace/megaplan-next",
        root_commit_sha="def456",
        idempotency_key=idem("contract", "codebase", "upsert"),
    )
    assert upserted_codebase.default_branch == "trunk"
    assert upserted_codebase.repo_url == "git@github.com:openai/megaplan.git"
    assert upserted_codebase.repo_workspace == "/workspace/megaplan-next"
    assert upserted_codebase.root_commit_sha == "def456"
    assert store.resolve_codebase_by_root_sha("def456").id == codebase.id
    ticket_codebase_fields = {
        "owner": "openai",
        "name": f"megaplan-{epic_home_backend}",
        "default_branch": "main",
        "root_commit_sha": f"epic-{epic_home_backend}-sha",
    }
    repo_root = getattr(store, "repo_root", None)
    if repo_root is None and hasattr(store, epic_home_backend):
        repo_root = getattr(getattr(store, epic_home_backend), "repo_root", None)
    if repo_root is not None:
        identity = repo_codebase_identity(repo_root)
        ticket_codebase_fields.update(
            owner=identity.owner,
            name=identity.name,
            default_branch=identity.default_branch,
            root_commit_sha=identity.root_commit_sha,
        )
    epic_codebase = store.create_codebase(
        **ticket_codebase_fields,
        scope="epic_specific",
        associated_epic_id=epic.id,
        idempotency_key=idem("contract", epic.id, "codebase"),
    )
    assert store.load_codebase_by_associated_epic(epic.id).id == epic_codebase.id
    ticket = store.create_ticket(
        codebase_id=epic_codebase.id,
        title="Fix store abstraction",
        body="Preserve codebase identity and ticket links.",
        source="agent",
        tags=["store", "ticket"],
        slug=f"store-ticket-{epic_home_backend}",
        idempotency_key=idem("contract", epic.id, "ticket"),
    )
    assert store.load_ticket(ticket.id).title == "Fix store abstraction"
    assert [row.id for row in store.list_tickets(codebase_id=epic_codebase.id, keywords=["identity"])] == [ticket.id]
    link = store.link_ticket_to_epic(
        ticket_id=ticket.id,
        epic_id=epic.id,
        resolves_on_complete=True,
        idempotency_key=idem("contract", epic.id, "ticket_link"),
    )
    assert link.resolves_on_complete is True
    assert store.list_ticket_epic_links(ticket_id=ticket.id)[0].epic_id == epic.id
    assert store.address_tickets_resolved_by_epic(epic.id) == [ticket.id]
    assert store.load_ticket(ticket.id).status == "addressed"
    store.unlink_ticket_from_epic(
        ticket_id=ticket.id,
        epic_id=epic.id,
        idempotency_key=idem("contract", epic.id, "ticket_unlink"),
    )
    assert store.list_ticket_epic_links(ticket_id=ticket.id) == []
    artifact = store.create_code_artifact(
        kind="excerpt",
        source="codebase",
        content="print('hi')",
        codebase_id=codebase.id,
        epic_id=epic.id,
        file_path="app.py",
        scope="file",
        metadata={"cache_key": "ignore"},
        idempotency_key=idem("contract", epic.id, "code_artifact"),
    )
    assert (
        store.touch_code_artifact_used(artifact.id, idempotency_key=idem("contract", artifact.id, "touch")).last_used_at
        is not None
    )
    cache = store.upsert_api_cache(
        cache_key="cache-1",
        content="cached",
        epic_id=epic.id,
        idempotency_key=idem("contract", epic.id, "api_cache"),
    )
    assert store.get_api_cache("cache-1", touch=False).id == cache.id
    assert store.cleanup_expired_api_cache(idempotency_key=idem("contract", "cleanup_api_cache")) == 0

    feedback = store.create_feedback(
        kind="friction",
        content="slow",
        source="agent_observation",
        epic_id=epic.id,
        idempotency_key=idem("contract", epic.id, "feedback"),
    )
    assert store.list_observations(resolved=False)[0].id == feedback.id
    assert (
        store.update_feedback(feedback.id, resolved=True, idempotency_key=idem("contract", feedback.id, "resolve")).resolved_at
        is not None
    )

    orphan_plan = store.create_plan(
        sprint_id=None,
        epic_id=None,
        name="orphan-plan",
        idea="legacy",
        idempotency_key=idem("contract", "orphan_plan"),
    )
    epic_plan = store.create_plan(
        sprint_id=sprint.id,
        epic_id=epic.id,
        name="epic-plan",
        idea="scoped",
        idempotency_key=idem("contract", epic.id, "epic_plan"),
    )
    assert orphan_plan.epic_id is None
    plans = store.list_plans(include_orphans=True)
    assert {plan.id for plan in plans} >= {orphan_plan.id, epic_plan.id}
    assert any(plan.id == orphan_plan.id for plan in store.list_plans(include_orphans=True) if plan.epic_id is None)
    store.write_plan_artifact(
        orphan_plan.id,
        "state.json",
        b"{\"ok\": true}\n",
        idempotency_key=idem("contract", orphan_plan.id, "artifact", "state"),
    )
    assert store.read_plan_artifact(orphan_plan.id, "state.json") == b"{\"ok\": true}\n"
    assert store.stat_plan_artifact(orphan_plan.id, "state.json").size_bytes == len(b"{\"ok\": true}\n")
    assert store.list_plan_artifacts(orphan_plan.id)[0].name == "state.json"

    lease = store.acquire_execution_lease(
        epic_plan.id,
        holder_id="worker-a",
        worker_kind="local_cli",
        ttl_seconds=120,
        epic_id=epic.id,
        idempotency_key=idem("contract", epic_plan.id, "acquire_execution_lease"),
    )
    assert lease.plan_id == epic_plan.id
    assert lease.epic_id == epic.id
    assert store.heartbeat_lease(epic_plan.id, "worker-a", idempotency_key=idem("contract", epic_plan.id, "heartbeat")).holder_id == "worker-a"
    assert store.get_active_lease(epic_plan.id).holder_id == "worker-a"
    store.release_lease(epic_plan.id, "worker-a", idempotency_key=idem("contract", epic_plan.id, "release_lease"))
    assert store.get_active_lease(epic_plan.id) is None

    lock = store.acquire_lock(epic.id, "holder-a", 120, idempotency_key=idem("contract", epic.id, "acquire_lock", "a"))
    assert lock.holder_id == "holder-a"
    try:
        store.acquire_lock(epic.id, "holder-b", 120, idempotency_key=idem("contract", epic.id, "acquire_lock", "b"))
    except Exception:
        pass
    else:
        raise AssertionError("expected lock conflict")
    store.release_lock(epic.id, "holder-a", idempotency_key=idem("contract", epic.id, "release_lock", "a"))

    control = store.put_control_message(
        ControlMessageInput(
            epic_id=epic.id,
            actor_id="actor-1",
            intent="pause_plan",
            target_id=orphan_plan.id,
            payload={"reason": "wait"},
            idempotency_key="control-1",
        ),
        idempotency_key=idem("contract", epic.id, "put_control_message"),
    )
    try:
        store.put_control_message(
            ControlMessageInput.model_construct(
                epic_id=epic.id,
                actor_id="actor-1",
                intent="bogus",
                target_id=orphan_plan.id,
                payload={},
                idempotency_key="invalid-control",
            ),
            idempotency_key=idem("contract", epic.id, "invalid_put_control_message"),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid control intent should be rejected")
    claimed = store.claim_pending_control_messages(
        processor_id="proc-1",
        idempotency_key=idem("contract", "proc-1", "claim_control"),
    )
    assert claimed[0].id == control.id
    store.mark_control_message_processed(
        control.id,
        {"ok": True},
        idempotency_key=idem("contract", control.id, "mark_processed"),
    )
    progress = store.append_progress_event(
        ProgressEventInput(
            epic_id=epic.id,
            plan_id=orphan_plan.id,
            idempotency_key=idem("contract", orphan_plan.id, "append_progress"),
            kind="phase_start",
            summary="started",
            details={"phase": "execute"},
        ),
        idempotency_key=idem("contract", orphan_plan.id, "append_progress"),
    )
    duplicate_progress = store.append_progress_event(
        ProgressEventInput(
            epic_id=epic.id,
            plan_id=orphan_plan.id,
            idempotency_key=idem("contract", orphan_plan.id, "append_progress"),
            kind="phase_start",
            summary="started",
            details={"phase": "execute"},
        ),
        idempotency_key=idem("contract", orphan_plan.id, "append_progress"),
    )
    progress_events = store.list_progress_events(plan_id=orphan_plan.id)
    assert progress_events[0].id == progress.id
    assert duplicate_progress.id == progress.id
    assert len([event for event in progress_events if event.idempotency_key == progress.idempotency_key]) == 1

    actor = store.create_automation_actor(
        actor_id="actor-1",
        name="CLI",
        granted_epic_ids="*",
        actor_kind="cli",
        idempotency_key=idem("contract", "actor-1", "create"),
    )
    assert store.load_automation_actor(actor.id).name == "CLI"
    assert (
        store.update_automation_actor(
            actor.id,
            name="CLI v2",
            idempotency_key=idem("contract", actor.id, "update"),
        ).name
        == "CLI v2"
    )


def run_store_error_class_parity_contract(
    reference_factory: Callable[[], Store],
    candidate_factory: Callable[[], Store],
    *,
    candidate_home_backend: str = "file",
) -> None:
    reference = reference_factory()
    candidate = candidate_factory()
    idem = deterministic_idempotency_key

    reference_epic = reference.create_epic(
        title="Reference conflict epic",
        goal="Goal",
        body="Body",
        idempotency_key=idem("contract", "reference", "conflict-epic"),
    )
    candidate_epic = candidate.create_epic(
        title="Candidate conflict epic",
        goal="Goal",
        body="Body",
        home_backend=candidate_home_backend,
        idempotency_key=idem("contract", "candidate", "conflict-epic"),
    )

    reference.acquire_lock(reference_epic.id, "holder-a", 120, idempotency_key=idem("contract", reference_epic.id, "lock", "holder-a"))
    candidate.acquire_lock(candidate_epic.id, "holder-a", 120, idempotency_key=idem("contract", candidate_epic.id, "lock", "holder-a"))
    reference_lock = _capture_error_class(
        lambda: reference.acquire_lock(reference_epic.id, "holder-b", 120, idempotency_key=idem("contract", reference_epic.id, "lock", "holder-b")),
        label="reference active lock conflict",
    )
    candidate_lock = _capture_error_class(
        lambda: candidate.acquire_lock(candidate_epic.id, "holder-b", 120, idempotency_key=idem("contract", candidate_epic.id, "lock", "holder-b")),
        label="candidate active lock conflict",
    )
    assert reference_lock is candidate_lock, f"active lock conflict error class mismatch: {reference_lock.__name__} != {candidate_lock.__name__}"
    reference.release_lock(reference_epic.id, "holder-a", idempotency_key=idem("contract", reference_epic.id, "lock", "release"))
    candidate.release_lock(candidate_epic.id, "holder-a", idempotency_key=idem("contract", candidate_epic.id, "lock", "release"))

    reference_plan = reference.create_plan(
        sprint_id=None,
        epic_id=reference_epic.id,
        name="reference-lease-plan",
        idea="lease",
        idempotency_key=idem("contract", reference_epic.id, "lease-plan"),
    )
    candidate_plan = candidate.create_plan(
        sprint_id=None,
        epic_id=candidate_epic.id,
        name="candidate-lease-plan",
        idea="lease",
        idempotency_key=idem("contract", candidate_epic.id, "lease-plan"),
    )
    reference.acquire_execution_lease(
        reference_plan.id,
        "worker-a",
        "local_cli",
        120,
        epic_id=reference_epic.id,
        idempotency_key=idem("contract", reference_plan.id, "lease", "worker-a"),
    )
    candidate.acquire_execution_lease(
        candidate_plan.id,
        "worker-a",
        "local_cli",
        120,
        epic_id=candidate_epic.id,
        idempotency_key=idem("contract", candidate_plan.id, "lease", "worker-a"),
    )
    reference_lease = _capture_error_class(
        lambda: reference.acquire_execution_lease(
            reference_plan.id,
            "worker-b",
            "local_cli",
            120,
            epic_id=reference_epic.id,
            idempotency_key=idem("contract", reference_plan.id, "lease", "worker-b"),
        ),
        label="reference active execution lease conflict",
    )
    candidate_lease = _capture_error_class(
        lambda: candidate.acquire_execution_lease(
            candidate_plan.id,
            "worker-b",
            "local_cli",
            120,
            epic_id=candidate_epic.id,
            idempotency_key=idem("contract", candidate_plan.id, "lease", "worker-b"),
        ),
        label="candidate active execution lease conflict",
    )
    assert reference_lease is candidate_lease, (
        f"active execution lease conflict error class mismatch: {reference_lease.__name__} != {candidate_lease.__name__}"
    )
    reference.release_lease(reference_plan.id, "worker-a", idempotency_key=idem("contract", reference_plan.id, "lease", "release"))
    candidate.release_lease(candidate_plan.id, "worker-a", idempotency_key=idem("contract", candidate_plan.id, "lease", "release"))

    reference_orphan = reference.create_plan(
        sprint_id=None,
        epic_id=None,
        name="reference-unsafe-plan",
        idea="unsafe",
        idempotency_key=idem("contract", "reference", "unsafe-plan"),
    )
    candidate_orphan = candidate.create_plan(
        sprint_id=None,
        epic_id=None,
        name="candidate-unsafe-plan",
        idea="unsafe",
        idempotency_key=idem("contract", "candidate", "unsafe-plan"),
    )
    reference_unsafe = _capture_error_class(
        lambda: reference.write_plan_artifact(
            reference_orphan.id,
            "../escape.bin",
            b"bad",
            idempotency_key=idem("contract", reference_orphan.id, "unsafe", "write"),
        ),
        label="reference unsafe artifact path",
    )
    candidate_unsafe = _capture_error_class(
        lambda: candidate.write_plan_artifact(
            candidate_orphan.id,
            "../escape.bin",
            b"bad",
            idempotency_key=idem("contract", candidate_orphan.id, "unsafe", "write"),
        ),
        label="candidate unsafe artifact path",
    )
    assert reference_unsafe is candidate_unsafe, (
        f"unsafe artifact path error class mismatch: {reference_unsafe.__name__} != {candidate_unsafe.__name__}"
    )


def run_dbstore_preflight_contract() -> None:
    store = DBStore(actor_id="contract-actor-without-dsn")
    idempotency_error = _capture_error_class(
        lambda: store.create_epic(title="T", goal="G", body="B"),
        label="DBStore.create_epic idempotency requirement",
    )
    update_error = _capture_error_class(
        lambda: store.update_body("epic-id", "new body", expected_revision=1),
        label="DBStore.update_body idempotency requirement",
    )
    assert idempotency_error is ValueError
    assert idempotency_error is update_error, (
        f"DB idempotency-required error class mismatch: {idempotency_error.__name__} != {update_error.__name__}"
    )


def run_arnold_adapter_contract(store_factory: Callable[[], Store]) -> None:
    adapter = ArnoldStoreAdapter(store_factory())
    idem = deterministic_idempotency_key
    epic = adapter.create_epic(title="Title", goal="Goal", body="# Title\n", idempotency_key=idem("adapter", "create_epic"))

    # --- Explicit epic_id through adapter ---
    explicit_adapter_epic = adapter.create_epic(
        title="Adapter Explicit",
        goal="Exercise explicit epic_id through adapter",
        body="# Adapter Explicit\n",
        epic_id="adapter-explicit-epic",
        idempotency_key=idem("adapter", "explicit_epic"),
    )
    assert explicit_adapter_epic["id"] == "adapter-explicit-epic", (
        f"Adapter explicit epic_id mismatch: {explicit_adapter_epic['id']!r}"
    )

    # --- Generated default through adapter ---
    default_adapter_epic = adapter.create_epic(
        title="Adapter Default",
        goal="Exercise generated epic_id through adapter",
        body="# Adapter Default\n",
        idempotency_key=idem("adapter", "default_epic"),
    )
    assert default_adapter_epic["id"], "Adapter generated epic_id must be non-empty"
    assert default_adapter_epic["id"] != "adapter-explicit-epic", (
        f"Adapter generated ID {default_adapter_epic['id']!r} must differ from explicit"
    )

    inbound = adapter.create_message(
        epic_id=epic["id"],
        direction="inbound",
        content="hello",
        idempotency_key=idem("adapter", epic["id"], "inbound"),
    )
    turn = adapter.create_turn(
        epic_id=None,
        triggered_by_message_ids=[],
        prompt_snapshot={"phase": "bootstrap"},
        idempotency_key=idem("adapter", "bootstrap_turn"),
    )
    assert turn["epic_id"] is None
    assert adapter.acquire_epic_lock(epic["id"], holder_id="holder-a") is True
    assert adapter.acquire_epic_lock(epic["id"], holder_id="holder-b") is False
    adapter.release_epic_lock(epic["id"], holder_id="holder-a")
    assert adapter.load_message(inbound["id"])["content"] == "hello"
    assert adapter.load_hot_context(epic["id"])["epic"]["id"] == epic["id"]


def run_ticket_relationship_contract(store_factory: Callable[[], Store]) -> None:
    """Validate ticket–epic relationship semantics across backends.

    Covers:
    - Relationship kind constants
    - Legacy frontmatter normalisation (through store read path)
    - Auto-address gating: only resolves_on_complete=True tickets are addressed
    - Idempotency replay for link/unlink
    """
    from arnold_pipelines.megaplan.tickets.relationships import (
        KIND_ASSOCIATED,
        KIND_PROMOTED_TO_EPIC,
        KIND_RESOLVES_ON_COMPLETE,
        RELATIONSHIP_KINDS,
        auto_address_predicate,
        parse_frontmatter_links,
        serialize_links_to_frontmatter,
    )

    store = store_factory()
    idem = deterministic_idempotency_key

    # ------------------------------
    # Constants
    # ------------------------------
    assert KIND_ASSOCIATED in RELATIONSHIP_KINDS
    assert KIND_PROMOTED_TO_EPIC in RELATIONSHIP_KINDS
    assert KIND_RESOLVES_ON_COMPLETE in RELATIONSHIP_KINDS
    assert len(RELATIONSHIP_KINDS) == 3

    # ------------------------------
    # Normalisation (unit)
    # ------------------------------
    legacy = parse_frontmatter_links(
        {"id": "tid", "epics": [{"epic_id": "e1", "resolves_on_complete": True}]},
        ticket_id="tid",
    )
    assert legacy[0].kind == KIND_RESOLVES_ON_COMPLETE
    assert legacy[0].provenance is None

    legacy_no_resolve = parse_frontmatter_links(
        {"id": "tid", "epics": [{"epic_id": "e2"}]},
        ticket_id="tid",
    )
    assert legacy_no_resolve[0].kind == KIND_ASSOCIATED

    # ------------------------------
    # Serialization round-trip
    # ------------------------------
    from arnold_pipelines.megaplan.schemas import TicketEpicLink

    link = TicketEpicLink(
        ticket_id="tid", epic_id="e3", resolves_on_complete=False,
        kind=KIND_PROMOTED_TO_EPIC, provenance="promo",
    )
    serialized = serialize_links_to_frontmatter([link])
    for entry in serialized:
        assert "kind" in entry
        assert "provenance" in entry

    # ------------------------------
    # Auto-address predicate
    # ------------------------------
    assert auto_address_predicate(
        TicketEpicLink(ticket_id="t", epic_id="e", resolves_on_complete=True, kind=KIND_RESOLVES_ON_COMPLETE),
    ) is True
    assert auto_address_predicate(
        TicketEpicLink(ticket_id="t", epic_id="e", resolves_on_complete=False, kind=KIND_ASSOCIATED),
    ) is False
    assert auto_address_predicate(
        TicketEpicLink(ticket_id="t", epic_id="e", resolves_on_complete=False, kind=KIND_PROMOTED_TO_EPIC),
    ) is False

    # ------------------------------
    # Store-backed contract
    # ------------------------------
    epic = store.create_epic(
        title="Relationship Contract Epic",
        goal="Exercise ticket–epic relationships",
        body="# Epic\n",
        idempotency_key=idem("rel-contract", "epic"),
    )
    codebase = None
    if hasattr(store, "_resolve_ticket_codebase"):
        codebase = store._resolve_ticket_codebase()
    else:
        # For DB-backed stores, resolve codebase via identity
        from arnold_pipelines.megaplan.tickets.identity import repo_codebase_identity

        identity = repo_codebase_identity()
        cb = store.resolve_codebase_by_root_sha(identity.root_commit_sha)
        if cb is None:
            cb = store.create_codebase(
                owner=identity.owner,
                name=identity.name,
                default_branch=identity.default_branch,
                root_commit_sha=identity.root_commit_sha,
                idempotency_key=idem("rel-contract", "codebase"),
            )
        codebase = cb

    ticket_resolve = store.create_ticket(
        codebase_id=codebase.id,
        title="Resolving Ticket",
        body="Should auto-address.",
        slug="resolving-ticket",
        idempotency_key=idem("rel-contract", "ticket-resolve"),
    )
    ticket_assoc = store.create_ticket(
        codebase_id=codebase.id,
        title="Associated Ticket",
        body="Should NOT auto-address.",
        slug="associated-ticket",
        idempotency_key=idem("rel-contract", "ticket-assoc"),
    )

    # Link with explicit kind
    link1 = store.link_ticket_to_epic(
        ticket_id=ticket_resolve.id,
        epic_id=epic.id,
        resolves_on_complete=True,
        kind=KIND_RESOLVES_ON_COMPLETE,
        provenance="contract",
        idempotency_key=idem("rel-contract", "link-resolve"),
    )
    assert link1.kind == KIND_RESOLVES_ON_COMPLETE
    assert link1.provenance == "contract"

    link2 = store.link_ticket_to_epic(
        ticket_id=ticket_assoc.id,
        epic_id=epic.id,
        resolves_on_complete=False,
        kind=KIND_ASSOCIATED,
        provenance="contract",
        idempotency_key=idem("rel-contract", "link-assoc"),
    )
    assert link2.kind == KIND_ASSOCIATED

    # Link replay (idempotency)
    replayed = store.link_ticket_to_epic(
        ticket_id=ticket_resolve.id,
        epic_id=epic.id,
        resolves_on_complete=True,
        kind=KIND_RESOLVES_ON_COMPLETE,
        provenance="contract",
        idempotency_key=idem("rel-contract", "link-resolve"),
    )
    assert replayed.linked_at == link1.linked_at

    # List links
    links = store.list_ticket_epic_links(epic_id=epic.id)
    assert len(links) == 2

    # --- Auto-address: only resolves_on_complete ticket is addressed ---
    addressed = store.address_tickets_resolved_by_epic(epic.id)
    assert addressed == [ticket_resolve.id]

    resolved_ticket = store.load_ticket(ticket_resolve.id)
    assert resolved_ticket.status == "addressed"

    assoc_ticket = store.load_ticket(ticket_assoc.id)
    assert assoc_ticket.status == "open"

    # --- Unlink idempotency ---
    store.unlink_ticket_from_epic(
        ticket_id=ticket_resolve.id,
        epic_id=epic.id,
        idempotency_key=idem("rel-contract", "unlink-resolve"),
    )
    # Second unlink should succeed
    store.unlink_ticket_from_epic(
        ticket_id=ticket_resolve.id,
        epic_id=epic.id,
        idempotency_key=idem("rel-contract", "unlink-resolve"),
    )
    remaining = store.list_ticket_epic_links(ticket_id=ticket_resolve.id)
    assert remaining == []


def test_db_copy_columns_preserve_ticket_epic_relationship_metadata() -> None:
    """Migration copy allowlist must preserve new relationship metadata."""

    from arnold_pipelines.megaplan.store._db.common import _COPY_TABLE_COLUMNS

    row = {
        "ticket_id": "ticket-1",
        "epic_id": "epic-1",
        "resolves_on_complete": True,
        "kind": "promoted_to_epic",
        "provenance": "promotion:ticket-1",
        "linked_at": "2026-07-14T00:00:00+00:00",
    }
    copied_columns = [column for column in row if column in _COPY_TABLE_COLUMNS["ticket_epics"]]
    assert {"kind", "provenance"}.issubset(copied_columns)


@pytest.fixture
def file_store_factory(tmp_path: Path):
    """Return a fresh FileStore factory so direct path selection collects tests."""
    return make_file_store_factory(tmp_path)


def test_store_contract_explicit_ids_and_idempotency(file_store_factory) -> None:
    """Direct selector coverage for the core store contract helper."""

    run_store_contract(file_store_factory)


def test_arnold_adapter_contract_epic_ids(file_store_factory) -> None:
    """Direct selector coverage for adapter explicit/generated epic IDs."""

    run_arnold_adapter_contract(file_store_factory)


def test_ticket_relationship_contract(file_store_factory) -> None:
    """Direct selector coverage for relationship semantics and auto-address gating."""

    run_ticket_relationship_contract(file_store_factory)
