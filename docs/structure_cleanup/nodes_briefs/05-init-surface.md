# Nodes Layer Audit 05: __init__ Surface

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: clean up `vibecomfy/nodes/__init__.py` and `.pyi`.

Current issue:
- `vibecomfy/nodes/__init__.py` hardcodes wildcard imports for each generated pack and then contains a huge static `__all__`.
- `_generated/__init__.py` already has `MODULES`.

Inspect:
- `vibecomfy/nodes/__init__.py`
- `vibecomfy/nodes/__init__.pyi`
- `vibecomfy/nodes/_generated/__init__.py`
- tests around generated wrappers and node shims.

Return:
1. Should `__init__.py` become dynamic over `_generated.MODULES`?
2. Should `__all__` remain static or be computed from generated module `__all__`?
3. What should happen to `.pyi`?
4. Exact tests to run.
Keep the answer under 450 words.
