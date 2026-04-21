from __future__ import annotations

import json
from pathlib import Path

import pytest

import megaplan
from megaplan._core import ensure_runtime_layout, load_plan

from tests.conftest import PlanFixture, read_json


def test_parse_claude_envelope_valid_with_result_block() -> None:
    from megaplan.workers import parse_claude_envelope
    raw = json.dumps({"result": json.dumps({"plan": "x"}), "total_cost_usd": 0.05})
    envelope, payload = parse_claude_envelope(raw)
    assert payload["plan"] == "x"


def test_parse_claude_envelope_structured_output() -> None:
    from megaplan.workers import parse_claude_envelope
    raw = json.dumps({"structured_output": {"plan": "x"}, "total_cost_usd": 0.01})
    envelope, payload = parse_claude_envelope(raw)
    assert payload == {"plan": "x"}


def test_parse_claude_envelope_direct_dict() -> None:
    from megaplan.workers import parse_claude_envelope
    raw = json.dumps({"plan": "direct"})
    envelope, payload = parse_claude_envelope(raw)
    assert payload["plan"] == "direct"


def test_parse_claude_envelope_malformed() -> None:
    from megaplan.workers import parse_claude_envelope
    with pytest.raises(megaplan.CliError, match="valid JSON"):
        parse_claude_envelope("not json at all")


def test_parse_claude_envelope_is_error() -> None:
    from megaplan.workers import parse_claude_envelope
    raw = json.dumps({"is_error": True, "result": "something failed"})
    with pytest.raises(megaplan.CliError, match="failed"):
        parse_claude_envelope(raw)


def test_parse_claude_envelope_empty_result() -> None:
    from megaplan.workers import parse_claude_envelope
    raw = json.dumps({"result": ""})
    with pytest.raises(megaplan.CliError, match="empty"):
        parse_claude_envelope(raw)


def test_parse_claude_envelope_non_object_result() -> None:
    from megaplan.workers import parse_claude_envelope
    raw = json.dumps({"result": "[1, 2, 3]"})
    with pytest.raises(megaplan.CliError, match="not an object"):
        parse_claude_envelope(raw)


def test_parse_json_file_valid(tmp_path: Path) -> None:
    from megaplan.workers import parse_json_file
    path = tmp_path / "test.json"
    path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    assert parse_json_file(path) == {"key": "value"}


def test_parse_json_file_missing(tmp_path: Path) -> None:
    from megaplan.workers import parse_json_file
    with pytest.raises(megaplan.CliError, match="not created"):
        parse_json_file(tmp_path / "missing.json")


def test_parse_json_file_non_object(tmp_path: Path) -> None:
    from megaplan.workers import parse_json_file
    path = tmp_path / "test.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(megaplan.CliError, match="not contain a JSON object"):
        parse_json_file(path)


def test_validate_payload_valid_pass() -> None:
    from megaplan.workers import validate_payload
    validate_payload("plan", {"plan": "x", "questions": [], "success_criteria": [], "assumptions": []})


def test_validate_payload_missing_keys_raise() -> None:
    from megaplan.workers import validate_payload
    with pytest.raises(megaplan.CliError, match="missing required"):
        validate_payload("plan", {"plan": "x"})


def test_validate_payload_unknown_step_noop() -> None:
    from megaplan.workers import validate_payload
    # Unknown step should not raise
    validate_payload("nonexistent_step", {})


def test_extract_session_id_jsonl_thread_id() -> None:
    from megaplan.workers import extract_session_id
    raw = '{"type":"thread.started","thread_id":"abc-123"}\n'
    assert extract_session_id(raw) == "abc-123"


def test_extract_session_id_unstructured() -> None:
    from megaplan.workers import extract_session_id
    raw = "Starting session... session_id: 12345678-abcd-ef01"
    assert extract_session_id(raw) == "12345678-abcd-ef01"


def test_extract_session_id_pattern() -> None:
    from megaplan.workers import extract_session_id
    raw = "session id: aabbccdd-1234-5678-abcd"
    assert extract_session_id(raw) == "aabbccdd-1234-5678-abcd"


def test_extract_session_id_no_match() -> None:
    from megaplan.workers import extract_session_id
    assert extract_session_id("no session here") is None


def test_extract_session_id_empty_string() -> None:
    from megaplan.workers import extract_session_id
    assert extract_session_id("") is None


def test_strict_schema_adds_additional_properties_false() -> None:
    from megaplan.schemas import strict_schema
    result = strict_schema({"type": "object", "properties": {"a": {"type": "string"}}})
    assert result["additionalProperties"] is False


def test_strict_schema_preserves_existing_additional_properties() -> None:
    from megaplan.schemas import strict_schema
    result = strict_schema({"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": True})
    assert result["additionalProperties"] is True


def test_strict_schema_sets_required_from_properties() -> None:
    from megaplan.schemas import strict_schema
    result = strict_schema({"type": "object", "properties": {"x": {"type": "string"}, "y": {"type": "number"}}})
    assert result["required"] == ["x", "y"]


def test_strict_schema_overwrites_partial_required_arrays_recursively() -> None:
    from megaplan.schemas import strict_schema
    schema = {
        "type": "object",
        "required": ["stale_root"],
        "properties": {
            "inner": {
                "type": "object",
                "required": ["stale_inner"],
                "properties": {"child": {"type": "string"}},
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["stale_item"],
                    "properties": {"name": {"type": "string"}},
                },
            },
        },
    }
    result = strict_schema(schema)
    assert result["required"] == ["inner", "items"]
    assert result["properties"]["inner"]["required"] == ["child"]
    assert result["properties"]["items"]["items"]["required"] == ["name"]


def test_strict_schema_nested_objects() -> None:
    from megaplan.schemas import strict_schema
    schema = {
        "type": "object",
        "properties": {
            "inner": {
                "type": "object",
                "properties": {"a": {"type": "string"}},
            }
        },
    }
    result = strict_schema(schema)
    assert result["properties"]["inner"]["additionalProperties"] is False
    assert result["properties"]["inner"]["required"] == ["a"]


def test_strict_schema_array_items() -> None:
    from megaplan.schemas import strict_schema
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
            }
        },
    }
    result = strict_schema(schema)
    assert result["properties"]["items"]["items"]["additionalProperties"] is False
    assert result["properties"]["items"]["items"]["required"] == ["name"]


def test_strict_schema_non_object_untouched() -> None:
    from megaplan.schemas import strict_schema
    assert strict_schema({"type": "string"}) == {"type": "string"}
    assert strict_schema(42) == 42
    assert strict_schema("hello") == "hello"
    assert strict_schema([1, 2]) == [1, 2]


def test_codex_uses_same_prompt_builders_for_shared_steps(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)
    from megaplan.prompts import create_claude_prompt, create_codex_prompt
    for step in ["plan", "critique"]:
        claude_prompt = create_claude_prompt(step, state, plan_fixture.plan_dir)
        codex_prompt = create_codex_prompt(step, state, plan_fixture.plan_dir)
        assert claude_prompt == codex_prompt


def test_load_plan_migrates_legacy_evaluated_state(tmp_path: Path) -> None:
    root = tmp_path / "root"
    ensure_runtime_layout(root)
    plan_dir = megaplan.plans_root(root) / "legacy"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "legacy",
                "idea": "old workflow",
                "current_state": "evaluated",
                "iteration": 1,
                "created_at": "2026-03-20T00:00:00Z",
                "config": {"project_dir": str(tmp_path / "project"), "auto_approve": False, "robustness": "standard"},
                "sessions": {},
                "plan_versions": [{"version": 1, "file": "plan_v1.md", "hash": "sha256:test", "timestamp": "2026-03-20T00:00:00Z"}],
                "history": [],
                "meta": {
                    "significant_counts": [],
                    "weighted_scores": [],
                    "plan_deltas": [],
                    "recurring_critiques": [],
                    "total_cost_usd": 0.0,
                    "overrides": [],
                    "notes": [],
                },
                "last_evaluation": {"recommendation": "SKIP"},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    _plan_dir, state = load_plan(root, "legacy")
    persisted = read_json(plan_dir / "state.json")

    assert state["current_state"] == megaplan.STATE_CRITIQUED
    assert state["last_gate"] == {}
    assert "last_evaluation" not in persisted
