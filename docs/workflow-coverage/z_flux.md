# Z-Image And Flux Klein Coverage

VibeComfy should treat Z-Image and Flux Klein the same way as LTX and Wan: raw workflows are source material, ready templates are reusable Python assets, and RunPod-green templates are the subset that have produced media through both baseline Comfy and VibeComfy.

## Source Priority

Use this order when adding high-quality workflows:

- Official Comfy workflow templates and Comfy docs/tutorial workflow JSON.
- Official model repository examples when they include Comfy JSON or embedded workflow metadata.
- Reputable hosted workflow packs only when the workflow JSON can be downloaded and provenance is clear.
- GitHub/Civitai/community workflows for capability gaps such as multi-image edit, ControlNet, LoRA consistency, GGUF, panorama/outpaint, or raster-to-vector variants.

Do not add screenshot-only workflows. Every source must become a committed raw JSON file, a manifest entry, and a generated or curated ready template before it is considered usable.

## Current Repo Coverage

Official templates already checked in:

- `image/z_image`: official Z-Image text-to-image.
- `image/flux2_klein_4b_t2i`: official Flux.2 Klein 4B text-to-image.
- `edit/flux2_klein_4b_image_edit_distilled`: official Flux.2 Klein 4B distilled image edit.
- `ready_templates/sources/official/image/flux2_klein_9b_t2i.json`: official Flux.2 Klein 9B text-to-image raw source.
- `ready_templates/sources/official/edit/flux2_klein_9b_image_edit_base.json`: official Flux.2 Klein 9B image edit raw source.
- `ready_templates/sources/official/edit/flux2_klein_9b_image_edit_distilled.json`: official Flux.2 Klein 9B distilled image edit raw source.
- `image/flux2_klein_9b_gguf_t2i`: public GGUF fallback for 9B text-to-image because the official 9B safetensors can be gated.

## Runtime Plan

Use the focused matrix scope:

```bash
VIBECOMFY_MATRIX_SCOPE=z_flux ../runpod-lifecycle/.venv/bin/python scripts/runpod_corpus_matrix.py
```

That scope should run Z-Image, Flux Klein 4B image workflows, and the public 9B GGUF workflow without pulling in video workflow setup.

Next template additions should be capability-led:

- Z-Image Turbo/base if the official template library has separate variants.
- Flux Klein 4B base edit, not only distilled edit.
- Flux Klein 9B base and distilled edit as ready templates, plus a public-runtime path where gated safetensors are unavailable.
- Multi-image edit and ControlNet-style Flux Klein workflows from prominent community packs if they normalize cleanly and have clear model requirements.
