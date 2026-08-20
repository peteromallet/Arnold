# Pushed follow-up epic custody stability audit

Date: 2026-08-02

Audited worktree:
`/private/tmp/arnold-critique-recovery-follow-up-epic-20260802`

Audited commit: `e32621cab0ba3d7ee30b68eba4e37a86e150ca14`

Audited tree: `645f65d87ac8fbe21f89e68130d603e43f025432`

Mode: read-only custody audit. This report is the only write. No audited file,
Git ref, cloud/provider state, owner state, process, or existing evidence was
mutated.

## Verdict

**FAIL — the logical custody index is now complete and internally consistent,
but the pushed branch is not yet physically self-contained.**

## Exact remaining gaps

### 1. The canonical 55-task source plan is a dangling branch reference

The README names
`docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`
as canonical, but that path does not exist in `e32621c...` and is not tracked on
the main checkout. The current external file SHA-256 is
`edddb198701c7567325aac5827100321addbe9e7c5dd458c1329628e82472e0c`.

All 55 task IDs appear somewhere across the committed epic and frozen recovery
reports, and no ID is absent, but scattered mentions are not a recoverable copy
of the canonical task definitions, dependencies, owners and proof obligations.
Track the exact source plan (or an exact content-addressed archival copy) in the
handoff branch.

### 2. Three dirty lanes are hashed but their bytes are not in durable custody

T1.1, T1.2 and T1.7 have reproducible status, worktree/index diff hashes; T1.1
and T1.2 also have exact untracked path/mode/content hashes. The referenced
bytes still exist only in `/private/tmp` worktrees. The pushed branch contains
no binary patches, untracked-file archive, or Git bundle from which those dirty
snapshots can be reconstructed. A digest detects loss or mutation but cannot
recover the work after a worktree disappears.

Add tracked, content-addressed custody packs for:

- `/private/tmp/arnold-critique-recovery-t1-1-admission-20260802`;
- `/private/tmp/arnold-critique-recovery-contract-bundles-20260802`, preserving
  the T1.2 dirty layer separately from the accepted bounded T1.3 base; and
- `/private/tmp/arnold-critique-recovery-t1-7-storage-20260802`, preserving
  staged and unstaged layers separately.

Each pack must contain the canonical binary index/worktree patches and exact
untracked bytes/modes where present, bind its base commit/tree, and pass a
throwaway reconstruction/hash check.

### 3. Ten referenced candidate commits are not reachable from the pushed handoff

The following unique commits are neither ancestors of `e32621c...` nor
contained by any fetched remote ref:

- `96d368de54876aaaec205290e2640d9daf78f3ea`
- `26aca6ace7f0af3279ca5b311e6983d4904a4d3a`
- `2f1500aea1d03fbf13df5c796b17bd03d17bb79c`
- `48e13e1bcbc6769aff753270331d52ac1c148125`
- `3ed353f8aa3d0df450c563c3cb8d76c87349e32d`
- `0c3d662024bc0497ed3979991a20b3b48ecf19cd`
- `939c763ae492a72efdd74941d431045b0f0ea61d`
- `9642193a063d91a6be364f2d11a04b221eae30cf`
- `06d41e6b7148db4e5b464131762d63fd697db056`
- `7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd`

They are available only through local worktree/object state. Reports, commit
SHAs and tree SHAs do not make the underlying source recoverable from the
pushed follow-up branch. Put the objects in a tracked, hashed Git bundle (or
push durable namespaced refs and bind those refs in custody). The rejected v1
provider and accepted bounded v2 provider identities must both remain; neither
may replace the other.

### 4. The latest stopped-container/ENOSPC observation and its custody split are absent

The newly reported live observation says the old cloud container is stopped and
preserved, the host workspace reports `free_bytes=0`, the stopped-container
mount observation fails with ENOSPC, and the legacy status/preflight CLI still
attempts `docker exec` before lifecycle/capacity classification. No exact,
hashed observation receipt containing those current facts exists in
`e32621c...` or its custody manifest. The older local incident reports are also
untracked and do not substitute for a fresh exact receipt.

Record this as a separate read-only incident/custody item with observation time,
target/container/image/mount identities, command/interface versions, typed
lifecycle/capacity outputs and evidence hashes. Its disposition must split the
work as follows.

Bounded relaunch blockers:

- integrate the accepted bounded provider v2 so status/preflight classifies
  host lifecycle/capacity before any `docker exec` collector path;
- preserve the stopped v2 container/evidence and fence the exact host
  service/unit/timer/restart policy so it cannot resume; and
- obtain a scoped storage-owner cleanup/reclaim decision, bound to an exact
  recoverable cleanup manifest that excludes preserved incident evidence, then
  prove nonzero byte/inode/reserve headroom and issue a fresh expiring
  predeploy receipt. `free_bytes=0` is an unconditional current NO-GO.

Post-relaunch unfinished work:

- platform-wide T1.7 owner-store capacity, WAL/fsync, corruption, crash and
  ENOSPC hardening; and
- broad retention/reserve policy plus real F8 24h/72h/7d durability.

The current proof map assigns all of T0.3 to F1, but the source plan makes safe
capacity restoration precede new effects. Type this split explicitly:
`T0.3/scoped-prelaunch-capacity-reclaim` belongs to the finite-canary admission
receipt, while only `T0.3/platform-capacity-and-storage-hardening` may remain in
F1. Otherwise the current hard NO-GO can be mistaken for post-relaunch debt.

## Checks that pass

- The audited branch is clean, has the stated exact commit/tree, tracks all 15
  epic files, and is synchronized `0/0` with
  `origin/epic/critique-ledger-post-relaunch-completion-20260802`.
- Strict JSON loading finds no duplicate keys. Every evidence/report path named
  by custody exists in `e32621c...`, is Git-tracked, and matches its recorded
  SHA-256.
- The dirty-capture recipe is explicit. All live status/index/worktree hashes,
  untracked inventories, modes and file hashes reproduce. T1.3 explicitly
  shares the T1.2 lane while limiting acceptance to the bounded raw
  target-bound transport component.
- Provider v1 remains rejected evidence; v2 is separately frozen at
  `26aca6a...` / `5503c69...` with author and independent-review hashes and the
  correct bounded-source-only disposition.
- Every registered `/private/tmp/arnold-critique-recovery-*` worktree other
  than the audited handoff itself maps to a custody item; no extra recovery
  worktree was found.
- T3.6 ownership is non-overlapping: F2 owns the release-authority subeffect and
  F7 owns administrative ticket closure. F2 consumes the incident replay as
  input only; F7 alone owns T8.3 completion/publication.
- Proof-map keys exactly match the eight milestone labels. Its 33 entries are
  concrete file paths, not directories or pseudo-milestones. Their future
  absence is expected post-run work and is outside this custody-only verdict.
- The finite-canary implementation and artifacts are explicitly pending. The
  current loader rejects unsupported `finite_canary_receipt`, and the canary
  initiative/receipt is absent, so launch fails closed. This pending executable
  gate is not counted as a custody defect in this pass.

## Pass condition

Track the exact canonical source plan, durable reconstructable custody for the
three dirty snapshots and ten otherwise-unreachable commits, and the exact
current stopped-container/ENOSPC receipt with the typed T0.3 pre/post-relaunch
split above. After those artifacts are pushed and their hashes/reconstruction
are verified, no other custody gap was found in this pass.
