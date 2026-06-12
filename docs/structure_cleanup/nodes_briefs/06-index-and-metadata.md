# Nodes Layer Audit 06: index.py and Metadata Boundary

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: decide whether `vibecomfy/nodes/index.py` earns its place at the nodes package root.

Inspect:
- `vibecomfy/nodes/index.py`
- imports of `vibecomfy.nodes.index`
- generated wrapper modules for any duplicated metadata structures
- `vibecomfy/porting/emit_constants.py`
- node index/cache commands, if any.

Return:
1. Keep/move/delete verdict for `nodes/index.py`.
2. Whether its name collides conceptually with root `node_index.json` removal.
3. Any safe cleanup to make this boundary clearer.
4. Verification commands.
Keep the answer under 450 words.
