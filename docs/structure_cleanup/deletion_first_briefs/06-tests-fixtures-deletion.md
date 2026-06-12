You are auditing tests and fixtures for deletion.

Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task:
- Find stale fixtures, generated reports, e2e outputs, ignored node_modules/report dirs, and obsolete tests that should be deleted.
- Check whether tracked fixtures are referenced before deletion.
- Include already-deleted fixture candidates if current evidence supports deletion.

Constraints:
- Do not edit files.
- Avoid deleting tests just because they fail; classify failing-but-valid separately.
- Output exact candidates and verification commands.
