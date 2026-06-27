"""Pure workflow pattern constructors for the M2 explicit-node DSL.

Stability markers (mirrored in ``docs/arnold/pattern-stability-matrix.md``):

- stable / public: ``agent``, ``external_call``, ``merge``, ``subpipeline``,
  ``branch``, ``fanout``, ``loop``, ``human_gate``
- provisional: ``panel``, ``retry``, ``critique``, ``review``, ``revise``,
  ``tournament``
- internal: ``PatternBlock`` and module-level helper symbols

The marker tuples ``PUBLIC_EXPORTS``, ``PROVISIONAL_EXPORTS``, and
``INTERNAL_EXPORTS`` are part of the import-boundary contract and may be used
by scanners and conformance tests.

Pattern constructors return pure DSL values.  They do not import
``arnold.execution`` or product Megaplan modules, and they never capture
closures, callable instances, live objects, or mutable state.
"""

from __future__ import annotations

from arnold.patterns.base import agent, external_call, merge, subpipeline
from arnold.patterns.control import (
    branch,
    fanout,
    human_gate,
    loop,
    panel,
    retry,
)
from arnold.patterns.review import critique, review, revise, tournament

PUBLIC_EXPORTS = (
    "agent",
    "external_call",
    "merge",
    "subpipeline",
    "branch",
    "loop",
    "fanout",
    "panel",
    "retry",
    "human_gate",
    "critique",
    "review",
    "revise",
    "tournament",
)
PROVISIONAL_EXPORTS = (
    "panel",
    "retry",
    "critique",
    "review",
    "revise",
    "tournament",
)
INTERNAL_EXPORTS = ("PatternBlock",)

__all__ = [
    "INTERNAL_EXPORTS",
    "PROVISIONAL_EXPORTS",
    "PUBLIC_EXPORTS",
    "PatternBlock",
    "agent",
    "branch",
    "critique",
    "external_call",
    "fanout",
    "human_gate",
    "loop",
    "merge",
    "panel",
    "retry",
    "review",
    "revise",
    "subpipeline",
    "tournament",
]

# Delayed import of PatternBlock to keep the public namespace clean while still
# exposing the composite carrier for advanced callers.
from arnold.patterns._core import PatternBlock as PatternBlock  # noqa: E402
