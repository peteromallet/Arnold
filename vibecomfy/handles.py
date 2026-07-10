from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

_OutputT = TypeVar("_OutputT", covariant=True)

@dataclass(frozen=True)
class Handle(Generic[_OutputT]):
    node_id: str
    output_slot: int | str = 0
    output_type: str | None = None
    name: str | None = None

    def __str__(self) -> str:
        return f"{self.node_id}.{self.output_slot}"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Handle):
            return self.node_id == other.node_id and str(self.output_slot) == str(other.output_slot)
        if isinstance(other, str):
            if other == str(self):
                return True
            return str(self.output_slot) == "0" and other == self.node_id
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.node_id, str(self.output_slot)))


__all__ = ["Handle"]
