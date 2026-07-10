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

def AddLabel(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    text_x: int | _Omitted = _UNSET,
    text_y: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    font_size: int | _Omitted = _UNSET,
    font_color: str | _Omitted = _UNSET,
    label_color: str | _Omitted = _UNSET,
    font: Any | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    direction: Literal['up', 'down', 'left', 'right', 'overlay'] | _Omitted = _UNSET,
    caption: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a new with the given text, and concatenates it to
    either above or below the input image.
    Note that this changes the input image's height!
    Fonts are loaded from this folder:
    ComfyUI/custom_nodes/ComfyUI-KJNodes/fonts

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"AddLabel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if text_x is not _UNSET:
        _kwargs['text_x'] = text_x
    if text_y is not _UNSET:
        _kwargs['text_y'] = text_y
    if height is not _UNSET:
        _kwargs['height'] = height
    if font_size is not _UNSET:
        _kwargs['font_size'] = font_size
    if font_color is not _UNSET:
        _kwargs['font_color'] = font_color
    if label_color is not _UNSET:
        _kwargs['label_color'] = label_color
    if font is not _UNSET:
        _kwargs['font'] = font
    if text is not _UNSET:
        _kwargs['text'] = text
    if direction is not _UNSET:
        _kwargs['direction'] = direction
    if caption is not _UNSET:
        _kwargs['caption'] = caption
    _kwargs.update(_extras)
    return node(wf, 'AddLabel', _id, pass_raw=pass_raw, **_kwargs)

def AddNoiseToTrackPath(
    *args: VibeWorkflow,
    _id: str | None = None,
    tracks: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    noise_x_ratio: float | _Omitted = _UNSET,
    noise_y_ratio: float | _Omitted = _UNSET,
    noise_temporal_ratio: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: ComfyUI-KJNodes
    Returns: TRACKS

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"AddNoiseToTrackPath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if noise_x_ratio is not _UNSET:
        _kwargs['noise_x_ratio'] = noise_x_ratio
    if noise_y_ratio is not _UNSET:
        _kwargs['noise_y_ratio'] = noise_y_ratio
    if noise_temporal_ratio is not _UNSET:
        _kwargs['noise_temporal_ratio'] = noise_temporal_ratio
    _kwargs.update(_extras)
    return node(wf, 'AddNoiseToTrackPath', _id, pass_raw=pass_raw, **_kwargs)

def AppendInstanceDiffusionTracking(
    *args: VibeWorkflow,
    _id: str | None = None,
    tracking_1: Any | _Omitted = _UNSET,
    tracking_2: Any | _Omitted = _UNSET,
    prompt_1: str | _Omitted = _UNSET,
    prompt_2: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Appends tracking data to be used with InstanceDiffusion:
    https://github.com/logtd/ComfyUI-InstanceDiffusion

    Pack: ComfyUI-KJNodes
    Returns: tracking, prompt

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"AppendInstanceDiffusionTracking() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if tracking_1 is not _UNSET:
        _kwargs['tracking_1'] = tracking_1
    if tracking_2 is not _UNSET:
        _kwargs['tracking_2'] = tracking_2
    if prompt_1 is not _UNSET:
        _kwargs['prompt_1'] = prompt_1
    if prompt_2 is not _UNSET:
        _kwargs['prompt_2'] = prompt_2
    _kwargs.update(_extras)
    return node(wf, 'AppendInstanceDiffusionTracking', _id, pass_raw=pass_raw, **_kwargs)

def AppendStringsToList(
    *args: VibeWorkflow,
    _id: str | None = None,
    string1: str | _Omitted = _UNSET,
    string2: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Append Strings To List

    Pack: ComfyUI-KJNodes
    Returns: STRING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"AppendStringsToList() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if string1 is not _UNSET:
        _kwargs['string1'] = string1
    if string2 is not _UNSET:
        _kwargs['string2'] = string2
    _kwargs.update(_extras)
    return node(wf, 'AppendStringsToList', _id, pass_raw=pass_raw, **_kwargs)

def ApplyRifleXRoPE_HunuyanVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    k: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Extends the potential frame count of HunyuanVideo using this method: https://github.com/thu-ml/RIFLEx

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ApplyRifleXRoPE_HunuyanVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if k is not _UNSET:
        _kwargs['k'] = k
    _kwargs.update(_extras)
    return node(wf, 'ApplyRifleXRoPE_HunuyanVideo', _id, pass_raw=pass_raw, **_kwargs)

def ApplyRifleXRoPE_WanVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    k: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Extends the potential frame count of HunyuanVideo using this method: https://github.com/thu-ml/RIFLEx

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ApplyRifleXRoPE_WanVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if k is not _UNSET:
        _kwargs['k'] = k
    _kwargs.update(_extras)
    return node(wf, 'ApplyRifleXRoPE_WanVideo', _id, pass_raw=pass_raw, **_kwargs)

def AudioConcatenate(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio1: Any | _Omitted = _UNSET,
    audio2: Any | _Omitted = _UNSET,
    direction: Literal['right', 'left'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Concatenates the audio1 to audio2 in the specified direction.

    Pack: ComfyUI-KJNodes
    Returns: AUDIO

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"AudioConcatenate() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio1 is not _UNSET:
        _kwargs['audio1'] = audio1
    if audio2 is not _UNSET:
        _kwargs['audio2'] = audio2
    if direction is not _UNSET:
        _kwargs['direction'] = direction
    _kwargs.update(_extras)
    return node(wf, 'AudioConcatenate', _id, pass_raw=pass_raw, **_kwargs)

def BOOLConstant(
    *args: VibeWorkflow,
    _id: str | None = None,
    value: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    BOOL Constant

    Pack: ComfyUI-KJNodes
    Returns: value

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BOOLConstant() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if value is not _UNSET:
        _kwargs['value'] = value
    _kwargs.update(_extras)
    return node(wf, 'BOOLConstant', _id, pass_raw=pass_raw, **_kwargs)

def BatchCLIPSeg(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    threshold: float | _Omitted = _UNSET,
    binary_mask: bool | _Omitted = _UNSET,
    combine_mask: bool | _Omitted = _UNSET,
    use_cuda: bool | _Omitted = _UNSET,
    blur_sigma: float | _Omitted = _UNSET,
    opt_model: Any | _Omitted = _UNSET,
    prev_mask: Any | _Omitted = _UNSET,
    image_bg_level: float | _Omitted = _UNSET,
    invert: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Segments an image or batch of images using CLIPSeg.

    Pack: ComfyUI-KJNodes
    Returns: Mask, Image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BatchCLIPSeg() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if text is not _UNSET:
        _kwargs['text'] = text
    if threshold is not _UNSET:
        _kwargs['threshold'] = threshold
    if binary_mask is not _UNSET:
        _kwargs['binary_mask'] = binary_mask
    if combine_mask is not _UNSET:
        _kwargs['combine_mask'] = combine_mask
    if use_cuda is not _UNSET:
        _kwargs['use_cuda'] = use_cuda
    if blur_sigma is not _UNSET:
        _kwargs['blur_sigma'] = blur_sigma
    if opt_model is not _UNSET:
        _kwargs['opt_model'] = opt_model
    if prev_mask is not _UNSET:
        _kwargs['prev_mask'] = prev_mask
    if image_bg_level is not _UNSET:
        _kwargs['image_bg_level'] = image_bg_level
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    _kwargs.update(_extras)
    return node(wf, 'BatchCLIPSeg', _id, pass_raw=pass_raw, **_kwargs)

def BatchCropFromMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    original_images: Any | _Omitted = _UNSET,
    masks: Any | _Omitted = _UNSET,
    crop_size_mult: float | _Omitted = _UNSET,
    bbox_smooth_alpha: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Batch Crop From Mask

    Pack: ComfyUI-KJNodes
    Returns: original_images, cropped_images, bboxes, width, height

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BatchCropFromMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if original_images is not _UNSET:
        _kwargs['original_images'] = original_images
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    if crop_size_mult is not _UNSET:
        _kwargs['crop_size_mult'] = crop_size_mult
    if bbox_smooth_alpha is not _UNSET:
        _kwargs['bbox_smooth_alpha'] = bbox_smooth_alpha
    _kwargs.update(_extras)
    return node(wf, 'BatchCropFromMask', _id, pass_raw=pass_raw, **_kwargs)

def BatchCropFromMaskAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    original_images: Any | _Omitted = _UNSET,
    masks: Any | _Omitted = _UNSET,
    crop_size_mult: float | _Omitted = _UNSET,
    bbox_smooth_alpha: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Batch Crop From Mask Advanced

    Pack: ComfyUI-KJNodes
    Returns: original_images, cropped_images, cropped_masks, combined_crop_image, combined_crop_masks, bboxes, combined_bounding_box, bbox_width, bbox_height

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BatchCropFromMaskAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if original_images is not _UNSET:
        _kwargs['original_images'] = original_images
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    if crop_size_mult is not _UNSET:
        _kwargs['crop_size_mult'] = crop_size_mult
    if bbox_smooth_alpha is not _UNSET:
        _kwargs['bbox_smooth_alpha'] = bbox_smooth_alpha
    _kwargs.update(_extras)
    return node(wf, 'BatchCropFromMaskAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def BatchUncrop(
    *args: VibeWorkflow,
    _id: str | None = None,
    original_images: Any | _Omitted = _UNSET,
    cropped_images: Any | _Omitted = _UNSET,
    bboxes: Any | _Omitted = _UNSET,
    border_blending: float | _Omitted = _UNSET,
    crop_rescale: float | _Omitted = _UNSET,
    border_top: bool | _Omitted = _UNSET,
    border_bottom: bool | _Omitted = _UNSET,
    border_left: bool | _Omitted = _UNSET,
    border_right: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Batch Uncrop

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BatchUncrop() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if original_images is not _UNSET:
        _kwargs['original_images'] = original_images
    if cropped_images is not _UNSET:
        _kwargs['cropped_images'] = cropped_images
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    if border_blending is not _UNSET:
        _kwargs['border_blending'] = border_blending
    if crop_rescale is not _UNSET:
        _kwargs['crop_rescale'] = crop_rescale
    if border_top is not _UNSET:
        _kwargs['border_top'] = border_top
    if border_bottom is not _UNSET:
        _kwargs['border_bottom'] = border_bottom
    if border_left is not _UNSET:
        _kwargs['border_left'] = border_left
    if border_right is not _UNSET:
        _kwargs['border_right'] = border_right
    _kwargs.update(_extras)
    return node(wf, 'BatchUncrop', _id, pass_raw=pass_raw, **_kwargs)

def BatchUncropAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    original_images: Any | _Omitted = _UNSET,
    cropped_images: Any | _Omitted = _UNSET,
    cropped_masks: Any | _Omitted = _UNSET,
    combined_crop_mask: Any | _Omitted = _UNSET,
    bboxes: Any | _Omitted = _UNSET,
    border_blending: float | _Omitted = _UNSET,
    crop_rescale: float | _Omitted = _UNSET,
    use_combined_mask: bool | _Omitted = _UNSET,
    use_square_mask: bool | _Omitted = _UNSET,
    combined_bounding_box: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Batch Uncrop Advanced

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BatchUncropAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if original_images is not _UNSET:
        _kwargs['original_images'] = original_images
    if cropped_images is not _UNSET:
        _kwargs['cropped_images'] = cropped_images
    if cropped_masks is not _UNSET:
        _kwargs['cropped_masks'] = cropped_masks
    if combined_crop_mask is not _UNSET:
        _kwargs['combined_crop_mask'] = combined_crop_mask
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    if border_blending is not _UNSET:
        _kwargs['border_blending'] = border_blending
    if crop_rescale is not _UNSET:
        _kwargs['crop_rescale'] = crop_rescale
    if use_combined_mask is not _UNSET:
        _kwargs['use_combined_mask'] = use_combined_mask
    if use_square_mask is not _UNSET:
        _kwargs['use_square_mask'] = use_square_mask
    if combined_bounding_box is not _UNSET:
        _kwargs['combined_bounding_box'] = combined_bounding_box
    _kwargs.update(_extras)
    return node(wf, 'BatchUncropAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def BboxToInt(
    *args: VibeWorkflow,
    _id: str | None = None,
    bboxes: Any | _Omitted = _UNSET,
    index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns selected index from bounding box list as integers.

    Pack: ComfyUI-KJNodes
    Returns: x_min, y_min, width, height, center_x, center_y

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BboxToInt() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    if index is not _UNSET:
        _kwargs['index'] = index
    _kwargs.update(_extras)
    return node(wf, 'BboxToInt', _id, pass_raw=pass_raw, **_kwargs)

def BboxVisualize(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    bboxes: Any | _Omitted = _UNSET,
    line_width: int | _Omitted = _UNSET,
    bbox_format: Literal['xywh', 'xyxy'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Visualizes the specified bbox on the image.

    Pack: ComfyUI-KJNodes
    Returns: images

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BboxVisualize() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    if line_width is not _UNSET:
        _kwargs['line_width'] = line_width
    if bbox_format is not _UNSET:
        _kwargs['bbox_format'] = bbox_format
    _kwargs.update(_extras)
    return node(wf, 'BboxVisualize', _id, pass_raw=pass_raw, **_kwargs)

def BlockifyMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    masks: Any | _Omitted = _UNSET,
    block_size: int | _Omitted = _UNSET,
    device: Literal['cpu', 'gpu'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a block mask by dividing the bounding box of each mask into blocks of the specified size and filling in blocks that contain any part of the original mask.

    Pack: ComfyUI-KJNodes
    Returns: mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"BlockifyMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    if block_size is not _UNSET:
        _kwargs['block_size'] = block_size
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'BlockifyMask', _id, pass_raw=pass_raw, **_kwargs)

def CFGZeroStarAndInit(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    use_zero_init: bool | _Omitted = _UNSET,
    zero_init_steps: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/WeichenFan/CFG-Zero-star

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CFGZeroStarAndInit() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if use_zero_init is not _UNSET:
        _kwargs['use_zero_init'] = use_zero_init
    if zero_init_steps is not _UNSET:
        _kwargs['zero_init_steps'] = zero_init_steps
    _kwargs.update(_extras)
    return node(wf, 'CFGZeroStarAndInit', _id, pass_raw=pass_raw, **_kwargs)

def CameraPoseVisualizer(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_file_path: str | _Omitted = _UNSET,
    base_xval: float | _Omitted = _UNSET,
    zval: float | _Omitted = _UNSET,
    scale: float | _Omitted = _UNSET,
    use_exact_fx: bool | _Omitted = _UNSET,
    relative_c2w: bool | _Omitted = _UNSET,
    use_viewer: bool | _Omitted = _UNSET,
    cameractrl_poses: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Visualizes the camera poses, from Animatediff-Evolved CameraCtrl Pose
    or a .txt file with RealEstate camera intrinsics and coordinates, in a 3D plot.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CameraPoseVisualizer() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pose_file_path is not _UNSET:
        _kwargs['pose_file_path'] = pose_file_path
    if base_xval is not _UNSET:
        _kwargs['base_xval'] = base_xval
    if zval is not _UNSET:
        _kwargs['zval'] = zval
    if scale is not _UNSET:
        _kwargs['scale'] = scale
    if use_exact_fx is not _UNSET:
        _kwargs['use_exact_fx'] = use_exact_fx
    if relative_c2w is not _UNSET:
        _kwargs['relative_c2w'] = relative_c2w
    if use_viewer is not _UNSET:
        _kwargs['use_viewer'] = use_viewer
    if cameractrl_poses is not _UNSET:
        _kwargs['cameractrl_poses'] = cameractrl_poses
    _kwargs.update(_extras)
    return node(wf, 'CameraPoseVisualizer', _id, pass_raw=pass_raw, **_kwargs)

def CheckpointLoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    ckpt_name: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = _UNSET,
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp16', 'bf16', 'fp32'] | _Omitted = _UNSET,
    compute_dtype: Literal['default', 'fp16', 'bf16', 'fp32'] | _Omitted = _UNSET,
    patch_cublaslinear: bool | _Omitted = _UNSET,
    sage_attention: Literal['disabled', 'auto', 'sageattn_qk_int8_pv_fp16_cuda', 'sageattn_qk_int8_pv_fp16_triton', 'sageattn_qk_int8_pv_fp8_cuda', 'sageattn_qk_int8_pv_fp8_cuda++', 'sageattn3', 'sageattn3_per_block_mean'] | _Omitted = _UNSET,
    enable_fp16_accumulation: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Experimental node for patching torch.nn.Linear with CublasLinear.

    Pack: ComfyUI-KJNodes
    Returns: MODEL, CLIP, VAE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CheckpointLoaderKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ckpt_name is not _UNSET:
        _kwargs['ckpt_name'] = ckpt_name
    if weight_dtype is not _UNSET:
        _kwargs['weight_dtype'] = weight_dtype
    if compute_dtype is not _UNSET:
        _kwargs['compute_dtype'] = compute_dtype
    if patch_cublaslinear is not _UNSET:
        _kwargs['patch_cublaslinear'] = patch_cublaslinear
    if sage_attention is not _UNSET:
        _kwargs['sage_attention'] = sage_attention
    if enable_fp16_accumulation is not _UNSET:
        _kwargs['enable_fp16_accumulation'] = enable_fp16_accumulation
    _kwargs.update(_extras)
    return node(wf, 'CheckpointLoaderKJ', _id, pass_raw=pass_raw, **_kwargs)

def CheckpointPerturbWeights(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    joint_blocks: float | _Omitted = _UNSET,
    final_layer: float | _Omitted = _UNSET,
    rest_of_the_blocks: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    CheckpointPerturbWeights

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CheckpointPerturbWeights() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if joint_blocks is not _UNSET:
        _kwargs['joint_blocks'] = joint_blocks
    if final_layer is not _UNSET:
        _kwargs['final_layer'] = final_layer
    if rest_of_the_blocks is not _UNSET:
        _kwargs['rest_of_the_blocks'] = rest_of_the_blocks
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'CheckpointPerturbWeights', _id, pass_raw=pass_raw, **_kwargs)

def ColorMatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    image_ref: Any | _Omitted = _UNSET,
    image_target: Any | _Omitted = _UNSET,
    method: Literal['mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    multithread: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    color-matcher enables color transfer across images which comes in handy for automatic
    color-grading of photographs, paintings and film sequences as well as light-field
    and stopmotion corrections.

    The methods behind the mappings are based on the approach from Reinhard et al.,
    the Monge-Kantorovich Linearization (MKL) as proposed by Pitie et al. and our analytical solution
    to a Multi-Variate Gaussian Distribution (MVGD) transfer in conjunction with classical histogram
    matching. As shown below our HM-MVGD-HM compound outperforms existing methods.
    https://github.com/hahnec/color-matcher/

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ColorMatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image_ref is not _UNSET:
        _kwargs['image_ref'] = image_ref
    if image_target is not _UNSET:
        _kwargs['image_target'] = image_target
    if method is not _UNSET:
        _kwargs['method'] = method
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if multithread is not _UNSET:
        _kwargs['multithread'] = multithread
    _kwargs.update(_extras)
    return node(wf, 'ColorMatch', _id, pass_raw=pass_raw, **_kwargs)

def ColorMatchV2(
    *args: VibeWorkflow,
    _id: str | None = None,
    image_target: Any | _Omitted = _UNSET,
    image_ref: Any | _Omitted = _UNSET,
    method: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    multithread: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    color-matcher enables color transfer across images which comes in handy for automatic
    color-grading of photographs, paintings and film sequences as well as light-field
    and stopmotion corrections.

    The methods behind the mappings are based on the approach from Reinhard et al.,
    the Monge-Kantorovich Linearization (MKL) as proposed by Pitie et al. and our analytical solution
    to a Multi-Variate Gaussian Distribution (MVGD) transfer in conjunction with classical histogram
    matching. As shown below our HM-MVGD-HM compound outperforms existing methods.
    https://github.com/hahnec/color-matcher/

    'reinhard_lab_gpu' method uses Kornia for GPU-accelerated color transfer in Lab color space.

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ColorMatchV2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image_target is not _UNSET:
        _kwargs['image_target'] = image_target
    if image_ref is not _UNSET:
        _kwargs['image_ref'] = image_ref
    if method is not _UNSET:
        _kwargs['method'] = method
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if multithread is not _UNSET:
        _kwargs['multithread'] = multithread
    _kwargs.update(_extras)
    return node(wf, 'ColorMatchV2', _id, pass_raw=pass_raw, **_kwargs)

def ColorToMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    invert: bool | _Omitted = _UNSET,
    red: int | _Omitted = _UNSET,
    green: int | _Omitted = _UNSET,
    blue: int | _Omitted = _UNSET,
    threshold: int | _Omitted = _UNSET,
    per_batch: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Converts chosen RGB value to a mask.
    With batch inputs, the **per_batch**
    controls the number of images processed at once.

    Pack: ComfyUI-KJNodes
    Returns: MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ColorToMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if red is not _UNSET:
        _kwargs['red'] = red
    if green is not _UNSET:
        _kwargs['green'] = green
    if blue is not _UNSET:
        _kwargs['blue'] = blue
    if threshold is not _UNSET:
        _kwargs['threshold'] = threshold
    if per_batch is not _UNSET:
        _kwargs['per_batch'] = per_batch
    _kwargs.update(_extras)
    return node(wf, 'ColorToMask', _id, pass_raw=pass_raw, **_kwargs)

def CondPassThrough(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Simply passes through the positive and negative conditioning,
        workaround for Set node not allowing bypassed inputs.

    Pack: ComfyUI-KJNodes
    Returns: positive, negative

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CondPassThrough() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    _kwargs.update(_extras)
    return node(wf, 'CondPassThrough', _id, pass_raw=pass_raw, **_kwargs)

def ConditioningMultiCombine(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: int | _Omitted = _UNSET,
    operation: Literal['combine', 'concat'] | _Omitted = _UNSET,
    conditioning_1: Any | _Omitted = _UNSET,
    conditioning_2: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Combines multiple conditioning nodes into one

    Pack: ComfyUI-KJNodes
    Returns: combined, inputcount

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ConditioningMultiCombine() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if inputcount is not _UNSET:
        _kwargs['inputcount'] = inputcount
    if operation is not _UNSET:
        _kwargs['operation'] = operation
    if conditioning_1 is not _UNSET:
        _kwargs['conditioning_1'] = conditioning_1
    if conditioning_2 is not _UNSET:
        _kwargs['conditioning_2'] = conditioning_2
    _kwargs.update(_extras)
    return node(wf, 'ConditioningMultiCombine', _id, pass_raw=pass_raw, **_kwargs)

def ConditioningSetMaskAndCombine(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive_1: Any | _Omitted = _UNSET,
    negative_1: Any | _Omitted = _UNSET,
    positive_2: Any | _Omitted = _UNSET,
    negative_2: Any | _Omitted = _UNSET,
    mask_1: Any | _Omitted = _UNSET,
    mask_2: Any | _Omitted = _UNSET,
    mask_1_strength: float | _Omitted = _UNSET,
    mask_2_strength: float | _Omitted = _UNSET,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Bundles multiple conditioning mask and combine nodes into one,functionality is identical to ComfyUI native nodes

    Pack: ComfyUI-KJNodes
    Returns: combined_positive, combined_negative

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ConditioningSetMaskAndCombine() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive_1 is not _UNSET:
        _kwargs['positive_1'] = positive_1
    if negative_1 is not _UNSET:
        _kwargs['negative_1'] = negative_1
    if positive_2 is not _UNSET:
        _kwargs['positive_2'] = positive_2
    if negative_2 is not _UNSET:
        _kwargs['negative_2'] = negative_2
    if mask_1 is not _UNSET:
        _kwargs['mask_1'] = mask_1
    if mask_2 is not _UNSET:
        _kwargs['mask_2'] = mask_2
    if mask_1_strength is not _UNSET:
        _kwargs['mask_1_strength'] = mask_1_strength
    if mask_2_strength is not _UNSET:
        _kwargs['mask_2_strength'] = mask_2_strength
    if set_cond_area is not _UNSET:
        _kwargs['set_cond_area'] = set_cond_area
    _kwargs.update(_extras)
    return node(wf, 'ConditioningSetMaskAndCombine', _id, pass_raw=pass_raw, **_kwargs)

def ConditioningSetMaskAndCombine3(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive_1: Any | _Omitted = _UNSET,
    negative_1: Any | _Omitted = _UNSET,
    positive_2: Any | _Omitted = _UNSET,
    negative_2: Any | _Omitted = _UNSET,
    positive_3: Any | _Omitted = _UNSET,
    negative_3: Any | _Omitted = _UNSET,
    mask_1: Any | _Omitted = _UNSET,
    mask_2: Any | _Omitted = _UNSET,
    mask_3: Any | _Omitted = _UNSET,
    mask_1_strength: float | _Omitted = _UNSET,
    mask_2_strength: float | _Omitted = _UNSET,
    mask_3_strength: float | _Omitted = _UNSET,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Bundles multiple conditioning mask and combine nodes into one,functionality is identical to ComfyUI native nodes

    Pack: ComfyUI-KJNodes
    Returns: combined_positive, combined_negative

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ConditioningSetMaskAndCombine3() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive_1 is not _UNSET:
        _kwargs['positive_1'] = positive_1
    if negative_1 is not _UNSET:
        _kwargs['negative_1'] = negative_1
    if positive_2 is not _UNSET:
        _kwargs['positive_2'] = positive_2
    if negative_2 is not _UNSET:
        _kwargs['negative_2'] = negative_2
    if positive_3 is not _UNSET:
        _kwargs['positive_3'] = positive_3
    if negative_3 is not _UNSET:
        _kwargs['negative_3'] = negative_3
    if mask_1 is not _UNSET:
        _kwargs['mask_1'] = mask_1
    if mask_2 is not _UNSET:
        _kwargs['mask_2'] = mask_2
    if mask_3 is not _UNSET:
        _kwargs['mask_3'] = mask_3
    if mask_1_strength is not _UNSET:
        _kwargs['mask_1_strength'] = mask_1_strength
    if mask_2_strength is not _UNSET:
        _kwargs['mask_2_strength'] = mask_2_strength
    if mask_3_strength is not _UNSET:
        _kwargs['mask_3_strength'] = mask_3_strength
    if set_cond_area is not _UNSET:
        _kwargs['set_cond_area'] = set_cond_area
    _kwargs.update(_extras)
    return node(wf, 'ConditioningSetMaskAndCombine3', _id, pass_raw=pass_raw, **_kwargs)

def ConditioningSetMaskAndCombine4(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive_1: Any | _Omitted = _UNSET,
    negative_1: Any | _Omitted = _UNSET,
    positive_2: Any | _Omitted = _UNSET,
    negative_2: Any | _Omitted = _UNSET,
    positive_3: Any | _Omitted = _UNSET,
    negative_3: Any | _Omitted = _UNSET,
    positive_4: Any | _Omitted = _UNSET,
    negative_4: Any | _Omitted = _UNSET,
    mask_1: Any | _Omitted = _UNSET,
    mask_2: Any | _Omitted = _UNSET,
    mask_3: Any | _Omitted = _UNSET,
    mask_4: Any | _Omitted = _UNSET,
    mask_1_strength: float | _Omitted = _UNSET,
    mask_2_strength: float | _Omitted = _UNSET,
    mask_3_strength: float | _Omitted = _UNSET,
    mask_4_strength: float | _Omitted = _UNSET,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Bundles multiple conditioning mask and combine nodes into one,functionality is identical to ComfyUI native nodes

    Pack: ComfyUI-KJNodes
    Returns: combined_positive, combined_negative

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ConditioningSetMaskAndCombine4() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive_1 is not _UNSET:
        _kwargs['positive_1'] = positive_1
    if negative_1 is not _UNSET:
        _kwargs['negative_1'] = negative_1
    if positive_2 is not _UNSET:
        _kwargs['positive_2'] = positive_2
    if negative_2 is not _UNSET:
        _kwargs['negative_2'] = negative_2
    if positive_3 is not _UNSET:
        _kwargs['positive_3'] = positive_3
    if negative_3 is not _UNSET:
        _kwargs['negative_3'] = negative_3
    if positive_4 is not _UNSET:
        _kwargs['positive_4'] = positive_4
    if negative_4 is not _UNSET:
        _kwargs['negative_4'] = negative_4
    if mask_1 is not _UNSET:
        _kwargs['mask_1'] = mask_1
    if mask_2 is not _UNSET:
        _kwargs['mask_2'] = mask_2
    if mask_3 is not _UNSET:
        _kwargs['mask_3'] = mask_3
    if mask_4 is not _UNSET:
        _kwargs['mask_4'] = mask_4
    if mask_1_strength is not _UNSET:
        _kwargs['mask_1_strength'] = mask_1_strength
    if mask_2_strength is not _UNSET:
        _kwargs['mask_2_strength'] = mask_2_strength
    if mask_3_strength is not _UNSET:
        _kwargs['mask_3_strength'] = mask_3_strength
    if mask_4_strength is not _UNSET:
        _kwargs['mask_4_strength'] = mask_4_strength
    if set_cond_area is not _UNSET:
        _kwargs['set_cond_area'] = set_cond_area
    _kwargs.update(_extras)
    return node(wf, 'ConditioningSetMaskAndCombine4', _id, pass_raw=pass_raw, **_kwargs)

def ConditioningSetMaskAndCombine5(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive_1: Any | _Omitted = _UNSET,
    negative_1: Any | _Omitted = _UNSET,
    positive_2: Any | _Omitted = _UNSET,
    negative_2: Any | _Omitted = _UNSET,
    positive_3: Any | _Omitted = _UNSET,
    negative_3: Any | _Omitted = _UNSET,
    positive_4: Any | _Omitted = _UNSET,
    negative_4: Any | _Omitted = _UNSET,
    positive_5: Any | _Omitted = _UNSET,
    negative_5: Any | _Omitted = _UNSET,
    mask_1: Any | _Omitted = _UNSET,
    mask_2: Any | _Omitted = _UNSET,
    mask_3: Any | _Omitted = _UNSET,
    mask_4: Any | _Omitted = _UNSET,
    mask_5: Any | _Omitted = _UNSET,
    mask_1_strength: float | _Omitted = _UNSET,
    mask_2_strength: float | _Omitted = _UNSET,
    mask_3_strength: float | _Omitted = _UNSET,
    mask_4_strength: float | _Omitted = _UNSET,
    mask_5_strength: float | _Omitted = _UNSET,
    set_cond_area: Literal['default', 'mask bounds'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Bundles multiple conditioning mask and combine nodes into one,functionality is identical to ComfyUI native nodes

    Pack: ComfyUI-KJNodes
    Returns: combined_positive, combined_negative

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ConditioningSetMaskAndCombine5() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive_1 is not _UNSET:
        _kwargs['positive_1'] = positive_1
    if negative_1 is not _UNSET:
        _kwargs['negative_1'] = negative_1
    if positive_2 is not _UNSET:
        _kwargs['positive_2'] = positive_2
    if negative_2 is not _UNSET:
        _kwargs['negative_2'] = negative_2
    if positive_3 is not _UNSET:
        _kwargs['positive_3'] = positive_3
    if negative_3 is not _UNSET:
        _kwargs['negative_3'] = negative_3
    if positive_4 is not _UNSET:
        _kwargs['positive_4'] = positive_4
    if negative_4 is not _UNSET:
        _kwargs['negative_4'] = negative_4
    if positive_5 is not _UNSET:
        _kwargs['positive_5'] = positive_5
    if negative_5 is not _UNSET:
        _kwargs['negative_5'] = negative_5
    if mask_1 is not _UNSET:
        _kwargs['mask_1'] = mask_1
    if mask_2 is not _UNSET:
        _kwargs['mask_2'] = mask_2
    if mask_3 is not _UNSET:
        _kwargs['mask_3'] = mask_3
    if mask_4 is not _UNSET:
        _kwargs['mask_4'] = mask_4
    if mask_5 is not _UNSET:
        _kwargs['mask_5'] = mask_5
    if mask_1_strength is not _UNSET:
        _kwargs['mask_1_strength'] = mask_1_strength
    if mask_2_strength is not _UNSET:
        _kwargs['mask_2_strength'] = mask_2_strength
    if mask_3_strength is not _UNSET:
        _kwargs['mask_3_strength'] = mask_3_strength
    if mask_4_strength is not _UNSET:
        _kwargs['mask_4_strength'] = mask_4_strength
    if mask_5_strength is not _UNSET:
        _kwargs['mask_5_strength'] = mask_5_strength
    if set_cond_area is not _UNSET:
        _kwargs['set_cond_area'] = set_cond_area
    _kwargs.update(_extras)
    return node(wf, 'ConditioningSetMaskAndCombine5', _id, pass_raw=pass_raw, **_kwargs)

def ConsolidateMasksKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    masks: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    padding: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Consolidates a batch of separate masks by finding the largest group of masks that fit inside a tile of the given width and height (including the padding), and repeating until no more masks can be combined.

    Pack: ComfyUI-KJNodes
    Returns: MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ConsolidateMasksKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if padding is not _UNSET:
        _kwargs['padding'] = padding
    _kwargs.update(_extras)
    return node(wf, 'ConsolidateMasksKJ', _id, pass_raw=pass_raw, **_kwargs)

def CreateAudioMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    invert: bool | _Omitted = _UNSET,
    frames: int | _Omitted = _UNSET,
    scale: float | _Omitted = _UNSET,
    audio_path: str | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create Audio Mask

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateAudioMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if frames is not _UNSET:
        _kwargs['frames'] = frames
    if scale is not _UNSET:
        _kwargs['scale'] = scale
    if audio_path is not _UNSET:
        _kwargs['audio_path'] = audio_path
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    _kwargs.update(_extras)
    return node(wf, 'CreateAudioMask', _id, pass_raw=pass_raw, **_kwargs)

def CreateFadeMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    invert: bool | _Omitted = _UNSET,
    frames: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out'] | _Omitted = _UNSET,
    start_level: float | _Omitted = _UNSET,
    midpoint_level: float | _Omitted = _UNSET,
    end_level: float | _Omitted = _UNSET,
    midpoint_frame: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create Fade Mask

    Pack: ComfyUI-KJNodes
    Returns: MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateFadeMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if frames is not _UNSET:
        _kwargs['frames'] = frames
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if start_level is not _UNSET:
        _kwargs['start_level'] = start_level
    if midpoint_level is not _UNSET:
        _kwargs['midpoint_level'] = midpoint_level
    if end_level is not _UNSET:
        _kwargs['end_level'] = end_level
    if midpoint_frame is not _UNSET:
        _kwargs['midpoint_frame'] = midpoint_frame
    _kwargs.update(_extras)
    return node(wf, 'CreateFadeMask', _id, pass_raw=pass_raw, **_kwargs)

def CreateFadeMaskAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    points_string: str | _Omitted = _UNSET,
    invert: bool | _Omitted = _UNSET,
    frames: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'none', 'default_to_black'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create a batch of masks interpolated between given frames and values.
    Uses same syntax as Fizz' BatchValueSchedule.
    First value is the frame index (not that this starts from 0, not 1)
    and the second value inside the brackets is the float value of the mask in range 0.0 - 1.0

    For example the default values:
    0:(0.0)
    7:(1.0)
    15:(0.0)

    Would create a mask batch fo 16 frames, starting from black,
    interpolating with the chosen curve to fully white at the 8th frame,
    and interpolating from that to fully black at the 16th frame.

    Pack: ComfyUI-KJNodes
    Returns: MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateFadeMaskAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if points_string is not _UNSET:
        _kwargs['points_string'] = points_string
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if frames is not _UNSET:
        _kwargs['frames'] = frames
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    _kwargs.update(_extras)
    return node(wf, 'CreateFadeMaskAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def CreateFluidMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    invert: bool | _Omitted = _UNSET,
    frames: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    inflow_count: int | _Omitted = _UNSET,
    inflow_velocity: int | _Omitted = _UNSET,
    inflow_radius: int | _Omitted = _UNSET,
    inflow_padding: int | _Omitted = _UNSET,
    inflow_duration: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create Fluid Mask

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateFluidMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if frames is not _UNSET:
        _kwargs['frames'] = frames
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if inflow_count is not _UNSET:
        _kwargs['inflow_count'] = inflow_count
    if inflow_velocity is not _UNSET:
        _kwargs['inflow_velocity'] = inflow_velocity
    if inflow_radius is not _UNSET:
        _kwargs['inflow_radius'] = inflow_radius
    if inflow_padding is not _UNSET:
        _kwargs['inflow_padding'] = inflow_padding
    if inflow_duration is not _UNSET:
        _kwargs['inflow_duration'] = inflow_duration
    _kwargs.update(_extras)
    return node(wf, 'CreateFluidMask', _id, pass_raw=pass_raw, **_kwargs)

def CreateGradientFromCoords(
    *args: VibeWorkflow,
    _id: str | None = None,
    coordinates: str | _Omitted = _UNSET,
    frame_width: int | _Omitted = _UNSET,
    frame_height: int | _Omitted = _UNSET,
    start_color: str | _Omitted = _UNSET,
    end_color: str | _Omitted = _UNSET,
    multiplier: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a gradient image from coordinates.

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateGradientFromCoords() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if frame_width is not _UNSET:
        _kwargs['frame_width'] = frame_width
    if frame_height is not _UNSET:
        _kwargs['frame_height'] = frame_height
    if start_color is not _UNSET:
        _kwargs['start_color'] = start_color
    if end_color is not _UNSET:
        _kwargs['end_color'] = end_color
    if multiplier is not _UNSET:
        _kwargs['multiplier'] = multiplier
    _kwargs.update(_extras)
    return node(wf, 'CreateGradientFromCoords', _id, pass_raw=pass_raw, **_kwargs)

def CreateGradientMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    invert: bool | _Omitted = _UNSET,
    frames: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create Gradient Mask

    Pack: ComfyUI-KJNodes
    Returns: MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateGradientMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if frames is not _UNSET:
        _kwargs['frames'] = frames
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    _kwargs.update(_extras)
    return node(wf, 'CreateGradientMask', _id, pass_raw=pass_raw, **_kwargs)

def CreateInstanceDiffusionTracking(
    *args: VibeWorkflow,
    _id: str | None = None,
    coordinates: str | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    bbox_width: int | _Omitted = _UNSET,
    bbox_height: int | _Omitted = _UNSET,
    class_name: str | _Omitted = _UNSET,
    class_id: int | _Omitted = _UNSET,
    prompt: str | _Omitted = _UNSET,
    size_multiplier: float | _Omitted = _UNSET,
    fit_in_frame: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates tracking data to be used with InstanceDiffusion:
    https://github.com/logtd/ComfyUI-InstanceDiffusion

    InstanceDiffusion prompt format:
    "class_id.class_name": "prompt",
    for example:
    "1.head": "((head))",

    Pack: ComfyUI-KJNodes
    Returns: tracking, prompt, width, height, bbox_width, bbox_height

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateInstanceDiffusionTracking() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if bbox_width is not _UNSET:
        _kwargs['bbox_width'] = bbox_width
    if bbox_height is not _UNSET:
        _kwargs['bbox_height'] = bbox_height
    if class_name is not _UNSET:
        _kwargs['class_name'] = class_name
    if class_id is not _UNSET:
        _kwargs['class_id'] = class_id
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if size_multiplier is not _UNSET:
        _kwargs['size_multiplier'] = size_multiplier
    if fit_in_frame is not _UNSET:
        _kwargs['fit_in_frame'] = fit_in_frame
    _kwargs.update(_extras)
    return node(wf, 'CreateInstanceDiffusionTracking', _id, pass_raw=pass_raw, **_kwargs)

def CreateMagicMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    frames: int | _Omitted = _UNSET,
    depth: int | _Omitted = _UNSET,
    distortion: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    transitions: int | _Omitted = _UNSET,
    frame_width: int | _Omitted = _UNSET,
    frame_height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create Magic Mask

    Pack: ComfyUI-KJNodes
    Returns: mask, mask_inverted

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateMagicMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if frames is not _UNSET:
        _kwargs['frames'] = frames
    if depth is not _UNSET:
        _kwargs['depth'] = depth
    if distortion is not _UNSET:
        _kwargs['distortion'] = distortion
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if transitions is not _UNSET:
        _kwargs['transitions'] = transitions
    if frame_width is not _UNSET:
        _kwargs['frame_width'] = frame_width
    if frame_height is not _UNSET:
        _kwargs['frame_height'] = frame_height
    _kwargs.update(_extras)
    return node(wf, 'CreateMagicMask', _id, pass_raw=pass_raw, **_kwargs)

def CreateShapeImageOnPath(
    *args: VibeWorkflow,
    _id: str | None = None,
    shape: Literal['circle', 'square', 'triangle'] | _Omitted = _UNSET,
    coordinates: str | _Omitted = _UNSET,
    frame_width: int | _Omitted = _UNSET,
    frame_height: int | _Omitted = _UNSET,
    shape_width: int | _Omitted = _UNSET,
    shape_height: int | _Omitted = _UNSET,
    shape_color: str | _Omitted = _UNSET,
    bg_color: str | _Omitted = _UNSET,
    blur_radius: float | _Omitted = _UNSET,
    intensity: float | _Omitted = _UNSET,
    size_multiplier: float | _Omitted = _UNSET,
    trailing: float | _Omitted = _UNSET,
    border_width: int | _Omitted = _UNSET,
    border_color: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates an image or batch of images with the specified shape.
    Locations are center locations.

    Pack: ComfyUI-KJNodes
    Returns: image, mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateShapeImageOnPath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if shape is not _UNSET:
        _kwargs['shape'] = shape
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if frame_width is not _UNSET:
        _kwargs['frame_width'] = frame_width
    if frame_height is not _UNSET:
        _kwargs['frame_height'] = frame_height
    if shape_width is not _UNSET:
        _kwargs['shape_width'] = shape_width
    if shape_height is not _UNSET:
        _kwargs['shape_height'] = shape_height
    if shape_color is not _UNSET:
        _kwargs['shape_color'] = shape_color
    if bg_color is not _UNSET:
        _kwargs['bg_color'] = bg_color
    if blur_radius is not _UNSET:
        _kwargs['blur_radius'] = blur_radius
    if intensity is not _UNSET:
        _kwargs['intensity'] = intensity
    if size_multiplier is not _UNSET:
        _kwargs['size_multiplier'] = size_multiplier
    if trailing is not _UNSET:
        _kwargs['trailing'] = trailing
    if border_width is not _UNSET:
        _kwargs['border_width'] = border_width
    if border_color is not _UNSET:
        _kwargs['border_color'] = border_color
    _kwargs.update(_extras)
    return node(wf, 'CreateShapeImageOnPath', _id, pass_raw=pass_raw, **_kwargs)

def CreateShapeMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    shape: Literal['circle', 'square', 'triangle'] | _Omitted = _UNSET,
    frames: int | _Omitted = _UNSET,
    location_x: int | _Omitted = _UNSET,
    location_y: int | _Omitted = _UNSET,
    grow: int | _Omitted = _UNSET,
    frame_width: int | _Omitted = _UNSET,
    frame_height: int | _Omitted = _UNSET,
    shape_width: int | _Omitted = _UNSET,
    shape_height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a mask or batch of masks with the specified shape.
    Locations are center locations.
    Grow value is the amount to grow the shape on each frame, creating animated masks.

    Pack: ComfyUI-KJNodes
    Returns: mask, mask_inverted

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateShapeMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if shape is not _UNSET:
        _kwargs['shape'] = shape
    if frames is not _UNSET:
        _kwargs['frames'] = frames
    if location_x is not _UNSET:
        _kwargs['location_x'] = location_x
    if location_y is not _UNSET:
        _kwargs['location_y'] = location_y
    if grow is not _UNSET:
        _kwargs['grow'] = grow
    if frame_width is not _UNSET:
        _kwargs['frame_width'] = frame_width
    if frame_height is not _UNSET:
        _kwargs['frame_height'] = frame_height
    if shape_width is not _UNSET:
        _kwargs['shape_width'] = shape_width
    if shape_height is not _UNSET:
        _kwargs['shape_height'] = shape_height
    _kwargs.update(_extras)
    return node(wf, 'CreateShapeMask', _id, pass_raw=pass_raw, **_kwargs)

def CreateShapeMaskOnPath(
    *args: VibeWorkflow,
    _id: str | None = None,
    shape: Literal['circle', 'square', 'triangle'] | _Omitted = _UNSET,
    coordinates: str | _Omitted = _UNSET,
    frame_width: int | _Omitted = _UNSET,
    frame_height: int | _Omitted = _UNSET,
    shape_width: int | _Omitted = _UNSET,
    shape_height: int | _Omitted = _UNSET,
    size_multiplier: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a mask or batch of masks with the specified shape.
    Locations are center locations.

    Pack: ComfyUI-KJNodes
    Returns: mask, mask_inverted

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateShapeMaskOnPath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if shape is not _UNSET:
        _kwargs['shape'] = shape
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if frame_width is not _UNSET:
        _kwargs['frame_width'] = frame_width
    if frame_height is not _UNSET:
        _kwargs['frame_height'] = frame_height
    if shape_width is not _UNSET:
        _kwargs['shape_width'] = shape_width
    if shape_height is not _UNSET:
        _kwargs['shape_height'] = shape_height
    if size_multiplier is not _UNSET:
        _kwargs['size_multiplier'] = size_multiplier
    _kwargs.update(_extras)
    return node(wf, 'CreateShapeMaskOnPath', _id, pass_raw=pass_raw, **_kwargs)

def CreateTextMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    invert: bool | _Omitted = _UNSET,
    frames: int | _Omitted = _UNSET,
    text_x: int | _Omitted = _UNSET,
    text_y: int | _Omitted = _UNSET,
    font_size: int | _Omitted = _UNSET,
    font_color: str | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    font: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    start_rotation: int | _Omitted = _UNSET,
    end_rotation: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a text image and mask.
    Looks for fonts from this folder:
    ComfyUI/custom_nodes/ComfyUI-KJNodes/fonts

    If start_rotation and/or end_rotation are different values,
    creates animation between them.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateTextMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if frames is not _UNSET:
        _kwargs['frames'] = frames
    if text_x is not _UNSET:
        _kwargs['text_x'] = text_x
    if text_y is not _UNSET:
        _kwargs['text_y'] = text_y
    if font_size is not _UNSET:
        _kwargs['font_size'] = font_size
    if font_color is not _UNSET:
        _kwargs['font_color'] = font_color
    if text is not _UNSET:
        _kwargs['text'] = text
    if font is not _UNSET:
        _kwargs['font'] = font
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if start_rotation is not _UNSET:
        _kwargs['start_rotation'] = start_rotation
    if end_rotation is not _UNSET:
        _kwargs['end_rotation'] = end_rotation
    _kwargs.update(_extras)
    return node(wf, 'CreateTextMask', _id, pass_raw=pass_raw, **_kwargs)

def CreateTextOnPath(
    *args: VibeWorkflow,
    _id: str | None = None,
    coordinates: str | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    frame_width: int | _Omitted = _UNSET,
    frame_height: int | _Omitted = _UNSET,
    font: Any | _Omitted = _UNSET,
    font_size: int | _Omitted = _UNSET,
    alignment: Literal['left', 'center', 'right'] | _Omitted = _UNSET,
    text_color: str | _Omitted = _UNSET,
    size_multiplier: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a mask or batch of masks with the specified text.
    Locations are center locations.

    Pack: ComfyUI-KJNodes
    Returns: image, mask, mask_inverted

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateTextOnPath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if text is not _UNSET:
        _kwargs['text'] = text
    if frame_width is not _UNSET:
        _kwargs['frame_width'] = frame_width
    if frame_height is not _UNSET:
        _kwargs['frame_height'] = frame_height
    if font is not _UNSET:
        _kwargs['font'] = font
    if font_size is not _UNSET:
        _kwargs['font_size'] = font_size
    if alignment is not _UNSET:
        _kwargs['alignment'] = alignment
    if text_color is not _UNSET:
        _kwargs['text_color'] = text_color
    if size_multiplier is not _UNSET:
        _kwargs['size_multiplier'] = size_multiplier
    _kwargs.update(_extras)
    return node(wf, 'CreateTextOnPath', _id, pass_raw=pass_raw, **_kwargs)

def CreateVoronoiMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    frames: int | _Omitted = _UNSET,
    num_points: int | _Omitted = _UNSET,
    line_width: int | _Omitted = _UNSET,
    speed: float | _Omitted = _UNSET,
    frame_width: int | _Omitted = _UNSET,
    frame_height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Create Voronoi Mask

    Pack: ComfyUI-KJNodes
    Returns: mask, mask_inverted

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CreateVoronoiMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if frames is not _UNSET:
        _kwargs['frames'] = frames
    if num_points is not _UNSET:
        _kwargs['num_points'] = num_points
    if line_width is not _UNSET:
        _kwargs['line_width'] = line_width
    if speed is not _UNSET:
        _kwargs['speed'] = speed
    if frame_width is not _UNSET:
        _kwargs['frame_width'] = frame_width
    if frame_height is not _UNSET:
        _kwargs['frame_height'] = frame_height
    _kwargs.update(_extras)
    return node(wf, 'CreateVoronoiMask', _id, pass_raw=pass_raw, **_kwargs)

def CrossFadeImages(
    *args: VibeWorkflow,
    _id: str | None = None,
    images_1: Any | _Omitted = _UNSET,
    images_2: Any | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = _UNSET,
    transition_start_index: int | _Omitted = _UNSET,
    transitioning_frames: int | _Omitted = _UNSET,
    start_level: float | _Omitted = _UNSET,
    end_level: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Cross Fade Images

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CrossFadeImages() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images_1 is not _UNSET:
        _kwargs['images_1'] = images_1
    if images_2 is not _UNSET:
        _kwargs['images_2'] = images_2
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if transition_start_index is not _UNSET:
        _kwargs['transition_start_index'] = transition_start_index
    if transitioning_frames is not _UNSET:
        _kwargs['transitioning_frames'] = transitioning_frames
    if start_level is not _UNSET:
        _kwargs['start_level'] = start_level
    if end_level is not _UNSET:
        _kwargs['end_level'] = end_level
    _kwargs.update(_extras)
    return node(wf, 'CrossFadeImages', _id, pass_raw=pass_raw, **_kwargs)

def CrossFadeImagesMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: int | _Omitted = _UNSET,
    image_1: Any | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = _UNSET,
    transitioning_frames: int | _Omitted = _UNSET,
    image_2: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Cross Fade Images Multi

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CrossFadeImagesMulti() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if inputcount is not _UNSET:
        _kwargs['inputcount'] = inputcount
    if image_1 is not _UNSET:
        _kwargs['image_1'] = image_1
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if transitioning_frames is not _UNSET:
        _kwargs['transitioning_frames'] = transitioning_frames
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    _kwargs.update(_extras)
    return node(wf, 'CrossFadeImagesMulti', _id, pass_raw=pass_raw, **_kwargs)

def CustomControlNetWeightsFluxFromList(
    *args: VibeWorkflow,
    _id: str | None = None,
    list_of_floats: float | _Omitted = _UNSET,
    uncond_multiplier: float | _Omitted = _UNSET,
    cn_extras: Any | _Omitted = _UNSET,
    autosize: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates controlnet weights from a list of floats for Advanced-ControlNet

    Pack: ComfyUI-KJNodes
    Returns: CN_WEIGHTS, TK_SHORTCUT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CustomControlNetWeightsFluxFromList() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if list_of_floats is not _UNSET:
        _kwargs['list_of_floats'] = list_of_floats
    if uncond_multiplier is not _UNSET:
        _kwargs['uncond_multiplier'] = uncond_multiplier
    if cn_extras is not _UNSET:
        _kwargs['cn_extras'] = cn_extras
    if autosize is not _UNSET:
        _kwargs['autosize'] = autosize
    _kwargs.update(_extras)
    return node(wf, 'CustomControlNetWeightsFluxFromList', _id, pass_raw=pass_raw, **_kwargs)

def CustomSigmas(
    *args: VibeWorkflow,
    _id: str | None = None,
    sigmas_string: str | _Omitted = _UNSET,
    interpolate_to_steps: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a sigmas tensor from a string of comma separated values.
    Examples:

    Nvidia's optimized AYS 10 step schedule for SD 1.5:
    14.615, 6.475, 3.861, 2.697, 1.886, 1.396, 0.963, 0.652, 0.399, 0.152, 0.029
    SDXL:
    14.615, 6.315, 3.771, 2.181, 1.342, 0.862, 0.555, 0.380, 0.234, 0.113, 0.029
    SVD:
    700.00, 54.5, 15.886, 7.977, 4.248, 1.789, 0.981, 0.403, 0.173, 0.034, 0.002

    Pack: ComfyUI-KJNodes
    Returns: SIGMAS

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CustomSigmas() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if sigmas_string is not _UNSET:
        _kwargs['sigmas_string'] = sigmas_string
    if interpolate_to_steps is not _UNSET:
        _kwargs['interpolate_to_steps'] = interpolate_to_steps
    _kwargs.update(_extras)
    return node(wf, 'CustomSigmas', _id, pass_raw=pass_raw, **_kwargs)

def CutAndDragOnPath(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    coordinates: str | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    frame_width: int | _Omitted = _UNSET,
    frame_height: int | _Omitted = _UNSET,
    inpaint: bool | _Omitted = _UNSET,
    bg_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Cuts the masked area from the image, and drags it along the path. If inpaint is enabled, and no bg_image is provided, the cut area is filled using cv2 TELEA algorithm.

    Pack: ComfyUI-KJNodes
    Returns: image, mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"CutAndDragOnPath() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if frame_width is not _UNSET:
        _kwargs['frame_width'] = frame_width
    if frame_height is not _UNSET:
        _kwargs['frame_height'] = frame_height
    if inpaint is not _UNSET:
        _kwargs['inpaint'] = inpaint
    if bg_image is not _UNSET:
        _kwargs['bg_image'] = bg_image
    _kwargs.update(_extras)
    return node(wf, 'CutAndDragOnPath', _id, pass_raw=pass_raw, **_kwargs)

def DecodeAndSaveVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    video_latent: Any | _Omitted = _UNSET,
    fps: float | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    format: Any | _Omitted = _UNSET,
    codec: Any | _Omitted = _UNSET,
    video_vae: Any | _Omitted = _UNSET,
    tiling: Any | _Omitted = _UNSET,
    audio_latent: Any | _Omitted = _UNSET,
    audio_vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Decodes video frames and audio from latent representations, combines them, and saves as a video file, without keeping intermediate images in memory.

    Pack: ComfyUI-KJNodes
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DecodeAndSaveVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video_latent is not _UNSET:
        _kwargs['video_latent'] = video_latent
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    if format is not _UNSET:
        _kwargs['format'] = format
    if codec is not _UNSET:
        _kwargs['codec'] = codec
    if video_vae is not _UNSET:
        _kwargs['video_vae'] = video_vae
    if tiling is not _UNSET:
        _kwargs['tiling'] = tiling
    if audio_latent is not _UNSET:
        _kwargs['audio_latent'] = audio_latent
    if audio_vae is not _UNSET:
        _kwargs['audio_vae'] = audio_vae
    _kwargs.update(_extras)
    return node(wf, 'DecodeAndSaveVideo', _id, pass_raw=pass_raw, **_kwargs)

def DiTBlockLoraLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    strength_model: float | _Omitted = _UNSET,
    lora_name: Literal['ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    opt_lora_path: str | _Omitted = _UNSET,
    blocks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    DiT Block Lora Loader

    Pack: ComfyUI-KJNodes
    Returns: model, rank

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DiTBlockLoraLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if strength_model is not _UNSET:
        _kwargs['strength_model'] = strength_model
    if lora_name is not _UNSET:
        _kwargs['lora_name'] = lora_name
    if opt_lora_path is not _UNSET:
        _kwargs['opt_lora_path'] = opt_lora_path
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    _kwargs.update(_extras)
    return node(wf, 'DiTBlockLoraLoader', _id, pass_raw=pass_raw, **_kwargs)

def DifferentialDiffusionAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    samples: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    multiplier: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Differential Diffusion Advanced

    Pack: ComfyUI-KJNodes
    Returns: MODEL, LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DifferentialDiffusionAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if multiplier is not _UNSET:
        _kwargs['multiplier'] = multiplier
    _kwargs.update(_extras)
    return node(wf, 'DifferentialDiffusionAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def DiffusionModelLoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    weight_dtype: Literal['default', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp16', 'bf16', 'fp32'] | _Omitted = _UNSET,
    compute_dtype: Literal['default', 'fp16', 'bf16', 'fp32'] | _Omitted = _UNSET,
    patch_cublaslinear: bool | _Omitted = _UNSET,
    sage_attention: Literal['disabled', 'auto', 'sageattn_qk_int8_pv_fp16_cuda', 'sageattn_qk_int8_pv_fp16_triton', 'sageattn_qk_int8_pv_fp8_cuda', 'sageattn_qk_int8_pv_fp8_cuda++', 'sageattn3', 'sageattn3_per_block_mean'] | _Omitted = _UNSET,
    enable_fp16_accumulation: bool | _Omitted = _UNSET,
    extra_state_dict: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Node for patching torch.nn.Linear with CublasLinear.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DiffusionModelLoaderKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if weight_dtype is not _UNSET:
        _kwargs['weight_dtype'] = weight_dtype
    if compute_dtype is not _UNSET:
        _kwargs['compute_dtype'] = compute_dtype
    if patch_cublaslinear is not _UNSET:
        _kwargs['patch_cublaslinear'] = patch_cublaslinear
    if sage_attention is not _UNSET:
        _kwargs['sage_attention'] = sage_attention
    if enable_fp16_accumulation is not _UNSET:
        _kwargs['enable_fp16_accumulation'] = enable_fp16_accumulation
    if extra_state_dict is not _UNSET:
        _kwargs['extra_state_dict'] = extra_state_dict
    _kwargs.update(_extras)
    return node(wf, 'DiffusionModelLoaderKJ', _id, pass_raw=pass_raw, **_kwargs)

def DiffusionModelSelector(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns the path to the model as a string.

    Pack: ComfyUI-KJNodes
    Returns: model_path

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DiffusionModelSelector() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    _kwargs.update(_extras)
    return node(wf, 'DiffusionModelSelector', _id, pass_raw=pass_raw, **_kwargs)

def DownloadAndLoadCLIPSeg(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['Kijai/clipseg-rd64-refined-fp16', 'CIDAS/clipseg-rd64-refined'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Downloads and loads CLIPSeg model with huggingface_hub,
    to ComfyUI/models/clip_seg

    Pack: ComfyUI-KJNodes
    Returns: clipseg_model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadCLIPSeg() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadCLIPSeg', _id, pass_raw=pass_raw, **_kwargs)

def DrawInstanceDiffusionTracking(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    tracking: Any | _Omitted = _UNSET,
    box_line_width: int | _Omitted = _UNSET,
    draw_text: bool | _Omitted = _UNSET,
    font: Any | _Omitted = _UNSET,
    font_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Draws the tracking data from
    CreateInstanceDiffusionTracking -node.

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DrawInstanceDiffusionTracking() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if tracking is not _UNSET:
        _kwargs['tracking'] = tracking
    if box_line_width is not _UNSET:
        _kwargs['box_line_width'] = box_line_width
    if draw_text is not _UNSET:
        _kwargs['draw_text'] = draw_text
    if font is not _UNSET:
        _kwargs['font'] = font
    if font_size is not _UNSET:
        _kwargs['font_size'] = font_size
    _kwargs.update(_extras)
    return node(wf, 'DrawInstanceDiffusionTracking', _id, pass_raw=pass_raw, **_kwargs)

def DrawMaskOnImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    color: str | _Omitted = _UNSET,
    device: Literal['cpu', 'gpu'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Applies the provided masks to the input images with Alpha Blending support.

    Pack: ComfyUI-KJNodes
    Returns: images

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DrawMaskOnImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if color is not _UNSET:
        _kwargs['color'] = color
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'DrawMaskOnImage', _id, pass_raw=pass_raw, **_kwargs)

def DummyOut(
    *args: VibeWorkflow,
    _id: str | None = None,
    any_input: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Does nothing, used to trigger generic workflow output.
    A way to get previews in the UI without saving anything to disk.

    Pack: ComfyUI-KJNodes
    Returns: *

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"DummyOut() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if any_input is not _UNSET:
        _kwargs['any_input'] = any_input
    _kwargs.update(_extras)
    return node(wf, 'DummyOut', _id, pass_raw=pass_raw, **_kwargs)

def EmptyLatentImageCustomPresets(
    *args: VibeWorkflow,
    _id: str | None = None,
    dimensions: Any | _Omitted = _UNSET,
    invert: bool | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Generates an empty latent image with the specified dimensions.
    The choices are loaded from 'custom_dimensions.json' in the nodes folder.

    Pack: ComfyUI-KJNodes
    Returns: Latent, Width, Height

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EmptyLatentImageCustomPresets() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if dimensions is not _UNSET:
        _kwargs['dimensions'] = dimensions
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyLatentImageCustomPresets', _id, pass_raw=pass_raw, **_kwargs)

def EmptyLatentImagePresets(
    *args: VibeWorkflow,
    _id: str | None = None,
    dimensions: Literal['512 x 512 (1:1)', '768 x 512 (1.5:1)', '960 x 512 (1.875:1)', '1024 x 512 (2:1)', '1024 x 576 (1.778:1)', '1536 x 640 (2.4:1)', '1344 x 768 (1.75:1)', '1216 x 832 (1.46:1)', '1152 x 896 (1.286:1)', '1024 x 1024 (1:1)'] | _Omitted = _UNSET,
    invert: bool | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Empty Latent Image Presets

    Pack: ComfyUI-KJNodes
    Returns: Latent, Width, Height

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EmptyLatentImagePresets() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if dimensions is not _UNSET:
        _kwargs['dimensions'] = dimensions
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'EmptyLatentImagePresets', _id, pass_raw=pass_raw, **_kwargs)

def EncodeVideoComponents(
    *args: VibeWorkflow,
    _id: str | None = None,
    video: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    max_frames: int | _Omitted = _UNSET,
    upscale_method: Any | _Omitted = _UNSET,
    keep_proportion: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Extracts video frames, resizes them, and encodes with a VAE directly, avoiding storing the full image tensor.

    Pack: ComfyUI-KJNodes
    Returns: latent, audio, fps, frame_count

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EncodeVideoComponents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video is not _UNSET:
        _kwargs['video'] = video
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if max_frames is not _UNSET:
        _kwargs['max_frames'] = max_frames
    if upscale_method is not _UNSET:
        _kwargs['upscale_method'] = upscale_method
    if keep_proportion is not _UNSET:
        _kwargs['keep_proportion'] = keep_proportion
    _kwargs.update(_extras)
    return node(wf, 'EncodeVideoComponents', _id, pass_raw=pass_raw, **_kwargs)

def EndRecordCUDAMemoryHistory(
    *args: VibeWorkflow,
    _id: str | None = None,
    input: Any | _Omitted = _UNSET,
    output_path: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Records CUDA memory allocation history between start and end, saves to a file that can be analyzed here: https://docs.pytorch.org/memory_viz or with VisualizeCUDAMemoryHistory node

    Pack: ComfyUI-KJNodes
    Returns: input, output_path

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"EndRecordCUDAMemoryHistory() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input is not _UNSET:
        _kwargs['input'] = input
    if output_path is not _UNSET:
        _kwargs['output_path'] = output_path
    _kwargs.update(_extras)
    return node(wf, 'EndRecordCUDAMemoryHistory', _id, pass_raw=pass_raw, **_kwargs)

def FastPreview(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    format: Literal['JPEG', 'PNG'] | _Omitted = _UNSET,
    max_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Fast image preview using binary websocket, bypassing base64/JSON overhead.

    Pack: ComfyUI-KJNodes
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"FastPreview() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if format is not _UNSET:
        _kwargs['format'] = format
    if max_size is not _UNSET:
        _kwargs['max_size'] = max_size
    _kwargs.update(_extras)
    return node(wf, 'FastPreview', _id, pass_raw=pass_raw, **_kwargs)

def FilterZeroMasksAndCorrespondingImages(
    *args: VibeWorkflow,
    _id: str | None = None,
    masks: Any | _Omitted = _UNSET,
    original_images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Filter out all the empty (i.e. all zero) mask in masks
    Also filter out all the corresponding images in original_images by indexes if provide

    original_images (optional): If provided, need have same length as masks.

    Pack: ComfyUI-KJNodes
    Returns: non_zero_masks_out, non_zero_mask_images_out, zero_mask_images_out, zero_mask_images_out_indexes

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"FilterZeroMasksAndCorrespondingImages() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    if original_images is not _UNSET:
        _kwargs['original_images'] = original_images
    _kwargs.update(_extras)
    return node(wf, 'FilterZeroMasksAndCorrespondingImages', _id, pass_raw=pass_raw, **_kwargs)

def FlipSigmasAdjusted(
    *args: VibeWorkflow,
    _id: str | None = None,
    sigmas: Any | _Omitted = _UNSET,
    divide_by_last_sigma: bool | _Omitted = _UNSET,
    divide_by: float | _Omitted = _UNSET,
    offset_by: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Flip Sigmas Adjusted

    Pack: ComfyUI-KJNodes
    Returns: SIGMAS, sigmas_string

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"FlipSigmasAdjusted() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if divide_by_last_sigma is not _UNSET:
        _kwargs['divide_by_last_sigma'] = divide_by_last_sigma
    if divide_by is not _UNSET:
        _kwargs['divide_by'] = divide_by
    if offset_by is not _UNSET:
        _kwargs['offset_by'] = offset_by
    _kwargs.update(_extras)
    return node(wf, 'FlipSigmasAdjusted', _id, pass_raw=pass_raw, **_kwargs)

def FloatConstant(
    *args: VibeWorkflow,
    _id: str | None = None,
    value: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Float Constant

    Pack: ComfyUI-KJNodes
    Returns: value

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"FloatConstant() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if value is not _UNSET:
        _kwargs['value'] = value
    _kwargs.update(_extras)
    return node(wf, 'FloatConstant', _id, pass_raw=pass_raw, **_kwargs)

def FloatToMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    input_values: float | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Generates a batch of masks based on the input float values.
    The batch size is determined by the length of the input float values.
    Each mask is generated with the specified width and height.

    Pack: ComfyUI-KJNodes
    Returns: MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"FloatToMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input_values is not _UNSET:
        _kwargs['input_values'] = input_values
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    _kwargs.update(_extras)
    return node(wf, 'FloatToMask', _id, pass_raw=pass_raw, **_kwargs)

def FloatToSigmas(
    *args: VibeWorkflow,
    _id: str | None = None,
    float_list: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a sigmas tensor from list of float values.

    Pack: ComfyUI-KJNodes
    Returns: SIGMAS

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"FloatToSigmas() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if float_list is not _UNSET:
        _kwargs['float_list'] = float_list
    _kwargs.update(_extras)
    return node(wf, 'FloatToSigmas', _id, pass_raw=pass_raw, **_kwargs)

def FluxBlockLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = None,
    double_blocks_0: float | _Omitted = _UNSET,
    double_blocks_1: float | _Omitted = _UNSET,
    double_blocks_2: float | _Omitted = _UNSET,
    double_blocks_3: float | _Omitted = _UNSET,
    double_blocks_4: float | _Omitted = _UNSET,
    double_blocks_5: float | _Omitted = _UNSET,
    double_blocks_6: float | _Omitted = _UNSET,
    double_blocks_7: float | _Omitted = _UNSET,
    double_blocks_8: float | _Omitted = _UNSET,
    double_blocks_9: float | _Omitted = _UNSET,
    double_blocks_10: float | _Omitted = _UNSET,
    double_blocks_11: float | _Omitted = _UNSET,
    double_blocks_12: float | _Omitted = _UNSET,
    double_blocks_13: float | _Omitted = _UNSET,
    double_blocks_14: float | _Omitted = _UNSET,
    double_blocks_15: float | _Omitted = _UNSET,
    double_blocks_16: float | _Omitted = _UNSET,
    double_blocks_17: float | _Omitted = _UNSET,
    double_blocks_18: float | _Omitted = _UNSET,
    single_blocks_0: float | _Omitted = _UNSET,
    single_blocks_1: float | _Omitted = _UNSET,
    single_blocks_2: float | _Omitted = _UNSET,
    single_blocks_3: float | _Omitted = _UNSET,
    single_blocks_4: float | _Omitted = _UNSET,
    single_blocks_5: float | _Omitted = _UNSET,
    single_blocks_6: float | _Omitted = _UNSET,
    single_blocks_7: float | _Omitted = _UNSET,
    single_blocks_8: float | _Omitted = _UNSET,
    single_blocks_9: float | _Omitted = _UNSET,
    single_blocks_10: float | _Omitted = _UNSET,
    single_blocks_11: float | _Omitted = _UNSET,
    single_blocks_12: float | _Omitted = _UNSET,
    single_blocks_13: float | _Omitted = _UNSET,
    single_blocks_14: float | _Omitted = _UNSET,
    single_blocks_15: float | _Omitted = _UNSET,
    single_blocks_16: float | _Omitted = _UNSET,
    single_blocks_17: float | _Omitted = _UNSET,
    single_blocks_18: float | _Omitted = _UNSET,
    single_blocks_19: float | _Omitted = _UNSET,
    single_blocks_20: float | _Omitted = _UNSET,
    single_blocks_21: float | _Omitted = _UNSET,
    single_blocks_22: float | _Omitted = _UNSET,
    single_blocks_23: float | _Omitted = _UNSET,
    single_blocks_24: float | _Omitted = _UNSET,
    single_blocks_25: float | _Omitted = _UNSET,
    single_blocks_26: float | _Omitted = _UNSET,
    single_blocks_27: float | _Omitted = _UNSET,
    single_blocks_28: float | _Omitted = _UNSET,
    single_blocks_29: float | _Omitted = _UNSET,
    single_blocks_30: float | _Omitted = _UNSET,
    single_blocks_31: float | _Omitted = _UNSET,
    single_blocks_32: float | _Omitted = _UNSET,
    single_blocks_33: float | _Omitted = _UNSET,
    single_blocks_34: float | _Omitted = _UNSET,
    single_blocks_35: float | _Omitted = _UNSET,
    single_blocks_36: float | _Omitted = _UNSET,
    single_blocks_37: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select individual block alpha values, value of 0 removes the block altogether

    Pack: ComfyUI-KJNodes
    Returns: blocks

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"FluxBlockLoraSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if double_blocks_0 is not _UNSET:
        _kwargs['double_blocks.0.'] = double_blocks_0
    if double_blocks_1 is not _UNSET:
        _kwargs['double_blocks.1.'] = double_blocks_1
    if double_blocks_2 is not _UNSET:
        _kwargs['double_blocks.2.'] = double_blocks_2
    if double_blocks_3 is not _UNSET:
        _kwargs['double_blocks.3.'] = double_blocks_3
    if double_blocks_4 is not _UNSET:
        _kwargs['double_blocks.4.'] = double_blocks_4
    if double_blocks_5 is not _UNSET:
        _kwargs['double_blocks.5.'] = double_blocks_5
    if double_blocks_6 is not _UNSET:
        _kwargs['double_blocks.6.'] = double_blocks_6
    if double_blocks_7 is not _UNSET:
        _kwargs['double_blocks.7.'] = double_blocks_7
    if double_blocks_8 is not _UNSET:
        _kwargs['double_blocks.8.'] = double_blocks_8
    if double_blocks_9 is not _UNSET:
        _kwargs['double_blocks.9.'] = double_blocks_9
    if double_blocks_10 is not _UNSET:
        _kwargs['double_blocks.10.'] = double_blocks_10
    if double_blocks_11 is not _UNSET:
        _kwargs['double_blocks.11.'] = double_blocks_11
    if double_blocks_12 is not _UNSET:
        _kwargs['double_blocks.12.'] = double_blocks_12
    if double_blocks_13 is not _UNSET:
        _kwargs['double_blocks.13.'] = double_blocks_13
    if double_blocks_14 is not _UNSET:
        _kwargs['double_blocks.14.'] = double_blocks_14
    if double_blocks_15 is not _UNSET:
        _kwargs['double_blocks.15.'] = double_blocks_15
    if double_blocks_16 is not _UNSET:
        _kwargs['double_blocks.16.'] = double_blocks_16
    if double_blocks_17 is not _UNSET:
        _kwargs['double_blocks.17.'] = double_blocks_17
    if double_blocks_18 is not _UNSET:
        _kwargs['double_blocks.18.'] = double_blocks_18
    if single_blocks_0 is not _UNSET:
        _kwargs['single_blocks.0.'] = single_blocks_0
    if single_blocks_1 is not _UNSET:
        _kwargs['single_blocks.1.'] = single_blocks_1
    if single_blocks_2 is not _UNSET:
        _kwargs['single_blocks.2.'] = single_blocks_2
    if single_blocks_3 is not _UNSET:
        _kwargs['single_blocks.3.'] = single_blocks_3
    if single_blocks_4 is not _UNSET:
        _kwargs['single_blocks.4.'] = single_blocks_4
    if single_blocks_5 is not _UNSET:
        _kwargs['single_blocks.5.'] = single_blocks_5
    if single_blocks_6 is not _UNSET:
        _kwargs['single_blocks.6.'] = single_blocks_6
    if single_blocks_7 is not _UNSET:
        _kwargs['single_blocks.7.'] = single_blocks_7
    if single_blocks_8 is not _UNSET:
        _kwargs['single_blocks.8.'] = single_blocks_8
    if single_blocks_9 is not _UNSET:
        _kwargs['single_blocks.9.'] = single_blocks_9
    if single_blocks_10 is not _UNSET:
        _kwargs['single_blocks.10.'] = single_blocks_10
    if single_blocks_11 is not _UNSET:
        _kwargs['single_blocks.11.'] = single_blocks_11
    if single_blocks_12 is not _UNSET:
        _kwargs['single_blocks.12.'] = single_blocks_12
    if single_blocks_13 is not _UNSET:
        _kwargs['single_blocks.13.'] = single_blocks_13
    if single_blocks_14 is not _UNSET:
        _kwargs['single_blocks.14.'] = single_blocks_14
    if single_blocks_15 is not _UNSET:
        _kwargs['single_blocks.15.'] = single_blocks_15
    if single_blocks_16 is not _UNSET:
        _kwargs['single_blocks.16.'] = single_blocks_16
    if single_blocks_17 is not _UNSET:
        _kwargs['single_blocks.17.'] = single_blocks_17
    if single_blocks_18 is not _UNSET:
        _kwargs['single_blocks.18.'] = single_blocks_18
    if single_blocks_19 is not _UNSET:
        _kwargs['single_blocks.19.'] = single_blocks_19
    if single_blocks_20 is not _UNSET:
        _kwargs['single_blocks.20.'] = single_blocks_20
    if single_blocks_21 is not _UNSET:
        _kwargs['single_blocks.21.'] = single_blocks_21
    if single_blocks_22 is not _UNSET:
        _kwargs['single_blocks.22.'] = single_blocks_22
    if single_blocks_23 is not _UNSET:
        _kwargs['single_blocks.23.'] = single_blocks_23
    if single_blocks_24 is not _UNSET:
        _kwargs['single_blocks.24.'] = single_blocks_24
    if single_blocks_25 is not _UNSET:
        _kwargs['single_blocks.25.'] = single_blocks_25
    if single_blocks_26 is not _UNSET:
        _kwargs['single_blocks.26.'] = single_blocks_26
    if single_blocks_27 is not _UNSET:
        _kwargs['single_blocks.27.'] = single_blocks_27
    if single_blocks_28 is not _UNSET:
        _kwargs['single_blocks.28.'] = single_blocks_28
    if single_blocks_29 is not _UNSET:
        _kwargs['single_blocks.29.'] = single_blocks_29
    if single_blocks_30 is not _UNSET:
        _kwargs['single_blocks.30.'] = single_blocks_30
    if single_blocks_31 is not _UNSET:
        _kwargs['single_blocks.31.'] = single_blocks_31
    if single_blocks_32 is not _UNSET:
        _kwargs['single_blocks.32.'] = single_blocks_32
    if single_blocks_33 is not _UNSET:
        _kwargs['single_blocks.33.'] = single_blocks_33
    if single_blocks_34 is not _UNSET:
        _kwargs['single_blocks.34.'] = single_blocks_34
    if single_blocks_35 is not _UNSET:
        _kwargs['single_blocks.35.'] = single_blocks_35
    if single_blocks_36 is not _UNSET:
        _kwargs['single_blocks.36.'] = single_blocks_36
    if single_blocks_37 is not _UNSET:
        _kwargs['single_blocks.37.'] = single_blocks_37
    _kwargs.update(_extras)
    return node(wf, 'FluxBlockLoraSelect', _id, pass_raw=pass_raw, **_kwargs)

def GGUFLoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Any | _Omitted = _UNSET,
    extra_model_name: Any | _Omitted = _UNSET,
    dequant_dtype: Any | _Omitted = _UNSET,
    patch_dtype: Any | _Omitted = _UNSET,
    patch_on_device: bool | _Omitted = _UNSET,
    enable_fp16_accumulation: bool | _Omitted = _UNSET,
    attention_override: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads a GGUF model with advanced options, requires [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) to be installed.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GGUFLoaderKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if extra_model_name is not _UNSET:
        _kwargs['extra_model_name'] = extra_model_name
    if dequant_dtype is not _UNSET:
        _kwargs['dequant_dtype'] = dequant_dtype
    if patch_dtype is not _UNSET:
        _kwargs['patch_dtype'] = patch_dtype
    if patch_on_device is not _UNSET:
        _kwargs['patch_on_device'] = patch_on_device
    if enable_fp16_accumulation is not _UNSET:
        _kwargs['enable_fp16_accumulation'] = enable_fp16_accumulation
    if attention_override is not _UNSET:
        _kwargs['attention_override'] = attention_override
    _kwargs.update(_extras)
    return node(wf, 'GGUFLoaderKJ', _id, pass_raw=pass_raw, **_kwargs)

def GLIGENTextBoxApplyBatchCoords(
    *args: VibeWorkflow,
    _id: str | None = None,
    conditioning_to: Any | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    clip: Any | _Omitted = _UNSET,
    gligen_textbox_model: Any | _Omitted = _UNSET,
    coordinates: str | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    size_multiplier: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node allows scheduling GLIGEN text box positions in a batch,
    to be used with AnimateDiff-Evolved. Intended to pair with the
    Spline Editor -node.

    GLIGEN model can be downloaded through the Manage's "Install Models" menu.
    Or directly from here:
    https://huggingface.co/comfyanonymous/GLIGEN_pruned_safetensors/tree/main

    Inputs:
    - **latents** input is used to calculate batch size
    - **clip** is your standard text encoder, use same as for the main prompt
    - **gligen_textbox_model** connects to GLIGEN Loader
    - **coordinates** takes a json string of points, directly compatible
    with the spline editor node.
    - **text** is the part of the prompt to set position for
    - **width** and **height** are the size of the GLIGEN bounding box

    Outputs:
    - **conditioning** goes between to clip text encode and the sampler
    - **coord_preview** is an optional preview of the coordinates and
    bounding boxes.

    Pack: ComfyUI-KJNodes
    Returns: conditioning, coord_preview

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GLIGENTextBoxApplyBatchCoords() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if conditioning_to is not _UNSET:
        _kwargs['conditioning_to'] = conditioning_to
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if gligen_textbox_model is not _UNSET:
        _kwargs['gligen_textbox_model'] = gligen_textbox_model
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if text is not _UNSET:
        _kwargs['text'] = text
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if size_multiplier is not _UNSET:
        _kwargs['size_multiplier'] = size_multiplier
    _kwargs.update(_extras)
    return node(wf, 'GLIGENTextBoxApplyBatchCoords', _id, pass_raw=pass_raw, **_kwargs)

def GenerateNoise(
    *args: VibeWorkflow,
    _id: str | None = None,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    multiplier: float | _Omitted = _UNSET,
    constant_batch_noise: bool | _Omitted = _UNSET,
    normalize: bool | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    latent_channels: Literal['4', '16'] | _Omitted = _UNSET,
    shape: Literal['BCHW', 'BCTHW', 'BTCHW'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Generates noise for injection or to be used as empty latents on samplers with add_noise off.

    Pack: ComfyUI-KJNodes
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GenerateNoise() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if multiplier is not _UNSET:
        _kwargs['multiplier'] = multiplier
    if constant_batch_noise is not _UNSET:
        _kwargs['constant_batch_noise'] = constant_batch_noise
    if normalize is not _UNSET:
        _kwargs['normalize'] = normalize
    if model is not _UNSET:
        _kwargs['model'] = model
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if latent_channels is not _UNSET:
        _kwargs['latent_channels'] = latent_channels
    if shape is not _UNSET:
        _kwargs['shape'] = shape
    _kwargs.update(_extras)
    return node(wf, 'GenerateNoise', _id, pass_raw=pass_raw, **_kwargs)

def GetImageSizeAndCount(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns width, height and batch size of the image,
    and passes it through unchanged.

    Pack: ComfyUI-KJNodes
    Returns: image, width, height, count

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetImageSizeAndCount() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'GetImageSizeAndCount', _id, pass_raw=pass_raw, **_kwargs)

def GetImagesFromBatchIndexed(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    indexes: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Selects and returns the images at the specified indices as an image batch.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetImagesFromBatchIndexed() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if indexes is not _UNSET:
        _kwargs['indexes'] = indexes
    _kwargs.update(_extras)
    return node(wf, 'GetImagesFromBatchIndexed', _id, pass_raw=pass_raw, **_kwargs)

def GetLatentRangeFromBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    start_index: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns a range of latents from a batch.

    Pack: ComfyUI-KJNodes
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetLatentRangeFromBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    _kwargs.update(_extras)
    return node(wf, 'GetLatentRangeFromBatch', _id, pass_raw=pass_raw, **_kwargs)

def GetLatentSizeAndCount(
    *args: VibeWorkflow,
    _id: str | None = None,
    latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns latent tensor dimensions,
    and passes the latent through unchanged.

    Pack: ComfyUI-KJNodes
    Returns: latent, batch_size, channels, frames, height, width

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetLatentSizeAndCount() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    _kwargs.update(_extras)
    return node(wf, 'GetLatentSizeAndCount', _id, pass_raw=pass_raw, **_kwargs)

def GetLatentsFromBatchIndexed(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    indexes: str | _Omitted = _UNSET,
    latent_format: Literal['BCHW', 'BTCHW', 'BCTHW'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Selects and returns the latents at the specified indices as an latent batch.

    Pack: ComfyUI-KJNodes
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetLatentsFromBatchIndexed() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if indexes is not _UNSET:
        _kwargs['indexes'] = indexes
    if latent_format is not _UNSET:
        _kwargs['latent_format'] = latent_format
    _kwargs.update(_extras)
    return node(wf, 'GetLatentsFromBatchIndexed', _id, pass_raw=pass_raw, **_kwargs)

def GetMaskSizeAndCount(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns the width, height and batch size of the mask,
    and passes it through unchanged.

    Pack: ComfyUI-KJNodes
    Returns: mask, width, height, count

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetMaskSizeAndCount() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'GetMaskSizeAndCount', _id, pass_raw=pass_raw, **_kwargs)

def GetTrackRange(
    *args: VibeWorkflow,
    _id: str | None = None,
    tracks: Any | _Omitted = _UNSET,
    start_index: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: ComfyUI-KJNodes
    Returns: TRACKS

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GetTrackRange() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    _kwargs.update(_extras)
    return node(wf, 'GetTrackRange', _id, pass_raw=pass_raw, **_kwargs)

def GradientToFloat(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Calculates list of floats from image.

    Pack: ComfyUI-KJNodes
    Returns: float_x, float_y

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GradientToFloat() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    _kwargs.update(_extras)
    return node(wf, 'GradientToFloat', _id, pass_raw=pass_raw, **_kwargs)

def GrowMaskWithBlur(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    expand: int | _Omitted = _UNSET,
    incremental_expandrate: float | _Omitted = _UNSET,
    tapered_corners: bool | _Omitted = _UNSET,
    flip_input: bool | _Omitted = _UNSET,
    blur_radius: float | _Omitted = _UNSET,
    lerp_alpha: float | _Omitted = _UNSET,
    decay_factor: float | _Omitted = _UNSET,
    fill_holes: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    # GrowMaskWithBlur
    - mask: Input mask or mask batch
    - expand: Expand or contract mask or mask batch by a given amount
    - incremental_expandrate: increase expand rate by a given amount per frame
    - tapered_corners: use tapered corners
    - flip_input: flip input mask
    - blur_radius: value higher than 0 will blur the mask
    - lerp_alpha: alpha value for interpolation between frames
    - decay_factor: decay value for interpolation between frames
    - fill_holes: fill holes in the mask (slow)

    Pack: ComfyUI-KJNodes
    Returns: mask, mask_inverted

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"GrowMaskWithBlur() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if expand is not _UNSET:
        _kwargs['expand'] = expand
    if incremental_expandrate is not _UNSET:
        _kwargs['incremental_expandrate'] = incremental_expandrate
    if tapered_corners is not _UNSET:
        _kwargs['tapered_corners'] = tapered_corners
    if flip_input is not _UNSET:
        _kwargs['flip_input'] = flip_input
    if blur_radius is not _UNSET:
        _kwargs['blur_radius'] = blur_radius
    if lerp_alpha is not _UNSET:
        _kwargs['lerp_alpha'] = lerp_alpha
    if decay_factor is not _UNSET:
        _kwargs['decay_factor'] = decay_factor
    if fill_holes is not _UNSET:
        _kwargs['fill_holes'] = fill_holes
    _kwargs.update(_extras)
    return node(wf, 'GrowMaskWithBlur', _id, pass_raw=pass_raw, **_kwargs)

def HDRPreviewKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    exposure: float | _Omitted = _UNSET,
    saturation: float | _Omitted = _UNSET,
    fps: float | _Omitted = _UNSET,
    input_space: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Realtime-exposure preview for HDR-compressed images.

    Input: LogC3-compressed [0,1] image/video batch (e.g. the VAE-decoded output of an HDR IC-LoRA workflow, prior to HDR decompression).

    Decompression + exposure + saturation + Reinhard tonemap + sRGB runs in a WebGL fragment shader in the browser for realtime slider feedback, and the same math runs server-side to produce the baked sRGB IMAGE output. Slider changes update the preview immediately; the IMAGE output only updates when the workflow is re-queued.

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"HDRPreviewKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if exposure is not _UNSET:
        _kwargs['exposure'] = exposure
    if saturation is not _UNSET:
        _kwargs['saturation'] = saturation
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    if input_space is not _UNSET:
        _kwargs['input_space'] = input_space
    _kwargs.update(_extras)
    return node(wf, 'HDRPreviewKJ', _id, pass_raw=pass_raw, **_kwargs)

def HunyuanVideoBlockLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = None,
    double_blocks_0: float | _Omitted = _UNSET,
    double_blocks_1: float | _Omitted = _UNSET,
    double_blocks_2: float | _Omitted = _UNSET,
    double_blocks_3: float | _Omitted = _UNSET,
    double_blocks_4: float | _Omitted = _UNSET,
    double_blocks_5: float | _Omitted = _UNSET,
    double_blocks_6: float | _Omitted = _UNSET,
    double_blocks_7: float | _Omitted = _UNSET,
    double_blocks_8: float | _Omitted = _UNSET,
    double_blocks_9: float | _Omitted = _UNSET,
    double_blocks_10: float | _Omitted = _UNSET,
    double_blocks_11: float | _Omitted = _UNSET,
    double_blocks_12: float | _Omitted = _UNSET,
    double_blocks_13: float | _Omitted = _UNSET,
    double_blocks_14: float | _Omitted = _UNSET,
    double_blocks_15: float | _Omitted = _UNSET,
    double_blocks_16: float | _Omitted = _UNSET,
    double_blocks_17: float | _Omitted = _UNSET,
    double_blocks_18: float | _Omitted = _UNSET,
    double_blocks_19: float | _Omitted = _UNSET,
    single_blocks_0: float | _Omitted = _UNSET,
    single_blocks_1: float | _Omitted = _UNSET,
    single_blocks_2: float | _Omitted = _UNSET,
    single_blocks_3: float | _Omitted = _UNSET,
    single_blocks_4: float | _Omitted = _UNSET,
    single_blocks_5: float | _Omitted = _UNSET,
    single_blocks_6: float | _Omitted = _UNSET,
    single_blocks_7: float | _Omitted = _UNSET,
    single_blocks_8: float | _Omitted = _UNSET,
    single_blocks_9: float | _Omitted = _UNSET,
    single_blocks_10: float | _Omitted = _UNSET,
    single_blocks_11: float | _Omitted = _UNSET,
    single_blocks_12: float | _Omitted = _UNSET,
    single_blocks_13: float | _Omitted = _UNSET,
    single_blocks_14: float | _Omitted = _UNSET,
    single_blocks_15: float | _Omitted = _UNSET,
    single_blocks_16: float | _Omitted = _UNSET,
    single_blocks_17: float | _Omitted = _UNSET,
    single_blocks_18: float | _Omitted = _UNSET,
    single_blocks_19: float | _Omitted = _UNSET,
    single_blocks_20: float | _Omitted = _UNSET,
    single_blocks_21: float | _Omitted = _UNSET,
    single_blocks_22: float | _Omitted = _UNSET,
    single_blocks_23: float | _Omitted = _UNSET,
    single_blocks_24: float | _Omitted = _UNSET,
    single_blocks_25: float | _Omitted = _UNSET,
    single_blocks_26: float | _Omitted = _UNSET,
    single_blocks_27: float | _Omitted = _UNSET,
    single_blocks_28: float | _Omitted = _UNSET,
    single_blocks_29: float | _Omitted = _UNSET,
    single_blocks_30: float | _Omitted = _UNSET,
    single_blocks_31: float | _Omitted = _UNSET,
    single_blocks_32: float | _Omitted = _UNSET,
    single_blocks_33: float | _Omitted = _UNSET,
    single_blocks_34: float | _Omitted = _UNSET,
    single_blocks_35: float | _Omitted = _UNSET,
    single_blocks_36: float | _Omitted = _UNSET,
    single_blocks_37: float | _Omitted = _UNSET,
    single_blocks_38: float | _Omitted = _UNSET,
    single_blocks_39: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select individual block alpha values, value of 0 removes the block altogether

    Pack: ComfyUI-KJNodes
    Returns: blocks

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"HunyuanVideoBlockLoraSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if double_blocks_0 is not _UNSET:
        _kwargs['double_blocks.0.'] = double_blocks_0
    if double_blocks_1 is not _UNSET:
        _kwargs['double_blocks.1.'] = double_blocks_1
    if double_blocks_2 is not _UNSET:
        _kwargs['double_blocks.2.'] = double_blocks_2
    if double_blocks_3 is not _UNSET:
        _kwargs['double_blocks.3.'] = double_blocks_3
    if double_blocks_4 is not _UNSET:
        _kwargs['double_blocks.4.'] = double_blocks_4
    if double_blocks_5 is not _UNSET:
        _kwargs['double_blocks.5.'] = double_blocks_5
    if double_blocks_6 is not _UNSET:
        _kwargs['double_blocks.6.'] = double_blocks_6
    if double_blocks_7 is not _UNSET:
        _kwargs['double_blocks.7.'] = double_blocks_7
    if double_blocks_8 is not _UNSET:
        _kwargs['double_blocks.8.'] = double_blocks_8
    if double_blocks_9 is not _UNSET:
        _kwargs['double_blocks.9.'] = double_blocks_9
    if double_blocks_10 is not _UNSET:
        _kwargs['double_blocks.10.'] = double_blocks_10
    if double_blocks_11 is not _UNSET:
        _kwargs['double_blocks.11.'] = double_blocks_11
    if double_blocks_12 is not _UNSET:
        _kwargs['double_blocks.12.'] = double_blocks_12
    if double_blocks_13 is not _UNSET:
        _kwargs['double_blocks.13.'] = double_blocks_13
    if double_blocks_14 is not _UNSET:
        _kwargs['double_blocks.14.'] = double_blocks_14
    if double_blocks_15 is not _UNSET:
        _kwargs['double_blocks.15.'] = double_blocks_15
    if double_blocks_16 is not _UNSET:
        _kwargs['double_blocks.16.'] = double_blocks_16
    if double_blocks_17 is not _UNSET:
        _kwargs['double_blocks.17.'] = double_blocks_17
    if double_blocks_18 is not _UNSET:
        _kwargs['double_blocks.18.'] = double_blocks_18
    if double_blocks_19 is not _UNSET:
        _kwargs['double_blocks.19.'] = double_blocks_19
    if single_blocks_0 is not _UNSET:
        _kwargs['single_blocks.0.'] = single_blocks_0
    if single_blocks_1 is not _UNSET:
        _kwargs['single_blocks.1.'] = single_blocks_1
    if single_blocks_2 is not _UNSET:
        _kwargs['single_blocks.2.'] = single_blocks_2
    if single_blocks_3 is not _UNSET:
        _kwargs['single_blocks.3.'] = single_blocks_3
    if single_blocks_4 is not _UNSET:
        _kwargs['single_blocks.4.'] = single_blocks_4
    if single_blocks_5 is not _UNSET:
        _kwargs['single_blocks.5.'] = single_blocks_5
    if single_blocks_6 is not _UNSET:
        _kwargs['single_blocks.6.'] = single_blocks_6
    if single_blocks_7 is not _UNSET:
        _kwargs['single_blocks.7.'] = single_blocks_7
    if single_blocks_8 is not _UNSET:
        _kwargs['single_blocks.8.'] = single_blocks_8
    if single_blocks_9 is not _UNSET:
        _kwargs['single_blocks.9.'] = single_blocks_9
    if single_blocks_10 is not _UNSET:
        _kwargs['single_blocks.10.'] = single_blocks_10
    if single_blocks_11 is not _UNSET:
        _kwargs['single_blocks.11.'] = single_blocks_11
    if single_blocks_12 is not _UNSET:
        _kwargs['single_blocks.12.'] = single_blocks_12
    if single_blocks_13 is not _UNSET:
        _kwargs['single_blocks.13.'] = single_blocks_13
    if single_blocks_14 is not _UNSET:
        _kwargs['single_blocks.14.'] = single_blocks_14
    if single_blocks_15 is not _UNSET:
        _kwargs['single_blocks.15.'] = single_blocks_15
    if single_blocks_16 is not _UNSET:
        _kwargs['single_blocks.16.'] = single_blocks_16
    if single_blocks_17 is not _UNSET:
        _kwargs['single_blocks.17.'] = single_blocks_17
    if single_blocks_18 is not _UNSET:
        _kwargs['single_blocks.18.'] = single_blocks_18
    if single_blocks_19 is not _UNSET:
        _kwargs['single_blocks.19.'] = single_blocks_19
    if single_blocks_20 is not _UNSET:
        _kwargs['single_blocks.20.'] = single_blocks_20
    if single_blocks_21 is not _UNSET:
        _kwargs['single_blocks.21.'] = single_blocks_21
    if single_blocks_22 is not _UNSET:
        _kwargs['single_blocks.22.'] = single_blocks_22
    if single_blocks_23 is not _UNSET:
        _kwargs['single_blocks.23.'] = single_blocks_23
    if single_blocks_24 is not _UNSET:
        _kwargs['single_blocks.24.'] = single_blocks_24
    if single_blocks_25 is not _UNSET:
        _kwargs['single_blocks.25.'] = single_blocks_25
    if single_blocks_26 is not _UNSET:
        _kwargs['single_blocks.26.'] = single_blocks_26
    if single_blocks_27 is not _UNSET:
        _kwargs['single_blocks.27.'] = single_blocks_27
    if single_blocks_28 is not _UNSET:
        _kwargs['single_blocks.28.'] = single_blocks_28
    if single_blocks_29 is not _UNSET:
        _kwargs['single_blocks.29.'] = single_blocks_29
    if single_blocks_30 is not _UNSET:
        _kwargs['single_blocks.30.'] = single_blocks_30
    if single_blocks_31 is not _UNSET:
        _kwargs['single_blocks.31.'] = single_blocks_31
    if single_blocks_32 is not _UNSET:
        _kwargs['single_blocks.32.'] = single_blocks_32
    if single_blocks_33 is not _UNSET:
        _kwargs['single_blocks.33.'] = single_blocks_33
    if single_blocks_34 is not _UNSET:
        _kwargs['single_blocks.34.'] = single_blocks_34
    if single_blocks_35 is not _UNSET:
        _kwargs['single_blocks.35.'] = single_blocks_35
    if single_blocks_36 is not _UNSET:
        _kwargs['single_blocks.36.'] = single_blocks_36
    if single_blocks_37 is not _UNSET:
        _kwargs['single_blocks.37.'] = single_blocks_37
    if single_blocks_38 is not _UNSET:
        _kwargs['single_blocks.38.'] = single_blocks_38
    if single_blocks_39 is not _UNSET:
        _kwargs['single_blocks.39.'] = single_blocks_39
    _kwargs.update(_extras)
    return node(wf, 'HunyuanVideoBlockLoraSelect', _id, pass_raw=pass_raw, **_kwargs)

def HunyuanVideoEncodeKeyframesToCond(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    start_frame: Any | _Omitted = _UNSET,
    end_frame: Any | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    tile_size: int | _Omitted = _UNSET,
    overlap: int | _Omitted = _UNSET,
    temporal_size: int | _Omitted = _UNSET,
    temporal_overlap: int | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    HunyuanVideo Encode Keyframes To Cond

    Pack: ComfyUI-KJNodes
    Returns: model, positive, negative, latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"HunyuanVideoEncodeKeyframesToCond() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if start_frame is not _UNSET:
        _kwargs['start_frame'] = start_frame
    if end_frame is not _UNSET:
        _kwargs['end_frame'] = end_frame
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if tile_size is not _UNSET:
        _kwargs['tile_size'] = tile_size
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if temporal_size is not _UNSET:
        _kwargs['temporal_size'] = temporal_size
    if temporal_overlap is not _UNSET:
        _kwargs['temporal_overlap'] = temporal_overlap
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    _kwargs.update(_extras)
    return node(wf, 'HunyuanVideoEncodeKeyframesToCond', _id, pass_raw=pass_raw, **_kwargs)

def INTConstant(
    *args: VibeWorkflow,
    _id: str | None = None,
    value: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    INT Constant

    Pack: ComfyUI-KJNodes
    Returns: value

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"INTConstant() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if value is not _UNSET:
        _kwargs['value'] = value
    _kwargs.update(_extras)
    return node(wf, 'INTConstant', _id, pass_raw=pass_raw, **_kwargs)

def ImageAddMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: int | _Omitted = _UNSET,
    image_1: Any | _Omitted = _UNSET,
    image_2: Any | _Omitted = _UNSET,
    blending: Literal['add', 'subtract', 'multiply', 'difference'] | _Omitted = _UNSET,
    blend_amount: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Add blends multiple images together.
    You can set how many inputs the node has,
    with the **inputcount** and clicking update.

    Pack: ComfyUI-KJNodes
    Returns: images

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageAddMulti() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if inputcount is not _UNSET:
        _kwargs['inputcount'] = inputcount
    if image_1 is not _UNSET:
        _kwargs['image_1'] = image_1
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    if blending is not _UNSET:
        _kwargs['blending'] = blending
    if blend_amount is not _UNSET:
        _kwargs['blend_amount'] = blend_amount
    _kwargs.update(_extras)
    return node(wf, 'ImageAddMulti', _id, pass_raw=pass_raw, **_kwargs)

def ImageAndMaskPreview(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask_opacity: float | _Omitted = _UNSET,
    mask_color: str | _Omitted = _UNSET,
    pass_through: bool | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preview an image or a mask, when both inputs are used
    composites the mask on top of the image.
    with pass_through on the preview is disabled and the
    composite is returned from the composite slot instead,
    this allows for the preview to be passed for video combine
    nodes for example. Supports RGBA for mask_color to adjust transparency per color.

    Pack: ComfyUI-KJNodes
    Returns: composite

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageAndMaskPreview() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask_opacity is not _UNSET:
        _kwargs['mask_opacity'] = mask_opacity
    if mask_color is not _UNSET:
        _kwargs['mask_color'] = mask_color
    if pass_through is not _UNSET:
        _kwargs['pass_through'] = pass_through
    if image is not _UNSET:
        _kwargs['image'] = image
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'ImageAndMaskPreview', _id, pass_raw=pass_raw, **_kwargs)

def ImageBatchExtendWithOverlap(
    *args: VibeWorkflow,
    _id: str | None = None,
    source_images: Any | _Omitted = _UNSET,
    overlap: int | _Omitted = _UNSET,
    overlap_side: Literal['source', 'new_images'] | _Omitted = _UNSET,
    overlap_mode: Literal['cut', 'linear_blend', 'ease_in_out', 'filmic_crossfade', 'perceptual_crossfade'] | _Omitted = _UNSET,
    new_images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Helper node for video generation extension
    First input source and overlap amount to get the starting frames for the extension.
    Then on another copy of the node provide the newly generated frames and choose how to overlap them.

    Pack: ComfyUI-KJNodes
    Returns: source_images, start_images, extended_images

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageBatchExtendWithOverlap() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if source_images is not _UNSET:
        _kwargs['source_images'] = source_images
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if overlap_side is not _UNSET:
        _kwargs['overlap_side'] = overlap_side
    if overlap_mode is not _UNSET:
        _kwargs['overlap_mode'] = overlap_mode
    if new_images is not _UNSET:
        _kwargs['new_images'] = new_images
    _kwargs.update(_extras)
    return node(wf, 'ImageBatchExtendWithOverlap', _id, pass_raw=pass_raw, **_kwargs)

def ImageBatchFilter(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    empty_color: str | _Omitted = _UNSET,
    empty_threshold: float | _Omitted = _UNSET,
    replacement_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Removes empty images from a batch

    Pack: ComfyUI-KJNodes
    Returns: images, removed_indices

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageBatchFilter() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if empty_color is not _UNSET:
        _kwargs['empty_color'] = empty_color
    if empty_threshold is not _UNSET:
        _kwargs['empty_threshold'] = empty_threshold
    if replacement_image is not _UNSET:
        _kwargs['replacement_image'] = replacement_image
    _kwargs.update(_extras)
    return node(wf, 'ImageBatchFilter', _id, pass_raw=pass_raw, **_kwargs)

def ImageBatchJoinWithTransition(
    *args: VibeWorkflow,
    _id: str | None = None,
    images_1: Any | _Omitted = _UNSET,
    images_2: Any | _Omitted = _UNSET,
    start_index: int | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = _UNSET,
    transition_type: Literal['horizontal slide', 'vertical slide', 'box', 'circle', 'horizontal door', 'vertical door', 'fade'] | _Omitted = _UNSET,
    transitioning_frames: int | _Omitted = _UNSET,
    blur_radius: float | _Omitted = _UNSET,
    reverse: bool | _Omitted = _UNSET,
    device: Literal['CPU', 'GPU'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Transitions between two batches of images, starting at a specified index in the first batch.
    During the transition, frames from both batches are blended frame-by-frame, so the video keeps playing.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageBatchJoinWithTransition() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images_1 is not _UNSET:
        _kwargs['images_1'] = images_1
    if images_2 is not _UNSET:
        _kwargs['images_2'] = images_2
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if transition_type is not _UNSET:
        _kwargs['transition_type'] = transition_type
    if transitioning_frames is not _UNSET:
        _kwargs['transitioning_frames'] = transitioning_frames
    if blur_radius is not _UNSET:
        _kwargs['blur_radius'] = blur_radius
    if reverse is not _UNSET:
        _kwargs['reverse'] = reverse
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'ImageBatchJoinWithTransition', _id, pass_raw=pass_raw, **_kwargs)

def ImageBatchMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: int | _Omitted = _UNSET,
    image_1: Any | _Omitted = _UNSET,
    image_2: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates an image batch from multiple images.
    You can set how many inputs the node has,
    with the **inputcount** and clicking update.

    Pack: ComfyUI-KJNodes
    Returns: images

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageBatchMulti() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if inputcount is not _UNSET:
        _kwargs['inputcount'] = inputcount
    if image_1 is not _UNSET:
        _kwargs['image_1'] = image_1
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    _kwargs.update(_extras)
    return node(wf, 'ImageBatchMulti', _id, pass_raw=pass_raw, **_kwargs)

def ImageBatchRepeatInterleaving(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    repeats: int | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Repeats each image in a batch by the specified number of times.
    Example batch of 5 images: 0, 1 ,2, 3, 4
    with repeats 2 becomes batch of 10 images: 0, 0, 1, 1, 2, 2, 3, 3, 4, 4

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageBatchRepeatInterleaving() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if repeats is not _UNSET:
        _kwargs['repeats'] = repeats
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'ImageBatchRepeatInterleaving', _id, pass_raw=pass_raw, **_kwargs)

def ImageBatchTestPattern(
    *args: VibeWorkflow,
    _id: str | None = None,
    batch_size: int | _Omitted = _UNSET,
    start_from: int | _Omitted = _UNSET,
    text_x: int | _Omitted = _UNSET,
    text_y: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    font: Any | _Omitted = _UNSET,
    font_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Batch Test Pattern

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageBatchTestPattern() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if start_from is not _UNSET:
        _kwargs['start_from'] = start_from
    if text_x is not _UNSET:
        _kwargs['text_x'] = text_x
    if text_y is not _UNSET:
        _kwargs['text_y'] = text_y
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if font is not _UNSET:
        _kwargs['font'] = font
    if font_size is not _UNSET:
        _kwargs['font_size'] = font_size
    _kwargs.update(_extras)
    return node(wf, 'ImageBatchTestPattern', _id, pass_raw=pass_raw, **_kwargs)

def ImageConcanate(
    *args: VibeWorkflow,
    _id: str | None = None,
    image1: Any | _Omitted = _UNSET,
    image2: Any | _Omitted = _UNSET,
    direction: Literal['right', 'down', 'left', 'up'] | _Omitted = _UNSET,
    match_image_size: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Concatenates the image2 to image1 in the specified direction.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageConcanate() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image1 is not _UNSET:
        _kwargs['image1'] = image1
    if image2 is not _UNSET:
        _kwargs['image2'] = image2
    if direction is not _UNSET:
        _kwargs['direction'] = direction
    if match_image_size is not _UNSET:
        _kwargs['match_image_size'] = match_image_size
    _kwargs.update(_extras)
    return node(wf, 'ImageConcanate', _id, pass_raw=pass_raw, **_kwargs)

def ImageConcatFromBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    num_columns: int | _Omitted = _UNSET,
    match_image_size: bool | _Omitted = _UNSET,
    max_resolution: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Concatenates images from a batch into a grid with a specified number of columns.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageConcatFromBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if num_columns is not _UNSET:
        _kwargs['num_columns'] = num_columns
    if match_image_size is not _UNSET:
        _kwargs['match_image_size'] = match_image_size
    if max_resolution is not _UNSET:
        _kwargs['max_resolution'] = max_resolution
    _kwargs.update(_extras)
    return node(wf, 'ImageConcatFromBatch', _id, pass_raw=pass_raw, **_kwargs)

def ImageConcatMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: int | _Omitted = _UNSET,
    image_1: Any | _Omitted = _UNSET,
    direction: Literal['right', 'down', 'left', 'up'] | _Omitted = _UNSET,
    match_image_size: bool | _Omitted = _UNSET,
    image_2: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates an image from multiple images.
    You can set how many inputs the node has,
    with the **inputcount** and clicking update.

    Pack: ComfyUI-KJNodes
    Returns: images

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageConcatMulti() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if inputcount is not _UNSET:
        _kwargs['inputcount'] = inputcount
    if image_1 is not _UNSET:
        _kwargs['image_1'] = image_1
    if direction is not _UNSET:
        _kwargs['direction'] = direction
    if match_image_size is not _UNSET:
        _kwargs['match_image_size'] = match_image_size
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    _kwargs.update(_extras)
    return node(wf, 'ImageConcatMulti', _id, pass_raw=pass_raw, **_kwargs)

def ImageCropByMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Crops the input images based on the provided mask.

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageCropByMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'ImageCropByMask', _id, pass_raw=pass_raw, **_kwargs)

def ImageCropByMaskAndResize(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    base_resolution: int | _Omitted = _UNSET,
    padding: int | _Omitted = _UNSET,
    min_crop_resolution: int | _Omitted = _UNSET,
    max_crop_resolution: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Crop By Mask And Resize

    Pack: ComfyUI-KJNodes
    Returns: images, masks, bbox

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageCropByMaskAndResize() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if base_resolution is not _UNSET:
        _kwargs['base_resolution'] = base_resolution
    if padding is not _UNSET:
        _kwargs['padding'] = padding
    if min_crop_resolution is not _UNSET:
        _kwargs['min_crop_resolution'] = min_crop_resolution
    if max_crop_resolution is not _UNSET:
        _kwargs['max_crop_resolution'] = max_crop_resolution
    _kwargs.update(_extras)
    return node(wf, 'ImageCropByMaskAndResize', _id, pass_raw=pass_raw, **_kwargs)

def ImageCropByMaskBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    masks: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    padding: int | _Omitted = _UNSET,
    preserve_size: bool | _Omitted = _UNSET,
    bg_color: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Crops the input images based on the provided masks.

    Pack: ComfyUI-KJNodes
    Returns: images, masks

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageCropByMaskBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if padding is not _UNSET:
        _kwargs['padding'] = padding
    if preserve_size is not _UNSET:
        _kwargs['preserve_size'] = preserve_size
    if bg_color is not _UNSET:
        _kwargs['bg_color'] = bg_color
    _kwargs.update(_extras)
    return node(wf, 'ImageCropByMaskBatch', _id, pass_raw=pass_raw, **_kwargs)

def ImageGrabPIL(
    *args: VibeWorkflow,
    _id: str | None = None,
    x: int | _Omitted = _UNSET,
    y: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    delay: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Captures an area specified by screen coordinates.
    Can be used for realtime diffusion with autoqueue.

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageGrabPIL() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if x is not _UNSET:
        _kwargs['x'] = x
    if y is not _UNSET:
        _kwargs['y'] = y
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if delay is not _UNSET:
        _kwargs['delay'] = delay
    _kwargs.update(_extras)
    return node(wf, 'ImageGrabPIL', _id, pass_raw=pass_raw, **_kwargs)

def ImageGridComposite2x2(
    *args: VibeWorkflow,
    _id: str | None = None,
    image1: Any | _Omitted = _UNSET,
    image2: Any | _Omitted = _UNSET,
    image3: Any | _Omitted = _UNSET,
    image4: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Concatenates the 4 input images into a 2x2 grid.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageGridComposite2x2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image1 is not _UNSET:
        _kwargs['image1'] = image1
    if image2 is not _UNSET:
        _kwargs['image2'] = image2
    if image3 is not _UNSET:
        _kwargs['image3'] = image3
    if image4 is not _UNSET:
        _kwargs['image4'] = image4
    _kwargs.update(_extras)
    return node(wf, 'ImageGridComposite2x2', _id, pass_raw=pass_raw, **_kwargs)

def ImageGridComposite3x3(
    *args: VibeWorkflow,
    _id: str | None = None,
    image1: Any | _Omitted = _UNSET,
    image2: Any | _Omitted = _UNSET,
    image3: Any | _Omitted = _UNSET,
    image4: Any | _Omitted = _UNSET,
    image5: Any | _Omitted = _UNSET,
    image6: Any | _Omitted = _UNSET,
    image7: Any | _Omitted = _UNSET,
    image8: Any | _Omitted = _UNSET,
    image9: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Concatenates the 9 input images into a 3x3 grid.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageGridComposite3x3() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image1 is not _UNSET:
        _kwargs['image1'] = image1
    if image2 is not _UNSET:
        _kwargs['image2'] = image2
    if image3 is not _UNSET:
        _kwargs['image3'] = image3
    if image4 is not _UNSET:
        _kwargs['image4'] = image4
    if image5 is not _UNSET:
        _kwargs['image5'] = image5
    if image6 is not _UNSET:
        _kwargs['image6'] = image6
    if image7 is not _UNSET:
        _kwargs['image7'] = image7
    if image8 is not _UNSET:
        _kwargs['image8'] = image8
    if image9 is not _UNSET:
        _kwargs['image9'] = image9
    _kwargs.update(_extras)
    return node(wf, 'ImageGridComposite3x3', _id, pass_raw=pass_raw, **_kwargs)

def ImageGridtoBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    columns: int | _Omitted = _UNSET,
    rows: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Converts a grid of images to a batch of images.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageGridtoBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if columns is not _UNSET:
        _kwargs['columns'] = columns
    if rows is not _UNSET:
        _kwargs['rows'] = rows
    _kwargs.update(_extras)
    return node(wf, 'ImageGridtoBatch', _id, pass_raw=pass_raw, **_kwargs)

def ImageNoiseAugmentation(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    noise_aug_strength: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Add noise to an image.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageNoiseAugmentation() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if noise_aug_strength is not _UNSET:
        _kwargs['noise_aug_strength'] = noise_aug_strength
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'ImageNoiseAugmentation', _id, pass_raw=pass_raw, **_kwargs)

def ImageNormalize_Neg1_To_1(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Normalize the images to be in the range [-1, 1]

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageNormalize_Neg1_To_1() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'ImageNormalize_Neg1_To_1', _id, pass_raw=pass_raw, **_kwargs)

def ImagePadForOutpaintMasked(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    left: int | _Omitted = _UNSET,
    top: int | _Omitted = _UNSET,
    right: int | _Omitted = _UNSET,
    bottom: int | _Omitted = _UNSET,
    feathering: int | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Pad For Outpaint Masked

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImagePadForOutpaintMasked() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if left is not _UNSET:
        _kwargs['left'] = left
    if top is not _UNSET:
        _kwargs['top'] = top
    if right is not _UNSET:
        _kwargs['right'] = right
    if bottom is not _UNSET:
        _kwargs['bottom'] = bottom
    if feathering is not _UNSET:
        _kwargs['feathering'] = feathering
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'ImagePadForOutpaintMasked', _id, pass_raw=pass_raw, **_kwargs)

def ImagePadForOutpaintTargetSize(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    target_width: int | _Omitted = _UNSET,
    target_height: int | _Omitted = _UNSET,
    feathering: int | _Omitted = _UNSET,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Pad For Outpaint Target Size

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImagePadForOutpaintTargetSize() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if target_width is not _UNSET:
        _kwargs['target_width'] = target_width
    if target_height is not _UNSET:
        _kwargs['target_height'] = target_height
    if feathering is not _UNSET:
        _kwargs['feathering'] = feathering
    if upscale_method is not _UNSET:
        _kwargs['upscale_method'] = upscale_method
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'ImagePadForOutpaintTargetSize', _id, pass_raw=pass_raw, **_kwargs)

def ImagePadKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    left: int | _Omitted = _UNSET,
    right: int | _Omitted = _UNSET,
    top: int | _Omitted = _UNSET,
    bottom: int | _Omitted = _UNSET,
    extra_padding: int | _Omitted = _UNSET,
    pad_mode: Literal['edge', 'edge_pixel', 'color', 'pillarbox_blur'] | _Omitted = _UNSET,
    color: str | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    target_width: int | _Omitted = _UNSET,
    target_height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pad the input image and optionally mask with the specified padding.

    Pack: ComfyUI-KJNodes
    Returns: images, masks

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImagePadKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if left is not _UNSET:
        _kwargs['left'] = left
    if right is not _UNSET:
        _kwargs['right'] = right
    if top is not _UNSET:
        _kwargs['top'] = top
    if bottom is not _UNSET:
        _kwargs['bottom'] = bottom
    if extra_padding is not _UNSET:
        _kwargs['extra_padding'] = extra_padding
    if pad_mode is not _UNSET:
        _kwargs['pad_mode'] = pad_mode
    if color is not _UNSET:
        _kwargs['color'] = color
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if target_width is not _UNSET:
        _kwargs['target_width'] = target_width
    if target_height is not _UNSET:
        _kwargs['target_height'] = target_height
    _kwargs.update(_extras)
    return node(wf, 'ImagePadKJ', _id, pass_raw=pass_raw, **_kwargs)

def ImagePass(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Passes the image through without modifying it.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImagePass() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'ImagePass', _id, pass_raw=pass_raw, **_kwargs)

def ImagePrepForICLora(
    *args: VibeWorkflow,
    _id: str | None = None,
    reference_image: Any | _Omitted = _UNSET,
    output_width: int | _Omitted = _UNSET,
    output_height: int | _Omitted = _UNSET,
    border_width: int | _Omitted = _UNSET,
    latent_image: Any | _Omitted = _UNSET,
    latent_mask: Any | _Omitted = _UNSET,
    reference_mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Prep For ICLora

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImagePrepForICLora() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if reference_image is not _UNSET:
        _kwargs['reference_image'] = reference_image
    if output_width is not _UNSET:
        _kwargs['output_width'] = output_width
    if output_height is not _UNSET:
        _kwargs['output_height'] = output_height
    if border_width is not _UNSET:
        _kwargs['border_width'] = border_width
    if latent_image is not _UNSET:
        _kwargs['latent_image'] = latent_image
    if latent_mask is not _UNSET:
        _kwargs['latent_mask'] = latent_mask
    if reference_mask is not _UNSET:
        _kwargs['reference_mask'] = reference_mask
    _kwargs.update(_extras)
    return node(wf, 'ImagePrepForICLora', _id, pass_raw=pass_raw, **_kwargs)

def ImageResizeKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = _UNSET,
    keep_proportion: bool | _Omitted = _UNSET,
    divisible_by: int | _Omitted = _UNSET,
    get_image_size: Any | _Omitted = _UNSET,
    crop: Literal['disabled', 'center', 0] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    DEPRECATED!

    Due to ComfyUI frontend changes, this node should no longer be used, please check the
    v2 of the node. This node is only kept to not completely break older workflows.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, width, height

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageResizeKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if upscale_method is not _UNSET:
        _kwargs['upscale_method'] = upscale_method
    if keep_proportion is not _UNSET:
        _kwargs['keep_proportion'] = keep_proportion
    if divisible_by is not _UNSET:
        _kwargs['divisible_by'] = divisible_by
    if get_image_size is not _UNSET:
        _kwargs['get_image_size'] = get_image_size
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    _kwargs.update(_extras)
    return node(wf, 'ImageResizeKJ', _id, pass_raw=pass_raw, **_kwargs)

def ImageResizeKJv2(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos', 'nvidia_rtx_vsr'] | _Omitted = _UNSET,
    keep_proportion: Literal['stretch', 'resize', 'pad', 'pad_edge', 'pad_edge_pixel', 'crop', 'pillarbox_blur', 'total_pixels'] | _Omitted = _UNSET,
    pad_color: str | _Omitted = _UNSET,
    crop_position: Literal['center', 'top', 'bottom', 'left', 'right'] | _Omitted = _UNSET,
    divisible_by: int | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    device: Literal['cpu', 'gpu'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Resizes the image to the specified width and height.
    Size can be retrieved from the input.

    Keep proportions keeps the aspect ratio of the image, by
    highest dimension.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, width, height, mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageResizeKJv2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if upscale_method is not _UNSET:
        _kwargs['upscale_method'] = upscale_method
    if keep_proportion is not _UNSET:
        _kwargs['keep_proportion'] = keep_proportion
    if pad_color is not _UNSET:
        _kwargs['pad_color'] = pad_color
    if crop_position is not _UNSET:
        _kwargs['crop_position'] = crop_position
    if divisible_by is not _UNSET:
        _kwargs['divisible_by'] = divisible_by
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'ImageResizeKJv2', _id, pass_raw=pass_raw, **_kwargs)

def ImageSharpenKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    method: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    GPU-accelerated image sharpening with multiple methods.

    **RCAS** — AMD's Robust Contrast-Adaptive Sharpening (from FSR).
    Single 5-tap cross filter that adapts to local contrast.
    Minimal artifacts, good for general use with little tuning.

    **Adaptive USM** — Unsharp mask with local variance modulation.
    Sharpens detail-rich areas more, flat/noisy areas less.
    More controllable than RCAS via radius and threshold parameters.

    **High-Pass** — Extracts high-frequency detail and blends it back.
    Gives a "clarity" enhancement feel. Uses radius to control detail scale.

    **Deconvolution** — Richardson-Lucy iterative deconvolution.
    Can recover actual lost detail from blur, not just enhance edges.
    Uses radius as the estimated blur kernel and iterations to control convergence.

    Pack: ComfyUI-KJNodes
    Returns: output

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageSharpenKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if method is not _UNSET:
        _kwargs['method'] = method
    _kwargs.update(_extras)
    return node(wf, 'ImageSharpenKJ', _id, pass_raw=pass_raw, **_kwargs)

def ImageTensorList(
    *args: VibeWorkflow,
    _id: str | None = None,
    image1: Any | _Omitted = _UNSET,
    image2: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates an image list from the input images.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageTensorList() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image1 is not _UNSET:
        _kwargs['image1'] = image1
    if image2 is not _UNSET:
        _kwargs['image2'] = image2
    _kwargs.update(_extras)
    return node(wf, 'ImageTensorList', _id, pass_raw=pass_raw, **_kwargs)

def ImageTransformByNormalizedAmplitude(
    *args: VibeWorkflow,
    _id: str | None = None,
    normalized_amp: Any | _Omitted = _UNSET,
    zoom_scale: float | _Omitted = _UNSET,
    x_offset: int | _Omitted = _UNSET,
    y_offset: int | _Omitted = _UNSET,
    cumulative: bool | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Works as a bridge to the AudioScheduler -nodes:
    https://github.com/a1lazydog/ComfyUI-AudioScheduler
    Transforms image based on the normalized amplitude.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageTransformByNormalizedAmplitude() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if normalized_amp is not _UNSET:
        _kwargs['normalized_amp'] = normalized_amp
    if zoom_scale is not _UNSET:
        _kwargs['zoom_scale'] = zoom_scale
    if x_offset is not _UNSET:
        _kwargs['x_offset'] = x_offset
    if y_offset is not _UNSET:
        _kwargs['y_offset'] = y_offset
    if cumulative is not _UNSET:
        _kwargs['cumulative'] = cumulative
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'ImageTransformByNormalizedAmplitude', _id, pass_raw=pass_raw, **_kwargs)

def ImageTransformKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    target_width: int | _Omitted = _UNSET,
    target_height: int | _Omitted = _UNSET,
    upscale_method: Any | _Omitted = _UNSET,
    keep_proportion: Any | _Omitted = _UNSET,
    divisible_by: int | _Omitted = _UNSET,
    extra_padding: Any | _Omitted = _UNSET,
    invert_crop: Any | _Omitted = _UNSET,
    bboxes: str | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Interactive image transform node: crop, resize, pad, and rotate.
    Connect an image input — the preview appears automatically.

    Cropping:
    Click + drag to draw a crop region.
    Drag inside to move, drag edges/corners to resize.
    Right-click to delete a region.
    Ctrl to snap to grid.
    Shift + resize to constrain aspect ratio.
    Alt + resize to resize symmetrically.

    Padding:
    Shift + drag to adjust padding position.

    Rotate button enables rotation cross (drag to rotate, right-click to reset).
    Set target_width/height to resize output (0 = keep original).
    Use keep_proportion to control how the image fits the target.
    Use extra_padding to add padding with color or edge fill (clamp/repeat/mirror).

    Pack: ComfyUI-KJNodes
    Returns: output, output_mask, bbox, bbox_mask, width, height

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageTransformKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if target_width is not _UNSET:
        _kwargs['target_width'] = target_width
    if target_height is not _UNSET:
        _kwargs['target_height'] = target_height
    if upscale_method is not _UNSET:
        _kwargs['upscale_method'] = upscale_method
    if keep_proportion is not _UNSET:
        _kwargs['keep_proportion'] = keep_proportion
    if divisible_by is not _UNSET:
        _kwargs['divisible_by'] = divisible_by
    if extra_padding is not _UNSET:
        _kwargs['extra_padding'] = extra_padding
    if invert_crop is not _UNSET:
        _kwargs['invert_crop'] = invert_crop
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'ImageTransformKJ', _id, pass_raw=pass_raw, **_kwargs)

def ImageUncropByMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    destination: Any | _Omitted = _UNSET,
    source: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    bbox: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Image Uncrop By Mask

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageUncropByMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if destination is not _UNSET:
        _kwargs['destination'] = destination
    if source is not _UNSET:
        _kwargs['source'] = source
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if bbox is not _UNSET:
        _kwargs['bbox'] = bbox
    _kwargs.update(_extras)
    return node(wf, 'ImageUncropByMask', _id, pass_raw=pass_raw, **_kwargs)

def ImageUpscaleWithModelBatched(
    *args: VibeWorkflow,
    _id: str | None = None,
    upscale_model: Any | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    per_batch: int | _Omitted = _UNSET,
    downscale_ratio: float | _Omitted = _UNSET,
    downscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = _UNSET,
    precision: Literal['float32', 'float16', 'bfloat16'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Same as ComfyUI native model upscaling node,
    but allows setting sub-batches for reduced VRAM usage.
    Optionally downscale the result with a ratio.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ImageUpscaleWithModelBatched() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if upscale_model is not _UNSET:
        _kwargs['upscale_model'] = upscale_model
    if images is not _UNSET:
        _kwargs['images'] = images
    if per_batch is not _UNSET:
        _kwargs['per_batch'] = per_batch
    if downscale_ratio is not _UNSET:
        _kwargs['downscale_ratio'] = downscale_ratio
    if downscale_method is not _UNSET:
        _kwargs['downscale_method'] = downscale_method
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'ImageUpscaleWithModelBatched', _id, pass_raw=pass_raw, **_kwargs)

def InjectNoiseToLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    noise: Any | _Omitted = _UNSET,
    normalize: bool | _Omitted = _UNSET,
    average: bool | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    mix_randn_amount: float | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Inject Noise To Latent

    Pack: ComfyUI-KJNodes
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"InjectNoiseToLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if noise is not _UNSET:
        _kwargs['noise'] = noise
    if normalize is not _UNSET:
        _kwargs['normalize'] = normalize
    if average is not _UNSET:
        _kwargs['average'] = average
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if mix_randn_amount is not _UNSET:
        _kwargs['mix_randn_amount'] = mix_randn_amount
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'InjectNoiseToLatent', _id, pass_raw=pass_raw, **_kwargs)

def InsertImageBatchByIndexes(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    images_to_insert: Any | _Omitted = _UNSET,
    insert_indexes: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node is designed to be use with node FilterZeroMasksAndCorrespondingImages
    It inserts the images_to_insert into images according to insert_indexes

    Returns:
        images_after_insert: updated original images with origonal sequence order

    Pack: ComfyUI-KJNodes
    Returns: images_after_insert

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"InsertImageBatchByIndexes() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if images_to_insert is not _UNSET:
        _kwargs['images_to_insert'] = images_to_insert
    if insert_indexes is not _UNSET:
        _kwargs['insert_indexes'] = insert_indexes
    _kwargs.update(_extras)
    return node(wf, 'InsertImageBatchByIndexes', _id, pass_raw=pass_raw, **_kwargs)

def InsertImagesToBatchIndexed(
    *args: VibeWorkflow,
    _id: str | None = None,
    original_images: Any | _Omitted = _UNSET,
    images_to_insert: Any | _Omitted = _UNSET,
    indexes: str | _Omitted = _UNSET,
    mode: Literal['replace', 'insert'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Inserts images at the specified indices into the original image batch.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"InsertImagesToBatchIndexed() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if original_images is not _UNSET:
        _kwargs['original_images'] = original_images
    if images_to_insert is not _UNSET:
        _kwargs['images_to_insert'] = images_to_insert
    if indexes is not _UNSET:
        _kwargs['indexes'] = indexes
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    _kwargs.update(_extras)
    return node(wf, 'InsertImagesToBatchIndexed', _id, pass_raw=pass_raw, **_kwargs)

def InsertLatentToIndexed(
    *args: VibeWorkflow,
    _id: str | None = None,
    source: Any | _Omitted = _UNSET,
    destination: Any | _Omitted = _UNSET,
    index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Inserts a latent at the specified index into the original latent batch.

    Pack: ComfyUI-KJNodes
    Returns: LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"InsertLatentToIndexed() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if source is not _UNSET:
        _kwargs['source'] = source
    if destination is not _UNSET:
        _kwargs['destination'] = destination
    if index is not _UNSET:
        _kwargs['index'] = index
    _kwargs.update(_extras)
    return node(wf, 'InsertLatentToIndexed', _id, pass_raw=pass_raw, **_kwargs)

def InterpolateCoords(
    *args: VibeWorkflow,
    _id: str | None = None,
    coordinates: str | _Omitted = _UNSET,
    interpolation_curve: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Interpolates coordinates based on a curve.

    Pack: ComfyUI-KJNodes
    Returns: coordinates

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"InterpolateCoords() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if interpolation_curve is not _UNSET:
        _kwargs['interpolation_curve'] = interpolation_curve
    _kwargs.update(_extras)
    return node(wf, 'InterpolateCoords', _id, pass_raw=pass_raw, **_kwargs)

def Intrinsic_lora_sampling(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    lora_name: Any | _Omitted = _UNSET,
    task: Literal['depth map', 'surface normals', 'albedo', 'shading'] | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    clip: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    per_batch: int | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    optional_latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sampler to use the intrinsic loras:
    https://github.com/duxiaodan/intrinsic-lora
    These LoRAs are tiny and thus included
    with this node pack.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, LATENT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Intrinsic_lora_sampling() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if lora_name is not _UNSET:
        _kwargs['lora_name'] = lora_name
    if task is not _UNSET:
        _kwargs['task'] = task
    if text is not _UNSET:
        _kwargs['text'] = text
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if per_batch is not _UNSET:
        _kwargs['per_batch'] = per_batch
    if image is not _UNSET:
        _kwargs['image'] = image
    if optional_latent is not _UNSET:
        _kwargs['optional_latent'] = optional_latent
    _kwargs.update(_extras)
    return node(wf, 'Intrinsic_lora_sampling', _id, pass_raw=pass_raw, **_kwargs)

def JoinStringMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: int | _Omitted = _UNSET,
    string_1: str | _Omitted = _UNSET,
    delimiter: str | _Omitted = _UNSET,
    return_list: bool | _Omitted = _UNSET,
    string_2: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates single string, or a list of strings, from
    multiple input strings.
    You can set how many inputs the node has,
    with the **inputcount** and clicking update.

    Pack: ComfyUI-KJNodes
    Returns: string

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"JoinStringMulti() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if inputcount is not _UNSET:
        _kwargs['inputcount'] = inputcount
    if string_1 is not _UNSET:
        _kwargs['string_1'] = string_1
    if delimiter is not _UNSET:
        _kwargs['delimiter'] = delimiter
    if return_list is not _UNSET:
        _kwargs['return_list'] = return_list
    if string_2 is not _UNSET:
        _kwargs['string_2'] = string_2
    _kwargs.update(_extras)
    return node(wf, 'JoinStringMulti', _id, pass_raw=pass_raw, **_kwargs)

def JoinStrings(
    *args: VibeWorkflow,
    _id: str | None = None,
    delimiter: str | _Omitted = _UNSET,
    string1: str | _Omitted = _UNSET,
    string2: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Join Strings

    Pack: ComfyUI-KJNodes
    Returns: STRING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"JoinStrings() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if delimiter is not _UNSET:
        _kwargs['delimiter'] = delimiter
    if string1 is not _UNSET:
        _kwargs['string1'] = string1
    if string2 is not _UNSET:
        _kwargs['string2'] = string2
    _kwargs.update(_extras)
    return node(wf, 'JoinStrings', _id, pass_raw=pass_raw, **_kwargs)

def LTX2AttentionTunerPatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    blocks: str | _Omitted = _UNSET,
    video_scale: float | _Omitted = _UNSET,
    audio_scale: float | _Omitted = _UNSET,
    audio_to_video_scale: float | _Omitted = _UNSET,
    video_to_audio_scale: float | _Omitted = _UNSET,
    triton_kernels: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EXPERIMENTAL! Custom LTX2 forward pass with attention scaling factors per modality, also reduces peak VRAM usage.

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTX2AttentionTunerPatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    if video_scale is not _UNSET:
        _kwargs['video_scale'] = video_scale
    if audio_scale is not _UNSET:
        _kwargs['audio_scale'] = audio_scale
    if audio_to_video_scale is not _UNSET:
        _kwargs['audio_to_video_scale'] = audio_to_video_scale
    if video_to_audio_scale is not _UNSET:
        _kwargs['video_to_audio_scale'] = video_to_audio_scale
    if triton_kernels is not _UNSET:
        _kwargs['triton_kernels'] = triton_kernels
    _kwargs.update(_extras)
    return node(wf, 'LTX2AttentionTunerPatch', _id, pass_raw=pass_raw, **_kwargs)

def LTX2AudioLatentNormalizingSampling(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    audio_normalization_factors: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Improves LTX2 generated audio quality by normalizing audio latents at specified sampling steps.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTX2AudioLatentNormalizingSampling() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if audio_normalization_factors is not _UNSET:
        _kwargs['audio_normalization_factors'] = audio_normalization_factors
    _kwargs.update(_extras)
    return node(wf, 'LTX2AudioLatentNormalizingSampling', _id, pass_raw=pass_raw, **_kwargs)

def LTX2BlockLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = None,
    blocks_0: float | _Omitted = _UNSET,
    blocks_1: float | _Omitted = _UNSET,
    blocks_2: float | _Omitted = _UNSET,
    blocks_3: float | _Omitted = _UNSET,
    blocks_4: float | _Omitted = _UNSET,
    blocks_5: float | _Omitted = _UNSET,
    blocks_6: float | _Omitted = _UNSET,
    blocks_7: float | _Omitted = _UNSET,
    blocks_8: float | _Omitted = _UNSET,
    blocks_9: float | _Omitted = _UNSET,
    blocks_10: float | _Omitted = _UNSET,
    blocks_11: float | _Omitted = _UNSET,
    blocks_12: float | _Omitted = _UNSET,
    blocks_13: float | _Omitted = _UNSET,
    blocks_14: float | _Omitted = _UNSET,
    blocks_15: float | _Omitted = _UNSET,
    blocks_16: float | _Omitted = _UNSET,
    blocks_17: float | _Omitted = _UNSET,
    blocks_18: float | _Omitted = _UNSET,
    blocks_19: float | _Omitted = _UNSET,
    blocks_20: float | _Omitted = _UNSET,
    blocks_21: float | _Omitted = _UNSET,
    blocks_22: float | _Omitted = _UNSET,
    blocks_23: float | _Omitted = _UNSET,
    blocks_24: float | _Omitted = _UNSET,
    blocks_25: float | _Omitted = _UNSET,
    blocks_26: float | _Omitted = _UNSET,
    blocks_27: float | _Omitted = _UNSET,
    blocks_28: float | _Omitted = _UNSET,
    blocks_29: float | _Omitted = _UNSET,
    blocks_30: float | _Omitted = _UNSET,
    blocks_31: float | _Omitted = _UNSET,
    blocks_32: float | _Omitted = _UNSET,
    blocks_33: float | _Omitted = _UNSET,
    blocks_34: float | _Omitted = _UNSET,
    blocks_35: float | _Omitted = _UNSET,
    blocks_36: float | _Omitted = _UNSET,
    blocks_37: float | _Omitted = _UNSET,
    blocks_38: float | _Omitted = _UNSET,
    blocks_39: float | _Omitted = _UNSET,
    blocks_40: float | _Omitted = _UNSET,
    blocks_41: float | _Omitted = _UNSET,
    blocks_42: float | _Omitted = _UNSET,
    blocks_43: float | _Omitted = _UNSET,
    blocks_44: float | _Omitted = _UNSET,
    blocks_45: float | _Omitted = _UNSET,
    blocks_46: float | _Omitted = _UNSET,
    blocks_47: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select individual block alpha values, value of 0 removes the block altogether

    Pack: ComfyUI-KJNodes
    Returns: blocks

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTX2BlockLoraSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if blocks_0 is not _UNSET:
        _kwargs['blocks.0.'] = blocks_0
    if blocks_1 is not _UNSET:
        _kwargs['blocks.1.'] = blocks_1
    if blocks_2 is not _UNSET:
        _kwargs['blocks.2.'] = blocks_2
    if blocks_3 is not _UNSET:
        _kwargs['blocks.3.'] = blocks_3
    if blocks_4 is not _UNSET:
        _kwargs['blocks.4.'] = blocks_4
    if blocks_5 is not _UNSET:
        _kwargs['blocks.5.'] = blocks_5
    if blocks_6 is not _UNSET:
        _kwargs['blocks.6.'] = blocks_6
    if blocks_7 is not _UNSET:
        _kwargs['blocks.7.'] = blocks_7
    if blocks_8 is not _UNSET:
        _kwargs['blocks.8.'] = blocks_8
    if blocks_9 is not _UNSET:
        _kwargs['blocks.9.'] = blocks_9
    if blocks_10 is not _UNSET:
        _kwargs['blocks.10.'] = blocks_10
    if blocks_11 is not _UNSET:
        _kwargs['blocks.11.'] = blocks_11
    if blocks_12 is not _UNSET:
        _kwargs['blocks.12.'] = blocks_12
    if blocks_13 is not _UNSET:
        _kwargs['blocks.13.'] = blocks_13
    if blocks_14 is not _UNSET:
        _kwargs['blocks.14.'] = blocks_14
    if blocks_15 is not _UNSET:
        _kwargs['blocks.15.'] = blocks_15
    if blocks_16 is not _UNSET:
        _kwargs['blocks.16.'] = blocks_16
    if blocks_17 is not _UNSET:
        _kwargs['blocks.17.'] = blocks_17
    if blocks_18 is not _UNSET:
        _kwargs['blocks.18.'] = blocks_18
    if blocks_19 is not _UNSET:
        _kwargs['blocks.19.'] = blocks_19
    if blocks_20 is not _UNSET:
        _kwargs['blocks.20.'] = blocks_20
    if blocks_21 is not _UNSET:
        _kwargs['blocks.21.'] = blocks_21
    if blocks_22 is not _UNSET:
        _kwargs['blocks.22.'] = blocks_22
    if blocks_23 is not _UNSET:
        _kwargs['blocks.23.'] = blocks_23
    if blocks_24 is not _UNSET:
        _kwargs['blocks.24.'] = blocks_24
    if blocks_25 is not _UNSET:
        _kwargs['blocks.25.'] = blocks_25
    if blocks_26 is not _UNSET:
        _kwargs['blocks.26.'] = blocks_26
    if blocks_27 is not _UNSET:
        _kwargs['blocks.27.'] = blocks_27
    if blocks_28 is not _UNSET:
        _kwargs['blocks.28.'] = blocks_28
    if blocks_29 is not _UNSET:
        _kwargs['blocks.29.'] = blocks_29
    if blocks_30 is not _UNSET:
        _kwargs['blocks.30.'] = blocks_30
    if blocks_31 is not _UNSET:
        _kwargs['blocks.31.'] = blocks_31
    if blocks_32 is not _UNSET:
        _kwargs['blocks.32.'] = blocks_32
    if blocks_33 is not _UNSET:
        _kwargs['blocks.33.'] = blocks_33
    if blocks_34 is not _UNSET:
        _kwargs['blocks.34.'] = blocks_34
    if blocks_35 is not _UNSET:
        _kwargs['blocks.35.'] = blocks_35
    if blocks_36 is not _UNSET:
        _kwargs['blocks.36.'] = blocks_36
    if blocks_37 is not _UNSET:
        _kwargs['blocks.37.'] = blocks_37
    if blocks_38 is not _UNSET:
        _kwargs['blocks.38.'] = blocks_38
    if blocks_39 is not _UNSET:
        _kwargs['blocks.39.'] = blocks_39
    if blocks_40 is not _UNSET:
        _kwargs['blocks.40.'] = blocks_40
    if blocks_41 is not _UNSET:
        _kwargs['blocks.41.'] = blocks_41
    if blocks_42 is not _UNSET:
        _kwargs['blocks.42.'] = blocks_42
    if blocks_43 is not _UNSET:
        _kwargs['blocks.43.'] = blocks_43
    if blocks_44 is not _UNSET:
        _kwargs['blocks.44.'] = blocks_44
    if blocks_45 is not _UNSET:
        _kwargs['blocks.45.'] = blocks_45
    if blocks_46 is not _UNSET:
        _kwargs['blocks.46.'] = blocks_46
    if blocks_47 is not _UNSET:
        _kwargs['blocks.47.'] = blocks_47
    _kwargs.update(_extras)
    return node(wf, 'LTX2BlockLoraSelect', _id, pass_raw=pass_raw, **_kwargs)

def LTX2LoraLoaderAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    lora_name: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    strength_model: float | _Omitted = _UNSET,
    video: float | _Omitted = _UNSET,
    video_to_audio: float | _Omitted = _UNSET,
    audio: float | _Omitted = _UNSET,
    audio_to_video: float | _Omitted = _UNSET,
    other: float | _Omitted = _UNSET,
    opt_lora_path: str | _Omitted = _UNSET,
    blocks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Advanced LoRA loader with per-block strength control for LTX2 models

    Pack: ComfyUI-KJNodes
    Returns: model, rank, loaded_keys_info

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTX2LoraLoaderAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if lora_name is not _UNSET:
        _kwargs['lora_name'] = lora_name
    if model is not _UNSET:
        _kwargs['model'] = model
    if strength_model is not _UNSET:
        _kwargs['strength_model'] = strength_model
    if video is not _UNSET:
        _kwargs['video'] = video
    if video_to_audio is not _UNSET:
        _kwargs['video_to_audio'] = video_to_audio
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if audio_to_video is not _UNSET:
        _kwargs['audio_to_video'] = audio_to_video
    if other is not _UNSET:
        _kwargs['other'] = other
    if opt_lora_path is not _UNSET:
        _kwargs['opt_lora_path'] = opt_lora_path
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    _kwargs.update(_extras)
    return node(wf, 'LTX2LoraLoaderAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def LTX2MemoryEfficientSageAttentionPatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    triton_kernels: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EXPERIMENTAL! Activates custom sageattention to reduce peak VRAM usage, overrides the attention mode. Requires latest sageattention version.

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTX2MemoryEfficientSageAttentionPatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if triton_kernels is not _UNSET:
        _kwargs['triton_kernels'] = triton_kernels
    _kwargs.update(_extras)
    return node(wf, 'LTX2MemoryEfficientSageAttentionPatch', _id, pass_raw=pass_raw, **_kwargs)

def LTX2SamplingPreviewOverride(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    preview_rate: int | _Omitted = _UNSET,
    latent_upscale_model: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Overrides the LTX2 preview sampling preview function, temporary measure until previews are in comfy core

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTX2SamplingPreviewOverride() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if preview_rate is not _UNSET:
        _kwargs['preview_rate'] = preview_rate
    if latent_upscale_model is not _UNSET:
        _kwargs['latent_upscale_model'] = latent_upscale_model
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'LTX2SamplingPreviewOverride', _id, pass_raw=pass_raw, **_kwargs)

def LTX2_NAG(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    nag_scale: float | _Omitted = _UNSET,
    nag_alpha: float | _Omitted = _UNSET,
    nag_tau: float | _Omitted = _UNSET,
    nag_cond_video: Any | _Omitted = _UNSET,
    nag_cond_audio: Any | _Omitted = _UNSET,
    inplace: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/ChenDarYen/Normalized-Attention-Guidance

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTX2_NAG() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if nag_scale is not _UNSET:
        _kwargs['nag_scale'] = nag_scale
    if nag_alpha is not _UNSET:
        _kwargs['nag_alpha'] = nag_alpha
    if nag_tau is not _UNSET:
        _kwargs['nag_tau'] = nag_tau
    if nag_cond_video is not _UNSET:
        _kwargs['nag_cond_video'] = nag_cond_video
    if nag_cond_audio is not _UNSET:
        _kwargs['nag_cond_audio'] = nag_cond_audio
    if inplace is not _UNSET:
        _kwargs['inplace'] = inplace
    _kwargs.update(_extras)
    return node(wf, 'LTX2_NAG', _id, pass_raw=pass_raw, **_kwargs)

def LTXVAudioVideoMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    video_fps: float | _Omitted = _UNSET,
    video_start_time: float | _Omitted = _UNSET,
    video_end_time: float | _Omitted = _UNSET,
    audio_start_time: float | _Omitted = _UNSET,
    audio_end_time: float | _Omitted = _UNSET,
    max_length: Any | _Omitted = _UNSET,
    video_latent: Any | _Omitted = _UNSET,
    audio_latent: Any | _Omitted = _UNSET,
    existing_mask_mode: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates noise masks for video and audio latents based on specified time ranges. New content is generated within these masked regions

    Pack: ComfyUI-KJNodes
    Returns: video_latent, audio_latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVAudioVideoMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video_fps is not _UNSET:
        _kwargs['video_fps'] = video_fps
    if video_start_time is not _UNSET:
        _kwargs['video_start_time'] = video_start_time
    if video_end_time is not _UNSET:
        _kwargs['video_end_time'] = video_end_time
    if audio_start_time is not _UNSET:
        _kwargs['audio_start_time'] = audio_start_time
    if audio_end_time is not _UNSET:
        _kwargs['audio_end_time'] = audio_end_time
    if max_length is not _UNSET:
        _kwargs['max_length'] = max_length
    if video_latent is not _UNSET:
        _kwargs['video_latent'] = video_latent
    if audio_latent is not _UNSET:
        _kwargs['audio_latent'] = audio_latent
    if existing_mask_mode is not _UNSET:
        _kwargs['existing_mask_mode'] = existing_mask_mode
    _kwargs.update(_extras)
    return node(wf, 'LTXVAudioVideoMask', _id, pass_raw=pass_raw, **_kwargs)

def LTXVChunkFeedForward(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    chunks: int | _Omitted = _UNSET,
    dim_threshold: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EXPERIMENTAL AND MAY CHANGE THE MODEL OUTPUT!! Chunks feedforward activations to reduce peak VRAM usage.

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVChunkFeedForward() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if chunks is not _UNSET:
        _kwargs['chunks'] = chunks
    if dim_threshold is not _UNSET:
        _kwargs['dim_threshold'] = dim_threshold
    _kwargs.update(_extras)
    return node(wf, 'LTXVChunkFeedForward', _id, pass_raw=pass_raw, **_kwargs)

def LTXVEnhanceAVideoKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    weight: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVEnhanceAVideoKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if weight is not _UNSET:
        _kwargs['weight'] = weight
    _kwargs.update(_extras)
    return node(wf, 'LTXVEnhanceAVideoKJ', _id, pass_raw=pass_raw, **_kwargs)

def LTXVImgToVideoInplaceKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    num_images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Replaces video latent frames with the encoded input images, uses DynamicCombo which requires ComfyUI 0.8.1 and frontend 1.33.4 or later.

    Pack: ComfyUI-KJNodes
    Returns: latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LTXVImgToVideoInplaceKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if num_images is not _UNSET:
        _kwargs['num_images'] = num_images
    _kwargs.update(_extras)
    return node(wf, 'LTXVImgToVideoInplaceKJ', _id, pass_raw=pass_raw, **_kwargs)

def LatentInpaintTTM(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/time-to-move/TTM

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LatentInpaintTTM() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'LatentInpaintTTM', _id, pass_raw=pass_raw, **_kwargs)

def LazySwitchKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    switch: bool | _Omitted = _UNSET,
    on_false: Any | _Omitted = _UNSET,
    on_true: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Controls flow of execution based on a boolean switch.

    Pack: ComfyUI-KJNodes
    Returns: *

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LazySwitchKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if switch is not _UNSET:
        _kwargs['switch'] = switch
    if on_false is not _UNSET:
        _kwargs['on_false'] = on_false
    if on_true is not _UNSET:
        _kwargs['on_true'] = on_true
    _kwargs.update(_extras)
    return node(wf, 'LazySwitchKJ', _id, pass_raw=pass_raw, **_kwargs)

def LeapfusionHunyuanI2VPatcher(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    index: int | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Leapfusion Hunyuan I2V Patcher

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LeapfusionHunyuanI2VPatcher() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if index is not _UNSET:
        _kwargs['index'] = index
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'LeapfusionHunyuanI2VPatcher', _id, pass_raw=pass_raw, **_kwargs)

def LoadAndResizeImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    resize: bool | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    repeat: int | _Omitted = _UNSET,
    keep_proportion: bool | _Omitted = _UNSET,
    divisible_by: int | _Omitted = _UNSET,
    mask_channel: Literal['alpha', 'red', 'green', 'blue'] | _Omitted = _UNSET,
    background_color: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load & Resize Image

    Pack: ComfyUI-KJNodes
    Returns: image, mask, width, height, image_path

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadAndResizeImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if resize is not _UNSET:
        _kwargs['resize'] = resize
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if repeat is not _UNSET:
        _kwargs['repeat'] = repeat
    if keep_proportion is not _UNSET:
        _kwargs['keep_proportion'] = keep_proportion
    if divisible_by is not _UNSET:
        _kwargs['divisible_by'] = divisible_by
    if mask_channel is not _UNSET:
        _kwargs['mask_channel'] = mask_channel
    if background_color is not _UNSET:
        _kwargs['background_color'] = background_color
    _kwargs.update(_extras)
    return node(wf, 'LoadAndResizeImage', _id, pass_raw=pass_raw, **_kwargs)

def LoadImagesFromFolderKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    folder: str | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    keep_aspect_ratio: Literal['crop', 'pad', 'stretch'] | _Omitted = _UNSET,
    image_load_cap: int | _Omitted = _UNSET,
    start_index: int | _Omitted = _UNSET,
    include_subfolders: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Loads images from a folder into a batch, images are resized and loaded into a batch.

    Pack: ComfyUI-KJNodes
    Returns: image, mask, count, image_path

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadImagesFromFolderKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if folder is not _UNSET:
        _kwargs['folder'] = folder
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if keep_aspect_ratio is not _UNSET:
        _kwargs['keep_aspect_ratio'] = keep_aspect_ratio
    if image_load_cap is not _UNSET:
        _kwargs['image_load_cap'] = image_load_cap
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    if include_subfolders is not _UNSET:
        _kwargs['include_subfolders'] = include_subfolders
    _kwargs.update(_extras)
    return node(wf, 'LoadImagesFromFolderKJ', _id, pass_raw=pass_raw, **_kwargs)

def LoadResAdapterNormalization(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    resadapter_path: Literal['ltx-2.3-22b-distilled-fp8.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors', 'LTX23_audio_vae_bf16.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    LoadResAdapterNormalization

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadResAdapterNormalization() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if resadapter_path is not _UNSET:
        _kwargs['resadapter_path'] = resadapter_path
    _kwargs.update(_extras)
    return node(wf, 'LoadResAdapterNormalization', _id, pass_raw=pass_raw, **_kwargs)

def LoadVideosFromFolder(
    *args: VibeWorkflow,
    _id: str | None = None,
    video: str | _Omitted = _UNSET,
    force_rate: float | _Omitted = _UNSET,
    custom_width: int | _Omitted = _UNSET,
    custom_height: int | _Omitted = _UNSET,
    frame_load_cap: int | _Omitted = _UNSET,
    skip_first_frames: int | _Omitted = _UNSET,
    select_every_nth: int | _Omitted = _UNSET,
    output_type: Literal['batch', 'grid'] | _Omitted = _UNSET,
    grid_max_columns: int | _Omitted = _UNSET,
    add_label: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Videos From Folder

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoadVideosFromFolder() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if video is not _UNSET:
        _kwargs['video'] = video
    if force_rate is not _UNSET:
        _kwargs['force_rate'] = force_rate
    if custom_width is not _UNSET:
        _kwargs['custom_width'] = custom_width
    if custom_height is not _UNSET:
        _kwargs['custom_height'] = custom_height
    if frame_load_cap is not _UNSET:
        _kwargs['frame_load_cap'] = frame_load_cap
    if skip_first_frames is not _UNSET:
        _kwargs['skip_first_frames'] = skip_first_frames
    if select_every_nth is not _UNSET:
        _kwargs['select_every_nth'] = select_every_nth
    if output_type is not _UNSET:
        _kwargs['output_type'] = output_type
    if grid_max_columns is not _UNSET:
        _kwargs['grid_max_columns'] = grid_max_columns
    if add_label is not _UNSET:
        _kwargs['add_label'] = add_label
    _kwargs.update(_extras)
    return node(wf, 'LoadVideosFromFolder', _id, pass_raw=pass_raw, **_kwargs)

def LoraExtractKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    finetuned: Any | _Omitted = _UNSET,
    original: Any | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    rank: int | _Omitted = _UNSET,
    lora_type: Any | _Omitted = _UNSET,
    algorithm: Any | _Omitted = _UNSET,
    lowrank_iters: int | _Omitted = _UNSET,
    output_dtype: Any | _Omitted = _UNSET,
    bias_diff: bool | _Omitted = _UNSET,
    adaptive_param: float | _Omitted = _UNSET,
    clamp_quantile: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: ComfyUI-KJNodes
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoraExtractKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if finetuned is not _UNSET:
        _kwargs['finetuned'] = finetuned
    if original is not _UNSET:
        _kwargs['original'] = original
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    if rank is not _UNSET:
        _kwargs['rank'] = rank
    if lora_type is not _UNSET:
        _kwargs['lora_type'] = lora_type
    if algorithm is not _UNSET:
        _kwargs['algorithm'] = algorithm
    if lowrank_iters is not _UNSET:
        _kwargs['lowrank_iters'] = lowrank_iters
    if output_dtype is not _UNSET:
        _kwargs['output_dtype'] = output_dtype
    if bias_diff is not _UNSET:
        _kwargs['bias_diff'] = bias_diff
    if adaptive_param is not _UNSET:
        _kwargs['adaptive_param'] = adaptive_param
    if clamp_quantile is not _UNSET:
        _kwargs['clamp_quantile'] = clamp_quantile
    _kwargs.update(_extras)
    return node(wf, 'LoraExtractKJ', _id, pass_raw=pass_raw, **_kwargs)

def LoraReduceRankKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    lora_name: Any | _Omitted = _UNSET,
    new_rank: int | _Omitted = _UNSET,
    dynamic_method: Any | _Omitted = _UNSET,
    dynamic_param: float | _Omitted = _UNSET,
    output_dtype: Any | _Omitted = _UNSET,
    verbose: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Resize a LoRA model by reducing its rank. Based on kohya's sd-scripts: https://github.com/kohya-ss/sd-scripts/blob/main/networks/resize_lora.py

    Pack: ComfyUI-KJNodes
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"LoraReduceRankKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if lora_name is not _UNSET:
        _kwargs['lora_name'] = lora_name
    if new_rank is not _UNSET:
        _kwargs['new_rank'] = new_rank
    if dynamic_method is not _UNSET:
        _kwargs['dynamic_method'] = dynamic_method
    if dynamic_param is not _UNSET:
        _kwargs['dynamic_param'] = dynamic_param
    if output_dtype is not _UNSET:
        _kwargs['output_dtype'] = output_dtype
    if verbose is not _UNSET:
        _kwargs['verbose'] = verbose
    _kwargs.update(_extras)
    return node(wf, 'LoraReduceRankKJ', _id, pass_raw=pass_raw, **_kwargs)

def MaskBatchMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: int | _Omitted = _UNSET,
    mask_1: Any | _Omitted = _UNSET,
    mask_2: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates an image batch from multiple masks.
    You can set how many inputs the node has,
    with the **inputcount** and clicking update.

    Pack: ComfyUI-KJNodes
    Returns: masks

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MaskBatchMulti() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if inputcount is not _UNSET:
        _kwargs['inputcount'] = inputcount
    if mask_1 is not _UNSET:
        _kwargs['mask_1'] = mask_1
    if mask_2 is not _UNSET:
        _kwargs['mask_2'] = mask_2
    _kwargs.update(_extras)
    return node(wf, 'MaskBatchMulti', _id, pass_raw=pass_raw, **_kwargs)

def MaskOrImageToWeight(
    *args: VibeWorkflow,
    _id: str | None = None,
    output_type: Literal['list', 'pandas series', 'tensor', 'string'] | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    masks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Gets the mean values from mask or image batch
    and returns that as the selected output type.

    Pack: ComfyUI-KJNodes
    Returns: FLOAT, STRING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MaskOrImageToWeight() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if output_type is not _UNSET:
        _kwargs['output_type'] = output_type
    if images is not _UNSET:
        _kwargs['images'] = images
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    _kwargs.update(_extras)
    return node(wf, 'MaskOrImageToWeight', _id, pass_raw=pass_raw, **_kwargs)

def MergeImageChannels(
    *args: VibeWorkflow,
    _id: str | None = None,
    red: Any | _Omitted = _UNSET,
    green: Any | _Omitted = _UNSET,
    blue: Any | _Omitted = _UNSET,
    alpha: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Merges channel data into an image.

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"MergeImageChannels() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if red is not _UNSET:
        _kwargs['red'] = red
    if green is not _UNSET:
        _kwargs['green'] = green
    if blue is not _UNSET:
        _kwargs['blue'] = blue
    if alpha is not _UNSET:
        _kwargs['alpha'] = alpha
    _kwargs.update(_extras)
    return node(wf, 'MergeImageChannels', _id, pass_raw=pass_raw, **_kwargs)

def ModelMemoryUsageFactorOverride(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    memory_usage_factor: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Overrides the memory usage factor of the model during sampling.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ModelMemoryUsageFactorOverride() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if memory_usage_factor is not _UNSET:
        _kwargs['memory_usage_factor'] = memory_usage_factor
    _kwargs.update(_extras)
    return node(wf, 'ModelMemoryUsageFactorOverride', _id, pass_raw=pass_raw, **_kwargs)

def ModelMemoryUseReportPatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds callbacks to model to report memory usage during after sampling

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ModelMemoryUseReportPatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'ModelMemoryUseReportPatch', _id, pass_raw=pass_raw, **_kwargs)

def ModelPassThrough(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Simply passes through the model,
        workaround for Set node not allowing bypassed inputs.

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ModelPassThrough() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'ModelPassThrough', _id, pass_raw=pass_raw, **_kwargs)

def ModelPatchTorchSettings(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    enable_fp16_accumulation: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Adds callbacks to model to set torch settings before and after running the model.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ModelPatchTorchSettings() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if enable_fp16_accumulation is not _UNSET:
        _kwargs['enable_fp16_accumulation'] = enable_fp16_accumulation
    _kwargs.update(_extras)
    return node(wf, 'ModelPatchTorchSettings', _id, pass_raw=pass_raw, **_kwargs)

def ModelSaveKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    model_key_prefix: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Model Save KJ

    Pack: ComfyUI-KJNodes
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ModelSaveKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    if model_key_prefix is not _UNSET:
        _kwargs['model_key_prefix'] = model_key_prefix
    _kwargs.update(_extras)
    return node(wf, 'ModelSaveKJ', _id, pass_raw=pass_raw, **_kwargs)

def NABLA_AttentionKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    window_time: int | _Omitted = _UNSET,
    window_width: int | _Omitted = _UNSET,
    window_height: int | _Omitted = _UNSET,
    sparsity: float | _Omitted = _UNSET,
    torch_compile: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Experimental node for patching attention mode to use NABLA sparse attention for video models, currently only works with Kadinsky5

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"NABLA_AttentionKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if window_time is not _UNSET:
        _kwargs['window_time'] = window_time
    if window_width is not _UNSET:
        _kwargs['window_width'] = window_width
    if window_height is not _UNSET:
        _kwargs['window_height'] = window_height
    if sparsity is not _UNSET:
        _kwargs['sparsity'] = sparsity
    if torch_compile is not _UNSET:
        _kwargs['torch_compile'] = torch_compile
    _kwargs.update(_extras)
    return node(wf, 'NABLA_AttentionKJ', _id, pass_raw=pass_raw, **_kwargs)

def NormalizedAmplitudeToFloatList(
    *args: VibeWorkflow,
    _id: str | None = None,
    normalized_amp: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Works as a bridge to the AudioScheduler -nodes:
    https://github.com/a1lazydog/ComfyUI-AudioScheduler
    Creates a list of floats from the normalized amplitude.

    Pack: ComfyUI-KJNodes
    Returns: FLOAT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"NormalizedAmplitudeToFloatList() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if normalized_amp is not _UNSET:
        _kwargs['normalized_amp'] = normalized_amp
    _kwargs.update(_extras)
    return node(wf, 'NormalizedAmplitudeToFloatList', _id, pass_raw=pass_raw, **_kwargs)

def NormalizedAmplitudeToMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    normalized_amp: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    frame_offset: int | _Omitted = _UNSET,
    location_x: int | _Omitted = _UNSET,
    location_y: int | _Omitted = _UNSET,
    size: int | _Omitted = _UNSET,
    shape: Literal['none', 'circle', 'square', 'triangle'] | _Omitted = _UNSET,
    color: Literal['white', 'amplitude'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Works as a bridge to the AudioScheduler -nodes:
    https://github.com/a1lazydog/ComfyUI-AudioScheduler
    Creates masks based on the normalized amplitude.

    Pack: ComfyUI-KJNodes
    Returns: MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"NormalizedAmplitudeToMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if normalized_amp is not _UNSET:
        _kwargs['normalized_amp'] = normalized_amp
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if frame_offset is not _UNSET:
        _kwargs['frame_offset'] = frame_offset
    if location_x is not _UNSET:
        _kwargs['location_x'] = location_x
    if location_y is not _UNSET:
        _kwargs['location_y'] = location_y
    if size is not _UNSET:
        _kwargs['size'] = size
    if shape is not _UNSET:
        _kwargs['shape'] = shape
    if color is not _UNSET:
        _kwargs['color'] = color
    _kwargs.update(_extras)
    return node(wf, 'NormalizedAmplitudeToMask', _id, pass_raw=pass_raw, **_kwargs)

def OffsetMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    x: int | _Omitted = _UNSET,
    y: int | _Omitted = _UNSET,
    angle: int | _Omitted = _UNSET,
    duplication_factor: int | _Omitted = _UNSET,
    roll: bool | _Omitted = _UNSET,
    incremental: bool | _Omitted = _UNSET,
    padding_mode: Literal['empty', 'border', 'reflection'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Offsets the mask by the specified amount.
     - mask: Input mask or mask batch
     - x: Horizontal offset
     - y: Vertical offset
     - angle: Angle in degrees
     - roll: roll edge wrapping
     - duplication_factor: Number of times to duplicate the mask to form a batch
     - border padding_mode: Padding mode for the mask

    Pack: ComfyUI-KJNodes
    Returns: mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"OffsetMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if x is not _UNSET:
        _kwargs['x'] = x
    if y is not _UNSET:
        _kwargs['y'] = y
    if angle is not _UNSET:
        _kwargs['angle'] = angle
    if duplication_factor is not _UNSET:
        _kwargs['duplication_factor'] = duplication_factor
    if roll is not _UNSET:
        _kwargs['roll'] = roll
    if incremental is not _UNSET:
        _kwargs['incremental'] = incremental
    if padding_mode is not _UNSET:
        _kwargs['padding_mode'] = padding_mode
    _kwargs.update(_extras)
    return node(wf, 'OffsetMask', _id, pass_raw=pass_raw, **_kwargs)

def OffsetMaskByNormalizedAmplitude(
    *args: VibeWorkflow,
    _id: str | None = None,
    normalized_amp: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    x: int | _Omitted = _UNSET,
    y: int | _Omitted = _UNSET,
    rotate: bool | _Omitted = _UNSET,
    angle_multiplier: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Works as a bridge to the AudioScheduler -nodes:
    https://github.com/a1lazydog/ComfyUI-AudioScheduler
    Offsets masks based on the normalized amplitude.

    Pack: ComfyUI-KJNodes
    Returns: mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"OffsetMaskByNormalizedAmplitude() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if normalized_amp is not _UNSET:
        _kwargs['normalized_amp'] = normalized_amp
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if x is not _UNSET:
        _kwargs['x'] = x
    if y is not _UNSET:
        _kwargs['y'] = y
    if rotate is not _UNSET:
        _kwargs['rotate'] = rotate
    if angle_multiplier is not _UNSET:
        _kwargs['angle_multiplier'] = angle_multiplier
    _kwargs.update(_extras)
    return node(wf, 'OffsetMaskByNormalizedAmplitude', _id, pass_raw=pass_raw, **_kwargs)

def PadImageBatchInterleaved(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    empty_frames_per_image: int | _Omitted = _UNSET,
    pad_frame_value: float | _Omitted = _UNSET,
    add_after_last: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Inserts empty frames between the images in a batch.

    Pack: ComfyUI-KJNodes
    Returns: images, masks

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PadImageBatchInterleaved() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if empty_frames_per_image is not _UNSET:
        _kwargs['empty_frames_per_image'] = empty_frames_per_image
    if pad_frame_value is not _UNSET:
        _kwargs['pad_frame_value'] = pad_frame_value
    if add_after_last is not _UNSET:
        _kwargs['add_after_last'] = add_after_last
    _kwargs.update(_extras)
    return node(wf, 'PadImageBatchInterleaved', _id, pass_raw=pass_raw, **_kwargs)

def PatchModelPatcherOrder(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    patch_order: Literal['object_patch_first', 'weight_patch_first'] | _Omitted = _UNSET,
    full_load: Literal['enabled', 'disabled', 'auto'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    NO LONGER NECESSARY OR FUNCTIONAL, keeping node for backwards compatibility. Use the TorchCompileModelAdvanced to use LoRA with torch.compile.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PatchModelPatcherOrder() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if patch_order is not _UNSET:
        _kwargs['patch_order'] = patch_order
    if full_load is not _UNSET:
        _kwargs['full_load'] = full_load
    _kwargs.update(_extras)
    return node(wf, 'PatchModelPatcherOrder', _id, pass_raw=pass_raw, **_kwargs)

def PathchSageAttentionKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    sage_attention: Literal['disabled', 'auto', 'sageattn_qk_int8_pv_fp16_cuda', 'sageattn_qk_int8_pv_fp16_triton', 'sageattn_qk_int8_pv_fp8_cuda', 'sageattn_qk_int8_pv_fp8_cuda++', 'sageattn3', 'sageattn3_per_block_mean'] | _Omitted = _UNSET,
    allow_compile: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Experimental node for patching attention mode. This doesn't use the model patching system and thus can't be disabled without running the node again with 'disabled' option.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PathchSageAttentionKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if sage_attention is not _UNSET:
        _kwargs['sage_attention'] = sage_attention
    if allow_compile is not _UNSET:
        _kwargs['allow_compile'] = allow_compile
    _kwargs.update(_extras)
    return node(wf, 'PathchSageAttentionKJ', _id, pass_raw=pass_raw, **_kwargs)

def PlaySoundKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio_path: str | _Omitted = _UNSET,
    mode: Any | _Omitted = _UNSET,
    volume: float | _Omitted = _UNSET,
    duration: float | _Omitted = _UNSET,
    any_input: Any | _Omitted = _UNSET,
    audio: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Plays the input audio in the browser. Modes: 'always' plays on every execution, 'on_empty_queue' plays only when the queue finishes, 'on_change' plays only when the audio content changes. Duration limits playback length (0 = full audio).

    Pack: ComfyUI-KJNodes
    Returns: any_output

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PlaySoundKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio_path is not _UNSET:
        _kwargs['audio_path'] = audio_path
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if volume is not _UNSET:
        _kwargs['volume'] = volume
    if duration is not _UNSET:
        _kwargs['duration'] = duration
    if any_input is not _UNSET:
        _kwargs['any_input'] = any_input
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    _kwargs.update(_extras)
    return node(wf, 'PlaySoundKJ', _id, pass_raw=pass_raw, **_kwargs)

def PlotCoordinates(
    *args: VibeWorkflow,
    _id: str | None = None,
    coordinates: str | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    bbox_width: int | _Omitted = _UNSET,
    bbox_height: int | _Omitted = _UNSET,
    size_multiplier: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Plots coordinates to sequence of images using Matplotlib.

    Pack: ComfyUI-KJNodes
    Returns: images, width, height, bbox_width, bbox_height

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PlotCoordinates() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if text is not _UNSET:
        _kwargs['text'] = text
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if bbox_width is not _UNSET:
        _kwargs['bbox_width'] = bbox_width
    if bbox_height is not _UNSET:
        _kwargs['bbox_height'] = bbox_height
    if size_multiplier is not _UNSET:
        _kwargs['size_multiplier'] = size_multiplier
    _kwargs.update(_extras)
    return node(wf, 'PlotCoordinates', _id, pass_raw=pass_raw, **_kwargs)

def PointsEditor(
    *args: VibeWorkflow,
    _id: str | None = None,
    points_store: str | _Omitted = _UNSET,
    coordinates: str | _Omitted = _UNSET,
    neg_coordinates: str | _Omitted = _UNSET,
    bbox_store: str | _Omitted = _UNSET,
    bboxes: str | _Omitted = _UNSET,
    bbox_format: Literal['xyxy', 'xywh'] | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    normalize: bool | _Omitted = _UNSET,
    bg_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    # WORK IN PROGRESS
    Do not count on this as part of your workflow yet,
    probably contains lots of bugs and stability is not
    guaranteed!!

    ## Graphical editor to create coordinates

    **Shift + click** to add a positive (green) point.
    **Shift + right click** to add a negative (red) point.
    **Right click on a point** to delete it.
    **Ctrl + click** to draw a bounding box.
    **Drag bbox corners** to resize, **drag inside** to move.
    **Right click on bbox** to delete it.

    To add an image select the node and copy/paste or drag in the image.
    Or from the bg_image input on queue (first frame of the batch).

    **THE IMAGE IS SAVED TO THE NODE AND WORKFLOW METADATA**
    you can clear the image from the context menu by right clicking on the canvas

    Pack: ComfyUI-KJNodes
    Returns: positive_coords, negative_coords, bbox, bbox_mask, cropped_image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PointsEditor() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if points_store is not _UNSET:
        _kwargs['points_store'] = points_store
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if neg_coordinates is not _UNSET:
        _kwargs['neg_coordinates'] = neg_coordinates
    if bbox_store is not _UNSET:
        _kwargs['bbox_store'] = bbox_store
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    if bbox_format is not _UNSET:
        _kwargs['bbox_format'] = bbox_format
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if normalize is not _UNSET:
        _kwargs['normalize'] = normalize
    if bg_image is not _UNSET:
        _kwargs['bg_image'] = bg_image
    _kwargs.update(_extras)
    return node(wf, 'PointsEditor', _id, pass_raw=pass_raw, **_kwargs)

def PreviewAnimation(
    *args: VibeWorkflow,
    _id: str | None = None,
    fps: float | _Omitted = _UNSET,
    images: Any | _Omitted = _UNSET,
    masks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preview Animation

    Pack: ComfyUI-KJNodes
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PreviewAnimation() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    if images is not _UNSET:
        _kwargs['images'] = images
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    _kwargs.update(_extras)
    return node(wf, 'PreviewAnimation', _id, pass_raw=pass_raw, **_kwargs)

def PreviewImageOrMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    input: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Previews the input images or masks.

    Pack: ComfyUI-KJNodes
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PreviewImageOrMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input is not _UNSET:
        _kwargs['input'] = input
    _kwargs.update(_extras)
    return node(wf, 'PreviewImageOrMask', _id, pass_raw=pass_raw, **_kwargs)

def PreviewLatentNoiseMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Previews the latent noise mask

    Pack: ComfyUI-KJNodes
    Returns: mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"PreviewLatentNoiseMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    _kwargs.update(_extras)
    return node(wf, 'PreviewLatentNoiseMask', _id, pass_raw=pass_raw, **_kwargs)

def RemapImageRange(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    min: float | _Omitted = _UNSET,
    max: float | _Omitted = _UNSET,
    clamp: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Remaps the image values to the specified range.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"RemapImageRange() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if min is not _UNSET:
        _kwargs['min'] = min
    if max is not _UNSET:
        _kwargs['max'] = max
    if clamp is not _UNSET:
        _kwargs['clamp'] = clamp
    _kwargs.update(_extras)
    return node(wf, 'RemapImageRange', _id, pass_raw=pass_raw, **_kwargs)

def RemapMaskRange(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    min: float | _Omitted = _UNSET,
    max: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Sets new min and max values for the mask.

    Pack: ComfyUI-KJNodes
    Returns: mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"RemapMaskRange() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if min is not _UNSET:
        _kwargs['min'] = min
    if max is not _UNSET:
        _kwargs['max'] = max
    _kwargs.update(_extras)
    return node(wf, 'RemapMaskRange', _id, pass_raw=pass_raw, **_kwargs)

def ReplaceImagesInBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    start_index: int | _Omitted = _UNSET,
    original_images: Any | _Omitted = _UNSET,
    replacement_images: Any | _Omitted = _UNSET,
    original_masks: Any | _Omitted = _UNSET,
    replacement_masks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Replaces the images in a batch, starting from the specified start index,
    with the replacement images.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE, MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ReplaceImagesInBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    if original_images is not _UNSET:
        _kwargs['original_images'] = original_images
    if replacement_images is not _UNSET:
        _kwargs['replacement_images'] = replacement_images
    if original_masks is not _UNSET:
        _kwargs['original_masks'] = original_masks
    if replacement_masks is not _UNSET:
        _kwargs['replacement_masks'] = replacement_masks
    _kwargs.update(_extras)
    return node(wf, 'ReplaceImagesInBatch', _id, pass_raw=pass_raw, **_kwargs)

def ResizeMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    keep_proportions: bool | _Omitted = _UNSET,
    upscale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos'] | _Omitted = _UNSET,
    crop: Literal['disabled', 'center'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Resizes the mask or batch of masks to the specified width and height.

    Pack: ComfyUI-KJNodes
    Returns: mask, width, height

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ResizeMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if keep_proportions is not _UNSET:
        _kwargs['keep_proportions'] = keep_proportions
    if upscale_method is not _UNSET:
        _kwargs['upscale_method'] = upscale_method
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    _kwargs.update(_extras)
    return node(wf, 'ResizeMask', _id, pass_raw=pass_raw, **_kwargs)

def ReverseImageBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Reverses the order of the images in a batch.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ReverseImageBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    _kwargs.update(_extras)
    return node(wf, 'ReverseImageBatch', _id, pass_raw=pass_raw, **_kwargs)

def RoundMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Rounds the mask or batch of masks to a binary mask.
    <img src="https://github.com/kijai/ComfyUI-KJNodes/assets/40791699/52c85202-f74e-4b96-9dac-c8bda5ddcc40" width="300" height="250" alt="RoundMask example">

    Pack: ComfyUI-KJNodes
    Returns: MASK

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"RoundMask() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs.update(_extras)
    return node(wf, 'RoundMask', _id, pass_raw=pass_raw, **_kwargs)

def SV3D_BatchSchedule(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_vision: Any | _Omitted = _UNSET,
    init_image: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out'] | _Omitted = _UNSET,
    azimuth_points_string: str | _Omitted = _UNSET,
    elevation_points_string: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Allow scheduling of the azimuth and elevation conditions for SV3D.
    Note that SV3D is still a video model and the schedule needs to always go forward
    https://huggingface.co/stabilityai/sv3d

    Pack: ComfyUI-KJNodes
    Returns: positive, negative, latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SV3D_BatchSchedule() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip_vision is not _UNSET:
        _kwargs['clip_vision'] = clip_vision
    if init_image is not _UNSET:
        _kwargs['init_image'] = init_image
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if azimuth_points_string is not _UNSET:
        _kwargs['azimuth_points_string'] = azimuth_points_string
    if elevation_points_string is not _UNSET:
        _kwargs['elevation_points_string'] = elevation_points_string
    _kwargs.update(_extras)
    return node(wf, 'SV3D_BatchSchedule', _id, pass_raw=pass_raw, **_kwargs)

def SamplerSelfRefineVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    input_mode: Any | _Omitted = _UNSET,
    certain_percentage: float | _Omitted = _UNSET,
    uncertainty_threshold: float | _Omitted = _UNSET,
    verbose: bool | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Attempt to implement https://github.com/agwmon/self-refine-video, for testing only, MAY NOT WORK AS INTENDED.

    Pack: ComfyUI-KJNodes
    Returns: SAMPLER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SamplerSelfRefineVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input_mode is not _UNSET:
        _kwargs['input_mode'] = input_mode
    if certain_percentage is not _UNSET:
        _kwargs['certain_percentage'] = certain_percentage
    if uncertainty_threshold is not _UNSET:
        _kwargs['uncertainty_threshold'] = uncertainty_threshold
    if verbose is not _UNSET:
        _kwargs['verbose'] = verbose
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    _kwargs.update(_extras)
    return node(wf, 'SamplerSelfRefineVideo', _id, pass_raw=pass_raw, **_kwargs)

def SaveImageKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    output_folder: str | _Omitted = _UNSET,
    caption_file_extension: str | _Omitted = _UNSET,
    caption: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input images to your ComfyUI output directory.

    Pack: ComfyUI-KJNodes
    Returns: filename

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SaveImageKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    if output_folder is not _UNSET:
        _kwargs['output_folder'] = output_folder
    if caption_file_extension is not _UNSET:
        _kwargs['caption_file_extension'] = caption_file_extension
    if caption is not _UNSET:
        _kwargs['caption'] = caption
    _kwargs.update(_extras)
    return node(wf, 'SaveImageKJ', _id, pass_raw=pass_raw, **_kwargs)

def SaveImageWithAlpha(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves an image and mask as .PNG with the mask as the alpha channel.

    Pack: ComfyUI-KJNodes
    Returns: None

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SaveImageWithAlpha() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    _kwargs.update(_extras)
    return node(wf, 'SaveImageWithAlpha', _id, pass_raw=pass_raw, **_kwargs)

def SaveStringKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    string: str | _Omitted = _UNSET,
    filename_prefix: str | _Omitted = _UNSET,
    output_folder: str | _Omitted = _UNSET,
    file_extension: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Saves the input string to your ComfyUI output directory.

    Pack: ComfyUI-KJNodes
    Returns: filename

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SaveStringKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if string is not _UNSET:
        _kwargs['string'] = string
    if filename_prefix is not _UNSET:
        _kwargs['filename_prefix'] = filename_prefix
    if output_folder is not _UNSET:
        _kwargs['output_folder'] = output_folder
    if file_extension is not _UNSET:
        _kwargs['file_extension'] = file_extension
    _kwargs.update(_extras)
    return node(wf, 'SaveStringKJ', _id, pass_raw=pass_raw, **_kwargs)

def ScaleBatchPromptSchedule(
    *args: VibeWorkflow,
    _id: str | None = None,
    input_str: str | _Omitted = _UNSET,
    old_frame_count: int | _Omitted = _UNSET,
    new_frame_count: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Scales a batch schedule from Fizz' nodes BatchPromptSchedule
    to a different frame count.

    Pack: ComfyUI-KJNodes
    Returns: STRING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ScaleBatchPromptSchedule() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input_str is not _UNSET:
        _kwargs['input_str'] = input_str
    if old_frame_count is not _UNSET:
        _kwargs['old_frame_count'] = old_frame_count
    if new_frame_count is not _UNSET:
        _kwargs['new_frame_count'] = new_frame_count
    _kwargs.update(_extras)
    return node(wf, 'ScaleBatchPromptSchedule', _id, pass_raw=pass_raw, **_kwargs)

def ScheduledCFGGuidance(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Scheduled CFG Guidance

    Pack: ComfyUI-KJNodes
    Returns: GUIDER

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ScheduledCFGGuidance() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'ScheduledCFGGuidance', _id, pass_raw=pass_raw, **_kwargs)

def ScreencapStream(
    *args: VibeWorkflow,
    _id: str | None = None,
    frame_data: str | _Omitted = _UNSET,
    crop_width: int | _Omitted = _UNSET,
    crop_height: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Captures a frame from a browser screen/window share stream.
    Click 'Start capture' to select a screen or window to share.
    Live preview is shown in the node. Works with auto-queue.

    Crop controls:
    - Drag on preview to draw a crop box
    - Drag inside the box to move it
    - Drag edges or corners to resize
    - Shift+drag to lock aspect ratio
    - Right-click or double-click to clear crop

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ScreencapStream() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if frame_data is not _UNSET:
        _kwargs['frame_data'] = frame_data
    if crop_width is not _UNSET:
        _kwargs['crop_width'] = crop_width
    if crop_height is not _UNSET:
        _kwargs['crop_height'] = crop_height
    _kwargs.update(_extras)
    return node(wf, 'ScreencapStream', _id, pass_raw=pass_raw, **_kwargs)

def Screencap_mss(
    *args: VibeWorkflow,
    _id: str | None = None,
    x: int | _Omitted = _UNSET,
    y: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    delay: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Captures an area specified by screen coordinates.
    Can be used for realtime diffusion with autoqueue.

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Screencap_mss() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if x is not _UNSET:
        _kwargs['x'] = x
    if y is not _UNSET:
        _kwargs['y'] = y
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if delay is not _UNSET:
        _kwargs['delay'] = delay
    _kwargs.update(_extras)
    return node(wf, 'Screencap_mss', _id, pass_raw=pass_raw, **_kwargs)

def SeparateMasks(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    size_threshold_width: int | _Omitted = _UNSET,
    size_threshold_height: int | _Omitted = _UNSET,
    mode: Literal['convex_polygons', 'area', 'box'] | _Omitted = _UNSET,
    max_poly_points: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Separates a mask into multiple masks based on the size of the connected components.

    Pack: ComfyUI-KJNodes
    Returns: mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SeparateMasks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if size_threshold_width is not _UNSET:
        _kwargs['size_threshold_width'] = size_threshold_width
    if size_threshold_height is not _UNSET:
        _kwargs['size_threshold_height'] = size_threshold_height
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if max_poly_points is not _UNSET:
        _kwargs['max_poly_points'] = max_poly_points
    _kwargs.update(_extras)
    return node(wf, 'SeparateMasks', _id, pass_raw=pass_raw, **_kwargs)

def SetShakkerLabsUnionControlNetType(
    *args: VibeWorkflow,
    _id: str | None = None,
    control_net: Any | _Omitted = _UNSET,
    type_: Literal['auto', 'canny', 'tile', 'depth', 'blur', 'pose', 'gray', 'low quality'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Set Shakker Labs Union ControlNet Type

    Pack: ComfyUI-KJNodes
    Returns: CONTROL_NET

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SetShakkerLabsUnionControlNetType() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if control_net is not _UNSET:
        _kwargs['control_net'] = control_net
    if type_ is not _UNSET:
        _kwargs['type'] = type_
    _kwargs.update(_extras)
    return node(wf, 'SetShakkerLabsUnionControlNetType', _id, pass_raw=pass_raw, **_kwargs)

def ShuffleImageBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Shuffle Image Batch

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"ShuffleImageBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'ShuffleImageBatch', _id, pass_raw=pass_raw, **_kwargs)

def SigmasToFloat(
    *args: VibeWorkflow,
    _id: str | None = None,
    sigmas: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a float list from sigmas tensors.

    Pack: ComfyUI-KJNodes
    Returns: float

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SigmasToFloat() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    _kwargs.update(_extras)
    return node(wf, 'SigmasToFloat', _id, pass_raw=pass_raw, **_kwargs)

def SimpleCalculatorKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    expression: str | _Omitted = _UNSET,
    variables: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Calculator node that evaluates a mathematical expression using inputs a and b.
        Supported operations: +, -, *, /, //, %, **, <<, >>, unary +/-
        Supported comparisons: ==, !=, <, <=, >, >=
        Supported logic: and, or, not
        Supported functions: abs(), round(), min(), max(), pow(), sqrt(), sin(), cos(), tan(), log(), log10(), exp(), floor(), ceil()
        Supported constants: pi, euler, True, False

    Pack: ComfyUI-KJNodes
    Returns: FLOAT, INT, BOOLEAN

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SimpleCalculatorKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if expression is not _UNSET:
        _kwargs['expression'] = expression
    if variables is not _UNSET:
        _kwargs['variables'] = variables
    _kwargs.update(_extras)
    return node(wf, 'SimpleCalculatorKJ', _id, pass_raw=pass_raw, **_kwargs)

def SkipLayerGuidanceWanVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    blocks: str | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Simplified skip layer guidance that only skips the uncond on selected blocks

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SkipLayerGuidanceWanVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    _kwargs.update(_extras)
    return node(wf, 'SkipLayerGuidanceWanVideo', _id, pass_raw=pass_raw, **_kwargs)

def Sleep(
    *args: VibeWorkflow,
    _id: str | None = None,
    input: Any | _Omitted = _UNSET,
    minutes: int | _Omitted = _UNSET,
    seconds: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Delays the execution for the input amount of time.

    Pack: ComfyUI-KJNodes
    Returns: *

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Sleep() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input is not _UNSET:
        _kwargs['input'] = input
    if minutes is not _UNSET:
        _kwargs['minutes'] = minutes
    if seconds is not _UNSET:
        _kwargs['seconds'] = seconds
    _kwargs.update(_extras)
    return node(wf, 'Sleep', _id, pass_raw=pass_raw, **_kwargs)

def SoundReactive(
    *args: VibeWorkflow,
    _id: str | None = None,
    sound_level: float | _Omitted = _UNSET,
    start_range_hz: int | _Omitted = _UNSET,
    end_range_hz: int | _Omitted = _UNSET,
    multiplier: float | _Omitted = _UNSET,
    smoothing_factor: float | _Omitted = _UNSET,
    normalize: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Reacts to the sound level of the input.
    Uses your browsers sound input options and requires.
    Meant to be used with realtime diffusion with autoqueue.

    Pack: ComfyUI-KJNodes
    Returns: sound_level, sound_level_int

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SoundReactive() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if sound_level is not _UNSET:
        _kwargs['sound_level'] = sound_level
    if start_range_hz is not _UNSET:
        _kwargs['start_range_hz'] = start_range_hz
    if end_range_hz is not _UNSET:
        _kwargs['end_range_hz'] = end_range_hz
    if multiplier is not _UNSET:
        _kwargs['multiplier'] = multiplier
    if smoothing_factor is not _UNSET:
        _kwargs['smoothing_factor'] = smoothing_factor
    if normalize is not _UNSET:
        _kwargs['normalize'] = normalize
    _kwargs.update(_extras)
    return node(wf, 'SoundReactive', _id, pass_raw=pass_raw, **_kwargs)

def SplineEditor(
    *args: VibeWorkflow,
    _id: str | None = None,
    points_store: str | _Omitted = _UNSET,
    coordinates: str | _Omitted = _UNSET,
    mask_width: int | _Omitted = _UNSET,
    mask_height: int | _Omitted = _UNSET,
    points_to_sample: int | _Omitted = _UNSET,
    sampling_method: Literal['path', 'time', 'controlpoints', 'speed'] | _Omitted = _UNSET,
    interpolation: Literal['cardinal', 'monotone', 'basis', 'linear', 'step-before', 'step-after', 'polar', 'polar-reverse', 'bezier'] | _Omitted = _UNSET,
    tension: float | _Omitted = _UNSET,
    repeat_output: int | _Omitted = _UNSET,
    float_output_type: Literal['list', 'pandas series', 'tensor'] | _Omitted = _UNSET,
    min_value: float | _Omitted = _UNSET,
    max_value: float | _Omitted = _UNSET,
    bg_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    # WORK IN PROGRESS
    Do not count on this as part of your workflow yet,
    probably contains lots of bugs and stability is not
    guaranteed!!

    ## Graphical editor to create values for various
    ## schedules and/or mask batches.

    **Shift + click** to add control point at end.
    **Ctrl + click** to add control point (subdivide) between two points.
    **Right click on a point** to delete it.
    Note that you can't delete from start/end.

    Right click on canvas for context menu:
    NEW!:
    - Add new spline
        - Creates a new spline on same canvas, currently these paths are only outputed
          as coordinates.
    - Add single point
        - Creates a single point that only returns it's current position coords
    - Delete spline
        - Deletes the currently selected spline, you can select a spline by clicking on
        it's path, or cycle through them with the 'Next spline' -option.

    These are purely visual options, doesn't affect the output:
     - Toggle handles visibility
     - Display sample points: display the points to be returned.

    **points_to_sample** value sets the number of samples
    returned from the **drawn spline itself**, this is independent from the
    actual control points, so the interpolation type matters.
    sampling_method:
     - time: samples along the time axis, used for schedules
     - path: samples along the path itself, useful for coordinates
     - controlpoints: samples only the control points themselves

    output types:
     - mask batch
            example compatible nodes: anything that takes masks
     - list of floats
            example compatible nodes: IPAdapter weights
     - pandas series
            example compatible nodes: anything that takes Fizz'
            nodes Batch Value Schedule
     - torch tensor
            example compatible nodes: unknown

    Pack: ComfyUI-KJNodes
    Returns: mask, coord_str, float, count, normalized_str

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SplineEditor() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if points_store is not _UNSET:
        _kwargs['points_store'] = points_store
    if coordinates is not _UNSET:
        _kwargs['coordinates'] = coordinates
    if mask_width is not _UNSET:
        _kwargs['mask_width'] = mask_width
    if mask_height is not _UNSET:
        _kwargs['mask_height'] = mask_height
    if points_to_sample is not _UNSET:
        _kwargs['points_to_sample'] = points_to_sample
    if sampling_method is not _UNSET:
        _kwargs['sampling_method'] = sampling_method
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if tension is not _UNSET:
        _kwargs['tension'] = tension
    if repeat_output is not _UNSET:
        _kwargs['repeat_output'] = repeat_output
    if float_output_type is not _UNSET:
        _kwargs['float_output_type'] = float_output_type
    if min_value is not _UNSET:
        _kwargs['min_value'] = min_value
    if max_value is not _UNSET:
        _kwargs['max_value'] = max_value
    if bg_image is not _UNSET:
        _kwargs['bg_image'] = bg_image
    _kwargs.update(_extras)
    return node(wf, 'SplineEditor', _id, pass_raw=pass_raw, **_kwargs)

def SplitBboxes(
    *args: VibeWorkflow,
    _id: str | None = None,
    bboxes: Any | _Omitted = _UNSET,
    index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Splits the specified bbox list at the given index into two lists.

    Pack: ComfyUI-KJNodes
    Returns: bboxes_a, bboxes_b

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SplitBboxes() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if bboxes is not _UNSET:
        _kwargs['bboxes'] = bboxes
    if index is not _UNSET:
        _kwargs['index'] = index
    _kwargs.update(_extras)
    return node(wf, 'SplitBboxes', _id, pass_raw=pass_raw, **_kwargs)

def SplitImageChannels(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Splits image channels into images where the selected channel
    is repeated for all channels, and the alpha as a mask.

    Pack: ComfyUI-KJNodes
    Returns: red, green, blue, mask

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"SplitImageChannels() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'SplitImageChannels', _id, pass_raw=pass_raw, **_kwargs)

def StableZero123_BatchSchedule(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_vision: Any | _Omitted = _UNSET,
    init_image: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out'] | _Omitted = _UNSET,
    azimuth_points_string: str | _Omitted = _UNSET,
    elevation_points_string: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Stable Zero123 Batch Schedule

    Pack: ComfyUI-KJNodes
    Returns: positive, negative, latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"StableZero123_BatchSchedule() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip_vision is not _UNSET:
        _kwargs['clip_vision'] = clip_vision
    if init_image is not _UNSET:
        _kwargs['init_image'] = init_image
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if azimuth_points_string is not _UNSET:
        _kwargs['azimuth_points_string'] = azimuth_points_string
    if elevation_points_string is not _UNSET:
        _kwargs['elevation_points_string'] = elevation_points_string
    _kwargs.update(_extras)
    return node(wf, 'StableZero123_BatchSchedule', _id, pass_raw=pass_raw, **_kwargs)

def StartRecordCUDAMemoryHistory(
    *args: VibeWorkflow,
    _id: str | None = None,
    input: Any | _Omitted = _UNSET,
    enabled: Literal['all', 'state', 'None'] | _Omitted = _UNSET,
    context: Literal['all', 'state', 'alloc', 'None'] | _Omitted = _UNSET,
    stacks: Literal['python', 'all'] | _Omitted = _UNSET,
    max_entries: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    THIS NODE ALWAYS RUNS. Starts recording CUDA memory allocation history, can be ended and saved with EndRecordCUDAMemoryHistory.

    Pack: ComfyUI-KJNodes
    Returns: input

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"StartRecordCUDAMemoryHistory() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input is not _UNSET:
        _kwargs['input'] = input
    if enabled is not _UNSET:
        _kwargs['enabled'] = enabled
    if context is not _UNSET:
        _kwargs['context'] = context
    if stacks is not _UNSET:
        _kwargs['stacks'] = stacks
    if max_entries is not _UNSET:
        _kwargs['max_entries'] = max_entries
    _kwargs.update(_extras)
    return node(wf, 'StartRecordCUDAMemoryHistory', _id, pass_raw=pass_raw, **_kwargs)

def StringConstant(
    *args: VibeWorkflow,
    _id: str | None = None,
    string: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    String Constant

    Pack: ComfyUI-KJNodes
    Returns: STRING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"StringConstant() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if string is not _UNSET:
        _kwargs['string'] = string
    _kwargs.update(_extras)
    return node(wf, 'StringConstant', _id, pass_raw=pass_raw, **_kwargs)

def StringConstantMultiline(
    *args: VibeWorkflow,
    _id: str | None = None,
    string: str | _Omitted = _UNSET,
    strip_newlines: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    String Constant Multiline

    Pack: ComfyUI-KJNodes
    Returns: STRING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"StringConstantMultiline() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if string is not _UNSET:
        _kwargs['string'] = string
    if strip_newlines is not _UNSET:
        _kwargs['strip_newlines'] = strip_newlines
    _kwargs.update(_extras)
    return node(wf, 'StringConstantMultiline', _id, pass_raw=pass_raw, **_kwargs)

def StringToFloatList(
    *args: VibeWorkflow,
    _id: str | None = None,
    string: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    String to Float List

    Pack: ComfyUI-KJNodes
    Returns: FLOAT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"StringToFloatList() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if string is not _UNSET:
        _kwargs['string'] = string
    _kwargs.update(_extras)
    return node(wf, 'StringToFloatList', _id, pass_raw=pass_raw, **_kwargs)

def StyleModelApplyAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    conditioning: Any | _Omitted = _UNSET,
    style_model: Any | _Omitted = _UNSET,
    clip_vision_output: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    StyleModelApply but with strength parameter

    Pack: ComfyUI-KJNodes
    Returns: CONDITIONING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"StyleModelApplyAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if conditioning is not _UNSET:
        _kwargs['conditioning'] = conditioning
    if style_model is not _UNSET:
        _kwargs['style_model'] = style_model
    if clip_vision_output is not _UNSET:
        _kwargs['clip_vision_output'] = clip_vision_output
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'StyleModelApplyAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def Superprompt(
    *args: VibeWorkflow,
    _id: str | None = None,
    instruction_prompt: str | _Omitted = _UNSET,
    prompt: str | _Omitted = _UNSET,
    max_new_tokens: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    # SuperPrompt
    A T5 model fine-tuned on the SuperPrompt dataset for
    upsampling text prompts to more detailed descriptions.
    Meant to be used as a pre-generation step for text-to-image
    models that benefit from more detailed prompts.
    https://huggingface.co/roborovski/superprompt-v1

    Pack: ComfyUI-KJNodes
    Returns: STRING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Superprompt() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if instruction_prompt is not _UNSET:
        _kwargs['instruction_prompt'] = instruction_prompt
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    _kwargs.update(_extras)
    return node(wf, 'Superprompt', _id, pass_raw=pass_raw, **_kwargs)

def TimerNodeKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    any_input: Any | _Omitted = _UNSET,
    mode: Literal['start', 'stop'] | _Omitted = _UNSET,
    name: str | _Omitted = _UNSET,
    timer: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Timer Node KJ

    Pack: ComfyUI-KJNodes
    Returns: any_output, timer, time

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TimerNodeKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if any_input is not _UNSET:
        _kwargs['any_input'] = any_input
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if name is not _UNSET:
        _kwargs['name'] = name
    if timer is not _UNSET:
        _kwargs['timer'] = timer
    _kwargs.update(_extras)
    return node(wf, 'TimerNodeKJ', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileControlNet(
    *args: VibeWorkflow,
    _id: str | None = None,
    controlnet: Any | _Omitted = _UNSET,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = _UNSET,
    fullgraph: bool | _Omitted = _UNSET,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    TorchCompileControlNet

    Pack: ComfyUI-KJNodes
    Returns: CONTROL_NET

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileControlNet() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if controlnet is not _UNSET:
        _kwargs['controlnet'] = controlnet
    if backend is not _UNSET:
        _kwargs['backend'] = backend
    if fullgraph is not _UNSET:
        _kwargs['fullgraph'] = fullgraph
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileControlNet', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileCosmosModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.

    Pack: ComfyUI-KJNodes
    Returns: *

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileCosmosModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileCosmosModel', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileLTXModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.

    Pack: ComfyUI-KJNodes
    Returns: *

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileLTXModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileLTXModel', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileModelAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = _UNSET,
    fullgraph: bool | _Omitted = _UNSET,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = _UNSET,
    dynamic: Literal['auto', 'true', 'false'] | _Omitted = _UNSET,
    compile_transformer_blocks_only: bool | _Omitted = _UNSET,
    dynamo_cache_size_limit: int | _Omitted = _UNSET,
    debug_compile_keys: bool | _Omitted = _UNSET,
    disable_dynamic_vram: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Advanced torch.compile patching for diffusion models.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileModelAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if backend is not _UNSET:
        _kwargs['backend'] = backend
    if fullgraph is not _UNSET:
        _kwargs['fullgraph'] = fullgraph
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if dynamic is not _UNSET:
        _kwargs['dynamic'] = dynamic
    if compile_transformer_blocks_only is not _UNSET:
        _kwargs['compile_transformer_blocks_only'] = compile_transformer_blocks_only
    if dynamo_cache_size_limit is not _UNSET:
        _kwargs['dynamo_cache_size_limit'] = dynamo_cache_size_limit
    if debug_compile_keys is not _UNSET:
        _kwargs['debug_compile_keys'] = debug_compile_keys
    if disable_dynamic_vram is not _UNSET:
        _kwargs['disable_dynamic_vram'] = disable_dynamic_vram
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileModelAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileModelFluxAdvanced(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.

    Pack: ComfyUI-KJNodes
    Returns: *

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileModelFluxAdvanced() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileModelFluxAdvanced', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileModelFluxAdvancedV2(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = _UNSET,
    fullgraph: bool | _Omitted = _UNSET,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = _UNSET,
    double_blocks: bool | _Omitted = _UNSET,
    single_blocks: bool | _Omitted = _UNSET,
    dynamic: bool | _Omitted = _UNSET,
    dynamo_cache_size_limit: int | _Omitted = _UNSET,
    force_parameter_static_shapes: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Deprecated, use TorchCompileModelAdvanced instead.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileModelFluxAdvancedV2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if backend is not _UNSET:
        _kwargs['backend'] = backend
    if fullgraph is not _UNSET:
        _kwargs['fullgraph'] = fullgraph
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if double_blocks is not _UNSET:
        _kwargs['double_blocks'] = double_blocks
    if single_blocks is not _UNSET:
        _kwargs['single_blocks'] = single_blocks
    if dynamic is not _UNSET:
        _kwargs['dynamic'] = dynamic
    if dynamo_cache_size_limit is not _UNSET:
        _kwargs['dynamo_cache_size_limit'] = dynamo_cache_size_limit
    if force_parameter_static_shapes is not _UNSET:
        _kwargs['force_parameter_static_shapes'] = force_parameter_static_shapes
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileModelFluxAdvancedV2', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileModelHyVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.

    Pack: ComfyUI-KJNodes
    Returns: *

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileModelHyVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileModelHyVideo', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileModelQwenImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.

    Pack: ComfyUI-KJNodes
    Returns: *

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileModelQwenImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileModelQwenImage', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileModelWanVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    This node has been replaced with TorchCompileModelAdvanced node, please use that instead.

    Pack: ComfyUI-KJNodes
    Returns: *

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileModelWanVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileModelWanVideo', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileModelWanVideoV2(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = _UNSET,
    fullgraph: bool | _Omitted = _UNSET,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = _UNSET,
    dynamic: bool | _Omitted = _UNSET,
    compile_transformer_blocks_only: bool | _Omitted = _UNSET,
    dynamo_cache_size_limit: int | _Omitted = _UNSET,
    force_parameter_static_shapes: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Deprecated, use TorchCompileModelAdvanced instead.

    Pack: ComfyUI-KJNodes
    Returns: MODEL

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileModelWanVideoV2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if backend is not _UNSET:
        _kwargs['backend'] = backend
    if fullgraph is not _UNSET:
        _kwargs['fullgraph'] = fullgraph
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if dynamic is not _UNSET:
        _kwargs['dynamic'] = dynamic
    if compile_transformer_blocks_only is not _UNSET:
        _kwargs['compile_transformer_blocks_only'] = compile_transformer_blocks_only
    if dynamo_cache_size_limit is not _UNSET:
        _kwargs['dynamo_cache_size_limit'] = dynamo_cache_size_limit
    if force_parameter_static_shapes is not _UNSET:
        _kwargs['force_parameter_static_shapes'] = force_parameter_static_shapes
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileModelWanVideoV2', _id, pass_raw=pass_raw, **_kwargs)

def TorchCompileVAE(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any | _Omitted = _UNSET,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = _UNSET,
    fullgraph: bool | _Omitted = _UNSET,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = _UNSET,
    compile_encoder: bool | _Omitted = _UNSET,
    compile_decoder: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    TorchCompileVAE

    Pack: ComfyUI-KJNodes
    Returns: VAE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TorchCompileVAE() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if backend is not _UNSET:
        _kwargs['backend'] = backend
    if fullgraph is not _UNSET:
        _kwargs['fullgraph'] = fullgraph
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if compile_encoder is not _UNSET:
        _kwargs['compile_encoder'] = compile_encoder
    if compile_decoder is not _UNSET:
        _kwargs['compile_decoder'] = compile_decoder
    _kwargs.update(_extras)
    return node(wf, 'TorchCompileVAE', _id, pass_raw=pass_raw, **_kwargs)

def TransitionImagesInBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = _UNSET,
    transition_type: Literal['horizontal slide', 'vertical slide', 'box', 'circle', 'horizontal door', 'vertical door', 'fade'] | _Omitted = _UNSET,
    transitioning_frames: int | _Omitted = _UNSET,
    blur_radius: float | _Omitted = _UNSET,
    reverse: bool | _Omitted = _UNSET,
    device: Literal['CPU', 'GPU'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates transitions between images in a batch.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TransitionImagesInBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if transition_type is not _UNSET:
        _kwargs['transition_type'] = transition_type
    if transitioning_frames is not _UNSET:
        _kwargs['transitioning_frames'] = transitioning_frames
    if blur_radius is not _UNSET:
        _kwargs['blur_radius'] = blur_radius
    if reverse is not _UNSET:
        _kwargs['reverse'] = reverse
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'TransitionImagesInBatch', _id, pass_raw=pass_raw, **_kwargs)

def TransitionImagesMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: int | _Omitted = _UNSET,
    image_1: Any | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out', 'ease_in_out', 'bounce', 'elastic', 'glitchy', 'exponential_ease_out'] | _Omitted = _UNSET,
    transition_type: Literal['horizontal slide', 'vertical slide', 'box', 'circle', 'horizontal door', 'vertical door', 'fade'] | _Omitted = _UNSET,
    transitioning_frames: int | _Omitted = _UNSET,
    blur_radius: float | _Omitted = _UNSET,
    reverse: bool | _Omitted = _UNSET,
    device: Literal['CPU', 'GPU'] | _Omitted = _UNSET,
    image_2: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates transitions between images.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"TransitionImagesMulti() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if inputcount is not _UNSET:
        _kwargs['inputcount'] = inputcount
    if image_1 is not _UNSET:
        _kwargs['image_1'] = image_1
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if transition_type is not _UNSET:
        _kwargs['transition_type'] = transition_type
    if transitioning_frames is not _UNSET:
        _kwargs['transitioning_frames'] = transitioning_frames
    if blur_radius is not _UNSET:
        _kwargs['blur_radius'] = blur_radius
    if reverse is not _UNSET:
        _kwargs['reverse'] = reverse
    if device is not _UNSET:
        _kwargs['device'] = device
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    _kwargs.update(_extras)
    return node(wf, 'TransitionImagesMulti', _id, pass_raw=pass_raw, **_kwargs)

def VAEDecodeLoopKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    overlap_latent_frames: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Video latent VAE decoding to fix artifacts on loop seams.

    Pack: ComfyUI-KJNodes
    Returns: IMAGE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VAEDecodeLoopKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if overlap_latent_frames is not _UNSET:
        _kwargs['overlap_latent_frames'] = overlap_latent_frames
    _kwargs.update(_extras)
    return node(wf, 'VAEDecodeLoopKJ', _id, pass_raw=pass_raw, **_kwargs)

def VAELoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors', 'pixel_space'] | _Omitted = _UNSET,
    device: Literal['main_device', 'cpu'] | _Omitted = _UNSET,
    weight_dtype: Literal['bf16', 'fp16', 'fp32'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VAELoader KJ

    Pack: ComfyUI-KJNodes
    Returns: VAE

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VAELoaderKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vae_name is not _UNSET:
        _kwargs['vae_name'] = vae_name
    if device is not _UNSET:
        _kwargs['device'] = device
    if weight_dtype is not _UNSET:
        _kwargs['weight_dtype'] = weight_dtype
    _kwargs.update(_extras)
    return node(wf, 'VAELoaderKJ', _id, pass_raw=pass_raw, **_kwargs)

def VRAM_Debug(
    *args: VibeWorkflow,
    _id: str | None = None,
    empty_cache: bool | _Omitted = _UNSET,
    gc_collect: bool | _Omitted = _UNSET,
    unload_all_models: bool | _Omitted = _UNSET,
    any_input: Any | _Omitted = _UNSET,
    image_pass: Any | _Omitted = _UNSET,
    model_pass: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns the inputs unchanged, they are only used as triggers,
    and performs comfy model management functions and garbage collection,
    reports free VRAM before and after the operations.

    Pack: ComfyUI-KJNodes
    Returns: any_output, image_pass, model_pass, freemem_before, freemem_after

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VRAM_Debug() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if empty_cache is not _UNSET:
        _kwargs['empty_cache'] = empty_cache
    if gc_collect is not _UNSET:
        _kwargs['gc_collect'] = gc_collect
    if unload_all_models is not _UNSET:
        _kwargs['unload_all_models'] = unload_all_models
    if any_input is not _UNSET:
        _kwargs['any_input'] = any_input
    if image_pass is not _UNSET:
        _kwargs['image_pass'] = image_pass
    if model_pass is not _UNSET:
        _kwargs['model_pass'] = model_pass
    _kwargs.update(_extras)
    return node(wf, 'VRAM_Debug', _id, pass_raw=pass_raw, **_kwargs)

def VisualizeCUDAMemoryHistory(
    *args: VibeWorkflow,
    _id: str | None = None,
    snapshot_path: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Visualizes a CUDA memory allocation history file, opens in browser

    Pack: ComfyUI-KJNodes
    Returns: output_path

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VisualizeCUDAMemoryHistory() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if snapshot_path is not _UNSET:
        _kwargs['snapshot_path'] = snapshot_path
    _kwargs.update(_extras)
    return node(wf, 'VisualizeCUDAMemoryHistory', _id, pass_raw=pass_raw, **_kwargs)

def VisualizeSigmasKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    sigmas: Any | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: ComfyUI-KJNodes
    Returns: sigmas_out, image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"VisualizeSigmasKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    _kwargs.update(_extras)
    return node(wf, 'VisualizeSigmasKJ', _id, pass_raw=pass_raw, **_kwargs)

def Wan21BlockLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = None,
    blocks_0: float | _Omitted = _UNSET,
    blocks_1: float | _Omitted = _UNSET,
    blocks_2: float | _Omitted = _UNSET,
    blocks_3: float | _Omitted = _UNSET,
    blocks_4: float | _Omitted = _UNSET,
    blocks_5: float | _Omitted = _UNSET,
    blocks_6: float | _Omitted = _UNSET,
    blocks_7: float | _Omitted = _UNSET,
    blocks_8: float | _Omitted = _UNSET,
    blocks_9: float | _Omitted = _UNSET,
    blocks_10: float | _Omitted = _UNSET,
    blocks_11: float | _Omitted = _UNSET,
    blocks_12: float | _Omitted = _UNSET,
    blocks_13: float | _Omitted = _UNSET,
    blocks_14: float | _Omitted = _UNSET,
    blocks_15: float | _Omitted = _UNSET,
    blocks_16: float | _Omitted = _UNSET,
    blocks_17: float | _Omitted = _UNSET,
    blocks_18: float | _Omitted = _UNSET,
    blocks_19: float | _Omitted = _UNSET,
    blocks_20: float | _Omitted = _UNSET,
    blocks_21: float | _Omitted = _UNSET,
    blocks_22: float | _Omitted = _UNSET,
    blocks_23: float | _Omitted = _UNSET,
    blocks_24: float | _Omitted = _UNSET,
    blocks_25: float | _Omitted = _UNSET,
    blocks_26: float | _Omitted = _UNSET,
    blocks_27: float | _Omitted = _UNSET,
    blocks_28: float | _Omitted = _UNSET,
    blocks_29: float | _Omitted = _UNSET,
    blocks_30: float | _Omitted = _UNSET,
    blocks_31: float | _Omitted = _UNSET,
    blocks_32: float | _Omitted = _UNSET,
    blocks_33: float | _Omitted = _UNSET,
    blocks_34: float | _Omitted = _UNSET,
    blocks_35: float | _Omitted = _UNSET,
    blocks_36: float | _Omitted = _UNSET,
    blocks_37: float | _Omitted = _UNSET,
    blocks_38: float | _Omitted = _UNSET,
    blocks_39: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Select individual block alpha values, value of 0 removes the block altogether

    Pack: ComfyUI-KJNodes
    Returns: blocks

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Wan21BlockLoraSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if blocks_0 is not _UNSET:
        _kwargs['blocks.0.'] = blocks_0
    if blocks_1 is not _UNSET:
        _kwargs['blocks.1.'] = blocks_1
    if blocks_2 is not _UNSET:
        _kwargs['blocks.2.'] = blocks_2
    if blocks_3 is not _UNSET:
        _kwargs['blocks.3.'] = blocks_3
    if blocks_4 is not _UNSET:
        _kwargs['blocks.4.'] = blocks_4
    if blocks_5 is not _UNSET:
        _kwargs['blocks.5.'] = blocks_5
    if blocks_6 is not _UNSET:
        _kwargs['blocks.6.'] = blocks_6
    if blocks_7 is not _UNSET:
        _kwargs['blocks.7.'] = blocks_7
    if blocks_8 is not _UNSET:
        _kwargs['blocks.8.'] = blocks_8
    if blocks_9 is not _UNSET:
        _kwargs['blocks.9.'] = blocks_9
    if blocks_10 is not _UNSET:
        _kwargs['blocks.10.'] = blocks_10
    if blocks_11 is not _UNSET:
        _kwargs['blocks.11.'] = blocks_11
    if blocks_12 is not _UNSET:
        _kwargs['blocks.12.'] = blocks_12
    if blocks_13 is not _UNSET:
        _kwargs['blocks.13.'] = blocks_13
    if blocks_14 is not _UNSET:
        _kwargs['blocks.14.'] = blocks_14
    if blocks_15 is not _UNSET:
        _kwargs['blocks.15.'] = blocks_15
    if blocks_16 is not _UNSET:
        _kwargs['blocks.16.'] = blocks_16
    if blocks_17 is not _UNSET:
        _kwargs['blocks.17.'] = blocks_17
    if blocks_18 is not _UNSET:
        _kwargs['blocks.18.'] = blocks_18
    if blocks_19 is not _UNSET:
        _kwargs['blocks.19.'] = blocks_19
    if blocks_20 is not _UNSET:
        _kwargs['blocks.20.'] = blocks_20
    if blocks_21 is not _UNSET:
        _kwargs['blocks.21.'] = blocks_21
    if blocks_22 is not _UNSET:
        _kwargs['blocks.22.'] = blocks_22
    if blocks_23 is not _UNSET:
        _kwargs['blocks.23.'] = blocks_23
    if blocks_24 is not _UNSET:
        _kwargs['blocks.24.'] = blocks_24
    if blocks_25 is not _UNSET:
        _kwargs['blocks.25.'] = blocks_25
    if blocks_26 is not _UNSET:
        _kwargs['blocks.26.'] = blocks_26
    if blocks_27 is not _UNSET:
        _kwargs['blocks.27.'] = blocks_27
    if blocks_28 is not _UNSET:
        _kwargs['blocks.28.'] = blocks_28
    if blocks_29 is not _UNSET:
        _kwargs['blocks.29.'] = blocks_29
    if blocks_30 is not _UNSET:
        _kwargs['blocks.30.'] = blocks_30
    if blocks_31 is not _UNSET:
        _kwargs['blocks.31.'] = blocks_31
    if blocks_32 is not _UNSET:
        _kwargs['blocks.32.'] = blocks_32
    if blocks_33 is not _UNSET:
        _kwargs['blocks.33.'] = blocks_33
    if blocks_34 is not _UNSET:
        _kwargs['blocks.34.'] = blocks_34
    if blocks_35 is not _UNSET:
        _kwargs['blocks.35.'] = blocks_35
    if blocks_36 is not _UNSET:
        _kwargs['blocks.36.'] = blocks_36
    if blocks_37 is not _UNSET:
        _kwargs['blocks.37.'] = blocks_37
    if blocks_38 is not _UNSET:
        _kwargs['blocks.38.'] = blocks_38
    if blocks_39 is not _UNSET:
        _kwargs['blocks.39.'] = blocks_39
    _kwargs.update(_extras)
    return node(wf, 'Wan21BlockLoraSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanChunkFeedForward(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    chunks: int | _Omitted = _UNSET,
    dim_threshold: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EXPERIMENTAL AND MAY CHANGE THE MODEL OUTPUT!! Chunks feedforward activations to reduce peak VRAM usage.

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanChunkFeedForward() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if chunks is not _UNSET:
        _kwargs['chunks'] = chunks
    if dim_threshold is not _UNSET:
        _kwargs['dim_threshold'] = dim_threshold
    _kwargs.update(_extras)
    return node(wf, 'WanChunkFeedForward', _id, pass_raw=pass_raw, **_kwargs)

def WanImageToVideoSVIPro(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    length: int | _Omitted = _UNSET,
    anchor_samples: Any | _Omitted = _UNSET,
    motion_latent_count: int | _Omitted = _UNSET,
    prev_samples: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pack: ComfyUI-KJNodes
    Returns: positive, negative, latent

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanImageToVideoSVIPro() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    if length is not _UNSET:
        _kwargs['length'] = length
    if anchor_samples is not _UNSET:
        _kwargs['anchor_samples'] = anchor_samples
    if motion_latent_count is not _UNSET:
        _kwargs['motion_latent_count'] = motion_latent_count
    if prev_samples is not _UNSET:
        _kwargs['prev_samples'] = prev_samples
    _kwargs.update(_extras)
    return node(wf, 'WanImageToVideoSVIPro', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEnhanceAVideoKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    latent: Any | _Omitted = _UNSET,
    weight: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEnhanceAVideoKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if latent is not _UNSET:
        _kwargs['latent'] = latent
    if weight is not _UNSET:
        _kwargs['weight'] = weight
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEnhanceAVideoKJ', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoNAG(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    conditioning: Any | _Omitted = _UNSET,
    nag_scale: float | _Omitted = _UNSET,
    nag_alpha: float | _Omitted = _UNSET,
    nag_tau: float | _Omitted = _UNSET,
    input_type: Literal['default', 'batch'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/ChenDarYen/Normalized-Attention-Guidance

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoNAG() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if conditioning is not _UNSET:
        _kwargs['conditioning'] = conditioning
    if nag_scale is not _UNSET:
        _kwargs['nag_scale'] = nag_scale
    if nag_alpha is not _UNSET:
        _kwargs['nag_alpha'] = nag_alpha
    if nag_tau is not _UNSET:
        _kwargs['nag_tau'] = nag_tau
    if input_type is not _UNSET:
        _kwargs['input_type'] = input_type
    _kwargs.update(_extras)
    return node(wf, 'WanVideoNAG', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTeaCacheKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    rel_l1_thresh: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    coefficients: Literal['disabled', '1.3B', '14B', 'i2v_480', 'i2v_720'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Patch WanVideo model to use TeaCache. Speeds up inference by caching the output and
    applying it instead of doing the step.  Best results are achieved by choosing the
    appropriate coefficients for the model. Early steps should never be skipped, with too
    aggressive values this can happen and the motion suffers. Starting later can help with that too.
    When NOT using coefficients, the threshold value should be
    about 10 times smaller than the value used with coefficients.

    Official recommended values https://github.com/ali-vilab/TeaCache/tree/main/TeaCache4Wan2.1

    Pack: ComfyUI-KJNodes
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTeaCacheKJ() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if rel_l1_thresh is not _UNSET:
        _kwargs['rel_l1_thresh'] = rel_l1_thresh
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if cache_device is not _UNSET:
        _kwargs['cache_device'] = cache_device
    if coefficients is not _UNSET:
        _kwargs['coefficients'] = coefficients
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTeaCacheKJ', _id, pass_raw=pass_raw, **_kwargs)

def WebcamCaptureCV2(
    *args: VibeWorkflow,
    _id: str | None = None,
    x: int | _Omitted = _UNSET,
    y: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    cam_index: int | _Omitted = _UNSET,
    release: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Captures a frame from a webcam using CV2.
    Can be used for realtime diffusion with autoqueue.

    Pack: ComfyUI-KJNodes
    Returns: image

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WebcamCaptureCV2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if x is not _UNSET:
        _kwargs['x'] = x
    if y is not _UNSET:
        _kwargs['y'] = y
    if width is not _UNSET:
        _kwargs['width'] = width
    if height is not _UNSET:
        _kwargs['height'] = height
    if cam_index is not _UNSET:
        _kwargs['cam_index'] = cam_index
    if release is not _UNSET:
        _kwargs['release'] = release
    _kwargs.update(_extras)
    return node(wf, 'WebcamCaptureCV2', _id, pass_raw=pass_raw, **_kwargs)

def WeightScheduleConvert(
    *args: VibeWorkflow,
    _id: str | None = None,
    input_values: float | _Omitted = _UNSET,
    output_type: Literal['match_input', 'list', 'pandas series', 'tensor'] | _Omitted = _UNSET,
    invert: bool | _Omitted = _UNSET,
    repeat: int | _Omitted = _UNSET,
    remap_to_frames: int | _Omitted = _UNSET,
    interpolation_curve: float | _Omitted = _UNSET,
    remap_values: bool | _Omitted = _UNSET,
    remap_min: float | _Omitted = _UNSET,
    remap_max: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Converts different value lists/series to another type.

    Pack: ComfyUI-KJNodes
    Returns: FLOAT, STRING, INT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WeightScheduleConvert() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input_values is not _UNSET:
        _kwargs['input_values'] = input_values
    if output_type is not _UNSET:
        _kwargs['output_type'] = output_type
    if invert is not _UNSET:
        _kwargs['invert'] = invert
    if repeat is not _UNSET:
        _kwargs['repeat'] = repeat
    if remap_to_frames is not _UNSET:
        _kwargs['remap_to_frames'] = remap_to_frames
    if interpolation_curve is not _UNSET:
        _kwargs['interpolation_curve'] = interpolation_curve
    if remap_values is not _UNSET:
        _kwargs['remap_values'] = remap_values
    if remap_min is not _UNSET:
        _kwargs['remap_min'] = remap_min
    if remap_max is not _UNSET:
        _kwargs['remap_max'] = remap_max
    _kwargs.update(_extras)
    return node(wf, 'WeightScheduleConvert', _id, pass_raw=pass_raw, **_kwargs)

def WeightScheduleExtend(
    *args: VibeWorkflow,
    _id: str | None = None,
    input_values_1: float | _Omitted = _UNSET,
    input_values_2: float | _Omitted = _UNSET,
    output_type: Literal['match_input', 'list', 'pandas series', 'tensor'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Extends, and converts if needed, different value lists/series

    Pack: ComfyUI-KJNodes
    Returns: FLOAT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WeightScheduleExtend() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input_values_1 is not _UNSET:
        _kwargs['input_values_1'] = input_values_1
    if input_values_2 is not _UNSET:
        _kwargs['input_values_2'] = input_values_2
    if output_type is not _UNSET:
        _kwargs['output_type'] = output_type
    _kwargs.update(_extras)
    return node(wf, 'WeightScheduleExtend', _id, pass_raw=pass_raw, **_kwargs)

def WidgetToString(
    *args: VibeWorkflow,
    _id: str | None = None,
    id: int | _Omitted = _UNSET,
    widget_name: str | _Omitted = _UNSET,
    return_all: bool | _Omitted = _UNSET,
    any_input: Any | _Omitted = _UNSET,
    node_title: str | _Omitted = _UNSET,
    allowed_float_decimals: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Selects a node and it's specified widget and outputs the value as a string.
    If no node id or title is provided it will use the 'any_input' link and use that node.
    To see node id's, enable "Node ID Badge Mode" in main settings.
    Alternatively you can search with the node title. Node titles ONLY exist if they
    are manually edited!
    'widget_name' can be a comma separated list.
    The 'any_input' is required for making sure the node you want the value from exists in the workflow.

    Pack: ComfyUI-KJNodes
    Returns: STRING

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"WidgetToString() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if id is not _UNSET:
        _kwargs['id'] = id
    if widget_name is not _UNSET:
        _kwargs['widget_name'] = widget_name
    if return_all is not _UNSET:
        _kwargs['return_all'] = return_all
    if any_input is not _UNSET:
        _kwargs['any_input'] = any_input
    if node_title is not _UNSET:
        _kwargs['node_title'] = node_title
    if allowed_float_decimals is not _UNSET:
        _kwargs['allowed_float_decimals'] = allowed_float_decimals
    _kwargs.update(_extras)
    return node(wf, 'WidgetToString', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['AddLabel', 'AddNoiseToTrackPath', 'AppendInstanceDiffusionTracking', 'AppendStringsToList', 'ApplyRifleXRoPE_HunuyanVideo', 'ApplyRifleXRoPE_WanVideo', 'AudioConcatenate', 'BOOLConstant', 'BatchCLIPSeg', 'BatchCropFromMask', 'BatchCropFromMaskAdvanced', 'BatchUncrop', 'BatchUncropAdvanced', 'BboxToInt', 'BboxVisualize', 'BlockifyMask', 'CFGZeroStarAndInit', 'CameraPoseVisualizer', 'CheckpointLoaderKJ', 'CheckpointPerturbWeights', 'ColorMatch', 'ColorMatchV2', 'ColorToMask', 'CondPassThrough', 'ConditioningMultiCombine', 'ConditioningSetMaskAndCombine', 'ConditioningSetMaskAndCombine3', 'ConditioningSetMaskAndCombine4', 'ConditioningSetMaskAndCombine5', 'ConsolidateMasksKJ', 'CreateAudioMask', 'CreateFadeMask', 'CreateFadeMaskAdvanced', 'CreateFluidMask', 'CreateGradientFromCoords', 'CreateGradientMask', 'CreateInstanceDiffusionTracking', 'CreateMagicMask', 'CreateShapeImageOnPath', 'CreateShapeMask', 'CreateShapeMaskOnPath', 'CreateTextMask', 'CreateTextOnPath', 'CreateVoronoiMask', 'CrossFadeImages', 'CrossFadeImagesMulti', 'CustomControlNetWeightsFluxFromList', 'CustomSigmas', 'CutAndDragOnPath', 'DecodeAndSaveVideo', 'DiTBlockLoraLoader', 'DifferentialDiffusionAdvanced', 'DiffusionModelLoaderKJ', 'DiffusionModelSelector', 'DownloadAndLoadCLIPSeg', 'DrawInstanceDiffusionTracking', 'DrawMaskOnImage', 'DummyOut', 'EmptyLatentImageCustomPresets', 'EmptyLatentImagePresets', 'EncodeVideoComponents', 'EndRecordCUDAMemoryHistory', 'FastPreview', 'FilterZeroMasksAndCorrespondingImages', 'FlipSigmasAdjusted', 'FloatConstant', 'FloatToMask', 'FloatToSigmas', 'FluxBlockLoraSelect', 'GGUFLoaderKJ', 'GLIGENTextBoxApplyBatchCoords', 'GenerateNoise', 'GetImageSizeAndCount', 'GetImagesFromBatchIndexed', 'GetLatentRangeFromBatch', 'GetLatentSizeAndCount', 'GetLatentsFromBatchIndexed', 'GetMaskSizeAndCount', 'GetTrackRange', 'GradientToFloat', 'GrowMaskWithBlur', 'HDRPreviewKJ', 'HunyuanVideoBlockLoraSelect', 'HunyuanVideoEncodeKeyframesToCond', 'INTConstant', 'ImageAddMulti', 'ImageAndMaskPreview', 'ImageBatchExtendWithOverlap', 'ImageBatchFilter', 'ImageBatchJoinWithTransition', 'ImageBatchMulti', 'ImageBatchRepeatInterleaving', 'ImageBatchTestPattern', 'ImageConcanate', 'ImageConcatFromBatch', 'ImageConcatMulti', 'ImageCropByMask', 'ImageCropByMaskAndResize', 'ImageCropByMaskBatch', 'ImageGrabPIL', 'ImageGridComposite2x2', 'ImageGridComposite3x3', 'ImageGridtoBatch', 'ImageNoiseAugmentation', 'ImageNormalize_Neg1_To_1', 'ImagePadForOutpaintMasked', 'ImagePadForOutpaintTargetSize', 'ImagePadKJ', 'ImagePass', 'ImagePrepForICLora', 'ImageResizeKJ', 'ImageResizeKJv2', 'ImageSharpenKJ', 'ImageTensorList', 'ImageTransformByNormalizedAmplitude', 'ImageTransformKJ', 'ImageUncropByMask', 'ImageUpscaleWithModelBatched', 'InjectNoiseToLatent', 'InsertImageBatchByIndexes', 'InsertImagesToBatchIndexed', 'InsertLatentToIndexed', 'InterpolateCoords', 'Intrinsic_lora_sampling', 'JoinStringMulti', 'JoinStrings', 'LTX2AttentionTunerPatch', 'LTX2AudioLatentNormalizingSampling', 'LTX2BlockLoraSelect', 'LTX2LoraLoaderAdvanced', 'LTX2MemoryEfficientSageAttentionPatch', 'LTX2SamplingPreviewOverride', 'LTX2_NAG', 'LTXVAudioVideoMask', 'LTXVChunkFeedForward', 'LTXVEnhanceAVideoKJ', 'LTXVImgToVideoInplaceKJ', 'LatentInpaintTTM', 'LazySwitchKJ', 'LeapfusionHunyuanI2VPatcher', 'LoadAndResizeImage', 'LoadImagesFromFolderKJ', 'LoadResAdapterNormalization', 'LoadVideosFromFolder', 'LoraExtractKJ', 'LoraReduceRankKJ', 'MaskBatchMulti', 'MaskOrImageToWeight', 'MergeImageChannels', 'ModelMemoryUsageFactorOverride', 'ModelMemoryUseReportPatch', 'ModelPassThrough', 'ModelPatchTorchSettings', 'ModelSaveKJ', 'NABLA_AttentionKJ', 'NormalizedAmplitudeToFloatList', 'NormalizedAmplitudeToMask', 'OffsetMask', 'OffsetMaskByNormalizedAmplitude', 'PadImageBatchInterleaved', 'PatchModelPatcherOrder', 'PathchSageAttentionKJ', 'PlaySoundKJ', 'PlotCoordinates', 'PointsEditor', 'PreviewAnimation', 'PreviewImageOrMask', 'PreviewLatentNoiseMask', 'RemapImageRange', 'RemapMaskRange', 'ReplaceImagesInBatch', 'ResizeMask', 'ReverseImageBatch', 'RoundMask', 'SV3D_BatchSchedule', 'SamplerSelfRefineVideo', 'SaveImageKJ', 'SaveImageWithAlpha', 'SaveStringKJ', 'ScaleBatchPromptSchedule', 'ScheduledCFGGuidance', 'ScreencapStream', 'Screencap_mss', 'SeparateMasks', 'SetShakkerLabsUnionControlNetType', 'ShuffleImageBatch', 'SigmasToFloat', 'SimpleCalculatorKJ', 'SkipLayerGuidanceWanVideo', 'Sleep', 'SoundReactive', 'SplineEditor', 'SplitBboxes', 'SplitImageChannels', 'StableZero123_BatchSchedule', 'StartRecordCUDAMemoryHistory', 'StringConstant', 'StringConstantMultiline', 'StringToFloatList', 'StyleModelApplyAdvanced', 'Superprompt', 'TimerNodeKJ', 'TorchCompileControlNet', 'TorchCompileCosmosModel', 'TorchCompileLTXModel', 'TorchCompileModelAdvanced', 'TorchCompileModelFluxAdvanced', 'TorchCompileModelFluxAdvancedV2', 'TorchCompileModelHyVideo', 'TorchCompileModelQwenImage', 'TorchCompileModelWanVideo', 'TorchCompileModelWanVideoV2', 'TorchCompileVAE', 'TransitionImagesInBatch', 'TransitionImagesMulti', 'VAEDecodeLoopKJ', 'VAELoaderKJ', 'VRAM_Debug', 'VisualizeCUDAMemoryHistory', 'VisualizeSigmasKJ', 'Wan21BlockLoraSelect', 'WanChunkFeedForward', 'WanImageToVideoSVIPro', 'WanVideoEnhanceAVideoKJ', 'WanVideoNAG', 'WanVideoTeaCacheKJ', 'WebcamCaptureCV2', 'WeightScheduleConvert', 'WeightScheduleExtend', 'WidgetToString']
__vibecomfy_class_types__ = {'AddLabel': 'AddLabel', 'AddNoiseToTrackPath': 'AddNoiseToTrackPath', 'AppendInstanceDiffusionTracking': 'AppendInstanceDiffusionTracking', 'AppendStringsToList': 'AppendStringsToList', 'ApplyRifleXRoPE_HunuyanVideo': 'ApplyRifleXRoPE_HunuyanVideo', 'ApplyRifleXRoPE_WanVideo': 'ApplyRifleXRoPE_WanVideo', 'AudioConcatenate': 'AudioConcatenate', 'BOOLConstant': 'BOOLConstant', 'BatchCLIPSeg': 'BatchCLIPSeg', 'BatchCropFromMask': 'BatchCropFromMask', 'BatchCropFromMaskAdvanced': 'BatchCropFromMaskAdvanced', 'BatchUncrop': 'BatchUncrop', 'BatchUncropAdvanced': 'BatchUncropAdvanced', 'BboxToInt': 'BboxToInt', 'BboxVisualize': 'BboxVisualize', 'BlockifyMask': 'BlockifyMask', 'CFGZeroStarAndInit': 'CFGZeroStarAndInit', 'CameraPoseVisualizer': 'CameraPoseVisualizer', 'CheckpointLoaderKJ': 'CheckpointLoaderKJ', 'CheckpointPerturbWeights': 'CheckpointPerturbWeights', 'ColorMatch': 'ColorMatch', 'ColorMatchV2': 'ColorMatchV2', 'ColorToMask': 'ColorToMask', 'CondPassThrough': 'CondPassThrough', 'ConditioningMultiCombine': 'ConditioningMultiCombine', 'ConditioningSetMaskAndCombine': 'ConditioningSetMaskAndCombine', 'ConditioningSetMaskAndCombine3': 'ConditioningSetMaskAndCombine3', 'ConditioningSetMaskAndCombine4': 'ConditioningSetMaskAndCombine4', 'ConditioningSetMaskAndCombine5': 'ConditioningSetMaskAndCombine5', 'ConsolidateMasksKJ': 'ConsolidateMasksKJ', 'CreateAudioMask': 'CreateAudioMask', 'CreateFadeMask': 'CreateFadeMask', 'CreateFadeMaskAdvanced': 'CreateFadeMaskAdvanced', 'CreateFluidMask': 'CreateFluidMask', 'CreateGradientFromCoords': 'CreateGradientFromCoords', 'CreateGradientMask': 'CreateGradientMask', 'CreateInstanceDiffusionTracking': 'CreateInstanceDiffusionTracking', 'CreateMagicMask': 'CreateMagicMask', 'CreateShapeImageOnPath': 'CreateShapeImageOnPath', 'CreateShapeMask': 'CreateShapeMask', 'CreateShapeMaskOnPath': 'CreateShapeMaskOnPath', 'CreateTextMask': 'CreateTextMask', 'CreateTextOnPath': 'CreateTextOnPath', 'CreateVoronoiMask': 'CreateVoronoiMask', 'CrossFadeImages': 'CrossFadeImages', 'CrossFadeImagesMulti': 'CrossFadeImagesMulti', 'CustomControlNetWeightsFluxFromList': 'CustomControlNetWeightsFluxFromList', 'CustomSigmas': 'CustomSigmas', 'CutAndDragOnPath': 'CutAndDragOnPath', 'DecodeAndSaveVideo': 'DecodeAndSaveVideo', 'DiTBlockLoraLoader': 'DiTBlockLoraLoader', 'DifferentialDiffusionAdvanced': 'DifferentialDiffusionAdvanced', 'DiffusionModelLoaderKJ': 'DiffusionModelLoaderKJ', 'DiffusionModelSelector': 'DiffusionModelSelector', 'DownloadAndLoadCLIPSeg': 'DownloadAndLoadCLIPSeg', 'DrawInstanceDiffusionTracking': 'DrawInstanceDiffusionTracking', 'DrawMaskOnImage': 'DrawMaskOnImage', 'DummyOut': 'DummyOut', 'EmptyLatentImageCustomPresets': 'EmptyLatentImageCustomPresets', 'EmptyLatentImagePresets': 'EmptyLatentImagePresets', 'EncodeVideoComponents': 'EncodeVideoComponents', 'EndRecordCUDAMemoryHistory': 'EndRecordCUDAMemoryHistory', 'FastPreview': 'FastPreview', 'FilterZeroMasksAndCorrespondingImages': 'FilterZeroMasksAndCorrespondingImages', 'FlipSigmasAdjusted': 'FlipSigmasAdjusted', 'FloatConstant': 'FloatConstant', 'FloatToMask': 'FloatToMask', 'FloatToSigmas': 'FloatToSigmas', 'FluxBlockLoraSelect': 'FluxBlockLoraSelect', 'GGUFLoaderKJ': 'GGUFLoaderKJ', 'GLIGENTextBoxApplyBatchCoords': 'GLIGENTextBoxApplyBatchCoords', 'GenerateNoise': 'GenerateNoise', 'GetImageSizeAndCount': 'GetImageSizeAndCount', 'GetImagesFromBatchIndexed': 'GetImagesFromBatchIndexed', 'GetLatentRangeFromBatch': 'GetLatentRangeFromBatch', 'GetLatentSizeAndCount': 'GetLatentSizeAndCount', 'GetLatentsFromBatchIndexed': 'GetLatentsFromBatchIndexed', 'GetMaskSizeAndCount': 'GetMaskSizeAndCount', 'GetTrackRange': 'GetTrackRange', 'GradientToFloat': 'GradientToFloat', 'GrowMaskWithBlur': 'GrowMaskWithBlur', 'HDRPreviewKJ': 'HDRPreviewKJ', 'HunyuanVideoBlockLoraSelect': 'HunyuanVideoBlockLoraSelect', 'HunyuanVideoEncodeKeyframesToCond': 'HunyuanVideoEncodeKeyframesToCond', 'INTConstant': 'INTConstant', 'ImageAddMulti': 'ImageAddMulti', 'ImageAndMaskPreview': 'ImageAndMaskPreview', 'ImageBatchExtendWithOverlap': 'ImageBatchExtendWithOverlap', 'ImageBatchFilter': 'ImageBatchFilter', 'ImageBatchJoinWithTransition': 'ImageBatchJoinWithTransition', 'ImageBatchMulti': 'ImageBatchMulti', 'ImageBatchRepeatInterleaving': 'ImageBatchRepeatInterleaving', 'ImageBatchTestPattern': 'ImageBatchTestPattern', 'ImageConcanate': 'ImageConcanate', 'ImageConcatFromBatch': 'ImageConcatFromBatch', 'ImageConcatMulti': 'ImageConcatMulti', 'ImageCropByMask': 'ImageCropByMask', 'ImageCropByMaskAndResize': 'ImageCropByMaskAndResize', 'ImageCropByMaskBatch': 'ImageCropByMaskBatch', 'ImageGrabPIL': 'ImageGrabPIL', 'ImageGridComposite2x2': 'ImageGridComposite2x2', 'ImageGridComposite3x3': 'ImageGridComposite3x3', 'ImageGridtoBatch': 'ImageGridtoBatch', 'ImageNoiseAugmentation': 'ImageNoiseAugmentation', 'ImageNormalize_Neg1_To_1': 'ImageNormalize_Neg1_To_1', 'ImagePadForOutpaintMasked': 'ImagePadForOutpaintMasked', 'ImagePadForOutpaintTargetSize': 'ImagePadForOutpaintTargetSize', 'ImagePadKJ': 'ImagePadKJ', 'ImagePass': 'ImagePass', 'ImagePrepForICLora': 'ImagePrepForICLora', 'ImageResizeKJ': 'ImageResizeKJ', 'ImageResizeKJv2': 'ImageResizeKJv2', 'ImageSharpenKJ': 'ImageSharpenKJ', 'ImageTensorList': 'ImageTensorList', 'ImageTransformByNormalizedAmplitude': 'ImageTransformByNormalizedAmplitude', 'ImageTransformKJ': 'ImageTransformKJ', 'ImageUncropByMask': 'ImageUncropByMask', 'ImageUpscaleWithModelBatched': 'ImageUpscaleWithModelBatched', 'InjectNoiseToLatent': 'InjectNoiseToLatent', 'InsertImageBatchByIndexes': 'InsertImageBatchByIndexes', 'InsertImagesToBatchIndexed': 'InsertImagesToBatchIndexed', 'InsertLatentToIndexed': 'InsertLatentToIndexed', 'InterpolateCoords': 'InterpolateCoords', 'Intrinsic_lora_sampling': 'Intrinsic_lora_sampling', 'JoinStringMulti': 'JoinStringMulti', 'JoinStrings': 'JoinStrings', 'LTX2AttentionTunerPatch': 'LTX2AttentionTunerPatch', 'LTX2AudioLatentNormalizingSampling': 'LTX2AudioLatentNormalizingSampling', 'LTX2BlockLoraSelect': 'LTX2BlockLoraSelect', 'LTX2LoraLoaderAdvanced': 'LTX2LoraLoaderAdvanced', 'LTX2MemoryEfficientSageAttentionPatch': 'LTX2MemoryEfficientSageAttentionPatch', 'LTX2SamplingPreviewOverride': 'LTX2SamplingPreviewOverride', 'LTX2_NAG': 'LTX2_NAG', 'LTXVAudioVideoMask': 'LTXVAudioVideoMask', 'LTXVChunkFeedForward': 'LTXVChunkFeedForward', 'LTXVEnhanceAVideoKJ': 'LTXVEnhanceAVideoKJ', 'LTXVImgToVideoInplaceKJ': 'LTXVImgToVideoInplaceKJ', 'LatentInpaintTTM': 'LatentInpaintTTM', 'LazySwitchKJ': 'LazySwitchKJ', 'LeapfusionHunyuanI2VPatcher': 'LeapfusionHunyuanI2VPatcher', 'LoadAndResizeImage': 'LoadAndResizeImage', 'LoadImagesFromFolderKJ': 'LoadImagesFromFolderKJ', 'LoadResAdapterNormalization': 'LoadResAdapterNormalization', 'LoadVideosFromFolder': 'LoadVideosFromFolder', 'LoraExtractKJ': 'LoraExtractKJ', 'LoraReduceRankKJ': 'LoraReduceRankKJ', 'MaskBatchMulti': 'MaskBatchMulti', 'MaskOrImageToWeight': 'MaskOrImageToWeight', 'MergeImageChannels': 'MergeImageChannels', 'ModelMemoryUsageFactorOverride': 'ModelMemoryUsageFactorOverride', 'ModelMemoryUseReportPatch': 'ModelMemoryUseReportPatch', 'ModelPassThrough': 'ModelPassThrough', 'ModelPatchTorchSettings': 'ModelPatchTorchSettings', 'ModelSaveKJ': 'ModelSaveKJ', 'NABLA_AttentionKJ': 'NABLA_AttentionKJ', 'NormalizedAmplitudeToFloatList': 'NormalizedAmplitudeToFloatList', 'NormalizedAmplitudeToMask': 'NormalizedAmplitudeToMask', 'OffsetMask': 'OffsetMask', 'OffsetMaskByNormalizedAmplitude': 'OffsetMaskByNormalizedAmplitude', 'PadImageBatchInterleaved': 'PadImageBatchInterleaved', 'PatchModelPatcherOrder': 'PatchModelPatcherOrder', 'PathchSageAttentionKJ': 'PathchSageAttentionKJ', 'PlaySoundKJ': 'PlaySoundKJ', 'PlotCoordinates': 'PlotCoordinates', 'PointsEditor': 'PointsEditor', 'PreviewAnimation': 'PreviewAnimation', 'PreviewImageOrMask': 'PreviewImageOrMask', 'PreviewLatentNoiseMask': 'PreviewLatentNoiseMask', 'RemapImageRange': 'RemapImageRange', 'RemapMaskRange': 'RemapMaskRange', 'ReplaceImagesInBatch': 'ReplaceImagesInBatch', 'ResizeMask': 'ResizeMask', 'ReverseImageBatch': 'ReverseImageBatch', 'RoundMask': 'RoundMask', 'SV3D_BatchSchedule': 'SV3D_BatchSchedule', 'SamplerSelfRefineVideo': 'SamplerSelfRefineVideo', 'SaveImageKJ': 'SaveImageKJ', 'SaveImageWithAlpha': 'SaveImageWithAlpha', 'SaveStringKJ': 'SaveStringKJ', 'ScaleBatchPromptSchedule': 'ScaleBatchPromptSchedule', 'ScheduledCFGGuidance': 'ScheduledCFGGuidance', 'ScreencapStream': 'ScreencapStream', 'Screencap_mss': 'Screencap_mss', 'SeparateMasks': 'SeparateMasks', 'SetShakkerLabsUnionControlNetType': 'SetShakkerLabsUnionControlNetType', 'ShuffleImageBatch': 'ShuffleImageBatch', 'SigmasToFloat': 'SigmasToFloat', 'SimpleCalculatorKJ': 'SimpleCalculatorKJ', 'SkipLayerGuidanceWanVideo': 'SkipLayerGuidanceWanVideo', 'Sleep': 'Sleep', 'SoundReactive': 'SoundReactive', 'SplineEditor': 'SplineEditor', 'SplitBboxes': 'SplitBboxes', 'SplitImageChannels': 'SplitImageChannels', 'StableZero123_BatchSchedule': 'StableZero123_BatchSchedule', 'StartRecordCUDAMemoryHistory': 'StartRecordCUDAMemoryHistory', 'StringConstant': 'StringConstant', 'StringConstantMultiline': 'StringConstantMultiline', 'StringToFloatList': 'StringToFloatList', 'StyleModelApplyAdvanced': 'StyleModelApplyAdvanced', 'Superprompt': 'Superprompt', 'TimerNodeKJ': 'TimerNodeKJ', 'TorchCompileControlNet': 'TorchCompileControlNet', 'TorchCompileCosmosModel': 'TorchCompileCosmosModel', 'TorchCompileLTXModel': 'TorchCompileLTXModel', 'TorchCompileModelAdvanced': 'TorchCompileModelAdvanced', 'TorchCompileModelFluxAdvanced': 'TorchCompileModelFluxAdvanced', 'TorchCompileModelFluxAdvancedV2': 'TorchCompileModelFluxAdvancedV2', 'TorchCompileModelHyVideo': 'TorchCompileModelHyVideo', 'TorchCompileModelQwenImage': 'TorchCompileModelQwenImage', 'TorchCompileModelWanVideo': 'TorchCompileModelWanVideo', 'TorchCompileModelWanVideoV2': 'TorchCompileModelWanVideoV2', 'TorchCompileVAE': 'TorchCompileVAE', 'TransitionImagesInBatch': 'TransitionImagesInBatch', 'TransitionImagesMulti': 'TransitionImagesMulti', 'VAEDecodeLoopKJ': 'VAEDecodeLoopKJ', 'VAELoaderKJ': 'VAELoaderKJ', 'VRAM_Debug': 'VRAM_Debug', 'VisualizeCUDAMemoryHistory': 'VisualizeCUDAMemoryHistory', 'VisualizeSigmasKJ': 'VisualizeSigmasKJ', 'Wan21BlockLoraSelect': 'Wan21BlockLoraSelect', 'WanChunkFeedForward': 'WanChunkFeedForward', 'WanImageToVideoSVIPro': 'WanImageToVideoSVIPro', 'WanVideoEnhanceAVideoKJ': 'WanVideoEnhanceAVideoKJ', 'WanVideoNAG': 'WanVideoNAG', 'WanVideoTeaCacheKJ': 'WanVideoTeaCacheKJ', 'WebcamCaptureCV2': 'WebcamCaptureCV2', 'WeightScheduleConvert': 'WeightScheduleConvert', 'WeightScheduleExtend': 'WeightScheduleExtend', 'WidgetToString': 'WidgetToString'}
