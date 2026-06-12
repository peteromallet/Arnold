Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit ignored `.megaplan` runtime/cache/log state and identify what can be removed only with explicit approval.

Use:
- `git status --ignored --short .megaplan`
- `du -sh .megaplan .megaplan/* 2>/dev/null | sort -h`
- `find .megaplan -maxdepth 2 -type d | sort`
- `find .megaplan -maxdepth 2 -type f -size +5M -print`

Do not delete or edit files.

Questions:
1. Which ignored directories are generated state (`plans`, `logs`, `telemetry`, locks, wakeup, verification)?
2. Which ignored files/directories might be authored or reusable (`schemas`, selected briefs, selected tickets)?
3. What cleanup policy should be documented, and what requires user approval?

Return a safe-delete-with-approval list, keep list, and uncertainty list.
