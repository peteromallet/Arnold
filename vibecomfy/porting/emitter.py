from __future__ import annotations

import keyword
import pprint
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from vibecomfy.porting.widget_aliases import resolve_widget_name
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

# -- readability warning codes ------------------------------------------------
READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT = "avoidable_positional_output"
READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY = "output_name_ambiguity"
READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED = "schema_backed_widget_alias_not_resolved"
READABILITY_WARNING_HIDDEN_MODEL_FILENAME = "hidden_model_filename"

READABILITY_WARNING_CODES: frozenset[str] = frozenset(
    {
        READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
        READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
        READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
        READABILITY_WARNING_HIDDEN_MODEL_FILENAME,
    }
)

EmissionSeverity = Literal["error", "warning", "info"]


@dataclass(slots=True)
class EmissionDiagnostic:
    """A readability diagnostic recorded during emission.

    These are always *warnings* (or info) - hard errors are surfaced through
    `PortConvertValidation` parity / schema failures, not here.
    """

    code: str
    message: str
    severity: EmissionSeverity = "warning"
    node_id: str | None = None
    class_type: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


GENERATED_HEADER = (
    "# vibecomfy: generated - converted by tools/convert_ready_templates.py\n"
    "# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`\n"
    "# marker on the first line if hand-editing is required.\n"
)

UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})

LTX2_3_TAIL_PATCHES: tuple[str, ...] = (
    "from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram",
    "from vibecomfy.patches.requirements import ensure_custom_nodes",
    "from vibecomfy.patches.resolution import resolution",
)


def emit_ready_template_python(
    workflow,
    *,
    ready_metadata: dict[str, Any],
    ready_requirements: dict[str, Any],
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
) -> str:
    metadata = dict(ready_metadata)
    requirements = dict(ready_requirements)
    if apply_overrides:
        for key, value in (apply_overrides.get("metadata_overrides") or {}).items():
            metadata[key] = value

    prepared = _prepare_workflow_for_emit(workflow, apply_overrides=apply_overrides)
    has_ltx_tail = _has_ltx_lowvram_tail(template_id)

    out_lines: list[str] = []
    out_lines.append(GENERATED_HEADER.rstrip("\n"))
    out_lines.append('"""Auto-generated ready_template - see tools/convert_ready_templates.py."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append("from vibecomfy.workflow import VibeWorkflow, WorkflowSource")
    out_lines.append("from vibecomfy.registry.ready_template import apply_ready_template_policy")
    if has_ltx_tail:
        out_lines.extend(LTX2_3_TAIL_PATCHES)
    out_lines.append("")
    out_lines.append("")
    out_lines.append(_format_metadata_dict("READY_METADATA", metadata))
    out_lines.append("")
    out_lines.append(_format_metadata_dict("READY_REQUIREMENTS", requirements))
    out_lines.append("")
    out_lines.append("")
    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr='READY_METADATA["ready_template"]',
            source_path_expr="__file__",
            source_type="ready_template",
            source_provenance=metadata.get("provenance") if isinstance(metadata.get("provenance"), dict) else None,
            registered_inputs=registered_inputs,
            tail_lines=_ready_template_tail_lines(has_ltx_tail),
            diagnostics=diagnostics,
        )
    )
    out_lines.append("")
    out_lines.append(_NODE_HELPER_SOURCE)
    return "\n".join(out_lines) + "\n"


def emit_scratchpad_python(
    workflow,
    *,
    workflow_id: str | None = None,
    source_path: str | None = None,
    provenance: dict[str, Any] | None = None,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
) -> str:
    workflow_id = workflow_id or getattr(workflow, "id", "scratchpad")
    prepared = _prepare_workflow_for_emit(workflow, apply_overrides=apply_overrides)
    source_path_expr = repr(source_path) if source_path is not None else "__file__"

    out_lines: list[str] = []
    out_lines.append("# vibecomfy: generated scratchpad")
    out_lines.append('"""Auto-generated VibeComfy scratchpad."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append("from vibecomfy.workflow import VibeWorkflow, WorkflowSource")
    out_lines.append("")
    out_lines.append("")
    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr=repr(workflow_id),
            source_path_expr=source_path_expr,
            source_type="scratchpad",
            source_provenance=provenance or {},
            registered_inputs=registered_inputs,
            tail_lines=["    wf.finalize_metadata()"],
            diagnostics=diagnostics,
        )
    )
    out_lines.append("")
    out_lines.append(_NODE_HELPER_SOURCE)
    return "\n".join(out_lines) + "\n"


def _prepare_workflow_for_emit(workflow: Any, *, apply_overrides: dict[str, Any] | None) -> dict[str, Any]:
    workflow_nodes = {
        nid: node
        for nid, node in workflow.nodes.items()
        if node.class_type not in UI_ONLY_CLASS_TYPES
    }
    edges_in: dict[str, list[Any]] = {}
    for edge in workflow.edges:
        if edge.from_node not in workflow_nodes or edge.to_node not in workflow_nodes:
            continue
        edges_in.setdefault(edge.to_node, []).append(edge)

    if apply_overrides:
        _apply_overrides(workflow_nodes, edges_in, apply_overrides.get("patches") or [])

    from vibecomfy.workflow import VibeEdge as _Edge

    extracted_edges_for_naming: list[Any] = []
    for nid, node in workflow_nodes.items():
        for key, value in {**node.inputs, **node.widgets}.items():
            if _is_link(value):
                extracted_edges_for_naming.append(_Edge(str(value[0]), str(value[1]), str(nid), key))

    var_names = _compute_variable_names(
        workflow_nodes,
        [edge for edges in edges_in.values() for edge in edges] + extracted_edges_for_naming,
    )
    return {"nodes": workflow_nodes, "edges_in": edges_in, "var_names": var_names}


def _emit_build_function(
    prepared: dict[str, Any],
    *,
    workflow_id_expr: str,
    source_path_expr: str,
    source_type: str,
    source_provenance: dict[str, Any] | None,
    registered_inputs: dict[str, tuple[str, str]] | None,
    tail_lines: list[str],
    diagnostics: list[EmissionDiagnostic] | None = None,
) -> list[str]:
    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    var_names = prepared["var_names"]

    out_lines: list[str] = []
    out_lines.append("def build() -> VibeWorkflow:")
    out_lines.append('    """Build the workflow (auto-generated)."""')
    provenance_part = ""
    if source_provenance is not None:
        provenance_part = f",\n            provenance={_format_value(source_provenance)}"
    out_lines.append(
        "    wf = VibeWorkflow(\n"
        f"        {workflow_id_expr},\n"
        "        WorkflowSource(\n"
        f"            id={workflow_id_expr},\n"
        f"            path={source_path_expr},\n"
        f"            source_type={source_type!r}"
        f"{provenance_part},\n"
        "        ),\n"
        "    )"
    )
    out_lines.append("")

    for nid in _topological_node_order(workflow_nodes, edges_in):
        node = workflow_nodes[nid]
        var = var_names[nid]
        kwargs = _node_kwargs(node, edges_in, var_names, workflow_nodes=workflow_nodes, diagnostics=diagnostics)

        head = f"    {var} = _node(wf, {node.class_type!r}, {nid!r}"
        if not kwargs:
            out_lines.append(f"{head})")
        else:
            out_lines.append(f"{head},")
            for key, expr in kwargs:
                out_lines.append(f"        {key}={expr},")
            out_lines.append("    )")

    out_lines.append("")
    out_lines.extend(tail_lines)
    if registered_inputs:
        for input_name, (old_id, field) in registered_inputs.items():
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
    return out_lines


def _ready_template_tail_lines(has_ltx_tail: bool) -> list[str]:
    if has_ltx_tail:
        return [
            "    apply_ltx_lowvram(wf)",
            "    resolution(384, 256, 9).apply(wf)",
            "    ensure_custom_nodes(wf, READY_REQUIREMENTS[\"custom_nodes\"])",
            "    wf.finalize_metadata()",
            "    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)",
        ]
    return [
        "    wf.finalize_metadata()",
        "    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)",
    ]


def _is_link(value: Any) -> bool:
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    return all(part.isdigit() for part in str(nid).split(":"))


def _safe_var(class_type: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", class_type.lower())
    if not name or name[0].isdigit():
        name = f"n_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def _connection_role_name(workflow_nodes: dict[str, Any], edges_out: dict[str, list[tuple[str, str]]]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for src_node_id, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        for to_node, to_input in edges_out.get(src_node_id, []):
            target = workflow_nodes.get(to_node)
            if target is None:
                continue
            if target.class_type == "KSampler" and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
            if target.class_type in ("CFGGuider", "MultimodalGuider") and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
    return roles


def _empty_text_role(workflow_nodes: dict[str, Any]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for nid, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        text_value = node.inputs.get("text", node.widgets.get("text", node.widgets.get("widget_0")))
        if isinstance(text_value, str) and text_value.strip() == "":
            roles.setdefault(nid, "negative")
    return roles


def _id_sort_key(nid: str) -> tuple[Any, ...]:
    parts = str(nid).split(":")
    if all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts)
    return (1 << 31, str(nid))


def _topological_node_order(nodes: dict[str, Any], edges_in: dict[str, list[Any]]) -> list[str]:
    deps: dict[str, set[str]] = {nid: set() for nid in nodes}
    for nid, node in nodes.items():
        for edge in edges_in.get(nid, []):
            if edge.from_node in nodes:
                deps[nid].add(edge.from_node)
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if _is_link(value):
                src = str(value[0])
                if src in nodes:
                    deps[nid].add(src)

    pending = set(nodes.keys())
    out: list[str] = []
    while pending:
        ready = sorted((nid for nid in pending if not (deps[nid] - set(out))), key=_id_sort_key)
        if not ready:
            out.extend(sorted(pending, key=_id_sort_key))
            break
        for nid in ready:
            out.append(nid)
            pending.discard(nid)
    return out


def _format_value(value: Any) -> str:
    return repr(value)


def _compute_variable_names(workflow_nodes: dict[str, Any], edges: list[Any]) -> dict[str, str]:
    edges_out: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        edges_out.setdefault(edge.from_node, []).append((edge.to_node, edge.to_input))

    role_conn = _connection_role_name(workflow_nodes, edges_out)
    role_empty = _empty_text_role(workflow_nodes)
    sorted_ids = sorted(workflow_nodes.keys(), key=_id_sort_key)

    used: dict[str, int] = {}
    var_names: dict[str, str] = {}
    for nid in sorted_ids:
        node = workflow_nodes[nid]
        base = role_conn.get(nid) or role_empty.get(nid) or _safe_var(node.class_type)
        used[base] = used.get(base, 0) + 1
        var_names[nid] = base if used[base] == 1 else f"{base}_{used[base]}"
    return var_names


def _node_kwargs(
    node: Any,
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    *,
    workflow_nodes: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
) -> list[tuple[str, str]]:
    cls = node.class_type
    schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
    schema_set = set(schema)

    # Per-node widget alias metadata populated by the schema provider during
    # convert_to_vibe_format.  Prefer this over the static WIDGET_SCHEMA so
    # that schema-source evidence wins - the static table is only a fallback.
    node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
    input_aliases: list[str | None] | None = node_metadata.get("input_aliases")

    incoming: dict[str, tuple[str, int]] = {}
    for edge in edges_in.get(node.id, []):
        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))

    def _translate_widget(key: str) -> str | None:
        if not key.startswith("widget_"):
            return key
        try:
            idx = int(key.split("_", 1)[1])
        except ValueError:
            return key
        # 1. Per-node schema-source evidence (input_aliases from provider).
        if isinstance(input_aliases, (list, tuple)) and 0 <= idx < len(input_aliases):
            alias = input_aliases[idx]
            if alias is not None:
                return alias
            # None -> UI-only widget, drop it.
            return None
        # 2. Static WIDGET_SCHEMA fallback (lowest priority).
        return resolve_widget_name(cls, idx)

    raw_inputs: dict[str, Any] = {}
    for key, value in node.inputs.items():
        if _is_link(value):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            raw_inputs[key] = value
    for key, value in node.widgets.items():
        if _is_link(value):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        elif key not in raw_inputs:
            raw_inputs[key] = value

    static_inputs: dict[str, Any] = {}
    for key, value in raw_inputs.items():
        translated = _translate_widget(key)
        if translated is None:
            continue
        if translated != key and translated not in raw_inputs and translated not in static_inputs and translated not in incoming:
            static_inputs[translated] = value
        else:
            static_inputs[key] = value

    if schema:
        ordered_static_keys = [key for key in schema if key in static_inputs]
        ordered_static_keys += sorted(key for key in static_inputs if key not in schema_set)
    else:
        ordered_static_keys = sorted(static_inputs.keys())

    def _is_python_ident(name: str) -> bool:
        return name.isidentifier() and not keyword.iskeyword(name)

    out: list[tuple[str, str]] = []
    extras: list[tuple[str, str]] = []
    output_names = _node_output_names(node)
    if output_names:
        out.append(("_outputs", _format_value(tuple(output_names))))
    for key in ordered_static_keys:
        if key in incoming:
            continue
        if not _is_python_ident(key):
            extras.append((key, _format_value(static_inputs[key])))
            continue
        out.append((key, _format_value(static_inputs[key])))

    if schema:
        ordered_incoming = [key for key in schema if key in incoming]
        ordered_incoming += sorted(key for key in incoming if key not in schema_set)
    else:
        ordered_incoming = sorted(incoming.keys())

    for to_input in ordered_incoming:
        from_node, from_slot = incoming[to_input]
        from_node_str = str(from_node)
        if from_node_str in var_names:
            safe_name = _safe_output_name(workflow_nodes, from_node_str, from_slot)
            if safe_name is not None:
                expr = f"{var_names[from_node_str]}.out({safe_name!r})"
            else:
                expr = f"{var_names[from_node_str]}.out({from_slot})"
                if diagnostics is not None and workflow_nodes is not None:
                    _output_fallback_diagnostic(
                        diagnostics, workflow_nodes, from_node_str, from_slot,
                        target_node=node, target_input=to_input,
                    )
        else:
            expr = f"[{from_node_str!r}, {from_slot}]"
        if not _is_python_ident(to_input):
            extras.append((to_input, expr))
            continue
        out.append((to_input, expr))

    # -- readability diagnostics: positional output detection ------------
    if diagnostics is not None:
        emit_diags = _collect_emission_diagnostics(node, output_names, incoming, var_names)
        diagnostics.extend(emit_diags)

    if extras:
        extras_repr = "{" + ", ".join(f"{key!r}: {value}" for key, value in extras) + "}"
        out.append(("_extras", extras_repr))
    return out


def _collect_emission_diagnostics(
    node: Any,
    output_names: list[str],
    incoming: dict[str, tuple[str, int]],
    var_names: dict[str, str],
) -> list[EmissionDiagnostic]:
    """Collect readability diagnostics for a single node during emission.

    This is called from `_node_kwargs` when a diagnostics collector is
    provided.  Currently flags:

    * **avoidable_positional_output** - the node has output names available
      (from schema metadata) but the emitter is using numeric `.out(n)`
      because one or more names are unsafe (blank, duplicate, conflicted).

    * **output_name_ambiguity** - output name is duplicated within the
      same node, forcing a numeric fallback.

    * **schema_backed_widget_alias_not_resolved** - one or more
      `widget_N` keys remain positional because no alias mapping could
      be resolved from schema / widget table evidence.
    """
    diags: list[EmissionDiagnostic] = []
    nid = getattr(node, "id", None)
    ctype = getattr(node, "class_type", None)
    metadata = getattr(node, "metadata", {}) or {}
    node_input_aliases = metadata.get("input_aliases")

    # 1. avoidable_positional_output / output_name_ambiguity
    if output_names:
        safe_names: set[str] = set()
        has_unsafe = False
        has_duplicate = False
        seen: set[str] = set()
        for name in output_names:
            if not name:
                has_unsafe = True
            elif name in seen:
                has_unsafe = True
                has_duplicate = True
            else:
                seen.add(name)
                safe_names.add(name)
        if has_unsafe:
            if has_duplicate:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
                        message=f"Node {nid} ({ctype}) has duplicate output names; falling back to numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
            else:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
                        message=f"Node {nid} ({ctype}) has partial/blank output names; some outputs use numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
    else:
        # No output names at all - check if schema has input_aliases available
        if not node_input_aliases:
            # Check if there are widget_N keys that could be aliased
            widget_keys = [
                k for k in getattr(node, "widgets", {}).keys()
                if k.startswith("widget_")
            ] + [
                k for k in getattr(node, "inputs", {}).keys()
                if k.startswith("widget_")
            ]
            if widget_keys:
                schema_source = metadata.get("schema_source")
                schema_available = schema_source is not None
                if schema_available:
                    diags.append(
                        EmissionDiagnostic(
                            code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                            message=f"Node {nid} ({ctype}) has {len(set(widget_keys))} unresolved widget_N keys despite schema being available.",
                            severity="warning",
                            node_id=str(nid) if nid is not None else None,
                            class_type=ctype,
                            detail={
                                "widget_keys": list(set(widget_keys)),
                                "schema_source": schema_source,
                            },
                        )
                    )

    # 3. schema_backed_widget_alias_not_resolved - when widget_N keys remain
    #    positional even though input_aliases could potentially cover them, or
    #    when the fallback to static WIDGET_SCHEMA was used.
    if node_input_aliases:
        # We have input_aliases - check if any widget_N index falls outside
        # the aliases list, forcing a fallback.
        widget_indices: list[int] = []
        for k in list(getattr(node, "widgets", {}).keys()) + list(getattr(node, "inputs", {}).keys()):
            if k.startswith("widget_"):
                try:
                    widget_indices.append(int(k.split("_", 1)[1]))
                except ValueError:
                    pass
        if widget_indices:
            max_idx = max(widget_indices)
            if max_idx >= len(node_input_aliases):
                unresolved = [
                    f"widget_{i}" for i in widget_indices
                    if i >= len(node_input_aliases)
                ]
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                        message=(
                            f"Node {nid} ({ctype}) has {len(unresolved)} widget_N key(s) "
                            f"({', '.join(unresolved)}) outside input_aliases range "
                            f"(len={len(node_input_aliases)}); keeping positional."
                        ),
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={
                            "unresolved_widgets": unresolved,
                            "input_aliases_length": len(node_input_aliases),
                        },
                    )
                )

    return diags


def _node_output_names(node: Any) -> list[str]:
    """Return output names for `_outputs` emission, preserving partial evidence.

    Unlike the old all-truthy gate, this always returns the full list from
    metadata so that `_outputs` is emitted even when some names are blank.
    The per-slot safety decision for `.out('name')` is made separately by
    `_safe_output_name` during incoming edge formatting.
    """
    output_names = getattr(node, "metadata", {}).get("output_names")
    if not isinstance(output_names, (list, tuple)):
        return []
    result: list[str] = []
    for name in output_names:
        if isinstance(name, str) and name:
            result.append(name)
        else:
            result.append("")
    return result


def _safe_output_name(
    workflow_nodes: dict[str, Any] | None,
    from_node: str,
    from_slot: int,
) -> str | None:
    """Return the safe output name for a slot, or `None` if numeric fallback is needed.

    A name is *safe* for `.out('name')` when all of these hold:

    * *slot in range:* `from_slot` is a valid index into the source node's
      `output_names` metadata list.
    * *name non-empty:* the name at that index is a non-blank string.
    * *name unique:* the name appears exactly once in the source node's
      `output_names` list (no duplicates).
    * *name not conflicted:* the source node's metadata does not list the name
      in a `conflicted_outputs` key.
    """
    if workflow_nodes is None:
        return None
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return None
    output_names = getattr(src_node, "metadata", {}).get("output_names")
    if not isinstance(output_names, (list, tuple)):
        return None
    if from_slot < 0 or from_slot >= len(output_names):
        return None
    name = output_names[from_slot]
    if not isinstance(name, str) or not name:
        return None
    # Duplicate check: the name must appear exactly once.
    if list(output_names).count(name) > 1:
        return None
    # Conflicted check: the name must not be in the conflicted_outputs list.
    conflicted = getattr(src_node, "metadata", {}).get("conflicted_outputs")
    if isinstance(conflicted, (list, tuple, set, frozenset)) and name in conflicted:
        return None
    return name


def _output_fallback_diagnostic(
    diagnostics: list[EmissionDiagnostic],
    workflow_nodes: dict[str, Any],
    from_node: str,
    from_slot: int,
    *,
    target_node: Any,
    target_input: str,
) -> None:
    """Record a diagnostic explaining why `.out(n)` was used instead of `.out('name')`.

    Only fires when the source node *has* output_names metadata - otherwise
    numeric fallback is expected and not an avoidable concern.
    """
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return

    output_names = getattr(src_node, "metadata", {}).get("output_names")
    # If the source node has no output_names metadata at all, numeric fallback
    # is the only option - no diagnostic warranted.
    if not isinstance(output_names, (list, tuple)):
        return

    src_ctype = getattr(src_node, "class_type", None)
    tgt_nid = getattr(target_node, "id", None)
    tgt_ctype = getattr(target_node, "class_type", None)

    reason_parts: list[str] = []
    if from_slot < 0 or from_slot >= len(output_names):
        reason_parts.append(
            f"slot {from_slot} out of range (source has {len(output_names)} output(s))"
        )
    else:
        name = output_names[from_slot]
        if not isinstance(name, str) or not name:
            reason_parts.append(f"output_names[{from_slot}] is blank")
        elif list(output_names).count(name) > 1:
            reason_parts.append(
                f"output_names[{from_slot}]={name!r} is duplicated in source output_names"
            )
        else:
            conflicted = getattr(src_node, "metadata", {}).get("conflicted_outputs")
            if isinstance(conflicted, (list, tuple, set, frozenset)) and name in conflicted:
                reason_parts.append(
                    f"output_names[{from_slot}]={name!r} is marked conflicted"
                )
            else:
                # Should not reach here - _safe_output_name would have succeeded.
                # Log it anyway as a safety net.
                reason_parts.append(
                    f"output_names[{from_slot}]={name!r} is not safe for named emission"
                )

    reason = "; ".join(reason_parts)
    diagnostics.append(
        EmissionDiagnostic(
            code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
            message=(
                f"Edge from {from_node} ({src_ctype}).out({from_slot}) to "
                f"{tgt_nid} ({tgt_ctype}).{target_input} uses numeric .out({from_slot}) "
                f"because: {reason}"
            ),
            severity="warning",
            node_id=str(tgt_nid) if tgt_nid is not None else None,
            class_type=tgt_ctype,
            detail={
                "from_node": from_node,
                "from_slot": from_slot,
                "target_input": target_input,
                "reason": reason,
                "output_names": list(output_names),
            },
        )
    )


def _format_metadata_dict(name: str, value: dict[str, Any]) -> str:
    formatted = pprint.pformat(value, width=110, sort_dicts=False)
    return f"{name} = {formatted}"


def _has_ltx_lowvram_tail(category_id: str) -> bool:
    return category_id.startswith("video/ltx2_3_t2v") or category_id.startswith("video/ltx2_3_i2v")


def _apply_overrides(nodes: dict[str, Any], edges_in: dict[str, list[Any]], patches: list[dict[str, Any]]) -> None:
    for patch in patches:
        match = patch.get("match", {})
        target_ids: list[str] = []
        if "node_id" in match:
            target_ids = [str(match["node_id"])]
        elif "class_type" in match:
            class_target = match["class_type"]
            ordinal = match.get("node_index")
            matches = [nid for nid, node in nodes.items() if node.class_type == class_target]
            if ordinal is not None and 0 <= ordinal < len(matches):
                target_ids = [matches[ordinal]]
            else:
                target_ids = matches

        for tid in target_ids:
            node = nodes.get(tid)
            if node is None:
                continue
            for old, new in (patch.get("rename_inputs") or {}).items():
                if old in node.widgets:
                    node.widgets[new] = node.widgets.pop(old)
                if old in node.inputs:
                    node.inputs[new] = node.inputs.pop(old)
            for key, value in (patch.get("set_inputs") or {}).items():
                if key in node.widgets:
                    node.widgets[key] = value
                else:
                    node.inputs[key] = value
            for key in patch.get("remove_inputs") or []:
                node.widgets.pop(key, None)
                node.inputs.pop(key, None)


_NODE_HELPER_SOURCE = '''
def _node(
    wf: VibeWorkflow,
    class_type: str,
    _id: str,
    _extras: dict | None = None,
    _outputs: tuple[str, ...] | None = None,
    **kwargs,
):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _outputs is not None:
        builder.node.metadata["output_names"] = list(_outputs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
'''


__all__ = [
    "emit_ready_template_python",
    "emit_scratchpad_python",
    "EmissionDiagnostic",
    "EmissionSeverity",
    "READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT",
    "READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY",
    "READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED",
    "READABILITY_WARNING_HIDDEN_MODEL_FILENAME",
    "READABILITY_WARNING_CODES",
]
