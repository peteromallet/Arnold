# GENERATED FILE — do not hand-edit; regenerate via `python -m tools.generate_node_shims`.
"""Type stubs for generated ComfyUI node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def Qwen3AudioCompare(
    *args: VibeWorkflow,
    _id: str | None = ...,
    reference_audio: Any | _Omitted = ...,
    generated_audio: Any | _Omitted = ...,
    speaker_encoder_model: Any | _Omitted = ...,
    local_model_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3CustomVoice(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    text: str | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'] | _Omitted = ...,
    speaker: Literal['Vivian', 'Serena', 'Uncle_Fu', 'Dylan', 'Eric', 'Ryan', 'Aiden', 'Ono_Anna', 'Sohee'] | _Omitted = ...,
    seed: int | _Omitted = ...,
    instruct: str | _Omitted = ...,
    custom_speaker_name: str | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3DataPrep(
    *args: VibeWorkflow,
    _id: str | None = ...,
    jsonl_path: str | _Omitted = ...,
    tokenizer_repo: Any | _Omitted = ...,
    source: Literal['HuggingFace', 'ModelScope'] | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3DatasetFromFolder(
    *args: VibeWorkflow,
    _id: str | None = ...,
    folder_path: str | _Omitted = ...,
    output_filename: str | _Omitted = ...,
    ref_audio_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3FineTune(
    *args: VibeWorkflow,
    _id: str | None = ...,
    train_jsonl: str | _Omitted = ...,
    init_model: Any | _Omitted = ...,
    source: Literal['HuggingFace', 'ModelScope'] | _Omitted = ...,
    output_dir: str | _Omitted = ...,
    epochs: int | _Omitted = ...,
    batch_size: int | _Omitted = ...,
    lr: float | _Omitted = ...,
    speaker_name: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    resume_training: bool | _Omitted = ...,
    log_every_steps: int | _Omitted = ...,
    save_every_epochs: int | _Omitted = ...,
    save_every_steps: int | _Omitted = ...,
    mixed_precision: Literal['bf16', 'fp32'] | _Omitted = ...,
    gradient_accumulation: int | _Omitted = ...,
    gradient_checkpointing: bool | _Omitted = ...,
    use_8bit_optimizer: bool | _Omitted = ...,
    weight_decay: float | _Omitted = ...,
    max_grad_norm: float | _Omitted = ...,
    warmup_steps: int | _Omitted = ...,
    warmup_ratio: float | _Omitted = ...,
    save_optimizer_state: bool | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3LoadPrompt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt_file: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3Loader(
    *args: VibeWorkflow,
    _id: str | None = ...,
    repo_id: Any | _Omitted = ...,
    source: Literal['HuggingFace', 'ModelScope'] | _Omitted = ...,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = ...,
    attention: Literal['auto', 'flash_attention_2', 'sdpa', 'eager'] | _Omitted = ...,
    local_model_path: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3PromptMaker(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    ref_audio: Any | _Omitted = ...,
    ref_text: str | _Omitted = ...,
    ref_audio_max_seconds: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3SavePrompt(
    *args: VibeWorkflow,
    _id: str | None = ...,
    prompt: Any | _Omitted = ...,
    filename: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3VoiceClone(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    text: str | _Omitted = ...,
    seed: int | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'] | _Omitted = ...,
    ref_audio: Any | _Omitted = ...,
    ref_text: str | _Omitted = ...,
    prompt: Any | _Omitted = ...,
    max_new_tokens: int | _Omitted = ...,
    ref_audio_max_seconds: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def Qwen3VoiceDesign(
    *args: VibeWorkflow,
    _id: str | None = ...,
    model: Any | _Omitted = ...,
    text: str | _Omitted = ...,
    instruct: str | _Omitted = ...,
    language: Literal['Auto', 'Chinese', 'English', 'Japanese', 'Korean', 'German', 'French', 'Russian', 'Portuguese', 'Spanish', 'Italian'] | _Omitted = ...,
    seed: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__: list[str]
