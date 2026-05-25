from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from megaplan.runtime.doc_assembly import extract_settled_decisions
from megaplan.forms import available_form_ids
from megaplan.profiles import apply_profile_expansion, load_profile_metadata
from megaplan.types import ROBUSTNESS_LEVELS, CliError, PlanState, STATE_INITIALIZED, StepResponse, normalize_robustness
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


# ── T10 (0.23): --mode deprecation routing ─────────────────────────────
#
# The four deprecated init-time modes redirect to first-class pipelines
# discoverable via ``megaplan run <pipeline>``. handle_init seeds
# ``state['config']['pipeline']`` so a follow-up ``megaplan run`` (the
# 0.23 user-facing entry point) routes correctly; the legacy
# ``--auto-start`` path continues to run the planning + mode-overlay
# chain in 0.23 (full integration ships in 0.24 per USER DECISION 2).
_DEPRECATED_INIT_MODES: frozenset[str] = frozenset(
    {"doc", "creative", "metaplan", "joke"}
)

# (explicit --mode) → pipeline name written into state['config']['pipeline'].
# metaplan→doc and joke→creative match the pinned config-write table
# from the plan Overview. Modes outside this map (only 'code' today)
# leave pipeline unset.
_PIPELINE_ROUTING: dict[str, str] = {
    "doc": "doc",
    "metaplan": "doc",
    "creative": "creative",
    "joke": "creative",
}


def _emit_mode_deprecation_warning(explicit_mode: str) -> None:
    """Emit the verbatim 0.23 deprecation warning to stderr.

    The text is pinned by T10 step (4); kept verbatim so downstream
    tooling can grep for ``[deprecation] megaplan init --mode`` and
    the release-notes/changelog tooling can cross-reference the string.
    """

    pipeline = _PIPELINE_ROUTING.get(explicit_mode, explicit_mode)
    form_suffix = " --form …" if pipeline == "creative" else ""
    msg = (
        f"[deprecation] megaplan init --mode {explicit_mode} is deprecated; "
        f"use \"megaplan run {pipeline}{form_suffix}\" instead. "
        f"NOTE: in 0.23, --auto-start after init --mode still runs the "
        f"LEGACY planning + mode-overlay path; the new {pipeline} pipeline "
        f"is only reached via \"megaplan run\". Full integration ships in "
        f"0.24. --mode will be removed in 0.24."
    )
    print(msg, file=sys.stderr)


def _build_state_config(
    args: argparse.Namespace,
    *,
    project_dir: Path,
    pipeline: str | None,
    mode: str,
    raw_form: str | None,
    normalized_output_path: str | None,
    normalized_primary_criterion: str | None,
    from_doc_rel: str | None,
) -> tuple[dict[str, Any], bool, str, bool, bool]:
    """Build ``state['config']`` for handle_init in one place.

    T10 step (6): single helper that takes the args namespace + an
    explicit pipeline name and assembles the config dict so the
    deprecated-mode redirects can NOT silently drop init.py's per-key
    normalisations. Specifically preserves:

    * ``auto_approve`` fallback to
      ``get_effective('execution', 'auto_approve')`` when --auto-approve
      is not passed (init.py:106-110 historical lines).
    * ``strict_notes`` auto-on for ``mode == 'doc'`` (init.py:113-119);
      ``--strict-notes`` left unset and mode != 'doc' falls back to
      ``get_effective('execution', 'strict_notes')``.
    * ``prep_direction`` strip + non-empty validation (init.py:171-176)
      — empty after strip raises ``CliError('invalid_args')``.

    Returns ``(config, auto_approve, robustness, strict_notes,
    strict_notes_explicit)`` so the caller (handle_init) can still
    surface the normalised values in its StepResponse and apply the
    one-off ``meta['notes']`` driver-source marker for the strict-notes
    auto-enable on doc mode.

    ``pipeline``, when not None, is written into ``config['pipeline']``
    — the seed the future ``megaplan run`` flow consults to dispatch
    the new first-class pipeline. ``--mode code`` passes
    ``pipeline=None`` and ``config`` carries no ``pipeline`` key (per
    T10 step (7)).
    """

    robustness = getattr(args, "robustness", None)
    if robustness is None:
        robustness = get_effective("execution", "robustness")
    robustness = normalize_robustness(robustness)

    auto_approve_value = getattr(args, "auto_approve", None)
    if auto_approve_value is None:
        auto_approve_value = get_effective("execution", "auto_approve")
    auto_approve = bool(auto_approve_value)

    adaptive_critique_value = getattr(args, "adaptive_critique", None)
    if adaptive_critique_value is None:
        adaptive_critique_value = get_effective("execution", "adaptive_critique")
    adaptive_critique = bool(adaptive_critique_value)

    strict_notes_arg = getattr(args, "strict_notes", None)
    strict_notes_explicit = strict_notes_arg is not None
    if strict_notes_arg is None:
        if mode == "doc":
            strict_notes_arg = True
        else:
            strict_notes_arg = get_effective("execution", "strict_notes")
    strict_notes = bool(strict_notes_arg)

    max_tasks_per_batch_arg = getattr(args, "max_tasks_per_batch", None)
    if max_tasks_per_batch_arg is not None:
        max_tasks_per_batch = int(max_tasks_per_batch_arg)
    else:
        max_tasks_per_batch = int(get_effective("execution", "max_tasks_per_batch"))
        profile_name = getattr(args, "profile", None)
        if profile_name:
            profile_meta = load_profile_metadata(project_dir=project_dir).get(profile_name, {})
            profile_ceiling = profile_meta.get("max_tasks_per_batch")
            if isinstance(profile_ceiling, int) and profile_ceiling > 0:
                max_tasks_per_batch = profile_ceiling
    if max_tasks_per_batch <= 0:
        max_tasks_per_batch = int(get_effective("execution", "max_tasks_per_batch"))

    config: dict[str, Any] = {
        "project_dir": str(project_dir),
        "auto_approve": auto_approve,
        "adaptive_critique": adaptive_critique,
        "robustness": robustness,
        "mode": mode,
        "strict_notes": strict_notes,
        "max_tasks_per_batch": max_tasks_per_batch,
        "agent": "hermes" if getattr(args, "hermes", None) is not None else "",
    }
    if pipeline is not None:
        config["pipeline"] = pipeline
    if getattr(args, "profile", None):
        config["profile"] = args.profile
    if getattr(args, "vendor", None):
        config["vendor"] = args.vendor
    if getattr(args, "critic", None):
        config["critic"] = args.critic
    if getattr(args, "depth", None):
        config["depth"] = args.depth
    if getattr(args, "deepseek_provider", None):
        config["deepseek_provider"] = args.deepseek_provider
    if getattr(args, "with_prep", False):
        config["with_prep"] = True
    if getattr(args, "with_feedback", False):
        config["with_feedback"] = True
    prep_direction_raw = getattr(args, "prep_direction", None)
    if prep_direction_raw is not None:
        prep_direction = str(prep_direction_raw).strip()
        if not prep_direction:
            raise CliError("invalid_args", "--prep-direction must be non-empty when provided")
        config["prep_direction"] = prep_direction
    if normalized_output_path is not None:
        config["output_path"] = normalized_output_path
    if raw_form:
        config["form"] = str(raw_form)
    if normalized_primary_criterion is not None:
        config["primary_criterion"] = normalized_primary_criterion
    if from_doc_rel is not None:
        config["from_doc"] = from_doc_rel
    phase_models = list(getattr(args, "phase_model", None) or [])
    if phase_models:
        config["phase_model"] = phase_models

    return config, auto_approve, robustness, strict_notes, strict_notes_explicit


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
    # T10 step (2): preserve the metaplan→state.config.mode='doc' coercion;
    # preserve joke→state.config.mode='joke' (do NOT rewrite to 'creative').
    if mode == "metaplan":
        mode = "doc"
    # T10 step (3) HARD CONTRACT: --form rules. The existing init.py:60
    # logic already rejects --form on doc|metaplan (mode != 'creative')
    # and the creative branch requires --form; for --mode joke we
    # preserve the historical behaviour (init.py:60 rejects an explicit
    # --form joke) per the v11 debt note — form is implicit when joke
    # is selected.
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

    # T10 step (2)+(7): pipeline routing seed.
    # --mode code → pipeline=None (no key written) and no warning.
    # --mode doc|creative|metaplan|joke → seed state.config.pipeline +
    # emit the verbatim deprecation warning to stderr.
    pipeline_routing: str | None = None
    if explicit_mode in _DEPRECATED_INIT_MODES:
        pipeline_routing = _PIPELINE_ROUTING[explicit_mode]
        _emit_mode_deprecation_warning(explicit_mode)

    # Build the full state.config via the single helper so the
    # auto_approve fallback / strict_notes auto-on / prep_direction
    # strip+non-empty normalisations apply uniformly to every code path,
    # including the deprecated-mode redirects.
    config, auto_approve, robustness, strict_notes, strict_notes_explicit = (
        _build_state_config(
            args,
            project_dir=project_dir,
            pipeline=pipeline_routing,
            mode=mode,
            raw_form=raw_form,
            normalized_output_path=normalized_output_path,
            normalized_primary_criterion=normalized_primary_criterion,
            from_doc_rel=from_doc_rel,
        )
    )

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
        "config": config,
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
    # Persist --vendor / --critic so subprocess phases (which don't re-pass
    # the original CLI flags) keep applying the same profile rewrites at
    # step time. apply_profile_expansion bakes the rewrite into the
    # resolved phase_models too, but persisting the dials directly keeps
    # the override observable / debuggable.
    if getattr(args, "vendor", None):
        state["config"]["vendor"] = args.vendor
    if getattr(args, "critic", None):
        state["config"]["critic"] = args.critic
    if getattr(args, "depth", None):
        state["config"]["depth"] = args.depth
    if getattr(args, "deepseek_provider", None):
        state["config"]["deepseek_provider"] = args.deepseek_provider
    tier_models = getattr(args, "tier_models", None)
    if tier_models:
        state["config"]["tier_models"] = tier_models
    if getattr(args, "with_prep", False):
        state["config"]["with_prep"] = True
    if getattr(args, "with_feedback", False):
        state["config"]["with_feedback"] = True
    prep_direction_raw = getattr(args, "prep_direction", None)
    if prep_direction_raw is not None:
        prep_direction = str(prep_direction_raw).strip()
        if not prep_direction:
            raise CliError("invalid_args", "--prep-direction must be non-empty when provided")
        state["config"]["prep_direction"] = prep_direction
    # If the plan was initialized inside a freshly-created worktree
    # (via `megaplan init --in-worktree <name>`), persist the audit trail.
    worktree_meta = getattr(args, "_worktree_meta", None)
    if worktree_meta:
        state["meta"]["worktree"] = dict(worktree_meta)
    if from_doc_rel is not None:
        state["meta"]["imported_decisions"] = imported_decisions
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
    if worktree_meta:
        summary = (
            f"Created worktree at {worktree_meta['path']} on branch "
            f"{worktree_meta['branch']}; plan initialized at "
            f"{plan_dir}."
        )
    else:
        summary = f"Initialized plan '{plan_name}' for project {project_dir}"
    response: StepResponse = {
        "success": True,
        "step": "init",
        "plan": plan_name,
        "state": STATE_INITIALIZED,
        "summary": summary,
        "artifacts": ["state.json"],
        "next_step": next_steps[0] if next_steps else None,
        "auto_approve": auto_approve,
        "robustness": robustness,
    }
    if worktree_meta:
        response["worktree"] = dict(worktree_meta)
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
