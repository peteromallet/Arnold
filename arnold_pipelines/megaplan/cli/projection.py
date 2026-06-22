"""CLI projection helpers for manifest-backed Megaplan runs.

These helpers reconstruct plan status, trace, gate/review/execute/override state,
resume coordinates, and inspection views from manifest journal events and
artifact bindings.  They do not read ``state.json`` as authority; legacy
``state.json`` is treated as a migration input only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from arnold.kernel.events import EventEnvelope
from arnold.kernel.journal import NDJsonEventJournal
from arnold.kernel.replay import ReplayCursor


# ---------------------------------------------------------------------------
# Data carriers
# ---------------------------------------------------------------------------

@dataclass
class PlanStatusProjection:
    """Projected status of a plan from manifest events."""

    plan_name: str
    current_state: str
    iteration: int
    active_node: str | None
    completed_nodes: list[str] = field(default_factory=list)
    failed_nodes: list[str] = field(default_factory=list)
    suspended_nodes: list[str] = field(default_factory=list)
    pending_nodes: list[str] = field(default_factory=list)
    control_transitions: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_name": self.plan_name,
            "current_state": self.current_state,
            "iteration": self.iteration,
            "active_node": self.active_node,
            "completed_nodes": self.completed_nodes,
            "failed_nodes": self.failed_nodes,
            "suspended_nodes": self.suspended_nodes,
            "pending_nodes": self.pending_nodes,
            "control_transitions": self.control_transitions,
            "artifacts": self.artifacts,
        }


@dataclass
class TraceRow:
    """Single trace row derived from a journal event."""

    sequence: int | None
    timestamp: str | None
    family: str
    kind: str
    node_ref: str | None
    payload_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "family": self.family,
            "kind": self.kind,
            "node_ref": self.node_ref,
            "payload_summary": self.payload_summary,
        }


# ---------------------------------------------------------------------------
# Journal readers
# ---------------------------------------------------------------------------

def read_events(artifact_root: Path) -> tuple[EventEnvelope, ...]:
    """Return all events from the manifest journal at ``artifact_root``."""

    return NDJsonEventJournal(artifact_root).read()


# ---------------------------------------------------------------------------
# Status projection
# ---------------------------------------------------------------------------

def project_status(
    *,
    plan_name: str,
    artifact_root: Path,
    expected_nodes: tuple[str, ...] = (),
) -> PlanStatusProjection:
    """Project plan status from manifest journal events."""

    events = read_events(artifact_root)
    completed: set[str] = set()
    failed: set[str] = set()
    suspended: set[str] = set()
    started: set[str] = set()
    control_transitions: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    iteration = 0

    for event in events:
        payload = event.payload
        node_ref = payload.get("node_ref")
        if event.kind == "node_completed" and isinstance(node_ref, str):
            completed.add(node_ref)
            started.discard(node_ref)
        elif event.kind == "node_failed" and isinstance(node_ref, str):
            failed.add(node_ref)
        elif event.kind == "node_suspended" and isinstance(node_ref, str):
            suspended.add(node_ref)
        elif event.kind == "node_started" and isinstance(node_ref, str):
            started.add(node_ref)
        elif event.kind == "control_transition":
            control_transitions.append({
                "sequence": event.sequence,
                "source": payload.get("source_node"),
                "target": payload.get("target_node"),
                "kind": payload.get("kind"),
                "trigger": payload.get("trigger"),
            })
        elif event.kind == "artifact_written":
            artifacts.append({
                "sequence": event.sequence,
                "artifact_id": payload.get("artifact_id"),
                "relative_path": payload.get("relative_path"),
                "content_type_id": payload.get("content_type_id"),
            })
        if isinstance(node_ref, str) and event.kind == "loop_iteration":
            iteration = max(iteration, int(payload.get("iteration", 0) or 0))

    # Determine current state from the terminal event or latest active node.
    terminal_kind = None
    for event in reversed(events):
        if event.kind in {"run_completed", "run_failed", "run_suspended", "run_cancelled"}:
            terminal_kind = event.kind
            break

    current_state = _terminal_state_to_plan_state(terminal_kind, bool(suspended), bool(failed))
    active_node = None
    if started - completed - failed - suspended:
        active_node = sorted(started - completed - failed - suspended)[-1]
    elif suspended:
        active_node = sorted(suspended)[0]

    pending = set(expected_nodes) - completed - failed - suspended - started

    return PlanStatusProjection(
        plan_name=plan_name,
        current_state=current_state,
        iteration=iteration,
        active_node=active_node,
        completed_nodes=sorted(completed),
        failed_nodes=sorted(failed),
        suspended_nodes=sorted(suspended),
        pending_nodes=sorted(pending),
        control_transitions=control_transitions,
        artifacts=artifacts,
    )


def _terminal_state_to_plan_state(
    terminal_kind: str | None,
    has_suspended: bool,
    has_failed: bool,
) -> str:
    if terminal_kind == "run_completed":
        return "done"
    if terminal_kind == "run_failed":
        return "failed"
    if terminal_kind == "run_suspended" or has_suspended:
        return "awaiting_human"
    if terminal_kind == "run_cancelled":
        return "cancelled"
    if has_failed:
        return "failed"
    return "running"


# ---------------------------------------------------------------------------
# Trace projection
# ---------------------------------------------------------------------------

def project_trace(
    *,
    artifact_root: Path,
    node_refs: tuple[str, ...] | None = None,
    kinds: tuple[str, ...] | None = None,
) -> list[TraceRow]:
    """Project a human-readable trace from manifest journal events."""

    events = read_events(artifact_root)
    rows: list[TraceRow] = []
    for event in events:
        payload = event.payload
        node_ref = payload.get("node_ref")
        if node_refs and node_ref not in node_refs:
            continue
        if kinds and event.kind not in kinds:
            continue
        summary = _summarize_payload(event)
        rows.append(
            TraceRow(
                sequence=event.sequence,
                timestamp=payload.get("timestamp") or event.event_id.split(":")[-1],
                family=event.family.value,
                kind=event.kind,
                node_ref=node_ref if isinstance(node_ref, str) else None,
                payload_summary=summary,
            )
        )
    return rows


def _summarize_payload(event: EventEnvelope) -> dict[str, Any]:
    payload = event.payload
    summary: dict[str, Any] = {}
    if event.kind == "node_started":
        summary = {"attempt": payload.get("attempt"), "iteration": payload.get("iteration")}
    elif event.kind == "node_completed":
        summary = {"outputs": list(payload.get("outputs", {}).keys())}
    elif event.kind == "node_failed":
        summary = {"error": payload.get("error")}
    elif event.kind == "node_suspended":
        summary = {"route_id": payload.get("route_id")}
    elif event.kind == "control_transition":
        summary = {
            "source": payload.get("source_node"),
            "target": payload.get("target_node"),
            "trigger": payload.get("trigger"),
        }
    elif event.kind == "artifact_written":
        summary = {
            "artifact_id": payload.get("artifact_id"),
            "relative_path": payload.get("relative_path"),
        }
    else:
        summary = {k: v for k, v in payload.items() if k in {"reason", "manifest_id", "reservation_id"}}
    return summary


# ---------------------------------------------------------------------------
# Command-specific projections
# ---------------------------------------------------------------------------

def project_plan_status(artifact_root: Path, plan_name: str) -> dict[str, Any]:
    """Project status for the ``plan`` command."""

    return project_status(plan_name=plan_name, artifact_root=artifact_root).to_dict()


def project_resume_status(artifact_root: Path, plan_name: str) -> dict[str, Any]:
    """Project resume context for the ``resume`` command."""

    status = project_status(plan_name=plan_name, artifact_root=artifact_root)
    events = read_events(artifact_root)
    last_sequence = events[-1].sequence if events else None
    return {
        "plan_name": plan_name,
        "current_state": status.current_state,
        "suspended_nodes": status.suspended_nodes,
        "active_node": status.active_node,
        "last_event_sequence": last_sequence,
        "can_resume": status.current_state in {"awaiting_human", "running"},
    }


def project_gate_status(artifact_root: Path) -> dict[str, Any]:
    """Project gate status from journal control transitions and artifacts."""

    events = read_events(artifact_root)
    recommendations: list[dict[str, Any]] = []
    for event in events:
        if event.kind == "control_transition":
            trigger = event.payload.get("trigger", "")
            if isinstance(trigger, str) and trigger.startswith("gate:"):
                recommendations.append({
                    "sequence": event.sequence,
                    "recommendation": trigger.split(":", 1)[1].upper(),
                    "source": event.payload.get("source_node"),
                    "target": event.payload.get("target_node"),
                })
        if event.kind == "artifact_written" and str(event.payload.get("artifact_id", "")).startswith("gate_signals"):
            recommendations.append({
                "sequence": event.sequence,
                "artifact_id": event.payload.get("artifact_id"),
                "relative_path": event.payload.get("relative_path"),
            })
    return {"recommendations": recommendations}


def project_review_status(artifact_root: Path) -> dict[str, Any]:
    """Project review status from journal events."""

    events = read_events(artifact_root)
    verdicts: list[dict[str, Any]] = []
    for event in events:
        if event.kind == "control_transition":
            trigger = event.payload.get("trigger", "")
            if isinstance(trigger, str) and trigger.startswith("review:"):
                verdicts.append({
                    "sequence": event.sequence,
                    "verdict": trigger.split(":", 1)[1].upper(),
                    "source": event.payload.get("source_node"),
                    "target": event.payload.get("target_node"),
                })
    return {"verdicts": verdicts}


def project_execute_status(artifact_root: Path) -> dict[str, Any]:
    """Project execute status from journal events."""

    events = read_events(artifact_root)
    started = any(
        event.kind == "node_started" and event.payload.get("node_ref") == "execute"
        for event in events
    )
    completed = any(
        event.kind == "node_completed" and event.payload.get("node_ref") == "execute"
        for event in events
    )
    failed = any(
        event.kind == "node_failed" and event.payload.get("node_ref") == "execute"
        for event in events
    )
    return {"started": started, "completed": completed, "failed": failed}


def project_override_status(artifact_root: Path) -> dict[str, Any]:
    """Project override actions from journal control transitions."""

    events = read_events(artifact_root)
    actions: list[dict[str, Any]] = []
    for event in events:
        if event.kind == "control_transition":
            kind = event.payload.get("kind")
            if kind == "override" or str(event.payload.get("trigger", "")).startswith("override:"):
                actions.append({
                    "sequence": event.sequence,
                    "action": event.payload.get("trigger", "").split(":")[-1] or event.payload.get("kind"),
                    "source": event.payload.get("source_node"),
                    "target": event.payload.get("target_node"),
                })
    return {"override_actions": actions}


def project_inspect(
    *,
    artifact_root: Path,
    plan_name: str,
    manifest_hash: str | None = None,
) -> dict[str, Any]:
    """Project a full inspect view from journal events and artifact bindings."""

    status = project_status(plan_name=plan_name, artifact_root=artifact_root)
    trace = project_trace(artifact_root=artifact_root)
    return {
        "plan_name": plan_name,
        "manifest_hash": manifest_hash,
        "status": status.to_dict(),
        "trace": [row.to_dict() for row in trace],
        "source_authority": "manifest_journal",
        "state_json_authority": False,
    }


# ---------------------------------------------------------------------------
# Resume cursor projection
# ---------------------------------------------------------------------------

def project_resume_cursor(
    *,
    artifact_root: Path,
    manifest_hash: str,
    node_ref: str | None = None,
    reentry_id: str | None = None,
) -> ReplayCursor:
    """Project a resume cursor from the journal and manifest coordinates."""

    events = read_events(artifact_root)
    last_sequence = events[-1].sequence if events else None
    active = None
    if node_ref is None:
        for event in reversed(events):
            if event.kind == "node_suspended":
                active = event.payload.get("node_ref")
                break
    node_ref = node_ref or active or "gate"
    return ReplayCursor(
        manifest_hash=manifest_hash,
        reentry_id=reentry_id,
        scope_stack=(),
        artifact_root=str(artifact_root),
        event_sequence=last_sequence,
    )


__all__ = [
    "PlanStatusProjection",
    "TraceRow",
    "project_execute_status",
    "project_gate_status",
    "project_inspect",
    "project_override_status",
    "project_plan_status",
    "project_resume_cursor",
    "project_resume_status",
    "project_review_status",
    "project_status",
    "project_trace",
    "read_events",
]
