# Agent Edit Validation Boundaries

## Purpose

This note describes what the agent-edit execution path validates today, what it
does not validate, and what extra checks are needed for precedent-driven
workflow edits.

## Product Path

The browser-facing product path currently uses the `batch_repl` contract:

```text
ingest_v2 -> agent_batch
```

The implementation lives in `vibecomfy/comfy_nodes/agent/edit.py`.

In this path, the model edits through `EditSession` batches and then calls
`done()`. The edit session is responsible for applying edits, rejecting invalid
statements, and validating the final candidate before the response is returned.

## Existing Structural Validation

The product path validates several important properties:

1. **Submit state is current**

   `ingest_v2` checks that the submitted graph still matches the backend
   baseline. If it does not, the turn fails with stale-state diagnostics.

2. **Edit statements must land**

   The batch loop tracks landed operations, failed operations, and query-only
   turns. It refuses premature `done()` when a search or failed edit produced no
   graph change.

3. **Candidate replay must be deterministic**

   The edit gates replay landed operations over the original graph. The
   recomputed candidate must match the session's working UI.

4. **Touched API regions must compile and compare**

   The edit gates compile the working UI and recomputed candidate to API form
   and compare the touched region for parity.

5. **Queue/apply eligibility is derived from gates**

   The response includes apply eligibility and queue blockers. Some candidates
   may be inspectable/applyable while queue remains blocked due to schema or
   confidence limits.

## Full Development Path

The older/full path is more explicit:

```text
ingest -> convert -> agent -> load_python -> lower -> validate -> emit -> summarize
```

Important validation stages:

- `load_python`: loads generated Python through the restricted generated-source
  loader.
- `lower`: lowers intent/helper constructs to a static graph.
- `validate`: calls workflow validation, schema validation when available, API
  link-shape validation, and helper diagnostics.
- `emit`: emits UI JSON and checks layout/fidelity constraints.
- `summarize`: computes queue blockers and response eligibility.

## What This Validation Proves

The current validation is strong for structural correctness:

- the graph can be represented as VibeComfy IR;
- generated/edit Python can be loaded under the expected loader;
- obvious schema and link-shape problems are caught;
- helper/lowering failures block the candidate;
- the UI candidate does not silently destroy unrelated editor state;
- apply/queue state is explicit.

## What It Does Not Prove

The current validation does not fully prove semantic task success.

It does not guarantee:

- the graph was actually run in ComfyUI;
- the graph will produce a good image/video/audio result;
- the edit matches the user's intent;
- a model-family-specific request used the right custom-node idiom;
- a precedent research result was actually followed;
- a newly added node is useful rather than merely present.

Example: a user asks to add an LTX custom-audio lipsync input. Structural
validation can prove that a candidate graph compiles and has legal links. It
does not, by itself, prove that the graph used the LTX/RuneXX custom-audio
pattern rather than an unattached generic audio loader.

## Needed Semantic Gate

Precedent-driven edits need an additional advisory semantic check after the
candidate is built.

Suggested output:

```json
{
  "task_satisfaction": {
    "ok": true,
    "checks": [
      {
        "code": "audio_input_present",
        "ok": true,
        "evidence": ["LoadAudio"]
      },
      {
        "code": "ltx_audio_pattern_present",
        "ok": true,
        "evidence": ["LTXVAudioVAEEncode", "RuneXXCustomAudioLipsync"]
      }
    ]
  }
}
```

Possible checks:

- user asked for audio input -> candidate contains an audio public input or
  audio loader;
- user asked for lipsync/custom audio -> candidate contains known audio encode
  or lipsync/custom-audio nodes;
- user asked for video edit -> candidate still contains a video output path;
- user asked for model-family-specific change -> candidate includes the
  relevant model family or custom-node pack;
- research found a precedent -> candidate contains at least one relevant
  pattern from that precedent.

Severity policy:

- hard structural failures should continue to block candidates;
- high-confidence semantic misses should force another agent turn or block the
  candidate;
- low-confidence semantic misses should appear as warnings in the report.

## Relationship To Runtime Validation

Runtime validation is separate. Queueing the workflow in ComfyUI or RunPod would
catch model availability, runtime-only custom-node errors, and output-shape
issues, but it is slower and may require GPU resources.

Recommended layers:

1. Structural validation: always required before candidate response.
2. Semantic task-satisfaction validation: required for complex precedent-driven
   edits.
3. Runtime smoke validation: optional or explicit, especially before promoting a
   workflow to a ready template.

