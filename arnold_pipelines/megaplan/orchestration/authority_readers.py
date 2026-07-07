"""M2 authority-reader route inventory.

Every production site that reads raw terminal task status, milestone outcome,
or batch completion state and can increase authority (by skipping work,
unblocking dependencies, resuming/redriving, selecting a plan, classifying
success, setting success exit status, or advancing work) must be listed here
with one of three dispositions:

* ``migrated`` — rewired through the shared authority adapter (TODO in later
  M2 steps).
* ``tested`` — covered by explicit authority-aware tests.
* ``deferred`` — not migrated in this milestone, with an explicit reason.
  Informational/status-only readers are also classified here.

This inventory is the source of truth for the T16 raw-status grep/code audit
and the SC1 sense check.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.observability.events import EventKind, emit
from arnold_pipelines.megaplan._core import list_batch_artifacts
from arnold_pipelines.megaplan.orchestration.completion_io import (
    read_typed_completion_verdict,
)
from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    ArtifactRef,
    EvidenceRef,
    EvidenceStatus,
    TrustClass,
)
from arnold_pipelines.megaplan.orchestration.rubber_stamp import is_rubber_stamp
from arnold_pipelines.megaplan.orchestration.task_satisfaction import (
    EvidenceExecutionWindow,
    TaskSatisfactionResult,
    is_task_satisfied,
)

# ── Route disposition vocabulary ──────────────────────────────────────────

MIGRATED = "migrated"
TESTED = "tested"
DEFERRED = "deferred"
INFORMATIONAL = "informational"


@dataclass(frozen=True)
class AuthorityRoute:
    """A single authority-increasing or informational reader route."""

    id: str
    file: str
    line_range: str
    description: str
    disposition: str  # migrated | tested | deferred | informational
    owner_or_reason: str
    route_family: str  # execute | resume | chain | supervisor | status | timeout


AUTHORITATIVE_TASK_STATUSES = frozenset(
    status.value
    for status in (
        EvidenceStatus.satisfied,
        EvidenceStatus.waived,
        EvidenceStatus.not_applicable,
    )
)

AUTHORITY_DIVERGENCE_LEDGER = "authority_divergence.jsonl"
_TERMINAL_AUTHORITY_CLAIMS = frozenset({"done", "skipped", "waived", "not_applicable"})
_AUDIT_RESEARCH_NOTES_MIN_LEN = 100


@dataclass(frozen=True)
class AuthorityDecision:
    """Authority adapter decision for one task.

    ``status`` is copied from ``is_task_satisfied``. Raw legacy terminal labels
    are retained as diagnostics only; they never become success by themselves.
    """

    task_id: str
    status: EvidenceStatus
    satisfied: bool
    evidence: tuple[EvidenceRef, ...] = ()
    diagnostics: dict[str, Any] = field(default_factory=dict)
    missing_outputs: tuple[str, ...] = ()
    stale_evidence: tuple[str, ...] = ()
    would_block_reasons: tuple[str, ...] = ()
    error: str | None = None

    @property
    def authoritative(self) -> bool:
        return self.status in {
            EvidenceStatus.satisfied,
            EvidenceStatus.waived,
            EvidenceStatus.not_applicable,
        }

    @classmethod
    def from_result(
        cls,
        task_id: str,
        result: TaskSatisfactionResult,
        *,
        diagnostics: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> "AuthorityDecision":
        merged_diagnostics = dict(result.diagnostics)
        if diagnostics:
            merged_diagnostics.update(dict(diagnostics))
        return cls(
            task_id=task_id,
            status=result.status,
            satisfied=result.satisfied,
            evidence=result.evidence,
            diagnostics=merged_diagnostics,
            missing_outputs=result.missing_outputs,
            stale_evidence=result.stale_evidence,
            would_block_reasons=result.would_block_reasons,
            error=error,
        )

    @classmethod
    def unknown(
        cls,
        task_id: str,
        *,
        reason: str,
        diagnostics: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> "AuthorityDecision":
        merged = {"reason": reason}
        if diagnostics:
            merged.update(dict(diagnostics))
        return cls(
            task_id=task_id,
            status=EvidenceStatus.unknown,
            satisfied=False,
            diagnostics=merged,
            would_block_reasons=(reason,),
            error=error,
        )


def authority_decision_for_task(
    task: Mapping[str, Any],
    evidence_nucleus: Any,
    *,
    current_head: str | None = None,
    current_code_hash: str | None = None,
    execution_window: EvidenceExecutionWindow | None = None,
) -> AuthorityDecision:
    """Return the authority decision for one task via ``is_task_satisfied``."""

    task_id = _task_id(task)
    try:
        result = is_task_satisfied(
            task,
            evidence_nucleus,
            current_head=current_head,
            current_code_hash=current_code_hash,
            execution_window=execution_window,
        )
    except Exception as exc:
        return AuthorityDecision.unknown(
            task_id,
            reason="is_task_satisfied_error",
            diagnostics={"exception_type": type(exc).__name__},
            error=str(exc),
        )
    return AuthorityDecision.from_result(
        task_id,
        result,
        diagnostics={"raw_terminal_status": _optional_str(task.get("status"))},
    )


def corroborated_completed_task_ids(
    tasks: Iterable[Mapping[str, Any]],
    *,
    plan_dir: Path | str | None = None,
    evidence_nucleus: Any = None,
    current_head: str | None = None,
    current_code_hash: str | None = None,
    execution_window: EvidenceExecutionWindow | None = None,
    decisions: dict[str, AuthorityDecision] | None = None,
) -> set[str]:
    """Return task IDs with authoritative satisfied/waived/not-applicable evidence.

    The only success path is an ``is_task_satisfied`` decision. Per-task errors
    degrade to ``unknown`` and do not stop other tasks from being evaluated.
    """

    task_records = tuple(tasks)
    nucleus, load_diagnostics = _resolve_evidence_nucleus(
        plan_dir=Path(plan_dir) if plan_dir is not None else None,
        evidence_nucleus=evidence_nucleus,
        default_head=current_head,
    )
    completed: set[str] = set()
    for task in task_records:
        task_id = _task_id(task)
        task_nucleus = tuple(nucleus)
        diagnostics = dict(load_diagnostics)
        if any(error.get("scope") == "task" and error.get("task_id") == task_id for error in load_diagnostics.get("errors", ())):
            task_nucleus = ()
        try:
            result = is_task_satisfied(
                task,
                task_nucleus,
                current_head=current_head,
                current_code_hash=current_code_hash,
                execution_window=execution_window,
            )
            decision = AuthorityDecision.from_result(
                task_id,
                result,
                diagnostics={
                    **diagnostics,
                    "raw_terminal_status": _optional_str(task.get("status")),
                },
            )
        except Exception as exc:
            decision = AuthorityDecision.unknown(
                task_id,
                reason="is_task_satisfied_error",
                diagnostics={"exception_type": type(exc).__name__, **diagnostics},
                error=str(exc),
            )
        if plan_dir is not None:
            _emit_authority_divergence_diagnostics(Path(plan_dir), task, decision)
        if decisions is not None:
            decisions[task_id] = decision
        if decision.authoritative:
            completed.add(task_id)
    return completed


def scheduler_completed_ids(
    tasks: Iterable[Mapping[str, Any]],
    *,
    plan_dir: Path | str | None = None,
    evidence_nucleus: Any = None,
    current_head: str | None = None,
    current_code_hash: str | None = None,
    execution_window: EvidenceExecutionWindow | None = None,
    decisions: dict[str, AuthorityDecision] | None = None,
) -> set[str]:
    """Return the production ``completed_ids`` set for the pure topo scheduler.

    Scheduler ``completed_ids`` must be corroborated authority decisions, not
    raw ``status="done"`` / ``"skipped"`` claims. This wrapper makes that
    boundary explicit at production call sites while keeping the scheduler
    itself pure and evidence-agnostic. When available, the helper also threads
    through the current git HEAD so stale task evidence cannot unlock
    dependents in production.
    """

    resolved_plan_dir = Path(plan_dir) if plan_dir is not None else None
    resolved_current_head = current_head
    if resolved_current_head is None and resolved_plan_dir is not None:
        resolved_current_head = _best_effort_git_head(resolved_plan_dir)

    return corroborated_completed_task_ids(
        tasks,
        plan_dir=resolved_plan_dir,
        evidence_nucleus=evidence_nucleus,
        current_head=resolved_current_head,
        current_code_hash=current_code_hash,
        execution_window=execution_window,
        decisions=decisions,
    )


def execute_execution_window(
    state: Mapping[str, Any] | None,
    *,
    project_dir: Path,
    current_head: str | None = None,
) -> EvidenceExecutionWindow | None:
    """Return the execution-window freshness envelope from persisted plan state."""

    if not isinstance(state, Mapping):
        return None
    meta = state.get("meta")
    if not isinstance(meta, Mapping):
        return None
    baseline = meta.get("execution_baseline")
    if not isinstance(baseline, Mapping):
        return None
    base_sha = _optional_str(baseline.get("base_sha")) or _optional_str(
        baseline.get("head")
    )
    if base_sha is None:
        return None
    head_sha = current_head or _optional_str(baseline.get("head"))
    base_ref = _optional_str(baseline.get("base_ref"))
    return EvidenceExecutionWindow(
        project_dir=project_dir,
        base_sha=base_sha,
        head_sha=head_sha,
        base_ref=base_ref,
    )


def effective_execute_completed_task_ids(
    tasks: Iterable[Mapping[str, Any]],
    *,
    plan_dir: Path | str | None = None,
    project_dir: Path | str | None = None,
    state: Mapping[str, Any] | None = None,
    evidence_nucleus: Any = None,
    current_head: str | None = None,
    current_code_hash: str | None = None,
    decisions: dict[str, AuthorityDecision] | None = None,
) -> set[str]:
    """Return execute completion IDs with execution-window freshness and explained skips.

    Execute scheduling and end-of-run accounting need one shared notion of
    "effectively complete": corroborated task evidence may come from an earlier
    commit within the same execution window, and conditional tasks can be
    explicitly skipped with a substantive executor note. Execute also treats
    narrow verification checkpoints as complete when their only declared
    command outputs are already corroborated by another authoritative task in
    the same execute run.
    """

    resolved_plan_dir = Path(plan_dir) if plan_dir is not None else None
    resolved_project_dir = Path(project_dir) if project_dir is not None else None
    if resolved_project_dir is None and isinstance(state, Mapping):
        config = state.get("config")
        raw_project_dir = config.get("project_dir") if isinstance(config, Mapping) else None
        if isinstance(raw_project_dir, (str, Path)):
            resolved_project_dir = Path(raw_project_dir)
    if current_head is None:
        baseline_head = _execution_baseline_head(state)
        current_head = _resolve_execute_authority_current_head(
            resolved_plan_dir,
            project_dir=resolved_project_dir,
            baseline_head=baseline_head,
        )
    execution_window = (
        execute_execution_window(
            state,
            project_dir=resolved_project_dir,
            current_head=current_head,
        )
        if resolved_project_dir is not None
        else None
    )
    completed = corroborated_completed_task_ids(
        tasks,
        plan_dir=resolved_plan_dir,
        evidence_nucleus=evidence_nucleus,
        current_head=current_head,
        current_code_hash=current_code_hash,
        execution_window=execution_window,
        decisions=decisions,
    )
    explained_skips = {
        task_id
        for task in tasks
        if isinstance(task, Mapping)
        and isinstance(task_id := _task_id(task), str)
        and _is_explained_skip(task)
    }
    completed |= explained_skips
    explained_noops = {
        task_id
        for task in tasks
        if isinstance(task, Mapping)
        and isinstance(task_id := _task_id(task), str)
        and _is_explained_noop_completion(task)
    }
    completed |= explained_noops
    if decisions is not None:
        for task in tasks:
            if not isinstance(task, Mapping):
                continue
            task_id = _task_id(task)
            if task_id in explained_skips:
                decisions[task_id] = _explained_skip_decision(task_id, task)
            elif task_id in explained_noops:
                decisions[task_id] = _explained_noop_decision(task_id, task)

    authoritative_commands = {
        command
        for task in tasks
        if isinstance(task, Mapping)
        and _task_id(task) in completed
        for command in _string_values(task.get("commands_run"))
    }
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        task_id = _task_id(task)
        if task_id in completed or not _is_execute_command_checkpoint(task):
            continue
        commands = set(_string_values(task.get("commands_run")))
        if commands and commands.issubset(authoritative_commands):
            completed.add(task_id)
            if decisions is not None:
                decisions[task_id] = AuthorityDecision(
                    task_id=task_id,
                    status=EvidenceStatus.satisfied,
                    satisfied=True,
                    diagnostics={
                        "raw_terminal_status": _optional_str(task.get("status")),
                        "execute_completion": "shared_authoritative_commands",
                    },
                )
    return completed


def _is_explained_skip(task: Mapping[str, Any]) -> bool:
    return _optional_str(task.get("status")) == "skipped" and (
        _optional_str(task.get("reviewer_verdict")) == "deferred_baseline_unavailable"
        or (
            isinstance(task.get("executor_notes"), str)
            and task["executor_notes"].strip()
            and not is_rubber_stamp(task["executor_notes"], strict=True)
        )
    )


def _is_explained_noop_completion(task: Mapping[str, Any]) -> bool:
    status = _optional_str(task.get("status"))
    if status not in {"done", "completed"}:
        return False
    if _declared_task_outputs(task):
        return False
    notes = task.get("executor_notes")
    return (
        isinstance(notes, str)
        and notes.strip()
        and not is_rubber_stamp(notes, strict=True)
    )


def _explained_skip_decision(task_id: str, task: Mapping[str, Any]) -> AuthorityDecision:
    return AuthorityDecision(
        task_id=task_id,
        status=EvidenceStatus.not_applicable,
        satisfied=False,
        diagnostics={
            "raw_terminal_status": _optional_str(task.get("status")),
            "execute_completion": "explained_skip",
        },
    )


def _explained_noop_decision(task_id: str, task: Mapping[str, Any]) -> AuthorityDecision:
    return AuthorityDecision(
        task_id=task_id,
        status=EvidenceStatus.satisfied,
        satisfied=True,
        diagnostics={
            "raw_terminal_status": _optional_str(task.get("status")),
            "execute_completion": "explained_noop_completion",
        },
    )


def _declared_task_outputs(task: Mapping[str, Any]) -> tuple[str, ...]:
    declared: list[str] = []
    for key in ("files_changed", "commands_run", "evidence_files", "sections_written"):
        values = task.get(key)
        if isinstance(values, str):
            if values.strip():
                declared.append(key)
        elif isinstance(values, Sequence):
            if any(isinstance(item, str) and item.strip() for item in values):
                declared.append(key)
    return tuple(declared)


def _execution_baseline_head(state: Mapping[str, Any] | None) -> str | None:
    if not isinstance(state, Mapping):
        return None
    meta = state.get("meta")
    if not isinstance(meta, Mapping):
        return None
    baseline = meta.get("execution_baseline")
    if not isinstance(baseline, Mapping):
        return None
    head = baseline.get("head")
    return head.strip() if isinstance(head, str) and head.strip() else None


def _resolve_execute_authority_current_head(
    plan_dir: Path | None,
    *,
    project_dir: Path | None,
    baseline_head: str | None,
) -> str | None:
    actual_head = _best_effort_git_head_for_path(project_dir) if project_dir is not None else None
    recorded_head = _latest_recorded_execution_head(plan_dir) if plan_dir is not None else None
    if actual_head and recorded_head:
        if actual_head == recorded_head:
            return actual_head
        if project_dir is not None:
            if _git_is_ancestor(project_dir, recorded_head, actual_head):
                return actual_head
            if _git_is_ancestor(project_dir, actual_head, recorded_head):
                return recorded_head
    return recorded_head or baseline_head or actual_head


def _is_execute_command_checkpoint(task: Mapping[str, Any]) -> bool:
    if _optional_str(task.get("status")) != "pending":
        return False
    if _optional_str(task.get("kind")) != "test":
        return False
    if not _string_values(task.get("commands_run")):
        return False
    return not any(
        _string_values(task.get(field))
        for field in ("files_changed", "evidence_files", "sections_written")
    )


def load_evidence_nucleus(
    plan_dir: Path | str,
    *,
    default_head: str | None = None,
) -> tuple[EvidenceRef, ...]:
    """Load the small task evidence nucleus from existing plan artifacts."""

    root = Path(plan_dir)
    refs: list[EvidenceRef] = []
    verdict = read_typed_completion_verdict(root)
    if verdict is not None:
        refs.extend(verdict.evidence)
    for artifact_path in _iter_existing_artifacts(root):
        refs.extend(
            _evidence_from_execution_artifact(
                root,
                artifact_path,
                default_head=default_head,
            )
        )
    return tuple(refs)


def _resolve_evidence_nucleus(
    *,
    plan_dir: Path | None,
    evidence_nucleus: Any,
    default_head: str | None = None,
) -> tuple[tuple[EvidenceRef, ...], dict[str, Any]]:
    refs: list[EvidenceRef] = []
    diagnostics: dict[str, Any] = {"evidence_sources": []}
    if evidence_nucleus is not None:
        refs.extend(_normalize_refs(evidence_nucleus))
        diagnostics["evidence_sources"].append("provided")
    if plan_dir is not None:
        try:
            loaded = load_evidence_nucleus(plan_dir, default_head=default_head)
            refs.extend(loaded)
            diagnostics["evidence_sources"].append("plan_artifacts")
            diagnostics["loaded_evidence_count"] = len(loaded)
        except Exception as exc:
            diagnostics.setdefault("errors", []).append(
                {
                    "scope": "plan",
                    "reason": "load_evidence_nucleus_error",
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
    return tuple(refs), diagnostics


def _iter_existing_artifacts(plan_dir: Path) -> tuple[Path, ...]:
    paths = sorted(list_batch_artifacts(plan_dir))
    finalize = plan_dir / "finalize.json"
    if finalize.is_file():
        paths.append(finalize)
    return tuple(paths)


def _evidence_from_execution_artifact(
    plan_dir: Path,
    artifact_path: Path,
    *,
    default_head: str | None = None,
) -> tuple[EvidenceRef, ...]:
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, Mapping):
        return ()

    refs: list[EvidenceRef] = []
    refs.extend(_normalize_refs(payload.get("evidence")))
    for record in _task_records(payload):
        refs.extend(_normalize_refs(record.get("evidence")))
        refs.extend(
            _evidence_from_task_record(
                record,
                artifact_path,
                root=plan_dir,
                default_head=default_head,
            )
        )
    return tuple(refs)


def _task_records(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    for key in ("task_updates", "tasks"):
        raw = payload.get(key)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            records.extend(item for item in raw if isinstance(item, Mapping))
    return tuple(records)


def _best_effort_git_head_for_path(path: Path) -> str | None:
    """Return the git HEAD for the repo containing *path*, if available."""

    root = path if path.is_dir() else path.parent
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def _latest_recorded_execution_head(plan_dir: Path) -> str | None:
    for path in sorted(
        list_batch_artifacts(plan_dir),
        key=_execution_batch_sort_key,
        reverse=True,
    ):
        head = _latest_head_in_artifact(path)
        if head:
            return head
    return _latest_head_in_artifact(plan_dir / "finalize.json")


def _latest_head_in_artifact(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    latest_head: str | None = None
    for key in ("task_updates", "tasks"):
        raw_records = payload.get(key)
        if not isinstance(raw_records, Sequence):
            continue
        for record in raw_records:
            if not isinstance(record, Mapping):
                continue
            observed = record.get("head_sha") or record.get("head")
            if isinstance(observed, str) and observed.strip():
                latest_head = observed.strip()
    return latest_head


def _execution_batch_sort_key(path: Path) -> int:
    name = path.stem
    try:
        return int(name.rsplit("_", 1)[-1])
    except ValueError:
        return -1


def _git_is_ancestor(project_dir: Path, ancestor: str, descendant: str) -> bool:
    try:
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=project_dir,
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _evidence_from_task_record(
    record: Mapping[str, Any],
    artifact_path: Path,
    *,
    root: Path,
    default_head: str | None = None,
) -> tuple[EvidenceRef, ...]:
    task_id = _task_id(record)
    fallback_head = _optional_str(record.get("head_sha") or record.get("head"))
    if fallback_head is None:
        fallback_head = _optional_str(default_head)
    if fallback_head is None and root is not None:
        fallback_head = _best_effort_git_head_for_path(root)
    refs: list[EvidenceRef] = []
    # Only treat reported files/commands as corroborating evidence when the
    # task has reached a terminal state. Finalize may pre-attribute expected
    # files to pending tasks; those speculative attributions must not count
    # as completed work before the executor has run.
    terminal_statuses = {"done", "skipped", "waived", "not_applicable"}
    status = _optional_str(record.get("status"))
    if status in terminal_statuses:
        for field_name in ("files_changed", "commands_run", "evidence_files", "sections_written"):
            for value in _string_values(record.get(field_name)):
                refs.append(
                    EvidenceRef(
                        kind=f"task_{field_name}",
                        status=EvidenceStatus.satisfied,
                        summary=f"{field_name} reported for {task_id}",
                        details={
                            "task_id": task_id,
                            field_name: [value],
                            "head_sha": fallback_head,
                            "code_hash": _optional_str(record.get("code_hash")),
                        },
                        trust_class=TrustClass.evidence,
                        artifact=ArtifactRef(path=_relative_artifact_path(artifact_path, root)),
                        source=artifact_path.name,
                        subject=task_id,
                        code_hash=_optional_str(record.get("code_hash")),
                    )
                )
    kind = _optional_str(record.get("kind"))
    notes = _optional_str(record.get("executor_notes"))
    if (
        not refs
        and kind in {"audit", "research"}
        and notes is not None
        and len(notes.strip()) >= _AUDIT_RESEARCH_NOTES_MIN_LEN
        and not is_rubber_stamp(notes, strict=True)
    ):
        refs.append(
            EvidenceRef(
                kind="task_executor_notes",
                status=EvidenceStatus.satisfied,
                summary=f"Substantive {kind} notes reported for {task_id}",
                details={
                    "task_id": task_id,
                    "kind": kind,
                    "executor_notes_length": len(notes.strip()),
                    "head_sha": fallback_head,
                    "code_hash": _optional_str(record.get("code_hash")),
                },
                trust_class=TrustClass.evidence,
                artifact=ArtifactRef(path=_relative_artifact_path(artifact_path, root)),
                source=artifact_path.name,
                subject=task_id,
                code_hash=_optional_str(record.get("code_hash")),
            )
        )
    if not refs and _optional_str(record.get("status")) in {"waived", "not_applicable"}:
        status = EvidenceStatus(_optional_str(record.get("status")))
        refs.append(
            EvidenceRef(
                kind="task_terminal_exception",
                status=status,
                summary=f"{status.value} task exception for {task_id}",
                details={"task_id": task_id},
                trust_class=TrustClass.judgment,
                artifact=ArtifactRef(path=_relative_artifact_path(artifact_path, root)),
                source=artifact_path.name,
                subject=task_id,
            )
        )
    return tuple(refs)


def _normalize_refs(value: Any) -> tuple[EvidenceRef, ...]:
    if value is None:
        return ()
    if isinstance(value, EvidenceRef):
        return (value,)
    if isinstance(value, Mapping):
        return (EvidenceRef.from_dict(dict(value)),)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        refs: list[EvidenceRef] = []
        for item in value:
            if isinstance(item, EvidenceRef):
                refs.append(item)
            elif isinstance(item, Mapping):
                refs.append(EvidenceRef.from_dict(dict(item)))
        return tuple(refs)
    return ()


def _relative_artifact_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _task_id(task: Mapping[str, Any]) -> str:
    return str(task.get("task_id") or task.get("id") or "")


def _best_effort_git_head(plan_dir: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=plan_dir,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = completed.stdout.strip()
    return head or None


def _string_values(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Mapping):
        return _string_values(value.get("path") or value.get("name") or value.get("id"))
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        result: list[str] = []
        for item in value:
            result.extend(_string_values(item))
        return tuple(item for item in result if item)
    return (str(value),)


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _emit_authority_divergence_diagnostics(
    plan_dir: Path,
    task: Mapping[str, Any],
    decision: AuthorityDecision,
) -> None:
    payload = _authority_divergence_payload(task, decision)
    if payload is None:
        return
    try:
        _append_authority_divergence_jsonl(plan_dir, payload)
    except Exception:
        pass
    try:
        emit(EventKind.AUTHORITY_DIVERGENCE, plan_dir=plan_dir, phase="execute", payload=payload)
    except Exception:
        pass


def _authority_divergence_payload(
    task: Mapping[str, Any],
    decision: AuthorityDecision,
) -> dict[str, Any] | None:
    raw_status = _optional_str(task.get("status"))
    if (
        raw_status not in _TERMINAL_AUTHORITY_CLAIMS
        or decision.authoritative
        or _is_explained_skip(task)
        or _is_explained_noop_completion(task)
    ):
        return None
    reasons = tuple(
        str(reason)
        for reason in decision.would_block_reasons
        if isinstance(reason, str) and reason
    )
    return {
        "diagnostic_version": 1,
        "task_id": decision.task_id,
        "raw_terminal_status": raw_status,
        "authority_status": decision.status.value,
        "authoritative": decision.authoritative,
        "reason": reasons[0] if reasons else _optional_str(decision.diagnostics.get("reason")) or "authority_diverged",
        "missing_outputs": list(decision.missing_outputs),
        "stale_evidence": list(decision.stale_evidence),
        "would_block_reasons": list(reasons),
        "error": decision.error,
        "diagnostics": dict(decision.diagnostics),
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }


def _append_authority_divergence_jsonl(plan_dir: Path, payload: Mapping[str, Any]) -> None:
    path = plan_dir / AUTHORITY_DIVERGENCE_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), sort_keys=True) + "\n")


# ── Route inventory ────────────────────────────────────────────────────────

AUTHORITY_ROUTES: tuple[AuthorityRoute, ...] = (
    # ═══ Execute family ═══════════════════════════════════════════════════
    AuthorityRoute(
        id="EXEC-01",
        file="arnold_pipelines/megaplan/execute/batch.py",
        line_range="1650-1654",
        description="Auto-loop task selection: builds completed_task_ids from raw task.get('status') in {'done','skipped'}",
        disposition=MIGRATED,
        owner_or_reason="T4: replace with corroborated_completed_task_ids() via authority adapter",
        route_family="execute",
    ),
    AuthorityRoute(
        id="EXEC-02",
        file="arnold_pipelines/megaplan/execute/batch.py",
        line_range="951-957",
        description="Batch prerequisite gate: completed_ids from batch_status_overlay trusting raw {'done','skipped'}",
        disposition=MIGRATED,
        owner_or_reason="T6: migrate to authority decisions; prior-batch divergence blocks, current-batch repairs",
        route_family="execute",
    ),
    AuthorityRoute(
        id="EXEC-03",
        file="arnold_pipelines/megaplan/execute/batch.py",
        line_range="1114-1118",
        description="All-tracked check for batch completion: all(t.get('status') in {'done','skipped'})",
        disposition=MIGRATED,
        owner_or_reason="T6/T7: replace with corroborated completed IDs; divergent tracked tasks → BLOCKED_BY_PREREQ",
        route_family="execute",
    ),
    AuthorityRoute(
        id="EXEC-04",
        file="arnold_pipelines/megaplan/execute/batch.py",
        line_range="2083",
        description="Post-batch completed_id update re-reading raw status from finalize.json",
        disposition=MIGRATED,
        owner_or_reason="T4: use corroborated completed set post-batch rather than raw status re-read",
        route_family="execute",
    ),
    AuthorityRoute(
        id="EXEC-05",
        file="arnold_pipelines/megaplan/_core/io.py",
        line_range="58-104",
        description="compute_task_batches: accepts completed_ids as satisfied deps; wrapper must supply corroborated IDs",
        disposition=MIGRATED,
        owner_or_reason="T5: keep function pure; add call-site wrapper that passes only corroborated completed_ids",
        route_family="execute",
    ),
    AuthorityRoute(
        id="EXEC-06",
        file="arnold_pipelines/megaplan/_core/scheduler/topo.py",
        line_range="15-62",
        description="schedule_batches: threads completed_ids through; same pure-assertion consumer as compute_task_batches",
        disposition=MIGRATED,
        owner_or_reason="T5: keep function pure; guarantee input completed_ids are already corroborated by wrapper",
        route_family="execute",
    ),
    AuthorityRoute(
        id="EXEC-07",
        file="arnold_pipelines/megaplan/execute/_binding/reducer.py",
        line_range="132",
        description="all_tracked = all(t.get('status') in {'done','skipped'}) determines BatchOutcome.SUCCESS",
        disposition=MIGRATED,
        owner_or_reason="T7: use authority-aware corroborated completed IDs; raw done divergence → non-success",
        route_family="execute",
    ),
    AuthorityRoute(
        id="EXEC-08",
        file="arnold_pipelines/megaplan/execute/timeout.py",
        line_range="350",
        description="Timeout recovery completed_tasks from raw status in {'done','skipped'}",
        disposition=MIGRATED,
        owner_or_reason="T8: use best-effort corroborated completion; label uncorroborated as asserted_terminal",
        route_family="execute",
    ),
    AuthorityRoute(
        id="EXEC-09",
        file="arnold_pipelines/megaplan/prompts/execute.py",
        line_range="156",
        description="Prompt helper filtering done_tasks from raw task.get('status') in ('done','skipped')",
        disposition=MIGRATED,
        owner_or_reason="T4: feed only corroborated completed IDs to prompt helpers showing completed dependencies",
        route_family="execute",
    ),

    # ═══ Resume / redrive family ══════════════════════════════════════════
    AuthorityRoute(
        id="RESUME-01",
        file="arnold_pipelines/megaplan/_core/workflow.py",
        line_range="508-699",
        description="resume_plan: reads resume_cursor, dispatches phase, pops cursor on success — no corroboration",
        disposition=MIGRATED,
        owner_or_reason="T9: guard with authority adapter; block if execute data incomplete; preserve cursor on divergence",
        route_family="resume",
    ),
    AuthorityRoute(
        id="RESUME-02",
        file="arnold_pipelines/megaplan/_pipeline/resume.py",
        line_range="133,166",
        description="Pipeline resume cursor: ResumeCursor.load() and with_entry() re-enter pipeline without corroboration",
        disposition=MIGRATED,
        owner_or_reason="T9: storage support only; annotate if guard needs cursor payload preservation",
        route_family="resume",
    ),
    AuthorityRoute(
        id="RESUME-03",
        file="arnold_pipelines/megaplan/auto.py",
        line_range="1675-1691",
        description="_active_phase_already_completed: trusts phase_produced_state without task-level corroboration",
        disposition=MIGRATED,
        owner_or_reason="T10: for execute-produced states require corroborated task completion before clearing active step",
        route_family="resume",
    ),
    AuthorityRoute(
        id="RESUME-04",
        file="arnold_pipelines/megaplan/auto.py",
        line_range="2217-2280",
        description="Auto terminal success signaling: terminal_status == 'done' gates PLAN_FINISHED, exit-code-0, shadow verdict",
        disposition=MIGRATED,
        owner_or_reason="T10: require corroborated task/milestone completion or emit divergence outcome; preserve recoverability",
        route_family="resume",
    ),

    # ═══ Chain family ═════════════════════════════════════════════════════
    AuthorityRoute(
        id="CHAIN-01",
        file="arnold_pipelines/megaplan/chain/__init__.py",
        line_range="598-646",
        description="_latest_execution_batch_all_tasks_done: raw status=='done' check on batch artifacts + finalize.json",
        disposition=MIGRATED,
        owner_or_reason="T11: replace with authority-aware helper over latest batch + finalize task records",
        route_family="chain",
    ),
    AuthorityRoute(
        id="CHAIN-02",
        file="arnold_pipelines/megaplan/chain/__init__.py",
        line_range="887-973",
        description="_handle_outcome: advances on outcome.status in {'done','finalized'} without task-level corroboration",
        disposition=MIGRATED,
        owner_or_reason="T12: corroborate plan constituent tasks before returning 'advance' for done/finalized outcomes",
        route_family="chain",
    ),
    AuthorityRoute(
        id="CHAIN-03",
        file="arnold_pipelines/megaplan/chain/__init__.py",
        line_range="666-698",
        description="_recover_blocked_execute_if_tasks_done: uses _latest_execution_batch_all_tasks_done raw status",
        disposition=MIGRATED,
        owner_or_reason="T12: guard with same authority-aware helper; block on uncorroborated legacy state",
        route_family="chain",
    ),
    AuthorityRoute(
        id="CHAIN-04",
        file="arnold_pipelines/megaplan/chain/__init__.py",
        line_range="1125-1154",
        description="Seed plan terminal skip: compares plan state against TERMINAL_SKIP_STATES {'done','aborted','failed'}",
        disposition=MIGRATED,
        owner_or_reason="T12: corroborate before skipping seed phase; stop/block with diagnostics for uncorroborated legacy",
        route_family="chain",
    ),
    AuthorityRoute(
        id="CHAIN-05",
        file="arnold_pipelines/megaplan/chain/__init__.py",
        line_range="1167-1217",
        description="current_plan_name pointer reads used to skip or advance chain work",
        disposition=MIGRATED,
        owner_or_reason="T12: informational pointer reads are fine; skip/advance from pointer must be corroborated",
        route_family="chain",
    ),

    # ═══ Supervisor family ════════════════════════════════════════════════
    AuthorityRoute(
        id="SUP-01",
        file="arnold_pipelines/megaplan/supervisor/chain_runner.py",
        line_range="696-719",
        description="_recover_blocked_execute_if_tasks_done: duplicate of CHAIN-03 raw status check for blocked→executed",
        disposition=MIGRATED,
        owner_or_reason="T13: share or mirror chain's authority-aware helper; prevent raw-status drift between copies",
        route_family="supervisor",
    ),
    AuthorityRoute(
        id="SUP-02",
        file="arnold_pipelines/megaplan/supervisor/chain_runner.py",
        line_range="453-463",
        description="_assert_dependencies_completed: gates on completed_node_ids labels only — no evidence corroboration",
        disposition=MIGRATED,
        owner_or_reason="T13: replace with corroborated milestone/task authority for dependency unlocks",
        route_family="supervisor",
    ),
    AuthorityRoute(
        id="SUP-03",
        file="arnold_pipelines/megaplan/supervisor/chain_runner.py",
        line_range="97-385",
        description="run_chain milestone advancement loop: advances on LadderAction.ADVANCE from driver outcome",
        disposition=MIGRATED,
        owner_or_reason="T13: gate ADVANCE, PR-merge advancement, and blocked-execute recovery on shared authority helper",
        route_family="supervisor",
    ),
    AuthorityRoute(
        id="SUP-04",
        file="arnold_pipelines/megaplan/supervisor/chain_runner.py",
        line_range="150-385",
        description="Supervisor dependency gates, PR-merge advancement, and blocked-execute recovery in run_chain",
        disposition=MIGRATED,
        owner_or_reason="T13: use same authority semantics as canonical chain; divergence → blocked/stopped with diagnostics",
        route_family="supervisor",
    ),

    # ═══ Status-only / informational routes ═══════════════════════════════
    AuthorityRoute(
        id="STATUS-01",
        file="arnold_pipelines/megaplan/cli/status_view.py",
        line_range="586",
        description="Status view filtering: displays done/skipped task counts for operator visibility",
        disposition=INFORMATIONAL,
        owner_or_reason="Informational read; does not skip, unblock, resume, classify success, or advance work (SD3)",
        route_family="status",
    ),
    AuthorityRoute(
        id="STATUS-02",
        file="arnold_pipelines/megaplan/auto.py",
        line_range="1395-1455",
        description="_shadow_completion_verdict in auto drive: calls compute_verdict but only blocks in enforce mode",
        disposition=DEFERRED,
        owner_or_reason="Completion contract enforcement is a later milestone concern; shadow/warn modes are fail-open",
        route_family="status",
    ),
    AuthorityRoute(
        id="STATUS-03",
        file="arnold_pipelines/megaplan/chain/__init__.py",
        line_range="465-500",
        description="_shadow_milestone_completion_verdict: shadow-only; explicitly NOT enforcement",
        disposition=DEFERRED,
        owner_or_reason="Deferred to later milestone; documented as SHADOW-ONLY, fail-open, never blocks advancement",
        route_family="status",
    ),
    AuthorityRoute(
        id="STATUS-04",
        file="arnold_pipelines/megaplan/orchestration/completion_contract.py",
        line_range="1698",
        description="compute_verdict: milestone-level completion checking from objective evidence (git, artifacts, suites)",
        disposition=DEFERRED,
        owner_or_reason="Shadow-only with SHADOW_TODOS; deliberately not enforcement per M2 scope boundary (SD2)",
        route_family="status",
    ),
    AuthorityRoute(
        id="STATUS-05",
        file="arnold_pipelines/megaplan/auto.py",
        line_range="1406-1436",
        description="Shadow verdict in auto terminal: calls compute_verdict for completion contract shadow/warn/enforce",
        disposition=DEFERRED,
        owner_or_reason="Shadow verdict path; evidence/shadow infrastructure, not authority enforcement (SD2, success criterion 13)",
        route_family="status",
    ),
    AuthorityRoute(
        id="STATUS-06",
        file="arnold_pipelines/megaplan/chain/__init__.py",
        line_range="485-525",
        description="Shadow verdict in chain _handle_outcome flow: calls compute_verdict for milestone check",
        disposition=DEFERRED,
        owner_or_reason="Shadow verdict path; fail-open, non-blocking in shadow/warn modes; enforcement deferred",
        route_family="status",
    ),

    # ═══ Timeout-reporting (operator-reporting) ════════════════════════════
    AuthorityRoute(
        id="TIMEOUT-01",
        file="arnold_pipelines/megaplan/execute/timeout.py",
        line_range="1-388",
        description="Timeout recovery summary: best-effort operator reporting; not a blocking authority gate",
        disposition=MIGRATED,
        owner_or_reason="T8: migrate to best-effort corroborated completion; label uncorroborated; fail-open (SD3)",
        route_family="timeout",
    ),
)


# ── Convenience views ──────────────────────────────────────────────────────

def migrated_routes() -> tuple[AuthorityRoute, ...]:
    """Return every route with disposition == 'migrated'."""
    return tuple(r for r in AUTHORITY_ROUTES if r.disposition == MIGRATED)


def deferred_routes() -> tuple[AuthorityRoute, ...]:
    """Return every route with disposition == 'deferred'."""
    return tuple(r for r in AUTHORITY_ROUTES if r.disposition == DEFERRED)


def informational_routes() -> tuple[AuthorityRoute, ...]:
    """Return every route with disposition == 'informational'."""
    return tuple(r for r in AUTHORITY_ROUTES if r.disposition == INFORMATIONAL)


def routes_by_family(family: str) -> tuple[AuthorityRoute, ...]:
    """Return all routes for a given route_family."""
    return tuple(r for r in AUTHORITY_ROUTES if r.route_family == family)


def route_ids_by_disposition() -> dict[str, list[str]]:
    """Group route IDs by disposition for audit convenience."""
    result: dict[str, list[str]] = {}
    for r in AUTHORITY_ROUTES:
        result.setdefault(r.disposition, []).append(r.id)
    return result
