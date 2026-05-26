# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, GetVideoComponents, KSamplerSelect, LTXAVTextEncoderLoader, LTXVConditioning, LTXVCropGuides, LoadVideo, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo, VAEDecodeTiled
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXAddVideoICLoRAGuide, LTXICLoRALoaderModelOnly, LTXVHDRDecodePostprocess


API_KEY = ''
DEFAULT_FPS = 30
DEFAULT_PROMPT = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_PROMPT_2 = 'pc game, console game, video game, ugly, still, static, slow'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.5
MODEL_NAME = 'comfy_gemma_3_12B_it.safetensors'
MODEL_NAME_2 = 'ltx-2.3-22b-dev.safetensors'
MODEL_NAME_3 = 'ltxv/ltx2/ltx-2.3-22b-ic-lora-hdr-0.9.safetensors'
MODEL_NAME_4 = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='4832', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'fps': InputSpec(node='5108', field='fps', default=DEFAULT_FPS, type='FLOAT'),
    'prompt': InputSpec(node='2483', field='text', default='HDR footage', type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='2612', field='text', default=DEFAULT_PROMPT_2, type='STRING', aliases=('negative',), media_semantics='text'),
}


def PUBLIC_INPUTS(**nodes):
    randomnoise = nodes['randomnoise']
    createvideo = nodes['createvideo']
    cliptextencode = nodes['cliptextencode']
    cliptextencode_2 = nodes['cliptextencode_2']
    return {
    'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'fps': InputSpec(node=createvideo, field='fps', default=DEFAULT_FPS, type='FLOAT'),
    'prompt': InputSpec(node=cliptextencode, field='text', default='HDR footage', type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node=cliptextencode_2, field='text', default=DEFAULT_PROMPT_2, type='STRING', aliases=('negative',), media_semantics='text'),
    }

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['euler_ancestral', 'ltx-2.3-22b-dev.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'ltxv/ltx2/ltx-2.3-22b-ic-lora-hdr-0.9.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVConditioning', 'LTXVCropGuides'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_HDR_Distilled.json', 'source_id': 'LTX-2.3_ICLoRA_HDR_Distilled', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_HDR_Distilled.json', 'source_hash': 'sha256:63dfbf9819ccbc4189964b6adccec84199e9763621c40ba0dd0f2eb0e462fd25', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_lightricks_iclora_hdr'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Loaders
        model, clip, vae = CheckpointLoaderSimple(ckpt_name=MODEL_NAME_2)

        # Sampling
        ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral')

        randomnoise = RandomNoise(
            noise_seed=DEFAULT_SEED,
            control_after_generate='fixed',
        )

        gemmaapitextencode = GemmaAPITextEncode(
            ckpt_name=MODEL_NAME_2,
            enhance_prompt=False,
            prompt=DEFAULT_PROMPT,
            widget_0='',
        )

        gemmaapitextencode_2 = GemmaAPITextEncode(
            ckpt_name=MODEL_NAME_2,
            enhance_prompt=MODEL_NAME_2,
            widget_0='',
        )

        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            text_encoder=MODEL_NAME,
            ckpt_name=MODEL_NAME_2,
            device='default',
        )

        manualsigmas = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        loadvideo = LoadVideo(file='hdr_input_video (1).mp4', unused_widget_1='image')

        # Conditioning
        cliptextencode = CLIPTextEncode(text='HDR footage', clip=ltxavtextencoderloader)

        cliptextencode_2 = CLIPTextEncode(
            text=DEFAULT_PROMPT_2,
            clip=ltxavtextencoderloader,
        )

        images, audio, fps = GetVideoComponents(video=loadvideo)

        model_ltxic_2, latent_downscale_factor_ltxic = LTXICLoRALoaderModelOnly(
            lora_name=MODEL_NAME_4,
            strength_model=GUIDE_STRENGTH_2,
            model=model,
        )

        positive, negative = LTXVConditioning(
            frame_rate=fps,
            negative=cliptextencode_2,
            positive=cliptextencode,
        )

        model_ltxic, latent_downscale_factor = LTXICLoRALoaderModelOnly(
            lora_name=MODEL_NAME_3,
            model=model_ltxic_2,
        )

        simplemath_ = raw_call('SimpleMath+', '5111', value='a*32', a=latent_downscale_factor)

        resizeimagemasknode = ResizeImageMaskNode(
            resize_type='scale to multiple',
            scale_method='lanczos',
            unused_widget_1=32,
            input=images,
            **{'resize_type.multiple': simplemath_.out(0)},
        )

        width, height, batch_size = GetImageSize(image=resizeimagemasknode)

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=width,
            height=height,
            length=batch_size,
        )

        positive_ltx, negative_ltx, latent = LTXAddVideoICLoRAGuide(
            crop=1,
            use_tiled_encode='disabled',
            unused_widget_4=False,
            image=resizeimagemasknode,
            latent=emptyltxvlatentvideo,
            negative=negative,
            positive=positive,
            vae=vae,
        )

        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH,
            model=model_ltxic,
            negative=negative_ltx,
            positive=positive_ltx,
        )

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
            exposure=7.1,
            output_dir='output/hdr_exr3',
            save_exr=True,
            image=vaedecodetiled,
        )

        createvideo = CreateVideo(audio=audio, images=hdr_linear)

        # Outputs
        savevideo = SaveVideo(filename_prefix='output', video=createvideo)

        return wf.finalize(PUBLIC_INPUTS(**locals()), output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

