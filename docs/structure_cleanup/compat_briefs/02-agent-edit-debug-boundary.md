# Compatibility Layer Audit 02: Agent Edit Debug Boundary

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: decide whether root `vibecomfy/_agent_edit_debug.py` should move under `vibecomfy/commands/` or elsewhere, and whether the root file can be deleted.

Inspect:
- `vibecomfy/_agent_edit_debug.py`
- `vibecomfy/commands/debug.py`
- `scripts/vibecomfy_debug.py`
- `tests/test_cli_debug.py`
- docs that mention debug tooling.

Return under 500 words:
1. Canonical home for this implementation.
2. Whether root import path is public or accidental.
3. Required import migrations for deletion.
4. Verification commands.
