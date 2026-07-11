"""``megaplan introspect`` — structured JSON snapshot of a plan's live state.

Produces a single JSON payload with all four killer fields:
- ``now_utc``: anti-stale-timestamp anchor.
- ``rubric_doc.drift``: drift between prep_skill.md and installed profiles.
- ``active_phase.liveness``: progressing | quiet | stalled | timeout-imminent.
- ``block_details.recoverable_via``: enumerated valid recoveries.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Tuple

from arnold_pipelines.megaplan.anchors import anchor_summary
from arnold_pipelines.megaplan.control_interface import read_valid_targets
from arnold_pipelines.megaplan.observability.events import EventKind, read_events
from arnold_pipelines.megaplan.observability.liveness import (
    has_active_in_flight_llm,
    unmatched_llm_starts,
)
from arnold.runtime.outcome import RunOutcome

# Default phase timeout (overridable from state)
_DEFAULT_PHASE_TIMEOUT_SECONDS = 3600


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts_str: str) -> Optional[float]:
    """Parse ISO timestamp string to epoch seconds."""
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def _active_phase_name(active: dict[str, Any]) -> str | None:
    phase = active.get("phase") or active.get("step")
    return phase if isinstance(phase, str) and phase else None


def _projected_outcome(state: dict[str, Any]) -> RunOutcome | None:
    current_state = state.get("current_state")
    if current_state == "done":
        return RunOutcome.SUCCEEDED
    if current_state in {"failed", "aborted"}:
        return RunOutcome.FAILED
    if current_state == "blocked":
        return RunOutcome.BLOCKED
    if current_state in {"awaiting_human", "clarifying"}:
        return RunOutcome.AWAITING_HUMAN
    return None


def _git_info(project_dir: Path) -> dict:
    """Return git branch, dirty flag, and head hash for the project."""
    info: dict = {"branch": None, "dirty": False, "head": None}
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            info["dirty"] = True
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["head"] = result.stdout.strip()[:12]
    except Exception:
        pass

    return info


def _editable_install_location() -> Optional[str]:
    """Return the editable-install location of megaplan, or None."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "megaplan"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("Editable project location:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def _get_profiles_list() -> list[str]:
    """Get profiles from the binary via ``megaplan config profiles list``."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "arnold_pipelines.megaplan", "config", "profiles", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "MEGAPLAN_NO_COLOR": "1"},
        )
        if result.returncode == 0:
            # The command returns a JSON object with a "profiles" list
            import json as _json
            data = _json.loads(result.stdout)
            profile_list = data.get("profiles", [])
            if isinstance(profile_list, list):
                names = [
                    p.get("name", "") for p in profile_list
                    if isinstance(p, dict) and p.get("name")
                ]
                if names:
                    return names
            # Fallback: maybe the output is line-by-line names
            names: list[str] = []
            for line in result.stdout.splitlines():
                name = line.strip()
                if name and not name.startswith("{"):
                    names.append(name)
            if names:
                return names
    except Exception:
        pass
    # Fallback: glob the profiles directory
    try:
        import arnold_pipelines.megaplan.profiles as megaplan_profiles

        profiles_dir = Path(megaplan_profiles.__file__).parent
        return sorted(
            p.stem for p in profiles_dir.glob("*.toml") if p.stem != "__init__"
        )
    except Exception:
        return []


def _parse_decision_skill_profiles() -> list[str]:
    """Parse the megaplan-prep skill (prep_skill.md) for profile references."""
    try:
        import arnold_pipelines.megaplan.data as megaplan_data

        # megaplan.data may be a namespace package (``__file__`` is None);
        # use ``__path__`` to locate the directory in that case.
        if getattr(megaplan_data, "__file__", None):
            data_dir = Path(megaplan_data.__file__).parent
        elif hasattr(megaplan_data, "__path__"):
            data_dir = Path(next(iter(megaplan_data.__path__)))
        else:
            return []
        skill_path = data_dir / "prep_skill.md"
        if not skill_path.exists():
            return []
        content = skill_path.read_text(encoding="utf-8")
    except Exception:
        return []

    names: set[str] = set()

    # Known canonical tier/profile names
    known = {
        "solo", "directed", "partnered", "premium", "apex",
        "all-deepseek-pro", "all-deepseek-pro-direct", "all-claude",
        "all-codex", "all-open", "all-deepseek-flash", "all-fireworks-deepseek",
    }

    for name in known:
        if re.search(rf"\b{re.escape(name)}\b", content, re.IGNORECASE):
            names.add(name)

    # Also extract --profile NAME patterns. Restrict to lowercase identifier
    # shape (letters/digits/hyphen/underscore) so we skip prose placeholders
    # like ``<name>``, ``NAME``, or trailing punctuation.
    for m in re.finditer(r"--profile\s+`?([a-z][a-z0-9_-]+)`?", content):
        nm = m.group(1)
        if nm:
            names.add(nm)

    return sorted(names)


def _load_state(plan_dir: Path) -> Optional[dict]:
    """Load state.json from plan_dir, returning None if missing/unreadable."""
    # cache-tolerant: introspect probe.
    state_file = plan_dir / "state.json"
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Liveness computation
# ---------------------------------------------------------------------------


def _compute_liveness(
    events: list[dict],
    plan_dir: Path,
    state: Optional[dict],
    now_ts: float,
) -> Tuple[str, str]:
    """Return (liveness_enum, liveness_reason).

    Rules:
    - progressing: most recent event < 60s OR in-flight LLM call exists.
    - quiet: most recent event 60–300s ago, no in-flight LLM.
    - stalled: most recent event > 300s ago, **BUT** excluded when an
      in-flight LLM call exists (unmatched llm_call_start without llm_call_end).
    - timeout-imminent: phase_age > 0.8 * phase_timeout (takes priority over
      the above when applicable).
    """
    # Phase age: from active_step.started_at if available
    phase_age: Optional[float] = None
    phase_timeout = _DEFAULT_PHASE_TIMEOUT_SECONDS

    if state and isinstance(state, dict):
        active = state.get("active_step")
        if isinstance(active, dict):
            started = active.get("started_at")
            if started:
                started_epoch = _parse_iso(str(started))
                if started_epoch is not None:
                    phase_age = now_ts - started_epoch

    # Find most recent event timestamp
    last_event_ts: Optional[float] = None
    for ev in events:
        ts = _parse_iso(ev.get("ts_utc", ""))
        if ts is not None:
            last_event_ts = ts

    has_in_flight_llm = has_active_in_flight_llm(
        events,
        state,
        now_ts,
        parse_timestamp=_parse_iso,
        start_kind=EventKind.LLM_CALL_START,
        end_kind=EventKind.LLM_CALL_END,
    )

    # Rule: timeout-imminent (always check first)
    if phase_age is not None and phase_age > 0.8 * phase_timeout:
        return "timeout-imminent", f"phase_age {phase_age:.0f}s > 0.8 * timeout {phase_timeout}s"

    if last_event_ts is None:
        return "quiet", "no events recorded yet"

    age = now_ts - last_event_ts

    # Rule: progressing
    if age < 60 or has_in_flight_llm:
        reason_parts = []
        if age < 60:
            reason_parts.append(f"last event {age:.0f}s ago")
        if has_in_flight_llm:
            reason_parts.append("in-flight LLM call")
        return "progressing", "; ".join(reason_parts)

    # Rule: stalled (but NOT when in-flight LLM)
    if age > 300 and not has_in_flight_llm:
        return "stalled", f"last event {age:.0f}s ago (>300s) and no in-flight LLM"

    # Rule: quiet
    return "quiet", f"last event {age:.0f}s ago (60-300s range)"


# ---------------------------------------------------------------------------
# Rubric drift
# ---------------------------------------------------------------------------


def _compute_rubric_drift() -> dict:
    """Compute rubric_doc.drift between prep_skill.md and installed profiles.

    Returns: {"drifted": bool, "referenced_profiles": [...], "available_profiles": [...],
               "missing": [...], "extra_in_skill": [...]}
    """
    referenced = _parse_decision_skill_profiles()
    available = _get_profiles_list()

    available_set = set(available)
    referenced_set = set(referenced)

    missing = sorted(referenced_set - available_set)
    extra = sorted(available_set - referenced_set)

    return {
        "drifted": bool(missing),
        "referenced_profiles": sorted(referenced),
        "available_profiles": sorted(available),
        "missing_in_binary": missing if missing else None,
        "extra_in_skill_not_referenced": extra if extra else None,
    }


# ---------------------------------------------------------------------------
# Block details / recoverable_via
# ---------------------------------------------------------------------------


def _compute_block_details(plan_dir: Path, state: Optional[dict]) -> dict:
    """Compute block_details with recoverable_via from workflow_next.

    Returns: {"is_blocked": bool, "current_state": str|null, "recoverable_via": [str]}
    """
    result: dict = {
        "is_blocked": False,
        "current_state": None,
        "recoverable_via": None,
    }

    if state is None:
        return result

    current_state = state.get("current_state")
    result["current_state"] = current_state

    if not isinstance(current_state, str):
        return result

    # Determine if blocked — keep the legacy display semantics, but use the
    # neutral outcome projection to decide whether recovery targets apply.
    flags_count = 0
    for path_obj in sorted(plan_dir.glob("gate_signals_v*.json"), reverse=True):
        try:
            data = json.loads(path_obj.read_text(encoding="utf-8"))
            flags = data.get("unresolved_flags", [])
            if isinstance(flags, list):
                flags_count = len(flags)
            break
        except Exception:
            continue

    outcome = _projected_outcome(state)
    is_blocked = flags_count > 0 or current_state in {"gated", "clarifying"} or outcome in {
        RunOutcome.BLOCKED,
        RunOutcome.AWAITING_HUMAN,
        RunOutcome.FAILED,
    }
    result["is_blocked"] = is_blocked

    if is_blocked:
        try:
            recovery = outcome in {
                RunOutcome.BLOCKED,
                RunOutcome.AWAITING_HUMAN,
                RunOutcome.FAILED,
            }
            recov = read_valid_targets(
                state,
                plugin_id="megaplan",
                recovery=recovery,
            )
            result["recoverable_via"] = [
                target.id
                for target in recov
                if isinstance(target.id, str)
                and target.id
                and target.metadata.get("actionable", True)
            ]
        except Exception:
            result["recoverable_via"] = []

    return result


# ---------------------------------------------------------------------------
# Process tree
# ---------------------------------------------------------------------------


def _process_tree(plan_name: str) -> list[dict]:
    """Return execution processes for this plan, excluding observers/prompts."""
    try:
        import psutil
    except ImportError:
        return []

    procs: list[dict] = []
    try:
        for proc in psutil.process_iter(["pid", "cmdline", "ppid", "create_time"]):
            cmdline = proc.info.get("cmdline") or []
            if "-m" not in cmdline or "arnold_pipelines.megaplan" not in cmdline:
                continue
            module_index = cmdline.index("arnold_pipelines.megaplan")
            command = cmdline[module_index + 1] if module_index + 1 < len(cmdline) else ""
            if command in {"introspect", "doctor", "trace", "status", "progress", "watch"}:
                continue
            if plan_name not in cmdline:
                continue
            procs.append({
                "pid": proc.info["pid"],
                "ppid": proc.info.get("ppid"),
                "cmdline": cmdline,
                "create_time": proc.info.get("create_time"),
            })
    except Exception:
        pass
    return procs


# ---------------------------------------------------------------------------
# Main payload builder
# ---------------------------------------------------------------------------


def build_introspect_payload(plan_dir: Path) -> dict:
    """Build the full introspect JSON payload for a plan.

    All keys from the design doc are present; optionals default to null.

    Args:
        plan_dir: Path to the plan directory (e.g., .megaplan/plans/<name>/).

    Returns:
        Dict suitable for json.dumps().
    """
    now = _now_utc()
    now_ts = now.timestamp()
    plan_name = plan_dir.name
    project_dir = plan_dir.parent.parent.parent  # .megaplan/plans/<name> → project root
    if not (project_dir / ".git").exists():
        # Try to find project dir by walking up
        d = plan_dir
        for _ in range(5):
            d = d.parent
            if (d / ".git").exists():
                project_dir = d
                break

    # Load state
    state = _load_state(plan_dir)

    # Read all events
    events = list(read_events(plan_dir))

    # ── Liveness ────────────────────────────────────────────────────────
    liveness, liveness_reason = _compute_liveness(events, plan_dir, state, now_ts)

    # ── Active phase info ───────────────────────────────────────────────
    active_phase: dict = {
        "phase": None,
        "agent": None,
        "model": None,
        "started_at": None,
        "attempt": None,
        "liveness": liveness,
        "liveness_reason": liveness_reason,
        "phase_age_s": None,
        "subprocess": None,
    }
    if state and isinstance(state, dict):
        active = state.get("active_step")
        if isinstance(active, dict):
            active_phase["phase"] = _active_phase_name(active)
            active_phase["agent"] = active.get("agent")
            active_phase["model"] = active.get("model")
            active_phase["started_at"] = active.get("started_at")
            active_phase["attempt"] = active.get("attempt")
            started = active.get("started_at")
            if started:
                started_epoch = _parse_iso(str(started))
                if started_epoch is not None:
                    active_phase["phase_age_s"] = now_ts - started_epoch

    # Subprocess stats
    subprocess_events = [
        e for e in events
        if e.get("kind") in (EventKind.SUBPROCESS_SPAWNED, EventKind.SUBPROCESS_EXITED,
                             EventKind.SUBPROCESS_SIGNALED)
    ]
    active_phase["subprocess"] = {
        "events_count": len(subprocess_events),
        "most_recent": subprocess_events[-1] if subprocess_events else None,
    }

    # Process tree
    proc_tree = _process_tree(plan_name)
    active_phase["subprocess"]["process_tree"] = proc_tree

    # ── Rubric doc drift ────────────────────────────────────────────────
    rubric_doc = _compute_rubric_drift()

    # ── Block details ───────────────────────────────────────────────────
    block_details = _compute_block_details(plan_dir, state)

    # ── Binary git ──────────────────────────────────────────────────────
    git_info = _git_info(project_dir)
    editable_loc = _editable_install_location()
    binary_git: dict = {
        "branch": git_info.get("branch"),
        "dirty": git_info.get("dirty", False),
        "head": git_info.get("head"),
        "editable_install": editable_loc,
    }

    # ── Evidence window / milestone attribution ─────────────────────────
    chain_policy = (state or {}).get("meta", {}).get("chain_policy", {}) if isinstance(state, dict) else {}
    milestone_base_sha: str | None = chain_policy.get("milestone_base_sha")
    head_sha: str | None = git_info.get("head")
    evidence_window: dict = {
        "base_sha": milestone_base_sha,
        "head_sha": head_sha,
        "source": "declared" if milestone_base_sha else "heuristic_merge_base",
    }

    # Count changed files between base and head when both are available
    changed_file_count: int | None = None
    if milestone_base_sha and head_sha:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{milestone_base_sha}..{head_sha}"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                changed_file_count = len(
                    [f for f in result.stdout.strip().split("\n") if f]
                )
        except Exception:
            pass

    # Derive divergence_count from the chain-policy fingerprint payload
    divergence_count: int | None = None
    rdf = chain_policy.get("repeated_divergence_fingerprint")
    if isinstance(rdf, dict):
        divergence_count = rdf.get("divergence_count")
    elif isinstance(rdf, str):
        divergence_count = None  # fingerprint is just a hash string

    repeated_divergence_fingerprint = chain_policy.get("repeated_divergence_fingerprint")

    carry_manifest = chain_policy.get("carry_forward_manifest")
    carry_forward_declared: bool = False
    if isinstance(carry_manifest, dict) and carry_manifest.get("milestone_label"):
        carry_forward_declared = True

    evidence: dict = {
        "window": evidence_window,
        "changed_file_count": changed_file_count,
        "divergence_count": divergence_count,
        "repeated_divergence_fingerprint": repeated_divergence_fingerprint,
        "carry_forward_declared": carry_forward_declared,
    }

    # ── Event stats ─────────────────────────────────────────────────────
    event_kinds_seen = sorted(set(e.get("kind") for e in events))
    event_stats: dict = {
        "total": len(events),
        "first_ts": events[0].get("ts_utc") if events else None,
        "last_ts": events[-1].get("ts_utc") if events else None,
        "kinds_seen": event_kinds_seen,
    }

    # ── In-flight LLM ───────────────────────────────────────────────────
    llm_starts_no_end = unmatched_llm_starts(
        events,
        start_kind=EventKind.LLM_CALL_START,
        end_kind=EventKind.LLM_CALL_END,
    )
    in_flight_llm: Optional[dict] = llm_starts_no_end[-1] if llm_starts_no_end else None

    # ── Cost ────────────────────────────────────────────────────────────
    total_cost = sum(
        float(e.get("payload", {}).get("cost_usd", 0))
        for e in events
        if e.get("kind") == EventKind.COST_RECORDED
    )

    # ── Outstanding flags ───────────────────────────────────────────────
    flags: list[dict] = []
    for path_obj in sorted(plan_dir.glob("gate_signals_v*.json"), reverse=True):
        try:
            data = json.loads(path_obj.read_text(encoding="utf-8"))
            unresolved = data.get("unresolved_flags", [])
            if isinstance(unresolved, list):
                flags = unresolved
            break
        except Exception:
            continue

    # ── Top-level state snapshot ───────────────────────────────────────
    plan_state: Optional[str] = None
    iteration: Optional[int] = None
    if state and isinstance(state, dict):
        cs = state.get("current_state")
        if isinstance(cs, str):
            plan_state = cs
        it = state.get("iteration")
        if isinstance(it, int):
            iteration = it

    # ── Assemble payload ────────────────────────────────────────────────
    payload: dict = {
        "now_utc": now.isoformat(),
        "plan": plan_name,
        "plan_state": plan_state,
        "iteration": iteration,
        "plan_dir": str(plan_dir),
        "anchors": anchor_summary(state or {}, plan_dir),
        "binary_git": binary_git,
        "evidence": evidence,
        "rubric_doc": rubric_doc,
        "active_phase": active_phase,
        "block_details": block_details,
        "event_stats": event_stats,
        "in_flight_llm": in_flight_llm,
        "cost": {
            "total_usd": total_cost,
            "currency": "USD",
        },
        "outstanding_flags": flags if flags else None,
        "outstanding_flags_count": len(flags) if isinstance(flags, list) else 0,
    }

    return payload
