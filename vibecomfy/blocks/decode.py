from __future__ import annotations

from vibecomfy.blocks import Handles, block
from vibecomfy.blocks._utils import add_block_node, connect
from vibecomfy.workflow import VibeWorkflow


@block
def vae(
    workflow: VibeWorkflow,
    *,
    samples: str,
    vae: str,
    block_id: str | None = None,
) -> Handles:
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.decode.vae",
        "VAEDecode",
        block_id=block_id,
    )
    connect(workflow, samples, node, "samples")
    connect(workflow, vae, node, "vae")
    return Handles(images=node.id)
