"""Fail-closed custody for critique findings across planning stages.

The model-facing critique schema is not an authority boundary.  This module
materializes every flagged finding as a stable flag, writes an immutable
production receipt, joins every receipt to explicit resolution evidence, and
binds the resulting clearance to the exact finalized task graph.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from arnold_pipelines.megaplan._core import (
    atomic_write_json,
    configured_robustness,
    latest_plan_path,
    load_flag_registry,
    now_utc,
    plan_lock,
    read_json,
    sha256_file,
    workflow_includes_step,
)
from arnold_pipelines.megaplan.flags import synthesize_critique_flags
from arnold_pipelines.megaplan.orchestration.task_feasibility import task_contract_hash
from arnold_pipelines.megaplan.orchestration.critique_status import is_unverifiable_check
from arnold_pipelines.megaplan.orchestration.rubber_stamp import is_rubber_stamp
from arnold_pipelines.megaplan.types import PlanState
from arnold_pipelines.megaplan.custody.worker_dispatch_wbc import (
    query_worker_dispatch_manifest,
)


CUSTODY_SCHEMA_VERSION = "megaplan-critique-custody-v2"
LEGACY_CUSTODY_SCHEMA_VERSION = "megaplan-critique-custody-v1"
LEGACY_MIGRATION_SCHEMA_VERSION = "megaplan-critique-custody-legacy-migration-v1"
LEGACY_PRODUCER_BINDING_SCHEMA_VERSION = "megaplan-critique-legacy-producer-binding-v1"
CLEARANCE_SCHEMA_VERSION = "megaplan-critique-clearance-v1"
FINAL_BINDING_SCHEMA_VERSION = "megaplan-finalize-critique-binding-v1"
_ALLOWED_FINDING_KEYS = {
    "detail",
    "flagged",
    "category",
    "severity_hint",
    "evidence",
    "finding_id",
}
_CANONICAL_FINDING_ID = re.compile(r"^CF-[0-9A-F]{20}$")

# --------------------------------------------------------------------------- #
# CL4 BRIDGE authority provenance.
#
# CL4 carries five unresolved CL1/CL2 blockers and an inferred (not CL3-vouched)
# CL3 contract, so every production receipt it emits is durable integrity
# evidence but must NEVER be treated as canonical gate/finalize authority.
# These values mirror ``gate_signals.CL4_BRIDGE_MODE`` /
# ``CL4_CARRIED_BLOCKERS`` and the CL4 handoff
# (docs/critique-ledger/handoffs/cl4-role-flow.json); they are copied into each
# persisted receipt so an immutable receipt always carries its own BRIDGE
# provenance rather than depending on a later live read.
# --------------------------------------------------------------------------- #
#: CL4 runs in canonical (non-BRIDGE) mode after the CL5 cutover. The CL3
#: handoff is resolved, all CL1/CL2 blockers are cleared, and the module-level
#: BRIDGE markers are disabled. NOTE: canonical gate authority is still denied
#: at runtime whenever any source receipt in the clearance chain carries
#: bridge_mode=true (the clearance aggregator below reads source receipts, not
#: this constant), so a stale pre-cutover receipt cannot slip through.
CL4_BRIDGE_MODE: bool = False
#: Empty after the CL5 cutover: all five carried CL1/CL2 blockers are resolved.
CL4_CARRIED_BLOCKERS: tuple[str, ...] = ()

# The matrix-authorized critique custody producer scope (WBC boundary adoption
# matrices).  Only these producers may anchor reconciliation claims in a
# custody receipt; any other producer is outside the authorized scope and its
# reconciliation bindings must be rejected as authority-shaped evidence.
_AUTHORIZED_CRITIQUE_PRODUCERS = frozenset(
    {"codex", "omp", "shannon", "claude", "parallel_critique_reducer"}
)


class CritiqueCustodyError(ValueError):
    """One or more custody invariants failed."""

    def __init__(self, code: str, issues: Sequence[str]) -> None:
        self.code = code
        self.issues = tuple(str(issue) for issue in issues)
        super().__init__(f"{code}: " + "; ".join(self.issues))


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _materialize_artifact_bindings(
    plan_dir: Path,
    declared: Sequence[Mapping[str, Any] | str] | None,
) -> list[dict[str, Any]]:
    """Materialize safe SHA-256 bindings for declared custody artifacts.

    Each declared entry is either a basename string or a mapping carrying an
    ``artifact`` basename.  A binding is recorded only for declared artifacts
    that resolve to a non-symlink regular file inside ``plan_dir``.  Missing or
    unsafe declarations are silently omitted so the stored binding set is always
    a truthful subset of declared intents; ``_artifact_binding_issues``
    re-checks every stored row against disk and fails closed on any drift.
    """
    if not declared:
        return []
    bindings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in declared:
        if isinstance(entry, str):
            name: str | None = entry
        elif isinstance(entry, Mapping):
            value = entry.get("artifact")
            name = value if isinstance(value, str) else None
        else:
            name = None
        if not isinstance(name, str) or not name or Path(name).name != name:
            continue
        if name in seen:
            continue
        path = plan_dir / name
        if path.is_symlink() or not path.is_file():
            continue
        seen.add(name)
        bindings.append({"artifact": name, "sha256": sha256_file(path)})
    return bindings


def _artifact_binding_issues(
    artifacts: object,
    *,
    plan_dir: Path,
    field: str,
) -> list[str]:
    """Fail closed for missing, unsafe, or hash-mismatched custody artifacts.

    A receipt may legitimately predate reconciliation/disposition artifact
    bindings; an absent (``None``) field therefore adds no issue.  Once a field
    is present, every bound artifact must resolve to a safe regular file whose
    recorded SHA-256 still matches the bytes on disk.
    """
    if artifacts is None:
        return []
    if not isinstance(artifacts, list):
        return [f"receipt {field} is not an array"]
    issues: list[str] = []
    seen: set[str] = set()
    for row in artifacts:
        if not isinstance(row, Mapping):
            issues.append(f"{field} binding row is not an object")
            continue
        name = row.get("artifact")
        digest = row.get("sha256")
        if not isinstance(name, str) or not name or Path(name).name != name:
            issues.append(f"{field} artifact reference is unsafe: {name!r}")
            continue
        if name in seen:
            issues.append(f"{field} has duplicate artifact {name!r}")
            continue
        seen.add(name)
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", digest) is None
        ):
            issues.append(f"{field} artifact {name!r} has an invalid sha256")
            continue
        artifact_path = plan_dir / name
        if artifact_path.is_symlink() or not artifact_path.is_file():
            issues.append(f"{field} artifact is missing or unsafe: {name!r}")
            continue
        if digest != sha256_file(artifact_path):
            issues.append(f"{field} artifact hash mismatch for {name!r}")
    return issues


def _producer_binding_issues(binding: object) -> list[str]:
    if not isinstance(binding, Mapping):
        return ["producer_binding is not an object"]
    issues: list[str] = []
    if binding.get("schema_version") != "megaplan-critique-producer-binding-v1":
        issues.append("producer binding schema is unsupported")
    invocation_id = binding.get("invocation_id")
    if not isinstance(invocation_id, str) or not invocation_id:
        issues.append("producer invocation_id is missing")
    attempt_index = binding.get("attempt_index")
    if isinstance(attempt_index, bool) or not isinstance(attempt_index, int) or attempt_index < 0:
        issues.append("producer attempt_index is invalid")
    expected_attempt_id = (
        f"{invocation_id}:{attempt_index}"
        if isinstance(invocation_id, str) and isinstance(attempt_index, int)
        else None
    )
    if binding.get("attempt_id") != expected_attempt_id:
        issues.append("producer attempt_id is not bound to invocation and attempt index")
    producer = binding.get("producer")
    if not isinstance(producer, str) or not producer:
        issues.append("producer identity is missing")
    transport = binding.get("transport")
    if transport not in {"registered_file_fill", "inline_response", "parallel_reduce"}:
        issues.append("producer transport is invalid")
    scratch_status = binding.get("scratch_status")
    if not isinstance(scratch_status, str) or not scratch_status:
        issues.append("producer scratch_status is missing")
    if binding.get("registered_scratch_artifact") != "critique_output.json":
        issues.append("producer scratch artifact is not the registered critique path")
    if transport != "registered_file_fill" and scratch_status == "filled":
        issues.append("inline/parallel producer cannot claim filled scratch custody")
    scratch_sha = binding.get("scratch_sha256")
    if scratch_sha is not None and (
        not isinstance(scratch_sha, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}|[0-9a-f]{64}", scratch_sha) is None
    ):
        issues.append("producer scratch_sha256 is invalid")
    if transport == "registered_file_fill" and scratch_status == "filled":
        if scratch_sha is None:
            issues.append("filled file transport has no scratch content hash")
        scratch_bytes = binding.get("scratch_bytes")
        if (
            isinstance(scratch_bytes, bool)
            or not isinstance(scratch_bytes, int)
            or scratch_bytes < 0
        ):
            issues.append("filled file transport has invalid scratch byte count")
    if not isinstance(binding.get("output_path_attested"), bool):
        issues.append("producer output_path_attested must be boolean")
    if transport == "parallel_reduce":
        if not isinstance(binding.get("phase_attempt_id"), str) or not binding.get(
            "phase_attempt_id"
        ):
            issues.append("parallel producer phase_attempt_id is missing")
        manifest_artifact = binding.get("child_manifest_artifact")
        if (
            not isinstance(manifest_artifact, str)
            or Path(manifest_artifact).name != manifest_artifact
            or re.fullmatch(r"critique_parallel_manifest_v\d+\.json", manifest_artifact)
            is None
        ):
            issues.append("parallel producer child manifest artifact is invalid")
        for field in ("child_manifest_sha256", "child_manifest_digest"):
            value = binding.get(field)
            if not isinstance(value, str) or re.fullmatch(
                r"(?:sha256:)?[0-9a-f]{64}", value
            ) is None:
                issues.append(f"parallel producer {field} is invalid")
    return issues


def _parallel_producer_binding_issues(
    plan_dir: Path,
    binding: Mapping[str, Any],
) -> list[str]:
    if binding.get("transport") != "parallel_reduce":
        return []
    issues: list[str] = []
    name = binding.get("child_manifest_artifact")
    if not isinstance(name, str) or Path(name).name != name:
        return ["parallel child manifest reference is unsafe"]
    path = plan_dir / name
    if path.is_symlink() or not path.is_file():
        return [f"parallel child manifest is missing or unsafe: {name}"]
    if binding.get("child_manifest_sha256") != sha256_file(path):
        issues.append("parallel child manifest artifact hash mismatch")
    manifest = read_json(path)
    unsigned = dict(manifest)
    stored_digest = unsigned.pop("manifest_digest", None)
    if stored_digest != _digest(unsigned):
        issues.append("parallel child manifest content digest mismatch")
    if binding.get("child_manifest_digest") != stored_digest:
        issues.append("parallel producer does not bind the child manifest digest")
    if manifest.get("invocation_id") != binding.get("invocation_id"):
        issues.append("parallel child manifest invocation mismatch")
    if manifest.get("phase_attempt_id") != binding.get("phase_attempt_id"):
        issues.append("parallel child manifest phase attempt mismatch")
    expected = manifest.get("expected_check_ids")
    artifacts = manifest.get("producer_artifacts")
    dispatches = manifest.get("dispatches")
    if not isinstance(expected, list) or any(
        not isinstance(item, str) or not item for item in expected
    ) or len(set(expected)) != len(expected):
        issues.append("parallel child manifest expected checks are invalid")
        expected = []
    if not isinstance(artifacts, list):
        issues.append("parallel child manifest producer artifacts are missing")
        artifacts = []
    artifact_ids: list[str] = []
    for row in artifacts:
        if not isinstance(row, Mapping):
            issues.append("parallel producer artifact row is malformed")
            continue
        check_id = row.get("check_id")
        artifact = row.get("producer_artifact")
        artifact_ids.append(str(check_id))
        if not isinstance(artifact, str) or Path(artifact).name != artifact:
            issues.append(f"parallel producer artifact is unsafe for {check_id!r}")
            continue
        artifact_path = plan_dir / artifact
        if not artifact_path.is_file() or row.get("producer_sha256") != sha256_file(
            artifact_path
        ):
            issues.append(f"parallel producer artifact hash mismatch for {check_id!r}")
    if artifact_ids != expected:
        issues.append("parallel producer artifacts do not cover expected checks in order")
    if not isinstance(dispatches, list):
        issues.append("parallel child dispatch manifest is missing")
        dispatches = []
    phase_attempt_id = manifest.get("phase_attempt_id")
    if isinstance(phase_attempt_id, str) and phase_attempt_id:
        try:
            durable_dispatches = query_worker_dispatch_manifest(
                plan_dir,
                phase_attempt_id=phase_attempt_id,
            )
        except Exception as error:
            issues.append(f"parallel child dispatch ledger is unreadable: {error}")
        else:
            if dispatches != durable_dispatches:
                issues.append("parallel child manifest differs from durable dispatch ledger")
    initial_keys = {
        str(row.get("dispatch_key"))
        for row in dispatches
        if isinstance(row, Mapping)
        and row.get("terminal_event") in {"completed", "failed", "cancelled"}
    }
    missing = [
        check_id
        for check_id in expected
        if f"critique:{check_id}:initial" not in initial_keys
    ]
    if missing:
        issues.append(f"parallel child dispatch custody missing checks {missing!r}")
    attempt_ids = [
        row.get("attempt_id") for row in dispatches if isinstance(row, Mapping)
    ]
    if any(not isinstance(item, str) or not item for item in attempt_ids) or len(
        set(attempt_ids)
    ) != len(attempt_ids):
        issues.append("parallel child dispatch attempt identities are missing or duplicated")
    return issues


def _receipt_semantic_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    semantic = dict(receipt)
    semantic.pop("produced_at", None)
    semantic.pop("receipt_digest", None)
    return semantic


def _publish_receipt_create_once(path: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    """Atomically publish one immutable receipt or return an identical restart."""

    def _existing() -> dict[str, Any]:
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise CritiqueCustodyError(
                "critique_custody_receipt_conflict",
                [f"refusing non-exclusive custody path {path.name}"],
            )
        existing = read_json(path)
        unsigned_existing = dict(existing)
        stored_digest = unsigned_existing.pop("receipt_digest", None)
        if stored_digest != _digest(unsigned_existing):
            raise CritiqueCustodyError(
                "critique_custody_receipt_conflict",
                [f"existing custody receipt has an invalid digest: {path.name}"],
            )
        if _receipt_semantic_payload(existing) != _receipt_semantic_payload(receipt):
            raise CritiqueCustodyError(
                "critique_custody_receipt_conflict",
                [f"create-once custody receipt already exists with different authority: {path.name}"],
            )
        return existing

    if path.exists() or path.is_symlink():
        return _existing()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    encoded = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            return _existing()
        return receipt
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _legacy_migration_path(plan_dir: Path, iteration: int) -> Path:
    return plan_dir / f"critique_custody_legacy_migration_v{iteration}.json"


def _legacy_artifact_evidence(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence = [
        {
            "role": "source_plan",
            "artifact": receipt.get("plan_artifact"),
            "sha256": receipt.get("plan_sha256"),
        },
        {
            "role": "canonical_critique",
            "artifact": receipt.get("critique_artifact"),
            "sha256": receipt.get("critique_sha256"),
        },
    ]
    for source in receipt.get("raw_sources", []):
        if isinstance(source, Mapping):
            name = source.get("artifact")
            role = (
                "producer_reduction"
                if isinstance(name, str) and "_producer_v" in name
                else "producer_raw_output"
            )
            evidence.append(
                {"role": role, "artifact": name, "sha256": source.get("sha256")}
            )
    return evidence


def _legacy_producer_evidence_binding(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Describe exactly what legacy evidence proves, without inventing an agent identity."""
    raw_sources = receipt.get("raw_sources", [])
    producer_artifacts = [
        source.get("artifact")
        for source in raw_sources
        if isinstance(source, Mapping)
        and isinstance(source.get("artifact"), str)
        and "_producer_v" in source["artifact"]
    ]
    return {
        "schema_version": LEGACY_PRODUCER_BINDING_SCHEMA_VERSION,
        "authority": "persisted_artifact_hashes",
        "producer_identity_status": "not_recorded_by_legacy_schema",
        "producer_identity": None,
        "invocation_identity": None,
        "critique_artifact": receipt.get("critique_artifact"),
        "critique_sha256": receipt.get("critique_sha256"),
        "producer_artifacts": producer_artifacts,
        "raw_sources_digest": _digest(raw_sources),
        "expected_check_ids": receipt.get("expected_check_ids", []),
    }


def _legacy_lineage_evidence(
    plan_dir: Path,
    legacy_path: Path,
    receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Prove the old artifact was successfully produced, consumed, and cleared."""
    iteration = int(receipt["iteration"])
    names = {
        "state_history": "state.json",
        "critique_step_receipt": f"step_receipt_critique_v{iteration}.json",
        "gate_signals": f"gate_signals_v{iteration}.json",
        "gate_step_receipt": f"step_receipt_gate_v{iteration}.json",
        "versioned_gate": f"gate_v{iteration}.json",
        "critique_clearance": "critique_clearance.json",
    }
    documents: dict[str, Mapping[str, Any]] = {}
    issues: list[str] = []
    for role, name in names.items():
        path = plan_dir / name
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            issues.append(f"legacy {role} artifact is missing or unsafe: {name}")
            continue
        value = read_json(path)
        if not isinstance(value, Mapping):
            issues.append(f"legacy {role} artifact is not an object: {name}")
            continue
        documents[role] = value

    state = documents.get("state_history", {})
    matching_history = [
        row
        for row in state.get("history", [])
        if isinstance(row, Mapping)
        and row.get("step") == "critique"
        and row.get("result") == "success"
        and row.get("output_file") == receipt.get("critique_artifact")
        and row.get("artifact_hash") == receipt.get("critique_sha256")
    ]
    if len(matching_history) != 1:
        issues.append("state history lacks exactly one matching successful critique result")

    critique_step = documents.get("critique_step_receipt", {})
    if critique_step.get("phase") != "critique" or critique_step.get("iteration") != iteration:
        issues.append("critique step receipt phase/iteration mismatch")
    if receipt.get("plan_sha256") not in critique_step.get("upstream_artifact_hashes", []):
        issues.append("critique step receipt is not bound to the source plan hash")
    if matching_history and critique_step.get("duration_ms") != matching_history[0].get("duration_ms"):
        issues.append("critique step receipt does not match successful history duration")

    gate_signals = documents.get("gate_signals", {})
    gate_custody = gate_signals.get("signals", {}).get("critique_custody", {})
    expected_gate_custody = {
        "schema_version": LEGACY_CUSTODY_SCHEMA_VERSION,
        "receipt": legacy_path.name,
        "receipt_sha256": sha256_file(legacy_path),
        "finding_count": receipt.get("finding_count"),
        "finding_ids": receipt.get("finding_ids"),
        "flag_ids": receipt.get("flag_ids"),
        "loss_count": 0,
        "admitted": True,
    }
    if gate_custody != expected_gate_custody:
        issues.append("gate signals do not bind the exact legacy custody receipt")

    gate_step = documents.get("gate_step_receipt", {})
    if gate_step.get("phase") != "gate" or gate_step.get("iteration") != iteration:
        issues.append("gate step receipt phase/iteration mismatch")
    if receipt.get("critique_sha256") not in gate_step.get("upstream_artifact_hashes", []):
        issues.append("gate step receipt is not bound to the critique hash")

    versioned_gate = documents.get("versioned_gate", {})
    if versioned_gate.get("recommendation") not in {"ITERATE", "PROCEED"}:
        issues.append("versioned gate has no admitted ITERATE/PROCEED recommendation")
    if versioned_gate.get("signals", {}).get("critique_custody") != expected_gate_custody:
        issues.append("versioned gate does not bind the exact legacy custody receipt")

    canonical_gate_path = plan_dir / "gate.json"
    if canonical_gate_path.is_symlink() or not canonical_gate_path.is_file():
        issues.append("canonical gate artifact is missing or unsafe: gate.json")
    else:
        canonical_gate = read_json(canonical_gate_path)
        if canonical_gate.get("signals", {}).get("critique_custody") == expected_gate_custody:
            if canonical_gate.get("recommendation") != "PROCEED":
                issues.append("current canonical gate did not record PROCEED")
            else:
                names["canonical_gate"] = "gate.json"

    clearance = documents.get("critique_clearance", {})
    unsigned_clearance = dict(clearance)
    clearance_digest = unsigned_clearance.pop("clearance_digest", None)
    if clearance_digest != _digest(unsigned_clearance) or clearance.get("admitted") is not True:
        issues.append("critique clearance is not an intact admitted receipt")
    source_rows = [
        row
        for row in clearance.get("source_receipts", [])
        if isinstance(row, Mapping)
        and row.get("artifact") == legacy_path.name
        and row.get("sha256") == sha256_file(legacy_path)
    ]
    if len(source_rows) != 1:
        issues.append("critique clearance does not bind the exact legacy receipt")
    if issues:
        raise CritiqueCustodyError("critique_custody_legacy_lineage_invalid", issues)
    return [
        {"role": role, "artifact": name, "sha256": sha256_file(plan_dir / name)}
        for role, name in names.items()
    ]


def _legacy_lineage_evidence_issues(
    stored: object,
    current: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Compare durable lineage without pinning rewritable projection byte streams.

    The migration sidecar is an immutable record of the evidence inspected at
    migration time.  ``state.json`` is an append-only workflow projection and
    ``critique_clearance.json`` is intentionally regenerated as resolution
    evidence advances (and includes ``produced_at``).  Their historical hashes
    must remain in the sidecar without becoming permanent pins on their current
    byte streams.

    ``_legacy_lineage_evidence`` revalidates both live projections before this
    comparison: state must still contain exactly one successful critique row
    bound to the admitted critique hash and immutable critique-step duration,
    while clearance must have an intact digest and exact source-receipt row.
    Therefore these two roles are compared by stable role/artifact identity;
    actual source, step, signal, and versioned-gate evidence remains byte-pinned.
    """
    if not isinstance(stored, list):
        return ["legacy lineage_evidence is not an array"]
    stored_by_role: dict[str, Mapping[str, Any]] = {}
    issues: list[str] = []
    for index, row in enumerate(stored):
        if not isinstance(row, Mapping):
            issues.append(f"legacy lineage row {index} is not an object")
            continue
        role = row.get("role")
        if not isinstance(role, str) or not role:
            issues.append(f"legacy lineage row {index} has no role")
            continue
        if role in stored_by_role:
            issues.append(f"legacy lineage has duplicate role {role!r}")
            continue
        artifact = row.get("artifact")
        digest = row.get("sha256")
        if not isinstance(artifact, str) or Path(artifact).name != artifact:
            issues.append(f"legacy lineage role {role!r} has an unsafe artifact")
        if not isinstance(digest, str) or re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", digest) is None:
            issues.append(f"legacy lineage role {role!r} has an invalid sha256")
        stored_by_role[role] = row

    current_by_role = {
        str(row.get("role")): row
        for row in current
        if isinstance(row.get("role"), str)
    }
    if set(stored_by_role) != set(current_by_role):
        issues.append("legacy lineage roles differ from the admitted lineage")
        return issues
    mutable_projection_roles = {"state_history", "critique_clearance"}
    for role, current_row in current_by_role.items():
        stored_row = stored_by_role[role]
        if role in mutable_projection_roles:
            if stored_row.get("artifact") != current_row.get("artifact"):
                issues.append(f"legacy {role} artifact identity changed")
            continue
        if dict(stored_row) != dict(current_row):
            issues.append(f"legacy immutable lineage changed for {role}")
    return issues


def _stable_finding_id(flag: Mapping[str, Any]) -> str:
    identity = {
        "source_check_id": flag.get("source_check_id"),
        "concern": str(flag.get("concern") or "").strip(),
        "category": flag.get("category"),
        "severity_hint": flag.get("severity_hint"),
        "evidence": str(flag.get("evidence") or "").strip(),
    }
    return "CF-" + hashlib.sha256(_canonical_bytes(identity)).hexdigest()[:20].upper()


def canonical_critique_flag_id(flag: Mapping[str, Any]) -> str:
    """Return the reducer-owned identity for a normalized critique finding."""
    return _stable_finding_id(flag)


def _normalize_flag_ids(payload: dict[str, Any]) -> None:
    flags = payload.get("flags")
    if not isinstance(flags, list):
        raise CritiqueCustodyError("critique_flags_malformed", ["flags must be an array"])
    seen: dict[str, int] = {}
    remapped: dict[str, set[str]] = {}
    issues: list[str] = []
    for index, raw_flag in enumerate(flags):
        if not isinstance(raw_flag, dict):
            issues.append(f"flags[{index}] is not an object")
            continue
        producer_id = raw_flag.get("id")
        if not isinstance(producer_id, str):
            issues.append(f"flags[{index}].id is not a string")
            continue
        for field in ("concern", "category", "severity_hint", "evidence"):
            value = raw_flag.get(field)
            if not isinstance(value, str) or not value.strip():
                issues.append(f"flags[{index}].{field} must be a non-empty string")
        local_id = producer_id.strip()
        canonical_id = canonical_critique_flag_id(raw_flag)
        if local_id and local_id != canonical_id and "producer_flag_id" not in raw_flag:
            raw_flag["producer_flag_id"] = local_id
        raw_flag["id"] = canonical_id
        remapped.setdefault(producer_id.strip(), set()).add(canonical_id)
        if canonical_id in seen:
            issues.append(
                f"duplicate canonical flag id {canonical_id!r} at "
                f"flags[{seen[canonical_id]}] and flags[{index}]"
            )
        seen[canonical_id] = index
    if issues:
        raise CritiqueCustodyError("critique_finding_identity_invalid", issues)
    for key in ("verified_flag_ids", "disputed_flag_ids"):
        values = payload.get(key)
        if isinstance(values, list):
            normalized_values: list[Any] = []
            for value in values:
                candidates = remapped.get(value, set())
                if len(candidates) > 1:
                    # A prior reducer-owned finding id can legitimately be
                    # mentioned by a current check while multiple current
                    # producers reuse that string as their local alias. Keep
                    # the canonical reference intact and let the downstream
                    # flag registry prove that it exists. Opaque/local ids
                    # remain ambiguous and fail closed here.
                    if (
                        isinstance(value, str)
                        and _CANONICAL_FINDING_ID.fullmatch(value)
                    ):
                        normalized_values.append(value)
                        continue
                    raise CritiqueCustodyError(
                        "critique_finding_reference_ambiguous",
                        [f"{key} local id {value!r} maps to {sorted(candidates)!r}"],
                    )
                normalized_values.append(next(iter(candidates)) if candidates else value)
            payload[key] = normalized_values


def prepare_critique_payload(
    payload: dict[str, Any],
    *,
    expected_check_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """Materialize and validate the canonical finding set before persistence."""
    synthesize_critique_flags(payload)
    issues: list[str] = []
    checks = payload.get("checks")
    if not isinstance(checks, list):
        raise CritiqueCustodyError("critique_checks_malformed", ["checks must be an array"])
    expected = list(expected_check_ids)
    observed: list[str] = []
    flagged_findings: list[tuple[str, str]] = []
    # Degraded (unverifiable) checks deliberately mint no durable flags:
    # _synthesize_flags_from_checks skips them wholesale so unverifiable
    # evidence never reaches the flag registry. Demanding flag coverage for
    # their flagged findings here contradicted that skip and wedged every
    # critique whose degraded check still emitted a flagged finding
    # (critique_finding_mapping_invalid with 0 candidate flags). The finding
    # text stays in the stored checks array and the degraded warning carries
    # the operator-attention signal instead.
    unverifiable_check_ids: set[str] = set()
    for check_index, check in enumerate(checks):
        if not isinstance(check, dict):
            issues.append(f"checks[{check_index}] is not an object")
            continue
        check_id = check.get("id")
        if not isinstance(check_id, str) or not check_id:
            issues.append(f"checks[{check_index}].id is missing")
            continue
        observed.append(check_id)
        if is_unverifiable_check(check):
            unverifiable_check_ids.add(check_id)
        findings = check.get("findings")
        if not isinstance(findings, list):
            issues.append(f"check {check_id!r} findings is not an array")
            continue
        seen_details: set[str] = set()
        for finding_index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                issues.append(f"check {check_id!r} finding {finding_index} is not an object")
                continue
            unknown = sorted(set(finding) - _ALLOWED_FINDING_KEYS)
            if unknown:
                issues.append(
                    f"check {check_id!r} finding {finding_index} has unknown fields {unknown!r}"
                )
            detail = finding.get("detail")
            if not isinstance(detail, str) or not detail.strip():
                issues.append(f"check {check_id!r} finding {finding_index} has empty detail")
                continue
            if not isinstance(finding.get("flagged"), bool):
                issues.append(f"check {check_id!r} finding {finding_index} has non-boolean flagged")
                continue
            normalized_detail = " ".join(detail.split())
            if normalized_detail in seen_details:
                issues.append(f"check {check_id!r} contains duplicate finding {normalized_detail!r}")
            seen_details.add(normalized_detail)
            if finding["flagged"]:
                flagged_findings.append((check_id, detail.strip()))
    if len(observed) != len(set(observed)):
        issues.append("critique contains duplicate check ids")
    if set(observed) != set(expected) or len(observed) != len(expected):
        issues.append(f"expected checks {expected!r}, observed {observed!r}")
    if issues:
        raise CritiqueCustodyError("critique_findings_malformed", issues)

    _normalize_flag_ids(payload)
    flags = payload["flags"]
    coverage_issues: list[str] = []
    for check_id, detail in flagged_findings:
        if check_id in unverifiable_check_ids:
            continue
        matches = [
            flag
            for flag in flags
            if isinstance(flag, dict)
            and flag.get("source_check_id") == check_id
            and str(flag.get("evidence") or "").strip() == detail
        ]
        if len(matches) != 1:
            coverage_issues.append(
                f"flagged finding from {check_id!r} maps to {len(matches)} top-level flags: {detail!r}"
            )
    if coverage_issues:
        raise CritiqueCustodyError("critique_finding_mapping_invalid", coverage_issues)
    return flags


def write_critique_production_receipt(
    plan_dir: Path,
    state: PlanState,
    payload: dict[str, Any],
    *,
    expected_check_ids: Sequence[str],
    producer_binding: Mapping[str, Any],
    reconciliation_artifacts: Sequence[Mapping[str, Any] | str] | None = None,
    disposition_artifacts: Sequence[Mapping[str, Any] | str] | None = None,
) -> dict[str, Any]:
    """Persist immutable custody evidence for one canonical critique artifact."""
    producer_issues = _producer_binding_issues(producer_binding)
    producer_issues.extend(_parallel_producer_binding_issues(plan_dir, producer_binding))
    if producer_issues:
        raise CritiqueCustodyError("critique_producer_binding_invalid", producer_issues)
    flags = prepare_critique_payload(payload, expected_check_ids=expected_check_ids)
    iteration = int(state["iteration"])
    critique_name = f"critique_v{iteration}.json"
    critique_path = plan_dir / critique_name
    if not critique_path.exists():
        raise CritiqueCustodyError(
            "critique_artifact_missing",
            [f"{critique_name} must be persisted before its custody receipt"],
        )
    plan_path = latest_plan_path(plan_dir, state)
    # Bind semantic-loop reconciliation and disposition artifacts by SHA-256 so a
    # gate/finalize consumer reading the receipt can prove the exact bytes it
    # trusts have not drifted since custody was taken.  The bindings are pure
    # integrity evidence: they fail closed on tamper but never positively
    # authorize dispatch/completion (per the WBC boundary adoption matrices).
    reconciliation_bindings = _materialize_artifact_bindings(
        plan_dir, reconciliation_artifacts
    )
    disposition_bindings = _materialize_artifact_bindings(
        plan_dir, disposition_artifacts
    )
    findings: list[dict[str, Any]] = []
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        finding_id = _stable_finding_id(flag)
        findings.append(
            {
                "finding_id": finding_id,
                "flag_id": flag["id"],
                "source_check_id": flag.get("source_check_id"),
                "category": flag.get("category"),
                "producer_category": flag.get("producer_category", flag.get("category")),
                "severity_hint": flag.get("severity_hint"),
                "producer_severity": flag.get("producer_severity", flag.get("severity_hint")),
                "blocking": flag.get("severity_hint") != "likely-minor",
                "concern": flag.get("concern", ""),
                "evidence": flag.get("evidence", ""),
                "evidence_digest": _digest(flag.get("evidence", "")),
            }
        )
    raw_candidates = [
        plan_dir / f"critique_raw_v{iteration}.txt",
        *sorted(plan_dir.glob(f"critique_check_*_producer_v{iteration}.json")),
        *sorted(plan_dir.glob(f"critique_check_*_raw_v{iteration}.txt")),
    ]
    raw_sources = [
        {"artifact": path.name, "sha256": sha256_file(path)}
        for path in raw_candidates
        if path.exists() and path.is_file()
    ]
    if findings and not raw_sources:
        raise CritiqueCustodyError(
            "critique_raw_evidence_missing",
            ["substantive findings require at least one persisted producer/raw source"],
        )
    receipt = {
        "schema_version": CUSTODY_SCHEMA_VERSION,
        "iteration": iteration,
        "produced_at": now_utc(),
        "plan_artifact": plan_path.name,
        "plan_sha256": sha256_file(plan_path),
        "critique_artifact": critique_name,
        "critique_sha256": sha256_file(critique_path),
        "critique_payload_digest": _digest(payload),
        "producer_binding": dict(producer_binding),
        "producer_binding_digest": _digest(producer_binding),
        "raw_sources": raw_sources,
        "reconciliation_artifacts": reconciliation_bindings,
        "disposition_artifacts": disposition_bindings,
        # BRIDGE authority provenance: the producing run is BRIDGE-mode and
        # carries the unresolved CL1/CL2 blockers, so this receipt is integrity
        # evidence, never canonical gate/finalize authority.  Per the WBC
        # boundary adoption matrices the artifact bindings above fail closed on
        # tamper but never positively authorize dispatch/completion; the
        # bridge_mode flag makes that limitation in-band so a downstream
        # consumer cannot mistake this receipt for canonical authority.
        "bridge_mode": CL4_BRIDGE_MODE,
        "carried_blockers": list(CL4_CARRIED_BLOCKERS),
        "expected_check_ids": list(expected_check_ids),
        "finding_count": len(findings),
        "finding_ids": [finding["finding_id"] for finding in findings],
        "flag_ids": [finding["flag_id"] for finding in findings],
        "findings": findings,
        "normalization": {
            "flagged_check_findings": sum(
                1
                for check in payload.get("checks", [])
                if isinstance(check, dict)
                for finding in check.get("findings", [])
                if isinstance(finding, dict) and finding.get("flagged") is True
            ),
            "canonical_flags": len(findings),
            "loss_count": 0,
        },
        "admitted": True,
    }
    receipt["receipt_digest"] = _digest(receipt)
    receipt_path = plan_dir / f"critique_custody_v{iteration}.json"
    _validate_production_receipt(
        plan_dir,
        receipt,
        expected_iteration=iteration,
        expected_receipt_path=receipt_path,
        expected_plan_artifact=plan_path.name,
    )
    return _publish_receipt_create_once(receipt_path, receipt)


def _plan_versions_from_state(plan_dir: Path) -> list[Mapping[str, Any]]:
    """Read the plan_versions ledger from the plan state for custody validation."""
    try:
        payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return []
    records = payload.get("plan_versions") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return []
    return [r for r in records if isinstance(r, Mapping)]


def _validate_production_receipt(
    plan_dir: Path,
    receipt: Mapping[str, Any],
    *,
    expected_iteration: int,
    expected_receipt_path: Path,
    expected_plan_artifact: str,
    allow_legacy_schema: bool = False,
    plan_versions: list[Mapping[str, Any]] | None = None,
) -> None:
    issues: list[str] = []
    schema_version = receipt.get("schema_version")
    legacy_schema = schema_version == LEGACY_CUSTODY_SCHEMA_VERSION
    if (
        schema_version != CUSTODY_SCHEMA_VERSION
        and not (allow_legacy_schema and legacy_schema)
    ) or receipt.get("admitted") is not True:
        issues.append("unsupported or non-admitted production receipt")
    unsigned_receipt = dict(receipt)
    stored_receipt_digest = unsigned_receipt.pop("receipt_digest", None)
    if stored_receipt_digest != _digest(unsigned_receipt):
        issues.append("production receipt digest mismatch")
    if expected_receipt_path.name != f"critique_custody_v{expected_iteration}.json":
        issues.append("validator receipt path does not match current iteration")
    if expected_receipt_path.parent.resolve() != plan_dir.resolve():
        issues.append("validator receipt path is outside the plan directory")
    if expected_receipt_path.exists() or expected_receipt_path.is_symlink():
        if expected_receipt_path.is_symlink() or not expected_receipt_path.is_file():
            issues.append("custody receipt path is not a regular file")
        elif expected_receipt_path.stat().st_nlink != 1:
            issues.append("custody receipt path has multiple hard links")
    if receipt.get("iteration") != expected_iteration:
        issues.append(
            f"receipt iteration {receipt.get('iteration')!r} does not match current iteration {expected_iteration}"
        )
    expected_critique_name = f"critique_v{expected_iteration}.json"
    if receipt.get("critique_artifact") != expected_critique_name:
        issues.append(
            f"critique artifact must be exact current canonical artifact {expected_critique_name}"
        )
    if receipt.get("plan_artifact") != expected_plan_artifact:
        issues.append(
            f"source plan artifact must be exact current plan {expected_plan_artifact}"
        )
    if not legacy_schema:
        producer_binding = receipt.get("producer_binding")
        issues.extend(_producer_binding_issues(producer_binding))
        if isinstance(producer_binding, Mapping):
            if receipt.get("producer_binding_digest") != _digest(producer_binding):
                issues.append("producer binding digest mismatch")
            issues.extend(_parallel_producer_binding_issues(plan_dir, producer_binding))
        # Reconciliation claims (reconciliation_artifacts SHA-256 bindings) may
        # only be anchored by a matrix-authorized critique producer.  An
        # out-of-scope producer cannot carry canonical reconciliation evidence,
        # so its reconciliation bindings must be rejected as authority-shaped
        # evidence even when the receipt digest is internally consistent.
        reconciliation_artifacts = receipt.get("reconciliation_artifacts")
        if isinstance(reconciliation_artifacts, list) and reconciliation_artifacts:
            producer = (
                producer_binding.get("producer")
                if isinstance(producer_binding, Mapping)
                else None
            )
            if producer not in _AUTHORIZED_CRITIQUE_PRODUCERS:
                issues.append(
                    "reconciliation claims require a matrix-authorized critique producer"
                )
    for field in ("plan_artifact", "critique_artifact"):
        name = receipt.get(field)
        if not isinstance(name, str) or not name or Path(name).name != name:
            issues.append(f"{field} is not a safe artifact basename")
    plan_name = receipt.get("plan_artifact")
    if isinstance(plan_name, str):
        plan_path = plan_dir / plan_name
        if plan_path.is_symlink():
            issues.append(f"source plan artifact is a symlink: {plan_name}")
        elif not plan_path.exists() or not plan_path.is_file():
            issues.append(f"missing source plan artifact {plan_name}")
        else:
            observed = sha256_file(plan_path)
            receipt_sha = receipt.get("plan_sha256")
            if receipt_sha != observed:
                # Sol Tier 1 append-only ledger repair: when the latest plan
                # artifact drifted from its attestation due to worker in-place
                # mutation (now prompt-forbidden), the plan_versions record
                # carries _reconciled_from = the ORIGINAL attestation and the
                # reconciled hash = the current file content.  A custody
                # receipt minted against the original attestation is valid
                # when its plan_sha256 matches the preserved original, and the
                # current file matches the reconciled hash.
                if plan_versions is None:
                    plan_versions = _plan_versions_from_state(plan_dir)
                reconciled = False
                for version in plan_versions or []:
                    if (
                        version.get("file") == plan_name
                        and version.get("hash") == observed
                        and version.get("_reconciled_from") == receipt_sha
                    ):
                        reconciled = True
                        break
                if not reconciled:
                    issues.append(f"source plan artifact hash mismatch for {plan_name}")
    critique_name = receipt.get("critique_artifact")
    if isinstance(critique_name, str):
        critique_path = plan_dir / critique_name
        if critique_path.is_symlink():
            issues.append(f"critique artifact is a symlink: {critique_name}")
        elif not critique_path.exists() or not critique_path.is_file():
            issues.append(f"missing critique artifact {critique_name}")
        elif receipt.get("critique_sha256") != sha256_file(critique_path):
            issues.append(f"critique artifact hash mismatch for {critique_name}")
        else:
            critique = read_json(critique_path)
            if receipt.get("critique_payload_digest") != _digest(critique):
                issues.append(f"critique payload digest mismatch for {critique_name}")
            payload_ids = [
                flag.get("id")
                for flag in critique.get("flags", [])
                if isinstance(flag, dict)
            ]
            if payload_ids != receipt.get("flag_ids"):
                issues.append(f"critique flags do not match receipt for {critique_name}")
            expected_findings = [
                {
                    "finding_id": _stable_finding_id(flag),
                    "flag_id": flag.get("id"),
                    "source_check_id": flag.get("source_check_id"),
                    "category": flag.get("category"),
                    "producer_category": flag.get("producer_category", flag.get("category")),
                    "severity_hint": flag.get("severity_hint"),
                    "producer_severity": flag.get("producer_severity", flag.get("severity_hint")),
                    "blocking": flag.get("severity_hint") != "likely-minor",
                    "concern": flag.get("concern", ""),
                    "evidence": flag.get("evidence", ""),
                    "evidence_digest": _digest(flag.get("evidence", "")),
                }
                for flag in critique.get("flags", [])
                if isinstance(flag, dict)
            ]
            if expected_findings != receipt.get("findings"):
                issues.append(f"critique finding content does not match receipt for {critique_name}")
    raw_sources = receipt.get("raw_sources")
    if not isinstance(raw_sources, list):
        issues.append("receipt raw_sources is not an array")
    else:
        for source in raw_sources:
            if not isinstance(source, Mapping):
                issues.append("raw source row is not an object")
                continue
            name = source.get("artifact")
            current_raw_pattern = re.compile(
                rf"^(?:critique_raw_v{expected_iteration}\.txt|"
                rf"critique_check_.+_(?:producer_v{expected_iteration}\.json|raw_v{expected_iteration}\.txt))$"
            )
            source_path = plan_dir / str(name)
            if (
                not isinstance(name, str)
                or Path(name).name != name
                or current_raw_pattern.fullmatch(name) is None
                or source_path.is_symlink()
                or not source_path.exists()
                or not source_path.is_file()
            ):
                issues.append(f"raw source artifact is missing or unsafe: {name!r}")
            elif source.get("sha256") != sha256_file(plan_dir / name):
                issues.append(f"raw source hash mismatch for {name}")
        if legacy_schema and not any(
            isinstance(source, Mapping)
            and isinstance(source.get("artifact"), str)
            and "_producer_v" in source["artifact"]
            for source in raw_sources
        ):
            issues.append("legacy receipt has no persisted producer reduction artifact")
    issues.extend(
        _artifact_binding_issues(
            receipt.get("reconciliation_artifacts"),
            plan_dir=plan_dir,
            field="reconciliation_artifacts",
        )
    )
    issues.extend(
        _artifact_binding_issues(
            receipt.get("disposition_artifacts"),
            plan_dir=plan_dir,
            field="disposition_artifacts",
        )
    )
    # BRIDGE provenance: bridge_mode and carried_blockers are present on every
    # CL4+ receipt.  An absent field is treated as a pre-CL4 receipt (the
    # receipt_digest already protects against stripping a present field), but a
    # present field must be well-formed so the authority limit is never silently
    # malformed.
    bridge_mode = receipt.get("bridge_mode")
    if bridge_mode is not None and not isinstance(bridge_mode, bool):
        issues.append("receipt bridge_mode must be a boolean")
    carried_blockers = receipt.get("carried_blockers")
    if carried_blockers is not None and (
        not isinstance(carried_blockers, list)
        or any(not isinstance(item, str) or not item for item in carried_blockers)
    ):
        issues.append("receipt carried_blockers must be an array of non-empty strings")
    findings = receipt.get("findings")
    if not isinstance(findings, list):
        issues.append("receipt findings is not an array")
    else:
        finding_ids = [item.get("finding_id") for item in findings if isinstance(item, dict)]
        flag_ids = [item.get("flag_id") for item in findings if isinstance(item, dict)]
        if len(finding_ids) != len(findings) or len(set(finding_ids)) != len(finding_ids):
            issues.append("receipt finding identities are missing or duplicated")
        if len(flag_ids) != len(findings) or len(set(flag_ids)) != len(flag_ids):
            issues.append("receipt flag mappings are missing or duplicated")
        if finding_ids != receipt.get("finding_ids") or flag_ids != receipt.get("flag_ids"):
            issues.append("receipt summary ids differ from finding rows")
        if receipt.get("finding_count") != len(findings):
            issues.append("receipt finding_count differs from finding rows")
    if receipt.get("normalization", {}).get("loss_count") != 0:
        issues.append("receipt reports lossy normalization")
    if issues:
        raise CritiqueCustodyError("critique_custody_receipt_invalid", issues)


def _validate_legacy_migration_receipt(
    plan_dir: Path,
    legacy_path: Path,
    legacy_receipt: Mapping[str, Any],
    migration: Mapping[str, Any],
) -> None:
    match = re.fullmatch(r"critique_custody_v(\d+)\.json", legacy_path.name)
    iteration = int(match.group(1)) if match else -1
    migration_path = _legacy_migration_path(plan_dir, iteration)
    issues: list[str] = []
    if migration_path.is_symlink() or not migration_path.is_file():
        issues.append(f"legacy migration receipt is missing or unsafe: {migration_path.name}")
    elif migration_path.stat().st_nlink != 1:
        issues.append(f"legacy migration receipt has multiple hard links: {migration_path.name}")
    if migration.get("schema_version") != LEGACY_MIGRATION_SCHEMA_VERSION:
        issues.append("legacy migration schema is unsupported")
    if migration.get("iteration") != iteration:
        issues.append("legacy migration iteration mismatch")
    if migration.get("admitted") is not True:
        issues.append("legacy migration receipt is not admitted")
    unsigned = dict(migration)
    stored_digest = unsigned.pop("receipt_digest", None)
    if stored_digest != _digest(unsigned):
        issues.append("legacy migration receipt digest mismatch")
    source = migration.get("source_receipt")
    expected_source = {
        "artifact": legacy_path.name,
        "sha256": sha256_file(legacy_path),
        "schema_version": LEGACY_CUSTODY_SCHEMA_VERSION,
        "receipt_digest": legacy_receipt.get("receipt_digest"),
    }
    if source != expected_source:
        issues.append("legacy migration source receipt binding mismatch")
    expected_evidence = _legacy_artifact_evidence(legacy_receipt)
    if migration.get("artifact_evidence") != expected_evidence:
        issues.append("legacy migration artifact evidence mismatch")
    expected_binding = _legacy_producer_evidence_binding(legacy_receipt)
    if migration.get("producer_binding") != expected_binding:
        issues.append("legacy migration producer evidence binding mismatch")
    if migration.get("producer_binding_digest") != _digest(expected_binding):
        issues.append("legacy migration producer binding digest mismatch")
    current_lineage = _legacy_lineage_evidence(plan_dir, legacy_path, legacy_receipt)
    issues.extend(
        _legacy_lineage_evidence_issues(
            migration.get("lineage_evidence"),
            current_lineage,
        )
    )
    if migration.get("custody_status") != "legacy_unbound":
        issues.append("legacy migration does not explicitly preserve unbound custody status")
    if not isinstance(migration.get("actor"), str) or not migration.get("actor", "").strip():
        issues.append("legacy migration actor is missing")
    if not isinstance(migration.get("reason"), str) or not migration.get("reason", "").strip():
        issues.append("legacy migration reason is missing")
    if issues:
        raise CritiqueCustodyError("critique_custody_legacy_migration_invalid", issues)


def _migrate_legacy_critique_custody_locked(
    plan_dir: Path,
    *,
    iteration: int,
    expected_source_sha256: str,
    actor: str,
    reason: str,
) -> list[dict[str, Any]]:
    """Admit intact v1 receipts without rewriting or overstating their authority."""
    plan_dir = plan_dir.resolve()
    if not actor.strip() or not reason.strip():
        raise CritiqueCustodyError(
            "critique_custody_legacy_migration_invalid",
            ["actor and reason must be non-empty"],
        )
    path = plan_dir / f"critique_custody_v{iteration}.json"
    paths = [path]
    migrated: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            raise CritiqueCustodyError(
                "critique_custody_missing", [f"missing legacy receipt {path.name}"]
            )
        receipt = read_json(path)
        observed_source_sha = sha256_file(path)
        if observed_source_sha != expected_source_sha256:
            raise CritiqueCustodyError(
                "critique_custody_legacy_source_conflict",
                [
                    f"{path.name} expected {expected_source_sha256}, "
                    f"observed {observed_source_sha}"
                ],
            )
        if receipt.get("schema_version") == CUSTODY_SCHEMA_VERSION:
            continue
        if receipt.get("schema_version") != LEGACY_CUSTODY_SCHEMA_VERSION:
            raise CritiqueCustodyError(
                "critique_custody_legacy_schema_unsupported",
                [f"{path.name}: {receipt.get('schema_version')!r}"],
            )
        match = re.fullmatch(r"critique_custody_v(\d+)\.json", path.name)
        if match is None:
            raise CritiqueCustodyError(
                "critique_custody_receipt_invalid", [f"non-canonical receipt {path.name}"]
            )
        receipt_iteration = int(match.group(1))
        plan_name = receipt.get("plan_artifact")
        if not isinstance(plan_name, str) or not plan_name:
            raise CritiqueCustodyError(
                "critique_custody_receipt_invalid", [f"{path.name} has no plan artifact"]
            )
        _validate_production_receipt(
            plan_dir,
            receipt,
            expected_iteration=receipt_iteration,
            expected_receipt_path=path,
            expected_plan_artifact=plan_name,
            allow_legacy_schema=True,
        )
        state = read_json(plan_dir / "state.json")
        current_iteration = state.get("iteration")
        if (
            state.get("current_state") != "gated"
            or not isinstance(current_iteration, int)
            or current_iteration < receipt_iteration
            or state.get("active_step") is not None
        ):
            raise CritiqueCustodyError(
                "critique_custody_legacy_state_invalid",
                [
                    "legacy migration requires a gated plan at or beyond the receipt "
                    "iteration with no active step"
                ],
            )
        binding = _legacy_producer_evidence_binding(receipt)
        lineage = _legacy_lineage_evidence(plan_dir, path, receipt)
        migration = {
            "schema_version": LEGACY_MIGRATION_SCHEMA_VERSION,
            "iteration": receipt_iteration,
            "produced_at": now_utc(),
            "source_receipt": {
                "artifact": path.name,
                "sha256": sha256_file(path),
                "schema_version": LEGACY_CUSTODY_SCHEMA_VERSION,
                "receipt_digest": receipt.get("receipt_digest"),
            },
            "artifact_evidence": _legacy_artifact_evidence(receipt),
            "lineage_evidence": lineage,
            "producer_binding": binding,
            "producer_binding_digest": _digest(binding),
            "custody_status": "legacy_unbound",
            "actor": actor.strip(),
            "reason": reason.strip(),
            "authority_limit": (
                "producer and invocation identities were not recorded by v1; "
                "admission proves only the immutable receipt-to-artifact hash chain"
            ),
            "admitted": True,
        }
        migration["receipt_digest"] = _digest(migration)
        migration_path = _legacy_migration_path(plan_dir, receipt_iteration)
        if sha256_file(path) != expected_source_sha256:
            raise CritiqueCustodyError(
                "critique_custody_legacy_source_conflict",
                [f"{path.name} changed while migration evidence was gathered"],
            )
        published = _publish_receipt_create_once(migration_path, migration)
        _validate_legacy_migration_receipt(plan_dir, path, receipt, published)
        migrated.append(published)
    return migrated


def migrate_legacy_critique_custody(
    plan_dir: Path,
    *,
    iteration: int,
    expected_source_sha256: str,
    actor: str,
    reason: str,
) -> list[dict[str, Any]]:
    """CAS-migrate one gated legacy receipt while holding the canonical plan lock."""
    plan_dir = plan_dir.resolve()
    with plan_lock(plan_dir, step="migrate-legacy-critique-custody"):
        return _migrate_legacy_critique_custody_locked(
            plan_dir,
            iteration=iteration,
            expected_source_sha256=expected_source_sha256,
            actor=actor,
            reason=reason,
        )


def _validate_receipt_at_path(
    plan_dir: Path,
    path: Path,
    receipt: Mapping[str, Any],
    *,
    expected_plan_artifact: str | None = None,
) -> None:
    match = re.fullmatch(r"critique_custody_v(\d+)\.json", path.name)
    if match is None:
        raise CritiqueCustodyError(
            "critique_custody_receipt_invalid",
            [f"receipt filename is not canonical: {path.name}"],
        )
    plan_name = expected_plan_artifact or receipt.get("plan_artifact")
    if not isinstance(plan_name, str) or not plan_name:
        raise CritiqueCustodyError(
            "critique_custody_receipt_invalid",
            ["receipt has no source plan artifact"],
        )
    legacy_schema = receipt.get("schema_version") == LEGACY_CUSTODY_SCHEMA_VERSION
    _validate_production_receipt(
        plan_dir,
        receipt,
        expected_iteration=int(match.group(1)),
        expected_receipt_path=path,
        expected_plan_artifact=plan_name,
        allow_legacy_schema=legacy_schema,
    )
    if legacy_schema:
        migration_path = _legacy_migration_path(plan_dir, int(match.group(1)))
        if not migration_path.exists():
            raise CritiqueCustodyError(
                "critique_custody_legacy_migration_missing",
                [
                    f"{path.name} uses {LEGACY_CUSTODY_SCHEMA_VERSION}; run the "
                    "explicit legacy custody migration before continuing"
                ],
            )
        _validate_legacy_migration_receipt(
            plan_dir,
            path,
            receipt,
            read_json(migration_path),
        )


def validate_gate_input_custody(plan_dir: Path, state: PlanState) -> dict[str, Any]:
    """Prove the latest critique and registry agree before gate dispatch."""
    iteration = int(state["iteration"])
    path = plan_dir / f"critique_custody_v{iteration}.json"
    if not path.exists():
        raise CritiqueCustodyError(
            "critique_custody_missing",
            [f"gate requires {path.name}; rerun critique"],
        )
    receipt = read_json(path)
    _validate_receipt_at_path(
        plan_dir,
        path,
        receipt,
        expected_plan_artifact=latest_plan_path(plan_dir, state).name,
    )
    registry = load_flag_registry(plan_dir)
    registry_ids = {
        flag.get("id")
        for flag in registry.get("flags", [])
        if isinstance(flag, dict)
    }
    missing = [flag_id for flag_id in receipt.get("flag_ids", []) if flag_id not in registry_ids]
    if missing:
        raise CritiqueCustodyError(
            "critique_registry_mapping_missing",
            [f"receipt flags missing from registry: {missing!r}"],
        )
    return {
        "schema_version": CUSTODY_SCHEMA_VERSION,
        "receipt": path.name,
        "receipt_sha256": sha256_file(path),
        "finding_count": receipt["finding_count"],
        "finding_ids": receipt["finding_ids"],
        "flag_ids": receipt["flag_ids"],
        "loss_count": 0,
        "admitted": True,
    }


def _receipt_paths(plan_dir: Path) -> list[Path]:
    def iteration(path: Path) -> int:
        match = re.fullmatch(r"critique_custody_v(\d+)\.json", path.name)
        return int(match.group(1)) if match else -1

    return sorted(plan_dir.glob("critique_custody_v*.json"), key=iteration)


_PLAN_DIGEST_RE = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")


def _normalized_digest(value: Any) -> str | None:
    """Bare hex for an optionally ``sha256:``-prefixed digest; ``None`` otherwise."""
    if not isinstance(value, str):
        return None
    match = _PLAN_DIGEST_RE.fullmatch(value.strip())
    return match.group(1).lower() if match else None


def _verified_by_current_critique(
    *,
    flag: Mapping[str, Any],
    finding: Mapping[str, Any],
    verified_in: str,
    verified_iteration: int,
    plan_dir: Path,
    receipts: Sequence[tuple[str, Mapping[str, Any], str]],
    occurrence_receipt: Mapping[str, Any],
    current_plan_name: str,
    current_plan_sha256: str,
) -> dict[str, Any] | None:
    """Accept a ``verified`` finding cleared by the current-iteration critique.

    Every precondition is required; any miss returns ``None`` so the caller
    stays fail-closed. The receipt set must already be validated by
    ``_validate_receipt_at_path`` — this helper never rescans receipts.
    """
    # 1. Exactly one validated receipt binds the named critique artifact to the
    #    CURRENT plan byte-identically (name + normalized sha equality).
    bound: tuple[str, Mapping[str, Any], str] | None = None
    for receipt_name, receipt, receipt_sha256 in receipts:
        if (
            receipt.get("iteration") == verified_iteration
            and receipt.get("critique_artifact") == verified_in
            and receipt.get("plan_artifact") == current_plan_name
            and _normalized_digest(receipt.get("plan_sha256"))
            == _normalized_digest(current_plan_sha256)
        ):
            if bound is not None:
                return None
            bound = (receipt_name, receipt, receipt_sha256)
    if bound is None:
        return None
    bound_name, bound_receipt, bound_sha256 = bound
    # 2. The bound critique artifact must be the digest the receipt recorded,
    #    and must actually verify this flag.
    critique_path = plan_dir / verified_in
    if not critique_path.is_file():
        return None
    critique_digest = _normalized_digest(sha256_file(critique_path))
    if critique_digest is None or critique_digest != _normalized_digest(
        bound_receipt.get("critique_sha256")
    ):
        return None
    critique = read_json(critique_path)
    bound_references = critique.get("verified_flag_ids")
    if not isinstance(bound_references, list):
        return None
    flag_id = str(flag.get("id"))
    correction = flag.get("id_correction") if isinstance(flag.get("id_correction"), dict) else {}
    referenced = False
    for reference in bound_references:
        if not isinstance(reference, str):
            continue
        if reference == flag_id:
            referenced = True
            break
        if (
            correction.get("from") == reference
            and correction.get("to") == flag_id
            and correction.get("recorded_in") == "critique"
            and correction.get("reference_kind") == "verified"
            and correction.get("at_iteration") == verified_iteration
        ):
            referenced = True
            break
    if not referenced:
        return None
    # 3. The verification must postdate this finding's occurrence.
    try:
        occurrence_iteration = int(occurrence_receipt.get("iteration"))
    except (TypeError, ValueError):
        return None
    if occurrence_iteration >= verified_iteration:
        return None
    # 4. Selected evidence must be non-empty.
    evidence = ""
    for candidate in (flag.get("verify_rationale"), finding.get("evidence"), flag.get("evidence")):
        if isinstance(candidate, str) and candidate.strip():
            evidence = candidate
            break
    if not evidence.strip():
        return None
    return {
        "finding_id": finding["finding_id"],
        "flag_id": str(finding.get("flag_id")),
        "disposition": "verified_by_current_critique",
        "verified_in": verified_in,
        "verification_receipt": bound_name,
        "verification_receipt_sha256": bound_sha256,
        "plan_artifact": current_plan_name,
        "plan_sha256": current_plan_sha256,
        "evidence": evidence,
    }


def _resolution_for_finding(
    flag: Mapping[str, Any],
    finding: Mapping[str, Any],
    *,
    current_plan_name: str,
    current_plan_sha256: str,
    source_plan_name: str,
    source_plan_sha256: str,
    plan_version_order: Mapping[str, int],
    gate_expected: bool,
    plan_dir: Path,
    receipts: Sequence[tuple[str, Mapping[str, Any], str]],
    occurrence_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    flag_id = str(finding.get("flag_id"))
    status = flag.get("status")
    resolution = flag.get("resolution") if isinstance(flag.get("resolution"), dict) else {}
    gate_resolution = (
        flag.get("gate_resolution") if isinstance(flag.get("gate_resolution"), dict) else {}
    )
    plan_mutated = current_plan_sha256 != source_plan_sha256
    addressed_in = str(flag.get("addressed_in") or "")
    source_version = plan_version_order.get(source_plan_name)
    addressed_version = plan_version_order.get(addressed_in)
    current_version = plan_version_order.get(current_plan_name)
    resolution_targets_admitted_descendant = bool(
        source_version is not None
        and addressed_version is not None
        and current_version is not None
        and source_version < addressed_version <= current_version
    )
    fixed_claim = (
        resolution.get("kind") == "fixed"
        and isinstance(resolution.get("claim"), str)
        and bool(resolution["claim"].strip())
        and isinstance(resolution.get("where"), str)
        and bool(resolution["where"].strip())
        and resolution_targets_admitted_descendant
        and plan_mutated
    )
    # A later critique/gate iteration may carry the registry status
    # ``accepted_tradeoff`` forward after the gate worker has stopped
    # repeating its accepted-tradeoff envelope. That status is not, by
    # itself, a reason to fail finalization when the earlier revise phase
    # already left a traceable fixed claim on an admitted descendant plan.
    # Require the same exact mutation/lineage proof as a verified finding;
    # tradeoffs without that proof remain fail-closed below.
    if status == "accepted_tradeoff" and gate_expected and fixed_claim:
        return {
            "finding_id": finding["finding_id"],
            "flag_id": flag_id,
            "disposition": "verified_plan_mutation",
            "plan_artifact": current_plan_name,
            "plan_sha256": current_plan_sha256,
            "evidence": gate_resolution.get("evidence") or flag.get("verify_rationale") or resolution.get("claim"),
        }
    if status == "verified" and fixed_claim:
        return {
            "finding_id": finding["finding_id"],
            "flag_id": flag_id,
            "disposition": "verified_plan_mutation",
            "plan_artifact": current_plan_name,
            "plan_sha256": current_plan_sha256,
            "evidence": gate_resolution.get("evidence") or flag.get("verify_rationale") or resolution.get("claim"),
        }
    if status == "verified" and not fixed_claim and plan_mutated:
        verified_in = str(flag.get("verified_in") or "")
        verified_match = re.fullmatch(r"critique_v([1-9][0-9]*)\.json", verified_in)
        if verified_match is not None:
            acceptance = _verified_by_current_critique(
                flag=flag,
                finding=finding,
                verified_in=verified_in,
                verified_iteration=int(verified_match.group(1)),
                plan_dir=plan_dir,
                receipts=receipts,
                occurrence_receipt=occurrence_receipt,
                current_plan_name=current_plan_name,
                current_plan_sha256=current_plan_sha256,
            )
            if acceptance is not None:
                return acceptance
        if (
            gate_expected
            and verified_in == "gate.json"
            and gate_resolution.get("action") == "verify_fixed"
        ):
            gate_evidence = gate_resolution.get("evidence")
            if (
                isinstance(gate_evidence, str)
                and gate_evidence.strip()
                and not is_rubber_stamp(gate_evidence, strict=True)
                and " ".join(gate_evidence.split()).casefold()
                != " ".join(str(flag.get("concern") or "").split()).casefold()
            ):
                return {
                    "finding_id": finding["finding_id"],
                    "flag_id": flag_id,
                    "disposition": "verified_by_gate_evidence",
                    "plan_artifact": current_plan_name,
                    "plan_sha256": current_plan_sha256,
                    "evidence": gate_evidence,
                }
    if status == "gate_disputed" and gate_expected:
        evidence = gate_resolution.get("evidence")
        if isinstance(evidence, str) and evidence.strip():
            return {
                "finding_id": finding["finding_id"],
                "flag_id": flag_id,
                "disposition": "invalidated_with_evidence",
                "evidence": evidence,
            }
    if (
        status == "accepted_tradeoff"
        and gate_expected
        and gate_resolution.get("action") == "accept_tradeoff"
    ):
        rationale = gate_resolution.get("rationale")
        if isinstance(rationale, str) and rationale.strip():
            return {
                "finding_id": finding["finding_id"],
                "flag_id": flag_id,
                "disposition": "minor_tradeoff",
                "evidence": rationale,
            }
    if (
        status in {"open", "verified"}
        and finding.get("blocking") is False
        and flag.get("severity") == "minor"
        and str(flag.get("concern") or "").strip()
        == str(finding.get("concern") or "").strip()
        and str(flag.get("evidence") or "").strip()
        == str(finding.get("evidence") or "").strip()
    ):
        resolution_record = {
            "finding_id": finding["finding_id"],
            "flag_id": flag_id,
            "disposition": "tracked_nonblocking_observation",
            "evidence": flag.get("evidence") or flag.get("concern"),
        }
        if isinstance(flag.get("verified_in"), str) and flag["verified_in"].strip():
            resolution_record["verified_in"] = flag["verified_in"]
        return resolution_record
    if status == "addressed" and not gate_expected and fixed_claim:
        return {
            "finding_id": finding["finding_id"],
            "flag_id": flag_id,
            "disposition": "plan_mutation_light_workflow",
            "plan_artifact": current_plan_name,
            "plan_sha256": current_plan_sha256,
            "evidence": resolution.get("claim"),
        }
    raise CritiqueCustodyError(
        "critique_finding_unresolved",
        [
            f"finding {finding.get('finding_id')} / flag {flag_id} remains {status!r}; "
            "it needs a traceable plan mutation plus verification, or an evidence-backed invalidation"
        ],
    )


def write_critique_clearance(plan_dir: Path, state: PlanState) -> dict[str, Any]:
    """Join every production receipt to current resolution evidence."""
    receipt_paths = _receipt_paths(plan_dir)
    robustness = configured_robustness(state)
    critique_expected = workflow_includes_step(robustness, "critique")
    gate_expected = workflow_includes_step(robustness, "gate")
    if critique_expected and not receipt_paths:
        raise CritiqueCustodyError(
            "critique_custody_missing",
            ["workflow includes critique but has no production receipt"],
        )
    current_plan = latest_plan_path(plan_dir, state)
    current_plan_sha = sha256_file(current_plan)
    plan_version_order = {
        str(version.get("file")): int(version.get("version"))
        for version in state.get("plan_versions", [])
        if isinstance(version, Mapping)
        and isinstance(version.get("file"), str)
        and isinstance(version.get("version"), int)
    }
    registry = load_flag_registry(plan_dir)
    by_id = {
        str(flag.get("id")): flag
        for flag in registry.get("flags", [])
        if isinstance(flag, dict) and flag.get("id")
    }
    resolutions: list[dict[str, Any]] = []
    source_receipts: list[dict[str, Any]] = []
    validated_receipts: list[tuple[str, Mapping[str, Any], str]] = []
    latest_occurrences: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    # Aggregate BRIDGE provenance across every joined receipt.  The clearance is
    # BRIDGE when any bound production receipt carries bridge_mode=true, and it
    # inherits the union of carried blockers so finalize custody can never hide
    # a BRIDGE source receipt behind a canonical-looking clearance.
    clearance_bridge_mode = False
    clearance_carried_blockers: list[str] = []
    for path in receipt_paths:
        receipt = read_json(path)
        _validate_receipt_at_path(plan_dir, path, receipt)
        receipt_sha256 = sha256_file(path)
        source_receipts.append({"artifact": path.name, "sha256": receipt_sha256})
        validated_receipts.append((path.name, receipt, receipt_sha256))
        if receipt.get("bridge_mode") is True:
            clearance_bridge_mode = True
        for blocker in receipt.get("carried_blockers", []) or []:
            if isinstance(blocker, str) and blocker and blocker not in clearance_carried_blockers:
                clearance_carried_blockers.append(blocker)
        for finding in receipt.get("findings", []):
            flag_id = str(finding.get("flag_id"))
            finding_id = str(finding.get("finding_id"))
            occurrence_key = f"finding:{finding_id}"
            if flag_id != finding_id:
                # Receipts created before reducer-owned canonical IDs can carry
                # a worker-local ordinal (for example ``verifiability-0``).
                # Such an ordinal is not identity authority.  A later
                # non-blocking observation in the same producer slot may
                # supersede it, but a significant occurrence remains strict so
                # migration can never hide a blocking finding.
                occurrence_key = f"legacy-producer-slot:{flag_id}"
                prior_occurrence = latest_occurrences.get(occurrence_key)
                if prior_occurrence is not None:
                    prior_finding = prior_occurrence[0]
                    prior_identity = str(prior_finding.get("finding_id"))
                    if prior_identity != finding_id and (
                        prior_finding.get("blocking") is not False
                        or finding.get("blocking") is not False
                    ):
                        raise CritiqueCustodyError(
                            "critique_finding_identity_reused",
                            [
                                f"legacy producer slot {flag_id!r} changed identity "
                                f"from {prior_identity} to {finding_id} across a "
                                "blocking occurrence"
                            ],
                        )
            # Later critique rounds supersede the occurrence context for the
            # same stable finding. A finding that recurs on the current plan
            # cannot be cleared using an older plan mutation receipt.
            latest_occurrences[occurrence_key] = (finding, receipt)
    for finding, receipt in latest_occurrences.values():
        finding_id = str(finding.get("finding_id"))
        flag_id = str(finding.get("flag_id"))
        flag = by_id.get(flag_id)
        if flag is None:
            raise CritiqueCustodyError(
                "critique_registry_mapping_missing",
                [f"finding {finding_id} has no registry flag {flag_id!r}"],
            )
        resolutions.append(
            _resolution_for_finding(
                flag,
                finding,
                current_plan_name=current_plan.name,
                current_plan_sha256=current_plan_sha,
                source_plan_name=str(receipt.get("plan_artifact") or ""),
                source_plan_sha256=str(receipt.get("plan_sha256")),
                plan_version_order=plan_version_order,
                gate_expected=gate_expected,
                plan_dir=plan_dir,
                receipts=validated_receipts,
                occurrence_receipt=receipt,
            )
        )
    clearance = {
        "schema_version": CLEARANCE_SCHEMA_VERSION,
        "produced_at": now_utc(),
        "workflow": {
            "robustness": robustness,
            "critique_expected": critique_expected,
            "gate_expected": gate_expected,
        },
        "source_receipts": source_receipts,
        "plan_artifact": current_plan.name,
        "plan_sha256": current_plan_sha,
        "finding_count": len(resolutions),
        "finding_ids": [item["finding_id"] for item in resolutions],
        "resolutions": resolutions,
        # BRIDGE provenance aggregated from the joined source receipts.  A
        # clearance is canonical gate authority only when no source receipt is
        # BRIDGE-mode; carrying bridge_mode/carried_blockers in-band lets
        # finalize custody refuse to treat a BRIDGE clearance as canonical.
        "bridge_mode": clearance_bridge_mode,
        "carried_blockers": clearance_carried_blockers,
        "admitted": True,
    }
    clearance["clearance_digest"] = _digest(clearance)
    atomic_write_json(plan_dir / "critique_clearance.json", clearance)
    return clearance


def bind_finalize_custody(
    plan_dir: Path,
    payload: dict[str, Any],
    clearance: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind current clearance to the exact post-mutation finalized graph."""
    clearance_path = plan_dir / "critique_clearance.json"
    if not clearance_path.exists():
        raise CritiqueCustodyError("critique_clearance_missing", [clearance_path.name])
    validate_finalize_resolution_coverage(payload, clearance)
    # Propagate the clearance's BRIDGE provenance into the finalize binding.  A
    # finalize binding grants canonical gate authority only when the clearance
    # is not BRIDGE-mode; when bridge_mode is true the binding explicitly denies
    # canonical authority so a downstream consumer cannot treat the bound
    # custody as canonical gate/finalize authority.
    binding_bridge_mode = bool(clearance.get("bridge_mode", False))
    binding_carried_blockers = list(clearance.get("carried_blockers", []) or [])
    binding = {
        "schema_version": FINAL_BINDING_SCHEMA_VERSION,
        "clearance_artifact": clearance_path.name,
        "clearance_sha256": sha256_file(clearance_path),
        "clearance_digest": clearance.get("clearance_digest"),
        "plan_artifact": clearance.get("plan_artifact"),
        "plan_sha256": clearance.get("plan_sha256"),
        "finding_count": clearance.get("finding_count"),
        "finding_ids": clearance.get("finding_ids", []),
        "task_contract_hash": task_contract_hash(payload),
        "resolution_coverage_digest": _digest(payload.get("critique_resolution_coverage", [])),
        "bridge_mode": binding_bridge_mode,
        "carried_blockers": binding_carried_blockers,
        "canonical_gate_authority": not binding_bridge_mode,
        "revalidated_at": now_utc(),
    }
    payload["critique_custody"] = binding
    return binding


def validate_finalize_resolution_coverage(
    payload: Mapping[str, Any],
    clearance: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Require an exact typed finding-to-final-task join from the finalizer."""
    expected_ids = clearance.get("finding_ids", [])
    if not isinstance(expected_ids, list) or any(not isinstance(item, str) for item in expected_ids):
        raise CritiqueCustodyError(
            "critique_clearance_invalid",
            ["clearance finding_ids must be an array of strings"],
        )
    raw_rows = payload.get("critique_resolution_coverage", [])
    if not isinstance(raw_rows, list):
        raise CritiqueCustodyError(
            "finalize_critique_coverage_invalid",
            ["critique_resolution_coverage must be an array"],
        )
    task_ids = {
        task.get("id")
        for task in payload.get("tasks", [])
        if isinstance(task, Mapping) and isinstance(task.get("id"), str)
    }
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    observed: list[str] = []
    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, Mapping):
            issues.append(f"coverage row {index} is not an object")
            continue
        finding_id = raw_row.get("finding_id")
        mapped_tasks = raw_row.get("task_ids")
        evidence = raw_row.get("resolution_evidence")
        if not isinstance(finding_id, str) or not finding_id:
            issues.append(f"coverage row {index} has no finding_id")
            continue
        observed.append(finding_id)
        if (
            not isinstance(mapped_tasks, list)
            or not mapped_tasks
            or any(not isinstance(task_id, str) or task_id not in task_ids for task_id in mapped_tasks)
            or len(set(mapped_tasks)) != len(mapped_tasks)
        ):
            issues.append(f"finding {finding_id} has missing, duplicate, or unknown task_ids")
        if not isinstance(evidence, str) or not evidence.strip():
            issues.append(f"finding {finding_id} has no resolution_evidence")
        rows.append(dict(raw_row))
    if len(observed) != len(set(observed)):
        issues.append("critique_resolution_coverage contains duplicate finding ids")
    if set(observed) != set(expected_ids) or len(observed) != len(expected_ids):
        issues.append(f"coverage expected findings {expected_ids!r}, observed {observed!r}")
    if issues:
        raise CritiqueCustodyError("finalize_critique_coverage_invalid", issues)
    return rows


def assert_finalize_custody(
    plan_dir: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Reject execution when v2 custody or exact graph evidence is missing."""
    if payload.get("task_contract_version") != 2:
        return None
    binding = payload.get("critique_custody")
    if not isinstance(binding, Mapping):
        raise CritiqueCustodyError(
            "finalize_critique_custody_missing",
            ["task_contract_version=2 requires critique_custody"],
        )
    issues: list[str] = []
    if binding.get("schema_version") != FINAL_BINDING_SCHEMA_VERSION:
        issues.append("unsupported finalize custody binding")
    if binding.get("task_contract_hash") != task_contract_hash(payload):
        issues.append("finalized graph hash differs from critique custody binding")
    if binding.get("resolution_coverage_digest") != _digest(
        payload.get("critique_resolution_coverage", [])
    ):
        issues.append("finalizer finding-to-task coverage differs from custody binding")
    clearance_name = binding.get("clearance_artifact")
    if not isinstance(clearance_name, str) or Path(clearance_name).name != clearance_name:
        issues.append("invalid clearance artifact reference")
    else:
        clearance_path = plan_dir / clearance_name
        if not clearance_path.exists():
            issues.append(f"missing clearance artifact {clearance_name}")
        elif binding.get("clearance_sha256") != sha256_file(clearance_path):
            issues.append("clearance artifact hash mismatch")
        else:
            clearance = read_json(clearance_path)
            if clearance.get("admitted") is not True:
                issues.append("clearance is not admitted")
            unsigned_clearance = dict(clearance)
            stored_clearance_digest = unsigned_clearance.pop("clearance_digest", None)
            if stored_clearance_digest != _digest(unsigned_clearance):
                issues.append("clearance content digest mismatch")
            if binding.get("clearance_digest") != clearance.get("clearance_digest"):
                issues.append("clearance digest mismatch")
            if binding.get("finding_count") != clearance.get("finding_count"):
                issues.append("binding finding_count differs from clearance")
            if binding.get("finding_ids") != clearance.get("finding_ids"):
                issues.append("binding finding_ids differ from clearance")
            try:
                validate_finalize_resolution_coverage(payload, clearance)
            except CritiqueCustodyError as error:
                issues.extend(error.issues)
            resolution_ids = [
                row.get("finding_id")
                for row in clearance.get("resolutions", [])
                if isinstance(row, Mapping)
            ]
            if resolution_ids != clearance.get("finding_ids"):
                issues.append("clearance resolution rows differ from finding ids")
            for source in clearance.get("source_receipts", []):
                if not isinstance(source, Mapping):
                    issues.append("clearance source receipt row is malformed")
                    continue
                source_name = source.get("artifact")
                if not isinstance(source_name, str) or Path(source_name).name != source_name:
                    issues.append("clearance source receipt reference is unsafe")
                    continue
                source_path = plan_dir / source_name
                if not source_path.exists() or source.get("sha256") != sha256_file(source_path):
                    issues.append(f"clearance source receipt mismatch for {source_name}")
                    continue
                try:
                    _validate_receipt_at_path(
                        plan_dir,
                        source_path,
                        read_json(source_path),
                    )
                except CritiqueCustodyError as error:
                    issues.extend(error.issues)
            plan_name = clearance.get("plan_artifact")
            if not isinstance(plan_name, str) or not (plan_dir / plan_name).exists():
                issues.append("clearance plan artifact is missing")
            elif clearance.get("plan_sha256") != sha256_file(plan_dir / plan_name):
                issues.append("clearance plan hash mismatch")
            # Negative-authority boundary: finalize custody must never treat a
            # bridge_mode=true clearance as canonical gate authority.  The
            # binding's bridge_mode must match the clearance's aggregated bridge
            # mode, and when the clearance is BRIDGE the binding must explicitly
            # deny canonical gate authority.  This is what prevents a
            # BRIDGE-mode receipt from authorizing finalize even when its receipt
            # digest is internally consistent.
            clearance_bridge_mode = bool(clearance.get("bridge_mode", False))
            if binding.get("bridge_mode") != clearance_bridge_mode:
                issues.append("finalize custody bridge_mode differs from clearance source receipts")
            if clearance_bridge_mode and binding.get("canonical_gate_authority") is not False:
                issues.append("bridge_mode=true clearance cannot bind canonical gate authority")
    if issues:
        raise CritiqueCustodyError("finalize_critique_custody_invalid", issues)
    return dict(binding)


__all__ = [
    "CritiqueCustodyError",
    "assert_finalize_custody",
    "bind_finalize_custody",
    "migrate_legacy_critique_custody",
    "prepare_critique_payload",
    "validate_gate_input_custody",
    "validate_finalize_resolution_coverage",
    "write_critique_clearance",
    "write_critique_production_receipt",
]


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create fail-closed sidecar admissions for intact legacy critique custody receipts."
    )
    parser.add_argument("migrate-legacy", choices=["migrate-legacy"])
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    receipts = migrate_legacy_critique_custody(
        args.plan_dir,
        iteration=args.iteration,
        expected_source_sha256=args.expected_source_sha256,
        actor=args.actor,
        reason=args.reason,
    )
    print(json.dumps({"migrated": receipts}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
