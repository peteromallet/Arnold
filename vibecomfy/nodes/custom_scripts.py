# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.templates import _current_workflow_or_raise, node
from vibecomfy.workflow import VibeWorkflow

class _Omitted:
    pass

_UNSET = _Omitted()

def MathExpression_pysssss(
    *args: VibeWorkflow,
    _id: str | None = None,
    expression: str | _Omitted = _UNSET,
    a: Any | _Omitted = _UNSET,
    b: Any | _Omitted = _UNSET,
    c: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Evaluate a math expression

    Pack: ComfyUI-Custom-Scripts
    Returns: int, float

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MathExpression_pysssss() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if expression is not _UNSET:
        _kwargs['expression'] = expression
    if a is not _UNSET:
        _kwargs['a'] = a
    if b is not _UNSET:
        _kwargs['b'] = b
    if c is not _UNSET:
        _kwargs['c'] = c
    _kwargs.update(_extras)
    return node(wf, 'MathExpression|pysssss', _id, pass_raw=pass_raw, **_kwargs)

def ShowText_pysssss(
    *args: VibeWorkflow,
    _id: str | None = None,
    text: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Show text output

    Pack: ComfyUI-Custom-Scripts
    Returns: text

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ShowText_pysssss() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if text is not _UNSET:
        _kwargs['text'] = text
    _kwargs.update(_extras)
    return node(wf, 'ShowText|pysssss', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['MathExpression_pysssss', 'ShowText_pysssss']
__vibecomfy_class_types__ = {'MathExpression_pysssss': 'MathExpression|pysssss', 'ShowText_pysssss': 'ShowText|pysssss'}
