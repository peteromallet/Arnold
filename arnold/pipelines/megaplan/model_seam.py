"""Model-step seam primitives for Megaplan worker integration.

This module is intentionally small for M3: it establishes the shared request,
telemetry, adapter, and capture contracts without forcing existing worker
consumers off their legacy payload dictionaries yet.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import Enum
from math import ceil
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipeline import (
    ContractResult,
    Provenance,
    StepInvocation,
    StepInvocationAdapterRegistry,
    validate_contract_result,
    validate_payload_against_schema,
)
from arnold.pipelines.megaplan.schemas import SCHEMAS


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


class CompatibilityMode(str, Enum):
    """Whether a step still relies on legacy compatibility repair."""

    NATIVE = "native"
    LEGACY = "legacy"


class ModelFamily(str, Enum):
    """Normalized model families with distinct budget/tokenizer behavior."""

    CODEX = "codex"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"
    KIMI = "kimi"
    GLM = "glm"


class ModelBudgetError(ValueError):
    """Raised when model input cannot be safely budgeted before dispatch."""


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
        super().__init__(f"worker_structural_audit_failed: model output structural audit failed: {details}")
        self.details = details


@dataclass(frozen=True)
class _RecoveredPayload:
    payload: dict[str, Any]
    provenance: str


class ModelStepInvocationAdapter:
    """Concrete ``model`` adapter for ``StepInvocationAdapterRegistry``."""

    def invoke(self, invocation: StepInvocation) -> RenderedStepMessage:
        if invocation.kind != "model":
            raise ValueError(f"ModelStepInvocationAdapter only handles 'model', got {invocation.kind!r}")
        return render_step_message(invocation)


def install_model_step_adapter(registry: StepInvocationAdapterRegistry) -> None:
    """Install the concrete model adapter through the reserved placeholder path."""

    registry.replace_reserved("model", ModelStepInvocationAdapter())


def render_step_message(invocation: StepInvocation) -> RenderedStepMessage:
    """Render a model step into a dispatchable message.

    This is the pre-dispatch chokepoint. It must account for every text-bearing
    request component and reject oversized out-of-band media/reference payloads
    before worker code can send anything to a provider.
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
        model=_optional_str(metadata.get("normalized_model") or metadata.get("model") or metadata.get("worker")),
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


def render_prompt_for_dispatch(
    agent: str,
    step: str,
    state: Mapping[str, Any],
    plan_dir: Path,
    *,
    root: Path | None = None,
    worker: str | None = None,
    model: str | None = None,
    normalized_model: str | None = None,
    tier: ModelTier | str = ModelTier.NON_ENFORCED,
    schema: Mapping[str, Any] | None = None,
    template: Any | None = None,
    prompt_override: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    **prompt_kwargs: object,
) -> RenderedStepMessage:
    """Render shared prompt components through the model seam.

    Legacy callers still consume ``RenderedStepMessage.prompt`` as the same
    string returned by ``create_*_prompt``; the structured fields are carried
    alongside it for budgeting, telemetry, and later capture correlation.
    """

    from arnold.pipelines.megaplan.prompts import PromptComponents, create_prompt_components

    component_metadata = {
        "tier": tier.value if isinstance(tier, ModelTier) else str(tier),
        "worker": worker or agent,
        "model": normalized_model or model,
        "normalized_model": normalized_model or model,
        "validation_step": step,
        **dict(metadata or {}),
    }
    if prompt_override is None:
        components = create_prompt_components(
            agent,
            step,
            state,  # type: ignore[arg-type]
            plan_dir,
            root=root,
            schema=schema,
            template=template,
            metadata=component_metadata,
            **prompt_kwargs,
        )
    else:
        components = PromptComponents(
            prompt=prompt_override,
            schema=dict(schema) if schema is not None else None,
            template=template,
            metadata=component_metadata,
        )
    invocation_metadata = components.to_model_metadata()
    invocation_metadata.update(component_metadata)
    return render_step_message(StepInvocation(kind="model", metadata=invocation_metadata))


def render_compact_review_prompt(
    agent: str,
    step: str,
    state: Mapping[str, Any],
    plan_dir: Path,
    *,
    root: Path | None = None,
    worker: str | None = None,
    model: str | None = None,
    normalized_model: str | None = None,
    tier: ModelTier | str = ModelTier.NON_ENFORCED,
    schema: Mapping[str, Any] | None = None,
    prompt_size_error: dict[str, Any] | None = None,
    pre_check_flags: list[dict[str, Any]] | None = None,
    projection_capabilities: Any | None = None,
) -> RenderedStepMessage:
    """Render a compacted review prompt through the model seam.

    Delegates to :func:`compact_review_prompt` for the actual prompt
    assembly while preserving the same structured ``RenderedStepMessage``
    shape used by the normal ``render_prompt_for_dispatch`` path.

    The compact prompt intentionally carries summaries instead of the
    full patch so the reviewer must inspect the repository directly.
    Every input required by the compaction contract — plan excerpt,
    diff context, projected execution/finalize context, prior unmet
    review block, and pre-check flags — is preserved because
    ``compact_review_prompt`` computes all of them from the same
    ``(state, plan_dir, root)`` triple plus the optional compaction
    parameters.
    """
    from arnold.pipelines.megaplan.prompts.review import compact_review_prompt

    compacted_text = compact_review_prompt(
        state,  # type: ignore[arg-type]
        plan_dir,
        root,
        prompt_size_error=prompt_size_error,
        pre_check_flags=pre_check_flags,
        projection_capabilities=projection_capabilities,
    )
    tier_value = tier.value if isinstance(tier, ModelTier) else str(tier)
    return render_step_message(
        StepInvocation(
            kind="model",
            metadata={
                "tier": tier_value,
                "worker": worker or agent,
                "model": normalized_model or model,
                "normalized_model": normalized_model or model,
                "validation_step": step,
                "prompt": compacted_text,
                "prompt_components": compacted_text,
                "schema": dict(schema) if schema is not None else None,
                "projection_capabilities": projection_capabilities,
            },
        )
    )


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
    ModelFamily.CODEX: ModelBudgetDefaults(max_input_tokens=192_000, tokenizer_source="tiktoken:o200k_base"),
    ModelFamily.CLAUDE: ModelBudgetDefaults(max_input_tokens=180_000, tokenizer_source="claude_conservative_estimate"),
    ModelFamily.DEEPSEEK: ModelBudgetDefaults(max_input_tokens=120_000, tokenizer_source="hf:auto"),
    ModelFamily.KIMI: ModelBudgetDefaults(max_input_tokens=120_000, tokenizer_source="hf:auto"),
    ModelFamily.GLM: ModelBudgetDefaults(max_input_tokens=120_000, tokenizer_source="hf:auto"),
}

_HF_TOKENIZERS: dict[ModelFamily, str] = {
    ModelFamily.DEEPSEEK: "deepseek-ai/DeepSeek-V3",
    ModelFamily.KIMI: "moonshotai/Kimi-K2-Thinking",
    ModelFamily.GLM: "zai-org/GLM-4.5",
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
        raise ModelBudgetError("model family classification requires a normalized model name")
    if ":" in name or lowered.startswith(_PROVIDER_PREFIXES):
        raise ModelBudgetError(f"raw provider-prefixed model name reached model seam: {model!r}")
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
    try:
        family = classify_model_family(model or "")
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


def _checked_budget(
    *,
    family: ModelFamily | None,
    input_tokens: int,
    max_input_tokens: int,
    tokenizer_source: str,
    degraded_reason: str | None = None,
) -> ModelBudget:
    status = BudgetStatus.DEGRADED_FALLBACK if degraded_reason else BudgetStatus.WITHIN_BUDGET
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


def _selected_template(metadata: Mapping[str, Any], schema: Mapping[str, Any] | None) -> Any | None:
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


def _selected_messages(metadata: Mapping[str, Any], prompt: str) -> list[Mapping[str, Any]]:
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


def _selected_stdin(metadata: Mapping[str, Any], messages: tuple[Mapping[str, Any], ...]) -> str | None:
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
        max_items=_optional_int(metadata.get("max_reference_items")) or _DEFAULT_MAX_REFERENCE_ITEMS,
        max_bytes=_optional_int(metadata.get("max_reference_bytes")) or _DEFAULT_MAX_REFERENCE_BYTES,
    )
    media_items = _items_for_fields(metadata, _MEDIA_FIELDS)
    _check_item_budget(
        "media",
        media_items,
        max_items=_optional_int(metadata.get("max_media_items")) or _DEFAULT_MAX_MEDIA_ITEMS,
        max_bytes=_optional_int(metadata.get("max_media_bytes")) or _DEFAULT_MAX_MEDIA_BYTES,
    )


def _items_for_fields(metadata: Mapping[str, Any], field_names: tuple[str, ...]) -> list[Any]:
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
        raise ModelBudgetError(f"{label} budget exceeded: {len(items)} items > {max_items} items")
    total_bytes = sum(_declared_payload_bytes(item) for item in items)
    if total_bytes > max_bytes:
        raise ModelBudgetError(f"{label} budget exceeded: {total_bytes} bytes > {max_bytes} bytes")


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
        return len(_stable_text({key: value for key, value in item.items() if key != "data"}).encode("utf-8"))
    return len(_stable_text(item).encode("utf-8"))


def capture_step_output(
    invocation: StepInvocation,
    output: Mapping[str, Any] | str,
) -> CaptureOutcome:
    """Capture model output without breaking legacy payload consumers.

    The capture boundary keeps legacy dict consumers intact while establishing a
    typed authority: parse/recover first, run enumerated legacy compatibility
    validation only when requested, then let the structural audit decide whether
    the typed result is authoritative.
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
            generator="arnold.pipelines.megaplan.model_seam",
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
        raise TypeError(f"model output must be a mapping or JSON string, got {type(output).__name__}")
    recovery = invocation.metadata.get("capture_recovery")
    if isinstance(recovery, Mapping) and bool(recovery.get("prefer_output_file", False)):
        recovered = _recover_payload_for_invocation(invocation, output)
        if recovered is not None:
            return recovered
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        recovered = _recover_payload_for_invocation(invocation, output)
        if recovered is not None:
            return recovered
        raise
    if not isinstance(parsed, Mapping):
        raise TypeError("model output JSON must contain an object")
    return dict(parsed), ("model_step_output",)


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


def _recovery_payload_looks_like_step(step: str, payload: Mapping[str, Any]) -> bool:
    schema_key = _CAPTURE_SCHEMA_KEYS_BY_STEP.get(step)
    required = set()
    if schema_key is not None:
        schema = SCHEMAS.get(schema_key)
        if isinstance(schema, Mapping):
            required = set(schema.get("required", ()))
    if required.intersection(payload):
        return True
    if step == "execute" and {"task_updates", "sense_check_acknowledgments"}.intersection(payload):
        return True
    return False


def _recovery_critique_completeness_score(item: _RecoveredPayload) -> tuple[int, int]:
    checks = item.payload.get("checks", [])
    if not isinstance(checks, list):
        return (0, 0)
    completed_checks = 0
    total_findings = 0
    for check in checks:
        if not isinstance(check, Mapping):
            continue
        findings = check.get("findings", [])
        if not isinstance(findings, list) or not findings:
            continue
        completed_checks += 1
        total_findings += len(findings)
    return (completed_checks, total_findings)


def _recover_payload_with_provenance(
    step: str,
    *,
    plan_dir: Path,
    output_path: Path,
    raw: str,
    prefer_output_file: bool = True,
) -> _RecoveredPayload | None:
    file_payload = None
    template_payload = None
    candidate_payloads: list[_RecoveredPayload] = []
    try:
        file_payload = _parse_recovery_json_file(output_path)
    except (FileNotFoundError, TypeError, ValueError):
        try:
            file_raw = output_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        else:
            candidate_payloads.extend(
                _RecoveredPayload(payload=candidate, provenance="output_file_recovered")
                for candidate in _extract_recovery_json_candidates(file_raw)
            )
    fallback_names = {
        "critique": "critique_output.json",
        "review": "review_output.json",
    }
    fallback_name = fallback_names.get(step, f"{step}_output.json")
    fallback_path = plan_dir / fallback_name
    if fallback_path != output_path and fallback_path.exists():
        try:
            template_payload = _parse_recovery_json_file(fallback_path)
        except (FileNotFoundError, TypeError, ValueError):
            try:
                fallback_raw = fallback_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
            else:
                candidate_payloads.extend(
                    _RecoveredPayload(payload=candidate, provenance="template_file_recovered")
                    for candidate in _extract_recovery_json_candidates(fallback_raw)
                )
    if file_payload is None and template_payload is not None:
        file_payload = template_payload
        template_payload = None
    output_is_template_file = output_path == fallback_path
    output_is_single_critique_check = (
        step == "critique"
        and output_path.name.startswith("critique_check_")
        and output_path.suffix == ".json"
    )
    validation_errors: list[str] = []
    if (
        prefer_output_file
        and file_payload is not None
        and (step != "critique" or output_is_template_file or output_is_single_critique_check)
    ):
        preferred_payload = dict(file_payload)
        try:
            audit_step_payload(step, preferred_payload)
        except ModelStructuralAuditError as error:
            if _recovery_payload_looks_like_step(step, preferred_payload):
                candidate_payloads.insert(
                    0,
                    _RecoveredPayload(payload=file_payload, provenance="output_file"),
                )
                validation_errors.append(error.details)
        else:
            return _RecoveredPayload(payload=preferred_payload, provenance="output_file")
    raw_candidates = _extract_recovery_json_candidates(raw)
    if file_payload is not None:
        if not any(candidate.payload is file_payload for candidate in candidate_payloads):
            candidate_payloads.insert(
                0,
                _RecoveredPayload(payload=file_payload, provenance="output_file"),
            )
    if template_payload is not None:
        insert_at = 1 if file_payload is not None else 0
        candidate_payloads.insert(
            insert_at,
            _RecoveredPayload(payload=template_payload, provenance="template_file"),
        )
    candidate_payloads.extend(
        _RecoveredPayload(payload=candidate, provenance="raw_output")
        for candidate in raw_candidates
    )
    valid_payloads: list[_RecoveredPayload] = []
    for candidate in candidate_payloads:
        payload = dict(candidate.payload)
        try:
            audit_step_payload(step, payload)
        except ModelStructuralAuditError as error:
            if _recovery_payload_looks_like_step(step, payload):
                validation_errors.append(error.details)
            continue
        valid_payloads.append(_RecoveredPayload(payload=payload, provenance=candidate.provenance))
    if not valid_payloads:
        if validation_errors:
            unique_errors = list(dict.fromkeys(validation_errors))
            raise ModelStructuralAuditError(
                f"Recovered JSON object for {step} failed validation: "
                + " | ".join(unique_errors),
            )
        return None
    if step == "critique" and len(valid_payloads) > 1:
        return max(valid_payloads, key=_recovery_critique_completeness_score)
    return valid_payloads[0]


def _recover_payload_for_invocation(invocation: StepInvocation, raw: str) -> tuple[dict[str, Any], tuple[str, ...]] | None:
    recovery = invocation.metadata.get("capture_recovery")
    if not isinstance(recovery, Mapping):
        return None
    step = _optional_str(recovery.get("step") or invocation.metadata.get("validation_step"))
    plan_dir = recovery.get("plan_dir")
    output_path = recovery.get("output_path")
    if step is None or plan_dir is None or output_path is None:
        return None
    recovered = _recover_payload_with_provenance(
        step,
        plan_dir=Path(plan_dir),
        output_path=Path(output_path),
        raw=raw,
        prefer_output_file=bool(recovery.get("prefer_output_file", True)),
    )
    if recovered is None:
        return None
    return dict(recovered.payload), ("model_step_output", f"codex_recovery:{recovered.provenance}")


def _repair_callback(invocation: StepInvocation) -> Callable[[Mapping[str, Any], ContractResult], Mapping[str, Any] | str] | None:
    callback = invocation.metadata.get("envelope_repair_callback")
    if callable(callback):
        return callback
    return None


def _repair_invocation(invocation: StepInvocation, repair_attempt: int) -> StepInvocation:
    return StepInvocation(
        kind=invocation.kind,
        metadata={**dict(invocation.metadata), "repair_attempt": repair_attempt},
    )


def _compatibility_projection(invocation: StepInvocation, payload: dict[str, Any]) -> dict[str, Any]:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    if step is None:
        return payload
    mode = _compatibility_mode_for_step(step)
    if mode is CompatibilityMode.NATIVE:
        return payload
    raise AssertionError(
        "Phase 5 deletion invariant violated: "
        f"_compatibility_projection received non-native step {step!r} "
        f"with mode {mode.value!r}. Run assert_all_compatibility_modes_native() "
        "before deleting shared legacy helpers."
    )


def _normalize_native_capture_payload(invocation: StepInvocation, payload: dict[str, Any]) -> dict[str, Any]:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    if step == "review":
        return _normalize_review_capture_payload(payload)
    if step == "critique":
        return _normalize_critique_capture_payload(payload)
    if step == "critique_evaluator":
        return _normalize_critique_evaluator_capture_payload(payload)
    if step == "prep-distill":
        return _normalize_prep_distill_capture_payload(payload)
    if step != "finalize":
        return payload
    if _finalize_schema_requires_nullable_task_optionals(invocation):
        return payload
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return payload
    normalized = dict(payload)
    normalized["tasks"] = [
        _strip_null_finalize_task_optionals(task) if isinstance(task, Mapping) else task
        for task in tasks
    ]
    return normalized


def _normalize_prep_distill_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["key_evidence"] = [
        _normalize_prep_key_evidence(item)
        for item in _as_sequence(normalized.get("key_evidence"))
    ]
    normalized["relevant_code"] = [
        _normalize_prep_relevant_code(item)
        for item in _as_sequence(normalized.get("relevant_code"))
    ]
    normalized["test_expectations"] = [
        _normalize_prep_test_expectation(index, item)
        for index, item in enumerate(_as_sequence(normalized.get("test_expectations")), start=1)
    ]
    if "open_questions" in normalized:
        normalized["open_questions"] = [
            _normalize_prep_open_question(item)
            for item in _as_sequence(normalized.get("open_questions"))
        ]
    return normalized


def _normalize_prep_key_evidence(item: Any) -> Any:
    if isinstance(item, str):
        return {"point": item, "source": "prep-distill", "relevance": "medium"}
    if not isinstance(item, Mapping):
        return item
    normalized = dict(item)
    if "point" not in normalized:
        normalized["point"] = _optional_str(
            normalized.get("finding")
            or normalized.get("summary")
            or normalized.get("text")
            or normalized.get("claim")
        ) or ""
    if "source" not in normalized:
        normalized["source"] = _optional_str(
            normalized.get("file")
            or normalized.get("file_path")
            or normalized.get("code_ref")
        ) or "prep-distill"
    normalized["relevance"] = _normalize_prep_relevance(normalized.get("relevance"))
    return {key: normalized[key] for key in ("point", "source", "relevance")}


def _normalize_prep_relevant_code(item: Any) -> Any:
    if isinstance(item, str):
        return {"file_path": item, "why": "Referenced by prep-distill.", "functions": []}
    if not isinstance(item, Mapping):
        return item
    normalized = dict(item)
    file_path = _optional_str(
        normalized.get("file_path")
        or normalized.get("path")
        or normalized.get("file")
        or normalized.get("code_ref")
    ) or ""
    why = _optional_str(
        normalized.get("why")
        or normalized.get("reason")
        or normalized.get("summary")
        or normalized.get("note")
    ) or "Referenced by prep-distill."
    functions = normalized.get("functions")
    if functions is None:
        functions = normalized.get("symbols")
    return {
        "file_path": file_path,
        "why": why,
        "functions": [_optional_str(item) or "" for item in _as_sequence(functions)],
    }


def _normalize_prep_test_expectation(index: int, item: Any) -> Any:
    if isinstance(item, str):
        return {
            "test_id": f"prep-distill-{index}",
            "what_it_checks": item,
            "status": "pass_to_pass",
        }
    if not isinstance(item, Mapping):
        return item
    normalized = dict(item)
    test_id = _optional_str(
        normalized.get("test_id")
        or normalized.get("id")
        or normalized.get("name")
    ) or f"prep-distill-{index}"
    what_it_checks = _optional_str(
        normalized.get("what_it_checks")
        or normalized.get("checks")
        or normalized.get("expectation")
        or normalized.get("description")
    ) or ""
    status = normalized.get("status")
    if status not in {"fail_to_pass", "pass_to_pass"}:
        status = "pass_to_pass"
    return {"test_id": test_id, "what_it_checks": what_it_checks, "status": status}


def _normalize_prep_open_question(item: Any) -> Any:
    if isinstance(item, str):
        return {"severity": "assume_and_proceed", "question": item}
    if not isinstance(item, Mapping):
        return item
    normalized = dict(item)
    classification = _optional_str(normalized.pop("classification", None))
    if normalized.get("severity") not in {"blocking", "assume_and_proceed"}:
        if classification == "blocking":
            normalized["severity"] = "blocking"
        else:
            normalized["severity"] = "assume_and_proceed"
    normalized["question"] = _optional_str(
        normalized.get("question")
        or normalized.get("gap")
        or normalized.get("issue")
        or normalized.get("text")
    ) or ""
    return {
        "severity": normalized["severity"],
        "question": normalized["question"],
        "assumption": _optional_str(normalized.get("assumption")) or "",
    }


def _normalize_prep_relevance(value: Any) -> str:
    if value in {"high", "medium", "low"}:
        return str(value)
    return "medium"


def _finalize_schema_requires_nullable_task_optionals(invocation: StepInvocation) -> bool:
    """Return true when the active finalize schema uses OpenAI strict nullables.

    OpenAI structured outputs require every property key to appear in
    ``required``. For optional finalize task objects, runtime schema generation
    therefore emits ``stance``/``stop_signal`` as required-but-nullable. In that
    case we must keep explicit ``null`` values until after structural audit;
    the finalize handler strips them before writing artifacts.
    """
    schema = invocation.metadata.get("capture_schema") or invocation.metadata.get("output_schema")
    if not isinstance(schema, Mapping):
        schema = invocation.metadata.get("schema")
    if not isinstance(schema, Mapping):
        return False
    try:
        task_schema = schema["properties"]["tasks"]["items"]
        required = set(task_schema.get("required", []))
        properties = task_schema.get("properties", {})
    except (KeyError, TypeError, AttributeError):
        return False
    for field in ("stance", "stop_signal"):
        if field not in required:
            return False
        field_schema = properties.get(field)
        if not isinstance(field_schema, Mapping):
            return False
        field_type = field_schema.get("type")
        if isinstance(field_type, str):
            if field_type != "null":
                return False
        elif isinstance(field_type, list):
            if "null" not in field_type:
                return False
        else:
            return False
    return True


def _normalize_review_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("checks") is None:
        normalized["checks"] = []
    normalized.pop("review_completion_status", None)
    return normalized


def _normalize_critique_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    flags = normalized.get("flags")
    if isinstance(flags, list):
        normalized["flags"] = [
            _normalize_critique_flag(flag) if isinstance(flag, Mapping) else flag
            for flag in flags
        ]
    return normalized


def _normalize_critique_flag(flag: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(flag)
    severity_hint = normalized.get("severity_hint")
    if severity_hint in {"high", "significant", "major", "critical"}:
        normalized["severity_hint"] = "likely-significant"
    elif severity_hint in {"low", "minor", "trivial", "cosmetic"}:
        normalized["severity_hint"] = "likely-minor"
    elif severity_hint in {"medium", "moderate", "unknown", None, ""}:
        normalized["severity_hint"] = "uncertain"
    return normalized


def _normalize_critique_evaluator_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("flag_verifications") is None:
        normalized["flag_verifications"] = []
    selections = normalized.get("selections")
    if isinstance(selections, list):
        normalized["selections"] = [
            _normalize_critique_evaluator_selection(selection)
            if isinstance(selection, Mapping)
            else selection
            for selection in selections
        ]
    return normalized


def _normalize_critique_evaluator_selection(selection: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(selection)
    if normalized.get("area") is None:
        normalized["area"] = ""
    if normalized.get("check_id") != "other":
        # The prompt historically allowed catalog selections to include an
        # optional rationale, but the live schema routes catalog lenses by
        # complexity only. Drop it before structural audit so strict-mode model
        # verbosity does not wedge adaptive critique.
        normalized.pop("why", None)
    return normalized


def _strip_null_finalize_task_optionals(task: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(task)
    for optional_object_field in ("stance", "stop_signal"):
        if normalized.get(optional_object_field) is None:
            normalized.pop(optional_object_field, None)
    return normalized


def schema_audits_step_payload(step: str | None) -> bool:
    return _compatibility_mode_for_step(step) is CompatibilityMode.NATIVE


def audit_step_payload(step: str, payload: Mapping[str, Any]) -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={"compatibility_validation_step": step},
    )
    contract = ContractResult(
        payload={
            "legacy_payload": dict(payload),
            "telemetry": {},
        },
        authority_level="typed",
        provenance=Provenance(
            sources=("recovered_step_output",),
            generator="arnold.pipelines.megaplan.model_seam",
        ),
    )
    _audit_capture_payload(invocation, payload, contract)


def _audit_capture_payload(
    invocation: StepInvocation,
    payload: Mapping[str, Any],
    contract: ContractResult,
) -> None:
    schema = invocation.metadata.get("capture_schema") or invocation.metadata.get("output_schema")
    if not isinstance(schema, Mapping):
        schema = invocation.metadata.get("schema")
    if not isinstance(schema, Mapping):
        schema = _capture_schema_for_invocation(invocation)
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


_CAPTURE_SCHEMA_KEYS_BY_STEP: dict[str, str] = {
    "execute": "execution_batch_relaxed.json",
    "finalize": "finalize.json",
    "critique": "critique.json",
    "review": "review.json",
    "gate": "gate.json",
    "plan": "plan.json",
    "prep": "prep.json",
    "prep-triage": "prep_triage.json",
    "prep-distill": "prep.json",
    "prep-research": "research.json",
    "feedback": "feedback.json",
    "critique_evaluator": "critique_evaluator.json",
    "revise": "revise.json",
    "loop_plan": "loop_plan.json",
    "loop_execute": "loop_execute.json",
    "tiebreaker_researcher": "tiebreaker_researcher.json",
    "tiebreaker_challenger": "tiebreaker_challenger.json",
}

_COMPATIBILITY_MODE_BY_STEP: dict[str, CompatibilityMode] = {
    "execute": CompatibilityMode.NATIVE,
    "finalize": CompatibilityMode.NATIVE,
    "critique": CompatibilityMode.NATIVE,
    "review": CompatibilityMode.NATIVE,
    "gate": CompatibilityMode.NATIVE,
    "plan": CompatibilityMode.NATIVE,
    "prep": CompatibilityMode.NATIVE,
    "prep-triage": CompatibilityMode.NATIVE,
    "prep-distill": CompatibilityMode.NATIVE,
    "prep-research": CompatibilityMode.NATIVE,
    "feedback": CompatibilityMode.NATIVE,
    "critique_evaluator": CompatibilityMode.NATIVE,
    "revise": CompatibilityMode.NATIVE,
    "loop_plan": CompatibilityMode.NATIVE,
    "loop_execute": CompatibilityMode.NATIVE,
    "tiebreaker_researcher": CompatibilityMode.NATIVE,
    "tiebreaker_challenger": CompatibilityMode.NATIVE,
}


def _remaining_legacy_compatibility_steps() -> tuple[str, ...]:
    return tuple(
        sorted(
            step
            for step, mode in _COMPATIBILITY_MODE_BY_STEP.items()
            if mode is CompatibilityMode.LEGACY
        )
    )


def assert_all_compatibility_modes_native() -> None:
    remaining = _remaining_legacy_compatibility_steps()
    if not remaining:
        return
    quoted_steps = ", ".join(f'"{step}"' for step in remaining)
    raise AssertionError(
        "Phase 5 deletion guard blocked: legacy compatibility steps remain in "
        f"_COMPATIBILITY_MODE_BY_STEP: {quoted_steps}. Migrate these steps to "
        "CompatibilityMode.NATIVE before deleting shared legacy helpers."
    )


def _compatibility_mode_for_step(step: str | None) -> CompatibilityMode:
    if step is None:
        return CompatibilityMode.LEGACY
    return _COMPATIBILITY_MODE_BY_STEP.get(step, CompatibilityMode.LEGACY)


def _capture_schema_for_invocation(invocation: StepInvocation) -> Mapping[str, Any] | None:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    schema_key = _CAPTURE_SCHEMA_KEYS_BY_STEP.get(step or "")
    if schema_key is not None:
        schema = SCHEMAS.get(schema_key)
        if isinstance(schema, Mapping):
            capture_schema = deepcopy(schema)
            capture_schema.setdefault("additionalProperties", False)
            return capture_schema
    return None


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
    "audit_step_payload",
    "budget_model_input",
    "capture_step_output",
    "classify_model_family",
    "assert_all_compatibility_modes_native",
    "install_model_step_adapter",
    "render_compact_review_prompt",
    "render_prompt_for_dispatch",
    "render_step_message",
    "schema_audits_step_payload",
]
