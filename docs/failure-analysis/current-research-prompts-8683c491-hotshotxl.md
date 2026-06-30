# Current Research Prompt Surfaces: HotShotXL Failure

Session: `8683c49126544e469a2eb15d89cfa711`
Turn: `0001`
Task: `Switch this to instead generate 8 frames of video using HotShotXL`

Raw artifacts:

- `out/editor_sessions/8683c49126544e469a2eb15d89cfa711/turns/0001/request.json`
- `out/editor_sessions/8683c49126544e469a2eb15d89cfa711/turns/0001/model_request.json`
- `out/editor_sessions/8683c49126544e469a2eb15d89cfa711/turns/0001/messages.jsonl`

## Important Clarification

There is not currently a separate LLM "research agent prompt" for the executor prefetch step.

The research phase is driven by:

1. The classifier prompt, which emits `research_goal`, `search_directions`, `source_preferences`, and `avoid`.
2. Deterministic retrieval in `vibecomfy/executor/core.py` and `vibecomfy/executor/research.py`.
3. The edit-agent prompt, which receives the resulting research packet and can call `research(...)` / `search(...)` during implementation.

So the "research agent received" two different kinds of guidance:

- deterministic research received the classifier fields as a scoped query;
- the edit model received the retrieved workflow evidence plus prompt guidance about how to use research.

## Current Classifier Research Prompt

Source: `vibecomfy/executor/prompts.py`

```text
"research_goal": string (optional) — for route="research" or route="adapt", state what the next agent should investigate; do not include conclusions.
"search_directions": array of strings (optional) — 2-5 concrete search directions or query concepts the research agent should try.
"source_preferences": array of strings (optional) — preferred evidence tiers such as "workflows", "registry", "messages", or "web".
"avoid": array of strings (optional) — only include clear retrieval or reasoning errors the research agent should avoid; omit it if unsure.
"known_graph_context": string (optional) — compact graph facts relevant to the research direction; leave blank if unknown.
```

```text
For route="research" and route="adapt", provide directional research metadata when useful: research_goal, search_directions, source_preferences, avoid, known_graph_context. These fields are instructions for what to investigate, not the answer. Research metadata must not pre-answer the research question. Use it to preserve constraints and identify what evidence to seek, not to declare which implementation families are allowed or forbidden. Do not claim that a source, node, model, or setting is correct until the research agent has actually searched.

Source preferences should match the job: use "messages" for community knowledge, usage tips, and failure-mode questions; use "workflows" for change-by-precedent or wiring-pattern requests; use "registry" for node pack/schema availability; use "web" only as fallback or when the user explicitly asks for online sources.

Search directions should be specific concepts, named technologies, model families, node packs, workflow patterns, or graph constraints. Never put the raw user sentence or generic filler words into search_directions.

When a graph edit will need research, make at least one search direction ask for concrete node combinations or workflow wiring evidence, not just high-level technique names.
```

This is the currently brittle part:

```text
When route="adapt" is chosen because the current graph already contains custom/branded nodes, search directions must name the exact visible class type(s) and fields/sockets from the graph reference map first. Do not start with broad ecosystem terms such as a model family, nodepack, or tutorial topic when an exact current class type is visible.

CRITICAL: NEVER name a technology ecosystem (AnimateDiff, LTX, VHS, WanVideo) that does NOT appear in the current graph's node types. Naming a different ecosystem will send research toward irrelevant workflow slices that cannot be lowered and will hard-fail implementation.

BAD: for a Wan2.2 I2V graph, search_directions mention "AnimateDiff/VideoHelperSuite LoRA noise variance" when AnimateDiff is not in the graph. GOOD: "UnetLoaderGGUF noise schedule", "LoraLoaderModelOnly strength_model", "KSamplerAdvanced steps".

For route="adapt", search_directions must include at least 2-3 EXACT class type strings visible in the graph reference map.

Avoid is optional. Use it only to block generic searches such as stopword-only fragments, unsupported guessed class names, or treating weak Discord/forum snippets as authoritative without workflow/registry evidence. Do not use avoid to rule out plausible implementation families or workflow ecosystems before research has checked them.
```

Why this is a problem for this class of request:

- It is reasonable when preserving a current custom stack.
- It is wrong for "switch this to X" requests, because the target workflow may need a new ecosystem that is not visible in the current graph.
- It biases research toward current local graph classes rather than target workflow precedents.

## Actual Classifier/Research Fields In This Turn

From `request.json`:

```json
{
  "research_goal": "Find the standard workflow structure and node requirements for HotShotXL video generation in ComfyUI, including model loading, text encoding, sampling parameters, and VAE decoding for video output.",
  "workflow_precedent_status": "compatible_workflow_found"
}
```

The final scoped research packet had this discardability preface:

```text
This research context is provided as evidence only. It is NOT authoritative guidance or a required implementation. Discard any packet that is empty, irrelevant, or contradicts the user's explicit request.
```

That wording is another source of confusion: it explicitly downranks the workflow packet even when `workflow_precedent_status` says a compatible workflow was found.

## Research Result The Edit Model Received

From `request.json` / `execution_protocol_notes`:

```text
Found 54 research result(s): video/ltx2_3_lightricks_two_stage, video/ltx2_3_t2v, video/ltx2_3_i2v, and 51 more. Relevant workflow/template paths: Wan2.1 Text-to-Video with WEBP and WEBM Output (...), AnimateDiff Video Generation with ControlNet and IP-Adapter (https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json), Flux Kontext Image Stitching Workflow (...).
```

Top compatible workflow source:

```json
{
  "class_type": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
  "source": "hivemind_workflow",
  "url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
  "pack": "workflow",
  "promotion_gates": {
    "has_compiled_api": true,
    "has_python_source": true,
    "has_workflow_json": true,
    "parseable_workflow": true
  },
  "reasons": [
    "hivemind:workflow resource",
    "hivemind:parseable workflow",
    "hivemind:compiled api available",
    "hivemind:filename matched 'HotShotXL'"
  ]
}
```

Critical semantic details present in the packet:

```json
{
  "model_families": ["hotshot", "animatediff", "sdxl", "controlnet"],
  "models": [
    "model.15.safetensors",
    "model.safetensors",
    "sd_xl_base_1.0_0.9vae.safetensors",
    "sdxl_vae.safetensors",
    "hotshotxl_mm_v1.pth",
    "thibaud_xl_openpose.safetensors",
    "ip-adapter-plus-face_sdxl_vit-h.bin",
    "ip-adapter_sdxl.bin"
  ],
  "searchable_aliases": [
    "hotshot",
    "hotshotxl",
    "hotshot xl",
    "animatediff",
    "animate diff",
    "sdxl",
    "sd_xl",
    "sd xl",
    "controlnet",
    "control net",
    "multi",
    "ip-adapter",
    "video-generation",
    "depth-map",
    "canny-edge",
    "openpose",
    "image-to-video"
  ]
}
```

Workflow-derived schemas present in the packet included:

```json
{
  "ADE_AnimateDiffLoaderWithContext": {
    "input": {
      "optional": {
        "motion_lora": {"type": "MOTION_LORA"}
      },
      "required": {
        "context_options": {"type": "CONTEXT_OPTIONS"},
        "model": {"type": "MODEL"}
      }
    },
    "outputs": [{"name": "MODEL", "type": "MODEL"}]
  },
  "ADE_AnimateDiffUniformContextOptions": {
    "input": {"optional": {}, "required": {}},
    "outputs": [{"name": "CONTEXT_OPTIONS", "type": "CONTEXT_OPTIONS"}]
  },
  "VHS_VideoCombine": {
    "input": {
      "optional": {},
      "required": {
        "images": {"type": "IMAGE"}
      }
    },
    "outputs": [{"name": "GIF", "type": "GIF"}]
  }
}
```

Warnings also present in the packet:

```text
precedent semantic gate: excluded ComfyUI-AnimateDiff-Evolved because model families ['animatediff'] do not match requested ['hotshot']
```

This warning directly conflicts with the selected workflow's own semantics, which had both `hotshot` and `animatediff`.

## Current Edit-Agent Research Guidance

Source: first system message in `model_request.json`.

```text
Use current authoring-schema lookup only when needed: existing nodes are shown above, so do NOT search for them. Reference EXISTING nodes by EXACT names from the rendered Python. Bare ambiguous refs are rejected. Exception: if Revision evidence or the Research brief says an existing custom/provisional class has an unknown schema and that exact class is the edit target, search that exact class to hydrate its schema before editing. Search first: use schema lookup for a NEW node TYPE you want to ADD; only `search(focus_types=["X"])` for a NEW exact node TYPE you intend to add. `search(...)` is factual current authoring-schema lookup, not workflow/web research, and never justifies substituting a merely similar node for the user's named target. A local miss is not a product-level failure: continue with workflow/registry resolution when the request names an external pattern, then edit only if that resolution yields schema-backed authoring capability. If schema-backed registry evidence identifies a supported pack, use the resolved class; VibeComfy will install it automatically. Do not tell the user to install nodes.
```

```text
Research strategy (bounded guidance): A Research brief is search direction, not an answer. Use separate evidence-tier calls — `research("...", sources=[...])`, one tier per call (`workflows`, `registry`, `messages`, `web`); never mix internal workflow search with web/registry in one call. For edit-by-precedent: `workflows` → `messages` → `registry` → `web`; for knowledge questions: `messages` then `workflows`. Anchor each query on the smallest named class/field/socket visible in the graph — never search the raw user sentence or guess class names (no `search(focus_types=[...])` for guessed names); workflow context is mandatory for named external requests. Before editing, extract a concrete node-combination reference (class types, input/output roles, terminal consumer, visible params); if none is defensible, keep researching or `clarify()` instead of splicing, and apply the smallest evidence-supported edit. Hydrate an exact target class with `search(focus_types=["X"])` or `research("X field", sources=["registry", "workflows"])` before editing an external/schema-fragile node, then land only the requested change when schema-backed authoring data is available. Supported node setup is automatic; your job is to ground the schema, not request installation. Never write a field/socket not visible in the render, catalog, `search(...)`, or exact-class schema — pick a visible nearby field or keep researching. Opaque `widget_N` needs a corroborating `search()`/schema hit or a self-evident current value, else `clarify()`. Use `clarify()` only after exact-class research still cannot identify the target.
```

This is the immediate reason the edit model searched more:

- It was told workflow context is mandatory, but also that the brief is "not an answer."
- It was told to hydrate exact target classes before editing.
- It saw local schema misses for workflow classes.
- It saw a registry semantic warning excluding AnimateDiff as not HotShot.
- It therefore looked for literal `HotShotXL` / `HotshotXL` node classes.

## What The Research Guidance Should Say Instead

The general prompt contract should guide research toward workflow grounding, not local-schema validation:

```text
For edit-by-precedent requests, research's primary job is to select and interpret the best workflow precedent. Do not use local installed schemas to decide what the target workflow pattern is.

When compatible workflow precedents are found, return a workflow-grounded conclusion:
- selected precedent name/path/source
- why it matches the user request
- exact matched requirement terms from title/path/body/models
- model/product/task requested by the user
- node ecosystem used by the workflow
- minimal node spine to adapt
- terminal output path
- parseability/promotion evidence
- misleading follow-up searches to avoid

Distinguish user-requested requirement terms from implementation ecosystem terms. A requested model, product, or task may be implemented through a differently named node ecosystem. Do not treat that as a contradiction when the workflow itself links them.

Registry and local schema checks are authoring/resolution evidence, not research grounding evidence. They may determine whether a selected workflow can be instantiated later, but they must not replace or reinterpret the selected workflow pattern.
```

For this specific turn, a good research conclusion would have been:

```text
Selected workflow precedent: AnimateDiff Video Generation with ControlNet and IP-Adapter.

Why it matches: the workflow path contains HotShotXL, the workflow model list contains hotshotxl_mm_v1.pth, it is parseable, has compiled API evidence, uses SDXL/AnimateDiff motion nodes, and outputs video via VHS_VideoCombine.

Interpretation: HotShotXL is the motion model/module requirement. AnimateDiff Evolved is the node ecosystem used by this workflow to run that motion model. Do not search for a literal HotShotXL node unless a selected workflow contains one.

Minimal spine: CheckpointLoaderSimple -> ADE_AnimateDiffUniformContextOptions -> ADE_AnimateDiffLoaderWithContext -> KSamplerAdvanced -> VAEDecode -> VHS_VideoCombine.
```
