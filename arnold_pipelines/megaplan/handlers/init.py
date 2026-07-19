from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.artifacts import markdown_body
from arnold_pipelines.megaplan.anchors import AnchorCaptureRequest, attach_anchor_documents, validate_anchor_source
from arnold_pipelines.megaplan.runtime.doc_assembly import extract_settled_decisions
from arnold_pipelines.megaplan.runtime.execution_environment import (
    persist_plan_isolation_evidence,
)
from arnold_pipelines.megaplan.forms import available_form_ids
from arnold_pipelines.megaplan.profiles import DEFAULT_AGENT_ROUTING, apply_profile_expansion, load_profile_metadata
from arnold_pipelines.megaplan.profiles import ROBUSTNESS_LEVELS, normalize_robustness
from arnold_pipelines.megaplan.types import CliError, PlanState, StepResponse
from arnold_pipelines.megaplan.planning.state import STATE_INITIALIZED
from arnold_pipelines.megaplan._core import (
    append_history,
    ensure_runtime_layout,
    find_command,
    get_effective,
    setting_is_explicit,
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
        robustness = get_effective("execution", "robustness", project_dir=project_dir)
    robustness = normalize_robustness(robustness)

    auto_approve_value = getattr(args, "auto_approve", None)
    if auto_approve_value is None:
        auto_approve_value = get_effective("execution", "auto_approve", project_dir=project_dir)
    auto_approve = bool(auto_approve_value)

    # Precedence: explicit --adaptive-critique CLI flag > explicit user-config
    # setting > profile-level `adaptive_critique` field > global default (False).
    # The profile field is consulted ONLY when the user has pinned nothing,
    # so premium-bearing profiles (partnered/premium/apex) default it on while
    # open-only profiles — which omit the field — stay off and never force a
    # premium evaluator key into a key-free setup.
    adaptive_critique_value = getattr(args, "adaptive_critique", None)
    if adaptive_critique_value is None:
        if setting_is_explicit("execution", "adaptive_critique", project_dir=project_dir):
            adaptive_critique_value = get_effective("execution", "adaptive_critique", project_dir=project_dir)
        else:
            profile_name = getattr(args, "profile", None)
            profile_default: Any = None
            if profile_name:
                profile_meta = load_profile_metadata(project_dir=project_dir).get(profile_name, {})
                profile_default = profile_meta.get("adaptive_critique")
            if isinstance(profile_default, bool):
                adaptive_critique_value = profile_default
            else:
                adaptive_critique_value = get_effective("execution", "adaptive_critique", project_dir=project_dir)
    adaptive_critique = bool(adaptive_critique_value)

    # Layered defense (May 2026 — see docs/critique.md): when adaptive critique
    # resolves True, fail fast at init if the runtime wiring is incomplete.
    # The original silent-fallback bug shipped because the missing schema only
    # KeyError'd inside the critique handler under a broad except. Probing at
    # init means a misconfigured profile is rejected before any planning cost.
    if adaptive_critique:
        from arnold_pipelines.megaplan.audits.critique_evaluator import assert_adaptive_critique_wired

        assert_adaptive_critique_wired()

    # Precedence mirrors adaptive_critique for the stored value, but only an
    # explicit operator source (CLI flag or explicit user config) is allowed to
    # act as a pin at critique time. Profile/default values are informational
    # and must not shadow per-lens tier routing.
    critic_model_explicit = False
    critic_model_value = getattr(args, "critic_model", None)
    if critic_model_value is not None:
        critic_model_explicit = True
    if critic_model_value is None:
        if setting_is_explicit("execution", "critic_model", project_dir=project_dir):
            critic_model_value = get_effective("execution", "critic_model", project_dir=project_dir)
            critic_model_explicit = True
        else:
            profile_name = getattr(args, "profile", None)
            profile_critic: Any = None
            if profile_name:
                profile_meta = load_profile_metadata(project_dir=project_dir).get(profile_name, {})
                profile_critic = profile_meta.get("critic_model")
            if isinstance(profile_critic, str) and profile_critic:
                critic_model_value = profile_critic
            else:
                critic_model_value = get_effective("execution", "critic_model", project_dir=project_dir)
    critic_model = str(critic_model_value or "").strip()

    strict_notes_arg = getattr(args, "strict_notes", None)
    strict_notes_explicit = strict_notes_arg is not None
    if strict_notes_arg is None:
        if mode == "doc":
            strict_notes_arg = True
        else:
            strict_notes_arg = get_effective("execution", "strict_notes", project_dir=project_dir)
    strict_notes = bool(strict_notes_arg)

    # Strict adaptive critique (PR #52, May 2026): when True AND
    # adaptive_critique is True, the critique handler raises
    # AdaptiveCritiqueDegradedError instead of silently falling back to static
    # lenses on a runtime-recoverable failure. Off by default for backward
    # compat. Recommended for production / CI / important runs (see
    # docs/critique.md). Precedence mirrors other execution settings: CLI flag
    # > explicit user config > global default.
    strict_adaptive_critique_arg = getattr(args, "strict_adaptive_critique", None)
    if strict_adaptive_critique_arg is None:
        strict_adaptive_critique_arg = get_effective("execution", "strict_adaptive_critique", project_dir=project_dir)
    strict_adaptive_critique = bool(strict_adaptive_critique_arg)

    max_tasks_per_batch_arg = getattr(args, "max_tasks_per_batch", None)
    if max_tasks_per_batch_arg is not None:
        max_tasks_per_batch = int(max_tasks_per_batch_arg)
    else:
        max_tasks_per_batch = int(get_effective("execution", "max_tasks_per_batch", project_dir=project_dir))
        profile_name = getattr(args, "profile", None)
        if profile_name:
            profile_meta = load_profile_metadata(project_dir=project_dir).get(profile_name, {})
            profile_ceiling = profile_meta.get("max_tasks_per_batch")
            if isinstance(profile_ceiling, int) and profile_ceiling > 0:
                max_tasks_per_batch = profile_ceiling
    if max_tasks_per_batch <= 0:
        max_tasks_per_batch = int(get_effective("execution", "max_tasks_per_batch", project_dir=project_dir))

    # Completion-verification contract mode: CLI flag > get_effective.
    # Snapshotted here so the gate never re-reads the live environment.
    completion_contract_mode = getattr(args, "completion_contract_mode", None)
    if completion_contract_mode is None:
        completion_contract_mode = get_effective("execution", "completion_contract_mode", project_dir=project_dir)

    # Full-suite backstop mode: CLI flag > get_effective.
    # Snapshotted here so chain gates do not re-read live environment.
    full_suite_backstop_mode = getattr(args, "full_suite_backstop_mode", None)
    if full_suite_backstop_mode is None:
        full_suite_backstop_mode = get_effective("execution", "full_suite_backstop_mode")

    # Test command the harness invokes: CLI flag > get_effective.
    test_command = getattr(args, "test_command", None)
    if test_command is None:
        test_command = get_effective("execution", "test_command", project_dir=project_dir)

    # Baseline / verification timeout: CLI flag > get_effective.
    test_baseline_timeout = getattr(args, "test_baseline_timeout", None)
    if test_baseline_timeout is None:
        test_baseline_timeout = get_effective("execution", "test_baseline_timeout", project_dir=project_dir)

    config: dict[str, Any] = {
        "project_dir": str(project_dir),
        "auto_approve": auto_approve,
        "adaptive_critique": adaptive_critique,
        "strict_adaptive_critique": strict_adaptive_critique,
        "critic_model": critic_model,
        "critic_model_explicit": critic_model_explicit,
        "robustness": robustness,
        "mode": mode,
        "strict_notes": strict_notes,
        "max_tasks_per_batch": max_tasks_per_batch,
        "agent": "hermes" if getattr(args, "hermes", None) is not None else "",
        "completion_contract_mode": completion_contract_mode,
        "full_suite_backstop_mode": full_suite_backstop_mode,
        "test_command": test_command,
        "test_baseline_timeout": test_baseline_timeout,
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
    if getattr(args, "max_execute_tier", None) is not None:
        config["max_execute_tier"] = args.max_execute_tier
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
    hermes_model = getattr(args, "hermes", None)
    if isinstance(hermes_model, str) and hermes_model.strip():
        pinned_phases = {
            entry.split("=", 1)[0]
            for entry in phase_models
            if isinstance(entry, str) and "=" in entry
        }
        hermes_model = hermes_model.strip()
        hermes_spec = hermes_model if hermes_model.startswith("hermes:") else f"hermes:{hermes_model}"
        phase_models.extend(
            f"{phase}={hermes_spec}"
            for phase in DEFAULT_AGENT_ROUTING
            if phase not in pinned_phases
        )
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
    idea_source_path: Path | None = None
    if positional_idea and idea_file:
        raise CliError("invalid_args", "Pass either the positional idea or --idea-file, not both")
    if idea_file:
        idea_path = _resolve_idea_path(idea_file, project_dir=project_dir)
        if not idea_path.is_file():
            raise CliError("missing_idea_file", f"idea file not found under {project_dir}: {idea_path}")
        try:
            idea_text = markdown_body(idea_path).strip()
        except OSError as exc:
            raise CliError("invalid_args", f"Unable to read --idea-file {idea_path}: {exc}") from exc
        idea_source = "--idea-file"
        idea_source_path = idea_path
    elif positional_idea:
        idea_path = _resolve_idea_path(positional_idea, project_dir=project_dir)
        if idea_path.is_file():
            try:
                idea_text = markdown_body(idea_path).strip()
            except OSError as exc:
                raise CliError("invalid_args", f"Unable to read idea file under {project_dir}: {idea_path}: {exc}") from exc
            idea_source = "positional idea file"
            idea_source_path = idea_path
        elif _looks_like_idea_file_path(positional_idea):
            raise CliError("missing_idea_file", f"idea file not found under {project_dir}: {idea_path}")
        else:
            idea_text = positional_idea
            idea_source = "positional idea"
    else:
        raise CliError("invalid_args", "Provide an idea argument or --idea-file <path>")
    if not idea_text.strip():
        raise CliError("BRIEF_MISSING", f"{idea_source} must contain non-empty UTF-8 text")
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
    north_star_path: Path | None = None
    raw_north_star = getattr(args, "north_star", None)
    if raw_north_star:
        north_star_path = validate_anchor_source(
            _resolve_idea_path(raw_north_star, project_dir=project_dir),
            label="--north-star",
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
    idea_snapshot_path = "idea_snapshot.md"
    (plan_dir / idea_snapshot_path).write_text(idea_text, encoding="utf-8")

    state: PlanState = {
        "name": plan_name,
        "idea": idea_text,
        "idea_snapshot_path": idea_snapshot_path,
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
    if idea_source_path is not None:
        from arnold_pipelines.megaplan.planning.source_binding import (
            capture_canonical_source_binding,
        )

        capture_canonical_source_binding(
            state,
            source_path=idea_source_path,
            project_dir=project_dir,
        )
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
    if getattr(args, "max_execute_tier", None) is not None:
        state["config"]["max_execute_tier"] = args.max_execute_tier
    tier_models = getattr(args, "tier_models", None)
    if tier_models:
        state["config"]["tier_models"] = tier_models
    routing_degradations = getattr(args, "routing_degradations", None)
    if routing_degradations:
        state["config"]["routing_degradations"] = routing_degradations
    prep_models = getattr(args, "prep_models", None)
    if prep_models:
        state["config"]["prep_models"] = prep_models
    prep_model_resolver_trace = getattr(args, "prep_model_resolver_trace", None)
    if prep_model_resolver_trace:
        state["config"]["prep_model_resolver_trace"] = prep_model_resolver_trace
    if getattr(args, "with_prep", False):
        state["config"]["with_prep"] = True
    if getattr(args, "with_feedback", False):
        state["config"]["with_feedback"] = True
    # Resolve prep_clarify: CLI > [defaults] > True.
    # Only written to config when False to keep state lean (absent == True).
    if not getattr(args, "prep_clarify", True):
        state["config"]["prep_clarify"] = False
    else:
        from arnold_pipelines.megaplan._core.user_config import default_prep_clarify
        if not default_prep_clarify():
            state["config"]["prep_clarify"] = False
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
    if north_star_path is not None:
        attach_anchor_documents(
            plan_dir=plan_dir,
            state=state,
            documents=[
                AnchorCaptureRequest(
                    anchor_type="north_star",
                    scope="plan",
                    source_path=north_star_path,
                    source_kind="cli",
                )
            ],
            project_root=project_dir,
        )
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
    persist_plan_isolation_evidence(root=root, state=state, phase="init")
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
        "artifacts": ["state.json"]
        + (
            ["anchors/north_star/plan.md", "anchors/north_star/combined.md"]
            if north_star_path is not None
            else []
        ),
        "next_step": next_steps[0] if next_steps else None,
        "auto_approve": auto_approve,
        "robustness": robustness,
    }
    if worktree_meta:
        response["worktree"] = dict(worktree_meta)
    if parse_warnings:
        response["warnings"] = parse_warnings
    if bool(getattr(args, "auto_start", False)):
        from arnold_pipelines.megaplan.auto import drive as auto_drive

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


def _resolve_idea_path(raw: str | Path, *, project_dir: Path) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (project_dir / path).resolve()


def _looks_like_idea_file_path(raw: object) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return False
    path = Path(raw)
    return path.suffix.lower() in {".md", ".markdown", ".txt"} or len(path.parts) > 1
