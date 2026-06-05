"""Stable routing identity for model-output cache keys."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

MODEL_PARAM_KEYS: tuple[str, ...] = ("temperature", "max_tokens", "top_p")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


@dataclass(frozen=True)
class ModelIdentity:
    """Cache identity for one routed model call."""

    prompt_hash: str
    model_version: str
    params_hash: str

    def to_json(self) -> dict[str, str]:
        return {
            "prompt_hash": self.prompt_hash,
            "model_version": self.model_version,
            "params_hash": self.params_hash,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> "ModelIdentity":
        return cls(
            prompt_hash=str(value["prompt_hash"]),
            model_version=str(value["model_version"]),
            params_hash=str(value["params_hash"]),
        )


def prompt_hash(prompt: str) -> str:
    """Return the SHA-256 hash of the exact prompt text."""

    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def params_hash(params: Mapping[str, Any] | None) -> str:
    """Return the hash of cache-relevant model-side parameters only."""

    filtered = {
        key: params[key]
        for key in MODEL_PARAM_KEYS
        if params is not None and key in params
    }
    return hashlib.sha256(_canonical_json(filtered).encode("utf-8")).hexdigest()


def _model_version(model: object) -> str:
    if isinstance(model, Mapping):
        for key in ("model_version", "reported_version", "version", "id", "model", "name"):
            value = model.get(key)
            if value is not None:
                return str(value)
    for attr in ("model_version", "reported_version", "version", "id", "model", "name"):
        value = getattr(model, attr, None)
        if value is not None:
            return str(value)
    return str(model)


def compute_identity(
    prompt: str,
    model: object,
    params: Mapping[str, Any] | None = None,
) -> ModelIdentity:
    """Compute the routing cache identity for a model call."""

    return ModelIdentity(
        prompt_hash=prompt_hash(prompt),
        model_version=_model_version(model),
        params_hash=params_hash(params),
    )
