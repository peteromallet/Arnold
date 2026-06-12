# Porting Deep Audit 06 — CLI Coupling To Porting Internals

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: inspect command modules that keep old porting paths alive or expose internal structure.

Focus:
- `vibecomfy/commands/`
- `vibecomfy/porting/`
- `tests/test_cli.py`, command tests

Questions:
1. Which CLI commands import porting internals directly?
2. Are there wrappers/barrels that should exist to reduce path churn?
3. Are any command modules stale after deletions (`commands/port.py`, `_analyze_names.py`)?
4. What additional file deletion or move is safe?

Return actionable cleanup with exact import references.

Do not edit files.
