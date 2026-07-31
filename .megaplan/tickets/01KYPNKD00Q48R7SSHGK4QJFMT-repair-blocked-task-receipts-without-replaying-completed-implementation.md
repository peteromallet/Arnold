---
id: 01KYPNKD00Q48R7SSHGK4QJFMT
title: Repair blocked task receipts without replaying completed implementation
status: open
source: human
tags:
- bug
- recovery
- task-receipts
- authority
- write-set
- execution-transaction-integrity
- pre-native-blocker
codebase_id: null
created_at: '2026-07-29T10:09:24.992935+00:00'
last_edited_at: '2026-07-30T19:00:17.814211+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: null
  linked_at: 2026-07-30 19:00:17.814131+00:00
---

## Classification

MUST LAND IN THE POST-M11 CONTAINMENT/RELEASE FOLLOW-UP BEFORE THE NATIVE PARITY EPIC STARTS. Native S5A/S5B must replay and absorb these fixtures, but it must not be the first place this production recovery defect is repaired.

## Problem

M11 T27/T28/T30/T7/T8 and attempt-66 T33/T43 implemented valid work, but task receipts were rejected for task-contract defects including missing shared paths, per-command time accounting collapsed into an aggregate budget, generated outputs absent from immutable scope, and descendant files treated as outside an admitted directory. Retrying unchanged implementation merely reproduced rejection.

## Contract-generation repair

Before dispatch, validate that objective-implied implementation surfaces, generated-output classes, validation selectors, and shared-file ownership are representable by the admitted task contract. Define per-command budgets separately from an optional total-task budget. Define canonical directory/write semantics for descendants, symlinks, traversal, renames, deletes, ignored files, and overlapping ownership. Correct the task contract or fail closed before execution.

## Recovery repair

Keep rejected attempts immutable. If valid landed work exists, recovery must prove the exact pre-attempt baseline and landed tree/commit, then create one CAS-fenced scope amendment or successor generation authorized against the current task/batch/attempt. Zero implementation body or effect execution may repeat; admitted verification commands may run. Never accept an aggregate dirty tree as a baseline and never silently widen authority.

## Acceptance

- Replay exact T30, T7/T8, T33, and T43 artifacts.
- Bind every decision to canonical task, batch, attempt, generation, pre-attempt baseline, landed tree/commit, write-set version, and test selector.
- Original rejected receipts remain immutable and inspectable.
- Competing amendments race through CAS; exactly one current amendment/successor claim wins.
- Crash immediately before or after amendment and successor-claim publication resumes idempotently.
- No undeclared path is accepted; directory/generated-output rules cover hostile symlink, traversal, rename/delete, ignored-file, and overlap cases.
- Zero body/effect re-execution; only admitted narrow verification runs.
- Exactly one authority-valid successor claim is accepted and the plan advances automatically.

## Successor-epic handoff

Native S5A/S5B/S7 consume these exact regressions and prove the compatibility recovery path is absorbed into declared review/rework lifecycle. C1/C2 provide immutable binding/evidence identity. Platformization may generalize retry/generation/fanout mechanics but cannot weaken Megaplan authority, write-set, or recovery policy.

## 2026-07-31 implementation evidence and residual

Implemented in `b39c6012ac` and `937df385dd`. Exact-match landed work can now
produce one CAS-fenced immutable successor claim without rerunning the
implementation worker. The claim binds task, batch, rejected attempt,
generation, revision, authority digest, baseline, landed tree, write-set
version, paths, verification commands, and receipt digest. Verification
commands are checked against narrow selectors and budgets and are actually run
before adoption.

Keep this ticket open until the exact archived T30/T7/T8/T33/T43 fixtures are
replayed. Canonical directory, symlink, rename/delete, ignored-file, and
overlapping-write-set semantics also still need completion in the task
contract generator and write validator.
