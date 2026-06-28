from __future__ import annotations

from typing import Any

from .ledger import EditLedger
from .ops import AddNodeOp, AnchorRef, ReorderOp
from vibecomfy.porting.edit.apply_place import _group_index_by_title
from vibecomfy.porting.edit.apply_resolve_base import _resolve_node, _resolve_scope, _resolve_source_endpoint
from vibecomfy.porting.edit.apply_slots import _linked_widget_names, _reorder_names
from vibecomfy.porting.edit.apply_types import ResolvedAddNodeSpec, ResolvedLinkEndpoint, ResolvedNodeRef, ResolvedOp, _issue
from vibecomfy.porting.edit.apply_values import _validate_literal_value
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import _normalize_type
from vibecomfy.schema import schema_for, socket_types_compatible


def _resolve_add_node(
    ledger: EditLedger,
    op: AddNodeOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    scope, issues = _resolve_scope(ledger, op.scope_path)
    if issues:
        return None, issues
    assert scope is not None

    schema = schema_for(schema_provider, op.class_type)
    if schema is None:
        return None, [
            _issue(
                "unknown_add_node_class_type",
                f"Unknown class_type {op.class_type!r} for add_node.",
                detail={"scope_path": op.scope_path, "class_type": op.class_type},
            )
        ]

    schema_inputs = getattr(schema, "inputs", {}) or {}
    issues = []
    for input_name, spec in schema_inputs.items():
        required = bool(getattr(spec, "required", False))
        default = getattr(spec, "default", None)
        if required and input_name not in op.fields and input_name not in op.inputs and default is None:
            issues.append(
                _issue(
                    "missing_required_add_node_input",
                    f"{op.class_type} requires input {input_name!r} for add_node.",
                    # Per the v2 spec, required-input completeness is a queue-validate
                    # WARNING, not a fidelity failure: adding a node and wiring it in a
                    # later step (or after manual review) is a legitimate flow. Surfacing
                    # this as a hard error blocked the natural "add a node, then connect
                    # it" pattern. The node is still added; queue-validate flags the gap.
                    severity="warning",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "input": input_name},
                )
            )
    for field_name, value in op.fields.items():
        spec = schema_inputs.get(field_name)
        if spec is None:
            issues.append(
                _issue(
                    "unknown_add_node_field",
                    f"{op.class_type} does not declare field {field_name!r}.",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "field": field_name},
                )
            )
            continue
        issues.extend(
            _validate_literal_value(
                value=value,
                spec=spec,
                class_type=op.class_type,
                input_name=field_name,
                context="add_node",
            )
        )
    # Block only on errors; carry warnings (e.g. missing required input) forward so the
    # node is still added and the gap surfaces as a non-blocking queue-validate warning.
    if any(issue.severity == "error" for issue in issues):
        return None, issues

    resolved_inputs: dict[str, ResolvedLinkEndpoint] = {}
    for input_name, source in op.inputs.items():
        if source.scope_path != op.scope_path:
            return None, [
                _issue(
                    "cross_scope_link_unsupported",
                    "add_node input endpoints must resolve within the same scope.",
                    detail={
                        "from_scope_path": source.scope_path,
                        "to_scope_path": op.scope_path,
                        "to_class_type": op.class_type,
                        "to_input": input_name,
                    },
                )
            ]
        spec = schema_inputs.get(input_name)
        if spec is None:
            return None, [
                _issue(
                    "unknown_add_node_input",
                    f"{op.class_type} does not declare input {input_name!r}.",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "input": input_name},
                )
            ]
        source_ref, source_issues = _resolve_source_endpoint(ledger, source, schema_provider=schema_provider)
        if source_issues:
            return None, source_issues
        assert source_ref is not None
        if not isinstance(source_ref.node_id, int):
            return None, [
                _issue(
                    "non_numeric_link_endpoint",
                    "add_node input sources must have numeric LiteGraph node ids.",
                    detail={
                        "from_scope_path": source.scope_path,
                        "from_uid": source.uid,
                        "from_node_id": source_ref.node_id,
                        "to_scope_path": op.scope_path,
                        "to_class_type": op.class_type,
                        "to_input": input_name,
                    },
                )
            ]
        target_type = _normalize_type(getattr(spec, "type", None))
        if source_ref.socket_type and target_type and not socket_types_compatible(source_ref.socket_type, target_type):
            return None, [
                _issue(
                    "incompatible_socket_types",
                    f"Cannot connect {source_ref.class_type}.{source_ref.slot_name} ({source_ref.socket_type}) to "
                    f"{op.class_type}.{input_name} ({target_type}).",
                    detail={
                        "from_scope_path": source.scope_path,
                        "from_uid": source.uid,
                        "from_slot": source_ref.slot_name,
                        "from_type": source_ref.socket_type,
                        "to_scope_path": op.scope_path,
                        "to_class_type": op.class_type,
                        "to_input": input_name,
                        "to_type": target_type,
                    },
                )
            ]
        resolved_inputs[input_name] = source_ref

    anchor_near = None
    anchor_between = None
    anchor_group_index = None
    anchor_group_title = None
    if op.anchor is not None:
        anchor_issues: list[PortIssue] = []
        anchor_near, anchor_between, anchor_group_index, anchor_group_title, anchor_issues = _resolve_add_node_anchor(
            ledger,
            op.scope_path,
            op.anchor,
        )
        if anchor_issues:
            return None, anchor_issues

    return (
        ResolvedAddNodeSpec(
            op=op,
            scope=scope,
            schema=schema,
            schema_inputs=schema_inputs,
            resolved_inputs=resolved_inputs,
            anchor_near=anchor_near,
            anchor_between=anchor_between,
            anchor_group_index=anchor_group_index,
            anchor_group_title=anchor_group_title,
        ),
        list(issues),
    )


def _resolve_reorder(
    ledger: EditLedger,
    op: ReorderOp,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if op.axis != "widgets":
        return None, [
            _issue(
                "unsupported_reorder_form",
                "Phase 1 reorder supports only cosmetic unlinked widget value permutations; structural slot reorder is rejected.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    node_ref, issues = _resolve_node(ledger, op.target)
    if issues:
        return None, issues
    assert node_ref is not None
    raw = node_ref.node.get("widgets_values")
    if not isinstance(raw, list):
        return None, [
            _issue(
                "unsupported_reorder_axis",
                f"{node_ref.class_type} has no reorderable widget surface.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    names = _reorder_names(node_ref.node, node_ref.class_type, op.axis)
    if names is None:
        return None, [
            _issue(
                "unsupported_reorder_axis",
                f"{node_ref.class_type} has no named reorderable {op.axis} surface.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    if tuple(op.order) == tuple(names):
        return node_ref, []
    if len(op.order) != len(names) or set(op.order) != set(names):
        return None, [
            _issue(
                "unsupported_reorder_form",
                "reorder must be a complete permutation of the existing named widget or output slots.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "axis": op.axis,
                    "expected": list(names),
                    "actual": list(op.order),
                },
            )
        ]
    linked_widgets = _linked_widget_names(node_ref.node.get("inputs"))
    linked_ordered_widgets = [name for name in op.order if name in linked_widgets]
    if linked_ordered_widgets:
        return None, [
            _issue(
                "unsupported_reorder_form",
                "Phase 1 reorder only supports unlinked widget values; linked widget inputs must be edited with link ops first.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "axis": op.axis,
                    "linked_widgets": linked_ordered_widgets,
                },
            )
        ]
    return node_ref, []


def _resolve_add_node_anchor(
    ledger: EditLedger,
    scope_path: str,
    anchor: AnchorRef,
) -> tuple[
    ResolvedNodeRef | None,
    tuple[ResolvedNodeRef, ResolvedNodeRef] | None,
    int | None,
    str | None,
    list[PortIssue],
]:
    if anchor.group_title is not None:
        group_index = _group_index_by_title(ledger.scopes[scope_path].graph, anchor.group_title)
        if group_index is None:
            return None, None, None, None, [
                _issue(
                    "unknown_group_anchor",
                    f"Unknown group title {anchor.group_title!r} for add_node anchor.",
                    detail={"scope_path": scope_path, "group_title": anchor.group_title},
                )
            ]
    else:
        group_index = None

    near_ref = None
    if anchor.near is not None:
        if anchor.near.scope_path != scope_path:
            return None, None, None, None, [
                _issue(
                    "cross_scope_anchor_unsupported",
                    "add_node anchors must reference nodes in the same scope.",
                    detail={"scope_path": scope_path, "anchor_scope_path": anchor.near.scope_path},
                )
            ]
        near_ref, issues = _resolve_node(ledger, anchor.near)
        if issues:
            return None, None, None, None, issues

    between_ref = None
    if anchor.between is not None:
        resolved: list[ResolvedNodeRef] = []
        for target in anchor.between:
            if target.scope_path != scope_path:
                return None, None, None, None, [
                    _issue(
                        "cross_scope_anchor_unsupported",
                        "add_node anchors must reference nodes in the same scope.",
                        detail={"scope_path": scope_path, "anchor_scope_path": target.scope_path},
                    )
                ]
            node_ref, issues = _resolve_node(ledger, target)
            if issues:
                return None, None, None, None, issues
            assert node_ref is not None
            resolved.append(node_ref)
        between_ref = (resolved[0], resolved[1])

    return near_ref, between_ref, group_index, anchor.group_title, []
