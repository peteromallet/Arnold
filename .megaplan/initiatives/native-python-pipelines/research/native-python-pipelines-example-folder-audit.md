# Example: `folder-audit` expressed natively

This is what `arnold/pipelines/folder_audit/__init__.py` could look like under the native-Python authoring layer. The decorators capture metadata; the bridge compiles this into the same three-stage `Pipeline` graph the existing executor already runs.

```python
from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path
from typing import Any

from arnold.pipeline.native import pipeline, phase, PhaseContext
from arnold.pipeline.types import Port, PortRef
from arnold.pipelines.megaplan._pipeline.artifacts import next_version_path
from arnold.pipelines.megaplan._pipeline.step_helpers import resolve_prompt_text
from arnold.runtime.state_persistence import atomic_write_json


# ---------------------------------------------------------------------------
# Contracts (reusing the existing Port / PortRef vocabulary)
# ---------------------------------------------------------------------------

tree_out = Port(name="tree", logical_type="folder_tree", content_type="application/json")
audit_out = Port(name="audit", logical_type="folder_audit", content_type="application/json")


# ---------------------------------------------------------------------------
# Phase handlers
# ---------------------------------------------------------------------------

def ingest_phase(ctx: PhaseContext) -> dict[str, Any]:
    """Read target_dir, build folder tree."""
    target = ctx.inputs.get("target_dir")
    if not target:
        raise ValueError(
            "Pass a directory path: arnold run folder-audit "
            "--inputs target_dir=/path/to/dir"
        )
    target_path = Path(str(target)).expanduser().resolve()
    if not target_path.exists() or not target_path.is_dir():
        raise ValueError(f"Target is not a directory: {target_path}")

    max_depth = int(str(ctx.inputs.get("max_depth", 8)))
    tree = _build_tree(target_path, max_depth=max_depth)
    return {"target_dir": str(target_path), "tree": tree}


def audit_phase(ctx: PhaseContext, tree: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit the tree level-by-level via agent workers."""
    # If the user supplied pre-computed agent_results, use them.
    agent_results_input = ctx.inputs.get("agent_results")
    if agent_results_input:
        results_path = Path(str(agent_results_input)).expanduser().resolve()
        audit_data = json.loads(results_path.read_text(encoding="utf-8"))
        if "summary" not in audit_data:
            audit_data["summary"] = _compute_summary(audit_data.get("folders", []))
        return audit_data

    target_dir = Path(ctx.state["target_dir"])
    max_chunk_size = int(str(ctx.inputs.get("chunk_size", 5)))
    max_workers = int(str(ctx.inputs.get("max_workers", 3)))

    by_level: dict[int, list[dict[str, Any]]] = {}
    for folder in tree:
        by_level.setdefault(folder["level"], []).append(folder)

    all_folders: list[dict[str, Any]] = []
    parent_purposes: dict[str, str] = {"": ""}
    raw_outputs: list[str] = []

    for level in sorted(by_level):
        folders = by_level[level]
        chunks = [folders[i : i + max_chunk_size] for i in range(0, len(folders), max_chunk_size)]
        level_results: list[dict[str, Any]] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(_audit_chunk, target_dir, level, chunk, parent_purposes, ctx)
                for chunk in chunks
            ]
            for future in concurrent.futures.as_completed(futures):
                chunk_result, raw_output = future.result()
                level_results.extend(chunk_result)
                raw_outputs.append(raw_output)

        for result in level_results:
            path = result.get("path", "")
            if path:
                parent_purposes[path] = result.get("inferred_purpose", "")
        all_folders.extend(level_results)

    audit_data = {
        "summary": _compute_summary(all_folders),
        "folders": all_folders,
        "settled_decisions": [],
    }

    raw_path = next_version_path(ctx, kind="audit_raw", extension="md")
    raw_path.write_text("\n\n---\n\n".join(raw_outputs), encoding="utf-8")

    # The bridge/executor attaches this as an output artifact.
    ctx.write_output("audit_raw", raw_path)
    return audit_data


def emit_phase(ctx: PhaseContext, audit: dict[str, Any]) -> dict[str, Path]:
    """Write audit.json and audit.md."""
    audit_json_path = ctx.plan_dir / "audit.json"
    audit_md_path = ctx.plan_dir / "audit.md"

    atomic_write_json(audit_json_path, audit)
    audit_md_path.write_text(_render_markdown(ctx.state.get("tree", []), audit), encoding="utf-8")

    ctx.write_output("audit_json", audit_json_path)
    ctx.write_output("audit_md", audit_md_path)
    return {"audit_json": audit_json_path, "audit_md": audit_md_path}


# ---------------------------------------------------------------------------
# Pipeline declaration
# ---------------------------------------------------------------------------

@pipeline("folder-audit", description="...")
def folder_audit_pipeline(ctx: PhaseContext):
    ingest_result = yield from phase(
        "ingest",
        ingest_phase,
        ctx,
        produces=(tree_out,),
    )
    tree = ingest_result["tree"]

    audit = yield from phase(
        "audit",
        audit_phase,
        ctx,
        tree,
        consumes=(PortRef(tree_out),),
        produces=(audit_out,),
    )

    yield from phase(
        "emit",
        emit_phase,
        ctx,
        audit,
        consumes=(PortRef(audit_out),),
    )


# ---------------------------------------------------------------------------
# Public build_pipeline contract (unchanged for the CLI)
# ---------------------------------------------------------------------------

def build_pipeline(worker: Any | None = None) -> Pipeline:
    # The bridge compiles ``folder_audit_pipeline`` into a Pipeline graph.
    # ``worker`` injection can be handled by attaching it to PhaseContext or
    # via a small adapter in the bridge; left as an implementation detail here.
    return native_to_pipeline(folder_audit_pipeline)
```

## What changed

- `IngestStep`, `AuditStep`, and `EmitStep` became plain Python functions (`ingest_phase`, `audit_phase`, `emit_phase`).
- `StepResult(next=..., state_patch=...)` boilerplate disappeared; functions return plain dicts / paths.
- The graph structure (`ingest → audit → emit`) is expressed as ordinary `yield from` calls.
- Contracts are declared on decorators instead of being implicit in `AgentStep` subclasses.

## What did not change

- The bridge compiles this into the same three-stage `Pipeline` the existing executor walks.
- Resume, event journals, artifact layout, `state.json`, and `arnold pipelines check` all behave exactly as before.
- Handoff validation still uses the existing `Port` / `PortRef` / `evaluate_step_io_handoff()` machinery.
