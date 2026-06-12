# vendor/

Vendored source material and local dependency checkouts that are useful for
porting, validation, and runtime compatibility work.

| Path | Kind | Purpose |
|---|---|---|
| [ComfyUI/](ComfyUI/) | Git submodule | Pinned ComfyUI fork used for embedded runtime and compatibility checks. The submodule is registered in `.gitmodules`. |
| `direct_templates/` | Checked-in JSON | Provider API workflow/template examples that are source material, not ready templates. |
| `workflow_templates/` | Local only | Large local checkout area ignored by git. |
| `external_workflows/` | Local only | Large local workflow source area ignored by git. |

## Policy

- Submodules belong at `vendor/<name>/` and must be declared in `.gitmodules`.
- Raw provider JSON that is not part of `workflow_corpus/` belongs under
  `vendor/direct_templates/`.
- Large local checkouts belong in the gitignored `workflow_templates/` or
  `external_workflows/` directories.
- Do not commit OS junk, Python bytecode, downloaded model weights, or runtime
  outputs in this tree.

## ComfyUI Submodule

The current submodule points at:

- Upstream: `https://github.com/peteromallet/ComfyUI.git`
- Branch: `fix/latentupscale-model-mmap-residency`

Update it deliberately:

```bash
git submodule update --remote vendor/ComfyUI
```
