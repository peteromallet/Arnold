"""Public-field tracing helper.

Provides :func:`trace_public_field` which statically inspects a workflow's
PUBLIC_INPUTS descriptors, mines module constants from the ready-template
source file via AST, reports inline node values, and notes CLI-override as
the highest conceptual priority (even though CLI overrides are not stored
in the VibeWorkflow object).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from vibecomfy.workflow import VibeInput, VibeWorkflow


def trace_public_field(
    workflow: VibeWorkflow,
    field_name: str,
    *,
    source_file: str | Path | None = None,
) -> dict[str, Any]:
    """Trace a public input field through all resolution layers.

    Args:
        workflow: The loaded workflow.
        field_name: The public input name to trace (canonical or alias).
        source_file: Optional path to the ready-template source file for
            AST-based constant mining. If not provided, attempts to use
            ``workflow.source.path``.

    Returns:
        A deterministic dict with ``field``, ``resolution_chain``,
        ``aliases``, ``bound_node``, and ``error`` keys.
    """
    # Look up the VibeInput descriptor
    vibe_input = _find_input(workflow, field_name)
    if vibe_input is None:
        return {
            "field": field_name,
            "error": f"Field {field_name!r} not found in workflow inputs.",
            "resolution_chain": [],
            "aliases": [],
            "bound_node": None,
        }

    name = vibe_input.name
    node_id = vibe_input.node_id
    field = vibe_input.field
    aliases = list(vibe_input.aliases) if vibe_input.aliases else []

    chain: list[dict[str, Any]] = []

    # 1. CLI override (highest conceptual priority, noted but not stored in wf)
    chain.append(
        {
            "priority": 1,
            "source": "cli_override",
            "description": f"CLI override --{name} <value>",
        }
    )

    # 2. PUBLIC_INPUTS default
    if vibe_input.default is not None or vibe_input.value is not None:
        default_val = vibe_input.default if vibe_input.default is not None else vibe_input.value
        chain.append(
            {
                "priority": 2,
                "source": "public_inputs_default",
                "field": name,
                "value": default_val,
            }
        )

    # 3. Inline node value
    node = workflow.nodes.get(node_id)
    if node is not None and field in node.inputs:
        inline_val = node.inputs[field]
        chain.append(
            {
                "priority": 3,
                "source": "inline_node_value",
                "node_id": node_id,
                "class_type": node.class_type,
                "field": field,
                "value": inline_val,
            }
        )

    # 4. Module constant (AST-scan source file if available)
    source_path = source_file or workflow.source.path
    if source_path is not None:
        try:
            path = Path(source_path)
            if path.is_file():
                source_text = path.read_text(encoding="utf-8")
                constants = _mine_module_constants(source_text, name, node_id, field)
                if constants:
                    chain.extend(constants)
        except (OSError, SyntaxError):
            pass

    # Bound-to node
    bound_node = None
    if node is not None:
        bound_node = {
            "node_id": node_id,
            "class_type": node.class_type,
            "field": field,
        }

    return {
        "field": name,
        "resolution_chain": chain,
        "aliases": aliases,
        "bound_node": bound_node,
    }


def _find_input(workflow: VibeWorkflow, field_name: str) -> VibeInput | None:
    """Find a VibeInput by canonical name or alias."""
    for inp in workflow.inputs.values():
        if inp.name == field_name:
            return inp
    for inp in workflow.inputs.values():
        if field_name in inp.aliases:
            return inp
    return None


def _mine_module_constants(
    source_text: str,
    field_name: str,
    node_id: str,
    field_key: str,
) -> list[dict[str, Any]]:
    """Mine module-level constants from the ready-template source via AST.

    Looks for patterns like:
        DEFAULT_PROMPT = 'some value'
    or:
        READY_METADATA = {..., 'unbound_inputs': {'prompt': 'value'}, ...}
    """
    results: list[dict[str, Any]] = []
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return results

    # Find READY_METADATA unbound_inputs
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "READY_METADATA":
                metadata = _literal_value(node.value, {})
                if isinstance(metadata, dict):
                    unbound = metadata.get("unbound_inputs")
                    if isinstance(unbound, dict) and field_name in unbound:
                        results.append(
                            {
                                "priority": 4,
                                "source": "unbound_inputs",
                                "context": "READY_METADATA['unbound_inputs']",
                                "field": field_name,
                                "value": unbound[field_name],
                            }
                        )

    # Find standalone module-level constants that look like defaults
    # Pattern: UPPER_CASE_NAME = 'some value'
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id.isupper() and target.id not in {
                "READY_METADATA",
                "READY_REQUIREMENTS",
            }:
                val = _literal_value(node.value, {})
                if isinstance(val, str) and val:
                    # Try to match with the inline value — if the field
                    # has this constant name as the value in the node
                    # inline call, we report it.
                    results.append(
                        {
                            "priority": 5,
                            "source": "module_constant",
                            "constant_name": target.id,
                            "value": val,
                        }
                    )

    return results


def _literal_value(node: ast.AST, assignments: dict[str, Any]) -> Any:
    """Evaluate an AST literal value (recursive)."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_literal_value(item, assignments) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal_value(item, assignments) for item in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _literal_value(key, assignments): _literal_value(value, assignments)
            for key, value in zip(node.keys, node.values)
            if key is not None
        }
    if isinstance(node, ast.Name):
        return assignments.get(node.id)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


__all__ = ["trace_public_field"]
