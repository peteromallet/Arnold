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
    _id: str | None = None,
    model: Any = _UNSET,
    segmentor: Any = _UNSET,
    device: Any = _UNSET,
    precision: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    DownloadAndLoadSAM2Model
    
    Pack: ComfyUI-segment-anything-2
    Returns: sam2_model
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if segmentor is not _UNSET:
        _kwargs['segmentor'] = segmentor
    if device is not _UNSET:
        _kwargs['device'] = device
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadSAM2Model', _id, pass_raw=pass_raw, **_kwargs)

def Florence2toCoordinates(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    data: Any = _UNSET,
    index: Any = _UNSET,
    batch: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Florence2toCoordinates
    
    Pack: ComfyUI-segment-anything-2
    Returns: center_coordinates, bboxes
    """
    _kwargs: dict[str, Any] = {}
    if data is not _UNSET:
        _kwargs['data'] = data
    if index is not _UNSET:
        _kwargs['index'] = index
    if batch is not _UNSET:
        _kwargs['batch'] = batch
    _kwargs.update(_extras)
    return node(wf, 'Florence2toCoordinates', _id, pass_raw=pass_raw, **_kwargs)

def Sam2AutoSegmentation(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    sam2_model: Any = _UNSET,
    image: Any = _UNSET,
    points_per_side: Any = _UNSET,
    points_per_batch: Any = _UNSET,
    pred_iou_thresh: Any = _UNSET,
    stability_score_thresh: Any = _UNSET,
    stability_score_offset: Any = _UNSET,
    mask_threshold: Any = _UNSET,
    crop_n_layers: Any = _UNSET,
    box_nms_thresh: Any = _UNSET,
    crop_nms_thresh: Any = _UNSET,
    crop_overlap_ratio: Any = _UNSET,
    crop_n_points_downscale_factor: Any = _UNSET,
    min_mask_region_area: Any = _UNSET,
    use_m2m: Any = _UNSET,
    keep_model_loaded: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sam2AutoSegmentation
    
    Pack: ComfyUI-segment-anything-2
    Returns: mask, segmented_image, bbox
    """
    _kwargs: dict[str, Any] = {}
    if sam2_model is not _UNSET:
        _kwargs['sam2_model'] = sam2_model
    if image is not _UNSET:
        _kwargs['image'] = image
    if points_per_side is not _UNSET:
        _kwargs['points_per_side'] = points_per_side
    if points_per_batch is not _UNSET:
        _kwargs['points_per_batch'] = points_per_batch
    if pred_iou_thresh is not _UNSET:
        _kwargs['pred_iou_thresh'] = pred_iou_thresh
    if stability_score_thresh is not _UNSET:
        _kwargs['stability_score_thresh'] = stability_score_thresh
    if stability_score_offset is not _UNSET:
        _kwargs['stability_score_offset'] = stability_score_offset
    if mask_threshold is not _UNSET:
        _kwargs['mask_threshold'] = mask_threshold
    if crop_n_layers is not _UNSET:
        _kwargs['crop_n_layers'] = crop_n_layers
    if box_nms_thresh is not _UNSET:
        _kwargs['box_nms_thresh'] = box_nms_thresh
    if crop_nms_thresh is not _UNSET:
        _kwargs['crop_nms_thresh'] = crop_nms_thresh
    if crop_overlap_ratio is not _UNSET:
        _kwargs['crop_overlap_ratio'] = crop_overlap_ratio
    if crop_n_points_downscale_factor is not _UNSET:
        _kwargs['crop_n_points_downscale_factor'] = crop_n_points_downscale_factor
    if min_mask_region_area is not _UNSET:
        _kwargs['min_mask_region_area'] = min_mask_region_area
    if use_m2m is not _UNSET:
        _kwargs['use_m2m'] = use_m2m
    if keep_model_loaded is not _UNSET:
        _kwargs['keep_model_loaded'] = keep_model_loaded
    _kwargs.update(_extras)
    return node(wf, 'Sam2AutoSegmentation', _id, pass_raw=pass_raw, **_kwargs)

def Sam2Segmentation(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    sam2_model: Any = _UNSET,
    image: Any = _UNSET,
    keep_model_loaded: Any = _UNSET,
    coordinates_positive: Any = _UNSET,
    coordinates_negative: Any = _UNSET,
    bboxes: Any = _UNSET,
    individual_objects: Any = _UNSET,
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
    if sam2_model is not _UNSET:
        _kwargs['sam2_model'] = sam2_model
    if image is not _UNSET:
        _kwargs['image'] = image
    if keep_model_loaded is not _UNSET:
        _kwargs['keep_model_loaded'] = keep_model_loaded
    if coordinates_positive is not _UNSET:
        _kwargs['coordinates_positive'] = coordinates_positive
    if coordinates_negative is not _UNSET:
        _kwargs['coordinates_negative'] = coordinates_negative
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    if individual_objects is not _UNSET:
        _kwargs['individual_objects'] = individual_objects
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'Sam2Segmentation', _id, pass_raw=pass_raw, **_kwargs)

def Sam2VideoSegmentation(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    sam2_model: Any = _UNSET,
    inference_state: Any = _UNSET,
    keep_model_loaded: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sam2VideoSegmentation
    
    Pack: ComfyUI-segment-anything-2
    Returns: mask
    """
    _kwargs: dict[str, Any] = {}
    if sam2_model is not _UNSET:
        _kwargs['sam2_model'] = sam2_model
    if inference_state is not _UNSET:
        _kwargs['inference_state'] = inference_state
    if keep_model_loaded is not _UNSET:
        _kwargs['keep_model_loaded'] = keep_model_loaded
    _kwargs.update(_extras)
    return node(wf, 'Sam2VideoSegmentation', _id, pass_raw=pass_raw, **_kwargs)

def Sam2VideoSegmentationAddPoints(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    sam2_model: Any = _UNSET,
    coordinates_positive: Any = _UNSET,
    frame_index: Any = _UNSET,
    object_index: Any = _UNSET,
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
    if sam2_model is not _UNSET:
        _kwargs['sam2_model'] = sam2_model
    if coordinates_positive is not _UNSET:
        _kwargs['coordinates_positive'] = coordinates_positive
    if frame_index is not _UNSET:
        _kwargs['frame_index'] = frame_index
    if object_index is not _UNSET:
        _kwargs['object_index'] = object_index
    if image is not _UNSET:
        _kwargs['image'] = image
    if coordinates_negative is not _UNSET:
        _kwargs['coordinates_negative'] = coordinates_negative
    if prev_inference_state is not _UNSET:
        _kwargs['prev_inference_state'] = prev_inference_state
    _kwargs.update(_extras)
    return node(wf, 'Sam2VideoSegmentationAddPoints', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['DownloadAndLoadSAM2Model', 'Florence2toCoordinates', 'Sam2AutoSegmentation', 'Sam2Segmentation', 'Sam2VideoSegmentation', 'Sam2VideoSegmentationAddPoints']
