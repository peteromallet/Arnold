"""Artifact binding and provenance contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from arnold.kernel.content_types import ContentTypeRegistration, RetentionPin

_VERSIONED_NAME_RE = re.compile(
    r"^v(?P<version>[1-9][0-9]*)\.(?P<ext>[A-Za-z0-9][A-Za-z0-9._-]*)$"
)


class ArtifactRootKind(StrEnum):
    """Neutral logical root shapes supported by the artifact contract."""

    REPO_ARTIFACT_ROOT = "repo_artifact_root"
    PLAN_ARTIFACT_ROOT = "plan_artifact_root"


@dataclass(frozen=True)
class ArtifactRoot:
    """Logical artifact root supplied by callers."""

    root_id: str
    path: str
    kind: ArtifactRootKind = ArtifactRootKind.PLAN_ARTIFACT_ROOT


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
        payload = json.dumps(
            {
                "generated_at": self.generated_at,
                "generator_module": self.generator_module,
                "generator_source_hash": self.generator_source_hash,
                "input_hashes": list(self.input_hashes),
                "manifest_contract_version": self.manifest_contract_version,
                "parents": [
                    {
                        "artifact_id": parent.artifact_id,
                        "content_hash": parent.content_hash,
                    }
                    for parent in self.parents
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
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
    if stem:
        raise ValueError("versioned artifact names are canonicalized as vN.<ext>")
    ext = extension[1:] if extension.startswith(".") else extension
    return f"v{version}.{ext}"


def latest_version(paths: tuple[str, ...], extension: str) -> int | None:
    """Return the highest ``vN.<ext>`` version in a set of paths."""

    ext = extension[1:] if extension.startswith(".") else extension
    versions: list[int] = []
    for raw in paths:
        name = PurePosixPath(raw).name
        match = _VERSIONED_NAME_RE.match(name)
        if match and match.group("ext") == ext:
            versions.append(int(match.group("version")))
    return max(versions) if versions else None


def next_version_path(
    directory: str, stem: str, extension: str, existing: tuple[str, ...]
) -> str:
    """Return the next canonical versioned artifact path."""

    version = (latest_version(existing, extension) or 0) + 1
    return str(
        PurePosixPath(directory) / versioned_artifact_name(stem, version, extension)
    )
