"""Tests for the EVALUAND_JUDGMENT event kind + emit_evaluand (M5-eval T2)."""

from __future__ import annotations

from pathlib import Path

from megaplan.observability import EvaluandRecord, emit_evaluand
from megaplan.observability.events import EventKind, read_events


def _record() -> EvaluandRecord:
    return EvaluandRecord(
        piece_version="piece-1",
        judge_version="judge-1",
        rubric_version="rubric-1",
        input_set_hash="input-hash",
        score=0.75,
        provenance={"source": "test"},
        taint="trusted",
        recorded_at="2026-05-31T00:00:00Z",
        model_identity="model-id",
        prompt_hash_canonical="canon-hash",
        prompt_hash_raw="raw-hash",
    )


def test_emit_and_read_roundtrip(tmp_path: Path) -> None:
    rec = _record()
    emit_evaluand(tmp_path, rec)
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["record"] == dict(rec)
    assert payload["schema_version"] == 0
    assert payload["taint"] == "trusted"


def test_explicit_schema_version_zero_preserved(tmp_path: Path) -> None:
    emit_evaluand(tmp_path, _record(), schema_version=0)
    events = list(read_events(tmp_path, kinds=[EventKind.EVALUAND_JUDGMENT]))
    assert events[0]["payload"]["schema_version"] == 0


def test_top_level_imports_succeed() -> None:
    from megaplan.observability import EvaluandRecord as ER, emit_evaluand as ee

    assert ER is EvaluandRecord
    assert ee is emit_evaluand


def test_event_kind_count_includes_evaluand() -> None:
    from megaplan.observability.events import _ALL_EVENT_KINDS

    assert EventKind.EVALUAND_JUDGMENT in _ALL_EVENT_KINDS
    assert len(_ALL_EVENT_KINDS) == 28
