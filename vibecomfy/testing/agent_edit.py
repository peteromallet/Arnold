"""Reusable agent-edit testing stubs.

Provides a :class:`StubDeepSeekClient` with an OpenAI-compatible
``chat.completions.create`` interface that returns a configurable,
fixed JSON response suitable for exercising :func:`handle_agent_edit`
in tests, plus :func:`stub_schema_provider` and :func:`stub_session_root`
helpers.

Import-cost contract: this module MUST NOT import
``vibecomfy.schema.provider``, ``vibecomfy.runtime.*``, or
``vibecomfy.comfy_command`` at module level so headless test imports
are free of server-side effects.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "StubDeepSeekClient",
    "stub_schema_provider",
    "stub_session_root",
]

# ── Minimal built-in node type names used by the stub schema provider ──────
_BUILTIN_NODE_TYPES: tuple[str, ...] = (
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "KSampler",
    "VAEDecode",
    "SaveImage",
    "CLIPSetLastLayer",
    "EmptyLatentImage",
    "PreviewImage",
    "LoadImage",
    "LoraLoader",
)


# ── Lightweight OpenAI-compatible response shapes ──────────────────────────
@dataclass(frozen=True, slots=True)
class _StubMessage:
    """Minimal ``choice.message`` shape."""
    content: str
    role: str = "assistant"


@dataclass(frozen=True, slots=True)
class _StubChoice:
    """Minimal ``choice`` shape with 0-based index."""
    index: int
    message: _StubMessage
    finish_reason: str = "stop"


@dataclass(frozen=True, slots=True)
class _StubCompletion:
    """Minimal ``chat.completions.create`` return value."""
    id: str = "stub-completion-1"
    object: str = "chat.completion"
    created: int = 0
    model: str = "stub-model"
    choices: list[_StubChoice] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# StubDeepSeekClient
# ═══════════════════════════════════════════════════════════════════════════


class _StubCompletions:
    """``client.chat.completions`` namespace."""

    __slots__ = ("_fixed_response",)

    def __init__(self, fixed_response: dict[str, str]) -> None:
        self._fixed_response = fixed_response

    def create(
        self,
        *,
        messages: list[dict[str, str]],
        model: str = "stub-model",
        **__: Any,
    ) -> _StubCompletion:
        """Return a fixed completion wrapping *self._fixed_response*.

        The raw JSON response dict is serialised into
        ``choices[0].message.content`` so the caller can ``json.loads`` it.
        This mirrors the real OpenAI / DeepSeek API contract.
        """
        content = json.dumps(self._fixed_response, ensure_ascii=False)
        return _StubCompletion(
            model=model,
            choices=[
                _StubChoice(
                    index=0,
                    message=_StubMessage(content=content),
                )
            ],
        )


class _StubChat:
    """``client.chat`` namespace — holds ``completions``."""

    __slots__ = ("completions",)

    def __init__(self, fixed_response: dict[str, str]) -> None:
        self.completions = _StubCompletions(fixed_response)


class StubDeepSeekClient:
    """Test double for the DeepSeek / OpenAI-compatible chat API.

    Offers *two* access patterns so the same stub works for callers
    that expect an openai-style ``client.chat.completions.create(...)``
    shape and for callers that treat the client as a plain
    ``Callable[[list[dict]], dict]`` (the ``DeepSeekClient`` protocol
    used by :func:`handle_agent_edit`).

    Parameters
    ----------
    fixed_response:
        The dict returned (as JSON content) by every
        ``chat.completions.create`` call and by direct invocation.
        Defaults to a minimal ``{"python": "# no edit", "message": "ok"}``
        payload accepted by the full-edit contract normaliser.
    """

    __slots__ = ("chat", "_fixed_response")

    def __init__(
        self,
        fixed_response: dict[str, str] | None = None,
    ) -> None:
        self._fixed_response: dict[str, str] = dict(
            fixed_response or _DEFAULT_FIXED_RESPONSE
        )
        self.chat = _StubChat(self._fixed_response)

    # -- Direct callable protocol (DeepSeekClient shape) --------------------
    def __call__(self, messages: list[dict[str, str]]) -> dict[str, str]:
        """Return *fixed_response* directly — no JSON wrap.

        This matches ``DeepSeekClient = Callable[[list[dict]], dict]``
        so the stub can be passed as ``deepseek_client=stub`` to
        :func:`handle_agent_edit`.
        """
        return dict(self._fixed_response)


# Default stub response: a full-contract "no changes" result that
# satisfies ``_normalize_test_client_response``.
_DEFAULT_FIXED_RESPONSE: dict[str, str] = {
    "python": "# agent edit stub — no changes\nprint('ok')",
    "message": "Stub agent turn completed successfully.",
}


# ═══════════════════════════════════════════════════════════════════════════
# stub_schema_provider
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class _StubAgentEditSchema:
    """A schema record just detailed enough for agent-edit use.

    Carries ``class_type``, ``input``/``output`` slot names, and
    per-input defaults so the lowering / emit stages can resolve
    required inputs and widget values.
    """

    class_type: str
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    widget_defaults: dict[str, Any] = field(default_factory=dict)

    @property
    def required_inputs(self) -> list[str]:
        """Names of inputs that have no default value."""
        required: list[str] = []
        for name, info in self.input.items():
            if not isinstance(info, dict):
                continue
            if "default" not in info:
                required.append(name)
        return required

    @property
    def output_slots(self) -> list[str]:
        """Names of output slots."""
        return list(self.output.keys())


def _make_minimal_schema(class_type: str) -> _StubAgentEditSchema:
    """Return a schema with slots appropriate for *class_type*."""
    if class_type == "CheckpointLoaderSimple":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={
                "ckpt_name": {"default": "v1-5-pruned-emaonly.safetensors"},
            },
            output={"MODEL": "MODEL", "CLIP": "CLIP", "VAE": "VAE"},
        )
    if class_type == "CLIPTextEncode":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={
                "text": {"default": ""},
                "clip": {"required": True},
            },
            output={"CONDITIONING": "CONDITIONING"},
        )
    if class_type == "KSampler":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={
                "model": {"required": True},
                "positive": {"required": True},
                "negative": {"required": True},
                "latent_image": {"required": True},
                "seed": {"default": 0},
                "steps": {"default": 20},
                "cfg": {"default": 7.0},
                "sampler_name": {"default": "euler"},
                "scheduler": {"default": "normal"},
                "denoise": {"default": 1.0},
            },
            output={"LATENT": "LATENT"},
        )
    if class_type == "VAEDecode":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={
                "samples": {"required": True},
                "vae": {"required": True},
            },
            output={"IMAGE": "IMAGE"},
        )
    if class_type == "SaveImage":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={
                "images": {"required": True},
                "filename_prefix": {"default": "ComfyUI"},
            },
            output={},
        )
    if class_type == "EmptyLatentImage":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={
                "width": {"default": 512},
                "height": {"default": 512},
                "batch_size": {"default": 1},
            },
            output={"LATENT": "LATENT"},
        )
    if class_type == "CLIPSetLastLayer":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={
                "clip": {"required": True},
                "stop_at_clip_layer": {"default": -1},
            },
            output={"CLIP": "CLIP"},
        )
    if class_type == "PreviewImage":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={"images": {"required": True}},
            output={},
        )
    if class_type == "LoadImage":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={
                "image": {"default": "example.png"},
            },
            output={"IMAGE": "IMAGE", "MASK": "MASK"},
        )
    if class_type == "LoraLoader":
        return _StubAgentEditSchema(
            class_type=class_type,
            input={
                "model": {"required": True},
                "clip": {"required": True},
                "lora_name": {"default": "epi_noiseoffset2.safetensors"},
                "strength_model": {"default": 1.0},
                "strength_clip": {"default": 1.0},
            },
            output={"MODEL": "MODEL", "CLIP": "CLIP"},
        )
    # Generic fallback for any unrecognised class_type.
    return _StubAgentEditSchema(
        class_type=class_type,
        input={},
        output={},
    )


class _StubAgentEditSchemaProvider:
    """A minimal schema provider backed by a built-in node catalog.

    Call :func:`stub_schema_provider` to get a configured instance.
    """

    __slots__ = ("_schemas",)

    def __init__(self) -> None:
        self._schemas: dict[str, _StubAgentEditSchema] = {
            ct: _make_minimal_schema(ct) for ct in _BUILTIN_NODE_TYPES
        }

    def node_schema(self, class_type: str) -> _StubAgentEditSchema | None:
        """Return the schema for *class_type*, or ``None`` if unknown.

        The returned object satisfies the ``SchemaProviderLike`` Protocol
        (``class_type`` attribute) *and* carries ``required_inputs``,
        ``output_slots``, and ``widget_defaults`` for agent-edit use.
        """
        return self._schemas.get(class_type)

    @property
    def object_info(self) -> dict[str, Any]:
        """Return a dict-of-schemas snapshot suitable for serialisation."""
        return {
            ct: {
                "class_type": s.class_type,
                "input": s.input,
                "output": s.output,
                "widget_defaults": s.widget_defaults,
            }
            for ct, s in self._schemas.items()
        }

    def __repr__(self) -> str:
        return f"_StubAgentEditSchemaProvider({len(self._schemas)} types)"


def stub_schema_provider() -> _StubAgentEditSchemaProvider:
    """Return a minimal schema provider with 10 built-in node types.

    The provider covers the minimum set needed to resolve a typical
    headless fixture workflow: ``CheckpointLoaderSimple``,
    ``CLIPTextEncode``, ``KSampler``, ``VAEDecode``, ``SaveImage``,
    ``CLIPSetLastLayer``, ``EmptyLatentImage``, ``PreviewImage``,
    ``LoadImage``, and ``LoraLoader``.

    Unknown class types return ``None`` from ``node_schema()``.
    """
    return _StubAgentEditSchemaProvider()


# ═══════════════════════════════════════════════════════════════════════════
# stub_session_root
# ═══════════════════════════════════════════════════════════════════════════


def stub_session_root() -> Path:
    """Create and return a temporary session-root directory.

    The directory is created inside the platform ``tmp`` area with a
    ``vibecomfy-agent-edit-test-`` prefix.  Callers own its lifecycle
    and should clean up after use.

    Returns
    -------
    pathlib.Path
        Absolute path to an existing, empty directory.
    """
    path = Path(tempfile.mkdtemp(prefix="vibecomfy-agent-edit-test-"))
    path.mkdir(parents=True, exist_ok=True)
    return path
