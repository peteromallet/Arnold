# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, LoadImage, PreviewImage
from vibecomfy.nodes.kjnodes import CameraPoseVisualizer, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoExperimentalArgs, WanVideoFunCameraEmbeds, WanVideoImageToVideoEncode, WanVideoModelLoader, WanVideoSampler, WanVideoTeaCache, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'high quality video of an old man'
DEFAULT_PROMPT_2 = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_3 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 43
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\Wan2.1-Fun-V1.1-1.3B-Control-Camera.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_4 = 'umt5_xxl_fp8_e4m3fn_scaled.safetensors'
WIDGET_0 = 'VAE'
WIDGET_0_2 = 'InputImage'
WIDGET_0_3 = ''


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT_2),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
    'width': InputSpec(node=ref('imageresizekjv2'), field='width', default=256),
    'height': InputSpec(node=ref('imageresizekjv2'), field='height', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='camera_control_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp8_e4m3fn_scaled.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoExperimentalArgs', 'WanVideoImageToVideoEncode', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='WanVideoFun camera-control workflow',
    smoke_resolution='256x256x5_frames',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control_camera.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
            _id='11',
            model_name=MODEL_NAME,
        )
        wf.metadata.setdefault('id_map', {})['loadwanvideot5textencoder'] = loadwanvideot5textencoder.node.id

        wanvideomodelloader = WanVideoModelLoader(_id='22', model=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id
        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoblockswap = WanVideoBlockSwap(
            _id='39',
            blocks_to_swap=15,
            use_non_blocking=True,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

        # Loaders
        cliploader = CLIPLoader(_id='48', clip_name=MODEL_NAME_4, type_='wan')
        wf.metadata.setdefault('id_map', {})['cliploader'] = cliploader.node.id
        wanvideoteacache = WanVideoTeaCache(
            _id='52',
            widget_0=0.08,
            widget_1=6,
            widget_2=-1,
            widget_3='offload_device',
            widget_4='true',
            widget_5='e0',
        )
        wf.metadata.setdefault('id_map', {})['wanvideoteacache'] = wanvideoteacache.node.id

        # Inputs
        loadimage = LoadImage(
            _id='58',
            image='oldman_upscaled.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        reroute = raw_call(wf, 'Reroute', '80')
        wf.metadata.setdefault('id_map', {})['reroute'] = reroute.node.id
        getnode = raw_call(wf, 'GetNode', '85', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        getnode_2 = raw_call(wf, 'GetNode', '86', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        getnode_3 = raw_call(wf, 'GetNode', '89', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        wanvideoexperimentalargs = WanVideoExperimentalArgs(
            _id='90',
            widget_0=WIDGET_0_3,
            widget_1=True,
            widget_2=False,
            widget_3=0,
            widget_4=True,
            widget_5=1,
            widget_6=1.25,
            widget_7=20,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoexperimentalargs'] = wanvideoexperimentalargs.node.id

        intconstant = INTConstant(_id='105', value=81)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        wanvideotextencode = WanVideoTextEncode(
            _id='16',
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            model_to_offload=wanvideomodelloader,
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

        setnode = raw_call(wf, 'SetNode', '83',
            widget_0=WIDGET_0,
            WANVAE=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='97',
            width=256,
            height=256,
            upscale_method='lanczos',
            keep_proportion='crop',
            divisible_by=16,
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        ade_cameraposebasic = raw_call(wf, 'ADE_CameraPoseBasic', '99',
            widget_0='Zoom Out',
            widget_1=0.1,
            widget_2=40,
            frame_length=intconstant,
        )
        wf.metadata.setdefault('id_map', {})['ade_cameraposebasic'] = ade_cameraposebasic.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            steps=1,
            seed=DEFAULT_SEED,
            batched_cfg='',
            start_step='',
            cache_args=wanvideoteacache,
            experimental_args=wanvideoexperimentalargs,
            image_embeds=reroute.out(0),
            model=wanvideomodelloader,
            text_embeds=wanvideotextencode,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideotextembedbridge = WanVideoTextEmbedBridge(
            _id='46',
            negative=cliptextencode_2,
            positive=cliptextencode,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextembedbridge'] = wanvideotextembedbridge.node.id

        setnode_2 = raw_call(wf, 'SetNode', '98',
            widget_0=WIDGET_0_2,
            IMAGE=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

        cameraposevisualizer = CameraPoseVisualizer(
            _id='102',
            widget_0=WIDGET_0_3,
            widget_1=0.2,
            widget_2=0.3,
            widget_3=1,
            widget_4=False,
            widget_5=True,
            widget_6=False,
            cameractrl_poses=ade_cameraposebasic.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cameraposevisualizer'] = cameraposevisualizer.node.id

        wanvideofuncameraembeds = WanVideoFunCameraEmbeds(
            _id='104',
            widget_0=832,
            widget_1=480,
            widget_2=1,
            widget_3=0,
            widget_4=1,
            height=imageresizekjv2.out('HEIGHT'),
            poses=ade_cameraposebasic.out(0),
            width=imageresizekjv2.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideofuncameraembeds'] = wanvideofuncameraembeds.node.id

        wanvideodecode = WanVideoDecode(
            _id='28',
            samples=wanvideosampler.out('SAMPLES'),
            vae=getnode_2.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
            _id='63',
            noise_aug_strength=0.03,
            tiled_vae=True,
            width=imageresizekjv2.out('WIDTH'),
            height=imageresizekjv2.out('HEIGHT'),
            num_frames=intconstant,
            control_embeds=wanvideofuncameraembeds,
            start_image=setnode_2.out(0),
            vae=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoimagetovideoencode'] = wanvideoimagetovideoencode.node.id

        # Outputs
        previewimage = PreviewImage(_id='103', images=cameraposevisualizer)
        wf.metadata.setdefault('id_map', {})['previewimage'] = previewimage.node.id
        imageconcatmulti = ImageConcatMulti(
            _id='87',
            inputcount=3,
            direction='left',
            match_image_size=True,
            unused_3=None,
            image_1=wanvideodecode,
            image_2=getnode_3.out(0),
            image_3=cameraposevisualizer,
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti'] = imageconcatmulti.node.id

        vhs_videocombine = VHS_VideoCombine(_id='30', images=imageconcatmulti)
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

