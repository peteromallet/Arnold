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

def DualCLIPLoaderGGUF(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_name1: Any | _Omitted = _UNSET,
    clip_name2: Any | _Omitted = _UNSET,
    type_: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    DualCLIPLoaderGGUF

    Pack: ComfyUI-GGUF
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DualCLIPLoaderGGUF() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip_name1 is not _UNSET:
        _kwargs['clip_name1'] = clip_name1
    if clip_name2 is not _UNSET:
        _kwargs['clip_name2'] = clip_name2
    if type_ is not _UNSET:
        _kwargs['type'] = type_
    _kwargs.update(_extras)
    return node(wf, 'DualCLIPLoaderGGUF', _id, pass_raw=pass_raw, **_kwargs)

def UnetLoaderGGUF(
    *args: VibeWorkflow,
    _id: str | None = None,
    unet_name: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    UnetLoaderGGUF

    Pack: ComfyUI-GGUF
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"UnetLoaderGGUF() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if unet_name is not _UNSET:
        _kwargs['unet_name'] = unet_name
    _kwargs.update(_extras)
    return node(wf, 'UnetLoaderGGUF', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF']
__vibecomfy_class_types__ = {'DualCLIPLoaderGGUF': 'DualCLIPLoaderGGUF', 'UnetLoaderGGUF': 'UnetLoaderGGUF'}
