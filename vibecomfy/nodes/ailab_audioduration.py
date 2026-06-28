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

def Audio_Duration(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio_path: str | _Omitted = _UNSET,
    audio: Any | _Omitted = _UNSET,
    fps: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Audio Duration & Frames

    Pack: AILab_AudioDuration
    Returns: duration_int, duration_float, frames, audio_path

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Audio_Duration() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio_path is not _UNSET:
        _kwargs['audio_path'] = audio_path
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    _kwargs.update(_extras)
    return node(wf, 'Audio Duration', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['Audio_Duration']
__vibecomfy_class_types__ = {'Audio_Duration': 'Audio Duration'}
