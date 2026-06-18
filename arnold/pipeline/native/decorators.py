"""Native runtime decorators for ``@phase``, ``@pipeline``, and ``@decision``.

These are lightweight markers that register phase functions, pipeline
generators, and decision callables with the native runtime.  They compose
with the native runner's dict-based context and state propagation.
"""

from __future__ import annotations

from typing import Any, Callable


# ── Decorators ──────────────────────────────────────────────────────────


def phase(
    name: str | None = None,
    *,
    description: str | None = None,
    produces: tuple = (),
    consumes: tuple = (),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a function as a native pipeline phase.

    Supports both ``@phase`` and ``@phase(...)`` usage.

    Parameters
    ----------
    name:
        Phase name (defaults to the function name).
    description:
        Optional human-readable description.
    produces:
        Typed ports this phase produces.
    consumes:
        Typed ports this phase consumes.

    Returns
    -------
    Callable
        The decorated function with ``__phase_name__``, ``__phase_description__``,
        ``__phase_produces__``, ``__phase_consumes__``, and ``__phase__``
        attributes attached.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__phase__ = True  # type: ignore[attr-defined]
        fn.__phase_name__ = name if isinstance(name, str) else fn.__name__  # type: ignore[attr-defined]
        fn.__phase_description__ = description  # type: ignore[attr-defined]
        fn.__phase_produces__ = produces  # type: ignore[attr-defined]
        fn.__phase_consumes__ = consumes  # type: ignore[attr-defined]
        return fn

    if callable(name):
        return decorator(name)
    return decorator


def pipeline(
    name: str | None = None,
    *,
    description: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a generator function as a native pipeline.

    Supports both ``@pipeline`` and ``@pipeline(...)`` usage.

    Parameters
    ----------
    name:
        Pipeline name (defaults to the function name).
    description:
        Optional human-readable description.

    Returns
    -------
    Callable
        The decorated function with ``__pipeline__``, ``__pipeline_name__``,
        and ``__pipeline_description__`` attributes attached.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__pipeline__ = True  # type: ignore[attr-defined]
        fn.__pipeline_name__ = name if isinstance(name, str) else fn.__name__  # type: ignore[attr-defined]
        fn.__pipeline_description__ = description  # type: ignore[attr-defined]
        return fn

    if callable(name):
        return decorator(name)
    return decorator


def decision(
    name: str | None = None,
    *,
    description: str | None = None,
    vocabulary: frozenset[str] = frozenset(),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Mark a function as a native decision point.

    Supports both ``@decision`` and ``@decision(...)`` usage.

    Parameters
    ----------
    name:
        Decision name (defaults to the function name).
    description:
        Optional human-readable description.
    vocabulary:
        Set of valid return labels (e.g. ``frozenset({'pass', 'fail'})``).

    Returns
    -------
    Callable
        The decorated function with ``__decision__``, ``__decision_name__``,
        ``__decision_description__``, and ``__decision_vocabulary__``
        attributes attached.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__decision__ = True  # type: ignore[attr-defined]
        fn.__decision_name__ = name if isinstance(name, str) else fn.__name__  # type: ignore[attr-defined]
        fn.__decision_description__ = description  # type: ignore[attr-defined]
        fn.__decision_vocabulary__ = vocabulary  # type: ignore[attr-defined]
        return fn

    if callable(name):
        return decorator(name)
    return decorator


# ── Introspection helpers ───────────────────────────────────────────────


def is_phase(fn: Any) -> bool:
    """Return ``True`` if *fn* is a ``@phase``-decorated callable."""
    return bool(getattr(fn, "__phase__", False))


def get_phase_meta(fn: Any) -> dict[str, Any] | None:
    """Return phase metadata dict for *fn*, or ``None``."""
    if not is_phase(fn):
        return None
    return {
        "name": getattr(fn, "__phase_name__", fn.__name__),
        "description": getattr(fn, "__phase_description__", None),
        "produces": getattr(fn, "__phase_produces__", ()),
        "consumes": getattr(fn, "__phase_consumes__", ()),
    }


def is_pipeline(fn: Any) -> bool:
    """Return ``True`` if *fn* is a ``@pipeline``-decorated callable."""
    return bool(getattr(fn, "__pipeline__", False))


def get_pipeline_meta(fn: Any) -> dict[str, Any] | None:
    """Return pipeline metadata dict for *fn*, or ``None``."""
    if not is_pipeline(fn):
        return None
    return {
        "name": getattr(fn, "__pipeline_name__", fn.__name__),
        "description": getattr(fn, "__pipeline_description__", None) or "",
        "phases": [],
        "decisions": [],
    }


def is_decision(fn: Any) -> bool:
    """Return ``True`` if *fn* is a ``@decision``-decorated callable."""
    return bool(getattr(fn, "__decision__", False))


def get_decision_meta(fn: Any) -> dict[str, Any] | None:
    """Return decision metadata dict for *fn*, or ``None``."""
    if not is_decision(fn):
        return None
    vocab = getattr(fn, "__decision_vocabulary__", frozenset())
    return {
        "name": getattr(fn, "__decision_name__", fn.__name__),
        "description": getattr(fn, "__decision_description__", None),
        "vocabulary": frozenset(vocab),
    }
