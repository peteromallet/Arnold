# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXFloatToInt, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode


CKPT_NAME = 'ltx-2.3-22b-dev.safetensors'
DEFAULT_FPS = 24.0
DEFAULT_FRAMES = 121
DEFAULT_PROMPT = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_PROMPT_2 = 'A traditional Japanese tea ceremony takes place in a tatami room as a host carefully prepares matcha. Soft traditional koto music plays in the background, adding to the serene atmosphere. The bamboo whisk taps rhythmically against the ceramic bowl while water simmers in an iron kettle. Guests kneel in formal seiza position, watching in respectful silence. The host bows and presents the tea bowl, turning it precisely before offering it to the first guest with soft-spoken words.'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
ENHANCE_PROMPT_NAME = 'ltx-2.3-22b-dev.safetensors'
FIXED = 'fixed'
GUIDE_STRENGTH = 0.5
GUIDE_STRENGTH_2 = 1
LORA_NAME = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
TEXT_ENCODER_NAME = 'comfy_gemma_3_12B_it.safetensors'


PUBLIC_INPUT_METADATA = {
    'model': InputSpec(node='3', field='ckpt_name', default=CKPT_NAME),
    'seed': InputSpec(node='6', field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node='16', field='text', default=DEFAULT_PROMPT_2),
    'image': InputSpec(node='1', field='image', default='example.png', aliases=('input_image',)),
    'width': InputSpec(node='2', field='width', default=960),
    'height': InputSpec(node='2', field='height', default=544),
    'frames': InputSpec(node='2', field='length', default=DEFAULT_FRAMES),
    'fps': InputSpec(node='36', field='fps', default=DEFAULT_FPS),
    'negative_prompt': InputSpec(node='17', field='text', default=DEFAULT_PROMPT, aliases=('negative',)),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors']},
    custom_node_packs={'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}},
    source_path='workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json',
    source_id='LTX-2.3_T2V_I2V_Two_Stage_Distilled',
    source_type='api',
    source_workflow_path='workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json',
    source_hash='sha256:2ea553cfa291cae680ef2b5834cbdb0f7b3e7ef5a81fe431953a18402931a7ba',
    output_mode='ready_template',
    ready_id='video/ltx2_3_lightricks_two_stage',
    provenance={'source_path': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json', 'source_id': 'LTX-2.3_T2V_I2V_Two_Stage_Distilled', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json', 'source_hash': 'sha256:2ea553cfa291cae680ef2b5834cbdb0f7b3e7ef5a81fe431953a18402931a7ba', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_lightricks_two_stage', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, mask = LoadImage(image='example.png', unused_widget_1='image')

    # Sampling
    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=960,
        height=544,
        length=DEFAULT_FRAMES,
    )

    # Loaders
    model, clip, vae = CheckpointLoaderSimple(ckpt_name=CKPT_NAME)
    ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)
    latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')

    gemmaapitextencode = GemmaAPITextEncode(
        ckpt_name=CKPT_NAME,
        enhance_prompt=ENHANCE_PROMPT_NAME,
    )

    gemmaapitextencode_2 = GemmaAPITextEncode(
        ckpt_name=CKPT_NAME,
        enhance_prompt=False,
        prompt=DEFAULT_PROMPT,
    )

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        text_encoder=TEXT_ENCODER_NAME,
        ckpt_name=CKPT_NAME,
        device='default',
    )

    manualsigmas = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_2 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
    ltxfloattoint = LTXFloatToInt(rounding=0, a=24.0)

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=ltxavtextencoderloader)
    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=ltxavtextencoderloader)

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=121,
        frame_rate=ltxfloattoint,
        audio_vae=ltxvaudiovaeloader,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=model,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale longer dimension',
        scale_method='lanczos',
        unused_widget_1=1536,
        input=image,
    )

    positive, negative = LTXVConditioning(
        frame_rate=24.0,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagemasknode)

    ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
        strength=0.7,
        bypass=True,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vae,
    )

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

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vae,
    )

    ltxvimgtovideoconditiononly_2 = LTXVImgToVideoConditionOnly(
        bypass=True,
        image=resizeimagemasknode,
        latent=ltxvlatentupsampler,
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
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv,
    )

    ltxvtiledvaedecode = LTXVTiledVAEDecode(
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        unused_widget_4='auto',
        unused_widget_5='auto',
        latents=video_latent_ltxv,
        vae=vae,
    )

    createvideo = CreateVideo(
        fps=DEFAULT_FPS,
        audio=ltxvaudiovaedecode,
        images=ltxvtiledvaedecode,
    )

    # Outputs
    savevideo = SaveVideo(filename_prefix='output', video=createvideo)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

