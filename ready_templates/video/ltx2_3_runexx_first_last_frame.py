# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, ImageScaleBy, KSamplerSelect, LTXVAddGuide, LTXVAudioVAEDecode, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVLatentUpsampler, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, StringConcatenate, TextGenerateLTX2Prompt, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2MemoryEfficientSageAttentionPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VAELoaderKJ
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
CENTER = 'center'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_NAME_GGUF = 'gemma-3-12b-it-Q2_K.gguf'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
CPU = 'cpu'
CROP = 'crop'
DEFAULT_PROMPT = 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
FIXED = 'fixed'
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.6
LORA_NAME = 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
LTXV = 'ltxv'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
NEAREST_EXACT = 'nearest-exact'
UNET_NAME = 'LTXVideo\\v2\\ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
UNET_NAME_GGUF = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
VAE_TAESD_NAME = 'vae_approx\\taeltx2_3.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'
V_0_0_0 = '0, 0, 0'


PUBLIC_INPUT_METADATA = {
    'enhance_prompt': InputSpec(node='2070', field='_un3681', default=True),
    'lastframe_strength': InputSpec(node='2152', field='strength', default=1.0),
    'firstframe_strength': InputSpec(node='2105', field='num_images.strength_1', default=0.5),
    'seed': InputSpec(node='14', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='45', field='image', default='image (6).png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'prompt': InputSpec(node='11', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo\\v2\\ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx\\taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'LTXVAddGuide', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideoInplaceKJ', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json', 'source_id': 'LTX-2.3_FLF2V_First_Last_Frame', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_first_last_frame'},
)

# === Subgraph functions ===

def prompt_enhancer(
    *,
    clip,
    image,
    enabled,
    prompt,
):
    """PROMPT ENHANCER - single-image variant.

    Materialized from subgraph 8fa4f93a-67ee-463f-ba43-249580c0bfb1 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json.
    # vibecomfy source hash: sha256:0f8159ebf8aa4a4c3a5e6b80f1b2ee0f64d219acd682c3d5e21076202df94076
    Inner nodes: StringConcatenate, ComfySwitchNode, easy showAnything, TextGenerateLTX2Prompt.
    """

    stringconcatenate = StringConcatenate(string_a='', string_b=prompt)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    easy_showanything = raw_call('easy showAnything', '486', _outputs=('output',), anything=textgenerateltx2prompt)

    comfyswitchnode = ComfySwitchNode(
        switch=enabled,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return comfyswitchnode


def frames_split_view():
    """Frames split view.

    Materialized from subgraph 19e3f7e8-881c-4a61-a360-1c463734043a in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json.
    # vibecomfy source hash: sha256:a4d60856efd1ce434648446187af66f3a319d0e453e9fb84ce71c56ccace6386
    Inner nodes: ResizeImageMaskNodex2, ImagePadForOutpaintx2, ImageStitch.
    """

    resizeimagemasknode = ResizeImageMaskNode(resize_type='scale by multiplier')
    resizeimagemasknode_2 = ResizeImageMaskNode(resize_type='scale by multiplier')

    imagepadforoutpaint = raw_call('ImagePadForOutpaint', '2098',
        _outputs=('IMAGE', 'MASK'),
        left=16,
        top=16,
        right=16,
        bottom=16,
        feathering=0,
        image=resizeimagemasknode,
    )

    imagepadforoutpaint_2 = raw_call('ImagePadForOutpaint', '2100',
        _outputs=('IMAGE', 'MASK'),
        left=16,
        top=16,
        right=16,
        bottom=16,
        feathering=0,
        image=resizeimagemasknode_2,
    )

    imagestitch = raw_call('ImageStitch', '2085',
        image1=imagepadforoutpaint_2.out('IMAGE'),
        image2=imagepadforoutpaint.out('IMAGE'),
    )

    return imagestitch

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Sampling
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')
    manualsigmas = ManualSigmas(sigmas='0.909375, 0.725, 0.421875, 0.0')
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)

    # Inputs
    image_load, mask_load = LoadImage(image='image (6).png')
    image_load_2, mask_load_2 = LoadImage(image='0 (13).webp')
    calc_float, calc_int, calc_bool = SimpleCalculatorKJ(expression='a', a=24.0)

    vaeloaderkj = VAELoaderKJ(
        vae_name=AUDIO_VAE_NAME,
        device='main_device',
        weight_dtype='bf16',
    )

    # Loaders
    vaeloader = VAELoader(vae_name=VAE_TAESD_NAME)
    vaeloader_2 = VAELoader(vae_name=VIDEO_VAE_NAME)
    latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME)

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1=CLIP_NAME_GGUF,
        clip_name2=CLIP_PROJECTION_NAME,
        type_=LTXV,
    )

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type_=LTXV,
        device='default',
    )

    unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME_GGUF)

    manualsigmas_2 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_3 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
    intconstant = INTConstant(value=10)
    intconstant_2 = INTConstant(value=720)
    intconstant_3 = INTConstant(value=1280)
    frames_split_view_result = frames_split_view()

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

    image, width_image, height_image, mask = ImageResizeKJv2(
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=image_load,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH_2,
        model=unetloader,
    )

    prompt_enhancer_result = prompt_enhancer(
        clip=dualcliploader,
        image=frames_split_view_result,
        enabled=None,
        prompt="Make this image come alive with cinematic motion, smooth animation. \n\nA foggy night in in 1700's Amsterdam. The fog is thick and swirling, illuminating by streetlights. we see a bridge over a canal, cobblestone streets, canal buildings lining the canal The vibe is uneasy, moody, slightly dangerous.\n\nThe camera crane down high angle to a low angle ending with a close up of a vampire's hand with leather gloves on holding a walking cane.  Single continuous camera shot ",
    )

    calc_float_simple, calc_int_simple, calc_bool_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        b=24.0,
        a=intconstant,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=calc_int_simple,
        frame_rate=calc_int,
        audio_vae=vaeloaderkj,
    )

    cliptextencode_2 = CLIPTextEncode(text=prompt_enhancer_result, clip=dualcliploader)
    imagescaleby = ImageScaleBy(upscale_method='lanczos', scale_by=0.5, image=image)

    image_image, width_image_2, height_image_2, mask_image = ImageResizeKJv2(
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=width_image,
        height=height_image,
        image=image_load_2,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image,
    )

    positive, negative = LTXVConditioning(
        frame_rate=24.0,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    width, height, batch_size = GetImageSize(image=imagescaleby)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=image_image)

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        model=pathchsageattentionkj,
    )

    ltxvpreprocess_2 = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge_2,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width,
        height=height,
        length=calc_int_simple,
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(
        model=ltx2memoryefficientsageattentionpatch,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        num_images='2',
        strength_1=0.7,
        index_1=0.7,
        widget_3=0,
        widget_4=-1,
        latent=emptyltxvlatentvideo,
        vae=vaeloader_2,
        **{'num_images.image_1': ltxvpreprocess_2, 'num_images.image_2': ltxvpreprocess},
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(model=ltxvchunkfeedforward)

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvimgtovideoinplacekj,
    )

    model, clip = Power_Lora_Loader_rgthree(model=ltx2attentiontunerpatch)
    ltxvscheduler = LTXVScheduler(steps=8, latent=ltxvconcatavlatent)
    ltx2samplingpreviewoverride = raw_call('LTX2SamplingPreviewOverride', '198', model=model, vae=vaeloader)

    ltx2_nag = LTX2_NAG(
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader_2,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        num_images='1',
        strength_1=1,
        index_1=0,
        latent=ltxvlatentupsampler,
        vae=vaeloader_2,
        **{'num_images.strength_1': 0.5, 'num_images.image_1': resizeimagesbylongeredge_2},
    )

    positive_ltxv, negative_ltxv, latent = LTXVAddGuide(
        frame_idx=-1,
        strength=1.0,
        image=resizeimagesbylongeredge,
        latent=ltxvimgtovideoinplacekj_2,
        negative=negative,
        positive=positive,
        vae=vaeloader_2,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=latent,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_3,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=vaeloaderkj,
        samples=audio_latent_ltxv,
    )

    positive_ltxv_2, negative_ltxv_2, latent_ltxv = LTXVCropGuides(
        latent=video_latent_ltxv,
        negative=negative_ltxv,
        positive=positive_ltxv,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        temporal_size=4096,
        samples=latent_ltxv,
        vae=vaeloader_2,
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
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-2_01574-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_01574.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-2_01574-audio.mp4'}},
        audio=ltxvaudiovaedecode,
        images=vaedecodetiled,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

