# Unfinished-work custody ledger

This is the mandatory handoff from the bounded Critique Ledger v3 canary into
the post-relaunch completion epic. An item leaves this ledger only through an
independently accepted completion or an explicit supersession record that binds
the replacement evidence. A passing canary does not complete any item below.

## Stable canary boundary

- [ ] The v3 handoff records exact deployed commit/tree/image/source identities.
- [ ] The poisoned v2 generation is fenced and cannot resume or notify.
- [ ] Automatic fixer effects are `DISABLED_FAIL_CLOSED` unless an independently
  accepted production owner proves exact-once semantics.
- [ ] Notification provider effects are `DISABLED_FAIL_CLOSED` unless an
  independently accepted occurrence/version-keyed owner proves dedupe.
- [ ] Recovery/notification capabilities, GLEKs, credentials, workers, timers
  and direct fallbacks are absent from the installed canary profile, with an
  accepted deny-before-mutation proof.
- [ ] Any canary runner failure fences and stops without invoking T1.5/T1.10.
- [ ] The canary is stopped at its declared finite boundary; no background
  wrapper, timer, resident, or watchdog can continue mutating or messaging.
- [ ] Every item below is emitted as `NOT_CONSUMED_OPERATIONAL_CANARY` in the
  T6.2 handoff with its evidence and preserved-work location.

## F1 — owner, storage and recovery root fixes

- [ ] Repair the rejected T1.5 candidate without discarding its valid HMAC
  receipt work. Coordinated deletion or rollback of local projections must
  reread the Run Authority grant/CAS, Custody occurrence/epoch and WBC
  attempt/effect evidence, then return typed UNKNOWN/indeterminate with no
  second attempt or effect when the join is unavailable. Evidence:
  `.megaplan/subagents/critique-ledger-recovery/T1.5/t1-5-operational-pass3-independent-review-luna.md`
  (SHA-256
  `290fcd8b2132b5834c6e6fe961a2640329bfb133eb1acd618f82fed2b3d8d13a`).
- [ ] Implement and deploy the real fixed-socket production recovery adapter;
  the current SQLite adapter is explicitly test-only. It must authenticate and
  consume Run Authority decisions/CAS, Custody occurrence/lease/epoch,
  lifecycle-owned accepted-state/due semantics and WBC intent/outcome evidence;
  it must not issue any of those authorities.
- [ ] Fix exact-occurrence handoff: immediate/reconcile wrappers must receive the
  Custody-issued occurrence ID rather than calling owner operations with zero
  arguments. Preserve the retired four-line watchdog tombstone; do not revive
  diagnostic/Kimi/meta/fallback launchers. Evidence:
  `.megaplan/subagents/critique-ledger-recovery/T1.4/incident-stall-notify-exact-implementation-map-luna.md`
  (SHA-256
  `fd83c969cd8c2ffa45819aa5d23d098974bbd2aab2b37259f48f919beada1213`).
- [ ] Prove notification custody by occurrence ID plus accepted state version:
  restart and 200 unchanged polls produce exactly one intent and at most one
  provider effect; missing
  provenance produces zero provider effects; same-occurrence reconciliation
  cannot mint a new notification key.
### Deferred platform inventory — nonblocking for T6.2 and F3

These items remain owned by the Custody Control Plane M6A-M11 or an explicit
successor receipt. They are not current-r5/T6.2 or enabled-surface F1/F2 gates;
an affected surface remains hard-denied until its item is accepted.

- [ ] Complete generic T1.5 topology and meaningful subject-specific retirement
  proofs for all 28 historical modules / 674 functions / 741 cases.
- [ ] Complete T1.7 owner-local transactional storage, capacity, ENOSPC,
  corruption and crash recovery. Preserved worktree:
  `/private/tmp/arnold-critique-recovery-t1-7-storage-20260802` (79 pass / 1 fail
  at pause; dirty work is evidence, not accepted code).
- [ ] Complete T1.10 notification rotation, reminder/chunk/child-key policy and
  auxiliary-writer retirement.

## F1 category hardening (blocking before F2)

The durable mapping is [`evidence/p2-control-plane-mapping-20260804.md`](evidence/p2-control-plane-mapping-20260804.md)
(captured from the recovery evidence mapping; source digest is recorded there).
These are explicit custody items, not narrative recommendations:

- [ ] Preserve r5/VJ24 as `QUARANTINED_IMMUTABLE` and accept one causally linked
  child/new-attempt migration with fresh Run Authority fence, Custody epoch and
  WBC attempt; same-occurrence resume is forbidden.
- [ ] Join parent, migration and child across exact Run Authority, Custody, WBC,
  execution-binding and lifecycle CAS records without creating a new ledger.
- [ ] Enforce VJ9/VJ8 exact-idempotency separation: identical same-key retries
  deduplicate, divergent same-key retries return a typed conflict, and store
  and outbox share one canonical serializer.
- [ ] Bind attempt, occurrence, fingerprint and generation to every failure,
  receipt, phase result and recovery mutation; reject stale artifact clears.
- [ ] Bind runtime/source/worktree/interpreter/test identity to repair receipts;
  changed imports or test hashes fail before mutation.
- [ ] Keep occurrence IDs, consumed grants, wrapper handoff, notification
  dedupe and no-redispatch authoritative outside caller-writable projections;
  snapshot/projection corruption, storage failure and replay fail closed.
- [ ] Make the CAS gate compare an independently reread authoritative cursor;
  do not treat `DispatchIdentity`'s expected-cursor self-check as enforcement.
  Define the relationship between the integer journal cursor and the
  content-addressed source-cursor vector, then prove stale, replayed and
  divergent cursor attempts fail closed.
- [ ] Guard every plan-version writer, including direct `execute/step_edit`,
  with predecessor path/regular-file/symlink/hash verification; a mismatch
  must emit no successor bytes (landed in the r7 candidate as `0a4369db2` and
  `1fd5272f9`).
- [ ] Require fresh-child owner admission before the first model call and make
  the cursor-save → Run Authority/WBC/Custody transaction → receipt-save
  boundary replay-safe after a crash; the r7 candidate proves this with an
  immutable receipt and idempotent retry (`63b1bb1f2`, `2ac8abf7c`).
- [ ] Keep isolated cloud runtimes on their own content-addressed source ref;
  never publish a divergent candidate into the shared `editible-install`
  checkout. The default shared path retains the divergence guard; scoped
  source-ref sync is covered by the r7 cloud tests (`9a497be31`).

## Deferred platform admission/model/effect inventory — nonblocking for F3

These preserved items require a named Custody Control Plane/successor owner and
accepted completion before their affected surface is enabled. They do not block
the category-limited F2 cutline.

- [ ] Resume and complete T1.1 universal admission from
  `/private/tmp/arnold-critique-recovery-t1-1-admission-20260802` (16 dirty
  files; paused at 6 pass / 1 fail). Do not infer acceptance from preservation.
- [ ] Resume and complete T1.2 typed attempt/model handling from its preserved
  partial lane; bind exact route/model, semantic success, bounded response-loss
  retry, sticky UNKNOWN and installed parity.
- [ ] Integrate and generalize accepted T1.3 transport authority commit
  `2f1500aea1d03fbf13df5c796b17bd03d17bb79c` only through a clean descendant
  with conflict and package qualification.
- [ ] Replace the legacy `DriverOutcome(status="finalized")` compatibility
  stop with a typed `finalized_not_executed` transition: resume execute only
  when the authoritative task/cursor permits it, otherwise emit a durable
  blocked diagnostic. Finalize is plan acceptance, not terminal task success;
  keep this as a P2 control-boundary fix and retain the current regression
  evidence until the transition is landed.
- [ ] Complete generalized T1.4 graph repair/retry and T1.6 effect-family
  migration plus the full release evidence matrix.

## F2 category hardening (blocking before F3)

- [ ] Emit one `selector_task_output_contract.v1` and prove finalizer,
  admission, executor, repository auditor, VJ19 and VJ24 persist the identical
  normalized selector-to-producer map/hash. Prospective output is typed deferred;
  only an accepted result envelope satisfies it.
- [ ] Reject stale declarations and plan/runtime/validator/normalizer drift before
  dispatch; T18/T23 cannot advance without accepted result envelopes.
- [ ] Require one non-bearer canonical action-envelope receipt for every launch/resume/override/adoption
  entry point, including direct `cloud exec`, `force-proceed`, unsafe adoption,
  bootstrap, epic-chain refresh and AgentBox replay; deny or audit break-glass.
- [ ] Use one canonical, role-scoped provider resolver for orchestration/task/
  validation route/capability attestation and verify it before lease/resource
  acquisition and on resume. These facts do not grant authority.
- [ ] Bind lease/process/source/runtime identity into installed-parity and
  hostile-fault evidence; marker/tmux/PID-only `executing` is forbidden.
- [ ] Make status snapshot-first with bounded live fallback, correlate every
  projection to attempt/generation, and durably dedupe incidents across
  refresh/restart.
- [ ] Inventory all entry points and prove exactly one authoritative writer per
  execution/effect state, with no bypass.
- [ ] Replay exact VJ24 under concurrent triggers, restart and repeated polls:
  exactly one canonical repair request, one accepted Run Authority decision,
  one Custody claim, one WBC fixer attempt, one notification intent and at most
  one provider effect; duplicates are no-ops and ambiguity is
  `INDETERMINATE`/no-redispatch.

### Incident-specific controls (mandatory amendment)

The complete, auditable wording is in
[`evidence/incident-specific-control-amendment-20260804.md`](evidence/incident-specific-control-amendment-20260804.md)
(amendment ID `incident-specific-control-amendment.v1`). The following items
must be accepted rather than inferred from the bounded relaunch:

- [ ] Contain cloud `exec`, force-proceed, unsafe adoption, bootstrap,
  epic-chain refresh, and AgentBox replay behind one admission boundary;
  deny by default and audit any break-glass path.
- [ ] Issue one content-addressed, non-bearer admission receipt referencing WBC,
  Run Authority and Custody records; every action rereads current owners and the
  receipt never becomes a competing bearer authority.
- [ ] Reject stale occurrence/generation/fingerprint evidence before every
  recovery, receipt, phase, lease, and notification mutation.
- [ ] Enforce role-scoped provider resolution and shared credential bootstrap
  before lease and on resume, with redacted capability attestation.
- [ ] Use configured pinned `runtime_python` in every generated cloud command;
  reject bare interpreter/mutating relaunch fallbacks.
- [ ] Make observation snapshot-first with bounded live fallback and durable
  notification dedupe; reconcile projection cursor mismatch fail-closed.
- [ ] Classify legacy sessions and require human-gated exact-occurrence
  takeover; never implicitly revive retired launchers.

## Preserved but non-authoritative artifacts

- Rejected oversized T1.5/B7 attempt:
  `/private/tmp/arnold-critique-recovery-simple-fixer-20260802` (32 files,
  roughly 28k inserted test lines). Mine it for evidence only; never merge it
  wholesale or report it as completed work.
- Rejected bounded T1.5 pass-3 commit:
  `9642193a063d91a6be364f2d11a04b221eae30cf`, tree
  `27a3d61dff39a4c1a26a8a736dc85ce727c57b7c`. Preserve its authenticated
  receipt design, but it has no acceptance or deployment authority.
- Accepted T1.8 Stage-A release/rollback commit:
  `06d41e6b7148db4e5b464131762d63fd697db056`, tree
  `a8a67b2e01b9129673afdc7931cb3ffdce03a2de`. Its accepted scope is local
  Stage-A interface behavior; it is not cloud deploy authority.

## Epic completion rule

The follow-up epic is incomplete until every category-blocking F1/F2 checkbox
has an accepted manifest, the ordinary Critique Ledger work is completed and
deployed, incident evidence is closed without rewriting history, and real
24h/72h/7d durability observations pass. Each `DEFERRED_NONBLOCKING` platform
item must retain a named Custody Control Plane/successor owner, target and
disposition; it need not complete this epic while the affected surface remains
hard-denied. No item may disappear without accepted completion or an explicit
content-addressed supersession record.
