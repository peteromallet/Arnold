"""
03_convert_json_to_ready_template.py — Convert ComfyUI JSON to a ready template
================================================================================

Take a ComfyUI API-format JSON file and convert it into a Python ready template
using the ``port check`` / ``port convert`` pipeline.

All work is build-only by default.  The actual conversion CLI commands are
shown in ``if __name__ == '__main__'``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# The conversion pipeline uses CLI commands.  This tutorial explains the
# concepts and demonstrates the programmatic API path.
# ---------------------------------------------------------------------------

# --- Concept: what the CLI does ---
#
#   1. vibecomfy port check workflow.json
#      Validates the JSON structure, detects custom nodes, model references,
#      widget aliases, and other portability issues.
#
#   2. vibecomfy port convert workflow.json
#      Produces a Python scratchpad (importable .py file) that builds the
#      same workflow using vibecomfy APIs.
#
#   3. vibecomfy port convert workflow.json --ready-id image/my_template
#      Produces a ready-template candidate with public inputs, model assets,
#      and metadata — suitable for the ready_templates/ directory.


def explain_pipeline() -> None:
    """Print the conversion pipeline steps (no filesystem or network access)."""
    steps = [
        ("1. Validate", "vibecomfy port check my_workflow.json"),
        ("2. Convert (scratchpad)", "vibecomfy port convert my_workflow.json"),
        ("3. Convert (ready template)", "vibecomfy port convert my_workflow.json --ready-id image/my_template"),
        ("4. Doctor check", "vibecomfy port doctor-all my_workflow.json --json"),
        ("5. Copy for hand-editing", "python -m vibecomfy.cli copy-to-recipe image/my_template --out my_recipe.py --strip-markers"),
    ]
    print("Port conversion pipeline:")
    for label, cmd in steps:
        print(f"  {label:30s} {cmd}")


# ---------------------------------------------------------------------------
# Programmatic path (build-only, import-safe)
# ---------------------------------------------------------------------------

def load_and_inspect_json(path: str) -> dict:
    """Load a ComfyUI API JSON and return basic stats — no GPU, no network."""
    import json
    from pathlib import Path

    raw = json.loads(Path(path).read_text())
    nodes = {k: v for k, v in raw.items() if isinstance(v, dict) and "class_type" in v}
    class_types = sorted({v["class_type"] for v in nodes.values()})
    return {
        "path": path,
        "node_count": len(nodes),
        "class_types": class_types,
    }


if __name__ == "__main__":
    explain_pipeline()

    # Example: inspect the wan_i2v.json workflow corpus entry
    import json
    from pathlib import Path

    corpus_path = Path(__file__).resolve().parents[2] / "ready_templates/sources" / "official" / "video" / "wan_i2v.json"
    if corpus_path.exists():
        info = load_and_inspect_json(str(corpus_path))
        print(f"\nExample: {info['path']}")
        print(f"  Nodes: {info['node_count']}")
        print(f"  Class types: {', '.join(info['class_types'])}")
    else:
        print("\n(ready_templates/sources not found — clone the repo to see a real example)")
