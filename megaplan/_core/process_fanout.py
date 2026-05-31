"""Process fan-out alias module.

Re-exports the process-isolated fan-out primitives from ``_core.hermes_fanout``
under a name that makes the generic (non-review) surface explicit.

This is *process fan-out* — each unit runs in a separate process.  For worker
fan-out that drives CLI backends (Claude/Shannon, Codex, Hermes) through
``run_step_with_worker``, see :mod:`megaplan._core.worker_fanout`.

This module deliberately excludes critique/review-specific names such as
``ScatterResult`` and ``scatter_gather_checks`` so that callers focused on
generic process fan-out do not accidentally depend on review-oriented
artifacts.
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
