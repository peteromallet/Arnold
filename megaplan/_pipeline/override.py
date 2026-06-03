"""Override edges — Sprint 4 Chunk D.

The executor consults a stage's ``override_edges`` whenever a Step
returns a :class:`StepResult` whose ``verdict.override`` field is
set. This makes the legacy CLI escape hatches
(``override force-proceed`` / ``override abort`` / ``override replan``
/ ``override add-note``) first-class edges instead of side-effecting
subcommands.

Because :class:`Stage` is ``@dataclass(frozen=True)``, the override
edges live on a new ``Stage.override_edges`` field that defaults to
``()``. Existing stage constructions are unaffected.
"""

from __future__ import annotations

from megaplan._pipeline.types import Edge


def override_edge(action: str, target: str) -> Edge:
    """Build an :class:`Edge` that matches a specific override action.

    M3b: *action* is a plain ``str`` (was a typed override action literal).
    """

    return Edge(
        label=f"override {action}",
        target=target,
        kind="override",
        recommendation=None,
    )


def find_override_edge(
    edges: "tuple[Edge, ...]",
    action: str | None,
) -> Edge | None:
    """Find the override edge matching the action, or None.

    The match is on ``edge.kind == "override"`` AND
    ``edge.label == f"override {action}"`` to keep the label
    human-readable.

    M3b: *action* is a plain ``str | None`` (was a typed override action literal).
    """

    if action is None:
        return None
    target_label = f"override {action}"
    return next(
        (e for e in edges if e.kind == "override" and e.label == target_label),
        None,
    )
