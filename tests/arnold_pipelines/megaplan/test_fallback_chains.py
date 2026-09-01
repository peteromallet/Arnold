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
    is_cross_family_retryable_classification,
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
        ["codex", "omp:deepseek/deepseek-v4-pro"],
        path="phase.execute",
    ) == ["codex", "omp:deepseek/deepseek-v4-pro"]


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
    chain = FallbackSpecChain.from_value(["codex", "omp:deepseek/deepseek-v4-pro"])
    encoded = encode_fallback_specs(chain)
    assert encoded == '__fallback_json__:["codex","omp:deepseek/deepseek-v4-pro"]'
    assert decode_fallback_specs(encoded) == chain.specs

    phase_entry = encode_phase_model_value("execute", chain)
    assert phase_entry == 'execute=__fallback_json__:["codex","omp:deepseek/deepseek-v4-pro"]'
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
        ("omp:deepseek/deepseek-v4-pro", "deepseek"),
        ("omp:fireworks/kimi-k2.6", "fireworks"),
        ("omp:mimo/mimo-v2-pro", "mimo"),
        ("omp:openai/gpt-5", "openai"),
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
        # Non-transient billing exhaustion reported as HTTP 429 must classify
        # as quota (not rate_limit) so the configured fallback chain advances.
        (
            {"status_code": 429, "message": "credit balance is too low"},
            "quota",
            False,
        ),
        (
            {
                "status_code": 429,
                "error_kind": "balance",
                "message": "余额不足或无可用资源包,请充值。",
            },
            "quota",
            False,
        ),
        (
            {"status_code": 429, "message": "余额不足或无可用资源包,请充值。"},
            "quota",
            False,
        ),
    ],
)
def test_retryability_boundaries(value: object, classification: str, retryable: bool) -> None:
    assert classify_retryability(value) == classification
    assert is_retryable_failure(value) is retryable


def test_codex_auth_error_surface_classifies_as_auth() -> None:
    """Codex auth failures (401 revoked/invalidated token) must classify as
    ``auth`` so configured-spec fallback can advance read-only phases.

    The codex worker raises CliError(code="auth_error", message="Codex
    authentication failed...") with no status_code and no _external_error
    (workers/_impl.py:6228-6238, _CODEX_ERROR_PATTERNS 3194-3195). Before the
    fix, ``auth_error`` was absent from _AUTH_TOKENS and the message needle
    list lacked "authentication", so classify_retryability returned
    "unknown" and _advance_configured_spec_fallback could never rescue a
    codex auth outage even with a 2-spec chain configured.
    """
    # CliError-dict surface built by _configured_spec_failure_class.
    assert (
        classify_retryability(
            {
                "code": "auth_error",
                "message": (
                    "Codex authentication failed. Re-run the same step on "
                    "Codex once before changing agent."
                ),
                "status_code": None,
                "retryable": None,
            }
        )
        == "auth"
    )
    # Flat _external_error surface (workers/hermes.py shape).
    assert (
        classify_retryability(
            {
                "status_code": 401,
                "message": "Your authentication token has been invalidated",
                "error_kind": "auth",
            }
        )
        == "auth"
    )
    # Raw codex transport text as the message still classifies as auth via the
    # "authentication" needle (refresh_token_invalidated revocations).
    assert (
        classify_retryability(
            {
                "code": "auth_error",
                "message": (
                    "Your access token could not be refreshed because your "
                    "refresh token was revoked. Please log out and sign in again."
                ),
            }
        )
        == "auth"
    )


def test_codex_no_credits_surface_classifies_as_quota() -> None:
    """Codex billing exhaustion ("no credits remaining") must classify as
    ``quota`` (durable, cross-family fallbackable), not ``availability``.

    The codex worker maps the raw transport text "stream disconnected before
    completion: You have no credits remaining..." to
    CliError(code="quota_exceeded", message="Codex quota exceeded. ...") via
    the _CODEX_ERROR_PATTERNS row added BEFORE the generic
    "stream disconnected before completion" connection_error row
    (workers/_impl.py:3171-3180). The CliError-dict surface below is exactly
    what _configured_spec_failure_class builds for classify_retryability
    (workers/_impl.py:7208-7219). Before the fix the code surface was
    connection_error -> availability, so the durable billing condition was
    treated as a transient transport drop (astrid-first m6 finalize stall,
    occurrence fc98376b2f10).
    """
    # CliError-dict surface built by _configured_spec_failure_class.
    assert (
        classify_retryability(
            {
                "code": "quota_exceeded",
                "message": (
                    "Codex quota exceeded. Do not retry immediately; this "
                    "condition cannot recover on its own."
                ),
                "status_code": None,
                "retryable": None,
            }
        )
        == "quota"
    )
    # The pre-existing "usage limit" codex row classifies via the same token.
    assert (
        classify_retryability(
            {
                "code": "quota_exceeded",
                "message": "Codex usage limit reached. Try again at a later time.",
                "status_code": None,
                "retryable": None,
            }
        )
        == "quota"
    )
    # Raw codex transport text as the message still classifies as quota via
    # the "billing"/"credit balance" needles.
    assert (
        classify_retryability(
            {
                "code": "connection_error",
                "message": (
                    "stream disconnected before completion: You have no "
                    "credits remaining. Add credits to continue using the API "
                    "at https://platform.openai.com/settings/organization/billing/."
                ),
            }
        )
        == "quota"
    )


def test_classify_retryability_reads_nested_extra_external_error() -> None:
    # workers/hermes.py wraps provider failures as
    # CliError("worker_error", ..., extra={"_external_error": <dict>}); the
    # structured status_code/error_kind live nested there.  classify_retryability
    # must see them (previously "unknown" for every wrapped provider error).
    from arnold_pipelines.megaplan.types import CliError

    wrapped = CliError(
        "worker_error",
        "Hermes worker failed for step 'plan': Error code: 429 - ...",
        extra={
            "_external_error": {
                "provider": "zhipu",
                "error_kind": "balance",
                "message": "余额不足或无可用资源包,请充值。",
                "status_code": 429,
            }
        },
    )
    assert classify_retryability(wrapped) == "quota"
    # A genuine transient rate limit stays rate_limit even when wrapped.
    wrapped_rate = CliError(
        "worker_error",
        "Hermes worker failed for step 'plan'",
        extra={
            "_external_error": {
                "provider": "zhipu",
                "error_kind": "rate_limit",
                "message": "rate limit hit",
                "status_code": 429,
            }
        },
    )
    assert classify_retryability(wrapped_rate) == "rate_limit"


def test_cross_family_advance_membership() -> None:
    from arnold_pipelines.megaplan.fallback_chains import (
        is_cross_family_retryable_classification,
    )

    assert is_cross_family_retryable_classification("availability")
    assert is_cross_family_retryable_classification("infrastructure")
    # Typed billing/auth/rate-limit failures never authorize a configured
    # target under frozen NBF06 v1.
    assert not is_cross_family_retryable_classification("quota")
    assert not is_cross_family_retryable_classification("rate_limit")
    assert not is_cross_family_retryable_classification("auth")
    assert not is_cross_family_retryable_classification("unknown")


def test_explicit_nonretryable_stays_permanent_despite_quota_words() -> None:
    # Explicit nonretryable/provider-contract evidence outranks quota words.
    value = {
        "nonretryable": True,
        "error_kind": "provider_contract",
        "error_layer": "schema_error",
        "message": "quota limit exceeded while validating provider contract",
        "status_code": 429,
    }
    assert classify_retryability(value) == "permanent"



def test_unrelated_nonretryable_error_stays_permanent() -> None:
    # The credential-preflight carve-out must not weaken other explicit
    # nonretryable errors (schema contract, semantic, etc.).
    value = {
        "nonretryable": True,
        "error_kind": "semantic",
        "error_layer": "output_validation",
        "message": "output failed semantic validation",
    }
    assert classify_retryability(value) == "permanent"


def test_same_family_quota_stays_fail_closed() -> None:
    from arnold_pipelines.megaplan.fallback_chains import (
        is_same_family_operational_classification,
    )

    # quota is NOT in the same-family operational set: a same-family retry
    # hits the same exhausted provider.
    assert not is_same_family_operational_classification("quota")


def test_execute_fallback_unsafe_carries_selected_attempt_metadata() -> None:
    error = ExecuteFallbackUnsafe(
        phase="execute",
        configured_specs=["codex", "omp:deepseek/deepseek-v4-pro"],
        attempted_index=1,
    )
    assert error.code == "execute_fallback_unsafe"
    assert error.phase == "execute"
    assert error.selected_spec == "omp:deepseek/deepseek-v4-pro"
    assert error.attempted_index == 1
    assert error.attempted_total == 2
