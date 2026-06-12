You are auditing tracked Python/source files for deletion.

Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task:
- Find tracked source files that appear obsolete, shadowed by packages, duplicate implementations, or unused compatibility shims.
- Check imports/references before recommending deletion.
- Include already-deleted candidates in the current worktree only if current evidence confirms the deletion is right.

Constraints:
- Do not edit files.
- Avoid behavior-changing deletion unless evidence is strong and verification is clear.
- Output delete / keep / needs deeper audit tables with exact evidence.
