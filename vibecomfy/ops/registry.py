from __future__ import annotations

from collections.abc import Callable
from typing import Any
import warnings


Op = Callable[..., Any]

_OPS: dict[tuple[str, str], Op] = {}
_OVERRIDE_WARNED: set[tuple[str, str]] = set()


def register_op(verb_kind: str, verb_name: str, fn: Op) -> Op:
    key = (verb_kind, verb_name)
    if key in _OPS and key not in _OVERRIDE_WARNED:
        warnings.warn(
            f"Overriding vibecomfy op {verb_kind}.{verb_name}",
            RuntimeWarning,
            stacklevel=2,
        )
        _OVERRIDE_WARNED.add(key)
    _OPS[key] = fn
    return fn


def lookup_op(verb_kind: str, verb_name: str) -> Op:
    try:
        return _OPS[(verb_kind, verb_name)]
    except KeyError as exc:
        raise AttributeError(f"No vibecomfy op registered for {verb_kind}.{verb_name}") from exc


__all__ = ["Op", "lookup_op", "register_op"]
