"""
01_first_workflow.py — Your first vibecomfy workflow
=====================================================

Build a minimal ready template from scratch: create a workflow context, add
nodes, wire them together, and finalize with public inputs.

This is a **build-only** tutorial — no GPU, no network, no model downloads.
"""

from __future__ import annotations

from vibecomfy.templates import InputSpec, new_workflow, node, ReadyMetadata, finalize_ready
from vibecomfy.workflow import VibeWorkflow

# ---------------------------------------------------------------------------
# 1. Define your metadata
# ---------------------------------------------------------------------------
# ReadyMetadata.build() helps you declare what your template can do, what
# models it needs, which inputs users can tweak, and where outputs land.
# For this minimal example we supply only the required fields.

METADATA = ReadyMetadata.build(
    capability="image",               # high-level capability tag
    models={},                         # no models needed for build-only
    inputs={},                         # we'll add inputs later
    output_prefix="image/MyFirst",     # output file prefix
)

# ---------------------------------------------------------------------------
# 2. Build the workflow inside a context manager
# ---------------------------------------------------------------------------
# ``new_workflow(...)`` activates a thread-local ContextVar.  Any call to
# ``node(...)`` or a generated wrapper inside the ``with`` block automatically
# binds to this workflow — you don't need to pass ``wf`` around.

def build() -> VibeWorkflow:
    """Assemble a minimal image-workflow (build-only, no GPU)."""
    with new_workflow(METADATA, source_path=__file__) as wf:

        # -- Loaders ---------------------------------------------------------
        # Each node() call creates a VibeNode in the active workflow.
        # Keyword arguments become node inputs/widgets.
        checkpoint = node("CheckpointLoaderSimple", ckpt_name="v1-5-pruned-emaonly.safetensors")

        # -- Conditioning ----------------------------------------------------
        positive = node("CLIPTextEncode", text="a cat sitting on a cloud", clip=checkpoint.out(1))
        negative = node("CLIPTextEncode", text="blurry, ugly", clip=checkpoint.out(1))

        # -- Latent ----------------------------------------------------------
        latent = node("EmptyLatentImage", width=512, height=512, batch_size=1)

        # -- Sampling --------------------------------------------------------
        sampled = node("KSampler",
            seed=42,
            steps=20,
            cfg=7.0,
            sampler_name="euler",
            scheduler="normal",
            denoise=1.0,
            model=checkpoint.out(0),
            positive=positive.out(0),
            negative=negative.out(0),
            latent_image=latent.out(0),
        )

        # -- Decode ----------------------------------------------------------
        decoded = node("VAEDecode", samples=sampled.out(0), vae=checkpoint.out(2))

        # -- Output ----------------------------------------------------------
        node("SaveImage", filename_prefix="MyFirst", images=decoded.out(0))

        # -- Finalize --------------------------------------------------------
        # finalize_ready() registers public inputs and seals the workflow.
        return finalize_ready(wf, METADATA, source_path=__file__)

# ---------------------------------------------------------------------------
# 3. Compile (build-only validation — no GPU)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    workflow = build()
    print(f"Workflow built: {workflow.id}")
    print(f"  Nodes: {len(workflow.nodes)}")
    print(f"  Edges: {len(workflow.edges)}")

    # Compile to API JSON to verify the graph is well-formed.
    api = workflow.compile("api")
    print(f"  API nodes: {len(api)}")
    print("✓ Build validated — no runtime required.")
