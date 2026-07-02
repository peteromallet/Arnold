from __future__ import annotations

# REJECTED — direct manifest authoring
# Hand-authoring WorkflowManifest JSON or Python objects is rejected.
# The manifest is compiled output, never hand-authored source of truth.

WorkflowManifest = {
    "id": "hand-authored-manifest",
    "version": "1.0",
    "grammar_version": "arnold.workflow.authoring.v2",
    "nodes": [
        {"id": "plan", "kind": "step"},
        {"id": "execute", "kind": "step"},
        {"id": "review", "kind": "step"},
    ],
    "edges": [
        {"source": "plan", "target": "execute"},
        {"source": "execute", "target": "review"},
    ],
}
