#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.profiles import (
    DEFAULT_AGENT_ROUTING,
    KNOWN_AGENTS,
    ROBUSTNESS_ACCEPTED,
    ROBUSTNESS_LEVELS,
    effective_premium_vendor,
)
from arnold_pipelines.megaplan.runtime.process import megaplan_engine_root
from arnold_pipelines.megaplan.types import (
    CliError,
    DEFAULTS,
    StepResponse,
    _SETTABLE_BOOL,
    _SETTABLE_ENUM,
    _SETTABLE_NUMERIC,
    format_agent_spec,
    is_premium_placeholder_spec,
    resolve_premium_placeholder_spec,
)
from arnold_pipelines.megaplan.planning.state import STATE_BLOCKED, STATE_DONE, STATE_REVIEWED, TERMINAL_STATES
from arnold_pipelines.megaplan._core import (
    active_phase_name,
    active_plan_dirs,
    add_or_increment_debt,
    atomic_write_text,
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
from arnold_pipelines.megaplan.execute.batch import build_monitor_hint
from arnold_pipelines.megaplan.forms import available_form_ids
from arnold_pipelines.megaplan.handlers import (
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
from arnold_pipelines.megaplan.loop.handlers import (
    handle_loop_init,
    handle_loop_pause,
    handle_loop_run,
    handle_loop_status,
)
from arnold_pipelines.megaplan.profiles import (
    load_profile_sources,
    load_profiles,
    resolve_profile,
)
from arnold_pipelines.megaplan.execute.step_edit import handle_step
from arnold_pipelines.megaplan.observability.doctor import handle_doctor
from arnold_pipelines.megaplan.observability.trace import handle_trace
from arnold_pipelines.megaplan.resolutions import SUPPORTED_USER_ACTION_RESOLUTION_STATES
from arnold_pipelines.megaplan.quality_resolutions import (
    VALID_RESOLUTIONS as QUALITY_GATE_RESOLUTION_STATES,
)
from arnold_pipelines.megaplan.user_actions import (
    FALLBACK,
    OMIT,
)
from .feedback import (
    _collect_feedback_rows,
    _filter_feedback_rows,
    _render_feedback_table,
    handle_feedback,
)
from .editor_setup import maybe_auto_sync_repo_editor_support
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
    _canonical_prep_skill,
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


def _add_vendor_critic_args(parser: argparse.ArgumentParser) -> None:
    """Wire profile modifier flags onto a subparser."""

    parser.add_argument("--vendor", choices=["claude", "codex"], default=None)
    parser.add_argument(
        "--depth",
        choices=["minimal", "low", "medium", "high", "xhigh", "max"],
        default=None,
    )
    parser.add_argument("--critic", choices=["kimi", "cross"], default=None)
    parser.add_argument("--deepseek-provider", choices=["direct"], default=None)


def build_parser() -> argparse.ArgumentParser:
    """Build the Megaplan CLI parser from the surviving CLI module."""

    parser = argparse.ArgumentParser(description="Megaplan orchestration CLI")
    parser.add_argument("--actor", default=None, metavar="ID")
    parser.add_argument("--backend", choices=["file", "db"], default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    from arnold_pipelines.megaplan.auto import build_auto_parser
    from arnold_pipelines.megaplan.chain import build_chain_parser
    from arnold_pipelines.megaplan.chain.epic_chain import build_epic_chain_parser

    setup_parser = subparsers.add_parser("setup")
    setup_parser.add_argument("--local", action="store_true")
    setup_parser.add_argument("--target-dir")
    setup_parser.add_argument("--force", action="store_true")
    setup_parser.add_argument("--regen-composed", action="store_true")
    setup_parser.add_argument("--install-hooks", action="store_true")
    setup_parser.add_argument("--editors", action="store_true")
    setup_parser.add_argument("--user-editors", action="store_true")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--project-dir", required=False)
    init_parser.add_argument("--in-worktree", default=None)
    init_parser.add_argument("--worktree-from", default=None)
    init_parser.add_argument("--clean-worktree", action="store_true", default=False)
    init_parser.add_argument("--carry-dirty", action="store_true", default=False)
    init_parser.add_argument("--name")
    init_parser.add_argument("--auto-approve", action="store_true", default=None)
    init_parser.add_argument("--adaptive-critique", action="store_true", default=None)
    init_parser.add_argument("--strict-adaptive-critique", action="store_true", default=None)
    init_parser.add_argument("--profile", default=None)
    init_parser.add_argument("--robustness", choices=ROBUSTNESS_ACCEPTED, default=None)
    init_parser.add_argument("--with-prep", action="store_true", default=False)
    init_parser.add_argument("--prep-direction", default=None)
    init_parser.add_argument("--with-feedback", action="store_true", default=False)
    init_parser.add_argument("--no-prep-clarify", dest="prep_clarify", action="store_false", default=True)
    _add_vendor_critic_args(init_parser)
    init_parser.add_argument("--phase-model", action="append", default=None)
    init_parser.add_argument("--idea-file", default=None)
    init_parser.add_argument("idea", nargs="?")

    for command in ("prep", "plan", "critique", "gate", "revise", "finalize", "execute", "review"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--plan", required=False)
        sub.add_argument("--fresh", action="store_true", default=False)
        sub.add_argument("--persist", action="store_true", default=False)
        sub.add_argument("--ephemeral", action="store_true", default=False)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--plan", required=False)
    status_parser.add_argument("--project-dir", dest="project_dir")
    status_parser.add_argument("--pending-human", action="store_true", default=False)

    authority_inventory_parser = subparsers.add_parser(
        "authority-inventory",
        help="Report the read-only authority evidence inventory for a plan.",
    )
    authority_inventory_parser.add_argument("--plan", required=False)
    authority_inventory_parser.add_argument("--project-dir", dest="project_dir")
    authority_inventory_parser.add_argument(
        "--session",
        default=None,
        help="Optional cloud session whose marker evidence should be observed.",
    )
    authority_inventory_parser.add_argument(
        "--marker-dir",
        default=None,
        help="Directory containing optional cloud session marker files.",
    )

    override_parser = subparsers.add_parser("override")
    override_parser.add_argument(
        "override_action",
        choices=[
            "add-note",
            "abort",
            "adopt-execution",
            "force-proceed",
            "recover-blocked",
            "replan",
            "resume-clarify",
            "set-model",
            "set-profile",
            "set-robustness",
            "set-vendor",
        ],
    )
    override_parser.add_argument("--plan", required=False)
    override_parser.add_argument("--note")
    override_parser.add_argument("--source", default="user")
    override_parser.add_argument("--reason")
    override_parser.add_argument("--user-approved", action="store_true", default=False)
    override_parser.add_argument("--robustness", choices=ROBUSTNESS_ACCEPTED)
    override_parser.add_argument("--profile")
    override_parser.add_argument("--phase")
    override_parser.add_argument("--model")
    override_parser.add_argument("--effort")
    override_parser.add_argument("--vendor")
    override_parser.add_argument("--expires-after-runs", dest="expires_after_runs", type=int)
    override_parser.add_argument("--project-dir", dest="project_dir")
    override_parser.add_argument("--target-root", dest="target_root")

    user_action_parser = subparsers.add_parser("user-action")
    user_action_sub = user_action_parser.add_subparsers(dest="user_action_action", required=True)
    user_action_resolve = user_action_sub.add_parser("resolve")
    user_action_resolve.add_argument("--plan", required=False)
    user_action_resolve.add_argument("--action-id", dest="action_id")
    user_action_resolve.add_argument(
        "--resolution",
        choices=sorted(SUPPORTED_USER_ACTION_RESOLUTION_STATES),
    )
    user_action_resolve.add_argument("--reason")
    user_action_resolve.add_argument("--instructions")
    user_action_resolve.add_argument("--tasks")
    user_action_resolve.add_argument("--phase")
    user_action_resolve.add_argument("--evidence", action="append")
    user_action_resolve.add_argument("--debt-note", dest="debt_note")
    user_action_resolve.add_argument("--fallback-mode", dest="fallback_mode")

    quality_gate_parser = subparsers.add_parser("quality-gate")
    quality_gate_sub = quality_gate_parser.add_subparsers(dest="quality_gate_action", required=True)
    quality_gate_resolve = quality_gate_sub.add_parser("resolve")
    quality_gate_resolve.add_argument("--plan", required=False)
    quality_gate_resolve.add_argument("--blocker-id", dest="blocker_id")
    quality_gate_resolve.add_argument(
        "--resolution",
        choices=QUALITY_GATE_RESOLUTION_STATES,
    )
    quality_gate_resolve.add_argument("--phase")
    quality_gate_resolve.add_argument("--evidence", action="append")
    quality_gate_resolve.add_argument("--debt-note", dest="debt_note")
    quality_gate_resolve.add_argument("--fallback-mode", dest="fallback_mode")

    build_auto_parser(subparsers)
    build_chain_parser(subparsers)
    build_epic_chain_parser(subparsers)

    brief_parser = subparsers.add_parser("brief")
    brief_sub = brief_parser.add_subparsers(dest="brief_action", required=True)
    brief_new = brief_sub.add_parser("new")
    brief_new.add_argument("slug")
    brief_new.add_argument("body", nargs="?")
    brief_new.add_argument("-b", "--body", dest="body_flag")
    brief_new.add_argument("--stdin-body", action="store_true")
    brief_new.add_argument("--from-file")
    brief_new.add_argument("--force", action="store_true")
    brief_new.add_argument("--init", action="store_true")
    brief_list = brief_sub.add_parser("list")
    brief_show = brief_sub.add_parser("show")
    brief_show.add_argument("brief_id")
    brief_search = brief_sub.add_parser("search")
    brief_search.add_argument("keywords", nargs="*")
    brief_search.add_argument("--keywords-all", action="store_true")
    brief_search.add_argument("--sort", default="path")
    brief_search.add_argument("--desc", action="store_true")
    brief_search.add_argument("--limit", type=int)
    brief_search.add_argument("--snippet", action="store_true", default=True)
    brief_epic = brief_sub.add_parser("epic")
    brief_epic.add_argument("slug")
    brief_epic.add_argument("--milestone", action="append", default=[])
    brief_epic.add_argument("--base-branch", default="main")
    brief_epic.add_argument("--force", action="store_true")

    initiative_parser = subparsers.add_parser("initiative")
    initiative_sub = initiative_parser.add_subparsers(dest="initiative_action", required=True)
    initiative_new = initiative_sub.add_parser("new")
    initiative_new.add_argument("slug")
    initiative_new.add_argument("--title")
    description_group = initiative_new.add_mutually_exclusive_group(required=False)
    description_group.add_argument("--description")
    description_group.add_argument("--description-file")
    initiative_new.add_argument("--north-star")
    initiative_new.add_argument("--north-star-file")
    initiative_new.add_argument("--chain", action="store_true")
    initiative_new.add_argument(
        "--doc",
        action="append",
        default=[],
        metavar="KIND=PATH",
        help=(
            "Copy an existing starting document into the initiative. KIND is one of "
            "research, decisions, notes, assets, or handoff. Repeatable."
        ),
    )
    initiative_new.add_argument(
        "--milestone",
        action="append",
        default=[],
        help="Add a milestone as LABEL=Title. Implies --chain.",
    )
    initiative_new.add_argument("--base-branch", default="main")
    initiative_new.add_argument("--merge-policy", choices=("auto", "review", "manual"), default="auto")
    initiative_new.add_argument("--branch-prefix")
    initiative_new.add_argument("--profile", default="partnered-5")
    initiative_new.add_argument("--vendor", default="codex")
    initiative_new.add_argument("--robustness", default="full")
    initiative_new.add_argument("--depth", default="high")
    initiative_new.add_argument("--no-with-prep", action="store_true")
    initiative_new.add_argument(
        "--cloud",
        action="store_true",
        help="Write initiative-local cloud.yaml with required edit-before-launch placeholders.",
    )
    initiative_new.add_argument("--repo-url")
    initiative_new.add_argument("--chain-session")
    initiative_new.add_argument("--force", action="store_true")
    initiative_list = initiative_sub.add_parser("list")
    initiative_list.add_argument("--limit", type=int)
    initiative_search = initiative_sub.add_parser("search")
    initiative_search.add_argument("keywords", nargs="*")
    initiative_search.add_argument("--keywords-all", action="store_true")
    initiative_search.add_argument("--limit", type=int)

    # `status` is defined above with its dedicated flags; only add the
    # lightweight observability siblings here.
    for command in ("progress", "watch"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--project-dir", default=None)
        sub.add_argument("--plan")

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--project-dir", default=None)
    audit_parser.add_argument("--plan")
    audit_sub = audit_parser.add_subparsers(dest="audit_action", required=False)
    audit_query = audit_sub.add_parser("query")
    audit_query.add_argument("--model")
    audit_query.add_argument("--phase")
    audit_query.add_argument("--profile")
    audit_query.add_argument("--since")
    audit_query.add_argument("--agg", default="")
    audit_query.add_argument("--json", action="store_true", default=False)
    audit_query.add_argument("--audit-dir", default=None)
    audit_report = audit_sub.add_parser("report")
    audit_report.add_argument("--plan")
    audit_report.add_argument("--compare")
    audit_report.add_argument("--output")
    audit_report.add_argument("--json-output")
    audit_report.add_argument("--format", choices=("markdown", "json"), default="markdown")

    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("--project-dir", default=None)
    resume_parser.add_argument("--plan", required=True)
    resume_parser.add_argument("--choice", default=None)

    verify_human = subparsers.add_parser("verify-human")
    verify_human.add_argument("--project-dir", default=None)
    verify_human.add_argument("--plan")
    verify_human.add_argument("--list", dest="list_flag", action="store_true", default=False)
    verify_human.add_argument("--json", dest="json_flag", action="store_true", default=False)
    verify_human.add_argument("--criterion", default=None)
    verify_human.add_argument("--pass", dest="pass_flag", action="store_true", default=False)
    verify_human.add_argument("--fail", dest="fail_flag", action="store_true", default=False)
    verify_human.add_argument("--evidence", default=None)

    audit_verifiability = subparsers.add_parser("audit-verifiability")
    audit_verifiability.add_argument("--project-dir", default=None)
    audit_verifiability.add_argument("--plan")

    migrate_layout = subparsers.add_parser("migrate-layout")
    migrate_layout.add_argument("--apply", action="store_true")

    pipelines_parser = subparsers.add_parser("pipelines")
    pipelines_sub = pipelines_parser.add_subparsers(dest="pipelines_action", required=True)
    pipelines_new = pipelines_sub.add_parser("new")
    pipelines_new.add_argument("pipeline_name")
    pipelines_new.add_argument("--driver", default=None)
    pipelines_check = pipelines_sub.add_parser("check")
    pipelines_check.add_argument("pipeline_name")
    pipelines_doctor = pipelines_sub.add_parser("doctor")

    # Also add aliases for other COMMAND_HANDLERS that are reached via main()
    # but never registered in the parser.
    for _cmd in ("introspect", "trace", "doctor", "record-tag"):
        observability_parser = subparsers.add_parser(_cmd)
        observability_parser.add_argument("--project-dir", default=None)
        observability_parser.add_argument("--plan")

    return parser
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
    # Handler next_step payloads are compatibility hints only and must not
    # become a live CLI-driven route authority.
    emitter.phase_end(
        step,
        success=bool(response.get("success", True)),
        state=state,
        result=response.get("result"),
        next_step=None,
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


def _legacy_list_route_hints(state: dict[str, Any]) -> dict[str, Any]:
    next_steps = infer_next_steps(state)
    return {
        "next_step": next_steps[0] if next_steps else None,
        "valid_next": list(next_steps),
    }




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
            # cache-tolerant: CLI status aggregation.
            state = read_json(plan_dir / "state.json")
            current_state = state["current_state"]
            state_counts[current_state] = state_counts.get(current_state, 0) + 1
            total_scanned += 1

            if filter_active and current_state in TERMINAL_STATES:
                continue
            if allowed_states and current_state not in allowed_states:
                continue

            legacy_route_hints = _legacy_list_route_hints(state)
            entry = {
                "name": state["name"],
                "idea": state["idea"],
                "state": current_state,
                "iteration": state["iteration"],
                "observed_phase": active_phase_name(state) or current_state,
                "next_step": legacy_route_hints["next_step"],
                "legacy_route_hints": legacy_route_hints,
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
        effective_vendor = effective_premium_vendor(config=config)

        def _display_spec(spec: str) -> str:
            if is_premium_placeholder_spec(spec):
                return format_agent_spec(
                    resolve_premium_placeholder_spec(spec, effective_vendor)
                )
            return spec

        effective_routing = {
            step: config.get("agents", {}).get(step, _display_spec(default))
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
        from arnold_pipelines.megaplan.store import (
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
    from arnold_pipelines.megaplan.store import MultiStore

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


def _capsule_blob_store(store: Any, *, epic_id: str | None = None) -> Any:
    backend = None
    if epic_id is not None and hasattr(store, "_route_for_epic"):
        backend = store._route_for_epic(epic_id)
    elif hasattr(store, "file"):
        backend = store.file
    else:
        backend = store
    blob_store = getattr(backend, "blobs", None)
    if blob_store is None:
        raise CliError(
            "capsule_blob_store_unavailable",
            "Capsule operations require a BlobStore-backed epic backend",
        )
    return blob_store


def _parse_json_object_arg(value: str | None, *, arg_name: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CliError("invalid_args", f"{arg_name} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise CliError("invalid_args", f"{arg_name} must be a JSON object")
    return parsed


def _handle_epic_capsule(root: Path, args: argparse.Namespace) -> StepResponse:
    from arnold_pipelines.megaplan.feature_flags import m7_sinks_on
    from arnold_pipelines.megaplan.store.capsule import (
        CapsuleStorageError,
        build_capsule,
        fork_capsule,
        inspect_capsule,
        list_capsules,
    )

    if not m7_sinks_on():
        raise CliError(
            "feature_disabled",
            "M7 Capsule commands are disabled; set MEGAPLAN_M7_SINKS=1 to enable them.",
        )

    store = build_epic_store(root)
    try:
        action = args.capsule_action
        try:
            if action == "build":
                blob_store = _capsule_blob_store(store, epic_id=args.epic_id)
                result = build_capsule(
                    store,
                    args.epic_id,
                    blob_store,
                    allow_degraded=bool(args.allow_degraded),
                    created_by=args.created_by,
                )
                return {
                    "success": True,
                    "step": "epic",
                    "action": "capsule-build",
                    "epic_id": args.epic_id,
                    "capsule_hash": result.capsule.capsule_hash,
                    "capsule_record_blob_id": result.write_result.capsule_ref.blob_id,
                    "index_blob_id": result.write_result.index_blob_id,
                    "completeness": result.capsule.completeness,
                    "replay_ready": result.capsule.replay_ready,
                    "record_count": len(result.record_refs),
                }
            if action == "inspect":
                blob_store = _capsule_blob_store(store)
                inspection = inspect_capsule(blob_store, args.capsule_hash)
                if not inspection.contract_check.ok or inspection.capsule.completeness != "complete":
                    raise CliError(
                        "capsule_contract_failed",
                        "Capsule inspect found degraded or unmet Contract requirements",
                        extra={
                            "summary": dict(inspection.summary),
                            "failures": list(inspection.contract_check.failures),
                            "adaptations": list(inspection.contract_check.adaptations),
                        },
                    )
                return {
                    "success": True,
                    "step": "epic",
                    "action": "capsule-inspect",
                    "capsule": dict(inspection.summary),
                    "failures": [],
                    "adaptations": list(inspection.contract_check.adaptations),
                }
            if action == "fork":
                blob_store = _capsule_blob_store(store)
                overrides = _parse_json_object_arg(
                    args.definition_overrides_json,
                    arg_name="--definition-overrides-json",
                )
                result = fork_capsule(
                    blob_store,
                    args.capsule_hash,
                    definition_overrides=overrides,
                    created_by=args.created_by,
                )
                return {
                    "success": True,
                    "step": "epic",
                    "action": "capsule-fork",
                    "source_capsule_hash": args.capsule_hash,
                    "capsule_hash": result.capsule.capsule_hash,
                    "parent_edges": result.capsule.lineage.parent_edges,
                    "parent_edge_count": len(result.capsule.lineage.parent_edges),
                    "index_blob_id": result.write_result.index_blob_id,
                }
            if action == "list":
                blob_store = _capsule_blob_store(store)
                return {
                    "success": True,
                    "step": "epic",
                    "action": "capsule-list",
                    "capsules": list_capsules(blob_store),
                }
        except CapsuleStorageError as exc:
            raise CliError(exc.error_kind, str(exc), extra=exc.details) from exc
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()
    raise CliError("invalid_args", f"Unknown epic capsule action: {args.capsule_action}")


def handle_ticket(args: argparse.Namespace) -> int:
    """Dispatch ``megaplan ticket ...`` subcommands."""
    from arnold_pipelines.megaplan.handlers.tickets import TICKET_DISPATCH
    from arnold_pipelines.megaplan.tickets.registry import touch as _registry_touch

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


def handle_contract(root: Path, args: argparse.Namespace) -> StepResponse:
    """Dispatch ``megaplan contract ...`` subcommands."""

    from arnold.pipeline import (
        TELEMETRY_FILENAME,
        StepIOOperation,
        is_step_io_envelope,
        read_violation_records,
    )
    from arnold_pipelines.megaplan.runtime.schema_registry_adapter import (
        create_step_io_contract_context,
    )
    from arnold_pipelines.megaplan.runtime.step_io_policy_adapter import (
        has_megaplan_step_io_self_validation_marker,
        load_megaplan_step_io_policy,
        record_megaplan_step_io_self_validation_marker,
        resolve_megaplan_step_io_policy,
        write_megaplan_step_io_policy,
    )
    from arnold_pipelines.megaplan.store import PlanRepository

    action = getattr(args, "contract_action", None)
    if action == "mode":
        mode_action = getattr(args, "mode_action", None)
        if mode_action == "set":
            plan_dir = resolve_plan_dir(root, args.plan)
            if args.mode == "enforce" and not has_megaplan_step_io_self_validation_marker(plan_dir):
                raise CliError(
                    "contract_self_validation_required",
                    "contract mode enforce requires a successful contract self-validate marker",
                )
            policy = resolve_megaplan_step_io_policy(
                configured_mode=args.mode,
                producer_typed=True,
                consumer_typed=True,
            )
            path = write_megaplan_step_io_policy(plan_dir, policy)
            return {
                "success": True,
                "step": "contract",
                "action": "mode-set",
                "plan": args.plan,
                "policy_path": str(path),
                "policy": policy.to_json(),
            }
        if mode_action == "list":
            repos = (
                [PlanRepository.from_plan_dir(resolve_plan_dir(root, args.plan))]
                if getattr(args, "plan", None)
                else [PlanRepository.from_plan_dir(path) for path in active_plan_dirs(root)]
            )
            return {
                "success": True,
                "step": "contract",
                "action": "mode-list",
                "policies": [
                    {
                        "plan": repo.plan_name,
                        "policy": load_megaplan_step_io_policy(repo.plan_dir),
                    }
                    for repo in repos
                ],
            }
    if action == "violations":
        plan_dir = resolve_plan_dir(root, args.plan)
        records = read_violation_records(plan_dir / TELEMETRY_FILENAME)
        if getattr(args, "as_json", False):
            return {
                "success": True,
                "step": "contract",
                "action": "violations",
                "plan": args.plan,
                "violations": records,
            }
        for record in records:
            print(
                "\t".join(
                    str(record.get(key, ""))
                    for key in ("seam", "artifact", "operation", "classification", "block_reason")
                )
            )
        return {
            "success": True,
            "step": "contract",
            "action": "violations",
            "plan": args.plan,
            "count": len(records),
        }
    if action == "self-validate":
        plan_dir = resolve_plan_dir(root, args.plan)
        repo = PlanRepository.from_plan_dir(plan_dir)
        typed_artifacts: list[str] = []
        for artifact_name in repo.list_artifact_names():
            if (
                not artifact_name.endswith(".json")
                or artifact_name.startswith(".contract_self_validate/")
            ):
                continue
            raw = json.loads(repo.artifact_path(artifact_name).read_text(encoding="utf-8"))
            if not is_step_io_envelope(raw):
                continue
            temp_name = f".contract_self_validate/{artifact_name}"
            repo.write_artifact_json(
                temp_name,
                raw,
                contract_context=create_step_io_contract_context(
                    operation=StepIOOperation.WRITE,
                    explicit_root=plan_dir,
                ),
                contract_binding={"producer_typed": True, "consumer_typed": True},
            )
            repo.read_artifact_json(
                temp_name,
                contract_context=create_step_io_contract_context(
                    operation=StepIOOperation.READ,
                    explicit_root=plan_dir,
                ),
                contract_binding={"producer_typed": True, "consumer_typed": True},
            )
            repo.delete_artifact(temp_name)
            typed_artifacts.append(artifact_name)
        if not typed_artifacts:
            raise CliError(
                "contract_self_validation_no_typed_artifacts",
                "contract self-validate requires at least one typed artifact round trip",
            )
        marker_path = record_megaplan_step_io_self_validation_marker(
            plan_dir,
            typed_artifacts=typed_artifacts,
        )
        return {
            "success": True,
            "step": "contract",
            "action": "self-validate",
            "plan": args.plan,
            "marker_path": str(marker_path),
            "typed_artifacts": typed_artifacts,
        }
    raise CliError("invalid_args", "unknown contract action")


def handle_brief(root: Path, args: argparse.Namespace) -> StepResponse:
    """Dispatch ``megaplan brief ...`` subcommands."""
    from arnold_pipelines.megaplan.briefs import (
        init_from_brief,
        list_briefs,
        scaffold_epic,
        search_briefs,
        show_brief,
        write_single_brief,
    )

    action = args.brief_action
    if action == "new":
        if getattr(args, "stdin_body", False):
            body = sys.stdin.read()
        elif getattr(args, "from_file", None):
            source = Path(args.from_file).expanduser()
            try:
                body = source.read_text(encoding="utf-8")
            except OSError as exc:
                raise CliError("invalid_args", f"Unable to read brief source {source}: {exc}") from exc
        else:
            body = getattr(args, "body_flag", None) or args.body
        try:
            path = write_single_brief(root, args.slug, body, force=bool(args.force))
        except FileExistsError as exc:
            existing = exc.args[0] if exc.args else exc.filename
            raise CliError(
                "brief_exists",
                f"Brief already exists: {existing}. Pass --force to overwrite.",
            ) from exc
        except ValueError as exc:
            raise CliError("invalid_args", str(exc)) from exc
        if bool(args.init):
            proc = init_from_brief(root, path, [])
            if proc.returncode != 0:
                raise CliError(
                    "init_failed",
                    f"megaplan init failed for {path}: {proc.stderr.strip() or proc.stdout.strip()}",
                )
            try:
                init_payload = json.loads(proc.stdout)
            except json.JSONDecodeError as exc:
                raise CliError("init_failed", f"megaplan init returned invalid JSON: {exc}") from exc
            return {
                "success": True,
                "step": "brief",
                "action": "new",
                "path": str(path),
                "initialized": True,
                "init": init_payload,
            }
        return {
            "success": True,
            "step": "brief",
            "action": "new",
            "path": str(path),
        }
    if action == "list":
        return {
            "success": True,
            "step": "brief",
            "action": "list",
            "briefs": _brief_cli_records(list_briefs(root)),
        }
    if action == "epic":
        try:
            chain_path, milestone_paths = scaffold_epic(
                root,
                args.slug,
                args.milestone,
                base_branch=args.base_branch,
                force=bool(args.force),
            )
        except FileExistsError as exc:
            existing = exc.args[0] if exc.args else exc.filename
            raise CliError(
                "brief_exists",
                f"Epic artifact already exists: {existing}. Pass --force to overwrite.",
            ) from exc
        except ValueError as exc:
            raise CliError("invalid_args", str(exc)) from exc
        return {
            "success": True,
            "step": "brief",
            "action": "epic",
            "chain": str(chain_path),
            "north_star": str(chain_path.with_name("NORTHSTAR.md")),
            "milestones": [str(path) for path in milestone_paths],
        }
    if action == "show":
        record = show_brief(root, args.brief_id)
        if record is None:
            raise CliError("not_found", f"Brief not found: {args.brief_id}")
        return {
            "success": True,
            "step": "brief",
            "action": "show",
            "brief": _brief_cli_record(record, include_body=True),
        }
    if action == "search":
        try:
            records = search_briefs(
                root,
                args.keywords or None,
                keywords_all=bool(args.keywords_all),
                sort=args.sort,
                order="desc" if args.desc else "asc",
                limit=args.limit,
                snippet=bool(args.snippet) and bool(args.keywords),
            )
        except ValueError as exc:
            raise CliError("invalid_args", str(exc)) from exc
        return {
            "success": True,
            "step": "brief",
            "action": "search",
            "briefs": _brief_cli_records(records),
        }
    raise CliError("invalid_args", f"Unknown brief action: {action}")


def _brief_cli_record(record: dict[str, Any], *, include_body: bool = False) -> dict[str, Any]:
    """Trim internal brief records for CLI JSON output."""
    keys = ["id", "title", "path", "relative_path", "slug", "epic", "tags", "snippet"]
    out = {key: record.get(key) for key in keys if key in record}
    metadata = record.get("metadata")
    if metadata:
        out["metadata"] = metadata
    if include_body:
        out["body"] = record.get("body", "")
    return out


def _brief_cli_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_brief_cli_record(record) for record in records]


def handle_initiative(root: Path, args: argparse.Namespace) -> StepResponse:
    """Dispatch ``megaplan initiative ...`` subcommands."""
    import shutil

    from arnold_pipelines.megaplan.briefs import (
        default_initiative_description,
        scaffold_epic,
        write_initiative_cloud_yaml,
    )
    from arnold_pipelines.megaplan.layout import (
        ALLOWED_INITIATIVE_SUBDIRS,
        initiative_metadata,
        initiative_root,
        initiatives_dir,
        search_initiatives,
        slugify_initiative,
    )

    action = args.initiative_action
    if action == "new":
        slug = slugify_initiative(args.slug)
        if not slug:
            raise CliError("invalid_args", "initiative slug must not be empty")
        initiative = initiative_root(root, slug)
        if initiative.exists() and any(initiative.iterdir()) and not args.force:
            raise CliError(
                "initiative_exists",
                f"Initiative already exists: {initiative}. Pass --force to add missing scaffold files.",
            )
        for name in ALLOWED_INITIATIVE_SUBDIRS:
            (initiative / name).mkdir(parents=True, exist_ok=True)
        copied_docs: list[Path] = []
        for raw_doc in getattr(args, "doc", []) or []:
            kind, sep, source_raw = str(raw_doc).partition("=")
            kind = kind.strip()
            source_raw = source_raw.strip()
            if not sep or not kind or not source_raw:
                raise CliError("invalid_args", "--doc must be formatted as KIND=PATH")
            if kind not in ALLOWED_INITIATIVE_SUBDIRS or kind == "briefs":
                allowed = ", ".join(sorted(name for name in ALLOWED_INITIATIVE_SUBDIRS if name != "briefs"))
                raise CliError("invalid_args", f"--doc kind must be one of: {allowed}")
            source = Path(source_raw).expanduser()
            if not source.is_file():
                raise CliError("invalid_args", f"--doc source does not exist or is not a file: {source}")
            destination = initiative / kind / source.name
            if destination.exists() and not args.force:
                raise CliError(
                    "initiative_exists",
                    f"Initiative document already exists: {destination}. Pass --force to overwrite.",
                )
            shutil.copyfile(source, destination)
            copied_docs.append(destination)
        description = args.description
        if args.description_file:
            source = Path(args.description_file).expanduser()
            try:
                description = source.read_text(encoding="utf-8")
            except OSError as exc:
                raise CliError("invalid_args", f"Unable to read description source {source}: {exc}") from exc
        description = (description or default_initiative_description(slug)).strip()
        readme = initiative / "README.md"
        if args.force or not readme.exists():
            title = (args.title or slug.replace("-", " ").title()).strip()
            readme.write_text(f"# {title}\n\n{description}\n", encoding="utf-8")
        north_star = args.north_star
        if args.north_star_file:
            source = Path(args.north_star_file).expanduser()
            try:
                north_star = source.read_text(encoding="utf-8")
            except OSError as exc:
                raise CliError("invalid_args", f"Unable to read north star source {source}: {exc}") from exc
        if north_star is not None:
            north_star_path = initiative / "NORTHSTAR.md"
            if args.force or not north_star_path.exists():
                north_star_path.write_text(north_star.rstrip() + "\n", encoding="utf-8")
        chain_path: Path | None = None
        milestone_paths: list[Path] = []
        milestones = list(getattr(args, "milestone", []) or [])
        if args.chain or milestones:
            if not milestones:
                milestones = ["m1=TODO_MILESTONE_TITLE"]
            try:
                chain_path, milestone_paths = scaffold_epic(
                    root,
                    slug,
                    milestones,
                    base_branch=args.base_branch,
                    merge_policy=args.merge_policy,
                    branch_prefix=args.branch_prefix,
                    profile=args.profile,
                    vendor=args.vendor,
                    robustness=args.robustness,
                    depth=args.depth,
                    with_prep=not bool(args.no_with_prep),
                    force=bool(args.force),
                )
            except FileExistsError as exc:
                existing = exc.args[0] if exc.args else exc.filename
                raise CliError(
                    "initiative_exists",
                    f"Initiative artifact already exists: {existing}. Pass --force to overwrite.",
                ) from exc
            except ValueError as exc:
                raise CliError("invalid_args", str(exc)) from exc
            milestone_paths = [path for path in milestone_paths if path.parent.name == "briefs"]
        cloud_path: Path | None = None
        if args.cloud:
            try:
                cloud_path = write_initiative_cloud_yaml(
                    root,
                    slug,
                    base_branch=args.base_branch,
                    force=bool(args.force),
                    repo_url=args.repo_url,
                    chain_session=args.chain_session,
                )
            except FileExistsError as exc:
                existing = exc.args[0] if exc.args else exc.filename
                raise CliError(
                    "initiative_exists",
                    f"Initiative cloud config already exists: {existing}. Pass --force to overwrite.",
                ) from exc
        return {
            "success": True,
            "step": "initiative",
            "action": "new",
            "initiative": initiative_metadata(root, slug),
            "chain": str(chain_path) if chain_path else None,
            "cloud_yaml": str(cloud_path) if cloud_path else None,
            "milestones": [str(path) for path in milestone_paths],
            "docs": [str(path) for path in copied_docs],
            "next": {
                "edit": str(initiative),
                "preflight": (
                    f"python -m arnold_pipelines.megaplan cloud preflight {chain_path} "
                    f"--cloud-yaml {cloud_path}"
                    if chain_path and cloud_path
                    else None
                ),
                "launch": (
                    f"python -m arnold_pipelines.megaplan cloud chain {chain_path} "
                    f"--cloud-yaml {cloud_path}"
                    if chain_path and cloud_path
                    else None
                ),
            },
        }
    if action == "list":
        base = initiatives_dir(root)
        rows = [
            initiative_metadata(root, path.name)
            for path in sorted(base.iterdir())
            if path.is_dir()
        ]
        if args.limit is not None:
            rows = rows[: args.limit]
        return {
            "success": True,
            "step": "initiative",
            "action": "list",
            "initiatives": rows,
        }
    if action == "search":
        keywords = [keyword for keyword in (args.keywords or []) if keyword.strip()]
        if not keywords:
            raise CliError("invalid_args", "initiative search requires at least one keyword")
        rows = search_initiatives(
            root,
            keywords,
            keywords_all=args.keywords_all,
            limit=args.limit or 25,
        )
        return {
            "success": True,
            "step": "initiative",
            "action": "search",
            "keywords": keywords,
            "initiatives": rows,
        }
    raise CliError("invalid_args", f"Unknown initiative action: {action}")


def handle_epic(root: Path, args: argparse.Namespace) -> StepResponse:
    action = args.epic_action
    if action == "capsule":
        return _handle_epic_capsule(root, args)
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
        from arnold_pipelines.megaplan.store.export import collect_epic_export, write_epic_export_tar

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
    from arnold_pipelines.megaplan.store.legacy_migration import migrate_local_plans

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


def handle_migrate_layout(root: Path, args: argparse.Namespace) -> StepResponse:
    from arnold_pipelines.megaplan.layout import migrate_legacy_briefs_layout

    result = migrate_legacy_briefs_layout(root, apply=bool(args.apply))
    return {
        "success": True,
        "step": "migrate-layout",
        "action": "apply" if args.apply else "dry-run",
        **result,
    }


def handle_resume(root: Path, args: argparse.Namespace) -> StepResponse:
    from arnold_pipelines.megaplan._core.io import find_plan_dir
    from arnold_pipelines.megaplan.runtime.resume import extract_typed_resume_metadata

    plan_dir = find_plan_dir(root, args.plan)
    typed_meta = (
        extract_typed_resume_metadata(plan_dir) if plan_dir is not None else None
    )
    typed_human_gate = (
        typed_meta is not None
        and isinstance(typed_meta.pipeline, str)
        and bool(typed_meta.pipeline)
        and isinstance(typed_meta.phase, str)
        and bool(typed_meta.phase)
        and isinstance(typed_meta.choices, list)
        and bool(typed_meta.choices)
    )
    if plan_dir is not None and (
        typed_human_gate or (plan_dir / "awaiting_user.json").exists()
    ):
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
    previous_provider = os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER")
    self_hosted = False
    if not previous_provider:
        try:
            self_hosted = root.resolve() == megaplan_engine_root()
        except Exception:
            self_hosted = False
        if self_hosted:
            os.environ["MEGAPLAN_ENGINE_ISOLATION_PROVIDER"] = "self_hosted_editable"
    try:
        return resume_plan(root, args.plan, store=store)
    finally:
        try:
            close = getattr(store, "close", None)
            if callable(close):
                close()
        finally:
            if self_hosted:
                if previous_provider is None:
                    os.environ.pop("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", None)
                else:
                    os.environ["MEGAPLAN_ENGINE_ISOLATION_PROVIDER"] = previous_provider


def _resume_human_gate(root: Path, plan_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Resume a pipeline paused at a human_gate stage.

    Re-reads ``awaiting_user.json``, validates the ``--choice`` argument,
    persists the choice back into ``awaiting_user.json`` as
    ``_resume_choice`` so :class:`HumanDecisionStep` picks it up on re-entry,
    then re-enters the pipeline at the paused stage.
    """
    awaiting_path = plan_dir / "awaiting_user.json"
    from arnold_pipelines.megaplan.runtime.resume import extract_typed_resume_metadata

    typed_meta = extract_typed_resume_metadata(plan_dir)

    def _read_awaiting_user_checkpoint(*, strict: bool) -> dict[str, Any]:
        try:
            raw = json.loads(awaiting_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            if strict:
                raise CliError(
                    "bad_awaiting_user", f"Cannot read awaiting_user.json: {exc}"
                ) from exc
            return {}
        if not isinstance(raw, dict):
            if strict:
                raise CliError(
                    "bad_awaiting_user", "awaiting_user.json must contain a JSON object"
                )
            return {}
        return dict(raw)

    def _typed_checkpoint_data() -> dict[str, Any] | None:
        if typed_meta is None:
            return None
        if (
            not isinstance(typed_meta.pipeline, str)
            or not typed_meta.pipeline
            or not isinstance(typed_meta.phase, str)
            or not typed_meta.phase
            or not isinstance(typed_meta.choices, list)
            or not typed_meta.choices
        ):
            return None
        suspension = getattr(typed_meta.contract, "suspension", None)
        if suspension is None:
            return None
        payload = getattr(typed_meta.contract, "payload", None)
        data: dict[str, Any] = {}
        if isinstance(payload, dict):
            awaiting = payload.get("awaiting_user")
            if isinstance(awaiting, dict):
                data.update(awaiting)
        data.update(
            {
                "pipeline": typed_meta.pipeline,
                "stage": typed_meta.phase,
                "choices": [str(choice) for choice in typed_meta.choices],
                "message": str(
                    getattr(suspension, "prompt", None)
                    or f"Pipeline '{typed_meta.pipeline}' paused at stage '{typed_meta.phase}'."
                ),
            }
        )
        prompt = getattr(suspension, "prompt", None)
        if isinstance(prompt, str) and prompt:
            data["prompt"] = prompt
        if typed_meta.resume_input_schema:
            data["resume_input_schema"] = dict(typed_meta.resume_input_schema)
        display_refs = getattr(suspension, "display_refs", ())
        if isinstance(display_refs, (list, tuple)) and display_refs:
            serialized_refs: list[dict[str, Any]] = []
            for ref in display_refs:
                to_json = getattr(ref, "to_json", None)
                if callable(to_json):
                    serialized_refs.append(to_json())
            if serialized_refs:
                data["display_refs"] = serialized_refs
        return data

    typed_data = _typed_checkpoint_data()
    if typed_data is not None:
        data = _read_awaiting_user_checkpoint(strict=False)
        data.update(typed_data)
    else:
        data = _read_awaiting_user_checkpoint(strict=True)

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

    from arnold_pipelines.megaplan.runtime.bridge import run_pipeline_dispatch
    from arnold_pipelines.megaplan.runtime.resume import with_entry
    from arnold_pipelines.megaplan.registry import get_pipeline
    from arnold_pipelines.megaplan.step_types import StepContext

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

    # Clear pause state before execution so repeated resumes do not reuse
    # stale typed or legacy suspension metadata.
    state.pop("_pipeline_paused", None)
    state.pop("_pipeline_paused_stage", None)
    state.pop("contract_result", None)
    save_state(plan_dir, state)

    ctx = StepContext(
        plan_dir=plan_dir,
        state=state,
        profile={},
        mode=state.get("mode", "code"),
        inputs={},
    )
    result = run_pipeline_dispatch(
        pipeline,
        ctx,
        artifact_root=plan_dir,
        pipeline_key=str(pipeline_name),
    )

    # Clean up awaiting_user.json after successful resume.
    if awaiting_path.exists():
        awaiting_path.unlink()

    return result


def _handle_trace(root: Path, args: argparse.Namespace) -> int:
    return handle_trace(root, args)


def _handle_doctor(root: Path, args: argparse.Namespace) -> int:
    return handle_doctor(root, args)


def _handle_introspect(root: Path, args: argparse.Namespace) -> int:
    from arnold_pipelines.megaplan._core import find_plan_dir
    from arnold_pipelines.megaplan.observability.introspect import build_introspect_payload
    import json as _json

    plan_dir = find_plan_dir(Path.cwd(), args.plan)
    if plan_dir is None:
        print(f"introspect: plan {args.plan!r} not found", file=sys.stderr)
        return 1

    print(_json.dumps(build_introspect_payload(plan_dir), indent=2))
    return 0


def _handle_cost(root: Path, args: argparse.Namespace) -> int:
    from arnold_pipelines.megaplan.observability.cost import handle_cost

    return handle_cost(root, args)


def _handle_record_tag(root: Path, args: argparse.Namespace) -> int:
    from arnold_pipelines.megaplan._core import find_plan_dir
    from arnold_pipelines.megaplan.observability.events import EventKind, emit

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

    def _emit_validator_defects(diag: object) -> None:
        defects = list(getattr(diag, "defects", ()) or ())
        issues = list(getattr(diag, "issues", ()) or ())
        if issues and len(issues) == len(defects):
            for issue in issues:
                print(f"  - [{issue.code}] {issue.message}", file=sys.stderr)
            return
        for defect in defects:
            print(f"  - {defect}", file=sys.stderr)

    action = getattr(args, "pipelines_action", None)
    if action == "check":
        name = getattr(args, "pipeline_name", None)
        if not name:
            print("(no pipeline name provided)")
            return 0
        from arnold_pipelines.megaplan.runtime.judge_manifest_discovery import (
            find_judge_manifest,
            validate_judge_manifest,
        )

        try:
            judge_match = find_judge_manifest(name)
        except Exception as exc:
            print(
                f"pipelines check: failed to load judge manifest for {name!r}: {exc}",
                file=sys.stderr,
            )
            return 1
        if judge_match is not None:
            diag = validate_judge_manifest(
                judge_match.manifest,
                path=judge_match.path,
            )
            if diag.ok:
                print(name)
                return 0
            print(
                f"pipelines check: judge manifest {name!r} has "
                f"{len(diag.defects)} defect(s):",
                file=sys.stderr,
            )
            _emit_validator_defects(diag)
            return 1

        from arnold_pipelines.megaplan.registry import (
            get_pipeline,
            pipeline_metadata,
        )
        from arnold_pipelines.megaplan.runtime.discovery import canonical_pipeline_name
        from arnold_pipelines.megaplan.runtime.discovery import scan_python_pipelines
        from arnold.workflow.discovery.manifest import Manifest, read_manifest
        from arnold.workflow.validator import ValidationOptions, validate

        canonical_name = canonical_pipeline_name(name)
        dispositions = scan_python_pipelines()
        for disposition in dispositions:
            if disposition.cli_name == canonical_name and disposition.status == "rejected":
                print(
                    f"pipelines check: {canonical_name!r} rejected: {disposition.reason}",
                    file=sys.stderr,
                )
                return 1
        try:
            pipeline = get_pipeline(canonical_name)
        except Exception as exc:  # discovery / build failure
            print(f"pipelines check: failed to load {name!r}: {exc}", file=sys.stderr)
            return 1
        if pipeline is None:
            print(f"pipelines check: {canonical_name!r} is not executable", file=sys.stderr)
            return 1

        context = None
        metadata = pipeline_metadata(canonical_name)
        manifest_path = metadata.get("manifest_source_path") or metadata.get("source_path")
        if isinstance(manifest_path, str) and manifest_path:
            manifest = read_manifest(Path(manifest_path))
            if isinstance(manifest, Manifest):
                context = manifest.validation_context(
                    package=canonical_name,
                    compatibility_classification=str(
                        metadata.get("compatibility_classification") or "native"
                    ),
                )
        diag = validate(
            pipeline,
            ValidationOptions(
                decision_vocabulary_fallback=frozenset(
                    {"proceed", "iterate", "tiebreaker", "escalate"}
                ),
            ),
            context=context,
        )
        if diag.ok:
            print(name)
            return 0
        print(f"pipelines check: {name!r} has {len(diag.defects)} defect(s):", file=sys.stderr)
        _emit_validator_defects(diag)
        return 1
    if action == "doctor":
        from arnold_pipelines.megaplan.runtime.discovery import scan_python_pipelines

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
        from arnold_pipelines.megaplan.runtime.discovery import _SCAN_ROOTS, _cli_name

        name = getattr(args, "pipeline_name", None)
        if not name:
            print("pipelines new: missing pipeline name", file=sys.stderr)
            return 1
        driver = getattr(args, "driver", None)
        if driver == "graph":
            print(
                "pipelines new: unsupported legacy driver 'graph'; "
                "native projection is emitted by default",
                file=sys.stderr,
            )
            return 1
        if driver not in (None, "native"):
            print(
                f"pipelines new: unsupported driver {driver!r}; only 'native' is supported",
                file=sys.stderr,
            )
            return 1

        # Derive the module stem (hyphens → underscores) and directory name.
        module_stem = name.replace("-", "_")
        cli_name = _cli_name(module_stem)  # normalise underscores→hyphens

        # Locate the in-tree pipelines directory (first scan root).
        pipelines_dir = None
        for dir_path, pkg_prefix in _SCAN_ROOTS:
            if pkg_prefix == "arnold_pipelines.megaplan.pipelines":
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
        module_content = f'''"""Native-first compositional shell for the ``{cli_name}`` pipeline."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from arnold.pipeline.native import (
    compile_pipeline,
    decision,
    parallel_map,
    phase,
    pipeline,
    project_graph,
    start_from_trace,
    workflow,
)
from arnold.pipeline.types import Pipeline, StepResult


_PIPELINE_DIR: Path = Path(__file__).parent / "{cli_name}"

name: str = "{cli_name}"
description: str = "TODO: add a description"
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "project+validate")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("skeleton",)
authoring_style: str = "compositional"

inputs: dict[str, Any] = {{
    "type": "object",
    "required": ["brief", "checks"],
    "properties": {{
        "brief": {{"type": "string"}},
        "checks": {{
            "type": "array",
            "items": {{
                "type": "object",
                "required": ["item_id"],
                "properties": {{"item_id": {{"type": "string"}}}},
            }},
        }},
    }},
}}

outputs: dict[str, Any] = {{
    "type": "object",
    "required": ["final_artifact"],
}}


def _required_schema(*names: str) -> dict[str, Any]:
    return {{"type": "object", "required": list(names)}}


@phase(name="draft_outline", id="{module_stem}.draft_outline", outputs=_required_schema("outline"))
def _native_draft(ctx: dict[str, Any]) -> StepResult:
    del ctx
    return StepResult(outputs={{"outline": "TODO: outline.md"}}, next="halt")


@phase(
    name="review_findings",
    id="{module_stem}.review_findings",
    inputs=_required_schema("outline"),
    outputs=_required_schema("findings"),
)
def _native_review_findings(ctx: dict[str, Any]) -> StepResult:
    outline = ctx["state"].get("working_outline") or ctx["state"].get("outline") or "TODO"
    return StepResult(outputs={{"findings": f"Findings for {{outline}}"}}, next="halt")


@phase(
    name="review_verdict",
    id="{module_stem}.review_verdict",
    inputs=_required_schema("findings"),
    outputs=_required_schema("verdict"),
)
def _native_review_verdict(ctx: dict[str, Any]) -> StepResult:
    del ctx
    return StepResult(outputs={{"verdict": "approved"}}, next="halt")


@phase(
    name="revise_outline",
    id="{module_stem}.revise_outline",
    inputs=_required_schema("working_outline", "first_findings"),
    outputs=_required_schema("outline"),
)
def _native_revise(ctx: dict[str, Any]) -> StepResult:
    outline = ctx["state"].get("working_outline") or "TODO: outline.md"
    findings = ctx["state"].get("first_findings") or "TODO findings"
    return StepResult(outputs={{"outline": f"{{outline}} revised after {{findings}}"}}, next="halt")


@phase(
    name="parallel_item_review",
    id="{module_stem}.parallel_item_review",
    inputs=_required_schema("item_id"),
    outputs=_required_schema("item_review"),
)
def _native_parallel_item_review(ctx: dict[str, Any]) -> StepResult:
    item_id = str(ctx["state"].get("item_id", "item"))
    return StepResult(outputs={{"item_review": f"reviewed:{{item_id}}"}}, next="halt")


@phase(
    name="publish_artifact",
    id="{module_stem}.publish_artifact",
    inputs=_required_schema("working_outline"),
    outputs=_required_schema("final_artifact"),
)
def _native_publish(ctx: dict[str, Any]) -> StepResult:
    outline = ctx["state"].get("working_outline") or "TODO: outline.md"
    return StepResult(outputs={{"final_artifact": f"published:{{outline}}"}}, next="halt")


@workflow(
    name="review_pass",
    id="{module_stem}.review_pass",
    inputs=_required_schema("outline"),
    outputs=_required_schema("findings", "verdict"),
)
def _review_pass(ctx: dict[str, Any]) -> Any:
    state = yield _native_review_findings(ctx, id="review-findings", outputs={{"findings": "findings"}})
    state = yield _native_review_verdict(ctx, id="review-verdict", outputs={{"verdict": "verdict"}})
    return state


@workflow(
    name="parallel_review_item",
    id="{module_stem}.parallel_review_item",
    inputs=_required_schema("item_id"),
    outputs=_required_schema("item_review"),
)
def _parallel_review_item(ctx: dict[str, Any]) -> Any:
    state = yield _native_parallel_item_review(
        ctx,
        id="parallel-item-review",
        outputs={{"item_review": "item_review"}},
    )
    return state


def _collect_parallel_reviews(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {{"parallel_reviews": results}}


@decision(name="publish_gate", vocabulary={{"publish", "revise"}})
def _native_publish_gate(ctx: dict[str, Any]) -> str:
    del ctx
    return "publish"


@pipeline(
    name="{cli_name}",
    id="{module_stem}.parent",
    description="TODO: compositional native workflow with child call sites and parallel fan-out",
    inputs=inputs,
    outputs=outputs,
)
def {module_stem}_native(ctx: dict[str, Any]) -> Any:
    state = yield _native_draft(ctx, id="draft-outline", outputs={{"outline": "working_outline"}})
    state = yield _review_pass(
        ctx,
        id="first-review",
        outputs={{"findings": "first_findings", "verdict": "first_verdict"}},
    )
    if _native_publish_gate(ctx) == "revise":
        state = yield _native_revise(ctx, id="revise-outline", outputs={{"outline": "working_outline"}})
        state = yield _review_pass(
            ctx,
            id="second-review",
            outputs={{"findings": "second_findings", "verdict": "second_verdict"}},
        )
    state = yield parallel_map(
        items="checks",
        step=_parallel_review_item,
        reducer=_collect_parallel_reviews,
        path_template="checks/{{item_id}}",
        name="parallel_review_items",
        id="parallel-review-items",
    )
    state = yield _native_publish(ctx, id="publish-artifact", outputs={{"final_artifact": "final_artifact"}})
    return state


def _native_program() -> Any:
    return compile_pipeline({module_stem}_native)


def resume_from_trace_example(
    trace_dir: str | Path,
    artifact_root: str | Path,
    *,
    target_path: str = "root/second-review/review_verdict",
) -> Any:
    return start_from_trace(_native_program(), trace_dir, target_path, artifact_root)


def build_pipeline() -> Pipeline:
    """Return the canonical native-backed ``{cli_name}`` :class:`Pipeline`."""

    native_program = _native_program()
    projected = project_graph(native_program, key_mode="phase")
    return replace(
        projected,
        resource_bundles=(),
        native_program=native_program,
    )


__all__ = [
    "arnold_api_version",
    "authoring_style",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "inputs",
    "name",
    "outputs",
    "recommended_profiles",
    "resume_from_trace_example",
    "supported_modes",
]
'''
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


def handle_anchors(root: Path, args: argparse.Namespace) -> StepResponse:
    from arnold_pipelines.megaplan.handlers.anchors import handle_anchors as _handle

    return _handle(root, args)


def handle_authority_inventory(root: Path, args: argparse.Namespace) -> StepResponse:
    """Return the canonical, read-only authority evidence inventory."""

    from arnold_pipelines.megaplan.authority.inventory import collect_authority_inventory

    plan_dir = resolve_plan_dir(root, args.plan)
    inventory = collect_authority_inventory(
        plan_dir,
        session=getattr(args, "session", None),
        marker_dir=getattr(args, "marker_dir", None),
    )
    return {
        "success": True,
        "step": "authority-inventory",
        "plan": plan_dir.name,
        "plan_dir": str(plan_dir),
        "inventory": inventory.to_dict(),
        "fingerprint": inventory.fingerprint,
    }


COMMAND_HANDLERS: dict[str, Callable[..., StepResponse]] = {
    "anchors": handle_anchors,
    "authority-inventory": handle_authority_inventory,
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
    "brief": handle_brief,
    "initiative": handle_initiative,
    "contract": handle_contract,
    "ticket": handle_ticket,
    "epic": handle_epic,
    "migrate-local-plans": handle_migrate_local_plans,
    "migrate-layout": handle_migrate_layout,
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

    from arnold_pipelines.megaplan.bakeoff.worktree import (
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
    from arnold_pipelines.megaplan.workers import set_work_dir_override

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


def _reset_chain_worktree_target(
    invoking_repo: Path,
    target: Path,
    branch: str,
    *,
    worktree_registered: Callable[[Path, Path], bool],
    protected_paths: list[Path] | None = None,
) -> None:
    """Clear the named chain worktree target for an explicit --fresh start."""
    target = target.resolve()
    protected = [invoking_repo.resolve(), Path.cwd().resolve()]
    protected.extend(path.resolve() for path in protected_paths or [])
    if target in protected:
        raise CliError(
            "worktree_reset_refused",
            f"refusing --fresh worktree reset: target path is protected: {target}",
        )
    registered = worktree_registered(invoking_repo, target)
    if not (target.exists() or registered):
        return
    if not registered:
        raise CliError(
            "worktree_reset_refused",
            (
                f"refusing --fresh worktree reset: target path exists but is not "
                f"a git worktree registered to {invoking_repo}: {target}"
            ),
        )
    if registered:
        proc = subprocess.run(
            ["git", "worktree", "remove", "--force", str(target)],
            cwd=str(invoking_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise CliError(
                "worktree_reset_failed",
                (
                    f"refusing --fresh worktree reset: could not remove registered "
                    f"worktree at {target}: {(proc.stderr or proc.stdout).strip()}"
                ),
            )
    if target.exists():
        raise CliError(
            "worktree_reset_failed",
            (
                f"refusing --fresh worktree reset: git worktree remove left "
                f"{target} on disk; inspect it manually before retrying"
            ),
        )
    proc = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(invoking_repo),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        delete = subprocess.run(
            ["git", "branch", "-D", branch],
            cwd=str(invoking_repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if delete.returncode != 0:
            raise CliError(
                "worktree_reset_failed",
                (
                    f"refusing --fresh worktree reset: could not delete local "
                    f"branch {branch!r}: {(delete.stderr or delete.stdout).strip()}"
                ),
            )


def _chain_worktree_base_ref(args: argparse.Namespace) -> str:
    """Resolve the git ref to fork the chain's shared worktree from.

    Explicit ``--worktree-from`` always wins. Otherwise default to the chain
    spec's ``base_branch`` — NOT the invoking ``HEAD``. The chain runs every
    milestone off ``base_branch`` (``git checkout -B <milestone> <base_branch>``),
    so forking the worktree from a stale invoking HEAD makes any carried-untracked
    file that is *tracked* on ``base_branch`` collide on that checkout
    ("untracked working tree files would be overwritten"; ticket 01KTQ35AB8).
    Forking from ``base_branch`` lands the carried dirt on top of the base the
    chain actually uses, so the checkout is a no-op base and never collides.
    Falls back to ``HEAD`` if the spec is absent or unreadable.
    """
    explicit = getattr(args, "worktree_from", None)
    if explicit:
        return explicit
    spec_path = getattr(args, "spec", None)
    if spec_path:
        try:
            from arnold_pipelines.megaplan.chain import load_spec

            return load_spec(Path(spec_path)).base_branch
        except CliError:
            pass
    return "HEAD"


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

    if action not in (None, "start", "plan", "execute"):
        raise CliError(
            "invalid_args",
            "--in-worktree is only valid for `megaplan chain start`, `plan`, or `execute`",
        )
    if getattr(args, "project_dir", None):
        raise CliError(
            "invalid_args",
            "pass either --project-dir or --in-worktree, not both",
        )

    from arnold_pipelines.megaplan.bakeoff.worktree import (
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
    if bool(getattr(args, "fresh", False)):
        _reset_chain_worktree_target(
            invoking_repo,
            target,
            name,
            worktree_registered=worktree_registered,
            protected_paths=[
                Path(getattr(args, "spec", "")).expanduser().resolve().parent
            ],
        )
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

    base_ref = _chain_worktree_base_ref(args)
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
    from arnold_pipelines.megaplan.workers import set_work_dir_override

    set_work_dir_override(target)

    # Point engine-isolation at the invoking (engine) checkout.  The target
    # worktree shadows the editable install when Python resolves ``arnold`` from
    # cwd, so ``megaplan_engine_root()`` needs an explicit anchor.
    os.environ["MEGAPLAN_ENGINE_ROOT"] = str(invoking_repo)

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
    from arnold_pipelines.megaplan.registry import (
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
    from arnold_pipelines.megaplan.cli.run import render_pipeline_description
    from arnold_pipelines.megaplan.planning.operations import canonical_metadata
    from arnold_pipelines.megaplan.registry import (
        describe_pipeline,
        pipeline_metadata,
        registered_pipelines,
        read_pipeline_skill_md,
    )
    from arnold_pipelines.megaplan.runtime.discovery import canonical_pipeline_name

    name = args.pipeline_name
    canonical_name = canonical_pipeline_name(name)
    if canonical_name not in set(registered_pipelines()):
        return {
            "success": False,
            "step": "describe",
            "error": f"Unknown pipeline: {name}",
        }

    meta = pipeline_metadata(canonical_name)
    if canonical_name == "megaplan":
        meta.update(canonical_metadata())
    desc = describe_pipeline(canonical_name) or str(meta.get("description") or "")
    rendered_meta = dict(meta)
    if desc and not rendered_meta.get("description"):
        rendered_meta["description"] = desc

    # For CLI rendering, print directly (descriptions are long-form text)
    print(
        render_pipeline_description(
            canonical_name,
            rendered_meta,
            skill_md=read_pipeline_skill_md(canonical_name),
        )
    )
    return {
        "success": True,
        "step": "describe",
        "pipeline": canonical_name,
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


def _consume_execute_compat_flags(
    args: argparse.Namespace,
    remaining: list[str],
) -> list[str]:
    """Back-compat for wrapper-supplied execute flags left in ``remaining``.

    Some cloud/watchdog launches always forward the execute envelope flags. If a
    stale or partial parser path leaves those tokens unconsumed, treat them as
    recognized execute options instead of hard-failing at argparse level.
    """

    if getattr(args, "command", None) != "execute" or not remaining:
        return remaining

    consumed: list[str] = []
    recognized = {
        "--confirm-destructive": "confirm_destructive",
        "--user-approved": "user_approved",
        "--retry-blocked-tasks": "retry_blocked_tasks",
    }
    index = 0
    while index < len(remaining):
        token = remaining[index]
        if token == "--phase-model":
            if index + 1 >= len(remaining):
                consumed.append(token)
                index += 1
                continue
            phase_model = list(getattr(args, "phase_model", None) or [])
            phase_model.append(remaining[index + 1])
            setattr(args, "phase_model", phase_model)
            index += 2
            continue
        attr = recognized.get(token)
        if attr is None:
            consumed.append(token)
            index += 1
            continue
        setattr(args, attr, True)
        index += 1
    return consumed


def _normalize_execute_compat_argv(argv: list[str]) -> list[str]:
    """Normalize wrapper-supplied execute flags into execute's subcommand scope.

    Some automation paths emit the execute envelope flags before the
    ``execute`` token instead of after it. That is semantically equivalent, but
    argparse only binds them reliably when they appear inside the execute
    subparser's argv segment. Move recognized flags to immediately after the
    first ``execute`` token before any parsing happens.

    A second stale-wrapper shape drops the ``execute`` token entirely and
    forwards execute options directly after the root options. In that case,
    synthesize the missing subcommand so compatibility routing still lands in
    the execute parser.
    """
    recognized = {
        "--confirm-destructive",
        "--user-approved",
        "--retry-blocked-tasks",
    }
    if "execute" not in argv:
        root_option_arity = {
            "--actor": 1,
            "--backend": 1,
        }
        prefix: list[str] = []
        index = 0
        while index < len(argv):
            token = argv[index]
            arity = root_option_arity.get(token)
            if arity is None:
                break
            end = index + 1 + arity
            if end > len(argv):
                return argv
            prefix.extend(argv[index:end])
            index = end
        execute_tail = argv[index:]
        if (
            execute_tail
            and execute_tail[0].startswith("-")
            and any(token in recognized for token in execute_tail)
        ):
            return [*prefix, "execute", *execute_tail]
        return argv

    execute_index = argv.index("execute")
    before_execute = argv[:execute_index]
    moved_flags = [token for token in before_execute if token in recognized]
    if not moved_flags:
        return argv
    kept_prefix = [token for token in before_execute if token not in recognized]
    return kept_prefix + ["execute", *moved_flags, *argv[execute_index + 1 :]]


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    argv = _normalize_execute_compat_argv(list(argv))
    maybe_auto_sync_repo_editor_support(Path.cwd())
    if argv and argv[0] == "cloud":
        from arnold_pipelines.megaplan.cloud.cli import _register_cloud_subcommands, run_cloud_cli

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
        from arnold_pipelines.megaplan.resident.cli import (
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
        from arnold_pipelines.megaplan.bakeoff.cli import _register_bakeoff_subcommands, run_bakeoff_cli

        bakeoff_parser = argparse.ArgumentParser(prog="megaplan bakeoff")
        _register_bakeoff_subcommands(bakeoff_parser)
        bakeoff_args = bakeoff_parser.parse_args(argv[1:])
        root = _find_megaplan_root(Path.cwd())
        ensure_runtime_layout(root)
        try:
            return run_bakeoff_cli(root, bakeoff_args)
        except CliError as error:
            return error_response(error, root=root)
    if argv and argv[0] == "incident":
        from arnold_pipelines.megaplan.incident.cli import (
            register_incident_subcommands,
            run_incident_cli,
        )

        incident_parser = argparse.ArgumentParser(prog="megaplan incident")
        register_incident_subcommands(incident_parser)
        incident_args = incident_parser.parse_args(argv[1:])
        root = _find_megaplan_root(Path.cwd())
        ensure_runtime_layout(root)
        try:
            return run_incident_cli(root, incident_args)
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
    from arnold_pipelines.megaplan.workers import set_work_dir_override

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
        from arnold_pipelines.megaplan.auto import run_auto

        try:
            return run_auto(root, args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "run":
        from arnold_pipelines.megaplan.cli.run import cli_run

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
        from arnold_pipelines.megaplan.chain import run_chain_cli

        try:
            return run_chain_cli(root, args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "epic-chain":
        from arnold_pipelines.megaplan.chain.epic_chain import run_epic_chain_cli

        try:
            return run_epic_chain_cli(root, args)
        except CliError as error:
            return error_response(error, root=root)

    if args.command == "tiebreaker":
        from arnold_pipelines.megaplan.prompts.tiebreaker_orchestrator import run_tiebreaker_cli

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
        from arnold_pipelines.megaplan.orchestration.progress import ProgressEmitter

        args.progress_emitter = ProgressEmitter.from_env()
        if args.command == "override" and remaining:
            if not args.note:
                args.note = " ".join(remaining)
            remaining = []
        remaining = _consume_execute_compat_flags(args, remaining)
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
            from arnold_pipelines.megaplan.store import DBStore

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
