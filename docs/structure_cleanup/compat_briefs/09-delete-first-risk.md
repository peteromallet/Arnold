# Compatibility Layer Audit 09: Deletion-First Risk

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: argue against keeping compatibility files by default. Find what can actually be deleted now.

Use the user's policy:
- Delete as many shims as possible.
- Keep only in extreme public-contract cases.

Inspect candidates and imports. Be strict.

Return under 500 words:
1. Files that should be deleted now.
2. Files that should stay only as public-contract exceptions.
3. Any hidden risk of leaving duplicate implementations in place.
4. Tests/commands to prove deletion safety.
