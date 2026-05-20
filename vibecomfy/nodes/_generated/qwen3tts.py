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
    _id: str | None = None,
    reference_audio: Any = _UNSET,
    generated_audio: Any = _UNSET,
    speaker_encoder_model: Any = _UNSET,
    local_model_path: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3AudioCompare
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: report
    """
    _kwargs: dict[str, Any] = {}
    if reference_audio is not _UNSET:
        _kwargs['reference_audio'] = reference_audio
    if generated_audio is not _UNSET:
        _kwargs['generated_audio'] = generated_audio
    if speaker_encoder_model is not _UNSET:
        _kwargs['speaker_encoder_model'] = speaker_encoder_model
    if local_model_path is not _UNSET:
        _kwargs['local_model_path'] = local_model_path
    _kwargs.update(_extras)
    return node(wf, 'Qwen3AudioCompare', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3CustomVoice(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    text: Any = _UNSET,
    language: Any = _UNSET,
    speaker: Any = _UNSET,
    seed: Any = _UNSET,
    instruct: Any = _UNSET,
    custom_speaker_name: Any = _UNSET,
    max_new_tokens: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3CustomVoice
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if text is not _UNSET:
        _kwargs['text'] = text
    if language is not _UNSET:
        _kwargs['language'] = language
    if speaker is not _UNSET:
        _kwargs['speaker'] = speaker
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if custom_speaker_name is not _UNSET:
        _kwargs['custom_speaker_name'] = custom_speaker_name
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    _kwargs.update(_extras)
    return node(wf, 'Qwen3CustomVoice', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3DataPrep(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    jsonl_path: Any = _UNSET,
    tokenizer_repo: Any = _UNSET,
    source: Any = _UNSET,
    batch_size: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3DataPrep
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: processed_jsonl_path
    """
    _kwargs: dict[str, Any] = {}
    if jsonl_path is not _UNSET:
        _kwargs['jsonl_path'] = jsonl_path
    if tokenizer_repo is not _UNSET:
        _kwargs['tokenizer_repo'] = tokenizer_repo
    if source is not _UNSET:
        _kwargs['source'] = source
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    _kwargs.update(_extras)
    return node(wf, 'Qwen3DataPrep', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3DatasetFromFolder(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    folder_path: Any = _UNSET,
    output_filename: Any = _UNSET,
    ref_audio_path: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3DatasetFromFolder
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: jsonl_path
    """
    _kwargs: dict[str, Any] = {}
    if folder_path is not _UNSET:
        _kwargs['folder_path'] = folder_path
    if output_filename is not _UNSET:
        _kwargs['output_filename'] = output_filename
    if ref_audio_path is not _UNSET:
        _kwargs['ref_audio_path'] = ref_audio_path
    _kwargs.update(_extras)
    return node(wf, 'Qwen3DatasetFromFolder', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3FineTune(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    train_jsonl: Any = _UNSET,
    init_model: Any = _UNSET,
    source: Any = _UNSET,
    output_dir: Any = _UNSET,
    epochs: Any = _UNSET,
    batch_size: Any = _UNSET,
    lr: Any = _UNSET,
    speaker_name: Any = _UNSET,
    seed: Any = _UNSET,
    resume_training: Any = _UNSET,
    log_every_steps: Any = _UNSET,
    save_every_epochs: Any = _UNSET,
    save_every_steps: Any = _UNSET,
    mixed_precision: Any = _UNSET,
    gradient_accumulation: Any = _UNSET,
    gradient_checkpointing: Any = _UNSET,
    use_8bit_optimizer: Any = _UNSET,
    weight_decay: Any = _UNSET,
    max_grad_norm: Any = _UNSET,
    warmup_steps: Any = _UNSET,
    warmup_ratio: Any = _UNSET,
    save_optimizer_state: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3FineTune
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: model_path, custom_speaker_name
    """
    _kwargs: dict[str, Any] = {}
    if train_jsonl is not _UNSET:
        _kwargs['train_jsonl'] = train_jsonl
    if init_model is not _UNSET:
        _kwargs['init_model'] = init_model
    if source is not _UNSET:
        _kwargs['source'] = source
    if output_dir is not _UNSET:
        _kwargs['output_dir'] = output_dir
    if epochs is not _UNSET:
        _kwargs['epochs'] = epochs
    if batch_size is not _UNSET:
        _kwargs['batch_size'] = batch_size
    if lr is not _UNSET:
        _kwargs['lr'] = lr
    if speaker_name is not _UNSET:
        _kwargs['speaker_name'] = speaker_name
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if resume_training is not _UNSET:
        _kwargs['resume_training'] = resume_training
    if log_every_steps is not _UNSET:
        _kwargs['log_every_steps'] = log_every_steps
    if save_every_epochs is not _UNSET:
        _kwargs['save_every_epochs'] = save_every_epochs
    if save_every_steps is not _UNSET:
        _kwargs['save_every_steps'] = save_every_steps
    if mixed_precision is not _UNSET:
        _kwargs['mixed_precision'] = mixed_precision
    if gradient_accumulation is not _UNSET:
        _kwargs['gradient_accumulation'] = gradient_accumulation
    if gradient_checkpointing is not _UNSET:
        _kwargs['gradient_checkpointing'] = gradient_checkpointing
    if use_8bit_optimizer is not _UNSET:
        _kwargs['use_8bit_optimizer'] = use_8bit_optimizer
    if weight_decay is not _UNSET:
        _kwargs['weight_decay'] = weight_decay
    if max_grad_norm is not _UNSET:
        _kwargs['max_grad_norm'] = max_grad_norm
    if warmup_steps is not _UNSET:
        _kwargs['warmup_steps'] = warmup_steps
    if warmup_ratio is not _UNSET:
        _kwargs['warmup_ratio'] = warmup_ratio
    if save_optimizer_state is not _UNSET:
        _kwargs['save_optimizer_state'] = save_optimizer_state
    _kwargs.update(_extras)
    return node(wf, 'Qwen3FineTune', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3LoadPrompt(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    prompt_file: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3LoadPrompt
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: prompt
    """
    _kwargs: dict[str, Any] = {}
    if prompt_file is not _UNSET:
        _kwargs['prompt_file'] = prompt_file
    _kwargs.update(_extras)
    return node(wf, 'Qwen3LoadPrompt', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3Loader(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    repo_id: Any = _UNSET,
    source: Any = _UNSET,
    precision: Any = _UNSET,
    attention: Any = _UNSET,
    local_model_path: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3Loader
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: model
    """
    _kwargs: dict[str, Any] = {}
    if repo_id is not _UNSET:
        _kwargs['repo_id'] = repo_id
    if source is not _UNSET:
        _kwargs['source'] = source
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if attention is not _UNSET:
        _kwargs['attention'] = attention
    if local_model_path is not _UNSET:
        _kwargs['local_model_path'] = local_model_path
    _kwargs.update(_extras)
    return node(wf, 'Qwen3Loader', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3PromptMaker(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    ref_audio: Any = _UNSET,
    ref_text: Any = _UNSET,
    ref_audio_max_seconds: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3PromptMaker
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: QWEN3_PROMPT
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if ref_audio is not _UNSET:
        _kwargs['ref_audio'] = ref_audio
    if ref_text is not _UNSET:
        _kwargs['ref_text'] = ref_text
    if ref_audio_max_seconds is not _UNSET:
        _kwargs['ref_audio_max_seconds'] = ref_audio_max_seconds
    _kwargs.update(_extras)
    return node(wf, 'Qwen3PromptMaker', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3SavePrompt(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    prompt: Any = _UNSET,
    filename: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3SavePrompt
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: filepath
    """
    _kwargs: dict[str, Any] = {}
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if filename is not _UNSET:
        _kwargs['filename'] = filename
    _kwargs.update(_extras)
    return node(wf, 'Qwen3SavePrompt', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3VoiceClone(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    text: Any = _UNSET,
    seed: Any = _UNSET,
    language: Any = _UNSET,
    ref_audio: Any = _UNSET,
    ref_text: Any = _UNSET,
    prompt: Any = _UNSET,
    max_new_tokens: Any = _UNSET,
    ref_audio_max_seconds: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3VoiceClone
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if text is not _UNSET:
        _kwargs['text'] = text
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if language is not _UNSET:
        _kwargs['language'] = language
    if ref_audio is not _UNSET:
        _kwargs['ref_audio'] = ref_audio
    if ref_text is not _UNSET:
        _kwargs['ref_text'] = ref_text
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    if ref_audio_max_seconds is not _UNSET:
        _kwargs['ref_audio_max_seconds'] = ref_audio_max_seconds
    _kwargs.update(_extras)
    return node(wf, 'Qwen3VoiceClone', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3VoiceDesign(
    wf: VibeWorkflow,
    *,
    _id: str | None = None,
    model: Any = _UNSET,
    text: Any = _UNSET,
    instruct: Any = _UNSET,
    language: Any = _UNSET,
    seed: Any = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3VoiceDesign
    
    Pack: ComfyUI-Qwen3-TTS
    Returns: AUDIO
    """
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if text is not _UNSET:
        _kwargs['text'] = text
    if instruct is not _UNSET:
        _kwargs['instruct'] = instruct
    if language is not _UNSET:
        _kwargs['language'] = language
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'Qwen3VoiceDesign', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['Qwen3AudioCompare', 'Qwen3CustomVoice', 'Qwen3DataPrep', 'Qwen3DatasetFromFolder', 'Qwen3FineTune', 'Qwen3LoadPrompt', 'Qwen3Loader', 'Qwen3PromptMaker', 'Qwen3SavePrompt', 'Qwen3VoiceClone', 'Qwen3VoiceDesign']
