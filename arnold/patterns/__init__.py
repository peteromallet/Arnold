"""Pure workflow pattern constructors for the M2 explicit-node DSL.

Stability:
    public: base constructors ``agent``, ``external_call``, ``merge``,
        ``subpipeline``
    public: control constructors ``branch``, ``loop``, ``fanout``, ``panel``,
        ``retry``, ``human_gate``
    public: review constructors ``critique``, ``review``, ``revise``,
        ``tournament``
    provisional: ``panel``, ``retry``, and all review constructors are
        provisional until the canonical fixture matrix validates their lowering.
    internal: ``PatternBlock`` and module-level helper symbols.

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
INTERNAL_EXPORTS = ()

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
from arnold.patterns._core import PatternBlock as PatternBlock
