Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: inspect tracked chain specs under `.megaplan/chains/` and compare them with `docs/megaplan_chains/`.

Use:
- `git ls-files .megaplan/chains docs/megaplan_chains`
- `sed -n '1,180p' .megaplan/chains/frontier-hardening.yaml`
- `sed -n '1,180p' .megaplan/chains/scratchpad-emitter.yaml`
- `rg -n "frontier-hardening|scratchpad-emitter|docs/megaplan_chains|\\.megaplan/chains" . docs README.md scripts tests vibecomfy 2>/dev/null`

Do not edit files.

Questions:
1. Are `.megaplan/chains/*.yaml` canonical executable specs, historical specs, or duplicates of docs specs?
2. Would moving them break commands, docs, or tests?
3. Should `.megaplan/chains/` get a README/policy instead of moving files?

Return a clear recommendation and exact references that support it.
