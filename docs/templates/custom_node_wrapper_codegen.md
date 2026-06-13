# Custom-node wrapper codegen pipeline

> **Scope.** This document covers Sweep 3 from [`decorator_template_emitter_completion.md`](decorator_template_emitter_completion.md): generating typed Python wrappers for ComfyUI custom-node packs so that template emission stops falling back to `raw_call('UnknownClass', '<node_id>', widget_0=...)` whenever a class is missing from `vibecomfy/nodes/`.

## Why

Today every typed wrapper in `vibecomfy/nodes/` is hand-written. When a new pack lands (or upstream adds new classes to an existing pack), templates that touch the pack emit `raw_call(...)` instead of typed calls. The root cause is structural — hand-writing wrappers does not scale and is the single biggest contributor to the "this class isn't supported" rough edge.

The pipeline in this doc replaces hand-writing with **discovery + codegen**: ingest the pack's `INPUT_TYPES` / `RETURN_TYPES` declarations from one of four sources, render a deterministic typed wrapper module, and write it to `vibecomfy/nodes/<slug>.py`.

## Architecture

```
+-------------------+      +---------------------+      +-----------------------+
|  discovery        | ---> |  ClassSpec list     | ---> |  codegen             |
|  (4 sources)      |      |  (normalized)       |      |  (Python module)     |
+-------------------+      +---------------------+      +-----------------------+
        |                                                       |
        |                                                       v
        |                                              vibecomfy/nodes/<slug>.py
        v
   provenance string                                  with header:
                                                       # vibecomfy:generated
                                                       # source_sha256: ...
                                                       # source: ...
```

Two new modules:

- **`vibecomfy/porting/wrapper_discovery.py`** — exposes `discover_pack(pack_slug)` and `discover_all()`. Returns a list of `ClassSpec` per pack.
- **`vibecomfy/porting/wrapper_codegen.py`** — exposes `render_pack(pack_slug, specs)` and `render_widget_schema(specs)`. Returns a `RenderResult` carrying the rendered Python text, the path to write it to, and a stable SHA-256 fingerprint.

The CLI surface lives in `vibecomfy/commands/nodes.py`:

```
vibecomfy nodes generate-wrappers <pack-slug>   [--source live|cache|snapshot|source|auto] [--out DIR] [--dry-run] [--diff] [--json]
vibecomfy nodes generate-wrappers --all
vibecomfy nodes wrapper-status                  [--json]
vibecomfy nodes generate-widget-schema <pack>   [--source ...] [--json]
```

## Discovery — sources and precedence

Four sources, tried in precedence order. The orchestrator returns the **first** non-empty result; it does not merge across sources (different sources can disagree on widget metadata and a merged spec hides the disagreement).

| # | Source     | Path                                                  | Where the data comes from                                           | Coverage |
|---|------------|-------------------------------------------------------|---------------------------------------------------------------------|----------|
| 1 | `live`     | `<server_url>/object_info`                            | Running ComfyUI server's HTTP endpoint                              | Best — combo enums are populated from `folder_paths.get_filename_list(...)` and other runtime calls |
| 2 | `cache`    | `vibecomfy/porting/cache/object_info/<slug>@<rev>.json` | `/object_info` dumps captured locally during a previous session    | Same shape as live; depends on cache freshness |
| 3 | `snapshot` | `vibecomfy/porting/object_info/<slug>@<rev>.json`       | Checked-in snapshots (e.g. captured on a RunPod runtime)            | Same shape as live; deterministic across machines |
| 4 | `source`   | `custom_nodes/<slug>/**/*.py`                         | AST parse of pack source — looks at `NODE_CLASS_MAPPINGS`, `INPUT_TYPES`, `RETURN_TYPES`, `RETURN_NAMES` | Offline; covers packs not in any object_info dump |

Default precedence is `("cache", "snapshot", "source")` — `live` is opt-in via `--server-url`.

### What AST parsing can't recover

The `source` fallback uses `ast.parse` — never `exec`, never `importlib.util.spec_from_file_location`. This matters because most ComfyUI packs import `torch`, `cuda`, or pack-specific C extensions at module load, and discovery must not require a GPU or even a Python env that can satisfy those imports.

That trade-off means **AST parsing cannot recover**:

- **COMBO enum values that come from runtime calls.** A pack that declares `("vae_name", (folder_paths.get_filename_list("vae"),))` produces an `InputFieldSpec(type="COMBO", options=None)` from `source`. From `live` or `cache`, `options` is populated with the actual list.
- **Mappings built at import time** from generated tables (e.g. metaprogrammed registration loops). The AST parser only handles `NODE_CLASS_MAPPINGS = {"Name": ClassName, ...}` literal-dict form.
- **Class-level decorators** that mutate `INPUT_TYPES` after the fact.

When these matter, prefer `live` or a fresh `cache` dump. `source` is the right fallback for *offline* discovery — wrapper signatures will be type-correct but combo defaults may be `None`.

## Codegen — what the rendered module looks like

One module per pack at `vibecomfy/nodes/<slug>.py`. The slug is lowered and non-identifier chars become underscores: `rgthree-comfy` → `rgthree_comfy`, `ComfyUI-LTXVideo` → `comfyui_ltxvideo`.

Each ComfyUI class becomes a typed wrapper class with a single static `add()` method:

```python
class KSampler:
    """Typed wrapper for the ComfyUI node class ``KSampler``."""

    CLASS_TYPE = "KSampler"
    OUTPUTS: tuple[str, ...] = ("LATENT",)
    OUTPUT_TYPES: tuple[str, ...] = ("LATENT",)

    @staticmethod
    def add(
        wf: "VibeWorkflow",
        *,
        model: "Handle",
        positive: "Handle",
        negative: "Handle",
        latent_image: "Handle",
        seed: int = 0,
        steps: int = 20,
        cfg: float = 8.0,
        sampler_name: str = "euler",
        scheduler: str = "normal",
        denoise: float = 1.0,
    ) -> "_NodeBuilder":
        """Add a ``KSampler`` node to ``wf`` and return the builder."""
        return wf.node(
            "KSampler",
            model=model,
            positive=positive,
            negative=negative,
            latent_image=latent_image,
            seed=seed,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            denoise=denoise,
        )
```

Conventions:

- **Static `add(wf, ...)` instead of `__init__`.** The wrapper is a *namespace*, not an instance — calling `KSampler.add(wf, ...)` is exactly equivalent to `wf.node("KSampler", ...)` and returns the same `_NodeBuilder`. This avoids constructing extra Python objects and lets callers freely chain `.out(slot)` as they would with `wf.node()`.
- **Link sockets typed as `"Handle"`.** Fields whose ComfyUI type is in `LINK_SOCKET_TYPES` (or any `ALL_CAPS_WITH_UNDERSCORES` socket) get the `Handle` annotation; scalars get `int` / `float` / `str` / `bool`.
- **Field ordering: required-link → required-scalar → optional**, alphabetized within each tier. This makes signatures deterministic without breaking callers (everything after `wf` is keyword-only).
- **Non-identifier field names** (rare; `double_blocks.0.` etc.) route through a `**{"raw.name": py_name, ...}` spread because Python kwargs forbid dots and spaces.
- **One section comment per source-of-truth.** The generated header lists the pack slug, full provenance, deterministic `source_sha256`, generator version, and the regen command.

## Determinism

Re-running `nodes generate-wrappers <pack>` against the same source data produces **byte-identical output**:

- Specs are sorted by `class_type`.
- Inputs within a spec are sorted by name (within tier).
- The `generated_at` timestamp defaults to `1970-01-01T00:00:00+00:00`; pass `--no-deterministic-timestamp` to opt in to wall-clock.
- Defaults and combo lists are dumped via `json.dumps(sort_keys=True)`.
- `source_sha256` is the SHA-256 of the canonical JSON representation of the input `ClassSpec`s (after sorting). It changes iff the input *data* changed, regardless of which discovery source produced it.

Drift detection is built on this: `nodes wrapper-status` compares the SHA in each existing wrapper's header against the SHA a fresh discovery would produce. States are:

- `current` — header SHA matches fresh discovery; no regen needed.
- `drifted` — fresh discovery produces a different SHA; regen would change the file.
- `missing` — no wrapper file exists yet for this lockfile pack.
- `hand_written` — file exists but has no generated-header marker; do not regenerate without confirmation.
- `drift_unknown` — file exists with marker, but no discovery source is available right now.

## When to regenerate

- **A pack's lockfile pin changed** (`custom_nodes.lock` updated to a new commit). Regenerate; the upstream class set may have changed.
- **A new `object_info` snapshot landed** in `vibecomfy/porting/object_info/` or `vibecomfy/porting/cache/object_info/`. Regenerate the affected pack.
- **`nodes wrapper-status --json` shows `drifted`.** Inspect the diff (`generate-wrappers <pack> --dry-run --diff`); commit the regen if it's an intentional pickup.

## When to fall back to hand-writing

The codegen output covers ~95% of pack classes. Hand-writing makes sense for:

- **Helper / UI classes** (`Note`, `MarkdownNote`, `SetNode`, `GetNode`, `Reroute`) — these have special elision rules in the emitter and shouldn't be exposed as typed callable wrappers anyway.
- **Classes with semantically meaningful method shapes beyond `add()`.** The current generator only emits the `add()` factory. If you want methods like `KSampler.from_preset(...)` or `KSampler.merge_with(...)`, write them by hand in a sibling file (`vibecomfy/nodes/<slug>_extras.py`) and re-export.
- **Classes where the rendered annotation is wrong** because the discovery source could not capture the type. The fix is usually a fresher `live` or `cache` dump; only fall back to hand-writing when the upstream is genuinely under-typed.

When you do hand-write, leave the generated file alone (or delete it entirely) and put the hand-written class in a separately-named module so future regens don't fight you. The header marker `# vibecomfy:generated` is the contract: only files carrying it should be overwritten by codegen.

## WIDGET_SCHEMA tie-in

`nodes generate-widget-schema <pack>` emits a chunk of Python text suitable for pasting into `vibecomfy/porting/widget_schema.py`'s `WIDGET_SCHEMA` dict. Each entry lists the non-link input fields in declaration order, with the upstream provenance commented inline. This is the auxiliary half of Sweep 3 — it lets a single regen cover both Categories B *and* C from the strategy doc, so new packs no longer need a manual widget-schema curation pass either.

The widget-schema output is *additive* — pipe it through your editor and merge it with the existing `WIDGET_SCHEMA` dict. The CLI does not write directly to `widget_schema.py` because the dict has other curation-only entries that must not be touched.

## How to regenerate one pack

```bash
# Cheap dry-run that shows the diff:
python -m vibecomfy.cli nodes generate-wrappers ComfyUI-LTXVideo --source snapshot --dry-run --diff

# Commit the change:
python -m vibecomfy.cli nodes generate-wrappers ComfyUI-LTXVideo --source snapshot

# Or, for every pack in custom_nodes.lock at once:
python -m vibecomfy.cli nodes generate-wrappers --all --source auto
```

`--source auto` is the default precedence: cache, snapshot, source. Use `--source live --server-url http://...:8188` to ingest from a running ComfyUI server (most accurate; populates dynamic combo enums).

## Drift detection workflow

```bash
# What's the state of every wrapper relative to its source?
python -m vibecomfy.cli nodes wrapper-status --json | jq '.packs[] | select(.state != "current")'

# For each drifted pack, preview the change before committing:
for pack in $(python -m vibecomfy.cli nodes wrapper-status --json | jq -r '.packs[] | select(.state == "drifted") | .pack'); do
    python -m vibecomfy.cli nodes generate-wrappers "$pack" --dry-run --diff
done
```

In CI, the cheapest check is `nodes wrapper-status --json` followed by a `jq` assertion that no pack is `drifted`. Until that's wired up, the pre-merge convention is: regenerate locally, commit, push.

## Future work

- **Multi-revision drift handling.** Today `wrapper-status` only knows the most recent revision in the snapshot/cache dir. A `wrapper-status --since <commit>` flag could surface what's changed between two versions of a pack.
- **Combo-enum extraction from `source`.** A constrained interpreter that evaluates `folder_paths.get_filename_list("vae")` against a mock folder layout would let `source`-only discovery populate combo defaults without a runtime.
- **Output-port aliasing.** Some packs return tuples where `RETURN_NAMES` doesn't match the natural API name (e.g. WanVideoWrapper's `(latent, mask)`). The codegen could emit `.latent()` / `.mask()` convenience accessors on top of `.out(0)` / `.out(1)`.
- **Per-class hand-overrides.** A small `vibecomfy/nodes/_overrides.py` could list classes whose generated `add()` signature should be augmented (e.g. adding a `_outputs=("latent","mask")` kwarg for tuple-unpacked usage) without forking the whole generator.
- **CI drift gate.** Once the on-disk wrappers are the source of truth, a CI job can fail the build if `nodes wrapper-status --json` reports any `drifted` entry whose pack is also pinned in `custom_nodes.lock`.

## Reference

- Strategy doc: [`decorator_template_emitter_completion.md`](decorator_template_emitter_completion.md) — Sweep 3
- Existing related docs: [`docs/custom_nodes.md`](../custom_nodes.md) for pack lifecycle (install/lock/restore)
- Discovery + codegen modules: `vibecomfy/porting/wrapper_discovery.py`, `vibecomfy/porting/wrapper_codegen.py`
- CLI: `vibecomfy/commands/nodes.py` — handlers `_cmd_nodes_generate_wrappers`, `_cmd_nodes_wrapper_status`, `_cmd_nodes_generate_widget_schema`
- Tests: `tests/test_wrapper_discovery.py`, `tests/test_wrapper_codegen.py`
