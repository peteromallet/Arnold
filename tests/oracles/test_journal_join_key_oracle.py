"""M4 T10 — Substrate-swap oracle: journals share the run_id join key.

Property: regardless of which observability backend (NDJSON file or Store
epic-event table) an emit lands in, when an envelope is in scope the
resolved ``run_id`` is the SAME for both — so a downstream join over
``run_id`` correlates a journal record with its NDJSON event.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from arnold.runtime.envelope import make_envelope
from arnold.pipelines.megaplan.observability import NdjsonBackend, StoreBackend
from arnold.pipelines.megaplan.observability.events import _envelope_ctx, read_events


@pytest.mark.substrate_swap
def test_run_id_consistent_across_ndjson_and_store(tmp_path: Path):
    captured: list[dict] = []

    class FakeStore:
        def record_epic_event(self, **fields):
            captured.append(fields)
            return fields

    env = make_envelope(lineage=("run-42",))
    token = _envelope_ctx.set(env)
    try:
        NdjsonBackend(tmp_path).emit("k1", payload={"a": 1})
        StoreBackend(FakeStore()).emit("k2", payload={"a": 2}, scope="ep-1")
    finally:
        _envelope_ctx.reset(token)

    ndjson_events = list(read_events(tmp_path))
    assert ndjson_events[-1]["run_id"] == "run-42"
    assert captured[-1]["run_id"] == "run-42"
    # Both journals carry the same join key under the same envelope.
    assert ndjson_events[-1]["run_id"] == captured[-1]["run_id"]


@pytest.mark.substrate_swap
def test_missing_envelope_omits_run_id_consistently(tmp_path: Path):
    """When no envelope is in scope, both backends omit run_id (consistent)."""
    captured: list[dict] = []

    class FakeStore:
        def record_epic_event(self, **fields):
            captured.append(fields)
            return fields

    NdjsonBackend(tmp_path).emit("k1", payload={})
    StoreBackend(FakeStore()).emit("k2", payload={}, scope="ep-1")

    ndjson_events = list(read_events(tmp_path))
    assert "run_id" not in ndjson_events[-1]
    assert "run_id" not in captured[-1]
