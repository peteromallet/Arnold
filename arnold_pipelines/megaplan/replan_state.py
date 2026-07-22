from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core.io import atomic_write_json

REPLAN_META_KEYS_TO_CLEAR: tuple[str, ...] = (
    "tiebreaker_count",
    "user_approved_gate",
)
REPLAN_STATE_KEYS_TO_CLEAR: tuple[str, ...] = (
    "active_step",
    "latest_failure",
    "resume_cursor",
)

# These artifacts are derived from the plan only after gate.  Keeping them at
# their active paths across an explicit replan lets gate/finalize workers read
# evidence from a different planning epoch and can make a repaired plan appear
# to retain an obsolete executable graph.  Preserve the bytes for audit, but
# remove them from the active plan namespace before the new planning loop.
REPLAN_DERIVED_ARTIFACTS_TO_INVALIDATE: tuple[str, ...] = (
    "critique_clearance.json",
    "finalize_output.json",
    "finalize.json",
    "finalize_snapshot.json",
    "task_feasibility.json",
    "contract.json",
    "final.md",
    "user_actions.md",
)


def invalidate_replan_derived_artifacts(
    plan_dir: Path,
    *,
    timestamp: str,
) -> dict[str, Any] | None:
    """Archive active post-gate artifacts invalidated by a replan.

    The archive sits outside the active plan directory so phase workers cannot
    mistake old finalize evidence for the current planning epoch.  A manifest
    remains in the plan directory and binds each preserved artifact by hash.
    """

    existing = [
        plan_dir / name
        for name in REPLAN_DERIVED_ARTIFACTS_TO_INVALIDATE
        if (plan_dir / name).is_file()
    ]
    if not existing:
        return None

    safe_timestamp = "".join(character for character in timestamp if character.isalnum())
    snapshots = [
        (source, source.read_bytes())
        for source in existing
    ]
    epoch_digest = hashlib.sha256(
        b"\0".join(
            source.name.encode("utf-8") + b"\0" + data
            for source, data in snapshots
        )
    ).hexdigest()[:12]
    epoch_id = f"{safe_timestamp or 'unknown-time'}-{epoch_digest}"
    archive_dir = (
        plan_dir.parent
        / ".replan-invalidated"
        / plan_dir.name
        / epoch_id
    )
    archive_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, str]] = []
    for source, data in snapshots:
        destination = archive_dir / source.name
        os.replace(source, destination)
        records.append(
            {
                "artifact": source.name,
                "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
                "archive_path": destination.relative_to(plan_dir.parent).as_posix(),
            }
        )

    manifest = {
        "schema_version": "megaplan-replan-artifact-invalidation-v1",
        "invalidated_at": timestamp,
        "reason": "override_replan_new_planning_epoch",
        "artifacts": records,
    }
    manifest_name = f"replan_artifact_invalidation_{epoch_id}.json"
    atomic_write_json(plan_dir / manifest_name, manifest)
    return {"manifest": manifest_name, **manifest}


def blocked_iterate_gate_replan_allowed(state: Mapping[str, Any]) -> bool:
    """Return whether a blocked ITERATE gate may re-enter planning.

    The critique-loop cap can latch the plan in ``blocked`` after an ITERATE
    verdict without writing a resume cursor.  Replanning is the narrow recovery
    seam for that exact state; every other blocked state remains fail closed.
    """

    if state.get("current_state") != "blocked":
        return False
    last_gate = state.get("last_gate")
    if not isinstance(last_gate, Mapping):
        return False
    recommendation = last_gate.get("recommendation")
    return (
        isinstance(recommendation, str)
        and recommendation.upper() == "ITERATE"
        and last_gate.get("passed") is False
    )


def reset_replan_loop_state(
    state: MutableMapping[str, Any],
    *,
    target_state: str,
) -> MutableMapping[str, Any]:
    """Clear stale loop/runtime state before re-entering planning."""

    raw_meta = state.get("meta")
    if isinstance(raw_meta, MutableMapping):
        meta = raw_meta
    else:
        meta = {}
        state["meta"] = meta

    for key in REPLAN_META_KEYS_TO_CLEAR:
        meta.pop(key, None)
    for key in REPLAN_STATE_KEYS_TO_CLEAR:
        state.pop(key, None)

    state["last_gate"] = {}
    state["current_state"] = target_state
    return meta
