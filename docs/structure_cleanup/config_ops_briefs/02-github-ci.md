Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit `.github/` structure.

Use:
- `find .github -maxdepth 4 -type f | sort`
- read workflow/action files as needed
- `rg -n "\\.github|workflow|pre-commit|CI|GitHub Actions" README.md docs scripts tests pyproject.toml .github`

Do not edit files.

Questions:
1. Are workflow files logically named and grouped?
2. Is any stale or generated output committed under `.github/`?
3. Should `.github/README.md` exist?
4. What safe cleanup is available without changing CI behavior?

Return exact recommendations.
