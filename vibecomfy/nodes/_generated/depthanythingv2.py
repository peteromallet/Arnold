"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def DepthAnything_V2(
    wf: VibeWorkflow,
    *,
    da_model: Any,
    images: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://depth-anything-v2.github.io
    
    Pack: ComfyUI-DepthAnythingV2
    Returns: image
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['da_model'] = da_model
    _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'DepthAnything_V2', pass_raw=pass_raw, **_kwargs)

def DownloadAndLoadDepthAnythingV2Model(
    wf: VibeWorkflow,
    *,
    model: Any = 'depth_anything_v2_vitl_fp32.safetensors',
    precision: Any = 'auto',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Models autodownload to `ComfyUI/models/depthanything` from   
    https://huggingface.co/Kijai/DepthAnythingV2-safetensors/tree/main   
       
    fp16 reduces quality by a LOT, not recommended.
    
    Pack: ComfyUI-DepthAnythingV2
    Returns: da_v2_model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadDepthAnythingV2Model', pass_raw=pass_raw, **_kwargs)

__all__ = ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model']
