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

def DownloadAndLoadGIMMVFIModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['GIMMVFI_flow_S.pkl', 'GIMMVFI_flow_M.pkl', 'GIMMVFI_noflow_S.pkl', 'GIMMVFI_noflow_M.pkl'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Download and load GIMM-VFI model

    Pack: ComfyUI-GIMM-VFI
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadGIMMVFIModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadGIMMVFIModel', _id, pass_raw=pass_raw, **_kwargs)

def GIMMVFI_interpolate(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    multiplier: int | _Omitted = _UNSET,
    scale: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Interpolate frames with GIMM-VFI

    Pack: ComfyUI-GIMM-VFI
    Returns: images

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GIMMVFI_interpolate() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if images is not _UNSET:
        _kwargs['images'] = images
    if multiplier is not _UNSET:
        _kwargs['multiplier'] = multiplier
    if scale is not _UNSET:
        _kwargs['scale'] = scale
    _kwargs.update(_extras)
    return node(wf, 'GIMMVFI_interpolate', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DownloadAndLoadGIMMVFIModel', 'GIMMVFI_interpolate']
__vibecomfy_class_types__ = {'DownloadAndLoadGIMMVFIModel': 'DownloadAndLoadGIMMVFIModel', 'GIMMVFI_interpolate': 'GIMMVFI_interpolate'}
