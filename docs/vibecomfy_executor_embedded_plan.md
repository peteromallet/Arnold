# Embedded VibeComfy Executor — Implementation Plan

## Goal

Ship a natural-language agent executor that runs **inside the VibeComfy/ComfyUI app**, takes a user query and an optional workflow graph, optionally researches, optionally edits the graph, and returns a final reply with any proposed graph changes.

The executor must support the existing model profiles:

- `default` — DeepSeek via Hermes
- `openai` — OpenAI Codex
- `anthropic` — Anthropic Claude (Shannon adapter)
- `opensource` — OpenRouter/Hermes models

## Strategic decision

Put the orchestration in VibeComfy as plain Python. Use Arnold as a backend library for **agent dispatch, profile loading, spec parsing, and model conventions**. Do **not** make a new Arnold runtime or neutral-graph executor a prerequisite.

This is the fastest path to a working embedded feature. A reusable Arnold runtime can be extracted later once the shape is proven.

## Current seams we reuse

- `vibecomfy/comfy_nodes/agent/provider.py` — VibeComfy's provider seam: `run_agent_turn`, `run_agent_turn_batch`, `run_agent_turn_delta`.
- `vibecomfy/comfy_nodes/agent/runtime.py` — Arnold/Hermes runtime adapter; maps panel routes to Arnold agent ids.
- `vibecomfy/comfy_nodes/agent/worker.py` — Subprocess worker that isolates Arnold/AIAgent imports from ComfyUI.
- `vibecomfy/comfy_nodes/agent/edit.py` — `handle_agent_edit`, the existing graph-editing engine.
- `vibecomfy/comfy_nodes/agent/routes.py` — Existing HTTP routes; we add one new route here.
- `vibecomfy/comfy_nodes/agent/contracts.py` — Existing response envelopes; we reuse them.
- `arnold/pipeline/profiles.py` — Neutral profile loader and `parse_agent_spec_shape`.
- `arnold/pipelines/vibecomfy_executor/profiles/*.toml` — Existing profile TOMLs with per-phase specs.

## Architecture

```
┌─────────────────────────────────────┐
│  VibeComfy/ComfyUI app process      │
│  ┌─────────────────────────────┐    │
│  │  vibecomfy/executor/core.py │    │  ← plain Python orchestration
│  │  classify → research →      │    │
│  │  implement → reply          │    │
│  └─────────────────────────────┘    │
│              │                      │
│  ┌───────────┴───────────────┐      │
│  │  agent_backend.py         │      │  ← calls provider.py with resolved tuples
│  │  profiles.py              │      │  ← thin wrapper around arnold.pipeline.profiles
│  │  research.py              │      │  ← Hivemind search
│  └───────────────────────────┘      │
│              │                      │
│  ┌───────────┴───────────────┐      │
│  │  vibecomfy/comfy_nodes/   │      │
│  │  agent/provider.py        │      │
│  └───────────────────────────┘      │
│              │                      │
│              ▼ subprocess spawn     │
├─────────────────────────────────────┤
│  worker.py subprocess               │
│  Arnold agent dispatch              │
│  (hermes / codex / claude / shannon)│
└─────────────────────────────────────┘
```

## File layout

```
vibecomfy/executor/
├── __init__.py
├── core.py              # run_executor() orchestration
├── profiles.py          # thin wrapper around arnold.pipeline.profiles
├── agent_backend.py     # calls into provider.py with resolved (agent, model, effort)
├── research.py          # Hivemind search adapter
├── contracts.py         # executor-internal dataclasses (Plan, ExecutorResult)
└── prompts.py           # per-phase prompt templates
```

## Phase flow

```python
def run_executor(query, graph=None, profile="default", session_id=None):
    ctx = ExecutorContext(
        profile=load_profile(profile),
        session_id=session_id,
    )

    plan = classify(ctx, query, graph)

    research_summary = None
    if plan.needs_research:
        research_summary = research(ctx, query, plan, graph)

    edited_graph = None
    implementation = None
    if plan.needs_edit:
        implementation = implement(ctx, query, plan, research_summary, graph)
        edited_graph = handle_agent_edit(graph, implementation, session_id=session_id)

    reply_text = reply(ctx, query, plan, research_summary, implementation, edited_graph)

    return ExecutorResult(
        message=reply_text,
        graph=edited_graph,
        plan=plan,
        research_summary=research_summary,
        implementation=implementation,
    )
```

## Implementation steps

### Step 1 — Bootstrap `vibecomfy/executor/`

Create the package with `contracts.py`, `prompts.py`, and stub implementations.

### Step 2 — Profile loader (reuse Arnold)

`vibecomfy/executor/profiles.py` is a thin wrapper around `arnold.pipeline.profiles`:

```python
from arnold.pipeline.profiles import load_profiles, parse_agent_spec_shape

_PROFILE_DIR = Path(__file__).parents[2] / ".." / "megaplan" / "arnold" / "pipelines" / "vibecomfy_executor" / "profiles"
_DECLARED_STAGES = frozenset({"classify", "research", "implement", "reply"})
_KNOWN_AGENTS = frozenset({"hermes", "codex", "claude", "shannon"})

def load_profile(name: str) -> dict[str, AgentSpecShape]:
    profiles = load_profiles(
        built_in_paths=_PROFILE_DIR.glob("*.toml"),
        declared_stage_keys=_DECLARED_STAGES,
        known_agents=_KNOWN_AGENTS,
    )
    stage_map = profiles[name]
    return {stage: parse_agent_spec_shape(spec, known_agents=_KNOWN_AGENTS) for stage, spec in stage_map.items()}
```

Arnold owns the parser and TOML mechanics. VibeComfy only declares its stage names and known agents.

### Step 3 — Agent backend shim

`vibecomfy/executor/agent_backend.py` exposes:

```python
def run_phase(
    phase: str,
    prompt: str,
    system: str | None,
    ctx: ExecutorContext,
) -> str:
    spec = ctx.profile[phase]  # already resolved to AgentSpecShape
    # Map spec.agent to the route/model/effort expected by provider.py
    return dispatch_to_provider(prompt, system, agent=spec.agent, model=spec.model, effort=spec.effort)
```

This keeps all transport, retries, and audit metadata inside `provider.py`.

### Step 4 — Classify, research, implement, reply

Implement each phase in `core.py`:

- **Classify** — LLM call that returns a `Plan` JSON object: `needs_research`, `needs_edit`, `intent`, `notes`.
- **Research** — direct Hivemind search; summarize results.
- **Implement** — LLM call that produces an edit request compatible with `handle_agent_edit`.
- **Reply** — LLM call that synthesizes the final user-facing message.

### Step 5 — Graph editing

The implement phase returns the same shape `handle_agent_edit` already accepts. Do not duplicate edit logic.

### Step 6 — HTTP route

Add to `vibecomfy/comfy_nodes/agent/routes.py`:

```python
@routes.post("/vibecomfy/agent-executor")
async def agent_executor(request):
    body = await request.json()
    result = run_executor(
        query=body["query"],
        graph=body.get("graph"),
        profile=body.get("profile", "default"),
        session_id=body.get("session_id"),
    )
    return web.json_response(result.to_envelope())
```

### Step 7 — Response contract

Return the existing `success_envelope` from `vibecomfy/comfy_nodes/agent/contracts.py`. Put executor metadata (`plan`, `research_summary`, `implementation`) inside the existing `debug` object.

### Step 8 — Readiness and error handling

Reuse existing provider readiness checks. Return honest `AGENT_RUNTIME_UNAVAILABLE` errors when the chosen route is not ready.

### Step 9 — Tests

- Unit tests for profile parsing and phase routing.
- Smoke tests for each profile:
  - respond-only query
  - research-only query
  - simple graph edit
  - graph describe without edit
- Characterization tests for graph outputs.

### Step 10 — Deprecate or redirect the old direct path

Once the executor route is stable, make the existing `/vibecomfy/agent-edit` route a special case of the executor (edit-only plan) or keep it as a low-level primitive.

## Response contract

Use the existing `success_envelope`. Executor-specific metadata lives in `debug`:

```json
{
  "ok": true,
  "message": "...",
  "graph": { ... },
  "outcome": { "kind": "candidate" },
  "debug": {
    "plan": { "needs_research": false, "needs_edit": true, "intent": "..." },
    "research_summary": "...",
    "implementation": "..."
  }
}
```

## Rollout

1. Merge `vibecomfy/executor/` behind the new route.
2. Keep the existing `handle_agent_edit` path untouched.
3. Run smoke matrix across all four profiles.
4. Switch the UI panel from direct `agent-edit` to `agent-executor` behind a feature flag.
5. Remove the flag once parity is proven.

## Reusable Arnold parts we lean on now

| Arnold component | What VibeComfy uses it for |
|---|---|
| `arnold.pipeline.profiles.load_profiles` | Load profile TOMLs |
| `arnold.pipeline.profiles.parse_agent_spec_shape` | Resolve `hermes:deepseek:...` to `{agent, model, effort}` |
| `arnold.agent.dispatch` | Dispatch codex/claude/shannon/hermes requests |
| Arnold adapter registrations | hermes, codex, claude, shannon already wired |
| Profile TOML conventions | `[profiles.default]` with per-phase specs |

## 10 load-bearing questions and predicted answers

### 1. Should the executor orchestration live in VibeComfy or in Arnold?

**Predicted answer:** In VibeComfy.

The orchestration is product-specific: it calls `handle_agent_edit`, shapes Hivemind queries for ComfyUI workflows, and returns VibeComfy UI contracts. Arnold should own reusable building blocks (dispatch, profiles), not this particular flow.

### 2. Should the orchestration run in-process or out-of-process relative to ComfyUI?

**Predicted answer:** In-process orchestration, out-of-process model turns.

Graph editing needs the live in-process schema provider and session/audit machinery. Model backends are unsafe to import in-process due to known collisions. The existing worker already solves the model-turn isolation problem.

### 3. Should we reuse `handle_agent_edit` or rebuild graph editing?

**Predicted answer:** Reuse `handle_agent_edit`.

It already exists, is tested, handles batch/delta contracts, and integrates with session/audit. Rebuilding it would duplicate months of work and risk regressions.

### 4. How should profile/model selection work?

**Predicted answer:** Arnold owns profile loading and spec parsing; VibeComfy calls `arnold.pipeline.profiles` and passes resolved `{agent, model, effort}` tuples to its provider seam.

Profile TOMLs are shared config. Spec resolution belongs in Arnold because it knows about agent families and model shapes. VibeComfy's provider layer should handle only transport.

### 5. What is the right phase structure?

**Predicted answer:** classify → research (optional) → implement (optional) → reply.

This matches the existing pipeline and the natural decomposition of the task: decide what to do, gather context, act, explain.

### 6. How should research work?

**Predicted answer:** Two-tier deterministic search first (local corpus → Hivemind), agentic research optional later.

Direct search is deterministic, fast, and sufficient for most ComfyUI workflow questions. Agentic research can be added as a phase variant once the baseline works.

### 7. What should the response contract to the UI be?

**Predicted answer:** Reuse the existing `success_envelope` from `vibecomfy/comfy_nodes/agent/contracts.py`. Put executor metadata inside the existing `debug` object.

The UI already parses this envelope. New top-level fields would force defensive UI changes.

### 8. How do we keep Arnold imports safe inside ComfyUI?

**Predicted answer:** Never import Arnold agent backends in the ComfyUI process.

Only import lightweight Arnold utilities like `arnold.pipeline.profiles`. All model calls go through the existing subprocess worker, which isolates `AIAgent` and dispatch imports.

### 9. What is the minimum viable milestone?

**Predicted answer:** One new `run_executor()` function plus one new HTTP route, wired to `handle_agent_edit` and reusing existing provider/profile machinery.

That is the smallest unit that actually runs inside the app end-to-end. Split into multiple files only when the single file grows enough to justify it.

### 10. When should we extract a reusable runtime into Arnold?

**Predicted answer:** Only after the VibeComfy executor is proven and a second app (or second workflow) wants the same plain-Python phase runner.

Premature extraction makes Arnold architecture the blocking path. Extraction after proof means the runtime is built from working code, not speculation.
