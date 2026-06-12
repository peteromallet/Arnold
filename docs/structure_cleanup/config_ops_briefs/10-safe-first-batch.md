Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: propose a safe first batch for config/ops structure cleanup.

Inputs:
- Root config files and hidden dirs
- `.github/`, `vendor/`, deployment/env files
- Existing cleanup policy: avoid path churn where tools depend on root paths

Do not edit files.

Return:
- exact edits to do now
- exact deletions to do now if safe
- moves/deletions to defer
- verification commands
