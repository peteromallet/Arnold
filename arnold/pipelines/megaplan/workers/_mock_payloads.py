"""Mock payload builders for worker steps.

These functions construct default mock payloads for each pipeline step,
supporting the mock worker path (``MEGAPLAN_MOCK=1``).
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any, Callable

from arnold.pipelines.megaplan.types import CliError, PlanState
from arnold.pipelines.megaplan._core import configured_robustness, latest_plan_meta_path, read_json
from arnold.pipelines.megaplan.audits.robustness import build_empty_template
from arnold.pipelines.megaplan.forms.provocations import select_active_checks


_EXECUTE_STEPS = {"execute", "loop_execute"}


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(base_value, value)
            continue
        merged[key] = value
    return merged


def _default_mock_plan_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "plan": textwrap.dedent(
            f"""
            # Implementation Plan: Mock Planning Pass

            ## Overview
            Produce a concrete plan for: {state['idea']}. Keep the scope grounded in the repository and define validation before execution.

            ## Step 1: Inspect the current flow (`megaplan/workers.py`)
            **Scope:** Small
            1. **Inspect** the planner and prompt touch points before editing (`megaplan/workers.py:199`, `megaplan/prompts.py:29`).

            ## Step 2: Implement the smallest viable change (`megaplan/handlers.py`)
            **Scope:** Medium
            1. **Update** the narrowest set of files required to implement the idea (`megaplan/handlers.py:400`).
            2. **Capture** any non-obvious behavior with a short example.
               ```python
               result = "keep the plan structure consistent"
               ```

            ## Step 3: Verify the behavior (`tests/test_megaplan.py`)
            **Scope:** Small
            1. **Run** focused checks that prove the change works (`tests/test_megaplan.py:1`).

            ## Execution Order
            1. Inspect before editing so the plan stays repo-specific.
            2. Implement before expanding verification.

            ## Validation Order
            1. Run targeted tests first.
            2. Run broader checks after the core change lands.
            """
        ).strip(),
        "questions": ["Are there existing patterns in the repo that should be preserved?"],
        "success_criteria": [
            {"criterion": "A concrete implementation path exists.", "priority": "must", "requires": []},
            {"criterion": "Verification is defined before execution.", "priority": "should", "requires": []},
        ],
        "assumptions": ["The project directory is writable."],
    }
    return payload


def _default_mock_prep_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    del plan_dir
    return {
        "skip": False,
        "task_summary": str(state.get("idea", "")).strip() or "Prepare a concise engineering brief for the requested task.",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "Inspect the code paths named in the task, read nearby tests first when they exist, then carry the distilled brief into planning.",
    }


def _default_mock_prep_triage_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    del state, plan_dir
    return {
        "triage_framing": "Mock prep triage found no uncertainty that requires fan-out.",
        "areas": [],
    }


def _default_mock_prep_research_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    del state, plan_dir
    return {"findings": []}


def _loop_goal(state: dict[str, Any]) -> str:
    return str(state.get("idea", state.get("spec", {}).get("goal", "")))


def _default_mock_loop_plan_payload(state: dict[str, Any], plan_dir: Path) -> dict[str, Any]:
    spec = state.get("spec", {})
    goal = _loop_goal(state)
    return {
        "spec_updates": {
            "known_issues": spec.get("known_issues", []),
            "tried_and_failed": spec.get("tried_and_failed", []),
            "best_result_summary": f"Most recent mock planning pass for: {goal}",
        },
        "next_action": "Run the project command, inspect the failures, and prepare the next minimal fix.",
        "reasoning": "The loop spec is initialized and ready for an execution pass based on the current goal and retained context.",
    }


def _default_mock_loop_execute_payload(
    state: dict[str, Any],
    plan_dir: Path,
    *,
    prompt_override: str | None = None,
) -> dict[str, Any]:
    spec = state.get("spec", {})
    goal = _loop_goal(state)
    return {
        "diagnosis": f"Mock execution diagnosis for goal: {goal}",
        "fix_description": "Inspect the command failure, update the smallest relevant file, and rerun the command.",
        "files_to_change": list(spec.get("allowed_changes", []))[:3],
        "confidence": "medium",
        "outcome": "continue",
        "should_pause": False,
    }


def _default_mock_critique_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    iteration = state["iteration"] or 1
    robustness = configured_robustness(state)
    active_checks = select_active_checks(state, robustness, plan_dir=plan_dir)
    checks = build_empty_template(active_checks)
    if iteration == 1:
        return {
            "checks": [
                {
                    **check,
                    "findings": [
                        {
                            "detail": "Mock critique found a concrete repository issue that should be addressed before proceeding.",
                            "flagged": True,
                        }
                    ],
                }
                for check in checks
            ],
            "flags": [
                {
                    "id": "FLAG-001",
                    "concern": "The plan does not name the files or modules it expects to touch.",
                    "category": "completeness",
                    "severity_hint": "likely-significant",
                    "evidence": "Execution could drift because there is no repo-specific scope.",
                },
                {
                    "id": "FLAG-002",
                    "concern": "The plan does not define an observable verification command.",
                    "category": "correctness",
                    "severity_hint": "likely-significant",
                    "evidence": "Success cannot be demonstrated without a concrete check.",
                },
            ],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        }
    return {
        "checks": [
            {
                **check,
                "findings": [
                    {
                        "detail": "Mock critique verified the revised plan against the repository context and found no remaining issue.",
                        "flagged": False,
                    }
                ],
            }
            for check in checks
        ],
        "flags": [],
        "verified_flag_ids": [*(check["id"] for check in checks), "FLAG-001", "FLAG-002"],
        "disputed_flag_ids": [],
    }



def _default_mock_revise_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    return {
        "plan": textwrap.dedent(
            f"""
            # Implementation Plan: Mock Revision Pass

            ## Overview
            Refine the plan for: {state['idea']}. Tighten file-level scope and keep validation explicit.

            ## Step 1: Reconfirm file scope (`megaplan/handlers.py`)
            **Scope:** Small
            1. **Inspect** the exact edit points before changing the plan (`megaplan/handlers.py:540`).

            ## Step 2: Tighten the implementation slice (`megaplan/workers.py`)
            **Scope:** Medium
            1. **Limit** the plan to the smallest coherent change set (`megaplan/workers.py:256`).
            2. **Illustrate** the intended shape when it helps reviewers.
               ```python
               changes_summary = "Added explicit scope and verification details."
               ```

            ## Step 3: Reconfirm verification (`tests/test_workers.py`)
            **Scope:** Small
            1. **Run** a concrete verification command and record the expected proof point (`tests/test_workers.py:251`).

            ## Execution Order
            1. Re-scope the plan before adjusting implementation details.
            2. Re-run validation after the plan is tightened.

            ## Validation Order
            1. Start with the focused worker and handler tests.
            2. End with the broader suite if the focused checks pass.
            """
        ).strip(),
        "changes_summary": "Added explicit repo-scoping and verification steps.",
        "flags_addressed": [
            {
                "id": "FLAG-001",
                "resolution": "addressed",
                "reason": "The revised plan now identifies exact touch points before editing.",
                "where": "Step 1",
            },
            {
                "id": "FLAG-002",
                "resolution": "addressed",
                "reason": "The revised plan now names a concrete verification command.",
                "where": "Step 3",
            },
        ],
        "assumptions": ["The repository contains enough context for implementation."],
        "success_criteria": [
            {"criterion": "The plan identifies exact touch points before editing.", "priority": "must", "requires": []},
            {"criterion": "A concrete verification command is defined.", "priority": "should", "requires": []},
        ],
        "questions": [],
    }


def _default_mock_gate_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    recommendation = "ITERATE" if state["iteration"] == 1 else "PROCEED"
    return {
        "recommendation": recommendation,
        "rationale": (
            "First critique cycle still needs another pass."
            if recommendation == "ITERATE"
            else "Signals are strong enough to move into execution."
        ),
        "signals_assessment": (
            "Iteration 1 still carries unresolved significant flags and should revise."
            if recommendation == "ITERATE"
            else "Weighted score and loop trajectory support proceeding."
        ),
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
        "tiebreaker_question": "",
        "tiebreaker_flag_ids": [],
        "tiebreaker_fuzzy_group_id": "",
    }


def _default_mock_finalize_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": f"Implement: {state['idea']}",
                "depends_on": [],
                "status": "pending",
                "complexity": 3,
                "complexity_justification": "Mock implementation task; assumes multi-file non-trivial logic → tier 3.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
            {
                "id": "T2",
                "description": "Verify success criteria",
                "depends_on": [],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Mock verification task; running and reading tests → tier 2.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
        ],
        "watch_items": ["Ensure repository state matches plan assumptions"],
        "sense_checks": [
            {
                "id": "SC1",
                "task_id": "T1",
                "question": "Verify implementation matches the stated idea.",
                "executor_note": "",
                "verdict": "",
            },
            {
                "id": "SC2",
                "task_id": "T2",
                "question": "Verify success criteria were actually checked.",
                "executor_note": "",
                "verdict": "",
            },
        ],
        "user_actions": [],
        "meta_commentary": "This is a mock finalize output.",
        "validation": {
            "plan_steps_covered": [
                {"plan_step_summary": f"Implement: {state['idea']}", "finalize_item_ids": ["T1"]},
                {"plan_step_summary": "Verify success criteria", "finalize_item_ids": ["T2"]},
            ],
            "orphan_tasks": [],
            "completeness_notes": "All plan steps mapped to tasks.",
            "coverage_complete": True,
        },
    }


def _task_ids_from_prompt_override(prompt_override: str | None) -> set[str] | None:
    if prompt_override is None:
        return None
    match = re.search(r"Only produce `?task_updates`? for these tasks:\s*\[([^\]]*)\]", prompt_override)
    if match is None:
        return None
    task_ids = {item.strip() for item in match.group(1).split(",") if item.strip()}
    return task_ids


def _default_mock_execute_payload(
    state: PlanState,
    plan_dir: Path,
    *,
    prompt_override: str | None = None,
) -> dict[str, Any]:
    target = Path(state["config"]["project_dir"]) / "IMPLEMENTED_BY_MEGAPLAN.txt"
    relative_target = str(target.relative_to(Path(state["config"]["project_dir"])))
    payload = {
        "output": "Mock execution completed successfully.",
        "files_changed": [relative_target],
        "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
        "deviations": [],
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Implemented via mock worker output and wrote IMPLEMENTED_BY_MEGAPLAN.txt.",
                "files_changed": [relative_target],
                "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
                "auto_attributed_files": False,
            },
            {
                "task_id": "T2",
                "status": "done",
                "executor_notes": "Verified success criteria via mock worker output and command checks.",
                "files_changed": [],
                "commands_run": ["mock-verify success criteria"],
                "auto_attributed_files": False,
            },
        ],
        "sense_check_acknowledgments": [
            {
                "sense_check_id": "SC1",
                "executor_note": "Confirmed the implementation artifact was written for the main task.",
            },
            {
                "sense_check_id": "SC2",
                "executor_note": "Confirmed the verification-only task is backed by command evidence.",
            },
        ],
    }
    batch_task_ids = _task_ids_from_prompt_override(prompt_override)
    if batch_task_ids is None:
        return payload
    payload["task_updates"] = [
        task_update
        for task_update in payload["task_updates"]
        if task_update["task_id"] in batch_task_ids
    ]
    payload["sense_check_acknowledgments"] = [
        acknowledgment
        for acknowledgment in payload["sense_check_acknowledgments"]
        if acknowledgment["sense_check_id"] in {
            f"SC{task_id[1:]}"
            for task_id in batch_task_ids
            if task_id.startswith("T")
        }
    ]
    return payload


def _default_mock_review_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    meta = read_json(latest_plan_meta_path(plan_dir, state))
    criteria = []
    for entry in meta.get("success_criteria", []):
        if isinstance(entry, dict):
            name = entry.get("criterion", str(entry))
            priority = entry.get("priority", "must")
        else:
            name = str(entry)
            priority = "must"
        criteria.append({"name": name, "priority": priority, "pass": "pass", "evidence": "Mock execution and artifacts satisfy the criterion."})
    return {
        "review_verdict": "approved",
        "checks": [],
        "pre_check_flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
        "criteria": criteria,
        "issues": [],
        "rework_items": [],
        "summary": "Mock review passed.",
        "task_verdicts": [
            {
                "task_id": "T1",
                "reviewer_verdict": "Pass - mock verified with file-backed implementation evidence.",
                "evidence_files": [str((Path(state["config"]["project_dir"]) / "IMPLEMENTED_BY_MEGAPLAN.txt").relative_to(Path(state["config"]["project_dir"])))],
            },
            {
                "task_id": "T2",
                "reviewer_verdict": "Pass - verification task was reviewed via command evidence and executor notes rather than a changed file.",
                "evidence_files": [],
            },
        ],
        "sense_check_verdicts": [
            {"sense_check_id": "SC1", "verdict": "Confirmed."},
            {"sense_check_id": "SC2", "verdict": "Confirmed."},
        ],
    }


_MockPayloadBuilder = Callable[[dict[str, Any], Path], dict[str, Any]]

_MOCK_DEFAULTS: dict[str, _MockPayloadBuilder] = {
    "plan": _default_mock_plan_payload,
    "prep": _default_mock_prep_payload,
    "prep-triage": _default_mock_prep_triage_payload,
    "prep-research": _default_mock_prep_research_payload,
    "prep-distill": _default_mock_prep_payload,
    "loop_plan": _default_mock_loop_plan_payload,
    "critique": _default_mock_critique_payload,
    "revise": _default_mock_revise_payload,
    "gate": _default_mock_gate_payload,
    "finalize": _default_mock_finalize_payload,
    "execute": _default_mock_execute_payload,
    "loop_execute": _default_mock_loop_execute_payload,
    "review": _default_mock_review_payload,
}


def _build_mock_payload(step: str, state: dict[str, Any], plan_dir: Path, **overrides: Any) -> dict[str, Any]:
    builder = _MOCK_DEFAULTS.get(step)
    if builder is None:
        raise CliError("unsupported_step", f"Mock worker does not support '{step}'")
    prompt_override = overrides.pop("prompt_override", None)
    if step in _EXECUTE_STEPS:
        if step == "loop_execute":
            return _deep_merge(_default_mock_loop_execute_payload(state, plan_dir, prompt_override=prompt_override), overrides)
        return _deep_merge(_default_mock_execute_payload(state, plan_dir, prompt_override=prompt_override), overrides)
    return _deep_merge(builder(state, plan_dir), overrides)
