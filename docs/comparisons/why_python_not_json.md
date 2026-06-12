# Why Python, Not JSON?

Earlier versions of VibeComfy tried to give agents better tools for working
directly with ComfyUI JSON. That helped in narrow cases, but it still forced the
agent to reconstruct intent from graph ids, links, widget arrays, and
node-specific conventions.

This version uses Python as the authoring surface instead. JSON remains the
import/export and runtime format; Python is the translation layer where agents
read, edit, validate, and compose workflows.

## Why Not Improve The JSON Instead?

JSON is the shape ComfyUI ultimately needs at queue time. But it is a poor
thinking surface for agents. It gives them nested data, ids, links, widget
positions, and class names, but very little semantic scaffolding for what the
workflow is trying to do.

You can add helpers, schema summaries, comments outside the JSON, or custom
views over the graph. The problem is that every extra aid starts to look like a
second language beside the JSON. Direct JSON editing asks the agent to reason in
a niche graph dialect when a better native working language is already
available.

VibeComfy takes the opposite route: translate the graph into ordinary Python,
let the agent work there, then compile back to the API JSON that ComfyUI already
accepts.

## Why Python Works Better

Based on public training practices and model behavior, LLMs have seen far more
Python code and Python reasoning than ComfyUI-specific workflow JSON. They know
how to read functions, names, imports, kwargs, tests, errors, and refactors.

They have also seen JSON, but usually as data to consume or emit, not as the
main place where a program is understood, modified, and validated. ComfyUI's
JSON is more specialized still: graph ids, link arrays, widgets, editor
furniture, custom-node quirks, and execution semantics all matter at once.

Python starts with a practical advantage: it is one of the world's most widely
used programming languages, and agents already demonstrate strong general
competence at reading and changing ordinary Python code.

## What Python Buys

- **Better comprehension.** Named variables, functions, kwargs, imports, and
  metadata declarations give the agent handles for intent, not just graph ids.
- **Lower reasoning overhead.** The agent can use its existing code-editing
  patterns instead of reconstructing meaning from nested JSON and link arrays.
- **Better token economy.** A readable Python workflow can carry the same
  structure with less repeated explanation because the syntax itself explains
  more of the job.
- **Smaller-agent accessibility.** We expect, pending systematic evaluation,
  that cheaper local models benefit from leaning on general Python competence
  instead of learning a niche graph JSON dialect from scratch.
- **Universal composition.** Once the workflow is Python, ordinary Python can
  wrap it: recipes, loops, parameter sweeps, validation, tests, filesystem
  logic, and higher-level orchestration all become straightforward.

## The Constraint: Faithful Translation

The translation has to preserve the graph semantics needed for execution.
VibeComfy is designed to carry nodes, edges, widget values, public inputs,
outputs, custom-node requirements, model assets, subgraphs, and provenance
through the Python layer. For UI round-trips, editor layout is preserved where it
is available.

That is the core bet: do not make agents become native ComfyUI JSON editors.
Give them a translation layer in the programming language where they already
show the strongest general competence.
