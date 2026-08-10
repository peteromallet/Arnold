"""Selection primitives for tournament-style reduces.

Each rule factory returns a :class:`Callable` consumed by :func:`select`
that maps a list of ``(item, score)`` candidates (or any sequence of
items the caller supplies) to a :class:`SelectionResult`.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from arnold.pipeline.types import SelectionResult

SelectionRule = Callable[[Sequence[Any]], SelectionResult]


def _coerce(items: Sequence[Any]) -> tuple[tuple[int, float], ...]:
    """Normalize *items* to ``((index, score), ...)`` tuples.

    Each element may be either a bare numeric score or a ``(item, score)``
    pair.  Index is the position in *items*.
    """
    out: list[tuple[int, float]] = []
    for idx, raw in enumerate(items):
        if isinstance(raw, tuple) and len(raw) == 2:
            score = float(raw[1])
        else:
            score = float(raw)
        out.append((idx, score))
    return tuple(out)


def select(items: Sequence[Any], rule: SelectionRule) -> SelectionResult:
    """Apply *rule* to *items* and return its :class:`SelectionResult`."""
    return rule(items)


def top_1() -> SelectionRule:
    """Pick the single highest-scored candidate."""

    def _rule(items: Sequence[Any]) -> SelectionResult:
        pairs = _coerce(items)
        if not pairs:
            return SelectionResult(winner=-1, cleared=False)
        ranked = sorted(pairs, key=lambda p: p[1], reverse=True)
        scores = tuple(s for _, s in pairs)
        winner = ranked[0][0]
        losers = tuple(i for i, _ in ranked[1:])
        return SelectionResult(
            winner=winner,
            subset=(winner,),
            losers=losers,
            scores=scores,
            cleared=True,
        )

    return _rule


def top_k(k: int) -> SelectionRule:
    """Retain the *k* highest-scored candidates as ``subset``."""

    def _rule(items: Sequence[Any]) -> SelectionResult:
        pairs = _coerce(items)
        scores = tuple(s for _, s in pairs)
        if not pairs:
            return SelectionResult(winner=-1, cleared=False, scores=scores)
        ranked = sorted(pairs, key=lambda p: p[1], reverse=True)
        kept = ranked[: max(0, k)]
        subset = tuple(i for i, _ in kept)
        losers = tuple(i for i, _ in ranked[len(kept):])
        winner = subset[0] if subset else -1
        return SelectionResult(
            winner=winner,
            subset=subset,
            losers=losers,
            scores=scores,
            cleared=bool(subset),
        )

    return _rule


def threshold(min_score: float) -> SelectionRule:
    """Keep only candidates whose score ≥ *min_score*."""

    def _rule(items: Sequence[Any]) -> SelectionResult:
        pairs = _coerce(items)
        scores = tuple(s for _, s in pairs)
        kept = [(i, s) for i, s in pairs if s >= min_score]
        if not kept:
            return SelectionResult(
                winner=-1,
                subset=(),
                losers=tuple(i for i, _ in pairs),
                scores=scores,
                cleared=False,
            )
        kept.sort(key=lambda p: p[1], reverse=True)
        subset = tuple(i for i, _ in kept)
        losers = tuple(i for i, s in pairs if s < min_score)
        return SelectionResult(
            winner=subset[0],
            subset=subset,
            losers=losers,
            scores=scores,
            cleared=True,
        )

    return _rule
