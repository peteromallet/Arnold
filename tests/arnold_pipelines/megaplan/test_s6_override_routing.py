from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from arnold.control.interface import ControlTransition
from arnold.workflow import authoring
from arnold.workflow.compiler import compile_pipeline
from arnold_pipelines.megaplan.control_interface import DECLARED_OVERRIDE_POLICY_TARGETS
from arnold_pipelines.megaplan.control_interface import apply_transition
from arnold_pipelines.megaplan.handlers.override import handle_override
from arnold_pipelines.megaplan.outcomes import OverrideOutcome, OverridePolicyRoute
from arnold_pipelines.megaplan.planning.control_binding import planning_run_state_view
from arnold_pipelines.megaplan.semantic_health import inspect_semantic_health
from arnold_pipelines.megaplan import workflows
from arnold_pipelines.megaplan.workflows import planning
from arnold_pipelines.megaplan.workflows.override_matrix import OVERRIDE_ACTION_MATRIX
from arnold_pipelines.megaplan.workflows.boundary_contracts import (
    OVERRIDE_AUTHORITY_CONTRACTS,
    execute_approval,
)


def _workflow_tree() -> ast.Module:
    return ast.parse(planning.AUTHORING_SOURCE_PATH.read_text(encoding="utf-8"))


def _override_branch_signals() -> set[str]:
    signals: set[str] = set()
    for node in ast.walk(_workflow_tree()):
        if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Name):
            continue
        if node.left.id != "override_result":
            continue
        for comparator in node.comparators:
            if (
                isinstance(comparator, ast.Attribute)
                and isinstance(comparator.value, ast.Name)
                and comparator.value.id == "OverrideOutcome"
                and comparator.attr in OverrideOutcome.__members__
            ):
                signals.add(OverrideOutcome[comparator.attr].value)
    return signals


def _declaration_literal_value(node: ast.AST) -> Any:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "OverrideOutcome"
        and node.attr in OverrideOutcome.__members__
    ):
        return OverrideOutcome[node.attr].value
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "OverridePolicyRoute"
        and node.attr in OverridePolicyRoute.__members__
    ):
        return OverridePolicyRoute[node.attr].value
    if isinstance(node, ast.Constant) and (
        node.value is None or isinstance(node.value, str)
    ):
        return node.value
    if isinstance(node, ast.Tuple):
        return tuple(_declaration_literal_value(item) for item in node.elts)
    raise AssertionError(f"Unsupported declaration literal: {ast.dump(node)}")


def _declared_override_routes(name: str) -> dict[str, dict[str, Any]]:
    for node in _workflow_tree().body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            raise AssertionError(f"{name} must be a dict literal")
        routes: dict[str, dict[str, Any]] = {}
        for key_node, value_node in zip(node.value.keys, node.value.values, strict=True):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                raise AssertionError("Override policy route keys must be string literals")
            if not isinstance(value_node, ast.Dict):
                raise AssertionError("Override route entries must be dict literals")
            entry: dict[str, Any] = {}
            for field_node, field_value_node in zip(value_node.keys, value_node.values, strict=True):
                if not isinstance(field_node, ast.Constant) or not isinstance(field_node.value, str):
                    raise AssertionError("Override route fields must be string literals")
                field_name = field_node.value
                entry[field_name] = _declaration_literal_value(field_value_node)
            routes[key_node.value] = entry
        return routes
    raise AssertionError(f"{name} not found in workflow.pypeline")


def _declared_override_outcome_targets() -> dict[str, dict[str, Any]]:
    return _declared_override_routes("DECLARED_OVERRIDE_OUTCOME_TARGETS")


def _declared_override_policy_routes() -> dict[str, dict[str, Any]]:
    return _declared_override_routes("DECLARED_OVERRIDE_POLICY_ROUTES")


def _routing_entries() -> dict[str, object]:
    return {
        entry.action: entry
        for entry in OVERRIDE_ACTION_MATRIX
        if entry.family == "terminal_route"
    }


def _effect_only_entries() -> dict[str, object]:
    return {
        entry.action: entry
        for entry in OVERRIDE_ACTION_MATRIX
        if entry.family == "additive_config"
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _clone_step_component_with_metadata(
    component: authoring.StepComponent,
    metadata: dict[str, object],
) -> authoring.StepComponent:
    return authoring.StepComponent(
        id=component.id,
        provenance=component.provenance,
        label=component.label,
        step_type=component.step_type,
        prompt=component.prompt,
        policy=component.policy,
        input_schema=component.input_schema,
        output_schema=component.output_schema,
        metadata=metadata,
    )


def _clone_workflow_component_with_metadata(
    component: authoring.ComponentContract,
    metadata: dict[str, object],
) -> authoring.ComponentContract:
    return authoring.ComponentContract(
        id=component.id,
        kind=component.kind,
        provenance=component.provenance,
        label=component.label,
        metadata=metadata,
    )


def _plan_dir(root: Path, plan: str = "demo") -> Path:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True, exist_ok=True)
    return plan_dir


def _base_state(root: Path, *, current_state: str) -> dict[str, Any]:
    return {
        "name": "demo",
        "idea": "Override routing authority test",
        "current_state": current_state,
        "iteration": 1,
        "created_at": "2026-07-08T10:14:00Z",
        "config": {"project_dir": str(root)},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"current_invocation_id": "inv-test"},
        "last_gate": {},
        "latest_failure": None,
    }


def _finding_ids(plan_dir: Path) -> set[str]:
    return {finding.finding_id for finding in inspect_semantic_health(plan_dir)}


def test_s6_override_matrix_distinguishes_routing_and_effect_only_actions() -> None:
    routing_entries = _routing_entries()
    effect_only_entries = _effect_only_entries()

    assert set(routing_entries) == {
        "abort",
        "adopt-execution",
        "force-proceed",
        "recover-blocked",
        "replan",
        "resume-clarify",
    }
    assert set(effect_only_entries) == {
        "add-note",
        "set-model",
        "set-profile",
        "set-robustness",
        "set-vendor",
    }

    for entry in routing_entries.values():
        assert entry.route_signal is not None


def test_s6_override_gap_table_is_explicit_in_current_native_surface() -> None:
    routing_entries = _routing_entries()
    typed_signal_to_action = {
        entry.route_signal: action
        for action, entry in routing_entries.items()
        if entry.dispatch_surface == "workflow.route_binding"
    }
    policy_signal_to_action = {
        entry.route_signal: action
        for action, entry in routing_entries.items()
        if entry.dispatch_surface == "workflow.native_policy"
    }
    typed_surface = {outcome.value for outcome in OverrideOutcome}
    workflow_surface = _override_branch_signals()
    policy_surface = {
        entry["route_signal"]
        for entry in _declared_override_policy_routes().values()
        if entry.get("route_signal") is not None
    }
    missing_typed_actions = {
        typed_signal_to_action[signal]
        for signal in typed_signal_to_action
        if signal not in typed_surface or signal not in workflow_surface
    }
    missing_policy_actions = {
        policy_signal_to_action[signal]
        for signal in policy_signal_to_action
        if signal not in policy_surface
    }

    assert typed_surface == {"abort", "force_proceed", "replan"}
    assert workflow_surface == {"abort", "force_proceed", "replan"}
    assert policy_surface == {"adopt_execution", "recover_blocked", "resume_clarify"}
    assert missing_typed_actions == set()
    assert missing_policy_actions == set()
    assert set(policy_signal_to_action.values()) == {
        "adopt-execution",
        "recover-blocked",
        "resume-clarify",
    }


def test_s6_override_outcome_targets_are_declared_in_canonical_source() -> None:
    assert _declared_override_outcome_targets() == {
        "abort": {
            "route_signal": "abort",
            "target_ref": "halt",
            "terminal_state_ref": "aborted",
            "description": (
                "Terminate the workflow through the halt node and land in the aborted terminal state."
            ),
        },
        "force-proceed": {
            "route_signal": "force_proceed",
            "target_refs": ("finalize", "execute"),
            "terminal_state_ref": "done",
            "description": (
                "Drive the native finalize/execute path, or land in done when the override exits the review loop."
            ),
        },
        "replan": {
            "route_signal": "replan",
            "target_ref": "revise",
            "reentry_target_ref": "critique",
            "description": (
                "Re-enter the planning loop by routing through revise and back to the critique reentry."
            ),
        },
    }


def test_s6_routing_override_actions_must_be_visible_in_native_surface() -> None:
    routing_entries = _routing_entries()
    declared_outcome_targets = _declared_override_outcome_targets()
    declared_policy_routes = _declared_override_policy_routes()
    typed_surface = {outcome.value for outcome in OverrideOutcome}
    workflow_surface = _override_branch_signals()
    typed_missing_from_enum: list[str] = []
    typed_missing_from_workflow: list[str] = []
    typed_missing_source_targets: list[str] = []
    policy_missing_from_workflow: list[str] = []
    policy_missing_route_ref: list[str] = []

    for action, entry in routing_entries.items():
        if entry.dispatch_surface == "workflow.route_binding":
            declared = declared_outcome_targets.get(action)
            if declared is None or declared.get("route_signal") != entry.route_signal:
                typed_missing_source_targets.append(action)
            if entry.route_signal not in typed_surface:
                typed_missing_from_enum.append(action)
            if entry.route_signal not in workflow_surface:
                typed_missing_from_workflow.append(action)
        elif entry.dispatch_surface == "workflow.native_policy":
            declared = declared_policy_routes.get(action)
            if declared is None:
                policy_missing_from_workflow.append(action)
                continue
            if declared.get("route_signal") != entry.route_signal:
                policy_missing_from_workflow.append(action)
            if declared.get("policy_route_ref") != entry.policy_route_ref:
                policy_missing_route_ref.append(action)
            declared_target_ref = declared.get("declared_target_ref", declared.get("target_ref"))
            if declared_target_ref != entry.declared_target_ref:
                policy_missing_from_workflow.append(action)

    assert (
        not typed_missing_from_enum
        and not typed_missing_from_workflow
        and not typed_missing_source_targets
        and not policy_missing_from_workflow
        and not policy_missing_route_ref
    ), (
        "Every routing override action must have either a native typed outcome "
        "branch or a declared native policy route before handler-local dispatch "
        "is removed. "
        f"Missing typed outcomes: {typed_missing_from_enum}; "
        f"missing typed workflow branches: {typed_missing_from_workflow}; "
        f"missing typed source target declarations: {typed_missing_source_targets}; "
        f"missing policy route declarations: {policy_missing_from_workflow}; "
        f"policy route ref mismatches: {policy_missing_route_ref}"
    )


def test_s6_effect_only_override_actions_have_no_product_route_target() -> None:
    effect_only_entries = _effect_only_entries()
    declared_outcome_targets = _declared_override_outcome_targets()
    workflow_surface = _override_branch_signals()
    typed_surface = {outcome.value for outcome in OverrideOutcome}

    for action, entry in effect_only_entries.items():
        assert action not in declared_outcome_targets
        assert entry.target_ref is None, f"{action} should not name a product route target"
        assert entry.policy_route_ref is None, f"{action} should not name a policy route target"
        assert entry.effect_id is not None, f"{action} should stay effect-only"
        assert entry.dispatch_surface == "policy.effect"
        assert entry.declared_target_ref is None, f"{action} should not name a declared route target"
        assert entry.route_signal not in typed_surface
        assert entry.route_signal not in workflow_surface


def test_s6_control_interface_policy_targets_match_native_route_declarations() -> None:
    declared_policy_routes = _declared_override_policy_routes()

    assert DECLARED_OVERRIDE_POLICY_TARGETS == {
        action: {
            "route_signal": str(entry["route_signal"]),
            "target_ref": str(entry.get("declared_target_ref", entry.get("target_ref"))),
            "policy_route_ref": str(entry["policy_route_ref"]),
        }
        for action, entry in declared_policy_routes.items()
    }


def test_s6_corrected_override_routes_survive_component_metadata_collapse(
    monkeypatch,
) -> None:
    baseline_pipeline = planning.build_pipeline()
    baseline_manifest = compile_pipeline(baseline_pipeline)
    baseline_routes = {
        (route.id, route.source, route.label, route.target)
        for route in baseline_pipeline.routes
        if route.source in {"gate", "finalize", "override", "tiebreaker_decision"}
    }

    stripped_components = []
    for component in planning.PIPELINE_STEP_COMPONENTS:
        step_id = component.id.removeprefix("megaplan:")
        if step_id in {"tiebreaker_run", "tiebreaker_decide"}:
            stripped_components.append(component)
            continue
        stripped_components.append(
            _clone_step_component_with_metadata(
                component,
                {
                    key: value
                    for key, value in component.metadata.items()
                    if key
                    not in {
                        "handler_ref",
                        "route_bindings",
                        "policy_refs",
                        "capability_requirements",
                        "override_actions",
                        "terminal",
                    }
                },
            )
        )
    stripped_components = tuple(stripped_components)
    monkeypatch.setattr(planning, "PIPELINE_STEP_COMPONENTS", stripped_components)
    monkeypatch.setattr(
        planning,
        "PIPELINE_STEP_COMPONENTS_BY_ID",
        {component.id.removeprefix("megaplan:"): component for component in stripped_components},
    )
    for export_name in (
        "SOURCE_EXECUTE_BATCH_WORKFLOW",
        "SOURCE_REVIEW_PANEL_WORKFLOW",
        "SOURCE_TIEBREAKER_WORKFLOW",
    ):
        component = getattr(workflows.components, export_name)
        monkeypatch.setattr(
            workflows.components,
            export_name,
            _clone_workflow_component_with_metadata(
                component,
                {
                    key: value
                    for key, value in component.metadata.items()
                    if key not in {"topology_contract", "fan_in_ref", "policy_refs"}
                },
            ),
        )

    pipeline = planning.build_pipeline()
    manifest = compile_pipeline(pipeline)

    assert {
        (route.id, route.source, route.label, route.target)
        for route in pipeline.routes
        if route.source in {"gate", "finalize", "override", "tiebreaker_decision"}
    } == baseline_routes
    assert manifest.to_json() == baseline_manifest.to_json()


def test_s6_override_and_human_gate_transitions_have_authority_contracts() -> None:
    authority_contracts = {
        contract.details["authority_transition"]: contract
        for contract in OVERRIDE_AUTHORITY_CONTRACTS
    }

    assert set(authority_contracts) == {
        "abort",
        "force-proceed",
        "replan",
        "recover-blocked",
        "resume-clarify",
        "adopt-execution",
        "suspension-waiver",
        "human-gate",
    }

    for action in _routing_entries():
        contract = authority_contracts[action]
        assert contract.details["actor_role_ref"] == "authority_records[].{actor,role}"
        assert contract.details["evidence_hashes_ref"] == (
            "authority_records[].details.evidence_hashes"
        )
        assert contract.details["freshness_token_ref"] == "state.meta.current_invocation_id"

    assert authority_contracts["human-gate"].details["approval_scope_ref"] == (
        "execute:approval-approved"
    )
    assert authority_contracts["suspension-waiver"].details["policy_ref"] == "megaplan:suspension"
    assert execute_approval.authority_required is True


def test_recover_blocked_emits_authority_receipt_and_stale_state_fails(
    tmp_path: Path,
) -> None:
    plan_dir = _plan_dir(tmp_path)
    state = _base_state(tmp_path, current_state="blocked")
    state["resume_cursor"] = {"phase": "review", "retry_strategy": "manual_review"}
    state["latest_failure"] = {"kind": "manual_block"}
    _write_json(plan_dir / "state.json", state)
    _write_json(
        plan_dir / "phase_result.json",
        {
            "schema": "megaplan.phase_result",
            "schema_version": 1,
            "phase_result_contract_version": 1,
            "phase": "review",
            "invocation_id": "inv-test",
            "exit_kind": "blocked_by_quality",
            "blocked_tasks": [],
            "deviations": [],
            "artifacts_written": [],
            "cli_provenance": {},
            "external_error": None,
        },
    )
    _write_json(plan_dir / "finalize.json", {"tasks": []})

    result = apply_transition(
        planning_run_state_view(state),
        ControlTransition(
            op="override",
            target_id="recover-blocked",
            payload={"reason": "operator cleared blockers"},
        ),
        "megaplan",
        plan_dir=plan_dir,
    )

    assert result.accepted is True
    receipt_payload = json.loads(
        (plan_dir / "boundary_receipts" / "override_recover_blocked_authority.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt_payload["authority_records"][0]["decision"] == "recover-blocked"
    assert receipt_payload["authority_records"][0]["details"]["declared_target_ref"] == (
        "recovery_predecessor"
    )
    assert "SH-override_recover_blocked_authority-authority-evidence-hash-mismatch-0" not in _finding_ids(
        plan_dir
    )

    persisted_state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    persisted_state["current_state"] = "blocked"
    _write_json(plan_dir / "state.json", persisted_state)

    assert "SH-override_recover_blocked_authority-authority-evidence-hash-mismatch-0" in _finding_ids(
        plan_dir
    )


def test_resume_clarify_emits_authority_receipt(tmp_path: Path) -> None:
    plan_dir = _plan_dir(tmp_path)
    state = _base_state(tmp_path, current_state="awaiting_human_verify")
    state["clarification"] = {"source": "prep"}
    state["meta"]["notes"] = [
        {
            "timestamp": "2026-07-08T10:15:00Z",
            "note": "operator answered clarification",
            "source": "user",
        }
    ]
    _write_json(plan_dir / "state.json", state)

    result = apply_transition(
        planning_run_state_view(state),
        ControlTransition(
            op="override",
            target_id="resume-clarify",
            payload={},
        ),
        "megaplan",
        plan_dir=plan_dir,
    )

    assert result.accepted is True
    receipt_payload = json.loads(
        (plan_dir / "boundary_receipts" / "override_resume_clarify_authority.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt_payload["authority_records"][0]["decision"] == "resume-clarify"
    assert receipt_payload["authority_records"][0]["details"]["declared_target_ref"] == "plan"
    assert "SH-override_resume_clarify_authority-authority-records-missing" not in _finding_ids(
        plan_dir
    )


def test_adopt_execution_emits_authority_receipt_and_mismatched_evidence_fails(
    tmp_path: Path,
) -> None:
    plan_dir = _plan_dir(tmp_path)
    state = _base_state(tmp_path, current_state="finalized")
    _write_json(plan_dir / "state.json", state)
    _write_json(
        plan_dir / "finalize.json",
        {
            "tasks": [{"id": "T1", "status": "done"}],
            "sense_checks": [{"id": "SC1"}],
        },
    )
    _write_json(
        plan_dir / "execution.json",
        {
            "task_updates": [{"task_id": "T1", "status": "done"}],
            "sense_check_acknowledgments": [{"sense_check_id": "SC1"}],
        },
    )

    response = handle_override(
        tmp_path,
        argparse.Namespace(
            plan="demo",
            override_action="adopt-execution",
            reason="operator adopted finished execution",
        ),
    )

    assert response["success"] is True
    receipt_payload = json.loads(
        (plan_dir / "boundary_receipts" / "override_adopt_execution_authority.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt_payload["authority_records"][0]["decision"] == "adopt-execution"
    assert receipt_payload["authority_records"][0]["details"]["declared_target_ref"] == "review"
    assert "SH-override_adopt_execution_authority-authority-evidence-hash-mismatch-0" not in _finding_ids(
        plan_dir
    )

    mutated_finalize = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    mutated_finalize["tasks"][0]["status"] = "blocked"
    _write_json(plan_dir / "finalize.json", mutated_finalize)

    assert "SH-override_adopt_execution_authority-authority-evidence-hash-mismatch-0" in _finding_ids(
        plan_dir
    )
