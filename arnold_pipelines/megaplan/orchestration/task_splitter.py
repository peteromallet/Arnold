"""Task splitter for complexity >= 7 tasks.

Pure module that splits high-complexity tasks into implementation and proof
subtasks, preserving write/test/checkpoint contracts. Returns typed diagnostics
for ambiguous, incomplete, or mutating inputs, and a typed blocker for proof
exhaustion.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping
from arnold_pipelines.megaplan.execute.test_budget import (
    CLASSIFICATION_V2,
    classify_narrow_tests,
    describe_budget_for_splitter,
)


# ---------------------------------------------------------------------------
# Diagnostic codes
# ---------------------------------------------------------------------------
SPLIT_AMBIGUOUS_OBJECTIVE = "split_ambiguous_objective"
SPLIT_INCOMPLETE_WRITE_SET = "split_incomplete_write_set"
SPLIT_MUTATING_VALIDATION = "split_mutating_validation"
SPLIT_PROOF_EXHAUSTED = "split_proof_exhausted"
SPLIT_COMPLEXITY_TOO_LOW = "split_complexity_too_low"
SPLIT_ID_COLLISION = "split_id_collision"
SPLIT_DEPENDENCY_REASON_MERGE = "split_dependency_reason_merge"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SPLIT_THRESHOLD = 7
_SPLITTABLE_KINDS = frozenset({"code", "docs"})
_IMPL_COMPLEXITY_REDUCTION = 3
_PROOF_COMPLEXITY = 3
_PROOF_KIND = "test"
_IMPL_KIND_OVERRIDE: dict[str, str] = {}
_CHECKPOINT_RECORDS = frozenset({
    "completed_subobjectives",
    "remaining_subobjectives",
    "output_hashes",
    "test_state",
})

# Objective ambiguity — verbs that signal an independent directive
_DIRECTIVE_VERBS = frozenset({
    "implement", "create", "build", "write", "add", "fix",
    "refactor", "test", "verify", "prove", "validate",
    "design", "migrate", "remove", "replace", "rewrite",
    "split", "extract", "merge", "upgrade", "downgrade",
})


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SplitDiagnostic:
    """Typed reject or blocker diagnostic from task splitting.

    Reject codes (split cannot proceed — the input task itself is invalid
    for splitting):
      - ``split_ambiguous_objective``
      - ``split_incomplete_write_set``
      - ``split_mutating_validation``
      - ``split_complexity_too_low``

    Blocker codes (split conceptually valid but no proof subtask can be
    formed):
      - ``split_proof_exhausted``
    """

    code: str
    message: str
    task_id: str | None = None

    @property
    def is_blocker(self) -> bool:
        """True for proof-exhaustion blockers, False for input rejects."""
        return self.code == SPLIT_PROOF_EXHAUSTED

    @property
    def is_reject(self) -> bool:
        """True for input rejection, False for blockers."""
        return not self.is_blocker

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.task_id is not None:
            result["task_id"] = self.task_id
        return result


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------

def _is_ambiguous_objective(task: Mapping[str, Any]) -> bool:
    """Return True if the objective contains multiple independent directives.

    Ambiguity markers:
    - Semicolons (used as directive separators).
    - Multiple (>=2) independent directive-verb sentences.
    - ``"and"`` joining two distinct action verbs (e.g. "Implement X and test Y").
    """
    objective = task.get("objective", "")
    if not isinstance(objective, str):
        return True
    objective = objective.strip()
    if not objective:
        return True
    if ";" in objective:
        return True

    # Split into sentences (heuristic: period followed by space/capital)
    sentences = [
        s.strip()
        for s in objective.replace("\n", ". ").split(". ")
        if s.strip()
    ]
    if len(sentences) > 2:
        directive_count = sum(
            1
            for s in sentences
            if any(
                s.lower().startswith(verb)
                for verb in _DIRECTIVE_VERBS
            )
        )
        if directive_count >= 2:
            return True

    # "and" joining two distinct actions: "Implement X and test Y"
    lowered = objective.lower()
    if " and " in lowered:
        verb_count = sum(1 for v in _DIRECTIVE_VERBS if v in lowered)
        if verb_count >= 2:
            return True

    # Newline-separated distinct directives
    lines = [line.strip() for line in objective.split("\n") if line.strip()]
    if len(lines) >= 2:
        directive_lines = sum(
            1
            for line in lines
            if any(line.lower().startswith(verb) for verb in _DIRECTIVE_VERBS)
        )
        if directive_lines >= 2:
            return True

    return False


def _is_incomplete_write_set(task: Mapping[str, Any]) -> bool:
    """Return True if the write_set is missing, incomplete, or invalid."""
    write_set = task.get("write_set")
    if not isinstance(write_set, Mapping):
        return True
    if write_set.get("complete") is not True:
        return True
    paths = write_set.get("paths")
    if not isinstance(paths, list):
        return True
    if not paths:
        return True
    if any(not isinstance(p, str) or not p.strip() for p in paths):
        return True
    return False


def _is_mutating_validation(task: Mapping[str, Any]) -> bool:
    """Return True if a test-kind task also claims write paths (mutating).

    A test task that writes files is self-contradictory: it should only
    produce evidence, not mutate the repository.
    """
    kind = task.get("kind")
    if kind != "test":
        return False
    write_set = task.get("write_set")
    if not isinstance(write_set, Mapping):
        return False
    paths = write_set.get("paths")
    if isinstance(paths, list) and paths:
        return True
    return False


def _proof_is_exhausted(task: Mapping[str, Any]) -> bool:
    """Return True if no valid proof subtask can be formed.

    Proof exhaustion occurs when the task lacks narrow tests entirely,
    or when the test budget is zeroed out. Classification is descriptive;
    remaining-time arithmetic stays in execute.test_budget.
    """
    narrow = task.get("narrow_tests")
    if not isinstance(narrow, Mapping):
        return True
    selectors = narrow.get("selectors")
    if not isinstance(selectors, list) or not selectors:
        return True
    if any(not isinstance(s, str) or not s.strip() for s in selectors):
        return True
    classification = classify_narrow_tests(narrow)
    if classification.semantics == CLASSIFICATION_V2:
        budget = classification.allowed_seconds
        if not isinstance(budget, (int, float)) or budget <= 0:
            return True
    else:
        max_seconds = narrow.get("max_seconds", 0)
        if not isinstance(max_seconds, (int, float)) or max_seconds <= 0:
            return True
    max_runs = narrow.get("max_runs", 0)
    if not isinstance(max_runs, int) or max_runs <= 0:
        return True
    return False


# ---------------------------------------------------------------------------
# Splitting logic
# ---------------------------------------------------------------------------

def split_task(task: Mapping[str, Any]) -> list[dict[str, Any]] | SplitDiagnostic:
    """Split a complexity >= 7 task into implementation + proof subtasks.

    Args:
        task: A task dict with at minimum ``id``, ``objective``, ``kind``,
            ``complexity``, ``estimated_minutes``, ``write_set``,
            ``narrow_tests``, ``checkpoint``, ``depends_on``, and
            ``dependency_reasons``.

    Returns:
        A list of exactly two subtask dicts (implementation, proof), or a
        :class:`SplitDiagnostic` when splitting is rejected or blocked.

    **Reject cases** (the input task itself is unsuitable)::

        split_ambiguous_objective  – objective has multiple directives
        split_incomplete_write_set – write_set missing or incomplete
        split_mutating_validation  – test-kind task claims write paths
        split_complexity_too_low   – complexity < 7

    **Blocker cases** (input is valid but no proof can be formed)::

        split_proof_exhausted – no narrow tests or zero test budget
    """
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        return SplitDiagnostic(
            SPLIT_AMBIGUOUS_OBJECTIVE,
            "Task must have a non-empty string id.",
            str(task_id),
        )

    complexity = task.get("complexity")
    if not isinstance(complexity, int) or complexity < _SPLIT_THRESHOLD:
        return SplitDiagnostic(
            SPLIT_COMPLEXITY_TOO_LOW,
            f"Task complexity ({complexity!r}) is below the split threshold of {_SPLIT_THRESHOLD}.",
            task_id,
        )

    # --- Reject checks (ordered: input quality first, then kind gate) ---

    if _is_ambiguous_objective(task):
        return SplitDiagnostic(
            SPLIT_AMBIGUOUS_OBJECTIVE,
            "Task objective contains multiple independent directives; it must be a single, bounded change.",
            task_id,
        )

    if _is_incomplete_write_set(task):
        return SplitDiagnostic(
            SPLIT_INCOMPLETE_WRITE_SET,
            "Task write_set must be complete with at least one non-empty path.",
            task_id,
        )

    if _is_mutating_validation(task):
        return SplitDiagnostic(
            SPLIT_MUTATING_VALIDATION,
            "Test-kind task declares write paths; validation must not mutate.",
            task_id,
        )

    kind = task.get("kind")
    if kind not in _SPLITTABLE_KINDS:
        return SplitDiagnostic(
            SPLIT_AMBIGUOUS_OBJECTIVE,
            f"Task kind '{kind!s}' is not splittable; only {sorted(_SPLITTABLE_KINDS)} tasks can be split into implementation + proof.",
            task_id,
        )

    # --- Blocker checks ---

    if _proof_is_exhausted(task):
        return SplitDiagnostic(
            SPLIT_PROOF_EXHAUSTED,
            "Task has no narrow test selectors or zero test budget; cannot form a proof subtask.",
            task_id,
        )

    # --- Build subtasks ---

    impl_id = f"{task_id}_impl"
    proof_id = f"{task_id}_proof"

    original_minutes = task.get("estimated_minutes", 0)
    if not isinstance(original_minutes, (int, float)) or original_minutes <= 0:
        original_minutes = 10  # sensible default
    original_minutes = int(original_minutes)

    # Implementation gets most of the time budget
    impl_minutes = max(1, int(original_minutes * 0.70))
    # Proof gets the remainder, at least 1 minute
    proof_minutes = max(1, original_minutes - impl_minutes)

    impl_complexity = max(1, min(6, complexity - _IMPL_COMPLEXITY_REDUCTION))

    # --- Implementation subtask ---
    impl: dict[str, Any] = {
        "id": impl_id,
        "objective": _derive_impl_objective(task),
        "description": task.get("description", ""),
        "kind": _IMPL_KIND_OVERRIDE.get(kind, kind),
        "status": "pending",
        "complexity": impl_complexity,
        "complexity_justification": (
            f"Implementation portion of complexity-{complexity} task {task_id}; "
            f"proof deferred to {proof_id}."
        ),
        "estimated_minutes": impl_minutes,
        "depends_on": list(task.get("depends_on", [])),
        "dependency_reasons": _adjust_dependency_reasons(
            task.get("dependency_reasons", {}),
            task.get("depends_on", []),
        ),
        "routing_group": task.get("routing_group", ""),
        "write_set": deepcopy(task.get("write_set", {})),
        "narrow_tests": _build_impl_narrow_tests(task),
        "checkpoint": deepcopy(task.get("checkpoint", {})),
    }

    # --- Proof subtask ---
    proof: dict[str, Any] = {
        "id": proof_id,
        "objective": _derive_proof_objective(task, impl_id),
        "description": (
            f"Verify the implementation in {impl_id} by running narrow tests "
            f"against the contract defined in {task_id}."
        ),
        "kind": _PROOF_KIND,
        "status": "pending",
        "complexity": _PROOF_COMPLEXITY,
        "complexity_justification": (
            f"Proof/verification subtask for complexity-{complexity} task {task_id}; "
            f"executes narrow tests only."
        ),
        "estimated_minutes": proof_minutes,
        "depends_on": [impl_id],
        "dependency_reasons": {
            impl_id: {
                "kind": "consumes_output",
                "reason": (
                    f"Proof {proof_id} verifies the files produced by "
                    f"implementation {impl_id}."
                ),
                "required_output": _derive_required_output(task, impl_id),
            }
        },
        "routing_group": task.get("routing_group", ""),
        "write_set": {"paths": [], "complete": True},
        "narrow_tests": deepcopy(task.get("narrow_tests", {})),
        "checkpoint": {
            "required": False,
            "max_interval_seconds": 0,
            "records": [],
        },
    }

    return [impl, proof]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_impl_objective(task: Mapping[str, Any]) -> str:
    """Derive a clean implementation objective from the original task."""
    original = task.get("objective", "")
    if not isinstance(original, str):
        original = ""
    original = original.strip()

    # If it starts with a directive verb, prefix with "Implement: "
    lowered = original.lower()
    for verb in _DIRECTIVE_VERBS:
        if lowered.startswith(verb):
            return f"Implement: {original[0].upper() + original[1:] if original else original}"
    # Otherwise just use as-is
    return f"Implement: {original}"


def _derive_proof_objective(task: Mapping[str, Any], impl_id: str) -> str:
    """Derive a proof objective referencing the implementation subtask."""
    original = task.get("objective", "")
    if not isinstance(original, str):
        original = ""
    original = original.strip()
    if len(original) > 80:
        original = original[:77] + "..."
    return f"Prove correctness of {impl_id}: {original}"


def _derive_required_output(task: Mapping[str, Any], impl_id: str) -> str:
    """Derive a required_output string for the proof -> impl dependency."""
    write_set = task.get("write_set")
    if isinstance(write_set, Mapping):
        paths = write_set.get("paths", [])
        if isinstance(paths, list) and paths:
            return ", ".join(str(p) for p in paths)
    return f"output of {impl_id}"


def _adjust_dependency_reasons(
    reasons: Any,
    deps: list[str],
) -> dict[str, Any]:
    """Copy dependency reasons, dropping any that reference the original task id."""
    if not isinstance(reasons, Mapping):
        return {}
    result: dict[str, Any] = {}
    for dep in deps:
        if dep in reasons:
            result[dep] = deepcopy(reasons[dep])
    return result


def _build_impl_narrow_tests(task: Mapping[str, Any]) -> dict[str, Any]:
    """Build the narrow_tests for the implementation subtask.

    Preserve the original admission. Do not recompute remaining elapsed time;
    execute.test_budget is the only arithmetic owner.
    """
    original = task.get("narrow_tests")
    if not isinstance(original, Mapping):
        return {"selectors": [], "max_seconds": 0, "max_runs": 0}

    copied = dict(original)
    selectors = copied.get("selectors", [])
    if not isinstance(selectors, list):
        copied["selectors"] = []
    else:
        copied["selectors"] = list(selectors)

    classification = classify_narrow_tests(copied)
    copied["budget_classification"] = classification.visible
    copied["budget_enforcement_note"] = describe_budget_for_splitter(classification)
    if classification.semantics == CLASSIFICATION_V2:
        budget = copied.get("test_budget_seconds", 0)
        if not isinstance(budget, (int, float)) or budget <= 0:
            copied["test_budget_seconds"] = 0
        max_runs = copied.get("max_runs", 0)
        if not isinstance(max_runs, int) or max_runs <= 0:
            copied["max_runs"] = 0
        return copied

    max_seconds = copied.get("max_seconds", 0)
    if not isinstance(max_seconds, (int, float)) or max_seconds <= 0:
        copied["max_seconds"] = 0
    else:
        copied["max_seconds"] = int(max_seconds)
    max_runs = copied.get("max_runs", 0)
    if not isinstance(max_runs, int) or max_runs <= 0:
        copied["max_runs"] = 0
    return copied


# ---------------------------------------------------------------------------
# Batch splitter (for whole payloads)
# ---------------------------------------------------------------------------

def _rewrite_task_references(
    tasks: list[dict[str, Any]],
    split_map: Mapping[str, Mapping[str, str]],
    diagnostics: list[SplitDiagnostic],
) -> None:
    """Rewire downstream task references after splitting (two-pass closure).

    Every ``depends_on`` entry and matching ``dependency_reasons`` key that
    names a split original task is remapped to the implementation subtask
    (``{original}_impl``), which carries the original's inherited
    dependencies and output-bearing work.  Duplicate and self dependencies
    are preserved verbatim so feasibility rejects malformed input
    deterministically.  If re-keying reasons would merge two distinct
    entries, the task is flagged fail-closed and left unchanged.
    """
    for task in tasks:
        deps = task.get("depends_on")
        if isinstance(deps, list):
            task["depends_on"] = [
                split_map[dep]["impl_id"] if dep in split_map else dep
                for dep in deps
            ]
        reasons = task.get("dependency_reasons")
        if not isinstance(reasons, Mapping):
            continue
        new_reasons: dict[str, Any] = {}
        merged = False
        for key, value in reasons.items():
            new_key = split_map[key]["impl_id"] if key in split_map else key
            if new_key in new_reasons and new_reasons[new_key] is not value:
                merged = True
            new_reasons[new_key] = value
        if merged:
            diagnostics.append(SplitDiagnostic(
                SPLIT_DEPENDENCY_REASON_MERGE,
                "dependency_reasons keys would merge after split rewiring; task left unchanged.",
                str(task.get("id")),
            ))
        else:
            task["dependency_reasons"] = new_reasons


def split_high_complexity_tasks(
    payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[SplitDiagnostic], dict[str, dict[str, str]]]:
    """Apply :func:`split_task` to every complexity >= 7 task in *payload*.

    Two-pass transform:

    1. Preflight every original task id and every generated ``{id}_impl`` /
       ``{id}_proof`` id.  A generated id colliding with any original or
       previously generated id fails closed with a deterministic
       ``split_id_collision`` diagnostic and the original task is kept
       un-split (never silently overwritten).
    2. Construct the implementation/proof children and the complete
       ``original_id -> {impl_id, proof_id}`` map, then rewire every
       downstream ``depends_on`` / ``dependency_reasons`` reference through
       :func:`_rewrite_task_references`.

    Args:
        payload: A finalized-plan payload dict with a ``tasks`` list.

    Returns:
        A tuple ``(tasks, diagnostics, split_map)`` where *tasks* is the
        transformed task list, *diagnostics* lists every reject/blocker/
        collision diagnostic, and *split_map* maps each split original id to
        its ``{impl_id, proof_id}`` replacement ids (empty when nothing was
        split).  An empty diagnostics list means every high-complexity task
        was successfully split and every downstream reference was rewired.
    """
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list):
        return [], [SplitDiagnostic(
            SPLIT_AMBIGUOUS_OBJECTIVE,
            "Payload has no tasks list.",
        )], {}

    original_ids = {
        raw.get("id")
        for raw in raw_tasks
        if isinstance(raw, Mapping) and isinstance(raw.get("id"), str)
    }

    output: list[dict[str, Any]] = []
    diagnostics: list[SplitDiagnostic] = []
    split_map: dict[str, dict[str, str]] = {}
    generated_ids: set[str] = set()

    for raw in raw_tasks:
        if not isinstance(raw, Mapping):
            diagnostics.append(SplitDiagnostic(
                SPLIT_AMBIGUOUS_OBJECTIVE,
                "Non-dict entry in tasks list.",
            ))
            continue

        task = dict(raw)
        complexity = task.get("complexity")
        if isinstance(complexity, int) and complexity >= _SPLIT_THRESHOLD:
            result = split_task(task)
            if isinstance(result, SplitDiagnostic):
                diagnostics.append(result)
                # Keep the original task in place (can't split it)
                output.append(task)
                continue

            impl, proof = result
            collided = [
                new_id for new_id in (impl["id"], proof["id"])
                if new_id in original_ids or new_id in generated_ids
            ]
            if collided:
                diagnostics.append(SplitDiagnostic(
                    SPLIT_ID_COLLISION,
                    "Generated split ids collide with existing ids: "
                    + ", ".join(sorted(collided)) + ".",
                    task.get("id"),
                ))
                # Fail closed: keep the original task un-split rather than
                # silently overwriting an existing id.
                output.append(task)
                continue

            generated_ids.update((impl["id"], proof["id"]))
            split_map[task["id"]] = {
                "impl_id": impl["id"],
                "proof_id": proof["id"],
            }
            output.extend([impl, proof])
        else:
            output.append(task)

    _rewrite_task_references(output, split_map, diagnostics)
    return output, diagnostics, split_map


__all__ = [
    "SPLIT_AMBIGUOUS_OBJECTIVE",
    "SPLIT_COMPLEXITY_TOO_LOW",
    "SPLIT_INCOMPLETE_WRITE_SET",
    "SPLIT_MUTATING_VALIDATION",
    "SPLIT_PROOF_EXHAUSTED",
    "SplitDiagnostic",
    "split_high_complexity_tasks",
    "split_task",
]
