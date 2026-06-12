# Porting Deep Audit 07 — Tests And Fixtures For Porting

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: determine whether tests/fixtures still reference removed or stale porting surfaces, and whether fixture files can be deleted or moved.

Focus:
- `tests/test_*port*`
- `tests/test_*wrapper*`
- `tests/fixtures/`
- `vibecomfy/porting/`

Questions:
1. Which tests assert old module names only in docstrings/comments?
2. Which fixtures are stale or unused?
3. Do tests need path migration after shim deletion?
4. What can be deleted now?

Return exact test/fixture actions and focused test commands.

Do not edit files.
