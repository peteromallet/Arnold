# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Vace Video Control.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json

Packs:   ComfyUI-DepthAnythingV2, ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _wan_video_tea_cache(wf, _id, widget_2, **overrides):
    kwargs = dict(widget_0=0.1,
                  widget_1=0,
                  widget_3='offload_device',
                  widget_4='true',
                  widget_5='e',
                  widget_2=widget_2)
    kwargs.update(overrides)
    return node(wf, 'WanVideoTeaCache', _id, **kwargs)
def _wan_video_experimental_args(wf, _id, **overrides):
    kwargs = dict(widget_0='',
                  widget_1=True,
                  widget_2=False,
                  widget_3=0,
                  widget_4=False,
                  widget_5=1,
                  widget_6=1.25,
                  widget_7=20)
    kwargs.update(overrides)
    return node(wf, 'WanVideoExperimentalArgs', _id, **kwargs)
def _get_node_WanVAE(wf, _id, **overrides):
    kwargs = dict(widget_0='WanVAE')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_WanTextEncoder(wf, _id, **overrides):
    kwargs = dict(widget_0='WanTextEncoder')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_WanModel(wf, _id, **overrides):
    kwargs = dict(widget_0='WanModel')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _image_concat_multi_down(wf, _id, image_1, image_2, **overrides):
    kwargs = dict(inputcount=2,
                  direction='down',
                  match_image_size=True,
                  unused_3=None,
                  image_1=image_1,
                  image_2=image_2)
    kwargs.update(overrides)
    return node(wf, 'ImageConcatMulti', _id, **kwargs)
def _image_concat_multi(wf, _id, image_1, image_2, image_3, **overrides):
    kwargs = dict(inputcount=3,
                  direction='left',
                  match_image_size=True,
                  unused_3=None,
                  image_1=image_1,
                  image_2=image_2,
                  image_3=image_3)
    kwargs.update(overrides)
    return node(wf, 'ImageConcatMulti', _id, **kwargs)
def _v_h_s__video_combine(wf, _id, images, **overrides):
    kwargs = dict(save_output=True,
                  images=images)
    kwargs.update(overrides)
    return node(wf, 'VHS_VideoCombine', _id, **kwargs)
def _wan_video_v_a_c_e_encode(wf, _id, height, input_frames, input_masks, num_frames, vae, width, **overrides):
    kwargs = dict(widget_0=480,
                  widget_1=832,
                  widget_2=29,
                  widget_3=1.0000000000000002,
                  widget_4=0,
                  widget_5=1,
                  widget_6=False,
                  height=height,
                  input_frames=input_frames,
                  input_masks=input_masks,
                  num_frames=num_frames,
                  vae=vae,
                  width=width)
    kwargs.update(overrides)
    return node(wf, 'WanVideoVACEEncode', _id, **kwargs)
def _wan_video_decode(wf, _id, samples, vae, **overrides):
    kwargs = dict(enable_vae_tiling=False,
                  tile_x=272,
                  tile_y=272,
                  tile_stride_x=144,
                  tile_stride_y=128,
                  samples=samples,
                  vae=vae)
    kwargs.update(overrides)
    return node(wf, 'WanVideoDecode', _id, **kwargs)
def _empty_image(wf, _id, height, **overrides):
    kwargs = dict(widget_0=8,
                  widget_1=512,
                  widget_2=1,
                  widget_3=0,
                  height=height)
    kwargs.update(overrides)
    return node(wf, 'EmptyImage', _id, **kwargs)
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_13b_vace',
    capability='vace_video_control',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-DepthAnythingV2', 'source': 'git',
                       'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json', 'source_role': 'materialized_ready_python_template', 'smoke_resolution': '256x256x5_frames', 'approach': 'VACE control/edit workflow'},
    coverage_tier='supplemental',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ TEXT CONDITIONING ════
    load_wan_video_t5_text_encoder_11 = node(wf, 'LoadWanVideoT5TextEncoder', '11',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        load_device='offload_device',
        quantization='disabled',
    )
    # ════ SAMPLING ════
    wan_video_torch_compile_settings_35 = node(wf, 'WanVideoTorchCompileSettings', '35',
        backend='inductor',
        fullgraph=False,
        mode='default',
        dynamic=False,
        dynamo_cache_size_limit=64,
        compile_transformer_blocks_only=True,
        dynamo_recompile_limit=128,
    )
    # ════ LOADERS ════
    wan_video_vaeloader = node(wf, 'WanVideoVAELoader', '38',
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
    )
    wan_video_block_swap_39 = node(wf, 'WanVideoBlockSwap', '39',
        blocks_to_swap=0,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=15,
    )
    wan_video_tea_cache_52 = _wan_video_tea_cache(wf, '52', -1)
    input_image_64 = node(wf, 'LoadImage', '64',
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp',
)
    wan_video_experimental_args_71 = _wan_video_experimental_args(wf, '71', )
    wan_video_slg_1 = node(wf, 'WanVideoSLG', '72',
        widget_0='8',
        widget_1=0.3,
        widget_2=0.7,
    )
    input_image_2 = node(wf, 'LoadImage', '112',
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-3.webp',
)
    get_node_123 = _get_node_WanVAE(wf, '123', )
    getnode_2 = _get_node_WanVAE(wf, '124', )
    getnode_3 = _get_node_WanTextEncoder(wf, '126', )
    getnode_4 = _get_node_WanModel(wf, '127', )
    getnode_5 = _get_node_WanModel(wf, '128', )
    getnode_6 = node(wf, 'GetNode', '130',
        widget_0='start_image',
    )
    getnode_7 = node(wf, 'GetNode', '131',
        widget_0='end_image',
    )
    getnode_8 = _get_node_WanVAE(wf, '142', )
    getnode_9 = _get_node_WanTextEncoder(wf, '143', )
    wanvideoteacache_2 = _wan_video_tea_cache(wf, '147', -1)
    wan_video_slg_2 = node(wf, 'WanVideoSLG', '149',
        widget_0='8',
        widget_1=0.3,
        widget_2=0.71,
    )
    wanvideoexperimentalargs_2 = _wan_video_experimental_args(wf, '150', )
    getnode_10 = _get_node_WanModel(wf, '151', )
    getnode_11 = _get_node_WanModel(wf, '152', )
    getnode_12 = node(wf, 'GetNode', '153',
        widget_0='reference_image',
    )
    getnode_13 = node(wf, 'GetNode', '154',
        widget_0='control_video',
    )
    getnode_14 = _get_node_WanVAE(wf, '166', )
    input_image_3 = node(wf, 'LoadImage', '169',
        image='hunhyuanwolf.png',
)
    vhs__load_video_1 = node(wf, 'VHS_LoadVideo', '173',
        video='wolf_interpolated.mp4',
    )
    # ════ CONTROL ════
    depth_model = node(wf, 'DownloadAndLoadDepthAnythingV2Model', '175',
        widget_0='depth_anything_v2_vitl_fp16.safetensors',
    )
    getnode_15 = _get_node_WanVAE(wf, '185', )
    getnode_16 = _get_node_WanTextEncoder(wf, '186', )
    wan_video_slg_3 = node(wf, 'WanVideoSLG', '187',
        widget_0='8',
        widget_1=0.3,
        widget_2=0.7,
    )
    wanvideoexperimentalargs_3 = _wan_video_experimental_args(wf, '188', )
    getnode_17 = _get_node_WanModel(wf, '189', )
    getnode_18 = _get_node_WanModel(wf, '190', )
    getnode_19 = _get_node_WanVAE(wf, '195', )
    vhs_loadvideo_2 = node(wf, 'VHS_LoadVideo', '199',
        video='wolf_interpolated.mp4',
    )
    getnode_20 = node(wf, 'GetNode', '201',
        widget_0='InputVideo',
    )
    wanvideoteacache_3 = _wan_video_tea_cache(wf, '214', -1)
    wan_video_vacemodel_select = node(wf, 'WanVideoVACEModelSelect', '224',
        widget_0='WanVideo\\Wan2_1-VACE_module_1_3B_bf16.safetensors',
    )
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt='black and white cartoon character',
        negative_prompt='colorful, bad quality, blurry, messy, chaotic',
        force_offload=True,
        model_to_offload=getnode_4.out(0),
        t5=getnode_3.out(0),
    )
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors',
        base_precision='fp16',
        quantization='disabled',
        load_device='offload_device',
        attention_mode='sdpa',
        vace_model=wan_video_vacemodel_select.out(0),
    )
    setnode_2 = node(wf, 'SetNode', '122',
        widget_0='WanVAE',
        WANVAE=wan_video_vaeloader.out(0),
    )
    setnode_3 = node(wf, 'SetNode', '125',
        widget_0='WanTextEncoder',
        WANTEXTENCODER=load_wan_video_t5_text_encoder_11.out(0),
    )
    add_label_133 = node(wf, 'AddLabel', '133',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='start_frame',
        widget_8='up',
        image=getnode_6.out(0),
    )
    add_label_2 = node(wf, 'AddLabel', '134',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='end_frame',
        widget_8='up',
        image=getnode_7.out(0),
    )
    add_label_3 = node(wf, 'AddLabel', '156',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='reference image',
        widget_8='up',
        image=getnode_12.out(0),
    )
    add_label_4 = node(wf, 'AddLabel', '157',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='control_video',
        widget_8='up',
        image=getnode_13.out(0),
    )
    wan_video_text_encode_2 = node(wf, 'WanVideoTextEncode', '168',
        positive_prompt='robotic cybernetic wolf turning his head',
        negative_prompt='bad quality, blurry, messy, chaotic',
        force_offload=True,
        model_to_offload=getnode_10.out(0),
        t5=getnode_9.out(0),
    )
    image_pad_k_j_184 = node(wf, 'ImagePadKJ', '184',
        widget_0=0,
        widget_1=0,
        widget_2=0,
        widget_3=0,
        widget_4=128,
        widget_5='color',
        widget_6='255,255,255',
        image=input_image_3.out('IMAGE'),
    )
    add_label_5 = node(wf, 'AddLabel', '202',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='input',
        widget_8='up',
        image=getnode_20.out(0),
    )
    wan_video_text_encode_3 = node(wf, 'WanVideoTextEncode', '211',
        positive_prompt='robotic cybernetic wolf turning his head',
        negative_prompt='bad quality, blurry, messy, chaotic',
        force_offload=True,
        model_to_offload=getnode_17.out(0),
        t5=getnode_16.out(0),
    )
    # ════ IMAGE PREP ════
    resized_image_226 = node(wf, 'ImageResizeKJv2', '226',
        height=256,
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='172,172,172',
        crop_position='center',
        divisible_by=2,
        width=256,
        image=vhs_loadvideo_2.out(0),
    )
    imageresizekjv2_2 = node(wf, 'ImageResizeKJv2', '227',
        height=256,
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='172,172,172',
        crop_position='center',
        divisible_by=16,
        width=256,
        image=input_image_64.out('IMAGE'),
    )
    imageresizekjv2_4 = node(wf, 'ImageResizeKJv2', '229',
        height=256,
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='172,172,172',
        crop_position='center',
        divisible_by=16,
        width=256,
        image=vhs__load_video_1.out(0),
    )
    set_node_121 = node(wf, 'SetNode', '121',
        widget_0='WanModel',
        WANVIDEOMODEL=wan_video_model_loader_22.out(0),
    )
    imageconcatmulti_2 = _image_concat_multi_down(wf, '136', add_label_133.out(0), add_label_2.out(0))
    setnode_4 = node(wf, 'SetNode', '140',
        widget_0='start_image',
        IMAGE=imageresizekjv2_2.out('IMAGE'),
    )
    imageconcatmulti_4 = _image_concat_multi_down(wf, '160', add_label_3.out(0), add_label_4.out(0))
    depth_map = node(wf, 'DepthAnything_V2', '174',
        da_model=depth_model.out('DA_V2_MODEL'),
        images=imageresizekjv2_4.out('IMAGE'),
    )
    image_pad_k_j_2 = node(wf, 'ImagePadKJ', '216',
        widget_0=0,
        widget_1=0,
        widget_2=0,
        widget_3=0,
        widget_4=128,
        widget_5='color',
        widget_6='127,127,127',
        image=resized_image_226.out('IMAGE'),
    )
    imageresizekjv2_3 = node(wf, 'ImageResizeKJv2', '228',
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='172,172,172',
        crop_position='center',
        divisible_by=16,
        height=imageresizekjv2_2.out(2),
        image=input_image_2.out('IMAGE'),
        width=imageresizekjv2_2.out(1),
    )
    imageresizekjv2_5 = node(wf, 'ImageResizeKJv2', '230',
        
        upscale_method='lanczos',
        keep_proportion='pad',
        pad_color='255,255,255',
        crop_position='center',
        divisible_by=16,
        height=imageresizekjv2_4.out(2),
        image=image_pad_k_j_184.out(0),
        width=imageresizekjv2_4.out(1),
    )
    imageresizekjv2_6 = node(wf, 'ImageResizeKJv2', '238',
        
        upscale_method='lanczos',
        keep_proportion='pad',
        pad_color='255,255,255',
        crop_position='center',
        divisible_by=16,
        height=imageresizekjv2_4.out(2),
        image=input_image_3.out('IMAGE'),
        width=imageresizekjv2_4.out(1),
    )
    setnode_5 = node(wf, 'SetNode', '141',
        widget_0='end_image',
        IMAGE=imageresizekjv2_3.out('IMAGE'),
    )
    setnode_6 = node(wf, 'SetNode', '179',
        widget_0='reference_image',
        IMAGE=imageresizekjv2_5.out('IMAGE'),
    )
    setnode_7 = node(wf, 'SetNode', '180',
        widget_0='control_video',
        IMAGE=depth_map.out('IMAGE'),
    )
    get_image_size_and_count_1 = node(wf, 'GetImageSizeAndCount', '205',
        image=image_pad_k_j_2.out(0),
    )
    get_image_range_from_batch_219 = node(wf, 'GetImageRangeFromBatch', '219',
        widget_0=0,
        widget_1=1,
        images=image_pad_k_j_2.out(0),
    )
    setnode_8 = node(wf, 'SetNode', '221',
        widget_0='InputVideo',
        IMAGE=image_pad_k_j_2.out(0),
    )
    get_image_range_from_batch_2 = node(wf, 'GetImageRangeFromBatch', '222',
        widget_0=0,
        widget_1=1,
        masks=image_pad_k_j_2.out(1),
    )
    # ════ OUTPUT ════
    preview_image_1 = node(wf, 'PreviewImage', '237',
        images=imageresizekjv2_5.out('IMAGE'),
    )
    wan_video_vacestart_to_end_frame_1 = node(wf, 'WanVideoVACEStartToEndFrame', '111',
        widget_0=33,
        widget_1=0.5,
        end_image=setnode_5.out(0),
        start_image=setnode_4.out(0),
    )
    vhs_videocombine_3 = _v_h_s__video_combine(wf, '177', setnode_7.out(0))
    wanvideovaceencode_3 = _wan_video_v_a_c_e_encode(wf, '209', get_image_size_and_count_1.out(2), get_image_size_and_count_1.out(0), image_pad_k_j_2.out(1), get_image_size_and_count_1.out(3), getnode_15.out(0), get_image_size_and_count_1.out(1))
    preview_image_2 = node(wf, 'PreviewImage', '220',
        images=get_image_range_from_batch_219.out(0),
    )
    wan_video_vacestart_to_end_frame_2 = node(wf, 'WanVideoVACEStartToEndFrame', '231',
        widget_0=33,
        widget_1=0.5,
        control_images=setnode_7.out(0),
        num_frames=vhs__load_video_1.out(1),
        start_image=imageresizekjv2_6.out('IMAGE'),
    )
    mask_preview_1 = node(wf, 'MaskPreview', '235',
        mask=get_image_range_from_batch_2.out(1),
    )
    get_image_size_and_count_104 = node(wf, 'GetImageSizeAndCount', '104',
        image=wan_video_vacestart_to_end_frame_1.out(0),
    )
    get_image_size_and_count_3 = node(wf, 'GetImageSizeAndCount', '145',
        image=wan_video_vacestart_to_end_frame_2.out(0),
    )
    wan_video_sampler_1 = node(wf, 'WanVideoSampler', '197',
        steps=1,
        cfg=4.000000000000001,
        rope_function='comfy',
        start_step='',
        shift=8.000000000000002,
        seed=18,
force_offload=True,
        scheduler='unipc',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        cache_args=wanvideoteacache_3.out(0),
        experimental_args=wanvideoexperimentalargs_3.out(0),
        image_embeds=wanvideovaceencode_3.out(0),
        model=getnode_18.out(0),
        slg_args=wan_video_slg_3.out(0),
        text_embeds=wan_video_text_encode_3.out(0),
    )
    preview_image_3 = node(wf, 'PreviewImage', '232',
        images=wan_video_vacestart_to_end_frame_2.out(0),
    )
    mask_preview_233 = node(wf, 'MaskPreview', '233',
        mask=wan_video_vacestart_to_end_frame_2.out(1),
    )
    mask_preview_3 = node(wf, 'MaskPreview', '234',
        mask=wan_video_vacestart_to_end_frame_1.out(1),
    )
    wan_video_v_a_c_e_encode_56 = _wan_video_v_a_c_e_encode(wf, '56', get_image_size_and_count_104.out(2), get_image_size_and_count_104.out(0), wan_video_vacestart_to_end_frame_1.out(1), get_image_size_and_count_104.out(3), getnode_2.out(0), get_image_size_and_count_104.out(1))
    preview_image_113 = node(wf, 'PreviewImage', '113',
        images=get_image_size_and_count_104.out(0),
    )
    wanvideovaceencode_2 = _wan_video_v_a_c_e_encode(wf, '148', get_image_size_and_count_3.out(2), get_image_size_and_count_3.out(0), wan_video_vacestart_to_end_frame_2.out(1), get_image_size_and_count_3.out(3), getnode_8.out(0), get_image_size_and_count_3.out(1))
    wanvideodecode_3 = _wan_video_decode(wf, '196', wan_video_sampler_1.out(0), getnode_19.out(0))
    wan_video_sampler_70 = node(wf, 'WanVideoSampler', '70',
        steps=1,
        cfg=4.000000000000001,
        rope_function='comfy',
        start_step='',
        shift=8.000000000000002,
        seed=18,
force_offload=True,
        scheduler='unipc',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        cache_args=wan_video_tea_cache_52.out(0),
        experimental_args=wan_video_experimental_args_71.out(0),
        image_embeds=wan_video_v_a_c_e_encode_56.out(0),
        model=getnode_5.out(0),
        slg_args=wan_video_slg_1.out(0),
        text_embeds=wan_video_text_encode_16.out(0),
    )
    wan_video_sampler_3 = node(wf, 'WanVideoSampler', '172',
        steps=1,
        cfg=4.000000000000001,
        rope_function='comfy',
        start_step='',
        shift=8.000000000000002,
        seed=0,
force_offload=True,
        scheduler='unipc',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        cache_args=wanvideoteacache_2.out(0),
        experimental_args=wanvideoexperimentalargs_2.out(0),
        image_embeds=wanvideovaceencode_2.out(0),
        model=getnode_11.out(0),
        slg_args=wan_video_slg_2.out(0),
        text_embeds=wan_video_text_encode_2.out(0),
    )
    get_image_size_and_count_4 = node(wf, 'GetImageSizeAndCount', '193',
        image=wanvideodecode_3.out(0),
    )
    wan_video_decode_138 = _wan_video_decode(wf, '138', wan_video_sampler_70.out(0), get_node_123.out(0))
    wanvideodecode_2 = _wan_video_decode(wf, '167', wan_video_sampler_3.out(0), getnode_14.out(0))
    emptyimage_3 = _empty_image(wf, '191', get_image_size_and_count_4.out(2))
    get_image_size_and_count_5 = node(wf, 'GetImageSizeAndCount', '137',
        image=wan_video_decode_138.out(0),
    )
    get_image_size_and_count_6 = node(wf, 'GetImageSizeAndCount', '159',
        image=wanvideodecode_2.out(0),
    )
    imageconcatmulti_5 = _image_concat_multi(wf, '192', get_image_size_and_count_4.out(0), emptyimage_3.out(0), add_label_5.out(0))
    empty_image_132 = _empty_image(wf, '132', get_image_size_and_count_5.out(2))
    emptyimage_2 = _empty_image(wf, '155', get_image_size_and_count_6.out(2))
    vhs_videocombine_4 = _v_h_s__video_combine(wf, '213', imageconcatmulti_5.out(0))
    image_concat_multi_135 = _image_concat_multi(wf, '135', get_image_size_and_count_5.out(0), empty_image_132.out(0), imageconcatmulti_2.out(0))
    imageconcatmulti_3 = _image_concat_multi(wf, '158', get_image_size_and_count_6.out(0), emptyimage_2.out(0), imageconcatmulti_4.out(0))
    video_output_139 = _v_h_s__video_combine(wf, '139', image_concat_multi_135.out(0))
    vhs_videocombine_2 = _v_h_s__video_combine(wf, '165', imageconcatmulti_3.out(0))

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

