"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import _current_workflow_or_raise, node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def DepthAnything_V2(
    *args: VibeWorkflow,
    _id: str | None = None,
    da_model: Any = _UNSET,
    images: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://depth-anything-v2.github.io
    
    Pack: ComfyUI-DepthAnythingV2
    Returns: image
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DepthAnything_V2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if da_model is not _UNSET:
        _kwargs['da_model'] = da_model
    if images is not _UNSET:
        _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'DepthAnything_V2', _id, pass_raw=pass_raw, **_kwargs)

def DownloadAndLoadDepthAnythingV2Model(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any = _UNSET,
    precision: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Models autodownload to `ComfyUI/models/depthanything` from   
    https://huggingface.co/Kijai/DepthAnythingV2-safetensors/tree/main   
       
    fp16 reduces quality by a LOT, not recommended.
    
    Pack: ComfyUI-DepthAnythingV2
    Returns: da_v2_model
    
    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadDepthAnythingV2Model() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadDepthAnythingV2Model', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model']
