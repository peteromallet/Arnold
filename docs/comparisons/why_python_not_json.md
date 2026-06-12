# Why Python, Not JSON?

VibeComfy uses Python as the authoring surface because agents are much better at
working with Python than with raw ComfyUI workflow JSON.

JSON is a good interchange format. It is stable, explicit, easy to serialize,
and it is the shape ComfyUI ultimately needs at queue time. But JSON is a poor
thinking surface for agents. It gives them nested data, ids, links, widget
positions, and class names, but very little of the semantic scaffolding that
helps them reason about what the workflow is trying to do.

Python gives the model a native working language.

LLMs have seen enormous amounts of Python: examples, explanations, debugging
threads, tutorials, refactors, tests, APIs, scripts, and long chains of
reasoning about code. They have also seen JSON, but usually as data to consume
or emit, not as the main place where a program is understood, modified, and
validated. ComfyUI's JSON is even more specialized: graph ids, link arrays,
widgets, node-specific conventions, editor furniture, and custom-node quirks all
matter at once.

That makes direct JSON editing an uphill fight. You can add helpers, schema
summaries, comments outside the JSON, or custom views over the graph, but you are
still asking the agent to work in a format that is less natural for reasoning.
Python starts with a huge advantage: it is already the most common programming
language in the world, and agents already know how to read and change ordinary
Python code.

## What Python Buys

- **Better comprehension.** Named variables, functions, kwargs, imports, and
  metadata declarations give the agent handles for intent, not just graph ids.
- **Lower reasoning overhead.** The agent can use its existing code-editing
  instincts instead of reconstructing meaning from nested JSON and link arrays.
- **Better token economy.** A readable Python workflow can carry the same
  structure with less repeated explanation because the syntax itself explains
  more of the job.
- **Smaller-agent accessibility.** We expect this approach to work better with
  cheaper, smaller, local models because they can lean on general Python
  competence instead of learning a niche graph JSON dialect from scratch.
- **Universal composition.** Once the workflow is Python, ordinary Python can
  wrap it: recipes, loops, parameter sweeps, validation, tests, filesystem
  logic, and higher-level orchestration all become straightforward.

## Why Not Improve The JSON Instead?

Earlier VibeComfy work explored tools for operating more directly on ComfyUI
JSON. That path can work for narrow tasks, but it felt like a losing battle for
agentic workflows. The more context you add around JSON, the closer you get to
inventing a second language beside it.

VibeComfy takes the opposite route: translate the graph into ordinary Python,
let the agent work there, then compile back to the API JSON that ComfyUI already
accepts.

The important constraint is that this translation must be faithful. VibeComfy is
designed to preserve the information that matters: nodes, edges, widget values,
public inputs, output contracts, custom-node requirements, model assets,
subgraphs, provenance, and, for UI round-trips, editor layout where it is
available. JSON remains the import/export and runtime format. Python becomes the
agent-readable middle layer.

That is the core bet: do not make agents become native ComfyUI JSON editors.
Give them a translation layer in the programming language they already
understand best.
