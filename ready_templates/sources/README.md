# Ready Template Sources

This directory stores source ComfyUI workflow JSON. These files are import
material for indexing, conversion, coverage analysis, and ready-template
regeneration. They are workflows, not curated Python templates.

## Layout

| Path | Purpose |
|---|---|
| `official/` | Source workflows grouped by media kind (`audio/`, `edit/`, `image/`, `video/`). |
| `custom_nodes/` | Source workflows grouped by the custom-node pack or community source they exercise. |
| `input/` | Small media fixtures referenced by corpus workflows. Keep paths stable because JSON workflows may refer to them directly. |
| `manifests/` | Corpus metadata such as coverage tiers and ready-template regeneration provenance. |

## Path Contracts

Workflow IDs and paths are index-backed. Moving or renaming a source JSON file
can change its indexed path and break coverage manifests, regeneration records,
tests, or docs that point at the old location.

Safe changes:

- add new JSON workflows under the appropriate existing subtree
- add documentation or manifests that do not change existing paths
- update `input/FIXTURES.md` when fixture media changes

Coordinated changes:

- moving JSON workflows between directories
- renaming JSON workflow files
- moving `manifests/` or `input/`

After source changes, refresh and check the generated indexes:

```bash
python -m vibecomfy.cli sources sync
python -m vibecomfy.cli workflows list --json
python -m vibecomfy.cli analyze corpus --json
```
