# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import AudioConcat, BasicScheduler, CFGGuider, CLIPTextEncode, DualCLIPLoader, GetImageRangeFromBatch, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PreviewAny, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAEDecodeTiled, VAEEncode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageBatchExtendWithOverlap, ImageBatchMulti, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2MemoryEfficientSageAttentionPatch, LTX2_NAG, LTXVAudioVideoMask, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VAELoaderKJ
from vibecomfy.nodes.ltxvideo import LTXVAddLatentGuide
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine, VHS_VideoInfo
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness


CLIP_NAME = 'gemma-3-12b-it-Q2_K.gguf'
CLIP_NAME_2 = 'ltx-2.3_text_projection_bf16.safetensors'
CLIP_NAME_3 = 'gemma_3_12B_it_fp8_scaled.safetensors'
DEFAULT_FRAMES = 1
DEFAULT_FRAMES_2 = 4096
DEFAULT_PROMPT = ' distorted sound, saturated sound, loud sound'
DEFAULT_PROMPT_2 = 'text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 432
DEFAULT_SEED_2 = 42
FIXED = 'fixed'
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.6
LORA_NAME = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
ROUND_A_B_1_8_8_1 = '((round((a * b -1) / 8)) * 8) + 1 '
UNET_NAME = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
UNET_NAME_2 = 'LTXVideo\\v2\\ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
VAE_NAME = 'vae_approx\\taeltx2_3.safetensors'
VAE_NAME_2 = 'LTX23_audio_vae_bf16_KJ.safetensors'
VAE_NAME_3 = 'LTX23_video_vae_bf16_KJ.safetensors'
VIDEO_H264_MP4 = 'video/h264-mp4'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'enable_promptenhance': InputSpec(node='599', field='_un1089', default=True),
    'seed': InputSpec(node='115', field='noise_seed', default=DEFAULT_SEED_2, type='INT'),
    'prompt': InputSpec(node='110', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='626', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo\\v2\\ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler', 'euler_ancestral', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx\\taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Fast Groups Bypasser (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json', 'source_id': 'LTX-2.3_V2V_Extend_Any_Video', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_video_to_video_extend'},
)

# === Subgraph functions ===

def prompt_enhancer(
    *,
    clip,
    image,
    prompt: str,
    enabled,
):
    """PROMPT ENHANCER - single-image variant.

    Materialized from subgraph 6002fb3c-ab34-4ad8-894e-fccaa60fd8c9 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json.
    # vibecomfy source hash: sha256:fb8fc782ba4314ba2a624cfd103b8bc2d82bd239ceae259d6a07016ccad0d45b
    Inner nodes: StringConcatenate, LazySwitchKJ, easy showAnything, TextGenerateLTX2Prompt.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    easy_showanything = raw_call('easy showAnything', '486', _outputs=('output',), anything=textgenerateltx2prompt)

    lazyswitchkj = LazySwitchKJ(
        switch=enabled,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return lazyswitchkj

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)

    # Decode
    vaedecodetiled = VAEDecodeTiled(temporal_size=4096)

    # Sampling
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral')
    intconstant = INTConstant(value=10)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler')
    intconstant_2 = INTConstant(value=3)

    image_load, frame_count, audio, video_info = VHS_LoadVideo(
        video='joker_therapy.mp4',
        force_rate=24.0,
        format='LTXV',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'joker_therapy.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 24, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
    )

    # Loaders
    vaeloader = VAELoader(vae_name=VAE_NAME_3)
    latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME_3,
        clip_name2=CLIP_NAME_2,
        type_='ltxv',
        device='default',
    )

    vaeloaderkj = VAELoaderKJ(
        vae_name=VAE_NAME_2,
        device='main_device',
        weight_dtype='bf16',
    )

    vaeloader_2 = VAELoader(vae_name=VAE_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME_2)
    unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME)

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_NAME_2,
        type_='sdxl',
    )

    manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')

    manualsigmas_2 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    intconstant_3 = INTConstant(value=832)
    fast_groups_bypasser__rgthree_ = raw_call('Fast Groups Bypasser (rgthree)', '515')

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=dualcliploader)

    float, int, boolean = SimpleCalculatorKJ(
        expression=ROUND_A_B_1_8_8_1,
        **{'variables.b': 24.0, 'variables.a': intconstant},
    )

    source_fps_, source_frame_count_, source_duration_, source_width_, source_height_, loaded_fps_, loaded_frame_count_, loaded_duration_, loaded_width_, loaded_height_ = VHS_VideoInfo(
        video_info=video_info,
    )

    normalizeaudioloudness = NormalizeAudioLoudness(lufs=-16, audio=audio)

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH_2,
        model=unetloader,
    )

    source_fps__video, source_frame_count__video, source_duration__video, source_width__video, source_height__video, loaded_fps__video, loaded_frame_count__video, loaded_duration__video, loaded_width__video, loaded_height__video = VHS_VideoInfo(
        video_info=video_info,
    )

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        longer_edge=intconstant_3,
        images=image_load,
    )

    float_simple_5, int_simple_5, boolean_simple_5 = SimpleCalculatorKJ(
        expression=ROUND_A_B_1_8_8_1,
        **{'variables.b': 24.0, 'variables.a': intconstant_2},
    )

    cliptextencode_3 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

    float_simple_2, int_simple_2, boolean_simple_2 = SimpleCalculatorKJ(
        expression='a / b',
        **{'variables.a': int_simple_5, 'variables.b': loaded_fps_},
    )

    float_simple_4, int_simple_4, boolean_simple_4 = SimpleCalculatorKJ(
        expression='(a > c) or (b > c) ',
        **{'variables.a': loaded_width__video, 'variables.b': loaded_height__video, 'variables.c': intconstant_3},
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        **{'variables.a': intconstant, 'variables.b': float_simple_2},
    )

    float_simple_3, int_simple_3, boolean_simple_3 = SimpleCalculatorKJ(
        expression='a - b',
        **{'variables.a': loaded_duration_, 'variables.b': float_simple_2},
    )

    lazyswitchkj = LazySwitchKJ(
        switch=boolean_simple_4,
        on_false=image_load,
        on_true=resizeimagesbylongeredge_2,
    )

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        model=pathchsageattentionkj,
    )

    trimaudioduration = TrimAudioDuration(
        start_index=float_simple_3,
        duration=float_simple_2,
        audio=normalizeaudioloudness,
    )

    image_get_3, width, height, count = GetImageSizeAndCount(image=lazyswitchkj)

    ltxvchunkfeedforward = LTXVChunkFeedForward(
        model=ltx2memoryefficientsageattentionpatch,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=vaeloaderkj,
    )

    image_image, width_image, height_image, mask_image = ImageResizeKJv2(
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=64,
        device='cpu',
        width=width,
        height=height,
        image=image_get_3,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(model=ltxvchunkfeedforward)

    ltx2samplingpreviewoverride = raw_call('LTX2SamplingPreviewOverride', '368',
        model=ltx2attentiontunerpatch,
        vae=vaeloader_2,
    )

    image_get, mask_get = GetImageRangeFromBatch(
        start_index=-1,
        num_frames=int_simple_5,
        images=image_image,
    )

    image_get_2, mask_get_2 = GetImageRangeFromBatch(images=image_image)

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=image_get,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_get_2,
    )

    modelsamplingsd3 = ModelSamplingSD3(shift=13, model=ltx2samplingpreviewoverride)

    ltx2_nag = LTX2_NAG(
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=cliptextencode_3,
        nag_cond_video=cliptextencode,
    )

    image_get_5, mask_get_4 = GetImageRangeFromBatch(images=image_get)

    basicscheduler = BasicScheduler(
        scheduler='linear_quadratic',
        steps=8,
        model=modelsamplingsd3,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)

    image_get_4, mask_get_3 = GetImageRangeFromBatch(
        start_index=-1,
        images=resizeimagemasknode,
    )

    vaeencode_2 = VAEEncode(pixels=resizeimagemasknode, vae=vaeloader)
    prompt_enhancer_result = prompt_enhancer(
        clip=dualcliploader,
        image=resizeimagesbylongeredge,
        prompt='The Joker looks at the camera and talks, he says "You know what clownheads. This scene is not from the movie. Its from LTX 2 point 3". \n\nThen the Joker stands up with an LTX soda can in his hand. \n\nHe drinks from the soda can, and then he says "Ahhh...  with a bit of LTX and Snickers, my mood changed. Lets all be friends." \n\nThen he laughs.\n',
        enabled=None,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVAudioVideoMask(
        video_fps=24.0,
        max_length='pad',
        video_start_time=float_simple_2,
        video_end_time=float_simple,
        audio_start_time=float_simple_2,
        audio_end_time=float_simple,
        audio_latent=ltxvaudiovaeencode,
        video_latent=vaeencode_2,
    )

    vaeencode = VAEEncode(pixels=image_get_4, vae=vaeloader)
    cliptextencode_2 = CLIPTextEncode(text=prompt_enhancer_result, clip=dualcliploader)

    previewany = PreviewAny(
        widget_0=None,
        widget_1=None,
        widget_2=None,
        source=prompt_enhancer_result,
    )

    positive_ltxv, negative_ltxv, latent = LTXVAddLatentGuide(
        latent_idx=-1,
        guiding_latent=vaeencode,
        latent=video_latent_ltxv,
        negative=cliptextencode,
        positive=cliptextencode_2,
        vae=vaeloader,
    )

    positive, negative = LTXVConditioning(
        frame_rate=24.0,
        negative=negative_ltxv,
        positive=positive_ltxv,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=latent,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=basicscheduler,
    )

    video_latent_ltxv_2, audio_latent_ltxv_2 = LTXVSeparateAVLatent(av_latent=output)

    positive_ltxv_2, negative_ltxv_2, latent_ltxv = LTXVCropGuides(
        latent=video_latent_ltxv_2,
        negative=negative,
        positive=positive,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=latent_ltxv,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative_ltxv_2,
        positive=positive_ltxv_2,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        image=image_get_5,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv_2,
        video_latent=ltxvimgtovideoinplace,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output_sampler)
    ltxvaudiovaedecode = LTXVAudioVAEDecode(audio_vae=vaeloaderkj, samples=audio_latent)

    positive_ltxv_3, negative_ltxv_3, latent_ltxv_2 = LTXVCropGuides(
        latent=video_latent,
        negative=negative,
        positive=positive,
    )

    trimaudioduration_2 = TrimAudioDuration(
        duration=2048,
        start_index=float_simple_2,
        audio=ltxvaudiovaedecode,
    )

    vaedecode = VAEDecode(samples=latent_ltxv_2, vae=vaeloader)

    image, mask = GetImageRangeFromBatch(
        num_frames=DEFAULT_FRAMES_2,
        start_index=int_simple_5,
        images=vaedecode,
    )

    audioconcat = AudioConcat(audio1=normalizeaudioloudness, audio2=trimaudioduration_2)

    source_images, start_images, extended_images = ImageBatchExtendWithOverlap(
        overlap_mode='perceptual_crossfade',
        overlap=int_simple_5,
        new_images=vaedecode,
        source_images=image_image,
    )

    imagebatchmulti = ImageBatchMulti(widget_1=None, image_1=image_image, image_2=image)

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': True, 'params': {'filename': 'LTX-2_00019-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_00019.png', 'fullpath': 'C:\\Users\\runeg\\AppData\\Local\\Temp\\latentsync_0315e009\\LTX-2_00019-audio.mp4'}},
        audio=audioconcat,
        images=extended_images,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': True, 'params': {'filename': 'LTX-2_00020-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_00020.png', 'fullpath': 'C:\\Users\\runeg\\AppData\\Local\\Temp\\latentsync_0315e009\\LTX-2_00020-audio.mp4'}},
        audio=audioconcat,
        images=imagebatchmulti,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

