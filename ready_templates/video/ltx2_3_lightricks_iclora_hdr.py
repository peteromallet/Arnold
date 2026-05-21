# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, GetVideoComponents, KSamplerSelect, LTXAVTextEncoderLoader, LTXVConditioning, LTXVCropGuides, LoadVideo, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo, VAEDecodeTiled
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXAddVideoICLoRAGuide, LTXICLoRALoaderModelOnly, LTXVHDRDecodePostprocess, LowVRAMCheckpointLoader


DEFAULT_FPS = 8
DEFAULT_PROMPT = 'pc game, console game, video game, ugly, still, static, slow'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 0.5
GUIDE_STRENGTH_2 = 2.5
MODEL_NAME = 'ltx-2.3-22b-dev-fp8.safetensors'
MODEL_NAME_2 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_3 = 'ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
MODEL_NAME_4 = 'ltx-2.3-22b-ic-lora-hdr-0.9.safetensors'
WIDGET_0 = ''


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('model'), field='ckpt_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default='HDR footage'),
    'fps': InputSpec(node=ref('createvideo'), field='fps', default=DEFAULT_FPS),
}

READY_METADATA = ReadyMetadata.build(
    capability='video_guided_hdr',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['euler_ancestral', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'ltx-2.3-22b-ic-lora-hdr-0.9.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVConditioning', 'LTXVCropGuides'], 'pip_packages': [], 'status': 'pinned'}},
    approach='official IC-LoRA HDR video guide',
    smoke_resolution='256x256x5_frames',
    manual_promotion_rationale='Promoted during sprint 7 because the declared upstream source workflow is absent; preserve the materialized graph and curate public contracts manually.',
    discord_signal='IC-LoRA, relight/HDR, and guide-video workflows were recurring LTX channel themes.',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_HDR_Distilled.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        model, clip, vae = LowVRAMCheckpointLoader(ckpt_name=MODEL_NAME)

        # Sampling
        ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral')

        randomnoise = RandomNoise(
            noise_seed=DEFAULT_SEED,
            control_after_generate='fixed',
        )

        # Inputs
        primitivestring = raw_call('PrimitiveString', '5022', value='')

        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            text_encoder=MODEL_NAME_2,
            ckpt_name=MODEL_NAME,
            device='default',
        )

        manualsigmas = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        loadvideo = LoadVideo(file='ltx_smoke_guide.mp4', video='ltx_smoke_guide.mp4')

        # Conditioning
        cliptextencode = CLIPTextEncode(text='HDR footage', clip=ltxavtextencoderloader)

        cliptextencode_2 = CLIPTextEncode(
            text=DEFAULT_PROMPT,
            clip=ltxavtextencoderloader,
        )

        gemmaapitextencode = GemmaAPITextEncode(
            widget_0=WIDGET_0,
            widget_1='pc game, console game, video game, cartoon, childish, ugly',
            widget_2=False,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )

        gemmaapitextencode_2 = GemmaAPITextEncode(
            widget_0=WIDGET_0,
            widget_1='',
            widget_2=MODEL_NAME,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )

        images, audio, fps = GetVideoComponents(video=loadvideo)

        model_ltxic, latent_downscale_factor = LTXICLoRALoaderModelOnly(
            lora_name=MODEL_NAME_3,
            strength_model=GUIDE_STRENGTH,
            model=model,
        )

        positive, negative = LTXVConditioning(
            frame_rate=fps,
            negative=cliptextencode_2,
            positive=cliptextencode,
        )

        model_ltxic_2, latent_downscale_factor_ltxic = LTXICLoRALoaderModelOnly(
            lora_name=MODEL_NAME_4,
            model=model_ltxic,
        )

        simplemath_ = raw_call('SimpleMath+', '5111',
            _outputs=('INT', 'FLOAT'),
            widget_0='a*32',
            a=latent_downscale_factor_ltxic,
        )

        resizeimagemasknode = ResizeImageMaskNode(
            resize_type='scale to multiple',
            scale_method='lanczos',
            input=images,
            **{'resize_type.multiple': simplemath_.out('INT')},
        )

        width, height, batch_size = GetImageSize(image=resizeimagemasknode)

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=width,
            height=height,
            length=batch_size,
        )

        positive_ltx, negative_ltx, latent = LTXAddVideoICLoRAGuide(
            crop=1,
            use_tiled_encode='disabled',
            tile_size=128,
            tile_overlap=32,
            image=resizeimagemasknode,
            latent=emptyltxvlatentvideo,
            negative=negative,
            positive=positive,
            vae=vae,
        )

        # Conditioning
        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH_2,
            model=model_ltxic_2,
            negative=negative_ltx,
            positive=positive_ltx,
        )

        # Sampling
        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=latent,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
        )

        positive_ltxv, negative_ltxv, latent_ltxv = LTXVCropGuides(
            latent=output,
            negative=negative_ltx,
            positive=positive_ltx,
        )

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            tile_size=768,
            overlap=256,
            temporal_size=8,
            temporal_overlap=4,
            samples=latent_ltxv,
            vae=vae,
        )

        tonemapped, hdr_linear = LTXVHDRDecodePostprocess(
            widget_0=7.1,
            widget_1=True,
            widget_2='output/hdr_exr3',
            widget_3='frame',
            widget_4=True,
            image=vaedecodetiled,
        )

        createvideo = CreateVideo(
            fps=DEFAULT_FPS,
            widget_0=8,
            audio=audio,
            images=hdr_linear,
        )

        # Outputs
        savevideo = SaveVideo(filename_prefix='output', video=createvideo)

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

