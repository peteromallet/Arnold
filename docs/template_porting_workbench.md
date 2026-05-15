# Template Porting Workbench

The porting workbench is the first stop when importing or repairing a ComfyUI workflow for VibeComfy. Run it before hand-editing a converted template, before spending RunPod time, and whenever a raw workflow fails with missing custom nodes, schema errors, model asset problems, helper nodes, or positional `widget_N` ambiguity.

The steady-state output should be Python: an editable scratchpad or a ready-template candidate. Raw JSON is source material, not the long-term authoring surface.

The converter writes atomically: emitted text goes to a temp file in the target directory, is re-validated and parity-checked, then replaced via `Path.replace()` only when all gates pass. Failed conversions leave pre-existing files byte-for-byte unchanged. Templates marked `# vibecomfy: manual` on their first line are never overwritten.

## Quick Start

```bash
python -m vibecomfy.cli port check <workflow> --json
python -m vibecomfy.cli port convert <workflow> --out out/scratchpads/<id>.py --json
python -m vibecomfy.cli port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
python -m vibecomfy.cli port inventory --ready --json
```

Use `<workflow>` as a ready id, scratchpad path, raw JSON path, or indexed workflow reference. `port check` is offline by default and cheap enough to run before every manual template edit and before every RunPod validation attempt.

## When To Use Each Command

| Need | Command |
| --- | --- |
| Preflight a source workflow before editing or RunPod | `python -m vibecomfy.cli port check <workflow> --json` |
| Turn raw JSON or an indexed workflow into editable Python | `python -m vibecomfy.cli port convert <workflow> --out out/scratchpads/<id>.py --json` |
| Produce a ready-template candidate | `python -m vibecomfy.cli port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json` |
| Validate an authored scratchpad or ready template | `python -m vibecomfy.cli validate <scratchpad-or-template.py>` |
| Diagnose runtime readiness and suggested fixes | `python -m vibecomfy.cli doctor <workflow>` |
| See custom-node packs to install | `python -m vibecomfy.cli nodes install-plan <workflow>` |
| Reconcile and fetch final runtime model assets | `python -m vibecomfy.cli run <workflow> --runtime embedded` |
| Fetch authored model asset metadata only | `python -m vibecomfy.cli fetch <workflow>` |
| Check model URLs without downloading bodies | `python -m vibecomfy.cli port check <workflow> --head-check-models --json` |

`--head-check-models` is opt-in. It performs HEAD requests only, follows redirects, records status codes, and does not download model bodies. Keep normal `run`, `doctor`, `validate`, and `fetch` behavior offline unless you intentionally ask for URL checks.

Embedded `run` reconciles model assets by default. It inspects the final built workflow after scratchpad patches, resolves model-picker values such as `ckpt_name`, `vae_name`, `unet_name`, and `lora_name` through authored `model_assets` and `vibecomfy/registry/models.yaml`, downloads/stages resolved files, and fails before queueing if a referenced asset cannot be resolved. Use `--no-ensure-models` only for compile-only work where downloads are intentionally disabled.

## What `port check` Reports

The report is a stable JSON object with provenance, source hash, workflow shape, node counts, diagnostics, custom-node pack suggestions, model asset candidates, optional URL check results, artifacts, and recommendations.

It catches the failure classes that previously surfaced only after conversion or on a GPU:

- helper and UI-only nodes such as `Note`, `MarkdownNote`, `SetNode`, and `GetNode`;
- unresolved helper broadcasts before compile can silently drop them;
- missing real runtime class types and matching node-pack suggestions;
- unknown classes, missing required inputs, invalid link shapes, and schema type mismatches;
- filename-only or missing model asset URLs;
- duplicate model URL targets and opt-in HEAD failures such as 404 or license-gated responses;
- unresolved positional `widget_N` aliases using widget-only schemas so link-only sockets do not shift widget positions.

Helper/UI classes are never treated as installable missing packs. They produce helper diagnostics. Real unresolved runtime classes remain hard porting errors.

## Convert Modes

Scratchpad mode is the default and is the right choice while investigating a workflow:

```bash
python -m vibecomfy.cli port convert workflow_corpus/community/example.json \
  --out out/scratchpads/example.py \
  --json
```

Ready-template mode is explicit because it creates a curated candidate with template identity:

```bash
python -m vibecomfy.cli port convert workflow_corpus/community/example.json \
  --ready-id image/example \
  --out ready_templates/image/example.py \
  --json
```

The converter validates emitted Python by importing the module, calling `build()`, compiling API output, and running schema validation when a provider is available.

### Dry-Run And Diff Modes

Use `--dry-run` to inspect conversion output and parity evidence without touching the filesystem:

```bash
python -m vibecomfy.cli port convert workflow_corpus/community/example.json \
  --out out/scratchpads/example.py \
  --dry-run --json
```

Use `--diff` to get a unified diff and JSON diff metadata alongside the write:

```bash
python -m vibecomfy.cli port convert workflow_corpus/community/example.json \
  --out out/scratchpads/example.py \
  --diff --json
```

### Manual Template Refusal

Templates whose first line contains `# vibecomfy: manual` will not be overwritten.
This is a hard gate evaluated before emission work. To regenerate a manual template,
remove the marker or use a different output path.

### Port Inventory

```bash
python -m vibecomfy.cli port inventory --ready --json
```

The inventory reports readability issues across all checked-in `ready_templates/**/*.py`
files: positional `.out(<int>)` calls, `widget_N` field references, UUID class types,
local `_node` helper copies, missing output contracts, marker classification, coverage-tier
joins, and source-provenance flags. It never consults plugin, cwd-extra, or user-global
paths. The JSON output is deterministic and versioned.

## From JSON To Checked-In Python

Use this path for workflows that should become reusable templates:

1. Keep the raw JSON in `workflow_corpus/.../<id>.json` when it is useful source material.
2. Run `port check <json> --json` and resolve hard diagnostics before conversion.
3. Convert to an editable scratchpad first when the graph needs investigation.
4. Convert with `--ready-id <kind>/<id>` or hand-author `ready_templates/<kind>/<id>.py` when the workflow becomes reusable.
5. Add or update the `workflow_corpus/manifests/coverage.json` row with `id`, `path`, `media`, `task`, `coverage_tier`, and `ready_template: true`.
6. Refresh the static discovery index:

```bash
python -m tools.refresh_template_index
python -m tools.refresh_template_index --check
```

Then validate the Python template:

```bash
python -m vibecomfy.cli validate ready_templates/<kind>/<id>.py
python -m pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py tests/test_cli.py
```

Editing internals of a Python template does not require a manifest or index
change unless its identity, category, task, coverage tier, custom-node
requirements, model requirements, or reusable capability changes. Adding,
renaming, or removing a ready template must update `coverage.json` and
`template_index.json`; `tools.refresh_template_index --check` catches drift.

## Live Validation Loop

Run this order while porting:

1. `port check <workflow> --json`
2. `nodes install-plan <workflow>` when unresolved runtime classes appear
3. `fetch <workflow>` when declared models are missing
4. `port convert <workflow> --out out/scratchpads/<id>.py --json`
5. `validate out/scratchpads/<id>.py`
6. `doctor out/scratchpads/<id>.py`
7. focused RunPod validation only after the local report has no hard porting errors

The RunPod corpus matrix writes an offline port report and a port-convert preview next to existing logs so GPU failures can be traced back to cheap local preflight results. Those reports are advisory artifacts; they do not make network checks mandatory.

## Battle Targets

Use a small source workflow first to verify the path quickly, then run the current production-parity target:

```bash
python -m vibecomfy.cli port check image/z_image --json
python -m vibecomfy.cli port check video/wanvideo_wrapper_22_wan_animate_preprocess_kijai --json
```

Add `--head-check-models` only when you specifically need URL reachability diagnostics.

## Roadmap

The first useful slice is intentionally pragmatic: source loading, helper stripping, custom-node pack inference, model asset analysis, opt-in URL HEAD checks, widget alias diagnostics, Python emission, CLI preflights, doctor guidance, and RunPod report artifacts.

Remaining work belongs in later batches:

- broaden CLI and parity tests across simple and WanAnimate paths;
- expand docs and agent guidance as new failure modes land;
- keep improving schema/object-info coverage for custom nodes;
- promote recurring RunPod failures into deterministic local checks where possible.
