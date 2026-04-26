from __future__ import annotations

from vibecomfy import Handle, VibeWorkflow, WorkflowSource


PROMPT = (
    "A hedgehog wearing a tiny party hat surrounded by confetti, early digital camera style, "
    "slight noise, flash photography, candid moment, 2000s digicam aesthetic, festive birthday "
    "celebration atmosphere\n"
)

FLUX_KLEIN_BASE_SUBGRAPH = "7b34ab90-36f9-45ba-a665-71d418f0df18"
FLUX_KLEIN_4B_SUBGRAPH = "a67caa28-5f85-4917-8396-36004960dd30"


def build() -> VibeWorkflow:
    workflow = VibeWorkflow("image/flux2_klein_4b_t2i", WorkflowSource("typed-fixture"))

    workflow.node("SaveImage", images=Handle("4", 0), widget_0="Flux2-Klein")
    workflow.node("SaveImage", images=Handle("5", 0), widget_0="Flux2-Klein")
    text = workflow.node("PrimitiveStringMultiline", widget_0=PROMPT).out(0)

    workflow.node(
        FLUX_KLEIN_BASE_SUBGRAPH,
        widget_0="",
        widget_1=1024,
        widget_2=1024,
        widget_3="flux-2-klein-base-4b.safetensors",
        widget_4="qwen_3_4b.safetensors",
        widget_5="flux2-vae.safetensors",
        text=text,
    )

    workflow.node(
        FLUX_KLEIN_4B_SUBGRAPH,
        widget_0="",
        widget_1=1024,
        widget_2=1024,
        widget_3="flux-2-klein-4b.safetensors",
        widget_4="qwen_3_4b.safetensors",
        widget_5="flux2-vae.safetensors",
        text=text,
    )
    return workflow
