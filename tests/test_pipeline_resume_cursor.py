"""Tests for ResumeCursor + with_entry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from megaplan._pipeline.resume import ResumeCursor, with_entry
from megaplan._pipeline.types import Edge, Pipeline, Stage, StepResult, StepContext


def test_load_none_when_no_state_file(tmp_path: Path) -> None:
    assert ResumeCursor.load(tmp_path) is None


def test_load_none_when_no_resume_cursor_key(tmp_path: Path) -> None:
    (tmp_path / "state.json").write_text(json.dumps({"current_state": "planned"}))
    assert ResumeCursor.load(tmp_path) is None


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    cursor = ResumeCursor(stage="critique", payload={"retry_strategy": "fresh"})
    cursor.save(tmp_path)

    reloaded = ResumeCursor.load(tmp_path)
    assert reloaded is not None
    assert reloaded.stage == "critique"
    assert reloaded.payload["retry_strategy"] == "fresh"


def test_save_preserves_other_state_keys(tmp_path: Path) -> None:
    (tmp_path / "state.json").write_text(
        json.dumps({"current_state": "planned", "history": [{"step": "plan"}]})
    )
    ResumeCursor(stage="critique").save(tmp_path)

    data = json.loads((tmp_path / "state.json").read_text())
    assert data["current_state"] == "planned"
    assert data["history"] == [{"step": "plan"}]
    assert data["resume_cursor"]["phase"] == "critique"


def test_load_reads_legacy_phase_key(tmp_path: Path) -> None:
    """The legacy schema uses 'phase' as the stage key."""
    (tmp_path / "state.json").write_text(
        json.dumps({"resume_cursor": {"phase": "gate", "retry_strategy": "fresh"}})
    )
    cursor = ResumeCursor.load(tmp_path)
    assert cursor is not None and cursor.stage == "gate"
    assert cursor.payload["retry_strategy"] == "fresh"


def test_load_reads_stage_key_alias(tmp_path: Path) -> None:
    (tmp_path / "state.json").write_text(
        json.dumps({"resume_cursor": {"stage": "execute"}})
    )
    cursor = ResumeCursor.load(tmp_path)
    assert cursor is not None and cursor.stage == "execute"


def test_with_payload_returns_immutable_copy() -> None:
    a = ResumeCursor(stage="critique", payload={"retry": 1})
    b = a.with_payload(retry=2, extra="x")
    assert a.payload == {"retry": 1}
    assert b.payload == {"retry": 2, "extra": "x"}
    assert a.stage == b.stage


# -----------------------------------------------------------------------
# with_entry helper
# -----------------------------------------------------------------------


class _Noop:
    name = "noop"
    kind = "produce"
    prompt_key = None
    slot = None

    def run(self, ctx):
        return StepResult(next="halt")


def _trivial_pipeline() -> Pipeline:
    return Pipeline(
        stages={
            "a": Stage(name="a", step=_Noop(), edges=(Edge("halt", "halt"),)),
            "b": Stage(name="b", step=_Noop(), edges=(Edge("halt", "halt"),)),
        },
        entry="a",
    )


def test_with_entry_returns_new_pipeline_at_named_stage() -> None:
    original = _trivial_pipeline()
    rerouted = with_entry(original, "b")
    assert rerouted.entry == "b"
    assert original.entry == "a"  # original unchanged
    assert rerouted.stages is original.stages  # stages shared (frozen)


def test_with_entry_raises_for_unknown_stage() -> None:
    with pytest.raises(KeyError, match="not in pipeline"):
        with_entry(_trivial_pipeline(), "ghost")
