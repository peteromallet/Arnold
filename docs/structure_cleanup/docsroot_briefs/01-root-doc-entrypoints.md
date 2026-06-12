Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: classify the remaining Markdown files directly under `docs/` after the first docs cleanup.

Use:
- `find docs -maxdepth 1 -type f -name '*.md' | sort`
- `sed -n '1,120p' docs/README.md`
- Read only the root docs needed to decide.

Do not edit files.

Questions:
1. Which root docs are true entry points and should stay directly under `docs/`?
2. Which root docs are topic-specific and should move under existing subfolders?
3. Which files need new subfolders if moved?

Return a table: path, classification, recommended location, confidence, link-update risk.
