---
id: 01KYT5MGMXNKKAV6MV5QPWWJWW
title: Reconcile review rework against current task authority before redispatch
status: open
source: human
tags:
- bug
- rework
- authority
- execution
- completion-contract
- pre-native-blocker
codebase_id: null
created_at: '2026-07-30T18:47:22.013736+00:00'
last_edited_at: '2026-07-30T19:00:04.248941+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: null
  linked_at: 2026-07-30 19:00:04.248853+00:00
---

## Classification

MUST LAND BEFORE THE NATIVE PARITY EPIC STARTS: a narrow compatibility repair in the post-M11 stabilization bootstrap. The upcoming Native Parity S5A/S5B work then replaces this compatibility path with source-visible review/rework semantics and replays the same fixtures. Platformization supplies neutral lifecycle and bounded-cursor primitives only; it must not own this Megaplan product decision or create a second scheduler.

## Observed failure

M11 attempt 70 copied stale task IDs from review.json into a 46-task execute wave even though the current content-addressed authority projection closed 46/46 tasks. Raw review/finalize/harness status bypassed current authority during rework admission. The bulk green-suite finding also became implementation redispatch instead of one bounded validation job.

## Immediate pre-epic repair

Before any review-originated redispatch, reconcile each finding occurrence against its pinned review evidence window, current completion binding/spec, and current accepted-attempt authority. Do not suppress a task merely because it is terminal. Suppress only when current accepted evidence satisfies the exact anchored obligation or deterministically classifies the finding stale or duplicate. Otherwise emit exactly one typed disposition: reopen/new generation, new admitted task, bounded validation job, or independently verified non-action. Preserve stale review occurrences as history. Reconciliation and dispatch must be one CAS-fenced transition so a concurrent authority change cannot produce duplicate or obsolete work.

## Acceptance

- Replay M11 review v10 and exact T33/T43/T44 accepted-debt artifacts.
- Derive zero implementation redispatches for obligations already satisfied by current authority.
- Preserve genuine T9/T42 regressions as scoped rework.
- A terminal-task/new-regression fixture must reopen or create a new generation, never disappear as terminal.
- Wrong batch, phase, evidence window, binding, or debt evidence fails closed.
- A bulk verification finding creates one bounded validation job, not T1-T46 implementation work.
- Concurrent authority-close/change races yield one current CAS-bound disposition.
- Repeated resume is idempotent.
- Emit requested IDs, suppressed IDs plus authority receipts, reopened/new IDs, validation-job IDs, and disposition receipts.
- Review cannot overwrite authoritative task status with raw finalize/harness status.

## Successor-epic handoff

Native Parity S5A/S5B/S7 must consume these fixtures and prove the compatibility repair is absorbed or deleted with no fallback. C1/C2 supply stable disposition vocabulary, binding identity, and inert shadow behavior. Platformization may generalize neutral retry/generation/fanout lifecycle but may not duplicate Megaplan finding-to-task policy.
