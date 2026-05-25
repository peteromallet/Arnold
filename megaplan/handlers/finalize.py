from __future__ import annotations

import argparse
import logging
import os
import re
import shlex
from pathlib import Path
from typing import Any

from megaplan.types import MOCK_ENV_VAR, PlanState, STATE_FINALIZED, STATE_GATED, STATE_PLANNED, StepResponse
from megaplan.workers import WorkerResult
from megaplan._core import (
    atomic_write_json,
    atomic_write_text,
    configured_robustness,
    is_creative_mode,
    latest_plan_path,
    load_plan_locked,
    render_final_md,
    require_state,
    sha256_file,
)

from .shared import _finish_step, _raise_step_validation_error, _run_worker, shutil, subprocess

LOGGER = logging.getLogger(__name__)


def _strict_finalize_validation_enabled() -> bool:
    return os.getenv("MEGAPLAN_FINALIZE_STRICT_VALIDATION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _task_is_test_verification(task: dict[str, Any]) -> bool:
    if task.get("kind") == "test":
        return True
    description = (task.get("description") or "").lower()
    test_keywords = (
        "pytest",
        "run test",
        "run the test",
        "test suite",
        "run existing test",
        "verify",
        "verification",
    )
    return any(keyword in description for keyword in test_keywords)


def _final_task_is_test_verification(tasks: list[Any]) -> bool:
    if not tasks or not isinstance(tasks[-1], dict):
        return False
    return _task_is_test_verification(tasks[-1])


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


_PATH_PATTERN = re.compile(r"(?:[\w.-]+/)+[\w.-]+|[\w.-]+\.[A-Za-z0-9]{1,8}")
_PLAN_STEP_PATTERN = re.compile(
    r"^##\s+Step\s+\d+\s*:\s*(?P<title>.+?)\s*$"
    r"(?P<body>.*?)(?=^##\s+Step\s+\d+\s*:|\Z)",
    re.MULTILINE | re.DOTALL,
)
_STOPWORDS = {
    "add",
    "and",
    "change",
    "create",
    "for",
    "from",
    "implement",
    "into",
    "make",
    "modify",
    "move",
    "update",
    "the",
    "this",
    "that",
    "with",
}


def _extract_plan_steps(plan_text: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for match in _PLAN_STEP_PATTERN.finditer(plan_text):
        title = " ".join(match.group("title").split())
        step_text = f"{title}\n{match.group('body')}"
        paths = {path.lower() for path in _PATH_PATTERN.findall(step_text)}
        keywords = {
            token.lower()
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_/-]{3,}", title)
            if token.lower() not in _STOPWORDS
        }
        steps.append({"summary": title, "paths": paths, "keywords": keywords})
    return steps


def _task_covers_plan_step(task: dict[str, Any], step: dict[str, Any]) -> bool:
    description = (task.get("description") or "").lower()
    if any(path in description for path in step["paths"]):
        return True
    return any(keyword in description for keyword in step["keywords"])


def _apply_programmatic_coverage(payload: dict[str, Any], plan_dir: Path, state: PlanState) -> None:
    if not state.get("plan_versions"):
        payload["validation"] = {
            "plan_steps_covered": [],
            "orphan_tasks": [],
            "completeness_notes": "No plan steps found for programmatic coverage.",
            "coverage_complete": True,
        }
        return
    plan_text = latest_plan_path(plan_dir, state).read_text(encoding="utf-8")
    steps = _extract_plan_steps(plan_text)
    tasks = [task for task in payload.get("tasks", []) if isinstance(task, dict)]
    covered_entries: list[dict[str, Any]] = []
    uncovered: list[str] = []

    for step in steps:
        task_ids = [
            task["id"]
            for task in tasks
            if isinstance(task.get("id"), str) and _task_covers_plan_step(task, step)
        ]
        if not task_ids:
            uncovered.append(step["summary"])
        covered_entries.append({
            "plan_step_summary": step["summary"],
            "finalize_item_ids": task_ids,
        })

    if uncovered:
        notes = "; ".join(f"auto-detected uncovered step: {summary}" for summary in uncovered)
        coverage_complete = False
    else:
        notes = "All detected plan steps mapped to tasks."
        coverage_complete = True

    payload["validation"] = {
        "plan_steps_covered": covered_entries,
        "orphan_tasks": [],
        "completeness_notes": notes,
        "coverage_complete": coverage_complete,
    }


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
        complexity = task.get("complexity")
        if not isinstance(complexity, int) or isinstance(complexity, bool) or not 1 <= complexity <= 5:
            _reject(
                f"Finalize task {tid} must include an integer `complexity` score in 1..5 "
                f"(got {complexity!r}). Adjudicate it against the rubric — do not omit or guess."
            )
        justification = task.get("complexity_justification")
        if not isinstance(justification, str) or not justification.strip():
            _reject(
                f"Finalize task {tid} is missing a non-empty `complexity_justification`. "
                "Every complexity score must be argued from the task's concrete files/risk."
            )
    if (
        state["config"].get("mode", "code") == "code"
        and _strict_finalize_validation_enabled()
        and not _final_task_is_test_verification(tasks)
    ):
        LOGGER.warning("Finalize output rejected: final task is not a test verification task.")
        _reject("Finalize output final task must run tests or otherwise verify the change.")
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
            "(manual UI checks), explicitly ask the user. "
            "If user_action_resolutions.json exists in the plan directory, it contains "
            "machine-readable resolution state for each action. "
            "accepted_blocked and waived actions should proceed using their fallback instructions. "
            "satisfied actions are resolved — confirm with a quick mechanical check. "
            "Only unresolved, manual_required, or rejected actions remain hard stops. "
            "If anything is incomplete or unverifiable (and not covered by a resolution), "
            "mark this task blocked with reason and STOP."
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
        "question": (
            "Were all before_execute user_actions either programmatically verified OR "
            "covered by an accepted_blocked/waived/satisfied resolution in "
            "user_action_resolutions.json before execution proceeded? "
            "Only unresolved, manual_required, or rejected actions should remain as hard stops."
        ),
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
    # after_execute actions are human handoff items, not work an executor can
    # perform inside an auto-run. Keep them in `user_actions`; the harness writes
    # user_actions.md so callers can surface them after execute without creating
    # an impossible pending task that blocks the plan.
    for action in after_actions:
        action.setdefault(
            "rationale",
            "Human-only after_execute handoff; surfaced by the harness in user_actions.md.",
        )


def _render_user_actions_md(payload: dict[str, Any]) -> str:
    actions = [
        action
        for action in payload.get("user_actions", [])
        if isinstance(action, dict)
    ]
    lines = ["# User Actions", ""]
    if not actions:
        lines.append("No human user actions recorded.")
        return "\n".join(lines) + "\n"
    for phase in ("before_execute", "after_execute"):
        phase_actions = [action for action in actions if action.get("phase") == phase]
        if not phase_actions:
            continue
        title = "Before Execute" if phase == "before_execute" else "After Execute"
        lines.extend([f"## {title}", ""])
        for action in phase_actions:
            aid = action.get("id", "unknown")
            description = action.get("description", "")
            lines.append(f"- **{aid}**: {description}")
            rationale = action.get("rationale")
            if rationale:
                lines.append(f"  Rationale: {rationale}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

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
            shlex.split(cmd_string),
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

def _normalize_task_complexity(payload: dict[str, Any]) -> None:
    """Safety net for the complexity fields of programmatically-injected tasks.

    LLM-produced tasks are hard-validated in ``_validate_finalize_payload`` (a
    missing/invalid ``complexity`` or empty ``complexity_justification`` bounces
    finalize), so by the time we get here those tasks already carry a deliberate,
    argued score.  This pass only backfills the tasks finalize injects *after*
    validation — the verification task and the user-action gate tasks — which the
    model never scored.  These are read-and-check tasks (verify a file exists,
    confirm a user-action completed), not deep implementation work — so missing/
    out-of-range scores are coerced to 4 (Sonnet) rather than the absolute-conservative
    5 (Opus): still a premium tier capable of any verification logic, but ~5–10×
    cheaper than defaulting to Opus for what is structurally not Opus work.
    A synthetic justification is stamped so the written artifact still satisfies
    the required schema field.
    """
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if not isinstance(task, dict):
            continue
        complexity = task.get("complexity")
        if not isinstance(complexity, int) or isinstance(complexity, bool) or complexity < 1 or complexity > 5:
            task["complexity"] = 4
            task.setdefault(
                "complexity_justification",
                "Auto-injected by finalize after adjudication; defaulted to tier 4 (Sonnet) "
                "because the model never scored this task — verification/gate tasks are read-and-check work.",
            )
        justification = task.get("complexity_justification")
        if not isinstance(justification, str) or not justification.strip():
            task["complexity_justification"] = (
                "Auto-injected by finalize after adjudication; no model-supplied justification."
            )


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
    _apply_programmatic_coverage(payload, plan_dir, state)
    _normalize_task_complexity(payload)
    _reconcile_validation_after_mutation(payload)
    atomic_write_json(plan_dir / "finalize.json", payload)
    atomic_write_json(plan_dir / "finalize_snapshot.json", payload)
    atomic_write_text(plan_dir / "user_actions.md", _render_user_actions_md(payload))
    atomic_write_text(plan_dir / "final.md", render_final_md(payload))
    return sha256_file(plan_dir / "finalize.json")

def handle_finalize(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="finalize") as (plan_dir, state):
        allowed_states = {STATE_GATED}
        robustness = configured_robustness(state)
        if robustness == "bare" or (is_creative_mode(state) and robustness == "light"):
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
            artifacts=["final.md", "finalize.json", "user_actions.md"],
            output_file="finalize.json",
            artifact_hash=artifact_hash,
            next_step="execute",
        )
