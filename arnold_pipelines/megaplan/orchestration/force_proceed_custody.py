"""CAS-owned custody reconciliation for ``override force-proceed``.

The override is allowed to waive a planning objection, but it must never make
that objection disappear.  This module converts every currently blocking
critique flag and North-Star action into an explicit, content-addressed
disposition.  The record is stored in ``state.meta`` by the same CAS that
advances the workflow; ``gate*.json``, ``faults.json`` and ``debt.json`` are
repairable projections of that record.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import (
    extract_subsystem_tag,
    load_debt_registry,
    load_flag_registry,
    now_utc,
    save_debt_registry,
    save_flag_registry,
    unresolved_significant_flags,
)
from arnold_pipelines.megaplan._core.registries import add_or_increment_debt
from arnold_pipelines.megaplan.north_star_actions import (
    blocking_north_star_actions,
    read_carried_north_star_actions,
)


SCHEMA_VERSION = "megaplan.force_proceed_custody.v1"


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_force_proceed_custody(
    plan_dir: Path,
    state: Mapping[str, Any],
    *,
    reason: str | None,
) -> dict[str, Any]:
    """Build the complete disposition set without mutating durable state."""

    flag_rows = []
    for flag in unresolved_significant_flags(load_flag_registry(plan_dir)):
        flag_id = str(flag["id"])
        flag_rows.append(
            {
                "subject_kind": "critique_finding",
                "subject_id": flag_id,
                "disposition": "waived_to_debt",
                "concern": str(flag.get("concern") or ""),
                "evidence": str(flag.get("evidence") or ""),
                "reason": reason or "Operator force-proceeded with explicit debt.",
            }
        )
    flag_rows.sort(key=lambda row: row["subject_id"])

    north_star_rows = []
    for action in blocking_north_star_actions(read_carried_north_star_actions(plan_dir)):
        action_id = str(action["id"])
        north_star_rows.append(
            {
                "subject_kind": "north_star_action",
                "subject_id": action_id,
                "action_type": str(action["action_type"]),
                "disposition": "operator_waiver",
                "concern": str(action.get("concern") or ""),
                "evidence": str(action.get("evidence") or ""),
                "reason": reason or "Operator force-proceeded with explicit debt.",
            }
        )
    north_star_rows.sort(key=lambda row: row["subject_id"])

    semantic = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": str(state.get("name") or plan_dir.name),
        "from_state": str(state.get("current_state") or ""),
        "reason": reason or "",
        "critique_dispositions": flag_rows,
        "north_star_dispositions": north_star_rows,
    }
    transaction_id = f"force-proceed:{_digest(semantic)}"
    return {
        **semantic,
        "transaction_id": transaction_id,
        "committed_at": now_utc(),
    }


def north_star_addressed_rows(custody: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project forced North-Star waivers into the existing addressed vocabulary."""

    transaction_id = str(custody.get("transaction_id") or "")
    return [
        {
            "action_id": row["subject_id"],
            "resolution": "rejected",
            "reason": row["reason"],
            "where": transaction_id,
            "plan_refs": [transaction_id],
            "action_type": row["action_type"],
        }
        for row in custody.get("north_star_dispositions", [])
        if isinstance(row, Mapping)
    ]


def critique_resolution_rows(custody: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project forced critique waivers into the existing gate vocabulary."""

    return [
        {
            "flag_id": row["subject_id"],
            "action": "accept_tradeoff",
            "evidence": row["evidence"],
            "rationale": row["reason"],
        }
        for row in custody.get("critique_dispositions", [])
        if isinstance(row, Mapping)
    ]


def project_force_proceed_custody(
    *,
    root: Path,
    plan_dir: Path,
    state: Mapping[str, Any],
    gate: Mapping[str, Any],
) -> int:
    """Idempotently materialize registries from the CAS-committed custody row."""

    meta = state.get("meta")
    custody = meta.get("force_proceed_custody") if isinstance(meta, Mapping) else None
    if not isinstance(custody, Mapping):
        raise ValueError("force-proceed projection requires committed custody")
    transaction_id = str(custody.get("transaction_id") or "")
    if not transaction_id:
        raise ValueError("force-proceed custody has no transaction_id")

    # Critique registry remains the existing authority surface.  The CAS-owned
    # row is its recovery source if projection crashes between files.
    registry = load_flag_registry(plan_dir)
    by_id = {
        str(flag.get("id")): flag
        for flag in registry.get("flags", [])
        if isinstance(flag, dict) and flag.get("id")
    }
    for row in custody.get("critique_dispositions", []):
        if not isinstance(row, Mapping):
            continue
        flag = by_id.get(str(row.get("subject_id") or ""))
        if flag is None:
            continue
        flag["status"] = "accepted_tradeoff"
        flag["gate_resolution"] = {
            "action": "accept_tradeoff",
            "evidence": str(row.get("evidence") or ""),
            "rationale": str(row.get("reason") or ""),
            "force_proceed_transaction_id": transaction_id,
        }
    save_flag_registry(plan_dir, registry)

    # Debt projection carries a transaction ledger so retries repair missing
    # files without incrementing occurrence counts twice.
    debt_registry = load_debt_registry(root)
    projected = debt_registry.setdefault("force_proceed_transactions", [])
    if transaction_id not in projected:
        for row in custody.get("critique_dispositions", []):
            if not isinstance(row, Mapping):
                continue
            concern = str(row.get("concern") or "")
            add_or_increment_debt(
                debt_registry,
                subsystem=extract_subsystem_tag(concern),
                concern=concern,
                flag_ids=[str(row.get("subject_id") or "")],
                plan_id=str(state.get("name") or ""),
            )
        for row in custody.get("north_star_dispositions", []):
            if not isinstance(row, Mapping):
                continue
            concern = str(row.get("concern") or "")
            add_or_increment_debt(
                debt_registry,
                subsystem="north-star",
                concern=concern,
                flag_ids=[str(row.get("subject_id") or "")],
                plan_id=str(state.get("name") or ""),
            )
        projected.append(transaction_id)
        save_debt_registry(root, debt_registry)

    # Write both artifacts: readers deliberately prefer gate_carry.json, so
    # updating only gate.json leaves stale custody in force.
    from arnold_pipelines.megaplan._core import atomic_write_json
    from arnold_pipelines.megaplan.handlers.gate import _build_gate_carry

    gate_payload = dict(gate)
    atomic_write_json(plan_dir / "gate.json", gate_payload)
    atomic_write_json(
        plan_dir / "gate_carry.json",
        {
            **_build_gate_carry(
                gate_payload,
                iteration=int(state.get("iteration") or 0),
            ),
            "source": "override_force_proceed",
            "force_proceed_transaction_id": transaction_id,
        },
    )
    return len(custody.get("critique_dispositions", [])) + len(
        custody.get("north_star_dispositions", [])
    )


__all__ = [
    "SCHEMA_VERSION",
    "build_force_proceed_custody",
    "critique_resolution_rows",
    "north_star_addressed_rows",
    "project_force_proceed_custody",
]
