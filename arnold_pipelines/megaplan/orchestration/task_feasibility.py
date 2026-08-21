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
from arnold_pipelines.megaplan.execute.test_budget import (
    CLASSIFICATION_V2,
    classify_task_budget,
    describe_budget_for_feasibility,
)



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


def _narrow_selector_is_path_shaped(selector: Any) -> bool:
    """True when a narrow_tests selector is a concrete pytest path selector."""
    from arnold_pipelines.megaplan.orchestration.validation_jobs import (
        validate_narrow_selector_shape,
    )

    return validate_narrow_selector_shape(selector)[0]
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
    """Stable hash of the structural task contract.

    Intentionally excludes ``seed_epoch`` and ``source`` so that epoch and
    source binding (added in Step 7H-a) do not perturb the structural identity
    relied upon by m8a_report, critique_custody, and other existing consumers.
    """
    encoded = json.dumps(
        _stable_contract(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _plan_identity_inputs(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Identity inputs for the additive ``plan_hash`` receipt field.

    Distinct from ``_stable_contract``: binds ``seed_epoch`` and ``source``
    so dispatch identity is traceable to its materialized seed and source
    provenance without changing ``task_contract_hash``.
    """
    return {
        "task_contract": _stable_contract(payload),
        "source": payload.get("source"),
        "seed_epoch": payload.get("seed_epoch"),
    }


def plan_hash(payload: Mapping[str, Any]) -> str:
    """Content hash binding source, seed_epoch, and the structural contract.

    Additive identity receipt field (Step 7H-a).  Changes when the structural
    contract, source, or seed epoch changes, but does not affect
    ``task_contract_hash``.
    """
    encoded = json.dumps(
        _plan_identity_inputs(payload),
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
    budget_classifications: list[dict[str, Any]] = []
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
        budget_classifications.append({
            "task_id": task["id"],
            **describe_budget_for_feasibility(classify_task_budget(task)),
        })
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
            classification = classify_task_budget(task)
            if classification.mixes_state_fields:
                diagnostics.append(FeasibilityDiagnostic(
                    "task_test_budget_state_mixed",
                    "v1 and v2 budget state fields must not be mixed; the loader does not rewrite artifacts.",
                    task["id"],
                ))
            if not isinstance(selectors, list) or any(not isinstance(item, str) or not item.strip() for item in selectors) or len(selectors) > MAX_NARROW_SELECTORS:
                diagnostics.append(FeasibilityDiagnostic("task_test_selector_budget_exceeded", f"narrow_tests.selectors must contain at most {MAX_NARROW_SELECTORS} non-empty selectors.", task["id"]))
            elif any(
                selector.strip().rstrip("/") in {"test", "tests"}
                or selector.strip().endswith("/")
                for selector in selectors
            ):
                diagnostics.append(FeasibilityDiagnostic("task_test_selector_too_broad", "Narrow selectors must name bounded files/modules, not an entire test directory.", task["id"]))
            elif any(
                not _narrow_selector_is_path_shaped(selector)
                for selector in selectors
                if isinstance(selector, str)
            ):
                diagnostics.append(FeasibilityDiagnostic(
                    "task_test_selector_invalid_shape",
                    "Narrow selectors must be concrete pytest path selectors (e.g. tests/core/store/test_x.py or tests/x.py::test_y); shell commands (pytest ..., python -m ..., bash ..., make ...) and flags are not allowed.",
                    task["id"],
                ))
            if payload.get("task_contract_version") == TASK_CONTRACT_VERSION:
                if classification.semantics != CLASSIFICATION_V2:
                    diagnostics.append(FeasibilityDiagnostic(
                        "task_test_budget_v2_required",
                        "New finalized plans must use elapsed_wall_clock_v2 with one positive test_budget_seconds; v1 max_seconds is not admitted on task_contract_version=2 graphs.",
                        task["id"],
                    ))
                else:
                    budget = narrow.get("test_budget_seconds")
                    if not isinstance(budget, (int, float)) or isinstance(budget, bool) or not 0 < float(budget) <= MAX_NARROW_TEST_SECONDS:
                        diagnostics.append(FeasibilityDiagnostic(
                            "task_test_time_budget_exceeded",
                            f"narrow_tests.test_budget_seconds must be in (0..{MAX_NARROW_TEST_SECONDS}] for elapsed_wall_clock_v2.",
                            task["id"],
                        ))
                    if "max_seconds" in narrow:
                        diagnostics.append(FeasibilityDiagnostic(
                            "task_test_budget_v1_on_v2_graph",
                            "narrow_tests.max_seconds is a v1 field and is not admitted on task_contract_version=2 graphs.",
                            task["id"],
                        ))
            elif classification.semantics == CLASSIFICATION_V2:
                budget = narrow.get("test_budget_seconds")
                if not isinstance(budget, (int, float)) or isinstance(budget, bool) or not 0 < float(budget) <= MAX_NARROW_TEST_SECONDS:
                    diagnostics.append(FeasibilityDiagnostic(
                        "task_test_time_budget_exceeded",
                        f"narrow_tests.test_budget_seconds must be in (0..{MAX_NARROW_TEST_SECONDS}] for elapsed_wall_clock_v2.",
                        task["id"],
                    ))
            elif not isinstance(max_seconds, int) or isinstance(max_seconds, bool) or not 0 <= max_seconds <= MAX_NARROW_TEST_SECONDS:
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
                matched = next((word for word in _ROUTING_WORDS if word in lowered), "")
                snippet = reason if len(reason) <= 240 else reason[:237] + "..."
                diagnostics.append(
                    FeasibilityDiagnostic(
                        "routing_dependency_forbidden",
                        "Routing, authoring order, and batch shape cannot create "
                        "correctness dependencies. Rewrite or remove the dependency "
                        f"reason for '{dep}' (currently: {snippet!r}; matched routing "
                        f"word {matched!r}) as a semantic consumes_output / "
                        "write_conflict / human_prerequisite rationale that names a "
                        "concrete required_output.",
                        task_id,
                        dep,
                    )
                )

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
        "plan_hash": plan_hash(payload),
        "seed_epoch": payload.get("seed_epoch"),
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
        "budget_classifications": budget_classifications,
        "warnings": ([{"code": "task_count_high", "message": "Task count exceeds 24; inspect scope."}] if task_count > 24 else []),
        "diagnostics": [diagnostic.as_dict() for diagnostic in diagnostics],
        "admitted": not diagnostics,
    }
    return report


# Sentinel distinguishing "caller has not adopted the epoch protocol" from
# an explicitly-absent attestation (``current_epoch=None``).  Callers that
# have not been wired in Step 7H-b leave the parameter unset and preserve
# the prior backward-compatible behavior; callers that explicitly pass
# ``current_epoch=None`` for a v2 plan trigger the fail-closed rejection.
_EPOCH_UNSET: Any = object()


def assert_admitted_task_feasibility(
    payload: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
    current_epoch: Any = _EPOCH_UNSET,
) -> dict[str, Any] | None:
    """Revalidate v2 graphs at execute entry; leave stored v1 plans readable.

    For v2 plans (``task_contract_version == TASK_CONTRACT_VERSION``):

    * **v1 escape** — non-v2 payloads return ``None`` immediately so stored
      legacy plans remain readable.
    * **v2 + missing-epoch rejection** — when ``current_epoch`` is explicitly
      ``None`` (the attestation is absent) the function raises
      ``ValueError("seed_epoch attestation required for v2 plans")``.
    * **Stale-epoch fencing** — when ``current_epoch`` is provided and
      non-``None``, it is compared against the receipt's embedded
      ``seed_epoch``; a mismatch raises ``ValueError``.
    * **Backward-compat** — when ``current_epoch`` is left unset
      (``_EPOCH_UNSET``), the caller has not yet adopted the epoch protocol
      (Step 7H-b wiring is pending) and the prior behavior is preserved.
    """

    if payload.get("task_contract_version") != TASK_CONTRACT_VERSION:
        return None
    if current_epoch is None:
        raise ValueError("seed_epoch attestation required for v2 plans")
    report = compile_task_feasibility(payload, config)
    if (
        current_epoch is not _EPOCH_UNSET
        and report.get("seed_epoch") != current_epoch
    ):
        raise ValueError(
            "seed_epoch mismatch: stale or conflicted epoch at execute entry"
        )
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
    "plan_hash",
    "task_contract_hash",
]