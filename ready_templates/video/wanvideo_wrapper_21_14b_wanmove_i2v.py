# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Motion Track I2V with CLIP Vision H CLIP.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_wanmove_i2v.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {
    'clip_vision_h_clip': ModelAsset(
        filename='clip_vision_h.safetensors',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_21_14b_wanmove_i2v',
    capability='motion_track_i2v',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]},
    provenance={'source_role': 'materialized_ready_python_template', 'approach': 'WanMove image-to-video motion track', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_wanmove_i2v.json', 'smoke_resolution': '256x256x5_frames'},
    coverage_tier='supplemental',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ TEXT CONDITIONING ════
    load_wan_video_t5_text_encoder_11 = node(wf, 'LoadWanVideoT5TextEncoder', '11',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        load_device='offload_device',
        quantization='disabled',
    )
    # ════ LOADERS ════
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\WanMove\\Wan21-WanMove_fp8_scaled_e4m3fn_KJ.safetensors',
        base_precision='fp16',
        quantization='disabled',
        load_device='offload_device',
        attention_mode='sdpa',
        rms_norm_function='default',
    )
    # ════ SAMPLING ════
    wan_video_torch_compile_settings_35 = node(wf, 'WanVideoTorchCompileSettings', '35',
        backend='inductor',
        fullgraph=False,
        mode='default',
        dynamic=False,
        dynamo_cache_size_limit=64,
        compile_transformer_blocks_only=True,
        dynamo_recompile_limit=128,
        force_parameter_static_shapes=False,
        allow_unmerged_lora_compile=False,
    )
    wan_video_vaeloader = node(wf, 'WanVideoVAELoader', '38',
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
        widget_2=False,
    )
    wan_video_block_swap_39 = node(wf, 'WanVideoBlockSwap', '39',
        blocks_to_swap=25,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=0,
        prefetch_blocks=1,
        block_swap_debug=False,
    )
    input_image = node(wf, 'LoadImage', '58',
        image='oldman_upscaled.png',
)
    clip_vision = node(wf, 'CLIPVisionLoader', '59',
        clip_name=MODELS['clip_vision_h_clip'].filename,
    )
    wan_video_lora_select_69 = node(wf, 'WanVideoLoraSelect', '69',
        lora='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        strength=1,
        low_mem_load=False,
        merge_loras=False,
    )
    primitive_node_85 = node(wf, 'PrimitiveNode', '85',
        widget_0=81,
        widget_1='fixed',
    )
    primitive_node_2 = node(wf, 'PrimitiveNode', '86',
        widget_0=640,
        widget_1='fixed',
    )
    primitive_node_3 = node(wf, 'PrimitiveNode', '87',
        widget_0=640,
        widget_1='fixed',
    )
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt='video of an old man',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        force_offload=True,
        use_disk_cache=True,
        device='gpu',
        model_to_offload=wan_video_model_loader_22.out(0),
        t5=load_wan_video_t5_text_encoder_11.out(0),
    )
    # ════ IMAGE PREP ════
    resized_image = node(wf, 'ImageResizeKJv2', '68',
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=16,
        device='cpu',
height=primitive_node_3.out(0),
        image=input_image.out('IMAGE'),
        width=primitive_node_2.out(0),
    )
    wan_video_set_lo_r_as_75 = node(wf, 'WanVideoSetLoRAs', '75',
        lora=wan_video_lora_select_69.out(0),
        model=wan_video_model_loader_22.out(0),
    )
    wan_video_clip_vision_encode_65 = node(wf, 'WanVideoClipVisionEncode', '65',
        strength_1=1,
        strength_2=1,
        crop='center',
        combine_embeds='average',
        force_offload=True,
        tiles=0,
        ratio=0.2,
        clip_vision=clip_vision.out('CLIP_VISION'),
        image_1=resized_image.out('IMAGE'),
    )
    wan_video_set_block_swap_70 = node(wf, 'WanVideoSetBlockSwap', '70',
        block_swap_args=wan_video_block_swap_39.out(0),
        model=wan_video_set_lo_r_as_75.out(0),
    )
    spline_editor_77 = node(wf, 'SplineEditor', '77',
        widget_0='[{"points":[{"x":309.03010266217507,"y":338.4615410109536},{"x":268.15310495553814,"y":268.15310495553814},{"x":367.8929793597322,"y":245.26198623982145},{"x":380.97361862585603,"y":327.0159816530953},{"x":312.300262478706,"y":385.8788583506524},{"x":238.72166660675956,"y":356.44742000187387},{"x":230.54626706543218,"y":312.300262478706}],"color":"#1f77b4","name":"Spline 1"}]',
        widget_1='[[{"x":309.03009033203125,"y":338.4615478515625},{"x":304.7218322753906,"y":333.7557067871094},{"x":300.4680480957031,"y":329.0005798339844},{"x":296.2775573730469,"y":324.1896057128906},{"x":292.16131591796875,"y":319.3149719238281},{"x":288.1344909667969,"y":314.36627197265625},{"x":284.21636962890625,"y":309.33111572265625},{"x":280.43511962890625,"y":304.1925048828125},{"x":276.83233642578125,"y":298.92742919921875},{"x":273.47186279296875,"y":293.5048828125},{"x":270.4659423828125,"y":287.8789978027344},{"x":268.02728271484375,"y":281.9877624511719},{"x":266.634033203125,"y":275.77642822265625},{"x":267.44195556640625,"y":269.5126037597656},{"x":271.0517272949219,"y":264.2775573730469},{"x":275.5921325683594,"y":259.80364990234375},{"x":280.6703186035156,"y":255.94668579101562},{"x":286.10455322265625,"y":252.60763549804688},{"x":291.78814697265625,"y":249.7119598388672},{"x":297.6553955078125,"y":247.20834350585938},{"x":303.66290283203125,"y":245.06248474121094},{"x":309.78057861328125,"y":243.25405883789062},{"x":315.986083984375,"y":241.774658203125},{"x":322.2609558105469,"y":240.62457275390625},{"x":328.5887756347656,"y":239.8154296875},{"x":334.9522705078125,"y":239.3683319091797},{"x":341.3310546875,"y":239.3177032470703},{"x":347.69744873046875,"y":239.71331787109375},{"x":354.0099182128906,"y":240.6256561279297},{"x":360.201904296875,"y":242.1505126953125},{"x":366.16265869140625,"y":244.41184997558594},{"x":371.7440490722656,"y":247.49278259277344},{"x":376.8460998535156,"y":251.3139190673828},{"x":381.28900146484375,"y":255.8828125},{"x":384.9034423828125,"y":261.1309509277344},{"x":387.59295654296875,"y":266.9087219238281},{"x":389.36480712890625,"y":273.0321044921875},{"x":390.3052062988281,"y":279.3385009765625},{"x":390.5349426269531,"y":285.71173095703125},{"x":390.1739807128906,"y":292.07977294921875},{"x":389.32659912109375,"y":298.402099609375},{"x":388.0774841308594,"y":304.6578674316406},{"x":386.4941101074219,"y":310.8377380371094},{"x":384.62884521484375,"y":316.9386291503906},{"x":382.5249328613281,"y":322.9615783691406},{"x":380.212646484375,"y":328.9076232910156},{"x":377.68255615234375,"y":334.76422119140625},{"x":374.89642333984375,"y":340.5031433105469},{"x":371.8153076171875,"y":346.08905029296875},{"x":368.40093994140625,"y":351.4773864746094},{"x":364.6192932128906,"y":356.6141357421875},{"x":360.4477233886719,"y":361.439208984375},{"x":355.88116455078125,"y":365.8919677734375},{"x":350.9376525878906,"y":369.9219970703125},{"x":345.65643310546875,"y":373.4981384277344},{"x":340.09100341796875,"y":376.61407470703125},{"x":334.2998046875,"y":379.2880554199219},{"x":328.3372497558594,"y":381.5551452636719},{"x":322.2490234375,"y":383.4603271484375},{"x":316.0707092285156,"y":385.0499267578125},{"x":309.8260803222656,"y":386.3546447753906},{"x":303.5069580078125,"y":387.2225036621094},{"x":297.13702392578125,"y":387.5397033691406},{"x":290.7676086425781,"y":387.22509765625},{"x":284.470947265625,"y":386.2176513671875},{"x":278.33062744140625,"y":384.4978942871094},{"x":272.420654296875,"y":382.102294921875},{"x":266.7846984863281,"y":379.11712646484375},{"x":261.4264221191406,"y":375.6566467285156},{"x":256.31378173828125,"y":371.8414611816406},{"x":251.39317321777344,"y":367.7808837890625},{"x":246.6000213623047,"y":363.57012939453125},{"x":241.8663787841797,"y":359.29241943359375},{"x":237.19577026367188,"y":354.9486999511719},{"x":233.47332763671875,"y":349.7870788574219},{"x":231.0011749267578,"y":343.91717529296875},{"x":229.6009063720703,"y":337.6989440917969},{"x":229.03160095214844,"y":331.34771728515625},{"x":229.09124755859375,"y":324.9698181152344},{"x":229.6313934326172,"y":318.6137390136719},{"x":230.5462646484375,"y":312.3002624511719}]]',
        widget_10=0,
        widget_11=1,
        widget_12='',
        widget_13=None,
        widget_2=640,
        widget_3=640,
        widget_4=81,
        widget_5='path',
        widget_6='cardinal',
        widget_7=0.5,
        widget_8=1,
        widget_9='list',
        bg_image=resized_image.out('IMAGE'),
        mask_height=primitive_node_3.out(0),
        mask_width=primitive_node_2.out(0),
        points_to_sample=primitive_node_85.out(0),
    )
    repeat_image_batch_91 = node(wf, 'RepeatImageBatch', '91',
        widget_0=81,
        amount=primitive_node_85.out(0),
        image=resized_image.out('IMAGE'),
    )
    wan_video_image_to_video_encode_63 = node(wf, 'WanVideoImageToVideoEncode', '63',
        
        
        noise_aug_strength=0,
        start_latent_strength=1,
        end_latent_strength=1,
        force_offload=True,
        tiled_vae=False,
        fun_or_fl2v_model=False,
        widget_9=0,
        clip_embeds=wan_video_clip_vision_encode_65.out(0),
        height=resized_image.out(2),
        num_frames=spline_editor_77.out(3),
        start_image=resized_image.out('IMAGE'),
        vae=wan_video_vaeloader.out(0),
        width=resized_image.out(1),
    )
    wan_video_add_wan_move_tracks_80 = node(wf, 'WanVideoAddWanMoveTracks', '80',
        widget_0=1,
        image_embeds=wan_video_image_to_video_encode_63.out(0),
        track_coords=spline_editor_77.out(1),
    )
    wan_video_sampler_27 = node(wf, 'WanVideoSampler', '27',
        steps=1,
        cfg=1,
        rope_function='comfy',
        start_step=0,
        end_step=-1,
        add_noise_to_samples=False,
        shift=5,
        seed=1057359483639287,
force_offload=True,
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg='',
        image_embeds=wan_video_add_wan_move_tracks_80.out(0),
        model=wan_video_set_block_swap_70.out(0),
        text_embeds=wan_video_text_encode_16.out(0),
    )
    wan_video_wan_draw_wan_move_tracks_1 = node(wf, 'WanVideoWanDrawWanMoveTracks', '88',
        images=repeat_image_batch_91.out(0),
        tracks=wan_video_add_wan_move_tracks_80.out(1),
    )
    # ════ DECODE ════
    wan_video_decode_28 = node(wf, 'WanVideoDecode', '28',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        normalization='default',
        samples=wan_video_sampler_27.out(0),
        vae=wan_video_vaeloader.out(0),
    )
    # ════ OUTPUT ════
    vhs_videocombine_2 = node(wf, 'VHS_VideoCombine', '90',
        save_output=True,
        images=wan_video_wan_draw_wan_move_tracks_1.out(0),
    )
    wan_video_wan_draw_wan_move_tracks_81 = node(wf, 'WanVideoWanDrawWanMoveTracks', '81',
        images=wan_video_decode_28.out(0),
        tracks=wan_video_add_wan_move_tracks_80.out(1),
    )
    video_output_30 = node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=wan_video_wan_draw_wan_move_tracks_81.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

