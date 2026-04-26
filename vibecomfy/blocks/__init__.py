from __future__ import annotations

from dataclasses import dataclass, field
from inspect import signature
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, TypeVar

from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True, init=False)
class Handles:
    values: Mapping[str, Any] = field(default_factory=dict)

    def __init__(self, values: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        merged: dict[str, Any] = {}
        if values is not None:
            merged.update(values)
        merged.update(kwargs)
        object.__setattr__(self, "values", MappingProxyType(merged))

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __getattr__(self, key: str) -> Any:
        try:
            return self.values[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.values)


class Block(Protocol):
    def __call__(self, workflow: VibeWorkflow, **kwargs: Any) -> Handles:
        """Mutate the workflow as needed (any VibeWorkflow method) and return handles for downstream wiring."""


@dataclass(frozen=True)
class BlockSpec:
    name: str
    module: str
    qualname: str
    signature: str


BlockFn = TypeVar("BlockFn", bound=Callable[..., Handles])

_BLOCK_REGISTRY: dict[str, Block] = {}


def block(fn: BlockFn) -> BlockFn:
    sig = signature(fn)
    first_param = next(iter(sig.parameters.values()), None)
    if first_param is None or first_param.name != "workflow":
        raise TypeError(f"{fn.__module__}.{fn.__qualname__} must accept workflow as its first parameter")
    name = f"{fn.__module__}.{fn.__name__}"
    spec = BlockSpec(
        name=name,
        module=fn.__module__,
        qualname=fn.__qualname__,
        signature=str(sig),
    )
    setattr(fn, "__vibecomfy_block__", spec)
    _BLOCK_REGISTRY[name] = fn
    return fn


def block_spec(fn: Callable[..., Any]) -> BlockSpec | None:
    spec = getattr(fn, "__vibecomfy_block__", None)
    return spec if isinstance(spec, BlockSpec) else None


def registered_blocks() -> Mapping[str, Block]:
    return MappingProxyType(dict(_BLOCK_REGISTRY))


__all__ = ["Block", "BlockSpec", "Handles", "block", "block_spec", "registered_blocks"]
