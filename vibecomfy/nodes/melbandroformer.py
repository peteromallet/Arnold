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

def MelBandRoFormerModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt', 'MelBandRoformer.ckpt'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load MelBandRoFormer audio separation model

    Pack: ComfyUI-MelBandRoformer
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MelBandRoFormerModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'MelBandRoFormerModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def MelBandRoFormerSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    overlap: float | _Omitted = _UNSET,
    chunk_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Separate audio using MelBandRoFormer

    Pack: ComfyUI-MelBandRoformer
    Returns: audio, instrumental

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MelBandRoFormerSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if model is not _UNSET:
        _kwargs['model'] = model
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if chunk_size is not _UNSET:
        _kwargs['chunk_size'] = chunk_size
    _kwargs.update(_extras)
    return node(wf, 'MelBandRoFormerSampler', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['MelBandRoFormerModelLoader', 'MelBandRoFormerSampler']
__vibecomfy_class_types__ = {'MelBandRoFormerModelLoader': 'MelBandRoFormerModelLoader', 'MelBandRoFormerSampler': 'MelBandRoFormerSampler'}
