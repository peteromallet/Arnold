"""Pure task-done predicate over the M1 evidence contract.

``is_task_satisfied`` is an authority-reader helper, not a verifier. It does
not run providers, mutate plan state, or change routing. Callers hand it a task
claim plus the current evidence nucleus, and it corroborates the claim from
canonical :class:`EvidenceRef` records. When callers supply an execution window,
the helper uses git ancestry to distinguish stale evidence from evidence
recorded earlier in the same execution window.

Supported evidence nucleus inputs are intentionally small and typed:

* a ``CompletionVerdict`` instance,
* a verdict-shaped dict with an ``evidence`` array,
* a single ``EvidenceRef`` or evidence-ref dict,
* an iterable of ``EvidenceRef`` instances and/or evidence-ref dicts.

Every dict evidence ref is deserialized through ``EvidenceRef.from_dict`` so
legacy statuses such as ``fail-not-success`` remain canonical ``unsatisfied``
with diagnostics. The predicate evaluates only the declared M1 task-output
fields: ``files_changed``, ``commands_run``, ``evidence_files``, and
``sections_written``.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    ArtifactRef,
    EvidenceRef,
    EvidenceStatus,
)

DECLARED_OUTPUT_FIELDS: tuple[str, ...] = (
    "files_changed",
    "commands_run",
    "evidence_files",
    "sections_written",
)

LINK_DETAIL_KEYS: tuple[str, ...] = (
    "task_id",
    "task_ids",
    "tasks",
    "criterion_id",
    "criterion_ids",
    "criteria",
)


@dataclass(frozen=True)
class TaskSatisfactionResult:
    """Canonical task satisfaction decision with evidence and diagnostics."""

    status: EvidenceStatus
    evidence: tuple[EvidenceRef, ...] = ()
    diagnostics: dict[str, Any] = field(default_factory=dict)
    missing_outputs: tuple[str, ...] = ()
    stale_evidence: tuple[str, ...] = ()
    would_block_reasons: tuple[str, ...] = ()

    @property
    def satisfied(self) -> bool:
        """True only for canonical satisfied evidence."""

        return self.status == EvidenceStatus.satisfied


@dataclass(frozen=True)
class EvidenceExecutionWindow:
    """Git window in which prior evidence can remain fresh after commits."""

    project_dir: Path
    base_sha: str
    head_sha: str | None = None
    base_ref: str | None = None


def is_task_satisfied(
    task: Any,
    evidence_nucleus: Any,
    current_head: str | None = None,
    current_code_hash: str | None = None,
    execution_window: EvidenceExecutionWindow | None = None,
) -> TaskSatisfactionResult:
    """Return whether *task* is corroborated by canonical evidence.

    Missing declared outputs, missing linked evidence, stale head/code-hash
    evidence, and canonical ``unsatisfied`` evidence all make the task not
    satisfied unless linked evidence explicitly waives or marks the task as not
    applicable. Legacy or incomplete evidence degrades to canonical ``unknown``.
    """

    refs, normalization_diagnostics = _normalize_evidence_nucleus(evidence_nucleus)
    task_id = _task_value(task, "task_id") or _task_value(task, "id")
    criterion_ids = _criterion_ids(task)
    declared_outputs = _declared_outputs(task)

    linked_refs = tuple(
        ref
        for ref in refs
        if _evidence_links_task(ref, task_id, criterion_ids, declared_outputs)
    )

    diagnostics: dict[str, Any] = {
        "task_id": task_id,
        "declared_outputs": {key: list(values) for key, values in declared_outputs.items()},
        "linked_evidence_count": len(linked_refs),
        "evidence_count": len(refs),
    }
    diagnostics.update(normalization_diagnostics)

    missing_outputs = _missing_declared_outputs(declared_outputs, linked_refs)
    resolved_current_head = current_head or (
        execution_window.head_sha if execution_window is not None else None
    )
    stale_evidence = _stale_evidence(
        linked_refs,
        resolved_current_head,
        current_code_hash,
        execution_window=execution_window,
    )
    explicit_status = _explicit_terminal_status(linked_refs)

    would_block: list[str] = []
    if not linked_refs:
        would_block.append("missing_linked_evidence")
    for missing in missing_outputs:
        would_block.append(f"missing_output:{missing}")
    for stale in stale_evidence:
        would_block.append(f"stale_evidence:{stale}")
    for ref in linked_refs:
        if ref.status == EvidenceStatus.unsatisfied:
            would_block.append(f"unsatisfied_evidence:{ref.kind}")

    if explicit_status in {EvidenceStatus.waived, EvidenceStatus.not_applicable}:
        status = explicit_status
        would_block = []
    elif any(ref.status == EvidenceStatus.unsatisfied for ref in linked_refs):
        status = EvidenceStatus.unsatisfied
    elif missing_outputs:
        status = EvidenceStatus.unsatisfied
    elif any(item.startswith("head_mismatch") or item.startswith("code_hash_mismatch") for item in stale_evidence):
        status = EvidenceStatus.unsatisfied
    elif stale_evidence or not linked_refs:
        status = EvidenceStatus.unknown
    elif any(ref.status == EvidenceStatus.unknown for ref in linked_refs):
        status = EvidenceStatus.unknown
    else:
        status = EvidenceStatus.satisfied

    diagnostics["status"] = status.value
    return TaskSatisfactionResult(
        status=status,
        evidence=linked_refs,
        diagnostics=diagnostics,
        missing_outputs=missing_outputs,
        stale_evidence=stale_evidence,
        would_block_reasons=tuple(dict.fromkeys(would_block)),
    )


def _normalize_evidence_nucleus(value: Any) -> tuple[tuple[EvidenceRef, ...], dict[str, Any]]:
    diagnostics: dict[str, Any] = {}
    if value is None:
        return (), {"normalization": "missing_evidence_nucleus"}

    raw_evidence: Any
    if isinstance(value, EvidenceRef):
        raw_evidence = (value,)
    elif hasattr(value, "evidence") and not isinstance(value, Mapping):
        raw_evidence = getattr(value, "evidence")
        diagnostics["normalization"] = type(value).__name__
    elif isinstance(value, Mapping):
        if "evidence" in value:
            raw_evidence = value.get("evidence")
            diagnostics["normalization"] = "verdict_dict"
        else:
            raw_evidence = (value,)
            diagnostics["normalization"] = "evidence_ref_dict"
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        raw_evidence = value
        diagnostics["normalization"] = "iterable"
    else:
        return (), {"normalization": "unsupported_evidence_nucleus"}

    refs: list[EvidenceRef] = []
    skipped = 0
    if not isinstance(raw_evidence, Iterable) or isinstance(raw_evidence, (str, bytes)):
        raw_evidence = ()
    for item in raw_evidence:
        if isinstance(item, EvidenceRef):
            refs.append(item)
        elif isinstance(item, Mapping):
            refs.append(EvidenceRef.from_dict(dict(item)))
        else:
            skipped += 1
    if skipped:
        diagnostics["skipped_evidence_items"] = skipped
    return tuple(refs), diagnostics


def _declared_outputs(task: Any) -> dict[str, tuple[str, ...]]:
    declared: dict[str, tuple[str, ...]] = {}
    for key in DECLARED_OUTPUT_FIELDS:
        values = _string_tuple(_task_value(task, key))
        if values:
            declared[key] = values
    return declared


def _criterion_ids(task: Any) -> tuple[str, ...]:
    raw: list[Any] = []
    for key in ("criterion_id", "criterion_ids", "criteria"):
        value = _task_value(task, key)
        if isinstance(value, Mapping):
            raw.append(value.get("id") or value.get("criterion") or value.get("name"))
        elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            raw.extend(value)
        else:
            raw.append(value)
    return _string_tuple(raw)


def _evidence_links_task(
    ref: EvidenceRef,
    task_id: str | None,
    criterion_ids: tuple[str, ...],
    declared_outputs: dict[str, tuple[str, ...]],
) -> bool:
    if not task_id and not criterion_ids and not declared_outputs:
        return True

    link_values = set(_evidence_link_values(ref))
    if task_id and task_id in link_values:
        return True
    if criterion_ids and link_values.intersection(criterion_ids):
        return True
    if declared_outputs and _ref_matches_any_declared_output(ref, declared_outputs):
        return True
    if not link_values and not declared_outputs:
        return True
    return False


def _missing_declared_outputs(
    declared_outputs: dict[str, tuple[str, ...]],
    linked_refs: tuple[EvidenceRef, ...],
) -> tuple[str, ...]:
    missing: list[str] = []
    for field_name, values in declared_outputs.items():
        for value in values:
            if not any(_ref_matches_declared_output(ref, field_name, value) for ref in linked_refs):
                missing.append(f"{field_name}:{value}")
    return tuple(missing)


def _stale_evidence(
    refs: tuple[EvidenceRef, ...],
    current_head: str | None,
    current_code_hash: str | None,
    *,
    execution_window: EvidenceExecutionWindow | None = None,
) -> tuple[str, ...]:
    stale: list[str] = []
    for ref in refs:
        if current_head:
            observed_head = _first_string(ref.details, ("head_sha", "current_head", "head"))
            if observed_head is None:
                stale.append(f"missing_head:{ref.kind}")
            elif observed_head != current_head and not (
                _head_is_fresh_in_execution_window(
                    observed_head,
                    current_head,
                    execution_window,
                )
                or _head_is_ancestor(observed_head, current_head)
            ):
                stale.append(f"head_mismatch:{ref.kind}")
        if current_code_hash:
            observed_code_hash = ref.code_hash or _first_string(ref.details, ("code_hash",))
            if observed_code_hash is None:
                stale.append(f"missing_code_hash:{ref.kind}")
            elif observed_code_hash != current_code_hash:
                stale.append(f"code_hash_mismatch:{ref.kind}")
    return tuple(stale)


def _head_is_fresh_in_execution_window(
    observed_head: str,
    current_head: str,
    execution_window: EvidenceExecutionWindow | None,
) -> bool:
    if execution_window is None or not execution_window.base_sha:
        return False
    project_dir = execution_window.project_dir
    return _git_is_ancestor(project_dir, observed_head, current_head) and _git_is_ancestor(
        project_dir,
        execution_window.base_sha,
        observed_head,
    )


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


def _head_is_ancestor(ancestor: str, descendant: str) -> bool:
    """Return True if ``ancestor`` is an ancestor of (or equal to) ``descendant``.

    When the harness commits plan state between batches, task evidence is
    recorded at the pre-commit HEAD. Treating such evidence as stale causes
    infinite re-execution loops, so we accept any evidence whose HEAD is in
    the current branch history.
    """
    if ancestor == descendant:
        return True
    root = os.environ.get("MEGAPLAN_TARGET_ROOT") or os.environ.get("MEGAPLAN_PROJECT_DIR")
    cwd = Path(root) if root else Path.cwd()
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _explicit_terminal_status(refs: tuple[EvidenceRef, ...]) -> EvidenceStatus | None:
    statuses = {ref.status for ref in refs}
    if EvidenceStatus.waived in statuses:
        return EvidenceStatus.waived
    if EvidenceStatus.not_applicable in statuses:
        return EvidenceStatus.not_applicable
    return None


def _evidence_link_values(ref: EvidenceRef) -> tuple[str, ...]:
    values: list[Any] = []
    if ref.subject is not None:
        values.append(ref.subject)
    for key in LINK_DETAIL_KEYS:
        value = ref.details.get(key)
        if isinstance(value, Mapping):
            values.append(value.get("id") or value.get("task_id") or value.get("criterion_id"))
        elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            values.extend(value)
        else:
            values.append(value)
    return _string_tuple(values)


def _ref_matches_any_declared_output(
    ref: EvidenceRef,
    declared_outputs: dict[str, tuple[str, ...]],
) -> bool:
    return any(
        _ref_matches_declared_output(ref, field_name, value)
        for field_name, values in declared_outputs.items()
        for value in values
    )


def _ref_matches_declared_output(ref: EvidenceRef, field_name: str, value: str) -> bool:
    if value in _artifact_paths(ref):
        return True
    details_value = ref.details.get(field_name)
    if value in _string_tuple(details_value):
        return True
    if field_name == "commands_run":
        command = _first_string(ref.details, ("command", "cmd"))
        return command == value
    return False


def _artifact_paths(ref: EvidenceRef) -> tuple[str, ...]:
    artifacts: list[ArtifactRef] = []
    if ref.artifact is not None:
        artifacts.append(ref.artifact)
    artifacts.extend(ref.artifacts)
    return tuple(artifact.path for artifact in artifacts if artifact.path)


def _task_value(task: Any, key: str) -> Any:
    if isinstance(task, Mapping):
        return task.get(key)
    return getattr(task, key, None)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, Mapping):
        return _string_tuple(value.get("id") or value.get("path") or value.get("name"))
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        result: list[str] = []
        for item in value:
            result.extend(_string_tuple(item))
        return tuple(item for item in result if item)
    return (str(value),)


def _first_string(d: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = d.get(key)
        if isinstance(value, str) and value:
            return value
    return None
