Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: inspect references between docs and `.megaplan` to identify link/path hazards for any restructure.

Use:
- `rg -n "\\.megaplan|megaplan_chains|megaplan-briefs|scratchpad-emitter|frontier-hardening" README.md CLAUDE.md AGENTS.md docs scripts tests vibecomfy .github 2>/dev/null`

Do not edit files.

Questions:
1. Which references are operational commands that must remain valid?
2. Which references are historical mentions that can tolerate path changes?
3. Which docs already cover the `.megaplan` material under `docs/megaplan_chains/`?
4. If adding `.megaplan/README.md`, what crosslinks should it include?

Return prioritized hazards and exact files that would need updates for any proposed move.
