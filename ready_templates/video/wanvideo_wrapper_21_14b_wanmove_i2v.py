# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4441},
 'ready_template': 'video/wanvideo_wrapper_21_14b_wanmove_i2v',
 'workflow_template': 'wanvideo_wrapper_21_14b_wanmove_i2v',
 'capability': 'motion_track_i2v',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_wanmove_i2v.json',
 'coverage_tier': 'supplemental',
 'approach': 'WanMove image-to-video motion track',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames'}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'],
 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes',
                       'source': 'git',
                       'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df',
                       'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'},
                      {'slug': 'ComfyUI-VideoHelperSuite',
                       'source': 'git',
                       'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'},
                      {'slug': 'ComfyUI-WanVideoWrapper',
                       'source': 'git',
                       'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c',
                       'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]}


def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    loadwanvideot5textencoder = _node(wf, 'LoadWanVideoT5TextEncoder', '11',
        widget_0='umt5-xxl-enc-bf16.safetensors',
        widget_1='bf16',
        widget_2='offload_device',
        widget_3='disabled',
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\WanMove\\Wan21-WanMove_fp8_scaled_e4m3fn_KJ.safetensors',
        widget_1='fp16',
        widget_2='disabled',
        widget_3='offload_device',
        widget_4='sdpa',
        widget_5='default',
    )
    wanvideotorchcompilesettings = _node(wf, 'WanVideoTorchCompileSettings', '35',
        widget_0='inductor',
        widget_1=False,
        widget_2='default',
        widget_3=False,
        widget_4=64,
        widget_5=True,
        widget_6=128,
        widget_7=False,
        widget_8=False,
    )
    wanvideovaeloader = _node(wf, 'WanVideoVAELoader', '38',
        widget_0='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        widget_1='bf16',
        widget_2=False,
    )
    wanvideoblockswap = _node(wf, 'WanVideoBlockSwap', '39',
        widget_0=25,
        widget_1=False,
        widget_2=False,
        widget_3=True,
        widget_4=0,
        widget_5=1,
        widget_6=False,
    )
    loadimage = _node(wf, 'LoadImage', '58',
        image='oldman_upscaled.png',
        widget_1='image',
    )
    clipvisionloader = _node(wf, 'CLIPVisionLoader', '59',
        widget_0='clip_vision_h.safetensors',
    )
    wanvideoloraselect = _node(wf, 'WanVideoLoraSelect', '69',
        widget_0='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        widget_1=1,
        widget_2=False,
        widget_3=False,
    )
    primitivenode = _node(wf, 'PrimitiveNode', '85',
        widget_0=81,
        widget_1='fixed',
    )
    primitivenode_2 = _node(wf, 'PrimitiveNode', '86',
        widget_0=640,
        widget_1='fixed',
    )
    primitivenode_3 = _node(wf, 'PrimitiveNode', '87',
        widget_0=640,
        widget_1='fixed',
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        widget_0='video of an old man',
        widget_1='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        widget_2=True,
        widget_3=True,
        widget_4='gpu',
        model_to_offload=wanvideomodelloader.out(0),
        t5=loadwanvideot5textencoder.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '68',
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=16,
        widget_7='cpu',
        widget_8='<tr><td>Output: </td><td><b>1</b> x <b>640</b> x <b>640 | 4.69MB</b></td></tr>',
        height=primitivenode_3.out(0),
        image=loadimage.out(0),
        width=primitivenode_2.out(0),
    )
    wanvideosetloras = _node(wf, 'WanVideoSetLoRAs', '75',
        lora=wanvideoloraselect.out(0),
        model=wanvideomodelloader.out(0),
    )
    wanvideoclipvisionencode = _node(wf, 'WanVideoClipVisionEncode', '65',
        widget_0=1,
        widget_1=1,
        widget_2='center',
        widget_3='average',
        widget_4=True,
        widget_5=0,
        widget_6=0.20000000000000004,
        clip_vision=clipvisionloader.out(0),
        image_1=imageresizekjv2.out(0),
    )
    wanvideosetblockswap = _node(wf, 'WanVideoSetBlockSwap', '70',
        block_swap_args=wanvideoblockswap.out(0),
        model=wanvideosetloras.out(0),
    )
    splineeditor = _node(wf, 'SplineEditor', '77',
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
        bg_image=imageresizekjv2.out(0),
        mask_height=primitivenode_3.out(0),
        mask_width=primitivenode_2.out(0),
        points_to_sample=primitivenode.out(0),
    )
    repeatimagebatch = _node(wf, 'RepeatImageBatch', '91',
        widget_0=81,
        amount=primitivenode.out(0),
        image=imageresizekjv2.out(0),
    )
    wanvideoimagetovideoencode = _node(wf, 'WanVideoImageToVideoEncode', '63',
        widget_0=256,
        widget_1=256,
        widget_2=5,
        widget_3=0,
        widget_4=1,
        widget_5=1,
        widget_6=True,
        widget_7=False,
        widget_8=False,
        widget_9=0,
        clip_embeds=wanvideoclipvisionencode.out(0),
        height=imageresizekjv2.out(2),
        num_frames=splineeditor.out(3),
        start_image=imageresizekjv2.out(0),
        vae=wanvideovaeloader.out(0),
        width=imageresizekjv2.out(1),
    )
    wanvideoaddwanmovetracks = _node(wf, 'WanVideoAddWanMoveTracks', '80',
        widget_0=1,
        image_embeds=wanvideoimagetovideoencode.out(0),
        track_coords=splineeditor.out(1),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '27',
        steps=1,
        widget_0=1,
        widget_1=1,
        widget_10='comfy',
        widget_11=0,
        widget_12=-1,
        widget_13=False,
        widget_2=5,
        widget_3=1057359483639287,
        widget_4='fixed',
        widget_5=True,
        widget_6='dpm++_sde',
        widget_7=0,
        widget_8=1,
        widget_9='',
        image_embeds=wanvideoaddwanmovetracks.out(0),
        model=wanvideosetblockswap.out(0),
        text_embeds=wanvideotextencode.out(0),
    )
    wanvideowandrawwanmovetracks_2 = _node(wf, 'WanVideoWanDrawWanMoveTracks', '88',
        images=repeatimagebatch.out(0),
        tracks=wanvideoaddwanmovetracks.out(1),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '28',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5='default',
        samples=wanvideosampler.out(0),
        vae=wanvideovaeloader.out(0),
    )
    vhs_videocombine_2 = _node(wf, 'VHS_VideoCombine', '90',
        save_output=True,
        images=wanvideowandrawwanmovetracks_2.out(0),
    )
    wanvideowandrawwanmovetracks = _node(wf, 'WanVideoWanDrawWanMoveTracks', '81',
        images=wanvideodecode.out(0),
        tracks=wanvideoaddwanmovetracks.out(1),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=wanvideowandrawwanmovetracks.out(0),
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder

