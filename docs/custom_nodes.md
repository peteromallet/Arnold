# Custom Nodes

Pinned custom-node packs:

```text
ComfyUI-KJNodes b7646ad70a7daa7aeb919ca542274758d26ba2df https://github.com/kijai/ComfyUI-KJNodes.git
ComfyUI-WanVideoWrapper df8f3e49daaad117cf3090cc916c83f3d001494c https://github.com/kijai/ComfyUI-WanVideoWrapper.git
```

The lockfile is `custom_nodes.lock`.

## Resolution Policy

Custom-node handling is now a catalog-backed workflow, not just a doc note.

- `vibecomfy doctor <workflow-or-scratchpad>` reports unknown classes and suggests known packs.
- `vibecomfy nodes install-plan <workflow-or-scratchpad>` prints the custom-node repos and pip packages needed for a workflow.
- `scripts/materialize_ready_templates.py` derives `READY_REQUIREMENTS["custom_nodes"]` from the same catalog.
- `scripts/runpod_matrix_remote.py` carries compatibility patches for known stale workflow class names, such as older Video-Depth-Anything nodes that now map to Kijai's `DepthAnything_V2` pack.

The current catalog includes WanVideoWrapper, LTXVideo, KJNodes, VideoHelperSuite, ControlNet Aux, DepthAnythingV2, GGUF, DarioFT Qwen3-TTS, and 1038lab QwenTTS. New workflow failures should generally become catalog entries or compatibility patches, not one-off matrix hacks.

VibeComfy scans these folders for workflow examples:

```text
example_workflows/
workflow/
workflows/
example/
examples/
```

Current local inventory:

- Official templates: 23
- External workflows/examples: 51
- Runtime node definitions from Comfy: 1,202

Known warnings during local and RunPod runtime loading:

- `sageattention` is not installed, so WanVideoWrapper loads without that acceleration path.
- `onnx` is not installed, so FantasyPortrait nodes are not available.

These warnings do not block the current smoke workflows, but workflows requiring those optional nodes should report a concrete missing dependency before being treated as runnable.
