from __future__ import annotations

import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from arnold.pipelines.megaplan._core.canonical import canonical_projection_bytes, sha256_hex
from arnold.pipelines.megaplan._core.io import (
    journal_blob_promotion,
    prepare_journal_transaction,
    recover_journal,
    write_journal_commit_marker,
)
# legal_coercions was previously imported from the now-deleted
# arnold.pipelines.megaplan._pipeline.contracts module (M4 Step 5).
# The canonical check_capsule_contract no longer references this dict;
# we provide a local replacement so the test that exercises the legacy
# coercion-registration path still compiles and can be evaluated.
legal_coercions: dict[tuple[str, str], object] = {}
from arnold.pipelines.megaplan.schemas import (
    Capsule,
    CapsuleContract,
    CapsuleDefinition,
    CapsuleEvidence,
    CapsuleLineage,
)
from arnold.pipelines.megaplan.store import MultiStore, deterministic_idempotency_key
from arnold.pipelines.megaplan.store.blob import BlobRef, BlobStore, LocalDirBlobStore
from arnold.pipelines.megaplan.store.capsule import (
    CAPSULE_INDEX_ID_PREFIX,
    CAPSULE_RECORD_ID_PREFIX,
    CapsuleIntegrityError,
    CapsuleListingUnsupportedError,
    CapsuleStorageError,
    check_capsule_contract,
    build_capsule,
    capsule_index_blob_id,
    capsule_record_blob_id,
    capsule_record_content_type,
    capsule_record_for_payload,
    get_capsule,
    list_capsules,
    put_capsule_record,
    write_capsule,
)
from arnold.pipelines.megaplan.store.export import collect_epic_export, write_epic_export_tar
from arnold.pipelines.megaplan.store.file import FileStore


NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _capsule(capsule_hash: str | None = None) -> Capsule:
    digest = "a" * 64
    value = capsule_hash or f"sha256:{digest}"
    return Capsule(
        capsule_hash=value,
        definition=CapsuleDefinition(
            identity_hash="sha256:" + "b" * 64,
            static_behavioral_hash="sha256:" + "c" * 64,
            replay_ready=True,
        ),
        contract=CapsuleContract(
            manifest_abi="arnold.pipelines.megaplan.pipeline.behavioral.v1",
            static_behavioral_hash="sha256:" + "c" * 64,
        ),
        lineage=CapsuleLineage(capsule_hash=value, created_at=NOW),
        created_at=NOW,
    )


def _contract_capsule(**contract_overrides) -> Capsule:
    capsule = _capsule()
    contract_data = capsule.contract.model_dump(mode="json")
    contract_data.update(contract_overrides)
    capsule.contract = CapsuleContract(**contract_data)
    return capsule


def _store(tmp_path: Path) -> MultiStore:
    return MultiStore(
        file_store=FileStore(tmp_path / "file"),
        db_store=FileStore(tmp_path / "db"),
        actor_id="actor",
    )


def test_check_capsule_contract_accepts_declared_manifest_topology_ports_and_evidence(tmp_path: Path) -> None:
    blob_store = LocalDirBlobStore(tmp_path / "blobs")
    blob_store.put("evidence-blob", b"payload", content_type="text/plain")
    capsule = _contract_capsule(
        runtime_topology_hash="sha256:" + "d" * 64,
        port_expectations=[
            {"name": "summary", "kind": "produce", "content_type": "text/markdown"},
        ],
        evidence_refs=[
            {
                "evidence_id": "artifact",
                "payload_sha256": "sha256:" + "e" * 64,
                "payload_ref": {"blob_id": "evidence-blob"},
            }
        ],
    )
    capsule.evidence = [
        CapsuleEvidence(
            evidence_id="artifact",
            evidence_type="artifact",
            payload_ref={"blob_id": "evidence-blob"},
            payload_sha256="sha256:" + "e" * 64,
        )
    ]

    check = check_capsule_contract(
        capsule,
        {
            "manifest_abi": "arnold.pipelines.megaplan.pipeline.behavioral.v1",
            "static_behavioral_hash": "sha256:" + "c" * 64,
            "runtime_topology_hash": "sha256:" + "d" * 64,
            "ports": [{"name": "summary", "kind": "produce", "content_type": "text/markdown"}],
            "blob_store": blob_store,
        },
    )

    assert check.ok is True
    assert check.failures == ()
    assert check.adaptations == ()


def test_check_capsule_contract_reports_machine_readable_manifest_and_topology_mismatch() -> None:
    capsule = _contract_capsule(runtime_topology_hash="sha256:" + "d" * 64)

    with pytest.raises(CapsuleStorageError) as exc_info:
        check_capsule_contract(
            capsule,
            {
                "manifest_abi": "wrong-abi",
                "static_behavioral_hash": "sha256:" + "0" * 64,
                "runtime_topology_hash": "sha256:" + "1" * 64,
            },
        )

    details = exc_info.value.details
    assert details["error_kind"] == "manifest_abi_mismatch"
    assert details["wanted"] == "arnold.pipelines.megaplan.pipeline.behavioral.v1"
    assert details["have"] == "wrong-abi"
    assert details["legal_moves"] == ()
    assert [failure["error_kind"] for failure in details["failures"]] == [
        "manifest_abi_mismatch",
        "static_behavioral_hash_mismatch",
        "runtime_topology_hash_mismatch",
    ]


def test_check_capsule_contract_adapts_only_registered_legal_port_coercions() -> None:
    capsule = _contract_capsule(
        port_expectations=[
            {"name": "summary", "kind": "produce", "content_type": "text/markdown"},
        ]
    )
    legal_coercions[("text/plain", "text/markdown")] = lambda value: value
    try:
        check = check_capsule_contract(
            capsule,
            {"ports": [{"name": "summary", "kind": "produce", "content_type": "text/plain"}]},
        )
    finally:
        legal_coercions.pop(("text/plain", "text/markdown"), None)

    assert check.ok is True
    assert check.failures == ()
    assert check.adaptations == (
        {
            "kind": "content_type_coercion",
            "port": "summary",
            "wanted": "text/markdown",
            "have": "text/plain",
            "legal_moves": ({"from": "text/plain", "to": "text/markdown"},),
        },
    )


def test_check_capsule_contract_refuses_illegal_port_coercions() -> None:
    capsule = _contract_capsule(
        port_expectations=[
            {"name": "summary", "kind": "produce", "content_type": "text/markdown"},
        ]
    )

    with pytest.raises(CapsuleStorageError) as exc_info:
        check_capsule_contract(
            capsule,
            {"ports": [{"name": "summary", "kind": "produce", "content_type": "application/json"}]},
        )

    assert exc_info.value.details["error_kind"] == "port_content_type_mismatch"
    assert exc_info.value.details["wanted"]["content_type"] == "text/markdown"
    assert exc_info.value.details["have"]["content_type"] == "application/json"
    assert exc_info.value.details["legal_moves"] == ()


def test_check_capsule_contract_reports_missing_and_degraded_evidence(tmp_path: Path) -> None:
    capsule = _contract_capsule(
        evidence_refs=[
            {
                "evidence_id": "artifact",
                "payload_sha256": "sha256:" + "e" * 64,
                "payload_ref": {"blob_id": "missing-blob"},
            }
        ]
    )
    capsule.completeness = "degraded"
    capsule.evidence = [
        CapsuleEvidence(
            evidence_id="artifact",
            evidence_type="artifact",
            payload_ref={"blob_id": "missing-blob"},
            payload_sha256="sha256:" + "e" * 64,
        )
    ]

    check = check_capsule_contract(
        capsule,
        {"blob_store": LocalDirBlobStore(tmp_path / "blobs")},
        raise_on_failure=False,
    )

    assert check.ok is False
    assert [failure["error_kind"] for failure in check.failures] == [
        "capsule_evidence_degraded",
        "evidence_blob_missing",
    ]


def test_check_capsule_contract_ignores_absent_optional_environment_requirements() -> None:
    capsule = _contract_capsule()

    check = check_capsule_contract(capsule, {}, raise_on_failure=False)

    assert check.ok is True
    assert check.failures == ()


def test_check_capsule_contract_checks_declared_environment_requirements_only_from_runtime_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAPSULE_ENV_REQUIRED", "secret-from-process")
    capsule = _contract_capsule(
        repo_commit="abc123",
        model_version_requirements={"execute": "codex:gpt-5.5"},
        tool_version_requirements={"python": "3.12"},
        environment_variable_requirements={"CAPSULE_ENV_REQUIRED": "declared-value"},
        secret_shape_declarations={
            "OPENAI_API_KEY": {"kind": "api_key", "prefix": "sk-", "min_length": 20}
        },
    )

    check = check_capsule_contract(
        capsule,
        {
            "repo_commit": "abc123",
            "model_versions": {"execute": "codex:gpt-5.5"},
            "tool_versions": {"python": "3.12"},
            "environment_variables": {"CAPSULE_ENV_REQUIRED": "declared-value"},
            "secret_shapes": {
                "OPENAI_API_KEY": {"kind": "api_key", "prefix": "sk-", "min_length": 20}
            },
        },
    )

    assert check.ok is True
    assert check.failures == ()


def test_check_capsule_contract_reports_declared_environment_mismatches_without_secret_values() -> None:
    capsule = _contract_capsule(
        repo_commit="abc123",
        model_version_requirements={"execute": "codex:gpt-5.5"},
        tool_version_requirements={"python": "3.12"},
        environment_variable_requirements={"CAPSULE_ENV_REQUIRED": "declared-value"},
        secret_shape_declarations={
            "OPENAI_API_KEY": {"kind": "api_key", "prefix": "sk-", "min_length": 20}
        },
    )

    check = check_capsule_contract(
        capsule,
        {
            "repo_commit": "def456",
            "model_versions": {"execute": "codex:gpt-5.4"},
            "tool_versions": {},
            "environment_variables": {"CAPSULE_ENV_REQUIRED": "other-value"},
            "secret_shapes": {
                "OPENAI_API_KEY": {"kind": "api_key", "prefix": "sk-", "min_length": 8}
            },
        },
        raise_on_failure=False,
    )

    assert check.ok is False
    assert [failure["error_kind"] for failure in check.failures] == [
        "repo_commit_mismatch",
        "model_version_requirement_mismatch",
        "tool_version_requirement_mismatch",
        "environment_variable_requirement_mismatch",
        "secret_shape_requirement_mismatch",
    ]
    secret_failure = check.failures[-1]
    assert "sk-live-secret" not in json.dumps(secret_failure)
    assert secret_failure["wanted"] == {
        "OPENAI_API_KEY": {"kind": "api_key", "prefix": "sk-", "min_length": 20}
    }


def test_capsule_record_ids_are_flat_content_addressed_and_expected_id_is_enforced(tmp_path: Path) -> None:
    store = LocalDirBlobStore(tmp_path / "blobs")
    capsule = _capsule()
    record = capsule_record_for_payload(
        "capsule",
        capsule.model_dump(mode="json"),
        capsule_hash=capsule.capsule_hash,
    )

    blob_id = capsule_record_blob_id(record)

    assert blob_id.startswith(CAPSULE_RECORD_ID_PREFIX)
    assert "/" not in blob_id
    assert "\\" not in blob_id
    assert blob_id == f"{CAPSULE_RECORD_ID_PREFIX}{sha256_hex(canonical_projection_bytes(record))}"
    assert put_capsule_record(store, record, expected_blob_id=blob_id).blob_id == blob_id
    with pytest.raises(CapsuleIntegrityError) as exc_info:
        put_capsule_record(store, record, expected_blob_id=f"{CAPSULE_RECORD_ID_PREFIX}{'0' * 64}")
    assert exc_info.value.error_kind == "capsule_expected_id_mismatch"


def test_write_get_and_local_list_capsules_excludes_non_capsule_blobs(tmp_path: Path) -> None:
    store = LocalDirBlobStore(tmp_path / "blobs")
    capsule = _capsule()

    result = write_capsule(store, capsule)
    store.put("ordinary-image-blob", b"not a capsule", content_type="image/png")

    assert result.capsule_ref.blob_id.startswith(CAPSULE_RECORD_ID_PREFIX)
    assert result.index_blob_id == capsule_index_blob_id(capsule.capsule_hash)
    assert result.index_blob_id.startswith(CAPSULE_INDEX_ID_PREFIX)
    assert get_capsule(store, capsule.capsule_hash).capsule_hash == capsule.capsule_hash
    assert list_capsules(store) == [capsule.capsule_hash]


def test_generic_blob_store_rejects_listing_but_get_by_hash_remains_portable(tmp_path: Path) -> None:
    class MemoryBlobStore(BlobStore):
        def __init__(self) -> None:
            self.data: dict[str, tuple[bytes, str]] = {}

        def put(self, blob_id: str, content: bytes, *, content_type: str) -> BlobRef:
            self.data[blob_id] = (content, content_type)
            return BlobRef(blob_id=blob_id, content_type=content_type, size_bytes=len(content))

        def get(self, blob_id: str) -> bytes:
            return self.data[blob_id][0]

        def url(self, blob_id: str, *, signed: bool = False, ttl: int = 3600) -> str:
            return blob_id

        def delete(self, blob_id: str) -> None:
            self.data.pop(blob_id, None)

        def stat(self, blob_id: str):
            return None

    store = MemoryBlobStore()
    capsule = _capsule("sha256:" + "d" * 64)
    write_capsule(store, capsule)

    assert get_capsule(store, capsule.capsule_hash).capsule_hash == capsule.capsule_hash
    with pytest.raises(CapsuleListingUnsupportedError) as exc_info:
        list_capsules(store)
    assert exc_info.value.error_kind == "capsule_listing_unsupported"


def test_capsule_get_rejects_tampered_record_and_embedded_hash_mismatch(tmp_path: Path) -> None:
    store = LocalDirBlobStore(tmp_path / "blobs")
    capsule = _capsule()
    result = write_capsule(store, capsule)
    data_path = Path(store.url(result.capsule_ref.blob_id))
    record = json.loads(data_path.read_text(encoding="utf-8"))

    record["payload"]["metadata"] = {"tampered": True}
    data_path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")

    with pytest.raises(CapsuleIntegrityError) as exc_info:
        get_capsule(store, capsule.capsule_hash)
    assert exc_info.value.error_kind == "capsule_record_hash_mismatch"

    store = LocalDirBlobStore(tmp_path / "other-blobs")
    result = write_capsule(store, capsule)
    data_path = Path(store.url(result.capsule_ref.blob_id))
    record = json.loads(data_path.read_text(encoding="utf-8"))
    record["capsule_hash"] = "sha256:" + "e" * 64
    new_blob_id = capsule_record_blob_id(record)
    store.put(new_blob_id, canonical_projection_bytes(record), content_type=capsule_record_content_type("capsule"))
    index = {
        "schema_version": 1,
        "record_type": "index",
        "capsule_hash": capsule.capsule_hash,
        "capsule_record_blob_id": new_blob_id,
        "capsule_record_sha256": "sha256:" + new_blob_id.removeprefix(CAPSULE_RECORD_ID_PREFIX),
    }
    store.put(
        capsule_index_blob_id(capsule.capsule_hash),
        canonical_projection_bytes(index),
        content_type=capsule_record_content_type("index"),
    )

    with pytest.raises(CapsuleIntegrityError) as exc_info:
        get_capsule(store, capsule.capsule_hash)
    assert exc_info.value.error_kind == "capsule_hash_mismatch"


def test_capsule_blob_ids_are_recoverable_through_journal_replay_and_discard(tmp_path: Path) -> None:
    root = tmp_path / "blobs"
    store = LocalDirBlobStore(root)
    capsule = _capsule()
    record = capsule_record_for_payload(
        "capsule",
        capsule.model_dump(mode="json"),
        capsule_hash=capsule.capsule_hash,
    )
    record_blob_id = capsule_record_blob_id(record)
    index_blob_id = capsule_index_blob_id(capsule.capsule_hash)
    index = {
        "schema_version": 1,
        "record_type": "index",
        "capsule_hash": capsule.capsule_hash,
        "capsule_record_blob_id": record_blob_id,
        "capsule_record_sha256": "sha256:" + record_blob_id.removeprefix(CAPSULE_RECORD_ID_PREFIX),
    }

    replay_tx = f"blob-{record_blob_id}"
    prepare_journal_transaction(
        root,
        replay_tx,
        blobs=[
            journal_blob_promotion(
                root / record_blob_id,
                canonical_projection_bytes(record),
                extension="json",
                metadata={
                    "blob_id": record_blob_id,
                    "content_type": capsule_record_content_type("capsule"),
                    "size_bytes": len(canonical_projection_bytes(record)),
                    "updated_at": "2026-06-01T00:00:00Z",
                },
            )
        ],
    )
    write_journal_commit_marker(root, replay_tx)
    assert recover_journal(root)["replayed"] == [replay_tx]

    discard_tx = f"blob-{index_blob_id}"
    prepare_journal_transaction(
        root,
        discard_tx,
        blobs=[
            journal_blob_promotion(
                root / index_blob_id,
                canonical_projection_bytes(index),
                extension="json",
                metadata={
                    "blob_id": index_blob_id,
                    "content_type": capsule_record_content_type("index"),
                    "size_bytes": len(canonical_projection_bytes(index)),
                    "updated_at": "2026-06-01T00:00:00Z",
                },
            )
        ],
    )
    assert recover_journal(root)["discarded"] == [discard_tx]
    assert store.get(record_blob_id) == canonical_projection_bytes(record)
    assert store.stat(index_blob_id) is None


def test_build_capsule_collects_export_records_without_inlining_evidence_bytes(tmp_path: Path) -> None:
    epic_store = _store(tmp_path)
    epic = epic_store.create_epic(title="Capsule", goal="g", body="body", home_backend="file")
    plan = epic_store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="capsule-plan",
        idea="capsule",
        idempotency_key=deterministic_idempotency_key("capsule", epic.id, "plan"),
    )
    epic_store.write_plan_artifact(
        plan.id,
        "large.bin",
        b"x" * 4096,
        idempotency_key=deterministic_idempotency_key("capsule", plan.id, "artifact"),
    )
    blob_store = LocalDirBlobStore(tmp_path / "capsule-blobs")

    result = build_capsule(epic_store, epic.id, blob_store, created_by="test")
    capsule = get_capsule(blob_store, result.capsule.capsule_hash)

    assert capsule.completeness == "complete"
    assert result.record_refs["definition"].record_type == "definition"
    assert result.record_refs["contract"].record_type == "contract"
    assert result.record_refs["lineage"].record_type == "lineage"
    assert result.record_refs["capsule"].record_type == "capsule"
    assert list_capsules(blob_store) == [capsule.capsule_hash]
    artifact_evidence = [
        item for item in capsule.evidence if item.payload_ref.get("path", "").endswith("large.bin")
    ][0]
    assert artifact_evidence.payload_ref["size_bytes"] == 4096
    assert "bytes" not in artifact_evidence.payload_ref
    assert artifact_evidence.payload_sha256 is not None


def test_build_capsule_populates_only_caller_supplied_environment_contract_requirements(tmp_path: Path) -> None:
    epic_store = _store(tmp_path)
    epic = epic_store.create_epic(title="Capsule", goal="g", body="body", home_backend="file")
    blob_store = LocalDirBlobStore(tmp_path / "capsule-blobs")

    bare = build_capsule(epic_store, epic.id, blob_store)
    explicit = build_capsule(
        epic_store,
        epic.id,
        LocalDirBlobStore(tmp_path / "explicit-capsule-blobs"),
        repo_commit="abc123",
        model_version_requirements={"execute": "codex:gpt-5.5"},
        tool_version_requirements={"python": "3.12"},
        environment_variable_requirements={"CAPSULE_ENV_REQUIRED": "declared-value"},
        secret_shape_declarations={
            "OPENAI_API_KEY": {"kind": "api_key", "prefix": "sk-", "min_length": 20}
        },
    )

    assert bare.capsule.contract.repo_commit is None
    assert bare.capsule.contract.model_version_requirements == {}
    assert bare.capsule.contract.tool_version_requirements == {}
    assert bare.capsule.contract.environment_variable_requirements == {}
    assert bare.capsule.contract.secret_shape_declarations == {}
    assert explicit.capsule.contract.repo_commit == "abc123"
    assert explicit.capsule.contract.model_version_requirements == {"execute": "codex:gpt-5.5"}
    assert explicit.capsule.contract.tool_version_requirements == {"python": "3.12"}
    assert explicit.capsule.contract.environment_variable_requirements == {
        "CAPSULE_ENV_REQUIRED": "declared-value"
    }
    assert explicit.capsule.contract.secret_shape_declarations == {
        "OPENAI_API_KEY": {"kind": "api_key", "prefix": "sk-", "min_length": 20}
    }


def test_build_capsule_is_deterministic_and_preserves_legacy_export_bytes(tmp_path: Path) -> None:
    epic_store = _store(tmp_path)
    epic = epic_store.create_epic(title="Capsule", goal="g", body="body", home_backend="file")
    plan = epic_store.create_plan(
        sprint_id=None,
        epic_id=epic.id,
        name="capsule-plan",
        idea="capsule",
        idempotency_key=deterministic_idempotency_key("capsule", epic.id, "plan"),
    )
    epic_store.write_plan_artifact(
        plan.id,
        "large.bin",
        b"x" * 8192,
        idempotency_key=deterministic_idempotency_key("capsule", plan.id, "artifact"),
    )
    before_export = collect_epic_export(epic_store, epic.id)
    before_tar = tmp_path / "before.tar"
    after_tar = tmp_path / "after.tar"
    first_capsule_blobs = LocalDirBlobStore(tmp_path / "first-capsule-blobs")
    second_capsule_blobs = LocalDirBlobStore(tmp_path / "second-capsule-blobs")

    before_result = write_epic_export_tar(before_export, before_tar)
    first = build_capsule(
        epic_store,
        epic.id,
        first_capsule_blobs,
        created_by="test",
        metadata={"purpose": "regression"},
    )
    second = build_capsule(
        epic_store,
        epic.id,
        second_capsule_blobs,
        created_by="test",
        metadata={"purpose": "regression"},
    )
    after_export = collect_epic_export(epic_store, epic.id)
    after_result = write_epic_export_tar(after_export, after_tar)

    assert before_export["manifest"] == after_export["manifest"]
    assert before_result["sha256"] == after_result["sha256"]
    assert before_tar.read_bytes() == after_tar.read_bytes()
    assert first.capsule.model_dump(mode="json") == second.capsule.model_dump(mode="json")
    assert {key: ref.blob_id for key, ref in first.record_refs.items()} == {
        key: ref.blob_id for key, ref in second.record_refs.items()
    }
    with tarfile.open(before_tar, "r") as tar:
        assert all(not name.startswith("capsule") for name in tar.getnames())


def test_build_capsule_fails_loud_on_export_errors_unless_missing_blobs_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_export(_store: object, epic_id: str, *, allow_missing_blobs: bool = False) -> dict:
        return {
            "epic_id": epic_id,
            "files": [],
            "manifest": {
                "format": "megaplan-epic-export-v1",
                "epic_id": epic_id,
                "file_count": 0,
                "files": [],
                "warnings": [],
                "errors": [{"error": "blob_store_unavailable"}],
            },
            "warnings": [],
            "errors": [{"error": "blob_store_unavailable"}],
        }

    monkeypatch.setattr("arnold.pipelines.megaplan.store.capsule.collect_epic_export", fake_export)
    blob_store = LocalDirBlobStore(tmp_path / "capsule-blobs")

    with pytest.raises(CapsuleStorageError) as exc_info:
        build_capsule(object(), "epic-1", blob_store)
    assert exc_info.value.error_kind == "capsule_export_errors"

    result = build_capsule(object(), "epic-1", blob_store, allow_missing_blobs=True)
    assert result.capsule.completeness == "degraded"
    assert get_capsule(blob_store, result.capsule.capsule_hash).completeness == "degraded"


def test_build_capsule_missing_blob_fails_by_default_and_degrades_only_when_allowed(tmp_path: Path) -> None:
    epic_store = _store(tmp_path)
    epic = epic_store.create_epic(title="Capsule", goal="g", body="![alt](mp://image/diagram)", home_backend="file")
    image = epic_store.attach_image(
        epic_id=epic.id,
        content=b"image-bytes",
        content_type="image/png",
        reference_key="diagram",
        idempotency_key=deterministic_idempotency_key("capsule", epic.id, "missing-image"),
    )
    epic_store.file.blobs.delete(image.blob_id)

    with pytest.raises(CapsuleStorageError) as exc_info:
        build_capsule(epic_store, epic.id, LocalDirBlobStore(tmp_path / "strict-blobs"))
    assert exc_info.value.error_kind == "capsule_export_errors"
    assert exc_info.value.details["errors"][0]["blob_id"] == image.blob_id

    result = build_capsule(
        epic_store,
        epic.id,
        LocalDirBlobStore(tmp_path / "degraded-blobs"),
        allow_missing_blobs=True,
    )
    assert result.capsule.completeness == "degraded"
    assert result.capsule.metadata["export_warning_count"] == 1
    assert result.capsule.metadata["export_error_count"] == 0


def test_build_capsule_keeps_allow_degraded_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_export(_store: object, epic_id: str, *, allow_missing_blobs: bool = False) -> dict:
        assert allow_missing_blobs is True
        return {
            "epic_id": epic_id,
            "files": [],
            "manifest": {
                "format": "megaplan-epic-export-v1",
                "epic_id": epic_id,
                "file_count": 0,
                "files": [],
                "warnings": [],
                "errors": [{"error": "blob_store_unavailable"}],
            },
            "warnings": [],
            "errors": [{"error": "blob_store_unavailable"}],
        }

    monkeypatch.setattr("arnold.pipelines.megaplan.store.capsule.collect_epic_export", fake_export)

    result = build_capsule(
        object(),
        "epic-1",
        LocalDirBlobStore(tmp_path / "alias-blobs"),
        allow_degraded=True,
    )

    assert result.capsule.completeness == "degraded"
