from __future__ import annotations

from vibecomfy import VibeWorkflow, WorkflowSource


PROMPT = (
    "A fashion photography work full of surreal romanticism, using a low-angle upward shooting "
    "composition, with a clear light blue sky as the background, and the visual focus concentrated "
    "on the fantasy blue vegetation and the model walking through it.\n"
    "\n"
    "The vegetation in the picture is processed into varying shades of blue, from light ice blue to "
    "deep cobalt blue. The textures of the leaves and branches are delicate and realistic. The warm "
    "brown tree trunks form a sharp contrast with the cool blue leaves, resembling a dreamy forest "
    "from another world. An African-American model wearing a yellow and white vertical striped long "
    "dress walks slowly on the sand. The warm tones of the dress echo with the surrounding cool blue "
    "vegetation. The noon sun casts clear shadows on the sand, enhancing the sense of space and "
    "reality in the picture.\n"
    "\n"
    "The entire scene, with its clean and transparent colors and fantasy settings, not only exudes "
    "the vastness of the natural wilderness but also presents a quiet and poetic high-fashion sense "
    "due to the surreal vegetation."
)

Z_IMAGE_SUBGRAPH = "9b9009e4-2d3d-445f-9be5-6063f465757e"


def build() -> VibeWorkflow:
    workflow = VibeWorkflow("image/z_image", WorkflowSource("typed-fixture"))
    save = workflow.node("SaveImage", widget_0="z-image")
    image = workflow.node(
        Z_IMAGE_SUBGRAPH,
        widget_0=PROMPT,
        widget_1=1024,
        widget_2=1024,
        widget_3=25,
        widget_4=4,
        widget_5=None,
        widget_6=None,
        widget_7="z_image_bf16.safetensors",
        widget_8="qwen_3_4b.safetensors",
        widget_9="ae.safetensors",
    ).out(0)
    workflow.connect(image, f"{save.id}.images")
    return workflow
