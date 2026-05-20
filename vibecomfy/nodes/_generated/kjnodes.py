"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import _current_workflow_or_raise, node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def AddLabel(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any = _UNSET,
    text_x: Any = _UNSET,
    text_y: Any = _UNSET,
    height: Any = _UNSET,
    font_size: Any = _UNSET,
    font_color: Any = _UNSET,
    label_color: Any = _UNSET,
    font: Any = _UNSET,
    text: Any = _UNSET,
    direction: Any = _UNSET,
    caption: Any = _UNSET,
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

def BlockifyMask(
    *args: VibeWorkflow,
    _id: str | None = None,
    masks: Any = _UNSET,
    block_size: Any = _UNSET,
    device: Any = _UNSET,
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

def CameraPoseVisualizer(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_file_path: Any = _UNSET,
    base_xval: Any = _UNSET,
    zval: Any = _UNSET,
    scale: Any = _UNSET,
    use_exact_fx: Any = _UNSET,
    relative_c2w: Any = _UNSET,
    use_viewer: Any = _UNSET,
    cameractrl_poses: Any = _UNSET,
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

def ColorMatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    image_ref: Any = _UNSET,
    image_target: Any = _UNSET,
    method: Any = _UNSET,
    strength: Any = _UNSET,
    multithread: Any = _UNSET,
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

def DrawMaskOnImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any = _UNSET,
    mask: Any = _UNSET,
    color: Any = _UNSET,
    device: Any = _UNSET,
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

def GetImageSizeAndCount(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any = _UNSET,
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
    images: Any = _UNSET,
    indexes: Any = _UNSET,
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

def INTConstant(
    *args: VibeWorkflow,
    _id: str | None = None,
    value: Any = _UNSET,
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

def ImageBatchExtendWithOverlap(
    *args: VibeWorkflow,
    _id: str | None = None,
    source_images: Any = _UNSET,
    overlap: Any = _UNSET,
    overlap_side: Any = _UNSET,
    overlap_mode: Any = _UNSET,
    new_images: Any = _UNSET,
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

def ImageBatchMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: Any = _UNSET,
    image_1: Any = _UNSET,
    image_2: Any = _UNSET,
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

def ImageConcatMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    inputcount: Any = _UNSET,
    image_1: Any = _UNSET,
    direction: Any = _UNSET,
    match_image_size: Any = _UNSET,
    image_2: Any = _UNSET,
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

def ImagePadKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any = _UNSET,
    left: Any = _UNSET,
    right: Any = _UNSET,
    top: Any = _UNSET,
    bottom: Any = _UNSET,
    extra_padding: Any = _UNSET,
    pad_mode: Any = _UNSET,
    color: Any = _UNSET,
    mask: Any = _UNSET,
    target_width: Any = _UNSET,
    target_height: Any = _UNSET,
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

def ImageResizeKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any = _UNSET,
    width: Any = _UNSET,
    height: Any = _UNSET,
    upscale_method: Any = _UNSET,
    keep_proportion: Any = _UNSET,
    divisible_by: Any = _UNSET,
    get_image_size: Any = _UNSET,
    crop: Any = _UNSET,
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
    image: Any = _UNSET,
    width: Any = _UNSET,
    height: Any = _UNSET,
    upscale_method: Any = _UNSET,
    keep_proportion: Any = _UNSET,
    pad_color: Any = _UNSET,
    crop_position: Any = _UNSET,
    divisible_by: Any = _UNSET,
    mask: Any = _UNSET,
    device: Any = _UNSET,
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

def InsertLatentToIndexed(
    *args: VibeWorkflow,
    _id: str | None = None,
    source: Any = _UNSET,
    destination: Any = _UNSET,
    index: Any = _UNSET,
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

def LTX2AttentionTunerPatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any = _UNSET,
    blocks: Any = _UNSET,
    video_scale: Any = _UNSET,
    audio_scale: Any = _UNSET,
    audio_to_video_scale: Any = _UNSET,
    video_to_audio_scale: Any = _UNSET,
    triton_kernels: Any = _UNSET,
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

def LTX2MemoryEfficientSageAttentionPatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any = _UNSET,
    triton_kernels: Any = _UNSET,
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

def LTX2_NAG(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any = _UNSET,
    nag_scale: Any = _UNSET,
    nag_alpha: Any = _UNSET,
    nag_tau: Any = _UNSET,
    nag_cond_video: Any = _UNSET,
    nag_cond_audio: Any = _UNSET,
    inplace: Any = _UNSET,
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
    video_fps: Any = _UNSET,
    video_start_time: Any = _UNSET,
    video_end_time: Any = _UNSET,
    audio_start_time: Any = _UNSET,
    audio_end_time: Any = _UNSET,
    max_length: Any = _UNSET,
    video_latent: Any = _UNSET,
    audio_latent: Any = _UNSET,
    existing_mask_mode: Any = _UNSET,
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
    model: Any = _UNSET,
    chunks: Any = _UNSET,
    dim_threshold: Any = _UNSET,
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

def LTXVImgToVideoInplaceKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae: Any = _UNSET,
    latent: Any = _UNSET,
    num_images: Any = _UNSET,
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

def LazySwitchKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    switch: Any = _UNSET,
    on_false: Any = _UNSET,
    on_true: Any = _UNSET,
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

def LoadVideosFromFolder(
    *args: VibeWorkflow,
    _id: str | None = None,
    video: Any = _UNSET,
    force_rate: Any = _UNSET,
    custom_width: Any = _UNSET,
    custom_height: Any = _UNSET,
    frame_load_cap: Any = _UNSET,
    skip_first_frames: Any = _UNSET,
    select_every_nth: Any = _UNSET,
    output_type: Any = _UNSET,
    grid_max_columns: Any = _UNSET,
    add_label: Any = _UNSET,
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

def PathchSageAttentionKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any = _UNSET,
    sage_attention: Any = _UNSET,
    allow_compile: Any = _UNSET,
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

def PointsEditor(
    *args: VibeWorkflow,
    _id: str | None = None,
    points_store: Any = _UNSET,
    coordinates: Any = _UNSET,
    neg_coordinates: Any = _UNSET,
    bbox_store: Any = _UNSET,
    bboxes: Any = _UNSET,
    bbox_format: Any = _UNSET,
    width: Any = _UNSET,
    height: Any = _UNSET,
    normalize: Any = _UNSET,
    bg_image: Any = _UNSET,
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
    fps: Any = _UNSET,
    images: Any = _UNSET,
    masks: Any = _UNSET,
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

def SimpleCalculatorKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    expression: Any = _UNSET,
    variables: Any = _UNSET,
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

def SplineEditor(
    *args: VibeWorkflow,
    _id: str | None = None,
    points_store: Any = _UNSET,
    coordinates: Any = _UNSET,
    mask_width: Any = _UNSET,
    mask_height: Any = _UNSET,
    points_to_sample: Any = _UNSET,
    sampling_method: Any = _UNSET,
    interpolation: Any = _UNSET,
    tension: Any = _UNSET,
    repeat_output: Any = _UNSET,
    float_output_type: Any = _UNSET,
    min_value: Any = _UNSET,
    max_value: Any = _UNSET,
    bg_image: Any = _UNSET,
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

def VAELoaderKJ(
    *args: VibeWorkflow,
    _id: str | None = None,
    vae_name: Any = _UNSET,
    device: Any = _UNSET,
    weight_dtype: Any = _UNSET,
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
    empty_cache: Any = _UNSET,
    gc_collect: Any = _UNSET,
    unload_all_models: Any = _UNSET,
    any_input: Any = _UNSET,
    image_pass: Any = _UNSET,
    model_pass: Any = _UNSET,
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

def WidgetToString(
    *args: VibeWorkflow,
    _id: str | None = None,
    id: Any = _UNSET,
    widget_name: Any = _UNSET,
    return_all: Any = _UNSET,
    any_input: Any = _UNSET,
    node_title: Any = _UNSET,
    allowed_float_decimals: Any = _UNSET,
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

__all__ = ['AddLabel', 'BlockifyMask', 'CameraPoseVisualizer', 'ColorMatch', 'DrawMaskOnImage', 'GetImageSizeAndCount', 'GetImagesFromBatchIndexed', 'INTConstant', 'ImageBatchExtendWithOverlap', 'ImageBatchMulti', 'ImageConcatMulti', 'ImagePadKJ', 'ImageResizeKJ', 'ImageResizeKJv2', 'InsertLatentToIndexed', 'LTX2AttentionTunerPatch', 'LTX2MemoryEfficientSageAttentionPatch', 'LTX2_NAG', 'LTXVAudioVideoMask', 'LTXVChunkFeedForward', 'LTXVImgToVideoInplaceKJ', 'LazySwitchKJ', 'LoadVideosFromFolder', 'PathchSageAttentionKJ', 'PointsEditor', 'PreviewAnimation', 'SimpleCalculatorKJ', 'SplineEditor', 'VAELoaderKJ', 'VRAM_Debug', 'WidgetToString']
