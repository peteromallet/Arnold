You are auditing `.megaplan`, `.agents`, `.claude`, `agents/`, and `agentic/` for deletion/retention.

Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task:
- Identify generated runtime state, stale logs, corrupt backups, scheduled-task state, and duplicate agent config that should be deleted.
- Distinguish repo-owned agent instructions from local runtime state.

Constraints:
- Do not edit files.
- Do not delete active user/global agent config without strong evidence.
- Output delete now / keep / needs approval lists.
