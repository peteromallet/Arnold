"""Prompt context projection utilities.

Conservative, purpose-specific helpers that shape execute/review/rework
prompt payloads so persistent JSON ledgers remain complete on disk while
model prompts receive compact, worker-readable context plus provenance
references.

Prompt projection happens at prompt-render time.  Execute summaries may also
store bounded advisory path lists, but only with ArtifactRef-backed sidecars
that preserve the complete set on disk.
"""

from __future__ import annotations

import hashlib
import json
import os
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    _projection_canonical_dumps,
    now_utc,
)

# ---------------------------------------------------------------------------
# Character budgets for inline text fields
# ---------------------------------------------------------------------------

MAX_EXECUTOR_NOTES_CHARS = 600
MAX_COMPLEXITY_JUSTIFICATION_CHARS = 300
MAX_META_COMMENTARY_CHARS = 1500
MAX_DESCRIPTION_CHARS = 500
MAX_SENSE_CHECK_QUESTION_CHARS = 400
MAX_EXECUTION_OUTPUT_CHARS = 1500
MAX_EXECUTION_DEVIATIONS = 20
MAX_EXECUTION_DEVIATION_CHARS = 700
MAX_EXECUTION_COMMAND_CHARS = 300
MAX_AUDIT_FINDINGS = 20
MAX_AUDIT_FILES = 40
MAX_FILE_LIST_ITEMS = 20
MAX_BULK_SUMMARY_SAMPLES = 5
MAX_BULK_SUMMARY_INSTRUCTIONS = 5

# Completed-task context is prompt-only and must stay bounded even when a
# long-running plan has hundreds of completed task records on disk.
MAX_COMPLETED_TASK_RECEIPTS = 32
MAX_COMPLETED_TASK_RECEIPT_CONTEXT_CHARS = 24_000
MAX_COMPLETED_TASK_RECEIPT_ID_CHARS = 120
MAX_COMPLETED_TASK_RECEIPT_FILES = 6
MAX_COMPLETED_TASK_RECEIPT_COMMANDS = 3
MAX_COMPLETED_TASK_RECEIPT_EVIDENCE_FILES = 4


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


@dataclass
class PromptProjectionCapabilities:
    """Worker capabilities that gate artifact references in projected prompts.

    Conservative by default: capabilities are ``False`` unless explicitly
    set.  This ensures artifact references don't leak into prompts for
    workers that cannot read those paths.
    """

    can_read_plan_dir: bool = False
    can_read_project_dir: bool = False
    has_file_tools: bool = False
    checkpoint_write_access: bool = False

    @classmethod
    def conservative(cls) -> PromptProjectionCapabilities:
        """Return capabilities with everything ``False`` (safe default)."""
        return cls()

    @classmethod
    def full(cls) -> PromptProjectionCapabilities:
        """Return capabilities with everything ``True`` (backward compatible)."""
        return cls(
            can_read_plan_dir=True,
            can_read_project_dir=True,
            has_file_tools=True,
            checkpoint_write_access=True,
        )

    @classmethod
    def from_worker_caps(
        cls, worker_caps: set[str] | None = None
    ) -> PromptProjectionCapabilities:
        """Build from a worker capability set.

        Workers with ``read_files`` and/or ``run_shell`` are assumed to have
        full filesystem access.  Without those, artifact references are
        gated.
        """
        if worker_caps is None:
            return cls.conservative()
        has_read = "read_files" in worker_caps
        has_shell = "run_shell" in worker_caps
        return cls(
            can_read_plan_dir=has_read or has_shell,
            can_read_project_dir=has_read or has_shell,
            has_file_tools=has_read,
            checkpoint_write_access=has_read or has_shell,
        )

    def artifact_reference_allowed(self, *, path_hint: str = "") -> bool:
        """Return ``True`` when a file reference is safe to include.

        Simple heuristic: if the path looks like it lives inside a plan
        directory we need ``can_read_plan_dir``; otherwise we need
        ``can_read_project_dir``.  Both are gated on filesystem tool access.
        """
        if not self.has_file_tools and not self.can_read_project_dir:
            return False
        if "/.megaplan/" in path_hint or "plan_dir" in path_hint:
            return self.can_read_plan_dir
        return self.can_read_project_dir


# ---------------------------------------------------------------------------
# Low-level field helpers
# ---------------------------------------------------------------------------


def _brief_text(value: Any, *, limit: int) -> str:
    """Truncate a string to *limit* characters, preserving word boundaries."""
    text = value if isinstance(value, str) else str(value) if value is not None else ""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _project_list(
    values: list[Any],
    *,
    item_limit: int,
    text_limit: int,
) -> list[Any]:
    """Project a noisy list while recording omitted item count."""
    projected: list[Any] = []
    for item in values[:item_limit]:
        if isinstance(item, str):
            projected.append(_brief_text(item, limit=text_limit))
        elif isinstance(item, dict):
            projected.append({
                str(key): _brief_text(value, limit=text_limit)
                if isinstance(value, str)
                else value
                for key, value in item.items()
            })
        else:
            projected.append(item)
    omitted = len(values) - item_limit
    if omitted > 0:
        projected.append({"omitted_count": omitted, "reason": "prompt projection"})
    return projected


def _project_path_list(value: Any, *, item_limit: int = MAX_FILE_LIST_ITEMS) -> Any:
    if isinstance(value, list):
        return value[:item_limit]
    if not isinstance(value, dict):
        return value
    items = value.get("items", [])
    projected: dict[str, Any] = {}
    if isinstance(items, list):
        projected["items"] = items[:item_limit]
        omitted = value.get("omitted_count")
        if isinstance(omitted, int):
            projected["omitted_count"] = omitted + max(0, len(items) - item_limit)
        elif len(items) > item_limit:
            projected["omitted_count"] = len(items) - item_limit
    for key in ("full_set_artifact_ref", "artifact_ref"):
        ref = value.get(key)
        if isinstance(ref, dict):
            projected[key] = ref
    bulk_summary = value.get("semantic_bulk_operation_summary")
    if isinstance(bulk_summary, dict):
        projected["semantic_bulk_operation_summary"] = _project_bulk_operation_summary(
            bulk_summary
        )
    return projected or value


def _project_bulk_operation_summary(summary: dict[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for key in (
        "kind",
        "operation",
        "confidence",
        "path_count",
        "common_directory",
        "file_extension",
        "fallback",
    ):
        if key in summary:
            projected[key] = summary[key]
    sample_paths = summary.get("sample_paths")
    if isinstance(sample_paths, list):
        projected["sample_paths"] = [
            item for item in sample_paths[:MAX_BULK_SUMMARY_SAMPLES] if isinstance(item, str)
        ]
    sampled_deviations = summary.get("sampled_deviations")
    if isinstance(sampled_deviations, list):
        projected["sampled_deviations"] = [
            _brief_text(item, limit=MAX_EXECUTION_DEVIATION_CHARS)
            for item in sampled_deviations[:MAX_BULK_SUMMARY_SAMPLES]
            if isinstance(item, str)
        ]
    instructions = summary.get("live_tree_verification")
    if isinstance(instructions, list):
        projected["live_tree_verification"] = [
            _brief_text(item, limit=MAX_EXECUTION_COMMAND_CHARS)
            for item in instructions[:MAX_BULK_SUMMARY_INSTRUCTIONS]
            if isinstance(item, str)
        ]
    return projected


def _project_task(task: dict[str, Any]) -> dict[str, Any]:
    """Project a single task object for prompt rendering.

    Keeps structural fields intact; truncates verbose prose fields
    (*executor_notes*, *complexity_justification*) to budget.

    Handles both finalize-style tasks (``id``) and execution-style
    task updates (``task_id``).
    """
    projected: dict[str, Any] = {}
    # Structural / routing fields — always keep.
    # ``id`` is the canonical key for finalize tasks, ``task_id`` for
    # execution task_updates.  Preserve whichever is present.
    for key in (
        "id",
        "task_id",
        "depends_on",
        "status",
        "kind",
        "complexity",
        "reviewer_verdict",
        "stance",
        "stop_signal",
    ):
        if key in task:
            projected[key] = task[key]

    # Description — keep but bound
    if "description" in task:
        projected["description"] = _brief_text(
            task["description"], limit=MAX_DESCRIPTION_CHARS
        )

    # Complexity justification — keep but bound
    if "complexity_justification" in task:
        projected["complexity_justification"] = _brief_text(
            task["complexity_justification"],
            limit=MAX_COMPLEXITY_JUSTIFICATION_CHARS,
        )

    # Executor notes — keep but bound (the main bloat source)
    if "executor_notes" in task:
        projected["executor_notes"] = _brief_text(
            task["executor_notes"], limit=MAX_EXECUTOR_NOTES_CHARS
        )

    # Evidence — keep compact
    for key in ("files_changed", "commands_run", "evidence_files"):
        if key in task:
            val = task[key]
            if isinstance(val, list):
                if key == "commands_run":
                    projected[key] = val[:20]  # cap at 20 entries
                else:
                    projected[key] = _project_path_list(val)
            elif key != "commands_run" and isinstance(val, dict):
                projected[key] = _project_path_list(val)
            else:
                projected[key] = val

    # Auto-attributed files — cap list size
    if "auto_attributed_files" in task:
        val = task["auto_attributed_files"]
        if isinstance(val, list):
            projected["auto_attributed_files"] = val[:20]

    # Preserve any remaining known fields at their original size
    # (they are typically short scalars)
    for key in ("baseline_test_failures", "baseline_test_command"):
        if key in task:
            projected[key] = task[key]

    return projected


def _project_sense_check(
    sense_check: dict[str, Any],
) -> dict[str, Any]:
    """Project a single sense-check object for prompt rendering."""
    projected: dict[str, Any] = {}
    for key in ("id", "task_id", "verdict"):
        if key in sense_check:
            projected[key] = sense_check[key]
    if "question" in sense_check:
        projected["question"] = _brief_text(
            sense_check["question"], limit=MAX_SENSE_CHECK_QUESTION_CHARS
        )
    if "executor_note" in sense_check:
        projected["executor_note"] = _brief_text(
            sense_check["executor_note"], limit=MAX_EXECUTOR_NOTES_CHARS
        )
    return projected


def _receipt_identifier(value: Any) -> tuple[str, str | None]:
    """Bound an identifier while preserving a stable lookup digest."""
    text = value if isinstance(value, str) else str(value) if value is not None else ""
    if len(text) <= MAX_COMPLETED_TASK_RECEIPT_ID_CHARS:
        return text, None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    suffix = f"...sha256:{digest[:16]}"
    return text[: MAX_COMPLETED_TASK_RECEIPT_ID_CHARS - len(suffix)] + suffix, digest


def _receipt_list(
    value: Any,
    *,
    item_limit: int,
    text_limit: int,
) -> tuple[list[str], int]:
    """Return bounded string evidence plus an explicit omitted count."""
    if isinstance(value, dict):
        raw_items = value.get("items", [])
        inherited_omitted = value.get("omitted_count", 0)
        inherited_omitted = inherited_omitted if isinstance(inherited_omitted, int) else 0
    else:
        raw_items = value
        inherited_omitted = 0
    if not isinstance(raw_items, list):
        return [], inherited_omitted
    strings = [item for item in raw_items if isinstance(item, str)]
    return (
        [_brief_text(item, limit=text_limit) for item in strings[:item_limit]],
        inherited_omitted + max(0, len(strings) - item_limit),
    )


def _completed_task_receipt(task: dict[str, Any], *, direct: bool) -> dict[str, Any]:
    task_id, task_id_digest = _receipt_identifier(task.get("id", ""))
    receipt: dict[str, Any] = {
        "task_id": task_id,
        "dependency_scope": "direct" if direct else "transitive",
        "status": _brief_text(task.get("status", "completed"), limit=40),
        "description": _brief_text(task.get("description", ""), limit=240),
        "outcome": _brief_text(task.get("executor_notes", ""), limit=500),
    }
    if task_id_digest:
        receipt["task_id_sha256"] = task_id_digest

    evidence: dict[str, Any] = {}
    for field, item_limit, text_limit in (
        ("files_changed", MAX_COMPLETED_TASK_RECEIPT_FILES, 180),
        ("commands_run", MAX_COMPLETED_TASK_RECEIPT_COMMANDS, 240),
        ("evidence_files", MAX_COMPLETED_TASK_RECEIPT_EVIDENCE_FILES, 180),
    ):
        items, omitted = _receipt_list(
            task.get(field, []),
            item_limit=item_limit,
            text_limit=text_limit,
        )
        if items:
            evidence[field] = items
        if omitted:
            evidence[f"{field}_omitted_count"] = omitted
    if evidence:
        receipt["evidence"] = evidence
    return receipt


def project_completed_task_receipts(
    finalize_data: dict[str, Any],
    *,
    batch_task_ids: list[str],
    completed_task_ids: set[str] | None,
    source_artifact_ref: str = "finalize.json",
) -> dict[str, Any]:
    """Build bounded, dependency-scoped receipts for an execute prompt.

    The complete task ledger remains unchanged in ``finalize.json``. Prompts
    receive only completed tasks in the current batch's dependency closure,
    ordered with direct dependencies first. Both receipt count and serialized
    character size are capped. If a dependency receipt cannot fit, the payload
    says so explicitly and points back to the authoritative artifact; executors
    must block rather than guess when that artifact is unavailable.
    """
    raw_tasks = finalize_data.get("tasks", [])
    tasks = [task for task in raw_tasks if isinstance(task, dict)] if isinstance(raw_tasks, list) else []
    task_by_id = {
        task["id"]: task
        for task in tasks
        if isinstance(task.get("id"), str) and task.get("id")
    }
    task_order = {task_id: index for index, task_id in enumerate(task_by_id)}
    completed = {
        task_id
        for task_id in (completed_task_ids or set())
        if isinstance(task_id, str) and task_id not in set(batch_task_ids)
    }

    direct_ids: set[str] = set()
    dependency_ids: set[str] = set()
    frontier: list[str] = []
    for batch_id in batch_task_ids:
        task = task_by_id.get(batch_id, {})
        depends_on = task.get("depends_on", [])
        if not isinstance(depends_on, list):
            continue
        for dependency_id in depends_on:
            if isinstance(dependency_id, str) and dependency_id in completed:
                direct_ids.add(dependency_id)
                frontier.append(dependency_id)

    while frontier:
        dependency_id = frontier.pop(0)
        if dependency_id in dependency_ids:
            continue
        dependency_ids.add(dependency_id)
        task = task_by_id.get(dependency_id, {})
        depends_on = task.get("depends_on", [])
        if not isinstance(depends_on, list):
            continue
        for parent_id in depends_on:
            if (
                isinstance(parent_id, str)
                and parent_id in completed
                and parent_id not in dependency_ids
            ):
                frontier.append(parent_id)

    ordered_dependency_ids = sorted(
        (task_id for task_id in dependency_ids if task_id in task_by_id),
        key=lambda task_id: (
            0 if task_id in direct_ids else 1,
            task_order.get(task_id, len(task_order)),
            task_id,
        ),
    )
    candidate_receipts = [
        _completed_task_receipt(
            task_by_id[task_id],
            direct=task_id in direct_ids,
        )
        for task_id in ordered_dependency_ids
    ]

    payload: dict[str, Any] = {
        "schema": "megaplan.completed_task_receipts.v1",
        "source_artifact": _brief_text(source_artifact_ref, limit=300),
        "selection": "completed dependency closure; direct dependencies first",
        "completed_task_count": len(completed),
        "dependency_task_count": len(candidate_receipts),
        "unrelated_completed_task_count": len(completed - dependency_ids),
        "receipts": [],
        "omitted_dependency_receipt_count": len(candidate_receipts),
    }

    for receipt in candidate_receipts[:MAX_COMPLETED_TASK_RECEIPTS]:
        proposed = dict(payload)
        proposed_receipts = [*payload["receipts"], receipt]
        proposed["receipts"] = proposed_receipts
        proposed["omitted_dependency_receipt_count"] = len(candidate_receipts) - len(proposed_receipts)
        if len(json.dumps(proposed, sort_keys=True, ensure_ascii=False)) > MAX_COMPLETED_TASK_RECEIPT_CONTEXT_CHARS:
            break
        payload = proposed

    def refresh_overflow() -> None:
        omitted_ids = ordered_dependency_ids[len(payload["receipts"]):]
        payload["omitted_dependency_receipt_count"] = len(omitted_ids)
        if not omitted_ids:
            payload.pop("overflow", None)
            return
        digest_input = "\0".join(omitted_ids).encode("utf-8")
        payload["overflow"] = {
            "task_id_set_sha256": hashlib.sha256(digest_input).hexdigest(),
            "task_id_sample": [
                _receipt_identifier(task_id)[0] for task_id in omitted_ids[:5]
            ],
            "required_action": (
                "Inspect source_artifact for omitted dependency evidence; "
                "if it is unavailable, block instead of guessing."
            ),
        }

    refresh_overflow()
    while (
        payload["receipts"]
        and len(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        > MAX_COMPLETED_TASK_RECEIPT_CONTEXT_CHARS
    ):
        payload["receipts"].pop()
        refresh_overflow()

    return payload


# ---------------------------------------------------------------------------
# Public projection helpers
# ---------------------------------------------------------------------------


def project_execute_context(
    finalize_data: dict[str, Any],
    *,
    capabilities: PromptProjectionCapabilities | None = None,
) -> dict[str, Any]:
    """Project ``finalize.json``-shaped data for execute-prompt rendering.

    Returns a shallow copy with projected *tasks* and *sense_checks*.
    Long executor notes and verbose justifications are truncated; active
    task descriptions, success criteria, sense-check questions, baseline
    failures, and user actions are preserved.

    *capabilities* gates artifact-reference fields (e.g. checkpoint paths).
    When ``None`` (the default), full capabilities are assumed for backward
    compatibility.
    """
    caps = capabilities if capabilities is not None else PromptProjectionCapabilities.full()
    projected: dict[str, Any] = {}

    # Top-level scalar / list fields — copy as-is
    for key in (
        "watch_items",
        "user_actions",
        "baseline_test_failures",
        "baseline_test_command",
        "success_criteria",
    ):
        if key in finalize_data:
            projected[key] = finalize_data[key]

    # meta_commentary — keep but bound
    if "meta_commentary" in finalize_data:
        projected["meta_commentary"] = _brief_text(
            finalize_data["meta_commentary"], limit=MAX_META_COMMENTARY_CHARS
        )

    # Tasks — project each
    raw_tasks = finalize_data.get("tasks", [])
    if isinstance(raw_tasks, list):
        projected["tasks"] = [_project_task(t) if isinstance(t, dict) else t for t in raw_tasks]

    # Sense checks — project each
    raw_checks = finalize_data.get("sense_checks", [])
    if isinstance(raw_checks, list):
        projected["sense_checks"] = [
            _project_sense_check(sc) if isinstance(sc, dict) else sc
            for sc in raw_checks
        ]

    return projected


def project_review_context(
    finalize_data: dict[str, Any],
    execution_data: dict[str, Any] | None = None,
    *,
    capabilities: PromptProjectionCapabilities | None = None,
) -> dict[str, Any]:
    """Project execution context for review-prompt rendering.

    Returns a dict with projected *tasks*, *sense_checks*, and compact
    execution evidence.  Long executor notes are truncated; structural
    fields needed for review verdicts are preserved.

    *execution_data* is optional — when provided its *task_updates* and
    *sense_check_acknowledgments* are merged into the projection.
    """
    caps = capabilities if capabilities is not None else PromptProjectionCapabilities.full()
    projected: dict[str, Any] = {}

    # Tasks — each projected
    raw_tasks = finalize_data.get("tasks", [])
    if isinstance(raw_tasks, list):
        projected["tasks"] = [
            _project_task(t) if isinstance(t, dict) else t for t in raw_tasks
        ]

    # Sense checks — each projected
    raw_checks = finalize_data.get("sense_checks", [])
    if isinstance(raw_checks, list):
        projected["sense_checks"] = [
            _project_sense_check(sc) if isinstance(sc, dict) else sc
            for sc in raw_checks
        ]

    # Merge execution evidence when available
    if isinstance(execution_data, dict):
        # task_updates carry per-task evidence
        task_updates = execution_data.get("task_updates", [])
        if isinstance(task_updates, list):
            projected["task_updates"] = [
                _project_task(tu) if isinstance(tu, dict) else tu
                for tu in task_updates
            ]

        # sense_check_acknowledgments
        sc_acks = execution_data.get("sense_check_acknowledgments", [])
        if isinstance(sc_acks, list):
            projected["sense_check_acknowledgments"] = [
                {
                    "sense_check_id": ack.get("sense_check_id", ""),
                    "executor_note": _brief_text(
                        ack.get("executor_note", ""), limit=MAX_EXECUTOR_NOTES_CHARS
                    ),
                }
                if isinstance(ack, dict)
                else ack
                for ack in sc_acks
            ]

        if "output" in execution_data:
            projected["output"] = _brief_text(
                execution_data["output"], limit=MAX_EXECUTION_OUTPUT_CHARS
            )

        deviations = execution_data.get("deviations")
        if isinstance(deviations, list):
            projected["deviations"] = _project_list(
                deviations,
                item_limit=MAX_EXECUTION_DEVIATIONS,
                text_limit=MAX_EXECUTION_DEVIATION_CHARS,
            )

        files_changed = execution_data.get("files_changed")
        if isinstance(files_changed, (list, dict)):
            projected["files_changed"] = _project_path_list(files_changed)

        commands_run = execution_data.get("commands_run")
        if isinstance(commands_run, list):
            projected["commands_run"] = _project_list(
                commands_run,
                item_limit=20,
                text_limit=MAX_EXECUTION_COMMAND_CHARS,
            )

    # Top-level finalize fields useful to review
    for key in ("watch_items", "user_actions", "meta_commentary"):
        if key in finalize_data:
            val = finalize_data[key]
            if key == "meta_commentary":
                projected[key] = _brief_text(val, limit=MAX_META_COMMENTARY_CHARS)
            else:
                projected[key] = val

    return projected


def project_rework_context(
    review_data: dict[str, Any],
    *,
    capabilities: PromptProjectionCapabilities | None = None,
) -> dict[str, Any]:
    """Project review findings for rework-prompt rendering.

    Returns a dict focused on *rework_items*, *issues*, and *criteria*
    that failed.  Evidence file paths are included only when capabilities
    allow the worker to read them.
    """
    caps = capabilities if capabilities is not None else PromptProjectionCapabilities.full()
    projected: dict[str, Any] = {}

    # Rework items — keep compact with gated evidence files
    raw_items = review_data.get("rework_items", [])
    if isinstance(raw_items, list):
        projected_rework: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                projected_rework.append(item)
                continue
            pi: dict[str, Any] = {}
            for key in ("task_id", "issue", "expected", "actual"):
                if key in item:
                    pi[key] = item[key]
            # Gate evidence_file on capabilities
            if "evidence_file" in item:
                ef = item["evidence_file"]
                if caps.artifact_reference_allowed(path_hint=str(ef)):
                    pi["evidence_file"] = ef
                else:
                    pi["evidence_file"] = "<gated: worker cannot read this path>"
            projected_rework.append(pi)
        projected["rework_items"] = projected_rework

    # Issues — one-line summaries
    issues = review_data.get("issues", [])
    if isinstance(issues, list):
        projected["issues"] = issues

    # Failed criteria only (keep review focused on what needs fixing)
    raw_criteria = review_data.get("criteria", [])
    if isinstance(raw_criteria, list):
        projected["criteria"] = [
            c
            for c in raw_criteria
            if isinstance(c, dict) and c.get("pass") in (False, "fail")
        ]

    # Summary
    if "summary" in review_data:
        projected["summary"] = _brief_text(
            review_data["summary"], limit=MAX_EXECUTOR_NOTES_CHARS
        )

    return projected


def project_execution_audit_context(
    audit_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Project ``execution_audit.json`` for review-prompt rendering."""
    if not isinstance(audit_data, dict):
        return {}

    projected: dict[str, Any] = {}
    for key in ("skipped", "reason"):
        if key in audit_data:
            projected[key] = audit_data[key]

    findings = audit_data.get("findings", [])
    if isinstance(findings, list):
        projected["findings"] = [
            _brief_text(item, limit=MAX_EXECUTOR_NOTES_CHARS)
            if isinstance(item, str)
            else item
            for item in findings[:MAX_AUDIT_FINDINGS]
        ]

    for key in ("files_in_diff", "files_claimed", "auto_attribution"):
        value = audit_data.get(key)
        if isinstance(value, list):
            projected[key] = value[:MAX_AUDIT_FILES]

    return projected


# ---------------------------------------------------------------------------
# Phase-aware prompt size guard
# ---------------------------------------------------------------------------

# Default per-phase prompt size limits (character count).
# Calibrated to the context windows of the models that actually run each phase,
# NOT to an arbitrary floor. The reasoning phases (plan/critique/gate/revise/
# review/finalize) run on premium models (Claude ~200K tokens ≈ 800K chars) or
# DeepSeek-V4 (registered ~1M-token window) — a 150K-char (~37K-token) cap was
# far too conservative and hard-failed legitimate large milestones (the relocation
# overflows). These are set generously enough to admit a large-but-valid prompt
# while still catching a genuine runaway (>~600K chars / ~150K tokens, under
# Claude's window with response headroom). `execute` stays conservative because a
# trivial (c1) task can route to DeepSeek-Flash with a smaller window. Callers may
# still override via MEGAPLAN_PROMPT_SIZE_LIMIT[_<PHASE>].
_DEFAULT_PHASE_LIMITS: dict[str, int] = {
    "plan": 400_000,
    "prep": 400_000,
    "prep-triage": 400_000,
    "prep-distill": 400_000,
    "critique": 600_000,
    "critique_evaluator": 600_000,
    "revise": 600_000,
    "gate": 600_000,
    "finalize": 400_000,
    "execute": 200_000,
    "execute-batch": 200_000,
    "review": 600_000,
    "review-doc": 600_000,
    "review-joke": 600_000,
    "feedback": 200_000,
    "rework": 600_000,
}

# Sentinel string used when no phase-specific limit is configured.
_PHASE_UNKNOWN_LIMIT = 200_000

# Environment variable keys
_ENV_GLOBAL_LIMIT = "MEGAPLAN_PROMPT_SIZE_LIMIT"
_ENV_PHASE_PREFIX = "MEGAPLAN_PROMPT_SIZE_LIMIT_"


def _resolve_prompt_size_limit(phase: str) -> int:
    """Resolve the prompt size limit for *phase*.

    Resolution order (highest priority first):
    1. ``MEGAPLAN_PROMPT_SIZE_LIMIT_<PHASE>`` (phase-specific override)
    2. ``MEGAPLAN_PROMPT_SIZE_LIMIT`` (global override)
    3. Phase-aware default from ``_DEFAULT_PHASE_LIMITS``
    4. Fallback of ``_PHASE_UNKNOWN_LIMIT``
    """
    # 1. Phase-specific env override (uppercase, hyphens → underscores)
    phase_env_key = _ENV_PHASE_PREFIX + phase.upper().replace("-", "_")
    phase_env_val = os.environ.get(phase_env_key)
    if phase_env_val is not None:
        try:
            return int(phase_env_val)
        except ValueError:
            pass  # fall through

    # 2. Global env override
    global_env_val = os.environ.get(_ENV_GLOBAL_LIMIT)
    if global_env_val is not None:
        try:
            return int(global_env_val)
        except ValueError:
            pass  # fall through

    # 3. Phase-aware default
    if phase in _DEFAULT_PHASE_LIMITS:
        return _DEFAULT_PHASE_LIMITS[phase]

    # 4. Fallback
    return _PHASE_UNKNOWN_LIMIT


def is_prompt_oversized(
    prompt_text: str,
    *,
    max_chars: int = 200_000,
) -> bool:
    """Return ``True`` when *prompt_text* exceeds *max_chars*.

    This is a fast character-count guard; callers should use this before
    dispatching to a model API.
    """
    return len(prompt_text) > max_chars


def oversized_prompt_error(
    step: str,
    prompt_size: int,
    max_chars: int,
    *,
    extra_guidance: str = "",
) -> str:
    """Build an actionable error message for an oversized prompt."""
    base = textwrap.dedent(
        f"""\
        LLM_CALL_ERROR: {step} prompt exceeds size limit.
        Prompt size: {prompt_size:,} characters (limit: {max_chars:,}).
        """
    )
    if extra_guidance:
        base += f"\n{extra_guidance}"
    return base


def check_prompt_size(
    prompt_text: str,
    *,
    phase: str,
) -> None:
    """Raise ``CliError`` when *prompt_text* exceeds the size limit for *phase*.

    The limit is resolved via :func:`_resolve_prompt_size_limit`, which
    respects per-phase defaults and environment variable overrides
    (``MEGAPLAN_PROMPT_SIZE_LIMIT`` / ``MEGAPLAN_PROMPT_SIZE_LIMIT_<PHASE>``).

    Raises:
        CliError: With code ``"prompt_oversized"`` and an actionable
            phase-aware message when the prompt exceeds the limit.
    """
    # Import here to avoid circular import at module level.
    from arnold_pipelines.megaplan.types import CliError

    max_chars = _resolve_prompt_size_limit(phase)
    prompt_size = len(prompt_text)

    if prompt_size <= max_chars:
        return

    # Build phase-specific guidance
    phase_guidance: dict[str, str] = {
        "execute": "Consider reducing batch size or splitting tasks into smaller batches.",
        "execute-batch": "Consider reducing batch size or splitting tasks into smaller batches.",
        "review": "Consider reviewing fewer tasks per prompt or narrowing criteria scope.",
        "review-doc": "Consider reducing the document or plan text size.",
        "review-joke": "Consider reducing the scene canvas or output scene size.",
        "finalize": "Consider reducing task count or truncating long executor notes in the plan.",
    }
    extra_guidance = phase_guidance.get(phase, "")

    message = oversized_prompt_error(
        step=phase,
        prompt_size=prompt_size,
        max_chars=max_chars,
        extra_guidance=extra_guidance,
    )

    raise CliError(
        code="prompt_oversized",
        message=message,
        extra={
            "phase": phase,
            "prompt_size": prompt_size,
            "max_chars": max_chars,
        },
    )


# ---------------------------------------------------------------------------
# Rebuild metadata & digest helpers (pure, no side effects)
# ---------------------------------------------------------------------------

REBUILD_METADATA_SCHEMA_VERSION = 1


def compute_prompt_projection_digest(projection: Mapping[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest of a prompt projection view.

    The digest is computed over the canonical (stable, sorted-key,
    no-whitespace) JSON representation of *projection*, making it
    byte-for-byte comparable across rebuilds.

    Parameters
    ----------
    projection:
        A projection dict produced by any prompt projection function
        (e.g. ``project_execute_context``, ``project_review_context``).

    Returns
    -------
    str
        ``"sha256:<hex>"`` digest string.
    """
    canonical = _projection_canonical_dumps(dict(projection))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def capture_prompt_source_cursor(source_path: str | Path) -> ProjectionCursor:
    """Capture a :class:`ProjectionCursor` for a prompt source file.

    Computes a cursor from the file at *source_path* that captures its
    absolute path, record count, and content digest.

    This function is **read-only** — it never mutates the source file.

    Parameters
    ----------
    source_path:
        Path to the source file (e.g. ``finalize.json`` or an
        execution output JSON file).

    Returns
    -------
    ProjectionCursor
        An immutable cursor capturing the source file state.
    """
    from arnold_pipelines.megaplan._core.io import _projection_cursor_from_path

    return _projection_cursor_from_path(Path(source_path))


def prompt_rebuild_metadata(
    source_path: str | Path,
    *,
    projection_digest: str = "",
    computed_at: str | None = None,
) -> dict[str, Any]:
    """Produce rebuild metadata (cursor, freshness, lag, digest) for a prompt projection.

    This is a **pure function** — it never mutates source evidence or
    writes to the filesystem.  The caller is responsible for attaching
    the returned metadata to a projection view.

    Parameters
    ----------
    source_path:
        Path to the source file driving the prompt projection.
    projection_digest:
        Pre-computed digest of the projection view. When empty, the
        returned metadata will not include a digest.
    computed_at:
        ISO-8601 timestamp for the rebuild. When ``None``, ``now_utc()``
        is used.

    Returns
    -------
    dict
        A metadata dict with keys ``source_cursor`` (``ProjectionCursor``
        as dict), ``rebuilt_at``, ``freshness_seconds``, ``lag_seconds``,
        ``projection_digest`` (when non-empty), and
        ``rebuild_schema_version``.
    """
    from datetime import datetime

    cursor = capture_prompt_source_cursor(source_path)
    rebuilt_at = computed_at or now_utc()

    freshness_seconds = 0.0

    try:
        source_path_obj = Path(source_path)
        if source_path_obj.exists():
            source_mtime = source_path_obj.stat().st_mtime
            rebuild_epoch = datetime.fromisoformat(rebuilt_at).timestamp()
            lag_seconds = max(0.0, rebuild_epoch - source_mtime)
        else:
            lag_seconds = 0.0
    except (OSError, ValueError):
        lag_seconds = 0.0

    metadata: dict[str, Any] = {
        "rebuild_schema_version": REBUILD_METADATA_SCHEMA_VERSION,
        "source_cursor": cursor.to_dict(),
        "rebuilt_at": rebuilt_at,
        "freshness_seconds": freshness_seconds,
        "lag_seconds": lag_seconds,
    }
    if projection_digest:
        metadata["projection_digest"] = projection_digest

    return metadata
