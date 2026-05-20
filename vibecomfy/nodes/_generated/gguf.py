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
    clip_name1: Any,
    clip_name2: Any,
    type_: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    DualCLIPLoaderGGUF
    
    Pack: ComfyUI-GGUF
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['clip_name1'] = clip_name1
    _kwargs['clip_name2'] = clip_name2
    _kwargs['type'] = type_
    _kwargs.update(_extras)
    return node(wf, 'DualCLIPLoaderGGUF', pass_raw=pass_raw, **_kwargs)

def UnetLoaderGGUF(
    wf: VibeWorkflow,
    *,
    unet_name: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    UnetLoaderGGUF
    
    Pack: ComfyUI-GGUF
    Returns: MODEL
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['unet_name'] = unet_name
    _kwargs.update(_extras)
    return node(wf, 'UnetLoaderGGUF', pass_raw=pass_raw, **_kwargs)

__all__ = ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF']
