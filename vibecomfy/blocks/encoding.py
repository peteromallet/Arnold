from __future__ import annotations

from vibecomfy.blocks import Handles, block
from vibecomfy.blocks._utils import add_block_node, connect
from vibecomfy.workflow import VibeWorkflow


@block
def text_pair(
    workflow: VibeWorkflow,
    *,
    clip: str,
    positive: str,
    negative: str = "",
    block_id: str | None = None,
) -> Handles:
    pos = add_block_node(
        workflow,
        "vibecomfy.blocks.encoding.text_pair",
        "CLIPTextEncode",
        block_id=block_id,
        widgets={"widget_0": positive},
    )
    neg = add_block_node(
        workflow,
        "vibecomfy.blocks.encoding.text_pair",
        "CLIPTextEncode",
        block_id=block_id,
        widgets={"widget_0": negative},
    )
    connect(workflow, clip, pos, "clip")
    connect(workflow, clip, neg, "clip")
    return Handles(positive=pos.id, negative=neg.id)


@block
def clip_vision(
    workflow: VibeWorkflow,
    *,
    clip_vision: str,
    image: str,
    crop: str = "center",
    block_id: str | None = None,
) -> Handles:
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.encoding.clip_vision",
        "CLIPVisionEncode",
        block_id=block_id,
        widgets={"widget_0": crop},
    )
    connect(workflow, clip_vision, node, "clip_vision")
    connect(workflow, image, node, "image")
    return Handles(clip_vision_output=node.id, encoded=node.id)
