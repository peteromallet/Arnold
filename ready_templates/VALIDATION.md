# Ready Template Validation

## 2026-04-26 Local Validation

Ready corpus size: 46 templates.

Added in this pass:

- `image/flux2_klein_9b_t2i`
- `edit/flux2_klein_4b_image_edit_base`
- `edit/flux2_klein_9b_image_edit_base`
- `edit/flux2_klein_9b_image_edit_distilled`

Validation run:

```bash
uv run pytest -q
uv run python - <<'PY'
from vibecomfy.registry.ready import ready_template_ids, workflow_from_ready

for template_id in ready_template_ids():
    workflow = workflow_from_ready(template_id)
    assert workflow.validate().ok, template_id
    assert workflow.compile("api"), template_id

print(f"validated_ready_templates={len(ready_template_ids())}")
PY
```

Result:

- `242 passed, 1 skipped`
- `validated_ready_templates=46`
- Latest full-suite rerun after RunPod harness fixes: `244 passed, 1 skipped`

Scope:

- Every ready template loaded through the ready registry.
- Every ready template passed `VibeWorkflow.validate()`.
- Every ready template compiled to non-empty Comfy API JSON.
- The new official Flux Klein templates are covered by registry assertions in `tests/test_ready_templates.py`.

Not covered by this local pass:

- Fresh GPU runtime execution for the 9B safetensors Flux templates, which require a Hugging Face token with accepted BFL license terms.
- Fresh RunPod matrix artifacts for the expanded 46-template corpus.

## 2026-04-26 RunPod Flux 4B Validation

Command:

```bash
VIBECOMFY_MATRIX_SCOPE=flux2_4b uv run --extra runpod-local --with runpod --with paramiko --with requests python scripts/runpod_corpus_matrix.py
```

Final artifact:

- `out/runpod_artifacts/1777225293`
- RunPod pod `c8h97tx96u6730`
- RTX 4090
- Pod terminated cleanly (`terminated_launched_pod=true`)

Result:

| Template | Baseline Comfy | Converted scratchpad | VibeComfy run | Media evidence |
| --- | --- | --- | --- | --- |
| `image/flux2_klein_4b_t2i` | ok, 110s | validate ok, 10s | ok, 90s | 2 images, 4,086,454 bytes |
| `edit/flux2_klein_4b_image_edit_base` | ok, 120s | validate ok, 10s | ok, 110s | 3 images, 5,017,911 bytes |
| `edit/flux2_klein_4b_image_edit_distilled` | ok, 90s | validate ok, 11s | ok, 90s | 4 images, 6,218,693 bytes |

Matrix summary:

- `failures=0`
- `ready_failures=0`
- Baseline images written under `out/corpus_matrix/comfyui/...`
- VibeComfy images written under `output/`

Issues found and fixed while validating:

- The matrix planner was not including supplemental Flux ready templates for Flux/image scopes. It now includes them for `image_core`, `z_flux`, `image_creation_types`, `flux2`, `flux2_4b`, and `flux2_9b`.
- `flux2_9b` scope only selected GGUF rows. It now also selects non-GGUF 9B ready templates for license-gated safetensors validation.
- The corpus matrix was passing universal `--prompt`/`--steps` overrides to Flux Klein workflows. Flux Klein uses custom scheduler/conditioning nodes, so the matrix now runs Flux workflows with source-authored prompt/step settings plus deterministic seed only.
- The 4B base edit workflow required `flux-2-klein-base-4b-fp8.safetensors` and `full_encoder_small_decoder.safetensors`; both are now in the model registry under `phase:core`.

Earlier failed artifacts kept for traceability:

- `out/runpod_artifacts/1777223626`: exposed invalid Flux universal `--steps` override and missing 4B base edit assets.
- `out/runpod_artifacts/1777224240`: confirmed the override fix and showed the model assets needed to move into registry staging rather than legacy staging only.
