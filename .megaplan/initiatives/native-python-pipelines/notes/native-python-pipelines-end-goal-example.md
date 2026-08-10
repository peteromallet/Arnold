# End-goal example: native Python as the runtime

This is what a pipeline would look like if we committed to Option B: the runtime executes ordinary Python, intercepts `@phase` calls as checkpoint boundaries, and derives graph views from traces or static analysis.

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from arnold.pipeline.native import pipeline, phase


@dataclass
class FolderTree:
    target_dir: Path
    max_depth: int
    folders: list[dict]


@dataclass
class Audit:
    summary: dict
    folders: list[dict]
    settled_decisions: list[str]

    @classmethod
    def empty(cls) -> "Audit":
        return cls(summary={}, folders=[], settled_decisions=[])


@dataclass
class AuditArtifacts:
    audit_json: Path
    audit_md: Path


@phase
async def ingest(target_dir: Path, max_depth: int = 8) -> FolderTree:
    """Read target_dir and build a folder tree."""
    folders = _build_tree(target_dir, max_depth)
    return FolderTree(target_dir=target_dir, max_depth=max_depth, folders=folders)


@phase
async def audit_tree(tree: FolderTree) -> Audit:
    """Audit the tree level-by-level via agent workers."""
    audited = await _audit_folders(tree.folders)
    return Audit(summary=_compute_summary(audited), folders=audited, settled_decisions=[])


@phase
async def emit(audit: Audit) -> AuditArtifacts:
    """Write audit.json and audit.md."""
    audit_json = _write_json(audit)
    audit_md = _write_markdown(audit)
    return AuditArtifacts(audit_json=audit_json, audit_md=audit_md)


@pipeline("folder-audit")
async def folder_audit_pipeline(target_dir: Path, max_depth: int = 8):
    """Walk a directory tree and produce a structured audit."""
    tree = await ingest(target_dir, max_depth)

    if not tree.folders:
        audit = Audit.empty()
    else:
        audit = await audit_tree(tree)

    artifacts = await emit(audit)
    return artifacts


# CLI entry point remains unchanged.
def build_pipeline() -> Pipeline:
    return native_to_pipeline(folder_audit_pipeline)
```

## Why this is the end goal

- **Ordinary Python.** The pipeline is an `async def` function. It uses variables, `if`, loops, and function calls exactly like any other Python code.
- **No graph vocabulary.** No `Stage`, `Edge`, `yield from phase(...)`, or `PortRef` in the author-facing code.
- **Inputs are parameters.** `target_dir` and `max_depth` are plain function arguments.
- **Data flows through return values.** `tree`, `audit`, and `artifacts` are ordinary local variables.
- **Phases are reusable functions.** `ingest`, `audit_tree`, and `emit` can be imported, unit-tested, and composed in other pipelines.

## How the runtime makes this possible

Under Option B, the runtime would:

1. **Intercept `@phase` calls.** When `folder_audit_pipeline` awaits `ingest(...)`, the runtime records:
   - the phase name,
   - the input arguments,
   - the current local-variable snapshot.

2. **Checkpoint before and after.** Before invoking the phase body, the runtime writes a checkpoint so the phase can be replayed or resumed. After the phase returns, the result is stored and the pipeline continues.

3. **Persist enough state to resume.** If the pipeline suspends after `audit_tree`, the runtime saves the local variables (`tree`, `audit`, etc.) and the program counter (the next `await` point). On resume, it restores those locals and continues from that point.

4. **Derive observability from traces.** `arnold pipelines check` and dashboards build a graph from the recorded trace or from static analysis of the `@pipeline` function, rather than from a hand-built graph.

5. **Enforce contracts at phase boundaries.** The runtime inspects `@phase` type annotations or registered schemas to validate handoffs, same as the current executor does today.

## What this costs

This is not a free upgrade. It requires:

- A native runtime that reproduces all current executor semantics: resume, state merge, event journal, suspension cursors, envelope joining, typed handoffs, override routing, subloop promotion, loop guards, policy/governor behavior, etc.
- A way to derive a trustworthy graph view for observability, either from static analysis or from recorded traces.
- A parity corpus proving that old graph-driven plans resume identically under the new runtime.

That is why the current plan treats this as the end-state and starts with the bridge path.
