Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: inspect tracked `.megaplan/ideas/` design notes and decide whether they belong in hidden `.megaplan` or docs.

Use:
- `git ls-files .megaplan/ideas`
- `find .megaplan/ideas -maxdepth 3 -type f`
- `rg -n "frontier-hardening|scratchpad-emitter|oracle-durability|helper-elimination|preserve-roundtrip|in-editor-surface" docs .megaplan tests vibecomfy scripts 2>/dev/null`

Do not edit files.

Questions:
1. Are these user-facing architecture/history docs or internal megaplan inputs?
2. Is there duplication with `docs/megaplan_chains/` or `docs/templates/`?
3. Should they move, be indexed by a README, or stay put?

Return:
- File-by-file or group-by-group classification.
- Move/no-move recommendation.
- Any link updates that would be required if moved.
