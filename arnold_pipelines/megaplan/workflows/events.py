"""Source-derived workflow event and cursor helpers.

These helpers project the lowered ``workflow.pypeline`` topology into a small
read-only API that auto/status/observability can consume without rebuilding
route authority from handler-local knowledge.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .components import ALL_STEP_COMPONENTS, SOURCE_TIEBREAKER_WORKFLOW
from .planning import AUTHORING_SOURCE_PATH, lowered_workflow_topology


@dataclass(frozen=True)
class WorkflowEvent:
    """One source-visible workflow transition."""

    id: str
    source_phase: str
    route_signal: str
    target_phase: str
    source_dispatch_phase: str
    target_dispatch_phase: str
    condition_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_phase": self.source_phase,
            "route_signal": self.route_signal,
            "target_phase": self.target_phase,
            "source_dispatch_phase": self.source_dispatch_phase,
            "target_dispatch_phase": self.target_dispatch_phase,
            "condition_ref": self.condition_ref,
        }


@dataclass(frozen=True)
class WorkflowCursor:
    """Cursor over the canonical lowered workflow topology."""

    phase: str
    dispatch_phase: str
    next_events: tuple[WorkflowEvent, ...]
    next_phases: tuple[str, ...]
    next_dispatch_phases: tuple[str, ...]
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "dispatch_phase": self.dispatch_phase,
            "next_events": [event.to_dict() for event in self.next_events],
            "next_phases": list(self.next_phases),
            "next_dispatch_phases": list(self.next_dispatch_phases),
            "source_path": self.source_path,
        }


@dataclass(frozen=True)
class _WorkflowTopology:
    steps: tuple[str, ...]
    dispatch_phases: tuple[str, ...]
    events: tuple[WorkflowEvent, ...]
    events_by_source: dict[str, tuple[WorkflowEvent, ...]]
    phase_aliases: dict[str, str]
    source_phase_aliases: dict[str, str]


def _unique(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _tiebreaker_metadata() -> tuple[tuple[str, ...], tuple[str, ...]]:
    metadata = SOURCE_TIEBREAKER_WORKFLOW.metadata
    canonical = tuple(str(item) for item in metadata.get("canonical_child_phases", ()) if isinstance(item, str))
    legacy = tuple(str(item) for item in metadata.get("child_steps", ()) if isinstance(item, str))
    return canonical, legacy


def _dispatch_phase_for_source_phase(source_phase: str) -> str:
    canonical_tiebreaker_phases, legacy_tiebreaker_steps = _tiebreaker_metadata()
    if len(canonical_tiebreaker_phases) >= 4 and len(legacy_tiebreaker_steps) >= 2:
        if source_phase in canonical_tiebreaker_phases[:-1]:
            return legacy_tiebreaker_steps[0]
        if source_phase == canonical_tiebreaker_phases[-1]:
            return legacy_tiebreaker_steps[1]
    return source_phase


def _entry_source_phase_for_dispatch_phase(dispatch_phase: str) -> str:
    canonical_tiebreaker_phases, legacy_tiebreaker_steps = _tiebreaker_metadata()
    if len(canonical_tiebreaker_phases) >= 4 and len(legacy_tiebreaker_steps) >= 2:
        if dispatch_phase == legacy_tiebreaker_steps[0]:
            return canonical_tiebreaker_phases[0]
        if dispatch_phase == legacy_tiebreaker_steps[1]:
            return canonical_tiebreaker_phases[-1]
    return dispatch_phase


@lru_cache(maxsize=1)
def _workflow_topology() -> _WorkflowTopology:
    topology = lowered_workflow_topology()
    steps = tuple(str(step) for step in topology.get("steps", ()) if isinstance(step, str))
    phase_aliases: dict[str, str] = {}
    source_phase_aliases: dict[str, str] = {}

    for step in steps:
        dispatch_phase = _dispatch_phase_for_source_phase(step)
        phase_aliases[step] = dispatch_phase
        source_phase_aliases[step] = step

    component_ids = {
        component.id.removeprefix("megaplan:"): component.id
        for component in ALL_STEP_COMPONENTS
        if isinstance(component.id, str) and component.id.startswith("megaplan:")
    }
    for step in steps:
        stable_id = component_ids.get(step)
        if stable_id is not None:
            phase_aliases[stable_id] = _dispatch_phase_for_source_phase(step)
            source_phase_aliases[stable_id] = step

    canonical_tiebreaker_phases, legacy_tiebreaker_steps = _tiebreaker_metadata()
    if len(canonical_tiebreaker_phases) >= 4 and len(legacy_tiebreaker_steps) >= 2:
        run_phase, decide_phase = legacy_tiebreaker_steps[:2]
        phase_aliases[run_phase] = run_phase
        phase_aliases[run_phase.replace("_", "-")] = run_phase
        phase_aliases[decide_phase] = decide_phase
        phase_aliases[decide_phase.replace("_", "-")] = decide_phase
        source_phase_aliases[run_phase] = canonical_tiebreaker_phases[0]
        source_phase_aliases[run_phase.replace("_", "-")] = canonical_tiebreaker_phases[0]
        source_phase_aliases[decide_phase] = canonical_tiebreaker_phases[-1]
        source_phase_aliases[decide_phase.replace("_", "-")] = canonical_tiebreaker_phases[-1]
        for source_phase, legacy_phase in zip(
            canonical_tiebreaker_phases,
            (
                run_phase,
                run_phase,
                run_phase,
                decide_phase,
            ),
        ):
            stable_id = component_ids.get(source_phase)
            if stable_id is not None:
                phase_aliases[stable_id] = legacy_phase
                source_phase_aliases[stable_id] = source_phase

    events: list[WorkflowEvent] = []
    grouped: dict[str, list[WorkflowEvent]] = defaultdict(list)
    for route in topology.get("routes", ()):
        if not isinstance(route, dict):
            continue
        source_phase = str(route.get("source") or "")
        target_phase = str(route.get("target") or "")
        route_signal = str(route.get("label") or "")
        if not source_phase or not target_phase or not route_signal:
            continue
        event = WorkflowEvent(
            id=str(route.get("id") or f"{source_phase}:{route_signal}"),
            source_phase=source_phase,
            route_signal=route_signal,
            target_phase=target_phase,
            source_dispatch_phase=_dispatch_phase_for_source_phase(source_phase),
            target_dispatch_phase=_dispatch_phase_for_source_phase(target_phase),
            condition_ref=str(route["condition_ref"]) if route.get("condition_ref") is not None else None,
        )
        events.append(event)
        grouped[source_phase].append(event)

    dispatch_phases = _unique(
        [
            _dispatch_phase_for_source_phase(step)
            for step in steps
            if step not in {"halt", "override"}
        ]
    )
    return _WorkflowTopology(
        steps=steps,
        dispatch_phases=dispatch_phases,
        events=tuple(events),
        events_by_source={source: tuple(items) for source, items in grouped.items()},
        phase_aliases=phase_aliases,
        source_phase_aliases=source_phase_aliases,
    )


def workflow_dispatch_phase_names() -> frozenset[str]:
    """Return operational phase names whose authority comes from workflow source."""

    return frozenset(_workflow_topology().dispatch_phases)


def workflow_phase_aliases() -> dict[str, str]:
    """Return alias -> dispatch-phase mappings derived from workflow source."""

    return dict(_workflow_topology().phase_aliases)


def resolve_workflow_phase(raw_phase: str | None) -> str | None:
    """Resolve a raw phase/step/stable-id into an operational dispatch phase."""

    if not isinstance(raw_phase, str) or not raw_phase:
        return None
    return _workflow_topology().phase_aliases.get(raw_phase)


def resolve_workflow_source_phase(raw_phase: str | None) -> str | None:
    """Resolve a raw phase/step/stable-id into a canonical lowered source phase."""

    if not isinstance(raw_phase, str) or not raw_phase:
        return None
    topology = _workflow_topology()
    source_phase = topology.source_phase_aliases.get(raw_phase)
    if source_phase is not None:
        return source_phase
    dispatch_phase = topology.phase_aliases.get(raw_phase)
    if dispatch_phase is None:
        return None
    return _entry_source_phase_for_dispatch_phase(dispatch_phase)


def workflow_events() -> tuple[WorkflowEvent, ...]:
    """Return all canonical workflow transitions from lowered source."""

    return _workflow_topology().events


def workflow_cursor(raw_phase: str | None) -> WorkflowCursor | None:
    """Return the source-derived cursor for ``raw_phase`` if it is workflow-backed."""

    source_phase = resolve_workflow_source_phase(raw_phase)
    if source_phase is None:
        return None
    topology = _workflow_topology()
    next_events = topology.events_by_source.get(source_phase, ())
    return WorkflowCursor(
        phase=source_phase,
        dispatch_phase=_dispatch_phase_for_source_phase(source_phase),
        next_events=next_events,
        next_phases=tuple(event.target_phase for event in next_events),
        next_dispatch_phases=_unique([event.target_dispatch_phase for event in next_events]),
        source_path=str(AUTHORING_SOURCE_PATH),
    )


__all__ = [
    "WorkflowCursor",
    "WorkflowEvent",
    "resolve_workflow_phase",
    "resolve_workflow_source_phase",
    "workflow_cursor",
    "workflow_dispatch_phase_names",
    "workflow_events",
    "workflow_phase_aliases",
]
