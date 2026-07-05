from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.fallback_chains import (
    ExecuteFallbackUnsafe,
    FallbackSpecChain,
    classify_retryability,
    decode_fallback_specs,
    decode_phase_model_value,
    encode_fallback_specs,
    encode_phase_model_value,
    is_retryable_failure,
    map_fallback_spec_value,
    normalize_fallback_spec_list,
    normalize_fallback_spec_value,
    provider_family,
    select_fallback_spec,
    validate_fallback_spec_value,
)


def test_normalize_scalar_and_list_values() -> None:
    assert normalize_fallback_spec_list("codex", path="phase.plan") == ("codex",)
    assert normalize_fallback_spec_value(
        ["codex", "hermes:deepseek:deepseek-v4-pro"],
        path="phase.execute",
    ) == ["codex", "hermes:deepseek:deepseek-v4-pro"]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ([], "path.to.phase must not be an empty list"),
        ([1], "path.to.phase[0] must be a string"),
        (["codex", ""], "path.to.phase[1] must be a non-empty string"),
    ],
)
def test_invalid_arrays_raise_path_specific_validation_errors(value: object, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        validate_fallback_spec_value(value, path="path.to.phase")  # type: ignore[arg-type]


def test_map_and_select_helpers_preserve_shape() -> None:
    assert map_fallback_spec_value("codex", lambda spec: f"{spec}:high") == "codex:high"
    assert map_fallback_spec_value(["codex", "claude"], lambda spec: f"{spec}:low") == [
        "codex:low",
        "claude:low",
    ]
    assert select_fallback_spec(["codex", "claude"], 1) == "claude"


def test_encoded_round_trip_helpers_are_compact_and_decode_back() -> None:
    chain = FallbackSpecChain.from_value(["codex", "hermes:deepseek:deepseek-v4-pro"])
    encoded = encode_fallback_specs(chain)
    assert encoded == '__fallback_json__:["codex","hermes:deepseek:deepseek-v4-pro"]'
    assert decode_fallback_specs(encoded) == chain.specs

    phase_entry = encode_phase_model_value("execute", chain)
    assert phase_entry == 'execute=__fallback_json__:["codex","hermes:deepseek:deepseek-v4-pro"]'
    phase, decoded_chain = decode_phase_model_value(phase_entry)
    assert phase == "execute"
    assert decoded_chain == chain


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("not_prefixed", "missing the reserved __fallback_json__ prefix"),
        ("__fallback_json__:{", "malformed fallback JSON payload"),
        ("__fallback_json__:{}", "must decode to a JSON array of spec strings"),
        ('__fallback_json__:["codex",1]', "fallback_json[1] must be a string"),
    ],
)
def test_malformed_encoded_values_fail_loudly(value: str, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        decode_fallback_specs(value)


@pytest.mark.parametrize(
    ("spec", "family"),
    [
        ("codex:gpt-5.4", "codex"),
        ("claude:sonnet", "claude"),
        ("hermes:deepseek:deepseek-v4-pro", "deepseek"),
        ("hermes:fireworks:accounts/fireworks/models/kimi-k2p6", "fireworks"),
        ("hermes:mimo:mimo-v2-pro", "mimo"),
        ("hermes:openai:gpt-5", "openai"),
    ],
)
def test_provider_family_classification(spec: str, family: str) -> None:
    assert provider_family(spec) == family


@pytest.mark.parametrize(
    ("value", "classification", "retryable"),
    [
        ({"status_code": 503, "error_kind": "network"}, "availability", True),
        ({"code": "internal_error"}, "infrastructure", True),
        ({"status_code": 429, "message": "rate limit hit"}, "rate_limit", False),
        ({"status_code": 401, "message": "unauthorized"}, "auth", False),
        ({"status_code": 402, "message": "credit balance is too low"}, "quota", False),
        ({"status_code": 400, "code": "unsupported_model"}, "unsupported_model", False),
        ({"code": "schema"}, "schema", False),
        ({"code": "semantic"}, "semantic", False),
        ({"retryable": False}, "permanent", False),
        (SimpleNamespace(retryable=True), "infrastructure", True),
    ],
)
def test_retryability_boundaries(value: object, classification: str, retryable: bool) -> None:
    assert classify_retryability(value) == classification
    assert is_retryable_failure(value) is retryable


def test_execute_fallback_unsafe_carries_selected_attempt_metadata() -> None:
    error = ExecuteFallbackUnsafe(
        phase="execute",
        configured_specs=["codex", "hermes:deepseek:deepseek-v4-pro"],
        attempted_index=1,
    )
    assert error.code == "execute_fallback_unsafe"
    assert error.phase == "execute"
    assert error.selected_spec == "hermes:deepseek:deepseek-v4-pro"
    assert error.attempted_index == 1
    assert error.attempted_total == 2
