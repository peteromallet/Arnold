---
id: 01KTH21EXMWBHWBA62QC5Y8D3D
title: Supervisor stale-step autonomous recovery policy
status: open
source: human
tags:
- supervisor
- recovery
- stale-detection
- autonomy-ladder
- reliability
- managed-recovery-custody
- immediate-residual
- lifecycle-authority
- write-intent
codebase_id: null
created_at: '2026-06-07T12:48:34.740779+00:00'
last_edited_at: '2026-07-31T06:54:31+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: post-m11-ticket-reconciliation-20260731
  linked_at: '2026-07-31T03:17:11+00:00'
- epic_id: native-workflow-platformization
  resolves_on_complete: false
  kind: associated
  provenance: shard015-lifecycle-authority-reconciliation-20260731
  linked_at: '2026-07-31T06:51:07+00:00'
---

Problem
The harness has active-step metadata, heartbeat/liveness signals, an autonomy ladder, and some blocked-execute recovery, but common stalls still require manual lock/state/PID diagnosis. Dead workers, stale heartbeats, repeated schema failures, and healthy long-running phases are not handled by a deterministic in-driver recovery policy.

Acceptance criteria
- Classify active phases into healthy wait, stale heartbeat retry, dead PID unlock/resume, repeated schema failure, and terminal exhaustion.
- Stale heartbeat recovery: after bounded consecutive stale windows, kill and resume from the last safe cursor, with a strict per-phase retry cap.
- Dead PID recovery: if PID is gone but `active_step` remains, clear the active lock/state safely and resume from the last completed phase, with a strict per-plan cap.
- Repeated identical schema/contract failures bypass model tier bumps and file a diagnostic terminal ticket.
- State lock files carry structured lease content: PID, timestamp, TTL, plan name, and phase.
- Golden/characterization tests cover stale heartbeat, dead PID, repeated schema failure, and terminal ticket trace.

Suggested touchpoints
- `arnold/pipelines/megaplan/auto.py`
- `arnold/pipelines/megaplan/supervisor/ladder.py`
- `arnold/pipelines/megaplan/supervisor/chain_runner.py`
- `arnold/pipelines/megaplan/control_interface.py`
- `arnold/runtime/resume.py`
- `tests/test_supervisor_ladder.py`

## 2026-07-31 reconciliation

M11 plus the post-M11 fixes now provide canonical repair custody, dead-PID
liveness checks, bounded event checkpoints, and safer handoff. Keep open:
structured lock leases, bounded stale-heartbeat kill/resume, repeated-schema
terminal classification, exact live replay, and the full golden policy matrix
are not complete. Native S6 is associated because it consumes and demotes
recovery control paths, but cannot auto-close these immediate residuals.

## 2026-07-31 shard 015 authority finding

Shard 015 reproduced a deeper source of false stale/dead-worker symptoms:
`active-step-heartbeat` was implemented through the same state-write function
as lifecycle transitions, and every successful write unconditionally ran
durable handoff reconciliation. A cache refresh could therefore reinterpret
already-committed execute/review custody, mutate or clear `active_step`, and
make the next observer report a stall that the heartbeat writer itself caused.

Commit `be164da4cb` is the reviewed immediate post-M11 containment. It guards
only the known `active-step-heartbeat` path from handoff reconciliation and
retains focused regressions showing that a heartbeat cannot arm, advance, or
recover a handoff while an authoritative lifecycle transition still can. Those
focused tests are green, the exact frozen shard passed 475/475 with zero debt,
and the change merged into the consolidation vector at `6027584bf9`. The
content-addressed receipt is
`Arnold-validation-checkpoints/be164da-shard015-exact-20260731/receipts/full-suite-015-be164da.json`
(`sha256:8494218e44063815fa1a622a49d81656a74ab17d62505c70f31e8bd36b36a0c2`).
The release umbrella `01KYSBGRHM1S8R6RQ1DGZ7843Y` remains open for the complete
frozen inventory and deployed live canary.

The broader nonlanded classifier experiment at `a242f6ea78` was rejected:
transport-mode names do not reliably describe semantic write authority across
missing files, full-state compatibility writes, declared-but-absent keys,
metadata, and opaque callbacks. This ticket stays open because the narrow
guard is release containment, not the final lifecycle API.

## Durable product and platform follow-up

Do not keep extending transport modes such as `patch-many`,
`executor-key-merge`, or `merge-meta-list` into an implicit authority table.
Their authority depends on the declared and actual write set, existing-file
state, opaque callbacks, and whether supplied lifecycle fields are preserved;
the mode name alone is not a semantic contract.

Native Parity must inventory and migrate the surviving Megaplan call sites to
an explicit, schema-versioned `WriteIntent` (or equivalent
`commit_lifecycle_transition`) that declares:

- observation/cache versus lifecycle-transition intent;
- expected source revision/cursor/fence and the exact changed key/delta set;
- the lifecycle transition or handoff operation being requested; and
- the durable receipt proving the admitted delta and resulting state.

Platformization must then own the neutral delta-aware lifecycle interface and
conformance suite used by Megaplan and the independent second consumer. The
Native Parity and Platformization links are association-only: neither epic may
auto-address this ticket merely by finishing.

Add these acceptance proofs to the existing stale-step matrix:

1. Observation, cache, heartbeat, Markdown, and status-projection writes cannot
   arm, claim, cross, recover, or erase a lifecycle handoff.
2. Admitted lifecycle transitions to `executed`, `review`, and terminal
   dispositions perform the required reconciliation exactly once.
3. Concurrent and stale heartbeats preserve a newer committed handoff and fail
   closed on a cursor/fence mismatch.
4. A generated call-site inventory proves every lifecycle-capable writer uses
   the typed intent API before mode-based inference is removed.
5. Missing files, absent declared keys, full-state compatibility inputs,
   metadata carrying handoff receipts, and opaque mutations have explicit
   deterministic dispositions rather than inheriting authority accidentally.
