# Subagent prompt: family-aware CLI overrides (no more universal --prompt/--steps)

You are working in `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`. Self-contained task. Do not modify the materializer, the validator, the watchdog, or the model-staging logic.

## Problem

The CLI flags `--prompt` and `--steps` (registered in `vibecomfy/commands/run.py:60-62`) are advertised as universal but only work correctly for mainline image workflows. They route through `vibecomfy/workflow.py:set_prompt`/`set_steps` → `set_input("prompt", ...)`, which targets whatever node was first registered as the canonical "prompt input" by `vibecomfy/metadata.py:_register_common_inputs` (lines 15-26).

Registration is field-name-based: any node with a field named `text`, `prompt`, `positive`, or `positive_prompt` becomes the prompt target. First match wins. This silently routes `--prompt` to the wrong node in non-image families:

- **WanVideoWrapper**: custom prompt nodes accept fields named `text`/`prompt` for sampler conditioning, not image-style positive prompts. The override mutates the wrong field.
- **ACE Step audio**: text encoders take *audio tag strings*, not image prompts. The override produces nonsense conditioning.
- **Workflows with multiple text fields** (negative prompts, condition prompts, talking-head prompts): the first registered field wins, but it's frequently not the one the user meant.

The matrix has been working around this with a case-statement in `scripts/runpod_corpus_matrix.py:264-281`:

```bash
case "$id" in
  wanvideo_wrapper*) workflow_override_args=(--seed 123) ;;  # strip --prompt/--steps
  *) if [ "$media" = "audio" ]; then workflow_override_args=(--seed 123); fi ;;
esac
```

That workaround belongs at the CLI/registration layer, not in the matrix. The doc entry is `Generic prompt and step overrides assume mainline image nodes` in `docs/hiddenswitch_incompatibilities.md` (Root cause: `local_bug`).

## Scope

Push the family-detection into `_register_common_inputs` so `--prompt` and `--steps` only attach to nodes whose class_type is in a known mainline-image-or-sampler allowlist. For workflows with no matching node, the override registers no input and the CLI prints a clear error if invoked. Delete the matrix-level workaround.

`--seed` stays universal and unchanged. `seed` and `noise_seed` are well-defined across families.

## Files to read

- `vibecomfy/commands/run.py` — CLI surface (`--prompt`, `--steps`, `--seed` registration; `_cmd_run` handler).
- `vibecomfy/metadata.py` — `_register_common_inputs` (the field-name-based registration).
- `vibecomfy/workflow.py:84-91` — `set_prompt` / `set_steps` (one-liners that dispatch to `set_input`).
- `vibecomfy/workflow.py:108+` — `set_input` (the actual mutation; understand failure modes).
- `scripts/runpod_corpus_matrix.py:257-281` — the case-statement workaround that this work removes.
- `docs/hiddenswitch_incompatibilities.md` — the doc entry; you'll update it when this lands.

## What to build

1. **Class-type allowlists in `vibecomfy/metadata.py`**:

   ```python
   PROMPT_NODE_CLASSES = {
       "CLIPTextEncode",
       "CLIPTextEncodeSDXL",
       "CLIPTextEncodeFlux",
       # add the exact mainline classes used by image families in the corpus —
       # check workflow_corpus/official/image/*.json and edit/*.json for class_types
       # that appear paired with a "text" or "prompt" field
   }

   STEPS_NODE_CLASSES = {
       "KSampler",
       "KSamplerAdvanced",
       "SamplerCustom",
       "SamplerCustomAdvanced",
       # add the exact mainline sampler classes
   }
   ```

   Source these by grep'ing `workflow_corpus/official/{image,edit}/*.json` for the actual class_types in use. Do not guess. Keep the lists small and specific — when in doubt, leave a class out and let the CLI error tell us.

2. **Tighten `_register_common_inputs`**:

   - Register `workflow.inputs["prompt"]` only if `node.class_type in PROMPT_NODE_CLASSES`.
   - Register `workflow.inputs["steps"]` only if `node.class_type in STEPS_NODE_CLASSES`.
   - `seed`/`noise_seed`/`model` registration is unchanged.

3. **CLI behavior in `vibecomfy/commands/run.py:_cmd_run`**:

   - When `--prompt` is supplied but `workflow.inputs.get("prompt")` is `None`: print a clear error to stderr and exit nonzero. Message must name the workflow, the flag, and suggest editing the source workflow's prompt fields directly. Do not silently no-op.
   - Same for `--steps`.
   - `--seed` behavior unchanged.

4. **Delete the matrix workaround**:

   - In `scripts/runpod_corpus_matrix.py`, the `case "$id" in ... wanvideo_wrapper*) ... esac` block (lines ~263-281) is the workaround. Remove the prompt/steps stripping branches; leave any non-prompt-related logic (timeouts, cache flags) intact.
   - The matrix's universal `workflow_override_args=(--steps 1 --seed 123 --prompt "...")` line stays as the default; the CLI now enforces correctness per-workflow. Custom-node families that previously needed stripping will still get the override args passed to them, but the CLI will refuse to apply prompt/steps if there's no eligible target — which is the desired behavior.
   - Actually: the matrix calls `comfyui run-workflow` (HiddenSwitch CLI) for the baseline, and `vibecomfy.cli run` for the converted scratchpad. The HiddenSwitch CLI is independent of vibecomfy and has its own override semantics. **Only delete the workaround for the `vibecomfy` invocation; leave the `comfyui run-workflow` invocation as-is.** Inspect both code paths carefully before removing anything.

5. **Update `docs/hiddenswitch_incompatibilities.md`**:

   - The entry `Generic prompt and step overrides assume mainline image nodes` currently lists `Status: Mitigated` with a "policy" workaround. After this work, the underlying cause is fixed. Update the entry to `Status: Fixed (local)` (or add this status to the legend if needed) and note the commit/PR. Keep the entry — historical record matters.

## Constraints

- **Reversibility**: behind an env var `VIBECOMFY_LEGACY_OVERRIDES=1` you can restore the old field-name-only registration. Default is the new behavior.
- **No new deps**.
- **Don't touch `set_input` semantics** — only the registration layer changes.
- **Don't add a per-workflow allowlist override** (e.g. metadata blocks in scratchpads). The class-type allowlist is the single source of truth. If a workflow legitimately uses a custom prompt class that should accept `--prompt`, add it to `PROMPT_NODE_CLASSES` with a comment explaining why.
- **Source the allowlists from real workflows**, not from imagination. Grep the corpus and only add classes you've confirmed appear in image/edit families.

## Acceptance

- The 14 runtime-green image/edit workflows still accept `--prompt "..."` and apply it correctly.
- A WanVideoWrapper workflow invoked with `--prompt "..."` now exits with a clear error directing the user to edit the source instead.
- An ACE Step audio workflow invoked with `--prompt "..."` errors the same way.
- The matrix runs end-to-end without the workaround block.
- New tests in `tests/test_metadata_registration.py`: registration happens for image classes, does not happen for WanVideoWrapper / ACE / unknown custom classes; and in `tests/test_run_command.py`: CLI errors loudly when override is supplied but unwired.
- Update one paragraph in `docs/hiddenswitch_incompatibilities.md` reflecting the new state.

## Out of scope

- A typed `--input KEY=VALUE` flag for arbitrary input mutation (separate work).
- Support for `--negative-prompt`, `--cfg`, or other overrides (separate work).
- Modifying the HiddenSwitch `comfyui run-workflow` baseline path; only `vibecomfy.cli run` changes.
- Auto-detecting the right prompt node when there are multiple eligible candidates (current behavior — first match — is fine for now).

## When done

Report:
- Final allowlist contents and the workflows you grepped to derive them.
- The exact lines deleted from `runpod_corpus_matrix.py`.
- Sample stderr messages from the new "no eligible target" error path (so we can verify they are actionable).
