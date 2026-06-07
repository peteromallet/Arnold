"""Deterministic artifact and validation helpers for M8 benchmark tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipeline import select_audit_mode

MANIFEST_ONLY_THRESHOLD_BYTES = 1 << 20

ARTIFACT_TIERS: tuple[tuple[str, int], ...] = (
    ("64KiB", 64 * 1024),
    ("1MiB", 1 * 1024 * 1024),
    ("8MiB", 8 * 1024 * 1024),
    ("32MiB", 32 * 1024 * 1024),
    ("100MiB", 100 * 1024 * 1024),
)


def deterministic_bytes(size_bytes: int, *, seed: str) -> bytes:
    """Expand a stable seed into exactly ``size_bytes`` bytes."""

    seed_bytes = seed.encode("utf-8")
    chunks = bytearray()
    counter = 0
    while len(chunks) < size_bytes:
        counter_bytes = counter.to_bytes(8, "big", signed=False)
        chunks.extend(hashlib.sha256(seed_bytes + counter_bytes).digest())
        counter += 1
    return bytes(chunks[:size_bytes])


def write_hashed_artifact(path: Path, *, seed: str, size_bytes: int) -> dict[str, Any]:
    """Write a deterministic artifact and its sidecar manifest."""

    payload = deterministic_bytes(size_bytes, seed=seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    manifest = {
        "path": path.name,
        "seed": seed,
        "size_bytes": size_bytes,
        "sha256": digest,
    }
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return manifest


def generate_artifact_tiers(root: Path, *, stem: str = "artifact") -> dict[str, dict[str, Any]]:
    """Materialize every benchmark tier deterministically under ``root``."""

    manifests: dict[str, dict[str, Any]] = {}
    for label, size_bytes in ARTIFACT_TIERS:
        path = root / f"{stem}-{label}.bin"
        manifests[label] = write_hashed_artifact(path, seed=f"{stem}:{label}", size_bytes=size_bytes)
    return manifests


def locked_by_ref_policy(size_bytes: int) -> str:
    """Return the audit mode for the locked by-reference validation policy."""

    return select_audit_mode(size_bytes, MANIFEST_ONLY_THRESHOLD_BYTES)


def validate_locked_by_ref_artifact(
    path: Path,
    *,
    manifest: Mapping[str, Any] | None = None,
    digest_reader: Callable[[Path], str] | None = None,
) -> dict[str, Any]:
    """Validate by content below 1 MiB and by sidecar manifest above it."""

    size_bytes = path.stat().st_size
    mode = locked_by_ref_policy(size_bytes)
    manifest_data = dict(manifest) if manifest is not None else json.loads(
        path.with_suffix(path.suffix + ".manifest.json").read_text(encoding="utf-8")
    )
    expected_sha = str(manifest_data["sha256"])
    if mode == "full":
        reader = digest_reader or _digest_file
        actual_sha = reader(path)
        if actual_sha != expected_sha:
            raise AssertionError(f"digest mismatch for {path.name}: {actual_sha} != {expected_sha}")
    return {
        "mode": mode,
        "size_bytes": size_bytes,
        "sha256": expected_sha,
        "manifest_path": str(path.with_suffix(path.suffix + ".manifest.json")),
    }


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()
