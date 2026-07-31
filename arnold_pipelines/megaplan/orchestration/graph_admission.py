"""Candidate-graph admission journal for finalization.

Candidates are content-addressed and validated off to the side.  A rejected
candidate can never replace ``finalize.json`` or ``task_feasibility.json``.
The existing plan lock is the publication CAS: exactly one admitted candidate
is published by the finalizer holding that lock.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import atomic_write_json, now_utc


SCHEMA = "megaplan.candidate_graph_admission"
SCHEMA_VERSION = 1
CIRCUIT_THRESHOLD = 2


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def candidate_graph_record(
    payload: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    graph = {
        "task_contract_version": payload.get("task_contract_version"),
        "tasks": payload.get("tasks", []),
        "validation_jobs": payload.get("validation_jobs", []),
        "sense_checks": payload.get("sense_checks", []),
    }
    diagnostic_signature = [
        {
            "code": row.get("code"),
            "task_ids": row.get("task_ids"),
            "path": row.get("path"),
        }
        for row in report.get("diagnostics", [])
        if isinstance(row, Mapping)
    ]
    fingerprint = _digest(
        {
            "task_contract_hash": report.get("task_contract_hash"),
            "diagnostics": diagnostic_signature,
        }
    )
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "candidate_id": f"candidate:{_digest(graph)}",
        "candidate_graph_hash": _digest(graph),
        "task_contract_hash": report.get("task_contract_hash"),
        "admitted": report.get("admitted") is True,
        "failure_fingerprint": None if report.get("admitted") is True else fingerprint,
        "diagnostics": list(report.get("diagnostics", [])),
        "observed_at": now_utc(),
    }


def record_rejected_candidate(
    plan_dir: Path,
    state: dict[str, Any],
    payload: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    record = candidate_graph_record(payload, report)
    candidate_dir = plan_dir / "finalize_candidates"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        candidate_dir / f"{record['candidate_id'].split(':', 1)[1]}.json",
        {**record, "report": dict(report)},
    )

    meta = state.setdefault("meta", {})
    prior = meta.get("planner_repair")
    same = (
        isinstance(prior, Mapping)
        and prior.get("failure_fingerprint") == record["failure_fingerprint"]
    )
    occurrences = int(prior.get("occurrences", 0)) + 1 if same else 1
    current_finalize = plan_dir / "finalize.json"
    current_feasibility = plan_dir / "task_feasibility.json"
    repair = {
        "schema": "megaplan.planner_repair",
        "schema_version": 1,
        "candidate_id": record["candidate_id"],
        "failure_fingerprint": record["failure_fingerprint"],
        "occurrences": occurrences,
        "circuit_open": occurrences >= CIRCUIT_THRESHOLD,
        "prior_state": state.get("current_state"),
        "prior_admitted_finalize_sha256": (
            hashlib.sha256(current_finalize.read_bytes()).hexdigest()
            if current_finalize.exists()
            else None
        ),
        "prior_admitted_feasibility_sha256": (
            hashlib.sha256(current_feasibility.read_bytes()).hexdigest()
            if current_feasibility.exists()
            else None
        ),
        "accepted_authority_preserved": True,
        "implementation_dispatch_allowed": False,
        "updated_at": now_utc(),
    }
    meta["planner_repair"] = repair
    atomic_write_json(plan_dir / "planner_repair.json", repair)
    return repair


def clear_planner_repair(state: dict[str, Any]) -> None:
    meta = state.get("meta")
    if isinstance(meta, dict):
        meta.pop("planner_repair", None)


__all__ = [
    "CIRCUIT_THRESHOLD",
    "SCHEMA",
    "SCHEMA_VERSION",
    "candidate_graph_record",
    "clear_planner_repair",
    "record_rejected_candidate",
]
