# M3: Merge Result Closeout

## Outcome

The integrated merge result, not just milestone branches, proves the cleanup is complete. Remaining external cleanup exceptions are closed or converted into explicit follow-up tickets with concrete owners and triggers.

## Scope

In:

- Run post-merge import, CLI, chain, resume, worker, discovery, docs, and wheel conformance on the final integrated checkout.
- Verify no milestone merge resurrected deleted legacy files, old docs, old skills, or aspirational tests.
- Verify local branch/worktree/stash state after the epic.
- Delete the operational `.megaplan-worktrees/native-python-pipelines-completion-thread2` checkout once the external process no longer uses it.
- Verify the old TypeScript Arnold snapshot was archived to `archive/typescript-bot-era` and removed locally, or record the exact push/blocker failure in a follow-up ticket.

Out:

- Do not repair new unrelated failures by loosening gates.
- Do not leave "review later" cleanup buckets unless an external process or remote failure makes deletion impossible in this milestone.

## Done Criteria

- Final integrated checkout passes the clean-break conformance suite.
- `git status` is clean.
- Local Arnold branches/worktrees/stashes have no undecided work.
- External snapshot disposition is complete or blocked by a documented remote/process constraint.
- Ticket `01KVZZ45DAZW9P5H4JA66JWNY3` is linked to this epic or closed by it.
