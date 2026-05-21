"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def AddLabel(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    text_x: int | _Omitted = ...,
    text_y: int | _Omitted = ...,
    height: int | _Omitted = ...,
    font_size: int | _Omitted = ...,
    font_color: str | _Omitted = ...,
    label_color: str | _Omitted = ...,
    font: Any | _Omitted = ...,
    text: str | _Omitted = ...,
    direction: Literal['up', 'down', 'left', 'right', 'overlay'] | _Omitted = ...,
    caption: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def BlockifyMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    masks: Any | _Omitted = ...,
    block_size: int | _Omitted = ...,
    device: Literal['cpu', 'gpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def CameraPoseVisualizer(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pose_file_path: str | _Omitted = ...,
    base_xval: float | _Omitted = ...,
    zval: float | _Omitted = ...,
    scale: float | _Omitted = ...,
    use_exact_fx: bool | _Omitted = ...,
    relative_c2w: bool | _Omitted = ...,
    use_viewer: bool | _Omitted = ...,
    cameractrl_poses: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ColorMatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image_ref: Any | _Omitted = ...,
    image_target: Any | _Omitted = ...,
    method: Literal['mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = ...,
    strength: float | _Omitted = ...,
    multithread: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def DrawMaskOnImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    mask: Any | _Omitted = ...,
    color: str | _Omitted = ...,
    device: Literal['cpu', 'gpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetImageSizeAndCount(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def GetImagesFromBatchIndexed(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    indexes: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def INTConstant(
    *args: VibeWorkflow,
    _id: str | None = ...,
    value: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBatchExtendWithOverlap(
    *args: VibeWorkflow,
    _id: str | None = ...,
    source_images: Any | _Omitted = ...,
    overlap: int | _Omitted = ...,
    overlap_side: Literal['source', 'new_images'] | _Omitted = ...,
    overlap_mode: Literal['cut', 'linear_blend', 'ease_in_out', 'filmic_crossfade', 'perceptual_crossfade'] | _Omitted = ...,
    new_images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageBatchMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    inputcount: int | _Omitted = ...,
    image_1: Any | _Omitted = ...,
    image_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageConcatMulti(
    *args: VibeWorkflow,
    _id: str | None = ...,
    inputcount: int | _Omitted = ...,
    image_1: Any | _Omitted = ...,
    direction: Literal['right', 'down', 'left', 'up'] | _Omitted = ...,
    match_image_size: bool | _Omitted = ...,
    image_2: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImagePadKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    left: int | _Omitted = ...,
    right: int | _Omitted = ...,
    top: int | _Omitted = ...,
    bottom: int | _Omitted = ...,
    extra_padding: int | _Omitted = ...,
    pad_mode: Literal['edge', 'edge_pixel', 'color', 'pillarbox_blur'] | _Omitted = ...,
    color: str | _Omitted = ...,
    mask: Any | _Omitted = ...,
    target_width: int | _Omitted = ...,
    target_height: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageResizeKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = ...,
    keep_proportion: bool | _Omitted = ...,
    divisible_by: int | _Omitted = ...,
    get_image_size: Any | _Omitted = ...,
    crop: Literal['disabled', 'center', 0] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def ImageResizeKJv2(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos', 'nvidia_rtx_vsr'] | _Omitted = ...,
    keep_proportion: Literal['stretch', 'resize', 'pad', 'pad_edge', 'pad_edge_pixel', 'crop', 'pillarbox_blur', 'total_pixels'] | _Omitted = ...,
    pad_color: str | _Omitted = ...,
    crop_position: Literal['center', 'top', 'bottom', 'left', 'right'] | _Omitted = ...,
    divisible_by: int | _Omitted = ...,
    mask: Any | _Omitted = ...,
    device: Literal['cpu', 'gpu'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def InsertLatentToIndexed(
    *args: VibeWorkflow,
    _id: str | None = ...,
    source: Any | _Omitted = ...,
    destination: Any | _Omitted = ...,
    index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2AttentionTunerPatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    blocks: str | _Omitted = ...,
    video_scale: float | _Omitted = ...,
    audio_scale: float | _Omitted = ...,
    audio_to_video_scale: float | _Omitted = ...,
    video_to_audio_scale: float | _Omitted = ...,
    triton_kernels: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2MemoryEfficientSageAttentionPatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    triton_kernels: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTX2_NAG(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    nag_scale: float | _Omitted = ...,
    nag_alpha: float | _Omitted = ...,
    nag_tau: float | _Omitted = ...,
    nag_cond_video: Any | _Omitted = ...,
    nag_cond_audio: Any | _Omitted = ...,
    inplace: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVAudioVideoMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video_fps: float | _Omitted = ...,
    video_start_time: float | _Omitted = ...,
    video_end_time: float | _Omitted = ...,
    audio_start_time: float | _Omitted = ...,
    audio_end_time: float | _Omitted = ...,
    max_length: Any | _Omitted = ...,
    video_latent: Any | _Omitted = ...,
    audio_latent: Any | _Omitted = ...,
    existing_mask_mode: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVChunkFeedForward(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    chunks: int | _Omitted = ...,
    dim_threshold: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LTXVImgToVideoInplaceKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae: Any | _Omitted = ...,
    latent: Any | _Omitted = ...,
    num_images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LazySwitchKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    switch: bool | _Omitted = ...,
    on_false: Any | _Omitted = ...,
    on_true: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def LoadVideosFromFolder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video: str | _Omitted = ...,
    force_rate: float | _Omitted = ...,
    custom_width: int | _Omitted = ...,
    custom_height: int | _Omitted = ...,
    frame_load_cap: int | _Omitted = ...,
    skip_first_frames: int | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    output_type: Literal['batch', 'grid'] | _Omitted = ...,
    grid_max_columns: int | _Omitted = ...,
    add_label: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PathchSageAttentionKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    sage_attention: Literal['disabled', 'auto', 'sageattn_qk_int8_pv_fp16_cuda', 'sageattn_qk_int8_pv_fp16_triton', 'sageattn_qk_int8_pv_fp8_cuda', 'sageattn_qk_int8_pv_fp8_cuda++', 'sageattn3', 'sageattn3_per_block_mean'] | _Omitted = ...,
    allow_compile: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PointsEditor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    points_store: str | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    neg_coordinates: str | _Omitted = ...,
    bbox_store: str | _Omitted = ...,
    bboxes: str | _Omitted = ...,
    bbox_format: Literal['xyxy', 'xywh'] | _Omitted = ...,
    width: int | _Omitted = ...,
    height: int | _Omitted = ...,
    normalize: bool | _Omitted = ...,
    bg_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def PreviewAnimation(
    *args: VibeWorkflow,
    _id: str | None = ...,
    fps: float | _Omitted = ...,
    images: Any | _Omitted = ...,
    masks: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SimpleCalculatorKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    expression: str | _Omitted = ...,
    variables: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def SplineEditor(
    *args: VibeWorkflow,
    _id: str | None = ...,
    points_store: str | _Omitted = ...,
    coordinates: str | _Omitted = ...,
    mask_width: int | _Omitted = ...,
    mask_height: int | _Omitted = ...,
    points_to_sample: int | _Omitted = ...,
    sampling_method: Literal['path', 'time', 'controlpoints', 'speed'] | _Omitted = ...,
    interpolation: Literal['cardinal', 'monotone', 'basis', 'linear', 'step-before', 'step-after', 'polar', 'polar-reverse', 'bezier'] | _Omitted = ...,
    tension: float | _Omitted = ...,
    repeat_output: int | _Omitted = ...,
    float_output_type: Literal['list', 'pandas series', 'tensor'] | _Omitted = ...,
    min_value: float | _Omitted = ...,
    max_value: float | _Omitted = ...,
    bg_image: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VAELoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vae_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors', 'pixel_space'] | _Omitted = ...,
    device: Literal['main_device', 'cpu'] | _Omitted = ...,
    weight_dtype: Literal['bf16', 'fp16', 'fp32'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VRAM_Debug(
    *args: VibeWorkflow,
    _id: str | None = ...,
    empty_cache: bool | _Omitted = ...,
    gc_collect: bool | _Omitted = ...,
    unload_all_models: bool | _Omitted = ...,
    any_input: Any | _Omitted = ...,
    image_pass: Any | _Omitted = ...,
    model_pass: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def WidgetToString(
    *args: VibeWorkflow,
    _id: str | None = ...,
    id: int | _Omitted = ...,
    widget_name: str | _Omitted = ...,
    return_all: bool | _Omitted = ...,
    any_input: Any | _Omitted = ...,
    node_title: str | _Omitted = ...,
    allowed_float_decimals: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
