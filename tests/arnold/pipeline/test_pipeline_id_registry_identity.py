from __future__ import annotations

import json

import pytest

from arnold.kernel import derive_pipeline_identity, derive_registry_runtime_id
from arnold.pipeline.pipeline_id_registry import (
    PipelineIdRegistryError,
    load_pipeline_id_registry,
    resolve_registry_runtime_identity,
)

MANIFEST_HASH = "sha256:" + "a" * 64


def _write_registry(tmp_path, pipelines):
    path = tmp_path / "pipeline_ids.json"
    path.write_text(json.dumps({"pipelines": pipelines}), encoding="utf-8")
    return path


def test_registry_validates_alias_then_derives_runtime_identity_from_alias_and_hash(tmp_path):
    path = _write_registry(
        tmp_path,
        [
            {
                "name": "planning",
                "stable_id": "legacy.stable.id",
                "typed_contract_capable": True,
                "manifest_hash": MANIFEST_HASH,
            }
        ],
    )
    registry = load_pipeline_id_registry(path)

    resolved = registry.resolve_runtime_identity("planning", MANIFEST_HASH)

    assert resolved.alias == "planning"
    assert resolved.manifest_hash == MANIFEST_HASH
    assert resolved.pipeline_identity == derive_pipeline_identity(
        "planning",
        MANIFEST_HASH,
    )
    assert resolved.registry_runtime_id == derive_registry_runtime_id(
        "planning",
        MANIFEST_HASH,
    )
    assert "legacy.stable.id" not in {
        resolved.pipeline_identity,
        resolved.registry_runtime_id,
    }


def test_registry_metadata_cannot_override_canonical_runtime_identity(tmp_path):
    path = _write_registry(
        tmp_path,
        [
            {
                "name": "planning",
                "stable_id": "sha256:" + "b" * 64,
                "previous_stable_ids": ["sha256:" + "c" * 64],
                "seam_ids": ["sha256:" + "d" * 64],
                "typed_contract_capable": True,
                "manifest_hash": MANIFEST_HASH,
                "pipeline_identity": "sha256:" + "e" * 64,
                "registry_runtime_id": "sha256:" + "f" * 64,
            }
        ],
    )
    registry = load_pipeline_id_registry(path)

    resolved = resolve_registry_runtime_identity(registry, "planning", MANIFEST_HASH)

    assert resolved.pipeline_identity == derive_pipeline_identity(
        "planning",
        MANIFEST_HASH,
    )
    assert resolved.registry_runtime_id == derive_registry_runtime_id(
        "planning",
        MANIFEST_HASH,
    )
    assert resolved.pipeline_identity != resolved.registry_entry["pipeline_identity"]
    assert resolved.registry_runtime_id != resolved.registry_entry["registry_runtime_id"]
    assert resolved.pipeline_identity not in {
        resolved.registry_entry["stable_id"],
        *resolved.registry_entry["previous_stable_ids"],
        *resolved.registry_entry["seam_ids"],
    }


def test_registry_helper_rejects_unknown_alias_without_using_stable_id(tmp_path):
    path = _write_registry(
        tmp_path,
        [
            {
                "name": "planning",
                "stable_id": "legacy.stable.id",
                "typed_contract_capable": True,
                "manifest_hash": MANIFEST_HASH,
            }
        ],
    )
    registry = load_pipeline_id_registry(path)

    with pytest.raises(PipelineIdRegistryError, match="not declared"):
        resolve_registry_runtime_identity(registry, "legacy.stable.id", MANIFEST_HASH)

    assert registry.resolve_runtime_identity(
        "planning",
        MANIFEST_HASH,
    ).pipeline_identity == derive_pipeline_identity("planning", MANIFEST_HASH)


def test_registry_helper_rejects_stale_registry_manifest_hash(tmp_path):
    path = _write_registry(
        tmp_path,
        [
            {
                "name": "planning",
                "stable_id": "planning",
                "typed_contract_capable": True,
                "manifest_hash": "sha256:" + "b" * 64,
            }
        ],
    )
    registry = load_pipeline_id_registry(path)

    with pytest.raises(PipelineIdRegistryError, match="does not match"):
        registry.resolve_runtime_identity("planning", MANIFEST_HASH)
