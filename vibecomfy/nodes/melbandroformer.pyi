# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def MelBandRoFormerModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt', 'MelBandRoformer.ckpt'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def MelBandRoFormerSampler(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    model: Any | _Omitted = ...,
    overlap: float | _Omitted = ...,
    chunk_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
