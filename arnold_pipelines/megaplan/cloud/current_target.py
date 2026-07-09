"""Deterministic current-target resolver for cloud repair observe mode."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.cloud.repair_contract import load_json
from arnold_pipelines.megaplan.cloud.feature_flags import resolver_observe_enabled
from arnold_pipelines.megaplan.cloud.session_markers import (
    canonical_sidecar_suffix,
    is_canonical_session_marker_path,
)

_FINGERPRINT_ALGORITHM = "sha256"
_TERMINAL_PLAN_STATES = {"done", "aborted", "cancelled"}

SessionLiveProbe = Callable[[str], bool | None]
PidLiveProbe = Callable[[int], bool | None]

def _pid_is_live(pid: int, probe: PidLiveProbe | None = None) -> bool:
    if pid <= 0:
        return False
    if probe is not None:
        return bool(probe(pid))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True

def _fingerprint(path: Path) -> str:
    """Return hex digest of file content, or empty string when unavailable."""
    try:
        return hashlib.new(_FINGERPRINT_ALGORITHM, path.read_bytes()).hexdigest()
    except (OSError, ValueError):
        return ""


def _mtime(path: Path) -> float:
    """Return st_mtime as float, or 0.0 when unavailable."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _is_terminal_plan_state(value: Any) -> bool:
    return _safe_text(value).lower() in _TERMINAL_PLAN_STATES


def resolve_current_target(
    session: str,
    *,
    marker_dir: str | Path,
    repair_data_dir: str | Path | None = None,
    session_is_live: SessionLiveProbe | None = None,
    pid_is_live: PidLiveProbe | None = None,
) -> dict[str, Any]:
    """Return a stable evidence record for the current repair target.

    When ``ARNOLD_RESOLVER_OBSERVE`` is disabled (set to ``\"0\"``, ``\"false\"``,
    etc.) this function returns a minimal stub record without inspecting any
    filesystem artifacts.  The stub is safe to persist and consumers already
    handle missing evidence gracefully.
    """

    if not resolver_observe_enabled():
        return {
            "schema_version": 1,
            "session": session,
            "target_id": f"{session}:unknown",
            "authoritative_source": "resolver_observe_disabled",
            "target_session": session,
            "current_refs": {},
            "marker": {},
            "plan_state": {},
            "chain_state": {},
            "event_cursors": {},
            "tmux_process": {},
            "needs_human": {},
            "repair_progress": {"present": False, "items": []},
            "chain_log": {},
            "active_step_heartbeat": {},
            "resume_authority_failure": {},
            "sibling_sessions": [],
            "ignored_artifacts": [],
            "stale_evidence": [],
            "rationale": ["resolver observe disabled via ARNOLD_RESOLVER_OBSERVE"],
        }

    markers_root = Path(marker_dir)
    data_root = Path(repair_data_dir) if repair_data_dir is not None else markers_root / "repair-data"
    marker_path = markers_root / f"{session}.json"
    marker = _safe_load_dict(marker_path)
    workspace = _safe_path(marker.get("workspace"))
    remote_spec = _resolve_remote_spec(workspace, marker.get("remote_spec"))
    run_kind = _resolve_run_kind(marker.get("run_kind"), remote_spec)
    marker_plan_name = _safe_plan_name(marker.get("plan_name"))

    chain_state_path = _chain_state_path(workspace, remote_spec, run_kind)
    chain_state = _safe_load_dict(chain_state_path)
    chain_current_plan = _safe_plan_name(chain_state.get("current_plan_name"))

    resolved_plan_name = chain_current_plan or marker_plan_name
    plan_state_path = _plan_state_path(workspace, resolved_plan_name, run_kind)
    plan_state = _safe_load_dict(plan_state_path)
    plan_name = _safe_plan_name(plan_state.get("name")) or resolved_plan_name

    needs_human_path = data_root / f"{session}.needs-human.json"
    needs_human = _safe_load_dict(needs_human_path)
    needs_human_plans = _collect_needs_human_plan_refs(needs_human)
    repair_progress = _collect_sidecar_status(markers_root, session)
    tmux_process = _collect_tmux_process_evidence(marker, session, session_is_live, pid_is_live)
    siblings = _collect_sibling_sessions(
        markers_root,
        session=session,
        workspace=workspace,
        session_is_live=session_is_live,
    )
    event_cursors = _collect_event_cursors(plan_state_path, plan_state)
    chain_log = _collect_chain_log_evidence(workspace, session, run_kind)
    active_step_heartbeat = _collect_active_step_heartbeat(plan_state, pid_is_live=pid_is_live)
    resume_authority_failure = _collect_resume_authority_failure(
        plan_state_path,
        plan_state,
    )

    stale_evidence: list[dict[str, Any]] = []
    rationale: list[str] = []
    ignored_artifacts: list[dict[str, Any]] = []

    if marker_path.exists() and not marker:
        stale_evidence.append(_artifact(kind="invalid_marker_json", path=marker_path))
        rationale.append("marker JSON was unreadable; continuing with partial evidence")
    elif not marker_path.exists():
        stale_evidence.append(_artifact(kind="missing_marker_json", path=marker_path))
        rationale.append("marker JSON missing")

    if remote_spec is None:
        stale_evidence.append(_artifact(kind="spec_missing", path=_safe_text(marker.get("remote_spec"))))
        rationale.append("marker did not provide a usable remote spec")
    if workspace is None:
        stale_evidence.append(_artifact(kind="workspace_missing", path=_safe_text(marker.get("workspace"))))
        rationale.append("marker did not provide a usable workspace")
    elif not workspace.exists():
        stale_evidence.append(_artifact(kind="workspace_missing", path=workspace))
        rationale.append("marker workspace path does not exist")
    if (
        remote_spec is not None
        and run_kind in {"chain", "epic_chain"}
        and not remote_spec.exists()
    ):
        stale_evidence.append(_artifact(kind="spec_missing", path=remote_spec, run_kind=run_kind))
        rationale.append("marker remote spec path does not exist")

    if chain_state_path is not None and not chain_state_path.exists():
        stale_evidence.append(_artifact(kind="missing_chain_state", path=chain_state_path))
    if resolved_plan_name and plan_state_path is not None and not plan_state_path.exists():
        stale_evidence.append(
            _artifact(kind="missing_plan_state", path=plan_state_path, plan_name=resolved_plan_name)
        )

    if needs_human_path.exists() and not needs_human:
        stale_evidence.append(_artifact(kind="invalid_needs_human_json", path=needs_human_path))
    elif needs_human_plans and plan_name and plan_name not in needs_human_plans:
        stale_evidence.append(
            _artifact(
                kind="stale_needs_human_plan_ref",
                path=needs_human_path,
                observed_plans=needs_human_plans,
                current_plan=plan_name,
            )
        )
        rationale.append("needs-human sidecar references an older plan")

    if active_step_heartbeat.get("worker_pid") and not active_step_heartbeat.get("active"):
        stale_evidence.append(
            _artifact(
                kind="stale_active_step_dead_pid",
                path=plan_state_path,
                plan_name=plan_name,
                worker_pid=active_step_heartbeat.get("worker_pid"),
            )
        )
        rationale.append("active_step worker PID is not live")

    plan_current_state = _safe_text(plan_state.get("current_state"))
    chain_last_state = _safe_text(chain_state.get("last_state"))

    if chain_current_plan and marker_plan_name and chain_current_plan != marker_plan_name:
        stale_evidence.append(
            _artifact(
                kind="stale_marker_plan_ref",
                path=marker_path,
                observed_plan=marker_plan_name,
                current_plan=chain_current_plan,
            )
        )
        rationale.append("marker plan reference is older than chain state")
    if (
        run_kind == "chain"
        and plan_name
        and _is_terminal_plan_state(plan_current_state)
        and chain_state_path is not None
        and chain_state_path.exists()
        and chain_last_state.lower() not in _TERMINAL_PLAN_STATES
    ):
        stale_evidence.append(
            _artifact(
                kind="stale_chain_state_after_terminal_plan",
                path=chain_state_path,
                plan_name=plan_name,
                plan_state=plan_current_state,
                chain_last_state=chain_last_state,
            )
        )
        rationale.append("terminal plan state supersedes stale chain state")

    live_siblings = [item for item in siblings if item["live_status"] == "alive"]
    for sibling in siblings:
        if sibling["live_status"] != "alive":
            ignored_artifacts.append(
                {
                    "kind": "inactive_sibling_session",
                    "path": sibling["marker_path"],
                    "session": sibling["session"],
                }
            )

    authoritative_source = "marker"
    target_session = session
    if live_siblings:
        chosen = live_siblings[0]
        authoritative_source = "live_sibling_session"
        target_session = chosen["session"]
        rationale.append(f"live sibling session supersedes current marker: {chosen['session']}")
        stale_evidence.append(
            {
                "kind": "superseded_by_live_sibling",
                "session": chosen["session"],
                "path": chosen["marker_path"],
            }
        )
    elif plan_name and plan_state_path is not None and plan_state_path.exists() and _is_terminal_plan_state(plan_current_state):
        authoritative_source = "plan_state"
    elif chain_current_plan and chain_state_path is not None and chain_state_path.exists():
        authoritative_source = "chain_state"
    elif plan_name and plan_state_path is not None and plan_state_path.exists():
        authoritative_source = "plan_state"

    if tmux_process["live_status"] == "alive":
        rationale.append("session has live tmux/process evidence")
    elif tmux_process["live_status"] == "stopped":
        rationale.append("session tmux/process evidence is stopped")

    if not rationale:
        rationale.append("marker is the only available evidence")

    return {
        "schema_version": 1,
        "session": session,
        "target_id": f"{target_session}:{plan_name or chain_current_plan or run_kind}",
        "authoritative_source": authoritative_source,
        "target_session": target_session,
        "current_refs": {
            "workspace": str(workspace) if workspace is not None else "",
            "run_kind": run_kind,
            "remote_spec": str(remote_spec) if remote_spec is not None else "",
            "marker_plan_name": marker_plan_name,
            "current_plan_name": plan_name,
            "chain_current_plan_name": chain_current_plan,
            "chain_last_state": chain_last_state,
            "plan_current_state": plan_current_state,
        },
        "marker": {
            "path": str(marker_path),
            "present": marker_path.exists(),
            "session": _safe_text(marker.get("session")) or session,
            "workspace": str(workspace) if workspace is not None else "",
            "run_kind": run_kind,
            "remote_spec": str(remote_spec) if remote_spec is not None else "",
            "plan_name": marker_plan_name,
        },
        "plan_state": {
            "path": str(plan_state_path) if plan_state_path is not None else "",
            "present": bool(plan_state_path and plan_state_path.exists()),
            "name": plan_name,
            "current_state": _safe_text(plan_state.get("current_state")),
            "resume_cursor": _stable_mapping(plan_state.get("resume_cursor")),
            "mtime": _mtime(plan_state_path) if plan_state_path is not None else 0.0,
            "fingerprint": _fingerprint(plan_state_path) if plan_state_path is not None else "",
        },
        "chain_state": {
            "path": str(chain_state_path) if chain_state_path is not None else "",
            "present": bool(chain_state_path and chain_state_path.exists()),
            "current_plan_name": chain_current_plan,
            "last_state": _safe_text(chain_state.get("last_state")),
            "mtime": _mtime(chain_state_path) if chain_state_path is not None else 0.0,
            "fingerprint": _fingerprint(chain_state_path) if chain_state_path is not None else "",
        },
        "event_cursors": event_cursors,
        "tmux_process": tmux_process,
        "needs_human": {
            "path": str(needs_human_path),
            "present": needs_human_path.exists(),
            "summary": _safe_text(needs_human.get("summary")),
            "plan_refs": needs_human_plans,
            "recorded_at": _safe_text(needs_human.get("recorded_at")),
        },
        "repair_progress": repair_progress,
        "chain_log": chain_log,
        "active_step_heartbeat": active_step_heartbeat,
        "resume_authority_failure": resume_authority_failure,
        "sibling_sessions": siblings,
        "ignored_artifacts": sorted(ignored_artifacts, key=_artifact_sort_key),
        "stale_evidence": sorted(stale_evidence, key=_artifact_sort_key),
        "rationale": sorted(set(rationale)),
    }


def _safe_load_dict(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    loaded = load_json(path, default={})
    if isinstance(loaded, dict):
        return loaded
    return {}


def _safe_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_plan_name(value: object) -> str:
    text = _safe_text(value)
    return text if text and "/" not in text else ""


def _safe_path(value: object) -> Path | None:
    text = _safe_text(value)
    return Path(text) if text else None


def _resolve_remote_spec(workspace: Path | None, value: object) -> Path | None:
    text = _safe_text(value)
    if not text:
        return None
    path = Path(text)
    if path.is_absolute() or workspace is None:
        return path
    return workspace / path


def _resolve_run_kind(value: object, remote_spec: Path | None) -> str:
    text = _safe_text(value)
    if text and text != "unknown":
        return text
    if remote_spec is not None and remote_spec.name == "chain.yaml":
        return "chain"
    if remote_spec is not None and remote_spec.name == "epic-chain.yaml":
        return "epic_chain"
    return "unknown"


def _chain_state_path(workspace: Path | None, remote_spec: Path | None, run_kind: str) -> Path | None:
    if workspace is None or remote_spec is None or run_kind != "chain":
        return None
    canonical_path = chain_spec._state_path_for(remote_spec)
    try:
        candidates = chain_spec._state_path_candidates_for(remote_spec)
    except Exception:
        candidates = [canonical_path]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return canonical_path


def _plan_state_path(workspace: Path | None, plan_name: str, run_kind: str) -> Path | None:
    if workspace is None:
        return None
    plans_dir = workspace / ".megaplan" / "plans"
    if plan_name:
        return plans_dir / plan_name / "state.json"
    if run_kind != "plan":
        return None
    state_paths = sorted(plans_dir.glob("*/state.json"), key=lambda item: item.parent.name)
    return state_paths[0] if state_paths else None


def _collect_event_cursors(plan_state_path: Path | None, plan_state: Mapping[str, Any]) -> dict[str, Any]:
    if plan_state_path is None:
        return {"events_path": "", "events_present": False, "line_count": 0, "latest_gate_kind": "", "resume_retry_strategy": "", "mtime": 0.0}
    events_path = plan_state_path.parent / "events.ndjson"
    line_count = 0
    latest_gate_kind = ""
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            line_count += 1
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            kind = _safe_text(payload.get("kind"))
            if kind.startswith("gate"):
                latest_gate_kind = kind
    resume_cursor = plan_state.get("resume_cursor")
    retry_strategy = ""
    if isinstance(resume_cursor, Mapping):
        retry_strategy = _safe_text(resume_cursor.get("retry_strategy"))
    return {
        "events_path": str(events_path),
        "events_present": events_path.exists(),
        "line_count": line_count,
        "latest_gate_kind": latest_gate_kind,
        "resume_retry_strategy": retry_strategy,
        "mtime": _mtime(events_path),
    }


def _collect_resume_authority_failure(
    plan_state_path: Path | None,
    plan_state: Mapping[str, Any],
) -> dict[str, Any]:
    if plan_state_path is None or not plan_state_path.exists() or not isinstance(plan_state, Mapping):
        return {}
    if _safe_text(plan_state.get("current_state")).lower() != "failed":
        return {}
    resume_cursor = plan_state.get("resume_cursor")
    if not isinstance(resume_cursor, Mapping):
        return {}
    phase = _safe_text(resume_cursor.get("phase"))
    if not phase:
        return {}

    try:
        from arnold_pipelines.megaplan._core import topology as _topology
        from arnold_pipelines.megaplan._core.workflow import (
            _resume_execute_authority_failure,
        )
    except Exception:
        return {}

    try:
        active_state = _topology.predecessors(phase, policy="resume")
    except Exception:
        return {}
    if active_state != "executed":
        return {}

    try:
        failure = _resume_execute_authority_failure(
            plan_state_path.parent,
            cursor=dict(resume_cursor),
            guard="current_target_observe",
        )
    except Exception:
        return {}
    if not isinstance(failure, Mapping) or not failure:
        return {}

    plan_name = _safe_plan_name(plan_state.get("name")) or plan_state_path.parent.name
    payload = _stable_mapping(failure)
    payload["code"] = "resume_execute_authority_blocked"
    payload["phase"] = phase
    payload["plan_name"] = plan_name
    payload["current_state"] = _safe_text(plan_state.get("current_state"))
    if _safe_text(payload.get("reason")) == "execute_authority_diverged":
        payload["recommended_action"] = "repair_execute_authority"
        payload["suggested_commands"] = [
            f"execute --plan {plan_name} --confirm-destructive --user-approved"
        ]
    return payload


def _collect_tmux_process_evidence(
    marker: Mapping[str, Any],
    session: str,
    session_is_live: SessionLiveProbe | None,
    pid_is_live: PidLiveProbe | None,
) -> dict[str, Any]:
    pid = marker.get("pid")
    if not isinstance(pid, int):
        pid = marker.get("pane_pid")
    pid_live = _pid_is_live(pid, pid_is_live) if isinstance(pid, int) else None
    session_live = session_is_live(session) if session_is_live is not None else None
    if session_live is True or pid_live is True:
        live_status = "alive"
    elif session_live is False or pid_live is False:
        live_status = "stopped"
    else:
        live_status = "unknown"
    return {
        "session": session,
        "pid": pid if isinstance(pid, int) else None,
        "pid_live": pid_live,
        "session_live": session_live,
        "live_status": live_status,
    }


def _collect_sidecar_status(marker_dir: Path, session: str) -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    for suffix in (".repair-progress.json", ".reap-progress.json"):
        path = marker_dir / f"{session}{suffix}"
        if not path.exists():
            continue
        payload = _safe_load_dict(path)
        sidecar_suffix = canonical_sidecar_suffix(path) or suffix
        found.append(
            {
                "kind": sidecar_suffix.removesuffix(".json").lstrip("."),
                "path": str(path),
                "present": True,
                "status": _safe_text(payload.get("status")) or _safe_text(payload.get("outcome")),
                "mtime": _mtime(path),
            }
        )
    found.sort(key=lambda item: item["path"])
    return {
        "present": bool(found),
        "items": found,
    }


def _collect_sibling_sessions(
    marker_dir: Path,
    *,
    session: str,
    workspace: Path | None,
    session_is_live: SessionLiveProbe | None,
) -> list[dict[str, Any]]:
    if workspace is None or not marker_dir.exists():
        return []
    siblings: list[dict[str, Any]] = []
    for path in sorted(marker_dir.glob("*.json")):
        if path.name == f"{session}.json" or not is_canonical_session_marker_path(path):
            continue
        payload = _safe_load_dict(path)
        other_session = _safe_text(payload.get("session"))
        other_workspace = _safe_text(payload.get("workspace"))
        if not other_session or Path(other_workspace) != workspace:
            continue
        other_run_kind = _safe_text(payload.get("run_kind")) or "unknown"
        other_plan_name = _safe_plan_name(payload.get("plan_name"))
        live = session_is_live(other_session) if session_is_live is not None else None
        siblings.append(
            {
                "session": other_session,
                "marker_path": str(path),
                "run_kind": other_run_kind,
                "plan_name": other_plan_name,
                "live_status": "alive" if live is True else "stopped" if live is False else "unknown",
            }
        )
    siblings.sort(key=lambda item: (item["live_status"] != "alive", item["session"]))
    return siblings


def _collect_needs_human_plan_refs(marker: Mapping[str, Any]) -> list[str]:
    plans: set[str] = set()

    def add(value: object) -> None:
        plan = _safe_plan_name(value)
        if plan:
            plans.add(plan)

    def collect(context: object) -> None:
        if not isinstance(context, Mapping):
            return
        add(context.get("current_plan_name"))
        add(context.get("plan_name"))
        add(context.get("milestone_or_plan"))
        chain_state = context.get("chain_state_summary")
        if isinstance(chain_state, Mapping):
            add(chain_state.get("current_plan_name"))
        current = context.get("current")
        if isinstance(current, Mapping):
            add(current.get("current_plan_name"))
            add(current.get("milestone_or_plan"))

    for key in ("plan_name", "current_plan_name", "chain_current_plan_name", "milestone_or_plan"):
        add(marker.get(key))
    collect(marker)

    repair_data_path = _safe_text(marker.get("repair_data_path"))
    if repair_data_path:
        repair_data = _safe_load_dict(Path(repair_data_path))
        add(repair_data.get("plan_name"))
        collect(repair_data.get("current_failure_context"))
        iterations = repair_data.get("iterations")
        if isinstance(iterations, list):
            for item in iterations[-3:]:
                collect(item)
                if isinstance(item, Mapping):
                    add(item.get("plan_name"))
                    collect(item.get("failure_context"))
                    collect(item.get("current_failure_context"))

    return sorted(plans)


def _stable_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): value[key] for key in sorted(value)}


def _artifact(kind: str, path: Path, **extra: Any) -> dict[str, Any]:
    payload = {"kind": kind, "path": str(path)}
    payload.update(extra)
    return payload


def compare_needs_human_diagnostic(
    session: str,
    current_plan: str,
    *,
    marker_dir: str | Path,
    repair_data_dir: str | Path | None = None,
    legacy_matches: bool,
    legacy_plans: list[str] | None = None,
) -> dict[str, Any]:
    """Compare legacy needs-human determination with resolver output (observe-only).

    Returns a diagnostic record indicating agreement or discrepancy between the
    legacy ``repair_needs_human_matches_current_plan`` helper and the resolver.
    This function does NOT alter any behavior -- it is purely diagnostic.
    """
    record = resolve_current_target(
        session,
        marker_dir=marker_dir,
        repair_data_dir=repair_data_dir,
    )
    resolver_stale = any(
        e.get("kind") == "stale_needs_human_plan_ref"
        for e in record.get("stale_evidence", [])
    )
    legacy_stale = not legacy_matches
    agreement = resolver_stale == legacy_stale

    return {
        "kind": "needs_human_comparison",
        "agreement": agreement,
        "legacy": {
            "matches_current_plan": legacy_matches,
            "stale": legacy_stale,
            "plans": legacy_plans or [],
        },
        "resolver": {
            "stale": resolver_stale,
            "plan_refs": record.get("needs_human", {}).get("plan_refs", []),
            "current_plan": record.get("current_refs", {}).get("current_plan_name", ""),
        },
    }


def _collect_chain_log_evidence(
    workspace: Path | None,
    session: str,
    run_kind: str,
) -> dict[str, Any]:
    """Collect deterministic chain-log evidence for comparison snapshots.

    The canonical chain log lives at ``.megaplan/cloud-chain.log``; per-session
    variants (``cloud-chain-{session}.log``) are also inspected when available.
    """
    if workspace is None:
        return {"path": "", "present": False, "mtime": 0.0, "size": 0, "fingerprint": ""}
    candidates: list[Path] = []
    if session:
        candidates.append(workspace / ".megaplan" / f"cloud-chain-{session}.log")
    candidates.append(workspace / ".megaplan" / "cloud-chain.log")
    for path in candidates:
        if path.exists():
            return {
                "path": str(path),
                "present": True,
                "mtime": _mtime(path),
                "size": path.stat().st_size if path.exists() else 0,
                "fingerprint": _fingerprint(path),
            }
    # No chain log found — return a stable empty record
    return {
        "path": str(candidates[-1]) if candidates else "",
        "present": False,
        "mtime": 0.0,
        "size": 0,
        "fingerprint": "",
    }


def _collect_active_step_heartbeat(
    plan_state: Mapping[str, Any],
    *,
    pid_is_live: PidLiveProbe | None = None,
) -> dict[str, Any]:
    """Extract active-step heartbeat evidence from plan state.

    Returns the ``active_step`` sub-dict with phase, attempt, worker_pid,
    and started_at fields, plus an ``active`` boolean for quick liveness checks.
    """
    active_step = plan_state.get("active_step")
    if not isinstance(active_step, dict):
        return {"active": False, "phase": "", "attempt": 0, "worker_pid": "", "started_at": "", "pid_live": None}
    raw_worker_pid = active_step.get("worker_pid")
    worker_pid = _safe_text(raw_worker_pid)
    if not worker_pid and isinstance(raw_worker_pid, int):
        worker_pid = str(raw_worker_pid)
    pid_live: bool | None = None
    if worker_pid:
        try:
            pid_live = _pid_is_live(int(worker_pid), pid_is_live)
        except (TypeError, ValueError):
            pid_live = False
    return {
        "active": bool(pid_live),
        "phase": _safe_text(active_step.get("phase")),
        "attempt": int(active_step.get("attempt") or 0),
        "worker_pid": worker_pid,
        "started_at": _safe_text(active_step.get("started_at")),
        "pid_live": pid_live,
    }

def _artifact_sort_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _safe_text(item.get("kind")),
        _safe_text(item.get("path")),
        _safe_text(item.get("session")),
    )
