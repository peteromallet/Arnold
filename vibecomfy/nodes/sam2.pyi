# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def DownloadAndLoadSAM2Model(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    segmentor: Any | _Omitted = ...,
    device: Any | _Omitted = ...,
    precision: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Florence2toCoordinates(
    *args: VibeWorkflow,
    _id: str | None = ...,
    data: Any | _Omitted = ...,
    index: Any | _Omitted = ...,
    batch: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Sam2AutoSegmentation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sam2_model: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    points_per_side: Any | _Omitted = ...,
    points_per_batch: Any | _Omitted = ...,
    pred_iou_thresh: Any | _Omitted = ...,
    stability_score_thresh: Any | _Omitted = ...,
    stability_score_offset: Any | _Omitted = ...,
    mask_threshold: Any | _Omitted = ...,
    crop_n_layers: Any | _Omitted = ...,
    box_nms_thresh: Any | _Omitted = ...,
    crop_nms_thresh: Any | _Omitted = ...,
    crop_overlap_ratio: Any | _Omitted = ...,
    crop_n_points_downscale_factor: Any | _Omitted = ...,
    min_mask_region_area: Any | _Omitted = ...,
    use_m2m: Any | _Omitted = ...,
    keep_model_loaded: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Sam2Segmentation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sam2_model: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    keep_model_loaded: Any | _Omitted = ...,
    coordinates_positive: Any | _Omitted = ...,
    coordinates_negative: Any | _Omitted = ...,
    bboxes: Any | _Omitted = ...,
    individual_objects: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Sam2VideoSegmentation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sam2_model: Any | _Omitted = ...,
    inference_state: Any | _Omitted = ...,
    keep_model_loaded: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Sam2VideoSegmentationAddPoints(
    *args: VibeWorkflow,
    _id: str | None = ...,
    sam2_model: Any | _Omitted = ...,
    coordinates_positive: Any | _Omitted = ...,
    frame_index: Any | _Omitted = ...,
    object_index: Any | _Omitted = ...,
    image: Any | _Omitted = ...,
    coordinates_negative: Any | _Omitted = ...,
    prev_inference_state: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
