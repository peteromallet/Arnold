"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any

from vibecomfy.templates import node
from vibecomfy.workflow import VibeWorkflow

_UNSET = object()

def Qwen3AudioCompare(
    wf: VibeWorkflow,
    *,
    reference_audio: Any,
    generated_audio: Any,
    speaker_encoder_model: Any = 'Qwen/Qwen3-TTS-12Hz-0.6B-Base',
    local_model_path: Any = '',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3AudioCompare
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: report
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['reference_audio'] = reference_audio
    _kwargs['generated_audio'] = generated_audio
    _kwargs['speaker_encoder_model'] = speaker_encoder_model
    _kwargs['local_model_path'] = local_model_path
    _kwargs.update(_extras)
    return node(wf, 'Qwen3AudioCompare', pass_raw=pass_raw, **_kwargs)

def Qwen3CustomVoice(
    wf: VibeWorkflow,
    *,
    model: Any,
    text: Any,
    language: Any = 'Auto',
    speaker: Any = 'Vivian',
    seed: Any = 42,
    instruct: Any = '',
    custom_speaker_name: Any = '',
    max_new_tokens: Any = 2048,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3CustomVoice
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['text'] = text
    _kwargs['language'] = language
    _kwargs['speaker'] = speaker
    _kwargs['seed'] = seed
    _kwargs['instruct'] = instruct
    _kwargs['custom_speaker_name'] = custom_speaker_name
    _kwargs['max_new_tokens'] = max_new_tokens
    _kwargs.update(_extras)
    return node(wf, 'Qwen3CustomVoice', pass_raw=pass_raw, **_kwargs)

def Qwen3DataPrep(
    wf: VibeWorkflow,
    *,
    jsonl_path: Any = '',
    tokenizer_repo: Any = 'Qwen/Qwen3-TTS-Tokenizer-12Hz',
    source: Any = 'HuggingFace',
    batch_size: Any = 16,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3DataPrep
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: processed_jsonl_path
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['jsonl_path'] = jsonl_path
    _kwargs['tokenizer_repo'] = tokenizer_repo
    _kwargs['source'] = source
    _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'Qwen3DataPrep', pass_raw=pass_raw, **_kwargs)

def Qwen3DatasetFromFolder(
    wf: VibeWorkflow,
    *,
    folder_path: Any = '',
    output_filename: Any = 'dataset.jsonl',
    ref_audio_path: Any = '',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3DatasetFromFolder
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: jsonl_path
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['folder_path'] = folder_path
    _kwargs['output_filename'] = output_filename
    _kwargs['ref_audio_path'] = ref_audio_path
    _kwargs.update(_extras)
    return node(wf, 'Qwen3DatasetFromFolder', pass_raw=pass_raw, **_kwargs)

def Qwen3FineTune(
    wf: VibeWorkflow,
    *,
    train_jsonl: Any = '',
    init_model: Any = 'Qwen/Qwen3-TTS-12Hz-1.7B-Base',
    source: Any = 'HuggingFace',
    output_dir: Any = 'output/finetuned_model',
    epochs: Any = 3,
    batch_size: Any = 2,
    lr: Any = 2e-06,
    speaker_name: Any = 'my_speaker',
    seed: Any = 42,
    resume_training: Any = False,
    log_every_steps: Any = 10,
    save_every_epochs: Any = 1,
    save_every_steps: Any = 0,
    mixed_precision: Any = 'bf16',
    gradient_accumulation: Any = 4,
    gradient_checkpointing: Any = True,
    use_8bit_optimizer: Any = True,
    weight_decay: Any = 0.01,
    max_grad_norm: Any = 1.0,
    warmup_steps: Any = 0,
    warmup_ratio: Any = 0.0,
    save_optimizer_state: Any = False,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3FineTune
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: model_path, custom_speaker_name
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['train_jsonl'] = train_jsonl
    _kwargs['init_model'] = init_model
    _kwargs['source'] = source
    _kwargs['output_dir'] = output_dir
    _kwargs['epochs'] = epochs
    _kwargs['batch_size'] = batch_size
    _kwargs['lr'] = lr
    _kwargs['speaker_name'] = speaker_name
    _kwargs['seed'] = seed
    _kwargs['resume_training'] = resume_training
    _kwargs['log_every_steps'] = log_every_steps
    _kwargs['save_every_epochs'] = save_every_epochs
    _kwargs['save_every_steps'] = save_every_steps
    _kwargs['mixed_precision'] = mixed_precision
    _kwargs['gradient_accumulation'] = gradient_accumulation
    _kwargs['gradient_checkpointing'] = gradient_checkpointing
    _kwargs['use_8bit_optimizer'] = use_8bit_optimizer
    _kwargs['weight_decay'] = weight_decay
    _kwargs['max_grad_norm'] = max_grad_norm
    _kwargs['warmup_steps'] = warmup_steps
    _kwargs['warmup_ratio'] = warmup_ratio
    _kwargs['save_optimizer_state'] = save_optimizer_state
    _kwargs.update(_extras)
    return node(wf, 'Qwen3FineTune', pass_raw=pass_raw, **_kwargs)

def Qwen3LoadPrompt(
    wf: VibeWorkflow,
    *,
    prompt_file: Any,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3LoadPrompt
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: prompt
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['prompt_file'] = prompt_file
    _kwargs.update(_extras)
    return node(wf, 'Qwen3LoadPrompt', pass_raw=pass_raw, **_kwargs)

def Qwen3Loader(
    wf: VibeWorkflow,
    *,
    repo_id: Any = 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice',
    source: Any = 'HuggingFace',
    precision: Any = 'bf16',
    attention: Any = 'auto',
    local_model_path: Any = '',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3Loader
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['repo_id'] = repo_id
    _kwargs['source'] = source
    _kwargs['precision'] = precision
    _kwargs['attention'] = attention
    _kwargs['local_model_path'] = local_model_path
    _kwargs.update(_extras)
    return node(wf, 'Qwen3Loader', pass_raw=pass_raw, **_kwargs)

def Qwen3PromptMaker(
    wf: VibeWorkflow,
    *,
    model: Any,
    ref_audio: Any,
    ref_text: Any,
    ref_audio_max_seconds: Any = 30.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3PromptMaker
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: QWEN3_PROMPT
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['ref_audio'] = ref_audio
    _kwargs['ref_text'] = ref_text
    _kwargs['ref_audio_max_seconds'] = ref_audio_max_seconds
    _kwargs.update(_extras)
    return node(wf, 'Qwen3PromptMaker', pass_raw=pass_raw, **_kwargs)

def Qwen3SavePrompt(
    wf: VibeWorkflow,
    *,
    prompt: Any,
    filename: Any = 'voice_embedding',
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3SavePrompt
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: filepath
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['prompt'] = prompt
    _kwargs['filename'] = filename
    _kwargs.update(_extras)
    return node(wf, 'Qwen3SavePrompt', pass_raw=pass_raw, **_kwargs)

def Qwen3VoiceClone(
    wf: VibeWorkflow,
    *,
    model: Any,
    text: Any,
    seed: Any = 42,
    language: Any = 'Auto',
    ref_audio: Any = _UNSET,
    ref_text: Any = _UNSET,
    prompt: Any = _UNSET,
    max_new_tokens: Any = 2048,
    ref_audio_max_seconds: Any = 30.0,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3VoiceClone
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['text'] = text
    _kwargs['seed'] = seed
    _kwargs['language'] = language
    if ref_audio is not _UNSET:
        _kwargs['ref_audio'] = ref_audio
    if ref_text is not _UNSET:
        _kwargs['ref_text'] = ref_text
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    _kwargs['max_new_tokens'] = max_new_tokens
    _kwargs['ref_audio_max_seconds'] = ref_audio_max_seconds
    _kwargs.update(_extras)
    return node(wf, 'Qwen3VoiceClone', pass_raw=pass_raw, **_kwargs)

def Qwen3VoiceDesign(
    wf: VibeWorkflow,
    *,
    model: Any,
    text: Any,
    instruct: Any,
    language: Any = 'Auto',
    seed: Any = 42,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3VoiceDesign
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    _kwargs['model'] = model
    _kwargs['text'] = text
    _kwargs['instruct'] = instruct
    _kwargs['language'] = language
    _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'Qwen3VoiceDesign', pass_raw=pass_raw, **_kwargs)

__all__ = ['Qwen3AudioCompare', 'Qwen3CustomVoice', 'Qwen3DataPrep', 'Qwen3DatasetFromFolder', 'Qwen3FineTune', 'Qwen3LoadPrompt', 'Qwen3Loader', 'Qwen3PromptMaker', 'Qwen3SavePrompt', 'Qwen3VoiceClone', 'Qwen3VoiceDesign']
