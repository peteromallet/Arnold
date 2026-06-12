# Compatibility Layer Audit 06: Import Coupling

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: map live import coupling for the compatibility-layer candidates.

Candidates:
- `vibecomfy.fixtures`
- `vibecomfy._agent_edit_debug`
- `vibecomfy.schema.format`
- `vibecomfy.diagnostics`
- `vibecomfy.diagnostics.findings`

Return under 500 words:
1. Live importers by candidate.
2. Which imports can be migrated safely.
3. Which import paths should remain public.
4. Suggested stale-import guard tests, if any.
