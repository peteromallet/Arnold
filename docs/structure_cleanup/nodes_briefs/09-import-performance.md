# Nodes Layer Audit 09: Import Performance and Side Effects

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: evaluate whether `vibecomfy.nodes.__init__` importing all generated wrappers is structurally bad or acceptable.

Inspect:
- `vibecomfy/nodes/__init__.py`
- generated wrapper module sizes under `_generated/`
- common imports from `vibecomfy.nodes`
- tests/commands that import package root.

Questions:
- Does importing `vibecomfy.nodes` eagerly load very large modules?
- Can this be improved without breaking public imports?
- Would dynamic lazy loading via `__getattr__` be worth it, or too risky?

Return:
1. Keep/eager/dynamic/lazy recommendation.
2. Safe cleanup for this pass.
3. Follow-up if performance needs a behavioral refactor.
Keep the answer under 450 words.
