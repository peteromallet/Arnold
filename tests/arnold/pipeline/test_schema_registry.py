from __future__ import annotations

import json

import pytest

from arnold.pipeline.contract_validation import validate_contract_result
from arnold.pipeline.schema_registry import (
    AcceptedVersionRange,
    ContractSchemaRegistry,
    SchemaRegistryError,
    accepts_version,
    canonical_schema_bytes,
)
from arnold.pipeline.types import ContractResult


def test_register_retrieve_and_index_writes_use_canonical_blob_paths(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    schema = {
        "type": "object",
        "required": ["name"],
        "properties": {"name": {"type": "string"}},
        "additionalProperties": False,
    }

    version = registry.register("demo", schema)
    digest = version.removeprefix("sha256:")
    blob_path = tmp_path / ".contract_schemas" / "sha256" / f"{digest}.json"
    index_path = tmp_path / ".contract_schemas" / "index.json"

    assert blob_path.read_bytes() == canonical_schema_bytes(schema)
    assert json.loads(index_path.read_text(encoding="utf-8")) == {"demo": [version]}
    assert registry.get_schema(digest) == schema
    assert registry.latest("demo") == version
    assert registry.history("demo") == (version,)


def test_register_retains_changed_schemas_and_old_schema_still_validates_contracts(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    v1_schema = {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "integer"}},
        "additionalProperties": False,
    }
    v2_schema = {
        "type": "object",
        "required": ["answer", "source"],
        "properties": {
            "answer": {"type": "integer"},
            "source": {"type": "string"},
        },
        "additionalProperties": False,
    }

    v1 = registry.register("demo", v1_schema)
    v2 = registry.register("demo", v2_schema)
    old_contract = ContractResult(payload={"answer": 42}, schema_version=v1)

    assert registry.history("demo") == (v1, v2)
    assert registry.get_schema(v1) == v1_schema
    assert registry.get_schema(v2) == v2_schema
    assert validate_contract_result(old_contract, registry.get_schema(v1)).ok


def test_existing_hash_reuse_requires_matching_canonical_bytes(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}}

    version = registry.register("demo", schema)
    digest = version.removeprefix("sha256:")
    blob_path = tmp_path / ".contract_schemas" / "sha256" / f"{digest}.json"

    assert registry.register("demo", {"properties": {"x": {"type": "integer"}}, "type": "object"}) == version

    blob_path.write_bytes(b'{"type":"object","properties":{"x":{"type":"string"}}}')
    with pytest.raises(SchemaRegistryError, match="pre-existing schema blob mismatch"):
        registry.register("other", schema)


def test_index_reads_observe_complete_old_or_new_json_during_updates(tmp_path, monkeypatch) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    before_replace_snapshots: list[dict[str, list[str]]] = []

    original_write_json_atomic = registry._write_json_atomic

    def recording_write_json_atomic(path, value) -> None:
        if path.exists():
            before_replace_snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        else:
            before_replace_snapshots.append({})
        original_write_json_atomic(path, value)

    monkeypatch.setattr(registry, "_write_json_atomic", recording_write_json_atomic)

    v1 = registry.register("demo", {"type": "object", "properties": {"v": {"const": 1}}})
    v2 = registry.register("demo", {"type": "object", "properties": {"v": {"const": 2}}})

    assert before_replace_snapshots == [{}, {"demo": [v1]}]
    assert json.loads(registry.index_path.read_text(encoding="utf-8")) == {"demo": [v1, v2]}


def test_contract_result_from_json_compatibility_is_m1_owned_manual_lookup_works_now(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    schema = {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "integer"}},
        "additionalProperties": False,
    }
    version = registry.register("demo", schema)
    contract = ContractResult.from_json({"payload": {"answer": 7}})

    # M0b validates via manual registry lookup; payload-hash/from_json compatibility wiring is M1 work.
    assert contract.schema_version != version
    assert validate_contract_result(contract, registry.get_schema(version)).ok


def test_accepts_version_uses_inclusive_logical_type_history_bounds(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    v1 = registry.register("demo", {"type": "object", "properties": {"v": {"const": 1}}})
    v2 = registry.register("demo", {"type": "object", "properties": {"v": {"const": 2}}})
    v3 = registry.register("demo", {"type": "object", "properties": {"v": {"const": 3}}})

    accepted = AcceptedVersionRange("demo", min_version=v1, max_version=v2)

    assert accepts_version("demo", v1, accepted, registry=registry) is True
    assert accepts_version("demo", v2, accepted, registry=registry) is True
    assert accepts_version("demo", v3, accepted, registry=registry) is False


def test_accepts_version_rejects_hash_only_registered_under_other_logical_type(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    shared_schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
    other_version = registry.register("other", shared_schema)
    registry.register("demo", {"type": "object", "properties": {"y": {"type": "integer"}}})

    accepted = AcceptedVersionRange("demo")

    assert accepts_version("demo", other_version, accepted, registry=registry) is False


def test_accepts_version_rejects_bounds_missing_from_logical_type_history(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    version = registry.register("demo", {"type": "object"})
    foreign_version = registry.register("other", {"type": "array"})

    with pytest.raises(SchemaRegistryError, match="min_version"):
        accepts_version(
            "demo",
            version,
            AcceptedVersionRange("demo", min_version=foreign_version),
            registry=registry,
        )


def test_accepts_version_rejects_mismatched_range_logical_type(tmp_path) -> None:
    registry = ContractSchemaRegistry(tmp_path)
    version = registry.register("demo", {"type": "object"})

    with pytest.raises(SchemaRegistryError, match="must match"):
        accepts_version(
            "demo",
            version,
            AcceptedVersionRange("other"),
            registry=registry,
        )
