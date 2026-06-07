from __future__ import annotations

from pathlib import Path

import pytest

from .helpers import (
    ARTIFACT_TIERS,
    MANIFEST_ONLY_THRESHOLD_BYTES,
    generate_artifact_tiers,
    locked_by_ref_policy,
    validate_locked_by_ref_artifact,
)


def test_generate_artifact_tiers_is_deterministic(tmp_path: Path) -> None:
    first = generate_artifact_tiers(tmp_path / "first")
    second = generate_artifact_tiers(tmp_path / "second")

    assert tuple(first.keys()) == tuple(label for label, _ in ARTIFACT_TIERS)
    assert first["100MiB"]["sha256"] == second["100MiB"]["sha256"]
    assert first["64KiB"]["size_bytes"] == 64 * 1024


def test_locked_by_ref_policy_switches_to_manifest_above_threshold() -> None:
    assert locked_by_ref_policy(MANIFEST_ONLY_THRESHOLD_BYTES) == "full"
    assert locked_by_ref_policy(MANIFEST_ONLY_THRESHOLD_BYTES + 1) == "manifest"


def test_validate_locked_by_ref_artifact_uses_manifest_only_for_100mib(tmp_path: Path) -> None:
    manifests = generate_artifact_tiers(tmp_path)
    artifact = tmp_path / "artifact-100MiB.bin"
    calls: list[Path] = []

    def _unexpected_digest_reader(path: Path) -> str:
        calls.append(path)
        raise AssertionError("100MiB manifest validation should not rehash blob contents")

    result = validate_locked_by_ref_artifact(
        artifact,
        manifest=manifests["100MiB"],
        digest_reader=_unexpected_digest_reader,
    )

    assert result["mode"] == "manifest"
    assert result["sha256"] == manifests["100MiB"]["sha256"]
    assert calls == []


def test_validate_locked_by_ref_artifact_hashes_small_files(tmp_path: Path) -> None:
    manifests = generate_artifact_tiers(tmp_path)
    artifact = tmp_path / "artifact-64KiB.bin"
    calls: list[Path] = []

    def _digest_reader(path: Path) -> str:
        calls.append(path)
        return manifests["64KiB"]["sha256"]

    result = validate_locked_by_ref_artifact(
        artifact,
        manifest=manifests["64KiB"],
        digest_reader=_digest_reader,
    )

    assert result["mode"] == "full"
    assert calls == [artifact]


@pytest.mark.parametrize("label,size_bytes", ARTIFACT_TIERS)
def test_generated_manifest_matches_artifact_size(tmp_path: Path, label: str, size_bytes: int) -> None:
    manifests = generate_artifact_tiers(tmp_path)
    artifact = tmp_path / f"artifact-{label}.bin"

    assert artifact.stat().st_size == size_bytes
    assert manifests[label]["size_bytes"] == size_bytes
