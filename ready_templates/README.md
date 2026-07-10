# Ready Templates

Ready templates are VibeComfy Python scratchpads that are intended to run end to end.

They are deliberately separate from `ready_templates/sources/`, which stores source ComfyUI JSON. A workflow graduates here only after it is part of the RunPod corpus matrix and either runs directly or has an explicit, documented runtime adaptation in the scratchpad.

Templates are organized by category (`audio/`, `edit/`, `image/`, `video/`) plus
`smoke/` for small structural templates, and expose category-qualified ids such
as `image/z_image`. New templates should be authored as VibeWorkflow builders
using `wf.node(...).out(...)`, block helpers, `subgraph.opaque` for UUID-class
subgraphs, and `workflow.finalize_metadata()`. Shared ready metadata belongs in
`vibecomfy.registry.ready_template`; see `docs/authoring.md`.

Some legacy templates still keep the API workflow, ready metadata, and ready requirements in the template file while delegating shared build/policy behavior to `vibecomfy.registry.ready_template`. Those remain supported until they are refactored.

Template files may be marked `# vibecomfy: generated` or `# vibecomfy: manual`.
Generated templates should be regenerated from corpus/source material instead of
hand-edited. Manual templates may be edited directly, but should still preserve
their public input/output contract and metadata.

The current checked-in ready corpus covers 64 templates:

- Audio: ACE Step song generation and Qwen3 TTS voice variants.
- Image/edit: Z-Image, Qwen image edit, Flux.2 Klein 4B and 9B T2I/edit variants, plus the Flux.2 Klein 9B GGUF T2I runtime fallback.
- Smoke: small structural templates used for fast validation.
- Wan: official Wan T2V/I2V plus the representative Kijai WanVideoWrapper matrix.
- LTX: official LTX 2.3 T2V/I2V/two-stage/IC-LoRA workflows plus community audio, V2V, anchor, motion-transfer, and long-form templates.

Raw JSON remains supported as import material, but this directory is the reusable native layer:

```text
raw Comfy JSON -> normalize_to_api -> VibeWorkflow -> ready Python template
```

Use `vibecomfy nodes install-plan <template.py>` when a ready template fails on missing custom nodes. The generated `READY_REQUIREMENTS` block is derived from the custom-node catalog where possible.

Ready templates change handles. Local recipes in gitignored `recipes/` decorate handles for specific runs by applying patches, seeds, or extra placeholder chains.

After adding, moving, or deleting a ready template, update the manifest row and refresh the static index:

```bash
python -m tools.refresh_template_index
python -m tools.refresh_template_index --check
pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py
```

Validate the runtime matrix with a focused scope while iterating, then broaden it:

```bash
VIBECOMFY_MATRIX_SCOPE=<family> python scripts/runpod_corpus_matrix.py
```
