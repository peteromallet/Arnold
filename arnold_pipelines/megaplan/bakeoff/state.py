"""Bake-off coordination state.

M7: Projection adapters for bakeoff state and channel shadow state persistence.
----------------------------------------------------------------------
OLD-READER / NEW-WRITER METADATA:
  - Legacy readers (all callers before M7) use load_bakeoff_state() and
    load_channel_shadow_state() which read the state JSON files directly.
    These readers accept the file as authority without cursor validation.
  - New writers (M7+) supplement each save_bakeoff_state() and
    save_channel_shadow_state() with cursor-checked projection events
    appended to append-only histories.
  - New readers (M7+) can use rebuild_bakeoff_state_projection(),
    rebuild_channel_shadow_projection(), or the projection cursor/snapshot
    accessors for cursor-validated reads.
  - UNCERTAINTY: Legacy readers have no cursor validation; divergence
    between the state file and projection history is only detectable by
    the new readers.  Production enforcement remains disabled in M7.
  - The projection histories are append-only ledgers; they never erase
    prior records, even on rebuild.
  - The projections are SUPPLEMENTAL evidence, not authority — the state
    JSON files remain the primary source of truth for all callers.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict

from arnold_pipelines.megaplan._core.io import (
    ProjectionCursor,
    ProjectionCursorMismatchError,
    ProjectionRecord,
    append_projection_event,
    atomic_write_json,
    deterministic_projection_replay,
    latest_projection_cursor,
    load_projection_history,
    now_utc,
    projection_history_path,
    projection_snapshot_path,
    read_json,
    rebuild_projection_atomically,
    sha256_file,
)

log = logging.getLogger("megaplan")


BAKEOFF_SCHEMA_VERSION: Literal[1] = 1
CHANNEL_SHADOW_SCHEMA_VERSION: Literal[1] = 1
BakeoffPhase = Literal["running", "compared", "picked", "merged", "abandoned"]
ChannelShadowSkipReason = Literal[
    "not_sampled",
    "shadow_disabled",
    "cap_pressure",
    "rate_limited",
    "primary_failed_before_shadow",
    "shadow_unavailable",
]


class BakeoffProfileRecord(TypedDict):
    name: str
    worktree: str
    plan_id: str
    pid: int | None
    launched_at: str | None
    terminated_at: str | None
    outcome: dict[str, Any] | None
    log_path: str
    outcome_path: str


class BakeoffState(TypedDict, total=False):
    schema_version: Literal[1]
    experiment_id: str
    base_sha: str
    idea_hash: str
    idea_path: str
    mode: str
    # Relative (to each worktree) path to the doc artifact in --mode doc bake-offs.
    # Absent / None for code-mode bake-offs. Kept optional so historical state
    # files written before this field existed still load.
    output_path: str | None
    profiles: list[BakeoffProfileRecord]
    phase: BakeoffPhase
    chosen_profile: str | None
    merged_at: str | None
    judge_model: str | None


class ChannelShadowReceiptRecord(TypedDict, total=False):
    receipt_path: str | None
    worker_channel: str
    auth_channel: str | None
    phase: str
    plan_id: str
    exit_kind: str | None
    payload_schema_valid: bool | None
    landed_diff: str | None
    worker_did_work: str | None
    latency_ms: int | None
    cost_usd: float | None
    metadata: dict[str, Any]


class ChannelShadowDecision(TypedDict):
    sampled: bool
    skipped: bool
    skip_reason: ChannelShadowSkipReason | None
    sample_rate: float
    sample_key: str


class ChannelShadowLatencyCostDrift(TypedDict):
    primary_latency_ms: int | None
    shadow_latency_ms: int | None
    latency_drift_ms: int | None
    latency_drift_ratio: float | None
    primary_cost_usd: float | None
    shadow_cost_usd: float | None
    cost_drift_usd: float | None
    cost_drift_ratio: float | None


class ChannelShadowParityResult(TypedDict):
    passed: bool
    exit_kind_match: bool
    payload_schema_valid_match: bool
    landed_diff_match: bool
    worker_did_work_match: bool
    compared_at: str
    details: dict[str, Any]


class ChannelShadowPair(TypedDict):
    primary_worker_channel: str
    primary_auth_channel: str | None
    shadow_worker_channel: str
    shadow_auth_channel: str | None


class ChannelShadowProvenance(TypedDict, total=False):
    source: str
    fixture: bool
    sample_key: str
    plan_id: str
    phase: str


class ChannelShadowGate(TypedDict):
    greenlight: bool
    threshold: int
    real_parity_success_count: int
    real_parity_failure_count: int
    skipped_count: int
    fixture_count: int
    blockers: list[str]
    channel_pair: ChannelShadowPair | None
    provenance: dict[str, Any]
    evaluated_at: str
    api_channel_greenlight: bool
    api_channel_blockers: list[str]


class ChannelShadowRecord(TypedDict, total=False):
    channel_pair: ChannelShadowPair
    provenance: ChannelShadowProvenance
    decision: ChannelShadowDecision
    primary_receipt: ChannelShadowReceiptRecord
    shadow_receipt: ChannelShadowReceiptRecord | None
    drift: ChannelShadowLatencyCostDrift | None
    parity_result: ChannelShadowParityResult | None
    real_parity_success_count: int
    recorded_at: str


class ChannelShadowState(TypedDict):
    schema_version: Literal[1]
    experiment_id: str
    records: list[ChannelShadowRecord]
    real_parity_success_count: int
    gate: ChannelShadowGate


def bakeoff_root(root: Path, exp_id: str) -> Path:
    return root / ".megaplan" / "bakeoffs" / exp_id


def worktree_root(root: Path, exp_id: str) -> Path:
    return root.resolve().parent / ".megaplan-worktrees" / exp_id


def load_bakeoff_state(root: Path, exp_id: str) -> BakeoffState:
    return read_json(bakeoff_root(root, exp_id) / "bakeoff.json")


def save_bakeoff_state(
    root: Path,
    state: BakeoffState,
    *,
    _record_projection: bool = True,
) -> None:
    """Persist bakeoff state with atomic JSON replacement.

    M7 (shadow): In addition to the legacy full-file atomic write, this
    function appends a cursor-checked projection event to an append-only
    history.  The projection event is recorded *after* the state file write
    succeeds so the source-of-truth file always reflects the committed state.

    Set ``_record_projection=False`` to skip the projection side-effect
    (used by internal rebuild/repair callers that should not create
    duplicate records).
    """
    atomic_write_json(
        bakeoff_root(root, state["experiment_id"]) / "bakeoff.json",
        state,
    )

    # ── M7 projection side-effect ────────────────────────────────────────
    if _record_projection:
        try:
            _record_bakeoff_state_event(root, state)
        except ProjectionCursorMismatchError as exc:
            log.warning(
                "M7 bakeoff-state projection append blocked by cursor mismatch: %s. "
                "State file is intact; projection history may need reconciliation.",
                exc,
            )
        except Exception:
            log.warning(
                "M7 bakeoff-state projection append failed (non-fatal). "
                "State file is intact.",
                exc_info=True,
            )


def channel_shadow_path(root: Path, exp_id: str) -> Path:
    return bakeoff_root(root, exp_id) / "channel_shadow.json"


def load_channel_shadow_state(root: Path, exp_id: str) -> ChannelShadowState:
    return read_json(channel_shadow_path(root, exp_id))


def save_channel_shadow_state(
    root: Path,
    state: ChannelShadowState,
    *,
    _record_projection: bool = True,
) -> None:
    """Persist channel shadow state with atomic JSON replacement.

    M7 (shadow): In addition to the legacy full-file atomic write, this
    function appends a cursor-checked projection event to an append-only
    history.  The projection event is recorded *after* the state file write
    succeeds so the source-of-truth file always reflects the committed state.

    Set ``_record_projection=False`` to skip the projection side-effect
    (used by internal rebuild/repair callers that should not create
    duplicate records).
    """
    atomic_write_json(
        channel_shadow_path(root, state["experiment_id"]),
        state,
    )

    # ── M7 projection side-effect ────────────────────────────────────────
    if _record_projection:
        try:
            _record_channel_shadow_event(root, state)
        except ProjectionCursorMismatchError as exc:
            log.warning(
                "M7 channel-shadow projection append blocked by cursor mismatch: %s. "
                "State file is intact; projection history may need reconciliation.",
                exc,
            )
        except Exception:
            log.warning(
                "M7 channel-shadow projection append failed (non-fatal). "
                "State file is intact.",
                exc_info=True,
            )


def hash_idea_file(path: Path) -> str:
    content = path.read_text(encoding="utf-8").encode("utf-8")
    return hashlib.sha256(content).hexdigest()


# ── M7 projection constants ───────────────────────────────────────────────

_BAKEOFF_PROJECTION_ID = "bakeoff-state"
_CHANNEL_SHADOW_PROJECTION_ID = "channel-shadow-state"
_PROJECTION_SCHEMA_VERSION = 1


def _bakeoff_projection_dir(root: Path, exp_id: str) -> Path:
    """Return the projection storage directory for bakeoff state events.

    Stores under ``<bakeoff_root>/projections/``.
    """
    return bakeoff_root(root, exp_id) / "projections"


def _channel_shadow_projection_dir(root: Path, exp_id: str) -> Path:
    """Return the projection storage directory for channel shadow state events.

    Stores under ``<bakeoff_root>/projections/``.
    """
    return bakeoff_root(root, exp_id) / "projections"


def _cursor_from_bakeoff_file(path: Path) -> ProjectionCursor:
    """Build a ProjectionCursor from the current state of a bakeoff JSON file."""
    resolved = path.resolve()
    record_count = 0
    if resolved.exists():
        try:
            text = resolved.read_text(encoding="utf-8")
            lines = [line for line in text.splitlines() if line.strip()]
            record_count = len(lines)
        except (FileNotFoundError, OSError):
            pass
    source_digest = (
        sha256_file(resolved)
        if resolved.exists()
        else "sha256:" + hashlib.sha256(b"").hexdigest()
    )
    return ProjectionCursor(
        source_path=str(resolved),
        source_record_count=record_count,
        source_digest=source_digest,
        last_appended_at=now_utc(),
    )


def _generate_bakeoff_event_id(projection_id: str, event_type: str) -> str:
    """Generate a deterministic event ID for bakeoff projection events."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    seed = f"{projection_id}:{event_type}:{ts}"
    return f"bakeoff-proj-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"


# ── Bakeoff state projection ──────────────────────────────────────────────


def _record_bakeoff_state_event(
    root: Path,
    state: BakeoffState,
    *,
    event_type: str = "state_saved",
    flock: bool = True,
) -> ProjectionRecord:
    """Append a cursor-checked projection event recording the bakeoff state save.

    The event carries the full state payload and a cursor derived from the
    current bakeoff.json file.  This is a shadow-side-effect — it supplements
    the existing full-file write without replacing it.
    """
    exp_id = state["experiment_id"]
    projection_dir = _bakeoff_projection_dir(root, exp_id)
    state_path = bakeoff_root(root, exp_id) / "bakeoff.json"

    source_cursor = None
    if state_path.exists():
        try:
            source_cursor = _cursor_from_bakeoff_file(state_path)
        except (FileNotFoundError, OSError):
            pass

    event_id = _generate_bakeoff_event_id(_BAKEOFF_PROJECTION_ID, event_type)
    record = ProjectionRecord(
        event_type=event_type,
        event_id=event_id,
        payload={
            "schema_version": _PROJECTION_SCHEMA_VERSION,
            "experiment_id": exp_id,
            "state": dict(state),
        },
        occurred_at=now_utc(),
        cursor=source_cursor,
        idempotency_key=f"bakeoff-save-{exp_id}-{event_id}",
    )
    return append_projection_event(
        projection_dir,
        _BAKEOFF_PROJECTION_ID,
        record,
        source_path=state_path,
        flock=flock,
        snapshot_dir=projection_dir,
    )


def rebuild_bakeoff_state_projection(
    root: Path,
    exp_id: str,
    *,
    flock: bool = True,
) -> dict[str, Any]:
    """Atomically rebuild the bakeoff state projection from the append-only history.

    Returns a dict with keys:
      - ``status``: ``"rebuilt"`` | ``"no_history"`` | ``"error"``
      - ``snapshot_path``: path to the written snapshot (if rebuilt)
      - ``projection``: the complete projected state (if rebuilt)
      - ``cursor``: the latest source cursor (if available)
      - ``record_count``: number of projection records processed
      - ``diagnostics``: list of diagnostic messages
    """
    projection_dir = _bakeoff_projection_dir(root, exp_id)
    diagnostics: list[str] = []
    records = load_projection_history(projection_dir, _BAKEOFF_PROJECTION_ID)
    if not records:
        return {
            "status": "no_history",
            "snapshot_path": None,
            "projection": None,
            "cursor": None,
            "record_count": 0,
            "diagnostics": ["No bakeoff projection history found — nothing to rebuild"],
        }

    def _fold_bakeoff_state(
        acc: dict[str, Any], record: ProjectionRecord
    ) -> dict[str, Any]:
        """Fold: last state payload wins."""
        state_payload = record.payload.get("state")
        if isinstance(state_payload, dict):
            acc.update(state_payload)
        return acc

    try:
        projection_data = deterministic_projection_replay(
            projection_dir, _BAKEOFF_PROJECTION_ID, fold_fn=_fold_bakeoff_state
        )
    except Exception as exc:
        return {
            "status": "error",
            "snapshot_path": None,
            "projection": None,
            "cursor": None,
            "record_count": len(records),
            "diagnostics": [f"Bakeoff replay failed: {exc}"],
        }

    last_cursor = latest_projection_cursor(projection_dir, _BAKEOFF_PROJECTION_ID)
    snapshot_path = rebuild_projection_atomically(
        projection_dir,
        _BAKEOFF_PROJECTION_ID,
        projection_data,
        cursor=last_cursor,
    )
    return {
        "status": "rebuilt",
        "snapshot_path": str(snapshot_path),
        "projection": dict(projection_data),
        "cursor": last_cursor.to_dict() if last_cursor else None,
        "record_count": len(records),
        "diagnostics": diagnostics,
    }


def bakeoff_state_projection_cursor(
    root: Path, exp_id: str
) -> ProjectionCursor | None:
    """Return the latest cursor from the bakeoff state projection history."""
    projection_dir = _bakeoff_projection_dir(root, exp_id)
    return latest_projection_cursor(projection_dir, _BAKEOFF_PROJECTION_ID)


def bakeoff_state_projection_snapshot(
    root: Path, exp_id: str
) -> dict[str, Any] | None:
    """Return the most recent bakeoff state projection snapshot, or None."""
    projection_dir = _bakeoff_projection_dir(root, exp_id)
    snapshot_path = projection_snapshot_path(projection_dir, _BAKEOFF_PROJECTION_ID)
    if not snapshot_path.exists():
        return None
    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


# ── Channel shadow state projection ────────────────────────────────────────


def _record_channel_shadow_event(
    root: Path,
    state: ChannelShadowState,
    *,
    event_type: str = "state_saved",
    flock: bool = True,
) -> ProjectionRecord:
    """Append a cursor-checked projection event recording the channel shadow state save."""
    exp_id = state["experiment_id"]
    projection_dir = _channel_shadow_projection_dir(root, exp_id)
    state_path = channel_shadow_path(root, exp_id)

    source_cursor = None
    if state_path.exists():
        try:
            source_cursor = _cursor_from_bakeoff_file(state_path)
        except (FileNotFoundError, OSError):
            pass

    event_id = _generate_bakeoff_event_id(_CHANNEL_SHADOW_PROJECTION_ID, event_type)
    record = ProjectionRecord(
        event_type=event_type,
        event_id=event_id,
        payload={
            "schema_version": _PROJECTION_SCHEMA_VERSION,
            "experiment_id": exp_id,
            "state": dict(state),
        },
        occurred_at=now_utc(),
        cursor=source_cursor,
        idempotency_key=f"chshadow-save-{exp_id}-{event_id}",
    )
    return append_projection_event(
        projection_dir,
        _CHANNEL_SHADOW_PROJECTION_ID,
        record,
        source_path=state_path,
        flock=flock,
        snapshot_dir=projection_dir,
    )


def rebuild_channel_shadow_projection(
    root: Path,
    exp_id: str,
    *,
    flock: bool = True,
) -> dict[str, Any]:
    """Atomically rebuild the channel shadow state projection from the append-only history.

    Returns a dict with keys:
      - ``status``: ``"rebuilt"`` | ``"no_history"`` | ``"error"``
      - ``snapshot_path``: path to the written snapshot (if rebuilt)
      - ``projection``: the complete projected state (if rebuilt)
      - ``cursor``: the latest source cursor (if available)
      - ``record_count``: number of projection records processed
      - ``diagnostics``: list of diagnostic messages
    """
    projection_dir = _channel_shadow_projection_dir(root, exp_id)
    diagnostics: list[str] = []
    records = load_projection_history(projection_dir, _CHANNEL_SHADOW_PROJECTION_ID)
    if not records:
        return {
            "status": "no_history",
            "snapshot_path": None,
            "projection": None,
            "cursor": None,
            "record_count": 0,
            "diagnostics": [
                "No channel shadow projection history found — nothing to rebuild"
            ],
        }

    def _fold_channel_shadow(
        acc: dict[str, Any], record: ProjectionRecord
    ) -> dict[str, Any]:
        """Fold: last state payload wins."""
        state_payload = record.payload.get("state")
        if isinstance(state_payload, dict):
            acc.update(state_payload)
        return acc

    try:
        projection_data = deterministic_projection_replay(
            projection_dir,
            _CHANNEL_SHADOW_PROJECTION_ID,
            fold_fn=_fold_channel_shadow,
        )
    except Exception as exc:
        return {
            "status": "error",
            "snapshot_path": None,
            "projection": None,
            "cursor": None,
            "record_count": len(records),
            "diagnostics": [f"Channel shadow replay failed: {exc}"],
        }

    last_cursor = latest_projection_cursor(
        projection_dir, _CHANNEL_SHADOW_PROJECTION_ID
    )
    snapshot_path = rebuild_projection_atomically(
        projection_dir,
        _CHANNEL_SHADOW_PROJECTION_ID,
        projection_data,
        cursor=last_cursor,
    )
    return {
        "status": "rebuilt",
        "snapshot_path": str(snapshot_path),
        "projection": dict(projection_data),
        "cursor": last_cursor.to_dict() if last_cursor else None,
        "record_count": len(records),
        "diagnostics": diagnostics,
    }


def channel_shadow_projection_cursor(
    root: Path, exp_id: str
) -> ProjectionCursor | None:
    """Return the latest cursor from the channel shadow projection history."""
    projection_dir = _channel_shadow_projection_dir(root, exp_id)
    return latest_projection_cursor(projection_dir, _CHANNEL_SHADOW_PROJECTION_ID)


def channel_shadow_projection_snapshot(
    root: Path, exp_id: str
) -> dict[str, Any] | None:
    """Return the most recent channel shadow projection snapshot, or None."""
    projection_dir = _channel_shadow_projection_dir(root, exp_id)
    snapshot_path = projection_snapshot_path(
        projection_dir, _CHANNEL_SHADOW_PROJECTION_ID
    )
    if not snapshot_path.exists():
        return None
    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
