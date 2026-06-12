Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit `.gitignore` after cleanup work.

Use:
- `sed -n '1,220p' .gitignore`
- `git status --ignored --short | sed -n '1,260p'`
- `git ls-files | rg "(__pycache__|\\.pyc$|\\.DS_Store$|\\.env$|\\.pytest_cache|\\.ruff_cache|\\.import_linter_cache|out/|input/)"`

Do not edit files.

Questions:
1. Are ignore rules too broad, stale, missing, or misleading?
2. Are ignored-but-important surfaces documented?
3. Are there ignored files under source dirs that should be removed?
4. What exact safe `.gitignore` or cleanup changes are recommended?

Return exact recommendations.
