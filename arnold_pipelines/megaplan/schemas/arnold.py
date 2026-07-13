"""Pydantic mirrors of the Arnold Supabase tables."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from .base import (
    HomeBackend,
    NormalizedDict,
    NormalizedList,
    NormalizedStringList,
    StorageModel,
    utc_now,
)

EpicState = Literal["shaping", "sprinting", "planned", "paused", "archived"]
ARNOLD_EPIC_STATES: tuple[str, ...] = ("shaping", "sprinting", "planned", "paused", "archived")
ARNOLD_TO_MEGAPLAN_EPIC_STATE: dict[str, str] = {state: state for state in ARNOLD_EPIC_STATES}


def map_arnold_epic_state(state: str) -> EpicState:
    """Return the Megaplan epic state for an Arnold editorial state."""
    try:
        return ARNOLD_TO_MEGAPLAN_EPIC_STATE[state]  # type: ignore[return-value]
    except KeyError as exc:
        raise ValueError(f"Unsupported Arnold epic state: {state}") from exc
BotTurnStatus = Literal["in_progress", "completed", "failed", "abandoned"]
MessageDirection = Literal["inbound", "outbound"]
ResidentConversationTransport = Literal["discord"]
ToolOperationKind = Literal["read", "write", "cloud_read", "cloud_start", "control"]
SystemLogLevel = Literal["debug", "info", "warn", "error"]
SystemLogCategory = Literal["system", "application", "tool", "llm", "external_api", "recovery"]
ExternalRequestProvider = Literal["anthropic", "openai", "groq", "github", "discord", "supabase_storage"]
ExternalRequestStatus = Literal["pending", "sent", "confirmed", "failed", "orphaned"]
ImageSource = Literal["agent_generated", "user_uploaded", "caller_uploaded"]
ChecklistStatus = Literal["open", "done", "skipped", "superseded"]
ChecklistSource = Literal["bot_inferred", "user_requested", "carried_over", "default_seed", "second_opinion"]
EpicEventType = Literal[
    "body_edit",
    "checklist_change",
    "sprints_change",
    "state_change",
    "forced_handoff",
    "created",
    "code_referenced",
    "codebase_added",
    "image_generated",
    "second_opinion_requested",
    "reverted_to",
    "sprint_status_change",
]
FeedbackKind = Literal[
    "style",
    "process",
    "epic_specific",
    "friction",
    "ambiguity",
    "tool_failure",
    "confusion",
    "pattern_noticed",
]
FeedbackSource = Literal[
    "user_volunteered",
    "agent_proposed_user_confirmed",
    "explicit_save_request",
    "agent_observation",
]
SprintStatus = Literal["proposed", "queued", "pending", "running", "done", "failed", "blocked", "cancelled"]
SprintItemComplexity = Literal["small", "medium", "large"]
SprintItemStatus = Literal["open", "in_progress", "done"]
SecondOpinionRequester = Literal["user", "auto_state_gate"]
CodebaseScope = Literal["global", "epic_specific"]
CodeArtifactKind = Literal["excerpt", "summary", "api_cache"]
CodeArtifactSource = Literal["conversation", "codebase"]
CodeArtifactScope = Literal["file", "directory", "cross_codebase"]


class Epic(StorageModel):
    id: str
    title: str
    goal: str
    body: str
    state: EpicState
    home_backend: HomeBackend = "file"
    migrated_to: str | None = None
    revision: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    last_edited_at: datetime = Field(default_factory=utc_now)
    last_active_at: datetime | None = None
    planned_at: datetime | None = None


class BotTurn(StorageModel):
    id: str
    epic_id: str | None = None
    triggered_by_message_ids: NormalizedStringList = Field(default_factory=list)
    prompt_snapshot: NormalizedDict | None = None
    prompt_version: str | None = None
    reasoning: str | None = None
    final_output_message_id: str | None = None
    status_message_id: str | None = None
    status: BotTurnStatus
    state_at_turn: NormalizedDict | None = None
    plan_edited: bool = False
    code_consulted: bool = False
    image_generated: bool = False
    second_opinion_requested: bool = False
    message_sent: bool = False
    warnings_issued: NormalizedList | None = None
    current_activity: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    model_version: str | None = None


class ResidentConversation(StorageModel):
    id: str
    transport: ResidentConversationTransport = "discord"
    conversation_key: str
    active_epic_id: str | None = None
    guild_id: str | None = None
    channel_id: str | None = None
    thread_id: str | None = None
    dm_user_id: str | None = None
    last_inbound_message_id: str | None = None
    last_outbound_message_id: str | None = None
    delivery_cursor: str | None = None
    metadata: NormalizedDict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_active_at: datetime | None = None


class ResidentUserPreference(StorageModel):
    """Durable presentation preferences for one transport user identity."""

    transport: ResidentConversationTransport = "discord"
    user_id: str
    timezone_name: str | None = None
    metadata: NormalizedDict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Message(StorageModel):
    id: str
    epic_id: str | None = None
    conversation_id: str | None = None
    idempotency_key: str | None = None
    direction: MessageDirection
    content: str
    sent_at: datetime = Field(default_factory=utc_now)
    discord_message_id: str | None = None
    # Immutable transport provenance captured when a Discord inbound message is
    # first accepted.  Reply ancestry belongs to the source message record; it
    # must never be reconstructed from a recent-history excerpt.
    discord_reply_provenance: NormalizedDict | None = None
    has_code_attachment: bool = False
    has_image_attachment: bool = False
    in_burst_with: NormalizedStringList | None = None
    was_voice_message: bool = False
    audio_storage_url: str | None = None
    transcription_metadata: NormalizedDict | None = None
    bot_turn_id: str | None = None


class ToolCall(StorageModel):
    id: str
    turn_id: str
    tool_name: str
    operation_kind: ToolOperationKind
    arguments: NormalizedDict = Field(default_factory=dict)
    result: NormalizedDict = Field(default_factory=dict)
    called_at: datetime = Field(default_factory=utc_now)
    duration_ms: int = Field(default=0, ge=0)


class SystemLog(StorageModel):
    id: str
    level: SystemLogLevel
    category: SystemLogCategory
    event_type: str
    message: str
    details: NormalizedDict = Field(default_factory=dict)
    turn_id: str | None = None
    epic_id: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class EpicLock(StorageModel):
    epic_id: str
    holder_id: str
    acquired_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class ExternalRequest(StorageModel):
    id: str
    idempotency_key: str
    provider: ExternalRequestProvider
    endpoint: str
    tool_call_id: str | None = None
    turn_id: str | None = None
    request_summary: NormalizedDict = Field(default_factory=dict)
    request_body: NormalizedDict | None = None
    status: ExternalRequestStatus
    provider_request_id: str | None = None
    provider_response_summary: NormalizedDict | None = None
    attempt_count: int = Field(default=1, ge=1)
    first_attempted_at: datetime = Field(default_factory=utc_now)
    last_attempted_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    error_details: NormalizedDict | None = None


class Image(StorageModel):
    id: str
    epic_id: str | None = None
    source: ImageSource
    prompt: str | None = None
    storage_url: str
    quality: str | None = None
    size: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    reference_key: str
    description: str | None = None
    caption: str | None = None
    in_body: bool = False
    active: bool = True
    discord_attachment_id: str | None = None
    blob_backend: str | None = None
    blob_id: str | None = None
    blob_sha256: str | None = None
    blob_size_bytes: int | None = Field(default=None, ge=0)
    content_type: str | None = None


class ChecklistItem(StorageModel):
    id: str
    epic_id: str
    content: str
    status: ChecklistStatus | None = None
    position: int = Field(gt=0)
    source: ChecklistSource | None = None
    skip_reason: str | None = None
    superseded_by_item_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class EpicEvent(StorageModel):
    id: str
    epic_id: str
    transaction_id: str
    event_type: EpicEventType | None = None
    summary: str
    prior_state: NormalizedDict | None = None
    pre_state: NormalizedDict | None = None
    post_state: NormalizedDict | None = None
    pre_state_canonical_json: str | None = None
    post_state_canonical_json: str | None = None
    pre_state_sha256: str | None = None
    post_state_sha256: str | None = None
    turn_id: str | None = None
    occurred_at: datetime = Field(default_factory=utc_now)


class EpicSnapshot(StorageModel):
    epic_id: str
    revision: int
    epic: NormalizedDict
    body: str
    checklist_items: NormalizedList = Field(default_factory=list)
    sprints: NormalizedList = Field(default_factory=list)
    sprint_items: NormalizedList = Field(default_factory=list)
    images: NormalizedList = Field(default_factory=list)
    second_opinions: NormalizedList = Field(default_factory=list)
    search_document: str | None = None


class EpicSummary(Epic):
    snippet: str | None = None
    rank: float | int | None = None
    match_tier: int | None = None
    backend: HomeBackend | None = None


EpicSearchSummary = EpicSummary


class Feedback(StorageModel):
    id: str
    kind: FeedbackKind
    content: str
    source: FeedbackSource
    source_message_id: str | None = None
    epic_id: str | None = None
    turn_id: str | None = None
    context_snapshot: NormalizedDict | None = None
    active: bool = True
    deactivation_reason: str | None = None
    resolved: bool = False
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    last_referenced_at: datetime | None = None
    last_applied_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_kind_source(self) -> Feedback:
        user_kinds = {"style", "process", "epic_specific"}
        user_sources = {
            "user_volunteered",
            "agent_proposed_user_confirmed",
            "explicit_save_request",
        }
        observation_kinds = {
            "friction",
            "ambiguity",
            "tool_failure",
            "confusion",
            "pattern_noticed",
        }
        if self.kind in user_kinds and self.source not in user_sources:
            raise ValueError("user-facing feedback kinds require a user-confirmed source")
        if self.kind in observation_kinds and self.source != "agent_observation":
            raise ValueError("observation feedback kinds require source='agent_observation'")
        return self


class Sprint(StorageModel):
    id: str
    epic_id: str
    sprint_number: int = Field(gt=0)
    name: str
    goal: str
    status: SprintStatus
    revision: int = 0
    queue_position: int | None = Field(default=None, gt=0)
    pending_reason: str | None = None
    target_weeks: int = Field(default=2, gt=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    queued_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_status_fields(self) -> Sprint:
        if self.status == "queued" and self.queue_position is None:
            raise ValueError("queued sprints require queue_position")
        if self.status == "pending" and not self.pending_reason:
            raise ValueError("pending sprints require pending_reason")
        if self.status != "queued" and self.queue_position is not None:
            raise ValueError("queue_position is only valid for queued sprints")
        return self


class SprintItem(StorageModel):
    id: str
    sprint_id: str
    content: str
    estimated_complexity: SprintItemComplexity
    status: SprintItemStatus
    source_section: str | None = None
    position: int = Field(gt=0)
    created_at: datetime = Field(default_factory=utc_now)


class SecondOpinion(StorageModel):
    id: str
    epic_id: str
    requested_at: datetime = Field(default_factory=utc_now)
    requested_by: SecondOpinionRequester
    focus_areas: NormalizedStringList = Field(default_factory=list)
    raw_response: str
    score: int = Field(ge=0, le=10)
    summary: str
    verdict: str
    resulting_checklist_item_ids: NormalizedStringList = Field(default_factory=list)
    model_used: str


class Codebase(StorageModel):
    id: str
    owner: str
    name: str
    repo_url: str | None = None
    repo_workspace: str | None = None
    default_branch: str
    scope: CodebaseScope = "global"
    group_name: str | None = None
    associated_epic_id: str | None = None
    added_at: datetime = Field(default_factory=utc_now)
    added_via: str = "manual"
    last_accessed_at: datetime | None = None
    verified_accessible_at: datetime | None = None
    notes: str | None = None
    root_commit_sha: str | None = None

    @field_validator("owner", "name")
    @classmethod
    def _require_lowercase_identifier(cls, value: str) -> str:
        if not value or value != value.lower():
            raise ValueError("codebase owner and name must be non-empty lowercase strings")
        return value


class Ticket(StorageModel):
    """A repo-scoped note on an issue/problem that may become work."""

    id: str
    codebase_id: str
    title: str
    body: str = ""
    status: str = "open"
    source: str = "human"
    tags: list[str] = Field(default_factory=list)
    filed_by_actor_id: str | None = None
    filed_in_turn_id: str | None = None
    slug: str
    created_at: datetime = Field(default_factory=utc_now)
    last_edited_at: datetime = Field(default_factory=utc_now)
    resolution_note: str | None = None
    addressed_at: datetime | None = None


class TicketEpicLink(StorageModel):
    """Many-to-many join between tickets and epics."""

    ticket_id: str
    epic_id: str
    resolves_on_complete: bool = False
    linked_at: datetime = Field(default_factory=utc_now)


class CodeArtifact(StorageModel):
    id: str
    codebase_id: str | None = None
    epic_id: str | None = None
    kind: CodeArtifactKind
    source: CodeArtifactSource
    file_path: str | None = None
    line_range: NormalizedDict | None = None
    scope: CodeArtifactScope | None = None
    content: str
    content_summary: str | None = None
    metadata: NormalizedDict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


class OutwardProjectionModel(StorageModel):
    """Base for versioned public projections that must tolerate forward keys."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, validate_assignment=True)

    schema_version: int = Field(default=1, ge=1)


class CapsuleDefinition(OutwardProjectionModel):
    identity_hash: str
    static_behavioral_hash: str
    runtime_topology_hash: str | None = None
    pipeline_name: str | None = None
    manifest: NormalizedDict = Field(default_factory=dict)
    intent: NormalizedDict = Field(default_factory=dict)
    routing: NormalizedDict = Field(default_factory=dict)
    ports: NormalizedList = Field(default_factory=list)
    unresolved_static_inputs: NormalizedList = Field(default_factory=list)
    replay_ready: bool = False


class CapsuleContract(OutwardProjectionModel):
    manifest_abi: str
    static_behavioral_hash: str
    runtime_topology_hash: str | None = None
    port_expectations: NormalizedList = Field(default_factory=list)
    evidence_refs: NormalizedList = Field(default_factory=list)
    repo_commit: str | None = None
    model_version_requirements: NormalizedDict = Field(default_factory=dict)
    tool_version_requirements: NormalizedDict = Field(default_factory=dict)
    environment_variable_requirements: NormalizedDict = Field(default_factory=dict)
    secret_shape_declarations: NormalizedDict = Field(default_factory=dict)
    model_requirements: NormalizedDict = Field(default_factory=dict)
    tool_requirements: NormalizedDict = Field(default_factory=dict)
    environment_requirements: NormalizedDict = Field(default_factory=dict)
    secret_shape_requirements: NormalizedDict = Field(default_factory=dict)


class CapsuleLineage(OutwardProjectionModel):
    capsule_hash: str | None = None
    parent_edges: NormalizedList = Field(default_factory=list)
    ancestors: NormalizedStringList = Field(default_factory=list)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class CapsuleEvidence(OutwardProjectionModel):
    evidence_id: str
    evidence_type: str
    payload_ref: NormalizedDict
    payload_sha256: str | None = None
    summary: str | None = None
    metadata: NormalizedDict = Field(default_factory=dict)


CapsuleCompleteness = Literal["complete", "degraded"]


class Capsule(OutwardProjectionModel):
    capsule_hash: str
    definition: CapsuleDefinition
    contract: CapsuleContract
    lineage: CapsuleLineage
    evidence: list[CapsuleEvidence] = Field(default_factory=list)
    completeness: CapsuleCompleteness = "complete"
    replay_ready: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    metadata: NormalizedDict = Field(default_factory=dict)


class WarrantAuthority(OutwardProjectionModel):
    authority_id: str
    policy_envelope: NormalizedDict
    grantor: str | None = None
    autonomy_level: str | None = None
    captured_at: datetime = Field(default_factory=utc_now)


class WarrantAccount(OutwardProjectionModel):
    account_id: str
    verified_work_units: NormalizedList = Field(default_factory=list)
    unit: str = "verified_work"
    verified_result_ref: NormalizedDict
    provider_cost_ref: NormalizedDict | None = None


class WarrantRationaleAnchor(OutwardProjectionModel):
    anchor_id: str
    manifest_hash: str
    rationale_ref: NormalizedDict
    captured_at: datetime = Field(default_factory=utc_now)


class WarrantSignature(OutwardProjectionModel):
    algorithm: str = "hmac-sha256"
    signed_payload_sha256: str
    signature: str
    key_id: str | None = None
    signed_at: datetime = Field(default_factory=utc_now)


class Warrant(OutwardProjectionModel):
    warrant_id: str
    authority: WarrantAuthority
    account: WarrantAccount
    rationale_anchor: WarrantRationaleAnchor
    behavioral_manifest_hash: str
    verified_result_ref: NormalizedDict
    signature: WarrantSignature
    issued_at: datetime = Field(default_factory=utc_now)
    metadata: NormalizedDict = Field(default_factory=dict)


class WarrantSourceCompleteness(OutwardProjectionModel):
    present: NormalizedStringList = Field(default_factory=list)
    missing: NormalizedStringList = Field(default_factory=list)
    unsupported: NormalizedStringList = Field(default_factory=list)
    required_fields: NormalizedStringList = Field(default_factory=list)
    signable: bool = False

    @model_validator(mode="after")
    def _validate_signable_required_fields(self) -> WarrantSourceCompleteness:
        if not self.signable:
            return self
        missing_required = set(self.required_fields) & set(self.missing)
        unsupported_required = set(self.required_fields) & set(self.unsupported)
        if missing_required or unsupported_required:
            raise ValueError("signable warrant sources cannot miss or not support required fields")
        return self


class WarrantSourceProjection(OutwardProjectionModel):
    projection_id: str
    completeness: WarrantSourceCompleteness
    authority: WarrantAuthority | None = None
    account: WarrantAccount | None = None
    rationale_anchor: WarrantRationaleAnchor | None = None
    behavioral_manifest_hash: str | None = None
    verified_result_ref: NormalizedDict | None = None
    source_refs: NormalizedDict = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=utc_now)
