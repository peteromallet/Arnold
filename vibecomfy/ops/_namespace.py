from __future__ import annotations

from typing import Any

from vibecomfy.ops.registry import lookup_op


def dispatch(verb_kind: str, verb_name: str, *args: Any, **kwargs: Any) -> Any:
    from vibecomfy.extras import ensure_plugins_loaded

    ensure_plugins_loaded()
    return lookup_op(verb_kind, verb_name)(*args, **kwargs)


def namespace_getattr(verb_kind: str, verb_name: str) -> Any:
    from vibecomfy.extras import ensure_plugins_loaded

    ensure_plugins_loaded()
    op = lookup_op(verb_kind, verb_name)

    def _call(*args: Any, **kwargs: Any) -> Any:
        return op(*args, **kwargs)

    _call.__name__ = verb_name
    _call.__qualname__ = verb_name
    _call.__doc__ = getattr(op, "__doc__", None)
    return _call
