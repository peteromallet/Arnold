vibecomfy: finish-higher-abstraction — finish the higher-abstraction authoring layer that `build-the-higher-abstraction-20260425-0953` planned but only partially executed. Most of the foundation is already shipped (blocks/, patches/, finalize_metadata, typed Handle, snapshots, authoring docs); this brief targets only the remaining gaps: typed artifacts, verb-native ops, router, plugin discovery, recipes, CLI loader unification, --json output, doctor patch suggestions, and the actual ready_templates refactor.

Source repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

# Why this exists

The original plan at `~/Documents/reigh-workspace/.megaplan/plans/build-the-higher-abstraction-20260425-0953/final.md` was a full 20-task brief that landed about 4 tasks (T1, T2, T5, T10) before its execute step returned `partial` twice and the plan stalled at `state=aborted`. Subsequent work (`design-a-concise-architecture-20260426-1555` → `p1-foundation-typed-handle-20260426-1927`) shipped a typed `Handle` dataclass and `wf.node(class_type, **kwargs).out(...)` authoring API, but did NOT cover the higher-abstraction layer (ops, artifacts, router, recipes, plugin discovery). So the framework exists but the user-facing "ordinary Python pipelines" surface does not.

The original plan doc is the source of truth for design decisions and watch items — read it before planning. This brief deliberately does not restate task details that are still accurate there. Where the original plan's design has been improved by p1-foundation (typed Handle, `wf.node().out()`), prefer the newer API.

# What is already shipped (DO NOT REDO)

Verified by inspection on 2026-04-27:

- `vibecomfy/blocks/` — `__init__.py`, `_utils.py`, `decode.py`, `encoding.py`, `latent.py`, `loaders.py`, `sampling.py`, `save.py`, `subgraph.py`, `video.py`. The `Handles` wrapper exists and is typed against the new `Handle` dataclass per p1-foundation.
- `vibecomfy/patches/` — `builtins.py`, `controlnet.py`, `gguf_unet.py`, `ltx_lowvram.py`, `requirements.py`, `resolution.py`, `save_prefix.py`, `seed.py`, `registry.py`, `types.py`. Original T4 patch list (gguf_unet, ltx_lowvram, resolution, seed, save_prefix) plus extras.
- `VibeWorkflow.finalize_metadata()` — `vibecomfy/workflow.py:97`. Helpers in `vibecomfy/metadata.py`.
- `Handle` dataclass + `wf.node(class_type).out(slot)` typed authoring API — `vibecomfy/blocks/__init__.py:16`, `vibecomfy/workflow.py:129`. Use these, not the older "string-only refs" assumption from the original plan.
- `tests/snapshots/` for 8 templates — pre-refactor API + class_type + widget_value snapshots already captured. Ready to drive snapshot-diff tests.
- `docs/authoring.md` (125 lines) — block + patch contracts, finalize_metadata, subgraph.opaque, "changes-handles → new template, decorates-handles → patch" rule. **Covers Layer 1 only — must be extended to cover Layer 2 (ops/artifacts/router/recipes/plugin discovery) — see C5 below.**
- `AGENTS.md` at repo root. **Covers Layer 1 only — must be extended to cover Layer 2 — see C5 below.**
- `vibecomfy/runtime/__init__.py` exports `run_embedded`, `run_embedded_sync`, `smoke_runtime`, `smoke_runtime_sync` (T10 done).
- `vibecomfy/commands/doctor.py` includes the `untyped_raw_ref` lint rule from p1-foundation (separate from T17 patch suggestions, which is still missing).

# What is still missing (THE SCOPE OF THIS PLAN)

Listed in dependency order. The original `final.md` task numbers are referenced for cross-checking; do not re-derive scope from scratch.

## Layer A — Typed surface (was original T11–T13)

A1. **`vibecomfy/artifacts.py`** — frozen `Artifact` dataclass (`workflow: VibeWorkflow`, `node_id: str`, `output_slot: int`, `kind: Literal['image','video','audio','latent','mask']`, `metadata: dict`) plus tag subclasses `Image`, `Video`, `Audio`, `Latent`, `Mask`. Methods: `preview_workflow() -> VibeWorkflow`, `compile() -> dict`, `run(*, runtime='embedded', **kwargs) -> RunResult` dispatching to `vibecomfy.runtime.{run_embedded_sync, run_sync}`.

   Note: original T10 listed this as "Depends on T1" and was marked done in `final.md`, but `vibecomfy/artifacts.py` does not exist on disk — verify and ship if missing. (Likely got rolled back when the plan aborted.)

A2. **`vibecomfy/ops/__init__.py` + `vibecomfy/ops/{image,video,audio,edit}.py`** — verb-native API returning typed Artifacts, lazy by default. Signatures from original T11:
   - `image.t2i(prompt, *, model=None, width=1024, height=1024, steps=None, seed=None, **overrides) -> Image`
   - `image.edit(image, instruction, *, model=None, **overrides) -> Image`
   - `video.t2v(prompt, *, model=None, width=None, height=None, length=None, fps=16, seed=None, **overrides) -> Video`
   - `video.i2v(image, prompt, *, model=None, length=None, fps=16, seed=None, **overrides) -> Video`
   - `audio.t2a(...)` raises `NotImplementedError('no audio template registered')`
   - `edit.qwen(image, instruction, **overrides) -> Image` delegates to `image.edit`

   Op body: pick `(template_id, [patch, ...])` via the router (A3); load via `cli_loader.load_workflow_any(template_id)` (B1) or `workflow_from_template`; build VibeWorkflow; apply `set_prompt`/`set_seed` and patches; return typed artifact pointing at the workflow's terminal save node from `outputs`.

A3. **`vibecomfy/router.py` + `vibecomfy/router_rules.py`** — hand-written decision table per original T12. Inputs: `verb`, `inputs` (image presence, requested model, requested resolution/length), `environment` (declared model presence + GPU memory hint, both pluggable; for v1 stub `environment` to `{}` and document that callers can override — exhaustive GPU detection is MP-5 territory).

   **Rules must be exhaustive across all 9 refactored templates** (see C1) — every template must be reachable via at least one rule. The full required rule set covering the 9 templates:
   - `('image', 't2i', model in {'z_image', None}) → 'image/z_image'`
   - `('image', 't2i', model='flux2_klein_4b') → 'image/flux2_klein_4b_t2i'`
   - `('image', 't2i', model='flux2_klein_9b_gguf') → 'image/flux2_klein_9b_gguf_t2i'`
   - `('video', 't2v', model in {'wan', None}) → 'video/wan_t2v'`
   - `('video', 't2v', model='ltx') → ('video/ltx2_3_t2v', [ltx_lowvram(), resolution(384, 256, 9)])`
   - `('video', 'i2v', model in {'wan', None}) → 'video/wan_i2v'`
   - `('video', 'i2v', model='ltx') → ('video/ltx2_3_i2v', [ltx_lowvram(), resolution(384, 256, 9)])`
   - `('image', 'edit', model in {'qwen', None}) → 'edit/qwen_image_edit'`
   - `('image', 'edit', model='flux2_klein_4b') → 'edit/flux2_klein_4b_image_edit_distilled'`
   - Fall back to `KeyError('no template for verb=...')`. After template selection, call `vibecomfy.patches.registry.find_applicable(workflow)` so router and doctor (C2) share the same probe. Data-driven rules in `router_rules.py` so plugins can extend via `register_route(verb, predicate, template_id, patches=())`.

A4. **Tests**: `tests/test_router.py` (rule table positive/negative + KeyError); `tests/test_ops.py` (`image.t2i('hello')` returns Image without executing; `Image.preview_workflow().compile('api')` has SaveImage and a node carrying the prompt; `preview_workflow().inputs['prompt']` registered — proves finalize_metadata wires through ops). Skip end-to-end runs in CI.

## Layer B — CLI unification + plugin discovery (was original T14–T16, T19)

B1. **`vibecomfy/cli_loader.py:load_workflow_any(path_or_id) -> VibeWorkflow`** with dispatch order from original T14:
   1. ready-template id (resolved through extended `ready_template_ids()` from B2) → `workflow_from_ready(id)`
   2. existing `.py` file → `load_scratchpad(path)`
   3. existing `.json` file → `convert_to_vibe_format(normalize_to_api(load_template(path), schema_provider=get_schema_provider('auto')), source_path=path, schema_provider=get_schema_provider('auto'))`
   4. fall through to existing index lookup

   Refactor `vibecomfy/commands/{doctor,inspect,run,validate,convert}.py` to call `load_workflow_any`. Either delegate or remove `vibecomfy/cli.py:23 _resolve_workflow_path` — do NOT leave duplicate logic. `tests/test_cli_loader.py` covering ready-template id, slash-separated id, scratchpad path, JSON path, missing-id `KeyError`.

B2. **`vibecomfy/extras.py:load_plugins()`** with three discovery sources per original T15:
   - project-local `./vibecomfy_extras/{blocks,patches,ops,recipes,ready_templates}/*.py`
   - user-global `~/.vibecomfy/{blocks,patches,ops,recipes,ready_templates}/*.py`
   - pip entry points `[project.entry-points."vibecomfy.plugins"] my_plugin = 'my_pkg:register'` whose `register(api)` callback receives `PluginAPI` with `register_block`, `register_patch`, `register_op`, `register_route`, `register_ready_root(path)`

   Replace module-level `READY_ROOT` in `vibecomfy/registry/ready.py` with `_ready_roots() -> list[Path]` returning built-in repo `ready_templates/`, project-local, user-global, plus paths registered via `register_ready_root`. `ready_template_ids()` walks all roots merging with built-in winning on duplicate ids (warn on collision). `_resolve_ready_path` walks all roots in order. Both call `vibecomfy.extras.ensure_plugins_loaded()` lazily; cache empty-plugin result so `workflows list` startup time does not regress. Expose `vibecomfy.ensure_plugins_loaded()` publicly. `tests/test_plugin_discovery.py` exercises one of each plugin type from each of: project-local fixture, user-global fixture (use `tmp_path` + monkeypatched HOME), entry-point fixture.

B3. **`--json` on `workflows list`, `nodes list`, `inspect`, `doctor`, `sources sync` summary, `analyze info`, `analyze diff`** per original T16. Default tab-separated output unchanged for backwards compat. Centralise printer choice in `vibecomfy/commands/_output.py`. For `inspect --json`, include `applicable_patches: [{name, rationale}]` from `find_applicable`. All `--json` paths use `load_workflow_any`.

B4. **Public exports** per original T19. Update `vibecomfy/__init__.py`: `Artifact`, `Image`, `Video`, `Audio`, `Latent`, `Mask`, `image`, `video`, `audio`, `edit`, `blocks`, `patches`, `router`, `ensure_plugins_loaded`, `load_workflow_any`. Smoke: `python -m vibecomfy.cli {sources,workflows,nodes,analyze,search,inspect,convert,validate,doctor,run,runtime,logs,runpod} --help` exits 0 for every subcommand. `scripts/runpod_runner.py` and `vibecomfy/commands/runpod.py` public surfaces unchanged.

## Layer C — Doctor + ready_templates refactor + recipes (was original T6, T7, T17)

C1. **Refactor the 9 snapshotted ready_templates into block-based builders** per original T6. Scope is **exactly the 9 templates with snapshots in `tests/snapshots/`** (z_image, flux2_klein_4b_t2i, flux2_klein_9b_gguf_t2i, qwen_image_edit, flux2_klein_4b_image_edit_distilled, wan_t2v, wan_i2v, ltx2_3_t2v, ltx2_3_i2v) — NOT the other ~40 templates in `ready_templates/{video,audio,image,edit}/`. The original plan said "eight" but listed nine; the snapshot directory confirms nine. The other ~40 templates (wanvideo_wrapper variants, ltx2_3_iamccs/runexx/lightricks variants, audio templates, etc.) stay on the legacy `API_WORKFLOW` + `build_api_ready_workflow` path until a follow-up plan refactors them; verify they still load and run unchanged after this work.

   Templates today still carry inline `API_WORKFLOW = {...}` dicts piped through `build_api_ready_workflow` (verified at `ready_templates/video/wan_t2v.py:1-15`). Convert:
   - WAN/LTX (`video/wan_t2v.py`, `video/wan_i2v.py`, `video/ltx2_3_t2v.py`, `video/ltx2_3_i2v.py`): compose loader → encoding → latent → sampling → decode → video.create → save, end with `wf.finalize_metadata()`. LTX additionally apply `ltx_lowvram` and `resolution(384, 256, 9)`; remove the old `_ready_template_policy` mutator.
   - Image/edit (`image/z_image.py`, `image/flux2_klein_4b_t2i.py`, `image/flux2_klein_9b_gguf_t2i.py`, `edit/qwen_image_edit.py`, `edit/flux2_klein_4b_image_edit_distilled.py`): use `subgraph.opaque` for UUID class types and ordinary blocks for surrounding loaders/save nodes.
   - Drop `convert_to_vibe_format(API_WORKFLOW, ...)`, literal `API_WORKFLOW = {...}`, and instructional `MarkdownNote` nodes. Each `build()` must return a VibeWorkflow whose `validate().ok` is True.
   - Authoring style: prefer the typed `wf.node(class_type, **kwargs).out(...)` API from p1-foundation over hand-built `add_node`/`connect` calls. (Improvement over the original plan, which predates the typed API.)

   **Critical**: snapshot diff in `tests/test_ready_templates.py` compares the refactored compile against `tests/snapshots/<id>.api.json` (already captured pre-refactor). LTX templates' existing `external_python_marker` assertion at `tests/test_ready_templates.py:19` must stay green — verify `ltx_lowvram` patch produces the same marker key/value before deleting `_ready_template_policy`.

C2. **Doctor patch suggestions** per original T17. After computing `report` in `vibecomfy/commands/doctor.py`, call `vibecomfy.patches.registry.find_applicable(workflow)` and print `Suggested patches: <name>: <rationale>` (or `suggested_patches` JSON array when `--json` is set). Verify each patch's `rationale(workflow) -> str` is implemented.

C3. **Delete `scripts/materialize_ready_templates.py`** per original T7 — but only after verifying its policy logic has been fully ported into `vibecomfy/patches/ltx_lowvram.py` and that the remaining ~40 non-refactored templates do not depend on it for materialization. Update `ready_templates/README.md` to describe the new authoring path and reference `docs/authoring.md`. Create `recipes/` at the **vibecomfy repo root** (`/Users/peteromalley/Documents/reigh-workspace/vibecomfy/recipes/`, not the parent reigh-workspace) with three runnable scripts:
   - `recipes/wan_i2v_lowres.py` — `wan_i2v + resolution(384, 256, 9)`
   - `recipes/wan_t2v_long.py` — `wan_t2v + resolution(832, 480, 81)` + custom seed
   - `recipes/dual_pass_t2i.py` — `z_image` followed by an upscaling chain via `subgraph.opaque` placeholder
   Each runnable via `python recipes/<name>.py` invoking `run_embedded_sync(build())`. Add `recipes/README.md` documenting "ready templates change handles, recipes decorate handles".

C4. **Phase-1 tests** per original T9. `tests/test_blocks.py`: smoke each block; assert produced `compile('api')` matches expected node count + widget keys. `tests/test_patches.py`: minimal workflow + `applies_to` (positive + negative) + `apply`; assert workflow diff matches the legacy materialize-script policy. `tests/test_finalize_metadata.py`: build small workflow with `add_node` + `connect` + `finalize_metadata()`; build equivalent JSON via `convert_to_vibe_format`; assert `inputs` keys, `outputs` list, and `requirements` are equal. Extend `tests/test_ready_templates.py` with snapshot diff (class_type set + widget-value set; node-id reordering allowed; MarkdownNote filtered at compile-time). Keep all existing assertions.

C5. **Extend `docs/authoring.md` and `AGENTS.md` to cover Layer 2** (per original T8 + T18 spirit, but focused on what's new). Both docs currently describe Layer 1 only (blocks, patches, finalize_metadata, subgraph.opaque). Extend them to also cover:
   - Typed `Artifact`s and the verb-native `image.t2i / video.t2v / video.i2v / image.edit / edit.qwen` API (lazy by default; `Artifact.run()` triggers execution).
   - The escape-hatch chain: `op() → Artifact → preview_workflow() → VibeWorkflow → compile() → API JSON → run()`. Every level publicly importable.
   - `router.pick(verb, **inputs)` — when ops use it implicitly vs. when callers use it directly.
   - Plugin discovery — project-local `./vibecomfy_extras/`, user-global `~/.vibecomfy/`, pip entry points; what `PluginAPI.{register_block, register_patch, register_op, register_route, register_ready_root}` does.
   - `recipes/` — worked compositions; the rule "ready templates change handles, recipes decorate handles" stated alongside the existing Layer 1 rule.
   - `audio.t2a` is a `NotImplementedError` stub until an audio ready template ships.
   - The `--json` output contract for `workflows list`, `nodes list`, `inspect`, `doctor`, `sources sync`, `analyze info`, `analyze diff`.
   Each doc stays ≤ ~200 lines combined-extension. Cross-link the two docs.

C6. **Declare plugin entry-point group in `pyproject.toml`.** The plugin discovery in B2 reads `[project.entry-points."vibecomfy.plugins"]`; verify `vibecomfy/pyproject.toml` declares the group (or a comment placeholder if the project uses a different pyproject layout). External packages discover via this group; without the declaration, only project-local + user-global discovery works.

## Final smoke

D1. **Acceptance smoke** (was original T20). Cheap first: `pytest tests/test_workflow_core.py tests/test_finalize_metadata.py tests/test_ready_templates.py -x`. Then new tests. Then full suite. Spot-check `python -m vibecomfy.cli doctor ready_templates/video/ltx2_3_t2v.py --json` (expect 0 LTX patch suggestions because the template already applied them) and a hand-stripped variant (expect `ltx_lowvram` suggested). Verify a fixture template under `vibecomfy_extras/ready_templates/` is resolvable by `workflow_from_ready`, `workflow_from_template`, `run --ready`, and `workflows list`. Throwaway script: `image.t2i('a tiny smoke test').preview_workflow().compile('api')` produces a SaveImage node — run, confirm, delete.

# Critical constraints (from original plan + new context)

- **VibeWorkflow remains the only editable IR.** Blocks must mutate via `add_node`/`connect`; patches must return VibeWorkflow; only `ingest/normalize.py` and `compile()` may edit API dicts directly.
- **Backward compatibility:** existing tests pass unchanged. Existing CLI flag surfaces stay identical. `scripts/runpod_runner.py` and `vibecomfy/commands/runpod.py` public-facing imports/CLI args must not diff.
- **MarkdownNote drop vs snapshot parity:** snapshots in `tests/snapshots/` were captured with MarkdownNote filtered at the source. Refactored templates drop MarkdownNote; snapshot test compares only runnable nodes. If you re-capture without filtering, parity test fails and refactor looks broken.
- **finalize_metadata parity is load-bearing:** `tests/test_finalize_metadata.py` must show `inputs/outputs/requirements` equal between block-built workflow + `finalize_metadata()` and `convert_to_vibe_format()` for an equivalent graph. If parity breaks, `set_prompt`/`set_seed`/inspect/op-terminal-artifact-lookup all silently degrade.
- **ltx_lowvram external_python_marker parity:** new patch must produce the same marker key/value as the legacy `_ready_template_policy` mutator before that function is deleted. Verify with `tests/test_ready_templates.py:19` still green.
- **`vibecomfy/cli.py:23 _resolve_workflow_path`** must be either deleted or made to delegate to `load_workflow_any` — duplicate logic in two places will diverge.
- **Plugin discovery cold-start cost:** `_resolve_ready_path` calls `ensure_plugins_loaded()` lazily; cache empty-plugin result so `workflows list` does not slow on every invocation.
- **Built-in ready-template ids win on duplicate id with plugin templates;** collisions emit a warning, not an exception.
- **Lazy ops contract:** verbs return Artifact objects without executing; `Artifact.run()` triggers execution; `Artifact.preview_workflow()` returns the VibeWorkflow without running. Pipelines compose via file-handoff — single-workflow chaining is out of scope for v1.
- **`audio.t2a` is a `NotImplementedError` stub** until an audio ready template ships. Document in AGENTS.md and `docs/authoring.md`.
- **Each block/patch/op file should stay under ~250 lines** with a single responsibility.
- **`subgraph.opaque` is a passthrough wrapper for UUID-class subgraph nodes;** it cannot be decomposed without unpacking the ComfyUI subgraph definition. Each affected template names the output slot it actually wires (typically slot 0 → 'out').
- **Repo is NOT a git repo.** Do NOT run `git init`. Verify `.git/` does not exist after each phase.

# Out of scope (do NOT do)

- Re-doing anything in the "already shipped" list — verify it still works, but don't reimplement.
- `vibecomfy/runtime/session.py` external-mode handling / `ExternalServerRestartRequired` — deferred to MP-5 by p1-foundation.
- Block library expansion beyond what's needed for the 8-template refactor.
- VibeFlow multi-stage orchestration, `wrap_api_dict`, ExternalPythonNode, stage-aware run-dirs / `flow_id` / `stage_index` — MP-5 territory per the design doc.
- Schema-backed validation, `/object_info` snapshot, `SCHEMA_TYPE_REGISTRY` — MP-6 territory.
- Compile-time serialization gate — MP-3 territory.
- RunPod end-to-end smoke as part of acceptance — `tests/smoke/test_p1_runpod.py` exists from p1-foundation but stays opt-in (`@pytest.mark.runpod`); do NOT execute during megaplan run.

# Key files to read first

Required reading before planning, in this order:

1. `~/Documents/reigh-workspace/.megaplan/plans/build-the-higher-abstraction-20260425-0953/final.md` — original 20-task plan with watch items, sense checks, and meta. Treat as load-bearing context; cross-reference T-numbers when scoping.
2. `vibecomfy/docs/python_composition_dsl_plan.md` — design doc the higher-abstraction work was meant to implement on top of (recently revised — read current version).
3. `vibecomfy/docs/python_composition_dsl_review.md` — issues the design closes.
4. `vibecomfy/docs/authoring.md` — block + patch contracts already documented.
5. `vibecomfy/AGENTS.md` — agent-facing contracts already documented (extend, don't duplicate).
6. `vibecomfy/blocks/__init__.py`, `vibecomfy/workflow.py:97-189` — `Handle`, `Handles`, `wf.node().out()`, `add_node`, `connect`, `compile`, `finalize_metadata`.
7. `vibecomfy/patches/registry.py`, `vibecomfy/patches/types.py` — `Patch`, `find_applicable`, registry.
8. `vibecomfy/runtime/__init__.py` and `vibecomfy/runtime/run.py` — `run_embedded_sync`, `run_sync`, `RunResult`.
9. `vibecomfy/registry/ready.py` — current `READY_ROOT` to be replaced with `_ready_roots()`.
10. `vibecomfy/cli.py:23` — `_resolve_workflow_path` to delegate or remove.
11. `ready_templates/video/wan_t2v.py` (one example of the current `API_WORKFLOW` shape to refactor) and `ready_templates/image/flux2_klein_4b_t2i.py` (parity anchor with snapshot).
12. `tests/snapshots/` — all 8 template snapshots already captured; don't recapture.
13. `tests/test_ready_templates.py:19` — `external_python_marker` assertion that LTX refactor must keep green.
14. `scripts/materialize_ready_templates.py:58-93` — policy logic to migrate into patches before deletion.

# Acceptance

- `from vibecomfy import Artifact, Image, Video, Audio, Latent, Mask, image, video, audio, edit, blocks, patches, router, ensure_plugins_loaded, load_workflow_any` succeeds.
- `image.t2i('hello').preview_workflow().compile('api')` returns a dict with a SaveImage node and the prompt registered as an input.
- `router.pick('video', 'i2v', model='ltx')` returns the LTX template + lowvram + resolution patches.
- `vibecomfy doctor` (text + `--json`) lists applicable patches; zero on a policy-applied LTX template, `ltx_lowvram` on a stripped one.
- All 9 snapshotted ready_templates compile to a snapshot-equivalent graph (modulo node-id reordering + MarkdownNote stripping). The other ~40 unrefactored templates still load and run unchanged.
- The router has at least one rule reaching every one of the 9 refactored templates; `tests/test_router.py` covers each one.
- `vibecomfy_extras/ready_templates/` fixture template is resolvable through `workflow_from_ready`, `workflow_from_template`, `run --ready`, `workflows list`.
- `python -m vibecomfy.cli {sources,workflows,nodes,analyze,search,inspect,convert,validate,doctor,run,runtime,logs,runpod} --help` exits 0 for every subcommand.
- `scripts/materialize_ready_templates.py` deleted; `recipes/` exists at vibecomfy repo root with three runnable scripts.
- `docs/authoring.md` and `AGENTS.md` describe Layer 2 (ops, artifacts, router, recipes, plugin discovery, escape-hatch chain, `audio.t2a` stub, `--json` contract).
- `vibecomfy/pyproject.toml` declares the `[project.entry-points."vibecomfy.plugins"]` group.
- Full pytest suite passes. RunPod smoke remains opt-in and unexecuted.
- `.git/` still absent.
