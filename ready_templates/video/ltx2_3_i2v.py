# vibecomfy: manual
# Promoted during sprint 7 to preserve snapshot parity while curating public output contracts.
"""Image-to-video generation with LTX 2.3 22B Dev Checkpoint.

Public inputs:
    image (required): Image
    prompt (required): Text prompt
    negative_prompt: Negative text prompt
    seed: Random seed
    width: Output width
    height: Output height
    output_fps: Output playback frame rate
    use_lora: Lightning LoRA branch toggle
    length: Number of output frames

Output: SaveVideo (node 4823).

Source:  workflow_corpus/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json

Packs:   ComfyUI-LTXVideo
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram
from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.resolution import resolution

_PROMPT_DEFAULT = """A traditional Japanese tea ceremony takes place in a tatami room as a host carefully prepares matcha. Soft traditional koto music plays in the background, adding to the serene atmosphere. The bamboo whisk taps rhythmically against the ceramic bowl while water simmers in an iron kettle. Guests kneel in formal seiza position, watching in respectful silence. The host bows and presents the tea bowl, turning it precisely before offering it to the first guest with soft-spoken words."""

MODELS = {
    'ltx_2_3_22b_dev_checkpoint': ModelAsset(
        filename='ltx-2.3-22b-dev.safetensors',
        url='',
        subdir='checkpoints',
    ),
}

PUBLIC_INPUTS = {
    'image': InputSpec(node='2004', field='image', default='example.png', type='IMAGE', required=True, aliases=('input_image', 'start_image'), description='Image.'),
    'prompt': InputSpec(node='2483', field='text', default=_PROMPT_DEFAULT, type='STRING', required=True, description='Text prompt.', media_semantics='text'),
    'negative_prompt': InputSpec(node='2612', field='text', default='pc game, console game, video game, cartoon, childish, ugly', type='STRING', aliases=('negative',), description='Negative text prompt.', media_semantics='text'),
    'seed': InputSpec(node='4814', field='noise_seed', default=42, type='INT', description='Random seed.'),
    'width': InputSpec(node='3059', field='width', default=960, type='INT', description='Output width.'),
    'height': InputSpec(node='3059', field='height', default=544, type='INT', description='Output height.'),
    'output_fps': InputSpec(node='4978', field='value', default=24, type='FLOAT', aliases=('fps',), description='Output playback frame rate.'),
    'use_lora': InputSpec(node='4977', field='value', default=True, type='BOOLEAN', description='Lightning LoRA branch toggle.'),
    'length': InputSpec(node='4979', field='value', default=121, type='INT', aliases=('frames',), description='Number of output frames.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_i2v',
    capability='image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}]},
    provenance={'source_role': 'materialized_ready_python_template', 'smoke_resolution': '256x256x5_frames', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json'},
    coverage_tier='required',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

READY_METADATA["unbound_inputs"].update({'fps': '4978.value', 'frames': '4979.value', 'height': '3059.height', 'image': '2004.image', 'negative_prompt': '2612.text', 'prompt': '2483.text', 'seed': '4814.noise_seed', 'width': '3059.width'})

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ INPUTS ════
    input_image = node(wf, 'LoadImage', '2004',
        image=PUBLIC_INPUTS['image'].default,
    )
    # ════ LOADERS ════
    checkpoint_loader_simple_3940 = node(wf, 'CheckpointLoaderSimple', '3940',
        ckpt_name=MODELS['ltx_2_3_22b_dev_checkpoint'].filename,
    )
    audio_vae = node(wf, 'LTXVAudioVAELoader', '4010',
        ckpt_name=MODELS['ltx_2_3_22b_dev_checkpoint'].filename,
    )
    # ════ SAMPLING ════
    noise_4814 = node(wf, 'RandomNoise', '4814',
        noise_seed=PUBLIC_INPUTS['seed'].default,
    )
    sampler_kind = node(wf, 'KSamplerSelect', '4831',
        sampler_name='euler_ancestral_cfg_pp',
    )
    noise_2 = node(wf, 'RandomNoise', '4832',
        noise_seed=43,
    )
    # ════ TEXT CONDITIONING ════
    ltxavtext_encoder_loader = node(wf, 'LTXAVTextEncoderLoader', '4960',
        ckpt_name=MODELS['ltx_2_3_22b_dev_checkpoint'].filename,
        device='default',
        text_encoder='comfy_gemma_3_12B_it.safetensors',
    )
    guider_parameters_4963 = node(wf, 'GuiderParameters', '4963',
        UNKNOWN=True,
    )
    clown_sampler__beta_4967 = node(wf, 'ClownSampler_Beta', '4967',
        UNKNOWN=True,
    )
    sigmas = node(wf, 'ManualSigmas', '4971',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    use_lora = node(wf, 'PrimitiveBoolean', '4977', value=PUBLIC_INPUTS['use_lora'].default)
    param_float = node(wf, 'PrimitiveFloat', '4978', value=PUBLIC_INPUTS['output_fps'].default)
    param_int = node(wf, 'PrimitiveInt', '4979', value=PUBLIC_INPUTS['length'].default)
    positive_prompt = node(wf, 'CLIPTextEncode', '2483',
        text=PUBLIC_INPUTS['prompt'].default,
        clip=ltxavtext_encoder_loader.out(0),
    )
    negative_prompt = node(wf, 'CLIPTextEncode', '2612',
        text=PUBLIC_INPUTS['negative_prompt'].default,
        clip=ltxavtext_encoder_loader.out(0),
    )
    # ════ LATENT ════
    empty_video_latent = node(wf, 'EmptyLTXVLatentVideo', '3059',
        width=PUBLIC_INPUTS['width'].default,
        height=PUBLIC_INPUTS['height'].default,
        batch_size=1,
        length=param_int.out('INT'),
    )
    # ════ MODEL PATCH STACK ════
    lora_4922 = node(wf, 'LoraLoaderModelOnly', '4922',
        lora_name='ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors',
        strength_model=0.5,
        model=checkpoint_loader_simple_3940.out(0),
    )
    guider_parameters_2 = node(wf, 'GuiderParameters', '4964',
        UNKNOWN=True,
        parameters=guider_parameters_4963.out(0),
    )
    lora_2 = node(wf, 'LoraLoaderModelOnly', '4968',
        lora_name='ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors',
        strength_model=0.2,
        model=checkpoint_loader_simple_3940.out(0),
    )
    # ════ IMAGE PREP ════
    resize_image_mask_node_4981 = node(wf, 'ResizeImageMaskNode', '4981',
        resize_type='scale longer dimension',
        scale_method='lanczos',
        input=input_image.out('IMAGE'),
        _extras={'resize_type.longer_size': 1536},
    )
    fps_int = node(wf, 'LTXFloatToInt', '4985',
        UNKNOWN=0,
        a=param_float.out('FLOAT'),
    )
    conditioning = node(wf, 'LTXVConditioning', '1241',
        frame_rate=param_float.out('FLOAT'),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    preprocessed_image = node(wf, 'LTXVPreprocess', '3336',
        img_compression=18,
        image=resize_image_mask_node_4981.out(0),
    )
    empty_audio_latent = node(wf, 'LTXVEmptyLatentAudio', '3980',
        batch_size=1,
        audio_vae=audio_vae.out('AUDIO_VAE'),
        frame_rate=fps_int.out('INT'),
        frames_number=param_int.out('INT'),
    )
    ltxvimg_to_video_condition_only = node(wf, 'LTXVImgToVideoConditionOnly', '3159',
        UNKNOWN=False,
        bypass=use_lora.out('BOOLEAN'),
        image=preprocessed_image.out('OUTPUT_IMAGE'),
        latent=empty_video_latent.out('LATENT'),
        vae=checkpoint_loader_simple_3940.out(2),
    )
    multimodal_guider_4808 = node(wf, 'MultimodalGuider', '4808',
        UNKNOWN='28',
        model=lora_2.out('MODEL'),
        negative=conditioning.out('NEGATIVE'),
        parameters=guider_parameters_2.out(0),
        positive=conditioning.out('POSITIVE'),
    )
    cfg_guider = node(wf, 'CFGGuider', '4828',
        cfg=1,
        model=lora_4922.out('MODEL'),
        negative=conditioning.out('NEGATIVE'),
        positive=conditioning.out('POSITIVE'),
    )
    av_latent = node(wf, 'LTXVConcatAVLatent', '4528',
        audio_latent=empty_audio_latent.out('LATENT'),
        video_latent=ltxvimg_to_video_condition_only.out(0),
    )
    sampled_latent_1 = node(wf, 'SamplerCustomAdvanced', '4829',
        guider=cfg_guider.out('GUIDER'),
        latent_image=av_latent.out('LATENT'),
        noise=noise_2.out('NOISE'),
        sampler=sampler_kind.out('SAMPLER'),
        sigmas=sigmas.out('SIGMAS'),
    )
    ltxvscheduler = node(wf, 'LTXVScheduler', '4966',
        base_shift=0.95,
        max_shift=2.05,
        steps=15,
        stretch=True,
        terminal=0.1,
        latent=av_latent.out('LATENT'),
    )
    sampled_latent_4802 = node(wf, 'SamplerCustomAdvanced', '4802',
        guider=multimodal_guider_4808.out(0),
        latent_image=av_latent.out('LATENT'),
        noise=noise_4814.out('NOISE'),
        sampler=clown_sampler__beta_4967.out(0),
        sigmas=ltxvscheduler.out(0),
    )
    av_latent_separated_1 = node(wf, 'LTXVSeparateAVLatent', '4845',
        av_latent=sampled_latent_1.out('OUTPUT'),
    )
    av_latent_separated_4824 = node(wf, 'LTXVSeparateAVLatent', '4824',
        av_latent=sampled_latent_4802.out('OUTPUT'),
    )
    # ════ DECODE ════
    decoded_audio_1 = node(wf, 'LTXVAudioVAEDecode', '4848',
        audio_vae=audio_vae.out('AUDIO_VAE'),
        samples=av_latent_separated_1.out('AUDIO_LATENT'),
    )
    ltxvtiled_vaedecode_1 = node(wf, 'LTXVTiledVAEDecode', '4982',
        UNKNOWN='auto',
        latents=av_latent_separated_1.out('VIDEO_LATENT'),
        vae=checkpoint_loader_simple_3940.out(2),
    )
    decoded_audio_4818 = node(wf, 'LTXVAudioVAEDecode', '4818',
        audio_vae=audio_vae.out('AUDIO_VAE'),
        samples=av_latent_separated_4824.out('AUDIO_LATENT'),
    )
    # ════ OUTPUT ════
    video_1 = node(wf, 'CreateVideo', '4849',
        fps=param_float.out('FLOAT'),
        audio=decoded_audio_1.out(0),
        images=ltxvtiled_vaedecode_1.out(0),
    )
    ltxvtiled_vaedecode_2 = node(wf, 'LTXVTiledVAEDecode', '4983',
        UNKNOWN='auto',
        latents=av_latent_separated_4824.out('VIDEO_LATENT'),
        vae=checkpoint_loader_simple_3940.out(2),
    )
    video_4819 = node(wf, 'CreateVideo', '4819',
        fps=param_float.out('FLOAT'),
        audio=decoded_audio_4818.out(0),
        images=ltxvtiled_vaedecode_2.out(0),
    )
    saved_video_1 = node(wf, 'SaveVideo', '4852',
        filename_prefix='output_D',
        format='auto',
        codec='auto',
        video=video_1.out('VIDEO'),
    )
    saved_video_4823 = node(wf, 'SaveVideo', '4823',
        filename_prefix='output_F',
        format='auto',
        codec='auto',
        video=video_4819.out('VIDEO'),
    )

    apply_ltx_lowvram(wf)
    resolution(384, 256, 9).apply(wf)
    ensure_custom_nodes(wf, READY_METADATA["requirements"]["custom_nodes"])
    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='4852',
        output_type='SaveVideo',
        name='',
        mime_type='video/mp4',
        expected_cardinality='one',
        source_path=__file__,
    )

