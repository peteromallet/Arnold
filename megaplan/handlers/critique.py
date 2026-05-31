from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

from megaplan import handlers as _pkg
from megaplan.audits.robustness import validate_critique_checks
from megaplan.forms.provocations import select_active_checks
from megaplan.forms.directors_notes import update_directors_notes_at_aggregate
from megaplan.orchestration.evaluation import build_gate_artifact, build_gate_signals, build_orchestrator_guidance, compute_plan_delta_percent, compute_recurring_critiques
from megaplan.orchestration.parallel_critique import run_parallel_critique
from megaplan.profiles import apply_profile_expansion
from megaplan.types import (
    CliError,
    FLAG_BLOCKING_STATUSES,
    PlanState,
    STATE_CRITIQUED,
    STATE_GATED,
    STATE_PLANNED,
    STATE_TIEBREAKER_PENDING,
    StepResponse,
)
from megaplan.workers import WorkerResult, validate_payload
from megaplan._core import (
    adaptive_critique_enabled,
    atomic_write_json,
    configured_robustness,
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

from .plan import _build_verifiability_flags, _merge_imported_decision_criteria
from .shared import _agent_mode_parts, _append_to_meta, _finish_step, _raise_step_validation_error, _write_plan_version
from .tiebreaker import _build_tiebreaker_reprompt

log = logging.getLogger("megaplan")

def handle_critique(root: Path, args: argparse.Namespace) -> StepResponse:
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
            from megaplan.audits.critique_evaluator import validate_evaluator_verdict
            from megaplan.audits.robustness import CRITIQUE_CHECKS

            from megaplan.types import AgentMode as _AgentMode

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
                from megaplan.audits.iteration import compute_iteration_pressure as _compute_iteration_pressure
                from megaplan.prompts.critique import _plan_version_unified_diff

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
                    eval_worker, _, _, _ = _pkg._run_worker(
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
        # Operator pin: when execution.critic_model is set, the evaluator still
        # selects which lenses fire, but every farmed-out critic is forced to
        # the pinned model instead of the complexity-based tier routing
        # (tier_models.critique). "" leaves tier-based routing in force.
        if adaptive_path:
            _pin = pinned_critic_model(state)
            if _pin:
                critic_model_override = _pin
            else:
                # No operator pin: resolve per-check AgentMode from
                # tier_models.critique (complexity-based routing, SD1).
                # Cache complexity → AgentMode to avoid redundant resolution
                # when multiple checks share the same complexity tier.
                _tier_models = getattr(args, "tier_models", None)
                if isinstance(_tier_models, dict):
                    _critique_tiers = _tier_models.get("critique")
                    if isinstance(_critique_tiers, dict) and _critique_tiers:
                        from megaplan.execute.batch import _resolve_tier_spec
                        from megaplan.types import AgentMode as _TierAgentMode

                        _complexity_cache: dict[int, _TierAgentMode] = {}
                        for _check in active_checks:
                            _cid = _check.get("id", "?")
                            _cx = _check.get("complexity")
                            if not isinstance(_cx, int) or _cx < 1 or _cx > 5:
                                raise CliError(
                                    "critique_complexity_invariant",
                                    f"Check '{_cid}' has missing or invalid "
                                    f"complexity ({_cx!r}); cannot resolve tier "
                                    "routing. This is an invariant error in "
                                    "the evaluator output.",
                                )
                            if _cx not in _complexity_cache:
                                _spec = _critique_tiers.get(_cx)
                                if not _spec:
                                    raise CliError(
                                        "critique_tier_missing",
                                        f"No tier spec for complexity {_cx} "
                                        f"in tier_models.critique; cannot "
                                        f"route check '{_cid}'.",
                                    )
                                (
                                    _t_agent,
                                    _t_mode,
                                    _t_model,
                                ) = _resolve_tier_spec(
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
                            # Attach resolved AgentMode to check metadata (SD1)
                            _check["_resolved_agent_mode"] = _complexity_cache[_cx]
        from megaplan.types import AgentMode as _AgentMode

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
            from megaplan.audits.critique_evaluator import roster_dispatch_spec
            from megaplan.types import parse_agent_spec

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
        # Compute revise_context for adaptive path iterations >= 2
        _revise_ctx = ""
        if adaptive_path and iteration >= 2:
            from megaplan.prompts.critique import _plan_version_unified_diff
            from megaplan.flags import flag_resolution_summary

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
        invalid_checks = validate_critique_checks(worker.payload, expected_ids=expected_ids)
        if invalid_checks:
            recovered_payload = _recover_valid_critique_output(plan_dir, expected_ids=expected_ids)
            if recovered_payload is None:
                _raise_step_validation_error(plan_dir=plan_dir, state=state, step="critique", iteration=iteration, worker=worker, code="invalid_critique", message="Critique output failed check validation: " + ", ".join(invalid_checks))
            _append_to_meta(state, "critique_validation_warnings", {"iteration": iteration, "invalid_checks": invalid_checks})
            worker = WorkerResult(
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
            )


        from megaplan.audits.capabilities import get_worker_capabilities

        plan_meta = read_json(latest_plan_meta_path(plan_dir, state))
        success_criteria = plan_meta.get("success_criteria", [])
        v_worker_caps = get_worker_capabilities(state)
        v_flags = _build_verifiability_flags(success_criteria, v_worker_caps)
        if v_flags:
            worker.payload.setdefault("flags", []).extend(v_flags)

        atomic_write_json(plan_dir / critique_filename, worker.payload)
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
        return _finish_step(
            plan_dir, state, args,
            step="critique",
            worker=worker, agent=agent, mode=mode, refreshed=refreshed,
            summary=f"Recorded {len(worker.payload.get('flags', []))} critique flags.",
            artifacts=[critique_filename, "faults.json"],
            output_file=critique_filename,
            artifact_hash=sha256_file(plan_dir / critique_filename),
            response_fields=response_fields,
            history_fields={"flags_count": len(worker.payload.get("flags", []))},
        )


def _recover_valid_critique_output(plan_dir: Path, *, expected_ids: list[str]) -> dict[str, Any] | None:
    output_path = plan_dir / "critique_output.json"
    if not output_path.exists():
        return None
    payload = read_json(output_path)
    invalid_checks = validate_critique_checks(payload, expected_ids=expected_ids)
    if invalid_checks:
        return None
    validate_payload("critique", payload)
    return payload


def handle_revise(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="revise") as (plan_dir, state):
        require_state(state, "revise", {STATE_CRITIQUED})
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        _has_gate, revise_transition = _resolve_revise_transition(state, plan_dir)
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
        validate_payload("revise", payload)
        payload["success_criteria"] = _merge_imported_decision_criteria(
            state,
            payload.get("success_criteria", []),
        )
        version = state["iteration"] + 1
        plan_text = payload["plan"].rstrip() + "\n"
        delta = compute_plan_delta_percent(previous_plan, plan_text)
        try:
            plan_filename, meta_filename, meta = _write_plan_version(
                plan_dir=plan_dir, state=state, step="revise", version=version,
                worker=worker, plan_filename=f"plan_v{version}.md", plan_text=plan_text,
                meta_fields={
                    "changes_summary": payload["changes_summary"],
                    "flags_addressed": payload["flags_addressed"],
                    "questions": payload.get("questions", []),
                    "success_criteria": payload.get("success_criteria", []),
                    "assumptions": payload.get("assumptions", []),
                    "delta_from_previous_percent": delta,
                },
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
    from megaplan.audits.iteration import compute_iteration_pressure, has_mechanical_recurrence

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
        from megaplan._core import load_flag_registry as _load_flag_registry
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


from .gate import _merge_gate_worker_attempt, _next_progress_step, _remaining_significant_flags, _resolve_revise_transition, _write_gate_carry
from megaplan.flags import apply_flag_verifications, update_flags_after_critique, update_flags_after_revise
