"""Neutral step-invocation seam primitives for adapter-backed execution.

This module defines the minimal Arnold-side invocation shape plus the
fail-closed adapter registry that later milestones can extend with concrete
adapter implementations.

Public adapter surface
----------------------

:class:`StepInvocationAdapter`
    Structural protocol for objects that handle a step invocation.
    Any callable / object that satisfies this protocol can be registered
    as a step-invocation adapter.  The protocol requires a single method::

        def invoke(self, invocation: StepInvocation) -> Any: ...

    ``invoke`` receives the full :class:`StepInvocation` (``kind`` +
    ``metadata``) and returns the result of the step.  Consumers register
    adapters into a :class:`StepInvocationAdapterRegistry`.

Adapter return contract (AR3+)
------------------------------

Adapters may return either a plain value (backward compatible) or a
:class:`StepInvocationResult` envelope::

    # Plain return — no media usage reported.
    return "some payload"

    # Envelope return — payload + optional media usage.
    return StepInvocationResult(
        payload="some payload",
        media_usage=(MediaUsage(unit="image", count=1),),
    )

Callers that consume adapter results should use
:func:`unwrap_step_invocation_result` to safely extract ``(payload,
media_usage)`` regardless of which shape the adapter returned.  Plain
returns are unwrapped to ``(payload, ())`` — no media usage.

The protocol signature ``def invoke(self, invocation: StepInvocation) -> Any``
is unchanged; :class:`StepInvocationResult` is an opt-in envelope that
adapters *may* produce.

:class:`StepInvocationAdapterRegistry`
    Fail-closed registry for step-invocation adapters.  Construct a fresh
    registry with ``StepInvocationAdapterRegistry()`` — it starts with only
    the reserved ``"model"`` slot wired to a placeholder implementation.
    Unknown kinds fail closed during resolution.

    ``register(kind, adapter)``
        Register *adapter* under *kind*.  Raises ``ValueError`` if *kind*
        is already registered (no silent overwrite).  Use this for non-model
        adapters (e.g. ``"tool"``, ``"collector"``).

    ``resolve(kind)``
        Return the registered adapter for *kind* or raise ``KeyError``
        (fail-closed).  This is the mechanism used by the validator and
        the static-check passes to confirm every invocation kind is known.

    ``registered_kinds``
        Property returning a ``tuple[str, ...]`` of all registered kind
        names in deterministic (sorted) order.  Useful for introspection
        and diagnostic messages.

    ``invoke(invocation)``
        Convenience method that resolves *invocation.kind* and delegates
        to the adapter's ``invoke``.  Equivalent to
        ``registry.resolve(invocation.kind).invoke(invocation)``.

    ``replace_reserved(kind, adapter)``
        Replace a reserved placeholder adapter (the ``"model"`` slot)
        with a concrete implementation.  Raises ``ValueError`` if the
        slot is not currently held by a placeholder.

The default (process-wide) singleton is available via
:func:`get_default_adapter_registry` and is used by the C4 static-check
pass when no explicit registry is provided.  Callers that want non-model
adapters to pass validation supply their own local
:class:`StepInvocationAdapterRegistry` to :func:`validate
<arnold.pipeline.validator.validate>` via the *adapter_registry*
keyword-only argument.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from arnold.pipeline.media_cost import MediaUsage


class ModelAdapterNotImplementedError(NotImplementedError):
    """Raised when the reserved model adapter slot is invoked before M3."""


@dataclass(frozen=True)
class StepInvocation:
    """Neutral invocation descriptor passed to an adapter.

    ``kind`` selects the adapter slot. ``metadata`` carries JSON-compatible
    invocation detail without imposing Megaplan-specific structure here.
    """

    kind: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def model(
        cls,
        *,
        adapter_config: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "StepInvocation":
        """Construct a ``model`` invocation with canonical adapter metadata."""
        return cls.with_adapter_config(
            kind="model",
            adapter_config=adapter_config,
            metadata=metadata,
        )

    @classmethod
    def with_adapter_config(
        cls,
        *,
        kind: str,
        adapter_config: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "StepInvocation":
        """Construct an invocation whose adapter config lives under ``metadata``."""
        canonical_metadata = _metadata_with_adapter_config(
            metadata=metadata,
            adapter_config=adapter_config,
        )
        return cls(kind=kind, metadata=canonical_metadata)


def _metadata_with_adapter_config(
    *,
    metadata: Mapping[str, Any] | None,
    adapter_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    canonical_metadata = dict(metadata or {})
    if adapter_config is None:
        return canonical_metadata
    canonical_adapter_config = dict(adapter_config)
    existing_adapter_config = canonical_metadata.get("adapter_config")
    if existing_adapter_config is not None and existing_adapter_config != canonical_adapter_config:
        raise ValueError("conflicting adapter_config supplied via metadata and factory")
    canonical_metadata["adapter_config"] = canonical_adapter_config
    return canonical_metadata


@runtime_checkable
class StepInvocationAdapter(Protocol):
    """Structural protocol for objects that can handle a step invocation.

    .. note::

        For AR3+, adapters may return either a plain value or a
        :class:`StepInvocationResult` envelope.  See the module-level
        adapter return contract documentation for details.
    """

    def invoke(self, invocation: StepInvocation) -> Any: ...


@dataclass(frozen=True)
class StepInvocationResult:
    """Optional envelope that an adapter may return.

    Plain (non-envelope) returns remain valid and are unwrapped as
    ``(payload, ())`` by :func:`unwrap_step_invocation_result`.

    Attributes
    ----------
    payload:
        The step's output payload — identical to what a plain return
        would have produced.
    media_usage:
        Zero or more :class:`~arnold.pipeline.media_cost.MediaUsage`
        records for media generated or consumed by this invocation.
        Defaults to an empty tuple (no media usage reported).
    """

    payload: Any
    media_usage: tuple[MediaUsage, ...] = ()


def unwrap_step_invocation_result(
    result: Any,
) -> tuple[Any, tuple[MediaUsage, ...]]:
    """Safely extract ``(payload, media_usage)`` from an adapter result.

    Parameters
    ----------
    result:
        The return value of ``StepInvocationAdapter.invoke()``.

    Returns
    -------
    tuple[Any, tuple[MediaUsage, ...]]
        * If *result* is a :class:`StepInvocationResult`: returns
          ``(result.payload, result.media_usage)``.
        * Otherwise: returns ``(result, ())`` — no media usage,
          preserving full backward compatibility with plain returns.
    """
    if isinstance(result, StepInvocationResult):
        return result.payload, result.media_usage
    return result, ()


class _ModelAdapterPlaceholder:
    """Reserved ``model`` adapter slot. Concrete behavior lands in M3."""

    def invoke(self, invocation: StepInvocation) -> Any:
        raise ModelAdapterNotImplementedError(
            "StepInvocation adapter kind 'model' is reserved for M3 and is not "
            "implemented in M2"
        )


class StepInvocationAdapterRegistry:
    """Small fail-closed registry for step-invocation adapters.

    The registry starts with only the reserved ``model`` slot wired to a
    placeholder implementation. Unknown kinds fail closed during resolution.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, StepInvocationAdapter] = {
            "model": _ModelAdapterPlaceholder(),
        }

    def register(self, kind: str, adapter: StepInvocationAdapter) -> None:
        """Register *adapter* under *kind* or reject duplicate registrations."""
        if kind in self._adapters:
            raise ValueError(f"adapter kind {kind!r} already registered")
        self._adapters[kind] = adapter

    def replace_reserved(self, kind: str, adapter: StepInvocationAdapter) -> None:
        """Replace a reserved placeholder adapter with a concrete implementation."""
        current = self.resolve(kind)
        if not isinstance(current, _ModelAdapterPlaceholder):
            raise ValueError(
                f"adapter kind {kind!r} is not a reserved placeholder and cannot be replaced"
            )
        self._adapters[kind] = adapter

    def resolve(self, kind: str) -> StepInvocationAdapter:
        """Return the registered adapter for *kind* or fail closed."""
        if kind not in self._adapters:
            raise KeyError(
                f"unknown adapter kind {kind!r}; registered kinds: {sorted(self._adapters)}"
            )
        return self._adapters[kind]

    def invoke(self, invocation: StepInvocation) -> Any:
        """Resolve *invocation.kind* and delegate to the registered adapter."""
        return self.resolve(invocation.kind).invoke(invocation)

    @property
    def registered_kinds(self) -> tuple[str, ...]:
        """Return the registry contents in deterministic order."""
        return tuple(sorted(self._adapters))


_default_registry: StepInvocationAdapterRegistry | None = None
_default_registry_lock = threading.Lock()


def get_default_adapter_registry() -> StepInvocationAdapterRegistry:
    """Return the process-wide default StepInvocationAdapterRegistry singleton."""
    global _default_registry
    if _default_registry is None:
        with _default_registry_lock:
            if _default_registry is None:
                _default_registry = StepInvocationAdapterRegistry()
    return _default_registry
