"""W7 — Static graph validator for :class:`Pipeline` definitions.

Pure graph-shape validation, NO dispatch and NO Port resolution:

* every :class:`Edge`.``target`` names a real stage in ``Pipeline.stages`` or
  the reserved terminal ``"halt"``;
* ``"halt"`` is never used as an :class:`Edge`.``label`` (it is reserved as a
  target only);
* every stage that emits at least one ``kind == "decision"`` edge must cover
  the declared ``decision_vocabulary`` when non-empty;
* every stage that emits at least one ``kind == "override"`` edge must cover
  the declared ``override_vocabulary`` when non-empty;
* no stage is unreachable from :attr:`Pipeline.entry`.

M3b: validation is driven by the stage's ``decision_vocabulary`` and
``override_vocabulary`` frozensets instead of the removed
typed gate recommendation alias.

A consumes↔produces ``Port`` check is explicitly out of scope (M2 territory;
no ``Port`` type exists today).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from megaplan._pipeline.types import Edge, Pipeline


# M3b: the four canonical planning recommendations are preserved as a
# default validation set for backward compatibility.  When a stage
# declares decision_vocabulary, that set is used instead.
_FALLBACK_DECISION_VOCABULARY: frozenset[str] = frozenset(
    {"proceed", "iterate", "tiebreaker", "escalate"}
)


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


def _stage_decision_vocabulary(stage: Any) -> frozenset[str] | None:
    """Return the stage's declared decision vocabulary, or the fallback.

    M3b: when the stage has a non-empty ``decision_vocabulary``, use it.
    Otherwise, use the fallback planning vocabulary for backward compat.
    Returns None when the stage has no vocabulary and the fallback is
    not appropriate (i.e. the stage has no decision edges — nothing to
    validate).
    """
    declared: frozenset[str] = frozenset(
        getattr(stage, "decision_vocabulary", frozenset()) or frozenset()
    )
    if declared:
        return declared
    return _FALLBACK_DECISION_VOCABULARY


def _stage_override_vocabulary(stage: Any) -> frozenset[str] | None:
    """Return the stage's declared override vocabulary, or None."""
    declared: frozenset[str] = frozenset(
        getattr(stage, "override_vocabulary", frozenset()) or frozenset()
    )
    if declared:
        return declared
    return None


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
        # M3b: match both kind='gate' (legacy) and kind='decision' (current)
        decision_edges = [e for e in edges if e.kind in ("gate", "decision")]
        override_edges_list = [e for e in edges if e.kind == "override"]

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

        # M3b: validate decision edges against declared vocabulary.
        if decision_edges:
            vocab = _stage_decision_vocabulary(stage)
            if vocab is not None:
                covered: set[str] = set()
                for edge in decision_edges:
                    # label is the decision key for kind='decision';
                    # recommendation is checked for legacy kind='gate' edges.
                    key = edge.label if edge.kind == "decision" else edge.recommendation
                    if not key:
                        diag.defects.append(
                            f"stage {stage_name!r}: decision edge {edge.label!r} has "
                            "no decision key set (label/recommendation is None)"
                        )
                    elif key not in vocab:
                        diag.defects.append(
                            f"stage {stage_name!r}: decision edge {edge.label!r} has "
                            f"decision key {key!r} not in "
                            f"declared vocabulary {sorted(vocab)}"
                        )
                    else:
                        covered.add(key)
                missing = vocab - covered
                if missing:
                    diag.defects.append(
                        f"stage {stage_name!r}: decision vocabulary "
                        f"{sorted(vocab)} declares {sorted(missing)} "
                        f"but no decision edge covers them"
                    )

        # M3b: validate override edges against declared vocabulary.
        if override_edges_list:
            vocab = _stage_override_vocabulary(stage)
            if vocab is not None:
                covered: set[str] = set()
                for edge in override_edges_list:
                    # label format is "override <action>"
                    if not edge.label.startswith("override "):
                        diag.defects.append(
                            f"stage {stage_name!r}: override edge {edge.label!r} "
                            "does not follow 'override <action>' label format"
                        )
                        continue
                    action = edge.label[len("override "):]
                    if action not in vocab:
                        diag.defects.append(
                            f"stage {stage_name!r}: override edge {edge.label!r} has "
                            f"action {action!r} not in "
                            f"declared override_vocabulary {sorted(vocab)}"
                        )
                    else:
                        covered.add(action)
                missing = vocab - covered
                if missing:
                    diag.defects.append(
                        f"stage {stage_name!r}: override vocabulary "
                        f"{sorted(vocab)} declares {sorted(missing)} "
                        f"but no override edge covers them"
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
