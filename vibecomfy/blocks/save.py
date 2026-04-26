from __future__ import annotations

from dataclasses import dataclass

from vibecomfy.blocks import Handles, block
from vibecomfy.blocks._utils import add_block_node, connect
from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True)
class VideoSaveSettings:
    filename_prefix: str = "video/ComfyUI"
    format: str = "auto"
    codec: str = "auto"


@block
def image(
    workflow: VibeWorkflow,
    *,
    images: str,
    filename_prefix: str = "ComfyUI",
    block_id: str | None = None,
) -> Handles:
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.save.image",
        "SaveImage",
        block_id=block_id,
        widgets={"widget_0": filename_prefix},
    )
    connect(workflow, images, node, "images")
    return Handles(output=node.id, image=node.id)


@block
def video(
    workflow: VibeWorkflow,
    *,
    video: str,
    settings: VideoSaveSettings | None = None,
    block_id: str | None = None,
) -> Handles:
    settings = settings or VideoSaveSettings()
    node = add_block_node(
        workflow,
        "vibecomfy.blocks.save.video",
        "SaveVideo",
        block_id=block_id,
        widgets={"widget_0": settings.filename_prefix, "widget_1": settings.format, "widget_2": settings.codec},
    )
    connect(workflow, video, node, "video")
    return Handles(output=node.id, video=node.id)
