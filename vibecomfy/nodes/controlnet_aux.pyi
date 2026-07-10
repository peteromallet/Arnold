# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def CannyEdgePreprocessor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    low_threshold: int | _Omitted = ...,
    high_threshold: int | _Omitted = ...,
    resolution: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DWPreprocessor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    detect_hand: Literal['enable', 'disable'] | _Omitted = ...,
    detect_body: Literal['enable', 'disable'] | _Omitted = ...,
    detect_face: Literal['enable', 'disable'] | _Omitted = ...,
    resolution: int | _Omitted = ...,
    bbox_detector: Literal['yolox_l.onnx', 'yolo_nas_l_fp16.onnx', 'yolo_nas_m_fp16.onnx', 'yolo_nas_s_fp16.onnx'] | _Omitted = ...,
    pose_estimator: Literal['dw-ll_ucoco_384_bs5.torchscript.pt', 'dw-ll_ucoco_384.onnx', 'dw-ll_ucoco.onnx'] | _Omitted = ...,
    scale_stick_for_xinsr_cn: Literal['disable', 'enable'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DepthAnythingPreprocessor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    ckpt_name: Literal['depth_anything_vitl14.pth', 'depth_anything_vitb14.pth', 'depth_anything_vits14.pth'] | _Omitted = ...,
    resolution: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
