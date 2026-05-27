# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, KSamplerSelect, LTXVAddGuideMulti, LTXVAudioVAEDecode, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVLatentUpsampler, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, StringConcatenate, TextGenerateLTX2Prompt, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2MemoryEfficientSageAttentionPatch, LTX2_NAG, LTXVChunkFeedForward, PathchSageAttentionKJ, SimpleCalculatorKJ, VAELoaderKJ
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
A_2 = 'a/2'
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
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 1
LANCZOS = 'lanczos'
LORA_NAME = 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
LTXV = 'ltxv'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'LTXVideo\\v2\\ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
UNET_NAME_GGUF = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
VAE_TAESD_NAME = 'vae_approx\\taeltx2_3.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'
V_0_0_0 = '0, 0, 0'


PUBLIC_INPUT_METADATA = {
    'enhance_prompt': InputSpec(node='8fa4f93a-67ee-463f-ba43-249580c0bfb1:2002', field='switch', default=True),
    'middleframe_strength': InputSpec(node='2221', field='num_guides.strength_2', default=0.3),
    'seed': InputSpec(node='14', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='45', field='image', default='sodacan_01.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'prompt': InputSpec(node='11', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo\\v2\\ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx\\taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json', 'source_id': 'LTX-2.3_FML2V_First_Middle_Last_Frame_guider', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_first_middle_last_frame'},
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

    Materialized from subgraph 8fa4f93a-67ee-463f-ba43-249580c0bfb1 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json.
    # vibecomfy source hash: sha256:f7decba5226c83eccee67a82fbe95fe22ddddfe9389c6c8c8517bb991d181343
    Inner nodes: StringConcatenate, ComfySwitchNode, TextGenerateLTX2Prompt.
    """

    stringconcatenate = StringConcatenate(
        _id='8fa4f93a-67ee-463f-ba43-249580c0bfb1:482',
        string_a='',
        string_b=prompt,
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        _id='8fa4f93a-67ee-463f-ba43-249580c0bfb1:485',
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    comfyswitchnode = ComfySwitchNode(
        _id='8fa4f93a-67ee-463f-ba43-249580c0bfb1:2002',
        switch=enabled,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return comfyswitchnode


def frames_split_view(
    *,
    input,
    input_2,
    input_3,
):
    """Frames split view.

    Materialized from subgraph 19e3f7e8-881c-4a61-a360-1c463734043a in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json.
    # vibecomfy source hash: sha256:ebeead8835c000544cea05b6274b184a0df126dcb6673c1779942713de402561
    Inner nodes: ResizeImageMaskNodex3, ImagePadForOutpaintx2, ImageStitchx2.
    """

    resizeimagemasknode = ResizeImageMaskNode(
        _id='19e3f7e8-881c-4a61-a360-1c463734043a:2092',
        resize_type='scale by multiplier',
        input=input,
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        _id='19e3f7e8-881c-4a61-a360-1c463734043a:2099',
        resize_type='scale by multiplier',
        input=input_2,
    )

    resizeimagemasknode_3 = ResizeImageMaskNode(
        _id='19e3f7e8-881c-4a61-a360-1c463734043a:2179',
        resize_type='scale by multiplier',
        input=input_3,
    )

    imagepadforoutpaint = raw_call('ImagePadForOutpaint', '19e3f7e8-881c-4a61-a360-1c463734043a:2098',
        _outputs=('IMAGE', 'MASK'),
        left=16,
        top=16,
        right=16,
        bottom=16,
        feathering=0,
        image=resizeimagemasknode,
    )

    imagepadforoutpaint_2 = raw_call('ImagePadForOutpaint', '19e3f7e8-881c-4a61-a360-1c463734043a:2100',
        _outputs=('IMAGE', 'MASK'),
        left=16,
        top=16,
        right=16,
        bottom=16,
        feathering=0,
        image=resizeimagemasknode_2,
    )

    imagestitch = raw_call('ImageStitch', '19e3f7e8-881c-4a61-a360-1c463734043a:2085',
        image1=imagepadforoutpaint_2.out('IMAGE'),
        image2=imagepadforoutpaint.out('IMAGE'),
    )

    imagestitch_2 = raw_call('ImageStitch', '19e3f7e8-881c-4a61-a360-1c463734043a:2178',
        image1=imagestitch,
        image2=resizeimagemasknode_3,
    )

    return imagestitch_2

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
    image_load, _ = LoadImage(image='sodacan_01.png')
    image_load_2, _ = LoadImage(image='image (11).png')
    _, calc_int, _ = SimpleCalculatorKJ(expression='a', a=24.0)

    vaeloaderkj = VAELoaderKJ(
        vae_name=AUDIO_VAE_NAME,
        device='main_device',
        weight_dtype='bf16',
    )

    # Loaders
    vaeloader = VAELoader(vae_name=VAE_TAESD_NAME)
    vaeloader_2 = VAELoader(vae_name=VIDEO_VAE_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name=SPATIAL_UPSCALER_NAME,
    )

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
    intconstant = INTConstant(value=15)
    intconstant_2 = INTConstant(value=720)
    intconstant_3 = INTConstant(value=1280)
    image_load_3, _ = LoadImage(image='image (12).png')

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

    image, width, height, _ = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=intconstant_3,
        height=intconstant_2,
        image=image_load,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    _, calc_int_simple, _ = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        b=24.0,
        a=intconstant,
    )

    _, comfy_int = ComfyMathExpression(expression='a/2', **{'values.a': intconstant_3})

    _, comfy_int_comfy = ComfyMathExpression(
        expression='a/2',
        **{'values.a': intconstant_2},
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=calc_int_simple,
        frame_rate=calc_int,
        audio_vae=vaeloaderkj,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=comfy_int,
        height=comfy_int_comfy,
        length=calc_int_simple,
    )

    image_image, width_image, height_image, _ = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=width,
        height=height,
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

    _, calc_int_simple_2, _ = SimpleCalculatorKJ(
        expression=A_2,
        **{'variables.a': calc_int_simple},
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image,
    )

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        model=pathchsageattentionkj,
    )

    ltxvpreprocess_2 = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge_2,
    )

    image_image_2, _, _, _ = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        divisible_by=32,
        device=CPU,
        width=width_image,
        height=height_image,
        image=image_load_3,
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(
        model=ltx2memoryefficientsageattentionpatch,
    )

    resizeimagesbylongeredge_3 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image_2,
    )

    ltxvpreprocess_3 = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge,
    )

    ltxvpreprocess = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge_3,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(model=ltxvchunkfeedforward)
    frames_split_view_result = frames_split_view(
        input=resizeimagesbylongeredge_3,
        input_2=resizeimagesbylongeredge_2,
        input_3=resizeimagesbylongeredge_2,
    )
    prompt_enhancer_result = prompt_enhancer(
        clip=dualcliploader,
        image=frames_split_view_result,
        enabled=True,
        prompt='Make this come alive with cinematic motion, smooth animation. \n\nThe scene starts with a close up of an LTX soda can with ic cubes around it. \n\nAll of a suddent an arm comes into frame and grabs the soda can, and lifts the soda can up. \n\nCamera pans up smoothly to show a woman holding the soda can. She talks with a soft British voice, and she says :" An LTX a day, keeps the doctor away". Then she laghts, and finally she drinks from the soda can. ',
    )
    model, _ = Power_Lora_Loader_rgthree(model=ltx2attentiontunerpatch)
    cliptextencode_2 = CLIPTextEncode(text=prompt_enhancer_result, clip=dualcliploader)
    ltx2samplingpreviewoverride = raw_call('LTX2SamplingPreviewOverride', '198', model=model, vae=vaeloader)

    positive, negative = LTXVConditioning(
        frame_rate=24.0,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    ltx2_nag = LTX2_NAG(
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=cliptextencode,
        nag_cond_video=cliptextencode,
    )

    positive_ltxv_3, negative_ltxv_3, latent_ltxv_2 = LTXVAddGuideMulti(
        widget_0='3',
        widget_1=0,
        widget_2=0.7,
        widget_3=0,
        widget_4=0.25,
        widget_5=-1,
        widget_6=1,
        latent=emptyltxvlatentvideo,
        negative=negative,
        positive=positive,
        vae=vaeloader_2,
        **{'num_guides.strength_1': 0.7, 'num_guides.strength_2': 0.3, 'num_guides.strength_3': 1.0, 'num_guides.frame_idx_2': calc_int_simple_2, 'num_guides.image_1': ltxvpreprocess_2, 'num_guides.image_2': ltxvpreprocess_3, 'num_guides.image_3': ltxvpreprocess},
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=latent_ltxv_2,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative_ltxv_3,
        positive=positive_ltxv_3,
    )

    ltxvscheduler = LTXVScheduler(steps=8, latent=ltxvconcatavlatent)

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    positive_ltxv_4, negative_ltxv_4, latent_ltxv_3 = LTXVCropGuides(
        latent=video_latent,
        negative=negative_ltxv_3,
        positive=positive_ltxv_3,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=latent_ltxv_3,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader_2,
    )

    positive_ltxv_2, negative_ltxv_2, latent_ltxv = LTXVAddGuideMulti(
        widget_0='2',
        widget_1=0,
        widget_2=1,
        widget_3=-1,
        widget_4=1,
        latent=ltxvlatentupsampler,
        negative=negative_ltxv_4,
        positive=positive_ltxv_4,
        vae=vaeloader_2,
        **{'num_guides.strength_1': 0.7, 'num_guides.strength_2': 1.0, 'num_guides.image_1': resizeimagesbylongeredge_2, 'num_guides.image_2': resizeimagesbylongeredge_3},
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative_ltxv_2,
        positive=positive_ltxv_2,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=latent_ltxv,
    )

    output_sampler, _ = SamplerCustomAdvanced(
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

    _, _, latent = LTXVCropGuides(
        latent=video_latent_ltxv,
        negative=negative_ltxv_2,
        positive=positive_ltxv_2,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(temporal_size=4096, samples=latent, vae=vaeloader_2)

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-2_01647-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_01647.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-2_01647-audio.mp4'}},
        audio=ltxvaudiovaedecode,
        images=vaedecodetiled,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

