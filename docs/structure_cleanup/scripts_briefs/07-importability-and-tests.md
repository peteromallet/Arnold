Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Audit importability and test dependencies for `scripts/` and `tools/`.

Check `__init__.py`, direct imports, subprocess invocations, GitHub Actions,
and docs. Return:

1. Paths that are load-bearing and should not move.
2. Paths that are only direct-run scripts and can move if docs update.
3. Verification commands for any cleanup.

Under 650 words.
