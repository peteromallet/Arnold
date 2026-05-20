"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def DualCLIPLoaderGGUF(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    clip_name1: Any = _UNSET,
    clip_name2: Any = _UNSET,
    type_: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    DualCLIPLoaderGGUF
    
    Pack: ComfyUI-GGUF
    Returns: None
    """
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
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    unet_name: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    UnetLoaderGGUF
    
    Pack: ComfyUI-GGUF
    Returns: MODEL
    """
    _kwargs: dict[str, Any] = {}
    if unet_name is not _UNSET:
        _kwargs['unet_name'] = unet_name
    _kwargs.update(_extras)
    return node(wf, 'UnetLoaderGGUF', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF']
