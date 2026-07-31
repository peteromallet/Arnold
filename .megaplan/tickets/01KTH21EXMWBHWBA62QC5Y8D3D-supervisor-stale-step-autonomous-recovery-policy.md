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
last_edited_at: '2026-07-31T06:51:07+00:00'
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

Commit `a242f6ea78` is the immediate post-M11 containment and implementation
evidence, pending merge into the release vector. It classifies heartbeat/cache
writes as non-lifecycle-authoritative and retains focused regressions showing
that they cannot arm, advance, or recover a handoff. The release umbrella
`01KYSBGRHM1S8R6RQ1DGZ7843Y` owns the exact shard rerun and deployed proof.
This ticket stays open because a write-mode classifier is a containment seam,
not the final lifecycle API.

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
