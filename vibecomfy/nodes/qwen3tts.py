# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Auto-generated thin wrappers for ComfyUI node classes.

Regenerate via: python -m tools.generate_node_shims
"""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.templates import _current_workflow_or_raise, node
from vibecomfy.workflow import VibeWorkflow

class _Omitted:
    pass

_UNSET = _Omitted()

def Qwen3AudioCompare(
    *args: VibeWorkflow,
    _id: str | None = None,
    reference_audio: Any | _Omitted = _UNSET,
    generated_audio: Any | _Omitted = _UNSET,
    speaker_encoder_model: Any | _Omitted = _UNSET,
    local_model_path: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3AudioCompare

    Pack: ComfyUI-Qwen3-TTS
    Returns: report

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3AudioCompare() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'] | _Omitted = _UNSET,
    speaker: Literal['Vivian', 'Serena', 'Uncle_Fu', 'Dylan', 'Eric', 'Ryan', 'Aiden', 'Ono_Anna', 'Sohee'] | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    instruct: str | _Omitted = _UNSET,
    custom_speaker_name: str | _Omitted = _UNSET,
    max_new_tokens: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3CustomVoice

    Pack: ComfyUI-Qwen3-TTS
    Returns: AUDIO

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3CustomVoice() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    jsonl_path: str | _Omitted = _UNSET,
    tokenizer_repo: Any | _Omitted = _UNSET,
    source: Literal['HuggingFace', 'ModelScope'] | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3DataPrep

    Pack: ComfyUI-Qwen3-TTS
    Returns: processed_jsonl_path

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3DataPrep() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    folder_path: str | _Omitted = _UNSET,
    output_filename: str | _Omitted = _UNSET,
    ref_audio_path: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3DatasetFromFolder

    Pack: ComfyUI-Qwen3-TTS
    Returns: jsonl_path

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3DatasetFromFolder() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    train_jsonl: str | _Omitted = _UNSET,
    init_model: Any | _Omitted = _UNSET,
    source: Literal['HuggingFace', 'ModelScope'] | _Omitted = _UNSET,
    output_dir: str | _Omitted = _UNSET,
    epochs: int | _Omitted = _UNSET,
    batch_size: int | _Omitted = _UNSET,
    lr: float | _Omitted = _UNSET,
    speaker_name: str | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    resume_training: bool | _Omitted = _UNSET,
    log_every_steps: int | _Omitted = _UNSET,
    save_every_epochs: int | _Omitted = _UNSET,
    save_every_steps: int | _Omitted = _UNSET,
    mixed_precision: Literal['bf16', 'fp32'] | _Omitted = _UNSET,
    gradient_accumulation: int | _Omitted = _UNSET,
    gradient_checkpointing: bool | _Omitted = _UNSET,
    use_8bit_optimizer: bool | _Omitted = _UNSET,
    weight_decay: float | _Omitted = _UNSET,
    max_grad_norm: float | _Omitted = _UNSET,
    warmup_steps: int | _Omitted = _UNSET,
    warmup_ratio: float | _Omitted = _UNSET,
    save_optimizer_state: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3FineTune

    Pack: ComfyUI-Qwen3-TTS
    Returns: model_path, custom_speaker_name

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3FineTune() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt_file: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3LoadPrompt

    Pack: ComfyUI-Qwen3-TTS
    Returns: prompt

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3LoadPrompt() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt_file is not _UNSET:
        _kwargs['prompt_file'] = prompt_file
    _kwargs.update(_extras)
    return node(wf, 'Qwen3LoadPrompt', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3Loader(
    *args: VibeWorkflow,
    _id: str | None = None,
    repo_id: Any | _Omitted = _UNSET,
    source: Literal['HuggingFace', 'ModelScope'] | _Omitted = _UNSET,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = _UNSET,
    attention: Literal['auto', 'flash_attention_2', 'sdpa', 'eager'] | _Omitted = _UNSET,
    local_model_path: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3Loader

    Pack: ComfyUI-Qwen3-TTS
    Returns: model

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3Loader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    ref_audio: Any | _Omitted = _UNSET,
    ref_text: str | _Omitted = _UNSET,
    ref_audio_max_seconds: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3PromptMaker

    Pack: ComfyUI-Qwen3-TTS
    Returns: QWEN3_PROMPT

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3PromptMaker() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt: Any | _Omitted = _UNSET,
    filename: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3SavePrompt

    Pack: ComfyUI-Qwen3-TTS
    Returns: filepath

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3SavePrompt() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if filename is not _UNSET:
        _kwargs['filename'] = filename
    _kwargs.update(_extras)
    return node(wf, 'Qwen3SavePrompt', _id, pass_raw=pass_raw, **_kwargs)

def Qwen3VoiceClone(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'] | _Omitted = _UNSET,
    ref_audio: Any | _Omitted = _UNSET,
    ref_text: str | _Omitted = _UNSET,
    prompt: Any | _Omitted = _UNSET,
    max_new_tokens: int | _Omitted = _UNSET,
    ref_audio_max_seconds: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3VoiceClone

    Pack: ComfyUI-Qwen3-TTS
    Returns: AUDIO

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3VoiceClone() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    text: str | _Omitted = _UNSET,
    instruct: str | _Omitted = _UNSET,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'] | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
):
    """
    Qwen3VoiceDesign

    Pack: ComfyUI-Qwen3-TTS
    Returns: AUDIO

    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.
    """
    if len(args) > 1:
        raise TypeError(f"Qwen3VoiceDesign() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
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
__vibecomfy_class_types__ = {'Qwen3AudioCompare': 'Qwen3AudioCompare', 'Qwen3CustomVoice': 'Qwen3CustomVoice', 'Qwen3DataPrep': 'Qwen3DataPrep', 'Qwen3DatasetFromFolder': 'Qwen3DatasetFromFolder', 'Qwen3FineTune': 'Qwen3FineTune', 'Qwen3LoadPrompt': 'Qwen3LoadPrompt', 'Qwen3Loader': 'Qwen3Loader', 'Qwen3PromptMaker': 'Qwen3PromptMaker', 'Qwen3SavePrompt': 'Qwen3SavePrompt', 'Qwen3VoiceClone': 'Qwen3VoiceClone', 'Qwen3VoiceDesign': 'Qwen3VoiceDesign'}
