Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: audit the tracked files under `.megaplan/` and decide what role this directory should play in repo structure.

Important facts:
- `.megaplan/` is gitignored, but some files are force-tracked.
- Use `git ls-files .megaplan` as the source of tracked files.
- Do not edit files. Return findings only.

Questions:
1. Which tracked `.megaplan` files are authored design/planning material versus generated runtime state?
2. Should tracked authored material stay under `.megaplan/`, move under `docs/megaplan_chains/` or another docs subtree, or remain force-tracked in place?
3. What is the least-risk first batch of changes for this layer?

Return:
- A concise classification table.
- A recommendation with rationale.
- Exact file paths for any proposed moves or README additions.
- Explicitly call out any paths that must not be deleted.
