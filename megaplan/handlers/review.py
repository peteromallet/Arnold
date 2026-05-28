from __future__ import annotations

import argparse
from copy import deepcopy
import logging
import os
from pathlib import Path
from typing import Any

from megaplan import handlers as _pkg
from megaplan.review import checks as review_checks
from megaplan.execute.quality import _check_done_task_evidence
from megaplan.execute.batch import build_monitor_hint
from megaplan.orchestration.evaluation import is_rubber_stamp
from megaplan.execute.merge import _validate_and_merge_batch
from megaplan.prompts import create_claude_prompt, create_codex_prompt, create_hermes_prompt
from megaplan.profiles import apply_profile_expansion
from megaplan.types import (
    MOCK_ENV_VAR,
    CliError,
    PlanState,
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FINALIZED,
    STATE_REVIEWED,
    StepResponse,
    normalize_robustness,
)
from megaplan.workers import (
    WorkerResult,
    validate_payload,
    warn_if_work_dir_differs_from_project_dir,
)
from megaplan._core import (
    append_history,
    apply_session_update,
    atomic_write_json,
    atomic_write_text,
    clear_active_step,
    configured_robustness,
    get_effective,
    is_prose_mode,
    is_creative_mode,
    load_plan_locked,
    make_history_entry,
    now_utc,
    read_json,
    record_step_failure,
    render_final_md,
    require_state,
    save_state,
    save_state_merge_meta,
    set_active_step,
    sha256_file,
)

from .shared import (
    _attach_next_step_runtime,
    _agent_mode_parts,
    _emit_phase_notice,
    _emit_receipt,
    _run_worker,
    _supports_prompt_kwargs,
    attach_agent_fallback,
    worker_module,
)
from megaplan.orchestration.phase_result import _emit_phase_result

"""Review handler — post-execute implementation-evidence pass.

Review runs *after* execute and evaluates implementation evidence,
merged artifacts, and completion quality.  It is the counterpart to
critique (which runs *before* execute and evaluates plan quality).
These two passes are distinct: critique judges the *plan*, review
judges the *work product*.  Do not rename or conflate them.
"""

log = logging.getLogger(__name__)


def _build_review_blocked_message(
    *,
    verdict_count: int,
    total_tasks: int,
    check_count: int,
    total_checks: int,
    missing_reviewer_evidence: list[str],
) -> str:
    if missing_reviewer_evidence:
        return (
            "Blocked: done tasks are missing reviewer evidence_files without a substantive reviewer_verdict ("
            + ", ".join(missing_reviewer_evidence)
            + "). Re-run review to complete."
        )
    return (
        "Blocked: incomplete review coverage "
        f"({verdict_count}/{total_tasks} task verdicts, {check_count}/{total_checks} sense checks). "
        "Re-run review to complete."
    )

def _is_substantive_reviewer_verdict(text: str) -> bool:
    return not is_rubber_stamp(text, strict=True)

def _build_review_prompt_override(
    agent_type: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    pre_check_flags: list[dict[str, Any]],
) -> str:
    if agent_type == "claude":
        return create_claude_prompt("review", state, plan_dir, root=root, pre_check_flags=pre_check_flags)
    if agent_type == "hermes":
        return create_hermes_prompt("review", state, plan_dir, root=root, pre_check_flags=pre_check_flags)
    return create_codex_prompt("review", state, plan_dir, root=root, pre_check_flags=pre_check_flags)

def _merge_review_verdicts(
    worker_payload: dict[str, Any],
    finalize_data: dict[str, Any],
    issues: list[str],
) -> tuple[int, int, int, int, list[str]]:
    """Merge task verdicts and sense check verdicts into finalize_data.

    Returns (verdict_count, total_tasks, check_count, total_checks, missing_evidence).
    """
    tasks_by_id = {task["id"]: task for task in finalize_data.get("tasks", [])}
    verdict_count, total_tasks = _validate_and_merge_batch(
        worker_payload.get("task_verdicts"),
        required_fields=("task_id", "reviewer_verdict", "evidence_files"),
        targets_by_id=tasks_by_id,
        id_field="task_id",
        merge_fields=("reviewer_verdict", "evidence_files"),
        issues=issues,
        validation_label="task_verdicts",
        merge_label="task_verdict",
        incomplete_message=lambda merged, total: f"Incomplete review: {merged}/{total} tasks received a reviewer verdict.",
        nonempty_fields={"reviewer_verdict"},
        array_fields=("evidence_files",),
    )
    sense_checks_by_id = {sc["id"]: sc for sc in finalize_data.get("sense_checks", [])}
    check_count, total_checks = _validate_and_merge_batch(
        worker_payload.get("sense_check_verdicts"),
        required_fields=("sense_check_id", "verdict"),
        targets_by_id=sense_checks_by_id,
        id_field="sense_check_id",
        merge_fields=("verdict",),
        issues=issues,
        validation_label="sense_check_verdicts",
        merge_label="sense_check_verdict",
        incomplete_message=lambda merged, total: f"Incomplete review: {merged}/{total} sense checks received a verdict.",
        nonempty_fields={"verdict"},
    )
    missing_evidence = _check_done_task_evidence(
        finalize_data.get("tasks", []),
        issues=issues,
        should_classify=lambda task: bool(task.get("reviewer_verdict", "").strip()),
        has_evidence=lambda task: bool(task.get("evidence_files")),
        has_advisory_evidence=lambda task: _is_substantive_reviewer_verdict(task.get("reviewer_verdict", "")),
        missing_message="Done tasks missing reviewer evidence_files without a substantive reviewer_verdict: ",
        advisory_message="Advisory: done tasks rely on substantive reviewer_verdict without evidence_files (FLAG-006 softening): ",
    )
    return verdict_count, total_tasks, check_count, total_checks, missing_evidence


def _maker_requested_stop(plan_dir: Path) -> dict[str, str] | None:
    finalize_path = plan_dir / "finalize.json"
    if not finalize_path.exists():
        return None
    try:
        finalize_data = read_json(finalize_path)
    except (OSError, ValueError):
        return None
    for task in finalize_data.get("tasks", []):
        if not isinstance(task, dict):
            continue
        stop_signal = task.get("stop_signal")
        if isinstance(stop_signal, dict) and stop_signal.get("requested") is True:
            return {"defense": str(stop_signal.get("defense", "")).strip()}
    return None


def _record_maker_stop(state: PlanState, plan_dir: Path, *, defense: str) -> None:
    note = f"Maker stop honored: {defense or 'No defense supplied.'}"
    state.setdefault("meta", {}).setdefault("notes", []).append(
        {"timestamp": now_utc(), "note": note}
    )
    notes_path = plan_dir / "directors_notes.json"
    if not notes_path.exists():
        return
    try:
        notes = read_json(notes_path)
    except (OSError, ValueError):
        return
    passes = notes.get("passes", [])
    if isinstance(passes, list) and passes:
        last_pass = passes[-1]
        if isinstance(last_pass, dict):
            last_pass["stop_requested"] = True
            last_pass["stop_defense"] = defense
            atomic_write_json(notes_path, notes)


def _resolve_review_outcome(
    plan_dir: Path,
    review_verdict: str,
    verdict_count: int,
    total_tasks: int,
    check_count: int,
    total_checks: int,
    missing_evidence: list[str],
    robustness: str,
    state: PlanState,
    issues: list[str],
    criteria: list[dict[str, Any]] | None = None,
) -> tuple[str, str, str | None]:
    """Determine review result, next state, and next step.

    Returns (result, next_state, next_step).
    """
    robustness = normalize_robustness(robustness)
    blocked = (
        verdict_count < total_tasks
        or check_count < total_checks
        or bool(missing_evidence)
    )
    if blocked:
        return "blocked", STATE_EXECUTED, "review"

    rework_requested = review_verdict == "needs_rework"
    if rework_requested:
        if is_creative_mode(state):
            stop_data = _maker_requested_stop(plan_dir)
            if stop_data is not None:
                _record_maker_stop(state, plan_dir, defense=stop_data.get("defense", ""))
                return "success", STATE_DONE, None
        cap_key = (
            "max_robust_review_rework_cycles"
            if robustness in {"thorough", "extreme"}
            else "max_review_rework_cycles"
        )
        max_review_rework_cycles = get_effective("execution", cap_key)
        prior_rework_count = sum(
            1 for entry in state.get("history", [])
            if entry.get("step") == "review" and entry.get("result") == "needs_rework"
        )
        if prior_rework_count >= max_review_rework_cycles:
            issues.append(
                f"Max review rework cycles ({max_review_rework_cycles}) reached. "
                "Force-proceeding to done despite unresolved review issues."
            )
        else:
            return "needs_rework", STATE_FINALIZED, "execute"

    if criteria:
        has_deferred_must = any(
            c.get("pass") == "deferred_human" and c.get("priority") == "must"
            for c in criteria
        )
        if has_deferred_must:
            # STATE_AWAITING_HUMAN_VERIFY is intentionally NOT modified for with_feedback.
            # When deferred_must criteria require human verification, the plan is not
            # considered complete yet — scaffolding feedback.md would be misleading
            # because the user still needs to verify. Feedback scaffolding is deferred
            # until the plan actually reaches done (via the existing interactive
            # 'megaplan feedback edit' path after verification).
            return "success", STATE_AWAITING_HUMAN_VERIFY, None

    with_feedback = state.get("config", {}).get("with_feedback", False)
    return "success", STATE_REVIEWED if with_feedback else STATE_DONE, None


def _format_review_success_summary(criteria: list[dict[str, Any]]) -> str:
    passed = sum(1 for c in criteria if c.get("pass") in (True, "pass"))
    total = len(criteria)
    waived = sum(1 for c in criteria if c.get("pass") == "waived")
    deferred = sum(1 for c in criteria if c.get("pass") == "deferred_human")
    failed = sum(1 for c in criteria if c.get("pass") in (False, "fail"))
    details: list[str] = []
    if waived:
        details.append(f"{waived} waived")
    if deferred:
        details.append(f"{deferred} deferred to human")
    if failed:
        details.append(f"{failed} failed but non-blocking")
    if details:
        return (
            f"Review complete: {passed}/{total} success criteria passed "
            f"({', '.join(details)})."
        )
    return f"Review complete: {passed}/{total} success criteria passed."


_EXPECTED_BY_CHECK_ID = {
    "coverage": "Extend the fix so every concrete failing example, symptom, or 'X should Y' statement in the issue is addressed by at least one diff line.",
    "placement": "Move the fix upstream to where the bad state is first introduced, or extend it to cover any alternate entry points identified in the finding.",
    "adjacent_calls": "Apply the same fix to each additional call site, sibling class, or downstream consumer identified in the finding.",
    "simplicity": "Remove unjustified changes, or justify each extra line against a concrete issue requirement.",
}

def _synthesize_review_rework_items(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rework_items: list[dict[str, Any]] = []
    for check in checks:
        check_id = check.get("id", "")
        if not isinstance(check_id, str) or not check_id:
            continue
        check_def = review_checks.get_check_by_id(check_id)
        if getattr(check_def, "default_severity", "") != "likely-significant":
            continue
        question = str(check.get("question", "") or "").strip()
        findings = check.get("findings", [])
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, dict) or not finding.get("flagged"):
                continue
            status = str(finding.get("status", "") or "").strip().lower()
            # megaplan/prompts/review.py:243-249 constrains status to {blocking, significant, minor, n/a};
            # significant is the explicit non-blocking downgrade for gate-settled concerns, while missing or
            # empty status means the model failed to classify, so we keep the check's default_severity gate as
            # the blocking fallback. That is the safe default for the sympy-21930 / sphinx-9711 regressions.
            if status and status != "blocking":
                continue
            detail = str(finding.get("detail", "") or "").strip()
            evidence_file = finding.get("evidence_file", "")
            if not isinstance(evidence_file, str):
                evidence_file = ""
            issue = detail or question or f"Heavy review found a blocking {check_id} issue."
            # Prefer a per-check actionable expected string; fall back to the
            # check's self-question; ultimately fall back to a generic message.
            expected = (
                _EXPECTED_BY_CHECK_ID.get(check_id)
                or question
                or f"Review check '{check_id}' should pass without blocking findings."
            )
            # `actual` should NOT duplicate `issue` — use a templated
            # acknowledgment of the finding instead so the executor sees
            # a clear "you didn't resolve it" signal without a copy of
            # the detail text.
            actual = f"The diff did not resolve the flagged {check_id} concern above."
            concerned_task_ids = check.get("concerned_task_ids", [])
            if (
                not isinstance(concerned_task_ids, list)
                or not concerned_task_ids
                or not all(isinstance(task_id, str) and task_id for task_id in concerned_task_ids)
            ):
                log.warning(
                    "Parallel review check %s omitted concerned_task_ids; falling back to synthetic REVIEW-%s task id.",
                    check_id,
                    check_id,
                )
                concerned_task_ids = [f"REVIEW-{check_id}"]
            for task_id in concerned_task_ids:
                rework_items.append(
                    {
                        "task_id": task_id,
                        "issue": issue,
                        "expected": expected,
                        "actual": actual,
                        "evidence_file": evidence_file,
                        "flag_id": f"REVIEW-{check_id}",
                        "source": f"review_{check_id}",
                    }
                )
    return rework_items


def _finalize_review_outcome(
    *,
    root: Path,
    args: argparse.Namespace,
    plan_dir: Path,
    state: PlanState,
    worker: WorkerResult,
    agent: str,
    mode: str,
    refreshed: bool,
    robustness: str,
) -> StepResponse:
    """Post-worker bookkeeping shared by both review paths.

    The single-worker (claude/codex/mock) and parallel-hermes branches of
    :func:`handle_review` previously inlined the same ~100-line block of
    verdict-merging, state advancement, receipt emission, and response
    construction. This helper is the single owner of that flow.
    """
    issues = list(worker.payload.get("issues", []))
    finalize_data = read_json(plan_dir / "finalize.json")
    review_projection = deepcopy(finalize_data)

    review_verdict = worker.payload.get("review_verdict")
    if review_verdict not in {"approved", "needs_rework"}:
        issues.append("Invalid review_verdict; expected 'approved' or 'needs_rework'.")
        review_verdict = "needs_rework"

    verdict_count, total_tasks, check_count, total_checks, missing_evidence = _merge_review_verdicts(
        worker.payload, review_projection, issues,
    )
    worker.payload["issues"] = issues
    atomic_write_json(plan_dir / "review.json", worker.payload)
    atomic_write_text(plan_dir / "final.md", render_final_md(review_projection, phase="review"))
    finalize_hash = sha256_file(plan_dir / "finalize.json")

    result, next_state, next_step = _resolve_review_outcome(
        plan_dir,
        review_verdict, verdict_count, total_tasks,
        check_count, total_checks, missing_evidence,
        robustness,
        state, issues,
        criteria=worker.payload.get("criteria", []),
    )
    state["current_state"] = next_state

    clear_active_step(state)
    apply_session_update(state, "review", agent, worker.session_id, mode=mode, refreshed=refreshed)
    append_history(
        state,
        make_history_entry(
            "review",
            duration_ms=worker.duration_ms, cost_usd=worker.cost_usd,
            result=result,
            worker=worker, agent=agent, mode=mode,
            output_file="review.json",
            prompt_tokens=worker.prompt_tokens,
            completion_tokens=worker.completion_tokens,
            total_tokens=worker.total_tokens,
            artifact_hash=sha256_file(plan_dir / "review.json"),
            finalize_hash=finalize_hash,
        ),
    )
    _emit_receipt(
        plan_dir=plan_dir,
        state=state,
        args=args,
        worker=worker,
        agent=agent,
        mode=mode,
        phase="review",
        output_file="review.json",
        artifact_hash=sha256_file(plan_dir / "review.json"),
        verdict=review_verdict,
    )
    save_state_merge_meta(plan_dir, state)

    criteria = worker.payload.get("criteria", [])
    if result == "blocked":
        summary = _build_review_blocked_message(
            verdict_count=verdict_count, total_tasks=total_tasks,
            check_count=check_count, total_checks=total_checks,
            missing_reviewer_evidence=missing_evidence,
        )
    elif result == "needs_rework":
        summary = "Review requested another execute pass. Re-run execute using the review findings as context."
    else:
        summary = _format_review_success_summary(criteria if isinstance(criteria, list) else [])

    response: StepResponse = {
        "success": result == "success",
        "step": "review",
        "summary": summary,
        "artifacts": ["review.json", "finalize.json", "final.md"],
        "monitor_hint": build_monitor_hint(plan_dir),
        "next_step": next_step,
        "state": next_state,
        "issues": issues,
        "rework_items": list(worker.payload.get("rework_items", [])),
    }
    _emit_phase_result(
        phase="review",
        state=state,
        plan_dir=plan_dir,
        exit_kind="success",
    )
    _attach_next_step_runtime(response)
    attach_agent_fallback(response, args)
    return response


def handle_review(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="review") as (plan_dir, state):
        require_state(state, "review", {STATE_EXECUTED})
        apply_profile_expansion(args, Path(state["config"]["project_dir"]), state=state)
        # Mirror the execute-phase sandbox-divergence warning so reviewers
        # notice when codex is pinned to a narrower tree than the plan's
        # project_dir.
        warn_if_work_dir_differs_from_project_dir(state)
        robustness = configured_robustness(state)
        plan_mode = state["config"].get("mode", "code")
        pre_check_flags: list[dict[str, Any]] = []
        if robustness in {"full", "thorough", "extreme"} and not is_prose_mode(state):
            pre_check_flags = _pkg.run_pre_checks(plan_dir, state, Path(state["config"]["project_dir"]))
        if robustness in {"full", "light", "thorough"}:
            resolved = None
            prompt_override = None
            prompt_kwargs = None
            if robustness in {"full", "thorough"}:
                resolved = _pkg.resolve_agent_mode("review", args)
                agent_type, _mode, _refreshed, _model = _agent_mode_parts(resolved)
                if _supports_prompt_kwargs(worker_module.run_step_with_worker):
                    prompt_kwargs = {"pre_check_flags": pre_check_flags}
                else:
                    prompt_override = _build_review_prompt_override(
                        agent_type,
                        state,
                        plan_dir,
                        root=root,
                        pre_check_flags=pre_check_flags,
                    )
            worker, agent, mode, refreshed = _run_worker(
                "review",
                state,
                plan_dir,
                args,
                root=root,
                resolved=resolved,
                prompt_override=prompt_override,
                prompt_kwargs=prompt_kwargs,
            )
            if robustness in {"full", "thorough"}:
                worker.payload["pre_check_flags"] = pre_check_flags
                _pkg.update_flags_after_review(plan_dir, worker.payload, iteration=state["iteration"])
            atomic_write_json(plan_dir / "review.json", worker.payload)
        else:
            rev_resolved = _pkg.resolve_agent_mode("review", args)
            agent_type, mode, refreshed, model = _agent_mode_parts(rev_resolved)
            if agent_type != "hermes" or os.getenv(MOCK_ENV_VAR) == "1":
                worker, agent, mode, refreshed = _run_worker(
                    "review",
                    state,
                    plan_dir,
                    args,
                    root=root,
                    resolved=(agent_type, mode, refreshed, model),
                )
                atomic_write_json(plan_dir / "review.json", worker.payload)
                return _finalize_review_outcome(
                    root=root,
                    args=args,
                    plan_dir=plan_dir,
                    state=state,
                    worker=worker,
                    agent=agent,
                    mode=mode,
                    refreshed=refreshed,
                    robustness=robustness,
                )

            run_id = None
            try:
                run_id = set_active_step(state, step="review", agent=agent_type, mode=mode, model=model)
                _emit_phase_notice("review")
                save_state_merge_meta(plan_dir, state)
                checks = review_checks.checks_for_robustness("extreme")
                parallel_result = _pkg.run_parallel_review(
                    state,
                    plan_dir,
                    root=root,
                    model=model if agent_type == "hermes" else None,
                    checks=checks,
                    pre_check_flags=pre_check_flags,
                )
                criteria_payload = parallel_result.payload.get("criteria_payload")
                if not isinstance(criteria_payload, dict):
                    raise CliError("worker_parse_error", "Parallel review did not return a criteria payload object")
                merged_payload = dict(criteria_payload)
                merged_payload["checks"] = list(parallel_result.payload.get("checks", []))
                merged_payload["pre_check_flags"] = pre_check_flags
                merged_payload["verified_flag_ids"] = list(parallel_result.payload.get("verified_flag_ids", []))
                merged_payload["disputed_flag_ids"] = list(parallel_result.payload.get("disputed_flag_ids", []))

                review_rework_items = _synthesize_review_rework_items(merged_payload["checks"])
                merged_payload.setdefault("rework_items", [])
                merged_payload.setdefault("issues", [])
                if review_rework_items:
                    merged_payload["rework_items"].extend(review_rework_items)
                    existing_issues = {str(issue) for issue in merged_payload["issues"] if isinstance(issue, str)}
                    for item in review_rework_items:
                        if item["issue"] not in existing_issues:
                            merged_payload["issues"].append(item["issue"])
                            existing_issues.add(item["issue"])
                    merged_payload["review_verdict"] = "needs_rework"

                validate_payload("review", merged_payload)
                atomic_write_json(plan_dir / "review.json", merged_payload)
                _pkg.update_flags_after_review(plan_dir, merged_payload, iteration=state["iteration"])
                worker = WorkerResult(
                    payload=merged_payload,
                    raw_output=parallel_result.raw_output,
                    duration_ms=parallel_result.duration_ms,
                    cost_usd=parallel_result.cost_usd,
                    session_id=None,
                    prompt_tokens=parallel_result.prompt_tokens,
                    completion_tokens=parallel_result.completion_tokens,
                    total_tokens=parallel_result.total_tokens,
                )
                agent, mode, refreshed = "hermes", "persistent", True
            except CliError as error:
                clear_active_step(state, run_id=run_id)
                record_step_failure(plan_dir, state, step="review", iteration=state["iteration"], error=error)
                raise
            except Exception:
                clear_active_step(state, run_id=run_id)
                save_state_merge_meta(plan_dir, state)
                raise

        return _finalize_review_outcome(
            root=root,
            args=args,
            plan_dir=plan_dir,
            state=state,
            worker=worker,
            agent=agent,
            mode=mode,
            refreshed=refreshed,
            robustness=robustness,
        )
