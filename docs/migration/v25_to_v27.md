# Migration guide: v2.5 → v2.7

This guide covers breaking and behavioral changes when upgrading VibeComfy
from v2.5-era code to v2.7. Each section is a self-contained migration
concern with before/after snippets and the commands that validate the change.

---

## 1. ContextVar template authoring (workflow binding)

Templates in v2.7 use a context-manager pattern. Passing `wf` explicitly to
every `node()` call is still supported but no longer required.

### Before (v2.5)

```python
def build():
    wf = workflow_from_ready("image/my_template")
    loader = node(wf, "CheckpointLoaderSimple", ckpt_name="...")
    latent = node(wf, "EmptyLatentImage", width=1024, height=1024)
    sampler = node(wf, "KSampler", model=loader.out(0), ...)
    return wf
```

### After (v2.7)

```python
from vibecomfy.templates import new_workflow, node

READY_METADATA = {"ready_template": "image/my_template", "task": "t2i"}

with new_workflow(READY_METADATA, source_path=__file__) as wf:
    loader = node("CheckpointLoaderSimple", ckpt_name="...")
    latent = node("EmptyLatentImage", width=1024, height=1024)
    sampler = node("KSampler", model=loader.out(0), ...)

wf.finalize_metadata()
```

### Migration commands

```bash
# Verify a template loads correctly with the new pattern
python -m vibecomfy.cli validate ready_templates/image/my_template.py

# Check for ContextVar binding errors
python -m vibecomfy.cli doctor ready_templates/image/my_template.py
```

---

## 2. Multi-output node return patterns

Nodes with multiple outputs now use tuple-unpacked returns instead of
chained `.out()` calls on a sentinel object.

### Before (v2.5)

```python
result = node(wf, "WanVideoWrapper", ...)
latent = result.out(0)
mask = result.out(1)
```

### After (v2.7)

```python
latent, mask = node("WanVideoWrapper", ...)
```

When a node has exactly one output, the return is a single `Handle`.
Hand-authored templates can override auto-detected output names:

```python
latent, mask = node("WanVideoWrapper", ..., _outputs=("latent", "mask"))
```

### Migration commands

```bash
# Check port report for missing multi-output annotations
python -m vibecomfy.cli port check <wf> --json

# Validate node call schema
python -m vibecomfy.cli port validate-call WanVideoWrapper \
  --kwargs '{"model": "...", "clip": "...", "vae": "..."}' --json
```

---

## 3. Materialized subgraphs

Subgraph nodes are now emitted as inline Python functions instead of inline
JSON blocks. This improves readability and allows subgraph reuse.

### Before (v2.5)

Subgraphs appeared as inline `raw_call()` blocks with UUID identifiers
and no explicit function boundary:

```python
sub_upscale = raw_call("<uuid>", "UpscaleModelLoader", model_name="...")
# ... internal nodes scattered inline ...
```

### After (v2.7)

```python
def _subgraph_upscale(**kwargs):
    upscale = raw_call("<uuid>", "UpscaleModelLoader", model_name=kwargs["model_name"])
    # ... internal nodes and edges ...
    return upscale

result = _subgraph_upscale(model_name="4x-UltraSharp")
```

### Migration commands

```bash
# Check subgraph freshness (compares source_hash against current emitter output)
python -m vibecomfy.cli port check <wf> --json

# Regenerate to materialize subgraphs into functions
python -m vibecomfy.cli port convert <wf> --ready-id image/my_template \
  --out ready_templates/image/my_template.py --json
```

---

## 4. Emission style changes (blank lines, label-preferred names)

v2.6.4 Fix 8 changes formatting of generated templates: multi-line node
calls are surrounded by blank lines, and emitter prefers label-derived
variable names.

### Before (v2.5)

```python
loader = node(wf, "CheckpointLoaderSimple", ckpt_name=InputSpec("ckpt_name", default="..."))
sampler = node(wf, "KSampler",
    model=loader.out(0),
    seed=InputSpec("seed", default=42),
    steps=InputSpec("steps", default=20),
    cfg=InputSpec("cfg", default=7.0),
    sampler_name=InputSpec("sampler_name", default="euler"),
    scheduler=InputSpec("scheduler", default="normal"),
    denoise=InputSpec("denoise", default=1.0),
)
vae_decode = node(wf, "VAEDecode", samples=sampler.out(0), vae=loader.out(2))
```

### After (v2.7)

```python
loader = node("CheckpointLoaderSimple", ckpt_name=InputSpec("ckpt_name", default="..."))

sampler = node("KSampler",
    model=loader.out(0),
    seed=InputSpec("seed", default=42),
    steps=InputSpec("steps", default=20),
    cfg=InputSpec("cfg", default=7.0),
    sampler_name=InputSpec("sampler_name", default="euler"),
    scheduler=InputSpec("scheduler", default="normal"),
    denoise=InputSpec("denoise", default=1.0),
)

vae_decode = node("VAEDecode", samples=sampler.out(0), vae=loader.out(2))
```

### Migration commands

```bash
# Check code style conventions
python -m vibecomfy.cli port lint <wf>

# Preview variable naming
python -m vibecomfy.cli analyze names <wf>
```

---

## 5. widget_N key resolution

Positional `widget_N` keys in JSON workflows are now resolved to their
named fields during conversion.

### Before (v2.5)

```python
# Emitted from JSON with unresolved widget keys:
sampler = node(wf, "KSampler",
    widget_0=42,     # seed
    widget_1=20,     # steps
    widget_2=7.0,    # cfg
    ...
)
```

### After (v2.7)

```python
sampler = node("KSampler",
    seed=42,
    steps=20,
    cfg=7.0,
    ...
)
```

### Migration commands

```bash
# Check for unresolved widget_N keys
python -m vibecomfy.cli port check <wf> --strict-ready-template --json

# Inventory remaining widget_N across all templates
python -m vibecomfy.cli port inventory --ready --json

# Resolve widget aliases for a specific class
python -m vibecomfy.cli port widgets KSampler --json
```

---

## 6. New CLI commands

Several new commands replace or augment v2.5 workflows.

### `port export`

Export a workflow as API JSON without queuing.

```bash
# v2.7
python -m vibecomfy.cli port export <wf> --to json

# This replaces manual wf.compile("api") calls for inspection
```

### `port validate-call`

Validate a single node call against the authoring schema.

```bash
# v2.7
python -m vibecomfy.cli port validate-call KSampler \
  --kwargs '{"seed": 42, "steps": 20, "cfg": 7.0}' --json

# This replaces ad-hoc node spec lookups followed by manual validation
```

### `port doctor-all`

Run port check + install-plan + validate + doctor + runtime doctor in one command.

```bash
# v2.7
python -m vibecomfy.cli port doctor-all <wf> --json

# This replaces running port check, validate, doctor, and runtime doctor separately
```

### `nodes compatible-with`

Check socket type compatibility between two node classes.

```bash
# v2.7 — find outputs compatible with VAE Decode's samples input
python -m vibecomfy.cli nodes compatible-with KSampler VAEDecode samples --as output --json

# This replaces manual object_info inspection
```

### `runtime eval-node`

Compile and queue a minimal subgraph to preview a single node.

```bash
# v2.7
python -m vibecomfy.cli runtime eval-node <wf> --node <node_id> --runtime embedded
```

---

## 7. wf.lookup_id() and wf.export_to_json()

New `VibeWorkflow` methods provide structured access to node information
and API JSON export.

### Before (v2.5)

```python
# Manual node lookup
node = wf.nodes["42"]
class_type = node.class_type
# No structured reverse lookup
# Manual compile for JSON export
api_dict = wf.compile("api")
```

### After (v2.7)

```python
# Structured reverse lookup
info = wf.lookup_id("42")
# {"node_id": "42", "class_type": "KSampler", "variable_name": "ks_advanced", ...}

# Explicit JSON export
api_dict = wf.export_to_json(format="api")
```

---

## 8. wf.strict_types

Enable socket type compatibility warnings on edge creation.

### Before (v2.5)

```python
wf = load_workflow_any("image/z_image")
wf.connect(loader.out(0), sampler, "model")  # No type checking
```

### After (v2.7)

```python
wf = load_workflow_any("image/z_image", strict_types=True)
wf.connect(loader.out(0), sampler, "model")  # Warns if LATENT → IMAGE mismatch
```

---

## 9. Structured errors with next_action

v2.7 introduces a structured exception hierarchy with built-in remediation
suggestions.

### Before (v2.5)

```python
try:
    wf.compile("api")
except ValueError as e:
    print(f"Validation failed: {e}")
```

### After (v2.7)

```python
from vibecomfy.errors import SchemaValidationError

try:
    wf.compile("api")
except SchemaValidationError as e:
    print(f"Validation failed: {e}")
    if e.next_action:
        print(f"Next action: {e.next_action}")
        # e.g., "vibecomfy doctor"
```

All VibeComfyError subclasses (`ModelAssetError`, `QueueError`,
`ContextVarBindingError`, `ConversionParityError`, `SubgraphFreshnessError`,
`RuntimeNodeError`, `DriftError`) support `next_action`.

---

## 10. attempt.json and drift detection

Every queue boundary now writes `attempt.json` with full pre-queue state.

### Before (v2.5)

```python
# Only metadata.json was written after queue
result = run_embedded_sync(wf)
# out/runs/<id>/metadata.json
```

### After (v2.7)

```python
# attempt.json written before queue, metadata.json after
result = run_embedded_sync(wf)
# out/runs/<id>/attempt.json  — pre-queue snapshot
# out/runs/<id>/metadata.json — post-queue result
```

The `attempt.json` contains:
- `compiled_prompt` — full API dict
- `id_map` — variable-name → node-id
- `node_lookups` — rich info per node via `wf.lookup_id()`
- `model_manifest` — expected/actual SHA-256 per asset
- `lockfile_snapshot` — `custom_nodes.lock` at queue time
- `drift` — pinned-vs-actual comparison

### Migration commands

```bash
# Check drift before queuing
python -m vibecomfy.cli runtime doctor

# Inspect attempt.json after a run
cat out/runs/<latest>/attempt.json | python -m json.tool | head -40
```

---

## 11. Bidirectional roundtrip limitations

JSON → Python → JSON roundtripping is not perfectly lossless.

| What | Behavior |
|------|----------|
| Helper/UI nodes (`Note`, `MarkdownNote`, `SetNode`, `GetNode`, `Reroute`) | Stripped during conversion |
| Unresolved `widget_N` on community nodes without `object_info` | May not roundtrip exactly |
| Subgraph UUIDs | Replaced by Python function names |
| Broadcast edge ordering | May differ from source JSON |
| Comment nodes and UI metadata | Intentionally omitted |

**Workaround**: If exact JSON reproduction is required, keep the original
JSON source and use `wf.export_to_json()` for the API-compatible dict
rather than expecting lossless roundtrip.

---

## Full migration checklist

Run these commands sequentially to validate a v2.5 workflow in v2.7:

```bash
# 1. Port check
python -m vibecomfy.cli port check <wf> --json

# 2. Convert with widget resolution (scratchpad first)
python -m vibecomfy.cli port convert <wf> \
  --out out/scratchpads/<name>.py --json

# 3. Validate the converted scratchpad
python -m vibecomfy.cli validate out/scratchpads/<name>.py

# 4. Full doctor run
python -m vibecomfy.cli port doctor-all out/scratchpads/<name>.py --json

# 5. Promote to ready template (if converting to checked-in template)
python -m vibecomfy.cli port convert <wf> \
  --ready-id <kind>/<name> \
  --out ready_templates/<kind>/<name>.py --json

# 6. Strict ready-template check
python -m vibecomfy.cli port check ready_templates/<kind>/<name>.py \
  --strict-ready-template --json

# 7. Check socket compatibility for critical connections
python -m vibecomfy.cli nodes compatible-with <FromClass> <ToClass> <ToInput> --json

# 8. Export final API JSON for diff comparison
python -m vibecomfy.cli port export ready_templates/<kind>/<name>.py --to json
```
