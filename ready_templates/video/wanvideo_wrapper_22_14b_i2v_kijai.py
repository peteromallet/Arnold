# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, LoadImage
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import CreateCFGScheduleFloatList, LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoImageToVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoVAELoader


ADD_NOISE_TO_SAMPLES = ''
BASE_PRECISION = 'fp16'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'old man gets up and jumps into the lake'
DEFAULT_PROMPT_2 = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_3 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 43
GUIDE_STRENGTH = 1
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\2_2\\Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_4 = 'umt5_xxl_fp16.safetensors'
MODEL_NAME_5 = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME_6 = 'WanVideo\\2_2\\Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'
QUANTIZATION = 'fp8_e4m3fn_scaled'
SCHEDULER = 'dpm++_sde'


MODELS = {
    'wan2_2_i2v_a14b_high_fp8_e4m3fn_scaled_kj': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', subdir='checkpoints'),
    'wan2_2_i2v_a14b_low_fp8_e4m3fn_scaled_kj': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', subdir='checkpoints'),
    'wan2_1_vae_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors', subdir='checkpoints'),
    'umt5_xxl_enc_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors', subdir='checkpoints'),
    'umt5_xxl_fp16': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors', subdir='checkpoints'),
    'lightx2v_i2v_14b_480p_cfg_step_distill_rank64_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', subdir='checkpoints'),
}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT_2),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
    'width': InputSpec(node=ref('imageresizekjv2'), field='width', default=720),
    'height': InputSpec(node=ref('imageresizekjv2'), field='height', default=720),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['CreateCFGScheduleFloatList', 'LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoImageToVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='Kijai WanVideoWrapper Wan 2.2 A14B I2V high/low two-phase workflow with Lightx2v LoRA',
    smoke_resolution='832x480x81_frames',
    runtime_note='Worker scratchpads patch image, prompt, seed, resolution, frame count, and force VHS output saving.',
    source_url='https://raw.githubusercontent.com/kijai/ComfyUI-WanVideoWrapper/main/example_workflows/wanvideo_2_2_I2V_A14B_example_WIP.json',
    provenance={'source_workflow': 'ready_templates/video/wanvideo_wrapper_22_14b_i2v_kijai.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
            _id='11',
            model_name=MODEL_NAME,
        )
        wf.metadata.setdefault('id_map', {})['loadwanvideot5textencoder'] = loadwanvideot5textencoder.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='22',
            model=MODEL_NAME_2,
            base_precision=BASE_PRECISION,
            quantization=QUANTIZATION,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoblockswap = WanVideoBlockSwap(_id='39', vace_blocks_to_swap=1)
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id
        # Loaders
        cliploader = CLIPLoader(_id='48', clip_name=MODEL_NAME_4, type_='wan')
        wf.metadata.setdefault('id_map', {})['cliploader'] = cliploader.node.id
        wanvideoloraselect = WanVideoLoraSelect(
            _id='56',
            lora=MODEL_NAME_5,
            strength=3,
            merge_loras=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselect'] = wanvideoloraselect.node.id

        # Inputs
        loadimage = LoadImage(
            _id='67',
            image='oldman_upscaled.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        wanvideomodelloader_2 = WanVideoModelLoader(
            _id='71',
            model=MODEL_NAME_6,
            base_precision=BASE_PRECISION,
            quantization=QUANTIZATION,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader_2'] = wanvideomodelloader_2.node.id

        intconstant = INTConstant(_id='91', value=3)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        intconstant_2 = INTConstant(_id='94', value=6)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        wanvideoloraselect_2 = WanVideoLoraSelect(
            _id='97',
            lora=MODEL_NAME_5,
            merge_loras=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselect_2'] = wanvideoloraselect_2.node.id

        wanvideotextencode = WanVideoTextEncode(
            _id='16',
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            t5=loadwanvideot5textencoder,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencode'] = wanvideotextencode.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='49',
            text=DEFAULT_PROMPT_2,
            clip=cliploader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        cliptextencode_2 = CLIPTextEncode(
            _id='50',
            text=DEFAULT_PROMPT_3,
            clip=cliploader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='68',
            width=720,
            height=720,
            upscale_method='lanczos',
            keep_proportion='crop',
            divisible_by=32,
            device='cpu',
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        wanvideosetblockswap = WanVideoSetBlockSwap(
            _id='92',
            block_swap_args=wanvideoblockswap,
            model=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap'] = wanvideosetblockswap.node.id

        wanvideosetblockswap_2 = WanVideoSetBlockSwap(
            _id='93',
            block_swap_args=wanvideoblockswap,
            model=wanvideomodelloader_2,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap_2'] = wanvideosetblockswap_2.node.id

        createcfgschedulefloatlist = CreateCFGScheduleFloatList(
            _id='95',
            cfg_scale_start=2,
            cfg_scale_end=2,
            end_percent=0.01,
            steps=intconstant_2,
        )
        wf.metadata.setdefault('id_map', {})['createcfgschedulefloatlist'] = createcfgschedulefloatlist.node.id

        wanvideotextembedbridge = WanVideoTextEmbedBridge(
            _id='46',
            negative=cliptextencode_2,
            positive=cliptextencode,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextembedbridge'] = wanvideotextembedbridge.node.id

        wanvideosetloras = WanVideoSetLoRAs(
            _id='79',
            lora=wanvideoloraselect_2,
            model=wanvideosetblockswap_2,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetloras'] = wanvideosetloras.node.id

        wanvideosetloras_2 = WanVideoSetLoRAs(
            _id='80',
            lora=wanvideoloraselect,
            model=wanvideosetblockswap,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetloras_2'] = wanvideosetloras_2.node.id

        wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
            _id='89',
            fun_or_fl2v_model=False,
            width=imageresizekjv2.out('WIDTH'),
            height=imageresizekjv2.out('HEIGHT'),
            start_image=imageresizekjv2.out('IMAGE'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoimagetovideoencode'] = wanvideoimagetovideoencode.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            shift=8,
            seed=DEFAULT_SEED,
            scheduler=SCHEDULER,
            add_noise_to_samples=ADD_NOISE_TO_SAMPLES,
            steps=intconstant_2,
            cfg=createcfgschedulefloatlist,
            end_step=intconstant,
            image_embeds=wanvideoimagetovideoencode,
            model=wanvideosetloras_2,
            text_embeds=wanvideotextencode,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideosampler_2 = WanVideoSampler(
            _id='90',
            cfg=GUIDE_STRENGTH,
            shift=8,
            seed=DEFAULT_SEED,
            scheduler=SCHEDULER,
            add_noise_to_samples=ADD_NOISE_TO_SAMPLES,
            steps=intconstant_2,
            start_step=intconstant,
            image_embeds=wanvideoimagetovideoencode,
            model=wanvideosetloras,
            samples=wanvideosampler.out('SAMPLES'),
            text_embeds=wanvideotextencode,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler_2'] = wanvideosampler_2.node.id

        wanvideodecode = WanVideoDecode(
            _id='28',
            normalization='default',
            samples=wanvideosampler_2.out('SAMPLES'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        getimagesizeandcount = GetImageSizeAndCount(
            _id='69',
            image=wanvideodecode,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='60',
            frame_rate=16,
            filename_prefix='WanVideo2_2_I2V',
            format='video/h264-mp4',
            save_output=False,
            crf=19,
            pix_fmt='yuv420p',
            save_metadata=True,
            trim_to_audio=False,
            videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_2_I2V_00006.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_2_I2V_00006.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_2_I2V_00006.png'}, 'paused': False},
            images=getimagesizeandcount.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_2_I2V')

