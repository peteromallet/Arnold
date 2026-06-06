"""Tests for ResumeCursor, composite suspension cursors, and with_entry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._pipeline.resume import (
    COMPOSITE_SUSPENSION_CURSOR_VERSION,
    COMPOSITE_SUSPENSION_KIND,
    ResumeCursor,
    extract_all_composite_child_resume_cursors,
    extract_composite_child_resume_cursor,
    is_composite_resume_cursor,
    load_composite_resume_cursor,
    load_resume_cursor_payload,
    save_composite_resume_cursor,
    with_entry,
)
from arnold.pipelines.megaplan._pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult


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


# ---------------------------------------------------------------------------
# Composite suspension cursor helpers
# ---------------------------------------------------------------------------


def _composite_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": COMPOSITE_SUSPENSION_KIND,
        "version": COMPOSITE_SUSPENSION_CURSOR_VERSION,
        "children": {
            "child_a": {"suspended": True, "label": "a"},
            "child_b": {"suspended": False, "label": "b"},
        },
    }
    payload.update(overrides)
    return payload


def _write_state_json(plan_dir: Path, data: dict[str, object]) -> Path:
    path = plan_dir / "state.json"
    path.write_text(json.dumps(data))
    return path


# ---- load_resume_cursor_payload ----

def test_load_resume_cursor_payload_returns_none_when_no_file(tmp_path: Path) -> None:
    assert load_resume_cursor_payload(tmp_path) is None


def test_load_resume_cursor_payload_returns_none_when_no_key(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {"current_state": "planned"})
    assert load_resume_cursor_payload(tmp_path) is None


def test_load_resume_cursor_payload_returns_dict(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {"resume_cursor": {"phase": "critique", "retry_strategy": "fresh"}})
    result = load_resume_cursor_payload(tmp_path)
    assert result == {"phase": "critique", "retry_strategy": "fresh"}


def test_load_resume_cursor_payload_returns_none_for_non_dict_cursor(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {"resume_cursor": "not_a_dict"})
    assert load_resume_cursor_payload(tmp_path) is None


def test_load_resume_cursor_payload_returns_none_for_bad_json(tmp_path: Path) -> None:
    (tmp_path / "state.json").write_text("{not valid json")
    assert load_resume_cursor_payload(tmp_path) is None


# ---- is_composite_resume_cursor ----

def test_is_composite_positive(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {"resume_cursor": _composite_payload()})
    cursor = load_resume_cursor_payload(tmp_path)
    assert is_composite_resume_cursor(cursor) is True


def test_is_composite_negative_legacy(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {"resume_cursor": {"phase": "critique"}})
    cursor = load_resume_cursor_payload(tmp_path)
    assert is_composite_resume_cursor(cursor) is False


def test_is_composite_negative_none() -> None:
    assert is_composite_resume_cursor(None) is False


def test_is_composite_negative_empty_dict() -> None:
    assert is_composite_resume_cursor({}) is False


def test_is_composite_negative_wrong_kind() -> None:
    assert is_composite_resume_cursor({"kind": "something_else"}) is False


# ---- Composite cursor save/load round trip ----

def test_composite_save_and_reload_round_trip(tmp_path: Path) -> None:
    save_composite_resume_cursor(
        tmp_path,
        children={"child_a": {"suspended": True}},
    )
    cursor = load_composite_resume_cursor(tmp_path)
    assert cursor is not None
    assert cursor["kind"] == COMPOSITE_SUSPENSION_KIND
    assert cursor["version"] == COMPOSITE_SUSPENSION_CURSOR_VERSION
    assert cursor["children"] == {"child_a": {"suspended": True}}


def test_composite_cursor_preserves_children_data(tmp_path: Path) -> None:
    children = {
        "agent_1": {"suspended": True, "thread_ref": "th-001", "actor": "claude"},
        "agent_2": {"suspended": False},
        "agent_3": {"suspended": True, "display_refs": ["msg-1", "msg-2"]},
    }
    save_composite_resume_cursor(tmp_path, children=children)
    reloaded = load_composite_resume_cursor(tmp_path)
    assert reloaded is not None
    assert reloaded["children"] == children


def test_composite_cursor_version_field_round_trip(tmp_path: Path) -> None:
    save_composite_resume_cursor(tmp_path, children={}, version=7)
    reloaded = load_composite_resume_cursor(tmp_path)
    assert reloaded is not None
    assert reloaded["version"] == 7


def test_composite_cursor_preserves_extra_fields(tmp_path: Path) -> None:
    save_composite_resume_cursor(
        tmp_path,
        children={"c1": {}},
        shared_awaitable="gate-1",
        pending_suspensions=3,
    )
    reloaded = load_composite_resume_cursor(tmp_path)
    assert reloaded is not None
    assert reloaded["shared_awaitable"] == "gate-1"
    assert reloaded["pending_suspensions"] == 3


def test_composite_cursor_preserves_other_state_keys(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {"current_state": "executed", "history": [{"step": "plan"}]})
    save_composite_resume_cursor(tmp_path, children={"c1": {}})
    data = json.loads((tmp_path / "state.json").read_text())
    assert data["current_state"] == "executed"
    assert data["history"] == [{"step": "plan"}]
    assert data["resume_cursor"]["kind"] == COMPOSITE_SUSPENSION_KIND


def test_composite_save_creates_state_json_if_missing(tmp_path: Path) -> None:
    assert not (tmp_path / "state.json").exists()
    save_composite_resume_cursor(tmp_path, children={})
    assert (tmp_path / "state.json").exists()
    cursor = load_composite_resume_cursor(tmp_path)
    assert cursor is not None


# ---- Targeted child cursor extraction ----

def test_extract_targeted_child_from_composite(tmp_path: Path) -> None:
    save_composite_resume_cursor(
        tmp_path,
        children={"child_a": {"suspended": True}, "child_b": {"suspended": False}},
    )
    result = extract_composite_child_resume_cursor(tmp_path, "child_a")
    assert result == {"suspended": True}


def test_extract_second_child_from_composite(tmp_path: Path) -> None:
    save_composite_resume_cursor(
        tmp_path,
        children={"child_a": {"suspended": True}, "child_b": {"suspended": False}},
    )
    result = extract_composite_child_resume_cursor(tmp_path, "child_b")
    assert result == {"suspended": False}


def test_extract_nonexistent_child_returns_none(tmp_path: Path) -> None:
    save_composite_resume_cursor(tmp_path, children={"child_a": {}})
    assert extract_composite_child_resume_cursor(tmp_path, "ghost") is None


def test_extract_child_from_non_composite_returns_none(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {"resume_cursor": {"phase": "critique"}})
    assert extract_composite_child_resume_cursor(tmp_path, "any") is None


def test_extract_child_when_no_cursor_returns_none(tmp_path: Path) -> None:
    assert extract_composite_child_resume_cursor(tmp_path, "any") is None


def test_extract_child_when_children_not_a_dict(tmp_path: Path) -> None:
    payload = _composite_payload()
    payload["children"] = "not_a_dict"  # type: ignore[assignment]
    _write_state_json(tmp_path, {"resume_cursor": payload})
    assert extract_composite_child_resume_cursor(tmp_path, "any") is None


# ---- Batch child cursor extraction ----

def test_extract_all_children_from_composite(tmp_path: Path) -> None:
    children = {"a": {"x": 1}, "b": {"y": 2}, "c": {"z": 3}}
    save_composite_resume_cursor(tmp_path, children=children)
    result = extract_all_composite_child_resume_cursors(tmp_path)
    assert result == children


def test_extract_all_children_empty_composite(tmp_path: Path) -> None:
    save_composite_resume_cursor(tmp_path, children={})
    result = extract_all_composite_child_resume_cursors(tmp_path)
    assert result == {}


def test_extract_all_children_from_non_composite_returns_empty(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {"resume_cursor": {"phase": "critique"}})
    assert extract_all_composite_child_resume_cursors(tmp_path) == {}


def test_extract_all_children_when_no_cursor_returns_empty(tmp_path: Path) -> None:
    assert extract_all_composite_child_resume_cursors(tmp_path) == {}


def test_extract_all_children_when_children_not_a_dict(tmp_path: Path) -> None:
    payload = _composite_payload()
    payload["children"] = [1, 2, 3]  # type: ignore[assignment]
    _write_state_json(tmp_path, {"resume_cursor": payload})
    assert extract_all_composite_child_resume_cursors(tmp_path) == {}


def test_extract_all_children_keys_are_strings(tmp_path: Path) -> None:
    save_composite_resume_cursor(tmp_path, children={1: "a", 2: "b"})
    result = extract_all_composite_child_resume_cursors(tmp_path)
    assert set(result.keys()) == {"1", "2"}


# ---- Process-like reload from disk ----

def test_composite_cursor_survives_disk_reload(tmp_path: Path) -> None:
    """Simulate a process restart: save, then load in a 'fresh' context."""
    save_composite_resume_cursor(
        tmp_path,
        children={"agent_1": {"suspended": True, "thread_ref": "th-99"}},
        shared_awaitable="gate-main",
    )
    # Simulate fresh process: re-read the raw JSON
    raw = json.loads((tmp_path / "state.json").read_text())
    assert raw["resume_cursor"]["kind"] == COMPOSITE_SUSPENSION_KIND
    assert raw["resume_cursor"]["children"]["agent_1"]["thread_ref"] == "th-99"
    # Also verify through the official loader
    reloaded = load_composite_resume_cursor(tmp_path)
    assert reloaded is not None
    assert reloaded["children"]["agent_1"]["suspended"] is True


def test_composite_child_integrity_after_reload(tmp_path: Path) -> None:
    children = {
        "w1": {"suspended": True, "actor": "claude", "display_refs": ["a", "b"]},
        "w2": {"suspended": False},
    }
    save_composite_resume_cursor(tmp_path, children=children, pending_suspensions=1)
    # Reload raw JSON
    raw = json.loads((tmp_path / "state.json").read_text())
    assert raw["resume_cursor"]["children"] == children
    assert raw["resume_cursor"]["pending_suspensions"] == 1
    # Extract individual child
    child = extract_composite_child_resume_cursor(tmp_path, "w1")
    assert child == {"suspended": True, "actor": "claude", "display_refs": ["a", "b"]}


def test_legacy_cursor_survives_disk_reload(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {"resume_cursor": {"phase": "execute", "retry_strategy": "fresh"}})
    raw = json.loads((tmp_path / "state.json").read_text())
    assert raw["resume_cursor"]["phase"] == "execute"
    assert raw["resume_cursor"]["retry_strategy"] == "fresh"
    cursor = ResumeCursor.load(tmp_path)
    assert cursor is not None
    assert cursor.stage == "execute"
    assert cursor.payload["retry_strategy"] == "fresh"


def test_composite_and_legacy_can_be_distinguished_on_reload(tmp_path: Path) -> None:
    """Both share state.json::resume_cursor but discriminator separates them."""
    # Save composite
    save_composite_resume_cursor(tmp_path, children={"c1": {}})
    # Legacy load should return None
    assert ResumeCursor.load(tmp_path) is None
    # Composite load should succeed
    assert load_composite_resume_cursor(tmp_path) is not None
    # Now overwrite with legacy
    ResumeCursor(stage="gate").save(tmp_path, overwrite_composite=True)
    # Legacy load should succeed
    assert ResumeCursor.load(tmp_path) is not None
    # Composite load should return None
    assert load_composite_resume_cursor(tmp_path) is None


# ---- ResumeCursor.load() ignoring composite cursors ----

def test_load_returns_none_for_composite_cursor(tmp_path: Path) -> None:
    save_composite_resume_cursor(tmp_path, children={"c1": {}})
    assert ResumeCursor.load(tmp_path) is None


def test_load_returns_none_when_composite_and_other_state_keys(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {
        "current_state": "executed",
        "resume_cursor": _composite_payload(),
        "history": [{"step": "plan"}],
    })
    assert ResumeCursor.load(tmp_path) is None
    # Other state keys are unmodified
    data = json.loads((tmp_path / "state.json").read_text())
    assert data["current_state"] == "executed"
    assert data["history"] == [{"step": "plan"}]


def test_load_returns_none_for_composite_with_phase_key(tmp_path: Path) -> None:
    """Even if 'phase' is present, kind='composite_suspension' wins."""
    payload = _composite_payload()
    payload["phase"] = "gate"
    _write_state_json(tmp_path, {"resume_cursor": payload})
    assert ResumeCursor.load(tmp_path) is None


def test_legacy_load_unaffected_by_composite_helper(tmp_path: Path) -> None:
    """Legacy ResumeCursor.load() still works alongside composite helper imports."""
    ResumeCursor(stage="review", payload={"flag": True}).save(tmp_path)
    cursor = ResumeCursor.load(tmp_path)
    assert cursor is not None
    assert cursor.stage == "review"
    assert cursor.payload["flag"] is True


# ---- Guard against accidental legacy overwrite ----

def test_legacy_save_raises_when_composite_exists(tmp_path: Path) -> None:
    save_composite_resume_cursor(tmp_path, children={"c1": {}})
    with pytest.raises(ValueError, match="composite suspension"):
        ResumeCursor(stage="critique").save(tmp_path)


def test_legacy_save_raises_descriptive_error(tmp_path: Path) -> None:
    save_composite_resume_cursor(tmp_path, children={"c1": {}})
    with pytest.raises(ValueError) as exc_info:
        ResumeCursor(stage="critique").save(tmp_path)
    msg = str(exc_info.value)
    assert "composite suspension cursor" in msg.lower() or "composite" in msg.lower()
    assert "save_composite_resume_cursor" in msg or "overwrite_composite" in msg


def test_legacy_save_with_overwrite_composite_succeeds(tmp_path: Path) -> None:
    save_composite_resume_cursor(tmp_path, children={"c1": {}})
    ResumeCursor(stage="gate", payload={"flag": 1}).save(tmp_path, overwrite_composite=True)
    cursor = ResumeCursor.load(tmp_path)
    assert cursor is not None
    assert cursor.stage == "gate"
    assert cursor.payload["flag"] == 1
    # Composite loader should now return None
    assert load_composite_resume_cursor(tmp_path) is None


def test_legacy_save_with_overwrite_composite_preserves_other_keys(tmp_path: Path) -> None:
    _write_state_json(tmp_path, {
        "current_state": "executed",
        "resume_cursor": _composite_payload(),
        "history": [{"step": "plan"}],
    })
    ResumeCursor(stage="review").save(tmp_path, overwrite_composite=True)
    data = json.loads((tmp_path / "state.json").read_text())
    assert data["current_state"] == "executed"
    assert data["history"] == [{"step": "plan"}]
    assert data["resume_cursor"]["phase"] == "review"


def test_composite_save_not_blocked_by_guard(tmp_path: Path) -> None:
    """save_composite_resume_cursor should always work regardless of existing cursor."""
    # Start with legacy cursor
    ResumeCursor(stage="plan").save(tmp_path)
    # Composite save should succeed
    save_composite_resume_cursor(tmp_path, children={"c1": {}})
    assert load_composite_resume_cursor(tmp_path) is not None
    # Legacy load should now see composite and return None
    assert ResumeCursor.load(tmp_path) is None


def test_legacy_save_no_guard_when_no_composite(tmp_path: Path) -> None:
    """Legacy save should work normally when no composite cursor exists."""
    ResumeCursor(stage="critique").save(tmp_path)
    # Second save works fine
    ResumeCursor(stage="execute", payload={"retry": 1}).save(tmp_path)
    cursor = ResumeCursor.load(tmp_path)
    assert cursor is not None
    assert cursor.stage == "execute"
    assert cursor.payload["retry"] == 1


def test_legacy_save_no_guard_when_legacy_exists(tmp_path: Path) -> None:
    """Legacy save should not raise when only a legacy cursor exists."""
    ResumeCursor(stage="plan").save(tmp_path)
    # Should not raise - only composite cursors trigger the guard
    ResumeCursor(stage="critique").save(tmp_path)
    cursor = ResumeCursor.load(tmp_path)
    assert cursor is not None
    assert cursor.stage == "critique"


def test_legacy_save_guard_fires_only_for_composite_kind(tmp_path: Path) -> None:
    """Only kind='composite_suspension' triggers the guard, not other kinds."""
    _write_state_json(tmp_path, {"resume_cursor": {"kind": "some_other_kind", "phase": "plan"}})
    # Should not raise - only COMPOSITE_SUSPENSION_KIND triggers the guard
    ResumeCursor(stage="critique").save(tmp_path)
    cursor = ResumeCursor.load(tmp_path)
    assert cursor is not None
    assert cursor.stage == "critique"
