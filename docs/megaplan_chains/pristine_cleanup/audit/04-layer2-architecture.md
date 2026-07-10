## Lens 4 Audit: Layer 2 Architecture Coherence

### HIGH

1. **`ltx_lowvram` patch hardcodes node IDs from one template — breaks the patch contract entirely.**
   `vibecomfy/patches/ltx_lowvram.py:23-44` — `_update_node` targets IDs like `"3059"`, `"4979"`, `"4010"`, `"3940"`. These are UUIDs from a *specific* LTX workflow. On any other LTX graph, those `workflow.nodes.get(node_id)` calls return `None` and silently no-op. The `applies_to` predicate checks generically for `LTX*` class types, but `apply` is hard-bound to one template's internal topology. This is not a patch — it's a recipe with delusions of reuse.

2. **`gguf_unet` patch changes class types on loader nodes (handle-changing behavior).**
   `vibecomfy/patches/gguf_unet.py:21-38` — Swaps `UNETLoader` → `UnetLoaderGGUF` and changes VAE filenames. This **changes what handles the loader produces** (different node class = different output semantics). The CLAUDE.md rule: *changes-handles → block; decorates-handles → patch*. This should live in `vibecomfy/blocks/`, not patches.

3. **`controlnet` patch adds 3 new nodes + splices into the conditioning chain.**
   `vibecomfy/patches/controlnet.py:60-92` — Adds `ControlNetLoader` + 2× `ControlNetApplyAdvanced`, wires them with `connect`/`replace_edge`. Adds new handle-producing nodes. CLAUDE.md defines patches as "decorate" (tweak widgets, splice into edges, swap classes). Adding multiple net-new nodes that introduce new handle types is block territory.

### MEDIUM

4. **`Patch` type docstring explicitly contradicts CLAUDE.md.**
   `vibecomfy/patches/types.py:12-16` — "Patches are free to use *any* VibeWorkflow method... they may add nodes, change widget/input values, splice nodes... or even manipulate edges directly." CLAUDE.md (line 74) says patches *decorate*: "tweaks a widget, splices a node into an edge, swaps a class." Adding nodes is not listed. The docstring licenses exactly the behavior that causes findings #2 and #3.

5. **`resize_schema.py` is an orphan in the patches directory.**
   `vibecomfy/patches/resize_schema.py` — It's a plain function `ensure_resize_image_mask_schema(workflow) -> VibeWorkflow` that edits inputs/edges. It is *not* a `Patch` dataclass, not exported from `patches/__init__.py`, not registered in `builtins.py`. It sits in the patches directory but obeys none of the patch conventions.

6. **`registry.py` duplication across patches/ and ops/ with inconsistent APIs.**
   `vibecomfy/patches/registry.py:10-34` vs `vibecomfy/ops/registry.py:10-29` — Both are module-level mutable global registries. Patches uses `dict[str, Patch]` with `register()`; ops uses `dict[tuple[str,str], Op]` with `register_op()`. Patches has `registered_patches()` + `find_applicable()`; ops has only `lookup_op()`. Patches has a `bootstrap_builtin_patches` concept; ops has override warnings. Same pattern, different shape — no shared base.

### LOW

7. **Mixed factory-vs-singleton convention in `patches/__init__.py`.**
   `vibecomfy/patches/__init__.py:9-32` — `resolution`, `seed`, `save_prefix` are factory functions (call to get a `Patch`); `controlnet`, `gguf_unet`, `ltx_lowvram` are module-level `Patch` singletons. The `__all__` list mixes both categories. Users must know which is which.

8. **Thin recipes that are just single-patch applications.**
   `recipes/wan_i2v_lowres.py:8-11`, `recipes/wan_t2v_long.py:8-12` — These are `load → resolution(...).apply(wf) → return wf`. CLAUDE.md says recipes "combine workflows + patches + blocks + ops + custom logic." A one-patch-and-done function is a patch-application, not a compose recipe.

---

**Worst thing in this lens:** Finding #1 — `ltx_lowvram` hardcodes node IDs from one workflow template (line 23-44), silently no-oping on any other LTX graph while its `applies_to` predicate returns `True` for all of them. It's a fragile, lying patch that will cause silent failures for anyone who loads a different LTX template.