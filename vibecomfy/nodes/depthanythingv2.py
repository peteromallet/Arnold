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

def DepthAnything_V2(
    *args: VibeWorkflow,
    _id: str | None = None,
    da_model: Any | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
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
    model: Literal['depth_anything_v2_vits_fp16.safetensors', 'depth_anything_v2_vits_fp32.safetensors', 'depth_anything_v2_vitb_fp16.safetensors', 'depth_anything_v2_vitb_fp32.safetensors', 'depth_anything_v2_vitl_fp16.safetensors', 'depth_anything_v2_vitl_fp32.safetensors', 'depth_anything_v2_vitg_fp32.safetensors', 'depth_anything_v2_metric_hypersim_vitl_fp32.safetensors', 'depth_anything_v2_metric_vkitti_vitl_fp32.safetensors'] | _Omitted = _UNSET,
    precision: Literal['auto', 'bf16', 'fp16', 'fp32'] | _Omitted = _UNSET,
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

def LoadVideoDepthAnythingModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['v2-vits', 'v2-vitb', 'v2-vitl'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load video depth anything model

    Pack: ComfyUI-DepthAnythingV2
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadVideoDepthAnythingModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'LoadVideoDepthAnythingModel', _id, pass_raw=pass_raw, **_kwargs)

def VideoDepthAnythingOutput(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Output video depth

    Pack: ComfyUI-DepthAnythingV2
    Returns: depth_image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VideoDepthAnythingOutput() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'VideoDepthAnythingOutput', _id, pass_raw=pass_raw, **_kwargs)

def VideoDepthAnythingProcess(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Process video frames with Depth Anything V2

    Pack: ComfyUI-DepthAnythingV2
    Returns: depth

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VideoDepthAnythingProcess() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if images is not _UNSET:
        _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'VideoDepthAnythingProcess', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model', 'LoadVideoDepthAnythingModel', 'VideoDepthAnythingOutput', 'VideoDepthAnythingProcess']
__vibecomfy_class_types__ = {'DepthAnything_V2': 'DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model': 'DownloadAndLoadDepthAnythingV2Model', 'LoadVideoDepthAnythingModel': 'LoadVideoDepthAnythingModel', 'VideoDepthAnythingOutput': 'VideoDepthAnythingOutput', 'VideoDepthAnythingProcess': 'VideoDepthAnythingProcess'}
