"""Content-addressed Capsule record storage over the existing BlobStore."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any, Literal, Mapping

from arnold_pipelines.megaplan._core.canonical import canonical_projection_bytes, sha256_hex, sha256_uri
from arnold_pipelines.megaplan.capsule_projection import capsule_definition_identity_projection
from arnold.pipeline.contracts import is_legal_coercion
from arnold_pipelines.megaplan.schemas import (
    Capsule,
    CapsuleContract,
    CapsuleDefinition,
    CapsuleEvidence,
    CapsuleLineage,
)

from .blob import BlobMissingError, BlobStore, LocalDirBlobStore
from .export import collect_epic_export


CAPSULE_RECORD_ID_PREFIX = "capsule-record-sha256-"
CAPSULE_INDEX_ID_PREFIX = "capsule-index-sha256-"
CAPSULE_CONTENT_TYPE = "application/vnd.megaplan.capsule+json"
CAPSULE_RECORD_TYPES = {"definition", "contract", "lineage", "evidence", "capsule"}
_HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")
CAPSULE_DETERMINISTIC_CREATED_AT = datetime(1970, 1, 1, tzinfo=timezone.utc)


class CapsuleStorageError(ValueError):
    """Base class for machine-readable Capsule storage failures."""

    def __init__(self, error_kind: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.error_kind = error_kind
        self.details = {"error_kind": error_kind, **details}


class CapsuleIntegrityError(CapsuleStorageError):
    """Raised when Capsule bytes do not match their content-addressed identity."""


class CapsuleListingUnsupportedError(CapsuleStorageError):
    """Raised when a BlobStore backend cannot locally list Capsule index records."""


class CapsuleContractError(CapsuleStorageError):
    """Raised when a Capsule Contract is not satisfied by the runtime context."""


@dataclass(frozen=True)
class CapsuleRecordRef:
    capsule_hash: str
    record_type: str
    record_hash: str
    blob_id: str
    content_type: str


@dataclass(frozen=True)
class CapsuleWriteResult:
    capsule_hash: str
    capsule_ref: CapsuleRecordRef
    index_blob_id: str


@dataclass(frozen=True)
class CapsuleBuildResult:
    capsule: Capsule
    write_result: CapsuleWriteResult
    record_refs: Mapping[str, CapsuleRecordRef]


@dataclass(frozen=True)
class CapsuleContractCheck:
    ok: bool
    failures: tuple[dict[str, Any], ...] = ()
    adaptations: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CapsuleInspection:
    capsule: Capsule
    contract_check: CapsuleContractCheck
    summary: Mapping[str, Any]


def _hash_hex_from_uri(value: str) -> str:
    return value.removeprefix("sha256:")


def _validate_flat_hash_id(blob_id: str, *, prefix: str) -> str:
    if "/" in blob_id or "\\" in blob_id:
        raise CapsuleIntegrityError(
            "unsafe_capsule_blob_id",
            "Capsule blob IDs must be flat and slash-free",
            blob_id=blob_id,
        )
    if not blob_id.startswith(prefix):
        raise CapsuleIntegrityError(
            "unexpected_capsule_blob_id",
            "Capsule blob ID has the wrong prefix",
            blob_id=blob_id,
            expected_prefix=prefix,
        )
    digest = blob_id[len(prefix) :]
    if _HEX_64_RE.fullmatch(digest) is None:
        raise CapsuleIntegrityError(
            "invalid_capsule_blob_hash",
            "Capsule blob ID must end with a SHA-256 hex digest",
            blob_id=blob_id,
        )
    return digest


def capsule_record_blob_id(record: Mapping[str, Any]) -> str:
    """Return the flat content-addressed blob ID for a Capsule record."""
    return f"{CAPSULE_RECORD_ID_PREFIX}{sha256_hex(canonical_projection_bytes(record))}"


def capsule_index_blob_id(capsule_hash: str) -> str:
    """Return the flat local-list index blob ID for a Capsule hash."""
    digest = _hash_hex_from_uri(capsule_hash)
    if _HEX_64_RE.fullmatch(digest) is None:
        raise CapsuleIntegrityError(
            "invalid_capsule_hash",
            "Capsule hash must be a sha256 URI or bare SHA-256 hex digest",
            capsule_hash=capsule_hash,
        )
    return f"{CAPSULE_INDEX_ID_PREFIX}{digest}"


def capsule_record_content_type(record_type: str) -> str:
    return f"{CAPSULE_CONTENT_TYPE}; record={record_type}"


def capsule_record_for_payload(
    record_type: Literal["definition", "contract", "lineage", "evidence", "capsule"],
    payload: Mapping[str, Any],
    *,
    capsule_hash: str,
) -> dict[str, Any]:
    if record_type not in CAPSULE_RECORD_TYPES:
        raise CapsuleIntegrityError(
            "unsupported_capsule_record_type",
            "Unsupported Capsule record type",
            record_type=record_type,
        )
    return {
        "schema_version": 1,
        "record_type": record_type,
        "capsule_hash": capsule_hash,
        "payload": dict(payload),
    }


def _decode_record_bytes(content: bytes, *, blob_id: str) -> dict[str, Any]:
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CapsuleIntegrityError(
            "invalid_capsule_record_json",
            "Capsule record content is not valid UTF-8 JSON",
            blob_id=blob_id,
        ) from exc
    if not isinstance(data, dict):
        raise CapsuleIntegrityError(
            "invalid_capsule_record_shape",
            "Capsule record content must be a JSON object",
            blob_id=blob_id,
        )
    return data


def verify_capsule_record(
    record: Mapping[str, Any],
    *,
    expected_blob_id: str,
    expected_capsule_hash: str | None = None,
    expected_record_type: str | None = None,
) -> CapsuleRecordRef:
    expected_digest = _validate_flat_hash_id(expected_blob_id, prefix=CAPSULE_RECORD_ID_PREFIX)
    actual_digest = sha256_hex(canonical_projection_bytes(record))
    if actual_digest != expected_digest:
        raise CapsuleIntegrityError(
            "capsule_record_hash_mismatch",
            "Capsule record bytes do not match the requested blob ID",
            expected_blob_id=expected_blob_id,
            actual_sha256=actual_digest,
        )
    record_type = record.get("record_type")
    if not isinstance(record_type, str) or record_type not in CAPSULE_RECORD_TYPES:
        raise CapsuleIntegrityError(
            "invalid_capsule_record_type",
            "Capsule record has an invalid record_type",
            expected_blob_id=expected_blob_id,
            record_type=record_type,
        )
    if expected_record_type is not None and record_type != expected_record_type:
        raise CapsuleIntegrityError(
            "capsule_record_type_mismatch",
            "Capsule record type does not match the requested type",
            expected_record_type=expected_record_type,
            actual_record_type=record_type,
        )
    capsule_hash = record.get("capsule_hash")
    if not isinstance(capsule_hash, str):
        raise CapsuleIntegrityError(
            "missing_capsule_hash",
            "Capsule record is missing capsule_hash",
            expected_blob_id=expected_blob_id,
        )
    if expected_capsule_hash is not None and capsule_hash != expected_capsule_hash:
        raise CapsuleIntegrityError(
            "capsule_hash_mismatch",
            "Capsule record capsule_hash does not match the requested hash",
            expected_capsule_hash=expected_capsule_hash,
            actual_capsule_hash=capsule_hash,
        )
    return CapsuleRecordRef(
        capsule_hash=capsule_hash,
        record_type=record_type,
        record_hash=f"sha256:{actual_digest}",
        blob_id=expected_blob_id,
        content_type=capsule_record_content_type(record_type),
    )


def put_capsule_record(
    blob_store: BlobStore,
    record: Mapping[str, Any],
    *,
    expected_blob_id: str | None = None,
) -> CapsuleRecordRef:
    blob_id = capsule_record_blob_id(record)
    if expected_blob_id is not None and expected_blob_id != blob_id:
        raise CapsuleIntegrityError(
            "capsule_expected_id_mismatch",
            "Caller-supplied Capsule blob ID does not match canonical record bytes",
            expected_blob_id=expected_blob_id,
            actual_blob_id=blob_id,
        )
    ref = verify_capsule_record(record, expected_blob_id=blob_id)
    blob_store.put(
        blob_id,
        canonical_projection_bytes(record),
        content_type=ref.content_type,
    )
    return ref


def _put_capsule_index(blob_store: BlobStore, *, capsule_hash: str, capsule_ref: CapsuleRecordRef) -> str:
    blob_id = capsule_index_blob_id(capsule_hash)
    record = {
        "schema_version": 1,
        "record_type": "index",
        "capsule_hash": capsule_hash,
        "capsule_record_blob_id": capsule_ref.blob_id,
        "capsule_record_sha256": capsule_ref.record_hash,
    }
    blob_store.put(
        blob_id,
        canonical_projection_bytes(record),
        content_type=capsule_record_content_type("index"),
    )
    return blob_id


def write_capsule(blob_store: BlobStore, capsule: Capsule) -> CapsuleWriteResult:
    """Write a top-level Capsule record and a local-list index record."""
    payload = capsule.model_dump(mode="json")
    record = capsule_record_for_payload("capsule", payload, capsule_hash=capsule.capsule_hash)
    capsule_ref = put_capsule_record(blob_store, record)
    index_blob_id = _put_capsule_index(
        blob_store,
        capsule_hash=capsule.capsule_hash,
        capsule_ref=capsule_ref,
    )
    return CapsuleWriteResult(
        capsule_hash=capsule.capsule_hash,
        capsule_ref=capsule_ref,
        index_blob_id=index_blob_id,
    )


def _export_manifest_hash(collected: Mapping[str, Any]) -> str:
    return sha256_uri(canonical_projection_bytes(collected["manifest"]))


def _export_evidence(collected: Mapping[str, Any]) -> list[CapsuleEvidence]:
    evidence: list[CapsuleEvidence] = []
    for entry in collected["manifest"]["files"]:
        payload_ref = {
            "path": entry["path"],
            "kind": entry["kind"],
            "sha256": f"sha256:{entry['sha256']}",
            "size_bytes": entry["size_bytes"],
        }
        for key in ("plan_id", "artifact_name", "image_id", "blob_id", "content_type"):
            if key in entry:
                payload_ref[key] = entry[key]
        evidence.append(
            CapsuleEvidence(
                evidence_id=f"export-file:{entry['path']}",
                evidence_type=entry["kind"],
                payload_ref=payload_ref,
                payload_sha256=f"sha256:{entry['sha256']}",
                summary=f"{entry['kind']} at {entry['path']}",
            )
        )
    evidence.append(
        CapsuleEvidence(
            evidence_id="export-manifest",
            evidence_type="export_manifest",
            payload_ref={
                "path": "manifest.json",
                "kind": "manifest",
                "sha256": _export_manifest_hash(collected),
                "size_bytes": len(canonical_projection_bytes(collected["manifest"])),
            },
            payload_sha256=_export_manifest_hash(collected),
            summary="Deterministic epic export manifest",
            metadata={
                "warning_count": len(collected.get("warnings") or []),
                "error_count": len(collected.get("errors") or []),
            },
        )
    )
    return evidence


def _capsule_hash_payload(
    *,
    definition: CapsuleDefinition,
    contract: CapsuleContract,
    lineage: CapsuleLineage,
    evidence: list[CapsuleEvidence],
    completeness: str,
    replay_ready: bool,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "definition": definition.model_dump(mode="json"),
        "contract": contract.model_dump(mode="json"),
        "lineage": lineage.model_dump(mode="json"),
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "completeness": completeness,
        "replay_ready": replay_ready,
        "metadata": dict(metadata),
    }


def build_capsule(
    epic_store: Any,
    epic_id: str,
    blob_store: BlobStore,
    *,
    allow_missing_blobs: bool = False,
    allow_degraded: bool | None = None,
    created_by: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    repo_commit: str | None = None,
    model_version_requirements: Mapping[str, Any] | None = None,
    tool_version_requirements: Mapping[str, Any] | None = None,
    environment_variable_requirements: Mapping[str, Any] | None = None,
    secret_shape_declarations: Mapping[str, Any] | None = None,
) -> CapsuleBuildResult:
    """Collect an epic export, build Capsule records, and persist them.

    Export collection remains read-only.  Evidence records reference export
    member paths and hashes rather than embedding their byte payloads.
    """
    degraded_allowed = allow_missing_blobs if allow_degraded is None else allow_degraded
    collected = collect_epic_export(
        epic_store,
        epic_id,
        allow_missing_blobs=degraded_allowed,
    )
    errors = list(collected.get("errors") or [])
    warnings = list(collected.get("warnings") or [])
    if errors and not degraded_allowed:
        raise CapsuleStorageError(
            "capsule_export_errors",
            "Epic export produced errors; pass allow_missing_blobs=True to emit a degraded Capsule",
            epic_id=epic_id,
            errors=errors,
        )

    export_hash = _export_manifest_hash(collected)
    identity = capsule_definition_identity_projection(
        static_behavioral_hash=export_hash,
        runtime_topology_hash=None,
    )
    replay_ready = False
    completeness = "degraded" if errors or warnings else "complete"
    definition = CapsuleDefinition(
        identity_hash=str(identity["definition_identity_hash"]),
        static_behavioral_hash=export_hash,
        manifest=collected["manifest"],
        intent={"epic_id": epic_id},
        routing={"source": "collect_epic_export"},
        unresolved_static_inputs=[],
        replay_ready=replay_ready,
    )
    evidence = _export_evidence(collected)
    contract = CapsuleContract(
        manifest_abi=collected["manifest"]["format"],
        static_behavioral_hash=export_hash,
        evidence_refs=[
            {
                "evidence_id": item.evidence_id,
                "payload_sha256": item.payload_sha256,
                "payload_ref": item.payload_ref,
            }
            for item in evidence
        ],
        repo_commit=repo_commit,
        model_version_requirements=dict(model_version_requirements or {}),
        tool_version_requirements=dict(tool_version_requirements or {}),
        environment_variable_requirements=dict(environment_variable_requirements or {}),
        secret_shape_declarations=dict(secret_shape_declarations or {}),
        environment_requirements={"store_export_format": collected["manifest"]["format"]},
    )
    lineage = CapsuleLineage(
        parent_edges=[],
        ancestors=[],
        created_by=created_by,
        created_at=CAPSULE_DETERMINISTIC_CREATED_AT,
    )
    capsule_metadata = {
        "epic_id": epic_id,
        "export_manifest_sha256": export_hash,
        "export_warning_count": len(warnings),
        "export_error_count": len(errors),
        **dict(metadata or {}),
    }
    capsule_hash = sha256_uri(
        canonical_projection_bytes(
            _capsule_hash_payload(
                definition=definition,
                contract=contract,
                lineage=lineage,
                evidence=evidence,
                completeness=completeness,
                replay_ready=replay_ready,
                metadata=capsule_metadata,
            )
        )
    )
    lineage.capsule_hash = capsule_hash
    capsule = Capsule(
        capsule_hash=capsule_hash,
        definition=definition,
        contract=contract,
        lineage=lineage,
        evidence=evidence,
        completeness=completeness,
        replay_ready=replay_ready,
        created_at=CAPSULE_DETERMINISTIC_CREATED_AT,
        metadata=capsule_metadata,
    )

    record_refs: dict[str, CapsuleRecordRef] = {}
    for record_type, payload in (
        ("definition", capsule.definition.model_dump(mode="json")),
        ("contract", capsule.contract.model_dump(mode="json")),
        ("lineage", capsule.lineage.model_dump(mode="json")),
    ):
        record_refs[record_type] = put_capsule_record(
            blob_store,
            capsule_record_for_payload(record_type, payload, capsule_hash=capsule_hash),
        )
    for item in capsule.evidence:
        record_refs[item.evidence_id] = put_capsule_record(
            blob_store,
            capsule_record_for_payload(
                "evidence",
                item.model_dump(mode="json"),
                capsule_hash=capsule_hash,
            ),
        )
    write_result = write_capsule(blob_store, capsule)
    record_refs["capsule"] = write_result.capsule_ref
    return CapsuleBuildResult(
        capsule=capsule,
        write_result=write_result,
        record_refs=record_refs,
    )


def _read_capsule_index(blob_store: BlobStore, capsule_hash: str) -> dict[str, Any]:
    blob_id = capsule_index_blob_id(capsule_hash)
    data = _decode_record_bytes(blob_store.get(blob_id), blob_id=blob_id)
    if data.get("record_type") != "index":
        raise CapsuleIntegrityError(
            "capsule_index_type_mismatch",
            "Capsule index record has the wrong record_type",
            index_blob_id=blob_id,
            actual_record_type=data.get("record_type"),
        )
    if data.get("capsule_hash") != capsule_hash:
        raise CapsuleIntegrityError(
            "capsule_index_hash_mismatch",
            "Capsule index points at a different capsule_hash",
            index_blob_id=blob_id,
            expected_capsule_hash=capsule_hash,
            actual_capsule_hash=data.get("capsule_hash"),
        )
    record_blob_id = data.get("capsule_record_blob_id")
    if not isinstance(record_blob_id, str):
        raise CapsuleIntegrityError(
            "capsule_index_missing_record_ref",
            "Capsule index is missing capsule_record_blob_id",
            index_blob_id=blob_id,
        )
    _validate_flat_hash_id(record_blob_id, prefix=CAPSULE_RECORD_ID_PREFIX)
    return data


def get_capsule(blob_store: BlobStore, capsule_hash: str) -> Capsule:
    """Read a Capsule by hash and verify both index and record integrity."""
    index = _read_capsule_index(blob_store, capsule_hash)
    record_blob_id = index["capsule_record_blob_id"]
    record = _decode_record_bytes(blob_store.get(record_blob_id), blob_id=record_blob_id)
    verify_capsule_record(
        record,
        expected_blob_id=record_blob_id,
        expected_capsule_hash=capsule_hash,
        expected_record_type="capsule",
    )
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise CapsuleIntegrityError(
            "capsule_record_missing_payload",
            "Capsule record is missing its payload object",
            expected_blob_id=record_blob_id,
        )
    capsule = Capsule(**payload)
    if capsule.capsule_hash != capsule_hash:
        raise CapsuleIntegrityError(
            "capsule_payload_hash_mismatch",
            "Capsule payload hash does not match the requested hash",
            expected_capsule_hash=capsule_hash,
            actual_capsule_hash=capsule.capsule_hash,
        )
    return capsule


def _field_value(item: Any, *names: str) -> Any:
    if isinstance(item, Mapping):
        for name in names:
            if name in item:
                return item[name]
        return None
    for name in names:
        if hasattr(item, name):
            return getattr(item, name)
    return None


def _port_key(item: Any) -> tuple[str | None, str | None]:
    return (
        _field_value(item, "name", "port_name"),
        _field_value(item, "kind", "direction", "role", "port_kind"),
    )


def _content_type(item: Any) -> str | None:
    value = _field_value(item, "content_type")
    return value if isinstance(value, str) and value else None


def _failure(error_kind: str, *, wanted: Any, have: Any, legal_moves: Any = ()) -> dict[str, Any]:
    return {
        "error_kind": error_kind,
        "wanted": wanted,
        "have": have,
        "legal_moves": tuple(legal_moves),
    }


def _declared_runtime_ports(runtime_context: Mapping[str, Any]) -> list[Any]:
    ports = runtime_context.get("ports")
    if ports is None:
        ports = runtime_context.get("port_expectations")
    if ports is None:
        return []
    return list(ports)


def _runtime_value(runtime_context: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in runtime_context:
            return runtime_context[key]
    return None


def _mapping_value(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _merged_requirements(*values: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for value in values:
        merged.update(dict(value))
    return merged


def _compare_mapping_requirements(
    failures: list[dict[str, Any]],
    *,
    error_kind: str,
    wanted: Mapping[str, Any],
    have: Mapping[str, Any] | None,
) -> None:
    if not wanted:
        return
    if have is None:
        failures.append(_failure(error_kind, wanted=dict(wanted), have=None))
        return
    for name, expected in wanted.items():
        actual = have.get(name)
        if actual != expected:
            failures.append(
                _failure(
                    error_kind,
                    wanted={name: expected},
                    have={name: actual} if name in have else None,
                )
            )


def _declared_evidence_refs(capsule: Capsule) -> list[Mapping[str, Any]]:
    if capsule.contract.evidence_refs:
        return [ref for ref in capsule.contract.evidence_refs if isinstance(ref, Mapping)]
    refs: list[Mapping[str, Any]] = []
    for item in capsule.evidence:
        refs.append(
            {
                "evidence_id": item.evidence_id,
                "payload_sha256": item.payload_sha256,
                "payload_ref": item.payload_ref,
            }
        )
    return refs


def _evidence_blob_id(ref: Mapping[str, Any]) -> str | None:
    direct = ref.get("blob_id")
    if isinstance(direct, str) and direct:
        return direct
    payload_ref = ref.get("payload_ref")
    if isinstance(payload_ref, Mapping):
        nested = payload_ref.get("blob_id")
        if isinstance(nested, str) and nested:
            return nested
    return None


def _evidence_sha(ref: Mapping[str, Any]) -> str | None:
    for key in ("payload_sha256", "sha256"):
        value = ref.get(key)
        if isinstance(value, str) and value:
            return value
    payload_ref = ref.get("payload_ref")
    if isinstance(payload_ref, Mapping):
        value = payload_ref.get("sha256")
        if isinstance(value, str) and value:
            return value
    return None


def check_capsule_contract(
    capsule: Capsule,
    runtime_context: Mapping[str, Any] | None = None,
    *,
    blob_store: BlobStore | None = None,
    raise_on_failure: bool = True,
) -> CapsuleContractCheck:
    """Check declared Capsule Contract facts against a runtime context.

    The first-pass checker is intentionally limited to facts already declared
    by the Capsule or supplied by the caller: manifest ABI/version, behavioral
    and topology hashes, port content types, legal content-type coercions, and
    Evidence availability. Environment requirements are likewise explicit:
    repo commits, model/tool versions, environment variables, and secret shapes
    are checked only when declared on the Contract and compared only with
    caller-supplied runtime context.
    """
    runtime_context = runtime_context or {}
    failures: list[dict[str, Any]] = []
    adaptations: list[dict[str, Any]] = []

    scalar_checks = (
        ("manifest_abi_mismatch", "manifest_abi", capsule.contract.manifest_abi),
        (
            "static_behavioral_hash_mismatch",
            "static_behavioral_hash",
            capsule.contract.static_behavioral_hash,
        ),
        (
            "runtime_topology_hash_mismatch",
            "runtime_topology_hash",
            capsule.contract.runtime_topology_hash,
        ),
    )
    for error_kind, key, wanted in scalar_checks:
        if wanted is None or key not in runtime_context:
            continue
        have = runtime_context.get(key)
        if have != wanted:
            failures.append(_failure(error_kind, wanted=wanted, have=have))

    if capsule.contract.repo_commit is not None:
        have = _runtime_value(runtime_context, "repo_commit", "commit", "git_commit")
        if have != capsule.contract.repo_commit:
            failures.append(
                _failure(
                    "repo_commit_mismatch",
                    wanted=capsule.contract.repo_commit,
                    have=have,
                    legal_moves=(),
                )
            )

    model_requirements = _merged_requirements(
        capsule.contract.model_requirements,
        capsule.contract.model_version_requirements,
    )
    tool_requirements = _merged_requirements(
        capsule.contract.tool_requirements,
        capsule.contract.tool_version_requirements,
    )
    secret_shape_requirements = _merged_requirements(
        capsule.contract.secret_shape_requirements,
        capsule.contract.secret_shape_declarations,
    )
    _compare_mapping_requirements(
        failures,
        error_kind="model_version_requirement_mismatch",
        wanted=model_requirements,
        have=_mapping_value(_runtime_value(runtime_context, "model_versions", "model_requirements")),
    )
    _compare_mapping_requirements(
        failures,
        error_kind="tool_version_requirement_mismatch",
        wanted=tool_requirements,
        have=_mapping_value(_runtime_value(runtime_context, "tool_versions", "tool_requirements")),
    )
    _compare_mapping_requirements(
        failures,
        error_kind="environment_variable_requirement_mismatch",
        wanted=capsule.contract.environment_variable_requirements,
        have=_mapping_value(_runtime_value(runtime_context, "environment_variables", "env_vars")),
    )
    _compare_mapping_requirements(
        failures,
        error_kind="secret_shape_requirement_mismatch",
        wanted=secret_shape_requirements,
        have=_mapping_value(_runtime_value(runtime_context, "secret_shapes", "secret_shape_requirements")),
    )

    runtime_ports = _declared_runtime_ports(runtime_context)
    runtime_by_key = {_port_key(port): port for port in runtime_ports if _port_key(port)[0]}
    for expected in capsule.contract.port_expectations:
        key = _port_key(expected)
        wanted_ct = _content_type(expected)
        have_port = runtime_by_key.get(key)
        have_ct = _content_type(have_port) if have_port is not None else None
        if have_port is None:
            failures.append(
                _failure(
                    "port_missing",
                    wanted=expected,
                    have=None,
                    legal_moves=(),
                )
            )
            continue
        if wanted_ct is None or have_ct == wanted_ct:
            continue
        legal_moves = ({"from": have_ct, "to": wanted_ct},) if have_ct and is_legal_coercion(have_ct, wanted_ct) else ()
        if legal_moves:
            adaptations.append(
                {
                    "kind": "content_type_coercion",
                    "port": key[0],
                    "wanted": wanted_ct,
                    "have": have_ct,
                    "legal_moves": legal_moves,
                }
            )
            continue
        failures.append(
            _failure(
                "port_content_type_mismatch",
                wanted=expected,
                have=have_port,
                legal_moves=(),
            )
        )

    evidence_by_id = {item.evidence_id: item for item in capsule.evidence}
    if capsule.completeness != "complete":
        failures.append(
            _failure(
                "capsule_evidence_degraded",
                wanted="complete",
                have=capsule.completeness,
                legal_moves=(),
            )
        )
    effective_blob_store = blob_store or runtime_context.get("blob_store")
    for ref in _declared_evidence_refs(capsule):
        evidence_id = ref.get("evidence_id")
        wanted_sha = _evidence_sha(ref)
        have_item = evidence_by_id.get(evidence_id) if isinstance(evidence_id, str) else None
        if have_item is None:
            failures.append(_failure("evidence_missing", wanted=ref, have=None))
            continue
        have_sha = have_item.payload_sha256 or have_item.payload_ref.get("sha256")
        if wanted_sha is not None and have_sha != wanted_sha:
            failures.append(
                _failure(
                    "evidence_sha_mismatch",
                    wanted=wanted_sha,
                    have=have_sha,
                    legal_moves=(),
                )
            )
        blob_id = _evidence_blob_id(ref)
        if blob_id and effective_blob_store is not None:
            try:
                stat = effective_blob_store.stat(blob_id)
            except BlobMissingError:
                stat = None
            if stat is None:
                failures.append(
                    _failure(
                        "evidence_blob_missing",
                        wanted={"blob_id": blob_id},
                        have=None,
                        legal_moves=(),
                    )
                )

    check = CapsuleContractCheck(
        ok=not failures,
        failures=tuple(failures),
        adaptations=tuple(adaptations),
    )
    if failures and raise_on_failure:
        first = failures[0]
        raise CapsuleContractError(
            first["error_kind"],
            "Capsule Contract check failed",
            failures=check.failures,
            adaptations=check.adaptations,
            wanted=first["wanted"],
            have=first["have"],
            legal_moves=first["legal_moves"],
        )
    return check


def list_capsules(blob_store: BlobStore) -> list[str]:
    """List Capsule hashes from LocalDirBlobStore index blobs."""
    if not isinstance(blob_store, LocalDirBlobStore):
        raise CapsuleListingUnsupportedError(
            "capsule_listing_unsupported",
            "Capsule listing is only supported for LocalDirBlobStore",
            backend=type(blob_store).__name__,
        )
    capsule_hashes: list[str] = []
    for blob_dir in sorted(blob_store.root.iterdir()) if blob_store.root.exists() else []:
        if not blob_dir.is_dir() or not blob_dir.name.startswith(CAPSULE_INDEX_ID_PREFIX):
            continue
        meta_path = blob_dir / "meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if meta.get("content_type") != capsule_record_content_type("index"):
            continue
        blob_id = blob_dir.name
        try:
            data = _decode_record_bytes(blob_store.get(blob_id), blob_id=blob_id)
            capsule_hash = data.get("capsule_hash")
            if isinstance(capsule_hash, str):
                _read_capsule_index(blob_store, capsule_hash)
        except (BlobMissingError, CapsuleStorageError):
            continue
        capsule_hashes.append(capsule_hash)
    return sorted(capsule_hashes)


def _write_capsule_projection_records(
    blob_store: BlobStore,
    capsule: Capsule,
) -> tuple[CapsuleWriteResult, dict[str, CapsuleRecordRef]]:
    record_refs: dict[str, CapsuleRecordRef] = {}
    for record_type, payload in (
        ("definition", capsule.definition.model_dump(mode="json")),
        ("contract", capsule.contract.model_dump(mode="json")),
        ("lineage", capsule.lineage.model_dump(mode="json")),
    ):
        record_refs[record_type] = put_capsule_record(
            blob_store,
            capsule_record_for_payload(record_type, payload, capsule_hash=capsule.capsule_hash),
        )
    for item in capsule.evidence:
        record_refs[item.evidence_id] = put_capsule_record(
            blob_store,
            capsule_record_for_payload(
                "evidence",
                item.model_dump(mode="json"),
                capsule_hash=capsule.capsule_hash,
            ),
        )
    write_result = write_capsule(blob_store, capsule)
    record_refs["capsule"] = write_result.capsule_ref
    return write_result, record_refs


def inspect_capsule(
    blob_store: BlobStore,
    capsule_hash: str,
    runtime_context: Mapping[str, Any] | None = None,
) -> CapsuleInspection:
    """Read, integrity-check, and summarize a Capsule and its Contract status."""
    capsule = get_capsule(blob_store, capsule_hash)
    check = check_capsule_contract(
        capsule,
        runtime_context or {},
        blob_store=blob_store,
        raise_on_failure=False,
    )
    summary = {
        "capsule_hash": capsule.capsule_hash,
        "definition_identity_hash": capsule.definition.identity_hash,
        "static_behavioral_hash": capsule.definition.static_behavioral_hash,
        "runtime_topology_hash": capsule.definition.runtime_topology_hash,
        "manifest_abi": capsule.contract.manifest_abi,
        "completeness": capsule.completeness,
        "replay_ready": capsule.replay_ready,
        "evidence_count": len(capsule.evidence),
        "parent_edge_count": len(capsule.lineage.parent_edges),
        "contract_ok": check.ok,
        "contract_failure_count": len(check.failures),
        "contract_adaptation_count": len(check.adaptations),
    }
    return CapsuleInspection(capsule=capsule, contract_check=check, summary=summary)


def fork_capsule(
    blob_store: BlobStore,
    capsule_hash: str,
    *,
    definition_overrides: Mapping[str, Any] | None = None,
    created_by: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> CapsuleBuildResult:
    """Create a child Capsule with exactly one parent edge to the source hash."""
    source = get_capsule(blob_store, capsule_hash)
    definition_data = source.definition.model_dump(mode="json")
    definition_data.update(dict(definition_overrides or {}))
    definition_data["identity_hash"] = sha256_uri(canonical_projection_bytes(definition_data))
    definition = CapsuleDefinition(**definition_data)
    contract = CapsuleContract(**source.contract.model_dump(mode="json"))
    evidence = [CapsuleEvidence(**item.model_dump(mode="json")) for item in source.evidence]
    lineage = CapsuleLineage(
        parent_edges=(
            {
                "parent_capsule_hash": source.capsule_hash,
                "relationship": "forked_from",
            },
        ),
        ancestors=tuple(
            dict.fromkeys((source.capsule_hash, *source.lineage.ancestors))
        ),
        created_by=created_by,
        created_at=CAPSULE_DETERMINISTIC_CREATED_AT,
    )
    child_metadata = {
        **dict(source.metadata),
        "forked_from_capsule_hash": source.capsule_hash,
        **dict(metadata or {}),
    }
    child_hash = sha256_uri(
        canonical_projection_bytes(
            _capsule_hash_payload(
                definition=definition,
                contract=contract,
                lineage=lineage,
                evidence=evidence,
                completeness=source.completeness,
                replay_ready=source.replay_ready,
                metadata=child_metadata,
            )
        )
    )
    lineage.capsule_hash = child_hash
    child = Capsule(
        capsule_hash=child_hash,
        definition=definition,
        contract=contract,
        lineage=lineage,
        evidence=evidence,
        completeness=source.completeness,
        replay_ready=source.replay_ready,
        created_at=CAPSULE_DETERMINISTIC_CREATED_AT,
        metadata=child_metadata,
    )
    write_result, record_refs = _write_capsule_projection_records(blob_store, child)
    return CapsuleBuildResult(
        capsule=child,
        write_result=write_result,
        record_refs=record_refs,
    )


__all__ = [
    "CAPSULE_CONTENT_TYPE",
    "CAPSULE_INDEX_ID_PREFIX",
    "CAPSULE_RECORD_ID_PREFIX",
    "CapsuleIntegrityError",
    "CapsuleContractCheck",
    "CapsuleContractError",
    "CapsuleInspection",
    "CapsuleListingUnsupportedError",
    "CapsuleBuildResult",
    "CapsuleRecordRef",
    "CapsuleStorageError",
    "CapsuleWriteResult",
    "capsule_index_blob_id",
    "capsule_record_blob_id",
    "capsule_record_content_type",
    "capsule_record_for_payload",
    "build_capsule",
    "check_capsule_contract",
    "fork_capsule",
    "get_capsule",
    "inspect_capsule",
    "list_capsules",
    "put_capsule_record",
    "verify_capsule_record",
    "write_capsule",
]
