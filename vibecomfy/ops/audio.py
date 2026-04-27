from __future__ import annotations

from typing import Any

from vibecomfy.ops._namespace import dispatch, namespace_getattr
from vibecomfy.ops.registry import register_op


def t2a(*args: Any, **kwargs: Any) -> Any:
    return dispatch("audio", "t2a", *args, **kwargs)


def _t2a(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError("no audio template registered")


def __getattr__(name: str) -> Any:
    return namespace_getattr("audio", name)


register_op("audio", "t2a", _t2a)


__all__ = ["t2a"]
