"""Deterministic harness-owned validation-job compiler.

Reads the finalize payload (tasks with narrow_tests, test_selection) and
compiles a stable, ordered list of no-file validation jobs.  The compiler
is intentionally pure so the same decision can be repeated at execute entry
and compared by content hash.

Key invariants
--------------
* Every returned job is read-only — it runs tests, never mutates files.
* Ambiguous selectors (directory-level, ``tests/`` without a concrete file)
  are rejected rather than silently widened.
* The post-execute suite job is the authoritative harness-owned backstop
  and is always emitted when *test_selection* indicates ``full`` or
  ``scoped`` mode.
* Narrow-recheck jobs are emitted one per task when the task carries at
  least one non-empty ``narrow_tests`` selector.
* Mutating tasks (write_set paths > 0 with kind=code/test/docs) do NOT
  produce validation jobs that touch files — validation jobs are pure
  pytest invocations.
"""

from __future__ import annotations

import shlex
from typing import Any, Mapping, Sequence

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

VALIDATION_JOB_KINDS = frozenset({"post_execute_suite", "narrow_recheck"})

# Selector strings that are too broad for a harness-owned deterministic
# validation job — they represent directory-level or catch-all selectors
# that could silently widen scope.
_AMBIGUOUS_SELECTOR_PATTERNS = frozenset({
    "test",
    "tests",
    "tests/",
    ".",
})

# Max reasonable timeout for a harness-owned validation job (seconds).
# Post-execute suites may legitimately be larger than narrow rechecks.
_DEFAULT_POST_EXECUTE_MAX_SECONDS = 3600
_DEFAULT_NARROW_RECHECK_MAX_SECONDS = 600
_MAX_POST_EXECUTE_RUNS = 1


def _is_ambiguous_selector(selector: str) -> bool:
    """Return True if *selector* is too broad for a deterministic job."""
    stripped = selector.strip().rstrip("/")
    return not stripped or stripped in _AMBIGUOUS_SELECTOR_PATTERNS


def _build_pytest_command(
    selectors: Sequence[str],
    *,
    timeout_seconds: int,
    extra_args: str = "",
) -> str:
    """Build a deterministic pytest command with a timeout wrapper."""
    quoted = " ".join(shlex.quote(s) for s in selectors)
    base = f"timeout {timeout_seconds}s pytest {quoted} --tb=short -q"
    if extra_args:
        base = f"{base} {extra_args}"
    return base


def _next_validation_job_id(existing: Sequence[Mapping[str, Any]]) -> str:
    """Return the next VJ-prefixed id."""
    next_num = 1
    for job in existing:
        jid = job.get("id", "") if isinstance(job, Mapping) else ""
        if isinstance(jid, str) and jid.startswith("VJ") and jid[2:].isdigit():
            next_num = max(next_num, int(jid[2:]) + 1)
    return f"VJ{next_num}"


# ---------------------------------------------------------------------------
# Narrow recheck jobs — one per task with non-empty narrow_tests selectors
# ---------------------------------------------------------------------------


def _compile_narrow_recheck(
    task: Mapping[str, Any],
    *,
    existing_jobs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Compile a single narrow-recheck validation job for *task*.

    Returns ``None`` when the task has no test selectors (audit/research
    tasks) or when every selector is ambiguous.
    """
    narrow = task.get("narrow_tests")
    if not isinstance(narrow, Mapping):
        return None

    selectors: list[str] = []
    raw = narrow.get("selectors")
    if isinstance(raw, list):
        for sel in raw:
            if isinstance(sel, str) and sel.strip():
                if _is_ambiguous_selector(sel):
                    # Reject ambiguous selectors — a harness-owned validation
                    # job must name concrete test files/modules.
                    return None
                selectors.append(sel.strip())

    if not selectors:
        return None

    max_seconds = narrow.get("max_seconds")
    if not isinstance(max_seconds, int) or max_seconds <= 0:
        max_seconds = _DEFAULT_NARROW_RECHECK_MAX_SECONDS
    max_seconds = min(max_seconds, _DEFAULT_NARROW_RECHECK_MAX_SECONDS)

    max_runs = narrow.get("max_runs")
    if not isinstance(max_runs, int) or max_runs <= 0:
        max_runs = 1
    max_runs = min(max_runs, 2)

    task_id = task.get("id", "")
    jid = _next_validation_job_id(existing_jobs)

    return {
        "id": jid,
        "kind": "narrow_recheck",
        "command": _build_pytest_command(
            selectors,
            timeout_seconds=max_seconds,
        ),
        "selectors": selectors,
        "max_seconds": max_seconds,
        "max_runs": max_runs,
        "reason": f"Narrow recheck for task {task_id}: {', '.join(selectors)}",
        "task_id": task_id,
        "writes_files": False,
    }


# ---------------------------------------------------------------------------
# Post-execute suite job — the authoritative harness-owned backstop
# ---------------------------------------------------------------------------


def _compile_post_execute_suite(
    test_selection: Mapping[str, Any],
    *,
    existing_jobs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Compile the post-execute suite validation job from *test_selection*.

    Returns ``None`` when *test_selection* mode is ``none`` or
    ``unresolved``.
    """
    mode = test_selection.get("mode")
    if mode not in ("full", "scoped"):
        return None

    command_override = test_selection.get("command_override")
    if isinstance(command_override, str) and command_override.strip():
        command = command_override.strip()
    else:
        # Full suite with generous timeout
        command = _build_pytest_command(
            ["tests"],
            timeout_seconds=_DEFAULT_POST_EXECUTE_MAX_SECONDS,
            extra_args="--no-header",
        )

    selectors = test_selection.get("selectors_used")
    if not isinstance(selectors, list):
        selectors = []

    reason = test_selection.get("reason", "Authoritative harness-owned post-execute suite.")

    jid = _next_validation_job_id(existing_jobs)

    return {
        "id": jid,
        "kind": "post_execute_suite",
        "command": command,
        "selectors": selectors,
        "max_seconds": _DEFAULT_POST_EXECUTE_MAX_SECONDS,
        "max_runs": _MAX_POST_EXECUTE_RUNS,
        "reason": reason,
        "writes_files": False,
    }


# ---------------------------------------------------------------------------
# Public compiler entry point
# ---------------------------------------------------------------------------


def compile_validation_jobs(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Compile deterministic no-file validation jobs from a finalize payload.

    Parameters
    ----------
    payload:
        The finalize payload containing ``tasks`` (with ``narrow_tests``)
        and ``test_selection``.

    Returns
    -------
    A stable, ordered list of validation job dicts.  The list always starts
    with the post-execute suite job (when applicable) followed by one
    narrow-recheck job per task that declares test selectors.

    Invariants
    ----------
    * Every job has ``writes_files: False``.
    * Ambiguous selectors (bare ``tests/``, ``.``) are rejected.
    * Post-execute suite only runs once (``max_runs: 1``).
    * Narrow rechecks respect the per-task ``max_runs`` ceiling.
    """
    jobs: list[dict[str, Any]] = []

    # --- Post-execute suite (always first) ---
    test_selection = payload.get("test_selection")
    if isinstance(test_selection, Mapping):
        suite_job = _compile_post_execute_suite(
            test_selection,
            existing_jobs=jobs,
        )
        if suite_job is not None:
            jobs.append(suite_job)

    # --- Narrow rechecks (one per task) ---
    raw_tasks = payload.get("tasks")
    tasks: list[dict[str, Any]] = []
    if isinstance(raw_tasks, list):
        tasks = [dict(t) for t in raw_tasks if isinstance(t, Mapping)]

    for task in tasks:
        # Skip audit/research tasks (kind that produces no test selectors)
        kind = task.get("kind", "")
        if isinstance(kind, str) and kind in ("audit", "research"):
            continue
        # Reject mutating validation: a validation job must never produce
        # files_changed.  Tasks that claim write_set paths with code/test/docs
        # kinds are implementation tasks, not validation jobs.
        write_set = task.get("write_set")
        if isinstance(write_set, Mapping):
            paths = write_set.get("paths", [])
            if isinstance(paths, list) and len(paths) > 0:
                # This is a mutating task — its narrow_tests produce a
                # narrow_recheck for the harness, but the task itself is
                # NOT a validation job.
                pass  # fall through to narrow_recheck compilation

        narrow_job = _compile_narrow_recheck(task, existing_jobs=jobs)
        if narrow_job is not None:
            jobs.append(narrow_job)

    return jobs


# ---------------------------------------------------------------------------
# Item-level validation — used by the finalize handler to reject malformed
# model-output validation_jobs before harness compilation replaces them.
# ---------------------------------------------------------------------------


def validate_model_validation_jobs(
    validation_jobs: Any,
) -> list[str]:
    """Validate the model-emitted ``validation_jobs`` field.

    The model MUST emit an empty list.  Any non-empty value is a model
    error — the harness owns validation-job compilation.

    Returns a list of human-readable issue strings (empty = valid).
    """
    issues: list[str] = []

    if not isinstance(validation_jobs, list):
        issues.append(
            "validation_jobs must be an array; the model must emit [] "
            "and the harness derives the actual jobs."
        )
        return issues

    if len(validation_jobs) > 0:
        issues.append(
            "validation_jobs must be an empty array. "
            "The harness owns integration and full-suite verification — "
            "model tasks must not emit validation jobs."
        )

    # Even if empty, verify each element would conform to the schema
    for index, job in enumerate(validation_jobs):
        if not isinstance(job, Mapping):
            issues.append(
                f"validation_jobs[{index}] must be an object; got {type(job).__name__}"
            )
            continue
        # Check for mutating fields that would make this ambiguous
        if job.get("writes_files") is not False:
            issues.append(
                f"validation_jobs[{index}] must have writes_files: false; "
                "harness-owned validation jobs never mutate files."
            )
        kind = job.get("kind")
        if isinstance(kind, str) and kind not in VALIDATION_JOB_KINDS:
            issues.append(
                f"validation_jobs[{index}] has unknown kind {kind!r}; "
                f"allowed: {sorted(VALIDATION_JOB_KINDS)}"
            )

    return issues


__all__ = [
    "VALIDATION_JOB_KINDS",
    "compile_validation_jobs",
    "validate_model_validation_jobs",
]
