from __future__ import annotations

import argparse
import logging
import os
import re
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.feature_flags import calibration_query_route_on
from arnold_pipelines.megaplan.calibration import (
    CapabilityClaim,
    EvaluandRef,
    ModelIdentity,
    check_reviewer_invariant,
    classify_claim_taint,
    query_route_if_enabled,
    write_capability_claim,
)
from arnold_pipelines.megaplan.types import CliError, MOCK_ENV_VAR, PlanState, StepResponse
from arnold_pipelines.megaplan.planning.state import (
    STATE_GATED,
    STATE_PLANNED,
)
from arnold_pipelines.megaplan.workers import WorkerResult
from arnold_pipelines.megaplan._core import (
    list_batch_artifacts,
    atomic_write_json,
    atomic_write_text,
    batch_artifact_index,
    configured_robustness,
    infer_next_steps,
    is_creative_mode,
    latest_plan_meta_path,
    latest_plan_path,
    load_plan_locked,
    read_json,
    record_step_failure,
    render_final_md,
    require_state,
    sha256_file,
)
from arnold.pipeline.contract_validation import validate_payload_against_schema
from arnold.pipeline.step_io_contract import StepIOOperation
from arnold_pipelines.megaplan.finalize_contract import FINALIZE_MODEL_OUTPUT_SCHEMA
from arnold_pipelines.megaplan.observability.evaluand import read_evaluand_events
from arnold_pipelines.megaplan.runtime.schema_registry_adapter import create_step_io_contract_context
from arnold_pipelines.megaplan.orchestration.plan_contracts import normalize_contract_payload
from arnold_pipelines.megaplan.orchestration.test_selection import (
    compute_test_blast_radius,
    resolve_baseline_test_selection,
)
from arnold_pipelines.megaplan.orchestration.task_feasibility import (
    compile_task_feasibility,
)
from arnold_pipelines.megaplan.orchestration.critique_custody import (
    CritiqueCustodyError,
    bind_finalize_custody,
    validate_finalize_resolution_coverage,
    write_critique_clearance,
)
from arnold_pipelines.megaplan.store import write_plan_artifact_json
from arnold_pipelines.megaplan.schema_projection import (
    project_schema_owned_fields,
    require_schema_fields,
    schema_property_names,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan._core.topology import STAGE_TO_STATE
from arnold_pipelines.megaplan.execute.quality import (
    _capture_git_status_snapshot_recursive,
    _git_head,
    _is_harness_generated_path,
    capture_uncommitted_baseline,
)
from arnold_pipelines.megaplan.workflows.components import FINALIZE_POLICY

from .shared import _attach_next_step_runtime, _finish_step, _raise_step_validation_error, _run_worker

LOGGER = logging.getLogger("megaplan")


class FinalizeBaselineSelectionError(Exception):
    """Raised when finalize cannot establish a trusted baseline test scope."""

    def __init__(self, test_selection: dict[str, Any]) -> None:
        self.test_selection = test_selection
        super().__init__(_finalize_baseline_contract_message(test_selection))


class TaskFeasibilityError(Exception):
    """Raised when a finalized v2 task graph cannot safely enter execute."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        codes = ", ".join(
            str(item.get("code"))
            for item in report.get("diagnostics", [])
            if isinstance(item, Mapping)
        )
        super().__init__(f"Finalized task graph failed feasibility admission: {codes}")


def _finalize_baseline_contract_message(test_selection: dict[str, Any]) -> str:
    reason = str(test_selection.get("reason") or "scoped baseline selection is unresolved")
    fallback_reason = test_selection.get("fallback_reason")
    details = f" Reason: {reason}"
    if isinstance(fallback_reason, str) and fallback_reason.strip():
        details += f" Fallback: {fallback_reason.strip()}"
    return (
        "Finalize could not resolve a scoped baseline test command. This is a "
        "plan-contract failure, not a finalize retry: revise the approved plan "
        "to include machine-readable `test_blast_radius` metadata for code-mode "
        "work, or explicitly set `test_selection=full` when the full suite is "
        "intended."
        + details
    )


def _required_mapping(value: object, *, context: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AssertionError(f"{context} must be a mapping")
    return dict(value)


def _required_string(mapping: dict[str, Any], key: str, *, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise AssertionError(f"{context}.{key} must be a non-empty string")
    return value


def _finalize_route_surface() -> dict[str, Any]:
    metadata = _required_mapping(FINALIZE_POLICY.metadata, context="FINALIZE_POLICY.metadata")
    return _required_mapping(
        metadata.get("route_surface"),
        context="FINALIZE_POLICY.metadata.route_surface",
    )


def _finalize_success_projection() -> dict[str, str]:
    success = _required_mapping(
        _finalize_route_surface().get("success_route"),
        context="FINALIZE_POLICY.metadata.route_surface.success_route",
    )
    return {
        "route_signal": _required_string(
            success,
            "route_signal",
            context="FINALIZE_POLICY.metadata.route_surface.success_route",
        ),
        "next_step": _required_string(
            success,
            "target_ref",
            context="FINALIZE_POLICY.metadata.route_surface.success_route",
        ),
        "state": _required_string(
            success,
            "state_ref",
            context="FINALIZE_POLICY.metadata.route_surface.success_route",
        ),
    }


def _finalize_revise_fallback_projection() -> dict[str, str]:
    route_surface = _finalize_route_surface()
    fallback = _required_mapping(
        _required_mapping(
            route_surface.get("fallback_routes"),
            context="FINALIZE_POLICY.metadata.route_surface.fallback_routes",
        ).get("plan_contract_revise_needed"),
        context="FINALIZE_POLICY.metadata.route_surface.fallback_routes.plan_contract_revise_needed",
    )
    projection = _required_mapping(
        _required_mapping(
            route_surface.get("final_projection_routes"),
            context="FINALIZE_POLICY.metadata.route_surface.final_projection_routes",
        ).get("revise_fallback"),
        context="FINALIZE_POLICY.metadata.route_surface.final_projection_routes.revise_fallback",
    )
    route_signal = _required_string(
        fallback,
        "route_signal",
        context="FINALIZE_POLICY.metadata.route_surface.fallback_routes.plan_contract_revise_needed",
    )
    target_ref = _required_string(
        fallback,
        "target_ref",
        context="FINALIZE_POLICY.metadata.route_surface.fallback_routes.plan_contract_revise_needed",
    )
    projected_phase = _required_string(
        projection,
        "projected_phase",
        context="FINALIZE_POLICY.metadata.route_surface.final_projection_routes.revise_fallback",
    )
    if route_signal != _required_string(
        projection,
        "route_signal",
        context="FINALIZE_POLICY.metadata.route_surface.final_projection_routes.revise_fallback",
    ):
        raise AssertionError("Finalize revise fallback route_signal must match its projection route")
    if target_ref != _required_string(
        projection,
        "target_ref",
        context="FINALIZE_POLICY.metadata.route_surface.final_projection_routes.revise_fallback",
    ):
        raise AssertionError("Finalize revise fallback target_ref must match its projection route")
    projected_state = STAGE_TO_STATE.get(projected_phase)
    if not isinstance(projected_state, str) or not projected_state:
        raise AssertionError(
            "FINALIZE_POLICY.metadata.route_surface.final_projection_routes."
            "revise_fallback.projected_phase must map to a known plan state"
        )
    return {
        "route_signal": route_signal,
        "next_step": target_ref,
        "state": projected_state,
    }


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


# Input-time JSON Schema for the finalize payload before _write_finalize_artifacts
# mutates it.  Only schema-expressible constraints (types, required fields,
# nested item shape) live here; non-empty-after-strip, range checks, bool-vs-int
# rejection, status="pending", verification-pattern detection, and U-prefixed
# plan_steps_covered rules are enforced by _finalize_semantic_postcheck.
_FINALIZE_INPUT_SCHEMA = FINALIZE_MODEL_OUTPUT_SCHEMA


def _validate_finalize_payload(plan_dir: Path, state: PlanState, worker: WorkerResult) -> None:
    """Thin wrapper: route schema-expressible checks through the C1 chokepoint
    (``validate_payload_against_schema``) then delegate residual semantic checks
    to :func:`_finalize_semantic_postcheck`."""
    payload = worker.payload

    def _reject(message: str) -> None:
        _raise_step_validation_error(
            plan_dir=plan_dir, state=state, step="finalize",
            iteration=state["iteration"], worker=worker,
            code="invalid_finalize", message=message,
        )

    # Pre-strip nullable optional task fields so downstream schema validation
    # and write-time enforcement see a clean shape.  Done before schema
    # validation so a None-valued optional doesn't bounce as a type error.
    raw_tasks = payload.get("tasks")
    if isinstance(raw_tasks, list):
        for task in raw_tasks:
            if not isinstance(task, dict):
                continue
            for optional_object_field in ("stance", "stop_signal"):
                if task.get(optional_object_field) is None:
                    task.pop(optional_object_field, None)

    # Schema-expressible checks: top-level required arrays, task/user_action
    # field types, required-field presence.  Routed through the C1 chokepoint.
    result = validate_payload_against_schema(payload, _FINALIZE_INPUT_SCHEMA)
    if result.diagnostics:
        diag = result.diagnostics[0]
        _reject(f"Finalize payload failed schema validation at {diag.payload_pointer!r}: {diag.message}")

    # Residual semantic checks the schema subset cannot express.
    _finalize_semantic_postcheck(plan_dir, state, worker, _reject)
    clearance_path = plan_dir / "critique_clearance.json"
    if clearance_path.exists():
        try:
            validate_finalize_resolution_coverage(payload, read_json(clearance_path))
        except CritiqueCustodyError as error:
            _reject(str(error))


def _finalize_semantic_postcheck(
    plan_dir: Path,
    state: PlanState,
    worker: WorkerResult,
    _reject,
) -> None:
    """Residual semantic checks not expressible in the C1 schema subset.

    Enforces: non-empty tasks list; non-empty-after-strip strings on tasks and
    user_actions; integer-not-bool complexity in 1..10; status == "pending";
    phase enum membership; re-run-until-pass scrubber (strict mode); and
    U-prefixed plan_steps_covered coverage rules.
    """
    payload = worker.payload

    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        _reject("Finalize output must include a non-empty `tasks` list.")

    user_actions = payload.get("user_actions", [])
    user_actions_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(user_actions, list):
        for index, action in enumerate(user_actions, start=1):
            if not isinstance(action, dict):
                continue
            aid = action.get("id", index)
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
        if not isinstance(task, dict):
            _reject(f"Finalize task {index} must be an object.")
        tid = task.get("id", index)
        if not isinstance(task.get("id"), str) or not task["id"].strip():
            _reject(f"Finalize task {index} is missing a non-empty `id`.")
        if not isinstance(task.get("description"), str) or not task["description"].strip():
            _reject(f"Finalize task {tid} is missing a non-empty `description`.")
        if task.get("status") != "pending":
            _reject(f"Finalize task {tid} must start with status `pending`.")
        files_changed = task.get("files_changed")
        if isinstance(files_changed, list):
            for raw_path in files_changed:
                if not isinstance(raw_path, str):
                    continue
                normalized_path = raw_path.strip().replace("\\", "/")
                if (
                    "/.megaplan/plans/" in normalized_path
                    or normalized_path.startswith(".megaplan/plans/")
                    or "/.megaplan/worker_tmp/" in normalized_path
                    or normalized_path.startswith(".megaplan/worker_tmp/")
                ):
                    _reject(
                        f"Finalize task {tid} lists harness artifact path "
                        f"{raw_path!r} in `files_changed`. Finalize must output "
                        "pending target-work tasks, not meta-work on plan scratch files."
                    )
        complexity = task.get("complexity")
        if (
            not isinstance(complexity, int)
            or isinstance(complexity, bool)
            or not 1 <= complexity <= 10
        ):
            _reject(
                f"Finalize task {tid} must include an integer `complexity` score in 1..10 "
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
    ):
        # Negatively assert: no re-run-until-pass task may survive in the
        # payload.  The harness owns authoritative verification — the LLM must
        # not author a task that loops the suite.
        for task in tasks:
            if isinstance(task, dict) and _task_matches_verification_pattern(task):
                _reject(
                    "Finalize output contains a re-run-until-pass task. "
                    "The harness owns test verification — do NOT author a re-run-until-pass task."
                )

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

# ---------------------------------------------------------------------------
# Scrubber detection helpers (shared between the scrubber and strict validation)
# ---------------------------------------------------------------------------

# Tightened keywords: require a run/re-run action word to co-occur with a
# test/pytest/verification target.  The standalone "test suite" keyword is
# intentionally dropped — it was too broad and caught unrelated descriptions.
_VERIFY_ACTIONS = ("run", "re-run", "re run", "rerun")
_VERIFY_TARGETS = ("test", "pytest", "verification")

# Catch-all regexes that match re-run-until-pass phrasing even when the
# tightened keyword heuristic misses it.
_RE_RUN_UNTIL_PASS_PATTERNS = [
    re.compile(r"re-?run.*(?:until|all).*(?:pass|green)", re.IGNORECASE),
    re.compile(r"iterate.*until.*(?:pass|succeed)", re.IGNORECASE),
    re.compile(r"loop.*(?:test|suite)", re.IGNORECASE),
]


def _task_matches_verification_pattern(task: dict[str, Any]) -> bool:
    """Return True if *task* describes a re-run-until-pass verification loop."""
    description = (task.get("description") or "").lower()

    # Tightened keyword heuristic: need both an action AND a target
    has_action = any(action in description for action in _VERIFY_ACTIONS)
    has_target = any(target in description for target in _VERIFY_TARGETS)
    if has_action and has_target:
        return True

    # Catch-all regexes
    if any(pattern.search(description) for pattern in _RE_RUN_UNTIL_PASS_PATTERNS):
        return True

    return False


def _ensure_verification_task(payload: dict, state: dict) -> None:
    """Bound verification loops without erasing the task's implementation objective.

    Scans all tasks for re-run-until-pass language. The old scrubber replaced
    the entire description and destroyed legitimate
    implementation objectives.  Preserve the description and append the
    bounded harness-owned verification contract instead.
    """
    tasks = payload.get("tasks", [])
    if not tasks:
        return

    BOUNDED_SUFFIX = (
        " Narrow verification is limited by narrow_tests; introduce no new failures "
        "vs the recorded baseline; "
        "do not try to make pre-existing baseline failures pass; "
        "do not narrow to individual functions. "
        "The harness will run the authoritative post-execute verification — "
        "do not loop the suite."
    )

    for task in tasks:
        if not isinstance(task, dict):
            continue
        if _task_matches_verification_pattern(task):
            if BOUNDED_SUFFIX.strip() not in task["description"]:
                task["description"] = task["description"].rstrip() + BOUNDED_SUFFIX

    # Sense-check injection and _append_plan_step_coverage removed — the harness owns verification.
    failures = payload.get("baseline_test_failures")
    if isinstance(failures, list) and failures:
        # Keep baseline information outside task objectives so the admitted
        # task hash is stable across baseline capture.
        payload["baseline_test_note"] = (
            f"Note: {len(failures)} tests were already failing before your changes "
            "(see baseline_test_failures in finalize.json)."
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
        "objective": "Resolve every before-execute human prerequisite.",
        "description": (
            "Read user_actions.md. For each before_execute action, programmatically verify "
            "completion using bash tools — grep .env for required keys, query the migrations "
            "table, curl the dev server, etc. Reading the file does NOT count as verification; "
            "you must run a command. For actions that genuinely cannot be verified mechanically "
            "(manual UI checks, legal/license judgments), explicitly ask the user via "
            "AskUserQuestion. "
            "After you get the user's answer (or after a mechanical verification produces a "
            "clear outcome), RECORD the resolution by invoking the CLI — do NOT hand-write "
            "user_action_resolutions.json, the schema is strict and you will get it wrong. "
            "Use: `megaplan user-action resolve --plan <PLAN_NAME> --action-id <U_ID> "
            "--resolution <satisfied|accepted_blocked|waived|manual_required|rejected> "
            "--reason '...' --instructions '...' --tasks <T_IDs>`. "
            "Run this exactly once per user_action you are recording. "
            "If user_action_resolutions.json already exists, it contains prior resolutions: "
            "accepted_blocked and waived actions should proceed using their fallback instructions; "
            "satisfied actions are resolved — confirm with a quick mechanical check; "
            "only unresolved, manual_required, or rejected actions remain hard stops. "
            "If anything is incomplete or unverifiable (and not covered by a resolution), "
            "mark this task blocked with reason and STOP."
        ),
        "depends_on": [],
        "dependency_reasons": {},
        "routing_group": "human-prerequisite-gate",
        "status": "pending",
        "kind": "audit",
        "complexity": 3,
        "complexity_justification": "A bounded prerequisite check with no repository mutation.",
        "estimated_minutes": 5,
        "write_set": {"paths": [], "complete": True},
        "narrow_tests": {"selectors": [], "max_seconds": 0, "max_runs": 0},
        "checkpoint": {"required": False, "max_interval_seconds": 300, "records": []},
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
            reasons = task.get("dependency_reasons")
            if not isinstance(reasons, dict):
                reasons = {}
            task["dependency_reasons"] = {
                task_id: {
                    "kind": "human_prerequisite",
                    "reason": "Execution cannot begin until required human-only prerequisites are resolved.",
                    "required_output": "user_action_resolutions.json",
                },
                **reasons,
            }

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

# Keys persisted to / restored from the per-plan baseline cache.
_BASELINE_CACHE_KEYS = (
    "baseline_test_failures",
    "baseline_test_command",
    "baseline_test_note",
    "baseline_test_collection_errors",
)


def _baseline_cache_path(plan_dir: Path) -> Path:
    return plan_dir / "baseline.json"


def _read_cached_baseline(plan_dir: Path) -> dict[str, Any] | None:
    """Return a previously-captured baseline for this plan, or ``None``.

    Only a SUCCESSFUL baseline (``baseline_test_failures`` is a concrete list,
    not ``None``) is treated as reusable. A poisoned/timeout/runner-error
    baseline (``failures is None``) is intentionally NOT cached at write time,
    so a retry under better conditions can re-establish it.
    """
    path = _baseline_cache_path(plan_dir)
    if not path.exists():
        return None
    try:
        import json as _json

        data = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("baseline_test_failures"), list):
        return None
    return {k: data.get(k) for k in _BASELINE_CACHE_KEYS if k in data}


def _write_cached_baseline(plan_dir: Path, baseline: dict[str, Any]) -> None:
    """Persist a SUCCESSFUL baseline so a finalize retry reuses it.

    A baseline with ``baseline_test_failures is None`` (timeout / runner error /
    not-applicable) is not cached — those are transient/degraded outcomes that a
    retry should be free to re-attempt.
    """
    if not isinstance(baseline.get("baseline_test_failures"), list):
        return
    payload = {k: baseline[k] for k in _BASELINE_CACHE_KEYS if k in baseline}
    try:
        atomic_write_json(_baseline_cache_path(plan_dir), payload)
    except OSError:
        # Best-effort cache; a write failure must never fail the phase.
        pass


def _capture_test_baseline_for_plan(
    plan_dir: Path, project_dir: Path, config: dict[str, Any]
) -> dict[str, Any]:
    """Capture the test baseline ONCE per plan, reusing a cached result on retry.

    The baseline runs the whole suite (minutes of work). A finalize retry — e.g.
    after a Shannon readiness-probe stall — has no reason to re-establish it, so
    a successful baseline is persisted to ``<plan_dir>/baseline.json`` and reused
    verbatim on any subsequent finalize attempt for the same plan. Mock mode and
    degraded (null-failures) outcomes bypass the cache and fall through to a live
    capture, preserving prior behaviour exactly for those cases.
    """
    if os.getenv(MOCK_ENV_VAR) != "1":
        cached = _read_cached_baseline(plan_dir)
        if cached is not None:
            LOGGER.info(
                "finalize: reusing cached test baseline from %s "
                "(%d pre-existing failures) — skipping suite re-run",
                _baseline_cache_path(plan_dir),
                len(cached.get("baseline_test_failures") or []),
            )
            return cached
    baseline = _capture_test_baseline(project_dir, config)
    _write_cached_baseline(plan_dir, baseline)
    return baseline


def _capture_test_baseline(project_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    if os.getenv(MOCK_ENV_VAR) == "1":
        return {
            "baseline_test_failures": [],
            "baseline_test_command": "pytest --tb=no -q --no-header -rA",
        }

    # Two caps govern baseline capture (see suite_runner._wait_for_process):
    #
    #   * IDLE timeout (primary) -- a true hang detector keyed on test output.
    #     While the suite's log keeps growing it is making progress and is left
    #     alone; only a log that goes SILENT for `idle` seconds is treated as
    #     wedged. This is independent of suite size, so it never needs re-tuning
    #     as the suite grows -- the failure mode that produced this null baseline
    #     (a 10k-test suite that legitimately runs past a fixed wall-clock cap)
    #     simply cannot recur, because a moving suite is never silent.
    #   * ABSOLUTE ceiling (last resort) -- a generous runaway guard. On timeout
    #     the capture emits a POISON value (baseline_test_failures=None) which
    #     breaks the downstream no-new-failures checkpoint, so a FALSE trip is
    #     expensive; with the idle detector doing the real work this ceiling
    #     should essentially never trip for a healthy suite. Default 3600s.
    #
    # Override ABSOLUTE ceiling via MEGAPLAN_TEST_BASELINE_TIMEOUT_S (env) or
    # test_baseline_timeout (config); IDLE via MEGAPLAN_TEST_BASELINE_IDLE_TIMEOUT_S
    # (env) or test_baseline_idle_timeout (config).
    raw_timeout = config.get("test_baseline_timeout")
    if raw_timeout is None:
        _env_timeout = os.getenv("MEGAPLAN_TEST_BASELINE_TIMEOUT_S")
        if _env_timeout:
            raw_timeout = _env_timeout
    try:
        if raw_timeout is not None:
            timeout = int(raw_timeout)
            if timeout <= 0:
                raise ValueError(f"test_baseline_timeout must be a positive int, got {raw_timeout!r}")
        else:
            timeout = 3600
    except (ValueError, TypeError):
        return {
            "baseline_test_failures": None,
            "baseline_test_command": config.get("test_command"),
            "baseline_test_note": (
                f"test_baseline_timeout config value is invalid ({raw_timeout!r}); "
                "must be a positive integer."
            ),
        }

    raw_idle = config.get("test_baseline_idle_timeout")
    if raw_idle is None:
        _env_idle = os.getenv("MEGAPLAN_TEST_BASELINE_IDLE_TIMEOUT_S")
        if _env_idle:
            raw_idle = _env_idle
    # Default 300s: pytest -q emits a progress char only *after* each test, so the
    # idle gap equals the slowest single test. 300s tolerates a slow integration
    # test (subprocess/LLM spawn) while still catching a genuinely wedged (infinite)
    # suite; a false idle-trip re-poisons the baseline, so err generous.
    try:
        idle_seconds = int(raw_idle) if raw_idle is not None else 300
        if idle_seconds <= 0:
            idle_seconds = 300
    except (ValueError, TypeError):
        idle_seconds = 300

    import time as _time_mod
    from arnold_pipelines.megaplan.orchestration.suite_runner import append_suite_run, run_suite
    from arnold_pipelines.megaplan.orchestration.baseline_gate import (
        BaselineSlot,
        baseline_slot,
        baseline_slot_wait_seconds,
    )

    # Host-wide baseline-concurrency gate. Several megaplan chains in finalize at
    # once would otherwise run the full pytest suite simultaneously and saturate
    # the box's CPU. Acquire a slot BEFORE the suite starts so queue-wait time
    # never counts against the suite's own timeout. If no slot frees within the
    # bounded wait, degrade gracefully (skip the baseline) rather than hanging.
    with baseline_slot() as slot:
        if slot is BaselineSlot.DEGRADED:
            return {
                "baseline_test_failures": None,
                "baseline_test_command": config.get("test_command"),
                "baseline_test_note": (
                    "Baseline test capture skipped: could not acquire a host-wide "
                    f"baseline slot within {baseline_slot_wait_seconds():.0f}s "
                    "(MEGAPLAN_TEST_BASELINE_MAX_CONCURRENT) — too many chains are "
                    "running the full suite concurrently. Proceeding without a "
                    "baseline to avoid CPU contention."
                ),
            }
        deadline = _time_mod.monotonic() + timeout
        result = run_suite(
            project_dir,
            config,
            phase="baseline",
            deadline_seconds=deadline,
            idle_seconds=idle_seconds,
        )
    plan_dir_str = config.get("plan_dir")
    if plan_dir_str:
        append_suite_run(Path(plan_dir_str), result)

    # NOTE: The new parser (regex-based nodeid extraction via
    # ``_NODEID_LINE_RE`` in ``suite_runner._parse_pytest_output``) is more
    # precise than the old ``' FAILED'``-substring scan that was previously
    # here.  Shadow mode's *verdict structure* is unchanged, but
    # ``baseline_test_failures`` content may now render as full nodeids
    # (e.g. ``tests/test_foo.py::test_param[a-1]``) rather than loose lines.
    # The set identity holds — the same failing tests are reported.

    if result.status == "timeout":
        if getattr(result, "timeout_reason", None) == "idle":
            note = (
                f"Baseline test capture stalled: no test output for {idle_seconds}s "
                f"(suite appears wedged, not merely slow) while running: {result.command}"
            )
        else:
            note = (
                f"Baseline test capture timed out after hitting the absolute {timeout}s ceiling "
                f"(suite still producing output but never finished) while running: "
                f"{result.command}"
            )
        return {
            "baseline_test_failures": None,
            "baseline_test_command": result.command,
            "baseline_test_note": note,
        }
    if result.status == "runner_error":
        return {
            "baseline_test_failures": None,
            "baseline_test_command": None,
            "baseline_test_note": (
                f"Baseline capture failed: runner error"
                + (f" (exit code: {result.exit_code})" if result.exit_code is not None else "")
            ),
        }
    if result.status == "not_applicable":
        return {
            "baseline_test_failures": None,
            "baseline_test_command": result.command,
            "baseline_test_note": "No tests collected (pytest exit code 5).",
        }

    # ``passed`` or ``failed`` — baseline captures whatever was failing *before*
    # the plan runs so the delta computation in post-execute can compare.
    return {
        "baseline_test_failures": result.failures,
        "baseline_test_command": result.command,
        "baseline_test_collection_errors": list(result.collection_errors or []),
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
    out-of-range scores are coerced to a high-but-not-max tier (8) rather than the absolute-conservative
    10: still a premium tier capable of any verification logic, but cheaper than defaulting to the
    absolute highest tier for what may not require it. A synthetic justification is stamped so the
    written artifact still satisfies the required schema field.
    """
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if not isinstance(task, dict):
            continue
        complexity = task.get("complexity")
        if not isinstance(complexity, int) or isinstance(complexity, bool) or complexity < 1 or complexity > 10:
            task["complexity"] = 8
            task.setdefault(
                "complexity_justification",
                "Auto-injected by finalize after adjudication; defaulted to tier 8 "
                "because the model never scored this task — verification/gate tasks are read-and-check work.",
            )
        justification = task.get("complexity_justification")
        if not isinstance(justification, str) or not justification.strip():
            task["complexity_justification"] = (
                "Auto-injected by finalize after adjudication; no model-supplied justification."
            )


def _finalize_task_signature(task: dict[str, Any]) -> str | None:
    task_id = task.get("id")
    complexity = task.get("complexity")
    if (
        not isinstance(task_id, str)
        or not task_id.strip()
        or not isinstance(complexity, int)
        or isinstance(complexity, bool)
    ):
        return None
    return f"finalize:task_id={task_id}:complexity={complexity}"


def _attach_calibration_route_reports(
    plan_dir: Path,
    payload: dict[str, Any],
    state: PlanState,
) -> None:
    if not calibration_query_route_on():
        return
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return
    tier_models = state.get("config", {}).get("tier_models")
    for task in tasks:
        if not isinstance(task, dict):
            continue
        signature = _finalize_task_signature(task)
        if signature is None:
            continue
        suggestion = query_route_if_enabled(
            signature,
            plan_dir=plan_dir,
            taint_class=None,
            exploration_budget=0.0,
            default_tier=task["complexity"],
            tier_models=tier_models,
        )
        metadata = task.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            task["metadata"] = metadata
        metadata["calibration_route_report"] = {
            "task_signature": signature,
            "authoritative_complexity": task["complexity"],
            "authoritative_complexity_justification": task.get("complexity_justification"),
            "suggestion": suggestion.to_json() if suggestion is not None else None,
        }


def _task_evaluand_ref(task: dict[str, Any]) -> EvaluandRef | None:
    metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    candidates = (
        task.get("evaluand_ref"),
        metadata.get("evaluand_ref"),
        metadata.get("calibration_evaluand_ref"),
        metadata.get("evaluand"),
        metadata.get("evaluand_record"),
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            if {"piece_version", "judge_version", "rubric_version", "input_set_hash"} <= set(candidate):
                return EvaluandRef.from_json(candidate)
            attribution_key = candidate.get("attribution_key")
            if isinstance(attribution_key, (list, tuple)) and len(attribution_key) == 4:
                piece_version, judge_version, rubric_version, input_set_hash = attribution_key
                return EvaluandRef(
                    piece_version=str(piece_version),
                    judge_version=str(judge_version),
                    rubric_version=str(rubric_version),
                    input_set_hash=str(input_set_hash),
                )
    return None


def _task_execute_claim_context(
    plan_dir: Path,
    state: PlanState,
) -> dict[str, dict[str, Any]]:
    history_by_output: dict[str, dict[str, Any]] = {
        str(entry["output_file"]): entry
        for entry in state.get("history", [])
        if isinstance(entry, dict)
        and entry.get("step") == "execute"
        and isinstance(entry.get("output_file"), str)
    }
    aggregate_tier_by_batch: dict[int, dict[str, Any]] = {}
    for entry in state.get("history", []):
        if not isinstance(entry, dict) or entry.get("step") != "execute":
            continue
        batch_to_tier = entry.get("batch_to_tier")
        if not isinstance(batch_to_tier, list):
            continue
        for batch_entry in batch_to_tier:
            if not isinstance(batch_entry, dict):
                continue
            raw_batch_number = batch_entry.get("batch_number")
            if isinstance(raw_batch_number, int) and not isinstance(raw_batch_number, bool):
                aggregate_tier_by_batch[raw_batch_number] = batch_entry
    context_by_task_id: dict[str, dict[str, Any]] = {}
    for batch_path in sorted(list_batch_artifacts(plan_dir)):
        history = history_by_output.get(batch_path.name)
        batch_number = batch_artifact_index(batch_path)
        aggregate_tier = aggregate_tier_by_batch.get(batch_number) if batch_number is not None else None
        if history is None and aggregate_tier is None:
            continue
        batch_data = read_json(batch_path)
        task_updates = batch_data.get("task_updates", [])
        if not isinstance(task_updates, list):
            continue
        history = history or {}
        aggregate_tier = aggregate_tier or {}
        routed_model_identity = (
            history.get("tier_model_resolved")
            or aggregate_tier.get("tier_model_resolved")
            or aggregate_tier.get("resolved_model")
        )
        context = {
            "cost_usd": history.get("cost_usd"),
            "predicted_tier": history.get(
                "tier_projected",
                history.get(
                    "batch_complexity",
                    aggregate_tier.get("projected_tier", aggregate_tier.get("batch_complexity")),
                ),
            ),
            "routed_model_identity": routed_model_identity,
            "counterfactual_tag": history.get(
                "tier_counterfactual_tag",
                history.get(
                    "tier_exploration_tag",
                    aggregate_tier.get("counterfactual_tag", aggregate_tier.get("exploration_tag")),
                ),
            ),
            "low_confidence_signal": bool(
                history.get("tier_low_confidence", aggregate_tier.get("low_confidence", False))
            ),
            "route_phase": "execute",
            "routed_tier_spec": history.get("tier_model_spec", aggregate_tier.get("tier_model_spec")),
        }
        for update in task_updates:
            if isinstance(update, dict) and isinstance(update.get("task_id"), str):
                context_by_task_id[update["task_id"]] = context
    return context_by_task_id


def _verifier_identity_from_record(record: Any) -> str:
    provenance = record.provenance if isinstance(getattr(record, "provenance", None), dict) else {}
    for key in ("verifier_identity", "verifier_model_identity", "model_identity"):
        value = provenance.get(key)
        if isinstance(value, str) and value.strip():
            return value
    model_name = provenance.get("verifier_model")
    reported_version = provenance.get("verifier_version")
    if isinstance(model_name, str) and model_name.strip():
        rv = str(reported_version) if reported_version is not None else None
        return ModelIdentity(model_name, rv).identity
    piece_version = getattr(record, "piece_version", None)
    judge_version = getattr(record, "judge_version", None)
    return ModelIdentity(
        str(piece_version or judge_version or "unknown-verifier"),
        str(judge_version) if judge_version is not None else None,
    ).identity


def _write_capability_claims_from_finalize(
    plan_dir: Path,
    payload: dict[str, Any],
    state: PlanState,
) -> None:
    if not calibration_query_route_on():
        return
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return
    evaluands = read_evaluand_events(plan_dir, strict=False)
    execute_context = _task_execute_claim_context(plan_dir, state)
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            continue
        task_signature = _finalize_task_signature(task)
        evaluand_ref = _task_evaluand_ref(task)
        if task_signature is None or evaluand_ref is None:
            continue
        record = evaluands.get(evaluand_ref.key)
        if record is None:
            continue
        task_context = execute_context.get(task_id, {})
        predicted_tier_raw = task_context.get("predicted_tier", task.get("complexity"))
        predicted_tier = (
            int(predicted_tier_raw)
            if isinstance(predicted_tier_raw, int) and not isinstance(predicted_tier_raw, bool)
            else None
        )
        verifier_tier_raw = record.provenance.get("verifier_tier") if isinstance(record.provenance, dict) else None
        verifier_tier = str(verifier_tier_raw) if verifier_tier_raw is not None else "4"
        verifier_identity = _verifier_identity_from_record(record)
        low_confidence_signal = bool(task_context.get("low_confidence_signal", False))
        if not low_confidence_signal:
            low_confidence_signal, _ = check_reviewer_invariant(
                verifier_tier=verifier_tier,
                routed_model_tier=predicted_tier,
            )
        taint_class, _ = classify_claim_taint(tuple(record.taint))
        claim = CapabilityClaim(
            outcome=evaluand_ref,
            task_signature=task_signature,
            routed_model=str(task_context["routed_model_identity"])
            if task_context.get("routed_model_identity") is not None
            else verifier_identity,
            recorded_at=float(getattr(record, "recorded_at", 0.0) or 0.0),
            verifier_tier=verifier_tier,
            verifier_identity=verifier_identity,
            counterfactual_tag=str(task_context["counterfactual_tag"])
            if task_context.get("counterfactual_tag") is not None
            else None,
            low_confidence_signal=low_confidence_signal,
            taint_class=taint_class,
            predicted_tier=predicted_tier,
            route_phase=str(task_context["route_phase"])
            if task_context.get("route_phase") is not None
            else None,
            routed_tier_spec=str(task_context["routed_tier_spec"])
            if task_context.get("routed_tier_spec") is not None
            else None,
            cost_usd=float(task_context["cost_usd"])
            if task_context.get("cost_usd") is not None
            else None,
        )
        write_capability_claim(
            claim,
            plan_dir=plan_dir,
            phase="execute",
            scope="calibration",
        )


def _resolve_evidence_base_ref(project_dir: Path) -> str | None:
    """Compute a stable base ref for the evidence window.

    Uses ``git merge-base`` with the configured base branch (default
    ``main``) so downstream evidence validation can anchor its diff
    window.  Returns ``None`` when git is unavailable or the merge-base
    cannot be resolved.
    """
    import subprocess as _subprocess

    try:
        proc = _subprocess.run(
            ["git", "merge-base", "HEAD", "origin/main"],
            cwd=str(project_dir),
            text=True,
            capture_output=True,
            timeout=15,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (FileNotFoundError, _subprocess.TimeoutExpired, OSError):
        pass

    # Fallback: try local main / master
    for base in ("main", "master"):
        try:
            proc = _subprocess.run(
                ["git", "merge-base", "HEAD", base],
                cwd=str(project_dir),
                text=True,
                capture_output=True,
                timeout=15,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except (FileNotFoundError, _subprocess.TimeoutExpired, OSError):
            pass

    return None


def _current_plan_changed_files(project_dir: Path, state: PlanState) -> tuple[list[str], str | None]:
    snapshot, error = _capture_git_status_snapshot_recursive(project_dir)
    if error is not None:
        return [], error

    meta = state.get("meta") if isinstance(state, dict) else {}
    baseline = (
        meta.get("execution_baseline")
        if isinstance(meta, dict) and isinstance(meta.get("execution_baseline"), dict)
        else None
    )
    baseline_paths = baseline.get("paths") if isinstance(baseline, dict) else None
    if not isinstance(baseline_paths, dict):
        baseline_paths = None

    changed: list[str] = []
    for path, current_hash in sorted(snapshot.items()):
        if path.endswith("/") or _is_harness_generated_path(path):
            continue
        # Plan artifacts are harness churn; counting them here would turn a
        # missing metadata blast-radius into a non-Python full-suite fallback.
        if path == ".megaplan" or path.startswith(".megaplan/"):
            continue
        if baseline_paths is not None and baseline_paths.get(path) == current_hash:
            continue
        changed.append(path)
    return changed, None


def _planned_task_changed_files(payload: dict[str, Any]) -> list[str]:
    """Return planned changed files declared by finalize tasks.

    Baseline capture runs before execution, so the worktree is usually clean.
    In that state a dirty-tree fallback cannot infer a scoped test command. The
    finalized task graph is the stable pre-execute declaration of intended file
    changes; deterministic test-selection code can use it as a floor without
    letting the model author the final pytest command.
    """
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return []

    paths: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        write_set = task.get("write_set")
        raw_files = write_set.get("paths") if isinstance(write_set, Mapping) else None
        if not isinstance(raw_files, list):
            raw_files = task.get("files_changed")
        if not isinstance(raw_files, list):
            continue
        for raw_path in raw_files:
            if not isinstance(raw_path, str):
                continue
            path = raw_path.strip().lstrip("./")
            if not path or path in seen:
                continue
            if path == ".megaplan" or path.startswith(".megaplan/"):
                continue
            seen.add(path)
            paths.append(path)
    return paths


def _repo_pytest_path_args(command: str) -> list[str]:
    """Extract repository test path selectors from one shell command."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return []

    runner_index: int | None = None
    runner_kind: str | None = None
    for index, part in enumerate(parts):
        if part == "pytest" or part.endswith("/pytest"):
            runner_index = index
            runner_kind = "pytest"
            break
        if part == "node" and index + 1 < len(parts) and parts[index + 1] == "--test":
            runner_index = index + 1
            runner_kind = "node_test"
            break
    if runner_index is None:
        return []

    paths: list[str] = []
    for part in parts[runner_index + 1 :]:
        if not part or part.startswith("-"):
            continue
        path = part.strip().lstrip("./")
        path_part = path.split("::", 1)[0]
        if (
            path_part == "tests"
            or path_part.startswith("tests/")
            or path_part.endswith(".py")
        ):
            paths.append(path)
            continue
        if runner_kind == "node_test" and path_part.endswith((".mjs", ".cjs", ".js")):
            paths.append(path)
    return paths


def _planned_task_pytest_command(payload: dict[str, Any]) -> str | None:
    """Build one scoped test command from finalize task validation commands."""
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return None

    paths: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        narrow_tests = task.get("narrow_tests")
        selectors = narrow_tests.get("selectors") if isinstance(narrow_tests, Mapping) else None
        if isinstance(selectors, list):
            for selector in selectors:
                if isinstance(selector, str) and selector.strip() and selector not in seen:
                    seen.add(selector)
                    paths.append(selector.strip())
        commands = task.get("commands_run")
        if not isinstance(commands, list):
            continue
        for command in commands:
            if not isinstance(command, str):
                continue
            for path in _repo_pytest_path_args(command):
                if path in seen:
                    continue
                seen.add(path)
                paths.append(path)

    if not paths:
        return None
    if all(path.endswith((".mjs", ".cjs", ".js")) for path in paths):
        return "node --test " + " ".join(shlex.quote(path) for path in paths)
    return "pytest " + " ".join(shlex.quote(path) for path in paths)


def _scoped_command_from_blast_radius(radius: dict[str, Any]) -> str | None:
    if radius.get("strategy") != "scoped":
        return None
    selectors = radius.get("selectors")
    if not isinstance(selectors, list) or not selectors:
        return None

    paths: list[str] = []
    seen: set[str] = set()
    for selector in selectors:
        if not isinstance(selector, dict) or selector.get("kind") != "path":
            return None
        value = selector.get("value")
        if not isinstance(value, str) or not value.strip():
            continue
        path = value.strip()
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
    if not paths:
        return None
    if all(path.endswith((".mjs", ".cjs", ".js")) for path in paths):
        return "node --test " + " ".join(shlex.quote(path) for path in paths)
    return "pytest " + " ".join(shlex.quote(path) for path in paths)


def _fallback_baseline_test_selection(
    plan_dir: Path,
    state: PlanState,
    project_dir: Path,
    resolved: dict[str, Any],
    planned_files: list[str] | None = None,
    planned_test_command: str | None = None,
) -> dict[str, Any]:
    config = state.get("config", {}) if isinstance(state, dict) else {}
    if config.get("test_selection", "scoped") == "full":
        return resolved
    if resolved.get("command_override"):
        return resolved

    if planned_test_command:
        return {
            "mode": "scoped",
            "reason": (
                f"{resolved.get('reason') or 'Scoped baseline selection is unresolved'}; "
                "parsed scoped pytest command from finalize task validation commands."
            ),
            "command_override": planned_test_command,
            "selectors_used": [],
            "fallback_attempted": True,
            "fallback_source": "finalize_task_commands_run",
        }

    planned_files = planned_files or []
    if planned_files:
        radius = compute_test_blast_radius(planned_files, project_dir)
        command = _scoped_command_from_blast_radius(radius)
        if command is not None:
            return {
                "mode": "scoped",
                "reason": (
                    f"{resolved.get('reason') or 'Scoped baseline selection is unresolved'}; "
                    "computed scoped pytest "
                    f"command from {len(planned_files)} finalize task file(s)."
                ),
                "command_override": command,
                "selectors_used": radius.get("selectors", []),
                "fallback_attempted": True,
                "fallback_changed_files": planned_files,
                "fallback_blast_radius": radius,
                "fallback_source": "finalize_task_files_changed",
            }

    return {
        **resolved,
        "reason": (
            str(resolved.get("reason") or "Scoped baseline selection is unresolved")
            + "; no finalize task pytest command or mappable planned files were available"
        ),
        "fallback_attempted": True,
        "fallback_reason": (
            "Finalize baseline selection intentionally does not infer scope from "
            "current git status; tests must come from plan metadata or finalized task declarations."
        ),
    }


def _require_explicit_finalize_baseline_selection(test_selection: dict[str, Any]) -> None:
    mode = test_selection.get("mode")
    if mode == "full":
        return
    if mode == "scoped" and test_selection.get("command_override"):
        return
    raise FinalizeBaselineSelectionError(test_selection)


def _route_finalize_baseline_selection_failure_to_revise(
    plan_dir: Path,
    state: PlanState,
    worker: WorkerResult,
    error: FinalizeBaselineSelectionError,
) -> StepResponse:
    projection = _finalize_revise_fallback_projection()
    message = _finalize_baseline_contract_message(error.test_selection)
    prior_gate_contract: dict[str, Any] = {}
    for prior_name in ("gate_carry.json", "gate.json"):
        prior_path = plan_dir / prior_name
        if not prior_path.exists():
            continue
        prior = read_json(prior_path)
        if isinstance(prior, Mapping):
            prior_gate_contract = project_schema_owned_fields(
                prior,
                SCHEMAS["gate.json"],
                contract="finalize revise gate preservation",
            )
            break
    gate_feedback = {
        **prior_gate_contract,
        "recommendation": "ITERATE",
        "passed": False,
        "rationale": message,
        "signals_assessment": (
            "Finalize baseline selection could not establish a trusted scoped "
            "test command from plan metadata or finalized task declarations."
        ),
        "warnings": [
            "Code-mode plans that require tests must carry machine-readable "
            "`test_blast_radius` metadata before finalize.",
            "Finalize refused to infer scope from current git status and refused "
            "to run the full suite implicitly.",
        ],
        "criteria_check": {
            "finalize_baseline_test_scope": {
                "passed": False,
                "message": message,
                "requires_revise": True,
            }
        },
        "preflight_results": {},
        "unresolved_flags": [
            {
                "id": "finalize-baseline-test-scope",
                "severity": "significant",
                "status": "open",
                "concern": (
                    "Plan metadata lacks a trusted scoped baseline test contract "
                    "for code-mode work."
                ),
                "evidence": message,
                "category": "verification_contract",
            }
        ],
        "addressed_flags": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": prior_gate_contract.get("accepted_tradeoffs", []),
        "settled_decisions": prior_gate_contract.get("settled_decisions", []),
        "north_star_actions": prior_gate_contract.get("north_star_actions", []),
        "orchestrator_guidance": (
            "Run revise. The revised plan must add structured `test_blast_radius` "
            "metadata with scoped path selectors, or explicitly opt into "
            "`test_selection=full` if that is intentional."
        ),
        "signals": {},
        "finalize_failure": {
            "code": "missing_scoped_baseline_test_contract",
            "test_selection": error.test_selection,
        },
    }
    require_schema_fields(
        gate_feedback,
        SCHEMAS["gate.json"],
        contract="finalize revise gate persistence",
    )
    state["current_state"] = projection["state"]
    from arnold_pipelines.megaplan.handlers.gate import (
        _build_gate_carry,
        _sync_legacy_last_gate_for_workflow,
    )

    _sync_legacy_last_gate_for_workflow(state, gate_feedback)
    meta = state.setdefault("meta", {})
    if isinstance(meta, dict):
        meta.setdefault("finalize_revise_feedback", []).append(
            {
                "code": "missing_scoped_baseline_test_contract",
                "message": message,
                "test_selection": error.test_selection,
            }
        )
    atomic_write_json(plan_dir / "gate.json", gate_feedback)
    atomic_write_json(
        plan_dir / "gate_carry.json",
        {
            **_build_gate_carry(
                gate_feedback,
                iteration=state["iteration"],
            ),
            "source": "finalize_baseline_selection",
        },
    )
    atomic_write_json(
        plan_dir / "finalize_revise_feedback.json",
        {
            "code": "missing_scoped_baseline_test_contract",
            "message": message,
            "next_step": "revise",
            "test_selection": error.test_selection,
        },
    )
    record_step_failure(
        plan_dir,
        state,
        step="finalize",
        iteration=state["iteration"],
        error=CliError(
            "missing_scoped_baseline_test_contract",
            message,
            valid_next=["revise"],
            extra={"raw_output": worker.raw_output, "test_selection": error.test_selection},
        ),
        duration_ms=worker.duration_ms,
    )
    response: StepResponse = {
        "success": False,
        "step": "finalize",
        "result": "plan_contract_revise_needed",
        "route_signal": projection["route_signal"],
        "summary": message,
        "artifacts": ["gate.json", "gate_carry.json", "finalize_revise_feedback.json"],
        "next_step": projection["next_step"],
        "state": projection["state"],
        "iteration": state["iteration"],
        "details": {
            "code": "missing_scoped_baseline_test_contract",
            "test_selection": error.test_selection,
        },
    }
    _attach_next_step_runtime(response)
    return response


def _route_finalize_task_feasibility_failure_to_revise(
    plan_dir: Path,
    state: PlanState,
    worker: WorkerResult,
    error: TaskFeasibilityError,
) -> StepResponse:
    """Persist final-stage sense-check evidence and route an infeasible DAG to revise."""

    projection = _finalize_revise_fallback_projection()
    diagnostics = error.report.get("diagnostics", [])
    codes = [str(item.get("code")) for item in diagnostics if isinstance(item, Mapping)]
    message = (
        "Finalize rejected the executable task graph at the post-finalization "
        f"feasibility gate ({', '.join(codes)}). Preserve legitimate dependencies, "
        "but split oversized objectives/paths/tests and remove routing-only edges."
    )
    prior_gate_contract: dict[str, Any] = {}
    for prior_name in ("gate_carry.json", "gate.json"):
        prior_path = plan_dir / prior_name
        if not prior_path.exists():
            continue
        prior = read_json(prior_path)
        if isinstance(prior, Mapping):
            prior_gate_contract = project_schema_owned_fields(
                prior,
                SCHEMAS["gate.json"],
                contract="finalize feasibility gate preservation",
            )
            break
    gate_feedback = {
        **prior_gate_contract,
        "recommendation": "ITERATE",
        "passed": False,
        "rationale": message,
        "signals_assessment": "The model-authored DAG is not executable within bounded task and phase budgets.",
        "warnings": [message],
        "criteria_check": {
            "finalized_task_feasibility": {
                "passed": False,
                "message": message,
                "requires_revise": True,
            }
        },
        "preflight_results": {},
        "unresolved_flags": [
            {
                "id": "finalized-task-feasibility",
                "severity": "significant",
                "status": "open",
                "concern": "The finalized graph exceeds executable task, dependency, path, or test budgets.",
                "evidence": ", ".join(codes),
                "category": "execution_feasibility",
            }
        ],
        "addressed_flags": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": prior_gate_contract.get("accepted_tradeoffs", []),
        "settled_decisions": prior_gate_contract.get("settled_decisions", []),
        "north_star_actions": prior_gate_contract.get("north_star_actions", []),
        "orchestrator_guidance": (
            "Run revise, then finalize again. Each task must have one <=15-minute objective, "
            "<=5 declared paths, and <=3 narrow selectors/120 seconds/2 runs; every edge "
            "must cite a concrete consumed output, write order, or human prerequisite."
        ),
        "signals": {},
        "finalize_failure": {
            "code": "finalized_task_feasibility_failed",
            "diagnostic_codes": codes,
            "task_contract_hash": error.report.get("task_contract_hash"),
        },
    }
    require_schema_fields(
        gate_feedback,
        SCHEMAS["gate.json"],
        contract="finalize feasibility revise gate persistence",
    )
    state["current_state"] = projection["state"]
    from arnold_pipelines.megaplan.handlers.gate import (
        _build_gate_carry,
        _sync_legacy_last_gate_for_workflow,
    )

    _sync_legacy_last_gate_for_workflow(state, gate_feedback)
    state.setdefault("meta", {}).setdefault("finalize_revise_feedback", []).append(
        {"code": "finalized_task_feasibility_failed", "message": message, "diagnostic_codes": codes}
    )
    atomic_write_json(plan_dir / "gate.json", gate_feedback)
    atomic_write_json(
        plan_dir / "gate_carry.json",
        {
            **_build_gate_carry(gate_feedback, iteration=state["iteration"]),
            "source": "finalize_task_feasibility",
        },
    )
    atomic_write_json(
        plan_dir / "finalize_revise_feedback.json",
        {
            "code": "finalized_task_feasibility_failed",
            "message": message,
            "next_step": "revise",
            "diagnostic_codes": codes,
            "report_artifact": "task_feasibility.json",
        },
    )
    record_step_failure(
        plan_dir,
        state,
        step="finalize",
        iteration=state["iteration"],
        error=CliError(
            "finalized_task_feasibility_failed",
            message,
            valid_next=["revise"],
            extra={"raw_output": worker.raw_output, "task_feasibility": error.report},
        ),
        duration_ms=worker.duration_ms,
    )
    response: StepResponse = {
        "success": False,
        "step": "finalize",
        "result": "plan_contract_revise_needed",
        "route_signal": projection["route_signal"],
        "summary": message,
        "artifacts": [
            "task_feasibility.json",
            "gate.json",
            "gate_carry.json",
            "finalize_revise_feedback.json",
        ],
        "next_step": projection["next_step"],
        "state": projection["state"],
        "iteration": state["iteration"],
        "details": {"code": "finalized_task_feasibility_failed", "diagnostic_codes": codes},
    }
    _attach_next_step_runtime(response)
    return response


def _reject_finalize_unresolved_north_star(plan_dir: Path, state: PlanState) -> None:
    """Reject finalize when carried blocking North Star actions remain unresolved.

    Compares the carried blocking actions from ``gate_carry.json`` (or
    ``gate.json``) against the ``north_star_actions_addressed[]`` metadata
    persisted by the latest revise step.  Absent, malformed, or incomplete
    addressed metadata is treated as all-carried-blocking-unresolved
    (fail-closed, SD1).

    Raises :class:`CliError` via ``record_step_failure`` when unresolved
    blockers are found, preventing finalize from producing executable tasks
    while blocking North Star actions are not concretely addressed.
    """
    from arnold_pipelines.megaplan.north_star_actions import (
        blocking_north_star_actions,
        find_unresolved_blocking_actions,
        read_carried_north_star_actions,
    )

    carried = read_carried_north_star_actions(plan_dir)
    carried_blocking = blocking_north_star_actions(carried)
    if not carried_blocking:
        return  # nothing to block on

    # Read latest revise metadata for north_star_actions_addressed[].
    # When the plan has never been revised (e.g. bare-mode plan→finalize
    # that somehow reached GATED) the metadata is absent → fail-closed.
    meta_path = latest_plan_meta_path(plan_dir, state)
    meta: dict[str, Any] | None = None
    if meta_path.exists():
        try:
            meta = read_json(meta_path)
        except Exception:
            meta = None

    addressed: list[dict[str, Any]] | None = None
    if isinstance(meta, dict):
        raw_addressed = meta.get("north_star_actions_addressed")
        if isinstance(raw_addressed, list):
            addressed = raw_addressed

    unresolved = find_unresolved_blocking_actions(
        carried_blocking=carried_blocking,
        addressed=addressed,
    )

    if unresolved:
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
        reasons = ", ".join(
            f"{reason}={count}" for reason, count in reason_counts.items()
        )
        message = (
            f"Finalize blocked: {len(unresolved)} carried blocking North Star "
            f"action(s) unresolved ({bullet_ids}) [{reasons}]. Each blocking "
            "action needs a north_star_actions_addressed record in the latest "
            "revise metadata with concrete plan_refs and the matching "
            "action_type marker. Re-run revise to address these actions before "
            "finalize can produce executable tasks."
        )
        error = CliError(
            "north_star_finalize_unresolved_blocking",
            message,
            valid_next=infer_next_steps(state),
            extra={
                "step": "finalize",
                "unresolved_actions": summaries,
                "count": len(unresolved),
            },
        )
        record_step_failure(
            plan_dir,
            state,
            step="finalize",
            iteration=state["iteration"],
            error=error,
        )
        raise error


def _write_finalize_artifacts(plan_dir: Path, payload: dict[str, Any], state: PlanState) -> str:
    contract_payload = normalize_contract_payload(
        {
            "provides": payload.get("provides", []),
            "assumes": payload.get("assumes", []),
            "pre_existing": payload.get("pre_existing", []),
        },
        root=Path(state["config"]["project_dir"]),
    )
    payload["provides"] = contract_payload["provides"]
    payload["assumes"] = contract_payload["assumes"]
    payload["pre_existing"] = contract_payload["pre_existing"]
    # Apply all task-graph mutations first, then run the deterministic final
    # sense-check. Baseline capture and evidence projection must not be able to
    # change the admitted executable contract afterward.
    _ensure_verification_task(payload, state)
    if state["config"].get("mode") not in {"doc", "joke"}:
        _ensure_user_actions_pre_gate_task(payload, state)
        _ensure_user_actions_post_gate_task(payload, state)
    _apply_programmatic_coverage(payload, plan_dir, state)
    _normalize_task_complexity(payload)
    # ── M8A T4: Compile harness-owned validation jobs after handler task
    # mutations and before the first feasibility pass so the task contract
    # hash reconciles the generated jobs from the start.  The model emits
    # validation_jobs: []; the handler owns derivation.
    from arnold_pipelines.megaplan.orchestration.validation_jobs import (
        compile_validation_jobs,
    )
    payload["validation_jobs"] = compile_validation_jobs(payload)
    # ───────────────────────────────────────────────────────────────────
    if state["config"].get("mode", "code") == "code":
        feasibility = compile_task_feasibility(payload, state.get("config", {}))
        atomic_write_json(plan_dir / "task_feasibility.json", feasibility)
        if not feasibility["admitted"]:
            raise TaskFeasibilityError(feasibility)
        payload["graph_report"] = feasibility

    if state["config"].get("mode") in {"doc", "joke"}:
        payload["baseline_test_failures"] = None
        payload["baseline_test_command"] = None
        payload["baseline_test_note"] = "Test baseline not applicable in doc mode."
    else:
        _config = dict(state.get("config", {}))
        _config["plan_dir"] = str(plan_dir)

        # ── M4 T5: Resolve plan blast radius before baseline capture ──────
        project_dir = Path(_config["project_dir"])
        test_selection = _fallback_baseline_test_selection(
            plan_dir,
            state,
            project_dir,
            resolve_baseline_test_selection(plan_dir, state),
            planned_files=_planned_task_changed_files(payload),
            planned_test_command=_planned_task_pytest_command(payload),
        )
        _require_explicit_finalize_baseline_selection(test_selection)
        if test_selection["mode"] == "scoped" and test_selection.get("command_override"):
            _config["test_command"] = test_selection["command_override"]
        payload["test_selection"] = test_selection
        # ──────────────────────────────────────────────────────────────────

        # ── M4 T8: Compute evidence base_ref for downstream consumers ─────
        payload["evidence_base_ref"] = _resolve_evidence_base_ref(project_dir)
        # ──────────────────────────────────────────────────────────────────

        if test_selection.get("mode") == "none":
            baseline = {
                "baseline_test_failures": None,
                "baseline_test_command": None,
                "baseline_test_note": test_selection.get("reason")
                or "No baseline tests apply for this plan.",
            }
        else:
            baseline = _capture_test_baseline_for_plan(plan_dir, project_dir, _config)
        payload.update(baseline)
        _ensure_verification_task(payload, state)
    _attach_calibration_route_reports(plan_dir, payload, state)
    _write_capability_claims_from_finalize(plan_dir, payload, state)
    _reconcile_validation_after_mutation(payload)
    # Finalization and baseline helpers may mutate the graph after the first
    # feasibility pass. Recompile at the final persistence boundary and bind
    # critique clearance only to these exact bytes.
    if state["config"].get("mode", "code") == "code":
        feasibility = compile_task_feasibility(payload, state.get("config", {}))
        atomic_write_json(plan_dir / "task_feasibility.json", feasibility)
        if not feasibility["admitted"]:
            raise TaskFeasibilityError(feasibility)
        payload["graph_report"] = feasibility
    clearance_path = plan_dir / "critique_clearance.json"
    if clearance_path.exists():
        bind_finalize_custody(plan_dir, payload, read_json(clearance_path))
    atomic_write_json(plan_dir / "contract.json", contract_payload)
    write_plan_artifact_json(
        plan_dir, "finalize.json", payload,
        contract_context=create_step_io_contract_context(
            operation=StepIOOperation.WRITE,
            explicit_root=plan_dir,
        ),
    )
    atomic_write_json(plan_dir / "finalize_snapshot.json", payload)
    atomic_write_text(plan_dir / "user_actions.md", _render_user_actions_md(payload))
    atomic_write_text(plan_dir / "final.md", render_final_md(payload))
    return sha256_file(plan_dir / "finalize.json")


def _ensure_execution_baseline(state: PlanState) -> None:
    meta = state.setdefault("meta", {})
    project_dir = Path(state["config"]["project_dir"])
    existing = meta.get("execution_baseline")
    if isinstance(existing, dict):
        baseline_head = existing.get("head")
        try:
            current_head = _git_head(project_dir)
        except Exception:
            current_head = None
        if (
            isinstance(baseline_head, str)
            and baseline_head.strip()
            and current_head
            and baseline_head.strip() == current_head
        ):
            return
    try:
        baseline = capture_uncommitted_baseline(project_dir)
    except Exception as exc:
        meta["execution_baseline_warning"] = (
            f"Failed to capture execution baseline: {exc}"
        )
        LOGGER.warning("Failed to capture execution baseline", exc_info=True)
        return
    meta["execution_baseline"] = baseline
    count = len(baseline.get("paths", {})) if isinstance(baseline.get("paths"), dict) else 0
    action = "Captured"
    if isinstance(existing, dict):
        action = "Refreshed"
    print(
        f"{action} execution baseline: {count} pre-existing uncommitted paths. "
        "Unchanged paths will be excluded from ownership audits.",
        file=sys.stderr,
    )

_FINALIZE_SCRATCH_KNOWN_KEYS: frozenset[str] = schema_property_names(
    _FINALIZE_INPUT_SCHEMA,
    contract="finalize scratch promotion",
)


def _finalize_scratch_known_keys() -> frozenset[str]:
    return schema_property_names(
        _FINALIZE_INPUT_SCHEMA,
        contract="finalize scratch promotion",
    )


def handle_finalize(root: Path, args: argparse.Namespace) -> StepResponse:
    with load_plan_locked(root, args.plan, step="finalize") as (plan_dir, state):
        allowed_states = {STATE_GATED}
        robustness = configured_robustness(state)
        if robustness == "bare" or (is_creative_mode(state) and robustness == "light"):
            allowed_states.add(STATE_PLANNED)
        require_state(state, "finalize", allowed_states)

        try:
            write_critique_clearance(plan_dir, state)
        except CritiqueCustodyError as error:
            raise CliError(
                error.code,
                str(error),
                valid_next=["critique", "revise", "gate"],
                extra={"issues": list(error.issues)},
            ) from error

        from arnold_pipelines.megaplan.handlers.structured_output import (
            require_scratch_filename_for_phase,
        )

        scratch_filename = require_scratch_filename_for_phase("finalize")
        seed_json: str | None = None
        try:
            from arnold_pipelines.megaplan.prompts.finalize import _write_finalize_template

            seed_path = _write_finalize_template(plan_dir, state)
            seed_json = seed_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            seed_json = None

        worker, agent, mode, refreshed = _run_worker("finalize", state, plan_dir, args, root=root)

        # ── T8: Scratch promotion ──────────────────────────────────
        # Prefer valid filled finalize_output.json over worker.payload;
        # fall back to worker.payload when scratch is missing/unmodified;
        # fail hard on modified invalid scratch when file-fill was
        # instructed (hermes agent).
        from arnold_pipelines.megaplan.handlers.structured_output import (
            build_promotion_evidence,
            promote_scratch,
        )

        # Only the Hermes agent can receive file-fill instructions;
        # Shannon/Codex workers use inline JSON and should never
        # hard-fail on a modified invalid scratch.
        file_fill_instructed = agent == "hermes"

        scratch_status, promoted_payload = promote_scratch(
            plan_dir,
            scratch_filename,
            _finalize_scratch_known_keys(),
            worker,
            seed_json=seed_json,
            file_fill_instructed=file_fill_instructed,
        )
        worker.payload = promoted_payload

        # ── T9: Structured promotion evidence ────────────────────
        promotion_evidence = build_promotion_evidence(
            plan_dir,
            scratch_status,
            phase_identity="finalize",
            scratch_filename=scratch_filename,
            worker_payload_used=scratch_status in ("missing", "unmodified"),
        )
        if promotion_evidence:
            LOGGER.debug(
                "finalize promotion evidence: %s",
                [e["promotion_state"] for e in promotion_evidence],
            )
        # ────────────────────────────────────────────────────────────

        _validate_finalize_payload(plan_dir, state, worker)

        # North Star closeout gate: reject finalize when carried blocking
        # North Star actions are not concretely addressed in the latest
        # revise metadata. This prevents prose-only completion from
        # producing executable tasks while blocking actions remain open.
        _reject_finalize_unresolved_north_star(plan_dir, state)

        try:
            artifact_hash = _write_finalize_artifacts(plan_dir, worker.payload, state)
        except TaskFeasibilityError as error:
            return _route_finalize_task_feasibility_failure_to_revise(
                plan_dir,
                state,
                worker,
                error,
            )
        except FinalizeBaselineSelectionError as error:
            return _route_finalize_baseline_selection_failure_to_revise(
                plan_dir,
                state,
                worker,
                error,
            )
        success_projection = _finalize_success_projection()
        _ensure_execution_baseline(state)
        state["current_state"] = success_projection["state"]
        return _finish_step(
            plan_dir, state, args,
            step="finalize",
            worker=worker, agent=agent, mode=mode, refreshed=refreshed,
            summary=f"Finalized plan with {len(worker.payload['tasks'])} tasks and {len(worker.payload['watch_items'])} watch items.",
            artifacts=(
                ["contract.json", "final.md", "finalize.json", "user_actions.md"]
                + (["task_feasibility.json"] if state["config"].get("mode", "code") == "code" else [])
            ),
            output_file="finalize.json",
            artifact_hash=artifact_hash,
            next_step=success_projection["next_step"],
            response_fields={"route_signal": success_projection["route_signal"]},
        )
