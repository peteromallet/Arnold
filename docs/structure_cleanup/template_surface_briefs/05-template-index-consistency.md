Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: inspect consistency between `ready_templates/`, `template_index.json`, and CLI listings.

Use:
- `python -m vibecomfy.cli workflows list --ready --json`
- `python -m vibecomfy.cli analyze corpus --json` if cheap
- `find ready_templates -type f -name '*.py' | sort`
- `python - <<'PY'\nimport json\nprint(json.load(open('template_index.json')).keys())\nPY`

Do not edit files.

Questions:
1. Are there obvious unindexed or orphaned ready templates?
2. Does any layout cleanup require regenerating indexes?
3. What verification should be run after any structure edit?

Return findings and exact commands.
