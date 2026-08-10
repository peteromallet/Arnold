from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import arnold_pipelines.megaplan.handlers.execute as execute_handler
import arnold_pipelines.megaplan.handlers.finalize as finalize_handler
from arnold.pipeline.native import compile_pipeline, phase, pipeline, start_from_trace, workflow
from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    Pipeline as ArnoldPipeline,
    StepResult,
    Suspension,
)
from arnold.workflow.compiler import compile_pipeline as compile_workflow_pipeline
from arnold.workflow.source_compiler import lower_workflow_file
from arnold_pipelines.megaplan.blocker_recovery import find_synthetic_before_execute_gate
from arnold_pipelines.megaplan.execute.policy import NoReviewTerminalOutcome
from arnold_pipelines.megaplan.outcomes import (
    GateOutcome,
    OverrideOutcome,
    ReviewOutcome,
    TiebreakerOutcome,
)
from arnold_pipelines.megaplan.workflows import planning
from arnold_pipelines.megaplan.workflows.components import (
    EXECUTE_POLICY,
    FINALIZE_POLICY,
    REVIEW_POLICY,
    SOURCE_EXECUTE_BATCH_WORKFLOW,
    SOURCE_REVIEW_PANEL_WORKFLOW,
    SOURCE_TIEBREAKER_WORKFLOW,
)


def _workflow_tree() -> ast.Module:
    return ast.parse(planning.AUTHORING_SOURCE_PATH.read_text(encoding="utf-8"))


def _planning_function() -> ast.FunctionDef:
    for node in _workflow_tree().body:
        if isinstance(node, ast.FunctionDef) and node.name == "planning_workflow":
            return node
    raise AssertionError("planning_workflow not found")


def _call_ids(call_name: str) -> set[str]:
    ids: set[str] = set()
    for node in ast.walk(_planning_function()):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != call_name:
            continue
        for keyword in node.keywords:
            if keyword.arg == "id" and isinstance(keyword.value, ast.Constant):
                ids.add(str(keyword.value.value))
    return ids


def _branch_literals(name: str) -> set[str]:
    outcome_types = {
        cls.__name__: cls
        for cls in (GateOutcome, OverrideOutcome, ReviewOutcome, TiebreakerOutcome)
    }
    values: set[str] = set()
    for node in ast.walk(_planning_function()):
        if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Name):
            continue
        if node.left.id != name:
            continue
        for comparator in node.comparators:
            if isinstance(comparator, ast.Constant):
                values.add(str(comparator.value))
            elif isinstance(comparator, ast.Attribute) and isinstance(comparator.value, ast.Name):
                outcome_type = outcome_types.get(comparator.value.id)
                if outcome_type is not None and comparator.attr in outcome_type.__members__:
                    values.add(str(outcome_type[comparator.attr].value))
    return values


def test_megaplan_resume_paths_are_visible_in_authored_workflow() -> None:
    assert _branch_literals("gate_route_signal") >= {
        "proceed",
        "iterate",
        "tiebreaker",
        "escalate",
        "abort",
        "suspend",
        "blocked_preflight",
        "force_proceed",
    }
    assert _branch_literals("decision") >= {"proceed", "escalate"}
    assert _branch_literals("review_route_signal") >= {"pass", "rework"}
    assert _call_ids("AUTHORING_REVISE") >= {"revise", "review_revise", "override_revise"}
    assert _call_ids("AUTHORING_EXECUTE") >= {"force_execute", "fallback_execute"}
    assert _call_ids("AUTHORING_FINALIZE") >= {
        "override_finalize",
        "force_finalize",
        "fallback_finalize",
    }
    assert _call_ids("parallel_map") >= {"override_execute_batches"}
    assert _call_ids("AUTHORING_HALT") >= {
        "halt",
        "review_halt",
        "gate_abort",
        "gate_suspend",
        "override_halt",
    }


def test_megaplan_child_workflow_metadata_covers_tiebreaker_execute_review_gates() -> None:
    assert SOURCE_TIEBREAKER_WORKFLOW.metadata["child_steps"] == (
        "tiebreaker_run",
        "tiebreaker_decide",
    )
    tiebreaker_contract = SOURCE_TIEBREAKER_WORKFLOW.metadata["topology_contract"]
    assert {
        route["route_signal"]: route["target_ref"]
        for route in tiebreaker_contract["decision_routes"]
    } == {
        "iterate": "critique-fanout",
        "proceed": "finalize",
        "escalate": "override",
    }

    execute_contract = SOURCE_EXECUTE_BATCH_WORKFLOW.metadata["topology_contract"]
    execute_gate = execute_contract["approval_gate"]
    assert execute_gate["required_ref"] == "state.meta.user_approved_gate"
    assert execute_gate["confirmation_ref"] == "args.confirm_destructive"
    assert {
        route["route_signal"]: route["target_ref"]
        for route in execute_contract["post_batch_routes"]
    } == {
        "review_required": "review-fan-in",
        "no_review": "halt",
        "deferred_human": "halt",
    }

    review_contract = SOURCE_REVIEW_PANEL_WORKFLOW.metadata["topology_contract"]
    assert {
        route["route_signal"]: route["target_ref"]
        for route in review_contract["reducer_routes"]
    } == {
        "pass": "halt",
        "rework": "execute",
        "blocked": "halt",
        "force_proceeded": "halt",
        "deferred_human": "halt",
    }


def test_non_protected_execute_routes_declare_no_review_to_done_contract() -> None:
    execute_contract = SOURCE_EXECUTE_BATCH_WORKFLOW.metadata["topology_contract"]
    review_contract = SOURCE_REVIEW_PANEL_WORKFLOW.metadata["topology_contract"]

    assert {
        route["route_signal"]: route["target_ref"]
        for route in execute_contract["post_batch_routes"]
    }["no_review"] == "halt"
    assert review_contract["no_review_route_signal"] == "pass"


def test_finalize_handlers_project_success_and_revise_fallback_from_policy_surface() -> None:
    success = finalize_handler._finalize_success_projection()
    fallback = finalize_handler._finalize_revise_fallback_projection()
    route_surface = FINALIZE_POLICY.metadata["route_surface"]

    assert success == {
        "route_signal": route_surface["success_route"]["route_signal"],
        "next_step": route_surface["success_route"]["target_ref"],
        "state": route_surface["success_route"]["state_ref"],
    }
    assert fallback == {
        "route_signal": route_surface["fallback_routes"]["plan_contract_revise_needed"]["route_signal"],
        "next_step": route_surface["fallback_routes"]["plan_contract_revise_needed"]["target_ref"],
        "state": "critiqued",
    }


def test_execute_terminal_projection_helpers_follow_source_policy_routes() -> None:
    execute_route_surface = EXECUTE_POLICY.metadata["route_surface"]
    finalize_route_surface = FINALIZE_POLICY.metadata["route_surface"]

    blocked = execute_handler._blocked_execute_projection()
    done = execute_handler._no_review_terminal_projection(
        NoReviewTerminalOutcome.TERMINATE_DONE
    )
    deferred = execute_handler._no_review_terminal_projection(
        NoReviewTerminalOutcome.TERMINATE_AWAITING_HUMAN
    )

    assert blocked == {
        "route_signal": execute_route_surface["retry_and_reentry"]["blocked_route"]["route_signal"],
        "next_step": execute_route_surface["retry_and_reentry"]["blocked_route"]["target_ref"],
        "state": execute_route_surface["retry_and_reentry"]["blocked_route"]["recoverable_state"],
    }
    assert done == {
        "route_signal": finalize_route_surface["skip_review_routes"]["no_review"]["route_signal"],
        "next_step": finalize_route_surface["skip_review_routes"]["no_review"]["target_ref"],
        "state": finalize_route_surface["final_projection_routes"]["no_review_done"]["terminal_state"],
    }
    assert deferred == {
        "route_signal": finalize_route_surface["skip_review_routes"]["deferred_human"]["route_signal"],
        "next_step": finalize_route_surface["skip_review_routes"]["deferred_human"]["target_ref"],
        "state": finalize_route_surface["final_projection_routes"]["no_review_deferred_human"]["terminal_state"],
    }


def test_review_human_verification_suspend_resume_surface_is_manifest_visible() -> None:
    manifest = compile_workflow_pipeline(planning.build_pipeline())
    review = next(node for node in manifest.nodes if node.id == "review")
    human_surface = REVIEW_POLICY.metadata["route_surface"]["human_verification"]
    review_suspension = next(
        route for route in review.policy.suspension_routes
        if route.route_id == human_surface["suspension_route_id"]
    )

    assert review_suspension.capability_id == human_surface["capability_id"]
    assert review_suspension.resume_schema_ref == human_surface["resume_schema_ref"]
    assert review_suspension.resume_payload_ref == human_surface["resume_payload_ref"]
    assert human_surface["state_ref"] == "awaiting_human_verify"
    assert "suspension:review-human" in {
        overlay.overlay_id for overlay in manifest.policy.topology_overlays
    }


def test_force_proceed_and_finalize_fallback_carriers_remain_visible_in_lowered_source() -> None:
    lowered = lower_workflow_file(planning.PYPELINE_AUTHORING_SOURCE_PATH)
    route_signatures = {
        (route.source, route.label, route.target)
        for route in lowered.routes
        if route.label != "else"
    }

    assert ("force_finalize", "default", "force_execute") in route_signatures
    assert ("fallback_finalize", "default", "fallback_execute") in route_signatures
    assert _call_ids("AUTHORING_FINALIZE") >= {"finalize", "force_finalize", "fallback_finalize"}
    assert _call_ids("AUTHORING_EXECUTE") >= {"force_execute", "fallback_execute"}


def test_execute_gate_protected_action_scope_is_recoverable() -> None:
    finalize_data = {
        "tasks": [
            {
                "id": "approve-before-execute",
                "description": "Read user_actions.md. Approve before execute.",
                "depends_on": [],
            },
            {"id": "T1", "description": "first task", "depends_on": ["approve-before-execute"]},
            {"id": "T2", "description": "second task", "depends_on": ["approve-before-execute"]},
        ]
    }

    gate_task_id, protected = find_synthetic_before_execute_gate(finalize_data)

    assert gate_task_id == "approve-before-execute"
    assert protected == ("T1", "T2")


def test_human_gate_continue_repoints_primary_input_to_latest_edited_artifact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from arnold_pipelines.megaplan.cli import run as run_cli

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    original = tmp_path / "draft.md"
    original.write_text("old", encoding="utf-8")
    revise_dir = plan_dir / "revise"
    revise_dir.mkdir()
    (revise_dir / "v1.md").write_text("v1", encoding="utf-8")
    latest = revise_dir / "v2.md"
    latest.write_text("v2", encoding="utf-8")
    (plan_dir / "awaiting_user.json").write_text(
        json.dumps({"artifact_stage": "revise"}), encoding="utf-8"
    )
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "_pipeline_paused_stage": "human_decide",
                "_inputs": {"draft": str(original), "side": str(tmp_path / "side.md")},
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.registry.pipeline_metadata",
        lambda _name: {"supported_modes": ("native",), "default_profile": None},
    )
    monkeypatch.setattr(run_cli, "_build_pipeline_for_run", lambda _args: ArnoldPipeline(stages={}, entry=""))
    monkeypatch.setattr(run_cli, "_validate_run_parameters", lambda _args: None)
    monkeypatch.setattr(run_cli, "_resolve_profile_for_run", lambda **_kwargs: {})
    monkeypatch.setattr(run_cli, "_validate_profile_for_run", lambda **_kwargs: None)

    def fake_dispatch(pipeline, ctx, *, artifact_root, pipeline_key):
        del pipeline, artifact_root, pipeline_key
        captured["inputs"] = dict(ctx.inputs)
        captured["state"] = dict(ctx.state)
        return {"final_stage": "halt", "state": ctx.state}

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.bridge.run_pipeline_dispatch",
        fake_dispatch,
    )

    rc = run_cli._run_pipeline(
        argparse.Namespace(
            pipeline_name="writing-panel-strict",
            mode=None,
            profile=None,
            vendor=None,
            inputs="",
            input_file=None,
            plan_dir=str(plan_dir),
            resume_choice="continue",
            state="{}",
        )
    )

    assert rc == 0
    assert captured["inputs"]["draft"] == latest
    assert captured["state"]["_inputs"]["draft"] == str(latest)
    assert captured["state"]["_inputs_original"]["draft"] == str(latest)


def test_start_from_path_replays_nested_megaplan_trace_fixture(tmp_path: Path) -> None:
    release = {"value": False}

    @phase
    def approve(ctx: dict) -> StepResult | dict[str, bool]:
        if not release["value"]:
            return StepResult(
                outputs={},
                contract_result=ContractResult(
                    status=ContractStatus.SUSPENDED,
                    suspension=Suspension(
                        kind="human",
                        resume_cursor="approve-protected-action",
                    ),
                ),
            )
        return {"approved": True}

    @workflow(name="protected_action", outputs={"type": "object", "required": ["approved"]})
    def protected_action(ctx: dict) -> dict:
        state = yield approve(ctx)
        return state

    @workflow(name="execute_batch", outputs={"type": "object", "required": ["execute_payload"]})
    def execute_batch(ctx: dict) -> dict:
        state = yield protected_action(ctx, id="protected_action", outputs={"approved": "execute_payload"})
        return state

    @pipeline("megaplan")
    def megaplan_fixture(ctx: dict) -> dict:
        state = yield execute_batch(ctx, id="execute_batch", outputs={"execute_payload": "result"})
        return state

    program = compile_pipeline(megaplan_fixture)
    source_root = tmp_path / "source"
    trace_dir = source_root / "trace"
    first = run_native_pipeline(
        program,
        artifact_root=source_root,
        trace_dir=trace_dir,
        max_phases=1,
    )
    assert first.suspended is True

    checkpoint = json.loads((trace_dir / "checkpoint.json").read_text(encoding="utf-8"))
    release["value"] = True
    replayed = start_from_trace(
        program,
        trace_dir,
        checkpoint["step_path"],
        tmp_path / "replay",
    )

    assert replayed.suspended is False
    assert replayed.state["result"] is True
    tree = json.loads((trace_dir / "tree.json").read_text(encoding="utf-8"))
    assert "root/execute_batch/protected_action/approve" in {
        node["path"] for node in tree["nodes"]
    }
