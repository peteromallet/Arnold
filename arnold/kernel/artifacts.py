"""Artifact binding and provenance contracts."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass, fields, is_dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, TypeVar, get_args, get_origin, get_type_hints

from arnold.kernel.content_types import ContentTypeRegistration, ContentTypeRegistry, RetentionPin

_VERSIONED_NAME_RE = re.compile(
    r"^v(?P<version>[1-9][0-9]*)\.(?P<ext>[A-Za-z0-9][A-Za-z0-9._-]*)$"
)
_LOGICAL_ROOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


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

    def __post_init__(self) -> None:
        validate_logical_root_id(self.root_id)
        if not self.path:
            raise ValueError("artifact root path must be non-empty")
        if "\x00" in self.path:
            raise ValueError("artifact root path must not contain NUL bytes")

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "path": self.path,
            "root_id": self.root_id,
        }


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

    def __post_init__(self) -> None:
        validate_logical_root_id(self.artifact_id)
        validate_safe_relative_subpath(self.relative_path)

    def to_dict(self) -> dict[str, Any]:
        return _plain_value(self)


def validate_logical_root_id(value: str) -> str:
    """Validate a stable logical artifact root or artifact id."""

    if not value:
        raise ValueError("logical root id must be non-empty")
    if not _LOGICAL_ROOT_ID_RE.fullmatch(value):
        raise ValueError("logical root id contains unsupported characters")
    return value


def validate_safe_relative_subpath(value: str) -> str:
    """Validate an artifact-relative POSIX path that cannot escape its root."""

    if not value:
        raise ValueError("relative artifact path must be non-empty")
    if "\\" in value or "\x00" in value:
        raise ValueError("relative artifact path contains unsupported characters")
    path = PurePosixPath(value)
    if str(path) != value:
        raise ValueError("relative artifact path must use canonical POSIX spelling")
    if path.is_absolute():
        raise ValueError("relative artifact path must not be absolute")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("relative artifact path must not contain empty, dot, or parent segments")
    return value


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


# ---------------------------------------------------------------------------
# Deterministic serialization helpers for artifact bindings.
# ---------------------------------------------------------------------------


_T = TypeVar("_T")


def _plain_value(value: Any) -> Any:
    """Convert dataclasses, enums, tuples, and mappings to plain JSON values."""

    if is_dataclass(value) and not isinstance(value, type):
        return {key: _plain_value(subvalue) for key, subvalue in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _plain_value(subvalue) for key, subvalue in value.items()}
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    return value


def _artifact_binding_json(binding: ArtifactBinding) -> str:
    return json.dumps(
        _plain_value(binding),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _decode_dataclass(cls: type[_T], payload: Mapping[str, Any]) -> _T:
    kwargs: dict[str, Any] = {}
    type_hints = get_type_hints(cls)
    for item in fields(cls):
        if item.name not in payload:
            continue
        kwargs[item.name] = _decode_value(type_hints[item.name], payload[item.name])
    return cls(**kwargs)


def _decode_value(annotation: Any, value: Any) -> Any:
    if value is None:
        return None
    origin = get_origin(annotation)
    args = get_args(annotation)
    if is_dataclass(annotation):
        if not isinstance(value, Mapping):
            raise ValueError(f"expected object for {annotation.__name__}")
        return _decode_dataclass(annotation, value)
    if origin is tuple and args:
        inner = args[0]
        return tuple(_decode_value(inner, item) for item in value)
    if origin is dict or origin is Mapping:
        return dict(value)
    if origin is not None and type(None) in args:
        non_none = [arg for arg in args if arg is not type(None)][0]
        return _decode_value(non_none, value)
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        return annotation(value)
    return value


def _artifact_binding_from_json(raw: str | bytes) -> ArtifactBinding:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("artifact binding JSON must decode to an object")
    return _decode_dataclass(ArtifactBinding, payload)


# ---------------------------------------------------------------------------
# File-backed versioned artifact store.
# ---------------------------------------------------------------------------


class FileBackedArtifactStore:
    """File-backed artifact store writing ``vN.<ext>`` versions.

    The store writes artifact bytes under ``<artifact_root>/<artifact_id>/``
    using canonical versioned filenames.  Each version is accompanied by a
    ``.meta.json`` sidecar that records the :class:`ArtifactBinding`, including
    content hash, content type, provenance, and retention pins.

    Legacy flat artifacts (any non-versioned file in the artifact directory)
    are quarantined on write rather than treated as authoritative runtime
    reads.  Quarantined files remain available as migration input.
    """

    def __init__(
        self,
        artifact_root: str | Path,
        content_type_registry: ContentTypeRegistry | None = None,
    ) -> None:
        self.root = Path(artifact_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = content_type_registry or ContentTypeRegistry()
        self._quarantine_dir = self.root / ".quarantine" / "legacy"

    def _artifact_dir(self, artifact_id: str) -> Path:
        validate_logical_root_id(artifact_id)
        directory = self.root / artifact_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _quarantine_legacy_files(self, artifact_dir: Path) -> list[Path]:
        """Move non-versioned, non-meta files into the legacy quarantine."""

        quarantined: list[Path] = []
        for entry in sorted(artifact_dir.iterdir()):
            if not entry.is_file():
                continue
            if entry.name.endswith(".meta.json"):
                continue
            if _VERSIONED_NAME_RE.match(entry.name):
                continue

            target_dir = self._quarantine_dir / artifact_dir.name
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / entry.name
            counter = 1
            original = target
            while target.exists():
                suffixes = "".join(original.suffixes)
                stem = original.name[: -len(suffixes)] if suffixes else original.name
                target = original.with_name(f"{stem}_{counter}{suffixes}")
                counter += 1

            shutil.move(str(entry), str(target))
            quarantined.append(target)
        return quarantined

    def write_artifact(
        self,
        artifact_id: str,
        content: bytes,
        content_type_id: str,
        provenance: GeneratedArtifactProvenance,
        extension: str,
        retention_pins: tuple[RetentionPin, ...] = (),
    ) -> ArtifactBinding:
        """Write a versioned artifact and return its binding."""

        validate_logical_root_id(artifact_id)
        content_type = self.registry.require(content_type_id)
        artifact_dir = self._artifact_dir(artifact_id)
        self._quarantine_legacy_files(artifact_dir)

        ext = extension[1:] if extension.startswith(".") else extension
        if not ext:
            raise ValueError("extension must be non-empty")

        existing = tuple(
            str(entry.relative_to(artifact_dir))
            for entry in sorted(artifact_dir.iterdir())
        )
        version = (latest_version(existing, ext) or 0) + 1
        versioned_name = versioned_artifact_name("", version, ext)
        relative_path = f"{artifact_id}/{versioned_name}"
        file_path = artifact_dir / versioned_name
        meta_path = file_path.with_name(file_path.name + ".meta.json")

        file_path.write_bytes(content)
        content_hash = "sha256:" + hashlib.sha256(content).hexdigest()

        binding = ArtifactBinding(
            artifact_id=artifact_id,
            root=ArtifactRoot(
                root_id="file-backed",
                path=str(self.root.resolve()),
                kind=ArtifactRootKind.PLAN_ARTIFACT_ROOT,
            ),
            relative_path=relative_path,
            content_type=content_type,
            provenance=provenance,
            retention_pins=retention_pins,
        )

        meta_path.write_text(_artifact_binding_json(binding), encoding="utf-8")
        return binding

    def resolve_newest(
        self, artifact_id: str, extension: str
    ) -> ArtifactBinding | None:
        """Return the binding for the newest ``vN.<ext>`` artifact."""

        validate_logical_root_id(artifact_id)
        artifact_dir = self.root / artifact_id
        if not artifact_dir.exists():
            return None

        ext = extension[1:] if extension.startswith(".") else extension
        existing = tuple(
            str(entry.relative_to(artifact_dir))
            for entry in sorted(artifact_dir.iterdir())
        )
        version = latest_version(existing, ext)
        if version is None:
            return None

        meta_path = artifact_dir / f"v{version}.{ext}.meta.json"
        if not meta_path.exists():
            return None

        return _artifact_binding_from_json(meta_path.read_text(encoding="utf-8"))

    def list_versions(self, artifact_id: str, extension: str) -> list[int]:
        """Return all ``vN.<ext>`` version numbers for an artifact."""

        validate_logical_root_id(artifact_id)
        artifact_dir = self.root / artifact_id
        if not artifact_dir.exists():
            return []
        ext = extension[1:] if extension.startswith(".") else extension
        existing = tuple(
            str(entry.relative_to(artifact_dir))
            for entry in sorted(artifact_dir.iterdir())
        )
        versions: list[int] = []
        for raw in existing:
            name = PurePosixPath(raw).name
            match = _VERSIONED_NAME_RE.match(name)
            if match and match.group("ext") == ext:
                versions.append(int(match.group("version")))
        return sorted(versions)

    def quarantine_legacy(self, artifact_id: str) -> list[Path]:
        """Quarantine any legacy flat artifacts for ``artifact_id``.

        Returns the list of quarantine paths.  Quarantined files remain
        available as migration input via :meth:`legacy_inputs`.
        """

        return self._quarantine_legacy_files(self._artifact_dir(artifact_id))

    def legacy_inputs(self, artifact_id: str) -> Mapping[str, bytes]:
        """Return quarantined legacy flat artifact contents as migration input."""

        validate_logical_root_id(artifact_id)
        target_dir = self._quarantine_dir / artifact_id
        if not target_dir.exists():
            return {}
        return {
            entry.name: entry.read_bytes()
            for entry in sorted(target_dir.iterdir())
            if entry.is_file()
        }


__all__ = [
    "ArtifactBinding",
    "ArtifactRoot",
    "ArtifactRootKind",
    "FileBackedArtifactStore",
    "GeneratedArtifactProvenance",
    "ProvenanceParent",
    "latest_version",
    "next_version_path",
    "validate_logical_root_id",
    "validate_safe_relative_subpath",
    "versioned_artifact_name",
]
