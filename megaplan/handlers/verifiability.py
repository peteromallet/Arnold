from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from megaplan.types import CliError, STATE_AWAITING_HUMAN, STATE_DONE, StepResponse
from megaplan._core import atomic_write_json, latest_plan_meta_path, load_plan, now_utc, read_json, save_state

def handle_verify_human(root: Path, args: argparse.Namespace) -> StepResponse:
    from megaplan._core import plans_root, resolve_plan_dir
    plan_dir, state = load_plan(root, args.plan)

    if state["current_state"] != STATE_AWAITING_HUMAN:
        raise CliError(
            "wrong_state",
            f"verify-human requires state 'awaiting_human_verify', got '{state['current_state']}'.",
        )

    criterion_ref = args.criterion
    passed = getattr(args, "pass_flag", False)
    failed = getattr(args, "fail_flag", False)
    evidence = args.evidence

    plan_meta = read_json(latest_plan_meta_path(plan_dir, state))
    success_criteria = plan_meta.get("success_criteria", [])

    target_idx: int | None = None
    try:
        idx = int(criterion_ref)
        if 0 <= idx < len(success_criteria):
            target_idx = idx
    except (ValueError, TypeError):
        for i, sc in enumerate(success_criteria):
            if sc.get("criterion", "") == criterion_ref:
                target_idx = i
                break

    if target_idx is None:
        raise CliError("invalid_criterion", f"Criterion not found: {criterion_ref!r}")

    verifications_path = plan_dir / "human_verifications.json"
    verifications: list[dict[str, Any]] = []
    if verifications_path.exists():
        verifications = read_json(verifications_path)
        if not isinstance(verifications, list):
            verifications = []

    verifications.append({
        "criterion_idx": target_idx,
        "criterion": success_criteria[target_idx].get("criterion", ""),
        "verdict": "pass" if passed else "fail",
        "evidence": evidence,
        "timestamp": now_utc(),
    })
    atomic_write_json(verifications_path, verifications)

    verified_idxs = {
        v["criterion_idx"] for v in verifications if v.get("verdict") == "pass"
    }

    from megaplan.audits.capabilities import get_worker_capabilities
    from megaplan.audits.verifiability import classify_criteria

    worker_caps = get_worker_capabilities(state)
    _, human_deferred = classify_criteria(success_criteria, worker_caps)
    deferred_must_idxs = {
        i for i, sc in enumerate(success_criteria)
        if sc in human_deferred and sc.get("priority") == "must"
    }

    all_verified = deferred_must_idxs <= verified_idxs
    if all_verified:
        state["current_state"] = STATE_DONE
        save_state(plan_dir, state)
        summary = "All deferred must criteria verified. Plan transitioned to done."
    else:
        remaining = deferred_must_idxs - verified_idxs
        summary = f"Verification recorded. {len(remaining)} deferred must criteria remaining."

    return {
        "success": True,
        "step": "verify-human",
        "plan": state["name"],
        "state": state["current_state"],
        "summary": summary,
        "criterion_idx": target_idx,
        "verdict": "pass" if passed else "fail",
    }

def handle_audit_verifiability(root: Path, args: argparse.Namespace) -> StepResponse:
    plan_dir, state = load_plan(root, args.plan)

    plan_meta = read_json(latest_plan_meta_path(plan_dir, state))
    success_criteria = plan_meta.get("success_criteria", [])

    from megaplan.audits.capabilities import get_worker_capabilities
    from megaplan.audits.verifiability import audit_criteria, validate_requires

    worker_caps = get_worker_capabilities(state)
    audits = audit_criteria(success_criteria, worker_caps)
    issues = validate_requires(success_criteria)

    audit_results = []
    for audit in audits:
        sc = success_criteria[audit.criterion_idx] if audit.criterion_idx < len(success_criteria) else {}
        audit_results.append({
            "criterion_idx": audit.criterion_idx,
            "criterion": sc.get("criterion", ""),
            "priority": sc.get("priority", ""),
            "verdict": audit.verdict,
            "rationale": audit.rationale,
            "missing_caps": audit.missing_caps,
        })

    return {
        "success": True,
        "step": "audit-verifiability",
        "plan": state["name"],
        "summary": f"Audited {len(success_criteria)} criteria: {sum(1 for a in audits if a.verdict == 'machine_verifiable')} machine-verifiable, {sum(1 for a in audits if a.verdict == 'human_only')} human-only, {sum(1 for a in audits if a.verdict == 'unverifiable_no_worker')} unverifiable.",
        "audits": audit_results,
        "validation_issues": issues,
    }
