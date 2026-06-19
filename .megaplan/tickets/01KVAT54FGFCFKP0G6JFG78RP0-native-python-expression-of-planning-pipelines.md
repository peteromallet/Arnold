---
id: 01KVAT54FGFCFKP0G6JFG78RP0
title: Native Python expression of planning pipelines
tags: [refactor, architecture, native-pipeline]
status: open
source: human
codebase_id: null
created_at: 2026-06-16T18:30:00Z
epics: []
---

# Native Python expression of planning pipelines

## Problem / observation

The Megaplan planning pipeline (and smaller pipelines like `vibecomfy-executor`) are currently expressed as framework graphs: `PipelineBuilder`, `Stage`, `Edge`, typed ports, `StepResult`, `StepContext`, and a legacy Megaplan executor conversion layer. This adds significant boilerplate and obscures the actual control flow, which for many pipelines is just sequential/conditional Python logic.

For `vibecomfy-executor` the graph is mostly overhead: the interesting routing (`classify → maybe research → maybe implement → reply`) already lives inside the steps as ad-hoc `if` branches. For the main Megaplan pipeline the graph is carrying real runtime responsibilities (typed contracts, decision routing, overrides, subloops, artifact/state wrapping, observability), but the *expression* of that graph is still noisy and hard to read.

## Proposal

Move to a native-Python authoring layer with the same Megaplan runtime features built on top:

- Write pipelines as ordinary Python functions with explicit `if` / `while` / `try` control flow.
- Declare stage contracts with lightweight decorators (`@phase`, `@decision`, `@pipeline`) that capture `consumes` / `produces` / `branches` metadata.
- Provide a runtime engine that:
  - executes the Python function,
  - checkpoints at every phase boundary for pause/resume,
  - validates typed handoffs,
  - derives a navigable graph from decorators + AST for observability,
  - injects overrides before decision phases,
  - runs subloops as nested `@pipeline` calls,
  - persists artifacts and state just like the current executor.

This separates *what the pipeline does* (plain Python) from *the runtime guarantees* (contract checking, tracing, resumability, overrides).

## High-level migration path

1. **Factor handlers into pure phase functions** (`handle_plan`, `handle_critique`, etc. already exist; keep them, but expose them through `@phase`).
2. **Introduce a `PhaseContext`** carrying `plan_dir`, `profile`, `iteration`, `state`, and typed payloads — replacing the untyped `ctx.state` dict.
3. **Rewrite `build_pipeline()` as a native `@pipeline` function** that calls `yield from run_phase(...)` and uses ordinary `while` loops for the critique/gate/revise cycle and tiebreaker subloop.
4. **Build the runtime engine** (`run_phase`, `run_subloop`, checkpoint serialization, override injection, graph introspection) as a thin layer underneath.
5. **Keep the existing CLI working** via a one-line adapter that runs the native pipeline function inside the current `arnold run` path, writing the same `state.json` / artifacts.
6. **Pilot on `vibecomfy-executor` first** because it is small and the native shape is already clearly better; then apply the same pattern to the main Megaplan planning pipeline.

## Why now

- The neutral `PipelineBuilder` already exists but still has to be converted back to Megaplan types (`_to_megaplan_pipeline`) because the CLI executor expects them.
- Codex and an internal coder subagent both recommended the native shape for `vibecomfy-executor`, while agreeing Megaplan itself still needs the graph-level guarantees.
- A native expression layer with decorator-driven contracts gives us the readability benefits both models flagged without giving up the runtime/observability features the production graph provides.

## Acceptance criteria (rough)

- A native `@pipeline` function can express the full Megaplan planning flow (`prep → plan → critique → gate → [revise loop | tiebreaker | escalate] → finalize → execute → review`).
- The runtime can pause after any phase and resume from serialized state.
- Existing overrides, decision vocabularies, fallback edges, and subloop promotion continue to work.
- Existing handlers and artifacts are reused unchanged.
- Graph introspection produces an equivalent stage/edge view for observability tools.
