# Porting Deep Audit 04 — Layout Boundary

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: audit whether porting layout code is cleanly organized.

Focus:
- `vibecomfy/porting/layout/`
- `vibecomfy/porting/layout_store.py`
- `vibecomfy/porting/ui_emitter.py`
- `vibecomfy/porting/emit/ui.py`
- layout-related tests

Questions:
1. Does `layout_store.py` earn root-level placement, or should it move under `layout/`?
2. Are any layout modules dead, duplicated, or stale?
3. Are there deleted-shim followups after identity import migration?
4. What move/delete path is safe now?

Return concrete actions, affected imports, and verification commands.

Do not edit files.
