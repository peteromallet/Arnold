from __future__ import annotations

from typing import Any

from vibecomfy.ops._namespace import dispatch, namespace_getattr
from vibecomfy.ops.registry import register_op


def qwen(image: Any, instruction: str, **overrides: Any) -> Any:
    return dispatch("edit", "qwen", image, instruction, **overrides)


def _qwen(image: Any, instruction: str, **overrides: Any) -> Any:
    from vibecomfy.ops.image import edit

    return edit(image, instruction, model="qwen", **overrides)


def __getattr__(name: str) -> Any:
    return namespace_getattr("edit", name)


register_op("edit", "qwen", _qwen)


__all__ = ["qwen"]
