"""Shared helpers for DBStore slice mixins."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import Any

_JSONB_WRAPPER: Any = None


def _jb(value: Any) -> Any:
    """Wrap a Python dict/list for JSONB column insertion."""
    if value is None:
        return None
    if _JSONB_WRAPPER is not None:
        return _JSONB_WRAPPER(value)
    return value


def _parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


_PLAN_COLUMNS = (
    "id", "name", "epic_id", "sprint_id", "revision", "idea", "current_state",
    "iteration", "config", "sessions", "plan_versions", "history", "meta",
    "last_gate", "active_step", "clarification", "latest_finalize",
    "latest_review", "latest_execution", "latest_failure", "resume_cursor",
    "feedback", "created_at", "updated_at",
)
_PLAN_JSONB = frozenset({
    "config", "sessions", "plan_versions", "history", "meta", "last_gate",
    "active_step", "clarification", "latest_finalize", "latest_review",
    "latest_execution", "latest_failure", "resume_cursor", "feedback",
})
_ARTIFACT_VALID_FIELDS = frozenset({
    "name", "kind", "role", "version", "batch", "phase",
    "content_text", "content_base64", "sha256", "created_at", "updated_at",
})

_MIGRATION_RUN_COLUMNS = (
    "id", "epic_id", "source_backend", "target_backend", "phase", "manifest",
    "copied_ids", "blob_copy_progress", "started_at", "updated_at",
    "completed_at", "holder_id", "expires_at",
)
_MIGRATION_RUN_JSONB = frozenset({"manifest", "copied_ids", "blob_copy_progress"})

_COPY_TABLE_COLUMNS: dict[str, frozenset[str]] = {
    "automation_actors": frozenset({"id", "name", "granted_epic_ids", "actor_kind", "created_at", "last_active_at"}),
    "bot_turns": frozenset({"id", "epic_id", "triggered_by_message_ids", "prompt_snapshot", "prompt_version", "state_at_turn", "status", "started_at", "completed_at", "model_version", "warnings_issued"}),
    "checklist_items": frozenset({"id", "epic_id", "content", "status", "position", "source", "skip_reason", "superseded_by_item_id", "created_at", "completed_at"}),
    "code_artifacts": frozenset({"id", "codebase_id", "epic_id", "kind", "source", "file_path", "line_range", "scope", "content", "content_summary", "metadata", "created_at", "last_used_at", "expires_at"}),
    "codebases": frozenset({"id", "owner", "name", "repo_url", "repo_workspace", "default_branch", "scope", "group_name", "associated_epic_id", "root_commit_sha", "added_at", "added_via", "last_accessed_at", "verified_accessible_at", "notes"}),
    "control_messages": frozenset({"id", "epic_id", "actor_id", "intent", "target_id", "payload", "idempotency_key", "created_at", "processor_id", "claimed_at", "processed_at", "result"}),
    "cloud_runs": frozenset({"id", "operation", "status", "conversation_id", "epic_id", "sprint_id", "plan_id", "provider", "provider_run_id", "target_id", "command_summary", "progress_summary", "last_status", "metadata", "idempotency_key", "started_by_actor_id", "started_at", "last_checked_at", "completed_at", "created_at", "updated_at"}),
    "epic_events": frozenset({
        "id", "epic_id", "transaction_id", "event_type", "summary",
        "prior_state", "pre_state", "post_state",
        "pre_state_canonical_json", "post_state_canonical_json",
        "pre_state_sha256", "post_state_sha256", "turn_id", "occurred_at",
    }),
    "epics": frozenset({"id", "title", "goal", "body", "state", "home_backend", "migrated_to", "revision", "created_at", "last_edited_at"}),
    "external_requests": frozenset({"id", "idempotency_key", "provider", "endpoint", "tool_call_id", "turn_id", "request_summary", "request_body", "status", "provider_request_id", "provider_response_summary", "attempt_count", "first_attempted_at", "last_attempted_at", "completed_at", "error_details"}),
    "feedback": frozenset({"id", "kind", "content", "source", "source_message_id", "epic_id", "turn_id", "context_snapshot", "active", "deactivation_reason", "resolved", "resolution_note", "resolved_at", "created_at", "last_referenced_at", "last_applied_at"}),
    "images": frozenset({
        "id", "epic_id", "source", "prompt", "storage_url", "quality", "size",
        "created_at", "reference_key", "description", "caption", "in_body",
        "active", "discord_attachment_id", "blob_backend", "blob_id",
        "blob_sha256", "blob_size_bytes", "content_type",
    }),
    "messages": frozenset({"id", "epic_id", "conversation_id", "idempotency_key", "direction", "content", "discord_message_id", "discord_reply_provenance", "bot_turn_id", "has_code_attachment", "has_image_attachment", "in_burst_with", "was_voice_message", "audio_storage_url", "transcription_metadata", "sent_at"}),
    "plan_artifacts": frozenset({
        "plan_id", "name", "kind", "role", "version", "batch", "phase",
        "content_text", "content_bytes", "sha256", "created_at", "updated_at",
    }),
    "plans": frozenset(_PLAN_COLUMNS),
    "progress_events": frozenset({"id", "epic_id", "plan_id", "sprint_id", "idempotency_key", "kind", "summary", "details", "occurred_at"}),
    "resident_conversations": frozenset({"id", "transport", "conversation_key", "active_epic_id", "guild_id", "channel_id", "thread_id", "dm_user_id", "last_inbound_message_id", "last_outbound_message_id", "delivery_cursor", "metadata", "created_at", "updated_at", "last_active_at"}),
    "resident_user_preferences": frozenset({"transport", "user_id", "timezone_name", "metadata", "created_at", "updated_at"}),
    "scheduled_jobs": frozenset({"id", "job_type", "status", "conversation_id", "cloud_run_id", "epic_id", "payload", "scheduled_for", "attempt_count", "max_attempts", "claimed_by", "claimed_at", "fired_at", "cancelled_at", "last_error", "created_at", "updated_at"}),
    "second_opinions": frozenset({"id", "epic_id", "requested_at", "requested_by", "focus_areas", "raw_response", "score", "summary", "verdict", "resulting_checklist_item_ids", "model_used"}),
    "sprint_items": frozenset({"id", "sprint_id", "content", "estimated_complexity", "status", "source_section", "position", "created_at"}),
    "sprints": frozenset({"id", "epic_id", "sprint_number", "name", "goal", "status", "queue_position", "pending_reason", "target_weeks", "revision", "created_at", "updated_at", "queued_at"}),
    "system_logs": frozenset({"id", "level", "category", "event_type", "message", "details", "turn_id", "epic_id", "occurred_at"}),
    "ticket_epics": frozenset({
        "ticket_id", "epic_id", "resolves_on_complete", "kind", "provenance", "linked_at",
    }),
    "tickets": frozenset({"id", "codebase_id", "title", "body", "status", "source", "tags", "filed_by_actor_id", "filed_in_turn_id", "slug", "created_at", "last_edited_at", "resolution_note", "addressed_at"}),
    "tool_calls": frozenset({"id", "turn_id", "tool_name", "operation_kind", "arguments", "result", "duration_ms", "called_at"}),
}
_COPY_JSONB_COLUMNS = frozenset({
    "active_step", "arguments", "blob_copy_progress", "clarification", "config",
    "context_snapshot", "copied_ids", "details", "error_details", "focus_areas",
    "granted_epic_ids", "history", "in_burst_with", "last_gate", "last_status",
    "feedback", "latest_execution", "latest_failure", "latest_finalize", "latest_review",
    "line_range", "manifest", "meta", "metadata", "payload",
    "plan_versions", "post_state", "pre_state", "prior_state", "prompt_snapshot",
    "provider_response_summary", "request_body", "request_summary", "result",
    "resulting_checklist_item_ids", "sessions", "state_at_turn",
    "discord_reply_provenance", "transcription_metadata", "triggered_by_message_ids", "warnings_issued",
})
_SOURCE_REFERENCE_PREFIX = {
    "user_uploaded": "img_user_upload",
    "caller_uploaded": "img_caller_upload",
    "agent_generated": "img_agent_generated",
}
_OBSERVATION_KINDS = frozenset({"friction", "ambiguity", "tool_failure", "confusion", "pattern_noticed"})


class _DBTransaction:
    """Thin wrapper yielded by DBStore.transaction().

    The actual psycopg transaction is managed by the surrounding
    conn.transaction() context manager; this object just satisfies
    the Transaction protocol so callers can type-annotate correctly.
    """

    def __enter__(self) -> _DBTransaction:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        pass


__all__ = [
    "_ARTIFACT_VALID_FIELDS",
    "_COPY_JSONB_COLUMNS",
    "_COPY_TABLE_COLUMNS",
    "_DBTransaction",
    "_MIGRATION_RUN_COLUMNS",
    "_MIGRATION_RUN_JSONB",
    "_OBSERVATION_KINDS",
    "_PLAN_COLUMNS",
    "_PLAN_JSONB",
    "_SOURCE_REFERENCE_PREFIX",
    "_jb",
    "_parse_datetime",
]
