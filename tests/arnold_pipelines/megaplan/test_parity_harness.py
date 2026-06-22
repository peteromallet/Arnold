"""Normalized parity harness for legacy vs manifest-backed Megaplan runs.

Helpers here compile the canonical M3 pipeline, run it through a configurable
fake backend, normalize volatile fields, and compare artifact hashes, decisions,
capability invocations, suspension points, control transitions, and event
sequences.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pytest

from arnold.execution import run as run_manifest
from arnold.execution.backend import ExecutionContext, LocalJournalBackend, NodeOutcome, NodeState
from arnold.execution.registries import ExecutionRegistries
from arnold.execution.state import RouteCoordinate
from arnold.execution.state_store import FileStateStore
from arnold.kernel import read_event_journal
from arnold.kernel.events import EventEnvelope, ManifestReference
from arnold.manifest import WorkflowManifest, WorkflowNode

from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline
from arnold_pipelines.megaplan.runtime.manifest_backend import MegaplanManifestBackend


# ---------------------------------------------------------------------------
# Volatile field normalization
# ---------------------------------------------------------------------------

VOLATILE_SCALAR_KEYS: frozenset[str] = frozenset({
    "run_id",
    "event_id",
    "timestamp",
    "duration_ms",
    "absolute_path",
    "model_latency",
    "token_count",
    "cost_usd",
    "actual_cost",
    "actual_seconds",
    "actual_tokens",
    "session_id",
    "attempt",
})


def normalize_value(value: object) -> object:
    """Replace volatile scalar values with a canonical placeholder."""

    if isinstance(value, str):
        # Absolute paths and uuids/timestamps are volatile.
        if value.startswith(("/", "run:", "sha256:", "event:")) or "/" in value:
            return "<normalized>"
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "<normalized>"
    return value


def normalize_event_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of an event payload with volatile fields scrubbed."""

    result: dict[str, Any] = {}
    for key, value in sorted(payload.items()):
        if key in VOLATILE_SCALAR_KEYS:
            result[key] = "<normalized>"
        elif isinstance(value, dict):
            result[key] = normalize_event_payload(value)
        elif isinstance(value, list):
            result[key] = [
                normalize_event_payload(item) if isinstance(item, dict) else normalize_value(item)
                for item in value
            ]
        else:
            result[key] = normalize_value(value)
    return result


def normalize_events(events: Sequence[EventEnvelope]) -> list[dict[str, Any]]:
    """Normalize a sequence of journal events for deterministic comparison."""

    normalized: list[dict[str, Any]] = []
    for event in events:
        normalized.append(
            {
                "kind": event.kind,
                "family": event.family,
                "payload": normalize_event_payload(event.payload),
            }
        )
    return normalized


def event_sequence(events: Sequence[EventEnvelope]) -> list[str]:
    """Return just the ordered event kinds, useful for coarse parity checks."""

    return [e.kind for e in events]


def completed_nodes(events: Sequence[EventEnvelope]) -> list[str]:
    """Return node_ref values for node_completed events in order."""

    return [
        e.payload.get("node_ref")
        for e in events
        if e.kind == "node_completed" and isinstance(e.payload.get("node_ref"), str)
    ]


def branch_selections(events: Sequence[EventEnvelope]) -> list[tuple[str, str]]:
    """Return (node_ref, edge_id) for branch_selected events."""

    return [
        (e.payload.get("node_ref"), e.payload.get("edge_id"))
        for e in events
        if e.kind == "branch_selected"
    ]


def control_transitions(events: Sequence[EventEnvelope]) -> list[dict[str, Any]]:
    """Return normalized control_transition payloads."""

    return [
        normalize_event_payload(e.payload)
        for e in events
        if e.kind == "control_transition"
    ]


def suspension_points(events: Sequence[EventEnvelope]) -> list[tuple[str, str]]:
    """Return (node_ref, route_id) for node_suspended events."""

    return [
        (e.payload.get("node_ref"), e.payload.get("route_id"))
        for e in events
        if e.kind == "node_suspended"
    ]


# ---------------------------------------------------------------------------
# Fake Megaplan backend
# ---------------------------------------------------------------------------

StepResponse = dict[str, Any]
HandlerFactory = Callable[[str], Callable[[Path, argparse.Namespace], StepResponse]]


class FakeMegaplanBackend(MegaplanManifestBackend):
    """Megaplan backend that dispatches to in-memory fake handlers.

    This lets parity tests drive the real compiled manifest topology without
    invoking LLMs, git, or subprocesses.
    """

    def __init__(
        self,
        *,
        plan_dir: Path,
        handlers: Mapping[str, Callable[[Path, argparse.Namespace], StepResponse]] | None = None,
        state: Mapping[str, Any] | None = None,
        args: argparse.Namespace | None = None,
        run_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            plan_dir=plan_dir,
            state=dict(state or {}),
            args=args or argparse.Namespace(),
            run_id=run_id,
            **kwargs,
        )
        self._fake_handlers: dict[str, Callable[[Path, argparse.Namespace], StepResponse]] = dict(
            handlers or {}
        )

    def _resolve_handler(self, node_id: str):
        if node_id in self._fake_handlers:
            return self._fake_handlers[node_id]
        # Default pass-through for unregistered handler nodes (e.g. halt).
        return make_simple_handler({"success": True, "node_id": node_id})


def make_simple_handler(
    response: StepResponse,
) -> Callable[[Path, argparse.Namespace], StepResponse]:
    """Return a handler callable that ignores inputs and returns *response*."""

    def _handler(root: Path, args: argparse.Namespace) -> StepResponse:
        return dict(response)

    return _handler


def run_fake_manifest(
    manifest: WorkflowManifest,
    *,
    plan_dir: Path,
    handlers: Mapping[str, Callable[[Path, argparse.Namespace], StepResponse]],
    artifact_root: Path,
    state: Mapping[str, Any] | None = None,
    args: argparse.Namespace | None = None,
    registries: ExecutionRegistries | None = None,
    run_id: str = "parity-run",
) -> tuple[Any, list[EventEnvelope]]:
    """Run a compiled manifest through FakeMegaplanBackend and return result + events."""

    backend = FakeMegaplanBackend(
        plan_dir=plan_dir,
        handlers=handlers,
        state=state,
        args=args,
        run_id=run_id,
    )
    result = run_manifest(
        manifest,
        artifact_root=artifact_root,
        backend=backend,
        registries=registries or ExecutionRegistries(),
    )
    events = list(read_event_journal(artifact_root))
    return result, events


# ---------------------------------------------------------------------------
# Topology locks
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LockedTopology:
    """Canonical topology invariants for the M4 Megaplan manifest."""

    manifest_hash: str
    topology_hash: str
    node_ids: frozenset[str]
    gate_targets: frozenset[str]
    tiebreaker_targets: frozenset[str]
    review_targets: frozenset[str]
    capabilities: frozenset[str]


M4_LOCKED_TOPOLOGY = LockedTopology(
    manifest_hash="sha256:245a06ac778caf20c645772b7c0570655af7a79a0d00eda959b19d2cf01a3eba",
    topology_hash="sha256:2705e157e12fc074301afa8f5aec4e48d9820814ebaaa77535d152a8cc381fd4",
    node_ids=frozenset({
        "prep",
        "plan",
        "critique",
        "gate",
        "revise",
        "tiebreaker_run",
        "tiebreaker_decide",
        "finalize",
        "execute",
        "review",
        "halt",
        "override",
    }),
    gate_targets=frozenset({"finalize", "revise", "tiebreaker_run", "override", "halt"}),
    tiebreaker_targets=frozenset({"critique", "finalize", "override"}),
    review_targets=frozenset({"halt", "revise"}),
    capabilities=frozenset({"megaplan:planning", "human:gate", "human:review"}),
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _make_event(family: str, kind: str, payload: dict[str, Any]) -> EventEnvelope:
    return EventEnvelope(
        event_id="event:1",
        family=family,
        kind=kind,
        manifest=ManifestReference(alias="megaplan", manifest_hash="sha256:" + "0" * 64),
        run_id="run:test",
        payload_schema_hash="sha256:" + "0" * 64,
        payload=payload,
    )


class TestParityHarnessHelpers:
    def test_normalize_events_scrubs_volatile_fields(self) -> None:
        events = [
            _make_event(
                family="run",
                kind="run_started",
                payload={"run_id": "run:abc", "timestamp": "2026-01-01T00:00:00Z"},
            ),
            _make_event(
                family="node",
                kind="node_completed",
                payload={"node_ref": "gate", "duration_ms": 123, "cost_usd": 0.05},
            ),
        ]
        normalized = normalize_events(events)
        assert normalized[0]["payload"]["run_id"] == "<normalized>"
        assert normalized[0]["payload"]["timestamp"] == "<normalized>"
        assert normalized[1]["payload"]["node_ref"] == "gate"
        assert normalized[1]["payload"]["duration_ms"] == "<normalized>"

    def test_branch_selections_extracted(self) -> None:
        events = [
            _make_event(
                family="node",
                kind="branch_selected",
                payload={"node_ref": "gate", "edge_id": "iterate"},
            ),
        ]
        assert branch_selections(events) == [("gate", "iterate")]


class TestCompiledTopologyLock:
    def test_m4_manifest_hashes_match_locked_topology(self) -> None:
        manifest = build_and_compile_pipeline()
        assert manifest.id == "megaplan"
        assert manifest.manifest_hash == M4_LOCKED_TOPOLOGY.manifest_hash
        assert manifest.topology_hash == M4_LOCKED_TOPOLOGY.topology_hash

    def test_m4_nodes_and_edges_cover_expected_surface(self) -> None:
        manifest = build_and_compile_pipeline()
        node_ids = {n.id for n in manifest.nodes}
        assert node_ids == M4_LOCKED_TOPOLOGY.node_ids

        gate_edges = {
            (e.target, e.label)
            for e in manifest.edges
            if e.source == "gate"
        }
        assert gate_edges == {
            ("finalize", "proceed"),
            ("revise", "iterate"),
            ("tiebreaker_run", "tiebreaker"),
            ("override", "escalate"),
            ("halt", "abort"),
            ("halt", "suspend"),
            ("override", "blocked_preflight"),
            ("finalize", "force_proceed"),
        }

    def test_m4_capabilities_declared(self) -> None:
        manifest = build_and_compile_pipeline()
        cap_ids = {c.capability_id for c in manifest.capabilities}
        assert cap_ids == M4_LOCKED_TOPOLOGY.capabilities


class TestFakeBackendRunsManifest:
    def test_fake_backend_drives_full_pipeline(self, tmp_path: Path) -> None:
        manifest = build_and_compile_pipeline()
        plan_dir = tmp_path / "plans" / "parity"
        plan_dir.mkdir(parents=True)

        handlers = {
            "prep": make_simple_handler({"success": True, "next_step": "plan"}),
            "plan": make_simple_handler({"success": True, "next_step": "critique"}),
            "critique": make_simple_handler({"success": True, "next_step": "gate"}),
            "gate": make_simple_handler({"success": True, "recommendation": "PROCEED"}),
            "finalize": make_simple_handler({"success": True, "next_step": "execute"}),
            "execute": make_simple_handler({"success": True, "next_step": "review"}),
            "review": make_simple_handler({"success": True, "verdict": "pass"}),
        }

        result, events = run_fake_manifest(
            manifest,
            plan_dir=plan_dir,
            handlers=handlers,
            artifact_root=tmp_path / "artifacts",
        )

        assert result.state.name == "COMPLETED"
        assert completed_nodes(events) == [
            "prep", "plan", "critique", "gate", "finalize", "execute", "review", "halt"
        ]
