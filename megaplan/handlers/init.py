from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from megaplan.doc_assembly import extract_settled_decisions
from megaplan.forms import available_form_ids
from megaplan.profiles import apply_profile_expansion
from megaplan.types import ROBUSTNESS_LEVELS, CliError, PlanState, STATE_INITIALIZED, StepResponse
from megaplan._core import (
    append_history,
    ensure_runtime_layout,
    find_command,
    get_effective,
    make_history_entry,
    now_utc,
    is_prose_mode,
    plans_root,
    save_state,
    slugify,
    workflow_next,
)

from .shared import _append_to_meta, _attach_next_step_runtime, _validate_relative_path

def handle_init(root: Path, args: argparse.Namespace) -> StepResponse:
    ensure_runtime_layout(root)
    project_dir = Path(args.project_dir).expanduser().resolve()
    if not project_dir.exists() or not project_dir.is_dir():
        raise CliError("invalid_project_dir", f"Project directory does not exist: {project_dir}")
    apply_profile_expansion(args, project_dir)
    positional_idea = getattr(args, "idea", None)
    idea_file = getattr(args, "idea_file", None)
    if positional_idea and idea_file:
        raise CliError("invalid_args", "Pass either the positional idea or --idea-file, not both")
    if idea_file:
        idea_path = Path(idea_file).expanduser().resolve()
        try:
            idea_text = idea_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise CliError("invalid_args", f"Unable to read --idea-file {idea_path}: {exc}") from exc
        if not idea_text:
            raise CliError("invalid_args", "--idea-file must contain non-empty UTF-8 text")
    elif positional_idea:
        idea_text = positional_idea
    else:
        raise CliError("invalid_args", "Provide an idea argument or --idea-file <path>")
    explicit_mode = getattr(args, "mode", None)
    raw_output_path = getattr(args, "output", None)
    raw_primary_criterion = getattr(args, "primary_criterion", None)
    raw_form = getattr(args, "form", None)
    mode = explicit_mode or "code"
    if mode == "metaplan":
        mode = "doc"
    if raw_primary_criterion and mode not in {"joke", "creative"}:
        raise CliError("invalid_args", "--primary-criterion is only valid with --mode joke or --mode creative")
    if raw_form and mode != "creative":
        raise CliError("invalid_args", "--form is only valid with --mode creative")
    if mode == "creative":
        if not raw_form:
            raise CliError("invalid_args", "--form is required when --mode creative is selected")
        if raw_form not in available_form_ids():
            raise CliError("invalid_args", f"Unknown creative form: {raw_form}")
    elif mode == "joke":
        raw_form = "joke"

    if mode == "code" and raw_output_path:
        raise CliError(
            "invalid_args",
            "--output is only valid with --mode doc, --mode joke, or --mode creative. For code-mode runs, remove "
            "--output; for prose artifact runs, also pass --mode doc, --mode joke, or --mode creative.",
        )
    normalized_output_path: str | None = None
    if is_prose_mode({"config": {"mode": mode}}) and not raw_output_path:
        raise CliError("invalid_args", f"--output is required when --mode {mode} is selected")
    if raw_output_path:
        normalized_output_path = _validate_relative_path(project_dir, raw_output_path, "--output")
    normalized_primary_criterion: str | None = None
    if raw_primary_criterion is not None:
        normalized_primary_criterion = str(raw_primary_criterion).strip()
        if not normalized_primary_criterion:
            raise CliError("invalid_args", "--primary-criterion must be non-empty when provided")
    raw_from_doc = getattr(args, "from_doc", None)
    from_doc_rel: str | None = None
    imported_decisions: list[dict[str, Any]] = []
    parse_warnings: list[str] = []
    if raw_from_doc:
        from_doc_rel = _validate_relative_path(project_dir, raw_from_doc, "--from-doc")
        from_doc_abs = project_dir / from_doc_rel
        if not from_doc_abs.exists() or not from_doc_abs.is_file():
            raise CliError("invalid_args", f"--from-doc path does not exist: {from_doc_rel}")
        imported_decisions, parse_warnings = extract_settled_decisions(
            from_doc_abs.read_text(encoding="utf-8")
        )
    robustness = getattr(args, "robustness", None)
    if robustness is None:
        robustness = get_effective("execution", "robustness")
    if robustness not in ROBUSTNESS_LEVELS:
        robustness = "standard"
    auto_approve_value = getattr(args, "auto_approve", None)
    if auto_approve_value is None:
        auto_approve_value = get_effective("execution", "auto_approve")
    auto_approve = bool(auto_approve_value)
    strict_notes_arg = getattr(args, "strict_notes", None)
    strict_notes_explicit = strict_notes_arg is not None
    if strict_notes_arg is None:
        # Auto-on for design-doc / metaplan flows: in those modes a user note
        # mid-flight almost always means "stop and reconsider" rather than
        # "keep going." Code mode keeps the historical default (off).
        if mode == "doc":
            strict_notes_arg = True
        else:
            strict_notes_arg = get_effective("execution", "strict_notes")
    strict_notes = bool(strict_notes_arg)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    plan_name = args.name or f"{slugify(idea_text)}-{timestamp}"
    plan_dir = plans_root(root) / plan_name
    if plan_dir.exists():
        raise CliError("duplicate_plan", f"Plan directory already exists: {plan_name}")
    plan_dir.mkdir(parents=True, exist_ok=False)

    state: PlanState = {
        "name": plan_name,
        "idea": idea_text,
        "current_state": STATE_INITIALIZED,
        "iteration": 0,
        "created_at": now_utc(),
        "config": {
            "project_dir": str(project_dir),
            "auto_approve": auto_approve,
            "robustness": robustness,
            "mode": mode,
            "strict_notes": strict_notes,
            "agent": "hermes" if getattr(args, "hermes", None) is not None else "",
        },
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {
            "significant_counts": [],
            "weighted_scores": [],
            "plan_deltas": [],
            "recurring_critiques": [],
            "total_cost_usd": 0.0,
            "overrides": [],
            "notes": [],
        },
        "last_gate": {},
    }
    if getattr(args, "profile", None):
        state["config"]["profile"] = args.profile
    if normalized_output_path is not None:
        state["config"]["output_path"] = normalized_output_path
    if raw_form:
        state["config"]["form"] = str(raw_form)
    if normalized_primary_criterion is not None:
        state["config"]["primary_criterion"] = normalized_primary_criterion
    if from_doc_rel is not None:
        state["config"]["from_doc"] = from_doc_rel
        state["meta"]["imported_decisions"] = imported_decisions
    phase_models = list(getattr(args, "phase_model", None) or [])
    if phase_models:
        state["config"]["phase_model"] = phase_models
    if strict_notes and mode == "doc" and not strict_notes_explicit:
        # Driver-source: marks the auto-enable for transparency without
        # blocking force-proceed (driver notes don't count toward strict
        # invariant 1).
        _append_to_meta(
            state,
            "notes",
            {
                "timestamp": now_utc(),
                "note": "strict-notes auto-enabled for metaplan/doc mode",
                "source": "driver",
            },
        )
    for warning in parse_warnings:
        _append_to_meta(state, "notes", {"timestamp": now_utc(), "note": warning})
    append_history(
        state,
        make_history_entry(
            "init",
            duration_ms=0,
            cost_usd=0.0,
            result="success",
            environment={
                "claude": bool(find_command("claude")),
                "codex": bool(find_command("codex")),
            },
        ),
    )
    save_state(plan_dir, state)
    next_steps = workflow_next(state)
    response: StepResponse = {
        "success": True,
        "step": "init",
        "plan": plan_name,
        "state": STATE_INITIALIZED,
        "summary": f"Initialized plan '{plan_name}' for project {project_dir}",
        "artifacts": ["state.json"],
        "next_step": next_steps[0] if next_steps else None,
        "auto_approve": auto_approve,
        "robustness": robustness,
    }
    if parse_warnings:
        response["warnings"] = parse_warnings
    if bool(getattr(args, "auto_start", False)):
        from megaplan.auto import drive as auto_drive

        outcome = auto_drive(
            plan_name,
            cwd=root,
        )
        response["auto_outcome"] = {
            "status": outcome.status,
            "plan": outcome.plan,
            "final_state": outcome.final_state,
            "iterations": outcome.iterations,
            "reason": outcome.reason,
            "last_phase": outcome.last_phase,
            "events": outcome.events,
        }
    _attach_next_step_runtime(response)
    return response
