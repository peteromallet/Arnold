from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any

from vibecomfy.blocks import Handle, Handles, block
from vibecomfy.blocks._utils import add_block_node, connect
from vibecomfy.workflow import VibeNode, VibeWorkflow


@dataclass(frozen=True)
class NodeRef:
    node_id: str
    slot: int = 0


def ref(node: str | VibeNode, slot: int = 0) -> NodeRef:
    node_id = node.id if isinstance(node, VibeNode) else str(node)
    return NodeRef(node_id=node_id, slot=slot)


@block
def opaque(
    workflow: VibeWorkflow,
    *,
    class_type: str,
    widgets_by_name: Mapping[str, Any] | None = None,
    widget_values: Sequence[Any] | None = None,
    inputs: Mapping[str, Any] | None = None,
    links: Mapping[str, NodeRef] | None = None,
    outputs: tuple[str, ...] = ("out",),
    block_id: str | None = None,
) -> Handles:
    widget_kwargs = _widget_kwargs(widgets_by_name=widgets_by_name, widget_values=widget_values)
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.subgraph.opaque",
        class_type,
        block_id=block_id,
        inputs=dict(inputs or {}),
        widgets=widget_kwargs,
        metadata={"subgraph_class_type": class_type},
    )
    for input_name, source in dict(links or {}).items():
        connect(workflow, source.node_id, node, input_name, output_slot=source.slot)
    return Handles(
        {name: Handle(node_id=node.id, output_slot=slot, name=name) for slot, name in enumerate(outputs)},
        node=Handle(node_id=node.id, output_slot=0, name="node"),
    )


def _widget_kwargs(
    *,
    widgets_by_name: Mapping[str, Any] | None,
    widget_values: Sequence[Any] | None,
) -> dict[str, Any]:
    if widgets_by_name is not None and widget_values is not None:
        raise ValueError("Use either widgets_by_name or widget_values, not both.")
    if widgets_by_name is not None:
        return dict(widgets_by_name)
    if widget_values is None:
        return {}
    return {f"widget_{index}": value for index, value in enumerate(widget_values)}
