# Active cloud-chain review and auto-continue audit

Audit source: canonical local cloud snapshot
`/workspace/.megaplan/status/cloud-status.json` generated
`2026-07-10T23:14:50.946698Z`, followed by a read-only fresh rebuild at
`2026-07-11T00:02:01.161095Z`. No chain was launched, duplicated, or mutated by
this audit.

## Active/non-complete inventory

| Session | Declared policy | Observed review/advancement state | Disposition |
|---|---|---|---|
| `megaplan-maintenance` | `merge_policy: auto`, `auto_approve: true` | M1 reached approved review and `done`; PR merged; chain advanced to live M2 | Covered by normal guarded reconciliation; preserve the live runner and never duplicate it. |
| `runauthority-epic-cloud` | `merge_policy: auto`, `auto_approve: true` | M1 merged; M2 live under repair/recovery custody | Covered by the same automatic review and PR/between-milestone policy; preserve the active worker. |
| `discord-resident-lifecycle-corrective-20260710` | `merge_policy: auto`, `auto_approve: true` | M1 review approved and plan reached `done`, while the snapshot/chain cursor lagged | Eligible for terminal reconciliation and guarded continuation; stale watchdog `needs_human` evidence must not override newer terminal review evidence. |
| `vibecomfy-trust-corrective-2026-07` | `merge_policy: auto`, `auto_approve: true` | Corrective M1 repeatedly reported blocked execution/verification evidence | Repairable implementation work may be retried, but the verification/security artifact blocker is not auto-approved or waived. |
| `native-composition-followup` | `merge_policy: auto`, `auto_approve: true` | Historical completion manifest says complete while stale chain-health says 6/7 between milestones | Treat as completed historical evidence, not launchable work; reconciliation may repair bookkeeping but must not start a duplicate chain. |

## Shared policy contract

- Machine review after `executed` is automatic workflow work, not a human approval.
- Guarded terminal reconciliation and between-milestone continuation are automatic
  after approved review when the PR gate is satisfied.
- Open milestone PRs progress automatically only when both `merge_policy: auto`
  and effective `review_policy.clean_milestone_pr: auto` permit it. Runtime
  overrides are authoritative.
- A merged PR is durable evidence that a manual PR gate was satisfied; bookkeeping
  and later milestones may continue without asking for the same approval again.
- Explicit human verification, credential/account, quota, security/policy approval,
  pause, and tiebreaker gates remain human-only. Failed tests, unresolved merge
  conflicts, destructive cleanup, and unresolved implementation evidence remain
  repair/block outcomes rather than implicit approvals.
- Any active step or live runner is preservation-only: no duplicate launch or
  second execution is allowed.

## Implementation coverage

The shared decision model is consumed by normal chain PR progression, canonical
status observability, watchdog PR reconciliation, scheduled six-hour recovery
evidence, repair-state recovery, and the compatibility supervisor PR actor.
Existing validation, publication, completion-authority, and security/approval
guards remain the action owners and are not bypassed.

## Verification evidence

- `python -m py_compile` passed for the shared policy, chain driver, status,
  and compatibility supervisor modules.
- `bash -n` passed for watchdog, repair-loop, and progress-auditor wrappers.
- 179 focused policy/status/watchdog/scheduler/repair tests passed.
- A wider wrapper/repair run added 245 passes and retained 20 pre-existing
  failures in unrelated legacy wrapper string/lock/claim expectations from the
  dirty checkout; the new advancement tests were green.
- A read-only snapshot rebuild at `2026-07-11T00:20:10.502890Z` projected
  live/repairing chains as `preserve_live`, historical native composition as
  `none`, and VibeComfy's `awaiting_human_verify` as `await_human`.
