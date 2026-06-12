# Porting Deep Audit 08 — Public API Compatibility Risk

Work from repo root `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: identify which remaining porting paths may be public enough to avoid deleting without a versioned breaking-change note.

Focus:
- `vibecomfy/porting/__init__.py`
- docs and README examples
- package exports in `pyproject.toml`
- tests that import `vibecomfy.porting.*`

Bias: the user prefers deleting shims by default. Keep a compatibility path only for a strong reason.

Questions:
1. Which deleted or candidate paths are documented public APIs?
2. Which are internal-only and safe to remove?
3. Which docs need migration notes?
4. What is the minimum public surface that should remain?

Return a keep/delete/migration table.

Do not edit files.
