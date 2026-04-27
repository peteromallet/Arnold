# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'ready_template': 'audio/qwen3_tts_voice_clone',
 'workflow_template': 'qwen3_tts_voice_clone',
 'capability': 'text_to_speech_voice_clone',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json',
 'coverage_tier': 'supplemental',
 'approach': 'reference-audio voice cloning with a bundled smoke fixture',
 'runtime_note': 'Uses workflow_corpus/input/speech_smoke.wav as the reference clip for repeatable '
                 'validation.',
 'discord_signal': None,
 'runtime_variant': 'qwen3-tts-smoke',
 'input_fixtures': ['workflow_corpus/input/speech_smoke.wav']}

READY_REQUIREMENTS = {'models': [], 'custom_nodes': ['ComfyUI-QwenTTS']}


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

    loadaudio = _node(wf, 'LoadAudio', '1',
        audio='speech_smoke.wav',
        widget_0='speech_smoke.wav',
    )
    ailab_qwen3ttsvoiceclone = _node(wf, 'AILab_Qwen3TTSVoiceClone', '2',
        language='English',
        model_size='0.6B',
        reference_text='This is a short reference audio sample for workflow smoke testing.',
        seed=3189,
        target_text='This Qwen voice clone template uses a tiny bundled reference clip and runs as a reusable audio smoke test.',
        unload_models=True,
        x_vector_only=False,
        reference_audio=loadaudio.out(0),
    )
    saveaudiomp3 = _node(wf, 'SaveAudioMP3', '3',
        filename_prefix='audio/qwen3_tts_voice_clone',
        quality='V0',
        audio=ailab_qwen3ttsvoiceclone.out(0),
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

