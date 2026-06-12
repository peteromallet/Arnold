# Porting Deep Audit 02 — Edit Session Root Modules

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: deletion-first audit of root-level edit-session modules now that `vibecomfy/porting/edit/` exists.

Focus files:
- `vibecomfy/porting/edit_session_*.py`
- `vibecomfy/porting/edit/`
- `vibecomfy/comfy_nodes/agent/`
- `tests/test_porting_edit_session.py`

Questions:
1. Are the root-level `edit_session_*.py` files still implementation modules, or should they move under `edit/`?
2. Which modules import them?
3. Are any dead after the previous shim deletion?
4. What concrete deletion or move plan reduces the root clutter without breaking tests?

Return specific file actions and import update requirements.

Do not edit files.
