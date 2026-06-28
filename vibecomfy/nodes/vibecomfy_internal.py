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

def VibeComfyStripConditioningKeys(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    keys: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VibeComfy Strip Conditioning Keys

    Pack: vibecomfy
    Returns: positive, negative

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VibeComfyStripConditioningKeys() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if keys is not _UNSET:
        _kwargs['keys'] = keys
    _kwargs.update(_extras)
    return node(wf, 'VibeComfyStripConditioningKeys', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['VibeComfyStripConditioningKeys']
__vibecomfy_class_types__ = {'VibeComfyStripConditioningKeys': 'VibeComfyStripConditioningKeys'}
