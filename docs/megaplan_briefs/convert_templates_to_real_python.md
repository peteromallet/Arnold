# Convert ready_templates to real Python — idea doc

Status: idea / pre-megaplan. Captures the realization from the layer-2 runpod test
debugging session and the architecture we landed on. Not yet a plan; meant to be
the input to a light megaplan.

## Context: what's broken today

`ready_templates/{image,video,edit,audio}/*.py` (50 files) ship as JSON-flavored
Python — they look like Python but they're really workflow JSON pasted into a
tuple. Two shapes coexist:

- **41 LEGACY** — `API_WORKFLOW = {node_id: {"class_type": "X", "inputs": {...}}}`
  + `build_api_ready_workflow(...)`. Class types are real ComfyUI names; inputs
  are real names. Effectively flat ComfyUI API JSON written as a Python dict.
- **8 AUTHORED** — `NODES = (("9", "SaveImage", {...}), ("76", "9b9009e4-...", {widget_0: ..., widget_1: 1024, ...}), ...)`
  + `build_authored_ready_workflow(...)`. **References subgraphs by UUID class
  type with positional `widget_0..widget_N` indices.** The actual subgraph
  definition (10–14 internal nodes) lives only in the source
  `workflow_corpus/official/*.json` under `definitions.subgraphs`.

Failure observed on a real RTX 4090 pod:
- vibecomfy compiles the AUTHORED templates with UUID class types passing through
- HiddenSwitch ComfyUI rejects them: `missing_node_type` / "Node '9b9009e4-...'
  not found. The custom node may not be installed."

`backend="graphbuilder"` doesn't fix it (the UUID survives the call). The runpod
test plan can't pass until the templates are converted.

## What we proved

`ready_templates/image/z_image.py` hand-rewritten as direct `wf.node()` calls
(named ComfyUI classes, named widget kwargs, bound variables for connections,
no UUID, no widget_0/1/2) **runs end-to-end on a real RTX 4090 pod**. The
template's compile produces an API dict HiddenSwitch accepts; models download
from HuggingFace; KSampler completes; SaveImage writes the output.

The shape is the same as upstream HiddenSwitch's `GraphBuilder` — vibecomfy's
`wf.node(class_type, **kwargs).out(slot)` is essentially a re-export. Not
reinventing.

## The thing to build

A small converter pipeline plus a reconciliation flow. Not a megaplan-sized
codebase — closer to ~500 LOC of Python plus drivers and tests.

```
sources                                           
─ ready_templates/*/*.py (NODES tuple)            
─ ready_templates/*/*.py (API_WORKFLOW dict)      
─ workflow_corpus/official/*/*.json               
                                                  
   │                                              
   ▼                                              
                                                  
existing vibecomfy parsers                        
─ convert_to_vibe_format(api_dict, ...)           
─ convert_ui_to_api(ui_dict, ...) + normalize     
─ build_authored_ready_workflow(NODES, ...)       
                                                  
   │                                              
   ▼                                              
                                                  
VibeWorkflow IR  ◄── canonical shape, ALL inputs converge here
                                                  
   │                                              
   ▼                                              
                                                  
emitter (NEW: tools/format_as_python.py)          
─ walks VibeWorkflow, emits `wf.node(...)` calls  
─ preserves READY_METADATA / READY_REQUIREMENTS   
─ uses schema (node_index.json) to map widget_X→real_name where possible
                                                  
   │                                              
   ▼                                              
                                                  
real Python file (`ready_templates/image/foo.py`) 
```

The architectural commitment: **one emitter, not N converters.** Variation lives
in the input layer; vibecomfy's IR absorbs it; the emitter only ever sees
VibeWorkflow.

## Correctness contracts: split by template kind

Roundtrip-equality is only the right contract for some of the 50 templates.

### LEGACY (41 templates, API_WORKFLOW dict, no UUID subgraphs)

```python
old = old_module.build()                          # via build_api_ready_workflow
new = new_module.build()                          # via wf.node()
assert compile_equivalent(old.compile("api"), new.compile("api"))
```

`compile_equivalent` allows node-id renumbering and order changes, but every
class_type, every input/widget value, every edge must match. If this passes,
conversion is **faithful** (no semantic drift). If it fails, the structured
diff tells you exactly what diverged — actionable in one read.

For these 41, roundtrip-equality is the load-bearing assertion. Compile-equal
means runtime-equal.

### AUTHORED-with-subgraph (8 templates, NODES tuple + UUID class type)

Roundtrip-equality **does not apply** to these. The whole point of the
conversion is for the new shape to **diverge** from the old: old has 2 nodes
(SaveImage + UUID wrapper), new has 10 nodes (the inlined subgraph). They MUST
differ.

For these 8, the correctness contract is different:

```python
new = new_module.build()
assert new.validate().ok                          # schema-shape correct
assert new.compile("api") == reference_api_dict   # if we have a ground-truth API dict
result = run_embedded_sync(new, backend="graphbuilder")  # on a pod
assert result.outputs                             # actual end-to-end execution
```

Where does the reference API dict come from? Two sources:
1. **HiddenSwitch's `convert_ui_to_api` on the source JSON** — this is what
   the ComfyUI runtime would compile the source workflow to *with subgraphs
   inlined*. If we can run it locally, it's the ground-truth flat API dict.
2. **A pod-captured run of the source JSON** — provision a pod, send the
   source `workflow_corpus/.../foo.json` directly to ComfyUI, capture the
   final flat prompt dict. Slower but unambiguous.

In practice the dev loop is: hand-author one template (z_image, done), confirm
GPU run, then make the converter reproduce its API dict — at which point the
reference for the other 7 AUTHORED templates is the converter's own output
once the converter is stable on z_image.

### Known gotcha: existing snapshots are the BROKEN shape

`tests/snapshots/z_image.api.json` and the 8 sibling `*.api.json` files were
captured pre-refactor — they encode the JSON-shaped Python output we're moving
away from. `z_image.api.json` has 2 nodes (UUID wrapper + SaveImage); the new
real-Python z_image compiles to 10 named nodes. **The snapshots are not ground
truth for the AUTHORED-with-subgraph 8.** They're useful as "what the old form
looked like" for diagnostic diffs, not as a passing assertion.

Plan: re-capture snapshots after each template is converted, using the new
build(). Snapshots become "freeze the converted form" rather than "check
parity with the old form." For the 41 LEGACY ones, the existing snapshots
*are* still valid (no subgraphs, conversion is faithful by definition).

## Validation as a grid, not a verdict

| Layer | Cost | Coverage | What it tells you |
|---|---|---|---|
| Python imports | ms | All 50 | Emitter produced parseable code |
| `build()` runs | ms | All 50 | IR survived round-trip |
| `wf.validate().ok` | ms | All 50 | Schema-shape correct |
| **Roundtrip equal** | ms | All 50 | **No semantic drift** (load-bearing) |
| Snapshot diff (`tests/snapshots/`) | ms | 9 templates | Per-template parity for the test-plan ones |
| Real GPU run | ~$0.30 | 9 stock-node templates | End-to-end |
| GPU + custom packs | ~$0.50/each | 41 with deps | Custom-pack-runtime |

Each row is independent. A template passes layers 1–4 but fails snapshot diff:
that's a snapshot to update, not a converter bug. A template fails layer 4 but
passes 1–3: emitter or parser bug, fix once, regenerate everything. Each
template gets a row in a results grid.

## Reconciliation: how an agent handles weirdos

Three escape hatches, ordered by power:

### 1. Pattern-fix the converter (mass fix)

When the same diff appears across many files:

> "11 templates with `LoraLoaderModelOnly` all show `lora_name` missing"

That's a parser or emitter bug. Fix once → regenerate all 50 → re-run grid. The
fact that you can regenerate is the converter's superpower: hand-edits would
have to be re-applied; generated code can be reflowed.

### 2. Per-template override (`<name>.override.json`)

When 90% of a template auto-generates but 10% is gnarly:

```
ready_templates/image/foo.py
ready_templates/image/foo.override.json   ← edits applied after auto-emit
```

The override is a small JSON of node-keyed patches the converter applies post-emit.
Used for templates that need ~one weird input fixed up by hand.

### 3. Manual full takeover (`# vibecomfy: manual`)

For genuinely weird templates, a magic comment at the top of the file makes the
driver skip it. The file is hand-authored (like z_image is today). Converter
never overwrites; you own it.

## What this looks like from an agent's perspective

Running the driver:

```bash
$ python -m tools.convert_ready_templates --all
Converted 47/50 (compile + validate + roundtrip pass)
Failures (3):
  ready_templates/edit/qwen_image_edit.py: ROUNDTRIP_FAIL
    diff:
      node 47 (KSampler) input 'denoise': old=1.0 new=missing
      node 12 (LoraLoaderModelOnly) input 'strength_clip': old=0.8 new=1.0
    hint: emitter doesn't preserve denoise=1.0 default OR LoraLoaderModelOnly
          widget_2 → strength_clip mapping missing
    next: edit tools/format_as_python.py:emit_node, OR add
          ready_templates/edit/qwen_image_edit.override.json
  ready_templates/video/wanvideo_wrapper_22_s2v_context_window.py: PARSE_FAIL
    error: source JSON has node class 'WanVideoSampler' not in node_index.json
    hint: install custom node pack `wanvideowrapper`, regenerate node_index.json
  ready_templates/video/ltx2_3_runexx_lipsync_custom_audio.py: SNAPSHOT_DIFF
    diff: ...
```

For each failure, the agent decides: fix once (regenerate all) or fix one
(override or manual takeover). The output of each row is structured enough that
a subagent can act on it without re-reading 200 lines of source.

## Test fixtures we have on disk

Use these for the dev loop — no GPU needed for any of it:

| File | Shape | Use for |
|---|---|---|
| `workflow_corpus/official/image/z_image.json` | UI-format ComfyUI workflow JSON, 31 KB, has `definitions.subgraphs` | Test the parser path: UI JSON → vibecomfy IR (with subgraph inlining) |
| `tests/snapshots/z_image.api.json` | Compiled API dict, 2 nodes (UUID wrapper + SaveImage) | "Old/broken" reference; useful for the diff that motivates conversion |
| `tests/snapshots/z_image.class_types.json` + `.widget_values.json` | Pre-refactor class-type set + widget value set | Pre-conversion shape baseline |
| `ready_templates/image/z_image.py` (current state) | Real-Python hand-authored, runs on GPU | The reference output the emitter must learn to reproduce |
| `tests/snapshots/wan_t2v.api.json` (and 7 others) | Pre-refactor compiled API dicts for the AUTHORED templates | Same caveat as z_image — encodes the broken shape; diagnostic only |
| `ready_templates/video/wan_t2v.py` (NODES tuple form, current) | LEGACY-style template w/ named class types but `widget_X` indices | Simplest *non-z_image* converter target — no subgraph inlining required |

For a **second test fixture** in the API-JSON shape, pick any LEGACY template's
`API_WORKFLOW = {...}` dict — that's literally a flat ComfyUI API dict. e.g.
`ready_templates/video/wanvideo_wrapper_22_5b_i2v.py:API_WORKFLOW` is one
import + one `dict()` call away from being a standalone fixture.

## How to test it (the dev loop)

Three loops, in order of cost. **The first two run entirely on your local
machine — no pod, no GPU, no HuggingFace, no internet.** That's the bar:
"happy converter" should be provable on a Mac before any pod spend.

### Local fast loop — seconds per template, no GPU, no network

Setup (one-time):
```bash
cd ~/Documents/reigh-workspace/vibecomfy
.venv/bin/python -m pytest tests/test_ready_templates.py -x   # baseline: should pass before you start
```

Per-template:

1. **Build `tools/format_as_python.py`** (~300 LOC). Walk VibeWorkflow, emit
   `wf = VibeWorkflow(...)` + `var_n = wf.node("CLASS", real_name=value,
   in_=other.out(0))` lines, preserve READY_METADATA / READY_REQUIREMENTS, end
   with `wf.finalize_metadata()`.
2. **Test the parser end** on the two fixtures: feed
   `workflow_corpus/official/image/z_image.json` through the UI→IR path, feed
   `tests/snapshots/z_image.api.json` through the API→IR path. Both should
   yield a VibeWorkflow. Quick scratch-py:
   ```python
   from vibecomfy.ingest.normalize import convert_ui_to_api
   from vibecomfy.ingest.loader import load_template
   from vibecomfy.ingest.normalize import normalize_to_api
   ui = load_template("workflow_corpus/official/image/z_image.json")
   api = normalize_to_api(ui, schema_provider=None)
   print(api)   # flat dict; should have inlined subgraphs
   ```
3. **Test the emitter end** by feeding `ready_templates/image/z_image.py`'s
   `build()` output through `format_as_python(wf)` and checking the produced
   string parses + builds equivalent to the input.
4. **Run on z_image**: compare emitter output to the current hand-written
   `z_image.py`. Should be structurally identical (cosmetic differences OK).
5. **Run on a LEGACY template** (e.g. `wan_t2v` after running it through
   `convert_to_vibe_format(API_WORKFLOW, ...)` to get a VibeWorkflow). Confirm
   roundtrip-equal.
6. **Run the existing per-template pytest** against the converted file to
   make sure nothing regressed:
   ```bash
   .venv/bin/python -m pytest tests/test_ready_templates.py -k z_image -x
   ```
   `tests/test_ready_templates.py` already covers `validate().ok`, build()
   round-trip via `convert_to_vibe_format`, and the `external_python_marker`
   parity for LTX templates. **This is your local end-to-end "without GPU"
   pass mark.** It runs in <1s per template.
7. Iterate the emitter until z_image and one LEGACY both pass on (4)+(5)+(6).

### Batch local loop — minutes total, no GPU, no network

8. Run the converter on all 8 AUTHORED templates. For each, capture diff vs
   current source (expected: large, that's the conversion). `validate().ok`
   must pass, `build()` must succeed.
9. Run on all 41 LEGACY templates. Roundtrip-equality must pass on every one,
   or the file goes into the "weirdo" bucket.
10. **Run the full local pytest suite**:
    ```bash
    .venv/bin/python -m pytest tests -x --ignore=tests/smoke
    ```
    `--ignore=tests/smoke` skips the runpod-only tests. Everything else runs
    on a Mac in seconds: ready_templates, blocks, patches, finalize_metadata,
    router, ops, plugin discovery, cli_loader, etc. **All green = the
    converter is locally trustworthy, no pod needed yet.**
11. Triage weirdos using the reconciliation flow (mass-fix vs override vs
    manual takeover).

### What the local loop does NOT catch

The Mac loop catches: parse errors, emitter bugs, validate.ok failures,
roundtrip drift, schema mismatches, snapshot drift. ~95% of issues.

The Mac loop does NOT catch: HiddenSwitch ComfyUI's strict prompt validation
quirks (saw `prompt_node.AdditionalProperties` rejection in our session),
custom-node missing-class errors at runtime, model download failures,
GPU-only KSampler convergence behavior at low step counts. These need the
pod loop.

If you want a slightly stronger local check before pod spend: install a
**CPU-only ComfyUI** (`pip install comfyui` on the Mac without CUDA),
`vibecomfy runtime smoke --mode managed` to confirm it imports, then run a
single trivial workflow through `run_embedded_sync(wf, backend="graphbuilder")`.
Slow (~minutes for even a simple t2i because no GPU), but it catches the
HiddenSwitch validation issues without any pod cost. **Optional, only if pod
runs are surfacing surprises the local pytest didn't.**

### Pod loop — minutes per pod, ~$0.30 each

12. Single z_image pod re-run (already proved): confirm conversion didn't
    regress.
13. Run `tests/smoke/test_layer2_runpod_ops.py` — exercises 6 verb-native
    routes covering 5 of the 8 AUTHORED templates. Green = test plan unblocked.
14. Run `tests/smoke/test_layer2_runpod_dropped.py` — exercises 3 dropped
    templates (the other 3 of the 8 AUTHORED). Green = scope-reduction
    conservatism check holds.
15. Run `tests/smoke/test_layer2_runpod_matrix.py` (with `--runpod-full`) —
    production-resolution matrix, ~$5-10. Run before tagging a release.

The 41 LEGACY templates are intentionally NOT in the pod loop yet — they
require their custom-node packs installed first (separate concern).

### Cost discipline

Numerical bar for "is the local loop enough yet?": **all of (10) green +
the converter passes (4)+(5)+(6) on z_image AND on at least one LEGACY +
weirdos triaged or marked manual. Only then push to a pod.** Resist the urge
to "test on a pod to see what breaks" — every iteration there is real money,
and the local loop is fast enough to surface 95% of issues if you're
disciplined about running it first.

## Agent ergonomics: one-at-a-time, with reflection

The right development model is **iterate the converter on one template at a
time, with a reflection step after each**. Not "build the whole converter,
batch on all 50, debug." Reasoning: the converter learns about the long tail
from each template. If you batch, the ninth weirdo's diff lands in a stack of
output where it can't be acted on cleanly.

### Per-template loop the agent runs

```
for template in [z_image, wan_t2v, ltx2_3_t2v, ..., (49 more)]:
    1. converter.convert(template)
    2. validate.local(template)      # imports, build, validate.ok, roundtrip
    3. report:
         if PASS:
            print(f"{template}: OK")
         else:
            print(f"{template}: {fail_layer}")
            print(f"  diff: {structured_diff}")
            print(f"  hint: {pattern_match_against_known_fixes}")
    4. reflect (if PASS):
         "anything notable about this template's shape?"
         "did the emitter produce something a human would write?"
         "any new pattern observed?"
       reflect (if FAIL):
         "is this a pattern? (similar to N prior fails?)"
         "fix the emitter, OR add an override, OR mark manual?"
    5. apply learning to the converter
    6. re-run on the prior N templates (regression check, free)
    7. move on
```

### What "really nice from an agent perspective" means here

- **Each template is a self-contained task.** No shared mutable state across
  templates beyond the converter source. An agent can pick up at template 17
  without re-loading templates 1–16 into context.
- **Failures are structured, not "the script crashed."** Every failure has a
  layer (parse / emit / validate / roundtrip), a diff (specific keys/values),
  and a hint (matches prior pattern? is it a known custom-node category?).
- **Two recovery paths, clearly distinguished.** Mass-fix the converter
  (regenerates everything; helps the next 33 templates) vs per-template
  override (helps only this one; uses the override JSON or `# vibecomfy:
  manual` magic comment).
- **The "what could have been better" prompt is built in.** After each
  successful conversion, the loop asks the agent to reflect: was the variable
  naming readable? Was a comment missing? Did the emitter produce anything
  awkward? Lessons go into the converter, not into a notes file.
- **Re-running is cheap.** Conversion is deterministic; running the converter
  on prior templates after improving it is a free regression test. If
  template 17's fix breaks template 4, you find out before moving on.
- **Pod runs are gated.** The local loop catches 95% of issues in seconds.
  Pod runs are reserved for the final test plan smoke — never for individual
  per-template debugging unless something genuinely runtime-specific goes
  wrong.

### One-by-one ordering

Start simple, end weird:

1. **z_image** — already done by hand; verify the converter reproduces it.
2. **A LEGACY template with stock nodes only** (e.g. `wan_t2v`) — easiest
   parse, no UUID inlining; tests the emitter on the simplest possible input.
3. **The other 7 AUTHORED templates** in dependency order
   (flux2_klein_4b_t2i → flux2_klein_9b_gguf_t2i → qwen_image_edit → ...).
   Tests the UUID-subgraph inlining path.
4. **The remaining 40 LEGACY templates** in any order. Mostly mechanical;
   weirdos surface in custom-node template families
   (`wanvideo_wrapper_*`, `runexx_*`, `iamccs_*`, `lightricks_*`).
5. **Triage and reconcile weirdos** at the end — by this point the converter
   is mature and the failures concentrate in genuinely-weird inputs.

After each major batch (AUTHORED done, LEGACY done), the runpod tests
(test_p1, test_layer2_runpod_ops, _dropped, _matrix) get re-run and the
results inform the next iteration.

## Schema source: where `widget_X → real_name` resolution comes from

The emitter wants to translate `widget_0 → unet_name` for readability. Three
sources to try in order, falling back to `widget_X` if all miss:

1. **`node_index.json` at repo root** — vibecomfy's pre-built schema cache, one
   entry per known node class with `INPUT_TYPES`. Cheap, on-disk, no runtime.
   Build it once via `python -m vibecomfy.cli sources sync` (or its inferior
   `python -m vibecomfy.cli nodes spec` — verify which is canonical). For stock
   ComfyUI nodes this covers everything we need.
2. **`vendor/ComfyUI/` git submodule** — the HiddenSwitch fork is checked out
   alongside the repo (per `.gitmodules`). Each node's `INPUT_TYPES` classmethod
   is parseable directly from `vendor/ComfyUI/comfy_extras/nodes/` and
   `vendor/ComfyUI/nodes.py`. Use AST parsing rather than importing — keeps the
   emitter free of GPU/CUDA imports.
3. **Hardcoded mapping for the ~25 most common nodes** — `UNETLoader`,
   `CLIPLoader`, `VAELoader`, `CLIPTextEncode`, `EmptySD3LatentImage`,
   `EmptyHunyuanLatentVideo`, `ModelSamplingAuraFlow`, `ModelSamplingSD3`,
   `KSampler`, `VAEDecode`, `SaveImage`, `SaveVideo`, `CreateVideo`,
   `LoraLoaderModelOnly`, etc. Lives in `tools/_widget_schema.py` as a
   `dict[class_type, list[input_name]]`. Always available, never wrong for
   stock nodes, easy to extend.

Recommended: start with (3) hardcoded for the stock 25; that's enough for the
9 test-plan templates. Add (1) for the LEGACY 41 sweep, (2) only if a custom
node pack proves stubborn.

For unknown class types: keep `widget_X` in the emitted output. Ugly but
faithful. The override JSON can remap if needed.

## Override JSON format

When the converter produces something *almost* right but a small edit is
needed (a misnamed widget, a missing connection, an extra metadata field),
drop a sidecar:

```json
{
  "patches": [
    {
      "match": {"class_type": "WanVideoSampler", "node_index": 0},
      "rename_inputs": {"widget_2": "noise_aug_strength"},
      "set_inputs": {"steps": 30}
    },
    {
      "match": {"node_id": "47"},
      "remove_inputs": ["unused_widget_5"]
    }
  ],
  "metadata_overrides": {
    "runtime_note": "Requires WanVideoWrapper >= 1.4.0"
  }
}
```

`match` selects nodes by class_type+index or by emitted node_id (post-renumber).
`rename_inputs` translates kwargs at emit time. `set_inputs` overrides values.
`remove_inputs` deletes them. `metadata_overrides` updates `READY_METADATA`.

Saved as `<template_path>.override.json`. The driver applies overrides in
the emit step, after schema-based widget resolution, before the file is
written.

Use sparingly — every override is a place the converter is hand-aware of one
template's quirks. If three templates need the same override, that's a hint to
fix the converter or extend the schema map instead.

## Failure modes you'll likely hit

These are the patterns to expect when running the converter across all 50
templates. Use this as a triage cheat-sheet when a template fails the grid:

| Pattern | Likely cause | Fix |
|---|---|---|
| `widget_X` survives in emitted output | Class type missing from schema map | Add to `tools/_widget_schema.py` |
| `Reroute` / `Note` / `MarkdownNote` nodes in IR | UI-only nodes leaking through `convert_ui_to_api` | Filter at parse time (already done for MarkdownNote in some paths; verify) |
| `PrimitiveNode`, `GetNode`, `SetNode`, `Bypasser` | More UI-only constructs | Same — strip pre-IR |
| Edge to a node that doesn't exist post-conversion | Renumber bug in the emitter | Fix the emitter's id-table; add to regression tests |
| `validate.ok = False` with "missing required input" | Source workflow had implicit defaults the emitter didn't preserve | Hardcode the default in the schema map, or add an override |
| Roundtrip diff shows reordered list values | Order-sensitive widget (e.g. KSampler `seed` vs `steps`) | Verify the schema map's input order matches `INPUT_TYPES` declaration order |
| `class_type: "WanVideoSampler"` / `"KJWidgetTools"` / etc. | Custom node pack widget convention not in schema | Add a mini-schema for the pack OR accept widget_X for that pack OR `# vibecomfy: manual` |
| Conversion succeeds but pod-run errors with `missing_node_type` | Custom pack isn't installed on the pod | Out of scope (separate `vibecomfy nodes ensure` work) |
| Conversion succeeds but pod-run errors with input-shape mismatch | Schema map says wrong arg order | Real bug; fix and regenerate |
| Two `CLIPTextEncode` nodes both bound to `text` variable | Naming heuristic collided | Improve emitter naming (positive/negative/etc.) — see below |

## Variable naming heuristic

When two nodes share a class type, the emitter needs distinct names. Suggested
priority:

1. **Role from connections** — a `CLIPTextEncode` connected to `KSampler.positive`
   becomes `positive`; connected to `KSampler.negative` becomes `negative`.
   Cheap structural inference.
2. **Role from text content** — if widget_0 is empty string, it's almost
   certainly the negative prompt; name it `negative`.
3. **Numbered fallback** — `cliptextencode_1`, `cliptextencode_2`. Always works,
   never wrong, sometimes ugly.
4. **Hint from metadata** — if `READY_METADATA["registered_inputs"]` says
   `prompt: ('76', 'widget_0')`, the node carrying the prompt becomes
   `prompt_node` or just `prompt`.

Keep this as a small heuristic table the agent can read and extend. Don't
over-engineer.

## Reflection prompt (run after each successful template)

After the converter passes the local-fast-loop on a template, the agent runs
this prompt against the produced output:

> 1. **Variable names**: are they semantically meaningful (`unet`, `pos`,
>    `decoded`) or class-bound (`unetloader_1`, `cliptextencode_2`)? If only
>    class-bound, would a small heuristic improve them?
> 2. **Surprising shape**: was anything in the source unexpected — a subgraph
>    in an unusual place, a custom node, a circular reference? If yes, note
>    it in the failure-modes table.
> 3. **Diff legibility**: if the roundtrip diff fired, was the structured
>    output enough to act on, or did you have to open the source files? If
>    the latter, what's missing from the diff?
> 4. **Readability test**: imagine handing this template to someone who's
>    never seen ComfyUI. Could they tell what it does? If not, what's the
>    minimum cosmetic change to fix it?
> 5. **Override or fix?**: if you reached for an override, would a converter
>    improvement have helped 3+ other templates? If yes, do that instead.
> 6. **Was this a "weirdo"?**: should it have been flagged for manual
>    takeover from the start? If yes, what's the signal in the source we
>    could detect?

The output of this prompt feeds back into either the converter source or the
schema map. Lessons that don't fit there go into a `tools/conversion_notes.md`
running log.

## If you're picking this up cold

Before writing any code, do this in order:

1. Read `ready_templates/image/z_image.py` (current real-Python form).
2. Read `tests/snapshots/z_image.api.json` (broken pre-refactor shape, for
   contrast).
3. Read `vibecomfy/workflow.py` lines 95–185 (`finalize_metadata`,
   `register_input`, `add_node`, `node()`) — that's the emitter target API.
4. Read `vibecomfy/ingest/` `convert_to_vibe_format` and `convert_ui_to_api`
   signatures — that's the parser side.
5. Read `vibecomfy/registry/ready_template.py:build_authored_ready_workflow`
   (lines 1–60). The new emitter is essentially the inverse of this.
6. Run the existing test suite locally:
   `cd vibecomfy && .venv/bin/python -m pytest tests/test_ready_templates.py -x`.
   Should pass before and after each conversion.

Then start with z_image as the reference round-trip target and only widen
scope once it's reproducible from end to end.

## Risks and unknowns

- **`convert_ui_to_api` may not inline subgraphs.** If the parser leaves UUID
  class types in the IR, the emitter has nothing to emit. Verify on z_image
  early; if true, add an inlining preprocess that walks `definitions.subgraphs`.
- **`node_index.json` may be stale or partial.** It only covers what the last
  `sources sync` saw — custom node packs not installed at index time will be
  missing. Fall back to schema map (3) for these.
- **Some LEGACY templates may not actually be runnable.** They were
  materialized from upstream JSONs that may have shifted; if a template was
  never runtime-validated, conversion preserves whatever was wrong. The 41
  LEGACY templates are not snapshot-tested; we trust them only as far as
  upstream did.
- **Custom-pack templates need the packs installed to runtime-validate.** The
  pod loop only covers the 9 stock-node templates by default. For the 41 with
  custom-pack deps, validation stops at the local-batch loop; runtime
  verification is a separate task.
- **HiddenSwitch's compile path differs from upstream ComfyUI.** Anything
  validated against HiddenSwitch may not transfer to other Comfy distributions
  without re-checking (object_info shape, subgraph handling). Out of scope
  here, but worth flagging.

## Acceptance (consolidated)

- `tools/format_as_python.py` exists, ~300 LOC, callable as
  `python -m tools.format_as_python <template_path>`.
- `tools/convert_ready_templates.py` driver enumerates all 50 templates,
  produces a structured grid output (one row per template, columns for each
  validation layer).
- All 41 LEGACY templates roundtrip-equal-pass against their current
  `build()` output.
- All 8 AUTHORED-with-subgraph templates compile + validate.ok + run on a pod
  (verified via the layer-2 runpod test grid).
- Weirdos are documented either via override JSON sidecars or
  `# vibecomfy: manual` magic comment, with a one-line note explaining why.
- `tests/smoke/test_layer2_runpod_ops.py` and
  `tests/smoke/test_layer2_runpod_dropped.py` pass on `--runpod`.
- `tests/smoke/test_layer2_runpod_matrix.py` passes on `--runpod-full`
  (release-gate).
- The post-conversion snapshots in `tests/snapshots/` are re-captured to
  reflect the new shape (a separate small task; can be one regenerate-all
  command).

## Out of scope for this doc

- Migrating to `comfy-script` typed authoring (separate megaplan; researched, ruled
  out as a *replacement* for now — vibecomfy's `wf.node()` IS upstream GraphBuilder
  semantics).
- `vibecomfy nodes ensure --workflow X` auto-installing custom packs at install time
  (separate; needed before runtime-checking the 41 templates with custom-pack deps).
- Renaming `ready_templates/` to `templates/` (bikeshed; loader/router/dispatch all
  reference the path; not worth touching now).
- Fixing templates that were already broken before conversion (the converter is
  faithful, not corrective).

## Existing assets we're standing on

- VibeWorkflow IR + parsers (`vibecomfy/workflow.py`, `vibecomfy/ingest/`)
- z_image.py: working reference output the emitter must reproduce
- `tests/snapshots/` (9 pre-refactor API snapshots) for parity diffing
- `tests/smoke/test_p1_runpod.py`, `test_layer2_runpod_ops.py`,
  `test_layer2_runpod_dropped.py`, `test_layer2_runpod_matrix.py` — the
  full runpod test grid, already wired to the conftest `--runpod` /
  `--runpod-full` flags
- `tests/smoke/_runpod_helpers.py` — pod-cost guardrails, install path
  (clone + pip install -e), shared across all runpod tests
- comfy-script + HiddenSwitch ComfyUI install line in `_runpod_helpers.py` —
  proven to bring up the runtime on a fresh RunPod pod
