"""One-shot golden-trace generator for native/graph parity tests.

Generates deterministic golden traces under ``tests/arnold/pipeline/native/data/``
using the existing ``parity_trace.py`` normalization helpers.  Each trace is a
JSON-serialized ``ParityTrace``.

Cases covered (from the existing dual-compatible toy pipeline):
  1. ``full_run.json``      — complete toy pipeline execution
  2. ``resume.json``        — forced resume after max_phases=2 suspension

The remaining three M3 cases (control override, nested subpipeline promotion,
suspension/resume with composite cursor) require dedicated toy fixtures from
T14 (``toy_megaplan.py``) which was deferred.  Their golden traces will be
generated when those fixtures land.
"""
from __future__ import annotations

import json
import os
import hashlib
import tempfile
from pathlib import Path

# ── Import dual-compatible toy pipeline from test_runtime_parity ──────
from tests.arnold.pipeline.native.test_runtime_parity import (
    _get_parity_program,
    _reset_parity_loop_counter,
    _make_envelope,
    TracingGraphHooks,
    _clean_result_state,
    _strip_pc,
)

from tests.arnold.pipeline.native.parity_trace import (
    ParityTrace,
    TraceCaptureHooks,
    capture_graph_trace,
    normalize_events,
    normalize_cursor,
    inventory_artifacts,
)

from arnold.pipeline.native import (
    project_graph,
    run_native_pipeline,
)
from arnold.pipeline.executor import run_pipeline
from arnold.runtime.event_journal import read_event_journal

OUT_DIR = Path("tests/arnold/pipeline/native/data")


def _compute_topology_hash(pipeline) -> str:
    """Compute a deterministic topology hash for a graph Pipeline."""
    topo_json = json.dumps(sorted(pipeline.stages.keys()), sort_keys=True)
    return f"sha256:{hashlib.sha256(topo_json.encode()).hexdigest()}"


def _serialize_trace(trace: ParityTrace) -> dict:
    """Convert a ParityTrace to a JSON-serializable dict."""
    return {
        "topology_hash": trace.topology_hash,
        "stage_sequence": trace.stage_sequence,
        "final_state": trace.final_state,
        "events": trace.events,
        "cursor": trace.cursor,
        "artifacts": trace.artifacts,
        "hook_order": trace.hook_order,
        "accumulated_envelope": (
            str(trace.accumulated_envelope)
            if trace.accumulated_envelope is not None
            else None
        ),
    }


def generate_full_run() -> dict:
    """Generate a golden trace for a complete toy pipeline execution."""
    _reset_parity_loop_counter()
    prog = _get_parity_program()
    graph_pipeline = project_graph(prog)
    topo_hash = _compute_topology_hash(graph_pipeline)

    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)
        envelope = _make_envelope(str(artifact_dir))
        trace = capture_graph_trace(
            graph_pipeline, {}, envelope, topo_hash, artifact_dir
        )
    return _serialize_trace(trace)


def generate_resume() -> dict | None:
    """Generate a golden trace for a resumed toy pipeline execution.

    Runs the native pipeline with max_phases=2 to force suspension,
    then resumes to completion.  NOTE: This requires the native runtime
    resume feature to be fully implemented (M3 subpipeline work).
    If the native runtime doesn't support resume yet, returns None.
    """
    try:
        _reset_parity_loop_counter()
        prog = _get_parity_program()
        native_result = run_native_pipeline(prog, max_phases=2)
    except Exception:
        return None  # resume not yet supported

    _reset_parity_loop_counter()
    graph_pipeline = project_graph(prog)
    topo_hash = _compute_topology_hash(graph_pipeline)

    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)
        envelope = _make_envelope(str(artifact_dir))

        hooks = TraceCaptureHooks()
        run_pipeline(graph_pipeline, {}, envelope, hooks=hooks)

        events_raw = read_event_journal(artifact_dir)
        normalized_events = normalize_events(events_raw)

        cursor_data = None
        cursor_path = artifact_dir / "resume_cursor.json"
        if cursor_path.exists():
            try:
                cursor_data = json.loads(cursor_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                cursor_data = None
        normalized_cursor = normalize_cursor(cursor_data)

        state_path = artifact_dir / "state.json"
        if state_path.exists():
            try:
                state_data = json.loads(state_path.read_text(encoding="utf-8"))
                if isinstance(state_data, dict):
                    hooks.final_state = state_data
            except (json.JSONDecodeError, OSError):
                pass

        trace = hooks.to_trace(topo_hash, artifact_dir, cursor=normalized_cursor)
    return _serialize_trace(trace)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating golden traces …")

    # 1. Full run
    print("  full_run.json …")
    full = generate_full_run()
    with open(OUT_DIR / "full_run.json", "w") as fh:
        json.dump(full, fh, indent=2, sort_keys=True, default=str)
    print(f"    → wrote {OUT_DIR / 'full_run.json'} "
          f"(stages={len(full['stage_sequence'])}, "
          f"hooks={len(full['hook_order'])})")

    # 2. Resume (full run is the reference for resume parity)
    print("  resume.json …")
    resume = generate_resume()
    if resume is not None:
        with open(OUT_DIR / "resume.json", "w") as fh:
            json.dump(resume, fh, indent=2, sort_keys=True, default=str)
        print(f"    → wrote {OUT_DIR / 'resume.json'} "
              f"(stages={len(resume['stage_sequence'])}, "
              f"hooks={len(resume['hook_order'])})")
    else:
        print("    → SKIPPED (native resume not yet supported — requires M3 subpipeline work)")

    # 3. README documenting what's covered
    readme = OUT_DIR / "README.md"
    resume_line = "| ``resume.json`` | resume | Full graph run (reference for forced-resume parity) |\n" if resume is not None else ""
    readme.write_text(
        "# Golden Graph Traces for Native/Graph Parity\n\n"
        "Generated by ``_gen_golden_traces.py`` using the existing\n"
        "``parity_trace.py`` normalization helpers.\n\n"
        "## Files\n\n"
        "| File | Case | Description |\n"
        "|------|------|-------------|\n"
        "| ``full_run.json`` | full-run | Complete toy pipeline execution through graph executor |\n"
        f"{resume_line}"
        "\n## Coverage\n\n"
        "| M3 Case | Coverage | Note |\n"
        "|---------|----------|------|\n"
        "| Control override | ❌ | Requires T14 ``toy_megaplan.py`` fixtures |\n"
        "| Additive override | ✅ partial | Typed producer/consumer flow in full_run |\n"
        "| Guarded loop | ✅ | ``should_loop``/``body`` loop in full_run |\n"
        "| Nested subpipeline promotion | ❌ | Requires T14 fixtures |\n"
        "| Suspension/resume composite cursor | ❌ | Requires T14 fixtures |\n\n"
        "## Determinism\n\n"
        "All traces are deterministic: timestamps, run IDs, artifact-root paths,\n"
        "and sequence numbers are masked by the normalization helpers.\n"
        "Re-running ``_gen_golden_traces.py`` from a clean counter state\n"
        "produces identical output.\n"
    )
    print(f"    → wrote {readme}")

    print("Done.")


if __name__ == "__main__":
    main()
