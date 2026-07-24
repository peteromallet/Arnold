from __future__ import annotations

from collections.abc import Iterator

from arnold_pipelines.megaplan.observability.events_projection import project_events
from arnold_pipelines.megaplan.store import StoredEvent


class _FakeStore:
    def __init__(self, events: tuple[StoredEvent, ...]) -> None:
        self._events = events

    def events_for_plan(self, plan_id: str) -> Iterator[StoredEvent]:
        del plan_id
        return iter(self._events)


def test_project_events_includes_workflow_cursor_for_workflow_backed_phase() -> None:
    store = _FakeStore(
        (
            StoredEvent(
                kind="phase_start",
                phase="gate",
                payload={"phase": "gate"},
                source="file",
            ),
        )
    )

    projected = project_events(store, "demo")

    assert len(projected) == 1
    cursor = projected[0]["workflow_cursor"]
    assert cursor["phase"] == "gate"
    assert cursor["dispatch_phase"] == "gate"
    assert cursor["next_dispatch_phases"] == [
        "finalize",
        "revise",
        "tiebreaker_run",
        "override",
        "halt",
    ]


def test_project_events_maps_legacy_tiebreaker_phase_to_source_cursor() -> None:
    store = _FakeStore(
        (
            StoredEvent(
                kind="phase_end",
                phase="tiebreaker-run",
                payload={"phase": "tiebreaker-run"},
                source="file",
            ),
        )
    )

    projected = project_events(store, "demo")

    assert len(projected) == 1
    cursor = projected[0]["workflow_cursor"]
    assert cursor["phase"] == "tiebreaker_researcher"
    assert cursor["dispatch_phase"] == "tiebreaker_run"
    assert cursor["next_phases"] == ["tiebreaker_challenger"]
