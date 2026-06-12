Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit whether template/corpus/recipe test fixtures are stored in the right places.

Use:
- `find tests -maxdepth 3 -type d -o -type f | rg "(fixture|snapshot|gold|recipe|workflow|template|corpus)" | sort`
- `find recipes ready_templates workflow_corpus -maxdepth 3 -type f | sort`
- `rg -n "gold_template|snapshot|fixture|recipes/|workflow_corpus|ready_templates" tests docs README.md vibecomfy`

Do not edit files.

Questions:
1. Are snapshots/test fixtures mixed into user-facing source directories?
2. Is that intentional or should some move under `tests/fixtures/`?
3. What moves are safe now?

Return exact recommendations and risks.
