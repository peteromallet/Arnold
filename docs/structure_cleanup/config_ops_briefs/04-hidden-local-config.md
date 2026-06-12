Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit hidden local/config directories at root.

Focus:
- `.agents/`
- `.claude/`
- `.desloppify/`
- `.pytest_cache/`
- `.venv/`
- `.importlinter/`

Use:
- `git status --ignored --short .agents .claude .desloppify .pytest_cache .venv .importlinter`
- `find .agents .claude .desloppify .importlinter -maxdepth 3 -type f 2>/dev/null | sort`
- `.gitignore`

Do not edit files.

Questions:
1. Which are tracked versus ignored local state?
2. Are any tracked files in hidden dirs intentional?
3. Is root README/agents docs enough to explain them?
4. What can be safely deleted only with explicit approval?

Return exact recommendations and deletion risks.
