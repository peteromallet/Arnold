"""Scheduler type definitions.

This module defines the generic ``Reduce[T]`` frozen dataclass used by the
task-DAG scheduler.  No planning vocabulary belongs here — ``BatchOutcome``
and ``BatchReduceResult`` are defined in the planning binding (T7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

# Reduce is a self-contained generic frozen dataclass defined here; it does not
# depend on _pipeline.types.  If a shared Reduce[T] ever lands in an Arnold or
# Megaplan-owned module, this definition should migrate there.


@dataclass(frozen=True)
class Reduce(Generic[T]):
    """Generic reduction result carrying a single value of type *T*.

    Frozen to ensure reducer outputs are immutable once constructed.
    """

    value: T
