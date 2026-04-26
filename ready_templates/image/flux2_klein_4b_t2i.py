from __future__ import annotations

from typing import Any

from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


READY_METADATA = {
    "model_assets": [
        {
            "name": "flux-2-klein-base-4b.safetensors",
            "url": "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors",
            "subdir": "diffusion_models",
        },
        {
            "name": "qwen_3_4b.safetensors",
            "url": "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
            "subdir": "text_encoders",
        },
        {
            "name": "flux2-vae.safetensors",
            "url": "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors",
            "subdir": "vae",
        },
        {
            "name": "flux-2-klein-4b.safetensors",
            "url": "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors",
            "subdir": "diffusion_models",
        },
    ],
    "unbound_inputs": {"seed": 2734},
    "ready_template": "image/flux2_klein_4b_t2i",
    "workflow_template": "flux2_klein_4b_t2i",
    "capability": "text_to_image",
    "source_role": "native_ready_python_template",
    "source_workflow": "workflow_corpus/official/image/flux2_klein_4b_t2i.json",
    "coverage_tier": "required",
    "approach": "native_python_builder",
    "runtime_note": None,
    "discord_signal": None,
}

READY_REQUIREMENTS = {
    "models": [
        {
            "name": "flux-2-klein-base-4b.safetensors",
            "url": "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors",
            "subdir": "diffusion_models",
        },
        {
            "name": "qwen_3_4b.safetensors",
            "url": "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors",
            "subdir": "text_encoders",
        },
        {
            "name": "flux2-vae.safetensors",
            "url": "https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors",
            "subdir": "vae",
        },
        {
            "name": "flux-2-klein-4b.safetensors",
            "url": "https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors",
            "subdir": "diffusion_models",
        },
    ],
    "custom_nodes": [],
}


PROMPT = (
    "A hedgehog wearing a tiny party hat surrounded by confetti, early digital camera style, "
    "slight noise, flash photography, candid moment, 2000s digicam aesthetic, festive birthday "
    "celebration atmosphere\n"
)

FLUX_KLEIN_BASE_SUBGRAPH = "7b34ab90-36f9-45ba-a665-71d418f0df18"
FLUX_KLEIN_4B_SUBGRAPH = "a67caa28-5f85-4917-8396-36004960dd30"


def build() -> VibeWorkflow:
    workflow = VibeWorkflow(
        "image/flux2_klein_4b_t2i",
        WorkflowSource(
            id="flux2_klein_4b_t2i",
            path=__file__,
            source_type="native_ready_python_template",
            provenance={"source_workflow": READY_METADATA["source_workflow"]},
        ),
    )

    text = prompt_text(workflow, PROMPT)

    base_image = flux2_klein_text_to_image(
        workflow,
        node_id="75",
        model="flux-2-klein-base-4b.safetensors",
        text_node=text,
        subgraph=FLUX_KLEIN_BASE_SUBGRAPH,
    )
    save_image(workflow, "9", base_image, prefix="Flux2-Klein")

    tuned_image = flux2_klein_text_to_image(
        workflow,
        node_id="77",
        model="flux-2-klein-4b.safetensors",
        text_node=text,
        subgraph=FLUX_KLEIN_4B_SUBGRAPH,
    )
    save_image(workflow, "78", tuned_image, prefix="Flux2-Klein")

    add_source_note(workflow)

    return apply_ready_template_policy(
        workflow,
        READY_METADATA,
        source_path=__file__,
        requirements=READY_REQUIREMENTS,
    )


def prompt_text(workflow: VibeWorkflow, text: str) -> VibeNode:
    return node(workflow, "76", "PrimitiveStringMultiline", widget_0=text)


def flux2_klein_text_to_image(
    workflow: VibeWorkflow,
    *,
    node_id: str,
    model: str,
    text_node: VibeNode,
    subgraph: str,
    width: int = 1024,
    height: int = 1024,
    text_encoder: str = "qwen_3_4b.safetensors",
    vae: str = "flux2-vae.safetensors",
) -> VibeNode:
    image = node(
        workflow,
        node_id,
        subgraph,
        widget_0="",
        widget_1=width,
        widget_2=height,
        widget_3=model,
        widget_4=text_encoder,
        widget_5=vae,
    )
    workflow.connect(f"{text_node.id}.0", f"{image.id}.text")
    return image


def save_image(workflow: VibeWorkflow, node_id: str, image_node: VibeNode, *, prefix: str) -> VibeNode:
    saved = node(workflow, node_id, "SaveImage", widget_0=prefix)
    workflow.connect(f"{image_node.id}.0", f"{saved.id}.images")
    return saved


def add_source_note(workflow: VibeWorkflow) -> VibeNode:
    return node(
        workflow,
        "79",
        "MarkdownNote",
        widget_0=(
            "Native VibeComfy Python builder for the official Flux.2 Klein 4B text-to-image "
            "template. The builder composes prompt, model subgraph calls, and save nodes in "
            "Python, then compiles to the Comfy API graph for HiddenSwitch execution."
        ),
    )


def node(workflow: VibeWorkflow, node_id: str, class_type: str, **inputs: Any) -> VibeNode:
    if node_id in workflow.nodes:
        raise ValueError(f"duplicate node id: {node_id}")
    created = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
    workflow.nodes[node_id] = created
    return created
