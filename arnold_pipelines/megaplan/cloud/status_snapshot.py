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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from arnold_pipelines.megaplan.cloud.current_target import resolve_current_target
from arnold_pipelines.megaplan.cloud.human_blockers import classify_needs_human_blocker
from arnold_pipelines.megaplan.cloud.repair_contract import is_success_outcome
from arnold_pipelines.megaplan.cloud.session_markers import (
    is_canonical_session_marker_path,
)
from arnold_pipelines.megaplan.chain.spec import load_spec as load_chain_spec

# --- canonical paths -------------------------------------------------------

DEFAULT_MARKER_DIR = Path("/workspace/.megaplan/cloud-sessions")
DEFAULT_WATCHDOG_REPORT = Path("/workspace/watchdog-report.json")
DEFAULT_FALLBACK_WATCHDOG_REPORT = Path("/workspace/.megaplan/watchdog-report.json")
DEFAULT_STATUS_DIR = Path("/workspace/.megaplan/status")
DEFAULT_SNAPSHOT_PATH = DEFAULT_STATUS_DIR / "cloud-status.json"
DEFAULT_PREVIOUS_SNAPSHOT_PATH = DEFAULT_STATUS_DIR / "cloud-status.previous.json"
DEFAULT_HISTORY_PATH = DEFAULT_STATUS_DIR / "progress-history.jsonl"
DEFAULT_WORKSPACE_ROOT = Path("/workspace")

# Progress-history rotation thresholds. The watchdog appends one compact row per
# sweep; we keep the file bounded so multi-week chains do not grow it unbounded.
HISTORY_TRIM_SIZE_BYTES = 512 * 1024
HISTORY_KEEP_LINES = 2000

STATE_INITIALIZED = "initialized"
PLAN_PROGRESSION_RUNGS: tuple[str, ...] = (
    "prepped",
    "planned",
    "critiqued",
    "gated",
    "finalized",
    "executed",
    "reviewed",
    "done",
)

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


def has_local_markers(marker_dir: Path | None = None) -> bool:
    """True when the canonical cloud-session marker directory is present.

    This is the on-box signal independent of the trust env var: when the marker
    dir exists, a fresh local snapshot can be built from it with no SSH. Unlike
    :func:`is_trusted_container`, this does NOT require
    ``MEGAPLAN_TRUSTED_CONTAINER=1`` — so a resident that lost the env var on a
    manual restart still reads live markers instead of a stale cache (see
    ``docs/arnold/watchdog-snapshot-staleness-fix.md`` P0). The canonical path is
    absolute (``/workspace/.megaplan/cloud-sessions``), so a laptop/CLI checkout
    with only a relative ``.megaplan`` cannot falsely trip it.
    """
    directory = Path(marker_dir) if marker_dir else DEFAULT_MARKER_DIR
    return directory.is_dir()

# A session whose latest activity is older than this is not "running" on
# activity alone; it must have a live process or be under active repair.
STALE_ACTIVITY_S = 30 * 60
# A repair-progress marker older than this no longer counts as "repairing".
REPAIR_FRESH_S = 6 * 60 * 60
CHAIN_HEALTH_STALE_GRACE_S = 5

SessionStatus = str  # one of: running | repairing | blocked | complete | attention
LivenessProbe = Callable[[Mapping[str, Any]], dict[str, bool]]


# --- public API ------------------------------------------------------------


def build_cloud_status_snapshot(
    *,
    marker_dir: Path | None = None,
    watchdog_report_path: Path | None = None,
    repair_data_dir: Path | None = None,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    now: datetime | None = None,
    liveness_probe: LivenessProbe | None = None,
    history_path: Path | str | None = None,
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

    # Enrich each session's progress block with time-series deltas (epic %
    # gained over 1h/5h, epic/plan start times) from the sweep history. Best
    # effort: missing/unreadable history just leaves the deltas absent.
    hist_path = Path(history_path) if history_path else DEFAULT_HISTORY_PATH
    for entry in sessions:
        progress = entry.get("progress")
        if not isinstance(progress, dict):
            continue
        deltas = compute_progress_deltas(
            history_path=hist_path,
            session=entry.get("session"),
            now=now,
            started_at=entry.get("started_at"),
            now_percent=progress.get("percent"),
        )
        if deltas:
            progress.update(deltas)

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
    history_path: Path | str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the snapshot and atomically write it + the previous rotation.

    Convenience entrypoint for the watchdog: one call after each sweep keeps
    ``cloud-status.json`` fresh and appends one row to the progress-history log
    (sweep cadence, not per-resident-turn). Returns the snapshot that was written.
    """
    snapshot = build_cloud_status_snapshot(
        marker_dir=marker_dir,
        watchdog_report_path=watchdog_report_path,
        now=now,
        history_path=history_path,
    )
    write_cloud_status_snapshot(snapshot, path=path, previous_path=previous_path)
    append_progress_history(snapshot, history_path or DEFAULT_HISTORY_PATH, now=now)
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
    # A sanitized stale snapshot (P1) carries a stale_banner and intentionally
    # empty buckets; surface it as degraded with the banner so consumers never
    # read "0 running" off a frozen view as "nothing is running".
    if snapshot.get("stale_banner"):
        return {
            "degraded": True,
            "reason": snapshot.get("stale_reason") or "snapshot stale",
            "stale_banner": snapshot.get("stale_banner"),
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


def append_progress_history(
    snapshot: Mapping[str, Any] | None,
    path: Path | str = DEFAULT_HISTORY_PATH,
    *,
    now: datetime | None = None,
) -> None:
    """Append one compact progress row per sweep to the history log.

    The watchdog calls this once per sweep (via :func:`build_and_write_snapshot`)
    so the file grows on sweep cadence — not on every resident turn. Each row
    records the epic %, in-flight plan %, plan state, and current plan for every
    session carrying a progress block. The resident later reads this series to
    answer "how much has the epic advanced in the past hour?".

    Best-effort and never raises: a write failure simply means one missed
    sample. The file is trimmed to ``HISTORY_KEEP_LINES`` once it exceeds
    ``HISTORY_TRIM_SIZE_BYTES``.
    """
    if not snapshot or not isinstance(snapshot, Mapping):
        return
    now = now or _utcnow()
    samples: list[dict[str, Any]] = []
    for entry in snapshot.get("sessions") or []:
        if not isinstance(entry, Mapping):
            continue
        progress = entry.get("progress")
        if not isinstance(progress, Mapping):
            continue
        samples.append(
            {
                "session": entry.get("session"),
                "epic_percent": progress.get("percent"),
                "plan_percent": progress.get("plan_percent"),
                "plan_state": progress.get("plan_state"),
                "current_plan": progress.get("current_plan"),
            }
        )
    if not samples:
        return
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"ts": _isoformat(now), "sessions": samples}, separators=(",", ":")) + "\n"
            )
    except OSError:
        return
    _maybe_trim_history(path)


def _maybe_trim_history(path: Path) -> None:
    """Bound the history log: once it exceeds the size threshold, keep the tail."""
    try:
        if path.stat().st_size < HISTORY_TRIM_SIZE_BYTES:
            return
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) <= HISTORY_KEEP_LINES:
        return
    tail = lines[-HISTORY_KEEP_LINES:]
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text("\n".join(tail) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


def _load_progress_history(path: Path | str) -> list[dict[str, Any]]:
    """Read the progress-history log as a list of parsed rows."""
    path = Path(path)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def compute_progress_deltas(
    *,
    history_path: Path | str = DEFAULT_HISTORY_PATH,
    session: str | None = None,
    now: datetime | None = None,
    started_at: str | None = None,
    now_percent: Any = None,
) -> dict[str, Any] | None:
    """Compute time-series progress deltas for one session from sweep history.

    Returns ``epic_delta_1h`` / ``epic_delta_5h`` (percentage points the epic
    gained over the last 1h / 5h), plus ``epic_started_at`` and
    ``plan_started_at``. Deltas are reported only when a history sample exists
    from at least that far back — a young epic honestly shows ``None`` until the
    window fills. Returns ``None`` when there is no history for the session.

    ``epic_started_at`` prefers the session marker's ``started_at`` (true chain
    start) and falls back to the first history sample. ``plan_started_at`` is the
    timestamp of the most recent transition into the current plan.
    """
    if not session:
        return None
    now = now or _utcnow()
    rows = _load_progress_history(history_path)
    if not rows:
        return None
    # Sorted timeline of (ts, epic_percent, current_plan, plan_state) for this session.
    points: list[tuple[datetime, Any, Any, Any]] = []
    for row in rows:
        row_dt = _parse_iso(row.get("ts"))
        if row_dt is None:
            continue
        for sample in row.get("sessions") or []:
            if not isinstance(sample, dict) or sample.get("session") != session:
                continue
            points.append(
                (row_dt, sample.get("epic_percent"), sample.get("current_plan"), sample.get("plan_state"))
            )
            break
    if not points:
        return None
    points.sort(key=lambda item: item[0])

    current_percent = now_percent
    if current_percent is None:
        current_percent = points[-1][1]

    def _percent_at_or_before(target: datetime) -> int | None:
        """Epic % at the latest sample at or before ``target`` (None if none)."""
        best: int | None = None
        for sample_dt, percent, _plan, _state in points:
            if sample_dt > target:
                break
            value = _as_int(percent)
            if value is not None:
                best = value
        return best

    def _delta(window_s: int) -> int | None:
        if current_percent is None:
            return None
        reference = _percent_at_or_before(now - timedelta(seconds=window_s))
        if reference is None:
            return None
        return _as_int(current_percent) - reference

    def _stages_advanced(window_s: int) -> list[str]:
        """Ladder rungs newly reached in the window, for "advanced N stages" color.

        Compares the highest ladder rung held at/before the window start against
        rungs first seen inside the window. Off-ladder states (authority_divergence,
        blocked, …) are skipped so transient sub-states don't masquerade as progress.
        """
        window_start = now - timedelta(seconds=window_s)
        prior_idx = -1
        for sample_dt, _pct, _plan, state in points:
            if sample_dt > window_start:
                break
            idx = _ladder_index(state)
            if idx >= 0:
                prior_idx = idx
        reached: list[str] = []
        seen: set[int] = set()
        for sample_dt, _pct, _plan, state in points:
            if sample_dt <= window_start:
                continue
            idx = _ladder_index(state)
            if idx < 0 or idx <= prior_idx or idx in seen:
                continue
            reached.append(PLAN_PROGRESSION_RUNGS[idx])
            seen.add(idx)
        return reached

    # plan_started_at: most recent transition into the current plan.
    current_plan = points[-1][2]
    plan_started_at: str | None = None
    prev_plan: Any = None
    for sample_dt, _percent, plan, _state in points:
        if plan != prev_plan:
            if plan is not None and plan == current_plan:
                plan_started_at = _isoformat(sample_dt)
            prev_plan = plan

    epic_started_at = started_at or _isoformat(points[0][0])
    return {
        "epic_delta_1h": _delta(3600),
        "epic_delta_5h": _delta(5 * 3600),
        "stage_changes_1h": _stages_advanced(3600),
        "epic_started_at": epic_started_at,
        "plan_started_at": plan_started_at,
    }


def _ladder_index(plan_state: Any) -> int:
    """Index of a state in PLAN_PROGRESSION_RUNGS, or -1 if off-ladder/empty."""
    if not plan_state:
        return -1
    try:
        return PLAN_PROGRESSION_RUNGS.index(str(plan_state).strip().lower())
    except ValueError:
        return -1


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


def _plan_stage_percent(plan_state: str) -> int | None:
    """Estimate a coarse "% through the in-flight plan" from its lifecycle state.

    A plan advances through a fixed ladder of stages (``PLAN_PROGRESSION_RUNGS``);
    its recorded ``current_state`` (exposed via chain-health ``last_state``) tells
    us how many it has completed. We map that to completed-stages / total-stages.
    ``initialized`` is 0%; an off-ladder state (blocked / failed / awaiting_* /
    tiebreaker_*) is not percentage-able, so we return ``None`` and let the caller
    surface the raw state label instead. This is a deliberately coarse stage
    estimate, not exact sub-plan progress — stages are treated as equal-weight.
    """
    if not plan_state:
        return None
    if plan_state == STATE_INITIALIZED:
        return 0
    try:
        index = PLAN_PROGRESSION_RUNGS.index(plan_state)
    except ValueError:
        return None
    return round((index + 1) / len(PLAN_PROGRESSION_RUNGS) * 100)


def _session_progress(
    *,
    completed_count: Any,
    milestone_count: Any,
    current_plan: str | None,
    complete: bool,
    plan_state: str | None = None,
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
    (carrying ``current_plan``), and the rest are pending.

    For the in-flight sprint we additionally estimate a per-plan percent
    (``plan_percent``) from ``plan_state`` via :func:`_plan_stage_percent`, plus
    the raw ``plan_state`` label. Both are omitted when there is no in-flight
    plan or no recorded state, so the progress block stays clean.

    The headline ``percent`` is the epic progress **with the in-flight plan's
    stage fraction folded in** — ``(completed + plan_percent/100) / total`` — so
    it advances as the current plan progresses rather than freezing between
    milestones. Without an in-flight plan-stage signal it falls back to plain
    ``completed / total``.
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

    # The in-flight plan's stage estimate is only meaningful while a sprint is
    # actually in progress (chain not complete, milestones remain).
    has_in_flight = (not complete) and done < total
    plan_state_norm = str(plan_state).strip().lower() if plan_state else ""
    plan_percent = _plan_stage_percent(plan_state_norm) if has_in_flight else None

    # Epic % folds the in-flight plan's stage fraction in, so the headline moves
    # as the current plan advances instead of freezing between milestones. With
    # no in-flight plan (complete) or no plan-stage signal, it is plain
    # completed-milestones / total. The plan fraction counts as up to one
    # milestone's worth of credit.
    if complete:
        percent = 100
    elif plan_percent is not None:
        percent = round((done + plan_percent / 100) / total * 100)
    else:
        percent = round(done / total * 100)

    sprints: list[dict[str, Any]] = []
    for index in range(1, total + 1):
        if complete or index <= done:
            sprints.append({"sprint": f"s{index}", "status": "done"})
        elif index == done + 1:
            sprint: dict[str, Any] = {"sprint": f"s{index}", "status": "in_progress"}
            if plan:
                sprint["plan"] = plan
            if plan_state_norm:
                sprint["plan_state"] = plan_state_norm
            if plan_percent is not None:
                sprint["plan_percent"] = plan_percent
            sprints.append(sprint)
        else:
            sprints.append({"sprint": f"s{index}", "status": "pending"})

    progress: dict[str, Any] = {
        "completed_milestones": done,
        "total_milestones": total,
        "percent": percent,
        "complete": bool(complete),
        "current_plan": plan,
        "sprints": sprints,
    }
    if has_in_flight and plan_state_norm:
        progress["plan_state"] = plan_state_norm
    if plan_percent is not None:
        progress["plan_percent"] = plan_percent
    return progress


def _overlay_newer_chain_state(
    chain_health: Mapping[str, Any] | None,
    *,
    workspace: Path | None,
    remote_spec: str,
) -> Mapping[str, Any] | None:
    state_path, chain_state = _load_latest_chain_state(workspace)
    if state_path is None or not isinstance(chain_state, Mapping):
        return chain_health

    health_mtime = _chain_health_mtime(chain_health)
    try:
        state_mtime = state_path.stat().st_mtime
    except OSError:
        return chain_health
    if health_mtime is not None and state_mtime <= health_mtime + CHAIN_HEALTH_STALE_GRACE_S:
        return chain_health

    milestone_count = _chain_milestone_count(remote_spec)
    if milestone_count is None and isinstance(chain_health, Mapping):
        milestone_count = _as_int(chain_health.get("milestone_count"))
    completed = chain_state.get("completed")
    completed_len = len(completed) if isinstance(completed, list) else 0
    current_index = _as_int(chain_state.get("current_milestone_index"))
    last_state = str(chain_state.get("last_state") or "").strip()
    chain_complete = _chain_state_complete(
        last_state=last_state,
        completed_len=completed_len,
        milestone_count=milestone_count,
    )
    custody_mismatch = bool(
        last_state.lower() in {"done", "complete", "completed"}
        and milestone_count is not None
        and completed_len < milestone_count
    )

    merged: dict[str, Any] = dict(chain_health or {})
    merged.update(
        {
            "chain_complete": chain_complete,
            "completed_count": completed_len,
            "current_milestone_index": current_index,
            "custody_mismatch": custody_mismatch,
            "last_state": last_state,
            "updated_at": _isoformat(datetime.fromtimestamp(state_mtime, timezone.utc)),
            "source": "chain_state",
            "chain_state_path": str(state_path),
        }
    )
    if milestone_count is not None:
        merged["milestone_count"] = milestone_count
    if chain_complete:
        merged["current_plan_name"] = ""
    elif isinstance(chain_state.get("current_plan_name"), str):
        merged["current_plan_name"] = chain_state.get("current_plan_name")
    completed_pr = completed[-1] if isinstance(completed, list) and completed else {}
    if chain_state.get("pr_number") is not None:
        merged["pr_number"] = chain_state.get("pr_number")
    elif isinstance(completed_pr, Mapping) and completed_pr.get("pr_number") is not None:
        merged["pr_number"] = completed_pr.get("pr_number")
    if chain_state.get("pr_state") is not None:
        merged["pr_state"] = chain_state.get("pr_state")
    elif isinstance(completed_pr, Mapping) and completed_pr.get("pr_state") is not None:
        merged["pr_state"] = completed_pr.get("pr_state")
    return merged


def _load_latest_chain_state(workspace: Path | None) -> tuple[Path | None, Mapping[str, Any] | None]:
    if workspace is None:
        return None, None
    chain_dir = workspace / ".megaplan" / "plans" / ".chains"
    try:
        candidates = [p for p in chain_dir.glob("*.json") if p.is_file()]
    except OSError:
        return None, None
    if not candidates:
        return None, None
    path = max(candidates, key=lambda p: p.stat().st_mtime)
    payload = _load_json(path)
    if not isinstance(payload, Mapping):
        return None, None
    return path, payload


def _chain_health_mtime(chain_health: Mapping[str, Any] | None) -> float | None:
    if not chain_health:
        return None
    updated = _parse_iso(chain_health.get("updated_at"))
    return updated.timestamp() if updated is not None else None


def _chain_milestone_count(remote_spec: str) -> int | None:
    if not remote_spec:
        return None
    try:
        spec_path = Path(remote_spec)
        if not spec_path.exists():
            return None
        return len(load_chain_spec(spec_path).milestones)
    except Exception:
        return None


def _chain_state_complete(
    *,
    last_state: str,
    completed_len: int,
    milestone_count: int | None,
) -> bool:
    if last_state.strip().lower() not in {"done", "complete", "completed"}:
        return False
    if milestone_count is None:
        return True
    return completed_len >= milestone_count


# --- per-session classification -------------------------------------------


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
    chain_health = _overlay_newer_chain_state(
        chain_health,
        workspace=workspace,
        remote_spec=remote_spec,
    )
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
    try:
        current_target_record = resolve_current_target(
            session,
            marker_dir=marker_dir,
            repair_data_dir=repair_data_dir,
        )
    except Exception:
        current_target_record = {}
    current_refs = (
        current_target_record.get("current_refs")
        if isinstance(current_target_record, Mapping)
        else None
    )
    if isinstance(current_refs, Mapping):
        resolved_current_plan = current_refs.get("current_plan_name")
        if isinstance(resolved_current_plan, str) and resolved_current_plan.strip():
            current_plan = resolved_current_plan.strip()
    # Plan lifecycle state for the per-plan stage %. Prefer the plan's own
    # ``current_state`` (from state.json): the chain-health ``last_state`` can be
    # a transient execute sub-state (e.g. ``authority_divergence``, ``error``)
    # that sits off the progression ladder and would under-report the plan's
    # position. Fall back to last_state when state.json is unavailable.
    plan_state_doc = _load_current_plan_state(workspace, str(current_plan or ""))
    plan_current_state = (
        str(plan_state_doc.get("current_state") or "").strip().lower()
        if isinstance(plan_state_doc, Mapping)
        else ""
    )
    plan_state_label = plan_current_state or (
        chain_health.get("last_state") if chain_health else None
    )
    if isinstance(chain_health, Mapping) and chain_health.get("custody_mismatch"):
        plan_state_label = None
    latest_activity = _latest_activity(chain_health, marker, plan_state_doc)
    liveness = _augment_liveness_with_plan_state(
        _safe_liveness(liveness_probe, marker),
        chain_health=chain_health,
        plan_state=plan_state_doc,
    )
    superseding_sibling = _find_superseding_sibling(
        marker,
        marker_dir=marker_dir,
        liveness_probe=liveness_probe,
    )

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
        plan_state=plan_state_doc,
        now=now,
    )

    return {
        "session": session,
        "display_name": session,
        "workspace": str(workspace) if workspace else "",
        "spec": remote_spec,
        "run_kind": run_kind,
        "started_at": marker.get("started_at"),
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
            plan_state=plan_state_label,
        ),
        "pr_number": chain_health.get("pr_number") if chain_health else None,
        "pr_state": chain_health.get("pr_state") if chain_health else None,
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

    if _canonical_spec_missing(workspace, remote_spec):
        return "attention", "spec missing or unreadable"

    if isinstance(chain_health, Mapping) and chain_health.get("custody_mismatch"):
        completed = chain_health.get("completed_count")
        total = chain_health.get("milestone_count")
        current_index = chain_health.get("current_milestone_index")
        return (
            "attention",
            "chain custody mismatch: terminal state with "
            f"completed={completed}/{total} current_milestone_index={current_index}",
        )

    # Fresh repair custody is stronger than a needs-human sidecar. Repair loops
    # can leave old needs-human markers in place while a higher layer is already
    # working the case; status consumers should show that as repairing.
    if _is_repair_active(repair_progress, repair_data_dir, session, now):
        return "repairing", "automated repair dispatched for this session"

    # A live runner with activity newer than the needs-human marker means the
    # target has moved since escalation. Do not let that stale marker mask the
    # recovery/retry that is currently executing.
    if _needs_human_superseded_by_live_activity(
        needs_human=needs_human,
        liveness=liveness,
        latest_activity_dt=latest_activity_dt,
    ):
        return "running", "live runner activity supersedes older needs-human marker"

    # A current needs-human sidecar is ground truth for non-repairing active
    # work. A complete chain with no active plan has no live repair target, so
    # stale repair exhaustion markers from earlier ticks must not keep it
    # blocked forever.
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


def _canonical_spec_missing(workspace: Path, remote_spec: str) -> bool:
    """True when a chain marker points at a spec that should exist locally.

    Many tests and some legacy markers carry placeholder specs outside the
    workspace. Those are not enough to invalidate a session. A spec inside the
    session workspace is canonical durable input, though; if that file is gone,
    old chain-health and needs-human sidecars are stale evidence and must not
    keep the session classified as a live blocker.
    """
    if not remote_spec:
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



def _needs_human_superseded_by_live_activity(
    *,
    needs_human: Mapping[str, Any] | None,
    liveness: Mapping[str, bool],
    latest_activity_dt: datetime | None,
) -> bool:
    if not _is_needs_human(needs_human):
        return False
    if not (liveness.get("tmux") or liveness.get("process")):
        return False
    if latest_activity_dt is None:
        return False
    recorded_at = _parse_iso(str(needs_human.get("recorded_at") or ""))
    return recorded_at is not None and latest_activity_dt > recorded_at

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
    repair_data = _load_json(repair_data_dir / f"{session}.repair-data.json")
    if isinstance(repair_data, Mapping):
        outcome = str(repair_data.get("outcome") or "").strip()
        if is_success_outcome(outcome):
            return False
        if str(repair_data.get("completed_at") or "").strip():
            return False
    recorded_at = _parse_iso(repair_progress.get("updated_at") or repair_progress.get("ts"))
    if recorded_at is None:
        # A repair-progress marker without a timestamp still means a repair ran;
        # treat it as active only if recent repair-data exists alongside.
        return bool(repair_data)
    age = (now - recorded_at).total_seconds()
    return age <= REPAIR_FRESH_S


def _watchdog_status(watchdog_item: Mapping[str, Any], chain_complete: bool) -> str:
    if chain_complete:
        return "complete"
    status = str(watchdog_item.get("status") or "").strip().lower()
    return status or "unknown"


def _load_current_plan_state(workspace: Path | None, current_plan: str) -> dict[str, Any] | None:
    if workspace is None or not current_plan:
        return None
    path = workspace / ".megaplan" / "plans" / current_plan / "state.json"
    loaded = _load_json(path)
    return dict(loaded) if isinstance(loaded, Mapping) and loaded else None


def _has_current_repairable_failure(plan_state: Mapping[str, Any] | None) -> bool:
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
    if kind in {"execution_blocked", "blocked_recovery_not_resolved"}:
        return True
    if current_state == "failed" and kind == "no_next_step":
        return True
    return current_state in {"blocked", "manual_review", "finalized", "failed"} and kind in {
        "phase_failed",
        "step_failed",
        "handler_failed",
        "no_next_step",
    }


def _latest_activity(
    chain_health: Mapping[str, Any] | None,
    marker: Mapping[str, Any],
    plan_state: Mapping[str, Any] | None = None,
) -> str:
    candidates: list[datetime] = []
    raw_candidates: list[Any] = []
    if chain_health:
        raw_candidates.append(chain_health.get("updated_at"))
        raw_candidates.append(_iso_from_epoch(chain_health.get("events_mtime")))
    if plan_state:
        active_step = plan_state.get("active_step")
        if isinstance(active_step, Mapping):
            raw_candidates.append(active_step.get("last_activity_at"))
            raw_candidates.append(active_step.get("started_at"))
        raw_candidates.append(plan_state.get("updated_at"))
    raw_candidates.append(marker.get("updated_at"))
    raw_candidates.append(marker.get("started_at"))
    for value in raw_candidates:
        if isinstance(value, (int, float)) and value:
            parsed = _parse_iso(_iso_from_epoch(value))
            if parsed is not None:
                candidates.append(parsed)
        if isinstance(value, str) and value:
            parsed = _parse_iso(value)
            if parsed is not None:
                candidates.append(parsed)
    if candidates:
        return _isoformat(max(candidates))
    return ""


def _augment_liveness_with_plan_state(
    liveness: Mapping[str, bool],
    *,
    chain_health: Mapping[str, Any] | None,
    plan_state: Mapping[str, Any] | None,
) -> dict[str, bool]:
    augmented = {"tmux": bool(liveness.get("tmux")), "process": bool(liveness.get("process"))}
    if augmented["process"]:
        return augmented

    active_step = plan_state.get("active_step") if isinstance(plan_state, Mapping) else None
    if isinstance(active_step, Mapping):
        pid = _as_int(active_step.get("worker_pid"))
        if pid is not None and _pid_is_live(pid):
            augmented["process"] = True
            return augmented

    # Chain-health active-step flags are cached breadcrumbs. They can outlive
    # the worker, so only a live PID or process probe may upgrade liveness.
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
    relaunch_command = str(marker.get("relaunch_command") or "")

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
    marker_pid = _as_int(marker.get("pid"))
    if marker_pid is not None and _pid_is_live(marker_pid):
        process_alive = True
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
                if session and f"watchdog-{session}" in line:
                    process_alive = True
                    break
                if relaunch_command and relaunch_command in line:
                    process_alive = True
                    break
                if "arnold_pipelines.megaplan" in line and any(needle in line for needle in needles) and (
                    " chain start" in line
                    or " epic-chain start" in line
                    or " auto " in line
                    or " execute " in line
                    or " resume " in line
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
