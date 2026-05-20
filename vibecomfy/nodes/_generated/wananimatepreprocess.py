"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def DrawViTPose(
    wf: VibeWorkflow,
    *,
    pose_data: Any,
    width: Any = 832,
    height: Any = 480,
    retarget_padding: Any = 16,
    body_stick_width: Any = -1,
    hand_stick_width: Any = -1,
    draw_head: Any = 'True',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Draws pose images from pose data.
    
    Pack: ComfyUI-WanAnimatePreprocess
    Returns: pose_images
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['pose_data'] = pose_data
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['retarget_padding'] = retarget_padding
    _kwargs['body_stick_width'] = body_stick_width
    _kwargs['hand_stick_width'] = hand_stick_width
    _kwargs['draw_head'] = draw_head
    _kwargs.update(_extras)
    return node(wf, 'DrawViTPose', pass_raw=pass_raw, **_kwargs)

def OnnxDetectionModelLoader(
    wf: VibeWorkflow,
    *,
    vitpose_model: Any,
    yolo_model: Any,
    onnx_device: Any = 'CUDAExecutionProvider',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads ONNX models for pose and face detection. ViTPose for pose estimation and YOLO for object detection.
    
    Pack: ComfyUI-WanAnimatePreprocess
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vitpose_model'] = vitpose_model
    _kwargs['yolo_model'] = yolo_model
    _kwargs['onnx_device'] = onnx_device
    _kwargs.update(_extras)
    return node(wf, 'OnnxDetectionModelLoader', pass_raw=pass_raw, **_kwargs)

def PoseAndFaceDetection(
    wf: VibeWorkflow,
    *,
    model: Any,
    images: Any,
    width: Any = 832,
    height: Any = 480,
    retarget_image: Any = None,
    face_padding: Any = 0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Detects human poses and face images from input images. Optionally retargets poses based on a reference image.
    
    Pack: ComfyUI-WanAnimatePreprocess
    Returns: pose_data, face_images, key_frame_body_points, bboxes, face_bboxes
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['images'] = images
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['retarget_image'] = retarget_image
    _kwargs['face_padding'] = face_padding
    _kwargs.update(_extras)
    return node(wf, 'PoseAndFaceDetection', pass_raw=pass_raw, **_kwargs)

def PoseDetectionOneToAllAnimation(
    wf: VibeWorkflow,
    *,
    model: Any,
    images: Any,
    width: Any = 832,
    height: Any = 480,
    align_to: Any = 'ref',
    draw_face_points: Any = 'full',
    draw_head: Any = 'full',
    ref_image: Any = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Specialized pose detection and alignment for OneToAllAnimation model https://github.com/ssj9596/One-to-All-Animation. Detects poses from input images and aligns them based on a reference image if provided.
    
    Pack: ComfyUI-WanAnimatePreprocess
    Returns: pose_images, ref_pose_image, ref_image, ref_mask
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['images'] = images
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['align_to'] = align_to
    _kwargs['draw_face_points'] = draw_face_points
    _kwargs['draw_head'] = draw_head
    _kwargs['ref_image'] = ref_image
    _kwargs.update(_extras)
    return node(wf, 'PoseDetectionOneToAllAnimation', pass_raw=pass_raw, **_kwargs)

def PoseRetargetPromptHelper(
    wf: VibeWorkflow,
    *,
    pose_data: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Generates text prompts for pose retargeting based on visibility of arms and legs in the template pose. Originally used for Flux Kontext
    
    Pack: ComfyUI-WanAnimatePreprocess
    Returns: prompt, retarget_prompt
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['pose_data'] = pose_data
    _kwargs.update(_extras)
    return node(wf, 'PoseRetargetPromptHelper', pass_raw=pass_raw, **_kwargs)

__all__ = ['DrawViTPose', 'OnnxDetectionModelLoader', 'PoseAndFaceDetection', 'PoseDetectionOneToAllAnimation', 'PoseRetargetPromptHelper']
