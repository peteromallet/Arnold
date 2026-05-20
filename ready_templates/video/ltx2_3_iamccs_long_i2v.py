# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Long Image To Video with LTX 2.19B Distilled Checkpoint.

Output: unknown.

Source:  workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json

Packs:   ComfyUI-GGUF, ComfyUI-KJNodes, ComfyUI-LTXVideo, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _create_video(wf, _id, fps, audio, images, **overrides):
    kwargs = dict(widget_0=8,
                  fps=fps,
                  audio=audio,
                  images=images)
    kwargs.update(overrides)
    return node(wf, 'CreateVideo', _id, **kwargs)
def _save_video(wf, _id, video, **overrides):
    kwargs = dict(filename_prefix='output',
                  format='mp4',
                  codec='h264',
                  video=video)
    kwargs.update(overrides)
    return node(wf, 'SaveVideo', _id, **kwargs)
MODELS = {
    'ltx_2_19b_distilled_checkpoint': ModelAsset(
        filename='ltx-2-19b-distilled.safetensors',
        url='',
        subdir='checkpoints',
    ),
    'gemma_clip': ModelAsset(
        filename='gemma_3_12B_it_fp8_e4m3fn.safetensors',
        url='',
        subdir='text_encoders',
    ),
    'ltx_2_19b_embeddings_connector_dev_bf16_cl': ModelAsset(
        filename='ltx-2-19b-embeddings_connector_dev_bf16.safetensors',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_iamccs_long_i2v',
    capability='long_image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git',
                       'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'approach': 'long low-VRAM image-to-video', 'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json', 'smoke_resolution': '256x256x5_frames'},
    coverage_tier='supplemental',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    primitive_string_multiline_5175 = node(wf, 'PrimitiveStringMultiline', '5175',
        value='Cinematic action packed shot. the man says silently: "We need to run." the camera zooms in on his mouth then immediately screams: "NOW!". the camera zooms back out, he turns around, and starts running away, the camera tracks his run in hand held style.',
    )
    # ════ LOADERS ════
    checkpoint_loader_simple_5176 = node(wf, 'CheckpointLoaderSimple', '5176',
        ckpt_name=MODELS['ltx_2_19b_distilled_checkpoint'].filename,
    )
    ltxvgemma_clipmodel_loader = node(wf, 'LTXVGemmaCLIPModelLoader', '5178',
        widget_0=MODELS['gemma_clip'].filename,
        widget_1=MODELS['ltx_2_19b_distilled_checkpoint'].filename,
        widget_2=1024,
    )
    input_image = node(wf, 'LoadImage', '5180',
        image='z-image_00255_.png',
)
    low_vramaudio_vaeloader = node(wf, 'LowVRAMAudioVAELoader', '5188',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
    )
    # ════ LATENT ════
    latent_upscale_model_loader_5210 = node(wf, 'LatentUpscaleModelLoader', '5210',
        model_name='ltx-2-spatial-upscaler-x2-1.0.safetensors',
    )
    unet_loader_gguf = node(wf, 'UnetLoaderGGUF', '5215',
        unet_name='LTX-2-dev-Q5_K_S.gguf',
    )
    iamccs__ltx2__lo_rastack_staged = node(wf, 'IAMCCS_LTX2_LoRAStackStaged', '5218',
        widget_0='ltx-2-19b-distilled-lora-384.safetensors',
        widget_1=1,
        widget_2=1,
        widget_3='ltx-2-19b-lora-camera-control-dolly-right.safetensors',
        widget_4=0,
        widget_5=0,
        widget_6='no',
        widget_7=0,
        widget_8=0,
    )
    vaeloader_k_j = node(wf, 'VAELoaderKJ', '5220',
        vae_name='LTX2_video_vae_2_bf16.safetensors',
        device='main_device',
        weight_dtype='bf16',
    )
    audio_vae = node(wf, 'LTXVAudioVAELoader', '5221',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    text_encoder = node(wf, 'DualCLIPLoader', '5222',
        clip_name1=MODELS['gemma_clip'].filename,
        clip_name2=MODELS['ltx_2_19b_embeddings_connector_dev_bf16_cl'].filename,
        type='ltxv',
        device='default',
    )
    iamccs__ltx2__frame_rate_sync = node(wf, 'IAMCCS_LTX2_FrameRateSync', '5225',
        widget_0=24,
        widget_1='fixed',
    )
    primitive_string_multiline_2 = node(wf, 'PrimitiveStringMultiline', '5232',
        value='man runs away from camera. the camera cranes up and show him run into the distance down the street at a busy New York night.',
    )
    fast_groups_muter__rgthree_ = node(wf, 'Fast Groups Muter (rgthree)', '5265')
    primitive_string_multiline_3 = node(wf, 'PrimitiveStringMultiline', '9001',
        value='the camera cranes up and show the whole streets of new york.',
    )
    iamccs__auto_link_arguments = node(wf, 'IAMCCS_AutoLinkArguments', '9026',
        widget_0=False,
        widget_1=False,
        widget_10='Red',
        widget_11='Orange',
        widget_12='Black',
        widget_13='',
        widget_14='',
        widget_15='both',
        widget_17='',
        widget_19='',
        widget_2=False,
        widget_3=True,
        widget_4='None',
        widget_5='',
        widget_6='TopToDown',
        widget_7='AvoidAll',
        widget_8='',
        widget_9=True,
    )
    empty_image_10955 = node(wf, 'EmptyImage', '10955',
        widget_0=1332,
        widget_1=720,
        widget_2=1,
        widget_3=0,
    )
    iamccs__ltx2__time_frame_count = node(wf, 'IAMCCS_LTX2_TimeFrameCount', '10956',
        widget_0=10,
        widget_1=241,
        widget_2='fixed',
    )
    iamccs__model_with_lo_r_a__ltx2__staged = node(wf, 'IAMCCS_ModelWithLoRA_LTX2_Staged', '5219',
        lora_stage1=iamccs__ltx2__lo_rastack_staged.out(0),
        lora_stage2=iamccs__ltx2__lo_rastack_staged.out(1),
        model=unet_loader_gguf.out(0),
        model_stage2=unet_loader_gguf.out(0),
    )
    iamccs__ltx2__lo_rastack_model_i_o = node(wf, 'IAMCCS_LTX2_LoRAStackModelIO', '5259',
        widget_0='ltx-2-19b-distilled-lora-384.safetensors',
        widget_1=1,
        widget_2='no',
        widget_3=0,
        widget_4='no',
        widget_5=0,
        model=checkpoint_loader_simple_5176.out(0),
    )
    any_switch__rgthree__2 = node(wf, 'Any Switch (rgthree)', '5261',
        any_01=low_vramaudio_vaeloader.out(0),
        any_02=audio_vae.out('AUDIO_VAE'),
    )
    any_switch__rgthree__3 = node(wf, 'Any Switch (rgthree)', '5262',
        any_01=ltxvgemma_clipmodel_loader.out(0),
        any_02=text_encoder.out('CLIP'),
    )
    any_switch__rgthree__4 = node(wf, 'Any Switch (rgthree)', '5263',
        any_01=checkpoint_loader_simple_5176.out(2),
        any_02=vaeloader_k_j.out(0),
    )
    iamccs__auto_link_converter = node(wf, 'IAMCCS_AutoLinkConverter', '9025',
        arg=iamccs__auto_link_arguments.out(0),
    )
    # ════ TEXT CONDITIONING ════
    negative = node(wf, 'CLIPTextEncode', '5174',
        text=primitive_string_multiline_5175.out(0),
        clip=any_switch__rgthree__3.out(0),
    )
    prompt_embedding_2 = node(wf, 'CLIPTextEncode', '5233',
        text=primitive_string_multiline_2.out(0),
        clip=any_switch__rgthree__3.out(0),
    )
    prompt_embedding_3 = node(wf, 'CLIPTextEncode', '9002',
        text=primitive_string_multiline_3.out(0),
        clip=any_switch__rgthree__3.out(0),
    )
    iamccs__ggufaccelerator_1 = node(wf, 'IAMCCS_GGUF_accelerator', '9684',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5='all_or_nothing',
        widget_6=1024,
        model=iamccs__model_with_lo_r_a__ltx2__staged.out(1),
    )
    iamccs_gguf_accelerator_2 = node(wf, 'IAMCCS_GGUF_accelerator', '9685',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5='all_or_nothing',
        widget_6=1024,
        model=iamccs__model_with_lo_r_a__ltx2__staged.out(1),
    )
    conditioning_1 = node(wf, 'LTXVConditioning', '5173',
        frame_rate=iamccs__ltx2__frame_rate_sync.out(1),
        negative=negative.out('CONDITIONING'),
        positive=negative.out('CONDITIONING'),
    )
    conditioning_2 = node(wf, 'LTXVConditioning', '5234',
        frame_rate=iamccs__ltx2__frame_rate_sync.out(1),
        negative=prompt_embedding_2.out('CONDITIONING'),
        positive=prompt_embedding_2.out('CONDITIONING'),
    )
    any_switch__rgthree_ = node(wf, 'Any Switch (rgthree)', '5258',
        any_01=iamccs__ltx2__lo_rastack_model_i_o.out(0),
        any_02=iamccs__ggufaccelerator_1.out(0),
    )
    any_switch__rgthree__5 = node(wf, 'Any Switch (rgthree)', '5264',
        any_01=iamccs__ltx2__lo_rastack_model_i_o.out(0),
        any_02=iamccs_gguf_accelerator_2.out(0),
    )
    conditioning_3 = node(wf, 'LTXVConditioning', '9003',
        frame_rate=iamccs__ltx2__frame_rate_sync.out(1),
        negative=prompt_embedding_3.out('CONDITIONING'),
        positive=prompt_embedding_3.out('CONDITIONING'),
    )
    n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78 = node(wf, '3eaa20c4-5842-4fe4-87df-c0a7e83a6a78', '5189',
        widget_0=121,
        widget_1=25,
        widget_2=0.6,
        widget_3=43,
        audio_vae=any_switch__rgthree__2.out(0),
        frame_rate=iamccs__ltx2__frame_rate_sync.out(0),
        image_1=empty_image_10955.out(0),
        images=input_image.out('IMAGE'),
        length=iamccs__ltx2__time_frame_count.out(0),
        model=any_switch__rgthree__5.out(0),
        model_1=any_switch__rgthree_.out(0),
        negative=conditioning_1.out('NEGATIVE'),
        positive=conditioning_1.out('POSITIVE'),
        upscale_model_1=latent_upscale_model_loader_5210.out(0),
        vae=any_switch__rgthree__4.out(0),
    )
    video_5190 = _create_video(wf, '5190', iamccs__ltx2__frame_rate_sync.out(1), n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(1), n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(0))
    iamccs__ltx2__get_image_from_batch = node(wf, 'IAMCCS_LTX2_GetImageFromBatch', '9014',
        widget_0='from_end',
        widget_1=10,
        widget_2='none',
        widget_3='none',
        widget_4='none',
        widget_5='native_workflow_safe',
        widget_6=10,
        widget_7=0,
        widget_8=10,
        images=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(0),
    )
    saved_video_4958 = _save_video(wf, '4958', video_5190.out('VIDEO'))
    n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0 = node(wf, '8b36a85a-087e-4ee5-85ca-cccc69c5c5d0', '5235',
        widget_0=121,
        widget_1=24,
        widget_2=0.6,
        widget_3=43,
        audio_vae=any_switch__rgthree__2.out(0),
        frame_rate=iamccs__ltx2__frame_rate_sync.out(0),
        image_1=empty_image_10955.out(0),
        images=iamccs__ltx2__get_image_from_batch.out(0),
        length=iamccs__ltx2__time_frame_count.out(0),
        model=any_switch__rgthree__5.out(0),
        model_1=any_switch__rgthree_.out(0),
        negative=conditioning_2.out('NEGATIVE'),
        positive=conditioning_2.out('POSITIVE'),
        upscale_model_1=latent_upscale_model_loader_5210.out(0),
        vae=any_switch__rgthree__4.out(0),
    )
    createvideo_2 = _create_video(wf, '5236', iamccs__ltx2__frame_rate_sync.out(1), n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(1), n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(0))
    audio_concat_5252 = node(wf, 'AudioConcat', '5252',
        widget_0='after',
        audio1=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(1),
        audio2=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(1),
    )
    iamccs__ltx2__extension_module_1 = node(wf, 'IAMCCS_LTX2_ExtensionModule', '9015',
        widget_0=10,
        widget_1='source',
        widget_10='none',
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14='target_extension_ltx2',
        widget_15=1,
        widget_2='linear_blend',
        widget_3=True,
        widget_4='a-1',
        widget_5='none',
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(0),
        source_images=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(0),
    )
    savevideo_2 = _save_video(wf, '5237', createvideo_2.out('VIDEO'))
    n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2 = node(wf, '8b36a85a-087e-4ee5-85ca-cccc69c5c5d0', '9004',
        widget_0=121,
        widget_1=24,
        widget_2=0.6,
        widget_3=43,
        audio_vae=any_switch__rgthree__2.out(0),
        frame_rate=iamccs__ltx2__frame_rate_sync.out(0),
        image_1=empty_image_10955.out(0),
        images=iamccs__ltx2__extension_module_1.out(1),
        length=iamccs__ltx2__time_frame_count.out(0),
        model=any_switch__rgthree__5.out(0),
        model_1=any_switch__rgthree_.out(0),
        negative=conditioning_3.out('NEGATIVE'),
        positive=conditioning_3.out('POSITIVE'),
        upscale_model_1=latent_upscale_model_loader_5210.out(0),
        vae=any_switch__rgthree__4.out(0),
    )
    createvideo_4 = _create_video(wf, '9005', iamccs__ltx2__frame_rate_sync.out(1), n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(1), n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(0))
    audio_concat_2 = node(wf, 'AudioConcat', '9008',
        widget_0='after',
        audio1=audio_concat_5252.out(0),
        audio2=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(1),
    )
    iamccs_ltx2_extensionmodule_2 = node(wf, 'IAMCCS_LTX2_ExtensionModule', '9016',
        widget_0=10,
        widget_1='source',
        widget_10='none',
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14='target_extension_ltx2',
        widget_15=1,
        widget_2='linear_blend',
        widget_3=True,
        widget_4='a-1',
        widget_5='none',
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(0),
        source_images=iamccs__ltx2__extension_module_1.out(2),
    )
    createvideo_3 = _create_video(wf, '5254', iamccs__ltx2__frame_rate_sync.out(1), audio_concat_2.out(0), iamccs_ltx2_extensionmodule_2.out(2))
    savevideo_4 = _save_video(wf, '9006', createvideo_4.out('VIDEO'))
    savevideo_3 = _save_video(wf, '5255', createvideo_3.out('VIDEO'))

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

