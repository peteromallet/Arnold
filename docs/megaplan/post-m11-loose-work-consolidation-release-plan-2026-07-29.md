# Post-M11 loose-work consolidation and release plan

Date: 2026-07-29

Status: execution-ready specification once this document is committed and
pushed on its protected planning branch. The working copy in the dirty local
checkout is not by itself an authority.

## Outcome

Arnold ends with one permanent development and release line: `main`.

A temporary branch named `release/post-m11-consolidation-20260729` will collect
all completed, valuable loose work after custody M11 finishes. It will be tested,
reviewed, merged into `main`, and then become deletion-ready itself. It is not a
new long-lived trunk.

All other branches, worktrees, runtime candidates, cloud clones, stashes, patch
files, and checkpoints must end in one of three states:

1. their valuable payload is reachable from `main`;
2. they are an explicitly named active future effort; or
3. they are proven redundant or abandoned and are ready for per-item deletion
   approval.

No branch, stash, worktree, cloud workspace, runtime candidate, or directory is
deleted merely because it looks old, clean, or temporary.

## Why cleanup must wait for M11

The active custody run is still the authoritative source of unfinished M11
work:

- checkout:
  `/workspace/custody-control-plane-20260714/Arnold`
- branch:
  `megaplan/custody-control-plane/m11-conformance-and-legacy-retirement`
- current base:
  `consolidate/arnold-runtime-activation-20260714`
- execution runtime:
  `/workspace/.megaplan/engine-runtimes/d6a7b716-execute-projection/venv`
- editable source:
  `/workspace/runtime-candidates/arnold-5bf11d5a5600`
- runtime-fix branch:
  `fix/simple-fixer-durable-runner-exit-20260729`

The M11 checkout and runtime candidate both contain uncommitted work. They must
not be switched, reset, cleaned, stashed, rebased, pruned, or deleted while the
runner is live.

The first cleanup phase is a non-mutating quiescence and checkpoint phase. It
starts only when all of the following are true:

- no M11 operator, chain, model, or repair process is live;
- the last live M11 checkout, runtime, receipt, and process identities have been
  recorded as a candidate closeout checkpoint;
- no repairable failure receipt remains current at that checkpoint;
- the M11 source and runtime-fixer payloads have byte-identical, restorable
  checkpoints.

That checkpoint is not final M11 acceptance. The authoritative M11 acceptance
manifest is generated only after the runtime fixer is landed into the custody
base, that updated base is merged into M11, and the resulting exact SHA/runtime
passes final acceptance again.

## Current risk snapshot

This is a planning snapshot, not a deletion ledger. It must be regenerated after
M11 completes.

### Local machine

- the current `main` checkout is 14 commits ahead and 578 behind `origin/main`;
- it has 87 tracked changes, including separate staged and unstaged layers;
- it has 542 untracked files represented by 90 top-level status records;
- there are 45 local branches and 39 registered worktrees;
- seven worktree registrations are stale;
- three secondary worktrees contain uncommitted payloads;
- there are no local stashes, interrupted operations, submodules, or odd refs;
- 99 patch/original artifacts and 7,129 unreachable Git objects must not be
  pruned before consolidation.

The current local checkout is a payload source, not a release checkout. It must
remain byte-identical until it has been fingerprinted and checkpointed from a
scratch worktree.

### Megaplan cloud machine

- 359 Git checkouts were found under `/workspace`;
- 68 are dirty;
- 43 contain untracked files;
- 16 current branches are ahead of their configured upstream;
- 29 checkouts expose stashes;
- 297 current branches have no upstream;
- one detached M6 recovery checkout has an interrupted merge;
- the active M11 checkout has 88 tracked changes, 67 untracked files, and four
  shared-repository stashes;
- the active runtime candidate has four tracked changes and no upstream;
- `/workspace/arnold` is also dirty and currently serves the resident process.

The machine therefore cannot be cleaned with a bulk branch or directory
deletion. Every dirty or referenced workspace needs a payload and dependency
decision.

Non-Arnold repositories, including Pumpernickel and Reigh workspaces, are
inventory-only context for this Arnold cleanup. They must never be merged into
Arnold or deleted by this plan. They require their own repo-scoped cleanup.

## Canonical lineage

Custody M5A through M11 intentionally land on
`consolidate/arnold-runtime-activation-20260714`. M10 is already merged there,
and the M11 source amendments have also landed there. M11 must first merge back
to that integration line.

The release sequence is:

```text
runtime-fixer payload
        |
        v
custody integration base <--- updated and reaccepted M11 milestone
        |
        +-----------------------------+
                                      |
current origin/main ---> release/post-m11-consolidation-20260729
                                      |
                                      +--- merge custody integration FIRST
                                      +--- reviewed local completed payloads
                                      +--- reviewed cloud completed payloads
                                      +--- durable plans, tickets, tests, evidence
                                      |
                                      v
                                    main
                                      |
                                      v
                     content-addressed runtime promotion
                              and resident cutover
```

Individual custody milestone branches must not be cherry-picked directly to
`main`: their serial integration branch is the custody lineage and contains the
cross-milestone merge decisions.

## Execution plan

### 1. Quiesce, checkpoint, and establish protected leases

Immediately after the live M11 execution becomes quiescent:

1. record the candidate M11 SHA, integration-base SHA, runtime-candidate SHA,
   runtime path, latest receipt IDs, and UTC checkpoint time;
2. prove the M11 processes and tmux session are no longer live;
3. create a protected-state exclusion manifest containing path, canonical
   origin, Git common directory, branch/HEAD, payload hash, dependency owner,
   marker/PID/tmux/`.pth` bindings, lease expiry, and retirement trigger for:
   - the M11 checkout and runtime candidate;
   - the dirty local `main`;
   - `/workspace/arnold`;
   - Superpom and Withings runtime sources;
   - Critique Ledger v2 and the paused critique archive;
   - every other live or marker-bound source;
4. fetch all remotes without changing any checkout;
5. regenerate a versioned machine-readable ledger for:
   - the current local checkout;
   - every registered and unregistered local worktree;
   - every local and remote branch;
   - every stash;
   - every open, draft, closed, and merged PR;
   - every cloud Git checkout;
   - every runtime `.pth`, marker, service, PID, and tmux dependency;
   - every Codespace;
6. redact credentials and secrets from every recorded path, URL, command, and
   artifact;
7. fingerprint staged, unstaged, and untracked payloads separately and prove
   that the current dirty local checkout is byte-identical before and after the
   checkpoint.

The regenerated ledger, not this snapshot, is the authority for per-item
decisions.

Before every later mutation batch, renew the protected leases and fail closed if
any HEAD, payload hash, marker, PID, tmux session, `.pth`, or service dependency
has changed.

### 2. Make exposed work recoverable and prove restoration

Before merging or deleting anything:

1. after byte-identical checkpoint verification, create and push an explicitly
   nonterminal, nonaccepted candidate commit on the existing M11 milestone
   branch; its commit message and ledger row must say that it cannot satisfy
   completion;
2. create and push an actual commit for the runtime-fixer payload on
   `fix/simple-fixer-durable-runner-exit-20260729`;
3. preserve each dirty local worktree independently;
4. preserve each dirty cloud workspace independently;
5. export stash patches and metadata without applying or dropping them;
6. preserve the interrupted M6 merge state and its parents;
7. create both:
   - a verified Git bundle containing every local-only ref and required parent;
   - a second encrypted checkpoint in a different durable location containing
     staged, unstaged, untracked, stash, interrupted-operation, and
     non-Git-suitable evidence manifests;
8. record content hashes for untracked and patch artifacts;
9. assign a recovery ID to every checkpoint, document its restore command, and
   restore-test a sample into an isolated directory;
10. retain checkpoints until at least 30 days after final cleanup acceptance
    and explicit expiry approval.

Checkpoints are safety belts, not final parking places. Every preserved payload
must still receive a land-or-delete verdict.

### 3. Complete the custody lineage

1. merge the runtime-fixer branch into
   `consolidate/arnold-runtime-activation-20260714` through review;
2. merge that updated base into the M11 milestone branch without rewriting the
   active M11 history;
3. resolve overlaps using the M11 acceptance contract as authority;
4. build a fresh content-addressed runtime from that exact post-fixer M11 SHA;
5. run focused M11 and recovery suites, then the declared full acceptance
   command manifest;
6. generate the authoritative M11 completion manifest, proof map, receipts, and
   runtime/source identity from that post-fixer SHA/runtime;
7. reject any pre-fixer manifest as completion evidence;
8. commit and push the final acceptance artifacts as a later acceptance commit
   on top of the explicitly nonaccepted candidate commit;
9. open and merge the M11 milestone PR back to the custody integration branch;
10. verify that no accepted live-runtime change exists only on the Hetzner
    volume.

### 4. Create the one temporary consolidation branch

Create a new clean worktree from the freshly fetched `origin/main` tip and create
`release/post-m11-consolidation-20260729`.

Do not create it from the current dirty local `main`, and do not perform
integration inside an active cloud workspace.

Import completed valuable work in this order:

1. merge the finished custody integration branch as the first reviewed unit,
   preserving its serial merge lineage;
2. resolve the `main`/custody divergence and run custody acceptance before any
   other loose payload is imported;
3. small shared runtime, resident, status, and recovery fixes;
4. M10/M11 follow-up fixes not already patch-equivalent to the custody line;
5. coherent local commits and dirty source/test units;
6. coherent cloud-only commits and dirty source/test units;
7. durable initiative specs, tickets, plans, skills, documentation, fixtures,
   and small redacted Git-suitable evidence;
8. generated artifacts only when they are intentional repository assets.

For overlapping branches:

- land their shared base once;
- compare the remaining deltas by patch ID and content;
- import only the unique intended delta;
- choose the current contract explicitly when tests disagree;
- test and commit after each logical unit.

Never merge a whole dirty checkout as one anonymous snapshot.

### 5. Operate through a resumable inventory and action ledger

The cleanup ledger is versioned and keyed by:

```text
(host, canonical_origin, git_common_dir, checkout_path, object_id, payload_hash)
```

It deduplicates shared repositories, worktrees, and stash stores by Git common
directory and object ID. It also groups byte-identical and strict-subset
payloads while retaining every exact source path.

Each row advances append-only through:

```text
surveyed
  -> checkpointed
  -> classified
  -> ported
  -> validated
  -> approval-ready
  -> deleted
```

Transitions use atomic writes and compare-and-swap against the expected row
hash. Changed rows are rejected and resurveyed; no executor may silently update
its expected target. Work runs in bounded resumable batches with a single
execution lease, stable cursors, UTC timestamps, tool/schema versions, and an
append-only action journal. Partial failures resume from the last proven row.

The ledger and journal must be committed or uploaded to a durable,
remote-reachable, redacted artifact location before they can authorize a
mutation.

### 6. Classify everything else

Every row in the refreshed ledger receives one decisive verdict:

- `merge-then-delete`;
- `cherry-pick-then-delete`;
- `port-then-delete`;
- `delete` with positive redundancy evidence; or
- `keep` with an explicit active dependency and retirement trigger.

`keep` is restricted to:

- a genuinely active service/runtime dependency;
- an open or draft PR that still represents intended work;
- an explicitly staged future effort.

The expected short-term exception list is:

- the Critique Ledger v2 effort while CL2–CL5 remain intentionally unlaunched;
- the Native Parity corrective epic after its milestone-gate bootstrap;
- Native Workflow Platformization, which begins only after Native Parity;
- live Superpom, Withings, and resident runtime sources until each is promoted
  to the merged `main` runtime.

Cancelled predecessor branches, completed milestone heads, dormant runtime
candidates, and historical `editible-install` remnants are not permanent
exceptions.

Every branch comparison uses its true PR/integration base. `main` is never
silently substituted for an epic's actual base. Stashes are classified once per
Git common directory and object ID.

### 7. Test and release to `main`

Before the first import, freeze a validation command manifest containing exact
commands, selectors, working directories, interpreters, environment names,
timeouts, expected exit codes, admitted skips, and artifact paths. A missing
selector, undeclared skip, changed command, or exhausted budget is a failed gate,
not an implicit waiver.

The consolidation branch must pass:

1. focused tests after every imported unit;
2. custody M10/M11 acceptance and recovery regressions;
3. resident, `/whats-cooking`, Superpom, and Withings focused tests;
4. CLI, chain, status, resume, repair, runtime-provenance, and editable-install
   tests;
5. the full practical repository suite;
6. a clean wheel/install smoke test where packaging behavior changed;
7. `git diff --check`;
8. a proof that every claimed completed payload is reachable from the release
   branch.

Then:

1. fetch `origin/main` again and compare-and-swap the expected base SHA;
2. if `main` advanced, merge it immediately and rerun the affected gates;
3. open one reviewed release PR to `main`;
4. merge it using the repository's normal protected-branch policy;
5. tag or otherwise record the exact merged release SHA;
6. verify the release branch contains no uncommitted or untracked source.

### 8. Promote the merged runtime with canary and rollback

After the release PR merges:

1. build a fresh content-addressed runtime candidate from the exact merged
   `main` SHA;
2. validate its source hash, interpreter, editable `.pth`, and dependency set;
3. write a content-addressed pre-cutover binding manifest containing every
   service/marker, old runtime, new runtime, acceptance check, rollback command,
   and abort threshold;
4. canary one non-critical binding first;
5. cut over each remaining service independently through its supported
   custody/resident mechanism;
6. after each cutover, verify its health and installed-runtime provenance;
7. on any failed acceptance or stale heartbeat, stop the batch and restore that
   service's prior content-addressed runtime;
8. verify resident health, `/whats-cooking`, Superpom, Withings, fixer recovery,
   and installed-runtime provenance;
9. rescan every marker, PID, tmux session, service, venv, and `.pth`.

An old checkout or runtime candidate is not deletion-ready while any live
process or marker references it.

Cross-service rebinding is not assumed to be globally atomic. The action journal
records each service transition and makes cutover/rollback resumable.

### 9. Stage cleanup, then request deletion approval

Only after `main` and the promoted runtime contain all accepted work:

1. remove stale worktree metadata;
2. list clean worktrees whose commits are reachable or patch-equivalent;
3. list merged local branches;
4. list merged remote branches;
5. list redundant stashes;
6. list deduplicated `.patch` and `.orig` artifacts;
7. list dormant cloud workspaces and runtime candidates with no dependency;
8. list obsolete draft/closed PRs;
9. list unreachable objects eligible for normal later garbage collection.

Generate content-addressed approval manifests in bounded batches of 20–50 rows.
Every row contains:

- its path or ref;
- canonical origin, object ID, payload hash, and expected current hash;
- user-facing purpose;
- last commit and age;
- true base and ahead/behind counts;
- `git cherry` or equivalent patch-equivalence result;
- linked worktree, stash, PR, marker, runtime, PID, and tmux state;
- what would be lost;
- the positive evidence that makes deletion safe.

The user may approve a whole manifest SHA while excluding named rows. This is
exact per-item approval with usable batch ergonomics: approval binds every
listed target and hash. The executor rejects globs, changed hashes, unlisted
targets, expired leases, or missing dependencies and reports partial failures.
There is no wildcard approval implied by approving this plan.

### 10. Durable artifacts and evidence boundaries

Before execution, this plan must be committed and pushed on a protected planning
branch. The following are also durable, versioned, timestamped, and
remote-reachable:

- source-ref and protected-state manifests;
- inventory/classification ledger;
- checkpoint and restore-test receipts;
- approval manifests and exclusions;
- action and rollback journal;
- validation command manifest and receipts;
- runtime binding manifests;
- final cleanup report.

Git-suitable plans, fixtures, small receipts, and redacted manifests land in the
repository. Bulky or secret-bearing logs remain in encrypted external artifact
storage and are referenced by recovery ID and content hash; secrets never enter
Git.

## Release blockers versus follow-ups

Release-blocking:

- the fixer is merged into the custody base;
- M11 is reaccepted on the post-fixer SHA/runtime;
- the authoritative completion manifest is generated from that exact state;
- the custody integration branch is merged and validated as the first release
  unit;
- every completed payload admitted to the release is reachable and tested;
- the merged `main` runtime passes canary and service cutover checks.

Non-blocking follow-ups are allowed only when the authoritative M11/release
manifest names them explicitly, explains why they do not invalidate acceptance,
and links a durable ticket. The canonical timeline projection and other
post-M11 observability improvements may remain follow-ups under that rule.

The milestone-gate bootstrap and Native Parity corrective epic start only after
M11 is merged to `main` with its validated manifest. Platformization remains
strictly after Native Parity. Critique Ledger v2 remains a separate later
integration line and does not enter this release branch as unfinished
implementation.

## Known first-pass classifications

These are provisional until the post-M11 resurvey.

### Hard keep until ported

- active M11 checkout and its stashes;
- active M11 runtime candidate and pinned runtime;
- `/workspace/arnold` while the resident process uses it;
- Superpom and Withings runtime sources still referenced by live configuration;
- the local dirty `main` payload;
- dirty local worktrees for historical Shannon compatibility, resident
  schedules, and Critique Ledger;
- the interrupted M6 recovery checkout;
- dirty cloud custody, native-parity, maintenance, critique, resident, and
  repair workspaces.

### Strong deletion candidates after proof

The following local branches are already ancestors of the currently cached
`origin/main`, but still require a fresh post-M11 equivalence check and clean
worktree removal:

- `chainfix`
- `consolidate/editible-to-main-20260710`
- `consolidate/loose-work-20260710`
- `consolidate/resident-runtime-20260719`
- `editible-install`
- `fix/hot-context-integration`
- `fix/workflow-cursor-recovery`
- `merge/cloud-checkpoint-20260713`
- `preserve/resident-b923802-20260719`
- `push-editible-mergefix`
- `push-main-mergefix`
- `worktree-watchdog-snapshot-staleness`

The roughly 291 clean cloud checkouts with no current ahead commit are only
probable deletion candidates. Each must still pass dependency, stash,
untracked, true-base, and patch-equivalence checks.

### Explicit supersession

- Critique Ledger accountability v2 supersedes the paused predecessor and draft
  PR #295 after its CL1 handoff is verified;
- completed M10 and M11 source-amendment heads become residue after the custody
  release lands;
- old Run Authority draft PRs #205 and #213 become closeable only when M11's
  retirement manifest proves their responsibilities are covered.

## Final acceptance

Cleanup and release are complete only when:

- `main` contains every accepted completed payload;
- local `main` is clean and matches `origin/main`;
- the temporary release branch is merged and deletion-ready;
- no completed functionality exists only in a worktree, stash, reflog, patch
  file, cloud volume, or runtime candidate;
- no live service uses an old `editible-install` or volume-only source;
- all inactive branches and workspaces have a decisive verdict;
- only the explicit active-effort exception list remains;
- every deletion performed has an approval and a recoverability record;
- every ledger transition and runtime cutover is represented in the durable
  action/rollback journal;
- the final report lists what landed, what was deleted, what remains active,
  and why.

## Safety rules

- no `reset --hard`, `clean`, force worktree removal, or history rewrite on an
  active or dirty checkout;
- no stash drop before its payload is landed or proven redundant;
- no cloud workspace or volume deletion before remote reachability and runtime
  dependency proof;
- no `git gc --prune=now`, reflog expiry, or unreachable-object pruning during
  consolidation;
- no direct push to `main`;
- no release cutover from an uncommitted runtime candidate;
- no change to the current M11 editable install while M11 is running;
- no mutation batch when a protected lease is expired or its expected hash,
  marker, PID, tmux, `.pth`, or service dependency has changed.
