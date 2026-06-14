"""Lower authored stage declarations into effective typed binding state.

The author-facing source of truth for new M7 declarations is ``reads`` /
``writes``: typed ``PortRef`` entries in ``reads`` lower into effective
consumes, and typed ``Port`` entries in ``writes`` lower into effective
produces. Legacy untyped ``ReadRef`` / ``WriteRef`` declarations are
preserved separately so validators can continue to reason about gradual
typing paths without forcing them into typed binding.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, is_dataclass, replace
from typing import Any, Iterable, Mapping

from arnold.pipeline.types import Port, PortRef, ReadRef, WriteRef

__all__ = [
    "DeclarationDrift",
    "LoweredDeclarations",
    "bind_with_lowered_declarations",
    "derive_binding_map",
    "lower_stage_declarations",
]

_LEGACY_CARDINALITY_ALIASES = {
    "one": "singleton",
}


@dataclass(frozen=True)
class DeclarationDrift:
    """A mismatch between explicit and lowered typed declarations."""

    code: str
    direction: str
    name: str
    detail: str


@dataclass(frozen=True)
class LoweredDeclarations:
    """Structured lowering state shared by binders and validators."""

    stage_name: str
    declared_produces: tuple[Port, ...]
    declared_consumes: tuple[PortRef, ...]
    typed_writes: tuple[Port, ...]
    typed_reads: tuple[PortRef, ...]
    legacy_writes: tuple[WriteRef, ...]
    legacy_reads: tuple[ReadRef, ...]
    effective_produces: tuple[Port, ...]
    effective_consumes: tuple[PortRef, ...]
    drift_defects: tuple[DeclarationDrift, ...]

    @property
    def clean_binding(self) -> bool:
        return not self.drift_defects


def lower_stage_declarations(stage: Any) -> LoweredDeclarations:
    """Return effective typed declarations plus legacy/untyped leftovers."""

    stage_name = getattr(stage, "name", "?")
    reads = tuple(getattr(stage, "reads", ()) or ())
    writes = tuple(getattr(stage, "writes", ()) or ())
    declared_produces = tuple(getattr(stage, "produces", ()) or ())
    declared_consumes = tuple(getattr(stage, "consumes", ()) or ())

    typed_reads = tuple(item for item in reads if isinstance(item, PortRef))
    legacy_reads = tuple(item for item in reads if isinstance(item, ReadRef))
    typed_writes = tuple(item for item in writes if isinstance(item, Port))
    legacy_writes = tuple(item for item in writes if isinstance(item, WriteRef))

    produce_drift = _declaration_drift(
        stage_name=stage_name,
        direction="produces",
        explicit=declared_produces,
        lowered=typed_writes,
    )
    consume_drift = _declaration_drift(
        stage_name=stage_name,
        direction="consumes",
        explicit=declared_consumes,
        lowered=typed_reads,
    )

    return LoweredDeclarations(
        stage_name=stage_name,
        declared_produces=declared_produces,
        declared_consumes=declared_consumes,
        typed_writes=typed_writes,
        typed_reads=typed_reads,
        legacy_writes=legacy_writes,
        legacy_reads=legacy_reads,
        effective_produces=_dedupe_ports(typed_writes or declared_produces),
        effective_consumes=_dedupe_ports(typed_reads or declared_consumes),
        drift_defects=produce_drift + consume_drift,
    )


def derive_binding_map(
    stages: Mapping[str, Any],
    edges: Mapping[str, Iterable[str]] | Iterable[tuple[str, str]],
    *,
    existing: Mapping[Any, Any] | None = None,
) -> dict | None:
    """Best-effort binding-map derivation for authored typed declarations."""

    existing_map = dict(existing) if isinstance(existing, Mapping) else None
    result = bind_with_lowered_declarations(stages, edges)
    if result is None:
        return existing_map
    from arnold.pipeline.contracts import BindResult
    if not isinstance(result, BindResult):
        return existing_map

    binding_map = dict(result.binding_map)
    if existing_map:
        existing_map.update(binding_map)
        return existing_map
    return binding_map


def bind_with_lowered_declarations(
    stages: Mapping[str, Any],
    edges: Mapping[str, Iterable[str]] | Iterable[tuple[str, str]],
):
    """Bind authored typed declarations after lowering and drift sanitization.

    Returns ``None`` when there is no clean typed authoring to bind. When
    drift is present, the affected stages are sanitized to their legacy-only
    declarations so the shared binder sees the same effective inputs that
    builder assembly uses for additive binding_map derivation.
    """

    if not stages:
        return None

    binding_stages: dict[str, Any] = {}
    saw_clean_typed_authoring = False
    for stage_name, stage in stages.items():
        lowered = lower_stage_declarations(stage)
        if lowered.clean_binding:
            if lowered.effective_produces or lowered.effective_consumes:
                saw_clean_typed_authoring = True
            binding_stages[stage_name] = stage
            continue
        binding_stages[stage_name] = replace(
            stage,
            reads=lowered.legacy_reads,
            writes=lowered.legacy_writes,
            produces=(),
            consumes=(),
        )

    if not saw_clean_typed_authoring:
        return None

    from arnold.pipeline.contracts import bind

    return bind(binding_stages, edges, typed_ports=True)


def _declaration_drift(
    *,
    stage_name: str,
    direction: str,
    explicit: tuple[Any, ...],
    lowered: tuple[Any, ...],
) -> tuple[DeclarationDrift, ...]:
    if not explicit or not lowered:
        return ()

    explicit_by_name = _ports_by_name(explicit)
    lowered_by_name = _ports_by_name(lowered)
    defects: list[DeclarationDrift] = []

    for name in sorted(set(explicit_by_name) | set(lowered_by_name)):
        explicit_signatures = explicit_by_name.get(name, set())
        lowered_signatures = lowered_by_name.get(name, set())
        if not explicit_signatures:
            defects.append(
                DeclarationDrift(
                    code="declaration_drift",
                    direction=direction,
                    name=name,
                    detail=(
                        f"stage {stage_name!r} lowers typed {direction} for {name!r} "
                        "without a matching explicit declaration"
                    ),
                )
            )
            continue
        if not lowered_signatures:
            defects.append(
                DeclarationDrift(
                    code="declaration_drift",
                    direction=direction,
                    name=name,
                    detail=(
                        f"stage {stage_name!r} declares explicit {direction} for {name!r} "
                        "without a matching typed read/write declaration"
                    ),
                )
            )
            continue
        if explicit_signatures != lowered_signatures:
            defects.append(
                DeclarationDrift(
                    code="declaration_drift",
                    direction=direction,
                    name=name,
                    detail=(
                        f"stage {stage_name!r} has conflicting explicit and typed "
                        f"{direction} declarations for {name!r}"
                    ),
                )
            )

    return tuple(defects)


def _ports_by_name(ports: tuple[Any, ...]) -> dict[str, set[tuple[Any, ...]]]:
    by_name: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
    for port in ports:
        by_name[_port_name(port)].add(_port_signature(port))
    return by_name


def _dedupe_ports(ports: tuple[Any, ...]) -> tuple[Any, ...]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[Any] = []
    for port in ports:
        signature = _port_signature(port)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(port)
    return tuple(deduped)


def _port_name(port: Any) -> str:
    return getattr(port, "name", getattr(port, "port_name", ""))


def _port_signature(port: Any) -> tuple[Any, ...]:
    return (
        _port_name(port),
        getattr(port, "content_type", None),
        _canonical_cardinality(getattr(port, "cardinality", "singleton")),
        getattr(port, "logical_type", None),
        _freeze_metadata(_metadata_payload(getattr(port, "accepted_version_range", None))),
    )


def _canonical_cardinality(cardinality: str | None) -> str:
    if cardinality is None:
        return "singleton"
    return _LEGACY_CARDINALITY_ALIASES.get(cardinality, cardinality)


def _metadata_payload(value: Any) -> Any:
    if value is None:
        return None
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return value


def _freeze_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze_metadata(inner)) for key, inner in value.items()))
    if isinstance(value, list):
        return tuple(_freeze_metadata(item) for item in value)
    return value
