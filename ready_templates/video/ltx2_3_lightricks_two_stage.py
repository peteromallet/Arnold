# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXFloatToInt, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode, LowVRAMAudioVAELoader, LowVRAMCheckpointLoader


CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_FPS = 8
DEFAULT_FRAMES = 5
DEFAULT_PROMPT = 'A traditional Japanese tea ceremony takes place in a tatami room as a host carefully prepares matcha. Soft traditional koto music plays in the background, adding to the serene atmosphere. The bamboo whisk taps rhythmically against the ceramic bowl while water simmers in an iron kettle. Guests kneel in formal seiza position, watching in respectful silence. The host bows and presents the tea bowl, turning it precisely before offering it to the first guest with soft-spoken words.'
DEFAULT_PROMPT_2 = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
GUIDE_STRENGTH = 0.5
GUIDE_STRENGTH_2 = 2.5
IMAGE = 'example.png'
MODEL_NAME = 'ltx-2.3-22b-dev-fp8.safetensors'
MODEL_NAME_2 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_3 = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
WIDGET_0 = ''


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('model'), field='ckpt_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'image': InputSpec(node=ref('image'), field='image', default=IMAGE),
    'input_image': InputSpec(node=ref('image'), field='image', default=IMAGE),
    'width': InputSpec(node=ref('emptyltxvlatentvideo'), field='width', default=256),
    'height': InputSpec(node=ref('emptyltxvlatentvideo'), field='height', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_or_image_to_video_upscale',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}},
    approach='official two-stage low-VRAM T2V/I2V with latent spatial upscaler',
    manual_promotion_rationale='Promoted during sprint 7 because the declared upstream source workflow is absent; preserve the materialized graph and curate public contracts manually.',
    discord_signal='Longer clips and upscale passes were recurring LTX channel themes.',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        image, mask = LoadImage(image=IMAGE, widget_0='example.png')
        model, clip, vae = LowVRAMCheckpointLoader(ckpt_name=MODEL_NAME)
        lowvramaudiovaeloader = LowVRAMAudioVAELoader(ckpt_name=MODEL_NAME)

        # Sampling
        ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')

        randomnoise = RandomNoise(
            noise_seed=DEFAULT_SEED,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        randomnoise_2 = RandomNoise(
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')

        # Inputs
        primitivestring = raw_call('PrimitiveString', '4979', value='')

        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            text_encoder=MODEL_NAME_2,
            ckpt_name=MODEL_NAME,
            device='default',
            widget_0='gemma_3_12B_it_fp4_mixed.safetensors',
            widget_1='ltx-2.3-22b-dev-fp8.safetensors',
        )

        manualsigmas = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        manualsigmas_2 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
        primitiveboolean = raw_call('PrimitiveBoolean', '4987', value=True)
        primitiveint = raw_call('PrimitiveInt', '4988', value=5, widget_1='fixed')
        primitivefloat = raw_call('PrimitiveFloat', '4989', value=8)

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text=DEFAULT_PROMPT,
            clip=ltxavtextencoderloader,
        )

        cliptextencode_2 = CLIPTextEncode(
            text=DEFAULT_PROMPT_2,
            clip=ltxavtextencoderloader,
        )

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=256,
            height=256,
            widget_0=256,
            widget_1=256,
            widget_2=5,
            length=primitiveint,
        )

        loraloadermodelonly = LoraLoaderModelOnly(
            lora_name=MODEL_NAME_3,
            strength_model=GUIDE_STRENGTH,
            model=model,
        )

        gemmaapitextencode = GemmaAPITextEncode(
            widget_0=WIDGET_0,
            widget_1='',
            widget_2=MODEL_NAME,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )

        gemmaapitextencode_2 = GemmaAPITextEncode(
            widget_0=WIDGET_0,
            widget_1=384,
            widget_2=False,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )

        resizeimagemasknode = ResizeImageMaskNode(
            resize_type='scale longer dimension',
            scale_method='lanczos',
            input=image,
        )

        ltxfloattoint = LTXFloatToInt(rounding=0, a=primitivefloat)

        positive, negative = LTXVConditioning(
            widget_0=8,
            frame_rate=primitivefloat,
            negative=cliptextencode_2,
            positive=cliptextencode,
        )

        ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagemasknode)

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            widget_0=5,
            widget_1=8,
            frames_number=primitiveint,
            frame_rate=ltxfloattoint,
            audio_vae=lowvramaudiovaeloader,
        )

        ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
            strength=0.7,
            widget_1=False,
            bypass=primitiveboolean,
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=vae,
        )

        # Conditioning
        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH_2,
            model=loraloadermodelonly,
            negative=negative,
            positive=positive,
        )

        cfgguider_2 = CFGGuider(
            cfg=GUIDE_STRENGTH_2,
            model=loraloadermodelonly,
            negative=negative,
            positive=positive,
        )

        ltxvconcatavlatent = LTXVConcatAVLatent(
            audio_latent=ltxvemptylatentaudio,
            video_latent=ltxvimgtovideoconditiononly,
        )

        # Sampling
        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
        )

        video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

        ltxvimgtovideoconditiononly_2 = LTXVImgToVideoConditionOnly(
            widget_1=False,
            bypass=primitiveboolean,
            image=resizeimagemasknode,
            latent=video_latent,
            vae=vae,
        )

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            audio_latent=audio_latent,
            video_latent=ltxvimgtovideoconditiononly_2,
        )

        output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
        )

        video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
            av_latent=output_sampler,
        )

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            audio_vae=lowvramaudiovaeloader,
            samples=audio_latent_ltxv,
        )

        ltxvtiledvaedecode = LTXVTiledVAEDecode(
            horizontal_tiles=2,
            vertical_tiles=2,
            overlap=6,
            latents=video_latent_ltxv,
            vae=vae,
        )

        createvideo = CreateVideo(
            widget_0=8,
            fps=primitivefloat,
            audio=ltxvaudiovaedecode,
            images=ltxvtiledvaedecode,
        )

        # Outputs
        savevideo = SaveVideo(filename_prefix='output', video=createvideo)

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

