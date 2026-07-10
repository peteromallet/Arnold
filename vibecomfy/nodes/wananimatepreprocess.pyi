# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DrawViTPose(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pose_data: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    retarget_padding: int | _Omitted = ...,
    body_stick_width: int | _Omitted = ...,
    hand_stick_width: int | _Omitted = ...,
    draw_head: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def OnnxDetectionModelLoader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vitpose_model: Any | _Omitted = ...,
    yolo_model: Any | _Omitted = ...,
    onnx_device: Literal['CUDAExecutionProvider', 'CPUExecutionProvider'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PoseAndFaceDetection(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    retarget_image: Any | _Omitted = ...,
    face_padding: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PoseDetectionOneToAllAnimation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    images: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    align_to: Literal['ref', 'pose', 'none'] | _Omitted = ...,
    draw_face_points: Literal['full', 'weak', 'none'] | _Omitted = ...,
    draw_head: Literal['full', 'weak', 'none'] | _Omitted = ...,
    ref_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PoseRetargetPromptHelper(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pose_data: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
