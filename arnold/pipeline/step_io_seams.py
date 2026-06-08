"""Stable identifiers for typed step-IO seams."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


_SEAM_SPLIT = "::"
_PORT_SPLIT = "<="
_PORT_REF_SPLIT = "."


@dataclass(frozen=True, order=True)
class SeamId:
    """Unique seam key for one producer-to-consumer port binding."""

    pipeline_id: str
    consumer_step: str
    consumer_port: str
    producer_step: str
    producer_port: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("pipeline_id", self.pipeline_id),
            ("consumer_step", self.consumer_step),
            ("consumer_port", self.consumer_port),
            ("producer_step", self.producer_step),
            ("producer_port", self.producer_port),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{field_name} must be a non-empty string")
            if any(token in value for token in (_SEAM_SPLIT, _PORT_SPLIT, _PORT_REF_SPLIT)):
                raise ValueError(f"{field_name} contains reserved seam delimiter characters")

    def __str__(self) -> str:
        return (
            f"{self.pipeline_id}{_SEAM_SPLIT}"
            f"{self.consumer_step}.{self.consumer_port}"
            f"{_PORT_SPLIT}"
            f"{self.producer_step}.{self.producer_port}"
        )

    @classmethod
    def parse(cls, value: str) -> "SeamId":
        if not isinstance(value, str) or not value:
            raise ValueError("SeamId value must be a non-empty string")
        try:
            pipeline_id, edge = value.split(_SEAM_SPLIT, 1)
            consumer_ref, producer_ref = edge.split(_PORT_SPLIT, 1)
            consumer_step, consumer_port = consumer_ref.split(_PORT_REF_SPLIT, 1)
            producer_step, producer_port = producer_ref.split(_PORT_REF_SPLIT, 1)
        except ValueError as exc:
            raise ValueError(f"Invalid SeamId string: {value!r}") from exc
        return cls(
            pipeline_id=pipeline_id,
            consumer_step=consumer_step,
            consumer_port=consumer_port,
            producer_step=producer_step,
            producer_port=producer_port,
        )


@dataclass(frozen=True)
class SeamResolution:
    """Resolved typed-side metadata for a pipeline binding-map seam."""

    seam_id: SeamId | None
    producer_typed: bool
    consumer_typed: bool
    both_sides_typed: bool
    binding_found: bool
    reason: str = ""


def resolve_seam_from_binding_map(
    pipeline: Any,
    *,
    pipeline_id: str,
    consumer_step: str,
    consumer_port: str,
) -> SeamResolution:
    """Resolve a producer/consumer port pair from ``pipeline.binding_map``.

    Lookup failures intentionally return legacy, non-enforceable metadata
    instead of raising. M1 uses this to cap policy to shadow when a seam cannot
    be resolved without changing production stage-port behavior.
    """

    binding_map = getattr(pipeline, "binding_map", None)
    if not isinstance(binding_map, Mapping):
        return _legacy_resolution("binding lookup unavailable")

    binding = binding_map.get((consumer_step, consumer_port))
    if not _is_binding_pair(binding):
        return _legacy_resolution("binding lookup unavailable")

    producer_step, producer_port = binding
    seam_id = SeamId(
        pipeline_id=pipeline_id,
        consumer_step=consumer_step,
        consumer_port=consumer_port,
        producer_step=producer_step,
        producer_port=producer_port,
    )
    producer_typed = _has_producer_port(pipeline, producer_step, producer_port)
    consumer_typed = _has_consumer_port(pipeline, consumer_step, consumer_port)
    return SeamResolution(
        seam_id=seam_id,
        producer_typed=producer_typed,
        consumer_typed=consumer_typed,
        both_sides_typed=producer_typed and consumer_typed,
        binding_found=True,
    )


def _legacy_resolution(reason: str) -> SeamResolution:
    return SeamResolution(
        seam_id=None,
        producer_typed=False,
        consumer_typed=False,
        both_sides_typed=False,
        binding_found=False,
        reason=reason,
    )


def _is_binding_pair(value: Any) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], str)
    )


def _has_producer_port(pipeline: Any, step_id: str, port_name: str) -> bool:
    stage = _stage_for(pipeline, step_id)
    if stage is None:
        return False
    return any(getattr(port, "name", "") == port_name for port in _stage_produces(stage))


def _has_consumer_port(pipeline: Any, step_id: str, port_name: str) -> bool:
    stage = _stage_for(pipeline, step_id)
    if stage is None:
        return False
    return any(getattr(port, "port_name", getattr(port, "name", "")) == port_name for port in _stage_consumes(stage))


def _stage_for(pipeline: Any, step_id: str) -> Any:
    stages = getattr(pipeline, "stages", None)
    if isinstance(stages, Mapping):
        return stages.get(step_id)
    return None


def _stage_produces(stage: Any) -> tuple[Any, ...]:
    produces = getattr(stage, "produces", None)
    if produces:
        return tuple(produces)
    step = getattr(stage, "step", None)
    step_produces = getattr(step, "produces", None)
    return tuple(step_produces) if step_produces else ()


def _stage_consumes(stage: Any) -> tuple[Any, ...]:
    consumes = getattr(stage, "consumes", None)
    if consumes:
        return tuple(consumes)
    step = getattr(stage, "step", None)
    step_consumes = getattr(step, "consumes", None)
    return tuple(step_consumes) if step_consumes else ()
