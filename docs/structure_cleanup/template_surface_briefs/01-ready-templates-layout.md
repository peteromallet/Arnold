Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit `ready_templates/` layout and documentation.

Use:
- `find ready_templates -maxdepth 3 -type f | sort`
- `sed -n '1,160p' ready_templates/README.md`
- `sed -n '1,160p' ready_templates/VALIDATION.md`
- `rg -n "ready_templates|workflow_from_ready|workflow_from_id|template_index" README.md docs tests vibecomfy pyproject.toml`

Do not edit files.

Questions:
1. Is the current category layout (`image/`, `video/`, `audio/`, `edit/`) consistent and loader-backed?
2. Are any docs/index files missing?
3. Are any generated or stale files mixed into the template source tree?
4. What changes are safe without altering runtime behavior?

Return exact recommendations and risks.
