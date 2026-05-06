"""Megaplan-specific resident bot profile and constrained tool surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from megaplan.control import ControlTargetResolver
from megaplan.editorial import body as editorial_body
from megaplan.editorial import checklist as editorial_checklist
from megaplan.editorial import gating as editorial_gating
from megaplan.editorial import sprints as editorial_sprints
from megaplan.store import (
    CloudRunInput,
    ControlMessageInput,
    ProgressEventInput,
    ScheduledJobInput,
    SprintItemInput,
    Store,
    deterministic_idempotency_key,
)
from megaplan.types import CliError

from .auth import AuthorizationSubject, ConfirmationManager, ResidentAuthorizer, StoreBackedConfirmationManager
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

MEGAPLAN_RESIDENT_PROMPT_VERSION = "megaplan-resident-v1"


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


class CloudResumeInput(CloudToolInput):
    plan: str | None = None


class CloudLogsInput(CloudToolInput):
    no_follow: bool = True


class ScheduleCloudCheckInput(CloudToolInput):
    interval_seconds: int = Field(default=60, gt=0)
    scheduled_for: datetime | None = None
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
            "run arbitrary remote shell commands."
        )

    async def load_hot_context(self, conversation_id: str) -> dict[str, Any]:
        base: dict[str, Any] = {
            "conversation_id": conversation_id,
            "prompt_version": MEGAPLAN_RESIDENT_PROMPT_VERSION,
        }
        if self.store is None:
            return base
        conversation = self.store.load_resident_conversation(conversation_id)
        if conversation is None:
            return base
        active_epic_id = conversation.active_epic_id
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

    def tools(self) -> ToolRegistry:
        return self.tool_registry

    def _register_default_tools(self) -> None:
        assert self.store is not None
        registrations = (
            ToolRegistration("create_epic", "Create a new Megaplan epic.", "write", CreateEpicInput, ToolResult, self._create_epic),
            ToolRegistration("select_epic", "Select the active epic for a resident conversation.", "write", SelectEpicInput, ToolResult, self._select_epic),
            ToolRegistration("read_epic", "Read an epic body, checklist, and sprints.", "read", EpicInput, ToolResult, self._read_epic),
            ToolRegistration("edit_epic_body", "Replace an epic body using expected_revision.", "write", EditEpicBodyInput, ToolResult, self._edit_epic_body),
            ToolRegistration("add_checklist_items", "Add checklist items to an epic.", "write", AddChecklistItemsInput, ToolResult, self._add_checklist_items),
            ToolRegistration("update_checklist_item", "Update one checklist item.", "write", UpdateChecklistItemInput, ToolResult, self._update_checklist_item),
            ToolRegistration("create_or_update_sprints", "Create or update sprints and their items.", "write", CreateOrUpdateSprintsInput, ToolResult, self._create_or_update_sprints),
            ToolRegistration("queue_sprints", "Queue or mark pending sprints.", "write", QueueSprintsInput, ToolResult, self._queue_sprints),
            ToolRegistration("transition_epic_state", "Transition an epic through editorial gates.", "write", TransitionEpicStateInput, ToolResult, self._transition_epic_state),
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
        )
        for registration in registrations:
            self.tool_registry.register(registration)

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
        if confirm := self._require_cloud_confirmation(
            payload,
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
        if confirm := self._require_cloud_confirmation(
            payload,
            tool_name="cloud_start_chain",
            target_summary=f"chain {payload.spec}",
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
        )

    async def _cloud_bootstrap(self, payload: CloudBootstrapInput) -> ToolResult:
        if confirm := self._require_cloud_confirmation(
            payload,
            tool_name="cloud_bootstrap",
            target_summary=f"bootstrap {payload.idea_file}",
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
        )

    async def _cloud_resume(self, payload: CloudResumeInput) -> ToolResult:
        if denied := self._denied(payload, "admin"):
            return denied
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

    async def _run_cloud_tool(
        self,
        *,
        operation: CloudOperation,
        payload: CloudToolInput,
        run_operation: str,
        arguments: dict[str, Any],
        target_id: str | None,
        command_summary: str,
    ) -> ToolResult:
        action = "cloud_read" if operation in {"cloud_status", "cloud_status_chain", "cloud_logs"} else "admin"
        if denied := self._denied(payload, action):
            return denied
        try:
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

    def _require_cloud_confirmation(
        self,
        payload: ActorToolInput,
        *,
        tool_name: str,
        target_summary: str,
        request_id: str | None,
        phrase: str | None,
    ) -> ToolResult | None:
        if denied := self._denied(payload, "cloud_start"):
            return denied
        manager = self.confirmation_manager
        if manager is None or not manager.required_for("cloud_start"):
            return None
        subject = self._subject(payload)
        if not request_id or not phrase:
            request = manager.request_confirmation(
                subject=subject,
                action="cloud_start",
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

    def _denied(self, payload: ActorToolInput, action: str) -> ToolResult | None:
        if self.authorizer is None:
            return None
        subject = self._subject(payload)
        decision = self.authorizer.authorize_action(subject, action)  # type: ignore[arg-type]
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
