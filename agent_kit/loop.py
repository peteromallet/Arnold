"""Transport-agnostic turn loop entry points."""

from __future__ import annotations

import asyncio
import json
from threading import Event as ThreadingEvent
from typing import Callable, Sequence
from uuid import uuid4

from agent_kit import body
from agent_kit.attachments import AttachmentInput, UnsupportedMediaTypeError, normalize_image_attachments
from agent_kit.end_of_turn import (
    DEFAULT_END_OF_TURN_ACKNOWLEDGMENT,
    EndOfTurnToolCall,
    ensure_reframing_suggestion,
    evaluate_end_of_turn,
)
from agent_kit.envelope import Envelope, EnvelopeError, Event, StateDelta
from agent_kit.ledger import Ledger
from agent_kit.logging import log
from agent_kit.ports import Blob, JSONDict, Model, OpenAIOps, ProviderError, PushTransport, Store
from agent_kit.epic_routing import conversation_gap_acknowledgment, detect_user_mode, resolve_reference
from agent_kit.prompts import (
    DEFAULT_PROMPT_VERSION,
    build_system_prompt,
    system_prompt_version,
)
from agent_kit.tool_kit import ToolContext, registry
import agent_kit.tools.communication  # noqa: F401
import agent_kit.tools.editorial  # noqa: F401
import agent_kit.tools.feedback  # noqa: F401
import agent_kit.tools.editorial_reads  # noqa: F401
import agent_kit.tools.images  # noqa: F401
import agent_kit.tools.second_opinion  # noqa: F401
import agent_kit.tools.code  # noqa: F401


ANTHROPIC_MESSAGES_ENDPOINT = "POST /v1/messages"
ANTHROPIC_MAX_TOKENS = 4096
def run_turn(
    *,
    epic_id: str | None = None,
    input: str,
    store: Store,
    model: Model,
    model_id: str = "claude-opus-4-7",
    on_event=None,
    cancel_event: ThreadingEvent | None = None,
    triggered_by_message_ids: Sequence[str] | None = None,
    recovered_input_messages: Sequence[JSONDict] | None = None,
    on_turn_start: Callable[[JSONDict], None] | None = None,
    mid_turn_message_check: Callable[[JSONDict], list[JSONDict] | None] | None = None,
    transport: PushTransport | None = None,
    blob: Blob | None = None,
    attachments: Sequence[AttachmentInput] | None = None,
    openai_ops: OpenAIOps | None = None,
    channel_id: str | None = None,
    response_policy: JSONDict | None = None,
    resolved_reference: JSONDict | None = None,
) -> Envelope:
    normalized_attachments = []
    if attachments:
        if triggered_by_message_ids is not None:
            return Envelope(
                turn_id=f"turn_attachments_{uuid4().hex}",
                epic_id=epic_id,
                epic_state_before="unknown",
                epic_state_after="unknown",
                reply="",
                state_delta=StateDelta(),
                outcome="errored",
                error=EnvelopeError(
                    code="attachments_require_invocation",
                    message="Image attachments are only supported for direct invocation turns.",
                    retryable=False,
                ),
            )
        if epic_id is None:
            return Envelope(
                turn_id=f"turn_attachments_{uuid4().hex}",
                epic_id=None,
                epic_state_before="unknown",
                epic_state_after="unknown",
                reply="",
                state_delta=StateDelta(),
                outcome="errored",
                error=EnvelopeError(
                    code="attachments_require_epic",
                    message="Image attachments require an explicit epic_id.",
                    retryable=False,
                ),
            )
        if blob is None:
            return Envelope(
                turn_id=f"turn_attachments_{uuid4().hex}",
                epic_id=epic_id,
                epic_state_before="unknown",
                epic_state_after="unknown",
                reply="",
                state_delta=StateDelta(),
                outcome="errored",
                error=EnvelopeError(
                    code="attachments_require_blob",
                    message="Image attachments require a blob adapter.",
                    retryable=False,
                ),
            )
        try:
            normalized_attachments = normalize_image_attachments(tuple(attachments))
        except UnsupportedMediaTypeError as exc:
            return Envelope(
                turn_id=f"turn_attachments_{uuid4().hex}",
                epic_id=epic_id,
                epic_state_before="unknown",
                epic_state_after="unknown",
                reply="",
                state_delta=StateDelta(),
                outcome="errored",
                error=EnvelopeError(
                    code="unsupported_media_type",
                    message=str(exc),
                    retryable=False,
                ),
            )

    holder_id = f"turn_holder_{uuid4().hex}"
    active_epic_id: str | None = epic_id
    lock_acquired = False
    if epic_id is not None:
        lock_acquired = store.acquire_epic_lock(epic_id, holder_id=holder_id, timeout_seconds=60)
        if not lock_acquired:
            log(
                store,
                "warn",
                "system",
                "epic_lock_contended",
                "Epic is already locked by another turn.",
                epic_id=active_epic_id,
            )
            return Envelope(
                turn_id=f"turn_lock_{uuid4().hex}",
                epic_id=active_epic_id,
                epic_state_before="unknown",
                epic_state_after="unknown",
                reply="",
                state_delta=StateDelta(),
                outcome="errored",
                error=EnvelopeError(
                    code="epic_locked",
                    message="Epic is already locked by another turn.",
                    retryable=True,
                ),
            )

    turn = None
    events: list[Event] = []
    reply_buffer: list[str] = []
    context: ToolContext | None = None
    state_before = "unknown"
    body_before: str | None = None
    checklist_before: list[JSONDict] = []
    tool_calls_this_turn: list[EndOfTurnToolCall] = []
    try:
        if recovered_input_messages is not None:
            initial_user_prompt = _messages_prompt(recovered_input_messages)
        else:
            initial_user_prompt = input

        if triggered_by_message_ids is None:
            inbound = store.create_message(
                epic_id=active_epic_id,
                direction="inbound",
                content=input,
                discord_message_id=f"inv_in_{uuid4().hex}",
            )
            if normalized_attachments:
                _store_invocation_image_attachments(
                    store=store,
                    blob=blob,
                    epic_id=active_epic_id,
                    message_id=inbound["id"],
                    attachments=normalized_attachments,
                )
                inbound = store.update_message(
                    inbound["id"],
                    has_image_attachment=True,
                )
            turn_message_ids = [inbound["id"]]
        else:
            turn_message_ids = list(triggered_by_message_ids)

        hot_context = store.load_hot_context(active_epic_id)
        latest_outbound = store.latest_outbound_message(epic_id=active_epic_id)
        if response_policy is None:
            recent_messages = hot_context.get("recent_messages") or []
            previous_inbound = next(
                (
                    row for row in reversed(recent_messages)
                    if row.get("direction") == "inbound"
                    and row.get("id") not in set(turn_message_ids)
                ),
                None,
            )
            response_policy = {
                "mode": detect_user_mode(initial_user_prompt),
                "conversation_gap_acknowledgment": conversation_gap_acknowledgment(
                    previous_inbound.get("sent_at") if previous_inbound else None
                ),
            }
        if resolved_reference is None:
            resolved_reference = resolve_reference(
                initial_user_prompt,
                str(latest_outbound.get("content") or "") if latest_outbound else None,
            )
        hot_context["response_policy"] = response_policy
        hot_context["resolved_reference"] = resolved_reference
        epic = hot_context.get("epic") or {}
        state_before = epic.get("state", "unknown")
        body_before = str(epic.get("body") or "") if epic else None
        checklist_before = (
            store.list_checklist_items(active_epic_id)
            if active_epic_id is not None
            else []
        )
        turn = store.create_turn(
            epic_id=active_epic_id,
            triggered_by_message_ids=turn_message_ids,
            prompt_snapshot={
                "input": initial_user_prompt,
                "hot_context": _summarize_hot_context(hot_context),
            },
            prompt_version=DEFAULT_PROMPT_VERSION,
            state_at_turn={"epic_state": state_before},
            model_version=model_id,
        )
        if on_turn_start is not None:
            on_turn_start(turn)
        ledger = Ledger(store)
        context = ToolContext(
            store=store,
            turn_id=turn["id"],
            events=events,
            on_event=on_event,
            reply_buffer=reply_buffer,
            metadata={
                "epic_id": active_epic_id,
                "outcome": "completed",
                "questions": [],
                "channel_id": channel_id,
                "user_message": initial_user_prompt,
            },
            transport=transport,
            blob=blob,
            openai_ops=openai_ops,
        )
        if triggered_by_message_ids is None:
            context.metadata["inbound_message_id"] = inbound["id"]

        if _is_cancelled(cancel_event):
            return _abort_turn(store, turn, active_epic_id, state_before, events, reply_buffer)

        model_call_seq = 0
        messages = [{"role": "user", "content": initial_user_prompt}]
        while True:
            model_call_seq += 1
            tool_definitions = list(registry.definitions())
            system_prompt = build_system_prompt(hot_context)
            prompt_version = system_prompt_version(system_prompt)
            request_body = {
                "model": model_id,
                "system": system_prompt,
                "messages": list(messages),
                "tools": tool_definitions,
                "max_tokens": ANTHROPIC_MAX_TOKENS,
            }
            request_summary = {
                "model": model_id,
                "message_count": len(messages),
                "tool_names": [definition["name"] for definition in tool_definitions],
                "input_length": len(input),
                "system_seq": model_call_seq,
                "hot_context": _summarize_hot_context(hot_context),
                "prompt_version": prompt_version,
                "system_hash": prompt_version,
            }
            request_id, idempotency_key = ledger.record_pending(
                provider="anthropic",
                endpoint=ANTHROPIC_MESSAGES_ENDPOINT,
                request_summary=request_summary,
                request_body=request_body,
                turn_id=turn["id"],
                system_seq=model_call_seq,
            )
            try:
                result = model.complete_turn(
                    model_id=model_id,
                    system=system_prompt,
                    messages=messages,
                    tools=tool_definitions,
                    hot_context=hot_context,
                    idempotency_key=idempotency_key,
                )
            except ProviderError as exc:
                ledger.mark_failed(request_id, exc.error_details)
                log(
                    store,
                    "error",
                    "llm",
                    "provider_error",
                    "Model provider returned an error.",
                    turn_id=turn["id"],
                    epic_id=active_epic_id,
                    error_details=exc.error_details,
                    provider_request_id=exc.provider_request_id,
                )
                store.update_turn(turn["id"], status="failed", reasoning=str(exc.error_details))
                return _envelope(
                    turn_id=turn["id"],
                    epic_id=active_epic_id,
                    state_before=state_before,
                    state_after=state_before,
                    reply_buffer=reply_buffer,
                    events=events,
                    outcome="errored",
                    error=EnvelopeError(
                        code="provider_error",
                        message="Model provider returned an error.",
                        retryable=True,
                    ),
                )
            except Exception as exc:
                log(
                    store,
                    "error",
                    "llm",
                    "transport_error",
                    "Model transport or SDK call failed.",
                    turn_id=turn["id"],
                    epic_id=active_epic_id,
                    error_type=type(exc).__name__,
                )
                store.update_turn(turn["id"], status="failed", reasoning=str(exc))
                return _envelope(
                    turn_id=turn["id"],
                    epic_id=active_epic_id,
                    state_before=state_before,
                    state_after=state_before,
                    reply_buffer=reply_buffer,
                    events=events,
                    outcome="errored",
                    error=EnvelopeError(
                        code="model_error",
                        message=str(exc),
                        retryable=True,
                    ),
                )

            ledger.mark_confirmed(
                request_id,
                result.provider_request_id,
                result.response_summary,
            )
            store.update_turn(
                turn["id"],
                prompt_snapshot=request_summary,
                reasoning=result.reasoning,
                model_version=model_id,
            )

            if _is_cancelled(cancel_event):
                return _abort_turn(store, turn, active_epic_id, state_before, events, reply_buffer)

            if result.tool_requests:
                reenter_model_loop = False
                for tool_request in result.tool_requests:
                    if _is_cancelled(cancel_event):
                        return _abort_turn(
                            store,
                            turn,
                            active_epic_id,
                            state_before,
                            events,
                            reply_buffer,
                        )
                    updated_turn = None
                    if tool_request.name == "send_message":
                        # Resident mode gives late inbound messages one more model pass before posting.
                        updated_turn = _append_mid_turn_messages(
                            store=store,
                            turn=turn,
                            messages=messages,
                            mid_turn_message_check=mid_turn_message_check,
                        )
                    if updated_turn is not None:
                        turn = updated_turn
                        reenter_model_loop = True
                        break
                    try:
                        invocation = registry.invoke(
                            tool_request.name,
                            context,
                            tool_request.arguments,
                        )
                        tool_calls_this_turn.append(_end_of_turn_tool_call(invocation.tool_call))
                        active_epic_id = context.metadata.get("epic_id", active_epic_id)
                    except Exception as exc:
                        log(
                            store,
                            "error",
                            "tool",
                            "tool_call_failed",
                            "Tool invocation failed.",
                            turn_id=turn["id"],
                            epic_id=active_epic_id,
                            tool_name=tool_request.name,
                            error_type=type(exc).__name__,
                        )
                        store.update_turn(turn["id"], status="failed", reasoning=str(exc))
                        return _envelope(
                            turn_id=turn["id"],
                            epic_id=active_epic_id,
                            state_before=state_before,
                            state_after=state_before,
                            reply_buffer=reply_buffer,
                            events=events,
                            outcome="errored",
                            error=EnvelopeError(
                                code="tool_error",
                                message=str(exc),
                                retryable=False,
                            ),
                        )
                    messages.append(
                        {
                            "role": "user",
                            "content": _tool_result_content(
                                tool_request.name,
                                invocation.result,
                            ),
                        }
                    )
                    if context.metadata.get("stop_requested"):
                        questions = list(context.metadata.get("questions", []))
                        store.update_turn(turn["id"], status="completed")
                        _log_epic_outline_if_needed(store, active_epic_id, turn, events)
                        return _envelope(
                            turn_id=turn["id"],
                            epic_id=active_epic_id,
                            state_before=state_before,
                            state_after=state_before,
                            reply_buffer=reply_buffer,
                            events=events,
                            outcome="blocked_on_caller",
                            questions=questions,
                        )
                if reenter_model_loop:
                    continue
                continue

            if result.final_text is not None:
                updated_turn = _append_mid_turn_messages(
                    store=store,
                    turn=turn,
                    messages=messages,
                    mid_turn_message_check=mid_turn_message_check,
                )
                if updated_turn is not None:
                    turn = updated_turn
                    continue
                return _finish_after_model_response(
                    store=store,
                    turn=turn,
                    context=context,
                    active_epic_id=active_epic_id,
                    state_before=state_before,
                    body_before=body_before,
                    checklist_before=checklist_before,
                    tool_calls_this_turn=tool_calls_this_turn,
                    reply_buffer=reply_buffer,
                    events=events,
                    final_text=result.final_text,
                    initial_user_prompt=initial_user_prompt,
                )

            return _finish_after_model_response(
                store=store,
                turn=turn,
                context=context,
                active_epic_id=active_epic_id,
                state_before=state_before,
                body_before=body_before,
                checklist_before=checklist_before,
                tool_calls_this_turn=tool_calls_this_turn,
                reply_buffer=reply_buffer,
                events=events,
                final_text=None,
                initial_user_prompt=initial_user_prompt,
            )
    finally:
        if lock_acquired and epic_id is not None:
            store.release_epic_lock(epic_id, holder_id=holder_id)


async def arun_turn(*args, **kwargs) -> Envelope:
    return await asyncio.to_thread(run_turn, *args, **kwargs)


__all__ = ["Envelope", "arun_turn", "run_turn"]


def _store_invocation_image_attachments(
    *,
    store: Store,
    blob: Blob | None,
    epic_id: str | None,
    message_id: str,
    attachments: Sequence[object],
) -> list[JSONDict]:
    if epic_id is None:
        raise ValueError("attachments require epic_id")
    if blob is None:
        raise ValueError("attachments require blob")
    images: list[JSONDict] = []
    with store.transaction():
        for index, attachment in enumerate(attachments, start=1):
            content = getattr(attachment, "content")
            mime_type = getattr(attachment, "mime_type")
            filename = getattr(attachment, "filename", None)
            ref = blob.put(
                epic_id,
                content,
                mime_type,
                idempotency_key=f"{message_id}_{index}",
            )
            caption = str(filename) if filename else None
            images.append(
                store.create_image(
                    epic_id=epic_id,
                    source="caller_uploaded",
                    storage_url=ref.key,
                    caption=caption,
                    description="Invocation image attachment.",
                )
            )
    return images


def _abort_turn(
    store: Store,
    turn: dict,
    epic_id: str | None,
    state_before: str,
    events: list[Event],
    reply_buffer: list[str],
) -> Envelope:
    store.update_turn(turn["id"], status="abandoned")
    return _envelope(
        turn_id=turn["id"],
        epic_id=epic_id,
        state_before=state_before,
        state_after=state_before,
        reply_buffer=reply_buffer,
        events=events,
        outcome="aborted",
    )


def _finish_after_model_response(
    *,
    store: Store,
    turn: JSONDict,
    context: ToolContext,
    active_epic_id: str | None,
    state_before: str,
    body_before: str | None,
    checklist_before: list[JSONDict],
    tool_calls_this_turn: list[EndOfTurnToolCall],
    reply_buffer: list[str],
    events: list[Event],
    final_text: str | None,
    initial_user_prompt: str,
) -> Envelope:
    body_after = _current_body(store, active_epic_id)
    checklist_after = (
        store.list_checklist_items(active_epic_id)
        if active_epic_id is not None
        else []
    )
    decision = evaluate_end_of_turn(
        user_message=initial_user_prompt,
        response_text=final_text,
        reply_sent=bool(reply_buffer),
        tool_calls=tool_calls_this_turn,
        body_before=body_before,
        body_after=body_after,
        checklist_before=checklist_before,
        checklist_after=checklist_after,
    )

    if decision.should_error_empty_response:
        _log_end_of_turn_findings(
            store=store,
            turn_id=str(turn["id"]),
            epic_id=active_epic_id,
            findings=decision.findings,
        )
        store.update_turn(turn["id"], status="failed", reasoning="model returned no action")
        return _envelope(
            turn_id=turn["id"],
            epic_id=active_epic_id,
            state_before=state_before,
            state_after=state_before,
            reply_buffer=reply_buffer,
            events=events,
            outcome="errored",
            error=EnvelopeError(
                code="empty_model_response",
                message="Model returned neither final text nor tool requests.",
                retryable=True,
            ),
        )

    outbound_text = (final_text or "").strip()
    if not outbound_text and decision.should_send_default_acknowledgment:
        outbound_text = DEFAULT_END_OF_TURN_ACKNOWLEDGMENT
    if outbound_text:
        outbound_text = ensure_reframing_suggestion(
            outbound_text,
            tool_calls=tool_calls_this_turn,
            low_score_details=context.metadata.get("low_second_opinion"),
        )

    if outbound_text and not reply_buffer:
        invocation = registry.invoke(
            "send_message",
            context,
            {"content": outbound_text},
        )
        tool_calls_this_turn.append(_end_of_turn_tool_call(invocation.tool_call))
        active_epic_id = context.metadata.get("epic_id", active_epic_id)

    _log_end_of_turn_findings(
        store=store,
        turn_id=str(turn["id"]),
        epic_id=active_epic_id,
        findings=decision.findings,
    )
    store.update_turn(turn["id"], status="completed")
    _log_epic_outline_if_needed(store, active_epic_id, turn, events)
    return _envelope(
        turn_id=turn["id"],
        epic_id=active_epic_id,
        state_before=state_before,
        state_after=_current_state(store, active_epic_id, state_before),
        reply_buffer=reply_buffer,
        events=events,
        outcome="completed",
        state_delta=_state_delta(
            body_before,
            body_after,
            checklist_before,
            checklist_after,
            tool_calls_this_turn,
        ),
    )


def _current_body(store: Store, epic_id: str | None) -> str | None:
    if epic_id is None:
        return None
    epic = store.load_epic(epic_id)
    if not epic:
        return None
    return str(epic.get("body") or "")


def _current_state(store: Store, epic_id: str | None, fallback: str) -> str:
    if epic_id is None:
        return fallback
    epic = store.load_epic(epic_id)
    if not epic:
        return fallback
    return str(epic.get("state") or fallback)


def _state_delta(
    body_before: str | None,
    body_after: str | None,
    checklist_before: list[JSONDict],
    checklist_after: list[JSONDict],
    tool_calls: list[EndOfTurnToolCall],
) -> StateDelta:
    body_diff = ""
    if (body_before or "") != (body_after or ""):
        body_diff = body.compute_diff(body_before or "", body_after or "")
    sprint_changes: list[JSONDict] = []
    state_transition: JSONDict | None = None
    for call in tool_calls:
        result = call.result if isinstance(call.result, dict) else {}
        if isinstance(result.get("sprint_changes"), list):
            sprint_changes.extend(result["sprint_changes"])
        if isinstance(result.get("state_transition"), dict):
            state_transition = result["state_transition"]
    return StateDelta(
        body_diff=body_diff,
        checklist_changes=_checklist_delta(checklist_before, checklist_after),
        sprint_changes=sprint_changes,
        state_transition=state_transition,
    )


def _checklist_delta(before: list[JSONDict], after: list[JSONDict]) -> list[JSONDict]:
    before_by_id = {str(item.get("id")): item for item in before}
    after_ids = {str(item.get("id")) for item in after}
    changes: list[JSONDict] = []
    for item in after:
        item_id = str(item.get("id"))
        previous = before_by_id.get(item_id)
        if previous is None:
            changes.append({"kind": "added", "id": item_id, "status": item.get("status")})
        elif previous.get("status") != item.get("status"):
            changes.append(
                {
                    "kind": "status",
                    "id": item_id,
                    "from": previous.get("status"),
                    "to": item.get("status"),
                }
            )
    for item_id in before_by_id:
        if item_id not in after_ids:
            changes.append({"kind": "deleted", "id": item_id})
    return changes


def _end_of_turn_tool_call(tool_call: JSONDict) -> EndOfTurnToolCall:
    return EndOfTurnToolCall(
        name=str(tool_call.get("tool_name") or ""),
        operation_kind=str(tool_call.get("operation_kind") or ""),
        result=tool_call.get("result") if isinstance(tool_call.get("result"), dict) else {},
    )


def _log_end_of_turn_findings(
    *,
    store: Store,
    turn_id: str,
    epic_id: str | None,
    findings: Sequence[object],
) -> None:
    for finding in findings:
        category = getattr(finding, "category", "unknown")
        message = getattr(finding, "message", "End-of-turn check finding.")
        details = getattr(finding, "details", {})
        store.log_system_event(
            level="warn",
            category="system",
            event_type=f"end_of_turn_{category}",
            message=str(message),
            details=details if isinstance(details, dict) else {},
            turn_id=turn_id,
            epic_id=epic_id,
        )


def _envelope(
    *,
    turn_id: str,
    epic_id: str | None,
    state_before: str,
    state_after: str,
    reply_buffer: list[str],
    events: list[Event],
    outcome: str,
    questions: list[str] | None = None,
    error: EnvelopeError | None = None,
    state_delta: StateDelta | None = None,
) -> Envelope:
    return Envelope(
        turn_id=turn_id,
        epic_id=epic_id,
        epic_state_before=state_before,
        epic_state_after=state_after,
        reply="\n\n".join(reply_buffer),
        state_delta=state_delta or StateDelta(),
        questions=questions or [],
        events=events,
        tool_call_count=sum(1 for event in events if event.tool_call_id),
        outcome=outcome,  # type: ignore[arg-type]
        error=error,
    )


def _is_cancelled(cancel_event: ThreadingEvent | None) -> bool:
    return bool(cancel_event and cancel_event.is_set())


def _messages_prompt(message_rows: Sequence[JSONDict]) -> str:
    ordered = sorted(message_rows, key=lambda row: row.get("sent_at") or "")
    return "\n\n".join(str(row.get("content") or "") for row in ordered)


def _append_mid_turn_messages(
    *,
    store: Store,
    turn: JSONDict,
    messages: list[JSONDict],
    mid_turn_message_check: Callable[[JSONDict], list[JSONDict] | None] | None,
) -> JSONDict | None:
    if mid_turn_message_check is None:
        return None

    new_rows = mid_turn_message_check(turn) or []
    existing_ids = list(turn.get("triggered_by_message_ids") or [])
    existing_id_set = set(existing_ids)
    fresh_rows = [
        row for row in new_rows
        if row.get("id") is not None and row.get("id") not in existing_id_set
    ]
    if not fresh_rows:
        return None

    ordered = sorted(fresh_rows, key=lambda row: row.get("sent_at") or "")
    new_ids = [str(row["id"]) for row in ordered]
    messages.append(
        {
            "role": "user",
            "content": _mid_turn_prompt(ordered),
        }
    )
    return store.update_turn(
        turn["id"],
        triggered_by_message_ids=existing_ids + new_ids,
    )


def _mid_turn_prompt(message_rows: Sequence[JSONDict]) -> str:
    lines = ["[Mid-turn messages — arrived after this turn started]"]
    for row in message_rows:
        content = str(row.get("content") or "")
        sent_at = row.get("sent_at")
        prefix = f"- {sent_at}: " if sent_at else "- "
        lines.append(prefix + content)
    return "\n".join(lines)


def _tool_result_content(tool_name: str, result: JSONDict) -> JSONDict | list[JSONDict]:
    if result.get("media_type") and result.get("image_bytes_b64"):
        metadata = {
            key: value
            for key, value in result.items()
            if key != "image_bytes_b64"
        }
        return [
            {
                "type": "text",
                "text": f"Tool result from {tool_name}:",
            },
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": result["media_type"],
                    "data": result["image_bytes_b64"],
                },
            },
            {
                "type": "text",
                "text": json.dumps(metadata, sort_keys=True),
            },
        ]
    return {
        "tool_name": tool_name,
        "result": result,
    }


def _log_epic_outline_if_needed(
    store: Store,
    active_epic_id: str | None,
    turn: JSONDict,
    events: list[Event],
) -> None:
    if active_epic_id is None:
        return
    if not any(
        event.name in {"create_epic", "edit_epic", "revert"}
        and event.tool_call_id is not None
        for event in events
    ):
        return
    epic = store.load_epic(active_epic_id)
    if not epic:
        return
    parsed = body.parse(str(epic.get("body") or ""))
    details = body.outline(parsed)
    store.log_system_event(
        level="info",
        category="application",
        event_type="epic_outline",
        message=f"Epic outline: {parsed.title or '(untitled)'}",
        details=details,
        turn_id=turn["id"],
        epic_id=active_epic_id,
    )


def _summarize_hot_context(hot_context: dict) -> dict:
    epic = hot_context.get("epic") or {}
    return {
        "epic_id": epic.get("id"),
        "epic_state": epic.get("state"),
        "recent_message_count": len(hot_context.get("recent_messages", [])),
        "recent_tool_call_count": len(hot_context.get("recent_tool_calls", [])),
        "active_feedback_count": len(hot_context.get("active_feedback", [])),
        "unresolved_observation_count": len(hot_context.get("unresolved_observations", [])),
        "sprint_count": len(hot_context.get("sprints", [])),
        "all_sprints_pending_no_queued": bool(hot_context.get("all_sprints_pending_no_queued")),
    }
