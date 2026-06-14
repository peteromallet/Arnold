from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import arnold.pipelines.megaplan as megaplan
import arnold.pipelines.megaplan.types as megaplan_types
from arnold.pipelines.megaplan.schemas.sprint1 import Plan
from arnold.pipelines.megaplan._core import ensure_runtime_layout, load_plan

from tests.conftest import PlanFixture, read_json


def test_plan_model_rejects_invalid_current_state() -> None:
    with pytest.raises(ValidationError, match="invalid current_state"):
        Plan(
            id="p",
            name="p",
            revision=0,
            idea="i",
            current_state="not-a-real-state",
            iteration=1,
            config={},
            sessions={},
            plan_versions=[],
            history=[],
            meta={},
            last_gate={},
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )


def test_parse_claude_envelope_valid_with_result_block() -> None:
    from arnold.pipelines.megaplan.workers import parse_claude_envelope
    raw = json.dumps({"result": json.dumps({"plan": "x"}), "total_cost_usd": 0.05})
    envelope, payload = parse_claude_envelope(raw)
    assert payload["plan"] == "x"


def test_parse_claude_envelope_structured_output() -> None:
    from arnold.pipelines.megaplan.workers import parse_claude_envelope
    raw = json.dumps({"structured_output": {"plan": "x"}, "total_cost_usd": 0.01})
    envelope, payload = parse_claude_envelope(raw)
    assert payload == {"plan": "x"}


def test_parse_claude_envelope_direct_dict() -> None:
    from arnold.pipelines.megaplan.workers import parse_claude_envelope
    raw = json.dumps({"plan": "direct"})
    envelope, payload = parse_claude_envelope(raw)
    assert payload["plan"] == "direct"


def test_parse_claude_envelope_malformed() -> None:
    from arnold.pipelines.megaplan.workers import parse_claude_envelope
    with pytest.raises(megaplan.CliError, match="valid JSON"):
        parse_claude_envelope("not json at all")


def test_parse_claude_envelope_is_error() -> None:
    from arnold.pipelines.megaplan.workers import parse_claude_envelope
    raw = json.dumps({"is_error": True, "result": "something failed"})
    with pytest.raises(megaplan.CliError, match="failed"):
        parse_claude_envelope(raw)


def test_parse_claude_envelope_empty_result() -> None:
    from arnold.pipelines.megaplan.workers import parse_claude_envelope
    raw = json.dumps({"result": ""})
    with pytest.raises(megaplan.CliError, match="empty"):
        parse_claude_envelope(raw)


def test_parse_claude_envelope_non_object_result() -> None:
    from arnold.pipelines.megaplan.workers import parse_claude_envelope
    raw = json.dumps({"result": "[1, 2, 3]"})
    with pytest.raises(megaplan.CliError, match="not an object"):
        parse_claude_envelope(raw)


def test_parse_json_file_valid(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.workers import parse_json_file
    path = tmp_path / "test.json"
    path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    assert parse_json_file(path) == {"key": "value"}


def test_parse_json_file_missing(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.workers import parse_json_file
    with pytest.raises(megaplan.CliError, match="not created"):
        parse_json_file(tmp_path / "missing.json")


def test_parse_json_file_non_object(tmp_path: Path) -> None:
    from arnold.pipelines.megaplan.workers import parse_json_file
    path = tmp_path / "test.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(megaplan.CliError, match="not contain a JSON object"):
        parse_json_file(path)


def test_validate_payload_is_not_importable_from_impl() -> None:
    with pytest.raises(ImportError):
        exec("from arnold.pipelines.megaplan.workers._impl import validate_payload", {})


def test_extract_session_id_jsonl_thread_id() -> None:
    from arnold.pipelines.megaplan.workers import extract_session_id
    raw = '{"type":"thread.started","thread_id":"abc-123"}\n'
    assert extract_session_id(raw) == "abc-123"


def test_extract_session_id_unstructured() -> None:
    from arnold.pipelines.megaplan.workers import extract_session_id
    raw = "Starting session... session_id: 12345678-abcd-ef01"
    assert extract_session_id(raw) == "12345678-abcd-ef01"


def test_extract_session_id_pattern() -> None:
    from arnold.pipelines.megaplan.workers import extract_session_id
    raw = "session id: aabbccdd-1234-5678-abcd"
    assert extract_session_id(raw) == "aabbccdd-1234-5678-abcd"


def test_extract_session_id_no_match() -> None:
    from arnold.pipelines.megaplan.workers import extract_session_id
    assert extract_session_id("no session here") is None


def test_extract_session_id_empty_string() -> None:
    from arnold.pipelines.megaplan.workers import extract_session_id
    assert extract_session_id("") is None


def test_strict_schema_adds_additional_properties_false() -> None:
    from arnold.pipelines.megaplan.schemas import strict_schema
    result = strict_schema({"type": "object", "properties": {"a": {"type": "string"}}})
    assert result["additionalProperties"] is False


def test_strict_schema_preserves_existing_additional_properties() -> None:
    from arnold.pipelines.megaplan.schemas import strict_schema
    result = strict_schema({"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": True})
    assert result["additionalProperties"] is True


def test_strict_schema_sets_required_from_properties() -> None:
    from arnold.pipelines.megaplan.schemas import strict_schema
    result = strict_schema({"type": "object", "properties": {"x": {"type": "string"}, "y": {"type": "number"}}})
    assert result["required"] == ["x", "y"]


def test_strict_schema_overwrites_partial_required_arrays_recursively() -> None:
    from arnold.pipelines.megaplan.schemas import strict_schema
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
    from arnold.pipelines.megaplan.schemas import strict_schema
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
    from arnold.pipelines.megaplan.schemas import strict_schema
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
    from arnold.pipelines.megaplan.schemas import strict_schema
    assert strict_schema({"type": "string"}) == {"type": "string"}
    assert strict_schema(42) == 42
    assert strict_schema("hello") == "hello"
    assert strict_schema([1, 2]) == [1, 2]


def test_planning_schema_contracts_no_longer_export_from_megaplan_types() -> None:
    for name in ("TiebreakerDecision", "GatePayload", "GateArtifact", "GateSignals"):
        assert not hasattr(megaplan_types, name)


def test_codex_uses_same_prompt_builders_for_shared_steps(plan_fixture: PlanFixture) -> None:
    megaplan.handle_plan(plan_fixture.root, plan_fixture.make_args(plan=plan_fixture.plan_name))
    _, state = load_plan(plan_fixture.root, plan_fixture.plan_name)
    from arnold.pipelines.megaplan.prompts import create_claude_prompt, create_codex_prompt
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


def test_parse_agent_spec_claude_effort_levels() -> None:
    from arnold.pipelines.megaplan.types import AgentSpec, parse_agent_spec
    # Effort-only: claude:low, claude:high → model=None, effort=set
    assert parse_agent_spec("claude:low") == AgentSpec("claude", effort="low")
    assert parse_agent_spec("claude:high") == AgentSpec("claude", effort="high")
    assert parse_agent_spec("claude:medium") == AgentSpec("claude", effort="medium")
    assert parse_agent_spec("claude:xhigh") == AgentSpec("claude", effort="xhigh")
    assert parse_agent_spec("claude:max") == AgentSpec("claude", effort="max")
    # Bare claude → model=None, effort=None
    assert parse_agent_spec("claude") == AgentSpec("claude")
    # Codex effort-only
    assert parse_agent_spec("codex:low") == AgentSpec("codex", effort="low")
    assert parse_agent_spec("codex:high") == AgentSpec("codex", effort="high")
    assert parse_agent_spec("codex:minimal") == AgentSpec("codex", effort="minimal")
    assert parse_agent_spec("codex") == AgentSpec("codex")
    # Hermes passthrough (non-premium)
    assert parse_agent_spec("hermes:openai/gpt-5") == AgentSpec("hermes", model="openai/gpt-5")


def test_parse_agent_spec_bare_specs() -> None:
    from arnold.pipelines.megaplan.types import AgentSpec, parse_agent_spec
    assert parse_agent_spec("claude") == AgentSpec("claude")
    assert parse_agent_spec("codex") == AgentSpec("codex")
    assert parse_agent_spec("hermes") == AgentSpec("hermes")
    assert parse_agent_spec("shannon") == AgentSpec("shannon")


def test_parse_agent_spec_effort_only() -> None:
    """Reserved effort tokens for premium agents must parse as effort, not model."""
    from arnold.pipelines.megaplan.types import AgentSpec, parse_agent_spec
    # claude:low must be effort-only (not model='low')
    spec = parse_agent_spec("claude:low")
    assert spec.agent == "claude"
    assert spec.model is None
    assert spec.effort == "low"
    # codex:minimal must be effort-only
    spec = parse_agent_spec("codex:minimal")
    assert spec.agent == "codex"
    assert spec.model is None
    assert spec.effort == "minimal"


def test_parse_agent_spec_model_only() -> None:
    """Model-only specs for premium agents."""
    from arnold.pipelines.megaplan.types import AgentSpec, parse_agent_spec
    spec = parse_agent_spec("claude:sonnet-4.6")
    assert spec.agent == "claude"
    assert spec.model == "sonnet-4.6"
    assert spec.effort is None


def test_parse_agent_spec_model_plus_effort() -> None:
    """Model-plus-effort specs for premium agents."""
    from arnold.pipelines.megaplan.types import AgentSpec, parse_agent_spec
    spec = parse_agent_spec("codex:gpt-5.3-codex:high")
    assert spec.agent == "codex"
    assert spec.model == "gpt-5.3-codex"
    assert spec.effort == "high"

    spec = parse_agent_spec("claude:sonnet-4.6:medium")
    assert spec.agent == "claude"
    assert spec.model == "sonnet-4.6"
    assert spec.effort == "medium"


def test_parse_agent_spec_hermes_passthrough_multiple_colons() -> None:
    """Hermes specs with multiple colons preserve the full model string."""
    from arnold.pipelines.megaplan.types import AgentSpec, parse_agent_spec
    spec = parse_agent_spec("hermes:fireworks:accounts/foo")
    assert spec.agent == "hermes"
    assert spec.model == "fireworks:accounts/foo"
    assert spec.effort is None

    spec = parse_agent_spec("hermes:fireworks:accounts/fireworks/models/kimi-k2p6")
    assert spec.agent == "hermes"
    assert spec.model == "fireworks:accounts/fireworks/models/kimi-k2p6"
    assert spec.effort is None


def test_parse_agent_spec_shannon_legacy() -> None:
    """Direct shannon specs preserve the full payload as model."""
    from arnold.pipelines.megaplan.types import AgentSpec, parse_agent_spec
    spec = parse_agent_spec("shannon")
    assert spec.agent == "shannon"
    assert spec.model is None
    assert spec.effort is None

    # shannon:anything → full payload as model (non-premium passthrough)
    spec = parse_agent_spec("shannon:some-payload")
    assert spec.agent == "shannon"
    assert spec.model == "some-payload"
    assert spec.effort is None


def test_parse_agent_spec_shannon_not_model_plus_effort() -> None:
    """shannon:sonnet-4.6:high is NOT model-plus-effort — it's a non-premium passthrough."""
    from arnold.pipelines.megaplan.types import AgentSpec, parse_agent_spec
    spec = parse_agent_spec("shannon:sonnet-4.6:high")
    assert spec.agent == "shannon"
    # The entire rest after first colon is the model (passthrough)
    assert spec.model == "sonnet-4.6:high"
    assert spec.effort is None


def test_parse_agent_spec_unknown_agent() -> None:
    """Unknown agents get passthrough treatment (whole rest after first colon = model)."""
    from arnold.pipelines.megaplan.types import AgentSpec, parse_agent_spec
    spec = parse_agent_spec("unknown-agent")
    assert spec.agent == "unknown-agent"
    assert spec.model is None
    assert spec.effort is None

    spec = parse_agent_spec("unknown:foo:bar")
    assert spec.agent == "unknown"
    assert spec.model == "foo:bar"
    assert spec.effort is None


def test_parse_agent_spec_round_trip() -> None:
    """format_agent_spec round-trips correctly through parse_agent_spec."""
    from arnold.pipelines.megaplan.types import AgentSpec, format_agent_spec, parse_agent_spec
    cases = [
        "claude",
        "claude:low",
        "claude:sonnet-4.6",
        "claude:sonnet-4.6:medium",
        "codex",
        "codex:high",
        "codex:gpt-5.3-codex:high",
        "codex:gpt-5.5",
        "hermes:fireworks:accounts/foo",
        "shannon",
        "shannon:some-payload",
    ]
    for case in cases:
        formatted = format_agent_spec(parse_agent_spec(case))
        assert formatted == case, f"Round-trip failed: {case!r} → {formatted!r}"


def test_reserved_effort_token_disambiguation() -> None:
    """All reserved effort tokens for claude/codex must NOT be parsed as model names."""
    from arnold.pipelines.megaplan.types import AgentSpec, _PREMIUM_EFFORT_TOKENS, parse_agent_spec
    for token in _PREMIUM_EFFORT_TOKENS:
        spec = parse_agent_spec(f"claude:{token}")
        assert spec.agent == "claude"
        assert spec.model is None, f"claude:{token} should be effort-only, not model='{token}'"
        assert spec.effort == token

        spec = parse_agent_spec(f"codex:{token}")
        assert spec.agent == "codex"
        assert spec.model is None, f"codex:{token} should be effort-only, not model='{token}'"
        assert spec.effort == token


# ---------------------------------------------------------------------------
# Semantic validation of premium agent specs (specfix)
#
# Regression: a plan initialised with --vendor codex once ended up with a
# malformed phase-routing spec ``critique=codex:claude:sonnet`` persisted to
# state.json -> config.phase_model. parse_agent_spec did NOT raise — it
# positionally yielded agent=codex, model='claude', effort='sonnet'. The bad
# spec rode silently through three sprints. These tests close the grammar.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_spec",
    [
        "codex:claude:sonnet",   # the original bug: model='claude', effort='sonnet'
        "codex:claude:opus",     # variant
        "claude:gpt-5.5",        # codex model on the claude agent
        "claude:gpt-5.4",        # codex model on the claude agent
        "codex:claude-sonnet-4-6",   # claude model on the codex agent
        "codex:opus",            # claude model shorthand on codex
        "claude:sonnet:bogus",   # valid model, bogus effort
        "codex:gpt-5.5:bogus",   # valid model, bogus effort
        "codex:nonsense",        # neither effort nor model
        "claude:totally-made-up-model",
    ],
)
def test_parse_agent_spec_rejects_malformed_premium_specs(bad_spec: str) -> None:
    """Premium specs whose token is neither a valid effort nor a recognised
    model for that vendor must raise (not silently mis-parse)."""
    from arnold.pipelines.megaplan.types import CliError, parse_agent_spec

    with pytest.raises(CliError) as exc:
        parse_agent_spec(bad_spec)
    assert bad_spec in str(exc.value), f"error should name the offending spec {bad_spec!r}"


@pytest.mark.parametrize(
    "good_spec",
    [
        # Bare agents
        "claude",
        "codex",
        "hermes",
        "shannon",
        # Claude effort ladder (= VALID_DEPTH_CHOICES)
        "claude:minimal",
        "claude:low",
        "claude:medium",
        "claude:high",
        "claude:xhigh",
        "claude:max",
        # Codex effort ladder
        "codex:minimal",
        "codex:low",
        "codex:medium",
        "codex:high",
        "codex:xhigh",   # produced by --depth xhigh on a codex slot
        "codex:max",     # produced by --depth max on a codex slot
        # Claude model shorthands + full pins
        "claude:sonnet",
        "claude:opus",
        "claude:sonnet-4.6",
        "claude:sonnet-4.6:medium",
        "claude:claude-sonnet-4-6",
        "claude:claude-opus-4-7",
        # Codex full pins
        "codex:gpt-5.4",
        "codex:gpt-5.5",
        "codex:gpt-5.3-codex",
        "codex:gpt-5.3-codex:high",
        # Hermes / shannon 3-segment provider:model form (non-premium passthrough)
        "hermes:deepseek:deepseek-v4-pro",
        "hermes:deepseek:deepseek-v4-flash",
        "hermes:fireworks:accounts/fireworks/models/kimi-k2p6",
        "hermes:glm-5.1",
        "shannon:some-payload",
    ],
)
def test_parse_agent_spec_accepts_all_legit_forms(good_spec: str) -> None:
    """Every spec form actually used in profiles/tier_models/defaults must parse."""
    from arnold.pipelines.megaplan.types import parse_agent_spec

    spec = parse_agent_spec(good_spec)
    assert spec.agent == good_spec.split(":", 1)[0]


def test_parse_agent_spec_accepts_every_spec_in_loaded_profiles() -> None:
    """Self-maintaining non-regression guard: enumerate EVERY agent spec across
    all built-in profiles (flat slots + nested tier_models) and assert each
    parses. If a future profile introduces a spec the validator rejects, this
    fails loudly at the source rather than at run time."""
    from arnold.pipelines.megaplan.profiles import load_profiles
    from arnold.pipelines.megaplan.types import parse_agent_spec

    specs: set[str] = set()

    def _collect(value: object) -> None:
        if isinstance(value, str):
            specs.add(value)
        elif isinstance(value, dict):
            for v in value.values():
                _collect(v)

    for pdict in load_profiles().values():
        _collect(pdict)

    failures: list[tuple[str, str]] = []
    for s in sorted(specs):
        try:
            parse_agent_spec(s)
        except Exception as exc:  # pragma: no cover - failure path
            failures.append((s, str(exc)))
    assert not failures, f"profile specs failed to parse: {failures}"


def test_parse_agent_spec_accepts_default_routing_specs() -> None:
    """DEFAULT_AGENT_ROUTING values must all parse."""
    from arnold.pipelines.megaplan.profiles import DEFAULT_AGENT_ROUTING
    from arnold.pipelines.megaplan.types import parse_agent_spec

    for spec in set(DEFAULT_AGENT_ROUTING.values()):
        parse_agent_spec(spec)


def test_parse_agent_spec_resolves_symbolic_premium_placeholder() -> None:
    from arnold.pipelines.megaplan.types import (
        format_agent_spec,
        parse_agent_spec,
        resolve_premium_placeholder_spec,
    )

    parsed = parse_agent_spec("premium:low")
    assert parsed.agent == "premium"
    assert parsed.model is None
    assert parsed.effort == "low"
    assert format_agent_spec(resolve_premium_placeholder_spec(parsed, "codex")) == "codex:low"
