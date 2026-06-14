"""Semantic replay: structural equivalence comparison for pipeline outputs.

Provides two public symbols:

* :func:`semantic_equivalent` — deep structural comparison with dotted-path
  ignore/unordered support.
* :func:`semantic_replay_journal` — replay an event journal, reconstruct the
  folded state, and optionally compare it against an expected plan using
  :func:`semantic_equivalent`.

Both are pure-data, opinion-free contracts that live at the runtime level
so any pipeline (not just deliberation) can use them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from arnold.runtime.event_journal import read_event_journal
from arnold.runtime.wal_fold import fold_journal, last_state_snapshot_projector


# ── helpers ─────────────────────────────────────────────────────────────────


def _is_glob_or_wildcard(path: str) -> bool:
    """Return ``True`` if *path* contains glob/wildcard characters."""
    return bool(set(path) & {"*", "?", "[", "]"}) or ".." in path


# ── semantic_equivalent ─────────────────────────────────────────────────────


def semantic_equivalent(
    a: Any,
    b: Any,
    *,
    ignore_paths: Iterable[str] = (),
    unordered_paths: Iterable[str] = (),
    _path: str = "",
) -> tuple[bool, list[str]]:
    """Deep structural equality with path-based difference reporting.

    Compares *a* and *b* recursively, returning ``(True, [])`` when they
    are structurally equivalent and ``(False, [path, ...])`` when a
    difference is found.

    Parameters
    ----------
    a, b:
        Values to compare.
    ignore_paths:
        Dotted paths (e.g. ``changelog.2.verdict``) whose differences
        are silently accepted.  Glob/wildcard characters (``*``, ``?``,
        ``[``, ``]``) are **not** allowed — only literal dotted paths.
    unordered_paths:
        Dotted paths where list/tuple order is irrelevant.  When the
        recursion reaches a path listed here, the two sequences are
        compared as multi-sets (sorted before comparison).
    _path:
        Internal recursion accumulator.  Callers should not set this.

    Returns
    -------
    tuple[bool, list[str]]
        ``(True, [])`` when equivalent; ``(False, [path, ...])`` when
        a difference is found.

    Raises
    ------
    ValueError
        If any entry in *ignore_paths* or *unordered_paths* contains
        glob/wildcard characters.
    """
    # --- validate paths ---
    for p in ignore_paths:
        if _is_glob_or_wildcard(p):
            raise ValueError(
                f"ignore_paths must contain literal dotted paths only, "
                f"got glob/wildcard: {p!r}"
            )
    for p in unordered_paths:
        if _is_glob_or_wildcard(p):
            raise ValueError(
                f"unordered_paths must contain literal dotted paths only, "
                f"got glob/wildcard: {p!r}"
            )

    _ignore = frozenset(ignore_paths)
    _unordered = frozenset(unordered_paths)

    if _path in _ignore:
        return True, []

    # --- type mismatch ---
    if type(a) is not type(b):
        # bool is a subclass of int, but semantically distinct
        if isinstance(a, bool) or isinstance(b, bool):
            return False, [_path] if _path else ["<root>"]
        # Numeric cross-type: int vs float with same mathematical value
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if a == b:
                return True, []
        return False, [_path] if _path else ["<root>"]

    # --- dict ---
    if isinstance(a, dict):
        if not isinstance(b, dict):
            return False, [_path] if _path else ["<root>"]
        keys_a = set(a.keys())
        keys_b = set(b.keys())
        if keys_a != keys_b:
            return False, [_path] if _path else ["<root>"]
        for key in sorted(keys_a):
            child_path = f"{_path}.{key}" if _path else key
            eq, diffs = semantic_equivalent(
                a[key],
                b[key],
                ignore_paths=_ignore,
                unordered_paths=_unordered,
                _path=child_path,
            )
            if not eq:
                return False, diffs
        return True, []

    # --- list / tuple (with optional unordered comparison) ---
    if isinstance(a, (list, tuple)):
        if not isinstance(b, (list, tuple)):
            return False, [_path] if _path else ["<root>"]

        if _path in _unordered:
            # Unordered: compare as multi-sets (sort both)
            if len(a) != len(b):
                return False, [_path] if _path else ["<root>"]
            # Sort by JSON-serialized representation for stability
            a_sorted = sorted(a, key=lambda x: _sort_key(x))
            b_sorted = sorted(b, key=lambda x: _sort_key(x))
            for i in range(len(a_sorted)):
                child_path = f"{_path}.{i}" if _path else str(i)
                eq, diffs = semantic_equivalent(
                    a_sorted[i],
                    b_sorted[i],
                    ignore_paths=_ignore,
                    unordered_paths=_unordered,
                    _path=child_path,
                )
                if not eq:
                    return False, diffs
            return True, []
        else:
            # Ordered comparison
            if len(a) != len(b):
                return False, [_path] if _path else ["<root>"]
            for i in range(len(a)):
                child_path = f"{_path}.{i}" if _path else str(i)
                eq, diffs = semantic_equivalent(
                    a[i],
                    b[i],
                    ignore_paths=_ignore,
                    unordered_paths=_unordered,
                    _path=child_path,
                )
                if not eq:
                    return False, diffs
            return True, []

    # --- scalar ---
    if a != b:
        return False, [_path] if _path else ["<root>"]
    return True, []


def _sort_key(obj: Any) -> str:
    """Stable sort key for arbitrary objects (used for unordered comparison)."""
    import json

    try:
        return json.dumps(obj, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(obj)


# ── semantic_replay_journal ─────────────────────────────────────────────────


def semantic_replay_journal(
    artifact_root: str | Path,
    *,
    expected_plan: dict[str, Any] | None = None,
    ignore_paths: Iterable[str] = (),
    unordered_paths: Iterable[str] = (),
) -> tuple[dict[str, Any] | None, tuple[bool, list[str]]]:
    """Replay the event journal and optionally check semantic equivalence.

    Reads ``<artifact_root>/events.ndjson``, folds all ``state`` events
    via :func:`fold_journal` with :func:`last_state_snapshot_projector`,
    and returns the reconstructed plan.  If *expected_plan* is provided,
    the reconstructed plan is compared against it using
    :func:`semantic_equivalent`.

    Parameters
    ----------
    artifact_root:
        Path to the artifact root directory containing ``events.ndjson``.
    expected_plan:
        If provided, the reconstructed plan is compared against this
        dict using :func:`semantic_equivalent`.
    ignore_paths:
        Passed through to :func:`semantic_equivalent`.
    unordered_paths:
        Passed through to :func:`semantic_equivalent`.

    Returns
    -------
    tuple[dict | None, tuple[bool, list[str]]]
        ``(reconstructed_plan, (is_equivalent, diff_paths))``.
        *reconstructed_plan* is ``None`` when no ``state`` events exist.
        *is_equivalent* is ``True`` when *expected_plan* is ``None`` or
        the comparison succeeds.
    """
    root = Path(artifact_root)
    events = read_event_journal(root)
    if not events:
        return None, (True, [])

    result = fold_journal(
        events,
        kind_filter="state",
        projector=last_state_snapshot_projector,
        initial=None,
    )
    plan: dict[str, Any] | None = result if isinstance(result, dict) else None

    if expected_plan is not None and plan is not None:
        eq, diffs = semantic_equivalent(
            expected_plan,
            plan,
            ignore_paths=ignore_paths,
            unordered_paths=unordered_paths,
        )
        return plan, (eq, diffs)

    return plan, (True, [])


__all__ = [
    "semantic_equivalent",
    "semantic_replay_journal",
]
