# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'ready_template': 'audio/qwen3_tts_voice_design',
 'workflow_template': 'qwen3_tts_voice_design',
 'capability': 'text_to_speech_voice_design',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_design.json',
 'coverage_tier': 'supplemental',
 'approach': 'text-to-speech from a natural language voice description',
 'runtime_note': 'Voice design currently requires the 1.7B Qwen3-TTS path exposed by the custom node.',
 'discord_signal': None,
 'runtime_variant': 'qwen3-tts-smoke',
 'input_fixtures': []}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-QwenTTS'],
 'custom_node_refs': [{'slug': 'ComfyUI-QwenTTS',
                       'source': 'git',
                       'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293',
                       'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git'}]}


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

    ailab_qwen3ttsvoicedesign = _node(wf, 'AILab_Qwen3TTSVoiceDesign', '1',
        instruct='A warm narrator voice with crisp diction and a neutral studio tone.',
        language='English',
        model_size='1.7B',
        seed=3294,
        text='This is a compact Qwen voice design smoke test for reusable VibeComfy audio templates.',
        unload_models=True,
    )
    saveaudiomp3 = _node(wf, 'SaveAudioMP3', '2',
        filename_prefix='audio/qwen3_tts_voice_design',
        quality='V0',
        audio=ailab_qwen3ttsvoicedesign.out(0),
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

