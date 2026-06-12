Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: take a decisive position on whether to move tracked `.megaplan` authored files into `docs/` now.

Context:
- The cleanup goal is repo organization with low regression risk.
- Many earlier layers preferred documentation/indexes over path churn when paths are operational contracts.
- `.megaplan/` is mostly ignored local state, but selected files are tracked by force.

Do not edit files.

Consider:
- `git ls-files .megaplan`
- `rg -n "\\.megaplan/briefs|\\.megaplan/chains|\\.megaplan/ideas|\\.megaplan/tickets|docs/megaplan_chains" docs README.md scripts tests vibecomfy .github 2>/dev/null`

Return:
- Final recommendation: move now / keep and document / split.
- Concrete first batch.
- Concrete deferred batch.
- Risks and verification commands.
