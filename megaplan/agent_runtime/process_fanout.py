"""Process fan-out alias module for the vendorable agent runtime surface.

Re-exports the generic (non-review) process fan-out primitives from
``megaplan._core.hermes_fanout`` so consumer packages can depend on the stable
``megaplan.agent_runtime`` namespace.

This is *process fan-out* — each unit runs in a separate process via
``scatter_gather_processes``.  For thread-based injected-dispatcher fan-out, see
:func:`megaplan.agent_runtime.scatter_agent_units`.  For worker fan-out that
drives CLI backends (Claude/Shannon, Codex, Hermes) through
``run_step_with_worker``, see :mod:`megaplan._core.worker_fanout`.

This module deliberately excludes critique/review-specific names such as
``ScatterResult`` and ``scatter_gather_checks``. Callers that need the
review-oriented variants should continue to import directly from
``megaplan._core.hermes_fanout``.
"""

from megaplan._core.hermes_fanout import (
    GenericScatterResult,
    scatter_gather,
    scatter_gather_processes,
    with_429_openrouter_fallback,
)

__all__ = [
    "GenericScatterResult",
    "scatter_gather",
    "scatter_gather_processes",
    "with_429_openrouter_fallback",
]
