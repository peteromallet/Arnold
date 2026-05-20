# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, PreviewAnimation
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoControlnet, WanVideoControlnetLoader, WanVideoDecode, WanVideoEasyCache, WanVideoEmptyEmbeds, WanVideoEnhanceAVideo, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSLG, WanVideoSampler, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_FRAMES = 5
DEFAULT_NEGATIVE = 'Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards"'
DEFAULT_PROMPT = "Close-up shot with soft lighting, focusing sharply on the lower half of a young woman's face. Her lips are slightly parted as she blows an enormous bubblegum bubble. The bubble is semi-transparent, shimmering gently under the light, and surprisingly contains a miniature aquarium inside, where two orange-and-white goldfish slowly swim, their fins delicately fluttering as if in an aquatic universe. The background is a pure light blue color."
DEFAULT_SEED = 47
DEVICE = 'cpu'
GUIDE_STRENGTH = 5
KEEP_PROPORTION = 'stretch'
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'Wan2_2_VAE_bf16.safetensors'
MODEL_NAME_3 = 'wan2.2-ti2v-5b-controlnet-depth-v1/diffusion_pytorch_model.safetensors'
MODEL_NAME_4 = 'Wan2_2-TI2V-5B-FastWanFullAttn_bf16.safetensors'
UPSCALE_METHOD = 'nearest-exact'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_video_controlnet',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['Wan2_2_VAE_bf16.safetensors', 'umt5-xxl-enc-bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2', 'PreviewAnimation'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoDecode', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='WanVideoWrapper 2.2 5B text-to-video ControlNet',
    smoke_resolution='256x256x5_frames',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_t2v_controlnet.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
            _id='11',
            model_name=MODEL_NAME,
        )
        wf.metadata.setdefault('id_map', {})['loadwanvideot5textencoder'] = loadwanvideot5textencoder.node.id

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoexperimentalargs = WanVideoExperimentalArgs(
            _id='90',
            widget_0='',
            widget_1=True,
            widget_2=False,
            widget_3=0,
            widget_4=False,
            widget_5=1,
            widget_6=1.25,
            widget_7=20,
            widget_8=True,
            widget_9=0,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoexperimentalargs'] = wanvideoexperimentalargs.node.id

        wanvideoslg = WanVideoSLG(
            _id='91',
            widget_0='7,8,9',
            widget_1=0.1,
            widget_2=0.7,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoslg'] = wanvideoslg.node.id

        wanvideoeasycache = WanVideoEasyCache(
            _id='94',
            widget_0=0.015,
            widget_1=10,
            widget_2=-1,
            widget_3='offload_device',
        )
        wf.metadata.setdefault('id_map', {})['wanvideoeasycache'] = wanvideoeasycache.node.id

        wanvideocontrolnetloader = WanVideoControlnetLoader(
            _id='103',
            widget_0=MODEL_NAME_3,
            widget_1='bf16',
            widget_2='disabled',
            widget_3='main_device',
        )
        wf.metadata.setdefault('id_map', {})['wanvideocontrolnetloader'] = wanvideocontrolnetloader.node.id

        wanvideoenhanceavideo = WanVideoEnhanceAVideo(
            _id='107',
            widget_0=2,
            widget_1=0,
            widget_2=1,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoenhanceavideo'] = wanvideoenhanceavideo.node.id

        intconstant = INTConstant(_id='113', value=121)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        intconstant_2 = INTConstant(_id='114', value=704)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        intconstant_3 = INTConstant(_id='115', value=1280)
        wf.metadata.setdefault('id_map', {})['intconstant_3'] = intconstant_3.node.id
        wanvideomodelloader = WanVideoModelLoader(
            _id='22',
            model=MODEL_NAME_4,
            base_precision='fp16',
            compile_args=wanvideotorchcompilesettings,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        vhs_loadvideo = VHS_LoadVideo(
            _id='98',
            video='wolf_interpolated.mp4',
            frame_load_cap=intconstant,
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideo'] = vhs_loadvideo.node.id

        wanvideoemptyembeds = WanVideoEmptyEmbeds(
            _id='106',
            num_frames=DEFAULT_FRAMES,
            widget_0=256,
            widget_1=256,
            widget_2=5,
            height=intconstant_2,
            width=intconstant_3,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoemptyembeds'] = wanvideoemptyembeds.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='101',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=vhs_loadvideo.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        midas_depthmappreprocessor = raw_call(wf, 'MiDaS-DepthMapPreprocessor', '104',
            widget_0=6.28318530718,
            widget_1=0.1,
            widget_2=512,
            image=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['midas_depthmappreprocessor'] = midas_depthmappreprocessor.node.id

        imageresizekjv2_2 = ImageResizeKJv2(
            _id='109',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=midas_depthmappreprocessor.out(0),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_2'] = imageresizekjv2_2.node.id

        wanvideocontrolnet = WanVideoControlnet(
            _id='105',
            widget_0=1,
            widget_1=3,
            widget_2=0,
            widget_3=1,
            control_images=imageresizekjv2_2.out('IMAGE'),
            controlnet=wanvideocontrolnetloader,
            model=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideocontrolnet'] = wanvideocontrolnet.node.id

        previewanimation = PreviewAnimation(
            _id='112',
            widget_0=24,
            images=imageresizekjv2_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['previewanimation'] = previewanimation.node.id

        wanvideotextencode = WanVideoTextEncode(
            _id='16',
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            model_to_offload=wanvideocontrolnet,
            t5=loadwanvideot5textencoder,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencode'] = wanvideotextencode.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            steps=1,
            cfg=GUIDE_STRENGTH,
            shift=8,
            seed=DEFAULT_SEED,
            scheduler='flowmatch_pusa',
            batched_cfg='',
            add_noise_to_samples='',
            cache_args=wanvideoeasycache,
            experimental_args=wanvideoexperimentalargs,
            feta_args=wanvideoenhanceavideo,
            image_embeds=wanvideoemptyembeds,
            model=wanvideocontrolnet,
            slg_args=wanvideoslg,
            text_embeds=wanvideotextencode,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideodecode = WanVideoDecode(
            _id='28',
            normalization='default',
            samples=wanvideosampler.out('SAMPLES'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(_id='92', images=wanvideodecode)
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

