"""Admission policy for review-originated work against current task authority."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from arnold_pipelines.megaplan.orchestration.external_gates import (
    is_external_human_rework_item,
)


PASS_STATUSES = frozenset({"pass", "passed", "success", "succeeded", "green", "0"})
FAIL_STATUSES = frozenset({"fail", "failed", "failure", "red", "1", "nonzero"})
ACCEPTED_DEBT_SOURCES = frozenset(
    {"accepted_debt", "accepted_tradeoff", "accepted_non_action"}
)


def _normalized_check_status(value: object) -> str:
    """Normalize a check-status string for set/prefix matching.

    Mirrors ``handlers/review.py:_failed_check_status`` so that a status
    carrying an evidence parenthetical (e.g. ``failed (AssertionError: ...)``)
    is recognized as the same outcome as the bare token ``failed`` instead of
    being mislabeled ``accepted_task_reopen_unproven``.
    """
    return (
        str(value or "")
        .strip()
        .casefold()
        .replace("-", "_")
        .replace(" ", "_")
    )


def _is_failed_check_status(value: object) -> bool:
    normalized = _normalized_check_status(value)
    return normalized in FAIL_STATUSES or any(
        normalized.startswith(f"{status}_") for status in FAIL_STATUSES
    )


def _is_passed_check_status(value: object) -> bool:
    normalized = _normalized_check_status(value)
    return normalized in PASS_STATUSES or any(
        normalized.startswith(f"{status}_") for status in PASS_STATUSES
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _strings(value: object) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [item for item in value if isinstance(item, str) and item]
    return []


def target_task_ids(item: Mapping[str, Any]) -> tuple[list[str], str]:
    target = item.get("target")
    if isinstance(target, Mapping):
        kind = str(target.get("kind") or "task").strip().lower()
        ids = []
        if kind == "task":
            ids.extend(_strings(target.get("task_id") or target.get("id")))
        ids.extend(_strings(target.get("task_ids")))
        return list(dict.fromkeys(ids)), kind
    task_id = item.get("task_id")
    return (_strings(task_id), "task")


@dataclass(frozen=True)
class ReworkAdmission:
    authority_digest: str
    requested_task_ids: tuple[str, ...]
    runnable_task_ids: tuple[str, ...]
    suppressed_task_ids: tuple[str, ...]
    validation_jobs: tuple[Mapping[str, Any], ...]
    external_gates: tuple[Mapping[str, Any], ...] = ()
    blockers: tuple[Mapping[str, Any], ...] = ()
    dispositions: tuple[Mapping[str, Any], ...] = ()

    @property
    def admitted(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "megaplan.review_rework_admission",
            "schema_version": 1,
            "authority_digest": self.authority_digest,
            "requested_task_ids": list(self.requested_task_ids),
            "runnable_task_ids": list(self.runnable_task_ids),
            "suppressed_task_ids": list(self.suppressed_task_ids),
            "validation_jobs": [dict(row) for row in self.validation_jobs],
            "external_gates": [dict(row) for row in self.external_gates],
            "blockers": [dict(row) for row in self.blockers],
            "dispositions": [dict(row) for row in self.dispositions],
            "admitted": self.admitted,
        }


def reconcile_review_rework(
    review_data: Mapping[str, Any],
    *,
    known_task_ids: set[str],
    accepted_task_ids: set[str],
    authority_revision: str | None,
    review_revision: str | None,
) -> ReworkAdmission:
    """Return one total disposition per review item before implementation dispatch.

    An accepted task is never replayed merely because its old ID appears in
    ``review.json``.  It can reopen only with a deterministic failing check.
    Bulk/manifest/global checks become one validation job.  Ambiguous rows fail
    closed instead of silently widening implementation authority.
    """

    authority_payload = {
        "accepted_task_ids": sorted(accepted_task_ids),
        "authority_revision": authority_revision,
    }
    authority_digest = _digest(authority_payload)
    requested: list[str] = []
    runnable: list[str] = []
    suppressed: list[str] = []
    jobs: list[Mapping[str, Any]] = []
    external_gates: list[Mapping[str, Any]] = []
    blockers: list[Mapping[str, Any]] = []
    dispositions: list[Mapping[str, Any]] = []

    if (
        review_revision
        and authority_revision
        and review_revision != authority_revision
    ):
        blockers.append(
            {
                "code": "review_evidence_window_stale",
                "review_revision": review_revision,
                "authority_revision": authority_revision,
            }
        )

    for index, raw in enumerate(review_data.get("rework_items", []) or []):
        if not isinstance(raw, Mapping):
            blockers.append({"code": "rework_item_malformed", "item_index": index})
            continue
        task_ids, kind = target_task_ids(raw)
        requested.extend(task_ids)
        missing = [task_id for task_id in task_ids if task_id not in known_task_ids]
        check = raw.get("deterministic_check")
        check = check if isinstance(check, Mapping) else None
        command = str(check.get("command") or "").strip() if check else ""
        post_status = str(check.get("post_status") or "").strip().lower() if check else ""
        # Taskless manifest/bulk/global items carrying a deterministic check are
        # verifiable as validation jobs (e.g. a dangling artifact anchor whose
        # file now exists). Only items with NO derivable target AND no check are
        # structurally unroutable -> rework_target_unknown.
        if (not task_ids or missing) and not (kind in {"bulk", "manifest", "global"} and command):
            blockers.append(
                {
                    "code": "rework_target_unknown",
                    "item_index": index,
                    "task_ids": task_ids,
                    "missing_task_ids": missing,
                }
            )
            continue
        accepted_ids = [task_id for task_id in task_ids if task_id in accepted_task_ids]
        open_ids = [task_id for task_id in task_ids if task_id not in accepted_task_ids]

        if kind in {"bulk", "manifest", "global"} and command:
            job_id = str(
                (raw.get("target") or {}).get("id")
                if isinstance(raw.get("target"), Mapping)
                else ""
            ) or f"review-validation-{index + 1}"
            # Human-gate items (NSA-1 / add_human_halt / north-star-human-halt) are
            # EXTERNAL gates, not bounded validation jobs: their deterministic check
            # fails by design until a human records an acceptance decision, and they
            # must not pre-empt runnable actionable rework or open the quality circuit.
            human_gate = is_external_human_rework_item(raw)
            if human_gate:
                external_gates.append(
                    {
                        "id": job_id,
                        "command": command,
                        "task_ids": task_ids,
                        "source_item_index": index,
                        "authority_digest": authority_digest,
                        "agent_actionable": False,
                        "reason": "requires an explicit human acceptance decision",
                    }
                )
                suppressed.extend(accepted_ids)
                dispositions.append(
                    {
                        "item_index": index,
                        "disposition": "external_gate_deferred",
                        "task_ids": task_ids,
                        "external_gate_id": job_id,
                    }
                )
                continue
            jobs.append(
                {
                    "id": job_id,
                    "command": command,
                    "task_ids": task_ids,
                    "source_item_index": index,
                    "authority_digest": authority_digest,
                }
            )
            suppressed.extend(accepted_ids)
            dispositions.append(
                {
                    "item_index": index,
                    "disposition": "bounded_validation_job",
                    "task_ids": task_ids,
                    "validation_job_id": job_id,
                }
            )
            continue

        if open_ids:
            runnable.extend(open_ids)
            dispositions.append(
                {
                    "item_index": index,
                    "disposition": "current_generation",
                    "task_ids": open_ids,
                }
            )

        if not accepted_ids:
            continue
        source = str(raw.get("source") or "").strip().lower()
        if source in ACCEPTED_DEBT_SOURCES:
            suppressed.extend(accepted_ids)
            dispositions.append(
                {
                    "item_index": index,
                    "disposition": "accepted_non_action_preserved",
                    "task_ids": accepted_ids,
                }
            )
        elif _is_failed_check_status(post_status):
            runnable.extend(accepted_ids)
            dispositions.append(
                {
                    "item_index": index,
                    "disposition": "new_regression_generation",
                    "task_ids": accepted_ids,
                    "deterministic_check": command,
                }
            )
        elif _is_passed_check_status(post_status):
            suppressed.extend(accepted_ids)
            dispositions.append(
                {
                    "item_index": index,
                    "disposition": "current_authority_satisfies_obligation",
                    "task_ids": accepted_ids,
                    "deterministic_check": command,
                }
            )
        else:
            blockers.append(
                {
                    "code": "accepted_task_reopen_unproven",
                    "item_index": index,
                    "task_ids": accepted_ids,
                    "post_status": post_status or None,
                }
            )

    return ReworkAdmission(
        authority_digest=authority_digest,
        requested_task_ids=tuple(dict.fromkeys(requested)),
        runnable_task_ids=tuple(dict.fromkeys(runnable)),
        suppressed_task_ids=tuple(dict.fromkeys(suppressed)),
        validation_jobs=tuple(jobs),
        external_gates=tuple(external_gates),
        blockers=tuple(blockers),
        dispositions=tuple(dispositions),
    )


__all__ = [
    "ReworkAdmission",
    "reconcile_review_rework",
    "target_task_ids",
]
