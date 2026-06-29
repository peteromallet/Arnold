"""Generic model-step seam primitives for arnold.pipeline.

This module hosts the family-agnostic core of the model seam:

- Enums + dataclasses (tier/budget/audit/telemetry/rendered + captured)
- Tokenizer table + family classification + ``budget_model_input``
- ``render_step_message`` (pre-dispatch chokepoint, budget + media gates)
- ``ModelStepInvocationAdapter`` / ``install_model_step_adapter`` (registry wiring)
- Generic ``capture_step_output`` core + structural audit + one-shot repair
- Recovery JSON parsers (``_iter_recovery_json_dicts``,
  ``_extract_recovery_json_candidates``, ``_parse_recovery_json_file``)

Step-name-keyed extension points (review/execute/critique/etc. payload
normalizers, capture-schema lookup, recovery shape checks) are NOT hard-coded
here. They register against the four hook tables exposed at module top via:

- ``register_native_normalizer(step, fn)`` — payload normalizer per step
- ``register_compatibility_projection(step, fn)`` — non-native projection
- ``register_capture_schema_resolver(fn)`` — resolves the capture schema for
  a ``StepInvocation`` (returns ``Mapping[str, Any] | None``)
- ``register_recovery_step_shape_check(fn)`` — predicate
  ``(step, payload) -> bool`` used during recovery to decide whether a
  candidate payload is plausibly the right step shape

A pipeline that wants to host new step-keyed behavior REGISTERS callables
against these hooks at its package import time; the generic module remains
pipeline-blind.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from enum import Enum
from math import ceil
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipeline import (
    ContractResult,
    Provenance,
    validate_contract_result,
    validate_payload_against_schema,
)
from arnold.execution.step_invocation import StepInvocation, StepInvocationAdapterRegistry


# --------------------------------------------------------------------------- #
# Public enums
# --------------------------------------------------------------------------- #


class ModelTier(str, Enum):
    """Enforcement tier used by a model-step invocation."""

    ENFORCED = "enforced"
    NON_ENFORCED = "non_enforced"


class BudgetStatus(str, Enum):
    """Budget-check result emitted by the seam."""

    NOT_EVALUATED = "not_evaluated"
    WITHIN_BUDGET = "within_budget"
    EXCEEDED = "exceeded"
    DEGRADED_FALLBACK = "degraded_fallback"


class AuditStatus(str, Enum):
    """Structural audit result emitted by the seam."""

    NOT_EVALUATED = "not_evaluated"
    PASSED = "passed"
    FAILED = "failed"


class TerminalStatus(str, Enum):
    """Terminal outcome status emitted by the seam."""

    RENDERED = "rendered"
    CAPTURED = "captured"
    FAILED = "failed"


class ModelFamily(str, Enum):
    """Normalized model families with distinct budget/tokenizer behavior."""

    CODEX = "codex"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"
    KIMI = "kimi"
    GLM = "glm"
    MIMO = "mimo"


class ModelBudgetError(ValueError):
    """Raised when model input cannot be safely budgeted before dispatch."""


# --------------------------------------------------------------------------- #
# Public dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ModelBudgetDefaults:
    """Static budget defaults for model-family assembly checks."""

    max_input_tokens: int
    tokenizer_source: str


@dataclass(frozen=True)
class ModelBudget:
    """Concrete budget estimate for one rendered model message."""

    family: ModelFamily | None
    input_tokens: int
    max_input_tokens: int
    tokenizer_source: str
    budget_result: BudgetStatus
    degraded_reason: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "family": self.family.value if self.family is not None else None,
            "input_tokens": self.input_tokens,
            "max_input_tokens": self.max_input_tokens,
            "tokenizer_source": self.tokenizer_source,
            "budget_result": self.budget_result.value,
            "degraded_reason": self.degraded_reason,
        }


@dataclass(frozen=True)
class TierMetadata:
    """Stable tier metadata for a model-step invocation."""

    tier: ModelTier
    enforced: bool
    worker: str | None = None
    model: str | None = None
    provider: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value,
            "enforced": self.enforced,
            "worker": self.worker,
            "model": self.model,
            "provider": self.provider,
        }

    @classmethod
    def from_invocation(cls, invocation: StepInvocation) -> "TierMetadata":
        metadata = invocation.metadata
        tier_value = str(metadata.get("tier") or ModelTier.NON_ENFORCED.value)
        tier = ModelTier(tier_value)
        enforced = bool(metadata.get("enforced", tier is ModelTier.ENFORCED))
        return cls(
            tier=tier,
            enforced=enforced,
            worker=_optional_str(metadata.get("worker")),
            model=_optional_str(metadata.get("model")),
            provider=_optional_str(metadata.get("provider")),
        )


@dataclass(frozen=True)
class ModelSeamTelemetry:
    """Machine-readable telemetry fields shared by render and capture."""

    tier: TierMetadata
    degraded_reason: str | None = None
    tokenizer_source: str | None = None
    budget_result: BudgetStatus = BudgetStatus.NOT_EVALUATED
    audit_result: AuditStatus = AuditStatus.NOT_EVALUATED
    repair_attempt: int = 0
    terminal_status: TerminalStatus = TerminalStatus.RENDERED

    def to_json(self) -> dict[str, Any]:
        return {
            "tier": self.tier.to_json(),
            "degraded_reason": self.degraded_reason,
            "tokenizer_source": self.tokenizer_source,
            "budget_result": self.budget_result.value,
            "audit_result": self.audit_result.value,
            "repair_attempt": self.repair_attempt,
            "terminal_status": self.terminal_status.value,
        }

    @classmethod
    def from_invocation(
        cls,
        invocation: StepInvocation,
        *,
        terminal_status: TerminalStatus = TerminalStatus.RENDERED,
    ) -> "ModelSeamTelemetry":
        metadata = invocation.metadata
        return cls(
            tier=TierMetadata.from_invocation(invocation),
            degraded_reason=_optional_str(metadata.get("degraded_reason")),
            tokenizer_source=_optional_str(metadata.get("tokenizer_source")),
            budget_result=_enum_or_default(
                BudgetStatus,
                metadata.get("budget_result"),
                BudgetStatus.NOT_EVALUATED,
            ),
            audit_result=_enum_or_default(
                AuditStatus,
                metadata.get("audit_result"),
                AuditStatus.NOT_EVALUATED,
            ),
            repair_attempt=int(metadata.get("repair_attempt") or 0),
            terminal_status=terminal_status,
        )


@dataclass(frozen=True)
class RenderedStepMessage:
    """Rendered model dispatch payload plus seam telemetry."""

    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    prompt: str = ""
    stdin: str | None = None
    messages: tuple[Mapping[str, Any], ...] = ()
    schema: Mapping[str, Any] | None = None
    template: Any | None = None
    envelope_examples: tuple[Mapping[str, Any], ...] = ()
    budget: ModelBudget | None = None
    telemetry: ModelSeamTelemetry = field(
        default_factory=lambda: ModelSeamTelemetry(
            tier=TierMetadata(tier=ModelTier.NON_ENFORCED, enforced=False)
        )
    )

    def to_json(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "metadata": dict(self.metadata),
            "prompt": self.prompt,
            "stdin": self.stdin,
            "messages": [dict(message) for message in self.messages],
            "schema": dict(self.schema) if self.schema is not None else None,
            "template": self.template,
            "envelope_examples": [dict(example) for example in self.envelope_examples],
            "budget": self.budget.to_json() if self.budget is not None else None,
            "telemetry": self.telemetry.to_json(),
        }


@dataclass(frozen=True)
class CaptureOutcome:
    """Capture result that preserves legacy payloads alongside typed authority."""

    contract_result: ContractResult
    legacy_payload: Mapping[str, Any]
    telemetry: ModelSeamTelemetry

    def to_json(self) -> dict[str, Any]:
        return {
            "contract_result": self.contract_result.to_json(),
            "legacy_payload": dict(self.legacy_payload),
            "telemetry": self.telemetry.to_json(),
        }


class ModelStructuralAuditError(ValueError):
    """Raised when captured model output fails the structural audit."""

    def __init__(self, details: str) -> None:
        super().__init__(
            f"worker_structural_audit_failed: model output structural audit failed: {details}"
        )
        self.details = details


@dataclass(frozen=True)
class _RecoveredPayload:
    payload: dict[str, Any]
    provenance: str


# --------------------------------------------------------------------------- #
# Hook registries (step-keyed extension surface)
# --------------------------------------------------------------------------- #

_NativeNormalizerFn = Callable[[Mapping[str, Any]], dict[str, Any]]
_CompatibilityProjectionFn = Callable[[StepInvocation, Mapping[str, Any]], dict[str, Any]]
_CaptureSchemaResolverFn = Callable[[StepInvocation], "Mapping[str, Any] | None"]
_RecoveryShapeCheckFn = Callable[[str, Mapping[str, Any]], bool]

_NATIVE_NORMALIZERS: dict[str, _NativeNormalizerFn] = {}
_COMPATIBILITY_PROJECTIONS: dict[str, _CompatibilityProjectionFn] = {}
_CAPTURE_SCHEMA_RESOLVERS: list[_CaptureSchemaResolverFn] = []
_RECOVERY_SHAPE_CHECKS: list[_RecoveryShapeCheckFn] = []


def register_native_normalizer(step: str, fn: _NativeNormalizerFn) -> None:
    """Register a step-keyed payload normalizer for native-compatibility capture."""

    _NATIVE_NORMALIZERS[step] = fn


def register_compatibility_projection(step: str, fn: _CompatibilityProjectionFn) -> None:
    """Register a step-keyed compatibility projection (non-native mode)."""

    _COMPATIBILITY_PROJECTIONS[step] = fn


def register_capture_schema_resolver(fn: _CaptureSchemaResolverFn) -> None:
    """Register a resolver that returns a capture schema for a StepInvocation.

    Resolvers are tried in registration order; the first non-``None`` result
    wins. Generic capture falls through to the generic envelope schema when
    no resolver returns one.
    """

    _CAPTURE_SCHEMA_RESOLVERS.append(fn)


def register_recovery_step_shape_check(fn: _RecoveryShapeCheckFn) -> None:
    """Register a predicate ``(step, payload) -> bool`` consulted during recovery.

    When any registered predicate returns ``True`` for a step+payload pair, the
    recovery flow treats the payload as plausibly the right shape (used to
    surface validation errors). When no predicates are registered the default
    is permissive (``True``).
    """

    _RECOVERY_SHAPE_CHECKS.append(fn)


def _resolve_capture_schema(invocation: StepInvocation) -> Mapping[str, Any] | None:
    for resolver in _CAPTURE_SCHEMA_RESOLVERS:
        result = resolver(invocation)
        if result is not None:
            return result
    return None


def _recovery_payload_looks_like_step(step: str, payload: Mapping[str, Any]) -> bool:
    if not _RECOVERY_SHAPE_CHECKS:
        return True
    return any(check(step, payload) for check in _RECOVERY_SHAPE_CHECKS)


# --------------------------------------------------------------------------- #
# Adapter wiring
# --------------------------------------------------------------------------- #


class ModelStepInvocationAdapter:
    """Concrete ``model`` adapter for ``StepInvocationAdapterRegistry``."""

    def invoke(self, invocation: StepInvocation) -> RenderedStepMessage:
        if invocation.kind != "model":
            raise ValueError(
                f"ModelStepInvocationAdapter only handles 'model', got {invocation.kind!r}"
            )
        return render_step_message(invocation)


def install_model_step_adapter(registry: StepInvocationAdapterRegistry) -> None:
    """Install the concrete model adapter through the reserved placeholder path."""

    current = registry.resolve("model")
    if isinstance(current, ModelStepInvocationAdapter):
        return
    registry.replace_reserved("model", ModelStepInvocationAdapter())


# --------------------------------------------------------------------------- #
# Render path
# --------------------------------------------------------------------------- #


def render_step_message(invocation: StepInvocation) -> RenderedStepMessage:
    """Render a model step into a dispatchable message.

    This is the pre-dispatch chokepoint. It accounts for every text-bearing
    request component and rejects oversized out-of-band media/reference
    payloads before worker code can send anything to a provider.
    """

    metadata = invocation.metadata
    text = _dispatch_text(metadata)
    worker_payload = _worker_payload(metadata, text)
    budget_text = _assemble_model_text(metadata)
    _enforce_media_reference_budget(metadata)
    telemetry = ModelSeamTelemetry.from_invocation(
        invocation,
        terminal_status=TerminalStatus.RENDERED,
    )
    budget = budget_model_input(
        budget_text,
        model=_optional_str(
            metadata.get("normalized_model")
            or metadata.get("model")
            or metadata.get("worker")
        ),
        tier=telemetry.tier.tier,
        max_input_tokens=_optional_int(metadata.get("max_input_tokens")),
    )
    telemetry = replace(
        telemetry,
        degraded_reason=budget.degraded_reason or telemetry.degraded_reason,
        tokenizer_source=budget.tokenizer_source,
        budget_result=budget.budget_result,
    )
    return RenderedStepMessage(
        text=text,
        metadata=metadata,
        prompt=worker_payload["prompt"],
        stdin=worker_payload["stdin"],
        messages=worker_payload["messages"],
        schema=worker_payload["schema"],
        template=worker_payload["template"],
        envelope_examples=worker_payload["envelope_examples"],
        budget=budget,
        telemetry=telemetry,
    )


# --------------------------------------------------------------------------- #
# Tokenizer / budget machinery
# --------------------------------------------------------------------------- #


_PROVIDER_PREFIXES = (
    "anthropic/",
    "openai/",
    "fireworks/",
    "google/",
    "zhipu/",
    "minimax/",
    "openrouter/",
)

_FAMILY_BUDGET_DEFAULTS: dict[ModelFamily, ModelBudgetDefaults] = {
    ModelFamily.CODEX: ModelBudgetDefaults(
        max_input_tokens=256_000, tokenizer_source="tiktoken:o200k_base"
    ),
    ModelFamily.CLAUDE: ModelBudgetDefaults(
        max_input_tokens=180_000, tokenizer_source="claude_conservative_estimate"
    ),
    ModelFamily.DEEPSEEK: ModelBudgetDefaults(
        max_input_tokens=120_000, tokenizer_source="hf:auto"
    ),
    ModelFamily.KIMI: ModelBudgetDefaults(
        max_input_tokens=120_000, tokenizer_source="hf:auto"
    ),
    ModelFamily.GLM: ModelBudgetDefaults(
        max_input_tokens=120_000, tokenizer_source="hf:auto"
    ),
    ModelFamily.MIMO: ModelBudgetDefaults(
        max_input_tokens=120_000, tokenizer_source="hf:auto"
    ),
}

_HF_TOKENIZERS: dict[ModelFamily, str] = {
    ModelFamily.DEEPSEEK: "deepseek-ai/DeepSeek-V3",
    ModelFamily.KIMI: "moonshotai/Kimi-K2-Thinking",
    ModelFamily.GLM: "zai-org/GLM-4.5",
    ModelFamily.MIMO: "deepseek-ai/DeepSeek-V3",
}
_TOKENIZER_CACHE: dict[str, Any] = {}


def classify_model_family(model: str) -> ModelFamily:
    """Classify an already-normalized model name.

    Raw provider-prefixed names are rejected here. Callers that receive
    provider-prefixed input must normalize through ``resolve_model`` first.
    """

    name = model.strip()
    lowered = name.lower()
    if not name:
        raise ModelBudgetError(
            "model family classification requires a normalized model name"
        )
    if ":" in name or lowered.startswith(_PROVIDER_PREFIXES):
        raise ModelBudgetError(
            f"raw provider-prefixed model name reached model seam: {model!r}"
        )
    if lowered.startswith(("gpt-", "codex-")) or "codex" in lowered:
        return ModelFamily.CODEX
    if lowered == "claude" or lowered.startswith("claude-"):
        return ModelFamily.CLAUDE
    if lowered.startswith("deepseek-") or lowered.startswith("deepseek/"):
        return ModelFamily.DEEPSEEK
    if lowered.startswith("kimi-") or lowered.startswith("kimi/") or "kimi" in lowered:
        return ModelFamily.KIMI
    if lowered.startswith(("glm-", "glm/")):
        return ModelFamily.GLM
    if lowered.startswith(("mimo-", "mimo/")):
        return ModelFamily.MIMO
    raise ModelBudgetError(f"unknown normalized model family: {model!r}")


def budget_model_input(
    text: str,
    *,
    model: str | None,
    tier: ModelTier,
    max_input_tokens: int | None = None,
) -> ModelBudget:
    """Estimate and enforce the static input budget for an assembled message."""

    enforced = tier is ModelTier.ENFORCED
    budget_model = _canonical_budget_model_name(model or "")
    try:
        family = classify_model_family(budget_model)
    except ModelBudgetError:
        if enforced:
            raise
        token_count = _fallback_token_count(text)
        limit = max_input_tokens or 32_000
        return _checked_budget(
            family=None,
            input_tokens=token_count,
            max_input_tokens=limit,
            tokenizer_source="byte_estimate:fallback",
            degraded_reason="unknown_model_family",
        )

    defaults = _FAMILY_BUDGET_DEFAULTS[family]
    source = defaults.tokenizer_source
    token_count = _count_tokens_for_family(text, family)
    if source == "hf:auto" and _TOKENIZER_CACHE.get(family.value) is None:
        source = "byte_estimate:fallback"
    return _checked_budget(
        family=family,
        input_tokens=token_count,
        max_input_tokens=max_input_tokens or defaults.max_input_tokens,
        tokenizer_source=source,
    )


def _canonical_budget_model_name(model: str) -> str:
    """Return a provider-neutral model id for budget family classification.

    Provider resolvers can return transport-specific IDs such as
    ``accounts/fireworks/models/deepseek-v4-pro``. Those are valid dispatch
    model names, but budget classification cares about the underlying model
    family, not the provider path.

    Also strips hermes-style ``provider:`` prefixes (e.g. ``deepseek:``,
    ``fireworks:``, ``mimo:``) that ``resolve_model`` in ``key_pool`` normally
    removes before dispatch, but which can reach the budget seam when
    fanout callers pass the raw ``resolved_model`` from ``AgentMode``
    directly without an intervening ``resolve_model`` call.
    """

    name = model.strip()
    lowered = name.lower()
    marker = "/models/"
    if marker in lowered:
        candidate = name[lowered.rfind(marker) + len(marker):].strip("/")
        if candidate:
            return candidate
    # Strip hermes-style provider: prefix (resolved_model may still carry it).
    _HERMES_PROVIDER_COLON_PREFIXES = (
        "deepseek:", "fireworks:", "mimo:", "openrouter:",
        "minimax:", "zhipu:", "google:",
    )
    if ":" in name and lowered.startswith(_HERMES_PROVIDER_COLON_PREFIXES):
        _, _, candidate = name.partition(":")
        candidate = candidate.strip()
        if candidate:
            return candidate
    return name


def _checked_budget(
    *,
    family: ModelFamily | None,
    input_tokens: int,
    max_input_tokens: int,
    tokenizer_source: str,
    degraded_reason: str | None = None,
) -> ModelBudget:
    status = (
        BudgetStatus.DEGRADED_FALLBACK if degraded_reason else BudgetStatus.WITHIN_BUDGET
    )
    if input_tokens > max_input_tokens:
        raise ModelBudgetError(
            f"model input budget exceeded: {input_tokens} tokens > {max_input_tokens} tokens"
        )
    return ModelBudget(
        family=family,
        input_tokens=input_tokens,
        max_input_tokens=max_input_tokens,
        tokenizer_source=tokenizer_source,
        budget_result=status,
        degraded_reason=degraded_reason,
    )


def _count_tokens_for_family(text: str, family: ModelFamily) -> int:
    if family is ModelFamily.CODEX:
        try:
            import tiktoken  # type: ignore[import-not-found]

            return len(tiktoken.get_encoding("o200k_base").encode(text))
        except Exception:
            return _fallback_token_count(text)
    if family is ModelFamily.CLAUDE:
        return _fallback_token_count(text)
    tokenizer_name = _HF_TOKENIZERS.get(family)
    if tokenizer_name is None:
        return _fallback_token_count(text)
    tokenizer = _lazy_hf_tokenizer(tokenizer_name, family)
    if tokenizer is None:
        return _fallback_token_count(text)
    return len(tokenizer.encode(text))


def _lazy_hf_tokenizer(tokenizer_name: str, family: ModelFamily) -> Any | None:
    cache_key = family.value
    if cache_key in _TOKENIZER_CACHE:
        return _TOKENIZER_CACHE[cache_key]
    try:
        from transformers import AutoTokenizer  # type: ignore[import-not-found]

        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, trust_remote_code=True)
    except Exception:
        tokenizer = None
    _TOKENIZER_CACHE[cache_key] = tokenizer
    return tokenizer


def _fallback_token_count(text: str) -> int:
    return ceil(len(text.encode("utf-8")) / 3 * 1.25)


# --------------------------------------------------------------------------- #
# Text / payload / media assembly
# --------------------------------------------------------------------------- #


_TEXT_BUDGET_FIELDS = (
    "system",
    "history",
    "message",
    "prompt",
    "prefill",
    "tools",
    "tool_schema",
    "tool_schemas",
    "schema",
    "response_schema",
    "template",
    "descriptor",
    "descriptors",
    "prompt_components",
)
_REFERENCE_FIELDS = ("references", "reference_descriptors")
_MEDIA_FIELDS = ("media", "media_refs", "attachments")
_DEFAULT_MAX_MEDIA_ITEMS = 16
_DEFAULT_MAX_MEDIA_BYTES = 20 * 1024 * 1024
_DEFAULT_MAX_REFERENCE_ITEMS = 128
_DEFAULT_MAX_REFERENCE_BYTES = 4 * 1024 * 1024


def _assemble_model_text(metadata: Mapping[str, Any]) -> str:
    sections: list[str] = []
    for field_name in _TEXT_BUDGET_FIELDS:
        if field_name in metadata:
            _append_budget_section(sections, field_name, metadata[field_name])
    for field_name in _REFERENCE_FIELDS:
        if field_name in metadata:
            _append_reference_descriptors(sections, field_name, metadata[field_name])
    return "\n\n".join(sections)


def _dispatch_text(metadata: Mapping[str, Any]) -> str:
    prompt_components = metadata.get("prompt_components")
    if prompt_components is not None:
        component_prompt = _prompt_from_components(prompt_components)
        if component_prompt:
            return component_prompt
    return str(metadata.get("message") or metadata.get("prompt") or "")


def _worker_payload(metadata: Mapping[str, Any], text: str) -> dict[str, Any]:
    schema = _selected_schema(metadata)
    template = _selected_template(metadata, schema)
    prompt = str(metadata.get("prompt") or text)
    messages = tuple(_selected_messages(metadata, prompt))
    stdin = _selected_stdin(metadata, messages)
    return {
        "prompt": prompt,
        "stdin": stdin,
        "messages": messages,
        "schema": schema,
        "template": template,
        "envelope_examples": tuple(_minimal_envelope_examples(schema, template)),
    }


def _prompt_from_components(value: Any) -> str:
    if hasattr(value, "as_prompt_text"):
        return str(value.as_prompt_text())
    if isinstance(value, Mapping):
        prompt = value.get("prompt")
        if prompt is not None:
            return str(prompt)
        messages = value.get("messages")
        if messages is not None:
            return "\n\n".join(
                str(message.get("content", message))
                if isinstance(message, Mapping)
                else str(message)
                for message in _as_sequence(messages)
            )
    return _stable_text(value)


def _selected_schema(metadata: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = metadata.get("schema", metadata.get("response_schema"))
    if isinstance(value, Mapping):
        return value
    return None


def _selected_template(
    metadata: Mapping[str, Any], schema: Mapping[str, Any] | None
) -> Any | None:
    if "template" in metadata:
        return metadata["template"]
    if schema is None:
        return None
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return {}
    return {str(key): _schema_placeholder(value) for key, value in properties.items()}


def _schema_placeholder(schema_fragment: Any) -> Any:
    if not isinstance(schema_fragment, Mapping):
        return "..."
    schema_type = schema_fragment.get("type")
    if isinstance(schema_type, list):
        non_null_types = [item for item in schema_type if item != "null"]
        schema_type = non_null_types[0] if non_null_types else "null"
    if schema_type == "array":
        return []
    if schema_type == "object":
        return {}
    if schema_type == "boolean":
        return False
    if schema_type in {"integer", "number"}:
        return 0
    return "..."


def _selected_messages(
    metadata: Mapping[str, Any], prompt: str
) -> list[Mapping[str, Any]]:
    messages = metadata.get("messages")
    if messages is None:
        messages = metadata.get("history")
    selected: list[Mapping[str, Any]] = []
    for item in _as_sequence(messages):
        if isinstance(item, Mapping):
            role = str(item.get("role") or "user")
            content = str(item.get("content") or item.get("text") or "")
            selected.append({"role": role, "content": content})
        elif item is not None:
            selected.append({"role": "user", "content": str(item)})
    if prompt and (not selected or selected[-1].get("content") != prompt):
        selected.append({"role": "user", "content": prompt})
    return selected


def _selected_stdin(
    metadata: Mapping[str, Any], messages: tuple[Mapping[str, Any], ...]
) -> str | None:
    if "stdin" in metadata:
        value = metadata["stdin"]
        return None if value is None else str(value)
    if not messages:
        return None
    return json.dumps(
        {"messages": [dict(message) for message in messages]},
        sort_keys=True,
        separators=(",", ":"),
    )


def _minimal_envelope_examples(
    schema: Mapping[str, Any] | None,
    template: Any | None,
) -> list[Mapping[str, Any]]:
    if isinstance(template, Mapping) and template:
        return [template]
    if schema is None:
        return [{"output": "..."}]
    properties = schema.get("properties")
    if not isinstance(properties, Mapping) or not properties:
        return [{"output": "..."}]
    return [{str(key): _schema_placeholder(value) for key, value in properties.items()}]


def _append_budget_section(sections: list[str], label: str, value: Any) -> None:
    if value is None or value == "":
        return
    sections.append(f"[{label}]\n{_stable_text(value)}")


def _append_reference_descriptors(sections: list[str], label: str, value: Any) -> None:
    for index, item in enumerate(_as_sequence(value)):
        if isinstance(item, Mapping):
            descriptor = (
                item.get("descriptor")
                or item.get("description")
                or item.get("caption")
                or item.get("text")
                or item.get("summary")
            )
            if descriptor is None:
                descriptor = {
                    key: val
                    for key, val in item.items()
                    if key not in {"bytes", "byte_size", "size_bytes", "content_bytes", "data"}
                }
        else:
            descriptor = item
        _append_budget_section(sections, f"{label}[{index}]", descriptor)


def _stable_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except TypeError:
        return str(value)


def _enforce_media_reference_budget(metadata: Mapping[str, Any]) -> None:
    reference_items = _items_for_fields(metadata, _REFERENCE_FIELDS)
    _check_item_budget(
        "reference",
        reference_items,
        max_items=_optional_int(metadata.get("max_reference_items"))
        or _DEFAULT_MAX_REFERENCE_ITEMS,
        max_bytes=_optional_int(metadata.get("max_reference_bytes"))
        or _DEFAULT_MAX_REFERENCE_BYTES,
    )
    media_items = _items_for_fields(metadata, _MEDIA_FIELDS)
    _check_item_budget(
        "media",
        media_items,
        max_items=_optional_int(metadata.get("max_media_items"))
        or _DEFAULT_MAX_MEDIA_ITEMS,
        max_bytes=_optional_int(metadata.get("max_media_bytes"))
        or _DEFAULT_MAX_MEDIA_BYTES,
    )


def _items_for_fields(
    metadata: Mapping[str, Any], field_names: tuple[str, ...]
) -> list[Any]:
    items: list[Any] = []
    for field_name in field_names:
        if field_name in metadata:
            items.extend(_as_sequence(metadata[field_name]))
    return items


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or isinstance(value, Mapping):
        return [value]
    if isinstance(value, list | tuple | set):
        return list(value)
    return [value]


def _check_item_budget(
    label: str,
    items: list[Any],
    *,
    max_items: int,
    max_bytes: int,
) -> None:
    if len(items) > max_items:
        raise ModelBudgetError(
            f"{label} budget exceeded: {len(items)} items > {max_items} items"
        )
    total_bytes = sum(_declared_payload_bytes(item) for item in items)
    if total_bytes > max_bytes:
        raise ModelBudgetError(
            f"{label} budget exceeded: {total_bytes} bytes > {max_bytes} bytes"
        )


def _declared_payload_bytes(item: Any) -> int:
    if isinstance(item, bytes):
        return len(item)
    if isinstance(item, str):
        return len(item.encode("utf-8"))
    if isinstance(item, Mapping):
        for key in ("bytes", "byte_size", "size_bytes", "content_bytes"):
            value = item.get(key)
            if value is not None:
                return int(value)
        data = item.get("data")
        if isinstance(data, bytes):
            return len(data)
        if isinstance(data, str):
            return len(data.encode("utf-8"))
        return len(
            _stable_text(
                {key: value for key, value in item.items() if key != "data"}
            ).encode("utf-8")
        )
    return len(_stable_text(item).encode("utf-8"))


# --------------------------------------------------------------------------- #
# Capture path
# --------------------------------------------------------------------------- #


def capture_step_output(
    invocation: StepInvocation,
    output: Mapping[str, Any] | str,
) -> CaptureOutcome:
    """Capture model output without breaking legacy payload consumers.

    The capture boundary keeps legacy dict consumers intact while establishing
    a typed authority: parse/recover first, run step-keyed normalizers and
    compatibility projections via the hook registry, then let the structural
    audit decide whether the typed result is authoritative.
    """

    legacy_payload, capture_sources = _capture_payload(invocation, output)
    legacy_payload = _normalize_native_capture_payload(invocation, legacy_payload)
    legacy_payload = _compatibility_projection(invocation, legacy_payload)
    telemetry = ModelSeamTelemetry.from_invocation(
        invocation,
        terminal_status=TerminalStatus.CAPTURED,
    )
    contract = ContractResult(
        payload={
            "legacy_payload": legacy_payload,
            "telemetry": telemetry.to_json(),
        },
        authority_level="typed",
        provenance=Provenance(
            sources=tuple(capture_sources),
            generator="arnold.pipeline.model_seam",
        ),
    )
    try:
        _audit_capture_payload(invocation, legacy_payload, contract)
    except ModelStructuralAuditError:
        if telemetry.tier.enforced:
            raise
        repair_callback = _repair_callback(invocation)
        if repair_callback is None or telemetry.repair_attempt >= 1:
            raise
        repaired_output = repair_callback(legacy_payload, contract)
        repaired_invocation = _repair_invocation(invocation, telemetry.repair_attempt + 1)
        return capture_step_output(repaired_invocation, repaired_output)
    telemetry = replace(telemetry, audit_result=AuditStatus.PASSED)
    contract = replace(
        contract,
        payload={
            "legacy_payload": legacy_payload,
            "telemetry": telemetry.to_json(),
        },
    )
    return CaptureOutcome(
        contract_result=contract,
        legacy_payload=legacy_payload,
        telemetry=telemetry,
    )


def _capture_payload(
    invocation: StepInvocation,
    output: Mapping[str, Any] | str,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    if isinstance(output, Mapping):
        return dict(output), ("model_step_output",)
    if not isinstance(output, str):
        raise TypeError(
            f"model output must be a mapping or JSON string, got {type(output).__name__}"
        )
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        raise
    if not isinstance(parsed, Mapping):
        raise TypeError("model output JSON must contain an object")
    return dict(parsed), ("model_step_output",)


def _normalize_native_capture_payload(
    invocation: StepInvocation, payload: dict[str, Any]
) -> dict[str, Any]:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    if step is None:
        return payload
    normalizer = _NATIVE_NORMALIZERS.get(step)
    if normalizer is None:
        return payload
    return normalizer(payload)


def _compatibility_projection(
    invocation: StepInvocation, payload: dict[str, Any]
) -> dict[str, Any]:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    if step is None:
        return payload
    projection = _COMPATIBILITY_PROJECTIONS.get(step)
    if projection is None:
        return payload
    return projection(invocation, payload)


def _audit_capture_payload(
    invocation: StepInvocation,
    payload: Mapping[str, Any],
    contract: ContractResult,
) -> None:
    schema = invocation.metadata.get("capture_schema") or invocation.metadata.get(
        "output_schema"
    )
    if not isinstance(schema, Mapping):
        schema = invocation.metadata.get("schema")
    if not isinstance(schema, Mapping):
        schema = _resolve_capture_schema(invocation)
    if isinstance(schema, Mapping):
        payload = _normalize_native_capture_payload(invocation, dict(payload))
        result = validate_payload_against_schema(payload, schema)
    else:
        result = validate_contract_result(contract, _capture_outcome_schema())
    if result.ok:
        return
    details = "; ".join(
        f"{diagnostic.code} at {diagnostic.payload_pointer or '/'}: {diagnostic.message}"
        for diagnostic in result.diagnostics
    )
    raise ModelStructuralAuditError(details)


def _capture_outcome_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["legacy_payload", "telemetry"],
        "additionalProperties": False,
        "properties": {
            "legacy_payload": {"type": "object"},
            "telemetry": {"type": "object"},
        },
    }


def _repair_callback(
    invocation: StepInvocation,
) -> Callable[[Mapping[str, Any], ContractResult], Mapping[str, Any] | str] | None:
    callback = invocation.metadata.get("envelope_repair_callback")
    if callable(callback):
        return callback
    return None


def _repair_invocation(invocation: StepInvocation, repair_attempt: int) -> StepInvocation:
    return StepInvocation(
        kind=invocation.kind,
        metadata={**dict(invocation.metadata), "repair_attempt": repair_attempt},
    )


# --------------------------------------------------------------------------- #
# Recovery parsers (generic; step-keyed shape decisions go through the hook)
# --------------------------------------------------------------------------- #


def _parse_recovery_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(path.name) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Output file {path.name} was not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise TypeError(f"Output file {path.name} did not contain a JSON object")
    return dict(payload)


def _iter_recovery_json_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        payload = dict(value)
        candidates = [payload]
        if "structured_output" in value:
            candidates.extend(_iter_recovery_json_dicts(value.get("structured_output")))
        for nested in value.values():
            candidates.extend(_iter_recovery_json_dicts(nested))
        return candidates
    if isinstance(value, list):
        candidates: list[dict[str, Any]] = []
        for item in value:
            candidates.extend(_iter_recovery_json_dicts(item))
        return candidates
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return []
            return _iter_recovery_json_dicts(parsed)
        embedded: list[dict[str, Any]] = []
        decoder = json.JSONDecoder()
        cursor = 0
        while True:
            brace = text.find("{", cursor)
            if brace < 0:
                break
            try:
                parsed, _end = decoder.raw_decode(text[brace:])
            except json.JSONDecodeError:
                cursor = brace + 1
                continue
            embedded.extend(_iter_recovery_json_dicts(parsed))
            cursor = brace + 1
        return embedded
    return []


def _extract_recovery_json_candidates(raw: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    fenced = re.findall(r"```json\s*\n(.*?)```", raw, re.DOTALL)
    for block in fenced:
        try:
            obj = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        candidates.extend(_iter_recovery_json_dicts(obj))

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidates.extend(_iter_recovery_json_dicts(obj))

    decoder = json.JSONDecoder()
    search_start = 0
    while True:
        brace_start = raw.find("{", search_start)
        if brace_start < 0:
            break
        try:
            obj, _end = decoder.raw_decode(raw[brace_start:])
        except json.JSONDecodeError:
            search_start = brace_start + 1
            continue
        candidates.extend(_iter_recovery_json_dicts(obj))
        search_start = brace_start + 1

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            marker = json.dumps(candidate, sort_keys=True)
        except TypeError:
            marker = repr(candidate)
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(candidate)
    return deduped


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _enum_or_default(enum_type: type[Enum], value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    return enum_type(str(value))


__all__ = [
    "AuditStatus",
    "BudgetStatus",
    "CaptureOutcome",
    "ModelBudget",
    "ModelBudgetDefaults",
    "ModelBudgetError",
    "ModelFamily",
    "ModelSeamTelemetry",
    "ModelStepInvocationAdapter",
    "ModelStructuralAuditError",
    "ModelTier",
    "RenderedStepMessage",
    "TerminalStatus",
    "TierMetadata",
    "budget_model_input",
    "capture_step_output",
    "classify_model_family",
    "install_model_step_adapter",
    "register_capture_schema_resolver",
    "register_compatibility_projection",
    "register_native_normalizer",
    "register_recovery_step_shape_check",
    "render_step_message",
]
