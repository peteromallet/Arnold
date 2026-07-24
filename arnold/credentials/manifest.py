"""Minimal Arnold credential manifest/spec model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "arnold.credentials.manifest requires PyYAML. Install with `pip install pyyaml`."
    ) from exc

from pydantic import BaseModel, Field


class CredentialRequirement(BaseModel):
    """One credential required by an operation."""

    name: str
    provider: str | None = None
    required: bool = True


class CredentialManifest(BaseModel):
    """A manifest declaring credentials an operation expects."""

    version: str = "v1"
    credentials: list[CredentialRequirement] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Any) -> "CredentialManifest":
        if not isinstance(raw, dict):
            raise ValueError("Credential manifest must be a YAML/JSON mapping")
        return cls.model_validate(raw)

    @classmethod
    def from_path(cls, path: Path) -> "CredentialManifest":
        if not path.exists():
            raise FileNotFoundError(f"Credential manifest not found: {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.from_dict(raw or {})


__all__ = [
    "CredentialManifest",
    "CredentialRequirement",
]
