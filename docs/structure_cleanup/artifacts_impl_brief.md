Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Implement the safe `artifacts/` cleanup batch. You may edit files.

Scope:

1. Create `docs/api/` with a README.
2. Move `artifacts/m6-public-api.md` to `docs/api/m6-public-api.md`.
3. Move orphaned milestone/audit docs:
   - `artifacts/m1-step1-audit.md` -> `docs/audits/m1-step1-audit.md`
   - `artifacts/m2-diff-hygiene.md` -> `docs/audits/m2-diff-hygiene.md`
4. Update references to the moved paths in tracked docs:
   - `README.md`
   - `CLAUDE.md`
   - `docs/historical/*.md`
   - `docs/megaplan_chains/**/*.md`
   - any other tracked markdown found by searching.
5. Add a small `artifacts/README.md` explaining the remaining directory is
   historical generated baseline/review evidence, not runtime output.
6. Update `docs/structure_cleanup/status.md` with a concise note for this layer.

Do not:

- Move or delete anything under `out/`.
- Move `artifacts/m1-safety-gate.md`, `artifacts/m2-symbol-map.md`,
  `artifacts/m4/`, `artifacts/m5_*`, or `artifacts/m5a-*`.
- Rewrite unrelated docs.
- Run a full test suite.

Verification to perform:

```bash
rg -n "artifacts/m6-public-api|artifacts/m1-step1-audit|artifacts/m2-diff-hygiene" README.md CLAUDE.md docs artifacts
python -m vibecomfy.cli workflows list --ready --json >/tmp/vibecomfy_ready.json
```

Return a concise summary of files changed and verification output.
