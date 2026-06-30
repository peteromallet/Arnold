# Mission: native-Python pipelines

## Fundamental goal

Pipelines are programs that orchestrate LLM/agent calls, human decisions, and tool invocations to produce structured outputs. We want to express these programs as **ordinary Python functions** because Python is our native language, and functions are the most composable, readable, and testable units we have.

A pipeline should read like any other Python module:

- imports at the top,
- helper functions defined above,
- a top-level function that wires them together with ordinary variables, `if`, `while`, and function calls.

The runtime — checkpointing, resume, typed handoffs, override injection, subloops, event journaling, observability — should be an **invisible substrate**. Authors should not have to think about graphs, stages, edges, or cursors while writing pipeline logic.

Graph introspection (`arnold pipelines check`, dashboards, capsules) should be a **derived view** of the running system, not the source of truth. If a static graph cannot be derived from a particular pipeline, that is a tooling limitation, not a programming limitation.

## Properties we want

1. **Readability.** A new reader can open a pipeline file and understand the control flow in one pass, top to bottom.
2. **Composability.** Phases are ordinary Python functions. They can be imported, reused, tested, wrapped, and composed with standard Python patterns.
3. **Familiar tooling.** Pipelines should work with type checkers, linters, debuggers, and unit tests without special plugins.
4. **Runtime transparency.** Persistence, resume, contracts, and observability happen automatically; the author writes pure domain logic.
5. **Evolvability.** Adding a branch, a loop, a new phase, or a subloop should be as easy as editing a Python function.

## What we are not optimizing for

- Graph aesthetics. The graph is a view, not the program.
- Static derivability at the expense of expressiveness. If a dynamic branch can only be understood at runtime, that is acceptable.
- Minimal runtime cost. Readability and maintainability come first; performance optimizations are secondary.

## Open architectural question

Given this mission, the central question is:

> Should the native Python function compile to the existing graph executor (authoring sugar), or should the runtime execute the Python function directly and derive the graph as a side effect (native runtime)?

The answer determines whether "native Python" is a syntax layer or a first-class execution model.
