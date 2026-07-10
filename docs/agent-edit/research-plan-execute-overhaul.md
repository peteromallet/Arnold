# Agent Edit Research -> Plan -> Execute Overhaul

## Problem

The current agent-edit flow can find the right workflow precedent and still apply an incomplete graph edit.

The HotShotXL failure is the concrete example:

- The user asked: "Switch this to instead generate 8 frames of video using HotShotXL."
- Research found a relevant HotShotXL/AnimateDiff workflow precedent.
- Execute added `ADE_AnimateDiffUniformContextOptions` and `ADE_AnimateDiffLoaderWithContext`.
- Execute did not wire `motion_model.MODEL` into the sampler.
- Execute did not add or wire an 8-frame latent/image batch path.
- Execute did not add a video terminal such as `VHS_VideoCombine`.
- The graph still effectively ended as an image workflow.
- `done()` was accepted because some edits landed.

The failure is not mainly that research chose the wrong nodes. It is that the system handed execution evidence, not a graph contract, and then accepted a partial sidecar edit.

## Current Boundary Problem

Today the stages are roughly:

1. Classify the user request.
2. Optionally research precedent.
3. Execute graph edits in a batch REPL.
4. Validate syntax/lowering/UI/queue enough to decide whether a candidate can be shown/applied.

This leaves two gaps:

1. Research returns relevant material, but not a mandatory implementation contract.
2. Execute is asked to infer a multi-node workflow transformation from loose evidence.

That makes the system vulnerable to "ingredient edits": adding the right node classes without connecting them into the active execution path.

## Target Architecture

Use three distinct stages for structural precedent-backed edits:

```text
research -> plan -> execute
```

Each stage has a narrow job.

### Research

Research gathers evidence.

It should answer:

- Which workflow precedents match the user's requested technology or behavior?
- What reusable graph pattern do those precedents show?
- What node classes participate in the pattern?
- What role does each node play?
- Which edges connect those roles?
- Which terminal/output node completes the pattern?
- Which widget values or model filenames explain the named technology?
- Which parts are required versus optional decoration?

Research must not:

- Validate local installation.
- Decide exact current-graph rewires.
- Ask whether a class is locally addable.
- Search registry/provider packs unless the user explicitly asked about installation/provider information.
- Produce implementation code.

### Plan

Plan converts research evidence plus the current graph into a machine-checkable implementation contract.

It should answer:

- Which precedent is selected?
- How does that precedent map onto the current graph?
- Which existing nodes are the role anchors?
- Which new nodes must be added?
- Which existing wires must change?
- Which values must be set?
- Which terminal output must exist?
- What conditions make `done()` valid?

Plan is the authority for execution. Execute should not reinterpret the named technology or swap in a different workflow family.

Important naming rule: do not reuse the existing `PrecedentAdaptationPlan` as this authoritative plan.

The current code already has several precedent-bearing contracts:

- `SelectedPrecedent`
- `PrecedentPacket`
- `WorkflowSlice`
- `PrecedentAdaptationPlan`

Those are research/context contracts. In current semantics, `PrecedentAdaptationPlan` can be neutral, can leave validation as `not_evaluated`, and can omit concrete required rewires. Treat it as evidence. The new object should be a separate typed `ExecutionPlan`.

### Execute

Execute implements the plan.

It should:

- Use exact planned classes.
- Use `search(focus_types=[...])` only to hydrate exact planned classes.
- Use workflow-provisional schemas when exact workflow classes are available from research.
- Apply the planned graph edits.
- Stop only when plan validation passes or a specific planned step is impossible to author.

Execute should not:

- Broaden research.
- Search for branded replacement classes.
- Decide a different workflow pattern.
- Call `done()` while required plan conditions are unsatisfied.

## When To Use This Flow

Do not run `research -> plan -> execute` for every request.

Use it when success depends on a multi-node workflow pattern or external precedent.

Good triggers:

- Named external technology/model family not already obvious in graph:
  - HotShotXL
  - Wan
  - LTX
  - AnimateDiff
  - IPAdapter
  - ControlNet
- Output-domain changes:
  - image -> video
  - image -> 3D
  - audio -> video
  - "generate N frames"
  - "export as mp4" when no local sink is obvious
- Multi-node graph rewrites:
  - "turn this img2img workflow into video"
  - "add face detailer and upscale"
  - "add ControlNet with depth"
  - "make it use reference image conditioning"
- Requests where the agent must identify a known workflow pattern:
  - "make this like X"
  - "use the standard Foo workflow"
  - "switch to a Foo pipeline"

Do not use it for small local edits:

- Prompt text changes.
- Seed/steps/CFG/sampler changes.
- Checkpoint dropdown changes.
- Bypass/mute/enable/delete.
- Direct rewires between visible nodes.
- Adding a simple local preview/save/output node.
- Local parameter tweaks.

Small edits should stay:

```text
classify -> execute -> validate
```

For medium local edits, use direct execute with exact local schema lookup as needed, not full precedent planning.

## Classifier Contract

The classifier should not grow conflicting route state. Prefer deriving the new behavior from existing route/task vocabulary:

```text
route == "adapt" + precedent triggers -> needs execution plan
route == "revise" or local edit -> direct execute
```

If an explicit flag is added, it must be versioned and have conflict rules:

```json
{
  "contract_version": "classify_vNext",
  "needs_precedent_plan": true,
  "reason": "external_named_video_workflow_adaptation",
  "route": "adapt"
}
```

Examples:

```json
{
  "needs_precedent_plan": false,
  "reason": "single_visible_field_change",
  "route": "parameter_tweak"
}
```

```json
{
  "needs_precedent_plan": true,
  "reason": "image_to_video_named_model_family",
  "route": "adapt"
}
```

The decision rule:

```text
If success depends on a known existing node/field in the current graph, execute directly.
If success depends on discovering and applying a reusable multi-node workflow pattern, use research -> plan -> execute.
```

Classifier guidance should preserve absent named technologies for research. A named technology not visible in the graph is not a reason to suppress that term; it is the main signal that precedent planning is needed.

## Research Output Shape

Research should output pattern evidence, not just relevant search hits.

Suggested shape:

```json
{
  "research_goal": "Find workflow patterns for generating video with HotShotXL from a current image/img2img graph.",
  "selected_precedent_candidates": [
    {
      "name": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
      "source": "workflow",
      "source_url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
      "why_relevant": [
        "filename mentions HotShotXL",
        "workflow contains hotshotxl_mm_v1.pth",
        "workflow uses AnimateDiff motion model with SDXL",
        "workflow terminates in VHS_VideoCombine"
      ],
      "confidence": "high",
      "node_roles": [
        {
          "role": "base_model_loader",
          "class_type": "CheckpointLoaderSimple",
          "outputs": {"model": "MODEL", "clip": "CLIP", "vae": "VAE"},
          "important_values": {
            "checkpoint_family": "SDXL"
          }
        },
        {
          "role": "context_options",
          "class_type": "ADE_AnimateDiffUniformContextOptions",
          "outputs": {"context_options": "CONTEXT_OPTIONS"},
          "important_values": {
            "widget_0": 8,
            "widget_1": 1,
            "widget_2": 3,
            "widget_3": "uniform",
            "widget_4": false
          }
        },
        {
          "role": "motion_model_loader",
          "class_type": "ADE_AnimateDiffLoaderWithContext",
          "inputs": {"model": "MODEL", "context_options": "CONTEXT_OPTIONS"},
          "outputs": {"model": "MODEL"},
          "important_values": {
            "widget_0": "hotshotxl_mm_v1.pth",
            "widget_1": "linear (HotshotXL/default)"
          }
        },
        {
          "role": "sampler",
          "class_type": "KSamplerAdvanced",
          "inputs": {"model": "MODEL", "latent_image": "LATENT"},
          "outputs": {"latent": "LATENT"}
        },
        {
          "role": "decoder",
          "class_type": "VAEDecode",
          "inputs": {"samples": "LATENT", "vae": "VAE"},
          "outputs": {"image": "IMAGE"}
        },
        {
          "role": "video_terminal",
          "class_type": "VHS_VideoCombine",
          "inputs": {"images": "IMAGE"},
          "outputs": {"filenames_or_gif": "VHS_FILENAMES|GIF"}
        }
      ],
      "pattern_edges": [
        ["base_model_loader.model", "motion_model_loader.model"],
        ["context_options.context_options", "motion_model_loader.context_options"],
        ["motion_model_loader.model", "sampler.model"],
        ["sampler.latent", "decoder.samples"],
        ["decoder.image", "video_terminal.images"]
      ],
      "terminal_pattern": {
        "role": "video_terminal",
        "class_type": "VHS_VideoCombine",
        "consumes_type": "IMAGE"
      },
      "frame_count_pattern": {
        "primary": {
          "role": "context_options",
          "field": "widget_0",
          "value": 8
        },
        "must_also_ensure": [
          "active latent/image path represents an 8-frame batch or sequence"
        ]
      },
      "optional_parts": [
        "ControlNet preprocessors",
        "IPAdapter branches",
        "PreviewImage nodes",
        "extra SaveImage outputs",
        "video loading if current graph starts from a single image"
      ],
      "unknowns": []
    }
  ]
}
```

Key rule: research should extract edges and roles. Class lists alone are not enough.

## Plan Output Shape

Plan should be compact, structured, and validation-friendly.

It should also be typed, persisted, and authoritative. The implementation should define dataclasses rather than pass untyped dicts through the system:

```python
ExecutionPlan
PlanStep
PlanCondition
RoleBinding
SocketRef
PlanEvaluation
```

The plan should use stable node/socket references, not only class names or REPL variable names. REPL names are useful for the model prompt, but validation should bind to stable graph identity where possible.

Suggested shape:

```json
{
  "contract_version": "execution_plan_v1",
  "plan_id": "hotshotxl_img2img_to_8_frame_video",
  "source_graph_hash": "<baseline structural hash>",
  "research_result_hash": "<hash of normalized research evidence>",
  "selected_precedent_id": "<stable source/workflow id>",
  "goal": "Convert the current image/img2img graph to generate an 8-frame HotShotXL video.",
  "selected_precedent": {
    "name": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
    "source_url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
    "implementation_ecosystem": ["AnimateDiff", "SDXL", "VHS"],
    "named_technology_mapping": {
      "HotShotXL": "AnimateDiff motion model file hotshotxl_mm_v1.pth"
    }
  },
  "current_graph_roles": {
    "base_model_loader": {
      "node_ref": {"uid": "n1", "var": "checkpointloadersimple"},
      "class_type": "CheckpointLoaderSimple",
      "confidence": "high"
    },
    "image_source": {
      "node_ref": {"uid": "n8", "var": "loadimage"},
      "class_type": "LoadImage",
      "confidence": "high"
    },
    "latent_encoder": {
      "node_ref": {"uid": "n9", "var": "vaeencode"},
      "class_type": "VAEEncode",
      "confidence": "high"
    },
    "sampler": {
      "node_ref": {"uid": "n5", "var": "ksampler"},
      "class_type": "KSampler",
      "confidence": "high"
    },
    "decoder": {
      "node_ref": {"uid": "n6", "var": "vaedecode"},
      "class_type": "VAEDecode",
      "confidence": "high"
    },
    "existing_image_terminal": {
      "node_ref": {"uid": "n7", "var": "saveimage"},
      "class_type": "SaveImage",
      "confidence": "high"
    }
  },
  "required_steps": [
    {
      "id": "add_context_options",
      "kind": "add_node",
      "criticality": "required",
      "class_type": "ADE_AnimateDiffUniformContextOptions",
      "assign_to": "context_opts",
      "schema_source": "workflow_provisional",
      "runtime_availability": "not_runtime_validated",
      "values": {
        "widget_0": 8,
        "widget_1": 1,
        "widget_2": 3,
        "widget_3": "uniform",
        "widget_4": false
      }
    },
    {
      "id": "add_motion_model",
      "kind": "add_node",
      "criticality": "required",
      "class_type": "ADE_AnimateDiffLoaderWithContext",
      "assign_to": "motion_model",
      "schema_source": "workflow_provisional",
      "runtime_availability": "not_runtime_validated",
      "inputs": {
        "model": "checkpointloadersimple.model",
        "context_options": "context_opts.context_options"
      },
      "values": {
        "widget_0": "hotshotxl_mm_v1.pth",
        "widget_1": "linear (HotshotXL/default)"
      }
    },
    {
      "id": "ensure_8_frame_latent_path",
      "kind": "ensure_batch_or_sequence",
      "criticality": "required",
      "target_count": 8,
      "preferred_classes": ["RepeatLatentBatch"],
      "source": "vaeencode.latent",
      "consumer": "ksampler.latent_image"
    },
    {
      "id": "rewire_sampler_model",
      "kind": "set_input",
      "criticality": "required",
      "target": "ksampler.model",
      "source": "motion_model.model"
    },
    {
      "id": "add_video_terminal",
      "kind": "add_node",
      "criticality": "required",
      "class_type": "VHS_VideoCombine",
      "assign_to": "video",
      "schema_source": "workflow_provisional",
      "runtime_availability": "not_runtime_validated",
      "inputs": {
        "images": "vaedecode.image"
      },
      "values": {
        "widget_0": 8,
        "widget_3": "video/h264-mp4"
      }
    }
  ],
  "done_conditions": [
    {
      "id": "motion_model_used",
      "type": "direct_edge_or_reachable_path",
      "source": "motion_model.model",
      "target": "ksampler.model"
    },
    {
      "id": "frame_count_8",
      "type": "value_or_path_count",
      "expected": 8,
      "acceptable_evidence": [
        "context_opts.widget_0 == 8",
        "RepeatLatentBatch.amount == 8 or equivalent active batch mechanism"
      ]
    },
    {
      "id": "video_terminal_exists",
      "type": "terminal_consumes",
      "class_type": "VHS_VideoCombine",
      "input": "images",
      "source_reaches": "vaedecode.image"
    }
  ],
  "active_path_conditions": [
    {
      "id": "active_model_path_uses_hotshot_motion_model",
      "source_role": "motion_model_loader",
      "target_role": "sampler",
      "source_socket": "model",
      "target_input": "model",
      "relationship": "direct_edge_or_reachable_path"
    },
    {
      "id": "active_output_domain_is_video",
      "terminal_role": "video_terminal",
      "terminal_class_type": "VHS_VideoCombine",
      "consumes_role": "decoder",
      "consumes_socket": "image"
    }
  ],
  "blocked_if": [
    {
      "condition": "planned class cannot be authored from installed schema or workflow-provisional schema",
      "action": "clarify with exact failed plan step"
    }
  ]
}
```

`PlanEvaluation` should be a separate typed result:

```json
{
  "contract_version": "plan_evaluation_v1",
  "plan_id": "hotshotxl_img2img_to_8_frame_video",
  "ok": false,
  "blocking": true,
  "source_graph_hash": "<baseline structural hash>",
  "candidate_graph_hash": "<candidate structural hash>",
  "step_status": [
    {"step_id": "add_context_options", "status": "satisfied"},
    {"step_id": "add_motion_model", "status": "satisfied"},
    {"step_id": "rewire_sampler_model", "status": "missing"}
  ],
  "failed_conditions": [
    {
      "condition_id": "motion_model_used",
      "severity": "critical",
      "message": "motion_model.model does not reach ksampler.model"
    }
  ],
  "feedback": "done() rejected: motion_model.model is not consumed by the sampler."
}
```

## Execute Prompt Requirements

Execute should receive the plan as a contract.

The prompt should say:

```text
You are implementing the execution_plan. It is authoritative unless it contradicts the user's explicit request.

Do:
- Implement required_steps.
- Hydrate exact planned class schemas with search(focus_types=[...]) when needed.
- Use workflow-provisional schemas for exact planned workflow classes.
- After each turn, continue with unsatisfied plan steps.

Do not:
- Reinterpret the selected technology.
- Search for alternative branded classes.
- Broaden research.
- Replace planned classes unless a planned step is impossible and you report that exact step.
- Call done() until done_conditions are satisfied.
```

Execute should see research only through the compiled plan and exact schema references. Once an `ExecutionPlan` exists, do not keep appending the full research packet to every prompt turn. The model should optimize against plan status, not against a large pile of precedent text.

The prompt should also include plan status on every later turn:

```text
Plan status:
- add_context_options: satisfied
- add_motion_model: satisfied
- ensure_8_frame_latent_path: missing
- rewire_sampler_model: missing; ksampler.model still points to checkpointloadersimple.model
- add_video_terminal: missing; no VHS_VideoCombine consumes vaedecode.image
```

This is more important than repeating the full research packet.

## Plan-Aware Done Guard

Prompting is not enough. `done()` must be validated against the plan.

Before accepting `done()`:

```text
validate_execution_plan(candidate_graph, execution_plan)
```

This should update a first-class `plan_validate_ok` gate:

```text
plan_validate_ok == true  -> critical plan conditions satisfied
plan_validate_ok == false -> no applyable candidate for precedent-backed adapt
```

The gate should be included in `StageResult.gate_updates`, `TurnContext`, response debug snapshots, and task satisfaction output.

If validation fails, reject `done()` and feed deterministic feedback into the next execute turn.

Example failure for the HotShotXL partial candidate:

```text
done() rejected: execution_plan is incomplete.
- motion_model_used failed: motion_model.model has no outgoing path to ksampler.model.
- frame_count_8 failed: no active 8-frame latent/image batch path was found.
- video_terminal_exists failed: no VHS_VideoCombine consumes vaedecode.image.
Continue editing; do not research again unless an exact planned class schema is missing.
```

The guard should catch:

- Newly added functional nodes whose outputs are unconsumed.
- Required model-patching nodes not reaching the sampler.
- Requested video output with no connected video terminal.
- Required frame/batch count not represented in the active path.
- Terminal output still being only the old image terminal for an image-to-video request.

Critical semantic plan blockers should not be bounded like syntax nudges. If the batch budget is exhausted while critical plan conditions are still false, the run should end as no-candidate/blocked, not accept the partial candidate.

## Apply Eligibility

Queue validation failure currently becomes `queue_blocked_warning` and remains applyable. That may be correct for candidates that intentionally include custom nodes the user still needs to install.

Do not globally change that rule without care.

Instead:

- Use plan validation to block semantically incomplete candidates before candidate/apply.
- Allow queue-blocked apply only when the plan is structurally satisfied and blockers are expected runtime/custom-node availability issues.

In other words:

```text
missing installed node, but plan graph is complete -> possibly applyable with warning
disconnected sidecar / missing terminal / unmet plan condition -> not applyable
```

Plan evaluation must run before candidate payload construction and apply eligibility. Queue-blocked warning is only valid after `plan_validate_ok` passes or no precedent plan applies.

## Small Edit Flow

Small edits should avoid research and plan model calls.

Examples:

- "Set steps to 30"
- "Change prompt to X"
- "Use seed 123"
- "Bypass this node"
- "Change CFG to 7"
- "Connect this visible node to that visible node"

Flow:

```text
classify -> execute -> local validation
```

Example classifier output:

```json
{
  "route": "parameter_tweak",
  "needs_precedent_plan": false,
  "operation": "set_field",
  "target_hint": "ksampler.steps",
  "value": 30
}
```

Validation:

```text
ksampler.steps == 30
graph loads
no unintended topology rewrite
```

Do not spend research/planning budget on these.

## Medium Edit Flow

Some edits are more than a parameter tweak but still do not need precedent.

Examples:

- Add a local `PreviewImage` after an existing image output.
- Add an upscaler if exact local class is known or found by compatible output search.
- Duplicate an output to two visible sinks.
- Add a save node for a known current output type.

Flow:

```text
classify -> execute with exact local schema lookup -> local validation
```

Use compatible-output search or exact schema lookup, but no research stage unless external precedent is needed.

## Implementation Plan

### 1. Add Plan Data Types

Add a small standalone module so the logic ports cleanly across branches:

```text
vibecomfy/comfy_nodes/agent/edit_plan.py
```

or, on the god-file-split branch:

```text
vibecomfy/comfy_nodes/agent/agent_edit/plan.py
```

Keep it independent of batch-loop file layout.

Suggested public functions:

```python
@dataclass(frozen=True)
class ExecutionPlan: ...

@dataclass(frozen=True)
class PlanStep: ...

@dataclass(frozen=True)
class PlanCondition: ...

@dataclass(frozen=True)
class RoleBinding: ...

@dataclass(frozen=True)
class SocketRef: ...

@dataclass(frozen=True)
class PlanEvaluation: ...

def needs_precedent_plan(classify_result, task, graph_facts) -> bool: ...

def build_execution_plan(
    *,
    task: str,
    current_python: str,
    graph: dict,
    research_result: Mapping[str, Any],
) -> ExecutionPlan: ...

def format_execution_plan_for_prompt(plan: ExecutionPlan) -> str: ...

def evaluate_execution_plan(
    *,
    graph: dict,
    python_render: str,
    plan: ExecutionPlan,
) -> PlanEvaluation: ...
```

Add state fields rather than overloading existing research fields:

```python
state.execution_plan
state.plan_evaluation
state.execution_plan_path
state.plan_evaluation_path
```

### 2. Build Plan From Research

Initial implementation can be deterministic and heuristic:

- Use `selected_precedent`.
- Use workflow schema and current graph roles.
- Recognize common roles:
  - checkpoint/model loader
  - sampler
  - VAE encode/decode
  - current terminal output
  - video terminal
- Use pattern edges extracted from workflow JSON when available.

Do not use `PrecedentAdaptationPlan` as the execution plan. Use it only as one evidence source. Build a new `ExecutionPlan` from normalized research, selected precedent, workflow schema, and current graph bindings.

Later, a model-backed planner can be added, but the first version should be small and auditable.

### 3. Add Plan To Execute Prompt

In adapt execution context:

- Include compact `execution_plan`.
- Include current `plan_status`.
- Suppress bulky research packet when a plan exists.
- Keep exact workflow schemas available through authoring surfaces/search, not as giant prompt text.

### 4. Add Done Guard

In the batch loop before `session.done()`:

```python
if done_requested and state.execution_plan:
    evaluation = evaluate_execution_plan(...)
    if not evaluation.ok:
        last_report += "\n\nNOTE: done() was NOT accepted — " + evaluation.feedback
        continue
```

This should be bounded like existing done nudges to avoid infinite loops, but it should not accept a candidate that violates critical required conditions.

The evaluation should also run after candidate graph construction and before `_build_candidate_payload(...)`, so a critical plan failure cannot be surfaced as an applyable candidate.

### 4a. Persist Plan Artifacts

Persist both plan and evaluation next to the existing turn artifacts:

```text
execution_plan.json
plan_evaluation.json
```

Expose them in `artifacts`, response debug payloads, and audit summaries. Include:

- `contract_version`
- `plan_id`
- `source_graph_hash`
- `candidate_graph_hash`
- `research_result_hash`
- `selected_precedent_id`
- idempotency key or derivation input
- per-step status
- failed conditions
- schema/runtime provenance for planned classes

Unknown newer plan/evaluation versions should fail closed to no-candidate, not fall back to direct execute.

### 5. Add Tests

Unit tests:

- Research evidence with HotShotXL workflow produces a plan with:
  - `ADE_AnimateDiffLoaderWithContext`
  - `ADE_AnimateDiffUniformContextOptions`
  - `VHS_VideoCombine`
  - sampler model rewire condition
  - video terminal condition
- Plan evaluation rejects:
  - motion model added but unused
  - no video terminal
  - sampler still using checkpoint model
- Plan evaluation accepts:
  - motion model reaches sampler
  - decoded images reach video combine
  - 8-frame count represented

Batch REPL tests:

- A client that adds only `ADE_AnimateDiffLoaderWithContext` and calls `done()` gets deterministic feedback and no applyable candidate.
- A client that completes the required edges can finish.

Live/agentic tests:

- HotShotXL image/img2img -> 8 or 16 frame video scenario.
- Assessment should inspect graph evidence, not rely on narrative:
  - has AnimateDiff loader
  - motion model output reaches sampler model input
  - active path includes 8/16 frame batch evidence
  - video terminal consumes decoded images

## Interaction With `origin/epic/god-file-splits/m2-agent-edit`

There is a remote overhaul branch:

```text
origin/epic/god-file-splits/m2-agent-edit
```

It is mostly a structural refactor of agent-edit and porting/edit internals.

It does not appear to solve the specific semantic-completion issue:

- Its `done()` guard still catches no-op and failed-statement cases, not successful disconnected sidecar edits.
- `queue_blocked_warning` remains applyable.
- It does not appear to introduce a research -> plan -> execute contract.

To minimize conflicts:

1. Implement the planner/evaluator as a standalone module.
2. Keep integration points small:
   - after research: build/attach plan
   - before execute prompt: format plan/status
   - before done acceptance: evaluate plan
3. Port the module into the overhaul branch later.

Avoid burying the core logic inside `edit_batch_loop_finish.py`, because that file is deleted/reorganized on the overhaul branch.

## Migration Strategy

### Phase 1: Deterministic Guard

Add a simple plan/evaluator for selected-precedent structural edits.

Focus on:

- Unconsumed added functional outputs.
- Required model-output-to-sampler path.
- Required video terminal for video requests.
- Required frame/batch count evidence for frame-count requests.

This alone would catch the HotShotXL failure.

This phase should add `plan_validate_ok` and block candidate/apply on critical failures.

### Phase 2: Structured Plan Artifact

Persist `execution_plan.json` in the turn artifacts.

Also persist `plan_evaluation.json`.

Include:

- selected precedent
- current graph roles
- required steps
- done conditions
- evaluation status

Also include baseline/candidate graph hashes and research/precedent IDs so stale plans can be detected after rebaseline or idempotent replay.

### Phase 3: Research Pattern Extraction

Improve research to emit role/edge/terminal patterns directly from workflow JSON.

Prefer parseable workflow JSON/compiled workflow evidence over prose-only hits.

### Phase 4: Execute Prompt Tightening

Make execute plan-obedient:

- No broad research.
- No alternative class invention.
- Exact planned schema hydration only.
- Plan status every turn.

Do not pass full research packets once an execution plan exists unless a planned step explicitly asks for additional evidence.

### Phase 5: Live Agentic Regression

Promote the HotShotXL scenario into recurring agentic coverage.

The pass condition must be graph-based:

- `ADE_AnimateDiffLoaderWithContext` exists.
- Its model output reaches sampler model input.
- 8/16 frame count is present in active path.
- `VHS_VideoCombine` or equivalent video terminal consumes decoded images.
- The old image-only terminal is not the sole terminal for a video request.

## Summary

The fix is not just better prompting.

The system needs a structured contract between precedent research and graph execution:

```text
Research gathers pattern evidence.
Plan converts evidence into required graph edits and invariants.
Execute implements only that contract.
Done/apply is blocked until the contract is satisfied.
```

That preserves speed for small edits, keeps research focused on precedent, and prevents the exact class of failure where the agent finds the right workflow but applies only disconnected pieces of it.
