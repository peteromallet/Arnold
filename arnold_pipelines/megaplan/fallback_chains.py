"""Shared fallback-chain primitives for Megaplan model routing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Literal

from arnold.runtime.errors import ArnoldError
from arnold_pipelines.megaplan.types import parse_agent_spec

FALLBACK_JSON_PREFIX = "__fallback_json__:"

FallbackSpecValue = str | list[str]
RetryabilityClass = Literal[
    "availability",
    "infrastructure",
    "auth",
    "quota",
    "rate_limit",
    "bad_request",
    "unsupported_model",
    "context_window",
    "semantic",
    "schema",
    "test",
    "evidence",
    "blocked",
    "gate",
    "review",
    "malformed_output",
    "permanent",
    "unknown",
]

_NON_RETRYABLE_TOKEN_MAP: tuple[tuple[str, RetryabilityClass], ...] = (
    ("malformed_output", "malformed_output"),
    ("schema", "schema"),
    ("semantic", "semantic"),
    ("evidence", "evidence"),
    ("blocked", "blocked"),
    ("review", "review"),
    ("gate", "gate"),
    ("test", "test"),
)
_AUTH_TOKENS = frozenset(
    {
        "auth",
        "authentication",
        "unauthorized",
        "forbidden",
        "invalid_api_key",
        "invalid_auth",
        "permission_denied",
    }
)
_QUOTA_TOKENS = frozenset(
    {
        "quota",
        "billing",
        "insufficient_credits",
        "credit_balance",
        "payment_required",
    }
)
_RATE_LIMIT_TOKENS = frozenset({"rate_limit", "rate_limited", "throttled", "retry_after"})
_BAD_REQUEST_TOKENS = frozenset({"bad_request", "invalid_request", "validation_error"})
_UNSUPPORTED_MODEL_TOKENS = frozenset(
    {"unsupported_model", "model_not_found", "unknown_model", "no_such_model"}
)
_CONTEXT_WINDOW_TOKENS = frozenset(
    {"context_length", "context_window", "max_tokens", "token_limit", "too_many_tokens"}
)
_AVAILABILITY_TOKENS = frozenset(
    {
        "availability",
        "connection_error",
        "network",
        "timeout",
        "timed_out",
        "worker_timeout",
        "streaming_timeout",
        "slow_output",
        "slow_visible_output",
        "no_observable_activity",
        "reasoning_grace_exhausted",
        "tool_activity_timeout",
        "stalled_stream",
        "stream_content_stall",
        "codex_pre_first_byte_stall",
        "service_unavailable",
        "unavailable",
        "overloaded",
    }
)
_INFRASTRUCTURE_TOKENS = frozenset(
    {
        "infrastructure",
        "internal_error",
        "tool_failure",
        "launch_failure",
        "worker_stall",
        "crash",
    }
)


def _validation_error(path: str, message: str) -> ValueError:
    return ValueError(f"{path} {message}")


def _validate_scalar_spec(spec: Any, *, path: str) -> str:
    if not isinstance(spec, str):
        raise _validation_error(path, "must be a string")
    if not spec:
        raise _validation_error(path, "must be a non-empty string")
    return spec


def normalize_fallback_spec_list(value: str | list[str] | tuple[str, ...], *, path: str) -> tuple[str, ...]:
    """Normalize a scalar-or-list fallback input to an immutable spec tuple."""
    if isinstance(value, str):
        return (_validate_scalar_spec(value, path=path),)
    if not isinstance(value, (list, tuple)):
        raise _validation_error(path, "must be a string or a non-empty list[str]")
    if not value:
        raise _validation_error(path, "must not be an empty list")
    return tuple(_validate_scalar_spec(item, path=f"{path}[{index}]") for index, item in enumerate(value))


def normalize_fallback_spec_value(value: str | list[str] | tuple[str, ...], *, path: str) -> FallbackSpecValue:
    """Validate a scalar-or-list value while preserving scalar vs list shape."""
    normalized = normalize_fallback_spec_list(value, path=path)
    if isinstance(value, str):
        return normalized[0]
    return list(normalized)


def validate_fallback_spec_value(value: str | list[str] | tuple[str, ...], *, path: str) -> None:
    normalize_fallback_spec_list(value, path=path)


@dataclass(frozen=True, slots=True)
class FallbackSpecChain:
    """Canonical ordered fallback chain."""

    specs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "specs", normalize_fallback_spec_list(self.specs, path="specs"))

    @classmethod
    def from_value(cls, value: str | list[str] | tuple[str, ...], *, path: str = "value") -> FallbackSpecChain:
        return cls(normalize_fallback_spec_list(value, path=path))

    def __iter__(self):
        return iter(self.specs)

    def __len__(self) -> int:
        return len(self.specs)

    @property
    def is_scalar(self) -> bool:
        return len(self.specs) == 1

    def selected(self, index: int = 0) -> str:
        if index < 0 or index >= len(self.specs):
            raise IndexError(f"fallback chain index {index} out of range for {len(self.specs)} specs")
        return self.specs[index]

    def map(self, mapper: Callable[[str], str]) -> FallbackSpecChain:
        mapped = tuple(_validate_scalar_spec(mapper(spec), path=f"mapped[{index}]") for index, spec in enumerate(self.specs))
        return FallbackSpecChain(mapped)

    def to_value(self) -> FallbackSpecValue:
        if self.is_scalar:
            return self.specs[0]
        return list(self.specs)

    def encode(self) -> str:
        return encode_fallback_specs(self.specs)

    def encode_phase_model(self, phase: str) -> str:
        return encode_phase_model_value(phase, self)


def map_fallback_spec_value(
    value: str | list[str] | tuple[str, ...],
    mapper: Callable[[str], str],
    *,
    path: str = "value",
) -> FallbackSpecValue:
    return FallbackSpecChain.from_value(value, path=path).map(mapper).to_value()


def select_fallback_spec(value: str | list[str] | tuple[str, ...], index: int = 0, *, path: str = "value") -> str:
    return FallbackSpecChain.from_value(value, path=path).selected(index)


def is_encoded_fallback_specs(value: str) -> bool:
    return value.startswith(FALLBACK_JSON_PREFIX)


def encode_fallback_specs(value: FallbackSpecChain | str | list[str] | tuple[str, ...]) -> str:
    if isinstance(value, FallbackSpecChain):
        specs = value.specs
    else:
        specs = normalize_fallback_spec_list(value, path="value")
    return FALLBACK_JSON_PREFIX + json.dumps(list(specs), separators=(",", ":"))


def decode_fallback_specs(encoded: str) -> tuple[str, ...]:
    if not is_encoded_fallback_specs(encoded):
        raise ValueError("encoded fallback value is missing the reserved __fallback_json__ prefix")
    payload = encoded[len(FALLBACK_JSON_PREFIX):]
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed fallback JSON payload: {exc.msg}") from exc
    if not isinstance(decoded, list):
        raise ValueError("fallback JSON payload must decode to a JSON array of spec strings")
    return normalize_fallback_spec_list(decoded, path="fallback_json")


def encode_phase_model_value(
    phase: str,
    value: FallbackSpecChain | str | list[str] | tuple[str, ...],
) -> str:
    _validate_scalar_spec(phase, path="phase")
    chain = value if isinstance(value, FallbackSpecChain) else FallbackSpecChain.from_value(value)
    selected = chain.selected()
    spec_value = selected if chain.is_scalar else chain.encode()
    return f"{phase}={spec_value}"


def decode_phase_model_value(entry: str) -> tuple[str, FallbackSpecChain]:
    _validate_scalar_spec(entry, path="phase_model")
    if "=" not in entry:
        raise ValueError("phase_model must contain '='")
    phase, raw_value = entry.split("=", 1)
    _validate_scalar_spec(phase, path="phase_model.phase")
    if is_encoded_fallback_specs(raw_value):
        return phase, FallbackSpecChain(decode_fallback_specs(raw_value))
    return phase, FallbackSpecChain.from_value(raw_value, path=f"{phase}.spec")


def configured_fallback_chain_for_phase(
    phase_models: list[str] | tuple[str, ...] | None,
    phase: str,
) -> FallbackSpecChain | None:
    """Return the configured chain for *phase* from phase_model entries."""
    if not isinstance(phase_models, (list, tuple)):
        return None
    for entry in phase_models:
        if not isinstance(entry, str) or "=" not in entry:
            continue
        entry_phase, chain = decode_phase_model_value(entry)
        if entry_phase == phase:
            return chain
    return None


def fallback_observability_fields(
    configured_specs: FallbackSpecChain | str | list[str] | tuple[str, ...] | None,
    *,
    attempt_index: int = 0,
    attempted_specs: str | list[str] | tuple[str, ...] | None = None,
    failed_attempt_reasons: list[str] | tuple[str, ...] | None = None,
    fallback_trigger: str | None = None,
) -> dict[str, Any]:
    """Build additive fallback observability fields with normalized shapes."""
    if configured_specs is None:
        return {}
    chain = (
        configured_specs
        if isinstance(configured_specs, FallbackSpecChain)
        else FallbackSpecChain.from_value(configured_specs, path="configured_specs")
    )
    if attempt_index < 0 or attempt_index >= len(chain):
        raise ValueError(
            f"attempt_index {attempt_index} is out of range for {len(chain)} configured_specs"
        )
    attempted = (
        normalize_fallback_spec_list(
            attempted_specs or chain.specs[: attempt_index + 1],
            path="attempted_specs",
        )
    )
    reasons: list[str] = []
    for index, reason in enumerate(failed_attempt_reasons or ()):
        if not isinstance(reason, str):
            raise TypeError(f"failed_attempt_reasons[{index}] must be a string")
        if not reason:
            raise ValueError(f"failed_attempt_reasons[{index}] must be a non-empty string")
        reasons.append(reason)
    if len(reasons) > len(attempted):
        raise ValueError("failed_attempt_reasons cannot exceed attempted_specs length")
    if fallback_trigger is not None:
        if not isinstance(fallback_trigger, str):
            raise TypeError("fallback_trigger must be a string when provided")
        if not fallback_trigger:
            raise ValueError("fallback_trigger must be a non-empty string when provided")
    return {
        "configured_specs": list(chain.specs),
        "attempted_specs": list(attempted),
        "selected_spec_index": attempt_index,
        "selected_spec_total": len(chain),
        "fallback_trigger": fallback_trigger,
        "failed_attempt_reasons": reasons,
    }


def provider_family(spec: str) -> str:
    """Return the provider-family boundary used for fallback independence."""
    parsed = parse_agent_spec(spec)
    if parsed.agent == "hermes" and isinstance(parsed.model, str) and parsed.model:
        family = parsed.model.split(":", 1)[0].strip().lower()
        alias_map = {
            "openai-codex": "codex",
            "openai": "openai",
            "deep-seek": "deepseek",
            "fireworks-ai": "fireworks",
            "fireworks_ai": "fireworks",
        }
        return alias_map.get(family, family)
    if parsed.agent == "premium":
        return "premium"
    return parsed.agent.lower()


def _object_field(value: object, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _normalized_tokens(value: object) -> set[str]:
    tokens: set[str] = set()
    field_names = (
        "category",
        "kind",
        "code",
        "error_kind",
        "error_layer",
        "provider_error_code",
        "failure_kind",
        "reason",
        "status",
    )
    for field_name in field_names:
        raw = _object_field(value, field_name)
        if not isinstance(raw, str):
            continue
        normalized = raw.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized:
            tokens.add(normalized)
    message = _object_field(value, "message")
    if isinstance(message, str):
        lowered = message.lower()
        for needle in (
            "rate limit",
            "quota",
            "credit balance",
            "billing",
            "unauthorized",
            "forbidden",
            "bad request",
            "context length",
            "unsupported model",
            "model not found",
            "timed out",
            "timeout",
            "service unavailable",
            "internal error",
            "blocked",
            "review",
            "gate",
            "schema",
            "semantic",
            "malformed output",
            "evidence",
            "test",
        ):
            if needle in lowered:
                tokens.add(needle.replace(" ", "_"))
    return tokens


def classify_retryability(value: object | None) -> RetryabilityClass:
    """Classify whether a failure is eligible for cross-provider fallback."""
    if value is None:
        return "unknown"

    status_code = _object_field(value, "status_code")
    retry_after_s = _object_field(value, "retry_after_s")
    retryable = _object_field(value, "retryable")
    tokens = _normalized_tokens(value)

    for token, classification in _NON_RETRYABLE_TOKEN_MAP:
        if token in tokens:
            return classification
    if retry_after_s is not None or status_code == 429 or tokens & _RATE_LIMIT_TOKENS:
        return "rate_limit"
    if status_code in {401, 403} or tokens & _AUTH_TOKENS:
        return "auth"
    if status_code == 402 or tokens & _QUOTA_TOKENS:
        return "quota"
    if tokens & _UNSUPPORTED_MODEL_TOKENS:
        return "unsupported_model"
    if tokens & _CONTEXT_WINDOW_TOKENS:
        return "context_window"
    if status_code in {400, 404, 422} or tokens & _BAD_REQUEST_TOKENS:
        return "bad_request"
    if status_code in {408, 500, 502, 503, 504} or tokens & _AVAILABILITY_TOKENS:
        return "availability"
    if tokens & _INFRASTRUCTURE_TOKENS:
        return "infrastructure"
    if retryable is True:
        return "infrastructure"
    if retryable is False:
        return "permanent"
    return "unknown"


@dataclass(frozen=True, slots=True)
class FailureDisposition:
    """Eligibility class plus the stable reason emitted in receipts."""

    classification: RetryabilityClass
    reason_code: str
    mutation_safe_to_retry: bool | None = None


def _mutation_safe_attestation(value: object | None) -> bool | None:
    """Return an executor's explicit retry-safety attestation, if present.

    An unchanged checkout proves only that repository files did not change.  It
    cannot prove that a tool did not mutate an external system, so execute
    fallback additionally requires the executor to attest that no tool activity
    capable of side effects was observed.  Missing or malformed evidence is
    deliberately unknown and therefore fails closed at the execute boundary.
    """

    raw = _object_field(value, "mutation_safe_to_retry")
    if isinstance(raw, bool):
        return raw
    extra = getattr(value, "extra", None)
    if isinstance(extra, dict):
        raw = extra.get("mutation_safe_to_retry")
        if isinstance(raw, bool):
            return raw
    return None


def failure_reason_code(value: object | None) -> str:
    """Return a stable, specific reason without conflating semantic failure."""

    if value is None:
        return "unknown"
    for field_name in (
        "progress_reason",
        "error_layer",
        "provider_error_code",
        "code",
        "error_kind",
        "failure_kind",
        "reason",
        "kind",
        "category",
    ):
        raw = _object_field(value, field_name)
        if isinstance(raw, str) and raw.strip():
            return raw.strip().lower().replace("-", "_").replace(" ", "_")
    return classify_retryability(value)


def classify_failure(value: object | None) -> FailureDisposition:
    return FailureDisposition(
        classification=classify_retryability(value),
        reason_code=failure_reason_code(value),
        mutation_safe_to_retry=_mutation_safe_attestation(value),
    )


def is_retryable_classification(classification: RetryabilityClass) -> bool:
    return classification in {"availability", "infrastructure"}


def is_same_family_operational_classification(
    classification: RetryabilityClass,
) -> bool:
    """Return whether a non-writing same-family model fallback may advance."""

    return classification in {"availability", "rate_limit", "unsupported_model"}


def is_retryable_failure(value: object | None) -> bool:
    return is_retryable_classification(classify_retryability(value))


class ExecuteFallbackUnsafe(ArnoldError):
    """Raised when execute resumes at a fallback index without attempt evidence."""

    def __init__(
        self,
        *,
        phase: str,
        configured_specs: FallbackSpecChain | str | list[str] | tuple[str, ...],
        attempted_index: int,
    ) -> None:
        chain = (
            configured_specs
            if isinstance(configured_specs, FallbackSpecChain)
            else FallbackSpecChain.from_value(configured_specs, path="configured_specs")
        )
        selected_spec = chain.selected(attempted_index)
        total = len(chain)
        super().__init__(
            "execute_fallback_unsafe",
            (
                f"Phase '{phase}' entered fallback index {attempted_index} "
                "without mutation-safety evidence from the preceding attempt; "
                f"refusing to dispatch index {attempted_index} of {total} "
                f"({selected_spec})."
            ),
        )
        self.phase = phase
        self.configured_specs = chain.specs
        self.attempted_index = attempted_index
        self.attempted_total = total
        self.selected_spec = selected_spec


class ExecuteFallbackMutationUnsafe(ArnoldError):
    """A failed execute attempt changed the project, so retry is prohibited."""

    def __init__(
        self,
        *,
        configured_specs: FallbackSpecChain | str | list[str] | tuple[str, ...],
        attempted_index: int,
        trigger: str,
        changed_paths: tuple[str, ...] = (),
        guard_error: str | None = None,
    ) -> None:
        chain = (
            configured_specs
            if isinstance(configured_specs, FallbackSpecChain)
            else FallbackSpecChain.from_value(configured_specs, path="configured_specs")
        )
        path_summary = ", ".join(changed_paths[:8]) if changed_paths else "unknown"
        detail = (
            f"workspace changed ({path_summary})"
            if changed_paths
            else f"mutation proof unavailable ({guard_error or 'unknown guard error'})"
        )
        super().__init__(
            "execute_fallback_mutation_unsafe",
            (
                "Execute fallback was eligible but was not mutation-safe: "
                f"attempt {attempted_index + 1}/{len(chain)} failed with {trigger}; "
                f"{detail}. Resolve or roll back the partial attempt explicitly "
                "before selecting another model."
            ),
        )
        self.configured_specs = chain.specs
        self.attempted_index = attempted_index
        self.trigger = trigger
        self.changed_paths = changed_paths
        self.guard_error = guard_error
