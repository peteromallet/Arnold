# Pipeline Directory Unification Plan

## Goal

Move every runnable pipeline out of the transitional
`arnold/pipelines/megaplan/pipelines/` directory and into a canonical top-level
package under `arnold/pipelines/<name>/`. Retire the legacy Megaplan graph-plugin
root once it is empty.

## Why

Arnold currently supports two pipeline layouts:

1. **Canonical Arnold-native packages** under `arnold/pipelines/<name>/` — the
   target form, used by `vibecomfy_executor`, `deliberation`, `evidence_pack`,
   and `megaplan` itself.
2. **Transitional Megaplan plugin root** under
   `arnold/pipelines/megaplan/pipelines/` — a leftover scan root that mixes
   graph-driven sibling-file modules, nested package modules, and helper code.

There is no architectural reason to keep introducing pipelines in the
transitional root. Centralizing everything under `arnold/pipelines/` makes
discovery, trust, documentation, and onboarding consistent.

## Canonical target structure

Use `arnold/pipelines/vibecomfy_executor/` as the reference:

```
arnold/pipelines/<pipeline_name>/
├── __init__.py          # module-level contract + build_pipeline()
├── pipelines.py         # PipelineBuilder wiring / stage graph
├── steps.py             # step implementations
├── _helpers.py          # (optional) internal helpers
├── profiles/            # TOML profile files
│   └── default.toml
├── prompts/             # .md prompt templates
│   └── ...
├── skills/
│   └── <cli-name>/
│       └── SKILL.md     # agent-facing skill docs
└── tests/               # (optional) pipeline-specific tests
```

`__init__.py` must declare the standard contract as module-level literals:

```python
name = "<pipeline-name>"
description = "..."
driver = "in_process"           # or ("graph", "dispatch+emit"), etc.
entrypoint = "build_pipeline"
arnold_api_version = "1.0"
capabilities = ("...",)
default_profile = None
supported_modes = ()
```

## What moves, and where

### 1. Sibling-file modules (`.py` file + resource folder)

These are the most visibly inconsistent because the Python module and its
resources are split across two naming conventions.

| Current | Becomes |
|---|---|
| `arnold/pipelines/megaplan/pipelines/folder_audit.py` | `arnold/pipelines/folder_audit/__init__.py` (logic split into `pipelines.py` / `steps.py`) |
| `arnold/pipelines/megaplan/pipelines/folder-audit/prompts/` | `arnold/pipelines/folder_audit/prompts/` |
| `arnold/pipelines/megaplan/pipelines/folder-audit/profiles/` | `arnold/pipelines/folder_audit/profiles/` |
| `arnold/pipelines/megaplan/pipelines/folder-audit/skills/folder-audit/SKILL.md` | `arnold/pipelines/folder_audit/skills/folder-audit/SKILL.md` |

Apply the same pattern to:

- `epic-blitz` → `arnold/pipelines/epic_blitz/`
- `simplify-writing` → `arnold/pipelines/simplify_writing/`
- `writing-panel-strict` → `arnold/pipelines/writing_panel_strict/`

### 2. Nested package modules

These already have package structure (`__init__.py`, `steps.py`, etc.); they
just live in the wrong parent directory.

| Current | Becomes |
|---|---|
| `arnold/pipelines/megaplan/pipelines/creative/` | `arnold/pipelines/creative/` |
| `arnold/pipelines/megaplan/pipelines/doc/` | `arnold/pipelines/doc/` |
| `arnold/pipelines/megaplan/pipelines/jokes/` | `arnold/pipelines/jokes/` |
| `arnold/pipelines/megaplan/pipelines/live_supervisor/` | `arnold/pipelines/live_supervisor/` |
| `arnold/pipelines/megaplan/pipelines/select-tournament/` | `arnold/pipelines/select_tournament/` |

Main work: update internal imports from
`arnold.pipelines.megaplan.pipelines.<name>.steps` to
`arnold.pipelines.<name>.steps`.

### 3. Non-pipeline helper

`arnold/pipelines/megaplan/pipelines/planning/` is not a registered pipeline —
discovery rejects it because it lacks required manifest fields. Move it out of
the pipelines directory entirely, likely to
`arnold/pipelines/megaplan/planning/` as an internal helper subpackage of the
Megaplan pipeline.

## Additional changes required

- **Registry scan roots.** In
  `arnold/pipelines/megaplan/_pipeline/registry.py`, `_SCAN_ROOTS` lists both
  `arnold/pipelines/` and `arnold/pipelines/megaplan/pipelines/`. Remove the
  second entry once the directory is empty so the transitional form can no
  longer be discovered.
- **Skill paths.** The manifest reader derives the expected `SKILL.md` location
  from the module path. Top-level packages use
  `arnold/pipelines/<name>/skills/<cli-name>/SKILL.md`. Most nested packages
  already match this; sibling-file modules need their skill tree moved into the
  new package.
- **Tests.** Update any tests that import from the old module paths or assert
  on discovery paths.
- **Authoring docs / skill.** Update `new arnold pipeline` skill and any
  `docs/arnold/` authoring guides to describe only the top-level package form.
- **Profile references.** Pipeline profile names like `@folder-audit:standard`
  stay the same because they are based on the CLI-visible name, not the
  filesystem path.

## Migration order

1. **Sibling-file modules first** (`folder-audit`, `epic-blitz`,
   `simplify-writing`, `writing-panel-strict`). They are the most structurally
   wrong and easiest to justify moving.
2. **Nested package modules next** (`creative`, `doc`, `jokes`,
   `live-supervisor`, `select-tournament`). Mostly directory moves plus import
   fixes.
3. **Relocate the `planning` helper** out of the pipelines tree.
4. **Delete `arnold/pipelines/megaplan/pipelines/`** once empty.
5. **Remove the legacy scan root** from `_SCAN_ROOTS`.
6. **Update authoring docs and skill** to forbid the old forms.

## Validation per migration

For each moved pipeline:

```bash
python -m arnold pipelines check <name>
python -m pytest tests/path/to/test_<name>.py -q
python -m arnold run <name> --inputs ... --plan-dir /tmp/<name>-test
```

## Risks

- Import breakage inside moved packages.
- Tests that hardcode old module paths.
- `subprocess_isolated` and graph drivers may have internal assumptions about
  import prefixes; verify each pipeline end-to-end after moving.

The registry and manifest reader already support the top-level form, so
pipeline discovery itself is expected to work without changes.
