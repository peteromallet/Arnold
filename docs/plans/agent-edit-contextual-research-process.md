# Agent Edit Contextual Research Process

## Problem

Recent failures around “save the generated video” exposed a process issue, not just a missing node lookup.

The current pipeline can classify a request as a simple local revise too early. Once that happens, the execute agent is nudged toward “add a node after the output” even when the right edit depends on workflow context, prior conversation, output conventions, or custom-node precedent.

That causes bad behavior:

- The execute agent guesses class names such as `ADE_CombineVideo` or `VHS_VideoCombine`.
- It searches local schema before understanding how working workflows usually solve the task.
- It can miss that the current graph is already invalid and should be repaired first.
- It treats the latest user sentence as isolated, instead of carrying durable context like “this is a Hotshot/AnimateDiff-style video workflow.”
- Tool output can overwhelm or truncate useful options, causing the model to see a distorted view of available choices.

The underlying engineering problem is a weak division of responsibility between classify, research, and execution.

## Desired Shape

The system should keep deterministic stages lightweight and let the execution LLM make the implementation judgment from evidence.

Classifier:

- Understand enough current workflow context to choose the process shape.
- Decide whether execution should include research.
- Avoid choosing concrete nodes, wiring, or implementation details.

Research:

- Gather relevant context and precedent options.
- Present multiple plausible patterns with sources and caveats.
- Avoid selecting the final path.

Execution:

- Inspect current graph state and validation issues.
- Use research packets and local schema/capability tools.
- Decide which precedent or local equivalent to apply.
- Repair graph validity before layering on the requested feature.

## Classifier Context

Classifier input should include a compact state sketch, not a full analysis bundle.

Example:

```text
Current graph:
- Node types: CheckpointLoaderSimple, LoadImage, VAEEncode, CLIPTextEncodeSDXL,
  ADE_AnimateDiffUniformContextOptions, ADE_AnimateDiffLoaderWithContext,
  KSamplerAdvanced, VAEDecode, PreviewImage
- Terminal outputs: VAEDecode.image -> PreviewImage.images (IMAGE)
- Known validation issues: KSamplerAdvanced has socket type mismatches
- Recent workflow context: user switched workflow toward Hotshot/AnimateDiff and 16 frames

User request:
Can you save the generated video
```

Classifier output should be process guidance:

```json
{
  "route": "revise",
  "research": true,
  "execution_protocol": "repair_graph_then_research_output_precedent_then_apply",
  "execution_notes": [
    "Current graph appears to be a Hotshot/AnimateDiff-style video workflow.",
    "Output/export behavior should be grounded in workflow precedent.",
    "Graph validation issues should be resolved before adding an output path."
  ]
}
```

It should not say:

- Use `CreateVideo`.
- Use `SaveVideo`.
- Use `VHS_VideoCombine`.
- Wire node A to node B.

Those are execution decisions.

## Research Output

Research should collect candidate context, not choose the implementation.

For a video save request, a useful research packet might look like:

```text
Goal: save generated video from current Hotshot/AnimateDiff-style graph.

Current graph facts:
- Terminal output: VAEDecode.image -> PreviewImage.images
- Output type: IMAGE batch
- Validation issues: KSamplerAdvanced inputs are socket-mismatched

Precedent options found:

1. AnimateDiff / VideoHelperSuite pattern
   - Pattern: VAEDecode.image -> VHS_VideoCombine.images
   - Output: video file directly
   - Nodes: VHS_VideoCombine
   - Source: workflow/example URL or internal workflow id
   - Local availability: not installed / schema absent

2. Core Comfy video pattern
   - Pattern: VAEDecode.image -> CreateVideo.images -> SaveVideo.video
   - Output: mp4
   - Nodes: CreateVideo, SaveVideo
   - Local availability: installed
   - Caveat: requires image batch frames

3. Animated image pattern
   - Pattern: VAEDecode.image -> SaveAnimatedWEBP.images
   - Output: animated webp
   - Nodes: SaveAnimatedWEBP
   - Local availability: installed
   - Caveat: not mp4

Execution constraints:
- Repair KSampler socket mismatches before adding output.
- Prefer installed nodes if they match the precedent’s socket-level role.
- Do not use ad hoc code unless no installed node path exists.
```

The execute agent then decides which option fits the user request, current graph, and local install.

## Execution Protocol

For workflow-dependent edits, the execute agent should follow this order:

1. Inspect graph validity.
2. Identify terminal outputs and socket types.
3. If graph wiring is invalid, repair or explicitly account for it first.
4. Search internal workflow precedents for how similar workflows perform the requested capability.
5. Search external workflow examples if internal precedent is missing or weak.
6. Verify exact node signatures locally.
7. If exact precedent nodes are absent, search for local capability-equivalent paths by socket role.
8. Apply the smallest graph edit that satisfies the request.
9. Reject or retry candidates that leave validation issues unresolved.

For the example request, the agent should reason:

```text
The current graph outputs an IMAGE batch, but the user asked to save a video.
Existing workflow precedents commonly use IMAGE batch -> video combine/save.
The graph has KSampler socket mismatches, so first repair KSampler wiring.
Then add a save path using installed nodes that match the precedent’s socket role.
```

## Tooling Implications

Avoid deterministic name matching as a decision mechanism.

Bad:

- Rank local nodes higher because their names contain `video`, `save`, or `webp`.
- Infer the right node from a hard-coded list.

Better:

- Provide complete, compact class-name indexes for compatibility searches.
- Provide exact signatures after the model chooses a candidate class.
- Provide workflow precedent packets with multiple options and caveats.
- Provide graph capability facts:
  - terminal nodes
  - terminal output socket types
  - current validation issues
  - installed local classes
  - missing exact precedent classes

The model should make the judgment call from this evidence.

## Why This Matters

This keeps the system agentic without making it blind.

Deterministic stages should supply state, evidence, and constraints. They should not quietly pick an implementation. The LLM should decide how to satisfy the user’s request, but it needs the right context:

- what the graph is
- what the graph currently produces
- what is broken
- how similar workflows solve the task
- what local nodes can actually do

That is the process improvement: move from one-turn “classify then edit” to context-aware “triage process, gather precedent, execute with judgment.”
