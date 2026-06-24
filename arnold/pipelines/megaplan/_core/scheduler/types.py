"""Scheduler type definitions.

This module defines the generic ``Reduce[T]`` frozen dataclass used by the
task-DAG scheduler.  No planning vocabulary belongs here — ``BatchOutcome``
and ``BatchReduceResult`` are defined in the planning binding (T7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

# TODO: import from arnold.pipelines.megaplan._pipeline.types once a generic Reduce[T] lands there


@dataclass(frozen=True)
class Reduce(Generic[T]):
    """Generic reduction result carrying a single value of type *T*.

    Frozen to ensure reducer outputs are immutable once constructed.
    """

    value: T
