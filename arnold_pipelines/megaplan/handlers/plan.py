from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan import handlers as _pkg
from arnold_pipelines.megaplan.outcomes import PrepOutcome
from arnold_pipelines.megaplan.types import CliError, MOCK_ENV_VAR, StepResponse
from arnold_pipelines.megaplan.planning.state import STATE_AWAITING_HUMAN, STATE_INITIALIZED, STATE_PLANNED, STATE_PREPPED
from arnold_pipelines.megaplan._core import (
    clear_active_step,
    load_plan_locked,
    read_json,
    require_state,
    save_state_merge_meta,
    set_active_step,
)

from .shared import (
    _finish_step,
    _merge_imported_decision_criteria,
    _write_json_artifact,
    _write_plan_version,
    activate_phase_wbc,
    phase_result_guard,
)


def _build_prep_clarify_signal(state: dict, payload: dict) -> dict[str, Any]:
    """Return a structured clarify signal for prep without naming route targets."""
    if not state["config"].get("prep_clarify", True):
        return {"decision": "continue", "suspend": False}
    open_questions = payload.get("open_questions") or []
    blocking = [q for q in open_questions if isinstance(q, dict) and q.get("severity") == "blocking"]
    if not blocking:
        return {"decision": "continue", "suspend": False}
    n = len(blocking)
    return {
        "decision": "clarify",
        "suspend": True,
        "clarification": {
            "intent_summary": (
                f"prep surfaced {n} blocking {'ambiguity' if n == 1 else 'ambiguities'}; "
                "answer and run `megaplan override resume-clarify`"
            ),
            "questions": [f"[blocking] {q['question']}" for q in blocking],
            "source": "prep",
        },
    }


def _apply_prep_signal(state: dict[str, Any], prep_signal: dict[str, Any]) -> str:
    """Persist the prep signal into state while leaving route ownership external."""
    clarification = prep_signal.get("clarification")
    if prep_signal.get("suspend"):
        if isinstance(clarification, dict):
            state["clarification"] = clarification
        return STATE_AWAITING_HUMAN
    state.pop("clarification", None)
    return STATE_PREPPED


def _criteria_require_tests(success_criteria: list[dict[str, Any]]) -> bool:
    for criterion in success_criteria:
        if not isinstance(criterion, dict):
            continue
        requires = criterion.get("requires")
        if isinstance(requires, list) and "run_tests" in requires:
            return True
    return False


def _prep_relevant_code_surfaces(plan_dir: Path) -> list[str]:
    try:
        prep = read_json(plan_dir / "prep.json")
    except Exception:
        return []
    if not isinstance(prep, dict):
        return []
    relevant_code = prep.get("relevant_code")
    if not isinstance(relevant_code, list):
        return []
    surfaces: list[str] = []
    for item in relevant_code:
        if not isinstance(item, dict):
            continue
        file_path = item.get("file_path")
        if isinstance(file_path, str) and file_path.strip():
            surfaces.append(file_path.strip())
    return surfaces


def _derive_plan_test_blast_radius(
    *,
    plan_dir: Path,
    state: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if state["config"].get("mode", "code") != "code":
        return None

    from arnold_pipelines.megaplan.orchestration.test_selection import (
        compute_default_blast_radius,
        merge_blast_radius_floor,
        sanitize_blast_radius_paths,
    )

    repo_root = Path(state["config"]["project_dir"])
    changed_surfaces = payload.get("changed_surfaces")
    if not isinstance(changed_surfaces, list):
        model_proposed = payload.get("test_blast_radius")
        if isinstance(model_proposed, dict):
            proposed_changed_surfaces = model_proposed.get("changed_surfaces")
            if isinstance(proposed_changed_surfaces, list):
                changed_surfaces = proposed_changed_surfaces
    if not isinstance(changed_surfaces, list):
        changed_surfaces = _prep_relevant_code_surfaces(plan_dir)
    changed_surfaces = [
        surface.strip()
        for surface in changed_surfaces
        if isinstance(surface, str) and surface.strip()
    ]

    deterministic_floor = compute_default_blast_radius(changed_surfaces, repo_root)
    if (
        deterministic_floor.get("strategy") == "none"
        and _criteria_require_tests(payload.get("success_criteria", []))
    ):
        deterministic_floor = {
            **deterministic_floor,
            "strategy": "full",
            "confidence": "low",
            "rationale": (
                str(deterministic_floor.get("rationale") or "")
                + " Success criteria require tests, but the plan did not declare "
                "any concrete changed_surfaces; revise must add scoped metadata or "
                "explicitly opt into full-suite validation."
            ).strip(),
        }

    model_proposed = payload.get("test_blast_radius")
    if isinstance(model_proposed, dict):
        final_blast_radius = merge_blast_radius_floor(
            deterministic_floor,
            model_proposed,
        )
    else:
        final_blast_radius = deterministic_floor

    if final_blast_radius is not None:
        final_blast_radius = sanitize_blast_radius_paths(final_blast_radius, repo_root)
    if final_blast_radius is not None and "changed_surfaces" not in final_blast_radius:
        final_blast_radius["changed_surfaces"] = list(changed_surfaces)
    return final_blast_radius


def handle_plan(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="plan") as (plan_dir, state):
        require_state(state, "plan", {STATE_INITIALIZED, STATE_PREPPED, STATE_PLANNED})
        if state["config"].get("mode") == "joke" and not state["config"].get("primary_criterion"):
            raise CliError(
                "invalid_state",
                "joke mode requires a primary_criterion — declare via --primary-criterion or in the prep brief",
            )
        with phase_result_guard(plan_dir):
            rerun = state["current_state"] == STATE_PLANNED
            version = state["iteration"] if rerun else state["iteration"] + 1
            worker, agent, mode, refreshed = _pkg._run_worker(
                "plan",
                state,
                plan_dir,
                args,
                root=root,
                iteration=version,
            )
            payload = worker.payload
            payload["success_criteria"] = _merge_imported_decision_criteria(
                state,
                payload["success_criteria"],
            )
            meta_fields: dict[str, Any] = {
                "questions": payload["questions"],
                "success_criteria": payload["success_criteria"],
                "assumptions": payload["assumptions"],
            }
            final_blast_radius = _derive_plan_test_blast_radius(
                plan_dir=plan_dir,
                state=state,
                payload=payload,
            )
            if final_blast_radius is not None:
                meta_fields["test_blast_radius"] = final_blast_radius
            plan_filename, meta_filename, meta = _write_plan_version(
                plan_dir=plan_dir,
                state=state,
                step="plan",
                version=version,
                worker=worker,
                plan_text=payload["plan"].rstrip() + "\n",
                meta_fields=meta_fields,
            )
            state["iteration"], state["current_state"] = version, STATE_PLANNED
            state["meta"].pop("user_approved_gate", None)
            state["last_gate"] = {}
            state["plan_versions"].append({
                "version": version, "file": plan_filename,
                "hash": meta["hash"], "timestamp": meta["timestamp"],
            })
            verb = "Refined" if rerun else "Generated"
            return _finish_step(
                plan_dir, state, args,
                step="plan",
                worker=worker, agent=agent, mode=mode, refreshed=refreshed,
                summary=f"{verb} plan v{version} with {len(payload['questions'])} questions and {len(payload['success_criteria'])} success criteria.",
                artifacts=[plan_filename, meta_filename],
                output_file=plan_filename,
                artifact_hash=meta["hash"],
                response_fields={
                    "iteration": version,
                    "questions": payload["questions"],
                    "assumptions": payload["assumptions"],
                    "success_criteria": payload["success_criteria"],
                },
            )

def handle_prep(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="prep") as (plan_dir, state):
        require_state(state, "prep", {STATE_INITIALIZED})
        prep_direction_arg = getattr(args, "prep_direction", None)
        if prep_direction_arg is not None:
            new_direction = str(prep_direction_arg).strip()
            if not new_direction:
                raise CliError("invalid_args", "--direction must be non-empty when provided")
            state["config"]["prep_direction"] = new_direction
        with phase_result_guard(plan_dir):
            prep_filename = "prep.json"
            if os.getenv(MOCK_ENV_VAR) == "1":
                worker, agent, mode, refreshed = _pkg._run_worker("prep", state, plan_dir, args, root=root)
                artifact_hash = _write_json_artifact(plan_dir, prep_filename, worker.payload)
                if state["config"].get("mode") == "joke" and not state["config"].get("primary_criterion"):
                    primary_criterion = worker.payload.get("primary_criterion")
                    if isinstance(primary_criterion, str) and primary_criterion.strip():
                        state["config"]["primary_criterion"] = primary_criterion.strip()
                code_refs = len(worker.payload.get("relevant_code", []))
                test_refs = len(worker.payload.get("test_expectations", []))
                prep_signal = _build_prep_clarify_signal(state, worker.payload)
                next_state = _apply_prep_signal(state, prep_signal)
                state["current_state"] = next_state
                prep_outcome = PrepOutcome.AWAITING_HUMAN if next_state == STATE_AWAITING_HUMAN else PrepOutcome.CONTINUE
                if next_state == STATE_AWAITING_HUMAN:
                    blocking_count = len(state["clarification"]["questions"])
                    summary = (
                        f"Prep halted: {blocking_count} blocking "
                        f"{'question' if blocking_count == 1 else 'questions'} require clarification before planning can proceed."
                    )
                else:
                    summary = f"Prep complete: captured {code_refs} relevant code reference(s) and {test_refs} test expectation(s)."
                return _finish_step(
                    plan_dir, state, args,
                    step="prep",
                    worker=worker, agent=agent, mode=mode, refreshed=refreshed,
                    summary=summary,
                    artifacts=[prep_filename],
                    output_file=prep_filename,
                    artifact_hash=artifact_hash,
                    response_fields={
                        "iteration": state["iteration"],
                        "prep_signal": prep_signal,
                        "prep_outcome": prep_outcome,
                    },
                )
            from arnold_pipelines.megaplan.orchestration.prep_research import (
                run_prep_orchestration,
            )

            run_id = set_active_step(state, step="prep", agent="prep-orchestration", mode="orchestrated")
            try:
                activate_phase_wbc(state=state, plan_dir=plan_dir, step="prep", agent="prep-orchestration")
                save_state_merge_meta(plan_dir, state)
                orchestration = run_prep_orchestration(state, plan_dir, root=root)
            except Exception:
                clear_active_step(state, run_id=run_id)
                save_state_merge_meta(plan_dir, state)
                raise
            worker = orchestration.worker
            artifact_hash = _write_json_artifact(plan_dir, prep_filename, worker.payload)
            if state["config"].get("mode") == "joke" and not state["config"].get("primary_criterion"):
                primary_criterion = worker.payload.get("primary_criterion")
                if isinstance(primary_criterion, str) and primary_criterion.strip():
                    state["config"]["primary_criterion"] = primary_criterion.strip()
            prep_signal = _build_prep_clarify_signal(state, worker.payload)
            next_state = _apply_prep_signal(state, prep_signal)
            state["current_state"] = next_state
            prep_outcome = PrepOutcome.AWAITING_HUMAN if next_state == STATE_AWAITING_HUMAN else PrepOutcome.CONTINUE
            if next_state == STATE_AWAITING_HUMAN:
                blocking_count = len(state["clarification"]["questions"])
                summary = (
                    f"Prep halted: {blocking_count} blocking "
                    f"{'question' if blocking_count == 1 else 'questions'} require clarification before planning can proceed."
                )
            else:
                summary = orchestration.summary
            return _finish_step(
                plan_dir, state, args,
                step="prep",
                worker=worker,
                agent=orchestration.agent,
                mode=orchestration.mode,
                refreshed=orchestration.refreshed,
                summary=summary,
                artifacts=orchestration.artifacts,
                output_file=prep_filename,
                artifact_hash=artifact_hash,
                response_fields={
                    "iteration": state["iteration"],
                    "prep_metrics_hash": orchestration.prep_metrics_hash,
                    "prep_signal": prep_signal,
                    "prep_outcome": prep_outcome,
                },
                run_id=run_id,
            )

def _build_verifiability_flags(
    success_criteria: list[dict[str, Any]],
    worker_caps: dict[str, set[str]],
) -> list[dict[str, Any]]:
    from arnold_pipelines.megaplan.audits.capabilities import ALL_CAPABILITIES
    from arnold_pipelines.megaplan.orchestration.verifiability import audit_criteria, validate_requires

    flags: list[dict[str, Any]] = []
    issues = validate_requires(success_criteria)
    for issue_str in issues:
        is_unknown_cap = "unknown capability" in issue_str
        flags.append({
            "id": f"verifiability-{len(flags)}",
            "concern": issue_str,
            "category": "verifiability",
            "severity_hint": "likely-significant" if is_unknown_cap else "likely-minor",
            "status": "open",
        })

    audits = audit_criteria(success_criteria, worker_caps)
    for audit in audits:
        if audit.verdict == "unverifiable_no_worker":
            flags.append({
                "id": f"verifiability-{len(flags)}",
                "concern": f"Criterion {audit.criterion_idx}: {audit.rationale} Missing: {', '.join(audit.missing_caps)}",
                "category": "verifiability",
                "severity_hint": "likely-significant",
                "status": "open",
            })
        elif audit.verdict == "human_only":
            flags.append({
                "id": f"verifiability-{len(flags)}",
                "concern": f"Criterion {audit.criterion_idx}: requires human verification ({', '.join(audit.missing_caps)}).",
                "category": "verifiability",
                "severity_hint": "likely-minor",
                "status": "open",
            })

    return flags
