# Publish — Commit & Push the Accumulated Cleanup Branch

## Outcome
The accumulated work from M1–M6 on the shared branch is committed and pushed, ready for
a single human review pass, with a top-level summary of what changed and which audit
findings were resolved.

## Scope
1. Verify the working tree is green: full `pytest`, then the CLI smoke commands
   (`workflows list --ready --json`, `port check` on a sample, `doctor`, `runtime
   doctor`).
2. Ensure all M1–M6 changes are committed on the shared branch (this milestone does the
   committing/pushing if the chain ran with per-milestone work uncommitted; if the cloud
   operator loop already pushed after each milestone, this is a final reconciliation).
3. Write/refresh `docs/megaplan_chains/pristine_cleanup/RESULTS.md`: a checklist mapping
   each audit finding (by lens) to its resolution (fixed / deferred / won't-fix +
   reason), plus before/after LOC for the god-files and a count of duplicates removed.
4. Open or update the PR for the shared branch with that summary in the body.

## Locked decisions
- This milestone is **light** — no new feature work, no refactors. Verification,
  bookkeeping, and publish only.
- Do NOT resolve product questions, merge conflicts, or failing tests here. If the tree
  is not green, STOP and surface it — a publish milestone must not paper over breakage.

## Done criteria
- Shared branch pushed; PR exists with the results summary.
- `RESULTS.md` accurately maps audit findings → resolutions.
- `pytest` and CLI smoke are green at the committed HEAD.

## Anti-scope
No code changes beyond what's needed to make the tree commit cleanly. No new findings
addressed here — anything discovered late goes into a follow-up ticket, not this branch.
