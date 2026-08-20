"""Mechanical, fail-closed M11 predecessor wrapper derivation.

The M11 aggregate consumes four predecessor wrapper families, but the genuine
source artifacts use their own milestone-native schemas.  This module reads
those source shapes, validates them without rewriting the source, and emits a
small content-addressed wrapper.  A wrapper may describe a blocked source; its
mere existence never means that the prerequisite is satisfied.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan.orchestration.m11_acceptance import (
    PredecessorAdapterResult,
    validate_a7_evidence,
    validate_f01_f17_evidence,
    validate_m10_c01_c20_evidence,
    validate_m5_evidence,
)


WRAPPER_SCHEMA = "m11.predecessor-wrapper.v1"
SATISFIED = "satisfied"
BLOCKED = "blocked"

M10_C01_C20_PATH = Path("evidence/m10-c01-c20-conformance.json")
F01_F17_PATH = Path("evidence/m10-f01-f17-fault-matrix.json")
M5_FINAL_ATTESTATION_PATH = Path(
    ".megaplan/initiatives/custody-control-plane/handoffs/"
    "m5-run-authority-receipt-reconciliation-and-retirement/final-attestation.json"
)
M5_COMPLETION_MANIFEST_PATH = M5_FINAL_ATTESTATION_PATH.with_name(
    "completion-manifest.json"
)
M5_PROOF_MAP_PATH = M5_FINAL_ATTESTATION_PATH.with_name("proof-map.json")
M5_MIGRATION_MATRIX_PATH = Path("evidence/migration-matrix-reconciled.json")
A7_RESEARCH_PATH = Path(
    ".megaplan/plans/m11-cross-contract-acceptance-20260728-1035/research.json"
)
A7_INVENTORY_PATH = Path("evidence/a7-legacy-bypass-inventory.json")
A7_SOURCE_PATHS = (
    Path("evidence/authority-reader-registry.json"),
    Path("evidence/controlled-writer-registry.json"),
    Path("evidence/rollout-deletion-register.json"),
    Path("evidence/wbc-historical-adapters.json"),
    Path("evidence/migration-matrix-reconciled.json"),
)

WRAPPER_PATHS: dict[str, Path] = {
    "m10_c01_c20": Path("evidence/C-family.json"),
    "m10_handoff": Path("evidence/m10-handoff.json"),
    "m5": Path("evidence/M5-family.json"),
    "a7": Path("evidence/A7-family.json"),
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _load_source(repo_root: Path, relative_path: Path) -> tuple[dict[str, Any], str]:
    path = repo_root / relative_path
    try:
        raw = path.read_bytes()
        parsed = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}, ""
    if not isinstance(parsed, dict):
        return {}, _sha256_bytes(raw)
    return parsed, _sha256_bytes(raw)


def _source_ref(path: Path, digest: str) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": digest}


def _failure(kind: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "detail": detail, **extra}


@dataclass(frozen=True)
class DerivedPredecessor:
    family: str
    source_artifacts: list[dict[str, str]]
    adapter_results: list[PredecessorAdapterResult]
    derivation_failures: list[dict[str, Any]] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)
    next_action: str = ""

    @property
    def satisfied(self) -> bool:
        return (
            bool(self.adapter_results)
            and all(result.passed for result in self.adapter_results)
            and not self.derivation_failures
            and all(source.get("sha256", "").startswith("sha256:")
                    for source in self.source_artifacts)
        )

    def wrapper(self) -> dict[str, Any]:
        status = SATISFIED if self.satisfied else BLOCKED
        payload: dict[str, Any] = {
            "schema": WRAPPER_SCHEMA,
            "family": self.family,
            "status": status,
            "source_artifacts": self.source_artifacts,
            "adapter_results": [result.to_dict() for result in self.adapter_results],
            "failures": [
                *self.derivation_failures,
                *[
                    failure
                    for result in self.adapter_results
                    for failure in result.failures
                ],
            ],
            "observations": self.observations,
            "next_action": self.next_action,
        }
        payload["content_sha256"] = _sha256_bytes(_canonical_bytes(payload))
        return payload


def _normalize_m10_c01_c20(
    source: dict[str, Any], source_digest: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    if source.get("schema_version") != 1:
        failures.append(_failure(
            "schema_mismatch",
            "M10 C01-C20 source must use schema_version 1",
            actual=source.get("schema_version"),
        ))
    if source.get("milestone") != "M10":
        failures.append(_failure(
            "milestone_mismatch",
            "M10 C01-C20 source milestone must be M10",
            actual=source.get("milestone"),
        ))
    if source.get("conformance_pass") is not True:
        failures.append(_failure(
            "conformance_not_passed",
            "M10 C01-C20 source does not report conformance_pass=true",
        ))
    if not isinstance(source.get("generated_at"), str) or not source["generated_at"]:
        failures.append(_failure(
            "missing_generated_at", "M10 C01-C20 source has no generated_at"
        ))
    bound_files = source.get("bound_files")
    if not isinstance(bound_files, dict) or not bound_files:
        failures.append(_failure(
            "missing_bound_files", "M10 C01-C20 source has no bound file vector"
        ))
        bound_files = {}

    normalized = {
        "schema": "m10.c01-c20-conformance.v1",
        "schema_version": 1,
        "generated_at": source.get("generated_at", ""),
        "status": "conformant" if not failures else "blocked",
        "effective_status": "conformant" if not failures else "blocked",
        "owner": f"M10/{source.get('step', 'unknown')}",
        "version_vector": {
            "source_sha256": source_digest,
            **{str(key): str(value) for key, value in bound_files.items()},
        },
        "source_path": M10_C01_C20_PATH.as_posix(),
    }
    return normalized, failures


def _normalize_f01_f17(
    source: dict[str, Any], source_digest: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    if source.get("schema_version") != 1:
        failures.append(_failure(
            "schema_mismatch",
            "F01-F17 source must use schema_version 1",
            actual=source.get("schema_version"),
        ))
    if source.get("status") != "reconciled":
        failures.append(_failure(
            "ineffective_status",
            "F01-F17 source status must be reconciled",
            actual=source.get("status"),
        ))
    scenarios = source.get("scenarios")
    actual_ids = {
        row.get("id")
        for row in scenarios
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    } if isinstance(scenarios, list) else set()
    expected_ids = {f"F{index:02d}" for index in range(1, 18)}
    if actual_ids != expected_ids or len(scenarios or []) != 17:
        failures.append(_failure(
            "scenario_coverage_mismatch",
            "F01-F17 source must contain each of F01 through F17 exactly once",
            missing=sorted(expected_ids - actual_ids),
            unexpected=sorted(actual_ids - expected_ids),
        ))
    if not isinstance(source.get("reconciliation"), dict):
        failures.append(_failure(
            "missing_reconciliation",
            "F01-F17 source has no reconciliation record",
        ))

    normalized = {
        "schema": "m10.f01-f17-fault-matrix.v1",
        "schema_version": 1,
        "status": "reconciled" if not failures else "blocked",
        "owner": "M10/F01-F17",
        "version_vector": {"source_sha256": source_digest},
        "source_path": F01_F17_PATH.as_posix(),
        "scenarios": scenarios if isinstance(scenarios, list) else [],
    }
    return normalized, failures


def _normalize_m5(
    repo_root: Path,
    final_attestation: dict[str, Any],
    final_digest: str,
    completion_manifest: dict[str, Any],
    completion_digest: str,
    proof_map: dict[str, Any],
    proof_digest: str,
    migration_matrix: dict[str, Any],
    matrix_digest: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    if final_attestation.get("schema") != "m5.final-attestation.v2":
        failures.append(_failure(
            "schema_mismatch",
            "M5 final attestation must use m5.final-attestation.v2",
            actual=final_attestation.get("schema"),
        ))
    if final_attestation.get("retirement_status") != "completed":
        failures.append(_failure(
            "ineffective_status",
            "M5 final attestation retirement_status must be completed",
            actual=final_attestation.get("retirement_status"),
        ))
    if final_attestation.get("unresolved_evidence") != []:
        failures.append(_failure(
            "unresolved_evidence",
            "M5 final attestation contains unresolved evidence",
        ))
    if completion_manifest.get("schema") != "arnold.megaplan.chain_completion_manifest.v1":
        failures.append(_failure(
            "schema_mismatch",
            "M5 completion manifest has an unexpected schema",
            actual=completion_manifest.get("schema"),
        ))
    if proof_map.get("schema") != "arnold.megaplan.proof_map.v1":
        failures.append(_failure(
            "schema_mismatch",
            "M5 proof map has an unexpected schema",
            actual=proof_map.get("schema"),
        ))
    if M5_FINAL_ATTESTATION_PATH.as_posix() not in proof_map.get("m5-handoff", []):
        failures.append(_failure(
            "attestation_not_in_proof_map",
            "M5 proof map does not reference the final attestation",
        ))
    canonical_digest = final_attestation.get("gates", {}).get(
        "canonical_manifest_sha256"
    )
    if canonical_digest != completion_digest.removeprefix("sha256:"):
        failures.append(_failure(
            "completion_manifest_digest_mismatch",
            "M5 final attestation does not bind the handoff completion manifest",
            expected=canonical_digest,
            actual=completion_digest,
        ))
    bound_artifacts = final_attestation.get("bound_artifacts")
    if not isinstance(bound_artifacts, dict) or not bound_artifacts:
        failures.append(_failure(
            "bound_artifacts_missing",
            "M5 final attestation has no bound artifact map",
        ))
    else:
        for relative_path, binding in bound_artifacts.items():
            expected = binding.get("sha256") if isinstance(binding, dict) else None
            try:
                actual = _sha256_bytes((repo_root / relative_path).read_bytes())
            except OSError:
                failures.append(_failure(
                    "bound_artifact_missing",
                    "M5 bound artifact is not readable",
                    path=relative_path,
                ))
                continue
            if actual.removeprefix("sha256:") != expected:
                failures.append(_failure(
                    "bound_artifact_digest_mismatch",
                    "M5 bound artifact digest does not match final attestation",
                    path=relative_path,
                    expected=expected,
                    actual=actual,
                ))
    repository_head = final_attestation.get("repository_subject_head")
    if not isinstance(repository_head, str) or len(repository_head) != 40:
        failures.append(_failure(
            "missing_repository_subject",
            "M5 final attestation has no full repository_subject_head",
        ))

    status = "done" if not failures else "blocked"
    normalized = {
        "schema": "m5.evidence.v1",
        "schema_version": 1,
        "generated_at": final_attestation.get("generated_at", ""),
        "status": status,
        "effective_status": status,
        "owner": "M5/run-authority-receipt-reconciliation",
        "version_vector": {
            "final_attestation_sha256": final_digest,
            "completion_manifest_sha256": completion_digest,
            "proof_map_sha256": proof_digest,
            "migration_matrix_sha256": matrix_digest,
            "repository_subject_head": repository_head or "",
        },
        "source_path": M5_FINAL_ATTESTATION_PATH.as_posix(),
    }
    return normalized, failures


def _normalize_a7(
    inventory: dict[str, Any], source_digest: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    if inventory.get("schema") == "m11.a7-legacy-bypass-inventory.v1":
        if inventory.get("status") != "satisfied":
            failures.append(_failure(
                "a7_inventory_incomplete",
                "A7 joined inventory status is not satisfied",
                actual=inventory.get("status"),
            ))
        static_ids = inventory.get("declared_callsite_ids")
        runtime_ids = inventory.get("runtime_callsite_ids")
        if (
            inventory.get("static_call_site_set_equality") is not True
            or not isinstance(static_ids, list)
            or not static_ids
            or static_ids != runtime_ids
        ):
            failures.append(_failure(
                "a7_static_runtime_mismatch",
                "A7 static and captured runtime call-site sets do not agree exactly",
            ))
        if not isinstance(inventory.get("source_bindings"), dict) or not inventory.get(
            "source_bindings"
        ):
            failures.append(_failure(
                "a7_source_registry_binding_missing",
                "A7 joined inventory does not bind source registries",
            ))
        if not isinstance(inventory.get("legacy_candidates"), list) or not inventory.get(
            "legacy_candidates"
        ):
            failures.append(_failure(
                "a7_inventory_empty",
                "A7 joined inventory has no legacy candidates",
            ))
        status = "done" if not failures else "blocked"
        return {
            "schema": "a7.evidence.v1",
            "schema_version": 1,
            "generated_at": "deterministic-content-addressed",
            "status": status,
            "effective_status": status,
            "owner": "M11/A7-legacy-bypass-inventory",
            "version_vector": {
                "inventory_sha256": source_digest,
                "inventory_content_sha256": inventory.get("content_sha256", ""),
            },
            "source_path": A7_INVENTORY_PATH.as_posix(),
        }, failures

    # No joined inventory yet.  Preserve the legacy prep result as diagnostic
    # context, but never treat a worker label as the A7 acceptance decision.
    findings = inventory.get("findings")
    a7_rows = [
        row for row in findings
        if isinstance(row, dict) and row.get("area") == "A7"
    ] if isinstance(findings, list) else []
    if len(a7_rows) != 1:
        failures.append(_failure(
            "a7_inventory_missing",
            "Expected exactly one A7 research result",
            count=len(a7_rows),
        ))
        a7 = {}
    else:
        a7 = a7_rows[0]
    if a7.get("status") != "complete":
        failures.append(_failure(
            "a7_inventory_incomplete",
            "A7 legacy-bypass inventory is not complete",
            actual=a7.get("status"),
            source_error=a7.get("error", ""),
        ))
    if not isinstance(a7.get("findings"), list) or not a7.get("findings"):
        failures.append(_failure(
            "a7_inventory_empty",
            "A7 legacy-bypass inventory has no findings",
        ))
    if not isinstance(a7.get("files"), list) or not a7.get("files"):
        failures.append(_failure(
            "a7_source_inventory_empty",
            "A7 legacy-bypass inventory has no source files",
        ))
    if a7.get("static_call_site_set_equality") is not True:
        failures.append(_failure(
            "a7_static_set_equality_missing",
            "A7 inventory has no passing static call-site set-equality proof",
        ))
    if not isinstance(a7.get("runtime_trace_coverage"), list) or not a7.get(
        "runtime_trace_coverage"
    ):
        failures.append(_failure(
            "a7_runtime_trace_coverage_missing",
            "A7 inventory has no captured runtime-trace coverage",
        ))
    if not isinstance(a7.get("source_registry_digests"), dict) or not a7.get(
        "source_registry_digests"
    ):
        failures.append(_failure(
            "a7_source_registry_binding_missing",
            "A7 inventory does not bind its source registries",
        ))

    status = "done" if not failures else "blocked"
    normalized = {
        "schema": "a7.evidence.v1",
        "schema_version": 1,
        # research.json has no timestamp; the wrapper binds its exact bytes.
        "generated_at": "not-present-in-source-schema",
        "status": status,
        "effective_status": status,
        "owner": "M11/A7-legacy-bypass-inventory",
        "version_vector": {"research_sha256": source_digest},
        "source_path": A7_RESEARCH_PATH.as_posix(),
    }
    return normalized, failures


def derive_predecessors(repo_root: Path, *, owner: str = "T7") -> dict[str, DerivedPredecessor]:
    c_source, c_digest = _load_source(repo_root, M10_C01_C20_PATH)
    f_source, f_digest = _load_source(repo_root, F01_F17_PATH)
    m5_source, m5_digest = _load_source(repo_root, M5_FINAL_ATTESTATION_PATH)
    completion_source, completion_digest = _load_source(
        repo_root, M5_COMPLETION_MANIFEST_PATH
    )
    proof_source, proof_digest = _load_source(repo_root, M5_PROOF_MAP_PATH)
    matrix_source, matrix_digest = _load_source(repo_root, M5_MIGRATION_MATRIX_PATH)
    a7_source, a7_digest = _load_source(repo_root, A7_INVENTORY_PATH)
    a7_research, a7_research_digest = _load_source(repo_root, A7_RESEARCH_PATH)
    a7_support = [
        (path, *_load_source(repo_root, path)) for path in A7_SOURCE_PATHS
    ]

    c_data, c_failures = _normalize_m10_c01_c20(c_source, c_digest)
    f_data, f_failures = _normalize_f01_f17(f_source, f_digest)
    m5_data, m5_failures = _normalize_m5(
        repo_root,
        m5_source,
        m5_digest,
        completion_source,
        completion_digest,
        proof_source,
        proof_digest,
        matrix_source,
        matrix_digest,
    )
    a7_data, a7_failures = _normalize_a7(a7_source, a7_digest)

    c_result = validate_m10_c01_c20_evidence(
        c_data, owner=owner, source_path=M10_C01_C20_PATH.as_posix()
    )
    f_result = validate_f01_f17_evidence(
        f_data, owner=owner, source_path=F01_F17_PATH.as_posix()
    )
    m5_result = validate_m5_evidence(
        m5_data, owner=owner, source_path=M5_FINAL_ATTESTATION_PATH.as_posix()
    )
    a7_result = validate_a7_evidence(
        a7_data,
        owner=owner,
        source_path=(
            A7_INVENTORY_PATH.as_posix()
            if a7_digest
            else A7_RESEARCH_PATH.as_posix()
        ),
    )

    return {
        "m10_c01_c20": DerivedPredecessor(
            family="m10_c01_c20",
            source_artifacts=[_source_ref(M10_C01_C20_PATH, c_digest)],
            adapter_results=[c_result],
            derivation_failures=c_failures,
            next_action=(
                "" if not c_failures
                else "Regenerate the M10 C01-C20 conformance artifact from its native validator."
            ),
        ),
        "m10_handoff": DerivedPredecessor(
            family="m10_handoff",
            source_artifacts=[
                _source_ref(M10_C01_C20_PATH, c_digest),
                _source_ref(F01_F17_PATH, f_digest),
            ],
            adapter_results=[c_result, f_result],
            derivation_failures=[*c_failures, *f_failures],
            next_action=(
                "" if not [*c_failures, *f_failures]
                else "Regenerate the M10 conformance and fault-matrix sources from their native validators."
            ),
        ),
        "m5": DerivedPredecessor(
            family="m5",
            source_artifacts=[
                _source_ref(M5_FINAL_ATTESTATION_PATH, m5_digest),
                _source_ref(M5_COMPLETION_MANIFEST_PATH, completion_digest),
                _source_ref(M5_PROOF_MAP_PATH, proof_digest),
                _source_ref(M5_MIGRATION_MATRIX_PATH, matrix_digest),
            ],
            adapter_results=[m5_result],
            derivation_failures=m5_failures,
            observations=[{
                "kind": "m11_residual_matrix_status",
                "path": M5_MIGRATION_MATRIX_PATH.as_posix(),
                "actual": matrix_source.get("prerequisite_status"),
                "detail": (
                    "This is M11 closure work, not a reason to invalidate the "
                    "authenticated historical M5 handoff."
                ),
            }],
            next_action=(
                "M11 must resolve the currently INCOHERENT residual matrix rows "
                "and regenerate evidence/migration-matrix-reconciled.json; this "
                "does not rewrite or invalidate the authenticated M5 handoff."
            ),
        ),
        "a7": DerivedPredecessor(
            family="a7",
            source_artifacts=[
                *(
                    [_source_ref(A7_INVENTORY_PATH, a7_digest)]
                    if a7_digest
                    else []
                ),
                _source_ref(A7_RESEARCH_PATH, a7_research_digest),
                *[
                    _source_ref(path, digest)
                    for path, _data, digest in a7_support
                ],
            ],
            adapter_results=[a7_result],
            derivation_failures=a7_failures,
            observations=[{
                "kind": "a7_research_worker_error",
                "path": A7_RESEARCH_PATH.as_posix(),
                "detail": next(
                    (
                        row.get("error", "")
                        for row in a7_research.get("findings", [])
                        if isinstance(row, dict) and row.get("area") == "A7"
                    ),
                    "",
                ),
            }],
            next_action=(
                ""
                if not a7_failures
                else (
                    "Generate one A7 inventory that joins the existing reader, "
                    "writer, deletion, historical-adapter, and migration registries "
                    "to exact static call-site equality and captured runtime traces. "
                    "The failed research worker may be rerun, but its status alone "
                    "is neither acceptance nor rejection evidence."
                )
            ),
        ),
    }


def validate_wrapper(
    wrapper: dict[str, Any], *, repo_root: Path | None = None
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if wrapper.get("schema") != WRAPPER_SCHEMA:
        failures.append(_failure("wrapper_schema_mismatch", "Unknown wrapper schema"))
    if wrapper.get("status") not in {SATISFIED, BLOCKED}:
        failures.append(_failure("wrapper_status_unknown", "Unknown wrapper status"))
    claimed_digest = wrapper.get("content_sha256")
    digest_payload = {
        key: value for key, value in wrapper.items() if key != "content_sha256"
    }
    actual_digest = _sha256_bytes(_canonical_bytes(digest_payload))
    if claimed_digest != actual_digest:
        failures.append(_failure(
            "wrapper_digest_mismatch",
            "Wrapper content digest does not match its payload",
            expected=actual_digest,
            actual=claimed_digest,
        ))
    results = wrapper.get("adapter_results")
    if not isinstance(results, list) or not results:
        failures.append(_failure("adapter_results_missing", "Wrapper has no adapter results"))
    elif wrapper.get("status") == SATISFIED and any(
        result.get("passed") is not True for result in results
        if isinstance(result, dict)
    ):
        failures.append(_failure(
            "satisfied_wrapper_has_failed_adapter",
            "Satisfied wrapper contains a failed adapter",
        ))
    if wrapper.get("status") == SATISFIED and wrapper.get("failures"):
        failures.append(_failure(
            "satisfied_wrapper_has_failures",
            "Satisfied wrapper contains failures",
        ))
    sources = wrapper.get("source_artifacts")
    if not isinstance(sources, list) or not sources:
        failures.append(_failure(
            "source_artifacts_missing", "Wrapper has no source artifacts"
        ))
    elif repo_root is not None:
        for source in sources:
            if not isinstance(source, dict):
                failures.append(_failure(
                    "source_artifact_invalid", "Source artifact row is not an object"
                ))
                continue
            relative_path = source.get("path")
            expected_digest = source.get("sha256")
            if not isinstance(relative_path, str) or not relative_path:
                failures.append(_failure(
                    "source_path_missing", "Source artifact path is missing"
                ))
                continue
            try:
                actual_digest = _sha256_bytes((repo_root / relative_path).read_bytes())
            except OSError:
                failures.append(_failure(
                    "source_artifact_missing",
                    "Source artifact is not readable",
                    path=relative_path,
                ))
                continue
            if actual_digest != expected_digest:
                failures.append(_failure(
                    "source_digest_mismatch",
                    "Source artifact digest no longer matches the wrapper",
                    path=relative_path,
                    expected=expected_digest,
                    actual=actual_digest,
                ))
    return failures


def write_predecessor_wrappers(
    repo_root: Path, *, owner: str = "T7"
) -> dict[str, dict[str, Any]]:
    derived = derive_predecessors(repo_root, owner=owner)
    wrappers: dict[str, dict[str, Any]] = {}
    for family, item in derived.items():
        wrapper = item.wrapper()
        failures = validate_wrapper(wrapper, repo_root=repo_root)
        if failures:
            raise ValueError(f"{family}: invalid derived wrapper: {failures}")
        output_path = repo_root / WRAPPER_PATHS[family]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(wrapper, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        wrappers[family] = wrapper
    return wrappers


__all__ = [
    "A7_RESEARCH_PATH",
    "A7_INVENTORY_PATH",
    "BLOCKED",
    "DerivedPredecessor",
    "F01_F17_PATH",
    "M10_C01_C20_PATH",
    "M5_FINAL_ATTESTATION_PATH",
    "M5_MIGRATION_MATRIX_PATH",
    "SATISFIED",
    "WRAPPER_PATHS",
    "WRAPPER_SCHEMA",
    "derive_predecessors",
    "validate_wrapper",
    "write_predecessor_wrappers",
]
