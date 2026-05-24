"""Public facade for emitting ready-template Python from VibeWorkflow IR."""

from __future__ import annotations

from vibecomfy._graph_utils import UI_ONLY_CLASS_TYPES, is_api_link
from vibecomfy.porting.formatting import format_metadata_dict
from vibecomfy.porting.naming import compute_variable_names, topological_node_order
from vibecomfy.porting.node_kwargs import apply_overrides as apply_override_patches
from vibecomfy.porting.node_kwargs import node_kwargs
from vibecomfy.porting.templates import (
    GENERATED_HEADER,
    LTX2_3_TAIL_PATCHES,
    NODE_HELPER_SOURCE,
    has_ltx_lowvram_tail,
)
from vibecomfy.porting.widget_schema import resolve_widget_name


def format_as_python(
    workflow,
    *,
    ready_metadata: dict,
    ready_requirements: dict,
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict | None = None,
) -> str:
    """Emit the converted Python module text for the given VibeWorkflow."""
    ready_metadata = dict(ready_metadata)
    ready_requirements = dict(ready_requirements)

    # Apply override "metadata_overrides" before stringifying.
    if apply_overrides:
        for key, value in (apply_overrides.get("metadata_overrides") or {}).items():
            ready_metadata[key] = value

    # Strip UI-only nodes (Reroute / Note / etc.) -- they should never reach the runtime.
    workflow_nodes = {
        nid: node
        for nid, node in workflow.nodes.items()
        if node.class_type not in UI_ONLY_CLASS_TYPES
    }
    edges_in: dict[str, list] = {}
    for edge in workflow.edges:
        # Drop edges that touch a stripped UI node.
        if edge.from_node not in workflow_nodes or edge.to_node not in workflow_nodes:
            continue
        edges_in.setdefault(edge.to_node, []).append(edge)

    # Apply override patches at IR level before var-naming.
    if apply_overrides:
        apply_override_patches(workflow_nodes, edges_in, apply_overrides.get("patches") or [])

    # Also detect dotted-id link values still in node.inputs for var-name heuristics.
    extracted_edges_for_naming: list = []
    from vibecomfy.workflow import VibeEdge as _Edge
    for nid, node in workflow_nodes.items():
        for key, value in {**node.inputs, **node.widgets}.items():
            if is_api_link(
                value,
                allow_tuple=False,
                require_string_node_id=True,
                require_numeric_node_id=True,
                allow_compound_node_id=True,
                require_int_slot=True,
            ):
                extracted_edges_for_naming.append(
                    _Edge(str(value[0]), str(value[1]), str(nid), key)
                )

    var_names = compute_variable_names(
        workflow_nodes,
        [e for es in edges_in.values() for e in es] + extracted_edges_for_naming,
    )

    has_ltx_tail = has_ltx_lowvram_tail(template_id)

    # ---- emit ---------------------------------------------------------------
    out_lines: list[str] = []
    out_lines.append(GENERATED_HEADER.rstrip("\n"))
    out_lines.append('"""Auto-generated ready_template — see tools/convert_ready_templates.py."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append("from vibecomfy.workflow import VibeWorkflow, WorkflowSource")
    out_lines.append(
        "from vibecomfy.registry.ready_template import apply_ready_template_policy"
    )
    if has_ltx_tail:
        for line in LTX2_3_TAIL_PATCHES:
            out_lines.append(line)
    out_lines.append("")
    out_lines.append("")
    out_lines.append(format_metadata_dict("READY_METADATA", ready_metadata))
    out_lines.append("")
    out_lines.append(format_metadata_dict("READY_REQUIREMENTS", ready_requirements))
    out_lines.append("")
    out_lines.append("")

    # build()
    out_lines.append("def build() -> VibeWorkflow:")
    out_lines.append('    """Build the workflow (auto-generated)."""')
    out_lines.append(
        "    wf = VibeWorkflow(\n"
        "        READY_METADATA[\"ready_template\"],\n"
        "        WorkflowSource(\n"
        "            id=READY_METADATA[\"ready_template\"],\n"
        "            path=__file__,\n"
        "            source_type=\"ready_template\",\n"
        "        ),\n"
        "    )"
    )
    out_lines.append("")

    # Topologically sort so producers come before consumers. Tie-break on
    # numeric-id ascending for stable, readable output. Cycles are tolerated
    # (they shouldn't exist) by emitting the remainder in id-sorted order.
    sorted_ids = topological_node_order(workflow_nodes, edges_in)

    for nid in sorted_ids:
        node = workflow_nodes[nid]
        var = var_names[nid]
        kwargs = node_kwargs(node, edges_in, var_names)

        head = f"    {var} = _node(wf, {node.class_type!r}, {nid!r}"
        if not kwargs:
            out_lines.append(f"{head})")
        else:
            out_lines.append(f"{head},")
            for i, (k, expr) in enumerate(kwargs):
                terminator = "," if i < len(kwargs) - 1 else ","
                out_lines.append(f"        {k}={expr}{terminator}")
            out_lines.append("    )")

    out_lines.append("")
    if has_ltx_tail:
        out_lines.append("    apply_ltx_lowvram(wf)")
        out_lines.append("    resolution(384, 256, 9).apply(wf)")
        out_lines.append("    ensure_custom_nodes(wf, READY_REQUIREMENTS[\"custom_nodes\"])")
        out_lines.append("    wf.finalize_metadata()")
    else:
        out_lines.append("    wf.finalize_metadata()")
    out_lines.append(
        "    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, "
        "requirements=READY_REQUIREMENTS)"
    )

    if registered_inputs:
        for input_name, (old_id, field) in registered_inputs.items():
            # Translate widget_X -> schema-resolved name when possible.
            resolved_field = field
            if field.startswith("widget_") and old_id in workflow_nodes:
                cls = workflow_nodes[old_id].class_type
                try:
                    idx = int(field.split("_", 1)[1])
                    resolved_field = resolve_widget_name(cls, idx)
                except (ValueError, IndexError):
                    pass
            out_lines.append(
                f"    wf.register_input({input_name!r}, {old_id!r}, {resolved_field!r}, "
                f"wf.nodes[{old_id!r}].inputs.get({resolved_field!r}, wf.nodes[{old_id!r}].widgets.get({resolved_field!r})))"
            )

    out_lines.append("    return wf")
    out_lines.append("")

    # Helper at module bottom for explicit-id node creation.
    out_lines.append(NODE_HELPER_SOURCE)
    return "\n".join(out_lines) + "\n"


__all__ = ["format_as_python"]
