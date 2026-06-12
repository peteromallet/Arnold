# Porting Deep Audit 01 — Old/New Emitter Split

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: deletion-first audit of the remaining old/new emitter split under `vibecomfy/porting`.

Focus files:
- `vibecomfy/porting/emitter.py`
- `vibecomfy/porting/emit/`
- `vibecomfy/porting/emit_*.py`
- `vibecomfy/porting/ui_emitter.py`
- `vibecomfy/porting/emit/ui.py`

Questions:
1. Which root-level emitter files are still real implementations, and which are shims/duplicates?
2. Which imports/callers keep each old file alive?
3. Is there a safe deletion/migration path now, or is it a deeper behavioral refactor?
4. What exact files should be deleted, moved, or kept?

Return:
- `DELETE_NOW`, `MIGRATE_THEN_DELETE`, `KEEP_FOR_NOW`, `NEEDS_DEEPER_REFACTOR`.
- Concrete references with file:line evidence.
- Verification commands after any proposed deletion.

Do not edit files.
