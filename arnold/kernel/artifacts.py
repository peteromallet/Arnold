"""Artifact binding and provenance contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath

from arnold.kernel.content_types import ContentTypeRegistration, RetentionPin


@dataclass(frozen=True)
class ArtifactRoot:
    """Logical artifact root supplied by callers."""

    root_id: str
    path: str


@dataclass(frozen=True)
class ProvenanceParent:
    """Parent artifact/hash link for provenance chains."""

    artifact_id: str
    content_hash: str


@dataclass(frozen=True)
class GeneratedArtifactProvenance:
    """Generator provenance for regenerated docs, registries, and scaffolds."""

    generator_module: str
    generator_source_hash: str
    manifest_contract_version: str
    generated_at: str
    input_hashes: tuple[str, ...] = ()
    parents: tuple[ProvenanceParent, ...] = ()

    @property
    def provenance_hash(self) -> str:
        payload = "|".join(
            (
                self.generator_module,
                self.generator_source_hash,
                self.manifest_contract_version,
                self.generated_at,
                ",".join(self.input_hashes),
                ",".join(parent.content_hash for parent in self.parents),
            )
        )
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ArtifactBinding:
    """A generated artifact bound to a logical root and content type."""

    artifact_id: str
    root: ArtifactRoot
    relative_path: str
    content_type: ContentTypeRegistration
    provenance: GeneratedArtifactProvenance
    retention_pins: tuple[RetentionPin, ...] = ()


def versioned_artifact_name(stem: str, version: int, extension: str) -> str:
    """Return the frozen ``vN.<ext>`` artifact filename."""

    if version < 1:
        raise ValueError("artifact version must be >= 1")
    ext = extension[1:] if extension.startswith(".") else extension
    if stem:
        return f"{stem}.v{version}.{ext}"
    return f"v{version}.{ext}"


def latest_version(paths: tuple[str, ...], extension: str) -> int | None:
    """Return the highest ``vN.<ext>`` version in a set of paths."""

    ext = extension[1:] if extension.startswith(".") else extension
    versions: list[int] = []
    for raw in paths:
        name = PurePosixPath(raw).name
        if not name.endswith("." + ext):
            continue
        for part in name.split("."):
            if part.startswith("v") and part[1:].isdigit():
                versions.append(int(part[1:]))
    return max(versions) if versions else None


def next_version_path(directory: str, stem: str, extension: str, existing: tuple[str, ...]) -> str:
    """Return the next canonical versioned artifact path."""

    version = (latest_version(existing, extension) or 0) + 1
    return str(PurePosixPath(directory) / versioned_artifact_name(stem, version, extension))
