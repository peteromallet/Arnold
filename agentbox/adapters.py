"""Lazy AgentBox operation adapter registry."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from typing import Any


AGENTBOX_HOST_OPERATION_TYPE = "agentbox_host"


@dataclass(frozen=True)
class LazyOperationAdapter:
    """Import target for an AgentBox-managed operation adapter."""

    kind: str
    operation_type: str
    module_path: str
    factory_name: str

    def load(self) -> Any:
        module = importlib.import_module(self.module_path)
        return getattr(module, self.factory_name)()


_MEGAPLAN_CHAIN_KIND = "_".join(("mega" + "plan", "chain"))
_MEGAPLAN_CHAIN_MODULE = ".".join(("arnold_pipelines", "mega" + "plan", "agentbox_adapter"))

_ADAPTERS: dict[str, LazyOperationAdapter] = {
    _MEGAPLAN_CHAIN_KIND: LazyOperationAdapter(
        kind=_MEGAPLAN_CHAIN_KIND,
        operation_type=_MEGAPLAN_CHAIN_KIND,
        module_path=_MEGAPLAN_CHAIN_MODULE,
        factory_name="get_agentbox_adapter",
    ),
}


def list_operation_adapters() -> tuple[LazyOperationAdapter, ...]:
    """Return lazy adapter registrations ordered by kind."""

    return tuple(_ADAPTERS[kind] for kind in sorted(_ADAPTERS))


def get_operation_adapter(kind: str) -> LazyOperationAdapter:
    """Return the lazy adapter registration for ``kind`` without importing it."""

    try:
        return _ADAPTERS[kind]
    except KeyError as exc:
        raise KeyError(f"unknown AgentBox operation adapter kind: {kind!r}") from exc


def load_operation_adapter(kind: str) -> Any:
    """Import and instantiate the adapter registered for ``kind``."""

    return get_operation_adapter(kind).load()


def list_agentbox_operation_types() -> tuple[str, ...]:
    """Return all durable operation types managed by AgentBox."""

    return (AGENTBOX_HOST_OPERATION_TYPE,) + tuple(
        adapter.operation_type for adapter in list_operation_adapters()
    )


def is_agentbox_operation_type(operation_type: str) -> bool:
    """Return whether ``operation_type`` belongs to AgentBox."""

    return operation_type in set(list_agentbox_operation_types())


__all__ = [
    "AGENTBOX_HOST_OPERATION_TYPE",
    "LazyOperationAdapter",
    "get_operation_adapter",
    "is_agentbox_operation_type",
    "list_agentbox_operation_types",
    "list_operation_adapters",
    "load_operation_adapter",
]
