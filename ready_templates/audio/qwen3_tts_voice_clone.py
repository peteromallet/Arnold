# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Text To Speech Voice Clone.

Output: unknown.

Source:  workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json

Packs:   ComfyUI-QwenTTS
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='qwen3_tts_voice_clone',
    capability='text_to_speech_voice_clone',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-QwenTTS'], 'custom_node_refs': [{'slug': 'ComfyUI-QwenTTS', 'source': 'git', 'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git'}]},
    provenance={'approach': 'reference-audio voice cloning with a bundled smoke fixture', 'runtime_variant': 'qwen3-tts-smoke', 'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json'},
    coverage_tier='supplemental',
    runtime_note='Uses workflow_corpus/input/speech_smoke.wav as the reference clip for repeatable validation.',
    input_fixtures=['workflow_corpus/input/speech_smoke.wav'],
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ LOADERS ════
    load_audio_1 = node(wf, 'LoadAudio', '1',
        audio='speech_smoke.wav',
        widget_0='speech_smoke.wav',
    )
    # ════ SAMPLING ════
    ailab__qwen3_ttsvoice_clone = node(wf, 'AILab_Qwen3TTSVoiceClone', '2',
        language='English',
        model_size='0.6B',
        reference_text='This is a short reference audio sample for workflow smoke testing.',
        seed=3189,
        target_text='This Qwen voice clone template uses a tiny bundled reference clip and runs as a reusable audio smoke test.',
        unload_models=True,
        x_vector_only=False,
        reference_audio=load_audio_1.out(0),
    )
    # ════ OUTPUT ════
    save_audio = node(wf, 'SaveAudioMP3', '3',
        filename_prefix='audio/qwen3_tts_voice_clone',
        quality='V0',
        audio=ailab__qwen3_ttsvoice_clone.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

