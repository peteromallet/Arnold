from __future__ import annotations

from pathlib import Path
from typing import Callable

from megaplan.store import (
    ArnoldStoreAdapter,
    ChecklistItemInput,
    ControlMessageInput,
    ProgressEventInput,
    SprintItemInput,
    Store,
    deterministic_idempotency_key,
)


def run_store_contract(store_factory: Callable[[], Store]) -> None:
    store = store_factory()
    idem = deterministic_idempotency_key

    epic = store.create_epic(
        title="Editorial Title",
        goal="Editorial Goal",
        body="# Editorial Title\n\nEditorial Goal\n",
        idempotency_key=idem("contract", "create_epic"),
    )
    assert store.load_epic(epic.id).title == "Editorial Title"
    assert store.load_body(epic.id).startswith("# Editorial Title")
    updated_epic = store.update_body(
        epic.id,
        "# Revised\n",
        expected_revision=epic.revision,
        idempotency_key=idem("contract", epic.id, "update_body"),
    )
    assert updated_epic.revision == epic.revision + 1
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
        group_name="backend",
        idempotency_key=idem("contract", "codebase", "create"),
    )
    assert store.find_codebase("openai", "megaplan").id == codebase.id
    assert (
        store.upsert_codebase(
            owner="openai",
            name="megaplan",
            default_branch="trunk",
            idempotency_key=idem("contract", "codebase", "upsert"),
        ).default_branch
        == "trunk"
    )
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
            kind="phase_start",
            summary="started",
            details={"phase": "execute"},
        ),
        idempotency_key=idem("contract", orphan_plan.id, "append_progress"),
    )
    assert store.list_progress_events(plan_id=orphan_plan.id)[0].id == progress.id

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


def run_arnold_adapter_contract(store_factory: Callable[[], Store]) -> None:
    adapter = ArnoldStoreAdapter(store_factory())
    idem = deterministic_idempotency_key
    epic = adapter.create_epic(title="Title", goal="Goal", body="# Title\n", idempotency_key=idem("adapter", "create_epic"))
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
