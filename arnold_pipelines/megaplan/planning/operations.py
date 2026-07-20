"""Canonical planning operation dispatch for the Megaplan pipeline."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
from typing import Any

from arnold.execution.operations import (
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
from arnold_pipelines.megaplan.control_interface import apply_transition
from arnold_pipelines.megaplan.planning.control_binding import (
    planning_control_binding,
    planning_run_state_view,
)
from arnold_pipelines.megaplan.planning.validation import preflight_or_raise, profile_validate_operation
from arnold_pipelines.megaplan.runtime.process import megaplan_engine_env
from arnold_pipelines.megaplan.types import CliError

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

_MEGAPLAN_MODULE_COMMANDS = frozenset(
    {
        "plan",
        "prep",
        "critique",
        "revise",
        "gate",
        "finalize",
        "execute",
        "review",
    }
)


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


def _pipeline():
    from arnold_pipelines.megaplan.pipeline import build_pipeline

    return build_pipeline()


def canonical_metadata() -> dict[str, Any]:
    """Return live canonical Megaplan metadata from the native-backed compile path."""

    import arnold_pipelines.megaplan as megaplan_package
    from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline
    from arnold_pipelines.megaplan.workflows import planning as workflow_planning

    compiled = build_and_compile_pipeline()
    facade_module = import_module("arnold_pipelines.megaplan.pipeline")
    native_program = getattr(compiled, "native_program", None)
    registration_kind = "native" if native_program is not None else "graph_compatibility"

    metadata: dict[str, Any] = {
        "name": str(getattr(megaplan_package, "name", "megaplan") or "megaplan"),
        "description": str(getattr(megaplan_package, "description", "") or ""),
        "source_path": str(Path(facade_module.__file__).resolve()),
        "authored_source_path": str(workflow_planning.AUTHORING_SOURCE_PATH.resolve()),
        "driver": tuple(getattr(megaplan_package, "driver", ()) or ()),
        "supported_modes": tuple(getattr(megaplan_package, "supported_modes", ()) or ()),
        "recommended_profiles": tuple(
            getattr(megaplan_package, "recommended_profiles", ()) or ()
        ),
        "capabilities": tuple(getattr(megaplan_package, "capabilities", ()) or ()),
        "arnold_api_version": str(getattr(megaplan_package, "arnold_api_version", "") or ""),
        "registration_kind": registration_kind,
        "compatibility_classification": "native" if native_program is not None else "graph",
        "supported_operations": tuple(kind.value for kind in sorted(SUPPORTED_OPERATIONS, key=lambda item: item.value)),
    }
    default_profile = getattr(megaplan_package, "default_profile", None)
    if isinstance(default_profile, str) and default_profile:
        metadata["default_profile"] = default_profile
    manifest_hash = getattr(compiled, "manifest_hash", None)
    if isinstance(manifest_hash, str) and manifest_hash:
        metadata["manifest_hash"] = manifest_hash
    topology_hash = getattr(compiled, "topology_hash", None)
    if isinstance(topology_hash, str) and topology_hash:
        metadata["topology_hash"] = topology_hash
    return metadata


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


def _phase_subprocess_command(argv: list[Any]) -> list[str]:
    args = [str(entry) for entry in argv]
    if not args:
        return []
    if args[0] == "megaplan":
        return [sys.executable, "-P", "-m", "arnold_pipelines.megaplan", *args[1:]]
    if args[0] in _MEGAPLAN_MODULE_COMMANDS:
        return [sys.executable, "-P", "-m", "arnold_pipelines.megaplan", *args]
    return args


def _run_phase_subprocess(
    phase: str,
    *,
    plan: str,
    cwd: Path | None = None,
    plan_dir: Path | None = None,
    argv: list[Any] | None = None,
    progress_env: Mapping[str, Any] | None = None,
) -> tuple[int, str, str]:
    del phase, plan, plan_dir
    if not argv:
        return 1, "", "missing command"

    env = megaplan_engine_env(dict(os.environ))
    env["PYTHONSAFEPATH"] = "1"
    if progress_env:
        env.update({str(key): str(value) for key, value in progress_env.items()})
    proc = subprocess.run(
        _phase_subprocess_command(argv),
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


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

        exit_code, stdout, stderr = _run_phase_subprocess(
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
            phase_runner = _run_phase_subprocess
        else:
            phase_runner = runner
        try:
            exit_code, stdout, stderr = phase_runner(
                phase,
                plan=plan,
                cwd=root,
                plan_dir=plan_dir,
                argv=args,
            )
        except TypeError as error:
            if runner is None:
                raise
            if "unexpected keyword" not in str(error):
                raise
            exit_code, stdout, stderr = runner(args, cwd=root)
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
            from arnold_pipelines.megaplan._core import load_plan
            from arnold_pipelines.megaplan.handlers.override import (
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
