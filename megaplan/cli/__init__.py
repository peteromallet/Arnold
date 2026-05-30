#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from megaplan.types import (
    CliError,
    DEFAULT_AGENT_ROUTING,
    DEFAULTS,
    KNOWN_AGENTS,
    ROBUSTNESS_ACCEPTED,
    ROBUSTNESS_LEVELS,
    STATE_BLOCKED,
    STATE_DONE,
    STATE_REVIEWED,
    StepResponse,
    TERMINAL_STATES,
    _SETTABLE_BOOL,
    _SETTABLE_ENUM,
    _SETTABLE_NUMERIC,
)
from megaplan._core import (
    active_phase_name,
    active_plan_dirs,
    add_or_increment_debt,
    atomic_write_text,
    build_next_step_runtime,
    build_phase_observability,
    compute_global_batches,
    config_dir,
    detect_available_agents,
    escalated_subsystems,
    ensure_runtime_layout,
    get_effective,
    has_any_plan_root,
    infer_next_steps,
    is_prose_mode,
    json_dump,
    list_batch_artifacts,
    load_config,
    load_debt_registry,
    load_plan,
    plan_lock_is_held,
    read_json,
    resolve_debt,
    resolve_plan_dir,
    resume_plan,
    save_debt_registry,
    save_config,
    save_state,
    subsystem_occurrence_total,
    humanize_seconds,
)
from megaplan.execute.batch import build_monitor_hint
from megaplan.forms import available_form_ids
from megaplan.handlers import (
    handle_audit_verifiability,
    handle_critique,
    handle_execute,
    handle_finalize,
    handle_gate,
    handle_init,
    handle_override,
    handle_plan,
    handle_prep,
    handle_review,
    handle_revise,
    handle_tiebreaker_run,
    handle_verify_human,
)
from megaplan.loop.handlers import (
    handle_loop_init,
    handle_loop_pause,
    handle_loop_run,
    handle_loop_status,
)
from megaplan.profiles import (
    load_profile_sources,
    load_profiles,
    resolve_profile,
)
from megaplan.execute.step_edit import handle_step
from megaplan.observability.doctor import handle_doctor
from megaplan.observability.trace import handle_trace
from megaplan.resolutions import SUPPORTED_USER_ACTION_RESOLUTION_STATES
from megaplan.user_actions import (
    FALLBACK,
    OMIT,
)
from .feedback import (
    _collect_feedback_rows,
    _filter_feedback_rows,
    _render_feedback_table,
    handle_feedback,
)
from .parser import _add_vendor_critic_args, build_parser
from .resolutions import handle_quality_gate, handle_user_action
from .roots import (
    _collect_megaplan_roots,
    _find_git_root,
    _find_megaplan_root,
    _resolve_project_root,
)
from .setup import (
    _install_owned_dir_symlink,
    _install_owned_file,
    _install_owned_symlink,
    handle_setup,
    handle_setup_global,
    handle_setup_hooks,
)
from .skills import (
    _GLOBAL_TARGETS,
    _canonical_bakeoff_skill,
    _canonical_cloud_skill,
    _canonical_composed,
    _canonical_decision_skill,
    _canonical_epic_skill,
    _canonical_instructions,
    _canonical_observe_skill,
    _canonical_pre_commit_hook,
    _canonical_tickets_skill,
    _claude_subagent_appendix,
    _codex_subagent_appendix,
    _CURSOR_HEADER,
    _resolve_bundle_path,
    _SKILL_HEADER,
    _subagent_appendix,
    bundled_agents_md,
    bundled_global_file,
    handle_regen_composed,
)
from .status_view import (
    _build_active_step,
    _build_progress_payload,
    _build_status_payload,
    _compute_user_action_blockers,
    handle_audit,
    handle_progress,
    handle_status,
    handle_watch,
)

_PROGRESS_PHASE_COMMANDS = {
    "plan",
    "prep",
    "critique",
    "revise",
    "gate",
    "finalize",
    "execute",
    "review",
}


def render_response(response: StepResponse, *, exit_code: int = 0) -> int:
    if isinstance(response, str):
        print(response, end="")
        return exit_code
    print(json_dump(response), end="")
    return exit_code


def _resolve_error_plan_dir(root: Path | None, error: CliError) -> Path | None:
    if root is None or error.code != "plan_locked" or not isinstance(error.extra, dict):
        return None
    plan_name = error.extra.get("plan")
    if not isinstance(plan_name, str) or not plan_name:
        return None
    try:
        return resolve_plan_dir(root, plan_name)
    except CliError:
        return None


def _augment_plan_locked_error(
    payload: StepResponse,
    error: CliError,
    *,
    root: Path | None,
) -> None:
    plan_dir = _resolve_error_plan_dir(root, error)
    details = payload.get("details")
    if not isinstance(details, dict):
        details = None
    plan_name = (details or {}).get("plan")
    if isinstance(plan_name, str) and plan_name:
        monitor_hint = build_monitor_hint(plan_dir or Path(plan_name))
        payload["monitor_hint"] = monitor_hint
        if details is not None:
            details["monitor_hint"] = monitor_hint
    raw_active_step = (details or {}).get("active_step")
    if isinstance(raw_active_step, dict):
        active_step = (
            _build_active_step(raw_active_step, plan_dir=plan_dir)
            if plan_dir is not None
            else dict(raw_active_step)
        )
        payload["active_step"] = active_step
        if details is not None:
            details["active_step"] = active_step


def error_response(error: CliError, *, root: Path | None = None) -> int:
    payload: StepResponse = {
        "success": False,
        "error": error.code,
        "message": error.message,
    }
    if error.valid_next:
        payload["valid_next"] = error.valid_next
    if error.extra:
        payload["details"] = dict(error.extra)
    if error.code == "plan_locked":
        _augment_plan_locked_error(payload, error, root=root)
    return render_response(payload, exit_code=error.exit_code)


def _emit_response_progress(command: str, response: StepResponse, emitter: Any) -> None:
    if command not in _PROGRESS_PHASE_COMMANDS or not isinstance(response, dict):
        return
    state = response.get("state")
    step = str(response.get("step") or command)
    emitter.phase_end(
        step,
        success=bool(response.get("success", True)),
        state=state,
        result=response.get("result"),
        next_step=response.get("next_step"),
    )
    if state == "done":
        emitter.plan_done(
            summary=str(response.get("summary") or "Plan complete"), phase=step
        )
    elif state == "failed":
        emitter.plan_failed(
            summary=str(response.get("summary") or "Plan failed"), phase=step
        )
    elif state == "blocked":
        emitter.execution_blocked(
            summary=str(response.get("summary") or "Execution blocked"), phase=step
        )


def _emit_error_progress(command: str, error: CliError, emitter: Any) -> None:
    if command not in _PROGRESS_PHASE_COMMANDS:
        return
    emitter.phase_end(
        command, success=False, error_code=error.code, message=error.message
    )




def handle_list(root: Path, args: argparse.Namespace) -> StepResponse:
    ensure_runtime_layout(root)

    # Dispatch to pipeline listing when 'pipelines' subcommand is used
    list_target = getattr(args, "list_target", None)
    if list_target == "pipelines":
        return _handle_list_pipelines(args)

    filter_status = getattr(args, "filter_status", None)
    no_tree = getattr(args, "no_tree", False)
    include_done = getattr(args, "include_done", False)
    show_summary = getattr(args, "summary", False)
    search_all = getattr(args, "all", False)
    # Default: tree=True (parent+child), active-only (exclude terminal plans)
    # --status overrides the active filter (explicit filter = show exactly that)
    search_tree = not no_tree and not search_all
    filter_active = not include_done and not filter_status

    roots = _collect_megaplan_roots(root, tree=search_tree, all_system=search_all)
    total_scanned = 0
    allowed_states: set[str] | None = None
    if filter_status:
        allowed_states = {s.strip() for s in filter_status.split(",")}

    items = []
    state_counts: dict[str, int] = {}
    resolved_root = root.resolve()
    for search_root in roots:
        resolved_search = search_root.resolve()
        is_local = resolved_search == resolved_root
        for plan_dir in active_plan_dirs(search_root):
            state = read_json(plan_dir / "state.json")
            current_state = state["current_state"]
            state_counts[current_state] = state_counts.get(current_state, 0) + 1
            total_scanned += 1

            if filter_active and current_state in TERMINAL_STATES:
                continue
            if allowed_states and current_state not in allowed_states:
                continue

            next_steps = infer_next_steps(state)
            entry = {
                "name": state["name"],
                "idea": state["idea"],
                "state": current_state,
                "iteration": state["iteration"],
                "next_step": next_steps[0] if next_steps else None,
            }
            if not is_local:
                try:
                    rel = resolved_search.relative_to(resolved_root)
                    entry["location"] = f"./{rel}"
                    entry["direction"] = "child"
                except ValueError:
                    try:
                        resolved_root.relative_to(resolved_search)
                        entry["location"] = os.path.relpath(
                            resolved_search, resolved_root
                        )
                        entry["direction"] = "parent"
                    except ValueError:
                        entry["location"] = str(resolved_search)
                        entry["direction"] = "external"
            items.append(entry)

    summary_parts = [f"Found {len(items)} plans"]
    if len(roots) > 1:
        summary_parts.append(f"across {len(roots)} directories")
    if allowed_states:
        summary_parts.append(f"matching {','.join(sorted(allowed_states))}")
    if filter_active:
        summary_parts.append("(active only)")

    result: StepResponse = {
        "success": True,
        "step": "list",
        "summary": f"{'. '.join(summary_parts)}.",
        "plans": items,
    }
    if show_summary:
        result["state_summary"] = dict(sorted(state_counts.items()))

    # Hints for discovering more plans
    hidden_done = total_scanned - len(items) if filter_active else 0
    hints: list[str] = []
    if hidden_done > 0:
        hints.append(
            f"{hidden_done} terminal plans hidden (use --include-done to show)"
        )
    if not search_all:
        hints.append("Use --all to search all plans system-wide")
    if hints:
        result["hints"] = hints

    return result


def handle_debt(root: Path, args: argparse.Namespace) -> StepResponse:
    ensure_runtime_layout(root)
    action = args.debt_action
    registry = load_debt_registry(root)
    default_plan_id = getattr(args, "plan", None) or "manual"

    if action == "list":
        entries = (
            registry["entries"]
            if args.all
            else [entry for entry in registry["entries"] if not entry["resolved"]]
        )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            grouped.setdefault(entry["subsystem"], []).append(entry)
        escalated = {
            subsystem: total
            for subsystem, total, _entries in escalated_subsystems(registry)
        }
        by_subsystem = [
            {
                "subsystem": subsystem,
                "escalated": subsystem in escalated,
                "total_occurrences": (
                    subsystem_occurrence_total(entries_for_subsystem)
                    if not args.all
                    else sum(
                        entry["occurrence_count"]
                        for entry in entries_for_subsystem
                        if not entry["resolved"]
                    )
                ),
                "entries": entries_for_subsystem,
            }
            for subsystem, entries_for_subsystem in sorted(grouped.items())
        ]
        return {
            "success": True,
            "step": "debt",
            "action": "list",
            "summary": f"Found {len(entries)} debt entries across {len(by_subsystem)} subsystem groups.",
            "details": {
                "entries": entries,
                "by_subsystem": by_subsystem,
                "escalated_subsystems": [
                    {"subsystem": subsystem, "total_occurrences": total}
                    for subsystem, total in sorted(escalated.items())
                ],
            },
        }

    if action == "add":
        flag_ids = [
            flag_id.strip()
            for flag_id in (args.flag_ids or "").split(",")
            if flag_id.strip()
        ]
        entry = add_or_increment_debt(
            registry,
            subsystem=args.subsystem,
            concern=args.concern,
            flag_ids=flag_ids,
            plan_id=default_plan_id,
        )
        save_debt_registry(root, registry)
        return {
            "success": True,
            "step": "debt",
            "action": "add",
            "summary": f"Tracked debt entry {entry['id']} for subsystem '{entry['subsystem']}'.",
            "details": {"entry": entry},
        }

    if action == "resolve":
        entry = resolve_debt(registry, args.debt_id, default_plan_id)
        save_debt_registry(root, registry)
        return {
            "success": True,
            "step": "debt",
            "action": "resolve",
            "summary": f"Resolved debt entry {entry['id']}.",
            "details": {"entry": entry},
        }

    raise CliError("invalid_args", f"Unknown debt action: {action}")




def handle_config(args: argparse.Namespace) -> StepResponse:
    action = args.config_action
    if action == "show":
        config = load_config()
        effective_routing = {
            step: config.get("agents", {}).get(step, default)
            for step, default in DEFAULT_AGENT_ROUTING.items()
        }
        effective_settings = {
            dot_key: get_effective(section, setting)
            for dot_key in sorted(DEFAULTS)
            for section, setting in [dot_key.split(".", 1)]
        }
        return {
            "success": True,
            "step": "config",
            "action": "show",
            "config_path": str(config_dir() / "config.json"),
            "routing": effective_routing,
            "effective_settings": effective_settings,
            "raw_config": config,
        }
    if action == "set":
        key, value = args.key, args.value
        parts = key.split(".", 1)
        config = load_config()
        valid_keys = [
            *(f"agents.{step}" for step in DEFAULT_AGENT_ROUTING),
            "orchestration.mode",
            *sorted(_SETTABLE_BOOL),
            *sorted(_SETTABLE_ENUM),
            *sorted(_SETTABLE_NUMERIC),
        ]
        if len(parts) != 2:
            raise CliError(
                "invalid_args",
                f"Unknown config key '{key}'. Valid keys: {', '.join(valid_keys)}",
            )
        section, setting = parts
        normalized_value = value.strip().lower()
        if section == "agents":
            if setting not in DEFAULT_AGENT_ROUTING:
                raise CliError(
                    "invalid_args",
                    f"Unknown step '{setting}'. Valid steps: {', '.join(DEFAULT_AGENT_ROUTING)}",
                )
            if value not in KNOWN_AGENTS:
                raise CliError(
                    "invalid_args",
                    f"Unknown agent '{value}'. Valid agents: {', '.join(KNOWN_AGENTS)}",
                )
            config.setdefault("agents", {})[setting] = value
        elif key == "orchestration.mode":
            if value not in {"inline", "subagent"}:
                raise CliError(
                    "invalid_args", "orchestration.mode must be 'inline' or 'subagent'"
                )
            config.setdefault("orchestration", {})["mode"] = value
        elif key in _SETTABLE_BOOL:
            if normalized_value in {"true", "1", "yes", "on"}:
                parsed_value = True
            elif normalized_value in {"false", "0", "no", "off"}:
                parsed_value = False
            else:
                raise CliError(
                    "invalid_args",
                    f"{key} must be one of: true, false, 1, 0, yes, no, on, off",
                )
            config.setdefault(section, {})[setting] = parsed_value
        elif key in _SETTABLE_ENUM:
            allowed_values = _SETTABLE_ENUM[key]
            if value not in allowed_values:
                raise CliError(
                    "invalid_args",
                    f"{key} must be one of: {', '.join(allowed_values)}",
                )
            config.setdefault(section, {})[setting] = value
        elif key in _SETTABLE_NUMERIC:
            try:
                parsed_value = int(value)
            except ValueError as exc:
                raise CliError(
                    "invalid_args", f"{key} must be an integer, got '{value}'"
                ) from exc
            config.setdefault(section, {})[setting] = parsed_value
        else:
            raise CliError(
                "invalid_args",
                f"Unknown config key '{key}'. Valid keys: {', '.join(valid_keys)}",
            )
        save_config(config)
        return {
            "success": True,
            "step": "config",
            "action": "set",
            "key": key,
            "value": config[section][setting],
        }
    if action == "profiles":
        project_dir = Path.cwd()
        profiles_action = args.profiles_action
        if profiles_action == "list":
            profiles = [
                {
                    "source": source_label,
                    "name": profile_name,
                    "phases": phase_map,
                }
                for source_label, profile_name, phase_map in load_profile_sources(
                    project_dir=project_dir
                )
            ]
            return {
                "success": True,
                "step": "config",
                "action": "profiles",
                "profiles_action": "list",
                "project_dir": str(project_dir),
                "profiles": profiles,
            }
        if profiles_action == "show":
            profiles = load_profiles(project_dir=project_dir)
            resolved = resolve_profile(args.name, profiles)
            return {
                "success": True,
                "step": "config",
                "action": "profiles",
                "profiles_action": "show",
                "project_dir": str(project_dir),
                "name": args.name,
                "profile": resolved,
            }
        raise CliError("invalid_args", f"Unknown profiles action: {profiles_action}")
    if action == "use-profile":
        project_dir = Path.cwd()
        name = args.name
        profiles = load_profiles(project_dir=project_dir)
        # resolve_profile raises CliError("unknown_profile", ...) with the list of
        # known profile names, which is what we want for a clear error.
        resolved = resolve_profile(name, profiles)
        config = load_config()
        agents_section = config.setdefault("agents", {})
        applied: dict[str, str] = {}
        for phase, spec in resolved.items():
            agents_section[phase] = spec
            applied[phase] = spec
        save_config(config)
        return {
            "success": True,
            "step": "config",
            "action": "use-profile",
            "config_path": str(config_dir() / "config.json"),
            "profile": name,
            "applied": applied,
            "summary": (
                f"Applied profile '{name}' to user config "
                f"({len(applied)} agent phase{'s' if len(applied) != 1 else ''} updated)."
            ),
        }
    if action == "reset":
        path = config_dir() / "config.json"
        if path.exists():
            path.unlink()
        return {
            "success": True,
            "step": "config",
            "action": "reset",
            "summary": "Config file removed. Using defaults.",
        }
    raise CliError("invalid_args", f"Unknown config action: {action}")


# ---------------------------------------------------------------------------
# Store factory
# ---------------------------------------------------------------------------


def build_store(args: argparse.Namespace):
    """Return a DBStore configured for writes, or None for the file backend."""
    backend = getattr(args, "backend", None) or os.environ.get("MEGAPLAN_BACKEND")
    if backend == "db":
        from megaplan.store import (
            DBStore,
            require_actor_id,
            resolve_actor_id,
            validate_actor_exists,
        )

        actor_id = require_actor_id(resolve_actor_id(args))
        store = DBStore(actor_id=actor_id)
        validate_actor_exists(store, actor_id)
        return store
    return None  # Sprint 3: write-back to DB


def build_epic_store(root: Path, *, actor_id: str | None = None):
    from megaplan.store import MultiStore

    return MultiStore.for_project(root, actor_id=actor_id)


def _jsonable_model(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _snapshot_payload(store: Any, epic_id: str) -> dict[str, Any]:
    epic = store.load_epic(epic_id)
    if epic is None:
        raise CliError("not_found", f"Epic {epic_id!r} not found")
    source = store._route_for_epic(epic_id)
    entities = store._migration_entities(source, epic_id)
    plan_artifacts: dict[str, list[dict[str, Any]]] = {}
    for plan_id, artifacts in entities["plan_artifacts"].items():
        plan_artifacts[plan_id] = [
            {
                "name": ref.name,
                "kind": ref.kind,
                "role": ref.role,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "content_text": data.decode("utf-8", errors="replace"),
            }
            for ref, data in artifacts
        ]
    return {
        "epic": _jsonable_model(entities["epic"]),
        "body": store.load_body(epic_id),
        "checklist_items": [
            _jsonable_model(row) for row in entities["checklist_items"]
        ],
        "sprints": [_jsonable_model(row) for row in entities["sprints"]],
        "sprint_items": [_jsonable_model(row) for row in entities["sprint_items"]],
        "plans": [_jsonable_model(row) for row in entities["plans"]],
        "plan_artifacts_by_plan": plan_artifacts,
        "images": [_jsonable_model(row) for row in entities["images"]],
        "second_opinions": [
            _jsonable_model(row) for row in entities["second_opinions"]
        ],
        "feedback": [_jsonable_model(row) for row in entities["feedback"]],
        "code_artifacts": [_jsonable_model(row) for row in entities["code_artifacts"]],
        "epic_events": [_jsonable_model(row) for row in entities["epic_events"]],
    }


def _snapshot_dir(epic_id: str) -> Path:
    timestamp = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )
    return Path.home() / ".megaplan" / "snapshots" / f"{epic_id}-{timestamp}"


def handle_ticket(args: argparse.Namespace) -> int:
    """Dispatch ``megaplan ticket ...`` subcommands."""
    from megaplan.handlers.tickets import TICKET_DISPATCH
    from megaplan.tickets.registry import touch as _registry_touch

    # Passive registry maintenance — best-effort, never raises.
    try:
        _registry_touch(Path.cwd())
    except Exception:
        pass

    action = args.ticket_action
    handler = TICKET_DISPATCH.get(action)
    if handler is None:
        print(f"Error: unknown ticket action {action!r}", file=sys.stderr)
        return 1
    return handler(args)


def handle_epic(root: Path, args: argparse.Namespace) -> StepResponse:
    action = args.epic_action
    if action == "snapshot":
        store = build_epic_store(root)
        try:
            payload = _snapshot_payload(store, args.epic_id)
        finally:
            close = getattr(store, "close", None)
            if callable(close):
                close()
        snapshot_dir = _snapshot_dir(args.epic_id)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / "snapshot.json"
        atomic_write_text(snapshot_path, json_dump(payload))
        return {
            "success": True,
            "step": "epic",
            "action": "snapshot",
            "epic_id": args.epic_id,
            "path": str(snapshot_path),
        }
    if action == "migrate":
        actor_id = getattr(args, "actor", None) or os.environ.get("MEGAPLAN_ACTOR_ID")
        if not actor_id:
            raise CliError(
                "missing_actor",
                "actor ID required for epic migration. Set MEGAPLAN_ACTOR_ID or pass --actor <id>.",
            )
        store = build_epic_store(root, actor_id=actor_id)
        try:
            warnings = store.warn_incomplete_migrations()
            if args.resume:
                if args.epic_id:
                    raise CliError(
                        "invalid_args",
                        "epic migrate --resume does not accept an epic id",
                    )
                run = store.resume_migration(args.resume, ttl_seconds=args.ttl)
                migration_action = "resume"
            else:
                if not args.epic_id:
                    raise CliError(
                        "invalid_args",
                        "epic migrate requires an epic id unless --resume is used",
                    )
                if not args.to:
                    raise CliError(
                        "invalid_args",
                        "epic migrate requires --to file|db unless --resume is used",
                    )
                run = store.migrate_epic(args.epic_id, to=args.to, ttl_seconds=args.ttl)
                migration_action = "migrate"
        finally:
            close = getattr(store, "close", None)
            if callable(close):
                close()
        return {
            "success": True,
            "step": "epic",
            "action": migration_action,
            "migration_id": run.id,
            "phase": run.phase,
            "epic_id": run.epic_id,
            "source_backend": run.source_backend,
            "target_backend": run.target_backend,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "migration": run.model_dump(mode="json"),
            "warnings": warnings,
        }
    if action == "export":
        from megaplan.store.export import collect_epic_export, write_epic_export_tar

        store = build_epic_store(root)
        try:
            try:
                collected = collect_epic_export(
                    store,
                    args.epic_id,
                    allow_missing_blobs=bool(args.allow_missing_blobs),
                )
            except FileNotFoundError as exc:
                raise CliError("not_found", f"Epic {args.epic_id!r} not found") from exc
            if collected["errors"]:
                raise CliError(
                    "export_failed",
                    f"Epic {args.epic_id!r} export has missing or corrupt blobs",
                    extra={"errors": collected["errors"]},
                )
            output = write_epic_export_tar(
                collected, args.output, gzip_output=bool(args.gzip)
            )
        finally:
            close = getattr(store, "close", None)
            if callable(close):
                close()
        return {
            "success": True,
            "step": "epic",
            "action": "export",
            "epic_id": args.epic_id,
            "path": output["path"],
            "gzip": output["gzip"],
            "size_bytes": output["size_bytes"],
            "sha256": output["sha256"],
            "member_count": output["member_count"],
            "warnings": collected["warnings"],
            "errors": collected["errors"],
        }
    raise CliError("invalid_args", f"Unknown epic action: {action}")


def handle_migrate_local_plans(root: Path, args: argparse.Namespace) -> StepResponse:
    del root
    from megaplan.store.legacy_migration import migrate_local_plans

    try:
        return migrate_local_plans(
            source_home=Path(args.source_home).expanduser(),
            source_project=args.source_project,
            all_projects=bool(args.all_projects),
            target_project_dir=Path(args.project_dir).expanduser(),
            mode=args.mode,
            dry_run=bool(args.dry_run),
        )
    except ValueError as exc:
        raise CliError("invalid_args", str(exc)) from exc


def handle_resume(root: Path, args: argparse.Namespace) -> StepResponse:
    # Check for awaiting_user.json first (pipeline human_gate pause).
    # When present, enter the human-gate resume flow consuming --choice.
    # When absent, fall through to existing state.json::resume_cursor recovery.
    from megaplan._core.io import find_plan_dir

    plan_dir = find_plan_dir(root, args.plan)
    if plan_dir is not None and (plan_dir / "awaiting_user.json").exists():
        return _resume_human_gate(root, plan_dir, args)

    store = None
    if (
        getattr(args, "actor", None)
        or getattr(args, "backend", None) == "db"
        or os.environ.get("MEGAPLAN_ACTOR_ID")
    ):
        store = build_epic_store(
            root,
            actor_id=getattr(args, "actor", None)
            or os.environ.get("MEGAPLAN_ACTOR_ID"),
        )
    try:
        return resume_plan(root, args.plan, store=store)
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def _resume_human_gate(root: Path, plan_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Resume a pipeline paused at a human_gate stage.

    Re-reads ``awaiting_user.json``, validates the ``--choice`` argument,
    persists the choice back into ``awaiting_user.json`` as
    ``_resume_choice`` so :class:`HumanDecisionStep` picks it up on re-entry,
    then re-enters the pipeline at the paused stage.
    """
    awaiting_path = plan_dir / "awaiting_user.json"
    try:
        data = json.loads(awaiting_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise CliError(
            "bad_awaiting_user", f"Cannot read awaiting_user.json: {exc}"
        ) from exc

    pipeline_name = data.get("pipeline")
    if not pipeline_name:
        raise CliError(
            "bad_awaiting_user", "awaiting_user.json is missing 'pipeline' field"
        )

    choices = data.get("choices", [])
    choice = getattr(args, "choice", None)
    if not choice:
        raise CliError(
            "missing_choice",
            f"Pipeline '{pipeline_name}' is paused at human_gate stage "
            f"'{data.get('stage', '?')}'. "
            f"Use --choice with one of: {', '.join(choices)}",
        )

    if choice not in choices:
        raise CliError(
            "invalid_choice",
            f"Invalid choice '{choice}'. " f"Valid choices: {', '.join(choices)}",
        )

    from megaplan._pipeline.executor import run_pipeline
    from megaplan._pipeline.registry import get_pipeline
    from megaplan._pipeline.resume import with_entry
    from megaplan._pipeline.types import StepContext

    data["_resume_choice"] = choice
    try:
        awaiting_path.write_text(json.dumps(data, indent=2, sort_keys=True))
    except OSError as exc:
        raise CliError(
            "bad_awaiting_user", f"Cannot write awaiting_user.json: {exc}"
        ) from exc

    pipeline = get_pipeline(pipeline_name)

    # Re-enter at the paused stage so prior stages are not re-run.
    paused_stage = data.get("stage")
    if paused_stage and paused_stage in pipeline.stages:
        pipeline = with_entry(pipeline, paused_stage)

    # Re-read state from disk (fresh artifact paths).
    state: dict[str, Any] = {}
    state_path = plan_dir / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            pass

    # Clear pause flags so the executor doesn't immediately halt again.
    state.pop("_pipeline_paused", None)
    state.pop("_pipeline_paused_stage", None)

    ctx = StepContext(
        plan_dir=plan_dir,
        state=state,
        profile={},
        mode=state.get("mode", "code"),
        inputs={},
    )
    result = run_pipeline(pipeline, ctx, artifact_root=plan_dir)

    # Clean up awaiting_user.json after successful resume.
    if awaiting_path.exists():
        awaiting_path.unlink()

    return result


def _handle_trace(root: Path, args: argparse.Namespace) -> int:
    return handle_trace(root, args)


def _handle_doctor(root: Path, args: argparse.Namespace) -> int:
    return handle_doctor(root, args)


def _handle_introspect(root: Path, args: argparse.Namespace) -> int:
    from megaplan._core import find_plan_dir
    from megaplan.observability.introspect import build_introspect_payload
    import json as _json

    plan_dir = find_plan_dir(Path.cwd(), args.plan)
    if plan_dir is None:
        print(f"introspect: plan {args.plan!r} not found", file=sys.stderr)
        return 1

    print(_json.dumps(build_introspect_payload(plan_dir), indent=2))
    return 0


def _handle_cost(root: Path, args: argparse.Namespace) -> int:
    from megaplan.observability.cost import handle_cost

    return handle_cost(root, args)


def _handle_record_tag(root: Path, args: argparse.Namespace) -> int:
    from megaplan._core import find_plan_dir
    from megaplan.observability.events import EventKind, emit

    plan_dir = find_plan_dir(Path.cwd(), args.plan)
    if plan_dir is None:
        print(f"record-tag: plan {args.plan!r} not found", file=sys.stderr)
        return 1

    emit(
        EventKind.NOTE_ADDED,
        plan_dir=plan_dir,
        payload={"tag": args.tag, "note": args.note},
    )
    return 0


def _handle_pipelines(root: Path, args: argparse.Namespace) -> int:
    """W7 — pipelines command group: check + doctor subcommands."""
    action = getattr(args, "pipelines_action", None)
    if action == "check":
        name = getattr(args, "pipeline_name", None)
        if not name:
            print("(no pipeline name provided)")
            return 0
        from megaplan._pipeline.registry import get_pipeline
        from megaplan._pipeline.validator import validate

        try:
            pipeline = get_pipeline(name)
        except Exception as exc:  # discovery / build failure
            print(f"pipelines check: failed to load {name!r}: {exc}", file=sys.stderr)
            return 1
        diag = validate(pipeline)
        if diag.ok:
            print(name)
            return 0
        print(f"pipelines check: {name!r} has {len(diag.defects)} defect(s):", file=sys.stderr)
        for defect in diag.defects:
            print(f"  - {defect}", file=sys.stderr)
        return 1
    if action == "doctor":
        from megaplan._pipeline.registry import scan_python_pipelines

        dispositions = scan_python_pipelines()
        for disp in dispositions:
            line = f"{disp.status}\t{disp.origin}\t{disp.path}"
            if disp.cli_name:
                line += f"\t(name={disp.cli_name})"
            if disp.reason:
                line += f"\treason={disp.reason}"
            print(line)
            if disp.traceback:
                for tb_line in disp.traceback.rstrip("\n").splitlines():
                    print(f"    {tb_line}")
        return 0
    if action == "new":
        from megaplan._pipeline.registry import _SCAN_ROOTS, _cli_name

        name = getattr(args, "pipeline_name", None)
        if not name:
            print("pipelines new: missing pipeline name", file=sys.stderr)
            return 1

        # Derive the module stem (hyphens → underscores) and directory name.
        module_stem = name.replace("-", "_")
        cli_name = _cli_name(module_stem)  # normalise underscores→hyphens

        # Locate the in-tree pipelines directory (first scan root).
        pipelines_dir = None
        for dir_path, pkg_prefix in _SCAN_ROOTS:
            if pkg_prefix == "megaplan.pipelines":
                pipelines_dir = dir_path
                break
        if pipelines_dir is None or not pipelines_dir.is_dir():
            print("pipelines new: cannot locate in-tree pipelines directory", file=sys.stderr)
            return 1

        module_path = pipelines_dir / f"{module_stem}.py"
        skill_dir = pipelines_dir / cli_name
        skill_path = skill_dir / "SKILL.md"

        if module_path.exists():
            print(f"pipelines new: {module_path} already exists", file=sys.stderr)
            return 1
        if skill_path.exists():
            print(f"pipelines new: {skill_path} already exists", file=sys.stderr)
            return 1

        # ── Scaffold the Python module ────────────────────────────
        module_content = (
            f'"""Python composition of the ``{cli_name}`` pipeline."""\n'
            f"\n"
            f"from __future__ import annotations\n"
            f"\n"
            f"from pathlib import Path\n"
            f"\n"
            f"from megaplan._pipeline.types import Pipeline\n"
            f"\n"
            f"\n"
            f'_PIPELINE_DIR: Path = Path(__file__).parent / "{cli_name}"\n'
            f"\n"
            f'\n'
            f'description: str = "TODO: add a description"\n'
            f"\n"
            f"\n"
            f"def build_pipeline() -> Pipeline:\n"
            f'    """Return the canonical ``{cli_name}`` :class:`Pipeline`."""\n'
            f"    return (\n"
            f"        Pipeline.builder(\n"
            f'            "{cli_name}",\n'
            f"            description=description,\n"
            f"            pipeline_dir=_PIPELINE_DIR,\n"
            f"        )\n"
            f'        .agent("run", prompt="TODO: add your prompt file path")\n'
            f"        .build()\n"
            f"    )\n"
            f"\n"
            f"\n"
            f"__all__ = [\n"
            f'    "build_pipeline",\n'
            f'    "description",\n'
            f"]\n"
        )
        skill_dir.mkdir(parents=True, exist_ok=True)
        module_path.write_text(module_content, encoding="utf-8")

        # ── Scaffold the SKILL.md stub ────────────────────────────
        skill_content = (
            f"---\n"
            f"name: {cli_name}\n"
            f"description: TODO: add a description\n"
            f"---\n"
            f"\n"
            f"# {cli_name}\n"
            f"\n"
            f"TODO: add pipeline documentation\n"
        )
        skill_path.write_text(skill_content, encoding="utf-8")

        print(f"Scaffolded pipeline {cli_name!r}:")
        print(f"  module: {module_path}")
        print(f"  skill:  {skill_path}")
        return 0

    print(f"pipelines: unknown action {action!r}", file=sys.stderr)
    return 1


COMMAND_HANDLERS: dict[str, Callable[..., StepResponse]] = {
    "init": handle_init,
    "plan": handle_plan,
    "prep": handle_prep,
    "critique": handle_critique,
    "revise": handle_revise,
    "gate": handle_gate,
    "finalize": handle_finalize,
    "execute": handle_execute,
    "review": handle_review,
    "status": handle_status,
    "audit": handle_audit,
    "progress": handle_progress,
    "watch": handle_watch,
    "resume": handle_resume,
    "feedback": handle_feedback,
    "list": handle_list,
    "loop-init": handle_loop_init,
    "loop-run": handle_loop_run,
    "loop-status": handle_loop_status,
    "loop-pause": handle_loop_pause,
    "debt": handle_debt,
    "user-action": handle_user_action,
    "ticket": handle_ticket,
    "epic": handle_epic,
    "migrate-local-plans": handle_migrate_local_plans,
    "step": handle_step,
    "override": handle_override,
    "verify-human": handle_verify_human,
    "audit-verifiability": handle_audit_verifiability,
    "tiebreaker-run": handle_tiebreaker_run,
    "introspect": _handle_introspect,
    "cost": _handle_cost,
    "trace": _handle_trace,
    "doctor": _handle_doctor,
    "record-tag": _handle_record_tag,
    "pipelines": _handle_pipelines,
    "quality-gate": handle_quality_gate,
}


def cli_entry() -> None:
    sys.exit(main())



def _setup_init_worktree(args: argparse.Namespace) -> None:
    """When ``--in-worktree`` is set on ``megaplan init``, create the worktree
    and rewrite ``args`` so the rest of the init flow lands inside it.

    Safety contract: this function MUST be strictly additive. It may only
    create one new branch + one new worktree directory. It never modifies the
    invoking repo, its branches (other than the one it creates), its remotes,
    its stash, or any other worktree. If anything looks ambiguous, it raises.
    """
    name = getattr(args, "in_worktree", None)
    clean_worktree = bool(getattr(args, "clean_worktree", False))
    carry_dirty_flag = bool(getattr(args, "carry_dirty", False))
    if clean_worktree and carry_dirty_flag:
        raise CliError(
            "invalid_args",
            "--clean-worktree and --carry-dirty are mutually exclusive",
        )
    if name is None:
        if getattr(args, "worktree_from", None):
            raise CliError(
                "invalid_args",
                "--worktree-from is only valid alongside --in-worktree",
            )
        if clean_worktree or carry_dirty_flag:
            raise CliError(
                "invalid_args",
                "--clean-worktree / --carry-dirty are only valid with --in-worktree",
            )
        return

    from megaplan.bakeoff.worktree import (
        branch_exists,
        carry_dirty_state_atomic,
        create_named_worktree,
        ensure_no_inprogress_op,
        has_dirty_state,
        resolve_ref,
        validate_worktree_name,
        worktree_registered,
    )

    if getattr(args, "project_dir", None):
        raise CliError(
            "invalid_args",
            "pass either --project-dir or --in-worktree, not both",
        )

    validate_worktree_name(name)

    # Locate the invoking repo. We deliberately do NOT use --project-dir here
    # (we just rejected it above); we use cwd-walk-up so the user can run
    # `megaplan init --in-worktree foo` from anywhere inside the repo.
    invoking_repo = _find_git_root(Path.cwd().resolve())
    if invoking_repo is None:
        raise CliError(
            "not_a_git_repo",
            "--in-worktree requires running from inside a git repository",
        )

    ensure_no_inprogress_op(invoking_repo)

    target = (Path.home() / "Documents" / ".megaplan-worktrees" / name).resolve()
    if target.exists():
        raise CliError(
            "worktree_target_exists",
            f"refusing to create worktree: target path already exists: {target}",
        )
    if worktree_registered(invoking_repo, target):
        raise CliError(
            "worktree_already_registered",
            f"git already has a worktree registered at {target} "
            "(run `git worktree prune` manually if it's stale)",
        )
    if branch_exists(invoking_repo, name):
        raise CliError(
            "worktree_branch_exists",
            f"branch {name!r} already exists locally or on a remote; "
            "pick a different --in-worktree name",
        )

    base_ref = getattr(args, "worktree_from", None) or "HEAD"
    base_sha = resolve_ref(invoking_repo, base_ref)

    create_named_worktree(invoking_repo, target, base_sha, name)

    # Carry uncommitted state from the source repo into the new worktree
    # unless the caller explicitly opted out via --clean-worktree. The source
    # repo is read-only throughout: we only capture a diff and copy untracked
    # files; we never run stash/checkout/reset/clean on it.
    tracked_carried = 0
    untracked_carried = 0
    if not clean_worktree:
        should_carry = carry_dirty_flag or has_dirty_state(invoking_repo)
        if should_carry:
            tracked_carried, untracked_carried = carry_dirty_state_atomic(
                invoking_repo, target
            )

    # Rewrite args so the rest of the init flow lands inside the worktree.
    args.project_dir = str(target)
    # Stash audit data on args so handle_init can persist it into plan state.
    args._worktree_meta = {
        "name": name,
        "path": str(target),
        "branch": name,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "source_repo": str(invoking_repo),
        "carried_tracked": tracked_carried,
        "carried_untracked": untracked_carried,
    }
    # Update work-dir override so subprocess workers run in the worktree.
    from megaplan.workers import set_work_dir_override

    set_work_dir_override(target)

    print(
        f"Created worktree at {target} on branch {name} "
        f"(base {base_sha[:12]}); initializing plan inside it...",
        file=sys.stderr,
    )
    if tracked_carried or untracked_carried:
        print(
            f"warning: carried {tracked_carried} uncommitted file change(s) "
            f"and {untracked_carried} untracked file(s) from {invoking_repo} "
            f"into {target}. Source worktree is unchanged.\n"
            f"  * To start the worktree from a clean base instead, commit your "
            f"changes first or re-run with --clean-worktree.\n"
            f"  * Files were carried as unstaged in the new worktree (staging "
            f"information is not preserved). Run `git diff` or `git status` "
            f"inside the worktree to inspect.",
            file=sys.stderr,
        )


def _setup_chain_worktree(args: argparse.Namespace) -> None:
    """Create a shared worktree for ``megaplan chain`` and reroot the command.

    Unlike ``megaplan init --in-worktree``, this creates one worktree for the
    entire chain. Every milestone plan initialized by the chain then receives
    ``--project-dir <that-worktree>`` from the chain driver.
    """
    name = getattr(args, "in_worktree", None)
    clean_worktree = bool(getattr(args, "clean_worktree", False))
    carry_dirty_flag = bool(getattr(args, "carry_dirty", False))
    action = getattr(args, "chain_action", None)
    if clean_worktree and carry_dirty_flag:
        raise CliError(
            "invalid_args",
            "--clean-worktree and --carry-dirty are mutually exclusive",
        )
    if name is None:
        if getattr(args, "worktree_from", None):
            raise CliError(
                "invalid_args",
                "--worktree-from is only valid alongside --in-worktree",
            )
        if clean_worktree or carry_dirty_flag:
            raise CliError(
                "invalid_args",
                "--clean-worktree / --carry-dirty are only valid with --in-worktree",
            )
        return

    if action not in (None, "start"):
        raise CliError(
            "invalid_args",
            "--in-worktree is only valid for `megaplan chain start`",
        )
    if getattr(args, "project_dir", None):
        raise CliError(
            "invalid_args",
            "pass either --project-dir or --in-worktree, not both",
        )

    from megaplan.bakeoff.worktree import (
        branch_exists,
        carry_dirty_state_atomic,
        create_named_worktree,
        ensure_no_inprogress_op,
        has_dirty_state,
        resolve_ref,
        validate_worktree_name,
        worktree_registered,
    )

    validate_worktree_name(name)

    invoking_repo = _find_git_root(Path.cwd().resolve())
    if invoking_repo is None:
        raise CliError(
            "not_a_git_repo",
            "--in-worktree requires running from inside a git repository",
        )
    ensure_no_inprogress_op(invoking_repo)

    target = (Path.home() / "Documents" / ".megaplan-worktrees" / name).resolve()
    if target.exists():
        raise CliError(
            "worktree_target_exists",
            f"refusing to create worktree: target path already exists: {target}",
        )
    if worktree_registered(invoking_repo, target):
        raise CliError(
            "worktree_already_registered",
            f"git already has a worktree registered at {target} "
            "(run `git worktree prune` manually if it's stale)",
        )
    if branch_exists(invoking_repo, name):
        raise CliError(
            "worktree_branch_exists",
            f"branch {name!r} already exists locally or on a remote; "
            "pick a different --in-worktree name",
        )

    base_ref = getattr(args, "worktree_from", None) or "HEAD"
    base_sha = resolve_ref(invoking_repo, base_ref)
    create_named_worktree(invoking_repo, target, base_sha, name)

    tracked_carried = 0
    untracked_carried = 0
    if not clean_worktree:
        should_carry = carry_dirty_flag or has_dirty_state(invoking_repo)
        if should_carry:
            tracked_carried, untracked_carried = carry_dirty_state_atomic(
                invoking_repo, target
            )

    args.project_dir = str(target)
    from megaplan.workers import set_work_dir_override

    set_work_dir_override(target)

    print(
        f"Created chain worktree at {target} on branch {name} "
        f"(base {base_sha[:12]}); running chain inside it...",
        file=sys.stderr,
    )
    if tracked_carried or untracked_carried:
        print(
            f"warning: carried {tracked_carried} uncommitted file change(s) "
            f"and {untracked_carried} untracked file(s) from {invoking_repo} "
            f"into {target}. Source worktree is unchanged.",
            file=sys.stderr,
        )



def _handle_list_pipelines(args: argparse.Namespace) -> StepResponse:
    """Handle ``megaplan list pipelines`` — list registered pipelines."""
    from megaplan._pipeline.registry import (
        describe_pipeline,
        pipeline_metadata,
        registered_pipelines,
    )

    verbose = getattr(args, "verbose", False)

    items: list[dict[str, Any]] = []
    for name in registered_pipelines():
        entry: dict[str, Any] = {"name": name}
        meta = pipeline_metadata(name)
        desc = describe_pipeline(name) or str(meta.get("description") or "")
        if desc:
            entry["description"] = desc.split("\n", 1)[0]
        if verbose:
            default_profile = meta.get("default_profile")
            if default_profile:
                entry["default_profile"] = default_profile
            modes = meta.get("supported_modes") or ()
            if modes:
                entry["modes"] = list(modes)
            recommended = meta.get("recommended_profiles") or ()
            if recommended:
                entry["recommended_profiles"] = list(recommended)
        items.append(entry)

    return {
        "success": True,
        "step": "list",
        "summary": f"Found {len(items)} pipeline(s): {', '.join(n['name'] for n in items)}",
        "pipelines": items,
    }


def handle_describe(args: argparse.Namespace) -> StepResponse:
    """Handle ``megaplan describe <pipeline>`` command."""
    from megaplan._pipeline.registry import (
        describe_pipeline,
        pipeline_metadata,
        registered_pipelines,
        read_pipeline_skill_md,
    )

    name = args.pipeline_name
    if name not in set(registered_pipelines()):
        return {
            "success": False,
            "step": "describe",
            "error": f"Unknown pipeline: {name}",
        }

    meta = pipeline_metadata(name)
    desc = describe_pipeline(name) or str(meta.get("description") or "")
    lines: list[str] = [f"Pipeline: {name}"]
    if desc:
        lines.append("")
        lines.append(desc)
    default_profile = meta.get("default_profile")
    if default_profile:
        lines.append(f"Default profile: {default_profile}")
    recommended = meta.get("recommended_profiles") or ()
    if recommended:
        lines.append("Recommended profiles: " + ", ".join(recommended))
    modes = meta.get("supported_modes") or ()
    if modes:
        lines.append("Modes: " + ", ".join(modes))
    skill_md = read_pipeline_skill_md(name)
    if skill_md:
        lines.append("")
        lines.append("SKILL.md:")
        lines.append(skill_md.rstrip())

    # For CLI rendering, print directly (descriptions are long-form text)
    print("\n".join(lines))
    return {
        "success": True,
        "step": "describe",
        "pipeline": name,
    }


def _auto_sync_installed_skills() -> None:
    try:
        for target in _GLOBAL_TARGETS:
            agent_dir = Path.home() / target["detect"]
            if not agent_dir.is_dir():
                continue
            mode = target.get("install")
            if mode == "symlink":
                _install_owned_symlink(
                    Path.home() / target["path"],
                    _resolve_bundle_path(target["data"]),
                    force=False,
                )
            elif mode == "dir_symlink":
                _install_owned_dir_symlink(
                    Path.home() / target["path"],
                    _resolve_bundle_path(target["data"]),
                    force=False,
                )
            else:
                _install_owned_file(
                    Path.home() / target["path"],
                    bundled_global_file(target["data"]),
                    force=False,
                )
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "cloud":
        from megaplan.cloud.cli import _register_cloud_subcommands, run_cloud_cli

        cloud_parser = argparse.ArgumentParser(prog="megaplan cloud")
        _register_cloud_subcommands(cloud_parser)
        cloud_args = cloud_parser.parse_args(argv[1:])
        root = _find_megaplan_root(Path.cwd())
        ensure_runtime_layout(root)
        try:
            return run_cloud_cli(root, cloud_args)
        except CliError as error:
            return error_response(error, root=root)
    if argv and argv[0] == "resident":
        from megaplan.resident.cli import (
            _register_resident_subcommands,
            run_resident_cli,
        )

        resident_parser = argparse.ArgumentParser(prog="megaplan resident")
        _register_resident_subcommands(resident_parser)
        resident_args = resident_parser.parse_args(argv[1:])
        root = _find_megaplan_root(Path.cwd())
        ensure_runtime_layout(root)
        try:
            return render_response(run_resident_cli(root, resident_args))
        except CliError as error:
            return error_response(error, root=root)
    if argv and argv[0] == "bakeoff":
        from megaplan.bakeoff.cli import _register_bakeoff_subcommands, run_bakeoff_cli

        bakeoff_parser = argparse.ArgumentParser(prog="megaplan bakeoff")
        _register_bakeoff_subcommands(bakeoff_parser)
        bakeoff_args = bakeoff_parser.parse_args(argv[1:])
        root = _find_megaplan_root(Path.cwd())
        ensure_runtime_layout(root)
        try:
            return run_bakeoff_cli(root, bakeoff_args)
        except CliError as error:
            return error_response(error, root=root)

    parser = build_parser()
    args, remaining = parser.parse_known_args(argv)
    if args.command != "setup":
        _auto_sync_installed_skills()
    try:
        if args.command == "setup":
            result = handle_setup(args)
            if getattr(args, "regen_composed", False) and not result.get(
                "success", True
            ):
                print(json_dump(result))
                return 1
            return render_response(result)
        if args.command == "config":
            return render_response(handle_config(args))
    except CliError as error:
        return error_response(error)

    # Capture an explicit --work-dir override for subprocess workers
    # (--add-dir / -C). When the flag is NOT passed, leave the override unset
    # so :func:`resolve_work_dir` can default to the plan's stored project_dir
    # (persisted at ``megaplan init``). Defaulting to CWD here silently
    # sandboxes codex to whatever subdirectory the shell happened to be in,
    # which breaks cross-subrepo writes — see resolve_work_dir for the
    # precedence rules.
    from megaplan.workers import set_work_dir_override

    work_dir_override = getattr(args, "work_dir", None)
    set_work_dir_override(Path(work_dir_override) if work_dir_override else None)

    # Handle --in-worktree on `init` *before* resolving project root. This
    # creates the worktree and rewrites args.project_dir to point at it, so
    # everything downstream behaves as if the user had passed --project-dir
    # <worktree> manually.
    if args.command == "init":
        try:
            _setup_init_worktree(args)
        except CliError as error:
            return error_response(error)
        if not getattr(args, "project_dir", None):
            return error_response(
                CliError(
                    "invalid_args",
                    "megaplan init requires --project-dir or --in-worktree",
                )
            )
    elif args.command == "chain":
        try:
            _setup_chain_worktree(args)
        except CliError as error:
            return error_response(error)

    try:
        root = _resolve_project_root(args)
    except CliError as error:
        return error_response(error)
    ensure_runtime_layout(root)

    if args.command == "auto":
        from megaplan.auto import run_auto

        try:
            return run_auto(root, args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "run":
        from megaplan._pipeline.run_cli import cli_run

        try:
            return cli_run(args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "describe":
        try:
            response = handle_describe(args)
            return render_response(response)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "chain":
        from megaplan.chain import run_chain_cli

        try:
            return run_chain_cli(root, args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "tiebreaker":
        from megaplan.prompts.tiebreaker_orchestrator import run_tiebreaker_cli

        try:
            return run_tiebreaker_cli(root, args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command in {"introspect", "trace", "doctor", "record-tag", "pipelines"}:
        handler = COMMAND_HANDLERS.get(args.command)
        if handler is not None:
            return handler(root, args)

    try:
        handler = COMMAND_HANDLERS.get(args.command)
        if handler is None:
            raise CliError("invalid_command", f"Unknown command {args.command!r}")
        # Ticket handler has a different signature (no root, returns int)
        if args.command == "ticket":
            return handler(args)
        from megaplan.orchestration.progress import ProgressEmitter

        args.progress_emitter = ProgressEmitter.from_env()
        if args.command == "override" and remaining:
            if not args.note:
                args.note = " ".join(remaining)
            remaining = []
        if remaining:
            parser.error(f"unrecognized arguments: {' '.join(remaining)}")
        if (
            args.command == "override"
            and args.override_action == "add-note"
            and not args.note
        ):
            raise CliError("invalid_args", "override add-note requires a note")
        if (
            args.command == "override"
            and args.override_action == "recover-blocked"
            and not args.reason
        ):
            raise CliError("invalid_args", "override recover-blocked requires --reason")
        if (
            args.command == "override"
            and args.override_action == "set-robustness"
            and not args.robustness
        ):
            raise CliError(
                "invalid_args",
                f"override set-robustness requires --robustness {'|'.join(ROBUSTNESS_ACCEPTED)}",
            )
        if (
            args.command == "override"
            and args.override_action == "set-profile"
            and not args.profile
        ):
            raise CliError(
                "invalid_args", "override set-profile requires --profile NAME"
            )
        if (
            args.command == "user-action"
            and getattr(args, "user_action_action", None) == "resolve"
        ):
            if not getattr(args, "action_id", None):
                raise CliError(
                    "invalid_args", "user-action resolve requires --action-id"
                )
            if not getattr(args, "resolution", None):
                raise CliError(
                    "invalid_args", "user-action resolve requires --resolution"
                )
        if (
            args.command == "quality-gate"
            and getattr(args, "quality_gate_action", None) == "resolve"
        ):
            if not getattr(args, "blocker_id", None):
                raise CliError(
                    "invalid_args", "quality-gate resolve requires --blocker-id"
                )
            if not getattr(args, "resolution", None):
                raise CliError(
                    "invalid_args", "quality-gate resolve requires --resolution"
                )
        if args.command == "override" and args.override_action == "set-model" and not args.phase:
            raise CliError("invalid_args", "override set-model requires --phase PHASE")
        if args.command == "override" and args.override_action == "set-model" and not args.model:
            raise CliError("invalid_args", "override set-model requires --model MODEL")
        if args.command == "init" and getattr(args, "from_arnold_epic", None):
            from megaplan.store import DBStore

            epic_id = args.from_arnold_epic
            store = DBStore(actor_id=None)  # read-only path
            try:
                epic = store.load_epic(epic_id)
                # Sprint 3: write-back to DB — load_hot_context for future context injection
            except Exception as exc:
                print(f"Error: failed to load epic {epic_id!r}: {exc}", file=sys.stderr)
                return 1
            finally:
                store.close()
            if epic is None:
                print(f"Error: epic {epic_id!r} not found.", file=sys.stderr)
                return 1
            parts = [epic.title]
            if epic.goal:
                parts.append(epic.goal)
            if epic.body:
                parts.append(epic.body)
            args.idea = "\n\n".join(parts)
        if args.command in _PROGRESS_PHASE_COMMANDS:
            args.progress_emitter.phase_start(
                args.command, plan=getattr(args, "plan", None)
            )
        response = handler(root, args)
        _emit_response_progress(args.command, response, args.progress_emitter)
        return render_response(response)
    except CliError as error:
        if "args" in locals() and hasattr(args, "progress_emitter"):
            _emit_error_progress(
                getattr(args, "command", ""), error, args.progress_emitter
            )
        return error_response(error, root=root)


if __name__ == "__main__":
    sys.exit(main())
