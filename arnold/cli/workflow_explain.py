"""Source-first explain builder for workflow CLI commands."""

from __future__ import annotations

from typing import Any

from arnold.manifest.manifests import WorkflowManifest, WorkflowNode
from arnold.workflow.source_compiler import (
    ParsedBranchBlock,
    ParsedIntrinsicCall,
    ParsedLoopBlock,
    ParsedSourceBlock,
    ParsedStepCall,
    ParsedSubflowCall,
    WorkflowDeclaration,
)


def _span_dict(span: Any) -> dict[str, Any] | None:
    if span is None:
        return None
    return {
        "path": span.path,
        "start_line": span.start_line,
        "start_column": span.start_column,
        "end_line": span.end_line,
        "end_column": span.end_column,
    }


def _node_input_bindings(node: WorkflowNode) -> dict[str, Any]:
    bindings = node.metadata.get("input_bindings", {})
    if not isinstance(bindings, dict):
        return {}
    return {
        name: {"value_ref": meta.get("value_ref") if isinstance(meta, dict) else None}
        for name, meta in bindings.items()
    }


def explain_step(
    call: ParsedStepCall,
    node: WorkflowNode | None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "kind": "step",
        "id": call.id,
        "summary": f"step {call.id} calls {call.component_ref}",
        "component_ref": call.component_ref,
        "source": _span_dict(call.source_span),
    }
    if node is not None:
        entry["node_id"] = node.id
        entry["inputs"] = _node_input_bindings(node)
    component = call.component
    if component is not None:
        if component.prompt is not None:
            entry["prompt"] = {
                "id": component.prompt.id,
                "label": component.prompt.label,
            }
        if component.policy is not None:
            entry["policy"] = {
                "id": component.policy.id,
                "policy_type": component.policy.policy_type,
            }
        if component.input_schema is not None:
            entry["input_schema"] = {"id": component.input_schema.id}
        if component.output_schema is not None:
            entry["output_schema"] = {"id": component.output_schema.id}
    return entry


def explain_subflow(call: ParsedSubflowCall) -> dict[str, Any]:
    return {
        "kind": "subflow",
        "id": call.id,
        "summary": f"subflow {call.id} calls {call.component_ref}",
        "component_ref": call.component_ref,
        "workflow_id": call.component.workflow_id if call.component is not None else None,
        "version": call.component.version if call.component is not None else None,
        "manifest_hash": call.manifest_hash,
        "source": _span_dict(call.source_span),
    }


def explain_branch(block: ParsedBranchBlock) -> dict[str, Any]:
    return {
        "kind": "branch",
        "id": f"branch-on-{block.decision_output}",
        "summary": f"branch on {block.decision_output} with {len(block.arms)} arm(s)",
        "decision_output": block.decision_output,
        "arms": [
            {
                "condition": {
                    "decision_output": arm.condition.decision_output,
                    "literal": arm.condition.literal,
                }
                if arm.condition is not None
                else None,
                "terminal": arm.terminal,
                "source": _span_dict(arm.source_span),
            }
            for arm in block.arms
        ],
        "source": _span_dict(block.source_span),
    }


def explain_loop(block: ParsedLoopBlock) -> dict[str, Any]:
    policy = block.policy
    return {
        "kind": "loop",
        "id": policy.reentry_id,
        "summary": (
            f"bounded loop (max {policy.max_iterations} iterations, "
            f"reentry {policy.reentry_id})"
        ),
        "policy_ref": policy.policy_ref,
        "max_iterations": policy.max_iterations,
        "reentry_id": policy.reentry_id,
        "until_ref": policy.until_ref,
        "source": _span_dict(block.source_span),
    }


def explain_intrinsic(call: ParsedIntrinsicCall) -> dict[str, Any]:
    return {
        "kind": "intrinsic",
        "id": call.name,
        "summary": f"intrinsic {call.name}",
        "arguments": dict(call.arguments),
        "source": _span_dict(call.source_span),
    }


def build_explain_entries(
    decl: WorkflowDeclaration,
    manifest: WorkflowManifest,
) -> list[dict[str, Any]]:
    """Return source-first explain entries for a parsed workflow and its manifest."""

    nodes_by_id = {node.id: node for node in manifest.nodes}
    block = decl.source_block
    entries: list[dict[str, Any]] = []
    for statement in block.statements:
        if isinstance(statement, ParsedStepCall):
            entries.append(explain_step(statement, nodes_by_id.get(statement.id)))
        elif isinstance(statement, ParsedSubflowCall):
            entries.append(explain_subflow(statement))
        elif isinstance(statement, ParsedBranchBlock):
            entries.append(explain_branch(statement))
        elif isinstance(statement, ParsedLoopBlock):
            entries.append(explain_loop(statement))
        elif isinstance(statement, ParsedIntrinsicCall):
            entries.append(explain_intrinsic(statement))

    # Workflow-level policies and suspension points are separate top-level entries.
    if decl.policies:
        entries.append(
            {
                "kind": "workflow-policies",
                "id": "workflow-policies",
                "summary": f"workflow policies: {', '.join(p.keyword for p in decl.policies)}",
                "policies": [
                    {
                        "keyword": p.keyword,
                        "component_ref": p.component_ref,
                        "policy_type": p.component.policy_type if p.component is not None else None,
                    }
                    for p in decl.policies
                ],
            }
        )

    suspension_points: list[dict[str, Any]] = []
    for node in manifest.nodes:
        if node.policy is None:
            continue
        for route in node.policy.suspension_routes:
            suspension_points.append(
                {
                    "node_id": node.id,
                    "route_id": route.route_id,
                    "capability_id": route.capability_id,
                    "reentry_id": route.reentry_id,
                }
            )
    if manifest.policy is not None:
        for route in manifest.policy.suspension_routes:
            suspension_points.append(
                {
                    "node_id": None,
                    "route_id": route.route_id,
                    "capability_id": route.capability_id,
                    "reentry_id": route.reentry_id,
                }
            )
    if suspension_points:
        entries.append(
            {
                "kind": "suspension-points",
                "id": "suspension-points",
                "summary": f"{len(suspension_points)} suspension point(s)",
                "suspension_points": suspension_points,
            }
        )

    return entries


__all__ = ["build_explain_entries"]
