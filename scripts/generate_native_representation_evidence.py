#!/usr/bin/env python3
"""Generate source and boundary evidence for Megaplan native representation rows."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import yaml


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from arnold.conformance.checks import check_generic_arnold_megaplan_coupling
from arnold.conformance.authoring_terms import FORBIDDEN_MEGAPLAN_IMPORT_PREFIXES
from arnold.conformance.deleted_surfaces import DELETED_IMPORT_MODULES, DELETED_SOURCE_PATHS
from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.boundary_evidence import AuthorityRecord, BoundaryOutcome, BoundaryReceipt
from arnold.workflow.handler_semantics import (
    LocalRouteFunctionDetector,
    M6_FANOUT_DISPATCH_CALLS,
    M6_FORBIDDEN_ROUTING_CALLS,
    M6_RETAINED_HANDLERS,
    StateMutationVisitor,
    check_handler_body_purity,
    collect_call_names,
    find_function,
    handler_source,
    parse_source,
)
from arnold_pipelines.megaplan.orchestration.override_authority import (
    build_override_authority_record,
)
from arnold_pipelines.megaplan.semantic_health import inspect_semantic_health
from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline, build_pipeline
from arnold_pipelines.megaplan.workflows.package_fingerprints import (
    canonical_workflow_fingerprints,
)
from arnold_pipelines.megaplan.workflows.boundary_contracts import BOUNDARY_CONTRACTS_BY_ID


DEFAULT_CONFORMANCE = "docs/arnold/megaplan-native-representation-conformance.yaml"
DEFAULT_TRACEABILITY = "docs/arnold/megaplan-native-representation-traceability.yaml"
DEFAULT_OUTPUT = "docs/arnold/megaplan-native-representation-evidence.yaml"
DEFAULT_BOUNDARY_FIXTURE_ROOT = "docs/arnold/megaplan-native-representation-boundary-fixtures"
DEFAULT_SCENARIOS = "docs/arnold/megaplan-native-representation-scenarios.yaml"
DEFAULT_CANONICAL_SOURCE = "arnold_pipelines/megaplan/workflows/workflow.pypeline"
DEFAULT_WORKFLOW_MODULE = "arnold_pipelines/megaplan/workflows/workflow.py"
DEFAULT_SHADOW_TOPOLOGY_FIXTURE = "tests/arnold_pipelines/megaplan/fixtures/megaplan_m4_topology.yaml"
EVIDENCE_SCHEMA = "arnold.megaplan_native_representation.evidence_bundle.v1"
SOURCE_CHECKER = "scripts.generate_native_representation_evidence"
BOUNDARY_HEALTH_STATUS = "healthy"
SHADOW_TOPOLOGY_ROW_ID = "shadow-topology"
HANDLER_PURITY_ROW_ID = "handler-purity-audit"
SOURCE_PATH_RECONCILIATION_ROW_ID = "source-path-reconciliation"
TOPOLOGY_REGENERATION_PROOF = "tests/arnold_pipelines/megaplan/test_compositional_workflow.py"
HANDLER_PURITY_PROOF = "tests/arnold_pipelines/megaplan/test_semantics_carrier.py"
COMPATIBILITY_QUARANTINE_PROOF = "tests/arnold/conformance/test_megaplan_coupling_gate.py"
DEAD_DELETE_MUTATION_PROOF = "tests/arnold/conformance/test_deleted_surfaces.py"
SPLIT_OUTCOME_CATEGORIES = (
    "prep",
    "gate",
    "cap",
    "tiebreaker",
    "execute",
    "approval",
    "review",
    "no_review",
    "override",
)

APPROVED_CARRIER_NAMES = {
    "arnold_pipelines/megaplan/workflows/workflow.pypeline": "canonical_workflow_source",
    "arnold_pipelines/megaplan/workflows/planning.py": "native_planning_surface",
    "arnold_pipelines/megaplan/workflows/boundary_contracts.py": "boundary_contract_registry",
    "arnold_pipelines/megaplan/workflows/override_matrix.py": "override_action_matrix",
    "arnold_pipelines/megaplan/workflows/events.py": "workflow_event_projection",
    "arnold_pipelines/megaplan/handlers/plan.py": "plan_phase_body",
    "arnold_pipelines/megaplan/handlers/_tiebreaker_impl.py": "tiebreaker_phase_body",
    "docs/arnold/native-platform.md": "native_platform_policy",
    "docs/arnold/operations.md": "operations_policy",
    "docs/arnold/package-authoring-contract.md": "package_authoring_contract",
}

UNSUPPORTED_DIRECT_BOUNDARY_FIXTURES = {
    "review_child_outputs",
    "review_reducer_promotion",
    "review_rework_effects",
}

ROW_SUPPORT_FIXTURE_IDS = {
    "prep-clarification-gate": ("prep_to_plan",),
    "plan-artifact-version-metadata": ("finalize_artifacts",),
    "critique-evaluator-retry": ("execute_blocked_anchor",),
    "critique-parallel-lenses": ("execute_aggregate_promotion",),
    "critique-gate-revise-loop": ("gate_to_revise", "revise_to_critique"),
    "gate-preflight-normalization": ("execute_blocked_anchor",),
    "gate-signal-reprompt": ("execute_resume_anchor",),
    "gate-flag-debt-fallback": ("execute_partial_failure", "finalize_artifacts"),
    "tiebreaker-subworkflow": (
        "tiebreaker_researcher_to_challenger",
        "tiebreaker_challenger_to_synthesis",
        "tiebreaker_synthesis_to_decision",
        "tiebreaker_decision_to_parent",
        "parent_rejoin_promotion",
        "replan_authority",
    ),
    "human-decision-suspension": (
        "execute_approval",
        "review_human_verification",
        "override_suspension_authority",
        "override_human_gate_authority",
    ),
    "finalize-fallback-routes": ("finalize_fallback", "final_projection"),
    "execute-dependency-batches": (
        "execute_batch_checkpoint",
        "execute_partial_failure",
        "execute_blocked_anchor",
        "execute_resume_anchor",
        "execute_aggregate_promotion",
    ),
    "execute-approval-gates": (
        "execute_approval",
        "override_human_gate_authority",
        "execute_no_review_terminal",
    ),
    "execute-review-rework-loop": ("execute_partial_failure", "execute_resume_anchor"),
    "review-parallel-fanin": ("execute_aggregate_promotion",),
    "review-retry-cap-outcomes": (
        "review_cap_authority",
        "review_human_verification",
        "execute_partial_failure",
    ),
    "override-action-surface": (
        "override_abort_authority",
        "override_force_proceed_authority",
        "override_replan_authority",
        "override_recover_blocked_authority",
        "override_resume_clarify_authority",
        "override_adopt_execution_authority",
        "override_suspension_authority",
        "override_human_gate_authority",
    ),
    "timeout-deadline-policy": (
        "review_cap_authority",
        "execute_blocked_anchor",
        "execute_resume_anchor",
    ),
    "model-routing-policy": ("execute_resume_anchor",),
    "autodrive-event-liveness": ("execute_approval", "override_recover_blocked_authority"),
    "path-addressed-checkpoints": (
        "execute_resume_anchor",
        "tiebreaker_researcher_to_challenger",
        "review_human_verification",
        "override_recover_blocked_authority",
    ),
}

ACTIVE_OVERRIDE_FIXTURES = {
    "override_abort_authority",
    "override_force_proceed_authority",
    "override_replan_authority",
    "override_recover_blocked_authority",
    "override_resume_clarify_authority",
    "override_adopt_execution_authority",
}

INACTIVE_OVERRIDE_FIXTURES = {
    "override_suspension_authority",
    "override_human_gate_authority",
}


@dataclass(frozen=True)
class ForbiddenAuthorityScan:
    scan_id: str
    path: str
    rationale: str
    patterns: tuple[str, ...]
    path_conflicts_with_authority: bool = True


@dataclass(frozen=True)
class GeneratedBoundaryFixture:
    fixture_id: str
    boundary_id: str
    capability_effects: frozenset[str]
    plan_dir: Path
    receipt_path: Path
    phase_result_path: Path
    semantic_health_path: Path
    manifest_path: Path
    scoped_findings: tuple[dict[str, Any], ...]
    scoped_error_count: int
    scoped_warning_count: int
    authority_record_count: int
    reducer_promotion: bool
    external_effect_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]


FORBIDDEN_AUTHORITY_SCANS = (
    ForbiddenAuthorityScan(
        scan_id="components-authority",
        path="arnold_pipelines/megaplan/workflows/components.py",
        rationale="Compatibility component metadata cannot satisfy implemented-row authority.",
        patterns=("handler_ref", "route_bindings", "compatibility_quarantine"),
    ),
    ForbiddenAuthorityScan(
        scan_id="manifest-route-bindings",
        path="arnold_pipelines/megaplan/workflows/planning.py",
        rationale="Manifest/declared route bindings are projections and cannot replace source-authoritative rows.",
        patterns=("declared_step_route_bindings", "lowered_route_bindings_by_step"),
        path_conflicts_with_authority=False,
    ),
    ForbiddenAuthorityScan(
        scan_id="auto-next-step-derivation",
        path="arnold_pipelines/megaplan/auto.py",
        rationale="Auto-driver next-step derivation is operational control flow, not semantic authority.",
        patterns=("_required_state_for_control_action", "_command_for_auto_target", "next_step"),
    ),
    ForbiddenAuthorityScan(
        scan_id="cli-dispatch",
        path="arnold/cli/workflow.py",
        rationale="CLI command dispatch is an invocation surface and cannot satisfy row evidence.",
        patterns=("def _cmd_", "subparsers", "build_pipeline"),
    ),
    ForbiddenAuthorityScan(
        scan_id="pipeline-projection",
        path="arnold_pipelines/megaplan/pipeline.py",
        rationale="Projected compatibility shells cannot satisfy native source authority.",
        patterns=("build_compatibility_shell", "build_and_compile_pipeline"),
    ),
    ForbiddenAuthorityScan(
        scan_id="workflow-shim",
        path="arnold_pipelines/megaplan/workflows/workflow.py",
        rationale="The workflow.py compatibility shim cannot satisfy native source authority.",
        patterns=("canonical_source_path", "build_pipeline", "Compatibility glue"),
    ),
)

FORBIDDEN_AUTHORITY_PATHS = {
    scan.path for scan in FORBIDDEN_AUTHORITY_SCANS if scan.path_conflicts_with_authority
}


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _line_count(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    return max(1, text.count("\n") + (0 if text.endswith("\n") else 1))


def _stable_json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _stable_payload_sha256(payload: Any) -> str:
    return f"sha256:{hashlib.sha256(_stable_json_dump(payload).encode('utf-8')).hexdigest()}"


def _relative_path(path: Path, *, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json_dump(payload), encoding="utf-8")


def _write_artifact(path: Path, *, fixture_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        _write_json(path, {"fixture_id": fixture_id, "artifact": path.name})
        return
    if path.suffix == ".md":
        path.write_text(f"# {fixture_id} {path.name}\n", encoding="utf-8")
        return
    path.write_text(f"{fixture_id}:{path.name}\n", encoding="utf-8")


def _history_prefix(expected_history_entry: str | None, phase: str | None) -> str:
    if expected_history_entry:
        return expected_history_entry.split("_")[0]
    if phase:
        return phase
    return "boundary"


def _fixture_current_state(boundary_id: str) -> str:
    if boundary_id == "prep_to_plan":
        return "prepped"
    if boundary_id == "plan_to_critique":
        return "planned"
    if boundary_id == "critique_to_gate":
        return "critiqued"
    if boundary_id == "gate_to_revise":
        return "gated"
    if boundary_id == "revise_to_critique":
        return "planned"
    if boundary_id == "execute_no_review_terminal":
        return "done"
    if boundary_id == "review_human_verification":
        return "awaiting_human_verify"
    if boundary_id.startswith("review_"):
        return "executed"
    if boundary_id in {"finalize_fallback", "final_projection"}:
        return "critiqued"
    if boundary_id == "finalize_artifacts":
        return "gated"
    if boundary_id.startswith("override_"):
        return "critiqued"
    if boundary_id.startswith("execute_"):
        return "executed"
    if boundary_id.startswith("tiebreaker_") or boundary_id in {
        "replan_authority",
        "parent_rejoin_promotion",
    }:
        return "critiqued"
    return "initialized"


def _fixture_current_phase(boundary_id: str, contract: Any) -> str:
    current_phase = contract.expected_state_delta.get("current_phase")
    if isinstance(current_phase, str) and current_phase:
        return current_phase
    if boundary_id.startswith("review_"):
        return "review"
    if boundary_id.startswith("final") or boundary_id.startswith("finalize_"):
        return "finalize"
    if boundary_id.startswith("override_"):
        return "override"
    if contract.phase is not None:
        return contract.phase.value
    return "boundary"


def _fixture_state(boundary_id: str, contract: Any) -> dict[str, Any]:
    history_step = _history_prefix(
        contract.expected_history_entry,
        contract.phase.value if contract.phase is not None else None,
    )
    state = {
        "name": f"boundary-fixture-{boundary_id}",
        "current_state": _fixture_current_state(boundary_id),
        "current_phase": _fixture_current_phase(boundary_id, contract),
        "iteration": 1,
        "created_at": "2026-07-08T00:00:00Z",
        "config": {"project_dir": "/tmp/boundary-fixture"},
        "sessions": {},
        "plan_versions": [],
        "history": [{"step": history_step, "result": "success"}],
        "meta": {"current_invocation_id": f"inv-{boundary_id}"},
        "last_gate": {},
        "latest_failure": None,
    }
    for key, value in contract.expected_state_delta.items():
        state[key] = value
    if boundary_id in ACTIVE_OVERRIDE_FIXTURES:
        action = contract.details.get("authority_transition")
        state["meta"]["overrides"] = [{"action": action}] if isinstance(action, str) else []
    elif boundary_id == "review_human_verification":
        state["plan_versions"] = [{"file": "plan_v1.md", "version": 1}]
    return state


def _phase_result_payload(boundary_id: str, contract: Any) -> dict[str, Any]:
    phase = contract.phase.value if contract.phase is not None else None
    return {
        "schema": "megaplan.phase_result",
        "schema_version": 1,
        "phase_result_contract_version": 1,
        "phase": phase,
        "invocation_id": f"inv-{boundary_id}",
        "exit_kind": "success",
        "blocked_tasks": [],
        "deviations": [],
        "artifacts_written": [],
        "cli_provenance": {},
        "external_error": None,
    }


def _ensure_supporting_files(plan_dir: Path, *, boundary_id: str, contract: Any) -> None:
    for artifact in contract.required_artifacts:
        _write_artifact(plan_dir / artifact, fixture_id=boundary_id)

    for ref_name in (
        contract.details.get("required_evidence_refs"),
        contract.details.get("optional_evidence_refs"),
    ):
        if isinstance(ref_name, tuple):
            for ref in ref_name:
                if isinstance(ref, str) and ref:
                    _write_artifact(plan_dir / ref, fixture_id=boundary_id)

    if boundary_id == "review_human_verification":
        _write_artifact(plan_dir / "review.json", fixture_id=boundary_id)
        _write_json(
            plan_dir / "plan_v1.meta.json",
            {"success_criteria": [{"criterion": "Human signoff", "priority": "must"}]},
        )
        _write_json(
            plan_dir / "human_verifications.json",
            [{"criterion_idx": 0, "timestamp": "2026-07-08T00:00:00Z", "verdict": "pass"}],
        )
    elif boundary_id.startswith("review_"):
        _write_artifact(plan_dir / "review.json", fixture_id=boundary_id)

    if boundary_id in {"finalize_artifacts", "finalize_fallback", "final_projection"}:
        _write_artifact(plan_dir / "finalize.json", fixture_id=boundary_id)
    if boundary_id == "finalize_artifacts":
        _write_artifact(plan_dir / "contract.json", fixture_id=boundary_id)
        _write_artifact(plan_dir / "final.md", fixture_id=boundary_id)
    if boundary_id == "finalize_fallback":
        _write_artifact(plan_dir / "finalize_revise_feedback.json", fixture_id=boundary_id)

    if boundary_id in {
        "execute_batch_checkpoint",
        "execute_partial_failure",
        "execute_blocked_anchor",
        "execute_resume_anchor",
    }:
        effect_path = plan_dir / "effects" / f"{boundary_id}.json"
        _write_artifact(effect_path, fixture_id=boundary_id)
        _write_artifact(plan_dir / "execution_batch_1.json", fixture_id=boundary_id)
    if boundary_id == "execute_aggregate_promotion":
        _write_artifact(plan_dir / "execution_batch_1.json", fixture_id=boundary_id)
    if boundary_id in {"execute_approval", "execute_approval_denial", "override_human_gate_authority"}:
        _write_artifact(plan_dir / "approval_record.json", fixture_id=boundary_id)
    if boundary_id == "override_adopt_execution_authority":
        _write_artifact(plan_dir / "execution.json", fixture_id=boundary_id)
        _write_artifact(plan_dir / "final.md", fixture_id=boundary_id)
    if boundary_id == "override_suspension_authority":
        _write_json(
            plan_dir / "human_verifications.json",
            [{"criterion_idx": 0, "timestamp": "2026-07-08T00:00:00Z", "verdict": "pass"}],
        )


def _build_authority_records(boundary_id: str, *, plan_dir: Path, contract: Any) -> list[dict[str, Any]]:
    if boundary_id in ACTIVE_OVERRIDE_FIXTURES:
        transition = contract.details.get("authority_transition")
        if not isinstance(transition, str) or not transition:
            raise ValueError(f"override fixture {boundary_id!r} is missing authority_transition")
        record = build_override_authority_record(
            transition,
            plan_dir=plan_dir,
            actor="fixture-operator",
            role="reviewer",
            freshness_token=f"inv-{boundary_id}",
        )
        return [record.to_dict()]
    if boundary_id in INACTIVE_OVERRIDE_FIXTURES:
        record = AuthorityRecord(
            actor="fixture-operator",
            role="reviewer",
            decision=str(contract.details.get("authority_transition") or boundary_id),
            scope=str(contract.details.get("authority_scope") or boundary_id),
            evidence_refs=("state.json",),
            details={"activation_state": "inactive_receipted_fixture"},
        )
        return [record.to_dict()]
    if contract.authority_required:
        record = AuthorityRecord(actor="fixture-operator", role="reviewer", conditions=())
        return [record.to_dict()]
    return []


def _receipt_payload(boundary_id: str, *, plan_dir: Path, contract: Any, state: dict[str, Any]) -> dict[str, Any]:
    artifact_refs = tuple(contract.required_artifacts)
    state_observation = {"current_state": state["current_state"]}
    if boundary_id == "final_projection":
        state_observation["next_step"] = "revise"
    authority_records = _build_authority_records(boundary_id, plan_dir=plan_dir, contract=contract)
    receipt = BoundaryReceipt(
        boundary_id=boundary_id,
        workflow_id=contract.workflow_id,
        row_id=contract.row_id,
        invocation_id=f"inv-{boundary_id}",
        artifact_refs=artifact_refs,
        state_observation=state_observation,
        history_ref=contract.expected_history_entry,
        phase_result_ref="phase_result.json",
        outcome=BoundaryOutcome.SUCCEEDED,
    ).to_dict()
    if authority_records:
        receipt["authority_records"] = authority_records
    if boundary_id == "execute_aggregate_promotion":
        receipt["reducer_promotion"] = True
    if boundary_id in {
        "execute_batch_checkpoint",
        "execute_partial_failure",
        "execute_blocked_anchor",
        "execute_resume_anchor",
    }:
        receipt["child_trace_path"] = f"effects/{boundary_id}.json"
        receipt["batch_index"] = 1
    if boundary_id == "finalize_artifacts":
        finalize_path = plan_dir / "finalize.json"
        receipt["artifact_refs"] = ["contract.json", "final.md", "finalize.json"]
        receipt["details"] = {"artifact_hash": _sha256(finalize_path)}
    return receipt


def _fixture_capability_effects(boundary_id: str, *, contract: Any, receipt_payload: dict[str, Any]) -> frozenset[str]:
    effects = {"state_history", "receipt", "phase_result"}
    artifact_refs = receipt_payload.get("artifact_refs")
    if contract.required_artifacts or (isinstance(artifact_refs, list) and artifact_refs):
        effects.add("artifact")
    if receipt_payload.get("authority_records"):
        effects.add("authority")
    if receipt_payload.get("reducer_promotion") or contract.details.get("reducer_promotion"):
        effects.add("reducer")
    if receipt_payload.get("child_trace_path"):
        effects.add("external_effect")
    if boundary_id in {"finalize_fallback", "final_projection"}:
        effects.add("external_effect")
    return frozenset(effects)


def _build_boundary_fixture(
    *,
    boundary_id: str,
    repo_root: Path,
    fixture_root: Path,
) -> GeneratedBoundaryFixture:
    contract = BOUNDARY_CONTRACTS_BY_ID.get(boundary_id)
    if contract is None:
        raise ValueError(f"unknown boundary fixture id {boundary_id!r}")

    plan_dir = fixture_root / boundary_id
    plan_dir.mkdir(parents=True, exist_ok=True)

    state = _fixture_state(boundary_id, contract)
    _write_json(plan_dir / "state.json", state)
    _write_json(plan_dir / "phase_result.json", _phase_result_payload(boundary_id, contract))
    _ensure_supporting_files(plan_dir, boundary_id=boundary_id, contract=contract)

    receipt_payload = _receipt_payload(boundary_id, plan_dir=plan_dir, contract=contract, state=state)
    receipt_path = plan_dir / "boundary_receipts" / f"{boundary_id}.json"
    _write_json(receipt_path, receipt_payload)

    findings = inspect_semantic_health(plan_dir)
    scoped_findings = tuple(
        finding.to_dict() for finding in findings if finding.boundary_id == boundary_id
    )
    scoped_error_count = sum(
        1 for finding in scoped_findings if finding.get("severity") == "error"
    )
    scoped_warning_count = sum(
        1 for finding in scoped_findings if finding.get("severity") == "warning"
    )

    external_effect_refs: list[str] = []
    child_trace_path = receipt_payload.get("child_trace_path")
    if isinstance(child_trace_path, str) and child_trace_path:
        external_effect_refs.append(child_trace_path)
    projection_ref = contract.details.get("projection_ref")
    if isinstance(projection_ref, str) and projection_ref:
        external_effect_refs.append(projection_ref)
    branch_ref = contract.details.get("branch_ref")
    if isinstance(branch_ref, str) and branch_ref:
        external_effect_refs.append(branch_ref)

    semantic_health_payload = {
        "fixture_id": boundary_id,
        "boundary_id": boundary_id,
        "scope_boundary_ids": [boundary_id],
        "status": BOUNDARY_HEALTH_STATUS if scoped_error_count == 0 else "error",
        "scoped_error_count": scoped_error_count,
        "scoped_warning_count": scoped_warning_count,
        "scoped_findings": list(scoped_findings),
        "receipt_path": _relative_path(receipt_path, repo_root=repo_root),
        "phase_result_path": _relative_path(plan_dir / "phase_result.json", repo_root=repo_root),
        "authority_record_count": len(receipt_payload.get("authority_records", [])),
        "reducer_promotion": bool(receipt_payload.get("reducer_promotion")),
        "external_effect_refs": external_effect_refs,
    }
    semantic_health_path = plan_dir / "semantic_health.json"
    _write_json(semantic_health_path, semantic_health_payload)

    manifest_payload = {
        "fixture_id": boundary_id,
        "boundary_id": boundary_id,
        "capability_effects": sorted(
            _fixture_capability_effects(boundary_id, contract=contract, receipt_payload=receipt_payload)
        ),
        "plan_dir": _relative_path(plan_dir, repo_root=repo_root),
        "state_path": _relative_path(plan_dir / "state.json", repo_root=repo_root),
        "phase_result_path": _relative_path(plan_dir / "phase_result.json", repo_root=repo_root),
        "receipt_path": _relative_path(receipt_path, repo_root=repo_root),
        "semantic_health_path": _relative_path(semantic_health_path, repo_root=repo_root),
        "artifact_refs": receipt_payload.get("artifact_refs", []),
        "authority_records": receipt_payload.get("authority_records", []),
        "reducer_promotion": bool(receipt_payload.get("reducer_promotion")),
        "external_effect_refs": external_effect_refs,
        "path_hashes": {
            "state_path": _sha256(plan_dir / "state.json"),
            "phase_result_path": _sha256(plan_dir / "phase_result.json"),
            "receipt_path": _sha256(receipt_path),
            "semantic_health_path": _sha256(semantic_health_path),
        },
    }
    manifest_path = plan_dir / "manifest.json"
    _write_json(manifest_path, manifest_payload)

    return GeneratedBoundaryFixture(
        fixture_id=boundary_id,
        boundary_id=boundary_id,
        capability_effects=_fixture_capability_effects(
            boundary_id, contract=contract, receipt_payload=receipt_payload
        ),
        plan_dir=plan_dir,
        receipt_path=receipt_path,
        phase_result_path=plan_dir / "phase_result.json",
        semantic_health_path=semantic_health_path,
        manifest_path=manifest_path,
        scoped_findings=scoped_findings,
        scoped_error_count=scoped_error_count,
        scoped_warning_count=scoped_warning_count,
        authority_record_count=len(receipt_payload.get("authority_records", [])),
        reducer_promotion=bool(receipt_payload.get("reducer_promotion")),
        external_effect_refs=tuple(external_effect_refs),
        artifact_refs=tuple(receipt_payload.get("artifact_refs", [])),
    )


def _traceability_rows_by_id(traceability: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = traceability.get("rows")
    if not isinstance(rows, list):
        raise ValueError("traceability rows must be a list")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            row_id = row.get("id")
            if isinstance(row_id, str) and row_id:
                result[row_id] = row
    return result


def _string_list(value: Any, *, field: str, row_id: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"traceability row {row_id!r} {field} must be a non-empty list[str]")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"traceability row {row_id!r} {field} must contain non-empty strings")
        items.append(item.strip())
    return items


def _label_sequence(value: Any, *, field: str, record_id: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"scenario record {record_id!r} field {field!r} must be a non-empty list[str]")
    labels: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                f"scenario record {record_id!r} field {field!r} must contain non-empty strings"
            )
        labels.append(item.strip())
    return labels


def _normalize_repo_relative_path(raw: Any, *, field: str, record_id: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"scenario record {record_id!r} field {field!r} must be a non-empty path")
    text = raw.strip().replace("\\", "/")
    if text.startswith("/"):
        raise ValueError(f"scenario record {record_id!r} field {field!r} must be repo-relative")
    parts: list[str] = []
    for part in text.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError(f"scenario record {record_id!r} field {field!r} escapes repo root")
        parts.append(part)
    if not parts:
        raise ValueError(f"scenario record {record_id!r} field {field!r} must not resolve to repo root")
    return "/".join(parts)


def _resolve_supported_fixture_id(
    *,
    row_id: str,
    contract_id: str,
    required_effects: set[str],
    fixtures: dict[str, GeneratedBoundaryFixture],
) -> str:
    candidate_ids: list[str] = []
    if contract_id in fixtures and contract_id not in UNSUPPORTED_DIRECT_BOUNDARY_FIXTURES:
        candidate_ids.append(contract_id)
    candidate_ids.extend(ROW_SUPPORT_FIXTURE_IDS.get(row_id, ()))
    deduped = [candidate for index, candidate in enumerate(candidate_ids) if candidate_ids.index(candidate) == index]
    if not deduped:
        raise ValueError(f"row {row_id!r} contract {contract_id!r} has no supporting boundary fixture")
    for candidate in deduped:
        fixture = fixtures[candidate]
        if required_effects <= fixture.capability_effects:
            return candidate
    return deduped[0]


def _select_contract_path(*, row: dict[str, Any], contract_id: str) -> str:
    if contract_id in BOUNDARY_CONTRACTS_BY_ID:
        return "arnold_pipelines/megaplan/workflows/boundary_contracts.py"
    if contract_id.startswith("override_"):
        return "arnold_pipelines/megaplan/workflows/boundary_contracts.py"
    if contract_id.startswith("review_"):
        return "arnold_pipelines/megaplan/workflows/boundary_contracts.py"
    if contract_id.startswith("finalize_") or contract_id == "final_projection":
        return "arnold_pipelines/megaplan/workflows/boundary_contracts.py"
    if contract_id.startswith("execute_") or contract_id.startswith("tiebreaker_"):
        return "arnold_pipelines/megaplan/workflows/boundary_contracts.py"
    if contract_id == "replan_authority" or contract_id == "parent_rejoin_promotion":
        return "arnold_pipelines/megaplan/workflows/boundary_contracts.py"
    if contract_id.startswith("arnold_pipelines.megaplan.workflows.override_matrix:"):
        return "arnold_pipelines/megaplan/workflows/override_matrix.py"
    if contract_id.startswith("arnold_pipelines.megaplan.workflows.events:"):
        return "arnold_pipelines/megaplan/workflows/events.py"
    if contract_id in {"critique-fanout", "execute-batches", "review-fan-in", "SOURCE_CRITIQUE"}:
        return "arnold_pipelines/megaplan/workflows/workflow.pypeline"
    if contract_id == "megaplan:artifact-contract":
        return "docs/arnold/package-authoring-contract.md"
    if contract_id in {"megaplan:model-routing", "megaplan:robustness"}:
        return "docs/arnold/operations.md"
    carriers = row.get("carrier_evidence")
    if isinstance(carriers, list) and carriers:
        carrier = carriers[0]
        if isinstance(carrier, str) and carrier:
            return carrier
    raise ValueError(f"row {row['id']!r} cannot resolve contract path for {contract_id!r}")


def _build_source_checker_record(
    *,
    row: dict[str, Any],
    carrier_path: str,
    carrier_name: str,
    proof_artifact_path: str,
    repo_root: Path,
) -> dict[str, Any]:
    carrier_target = repo_root / carrier_path
    proof_target = repo_root / proof_artifact_path
    return {
        "row_id": row["id"],
        "semantic_carrier": row["semantic_carrier"],
        "kind": "source_checker",
        "checker": SOURCE_CHECKER,
        "carrier_path": carrier_path,
        "carrier_sha256": _sha256(carrier_target),
        "proof_artifact_path": proof_artifact_path,
        "proof_artifact_sha256": _sha256(proof_target),
        "source_span": {
            "path": carrier_path,
            "start_line": 1,
            "end_line": _line_count(carrier_target),
        },
        "policy_object": carrier_name,
        "carrier_name": carrier_name,
    }


def _select_proof_artifact(carrier_path: str, proof_artifacts: list[str]) -> str:
    if carrier_path in proof_artifacts:
        return carrier_path
    carrier_parts = Path(carrier_path).parts[:3]
    for artifact in proof_artifacts:
        if Path(artifact).parts[:3] == carrier_parts:
            return artifact
    return proof_artifacts[0]


def _build_fixture_hashes(rows: list[dict[str, Any]], *, repo_root: Path) -> list[dict[str, Any]]:
    references: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("status") != "implemented":
            continue
        for path in row["proof_artifacts"]:
            target = repo_root / path
            if not target.is_file():
                raise ValueError(f"implemented row {row['id']!r} proof artifact is missing: {path}")
            entry = references.setdefault(
                path,
                {
                    "path": path,
                    "sha256": _sha256(target),
                    "referenced_by_rows": [],
                },
            )
            entry["referenced_by_rows"].append(row["id"])
    return [
        {
            **entry,
            "referenced_by_rows": sorted(set(entry["referenced_by_rows"])),
        }
        for _, entry in sorted(references.items())
    ]


def _build_approved_carrier_inventory(
    rows: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("status") != "implemented":
            continue
        for carrier_path in row["carrier_evidence"]:
            target = repo_root / carrier_path
            if not target.is_file():
                raise ValueError(f"implemented row {row['id']!r} carrier file is missing: {carrier_path}")
            if carrier_path in FORBIDDEN_AUTHORITY_PATHS:
                raise ValueError(
                    f"implemented row {row['id']!r} uses forbidden authority carrier {carrier_path!r}"
                )
            carrier_name = APPROVED_CARRIER_NAMES.get(carrier_path)
            if carrier_name is None:
                raise ValueError(
                    f"implemented row {row['id']!r} uses unapproved carrier path {carrier_path!r}"
                )
            entry = inventory.setdefault(
                carrier_path,
                {
                    "path": carrier_path,
                    "carrier_name": carrier_name,
                    "sha256": _sha256(target),
                    "rows": [],
                },
            )
            entry["rows"].append(row["id"])
    return [
        {
            **entry,
            "rows": sorted(set(entry["rows"])),
        }
        for _, entry in sorted(inventory.items())
    ]


def _pattern_matches(path: Path, pattern: str) -> list[int]:
    return [
        line_number
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if pattern in line
    ]


def _build_quarantine_scans(
    rows: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[dict[str, Any]]:
    carrier_rows_by_path: dict[str, list[str]] = {}
    proof_rows_by_path: dict[str, list[str]] = {}
    for row in rows:
        if row.get("status") != "implemented":
            continue
        for carrier_path in row["carrier_evidence"]:
            carrier_rows_by_path.setdefault(carrier_path, []).append(row["id"])
        for proof_path in row["proof_artifacts"]:
            proof_rows_by_path.setdefault(proof_path, []).append(row["id"])

    records: list[dict[str, Any]] = []
    for scan in FORBIDDEN_AUTHORITY_SCANS:
        target = repo_root / scan.path
        if not target.is_file():
            raise ValueError(f"forbidden authority scan target is missing: {scan.path}")
        matches = [
            {"pattern": pattern, "line_numbers": _pattern_matches(target, pattern)}
            for pattern in scan.patterns
        ]
        records.append(
            {
                "scan_id": scan.scan_id,
                "path": scan.path,
                "sha256": _sha256(target),
                "authority_allowed": False,
                "classification": "quarantined_authority_surface",
                "rationale": scan.rationale,
                "cited_as_authority_rows": (
                    sorted(set(carrier_rows_by_path.get(scan.path, [])))
                    if scan.path_conflicts_with_authority
                    else []
                ),
                "rows_sharing_file": (
                    []
                    if scan.path_conflicts_with_authority
                    else sorted(set(carrier_rows_by_path.get(scan.path, [])))
                ),
                "cited_as_proof_artifact_rows": sorted(set(proof_rows_by_path.get(scan.path, []))),
                "matched_patterns": matches,
            }
        )
    return records


def _build_installed_package_fingerprints(
    rows: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[dict[str, Any]]:
    proof_artifact_path = "tests/arnold_pipelines/megaplan/test_installed_package_composition_smoke.py"
    workflow_source_path = repo_root / DEFAULT_CANONICAL_SOURCE
    workflow_module_path = repo_root / DEFAULT_WORKFLOW_MODULE
    proof_artifact = repo_root / proof_artifact_path
    fingerprints = canonical_workflow_fingerprints(
        workflow_source_path=workflow_source_path,
        workflow_module_path=workflow_module_path,
    )
    row_ids = sorted(
        row["id"]
        for row in rows
        if row.get("status") == "implemented"
        and proof_artifact_path in row.get("proof_artifacts", [])
        and DEFAULT_CANONICAL_SOURCE in row.get("carrier_evidence", [])
    )
    if not row_ids:
        return []
    return [
        {
            "suite_id": "installed_package_canonical_source",
            "row_ids": row_ids,
            "proof_artifact_path": proof_artifact_path,
            "proof_artifact_sha256": _sha256(proof_artifact),
            **fingerprints,
        }
    ]


def _implemented_row_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {
        row["id"]
        for row in rows
        if row.get("status") == "implemented" and isinstance(row.get("id"), str)
    }


def _build_topology_regeneration_checks(
    rows: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[dict[str, Any]]:
    if SHADOW_TOPOLOGY_ROW_ID not in _implemented_row_ids(rows):
        return []

    fixture_path = repo_root / DEFAULT_SHADOW_TOPOLOGY_FIXTURE
    proof_artifact_path = TOPOLOGY_REGENERATION_PROOF
    proof_artifact = repo_root / proof_artifact_path
    fixture = _load_yaml(fixture_path)
    manifest = compile_pipeline(build_pipeline())
    shell = build_and_compile_pipeline()

    topology = shell.native_program.routing_topology
    compiled_nodes = [node["name"] for node in topology["nodes"]]
    compiled_gate_targets = sorted(
        (route["label"], route["target"])
        for route in topology["routes"]
        if route["source"] == "gate"
    )
    compiled_tiebreaker_targets = sorted(
        (route["label"], route["target"])
        for route in topology["routes"]
        if route["source"] == "tiebreaker_decision"
    )
    fixture_gate_targets = sorted(
        (entry["label"], entry["target"]) for entry in fixture.get("gate_targets", [])
    )
    fixture_tiebreaker_targets = sorted(
        (entry["label"], entry["target"]) for entry in fixture.get("tiebreaker_targets", [])
    )

    return [
        {
            "check_id": "topology_regeneration",
            "row_ids": [SHADOW_TOPOLOGY_ROW_ID],
            "proof_artifact_path": proof_artifact_path,
            "proof_artifact_sha256": _sha256(proof_artifact),
            "fixture_path": DEFAULT_SHADOW_TOPOLOGY_FIXTURE,
            "fixture_sha256": _sha256(fixture_path),
            "canonical_source_path": DEFAULT_CANONICAL_SOURCE,
            "canonical_source_sha256": _sha256(repo_root / DEFAULT_CANONICAL_SOURCE),
            "compiled_manifest_hash": manifest.manifest_hash,
            "compiled_topology_hash": manifest.topology_hash,
            "fixture_manifest_hash": fixture.get("manifest_hash"),
            "fixture_topology_hash": fixture.get("topology_hash"),
            "compiled_node_count": len(compiled_nodes),
            "compiled_route_count": len(topology["routes"]),
            "matches_fixture": (
                manifest.manifest_hash == fixture.get("manifest_hash")
                and manifest.topology_hash == fixture.get("topology_hash")
                and compiled_nodes == fixture.get("nodes", [])
                and compiled_gate_targets == fixture_gate_targets
                and compiled_tiebreaker_targets == fixture_tiebreaker_targets
            ),
        }
    ]


def _build_handler_purity_checks(
    rows: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[dict[str, Any]]:
    if HANDLER_PURITY_ROW_ID not in _implemented_row_ids(rows):
        return []

    proof_artifact_path = HANDLER_PURITY_PROOF
    proof_artifact = repo_root / proof_artifact_path
    module_hashes: dict[str, str] = {}
    violations: dict[str, dict[str, Any]] = {}
    for handler_name in sorted(M6_RETAINED_HANDLERS):
        path, source = handler_source(handler_name)
        rel_path = _relative_path(path, repo_root=repo_root)
        module_hashes.setdefault(rel_path, _sha256(path))
        tree = parse_source(source)
        func = find_function(tree, handler_name)
        if func is None:
            violations[handler_name] = {"missing_handler_definition": True}
            continue

        mutation_visitor = StateMutationVisitor()
        mutation_visitor.visit(func)
        routing_calls = sorted(collect_call_names(func) & M6_FORBIDDEN_ROUTING_CALLS)
        fanout_calls = sorted(collect_call_names(func) & M6_FANOUT_DISPATCH_CALLS)
        local_detector = LocalRouteFunctionDetector(
            handler_name=handler_name,
            forbidden_routing=M6_FORBIDDEN_ROUTING_CALLS,
            fanout_calls=M6_FANOUT_DISPATCH_CALLS,
        )
        local_detector.visit(tree)
        if (
            mutation_visitor.violations
            or routing_calls
            or fanout_calls
            or local_detector.violations
        ):
            violation_entry: dict[str, Any] = {}
            if mutation_visitor.violations:
                violation_entry["state_mutation"] = list(mutation_visitor.violations)
            if routing_calls:
                violation_entry["routing_calls"] = routing_calls
            if fanout_calls:
                violation_entry["fanout_calls"] = fanout_calls
            if local_detector.violations:
                violation_entry["local_route_functions"] = {
                    name: sorted(details)
                    for name, details in sorted(local_detector.violations.items())
                }
            violations[handler_name] = violation_entry

    shared_path = repo_root / "arnold_pipelines/megaplan/handlers/shared.py"
    shared_module_hash = _sha256(shared_path)
    shared_source = shared_path.read_text(encoding="utf-8")
    shared_tree = ast.parse(shared_source, filename=str(shared_path))
    shared_violations: dict[str, list[str]] = {}
    for node in ast.iter_child_nodes(shared_tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        function_violations = sorted(
            check_handler_body_purity(
                node,
                forbidden_routing=M6_FORBIDDEN_ROUTING_CALLS,
                fanout_calls=M6_FANOUT_DISPATCH_CALLS,
            )
        )
        if function_violations:
            shared_violations[node.name] = function_violations
    module_hashes[_relative_path(shared_path, repo_root=repo_root)] = shared_module_hash

    return [
        {
            "check_id": "handler_purity_scan",
            "row_ids": [HANDLER_PURITY_ROW_ID],
            "proof_artifact_path": proof_artifact_path,
            "proof_artifact_sha256": _sha256(proof_artifact),
            "retained_handlers": sorted(M6_RETAINED_HANDLERS),
            "module_hashes": [
                {"path": path, "sha256": sha256}
                for path, sha256 in sorted(module_hashes.items())
            ],
            "violations": violations,
            "shared_module_violations": shared_violations,
            "passed": not violations and not shared_violations,
        }
    ]


def _present_deleted_source_paths(repo_root: Path) -> list[str]:
    return sorted(
        str((repo_root / path.rstrip("/")).relative_to(repo_root))
        for path in DELETED_SOURCE_PATHS
        if (repo_root / path.rstrip("/")).exists()
    )


def _present_deleted_import_modules(repo_root: Path) -> list[str]:
    present: list[str] = []
    for module_name in DELETED_IMPORT_MODULES:
        package_path = repo_root / Path(*module_name.split("."))
        module_path = repo_root / Path(*module_name.split(".")).with_suffix(".py")
        if package_path.is_dir() or module_path.exists():
            present.append(module_name)
    return present


def _deleted_product_import_violations(repo_root: Path) -> dict[str, tuple[str, ...]]:
    product_roots = (repo_root / "arnold_pipelines",)
    violations: dict[str, tuple[str, ...]] = {}

    for root in product_roots:
        for source in sorted(root.rglob("*.py")):
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            except SyntaxError:
                continue

            hits: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in FORBIDDEN_MEGAPLAN_IMPORT_PREFIXES:
                            if alias.name == prefix or alias.name.startswith(prefix + "."):
                                hits.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_MEGAPLAN_IMPORT_PREFIXES:
                        if node.module == prefix or node.module.startswith(prefix + "."):
                            hits.add(node.module)

            if hits:
                violations[str(source.relative_to(repo_root))] = tuple(sorted(hits))

    return violations


def _build_compatibility_quarantine_checks(
    rows: list[dict[str, Any]],
    *,
    quarantine_records: list[dict[str, Any]],
    repo_root: Path,
) -> list[dict[str, Any]]:
    if SOURCE_PATH_RECONCILIATION_ROW_ID not in _implemented_row_ids(rows):
        return []

    proof_artifact_path = COMPATIBILITY_QUARANTINE_PROOF
    proof_artifact = repo_root / proof_artifact_path
    coupling_gate = check_generic_arnold_megaplan_coupling(package_root=repo_root / "arnold")
    authority_conflicts = {
        record["scan_id"]: record["cited_as_authority_rows"]
        for record in quarantine_records
        if record["cited_as_authority_rows"]
    }

    return [
        {
            "check_id": "compatibility_quarantine",
            "row_ids": [SOURCE_PATH_RECONCILIATION_ROW_ID],
            "proof_artifact_path": proof_artifact_path,
            "proof_artifact_sha256": _sha256(proof_artifact),
            "quarantined_scan_ids": [record["scan_id"] for record in quarantine_records],
            "quarantine_record_count": len(quarantine_records),
            "authority_conflicts": authority_conflicts,
            "coupling_gate": {
                "passed": coupling_gate.passed,
                "check_id": coupling_gate.check_id,
                "message": coupling_gate.message,
                "details": coupling_gate.details,
            },
            "passed": coupling_gate.passed and not authority_conflicts,
        }
    ]


def _build_dead_delete_mutation_checks(
    rows: list[dict[str, Any]],
    *,
    repo_root: Path,
) -> list[dict[str, Any]]:
    if SOURCE_PATH_RECONCILIATION_ROW_ID not in _implemented_row_ids(rows):
        return []

    proof_artifact_path = DEAD_DELETE_MUTATION_PROOF
    proof_artifact = repo_root / proof_artifact_path
    present_deleted_paths = _present_deleted_source_paths(repo_root)
    present_deleted_modules = _present_deleted_import_modules(repo_root)
    product_import_violations = _deleted_product_import_violations(repo_root)
    return [
        {
            "check_id": "dead_delete_mutation",
            "row_ids": [SOURCE_PATH_RECONCILIATION_ROW_ID],
            "proof_artifact_path": proof_artifact_path,
            "proof_artifact_sha256": _sha256(proof_artifact),
            "deleted_source_path_count": len(DELETED_SOURCE_PATHS),
            "deleted_import_module_count": len(DELETED_IMPORT_MODULES),
            "present_deleted_paths": present_deleted_paths,
            "present_deleted_modules": present_deleted_modules,
            "product_import_violations": {
                path: list(imports)
                for path, imports in sorted(product_import_violations.items())
            },
            "passed": not present_deleted_paths
            and not present_deleted_modules
            and not product_import_violations,
        }
    ]


def _build_boundary_fixture_bundle(
    *,
    rows: list[dict[str, Any]],
    traceability: dict[str, Any],
    repo_root: Path,
    fixture_root: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    traceability_rows = _traceability_rows_by_id(traceability)
    required_fixture_ids = sorted(
        {
            fixture_id
            for row in rows
            if row.get("status") == "implemented" and row["id"] in ROW_SUPPORT_FIXTURE_IDS
            for fixture_id in ROW_SUPPORT_FIXTURE_IDS[row["id"]]
        }
        | {
            contract_id
            for row in rows
            if row.get("status") == "implemented"
            for contract_id in traceability_rows.get(row["id"], {}).get("boundary_contract_ids", [])
            if isinstance(contract_id, str)
            and contract_id in BOUNDARY_CONTRACTS_BY_ID
            and contract_id not in UNSUPPORTED_DIRECT_BOUNDARY_FIXTURES
        }
    )
    fixtures = {
        fixture_id: _build_boundary_fixture(
            boundary_id=fixture_id,
            repo_root=repo_root,
            fixture_root=fixture_root,
        )
        for fixture_id in required_fixture_ids
    }

    boundary_contract_records: list[dict[str, Any]] = []
    boundary_receipt_records: list[dict[str, Any]] = []
    boundary_semantic_health_records: list[dict[str, Any]] = []
    boundary_phase_result_records: list[dict[str, Any]] = []
    fixture_usage: dict[str, dict[str, set[str]]] = {
        fixture_id: {"row_ids": set(), "contract_ids": set()} for fixture_id in fixtures
    }

    for row in rows:
        if row.get("status") != "implemented":
            continue
        row_id = row["id"]
        trace_row = traceability_rows.get(row_id)
        if trace_row is None:
            continue
        boundary_effects_raw = trace_row.get("boundary_effects_required")
        if boundary_effects_raw is None:
            continue
        required_effects = set(
            _string_list(boundary_effects_raw, field="boundary_effects_required", row_id=row_id)
        )
        contract_ids = _string_list(
            trace_row.get("boundary_contract_ids"),
            field="boundary_contract_ids",
            row_id=row_id,
        )
        for contract_id in contract_ids:
            support_fixture_id = _resolve_supported_fixture_id(
                row_id=row_id,
                contract_id=contract_id,
                required_effects=required_effects,
                fixtures=fixtures,
            )
            fixture = fixtures[support_fixture_id]
            fixture_usage[support_fixture_id]["row_ids"].add(row_id)
            fixture_usage[support_fixture_id]["contract_ids"].add(contract_id)
            contract_path = _select_contract_path(row=row, contract_id=contract_id)
            boundary_contract_records.append(
                {
                    "row_id": row_id,
                    "contract_id": contract_id,
                    "covered_effects": sorted(required_effects),
                    "contract_path": contract_path,
                    "contract_sha256": _sha256(repo_root / contract_path),
                    "policy_object": contract_id,
                    "supporting_fixture_id": support_fixture_id,
                    "observed_boundary_id": fixture.boundary_id,
                    "fixture_manifest_path": _relative_path(fixture.manifest_path, repo_root=repo_root),
                    "fixture_manifest_sha256": _sha256(fixture.manifest_path),
                }
            )
            boundary_semantic_health_records.append(
                {
                    "row_id": row_id,
                    "contract_id": contract_id,
                    "covered_effects": sorted(required_effects),
                    "proof_artifact_path": _relative_path(
                        fixture.semantic_health_path,
                        repo_root=repo_root,
                    ),
                    "proof_artifact_sha256": _sha256(fixture.semantic_health_path),
                    "status": BOUNDARY_HEALTH_STATUS if fixture.scoped_error_count == 0 else "error",
                    "supporting_fixture_id": support_fixture_id,
                    "observed_boundary_id": fixture.boundary_id,
                    "scoped_error_count": fixture.scoped_error_count,
                    "scoped_warning_count": fixture.scoped_warning_count,
                    "fixture_manifest_path": _relative_path(fixture.manifest_path, repo_root=repo_root),
                    "fixture_manifest_sha256": _sha256(fixture.manifest_path),
                    "authority_records": fixture.authority_record_count,
                    "reducer_promotion": fixture.reducer_promotion,
                    "external_effect_refs": list(fixture.external_effect_refs),
                    "artifact_refs": list(fixture.artifact_refs),
                }
            )
            receipt_effects = required_effects & {"receipt", "authority"}
            if receipt_effects:
                boundary_receipt_records.append(
                    {
                        "row_id": row_id,
                        "contract_id": contract_id,
                        "covered_effects": sorted(receipt_effects),
                        "receipt_path": _relative_path(fixture.receipt_path, repo_root=repo_root),
                        "receipt_sha256": _sha256(fixture.receipt_path),
                        "supporting_fixture_id": support_fixture_id,
                        "observed_boundary_id": fixture.boundary_id,
                    }
                )
            phase_result_effects = required_effects & {"state_history", "phase_result"}
            if phase_result_effects:
                boundary_phase_result_records.append(
                    {
                        "row_id": row_id,
                        "contract_id": contract_id,
                        "covered_effects": sorted(phase_result_effects),
                        "phase_result_path": _relative_path(
                            fixture.phase_result_path,
                            repo_root=repo_root,
                        ),
                        "phase_result_sha256": _sha256(fixture.phase_result_path),
                        "supporting_fixture_id": support_fixture_id,
                        "observed_boundary_id": fixture.boundary_id,
                    }
                )

    boundary_fixture_hashes = [
        {
            "fixture_id": fixture_id,
            "boundary_id": fixture.boundary_id,
            "manifest_path": _relative_path(fixture.manifest_path, repo_root=repo_root),
            "manifest_sha256": _sha256(fixture.manifest_path),
            "semantic_health_path": _relative_path(fixture.semantic_health_path, repo_root=repo_root),
            "semantic_health_sha256": _sha256(fixture.semantic_health_path),
            "plan_dir": _relative_path(fixture.plan_dir, repo_root=repo_root),
            "capability_effects": sorted(fixture.capability_effects),
            "row_ids": sorted(fixture_usage[fixture_id]["row_ids"]),
            "contract_ids": sorted(fixture_usage[fixture_id]["contract_ids"]),
        }
        for fixture_id, fixture in sorted(fixtures.items())
        if fixture_usage[fixture_id]["row_ids"]
    ]
    return (
        boundary_contract_records,
        boundary_receipt_records,
        boundary_semantic_health_records,
        boundary_phase_result_records,
        boundary_fixture_hashes,
    )


def _build_split_outcome_hashes(
    *,
    repo_root: Path,
    traceability: dict[str, Any],
    scenarios_path: Path,
) -> list[dict[str, Any]]:
    scenarios_payload = _load_yaml(scenarios_path)
    if scenarios_payload.get("schema") != "arnold.megaplan_native_representation.scenarios.v1":
        raise ValueError("scenario manifest schema must be arnold.megaplan_native_representation.scenarios.v1")
    manifest_traceability = scenarios_payload.get("traceability")
    if manifest_traceability != DEFAULT_TRACEABILITY:
        raise ValueError("scenario manifest must reference the canonical traceability ledger")

    scenario_rows = scenarios_payload.get("scenarios")
    if not isinstance(scenario_rows, list) or not scenario_rows:
        raise ValueError("scenario manifest scenarios must be a non-empty list")
    scenarios_by_id: dict[str, dict[str, Any]] = {}
    for scenario in scenario_rows:
        if not isinstance(scenario, dict):
            raise ValueError("scenario manifest scenarios entries must be mappings")
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ValueError("scenario manifest scenario ids must be non-empty strings")
        rows = scenario.get("rows")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"scenario {scenario_id!r} must declare non-empty rows")
        scenarios_by_id[scenario_id.strip()] = scenario

    manifest_categories = _label_sequence(
        scenarios_payload.get("split_outcome_categories"),
        field="split_outcome_categories",
        record_id="<manifest>",
    )
    expected_categories = set(SPLIT_OUTCOME_CATEGORIES)
    if set(manifest_categories) != expected_categories:
        raise ValueError(
            "scenario manifest split_outcome_categories must exactly match the required category set"
        )
    refresh_rule = scenarios_payload.get("split_outcome_refresh_rule")
    if not isinstance(refresh_rule, str) or not refresh_rule.strip():
        raise ValueError("scenario manifest split_outcome_refresh_rule must be a non-empty string")
    authority_rule = scenarios_payload.get("split_outcome_authority_rule")
    if not isinstance(authority_rule, str) or not authority_rule.strip():
        raise ValueError("scenario manifest split_outcome_authority_rule must be a non-empty string")

    split_records = scenarios_payload.get("split_outcome_records")
    if not isinstance(split_records, list) or not split_records:
        raise ValueError("scenario manifest split_outcome_records must be a non-empty list")

    traceability_row_ids = set(_traceability_rows_by_id(traceability))
    coverage: set[str] = set()
    records: list[dict[str, Any]] = []
    for raw_record in split_records:
        if not isinstance(raw_record, dict):
            raise ValueError("split_outcome_records entries must be mappings")
        record_id = raw_record.get("id")
        if not isinstance(record_id, str) or not record_id.strip():
            raise ValueError("split_outcome_records ids must be non-empty strings")
        record_id = record_id.strip()

        path_classes = _label_sequence(
            raw_record.get("path_classes"),
            field="path_classes",
            record_id=record_id,
        )
        unknown_classes = set(path_classes) - expected_categories
        if unknown_classes:
            raise ValueError(f"scenario record {record_id!r} uses unknown path classes: {sorted(unknown_classes)}")
        coverage.update(path_classes)

        scenario_refs = _label_sequence(
            raw_record.get("scenario_refs"),
            field="scenario_refs",
            record_id=record_id,
        )
        missing_scenarios = [scenario_id for scenario_id in scenario_refs if scenario_id not in scenarios_by_id]
        if missing_scenarios:
            raise ValueError(f"scenario record {record_id!r} references unknown scenarios: {missing_scenarios}")

        row_ids = _label_sequence(
            raw_record.get("row_ids"),
            field="row_ids",
            record_id=record_id,
        )
        unknown_row_ids = set(row_ids) - traceability_row_ids
        if unknown_row_ids:
            raise ValueError(f"scenario record {record_id!r} references unknown row ids: {sorted(unknown_row_ids)}")
        allowed_row_ids = {
            row_id
            for scenario_id in scenario_refs
            for row_id in scenarios_by_id[scenario_id]["rows"]
            if isinstance(row_id, str)
        }
        stray_row_ids = set(row_ids) - allowed_row_ids
        if stray_row_ids:
            raise ValueError(
                f"scenario record {record_id!r} row ids are not covered by its scenario refs: {sorted(stray_row_ids)}"
            )

        executable_modules_raw = raw_record.get("executable_modules")
        if not isinstance(executable_modules_raw, list) or not executable_modules_raw:
            raise ValueError(f"scenario record {record_id!r} must declare executable_modules")
        executable_modules: list[dict[str, Any]] = []
        for index, module in enumerate(executable_modules_raw):
            if not isinstance(module, dict):
                raise ValueError(f"scenario record {record_id!r} executable_modules[{index}] must be a mapping")
            module_path = _normalize_repo_relative_path(
                module.get("path"),
                field=f"executable_modules[{index}].path",
                record_id=record_id,
            )
            module_target = repo_root / module_path
            if not module_target.is_file():
                raise ValueError(f"scenario record {record_id!r} executable module is missing: {module_path}")
            case_ids = _label_sequence(
                module.get("case_ids"),
                field=f"executable_modules[{index}].case_ids",
                record_id=record_id,
            )
            executable_modules.append(
                {
                    "path": module_path,
                    "case_ids": sorted(set(case_ids)),
                    "sha256": _sha256(module_target),
                }
            )

        expected_outcomes = _label_sequence(
            raw_record.get("expected_outcomes"),
            field="expected_outcomes",
            record_id=record_id,
        )

        deterministic_fixture_paths = _label_sequence(
            raw_record.get("deterministic_fixture_paths"),
            field="deterministic_fixture_paths",
            record_id=record_id,
        )
        deterministic_fixture_hashes: list[dict[str, str]] = []
        for fixture_path in deterministic_fixture_paths:
            normalized = _normalize_repo_relative_path(
                fixture_path,
                field="deterministic_fixture_paths",
                record_id=record_id,
            )
            target = repo_root / normalized
            if not target.is_file():
                raise ValueError(f"scenario record {record_id!r} fixture path is missing: {normalized}")
            deterministic_fixture_hashes.append({"path": normalized, "sha256": _sha256(target)})

        source_warrant_paths = _label_sequence(
            raw_record.get("source_warrant_paths"),
            field="source_warrant_paths",
            record_id=record_id,
        )
        source_warrant_hashes: list[dict[str, str]] = []
        for source_path in source_warrant_paths:
            normalized = _normalize_repo_relative_path(
                source_path,
                field="source_warrant_paths",
                record_id=record_id,
            )
            target = repo_root / normalized
            if not target.is_file():
                raise ValueError(f"scenario record {record_id!r} source warrant path is missing: {normalized}")
            source_warrant_hashes.append({"path": normalized, "sha256": _sha256(target)})

        route_authority = raw_record.get("route_authority")
        if route_authority is not False:
            raise ValueError(f"scenario record {record_id!r} must set route_authority to false")

        hash_payload = {
            "record_id": record_id,
            "path_classes": sorted(set(path_classes)),
            "scenario_refs": sorted(set(scenario_refs)),
            "row_ids": sorted(set(row_ids)),
            "expected_outcomes": sorted(set(expected_outcomes)),
            "route_authority": False,
            "refresh_rule": refresh_rule.strip(),
            "authority_rule": authority_rule.strip(),
            "executable_modules": executable_modules,
            "deterministic_fixture_hashes": deterministic_fixture_hashes,
            "source_warrant_hashes": source_warrant_hashes,
        }
        records.append(
            {
                "record_id": record_id,
                "path_classes": sorted(set(path_classes)),
                "scenario_refs": sorted(set(scenario_refs)),
                "row_ids": sorted(set(row_ids)),
                "expected_outcomes": sorted(set(expected_outcomes)),
                "route_authority": False,
                "scenario_manifest_path": _relative_path(scenarios_path, repo_root=repo_root),
                "scenario_manifest_sha256": _sha256(scenarios_path),
                "record_sha256": _stable_payload_sha256(hash_payload),
                "refresh_rule": refresh_rule.strip(),
                "authority_rule": authority_rule.strip(),
                "executable_modules": executable_modules,
                "deterministic_fixture_hashes": deterministic_fixture_hashes,
                "source_warrant_hashes": source_warrant_hashes,
            }
        )

    if coverage != expected_categories:
        raise ValueError(
            f"split-outcome coverage mismatch: expected {sorted(expected_categories)}, got {sorted(coverage)}"
        )
    return records


def generate_evidence_bundle(
    *,
    conformance_path: Path,
    repo_root: Path,
    traceability_path: Path | None = None,
    boundary_fixture_root: Path | None = None,
    scenarios_path: Path | None = None,
) -> dict[str, Any]:
    conformance = _load_yaml(conformance_path)
    rows = conformance.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"{conformance_path} rows must be a list")
    resolved_traceability_path = traceability_path or (repo_root / DEFAULT_TRACEABILITY)
    traceability = _load_yaml(resolved_traceability_path)
    resolved_boundary_fixture_root = boundary_fixture_root or (repo_root / DEFAULT_BOUNDARY_FIXTURE_ROOT)
    resolved_scenarios_path = scenarios_path or (repo_root / DEFAULT_SCENARIOS)

    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{conformance_path} rows entries must be mappings")
        if row.get("status") != "implemented":
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            raise ValueError("implemented rows must have non-empty ids")
        carrier_evidence = row.get("carrier_evidence")
        proof_artifacts = row.get("proof_artifacts")
        if not isinstance(carrier_evidence, list) or not carrier_evidence:
            raise ValueError(f"implemented row {row_id!r} must declare non-empty carrier_evidence")
        if not isinstance(proof_artifacts, list) or not proof_artifacts:
            raise ValueError(f"implemented row {row_id!r} must declare non-empty proof_artifacts")
        for carrier_path in carrier_evidence:
            if not isinstance(carrier_path, str) or not carrier_path:
                raise ValueError(f"implemented row {row_id!r} has invalid carrier path {carrier_path!r}")
            if carrier_path in FORBIDDEN_AUTHORITY_PATHS:
                raise ValueError(
                    f"implemented row {row_id!r} cannot use forbidden authority carrier {carrier_path!r}"
                )
            carrier_name = APPROVED_CARRIER_NAMES.get(carrier_path)
            if carrier_name is None:
                raise ValueError(f"implemented row {row_id!r} uses unapproved carrier {carrier_path!r}")
            proof_artifact_path = _select_proof_artifact(carrier_path, proof_artifacts)
            records.append(
                _build_source_checker_record(
                    row=row,
                    carrier_path=carrier_path,
                    carrier_name=carrier_name,
                    proof_artifact_path=proof_artifact_path,
                    repo_root=repo_root,
                )
            )

    (
        boundary_contract_records,
        boundary_receipt_records,
        boundary_semantic_health_records,
        boundary_phase_result_records,
        boundary_fixture_hashes,
    ) = _build_boundary_fixture_bundle(
        rows=[row for row in rows if isinstance(row, dict)],
        traceability=traceability,
        repo_root=repo_root,
        fixture_root=resolved_boundary_fixture_root,
    )
    scenario_hashes = _build_split_outcome_hashes(
        repo_root=repo_root,
        traceability=traceability,
        scenarios_path=resolved_scenarios_path,
    )
    quarantine_records = _build_quarantine_scans(rows, repo_root=repo_root)

    return {
        "schema": EVIDENCE_SCHEMA,
        "records": records,
        "boundary_contract_records": boundary_contract_records,
        "boundary_receipt_records": boundary_receipt_records,
        "boundary_semantic_health_records": boundary_semantic_health_records,
        "boundary_phase_result_records": boundary_phase_result_records,
        "scenario_hashes": scenario_hashes,
        "installed_package_fingerprints": _build_installed_package_fingerprints(
            [row for row in rows if isinstance(row, dict)],
            repo_root=repo_root,
        ),
        "topology_regeneration_checks": _build_topology_regeneration_checks(
            [row for row in rows if isinstance(row, dict)],
            repo_root=repo_root,
        ),
        "handler_purity_checks": _build_handler_purity_checks(
            [row for row in rows if isinstance(row, dict)],
            repo_root=repo_root,
        ),
        "compatibility_quarantine_checks": _build_compatibility_quarantine_checks(
            [row for row in rows if isinstance(row, dict)],
            quarantine_records=quarantine_records,
            repo_root=repo_root,
        ),
        "dead_delete_mutation_checks": _build_dead_delete_mutation_checks(
            [row for row in rows if isinstance(row, dict)],
            repo_root=repo_root,
        ),
        "approved_carriers": _build_approved_carrier_inventory(rows, repo_root=repo_root),
        "fixture_hashes": _build_fixture_hashes(rows, repo_root=repo_root),
        "boundary_fixture_hashes": boundary_fixture_hashes,
        "quarantine_records": quarantine_records,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--conformance",
        default=DEFAULT_CONFORMANCE,
        help=f"Conformance ledger to read (default: {DEFAULT_CONFORMANCE})",
    )
    parser.add_argument(
        "--traceability",
        default=DEFAULT_TRACEABILITY,
        help=f"Traceability ledger to read (default: {DEFAULT_TRACEABILITY})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Evidence bundle path to write (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used to resolve relative paths (default: .)",
    )
    parser.add_argument(
        "--boundary-fixture-root",
        default=DEFAULT_BOUNDARY_FIXTURE_ROOT,
        help=(
            "Output directory for generated semantic-health fixture artifacts "
            f"(default: {DEFAULT_BOUNDARY_FIXTURE_ROOT})"
        ),
    )
    parser.add_argument(
        "--scenarios",
        default=DEFAULT_SCENARIOS,
        help=f"Scenario manifest path to read (default: {DEFAULT_SCENARIOS})",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root).resolve()
    conformance_path = Path(args.conformance)
    if not conformance_path.is_absolute():
        conformance_path = repo_root / conformance_path
    traceability_path = Path(args.traceability)
    if not traceability_path.is_absolute():
        traceability_path = repo_root / traceability_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    boundary_fixture_root = Path(args.boundary_fixture_root)
    if not boundary_fixture_root.is_absolute():
        boundary_fixture_root = repo_root / boundary_fixture_root
    scenarios_path = Path(args.scenarios)
    if not scenarios_path.is_absolute():
        scenarios_path = repo_root / scenarios_path

    bundle = generate_evidence_bundle(
        conformance_path=conformance_path,
        repo_root=repo_root,
        traceability_path=traceability_path,
        boundary_fixture_root=boundary_fixture_root,
        scenarios_path=scenarios_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(bundle, sort_keys=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
