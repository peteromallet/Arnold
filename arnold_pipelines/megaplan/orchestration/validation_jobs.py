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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan.orchestration.test_selection import (
    _existing_pytest_selector_path,
    _looks_like_repo_path,
)

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

# Selector lifecycle outcomes are deliberately small and phase-neutral.  The
# Finalize handler uses the same contract reader as Execute; only Execute is
# allowed to run a command or persist a runtime deferral.
SELECTOR_READY = "ready"
SELECTOR_DEFERRED = "deferred_task_output"
SELECTOR_INVALID = "invalid"


@dataclass(frozen=True)
class SelectorLifecycle:
    """Deterministic classification of one narrow validation job's selectors.

    ``write_set.paths`` is the sole ownership source.  In particular, this
    reader never falls back to ``files_changed``, command arguments, or an
    observed dirty tree: doing so would silently widen the admitted write set.
    """

    status: str
    selector_paths: tuple[str, ...] = ()
    missing_selectors: tuple[str, ...] = ()
    undeclared_missing_selectors: tuple[str, ...] = ()
    declared_outputs: tuple[str, ...] = ()
    reason: str = ""


def normalize_selector_path(selector: Any) -> str | None:
    """Return the repository-relative path portion of a test selector.

    The ``::`` strip exists for write-set matching only — ownership is
    file-level.  Existence is decided separately by the node-aware
    ``_existing_pytest_selector_path`` on the full selector.  We retain no
    inferred path and reject traversal or empty selectors rather than trying
    to repair them.
    """

    if not isinstance(selector, str):
        return None
    value = selector.strip()
    if not value:
        return None
    path = value.split("::", 1)[0].strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if (
        not path
        or path in {".", ".."}
        or path.startswith("../")
        or "/../" in path
        or path.endswith("/..")
    ):
        return None
    # Absolute selectors cannot be owned by a repository-relative write set.
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        return None
    return path


def declared_task_output_paths(task: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Read the exact task-owned output paths from ``write_set.paths``.

    No other result or observation field is consulted.  This is the guard
    against inferred write-set widening that caused VJ24's ambiguous gate.
    """

    if not isinstance(task, Mapping):
        return ()
    write_set = task.get("write_set")
    if not isinstance(write_set, Mapping):
        return ()
    raw_paths = write_set.get("paths")
    if not isinstance(raw_paths, list):
        return ()
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_path in raw_paths:
        path = normalize_selector_path(raw_path)
        if path is None or path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return tuple(normalized)


def graph_declared_output_paths(
    tasks: Sequence[Mapping[str, Any]] | None,
) -> tuple[str, ...]:
    """Return the normalized, deterministic union of task-declared outputs.

    The union spans every admitted task's ``write_set.paths`` AND
    ``narrow_tests.selectors``.  ``narrow_tests`` are the test files the
    finalize contract declares each task will produce/run, so a narrow
    validation job referencing a test file authored by ANOTHER task in the
    same graph (e.g. a packaging task whose narrow test is written by a later
    test-authoring task) is owned by the graph and may be produced in a later
    batch.  Normalization and deduplication mirror
    ``declared_task_output_paths`` exactly; the result is stable-sorted so
    classification is deterministic across processes.
    """

    if not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes)):
        return ()
    seen: set[str] = set()
    normalized: list[str] = []
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        for path in declared_task_output_paths(task):
            if path in seen:
                continue
            seen.add(path)
            normalized.append(path)
        narrow = task.get("narrow_tests")
        if not isinstance(narrow, Mapping):
            continue
        raw_selectors = narrow.get("selectors")
        if not isinstance(raw_selectors, list):
            continue
        for raw in raw_selectors:
            path = normalize_selector_path(raw)
            if path is None or path in seen:
                continue
            seen.add(path)
            normalized.append(path)
    return tuple(sorted(normalized))


def classify_selector_lifecycle(
    *,
    project_dir: Path | str,
    job: Mapping[str, Any],
    task: Mapping[str, Any] | None,
    all_declared_outputs: tuple[str, ...] | None = None,
) -> SelectorLifecycle:
    """Classify selectors as runnable, deferred, or invalid.

    Existing selectors (node-aware: file exists and any ``::node`` parts are
    defined in the source AST) are runnable immediately.  A missing selector
    is deferred only when its file-level path is present in the task's
    declared ``write_set.paths`` OR (when ``all_declared_outputs`` is given)
    in the union of every admitted task's declared ``write_set.paths`` — a
    selector owned by a different task in the same graph may be produced in a
    later batch.  A missing selector with no declared owner is invalid and
    must stop execution before a worker is dispatched.
    """

    raw_selectors = job.get("selectors")
    if not isinstance(raw_selectors, list) or not raw_selectors:
        return SelectorLifecycle(status=SELECTOR_INVALID, reason="missing_selectors")

    selector_paths: list[str] = []
    for selector in raw_selectors:
        path = normalize_selector_path(selector)
        if path is None:
            return SelectorLifecycle(
                status=SELECTOR_INVALID,
                reason="invalid_selector_path",
            )
        if path not in selector_paths:
            selector_paths.append(path)

    declared_outputs = declared_task_output_paths(task)
    admissible_outputs = set(declared_outputs)
    if all_declared_outputs is not None:
        admissible_outputs.update(all_declared_outputs)
    root = Path(project_dir)
    # Existence is node-aware: a selector whose file exists but whose node is
    # absent is missing.  missing_selectors keeps the full selector string.
    missing_selectors: list[str] = []
    missing_paths: list[str] = []
    seen_missing: set[str] = set()
    for selector in raw_selectors:
        if _existing_pytest_selector_path(root, selector):
            continue
        path = normalize_selector_path(selector)
        if path is None or path in seen_missing:
            continue
        seen_missing.add(path)
        missing_selectors.append(selector.strip())
        missing_paths.append(path)
    missing = tuple(missing_selectors)
    if not missing:
        return SelectorLifecycle(
            status=SELECTOR_READY,
            selector_paths=tuple(selector_paths),
            declared_outputs=declared_outputs,
        )

    undeclared = tuple(path for path in missing_paths if path not in admissible_outputs)
    if undeclared:
        return SelectorLifecycle(
            status=SELECTOR_INVALID,
            selector_paths=tuple(selector_paths),
            missing_selectors=missing,
            undeclared_missing_selectors=undeclared,
            declared_outputs=declared_outputs,
            reason="undeclared_missing_selector",
        )
    return SelectorLifecycle(
        status=SELECTOR_DEFERRED,
        selector_paths=tuple(selector_paths),
        missing_selectors=missing,
        declared_outputs=declared_outputs,
        reason="selector_is_declared_task_output",
    )


def deferred_selector_evidence(
    job: Mapping[str, Any], lifecycle: SelectorLifecycle
) -> dict[str, Any]:
    """Build the stable, content-addressed deferred-selector evidence record."""

    evidence = {
        "job_id": str(job.get("id") or "vj"),
        "kind": str(job.get("kind") or "narrow_recheck"),
        "status": SELECTOR_DEFERRED,
        "exit_code": None,
        "task_id": str(job.get("task_id") or ""),
        "missing_selectors": sorted(set(lifecycle.missing_selectors)),
        "reason": lifecycle.reason or "selector_is_declared_task_output",
    }
    import hashlib
    import json

    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    evidence["evidence_hash"] = "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return evidence


def _is_ambiguous_selector(selector: str) -> bool:
    """Return True if *selector* is too broad for a deterministic job."""
    stripped = selector.strip().rstrip("/")
    return not stripped or stripped in _AMBIGUOUS_SELECTOR_PATTERNS


import re

_PYTEST_TEST_FILE_RE = re.compile(r"^(?:test_.*|.*_test)\.py$")


def is_pytest_collectible_selector(selector: str) -> bool:
    """True when pytest can deterministically collect *selector*.

    A single ``.py`` file outside pytest's default ``python_files``
    convention (``test_*.py`` / ``*_test.py``, plus ``conftest.py``) is a
    CLI validator, not a test module: pytest collects zero tests from it
    and always exits 5. Directories and ``::node`` selectors always
    compile as pytest.
    """
    stripped = selector.strip()
    if "::" in stripped:
        return True
    name = stripped.rsplit("/", 1)[-1]
    if name == "conftest.py":
        return True
    return bool(_PYTEST_TEST_FILE_RE.fullmatch(name))


def direct_validator_command(job: Mapping[str, Any]) -> str | None:
    """Recompile a persisted pytest narrow-recheck into a direct validator run.

    Compiled narrow-recheck jobs historically always built
    ``pytest <selectors> ...``.  For a CLI validator selector (single ``.py``
    file outside pytest's ``python_files`` convention), that compiled command
    deterministically collects zero tests and exits 5 — it can never pass,
    so any plan whose recheck names a validator wedges execute pre-dispatch
    forever.  The declared intent is the selector's own exit code as the
    validation result, so the admission gate projects the command to a
    direct run IN MEMORY.  This never rewrites plan artifacts: finalize
    custody verifies the persisted contract, which stays unchanged.

    Returns ``None`` unless the persisted command is exactly the compiled
    pytest shape over exactly the job's single validator selector (fail
    closed on any drift).
    """
    if job.get("kind") != "narrow_recheck":
        return None
    command = job.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    selectors = job.get("selectors")
    if not isinstance(selectors, list) or len(selectors) != 1:
        return None
    selector = selectors[0]
    if not isinstance(selector, str) or not selector.strip():
        return None
    if is_pytest_collectible_selector(selector):
        return None
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts or parts[0] != "pytest":
        return None
    non_option = [tok.strip("'\"") for tok in parts[1:] if not tok.startswith("-")]
    if non_option != [selector]:
        return None
    return f"python3 {shlex.quote(selector)}"


def _build_pytest_command(
    selectors: Sequence[str],
    *,
    timeout_seconds: int,
    extra_args: str = "",
    embed_timeout: bool = True,
) -> str:
    """Build a deterministic pytest command.

    By default the command carries a GNU ``timeout`` wrapper.  Narrow-recheck
    jobs compile with ``embed_timeout=False``: the structured suite runner
    owns the sole deadline (the authoritative comparison ceiling), and an
    embedded probe-budget timeout would deterministically kill a full-file
    differential run that legitimately exceeds the planner's cost hint.
    """
    quoted = " ".join(shlex.quote(s) for s in selectors)
    if embed_timeout:
        base = f"timeout {timeout_seconds}s pytest {quoted} --tb=short -q"
    else:
        base = f"pytest {quoted} --tb=short -q"
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
        "scope": f"narrow_recheck:{task_id}",
        "command": (
            f"python3 {shlex.quote(selectors[0])}"
            if len(selectors) == 1 and not is_pytest_collectible_selector(selectors[0])
            else _build_pytest_command(
                selectors,
                timeout_seconds=max_seconds,
                embed_timeout=False,
            )
        ),
        "environment": {},
        "expected_exit_codes": [0],
        "timeout_seconds": max_seconds,
        "content_hash_algorithm": "sha256",
        "evidence_label": f"validation:narrow_recheck:{task_id}",
        "mutates": False,
        "selectors": selectors,
        "max_seconds": max_seconds,
        "max_runs": max_runs,
        "acceptance_mode": "no_new_failures_delta",
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
        "scope": "post_execute_suite",
        "command": command,
        "environment": {},
        "expected_exit_codes": [0],
        "timeout_seconds": _DEFAULT_POST_EXECUTE_MAX_SECONDS,
        "content_hash_algorithm": "sha256",
        "evidence_label": "validation:post_execute_suite",
        "mutates": False,
        "selectors": selectors,
        "max_seconds": _DEFAULT_POST_EXECUTE_MAX_SECONDS,
        "max_runs": _MAX_POST_EXECUTE_RUNS,
        "reason": reason,
        "writes_files": False,
    }


# ---------------------------------------------------------------------------
# Selector shape validation + legacy-contract recovery projection
# ---------------------------------------------------------------------------
#
# The finalize model occasionally emits full shell commands as
# ``narrow_tests.selectors`` (``python -m compileall -q astrid/core/store``,
# ``pytest tests/x.py -q``).  Ordinary finalization must REJECT those graphs
# (task_feasibility emits ``task_test_selector_invalid_shape`` so planner
# repair re-emits path selectors).  The projector below exists ONLY for the
# bounded execute-entry recovery path: a blocked pre-dispatch validation
# failure whose resume cursor is ``{phase: execute, retry_strategy:
# repair_validation_failure}`` may deterministically recompile an in-memory
# contract from the preserved finalize payload.  It never rewrites plan
# artifacts, never silently widens, and fails closed unless every effective
# narrow job still classifies READY or DEFERRED under the unchanged
# ``classify_selector_lifecycle`` ownership rules.


def validate_narrow_selector_shape(selector: Any) -> tuple[bool, str]:
    """Return ``(valid, reason)`` for one ``narrow_tests`` selector string.

    Valid selectors are concrete repository-relative pytest path selectors
    (``tests/x.py``, ``tests/x.py::test_y``, ``astrid/pkg/mod.py``) with no
    whitespace, no shell operators, no runner prefixes (``pytest``,
    ``python -m``, ``bash``, ``make``, ...), no flags, and no absolute or
    traversal paths.  Command-shaped selectors are rejected so the harness
    compiler can never copy a shell command into a deterministic job.
    """
    if not isinstance(selector, str):
        return False, "selector must be a string"
    value = selector.strip()
    if not value:
        return False, "empty selector"
    if any(ch in value for ch in (" ", "\t", "\n")):
        return False, "selector must be a single path token (no shell commands or flags)"
    if any(op in value for op in ("&&", "||", ";", "|", ">", "<", "`", "$(")):
        return False, "selector must not contain shell operators"
    if value.startswith("-"):
        return False, "selector must not start with a flag"
    path = normalize_selector_path(value)
    if path is None:
        return False, "selector must be a repository-relative path"
    if not _looks_like_repo_path(value):
        return False, "selector must be a tests/-prefixed or .py pytest path"
    if _is_ambiguous_selector(value):
        return False, "selector is ambiguous (directory-wide or catch-all)"
    return True, ""


def _extract_pytest_paths_from_command(command: str) -> list[str]:
    """Extract positional pytest path selectors from one pytest command.

    Recognizes only ``pytest ...`` / ``python -m pytest ...`` invocations.
    Parsing stops at the first option so option values (e.g.
    ``--cov tests/y.py``) can never widen the selector set, and only
    path-shaped tokens are kept.
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        return []
    runner_index: int | None = None
    for index, part in enumerate(parts):
        if part == "pytest" or part.endswith("/pytest"):
            runner_index = index
            break
        if (
            part in ("python", "python3")
            and index + 1 < len(parts)
            and parts[index + 1] == "-m"
            and index + 2 < len(parts)
            and parts[index + 2] == "pytest"
        ):
            runner_index = index + 2
            break
    if runner_index is None:
        return []
    paths: list[str] = []
    for part in parts[runner_index + 1 :]:
        if part.startswith("-"):
            break
        if not part:
            continue
        if _looks_like_repo_path(part):
            paths.append(part)
    return paths


def project_legacy_validation_contract(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Deterministic in-memory recompilation of a malformed legacy contract.

    Only the bounded execute-entry recovery path may call this.  Returns
    ``None`` when the payload carries nothing to recover.  The returned
    receipt binds the original and effective job sets plus every excluded
    command-shaped selector; callers persist it and never rewrite
    ``finalize.json``.
    """
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return None

    normalized_tasks: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        task = dict(task)
        narrow = task.get("narrow_tests")
        if isinstance(narrow, Mapping):
            narrow = dict(narrow)
            raw_selectors = narrow.get("selectors")
            kept: list[str] = []
            if isinstance(raw_selectors, list):
                for selector in raw_selectors:
                    if not isinstance(selector, str):
                        continue
                    ok, _reason = validate_narrow_selector_shape(selector)
                    if ok:
                        if selector not in kept:
                            kept.append(selector)
                        continue
                    extracted = _extract_pytest_paths_from_command(selector)
                    if extracted:
                        for path in extracted:
                            if path not in kept:
                                kept.append(path)
                        excluded.append(
                            {
                                "task_id": task.get("id"),
                                "selector": selector,
                                "reason": "command_extracted",
                                "paths": extracted,
                            }
                        )
                    else:
                        excluded.append(
                            {
                                "task_id": task.get("id"),
                                "selector": selector,
                                "reason": "non_path_selector_dropped",
                            }
                        )
            narrow["selectors"] = kept
            task["narrow_tests"] = narrow
        normalized_tasks.append(task)

    projected = dict(payload)
    projected["tasks"] = normalized_tasks

    test_selection = payload.get("test_selection")
    if isinstance(test_selection, Mapping):
        ts = dict(test_selection)
        command_override = ts.get("command_override")
        if isinstance(command_override, str) and command_override.strip():
            override_paths = _extract_pytest_paths_from_command(command_override)
            if not override_paths:
                # Malformed override (e.g. quoted command list): rebuild from
                # the union of extracted per-task paths, else full-suite.
                all_paths: list[str] = []
                for entry in excluded:
                    for path in entry.get("paths") or []:
                        if path not in all_paths:
                            all_paths.append(path)
                override_paths = all_paths
            if override_paths:
                ts["command_override"] = _build_pytest_command(
                    override_paths,
                    timeout_seconds=_DEFAULT_POST_EXECUTE_MAX_SECONDS,
                    extra_args="--no-header",
                )
            else:
                ts.pop("command_override", None)
                ts["mode"] = "full"
                ts["selectors_used"] = []
        projected["test_selection"] = ts

    effective_jobs = compile_validation_jobs(projected)
    original_jobs = payload.get("validation_jobs")
    return {
        "effective_jobs": effective_jobs,
        "original_jobs": [dict(j) for j in original_jobs] if isinstance(original_jobs, list) else [],
        "excluded": excluded,
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
    "SELECTOR_DEFERRED",
    "SELECTOR_INVALID",
    "SELECTOR_READY",
    "SelectorLifecycle",
    "classify_selector_lifecycle",
    "compile_validation_jobs",
    "declared_task_output_paths",
    "deferred_selector_evidence",
    "graph_declared_output_paths",
    "normalize_selector_path",
    "project_legacy_validation_contract",
    "validate_model_validation_jobs",
    "validate_narrow_selector_shape",
]
