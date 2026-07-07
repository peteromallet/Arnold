"""Pure canonical run-state resolver.

``resolve_run_state(evidence, blocker_verdict=None)`` classifies current-target
evidence into a single :class:`CanonicalRunState` by applying the ordered
North Star classifiers from :mod:`arnold_pipelines.megaplan.run_state.classifiers`.

This function is read-only and pure: it never mutates state, performs no
filesystem or network I/O, and reads no environment variables.  Consumer
gating (``resolver_observe_enabled`` / ``resolver_enforcement_enabled`` in
:mod:`arnold_pipelines.megaplan.cloud.feature_flags`) belongs to the
consumers (watchdog, repair-loop, status/Discord), not to this resolver.

Classification order (first non-None match wins):

1. :func:`~.classifiers.classify_completed`               (authority beats stale)
2. :func:`~.classifiers.classify_broken_state_machine`     (genuine escalation)
3. :func:`~.classifiers.classify_stale_derived_state`     (live beats stale)
4. :func:`~.classifiers.classify_running`                 (live beats stale)
5. :func:`~.classifiers.classify_human_action_required`   (explicit typed gate)
6. :func:`~.classifiers.classify_real_implementation_block`
7. :func:`~.classifiers.classify_retryable_execution_block`
8. :func:`~.classifiers.classify_repairing`
9. :func:`~.classifiers.classify_unknown`                 (conservative fallback)
"""

from __future__ import annotations

from typing import Any, Mapping

from arnold_pipelines.megaplan.run_state.classifiers import (
    ORDERED_CLASSIFIERS,
    ResolverContext,
    _coerce_verdict,
    classify_unknown,
)
from arnold_pipelines.megaplan.run_state.model import CanonicalRunState

__all__ = ["resolve_run_state", "ResolverContext"]


def resolve_run_state(
    evidence: Mapping[str, Any] | None = None,
    blocker_verdict: object = None,
) -> CanonicalRunState:
    """Classify current-target evidence into a canonical run state.

    Args:
        evidence: Raw evidence dict from
            :func:`~arnold_pipelines.megaplan.cloud.current_target.resolve_current_target`.
            ``None`` or a non-mapping is treated as empty evidence and resolves
            conservatively to :attr:`CanonicalState.UNKNOWN`.
        blocker_verdict: Optional
            :class:`~arnold_pipelines.megaplan.cloud.human_blockers.BlockerVerdict`
            (enum member or ``.name`` string) consumed as *advisory* context.
            The resolver's own evidence priority always overrides a stale or
            contradictory verdict (e.g. a ``TRUE_BLOCKER`` verdict alongside
            AWF018 diagnostic codes is classified as a real implementation
            block, not a human gate).

    Returns:
        A frozen :class:`CanonicalRunState`.  Callers that want JSON should use
        ``result.to_dict()`` / ``result.to_json()``.
    """
    if not isinstance(evidence, Mapping):
        evidence = {}
    verdict = _coerce_verdict(blocker_verdict)
    ctx = ResolverContext.build(evidence, verdict)
    for classify in ORDERED_CLASSIFIERS:
        result = classify(ctx)
        if result is not None:
            return result
    return classify_unknown(ctx)
