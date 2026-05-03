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
)


def run_store_contract(store_factory: Callable[[], Store]) -> None:
    store = store_factory()

    epic = store.create_epic(
        title="Editorial Title",
        goal="Editorial Goal",
        body="# Editorial Title\n\nEditorial Goal\n",
    )
    assert store.load_epic(epic.id).title == "Editorial Title"
    assert store.load_body(epic.id).startswith("# Editorial Title")
    updated_epic = store.update_body(epic.id, "# Revised\n", expected_revision=epic.revision)
    assert updated_epic.revision == epic.revision + 1
    assert store.search_epics(query="revised")[0].id == epic.id

    checklist = store.seed_checklist(epic.id, ["First item", "Second item"])
    assert [item.position for item in checklist] == [1, 2]
    replaced = store.replace_checklist(
        epic.id,
        [
            ChecklistItemInput(content="Replacement item", status="open", position=1, source="user_requested"),
        ],
    )
    assert [item.content for item in replaced] == ["Replacement item"]
    assert store.update_checklist_item(replaced[0].id, status="done").completed_at is not None

    sprint = store.create_sprint(epic_id=epic.id, sprint_number=1, name="Sprint 1", goal="Ship it")
    items = store.replace_sprint_items(
        sprint.id,
        [
            SprintItemInput(content="Investigate", estimated_complexity="small", status="open", position=1),
        ],
    )
    assert items[0].content == "Investigate"
    queued = store.set_sprint_queue(epic.id, [sprint.id], {})
    assert queued[0].queue_position == 1
    assert store.list_sprints_with_items(epic.id)[0].items[0].id == items[0].id

    bootstrap_turn = store.create_turn(epic_id=None, triggered_by_message_ids=[], prompt_snapshot={"phase": "bootstrap"})
    assert bootstrap_turn.epic_id is None
    bootstrap_message = store.create_message(epic_id=None, direction="inbound", content="bootstrap hello")
    assert bootstrap_message.epic_id is None

    inbound = store.create_message(
        epic_id=epic.id,
        direction="inbound",
        content="hello from user",
        discord_message_id="discord_1",
        has_code_attachment=True,
    )
    turn = store.create_turn(
        epic_id=epic.id,
        triggered_by_message_ids=[inbound.id],
        prompt_snapshot={"input": "hello from user"},
        state_at_turn={"state": "shaping"},
        model_version="fake",
    )
    completed_turn = store.update_turn(turn.id, status="completed", reasoning="done")
    assert completed_turn.completed_at is not None
    outbound = store.create_message(epic_id=epic.id, direction="outbound", content="hi", bot_turn_id=turn.id)
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
    )
    second_event = store.record_epic_event(
        epic_id=epic.id,
        transaction_id="txn_shared",
        event_type="checklist_change",
        summary="Checklist updated",
        prior_state={"items": [item.model_dump(mode='json') for item in replaced]},
        turn_id=turn.id,
    )
    latest_event = store.record_epic_event(
        epic_id=epic.id,
        transaction_id="txn_latest",
        event_type="state_change",
        summary="State updated",
        prior_state={"state": "shaping"},
        turn_id=turn.id,
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
    orphaned = store.mark_orphaned(request.id, error_details={"reason": "expired"})
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
    )
    assert confirmed.status == "confirmed"

    user_image = store.create_image(epic_id=epic.id, source="user_uploaded", storage_url="images/a.png")
    hero = store.create_image(epic_id=epic.id, source="agent_generated", storage_url="images/b.png", reference_key="hero")
    assert user_image.reference_key == "img_user_upload_1"
    assert store.load_active_image_by_reference(epic.id, "hero").id == hero.id
    assert store.active_image_reference_exists(epic.id, "hero") is True
    assert store.deactivate_active_image_reference(epic.id, "hero")[0].active is False

    second_opinion = store.create_second_opinion(
        epic_id=epic.id,
        requested_by="user",
        focus_areas=["tone"],
        raw_response="raw",
        score=8,
        summary="solid",
        verdict="keep going",
        model_used="mock",
    )
    updated_opinion = store.set_second_opinion_checklist_items(second_opinion.id, [replaced[0].id])
    assert updated_opinion.resulting_checklist_item_ids == [replaced[0].id]

    codebase = store.create_codebase(owner="openai", name="megaplan", default_branch="main", group_name="backend")
    assert store.find_codebase("openai", "megaplan").id == codebase.id
    assert store.upsert_codebase(owner="openai", name="megaplan", default_branch="trunk").default_branch == "trunk"
    artifact = store.create_code_artifact(
        kind="excerpt",
        source="codebase",
        content="print('hi')",
        codebase_id=codebase.id,
        epic_id=epic.id,
        file_path="app.py",
        scope="file",
        metadata={"cache_key": "ignore"},
    )
    assert store.touch_code_artifact_used(artifact.id).last_used_at is not None
    cache = store.upsert_api_cache(cache_key="cache-1", content="cached", epic_id=epic.id)
    assert store.get_api_cache("cache-1", touch=False).id == cache.id
    assert store.cleanup_expired_api_cache() == 0

    feedback = store.create_feedback(
        kind="friction",
        content="slow",
        source="agent_observation",
        epic_id=epic.id,
    )
    assert store.list_observations(resolved=False)[0].id == feedback.id
    assert store.update_feedback(feedback.id, resolved=True).resolved_at is not None

    orphan_plan = store.create_plan(sprint_id=None, epic_id=None, name="orphan-plan", idea="legacy")
    epic_plan = store.create_plan(sprint_id=sprint.id, epic_id=epic.id, name="epic-plan", idea="scoped")
    assert orphan_plan.epic_id is None
    plans = store.list_plans(include_orphans=True)
    assert {plan.id for plan in plans} >= {orphan_plan.id, epic_plan.id}
    assert any(plan.id == orphan_plan.id for plan in store.list_plans(include_orphans=True) if plan.epic_id is None)
    store.write_plan_artifact(orphan_plan.id, "state.json", b"{\"ok\": true}\n")
    assert store.read_plan_artifact(orphan_plan.id, "state.json") == b"{\"ok\": true}\n"
    assert store.stat_plan_artifact(orphan_plan.id, "state.json").size_bytes == len(b"{\"ok\": true}\n")
    assert store.list_plan_artifacts(orphan_plan.id)[0].name == "state.json"

    lease = store.acquire_execution_lease(orphan_plan.id, holder_id="worker-a", worker_kind="local_cli", ttl_seconds=120)
    assert lease.plan_id == orphan_plan.id
    assert store.heartbeat_lease(orphan_plan.id, "worker-a").holder_id == "worker-a"
    assert store.get_active_lease(orphan_plan.id).holder_id == "worker-a"
    store.release_lease(orphan_plan.id, "worker-a")
    assert store.get_active_lease(orphan_plan.id) is None

    lock = store.acquire_lock(epic.id, "holder-a", 120)
    assert lock.holder_id == "holder-a"
    try:
        store.acquire_lock(epic.id, "holder-b", 120)
    except Exception:
        pass
    else:
        raise AssertionError("expected lock conflict")
    store.release_lock(epic.id, "holder-a")

    control = store.put_control_message(
        ControlMessageInput(
            epic_id=epic.id,
            actor_id="actor-1",
            intent="pause_plan",
            target_id=orphan_plan.id,
            payload={"reason": "wait"},
            idempotency_key="control-1",
        )
    )
    claimed = store.claim_pending_control_messages(processor_id="proc-1")
    assert claimed[0].id == control.id
    store.mark_control_message_processed(control.id, {"ok": True})
    progress = store.append_progress_event(
        ProgressEventInput(
            epic_id=epic.id,
            plan_id=orphan_plan.id,
            kind="phase_start",
            summary="started",
            details={"phase": "execute"},
        )
    )
    assert store.list_progress_events(plan_id=orphan_plan.id)[0].id == progress.id

    actor = store.create_automation_actor(
        actor_id="actor-1",
        name="CLI",
        granted_epic_ids="*",
        actor_kind="cli",
    )
    assert store.load_automation_actor(actor.id).name == "CLI"
    assert store.update_automation_actor(actor.id, name="CLI v2").name == "CLI v2"


def run_arnold_adapter_contract(store_factory: Callable[[], Store]) -> None:
    adapter = ArnoldStoreAdapter(store_factory())
    epic = adapter.create_epic(title="Title", goal="Goal", body="# Title\n")
    inbound = adapter.create_message(epic_id=epic["id"], direction="inbound", content="hello")
    turn = adapter.create_turn(epic_id=None, triggered_by_message_ids=[], prompt_snapshot={"phase": "bootstrap"})
    assert turn["epic_id"] is None
    assert adapter.acquire_epic_lock(epic["id"], holder_id="holder-a") is True
    assert adapter.acquire_epic_lock(epic["id"], holder_id="holder-b") is False
    adapter.release_epic_lock(epic["id"], holder_id="holder-a")
    assert adapter.load_message(inbound["id"])["content"] == "hello"
    assert adapter.load_hot_context(epic["id"])["epic"]["id"] == epic["id"]
