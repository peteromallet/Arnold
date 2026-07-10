# Agent Edit Grounded Implementation Plan

This plan consolidates three DeepSeek subagent audits of the current VibeComfy agent-edit path:

- classify/research/execute flow
- graph/schema/search tooling
- workflow-precedent research

The goal is to make the agent-edit process genuinely context-aware without replacing LLM judgment with deterministic node-name heuristics.

## Target Architecture

Deterministic code should provide facts, constraints, and context. It should not choose the implementation.

The intended split is:

- Classifier chooses the process shape.
- Research gathers multiple workflow precedents and local availability facts.
- Execute agent decides the concrete graph edit.
- Validation accepts or rejects the candidate based on graph correctness.

For a request like "save the generated video" on a Hotshot/AnimateDiff-style graph, the system should:

1. Notice the graph's terminal output and validation state.
2. Route to an implementation path that includes research.
3. Search workflow precedents before guessing node names.
4. Present multiple viable patterns and local availability facts.
5. Let the execute agent choose and apply the smallest valid edit.

## Current State

There are two connected pipelines.

`vibecomfy/executor/core.py` runs the outer executor flow:

- classify
- optional research
- implement/reply

The current classifier produces `ClassifyDecision` with route-level fields such as route, intent, task, research, implement, model families, pattern category, and research goal. It does not currently carry an explicit "execution protocol" or structured execution notes.

`vibecomfy/comfy_nodes/agent/edit.py` runs the browser agent-edit flow:

- ingest graph/request
- collect revision evidence
- build batch REPL prompt
- run model turns
- validate candidate diff
- apply or reject

`_stage_revision_evidence()` already collects important facts through `collect_topology_evidence()` and readiness checks. Recent changes add socket mismatch detection. Those facts are still not cleanly surfaced as a compact "current graph facts" block to both classify and execute.

Research already exists in `vibecomfy/executor/research.py` and is more capable than the failing behavior implied:

- local workflow corpus search
- Hivemind/community search
- web search
- GitHub/workflow JSON fetching
- Comfy Registry missing-node resolution

Inline `research(...)` from the batch REPL is resolved in `vibecomfy/porting/edit/_resolve.py`. It returns text and some detail fields, but not a structured multi-option workflow precedent packet.

## Problems To Fix

### 1. Classifier Has Too Little Graph Context

The classifier gets a compact graph summary and reference map, but not enough operational facts:

- terminal node/output socket types
- whether the graph currently ends in IMAGE, LATENT, VIDEO, etc.
- socket mismatches
- missing node packs/custom nodes
- recent workflow context from prior turns

That makes it too likely to classify a workflow-dependent request as a simple revise.

### 2. Research Is Not Reliably Prefetched For Implementation

The outer executor can prefetch research, and the batch agent can call `research(...)` inline, but the process does not guarantee workflow-precedent research for implementation requests that need it.

The weak behavior is:

- classify as revise
- hand off to execution
- execution guesses likely class names
- only then searches local schema or registry

The desired behavior is:

- classify as implementation with research needed
- gather workflow precedents/options
- execution decides from those options and local facts

### 3. Research Results Are Flat Text, Not Options

`research.py` already has `WorkflowSlice`, `InspectionSummary`, and `PrecedentAdaptationPlan` concepts. However, the adaptation flow currently tends to use the first slice, and inline research returns a merged text summary rather than a structured list of options.

The execute agent needs a compact packet like:

- Option A: workflow pattern, source, local nodes present/missing, caveats
- Option B: workflow pattern, source, local nodes present/missing, caveats
- Option C: local socket-equivalent fallback, source, caveats

It should not receive "use this node."

### 4. Tool Output Can Hide Useful Choices

Compatibility search must expose complete but compact facts. If output is truncated or dominated by detailed signatures, the model can miss locally installed options.

Good deterministic behavior:

- socket-type filters
- exact schema signatures
- compact class-name indexes
- terminal output facts
- candidate chain facts

Bad deterministic behavior:

- hard-coded node preference
- name-token ranking
- one-off Hotshot/AnimateDiff rules
- sorting that makes one implementation appear selected

### 5. Some Deterministic Gates Still Depend On Task Text

The pipeline still has places where task text is interpreted deterministically to decide process shape or safety exceptions. The subagent audit specifically flagged functions such as `_runtime_code_additive_request()` and `_can_attempt_local_additive_revise()` in `comfy_nodes/agent/edit.py`.

Those should be simplified so classifier/executor model judgment drives process, while deterministic code only enforces graph validity and safety.

## Implementation Plan

### Phase 1: Add Structured Graph Facts

Add a compact graph-facts object/string derived from existing revision evidence.

Files:

- `vibecomfy/executor/contracts.py`
- `vibecomfy/executor/revision_evidence.py`
- `vibecomfy/executor/prompts.py`
- `vibecomfy/executor/core.py`
- `vibecomfy/comfy_nodes/agent/provider.py`
- `vibecomfy/comfy_nodes/agent/edit.py`

Changes:

- Extend topology facts with terminal output summaries:
  - node id
  - class type
  - output socket name
  - output socket type
- Include socket mismatch summaries.
- Include missing node/custom-node readiness findings when available.
- Pass the compact graph facts into classifier prompts.
- Pass the same compact graph facts into turn-0 batch REPL prompts.

Classifier prompt rule:

> Choose process shape only. Do not name concrete nodes, class types, or wiring for the implementer.

Execution prompt rule:

> Use graph facts, workflow precedent, local schemas, and validation results to decide the implementation.

### Phase 2: Extend The Classifier Contract

Files:

- `vibecomfy/executor/contracts.py`
- `vibecomfy/executor/prompts.py`
- `vibecomfy/executor/core.py`
- tests around classify parsing/serialization

Add fields to `ClassifyDecision`:

- `execution_protocol: str = ""`
- `execution_notes: tuple[str, ...] = ()`

These fields guide process, not implementation.

Example:

```json
{
  "route": "revise",
  "research": true,
  "implement": true,
  "execution_protocol": "repair_graph_then_research_workflow_precedent_then_apply",
  "execution_notes": [
    "Current graph appears to be a video-generation workflow.",
    "Graph terminal output is IMAGE.",
    "User request depends on output/export precedent.",
    "Do not choose concrete nodes during classification."
  ]
}
```

### Phase 3: Prefetch Research For Implementation When Needed

Files:

- `vibecomfy/executor/core.py`
- `vibecomfy/executor/research.py`
- `vibecomfy/comfy_nodes/agent/edit.py`

Change the research gate so implementation routes can receive prefetched research when classifier says research is needed.

Current problem:

- Research prefetch is tied too narrowly to pure research/adapt flows.

Required behavior:

- If `ClassifyDecision.research == true` and `implement == true`, gather research context before implementation.
- Pass `research_summary`, sources, warnings, and precedent packets to the agent-edit state.
- Keep inline `research(...)` available for follow-up research inside execution.

This avoids forcing the execute agent to discover from scratch that it should search workflows first.

### Phase 4: Build Workflow Precedent Packets

Files:

- `vibecomfy/executor/contracts.py`
- `vibecomfy/executor/research.py`
- `vibecomfy/porting/edit/_resolve.py`
- `vibecomfy/comfy_nodes/agent/edit.py`
- `vibecomfy/comfy_nodes/agent/provider.py`

Add contracts:

- `PrecedentOption`
- `PrecedentPacket`

Recommended fields:

- source title/url/id
- source quality: runnable workflow, partial workflow, registry lead, web lead, community lead
- pattern summary
- relevant node class types
- terminal output behavior
- local availability:
  - installed exact classes
  - missing classes
  - registry-resolvable classes/packs
- socket-level role:
  - consumes IMAGE, produces VIDEO, terminal sink, etc.
- caveats
- optional adaptation plan

Important: do not include a deterministic "winner" field.

Ordering should be neutral and explainable:

- source quality grouping
- stable source order
- alphabetical within equal groups

The packet can show factual indicators such as "all classes installed" or "missing 3 classes," but execution chooses how to use that evidence.

### Phase 5: Make Inline Research Return Structured Options

Files:

- `vibecomfy/porting/edit/_resolve.py`
- `vibecomfy/comfy_nodes/agent/edit.py`

When the batch agent calls `research("...", sources=["workflows"])`, the statement result should include:

- formatted multi-option text in `query_output`
- structured `precedent_packet` in `StatementResult.detail`
- workflow schema candidates
- resolver/registry candidates
- research source metadata

Then `_batch_research_memory_summary()` should carry compact precedent options across later turns so the agent does not re-search unnecessarily.

### Phase 6: Improve Search Tooling Without Name Ranking

Files:

- `vibecomfy/porting/edit/_describe.py`
- `vibecomfy/porting/emitter.py`
- `vibecomfy/porting/emit/emitter.py`
- `vibecomfy/schema/provider.py`
- `vibecomfy/porting/emit_constants.py`

Required behavior:

- Compatibility search should filter by socket type.
- Search output should include a compact class-name index before detailed signatures.
- Terminal/output capability should be displayed as facts.
- Multi-hop search can be added for cases like `IMAGE -> VIDEO -> terminal sink`.

Avoid:

- name-token rankers
- "preferred" local node lists
- prompt examples that say "use CreateVideo -> SaveVideo" as a preference

Better wording:

> Search for installed nodes by socket compatibility and terminal role. If exact precedent nodes are absent, compare local socket-equivalent paths and choose one in execution.

### Phase 7: Remove Or Neutralize Deterministic Task-Text Heuristics

Files:

- `vibecomfy/comfy_nodes/agent/edit.py`
- related tests

Review and simplify:

- `_runtime_code_additive_request()`
- `_can_attempt_local_additive_revise()`
- any task-text string matching used to bypass normal process

Keep deterministic gates only for:

- graph missing/unavailable
- candidate validation failure
- unresolved unsafe topology in the candidate
- unsupported operation class

Do not keep deterministic gates for:

- deciding "this sounds like a video save request"
- deciding "this should use code"
- deciding "this should use a particular node family"

Those belong to classifier/executor model judgment with graph facts.

## Test Plan

### Unit/Contract Tests

Add or update:

- `ClassifyDecision` serialization with `execution_protocol` and `execution_notes`
- graph facts formatting from topology evidence
- terminal output summary extraction
- socket mismatch summary extraction
- `PrecedentPacket` and `PrecedentOption` serialization

### Search/Schema Tests

Add or update:

- compatibility search filters by socket type
- compatibility search uses neutral/alphabetical/stable ordering
- compatibility search index includes all compatible classes before detailed signatures
- no test expects video/save name ranking
- terminal capability is displayed as a fact, not used as a hard-coded preference

### Research Tests

Add:

- research result with multiple workflow sources becomes a multi-option precedent packet
- inline `research(...)` includes `precedent_packet` in statement details
- research memory carries prior precedent options across batch turns
- registry candidates are attached to missing node facts, not presented as implementation decisions

### Executor/Agent Tests

Add:

- implementation route with `research=true` receives prefetched research
- classifier prompt includes graph facts but not concrete node recommendations
- batch prompt includes graph facts and precedent packet
- rejected candidate retry receives validation facts, not hard-coded node advice

### Agentic Harness Test

Create an end-to-end agentic test for:

> Switch workflow to Hotshot/AnimateDiff-style generation, generate 16 frames, then save the generated video.

Expected evidence:

- actual agent runs through normal pipeline
- classifier sees graph facts
- research happens before implementation or is explicitly called by execution
- workflow precedent options are present
- execution picks an installed/local-compatible path
- graph candidate validates
- no deterministic name-ranker is required for success

## Merge Order

1. Graph facts extraction and prompt injection.
2. Classifier contract extension.
3. Research prefetch for implementation routes.
4. Precedent packet contracts and formatting.
5. Inline research packet plumbing and memory carry-over.
6. Search output improvements without name ranking.
7. Removal of remaining task-text heuristic bypasses.
8. Structural and live agentic harness coverage.

This order keeps each merge reviewable and avoids making the full behavior depend on an untested end-to-end rewrite.

## Decisions

### Do Not Add Deterministic Winner Selection

The subagent audit proposed compatibility scores in one place. That should be adjusted before implementation.

Use factual indicators instead:

- exact nodes installed: yes/no
- missing nodes count/list
- registry package found: yes/no
- source is runnable JSON: yes/no
- terminal/socket role: facts

The execute agent can compare those facts and explain its choice.

### Do Not Overload Classification

Classifier should see enough to choose process, not enough to design the graph edit. The classifier prompt should explicitly prohibit concrete node/wiring recommendations.

### Preserve Validation As The Final Deterministic Gate

The LLM chooses. Deterministic validation decides whether the candidate is safe to apply.

That is the correct boundary.
