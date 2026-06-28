"""Source topology sidecars for workflow CLI views."""

from __future__ import annotations

from typing import Any

from arnold.manifest.manifests import WorkflowManifest
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


def build_source_topology(
    decl: WorkflowDeclaration,
    manifest: WorkflowManifest,
) -> dict[str, Any]:
    """Return source-derived annotations without mutating manifest identity."""

    manifest_node_ids = {node.id for node in manifest.nodes}
    collector = _TopologyCollector(manifest_node_ids, manifest)
    collector.visit_block(decl.source_block, nesting_depth=0, context={})
    return {
        "nodes": collector.nodes,
        "branches": collector.branches,
        "loops": collector.loops,
    }


class _TopologyCollector:
    def __init__(self, manifest_node_ids: set[str], manifest: WorkflowManifest) -> None:
        self._manifest_node_ids = manifest_node_ids
        self._manifest = manifest
        self.nodes: dict[str, dict[str, Any]] = {}
        self.branches: list[dict[str, Any]] = []
        self.loops: list[dict[str, Any]] = []

    def visit_block(
        self,
        block: ParsedSourceBlock,
        *,
        nesting_depth: int,
        context: dict[str, Any],
    ) -> list[str]:
        node_ids: list[str] = []
        for statement in block.statements:
            if isinstance(statement, ParsedStepCall):
                node_ids.extend(
                    self._visit_step(
                        statement,
                        nesting_depth=nesting_depth,
                        context=context,
                    )
                )
            elif isinstance(statement, ParsedSubflowCall):
                node_ids.extend(
                    self._visit_subflow(
                        statement,
                        nesting_depth=nesting_depth,
                        context=context,
                    )
                )
            elif isinstance(statement, ParsedBranchBlock):
                node_ids.extend(
                    self._visit_branch(
                        statement,
                        nesting_depth=nesting_depth,
                        context=context,
                    )
                )
            elif isinstance(statement, ParsedLoopBlock):
                node_ids.extend(
                    self._visit_loop(
                        statement,
                        nesting_depth=nesting_depth,
                        context=context,
                    )
                )
            elif isinstance(statement, ParsedIntrinsicCall):
                continue
        return node_ids

    def _node_context_fields(self, context: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in context.items() if value is not None}

    def _visit_step(
        self,
        call: ParsedStepCall,
        *,
        nesting_depth: int,
        context: dict[str, Any],
    ) -> list[str]:
        if call.id not in self._manifest_node_ids:
            return []
        self.nodes[call.id] = {
            "kind": "step",
            "source_role": "step",
            "authored_id": call.id,
            "node_id": call.id,
            "component_ref": call.component_ref,
            "source_span": _span_dict(call.source_span),
            "nesting_depth": nesting_depth,
            **self._node_context_fields(context),
        }
        return [call.id]

    def _visit_subflow(
        self,
        call: ParsedSubflowCall,
        *,
        nesting_depth: int,
        context: dict[str, Any],
    ) -> list[str]:
        if call.id not in self._manifest_node_ids:
            return []
        self.nodes[call.id] = {
            "kind": "subflow",
            "source_role": "subflow",
            "authored_id": call.id,
            "node_id": call.id,
            "component_ref": call.component_ref,
            "manifest_hash": call.manifest_hash,
            "alias": call.alias,
            "source_span": _span_dict(call.source_span),
            "nesting_depth": nesting_depth,
            **self._node_context_fields(context),
        }
        return [call.id]

    def _visit_branch(
        self,
        block: ParsedBranchBlock,
        *,
        nesting_depth: int,
        context: dict[str, Any],
    ) -> list[str]:
        branch_id = f"branch-on-{block.decision_output}"
        branch_node_ids: list[str] = []
        arms: list[dict[str, Any]] = []
        for arm_index, arm in enumerate(block.arms):
            arm_id = f"{branch_id}-arm-{arm_index}"
            condition_literal = arm.condition.literal if arm.condition is not None else None
            arm_context = {
                **context,
                "branch_id": branch_id,
                "branch_arm_id": arm_id,
                "branch_decision_output": block.decision_output,
                "branch_condition_literal": condition_literal,
            }
            arm_node_ids = self.visit_block(
                arm.body,
                nesting_depth=nesting_depth + 1,
                context=arm_context,
            )
            branch_node_ids.extend(arm_node_ids)
            arms.append(
                {
                    "id": arm_id,
                    "index": arm_index,
                    "condition": {
                        "decision_output": arm.condition.decision_output,
                        "literal": arm.condition.literal,
                        "source_span": _span_dict(arm.condition.source_span),
                    }
                    if arm.condition is not None
                    else None,
                    "terminal": arm.terminal,
                    "source_span": _span_dict(arm.source_span),
                    "entry_node_id": arm_node_ids[0] if arm_node_ids else None,
                    "node_ids": arm_node_ids,
                    "nesting_depth": nesting_depth + 1,
                }
            )
        self.branches.append(
            {
                "id": branch_id,
                "decision_output": block.decision_output,
                "source_span": _span_dict(block.source_span),
                "node_ids": branch_node_ids,
                "arms": arms,
                "nesting_depth": nesting_depth,
            }
        )
        return branch_node_ids

    def _visit_loop(
        self,
        block: ParsedLoopBlock,
        *,
        nesting_depth: int,
        context: dict[str, Any],
    ) -> list[str]:
        policy = block.policy
        loop_context = {
            **context,
            "loop_id": policy.reentry_id,
            "loop_policy_ref": policy.policy_ref,
            "loop_reentry_id": policy.reentry_id,
        }
        body_node_ids = self.visit_block(
            block.body,
            nesting_depth=nesting_depth + 1,
            context=loop_context,
        )
        body_node_set = set(body_node_ids)
        exit_edges = [
            {
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "label": edge.label,
                "condition_ref": edge.condition_ref,
            }
            for edge in self._manifest.edges
            if edge.source in body_node_set and edge.target not in body_node_set
        ]
        self.loops.append(
            {
                "id": policy.reentry_id,
                "policy_ref": policy.policy_ref,
                "max_iterations": policy.max_iterations,
                "reentry_id": policy.reentry_id,
                "until_ref": policy.until_ref,
                "source_span": _span_dict(block.source_span),
                "entry_node_id": body_node_ids[0] if body_node_ids else None,
                "exit_node_ids": sorted({edge["source"] for edge in exit_edges}),
                "exit_edges": exit_edges,
                "body_node_ids": body_node_ids,
                "nesting_depth": nesting_depth,
            }
        )
        return body_node_ids


__all__ = ["build_source_topology"]
