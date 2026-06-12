# Nodes Layer Audit 01: Delete Node Shims

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: evaluate whether the thin files directly under `vibecomfy/nodes/` can be deleted.

Context:
- `vibecomfy/nodes/_generated/*.py` contains the real generated wrapper modules.
- `vibecomfy/nodes/<pack>.py` files appear to be thin re-export shims.
- User preference: delete shims by default; keep only in an extreme case with a hard public contract.

Inspect:
- `vibecomfy/nodes/`
- `vibecomfy/nodes/_generated/`
- `tests/test_node_shims.py`
- `tools/generate_node_shims.py`
- imports under `ready_templates/`, `tests/`, `scripts/`, `docs/`, and `vibecomfy/`

Return:
1. Ranked list of node shim files that can be safely deleted now.
2. Ranked list of shim files that must stay for public/API reasons.
3. Required caller migrations if deletion is possible.
4. Highest-risk test/doc surfaces to update.
Keep the answer under 500 words.
