You are auditing deletion candidates in local ignored/untracked junk.

Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task:
- Find ignored/cache/backup/build/runtime files that should be deleted from this checkout.
- Include `.pytest_cache`, `__pycache__`, `.pyc`, `.bak`, stale pid/log/temp outputs, and generated local tool state.
- Distinguish safe-delete local junk from ignored state that may be intentionally retained (e.g. secrets, model caches, user data).

Constraints:
- Do not edit files.
- Do not print secret contents. Treat `this.env` as secret and leave it alone.
- Output: exact paths to delete, exact paths to keep, and verification commands.
