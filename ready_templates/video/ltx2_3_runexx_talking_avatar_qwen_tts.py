# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PreviewAudio, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSVoiceClone
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_NAME_GGUF = 'gemma-3-12b-it-Q2_K.gguf'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
FIXED = 'fixed'
FULL_TRACK = 'full_track'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 1
LINEAR_QUADRATIC = 'linear_quadratic'
LORA_NAME = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
MODEL_NAME_2 = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'
UNET_NAME = 'LTXVideo\\v2\\ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
UNET_NAME_GGUF = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
VAE_TAESD_NAME = 'vae_approx\\taeltx2_3.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'


PUBLIC_INPUT_METADATA = {
    'enhance_prompt': InputSpec(node='1926', field='_un3491', default=True),
    'image': InputSpec(node='444', field='image', default='17745317855d08.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='1832', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node='1626', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo\\v2\\ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx\\taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSVoiceClone'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json', 'source_id': 'LTX-2.3_Talking_Avatar_Qwen_TTS', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_talking_avatar_qwen_tts'},
)

# === Subgraph functions ===

def calculate_frames(
    *,
    audio,
):
    """Calculate Frames.

    Materialized from subgraph 63e8c999-0a69-4f62-af3f-8b77f0095971 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json.
    # vibecomfy source hash: sha256:014978879e8c31d5f5008fa123d298ac383b594f03e1d8d75c11ceabc1cd6d0b
    Inner nodes: Audio Duration (mtb), SimpleCalculatorKJx3, LazySwitchKJ.
    """

    audio_duration__mtb_ = raw_call('Audio Duration (mtb)', '1864', _outputs=('duration_ms',), audio=audio)

    calc_float_simple, calc_int_simple, calc_bool_simple = SimpleCalculatorKJ(
        expression='ceil(a/1000)',
        **{'variables.a': audio_duration__mtb_.out('duration_ms')},
    )

    calc_float, calc_int, calc_bool = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': calc_int_simple},
    )

    calc_float_simple_2, calc_int_simple_2, calc_bool_simple_2 = SimpleCalculatorKJ(
        expression='a<b ',
        **{'variables.b': calc_int},
    )

    lazyswitchkj = LazySwitchKJ(switch=calc_bool_simple_2, on_true=calc_int)

    return lazyswitchkj


def prompt_enhancer(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph a8d7fd9f-52aa-447a-9766-53cb91c0ef18 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json.
    # vibecomfy source hash: sha256:c3ac2697c91666dfd93673caf11e1a81fd3692528b555ec9e1aa02ffc8d8ec4e
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, mask = LoadImage(image='17745317855d08.png')

    # Loaders
    vaeloader = VAELoader(vae_name=VIDEO_VAE_NAME)
    latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='ltxv',
        device='default',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=AUDIO_VAE_NAME)
    vaeloader_2 = VAELoader(vae_name=VAE_TAESD_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME)
    unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME_GGUF)

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1=CLIP_NAME_GGUF,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='sdxl',
    )

    intconstant = INTConstant(value=10)
    intconstant_2 = INTConstant(value=960)
    intconstant_3 = INTConstant(value=544)
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)
    manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')

    # Sampling
    ksamplerselect = KSamplerSelect(sampler_name='euler_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')

    manualsigmas_2 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '1937', model=MODEL_NAME_2)
    loadaudio = LoadAudio(audio='d1b26d5a32db420183fa17af9c699278.mp3')

    image_image, width, height, mask_image = ImageResizeKJv2(
        upscale_method='lanczos',
        keep_proportion='crop',
        device='cpu',
        width=intconstant_3,
        height=intconstant_2,
        image=image,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    # Conditioning
    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)
    solidmask = SolidMask(value=0, width=intconstant_3, height=intconstant_2)

    calc_float, calc_int, calc_bool = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.b': 24.0, 'variables.a': intconstant},
    )

    trimaudioduration = TrimAudioDuration(duration=15, audio=loadaudio)

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=image_image)

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=image_image,
    )

    melbandroformersampler = raw_call('MelBandRoFormerSampler', '1936',
        audio=trimaudioduration,
        model=melbandroformermodelloader.out(0),
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)
    width_get, height_get, batch_size = GetImageSize(image=resizeimagemasknode)
    prompt_enhancer_result = prompt_enhancer(
        clip=dualcliploader,
        image=resizeimagemasknode,
        enable=None,
        prompt="A video from a TV broadcast with a male and a female news achor. They both stay in frame all the time.\n\nThe dialog from the male and female is as follows:\n\nSpaker_1 is the woman, and Speaker_2 is the man.\n\n[speaker_1][confused]: This is awkward! I guess the prompter ran out of ideas, and put us in this odd situation.\n[speaker_2][embarrassed] : But hey,  just because we are here, in a new video, doesn't mean our voices change. \n[speaker_1][excited]: Aber ich möchte mit dir schlafen.\n[speaker_2][happy]: I still have no idea what she said! Might be for the best [laughing]\n\nThe dialog with perfect lip-sync to the audio\n\n\nThey both smile at the end.\n\n\n",
    )

    ailab_qwen3ttsvoiceclone = AILab_Qwen3TTSVoiceClone(
        target_text='So what if you just want to prompt. Text to video works fine as well. Go generate some while I enjoy my coffee. ',
        x_vector_only=True,
        voice=986337553816914,
        unload_models=116899311982882,
        seed='randomize',
        reference_audio=melbandroformersampler.out(0),
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(model=ltxvchunkfeedforward)
    cliptextencode = CLIPTextEncode(text=prompt_enhancer_result, clip=dualcliploader)
    easy_showanything = raw_call('easy showAnything', '1625', anything=prompt_enhancer_result)

    audionormalizelufs = raw_call('AudioNormalizeLUFS', '1916',
        target_lufs=-20,
        start_time=0,
        end_time=0,
        apply_to=FULL_TRACK,
        audio=ailab_qwen3ttsvoiceclone,
    )

    positive, negative = LTXVConditioning(
        frame_rate=24.0,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    model, clip = Power_Lora_Loader_rgthree(model=ltx2attentiontunerpatch)

    audioenhancementnode = raw_call('AudioEnhancementNode', '1904',
        enhancement_mode='manual',
        enhancement_strength=0.7,
        harmonic_intensity=0.6,
        stereo_width=1.3,
        dynamic_enhancement=1.2,
        bass_boost=1,
        presence_boost=1,
        warmth=0.5,
        target_sample_rate='keep_original',
        enable_noise_reduction=False,
        noise_reduction_level=5,
        start_time=0,
        end_time=0,
        apply_to=FULL_TRACK,
        audio=audionormalizelufs.out(0),
    )

    ltx2samplingpreviewoverride = raw_call('LTX2SamplingPreviewOverride', '1858', model=model, vae=vaeloader_2)

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=audioenhancementnode.out(0),
        audio_vae=ltxvaudiovaeloader,
    )

    calculate_frames_result = calculate_frames(audio=audioenhancementnode.out(0))
    previewaudio = PreviewAudio(audio=audioenhancementnode.out(0))

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width_get,
        height=height_get,
        length=calculate_frames_result,
    )

    ltx2_nag = LTX2_NAG(
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    modelsamplingsd3 = ModelSamplingSD3(shift=13, model=ltx2_nag)
    modelsamplingsd3_2 = ModelSamplingSD3(shift=13, model=ltx2_nag)

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        strength=0.7,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplace_2,
    )

    basicscheduler = BasicScheduler(
        scheduler=LINEAR_QUADRATIC,
        steps=8,
        model=modelsamplingsd3,
    )

    basicscheduler_2 = BasicScheduler(
        scheduler=LINEAR_QUADRATIC,
        steps=4,
        model=modelsamplingsd3_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output_sampler)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        image=image_image,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplace,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(av_latent=output)

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        temporal_size=4096,
        samples=video_latent_ltxv,
        vae=vaeloader,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv,
    )

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        unload_all_models=True,
        image_pass=vaedecodetiled,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-2_01250-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_01250.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-2_01250-audio.mp4'}},
        audio=ltxvaudiovaedecode,
        images=image_pass,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

