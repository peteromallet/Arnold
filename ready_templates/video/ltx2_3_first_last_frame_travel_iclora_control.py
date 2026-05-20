"""LTX 2.3 first/last-frame travel with full-length IC-LoRA control guide.

Public inputs:
    start_image: Starting image
    end_image: Ending image
    control_video: Control video
    control_mode: Control branch selector
    prompt: Text prompt
    negative_prompt: Negative text prompt
    seed: Random seed
    width: Output width
    height: Output height
    output_fps: Output playback frame rate
    ic_lora_filename: IC-LoRA model filename
    ic_lora_strength: IC-LoRA strength
    seed_refine: Refine-pass random seed
    length: Number of output frames
    guide_strength: Guide strength

Output: VHS_VideoCombine (node 43).

Source:  manual composition of Runexx first/last frame and Lightricks IC-LoRA union control

Packs:   ComfyUI-DepthAnythingV2, ComfyUI-KJNodes, ComfyUI-LTXVideo, ComfyUI-VideoHelperSuite, comfyui_controlnet_aux
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

ANCHOR_STRENGTH = 0.8
CONTROL_RESOLUTION = 256
# Step count = list length (currently 9 steps refine).
REFINE_SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
# Step count = list length (currently 4 steps finish).
FINISH_SIGMAS = "0.85, 0.7250, 0.4219, 0.0"

_PROMPT_DEFAULT = """A cinematic first-to-last-frame travel shot with smooth continuous camera motion, coherent subject motion, realistic lighting, and natural temporal consistency."""

_NEGATIVE_PROMPT_DEFAULT = """blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles"""

MODELS = {
    'ltx_2_3_text_projection_bf16': ModelAsset(
        filename='ltx-2.3_text_projection_bf16.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors',
        subdir='text_encoders',
    ),
    'ltx23_video_vae_bf16': ModelAsset(
        filename='LTX23_video_vae_bf16.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors',
        subdir='vae',
    ),
    'ltx23_audio_vae_bf16': ModelAsset(
        filename='LTX23_audio_vae_bf16.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors',
        subdir='checkpoints',
    ),
    'taeltx2_3': ModelAsset(
        filename='taeltx2_3.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors',
        subdir='vae',
    ),
    'ltx_2_3_22b_distilled_1_1_transformer_only': ModelAsset(
        filename='ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
        subdir='diffusion_models',
    ),
    'ltx_2_3_22b_distilled_1_1_lora_dynamic_fro': ModelAsset(
        filename='LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors',
        subdir='loras',
    ),
    'depth_anything_v2_vits_fp32': ModelAsset(
        filename='depth_anything_v2_vits_fp32.safetensors',
        url='https://huggingface.co/Kijai/DepthAnythingV2-safetensors/resolve/main/depth_anything_v2_vits_fp32.safetensors',
        subdir='depthanything',
    ),
    'yolox_l': ModelAsset(
        filename='yolox_l.onnx',
        url='https://huggingface.co/yzd-v/DWPose/resolve/main/yolox_l.onnx',
        subdir='controlnet_aux',
        target_path='custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx',
    ),
    'dw_ll_ucoco_384_bs5_torchscript': ModelAsset(
        filename='dw-ll_ucoco_384_bs5.torchscript.pt',
        url='https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt',
        subdir='controlnet_aux',
        target_path='custom_nodes/comfyui_controlnet_aux/ckpts/hr16/DWPose-TorchScript-BatchSize5/dw-ll_ucoco_384_bs5.torchscript.pt',
    ),
    'gemma_clip': ModelAsset(
        filename='gemma_3_12B_it_fp4_mixed.safetensors',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {
    'start_image': InputSpec(node='45', field='image', default='example.png', type='STRING', description='Starting image.', media_semantics='image'),
    'end_image': InputSpec(node='47', field='image', default='egyptian_queen.png', type='STRING', description='Ending image.', media_semantics='image'),
    'control_video': InputSpec(node='5001', field='video', default='ltx_smoke_guide.mp4', type='STRING', description='Control video.', media_semantics='video'),
    'control_mode': InputSpec(node='6000', field='value', default='canny', type='STRING', description='Control branch selector.'),
    'prompt': InputSpec(node='16', field='text', default=_PROMPT_DEFAULT, type='STRING', description='Text prompt.', media_semantics='text'),
    'negative_prompt': InputSpec(node='11', field='text', default=_NEGATIVE_PROMPT_DEFAULT, type='STRING', aliases=('negative',), description='Negative text prompt.', media_semantics='text'),
    'seed': InputSpec(node='14', field='noise_seed', default=43, type='STRING', description='Random seed.'),
    'width': InputSpec(node='2080', field='value', default=256, type='STRING', description='Output width.'),
    'height': InputSpec(node='2079', field='value', default=256, type='STRING', description='Output height.'),
    'output_fps': InputSpec(node='2076', field='value', default=8, type='STRING', aliases=('fps',), description='Output playback frame rate.'),
    'ic_lora_filename': InputSpec(node='5011', field='lora_name', default='ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors', type='STRING', description='IC-LoRA model filename.'),
    'ic_lora_strength': InputSpec(node='5011', field='strength_model', default=1, type='STRING', description='IC-LoRA strength.'),
    'seed_refine': InputSpec(node='15', field='noise_seed', default=42, type='INT', description='Refine-pass random seed.'),
    'length': InputSpec(node='2078', field='value', default=9, type='STRING', aliases=('frames',), description='Number of output frames.'),
    'guide_strength': InputSpec(node='5012', field='strength', default=1, type='STRING', aliases=('strength',), description='Guide strength.'),
}

# vibecomfy: narrative (generated by tools/narrate_template.py @ 0.1.0+g9c5810f+dirty)
# ported from manual composition of Runexx first/last frame and Lightricks IC-LoRA union control (sha256: 9c48c9b95bad68ed8196e239dedfd5ec887836e569e21bcb60ff6e5ec0a9c0a2)
READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_first_last_frame_travel_iclora_control',
    capability='first_last_frame_control_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'models': [],
 'custom_nodes': ['ComfyUI-DepthAnythingV2',
                  'ComfyUI-KJNodes',
                  'ComfyUI-LTXVideo',
                  'ComfyUI-VideoHelperSuite',
                  'comfyui_controlnet_aux'],
 'custom_node_refs': [{'slug': 'ComfyUI-DepthAnythingV2',
                       'source': 'git',
                       'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git'},
                      {'slug': 'ComfyUI-KJNodes',
                       'source': 'git',
                       'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df',
                       'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'},
                      {'slug': 'ComfyUI-LTXVideo',
                       'source': 'git',
                       'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'},
                      {'slug': 'ComfyUI-VideoHelperSuite',
                       'source': 'git',
                       'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'},
                      {'slug': 'comfyui_controlnet_aux',
                       'source': 'git',
                       'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git'}]},
    provenance={'source_role': 'manual_ready_python_template', 'smoke_resolution': '256x256x9_frames', 'approach': 'first/last-frame image anchors plus full-length raw/pose/depth/canny IC-LoRA guide branches', 'source_workflow': 'manual composition of Runexx first/last frame and Lightricks IC-LoRA union control'},
    coverage_tier='required',
    runtime_note='Default guide branch is Canny. Patch node 5012 input image to select raw, pose, or depth branches.',
    discord_signal='Combines recurring LTX first/last travel and full-length control-guide workflows.',
    ltx_best_practices=['Use first/last anchors for travel endpoints.', 'Use a full-length guide video with IC-LoRA union-control conditioning.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loader settings.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'min_version': None, 'tested_at': None, 'commit': None, 'status': 'unavailable'},
)

def build() -> VibeWorkflow:
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    sampler_refine = node(wf, "KSamplerSelect", "1", sampler_name="euler_ancestral_cfg_pp")
    sampler_finish = node(wf, "KSamplerSelect", "4", sampler_name="euler_cfg_pp")
    randomnoise_finish = node(wf, "RandomNoise", "14", noise_seed=PUBLIC_INPUTS['seed'].default, control_after_generate="fixed")
    randomnoise_refine = node(wf, "RandomNoise", "15", noise_seed=PUBLIC_INPUTS['seed_refine'].default, control_after_generate="fixed")

    # ════ INPUTS ════
    start_image = node(wf, "LoadImage", "45", image=PUBLIC_INPUTS['start_image'].default,)
    end_image = node(wf, "LoadImage", "47", image=PUBLIC_INPUTS['end_image'].default,)
    control_video = node(
        wf,
        "LoadVideo",
        "5001",
        file="ltx_smoke_guide.mp4",
        video=PUBLIC_INPUTS['control_video'].default,
    )
    # parity-preserved label (edit PUBLIC_INPUTS['control_mode'].default to change)
    control_mode = node(wf, "PrimitiveString", "6000", value=PUBLIC_INPUTS['control_mode'].default)

    fps = node(wf, "PrimitiveFloat", "2076", value=PUBLIC_INPUTS['output_fps'].default)
    frames = node(wf, "INTConstant", "2078", value=PUBLIC_INPUTS['length'].default)
    height = node(wf, "INTConstant", "2079", value=PUBLIC_INPUTS['height'].default)
    width = node(wf, "INTConstant", "2080", value=PUBLIC_INPUTS['width'].default)
    first_strength = node(wf, "PrimitiveFloat", "2110", value=ANCHOR_STRENGTH)
    last_strength = node(wf, "PrimitiveFloat", "2108", value=ANCHOR_STRENGTH)
    assert first_strength.node.inputs["value"] == last_strength.node.inputs["value"]

    # ════ LOADERS ════
    video_vae = node(wf, "VAELoader", "181", vae_name=MODELS['ltx23_video_vae_bf16'].filename)
    # parity-preserved leaves:
    _tiny_vae = node(wf, "VAELoader", "180", vae_name=MODELS['taeltx2_3'].filename)
    audio_vae = node(wf, "LTXVAudioVAELoader", "175", ckpt_name=MODELS['ltx23_audio_vae_bf16'].filename)
    unet = node(
        wf,
        "UNETLoader",
        "187",
        unet_name=MODELS['ltx_2_3_22b_distilled_1_1_transformer_only'].filename,
        weight_dtype="default",
    )
    clip = node(
        wf,
        "DualCLIPLoader",
        "190",
        clip_name1=MODELS['gemma_clip'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16'].filename,
        type="ltxv",
        device="default",
    )
    # ════ MODEL PATCH STACK ════
    distilled_lora = node(
        wf,
        "LoraLoaderModelOnly",
        "186",
        lora_name=MODELS['ltx_2_3_22b_distilled_1_1_lora_dynamic_fro'].filename,
        strength_model=0.6,
        model=unet.out('MODEL'),
    )
    nag_model = node(
    # INTENTIONAL CHAIN BYPASS: takes UNETLoader directly; does NOT inherit the LoraLoaderModelOnly/PathchSageAttentionKJ/LTXVChunkFeedForward/LTX2AttentionTunerPatch/LTXICLoRALoaderModelOnly patches. consumed elsewhere (likely a separate sampler).
        wf,
        "LTX2_NAG",
        "197",
        nag_scale=11,
        nag_alpha=0.25,
        nag_tau=2.5,
        model=unet.out('MODEL'),
    )
    # Upstream class is misspelled; do not rename.
    sage = node(wf, "PathchSageAttentionKJ", "226", sage_attention="disabled", allow_compile=False, model=distilled_lora.out('MODEL'))
    chunked = node(wf, "LTXVChunkFeedForward", "228", chunks=2, dim_threshold=4096, model=sage.out('MODEL'))
    tuned = node(
        wf,
        "LTX2AttentionTunerPatch",
        "229",
        blocks="",
        video_scale=1,
        audio_scale=1,
        video_to_audio_scale=1,
        audio_to_video_scale=1,
        triton_kernels=False,
        model=chunked.out('MODEL'),
    )
    ic_lora = node(
        wf,
        "LTXICLoRALoaderModelOnly",
        "5011",
        lora_name=PUBLIC_INPUTS['ic_lora_filename'].default,
        strength_model=PUBLIC_INPUTS['ic_lora_strength'].default,
        model=tuned.out('MODEL'),
    )

    # ════ TEXT CONDITIONING ════
    negative_prompt = node(
        wf,
        "CLIPTextEncode",
        "11",
        text=PUBLIC_INPUTS['negative_prompt'].default,
        clip=clip.out('CLIP'),
    )
    positive_prompt = node(
        wf,
        "CLIPTextEncode",
        "16",
        text=PUBLIC_INPUTS['prompt'].default,
        clip=clip.out('CLIP'),
    )
    conditioning = node(
        wf,
        "LTXVConditioning",
        "10",
        frame_rate=fps.out('FLOAT'),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )

    start_resized = node(wf, 'ImageResizeKJv2', '44', upscale_method='nearest-exact', keep_proportion='crop', pad_color='0, 0, 0', crop_position='center', divisible_by=32, device='cpu', width=width.out('VALUE'), height=height.out('VALUE'), image=start_image.out('IMAGE'))
    end_resized = node(wf, 'ImageResizeKJv2', '48', upscale_method='nearest-exact', keep_proportion='crop', pad_color='0, 0, 0', crop_position='center', divisible_by=32, device='cpu', width=width.out('VALUE'), height=height.out('VALUE'), image=end_image.out('IMAGE'))
    # ════ IMAGE PREP ════
    first_preprocessed = node(wf, "LTXVPreprocess", "2084", img_compression=18, image=start_resized.out('IMAGE'))
    last_preprocessed = node(wf, "LTXVPreprocess", "50", img_compression=18, image=end_resized.out('IMAGE'))

    components = node(wf, "GetVideoComponents", "5000", video=control_video.out('VIDEO'))
    guide_resized = node(wf, 'ImageResizeKJv2', '5026', upscale_method='lanczos', keep_proportion='stretch', pad_color='0, 0, 0', crop_position='center', divisible_by=32, device='cpu', width=width.out('VALUE'), height=height.out('VALUE'), image=components.out('IMAGES'))
    guide_raw = node(wf, 'ImageResizeKJv2', '6101', upscale_method='lanczos', keep_proportion='stretch', pad_color='0, 0, 0', crop_position='center', divisible_by=32, device='cpu', width=width.out('VALUE'), height=height.out('VALUE'), image=guide_resized.out('IMAGE'))
    # ════ CONTROL ════
    guide_pose = node(
        wf,
        "DWPreprocessor",
        "4986",
        detect_hand="enable",
        detect_body="enable",
        detect_face="enable",
        resolution=CONTROL_RESOLUTION,
        bbox_detector=MODELS['yolox_l'].filename,
        pose_estimator=MODELS['dw_ll_ucoco_384_bs5_torchscript'].filename,
        scale_stick_for_xinsr_cn="disable",
        image=guide_resized.out('IMAGE'),
    )
    guide_canny_edges = node(
        wf,
        "CannyEdgePreprocessor",
        "4991",
        low_threshold=92,
        high_threshold=200,
        resolution=CONTROL_RESOLUTION,
        image=guide_resized.out('IMAGE'),
    )
    depth_model = node(wf, "DownloadAndLoadDepthAnythingV2Model", "5060", model=MODELS['depth_anything_v2_vits_fp32'].filename, precision="fp32")
    guide_depth = node(wf, "DepthAnything_V2", "5061", da_model=depth_model.out('DA_V2_MODEL'), images=guide_resized.out('IMAGE'))
    guide_canny = node(wf, 'ImageResizeKJv2', '5028', upscale_method='lanczos', keep_proportion='stretch', pad_color='0, 0, 0', crop_position='center', divisible_by=32, device='cpu', width=width.out('VALUE'), height=height.out('VALUE'), image=guide_canny_edges.out('IMAGE'))
    guide_pose_sized = node(wf, 'ImageResizeKJv2', '6102', upscale_method='lanczos', keep_proportion='stretch', pad_color='0, 0, 0', crop_position='center', divisible_by=32, device='cpu', width=width.out('VALUE'), height=height.out('VALUE'), image=guide_pose.out('IMAGE'))
    guide_depth_sized = node(wf, 'ImageResizeKJv2', '6103', upscale_method='lanczos', keep_proportion='stretch', pad_color='0, 0, 0', crop_position='center', divisible_by=32, device='cpu', width=width.out('VALUE'), height=height.out('VALUE'), image=guide_depth.out('IMAGE'))

    # ════ LATENT ════
    latent = node(
        wf,
        "EmptyLTXVLatentVideo",
        "32",
        batch_size=1,
        
        
        width=width.out('VALUE'),
        height=height.out('VALUE'),
        length=frames.out('VALUE'),
    )
    fps_int = node(wf, "LTXFloatToInt", "5066", rounding=0, a=fps.out('FLOAT'))
    audio_latent = node(
        wf,
        "LTXVEmptyLatentAudio",
        "9",
        
        batch_size=1,
        audio_vae=audio_vae.out('AUDIO_VAE'),
        frame_rate=fps_int.out('INT'),
        frames_number=frames.out('VALUE'),
    )
    anchored_latent = node(
        wf,
        "LTXVImgToVideoInplaceKJ",
        "210",
        latent=latent.out('LATENT'),
        num_images="2",
        vae=video_vae.out('VAE'),
        _extras={
            "num_images.image_1": first_preprocessed.out('OUTPUT_IMAGE'),
            "num_images.image_2": last_preprocessed.out('OUTPUT_IMAGE'),
            "num_images.index_1": 0,
            "num_images.index_2": -1,
            "num_images.strength_1": first_strength.out('FLOAT'),
            "num_images.strength_2": last_strength.out('FLOAT'),
        },
    )

    GUIDE_BRANCH = PUBLIC_INPUTS['control_mode'].default  # one of: 'canny', 'raw', 'pose', 'depth'
    GUIDE_NODES = {
        'canny': guide_canny,
        'depth': guide_depth_sized,
        'pose': guide_pose_sized,
        'raw': guide_raw,
    }
    guided = node(
    # BRANCH SELECTION: 'image=' picks which control branch is active. Currently wired to node 5028 (canny). Alternatives: 6101 (raw), 6102 (pose), 6103 (depth).
        wf,
        "LTXAddVideoICLoRAGuide",
        "5012",
        frame_idx=0,
        strength=PUBLIC_INPUTS['guide_strength'].default,
        crop="center",
        use_tiled_encode="disabled",
        tile_size=128,
        tile_overlap=32,
        image=GUIDE_NODES[GUIDE_BRANCH].out("IMAGE"),
        latent=anchored_latent.out('LATENT'),
        latent_downscale_factor=ic_lora.out('LATENT_DOWNSCALE_FACTOR'),
        negative=conditioning.out('NEGATIVE'),
        positive=conditioning.out('POSITIVE'),
        vae=video_vae.out('VAE'),
    )
    av_latent = node(wf, "LTXVConcatAVLatent", "24", audio_latent=audio_latent.out('LATENT'), video_latent=guided.out('LATENT'))
    # Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning
    # Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning
    cfg_refine = node(wf, "CFGGuider", "36", cfg=2.5, model=nag_model.out('MODEL'), negative=conditioning.out('NEGATIVE'), positive=conditioning.out('POSITIVE'))
    sigmas_refine = node(wf, "ManualSigmas", "215", sigmas=REFINE_SIGMAS)
    refined = node(
        wf,
        "SamplerCustomAdvanced",
        "13",
        guider=cfg_refine.out('GUIDER'),
        latent_image=av_latent.out('LATENT'),
        noise=randomnoise_refine.out('NOISE'),
        sampler=sampler_refine.out('SAMPLER'),
        sigmas=sigmas_refine.out('SIGMAS'),
    )
    separated_refined = node(wf, "LTXVSeparateAVLatent", "18", av_latent=refined.out('OUTPUT'))
    av_latent_finish = node(wf, "LTXVConcatAVLatent", "34", audio_latent=separated_refined.out('AUDIO_LATENT'), video_latent=separated_refined.out('VIDEO_LATENT'))
    cfg_finish = node(wf, "CFGGuider", "8", cfg=2.5, model=ic_lora.out('MODEL'), negative=guided.out('NEGATIVE'), positive=guided.out('POSITIVE'))
    sigmas_finish = node(wf, "ManualSigmas", "216", sigmas=FINISH_SIGMAS)
    finished = node(
        wf,
        "SamplerCustomAdvanced",
        "21",
        guider=cfg_finish.out('GUIDER'),
        latent_image=av_latent_finish.out('LATENT'),
        noise=randomnoise_finish.out('NOISE'),
        sampler=sampler_finish.out('SAMPLER'),
        sigmas=sigmas_finish.out('SIGMAS'),
    )
    separated_finished = node(wf, "LTXVSeparateAVLatent", "146", av_latent=finished.out('OUTPUT'))
    cropped = node(wf, "LTXVCropGuides", "2156", latent=separated_finished.out('VIDEO_LATENT'), negative=guided.out('NEGATIVE'), positive=guided.out('POSITIVE'))
    # ════ DECODE ════
    _decoded_audio = node(wf, "LTXVAudioVAEDecode", "150", audio_vae=audio_vae.out('AUDIO_VAE'), samples=separated_finished.out('AUDIO_LATENT'))
    decoded_video = node(
        wf,
        "VAEDecodeTiled",
        "149",
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
        samples=cropped.out('LATENT'),
        vae=video_vae.out('VAE'),
    )
    # ════ OUTPUT ════
    output = node(
        wf,
        "VHS_VideoCombine",
        "43",
        filename_prefix="reigh_vibecomfy_ltx_control_first_last",
        format="video/h264-mp4",
        frame_rate=fps.out('FLOAT'),
        images=decoded_video.out('IMAGE'),
        loop_count=0,
        pingpong=False,
        save_output=True,
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='43',
        output_type='VHS_VideoCombine',
        name='video',
        mime_type='video/mp4',
        expected_cardinality='one',
        filename_prefix='',
        source_path=__file__,
        
    )
