Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: inspect `.megaplan/briefs/` and classify tracked brief files versus ignored/local brief files.

Use:
- `git ls-files .megaplan/briefs`
- `find .megaplan/briefs -maxdepth 3 -type f`
- `rg -n "agent-edit-chat|agent-edit-hardening|agent-edit-structural|text-to-graph-agent-epic|\\.megaplan/briefs" docs README.md tests vibecomfy scripts .megaplan 2>/dev/null`

Do not edit files.

Questions:
1. Which tracked brief sets are active contracts that other docs/tests reference?
2. Which ignored/local brief sets look like stale or private run inputs?
3. If we add documentation, where should the README live and what should it say?
4. Are any tracked `.megaplan/briefs` candidates for moving into `docs/` now, or would that create path churn?

Return exact paths and a conservative safe-first recommendation.
