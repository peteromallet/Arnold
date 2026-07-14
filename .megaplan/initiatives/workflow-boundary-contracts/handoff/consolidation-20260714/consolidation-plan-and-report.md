# Arnold consolidation and runtime activation

Date: 2026-07-14 UTC

## Outcome contract

This is the durable four-phase consolidation record for Workflow Boundary
Contracts and the Arnold loose-work estate. The exact post-push SHA and live
activation receipts are written after landing to
`/workspace/.megaplan/consolidation-evidence/arnold-20260714/` so the evidence
can name the commit that contains this report without a self-referential Git
commit.

No discovered branch, ref, worktree, stash, clone, workspace, volume,
Codespace, or source payload is to be deleted by this run. Deletion verdicts
are recommendations for explicit user approval only.

## Phase 1 — protect and inventory

The live checkout began at `612b139971e1a65d2a40f9e387a5e8ff3e2ab960`
with 78 tracked and 155 untracked paths. An alternate-index checkpoint was
created without changing its index or worktree:

- ref: `checkpoint/local-main-dirty-consolidation-20260714T124424Z`
- commit: `8dc3693b74115f76ce1291651c374a46bfaa56af`
- tree: `cf5058e50131a7491c5ecb3429c1188e8cafa8f6`
- status SHA-256 before and after: `b31c957c...` (identical)
- diff SHA-256: `bbeee07f...`

The source and target were re-fetched without pruning:

- target: `origin/main` at inventory time,
  `7644f55dd9be75632670f990268e045d3ee1c2f7`
- source: `cbe69337d6f469fd7ae12f1fd0a51007d93b5d70`
- merge base: `432760d13abb69a32a77e7bb1e79c1136d4ce533`
- unique source commits: 5; real textual conflicts: 35

Coverage and item-by-item verdicts are in [local-inventory.md](local-inventory.md)
and [cloud-inventory.md](cloud-inventory.md). They cover the primary checkout,
all local and remote refs, PR heads, registered and unregistered worktrees,
stashes, interrupted-operation metadata, detached/unreachable objects,
submodules and nested repositories, sibling clones, 95 reachable Git
workspace paths on AgentBox, live tmux ownership, other repositories, and the
Codespaces API gate.

## Phase 2 — decisive classification

Useful units selected for landing:

1. WBC C1/S2/S3/S4 contracts, fixtures, evidence, recovery verification, and
   cloud/PR integration from `cbe69337d6f4`.
2. The 12-commit supervisor/runtime umbrella ending at `405eb641b0d4`.
3. Schema-derived fail-closed gate contracts ending at `790fa2583861`.
4. Atomic transaction/event projections ending at `9c3bb63ece9b`.
5. Resident semantic correlation already represented by the newer umbrella
   implementation (`c501c6a660`); the earlier local patch became empty.
6. The direct Grok API demo/tests, preserving the newer existing script.
7. The unique review-gated SuperFixer episode module/tests, byte-identical to
   the only discovered source copies.
8. A selective 102-file port from the protected dirty checkpoint: resident
   commands and scheduled provenance, managed-agent custody, cloud audit and
   human-review controllers, repair-trigger L3 custody, ticket/epic relation
   storage, packaging/CI, migrations, tests, documentation, and durable
   initiative artifacts.

Rejected as superseded or non-product payload, while remaining preserved in
their source/checkpoint locations: broken absolute symlinks, nested gitlinks,
AppleDouble files, generated logs, scratch fan-outs, stale ledger projections,
failed/intermediate stash trees, and older semantic implementations. Large
patch mismatch alone was not treated as unique value: every orphan was checked
against later reachable semantic successors.

The VP special-request todos remain pending. The exact audited six-milestone
vendor-locked WBC launch identity was not proven, and the sequential-model
fallback prerequisite has not been rebased/preflighted/launched.

## Phase 3 — consolidation judgments

The WBC merge is `24afce006b9ad20391ac7af10ef67ea0b1774f9f` with
exact parents `7644f55dd9be...` and `cbe69337d6f4...`. Main's newer six-milestone
chain specification, RunAuthority proof hashes, and fail-closed durable-custody
semantics won where the source carried an older fork. Product contracts,
fixtures, and tests were unioned. The incident ledger was losslessly deduped,
chronologically resequenced to 513 unique events, then deterministically
rebuilt. Full details are in [wbc-merge-evidence.md](wbc-merge-evidence.md).

The dirty checkpoint was applied three-way, then scratch and broken-link paths
were excluded. Conflicts retained the supervisor umbrella's dedicated Python
runtime and stronger recovery-verification contract while adding the dirty
branch's L3 repair trigger, human diagnostics, resident command set, and
managed launch custody. Integration testing found and fixed four cross-lineage
gaps: identity-free attempt ownership, terminal receipt closure, chronological
duplicate request ownership/request-filter shadowing, and repo-local chain
visibility when the machine-wide snapshot describes another workspace.

## Phase 4 — verification and activation

Pre-layer WBC evidence:

- compileall and diff-check: pass
- WBC focused suite: 1,799 passed in 17.15 s
- bounded WBC regression suite: 259 passed in 12.85 s
- detached WBC baseline: 892 core tests passed; broader historical branch run
  978 passed / 21 failed, with those custody/watchdog gaps superseded by later
  integrated lineages

Post-layer evidence is recorded in the activation receipt directory after the
final practical suite, remote-main compare-and-push, editable installation,
canonical resident restart, and live import/provenance checks.

Before activation, pip's editable `.pth` incorrectly named the old WBC runtime
mirror at revision `91a33d...`, while ordinary cwd imports and the resident
used `/workspace/arnold` at `612b139...`. The cutover must point both ordinary
imports and `MEGAPLAN_RUNTIME_SRC` to the clean integration checkout at the
exact remote `main` SHA, install it with the repository-supported editable
mechanism, and restart only with
`agentbox services restart agentbox-discord-resident`.

## Approval boundary

Nothing in the READY-DELETE inventories has been deleted or pruned. Active and
paused/protected workspaces remain KEEP even when their code is landed. In
particular, `editible-install` remains KEEP until the active
repository-strategy-roadmap chain no longer names it. Codespaces remain the
only external-fact gap: the current GitHub token receives HTTP 403 and lacks
the `codespace` scope; resolution is `gh auth refresh -h github.com -s
codespace`, followed by a rerun of `gh codespace list`.
