"""Fail-closed proof helpers for M7 model/resource capabilities.

This module is deliberately separate from Megaplan's human/container
verification capability registry. It covers only authored model/resource
requirements that can be proven from neutral pipeline metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from arnold.pipeline.step_invocation import StepInvocation

MODEL_RESOURCE_CAPABILITIES: frozenset[str] = frozenset(
    {"model:text", "model:vision", "decoder:image"}
)
CAPABILITY_ALIASES: Mapping[str, str] = {
    "requires-vision-model": "model:vision",
    "requires-image-decoder": "decoder:image",
}

_EXPLICIT_CAPABILITY_FIELDS = (
    "capabilities",
    "provided_capabilities",
    "resource_capabilities",
    "supported_capabilities",
)
_MODALITY_FIELDS = ("modality", "modalities", "input_modality", "input_modalities")
_DECODER_FIELDS = ("decoder", "decoders", "output_decoder", "output_decoders")
_TEXT_FIELDS = ("prompt", "message", "messages", "history", "prompt_components")
_MEDIA_FIELDS = ("media", "media_refs", "attachments")


@dataclass(frozen=True)
class CapabilityEvidence:
    """One proof record for a capability derived from authored metadata."""

    capability: str
    source: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityProof:
    """Fail-closed result for one stage's authored capability requirements."""

    required_capabilities: tuple[str, ...]
    normalized_required_capabilities: tuple[str, ...]
    proven_capabilities: tuple[str, ...]
    unsatisfied_capabilities: tuple[str, ...]
    unknown_required_capabilities: tuple[str, ...]
    unknown_provided_capabilities: tuple[str, ...]
    evidence: tuple[CapabilityEvidence, ...]

    @property
    def ok(self) -> bool:
        return not self.unsatisfied_capabilities and not self.unknown_required_capabilities


def prove_invocation_capabilities(invocation: StepInvocation | None) -> tuple[CapabilityEvidence, ...]:
    """Return capabilities provable from a step invocation's metadata alone."""
    if invocation is None:
        return ()
    evidence: list[CapabilityEvidence] = []
    metadata = _mapping_or_empty(invocation.metadata)
    adapter_config = _mapping_or_empty(metadata.get("adapter_config"))

    evidence.extend(
        _explicit_capability_evidence(
            adapter_config,
            source="invocation.adapter_config",
        )
    )
    evidence.extend(
        _explicit_capability_evidence(
            metadata,
            source="invocation.metadata",
        )
    )

    if invocation.kind == "model":
        if _has_text_payload(adapter_config) or _has_text_payload(metadata):
            evidence.append(
                CapabilityEvidence(
                    capability="model:text",
                    source="invocation.model_payload",
                    details={"kind": invocation.kind},
                )
            )
        if _has_image_payload(adapter_config) or _has_image_payload(metadata):
            evidence.append(
                CapabilityEvidence(
                    capability="model:vision",
                    source="invocation.media_payload",
                    details={"kind": invocation.kind},
                )
            )

    return _dedupe_evidence(evidence)


def prove_stage_required_capabilities(stage: Any, pipeline: Any | None = None) -> CapabilityProof:
    """Return fail-closed proof state for one stage's required capabilities."""
    required_capabilities = tuple(getattr(stage, "required_capabilities", ()) or ())
    normalized_required = tuple(
        normalize_required_capability(capability) for capability in required_capabilities
    )
    known_required = tuple(
        capability
        for capability in normalized_required
        if capability in MODEL_RESOURCE_CAPABILITIES
    )
    unknown_required = tuple(
        capability
        for capability in normalized_required
        if capability not in MODEL_RESOURCE_CAPABILITIES
    )

    evidence: list[CapabilityEvidence] = list(
        prove_invocation_capabilities(getattr(stage, "invocation", None))
    )
    unknown_provided: list[str] = []

    stage_evidence, stage_unknown = _explicit_subject_capabilities(stage, "stage")
    evidence.extend(stage_evidence)
    unknown_provided.extend(stage_unknown)

    if pipeline is not None:
        pipeline_evidence, pipeline_unknown = _explicit_subject_capabilities(
            pipeline,
            "pipeline",
        )
        evidence.extend(pipeline_evidence)
        unknown_provided.extend(pipeline_unknown)

        for index, bundle in enumerate(_resource_bundles_for_pipeline(pipeline)):
            bundle_evidence, bundle_unknown = _resource_bundle_capabilities(bundle, index)
            evidence.extend(bundle_evidence)
            unknown_provided.extend(bundle_unknown)

    deduped_evidence = _dedupe_evidence(evidence)
    proven = tuple(
        capability
        for capability in _ordered_capabilities(deduped_evidence)
        if capability in known_required
    )
    unsatisfied = tuple(
        capability for capability in known_required if capability not in set(proven)
    )

    return CapabilityProof(
        required_capabilities=required_capabilities,
        normalized_required_capabilities=normalized_required,
        proven_capabilities=proven,
        unsatisfied_capabilities=unsatisfied,
        unknown_required_capabilities=unknown_required,
        unknown_provided_capabilities=tuple(dict.fromkeys(unknown_provided)),
        evidence=deduped_evidence,
    )


def normalize_required_capability(capability: str) -> str:
    return CAPABILITY_ALIASES.get(capability, capability)


def _ordered_capabilities(evidence: tuple[CapabilityEvidence, ...]) -> tuple[str, ...]:
    ordered: list[str] = []
    for item in evidence:
        if item.capability not in ordered:
            ordered.append(item.capability)
    return tuple(ordered)


def _explicit_subject_capabilities(subject: Any, source: str) -> tuple[list[CapabilityEvidence], list[str]]:
    evidence: list[CapabilityEvidence] = []
    unknown: list[str] = []
    for metadata_source, mapping in _metadata_mappings(subject):
        subject_evidence = _explicit_capability_evidence(mapping, source=f"{source}.{metadata_source}")
        evidence.extend(subject_evidence)
        unknown.extend(_unknown_explicit_capabilities(mapping))
    return evidence, unknown


def _resource_bundle_capabilities(bundle: Any, index: int) -> tuple[list[CapabilityEvidence], list[str]]:
    source = f"resource_bundle[{index}]"
    evidence: list[CapabilityEvidence] = []
    unknown: list[str] = []
    for metadata_source, mapping in _metadata_mappings(bundle):
        bundle_evidence = _explicit_capability_evidence(mapping, source=f"{source}.{metadata_source}")
        evidence.extend(bundle_evidence)
        unknown.extend(_unknown_explicit_capabilities(mapping))
    resources = _mapping_or_empty(getattr(bundle, "resources", None))
    if resources:
        resource_evidence = _explicit_capability_evidence(resources, source=f"{source}.resources")
        evidence.extend(resource_evidence)
        unknown.extend(_unknown_explicit_capabilities(resources))
    return evidence, unknown


def _metadata_mappings(subject: Any) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    mappings: list[tuple[str, Mapping[str, Any]]] = []
    for attr in ("capability_metadata", "metadata"):
        value = _mapping_or_empty(getattr(subject, attr, None))
        if value:
            mappings.append((attr, value))
    explicit: dict[str, Any] = {}
    for field_name in _EXPLICIT_CAPABILITY_FIELDS + _MODALITY_FIELDS + _DECODER_FIELDS:
        value = getattr(subject, field_name, None)
        if value is not None:
            explicit[field_name] = value
    if explicit:
        mappings.append(("attrs", explicit))
    return tuple(mappings)


def _explicit_capability_evidence(
    metadata: Mapping[str, Any],
    *,
    source: str,
) -> list[CapabilityEvidence]:
    evidence: list[CapabilityEvidence] = []
    capabilities, _unknown = _known_and_unknown_capabilities(
        _sequence_from_fields(metadata, _EXPLICIT_CAPABILITY_FIELDS)
    )
    for capability in capabilities:
        evidence.append(
            CapabilityEvidence(
                capability=capability,
                source=source,
                details={"proof": "explicit_capability"},
            )
        )

    modalities = _normalized_modalities(_sequence_from_fields(metadata, _MODALITY_FIELDS))
    if "text" in modalities:
        evidence.append(
            CapabilityEvidence(
                capability="model:text",
                source=source,
                details={"proof": "explicit_modality", "modality": "text"},
            )
        )
    if "vision" in modalities:
        evidence.append(
            CapabilityEvidence(
                capability="model:vision",
                source=source,
                details={"proof": "explicit_modality", "modality": "vision"},
            )
        )

    decoders = _normalized_decoders(_sequence_from_fields(metadata, _DECODER_FIELDS))
    if "image" in decoders:
        evidence.append(
            CapabilityEvidence(
                capability="decoder:image",
                source=source,
                details={"proof": "explicit_decoder", "decoder": "image"},
            )
        )
    return evidence


def _unknown_explicit_capabilities(metadata: Mapping[str, Any]) -> list[str]:
    _known, unknown = _known_and_unknown_capabilities(
        _sequence_from_fields(metadata, _EXPLICIT_CAPABILITY_FIELDS)
    )
    return list(unknown)


def _known_and_unknown_capabilities(values: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    known = tuple(value for value in values if value in MODEL_RESOURCE_CAPABILITIES)
    unknown = tuple(value for value in values if value not in MODEL_RESOURCE_CAPABILITIES)
    return known, unknown


def _sequence_from_fields(metadata: Mapping[str, Any], field_names: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    for field_name in field_names:
        if field_name not in metadata:
            continue
        values.extend(_coerce_string_sequence(metadata[field_name]))
    return tuple(values)


def _normalized_modalities(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        lowered = value.strip().lower()
        if lowered in {"text", "vision"} and lowered not in normalized:
            normalized.append(lowered)
    return tuple(normalized)


def _normalized_decoders(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        lowered = value.strip().lower()
        if lowered == "image" and lowered not in normalized:
            normalized.append(lowered)
    return tuple(normalized)


def _has_text_payload(metadata: Mapping[str, Any]) -> bool:
    return any(field_name in metadata and metadata[field_name] for field_name in _TEXT_FIELDS)


def _has_image_payload(metadata: Mapping[str, Any]) -> bool:
    for field_name in _MEDIA_FIELDS:
        if field_name not in metadata:
            continue
        for item in _coerce_sequence(metadata[field_name]):
            if _is_image_descriptor(item):
                return True
    return False


def _is_image_descriptor(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key in ("mime_type", "content_type", "type", "kind"):
            item = value.get(key)
            if isinstance(item, str) and item.lower().startswith("image/"):
                return True
            if isinstance(item, str) and item.lower() in {"image", "vision"}:
                return True
    if isinstance(value, str):
        lowered = value.lower()
        return lowered.startswith("image/") or lowered in {"image", "vision"}
    return False


def _resource_bundles_for_pipeline(pipeline: Any) -> tuple[Any, ...]:
    bundles = getattr(pipeline, "resource_bundles", ()) or ()
    if isinstance(bundles, tuple):
        return bundles
    if isinstance(bundles, list):
        return tuple(bundles)
    return (bundles,) if bundles else ()


def _coerce_string_sequence(value: Any) -> list[str]:
    result: list[str] = []
    for item in _coerce_sequence(value):
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                result.append(stripped)
    return result


def _coerce_sequence(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return (value,)


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _dedupe_evidence(evidence: list[CapabilityEvidence]) -> tuple[CapabilityEvidence, ...]:
    seen: set[tuple[str, str, tuple[tuple[str, Any], ...]]] = set()
    deduped: list[CapabilityEvidence] = []
    for item in evidence:
        key = (
            item.capability,
            item.source,
            tuple(sorted((str(k), v) for k, v in item.details.items())),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return tuple(deduped)
