from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from megaplan.types import MOCK_ENV_VAR, PlanState, STATE_FINALIZED, STATE_GATED, STATE_PLANNED, StepResponse
from megaplan.workers import WorkerResult
from megaplan._core import (
    atomic_write_json,
    atomic_write_text,
    configured_robustness,
    is_creative_mode,
    load_plan_locked,
    render_final_md,
    require_state,
    sha256_file,
)

from .shared import _finish_step, _raise_step_validation_error, _run_worker, shutil, subprocess

def _reconcile_validation_after_mutation(payload: dict[str, Any]) -> None:
    """Ensure validation block is consistent with the (possibly mutated) task list.

    After handler helpers may have injected tasks, update the
    validation block so orphan_tasks includes any handler-injected tasks.
    """
    validation = payload.get("validation")
    if not validation or not isinstance(validation, dict):
        return
    task_ids = {t["id"] for t in payload.get("tasks", []) if isinstance(t, dict)}
    covered_ids: set[str] = set()
    for entry in validation.get("plan_steps_covered", []):
        if isinstance(entry, dict):
            for tid in entry.get("finalize_item_ids", []):
                covered_ids.add(tid)
    orphan_ids = set(validation.get("orphan_tasks", []))
    for tid in task_ids:
        if tid not in covered_ids and tid not in orphan_ids:
            orphan_ids.add(tid)
    validation["orphan_tasks"] = sorted(orphan_ids)

def _next_task_id(tasks: list[dict[str, Any]]) -> str:
    next_num = max(
        (
            int(task["id"].lstrip("T"))
            for task in tasks
            if isinstance(task, dict)
            and isinstance(task.get("id"), str)
            and task["id"].startswith("T")
            and task["id"][1:].isdigit()
        ),
        default=0,
    ) + 1
    return f"T{next_num}"

def _next_sense_check_id(sense_checks: list[dict[str, Any]]) -> str:
    next_num = max(
        (
            int(sense_check["id"].lstrip("SC"))
            for sense_check in sense_checks
            if isinstance(sense_check, dict)
            and isinstance(sense_check.get("id"), str)
            and sense_check["id"].startswith("SC")
            and sense_check["id"][2:].isdigit()
        ),
        default=0,
    ) + 1
    return f"SC{next_num}"

def _append_plan_step_coverage(payload: dict[str, Any], summary: str, item_id: str) -> None:
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        return
    plan_steps_covered = validation.get("plan_steps_covered")
    if not isinstance(plan_steps_covered, list):
        return
    for entry in plan_steps_covered:
        if not isinstance(entry, dict):
            continue
        item_ids = entry.get("finalize_item_ids", [])
        if isinstance(item_ids, list) and item_id in item_ids:
            return
    plan_steps_covered.append({
        "plan_step_summary": summary,
        "finalize_item_ids": [item_id],
    })

def _validate_finalize_payload(plan_dir: Path, state: PlanState, worker: WorkerResult) -> None:
    payload = worker.payload

    def _reject(message: str) -> None:
        _raise_step_validation_error(
            plan_dir=plan_dir, state=state, step="finalize",
            iteration=state["iteration"], worker=worker,
            code="invalid_finalize", message=message,
        )

    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        _reject("Finalize output must include a non-empty `tasks` list.")
    if not isinstance(payload.get("sense_checks"), list):
        _reject("Finalize output must include a `sense_checks` list.")
    if not isinstance(payload.get("watch_items"), list):
        _reject("Finalize output must include a `watch_items` list.")
    user_actions = payload.get("user_actions", [])
    if not isinstance(user_actions, list):
        _reject("Finalize output `user_actions` must be a list when present.")
    user_actions_by_id: dict[str, dict[str, Any]] = {}
    for index, action in enumerate(user_actions, start=1):
        aid = action.get("id", index) if isinstance(action, dict) else index
        if not isinstance(action, dict):
            _reject(f"Finalize user_action {index} must be an object.")
        if not isinstance(action.get("id"), str) or not action["id"].strip():
            _reject(f"Finalize user_action {index} is missing a non-empty `id`.")
        if not isinstance(action.get("description"), str) or not action["description"].strip():
            _reject(f"Finalize user_action {aid} is missing a non-empty `description`.")
        if action.get("phase") not in {"before_execute", "after_execute"}:
            _reject(
                f"Finalize user_action {aid} must use phase `before_execute` or `after_execute`."
            )
        user_actions_by_id[action["id"]] = action
    for index, task in enumerate(tasks, start=1):
        tid = task.get("id", index) if isinstance(task, dict) else index
        if not isinstance(task, dict):
            _reject(f"Finalize task {index} must be an object.")
        if not isinstance(task.get("id"), str) or not task["id"].strip():
            _reject(f"Finalize task {index} is missing a non-empty `id`.")
        if not isinstance(task.get("description"), str) or not task["description"].strip():
            _reject(f"Finalize task {tid} is missing a non-empty `description`.")
        if task.get("status") != "pending":
            _reject(f"Finalize task {tid} must start with status `pending`.")
    validation = payload.get("validation")
    if isinstance(validation, dict):
        for index, entry in enumerate(validation.get("plan_steps_covered", []), start=1):
            if not isinstance(entry, dict):
                continue
            finalize_item_ids = entry.get("finalize_item_ids", [])
            if (
                isinstance(finalize_item_ids, list)
                and len(finalize_item_ids) == 1
                and isinstance(finalize_item_ids[0], str)
                and finalize_item_ids[0].startswith("U")
            ):
                action = user_actions_by_id.get(finalize_item_ids[0])
                if action is None:
                    _reject(
                        f"Finalize plan_steps_covered entry {index} references unknown user_action "
                        f"`{finalize_item_ids[0]}`."
                    )
                reason = action.get("requires_human_only_reason")
                if not isinstance(reason, str) or not reason.strip():
                    _reject(
                        f"Finalize user_action {finalize_item_ids[0]} is sole coverage for a plan "
                        "step and must include `requires_human_only_reason`."
                    )

def _ensure_verification_task(payload: dict, state: dict) -> None:
    """Ensure the task list ends with a test verification task.

    If the last task already looks like a verification/test task, leave it.
    Otherwise append one that depends on all other tasks.
    """
    tasks = payload.get("tasks", [])
    if not tasks:
        return

    # Check if last task is already a verification task
    last_desc = (tasks[-1].get("description") or "").lower()
    test_keywords = ("run test", "run the test", "verify", "verification", "pytest", "test suite", "run existing test")
    has_verification_task = any(kw in last_desc for kw in test_keywords)

    if not has_verification_task:
        # Build the verification task
        all_ids = [t["id"] for t in tasks]
        next_num = max((int(t["id"].lstrip("T")) for t in tasks if t["id"].startswith("T")), default=0) + 1
        task_id = f"T{next_num}"

        # Pull specific test IDs from the original prompt if available
        idea = state.get("idea", "") or ""
        notes = "\n".join(state.get("notes", []) or [])
        source_text = idea + "\n" + notes

        if "FAIL_TO_PASS" in source_text or "test must pass" in source_text.lower() or "verification" in source_text.lower():
            desc = (
                "Run the tests specified in the task description to verify the fix — run the full test file/module, not just individual functions. "
                "Run the project's existing test suite — do NOT create new test files. "
                "If any test fails, read the error, fix the code, and re-run until all tests pass."
            )
        else:
            desc = (
                "Run tests relevant to the changed files to verify correctness and check for regressions — run the full test file/module, not just individual functions. "
                "Find and run the project's existing test suite — do NOT create new test files. "
                "If any test fails, read the error, fix the code, and re-run until all tests pass."
            )

        verification_task = {
            "id": task_id,
            "description": desc,
            "depends_on": [all_ids[-1]],
            "status": "pending",
            "executor_notes": "",
            "files_changed": [],
            "commands_run": [],
            "evidence_files": [],
            "reviewer_verdict": "",
        }
        tasks.append(verification_task)

        # Add a sense check for it
        sense_checks = payload.get("sense_checks", [])
        sc_num = max((int(sc["id"].lstrip("SC")) for sc in sense_checks if sc["id"].startswith("SC")), default=0) + 1
        sense_checks.append({
            "id": f"SC{sc_num}",
            "task_id": task_id,
            "question": "Did the verification tests pass? Were any regressions found and fixed?",
            "executor_note": "",
            "verdict": "",
        })
        _append_plan_step_coverage(payload, "Run verification tests", task_id)

    failures = payload.get("baseline_test_failures")
    if isinstance(failures, list) and failures:
        tasks[-1]["description"] += (
            f" Note: {len(failures)} tests were already failing before your changes "
            "(see baseline_test_failures in finalize.json) — do not scope-creep into fixing these."
        )

def _ensure_user_actions_pre_gate_task(payload: dict[str, Any], state: dict[str, Any]) -> None:
    if state["config"].get("mode", "code") != "code":
        return
    before_actions = [
        action
        for action in payload.get("user_actions", [])
        if isinstance(action, dict) and action.get("phase") == "before_execute"
    ]
    if not before_actions:
        return
    tasks = payload.get("tasks", [])
    if not tasks:
        return

    task_id = _next_task_id(tasks)
    gate_task = {
        "id": task_id,
        "description": (
            "Read user_actions.md. For each before_execute action, programmatically verify "
            "completion using bash tools — grep .env for required keys, query the migrations "
            "table, curl the dev server, etc. Reading the file does NOT count as verification; "
            "you must run a command. For actions that genuinely cannot be verified mechanically "
            "(manual UI checks), explicitly ask the user. If anything is incomplete or "
            "unverifiable, mark this task blocked with reason and STOP."
        ),
        "depends_on": [],
        "status": "pending",
        "executor_notes": "",
        "files_changed": [],
        "commands_run": [],
        "evidence_files": [],
        "reviewer_verdict": "",
    }
    tasks.insert(0, gate_task)
    for task in tasks[1:]:
        depends_on = task.get("depends_on", [])
        if not isinstance(depends_on, list):
            depends_on = []
        if task_id not in depends_on:
            task["depends_on"] = [task_id, *depends_on]

    sense_checks = payload.setdefault("sense_checks", [])
    sense_checks.append({
        "id": _next_sense_check_id(sense_checks),
        "task_id": task_id,
        "question": "Were all before_execute user_actions programmatically verified before execution proceeded?",
        "executor_note": "",
        "verdict": "",
    })
    _append_plan_step_coverage(payload, "Verify before_execute user_actions", task_id)

def _ensure_user_actions_post_gate_task(payload: dict[str, Any], state: dict[str, Any]) -> None:
    if state["config"].get("mode", "code") != "code":
        return
    after_actions = [
        action
        for action in payload.get("user_actions", [])
        if isinstance(action, dict) and action.get("phase") == "after_execute"
    ]
    if not after_actions:
        return
    tasks = payload.get("tasks", [])
    if not tasks:
        return

    task_order = [
        task["id"]
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    ]
    task_ids = set(task_order)
    depended_on: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        depends_on = task.get("depends_on", [])
        if not isinstance(depends_on, list):
            continue
        for dep in depends_on:
            if isinstance(dep, str) and dep in task_ids:
                depended_on.add(dep)
    terminal_ids = [task_id for task_id in task_order if task_id not in depended_on]
    if not terminal_ids and task_order:
        terminal_ids = [task_order[-1]]

    action_lines = [
        f"- {action.get('id', 'unknown')}: {action.get('description', '')}"
        for action in after_actions
    ]
    task_id = _next_task_id(tasks)
    tasks.append({
        "id": task_id,
        "description": (
            "Surface after_execute user_actions to the user:\n"
            + "\n".join(action_lines)
            + "\nDo not perform them yourself — these require human action. Mark this task done "
            "once they have been clearly communicated."
        ),
        "depends_on": terminal_ids,
        "status": "pending",
        "executor_notes": "",
        "files_changed": [],
        "commands_run": [],
        "evidence_files": [],
        "reviewer_verdict": "",
    })

    sense_checks = payload.setdefault("sense_checks", [])
    sense_checks.append({
        "id": _next_sense_check_id(sense_checks),
        "task_id": task_id,
        "question": "Were all after_execute user_actions clearly surfaced to the user without the executor performing them?",
        "executor_note": "",
        "verdict": "",
    })
    _append_plan_step_coverage(payload, "Surface after_execute user_actions", task_id)

def _capture_test_baseline(project_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    if os.getenv(MOCK_ENV_VAR) == "1":
        return {
            "baseline_test_failures": [],
            "baseline_test_command": "pytest --tb=no -q --no-header",
        }

    configured_command = config.get("test_command")
    cmd_string: str | None = None

    if isinstance(configured_command, str) and configured_command.strip():
        cmd_string = configured_command.strip()
        if cmd_string.startswith("pytest"):
            cmd_string = f"{cmd_string} --tb=no -q --no-header"
    elif shutil.which("pytest"):
        cmd_string = "pytest --tb=no -q --no-header"

    if cmd_string is None:
        return {
            "baseline_test_failures": None,
            "baseline_test_command": None,
            "baseline_test_note": (
                "No supported test runner detected on PATH (looked for: pytest). "
                "Configure test_command in state config to specify one."
            ),
        }

    try:
        result = subprocess.run(
            cmd_string,
            shell=True,
            cwd=project_dir,
            timeout=120,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {
            "baseline_test_failures": None,
            "baseline_test_command": cmd_string,
            "baseline_test_note": (
                f"Baseline test capture timed out after 120 seconds while running: {cmd_string}"
            ),
        }
    except Exception as exc:
        return {
            "baseline_test_failures": None,
            "baseline_test_command": None,
            "baseline_test_note": f"Baseline capture crashed: {exc}",
        }

    failures: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line.endswith(" FAILED"):
            continue
        test_id = line[: -len(" FAILED")].strip()
        if test_id:
            failures.append(test_id)

    return {
        "baseline_test_failures": failures,
        "baseline_test_command": cmd_string,
    }

def _write_finalize_artifacts(plan_dir: Path, payload: dict[str, Any], state: PlanState) -> str:
    if state["config"].get("mode") in {"doc", "joke"}:
        payload["baseline_test_failures"] = None
        payload["baseline_test_command"] = None
        payload["baseline_test_note"] = "Test baseline not applicable in doc mode."
    else:
        baseline = _capture_test_baseline(Path(state["config"]["project_dir"]), state.get("config", {}))
        payload.update(baseline)
        _ensure_verification_task(payload, state)
        _ensure_user_actions_pre_gate_task(payload, state)
        _ensure_user_actions_post_gate_task(payload, state)
    _reconcile_validation_after_mutation(payload)
    atomic_write_json(plan_dir / "finalize.json", payload)
    atomic_write_json(plan_dir / "finalize_snapshot.json", payload)
    atomic_write_text(plan_dir / "final.md", render_final_md(payload))
    return sha256_file(plan_dir / "finalize.json")

def handle_finalize(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="finalize") as (plan_dir, state):
        allowed_states = {STATE_GATED}
        if is_creative_mode(state) and configured_robustness(state) == "light":
            allowed_states.add(STATE_PLANNED)
        require_state(state, "finalize", allowed_states)
        worker, agent, mode, refreshed = _run_worker("finalize", state, plan_dir, args, root=root)
        _validate_finalize_payload(plan_dir, state, worker)
        artifact_hash = _write_finalize_artifacts(plan_dir, worker.payload, state)
        state["current_state"] = STATE_FINALIZED
        return _finish_step(
            plan_dir, state, args,
            step="finalize",
            worker=worker, agent=agent, mode=mode, refreshed=refreshed,
            summary=f"Finalized plan with {len(worker.payload['tasks'])} tasks and {len(worker.payload['watch_items'])} watch items.",
            artifacts=["final.md", "finalize.json"],
            output_file="finalize.json",
            artifact_hash=artifact_hash,
            next_step="execute",
        )
