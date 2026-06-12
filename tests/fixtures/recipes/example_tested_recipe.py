"""A canonical tested recipe fixture for `vibecomfy test verify`.

Build a tiny synthetic VibeWorkflow that doesn't depend on heavy models, so
the snapshot baseline stays stable across environments.
"""
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    wf = VibeWorkflow(id="example-tested-recipe", source=WorkflowSource(id="example-tested-recipe"))
    wf.nodes["1"] = VibeNode(id="1", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": "noop.safetensors"})
    wf.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"images": ["1", 0], "filename_prefix": "out/example_tested"})
    return wf
