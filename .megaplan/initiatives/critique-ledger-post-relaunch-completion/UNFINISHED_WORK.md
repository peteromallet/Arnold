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
  receipt work. Coordinated deletion or rollback of `attempts`, `claims`, and
  `simulated_effects` must query an independently authoritative monotonic
  consumed-grant/idempotency record and return typed UNKNOWN/indeterminate with
  no second attempt or effect. Evidence:
  `.megaplan/subagents/critique-ledger-recovery/T1.5/t1-5-operational-pass3-independent-review-luna.md`
  (SHA-256
  `290fcd8b2132b5834c6e6fe961a2640329bfb133eb1acd618f82fed2b3d8d13a`).
- [ ] Implement and deploy the real fixed-socket production recovery owner; the
  current SQLite owner is explicitly test-only. The production owner must issue
  the occurrence target/ref, monotonic accepted state version, quiet transition,
  due-selection result, authenticated effect receipt, and exact-once consumed
  grant.
- [ ] Fix exact-occurrence handoff: immediate/reconcile wrappers must receive the
  owner-issued occurrence ID rather than calling owner operations with zero
  arguments. Preserve the retired four-line watchdog tombstone; do not revive
  diagnostic/Kimi/meta/fallback launchers. Evidence:
  `.megaplan/subagents/critique-ledger-recovery/T1.4/incident-stall-notify-exact-implementation-map-luna.md`
  (SHA-256
  `fd83c969cd8c2ffa45819aa5d23d098974bbd2aab2b37259f48f919beada1213`).
- [ ] Prove notification custody by occurrence ID plus accepted state version:
  restart and 200 unchanged polls produce one intent/effect maximum; missing
  provenance produces zero provider effects; same-occurrence reconciliation
  cannot mint a new notification key.
- [ ] Complete generic T1.5 topology and meaningful subject-specific retirement
  proofs for all 28 historical modules / 674 functions / 741 cases.
- [ ] Complete T1.7 owner-local transactional storage, capacity, ENOSPC,
  corruption and crash recovery. Preserved worktree:
  `/private/tmp/arnold-critique-recovery-t1-7-storage-20260802` (79 pass / 1 fail
  at pause; dirty work is evidence, not accepted code).
- [ ] Complete T1.10 notification rotation, reminder/chunk/child-key policy and
  auxiliary-writer retirement.

## F2 — admission, model, effect and release closure

- [ ] Resume and complete T1.1 universal admission from
  `/private/tmp/arnold-critique-recovery-t1-1-admission-20260802` (16 dirty
  files; paused at 6 pass / 1 fail). Do not infer acceptance from preservation.
- [ ] Resume and complete T1.2 typed attempt/model handling from its preserved
  partial lane; bind exact route/model, semantic success, bounded response-loss
  retry, sticky UNKNOWN and installed parity.
- [ ] Integrate and generalize accepted T1.3 transport authority commit
  `2f1500aea1d03fbf13df5c796b17bd03d17bb79c` only through a clean descendant
  with conflict and package qualification.
- [ ] Complete generalized T1.4 graph repair/retry and T1.6 effect-family
  migration plus the full release evidence matrix.

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

The follow-up epic is incomplete until every checkbox above has an accepted
manifest or explicit supersession record, the ordinary Critique Ledger work is
completed and deployed, incident evidence is closed without rewriting history,
and real 24h/72h/7d durability observations pass.
