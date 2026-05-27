# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEEncode, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, LazySwitchKJ, LoadVideosFromFolder, PathchSageAttentionKJ, SimpleCalculatorKJ, VAELoaderKJ, VRAM_Debug
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_NAME_GGUF = 'gemma-3-12b-it-Q2_K.gguf'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
DEFAULT_SEED_3 = 1030
DEFAULT_SEED_4 = 1021
DEFAULT_SEED_5 = 1040
DEFAULT_SEED_6 = 1050
FIXED = 'fixed'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 1
LINEAR_QUADRATIC = 'linear_quadratic'
LORA_NAME = 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors'
MEL_BAND_ROFORMER_NAME = 'MelBandRoformer/MelBandRoformer_fp16.safetensors'
MYNEWVIDEO = 'mynewvideo'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
UNET_NAME_GGUF = 'LTXvideo/LTX-2/quantstack/LTX-2.3-distilled-Q4_K_S.gguf'
VAE_TAESD_NAME = 'vae_approx/taeltx2_3.safetensors'
VALUE = '\\'
VIDEO_H264_MP4 = 'video/h264-mp4'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'image_strength': InputSpec(node='2183', field='strength', default=0.7),
    'window_sec_02': InputSpec(node='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2324', field='variables.a', default=10.0),
    'enhance_prompt': InputSpec(node='3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf:1928', field='switch', default=False),
    'window_sec_03': InputSpec(node='17238add-9973-482f-8fa3-248d4ed29886:5041', field='variables.a', default=18.0),
    'window_sec_04': InputSpec(node='a3fb563d-4711-4225-9210-fbe61b1bd79d:5116', field='variables.a', default=15.0),
    'window_sec_05': InputSpec(node='4acc9924-c0bd-470a-b000-46c75e61d004:5191', field='variables.a', default=10.0),
    'image': InputSpec(node='444', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='2169', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node='1626', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo/v2/ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'LTX/LTX-2/ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo/LTX-2/quantstack/LTX-2.3-distilled-Q4_K_S.gguf', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx/taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json', 'source_id': 'LTX-2.3_Music_Video_Creator_Low_RAM', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_music_video_low_ram'},
)

# === Subgraph functions ===

def prompt_enhancer_3bd4eeb9(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:2d0dc3ed6d0c2a03de0305f15253f33dd30611c205abd2e7e3c0c63e010bf8b3
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(
        _id='3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf:1618',
        string_a='',
        string_b=prompt,
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        _id='3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf:1623',
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        _id='3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf:1928',
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def prompt_enhancer(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 2413a8aa-1f77-466f-8508-ed07fa6ac302 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:19a6af25c0629d69f9a8f32abaaca0da5690f4b1d5f343983d6aaa3665559463
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(
        _id='2413a8aa-1f77-466f-8508-ed07fa6ac302:2120',
        string_a='',
        string_b=prompt,
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        _id='2413a8aa-1f77-466f-8508-ed07fa6ac302:2117',
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        _id='2413a8aa-1f77-466f-8508-ed07fa6ac302:2119',
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def generate_video_c4106aee(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
    upscale_model,
    vae,
    clip,
    audio_vae,
    model,
    negative,
    sampler,
    sigmas,
    values_b,
    variables_b,
    width,
    height,
    audio,
    vae_2,
    clip_2,
    un3912,
    audio_2,
    vae_3,
    num_images_strength_1,
    vae_4,
    num_images_strength_1_2,
    model_2,
    negative_2,
    sampler_2,
    sigmas_2,
):
    """Generate Video - single-image variant.

    Materialized from subgraph c4106aee-ad7a-4925-972b-6f5b3d34db6e in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:cbf37f5017a5530871597dcd4b5d008c9ea29dde34de0757fec85749b6b65546
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SamplerCustomAdvancedx2, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 2413a8aa-1f77-466f-8508-ed07fa6ac302, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2.
    """

    comfy_float, _ = ComfyMathExpression(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2210',
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': values_b},
    )

    randomnoise = RandomNoise(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2244',
        control_after_generate='fixed',
        noise_seed=noise_seed,
    )

    solidmask = SolidMask(_id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2289', value=0)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2292',
        longer_edge=1536,
        images=ref_image,
    )

    randomnoise_2 = RandomNoise(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2299',
        noise_seed=405,
        control_after_generate='fixed',
    )

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2324',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': variables_b},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2327',
        resize_type='scale by multiplier',
        input=ref_image,
    )

    trimaudioduration = TrimAudioDuration(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2223',
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio,
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2265',
        img_compression=18,
        image=resizeimagesbylongeredge,
    )

    prompt_enhancer_result = prompt_enhancer(
        clip=['-10', 19],
        image=resizeimagemasknode,
        enable=['-10', 20],
        prompt=['-10', 1],
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2322',
        width=width,
        height=height,
        length=calc_int,
    )

    trimaudioduration_2 = TrimAudioDuration(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:4747',
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio_2,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2224',
        audio=trimaudioduration,
        audio_vae=audio_vae,
    )

    positive = CLIPTextEncode(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2278',
        text=prompt_enhancer_result,
        clip=clip,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:4998',
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=emptyltxvlatentvideo,
        vae=vae_3,
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': num_images_strength_1},
    )

    cfgguider = CFGGuider(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2227',
        cfg=1,
        model=model,
        negative=negative,
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2287',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )

    cfgguider_2 = CFGGuider(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2307',
        cfg=1,
        model=model_2,
        negative=negative_2,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2205',
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, _ = SamplerCustomAdvanced(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2249',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=sampler_2,
        sigmas=sigmas_2,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2298',
        av_latent=output,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2297',
        samples=video_latent_ltxv,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:4999',
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vae_4,
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': num_images_strength_1_2},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2296',
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, _ = SamplerCustomAdvanced(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2312',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=sampler,
        sigmas=sigmas,
    )

    video_latent, _ = LTXVSeparateAVLatent(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2239',
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2241',
        samples=video_latent,
        vae=vae_2,
    )

    _, image_pass, _, _, _ = VRAM_Debug(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:2108',
        image_pass=vaedecode,
    )

    _, _, _, count = GetImageSizeAndCount(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:4202',
        image=image_pass,
    )

    _, calc_int_simple, _ = SimpleCalculatorKJ(
        _id='c4106aee-ad7a-4925-972b-6f5b3d34db6e:4201',
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return calc_int_simple, vaedecode, trimaudioduration_2


def total_duration(
    *,
    variables_a,
    variables_b,
    variables_c,
    variables_d,
    variables_e,
):
    """Total duration.

    Materialized from subgraph 5e410bb1-405a-4d3d-808b-8f5f29426943 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:499d1097b28fe35bbf263370c1665c25ad008f551cb2fc33f04b8e0c5df2c383
    Inner nodes: SimpleCalculatorKJ.
    """

    calc_float, _, _ = SimpleCalculatorKJ(
        _id='5e410bb1-405a-4d3d-808b-8f5f29426943:3721',
        expression='a + b + c + d + e + 2\n',
        **{'variables.a': variables_a, 'variables.b': variables_b, 'variables.c': variables_c, 'variables.d': variables_d, 'variables.e': variables_e},
    )

    return calc_float


def prompt_enhancer_97b9884d(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 97b9884d-4a32-4b0d-ad19-be662c1c2002 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:36dbf4b3119343559cc3c2b629aed447d88526100f83b417258078b290ff28aa
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(
        _id='97b9884d-4a32-4b0d-ad19-be662c1c2002:5063',
        string_a='',
        string_b=prompt,
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        _id='97b9884d-4a32-4b0d-ad19-be662c1c2002:5058',
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        _id='97b9884d-4a32-4b0d-ad19-be662c1c2002:5059',
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def generate_video(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
    upscale_model,
    vae,
    clip,
    audio_vae,
    model,
    negative,
    values_b,
    variables_b,
    width,
    height,
    audio,
    vae_2,
    clip_2,
    un3912,
    audio_2,
    vae_3,
    num_images_strength_1,
    vae_4,
    num_images_strength_1_2,
    model_2,
    negative_2,
    sampler,
    sigmas,
    sampler_2,
    sigmas_2,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 17238add-9973-482f-8fa3-248d4ed29886 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:28643b6c64068643a90cd88b40ab7b216aa3728cbc287a2d0c67a24484f18244
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 97b9884d-4a32-4b0d-ad19-be662c1c2002, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    solidmask = SolidMask(_id='17238add-9973-482f-8fa3-248d4ed29886:5003', value=0)

    randomnoise = RandomNoise(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5026',
        control_after_generate='fixed',
        noise_seed=noise_seed,
    )

    randomnoise_2 = RandomNoise(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5027',
        noise_seed=405,
        control_after_generate='fixed',
    )

    comfy_float, _ = ComfyMathExpression(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5038',
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': values_b},
    )

    _, calc_int_simple, _ = SimpleCalculatorKJ(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5041',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': variables_b},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5047',
        resize_type='scale by multiplier',
        input=ref_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5053',
        longer_edge=1536,
        images=ref_image,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5042',
        width=width,
        height=height,
        length=calc_int_simple,
    )

    trimaudioduration = TrimAudioDuration(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5044',
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio,
    )

    prompt_enhancer_97b9884d_result = prompt_enhancer_97b9884d(
        clip=['-10', 17],
        image=resizeimagemasknode,
        enable=['-10', 18],
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5051',
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio_2,
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5052',
        img_compression=18,
        image=resizeimagesbylongeredge,
    )

    positive = CLIPTextEncode(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5012',
        text=prompt_enhancer_97b9884d_result,
        clip=clip,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5019',
        audio=trimaudioduration,
        audio_vae=audio_vae,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5054',
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=emptyltxvlatentvideo,
        vae=vae_3,
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': num_images_strength_1},
    )

    cfgguider = CFGGuider(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5023',
        cfg=1,
        model=model,
        negative=negative,
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5024',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )

    cfgguider_2 = CFGGuider(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5057',
        cfg=1,
        model=model_2,
        negative=negative_2,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5025',
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, _ = SamplerCustomAdvanced(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5029',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=sampler,
        sigmas=sigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5010',
        av_latent=output,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5011',
        samples=video_latent,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5055',
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vae_4,
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': num_images_strength_1_2},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5056',
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, _ = SamplerCustomAdvanced(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5030',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=sampler_2,
        sigmas=sigmas_2,
    )

    video_latent_ltxv, _ = LTXVSeparateAVLatent(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5028',
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5046',
        samples=video_latent_ltxv,
        vae=vae_2,
    )

    _, image_pass, _, _, _ = VRAM_Debug(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5037',
        image_pass=vaedecode,
    )

    _, _, _, count = GetImageSizeAndCount(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5036',
        image=image_pass,
    )

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='17238add-9973-482f-8fa3-248d4ed29886:5035',
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return calc_int, vaedecode, trimaudioduration_2


def prompt_enhancer_cc5ea718(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph cc5ea718-db6a-47c7-83cf-7d9a8442ba99 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:8ce010c65ed2457df2de94406016a7eee37b5fb7a7cb0a3a41246a5e9c74f342
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(
        _id='cc5ea718-db6a-47c7-83cf-7d9a8442ba99:5138',
        string_a='',
        string_b=prompt,
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        _id='cc5ea718-db6a-47c7-83cf-7d9a8442ba99:5133',
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        _id='cc5ea718-db6a-47c7-83cf-7d9a8442ba99:5134',
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def generate_video_a3fb563d(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
    upscale_model,
    vae,
    clip,
    audio_vae,
    model,
    negative,
    values_b,
    variables_b,
    width,
    height,
    audio,
    vae_2,
    clip_2,
    un3912,
    audio_2,
    vae_3,
    num_images_strength_1,
    vae_4,
    num_images_strength_1_2,
    model_2,
    negative_2,
    sampler,
    sigmas,
    sampler_2,
    sigmas_2,
):
    """Generate Video - single-image variant.

    Materialized from subgraph a3fb563d-4711-4225-9210-fbe61b1bd79d in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:238dc4a8d04df1c8b62437cb86819e13f8c09a55b0c565dbd9a2982b277aa858
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, cc5ea718-db6a-47c7-83cf-7d9a8442ba99, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    solidmask = SolidMask(_id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5078', value=0)

    randomnoise = RandomNoise(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5101',
        control_after_generate='fixed',
        noise_seed=noise_seed,
    )

    randomnoise_2 = RandomNoise(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5102',
        noise_seed=405,
        control_after_generate='fixed',
    )

    comfy_float, _ = ComfyMathExpression(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5113',
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': values_b},
    )

    _, calc_int_simple, _ = SimpleCalculatorKJ(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5116',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': variables_b},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5122',
        resize_type='scale by multiplier',
        input=ref_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5128',
        longer_edge=1536,
        images=ref_image,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5117',
        width=width,
        height=height,
        length=calc_int_simple,
    )

    trimaudioduration = TrimAudioDuration(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5119',
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio,
    )

    prompt_enhancer_cc5ea718_result = prompt_enhancer_cc5ea718(
        clip=['-10', 17],
        image=resizeimagemasknode,
        enable=['-10', 18],
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5126',
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio_2,
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5127',
        img_compression=18,
        image=resizeimagesbylongeredge,
    )

    positive = CLIPTextEncode(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5087',
        text=prompt_enhancer_cc5ea718_result,
        clip=clip,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5094',
        audio=trimaudioduration,
        audio_vae=audio_vae,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5129',
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=emptyltxvlatentvideo,
        vae=vae_3,
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': num_images_strength_1},
    )

    cfgguider = CFGGuider(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5098',
        cfg=1,
        model=model,
        negative=negative,
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5099',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )

    cfgguider_2 = CFGGuider(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5132',
        cfg=1,
        model=model_2,
        negative=negative_2,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5100',
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, _ = SamplerCustomAdvanced(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5104',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=sampler,
        sigmas=sigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5085',
        av_latent=output,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5086',
        samples=video_latent,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5130',
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vae_4,
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': num_images_strength_1_2},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5131',
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, _ = SamplerCustomAdvanced(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5105',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=sampler_2,
        sigmas=sigmas_2,
    )

    video_latent_ltxv, _ = LTXVSeparateAVLatent(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5103',
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5121',
        samples=video_latent_ltxv,
        vae=vae_2,
    )

    _, image_pass, _, _, _ = VRAM_Debug(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5112',
        image_pass=vaedecode,
    )

    _, _, _, count = GetImageSizeAndCount(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5111',
        image=image_pass,
    )

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='a3fb563d-4711-4225-9210-fbe61b1bd79d:5110',
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return calc_int, vaedecode, trimaudioduration_2


def prompt_enhancer_50a3ed96(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 50a3ed96-aa61-4734-97cb-28cb47d171be in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:106b8c1e1f848de09ddc31f53b525c819c6acea35ef8cb989b287387898d3fed
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(
        _id='50a3ed96-aa61-4734-97cb-28cb47d171be:5213',
        string_a='',
        string_b=prompt,
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        _id='50a3ed96-aa61-4734-97cb-28cb47d171be:5208',
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    lazyswitchkj = LazySwitchKJ(
        _id='50a3ed96-aa61-4734-97cb-28cb47d171be:5209',
        switch=enable,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj


def generate_video_4acc9924(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
    upscale_model,
    vae,
    clip,
    audio_vae,
    model,
    negative,
    values_b,
    variables_b,
    width,
    height,
    audio,
    vae_2,
    clip_2,
    un3912,
    audio_2,
    vae_3,
    num_images_strength_1,
    vae_4,
    num_images_strength_1_2,
    model_2,
    negative_2,
    sampler,
    sigmas,
    sampler_2,
    sigmas_2,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 4acc9924-c0bd-470a-b000-46c75e61d004 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:15e1174c0eeb3e4b46f8553675deed8c2ed2828151886bf61a1a1df15272cabf
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 50a3ed96-aa61-4734-97cb-28cb47d171be, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    solidmask = SolidMask(_id='4acc9924-c0bd-470a-b000-46c75e61d004:5153', value=0)

    randomnoise = RandomNoise(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5176',
        control_after_generate='fixed',
        noise_seed=noise_seed,
    )

    randomnoise_2 = RandomNoise(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5177',
        noise_seed=405,
        control_after_generate='fixed',
    )

    comfy_float, _ = ComfyMathExpression(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5188',
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': values_b},
    )

    _, calc_int_simple, _ = SimpleCalculatorKJ(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5191',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': variables_b},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5197',
        resize_type='scale by multiplier',
        input=ref_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5203',
        longer_edge=1536,
        images=ref_image,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5192',
        width=width,
        height=height,
        length=calc_int_simple,
    )

    trimaudioduration = TrimAudioDuration(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5194',
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio,
    )

    prompt_enhancer_50a3ed96_result = prompt_enhancer_50a3ed96(
        clip=['-10', 17],
        image=resizeimagemasknode,
        enable=['-10', 18],
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5201',
        start_index=comfy_float,
        duration=window_seconds,
        audio=audio_2,
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5202',
        img_compression=18,
        image=resizeimagesbylongeredge,
    )

    positive = CLIPTextEncode(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5162',
        text=prompt_enhancer_50a3ed96_result,
        clip=clip,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5169',
        audio=trimaudioduration,
        audio_vae=audio_vae,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5204',
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=emptyltxvlatentvideo,
        vae=vae_3,
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': num_images_strength_1},
    )

    cfgguider = CFGGuider(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5173',
        cfg=1,
        model=model,
        negative=negative,
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5174',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )

    cfgguider_2 = CFGGuider(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5207',
        cfg=1,
        model=model_2,
        negative=negative_2,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5175',
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, _ = SamplerCustomAdvanced(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5179',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=sampler,
        sigmas=sigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5160',
        av_latent=output,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5161',
        samples=video_latent,
        upscale_model=upscale_model,
        vae=vae,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5205',
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vae_4,
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': num_images_strength_1_2},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5206',
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, _ = SamplerCustomAdvanced(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5180',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=sampler_2,
        sigmas=sigmas_2,
    )

    video_latent_ltxv, _ = LTXVSeparateAVLatent(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5178',
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5196',
        samples=video_latent_ltxv,
        vae=vae_2,
    )

    _, image_pass, _, _, _ = VRAM_Debug(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5187',
        image_pass=vaedecode,
    )

    _, _, _, count = GetImageSizeAndCount(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5186',
        image=image_pass,
    )

    _, calc_int, _ = SimpleCalculatorKJ(
        _id='4acc9924-c0bd-470a-b000-46c75e61d004:5185',
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return calc_int, vaedecode, trimaudioduration_2

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(image='download (8).png')
    intconstant = INTConstant(value=1000)

    # Loaders
    vaeloader = VAELoader(vae_name=VIDEO_VAE_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name=SPATIAL_UPSCALER_NAME,
    )

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='ltxv',
        device='default',
    )

    vaeloaderkj = VAELoaderKJ(
        vae_name=AUDIO_VAE_NAME,
        device='main_device',
        weight_dtype='bf16',
    )

    vaeloader_2 = VAELoader(vae_name=VAE_TAESD_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME)
    unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME_GGUF)

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1=CLIP_NAME_GGUF,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='sdxl',
    )

    intconstant_2 = INTConstant(value=480)
    loadaudio = LoadAudio(audio='ComfyUI_00152_.mp3')
    melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '1600', model=MEL_BAND_ROFORMER_NAME)
    intconstant_3 = INTConstant(value=832)

    _, calc_int, _ = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': 11.0, 'variables.b': 25.0},
    )

    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)

    # Sampling
    ksamplerselect = KSamplerSelect(sampler_name='euler_cfg_pp')
    manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')

    manualsigmas_2 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    total_duration_result = total_duration(
        variables_a=['2012', 0],
        variables_b=['1997', 0],
        variables_c=['5071', 0],
        variables_d=['5146', 0],
        variables_e=['5221', 0],
    )

    stringconcatenate = StringConcatenate(
        string_a='MusicVideo',
        string_b=MYNEWVIDEO,
        delimiter=VALUE,
    )

    stringconcatenate_3 = StringConcatenate(
        string_a='output\\MusicVideo',
        string_b=MYNEWVIDEO,
        delimiter=VALUE,
    )

    image_load, _ = LoadImage(image='download (1).png')
    image_load_2, _ = LoadImage(image='download (6).png')
    image_load_3, _ = LoadImage(image='download (2).png')
    image_load_4, _ = LoadImage(image='download (12).png')

    image_image, _, _, _ = ImageResizeKJv2(
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

    trimaudioduration = TrimAudioDuration(
        start_index=11,
        duration=total_duration_result,
        audio=loadaudio,
    )

    solidmask = SolidMask(value=0, width=intconstant_3, height=intconstant_2)

    # Conditioning
    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

    stringconcatenate_2 = StringConcatenate(
        string_b='MusicVideo',
        delimiter=VALUE,
        string_a=stringconcatenate,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    melbandroformersampler = raw_call('MelBandRoFormerSampler', '1599',
        audio=trimaudioduration,
        model=melbandroformermodelloader.out(0),
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=image_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

    comfyswitchnode = ComfySwitchNode(
        switch=True,
        on_false=trimaudioduration,
        on_true=melbandroformersampler.out(0),
    )

    width_get, height_get, _ = GetImageSize(image=resizeimagemasknode)
    prompt_enhancer_3bd4eeb9_result = prompt_enhancer_3bd4eeb9(
        clip=dualcliploader,
        image=resizeimagesbylongeredge,
        enable=False,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width_get,
        height=height_get,
        length=calc_int,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(model=ltxvchunkfeedforward)

    cliptextencode = CLIPTextEncode(
        text=prompt_enhancer_3bd4eeb9_result,
        clip=dualcliploader,
    )

    trimaudioduration_2 = TrimAudioDuration(duration=11.0, audio=comfyswitchnode)

    positive, negative = LTXVConditioning(
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration_2,
        audio_vae=vaeloaderkj,
    )

    model, _ = Power_Lora_Loader_rgthree(
        lora_1={'on': False, 'lora': 'LTX\\LTX-2\\LTX-2-Image2Vid-Adapter.safetensors', 'strength': 0.3, 'strengthTwo': None},
        lora_2={'on': False, 'lora': 'LTX\\v2\\ltx-2-19b-lora-camera-control-dolly-out.safetensors', 'strength': 0.3, 'strengthTwo': None},
        model=ltx2attentiontunerpatch,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)
    ltx2samplingpreviewoverride = raw_call('LTX2SamplingPreviewOverride', '2188', model=model, vae=vaeloader_2)

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplace_2,
    )

    ltx2_nag = LTX2_NAG(
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=positive,
        positive=positive,
    )

    modelsamplingsd3 = ModelSamplingSD3(shift=13, model=ltx2_nag)

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    modelsamplingsd3_2 = ModelSamplingSD3(shift=13, model=ltx2_nag)

    basicscheduler = BasicScheduler(
        scheduler=LINEAR_QUADRATIC,
        steps=4,
        model=modelsamplingsd3,
    )

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    basicscheduler_2 = BasicScheduler(
        scheduler=LINEAR_QUADRATIC,
        steps=10,
        model=modelsamplingsd3_2,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent_ltxv,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        strength=0.7,
        image=resizeimagesbylongeredge,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplace,
    )

    output_sampler, _ = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, _ = LTXVSeparateAVLatent(av_latent=output_sampler)

    # Decode
    vaedecode = VAEDecode(samples=video_latent, vae=vaeloader)
    GetImageSizeAndCount(image=vaedecode)
    _, image_pass, _, _, _ = VRAM_Debug(image_pass=vaedecode)

    # Outputs
    vhs_videocombine_3 = VHS_VideoCombine(
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00004-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00004.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00004-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=trimaudioduration,
        images=vaedecode,
    )

    _, _, _, count_get = GetImageSizeAndCount(image=image_pass)
    int_2, output_1_2, audio_2 = generate_video_c4106aee(
        noise_seed=1021,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a romantic greenhouse with flowers and warm light, tracking camera as she walks towards the viewer.\n\nShe sings the lyrics: "I type a whisper, watch it bloom. In pixel fog and quiet rooms. A hundred frames begin to breathe. While melodies I couldn’t weave" \n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        window_seconds=10.0,
        frames_count=count_get,
        ref_image=image_load,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
        clip=dualcliploader,
        audio_vae=vaeloaderkj,
        model=ltx2_nag,
        negative=negative,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
        values_b=['1586', 0],
        variables_b=['1586', 0],
        width=width_get,
        height=height_get,
        audio=comfyswitchnode,
        vae_2=vaeloader,
        clip_2=dualcliploader,
        un3912=['2116', 0],
        audio_2=trimaudioduration,
        vae_3=vaeloader,
        num_images_strength_1=['1722', 0],
        vae_4=vaeloader,
        num_images_strength_1_2=['1722', 0],
        model_2=ltx2_nag,
        negative_2=negative,
        sampler_2=ksamplerselect_2,
        sigmas_2=manualsigmas_2,
    )

    vhs_videocombine = VHS_VideoCombine(
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00002-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00002.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00002-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=audio_2,
        images=output_1_2,
    )

    int, output_1, audio = generate_video(
        noise_seed=1030,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at the stage at an abandoned teather.  The camera slowly orbits around the woman, the woman is always looking at the viewer.\n\nShe sings the lyrics: "Now rise from weights, unchained and free.\nLike open doors for you and me.\nAnd every node connects the light. To hands that build without a figh.  No locked gates, just open skies.Where anyone can close their eyes…".\n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        window_seconds=18.0,
        frames_count=int_2,
        ref_image=image_load_2,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
        clip=dualcliploader,
        audio_vae=vaeloaderkj,
        model=ltx2_nag,
        negative=negative,
        values_b=['1586', 0],
        variables_b=['1586', 0],
        width=width_get,
        height=height_get,
        audio=comfyswitchnode,
        vae_2=vaeloader,
        clip_2=dualcliploader,
        un3912=['2116', 0],
        audio_2=trimaudioduration,
        vae_3=vaeloader,
        num_images_strength_1=['1722', 0],
        vae_4=vaeloader,
        num_images_strength_1_2=['1722', 0],
        model_2=ltx2_nag,
        negative_2=negative,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
        sampler_2=ksamplerselect,
        sigmas_2=manualsigmas,
    )

    vhs_videocombine_4 = VHS_VideoCombine(
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00003-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00003.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00003-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=audio,
        images=output_1,
    )

    int_3, output_1_3, audio_3 = generate_video_a3fb563d(
        noise_seed=1040,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at a piece of drift-wood at the beach, at dusk. Soft light from a cloudy sky. \n\n\nShe sings the lyrics: " … and dream. Oh, AceStep XL, you paint my dreams. ComfyUI, you stitch the seams. Of every film, each trembling tone. Where lonely sparks now feel at home".\n\nShe sings for a bit before she stands up and walks towards the viewer. \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        window_seconds=15.0,
        frames_count=int,
        ref_image=image_load_3,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
        clip=dualcliploader,
        audio_vae=vaeloaderkj,
        model=ltx2_nag,
        negative=negative,
        values_b=['1586', 0],
        variables_b=['1586', 0],
        width=width_get,
        height=height_get,
        audio=comfyswitchnode,
        vae_2=vaeloader,
        clip_2=dualcliploader,
        un3912=['2116', 0],
        audio_2=trimaudioduration,
        vae_3=vaeloader,
        num_images_strength_1=['1722', 0],
        vae_4=vaeloader,
        num_images_strength_1_2=['1722', 0],
        model_2=ltx2_nag,
        negative_2=negative,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
        sampler_2=ksamplerselect,
        sigmas_2=manualsigmas,
    )

    vhs_videocombine_5 = VHS_VideoCombine(
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00004-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00004.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00004-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=audio_3,
        images=output_1_3,
    )

    int_4, output_1_4, audio_4 = generate_video_4acc9924(
        noise_seed=1050,
        prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is standing on a rooftop balcony with the city behind her, at night. Camera slowly orbits around her, with her always looking towards the viewer as she sings. \n\nShe sings the lyrics: "Thank you, Kijai, for the quiet grace. That smoothed the path through digital space. We dream in code, we dream in blue. And every open door leads through.......". \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        window_seconds=10.0,
        frames_count=int_3,
        ref_image=image_load_4,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
        clip=dualcliploader,
        audio_vae=vaeloaderkj,
        model=ltx2_nag,
        negative=negative,
        values_b=['1586', 0],
        variables_b=['1586', 0],
        width=width_get,
        height=height_get,
        audio=comfyswitchnode,
        vae_2=vaeloader,
        clip_2=dualcliploader,
        un3912=['2116', 0],
        audio_2=trimaudioduration,
        vae_3=vaeloader,
        num_images_strength_1=['1722', 0],
        vae_4=vaeloader,
        num_images_strength_1_2=['1722', 0],
        model_2=ltx2_nag,
        negative_2=negative,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
        sampler_2=ksamplerselect,
        sigmas_2=manualsigmas,
    )

    vhs_videocombine_6 = VHS_VideoCombine(
        frame_rate=25.0,
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00005-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00005.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00005-audio.mp4'}},
        filename_prefix=stringconcatenate_2,
        audio=audio_4,
        images=output_1_4,
    )

    _, calc_int_simple, _ = SimpleCalculatorKJ(
        expression='a + 100',
        **{'variables.a': int_4},
    )

    loadvideosfromfolder = LoadVideosFromFolder(
        video=stringconcatenate_3,
        frame_load_cap=calc_int_simple,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        frame_rate=25.0,
        filename_prefix='LTX-MusicVideo-Final',
        format=VIDEO_H264_MP4,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-MusicVideo-Final_00003-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'LTX-MusicVideo-Final_00003.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-MusicVideo-Final_00003-audio.mp4'}},
        audio=trimaudioduration,
        images=loadvideosfromfolder,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

