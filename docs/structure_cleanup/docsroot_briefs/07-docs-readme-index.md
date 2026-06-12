Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit `docs/README.md` against the remaining root docs.

Use:
- `find docs -maxdepth 1 -type f -name '*.md' | sort`
- `sed -n '1,160p' docs/README.md`

Do not edit files.

Questions:
1. Does `docs/README.md` link every root doc that should be discoverable?
2. Does it point users to correct subfolders after recent moves?
3. What minimal edits should be made after this layer?

Return exact README changes.
