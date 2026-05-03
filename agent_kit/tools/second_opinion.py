"""Second-opinion tool."""

from __future__ import annotations

from typing import Any

from agent_kit.openai_ops import SECOND_OPINION_MODEL
from agent_kit.second_opinion import (
    build_second_opinion_payload,
    parse_second_opinion,
    proposed_checklist_items,
)
from agent_kit.tool_kit import ExternalSpec, ToolContext, register_tool, run_synchronous_external_effect


REQUEST_SECOND_OPINION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["epic_id"],
    "properties": {
        "epic_id": {"type": "string"},
        "focus_areas": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "scoring_override": {"type": ["string", "null"]},
        "requested_by": {
            "type": ["string", "null"],
            "enum": ["user", "auto_state_gate", None],
        },
    },
}


@register_tool(
    "request_second_opinion",
    schema=REQUEST_SECOND_OPINION_SCHEMA,
    event_kind="tool_call",
    operation_kind="write",
)
def request_second_opinion(
    context: ToolContext,
    epic_id: str,
    focus_areas: list[str] | None = None,
    scoring_override: str | None = None,
    requested_by: str | None = None,
) -> dict[str, Any]:
    if context.openai_ops is None:
        raise ValueError("request_second_opinion requires openai_ops")
    if requested_by is None:
        requested_by = "user"
    if requested_by not in {"user", "auto_state_gate"}:
        raise ValueError("requested_by must be user or auto_state_gate")
    epic = context.store.load_epic(epic_id)
    if not epic:
        raise ValueError(f"epic not found: {epic_id}")
    normalized_focus = [str(item).strip() for item in focus_areas or [] if str(item).strip()]
    checklist = context.store.list_checklist_items(epic_id)
    sprints = context.store.list_sprints_with_items(epic_id)
    recent_feedback = context.store.list_feedback(
        epic_id=epic_id,
        active=True,
        kinds=None,
        limit=8,
    )
    payload = build_second_opinion_payload(
        epic=epic,
        checklist=checklist,
        sprints=sprints,
        recent_feedback=recent_feedback,
        focus_areas=normalized_focus,
        scoring_override=scoring_override,
    )
    result = run_synchronous_external_effect(
        context,
        ExternalSpec(
            provider="openai",
            endpoint=f"responses.create:{SECOND_OPINION_MODEL}",
            request_summary={
                "epic_id": epic_id,
                "focus_areas": normalized_focus,
                "requested_by": requested_by,
                "model": SECOND_OPINION_MODEL,
            },
            request_body={
                "model": SECOND_OPINION_MODEL,
                "payload": payload,
            },
        ),
        lambda idempotency_key: _call_second_opinion(context, payload, idempotency_key),
    )
    openai_result = result.result
    parsed = parse_second_opinion(openai_result.raw_response)
    row = context.store.create_second_opinion(
        epic_id=epic_id,
        requested_by=requested_by,
        focus_areas=normalized_focus,
        raw_response=openai_result.raw_response,
        score=parsed.score,
        summary=parsed.summary,
        verdict=parsed.verdict,
        model_used=SECOND_OPINION_MODEL,
    )
    proposed_items = proposed_checklist_items(
        parsed.holes,
        source_second_opinion_id=row["id"],
    )
    context.metadata["second_opinion_requested_this_turn"] = True
    if parsed.score < 5:
        context.metadata["low_second_opinion"] = {
            "second_opinion_id": row["id"],
            "score": parsed.score,
            "verdict": parsed.verdict,
            "summary": parsed.summary,
        }
    return {
        "second_opinion_id": row["id"],
        "score": parsed.score,
        "summary": parsed.summary,
        "verdict": parsed.verdict,
        "strengths": parsed.strengths,
        "holes": parsed.holes,
        "proposed_checklist_items": proposed_items,
        "openai_external_request_id": result.request_id,
        "openai_provider_request_id": result.provider_request_id,
        "model_used": SECOND_OPINION_MODEL,
    }


def _call_second_opinion(
    context: ToolContext,
    payload: dict[str, Any],
    idempotency_key: str,
):
    result = context.openai_ops.request_second_opinion(  # type: ignore[union-attr]
        payload=payload,
        idempotency_key=idempotency_key,
    )
    return (
        result.provider_request_id,
        result.response_summary,
        result,
    )


__all__ = ["request_second_opinion"]
