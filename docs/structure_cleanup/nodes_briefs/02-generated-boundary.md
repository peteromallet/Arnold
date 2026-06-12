# Nodes Layer Audit 02: Generated Boundary

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: decide the cleanest file boundary between generated wrappers and checked-in public API files.

Questions:
- Should `vibecomfy/nodes/_generated/` be the only place containing per-pack generated code?
- Should `vibecomfy/nodes/` contain any generated files beyond `__init__.py`, `__init__.pyi`, and maybe `index.py`?
- Should per-pack public imports be generated as packages, aliases, dynamic module registration, or explicit files?

Inspect:
- `vibecomfy/nodes/__init__.py`
- `vibecomfy/nodes/__init__.pyi`
- `vibecomfy/nodes/_generated/__init__.py`
- `tools/generate_node_shims.py`
- `vibecomfy/porting/emit_ready.py`
- `vibecomfy/porting/emitter.py`
- `vibecomfy/porting/emit/emitter.py`

Return:
1. Recommended target layout.
2. What files should be deleted, kept, or generated.
3. Whether the generator should be changed in this pass.
4. Verification commands.
Keep the answer under 500 words.
