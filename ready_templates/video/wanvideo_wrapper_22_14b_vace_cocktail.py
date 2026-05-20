# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import LoadImage
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import WanVideoBlockSwap, WanVideoDecode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoVACEEncode, WanVideoVACEModelSelect, WanVideoVACEStartToEndFrame, WanVideoVAELoader


BASE_PRECISION = 'fp16'
DEFAULT_NEGATIVE = 'fading, breaking, shot cuts, jumpcuts, blurry, noise, distorted'
DEFAULT_PROMPT = 'A smooth cinematic transition with consistent identity, lighting, and camera motion.'
DEFAULT_SEED = 12345
GUIDE_STRENGTH = 3.0
GUIDE_STRENGTH_2 = 1.0
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo/Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors'
MODEL_NAME_4 = 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors'
MODEL_NAME_5 = 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_6 = 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'
QUANTIZATION = 'fp8_e4m3fn_scaled'
SCHEDULER = 'euler'


MODELS = {
    'wan2_2_t2v_a14b_high_fp8_e4m3fn_scaled_kj': ModelAsset(filename='Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors', sha256='15384a1da9b5aa463464ba50a596b84f6c0929bfb72ec47df6bb48cb2e0b6f0c', hf_revision='5571ff9d81a631ee97946a703e94911d63214c44', size_bytes=15001361458, subdir='diffusion_models/WanVideo/2_2'),
    'wan2_2_t2v_a14b_low_fp8_e4m3fn_scaled_kj': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', sha256='ce74fff05e37f995a0ae845f53510e43f98b838f4e75d846eb3e2929e7f555cc', hf_revision='5571ff9d81a631ee97946a703e94911d63214c44', size_bytes=15001361458, subdir='diffusion_models/WanVideo/2_2'),
    'wan2_1_vace_module_14b_fp8_e4m3fn': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', sha256='4e251417a499fcdce54b6cddbd53d85644bcafb4e3d43a7d10c346612cb75501', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=3052113849, subdir='diffusion_models/WanVideo'),
    'lightx2v_t2v_14b_cfg_step_distill_v2_lora_rank64_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', sha256='37d49218544b9e0bfb8e831d1399f451fbc5068aff6474f42a90c928363c3573', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=630697104, subdir='loras/WanVideo/Lightx2v'),
    'wan2_1_vae_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors', sha256='1ab9a32cc2c740f6e39d80d367ce5dcc28db8c71b79b28670546b8973e9d75f9', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=253806278, subdir='vae'),
    'umt5_xxl_enc_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors', sha256='4fa971faf306cad919033d5bbe192e571dc08452f800cbf2ec3c73977c01b2cc', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=11361845464, subdir='text_encoders'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('wanvideovaeloader'), field='model_name', default=MODEL_NAME_2),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'width': InputSpec(node=ref('wanvideovaceencode'), field='width', default=832),
    'height': InputSpec(node=ref('wanvideovaceencode'), field='height', default=480),
    'image': InputSpec(node=ref('loadimage'), field='image', default='vace_start.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='vace_start.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video_vace_travel_join',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoVACEEncode', 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='832x480x81_frames',
    approach='Wan 2.2 14B VACE high/high/low cocktail with first/last frame and optional control-video conditioning',
    runtime_note='Matches Reigh Wan2GP VACE baseline shape: 81 frames, 6 Euler steps, CFG 3/1/1, flow shift 5.',
    provenance={'source_workflow': 'ready_templates/video/wanvideo_wrapper_22_14b_vace_cocktail.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        wanvideotextencodecached = WanVideoTextEncodeCached(
            _id='16',
            model_name=MODEL_NAME,
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            _outputs=('TEXT_EMBEDS', 'NEGATIVE_TEXT_EMBEDS', 'POSITIVE_PROMPT'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencodecached'] = wanvideotextencodecached.node.id

        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoblockswap = WanVideoBlockSwap(
            _id='39',
            blocks_to_swap=30,
            offload_img_emb=True,
            offload_txt_emb=True,
            use_non_blocking=True,
            vace_blocks_to_swap=8,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

        # Inputs
        loadimage = LoadImage(
            _id='64',
            image='vace_start.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        wanvideoloraselectmulti = WanVideoLoraSelectMulti(
            _id='93',
            lora_0=MODEL_NAME_3,
            merge_loras=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselectmulti'] = wanvideoloraselectmulti.node.id

        wanvideoloraselectmulti_2 = WanVideoLoraSelectMulti(
            _id='98',
            lora_0=MODEL_NAME_3,
            merge_loras=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselectmulti_2'] = wanvideoloraselectmulti_2.node.id

        loadimage_2 = LoadImage(
            _id='112',
            image='vace_end.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_2'] = loadimage_2.node.id

        vhs_loadvideo = VHS_LoadVideo(
            _id='199',
            custom_height=480,
            custom_width=832,
            force_rate=16,
            frame_load_cap=81,
            video='vace_control.mp4',
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
            **{'choose video to upload': 'image'},
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideo'] = vhs_loadvideo.node.id

        wanvideovacemodelselect = WanVideoVACEModelSelect(
            _id='224',
            vace_model=MODEL_NAME_4,
        )
        wf.metadata.setdefault('id_map', {})['wanvideovacemodelselect'] = wanvideovacemodelselect.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='22',
            model=MODEL_NAME_5,
            base_precision=BASE_PRECISION,
            quantization=QUANTIZATION,
            extra_model=wanvideovacemodelselect,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        wanvideomodelloader_2 = WanVideoModelLoader(
            _id='92',
            model=MODEL_NAME_6,
            base_precision=BASE_PRECISION,
            quantization=QUANTIZATION,
            extra_model=wanvideovacemodelselect,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader_2'] = wanvideomodelloader_2.node.id

        wanvideovacestarttoendframe = WanVideoVACEStartToEndFrame(
            _id='111',
            control_images=vhs_loadvideo.out('IMAGE'),
            end_image=loadimage_2.out('IMAGE'),
            start_image=loadimage.out('IMAGE'),
            _outputs=('IMAGES', 'MASKS'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideovacestarttoendframe'] = wanvideovacestarttoendframe.node.id

        wanvideovaceencode = WanVideoVACEEncode(
            _id='56',
            height=480,
            width=832,
            input_frames=wanvideovacestarttoendframe.out('IMAGES'),
            input_masks=wanvideovacestarttoendframe.out('MASKS'),
            ref_images=loadimage.out('IMAGE'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideovaceencode'] = wanvideovaceencode.node.id

        wanvideosetloras = WanVideoSetLoRAs(
            _id='79',
            lora=wanvideoloraselectmulti_2,
            model=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetloras'] = wanvideosetloras.node.id

        wanvideosetloras_2 = WanVideoSetLoRAs(
            _id='80',
            lora=wanvideoloraselectmulti,
            model=wanvideomodelloader_2,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetloras_2'] = wanvideosetloras_2.node.id

        wanvideosetblockswap = WanVideoSetBlockSwap(
            _id='86',
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap'] = wanvideosetblockswap.node.id

        wanvideosetblockswap_2 = WanVideoSetBlockSwap(
            _id='91',
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras_2,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap_2'] = wanvideosetblockswap_2.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            steps=6,
            cfg=GUIDE_STRENGTH,
            seed=DEFAULT_SEED,
            scheduler=SCHEDULER,
            end_step=2,
            image_embeds=wanvideovaceencode,
            model=wanvideosetblockswap,
            text_embeds=wanvideotextencodecached.out('TEXT_EMBEDS'),
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideosampler_2 = WanVideoSampler(
            _id='87',
            steps=6,
            cfg=GUIDE_STRENGTH_2,
            seed=DEFAULT_SEED,
            scheduler=SCHEDULER,
            start_step=2,
            end_step=4,
            image_embeds=wanvideovaceencode,
            model=wanvideosetblockswap,
            samples=wanvideosampler.out('SAMPLES'),
            text_embeds=wanvideotextencodecached.out('TEXT_EMBEDS'),
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler_2'] = wanvideosampler_2.node.id

        wanvideosampler_3 = WanVideoSampler(
            _id='197',
            steps=6,
            cfg=GUIDE_STRENGTH_2,
            seed=DEFAULT_SEED,
            scheduler=SCHEDULER,
            start_step=4,
            image_embeds=wanvideovaceencode,
            model=wanvideosetblockswap_2,
            samples=wanvideosampler_2.out('SAMPLES'),
            text_embeds=wanvideotextencodecached.out('TEXT_EMBEDS'),
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler_3'] = wanvideosampler_3.node.id

        wanvideodecode = WanVideoDecode(
            _id='28',
            normalization='default',
            samples=wanvideosampler_3.out('SAMPLES'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='139',
            frame_rate=16,
            filename_prefix='Wan-2-2-VACE',
            format='video/h264-mp4',
            crf=19,
            pix_fmt='yuv420p',
            save_metadata=True,
            trim_to_audio=False,
            images=wanvideodecode,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='Wan-2-2-VACE')

