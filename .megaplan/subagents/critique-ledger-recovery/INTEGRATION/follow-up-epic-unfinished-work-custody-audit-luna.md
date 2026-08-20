# Follow-up epic unfinished-work custody audit

Date: 2026-08-02

Auditor: Luna (read-only custody audit; this report is the only created artifact)

## Verdict

**FAIL — custody is directionally correct, and launch fails safely today, but the
epic is not yet a complete or mechanically trustworthy handoff.**

The README, unfinished-work ledger, briefs, chain, and proof map preserve the
broad post-canary work and correctly supersede the original four-change launch
route after independent rejection of T1.5 commit
`9642193a063d91a6be364f2d11a04b221eae30cf`. However:

1. several live or rejected worktrees are absent or only vaguely identified in
   the custody ledger;
2. several accepted labels need scope qualifiers or are now false;
3. the T6.2 launch preconditions authenticate words in files, not the evidence
   and identities those words purport to describe; and
4. one brief asserts that a launch-critical T3.6 release receipt already exists,
   although no such deploy/release receipt exists in the audited evidence.

The current checkout is safe against accidental chain start for a simple
reason: all four top-level epic files audited below are untracked, and the
chain requires the unfinished-work ledger to be tracked. The intended T6.2
handoff, its evidence directory, and the epic evidence directory are also
absent. That is an honest present-day block, not proof that the future launch
gate is sufficient.

## Audited authorities and content identities

| Artifact | SHA-256 | Role |
|---|---|---|
| `ACTIVE_STATE_20260802_1712.md` | `988cc6920af7655a33384fea70c3253ff1d1d39edf53b2a96337e9a27288a344` | Historical active-state snapshot; not a current file-status authority |
| `SEQUENCING/relaunch-cutline-luna-audit.md` | `9f80dac9152bdc10a330bef3244de0b33ea9c5d1be142827be1015e5ac9e76a4` | Cutline audit |
| `SEQUENCING/shortest-safe-relaunch-sol-high-result.md` | `acab5e0d46119eaa0801cb2f0d8b54c430d1da4a1cd04ab5d327bfc3b9faa8a3` | Original sequencing result |
| `INTEGRATION/post-t1-5-fail-shortest-launch-route-luna.md` | `abe9d64aeb0a35f81ec5fa72b804471a2b2307e34210b993163575a7090e2f47` | Current corrected launch-route authority |
| `INTEGRATION/minimal-operational-relaunch-map-sol.md` | `fd1a33ba58566aa126e170643f59a39bca13972e5919d0a338403b50c169312e` | Superseded four-change route; evidence only |
| `INTEGRATION/stage-a-integration-map-sol.md` | `87809fc379846c1de21b6b9d7a79575ac209936a7935445931c3b876bbcbc910` | Partly superseded integration map; evidence only until reconciled |
| `T1.4/incident-stall-notify-exact-implementation-map-luna.md` | `fd83c969cd8c2ffa45819aa5d23d098974bbd2aab2b37259f48f919beada1213` | Counterfactual map based on later-rejected T1.5; evidence only |
| Follow-up `README.md` | `64b9d8db6718d168cad086a2a0fcc554eef966e812207bad2e162ed7f9548e65` | Human route/cutline statement |
| Follow-up `UNFINISHED_WORK.md` | `9d676f83c263cd58393c4ecc036dc3b38fd5a38f26d955ace42856e4dfc3c0cd` | Human custody ledger |
| Follow-up `chain.yaml` | `24c7f5a80f246ede93007589be993dd90741dc723ddaba7266d4ca3d8a842fcc` | Executable milestone ordering and launch preconditions |
| Follow-up `proof-map.json` | `424c974396e311b7170cffc84fd3d8795e156a02db2d4ce16fe57d9fb27cca04` | Planned task-to-proof locations |

The active-state snapshot records older final README and ledger hashes because
those files changed after the snapshot. A new content-addressed handoff is
required after the deltas below; the historic snapshot must not be silently
treated as attesting to the current epic files.

## What is correctly preserved

- The README explicitly makes independently accepted finite-slice T6.2 safe
  canary completion plus stop/expiry the boundary before the follow-up chain.
- It correctly says the original four-commit wording is superseded after the
  independent rejection of `9642193...`, and points to the corrected
  post-T1.5-fail route.
- It correctly removes operational recovery and notification from the canary,
  including their capabilities, GLEKs, credentials, workers, timers, and
  fallbacks.
- F1 inherits the rejected T1.5 capability, real production owner/storage
  work, T1.7, broad T1.8/T1.9, topology retirement, and T1.10.
- F2 inherits T1.1, T1.2, bounded accepted T1.3, generalized T1.4, and T1.6.
- The eight-milestone F1-F8 chain broadly covers the remainder of the 55-task
  master checklist; no entire post-canary milestone family was found missing.
- `UNFINISHED_WORK.md` preserves the rejected `9642193...` candidate and the
  bounded local T1.8 commit `06d41e...`, and it does not claim the rejected
  T1.5 candidate is deployable.

## Missing or imprecise custody

The ledger must preserve each item below by exact path, base/HEAD commit, tree
where committed, index/worktree status or a digest manifest, evidence/report
location, disposition, and acceptance path. A worktree path alone is not a
durable acceptance contract.

| Item | Current exact evidence/location | Defect | Required acceptance path |
|---|---|---|---|
| Host-side cloud observation/preflight | `/private/tmp/arnold-critique-recovery-cloud-observation-preflight-20260802`, HEAD `6787d6363e8fc0603092913ae877db14f3b9fff8`; modified `cloud/cli.py`, `cloud/providers/ssh.py`, `cloud/spec.py`, `cloud/templates/cloud.yaml.tmpl`, `tests/cloud/test_cloud_chain_command.py`; untracked `cloud/providers/ssh_preflight.py`, `tests/cloud/test_ssh_prelaunch_observation.py` | Entire causal prelaunch lane is absent from the ledger. | Independent review must accept lifecycle, mount identity, bytes/inodes, fsync/WAL and reserve proof **before any replacement or other cloud mutation**; bind the accepted commit/tree and receipts in T6.2, or preserve this lane explicitly as rejected/deferred evidence. |
| T1.2 partial contract-bundle lane | `/private/tmp/arnold-critique-recovery-contract-bundles-20260802`, HEAD accepted T1.3 `2f1500aea1d03fbf13df5c796b17bd03d17bb79c`; modified `_core/worker_fanout.py`, `workers/_impl.py`, `workers/hermes.py`; untracked `orchestration/critique_attempts.py` | Ledger says only “preserved partial lane”; it does not identify the worktree or current files. | Review the T1.2 slice independently, integrate through a clean descendant, then prove installed route behavior; otherwise preserve exact diff/status as unfinished. |
| Run-authority containment candidate | `/private/tmp/arnold-critique-recovery-ra-contain-20260802`, commit `48e13e1bcbc6769aff753270331d52ac1c148125`, tree `550421...`, clean | Missing from unfinished custody. Local integration eligibility is not formal T0.0 or installed production authority. | Integrate cleanly, install the exact candidate, and bind an owner-issued production containment decision/revision/fence/receipt in T6.2. |
| T1.1 admission repair | `/private/tmp/arnold-critique-recovery-t1-1-admission-20260802`, HEAD `3ed353f8aa3d0df450c563c3cb8d76c87349e32d`, tree `f6c83...`; 15 modified plus four untracked files (`run_authority/owner_client.py`, `run_authority/conformance_backend.py`, `arnold_run_authority_owner/{__init__.py,endpoint.py}`) = 19 files | Ledger's “16 dirty files” is stale and not reproducible. | Replace the count with a content-addressed status/diff manifest; independent acceptance, clean descendant integration, and installed backend/owner conformance are required. |
| T1.7 storage lane | `/private/tmp/arnold-critique-recovery-t1-7-storage-20260802`, base `6787d...`; 15 staged additions, with `adapters.py`, `models.py`, and `sqlite_owner_store.py` also modified after staging | Path and test count are present, but not the split index/worktree state, exact file manifest, failing test identity, or decision route. | Record staged and unstaged digests separately, exact 79-pass/1-fail command and failing node, repair it, then require independent semantic and installed-wheel acceptance before F1 consumption. |
| T1.10 notification candidate | `/private/tmp/arnold-critique-recovery-notification-ux-20260802`, rejected commit `0c3d662024bc0497ed3979991a20b3b48ecf19cd`, tree `d4c10e...`, clean | Exact rejected lane is omitted even though F1 asks to redo T1.10. | Mark evidence-only / never wholesale integrate; any later notification implementation must be independently rebuilt and accepted after the stable canary. |
| Oversized T1.5 candidate | `/private/tmp/arnold-critique-recovery-simple-fixer-20260802`, current HEAD `939c763ae492a72efdd74941d431045b0f0ea61d`, tree `c788...`, clean | Ledger's size description does not bind the current commit/tree. | Add the exact current identity and rejection/evidence-only disposition; salvage only by independently reviewed narrow reimplementation after canary. |
| Rejected T1.5 pass 3 | `/private/tmp/arnold-critique-recovery-t1-5-operational-pass3-20260802`, `9642193a063d91a6be364f2d11a04b221eae30cf`, tree `27a3d61...`, clean | Correctly named, but supersession is only narrative. | Machine-readable rejection/supersession index; T6.2 must record `NOT_CONSUMED_OPERATIONAL_CANARY` and exact deny receipts. |
| T1.8 bootstrap | `/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`, commit `06d41e6b7148db4e5b464131762d63fd697db056`, tree `a8a67...`, clean | Correctly called bounded, but no exact production acceptance path is bound. | Clean integration plus production adapter/deploy/live installed-vector proof. Local Stage-A acceptance is not cloud-deploy authority. |
| T1.3 contracts | commit `2f1500aea1d03fbf13df5c796b17bd03d17bb79c`, tree `0e060...` at the T1.2 worktree above | “Accepted T1.3” can be misread as complete end-to-end. | Preserve as accepted **Stage-A component only**; require clean descendant integration and installed route proof before operational reliance. |
| T5.1 evidence schema candidate | `/private/tmp/arnold-critique-recovery-t5-1-20260802`, commit `7c254f7f0d15ba4e835a6fe7cae40b47d29ef7cd`, tree `27e7...`, clean; semantic review found four owner decisions outstanding | Entire prelaunch evidence lane is absent. | Resolve all four owner decisions, independently accept replacement, recompute T5.2, and bind T5.3-T5.6 fresh-input/envelope identities in the T6.2 handoff. |
| Prepared T1.4/T1.10 worktree | `/private/tmp/arnold-critique-recovery-incident-stall-notify-20260802`, clean at base `6787d...` | Not harmful, but its empty/prepared status is not distinguished from implemented work. | Record as a no-edit prepared lane or omit it only through an explicit supersession/custody decision. |

## False, stale, or over-broad accepted/complete language

These statements must be corrected in their source or covered by an explicit,
machine-readable supersession manifest consumed by the chain:

1. `T1.4/incident-stall-notify-exact-implementation-map-luna.md:5` calls
   `9642193...` an “accepted T1.5 candidate.” It was later independently
   rejected. The whole map is a counterfactual implementation map, not a valid
   launch instruction.
2. `INTEGRATION/minimal-operational-relaunch-map-sol.md:5` says “four bounded
   code changes,” and lines 20, 77, 98, and 252 depend on accepted T1.5. The
   README narratively supersedes this document, but no manifest prevents tools
   or agents from treating the old route as current.
3. `INTEGRATION/stage-a-integration-map-sol.md:109` and `:151` refer to an
   “accepted T1.10 notification” port and include T1.5/T1.10 positive
   capabilities. Both are invalid for the corrected zero-recovery canary.
4. `briefs/f1-owner-storage-recovery-hardening.md:19` says “The accepted
   Stage-A route.” Only bounded components T1.3 and T1.8 have scoped local
   acceptance; no integrated, installed, stopped-and-fenced Stage-A route has
   been accepted. Say “eventual accepted Stage-A route” or identify only those
   bounded components.
5. `briefs/m5-evidence-and-incident-closeout.md:15` says the launch-critical
   T3.6 release receipt “already exists.” It does not. Change this to a future
   precondition bound to the accepted T6.2 handoff. This is the most serious
   false-complete statement in the follow-up epic itself.
6. Any use of “accepted” for `48e13e...` must say local integration-eligible,
   not T0.0 complete; for `06d41e...`, bounded local Stage-A only, not cloud
   deployment; and for `2f1500...`, accepted Stage-A contract component only,
   not full installed-route closure.

## Stable-canary handoff defects

`chain.yaml:13-47` checks `contains_text` and `git_tracked`. An independently
created acceptance JSON can therefore say `"decision":"accepted"` without
cryptographically binding the handoff it reviewed, and a handoff can contain
the required phrases without possessing the claimed evidence. This is
self-attestation by string presence, not acceptance.

Before F1 may start, the chain must require a committed, content-addressed T6.2
handoff and a separate independent decision that binds the handoff SHA-256 and
all of the following:

- candidate commit/tree, source archive, wheel/image, installed paths,
  wrappers/services, interpreter and `python -P` vector, plus two-observer
  parity;
- run-authority owner revision, advanced epoch/tombstone, selection CAS,
  marker-byte identity, fences, and the owner-installed decision/receipt;
- revocation of every old v2 grant/GLEK/capability before the new process;
- a zero-capability registry and explicit deny receipts for fixer,
  notification, reminders, chunks, diagnostics, resident/watchdog and direct
  fallbacks, with no recovery/notification credential, provider binding,
  worker or timer;
- accepted host-side lifecycle/mount/capacity/inode/fsync/WAL/reserve preflight
  **before** replacement;
- exactly one upload/start/stop sequence, fresh signed envelope, pinned model,
  exact launch and terminal stop/expiry receipts, terminal
  `SUCCEEDED_CLOSED` / `STOPPED_FENCED`, and proof that no live runner, timer or
  worker remains;
- 200 read-only observations with zero provider calls;
- fail-closed treatment of any UNKNOWN or incomplete prior upload/start/stop;
- content-addressed T0.2 and T0.4 manifests; and
- the exact deferred/residual ledger digest.

The handoff's `NOT_CONSUMED_OPERATIONAL_CANARY` set must be exact, not three
free-text phrases. At minimum it must bind T0.3 residue; generalized T1.1;
T1.2; generalized T1.4; T1.5; broad T1.6; T1.7; generalized T1.8/T1.9; T1.10;
T2.2; T2.4; broad T2.5; T2.6; broad T3.5; T3.6 admin closure; and T4.6,
including locations and dispositions. The acceptance validator must reject a
handoff/decision digest mismatch and reject missing, duplicate, or extra
claimed consumed capabilities.

## Proof-map defects

`proof-map.json` mostly names future directories. Those directories currently
do not exist, and the map does not bind current evidence identities,
acceptance decisions, or supersession decisions. Add:

- the T6.2 launch handoff and independent acceptance decision (or a separate
  launch proof map whose digest is bound here);
- exact current source-report/worktree/commit/tree identities from the custody
  table above;
- typed acceptance and supersession manifests, including the rejected T1.5 and
  T1.10 lanes; and
- typed subeffects where one master task appears in multiple milestones. In
  particular, T3.6 release-receipt proof and later T3.6 administrative closure
  must not allow either milestone to imply the whole task is complete.

## Required deltas before this audit can PASS

1. Commit and content-address the epic files after correcting the false T3.6
   and over-broad acceptance wording.
2. Replace the string-only launch checks with schema/identity validation that
   binds an independently accepted T6.2 handoff to its evidence, runtime,
   owner/fence, stop, preflight, zero-capability and deferred-ledger digests.
3. Add the complete exact worktree/commit custody table above to
   `UNFINISHED_WORK.md` or to a content-addressed manifest referenced by it.
4. Add machine-readable rejection/supersession records for the original
   four-change route, the T1.5-dependent T1.4 map, and the T1.5/T1.10-positive
   Stage-A integration text.
5. Bind exact scoped acceptance paths for the run-authority candidate, T1.3,
   T1.8, T1.9, and T5.1-T5.6; do not promote local/spec acceptance to installed
   production completion.
6. Reconcile `proof-map.json` to actual evidence plus typed subeffects and bind
   its digest into the completion contract.
7. Re-run this custody audit against the committed epic, exact handoff and
   independent decision. PASS requires that the chain refuse forged phrase-only
   files and any handoff/decision or evidence-digest mismatch.

F1 and F2 are serialized in `chain.yaml` even though the sequencing result
allowed them to run independently and join at F3. This is conservative and
does not lose custody, so it is not itself a launch blocker; it is an optional
throughput correction after the safety defects above are repaired.

## Final custody judgment

No prior implementation should be deleted or integrated wholesale based on
this epic as written. The corrected route and broad deferred-work partition are
good human guidance, but exact custody and the stable-canary admission contract
remain incomplete. Until the required deltas are independently accepted, the
only truthful state is:

`FOLLOW_UP_EPIC_NOT_ADMITTED / STABLE_CANARY_HANDOFF_ABSENT / NO_CLOUD_MUTATION`
