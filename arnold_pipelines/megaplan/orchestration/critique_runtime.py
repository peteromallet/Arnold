from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan import handlers as _pkg
from arnold_pipelines.megaplan.outcomes import CritiqueOutcome, ReviseOutcome
from arnold_pipelines.megaplan.audits.robustness import validate_critique_checks
from arnold_pipelines.megaplan.forms.provocations import select_active_checks
from arnold_pipelines.megaplan.forms.directors_notes import update_directors_notes_at_aggregate
from arnold_pipelines.megaplan.orchestration.gate_checks import build_gate_artifact, build_orchestrator_guidance
from arnold_pipelines.megaplan.orchestration.gate_signals import build_gate_signals, compute_plan_delta_percent, compute_recurring_critiques
from arnold_pipelines.megaplan.orchestration.critique_status import (
    annotate_unverifiable_checks,
    build_unverifiable_warnings,
)
from arnold_pipelines.megaplan.orchestration.parallel_critique import run_parallel_critique
from arnold_pipelines.megaplan.orchestration.critique_custody import (
    CritiqueCustodyError,
    prepare_critique_payload,
    write_critique_production_receipt,
)
from arnold_pipelines.megaplan.profiles import apply_profile_expansion
from arnold_pipelines.megaplan.model_seam import ModelStructuralAuditError, audit_step_payload
from arnold_pipelines.megaplan.schema_projection import schema_property_names
from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.types import (
    CliError,
    FLAG_BLOCKING_STATUSES,
    PlanState,
    StepResponse,
)
from arnold_pipelines.megaplan.planning.state import (
    STATE_CRITIQUED,
    STATE_GATED,
    STATE_PLANNED,
    STATE_TIEBREAKER_PENDING,
)
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan._core import (
    adaptive_critique_enabled,
    atomic_write_json,
    atomic_write_text,
    configured_robustness,
    infer_next_steps,
    is_creative_mode,
    latest_plan_meta_path,
    latest_plan_path,
    load_flag_registry,
    load_plan_locked,
    now_utc,
    pinned_critic_model,
    read_json,
    record_step_failure,
    require_state,
    scope_creep_flags,
    sha256_file,
    workflow_includes_step,
)

from arnold_pipelines.megaplan.handlers.plan import (
    _build_verifiability_flags,
    _derive_plan_test_blast_radius,
    _merge_imported_decision_criteria,
)
from arnold_pipelines.megaplan.handlers.shared import (
    _agent_mode_parts,
    _append_to_meta,
    _finish_step,
    _load_bearing_decision_criteria_issues,
    _raise_step_validation_error,
    _write_plan_version,
)
from arnold_pipelines.megaplan.handlers.tiebreaker import _build_tiebreaker_reprompt
from arnold_pipelines.megaplan.fallback_chains import select_fallback_spec
from arnold_pipelines.megaplan.north_star_actions import (
    NORTH_STAR_ACTION_TYPES,
    NorthStarActionValidationError,
    blocking_north_star_actions,
    is_blocking_action,
    is_blocking_category,
    normalize_north_star_actions_addressed,
)

log = logging.getLogger("megaplan")
_ORIGINAL_VALIDATE_CRITIQUE_CHECKS = validate_critique_checks


def _recover_evaluator_payload_from_raw(
    raw: str,
    evaluator_model: str,
    vendor: str | None,
) -> dict[str, Any] | None:
    """Recover a usable critique_evaluator payload from the raw transcript.

    The Codex structured-output path occasionally emits a valid JSON verdict
    in its raw transcript while reporting an empty ``worker.payload``.  When
    scratch promotion falls back to that empty payload, this helper scans the
    saved raw output for the last JSON object that looks like a valid evaluator
    verdict and passes schema validation.
    """
    try:
        from arnold_pipelines.megaplan.workers._impl import (
            _extract_json_candidates_from_raw,
        )
    except Exception:
        return None

    candidates = _extract_json_candidates_from_raw(raw)
    from arnold_pipelines.megaplan.audits.critique_evaluator import (
        validate_evaluator_verdict,
    )

    for cand in reversed(candidates):
        if not isinstance(cand, dict):
            continue
        if "selections" not in cand or "skipped" not in cand:
            continue
        try:
            validate_evaluator_verdict(
                cand,
                evaluator_model=evaluator_model,
                vendor=vendor if vendor in ("claude", "codex") else None,
            )
        except Exception:
            continue
        return cand
    return None


def _prefer_nonempty_evaluator_payload(
    worker_payload: dict[str, Any], promoted_payload: dict[str, Any]
) -> dict[str, Any]:
    """Do not let an untouched empty evaluator scratch erase a worker verdict."""
    if worker_payload.get("selections") and not promoted_payload.get("selections"):
        return worker_payload
    return promoted_payload


# ── T11: Critique-scoped scratch promotion known keys ──────────────────────
# The model produces only these keys in the scratch template; unknown
# top-level keys injected by the model are stripped before promotion.
_CRITIQUE_SCRATCH_KNOWN_KEYS: frozenset[str] = schema_property_names(
    SCHEMAS["critique.json"],
    contract="critique scratch promotion",
)


def _critique_scratch_known_keys() -> frozenset[str]:
    return schema_property_names(
        SCHEMAS["critique.json"],
        contract="critique scratch promotion",
    )


def _critique_evaluator_scratch_known_keys() -> frozenset[str]:
    return schema_property_names(
        SCHEMAS["critique_evaluator.json"],
        contract="critique evaluator scratch promotion",
    )
# ────────────────────────────────────────────────────────────────────────────


def _critique_check_validator() -> Any:
    pkg_validator = getattr(_pkg, "validate_critique_checks", validate_critique_checks)
    if (
        validate_critique_checks is _ORIGINAL_VALIDATE_CRITIQUE_CHECKS
        and pkg_validator is not _ORIGINAL_VALIDATE_CRITIQUE_CHECKS
    ):
        return pkg_validator
    return validate_critique_checks


def _rebuild_recovered_critique_worker(
    worker: WorkerResult,
    recovered_payload: dict[str, Any],
    invalid_checks: list[str],
) -> WorkerResult:
    return WorkerResult(
        payload=recovered_payload,
        raw_output=worker.raw_output + "\n[megaplan] recovered critique payload from critique_output.json; original worker failed validation for checks: " + ", ".join(invalid_checks),
        duration_ms=worker.duration_ms,
        cost_usd=worker.cost_usd,
        session_id=worker.session_id,
        trace_output=worker.trace_output,
        rendered_prompt=worker.rendered_prompt,
        model_actual=worker.model_actual,
        prompt_tokens=worker.prompt_tokens,
        completion_tokens=worker.completion_tokens,
        total_tokens=worker.total_tokens,
        rate_limit=worker.rate_limit,
    )


def _apply_adaptive_critique_routing(
    state: PlanState,
    args: argparse.Namespace,
    active_checks: list[dict[str, Any]],
) -> str | None:
    """Attach per-check critic modes or return a whole-phase critic pin.

    In adaptive critique mode, ``tier_models.critique`` is authoritative for
    complexities it names. A global ``execution.critic_model`` pin is only a
    fallback for missing complexity tiers, not a short-circuit that disables
    tier routing.
    """
    _pin = pinned_critic_model(state)

    # Resolve per-check AgentMode from tier_models.critique (complexity-based
    # routing, SD1). Cache complexity -> AgentMode to avoid redundant resolution
    # when multiple checks share the same complexity tier.
    _tier_models = getattr(args, "tier_models", None)
    if not isinstance(_tier_models, dict):
        _tier_models = {}
    _critique_tiers = _tier_models.get("critique")
    # apply_profile_expansion strips critique tiers when a persisted/static
    # phase_model entry for critique is present. Prefer the tier table persisted
    # with the plan before reloading the current profile from disk; profile files
    # can legitimately drift during long-running chains, while state.json records
    # the routing contract chosen at init time.
    if not isinstance(_critique_tiers, dict) or not _critique_tiers:
        _state_tier_models = (state.get("config") or {}).get("tier_models")
        if isinstance(_state_tier_models, dict):
            _critique_tiers = _state_tier_models.get("critique")
    # If no persisted tier table exists, reload the raw profile tiers so
    # adaptive routing can still honor complexity-based critic assignments.
    if not isinstance(_critique_tiers, dict) or not _critique_tiers:
        _profile_name = (
            getattr(args, "profile", None)
            or (state.get("config") or {}).get("profile")
        )
        if _profile_name:
            try:
                from arnold_pipelines.megaplan.profiles import (
                    load_profile_metadata,
                    load_profiles,
                )
                from arnold_pipelines.megaplan.profiles import _resolve_tier_models_with_inheritance

                _profile_tiers = _resolve_tier_models_with_inheritance(
                    _profile_name,
                    system_profiles=load_profiles(),
                    system_metadata=load_profile_metadata(),
                    pipeline_local_profiles={},
                    pipeline_local_metadata={},
                )
                _critique_tiers = _profile_tiers.get("critique")
            except Exception:
                _critique_tiers = None
    if not isinstance(_critique_tiers, dict) or not _critique_tiers:
        return _pin

    from arnold_pipelines.megaplan.execute.batch import _resolve_tier_spec
    from arnold_pipelines.megaplan.types import AgentMode as _TierAgentMode

    _complexity_cache: dict[int, _TierAgentMode] = {}
    _pin_agent_mode: _TierAgentMode | None = None

    def _tier_value_for(tier: int) -> object | None:
        value = _critique_tiers.get(tier)
        return _critique_tiers.get(str(tier)) if value is None else value

    def _configured_tiers() -> tuple[int, ...]:
        """Return structurally valid configured tiers in deterministic order."""
        return tuple(
            sorted(
                {
                    int(raw_tier)
                    for raw_tier in _critique_tiers
                    if not isinstance(raw_tier, bool)
                    and str(raw_tier).isdigit()
                    and 1 <= int(raw_tier) <= 10
                    and _tier_value_for(int(raw_tier)) is not None
                }
            )
        )

    def _tier_spec_for(complexity: int) -> str | None:
        _raw = _tier_value_for(complexity)
        selected_tier = complexity
        # Profiles that predate the 1..10 evaluator scale legitimately expose
        # only 1..5 critique tiers.  A high valid selection maps to their
        # strongest configured critic; do not use this as a general sparse-map
        # fallback, because a missing tier inside the configured range remains
        # a routing-contract error.
        if _raw is None:
            tiers = _configured_tiers()
            if (
                tiers
                and tiers == tuple(range(1, tiers[-1] + 1))
                and complexity > tiers[-1]
            ):
                selected_tier = tiers[-1]
                _raw = _tier_value_for(selected_tier)
        if isinstance(_raw, str):
            return _raw or None
        if isinstance(_raw, list):
            return select_fallback_spec(
                _raw, 0, path=f"tier_models.critique.{selected_tier}"
            )
        return None

    def _resolved_pin_agent_mode() -> _TierAgentMode:
        nonlocal _pin_agent_mode
        if _pin_agent_mode is None:
            from arnold_pipelines.megaplan.audits.critique_evaluator import roster_dispatch_spec
            from arnold_pipelines.megaplan.types import parse_agent_spec

            _pin_parsed = parse_agent_spec(roster_dispatch_spec(str(_pin)))
            _pin_agent_mode = _TierAgentMode(
                agent=_pin_parsed.agent,
                mode="fresh",
                refreshed=False,
                model=_pin_parsed.model,
                effort=_pin_parsed.effort,
                resolved_model=_pin_parsed.model,
            )
        return _pin_agent_mode

    for _check in active_checks:
        _cid = _check.get("id", "?")
        _cx = _check.get("complexity")
        # Critique selection and execute-tier routing share the 1..10
        # complexity scale.  Keep this structural check strict (including
        # rejecting bool, which is an int subclass) while permitting the high
        # tiers that the evaluator and profile tier tables can legitimately
        # select.
        if (
            not isinstance(_cx, int)
            or isinstance(_cx, bool)
            or _cx < 1
            or _cx > 10
        ):
            raise CliError(
                "critique_complexity_invariant",
                f"Check '{_cid}' has missing or invalid "
                f"complexity ({_cx!r}); cannot resolve tier "
                "routing. This is an invariant error in "
                "the evaluator output.",
            )
        if _cx not in _complexity_cache:
            _spec = _tier_spec_for(_cx)
            if not _spec:
                if _pin:
                    _complexity_cache[_cx] = _resolved_pin_agent_mode()
                else:
                    raise CliError(
                        "critique_tier_missing",
                        f"No tier spec for complexity {_cx} "
                        f"in tier_models.critique; cannot "
                        f"route check '{_cid}'.",
                    )
            else:
                _t_agent, _t_mode, _t_model = _resolve_tier_spec(
                    args, _spec, phase="critique"
                )
                _complexity_cache[_cx] = _TierAgentMode(
                    agent=_t_agent,
                    mode=_t_mode,
                    refreshed=False,
                    model=_t_model,
                    effort=None,
                    resolved_model=_t_model,
                )
        _check["_resolved_agent_mode"] = _complexity_cache[_cx]
        _check["_routing_selected_spec"] = _tier_spec_for(_cx) or f"critic_model:{_pin}"
        _check["_routing_tier"] = _cx
        _check["_routing_tier_active"] = True

    return None


def handle_critique(root: Path, args: argparse.Namespace) -> StepResponse:
    from arnold_pipelines.megaplan.handlers.gate import _write_gate_carry

    with load_plan_locked(root, args.plan, step="critique") as (plan_dir, state):
        require_state(state, "critique", {STATE_PLANNED})
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        iteration = state["iteration"]
        robustness = configured_robustness(state)
        state["last_gate"] = {}
        critique_filename = f"critique_v{iteration}.json"
        if robustness == "bare":
            raise CliError(
                "bare_skips_critique",
                "bare robustness skips critique entirely; the workflow routes plan -> finalize directly. "
                "Run `megaplan finalize` instead, or use --robustness light if you want a critique pass.",
            )
        adaptive_path = adaptive_critique_enabled(state) and not is_creative_mode(state)
        critic_model_override: str | None = None
        _verified_flag_ids_set: set[str] = set()
        _selection_why: dict[str, str] = {}
        if adaptive_path:
            from arnold_pipelines.megaplan.audits.critique_evaluator import validate_evaluator_verdict
            from arnold_pipelines.megaplan.audits.robustness import CRITIQUE_CHECKS

            from arnold_pipelines.megaplan.types import AgentMode as _AgentMode

            resolved = _pkg.resolve_agent_mode("critique", args)
            # The evaluator runs on its OWN routing slot (`critique_evaluator`),
            # declared per profile, at its own depth (default medium) — it is NOT
            # escalated off the critic slot. Each profile routes the evaluator to
            # the vendor it wants: premium profiles -> claude/codex; all-DeepSeek
            # /open profiles -> their own family, so those profiles stay
            # premium-free instead of silently pulling a premium model into the
            # critique phase. --vendor and --phase-model flow through resolution;
            # a bare config with no profile falls back to
            # DEFAULT_AGENT_ROUTING["critique_evaluator"] (claude, or codex under
            # --vendor codex). The rater >= dispatchee invariant is enforced
            # downstream by validate_evaluator_verdict — a too-weak evaluator
            # simply can't assign stronger critics, and an invalid verdict
            # triggers the retry-then-block path below. Depth is medium by
            # default and never touched by --depth; override with
            # `--phase-model critique_evaluator=<agent>:<depth>`.
            _eval_slot = _pkg.resolve_agent_mode("critique_evaluator", args)
            _ev_agent, _ev_mode, _ev_refreshed, _ev_model = _agent_mode_parts(_eval_slot)
            _ev_resolved_model = (
                _eval_slot.resolved_model if isinstance(_eval_slot, _AgentMode) else _ev_model
            ) or _ev_model
            _eval_effort = (
                _eval_slot.effort if isinstance(_eval_slot, _AgentMode) else None
            ) or "medium"
            evaluator_model = _ev_resolved_model or _ev_agent
            evaluator_resolved: Any = _AgentMode(
                agent=_ev_agent,
                mode=_ev_mode,
                refreshed=_ev_refreshed,
                model=_ev_model,
                effort=_eval_effort,
                resolved_model=_ev_resolved_model,
            )
            _eval_prompt_kwargs: dict[str, Any] | None = None
            # Prep context — feed the evaluator the prep research record (dossier +
            # coverage metrics) so it selects lenses knowing what was investigated
            # and where prep left gaps. Available from iteration 1 onward.
            _prep_dossier_path = plan_dir / "prep_dossier.md"
            _prep_metrics_path = plan_dir / "prep_metrics.json"
            _prep_dossier_text = (
                _prep_dossier_path.read_text(encoding="utf-8")
                if _prep_dossier_path.exists()
                else None
            )
            _prep_metrics = (
                read_json(_prep_metrics_path) if _prep_metrics_path.exists() else None
            )
            if _prep_dossier_text or _prep_metrics:
                _eval_prompt_kwargs = {
                    "prep_dossier_text": _prep_dossier_text,
                    "prep_metrics": _prep_metrics,
                }
            if iteration >= 2:
                from arnold_pipelines.megaplan.audits.iteration import compute_iteration_pressure as _compute_iteration_pressure
                from arnold_pipelines.megaplan.prompts.critique import _plan_version_unified_diff

                _registry = load_flag_registry(plan_dir)
                _resolved = [
                    {
                        "id": f["id"],
                        "concern": f.get("concern", ""),
                        "evidence": f.get("evidence", ""),
                        "resolution": f.get("resolution", {}),
                    }
                    for f in _registry.get("flags", [])
                    if isinstance(f.get("resolution"), dict) and f["resolution"].get("claim")
                ]
                _diff = _plan_version_unified_diff(plan_dir, iteration)
                _eval_prompt_kwargs = {
                    **(_eval_prompt_kwargs or {}),
                    "flag_lifecycle": _registry,
                    "iteration_pressure": _compute_iteration_pressure(plan_dir, state),
                    "gate_signals": build_gate_signals(plan_dir, state, root),
                    "revise_resolutions": _resolved,
                    "plan_diff": _diff if _diff else None,
                }
            # Adaptive critique is the ONLY critique path: there is no static
            # lens fallback. If the evaluator fails we retry once, then block
            # the milestone loudly rather than degrade to a hand-curated lens
            # set. One transient failure (flaky API, malformed first parse) is
            # absorbed; a persistent wiring fault surfaces as a hard error.
            _MAX_EVAL_ATTEMPTS = 2  # one initial attempt + one retry
            _eval_last_exc: Exception | None = None
            for _eval_attempt in range(1, _MAX_EVAL_ATTEMPTS + 1):
                try:
                    eval_worker, eval_agent, _, _ = _pkg._run_worker(
                        "critique_evaluator",
                        state,
                        plan_dir,
                        args,
                        root=root,
                        resolved=evaluator_resolved,
                        prompt_kwargs=_eval_prompt_kwargs,
                    )
                    # Persist the raw evaluator response BEFORE validation so a
                    # rejected/deduped verdict is inspectable post-hoc (the parsed
                    # verdict alone hid the root cause of past failures).
                    _raw_eval = getattr(eval_worker, "raw_output", None)
                    if _raw_eval:
                        # Write a per-iteration copy (_v{n}) so a multi-iteration
                        # plan keeps every iteration's evaluator reasoning, plus
                        # the canonical fixed-path file as the "latest" pointer
                        # that existing readers consume unchanged.
                        (plan_dir / f"critique_evaluator_raw_v{iteration}.txt").write_text(
                            _raw_eval, encoding="utf-8"
                        )
                        (plan_dir / "critique_evaluator_raw.txt").write_text(
                            _raw_eval, encoding="utf-8"
                        )
                    # ── T9: Scratch promotion ──────────────────────────
                    # Prefer valid filled critique_evaluator_output.json
                    # over worker.payload; fall back to worker.payload when
                    # scratch is missing/unmodified; fail hard on modified
                    # invalid scratch when file-fill was instructed (hermes
                    # agent).  Raw debug captures above are unaffected.
                    from arnold_pipelines.megaplan.handlers.structured_output import (
                        promote_scratch,
                        require_scratch_filename_for_phase,
                    )

                    _EVAL_KNOWN_KEYS = _critique_evaluator_scratch_known_keys()
                    _scratch_filename = require_scratch_filename_for_phase("critique_evaluator")
                    _seed_path = plan_dir / _scratch_filename
                    _seed_json: str | None = None
                    if _seed_path.exists():
                        try:
                            _seed_json = _seed_path.read_text(encoding="utf-8")
                        except (OSError, UnicodeDecodeError):
                            _seed_json = None

                    _file_fill_instructed = eval_agent == "hermes"

                    _worker_payload = dict(eval_worker.payload)
                    _, _promoted = promote_scratch(
                        plan_dir,
                        _scratch_filename,
                        _EVAL_KNOWN_KEYS,
                        eval_worker,
                        seed_json=_seed_json,
                        file_fill_instructed=_file_fill_instructed,
                    )
                    eval_worker.payload = _prefer_nonempty_evaluator_payload(
                        _worker_payload, _promoted
                    )
                    # Recovery: the Codex structured-output path sometimes
                    # returns an empty payload even though the raw transcript
                    # contains a valid verdict.  Re-parse the saved raw output
                    # before giving up.
                    if (
                        not eval_worker.payload.get("selections")
                        and _raw_eval
                    ):
                        _recovered = _recover_evaluator_payload_from_raw(
                            _raw_eval,
                            evaluator_model=evaluator_model,
                            vendor=state["config"].get("vendor"),
                        )
                        if _recovered is not None:
                            eval_worker.payload = _recovered
                            print(
                                "[megaplan] recovered critique_evaluator payload "
                                "from raw output",
                                file=sys.stderr,
                                flush=True,
                            )
                    # ────────────────────────────────────────────────────
                    _vendor = state["config"].get("vendor")
                    _eval_warnings = validate_evaluator_verdict(
                        eval_worker.payload,
                        evaluator_model=evaluator_model,
                        vendor=_vendor if _vendor in ("claude", "codex") else None,
                    )
                    if _eval_warnings:
                        _append_to_meta(state, "critique_evaluator_warnings", {
                            "iteration": iteration,
                            "deduped": _eval_warnings,
                        })
                        print(
                            f"[megaplan] NOTE: critique_evaluator verdict had "
                            f"{len(_eval_warnings)} recoverable issue(s), deduped: "
                            f"{'; '.join(_eval_warnings)}",
                            file=sys.stderr,
                            flush=True,
                        )
                    verdict = eval_worker.payload
                    selections = verdict.get("selections", [])
                    # The evaluator decides only WHICH lenses fire — not which
                    # model runs them. Each selected lens carries a 1–5
                    # `complexity` score (with a `complexity_justification`);
                    # the handler resolves the critic model per-lens from
                    # `tier_models.critique` further down (SD1). The only
                    # override is the operator pin (`execution.critic_model`,
                    # applied further down). The evaluator no longer emits
                    # per-lens model names — it only scores complexity.
                    critic_model_override = None
                    # Build a lookup from selection check_id → selection dict.
                    _sel_by_id: dict[str, dict[str, Any]] = {}
                    for sel in selections:
                        cid = sel.get("check_id", "")
                        if cid and cid not in _sel_by_id:
                            _sel_by_id[cid] = sel

                    selected_ids = {sel["check_id"] for sel in selections}
                    _selection_why: dict[str, str] = {}
                    active_checks: list[dict[str, Any]] = []
                    for c in CRITIQUE_CHECKS:
                        if c["id"] not in selected_ids:
                            continue
                        sel = _sel_by_id.get(c["id"], {})
                        # Attach complexity metadata to each active check so
                        # downstream routing (parallel critique / worker dispatch)
                        # can read per-check complexity without re-parsing the
                        # evaluator verdict.
                        check_dict = dict(c)
                        check_dict["complexity"] = sel.get("complexity")
                        check_dict["complexity_justification"] = sel.get(
                            "complexity_justification", ""
                        )
                        active_checks.append(check_dict)
                        # For catalog checks, the evaluator's complexity
                        # justification IS the selection reason — it explains why
                        # this lens was chosen at this complexity tier.
                        _selection_why[c["id"]] = sel.get(
                            "complexity_justification", ""
                        )

                    # Synthesize a check spec for each bespoke "other" custom area
                    # so it runs like a lens: its `why` becomes the critic's
                    # question/probe. These are additive (the validator keeps them
                    # out of the 9-lens coverage union). Build a unique id per area
                    # so two "other" entries don't collide on the key.
                    _used_ids = {c["id"] for c in active_checks}
                    for sel in selections:
                        if sel.get("check_id") != "other":
                            continue
                        area = sel.get("area", "")
                        slug = re.sub(r"[^a-z0-9]+", "_", area.lower()).strip("_") or "custom"
                        oid = f"other_{slug}"
                        if oid in _used_ids:
                            n = 2
                            while f"{oid}_{n}" in _used_ids:
                                n += 1
                            oid = f"{oid}_{n}"
                        _used_ids.add(oid)
                        active_checks.append({
                            "id": oid,
                            "question": sel.get("why", ""),
                            "tier": "extended",
                            "category": "custom",
                            "guidance": (
                                "Custom critique area added by the evaluator for "
                                f"this plan: {area}."
                            ),
                            # Routing/targeting metadata: complexity +
                            # justification let downstream dispatch select the
                            # right tier model without re-parsing the verdict.
                            "complexity": sel.get("complexity"),
                            "complexity_justification": sel.get(
                                "complexity_justification", ""
                            ),
                        })
                        # For `other` areas, the probe/question IS the `why`
                        # (it becomes the critic's question), while
                        # complexity_justification is kept on the check dict as
                        # routing/targeting metadata.
                        _selection_why[oid] = sel.get("why", "")
                    # Per-iteration copy (_v{n}) preserves each pass's verdict
                    # (stage-1 lens selections/skips + stage-3 flag_verifications
                    # on iteration >=2) for audit; the canonical file is the
                    # "latest" pointer for existing downstream readers.
                    atomic_write_json(plan_dir / f"evaluator_verdict_v{iteration}.json", verdict)
                    atomic_write_json(plan_dir / "evaluator_verdict.json", verdict)
                    # Apply flag verifications BEFORE the critic runs so it sees fresh statuses.
                    _fv_list = verdict.get("flag_verifications", [])
                    if _fv_list:
                        _verified_flag_ids_set = apply_flag_verifications(plan_dir, _fv_list)
                    break
                except Exception as exc:
                    _eval_last_exc = exc
                    _append_to_meta(state, "critique_evaluator_warnings", {
                        "iteration": iteration,
                        "attempt": _eval_attempt,
                        "error": str(exc),
                    })
                    print(
                        f"[megaplan] WARNING: critique_evaluator attempt "
                        f"{_eval_attempt}/{_MAX_EVAL_ATTEMPTS} failed "
                        f"({type(exc).__name__}: {exc}).",
                        file=sys.stderr,
                        flush=True,
                    )
            else:
                # Every attempt failed. There is no static lens fallback — block
                # the milestone rather than critique with a degraded lens set.
                _blocked_verdict = {
                    "evaluator_model": evaluator_model,
                    "blocked": True,
                    "attempts": _MAX_EVAL_ATTEMPTS,
                    "failure_reason": str(_eval_last_exc),
                }
                # Preserve the failed iteration's blocked verdict per-iteration
                # too, then write the canonical "latest" pointer.
                atomic_write_json(
                    plan_dir / f"evaluator_verdict_v{iteration}.json", _blocked_verdict
                )
                atomic_write_json(plan_dir / "evaluator_verdict.json", _blocked_verdict)
                raise CliError(
                    "critique_evaluator_failed",
                    f"critique_evaluator failed after {_MAX_EVAL_ATTEMPTS} attempts "
                    f"({type(_eval_last_exc).__name__}: {_eval_last_exc}). Adaptive "
                    "critique is the only critique path and there is no static fallback, "
                    "so the plan cannot be critiqued. Investigate the critique_evaluator "
                    "wiring (profile slot, schema, prompt) and re-run `megaplan critique`.",
                )
            expected_ids = [check["id"] for check in active_checks]
        else:
            active_checks = select_active_checks(state, robustness, plan_dir=plan_dir)
            expected_ids = [check["id"] for check in active_checks]
            resolved = _pkg.resolve_agent_mode("critique", args)
        # Explicit operator pin: when execution.critic_model was explicitly
        # supplied, the evaluator still selects which lenses fire, but every
        # critic is forced to that model. Stale/profile/default critic_model
        # values are ignored so tier_models.critique can route per complexity.
        if adaptive_path:
            critic_model_override = _apply_adaptive_critique_routing(
                state, args, active_checks
            )
        from arnold_pipelines.megaplan.types import AgentMode as _AgentMode

        agent_type, mode, refreshed, model = _agent_mode_parts(resolved)
        # Thinking depth for the critic: carry the resolved effort (set by
        # --depth or an explicit suffix on the `critique` slot) so the parallel
        # critic forwards it to its reasoning config. Captured before the
        # operator-pin branch below rebinds `resolved`.
        _critique_effort = getattr(resolved, "effort", None)
        # Resolved model (the materialized model the worker should launch with).
        # For an AgentMode this is .resolved_model (with the vendor default
        # applied); fall back to the bare model otherwise.
        _critique_resolved_model = getattr(resolved, "resolved_model", None) or model
        if adaptive_path and critic_model_override:
            # Operator pin only: the pinned `critic_model` is a bare roster
            # token (e.g. "deepseek-v4-pro"). Resolve it to a full agent spec so
            # the critic dispatches to the right vendor/provider instead of (a)
            # running under whatever agent the `critique` slot resolved to, or
            # (b) falling through to OpenRouter for an unprefixed DeepSeek name.
            # DeepSeek critics route to DeepSeek's direct API.
            from arnold_pipelines.megaplan.audits.critique_evaluator import roster_dispatch_spec
            from arnold_pipelines.megaplan.types import parse_agent_spec

            _override_parsed = parse_agent_spec(roster_dispatch_spec(critic_model_override))
            agent_type = _override_parsed.agent
            model = _override_parsed.model
            _critique_effort = _override_parsed.effort
            _critique_resolved_model = model
        # Reconstruct an AgentMode (NOT a bare 4-tuple) so the effort and
        # resolved_model survive the hop into run_step_with_worker. A plain
        # 4-tuple drops both: that is the effort-drop bug where a `critique`
        # slot's effort never reached the codex-effort gate (and a bad
        # ``model=`` rode through verbatim to ``-c model='...'``).
        resolved = _AgentMode(
            agent=agent_type,
            mode=mode,
            refreshed=refreshed,
            model=model,
            effort=_critique_effort,
            resolved_model=_critique_resolved_model,
        )
        if len(active_checks) > 1:
            for _check in active_checks:
                if adaptive_path and not critic_model_override:
                    _check.setdefault("_resolved_agent_mode", resolved)
                else:
                    _check["_resolved_agent_mode"] = resolved
        elif adaptive_path and not critic_model_override and active_checks:
            _single_resolved = active_checks[0].get("_resolved_agent_mode")
            if isinstance(_single_resolved, _AgentMode):
                resolved = _single_resolved
                agent_type, mode, refreshed, model = _agent_mode_parts(resolved)
                _critique_effort = getattr(resolved, "effort", None)
                _critique_resolved_model = getattr(resolved, "resolved_model", None) or model
        # Compute revise_context for adaptive path iterations >= 2
        _revise_ctx = ""
        if adaptive_path and iteration >= 2:
            from arnold_pipelines.megaplan.prompts.critique import _plan_version_unified_diff
            from arnold_pipelines.megaplan.flags import flag_resolution_summary

            _diff = _plan_version_unified_diff(plan_dir, iteration)
            _registry = load_flag_registry(plan_dir)
            _resolved_flags = [
                f for f in _registry.get("flags", [])
                if isinstance(f.get("resolution"), dict) and f["resolution"].get("claim")
            ]
            _parts: list[str] = []
            if _diff:
                _parts.append(f"Unified diff between plan versions:\n```diff\n{_diff}\n```")
            if _resolved_flags:
                _res_lines = [
                    f"- {f['id']}: {flag_resolution_summary(f)}"
                    for f in _resolved_flags
                ]
                _parts.append("Per-flag resolution claims:\n" + "\n".join(_res_lines))
            _revise_ctx = "\n\n".join(_parts)
        _parallel_critique_reduced = False
        if len(active_checks) > 1:
            try:
                worker = run_parallel_critique(state, plan_dir, root=root, model=model, checks=active_checks, effort=_critique_effort)
            except Exception as exc:
                log.warning(
                    "M3A_WARN_PARALLEL_CRITIQUE_FALLBACK parallel critique fallback",
                    exc_info=True,
                )
                print(f"[parallel-critique] Failed, falling back to sequential: {exc}", file=sys.stderr)
                _seq_prompt_kwargs = {"active_checks": list(active_checks), "expected_ids": expected_ids, "revise_context": _revise_ctx, "selection_why": _selection_why} if adaptive_path else None
                worker, agent, mode, refreshed = _pkg._run_worker(
                    "critique",
                    state,
                    plan_dir,
                    args,
                    root=root,
                    resolved=resolved,
                    prompt_kwargs=_seq_prompt_kwargs,
                )
            else:
                agent = agent_type
                _parallel_critique_reduced = True
        else:
            worker, agent, mode, refreshed = _pkg._run_worker(
                "critique",
                state,
                plan_dir,
                args,
                root=root,
                resolved=resolved,
                prompt_kwargs={"active_checks": list(active_checks), "expected_ids": expected_ids, "revise_context": _revise_ctx, "selection_why": _selection_why} if adaptive_path else None,
            )

        # ── T11: Scratch promotion for critique ─────────────────────
        # Prefer valid filled critique_output.json over worker.payload;
        # fall back to worker.payload when scratch is missing/unmodified;
        # fail hard on modified invalid scratch when file-fill was
        # instructed (hermes agent).  Canonical promotion to
        # critique_v{iteration}.json is preserved unchanged below.
        from arnold_pipelines.megaplan.handlers.structured_output import (
            promote_scratch,
            require_scratch_filename_for_phase,
        )

        _scratch_filename = require_scratch_filename_for_phase("critique")
        _seed_path = plan_dir / _scratch_filename
        _seed_json: str | None = None
        if _seed_path.exists():
            try:
                _seed_json = _seed_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                _seed_json = None

        _file_fill_instructed = agent == "hermes"

        if _parallel_critique_reduced:
            _promoted = worker.payload
        else:
            _, _promoted = promote_scratch(
                plan_dir,
                _scratch_filename,
                _critique_scratch_known_keys(),
                worker,
                seed_json=_seed_json,
                file_fill_instructed=_file_fill_instructed,
            )
            worker.payload = _promoted
        # ────────────────────────────────────────────────────────────

        try:
            audit_step_payload("critique", worker.payload)
        except ModelStructuralAuditError as error:
            recovered_payload = _recover_valid_critique_output(plan_dir, expected_ids=expected_ids)
            if recovered_payload is None:
                _raise_step_validation_error(
                    plan_dir=plan_dir,
                    state=state,
                    step="critique",
                    iteration=iteration,
                    worker=worker,
                    code="invalid_critique",
                    message=f"Critique output failed schema audit: {error.details}",
                )
            _append_to_meta(
                state,
                "critique_validation_warnings",
                {"iteration": iteration, "schema_audit_warning": error.details},
            )
            worker = WorkerResult(
                payload=recovered_payload,
                raw_output=worker.raw_output + "\n[megaplan] recovered critique payload from critique_output.json; original worker failed schema audit: " + error.details,
                duration_ms=worker.duration_ms,
                cost_usd=worker.cost_usd,
                session_id=worker.session_id,
                trace_output=worker.trace_output,
                rendered_prompt=worker.rendered_prompt,
                model_actual=worker.model_actual,
                prompt_tokens=worker.prompt_tokens,
                completion_tokens=worker.completion_tokens,
                total_tokens=worker.total_tokens,
            )
        invalid_checks = _critique_check_validator()(worker.payload, expected_ids=expected_ids)
        if invalid_checks:
            recovered_payload = _recover_valid_critique_output(plan_dir, expected_ids=expected_ids)
            if recovered_payload is None:
                _raise_step_validation_error(plan_dir=plan_dir, state=state, step="critique", iteration=iteration, worker=worker, code="invalid_critique", message="Critique output failed check validation: " + ", ".join(invalid_checks))
            _append_to_meta(state, "critique_validation_warnings", {"iteration": iteration, "invalid_checks": invalid_checks})
            worker = _rebuild_recovered_critique_worker(worker, recovered_payload, invalid_checks)
        worker.payload = _filter_critique_payload_to_expected_checks(worker.payload, expected_ids=expected_ids)

        unverifiable_checks = annotate_unverifiable_checks(
            worker.payload,
            check_specs=active_checks,
        )
        unverifiable_warnings = build_unverifiable_warnings(unverifiable_checks)
        if unverifiable_checks:
            _append_to_meta(state, "critique_unverifiable_checks", {
                "iteration": iteration,
                "checks": unverifiable_checks,
                "warnings": unverifiable_warnings,
            })
        for _warning in unverifiable_warnings:
            print(f"[megaplan] WARNING: {_warning}", file=sys.stderr, flush=True)

        from arnold_pipelines.megaplan.audits.capabilities import get_worker_capabilities

        plan_meta = read_json(latest_plan_meta_path(plan_dir, state))
        success_criteria = plan_meta.get("success_criteria", [])
        v_worker_caps = get_worker_capabilities(state)
        v_flags = _build_verifiability_flags(success_criteria, v_worker_caps)
        if v_flags:
            worker.payload.setdefault("flags", []).extend(v_flags)

        try:
            prepare_critique_payload(worker.payload, expected_check_ids=expected_ids)
        except CritiqueCustodyError as error:
            _raise_step_validation_error(
                plan_dir=plan_dir,
                state=state,
                step="critique",
                iteration=iteration,
                worker=worker,
                code=error.code,
                message=str(error),
            )
        atomic_write_text(plan_dir / f"critique_raw_v{iteration}.txt", worker.raw_output or "")
        atomic_write_json(plan_dir / critique_filename, worker.payload)
        try:
            custody_receipt = write_critique_production_receipt(
                plan_dir,
                state,
                worker.payload,
                expected_check_ids=expected_ids,
            )
        except CritiqueCustodyError as error:
            _raise_step_validation_error(
                plan_dir=plan_dir,
                state=state,
                step="critique",
                iteration=iteration,
                worker=worker,
                code=error.code,
                message=str(error),
            )
        if is_creative_mode(state):
            fired = [
                check.get("provocation", {})
                for check in active_checks
                if isinstance(check, dict) and isinstance(check.get("provocation"), dict)
            ]
            voice = next(
                (
                    check.get("provocateur_voice")
                    for check in active_checks
                    if isinstance(check, dict) and check.get("provocateur_voice")
                ),
                None,
            )
            update_directors_notes_at_aggregate(
                plan_dir,
                state,
                {"task_updates": []},
                iteration=iteration,
                voice=voice,
                fired_provocations=fired,
            )
        registry = update_flags_after_critique(
            plan_dir,
            worker.payload,
            iteration=iteration,
            skip_flag_ids=frozenset(_verified_flag_ids_set) if _verified_flag_ids_set else None,
        )
        significant = len([flag for flag in registry["flags"] if flag.get("severity") == "significant" and flag["status"] in FLAG_BLOCKING_STATUSES])
        _append_to_meta(state, "significant_counts", significant)
        recurring = compute_recurring_critiques(plan_dir, iteration)
        _append_to_meta(state, "recurring_critiques", recurring)
        state["current_state"] = STATE_CRITIQUED
        skip_gate = not workflow_includes_step(robustness, "gate")
        if skip_gate:
            minimal_gate: dict[str, Any] = {
                "recommendation": "ITERATE",
                "rationale": "Light robustness: single revision pass to incorporate critique feedback.",
                "signals_assessment": "",
                "warnings": [],
                "settled_decisions": [],
                "passed": False,
                "flag_resolutions": [],
                "accepted_tradeoffs": [],
                "north_star_actions": [],
                "unresolved_flags": [],
                "preflight_results": {},
                "orchestrator_guidance": "Light robustness routes critique to one revision pass.",
            }
            atomic_write_json(plan_dir / "gate.json", minimal_gate)
            _write_gate_carry(plan_dir, minimal_gate, iteration=iteration)
            state["last_gate"] = {"recommendation": "ITERATE"}
        scope_flags_list = scope_creep_flags(registry, statuses=FLAG_BLOCKING_STATUSES)
        open_flags_detail = [
            {"id": flag["id"], "concern": flag["concern"], "category": flag["category"], "severity": flag.get("severity", "unknown")}
            for flag in registry["flags"]
            if flag["status"] == "open"
        ]
        response_fields: dict[str, Any] = {
            "iteration": iteration,
            "checks": worker.payload.get("checks", []),
            "verified_flags": worker.payload.get("verified_flag_ids", []),
            "open_flags": open_flags_detail,
            "scope_creep_flags": [flag["id"] for flag in scope_flags_list],
        }
        if scope_flags_list:
            response_fields["warnings"] = ["Scope creep detected in the plan. Surface this drift to the user while continuing the loop."]
        if unverifiable_checks:
            response_fields["unverifiable_checks"] = unverifiable_checks
            response_fields["warnings"] = [
                *response_fields.get("warnings", []),
                *unverifiable_warnings,
            ]
        return _finish_step(
            plan_dir, state, args,
            step="critique",
            worker=worker, agent=agent, mode=mode, refreshed=refreshed,
            summary=f"Recorded {len(worker.payload.get('flags', []))} critique flags.",
            artifacts=[critique_filename, f"critique_custody_v{iteration}.json", "faults.json"],
            output_file=critique_filename,
            artifact_hash=sha256_file(plan_dir / critique_filename),
            response_fields={
                **response_fields,
                "critique_outcome": CritiqueOutcome.COMPLETED,
                "critique_custody": {
                    "receipt": f"critique_custody_v{iteration}.json",
                    "finding_count": custody_receipt["finding_count"],
                    "loss_count": 0,
                },
            },
            history_fields={"flags_count": len(worker.payload.get("flags", []))},
        )


def _recover_valid_critique_output(plan_dir: Path, *, expected_ids: list[str]) -> dict[str, Any] | None:
    output_path = plan_dir / "critique_output.json"
    if not output_path.exists():
        return None
    payload = read_json(output_path)
    payload = _normalize_critique_payload_for_recovery(payload)
    try:
        audit_step_payload("critique", payload)
    except ModelStructuralAuditError:
        return None
    invalid_checks = _critique_check_validator()(payload, expected_ids=expected_ids)
    if invalid_checks:
        return None
    return _filter_critique_payload_to_expected_checks(payload, expected_ids=expected_ids)


def _filter_critique_payload_to_expected_checks(
    payload: dict[str, Any],
    *,
    expected_ids: list[str],
) -> dict[str, Any]:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return payload
    expected = set(expected_ids)
    filtered_checks = [
        check
        for check in checks
        if not isinstance(check, dict) or check.get("id") in expected
    ]
    if len(filtered_checks) == len(checks):
        return payload
    filtered_payload = dict(payload)
    filtered_payload["checks"] = filtered_checks
    return filtered_payload


def _normalize_critique_payload_for_recovery(payload: dict[str, Any]) -> dict[str, Any]:
    changed = False
    clean_payload = dict(payload)

    flags = payload.get("flags")
    if isinstance(flags, list):
        clean_flags: list[Any] = []
        for flag in flags:
            if not isinstance(flag, dict):
                clean_flags.append(flag)
                continue
            clean_flag = _normalize_critique_recovery_flag(flag)
            if clean_flag != flag:
                changed = True
            clean_flags.append(clean_flag)
        clean_payload["flags"] = clean_flags

    checks = payload.get("checks")
    if not isinstance(checks, list):
        return clean_payload if changed else payload
    clean_checks: list[Any] = []
    for check in checks:
        if not isinstance(check, dict):
            clean_checks.append(check)
            continue
        findings = check.get("findings")
        if not isinstance(findings, list):
            clean_checks.append(check)
            continue
        clean_findings: list[Any] = []
        check_changed = False
        for finding in findings:
            if not isinstance(finding, dict):
                clean_findings.append(finding)
                continue
            clean_findings.append(finding)
        if check_changed:
            check = dict(check)
            check["findings"] = clean_findings
            changed = True
        clean_checks.append(check)
    if not changed:
        return payload
    clean_payload["checks"] = clean_checks
    return clean_payload


def _normalize_critique_recovery_flag(flag: dict[str, Any]) -> dict[str, Any]:
    severity_hint = flag.get("severity_hint")
    if not isinstance(severity_hint, str):
        if severity_hint is None:
            canonical = "uncertain"
        else:
            return flag
    else:
        normalized = severity_hint.strip().lower()
        if normalized in {"likely-significant", "high", "significant", "major", "critical"}:
            canonical = "likely-significant"
        elif normalized in {"likely-minor", "low", "minor", "trivial", "cosmetic"}:
            canonical = "likely-minor"
        elif normalized in {"uncertain", "medium", "moderate", "unknown", ""}:
            canonical = "uncertain"
        else:
            return flag
    if canonical == severity_hint:
        return flag
    clean_flag = dict(flag)
    clean_flag["severity_hint"] = canonical
    return clean_flag


# --------------------------------------------------------------------------- #
# North Star pre-worker revise guard
# --------------------------------------------------------------------------- #
#
# Before the revise worker is invoked, halt through the existing
# ``CliError``/``record_step_failure`` path when a carried North Star action
# cannot be mapped to concrete worker work. The guard is fail-closed: it only
# ever *prevents* a revise run, never enables one. The three halt conditions
# mirror the revise prompt's per-action instructions and the brief:
#
#   * ``add_human_halt`` — the gate explicitly requires a human;
#   * any other unmappable blocking action — its ``action_type`` is not one of
#     the concrete mappable types the revise worker can act on
#     (``change_plan``/``add_gate``/``add_scenario``/``add_checker``/
#     ``dead_delete``);
#   * a schema-blocking (dangerous) category action that carries no concrete
#     mappable target (neither ``plan_refs`` nor ``required_change``), so the
#     worker has nothing concrete to map it to.

# The concrete action types the revise worker can map to plan/scenario/checker
# work. ``add_human_halt`` is intentionally excluded — it is never mappable.
_REVISE_MAPPABLE_NORTH_STAR_ACTION_TYPES: frozenset[str] = frozenset(
    t for t in NORTH_STAR_ACTION_TYPES if t != "add_human_halt"
)


def _carried_north_star_actions(plan_dir: Path) -> list[dict[str, Any]]:
    """Read the normalized North Star actions the revise worker will see.

    Mirrors the revise prompt reader: prefer ``gate_carry.json`` and fall back
    to ``gate.json`` when the carry file is absent or holds no actions. Both
    sources carry *normalized* actions (severity already derived with schema
    authority by the gate artifact builder), so the returned actions can be
    inspected directly with :func:`is_blocking_action` /
    :func:`is_blocking_category`. Missing/malformed payloads yield an empty
    list; the guard is the single fail-closed authority.
    """
    from arnold_pipelines.megaplan.north_star_actions import (
        read_carried_north_star_actions,
    )

    return read_carried_north_star_actions(plan_dir)


def _revise_north_star_halt_actions(
    actions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return the blocking North Star actions that force a pre-worker halt.

    See the module-level comment for the three halt conditions. Advisory actions
    and non-blocking entries are never halt triggers. ``plan_refs`` counts as a
    concrete target only when it holds at least one non-blank string (mirrors
    the post-revise concrete-ref rule); ``required_change`` only when it is a
    non-empty (stripped) string.
    """
    halt: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, Mapping) or not is_blocking_action(action):
            continue
        action_type = action.get("action_type")
        category = action.get("category")
        if action_type == "add_human_halt":
            halt.append(dict(action))
            continue
        if action_type not in _REVISE_MAPPABLE_NORTH_STAR_ACTION_TYPES:
            halt.append(dict(action))
            continue
        if is_blocking_category(category):
            plan_refs = action.get("plan_refs")
            required_change = action.get("required_change")
            has_target = (
                isinstance(plan_refs, list)
                and any(isinstance(ref, str) and ref.strip() for ref in plan_refs)
            ) or (
                isinstance(required_change, str) and bool(required_change.strip())
            )
            if not has_target:
                halt.append(dict(action))
    return halt


def _raise_north_star_revise_halt(
    plan_dir: Path,
    state: PlanState,
    *,
    iteration: int,
    halt_actions: list[dict[str, Any]],
) -> None:
    """Record a revise step failure and raise for an unmappable North Star halt.

    Uses the existing ``CliError``/``record_step_failure`` path (mirroring the
    revise cost-sanity guard), so the halt shows up in history as a normal
    step failure without inventing a new runner state.
    """
    summaries = [
        {
            "id": a.get("id"),
            "category": a.get("category"),
            "action_type": a.get("action_type"),
            "concern": a.get("concern"),
        }
        for a in halt_actions
    ]
    bullet_ids = ", ".join(str(a.get("id")) for a in halt_actions)
    message = (
        "Revise halted before worker invocation: one or more carried North Star "
        f"actions require a human and cannot be mapped to revise work ({bullet_ids}). "
        "Address the halt actions (change the plan/scenario/checker target, or "
        "resolve the human-halt) and re-run gate/revise."
    )
    error = CliError(
        "north_star_revise_human_halt",
        message,
        valid_next=infer_next_steps(state),
        extra={
            "step": "revise",
            "halt_actions": summaries,
            "count": len(halt_actions),
        },
    )
    record_step_failure(
        plan_dir,
        state,
        step="revise",
        iteration=iteration,
        error=error,
        duration_ms=0,
    )
    raise error


def _revise_north_star_unresolved_actions(
    *,
    carried_blocking: Sequence[Mapping[str, Any]],
    addressed: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Return the carried blocking actions that are NOT concretely resolved.

    This is the fail-closed authority for revise closeout (Step 6). A carried
    blocking action is considered resolved only when the worker's
    ``north_star_actions_addressed[]`` contains a record that:

    * links to the carried action by ``action_id`` (not omitted);
    * cites *concrete* plan refs — a non-empty ``plan_refs`` list with at least
      one non-blank string (not prose-only);
    * echoes the carried action's ``action_type`` marker exactly
      (satisfies the required action-type structural marker).

    When *addressed* is ``None`` (the worker payload was malformed) every
    carried blocker is reported as unresolved, mirroring the
    ``_post_revise_gate_allowed`` / ``flags_addressed`` convention that absent
    or incomplete metadata can never stand in for evidence of resolution.
    Advisory actions are never in scope — only carried blocking actions need
    concrete addressing before revise can close.
    """
    # Absent/malformed addressed metadata => all carried blockers unresolved.
    if addressed is None:
        return [
            {
                "id": action.get("id"),
                "action_type": action.get("action_type"),
                "reason": "addressed_metadata_malformed",
            }
            for action in carried_blocking
            if isinstance(action, Mapping)
        ]

    # Index addressed records by normalized action_id (first occurrence wins;
    # a duplicate never strengthens resolution).
    addressed_by_id: dict[str, dict[str, Any]] = {}
    for rec in addressed:
        if not isinstance(rec, Mapping):
            continue
        aid = rec.get("action_id")
        if isinstance(aid, str) and aid.strip():
            addressed_by_id.setdefault(aid.strip(), dict(rec))

    unresolved: list[dict[str, Any]] = []
    for action in carried_blocking:
        if not isinstance(action, Mapping):
            continue
        aid = action.get("id")
        aid_key = aid.strip() if isinstance(aid, str) else None
        record = addressed_by_id.get(aid_key) if aid_key else None

        if record is None:
            unresolved.append(
                {
                    "id": aid,
                    "action_type": action.get("action_type"),
                    "reason": "omitted",
                }
            )
            continue

        plan_refs = record.get("plan_refs")
        has_concrete_refs = isinstance(plan_refs, list) and any(
            isinstance(ref, str) and ref.strip() for ref in plan_refs
        )
        if not has_concrete_refs:
            unresolved.append(
                {
                    "id": aid,
                    "action_type": action.get("action_type"),
                    "reason": "prose_only",
                }
            )
            continue

        carried_type = action.get("action_type")
        addressed_type = record.get("action_type")
        if addressed_type != carried_type:
            unresolved.append(
                {
                    "id": aid,
                    "action_type": carried_type,
                    "addressed_action_type": addressed_type,
                    "reason": "action_type_mismatch",
                }
            )
            continue
    return unresolved


def _raise_north_star_revise_unresolved(
    plan_dir: Path,
    state: PlanState,
    *,
    iteration: int,
    unresolved: list[dict[str, Any]],
    malformed_reason: str | None = None,
    duration_ms: int = 0,
) -> None:
    """Record a revise step failure and raise when carried blocking actions are
    not concretely resolved in the worker output.

    Mirrors ``_raise_north_star_revise_halt``: routes through the existing
    ``CliError`` / ``record_step_failure`` path so the failure surfaces in
    history as a normal step failure without inventing a new runner state.
    """
    summaries = [
        {
            "id": u.get("id"),
            "action_type": u.get("action_type"),
            "reason": u.get("reason"),
        }
        for u in unresolved
    ]
    bullet_ids = ", ".join(str(u.get("id")) for u in unresolved)
    reason_counts: dict[str, int] = {}
    for u in unresolved:
        key = str(u.get("reason"))
        reason_counts[key] = reason_counts.get(key, 0) + 1
    reasons = ", ".join(f"{reason}={count}" for reason, count in reason_counts.items())
    prefix = f"{malformed_reason} " if malformed_reason else ""
    message = (
        f"{prefix}Revise cannot close: {len(unresolved)} carried blocking "
        f"North Star action(s) unresolved ({bullet_ids}) [{reasons}]. Each "
        "blocking action needs a north_star_actions_addressed record with "
        "concrete plan_refs and the matching action_type marker."
    )
    error = CliError(
        "north_star_revise_unresolved_blocking",
        message,
        valid_next=infer_next_steps(state),
        extra={
            "step": "revise",
            "unresolved_actions": summaries,
            "count": len(unresolved),
        },
    )
    record_step_failure(
        plan_dir,
        state,
        step="revise",
        iteration=iteration,
        error=error,
        duration_ms=duration_ms,
    )
    raise error


def handle_revise(root: Path, args: argparse.Namespace) -> StepResponse:
    from arnold_pipelines.megaplan.handlers.gate import (
        _next_progress_step,
        _remaining_significant_flags,
        _resolve_revise_transition,
    )

    with load_plan_locked(root, args.plan, step="revise") as (plan_dir, state):
        require_state(state, "revise", {STATE_CRITIQUED})
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        _has_gate, revise_transition = _resolve_revise_transition(state, plan_dir)
        # Pre-worker North Star guard: halt through the existing CliError /
        # record_step_failure path before spending a worker run when a carried
        # action requires a human, is unmappable, or is a dangerous-category
        # blocker with no concrete target.
        carried_ns_actions = _carried_north_star_actions(plan_dir)
        ns_halt_actions = _revise_north_star_halt_actions(carried_ns_actions)
        if ns_halt_actions:
            _raise_north_star_revise_halt(
                plan_dir,
                state,
                iteration=state["iteration"] + 1,
                halt_actions=ns_halt_actions,
            )
        previous_plan = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
        revise_start_iso = now_utc()
        notes_consumed = [
            n["timestamp"]
            for n in state["meta"].get("notes", [])
            if isinstance(n, dict) and "timestamp" in n
        ]
        worker, agent, mode, refreshed = _pkg._run_worker(
            "revise",
            state,
            plan_dir,
            args,
            root=root,
            iteration=state["iteration"] + 1,
        )
        # Record audit fields on the revise receipt: which notes existed at the
        # moment we ran revise (so a future force-proceed can tell if notes
        # arrived after the last revise) and when revise started.
        worker.receipt_metrics = {
            "start_timestamp_utc": revise_start_iso,
            "notes_consumed": notes_consumed,
            "notes_consumed_count": len(notes_consumed),
        }
        if worker.cost_usd > 5.0:
            error = CliError(
                "revise_cost_sanity_guard",
                "revise cost exceeded $5.00; aborting to avoid a possible session-cache loop. See ticket 01KRXNZZGRV17PHZRJ2Q56SPS3.",
                extra={
                    "step": "revise",
                    "cost_usd": worker.cost_usd,
                    "session_id": worker.session_id,
                    "prompt_tokens": worker.prompt_tokens,
                    "completion_tokens": worker.completion_tokens,
                    "ticket": "01KRXNZZGRV17PHZRJ2Q56SPS3",
                },
            )
            record_step_failure(
                plan_dir,
                state,
                step="revise",
                iteration=state["iteration"] + 1,
                error=error,
                duration_ms=worker.duration_ms,
            )
            raise error
        payload = worker.payload
        audit_step_payload("revise", payload)
        imported_decision_issues = _load_bearing_decision_criteria_issues(
            state,
            payload.get("success_criteria", []),
        )
        if imported_decision_issues:
            _raise_step_validation_error(
                plan_dir=plan_dir,
                state=state,
                step="revise",
                iteration=state["iteration"] + 1,
                worker=worker,
                code="invalid_imported_decision_criteria",
                message=(
                    "Revise output did not mechanically bind every load-bearing "
                    "imported decision: "
                    + "; ".join(imported_decision_issues)
                ),
            )
        payload["success_criteria"] = _merge_imported_decision_criteria(
            state,
            payload.get("success_criteria", []),
        )
        version = state["iteration"] + 1
        plan_text = payload["plan"].rstrip() + "\n"
        delta = compute_plan_delta_percent(previous_plan, plan_text)
        revise_blast_radius = payload.get("test_blast_radius")
        if not isinstance(revise_blast_radius, dict):
            revise_blast_radius = None
        prior_blast_radius = None
        try:
            prior_meta = read_json(latest_plan_meta_path(plan_dir, state)) or {}
            carried = prior_meta.get("test_blast_radius")
            prior_blast_radius = carried if isinstance(carried, dict) else None
        except Exception:
            prior_blast_radius = None
        if revise_blast_radius is not None:
            try:
                revise_blast_radius = _derive_plan_test_blast_radius(
                    plan_dir=plan_dir,
                    state=state,
                    payload=payload,
                )
            except Exception:
                if prior_blast_radius is not None:
                    revise_blast_radius = prior_blast_radius
        elif revise_blast_radius is None:
            revise_blast_radius = prior_blast_radius
        # Step 6: validate carried blocking North Star actions are concretely
        # resolved in the worker output, then persist the normalized
        # north_star_actions_addressed[] beside the revise metadata. Fail
        # closed (record_step_failure -> CliError, no new runner state) when a
        # carried blocking action is omitted, prose-only (no concrete
        # plan_refs), structurally malformed, or mismatches the required
        # action_type marker. Absent/malformed addressed metadata is treated as
        # all-carried-blocking-unresolved, mirroring the flags_addressed /
        # _post_revise_gate_allowed convention (SD1).
        carried_blocking = blocking_north_star_actions(carried_ns_actions)
        raw_addressed = payload.get("north_star_actions_addressed")
        addressed_malformed_reason: str | None = None
        try:
            normalized_addressed = normalize_north_star_actions_addressed(
                raw_addressed
            )
        except NorthStarActionValidationError as exc:
            normalized_addressed = None
            addressed_malformed_reason = (
                f"north_star_actions_addressed[] malformed: {exc};"
            )
        if carried_blocking:
            unresolved_actions = _revise_north_star_unresolved_actions(
                carried_blocking=carried_blocking,
                addressed=normalized_addressed,
            )
            if unresolved_actions:
                _raise_north_star_revise_unresolved(
                    plan_dir,
                    state,
                    iteration=version,
                    unresolved=unresolved_actions,
                    malformed_reason=addressed_malformed_reason,
                )
        revise_meta_fields = {
            "changes_summary": payload["changes_summary"],
            "flags_addressed": payload["flags_addressed"],
            "questions": payload.get("questions", []),
            "success_criteria": payload.get("success_criteria", []),
            "assumptions": payload.get("assumptions", []),
            "delta_from_previous_percent": delta,
            # Persist the (normalized) addressed-action metadata beside revise
            # output so finalize/review can trust it as the closeout contract.
            "north_star_actions_addressed": normalized_addressed or [],
        }
        if revise_blast_radius is not None:
            revise_meta_fields["test_blast_radius"] = revise_blast_radius
        try:
            plan_filename, meta_filename, meta = _write_plan_version(
                plan_dir=plan_dir, state=state, step="revise", version=version,
                worker=worker, plan_filename=f"plan_v{version}.md", plan_text=plan_text,
                meta_fields=revise_meta_fields,
            )
        except CliError as error:
            if error.code == "cache_hit_suspected":
                record_step_failure(
                    plan_dir,
                    state,
                    step="revise",
                    iteration=version,
                    error=error,
                    duration_ms=worker.duration_ms,
                )
            raise
        state["iteration"], state["current_state"] = version, revise_transition.next_state
        state["meta"].pop("user_approved_gate", None)
        if _has_gate:
            state["last_gate"] = {}
        state["plan_versions"].append({
            "version": version, "file": plan_filename,
            "hash": meta["hash"], "timestamp": meta["timestamp"],
        })
        _append_to_meta(state, "plan_deltas", delta)
        update_flags_after_revise(plan_dir, payload["flags_addressed"], plan_file=plan_filename, summary=payload["changes_summary"])
        next_step = _next_progress_step(state)
        remaining = _remaining_significant_flags(plan_dir)
        return _finish_step(
            plan_dir, state, args,
            step="revise",
            worker=worker, agent=agent, mode=mode, refreshed=refreshed,
            summary=f"Updated plan to v{version}; addressed {len(payload['flags_addressed'])} flags.",
            artifacts=[plan_filename, meta_filename, "faults.json"],
            output_file=plan_filename,
            artifact_hash=meta["hash"],
            next_step=next_step,
            response_fields={
                "iteration": version,
                "changes_summary": payload["changes_summary"],
                "flags_addressed": payload["flags_addressed"],
                "flags_remaining": remaining,
                "plan_delta_percent": delta,
                "revise_outcome": ReviseOutcome.COMPLETED,
            },
            history_fields={"flags_addressed": payload["flags_addressed"]},
        )

def _validate_tiebreaker(
    state: PlanState,
    gate_summary: dict[str, Any],
    plan_dir: Path,
    worker: WorkerResult,
    args: argparse.Namespace,
    agent: str,
    resolved: tuple,
    signals_artifact: dict[str, Any],
    gate_signals: dict[str, Any],
    root: Path,
) -> tuple[str, str, str]:
    """Validate a TIEBREAKER gate recommendation. Returns (result, next_step, summary)."""
    from arnold_pipelines.megaplan.audits.iteration import compute_iteration_pressure, has_mechanical_recurrence
    from arnold_pipelines.megaplan.handlers.gate import _merge_gate_worker_attempt

    config = state.get("config", {})
    summary_base = f"Gate recommendation TIEBREAKER: {gate_summary['rationale']}"

    if not config.get("allow_tiebreaker", True):
        gate_summary["recommendation"] = "ITERATE"
        gate_summary["rationale"] += " [Auto-downgraded: tiebreaker disabled for this plan]"
        state["current_state"] = STATE_CRITIQUED
        return "tiebreaker_rejected_disabled", "revise", summary_base

    tiebreaker_count = state["meta"].get("tiebreaker_count", 0)
    max_tiebreakers = config.get("max_tiebreakers_per_plan", 2)
    if tiebreaker_count >= max_tiebreakers:
        gate_summary["recommendation"] = "ESCALATE"
        gate_summary["rationale"] += " [Auto-downgraded to ESCALATE: tiebreaker budget exhausted]"
        state["current_state"] = STATE_CRITIQUED
        return "tiebreaker_rejected_budget", "override add-note", summary_base

    blocklist = config.get("tiebreaker_blocklist", [])
    tiebreaker_flag_ids = gate_summary.get("tiebreaker_flag_ids", [])
    if blocklist and tiebreaker_flag_ids:
        from arnold_pipelines.megaplan._core import load_flag_registry as _load_flag_registry
        registry = _load_flag_registry(plan_dir)
        flag_by_id = {f["id"]: f for f in registry.get("flags", [])}
        for fid in tiebreaker_flag_ids:
            flag = flag_by_id.get(fid, {})
            if flag.get("category", "") in blocklist:
                gate_summary["recommendation"] = "ITERATE"
                gate_summary["rationale"] += f" [Auto-downgraded: flag {fid} category in tiebreaker blocklist]"
                state["current_state"] = STATE_CRITIQUED
                return "tiebreaker_rejected_blocklist", "revise", summary_base

    required_fields = ("tiebreaker_question", "tiebreaker_flag_ids", "tiebreaker_fuzzy_group_id")
    missing = [f for f in required_fields if not gate_summary.get(f)]
    if missing:
        gate_summary["recommendation"] = "ITERATE"
        gate_summary["rationale"] += (
            f" [TIEBREAKER_DOWNGRADED_MISSING_FIELDS: missing required fields {missing}]"
        )
        state["current_state"] = STATE_CRITIQUED
        return "tiebreaker_rejected_missing_fields", "revise", summary_base

    entries = compute_iteration_pressure(plan_dir, state)
    if not has_mechanical_recurrence(entries):
        reprompt_prompt = _build_tiebreaker_reprompt(agent, state, plan_dir, root=root)
        retry_worker, _, _, _ = _pkg._run_worker(
            "gate", state, plan_dir, args, root=root,
            resolved=resolved, prompt_override=reprompt_prompt,
        )
        worker = _merge_gate_worker_attempt(worker, retry_worker)
        retry_payload = worker.payload
        if retry_payload.get("recommendation") == "TIEBREAKER":
            entries_retry = compute_iteration_pressure(plan_dir, state)
            if not has_mechanical_recurrence(entries_retry):
                gate_summary["recommendation"] = "ITERATE"
                gate_summary["rationale"] += " [Auto-downgraded: no mechanical recurrence signal after reprompt]"
                state["current_state"] = STATE_CRITIQUED
                return "tiebreaker_rejected_no_signal", "revise", summary_base
        else:
            gate_summary["recommendation"] = retry_payload.get("recommendation", "ITERATE")
            gate_summary["rationale"] = retry_payload.get("rationale", gate_summary["rationale"])
            guidance = build_orchestrator_guidance(
                gate_payload=retry_payload,
                signals=signals_artifact["signals"],
                preflight_passed=all(signals_artifact["preflight_results"].values()),
                preflight_results=signals_artifact["preflight_results"],
                robustness=signals_artifact.get("robustness", "standard"),
                plan_name=state["name"],
                strict_notes=bool(state["config"].get("strict_notes", False)),
            )
            new_summary = build_gate_artifact(
                signals_artifact, retry_payload,
                override_forced=False, orchestrator_guidance=guidance,
            )
            gate_summary.update(new_summary)
            state["current_state"] = STATE_CRITIQUED
            if gate_summary["recommendation"] == "PROCEED" and gate_summary.get("passed"):
                state["current_state"] = STATE_GATED
                return "success", "finalize", f"Gate recommendation {gate_summary['recommendation']}: {gate_summary['rationale']}"
            return "success", "revise", f"Gate recommendation {gate_summary['recommendation']}: {gate_summary['rationale']}"

    state["current_state"] = STATE_TIEBREAKER_PENDING
    state["meta"]["tiebreaker_count"] = tiebreaker_count + 1
    return "tiebreaker_approved", "tiebreaker-run", summary_base


from arnold_pipelines.megaplan.flags import apply_flag_verifications, update_flags_after_critique, update_flags_after_revise
