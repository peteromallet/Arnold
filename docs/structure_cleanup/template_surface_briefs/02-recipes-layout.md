Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit `recipes/` as user-facing runnable examples.

Use:
- `find recipes -maxdepth 2 -type f | sort`
- `sed -n '1,200p' recipes/README.md`
- `rg -n "recipes/|dual_pass_t2i|wan_i2v_lowres|example_tested_recipe|wan_t2v_long" README.md docs tests vibecomfy pyproject.toml`

Do not edit files.

Questions:
1. Are recipe files organized and named clearly?
2. Is any generated snapshot or test fixture misplaced?
3. Should recipes split into subdirs, or would that break references?
4. What safe doc/index improvements are available?

Return exact recommendations and risks.
