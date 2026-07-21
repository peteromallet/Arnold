"""Deterministic admission checks for finalized executable task graphs.

The finalizer model proposes a graph; this module decides whether that graph is
small and well-evidenced enough to execute.  It is intentionally pure so the
same decision can be repeated at execute entry and compared by content hash.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from arnold_pipelines.megaplan._core.io import compute_task_batches


TASK_CONTRACT_VERSION = 2
MAX_OBJECTIVE_CHARS = 240
MAX_TASK_MINUTES = 15
MAX_WRITE_PATHS = 5
MAX_NARROW_SELECTORS = 3
MAX_NARROW_TEST_SECONDS = 120
MAX_NARROW_TEST_RUNS = 2
DEFAULT_EXECUTE_PHASE_SECONDS = 3600
_CHECKPOINT_RECORDS = {
    "completed_subobjectives",
    "remaining_subobjectives",
    "output_hashes",
    "test_state",
}
_DEPENDENCY_KINDS = {"consumes_output", "write_conflict", "human_prerequisite"}
_ROUTING_WORDS = {
    "routing",
    "model tier",
    "batch size",
    "batching",
    "authoring order",
    "keep separate",
    "isolate model",
}


@dataclass(frozen=True)
class FeasibilityDiagnostic:
    code: str
    message: str
    task_id: str | None = None
    dependency_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.task_id is not None:
            result["task_id"] = self.task_id
        if self.dependency_id is not None:
            result["dependency_id"] = self.dependency_id
        return result


def _stable_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for raw in payload.get("tasks", []) if isinstance(payload.get("tasks"), list) else []:
        if not isinstance(raw, Mapping):
            continue
        tasks.append(
            {
                key: raw.get(key)
                for key in (
                    "id",
                    "objective",
                    "description",
                    "kind",
                    "complexity",
                    "estimated_minutes",
                    "depends_on",
                    "dependency_reasons",
                    "routing_group",
                    "write_set",
                    "narrow_tests",
                    "checkpoint",
                )
            }
        )
    return {
        "task_contract_version": payload.get("task_contract_version"),
        "tasks": tasks,
        "validation_jobs": payload.get("validation_jobs", []),
    }


def task_contract_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _stable_contract(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _phase_timeout_minutes(config: Mapping[str, Any] | None) -> float:
    raw: Any = None
    if isinstance(config, Mapping):
        raw = config.get("phase_timeout_seconds", config.get("phase_timeout"))
    if not isinstance(raw, (int, float)) or isinstance(raw, bool) or raw <= 0:
        raw = DEFAULT_EXECUTE_PHASE_SECONDS
    return float(raw) / 60.0


def _longest_paths(
    tasks: list[dict[str, Any]],
    order: list[str],
) -> tuple[list[str], int, float]:
    by_id = {str(task.get("id")): task for task in tasks}
    weighted: dict[str, float] = {}
    counts: dict[str, int] = {}
    predecessors: dict[str, str | None] = {}
    for task_id in order:
        task = by_id[task_id]
        deps = [dep for dep in task.get("depends_on", []) if dep in weighted]
        predecessor = max(deps, key=lambda dep: (weighted[dep], counts[dep], dep)) if deps else None
        minutes = task.get("estimated_minutes")
        own = float(minutes) if _positive_int(minutes) else 0.0
        weighted[task_id] = own + (weighted[predecessor] if predecessor else 0.0)
        counts[task_id] = 1 + (counts[predecessor] if predecessor else 0)
        predecessors[task_id] = predecessor
    if not order:
        return [], 0, 0.0
    end = max(order, key=lambda task_id: (weighted[task_id], counts[task_id], task_id))
    path: list[str] = []
    cursor: str | None = end
    while cursor is not None:
        path.append(cursor)
        cursor = predecessors[cursor]
    path.reverse()
    return path, counts[end], weighted[end]


def _has_path(start: str, target: str, children: Mapping[str, set[str]]) -> bool:
    pending = [start]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(children.get(current, set()))
    return False


def compile_task_feasibility(
    payload: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic report and stable diagnostics for a v2 graph."""

    diagnostics: list[FeasibilityDiagnostic] = []
    raw_tasks = payload.get("tasks")
    tasks = [dict(task) for task in raw_tasks] if isinstance(raw_tasks, list) and all(isinstance(task, Mapping) for task in raw_tasks) else []
    if payload.get("task_contract_version") != TASK_CONTRACT_VERSION:
        diagnostics.append(
            FeasibilityDiagnostic(
                "task_contract_version_required",
                "New finalized plans must use task_contract_version=2.",
            )
        )
    if not isinstance(payload.get("validation_jobs"), list):
        diagnostics.append(
            FeasibilityDiagnostic(
                "validation_jobs_missing",
                "validation_jobs must be an array; harness-owned validation is not a model task.",
            )
        )

    ids: list[str] = []
    for index, task in enumerate(tasks, start=1):
        task_id = task.get("id") if isinstance(task.get("id"), str) else f"#{index}"
        if not isinstance(task.get("id"), str) or not task["id"].strip() or task["id"] in ids:
            diagnostics.append(FeasibilityDiagnostic("task_id_invalid", "Task IDs must be non-empty and unique.", str(task_id)))
            continue
        ids.append(task["id"])
        objective = task.get("objective")
        if not isinstance(objective, str) or not objective.strip():
            diagnostics.append(FeasibilityDiagnostic("task_objective_missing", "Task must declare one primary objective.", task["id"]))
        elif len(objective.strip()) > MAX_OBJECTIVE_CHARS or "\n" in objective or ";" in objective:
            diagnostics.append(FeasibilityDiagnostic("task_objective_oversized", f"Task objective must be one line without semicolon-separated objectives and <= {MAX_OBJECTIVE_CHARS} characters.", task["id"]))
        elif task.get("kind") == "test" and any(
            phrase in objective.lower()
            for phrase in ("full suite", "integration suite", "integration tests")
        ):
            diagnostics.append(FeasibilityDiagnostic("model_validation_job_forbidden", "Integration and full-suite validation must be a harness validation job, not a model task.", task["id"]))

        minutes = task.get("estimated_minutes")
        if not _positive_int(minutes) or minutes > MAX_TASK_MINUTES:
            diagnostics.append(FeasibilityDiagnostic("task_duration_exceeded", f"estimated_minutes must be an integer in 1..{MAX_TASK_MINUTES}; split larger work.", task["id"]))

        write_set = task.get("write_set")
        paths: list[str] = []
        if isinstance(write_set, Mapping) and write_set.get("complete") is True and isinstance(write_set.get("paths"), list):
            paths = [path.strip().replace("\\", "/") for path in write_set["paths"] if isinstance(path, str) and path.strip()]
        else:
            diagnostics.append(FeasibilityDiagnostic("write_set_missing", "Task must declare a complete write_set.", task["id"]))
        if isinstance(write_set, Mapping) and isinstance(write_set.get("paths"), list) and len(paths) != len(write_set["paths"]):
            diagnostics.append(FeasibilityDiagnostic("task_path_invalid", "write_set paths must be non-empty strings.", task["id"]))
        if len(paths) != len(set(paths)) or len(paths) > MAX_WRITE_PATHS:
            diagnostics.append(FeasibilityDiagnostic("task_path_budget_exceeded", f"write_set paths must be unique and contain at most {MAX_WRITE_PATHS} paths.", task["id"]))
        if task.get("kind") in {"code", "test", "docs"} and not paths:
            diagnostics.append(FeasibilityDiagnostic("write_set_missing", "Mutating tasks must declare at least one planned path.", task["id"]))

        narrow = task.get("narrow_tests")
        if not isinstance(narrow, Mapping):
            diagnostics.append(FeasibilityDiagnostic("task_test_budget_missing", "Task must declare its narrow test budget.", task["id"]))
        else:
            selectors = narrow.get("selectors")
            max_seconds = narrow.get("max_seconds")
            max_runs = narrow.get("max_runs")
            if not isinstance(selectors, list) or any(not isinstance(item, str) or not item.strip() for item in selectors) or len(selectors) > MAX_NARROW_SELECTORS:
                diagnostics.append(FeasibilityDiagnostic("task_test_selector_budget_exceeded", f"narrow_tests.selectors must contain at most {MAX_NARROW_SELECTORS} non-empty selectors.", task["id"]))
            elif any(
                selector.strip().rstrip("/") in {"test", "tests"}
                or selector.strip().endswith("/")
                for selector in selectors
            ):
                diagnostics.append(FeasibilityDiagnostic("task_test_selector_too_broad", "Narrow selectors must name bounded files/modules, not an entire test directory.", task["id"]))
            if not isinstance(max_seconds, int) or isinstance(max_seconds, bool) or not 0 <= max_seconds <= MAX_NARROW_TEST_SECONDS:
                diagnostics.append(FeasibilityDiagnostic("task_test_time_budget_exceeded", f"narrow_tests.max_seconds must be in 0..{MAX_NARROW_TEST_SECONDS}.", task["id"]))
            if not isinstance(max_runs, int) or isinstance(max_runs, bool) or not 0 <= max_runs <= MAX_NARROW_TEST_RUNS:
                diagnostics.append(FeasibilityDiagnostic("task_test_run_budget_exceeded", f"narrow_tests.max_runs must be in 0..{MAX_NARROW_TEST_RUNS}.", task["id"]))

        if isinstance(task.get("complexity"), int) and task["complexity"] >= 7:
            checkpoint = task.get("checkpoint")
            records = checkpoint.get("records") if isinstance(checkpoint, Mapping) else None
            interval = checkpoint.get("max_interval_seconds") if isinstance(checkpoint, Mapping) else None
            if not (
                isinstance(checkpoint, Mapping)
                and checkpoint.get("required") is True
                and isinstance(interval, int)
                and 0 < interval <= 300
                and isinstance(records, list)
                and _CHECKPOINT_RECORDS.issubset(set(records))
            ):
                diagnostics.append(FeasibilityDiagnostic("task_checkpoint_required", "Complexity >=7 requires a <=300-second residual checkpoint contract.", task["id"]))

    id_set = set(ids)
    children: dict[str, set[str]] = {task_id: set() for task_id in ids}
    edge_count = 0
    for task in tasks:
        task_id = task.get("id")
        if task_id not in id_set:
            continue
        deps = task.get("depends_on")
        reasons = task.get("dependency_reasons")
        if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps):
            diagnostics.append(FeasibilityDiagnostic("dependency_list_invalid", "depends_on must be a list of task IDs.", task_id))
            deps = []
        if len(deps) != len(set(deps)):
            diagnostics.append(FeasibilityDiagnostic("dependency_duplicate", "depends_on must not contain duplicate IDs.", task_id))
        reason_map = reasons if isinstance(reasons, Mapping) else {}
        if set(reason_map) != set(deps):
            diagnostics.append(FeasibilityDiagnostic("dependency_reason_missing", "Every dependency, and only a dependency, must have a dependency_reasons entry.", task_id))
        for dep in deps:
            edge_count += 1
            if dep not in id_set or dep == task_id:
                diagnostics.append(FeasibilityDiagnostic("dependency_unknown", "Dependency must reference a different finalized task.", task_id, dep))
                continue
            children[dep].add(task_id)
            evidence = reason_map.get(dep)
            if not isinstance(evidence, Mapping):
                diagnostics.append(FeasibilityDiagnostic("routing_dependency_forbidden", "Dependency evidence must be a semantic reason object; routing preferences are not valid dependencies.", task_id, dep))
                continue
            kind = evidence.get("kind")
            reason = evidence.get("reason")
            required_output = evidence.get("required_output")
            if kind not in _DEPENDENCY_KINDS:
                diagnostics.append(FeasibilityDiagnostic("routing_dependency_forbidden", f"Dependency kind '{kind!s}' is not a semantic dependency reason; only {sorted(_DEPENDENCY_KINDS)} are valid.", task_id, dep))
                continue
            if not isinstance(reason, str) or not reason.strip() or not isinstance(required_output, str) or not required_output.strip():
                diagnostics.append(FeasibilityDiagnostic("dependency_reason_invalid", "Dependency evidence requires an allowed kind, concrete reason, and required_output.", task_id, dep))
                continue
            lowered = reason.lower()
            if any(word in lowered for word in _ROUTING_WORDS):
                diagnostics.append(FeasibilityDiagnostic("routing_dependency_forbidden", "Routing, authoring order, and batch shape cannot create correctness dependencies.", task_id, dep))

    batches: list[list[str]] = []
    if ids and len(ids) == len(tasks):
        try:
            batches = compute_task_batches(tasks)
        except ValueError as exc:
            diagnostics.append(FeasibilityDiagnostic("dependency_graph_invalid", str(exc)))

    # Overlapping planned writes need either a real ordered path or an explicit
    # non-authoritative routing group.  This preserves legitimate dependencies
    # without manufacturing them solely to tune batches.
    for left_index, left in enumerate(tasks):
        left_id = left.get("id")
        left_paths = set((left.get("write_set") or {}).get("paths", [])) if isinstance(left.get("write_set"), Mapping) else set()
        if left_id not in id_set or not left_paths:
            continue
        for right in tasks[left_index + 1 :]:
            right_id = right.get("id")
            right_paths = set((right.get("write_set") or {}).get("paths", [])) if isinstance(right.get("write_set"), Mapping) else set()
            overlap = sorted(left_paths & right_paths)
            if right_id not in id_set or not overlap:
                continue
            ordered = _has_path(left_id, right_id, children) or _has_path(right_id, left_id, children)
            same_group = bool(left.get("routing_group")) and left.get("routing_group") == right.get("routing_group")
            if not ordered and not same_group:
                diagnostics.append(FeasibilityDiagnostic("write_overlap_unordered", f"Tasks {left_id} and {right_id} overlap on {overlap!r} without semantic order or a shared routing_group."))

    order = [task_id for batch in batches for task_id in batch]
    critical_ids, critical_count, critical_minutes = _longest_paths(tasks, order)
    task_count = len(tasks)
    seriality = (critical_count / task_count) if task_count else 0.0
    by_id = {task.get("id"): task for task in tasks}
    dispatch_minutes = sum(
        max((float(by_id[task_id].get("estimated_minutes", 0)) for task_id in batch), default=0.0)
        for batch in batches
    )
    timeout_minutes = _phase_timeout_minutes(config)
    if task_count >= 8 and seriality == 1.0:
        diagnostics.append(FeasibilityDiagnostic("serial_graph_unjustified", "A fully linear graph with 8 or more tasks cannot fit one execute phase; preserve valid edges but split/replan the milestone."))
    elif task_count >= 12 and seriality > 0.90:
        diagnostics.append(FeasibilityDiagnostic("serial_graph_unjustified", "A graph with 12 or more tasks may not put more than 90% of tasks on one critical path."))
    if critical_minutes > timeout_minutes * 0.80:
        diagnostics.append(FeasibilityDiagnostic("critical_path_infeasible", "Estimated critical path exceeds 80% of the configured execute-phase timeout."))
    if dispatch_minutes > timeout_minutes * 0.80:
        diagnostics.append(FeasibilityDiagnostic("dispatch_budget_infeasible", "Estimated sequential batch dispatch exceeds 80% of the configured execute-phase timeout."))

    report = {
        "schema_version": "megaplan-task-feasibility-v2",
        "task_contract_hash": task_contract_hash(payload),
        "task_count": task_count,
        "edge_count": edge_count,
        "root_count": len(batches[0]) if batches else 0,
        "max_width": max((len(batch) for batch in batches), default=0),
        "batches": batches,
        "critical_path_task_ids": critical_ids,
        "critical_path_task_count": critical_count,
        "critical_path_minutes": critical_minutes,
        "seriality": round(seriality, 6),
        "estimated_dispatch_minutes": dispatch_minutes,
        "execute_phase_timeout_minutes": timeout_minutes,
        "warnings": ([{"code": "task_count_high", "message": "Task count exceeds 24; inspect scope."}] if task_count > 24 else []),
        "diagnostics": [diagnostic.as_dict() for diagnostic in diagnostics],
        "admitted": not diagnostics,
    }
    return report


def assert_admitted_task_feasibility(
    payload: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Revalidate v2 graphs at execute entry; leave stored v1 plans readable."""

    if payload.get("task_contract_version") != TASK_CONTRACT_VERSION:
        return None
    report = compile_task_feasibility(payload, config)
    admitted = payload.get("graph_report")
    admitted_hash = admitted.get("task_contract_hash") if isinstance(admitted, Mapping) else None
    if not report["admitted"]:
        codes = ", ".join(item["code"] for item in report["diagnostics"])
        raise ValueError(f"Finalized task graph no longer passes feasibility: {codes}")
    if admitted_hash != report["task_contract_hash"]:
        raise ValueError("Finalized task graph hash differs from the admitted post-finalize graph")
    return report


__all__ = [
    "TASK_CONTRACT_VERSION",
    "assert_admitted_task_feasibility",
    "compile_task_feasibility",
    "task_contract_hash",
]
