"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def AddLabel(
    wf: VibeWorkflow,
    *,
    image: Any,
    font: Any,
    text_x: Any = 10,
    text_y: Any = 2,
    height: Any = 48,
    font_size: Any = 32,
    font_color: Any = 'white',
    label_color: Any = 'black',
    text: Any = 'Text',
    direction: Any = 'up',
    caption: Any = '',
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['font'] = font
    _kwargs['text_x'] = text_x
    _kwargs['text_y'] = text_y
    _kwargs['height'] = height
    _kwargs['font_size'] = font_size
    _kwargs['font_color'] = font_color
    _kwargs['label_color'] = label_color
    _kwargs['text'] = text
    _kwargs['direction'] = direction
    _kwargs['caption'] = caption
    _kwargs.update(_extras)
    return node(wf, 'AddLabel', pass_raw=pass_raw, **_kwargs)

def BlockifyMask(
    wf: VibeWorkflow,
    *,
    masks: Any,
    block_size: Any = 32,
    device: Any = 'cpu',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates a block mask by dividing the bounding box of each mask into blocks of the specified size and filling in blocks that contain any part of the original mask.
    
    Pack: ComfyUI-KJNodes
    Returns: mask
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['masks'] = masks
    _kwargs['block_size'] = block_size
    _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'BlockifyMask', pass_raw=pass_raw, **_kwargs)

def CameraPoseVisualizer(
    wf: VibeWorkflow,
    *,
    pose_file_path: Any = '',
    base_xval: Any = 0.2,
    zval: Any = 0.3,
    scale: Any = 1.0,
    use_exact_fx: Any = False,
    relative_c2w: Any = True,
    use_viewer: Any = False,
    cameractrl_poses: Any = None,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Visualizes the camera poses, from Animatediff-Evolved CameraCtrl Pose  
    or a .txt file with RealEstate camera intrinsics and coordinates, in a 3D plot.
    
    Pack: ComfyUI-KJNodes
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['pose_file_path'] = pose_file_path
    _kwargs['base_xval'] = base_xval
    _kwargs['zval'] = zval
    _kwargs['scale'] = scale
    _kwargs['use_exact_fx'] = use_exact_fx
    _kwargs['relative_c2w'] = relative_c2w
    _kwargs['use_viewer'] = use_viewer
    _kwargs['cameractrl_poses'] = cameractrl_poses
    _kwargs.update(_extras)
    return node(wf, 'CameraPoseVisualizer', pass_raw=pass_raw, **_kwargs)

def ColorMatch(
    wf: VibeWorkflow,
    *,
    image_ref: Any,
    image_target: Any,
    method: Any = 'mkl',
    strength: Any = 1.0,
    multithread: Any = True,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image_ref'] = image_ref
    _kwargs['image_target'] = image_target
    _kwargs['method'] = method
    _kwargs['strength'] = strength
    _kwargs['multithread'] = multithread
    _kwargs.update(_extras)
    return node(wf, 'ColorMatch', pass_raw=pass_raw, **_kwargs)

def DrawMaskOnImage(
    wf: VibeWorkflow,
    *,
    image: Any,
    mask: Any,
    color: Any = '0, 0, 0',
    device: Any = 'cpu',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Applies the provided masks to the input images with Alpha Blending support.
    
    Pack: ComfyUI-KJNodes
    Returns: images
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['mask'] = mask
    _kwargs['color'] = color
    _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'DrawMaskOnImage', pass_raw=pass_raw, **_kwargs)

def GetImageSizeAndCount(
    wf: VibeWorkflow,
    *,
    image: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Returns width, height and batch size of the image,  
    and passes it through unchanged.
    
    Pack: ComfyUI-KJNodes
    Returns: image, width, height, count
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'GetImageSizeAndCount', pass_raw=pass_raw, **_kwargs)

def GetImagesFromBatchIndexed(
    wf: VibeWorkflow,
    *,
    images: Any,
    indexes: Any = '0, 1, 2',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Selects and returns the images at the specified indices as an image batch.
    
    Pack: ComfyUI-KJNodes
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['images'] = images
    _kwargs['indexes'] = indexes
    _kwargs.update(_extras)
    return node(wf, 'GetImagesFromBatchIndexed', pass_raw=pass_raw, **_kwargs)

def INTConstant(
    wf: VibeWorkflow,
    *,
    value: Any = 0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    INT Constant
    
    Pack: ComfyUI-KJNodes
    Returns: value
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['value'] = value
    _kwargs.update(_extras)
    return node(wf, 'INTConstant', pass_raw=pass_raw, **_kwargs)

def ImageBatchExtendWithOverlap(
    wf: VibeWorkflow,
    *,
    source_images: Any,
    overlap: Any = 13,
    overlap_side: Any = 'source',
    overlap_mode: Any = 'linear_blend',
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['source_images'] = source_images
    _kwargs['overlap'] = overlap
    _kwargs['overlap_side'] = overlap_side
    _kwargs['overlap_mode'] = overlap_mode
    if new_images is not _UNSET:
        _kwargs['new_images'] = new_images
    _kwargs.update(_extras)
    return node(wf, 'ImageBatchExtendWithOverlap', pass_raw=pass_raw, **_kwargs)

def ImageBatchMulti(
    wf: VibeWorkflow,
    *,
    image_1: Any,
    inputcount: Any = 2,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image_1'] = image_1
    _kwargs['inputcount'] = inputcount
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    _kwargs.update(_extras)
    return node(wf, 'ImageBatchMulti', pass_raw=pass_raw, **_kwargs)

def ImageConcatMulti(
    wf: VibeWorkflow,
    *,
    image_1: Any,
    inputcount: Any = 2,
    direction: Any = 'right',
    match_image_size: Any = False,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image_1'] = image_1
    _kwargs['inputcount'] = inputcount
    _kwargs['direction'] = direction
    _kwargs['match_image_size'] = match_image_size
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    _kwargs.update(_extras)
    return node(wf, 'ImageConcatMulti', pass_raw=pass_raw, **_kwargs)

def ImagePadKJ(
    wf: VibeWorkflow,
    *,
    image: Any,
    pad_mode: Any,
    left: Any = 0,
    right: Any = 0,
    top: Any = 0,
    bottom: Any = 0,
    extra_padding: Any = 0,
    color: Any = '0, 0, 0',
    mask: Any = _UNSET,
    target_width: Any = 512,
    target_height: Any = 512,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Pad the input image and optionally mask with the specified padding.
    
    Pack: ComfyUI-KJNodes
    Returns: images, masks
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['pad_mode'] = pad_mode
    _kwargs['left'] = left
    _kwargs['right'] = right
    _kwargs['top'] = top
    _kwargs['bottom'] = bottom
    _kwargs['extra_padding'] = extra_padding
    _kwargs['color'] = color
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    _kwargs['target_width'] = target_width
    _kwargs['target_height'] = target_height
    _kwargs.update(_extras)
    return node(wf, 'ImagePadKJ', pass_raw=pass_raw, **_kwargs)

def ImageResizeKJ(
    wf: VibeWorkflow,
    *,
    image: Any,
    upscale_method: Any,
    width: Any = 512,
    height: Any = 512,
    keep_proportion: Any = False,
    divisible_by: Any = 2,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['upscale_method'] = upscale_method
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['keep_proportion'] = keep_proportion
    _kwargs['divisible_by'] = divisible_by
    if get_image_size is not _UNSET:
        _kwargs['get_image_size'] = get_image_size
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    _kwargs.update(_extras)
    return node(wf, 'ImageResizeKJ', pass_raw=pass_raw, **_kwargs)

def ImageResizeKJv2(
    wf: VibeWorkflow,
    *,
    image: Any,
    upscale_method: Any,
    width: Any = 512,
    height: Any = 512,
    keep_proportion: Any = False,
    pad_color: Any = '0, 0, 0',
    crop_position: Any = 'center',
    divisible_by: Any = 2,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['image'] = image
    _kwargs['upscale_method'] = upscale_method
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['keep_proportion'] = keep_proportion
    _kwargs['pad_color'] = pad_color
    _kwargs['crop_position'] = crop_position
    _kwargs['divisible_by'] = divisible_by
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if device is not _UNSET:
        _kwargs['device'] = device
    _kwargs.update(_extras)
    return node(wf, 'ImageResizeKJv2', pass_raw=pass_raw, **_kwargs)

def InsertLatentToIndexed(
    wf: VibeWorkflow,
    *,
    source: Any,
    destination: Any,
    index: Any = 0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Inserts a latent at the specified index into the original latent batch.
    
    Pack: ComfyUI-KJNodes
    Returns: LATENT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['source'] = source
    _kwargs['destination'] = destination
    _kwargs['index'] = index
    _kwargs.update(_extras)
    return node(wf, 'InsertLatentToIndexed', pass_raw=pass_raw, **_kwargs)

def LTX2AttentionTunerPatch(
    wf: VibeWorkflow,
    *,
    model: Any,
    blocks: Any = '',
    video_scale: Any = 1.0,
    audio_scale: Any = 1.0,
    audio_to_video_scale: Any = 1.0,
    video_to_audio_scale: Any = 1.0,
    triton_kernels: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EXPERIMENTAL! Custom LTX2 forward pass with attention scaling factors per modality, also reduces peak VRAM usage.
    
    Pack: ComfyUI-KJNodes
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['blocks'] = blocks
    _kwargs['video_scale'] = video_scale
    _kwargs['audio_scale'] = audio_scale
    _kwargs['audio_to_video_scale'] = audio_to_video_scale
    _kwargs['video_to_audio_scale'] = video_to_audio_scale
    _kwargs['triton_kernels'] = triton_kernels
    _kwargs.update(_extras)
    return node(wf, 'LTX2AttentionTunerPatch', pass_raw=pass_raw, **_kwargs)

def LTX2MemoryEfficientSageAttentionPatch(
    wf: VibeWorkflow,
    *,
    model: Any,
    triton_kernels: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EXPERIMENTAL! Activates custom sageattention to reduce peak VRAM usage, overrides the attention mode. Requires latest sageattention version.
    
    Pack: ComfyUI-KJNodes
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['triton_kernels'] = triton_kernels
    _kwargs.update(_extras)
    return node(wf, 'LTX2MemoryEfficientSageAttentionPatch', pass_raw=pass_raw, **_kwargs)

def LTX2_NAG(
    wf: VibeWorkflow,
    *,
    model: Any,
    nag_scale: Any = 11.0,
    nag_alpha: Any = 0.25,
    nag_tau: Any = 2.5,
    nag_cond_video: Any = _UNSET,
    nag_cond_audio: Any = _UNSET,
    inplace: Any = True,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    https://github.com/ChenDarYen/Normalized-Attention-Guidance
    
    Pack: ComfyUI-KJNodes
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['nag_scale'] = nag_scale
    _kwargs['nag_alpha'] = nag_alpha
    _kwargs['nag_tau'] = nag_tau
    if nag_cond_video is not _UNSET:
        _kwargs['nag_cond_video'] = nag_cond_video
    if nag_cond_audio is not _UNSET:
        _kwargs['nag_cond_audio'] = nag_cond_audio
    _kwargs['inplace'] = inplace
    _kwargs.update(_extras)
    return node(wf, 'LTX2_NAG', pass_raw=pass_raw, **_kwargs)

def LTXVAudioVideoMask(
    wf: VibeWorkflow,
    *,
    video_fps: Any = 25,
    video_start_time: Any = 0.0,
    video_end_time: Any = 5.0,
    audio_start_time: Any = 0.0,
    audio_end_time: Any = 5.0,
    max_length: Any = 'truncate',
    video_latent: Any = _UNSET,
    audio_latent: Any = _UNSET,
    existing_mask_mode: Any = 'add',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Creates noise masks for video and audio latents based on specified time ranges. New content is generated within these masked regions
    
    Pack: ComfyUI-KJNodes
    Returns: video_latent, audio_latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['video_fps'] = video_fps
    _kwargs['video_start_time'] = video_start_time
    _kwargs['video_end_time'] = video_end_time
    _kwargs['audio_start_time'] = audio_start_time
    _kwargs['audio_end_time'] = audio_end_time
    _kwargs['max_length'] = max_length
    if video_latent is not _UNSET:
        _kwargs['video_latent'] = video_latent
    if audio_latent is not _UNSET:
        _kwargs['audio_latent'] = audio_latent
    _kwargs['existing_mask_mode'] = existing_mask_mode
    _kwargs.update(_extras)
    return node(wf, 'LTXVAudioVideoMask', pass_raw=pass_raw, **_kwargs)

def LTXVChunkFeedForward(
    wf: VibeWorkflow,
    *,
    model: Any,
    chunks: Any = 2,
    dim_threshold: Any = 4096,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    EXPERIMENTAL AND MAY CHANGE THE MODEL OUTPUT!! Chunks feedforward activations to reduce peak VRAM usage.
    
    Pack: ComfyUI-KJNodes
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['chunks'] = chunks
    _kwargs['dim_threshold'] = dim_threshold
    _kwargs.update(_extras)
    return node(wf, 'LTXVChunkFeedForward', pass_raw=pass_raw, **_kwargs)

def LTXVImgToVideoInplaceKJ(
    wf: VibeWorkflow,
    *,
    vae: Any,
    latent: Any,
    num_images: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Replaces video latent frames with the encoded input images, uses DynamicCombo which requires ComfyUI 0.8.1 and frontend 1.33.4 or later.
    
    Pack: ComfyUI-KJNodes
    Returns: latent
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae'] = vae
    _kwargs['latent'] = latent
    _kwargs['num_images'] = num_images
    _kwargs.update(_extras)
    return node(wf, 'LTXVImgToVideoInplaceKJ', pass_raw=pass_raw, **_kwargs)

def LazySwitchKJ(
    wf: VibeWorkflow,
    *,
    switch: Any,
    on_false: Any,
    on_true: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Controls flow of execution based on a boolean switch.
    
    Pack: ComfyUI-KJNodes
    Returns: *
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['switch'] = switch
    _kwargs['on_false'] = on_false
    _kwargs['on_true'] = on_true
    _kwargs.update(_extras)
    return node(wf, 'LazySwitchKJ', pass_raw=pass_raw, **_kwargs)

def LoadVideosFromFolder(
    wf: VibeWorkflow,
    *,
    video: Any = 'X://insert/path/',
    force_rate: Any = 0,
    custom_width: Any = 0,
    custom_height: Any = 0,
    frame_load_cap: Any = 0,
    skip_first_frames: Any = 0,
    select_every_nth: Any = 1,
    output_type: Any = 'batch',
    grid_max_columns: Any = 4,
    add_label: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Load Videos From Folder
    
    Pack: ComfyUI-KJNodes
    Returns: IMAGE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['video'] = video
    _kwargs['force_rate'] = force_rate
    _kwargs['custom_width'] = custom_width
    _kwargs['custom_height'] = custom_height
    _kwargs['frame_load_cap'] = frame_load_cap
    _kwargs['skip_first_frames'] = skip_first_frames
    _kwargs['select_every_nth'] = select_every_nth
    _kwargs['output_type'] = output_type
    _kwargs['grid_max_columns'] = grid_max_columns
    _kwargs['add_label'] = add_label
    _kwargs.update(_extras)
    return node(wf, 'LoadVideosFromFolder', pass_raw=pass_raw, **_kwargs)

def PathchSageAttentionKJ(
    wf: VibeWorkflow,
    *,
    model: Any,
    sage_attention: Any = False,
    allow_compile: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Experimental node for patching attention mode. This doesn't use the model patching system and thus can't be disabled without running the node again with 'disabled' option.
    
    Pack: ComfyUI-KJNodes
    Returns: MODEL
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['sage_attention'] = sage_attention
    _kwargs['allow_compile'] = allow_compile
    _kwargs.update(_extras)
    return node(wf, 'PathchSageAttentionKJ', pass_raw=pass_raw, **_kwargs)

def PointsEditor(
    wf: VibeWorkflow,
    *,
    points_store: Any,
    coordinates: Any,
    neg_coordinates: Any,
    bbox_store: Any,
    bboxes: Any,
    bbox_format: Any,
    width: Any = 512,
    height: Any = 512,
    normalize: Any = False,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['points_store'] = points_store
    _kwargs['coordinates'] = coordinates
    _kwargs['neg_coordinates'] = neg_coordinates
    _kwargs['bbox_store'] = bbox_store
    _kwargs['bboxes'] = bboxes
    _kwargs['bbox_format'] = bbox_format
    _kwargs['width'] = width
    _kwargs['height'] = height
    _kwargs['normalize'] = normalize
    if bg_image is not _UNSET:
        _kwargs['bg_image'] = bg_image
    _kwargs.update(_extras)
    return node(wf, 'PointsEditor', pass_raw=pass_raw, **_kwargs)

def PreviewAnimation(
    wf: VibeWorkflow,
    *,
    fps: Any = 8.0,
    images: Any = _UNSET,
    masks: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Preview Animation
    
    Pack: ComfyUI-KJNodes
    Returns: None
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['fps'] = fps
    if images is not _UNSET:
        _kwargs['images'] = images
    if masks is not _UNSET:
        _kwargs['masks'] = masks
    _kwargs.update(_extras)
    return node(wf, 'PreviewAnimation', pass_raw=pass_raw, **_kwargs)

def SimpleCalculatorKJ(
    wf: VibeWorkflow,
    *,
    variables: Any,
    expression: Any = 'a + b',
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['variables'] = variables
    _kwargs['expression'] = expression
    _kwargs.update(_extras)
    return node(wf, 'SimpleCalculatorKJ', pass_raw=pass_raw, **_kwargs)

def SplineEditor(
    wf: VibeWorkflow,
    *,
    points_store: Any,
    coordinates: Any,
    mask_width: Any = 512,
    mask_height: Any = 512,
    points_to_sample: Any = 16,
    sampling_method: Any = 'time',
    interpolation: Any = 'cardinal',
    tension: Any = 0.5,
    repeat_output: Any = 1,
    float_output_type: Any = 'list',
    min_value: Any = 0.0,
    max_value: Any = 1.0,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['points_store'] = points_store
    _kwargs['coordinates'] = coordinates
    _kwargs['mask_width'] = mask_width
    _kwargs['mask_height'] = mask_height
    _kwargs['points_to_sample'] = points_to_sample
    _kwargs['sampling_method'] = sampling_method
    _kwargs['interpolation'] = interpolation
    _kwargs['tension'] = tension
    _kwargs['repeat_output'] = repeat_output
    _kwargs['float_output_type'] = float_output_type
    _kwargs['min_value'] = min_value
    _kwargs['max_value'] = max_value
    if bg_image is not _UNSET:
        _kwargs['bg_image'] = bg_image
    _kwargs.update(_extras)
    return node(wf, 'SplineEditor', pass_raw=pass_raw, **_kwargs)

def VAELoaderKJ(
    wf: VibeWorkflow,
    *,
    vae_name: Any,
    device: Any,
    weight_dtype: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    VAELoader KJ
    
    Pack: ComfyUI-KJNodes
    Returns: VAE
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['vae_name'] = vae_name
    _kwargs['device'] = device
    _kwargs['weight_dtype'] = weight_dtype
    _kwargs.update(_extras)
    return node(wf, 'VAELoaderKJ', pass_raw=pass_raw, **_kwargs)

def VRAM_Debug(
    wf: VibeWorkflow,
    *,
    empty_cache: Any = True,
    gc_collect: Any = True,
    unload_all_models: Any = False,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['empty_cache'] = empty_cache
    _kwargs['gc_collect'] = gc_collect
    _kwargs['unload_all_models'] = unload_all_models
    if any_input is not _UNSET:
        _kwargs['any_input'] = any_input
    if image_pass is not _UNSET:
        _kwargs['image_pass'] = image_pass
    if model_pass is not _UNSET:
        _kwargs['model_pass'] = model_pass
    _kwargs.update(_extras)
    return node(wf, 'VRAM_Debug', pass_raw=pass_raw, **_kwargs)

def WidgetToString(
    wf: VibeWorkflow,
    *,
    widget_name: Any,
    id: Any = 0,
    return_all: Any = False,
    any_input: Any = _UNSET,
    node_title: Any = _UNSET,
    allowed_float_decimals: Any = 2,
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
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['widget_name'] = widget_name
    _kwargs['id'] = id
    _kwargs['return_all'] = return_all
    if any_input is not _UNSET:
        _kwargs['any_input'] = any_input
    if node_title is not _UNSET:
        _kwargs['node_title'] = node_title
    _kwargs['allowed_float_decimals'] = allowed_float_decimals
    _kwargs.update(_extras)
    return node(wf, 'WidgetToString', pass_raw=pass_raw, **_kwargs)

__all__ = ['AddLabel', 'BlockifyMask', 'CameraPoseVisualizer', 'ColorMatch', 'DrawMaskOnImage', 'GetImageSizeAndCount', 'GetImagesFromBatchIndexed', 'INTConstant', 'ImageBatchExtendWithOverlap', 'ImageBatchMulti', 'ImageConcatMulti', 'ImagePadKJ', 'ImageResizeKJ', 'ImageResizeKJv2', 'InsertLatentToIndexed', 'LTX2AttentionTunerPatch', 'LTX2MemoryEfficientSageAttentionPatch', 'LTX2_NAG', 'LTXVAudioVideoMask', 'LTXVChunkFeedForward', 'LTXVImgToVideoInplaceKJ', 'LazySwitchKJ', 'LoadVideosFromFolder', 'PathchSageAttentionKJ', 'PointsEditor', 'PreviewAnimation', 'SimpleCalculatorKJ', 'SplineEditor', 'VAELoaderKJ', 'VRAM_Debug', 'WidgetToString']
