"""Neutral versioned-artifact helpers for the Arnold pipeline boundary.

Every Step that writes artifacts uses the same layout::

    <artifact_root>/<stage>/<label>/v<n>.<suffix>

where ``<n>`` is an auto-incremented integer.  The helpers below
provide the mechanics — path construction, version scanning, and
atomic writes — without any opinion about what the artifacts mean.

Boundary discipline
-------------------

No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from arnold.pipeline.types import StepContext

LARGE_ARTIFACT_THRESHOLD_BYTES = 1024 * 1024  # 1 MiB
_HASH_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class SidecarManifest:
    """Sidecar metadata persisted next to large (>1 MiB) artifacts.

    Recorded fields:
    * ``content_type`` — declared MIME / logical content tag.
    * ``schema_hash`` — sha256 of the canonical schema bytes the artifact
      claims to satisfy (empty when not declared).
    * ``size`` — blob byte count.
    * ``sha256`` — blob digest (computed via streaming hasher).
    """

    content_type: str
    schema_hash: str
    size: int
    sha256: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "SidecarManifest":
        data = json.loads(raw)
        return cls(
            content_type=str(data.get("content_type", "")),
            schema_hash=str(data.get("schema_hash", "")),
            size=int(data.get("size", 0)),
            sha256=str(data.get("sha256", "")),
        )


def sidecar_path_for(blob_path: Path) -> Path:
    """Return the sidecar manifest path next to ``blob_path``."""
    return blob_path.with_suffix(blob_path.suffix + ".manifest.json")


def stream_sha256(path: Path) -> str:
    """Compute the sha256 hex digest of ``path`` via a streaming hasher."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_HASH_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def write_sidecar_manifest(
    blob_path: Path,
    *,
    content_type: str,
    schema_hash: str,
) -> SidecarManifest:
    """Hash ``blob_path`` (streaming) and write its sidecar manifest.

    Called by :func:`write_versioned` for large artifacts. Returns the
    manifest object that was persisted.
    """
    size = blob_path.stat().st_size
    digest = stream_sha256(blob_path)
    manifest = SidecarManifest(
        content_type=content_type,
        schema_hash=schema_hash,
        size=size,
        sha256=digest,
    )
    sidecar = sidecar_path_for(blob_path)
    tmp = sidecar.with_suffix(sidecar.suffix + ".tmp")
    tmp.write_text(manifest.to_json(), encoding="utf-8")
    os.replace(tmp, sidecar)
    return manifest


def read_sidecar_manifest(blob_path: Path) -> SidecarManifest | None:
    """Return the parsed manifest for ``blob_path``, or ``None`` if absent."""
    sidecar = sidecar_path_for(blob_path)
    if not sidecar.is_file():
        return None
    return SidecarManifest.from_json(sidecar.read_text(encoding="utf-8"))


def verify_sidecar_integrity(blob_path: Path) -> bool:
    """Recompute the blob's sha256 and compare to its sidecar manifest.

    Lazy / consumer-opt-in: callers invoke this ONLY when they need to
    catch tampering or corruption. Returns ``False`` if the manifest is
    missing or any field disagrees.
    """
    manifest = read_sidecar_manifest(blob_path)
    if manifest is None:
        return False
    if blob_path.stat().st_size != manifest.size:
        return False
    return stream_sha256(blob_path) == manifest.sha256

_VERSION_RE = re.compile(r"^v(\d+)\.([a-z0-9]+)$")


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def artifact_dir(ctx: StepContext, stage: str, label: str) -> Path:
    """Return ``<artifact_root>/<stage>/<label>/``, creating parents.

    Uses *ctx.artifact_root* — the neutral root — instead of any
    opinionated ``plan_dir`` concept.
    """
    out = Path(ctx.artifact_root) / stage / label
    out.mkdir(parents=True, exist_ok=True)
    return out


def artifact_path(
    ctx: StepContext, stage: str, label: str, version: int, suffix: str
) -> Path:
    """Return ``<artifact_root>/<stage>/<label>/v<version>.<suffix>``.

    Does NOT create the file — callers own writing.  The parent
    directory is created if absent.
    """
    return artifact_dir(ctx, stage, label) / f"v{version}.{suffix}"


def next_version(ctx: StepContext, stage: str, label: str, suffix: str) -> int:
    """Return the next unused version integer for *stage*/*label*/*suffix*.

    Scans ``<artifact_root>/<stage>/<label>/v*.<suffix>`` and returns
    ``max(existing) + 1`` (or ``1`` when no versions exist yet).
    """
    directory = Path(ctx.artifact_root) / stage / label
    if not directory.is_dir():
        return 1
    highest = 0
    for path in directory.glob(f"v*.{suffix}"):
        m = _VERSION_RE.match(path.name)
        if m and m.group(2) == suffix:
            highest = max(highest, int(m.group(1)))
    return highest + 1


def latest_artifact(ctx: StepContext, stage: str, label: str, suffix: str) -> Path | None:
    """Return the highest-version artifact path, or ``None`` if none exist.

    Uses *ctx.artifact_root* as the base directory.
    """
    directory = Path(ctx.artifact_root) / stage / label
    if not directory.is_dir():
        return None
    candidates: list[tuple[int, Path]] = []
    for path in directory.glob(f"v*.{suffix}"):
        m = _VERSION_RE.match(path.name)
        if m and m.group(2) == suffix:
            candidates.append((int(m.group(1)), path))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def write_versioned(
    ctx: StepContext,
    stage: str,
    label: str,
    content: str,
    suffix: str,
    *,
    version: int | None = None,
    content_type: str = "",
    schema_hash: str = "",
) -> Path:
    """Write *content* to the next versioned artifact path atomically.

    If *version* is ``None``, :func:`next_version` is called to
    auto-increment.  The write uses a ``.tmp`` sibling + ``os.replace``
    for atomicity.

    Large artifacts (>1 MiB) get a sidecar manifest written next to the
    blob via :func:`write_sidecar_manifest`. Smaller artifacts skip the
    sidecar — the legacy ≤1 MiB path is unchanged.

    Returns the final blob path written.
    """
    v = version if version is not None else next_version(ctx, stage, label, suffix)
    dest = artifact_path(ctx, stage, label, v, suffix)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, dest)
    if dest.stat().st_size > LARGE_ARTIFACT_THRESHOLD_BYTES:
        write_sidecar_manifest(
            dest, content_type=content_type, schema_hash=schema_hash
        )
    return dest
