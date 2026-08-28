from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.types import FLAG_BLOCKING_STATUSES

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

# Versioned critique-family artifacts are re-produced whenever the planning
# loop re-enters the critique phase (an explicit ``override replan`` or a
# deterministic ``override recover-blocked`` repair of the critique phase).
# The create-once custody receipts (``critique_custody_v*.json``) are the
# collision point: a fresh critique run at the same iteration computes a
# different semantic payload, and the create-once publish refuses to overwrite
# the stale receipt, producing a deterministic
# ``critique_custody_receipt_conflict`` phase failure.  Archive the whole
# versioned critique family so the fresh epoch starts from an empty active
# namespace while the superseded bytes remain audit-preserved.  The create-once
# invariant itself is unchanged: it still applies within a planning epoch.
REPLAN_CRITIQUE_EPOCH_ARTIFACT_PATTERNS: tuple[str, ...] = (
    "critique_custody_v*.json",
    "critique_custody_legacy_migration_v*.json",
    "critique_v*.json",
    "critique_raw_v*.txt",
    "critique_parallel_manifest_v*.json",
    "critique_check_*.json",
    "critique_check_*_raw*.txt",
    "critique_evaluator_output*.json",
    "critique_evaluator_raw_v*.txt",
    "step_receipt_critique_v*.json",
)

# The gate phase publishes the immutable ``gate_v*.json`` projection
# (write_immutable_json).  Re-entering gate at the same iteration after a
# deterministic repair collides with the stale immutable bytes exactly like the
# critique custody receipts; the versioned gate family is archived so the fresh
# gate run publishes new evidence.  The unversioned ``gate.json`` projection
# stays atomic (overwritten by the fresh run).
REPLAN_GATE_EPOCH_ARTIFACT_PATTERNS: tuple[str, ...] = (
    "gate_v*.json",
    "gate_v*_raw.txt",
    "gate_signals_v*.json",
    "step_receipt_gate_v*.json",
)


def invalidate_replan_derived_artifacts(
    plan_dir: Path,
    *,
    timestamp: str,
    include_critique_epoch: bool = False,
    include_gate_epoch: bool = False,
    scope: str | None = None,
) -> dict[str, Any] | None:
    """Archive active post-gate artifacts invalidated by a replan.

    The archive sits outside the active plan directory so phase workers cannot
    mistake old finalize evidence for the current planning epoch.  A manifest
    remains in the plan directory and binds each preserved artifact by hash.
    When ``include_critique_epoch`` is set, the versioned critique-family
    artifacts (including the create-once custody receipts) are archived with
    the same manifest so a re-entered planning loop can publish fresh receipts.
    ``include_gate_epoch`` does the same for the versioned gate family
    (including the immutable ``gate_v*.json`` projections).

    ``scope`` selects a NARROWER, phase-scoped invalidation for a deterministic
    retry (e.g. a gate re-run after a tiebreaker or provider retry):
    - ``"gate_retry"``: archive ONLY the current-iteration gate family. The
      critique custody receipt + critique producer/raw/manifest set stay ACTIVE
      because ``validate_gate_input_custody()`` requires them on resume. This
      fixes the over-archive that removed critique custody and broke gate resume.
    - ``"critique_retry"``: archive ONLY the current-iteration critique family
      (fresh critique re-run publishes a new receipt).
    - ``"full_replan"``: archive both critique and gate families (same as
      include_critique_epoch + include_gate_epoch).
    """

    matched: list[Path] = []
    if scope == "gate_retry":
        for pattern in REPLAN_GATE_EPOCH_ARTIFACT_PATTERNS:
            for candidate in plan_dir.glob(pattern):
                if candidate.is_file() and candidate not in matched:
                    matched.append(candidate)
        existing = sorted(matched)
        if not existing:
            return None
        return _archive_matched(plan_dir, existing, timestamp)
    if scope == "critique_retry":
        for pattern in REPLAN_CRITIQUE_EPOCH_ARTIFACT_PATTERNS:
            for candidate in plan_dir.glob(pattern):
                if candidate.is_file() and candidate not in matched:
                    matched.append(candidate)
        existing = sorted(matched)
        if not existing:
            return None
        return _archive_matched(plan_dir, existing, timestamp)
    for name in REPLAN_DERIVED_ARTIFACTS_TO_INVALIDATE:
        candidate = plan_dir / name
        if candidate.is_file():
            matched.append(candidate)
    if include_critique_epoch:
        for pattern in REPLAN_CRITIQUE_EPOCH_ARTIFACT_PATTERNS:
            for candidate in plan_dir.glob(pattern):
                if candidate.is_file() and candidate not in matched:
                    matched.append(candidate)
    if include_gate_epoch:
        for pattern in REPLAN_GATE_EPOCH_ARTIFACT_PATTERNS:
            for candidate in plan_dir.glob(pattern):
                if candidate.is_file() and candidate not in matched:
                    matched.append(candidate)
    existing = sorted(matched)
    if not existing:
        return None
    return _archive_matched(plan_dir, existing, timestamp)


def _archive_matched(
    plan_dir: Path,
    existing: list[Path],
    timestamp: str,
) -> dict[str, Any]:
    """Archive a concrete artifact list to .replan-invalidated with a manifest."""
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


CAP_REVISE_ONCE_GRANT_KEY = "cap_revise_once_grant"
_CAP_REVISE_ONCE_SIGNIFICANT_SEVERITIES = ("significant", "likely-significant")


def cap_revise_once_override_allowed(state: Mapping[str, Any]) -> bool:
    """Return whether a critique-cap blocked park may grant one revise round.

    Accepts ONLY the exact cap-terminated shape: blocked on an ITERATE gate
    that did not pass, with the cap termination recorded as the newest history
    entry, no resume cursor or failure record, and no unconsumed grant. Every
    other blocked shape stays fail closed.
    """

    if state.get("current_state") != "blocked":
        return False
    last_gate = state.get("last_gate")
    if not isinstance(last_gate, Mapping):
        return False
    recommendation = last_gate.get("recommendation")
    if not (
        isinstance(recommendation, str)
        and recommendation.upper() == "ITERATE"
        and last_gate.get("passed") is False
    ):
        return False
    if (
        state.get("resume_cursor") is not None
        or state.get("latest_failure") is not None
    ):
        return False
    history = state.get("history")
    if not isinstance(history, list) or not history:
        return False
    newest = history[-1]
    if (
        not isinstance(newest, Mapping)
        or newest.get("step") != "gate"
        or newest.get("result") != "blocked"
    ):
        return False
    meta = state.get("meta")
    if isinstance(meta, Mapping):
        grant = meta.get(CAP_REVISE_ONCE_GRANT_KEY)
        if isinstance(grant, Mapping) and not grant.get("consumed"):
            return False
    return True


def significant_flag_ids(flags: Any) -> set[str]:
    """Open significant flag IDs from a gate ``unresolved_flags`` list.

    Mirrors the cap-termination policy's significant severities; the result is
    used only for cap-revise-once bookkeeping (baseline capture and the
    strict-decrease check), never to change whether a gate blocks.
    """

    ids: set[str] = set()
    if not isinstance(flags, Sequence) or isinstance(flags, (str, bytes)):
        return ids
    for flag in flags:
        if not isinstance(flag, Mapping):
            continue
        if flag.get("status") not in FLAG_BLOCKING_STATUSES:
            continue
        if flag.get("severity") not in _CAP_REVISE_ONCE_SIGNIFICANT_SEVERITIES:
            continue
        flag_id = flag.get("id")
        if isinstance(flag_id, str) and flag_id:
            ids.add(flag_id)
    return ids


def gate_signals_baseline(plan_dir: Path, iteration: Any) -> dict[str, Any]:
    """Baseline open-significant flags from the blocking gate's artifact.

    Reads ``gate_signals_v{iteration}.json`` (falling back to the newest gate
    signals artifact) so the grant records exactly the flag set the blocking
    gate saw. Fails closed when the artifact is missing, unreadable, or shows
    no open significant flag — a block without one is not a critique-cap flag
    park.
    """

    artifact = plan_dir / f"gate_signals_v{iteration}.json"
    if not artifact.exists():
        candidates = sorted(plan_dir.glob("gate_signals_v*.json"))
        if not candidates:
            raise ValueError(
                "cap-revise-once requires the blocking gate's signals artifact "
                f"gate_signals_v{iteration}.json to record the flag baseline"
            )
        artifact = candidates[-1]
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as error:
        raise ValueError(
            f"cap-revise-once could not read gate signals artifact {artifact.name}: {error}"
        ) from error
    unresolved = payload.get("unresolved_flags") if isinstance(payload, dict) else None
    ids = significant_flag_ids(unresolved)
    if not ids:
        raise ValueError(
            "cap-revise-once requires at least one open significant flag in "
            f"{artifact.name}; this block shape is not a critique-cap flag park"
        )
    digest = hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()[:16]
    return {
        "artifact": artifact.name,
        "baseline_flag_ids": sorted(ids),
        "baseline_flag_count": len(ids),
        "baseline_digest": f"sha256:{digest}",
    }


def events_max_seq(plan_dir: Path) -> int | None:
    """Newest ``seq`` in the plan's ``events.ndjson`` (None when absent)."""

    events_path = plan_dir / "events.ndjson"
    if not events_path.exists():
        return None
    with events_path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - 65536))
        tail = handle.read().decode("utf-8", errors="replace")
    lines = [line for line in tail.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        payload = json.loads(lines[-1])
    except ValueError:
        return None
    seq = payload.get("seq") if isinstance(payload, dict) else None
    return seq if isinstance(seq, int) else None


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
