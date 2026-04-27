# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [{'name': 'qwen_0.6b_ace15.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'qwen_4b_ace15.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'ace_1.5_vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'acestep_v1.5_turbo.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_turbo.safetensors',
                   'subdir': 'diffusion_models'}],
 'unbound_inputs': {'seed': 3020},
 'ready_template': 'audio/ace_step_1_5_t2a_song',
 'workflow_template': 'ace_step_1_5_t2a_song',
 'capability': 'text_to_audio_song',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/audio/ace_step_1_5_t2a_song.json',
 'coverage_tier': 'required',
 'approach': 'ACE-Step 1.5 text-to-audio song generation',
 'runtime_note': 'Official subgraph materialized to API-shaped nodes for VibeComfy smoke execution.',
 'discord_signal': None,
 'smoke_duration_seconds': 2,
 'subgraph_materialized': True}

READY_REQUIREMENTS = {'models': [{'name': 'qwen_0.6b_ace15.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'qwen_4b_ace15.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'ace_1.5_vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors',
             'subdir': 'vae'},
            {'name': 'acestep_v1.5_turbo.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_turbo.safetensors',
             'subdir': 'diffusion_models'}],
 'custom_nodes': ['EmptyAceStep1', 'TextEncodeAceStepAudio1']}


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

    dualcliploader = _node(wf, 'DualCLIPLoader', '105',
        clip_name1='qwen_0.6b_ace15.safetensors',
        clip_name2='qwen_4b_ace15.safetensors',
        type='ace',
        device='default',
    )
    vaeloader = _node(wf, 'VAELoader', '106',
        vae_name='ace_1.5_vae.safetensors',
    )
    emptyacestep1_5latentaudio = _node(wf, 'EmptyAceStep1.5LatentAudio', '122',
        batch_size=1,
        seconds=2,
    )
    unetloader = _node(wf, 'UNETLoader', '125',
        unet_name='acestep_v1.5_turbo.safetensors',
        weight_dtype='default',
    )
    modelsamplingauraflow = _node(wf, 'ModelSamplingAuraFlow', '78',
        shift=3,
        model=unetloader.out(0),
    )
    textencodeacestepaudio1_5 = _node(wf, 'TextEncodeAceStepAudio1.5', '124',
        bpm=120,
        cfg_scale=1.5,
        duration=2,
        generate_audio_codes=True,
        keyscale='E minor',
        language='en',
        lyrics='Verse\nTiny signal in the night.',
        min_p=0.9,
        seed=561594583201063,
        tags='synthwave, short instrumental',
        temperature=0,
        timesignature='4',
        top_k=0,
        top_p=0.85,
        clip=dualcliploader.out(0),
    )
    conditioningzeroout = _node(wf, 'ConditioningZeroOut', '47',
        conditioning=textencodeacestepaudio1_5.out(0),
    )
    ksampler = _node(wf, 'KSampler', '3',
        seed=561594583201063,
        steps=1,
        cfg=1,
        sampler_name='euler',
        scheduler='simple',
        denoise=1,
        latent_image=emptyacestep1_5latentaudio.out(0),
        model=modelsamplingauraflow.out(0),
        negative=conditioningzeroout.out(0),
        positive=textencodeacestepaudio1_5.out(0),
    )
    vaedecodeaudio = _node(wf, 'VAEDecodeAudio', '123',
        samples=ksampler.out(0),
        vae=vaeloader.out(0),
    )
    saveaudiomp3 = _node(wf, 'SaveAudioMP3', '59',
        filename_prefix='audio/vibecomfy_ace_step_smoke',
        quality='V0',
        audio=vaedecodeaudio.out(0),
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

