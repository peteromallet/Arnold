"""Megaplan-specific resident bot profile and constrained tool surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field

from arnold_pipelines.megaplan.control import ControlTargetResolver
from arnold_pipelines.megaplan.editorial import body as editorial_body
from arnold_pipelines.megaplan.editorial import checklist as editorial_checklist
from arnold_pipelines.megaplan.editorial import gating as editorial_gating
from arnold_pipelines.megaplan.editorial import sprints as editorial_sprints
from arnold_pipelines.megaplan.store import (
    CloudRunInput,
    ControlMessageInput,
    ProgressEventInput,
    ScheduledJobInput,
    SprintItemInput,
    Store,
    deterministic_idempotency_key,
)
from arnold_pipelines.megaplan.store.export import collect_epic_export, write_epic_export_tar
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan.cloud import status_snapshot
from arnold_pipelines.megaplan.layout import (
    ALLOWED_INITIATIVE_SUBDIRS,
    LAYOUT_POLICY_VERSION,
    classify_initiative_doc_path,
    initiative_compact_index,
    initiative_doc_dir,
    initiative_metadata,
    initiative_root,
    initiatives_dir,
    migrate_legacy_briefs_layout,
    search_initiatives,
    slugify_initiative,
)

from .auth import ActionKind, AuthorizationSubject, ConfirmationManager, ResidentAuthorizer, StoreBackedConfirmationManager
from .cloud import (
    CloudCliBackend,
    CloudOperation,
    CloudToolBackend,
    CloudToolRequest,
    CloudToolResult,
    cloud_run_status_for_classification,
    progress_kind_for_classification,
)
from .config import ResidentConfig
from .tool_registry import ToolRegistration, ToolRegistry
from .tool_schemas import ToolInput, ToolResult
from . import vp_todo
from .subagent import launch_subagent_task

MEGAPLAN_RESIDENT_PROMPT_VERSION = "megaplan-resident-v1"
# The watchdog refreshes the snapshot roughly hourly; tolerate up to two ticks
# of staleness before treating broad status as degraded.
_SNAPSHOT_MAX_AGE_S = 2 * 60 * 60
INITIATIVE_DOC_KIND = Literal["briefs", "research", "decisions", "notes", "assets", "handoff"]


class ActorToolInput(ToolInput):
    actor_user_id: str | None = None
    guild_id: str | None = None
    channel_id: str | None = None


class CreateEpicInput(ActorToolInput):
    title: str
    goal: str
    body: str


class SelectEpicInput(ActorToolInput):
    conversation_id: str
    epic_id: str


class EpicInput(ActorToolInput):
    epic_id: str


class EditEpicBodyInput(EpicInput):
    body: str
    expected_revision: int | None = None


class AddChecklistItemsInput(EpicInput):
    items: list[str] = Field(min_length=1)


class UpdateChecklistItemInput(EpicInput):
    item_id: str
    content: str | None = None
    status: Literal["open", "done", "skipped", "superseded"] | None = None
    position: int | None = Field(default=None, gt=0)
    skip_reason: str | None = None
    superseded_by_item_id: str | None = None


class SprintItemSpec(ToolInput):
    content: str
    estimated_complexity: str = "medium"
    status: str = "open"
    source_section: str | None = None


class SprintSpec(ToolInput):
    sprint_id: str | None = None
    sprint_number: int = Field(gt=0)
    name: str
    goal: str
    target_weeks: int = Field(default=2, gt=0)
    expected_revision: int | None = None
    items: list[SprintItemSpec] = Field(default_factory=list)


class CreateOrUpdateSprintsInput(EpicInput):
    sprints: list[SprintSpec] = Field(min_length=1)


class QueueSprintsInput(EpicInput):
    ordered_sprint_ids: list[str] = Field(default_factory=list)
    pending: dict[str, str] = Field(default_factory=dict)


class TransitionEpicStateInput(EpicInput):
    target_state: Literal["shaping", "sprinting", "planned", "paused", "archived"]
    expected_revision: int | None = None
    force: bool = False


class ControlToolInput(ActorToolInput):
    conversation_id: str | None = None
    epic_id: str
    target_id: str
    project_root: str
    plan: str | None = None
    reason: str | None = None
    note: str | None = None
    auto_continue: bool = False
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class CloudToolInput(ActorToolInput):
    conversation_id: str | None = None
    epic_id: str | None = None
    sprint_id: str | None = None
    plan_id: str | None = None
    cloud_run_id: str | None = None
    project_root: str = "."
    cloud_yaml: str | None = None
    codebase_id: str | None = None
    repo_url: str | None = None
    repo_branch: str | None = None
    repo_workspace: str | None = None


class CloudStatusInput(CloudToolInput):
    plan: str | None = None


class CloudStatusChainInput(CloudToolInput):
    remote_spec: str | None = None


class ConfirmedCloudToolInput(CloudToolInput):
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class CloudStartChainInput(ConfirmedCloudToolInput):
    spec: str
    idea_dir: str | None = None


class CloudBootstrapInput(ConfirmedCloudToolInput):
    idea_file: str
    plan_name: str | None = None
    robustness: str = "standard"


class CloudResumeInput(ConfirmedCloudToolInput):
    plan: str | None = None


class CloudLogsInput(CloudToolInput):
    no_follow: bool = True


class ScheduleCloudCheckInput(CloudToolInput):
    interval_seconds: int = Field(default=60, gt=0)
    scheduled_for: datetime | None = None
    notify_every_check: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1)


class CancelCloudCheckInput(ActorToolInput):
    scheduled_job_id: str


class ListCloudChecksInput(ActorToolInput):
    conversation_id: str | None = None
    cloud_run_id: str | None = None
    epic_id: str | None = None
    status: Literal["pending", "claimed", "fired", "cancelled", "failed"] | None = None
    limit: int = Field(default=10, gt=0, le=50)


class SearchMessagesInput(ActorToolInput):
    query: str = ""
    conversation_id: str | None = None
    epic_id: str | None = None
    limit: int = Field(default=10, gt=0, le=50)


class SearchEpicsInput(ActorToolInput):
    query: str = ""
    state: str | None = None
    limit: int = Field(default=10, gt=0, le=50)


class SearchPlansInput(ActorToolInput):
    query: str = ""
    epic_id: str | None = None
    sprint_id: str | None = None
    limit: int = Field(default=10, gt=0, le=50)


class SearchCodeArtifactsInput(ActorToolInput):
    query: str = ""
    codebase_id: str | None = None
    epic_id: str | None = None
    kind: str | None = None
    source: str | None = None
    file_path: str | None = None
    limit: int = Field(default=10, gt=0, le=50)


class ListCodebasesInput(ActorToolInput):
    scope: str | None = None
    group_name: str | None = None
    epic_id: str | None = None
    include_global: bool = True
    limit: int = Field(default=25, gt=0, le=100)


class RegisterCodebaseInput(ActorToolInput):
    owner: str
    name: str
    repo_url: str
    repo_workspace: str | None = None
    default_branch: str = "main"
    scope: Literal["global", "epic_specific"] = "global"
    group_name: str | None = None
    associated_epic_id: str | None = None
    notes: str | None = None
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class ListReposInput(ListCodebasesInput):
    pass


class ReconcileEpicInput(EpicInput):
    apply: bool = False
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class ReconcilePlanStorageInput(ActorToolInput):
    plan_id: str | None = None
    epic_id: str | None = None
    apply: bool = False
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class PlanArtifactInput(ActorToolInput):
    plan_id: str
    name: str


class ReadPlanArtifactInput(PlanArtifactInput):
    max_bytes: int = Field(default=65536, gt=0, le=262144)


class WritePlanArtifactInput(PlanArtifactInput):
    content_text: str
    kind: str | None = None
    role: str | None = None
    expected_revision: int | None = None
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class InitiativeToolInput(ActorToolInput):
    project_root: str = "."


class ListInitiativesInput(InitiativeToolInput):
    limit: int = Field(default=50, gt=0, le=200)


class SearchInitiativesInput(InitiativeToolInput):
    query: str = Field(min_length=1)
    keywords_all: bool = False
    limit: int = Field(default=10, gt=0, le=50)


class CreateInitiativeInput(InitiativeToolInput):
    slug: str
    title: str | None = None
    description: str = Field(min_length=1)
    north_star: str | None = None
    create_chain: bool = False


class ReadInitiativeInput(InitiativeToolInput):
    slug: str
    max_docs: int = Field(default=25, gt=0, le=100)


class WriteInitiativeDocInput(InitiativeToolInput):
    initiative_slug: str
    doc_kind: INITIATIVE_DOC_KIND
    filename: str
    content_text: str
    create_if_missing: bool = True
    overwrite: bool = False


class ClassifyInitiativeDocInput(ToolInput):
    path: str


class MigrateInitiativeLayoutInput(InitiativeToolInput):
    apply: bool = False


class ExportEpicBundleInput(EpicInput):
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class ArchiveCloudLogsInput(ActorToolInput):
    cloud_run_id: str
    plan_id: str | None = None
    project_root: str = "."
    cloud_yaml: str | None = None
    no_follow: bool = True
    confirmation_request_id: str | None = None
    confirmation_phrase: str | None = None


class ReadTodoListInput(ToolInput):
    """Read the VP special-requests to-do list (no arguments)."""


class CompleteTodoItemInput(ToolInput):
    id: str
    result: str = ""


class FailTodoItemInput(ToolInput):
    id: str
    reason: str = ""


class AddTodoItemInput(ToolInput):
    task: str
    when: str = ""


class LaunchSubagentInput(ToolInput):
    task: str
    toolsets: str | None = None
    project_dir: str | None = None


@dataclass
class MegaplanResidentProfile:
    """Megaplan-specific prompt, context, and constrained tool surface."""

    store: Store | None = None
    authorizer: ResidentAuthorizer | None = None
    config: ResidentConfig = field(default_factory=ResidentConfig)
    confirmation_manager: ConfirmationManager | None = None
    cloud_backend: CloudToolBackend = field(default_factory=CloudCliBackend)
    actor_id: str = "resident-bot"
    tool_registry: ToolRegistry = field(default_factory=ToolRegistry)
    _registered_default_tools: bool = False

    def __post_init__(self) -> None:
        if self.confirmation_manager is None:
            self.confirmation_manager = (
                StoreBackedConfirmationManager(self.config, self.store)
                if self.store is not None
                else ConfirmationManager(self.config)
            )
        if self.store is not None and not self._registered_default_tools:
            self._register_default_tools()
            self._registered_default_tools = True

    def system_prompt(self) -> str:
        return (
            "You are the resident Megaplan operator. Shape epics through Megaplan "
            "editorial tools, report cloud status through constrained cloud tools, "
            "ask for human input when gates or ambiguity require it, and do not "
            "run arbitrary remote shell commands. Durable planning assets use "
            f"{LAYOUT_POLICY_VERSION}: create or update project material under "
            ".megaplan/initiatives/<slug>/ only. Put executable chain specs at "
            "chain.yaml, milestone briefs in briefs/, research in research/, "
            "decisions in decisions/, notes in notes/, assets in assets/, and "
            "handoffs in handoff/. Never create planning docs directly under "
            ".megaplan/briefs. Use tickets/ only for backlog/issues and plans/ "
            "only for generated runtime state. If a project or epic does not "
            "exist yet, search initiatives by rough slug/title/description first; "
            "reuse the closest existing initiative when it matches before creating a new one."
            " You also keep a VP special-requests to-do list (the `*_todo_item` tools). "
            "When the user asks you to queue a recurring task or special request, add it with "
            "`add_todo_item` (optionally a `when` condition, e.g. 'once epic <id> is done'); use "
            "`read_todo_list` to show what's queued. In conversation you add and read items — a "
            "scheduled sweep picks up pending items and executes them with `launch_subagent`."
            " For broad status questions ('how's it going?', 'what is active?', 'is it cooking?', "
            "'why did it not reply?'), answer from `cloud_status_snapshot` / `plan_activity_summary` "
            "in hot context FIRST. That snapshot is the canonical shared-runner view produced by the "
            "watchdog; cite its generated_at timestamp. If `cloud_status_degraded` is set or the "
            "snapshot is missing/stale, say so explicitly before using `local_epic_chain_state` or "
            "`live_cloud_chain` as fallback — and label that fallback as degraded, not full cloud "
            "status. When a snapshot session carries a `progress` block, lead with the active "
            "epic's overall percent — e.g. 'Epic X: <progress.percent>% (A/B sprints done), currently "
            "on <current_plan>'. `progress.percent` already folds the in-flight plan's stage fraction "
            "in, so it advances as the current plan progresses rather than freezing between milestones. "
            "When `progress.plan_percent` is present, also append the in-flight plan's stage estimate, "
            "e.g. '...; in-flight <plan_percent>% (<plan_state>)'; if `plan_state` is present without "
            "a `plan_percent` (e.g. 'blocked'), show that state instead. When `epic_delta_1h` / "
            "`epic_delta_5h` are present, append the recent rate — e.g. '(+<d1>% in the past hour, "
            "+<d5>% in the past 5h)' — and omit any window whose delta is null (the epic is younger "
            "than that window). When `progress.stage_changes_1h` is a non-empty list, add one line of "
            "color on what the plan did in the past hour — e.g. 'advanced 2 stages (gated → finalized "
            "in the past hour)'; omit it when the list is empty (no ladder progress in the window). "
            "When `epic_started_at` / `plan_started_at` are present, add 'epic "
            "started <relative time>, plan started <relative time>'. Use the pre-calculated fields as "
            "given; do not recompute them or invent other sub-plan percentages — `plan_percent` is a "
            "coarse completed-stages/total-stages estimate, so present it as approximate. "
            "Do not answer broad status from an arbitrary `.megaplan/plans` or `.chains` scan "
            "without labeling it degraded. Targeted per-plan questions may still use the cloud tools."
        )

    async def load_hot_context(self, conversation_id: str) -> dict[str, Any]:
        local_epic_chain_state = self._load_local_epic_chain_state_context()
        live_cloud_chain = await self._load_live_cloud_chain_context()
        cloud_status_snapshot, snapshot_degraded = self._load_cloud_status_snapshot()
        base: dict[str, Any] = {
            "conversation_id": conversation_id,
            "prompt_version": MEGAPLAN_RESIDENT_PROMPT_VERSION,
            "layout_policy": {
                "version": LAYOUT_POLICY_VERSION,
                "initiatives_root": ".megaplan/initiatives",
                "allowed_doc_kinds": sorted(ALLOWED_INITIATIVE_SUBDIRS),
                "legacy_briefs_root": ".megaplan/briefs",
            },
            "initiative_index": initiative_compact_index(Path.cwd(), limit=40),
            "resident_runtime": {
                "model_provider": self.config.model_provider,
                "model": self.config.model_name,
                "codex_reasoning_effort": self.config.codex_reasoning_effort,
                "codex_sandbox": self.config.codex_sandbox,
                "codex_machine_access": (
                    "full machine access; Codex CLI is launched with danger-full-access"
                    if self.config.codex_sandbox == "danger-full-access"
                    else f"Codex CLI sandbox: {self.config.codex_sandbox}"
                ),
            },
            "configured_cloud_yaml": str(self.config.cloud_yaml_path),
            # Canonical broad-status snapshot — the first source for "how's it
            # going?" / "what is active?" questions. Produced by the watchdog
            # from local observation only; never requires SSH from the resident.
            "cloud_status_snapshot": cloud_status_snapshot,
            "plan_activity_summary": status_snapshot.plan_activity_summary(cloud_status_snapshot),
            "cloud_status_degraded": snapshot_degraded,
            "epic_chain_visibility": _summarize_epic_chain_visibility(local_epic_chain_state, live_cloud_chain),
            # Supplemental detail only; NOT the canonical shared-runner view.
            "local_epic_chain_state": local_epic_chain_state,
            "live_cloud_chain": live_cloud_chain,
        }
        if self.store is None:
            return base
        conversation = self.store.load_resident_conversation(conversation_id)
        if conversation is None:
            return base
        active_epic_id = conversation.active_epic_id
        active_initiative_slug = slugify_initiative(active_epic_id) if active_epic_id else None
        context = self.store.load_hot_context(active_epic_id) if active_epic_id else None
        cloud_runs = self.store.list_cloud_runs(conversation_id=conversation.id, limit=5)
        pending_checks = self.store.list_scheduled_jobs(
            conversation_id=conversation.id,
            status="pending",
            job_type="cloud_check",
            limit=10,
        )
        base.update(
            {
                "conversation": conversation.model_dump(mode="json"),
                "active_epic": context.epic.model_dump(mode="json") if context and context.epic else None,
                "active_initiative": (
                    initiative_metadata(Path.cwd(), active_initiative_slug)
                    if active_initiative_slug
                    else None
                ),
                "recent_messages": [row.model_dump(mode="json") for row in (context.recent_messages if context else [])],
                "recent_tool_calls": [row.model_dump(mode="json") for row in (context.recent_tool_calls if context else [])],
                "checklist": [
                    row.model_dump(mode="json")
                    for row in (self.store.list_checklist_items(active_epic_id) if active_epic_id else [])
                ],
                "sprints": [row.model_dump(mode="json") for row in (context.sprints if context else [])],
                "cloud_runs": [row.model_dump(mode="json") for row in cloud_runs],
                "pending_cloud_checks": [row.model_dump(mode="json") for row in pending_checks],
            }
        )
        return base

    def _load_local_epic_chain_state_context(self) -> dict[str, Any]:
        roots: list[Path] = [Path.cwd()]
        workspace = Path("/workspace")
        if workspace.exists() and workspace not in roots:
            roots.append(workspace)
        epic_paths = _recent_state_paths(roots, ".epic_chains", limit=8)
        chain_paths = _recent_state_paths(roots, ".chains", limit=12)
        epic_states = [_summarize_epic_chain_state(path) for path in epic_paths]
        chain_states = [_summarize_chain_state(path) for path in chain_paths]
        return {
            "searched_roots": [str(root) for root in roots],
            "epic_chains": epic_states,
            "chains": chain_states,
            "active_chains": [
                row
                for row in chain_states
                if _is_active_chain_state(row)
            ][:5],
        }

    async def _load_live_cloud_chain_context(self) -> dict[str, Any] | None:
        cloud_yaml = self.config.cloud_yaml_path
        if not cloud_yaml:
            return None
        if not cloud_yaml.is_absolute():
            cloud_yaml = Path.cwd() / cloud_yaml
        if not cloud_yaml.exists():
            return {
                "available": False,
                "cloud_yaml": str(self.config.cloud_yaml_path),
                "message": "configured cloud YAML does not exist",
            }
        try:
            result = await self.cloud_backend.run(
                CloudToolRequest(
                    operation="cloud_status_chain",
                    arguments={
                        "project_root": str(Path.cwd()),
                        "cloud_yaml": str(self.config.cloud_yaml_path),
                    },
                )
            )
        except Exception as exc:
            return {
                "available": False,
                "cloud_yaml": str(self.config.cloud_yaml_path),
                "error": f"{exc.__class__.__name__}: {exc}",
            }
        return {
            "available": True,
            "cloud_yaml": str(self.config.cloud_yaml_path),
            "classification": result.classification,
            "summary": result.summary,
            "details": result.details,
        }

    def _load_cloud_status_snapshot(self) -> tuple[dict[str, Any] | None, str | None]:
        """Load the canonical cloud status snapshot for broad-status answers.

        Returns ``(snapshot, degraded_reason)``. ``degraded_reason`` is ``None``
        when the snapshot is present and fresh; otherwise it explains why the
        resident must fall back to local plan evidence (clearly labeled as
        degraded, not canonical). Never raises — a missing/unreadable snapshot
        is the degraded-mode signal, not an error.

        Inside the trusted container the snapshot is built fresh from local
        observation on every call, so hot context always reflects the current
        running/stuck/done set (the on-disk file the watchdog writes hourly can
        lag a newly-started session by up to a tick). Elsewhere the on-disk file
        is read with a freshness window.
        """
        if status_snapshot.is_trusted_container():
            try:
                snapshot = status_snapshot.build_cloud_status_snapshot()
            except Exception as exc:  # pragma: no cover - defensive guard
                return None, f"snapshot build failed: {exc.__class__.__name__}: {exc}"
            # Best-effort refresh of the shared on-disk file so CLI/laptop and
            # later reads see the current view too. The watchdog still owns the
            # hourly cadence; this just keeps the file fresh between sweeps while
            # the resident is active. A write failure never degrades the answer.
            try:
                status_snapshot.write_cloud_status_snapshot(
                    snapshot, path=self.config.status_snapshot_path
                )
            except Exception:  # pragma: no cover - best effort
                pass
            return snapshot, None
        path = self.config.status_snapshot_path
        try:
            return status_snapshot.load_cloud_status_snapshot(path, max_age_s=_SNAPSHOT_MAX_AGE_S)
        except Exception as exc:  # pragma: no cover - defensive guard for callers
            return None, f"snapshot load failed at {path}: {exc.__class__.__name__}"

    def tools(self) -> ToolRegistry:
        return self.tool_registry

    def _register_default_tools(self) -> None:
        assert self.store is not None
        registrations = (
            ToolRegistration("create_epic", "Create a new Megaplan epic.", "write", CreateEpicInput, ToolResult, self._create_epic),
            ToolRegistration("select_epic", "Select the active epic for a resident conversation.", "write", SelectEpicInput, ToolResult, self._select_epic),
            ToolRegistration("read_epic", "Read an epic body, checklist, and sprints.", "read", EpicInput, ToolResult, self._read_epic),
            ToolRegistration("search_messages", "Search resident messages using the Megaplan store.", "read", SearchMessagesInput, ToolResult, self._search_messages),
            ToolRegistration("search_epics", "Search Megaplan epics using the Megaplan store.", "read", SearchEpicsInput, ToolResult, self._search_epics),
            ToolRegistration("search_plans", "Search Megaplan plans using the Megaplan store.", "read", SearchPlansInput, ToolResult, self._search_plans),
            ToolRegistration("search_code_artifacts", "Search stored code artifacts with bounded redacted results.", "read", SearchCodeArtifactsInput, ToolResult, self._search_code_artifacts),
            ToolRegistration("list_codebases", "List durable codebase records visible to the resident.", "read", ListCodebasesInput, ToolResult, self._list_codebases),
            ToolRegistration("list_repos", "List durable registered repo metadata.", "read", ListReposInput, ToolResult, self._list_repos),
            ToolRegistration("edit_epic_body", "Replace an epic body using expected_revision.", "write", EditEpicBodyInput, ToolResult, self._edit_epic_body),
            ToolRegistration("add_checklist_items", "Add checklist items to an epic.", "write", AddChecklistItemsInput, ToolResult, self._add_checklist_items),
            ToolRegistration("update_checklist_item", "Update one checklist item.", "write", UpdateChecklistItemInput, ToolResult, self._update_checklist_item),
            ToolRegistration("create_or_update_sprints", "Create or update sprints and their items.", "write", CreateOrUpdateSprintsInput, ToolResult, self._create_or_update_sprints),
            ToolRegistration("queue_sprints", "Queue or mark pending sprints.", "write", QueueSprintsInput, ToolResult, self._queue_sprints),
            ToolRegistration("transition_epic_state", "Transition an epic through editorial gates.", "write", TransitionEpicStateInput, ToolResult, self._transition_epic_state),
            ToolRegistration("register_codebase", "Register durable repo metadata after admin confirmation.", "repo_write", RegisterCodebaseInput, ToolResult, self._register_codebase),
            ToolRegistration("add_repo", "Alias for registering durable repo metadata after admin confirmation.", "repo_write", RegisterCodebaseInput, ToolResult, self._register_codebase),
            ToolRegistration("read_plan_artifact", "Read a bounded plan artifact through the Megaplan store.", "read", ReadPlanArtifactInput, ToolResult, self._read_plan_artifact),
            ToolRegistration("write_plan_artifact", "Write a plan artifact through the Megaplan store after admin confirmation.", "artifact_write", WritePlanArtifactInput, ToolResult, self._write_plan_artifact),
            ToolRegistration("list_initiatives", "List canonical .megaplan initiative folders.", "read", ListInitiativesInput, ToolResult, self._list_initiatives),
            ToolRegistration("search_initiatives", "Search canonical initiatives by slug/title/description with rough fuzzy matching.", "read", SearchInitiativesInput, ToolResult, self._search_initiatives),
            ToolRegistration("create_initiative", "Create a canonical .megaplan/initiatives/<slug> folder.", "write", CreateInitiativeInput, ToolResult, self._create_initiative),
            ToolRegistration("read_initiative", "Read metadata and bounded document inventory for one initiative.", "read", ReadInitiativeInput, ToolResult, self._read_initiative),
            ToolRegistration("write_initiative_doc", "Write a document under an initiative briefs/research/decisions/notes/assets/handoff folder.", "write", WriteInitiativeDocInput, ToolResult, self._write_initiative_doc),
            ToolRegistration("classify_initiative_doc", "Classify a prospective initiative document path into the canonical folder set.", "read", ClassifyInitiativeDocInput, ToolResult, self._classify_initiative_doc),
            ToolRegistration("migrate_initiative_layout", "Dry-run or apply migration from legacy .megaplan/briefs to initiatives layout.", "write", MigrateInitiativeLayoutInput, ToolResult, self._migrate_initiative_layout),
            ToolRegistration("export_epic_bundle", "Export an epic bundle under the managed resident export root after admin confirmation.", "export", ExportEpicBundleInput, ToolResult, self._export_epic_bundle),
            ToolRegistration("reconcile_epic", "Summarize or apply epic reconciliation using existing store helpers.", "reconcile_apply", ReconcileEpicInput, ToolResult, self._reconcile_epic),
            ToolRegistration("reconcile_plan_storage", "Summarize or apply plan storage reconciliation using existing store helpers.", "reconcile_apply", ReconcilePlanStorageInput, ToolResult, self._reconcile_plan_storage),
            ToolRegistration("archive_cloud_logs", "Archive constrained cloud logs into plan artifacts after admin confirmation.", "archive_logs", ArchiveCloudLogsInput, ToolResult, self._archive_cloud_logs),
            ToolRegistration("approve_gate", "Queue a validated gate approval control message.", "control", ControlToolInput, ToolResult, self._approve_gate),
            ToolRegistration("reject_gate", "Queue a validated gate rejection control message.", "control", ControlToolInput, ToolResult, self._reject_gate),
            ToolRegistration("run_sprint_on_cloud", "Queue a validated sprint-run control message for later cloud handling.", "control", ControlToolInput, ToolResult, self._run_sprint_on_cloud),
            ToolRegistration("cloud_status", "Inspect a constrained cloud plan status.", "cloud_read", CloudStatusInput, ToolResult, self._cloud_status),
            ToolRegistration("cloud_status_chain", "Inspect constrained cloud chain status.", "cloud_read", CloudStatusChainInput, ToolResult, self._cloud_status_chain),
            ToolRegistration("cloud_start_chain", "Start a constrained cloud chain after exact confirmation.", "cloud_start", CloudStartChainInput, ToolResult, self._cloud_start_chain),
            ToolRegistration("cloud_bootstrap", "Bootstrap a constrained cloud plan after exact confirmation.", "cloud_start", CloudBootstrapInput, ToolResult, self._cloud_bootstrap),
            ToolRegistration("cloud_resume", "Resume constrained cloud work.", "cloud_start", CloudResumeInput, ToolResult, self._cloud_resume),
            ToolRegistration("cloud_logs", "Read constrained cloud logs.", "cloud_read", CloudLogsInput, ToolResult, self._cloud_logs),
            ToolRegistration("schedule_cloud_check", "Schedule a durable cloud status check.", "control", ScheduleCloudCheckInput, ToolResult, self._schedule_cloud_check),
            ToolRegistration("cancel_cloud_check", "Cancel a durable cloud status check.", "control", CancelCloudCheckInput, ToolResult, self._cancel_cloud_check),
            ToolRegistration("list_cloud_checks", "List durable cloud status checks.", "cloud_read", ListCloudChecksInput, ToolResult, self._list_cloud_checks),
            ToolRegistration("read_todo_list", "Read the VP special-requests to-do list (pending + retained items).", "read", ReadTodoListInput, ToolResult, self._read_todo_list),
            ToolRegistration("complete_todo_item", "Mark a to-do item done and clear it from the list; pass a short result summary.", "write", CompleteTodoItemInput, ToolResult, self._complete_todo_item),
            ToolRegistration("fail_todo_item", "Mark a to-do item failed (retained for retry); pass the reason.", "write", FailTodoItemInput, ToolResult, self._fail_todo_item),
            ToolRegistration("add_todo_item", "Append a new pending item to the VP to-do list. Optional `when` is a natural-language condition the agent checks before executing (e.g. 'once epic <id> is done').", "write", AddTodoItemInput, ToolResult, self._add_todo_item),
            ToolRegistration("launch_subagent", "Launch a sub-agent to execute an arbitrary task with file/web/terminal tools and return its final response.", "write", LaunchSubagentInput, ToolResult, self._launch_subagent),
        )
        for registration in registrations:
            self.tool_registry.register(registration)

    def _search_messages(self, payload: SearchMessagesInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        rows = self._store().search_messages(query=payload.query, epic_id=payload.epic_id, limit=payload.limit)
        if payload.conversation_id is not None:
            rows = [row for row in rows if row.conversation_id == payload.conversation_id][: payload.limit]
        return _ok("messages searched", messages=[_message_result(row) for row in rows], count=len(rows), limit=payload.limit)

    def _search_epics(self, payload: SearchEpicsInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        rows = self._store().search_epics(query=payload.query, active_only=False, limit=payload.limit)
        if payload.state is not None:
            rows = [row for row in rows if row.state == payload.state][: payload.limit]
        return _ok("epics searched", epics=[_epic_result(row) for row in rows], count=len(rows), limit=payload.limit)

    def _search_plans(self, payload: SearchPlansInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        needle = _normalize_search(payload.query)
        rows = self._store().list_plans(
            sprint_id=payload.sprint_id,
            epic_id=payload.epic_id,
            include_orphans=payload.epic_id is None,
        )
        if needle:
            rows = [
                row
                for row in rows
                if needle in _normalize_search(" ".join([row.id, row.name, row.idea, row.current_state]))
            ]
        rows.sort(key=lambda row: (row.updated_at, row.id), reverse=True)
        rows = rows[: payload.limit]
        return _ok("plans searched", plans=[_plan_result(row) for row in rows], count=len(rows), limit=payload.limit)

    def _search_code_artifacts(self, payload: SearchCodeArtifactsInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        needle = _normalize_search(payload.query)
        rows = self._store().list_code_artifacts(
            codebase_id=payload.codebase_id,
            epic_id=payload.epic_id,
            kind=payload.kind,
            source=payload.source,
            file_path=payload.file_path,
            include_expired=False,
            limit=None,
        )
        if needle:
            rows = [
                row
                for row in rows
                if needle
                in _normalize_search(
                    " ".join(
                        [
                            row.file_path or "",
                            row.content_summary or "",
                            " ".join(str(key) for key in row.metadata.keys()),
                            row.content,
                        ]
                    )
                )
            ]
        rows = rows[: payload.limit]
        return _ok(
            "code artifacts searched",
            artifacts=[_code_artifact_result(row) for row in rows],
            count=len(rows),
            limit=payload.limit,
        )

    def _list_codebases(self, payload: ListCodebasesInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        rows = self._store().list_codebases(
            scope=payload.scope,
            group_name=payload.group_name,
            epic_id=payload.epic_id,
            include_global=payload.include_global,
        )[: payload.limit]
        return _ok("codebases listed", codebases=[_codebase_result(row) for row in rows], count=len(rows), limit=payload.limit)

    def _list_repos(self, payload: ListReposInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        rows = [
            row
            for row in self._store().list_codebases(
                scope=payload.scope,
                group_name=payload.group_name,
                epic_id=payload.epic_id,
                include_global=payload.include_global,
            )
            if row.repo_url
        ][: payload.limit]
        return _ok("repos listed", repos=[_repo_result(row) for row in rows], count=len(rows), limit=payload.limit)

    def _register_codebase(self, payload: RegisterCodebaseInput) -> ToolResult:
        repo_url = payload.repo_url.strip()
        try:
            _validate_git_url(repo_url)
            workspace = _validate_repo_workspace(payload.repo_workspace)
        except ValueError as exc:
            return _fail(str(exc), validation_error=True)
        if confirm := self._require_confirmation(
            payload,
            action="repo_write",
            tool_name="register_codebase",
            target_summary=f"{payload.owner}/{payload.name} {repo_url}@{payload.default_branch} workspace={workspace or 'default'}",
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        try:
            codebase = self._store().upsert_codebase(
                owner=payload.owner,
                name=payload.name,
                repo_url=repo_url,
                repo_workspace=workspace,
                default_branch=payload.default_branch,
                scope=payload.scope,
                group_name=payload.group_name,
                associated_epic_id=payload.associated_epic_id,
                added_via="resident",
                notes=payload.notes,
                idempotency_key=deterministic_idempotency_key(
                    "resident-register-codebase",
                    payload.owner,
                    payload.name,
                    repo_url,
                    payload.default_branch,
                    workspace,
                ),
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok("codebase registered", codebase=_codebase_result(codebase), repo=_repo_result(codebase))

    def _read_plan_artifact(self, payload: ReadPlanArtifactInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        try:
            stat = self._store().stat_plan_artifact(payload.plan_id, payload.name)
            data = self._store().read_plan_artifact(payload.plan_id, payload.name)
        except Exception as exc:
            return _exception_result(exc)
        if data is None:
            return _fail("plan artifact not found", plan_id=payload.plan_id, name=payload.name)
        metadata: dict[str, Any] = {
            "plan_id": payload.plan_id,
            "name": payload.name,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "store_stat": stat.model_dump(mode="json") if stat is not None else None,
        }
        if len(data) > payload.max_bytes:
            return _ok("plan artifact metadata read", artifact={**metadata, "oversized": True, "max_bytes": payload.max_bytes})
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return _ok("plan artifact metadata read", artifact={**metadata, "binary": True})
        return _ok("plan artifact read", artifact={**metadata, "binary": False, "oversized": False, "content_text": text})

    def _write_plan_artifact(self, payload: WritePlanArtifactInput) -> ToolResult:
        if confirm := self._require_confirmation(
            payload,
            action="artifact_write",
            tool_name="write_plan_artifact",
            target_summary=f"{payload.plan_id}:{payload.name}",
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        data = payload.content_text.encode("utf-8")
        try:
            ref = self._store().write_plan_artifact(
                payload.plan_id,
                payload.name,
                data,
                expected_revision=payload.expected_revision,
                idempotency_key=deterministic_idempotency_key("resident-write-plan-artifact", payload.plan_id, payload.name, data),
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok("plan artifact written", artifact=ref.model_dump(mode="json"))

    def _list_initiatives(self, payload: ListInitiativesInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        try:
            root = _resident_project_root(payload.project_root)
            base = initiatives_dir(root)
            rows = [
                initiative_metadata(root, path.name)
                for path in sorted(base.iterdir())
                if path.is_dir()
            ][: payload.limit]
        except Exception as exc:
            return _exception_result(exc)
        return _ok(
            "initiatives listed",
            initiatives=rows,
            count=len(rows),
            layout_policy_version=LAYOUT_POLICY_VERSION,
        )

    def _search_initiatives(self, payload: SearchInitiativesInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        try:
            root = _resident_project_root(payload.project_root)
            rows = search_initiatives(
                root,
                payload.query,
                keywords_all=payload.keywords_all,
                limit=payload.limit,
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok(
            "initiatives searched",
            initiatives=rows,
            count=len(rows),
            query=payload.query,
            layout_policy_version=LAYOUT_POLICY_VERSION,
        )

    def _create_initiative(self, payload: CreateInitiativeInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        try:
            root = _resident_project_root(payload.project_root)
            slug = slugify_initiative(payload.slug)
            initiative = initiative_root(root, slug)
            for name in ALLOWED_INITIATIVE_SUBDIRS:
                (initiative / name).mkdir(parents=True, exist_ok=True)
            if payload.north_star is not None:
                (initiative / "NORTHSTAR.md").write_text(payload.north_star.rstrip() + "\n", encoding="utf-8")
            description = payload.description.strip()
            if not description:
                raise ValueError("initiative description must not be empty")
            readme = initiative / "README.md"
            if not readme.exists():
                title = (payload.title or slug.replace("-", " ").title()).strip()
                readme.write_text(f"# {title}\n\n{description}\n", encoding="utf-8")
            if payload.create_chain:
                chain = initiative / "chain.yaml"
                if not chain.exists():
                    chain.write_text("milestones: []\n", encoding="utf-8")
        except Exception as exc:
            return _exception_result(exc)
        return _ok("initiative created", initiative=initiative_metadata(root, slug))

    def _read_initiative(self, payload: ReadInitiativeInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        try:
            root = _resident_project_root(payload.project_root)
            slug = slugify_initiative(payload.slug)
            initiative = initiative_root(root, slug)
            if not initiative.exists():
                return _fail("initiative not found", slug=slug, path=str(initiative))
            files = [
                path
                for path in sorted(initiative.rglob("*"))
                if path.is_file() and ".megaplan" not in path.relative_to(initiative).parts
            ][: payload.max_docs]
            docs = [
                {
                    "path": path.relative_to(initiative).as_posix(),
                    "size_bytes": path.stat().st_size,
                }
                for path in files
            ]
        except Exception as exc:
            return _exception_result(exc)
        return _ok("initiative read", initiative=initiative_metadata(root, slug), documents=docs)

    def _write_initiative_doc(self, payload: WriteInitiativeDocInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        try:
            root = _resident_project_root(payload.project_root)
            slug = slugify_initiative(payload.initiative_slug)
            initiative = initiative_root(root, slug)
            if not initiative.exists() and not payload.create_if_missing:
                return _fail("initiative not found", slug=slug, path=str(initiative))
            target_dir = initiative_doc_dir(root, slug, payload.doc_kind)
            target = _safe_child_path(target_dir, payload.filename)
            if target.exists() and not payload.overwrite:
                return _fail("initiative document already exists", path=str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload.content_text.rstrip() + "\n", encoding="utf-8")
        except Exception as exc:
            return _exception_result(exc)
        return _ok(
            "initiative document written",
            initiative=initiative_metadata(root, slug),
            path=str(target),
            relative_path=target.relative_to(root).as_posix(),
            doc_kind=payload.doc_kind,
        )

    def _classify_initiative_doc(self, payload: ClassifyInitiativeDocInput) -> ToolResult:
        try:
            kind = classify_initiative_doc_path(payload.path)
        except Exception as exc:
            return _exception_result(exc)
        return _ok("initiative document classified", path=payload.path, doc_kind=kind)

    def _migrate_initiative_layout(self, payload: MigrateInitiativeLayoutInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        try:
            root = _resident_project_root(payload.project_root)
            result = migrate_legacy_briefs_layout(root, apply=payload.apply)
        except Exception as exc:
            return _exception_result(exc)
        return _ok("initiative layout migration complete", **result)

    def _export_epic_bundle(self, payload: ExportEpicBundleInput) -> ToolResult:
        if confirm := self._require_confirmation(
            payload,
            action="export",
            tool_name="export_epic_bundle",
            target_summary=payload.epic_id,
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        try:
            export_root = self._managed_export_root()
            output = export_root / f"epic-{_safe_filename(payload.epic_id)}.tar"
            if not _is_relative_to(output, export_root):
                return _fail("managed export path escaped export root", export_root=str(export_root))
            collected = (
                collect_epic_export(self._store(), payload.epic_id)
                if hasattr(self._store(), "_route_for_epic")
                else _collect_basic_epic_export(self._store(), payload.epic_id)
            )
            if collected["errors"]:
                return _fail("epic export has blocking errors", errors=collected["errors"], warnings=collected["warnings"])
            result = write_epic_export_tar(collected, output)
        except Exception as exc:
            return _exception_result(exc)
        return _ok("epic bundle exported", export=result, manifest=collected["manifest"])

    def _reconcile_epic(self, payload: ReconcileEpicInput) -> ToolResult:
        if not payload.apply:
            if denied := self._denied(payload, "read"):
                return denied
            return _ok("epic reconciliation dry run", summary=self._epic_reconciliation_summary(payload.epic_id))
        if confirm := self._require_confirmation(
            payload,
            action="reconcile_apply",
            tool_name="reconcile_epic",
            target_summary=payload.epic_id,
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        return _ok("epic reconciliation applied", summary=self._epic_reconciliation_summary(payload.epic_id), applied=True)

    def _reconcile_plan_storage(self, payload: ReconcilePlanStorageInput) -> ToolResult:
        if not payload.apply:
            if denied := self._denied(payload, "read"):
                return denied
            return _ok("plan storage reconciliation dry run", summary=self._plan_storage_summary(payload))
        if confirm := self._require_confirmation(
            payload,
            action="reconcile_apply",
            tool_name="reconcile_plan_storage",
            target_summary=str(payload.plan_id or payload.epic_id or "plan-storage"),
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        return _ok("plan storage reconciliation applied", summary=self._plan_storage_summary(payload), applied=True)

    async def _archive_cloud_logs(self, payload: ArchiveCloudLogsInput) -> ToolResult:
        if confirm := self._require_confirmation(
            payload,
            action="archive_logs",
            tool_name="archive_cloud_logs",
            target_summary=payload.cloud_run_id,
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        store = self._store()
        run = store.load_cloud_run(payload.cloud_run_id)
        plan_id = payload.plan_id or (run.plan_id if run is not None else None)
        if not plan_id:
            return _fail("plan_id is required to archive cloud logs", cloud_run_id=payload.cloud_run_id)
        try:
            result = await self.cloud_backend.run(
                CloudToolRequest(
                    operation="cloud_logs",
                    target_id=payload.cloud_run_id,
                    arguments={
                        "project_root": payload.project_root,
                        "cloud_yaml": payload.cloud_yaml or str(self.config.cloud_yaml_path),
                        "no_follow": "true",
                    },
                    confirmed=True,
                )
            )
            captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            artifact_payload = {
                "cloud_run_id": payload.cloud_run_id,
                "plan_id": plan_id,
                "captured_at": captured_at,
                "no_follow": True,
                "classification": result.classification,
                "summary": result.summary,
                "details": result.details,
            }
            data = json.dumps(artifact_payload, indent=2, sort_keys=True).encode("utf-8")
            digest = hashlib.sha256(data).hexdigest()
            ref = store.write_plan_artifact(
                plan_id,
                f"cloud-logs/{payload.cloud_run_id}.json",
                data,
                idempotency_key=deterministic_idempotency_key("resident-archive-cloud-logs", payload.cloud_run_id, digest),
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok(
            "cloud logs archived",
            artifact=ref.model_dump(mode="json"),
            cloud_run_id=payload.cloud_run_id,
            plan_id=plan_id,
            size_bytes=len(data),
            sha256=digest,
            classification=result.classification,
        )

    def _managed_export_root(self) -> Path:
        root = self.config.resident_export_root.expanduser()
        if not root.is_absolute():
            root = Path.cwd() / root
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _epic_reconciliation_summary(self, epic_id: str) -> dict[str, Any]:
        store = self._store()
        epic = self._require_epic(epic_id)
        plans = store.list_plans(epic_id=epic_id, include_orphans=True)
        artifacts_by_plan = {
            plan.id: [ref.model_dump(mode="json") for ref in store.list_plan_artifacts(plan.id)]
            for plan in plans
        }
        incomplete = []
        warnings_fn = getattr(store, "incomplete_migration_warnings", None)
        if callable(warnings_fn):
            incomplete = [message for message in warnings_fn() if epic_id in message]
        return {
            "epic": _epic_result(epic),
            "body_present": bool(store.load_body(epic_id)),
            "checklist_count": len(store.list_checklist_items(epic_id)),
            "sprint_count": len(store.list_sprints(epic_id)),
            "plan_count": len(plans),
            "plan_artifacts": artifacts_by_plan,
            "codebase_count": len(store.list_codebases(epic_id=epic_id)),
            "code_artifact_count": len(store.list_code_artifacts(epic_id=epic_id, limit=None)),
            "incomplete_migration_warnings": incomplete,
        }

    def _plan_storage_summary(self, payload: ReconcilePlanStorageInput) -> dict[str, Any]:
        store = self._store()
        plans = (
            [store.load_plan(payload.plan_id)] if payload.plan_id else store.list_plans(epic_id=payload.epic_id, include_orphans=payload.epic_id is None)
        )
        existing = [plan for plan in plans if plan is not None]
        missing_plan_ids = [payload.plan_id] if payload.plan_id and not existing else []
        return {
            "plan_count": len(existing),
            "missing_plan_ids": missing_plan_ids,
            "plans": [
                {
                    **_plan_result(plan),
                    "artifacts": [
                        {
                            **ref.model_dump(mode="json"),
                            "stat": (
                                store.stat_plan_artifact(plan.id, ref.name).model_dump(mode="json")
                                if store.stat_plan_artifact(plan.id, ref.name) is not None
                                else None
                            ),
                        }
                        for ref in store.list_plan_artifacts(plan.id)
                    ],
                }
                for plan in existing
            ],
        }

    def _create_epic(self, payload: CreateEpicInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        store = self._store()
        epic = store.create_epic(
            title=payload.title,
            goal=payload.goal,
            body=payload.body,
            idempotency_key=deterministic_idempotency_key("resident-tool-create-epic", payload.title, payload.goal),
        )
        return _ok("epic created", epic=epic.model_dump(mode="json"))

    def _select_epic(self, payload: SelectEpicInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        store = self._store()
        epic = self._require_epic(payload.epic_id)
        conversation = store.load_resident_conversation(payload.conversation_id)
        if conversation is None:
            return _fail("conversation not found", conversation_id=payload.conversation_id)
        updated = store.update_resident_conversation(
            conversation.id,
            active_epic_id=epic.id,
            idempotency_key=deterministic_idempotency_key("resident-tool-select-epic", conversation.id, epic.id),
        )
        return _ok("active epic selected", conversation=updated.model_dump(mode="json"), epic=epic.model_dump(mode="json"))

    def _read_epic(self, payload: EpicInput) -> ToolResult:
        if denied := self._denied(payload, "read"):
            return denied
        epic = self._require_epic(payload.epic_id)
        store = self._store()
        return _ok(
            "epic read",
            epic=epic.model_dump(mode="json"),
            body=store.load_body(epic.id),
            checklist=[row.model_dump(mode="json") for row in store.list_checklist_items(epic.id)],
            sprints=[row.model_dump(mode="json") for row in store.list_sprints_with_items(epic.id)],
            cloud_runs=[row.model_dump(mode="json") for row in store.list_cloud_runs(epic_id=epic.id, limit=5)],
            pending_cloud_checks=[
                row.model_dump(mode="json")
                for row in store.list_scheduled_jobs(epic_id=epic.id, status="pending", job_type="cloud_check", limit=10)
            ],
        )

    def _edit_epic_body(self, payload: EditEpicBodyInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        try:
            epic = self._require_epic(payload.epic_id)
            if payload.expected_revision is not None and payload.expected_revision != epic.revision:
                return _fail(
                    "expected_revision does not match current epic revision",
                    expected_revision=payload.expected_revision,
                    current_revision=epic.revision,
                )
            updated = editorial_body.update_body(
                store=self._store(),
                epic_id=payload.epic_id,
                actor_id=self.actor_id,
                body=payload.body,
                expected_revision=epic.revision,
                idempotency_key=deterministic_idempotency_key("resident-tool-body", payload.epic_id, epic.revision),
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok("epic body updated", epic=updated.model_dump(mode="json"))

    def _add_checklist_items(self, payload: AddChecklistItemsInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        try:
            created = editorial_checklist.add_items(
                store=self._store(),
                epic_id=payload.epic_id,
                actor_id=self.actor_id,
                contents=payload.items,
                idempotency_key=deterministic_idempotency_key("resident-tool-checklist-add", payload.epic_id, *payload.items),
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok("checklist items added", items=[row.model_dump(mode="json") for row in created])

    def _update_checklist_item(self, payload: UpdateChecklistItemInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        changes = payload.model_dump(exclude={"actor_user_id", "guild_id", "channel_id", "epic_id", "item_id"}, exclude_none=True)
        try:
            updated = editorial_checklist.update_item(
                store=self._store(),
                epic_id=payload.epic_id,
                actor_id=self.actor_id,
                item_id=payload.item_id,
                idempotency_key=deterministic_idempotency_key("resident-tool-checklist-update", payload.epic_id, payload.item_id, sorted(changes)),
                **changes,
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok("checklist item updated", item=updated.model_dump(mode="json"))

    def _create_or_update_sprints(self, payload: CreateOrUpdateSprintsInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        store = self._store()
        results: list[dict[str, Any]] = []
        try:
            for spec in payload.sprints:
                if spec.sprint_id:
                    current = store.load_sprint(spec.sprint_id)
                    if current is None:
                        return _fail("sprint not found", sprint_id=spec.sprint_id)
                    if current.epic_id != payload.epic_id:
                        return _fail("sprint does not belong to epic", sprint_id=spec.sprint_id, epic_id=payload.epic_id)
                    if spec.expected_revision is not None and spec.expected_revision != current.revision:
                        return _fail(
                            "expected_revision does not match current sprint revision",
                            sprint_id=spec.sprint_id,
                            expected_revision=spec.expected_revision,
                            current_revision=current.revision,
                        )
                    sprint = editorial_sprints.update_sprint(
                        store=store,
                        epic_id=payload.epic_id,
                        actor_id=self.actor_id,
                        sprint_id=spec.sprint_id,
                        expected_revision=current.revision,
                        name=spec.name,
                        goal=spec.goal,
                        target_weeks=spec.target_weeks,
                        idempotency_key=deterministic_idempotency_key("resident-tool-sprint-update", payload.epic_id, spec.sprint_id, current.revision),
                    )
                else:
                    sprint = editorial_sprints.create_sprint(
                        store=store,
                        epic_id=payload.epic_id,
                        actor_id=self.actor_id,
                        sprint_number=spec.sprint_number,
                        name=spec.name,
                        goal=spec.goal,
                        target_weeks=spec.target_weeks,
                        idempotency_key=deterministic_idempotency_key("resident-tool-sprint-create", payload.epic_id, spec.sprint_number, spec.name),
                    )
                if spec.items:
                    items = [
                        SprintItemInput(
                            content=item.content,
                            estimated_complexity=item.estimated_complexity,
                            status=item.status,
                            source_section=item.source_section,
                        )
                        for item in spec.items
                    ]
                    editorial_sprints.replace_sprint_items(
                        store=store,
                        epic_id=payload.epic_id,
                        actor_id=self.actor_id,
                        sprint_id=sprint.id,
                        items=items,
                        idempotency_key=deterministic_idempotency_key("resident-tool-sprint-items", payload.epic_id, sprint.id, len(items)),
                    )
                results.append(store.load_sprint(sprint.id).model_dump(mode="json"))
        except Exception as exc:
            return _exception_result(exc)
        return _ok("sprints created or updated", sprints=results)

    def _queue_sprints(self, payload: QueueSprintsInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        try:
            queued = editorial_sprints.set_sprint_queue(
                store=self._store(),
                epic_id=payload.epic_id,
                actor_id=self.actor_id,
                ordered_sprint_ids=payload.ordered_sprint_ids,
                pending=payload.pending,
                idempotency_key=deterministic_idempotency_key("resident-tool-sprint-queue", payload.epic_id, *payload.ordered_sprint_ids, *payload.pending),
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok("sprint queue updated", sprints=[row.model_dump(mode="json") for row in queued])

    def _transition_epic_state(self, payload: TransitionEpicStateInput) -> ToolResult:
        if denied := self._denied(payload, "write"):
            return denied
        try:
            epic = self._require_epic(payload.epic_id)
            if payload.expected_revision is not None and payload.expected_revision != epic.revision:
                return _fail(
                    "expected_revision does not match current epic revision",
                    expected_revision=payload.expected_revision,
                    current_revision=epic.revision,
                )
            updated = editorial_gating.transition_epic_state(
                store=self._store(),
                epic_id=payload.epic_id,
                actor_id=self.actor_id,
                target_state=payload.target_state,
                expected_revision=epic.revision,
                force=payload.force,
                idempotency_key=deterministic_idempotency_key(
                    "resident-tool-transition",
                    payload.epic_id,
                    payload.target_state,
                    epic.revision,
                ),
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok("epic state transitioned", epic=updated.model_dump(mode="json"))

    def _approve_gate(self, payload: ControlToolInput) -> ToolResult:
        return self._queue_control("approve_gate", payload)

    def _reject_gate(self, payload: ControlToolInput) -> ToolResult:
        return self._queue_control("reject_gate", payload)

    def _run_sprint_on_cloud(self, payload: ControlToolInput) -> ToolResult:
        if confirm := self._require_confirmation(
            payload,
            action="cloud_start",
            tool_name="run_sprint_on_cloud",
            target_summary=f"sprint {payload.target_id}",
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        try:
            self._validate_control_target("run_sprint", payload, resident_cloud=True)
            run = self._create_cloud_run(
                operation="sprint",
                payload=payload,
                target_id=payload.target_id,
                command_summary=f"run sprint {payload.target_id} on cloud",
                status="queued",
                metadata={"tool": "run_sprint_on_cloud"},
            )
        except Exception as exc:
            return _exception_result(exc)
        return self._queue_control(
            "run_sprint",
            payload,
            resident_cloud=True,
            extra_payload={"cloud_run_id": run.id},
            target_already_validated=True,
        )

    def _queue_control(
        self,
        intent: str,
        payload: ControlToolInput,
        *,
        resident_cloud: bool = False,
        extra_payload: dict[str, Any] | None = None,
        target_already_validated: bool = False,
    ) -> ToolResult:
        if denied := self._denied(payload, "admin"):
            return denied
        store = self._store()
        control_payload = {
            "epic_id": payload.epic_id,
            "project_root": str(Path(payload.project_root).expanduser()),
            "reason": payload.reason,
            "note": payload.note,
            "auto_continue": payload.auto_continue,
            "resident_cloud": resident_cloud,
        }
        if payload.plan:
            control_payload["plan"] = payload.plan
        if extra_payload:
            control_payload.update(extra_payload)
        control_payload = {key: value for key, value in control_payload.items() if value is not None}
        try:
            if not target_already_validated:
                ControlTargetResolver(store).resolve(intent, payload.target_id, control_payload)
            recovered = store.recover_stale_control_messages(
                processor_id="resident-tool",
                older_than_seconds=600,
                max=10,
                idempotency_key=deterministic_idempotency_key("resident-tool-control-recover", intent, payload.target_id),
            )
            control = store.put_control_message(
                ControlMessageInput(
                    epic_id=payload.epic_id,
                    actor_id=payload.actor_user_id or self.actor_id,
                    intent=intent,
                    target_id=payload.target_id,
                    payload=control_payload,
                    idempotency_key=deterministic_idempotency_key("resident-tool-control", intent, payload.epic_id, payload.target_id, control_payload),
                ),
                idempotency_key=deterministic_idempotency_key("resident-tool-control", intent, payload.epic_id, payload.target_id, control_payload),
            )
        except Exception as exc:
            return _exception_result(exc)
        return _ok(
            "control message queued",
            control_message=control.model_dump(mode="json"),
            recovered_stale_control_message_ids=[row.id for row in recovered],
        )

    def _validate_control_target(self, intent: str, payload: ControlToolInput, *, resident_cloud: bool = False) -> None:
        control_payload = {
            "epic_id": payload.epic_id,
            "project_root": str(Path(payload.project_root).expanduser()),
            "reason": payload.reason,
            "note": payload.note,
            "auto_continue": payload.auto_continue,
            "resident_cloud": resident_cloud,
        }
        if payload.plan:
            control_payload["plan"] = payload.plan
        ControlTargetResolver(self._store()).resolve(
            intent,
            payload.target_id,
            {key: value for key, value in control_payload.items() if value is not None},
        )

    async def _cloud_status(self, payload: CloudStatusInput) -> ToolResult:
        return await self._run_cloud_tool(
            operation="cloud_status",
            payload=payload,
            run_operation="status",
            arguments={"plan": payload.plan},
            target_id=payload.plan or payload.plan_id,
            command_summary="cloud status",
        )

    async def _cloud_status_chain(self, payload: CloudStatusChainInput) -> ToolResult:
        return await self._run_cloud_tool(
            operation="cloud_status_chain",
            payload=payload,
            run_operation="status",
            arguments={"remote_spec": payload.remote_spec},
            target_id=payload.remote_spec,
            command_summary="cloud status --chain",
        )

    async def _cloud_start_chain(self, payload: CloudStartChainInput) -> ToolResult:
        try:
            repo_args = self._repo_arguments_for_payload(payload)
        except Exception as exc:
            return _exception_result(exc)
        if confirm := self._require_confirmation(
            payload,
            action="cloud_start",
            tool_name="cloud_start_chain",
            target_summary=_cloud_target_summary(f"chain {payload.spec}", repo_args),
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        return await self._run_cloud_tool(
            operation="cloud_start_chain",
            payload=payload,
            run_operation="chain",
            arguments={"spec": payload.spec, "idea_dir": payload.idea_dir},
            target_id=payload.spec,
            command_summary=f"cloud chain {payload.spec}",
            resolved_repo_args=repo_args,
        )

    async def _cloud_bootstrap(self, payload: CloudBootstrapInput) -> ToolResult:
        try:
            repo_args = self._repo_arguments_for_payload(payload)
        except Exception as exc:
            return _exception_result(exc)
        if confirm := self._require_confirmation(
            payload,
            action="cloud_start",
            tool_name="cloud_bootstrap",
            target_summary=_cloud_target_summary(f"bootstrap {payload.idea_file}", repo_args),
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        return await self._run_cloud_tool(
            operation="cloud_bootstrap",
            payload=payload,
            run_operation="bootstrap",
            arguments={"idea_file": payload.idea_file, "plan_name": payload.plan_name, "robustness": payload.robustness},
            target_id=payload.idea_file,
            command_summary=f"cloud bootstrap {payload.idea_file}",
            resolved_repo_args=repo_args,
        )

    async def _cloud_resume(self, payload: CloudResumeInput) -> ToolResult:
        if confirm := self._require_confirmation(
            payload,
            action="cloud_start",
            tool_name="cloud_resume",
            target_summary=payload.plan or payload.plan_id or "cloud resume",
            request_id=payload.confirmation_request_id,
            phrase=payload.confirmation_phrase,
        ):
            return confirm
        return await self._run_cloud_tool(
            operation="cloud_resume",
            payload=payload,
            run_operation="resume",
            arguments={"plan": payload.plan},
            target_id=payload.plan or payload.plan_id,
            command_summary="cloud resume",
        )

    async def _cloud_logs(self, payload: CloudLogsInput) -> ToolResult:
        return await self._run_cloud_tool(
            operation="cloud_logs",
            payload=payload,
            run_operation="status",
            arguments={"no_follow": str(payload.no_follow).lower()},
            target_id=payload.cloud_run_id or payload.plan_id,
            command_summary="cloud logs",
        )

    def _schedule_cloud_check(self, payload: ScheduleCloudCheckInput) -> ToolResult:
        if denied := self._denied(payload, "admin"):
            return denied
        if not payload.cloud_run_id:
            return _fail("cloud_run_id is required")
        store = self._store()
        run = store.load_cloud_run(payload.cloud_run_id)
        if run is None:
            return _fail("cloud run not found", cloud_run_id=payload.cloud_run_id)
        conversation_id = payload.conversation_id or run.conversation_id
        if not conversation_id:
            return _fail("conversation_id is required")
        conversation = store.load_resident_conversation(conversation_id)
        if conversation is None:
            return _fail("conversation not found", conversation_id=conversation_id)
        scheduled_for = payload.scheduled_for or (datetime.now(UTC) + timedelta(seconds=payload.interval_seconds))
        job_payload = {
            "conversation_id": conversation.id,
            "cloud_run_id": run.id,
            "project_root": payload.project_root,
            "cloud_yaml": payload.cloud_yaml or str(self.config.cloud_yaml_path),
            "check_interval_s": payload.interval_seconds,
            "notify_every_check": payload.notify_every_check,
            **payload.payload,
        }
        job = store.create_scheduled_job(
            ScheduledJobInput(
                job_type="cloud_check",
                conversation_id=conversation.id,
                cloud_run_id=run.id,
                epic_id=run.epic_id or payload.epic_id or conversation.active_epic_id,
                payload=job_payload,
                scheduled_for=scheduled_for,
                max_attempts=payload.max_attempts,
            ),
            idempotency_key=deterministic_idempotency_key(
                "resident-tool-schedule-cloud-check",
                conversation.id,
                run.id,
                scheduled_for.isoformat(),
                payload.interval_seconds,
            ),
        )
        return _ok("cloud check scheduled", scheduled_job=job.model_dump(mode="json"))

    def _cancel_cloud_check(self, payload: CancelCloudCheckInput) -> ToolResult:
        if denied := self._denied(payload, "admin"):
            return denied
        store = self._store()
        job = store.load_scheduled_job(payload.scheduled_job_id)
        if job is None:
            return _fail("scheduled job not found", scheduled_job_id=payload.scheduled_job_id)
        if job.job_type != "cloud_check":
            return _fail("scheduled job is not a cloud_check", scheduled_job_id=payload.scheduled_job_id)
        updated = store.update_scheduled_job(
            job.id,
            status="cancelled",
            cancelled_at=datetime.now(UTC),
            idempotency_key=deterministic_idempotency_key("resident-tool-cancel-cloud-check", job.id),
        )
        return _ok("cloud check cancelled", scheduled_job=updated.model_dump(mode="json"))

    def _list_cloud_checks(self, payload: ListCloudChecksInput) -> ToolResult:
        if denied := self._denied(payload, "cloud_read"):
            return denied
        rows = self._store().list_scheduled_jobs(
            conversation_id=payload.conversation_id,
            cloud_run_id=payload.cloud_run_id,
            status=payload.status,
            job_type="cloud_check",
            limit=payload.limit,
        )
        if payload.epic_id is not None:
            rows = [row for row in rows if row.epic_id == payload.epic_id]
        return _ok("cloud checks listed", scheduled_jobs=[row.model_dump(mode="json") for row in rows])

    def _todo_path(self) -> Path:
        return Path(self.config.special_requests_todo_path)

    def _read_todo_list(self, payload: ReadTodoListInput) -> ToolResult:
        items = vp_todo.load_items(self._todo_path())
        return _ok(
            "todo list read",
            items=[vp_todo.public_item(item) for item in items],
            pending=sum(1 for item in items if item["status"] == vp_todo.PENDING),
        )

    def _complete_todo_item(self, payload: CompleteTodoItemInput) -> ToolResult:
        completed = vp_todo.complete_item(self._todo_path(), payload.id, payload.result)
        if completed is None:
            return _fail("todo item not found", id=payload.id)
        return _ok("todo item completed and cleared", item=vp_todo.public_item(completed))

    def _fail_todo_item(self, payload: FailTodoItemInput) -> ToolResult:
        failed = vp_todo.fail_item(self._todo_path(), payload.id, payload.reason)
        if failed is None:
            return _fail("todo item not found", id=payload.id)
        return _ok("todo item marked failed (retained)", item=vp_todo.public_item(failed))

    def _add_todo_item(self, payload: AddTodoItemInput) -> ToolResult:
        task = payload.task.strip()
        if not task:
            return _fail("task is required")
        item = vp_todo.add_item(self._todo_path(), task, when=payload.when)
        return _ok("todo item added", item=vp_todo.public_item(item))

    async def _launch_subagent(self, payload: LaunchSubagentInput) -> ToolResult:
        task = payload.task.strip()
        if not task:
            return _fail("task is required")
        result = await launch_subagent_task(
            self.config,
            task=task,
            toolsets=payload.toolsets,
            project_dir=payload.project_dir,
        )
        if not result.ok:
            return ToolResult(
                ok=False,
                message=result.error or "subagent failed",
                data={"returncode": result.returncode, "stderr": result.stderr[:1000]},
            )
        return ToolResult(
            ok=True,
            message="subagent completed",
            data={"final_text": result.final_text, "returncode": result.returncode},
        )

    async def _run_cloud_tool(
        self,
        *,
        operation: CloudOperation,
        payload: CloudToolInput,
        run_operation: str,
        arguments: dict[str, Any],
        target_id: str | None,
        command_summary: str,
        resolved_repo_args: dict[str, str] | None = None,
    ) -> ToolResult:
        action = "cloud_read" if operation in {"cloud_status", "cloud_status_chain", "cloud_logs"} else "admin"
        if denied := self._denied(payload, action):
            return denied
        try:
            repo_args = resolved_repo_args if resolved_repo_args is not None else self._repo_arguments_for_payload(payload)
            run = self._load_or_create_cloud_run(
                cloud_run_id=payload.cloud_run_id,
                operation=run_operation,
                payload=payload,
                target_id=target_id,
                command_summary=command_summary,
                status="running" if operation != "cloud_logs" else "unknown",
                metadata={"tool": operation},
            )
            request_args = {
                "project_root": payload.project_root,
                "cloud_yaml": payload.cloud_yaml or str(self.config.cloud_yaml_path),
                **{key: value for key, value in arguments.items() if value is not None},
                **repo_args,
            }
        except Exception as exc:
            return _exception_result(exc)
        try:
            result = await self.cloud_backend.run(
                CloudToolRequest(
                    operation=operation,
                    target_id=target_id,
                    arguments={key: str(value) for key, value in request_args.items() if value is not None},
                    confirmed=operation in {"cloud_start_chain", "cloud_bootstrap"},
                )
            )
        except Exception as exc:
            result = CloudToolResult(
                classification="failed",
                summary=f"{operation} failed: {exc}",
                details={"error": str(exc), "error_type": exc.__class__.__name__},
            )
        updated = self._persist_cloud_result(run.id, result, payload=payload, operation=run_operation)
        return _ok(
            result.summary,
            classification=result.classification,
            cloud_run=updated.model_dump(mode="json"),
            cloud_result={"summary": result.summary, "details": result.details},
        )

    def _repo_arguments_for_payload(self, payload: CloudToolInput) -> dict[str, str]:
        repo_url = payload.repo_url
        repo_branch = payload.repo_branch
        repo_workspace = payload.repo_workspace
        if payload.codebase_id:
            codebase = self._store().load_codebase(payload.codebase_id)
            if codebase is None:
                raise CliError("unknown_codebase", f"Codebase {payload.codebase_id!r} was not found")
            repo_url = repo_url or codebase.repo_url
            repo_branch = repo_branch or codebase.default_branch
            repo_workspace = repo_workspace or getattr(codebase, "repo_workspace", None)
        if repo_url:
            _validate_git_url(repo_url)
        if repo_workspace:
            repo_workspace = _validate_repo_workspace(repo_workspace)
        return {
            key: value
            for key, value in {
                "repo_url": repo_url,
                "repo_branch": repo_branch,
                "repo_workspace": repo_workspace,
            }.items()
            if value
        }

    def _load_or_create_cloud_run(
        self,
        *,
        cloud_run_id: str | None,
        operation: str,
        payload: CloudToolInput,
        target_id: str | None,
        command_summary: str,
        status: str,
        metadata: dict[str, Any],
    ) -> Any:
        store = self._store()
        if cloud_run_id:
            existing = store.load_cloud_run(cloud_run_id)
            if existing is None:
                raise CliError("unknown_cloud_run", f"Cloud run {cloud_run_id!r} was not found")
            return existing
        return self._create_cloud_run(
            operation=operation,
            payload=payload,
            target_id=target_id,
            command_summary=command_summary,
            status=status,
            metadata=metadata,
        )

    def _create_cloud_run(
        self,
        *,
        operation: str,
        payload: CloudToolInput,
        target_id: str | None,
        command_summary: str,
        status: str,
        metadata: dict[str, Any],
    ) -> Any:
        idempotency_key = deterministic_idempotency_key(
            "resident-cloud-run",
            operation,
            getattr(payload, "conversation_id", None),
            getattr(payload, "epic_id", None),
            getattr(payload, "sprint_id", None),
            getattr(payload, "plan_id", None) or getattr(payload, "plan", None),
            target_id,
            command_summary,
            payload.actor_user_id or self.actor_id,
        )
        run = self._store().create_cloud_run(
            CloudRunInput(
                operation=operation,
                conversation_id=getattr(payload, "conversation_id", None),
                epic_id=getattr(payload, "epic_id", None),
                sprint_id=getattr(payload, "sprint_id", None),
                plan_id=getattr(payload, "plan_id", None) or getattr(payload, "plan", None),
                provider="megaplan-cloud-cli",
                target_id=target_id,
                command_summary=command_summary,
                metadata=metadata,
                idempotency_key=idempotency_key,
                started_by_actor_id=payload.actor_user_id or self.actor_id,
            ),
            idempotency_key=idempotency_key,
        )
        if run.status != status:
            run = self._store().update_cloud_run(
                run.id,
                status=status,
                idempotency_key=deterministic_idempotency_key("resident-cloud-run-initial-status", run.id, status),
            )
        return run

    def _persist_cloud_result(
        self,
        run_id: str,
        result: CloudToolResult,
        *,
        payload: CloudToolInput,
        operation: str,
    ) -> Any:
        now = datetime.now(UTC)
        status = cloud_run_status_for_classification(result.classification)
        last_status = {
            "cloud_status": result.classification,
            "summary": result.summary,
            "details": result.details,
            "checked_at": now.isoformat().replace("+00:00", "Z"),
        }
        changes: dict[str, Any] = {
            "status": status,
            "progress_summary": result.summary,
            "last_status": last_status,
            "last_checked_at": now,
        }
        if status in {"completed", "failed", "blocked", "gate-needed"}:
            changes["completed_at"] = now
        updated = self._store().update_cloud_run(
            run_id,
            **changes,
            idempotency_key=deterministic_idempotency_key("resident-cloud-run-status", run_id, result.classification, result.summary),
        )
        if updated.epic_id:
            self._store().append_progress_event(
                ProgressEventInput(
                    epic_id=updated.epic_id,
                    plan_id=updated.plan_id,
                    sprint_id=updated.sprint_id,
                    kind=progress_kind_for_classification(result.classification),
                    summary=result.summary,
                    details={
                        "cloud_status": result.classification,
                        "cloud_run_id": updated.id,
                        "operation": operation,
                    },
                ),
                idempotency_key=deterministic_idempotency_key(
                    "resident-cloud-progress",
                    updated.id,
                    result.classification,
                    result.summary,
                ),
            )
        return updated

    def _require_confirmation(
        self,
        payload: ActorToolInput,
        *,
        action: ActionKind,
        tool_name: str,
        target_summary: str,
        request_id: str | None,
        phrase: str | None,
    ) -> ToolResult | None:
        if denied := self._denied(payload, action):
            return denied
        manager = self.confirmation_manager
        if manager is None or not manager.required_for(action):
            return None
        subject = self._subject(payload)
        if not request_id or not phrase:
            request = manager.request_confirmation(
                subject=subject,
                action=action,
                target_summary=target_summary,
                metadata={"tool": tool_name},
            )
            return ToolResult(
                ok=False,
                message="confirmation required",
                data={
                    "confirmation_required": True,
                    "request_id": request.id,
                    "exact_phrase": request.exact_phrase,
                    "expires_at": request.expires_at.isoformat().replace("+00:00", "Z"),
                    "target_summary": target_summary,
                },
            )
        decision = manager.confirm(request_id=request_id, subject=subject, phrase=phrase)
        if not decision.allowed:
            return ToolResult(
                ok=False,
                message=f"confirmation {decision.status}: {decision.reason}",
                data={"confirmation_required": True, "request_id": request_id, "reason": decision.reason},
            )
        return None

    def _denied(self, payload: ActorToolInput, action: ActionKind) -> ToolResult | None:
        if self.authorizer is None:
            return None
        subject = self._subject(payload)
        decision = self.authorizer.authorize_action(subject, action)
        if decision.allowed:
            return None
        return ToolResult(
            ok=False,
            message=f"authorization denied: {decision.reason}",
            data={"authorization_denied": True, "reason": decision.reason, "audit": decision.audit},
        )

    def _subject(self, payload: ActorToolInput) -> AuthorizationSubject:
        return AuthorizationSubject(
            user_id=payload.actor_user_id or self.actor_id,
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
        )

    def _store(self) -> Store:
        if self.store is None:
            raise RuntimeError("MegaplanResidentProfile requires a Store for default tools")
        return self.store

    def _require_epic(self, epic_id: str) -> Any:
        epic = self._store().load_epic(epic_id)
        if epic is None:
            raise CliError("unknown_epic", f"Epic {epic_id!r} was not found")
        return epic


def _ok(message: str, **data: Any) -> ToolResult:
    return ToolResult(ok=True, message=message, data=data)


def _fail(message: str, **data: Any) -> ToolResult:
    return ToolResult(ok=False, message=message, data=data)


def _exception_result(exc: Exception) -> ToolResult:
    code = getattr(exc, "code", exc.__class__.__name__)
    details = dict(getattr(exc, "extra", None) or getattr(exc, "details", None) or {})
    return ToolResult(ok=False, message=str(exc), data={"error": code, "details": details})


def _normalize_search(value: str) -> str:
    return " ".join(value.casefold().split())


def _message_result(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "epic_id": row.epic_id,
        "conversation_id": row.conversation_id,
        "direction": row.direction,
        "author_id": getattr(row, "author_id", None),
        "sent_at": row.sent_at.isoformat().replace("+00:00", "Z"),
        "snippet": _bounded_text(getattr(row, "snippet", None) or row.content, 280),
        "rank": getattr(row, "rank", None),
    }


def _epic_result(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "goal": row.goal,
        "state": row.state,
        "revision": row.revision,
        "last_edited_at": row.last_edited_at.isoformat().replace("+00:00", "Z"),
        "snippet": _bounded_text(getattr(row, "snippet", None) or row.body, 280),
        "rank": getattr(row, "rank", None),
        "match_tier": getattr(row, "match_tier", None),
    }


def _plan_result(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "epic_id": row.epic_id,
        "sprint_id": row.sprint_id,
        "revision": row.revision,
        "current_state": row.current_state,
        "iteration": row.iteration,
        "idea_snippet": _bounded_text(row.idea, 280),
        "updated_at": row.updated_at.isoformat().replace("+00:00", "Z"),
    }


def _codebase_result(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "owner": row.owner,
        "name": row.name,
        "repo_url": row.repo_url,
        "repo_workspace": getattr(row, "repo_workspace", None),
        "default_branch": row.default_branch,
        "scope": row.scope,
        "group_name": row.group_name,
        "associated_epic_id": row.associated_epic_id,
        "added_via": row.added_via,
        "verified_accessible_at": row.verified_accessible_at.isoformat().replace("+00:00", "Z") if row.verified_accessible_at else None,
        "last_accessed_at": row.last_accessed_at.isoformat().replace("+00:00", "Z") if row.last_accessed_at else None,
        "notes": _bounded_text(row.notes or "", 500) if row.notes else None,
    }


def _repo_result(row: Any) -> dict[str, Any]:
    return {
        "codebase_id": row.id,
        "owner": row.owner,
        "name": row.name,
        "repo_url": row.repo_url,
        "branch": row.default_branch,
        "workspace": getattr(row, "repo_workspace", None),
        "scope": row.scope,
        "associated_epic_id": row.associated_epic_id,
    }


def _cloud_target_summary(base: str, repo_args: dict[str, str]) -> str:
    if not repo_args:
        return base
    details = []
    if repo_url := repo_args.get("repo_url"):
        details.append(f"repo {repo_url}")
    if repo_branch := repo_args.get("repo_branch"):
        details.append(f"branch {repo_branch}")
    if repo_workspace := repo_args.get("repo_workspace"):
        details.append(f"workspace {repo_workspace}")
    if not details:
        return base
    return f"{base} ({', '.join(details)})"


def _code_artifact_result(row: Any) -> dict[str, Any]:
    metadata = dict(row.metadata or {})
    safe_metadata = {
        key: metadata[key]
        for key in sorted(metadata)
        if key in {"cache_key", "language", "symbol", "title", "source_url", "repo_url", "commit", "branch"}
        and isinstance(metadata[key], (str, int, float, bool, type(None)))
    }
    return {
        "id": row.id,
        "codebase_id": row.codebase_id,
        "epic_id": row.epic_id,
        "kind": row.kind,
        "source": row.source,
        "file_path": row.file_path,
        "line_range": row.line_range,
        "scope": row.scope,
        "content_summary": _bounded_text(row.content_summary or "", 500) if row.content_summary else None,
        "snippet": _bounded_text(row.content, 320),
        "content_size": len(row.content),
        "metadata_keys": sorted(metadata.keys()),
        "metadata": safe_metadata,
        "created_at": row.created_at.isoformat().replace("+00:00", "Z"),
        "expires_at": row.expires_at.isoformat().replace("+00:00", "Z") if row.expires_at else None,
    }


def _bounded_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "..."


def _recent_state_paths(roots: list[Path], state_dir_name: str, *, limit: int) -> list[Path]:
    paths: dict[str, Path] = {}
    for root in roots:
        try:
            matches = root.glob(f"**/.megaplan/plans/{state_dir_name}/*.json")
            for path in matches:
                try:
                    if path.is_file():
                        paths[str(path.resolve())] = path.resolve()
                except OSError:
                    continue
        except OSError:
            continue
    return sorted(paths.values(), key=lambda path: _path_mtime(path), reverse=True)[:limit]


def _summarize_epic_chain_visibility(
    local_state: dict[str, Any],
    live_cloud_chain: dict[str, Any] | None,
) -> dict[str, Any]:
    active_chains = local_state.get("active_chains") if isinstance(local_state, dict) else []
    active_chains = active_chains if isinstance(active_chains, list) else []
    primary = active_chains[0] if active_chains else None
    live_classification = live_cloud_chain.get("classification") if isinstance(live_cloud_chain, dict) else None
    if primary:
        return {
            "status": "active_from_local_state",
            "source": "local .megaplan chain state files",
            "active_chain_count": len(active_chains),
            "current_plan_name": primary.get("current_plan_name"),
            "last_state": primary.get("last_state"),
            "chain_spec_path": primary.get("chain_spec_path"),
            "work_dir": primary.get("work_dir"),
            "cloud_cli_classification": live_classification,
            "cloud_cli_note": (
                "Cloud CLI status is secondary here; local state files are authoritative inside the cloud container."
                if live_classification == "failed"
                else None
            ),
        }
    return {
        "status": "none_visible",
        "source": "local .megaplan chain state files",
        "active_chain_count": 0,
        "cloud_cli_classification": live_classification,
    }


def _summarize_plan_activity(
    local_state: dict[str, Any],
    live_cloud_chain: dict[str, Any] | None,
) -> dict[str, Any]:
    chains = local_state.get("chains") if isinstance(local_state, dict) else []
    chains = chains if isinstance(chains, list) else []
    active: list[dict[str, Any]] = []
    needs_attention: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    for row in chains:
        if not isinstance(row, dict):
            continue
        item = _plan_activity_item(row)
        if _chain_needs_attention(row):
            needs_attention.append(item)
        elif _chain_recently_completed(row):
            completed.append(item)
        elif _is_active_chain_state(row):
            active.append(item)
    live_classification = live_cloud_chain.get("classification") if isinstance(live_cloud_chain, dict) else None
    live_summary = live_cloud_chain.get("summary") if isinstance(live_cloud_chain, dict) else None
    return {
        "active_working": active[:5],
        "should_be_working_but_needs_attention": needs_attention[:5],
        "recently_completed": completed[:5],
        "live_cloud": {
            "classification": live_classification,
            "summary": live_summary,
        },
        "counts": {
            "active_working": len(active),
            "should_be_working_but_needs_attention": len(needs_attention),
            "recently_completed": len(completed),
            "visible_chains": len(chains),
        },
    }


def _summarize_epic_chain_state(path: Path) -> dict[str, Any]:
    data = _read_json_object(path)
    return {
        "path": str(path),
        "mtime": _path_mtime(path),
        "current_epic_id": data.get("current_epic_id"),
        "current_epic_index": data.get("current_epic_index"),
        "current_spec_path": data.get("current_spec_path"),
        "last_state": data.get("last_state"),
        "completed_count": len(data.get("completed") or []),
        "chain_session": data.get("chain_session"),
        "resolved_workspace": data.get("resolved_workspace"),
        "read_error": data.get("_read_error"),
    }


def _summarize_chain_state(path: Path) -> dict[str, Any]:
    data = _read_json_object(path)
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    execution_environment = (
        metadata.get("execution_environment")
        if isinstance(metadata.get("execution_environment"), dict)
        else {}
    )
    current_plan = data.get("current_plan_name")
    work_dir = execution_environment.get("work_dir") or execution_environment.get("project_root")
    plan_state = _summarize_plan_state(Path(str(work_dir)), str(current_plan)) if work_dir and current_plan else None
    return {
        "path": str(path),
        "mtime": _path_mtime(path),
        "current_plan_name": current_plan,
        "current_milestone_index": data.get("current_milestone_index"),
        "last_state": data.get("last_state"),
        "completed_count": len(data.get("completed") or []),
        "dirty_flag": data.get("dirty_flag"),
        "chain_spec_path": metadata.get("chain_spec_path"),
        "work_dir": work_dir,
        "chain_session": data.get("chain_session"),
        "plan_state": plan_state,
        "read_error": data.get("_read_error"),
    }


def _summarize_plan_state(work_dir: Path, plan_name: str) -> dict[str, Any] | None:
    candidates = [
        work_dir / ".megaplan" / "plans" / plan_name / "state.json",
        work_dir / ".megaplan" / "briefs" / plan_name / "state.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        data = _read_json_object(path)
        return {
            "path": str(path),
            "mtime": _path_mtime(path),
            "current_state": data.get("current_state") or data.get("state"),
            "iteration": data.get("iteration"),
            "active_step": _summarize_active_step(data.get("active_step")),
            "last_gate": _summarize_last_gate(data.get("last_gate")),
            "read_error": data.get("_read_error"),
        }
    return None


def _is_active_chain_state(row: dict[str, Any]) -> bool:
    if not row.get("current_plan_name") and not row.get("plan_state"):
        return False
    state = str(row.get("last_state") or "").lower()
    if state in {"done", "completed", "failed", "aborted", "finalized"}:
        return False
    plan_state = row.get("plan_state")
    if isinstance(plan_state, dict):
        plan_current_state = str(plan_state.get("current_state") or "").lower()
        if plan_current_state in {"done", "completed", "failed", "aborted"}:
            return False
    return True


def _chain_needs_attention(row: dict[str, Any]) -> bool:
    state = str(row.get("last_state") or "").lower().replace("-", "_")
    if any(token in state for token in ("awaiting_human", "blocked", "gate_needed", "needs_human", "stalled")):
        return True
    plan_state = row.get("plan_state")
    if isinstance(plan_state, dict):
        plan_current_state = str(plan_state.get("current_state") or "").lower().replace("-", "_")
        if any(token in plan_current_state for token in ("awaiting_human", "blocked", "paused", "stalled")):
            return True
        active_step = plan_state.get("active_step")
        if plan_current_state in {"initialized", "prepped", "planned", "gated", "finalized"} and active_step is None:
            return True
    return False


def _chain_recently_completed(row: dict[str, Any]) -> bool:
    state = str(row.get("last_state") or "").lower()
    if state in {"done", "completed", "finalized"}:
        return True
    plan_state = row.get("plan_state")
    if isinstance(plan_state, dict):
        plan_current_state = str(plan_state.get("current_state") or "").lower()
        return plan_current_state in {"done", "completed", "reviewed"}
    return False


def _plan_activity_item(row: dict[str, Any]) -> dict[str, Any]:
    plan_state = row.get("plan_state") if isinstance(row.get("plan_state"), dict) else {}
    active_step = plan_state.get("active_step") if isinstance(plan_state, dict) else None
    return {
        "current_plan_name": row.get("current_plan_name"),
        "last_state": row.get("last_state"),
        "plan_current_state": plan_state.get("current_state") if isinstance(plan_state, dict) else None,
        "active_step": active_step,
        "chain_spec_path": row.get("chain_spec_path"),
        "work_dir": row.get("work_dir"),
        "mtime": row.get("mtime"),
    }


def _summarize_active_step(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "phase": value.get("phase"),
        "agent": value.get("agent"),
        "attempt": value.get("attempt"),
        "mode": value.get("mode"),
        "started_at": value.get("started_at"),
        "last_activity_at": value.get("last_activity_at"),
        "last_activity_kind": value.get("last_activity_kind"),
        "last_activity_detail": value.get("last_activity_detail"),
    }


def _summarize_last_gate(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "recommendation": value.get("recommendation"),
        "passed": value.get("passed"),
        "rationale": _bounded_text(str(value.get("rationale") or ""), 500) if value.get("rationale") else None,
        "warnings": value.get("warnings") if isinstance(value.get("warnings"), list) else None,
    }


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": f"{exc.__class__.__name__}: {exc}"}
    return data if isinstance(data, dict) else {"_read_error": "state JSON was not an object"}


def _path_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "epic"


def _resident_project_root(value: str) -> Path:
    root = Path(value).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _safe_child_path(root: Path, relative: str) -> Path:
    if not relative or relative.strip() in {"", ".", ".."}:
        raise ValueError("filename must not be empty")
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("filename must be relative and stay inside the initiative")
    target = (root / rel).resolve()
    if not _is_relative_to(target, root):
        raise ValueError("filename escaped initiative document directory")
    return target


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _validate_git_url(repo_url: str) -> None:
    if not repo_url:
        raise ValueError("repo_url is required")
    if any(ch.isspace() for ch in repo_url):
        raise ValueError("repo_url must not contain whitespace")
    parsed = urlparse(repo_url)
    if parsed.scheme in {"https", "ssh"}:
        if not parsed.netloc or not parsed.path or parsed.path in {"/", ""}:
            raise ValueError("repo_url must include host and repository path")
        return
    if re.fullmatch(r"git@[A-Za-z0-9.-]+:[A-Za-z0-9._/-]+(?:\.git)?", repo_url):
        return
    raise ValueError("repo_url must be an HTTPS or SSH Git URL")


def _validate_repo_workspace(workspace: str | None) -> str | None:
    if workspace is None or workspace == "":
        return None
    if "\\" in workspace or "\x00" in workspace:
        raise ValueError("repo_workspace is unsafe")
    path = Path(workspace)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("repo_workspace is unsafe")
    return workspace


def _collect_basic_epic_export(store: Store, epic_id: str) -> dict[str, Any]:
    epic = store.load_epic(epic_id)
    if epic is None:
        raise FileNotFoundError(epic_id)
    files: list[dict[str, Any]] = []

    def add(path: str, kind: str, value: Any) -> None:
        data = (json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode("utf-8")
        files.append({"path": path, "kind": kind, "bytes": data, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    add("rows/epic.json", "row_json", epic.model_dump(mode="json"))
    add("rows/body.json", "row_json", store.load_body(epic_id))
    add("rows/checklist_items.json", "row_json", [row.model_dump(mode="json") for row in store.list_checklist_items(epic_id)])
    add("rows/sprints.json", "row_json", [row.model_dump(mode="json") for row in store.list_sprints(epic_id)])
    plans = store.list_plans(epic_id=epic_id, include_orphans=True)
    add("rows/plans.json", "row_json", [row.model_dump(mode="json") for row in plans])
    for plan in plans:
        for ref in store.list_plan_artifacts(plan.id):
            data = store.read_plan_artifact(plan.id, ref.name)
            if data is None:
                continue
            files.append({
                "path": f"plan_artifacts/{plan.id}/{ref.name}",
                "kind": "plan_artifact",
                "plan_id": plan.id,
                "artifact_name": ref.name,
                "bytes": data,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
    manifest = {
        "format": "megaplan-epic-export-v1",
        "epic_id": epic_id,
        "file_count": len(files),
        "files": [{key: value for key, value in file.items() if key != "bytes"} for file in sorted(files, key=lambda item: item["path"])],
        "warnings": [],
        "errors": [],
    }
    return {"epic_id": epic_id, "files": sorted(files, key=lambda item: item["path"]), "manifest": manifest, "warnings": [], "errors": []}
