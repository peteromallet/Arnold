# Workflow Precedent Research Plan

## Goal

For complex workflow-edit requests, VibeComfy should find a validated existing
workflow pattern before editing the user's graph. The research step should answer:

> What known-good workflow should this edit imitate?

The implementation step should then answer:

> How do we apply that pattern to this exact current graph?

This is different from generic web search. The desired research output is a
structured precedent, with provenance and conversion evidence, that can be fed
directly into the graph-edit agent.

## Current State

The executor already has a four-stage shape:

```text
classify -> research -> implement -> reply
```

Relevant current pieces:

- `vibecomfy/executor/core.py` orchestrates the pipeline.
- `vibecomfy/executor/contracts.py` defines `ClassifyDecision`,
  `ResearchResult`, `ImplementationResult`, and `ExecutorResult`.
- `vibecomfy/executor/research.py` searches local corpus, Hivemind, then a
  DuckDuckGo HTML fallback.
- `vibecomfy/comfy_nodes/agent/edit.py` receives `research_summary`,
  `research_sources`, and `executor_research` and injects them into the edit
  prompt.
- `vibecomfy/commands/port/_convert.py` and `vibecomfy/porting/convert.py`
  already convert ComfyUI JSON workflows to VibeComfy Python scratchpads or
  ready-template candidates.
- `scripts/upload_ready_templates_to_hivemind.py` already uploads curated
  Python ready templates to Hivemind and supports `--dry-run`.

The missing piece is a first-class "workflow precedent" artifact. Today,
research returns flat source dictionaries and a prose summary. That is enough
to nudge the model, but not enough to reliably make research produce a reusable
validated workflow reference for execution.

## Scope And Non-Goals

Precedent research is a specialized lane for pattern-adaptation edits. It should
not become the default executor for every request that feels difficult.

The shared substrate should be graph-native inspection and validation with
Python-rendered evidence when useful. `PrecedentAdaptationPlan` sits on top only
when the user asks for a workflow-pattern change that benefits from imitating a
known-good precedent.

Routing matrix:

| User task class | Route | Use precedent research? | Notes |
| --- | --- | --- | --- |
| Widget or parameter update | `direct_edit` | No | Seed, prompt, steps, CFG, filename prefix, resolution. |
| Obvious single-node tap | `direct_edit` | No | Example: add `PreviewImage` after a clear `IMAGE` output. |
| Current-graph explanation | `inspect_only` | No | Can fetch graph slices/Python evidence for explanation, but must not edit. |
| Multi-node model-family pattern | `precedent_research` | Yes | Example: LTX audio/video latent path, Wan control path, LoRA stack. |
| External pattern not found locally | `precedent_research` | Yes, gated | Preview/fetch/convert/validate before use. |
| Ambiguous workflow request | `clarify` | Not yet | Example: "add audio" could mean background music, lipsync, or audio-reactive conditioning. |
| Model or asset configuration swap | `asset_lookup` -> `direct_edit` | Usually no | Use model registry/asset validation, not precedent slices unless topology changes. |
| Existing broken or dangling graph | `diagnose_repair` | Maybe as confirmation | Diagnose current graph first; use precedent only to confirm intended pattern. |
| Composite multi-pattern edit | `decompose` -> iterative `precedent_research` | Per subgoal | One precedent slice per subgoal; validate between steps. |
| Runtime preview/eval of a node | `subgraph_preview` | No | Use runtime eval/preview machinery; do not treat as durable workflow edit. |

Do not use the precedent route for simple edits, pure inspection, asset swaps
that do not change topology, repair-first tasks where the intended pattern is
already present, or runtime preview/eval requests.

## Desired Decision Behavior

The classify stage should distinguish simple edits from workflow-pattern edits.

Suggested internal shape:

```json
{
  "intent": "edit",
  "route": "precedent_research",
  "implement": true,
  "research": true,
  "edit_complexity": "complex",
  "research_goal": "find_workflow_precedent",
  "model_families": ["LTX"],
  "pattern_category": "image-to-video custom audio",
  "change_goal": "add user-provided audio input"
}
```

Rules:

- `direct_edit`: execute directly.
- `precedent_research`: run precedent research first.
- `inspect_only`: inspect graph and reply, no graph edit.
- `clarify`: ask a focused question before research or implementation.
- `asset_lookup`: resolve model/asset/config changes, then direct edit.
- `diagnose_repair`: diagnose current graph validity/connectivity first.
- `subgraph_preview`: run preview/eval machinery, not durable workflow edit.
- `respond_only`: answer without graph operations.

The important boundary is that classify should produce routing facts, not just
advice. A downstream research agent should not have to infer from prose whether
it is looking for a node signature, a workflow precedent, or a general answer.
At minimum, classification should carry:

- `route`: one of the route names above;
- `task_class`: `widget_update`, `obvious_node_add`, `pattern_add`,
  `pattern_replace`, `inspect`, `asset_swap`, `diagnose_repair`,
  `preview_eval`, or `respond`;
- `research_goal`: `none`, `find_workflow_precedent`,
  `find_node_signature`, or `answer_question`;
- `edit_complexity`: `simple`, `complex`, or `none`;
- `model_families` and constrained `pattern_category` when known;
- `change_goal`: a short imperative describing what implementation must do.

Examples of edits that should request precedent research:

- model-family-specific video edits, such as LTX, Wan, Flux, SVD, Hotshot.
- custom-node-pack-specific edits where socket semantics are not obvious.
- multi-node feature additions, such as lipsync, custom audio, second-pass
  refinement, interpolation, LoRA stacks, control paths, and guide injection.

Examples that should usually skip precedent research:

- change a seed, prompt, filename prefix, step count, CFG value, or resolution
  field already visible in the current graph.
- add an obvious save/preview node when the source socket is clear.
- answer a question about the current graph.

## Desired Research Behavior

Research should primarily find validated workflow precedents, not arbitrary
documentation.

Search order:

1. Local ready templates and repo examples.
2. Existing Hivemind workflow resources.
3. External public web results.

For model-family-specific work, research queries should include the family and
workflow pattern, for example:

- `LTX RuneXX custom audio workflow`
- `LTX image to video lipsync ComfyUI workflow`
- `Wan 2.2 image to video LoRA workflow`
- `Flux ControlNet workflow ComfyUI`

The research stage should select the closest precedent and explain why it is
appropriate. It should prefer sources that are:

- local or already indexed in Hivemind,
- represented as VibeComfy Python,
- converted successfully from JSON,
- structurally validated,
- tied to the same model family or custom-node pack,
- close to the current graph's task and media type.

## Proposed Precedent Contract

Add a structured object, either as a dataclass or as a typed dictionary, carried
inside `ResearchResult`.

```python
@dataclass(frozen=True)
class PrecedentWorkflow:
    title: str
    source_kind: str          # local | hivemind | web
    source_url: str | None
    source_path: str | None
    source_hash: str | None
    local_json_path: str | None
    converted_python_path: str | None
    converted_python: str | None
    model_family: str | None
    workflow_pattern: str | None
    relevant_nodes: tuple[str, ...]
    relevant_pattern: str
    validation: dict[str, Any]
    hivemind_id: str | None = None
```

Extend `ResearchResult`:

```python
@dataclass(frozen=True)
class ResearchResult:
    summary: str = ""
    sources: tuple[dict[str, Any], ...] = ()
    precedents: tuple[PrecedentWorkflow, ...] = ()
    warnings: tuple[str, ...] = ()
```

The existing `sources` field can remain for compatibility. New code should use
`precedents` when it needs an executable implementation handoff.

## Summary And Detail Access

Agents should not need to load entire workflow sources into context just to
decide whether a precedent is relevant. The workflow research surface should be
two-level:

1. A compact summary view for ranking and selection.
2. A focused detail view for fetching the exact nodes, links, or Python segment
   needed by implementation.

The internal representation should be graph-native: normalized `VibeWorkflow`
objects, graph topology, node schemas, socket compatibility, validation
diagnostics, and edit-session addresses. The agent-facing evidence should still
be Pythonic when that helps the agent reason. Python should be a rendering of a
selected graph slice, not the only source of truth.

In other words:

```text
normalized workflow graph
-> compact inspection summary
-> fetched graph slice
-> Python-rendered evidence
-> adaptation plan
-> edit operations
-> validated candidate graph
-> emitted Python / Comfy API
```

For ready templates and converted external workflows, summaries and slices
should be built from the normalized workflow graph. Stable Python-like names can
come from the existing emission naming layer. Raw ComfyUI graph JSON should not
be the primary agent surface, but the system should avoid overfitting the design
to AST parsing of ready-template Python.

### Existing Summary Surfaces

VibeComfy already has partial summary surfaces:

- `vibecomfy workflows list --ready --json` returns ready-template metadata:
  template id, path, capability, public inputs, public outputs, custom nodes,
  model count, readiness, coverage tier, and status flags.
- `vibecomfy workflows lens <template-or-path> --json` returns a topology
  summary: workflow id, node count, edge count, registered inputs, outputs, and
  per-node upstream/downstream IDs.
- `vibecomfy/executor/research.py` returns ranked source rows with class type,
  score, reasons, source, path, description, and tasks.

Those are useful, but they are not yet one agent-facing workflow-inspection API.
They also do not provide focused segment retrieval. An agent can find a workflow
path, but it cannot yet ask for "the audio-conditioning branch around node X" in
a stable structured way.

### Proposed Summary Shape

Add a compact precedent summary shape. It should bind Python names to node
identity so agents can search and navigate using source-level handles:

```json
{
  "precedent_id": "local:video/ltx2_3_i2v",
  "title": "video/ltx2_3_i2v",
  "source_kind": "local",
  "path": "ready_templates/video/ltx2_3_i2v.py",
  "capability": "video",
  "model_family": "LTX",
  "workflow_pattern": "image-to-video with audio/video latent path",
  "readiness": "ready",
  "node_count": 38,
  "edge_count": 50,
  "public_inputs": ["prompt", "negative_prompt", "image", "frames", "fps"],
  "public_outputs": ["SaveVideo"],
  "important_nodes": [
    {
      "python_name": "ltxvemptylatentaudio",
      "id": "3980",
      "class_type": "LTXVEmptyLatentAudio",
      "line": 125,
      "deps": ["ltxfloattoint", "ltxvaudiovaeloader"],
      "role": "audio latent source"
    },
    {
      "python_name": "ltxvconcatavlatent",
      "id": "4528",
      "class_type": "LTXVConcatAVLatent",
      "line": 200,
      "deps": ["ltxvemptylatentaudio", "ltxvimgtovideoconditiononly"],
      "role": "joins audio and video latents"
    }
  ],
  "segments": [
    {
      "segment_id": "audio_latent_path",
      "label": "Audio latent path",
      "python_names": [
        "ltxvaudiovaeloader",
        "ltxvemptylatentaudio",
        "ltxvconcatavlatent",
        "output",
        "ltxvaudiovaedecode",
        "createvideo"
      ],
      "node_ids": ["4010", "3980", "4528", "4802", "4818", "4819"],
      "reason": "Shows how LTX audio latents are introduced and decoded."
    },
    {
      "segment_id": "conditioning_path",
      "label": "Text/video conditioning path",
      "node_ids": ["4960", "2483", "2612", "1241", "4808"],
      "reason": "Shows how prompts feed LTX conditioning."
    }
  ],
  "validation": {
    "structural": "ok",
    "warnings": []
  }
}
```

This should be short enough to include several candidates in a research prompt.
It should avoid full Python source, full JSON, widget blobs, and large model
metadata.

### Inspection Summary

Function headers alone are too shallow for generated workflows, because most
ready templates expose only `build()`. The useful compact view is an inspection
summary: a graph-derived, topologically grouped set of important nodes,
dependency relationships, stable readable names, and named slices. It can be
rendered in a Python-like outline:

```text
L67: ltxvaudiovaeloader = LTXVAudioVAELoader(...)  # deps:
L125: ltxvemptylatentaudio = LTXVEmptyLatentAudio(...)  # deps: ltxfloattoint, ltxvaudiovaeloader
L174: ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(...)  # deps: emptyltxvlatentvideo, ltxvpreprocess, vae
L200: ltxvconcatavlatent = LTXVConcatAVLatent(...)  # deps: ltxvemptylatentaudio, ltxvimgtovideoconditiononly
L217: output = SamplerCustomAdvanced(...)  # deps: ltxvconcatavlatent, ltxvscheduler, multimodalguider, randomnoise
L248: ltxvaudiovaedecode = LTXVAudioVAEDecode(...)  # deps: audio_latent, ltxvaudiovaeloader
L270: createvideo = CreateVideo(...)  # deps: ltxvaudiovaedecode, ltxvtiledvaedecode_2
L279: savevideo = SaveVideo(...)  # deps: createvideo
```

Each summary row should carry:

- `python_name` or assigned output names;
- source line span;
- `_id` when present;
- class type or `raw_call` target;
- dependency names discovered from keyword arguments and `.out(...)` calls;
- consumers discovered from the reverse dependency index;
- comments or section labels when available.

This preserves Python-native readability while keeping graph-aware operations
and validation as the internal authority.

### Agent UX For Summary And Fetch

The research agent should experience workflow inspection as a small set of
Python-native moves:

1. Search for candidate precedents.
2. Read compact Python outlines for the top candidates.
3. Choose the closest precedent.
4. Fetch the exact graph slice or neighborhood it intends execution to imitate.
5. Hand execution both the conclusion and the fetched excerpt.

Example interaction:

```text
User request:
Add an audio input to this LTX image-to-video workflow.

Research tool call:
search_workflows("LTX image-to-video user audio input", model_family="LTX")

Tool result:
- ready:video/ltx2_3_i2v
  pattern: LTX image-to-video with audio/video latent path
  segments: audio_latent_path, video_conditioning_path, final_output_path
- hivemind:ltx_custom_audio_i2v
  pattern: public LTX custom audio i2v workflow
  segments: audio_input_path, audio_video_latent_join, final_av_decode
```

The agent then asks for an inspection summary, not a full workflow:

```text
get_inspection_summary("ready:video/ltx2_3_i2v", detail="compact")
```

The summary includes a concise Python-rendered view:

```text
L67: ltxvaudiovaeloader = LTXVAudioVAELoader(...)  # deps:
L125: ltxvemptylatentaudio = LTXVEmptyLatentAudio(...)  # deps: ltxfloattoint, ltxvaudiovaeloader
L174: ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(...)  # deps: emptyltxvlatentvideo, ltxvpreprocess, vae
L200: ltxvconcatavlatent = LTXVConcatAVLatent(...)  # deps: ltxvemptylatentaudio, ltxvimgtovideoconditiononly
L217: output = SamplerCustomAdvanced(...)  # deps: ltxvconcatavlatent, ltxvscheduler, multimodalguider, randomnoise
L248: ltxvaudiovaedecode = LTXVAudioVAEDecode(...)  # deps: audio_latent, ltxvaudiovaeloader
L270: createvideo = CreateVideo(...)  # deps: ltxvaudiovaedecode, ltxvtiledvaedecode_2
```

If the summary shows the right pattern, the agent fetches only the relevant
slice:

```text
fetch_slice("ready:video/ltx2_3_i2v", "audio_latent_path", render="python")
```

The fetched slice should contain graph-native data plus Python-rendered evidence
and enough metadata to keep it anchored:

```json
{
  "precedent_id": "ready:video/ltx2_3_i2v",
  "segment_id": "audio_latent_path",
  "line_span": [67, 270],
  "python_names": [
    "ltxvaudiovaeloader",
    "ltxvemptylatentaudio",
    "ltxvconcatavlatent",
    "output",
    "ltxvaudiovaedecode",
    "createvideo"
  ],
  "python_excerpt": "ltxvaudiovaeloader = LTXVAudioVAELoader(...)\\n...",
  "notes": "Audio becomes an LTX audio latent, joins the video latent before sampling, then is decoded into CreateVideo."
}
```

The execution handoff should include the exact fetched slice. The summary is for
selecting; the fetched slice is what execution imitates. The Python excerpt is
evidence for the agent, while the node IDs, edges, schemas, and socket metadata
remain the authoritative execution data.

Suggested handoff shape:

```json
{
  "selected_precedent_id": "ready:video/ltx2_3_i2v",
  "selected_segment_id": "audio_latent_path",
  "why_relevant": "Shows the LTX-specific audio latent branch and where it joins video sampling.",
  "implementation_instruction": "Adapt this pattern to the current graph. Do not add a loose LoadAudio node.",
  "selected_slice": {
    "node_ids": ["4010", "3980", "4528"],
    "python_excerpt": "ltxvaudiovaeloader = LTXVAudioVAELoader(...)\\n..."
  },
  "required_semantic_checks": [
    "audio input or loader exists",
    "audio path reaches LTX audio latent branch",
    "audio/video latent join happens before sampling",
    "video output remains present"
  ]
}
```

This keeps the context small without making execution reason from a lossy
summary. The summary ranks and selects; the fetch supplies the concrete pattern;
the handoff preserves concrete graph data and Python-rendered evidence for the
next stage.

### Proposed Detail Queries

After choosing a summary, the agent should be able to fetch focused detail by
stable identifiers:

```python
search_precedents(query, capability=None, model_family=None, task=None, limit=5) -> list[InspectionSummary]
get_inspection_summary(precedent_id, detail="compact") -> InspectionSummary
list_slices(precedent_id) -> list[SliceSummary]
fetch_slice(precedent_id, slice_id=None, anchor=None, radius=1, direction="both", render="python") -> WorkflowSlice
```

Suggested `WorkflowSlice` shape:

```json
{
  "precedent_id": "local:video/ltx2_3_i2v",
  "segment_id": "audio_latent_path",
  "format": "python",
  "python_names": [
    "ltxvaudiovaeloader",
    "ltxvemptylatentaudio",
    "ltxvconcatavlatent",
    "output",
    "ltxvaudiovaedecode",
    "createvideo"
  ],
  "node_ids": ["4010", "3980", "4528", "4802", "4824", "4818", "4819"],
  "class_types": [
    "LowVRAMAudioVAELoader",
    "LTXVEmptyLatentAudio",
    "LTXVConcatAVLatent",
    "SamplerCustomAdvanced",
    "LTXVSeparateAVLatent",
    "LTXVAudioVAEDecode",
    "CreateVideo"
  ],
  "edges": [
    {"from": "4010", "slot": 0, "to": "3980", "input": "audio_vae"},
    {"from": "3980", "slot": 0, "to": "4528", "input": "audio_latent"}
  ],
  "python_excerpt": "...",
  "notes": "This segment shows the source audio latent path and where it joins the video latent path."
}
```

Detail fetches should support:

- `render="summary"` for node IDs/classes/edges only;
- `render="python"` for an agent-facing Python excerpt;
- `render="json"` for raw UI/API JSON only when explicitly needed;
- `radius` around anchor nodes;
- class-type filters;
- named segment IDs discovered from the summary.

### Challenges To Design For

The Python-native approach is the right interface, but it creates a few concrete
implementation challenges:

- Stable identity: generated variable names are readable but can drift, so every
  summary entry must bind readable name, `_id`, `class_type`, assigned outputs,
  and source line span.
- Segmentation: source comments are helpful but insufficient. Segment labels
  should be derived from dependency paths and class-type roles, then improved by
  comments or curated Hivemind annotations.
- Fidelity: tuple unpacking, `raw_call`, `.out(0)`, final `wf.finalize(...)`
  calls, public input targets, and patches must be represented. Dropping any of
  these can make the excerpt misleading.
- Compactness: the research stage should rank candidates from summaries and
  fetch only one or two focused neighborhoods. Whole-workflow source should be
  a deliberate fallback.
- Conversion consistency: external JSON workflows should become normalized
  workflows first, then be indexed through the same inspection/slice system as
  local Python. Avoid maintaining one navigation model for local Python and
  another for external JSON.

### Segment Discovery

Initial segment discovery can be heuristic:

- start from public inputs and outputs;
- group one-hop/two-hop neighborhoods around matching class types;
- group paths between important class types, such as loaders, encoders,
  samplers, decoders, and save nodes;
- use model-family vocabularies for LTX/Wan/Flux-specific roles;
- label segments with short, non-authoritative roles.

Later, Hivemind uploads can include curated segment annotations so future agents
do not need to rediscover them.

### Prompt Contract

Research should include summaries first. It should fetch details only for the
chosen candidate or for a small number of close candidates.

Implementation should receive only the detail segment it needs, plus the compact
implementation brief. It should not receive every node in a large workflow unless
the task truly requires whole-workflow comparison.

## External Workflow Ingestion

When research finds an external public ComfyUI JSON workflow, the ingestion path
should be explicit and gated:

1. Preview URL with timeout, byte-size hint, content type, domain/provenance
   signals, and suspicious-pattern scan.
2. Fetch URL only if preview passes.
3. Parse JSON as data only.
4. Detect workflow shape.
5. Run port analysis/conversion into a normalized workflow.
6. Validate generated workflow, conversion loss, and parity when possible.
7. Assign a machine-readable trust tier and loss summary.
8. Create a workflow precedent with provenance and diagnostics.
9. Optionally upload the converted public workflow to Hivemind.

Treat external JSON as hostile until it passes intake. The conversion pipeline
already has useful post-conversion checks, but external intake needs its own
fail-closed gate before generated Python is imported or uploaded.

Pre-conversion gates should include:

- maximum byte size, nesting depth, node count, and link count;
- canonical content hash and source URL dedupe;
- source URL, license, and provenance capture;
- rejection or quarantine for absolute local paths and `file://` references;
- class-type and dependency allowlist checks against known custom-node packs;
- quarantine for `vibecomfy.exec`, unknown classes, network/download nodes, and
  file-writing nodes;
- no low-confidence provenance for execution-capable nodes.

Conversion output should include:

- `trust_tier`: `trusted`, `converted_validated`, `warnings_only`,
  `quarantine`, or `reject`;
- `loss_summary`: dropped widgets, missing models, unresolved aliases, unknown
  classes, and any parity gaps;
- source hash and converted workflow hash;
- capped fetch count and retry count.

Pre-upload gates should include:

- structural validation passed;
- parity and strict-ready checks passed when applicable;
- trust tier is high enough for reuse;
- no unresolved widget aliases or model-value drops;
- no local/private source references;
- source hash, converted-template hash, and validation evidence attached;
- dry-run envelope review before real Hivemind upload.

The conversion surface already exists, but the executor needs a small service
around it, for example:

```text
vibecomfy/executor/precedents.py
```

Suggested responsibilities:

- `find_precedents(query, decision, graph) -> list[PrecedentWorkflow]`
- `fetch_external_workflow(url) -> DownloadedWorkflow`
- `convert_workflow_json(path, source_url) -> PrecedentWorkflow`
- `build_implementation_brief(precedent, request, graph) -> str`

## Hivemind Upload

External public workflows that pass conversion should be uploaded to Hivemind so
future agents find them before falling back to web search.

The existing `scripts/upload_ready_templates_to_hivemind.py` should be refactored
so its envelope builder and POST client are reusable from code. The script can
remain as a CLI wrapper.

Suggested upload metadata:

```json
{
  "asset_kind": "vibecomfy_workflow_precedent",
  "representation": "python",
  "source_url": "...",
  "source_hash": "...",
  "converted_from_json": "...",
  "model_family": "LTX",
  "workflow_pattern": "custom audio lipsync",
  "relevant_nodes": ["LoadAudio", "LTXVAudioVAEEncode"],
  "conversion_status": "ok"
}
```

Upload rules:

- Never auto-upload a user's private canvas.
- Only upload external public sources with provenance.
- Dedupe by source URL and content hash.
- Record conversion warnings.
- Use `--dry-run` behavior in tests.
- Require `HIVEMIND_CONTRIBUTOR_KEY` for real upload.

## Composite Edits

Composite requests should be decomposed before research. Do not merge unrelated
precedents into one invented pattern.

Example:

```text
User request:
Add ControlNet-style pose guidance and a LoRA stack to this Wan I2V workflow.
```

Suggested decomposition:

```json
{
  "route": "decompose",
  "subgoals": [
    {
      "task_class": "pattern_add",
      "pattern_category": "pose_guidance",
      "route": "precedent_research"
    },
    {
      "task_class": "pattern_add",
      "pattern_category": "lora_stack",
      "route": "precedent_research"
    }
  ],
  "validation_strategy": "apply_and_validate_each_subgoal"
}
```

Each subgoal should select at most one precedent slice by default, build its own
adaptation plan, apply edits, and validate before the next subgoal starts. If
two precedents imply incompatible anchors or socket requirements, stop for
clarification instead of merging them.

## Execution Handoff

The implementation step should not receive a full raw research dump. It should
receive a compact implementation brief.

For precedent-driven edits, the handoff should be a structured
`PrecedentAdaptationPlan`, not a general whole-graph mapping.

Suggested shape:

```json
{
  "precedent_id": "ready:video/ltx2_3_i2v",
  "selected_slice_id": "audio_latent_path",
  "selected_slice": {
    "node_ids": ["4010", "3980", "4528", "4802", "4818", "4819"],
    "render": "python",
    "python_excerpt": "ltxvaudiovaeloader = LTXVAudioVAELoader(...)\\n..."
  },
  "why_relevant": "Shows the LTX-specific audio latent branch and where it joins video sampling.",
  "anchor_bindings": [
    {
      "precedent_name": "ltxvconcatavlatent",
      "precedent_role": "audio/video latent join",
      "current_anchor": {
        "node_id": "current_sampler",
        "class_type": "SamplerCustomAdvanced",
        "input": "latent_image"
      },
      "binding_type": "insert_before",
      "socket_evidence": {
        "source_type": "LATENT",
        "target_type": "LATENT",
        "compatible": true
      },
      "confidence": "high"
    }
  ],
  "required_new_nodes": [
    {"class_type": "LoadAudio", "role": "user audio input"},
    {"class_type": "LTXVAudioVAELoader", "role": "LTX audio VAE"},
    {"class_type": "LTXVEmptyLatentAudio", "role": "audio latent source"},
    {"class_type": "LTXVConcatAVLatent", "role": "join audio and video latents"}
  ],
  "required_rewires": [
    "route existing video latent into LTXVConcatAVLatent.video_latent",
    "route new audio latent into LTXVConcatAVLatent.audio_latent",
    "route concat output into existing sampler latent_image",
    "route decoded audio into existing CreateVideo.audio"
  ],
  "avoid_patterns": [
    "do not leave LoadAudio dangling",
    "do not attach audio only at the final video node if LTX sampling needs AV latent input"
  ],
  "semantic_checks": [
    "audio input or loader exists",
    "audio path reaches LTX audio latent branch",
    "audio/video latent join happens before sampling",
    "video output remains present"
  ]
}
```

The implementation agent consumes this plan with the current editable graph
projection and emits edit operations. It should not paste the precedent Python
verbatim. The terminal flow is:

```text
selected_slice + anchor_bindings + required_new_nodes + required_rewires
-> edit_ops[]
-> candidate_graph
-> structural validation
-> semantic task validation
-> emitted Python / Comfy API
```

Example:

```text
User asked: add user-provided voice audio to the current LTX image-to-video graph.

Best precedent: LTX RuneXX custom audio lipsync workflow.
Source: ready_templates/video/ltx2_3_runexx_lipsync_custom_audio.py

Why relevant:
The precedent shows the LTX/RuneXX-specific path for custom audio, rather than
adding a generic unattached LoadAudio node.

Pattern to adapt:
- Add or expose a LoadAudio-style user audio input.
- Encode audio through the LTX/RuneXX audio encoder path.
- Wire the encoded audio into the lipsync/custom-audio conditioning node.
- Preserve the current I2V image/video path.

Current graph anchors:
- Existing LTX I2V model/conditioning path.
- Existing video output/combine node.

Avoid:
- Switching to a generic audio-only workflow.
- Leaving the audio loader unattached.
```

Worked example:

```text
Research selected:
ready:video/ltx2_3_i2v / audio_latent_path

Fetched evidence:
ltxvemptylatentaudio = LTXVEmptyLatentAudio(...)
ltxvconcatavlatent = LTXVConcatAVLatent(
    audio_latent=ltxvemptylatentaudio,
    video_latent=ltxvimgtovideoconditiononly,
)
output = SamplerCustomAdvanced(..., latent_image=ltxvconcatavlatent)

Adaptation:
- bind precedent video-latent join before the current sampler's `latent_image`;
- add the missing audio latent branch;
- preserve the existing video decode/output path;
- connect decoded audio into the existing `CreateVideo.audio` if present.

Execution form:
add_node(LoadAudio)
add_node(LTXVAudioVAELoader)
add_node(LTXVEmptyLatentAudio)
add_node(LTXVConcatAVLatent)
connect(existing_video_latent, concat.video_latent)
connect(audio_latent, concat.audio_latent)
connect(concat, sampler.latent_image)
connect(decoded_audio, create_video.audio)

Validation:
- no dangling audio input;
- sampler receives the joined AV latent;
- video output remains present;
- candidate graph compiles and can be emitted as Python/API.
```

The edit prompt should continue to enforce:

- search output is discovery only,
- a graph edit request must land actual edits,
- `clarify()` is terminal and produces no candidate,
- `done()` only commits landed edits.

## Validation

VibeComfy already validates candidate edits structurally. See
`docs/agent-edit/validation-boundaries.md` for the current validation boundary.

For precedent-driven work, add one more advisory semantic layer:

- requested audio input -> candidate contains an audio node or audio public input;
- requested LTX/RuneXX path -> candidate includes relevant LTX/RuneXX nodes or
  connections;
- requested video workflow -> video output remains present;
- requested precedent pattern -> expected node family appears in candidate.

This semantic check should not replace structural validation. It should produce
clear diagnostics and, for high-confidence misses, block the candidate or force
another agent turn.

## Test Plan

Unit tests:

- classify emits `edit_complexity` and `research_goal` for complex workflow edits.
- local/Hivemind sources can become `PrecedentWorkflow` records.
- external workflow fetch rejects oversized, non-JSON, and private/local-only
  sources.
- JSON conversion returns converted Python and validation diagnostics.
- Hivemind upload dry-run emits the expected envelope.
- duplicate source URL/hash does not upload twice.

Executor tests:

- simple edit skips precedent research.
- LTX custom-audio edit requests precedent research.
- research result includes a `PrecedentWorkflow`.
- implement payload includes an implementation brief.
- implementation still receives legacy `research_summary` and `research_sources`
  for compatibility.

Structural harness:

- Update `ltx-i2v-audio-research-execute` so the evidence proves:
  - research found a local or Hivemind precedent;
  - if external JSON was used, it was converted to Python;
  - implementation consumed the precedent brief;
  - candidate contains structural audio-related nodes;
  - candidate remains valid.

Security tests:

- malicious JSON cannot declare trusted provenance.
- embedded `vibecomfy.exec` source is bounded.
- external downloads are byte-limited.
- private/user canvas workflows are not uploaded.

## Implementation Order

1. Land prompt/report cleanup that makes search clearly discovery-only.
2. Extend classify output with edit complexity and precedent-research hints.
3. Add `PrecedentWorkflow` and `ResearchResult.precedents`.
4. Build local/Hivemind precedent extraction from existing Python workflow
   sources.
5. Add external JSON fetch and conversion behind strict safety gates.
6. Refactor Hivemind upload into reusable code.
7. Generate implementation briefs and pass them into `handle_agent_edit`.
8. Add semantic task-satisfaction validation.
9. Update executor and structural harness tests.
