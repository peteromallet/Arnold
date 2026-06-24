"""Canonical planning operation dispatch for the Megaplan pipeline."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import io
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from arnold.runtime.operations import (
    OperationKind,
    OperationRegistry,
    OperationRequest,
    OperationResult,
)
from arnold.control.interface import (
    ControlTransition,
    ControlTransitionRequest,
    RunStateView,
)
from arnold.pipelines.megaplan.control_interface import apply_transition
from arnold.pipelines.megaplan.planning.control_binding import (
    planning_control_binding,
    planning_run_state_view,
)
from arnold.pipelines.megaplan.planning.validation import preflight_or_raise, profile_validate_operation
from arnold.pipelines.megaplan.types import CliError

SUPPORTED_OPERATIONS = frozenset(
    {
        OperationKind.EXECUTE,
        OperationKind.STATUS_PROJECTION,
        OperationKind.RESUME,
        OperationKind.OVERRIDE_LIST,
        OperationKind.OVERRIDE_APPLY,
        OperationKind.PROFILE_VALIDATE,
    }
)

_OVERRIDE_CATALOG: dict[str, dict[str, Any]] = {
    "add-note": {"kind": "annotation"},
    "abort": {"kind": "termination"},
    "force-proceed": {"kind": "transition"},
    "recover-blocked": {"kind": "recovery"},
    "replan": {"kind": "transition"},
    "resume-clarify": {"kind": "recovery"},
    "set-model": {"kind": "config"},
    "set-profile": {"kind": "config"},
    "set-robustness": {"kind": "config"},
    "set-vendor": {"kind": "config"},
}


def override_catalog() -> dict[str, dict[str, Any]]:
    return {name: dict(meta) for name, meta in _OVERRIDE_CATALOG.items()}


def resume_phase_args(cursor: Mapping[str, Any], plan: str) -> list[str]:
    phase = cursor.get("phase")
    if not isinstance(phase, str) or not phase:
        raise CliError(
            "invalid_resume_cursor",
            "resume cursor requires a non-empty phase",
            extra={"resume_cursor": dict(cursor)},
        )
    args = [phase, "--plan", plan]
    if phase == "execute":
        args.extend(["--confirm-destructive", "--user-approved"])
        batch_index = cursor.get("batch_index")
        if isinstance(batch_index, int) and batch_index > 0:
            args.extend(["--batch", str(batch_index)])
    return args


class _RunPhaseCompatiblePipeline:
    """Compatibility wrapper exposing legacy ``run_phase`` on native pipelines."""

    def __init__(self, pipeline: Any) -> None:
        self._pipeline = pipeline

    def __getattr__(self, name: str) -> Any:
        return getattr(self._pipeline, name)

    def _phase_step_with_overrides(self, phase: str, overrides: Mapping[str, Any]) -> Any | None:
        from arnold.pipelines.megaplan.stages.critique import CritiqueStep
        from arnold.pipelines.megaplan.stages.execute import ExecuteStep
        from arnold.pipelines.megaplan.stages.finalize import FinalizeStep
        from arnold.pipelines.megaplan.stages.gate import GateStep
        from arnold.pipelines.megaplan.stages.plan import PlanStep
        from arnold.pipelines.megaplan.stages.prep import PrepStep
        from arnold.pipelines.megaplan.stages.revise import ReviseStep
        from arnold.pipelines.megaplan.stages.review import ReviewStep
        from arnold.pipelines.megaplan._pipeline.steps.tiebreaker import TiebreakerStep

        factories: dict[str, Callable[..., Any]] = {
            "prep": PrepStep,
            "plan": PlanStep,
            "critique": CritiqueStep,
            "gate": GateStep,
            "revise": ReviseStep,
            "finalize": FinalizeStep,
            "execute": ExecuteStep,
            "review": ReviewStep,
            "tiebreaker": TiebreakerStep,
        }
        factory = factories.get(phase)
        if factory is None:
            return None
        return factory(arg_overrides=dict(overrides))

    def run_phase(
        self,
        phase: str,
        *,
        plan: str,
        cwd: Path | None = None,
        plan_dir: Path | None = None,
        argv: list[str] | tuple[str, ...] | None = None,
        progress_env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        from arnold.pipelines.megaplan._core import find_plan_dir
        from arnold.pipelines.megaplan._core.io import json_dump
        from arnold.pipelines.megaplan._pipeline.types import (
            StepContext,
            _phase_arg_overrides,
            _phase_namespace,
            _read_phase_state,
        )
        from arnold.pipelines.megaplan.types import CliError

        root = Path(cwd or Path.cwd())
        resolved_plan_dir = Path(plan_dir) if plan_dir is not None else find_plan_dir(root, plan)
        if resolved_plan_dir is None:
            return 1, "", f"Plan {plan!r} does not exist"

        stdout = io.StringIO()
        stderr = io.StringIO()

        try:
            if phase == "feedback" and phase not in self.stages:
                from arnold.pipelines.megaplan.cli.feedback import handle_feedback

                args = _phase_namespace(
                    phase,
                    plan=plan,
                    argv=argv,
                    progress_env=progress_env,
                )
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    response = handle_feedback(root, args)
                return 0, stdout.getvalue() or json_dump(response), stderr.getvalue()

            if phase not in self.stages:
                return 1, "", f"phase {phase!r} is not in pipeline; available: {sorted(self.stages)}"

            node = self.stages[phase]
            if not hasattr(node, "step"):
                return 1, "", f"phase {phase!r} is not a single-stage phase"

            state = _read_phase_state(resolved_plan_dir)
            overrides = _phase_arg_overrides(phase, argv=argv)
            step = node.step
            if overrides:
                if hasattr(step, "arg_overrides") and dataclasses.is_dataclass(step):
                    current = getattr(step, "arg_overrides", {}) or {}
                    step = dataclasses.replace(step, arg_overrides={**dict(current), **overrides})
                else:
                    override_step = self._phase_step_with_overrides(phase, overrides)
                    if override_step is not None:
                        step = override_step
            ctx = StepContext(
                plan_dir=resolved_plan_dir,
                state=state,
                profile={
                    "root": root,
                    "project_dir": (state.get("config") or {}).get("project_dir", str(root)),
                },
                mode=(state.get("config") or {}).get("mode", "code"),
                inputs={"_pipeline": "megaplan", "_progress_env": progress_env or {}},
            )
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                if hasattr(step, "run") and callable(step.run):
                    result = step.run(ctx)
                elif callable(step):
                    result = step(ctx)
                else:
                    return 1, "", f"phase {phase!r} is not runnable"
            payload = {
                "success": True,
                "step": phase,
                "next": result.next,
                "outputs": {key: str(value) for key, value in result.outputs.items()},
            }
            return 0, stdout.getvalue() or json_dump(payload), stderr.getvalue()
        except CliError as error:
            payload: dict[str, Any] = {
                "success": False,
                "error": error.code,
                "message": error.message,
            }
            if error.extra:
                payload["details"] = dict(error.extra)
            return error.exit_code, stdout.getvalue(), stderr.getvalue() + json_dump(payload)
        except Exception as error:  # noqa: BLE001 - preserve CLI-like failure surface.
            return 1, stdout.getvalue(), stderr.getvalue() + f"{type(error).__name__}: {error}"


def _pipeline():
    from arnold.pipelines.megaplan.pipeline import build_pipeline

    pipeline = build_pipeline()
    if hasattr(pipeline, "run_phase"):
        return pipeline
    return _RunPhaseCompatiblePipeline(pipeline)


def _invalid_request(message: str, **details: Any) -> OperationResult:
    payload = {"details": details} if details else {}
    return OperationResult(
        ok=False,
        payload=payload,
        errors=("invalid_request", message),
    )


def _payload_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else None


def _payload_path(payload: Mapping[str, Any], key: str) -> Path | None:
    value = payload.get(key)
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value:
        return Path(value)
    return None


def _payload_str(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def _payload_state_view(payload: Mapping[str, Any], state: Mapping[str, Any]) -> RunStateView:
    candidate = payload.get("state_view")
    if isinstance(candidate, RunStateView):
        return candidate
    run_id = payload.get("run_id")
    resolved_run_id = run_id if isinstance(run_id, str) and run_id else None
    surface = payload.get("projection_surface")
    projection_surface = surface if isinstance(surface, str) and surface else "legacy"
    return planning_run_state_view(
        state,
        run_id=resolved_run_id,
        projection_surface=projection_surface,
    )


def _control_transition(payload: Mapping[str, Any]) -> ControlTransition | ControlTransitionRequest:
    request = payload.get("request")
    if isinstance(request, (ControlTransition, ControlTransitionRequest)):
        return request
    transition = payload.get("transition")
    if isinstance(transition, (ControlTransition, ControlTransitionRequest)):
        return transition

    action = payload.get("action")
    if not isinstance(action, str) or not action:
        raise CliError("invalid_args", "override_apply requires payload.action")
    params = _payload_mapping(payload, "params")
    metadata = _payload_mapping(payload, "metadata")
    expected_versions = _payload_mapping(payload, "expected_versions")
    actor = payload.get("actor")
    source = payload.get("source")
    reason = payload.get("reason")
    note = payload.get("note")
    target_id = payload.get("target_id")
    return ControlTransitionRequest(
        action=action,
        target_id=target_id if isinstance(target_id, str) and target_id else None,
        params=dict(params or {}),
        actor=actor if isinstance(actor, str) and actor else None,
        source=source if isinstance(source, str) and source else None,
        reason=reason if isinstance(reason, str) and reason else None,
        note=note if isinstance(note, str) and note else None,
        metadata=dict(metadata or {}),
        expected_versions={
            k: int(v) for k, v in dict(expected_versions or {}).items()
        },
        idempotency_key=payload.get("idempotency_key")
        if isinstance(payload.get("idempotency_key"), str)
        else None,
    )


class PlanningOperationRegistry(OperationRegistry):
    def supported_operations(self) -> frozenset[OperationKind]:
        return SUPPORTED_OPERATIONS

    def dispatch(self, request: OperationRequest) -> OperationResult:
        handler = {
            OperationKind.EXECUTE: self._dispatch_run_phase,
            OperationKind.STATUS_PROJECTION: self._dispatch_status_projection,
            OperationKind.RESUME: self._dispatch_resume,
            OperationKind.OVERRIDE_LIST: self._dispatch_override_list,
            OperationKind.OVERRIDE_APPLY: self._dispatch_override_apply,
            OperationKind.PROFILE_VALIDATE: self._dispatch_profile_validate,
        }.get(request.kind)
        if handler is None:
            return OperationResult(
                ok=False,
                payload={},
                errors=("unsupported", request.kind.value),
            )
        return handler(request.payload)

    def _dispatch_run_phase(self, payload: Mapping[str, Any]) -> OperationResult:
        phase = payload.get("phase")
        plan = payload.get("plan")
        if not isinstance(phase, str) or not phase:
            return _invalid_request("run_phase requires payload.phase")
        if not isinstance(plan, str) or not plan:
            return _invalid_request("run_phase requires payload.plan")

        cwd = _payload_path(payload, "cwd")
        plan_dir = _payload_path(payload, "plan_dir")
        argv = payload.get("argv")
        progress_env = payload.get("progress_env")
        if argv is not None and not isinstance(argv, list):
            return _invalid_request("run_phase payload.argv must be a list when provided")
        if progress_env is not None and not isinstance(progress_env, Mapping):
            return _invalid_request(
                "run_phase payload.progress_env must be a mapping when provided"
            )

        exit_code, stdout, stderr = _pipeline().run_phase(
            phase,
            plan=plan,
            cwd=cwd,
            plan_dir=plan_dir,
            argv=argv,
            progress_env=dict(progress_env or {}),
        )
        return OperationResult(
            ok=exit_code == 0,
            payload={
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
            },
            errors=() if exit_code == 0 else ("run_phase_failed", phase),
        )

    def _dispatch_status_projection(self, payload: Mapping[str, Any]) -> OperationResult:
        state = _payload_mapping(payload, "state")
        if state is None:
            return _invalid_request("status_projection requires payload.state")

        mode = payload.get("mode")
        if not isinstance(mode, str) or not mode:
            mode = "view"
        binding = planning_control_binding()
        state_view = _payload_state_view(payload, state)

        projection: dict[str, Any] = {
            "state_view": state_view,
            "binding": binding,
        }
        if mode == "view":
            projection["projection"] = state_view
        elif mode == "valid_targets":
            projection["valid_targets"] = tuple(binding.valid_targets(state_view))
        elif mode == "recover_targets":
            projection["recover_targets"] = tuple(binding.recover_targets(state_view))
        elif mode == "binding":
            projection["projection"] = state_view
        else:
            return _invalid_request(
                "status_projection mode must be one of view|valid_targets|recover_targets|binding",
                mode=mode,
            )
        return OperationResult(ok=True, payload=projection)

    def _dispatch_resume(self, payload: Mapping[str, Any]) -> OperationResult:
        cursor = _payload_mapping(payload, "cursor")
        plan = payload.get("plan")
        if cursor is None:
            return _invalid_request("resume requires payload.cursor")
        if not isinstance(plan, str) or not plan:
            return _invalid_request("resume requires payload.plan")

        args = resume_phase_args(cursor, plan)
        phase = args[0]
        runner = payload.get("runner")
        if runner is not None and not callable(runner):
            return _invalid_request("resume payload.runner must be callable when provided")

        root = _payload_path(payload, "root")
        plan_dir = _payload_path(payload, "plan_dir")
        phase_runner: Callable[..., tuple[int, str, str]]
        if runner is None:
            phase_runner = _pipeline().run_phase
        else:
            phase_runner = runner
        exit_code, stdout, stderr = phase_runner(
            phase,
            plan=plan,
            cwd=root,
            plan_dir=plan_dir,
            argv=args,
        )
        return OperationResult(
            ok=exit_code == 0,
            payload={
                "args": args,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
            },
            errors=() if exit_code == 0 else ("resume_failed", phase),
        )

    def _dispatch_override_list(self, payload: Mapping[str, Any]) -> OperationResult:
        state = _payload_mapping(payload, "state")
        binding = None
        state_view = None
        valid_targets = ()
        recover_targets = ()
        if state is not None:
            binding = planning_control_binding()
            state_view = _payload_state_view(payload, state)
            valid_targets = tuple(binding.valid_targets(state_view))
            recover_targets = tuple(binding.recover_targets(state_view))
        return OperationResult(
            ok=True,
            payload={
                "catalog": override_catalog(),
                "binding": binding,
                "state_view": state_view,
                "valid_targets": valid_targets,
                "recover_targets": recover_targets,
            },
        )

    def _dispatch_override_apply(self, payload: Mapping[str, Any]) -> OperationResult:
        state = _payload_mapping(payload, "state")
        if state is None:
            return _invalid_request("override_apply requires payload.state")
        try:
            transition = _control_transition(payload)
            state_view = _payload_state_view(payload, state)
            plan_dir = _payload_path(payload, "plan_dir")
            if plan_dir is None:
                result = planning_control_binding().apply_transition(state_view, transition)
            else:
                result = apply_transition(
                    state_view,
                    transition,
                    planning_control_binding(),
                    plan_dir=plan_dir,
                )
        except CliError as exc:
            return OperationResult(
                ok=False,
                payload={
                    "error": exc.code,
                    "message": exc.message,
                    "details": dict(exc.extra),
                    "valid_next": list(exc.valid_next),
                },
                errors=(exc.code,),
            )
        response: Mapping[str, Any] | None = None
        root = _payload_path(payload, "root")
        plan_dir = _payload_path(payload, "plan_dir")
        plan = _payload_str(payload, "plan")
        action = getattr(transition, "action", None) or transition.target_id or transition.op
        if result.accepted and root is not None and plan_dir is not None and plan is not None:
            from arnold.pipelines.megaplan._core import load_plan
            from arnold.pipelines.megaplan.handlers.override import (
                _emit_routed_override_events,
                _routed_override_response,
            )

            args = argparse.Namespace(
                plan=plan,
                override_action=action,
                note=getattr(transition, "note", None),
                reason=getattr(transition, "reason", None),
                source=getattr(transition, "source", None),
                user_approved=bool(transition.payload.get("user_approved", False)),
                robustness=transition.payload.get("robustness"),
                profile=transition.payload.get("profile"),
                phase=transition.payload.get("phase"),
                model=transition.payload.get("model"),
                effort=transition.payload.get("effort"),
                vendor=transition.payload.get("vendor"),
                strict_notes=transition.payload.get("strict_notes"),
            )
            persisted_state = load_plan(root, plan)[1]
            _emit_routed_override_events(
                action,
                plan_dir=plan_dir,
                state=persisted_state,
                args=args,
            )
            response = _routed_override_response(
                action,
                plan_dir=plan_dir,
                state=persisted_state,
                args=args,
                artifacts=dict(result.artifacts),
            )

        operation_payload: dict[str, Any] = {
            "result": result,
            "accepted": result.accepted,
            "mutated": result.mutated,
            "reason": result.reason,
            "artifacts": dict(result.artifacts),
            "state_deltas": tuple(result.state_deltas),
            "events": tuple(result.events),
        }
        if response is not None:
            operation_payload["response"] = dict(response)
        return OperationResult(
            ok=result.accepted,
            payload=operation_payload,
            errors=() if result.accepted else ("override_rejected", result.reason or "rejected"),
        )

    def _dispatch_profile_validate(self, payload: Mapping[str, Any]) -> OperationResult:
        return profile_validate_operation(payload)


def operation_registry() -> OperationRegistry:
    return PlanningOperationRegistry()


__all__ = [
    "PlanningOperationRegistry",
    "SUPPORTED_OPERATIONS",
    "operation_registry",
    "override_catalog",
    "preflight_or_raise",
    "profile_validate_operation",
    "resume_phase_args",
]
