# AGENTS.md

## Project Context

VibeComfy is a Python package for discovering, converting, validating, and running ComfyUI workflows from Python scratchpads and JSON workflow inputs. The primary package lives in `vibecomfy/`, tests live in `tests/`, documentation lives in `docs/`, and ready workflow examples live in `ready_templates/`.

## Working Rules

- Work from the repository root: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.
- Treat the worktree as shared. Do not revert, overwrite, or clean up edits you did not make.
- Keep changes scoped to the requested task. Avoid unrelated refactors, generated-output churn, and broad formatting changes.
- Prefer explicit, local registries and small modules over implicit discovery unless a task specifically asks for discovery.
- Do not change runtime behavior, templates, workflow corpus files, or generated snapshots unless the task explicitly covers those areas.
- If a change needs coordination with another interface or parallel task, document the integration note instead of guessing across ownership boundaries.

## Common Commands

- Run the full test suite with `pytest`.
- Run focused tests with `pytest tests/test_cli.py` or the relevant test file.
- Exercise the CLI locally with `python -m vibecomfy.cli ...`.
- Sync indexes only when a task or test requires it: `python -m vibecomfy.cli sources sync`.

## CLI Guidance

- The console entrypoint is `vibecomfy = "vibecomfy.cli:main"`.
- Top-level command registration belongs in `vibecomfy/commands/__init__.py`.
- Individual command modules should expose `register(subparsers)` and keep command execution in private `_cmd_*` helpers.
- Keep command registration explicit. Do not add plugin discovery or dynamic filesystem scanning unless the task asks for it.
- `workflows list`, `nodes list`, `inspect`, `doctor`, `sources sync`, `analyze info`, and `analyze diff` support `--json`; keep existing text output stable.

## Layer 2 Authoring

See [docs/authoring.md](docs/authoring.md) for the user-facing contract. Keep these agent rules aligned with that doc.

- The public lazy ops are `image.t2i`, `video.t2v`, and `video.i2v`; they return typed `Artifact` objects without executing. `Artifact.run()` executes, and `Artifact.preview_workflow()` returns the editable `VibeWorkflow`.
- The escape-hatch chain is `op() -> Artifact -> preview_workflow() -> VibeWorkflow -> compile() -> API JSON -> run()`. Every level is intentionally public.
- `audio.t2a`, `image.edit`, and `edit.qwen` are `NotImplementedError` stubs in v1.
- `image.t2i(model="flux2_klein_9b_gguf")` and `image.edit(model in {"qwen", "flux2_klein_4b"})` are not exposed via verb-native ops. Use `load_workflow_any("image/flux2_klein_9b_gguf_t2i")` or `load_workflow_any("edit/qwen_image_edit")` and edit the `VibeWorkflow` directly until MP-6 ships schema-backed UUID-subgraph input validation.
- `router.pick(verb_kind, verb_name, **inputs)` returns `RouterResult(template_id, explicit_patches, applicable_patches)`. Treat `applicable_patches` as the remaining patch gap after loading; it should be empty for as-shipped LTX templates.
- Plugin discovery is explicit and lazy through `ensure_plugins_loaded()`: project-local `./vibecomfy_extras/`, user-global `~/.vibecomfy/`, and pip entry points in `vibecomfy.plugins`. `PluginAPI` exposes `register_block`, `register_patch`, `register_op`, `register_route`, and `register_ready_root`.
- Ready templates change handles; recipes decorate handles. This complements the Layer 1 rule: changes-handles -> template, decorates-handles -> patch.
- `wf.register_input(name, node_id, field, value=None)` is the public helper for authored inputs that metadata inference cannot discover.
- Prompt registration is expected for exactly these routed templates: `image/z_image`, `image/flux2_klein_4b_t2i`, `video/wan_t2v`, `video/wan_i2v`, `video/ltx2_3_t2v`, and `video/ltx2_3_i2v`.
- `OUTPUT_NODE_NAMES` includes `SaveVideo`, `SaveAudio`, and `SaveAudioMP3`; `finalize_metadata()` sorts outputs by node id deterministically.

## Testing Expectations

- Add or update focused tests when changing command routing, parser behavior, workflow conversion, validation, search, or runtime-facing code.
- Prefer subprocess CLI smoke tests only when behavior depends on process-level invocation or current working directory.
- Keep tests deterministic and avoid requiring ComfyUI, RunPod, network access, or local model files unless the test is explicitly marked or scoped for that environment.
