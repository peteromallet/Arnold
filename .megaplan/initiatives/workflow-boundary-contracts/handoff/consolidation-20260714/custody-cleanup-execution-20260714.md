# Arnold custody consolidation and approved cleanup execution

Date: 2026-07-14 UTC

## Authority and scope

This execution implements the user's approval in Discord message
`1526612246162309154`. The approval applies only to items explicitly classified
`READY-DELETE` in the prior authoritative inventories:

- `local-inventory.md`
- `cloud-inventory.md`
- `consolidation-plan-and-report.md`
- delegated result `subagent-20260714-124257-a1b920cf/result.md`

Newly discovered or name-ambiguous loose work is retained and reported. A safe
deletion refusal or changed unique-work signal stops that item; it does not
authorize force deletion.

## Preservation receipts

Original dirty checkout `/workspace/arnold`:

- original HEAD: `612b139971e1a65d2a40f9e387a5e8ff3e2ab960`
- checkpoint ref: `checkpoint/original-dirty-custody-20260714T153807Z`
- checkpoint commit: `aeb1ea35bf3754647d813134a595e3cb95e4bcac`
- checkpoint tree: `c1f2fb84cc30483879bc514370745165e45472ff`
- status SHA-256 before/after:
  `d14aa4302e47cc58c8767dc3bdc137e85a33fe8c36fc5053941def3fac6c9c75`
- index SHA-256 before/after:
  `9ded954d203dd68815138ef707216c55f6e644a43863cca7c97fed5705b79bde`
- binary diff SHA-256 before/after:
  `6ffd6e749bd87d5ab65de490151109901b55a38b68d33e9bc1ff642ed84c3f76`
- 244-path payload tar SHA-256 before/after:
  `b8549e9c78a43f60a74273ade53d7ca9f6113989726c52204d65c2f6ab76e587`
- recoverability: pushed remote checkpoint ref plus local Git bundle and payload
  tar under `/workspace/.megaplan/consolidation-evidence/`.

Canonical runtime checkout `/workspace/arnold-consolidation-20260714`:

- HEAD: `1fc545cc0c95c933a88fbf5b2556b479d76a31bd`
- tree: `800fa69fe7d5c0feb9b2df9c3cd1d35f5f3db095`
- clean status SHA-256 before/after:
  `9dd9311238f2e919e051220b0452cc033e4ed6b616c384868899d13e00e94e8d`
- tree listing SHA-256:
  `7bb27de71fc76f6b14955ba3e451adc7c7bd65b1f428271ecb74556c93d8fb58`
- bundle SHA-256:
  `7d0e27cd7231d1f91fb9c8093c91c3139a09ec3b5386fbde2792bd4f91ed0bf0`
- remote containment: `1fc545c` is an ancestor of base
  `616d5bb839779d20ea8d2bc9ebdd24de31d0234c`.

## Reconciliation strategy

1. Start from the fetched remote-main base `616d5bb839779d20ea8d2bc9ebdd24de31d0234c`.
2. Merge the protected dirty-checkpoint commit with full ancestry so conflicts
   expose both sides instead of silently replacing either tree.
3. Keep current main/runtime contracts for WBC, Run Authority, fail-closed
   custody, request summaries, schema projections, strategy migrations, ticket
   relations, and execution binding unless the dirty side is a demonstrably
   newer compatible extension.
4. Retain dirty-only source, tests, planning/control-plane assets, CI, wrappers,
   migrations, and documentation. Do not promote broken external symlinks,
   embedded Git repositories, AppleDouble/cache files, generated telemetry,
   logs, or scratch fan-out directories as product source; those remain
   recoverable in the checkpoint/tar.
5. Run focused tests for each conflict cluster, then the broad practical suite.
6. Re-fetch before push. If remote main moved, integrate it and rerun affected
   tests. Push only a tested descendant of the then-current remote main.
7. Rebind the editable install, ordinary imports, and resident runtime to one
   checkout at the exact landed revision; require provenance `ok=true`.

## Retention invariants

- Keep `/workspace/arnold` and its reconciled payload.
- Keep canonical runtime until replacement is proven.
- Keep active/draft and paused chain workspaces and all live tmux sessions.
- Keep the three named Reigh workspaces and their Reigh stash until that work
  lands in Reigh; never merge it into Arnold.
- Keep protected/default branches and any newly discovered candidate.
- Codespaces remain unknown and untouched because scope is unavailable.

## Approved deletion execution

After landing and runtime proof, process only exact `READY-DELETE` rows from the
two authoritative inventories. Use `git branch -d` only, remove worktrees only
when their current payload still matches the approved evidence, drop stashes
one at a time by exact current identity, and remove directories only after
rechecking repository identity, live ownership, status, and remote containment.
Do not use stash clear, `-D`, reflog expiry, `gc --prune=now`, reset hard, broad
force removal, or any deletion that could touch a live session.

## Final evidence

The completed result must record commands/results, final commit and remote SHA,
runtime/import paths, focused and broad tests, exact deletion names/counts,
retained/new items, refusals, and whether dirty checkout, remote main, and
runtime converge to one revision.
