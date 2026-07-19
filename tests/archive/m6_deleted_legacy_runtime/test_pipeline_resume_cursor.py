"""Tests for ResumeCursor, composite suspension cursors, and with_entry."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

pytest.skip("archived deleted pipeline resume cursor runtime", allow_module_level=True)

import arnold_pipelines.megaplan.cli as megaplan_cli
from arnold_pipelines.megaplan._core.workflow import resume_plan
from arnold_pipelines.megaplan._pipeline.resume import (
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
from arnold_pipelines.megaplan.types import CliError
from arnold_pipelines.megaplan._pipeline.types import Edge, Pipeline, Stage, StepContext, StepResult


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


def test_resume_execute_divergent_completion_preserves_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_megaplan_resume(monkeypatch)
    plan_dir = _write_resume_plan(
        tmp_path,
        "resume-execute-divergent",
        phase="execute",
        tasks=[{"id": "T1", "status": "done", "depends_on": []}],
    )

    result = resume_plan(tmp_path, "resume-execute-divergent")

    state = json.loads((plan_dir / "state.json").read_text())
    assert result["success"] is False
    assert result["authority"]["reason"] == "execute_authority_diverged"
    assert result["authority"]["missing_task_ids"] == ["T1"]
    assert state["current_state"] == "blocked"
    assert state["resume_cursor"]["phase"] == "execute"


def test_resume_later_phase_blocks_on_incomplete_execute_authority_before_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_megaplan_resume(monkeypatch)
    plan_dir = _write_resume_plan(
        tmp_path,
        "resume-review-incomplete",
        phase="review",
        tasks=[],
    )

    with pytest.raises(CliError) as exc_info:
        resume_plan(tmp_path, "resume-review-incomplete")

    state = json.loads((plan_dir / "state.json").read_text())
    assert exc_info.value.code == "resume_execute_authority_blocked"
    assert exc_info.value.extra["reason"] == "execute_authority_unknown"
    assert state["current_state"] == "blocked"
    assert state["resume_cursor"]["phase"] == "review"


def test_resume_plan_prefers_state_resume_cursor_over_typed_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    _stub_megaplan_resume(monkeypatch)
    plan_dir = _write_resume_plan(
        tmp_path,
        "resume-state-over-typed",
        phase="critique",
    )
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state["resume_cursor"] = {"phase": "critique", "retry_strategy": "state-first"}
    state["contract_result"] = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            prompt="Typed fallback",
            resume_cursor=json.dumps({"phase": "execute", "retry_strategy": "typed"}),
        ),
    ).to_json()
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    result = resume_plan(tmp_path, "resume-state-over-typed")

    assert result["success"] is True
    assert result["phase"] == "critique"


def test_resume_plan_routes_native_born_megaplan_cursor_to_canonical_native_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan._core import workflow
    from arnold_pipelines.megaplan._pipeline import registry

    _stub_megaplan_resume(monkeypatch)
    plan_dir = _write_resume_plan(tmp_path, "resume-native-born", phase="plan")
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state["resume_cursor"] = {
        "phase": "plan",
        "retry_strategy": "fresh_session",
        "native": {"pc": 1, "version": 1},
    }
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    called: dict[str, object] = {}

    def fake_native_resume(**kwargs):  # noqa: ANN003
        called.update(kwargs)
        return 0, '{"ok": true}', ""

    monkeypatch.setattr(workflow, "_run_canonical_native_resume", fake_native_resume)
    monkeypatch.setattr(
        registry,
        "dispatch_operation_for",
        lambda *_args, **_kwargs: pytest.fail("native-born resume used graph operation"),
    )

    result = resume_plan(tmp_path, "resume-native-born")

    assert result["success"] is True
    assert result["phase"] == "plan"
    assert called["plan_dir"] == plan_dir
    assert called["plan"] == "resume-native-born"


def test_resume_plan_preserves_graph_born_resume_operation_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold_pipelines.megaplan._core import workflow
    from arnold_pipelines.megaplan import registry

    _stub_megaplan_resume(monkeypatch)
    plan_dir = _write_resume_plan(tmp_path, "resume-graph-born", phase="plan")

    monkeypatch.setattr(
        workflow,
        "_run_canonical_native_resume",
        lambda **_: pytest.fail("graph-born cursor used native dispatch"),
    )
    operation_calls: list[object] = []

    def fake_dispatch(*args, **kwargs):  # noqa: ANN002, ANN003
        operation_calls.append((args, kwargs))
        return {"success": True, "exit_code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(registry, "dispatch_operation_for", fake_dispatch)

    result = resume_plan(tmp_path, "resume-graph-born")

    assert result["success"] is True
    assert result["phase"] == "plan"
    assert len(operation_calls) == 1
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert "resume_cursor" not in state


def test_resume_plan_prefers_typed_contract_over_awaiting_user_and_normalizes_envelope_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension
    from arnold.runtime.envelope import RuntimeEnvelope

    _stub_megaplan_resume(monkeypatch)
    plan_dir = _write_resume_plan(
        tmp_path,
        "resume-typed-over-awaiting",
        phase="critique",
    )
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state.pop("resume_cursor", None)
    state["_pipeline_paused_stage"] = "critique"
    state["contract_result"] = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            prompt="Typed prompt",
            thread_ref="typed-pipeline",
            resume_cursor=json.dumps({"retry_strategy": "typed"}),
        ),
    ).to_json()
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (plan_dir / "awaiting_user.json").write_text(
        json.dumps(
            {
                "message": "Legacy prompt",
                "pipeline": "legacy-pipeline",
                "choices": ["legacy"],
            }
        ),
        encoding="utf-8",
    )

    result = resume_plan(tmp_path, "resume-typed-over-awaiting")

    assert result["success"] is True
    assert result["phase"] == "critique"
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    envelope = RuntimeEnvelope.from_json(json.dumps(persisted["runtime_envelope"]))
    assert envelope.resume_cursor is not None
    assert envelope.resume_cursor.cursor["phase"] == "critique"
    assert envelope.resume_cursor.cursor["retry_strategy"] == "typed"


def test_resume_plan_uses_composite_cursor_file_before_awaiting_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipeline.resume import persist_composite_resume_cursor

    _stub_megaplan_resume(monkeypatch)
    plan_dir = _write_resume_plan(
        tmp_path,
        "resume-composite-before-awaiting",
        phase="critique",
    )
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state.pop("resume_cursor", None)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    persist_composite_resume_cursor(
        plan_dir,
        children={"child-a": {"token": 1}},
        phase="critique",
    )
    (plan_dir / "awaiting_user.json").write_text(
        json.dumps({"message": "Legacy prompt", "pipeline": "legacy-pipeline"}),
        encoding="utf-8",
    )

    result = resume_plan(tmp_path, "resume-composite-before-awaiting")

    assert result["success"] is True
    assert result["phase"] == "critique"


def test_resume_plan_rejects_phase_less_composite_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipeline.resume import persist_composite_resume_cursor

    _stub_megaplan_resume(monkeypatch)
    plan_dir = _write_resume_plan(
        tmp_path,
        "resume-phase-less-composite",
        phase="review",
    )
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state.pop("resume_cursor", None)
    state.pop("_pipeline_paused_stage", None)
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    persist_composite_resume_cursor(
        plan_dir,
        children={"child-a": {"token": 1}},
    )

    with pytest.raises(CliError) as exc_info:
        resume_plan(tmp_path, "resume-phase-less-composite")

    assert exc_info.value.code == "invalid_resume_cursor"
    assert exc_info.value.extra["resume_cursor"]["kind"] == COMPOSITE_SUSPENSION_KIND


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


def _write_resume_plan(
    root: Path,
    plan_name: str,
    *,
    phase: str,
    current_state: str = "blocked",
    tasks: list[dict[str, object]] | None = None,
) -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True)
    _write_state_json(
        plan_dir,
        {
            "name": plan_name,
            "idea": "resume authority",
            "current_state": current_state,
            "iteration": 0,
            "created_at": "2026-01-01T00:00:00Z",
            "config": {"robustness": "full"},
            "sessions": {},
            "plan_versions": [],
            "history": [],
            "meta": {},
            "last_gate": {},
            "latest_failure": {"result": "failed", "phase": phase},
            "resume_cursor": {"phase": phase, "retry_strategy": "fresh_session"},
        },
    )
    if tasks is not None:
        (plan_dir / "finalize.json").write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    return plan_dir


def _stub_megaplan_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    from arnold_pipelines.megaplan._core import workflow
    from arnold_pipelines.megaplan._pipeline import registry

    monkeypatch.setattr(workflow, "preflight_phase", lambda **_: None)
    monkeypatch.setattr(workflow, "preflight_mutating_phase", lambda **_: None)
    monkeypatch.setattr(registry, "canonical_pipeline_name", lambda name: name)
    monkeypatch.setattr(
        registry,
        "dispatch_operation_for",
        lambda *_args, **_kwargs: {"success": True, "exit_code": 0, "stdout": "", "stderr": ""},
    )
    monkeypatch.setattr(registry, "resume_result_from_operation_result", lambda result, **_: result)


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


# ---------------------------------------------------------------------------
# Composite resume cursor fallback: recover from composite_resume_cursor.json
# when state.json::resume_cursor is absent
# ---------------------------------------------------------------------------


def _write_composite_json(plan_dir: Path, **kwargs: object) -> Path:
    """Write a ``composite_resume_cursor.json`` directly via the generic layer."""
    from arnold.pipeline.resume import persist_composite_resume_cursor

    return persist_composite_resume_cursor(plan_dir, **kwargs)  # type: ignore[arg-type]


def _composite_json_payload(
    children: dict[str, object] | None = None,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": COMPOSITE_SUSPENSION_KIND,
        "version": COMPOSITE_SUSPENSION_CURSOR_VERSION,
        "children": children or {},
    }
    payload.update(extra)
    return payload


def test_load_composite_from_json_when_state_missing(tmp_path: Path) -> None:
    """``load_composite_resume_cursor`` recovers from ``composite_resume_cursor.json``
    when ``state.json`` does not exist at all."""
    _write_composite_json(
        tmp_path,
        children={"child_a": {"suspended": True, "label": "a"}},
        version=COMPOSITE_SUSPENSION_CURSOR_VERSION,
        pending_suspensions=[{"child_id": "child_a", "suspension": {"kind": "human"}}],
    )
    # No state.json exists
    assert not (tmp_path / "state.json").exists()
    cursor = load_composite_resume_cursor(tmp_path)
    assert cursor is not None
    assert cursor["children"] == {"child_a": {"suspended": True, "label": "a"}}
    assert cursor["version"] == COMPOSITE_SUSPENSION_CURSOR_VERSION
    assert cursor["pending_suspensions"] == [
        {"child_id": "child_a", "suspension": {"kind": "human"}}
    ]


def test_load_composite_from_json_when_state_has_no_cursor(tmp_path: Path) -> None:
    """``load_composite_resume_cursor`` recovers from ``composite_resume_cursor.json``
    when ``state.json`` exists but has no ``resume_cursor`` key."""
    _write_state_json(tmp_path, {"current_state": "planned"})
    _write_composite_json(
        tmp_path,
        children={"child_b": {"suspended": False}},
    )
    cursor = load_composite_resume_cursor(tmp_path)
    assert cursor is not None
    assert cursor["children"] == {"child_b": {"suspended": False}}


def test_load_composite_from_json_when_state_has_legacy_cursor(tmp_path: Path) -> None:
    """``load_composite_resume_cursor`` recovers from ``composite_resume_cursor.json``
    when ``state.json::resume_cursor`` is a legacy (non-composite) cursor."""
    _write_state_json(tmp_path, {"resume_cursor": {"phase": "critique"}})
    _write_composite_json(
        tmp_path,
        children={"child_c": {"suspended": True}},
    )
    cursor = load_composite_resume_cursor(tmp_path)
    assert cursor is not None
    assert cursor["children"] == {"child_c": {"suspended": True}}
    # Legacy cursor is unaffected
    legacy = ResumeCursor.load(tmp_path)
    assert legacy is not None
    assert legacy.stage == "critique"


def test_load_composite_from_json_returns_none_when_neither_source(tmp_path: Path) -> None:
    """``load_composite_resume_cursor`` returns None when neither
    ``state.json::resume_cursor`` nor ``composite_resume_cursor.json`` exists."""
    assert load_composite_resume_cursor(tmp_path) is None


def test_load_composite_state_json_wins_over_json_file(tmp_path: Path) -> None:
    """When both ``state.json::resume_cursor`` and ``composite_resume_cursor.json``
    contain composite cursors, ``state.json::resume_cursor`` takes precedence."""
    _write_state_json(
        tmp_path,
        {
            "resume_cursor": _composite_payload(
                children={"primary": {"suspended": True, "source": "state"}},
            ),
        },
    )
    _write_composite_json(
        tmp_path,
        children={"secondary": {"suspended": False, "source": "json"}},
    )
    cursor = load_composite_resume_cursor(tmp_path)
    assert cursor is not None
    assert cursor["children"] == {"primary": {"suspended": True, "source": "state"}}
    assert "secondary" not in cursor["children"]


# ---- Targeted child extraction through fallback ----


def test_extract_child_from_json_fallback(tmp_path: Path) -> None:
    """``extract_composite_child_resume_cursor`` recovers individual children
    from ``composite_resume_cursor.json`` when ``state.json`` is absent."""
    _write_composite_json(
        tmp_path,
        children={"child_a": {"suspended": True}, "child_b": {"suspended": False}},
    )
    result = extract_composite_child_resume_cursor(tmp_path, "child_a")
    assert result == {"suspended": True}
    result_b = extract_composite_child_resume_cursor(tmp_path, "child_b")
    assert result_b == {"suspended": False}


def test_extract_all_children_from_json_fallback(tmp_path: Path) -> None:
    """``extract_all_composite_child_resume_cursors`` recovers all children
    from ``composite_resume_cursor.json`` when ``state.json`` is absent."""
    children = {"a": {"x": 10}, "b": {"y": 20}, "c": {"z": 30}}
    _write_composite_json(tmp_path, children=children)
    result = extract_all_composite_child_resume_cursors(tmp_path)
    assert result == children


# ---- Pending suspension metadata recovery from composite_resume_cursor.json ----


def test_pending_suspensions_recovered_from_json_fallback(tmp_path: Path) -> None:
    """``load_composite_resume_cursor`` recovers ``pending_suspensions``
    from ``composite_resume_cursor.json`` when ``state.json`` is absent."""
    pending = [
        {
            "child_id": "agent_1",
            "suspension": {
                "kind": "human",
                "prompt": "Approve deployment?",
                "awaitable": "gate-1",
            },
        }
    ]
    _write_composite_json(
        tmp_path,
        children={"agent_1": {"suspended": True}},
        pending_suspensions=pending,
    )
    cursor = load_composite_resume_cursor(tmp_path)
    assert cursor is not None
    assert cursor["pending_suspensions"] == pending
    assert cursor["pending_suspensions"][0]["child_id"] == "agent_1"
    assert cursor["pending_suspensions"][0]["suspension"]["kind"] == "human"


def test_extract_child_resume_target_pending_suspensions(tmp_path: Path) -> None:
    """``extract_composite_child_resume_target`` recovers a child target including
    pending suspension metadata from ``composite_resume_cursor.json`` fallback."""
    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_composite_child_resume_target,
    )

    pending = [
        {
            "child_id": "agent_1",
            "suspension": {
                "kind": "human",
                "prompt": "Approve deployment?",
                "awaitable": "gate-1",
            },
        }
    ]
    _write_composite_json(
        tmp_path,
        children={"agent_1": {"suspended": True, "thread_ref": "th-42"}},
        pending_suspensions=pending,
    )
    target = extract_composite_child_resume_target(tmp_path, "agent_1")
    assert target is not None
    assert target.child_id == "agent_1"
    assert target.cursor == {"suspended": True, "thread_ref": "th-42"}
    assert target.pending_suspension == pending[0]
    assert target.suspension.kind == "human"


# ---- Dual-write: save_composite_resume_cursor persists both surfaces ----


def test_save_composite_writes_both_state_and_json(tmp_path: Path) -> None:
    """``save_composite_resume_cursor`` writes both ``state.json::resume_cursor``
    and ``composite_resume_cursor.json``."""
    save_composite_resume_cursor(
        tmp_path,
        children={"child_a": {"suspended": True}},
        pending_suspensions=[{"child_id": "child_a", "suspension": {"kind": "human"}}],
    )
    # state.json should contain the cursor
    assert (tmp_path / "state.json").exists()
    state_data = json.loads((tmp_path / "state.json").read_text())
    assert state_data["resume_cursor"]["kind"] == COMPOSITE_SUSPENSION_KIND
    assert state_data["resume_cursor"]["children"] == {"child_a": {"suspended": True}}

    # composite_resume_cursor.json should also exist and match
    assert (tmp_path / "composite_resume_cursor.json").exists()
    composite_data = json.loads(
        (tmp_path / "composite_resume_cursor.json").read_text()
    )
    assert composite_data["kind"] == COMPOSITE_SUSPENSION_KIND
    assert composite_data["children"] == {"child_a": {"suspended": True}}
    assert composite_data["pending_suspensions"] == [
        {"child_id": "child_a", "suspension": {"kind": "human"}}
    ]


def test_save_composite_json_self_consistent(tmp_path: Path) -> None:
    """After ``save_composite_resume_cursor``, the JSON file is self-consistent
    and can be independently reloaded with the same data."""
    children = {
        "w1": {"suspended": True, "actor": "claude"},
        "w2": {"suspended": False},
    }
    pending = [
        {"child_id": "w1", "suspension": {"kind": "human", "prompt": "ok?"}},
    ]
    save_composite_resume_cursor(
        tmp_path,
        children=children,
        pending_suspensions=pending,
        shared_awaitable="gate-main",
    )

    # Delete state.json to simulate state loss / manual reset
    (tmp_path / "state.json").unlink()

    # The composite_resume_cursor.json should still be recoverable
    cursor = load_composite_resume_cursor(tmp_path)
    assert cursor is not None
    assert cursor["children"] == children
    assert cursor["pending_suspensions"] == pending
    assert cursor["shared_awaitable"] == "gate-main"


def test_save_composite_json_survives_state_absence(tmp_path: Path) -> None:
    """After dual-write, all extraction helpers work from ``composite_resume_cursor.json``
    alone when ``state.json`` is deleted."""
    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_composite_child_resume_target,
    )

    children = {
        "c1": {"suspended": True, "thread_ref": "th-1"},
        "c2": {"suspended": False},
    }
    pending = [
        {
            "child_id": "c1",
            "suspension": {
                "kind": "human",
                "prompt": "Continue?",
                "awaitable": "gate-abc",
            },
        },
    ]
    save_composite_resume_cursor(
        tmp_path,
        children=children,
        pending_suspensions=pending,
    )

    # Simulate state.json loss
    (tmp_path / "state.json").unlink()
    assert not (tmp_path / "state.json").exists()

    # All extraction helpers should still work
    cursor = load_composite_resume_cursor(tmp_path)
    assert cursor is not None

    child = extract_composite_child_resume_cursor(tmp_path, "c1")
    assert child == {"suspended": True, "thread_ref": "th-1"}

    all_children = extract_all_composite_child_resume_cursors(tmp_path)
    assert all_children == children

    target = extract_composite_child_resume_target(tmp_path, "c1")
    assert target is not None
    assert target.cursor == {"suspended": True, "thread_ref": "th-1"}
    assert target.suspension.kind == "human"
    assert target.suspension.awaitable == "gate-abc"


def test_save_composite_children_keys_round_trip_through_json(tmp_path: Path) -> None:
    """Child keys survive the dual-write round-trip through
    ``composite_resume_cursor.json``."""
    children_with_int_keys = {1: "a", 2: "b"}
    save_composite_resume_cursor(tmp_path, children=children_with_int_keys)

    # Wipe state.json
    (tmp_path / "state.json").unlink()

    result = extract_all_composite_child_resume_cursors(tmp_path)
    assert set(result.keys()) == {"1", "2"}


# ---------------------------------------------------------------------------
# C3: Typed suspended-contract extraction tests
# ---------------------------------------------------------------------------


def test_extract_suspended_contract_result_returns_contract(tmp_path: Path) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
    )

    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Need approval",
            resume_cursor=json.dumps({"phase": "review", "retry_strategy": "fresh"}),
        ),
    )
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()})
    )

    extracted = extract_suspended_contract_result(tmp_path)
    assert extracted is not None
    assert extracted.status is ContractStatus.SUSPENDED
    assert extracted.suspension is not None
    assert extracted.suspension.kind == "human"
    assert extracted.suspension.awaitable == "user"


def test_extract_suspended_contract_result_none_for_missing_key(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
    )

    (tmp_path / "state.json").write_text(json.dumps({"other_key": "value"}))
    assert extract_suspended_contract_result(tmp_path) is None


def test_extract_suspended_contract_result_none_for_missing_file(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
    )

    assert extract_suspended_contract_result(tmp_path) is None


def test_extract_suspended_contract_result_none_for_malformed_json(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
    )

    (tmp_path / "state.json").write_text("not json")
    assert extract_suspended_contract_result(tmp_path) is None


def test_extract_suspended_contract_result_none_for_completed(tmp_path: Path) -> None:
    from arnold.pipeline import ContractResult, ContractStatus

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
    )

    contract = ContractResult(status=ContractStatus.COMPLETED)
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()})
    )
    assert extract_suspended_contract_result(tmp_path) is None


def test_extract_suspended_contract_result_none_for_failed(tmp_path: Path) -> None:
    from arnold.pipeline import ContractResult, ContractStatus

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
    )

    contract = ContractResult(status=ContractStatus.FAILED)
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()})
    )
    assert extract_suspended_contract_result(tmp_path) is None


def test_extract_suspended_contract_result_none_for_schema_version_mismatch(
    tmp_path: Path,
) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
    )

    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(kind="human", prompt="Test"),
    )
    raw = contract.to_json()
    # Corrupt the schema_version
    raw["schema_version"] = "v99-nonexistent"
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": raw})
    )
    assert extract_suspended_contract_result(tmp_path) is None


def test_extract_suspended_contract_result_none_for_suspended_without_suspension(
    tmp_path: Path,
) -> None:
    from arnold.pipeline import ContractResult, ContractStatus

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
    )

    # Suspended status but no suspension object
    raw = {
        "status": "suspended",
        "suspension": None,
        "payload": {},
        "schema_version": ContractResult().schema_version,
    }
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": raw})
    )
    assert extract_suspended_contract_result(tmp_path) is None


def test_extract_typed_resume_metadata_phase_and_pipeline(tmp_path: Path) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_typed_resume_metadata,
    )

    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Need approval",
            thread_ref="pipeline-abc",
            resume_cursor=json.dumps({"phase": "review", "retry_strategy": "fresh"}),
        ),
    )
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()})
    )

    meta = extract_typed_resume_metadata(tmp_path)
    assert meta is not None
    assert meta.phase == "review"
    assert meta.pipeline == "pipeline-abc"
    assert meta.suspension_kind == "human"
    assert meta.awaitable == "user"
    assert isinstance(meta.cursor_data, dict)
    assert meta.cursor_data["phase"] == "review"
    assert meta.cursor_data["retry_strategy"] == "fresh"


def test_extract_typed_resume_metadata_none_when_no_suspended_contract(
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_typed_resume_metadata,
    )

    (tmp_path / "state.json").write_text(json.dumps({}))
    assert extract_typed_resume_metadata(tmp_path) is None


def test_extract_typed_resume_metadata_choices_from_schema(tmp_path: Path) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_typed_resume_metadata,
    )

    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Choose action",
            resume_cursor=json.dumps({"phase": "gate"}),
            resume_input_schema={
                "type": "object",
                "properties": {
                    "choice": {
                        "type": "string",
                        "enum": ["approve", "reject", "retry"],
                    }
                },
                "required": ["choice"],
            },
        ),
    )
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()})
    )

    meta = extract_typed_resume_metadata(tmp_path)
    assert meta is not None
    assert meta.phase == "gate"
    assert meta.choices == ["approve", "reject", "retry"]
    assert meta.resume_input_schema == contract.suspension.resume_input_schema


def test_extract_typed_resume_metadata_opaque_cursor_preserved(tmp_path: Path) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_typed_resume_metadata,
    )

    # Non-JSON cursor (opaque string)
    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Need action",
            resume_cursor="opaque-cursor-data-not-json",
        ),
    )
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()})
    )

    meta = extract_typed_resume_metadata(tmp_path)
    assert meta is not None
    # phase should be None since the cursor isn't JSON
    assert meta.phase is None
    # cursor_data should be the opaque string preserved
    assert meta.cursor_data == "opaque-cursor-data-not-json"


def test_extract_typed_resume_metadata_none_cursor(tmp_path: Path) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_typed_resume_metadata,
    )

    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Need action",
            resume_cursor=None,
        ),
    )
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()})
    )

    meta = extract_typed_resume_metadata(tmp_path)
    assert meta is not None
    assert meta.phase is None
    assert meta.cursor_data is None


def test_typed_state_wins_over_conflicting_awaiting_user(tmp_path: Path) -> None:
    """Typed suspended contract_result takes precedence over conflicting
    awaiting_user.json — the extraction helpers return typed data even when
    a legacy sidecar file is also present."""
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    from arnold_pipelines.megaplan._pipeline.resume import (
        check_awaiting_user,
        extract_suspended_contract_result,
        extract_typed_resume_metadata,
    )

    contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Typed prompt",
            thread_ref="typed-pipeline",
            resume_cursor=json.dumps({"phase": "typed-stage", "source": "contract"}),
        ),
    )
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()})
    )

    # Also write a conflicting awaiting_user.json
    (tmp_path / "awaiting_user.json").write_text(
        json.dumps(
            {
                "message": "Legacy prompt",
                "pipeline": "legacy-pipeline",
                "choices": ["legacy-a", "legacy-b"],
            }
        )
    )

    # awaiting_user.json is still detectable
    awaiting = check_awaiting_user(tmp_path)
    assert awaiting is not None
    assert awaiting["message"] == "Legacy prompt"

    # But typed extraction helpers return contract data — callers should
    # prefer this over the sidecar
    extracted = extract_suspended_contract_result(tmp_path)
    assert extracted is not None
    assert extracted.suspension.prompt == "Typed prompt"
    assert extracted.suspension.thread_ref == "typed-pipeline"

    meta = extract_typed_resume_metadata(tmp_path)
    assert meta is not None
    assert meta.phase == "typed-stage"
    assert meta.pipeline == "typed-pipeline"


def test_malformed_typed_state_falls_back(tmp_path: Path) -> None:
    """When contract_result is present but malformed (e.g. missing required
    fields), the extraction helpers return None so callers can fall through
    to legacy sources like awaiting_user.json."""
    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
        extract_typed_resume_metadata,
    )

    # Malformed: has contract_result key but the dict is not a valid
    # ContractResult (missing status, etc.)
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": {"garbage": True}})
    )

    assert extract_suspended_contract_result(tmp_path) is None
    assert extract_typed_resume_metadata(tmp_path) is None


def test_non_suspended_typed_state_falls_back(tmp_path: Path) -> None:
    """When contract_result exists but is completed (not suspended), the
    extraction helpers return None, allowing fallback to other sources."""
    from arnold.pipeline import ContractResult, ContractStatus

    from arnold_pipelines.megaplan._pipeline.resume import (
        extract_suspended_contract_result,
        extract_typed_resume_metadata,
    )

    contract = ContractResult(status=ContractStatus.COMPLETED)
    (tmp_path / "state.json").write_text(
        json.dumps({"contract_result": contract.to_json()})
    )

    assert extract_suspended_contract_result(tmp_path) is None
    assert extract_typed_resume_metadata(tmp_path) is None


def test_decode_json_cursor_preserves_opaque(tmp_path: Path) -> None:
    from arnold_pipelines.megaplan._pipeline.resume import _decode_json_cursor

    # JSON string
    assert _decode_json_cursor('{"key": "value"}') == {"key": "value"}

    # Opaque non-JSON string
    assert _decode_json_cursor("not-json") == "not-json"

    # None
    assert _decode_json_cursor(None) is None

    # Non-string (should be passed through)
    assert _decode_json_cursor(42) == 42


def test_resume_human_gate_prefers_typed_state_over_conflicting_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    typed_contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Typed prompt",
            thread_ref="typed-pipeline",
            resume_input_schema={
                "type": "object",
                "properties": {"choice": {"type": "string", "enum": ["typed-yes", "typed-no"]}},
                "required": ["choice"],
                "additionalProperties": False,
            },
            resume_cursor=json.dumps({"phase": "typed-stage", "retry_strategy": "typed"}),
        ),
        payload={"awaiting_user": {"artifact_stage": "draft", "artifact_path": "draft/v1.md"}},
    )
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "contract_result": typed_contract.to_json(),
                "_pipeline_paused": True,
                "_pipeline_paused_stage": "legacy-stage",
                "mode": "code",
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "awaiting_user.json").write_text(
        json.dumps(
            {
                "pipeline": "legacy-pipeline",
                "stage": "legacy-stage",
                "choices": ["legacy-only"],
                "message": "Legacy prompt",
            }
        ),
        encoding="utf-8",
    )

    pipeline = Pipeline(
        stages={"typed-stage": Stage(name="typed-stage", step=_Noop())},
        entry="typed-stage",
    )
    captured: dict[str, object] = {}

    def fake_run_pipeline(resumed_pipeline, ctx, artifact_root):  # noqa: ANN001
        captured["entry"] = resumed_pipeline.entry
        captured["state"] = dict(ctx.state)
        captured["disk_state"] = json.loads(
            (plan_dir / "state.json").read_text(encoding="utf-8")
        )
        captured["artifact_root"] = artifact_root
        captured["awaiting_user"] = json.loads(
            (plan_dir / "awaiting_user.json").read_text(encoding="utf-8")
        )
        return {"success": True, "phase": resumed_pipeline.entry}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan._pipeline.registry.get_pipeline",
        lambda name: pipeline if name == "typed-pipeline" else None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan._pipeline.executor.run_pipeline",
        fake_run_pipeline,
    )

    result = megaplan_cli._resume_human_gate(
        tmp_path,
        plan_dir,
        argparse.Namespace(choice="typed-yes"),
    )

    assert result == {"success": True, "phase": "typed-stage"}
    assert captured["entry"] == "typed-stage"
    assert captured["artifact_root"] == plan_dir
    assert captured["state"]["mode"] == "code"
    assert "_pipeline_paused" not in captured["state"]
    assert "_pipeline_paused_stage" not in captured["state"]
    assert "contract_result" not in captured["state"]
    assert "_pipeline_paused" not in captured["disk_state"]
    assert "_pipeline_paused_stage" not in captured["disk_state"]
    assert "contract_result" not in captured["disk_state"]
    assert captured["awaiting_user"] == {
        "artifact_path": "draft/v1.md",
        "artifact_stage": "draft",
        "pipeline": "typed-pipeline",
        "stage": "typed-stage",
        "choices": ["typed-yes", "typed-no"],
        "message": "Typed prompt",
        "prompt": "Typed prompt",
        "resume_input_schema": {
            "type": "object",
            "properties": {"choice": {"type": "string", "enum": ["typed-yes", "typed-no"]}},
            "required": ["choice"],
            "additionalProperties": False,
        },
        "_resume_choice": "typed-yes",
    }
    assert not (plan_dir / "awaiting_user.json").exists()


def test_handle_resume_legacy_sidecar_only_still_routes_human_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "_pipeline_paused": True,
                "_pipeline_paused_stage": "legacy-stage",
                "mode": "code",
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "awaiting_user.json").write_text(
        json.dumps(
            {
                "pipeline": "legacy-pipeline",
                "stage": "legacy-stage",
                "choices": ["continue"],
                "message": "Legacy prompt",
            }
        ),
        encoding="utf-8",
    )

    pipeline = Pipeline(
        stages={"legacy-stage": Stage(name="legacy-stage", step=_Noop())},
        entry="legacy-stage",
    )
    captured: dict[str, object] = {}

    def fake_run_pipeline(resumed_pipeline, ctx, artifact_root):  # noqa: ANN001
        captured["entry"] = resumed_pipeline.entry
        captured["state"] = dict(ctx.state)
        captured["awaiting_user"] = json.loads(
            (plan_dir / "awaiting_user.json").read_text(encoding="utf-8")
        )
        return {"success": True, "phase": resumed_pipeline.entry}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan._core.io.find_plan_dir",
        lambda root, requested_name: plan_dir,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan._pipeline.registry.get_pipeline",
        lambda name: pipeline if name == "legacy-pipeline" else None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan._pipeline.executor.run_pipeline",
        fake_run_pipeline,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cli.resume_plan",
        lambda *_args, **_kwargs: pytest.fail("resume_plan should not run for sidecar human-gate resumes"),
    )

    result = megaplan_cli.handle_resume(
        tmp_path,
        argparse.Namespace(plan="plan", choice="continue", actor=None, backend=None),
    )

    assert result == {"success": True, "phase": "legacy-stage"}
    assert captured["entry"] == "legacy-stage"
    assert captured["state"] == {"mode": "code"}
    assert captured["awaiting_user"] == {
        "pipeline": "legacy-pipeline",
        "stage": "legacy-stage",
        "choices": ["continue"],
        "message": "Legacy prompt",
        "_resume_choice": "continue",
    }
    assert not (plan_dir / "awaiting_user.json").exists()


def test_handle_resume_routes_typed_only_human_gate_without_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    typed_contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Choose",
            thread_ref="typed-pipeline",
            resume_input_schema={
                "type": "object",
                "properties": {"choice": {"type": "string", "enum": ["continue", "stop"]}},
                "required": ["choice"],
                "additionalProperties": False,
            },
            resume_cursor=json.dumps({"phase": "gate"}),
        ),
    )
    (plan_dir / "state.json").write_text(
        json.dumps({"contract_result": typed_contract.to_json()}),
        encoding="utf-8",
    )

    pipeline = Pipeline(stages={"gate": Stage(name="gate", step=_Noop())}, entry="gate")
    captured: dict[str, object] = {}

    def fake_run_pipeline(resumed_pipeline, ctx, artifact_root):  # noqa: ANN001
        captured["entry"] = resumed_pipeline.entry
        captured["awaiting_user"] = json.loads(
            (plan_dir / "awaiting_user.json").read_text(encoding="utf-8")
        )
        return {"success": True, "phase": resumed_pipeline.entry}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan._core.io.find_plan_dir",
        lambda root, requested_name: plan_dir,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan._pipeline.registry.get_pipeline",
        lambda name: pipeline if name == "typed-pipeline" else None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan._pipeline.executor.run_pipeline",
        fake_run_pipeline,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cli.resume_plan",
        lambda *_args, **_kwargs: pytest.fail("resume_plan should not run for typed human-gate resumes"),
    )

    result = megaplan_cli.handle_resume(
        tmp_path,
        argparse.Namespace(plan="plan", choice="continue", actor=None, backend=None),
    )

    assert result == {"success": True, "phase": "gate"}
    assert captured["entry"] == "gate"
    assert captured["awaiting_user"] == {
        "pipeline": "typed-pipeline",
        "stage": "gate",
        "choices": ["continue", "stop"],
        "message": "Choose",
        "prompt": "Choose",
        "resume_input_schema": {
            "type": "object",
            "properties": {"choice": {"type": "string", "enum": ["continue", "stop"]}},
            "required": ["choice"],
            "additionalProperties": False,
        },
        "_resume_choice": "continue",
    }
    assert not (plan_dir / "awaiting_user.json").exists()


def test_handle_resume_routes_typed_programmatic_resume_to_resume_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from arnold.pipeline import ContractResult, ContractStatus, Suspension

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    typed_contract = ContractResult(
        status=ContractStatus.SUSPENDED,
        suspension=Suspension(
            kind="human",
            awaitable="user",
            prompt="Programmatic resume",
            thread_ref="typed-pipeline",
            resume_input_schema={},
            resume_cursor=json.dumps({"phase": "execute", "retry_strategy": "typed"}),
        ),
    )
    (plan_dir / "state.json").write_text(
        json.dumps({"contract_result": typed_contract.to_json()}),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan._core.io.find_plan_dir",
        lambda root, requested_name: plan_dir,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cli._resume_human_gate",
        lambda *_args, **_kwargs: pytest.fail("_resume_human_gate should not run without typed choices or sidecar"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cli.resume_plan",
        lambda root, plan, store=None: captured.update(
            {"root": root, "plan": plan, "store": store}
        )
        or {"success": True, "phase": "execute"},
    )

    result = megaplan_cli.handle_resume(
        tmp_path,
        argparse.Namespace(plan="plan", choice=None, actor=None, backend=None),
    )

    assert result == {"success": True, "phase": "execute"}
    assert captured == {"root": tmp_path, "plan": "plan", "store": None}


def test_handle_resume_opts_into_self_hosted_editable_for_engine_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(json.dumps({"current_state": "failed"}), encoding="utf-8")
    seen_provider: list[str | None] = []

    monkeypatch.delenv("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", raising=False)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.cli.megaplan_engine_root",
        lambda: tmp_path.resolve(),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan._core.io.find_plan_dir",
        lambda root, requested_name: plan_dir,
    )

    def fake_resume_plan(*_args, **_kwargs):
        seen_provider.append(os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER"))
        return {"success": True, "phase": "finalize"}

    monkeypatch.setattr("arnold_pipelines.megaplan.cli.resume_plan", fake_resume_plan)

    result = megaplan_cli.handle_resume(
        tmp_path,
        argparse.Namespace(plan="plan", choice=None, actor=None, backend=None),
    )

    assert result == {"success": True, "phase": "finalize"}
    assert seen_provider == ["self_hosted_editable"]
    assert os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER") is None
