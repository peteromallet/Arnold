# vibecomfy: manual
# Promoted because the upstream Lightricks source JSON is not present in this checkout.
"""Video Guided Hdr.

Output: SaveVideo (node 5109).

Source:  workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_HDR_Distilled.json

Packs:   ComfyUI-KJNodes, ComfyUI-LTXVideo
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_lightricks_iclora_hdr',
    capability='video_guided_hdr',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}]},
    provenance={'approach': 'official IC-LoRA HDR video guide', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_HDR_Distilled.json', 'source_role': 'materialized_ready_python_template', 'smoke_resolution': '256x256x5_frames'},
    coverage_tier='required',
    manual_promotion_rationale='Promoted during sprint 7 because the declared upstream source workflow is absent; preserve the materialized graph and curate public contracts manually.',
    discord_signal='IC-LoRA, relight/HDR, and guide-video workflows were recurring LTX channel themes.',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ LOADERS ════
    low_vramcheckpoint_loader = node(wf, 'LowVRAMCheckpointLoader', '3940',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
    )
    # ════ SAMPLING ════
    sampler_kind = node(wf, 'KSamplerSelect', '4831',
        sampler_name='euler_ancestral',
    )
    noise = node(wf, 'RandomNoise', '4832',
        noise_seed=42,
        control_after_generate='fixed',
    )
    param_string = node(wf, 'PrimitiveString', '5022', value='')
    # ════ TEXT CONDITIONING ════
    ltxavtext_encoder_loader = node(wf, 'LTXAVTextEncoderLoader', '5023',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
        text_encoder='gemma_3_12B_it_fp4_mixed.safetensors',
        
        device='default',
    )
    sigmas = node(wf, 'ManualSigmas', '5025',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    input_video = node(wf, 'LoadVideo', '5106',
        file='ltx_smoke_guide.mp4',
        video='ltx_smoke_guide.mp4',
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '2483',
        text='HDR footage',
        clip=ltxavtext_encoder_loader.out(0),
    )
    negative_prompt = node(wf, 'CLIPTextEncode', '2612',
        text='pc game, console game, video game, ugly, still, static, slow',
        clip=ltxavtext_encoder_loader.out(0),
    )
    gemma_apitext_encode_1 = node(wf, 'GemmaAPITextEncode', '5020',
        widget_0='',
        widget_1='pc game, console game, video game, cartoon, childish, ugly',
        widget_2=False,
        widget_3='ltx-2.3-22b-dev-fp8.safetensors',
        api_key=param_string.out(0),
    )
    gemma_apitext_encode_2 = node(wf, 'GemmaAPITextEncode', '5021',
        widget_0='',
        widget_1='',
        widget_2='ltx-2.3-22b-dev-fp8.safetensors',
        widget_3='ltx-2.3-22b-dev-fp8.safetensors',
        api_key=param_string.out(0),
    )
    # ════ IMAGE PREP ════
    video_components = node(wf, 'GetVideoComponents', '5105',
        video=input_video.out('VIDEO'),
    )
    # ════ MODEL PATCH STACK ════
    final_model_with_ic_lora_1 = node(wf, 'LTXICLoRALoaderModelOnly', '5125',
        lora_name='ltx-2.3-22b-distilled-lora-384-1.1.safetensors',
        strength_model=0.5,
        model=low_vramcheckpoint_loader.out(0),
    )
    conditioning = node(wf, 'LTXVConditioning', '1241',
        frame_rate=video_components.out(2),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    final_model_with_ic_lora_5011 = node(wf, 'LTXICLoRALoaderModelOnly', '5011',
        lora_name='ltx-2.3-22b-ic-lora-hdr-0.9.safetensors',
        strength_model=1,
        model=final_model_with_ic_lora_1.out('MODEL'),
    )
    simplemath_ = node(wf, 'SimpleMath+', '5111',
        widget_0='a*32',
        a=final_model_with_ic_lora_5011.out('LATENT_DOWNSCALE_FACTOR'),
    )
    resize_image_mask_node_5112 = node(wf, 'ResizeImageMaskNode', '5112',
        resize_type='scale to multiple',
scale_method='lanczos',
        input=video_components.out('IMAGES'),
        _extras={'resize_type.multiple': simplemath_.out(0)},
    )
    get_image_size_5029 = node(wf, 'GetImageSize', '5029',
        image=resize_image_mask_node_5112.out(0),
    )
    # ════ LATENT ════
    empty_video_latent = node(wf, 'EmptyLTXVLatentVideo', '3059',
        batch_size=1,
        
        
        width=get_image_size_5029.out(0),
        height=get_image_size_5029.out(1),
        length=get_image_size_5029.out(2),
    )
    guided_latent = node(wf, 'LTXAddVideoICLoRAGuide', '5012',
        frame_idx=0,
        strength=1,
        crop=1,
        use_tiled_encode='disabled',
tile_size=128,
        tile_overlap=32,
        image=resize_image_mask_node_5112.out(0),
        latent=empty_video_latent.out('LATENT'),
        negative=conditioning.out('NEGATIVE'),
        positive=conditioning.out('POSITIVE'),
        vae=low_vramcheckpoint_loader.out(2),
    )
    cfg_guider = node(wf, 'CFGGuider', '4828',
        cfg=2.5,
        model=final_model_with_ic_lora_5011.out('MODEL'),
        negative=guided_latent.out('NEGATIVE'),
        positive=guided_latent.out('POSITIVE'),
    )
    sampled_latent = node(wf, 'SamplerCustomAdvanced', '4829',
        guider=cfg_guider.out('GUIDER'),
        latent_image=guided_latent.out('LATENT'),
        noise=noise.out('NOISE'),
        sampler=sampler_kind.out('SAMPLER'),
        sigmas=sigmas.out('SIGMAS'),
    )
    cropped_latent = node(wf, 'LTXVCropGuides', '5013',
        latent=sampled_latent.out('OUTPUT'),
        negative=guided_latent.out('NEGATIVE'),
        positive=guided_latent.out('POSITIVE'),
    )
    # ════ DECODE ════
    decoded_video = node(wf, 'VAEDecodeTiled', '4851',
        tile_size=768,
        overlap=256,
        temporal_size=8,
        temporal_overlap=4,
        samples=cropped_latent.out(2),
        vae=low_vramcheckpoint_loader.out(2),
    )
    ltxvhdrdecode_postprocess = node(wf, 'LTXVHDRDecodePostprocess', '5114',
        widget_0=7.1,
        widget_1=True,
        widget_2='output/hdr_exr3',
        widget_3='frame',
        widget_4=True,
        image=decoded_video.out('IMAGE'),
    )
    # ════ OUTPUT ════
    video = node(wf, 'CreateVideo', '5108',
        fps=8,
        widget_0=8,
        audio=video_components.out(1),
        images=ltxvhdrdecode_postprocess.out(1),
    )
    saved_video = node(wf, 'SaveVideo', '5109',
        filename_prefix='output',
        format='auto',
        codec='auto',
        video=video.out('VIDEO'),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='5109',
        output_type='SaveVideo',
        name='video',
        mime_type='video/mp4',
        expected_cardinality='one',
        source_path=__file__,
    )

