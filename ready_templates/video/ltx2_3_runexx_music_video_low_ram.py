# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEEncode, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, LazySwitchKJ, LoadVideosFromFolder, PathchSageAttentionKJ, SimpleCalculatorKJ, VAELoaderKJ, VRAM_Debug
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
DEFAULT_SEED_3 = 1030
DEFAULT_SEED_4 = 1021
DEFAULT_SEED_5 = 1040
DEFAULT_SEED_6 = 1050
DELIMITER = '\\'
FORMAT = 'video/h264-mp4'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 1
MODEL_NAME = 'vae_approx\\taeltx2_3.safetensors'
MODEL_NAME_10 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
MODEL_NAME_11 = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
MODEL_NAME_2 = 'LTXVideo\\v2\\ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
MODEL_NAME_3 = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME_4 = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_5 = 'LTX23_audio_vae_bf16_KJ.safetensors'
MODEL_NAME_6 = 'LTX23_video_vae_bf16_KJ.safetensors'
MODEL_NAME_7 = 'gemma_3_12B_it_fp8_scaled.safetensors'
MODEL_NAME_8 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_9 = 'gemma-3-12b-it-Q2_K.gguf'
PIX_FMT = 'yuv420p'
SCHEDULER = 'linear_quadratic'
STRING_A = 'MusicVideo'
STRING_B = 'mynewvideo'
STRING_B_2 = ''
UNUSED_WIDGET_1 = 'image'


PUBLIC_INPUT_METADATA = {
    'image_strength': InputSpec(node='2183', field='strength', default=0.7),
    'window_sec_02': InputSpec(node='2329', field='_2', default=10.0),
    'enhance_prompt': InputSpec(node='2109', field='_un3705', default=False),
    'window_sec_03': InputSpec(node='5073', field='_2', default=18.0),
    'window_sec_04': InputSpec(node='5148', field='_2', default=15.0),
    'window_sec_05': InputSpec(node='5223', field='_2', default=10.0),
    'image': InputSpec(node='444', field='image', default='download (8).png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='2169', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node='1626', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}


def PUBLIC_INPUTS(**nodes):
    ltxvimgtovideoinplace = nodes['ltxvimgtovideoinplace']
    int_2 = nodes['int_2']
    prompt_enhancer_3bd4eeb9 = nodes['prompt_enhancer_3bd4eeb9']
    int = nodes['int']
    int_3 = nodes['int_3']
    int_4 = nodes['int_4']
    image = nodes['image']
    randomnoise = nodes['randomnoise']
    cliptextencode_2 = nodes['cliptextencode_2']
    return {
    'image_strength': InputSpec(node=ltxvimgtovideoinplace, field='strength', default=0.7),
    'window_sec_02': InputSpec(node=int_2, field='_2', default=10.0),
    'enhance_prompt': InputSpec(node=prompt_enhancer_3bd4eeb9, field='_un3705', default=False),
    'window_sec_03': InputSpec(node=int, field='_2', default=18.0),
    'window_sec_04': InputSpec(node=int_3, field='_2', default=15.0),
    'window_sec_05': InputSpec(node=int_4, field='_2', default=10.0),
    'image': InputSpec(node=image, field='image', default='download (8).png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node=cliptextencode_2, field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
    }

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo\\v2\\ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx\\taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Label (rgthree)', 'Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json', 'source_id': 'LTX-2.3_Music_Video_Creator_Low_RAM', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json', 'source_hash': 'sha256:9d41659daf6e14cacc66b5470599fcd146dcf969ebe30f3a4dabdd6c36574319', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_music_video_low_ram'},
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

    Materialized from subgraph 3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:d478bb1051f8c0ab301b1c97e1f0818e71241243b96c04f17495d1168c261689
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        on_false=prompt,
        on_true=textgenerateltx2prompt,
        switch=enable,
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

    Materialized from subgraph 2413a8aa-1f77-466f-8508-ed07fa6ac302 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:cef15596b6ccd25071529b637f855fd15628fc5963bf43fe332fd3d3ec2d0f9d
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        on_false=prompt,
        on_true=textgenerateltx2prompt,
        switch=enable,
    )

    return lazyswitchkj


def generate_video_c4106aee(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph c4106aee-ad7a-4925-972b-6f5b3d34db6e in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:015dcf2244fb63b0f6dc70443cc384dbdd8bf9961b82966703e49ac4a56c477f
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SamplerCustomAdvancedx2, easy showAnything, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 2413a8aa-1f77-466f-8508-ed07fa6ac302, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2.
    """

    float, int = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': ['1586', 0]},
    )

    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    solidmask = SolidMask(value=0)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')

    float_simple, int_simple, boolean = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': ['1586', 0]},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        audio=['1616', 0],
        duration=window_seconds,
        start_index=float,
    )

    easy_showanything = raw_call('easy showAnything', '2256',
        _outputs=('output',),
        widget_0='10.92',
        anything=float,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    prompt_enhancer = prompt_enhancer(
        clip=['1562', 0],
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=['1631', 0],
        height=['1631', 1],
        length=int_simple,
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        audio=['1598', 0],
        duration=window_seconds,
        start_index=float,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=['1567', 0],
    )

    positive = CLIPTextEncode(text=prompt_enhancer, clip=['1562', 0])

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=['1559', 0],
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': ['1722', 0]},
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=['2178', 0],
        negative=['164', 1],
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=['2178', 0],
        negative=['164', 1],
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=['2180', 0],
        sigmas=['2187', 0],
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent_ltxv,
        upscale_model=['1561', 0],
        vae=['1559', 0],
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=['1559', 0],
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': ['1722', 0]},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=['2174', 0],
        sigmas=['2176', 0],
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output_sampler)
    vaedecode = VAEDecode(samples=video_latent, vae=['1559', 0])

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float_simple_2, int_simple_2, boolean_simple = SimpleCalculatorKJ(
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return int_simple_2, vaedecode, trimaudioduration_2


def total_duration():
    """Total duration.

    Materialized from subgraph 5e410bb1-405a-4d3d-808b-8f5f29426943 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:bba7be5fb14ab0c81d77583bcc6a8e3e8ee0f9c335fbcbb62620263e23c4e25c
    Inner nodes: SimpleCalculatorKJ.
    """

    float, int, boolean = SimpleCalculatorKJ(
        expression='a + b + c + d + e + 2\n',
        **{'variables.a': ['2012', 0], 'variables.b': ['1997', 0], 'variables.c': ['5071', 0], 'variables.d': ['5146', 0], 'variables.e': ['5221', 0]},
    )

    return float


def prompt_enhancer_97b9884d(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 97b9884d-4a32-4b0d-ad19-be662c1c2002 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:b3909ba11d1fdc09911298176ccdab18305f619aca7dfdc2054ebd250b3303ea
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        on_false=prompt,
        on_true=textgenerateltx2prompt,
        switch=enable,
    )

    return lazyswitchkj


def generate_video(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 17238add-9973-482f-8fa3-248d4ed29886 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:2d08f203d2d9d59f59b1a148803c057a3c55035e688df5a0263422cb759aa897
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, easy showAnything, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 97b9884d-4a32-4b0d-ad19-be662c1c2002, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    solidmask = SolidMask(value=0)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': ['1586', 0]},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': ['1586', 0]},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    easy_showanything = raw_call('easy showAnything', '5031',
        _outputs=('output',),
        widget_0='20.88',
        anything=float_comfy,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=['1631', 0],
        height=['1631', 1],
        length=int_simple,
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        audio=['1616', 0],
        duration=window_seconds,
        start_index=float_comfy,
    )

    prompt_enhancer_97b9884d = prompt_enhancer_97b9884d(
        clip=['1562', 0],
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        audio=['1598', 0],
        duration=window_seconds,
        start_index=float_comfy,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    positive = CLIPTextEncode(text=prompt_enhancer_97b9884d, clip=['1562', 0])

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=['1567', 0],
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=['1559', 0],
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': ['1722', 0]},
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=['2178', 0],
        negative=['164', 1],
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=['2178', 0],
        negative=['164', 1],
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=['2180', 0],
        sigmas=['2187', 0],
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=['1561', 0],
        vae=['1559', 0],
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=['1559', 0],
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': ['1722', 0]},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=['2174', 0],
        sigmas=['2176', 0],
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(samples=video_latent_ltxv, vae=['1559', 0])

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float, int, boolean = SimpleCalculatorKJ(
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return int, vaedecode, trimaudioduration_2


def prompt_enhancer_cc5ea718(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph cc5ea718-db6a-47c7-83cf-7d9a8442ba99 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:70c4dcd27544b05f84493cd6e0a0c1eba49969737a6ce12255796d434ad40a84
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        on_false=prompt,
        on_true=textgenerateltx2prompt,
        switch=enable,
    )

    return lazyswitchkj


def generate_video_a3fb563d(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph a3fb563d-4711-4225-9210-fbe61b1bd79d in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:ee84f6cc09c042c90be076f5912a97e44fbf86cb98a3ecdb54533ce234fb85dd
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, easy showAnything, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, cc5ea718-db6a-47c7-83cf-7d9a8442ba99, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    solidmask = SolidMask(value=0)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': ['1586', 0]},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': ['1586', 0]},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    easy_showanything = raw_call('easy showAnything', '5106',
        _outputs=('output',),
        widget_0='38.84',
        anything=float_comfy,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=['1631', 0],
        height=['1631', 1],
        length=int_simple,
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        audio=['1616', 0],
        duration=window_seconds,
        start_index=float_comfy,
    )

    prompt_enhancer_cc5ea718 = prompt_enhancer_cc5ea718(
        clip=['1562', 0],
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        audio=['1598', 0],
        duration=window_seconds,
        start_index=float_comfy,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    positive = CLIPTextEncode(text=prompt_enhancer_cc5ea718, clip=['1562', 0])

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=['1567', 0],
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=['1559', 0],
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': ['1722', 0]},
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=['2178', 0],
        negative=['164', 1],
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=['2178', 0],
        negative=['164', 1],
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=['2180', 0],
        sigmas=['2187', 0],
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=['1561', 0],
        vae=['1559', 0],
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=['1559', 0],
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': ['1722', 0]},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=['2174', 0],
        sigmas=['2176', 0],
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(samples=video_latent_ltxv, vae=['1559', 0])

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float, int, boolean = SimpleCalculatorKJ(
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return int, vaedecode, trimaudioduration_2


def prompt_enhancer_50a3ed96(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 50a3ed96-aa61-4734-97cb-28cb47d171be in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:65b9dd2af249e55faece66a5caacea65832b544d0930f2956aa42896db0baa53
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        on_false=prompt,
        on_true=textgenerateltx2prompt,
        switch=enable,
    )

    return lazyswitchkj


def generate_video_4acc9924(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 4acc9924-c0bd-470a-b000-46c75e61d004 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:edd2e1bddf0592e59d8f10dd6961a54323e42e84767bf6c8c0d63679c3ea740d
    Inner nodes: SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, easy showAnything, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 50a3ed96-aa61-4734-97cb-28cb47d171be, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    solidmask = SolidMask(value=0)
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': frames_count, 'values.b': ['1586', 0]},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': window_seconds, 'variables.b': ['1586', 0]},
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    easy_showanything = raw_call('easy showAnything', '5181',
        _outputs=('output',),
        widget_0='53.92',
        anything=float_comfy,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=['1631', 0],
        height=['1631', 1],
        length=int_simple,
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        audio=['1616', 0],
        duration=window_seconds,
        start_index=float_comfy,
    )

    prompt_enhancer_50a3ed96 = prompt_enhancer_50a3ed96(
        clip=['1562', 0],
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        audio=['1598', 0],
        duration=window_seconds,
        start_index=float_comfy,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    positive = CLIPTextEncode(text=prompt_enhancer_50a3ed96, clip=['1562', 0])

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=['1567', 0],
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=['1559', 0],
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': ['1722', 0]},
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=['2178', 0],
        negative=['164', 1],
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=['2178', 0],
        negative=['164', 1],
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=['2180', 0],
        sigmas=['2187', 0],
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=['1561', 0],
        vae=['1559', 0],
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=['1559', 0],
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': ['1722', 0]},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=['2174', 0],
        sigmas=['2176', 0],
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(samples=video_latent_ltxv, vae=['1559', 0])

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float, int, boolean = SimpleCalculatorKJ(
        **{'variables.a': frames_count, 'variables.b': count},
    )

    return int, vaedecode, trimaudioduration_2

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        image, mask = LoadImage(
            image='download (8).png',
            unused_widget_1=UNUSED_WIDGET_1,
        )

        intconstant = INTConstant(value=1000)

        # Loaders
        vaeloader = VAELoader(vae_name=MODEL_NAME_6)
        latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME_11)

        dualcliploader = DualCLIPLoader(
            clip_name1=MODEL_NAME_7,
            clip_name2=MODEL_NAME_8,
            type_='ltxv',
            device='default',
        )

        vaeloaderkj = VAELoaderKJ(
            vae_name=MODEL_NAME_5,
            device='main_device',
            weight_dtype='bf16',
        )

        vaeloader_2 = VAELoader(vae_name=MODEL_NAME)
        unetloader = UNETLoader(unet_name=MODEL_NAME_2)
        unetloadergguf = UnetLoaderGGUF(unet_name=MODEL_NAME_10)

        dualcliploadergguf = DualCLIPLoaderGGUF(
            clip_name1=MODEL_NAME_9,
            clip_name2=MODEL_NAME_8,
            type_='sdxl',
        )

        intconstant_2 = INTConstant(value=480)
        loadaudio = LoadAudio(audio='ComfyUI_00152_.mp3', widget_1=None, widget_2=None)
        melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '1600', widget_0=MODEL_NAME_4)
        intconstant_3 = INTConstant(value=832)

        float, int, boolean = SimpleCalculatorKJ(
            expression='((round((a * b -1) / 8)) * 8) + 1 ',
            **{'variables.a': 11.0, 'variables.b': 25.0},
        )

        label__rgthree_ = raw_call('Label (rgthree)', '1953')
        label__rgthree__2 = raw_call('Label (rgthree)', '1954')

        randomnoise = RandomNoise(
            noise_seed=DEFAULT_SEED,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        # Sampling
        ksamplerselect = KSamplerSelect(sampler_name='euler_cfg_pp')
        manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')

        randomnoise_2 = RandomNoise(
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        ksamplerselect_2 = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')

        manualsigmas_2 = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        label__rgthree__3 = raw_call('Label (rgthree)', '2394')
        label__rgthree__4 = raw_call('Label (rgthree)', '3793')
        label__rgthree__5 = raw_call('Label (rgthree)', '3873')
        total_duration = total_duration()

        stringconcatenate = StringConcatenate(
            delimiter='\\',
            string_a='MusicVideo',
            string_b=STRING_B,
            widget_1='',
        )

        stringconcatenate_3 = StringConcatenate(
            delimiter='\\',
            string_a='output\\MusicVideo',
            string_b=STRING_B,
            widget_1='',
        )

        image_load, mask_load = LoadImage(
            image='download (1).png',
            unused_widget_1=UNUSED_WIDGET_1,
        )

        image_load_2, mask_load_2 = LoadImage(
            image='download (6).png',
            unused_widget_1=UNUSED_WIDGET_1,
        )

        image_load_3, mask_load_3 = LoadImage(
            image='download (2).png',
            unused_widget_1=UNUSED_WIDGET_1,
        )

        image_load_4, mask_load_4 = LoadImage(
            image='download (12).png',
            unused_widget_1=UNUSED_WIDGET_1,
        )

        image_image, width, height, mask_image = ImageResizeKJv2(
            upscale_method='lanczos',
            keep_proportion='crop',
            device='cpu',
            width=intconstant_3,
            height=intconstant_2,
            image=image,
        )

        loraloadermodelonly = LoraLoaderModelOnly(
            lora_name=MODEL_NAME_3,
            strength_model=GUIDE_STRENGTH,
            model=unetloader,
        )

        easy_showanything = raw_call('easy showAnything', '1596', widget_0='66.0', anything=total_duration)

        trimaudioduration = TrimAudioDuration(
            widget_0=11,
            widget_1=40,
            audio=loadaudio,
            duration=total_duration,
        )

        solidmask = SolidMask(
            value=0,
            widget_1=512,
            widget_2=512,
            height=intconstant_2,
            width=intconstant_3,
        )

        # Conditioning
        cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

        stringconcatenate_2 = StringConcatenate(
            delimiter='\\',
            string_b='MusicVideo',
            widget_0='MusicVideo',
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
            unused_widget_1=0.5,
            input=image_image,
        )

        resizeimagesbylongeredge = ResizeImagesByLongerEdge(
            longer_edge=1536,
            images=image_image,
        )

        easy_showanything_3 = raw_call('easy showAnything', '4744',
            widget_0='MusicVideo\\mynewvideo\\MusicVideo',
            anything=stringconcatenate_2,
        )

        ltxvpreprocess = LTXVPreprocess(
            img_compression=18,
            image=resizeimagesbylongeredge,
        )

        ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

        comfyswitchnode = ComfySwitchNode(
            switch=True,
            on_false=trimaudioduration,
            on_true=melbandroformersampler.out(0),
        )

        width_get, height_get, batch_size = GetImageSize(image=resizeimagemasknode)
        prompt_enhancer_3bd4eeb9 = prompt_enhancer_3bd4eeb9(
            clip=dualcliploader,
            image=resizeimagesbylongeredge,
            enable=None,
            prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=width_get,
            height=height_get,
            length=int,
        )

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(model=ltxvchunkfeedforward)

        cliptextencode = CLIPTextEncode(
            text=prompt_enhancer_3bd4eeb9,
            clip=dualcliploader,
        )

        trimaudioduration_2 = TrimAudioDuration(
            duration=11.0,
            widget_0=0,
            widget_1=40,
            audio=comfyswitchnode,
        )

        easy_showanything_2 = raw_call('easy showAnything', '2112',
            widget_0='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
            anything=prompt_enhancer_3bd4eeb9,
        )

        positive, negative = LTXVConditioning(
            negative=cliptextencode_2,
            positive=cliptextencode,
        )

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            audio=trimaudioduration_2,
            audio_vae=vaeloaderkj,
        )

        power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '2150',
            unused_widget_0={},
            unused_widget_1={'type': 'PowerLoraLoaderHeaderWidget'},
            unused_widget_2={'on': False, 'lora': 'LTX\\LTX-2\\ID-Lora\\LTX-2.3-22b-AV-LoRA-talking-head-v1.safetensors', 'strength': 0.5, 'strengthTwo': None},
            unused_widget_3={'on': False, 'lora': 'LTX\\LTX-2\\Ltx2.3-Licon-VBVR-I2V-96000-R32.safetensors', 'strength': 1, 'strengthTwo': None},
            widget_4={'on': False, 'lora': 'LTX\\LTX-2\\LTX-2-Image2Vid-Adapter.safetensors', 'strength': 0.3, 'strengthTwo': None},
            widget_5={'on': False, 'lora': 'LTX\\v2\\ltx-2-19b-lora-camera-control-dolly-out.safetensors', 'strength': 0.3, 'strengthTwo': None},
            widget_6={},
            widget_7='',
            model=ltx2attentiontunerpatch,
        )

        ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
            widget_0=1,
            widget_1=False,
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=vaeloader,
        )

        setlatentnoisemask = SetLatentNoiseMask(
            mask=solidmask,
            samples=ltxvaudiovaeencode,
        )

        ltx2samplingpreviewoverride = raw_call('LTX2SamplingPreviewOverride', '2188',
            model=power_lora_loader__rgthree_.out(0),
            vae=vaeloader_2,
        )

        ltxvconcatavlatent = LTXVConcatAVLatent(
            audio_latent=setlatentnoisemask,
            video_latent=ltxvimgtovideoinplace_2,
        )

        ltx2_nag = LTX2_NAG(
            unused_widget_3=True,
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
            scheduler=SCHEDULER,
            steps=4,
            model=modelsamplingsd3,
        )

        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
        )

        basicscheduler_2 = BasicScheduler(
            scheduler=SCHEDULER,
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
            widget_0=1,
            widget_1=False,
            image=resizeimagesbylongeredge,
            latent=ltxvlatentupsampler,
            vae=vaeloader,
        )

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            audio_latent=audio_latent_ltxv,
            video_latent=ltxvimgtovideoinplace,
        )

        output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
        )

        video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output_sampler)

        # Decode
        vaedecode = VAEDecode(samples=video_latent, vae=vaeloader)

        image_get, width_get_2, height_get_2, count = GetImageSizeAndCount(
            image=vaedecode,
        )

        any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
            image_pass=vaedecode,
        )

        # Outputs
        vhs_videocombine_3 = VHS_VideoCombine(
            frame_rate=25.0,
            format=FORMAT,
            crf=19,
            pix_fmt=PIX_FMT,
            save_metadata=True,
            trim_to_audio=False,
            videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00004-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00004.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00004-audio.mp4'}},
            filename_prefix=stringconcatenate_2,
            audio=trimaudioduration,
            images=vaedecode,
        )

        image_get_2, width_get_3, height_get_3, count_get = GetImageSizeAndCount(
            image=image_pass,
        )

        int_2, output_1_2, audio_2 = generate_video_c4106aee(
            noise_seed=1021,
            prompt='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a romantic greenhouse with flowers and warm light, tracking camera as she walks towards the viewer.\n\nShe sings the lyrics: "I type a whisper, watch it bloom. In pixel fog and quiet rooms. A hundred frames begin to breathe. While melodies I couldn’t weave" \n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
            window_seconds=10.0,
            frames_count=count_get,
            ref_image=image_load,
        )

        vhs_videocombine = VHS_VideoCombine(
            frame_rate=25.0,
            format=FORMAT,
            crf=19,
            pix_fmt=PIX_FMT,
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
        )

        vhs_videocombine_4 = VHS_VideoCombine(
            frame_rate=25.0,
            format=FORMAT,
            crf=19,
            pix_fmt=PIX_FMT,
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
        )

        vhs_videocombine_5 = VHS_VideoCombine(
            frame_rate=25.0,
            format=FORMAT,
            crf=19,
            pix_fmt=PIX_FMT,
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
        )

        vhs_videocombine_6 = VHS_VideoCombine(
            frame_rate=25.0,
            format=FORMAT,
            crf=19,
            pix_fmt=PIX_FMT,
            save_metadata=True,
            trim_to_audio=False,
            videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'MusicVideo_00005-audio.mp4', 'subfolder': 'MusicVideo\\mynewvideo', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'MusicVideo_00005.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\MusicVideo\\mynewvideo\\MusicVideo_00005-audio.mp4'}},
            filename_prefix=stringconcatenate_2,
            audio=audio_4,
            images=output_1_4,
        )

        float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
            expression='a + 100',
            **{'variables.a': int_4},
        )

        loadvideosfromfolder = LoadVideosFromFolder(
            widget_0='output\\MusicVideo',
            widget_4=0,
            frame_load_cap=int_simple,
            video=stringconcatenate_3,
        )

        vhs_videocombine_2 = VHS_VideoCombine(
            frame_rate=25.0,
            filename_prefix='LTX-MusicVideo-Final',
            format=FORMAT,
            crf=19,
            pix_fmt=PIX_FMT,
            save_metadata=True,
            trim_to_audio=False,
            videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-MusicVideo-Final_00003-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'LTX-MusicVideo-Final_00003.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-MusicVideo-Final_00003-audio.mp4'}},
            audio=trimaudioduration,
            images=loadvideosfromfolder,
        )

        return wf.finalize(PUBLIC_INPUTS(**locals()), output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

