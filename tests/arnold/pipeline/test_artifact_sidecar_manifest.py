"""Sidecar-manifest unit tests for large-artifact handoff (T9)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from arnold.pipeline.artifact_io import (
    ArtifactIOBlocked,
    validate_large_artifact_by_manifest,
)
from arnold.pipeline.artifacts import (
    LARGE_ARTIFACT_THRESHOLD_BYTES,
    SidecarManifest,
    read_sidecar_manifest,
    sidecar_path_for,
    stream_sha256,
    verify_sidecar_integrity,
    write_sidecar_manifest,
    write_versioned,
)


@dataclass
class _Ctx:
    artifact_root: str


@pytest.fixture
def ctx(tmp_path: Path) -> _Ctx:
    return _Ctx(artifact_root=str(tmp_path))


class TestSmallArtifactPathUnchanged:
    def test_small_write_emits_no_sidecar(self, ctx: _Ctx) -> None:
        dest = write_versioned(ctx, "stage", "label", "hi", "txt")
        assert dest.is_file()
        assert not sidecar_path_for(dest).exists()


class TestLargeArtifactStreamingHashAndManifest:
    def test_large_write_emits_sidecar(self, ctx: _Ctx) -> None:
        big = "x" * (LARGE_ARTIFACT_THRESHOLD_BYTES + 1024)
        dest = write_versioned(
            ctx,
            "stage",
            "label",
            big,
            "txt",
            content_type="text/plain",
            schema_hash="sha256:abc",
        )
        manifest = read_sidecar_manifest(dest)
        assert manifest is not None
        assert manifest.size == dest.stat().st_size
        assert manifest.sha256 == stream_sha256(dest)
        assert manifest.content_type == "text/plain"
        assert manifest.schema_hash == "sha256:abc"


class TestValidationReadsManifestOnly:
    def test_chokepoint_uses_manifest_not_blob(self, ctx: _Ctx) -> None:
        big = "y" * (LARGE_ARTIFACT_THRESHOLD_BYTES + 256)
        dest = write_versioned(
            ctx, "s", "l", big, "txt",
            content_type="text/plain", schema_hash="sha256:expected",
        )
        # No exception — lazy default, manifest is trusted.
        assert validate_large_artifact_by_manifest(
            dest, expected_schema_hash="sha256:expected"
        )

    def test_schema_hash_mismatch_blocks(self, ctx: _Ctx) -> None:
        big = "y" * (LARGE_ARTIFACT_THRESHOLD_BYTES + 16)
        dest = write_versioned(
            ctx, "s", "l", big, "txt",
            content_type="text/plain", schema_hash="sha256:A",
        )
        with pytest.raises(ArtifactIOBlocked):
            validate_large_artifact_by_manifest(
                dest, expected_schema_hash="sha256:B"
            )


class TestTamperDetectionOnConsumerOptIn:
    def test_recompute_catches_tamper(self, ctx: _Ctx) -> None:
        big = "z" * (LARGE_ARTIFACT_THRESHOLD_BYTES + 8)
        dest = write_versioned(
            ctx, "s", "l", big, "txt",
            content_type="text/plain", schema_hash="sha256:h",
        )
        # Tamper with the blob without updating the manifest.
        with open(dest, "ab") as fh:
            fh.write(b"!!!")
        with pytest.raises(ArtifactIOBlocked):
            validate_large_artifact_by_manifest(
                dest, expected_schema_hash="sha256:h", recompute_sha256=True
            )

    def test_lazy_default_does_not_recompute(self, ctx: _Ctx) -> None:
        big = "z" * (LARGE_ARTIFACT_THRESHOLD_BYTES + 8)
        dest = write_versioned(
            ctx, "s", "l", big, "txt",
            content_type="text/plain", schema_hash="sha256:h",
        )
        with open(dest, "ab") as fh:
            fh.write(b"!!!")
        # Lazy default trusts manifest, so no exception.
        assert validate_large_artifact_by_manifest(
            dest, expected_schema_hash="sha256:h"
        )


class TestMissingManifestBlocks:
    def test_missing_manifest_blocks(self, tmp_path: Path) -> None:
        blob = tmp_path / "v1.bin"
        blob.write_bytes(b"x" * 16)
        with pytest.raises(ArtifactIOBlocked):
            validate_large_artifact_by_manifest(
                blob, expected_schema_hash="sha256:h"
            )


class TestVerifySidecarIntegrity:
    def test_round_trip(self, tmp_path: Path) -> None:
        blob = tmp_path / "v1.bin"
        blob.write_bytes(b"hello" * 4096)
        write_sidecar_manifest(blob, content_type="application/octet-stream", schema_hash="")
        assert verify_sidecar_integrity(blob)
