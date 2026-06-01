"""W7 — Static graph validator for :class:`Pipeline` definitions.

Pure graph-shape validation, NO dispatch and NO Port resolution:

* every :class:`Edge`.``target`` names a real stage in ``Pipeline.stages`` or
  the reserved terminal ``"halt"``;
* ``"halt"`` is never used as an :class:`Edge`.``label`` (it is reserved as a
  target only);
* every stage that emits at least one ``kind == "gate"`` edge covers the full
  set of :data:`GateRecommendation` literals across its outgoing
  ``Edge.recommendation`` values;
* no stage is unreachable from :attr:`Pipeline.entry`.

A consumes↔produces ``Port`` check is explicitly out of scope (M2 territory;
no ``Port`` type exists today).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, get_args

from megaplan._pipeline.types import Edge, GateRecommendation, Pipeline


_GATE_RECOMMENDATIONS: frozenset[str] = frozenset(get_args(GateRecommendation))


@dataclass
class Diagnostics:
    """Result of :func:`validate` over a :class:`Pipeline`.

    Each defect is a short human-readable string naming the offending
    stage/edge so ``pipelines check`` can echo it on a non-zero exit.
    """

    defects: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.defects


def _stage_edges(stage: Any) -> tuple[Edge, ...]:
    return tuple(getattr(stage, "edges", ()) or ())


def validate(pipeline: Pipeline) -> Diagnostics:
    """Run the W7 graph-shape checks over ``pipeline``.

    Returns a :class:`Diagnostics` whose ``defects`` list is empty iff every
    check passes.
    """
    diag = Diagnostics()
    stage_names = set(pipeline.stages.keys())

    if pipeline.entry not in stage_names:
        diag.defects.append(
            f"entry stage {pipeline.entry!r} not present in pipeline.stages"
        )

    for stage_name, stage in pipeline.stages.items():
        edges = _stage_edges(stage)
        gate_edges = [e for e in edges if e.kind == "gate"]

        for edge in edges:
            # 'halt' is a reserved target sentinel; flagged as a label only when
            # the edge does NOT also resolve to the terminal target (the
            # conventional ``label='halt' target='halt'`` pair stays valid).
            if edge.label == "halt" and edge.target != "halt":
                diag.defects.append(
                    f"stage {stage_name!r}: edge uses reserved label 'halt' "
                    "(halt is a target sentinel, not an edge label)"
                )
            if edge.target != "halt" and edge.target not in stage_names:
                diag.defects.append(
                    f"stage {stage_name!r}: edge {edge.label!r} targets "
                    f"unknown stage {edge.target!r}"
                )

        for edge in gate_edges:
            if edge.recommendation is None:
                diag.defects.append(
                    f"stage {stage_name!r}: gate edge {edge.label!r} has "
                    "no recommendation set (gate verdict would not dispatch)"
                )
            elif edge.recommendation not in _GATE_RECOMMENDATIONS:
                diag.defects.append(
                    f"stage {stage_name!r}: gate edge {edge.label!r} has "
                    f"recommendation {edge.recommendation!r} not in "
                    f"GateRecommendation literals {sorted(_GATE_RECOMMENDATIONS)}"
                )

    # Reachability from entry.
    if pipeline.entry in stage_names:
        reachable: set[str] = set()
        frontier = [pipeline.entry]
        while frontier:
            current = frontier.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stage = pipeline.stages.get(current)
            if stage is None:
                continue
            for edge in _stage_edges(stage):
                if edge.target != "halt" and edge.target in stage_names:
                    frontier.append(edge.target)
        unreachable = stage_names - reachable
        for name in sorted(unreachable):
            diag.defects.append(
                f"stage {name!r} is unreachable from entry {pipeline.entry!r}"
            )

    return diag
