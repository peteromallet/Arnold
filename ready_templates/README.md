# Ready Templates

Ready templates are VibeComfy Python scratchpads that are intended to run end to end.

They are deliberately separate from `workflow_corpus/`, which stores source ComfyUI JSON. A workflow graduates here only after it is part of the RunPod corpus matrix and either runs directly or has an explicit, documented runtime adaptation in the scratchpad.

Templates are organized by category (`edit/`, `image/`, `video`) and expose category-qualified ids such as `image/z_image`. Generated templates keep the API workflow, ready metadata, and ready requirements in the template file while delegating shared build/policy behavior to `vibecomfy.registry.ready_template`.

The current checked-in ready corpus covers:

- Image/edit: Z-Image, Qwen image edit, Flux.2 Klein 4B T2I/edit, and Flux.2 Klein 9B GGUF T2I.
- Wan: official Wan T2V/I2V plus the representative Kijai WanVideoWrapper matrix.
- LTX: official LTX 2.3 T2V/I2V/two-stage/IC-LoRA workflows plus community audio, V2V, anchor, motion-transfer, and long-form templates.

Raw JSON remains supported as import material, but this directory is the reusable native layer:

```text
raw Comfy JSON -> normalize_to_api -> VibeWorkflow -> ready Python template
```

Use `vibecomfy nodes install-plan <template.py>` when a ready template fails on missing custom nodes. The generated `READY_REQUIREMENTS` block is derived from the custom-node catalog where possible.

Validate the library with:

```bash
python3 scripts/runpod_corpus_matrix.py
```
