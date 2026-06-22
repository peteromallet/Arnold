"""Join-callable primitives for pipeline pattern composition.

M3a compatibility bridge; delete in M7.

This module wraps the neutral Arnold ``majority_vote`` and
``weighted_vote`` functions from :mod:`arnold.pipeline.pattern_joins`,
injecting the Megaplan-specific ``typed_ports_on()`` check and the
legacy ``'tiebreaker'`` default-on-tie label.
"""

from __future__ import annotations

from typing import Callable, Mapping

from arnold.pipeline.contract_reduce import ReducePolicy
from arnold.pipeline.pattern_joins import majority_vote as _arnold_majority_vote
from arnold.pipeline.pattern_joins import weighted_vote as _arnold_weighted_vote
from arnold_pipelines.megaplan._pipeline.flags import typed_ports_on
from arnold.pipeline.pattern_types import JoinFn


__all__ = ["majority_vote", "weighted_vote"]


def majority_vote(
    panel_output_key: str = "verdict",
    *,
    label_extractor: Callable | None = None,
    default_on_tie: str | None = "tiebreaker",
    reduce_policy: ReducePolicy = ReducePolicy.MAX_WINS,
    suspension_scope: str | None = None,
) -> JoinFn:
    """Return a join callable that picks the majority recommendation.

    Megaplan bridge: delegates to :func:`arnold.pipeline.pattern_joins.majority_vote`
    with ``typed_reduce=typed_ports_on()`` and the legacy ``default_on_tie='tiebreaker'``.

    M3a compatibility bridge; delete in M7.
    """
    return _arnold_majority_vote(
        panel_output_key=panel_output_key,
        label_extractor=label_extractor,
        default_on_tie=default_on_tie,
        typed_reduce=typed_ports_on(),
        reduce_policy=reduce_policy,
        suspension_scope=suspension_scope,
    )


def weighted_vote(
    weights: Mapping[str, float],
    *,
    label_extractor: Callable | None = None,
    default_on_tie: str | None = "tiebreaker",
    reduce_policy: ReducePolicy = ReducePolicy.MAX_WINS,
    suspension_scope: str | None = None,
) -> JoinFn:
    """Return a join callable that picks the highest-weighted recommendation.

    Megaplan bridge: delegates to :func:`arnold.pipeline.pattern_joins.weighted_vote`
    with ``typed_reduce=typed_ports_on()`` and the legacy ``default_on_tie='tiebreaker'``.

    M3a compatibility bridge; delete in M7.
    """
    return _arnold_weighted_vote(
        weights=weights,
        label_extractor=label_extractor,
        default_on_tie=default_on_tie,
        typed_reduce=typed_ports_on(),
        reduce_policy=reduce_policy,
        suspension_scope=suspension_scope,
    )
