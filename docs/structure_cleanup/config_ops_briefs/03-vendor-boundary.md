Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit `vendor/` as a structural boundary.

Use:
- `find vendor -maxdepth 3 -type f | sort | sed -n '1,240p'`
- `.gitmodules`
- `rg -n "vendor/|ComfyUI|submodule|gitmodules" README.md docs scripts tests vibecomfy pyproject.toml .github`

Do not edit files.

Questions:
1. Is `vendor/` a submodule, checked-in vendored code, or local dependency?
2. Is there a README or policy explaining what belongs there?
3. Are any safe docs/index improvements needed?
4. What must not move?

Return exact recommendations.
