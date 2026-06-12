# Nodes Layer Audit 04: Public API Contract

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: determine whether `from vibecomfy.nodes.core import SaveImage` and sibling pack imports are public API or internal shims.

Inspect:
- `README.md`
- `docs/authoring.md`
- `docs/templates/`
- `docs/runtime/`
- `AGENTS.md`, `CLAUDE.md`
- `pyproject.toml`
- `tests/test_api_surface.py`
- `tests/test_node_shims.py`

Question:
If these imports are public API, say so clearly and explain whether deletion would violate the user's "delete shims except extreme case" rule by being an extreme case.

Return:
1. Verdict: public API, internal shim, or mixed.
2. Strongest evidence.
3. If public, the best cleanup that still improves structure.
4. If internal, migration/deletion plan.
Keep the answer under 500 words.
