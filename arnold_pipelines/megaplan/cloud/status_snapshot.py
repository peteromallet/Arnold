"""Canonical cloud status snapshot — local observation only, never SSH.

This module produces the single "what is running?" truth document for the cloud
worker, ``/workspace/.megaplan/status/cloud-status.json``. Every status consumer
reads this same document: the Discord resident, watchdog notifications,
``megaplan cloud status --all``, and humans debugging the box.

Design rules (see ``docs/ops/elegant-cloud-status-resident-plan.md``):

- Describe the cloud box from inside the cloud box. Never SSH.
- Read only files the watchdog already writes: the canonical session markers in
  ``/workspace/.megaplan/cloud-sessions/*.json``, the chain-health sidecars
  ``*.chain-health.progress.json``, repair markers, ``needs-human`` markers, the
  ``/workspace/watchdog-report.json`` verdicts, and the plan state files. The only
  process namespace touch is best-effort tmux/ps liveness probing.
- Be unit-testable with fixture directories and an injectable liveness probe.
- Know nothing about Discord, resident conversations, or CLI rendering. Those
  live in :mod:`arnold_pipelines.megaplan.cloud.status_format` and the resident.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from arnold_pipelines.megaplan.cloud.feature_flags import resolver_observe_enabled
from arnold_pipelines.megaplan.cloud.human_blockers import classify_needs_human_blocker
from arnold_pipelines.megaplan.cloud.session_markers import (
    is_canonical_session_marker_path,
)
from arnold_pipelines.megaplan.observability.events import EventKind, emit
from arnold_pipelines.megaplan.run_state.model import CanonicalRunState, CanonicalState
from arnold_pipelines.megaplan.run_state.resolver import resolve_run_state

# --- canonical paths -------------------------------------------------------

DEFAULT_MARKER_DIR = Path("/workspace/.megaplan/cloud-sessions")
DEFAULT_WATCHDOG_REPORT = Path("/workspace/watchdog-report.json")
DEFAULT_FALLBACK_WATCHDOG_REPORT = Path("/workspace/.megaplan/watchdog-report.json")
DEFAULT_STATUS_DIR = Path("/workspace/.megaplan/status")
DEFAULT_SNAPSHOT_PATH = DEFAULT_STATUS_DIR / "cloud-status.json"
DEFAULT_PREVIOUS_SNAPSHOT_PATH = DEFAULT_STATUS_DIR / "cloud-status.previous.json"
DEFAULT_WORKSPACE_ROOT = Path("/workspace")

SNAPSHOT_SOURCE = "cloud-local-observer"


def is_trusted_container() -> bool:
    """True when this process is the cloud worker itself (local observation fits).

    The resident, watchdog, and runners set ``MEGAPLAN_TRUSTED_CONTAINER=1`` inside
    the container; combined with the canonical marker directory being present, that
    means a fresh local snapshot can be built on demand with no SSH. Consumers that
    opt into a per-turn fresh view (the resident hot context) use this to decide
    build-vs-read.
    """
    if os.environ.get("MEGAPLAN_TRUSTED_CONTAINER") != "1":
        return False
    return DEFAULT_MARKER_DIR.exists()

# A session whose latest activity is older than this is not "running" on
# activity alone; it must have a live process or be under active repair.
STALE_ACTIVITY_S = 30 * 60
# A repair-progress marker older than this no longer counts as "repairing".
REPAIR_FRESH_S = 6 * 60 * 60

SessionStatus = str  # one of: running | repairing | blocked | complete | attention
LivenessProbe = Callable[[Mapping[str, Any]], dict[str, bool]]

_CANONICAL_STATUS_MAP: dict[CanonicalState, SessionStatus | None] = {
    CanonicalState.RUNNING: "running",
    CanonicalState.REPAIRING: "repairing",
    CanonicalState.RETRYABLE_EXECUTION_BLOCK: "attention",
    CanonicalState.REAL_IMPLEMENTATION_BLOCK: "attention",
    CanonicalState.HUMAN_ACTION_REQUIRED: "blocked",
    CanonicalState.COMPLETED: "complete",
    CanonicalState.STALE_DERIVED_STATE: "attention",
    CanonicalState.BROKEN_STATE_MACHINE: "attention",
    CanonicalState.UNKNOWN: None,
}


# --- public API ------------------------------------------------------------


def build_cloud_status_snapshot(
    *,
    marker_dir: Path | None = None,
    watchdog_report_path: Path | None = None,
    repair_data_dir: Path | None = None,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    now: datetime | None = None,
    liveness_probe: LivenessProbe | None = None,
) -> dict[str, Any]:
    """Build the canonical cloud status snapshot from local observation only.

    All file reads are defensive: a missing or malformed source file degrades a
    session to ``attention`` rather than raising. The function never raises on
    absent inputs — callers may inspect the top-level ``degraded`` field.
    """
    now = now or _utcnow()
    # Resolve defaults at call time so tests (and in-container callers) see the
    # current module-level paths rather than values captured at def time.
    marker_dir = Path(marker_dir) if marker_dir else DEFAULT_MARKER_DIR
    watchdog_report_path = Path(watchdog_report_path) if watchdog_report_path else DEFAULT_WATCHDOG_REPORT
    repair_data_dir = Path(repair_data_dir) if repair_data_dir else marker_dir / "repair-data"
    probe = liveness_probe or default_liveness_probe

    watchdog_report, watchdog_by_session, degraded_reasons = _load_watchdog_report(
        watchdog_report_path, DEFAULT_FALLBACK_WATCHDOG_REPORT
    )
    markers = _load_session_markers(marker_dir)

    sessions: list[dict[str, Any]] = []
    for marker in markers:
        sessions.append(
            _build_session_entry(
                marker,
                marker_dir=marker_dir,
                repair_data_dir=repair_data_dir,
                watchdog_by_session=watchdog_by_session,
                watchdog_report_path=watchdog_report_path,
                now=now,
                liveness_probe=probe,
            )
        )

    sessions.sort(key=lambda entry: (entry["session"] != "editable-install", entry["status"], entry["session"]))

    summary = _summarize(sessions)
    snapshot: dict[str, Any] = {
        "generated_at": _isoformat(now),
        "source": SNAPSHOT_SOURCE,
        "marker_dir": str(marker_dir),
        "watchdog_report": str(watchdog_report_path),
        "summary": summary,
        "sessions": sessions,
        "degraded": {"reasons": degraded_reasons} if degraded_reasons else None,
    }
    if watchdog_report is not None:
        snapshot["watchdog_generated_at"] = watchdog_report.get("timestamp_utc") or ""
        snapshot["watchdog_sessions_seen"] = watchdog_report.get("sessions_seen")
    return snapshot


def write_cloud_status_snapshot(
    snapshot: Mapping[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_PATH,
    *,
    previous_path: Path | str | None = DEFAULT_PREVIOUS_SNAPSHOT_PATH,
) -> Path:
    """Atomically write ``snapshot`` to ``path``, rotating the prior file.

    Writes through a temp file in the same directory and renames, so partial
    writes are never observable. When ``previous_path`` is set, the existing
    snapshot (if any) is moved there first so consumers can diff consecutive
    sweeps. Returns the final path written.
    """
    target = Path(path)
    previous = Path(previous_path) if previous_path else None
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, indent=2, sort_keys=True) + "\n"

    # Rotate the previous snapshot before overwriting.
    if previous is not None and target.exists():
        try:
            shutil.move(str(target), str(previous))
        except OSError:
            # Rotation is best-effort; the fresh write is what matters.
            pass

    fd, tmp_name = tempfile.mkstemp(prefix=".cloud-status.", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def build_and_write_snapshot(
    *,
    marker_dir: Path | None = None,
    watchdog_report_path: Path | None = None,
    path: Path | str = DEFAULT_SNAPSHOT_PATH,
    previous_path: Path | str | None = DEFAULT_PREVIOUS_SNAPSHOT_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the snapshot and atomically write it + the previous rotation.

    Convenience entrypoint for the watchdog: one call after each sweep keeps
    ``cloud-status.json`` fresh. Returns the snapshot that was written.
    """
    snapshot = build_cloud_status_snapshot(
        marker_dir=marker_dir,
        watchdog_report_path=watchdog_report_path,
        now=now,
    )
    write_cloud_status_snapshot(snapshot, path=path, previous_path=previous_path)
    return snapshot


def load_cloud_status_snapshot(
    path: Path | str = DEFAULT_SNAPSHOT_PATH,
    *,
    max_age_s: float | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Read a snapshot from disk, returning ``(snapshot, degraded_reason)``.

    Returns ``(None, reason)`` when the file is missing, unreadable, or — when
    ``max_age_s`` is given — older than the freshness window. This is the single
    entry point consumers use to decide snapshot-first vs. degraded fallback.
    """
    path = Path(path)
    if not path.exists():
        return None, f"snapshot missing at {path}"
    try:
        raw = path.read_text(encoding="utf-8")
        snapshot = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"snapshot unreadable at {path}: {exc.__class__.__name__}"
    if not isinstance(snapshot, dict):
        return None, f"snapshot at {path} is not a JSON object"

    if max_age_s is not None:
        now = now or _utcnow()
        generated_at = _parse_iso(snapshot.get("generated_at"))
        if generated_at is None:
            return snapshot, "snapshot has no generated_at timestamp"
        age = (now - generated_at).total_seconds()
        if age > max_age_s:
            return snapshot, f"snapshot stale ({int(age)}s old, limit {int(max_age_s)}s)"
    return snapshot, None


def plan_activity_summary(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    """Derive the resident ``plan_activity_summary`` from a snapshot.

    Returns three buckets — ``active_working`` (running),
    ``should_be_working_but_needs_attention`` (repairing + attention + blocked
    that should be running), and ``recently_completed`` — plus a ``degraded``
    flag when no snapshot was supplied. This is the shape the resident hot
    context injects; it is derived from the canonical snapshot first.
    """
    if not snapshot or not isinstance(snapshot, Mapping):
        return {
            "degraded": True,
            "reason": "no cloud status snapshot available",
            "active_working": [],
            "should_be_working_but_needs_attention": [],
            "recently_completed": [],
        }
    sessions = snapshot.get("sessions") or []
    active: list[dict[str, Any]] = []
    needs_attention: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    for entry in sessions:
        if not isinstance(entry, Mapping):
            continue
        compact = {
            "session": entry.get("session"),
            "status": entry.get("status"),
            "current_plan": entry.get("current_plan"),
            "operator_next": entry.get("operator_next"),
            "latest_activity": entry.get("latest_activity"),
            "progress": entry.get("progress"),
        }
        status = entry.get("status")
        if status == "running":
            active.append(compact)
        elif status == "complete":
            completed.append(compact)
        elif status in {"repairing", "attention", "blocked"}:
            needs_attention.append(compact)
    return {
        "degraded": False,
        "active_working": active,
        "should_be_working_but_needs_attention": needs_attention,
        "recently_completed": completed,
    }


def _as_int(value: Any) -> int | None:
    """Best-effort int coercion; ``None`` for non-numeric (or bool) values."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_gh_pr_state(payload: Mapping[str, Any]) -> str:
    merged_at = str(payload.get("mergedAt") or "").strip()
    if merged_at:
        return "merged"
    state = str(payload.get("state") or "").strip().lower()
    if state == "open" and bool(payload.get("isDraft")):
        return "draft"
    if state in {"open", "closed", "merged", "draft"}:
        return state
    return ""


def _probe_live_pr_state(workspace: Path | None, pr_number: object) -> dict[str, Any]:
    pr = _as_int(pr_number)
    if pr is None:
        return {"available": False, "reason": "no_pr_number"}
    if workspace is None:
        return {"available": False, "pr_number": pr, "reason": "no_workspace"}
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", str(pr), "--json", "number,state,isDraft,mergedAt"],
            cwd=str(workspace),
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "pr_number": pr, "reason": type(exc).__name__}
    if proc.returncode != 0:
        return {
            "available": False,
            "pr_number": pr,
            "reason": "gh_pr_view_failed",
            "stderr": str(proc.stderr or "").strip()[-500:],
        }
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"available": False, "pr_number": pr, "reason": "invalid_gh_json"}
    if not isinstance(payload, Mapping):
        return {"available": False, "pr_number": pr, "reason": "invalid_gh_payload"}
    state = _normalize_gh_pr_state(payload)
    if not state:
        return {"available": False, "pr_number": pr, "reason": "missing_gh_state"}
    return {
        "available": True,
        "pr_number": _as_int(payload.get("number")) or pr,
        "state": state,
    }


def _session_progress(
    *,
    completed_count: Any,
    milestone_count: Any,
    current_plan: str | None,
    complete: bool,
) -> dict[str, Any] | None:
    """Pre-calculate epic/sprint progress for one snapshot session.

    A chain (epic) is a sequence of milestones — the ``s1``/``s2`` plans. The
    chain-health sidecar tells us how many milestones are done and the total;
    from that we derive an overall epic percent and a per-sprint
    done/in-progress/pending breakdown, so the resident can surface a
    pre-calculated number instead of guessing. Returns ``None`` when there is no
    milestone data to score against, so consumers skip cleanly.

    The breakdown follows the chain's standard sequential progression: the first
    ``completed_count`` milestones are done, the next is the in-flight sprint
    (carrying ``current_plan``), and the rest are pending. We report discrete
    states rather than a false-precision sub-sprint percentage.
    """
    total = _as_int(milestone_count)
    if total is None or total <= 0:
        return None
    done = _as_int(completed_count)
    if done is None:
        done = 0
    done = max(0, min(done, total))
    if complete:
        done = total
    plan = current_plan or None

    percent = 100 if complete else round(done / total * 100)
    sprints: list[dict[str, Any]] = []
    for index in range(1, total + 1):
        if complete or index <= done:
            sprints.append({"sprint": f"s{index}", "status": "done"})
        elif index == done + 1:
            sprint: dict[str, Any] = {"sprint": f"s{index}", "status": "in_progress"}
            if plan:
                sprint["plan"] = plan
            sprints.append(sprint)
        else:
            sprints.append({"sprint": f"s{index}", "status": "pending"})

    return {
        "completed_milestones": done,
        "total_milestones": total,
        "percent": percent,
        "complete": bool(complete),
        "current_plan": plan,
        "sprints": sprints,
    }


# --- per-session classification -------------------------------------------


def _build_resolver_evidence(
    *,
    chain_health: Mapping[str, Any] | None,
    needs_human: Mapping[str, Any] | None,
    repair_progress: Mapping[str, Any] | None,
    watchdog_item: Mapping[str, Any],
    liveness: Mapping[str, bool],
    chain_complete: bool,
) -> dict[str, Any]:
    """Map already-gathered status-snapshot evidence into resolver-compatible shape.

    This is read-only and purely derived from evidence ``_build_session_entry``
    already loaded — no additional filesystem I/O.
    """
    ch = chain_health or {}
    nh = needs_human or {}
    wi = watchdog_item or {}
    is_live = bool(liveness.get("tmux") or liveness.get("process"))

    # Authority completion: a terminal "done" plan state
    plan_current_state = "done" if chain_complete else (ch.get("current_plan_name") or "")

    # Chain last_state — defer to watchdog verdict when chain-health is frozen
    chain_last_state = "done" if chain_complete else (ch.get("last_state") or "")
    wd_status = str(wi.get("status", "")).lower()
    if not chain_last_state and wd_status:
        chain_last_state = wd_status

    # Needs-human structured evidence
    nh_present = bool(nh)
    nh_evidence: dict[str, Any] = {"present": nh_present}
    if nh_present:
        nh_evidence.update(
            {
                "summary": nh.get("summary", ""),
                "path": nh.get("path", ""),
                "recorded_at": nh.get("recorded_at", ""),
                "escalation_label": nh.get("escalation_label", ""),
                "gate_type": nh.get("gate_type", ""),
                "human_gate": nh.get("human_gate", ""),
                "gate": nh.get("gate", ""),
                "category": nh.get("category", ""),
                "gate_kind": nh.get("gate_kind", ""),
                "kind": nh.get("kind", ""),
                "blocked_task_id": nh.get("current", ""),
                "plan_refs": nh.get("plan_refs", []),
            }
        )

    # Repair-progress items
    rp_items: list[dict[str, Any]] = []
    if isinstance(repair_progress, Mapping) and repair_progress:
        rp_items = [dict(repair_progress)]

    return {
        "schema_version": 1,
        "session": "",
        "target_id": "snapshot-observe",
        "authoritative_source": "status_snapshot_observe",
        "target_session": "",
        "current_refs": {},
        "marker": {},
        "plan_state": {
            "current_state": plan_current_state,
            "fingerprint": ch.get("fingerprint", ""),
            "mtime": ch.get("mtime", 0.0),
        },
        "chain_state": {
            "last_state": chain_last_state,
            "fingerprint": ch.get("fingerprint", ""),
            "mtime": ch.get("mtime", 0.0),
        },
        "event_cursors": {
            "latest_gate_kind": wi.get("status", ""),
        },
        "tmux_process": {
            "live_status": "alive" if is_live else "stopped",
        },
        "needs_human": nh_evidence,
        "repair_progress": {
            "present": bool(repair_progress),
            "items": rp_items,
        },
        "chain_log": {},
        "active_step_heartbeat": {},
        "sibling_sessions": [],
        "ignored_artifacts": [],
        "stale_evidence": [],
        "rationale": ["resolver observe via status_snapshot"],
        "diagnostic_codes": {
            "escalation_label": nh.get("escalation_label", ""),
            "event_signature_labels": [],
            "discord_status": "",
            "retry_strategy": "",
        },
    }


def _build_session_entry(
    marker: Mapping[str, Any],
    *,
    marker_dir: Path,
    repair_data_dir: Path,
    watchdog_by_session: Mapping[str, Mapping[str, Any]],
    watchdog_report_path: Path,
    now: datetime,
    liveness_probe: LivenessProbe,
) -> dict[str, Any]:
    session = str(marker.get("session") or "")
    workspace = _as_path(marker.get("workspace"))
    remote_spec = str(marker.get("remote_spec") or "")
    run_kind = str(marker.get("run_kind") or "chain")
    plan_name = str(marker.get("plan_name") or "")

    marker_path = Path(marker.get("_marker_path") or (marker_dir / f"{session}.json"))
    chain_health = _load_json(marker_dir / f"{session}.chain-health.progress.json")
    repair_progress = _load_json(marker_dir / f"{session}.repair-progress.json")
    needs_human = _load_json(repair_data_dir / f"{session}.needs-human.json")
    watchdog_item = watchdog_by_session.get(session, {})

    chain_complete = bool(chain_health.get("chain_complete")) if chain_health else False
    completed_count = chain_health.get("completed_count") if chain_health else None
    milestone_count = chain_health.get("milestone_count") if chain_health else None
    current_plan = (
        (chain_health.get("current_plan_name") if chain_health else None)
        or plan_name
        or None
    )
    latest_activity = _latest_activity(chain_health, marker)
    plan_state = _load_current_plan_state(workspace, str(current_plan or ""))
    liveness = _augment_liveness_with_plan_state(
        _safe_liveness(liveness_probe, marker),
        chain_health=chain_health,
        plan_state=plan_state,
    )
    superseding_sibling = _find_superseding_sibling(
        marker,
        marker_dir=marker_dir,
        liveness_probe=liveness_probe,
    )

    canonical_run_state: CanonicalRunState | None = None
    canonical_state: str | None = None
    canonical_reason: str | None = None
    canonical_human_required: bool | None = None
    canonical_human_gate: str | None = None
    canonical_resolver_dict: dict[str, Any] | None = None
    try:
        resolver_evidence = _build_resolver_evidence(
            chain_health=chain_health,
            needs_human=needs_human,
            repair_progress=repair_progress,
            watchdog_item=watchdog_item,
            liveness=liveness,
            chain_complete=chain_complete,
        )
        canonical_run_state = resolve_run_state(resolver_evidence)
        if resolver_observe_enabled():
            canonical_state = canonical_run_state.canonical_state.name
            canonical_reason = canonical_run_state.reason
            canonical_human_required = canonical_run_state.human_required
            canonical_human_gate = (
                canonical_run_state.human_gate.name if canonical_run_state.human_gate else None
            )
            canonical_resolver_dict = canonical_run_state.to_dict()
    except Exception:
        # Resolver failure must never affect the legacy snapshot output.
        canonical_run_state = None
        canonical_resolver_dict = None

    event_plan_dir = _derive_status_event_plan_dir(
        workspace=workspace,
        current_plan=str(current_plan or ""),
        marker_dir=marker_dir,
        session=session,
    )
    stored_pr_number = chain_health.get("pr_number") if chain_health else None
    stored_pr_state = chain_health.get("pr_state") if chain_health else None
    live_pr_state = _probe_live_pr_state(workspace, stored_pr_number)
    pr_number = live_pr_state.get("pr_number") if live_pr_state.get("available") else stored_pr_number
    pr_state = live_pr_state.get("state") if live_pr_state.get("available") else stored_pr_state

    status, operator_next = _classify_session(
        session=session,
        workspace=workspace,
        remote_spec=remote_spec,
        chain_health=chain_health,
        chain_complete=chain_complete,
        needs_human=needs_human,
        repair_progress=repair_progress,
        watchdog_item=watchdog_item,
        liveness=liveness,
        superseding_sibling=superseding_sibling,
        latest_activity_dt=_parse_iso(latest_activity),
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        current_plan=str(current_plan or ""),
        plan_state=plan_state,
        now=now,
        canonical_run_state=canonical_run_state,
        event_plan_dir=event_plan_dir,
    )

    entry: dict[str, Any] = {
        "session": session,
        "display_name": session,
        "workspace": str(workspace) if workspace else "",
        "spec": remote_spec,
        "run_kind": run_kind,
        "status": status,
        "should_run": status not in {"complete"},
        "tmux": liveness.get("tmux", False),
        "process": liveness.get("process", False),
        "watchdog": _watchdog_status(watchdog_item, chain_complete),
        "repairing": status == "repairing",
        "current_plan": current_plan,
        "completed_count": completed_count,
        "milestone_count": milestone_count,
        "chain_complete": chain_complete,
        "progress": _session_progress(
            completed_count=completed_count,
            milestone_count=milestone_count,
            current_plan=current_plan,
            complete=chain_complete,
        ),
        "pr_number": pr_number,
        "pr_state": pr_state,
        "latest_activity": latest_activity,
        "operator_next": operator_next,
        "evidence": {
            "marker": str(marker_path),
            "chain_health": str(marker_dir / f"{session}.chain-health.progress.json"),
            "watchdog_report": str(watchdog_report_path),
            "needs_human": (
                str(repair_data_dir / f"{session}.needs-human.json") if needs_human else None
            ),
            "superseded_by": superseding_sibling,
        },
    }

    # Attach canonical resolver fields when observe is enabled and the resolver
    # produced a result.  These are flat keys so callers don't need to drill into
    # a nested object, but they are also self-contained in canonical_resolver_dict
    # for consumers that want the full structured result.
    if canonical_resolver_dict is not None:
        entry["canonical_state"] = canonical_state
        entry["canonical_reason"] = canonical_reason
        entry["canonical_human_required"] = canonical_human_required
        entry["canonical_human_gate"] = canonical_human_gate
        entry["canonical_resolver"] = canonical_resolver_dict

    return entry


def _classify_session(
    *,
    session: str,
    workspace: Path | None,
    remote_spec: str,
    chain_health: Mapping[str, Any],
    chain_complete: bool,
    needs_human: Mapping[str, Any],
    repair_progress: Mapping[str, Any],
    watchdog_item: Mapping[str, Any],
    liveness: Mapping[str, bool],
    superseding_sibling: str | None,
    latest_activity_dt: datetime | None,
    marker_dir: Path,
    repair_data_dir: Path,
    current_plan: str,
    plan_state: Mapping[str, Any] | None,
    now: datetime,
    canonical_run_state: CanonicalRunState | None,
    event_plan_dir: Path,
) -> tuple[SessionStatus, str]:
    legacy_status, legacy_reason = _classify_session_legacy(
        session=session,
        workspace=workspace,
        remote_spec=remote_spec,
        chain_health=chain_health,
        chain_complete=chain_complete,
        needs_human=needs_human,
        repair_progress=repair_progress,
        watchdog_item=watchdog_item,
        liveness=liveness,
        superseding_sibling=superseding_sibling,
        latest_activity_dt=latest_activity_dt,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        current_plan=current_plan,
        plan_state=plan_state,
        now=now,
    )
    canonical_status = _canonical_session_status(canonical_run_state)
    if canonical_status is not None:
        if canonical_status != legacy_status:
            _emit_status_drift_detected(
                event_plan_dir=event_plan_dir,
                canonical_run_state=canonical_run_state,
                canonical_status=canonical_status,
                legacy_status=legacy_status,
                session=session,
                workspace=workspace,
                current_plan=current_plan,
            )
        return canonical_status, legacy_reason
    return legacy_status, legacy_reason


def _classify_session_legacy(
    *,
    session: str,
    workspace: Path | None,
    remote_spec: str,
    chain_health: Mapping[str, Any],
    chain_complete: bool,
    needs_human: Mapping[str, Any],
    repair_progress: Mapping[str, Any],
    watchdog_item: Mapping[str, Any],
    liveness: Mapping[str, bool],
    superseding_sibling: str | None,
    latest_activity_dt: datetime | None,
    marker_dir: Path,
    repair_data_dir: Path,
    current_plan: str,
    plan_state: Mapping[str, Any] | None,
    now: datetime,
) -> tuple[SessionStatus, str]:
    # Structural problems first: a session we cannot reason about is attention.
    if not session:
        return "attention", "marker has no session name"
    if workspace is None or not workspace.exists():
        return "attention", "workspace missing or unreadable"
    if chain_health is None and not remote_spec and not _is_plan_kind_marker(workspace):
        return "attention", "no chain-health snapshot and no remote spec"

    if superseding_sibling and not (liveness.get("tmux") or liveness.get("process")):
        return (
            "complete",
            f"superseded by sibling session {superseding_sibling}; no runner expected",
        )

    # A spec inside the session workspace is canonical durable input; if that
    # file is gone, old chain-health and needs-human sidecars are stale evidence
    # and must not keep the session classified as a live blocker. Specs outside
    # the workspace (placeholders, legacy) never invalidate a session.
    if _canonical_spec_missing(workspace, remote_spec):
        return "attention", "spec missing or unreadable"

    # A current needs-human sidecar is ground truth for active work. A complete
    # chain with no active plan has no live repair target, so stale repair
    # exhaustion markers from earlier ticks must not keep it blocked forever.
    if _is_current_needs_human(
        session=session,
        needs_human=needs_human,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
        current_plan=current_plan,
        chain_complete=chain_complete,
        latest_activity_dt=latest_activity_dt,
    ):
        return "blocked", _needs_human_reason(needs_human)

    # The watchdog report is the authority on runner truth: it reads the
    # authoritative chain state every tick. The chain-health sidecar can freeze
    # at the last non-complete snapshot for a finished chain (it stops being
    # refreshed once the session goes idle), so defer to the watchdog's verdict
    # when it has already classified the session. Without this the snapshot
    # reports done chains as stalled attention, disagreeing with the watchdog.
    wd_status = str(watchdog_item.get("status") or "").lower()
    if wd_status in {"complete", "completed"}:
        return "complete", "watchdog reports chain complete"

    # Terminal success is the strongest signal and beats stale plan failures.
    if chain_complete:
        return "complete", "chain complete; no runner expected"

    # Active automated repair takes precedence over plain stalled/running when
    # the chain is not advancing on its own.
    if _is_repair_active(repair_progress, repair_data_dir, session, now):
        return "repairing", "automated repair dispatched for this session"

    # A live process plus an unchanged repairable failure receipt is custody, not
    # running: the failure has not been cleared, so report it as attention so the
    # operator can see the repair system is stuck. Checked before any
    # liveness-based ``running`` return on purpose.
    if _has_current_repairable_failure(plan_state):
        return "attention", "alive_but_failed: current repairable failure receipt remains"

    if liveness.get("tmux") or liveness.get("process"):
        return "running", "live runner process observed"

    if latest_activity_dt is not None and (now - latest_activity_dt).total_seconds() <= STALE_ACTIVITY_S:
        return "running", "recent plan/chain activity"

    # Not complete, not blocked, not under repair, not live, not recent. That is
    # exactly the "should be working but is not" case the watchdog escalates.
    if latest_activity_dt is None:
        return "attention", "no activity timestamp; cannot confirm liveness"
    return "attention", f"stalled (no live process, last activity {_age_s(latest_activity_dt, now)}s ago)"


def _canonical_session_status(canonical_run_state: CanonicalRunState | None) -> SessionStatus | None:
    if canonical_run_state is None:
        return None
    return _CANONICAL_STATUS_MAP.get(canonical_run_state.canonical_state)


def _derive_status_event_plan_dir(
    *,
    workspace: Path | None,
    current_plan: str,
    marker_dir: Path,
    session: str,
) -> Path:
    plan_name = current_plan.strip()
    if workspace is not None and plan_name:
        return workspace / ".megaplan" / "plans" / plan_name
    return marker_dir / ".status-events" / (session or "_unknown-session")


def _emit_status_drift_detected(
    *,
    event_plan_dir: Path,
    canonical_run_state: CanonicalRunState | None,
    canonical_status: SessionStatus,
    legacy_status: SessionStatus,
    session: str,
    workspace: Path | None,
    current_plan: str,
) -> None:
    if canonical_run_state is None:
        return
    payload = {
        "what": "status_snapshot.session_status",
        "expected": canonical_status,
        "actual": legacy_status,
        "canonical_state": canonical_run_state.canonical_state.name,
        "legacy_label": legacy_status,
        "stale_sources": list(canonical_run_state.stale_sources),
        "session": session,
        "workspace": str(workspace) if workspace is not None else "",
        "current_plan": current_plan,
    }
    try:
        emit(EventKind.DRIFT_DETECTED, event_plan_dir, payload=payload)
    except Exception:
        return


def _canonical_spec_missing(workspace: Path | None, remote_spec: str) -> bool:
    """True when a chain marker points at a spec that should exist locally.

    Many tests and some legacy markers carry placeholder specs outside the
    workspace. Those are not enough to invalidate a session. A spec inside the
    session workspace is canonical durable input, though; if that file is gone,
    old chain-health and needs-human sidecars are stale evidence and must not
    keep the session classified as a live blocker.
    """
    if workspace is None or not remote_spec:
        return False
    try:
        spec_path = Path(remote_spec)
        workspace_resolved = workspace.resolve()
        spec_resolved = spec_path.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False
    if spec_resolved != workspace_resolved and workspace_resolved not in spec_resolved.parents:
        return False
    return not spec_path.exists()


# --- source file readers ---------------------------------------------------


def _load_watchdog_report(
    primary: Path, fallback: Path
) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]], list[str]]:
    path = primary if primary.exists() else (fallback if fallback.exists() else None)
    if path is None:
        return None, {}, [f"watchdog report missing (looked for {primary}, {fallback})"]
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, {}, [f"watchdog report unreadable at {path}: {exc.__class__.__name__}"]
    if not isinstance(report, dict):
        return None, {}, [f"watchdog report at {path} is not a JSON object"]
    by_session: dict[str, dict[str, Any]] = {}
    for section in ("items", "issues"):
        items = report.get(section)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("session")
            if isinstance(name, str) and name:
                # Keep the most informative item per session.
                existing = by_session.get(name)
                if existing is None or _item_signal_rank(item) > _item_signal_rank(existing):
                    by_session[name] = item
    return report, by_session, []


def _item_signal_rank(item: Mapping[str, Any]) -> int:
    """Rank watchdog items so the most actionable one wins per session."""
    status = str(item.get("status") or "")
    order = [
        "needs_human",
        "restarted",
        "reaped",
        "sync_dirty",
        "sync_failed",
        "alive",
        "skipped",
        "synced",
        "complete",
        "completed",
    ]
    try:
        return len(order) - order.index(status)
    except ValueError:
        return -1


def _load_session_markers(marker_dir: Path) -> list[dict[str, Any]]:
    if not marker_dir.exists():
        return []
    markers: list[dict[str, Any]] = []
    for path in sorted(marker_dir.glob("*.json")):
        if not is_canonical_session_marker_path(path):
            continue
        payload = _load_json(path)
        if not isinstance(payload, dict) or not payload.get("session"):
            continue
        payload["_marker_path"] = str(path)
        markers.append(payload)
    return markers


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _find_superseding_sibling(
    marker: Mapping[str, Any],
    *,
    marker_dir: Path,
    liveness_probe: LivenessProbe,
) -> str | None:
    """Return sibling evidence that makes this stale marker non-actionable.

    The watchdog wrapper has the same operational rule for stopped sessions:
    when another canonical marker in the same workspace owns the live work, the
    older marker is superseded rather than relaunched or escalated. The snapshot
    needs that reconciliation too, otherwise stale needs-human sidecars from a
    parent wrapper continue to appear as active blocked work after a child chain
    has taken over or completed.
    """

    session = str(marker.get("session") or "")
    workspace = str(marker.get("workspace") or "")
    if not session or not workspace:
        return None

    for other in _load_session_markers(marker_dir):
        other_session = str(other.get("session") or "")
        other_workspace = str(other.get("workspace") or "")
        if not other_session or other_session == session or other_workspace != workspace:
            continue
        other_remote_spec = str(other.get("remote_spec") or "")
        if not other_remote_spec:
            continue

        other_health = _load_json(marker_dir / f"{other_session}.chain-health.progress.json")
        if isinstance(other_health, Mapping) and bool(other_health.get("chain_complete")):
            return f"{other_session}:complete"

        other_liveness = _safe_liveness(liveness_probe, other)
        if other_liveness.get("tmux") or other_liveness.get("process"):
            return f"{other_session}:alive"

    return None


# --- classification helpers ------------------------------------------------



def _is_current_needs_human(
    *,
    session: str,
    needs_human: Mapping[str, Any] | None,
    marker_dir: Path,
    repair_data_dir: Path,
    current_plan: str,
    chain_complete: bool,
    latest_activity_dt: datetime | None,
) -> bool:
    if not _is_needs_human(needs_human):
        return False

    if chain_complete and not current_plan:
        return False

    recorded_at = _parse_iso(str(needs_human.get("recorded_at") or ""))
    if chain_complete and recorded_at is not None and latest_activity_dt is not None:
        if recorded_at <= latest_activity_dt:
            return False

    try:
        classification = classify_needs_human_blocker(
            session,
            current_plan=current_plan,
            marker_dir=marker_dir,
            repair_data_dir=repair_data_dir,
            needs_human_payload=needs_human,
        )
    except Exception:
        return True
    return classification.should_block

def _is_needs_human(needs_human: Mapping[str, Any] | None) -> bool:
    return bool(needs_human)


def _needs_human_reason(needs_human: Mapping[str, Any]) -> str:
    summary = needs_human.get("summary") if isinstance(needs_human, Mapping) else None
    if isinstance(summary, str) and summary:
        first = summary.splitlines()[0]
        return f"awaiting human action: {first[:160]}"
    return "awaiting human action"


def _is_repair_active(
    repair_progress: Mapping[str, Any] | None,
    repair_data_dir: Path,
    session: str,
    now: datetime,
) -> bool:
    if not isinstance(repair_progress, Mapping) or not repair_progress:
        return False
    recorded_at = _parse_iso(repair_progress.get("updated_at") or repair_progress.get("ts"))
    if recorded_at is None:
        # A repair-progress marker without a timestamp still means a repair ran;
        # treat it as active only if recent repair-data exists alongside.
        repair_data = _load_json(repair_data_dir / f"{session}.repair-data.json")
        return bool(repair_data)
    age = (now - recorded_at).total_seconds()
    return age <= REPAIR_FRESH_S


def _watchdog_status(watchdog_item: Mapping[str, Any], chain_complete: bool) -> str:
    if chain_complete:
        return "complete"
    status = str(watchdog_item.get("status") or "").strip().lower()
    return status or "unknown"


def _load_current_plan_state(workspace: Path | None, current_plan: str) -> dict[str, Any] | None:
    """Load the per-plan ``state.json`` so custody can read its failure receipt."""
    if workspace is None or not current_plan:
        return None
    path = workspace / ".megaplan" / "plans" / current_plan / "state.json"
    loaded = _load_json(path)
    return dict(loaded) if isinstance(loaded, Mapping) and loaded else None


def _has_current_repairable_failure(plan_state: Mapping[str, Any] | None) -> bool:
    """True when the current plan state carries an unresolved repairable failure.

    A live process coexisting with such a receipt is ``alive_but_failed`` custody
    (attention), not ``running``: the failure has not been cleared. ``phase_failed``
    in the execute phase is the open repair case; a finalized/blocked/manual-review
    state with a step/handler failure is the parked-but-unresolved case.
    """
    if not isinstance(plan_state, Mapping) or not plan_state:
        return False
    latest_failure = plan_state.get("latest_failure")
    if not isinstance(latest_failure, Mapping) or not latest_failure:
        return False
    kind = str(latest_failure.get("kind") or "").strip().lower()
    phase = str(latest_failure.get("phase") or "").strip().lower()
    current_state = str(plan_state.get("current_state") or "").strip().lower()
    if kind == "phase_failed" and phase in {"", "execute"}:
        return True
    return current_state in {"blocked", "manual_review", "finalized"} and kind in {
        "phase_failed",
        "step_failed",
        "handler_failed",
    }


def _augment_liveness_with_plan_state(
    liveness: Mapping[str, bool],
    *,
    chain_health: Mapping[str, Any] | None,
    plan_state: Mapping[str, Any] | None,
) -> dict[str, bool]:
    """Augment generic ps/tmux liveness with plan-state + chain-health signals.

    The generic process matcher can miss a manual-phase worker (e.g.
    ``megaplan execute --plan ...``) that the watchdog chain-health and the plan's
    own ``active_step`` already track. This keeps custody honest about which
    processes are truly live without re-implementing a process scanner here.
    """
    augmented = {"tmux": bool(liveness.get("tmux")), "process": bool(liveness.get("process"))}
    if augmented["process"]:
        return augmented

    active_step = plan_state.get("active_step") if isinstance(plan_state, Mapping) else None
    if isinstance(active_step, Mapping):
        pid = _as_int(active_step.get("worker_pid"))
        if pid is not None and _pid_is_live(pid):
            augmented["process"] = True
            return augmented

    # Watchdog chain-health is produced from the same local namespace and can
    # observe an active step even when the generic ps matcher cannot identify a
    # direct manual phase command.
    if chain_health and bool(chain_health.get("plan_has_active_step")) and bool(
        chain_health.get("plan_has_live_activity")
    ):
        augmented["process"] = True
    return augmented


def _pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _latest_activity(chain_health: Mapping[str, Any] | None, marker: Mapping[str, Any]) -> str:
    candidates = []
    if chain_health:
        candidates.append(chain_health.get("updated_at"))
        candidates.append(_iso_from_epoch(chain_health.get("events_mtime")))
    candidates.append(marker.get("started_at"))
    for value in candidates:
        if isinstance(value, (int, float)) and value:
            iso = _iso_from_epoch(value)
            if iso:
                return iso
        if isinstance(value, str) and value:
            return value
    return ""


def _is_plan_kind_marker(workspace: Path | None) -> bool:
    # Plan-kind sessions carry plan_name and need no remote_spec/chain-health.
    return workspace is not None and workspace.exists()


def _safe_liveness(probe: LivenessProbe, marker: Mapping[str, Any]) -> dict[str, bool]:
    try:
        result = probe(marker)
    except Exception:
        return {"tmux": False, "process": False}
    if not isinstance(result, dict):
        return {"tmux": False, "process": False}
    return {
        "tmux": bool(result.get("tmux")),
        "process": bool(result.get("process")),
    }


def default_liveness_probe(marker: Mapping[str, Any]) -> dict[str, bool]:
    """Best-effort tmux + process liveness from the current namespace.

    Swallows all errors so a fixture directory without tmux/ps still classifies
    sessions from file evidence alone. Returns ``{"tmux": bool, "process": bool}``.
    """
    session = str(marker.get("session") or "")
    workspace = str(marker.get("workspace") or "")
    remote_spec = str(marker.get("remote_spec") or "")
    plan_name = str(marker.get("plan_name") or "")

    tmux_alive = False
    if session:
        try:
            proc = subprocess.run(
                ["tmux", "has-session", "-t", session],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            tmux_alive = proc.returncode == 0
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            tmux_alive = False

    process_alive = False
    needles = [value for value in (remote_spec, workspace, plan_name) if value]
    if needles:
        try:
            ps = subprocess.run(
                ["ps", "-eww", "-o", "args="],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            ps = None
        if ps is not None and ps.returncode == 0:
            for line in ps.stdout.splitlines():
                if "arnold_pipelines.megaplan" not in line:
                    continue
                if needles[0] in line and (
                    " chain start" in line or " epic-chain start" in line or " auto " in line
                ):
                    process_alive = True
                    break

    return {"tmux": tmux_alive, "process": process_alive}


def _summarize(sessions: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"running": 0, "blocked": 0, "repairing": 0, "complete": 0, "attention": 0}
    for entry in sessions:
        status = entry.get("status")
        if status in counts:
            counts[status] += 1
    return counts


# --- time helpers ----------------------------------------------------------


def _utcnow() -> datetime:
    # ``datetime.now(timezone.utc)`` with no arg is allowed here (this is the
    # library, not a workflow script). Callers may inject ``now`` for tests.
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_from_epoch(value: object) -> str:
    try:
        epoch = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if epoch <= 0:
        return ""
    return _isoformat(datetime.fromtimestamp(epoch, timezone.utc))


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_s(dt: datetime, now: datetime) -> int:
    return max(0, int((now - dt).total_seconds()))


def _as_path(value: object) -> Path | None:
    if isinstance(value, str) and value.strip():
        return Path(value.strip())
    if isinstance(value, Path):
        return value
    return None
