# Post-M11 loose-work consolidation and release plan

Date: 2026-07-29

Decision review: 2026-07-31

Status: decision-complete specification, but not an execution authorization.
Execution requires this exact amended file to be committed and pushed on a
protected planning ref. The working copy in the dirty local checkout is not by
itself an authority.

## Authority, roles, and dated facts

The exact plan commit SHA, this file's Git blob SHA, and the ledger schema
version are recorded in every inventory, checkpoint, approval manifest, action
journal, validation receipt, and runtime binding manifest. Any change to this
plan or to action semantics invalidates outstanding mutation approvals.

Five roles are named by stable actor ID before execution:

- cleanup operator: surveys, checkpoints, integrates, and executes approved
  rows;
- release owner: owns Git lineage, validation, and the final merge decision;
- runtime owner: owns each service cutover and rollback;
- evidence custodian: owns checkpoint storage, encryption keys, restore tests,
  and retention;
- destructive approver: approves exact deletion manifests and cannot be
  inferred from the operator role.

One person may hold several roles, but the cleanup operator cannot
self-authorize a destructive action. Approval of this plan is not deletion
approval.

All paths, branch names, PR numbers, counts, SHAs, process identities, and
classifications dated 2026-07-29 are historical discovery seeds. The refreshed
post-M11 ledger is the sole authority for execution targets. If a named seed is
absent or changed, the operator resurveys it; the operator never recreates the
old ref or silently substitutes a similarly named target.

## Outcome

Arnold ends with one permanent development and release line: `main`.

A temporary branch named
`consolidate/post-m11-<plan-sha12>-<base-sha12>` will collect all completed,
valuable loose work after custody M11 finishes. Its name is generated from the
authoritative plan commit and captured `origin/main` base. If that ref already
exists, execution resumes it only when its ledger identity matches; otherwise
execution fails closed. The branch will be tested, reviewed, merged into `main`,
and then become deletion-ready itself. It is not a new long-lived trunk.

The `consolidate/` namespace is deliberate: `release/*` refs are protected from
cleanup and therefore cannot be used for an intentionally temporary branch.

All other branches, worktrees, runtime candidates, cloud clones, stashes, patch
files, and checkpoints must end in one of three states:

1. their valuable payload is reachable from `main`;
2. they are an explicitly named active future effort; or
3. they are proven redundant or abandoned and are ready for per-item deletion
   approval.

No branch, stash, worktree, cloud workspace, runtime candidate, or directory is
deleted merely because it looks old, clean, or temporary.

## Quiescence gate and historical M11 seed

At the 2026-07-29 snapshot, the active custody run was the authoritative source
of unfinished M11 work:

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

These identities are resurvey seeds, not current execution targets. The
operator resolves the accepted M11 and custody lineage from current PR/merge
receipts, the committed chain manifest, and the acceptance manifest. A deleted
milestone ref is not recreated. Missing or conflicting lineage blocks
execution.

If the resolved M11 checkout or runtime candidate contains uncommitted work, it
must not be switched, reset, cleaned, stashed, rebased, pruned, or deleted while
the runner is live.

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

## Historical risk snapshot

This is a planning snapshot, not a deletion ledger or acceptance input. Every
count and identity must be regenerated after M11 completes.

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

Those names describe the intended graph, not permission to act on a stale ref.
For every source row, the true base is resolved in this order:

1. the current PR's `baseRefName` and exact base SHA;
2. otherwise, the explicit integration ref in the committed epic/chain
   manifest;
3. otherwise, `blocked`.

`main` is never inferred as a missing true base. The ledger records source ref,
source SHA/range, true-base ref/SHA, PR identity, fork point, and accepted
custody owner.

The release sequence is:

```text
runtime-fixer payload
        |
        v
custody integration base <--- updated and reaccepted M11 milestone
        |
        +-----------------------------+
                                      |
current origin/main ---> consolidate/post-m11-<plan-sha12>-<base-sha12>
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

1. record the authoritative plan commit/blob, schema version, role bindings,
   candidate M11 SHA, integration-base SHA, runtime-candidate SHA, runtime path,
   latest receipt IDs, and UTC checkpoint time;
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
   - submodules, tags, notes, replace/original refs, alternates, detached heads,
     interrupted operations, and unreachable objects;
   - every open, draft, closed, and merged PR;
   - fork PR heads, non-origin remotes, sibling variants, and other clones;
   - every cloud Git checkout;
   - every non-Git cloud path and provider volume that contains an Arnold
     workspace;
   - every runtime `.pth`, marker, service, PID, and tmux dependency;
   - every Codespace;
6. redact credentials and secrets from every recorded path, URL, command, and
   artifact;
7. treat the current checkout as immutable input and fingerprint HEAD, the
   complete index including conflict stages, staged, unstaged, untracked, and
   relevant ignored payloads separately, including path type, mode, symlink
   target, size, and content hash;
8. prove that the current dirty local checkout is byte-identical before and
   after checkpointing. No final-acceptance rule authorizes cleaning this
   checkout in place.

The regenerated ledger, not this snapshot, is the authority for per-item
decisions.

The execution lease has a 30-minute TTL, a 60-second heartbeat, an owner ID, and
a monotonically increasing fencing token. Expiry alone never permits takeover:
the successor must resurvey protected resources, prove the prior process is
dead, reconcile any unknown action outcome, and acquire a new token.

Immediately before each mutation, the executor revalidates the target's exact
old ref/content/volume identity and every marker, PID, tmux session, `.pth`,
mount, PR, or service dependency named by its row. A changed target fails
closed. Ledger compare-and-swap is necessary but is never sufficient authority
for a real-world mutation.

### 2. Make exposed work recoverable and prove restoration

Before classification or integration, perform only checkpoint and restore work:

1. preserve each dirty local worktree independently;
2. preserve each dirty cloud workspace independently;
3. preserve each stash by immutable stash commit and all parent IDs, complete
   trees, modes, binary/staged/untracked payloads, and base identity; export a
   human-readable patch only as supplemental evidence, without applying or
   dropping the stash;
4. preserve the interrupted M6 merge's HEAD, operation marker files, complete
   conflict-stage index, worktree payload, merge message, and parents;
5. create both:
   - a verified Git bundle containing every local-only ref and required parent;
   - a second encrypted checkpoint in a different durable location containing
     staged, unstaged, untracked, stash, interrupted-operation, and
     non-Git-suitable evidence manifests;
6. record content hashes for untracked and patch artifacts;
7. assign a recovery ID, immutable content hash, storage URI,
   encryption/key-custodian record, manifest, and restore command to every
   checkpoint;
8. restore-test every unique dirty-worktree payload, relevant ignored or
   untracked payload, stash, interrupted operation, cloud-only payload, and
   runtime-evidence class into an isolated location and compare source and
   restored hashes. Clean refs already present in the verified Git bundle do
   not each need an independent full restore;
9. retain checkpoints until at least 30 days after final cleanup acceptance,
   while any linked `keep` exception remains open, and until a separate
   content-addressed expiry manifest receives destructive approval.

Checkpoints are safety belts, not final parking places. Every preserved payload
must still receive a land-or-delete verdict.

The shared Hetzner provider volume is not a deletion target under this
Arnold-only plan. Any volume containing a non-Arnold repository or any unknown
path is out of scope for destruction. Only exact Arnold workspace paths may
become deletion rows. Provider-volume destruction requires a separate
volume-wide plan, inventory, restore-tested snapshot, and approval from every
affected repository/data owner.

### 3. Operate through a resumable inventory and action ledger

The cleanup ledger is versioned and separates:

- repository stores;
- checkouts/worktrees;
- refs;
- stashes and their immutable commit/parent IDs;
- PR heads, including fork repository identity;
- content-manifest payloads;
- runtimes, services, processes, mounts, and other dependencies.

Stable entity IDs use host identity, canonical origin set, normalized real path
or immutable external identifier, entity kind, and Git common-directory/store
identity. Mutable object IDs and payload hashes are row revisions, not entity
identity. Aliases and shared stores are explicit links, not duplicate rows. A
store-level deletion is forbidden while any checkout, ref, stash, PR,
alternate, process, runtime, or other dependency links to it.

A payload hash is SHA-256 over a canonical sorted manifest of paths, path types,
modes, symlink targets, sizes, and content hashes, with staged, unstaged,
untracked, relevant ignored, and conflict-stage content represented
separately. Byte-identical and strict-subset relationships may share
classification evidence, but every exact source path remains an independent
mutation target.

Each entity advances append-only through one of three explicit paths:

```text
surveyed -> checkpointed -> classified

LAND:
  classified -> ported -> unit-validated -> release-reachable
    -> approval-ready -> source-deleted

DELETE:
  classified -> redundancy-validated -> approval-ready -> deleted

KEEP:
  classified -> kept -> resurvey-due -> surveyed
```

Any state may enter `blocked`, `failed`, or `quarantined`; approvals may enter
`expired` or `rejected`. No row with one of those states may authorize a
mutation.

Transitions use atomic writes and compare-and-swap against the expected row
revision. Every external action has a stable action ID, fencing token,
precondition, and postcondition probe. A mutation is complete only after its
postcondition is observed and journaled. If the process crashes after the
external effect but before journaling, the row becomes `quarantined`; the
executor reconciles the real target before retrying and reuses the same action
ID. It never repeats an irreversible operation blindly.

Work runs in bounded resumable batches with a single execution lease, stable
cursors, UTC timestamps, tool/schema versions, and an append-only action
journal. Partial failures stop the unexecuted remainder and resume from the
last reconciled row.

The ledger and journal must be committed or uploaded to a durable,
remote-reachable, redacted artifact location before they can authorize a
mutation.

### 4. Classify everything

Every row in the refreshed ledger receives one decisive verdict:

- `LAND` with `merge-range`, `cherry-pick-shas`, or `port-paths`;
- `DELETE` with positive redundancy evidence; or
- `KEEP` with an explicit active dependency and retirement trigger.

`DELETE` requires all of:

- every payload is reachable from the accepted target or proven byte/patch
  equivalent against its true base;
- no unique staged, unstaged, untracked, ignored, stash, interrupted-operation,
  or patch payload remains;
- no open/draft PR, worktree pin, alternate, marker, process, runtime, mount, or
  service dependency remains;
- the exact target revision was revalidated immediately before mutation.

Age, cleanliness, a merged PR, ancestry, or `git cherry +0` is supporting
evidence, never sufficient by itself.

`KEEP` is restricted to:

- a genuinely active service/runtime dependency;
- an open or draft PR that still represents intended work;
- an interrupted operation;
- a protected ref;
- an explicitly active future effort that is not yet ready to land.

Every `KEEP` row names an owner, user-facing purpose, current dependency, next
action, retirement trigger, and `review_at` no more than 30 days away. An
ownerless or unreviewed item cannot qualify as an active exception. Expiry
causes resurvey and reclassification, never automatic deletion.

The expected short-term exception candidates are:

- the Critique Ledger v2 effort while CL2–CL5 remain intentionally unlaunched;
- the Native Parity corrective epic after its milestone-gate bootstrap;
- Native Workflow Platformization, which begins only after Native Parity;
- live Superpom, Withings, and resident runtime sources until each is promoted
  to the merged `main` runtime.

Each candidate becomes `KEEP` only if the refreshed ledger supplies the required
owner, dependency, next action, retirement trigger, and review date. Otherwise
it receives `LAND`, `DELETE`, or `blocked`; the dated list grants no exception
by itself.

Cancelled predecessor branches, completed milestone heads, dormant runtime
candidates, and historical `editible-install` remnants are not permanent
exceptions.

Supersession is proven only when the replacement is reachable from the accepted
true base/target, covers the predecessor's user-facing behavior and required
tests/evidence, and leaves no unique intended delta. Otherwise the unique delta
lands or the predecessor remains `KEEP`.

Every branch comparison uses its true PR/integration base. `main` is never
silently substituted for an epic's actual base. Stashes are classified by
immutable stash and parent commit IDs, never by unstable `stash@{N}` ordinals.
There are no `uncertain` final rows: unresolved lineage or evidence is
`blocked` until the specified investigation closes it.

Before importing anything, publish the complete classification table and
ordered integration strategy, then obtain explicit user authorization to
execute that strategy. This is the Phase 2-to-Phase 3 decision gate; it does not
authorize any deletion. The gate binds the exact plan/blob SHA, ledger/schema
SHA, action IDs, source and destination identities, approver, timestamp, and
seven-day expiry. Any bound change requires a refreshed gate.

### 5. Freeze validation and complete the custody lineage

Before creating source commits or merging anything, freeze a validation command
manifest containing exact commands, selectors, working directories,
interpreters, environment names, dependency/image digests, timeouts, phase
budgets, expected exit codes, admitted skips, owners, and artifact paths. Record
its schema and artifact SHA. A missing selector, undeclared skip, changed
command, or exhausted budget is a failed gate, not an implicit waiver. Values
are regenerated and then frozen; this dated plan does not freeze current command
or timing facts.

Then:

1. if and only if the classified ledger proves the authoritative M11 payload is
   still uncommitted, create and push an explicitly nonterminal, nonaccepted
   candidate commit on the resolved M11 source branch; its commit message and
   ledger row must say that it cannot satisfy completion. Do not manufacture a
   replacement for a deleted or already-merged milestone ref;
2. resolve the runtime-fixer payload and source ref. If it is still uncommitted,
   create and push an actual commit on that resolved ref; if it is already
   pushed or merged, record the existing full commit and do not create a
   duplicate. The historical
   `fix/simple-fixer-durable-runner-exit-20260729` name is only a seed;
3. resolve the exact runtime-fixer commit, M11 source, and custody integration
   ref from current receipts and the refreshed ledger;
4. merge the fixer commit into the custody integration ref through review if
   it is not already reachable there;
5. if the resolved M11 source still contains unique intended payload, merge the
   updated integration base into it without rewriting history. If the M11 ref
   was deleted after a recorded merge, verify the merge receipt and exact tree
   instead of recreating the ref;
6. resolve overlaps using the M11 acceptance contract as authority;
7. build a fresh content-addressed runtime from that exact post-fixer M11 SHA;
8. run focused M11 and recovery suites, then the frozen full acceptance command
   manifest;
9. generate the authoritative M11 completion manifest, proof map, receipts, and
   runtime/source identity from that post-fixer SHA/runtime;
10. reject any pre-fixer manifest as completion evidence;
11. commit and push the final acceptance artifacts as a later acceptance commit
    on top of the explicitly nonaccepted candidate commit when item 1 created
    one, or on top of the resolved accepted source history otherwise;
12. open and merge the M11 milestone PR back to the custody integration branch
    when a live milestone ref remains; otherwise verify the recorded merge
    result;
13. verify that no accepted live-runtime change exists only on the Hetzner
    volume.

The action journal records the full fixer commit, accepted M11 commit,
M11-to-integration merge result, integration-to-consolidation merge result,
final `main` merge commit, and runtime digest. Acceptance applies to an exact
tree. Any later merge that changes that tree invalidates the earlier acceptance
for release purposes and requires the frozen acceptance manifest to run again
against the new merge result.

### 6. Create the one temporary consolidation branch

Create a new clean worktree from the freshly fetched `origin/main` tip and create
`consolidate/post-m11-<plan-sha12>-<base-sha12>`.

Do not create it from the current dirty local `main`, and do not perform
integration inside an active cloud workspace.

### 7. Integrate all classified `LAND` rows

Import work in this order:

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

Every `LAND` row declares exactly one integration action:

- `merge-range` for an authoritative serial integration branch or a coherent
  independent branch whose history should be preserved;
- `cherry-pick-shas` for unique top-layer commits from a stacked branch or
  post-squash residual;
- `port-paths` for mixed, dirty, or partially superseded payloads.

Each action names exact source/base SHAs or selected path hashes and its
patch-equivalence evidence. Existing source, custody, and consolidation refs
are never rebased or force-pushed during this cleanup. A changed
base is merged append-only.

Dirty payloads are grouped into named source/test/fixture/documentation units.
Raw outputs, caches, credentials, and regenerated artifacts are excluded unless
the ledger explicitly classifies them as repository assets. Selected units are
materialized and committed from an isolated source worktree; the live dirty
checkout is never altered as an import mechanism.

### 8. Test and release to `main`

The consolidation branch must pass:

1. focused tests after every imported unit;
2. custody M10/M11 acceptance and recovery regressions;
3. resident, `/whats-cooking`, Superpom, and Withings focused tests;
4. CLI, chain, status, resume, repair, runtime-provenance, and editable-install
   tests;
5. the named repository-wide suites in the frozen command manifest;
6. a clean wheel/install smoke test where packaging behavior changed;
7. `git diff --check`;
8. a proof that every claimed completed payload is reachable from the
   consolidation branch.

Then:

1. fetch `origin/main` again and compare-and-swap the expected base SHA;
2. if `main` advanced, stop, merge the new tip append-only, rerun the entire
   frozen validation manifest, regenerate SHA-bound receipts, and renew review;
3. open one reviewed release PR to `main`;
4. capture required checks, approval count, stale-review dismissal, merge queue,
   and allowed merge method, then merge only when approvals and checks bind the
   exact PR head SHA;
5. create an immutable annotated tag
   `post-m11-consolidation-<final-main-sha12>` on the exact final `main` merge
   commit and record the tag object, peeled commit, and runtime-manifest SHA;
6. verify the consolidation branch contains no uncommitted or untracked source.

Validation failures stop the affected import and all dependents. Integration
failures are fixed and rerun. Infrastructure failures may be retried under the
same frozen command. A baseline exception requires an owner, exact failure,
durable ticket, expiry, and proof that no release blocker is waived. No
release-blocking acceptance, provenance, recovery, packaging, or runtime
failure may be waived.

### 9. Promote the merged runtime with canary and rollback

After the release PR merges:

1. build a fresh content-addressed runtime candidate from the exact merged
   `main` SHA;
2. validate its source hash, interpreter, editable `.pth`, and dependency set;
3. write a content-addressed pre-cutover binding manifest containing every
   service/marker, old runtime, new runtime, acceptance check, rollback command,
   persistent-data compatibility rule, observation window, and abort threshold;
4. restore-test each service's rollback binding in isolation, then canary one
   non-critical binding first;
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

The canary must remain healthy for at least 10 continuous minutes and three
expected heartbeat/probe cycles, whichever is longer. Any critical probe
failure, runtime/source provenance mismatch, or two consecutive missed expected
heartbeats aborts the batch and triggers rollback. Rollback is successful only
after the old immutable runtime identity and the full service probe set are
verified. Old runtime bindings remain checkpointed and available for at least
24 hours after the last successful cutover and one subsequent scheduled
watchdog/auditor cycle.

Cross-service rebinding is not assumed to be globally atomic. The action journal
records each service transition and makes cutover/rollback resumable.

### 10. Stage cleanup, then request deletion approval

Only after `main` and the promoted runtime contain all accepted work:

1. identify stale worktree metadata and prove the referenced path is absent;
2. list clean worktrees whose commits are reachable or patch-equivalent;
3. list merged local branches;
4. list merged remote branches;
5. list redundant stashes;
6. list deduplicated `.patch` and `.orig` artifacts;
7. list dormant cloud workspaces and runtime candidates with no dependency;
8. list obsolete draft/closed PRs;
9. list unreachable objects eligible for normal later garbage collection.

Approved actions execute lowest blast-radius first:

1. remove a clean, checkpointed worktree or stale registration;
2. delete its approved local ref;
3. delete its approved remote ref;
4. separately delete approved stashes and patch/original artifacts;
5. stop (`down`) an approved dormant Arnold cloud workspace;
6. delete an approved exact Arnold workspace directory or Codespace;
7. leave shared Git stores, provider volumes, tags, odd refs, reflogs, and
   unreachable objects intact for their separately scoped retention review.

Branch, worktree, stash, workspace, Codespace, and GC approvals never cascade
into one another.

Generate content-addressed approval manifests containing at most 25 rows from
one host and one action class. A filesystem directory, cloud workspace,
Codespace, runtime, stash store, or any other non-ref target receives its own
one-row manifest. The shared provider volume is never a target.
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
listed target and hash. Approval also binds the authoritative plan/blob SHA,
ledger/schema SHA, proposed action, destination/new SHA when applicable,
approver, timestamp, and expiry. It expires after seven calendar days or
immediately when any target hash, recommendation, destination, dependency,
marker, process, PR state, lease, or manifest changes.

Immediately before action, the executor rechecks the target-level fencing token
and precondition. It rejects globs, changed hashes, unlisted targets, expired
approvals or leases, and missing dependencies. Each successful row is journaled
before the next starts. A partial failure stops the unexecuted remainder; it
does not blindly retry or attempt to undo irreversible completed deletions.
After reconciliation, remaining rows require a fresh manifest if any bound
state changed.

There is no wildcard or conversational-default approval implied by approving
this plan. Approval is never renewed implicitly.

### 11. Durable artifacts and evidence boundaries

Before execution, this plan must be committed and pushed on a protected planning
ref. Its commit and blob SHAs bind every downstream artifact. The following are
also durable, versioned, timestamped, and remote-reachable:

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

Secret inventory records secret-manager reference/version and consumer
identity, never secret values. Command lines, environment captures, logs,
archives, and volume manifests are scanned before publication. Encrypted
recovery material names its key custodian and key-retrieval procedure. Before a
secret-bearing source is deleted, the runtime owner rotates or revokes the
credential where deletion would otherwise remove the only trusted copy.

## Release blockers versus follow-ups

Release-blocking:

- the fixer is merged into the custody base;
- M11 is reaccepted on the post-fixer SHA/runtime;
- the authoritative completion manifest is generated from that exact state;
- the custody integration branch is merged and validated as the first release
  unit;
- every refreshed-ledger `LAND` payload is reachable from the exact final
  branch head and has its declared validation receipt;
- the merged `main` runtime passes canary and service cutover checks.

Non-blocking follow-ups are allowed only when the authoritative M11/release
manifest names them explicitly, explains why they do not invalidate acceptance,
and links a durable ticket. The canonical timeline projection and other
post-M11 observability improvements may remain follow-ups under that rule.

The milestone-gate bootstrap and Native Parity corrective epic start only after
M11 is merged to `main` with its validated manifest. Platformization remains
strictly after Native Parity. Critique Ledger v2 remains a separate later
integration line and does not enter this consolidation branch as unfinished
implementation.

## Historical investigation seeds, not classifications

The 2026-07-29 survey identified the active M11/runtime sources, dirty local
`main`, interrupted M6 recovery state, live resident/Superpom/Withings sources,
Critique Ledger work, completed custody milestone heads, old Run Authority
drafts, and hundreds of cloud checkouts as investigation areas.

The decision is that none of those dated rows is `KEEP`, `DELETE`, or `LAND`
merely because it appeared in that survey. The refreshed ledger is the only
classification table. It must rediscover the items, bind their current
identities, and apply the decision policy in section 4.

The known supersession questions remain:

- whether Critique Ledger accountability v2 fully covers the paused predecessor
  and draft PR after the landed CL1 handoff;
- whether completed M10/M11 source-amendment heads contain any intended delta
  not present in the accepted custody integration result;
- whether M11's retirement evidence fully covers the responsibilities in the
  old Run Authority drafts.

Each question receives a current evidence-backed verdict before any related
source becomes approval-ready. No old branch list or checkout count is carried
forward as deletion authority.

## Final acceptance

The frozen validation manifest includes a `final_acceptance` validator with
`release` and `cleanup` modes. `release` mode verifies the exact final `main`
SHA, all `LAND` reachability, tag/runtime/receipt bindings, clean canonical
worktree, protected status of the original dirty checkout, and cutover/rollback
receipts. `cleanup` mode additionally verifies zero prohibited ledger states,
current `KEEP` ownership/review fields, approvals, deletion postconditions, and
tombstones. Each mode exits nonzero on any failed predicate and emits a
machine-readable receipt bound to the plan, ledger, final `main`, and runtime
SHAs. Narrative reports cannot confer acceptance.

### Release accepted

Release is accepted only when `final_acceptance --mode release` succeeds and:

- exact final `main` contains every ledger `LAND` payload;
- the annotated release tag, final validation receipts, and promoted runtime all
  bind that same final `main` commit;
- the temporary consolidation branch is merged and deletion-ready;
- a newly designated canonical local `main` worktree is clean and matches
  `origin/main`; the pre-existing dirty checkout remains protected until its
  own payload rows are landed or separately approved for deletion;
- canary, service cutover, provenance, health, and rollback checks have passed.

### Cleanup accepted

Cleanup is accepted only when `final_acceptance --mode cleanup` succeeds and:

- no completed functionality exists only in a worktree, stash, reflog, patch
  file, cloud volume, or runtime candidate;
- no live service uses an old `editible-install` or volume-only source;
- all inactive branches and workspaces have a decisive verdict;
- there are zero `blocked`, `failed`, `quarantined`, `uncertain`,
  expired-approval, dirty-consolidation, or unpushed-consolidation rows;
- only current `KEEP` rows with owner, dependency, next action, retirement
  trigger, and review date remain;
- every deletion performed has an approval and a recoverability record;
- every deletion has a verified postcondition and a durable tombstone row;
- every ledger transition and runtime cutover is represented in the durable
  action/rollback journal;
- the final report lists what landed, what was deleted, what remains active,
  and why.

## Safety rules

- no `reset --hard`, `clean`, force worktree removal, or history rewrite on an
  active or dirty checkout;
- no rebase or force-push of any source, custody, or consolidation ref;
- no stash drop before its payload is landed or proven redundant;
- no stash mutation by `stash@{N}` ordinal; bind immutable stash/parent commit
  IDs and approve stash deletion separately from branch deletion;
- no exact cloud-workspace deletion before remote reachability, non-Git payload,
  shared-store, and runtime-dependency proof;
- no destruction of the shared provider volume under this Arnold-only plan;
- no `git gc --prune=now`, reflog expiry, or unreachable-object pruning during
  consolidation;
- no direct push to `main`;
- no release cutover from an uncommitted runtime candidate;
- no change to the current M11 editable install while M11 is running;
- no execution from an uncommitted or blob-mismatched copy of this plan;
- no mutation batch when a protected lease is expired or its expected hash,
  marker, PID, tmux, `.pth`, or service dependency has changed.
