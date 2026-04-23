from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from megaplan.types import MOCK_ENV_VAR, PlanState, STATE_FINALIZED, STATE_GATED, StepResponse
from megaplan.workers import WorkerResult
from megaplan._core import (
    atomic_write_json,
    atomic_write_text,
    load_plan_locked,
    render_final_md,
    require_state,
    sha256_file,
)

from .shared import _finish_step, _raise_step_validation_error, _run_worker, shutil, subprocess

def _reconcile_validation_after_mutation(payload: dict[str, Any]) -> None:
    """Ensure validation block is consistent with the (possibly mutated) task list.

    After _ensure_verification_task() may have appended a task, update the
    validation block so orphan_tasks includes any handler-injected tasks.
    """
    validation = payload.get("validation")
    if not validation or not isinstance(validation, dict):
        return
    task_ids = {t["id"] for t in payload.get("tasks", []) if isinstance(t, dict)}
    covered_ids: set[str] = set()
    for entry in validation.get("plan_steps_covered", []):
        if isinstance(entry, dict):
            for tid in entry.get("finalize_task_ids", []):
                covered_ids.add(tid)
    orphan_ids = set(validation.get("orphan_tasks", []))
    for tid in task_ids:
        if tid not in covered_ids and tid not in orphan_ids:
            orphan_ids.add(tid)
    validation["orphan_tasks"] = sorted(orphan_ids)

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

    failures = payload.get("baseline_test_failures")
    if isinstance(failures, list) and failures:
        tasks[-1]["description"] += (
            f" Note: {len(failures)} tests were already failing before your changes "
            "(see baseline_test_failures in finalize.json) — do not scope-creep into fixing these."
        )

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
    _reconcile_validation_after_mutation(payload)
    atomic_write_json(plan_dir / "finalize.json", payload)
    atomic_write_json(plan_dir / "finalize_snapshot.json", payload)
    atomic_write_text(plan_dir / "final.md", render_final_md(payload))
    return sha256_file(plan_dir / "finalize.json")

def handle_finalize(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="finalize") as (plan_dir, state):
        require_state(state, "finalize", {STATE_GATED})
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
