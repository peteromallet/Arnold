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

Scope:

- Every ready template loaded through the ready registry.
- Every ready template passed `VibeWorkflow.validate()`.
- Every ready template compiled to non-empty Comfy API JSON.
- The new official Flux Klein templates are covered by registry assertions in `tests/test_ready_templates.py`.

Not covered by this local pass:

- Fresh GPU runtime execution for the four newly added Flux templates.
- Fresh RunPod matrix artifacts for the expanded 46-template corpus.

