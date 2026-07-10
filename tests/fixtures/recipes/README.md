# Recipe Fixtures

These recipes are committed fixtures for `vibecomfy test verify` coverage.
User recipes belong in the local, gitignored root `recipes/` workspace.

Ready templates change handles by defining a reusable graph. Recipes decorate handles by loading a ready graph and applying patches, seeds, or extra nodes for a concrete run.

Run a fixture recipe with:

```bash
python tests/fixtures/recipes/wan_t2v_long.py
```

## Current Recipes

| Recipe | Purpose |
|---|---|
| `dual_pass_t2i.py` | Loads `image/z_image`, adds a placeholder upscale pass, and saves the second output. |
| `example_tested_recipe.py` | Minimal tested recipe used by the user-code testing docs and snapshot tests. |
| `wan_i2v_lowres.py` | Loads `video/wan_i2v` and applies low-resolution iteration settings. |
| `wan_t2v_long.py` | Loads `video/wan_t2v` and applies longer-form generation settings. |

## Authoring Notes

Recipes should prefer `from vibecomfy import load_workflow_any` when starting
from an existing workflow or ready template. That keeps the recipe independent
of generated template internals and matches the same loader path used by the
CLI.

Keep recipe snapshots beside the recipe only when they are part of the
documented user-code testing flow. Otherwise, generated run outputs belong
under `out/`.

Useful references:

- [Authoring guide](../../../docs/authoring.md)
- [User-code testing](../../../docs/testing/user_code.md)
- [Ready templates](../../../ready_templates/README.md)
