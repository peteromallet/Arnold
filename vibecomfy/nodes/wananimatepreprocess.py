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

def DrawViTPose(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_data: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    retarget_padding: int | _Omitted = _UNSET,
    body_stick_width: int | _Omitted = _UNSET,
    hand_stick_width: int | _Omitted = _UNSET,
    draw_head: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Draws pose images from pose data.

    Pack: ComfyUI-WanAnimatePreprocess
    Returns: pose_images

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DrawViTPose() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pose_data is not _UNSET:
        _kwargs['pose_data'] = pose_data
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if retarget_padding is not _UNSET:
        _kwargs['retarget_padding'] = retarget_padding
    if body_stick_width is not _UNSET:
        _kwargs['body_stick_width'] = body_stick_width
    if hand_stick_width is not _UNSET:
        _kwargs['hand_stick_width'] = hand_stick_width
    if draw_head is not _UNSET:
        _kwargs['draw_head'] = draw_head
    _kwargs.update(_extras)
    return node(wf, 'DrawViTPose', _id, pass_raw=pass_raw, **_kwargs)

def OnnxDetectionModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    vitpose_model: Any | _Omitted = _UNSET,
    yolo_model: Any | _Omitted = _UNSET,
    onnx_device: Literal['CUDAExecutionProvider', 'CPUExecutionProvider'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads ONNX models for pose and face detection. ViTPose for pose estimation and YOLO for object detection.

    Pack: ComfyUI-WanAnimatePreprocess
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"OnnxDetectionModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vitpose_model is not _UNSET:
        _kwargs['vitpose_model'] = vitpose_model
    if yolo_model is not _UNSET:
        _kwargs['yolo_model'] = yolo_model
    if onnx_device is not _UNSET:
        _kwargs['onnx_device'] = onnx_device
    _kwargs.update(_extras)
    return node(wf, 'OnnxDetectionModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def PoseAndFaceDetection(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    retarget_image: Any | _Omitted = _UNSET,
    face_padding: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Detects human poses and face images from input images. Optionally retargets poses based on a reference image.

    Pack: ComfyUI-WanAnimatePreprocess
    Returns: pose_data, face_images, key_frame_body_points, bboxes, face_bboxes

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PoseAndFaceDetection() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if images is not _UNSET:
        _kwargs['images'] = images
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if retarget_image is not _UNSET:
        _kwargs['retarget_image'] = retarget_image
    if face_padding is not _UNSET:
        _kwargs['face_padding'] = face_padding
    _kwargs.update(_extras)
    return node(wf, 'PoseAndFaceDetection', _id, pass_raw=pass_raw, **_kwargs)

def PoseDetectionOneToAllAnimation(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    align_to: Literal['ref', 'pose', 'none'] | _Omitted = _UNSET,
    draw_face_points: Literal['full', 'weak', 'none'] | _Omitted = _UNSET,
    draw_head: Literal['full', 'weak', 'none'] | _Omitted = _UNSET,
    ref_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Specialized pose detection and alignment for OneToAllAnimation model https://github.com/ssj9596/One-to-All-Animation. Detects poses from input images and aligns them based on a reference image if provided.

    Pack: ComfyUI-WanAnimatePreprocess
    Returns: pose_images, ref_pose_image, ref_image, ref_mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PoseDetectionOneToAllAnimation() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if images is not _UNSET:
        _kwargs['images'] = images
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if align_to is not _UNSET:
        _kwargs['align_to'] = align_to
    if draw_face_points is not _UNSET:
        _kwargs['draw_face_points'] = draw_face_points
    if draw_head is not _UNSET:
        _kwargs['draw_head'] = draw_head
    if ref_image is not _UNSET:
        _kwargs['ref_image'] = ref_image
    _kwargs.update(_extras)
    return node(wf, 'PoseDetectionOneToAllAnimation', _id, pass_raw=pass_raw, **_kwargs)

def PoseRetargetPromptHelper(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_data: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Generates text prompts for pose retargeting based on visibility of arms and legs in the template pose. Originally used for Flux Kontext

    Pack: ComfyUI-WanAnimatePreprocess
    Returns: prompt, retarget_prompt

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PoseRetargetPromptHelper() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pose_data is not _UNSET:
        _kwargs['pose_data'] = pose_data
    _kwargs.update(_extras)
    return node(wf, 'PoseRetargetPromptHelper', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DrawViTPose', 'OnnxDetectionModelLoader', 'PoseAndFaceDetection', 'PoseDetectionOneToAllAnimation', 'PoseRetargetPromptHelper']
__vibecomfy_class_types__ = {'DrawViTPose': 'DrawViTPose', 'OnnxDetectionModelLoader': 'OnnxDetectionModelLoader', 'PoseAndFaceDetection': 'PoseAndFaceDetection', 'PoseDetectionOneToAllAnimation': 'PoseDetectionOneToAllAnimation', 'PoseRetargetPromptHelper': 'PoseRetargetPromptHelper'}
