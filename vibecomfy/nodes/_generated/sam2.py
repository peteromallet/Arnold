"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def DownloadAndLoadSAM2Model(
    wf: VibeWorkflow,
    *,
    model: Any,
    segmentor: Any,
    device: Any,
    precision: Any = 'fp16',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    DownloadAndLoadSAM2Model
    
    Pack: ComfyUI-segment-anything-2
    Returns: sam2_model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['segmentor'] = segmentor
    _kwargs['device'] = device
    _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadSAM2Model', pass_raw=pass_raw, **_kwargs)

def Florence2toCoordinates(
    wf: VibeWorkflow,
    *,
    data: Any,
    index: Any = '0',
    batch: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Florence2toCoordinates
    
    Pack: ComfyUI-segment-anything-2
    Returns: center_coordinates, bboxes
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['data'] = data
    _kwargs['index'] = index
    _kwargs['batch'] = batch
    _kwargs.update(_extras)
    return node(wf, 'Florence2toCoordinates', pass_raw=pass_raw, **_kwargs)

def Sam2AutoSegmentation(
    wf: VibeWorkflow,
    *,
    sam2_model: Any,
    image: Any,
    points_per_side: Any = 32,
    points_per_batch: Any = 64,
    pred_iou_thresh: Any = 0.8,
    stability_score_thresh: Any = 0.95,
    stability_score_offset: Any = 1.0,
    mask_threshold: Any = 0.0,
    crop_n_layers: Any = 0,
    box_nms_thresh: Any = 0.7,
    crop_nms_thresh: Any = 0.7,
    crop_overlap_ratio: Any = 0.34,
    crop_n_points_downscale_factor: Any = 1,
    min_mask_region_area: Any = 0.0,
    use_m2m: Any = False,
    keep_model_loaded: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sam2AutoSegmentation
    
    Pack: ComfyUI-segment-anything-2
    Returns: mask, segmented_image, bbox
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['sam2_model'] = sam2_model
    _kwargs['image'] = image
    _kwargs['points_per_side'] = points_per_side
    _kwargs['points_per_batch'] = points_per_batch
    _kwargs['pred_iou_thresh'] = pred_iou_thresh
    _kwargs['stability_score_thresh'] = stability_score_thresh
    _kwargs['stability_score_offset'] = stability_score_offset
    _kwargs['mask_threshold'] = mask_threshold
    _kwargs['crop_n_layers'] = crop_n_layers
    _kwargs['box_nms_thresh'] = box_nms_thresh
    _kwargs['crop_nms_thresh'] = crop_nms_thresh
    _kwargs['crop_overlap_ratio'] = crop_overlap_ratio
    _kwargs['crop_n_points_downscale_factor'] = crop_n_points_downscale_factor
    _kwargs['min_mask_region_area'] = min_mask_region_area
    _kwargs['use_m2m'] = use_m2m
    _kwargs['keep_model_loaded'] = keep_model_loaded
    _kwargs.update(_extras)
    return node(wf, 'Sam2AutoSegmentation', pass_raw=pass_raw, **_kwargs)

def Sam2Segmentation(
    wf: VibeWorkflow,
    *,
    sam2_model: Any,
    image: Any,
    keep_model_loaded: Any = False,
    coordinates_positive: Any = _UNSET,
    coordinates_negative: Any = _UNSET,
    bboxes: Any = _UNSET,
    individual_objects: Any = False,
    mask: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sam2Segmentation
    
    Pack: ComfyUI-segment-anything-2
    Returns: mask
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['sam2_model'] = sam2_model
    _kwargs['image'] = image
    _kwargs['keep_model_loaded'] = keep_model_loaded
    if coordinates_positive is not _UNSET:
        _kwargs['coordinates_positive'] = coordinates_positive
    if coordinates_negative is not _UNSET:
        _kwargs['coordinates_negative'] = coordinates_negative
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    _kwargs['individual_objects'] = individual_objects
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'Sam2Segmentation', pass_raw=pass_raw, **_kwargs)

def Sam2VideoSegmentation(
    wf: VibeWorkflow,
    *,
    sam2_model: Any,
    inference_state: Any,
    keep_model_loaded: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sam2VideoSegmentation
    
    Pack: ComfyUI-segment-anything-2
    Returns: mask
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['sam2_model'] = sam2_model
    _kwargs['inference_state'] = inference_state
    _kwargs['keep_model_loaded'] = keep_model_loaded
    _kwargs.update(_extras)
    return node(wf, 'Sam2VideoSegmentation', pass_raw=pass_raw, **_kwargs)

def Sam2VideoSegmentationAddPoints(
    wf: VibeWorkflow,
    *,
    sam2_model: Any,
    coordinates_positive: Any,
    frame_index: Any = 0,
    object_index: Any = 0,
    image: Any = _UNSET,
    coordinates_negative: Any = _UNSET,
    prev_inference_state: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sam2VideoSegmentationAddPoints
    
    Pack: ComfyUI-segment-anything-2
    Returns: sam2_model, inference_state
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['sam2_model'] = sam2_model
    _kwargs['coordinates_positive'] = coordinates_positive
    _kwargs['frame_index'] = frame_index
    _kwargs['object_index'] = object_index
    if image is not _UNSET:
        _kwargs['image'] = image
    if coordinates_negative is not _UNSET:
        _kwargs['coordinates_negative'] = coordinates_negative
    if prev_inference_state is not _UNSET:
        _kwargs['prev_inference_state'] = prev_inference_state
    _kwargs.update(_extras)
    return node(wf, 'Sam2VideoSegmentationAddPoints', pass_raw=pass_raw, **_kwargs)

__all__ = ['DownloadAndLoadSAM2Model', 'Florence2toCoordinates', 'Sam2AutoSegmentation', 'Sam2Segmentation', 'Sam2VideoSegmentation', 'Sam2VideoSegmentationAddPoints']
