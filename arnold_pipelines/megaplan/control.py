"""Discord-independent control-plane target resolution and processing.

Sprint 6 intentionally keeps this module free of Discord concepts. Arnold or
any other client writes ControlMessage rows; megaplan validates the requested
workflow target before later processor code dispatches to existing handlers.

Crash semantics: claimed-but-unprocessed control messages can be stranded if a
processor dies after claim and before mark_processed. Sprint 6 documents that
gap explicitly and does not implement stale-claim retry; Sprint 7 hardening can
add lease expiry/reclaim behavior without changing the result contract below.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import traceback
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan._core import save_state, slugify
from arnold_pipelines.megaplan._core.workflow import resume_plan
from arnold_pipelines.megaplan.auto import drive as drive_auto
from arnold_pipelines.megaplan.runtime.process import megaplan_engine_env
from arnold.control.interface import RunStateView
from arnold_pipelines.megaplan.control_interface import apply_transition, build_override_transition_request
from arnold_pipelines.megaplan.handlers import handle_init
from arnold_pipelines.megaplan.orchestration.progress import ProgressContext, ProgressEmitter
from arnold_pipelines.megaplan.schemas import ControlMessage, Sprint
from arnold_pipelines.megaplan.store import Store
from arnold_pipelines.megaplan.types import CliError


SUPPORTED_CONTROL_INTENTS = {"run_sprint", "resume_plan", "approve_gate", "reject_gate"}
GATE_CONTROL_INTENTS = {"approve_gate", "reject_gate"}


@dataclass(frozen=True)
class ControlTarget:
    """Megaplan control-message target, distinct from arnold.control.interface.ControlTarget."""

    intent: str
    target_id: str
    project_root: Path
    epic_id: str | None = None
    plan: str | None = None
    plan_dir: Path | None = None
    sprint_id: str | None = None
    sprint_number: int | None = None
    gate_id: str | None = None
    progress_context: ProgressContext | None = None
    payload: dict[str, Any] | None = None


ControlHandler = Callable[[ControlTarget, ControlMessage], Mapping[str, Any] | None]


def _drop_next_step_authority(response: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = dict(response)
    sanitized.pop("next_step", None)
    sanitized.pop("next_step_runtime", None)
    return sanitized


class ControlTargetResolver:
    """Validate control-message payloads and resolve runnable workflow targets."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def resolve(self, intent: str, target_id: str, payload: Mapping[str, Any] | None) -> ControlTarget:
        data = dict(payload or {})
        project_root = self._project_root(data)
        progress_context = self._progress_context(data)

        if intent == "run_sprint":
            return self._resolve_run_sprint(target_id, data, project_root, progress_context)
        if intent == "resume_plan":
            return self._resolve_plan_target(intent, target_id, data, project_root, progress_context)
        if intent in GATE_CONTROL_INTENTS:
            return self._resolve_gate_target(intent, target_id, data, project_root, progress_context)
        raise CliError(
            "unsupported_control_intent",
            f"Unsupported control intent {intent!r}",
            extra={"intent": intent, "supported": sorted(SUPPORTED_CONTROL_INTENTS)},
        )

    def _project_root(self, payload: Mapping[str, Any]) -> Path:
        raw = payload.get("project_root")
        if not isinstance(raw, str) or not raw.strip():
            raise CliError("missing_project_root", "Control message payload requires project_root")
        root = Path(raw).expanduser()
        if not root.exists() or not root.is_dir():
            raise CliError("invalid_project_root", f"Control project_root does not exist: {raw}")
        return root.resolve()

    def _progress_context(self, payload: Mapping[str, Any]) -> ProgressContext | None:
        raw = payload.get("progress_context")
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise CliError("invalid_progress_context", "progress_context must be an object")
        try:
            return ProgressContext(**dict(raw))
        except (TypeError, ValueError) as error:
            raise CliError("invalid_progress_context", str(error)) from error

    def _resolve_run_sprint(
        self,
        target_id: str,
        payload: Mapping[str, Any],
        project_root: Path,
        progress_context: ProgressContext | None,
    ) -> ControlTarget:
        epic_id = self._require_epic(payload)
        sprint = self._resolve_sprint(epic_id, target_id)
        plan = self._optional_plan_name(payload)
        plan_dir = self._load_plan_dir(project_root, plan) if plan else None
        if plan_dir is not None:
            state = self._read_plan_state(plan_dir)
            self._validate_plan_identity(state, epic_id=epic_id, sprint_id=sprint.id)
        return ControlTarget(
            intent="run_sprint",
            target_id=target_id,
            project_root=project_root,
            epic_id=epic_id,
            plan=plan,
            plan_dir=plan_dir,
            sprint_id=sprint.id,
            sprint_number=sprint.sprint_number,
            progress_context=progress_context,
            payload=dict(payload),
        )

    def _resolve_plan_target(
        self,
        intent: str,
        target_id: str,
        payload: Mapping[str, Any],
        project_root: Path,
        progress_context: ProgressContext | None,
    ) -> ControlTarget:
        plan = self._plan_name(payload, target_id)
        plan_dir = self._require_plan_dir(project_root, plan)
        state = self._read_plan_state(plan_dir)
        epic_id = self._optional_string(payload, "epic_id")
        sprint_id = self._optional_string(payload, "sprint_id")
        self._validate_plan_identity(state, epic_id=epic_id, sprint_id=sprint_id)
        meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
        return ControlTarget(
            intent=intent,
            target_id=target_id,
            project_root=project_root,
            epic_id=epic_id or self._state_string(meta, "epic_id"),
            plan=plan,
            plan_dir=plan_dir,
            sprint_id=sprint_id or self._state_string(meta, "sprint_id"),
            progress_context=progress_context,
            payload=dict(payload),
        )

    def _resolve_gate_target(
        self,
        intent: str,
        target_id: str,
        payload: Mapping[str, Any],
        project_root: Path,
        progress_context: ProgressContext | None,
    ) -> ControlTarget:
        if not isinstance(target_id, str) or not target_id.strip():
            raise CliError("invalid_gate_payload", "Gate control requires a non-empty gate target_id")
        target = self._resolve_plan_target(intent, target_id, payload, project_root, progress_context)
        return ControlTarget(
            **{
                **target.__dict__,
                "gate_id": target_id,
            }
        )

    def _resolve_sprint(self, epic_id: str, target_id: str) -> Sprint:
        sprint = self.store.load_sprint(target_id)
        if sprint is None and target_id.isdigit():
            sprint_number = int(target_id)
            matches = [row for row in self.store.list_sprints(epic_id) if row.sprint_number == sprint_number]
            sprint = matches[0] if matches else None
        if sprint is None or sprint.epic_id != epic_id:
            raise CliError("unknown_sprint", f"Sprint {target_id!r} was not found for epic {epic_id!r}")
        return sprint

    def _require_epic(self, payload: Mapping[str, Any]) -> str:
        epic_id = self._optional_string(payload, "epic_id")
        if epic_id is None:
            raise CliError("missing_epic", "Control message payload requires epic_id")
        if self.store.load_epic(epic_id) is None:
            raise CliError("unknown_epic", f"Epic {epic_id!r} was not found")
        return epic_id

    def _optional_plan_name(self, payload: Mapping[str, Any]) -> str | None:
        raw = payload.get("plan")
        if raw is None:
            return None
        if not isinstance(raw, str) or not raw.strip():
            raise CliError("invalid_plan", "Control message payload plan must be a non-empty string")
        return raw.strip()

    def _plan_name(self, payload: Mapping[str, Any], target_id: str) -> str:
        plan = self._optional_plan_name(payload)
        if plan:
            return plan
        if isinstance(target_id, str) and target_id.strip():
            return target_id.strip()
        raise CliError("invalid_plan", "Control message requires a plan name")

    def _load_plan_dir(self, project_root: Path, plan: str) -> Path | None:
        plan_dir = project_root / ".megaplan" / "plans" / plan
        if plan_dir.is_dir() and (plan_dir / "state.json").is_file():
            return plan_dir
        return None

    def _require_plan_dir(self, project_root: Path, plan: str) -> Path:
        plan_dir = self._load_plan_dir(project_root, plan)
        if plan_dir is not None:
            return plan_dir
        store_plan = self.store.load_plan(plan)
        if store_plan is not None:
            raise CliError(
                "missing_filesystem_plan",
                f"Plan {plan!r} exists in Store metadata but has no runnable state.json",
                extra={"plan": plan},
            )
        raise CliError("unknown_plan", f"Plan {plan!r} was not found under {project_root}")

    def _read_plan_state(self, plan_dir: Path) -> dict[str, Any]:
        try:
            from arnold_pipelines.megaplan._core.io import read_plan_state_cached
            state = read_plan_state_cached(plan_dir, mode="authority")
        except Exception as error:
            raise CliError("invalid_plan_state", f"Failed to read {plan_dir / 'state.json'}: {error}") from error
        if not isinstance(state, dict):
            raise CliError("invalid_plan_state", f"{plan_dir / 'state.json'} must contain a JSON object")
        return state

    def _validate_plan_identity(
        self,
        state: Mapping[str, Any],
        *,
        epic_id: str | None,
        sprint_id: str | None,
    ) -> None:
        meta = state.get("meta") if isinstance(state.get("meta"), Mapping) else {}
        actual_epic_id = self._state_string(meta, "epic_id")
        actual_sprint_id = self._state_string(meta, "sprint_id")
        if epic_id is not None and actual_epic_id is not None and epic_id != actual_epic_id:
            raise CliError("epic_mismatch", f"Plan epic_id {actual_epic_id!r} does not match {epic_id!r}")
        if sprint_id is not None and actual_sprint_id is not None and sprint_id != actual_sprint_id:
            raise CliError("sprint_mismatch", f"Plan sprint_id {actual_sprint_id!r} does not match {sprint_id!r}")

    def _optional_string(self, payload: Mapping[str, Any], key: str) -> str | None:
        raw = payload.get(key)
        if raw is None:
            return None
        if not isinstance(raw, str) or not raw.strip():
            raise CliError(f"invalid_{key}", f"{key} must be a non-empty string")
        return raw.strip()

    def _state_string(self, payload: Mapping[str, Any], key: str) -> str | None:
        raw = payload.get(key)
        return raw if isinstance(raw, str) and raw else None


class ControlProcessor:
    """Claim pending control messages and record one structured result per claim."""

    def __init__(
        self,
        store: Store,
        *,
        processor_id: str,
        resolver: ControlTargetResolver | None = None,
        handlers: Mapping[str, ControlHandler] | None = None,
    ) -> None:
        if not processor_id.strip():
            raise ValueError("processor_id must be non-empty")
        self.store = store
        self.processor_id = processor_id
        self.resolver = resolver or ControlTargetResolver(store)
        self.handlers = _default_handlers(store)
        self.handlers.update(dict(handlers or {}))

    def process_pending(self, *, max: int = 10) -> list[dict[str, Any]]:
        claimed = self.store.claim_pending_control_messages(processor_id=self.processor_id, max=max)
        results: list[dict[str, Any]] = []
        for message in claimed:
            result = self._process_one(message)
            self.store.mark_control_message_processed(
                message.id,
                result,
                idempotency_key=f"control-processed:{message.id}",
            )
            results.append(result)
        return results

    def _process_one(self, message: ControlMessage) -> dict[str, Any]:
        base = {
            "message_id": message.id,
            "intent": message.intent,
            "target_id": message.target_id,
            "processor_id": self.processor_id,
        }
        if message.intent not in SUPPORTED_CONTROL_INTENTS:
            return {
                **base,
                "status": "unsupported",
                "ok": False,
                "error": {
                    "code": "unsupported_control_intent",
                    "message": f"Unsupported control intent {message.intent!r}",
                },
            }
        handler = self.handlers.get(message.intent)
        if handler is None:
            return {
                **base,
                "status": "unsupported",
                "ok": False,
                "error": {
                    "code": "control_handler_unimplemented",
                    "message": f"Control intent {message.intent!r} is valid but has no processor handler",
                },
            }
        try:
            target = self.resolver.resolve(message.intent, message.target_id, message.payload)
            details = handler(target, message)
            return {
                **base,
                "status": "success",
                "ok": True,
                "target": _target_result(target),
                "details": dict(details or {}),
            }
        except CliError as error:
            return {
                **base,
                "status": "failure",
                "ok": False,
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "details": dict(error.extra or {}),
                },
            }
        except Exception as error:  # pragma: no cover - exact exception type is handler-defined.
            return {
                **base,
                "status": "failure",
                "ok": False,
                "error": {
                    "code": "control_handler_exception",
                    "message": str(error),
                    "type": type(error).__name__,
                    "traceback": traceback.format_exception_only(type(error), error)[-1].strip(),
                },
            }


def _target_result(target: ControlTarget) -> dict[str, Any]:
    return {
        "intent": target.intent,
        "epic_id": target.epic_id,
        "plan": target.plan,
        "plan_dir": str(target.plan_dir) if target.plan_dir is not None else None,
        "sprint_id": target.sprint_id,
        "sprint_number": target.sprint_number,
        "gate_id": target.gate_id,
    }


def _default_handlers(store: Store) -> dict[str, ControlHandler]:
    return {
        "run_sprint": lambda target, message: _run_sprint_control_event_request_adapter(
            target, message, store=store
        ),
        "resume_plan": lambda target, message: _resume_plan_control_event_request_adapter(
            target, message, store=store
        ),
        "approve_gate": lambda target, message: _approve_gate_control_event_request_adapter(
            target, message, store=store
        ),
        "reject_gate": lambda target, message: _reject_gate_control_event_request_adapter(
            target, message, store=store
        ),
    }


def _run_sprint_control_event_request_adapter(
    target: ControlTarget,
    message: ControlMessage,
    *,
    store: Store,
) -> dict[str, Any]:
    if target.intent != "run_sprint" or target.epic_id is None or target.sprint_id is None:
        raise CliError("invalid_control_target", "run_sprint handler requires a resolved sprint target")
    sprint = store.load_sprint(target.sprint_id)
    if sprint is None:
        raise CliError("unknown_sprint", f"Sprint {target.sprint_id!r} was not found")
    plan = target.plan or _default_sprint_plan_name(sprint)
    plan_dir = target.plan_dir or _plan_dir(target.project_root, plan)
    created = False
    if target.plan_dir is None:
        idea = _build_sprint_idea(target, sprint, store)
        response = handle_init(target.project_root, _init_args(target.project_root, plan, idea, message.payload))
        if not response.get("success"):
            raise CliError("run_sprint_init_failed", f"Plan initialization failed for {plan!r}", extra={"response": response})
        created = True
        plan_dir = _plan_dir(target.project_root, plan)
        from arnold_pipelines.megaplan._core.io import read_plan_state_cached
        state = read_plan_state_cached(plan_dir, mode="authority")
        meta = state.get("meta") if isinstance(state.get("meta"), dict) else {}
        state["meta"] = {**meta, "epic_id": target.epic_id, "sprint_id": target.sprint_id}
        save_state(plan_dir, state)
    if not (plan_dir / "state.json").is_file():
        raise CliError("missing_filesystem_plan", f"run_sprint requires runnable state.json for plan {plan!r}")
    progress_env = _progress_env_for_target(target, plan)
    outcome = drive_auto(
        plan,
        cwd=target.project_root,
        progress_env=progress_env,
    )
    return {
        "plan": plan,
        "plan_dir": str(plan_dir),
        "sprint_id": target.sprint_id,
        "sprint_number": sprint.sprint_number,
        "created_plan": created,
        "auto_outcome": {
            "status": outcome.status,
            "final_state": outcome.final_state,
            "iterations": outcome.iterations,
            "reason": outcome.reason,
            "last_phase": outcome.last_phase,
        },
    }


def run_sprint_control_handler(target: ControlTarget, message: ControlMessage, *, store: Store) -> dict[str, Any]:
    """Legacy entry-point name retained as an event-request adapter."""

    return _run_sprint_control_event_request_adapter(target, message, store=store)


def _resume_plan_control_event_request_adapter(
    target: ControlTarget,
    message: ControlMessage,
    *,
    store: Store,
) -> dict[str, Any]:
    del message
    if target.intent != "resume_plan" or target.plan is None:
        raise CliError("invalid_control_target", "resume_plan handler requires a resolved plan target")
    progress_env = _progress_env_for_target(target, target.plan)
    response = resume_plan(
        target.project_root,
        target.plan,
        store=store,
        runner=_resume_runner(progress_env),
    )
    details: dict[str, Any] = {"resume": response}
    if _should_auto_continue(target.payload):
        outcome = drive_auto(target.plan, cwd=target.project_root, progress_env=progress_env)
        details["auto_outcome"] = _auto_outcome(outcome)
    return details


def resume_plan_control_handler(target: ControlTarget, message: ControlMessage, *, store: Store) -> dict[str, Any]:
    """Legacy entry-point name retained as an event-request adapter."""

    return _resume_plan_control_event_request_adapter(target, message, store=store)


def _approve_gate_control_event_request_adapter(
    target: ControlTarget,
    message: ControlMessage,
    *,
    store: Store,
) -> dict[str, Any]:
    if target.intent != "approve_gate" or target.plan is None or target.gate_id is None:
        raise CliError("invalid_control_target", "approve_gate handler requires a resolved gate target")
    payload = target.payload or {}
    reason = _payload_text(payload, "reason", "Approved from control message.")
    response = _apply_gate_control_request(
        target,
        message,
        action="force-proceed",
        payload={"user_approved": True},
        reason=reason,
    )
    response = _drop_next_step_authority(response)
    event = _gate_resolved(target, store, decision="approved", summary=str(response.get("summary") or "Gate approved"))
    details: dict[str, Any] = {
        "gate": response,
        "progress_event_id": getattr(event, "id", None) if event is not None else None,
    }
    if _should_auto_continue(payload):
        progress_env = _progress_env_for_target(target, target.plan)
        outcome = drive_auto(target.plan, cwd=target.project_root, progress_env=progress_env)
        details["auto_outcome"] = _auto_outcome(outcome)
    return details


def approve_gate_control_handler(target: ControlTarget, message: ControlMessage, *, store: Store) -> dict[str, Any]:
    """Legacy entry-point name retained as an event-request adapter."""

    return _approve_gate_control_event_request_adapter(target, message, store=store)


def _reject_gate_control_event_request_adapter(
    target: ControlTarget,
    message: ControlMessage,
    *,
    store: Store,
) -> dict[str, Any]:
    if target.intent != "reject_gate" or target.plan is None or target.gate_id is None:
        raise CliError("invalid_control_target", "reject_gate handler requires a resolved gate target")
    payload = target.payload or {}
    reason = _payload_text(payload, "reason", "Gate rejected from control message.")
    note = _payload_text(payload, "note", reason)
    response = _apply_gate_control_request(
        target,
        message,
        action="add-note",
        payload={},
        note=note,
        reason=reason,
        source="user",
    )
    response = _drop_next_step_authority(response)
    event = _gate_resolved(target, store, decision="rejected", summary=str(response.get("summary") or "Gate rejected"))
    return {
        "gate": response,
        "progress_event_id": getattr(event, "id", None) if event is not None else None,
    }


def reject_gate_control_handler(target: ControlTarget, message: ControlMessage, *, store: Store) -> dict[str, Any]:
    """Legacy entry-point name retained as an event-request adapter."""

    return _reject_gate_control_event_request_adapter(target, message, store=store)


def _apply_gate_control_request(
    target: ControlTarget,
    message: ControlMessage,
    *,
    action: str,
    payload: Mapping[str, Any],
    reason: str,
    note: str | None = None,
    source: str = "control_message",
) -> dict[str, Any]:
    if target.plan is None or target.plan_dir is None:
        raise CliError("invalid_control_target", "gate control requires a resolved filesystem plan")

    from arnold_pipelines.megaplan._core.io import read_plan_state_cached
    from arnold_pipelines.megaplan.handlers.override import _emit_routed_override_events, _routed_override_response

    state = read_plan_state_cached(target.plan_dir, mode="authority")
    transition = build_override_transition_request(
        action,
        params={
            **dict(payload),
            "root": str(target.project_root),
            "plan_dir": str(target.plan_dir),
        },
        actor=message.actor_id,
        source=source,
        reason=reason,
        note=note,
        metadata={
            "control_intent": target.intent,
            "control_message_id": message.id,
        },
        idempotency_key=f"control-message:{message.id}:{action}",
    )
    result = apply_transition(
        RunStateView(
            run_id=state.get("name", target.plan),
            cursor=state.get("current_state"),
            raw_state=state,
        ),
        transition,
        "megaplan",
        plan_dir=target.plan_dir,
    )
    if not result.accepted:
        if result.reason == "control_transition_conflict":
            raise CliError(
                "invalid_transition",
                result.reason,
                extra={"conflict": result.artifacts.get("conflict")},
            )
        raise CliError("invalid_transition", result.reason or "control transition rejected")

    persisted_state = read_plan_state_cached(target.plan_dir, mode="authority")
    args = _override_args(
        plan=target.plan,
        action=action,
        reason=reason,
        note=note,
        source=source,
        user_approved=bool(payload.get("user_approved", False)),
    )
    _emit_routed_override_events(action, plan_dir=target.plan_dir, state=persisted_state, args=args)
    return _drop_next_step_authority(
        _routed_override_response(
            action,
            plan_dir=target.plan_dir,
            state=persisted_state,
            args=args,
            artifacts=dict(result.artifacts),
        )
    )


def _default_sprint_plan_name(sprint: Sprint) -> str:
    return f"sprint-{sprint.sprint_number}-{slugify(sprint.name or sprint.goal)}"


def _resume_runner(progress_env: dict[str, str] | None) -> Callable[[list[str], Path | None], tuple[int, str, str]]:
    def run(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
        env = megaplan_engine_env(dict(os.environ))
        env["PYTHONSAFEPATH"] = "1"
        if progress_env:
            env.update(progress_env)
        proc = subprocess.run(
            [sys.executable, "-P", "-m", "arnold_pipelines.megaplan", *args],
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr

    return run


def _override_args(
    *,
    plan: str,
    action: str,
    reason: str = "",
    note: str | None = None,
    source: str = "user",
    user_approved: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        plan=plan,
        override_action=action,
        reason=reason,
        note=note,
        source=source,
        user_approved=user_approved,
        robustness=None,
        profile=None,
    )


def _payload_text(payload: Mapping[str, Any], key: str, default: str) -> str:
    raw = payload.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return default


def _should_auto_continue(payload: Mapping[str, Any] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    return bool(payload.get("auto_continue") or payload.get("continue"))


def _gate_resolved(target: ControlTarget, store: Store, *, decision: str, summary: str) -> Any:
    if target.gate_id is None:
        return None
    return ProgressEmitter(
        store=store,
        context=target.progress_context,
        epic_id=target.epic_id,
        plan_id=target.plan,
        sprint_id=target.sprint_id,
    ).gate_resolved(
        target.gate_id,
        decision,
        summary=summary,
    )


def _auto_outcome(outcome: Any) -> dict[str, Any]:
    return {
        "status": outcome.status,
        "final_state": outcome.final_state,
        "iterations": outcome.iterations,
        "reason": outcome.reason,
        "last_phase": outcome.last_phase,
    }


def _plan_dir(project_root: Path, plan: str) -> Path:
    return project_root / ".megaplan" / "plans" / plan


def _build_sprint_idea(target: ControlTarget, sprint: Sprint, store: Store) -> str:
    items = [item.content.strip() for item in store.list_sprint_items(sprint.id) if item.content.strip()]
    lines = [
        f"Run sprint {sprint.sprint_number}: {sprint.name}",
        "",
        f"Epic ID: {target.epic_id}",
        f"Sprint ID: {target.sprint_id}",
        "",
        "Sprint goal:",
        sprint.goal,
    ]
    if items:
        lines.extend(["", "Sprint items:", *[f"- {item}" for item in items]])
    return "\n".join(lines).strip()


def _init_args(project_root: Path, plan: str, idea: str, payload: Mapping[str, Any]) -> argparse.Namespace:
    return argparse.Namespace(
        idea=idea,
        idea_file=None,
        name=plan,
        project_dir=str(project_root),
        auto_approve=payload.get("auto_approve"),
        robustness=payload.get("robustness"),
        mode=payload.get("mode") or "code",
        output=payload.get("output"),
        primary_criterion=payload.get("primary_criterion"),
        form=payload.get("form"),
        from_doc=payload.get("from_doc"),
        phase_model=payload.get("phase_model") or [],
        strict_notes=payload.get("strict_notes"),
        profile=payload.get("profile"),
        hermes=payload.get("hermes"),
        auto_start=False,
    )


def _progress_env_for_target(target: ControlTarget, plan: str) -> dict[str, str] | None:
    if target.progress_context is None:
        return None
    context = replace(
        target.progress_context,
        epic_id=target.progress_context.epic_id or target.epic_id,
        plan_id=target.progress_context.plan_id or plan,
        sprint_id=target.progress_context.sprint_id or target.sprint_id,
    )
    return context.to_env()


def process_pending_control_messages(
    store: Store,
    *,
    processor_id: str,
    max: int = 10,
    resolver: ControlTargetResolver | None = None,
    handlers: Mapping[str, ControlHandler] | None = None,
) -> list[dict[str, Any]]:
    return ControlProcessor(
        store,
        processor_id=processor_id,
        resolver=resolver,
        handlers=handlers,
    ).process_pending(max=max)


__all__ = [
    "ControlHandler",
    "ControlProcessor",
    "ControlTarget",
    "ControlTargetResolver",
    "GATE_CONTROL_INTENTS",
    "SUPPORTED_CONTROL_INTENTS",
    "process_pending_control_messages",
    "run_sprint_control_handler",
]
