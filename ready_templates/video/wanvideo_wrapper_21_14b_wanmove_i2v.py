# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPVisionLoader, LoadImage, RepeatImageBatch
from vibecomfy.nodes.kjnodes import ImageResizeKJv2, SplineEditor
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoAddWanMoveTracks, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoImageToVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader, WanVideoWanDrawWanMoveTracks


DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 1057359483639287
GUIDE_STRENGTH = 1
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\WanMove\\Wan21-WanMove_fp8_scaled_e4m3fn_KJ.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_4 = 'clip_vision_h.safetensors'
MODEL_NAME_5 = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
WIDGET_1 = 'fixed'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='motion_track_i2v',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoImageToVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='WanMove image-to-video motion track',
    smoke_resolution='256x256x5_frames',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_wanmove_i2v.json'},
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
            base_precision='fp16',
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideovaeloader = WanVideoVAELoader(
            _id='38',
            model_name=MODEL_NAME_3,
            widget_2=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id

        wanvideoblockswap = WanVideoBlockSwap(
            _id='39',
            blocks_to_swap=25,
            use_non_blocking=True,
            prefetch_blocks=1,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

        # Inputs
        loadimage = LoadImage(
            _id='58',
            image='oldman_upscaled.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        # Loaders
        clipvisionloader = CLIPVisionLoader(_id='59', clip_name=MODEL_NAME_4)
        wf.metadata.setdefault('id_map', {})['clipvisionloader'] = clipvisionloader.node.id
        wanvideoloraselect = WanVideoLoraSelect(
            _id='69',
            lora=MODEL_NAME_5,
            merge_loras=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselect'] = wanvideoloraselect.node.id

        primitivenode = raw_call(wf, 'PrimitiveNode', '85',
            widget_0=81,
            widget_1=WIDGET_1,
        )
        wf.metadata.setdefault('id_map', {})['primitivenode'] = primitivenode.node.id

        primitivenode_2 = raw_call(wf, 'PrimitiveNode', '86',
            widget_0=640,
            widget_1=WIDGET_1,
        )
        wf.metadata.setdefault('id_map', {})['primitivenode_2'] = primitivenode_2.node.id

        primitivenode_3 = raw_call(wf, 'PrimitiveNode', '87',
            widget_0=640,
            widget_1=WIDGET_1,
        )
        wf.metadata.setdefault('id_map', {})['primitivenode_3'] = primitivenode_3.node.id

        wanvideotextencode = WanVideoTextEncode(
            _id='16',
            positive_prompt='video of an old man',
            negative_prompt=DEFAULT_NEGATIVE,
            use_disk_cache=True,
            model_to_offload=wanvideomodelloader,
            t5=loadwanvideot5textencoder,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencode'] = wanvideotextencode.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='68',
            upscale_method='lanczos',
            keep_proportion='crop',
            divisible_by=16,
            device='cpu',
            width=primitivenode_2.out(0),
            height=primitivenode_3.out(0),
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        wanvideosetloras = WanVideoSetLoRAs(
            _id='75',
            lora=wanvideoloraselect,
            model=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetloras'] = wanvideosetloras.node.id

        wanvideoclipvisionencode = WanVideoClipVisionEncode(
            _id='65',
            ratio=0.2,
            clip_vision=clipvisionloader,
            image_1=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoclipvisionencode'] = wanvideoclipvisionencode.node.id

        wanvideosetblockswap = WanVideoSetBlockSwap(
            _id='70',
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap'] = wanvideosetblockswap.node.id

        splineeditor = SplineEditor(
            _id='77',
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
            bg_image=imageresizekjv2.out('IMAGE'),
            mask_height=primitivenode_3.out(0),
            mask_width=primitivenode_2.out(0),
            points_to_sample=primitivenode.out(0),
            _outputs=('MASK', 'COORD_STR', 'FLOAT', 'COUNT', 'NORMALIZED_STR'),
        )
        wf.metadata.setdefault('id_map', {})['splineeditor'] = splineeditor.node.id

        repeatimagebatch = RepeatImageBatch(
            _id='91',
            widget_0=81,
            amount=primitivenode.out(0),
            image=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['repeatimagebatch'] = repeatimagebatch.node.id

        wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
            _id='63',
            fun_or_fl2v_model=False,
            widget_9=0,
            width=imageresizekjv2.out('WIDTH'),
            height=imageresizekjv2.out('HEIGHT'),
            num_frames=splineeditor.out('COUNT'),
            clip_embeds=wanvideoclipvisionencode,
            start_image=imageresizekjv2.out('IMAGE'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoimagetovideoencode'] = wanvideoimagetovideoencode.node.id

        wanvideoaddwanmovetracks = WanVideoAddWanMoveTracks(
            _id='80',
            widget_0=1,
            image_embeds=wanvideoimagetovideoencode,
            track_coords=splineeditor.out('COORD_STR'),
            _outputs=('IMAGE_EMBEDS', 'TRACKS'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoaddwanmovetracks'] = wanvideoaddwanmovetracks.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            steps=1,
            cfg=GUIDE_STRENGTH,
            seed=DEFAULT_SEED,
            scheduler='dpm++_sde',
            batched_cfg='',
            image_embeds=wanvideoaddwanmovetracks.out('IMAGE_EMBEDS'),
            model=wanvideosetblockswap,
            text_embeds=wanvideotextencode,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideowandrawwanmovetracks_2 = WanVideoWanDrawWanMoveTracks(
            _id='88',
            images=repeatimagebatch,
            tracks=wanvideoaddwanmovetracks.out('TRACKS'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideowandrawwanmovetracks_2'] = wanvideowandrawwanmovetracks_2.node.id

        wanvideodecode = WanVideoDecode(
            _id='28',
            normalization='default',
            samples=wanvideosampler.out('SAMPLES'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        # Outputs
        vhs_videocombine_2 = VHS_VideoCombine(
            _id='90',
            images=wanvideowandrawwanmovetracks_2,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_2'] = vhs_videocombine_2.node.id

        wanvideowandrawwanmovetracks = WanVideoWanDrawWanMoveTracks(
            _id='81',
            images=wanvideodecode,
            tracks=wanvideoaddwanmovetracks.out('TRACKS'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideowandrawwanmovetracks'] = wanvideowandrawwanmovetracks.node.id

        vhs_videocombine = VHS_VideoCombine(
            _id='30',
            images=wanvideowandrawwanmovetracks,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

