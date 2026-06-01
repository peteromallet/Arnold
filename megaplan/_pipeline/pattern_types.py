"""Type aliases used as contracts by the pipeline pattern library.

:data:`PromoteFn` and :data:`JoinFn` are the two canonical callable
signatures consumed by :mod:`megaplan._pipeline.pattern_topology` and
:mod:`megaplan._pipeline.patterns`.  They are factored into their own
module so that topology modules can import them without pulling in the
entire pattern aggregation surface.
"""

from __future__ import annotations

from typing import Any, Callable

from megaplan._pipeline.types import StepContext, StepResult

PromoteFn = Callable[[dict[str, Any]], Any]
"""Map a child pipeline's terminal state dict to a planning recommendation."""

JoinFn = Callable[[list[StepResult], StepContext], StepResult]
"""Collate a list of :class:`StepResult` instances into a single result."""
