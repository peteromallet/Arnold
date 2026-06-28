# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DepthAnything_V2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    da_model: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DownloadAndLoadDepthAnythingV2Model(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['depth_anything_v2_vits_fp16.safetensors', 'depth_anything_v2_vits_fp32.safetensors', 'depth_anything_v2_vitb_fp16.safetensors', 'depth_anything_v2_vitb_fp32.safetensors', 'depth_anything_v2_vitl_fp16.safetensors', 'depth_anything_v2_vitl_fp32.safetensors', 'depth_anything_v2_vitg_fp32.safetensors', 'depth_anything_v2_metric_hypersim_vitl_fp32.safetensors', 'depth_anything_v2_metric_vkitti_vitl_fp32.safetensors'] | _Omitted = ...,
    precision: Literal['auto', 'bf16', 'fp16', 'fp32'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadVideoDepthAnythingModel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Literal['v2-vits', 'v2-vitb', 'v2-vitl'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VideoDepthAnythingOutput(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VideoDepthAnythingProcess(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
