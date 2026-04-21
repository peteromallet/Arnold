from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from megaplan.types import STATE_INITIALIZED, STATE_PLANNED, STATE_PREPPED, StepResponse
from megaplan._core import load_plan_locked, require_state

from .shared import (
    _finish_step,
    _merge_imported_decision_criteria,
    _run_worker,
    _write_json_artifact,
    _write_plan_version,
)

def handle_plan(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="plan") as (plan_dir, state):
        require_state(state, "plan", {STATE_INITIALIZED, STATE_PREPPED, STATE_PLANNED})
        rerun = state["current_state"] == STATE_PLANNED
        version = state["iteration"] if rerun else state["iteration"] + 1
        worker, agent, mode, refreshed = _run_worker("plan", state, plan_dir, args, root=root, iteration=version)
        payload = worker.payload
        payload["success_criteria"] = _merge_imported_decision_criteria(
            state,
            payload["success_criteria"],
        )
        plan_filename, meta_filename, meta = _write_plan_version(
            plan_dir=plan_dir,
            state=state,
            step="plan",
            version=version,
            worker=worker,
            plan_text=payload["plan"].rstrip() + "\n",
            meta_fields={
                "questions": payload["questions"],
                "success_criteria": payload["success_criteria"],
                "assumptions": payload["assumptions"],
            },
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
        worker, agent, mode, refreshed = _run_worker("prep", state, plan_dir, args, root=root)
        prep_filename = "prep.json"
        artifact_hash = _write_json_artifact(plan_dir, prep_filename, worker.payload)
        code_refs = len(worker.payload.get("relevant_code", []))
        test_refs = len(worker.payload.get("test_expectations", []))
        state["current_state"] = STATE_PREPPED
        return _finish_step(
            plan_dir, state, args,
            step="prep",
            worker=worker, agent=agent, mode=mode, refreshed=refreshed,
            summary=f"Prep complete: captured {code_refs} relevant code reference(s) and {test_refs} test expectation(s).",
            artifacts=[prep_filename],
            output_file=prep_filename,
            artifact_hash=artifact_hash,
            response_fields={"iteration": state["iteration"]},
        )

def _build_verifiability_flags(
    success_criteria: list[dict[str, Any]],
    worker_caps: dict[str, set[str]],
) -> list[dict[str, Any]]:
    from megaplan.capabilities import ALL_CAPABILITIES
    from megaplan.verifiability import audit_criteria, validate_requires

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
